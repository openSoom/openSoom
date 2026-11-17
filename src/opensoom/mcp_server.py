"""The shared operator tool boundary used by Codex and the API runner."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import threading
from typing import Any, Literal
from urllib.parse import urlparse
import uuid

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError


def project_dir() -> Path:
    return Path(os.environ.get("OPENSOOM_PROJECT_DIR", Path.cwd())).expanduser().resolve()


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if any(part in key.lower() for part in ("token", "password", "api_key", "authorization", "secret"))
                  and key.lower() not in {"tokens", "input_tokens", "output_tokens", "total_tokens", "tokens_charged", "tokens_remaining", "tokens_reserved", "max_tokens"}
                  else redact(item, secrets))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[redacted]")
    return value


class ServiceError(RuntimeError):
    def __init__(self, result: dict):
        self.result = result
        super().__init__(json.dumps(result, ensure_ascii=False))


class ServiceProxy:
    """A fixed service identity; tool arguments never choose role or credentials."""

    def __init__(self, base_url: str | None = None, token: str | None = None,
                 run_id: str | None = None, transport: httpx.BaseTransport | None = None):
        self.base_url = (base_url or os.environ.get("OPENSOOM_SERVICE_URL", "http://127.0.0.1:8090")).rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use an HTTP(S) service URL without embedded credentials, query parameters or fragments")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Plain HTTP is allowed only for the local service; remote service requires HTTPS")
        self.token = token if token is not None else self._operator_token()
        self.run_id = run_id or os.environ.get("OPENSOOM_RUN_ID") or None
        self.transport = transport
        self.host_runs: dict[str, str] = {}
        self._runs_lock = threading.Lock()

    @staticmethod
    def _operator_token() -> str:
        value = os.environ.get("OPENSOOM_SERVICE_TOKEN")
        if value:
            return value
        path = project_dir() / ".runtime/service-credentials.json"
        try:
            return str(json.loads(path.read_text()).get("operator_token", ""))
        except (FileNotFoundError, ValueError, OSError):
            return ""

    def request(self, method: str, path: str, payload: dict | None = None, *, require_auth: bool = True,
                run_id: str | None = None) -> dict[str, Any]:
        if require_auth and not self.token:
            raise ServiceError({"code": "SETUP_REQUIRED", "message": "Start openSoom locally to create the operator connection; do not paste credentials into chat."})
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        effective_run = run_id or self.run_id
        if effective_run:
            headers["X-OpenSoom-Run-ID"] = effective_run
        try:
            with httpx.Client(base_url=self.base_url, timeout=20, transport=self.transport, trust_env=False) as client:
                response = client.request(method, path, json=payload, headers=headers)
                try:
                    data = response.json()
                except ValueError:
                    data = {"code": "INVALID_SERVICE_RESPONSE", "message": "The service did not return JSON."}
        except httpx.HTTPError as exc:
            raise ServiceError({"code": "SERVICE_UNAVAILABLE", "message": "The openSoom service is unreachable; run its startup command and doctor.", "error_type": type(exc).__name__}) from None
        data = redact(data, (self.token,))
        if response.status_code >= 400:
            detail = data.get("detail", data) if isinstance(data, dict) else data
            if not isinstance(detail, dict):
                detail = {"message": str(detail)}
            raise ServiceError({"code": detail.get("code", "SERVICE_REJECTED"), "http_status": response.status_code, **detail})
        return data if isinstance(data, dict) else {"result": data}

    def call(self, name: str, arguments: dict) -> dict[str, Any]:
        run_id = self.run_id
        facility = arguments.get("facility_id")
        if run_id is None and facility:
            # A host connection gets a separate service-owned context per
            # facility. No credential or authority is changed. Serialize only
            # context creation; tool calls retain their own explicit header.
            with self._runs_lock:
                if facility not in self.host_runs:
                    candidate = "mcp-" + uuid.uuid4().hex[:12]
                    created = self.request("POST", "/api/agent-runs", {
                        "id": candidate, "mode": "mcp_host", "facility_id": facility,
                        "model": None,
                    })
                    actual = created.get("run_id", created.get("id"))
                    if actual != candidate:
                        raise ServiceError({"code": "RUN_CORRELATION_FAILED", "message": "Service did not preserve the host run identity"})
                    self.host_runs[facility] = candidate
                run_id = self.host_runs[facility]
        try:
            result = self.request("POST", "/api/tools/" + name, {"arguments": arguments}, run_id=run_id)
        except ServiceError as exc:
            if run_id:
                exc.result["run_id"] = run_id
            raise ServiceError(exc.result) from None
        if run_id:
            result.setdefault("run_id", run_id)
        return result


def create_server(proxy: ServiceProxy | None = None) -> MCPServer:
    service = proxy or ServiceProxy()
    server = MCPServer(
        "openSoom", version="0.1.0",
        instructions=("Manage only accessible facilities. Read current evidence before action; commands and ACKs do not prove recovery. "
                      "Use verify_result and report unresolved/denied outcomes honestly. Physical equipment and observations in the demo are simulated. "
                      "Tools cannot grant permissions or activate profiles without the configured administrator identity."),
    )

    def call(name: str, args: dict) -> dict[str, Any]:
        try:
            return service.call(name, {k: v for k, v in args.items() if v is not None})
        except ServiceError as exc:
            raise ToolError(str(exc)) from None

    @server.tool(structured_output=True)
    def doctor() -> dict[str, Any]:
        """Check service/CSE readiness and actionable setup diagnostics without exposing credentials."""
        if not service.token:
            try:
                health = service.request("GET", "/api/health", require_auth=False)
            except ServiceError as exc:
                return {"ready": False, "connection": exc.result, "next_action": "Start the local openSoom service using the repository instructions."}
            return {"ready": False, "health": health, "next_action": "Complete local startup to create the scoped operator credential."}
        return call("doctor", {})

    @server.tool(structured_output=True)
    def prepare_setup(profile_id: str) -> dict[str, Any]:
        """Validate an existing facility profile and explain the setup plan without activating it."""
        return call("prepare_setup", {"profile_id": profile_id})

    @server.tool(structured_output=True)
    def apply_setup(profile_id: str) -> dict[str, Any]:
        """Apply a validated profile only if this server's fixed identity is already an administrator; never self-grant."""
        return call("apply_setup", {"profile_id": profile_id})

    @server.tool(structured_output=True)
    def discover(facility_id: str | None = None) -> dict[str, Any]:
        """Find accessible facilities and equipment using real oneM2M discovery."""
        return call("discover", {"facility_id": facility_id})

    @server.tool(structured_output=True)
    def read_group(facility_id: str) -> dict[str, Any]:
        """Query the facility's native oneM2M group and retain each member's result; group success is not device ACK."""
        return call("read_group", {"facility_id": facility_id})

    @server.tool(structured_output=True)
    def read_evidence(facility_id: str, zone_id: str | None = None) -> dict[str, Any]:
        """Read current observations, freshness, incidents and commands before deciding on an action."""
        return call("read_evidence", {"facility_id": facility_id, "zone_id": zone_id})

    @server.tool(structured_output=True)
    def request_action(facility_id: str, zone_id: str, action: Literal["set_damper", "request_maintenance"],
                       reason: str, request_id: str, value: float | None = None) -> dict[str, Any]:
        """Request a profile-authorized action. Reuse request_id when retrying the same intended action. Server validates freshness and scope."""
        return call("request_action", {"facility_id": facility_id, "zone_id": zone_id, "action": action,
                                       "reason": reason, "request_id": request_id, "value": value})

    @server.tool(structured_output=True)
    def verify_result(facility_id: str, command_id: str) -> dict[str, Any]:
        """Independently check command state, device ACK and later observations; report pending/failed/unresolved outcomes as returned."""
        return call("verify_result", {"facility_id": facility_id, "command_id": command_id})

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="openSoom shared MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8091)
    args = parser.parse_args()
    server = create_server()
    if args.transport == "stdio":
        server.run()
    else:
        server.run(transport="streamable-http", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
