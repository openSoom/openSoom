"""Small, traceable client for the actual oneM2M HTTP binding.

Application identity is supplied by a trusted service, never by arbitrary model
arguments. ACP enforcement is distinct from transport authentication. The local
development CSE trusts loopback callers; see deploy/README.md for that boundary.
"""
from __future__ import annotations

import json
import ssl
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx


class CSEError(RuntimeError):
    """A transport or oneM2M failure, with a serializable redacted result."""

    def __init__(self, message: str, result: dict[str, Any]):
        super().__init__(message)
        self.result = result
        self.rsc = result.get("rsc", 0)


_TRACE_LOCK = threading.Lock()
_SECRET_KEYS = {"authorization", "password", "passwd", "secret", "token", "api_key", "apikey", "access_token", "refresh_token"}


def _redacted(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if str(k).lower() in _SECRET_KEYS else _redacted(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redacted(v) for v in value]
    return value


class CSEClient:
    """No implicit retries: command idempotency is owned by the service."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080", origin: str = "CAdmin", ca_file: str | Path | None = None, trace_path: str | Path | None = None, timeout: float = 10.0, bearer_token: str | None = None):
        parsed = urlsplit(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("CSE base_url must be an http(s) URL without embedded credentials")
        self.base_url = base_url.rstrip("/")
        self.origin = origin
        self.trace_path = Path(trace_path) if trace_path else None
        verify: bool | ssl.SSLContext = ssl.create_default_context(cafile=str(ca_file)) if ca_file else True
        self._http = httpx.Client(timeout=timeout, verify=verify, trust_env=False, follow_redirects=False)
        self._bearer_token = bearer_token

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "CSEClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _request(self, method: str, path: str, resource: dict[str, Any] | None = None, *, ty: int | None = None, origin: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        # Prevent a resource path from redirecting credentials to another host.
        if "://" in path or "?" in path or "#" in path or ".." in path.split("/"):
            raise ValueError("Use a CSE resource path and separate query parameters")
        rqi = f"opensoom-{uuid.uuid4().hex}"
        headers = {"X-M2M-Origin": origin or self.origin, "X-M2M-RI": rqi, "X-M2M-RVI": "4", "Accept": "application/json"}
        if resource is not None:
            headers["Content-Type"] = "application/json" + (f";ty={ty}" if ty is not None else "")
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), "method": method, "path": path, "origin": headers["X-M2M-Origin"], "rqi": rqi, "request": _redacted(resource), "query": _redacted(params or {})}
        try:
            response = self._http.request(method, self.base_url + "/" + path.lstrip("/"), json=resource if resource is not None else None, headers=headers, params=params)
            try:
                body = response.json() if response.content else {}
            except ValueError:
                body = {"error": "CSE returned non-JSON content"}
            raw_rsc = response.headers.get("X-M2M-RSC", "0")
            rsc = int(raw_rsc) if raw_rsc.isdigit() else 0
            result = {"rsc": rsc, "rqi": response.headers.get("X-M2M-RI"), "body": _redacted(body), "http_status": response.status_code}
        except httpx.HTTPError as exc:
            result = {"rsc": 0, "rqi": rqi, "body": {"error": type(exc).__name__}, "http_status": 0}
            self._record({**event, "response": result})
            raise CSEError(f"CSE transport failed: {type(exc).__name__}", result) from exc
        self._record({**event, "response": result})
        if not (2000 <= result["rsc"] < 3000 and 200 <= result["http_status"] < 300):
            raise CSEError(f"CSE request failed: rsc={result['rsc']} http={result['http_status']}", result)
        if result["rqi"] != rqi:
            raise CSEError("CSE response request identifier did not match", result)
        return result

    def _record(self, event: dict[str, Any]) -> None:
        if self.trace_path:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            with _TRACE_LOCK, self.trace_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

    def create(self, parent: str, ty: int, resource: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
        return self._request("POST", parent, resource, ty=ty, origin=origin)

    def retrieve(self, path: str, origin: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", path, origin=origin, params=params)

    def update(self, path: str, resource: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
        return self._request("PUT", path, resource, origin=origin)

    def delete(self, path: str, origin: str | None = None) -> dict[str, Any]:
        return self._request("DELETE", path, origin=origin)

    def discover(self, path: str, filters: dict[str, Any] | None = None, origin: str | None = None) -> dict[str, Any]:
        return self.retrieve(path, origin=origin, params={"fu": 1, "drt": 2, **(filters or {})})

    def group_read(self, path: str, origin: str | None = None) -> dict[str, Any]:
        return self.retrieve(path.rstrip("/") + "/fopt", origin=origin)


class MQTTCSEClient(CSEClient):
    """Native oneM2M request primitives over MQTT/TLS, not an HTTP bridge.

    A local lab broker provides server-authenticated TLS. Production deployments
    must additionally bind broker credentials/topic ACLs to AE identities.
    """

    def __init__(self, host: str, cse_id: str, origin: str, ca_file: str | Path, port: int = 8883, trace_path: str | Path | None = None, timeout: float = 10.0):
        from paho.mqtt import client as mqtt
        self.origin = origin
        self.cse_id = cse_id
        self.timeout = timeout
        self.trace_path = Path(trace_path) if trace_path else None
        self._responses: dict[str, dict[str, Any]] = {}
        self._active_rqi: str | None = None
        self._condition = threading.Condition()
        self._request_lock = threading.Lock()
        self._subscribed = threading.Event()
        self._topic_origin = "opensoom-" + uuid.uuid4().hex
        receiver = cse_id.lstrip("/").replace("/", ":")
        self.request_topic = f"/oneM2M/req/{self._topic_origin}/{receiver}/json"
        self.response_topic = f"/oneM2M/resp/{self._topic_origin}/{receiver}/json"
        self._mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self._topic_origin)
        self._mqtt.tls_set_context(ssl.create_default_context(cafile=str(ca_file)))
        def on_connect(client, userdata, flags, reason_code, properties):
            if reason_code == 0:
                client.subscribe(self.response_topic, qos=1)
        def on_subscribe(client, userdata, mid, reason_codes, properties):
            if all(int(code.value) < 128 for code in reason_codes):
                self._subscribed.set()
        def on_message(client, userdata, message):
            try:
                payload = json.loads(message.payload)
                if not isinstance(payload, dict):
                    return
                payload = payload.get("m2m:rsp", payload)
                if not isinstance(payload, dict):
                    return
                with self._condition:
                    # Ignore unrelated/late responses, keeping memory bounded.
                    if payload["rqi"] == self._active_rqi:
                        self._responses[payload["rqi"]] = payload
                        self._condition.notify_all()
            except (ValueError, KeyError, TypeError):
                return
        self._mqtt.on_connect = on_connect
        self._mqtt.on_subscribe = on_subscribe
        self._mqtt.on_message = on_message
        try:
            self._mqtt.connect(host, port, keepalive=30)
        except OSError as exc:
            raise CSEError(f"MQTT/TLS connection failed: {type(exc).__name__}", {"rsc": 0, "rqi": None, "body": {"error": type(exc).__name__}, "http_status": None}) from exc
        self._mqtt.loop_start()
        if not self._subscribed.wait(timeout):
            self.close()
            raise CSEError("MQTT/TLS connection or subscription timed out", {"rsc": 0, "rqi": None, "body": {}, "http_status": None})

    def close(self) -> None:
        self._mqtt.disconnect()
        self._mqtt.loop_stop()

    def _request(self, method: str, path: str, resource: dict[str, Any] | None = None, *, ty: int | None = None, origin: str | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if "://" in path or "?" in path or "#" in path or ".." in path.split("/"):
            raise ValueError("Use a CSE resource path and separate query parameters")
        rqi = "opensoom-" + uuid.uuid4().hex
        primitive: dict[str, Any] = {"op": {"POST": 1, "GET": 2, "PUT": 3, "DELETE": 4}[method], "to": path, "fr": origin or self.origin, "rqi": rqi, "rvi": "4"}
        if ty is not None:
            primitive["ty"] = ty
        if resource is not None:
            primitive["pc"] = resource
        if params:
            primitive["fc"] = {key: val for key, val in params.items() if key not in ("rcn", "drt")}
            primitive.update({key: params[key] for key in ("rcn", "drt") if key in params})
        with self._request_lock:
            with self._condition:
                self._active_rqi = rqi
                self._responses.clear()
            try:
                self._mqtt.publish(self.request_topic, json.dumps(primitive), qos=1).wait_for_publish(timeout=self.timeout)
                deadline = time.monotonic() + self.timeout
                with self._condition:
                    while rqi not in self._responses and time.monotonic() < deadline:
                        self._condition.wait(max(0, deadline - time.monotonic()))
                    response = self._responses.pop(rqi, None)
            except (OSError, RuntimeError) as exc:
                result = {"rsc": 0, "rqi": rqi, "body": {"error": type(exc).__name__}, "http_status": None, "transport": "MQTT_TLS"}
                self._record({"timestamp": datetime.now(timezone.utc).isoformat(), "topic": self.request_topic, "request": _redacted(primitive), "response": result})
                raise CSEError(f"MQTT transport failed: {type(exc).__name__}", result) from exc
            finally:
                with self._condition:
                    self._active_rqi = None
                    self._responses.pop(rqi, None)
        result = {"rsc": response.get("rsc", 0) if response else 0, "rqi": rqi, "body": _redacted(response.get("pc", {})) if response else {"error": "MQTT response timeout"}, "http_status": None, "transport": "MQTT_TLS"}
        self._record({"timestamp": datetime.now(timezone.utc).isoformat(), "topic": self.request_topic, "request": _redacted(primitive), "response": result})
        if not 2000 <= result["rsc"] < 3000:
            raise CSEError(f"MQTT CSE request failed: rsc={result['rsc']}", result)
        return result
