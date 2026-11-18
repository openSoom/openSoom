"""Discover an approved ETSI sensor-sharing service and read one mapped sensor."""
from __future__ import annotations

import hashlib
import json
import math
import threading
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

import httpx


class EvidenceError(ValueError):
    """A short, nonsecret reason that an input cannot support a diagnosis."""


def timestamp(value: str) -> datetime:
    try:
        instant = datetime.fromisoformat(value)
        if instant.utcoffset() is None:
            raise ValueError
        return instant.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EvidenceError("invalid_measurement_time") from exc


def percentage(value):
    if isinstance(value, bool):
        raise EvidenceError("invalid_percentage")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise EvidenceError("invalid_percentage") from exc
    if not math.isfinite(result) or not 0 <= result <= 100:
        raise EvidenceError("invalid_percentage")
    return result


def unique_sensor(value, sensor_id):
    rows = value if isinstance(value, list) else [value]
    matches = [row for row in rows if isinstance(row, dict) and row.get("sensorIdentifier") == sensor_id]
    if len(matches) != 1:
        raise EvidenceError("unexpected_sensor")
    return matches[0]


def provider_sample(raw, request, provider_id=None):
    """Read either a standard scalar or a timestamped upstream Sandbox CIN."""
    sensor = unique_sensor(raw, provider_id or request["sensor_id"])
    data = sensor["data"]
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            pass
    if isinstance(data, list):
        # STF_685 serializes the provider resource's attributes as Go rows.
        contents = [c.get("CharacteristicValue") for c in data if isinstance(c, dict)
                    and c.get("CharacteristicName") in ("con", "sample")]
        if len(contents) != 1:
            raise EvidenceError("missing_provider_sample")
        try:
            data = json.loads(contents[0])
        except (ValueError, TypeError) as exc:
            raise EvidenceError("invalid_provider_sample") from exc
        if not isinstance(data, dict) or data.get("source") != "independent_position_sensor":
            raise EvidenceError("unverified_source")
        if any(data.get(key) != request[key] for key in ("asset_id", "facility_id", "zone_id", "sensor_id")):
            raise EvidenceError("source_scope_mismatch")
    record = data if isinstance(data, dict) else {"value": data}
    if "source" in record and record["source"] != "independent_position_sensor":
        raise EvidenceError("unverified_source")
    for key in ("facility_id", "zone_id", "asset_id", "sensor_id"):
        if key in record and record[key] != request[key]:
            raise EvidenceError("source_scope_mismatch")
    unit = sensor.get("dataUnitOfMeasure") or record.get("unit")
    if unit != "%" or record.get("unit", unit) != unit:
        raise EvidenceError("unexpected_measurement_unit")
    measured = record.get("observed_at")
    stamp = sensor.get("dataTimestamp")
    if stamp is not None:
        try:
            seconds, nanos = stamp["seconds"], stamp["nanoSeconds"]
            if type(seconds) is not int or type(nanos) is not int or not 0 <= nanos < 1_000_000_000:
                raise ValueError
            instant = datetime.fromtimestamp(seconds, timezone.utc).replace(microsecond=nanos // 1000)
        except (KeyError, TypeError, ValueError, OverflowError, OSError) as exc:
            raise EvidenceError("invalid_measurement_time") from exc
        if measured and timestamp(measured) != instant:
            raise EvidenceError("conflicting_measurement_time")
        measured = instant.isoformat()
    return {"sensor_id": request["sensor_id"], "value": percentage(record["value"]),
            "unit": unit, "observed_at": timestamp(measured).isoformat(),
            "source": "independent_position_sensor"}


def authority(url):
    parsed = urlsplit(url)
    if (parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise EvidenceError("invalid_service_endpoint")
    return (parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == "https" else 80))


class SensorService:
    def __init__(self, config, token=None):
        self.config = config
        self.registry = config["registry_url"]
        self.allowed = {authority(url) for url in [self.registry, *config.get("allowed_service_origins", [])]}
        if token and any(scheme != "https" for scheme, _, _ in self.allowed):
            raise ValueError("MEC bearer tokens require HTTPS service endpoints")
        self.callback = config.get("sensor_test_callback")
        if self.callback:
            authority(self.callback)
            if urlsplit(self.callback).path != "/mec046/test":
                raise ValueError("The installed bridge must receive test callbacks at /mec046/test")
        self.callback_lock = threading.Condition()
        self.pending_collection = None
        self.test_callbacks = {}
        self.client = httpx.Client(follow_redirects=False, trust_env=False, timeout=5,
                                   headers={"Authorization": "Bearer " + token} if token else None,
                                   verify=config.get("mec_ca") or True)

    def service(self, category, name=None):
        response = self.client.get(self.registry)
        response.raise_for_status()
        services = response.json()
        if not isinstance(services, list):
            raise EvidenceError("invalid_registry_result")
        matches = [s for s in services if isinstance(s, dict) and s.get("state") == "ACTIVE" and
                   (s.get("serCategory") or {}).get("id") == category and (not name or s.get("serName") == name)]
        if len(matches) != 1 or not matches[0].get("serInstanceId"):
            raise EvidenceError("service_missing_or_ambiguous")
        service = matches[0]
        uris = service["transportInfo"]["endpoint"]["uris"]
        bases = [url.rstrip("/") for url in uris if authority(url) in self.allowed]
        if not bases:
            raise EvidenceError("unapproved_service_endpoint")
        return bases[0], {"service_id": service["serInstanceId"], "service_name": service.get("serName"),
                          "registry_status": response.status_code}

    def registration(self, *, commission=False):
        binding = self.config["provider_registration"]
        expected = binding["record"]
        base, receipt = self.service("iotId")
        collection = base + "/registered_iot_platforms"
        path = collection + "/" + quote(expected["iotPlatformId"], safe="")
        found = self.client.get(path)
        receipt.update(platform_id=expected["iotPlatformId"], before_status=found.status_code)
        status = "already_enabled"
        if found.status_code == 404:
            if not commission:
                raise EvidenceError("provider_unregistered")
            write = self.client.post(collection, json=expected)
            write.raise_for_status()
            receipt.update(before_enabled=None, operation="POST", write_status=write.status_code)
            status = "enabled"
        else:
            found.raise_for_status()
            current = found.json()
            self.check_registration(current, expected)
            receipt["before_enabled"] = current["enabled"]
            if current["enabled"] is False:
                if not commission:
                    raise EvidenceError("provider_disabled")
                write = self.client.put(path, json={**current, "enabled": True})
                write.raise_for_status()
                receipt.update(operation="PUT", write_status=write.status_code)
                status = "enabled"
        verified = self.client.get(path) if commission else found
        verified.raise_for_status()
        current = verified.json()
        self.check_registration(current, expected)
        if current["enabled"] is not True:
            raise EvidenceError("provider_enable_unconfirmed")
        receipt.update(readback_status=verified.status_code, enabled=True,
                       readback_sha256=hashlib.sha256(verified.content).hexdigest())
        return status, receipt

    @staticmethod
    def check_registration(actual, expected):
        if actual.get("iotPlatformId") != expected["iotPlatformId"] or type(actual.get("enabled")) is not bool:
            raise EvidenceError("provider_identity_mismatch")
        for group in ("userTransportInfo", "customServicesTransportInfo"):
            transports = actual.get(group) or []
            if len(transports) != len(expected[group]):
                raise EvidenceError("provider_transport_mismatch")
            for wanted in expected[group]:
                matches = [t for t in transports if all(t.get(k) == wanted[k] for k in
                           ("id", "name", "protocol", "type", "version"))]
                if len(matches) != 1 or matches[0]["endpoint"].get("addresses") != wanted["endpoint"]["addresses"]:
                    raise EvidenceError("provider_transport_mismatch")

    @staticmethod
    def subscription_id(href, collection):
        prefix = collection + "/"
        suffix = href.removeprefix(prefix) if isinstance(href, str) else ""
        if not isinstance(href, str) or not href.startswith(prefix) or not suffix.isascii() or not suffix.isdecimal() or len(suffix) > 12:
            raise EvidenceError("invalid_sensor_subscription_link")
        return suffix

    def observe_test(self, message):
        """Accept a correlated delivery acknowledgement. Sensor readings come from the 046 query."""
        if not isinstance(message, dict) or message.get("notificationType") != "TestNotification":
            return False
        try:
            href = message["_links"]["subscription"]["href"]
            with self.callback_lock:
                if not self.pending_collection:
                    return False
                self.subscription_id(href, self.pending_collection)
                if len(self.test_callbacks) >= 8:
                    return False
                self.test_callbacks[href] = datetime.now(timezone.utc).isoformat()
                self.callback_lock.notify_all()
        except (KeyError, TypeError, EvidenceError):
            return False
        return True

    def installed_subscription(self, base):
        collection = base + "/subscriptions/sensor_data"
        response = self.client.get(collection)
        response.raise_for_status()
        links = response.json()["_links"].get("subscriptions") or []
        if not isinstance(links, list) or len(links) > 64:
            raise EvidenceError("unexpected_sensor_subscription_list")
        owned = []
        for item in links:
            sid = self.subscription_id(item["href"], collection)
            # The pinned Sandbox advertises /subscriptions in Location and
            # routes the individual GET/DELETE under /queries.
            res = self.client.get(base + "/queries/sensor_data/" + sid)
            if res.status_code == 404:
                continue
            res.raise_for_status()
            row = res.json()
            if row.get("callbackReference") == self.callback:
                if row.get("subscriptionType") != "SensorDataSubscription" or row["_links"]["self"]["href"] != item["href"]:
                    raise EvidenceError("sensor_subscription_mismatch")
                owned.append((sid, res))
        if len(owned) > 1:
            raise EvidenceError("duplicate_sensor_subscriptions")
        return owned[0] if owned else (None, None)

    def data_subscription(self, *, commission=False, remove=False):
        if not self.callback:
            raise EvidenceError("sensor_subscription_not_configured")
        base, receipt = self.service("sssId", self.config.get("service_name"))
        collection = base + "/subscriptions/sensor_data"
        sid, confirmed = self.installed_subscription(base)
        receipt["before_present"] = sid is not None
        if remove:
            if sid:
                deleted = self.client.delete(base + "/queries/sensor_data/" + sid)
                deleted.raise_for_status()
                if self.installed_subscription(base)[0] is not None:
                    raise EvidenceError("sensor_subscription_removal_unconfirmed")
                receipt.update(operation="DELETE", write_status=deleted.status_code, subscription_id=sid)
            return receipt
        if not sid:
            if not commission:
                raise EvidenceError("sensor_subscription_missing")
            spec = {"subscriptionType":"SensorDataSubscription", "callbackReference":self.callback,
                    "requestTestNotification":True}
            # STF_685 uses the required request wrapper for POST validation
            # and reads the same fields at the root when persisting the object.
            with self.callback_lock:
                self.pending_collection = collection
                self.test_callbacks.clear()
            try:
                created = self.client.post(collection, json={"SensorDataSubscription":spec, **spec})
                created.raise_for_status()
                href = created.headers.get("Location")
                sid = self.subscription_id(href, collection)
                if created.status_code != 201:
                    raise EvidenceError("sensor_subscription_creation_unconfirmed")
                with self.callback_lock:
                    self.callback_lock.wait_for(lambda: href in self.test_callbacks, timeout=2)
                    observed_at = self.test_callbacks.get(href)
            finally:
                with self.callback_lock:
                    self.pending_collection = None
                    self.test_callbacks.clear()
            confirmed_id, confirmed = self.installed_subscription(base)
            if confirmed_id != sid:
                raise EvidenceError("sensor_subscription_readback_mismatch")
            if not observed_at:
                # Remove only the new and independently read-back owned slot.
                self.client.delete(base + "/queries/sensor_data/" + sid).raise_for_status()
                raise EvidenceError("sensor_test_callback_unconfirmed")
            receipt.update(operation="POST", write_status=created.status_code,
                           test_callback={"type":"TestNotification","observed_at":observed_at,"status":204})
        receipt.update(subscription_id=sid, subscription_type="SensorDataSubscription",
                       readback_status=confirmed.status_code, readback_sha256=hashlib.sha256(confirmed.content).hexdigest())
        return receipt

    def read(self, req):
        registration = self.registration()[1] if self.config.get("provider_registration") else None
        subscription = self.data_subscription() if self.callback else None
        base, receipt = self.service("sssId", self.config.get("service_name"))
        provider_id = self.config.get("provider_sensor_ids", {}).get(req["sensor_id"], req["sensor_id"])
        discovery = self.client.get(base + "/queries/sensor_discovery", params={
            "type": self.config.get("sensor_type", "FLX"), "sensorPropertyList": "saref:any"})
        discovery.raise_for_status()
        unique_sensor(discovery.json(), provider_id)
        result = self.client.get(base + "/queries/sensor_data", params={"sensorIdentifier": provider_id})
        result.raise_for_status()
        sample = provider_sample(result.json(), req, provider_id)
        receipt = {**receipt, "discovery_status": discovery.status_code,
                   "lookup_status": result.status_code, "lookup_path": "/queries/sensor_data",
                   "provider_sensor_id": provider_id,
                   "lookup_sha256": hashlib.sha256(result.content).hexdigest()}
        if registration:
            receipt["provider_registration"] = registration
        if subscription:
            receipt["sensor_subscription"] = subscription
        return sample, receipt
