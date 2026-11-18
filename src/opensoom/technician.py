"""Facility-scoped human workbench served separately from the operator and MEC apps."""
from __future__ import annotations

import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .maintenance import current_order_view, latest_damper_commands, select_work_orders
from .maintenance_worker import key, read_content, safe_rn
from .onem2m import CSEClient, CSEError


class Inspection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    work_order_ri: str = Field(pattern=r"^[a-zA-Z0-9._-]{1,128}$")
    request_id: UUID
    action: Literal["scheduled", "checked", "escalated"]
    note: str = Field(default="", max_length=280)


class FieldDesk:
    def __init__(self, config, cse):
        self.facility = config["facility_id"]
        self.path = config["facility_path"].strip("/")
        if self.path.split("/")[-3:] != ["opensoom", "facilities", safe_rn(self.facility)]:
            raise ValueError("Choose the commissioned facility resource path")
        self.zones = config["zones"]
        self.name = config["name"]
        self.profile = config["profile"]
        self.simulation = config["simulation"]
        self.cse = cse
        self.cache = {}
        self.lock = RLock()

    PAGE_SIZE = 64

    @staticmethod
    def stream_version(container):
        if container.get("disr"):
            raise HTTPException(503, "Reading content is disabled for this facility stream.")
        # ACME increments st on creation; deletion can change cni without changing st.
        return container["ri"], container["st"], container["cni"]

    def read_page(self, path, version, filters):
        reply = self.cse.retrieve(path, params={"rcn": 4, "ty": 4, "lvl": 1, **filters})
        container = reply["body"]["m2m:cnt"]
        if self.stream_version(container) != version:
            return None
        records = []
        for cin in container.get("m2m:cin", []):
            data = read_content(cin)
            if cin["pi"] != version[0] or data.get("facility_id") != self.facility:
                raise ValueError("Record has inconsistent facility provenance")
            records.append({**data, "resource_id": cin["ri"], "read_rqi": reply["rqi"],
                            "recorded_at": cin["ct"], "state_tag": cin["st"]})
        return records

    def retained_records(self, path, version, saved):
        parent, tag, count = version
        if saved and saved[1]:
            (old_parent, old_tag, old_count), previous = saved
            added = count - old_count
            if old_parent == parent and 0 < added == tag - old_tag and added <= self.PAGE_SIZE:
                # An equal increase in tag and count means pure appends in this CSE.
                delta = self.read_page(path, version, {"sts": old_tag})
                if delta is None:
                    return None
                if len(delta) == added and all(old_tag < row["state_tag"] <= tag for row in delta):
                    return previous + delta

        records = []
        # Offset is 1-based. In the pinned CSE virtual /la, /ol and a stream
        # subscription can occupy offsets before the CIN type filter runs.
        for offset in range(1, count + self.PAGE_SIZE + 1, self.PAGE_SIZE):
            page = self.read_page(path, version, {"lim": self.PAGE_SIZE, "ofst": offset})
            if page is None:
                return None
            records.extend(page)
            if len(records) >= count:
                break
        return records

    def stream(self, stream):
        path = self.path + "/" + stream
        for _ in range(2):
            version = self.stream_version(self.cse.retrieve(path)["body"]["m2m:cnt"])
            saved = self.cache.get(stream)
            if saved and saved[0] == version:
                return saved[1]
            rows = self.retained_records(path, version, saved) if version[2] else []
            if rows is None or len(rows) != version[2] or len({row["resource_id"] for row in rows}) != version[2]:
                continue
            if rows and self.stream_version(self.cse.retrieve(path)["body"]["m2m:cnt"]) != version:
                continue
            self.cache[stream] = version, rows
            return rows
        raise HTTPException(503, "Could not read the complete current facility stream. Refresh to retry.")

    def work_orders(self):
        orders = self.stream("work_orders")
        incident_by_command = {o["command_id"]: o["incident_id"] for o in orders if o.get("command_id")}
        commands = []
        for zone in {o["zone_id"] for o in orders}:
            if zone not in self.zones:
                raise ValueError("Work order has no commissioned zone")
            for ack in self.stream(safe_rn(zone) + "/acks"):
                if ack.get("device_state") == "damper_changed" and ack.get("zone_id") == zone:
                    commands.append({**ack, "action": "set_damper", "id": ack["command_id"],
                                     "incident_id": ack.get("incident_id") or incident_by_command.get(ack["command_id"]),
                                     "ack_sequence": ack["state_tag"], "ack_rqi": ack["read_rqi"]})
        active = latest_damper_commands(commands)
        inspections = self.stream("inspections")
        notes = {n["request_id"]: n.get("note", "") for n in self.stream("inspection_notes")}
        actions_by_order = {}
        for entry in inspections:
            actions_by_order.setdefault(entry["work_order_id"], []).append(
                {**entry, "note": notes.get(entry["request_id"], "")})
        results = []
        for order in select_work_orders(orders, active):
            item = current_order_view(order, active)
            zone = self.zones[item["zone_id"]]
            actions = actions_by_order.get(item["work_order_id"], [])
            actions.sort(key=lambda r: (r["recorded_at"], r["state_tag"]), reverse=True)
            target = item.get("target_airflow_m3_h")
            current = active.get((self.facility, item["zone_id"], item["incident_id"]), {})
            if item.get("command_id") == current.get("id") and current:
                item = {"requested_pct": current["value"], **item}
            results.append({**item, "zone_name": zone["name"], "inspections": actions,
                            "configured_target_m3_h": target if target is not None else zone["target_m3_h"],
                            "target_source": "work_order_cin" if target is not None else "current_facility_configuration"})
        return sorted(results, key=lambda o: (o["observed_at"], o["work_order_id"]), reverse=True)

    def queue(self):
        with self.lock:
            return {"facility": {"id": self.facility, "name": self.name, "profile": self.profile,
                                 "simulation": self.simulation}, "work_orders": self.work_orders()}

    def record(self, order_id, form):
        with self.lock:
            name = key("inspection", self.facility, str(form.request_id))
            scope = {"facility_id": self.facility, "work_order_id": order_id, "work_order_ri": form.work_order_ri,
                     "action": form.action, "request_id": str(form.request_id)}
            private = {**scope, "kind": "technician.field_note", "note": form.note}

            def read(stream, expected):
                try:
                    result = self.cse.retrieve(self.path + "/" + stream + "/" + name)
                except CSEError as exc:
                    if exc.rsc == 4004:
                        return None
                    raise
                cin = result["body"]["m2m:cin"]
                item = read_content(cin)
                if any(item.get(k) != v for k, v in expected.items()):
                    raise HTTPException(409, "This request already belongs to another inspection entry.")
                return {**item, "resource_id": cin["ri"], "read_rqi": result["rqi"], "recorded_at": cin["ct"]}

            def write(stream, entry):
                try:
                    self.cse.create(self.path + "/" + stream, 4, {"m2m:cin": {
                        "rn": name, "cnf": "application/json:0", "con": json.dumps(entry)}})
                except CSEError as exc:
                    if exc.rsc != 4105:
                        raise
                receipt = read(stream, entry)
                if receipt is None:
                    raise HTTPException(503, "Inspection entry could not be read back.")
                return receipt

            # Persist the exact note and reviewed decision in a private stream first.
            # Retrying an interrupted pair completes its public disposition from that record.
            note = read("inspection_notes", private)
            if note is None:
                order = next((o for o in self.work_orders() if o["work_order_id"] == order_id), None)
                if order is None:
                    raise HTTPException(404, "Work order is outside this facility queue.")
                if order.get("resource_id") != form.work_order_ri:
                    raise HTTPException(409, "The work order changed. Review the latest evidence before recording the inspection.")
                note = write("inspection_notes", {**private, "zone_id": order["zone_id"], "asset_id": order["asset_id"],
                             "command_id": order.get("command_id"), "priority_reviewed": order["priority"]})
            entry = {**scope, **{k: note[k] for k in ("zone_id", "asset_id", "command_id", "priority_reviewed")},
                     "kind": "technician.inspection"}
            existing = read("inspections", entry)
            return {**(existing or write("inspections", entry)), "note": note["note"]}



