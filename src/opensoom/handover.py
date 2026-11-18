"""Optional application-managed serving-CSE maintenance transition.

The controller and virtual actuator share a durable local authority database.
This is deliberately not distributed consensus, native AE registration mobility,
process migration, or a hardware controller. See docs/handover.md for scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

from .onem2m import CSEClient, CSEError


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


class AuthorityStore:
    """One local transaction orders fencing, deduplication and virtual effects."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS records (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS executions (command_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, receipt TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=5)

    def get(self, key: str, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM records WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key: str, value: Any):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO records VALUES (?,?)", (key, json.dumps(value)))

    def activate(self, expected: dict | None, target: str, cse_id: str) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM records WHERE key='authority'").fetchone()
            current = json.loads(row[0]) if row else None
            if current != expected:
                raise RuntimeError("Authority changed concurrently; refusing a second transition")
            authority = {"target": target, "cse_id": cse_id, "epoch": (current["epoch"] + 1) if current else 1}
            db.execute("INSERT OR REPLACE INTO records VALUES ('authority',?)", (json.dumps(authority),))
        return authority

    def stage_restoration(self, target: str, cse_id: str) -> dict:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT value FROM records WHERE key='restore_pending'").fetchone()
            if previous:
                return json.loads(previous[0])
            authority = json.loads(db.execute("SELECT value FROM records WHERE key='authority'").fetchone()[0])
            snapshot = json.loads(db.execute("SELECT value FROM records WHERE key='snapshot'").fetchone()[0])
            marker = {"from": authority, "target": target, "target_cse_id": cse_id, "snapshot": snapshot, "started_at": timestamp(), "attempts": 0}
            db.execute("INSERT INTO records VALUES ('restore_pending',?)", (json.dumps(marker),))
            return marker

    def commit_restoration(self, marker: dict, snapshot: dict) -> dict:
        """Authority, restored checkpoint and marker removal commit together."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            pending = db.execute("SELECT value FROM records WHERE key='restore_pending'").fetchone()
            authority = json.loads(db.execute("SELECT value FROM records WHERE key='authority'").fetchone()[0])
            if not pending or json.loads(pending[0]) != marker or authority != marker["from"]:
                raise RuntimeError("Restoration authority or snapshot changed concurrently")
            successor = {"target": marker["target"], "cse_id": marker["target_cse_id"], "epoch": authority["epoch"] + 1}
            db.execute("INSERT OR REPLACE INTO records VALUES ('authority',?)", (json.dumps(successor),))
            db.execute("INSERT OR REPLACE INTO records VALUES ('snapshot',?)", (json.dumps(snapshot),))
            db.execute("DELETE FROM records WHERE key='restore_pending'")
            return successor

    def defer_restoration(self, marker: dict) -> dict:
        """Do not resurrect a failed preparation after another worker commits."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT value FROM records WHERE key='restore_pending'").fetchone()
            authority = json.loads(db.execute("SELECT value FROM records WHERE key='authority'").fetchone()[0])
            if not row or json.loads(row[0]) != marker or authority != marker["from"]:
                raise RuntimeError("Restoration changed before failure could be recorded")
            updated = {**marker, "attempts": marker["attempts"] + 1}
            db.execute("UPDATE records SET value=? WHERE key='restore_pending'", (json.dumps(updated),))
            return updated

    def execute_virtual(self, command: dict, source_cse_id: str) -> dict:
        """Apply only a current, unexpired command, once. No physical actuation."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            def read(key):
                row = db.execute("SELECT value FROM records WHERE key=?", (key,)).fetchone()
                return json.loads(row[0]) if row else None
            authority, snapshot = read("authority"), read("snapshot")
            if not authority or command.get("target") != authority["target"] or command.get("epoch") != authority["epoch"] or command.get("source_cse_id") != source_cse_id or source_cse_id != authority["cse_id"]:
                return {"status": "rejected", "code": "stale_authority", "command_id": command.get("command_id")}
            if command.get("facility_id") != snapshot["facility_id"] or command.get("profile_version") != snapshot["profile_version"]:
                return {"status": "rejected", "code": "scope_mismatch", "command_id": command.get("command_id")}
            try:
                expires = datetime.fromisoformat(command["expires_at"])
                issued = datetime.fromisoformat(command["issued_at"])
                value = command["value"]
                now = datetime.now(timezone.utc)
                valid = isinstance(command.get("command_id"), str) and 1 <= len(command["command_id"]) <= 128 and expires.tzinfo is not None and issued.tzinfo is not None and issued <= now < expires and 0 < (expires - issued).total_seconds() <= snapshot.get("command_ttl_seconds", 60) and command["action"] == "set_damper" and type(value) in (float, int) and 0 <= value <= 100
            except (KeyError, TypeError, ValueError):
                valid = False
            if not valid:
                return {"status": "rejected", "code": "expired_or_invalid", "command_id": command.get("command_id")}
            business = {k: command[k] for k in ("command_id", "facility_id", "profile_version", "action", "value", "issued_at", "expires_at")}
            fingerprint = hashlib.sha256(json.dumps(business, sort_keys=True).encode()).hexdigest()
            previous = db.execute("SELECT fingerprint,receipt FROM executions WHERE command_id=?", (command["command_id"],)).fetchone()
            if previous:
                if previous[0] != fingerprint:
                    return {"status": "rejected", "code": "idempotency_conflict", "command_id": command["command_id"]}
                return {**json.loads(previous[1]), "status": "duplicate", "applied_again": False}
            receipt = {"status": "applied", "command_id": command["command_id"], "applied_at": timestamp(), "epoch": authority["epoch"], "target": authority["target"], "damper_pct": value, "simulated": True}
            db.execute("INSERT INTO executions VALUES (?,?,?)", (command["command_id"], fingerprint, json.dumps(receipt)))
            db.execute("INSERT OR REPLACE INTO records VALUES ('virtual_device',?)", (json.dumps(receipt),))
            return receipt

    def execution_count(self) -> int:
        with self.connect() as db:
            return db.execute("SELECT count(*) FROM executions").fetchone()[0]


@dataclass
class ServingCSE:
    key: str
    url: str
    base: str
    cse_id: str
    client: CSEClient
    root: str = ""
    roles: dict = field(default_factory=dict)
    resources: dict = field(default_factory=dict)


class MaintenanceHandover:
    """Stable logical facility routed to one of two preconfigured real CSEs.

    Privileged provisioning is explicit. Ordinary data/command/ACK requests use
    scoped registered AE origins. Only a failed transport health probe triggers
    the bounded A-to-B transition; permission/configuration errors fail closed.
    """

    def __init__(self, targets: list[ServingCSE], store: AuthorityStore, namespace: str, callback_url: str, failure_threshold: int = 2):
        if len(targets) != 2 or targets[0].cse_id == targets[1].cse_id or failure_threshold < 1:
            raise ValueError("Two independent CSE identities and a positive threshold are required")
        self.targets = {target.key: target for target in targets}
        self.store, self.namespace, self.callback_url = store, namespace, callback_url
        self.failure_threshold, self.failures = failure_threshold, 0
        self.history, self.notifications = [], []
        self._lock = threading.RLock()

    @property
    def active(self) -> ServingCSE:
        return self.targets[self.store.get("authority")["target"]]

    def _ensure(self, target, parent, ty, tag, attrs, origin=None):
        try:
            return target.client.create(parent, ty, {tag: attrs}, origin=origin)
        except CSEError as error:
            if error.rsc not in (4105, 4117):
                raise
            return target.client.retrieve(parent + "/" + attrs["rn"], origin=origin)

    def provision(self, target: ServingCSE) -> dict:
        base = target.client.retrieve(target.base)
        if base["body"]["m2m:cb"]["csi"] != target.cse_id:
            raise RuntimeError("Configured target CSE identity does not match actual CSE")
        registrations = {}
        for role in ("controller", "device", "observer"):
            name = self.namespace + "-" + role
            origin = "Cho" + hashlib.sha256((name + target.key).encode()).hexdigest()[:18]
            result = self._ensure(target, target.base, 2, "m2m:ae", {"rn": name, "api": "N.org.opensoom.handover", "rr": False, "srv": ["4"]}, origin)
            target.roles[role] = result["body"]["m2m:ae"]["aei"]
            registrations[role] = result
        target.root = target.base + "/" + self.namespace + "-controller"
        policies = {}
        for kind in ("state", "observations", "commands", "acks"):
            permissions = {"controller": 35 if kind in ("state", "commands") else 34,
                           "device": 35 if kind in ("observations", "acks") else (34 if kind == "commands" else 0),
                           "observer": 34 if kind != "state" else 0}
            rules = [{"acor": ["CAdmin"], "acop": 63}] + [{"acor": [target.roles[role]], "acop": access} for role, access in permissions.items() if access]
            result = self._ensure(target, target.base, 1, "m2m:acp", {"rn": self.namespace + "-" + kind + "-policy", "pv": {"acr": rules}, "pvs": {"acr": [{"acor": ["CAdmin"], "acop": 63}]}})
            policies[kind] = result
        for name in ("state", "incident", "observations", "commands", "acks"):
            policy = policies["state" if name == "incident" else name]["body"]["m2m:acp"]["ri"]
            result = self._ensure(target, target.root, 3, "m2m:cnt", {"rn": name, "mni": 100, "acpi": [policy], "lbl": ["opensoom:maintenance-handover"]})
            target.resources[name] = result["body"]["m2m:cnt"]["ri"]
        subscription = self._ensure(target, target.root + "/observations", 23, "m2m:sub", {"rn": "diagnosis", "nu": [self.callback_url], "enc": {"net": [3]}, "nct": 1})
        return {"cse_base": base, "registrations": registrations, "policies": policies, "subscription": subscription, "root": target.root}

    def write(self, target, container, body, role="controller", rn=None):
        attrs = {"con": json.dumps(body), "cnf": "application/json:0"}
        if rn:
            attrs["rn"] = rn
        return target.client.create(target.root + "/" + container, 4, {"m2m:cin": attrs}, origin=target.roles[role])

    @serialized
    def initialize(self, state: dict) -> dict:
        if self.store.get("authority"):
            raise RuntimeError("Use an isolated new checkpoint for an initial transition")
        self.store.put("snapshot", state)
        target = next(iter(self.targets.values()))
        provisioned = self.provision(target)
        self.store.activate(None, target.key, target.cse_id)
        self.persist_snapshot()
        return provisioned

    @serialized
    def persist_snapshot(self):
        snapshot = self.store.get("snapshot")
        self.write(self.active, "state", snapshot)
        self.write(self.active, "incident", snapshot["incident"])

    @serialized
    def publish_observation(self, observation: dict):
        if self.store.get("restore_pending"):
            raise RuntimeError("Observation submission paused while a target is being restored")
        return self.write(self.active, "observations", observation, "device")

    @serialized
    def queue_command(self, command_id: str, value: float, expires_at: str) -> dict:
        if self.store.get("restore_pending"):
            raise RuntimeError("New command submission paused while a target is being restored")
        snapshot, authority = self.store.get("snapshot"), self.store.get("authority")
        issued = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(expires_at)
        if not isinstance(command_id, str) or not 1 <= len(command_id) <= 128 or type(value) not in (int, float) or not 0 <= value <= 100 or expires.tzinfo is None or not 0 < (expires - issued).total_seconds() <= snapshot.get("command_ttl_seconds", 60):
            raise ValueError("Command identity, setpoint and lifetime must match the configured simulation profile")
        command = {"command_id": command_id, "facility_id": snapshot["facility_id"], "profile_version": snapshot["profile_version"], "action": "set_damper", "value": value, "issued_at": issued.isoformat(), "expires_at": expires_at, **authority, "source_cse_id": self.active.cse_id}
        result = self.write(self.active, "commands", command)
        snapshot["pending_command"] = command
        self.store.put("snapshot", snapshot)
        self.persist_snapshot()
        return result

    def _prepared_content(self, target, name, body, role, epoch):
        rn = "restored-" + name + "-e" + str(epoch)
        result = self._ensure(target, target.root + "/" + name, 4, "m2m:cin", {"rn": rn, "con": json.dumps(body), "cnf": "application/json:0"}, target.roles[role])
        actual = result["body"]["m2m:cin"]["con"]
        if (json.loads(actual) if isinstance(actual, str) else actual) != body:
            raise RuntimeError("Existing target restoration content conflicts with the staged snapshot")
        readback = target.client.retrieve(target.root + "/" + name + "/" + rn, origin=target.roles[role])
        content = readback["body"]["m2m:cin"]["con"]
        if (json.loads(content) if isinstance(content, str) else content) != body:
            raise RuntimeError("Target restoration readback differs")
        return readback

    def _resume_restoration(self, marker):
        alternative = self.targets[marker["target"]]
        if alternative.cse_id != marker["target_cse_id"] or self.store.get("authority") != marker["from"]:
            raise RuntimeError("Pending restoration no longer matches configured authority")
        if marker["attempts"] >= 3:
            raise RuntimeError("Bounded restoration attempts exhausted; authority remains fenced")
        try:
            restored = self.provision(alternative)
            snapshot = json.loads(json.dumps(marker["snapshot"]))
            epoch = marker["from"]["epoch"] + 1
            pending = snapshot.get("pending_command")
            if pending:
                pending = {**pending, "target": alternative.key, "cse_id": alternative.cse_id, "epoch": epoch, "source_cse_id": alternative.cse_id}
                snapshot["pending_command"] = pending
            # Every remote write and authoritative readback precedes activation.
            prepared = {"state": self._prepared_content(alternative, "state", snapshot, "controller", epoch),
                        "incident": self._prepared_content(alternative, "incident", snapshot["incident"], "controller", epoch)}
            if snapshot.get("last_observation"):
                prepared["observations"] = self._prepared_content(alternative, "observations", snapshot["last_observation"], "device", epoch)
            if pending:
                prepared["commands"] = self._prepared_content(alternative, "commands", pending, "controller", epoch)
        except CSEError as error:
            if error.rsc != 0 and error.rsc < 5000:
                raise
            marker = self.store.defer_restoration(marker)
            event = {"at": timestamp(), "kind": "target_restore_pending", "target": alternative.key, "attempt": marker["attempts"], "authority_retained": self.store.get("authority"), "response": error.result}
            self.history.append(event)
            return event
        successor = self.store.commit_restoration(marker, snapshot)
        self.failures = 0
        event = {"at": timestamp(), "kind": "serving_cse_changed", "trigger": "consecutive_transport_failures", "from": marker["from"], "to": successor, "restoration": restored, "prepared_readbacks": prepared, "resumed_after_failures": marker["attempts"]}
        self.history.append(event)
        return event

    @serialized
    def tick(self) -> dict:
        marker = self.store.get("restore_pending")
        if marker:
            return self._resume_restoration(marker)
        authority = self.store.get("authority")
        target = self.active
        try:
            result = target.client.retrieve(target.root + "/state/la", origin=target.roles["controller"])
        except CSEError as error:
            if error.rsc != 0:
                raise
            self.failures += 1
            event = {"at": timestamp(), "kind": "transport_failure", "target": target.key, "count": self.failures, "response": error.result}
            self.history.append(event)
            if self.failures < self.failure_threshold:
                return event
            # One directed maintenance transition, never automatic failback.
            alternative = next(item for item in self.targets.values() if item.key != target.key)
            if authority["epoch"] != 1:
                raise RuntimeError("Both targets unavailable; no unbounded switching")
            marker = self.store.stage_restoration(alternative.key, alternative.cse_id)
            return self._resume_restoration(marker)
        self.failures = 0
        return {"at": timestamp(), "kind": "healthy", "target": target.key, "response": result}

    @serialized
    def accept_notification(self, event: dict) -> dict | None:
        """Callback is a hint; reread its CIN from the fixed active CSE."""
        if self.store.get("restore_pending"):
            return None
        signal = event.get("body", {}).get("m2m:sgn", {})
        cin = signal.get("nev", {}).get("rep", {}).get("m2m:cin")
        if not cin or cin.get("pi") != self.active.resources["observations"] or not signal.get("sur", "").startswith(self.active.cse_id + "/"):
            return None
        actual = self.active.client.retrieve(self.active.root + "/observations/" + cin["rn"], origin=self.active.roles["controller"])
        reread = actual["body"]["m2m:cin"]
        if reread["ri"] != cin["ri"] or reread["pi"] != self.active.resources["observations"]:
            raise RuntimeError("Callback and authoritative CIN identity differ")
        observation = json.loads(reread["con"])
        snapshot = self.store.get("snapshot")
        if observation["facility_id"] != snapshot["facility_id"]:
            raise RuntimeError("Observation belongs to a different logical facility")
        if observation["sequence"] <= snapshot.get("last_sequence", 0):
            return None
        snapshot.update(last_observation=observation, last_sequence=observation["sequence"])
        self.store.put("snapshot", snapshot)
        self.persist_snapshot()
        result = {"at": timestamp(), "authority": self.store.get("authority"), "callback": event, "authoritative_read": actual, "sequence": observation["sequence"]}
        self.notifications.append(result)
        return result

    def logical_snapshot(self) -> dict:
        authority = self.store.get("authority")
        target = self.targets[authority["target"]]
        state = target.client.retrieve(target.root + "/state/la", origin=target.roles["controller"])
        incident = target.client.retrieve(target.root + "/incident/la", origin=target.roles["controller"])
        return {"logical_facility_id": self.store.get("snapshot")["facility_id"], "serving_cse_id": target.cse_id, "serving_url": target.url, "authority": authority, "state": state, "incident": incident}

    def read_command(self, target=None) -> dict:
        target = target or self.active
        return target.client.retrieve(target.root + "/commands/la", origin=target.roles["device"])

    @serialized
    def apply_virtual(self, retrieved: dict, source: ServingCSE) -> dict:
        command = json.loads(retrieved["body"]["m2m:cin"]["con"])
        receipt = self.store.execute_virtual(command, source.cse_id)
        if receipt["status"] in ("applied", "duplicate"):
            # A crash after the atomic virtual effect but before CSE ACK can be
            # retried without a second effect. One deterministic ACK per epoch.
            name = "ack-" + hashlib.sha256((command["command_id"] + ":" + str(command["epoch"])).encode()).hexdigest()[:20]
            self._ensure(source, source.root + "/acks", 4, "m2m:cin", {"rn": name, "con": json.dumps(receipt), "cnf": "application/json:0"}, source.roles["device"])
            snapshot = self.store.get("snapshot")
            if (snapshot.get("pending_command") or {}).get("command_id") == command["command_id"]:
                snapshot.update(pending_command=None, last_command=command, last_ack=receipt)
                self.store.put("snapshot", snapshot)
                self.persist_snapshot()
        return receipt
