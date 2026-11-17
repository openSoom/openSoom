#!/usr/bin/env python3
"""Fresh Codex model -> installed setup skill -> MCP rehearsal, budget bounded.

Default is a zero-provider-call dry capture. --live forwards only to the fixed
OpenAI Responses endpoint after atomic reservation in the existing shared batch.
The ordinary Codex profile and all host security policies remain untouched.
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agent_install_plugin import prepare
from opensoom.llm_budget import SharedBudget, conservative_token_reservation
from opensoom.mcp_server import ServiceProxy
import httpx

ALLOWED_TOOLS = {"doctor", "prepare_setup", "discover", "read_group", "read_evidence"}
MODEL = "gpt-5-mini"
BASE_INSTRUCTIONS = """You are Codex helping a nontechnical facility manager through the installed openSoom plugin. Follow the attached skill and the user's request. Choose the necessary available tools yourself. Use only read-only facility tools, never change roles, permissions, profiles, equipment, files, or credentials. Do not request or reveal secrets. Report facts from actual tools, distinguish simulated physical equipment from real software execution, and be concise in Korean. Never invent or give illustrative measurements. If a required check is unavailable, state that limitation honestly. No shell or web actions are needed for this prestarted-runtime rehearsal. At most four model responses remain; combine independent read-only checks when useful and leave room for a brief final explanation."""
PROMPT = """openSoom을 처음 쓰는 시설 관리자입니다. 이미 관리자가 실행하고 가상 프로필을 활성화한 서비스에 이 새 Codex를 연결해 설정 상태를 확인하고, learning-b 시설의 현재 공기 상태를 진단해 한국어로 설명해주세요. 장비 제어와 관리자 설정 변경은 하지 마세요. 실제로 확인한 사실, 남아 있는 문제, 제가 다음에 할 일을 알려주세요."""


def safe(value, secret_values=()):
    secret_names = {"authorization", "password", "secret", "api_key", "apikey", "access_token", "refresh_token", "operator_token", "admin_token", "maintenance_token", "observer_token"}
    def clean(item):
        if isinstance(item, dict):
            return {key: "[REDACTED]" if key.lower() in secret_names else clean(val) for key, val in item.items()}
        if isinstance(item, list):
            return [clean(val) for val in item]
        return item
    text = json.dumps(clean(value), ensure_ascii=False)
    for value in secret_values:
        if value:
            text = text.replace(value, "[REDACTED]")
    return json.loads(text.replace(str(ROOT), "<checkout>").replace(str(Path.home()), "<user-home>"))


def name_allowed(name):
    return "opensoom" in name.lower() and any(name.endswith("__" + allowed) or name.endswith("_" + allowed) for allowed in ALLOWED_TOOLS)


def rehearsal_scope_snapshot():
    """The fixed six-request allowance includes every earlier guided attempt."""
    with sqlite3.connect(ROOT / ".runtime/llm-budget.sqlite") as conn:
        calls, charged = conn.execute("SELECT COUNT(*), COALESCE(SUM(charged_tokens),0) FROM reservations WHERE run_id LIKE 'guided-%'").fetchone()
    return {"max_requests": 6, "max_tokens": 50000, "requests_consumed": calls, "tokens_charged": charged, "requests_remaining": max(0, 6 - calls), "tokens_remaining": max(0, 50000 - charged)}


