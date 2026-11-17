import asyncio
import json

import httpx
from mcp import Client

from opensoom.mcp_server import ServiceProxy, create_server, redact


def test_mcp_tools_use_fixed_identity_and_preserve_denials():
    observed = []

    def handler(request):
        observed.append((request.headers.get("authorization"), request.headers.get("x-opensoom-run-id"), json.loads(request.content)))
        if request.url.path.endswith("apply_setup"):
            return httpx.Response(403, json={"detail": {"code": "admin_required", "message": "Administrator profile required"}})
        return httpx.Response(200, json={"facilities": [{"id": "food-a"}], "cse_discovery": [{"rsc": 2000, "rqi": "test-rqi"}]})

    server = create_server(ServiceProxy(token="operator-example", run_id="run-example", transport=httpx.MockTransport(handler)))

    async def check():
        async with Client(server) as client:
            tools = await client.list_tools()
            assert {t.name for t in tools.tools} == {"doctor", "prepare_setup", "apply_setup", "discover", "read_group", "read_evidence", "request_action", "verify_result"}
            result = await client.call_tool("discover", {"facility_id": "food-a"})
            assert not result.is_error
            assert result.structured_content["facilities"][0]["id"] == "food-a"
            denied = await client.call_tool("apply_setup", {"profile_id": "food-production"})
            assert denied.is_error
            assert "admin_required" in denied.content[0].text
            malformed = await client.call_tool("request_action", {"facility_id": "food-a", "action": "grant_admin"})
            assert malformed.is_error
    asyncio.run(check())
    assert len(observed) == 2
    assert all(auth == "Bearer operator-example" and run == "run-example" for auth, run, _ in observed)
    assert all("role" not in body["arguments"] for _, _, body in observed)


def test_no_credential_in_diagnostics_or_echo():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"operator_token": "credential", "message": "echo credential", "input_tokens": 12}))
    result = ServiceProxy(token="credential", transport=transport).call("doctor", {})
    assert "credential" not in json.dumps(result)
    assert result["input_tokens"] == 12
    assert redact({"password": "hidden"}) == {"password": "[redacted]"}


def test_remote_cleartext_connection_is_rejected():
    try:
        ServiceProxy(base_url="http://example.com", token="do-not-send")
    except ValueError:
        pass
    else:
        raise AssertionError("Remote cleartext service should not receive a credential")


def test_host_contexts_are_service_owned_facility_scoped_and_reused():
    observed = []
    def handler(request):
        body = json.loads(request.content)
        observed.append((request.url.path, request.headers.get("x-opensoom-run-id"), body,
                         request.headers.get("authorization")))
        if request.url.path == "/api/agent-runs":
            return httpx.Response(200, json={"run_id": body["id"]})
        return httpx.Response(200, json={"status": "nominal"})
    proxy = ServiceProxy(token="scoped-observer", transport=httpx.MockTransport(handler))
    first = proxy.call("read_evidence", {"facility_id": "food-a"})
    again = proxy.call("read_group", {"facility_id": "food-a"})
    other = proxy.call("read_evidence", {"facility_id": "learning-b"})
    assert first["run_id"] == again["run_id"] != other["run_id"]
    assert len([r for r in observed if r[0] == "/api/agent-runs"]) == 2
    assert all(r[3] == "Bearer scoped-observer" for r in observed)
    tool_calls = [r for r in observed if r[0].startswith("/api/tools/")]
    assert [r[1] for r in tool_calls] == [first["run_id"], first["run_id"], other["run_id"]]