def build_app(desk):
    """Loopback lab session. A deployed technician service needs a site identity provider."""
    session = secrets.token_urlsafe(36)
    assets = Path(__file__).with_name("technician_web")

    @asynccontextmanager
    async def lifespan(app):
        yield
        desk.cse.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
            return JSONResponse({"detail": "Open the local technician service."}, status_code=403)
        origin = request.headers.get("origin")
        if (origin or request.method == "POST") and origin != f"{request.url.scheme}://{request.headers.get('host')}":
            return JSONResponse({"detail": "Use the technician workbench on its own origin."}, status_code=403)
        response = await call_next(request)
        response.headers.update({"cache-control": "no-store", "referrer-policy": "no-referrer",
                                 "x-content-type-options": "nosniff", "x-frame-options": "DENY",
                                 "content-security-policy": "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    def check_session(request):
        if not secrets.compare_digest(request.cookies.get("opensoom_field_" + str(request.url.port), "").encode(), session.encode()):
            raise HTTPException(401, "Open the site technician workbench to start a local session.")

    @app.exception_handler(CSEError)
    async def cse_unavailable(request, exc):
        return JSONResponse({"detail": "The facility work queue is unavailable.", "rsc": exc.rsc}, status_code=503)

    @app.get("/")
    def home(request: Request):
        response = FileResponse(assets / "index.html")
        response.set_cookie("opensoom_field_" + str(request.url.port), session, httponly=True,
                            samesite="strict", path="/api/work-orders")
        return response

    @app.get("/api/work-orders")
    def queue(request: Request):
        check_session(request)
        return desk.queue()

    @app.post("/api/work-orders/{order_id}/inspections")
    def record(order_id: str, data: Inspection, request: Request):
        check_session(request)
        return desk.record(order_id, data)

    return app


def create_app():
    config = json.loads(Path(os.environ["OPENSOOM_TECHNICIAN_CONFIG"]).read_text())
    token = os.environ["OPENSOOM_TECHNICIAN_CSE_TOKEN"]
    if not token or not config["origin"] or config["origin"] == "CAdmin" or not config["cse_url"].startswith("https://"):
        raise ValueError("Use the technician AE's credential and authenticated TLS gateway")
    client = CSEClient(config["cse_url"], config["origin"], ca_file=config["cse_ca"], bearer_token=token, timeout=5)
    return build_app(FieldDesk(config, client))