class BoundedProxy:
    def __init__(self, folder, live, protocol_fixture=False):
        self.folder, self.live, self.protocol_fixture = folder, live, protocol_fixture
        self.key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENSOOM_LLM_API_KEY", "")
        self.local_token = secrets.token_urlsafe(32)
        self.secrets = [self.key, self.local_token, *json.loads((ROOT / ".runtime/service-credentials.json").read_text()).values()]
        self.budget = SharedBudget(ROOT / ".runtime/llm-budget.sqlite")
        self.before = self.budget.snapshot()
        self.scope_before = rehearsal_scope_snapshot()
        self.run_id = folder.name
        self.calls, self.charged = 0, 0
        self.records = []
        self.lock = threading.Lock()
        self.deadline = time.monotonic() + 240
        self.limits = {"max_provider_requests": 6, "max_run_charged_tokens": 50000, "max_output_tokens": 1024, "provider_timeout_seconds": 45, "turn_timeout_seconds": 180, "request_max_retries": 0}
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def error(self, code, message):
                content = json.dumps({"error": {"type": "bounded_rehearsal", "code": message, "message": message}}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def do_GET(self):
                self.error(404, "only_responses_post_is_supported")

            def do_POST(self):
                if self.path != "/v1/responses" or not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + owner.local_token):
                    return self.error(403, "proxy_scope_denied")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 100000 or self.headers.get("Content-Encoding"):
                    return self.error(413, "unsupported_request_size_or_encoding")
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw)
                    assert isinstance(payload, dict) and payload.get("model") == MODEL and isinstance(payload.get("input"), list)
                    assert not any(secret.encode() in raw for secret in owner.secrets if secret)
                    # Keep only the installed plugin's read-only functions. This
                    # bounds capability, without choosing their order or arguments.
                    tools = []
                    for tool in payload.get("tools", []):
                        if tool.get("type") == "function" and name_allowed(tool.get("name", "")):
                            tools.append(tool)
                        elif tool.get("type") == "namespace" and "opensoom" in tool.get("name", "").lower():
                            children = [child for child in tool.get("tools", []) if child.get("type") == "function" and child.get("name") in ALLOWED_TOOLS]
                            if children:
                                tools.append({**tool, "tools": children})
                    assert tools, "No installed openSoom read-only tools were offered"
                    payload["tools"] = tools
                    payload["max_output_tokens"] = owner.limits["max_output_tokens"]
                    payload["store"] = False
                    payload["stream"] = True
                    payload["reasoning"] = {"effort": "minimal"}
                    # Codex-specific transport metadata is not part of the
                    # public Responses API's operational input or tool schemas.
                    omitted_client_metadata = "client_metadata" in payload
                    payload.pop("client_metadata", None)
                    allowed_keys = {"model", "input", "instructions", "tools", "tool_choice", "parallel_tool_calls", "reasoning", "text", "stream", "include", "store", "metadata", "max_output_tokens", "prompt_cache_key", "service_tier", "truncation"}
                    assert not set(payload) - allowed_keys, "Unsupported Responses fields: " + ",".join(sorted(set(payload) - allowed_keys))
                    bound = conservative_token_reservation(payload, owner.limits["max_output_tokens"])
                    record = {"model": MODEL, "payload_bytes": len(json.dumps(payload, ensure_ascii=False).encode()), "conservative_reserved_tokens": bound, "tool_names": [tool.get("name") for tool in tools], "payload_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(), "omitted_codex_transport_metadata": omitted_client_metadata, "forwarded": False}
                    owner.records.append(record)
                    if owner.protocol_fixture:
                        # Explicit zero-inference transport fixture: replay only
                        # the already observed doctor choice to inspect the host
                        # approval protocol. This is never live-model evidence.
                        call = {"type": "function_call", "id": "fc_protocol_fixture", "call_id": "call_protocol_fixture", "namespace": "mcp__opensoom", "name": "doctor", "arguments": "{}", "status": "completed"}
                        message = {"type": "message", "id": "msg_protocol_fixture", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": "Approval protocol fixture completed; no provider inference.", "annotations": []}]}
                        item = call if len(owner.records) == 1 else message
                        response = {"id": "resp_protocol_fixture_" + str(len(owner.records)), "object": "response", "status": "completed", "output": [item], "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}
                        events = [{"type": "response.created", "response": {**response, "status": "in_progress", "output": []}}, {"type": "response.output_item.done", "output_index": 0, "item": item}, {"type": "response.completed", "response": response}]
                        record["synthetic_protocol_fixture"] = True
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header("Connection", "close")
                        self.end_headers()
                        self.wfile.write("".join("data: " + json.dumps(event) + "\n\n" for event in events).encode())
                        self.wfile.flush()
                        self.close_connection = True
                        return
                    if not owner.live:
                        return self.error(400, "dry_capture_no_provider_call")
                    with owner.lock:
                        assert owner.key, "Provider key is unavailable"
                        assert owner.calls < owner.limits["max_provider_requests"] and time.monotonic() < owner.deadline, "Run request/time limit reached"
                        assert owner.charged + bound <= owner.limits["max_run_charged_tokens"], "Run token allowance cannot cover the reservation"
                        reservation = owner.run_id + ":" + str(owner.calls) + ":" + uuid.uuid4().hex[:8]
                        with (ROOT / ".runtime/guided-budget.lock").open("a") as lockfile:
                            fcntl.flock(lockfile, fcntl.LOCK_EX)
                            scope = rehearsal_scope_snapshot()
                            assert scope["requests_remaining"] > 0 and bound <= scope["tokens_remaining"], "Fixed whole-rehearsal allowance cannot cover the reservation"
                            owner.budget.reserve(reservation, owner.run_id, bound)
                        owner.calls += 1
                        owner.charged += bound
                        record.update(forwarded=True, reservation_id=reservation)
                except Exception as error:
                    owner.records.append({"forwarded": False, "rejection": type(error).__name__, "reason": str(error)[:200]})
                    return self.error(400, "request_or_budget_guard_rejected")
                actual, stream_started = None, False
                try:
                    with httpx.Client(timeout=45, trust_env=False, follow_redirects=False) as client:
                        with client.stream("POST", "https://api.openai.com/v1/responses", headers={"Authorization": "Bearer " + owner.key, "Content-Type": "application/json"}, json=payload) as response:
                            record["http_status"] = response.status_code
                            if response.status_code != 200:
                                response.read()
                                try:
                                    record["provider_error_code"] = response.json().get("error", {}).get("code")
                                except ValueError:
                                    pass
                                return self.error(response.status_code, "provider_rejected_request")
                            self.send_response(200)
                            self.send_header("Content-Type", "text/event-stream")
                            self.send_header("Connection", "close")
                            self.end_headers()
                            stream_started = True
                            begin = time.monotonic()
                            for line in response.iter_lines():
                                if time.monotonic() - begin > 45:
                                    raise TimeoutError("Provider stream deadline reached")
                                if line.startswith("data: "):
                                    try:
                                        event = json.loads(line[6:])
                                        if event.get("type") in ("response.completed", "response.incomplete"):
                                            result = event.get("response", {})
                                            usage = result.get("usage", {})
                                            actual = usage.get("total_tokens")
                                            if actual is None and "input_tokens" in usage and "output_tokens" in usage:
                                                actual = usage["input_tokens"] + usage["output_tokens"]
                                            record["provider_response_id"] = result.get("id")
                                            record["usage"] = usage
                                            record["output_items"] = [{key: item[key] for key in ("type", "name", "call_id", "arguments") if key in item} for item in result.get("output", []) if item.get("type") in ("function_call", "message")]
                                    except ValueError:
                                        pass
                                self.wfile.write((line + "\n").encode())
                                self.wfile.flush()
                except (httpx.HTTPError, OSError, TimeoutError) as error:
                    record["transport_error"] = type(error).__name__
                    if not stream_started:
                        self.error(502, "provider_transport_failed")
                finally:
                    self.close_connection = True
                    if not isinstance(actual, int) or actual < 0:
                        actual = None
                    try:
                        owner.budget.settle(reservation, actual)
                        with owner.lock:
                            owner.charged += (bound if actual is None else actual) - bound
                    except Exception as error:
                        record["settlement_error"] = type(error).__name__
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = False
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class RPC:
    def __init__(self, process):
        self.process, self.counter, self.events = process, 0, []
        self.approval_decisions = []

    def authorized_readonly_approval(self, event):
        """Accept one standard approval, never persist or alter host policy."""
        params = event.get("params", {})
        meta = params.get("_meta") or {}
        if event.get("method") != "mcpServer/elicitation/request" or params.get("serverName") != "opensoom" or params.get("mode") != "form" or meta.get("codex_approval_kind") != "mcp_tool_call":
            return None
        name = next((name for name in ALLOWED_TOOLS if params.get("message") == f'Allow the opensoom MCP server to run tool "{name}"?'), None)
        args = meta.get("tool_params")
        if not name or not isinstance(args, dict) or params.get("requestedSchema") != {"type": "object", "properties": {}}:
            return None
        calls = [e.get("params", {}).get("item", {}) for e in self.events if e.get("method") == "item/started" and e.get("params", {}).get("threadId") == params.get("threadId") and e.get("params", {}).get("turnId") == params.get("turnId")]
        if not any(item.get("type") == "mcpToolCall" and item.get("server") == "opensoom" and item.get("tool") == name and item.get("arguments") == args and item.get("pluginId") == "opensoom@opensoom-local" for item in calls):
            return None
        allowed = name == "doctor" and args == {}
        if name == "discover":
            allowed = set(args) <= {"facility_id"} and args.get("facility_id") in (None, "learning-b")
        elif name == "prepare_setup":
            facilities = json.loads((ROOT / "config/facilities.json").read_text())
            records = facilities.get("facilities", []) if isinstance(facilities, dict) else facilities
            profile_ids = {item["profile"] for item in records if item.get("id") == "learning-b"}
            allowed = set(args) == {"profile_id"} and args["profile_id"] in profile_ids
        elif name in {"read_group", "read_evidence"}:
            allowed = set(args) <= {"facility_id", "zone_id"} and args.get("facility_id") == "learning-b" and (args.get("zone_id") is None or isinstance(args.get("zone_id"), str))
        return {"action": "accept", "content": {}} if allowed else None

    async def send(self, message):
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        await self.process.stdin.drain()

    async def read(self):
        line = await self.process.stdout.readline()
        if not line:
            raise RuntimeError("Codex app-server exited")
        event = json.loads(line)
        if "method" in event:
            self.events.append(event)
            if "id" in event:
                response = self.authorized_readonly_approval(event)
                self.approval_decisions.append({"request_id": event["id"], "method": event["method"], "decision": "accept_once" if response else "deny", "policy_changed": False})
                if response:
                    await self.send({"jsonrpc": "2.0", "id": event["id"], "result": response})
                else:
                    await self.send({"jsonrpc": "2.0", "id": event["id"], "error": {"code": -32601, "message": "This request is outside the already authorized read-only openSoom scope"}})
        return event

    async def request(self, method, params):
        self.counter += 1
        request_id = self.counter
        await self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        async with asyncio.timeout(45):
            while True:
                value = await self.read()
                if value.get("id") == request_id and "method" not in value:
                    if "error" in value:
                        raise RuntimeError(method + " failed: " + str(value["error"]))
                    return value["result"]


def find_skill(value):
    if isinstance(value, dict):
        if str(value.get("name", "")).endswith("opensoom-setup") and value.get("path"):
            return value
        for item in value.values():
            found = find_skill(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = find_skill(item)
            if found:
                return found


def structured_tool_result(item):
    result = item.get("result") or {}
    if isinstance(result.get("structuredContent"), dict):
        return result["structuredContent"]
    for block in result.get("content", []):
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            try:
                value = json.loads(block["text"])
                if isinstance(value, dict):
                    return value
            except ValueError:
                pass
    return {}


async def rehearse(live, protocol_fixture=False):
    folder = ROOT / ".runtime" / ("guided-" + uuid.uuid4().hex[:10])
    profile = folder / "codex-profile"
    profile.mkdir(parents=True)
    proxy = BoundedProxy(folder, live, protocol_fixture)
    proxy.start()
    executable = shutil.which("codex")
    env = {key: val for key, val in os.environ.items() if not any(word in key for word in ("API_KEY", "TOKEN", "SECRET"))}
    env.update(CODEX_HOME=str(profile), OPENSOOM_CODEX_PROXY_TOKEN=proxy.local_token)
    catalog = prepare(ROOT)
    result = {"status": "RUNNING", "rehearsal_id": folder.name, "mode": "live" if live else "dry_capture", "provider": "https://api.openai.com/v1/responses", "model": MODEL, "limits": proxy.limits, "shared_budget_before": proxy.before, "starting_state": "Maintainer installed and started the virtual service and activated its profiles before rehearsal; Codex profile/workspace are fresh.", "global_settings_changed": False, "model_decides_tool_order_and_arguments": True, "manual_operational_tool_calls": 0, "user_prompt": PROMPT, "scoped_base_instructions": BASE_INSTRUCTIONS, "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [Path(__file__).resolve(), ROOT / "src/opensoom/mcp_server.py", *sorted((ROOT / "plugin").rglob("SKILL.md"))]}}
    process = None
    stderr_task = None
    with tempfile.TemporaryDirectory(prefix="opensoom-guided-", dir="/private/tmp") as workspace:
        try:
            version = subprocess.run([executable, "--version"], env=env, capture_output=True, text=True, timeout=15)
            result["codex_version"] = version.stdout.strip()
            result["plugin_installation"] = []
            for command in [["plugin", "list", "--json"], ["plugin", "marketplace", "add", str(catalog), "--json"], ["plugin", "add", "opensoom@opensoom-local", "--json"]]:
                run = subprocess.run([executable, *command], cwd=workspace, env=env, capture_output=True, text=True, timeout=45)
                result["plugin_installation"].append({"command": command, "exit_status": run.returncode, "output": json.loads(run.stdout) if run.stdout.strip().startswith(("{", "[")) else run.stdout[:2000]})
                assert run.returncode == 0, "Plugin installation failed"
            # Preserve the installer's marketplace/plugin configuration. These
            # standard child-process overrides contain no provider credential.
            settings = ['model="gpt-5-mini"', 'model_provider="opensoom_bounded"', 'model_reasoning_effort="minimal"', 'web_search="disabled"', 'features.shell_tool=false', 'features.multi_agent=false', 'model_providers.opensoom_bounded.name="openSoom bounded rehearsal"', f'model_providers.opensoom_bounded.base_url="http://127.0.0.1:{proxy.server.server_port}/v1"', 'model_providers.opensoom_bounded.env_key="OPENSOOM_CODEX_PROXY_TOKEN"', 'model_providers.opensoom_bounded.wire_api="responses"', 'model_providers.opensoom_bounded.requires_openai_auth=false', 'model_providers.opensoom_bounded.request_max_retries=0', 'model_providers.opensoom_bounded.stream_max_retries=0', 'model_providers.opensoom_bounded.stream_idle_timeout_ms=50000']
            overrides = [part for setting in settings for part in ("-c", setting)]
            result["scoped_startup_overrides"] = settings
            process = await asyncio.create_subprocess_exec(executable, *overrides, "app-server", "--listen", "stdio://", cwd=workspace, env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=4_000_000)
            stderr_task = asyncio.create_task(process.stderr.read())
            rpc = RPC(process)
            await rpc.request("initialize", {"clientInfo": {"name": "opensoom-guided-rehearsal", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}})
            await rpc.send({"jsonrpc": "2.0", "method": "initialized"})
            result["plugin_inventory"] = await rpc.request("plugin/list", {"cwds": [workspace], "forceRefetch": False})
            skills = await rpc.request("skills/list", {"cwds": [workspace], "forceReload": True})
            skill = find_skill(skills)
            assert skill, "Installed setup skill was not discovered by Codex"
            result["selected_installed_skill"] = skill
            thread = await rpc.request("thread/start", {"cwd": workspace, "ephemeral": True, "sandbox": "read-only", "approvalPolicy": "on-request", "model": MODEL, "modelProvider": "opensoom_bounded", "baseInstructions": BASE_INSTRUCTIONS})
            thread_id = thread["thread"]["id"]
            result["host_mcp_inventory"] = await rpc.request("mcpServerStatus/list", {"threadId": thread_id, "limit": 20})
            await rpc.request("turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": PROMPT}, {"type": "skill", "name": skill["name"], "path": skill["path"]}]})
            async with asyncio.timeout(180):
                while True:
                    event = await rpc.read()
                    if event.get("method") == "turn/completed":
                        result["turn"] = event["params"]["turn"]
                        break
            result["host_events"] = [event for event in rpc.events if event.get("method") in ("item/started", "item/completed", "turn/completed", "error") or "id" in event]
            result["host_approval_decisions"] = rpc.approval_decisions
            if protocol_fixture:
                assert proxy.calls == 0
                result["status"] = "CAPTURED_ZERO_API_PROTOCOL_FIXTURE"
            elif not live:
                assert proxy.calls == 0 and any(record.get("conservative_reserved_tokens") for record in proxy.records), "Dry request did not pass the forwarding schema checks"
                result["status"] = "PASS_ZERO_API_DRY_CAPTURE"
            else:
                completed = [event["params"]["item"] for event in result["host_events"] if event.get("method") == "item/completed"]
                calls = [item for item in completed if item.get("type") == "mcpToolCall"]
                result["model_selected_mcp_calls"] = calls
                names = {item.get("tool") for item in calls}
                assert {"doctor", "prepare_setup", "discover", "read_evidence"} <= names, names
                assert names <= ALLOWED_TOOLS and all(item.get("status") == "completed" for item in calls)
                texts = [item.get("text", "") for item in completed if item.get("type") == "agentMessage"]
                result["model_korean_explanation"] = "\n".join(texts)
                assert any("가" <= char <= "힣" for char in result["model_korean_explanation"])
                assert proxy.calls and result["turn"]["status"] == "completed"
                returned = [structured_tool_result(item) for item in calls]
                run_ids = {item["run_id"] for item in returned if item.get("run_id")}
                assert len(run_ids) == 1, "Host facility calls did not share one service run"
                service_run = ServiceProxy().request("GET", "/api/runs/" + next(iter(run_ids)))
                assert service_run["mode"] == "mcp_host" and service_run["facility_id"] == "learning-b"
                assert {"discover", "read_evidence"} <= {item["name"] for item in service_run["tool_calls"]}
                result["independently_retrieved_service_run"] = service_run
                result["run_correlation_verified"] = True
                result["status"] = "PASS_CODEX_MODEL_GUIDED_READONLY"
        except Exception as error:
            result.update(status="BLOCKED_GUIDED_REHEARSAL", error={"type": type(error).__name__, "message": str(error)[:1000]})
        finally:
            if process and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=8)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            if stderr_task:
                (folder / "codex-stderr.log").write_bytes(await stderr_task)
            proxy.close()
    result.update(provider_requests=proxy.records, provider_calls=proxy.calls, run_tokens_charged=proxy.charged, shared_budget_after=proxy.budget.snapshot(), fixed_rehearsal_scope_before=proxy.scope_before, fixed_rehearsal_scope_after=rehearsal_scope_snapshot(), synthetic_protocol_fixture=protocol_fixture, test_process_stopped=not process or process.returncode is not None)
    result = safe(result, proxy.secrets)
    (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result, folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--protocol-fixture", action="store_true", help="Zero-provider-call host approval protocol test; never live model evidence")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.live and args.protocol_fixture:
        parser.error("Protocol fixtures cannot be used in live mode")
    result, folder = asyncio.run(rehearse(args.live, args.protocol_fixture))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "provider_calls": result["provider_calls"], "error": result.get("error"), "requests": [{k: record.get(k) for k in ("payload_bytes", "conservative_reserved_tokens", "tool_names", "forwarded", "rejection", "reason")} for record in result["provider_requests"]], "local_result": str(folder.relative_to(ROOT) / "result.json")}, ensure_ascii=False))
    raise SystemExit(0 if result["status"].startswith(("PASS", "CAPTURED")) else 1)


if __name__ == "__main__":
    main()
