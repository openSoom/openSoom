"""Run a named virtual trial in a real isolated Codex host using the existing shared test budget."""
import argparse
import asyncio
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import uuid

import codex_guided_rehearsal as base
from codex_configuration_rehearsal import compact_tool_json

ROOT = base.ROOT
PREFIX = "codex-scenario-"
TOOLS = {"save_scenario", "run_scenario", "read_scenario_run"}
LIMITS = {"max_provider_requests": 1, "max_run_charged_tokens": 5924, "max_output_tokens": 150,
          "provider_timeout_seconds": 45, "turn_timeout_seconds": 150, "request_max_retries": 0}


def case_scope():
    with sqlite3.connect(ROOT / ".runtime/llm-budget.sqlite") as conn:
        count, charged = conn.execute("SELECT COUNT(*),COALESCE(SUM(charged_tokens),0) FROM reservations WHERE run_id LIKE ?", (PREFIX + "%",)).fetchone()
    policy = json.loads((ROOT / "config/live-test-budget.json").read_text())
    return {"requests_remaining": policy["max_attempts_per_step"] - count,
            "tokens_remaining": LIMITS["max_run_charged_tokens"] - charged}


class TrialRPC(base.RPC):
    def __init__(self, process, scenario):
        super().__init__(process)
        self.scenario = scenario

    def authorized_readonly_approval(self, event):
        params = event.get("params", {})
        meta = params.get("_meta") or {}
        name = "test_virtual_scenario"
        if params.get("message") != f'Allow the opensoom MCP server to run tool "{name}"?':
            return None
        args = meta.get("tool_params")
        if (event.get("method") != "mcpServer/elicitation/request" or params.get("mode") != "form"
                or params.get("serverName") != "opensoom" or meta.get("codex_approval_kind") != "mcp_tool_call"
                or not isinstance(args, dict) or params.get("requestedSchema") != {"type": "object", "properties": {}}):
            return None
        matching = [e["params"].get("item", {}) for e in self.events if e.get("method") == "item/started"
                    and e["params"].get("threadId") == params.get("threadId") and e["params"].get("turnId") == params.get("turnId")]
        if not any(item.get("type") == "mcpToolCall" and item.get("server") == "opensoom" and item.get("tool") == name
                   and item.get("arguments") == args and item.get("pluginId") == "opensoom@opensoom-local" for item in matching):
            return None
        valid = (set(args) == set(self.scenario) | {"request_id"} and all(args[k] == v for k, v in self.scenario.items())
                 and isinstance(args["request_id"], str) and re.fullmatch(r"[a-zA-Z0-9._:-]{1,80}", args["request_id"]))
        return {"action": "accept", "content": {}} if valid else None


def verify_model_call(item, scope, service_run):
    data = base.structured_tool_result(item)
    inputs = {k: v for k, v in item["arguments"].items() if k != "request_id"}
    calls = [c for c in service_run["tool_calls"] if c["name"] in TOOLS]
    names = [c["name"] for c in calls]
    use = calls[1]["arguments"] if len(calls) == 3 else {}
    read = calls[2]["arguments"] if len(calls) == 3 else {}
    return {
        "actual_plugin": item.get("pluginId") == "opensoom@opensoom-local" and item["status"] == "completed",
        "model_arguments_match_manager_request": inputs == scope,
        "actual_cse_cin": bool(data.get("cin")) and data["cin"] == data.get("readback", {}).get("cin") and bool(data["readback"].get("rqi")),
        "zero_new_commands": data.get("command_state_tag_delta") == 0 and data["commands_before"]["state_tag"] == data["commands_after"]["state_tag"],
        "expectation_met": data.get("assertion_passed") is True and data["actual_result"] == "command_refused",
        "service_recorded": names == ["save_scenario", "run_scenario", "read_scenario_run"]
            and calls[0]["arguments"] == scope and calls[0]["result_status"] == "ok"
            and all(c["result_status"] == "completed" for c in calls[1:]),
        "same_definition": bool(use.get("version")) and use["version"] == data["version"]
            and all(use.get(k) == scope[k] for k in ("facility_id", "scenario_id"))
            and use["request_id"] == item["arguments"]["request_id"]
            and read == {"facility_id": scope["facility_id"], "execution_id": data["execution_id"]},
        "exact_origin": data["readback"]["zone_id"] == scope["zone_id"] and data["readback"]["airflow_m3_h"] == scope["airflow_m3_h"],
    }


def audit_after_restart(args):
    """Recheck an original hosted tool call and replay its saved version, without inference."""
    from opensoom.scenario_authoring import digest
    from opensoom.store import Store
    capture = json.loads(args.audit_restart.read_text())
    item = next(c for c in capture["tool_calls"] if c["tool"] == "test_virtual_scenario" and c["status"] == "completed")
    data, scope = base.structured_tool_result(item), capture["authorized_scope"]
    token = json.loads((args.runtime / "service-credentials.json").read_text())["operator_token"]
    service = base.ServiceProxy(args.service, token=token)
    run = service.request("GET", "/api/runs/" + data["run_id"])
    checks = verify_model_call(item, scope, run)
    saved = Store(args.runtime / "operations.sqlite").get("scenario_definitions", data["version"])
    checks["stored_version_hash"] = (digest({k:v for k,v in saved.items() if k != "version"}) == data["version"]
                                      and all(saved[k] == value for k, value in scope.items()))
    def call(name, arguments):
        return service.request("POST", "/api/tools/" + name, {"arguments": arguments})
    def read(execution):
        return call("read_scenario_run", {"facility_id":scope["facility_id"], "execution_id":execution})
    original = read(data["execution_id"])
    checks["original_cin_after_service_restart"] = (original["readback"]["cin"] == data["cin"]
                                                     and original["readback"]["rqi"] != data["readback"]["rqi"])
    trial = call("run_scenario", {"facility_id":scope["facility_id"], "scenario_id":scope["scenario_id"],
                                  "version":saved["version"], "request_id":"restart-" + uuid.uuid4().hex[:16]})
    replay = read(trial["execution_id"])
    checks["replay_new_cin_same_definition"] = (replay["version"] == data["version"] and replay["cin"] != data["cin"]
        and replay["readback"]["cin"] == replay["cin"] and replay["assertion_passed"] and replay["command_state_tag_delta"] == 0)
    accepted = all(checks.values())
    result = {"status":"verified" if accepted else "incomplete", "source_capture":args.audit_restart.name,
              "run_id":data["run_id"], "execution_id":data["execution_id"], "model":capture["model"],
              "model_selected_tool":item["tool"], "model_generated_arguments":item["arguments"],
              "host_approval":capture["approvals"], "original_inference_calls":sum(p.get("forwarded") is True for p in capture["provider_requests"]),
              "new_inference_calls_for_audit":0, "checks":checks, "service_run":run, "stored_definition":saved,
              "original_after_restart":original, "replay_after_restart":replay}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status":result["status"], "checks":checks}))
    return accepted


async def rehearse(args):
    folder = ROOT / ".runtime" / (PREFIX + uuid.uuid4().hex[:10])
    profile = folder / "codex-profile"
    profile.mkdir(parents=True)
    credentials = args.runtime / "service-credentials.json"
    service = base.ServiceProxy(args.service, token=json.loads(credentials.read_text())["operator_token"])
    base.rehearsal_scope_snapshot = case_scope
    base.ALLOWED_TOOLS = {"test_virtual_scenario"}
    proxy = base.BoundedProxy(folder, args.live)
    proxy.limits = dict(LIMITS)
    proxy.use_provider_token_count = True
    proxy.secrets.append(service.token)
    in_order = threading.Lock()
    handler = proxy.server.RequestHandlerClass
    class TrialHandler(handler):
        def do_POST(self):
            with in_order:
                length = int(self.headers.get("Content-Length", "0"))
                if 0 < length <= 100000:
                    raw = self.rfile.read(length)
                    if any(secret.encode() in raw for secret in proxy.secrets if secret):
                        return self.error(403, "secret_in_payload")
                    payload = json.loads(raw)
                    # The rehearsal needs only the structured call and its receipt.
                    payload.pop("prompt_cache_key", None)
                    payload.pop("include", None)
                    for item in payload.get("input", []):
                        if item.get("type") == "function_call_output":
                            item["output"], _ = compact_tool_json(item.get("output"))
                        for part in item.get("content", []) if isinstance(item.get("content"), list) else []:
                            if isinstance(part, dict) and isinstance(part.get("text"), str):
                                part["text"] = part["text"].replace(str(ROOT), "<checkout>").replace(str(Path.home()), "<user-home>").replace(workspace, "<workspace>")
                    raw = json.dumps(payload, ensure_ascii=False).encode()
                    if not args.live:
                        (folder / "dry-request.json").write_bytes(raw)
                    self.headers.replace_header("Content-Length", str(len(raw)))
                    self.rfile = io.BytesIO(raw)
                return super().do_POST()
    proxy.server.RequestHandlerClass = TrialHandler
    proxy.start()
    scope = {"facility_id": "learning-b", "scenario_id": "lounge-probe-" + uuid.uuid4().hex[:6], "zone_id": "lounge",
             "observation_age_seconds": 93, "airflow_m3_h": 345, "damper_percent": 83, "expected_result": "command_refused"}
    prompt = (f"Test virtual facility learning-b, zone lounge. Name the trial {scope['scenario_id']}. "
              "Airflow 345 m3/h, age 93 seconds, damper 83%. Expect command refused. Verify.")
    result = {"status": "incomplete", "case_id": folder.name, "user_prompt": prompt, "authorized_scope": scope,
              "known_limits": "Isolated Codex host with a dedicated loopback service. Startup and facility activation already completed. "
                              "The installed plugin exposes the full tool set. In this focused rehearsal the model can invoke the compound "
                              "virtual-test tool. Its one actual model call supplies the test arguments. The service records the three "
                              "underlying operations; the harness ends at actual readback. Local path prefixes are redacted.",
              "provider": "https://api.openai.com/v1/responses", "model": base.MODEL, "shared_before": proxy.before,
              "case_limits": LIMITS, "mode": "live" if args.live else "dry"}
    executable = shutil.which("codex")
    env = {k: v for k, v in os.environ.items() if not any(word in k for word in ("API_KEY", "TOKEN", "SECRET"))}
    env.update(CODEX_HOME=str(profile), OPENSOOM_CODEX_PROXY_TOKEN=proxy.local_token)
    process = rpc = stderr = None
    with tempfile.TemporaryDirectory(prefix="opensoom-trial-") as workspace:
        try:
            catalog = base.prepare(ROOT, service_url=args.service, credentials=credentials, catalog_dir=folder / "marketplace")
            result["codex"] = subprocess.check_output([executable, "--version"], env=env, text=True).strip()
            for command in (["plugin", "marketplace", "add", str(catalog), "--json"], ["plugin", "add", "opensoom@opensoom-local", "--json"]):
                subprocess.run([executable, *command], cwd=workspace, env=env, capture_output=True, timeout=45, check=True)
            result["installed"] = "opensoom@opensoom-local"
            config = ['model="gpt-5-mini"', 'model_provider="bounded"', 'model_reasoning_effort="minimal"', 'web_search="disabled"', 'features.shell_tool=false',
                      'features.omit_skill_descriptions=true', 'features.skip_host_skill_discovery=true',
                      'model_providers.bounded.name="openSoom virtual trial"', f'model_providers.bounded.base_url="http://127.0.0.1:{proxy.server.server_port}/v1"',
                      'model_providers.bounded.env_key="OPENSOOM_CODEX_PROXY_TOKEN"', 'model_providers.bounded.wire_api="responses"',
                      'model_providers.bounded.request_max_retries=0', 'model_providers.bounded.stream_max_retries=0']
            overrides = [s for line in config for s in ("-c", line)]
            process = await asyncio.create_subprocess_exec(executable, *overrides, "app-server", "--listen", "stdio://", cwd=workspace, env=env,
                                                         stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=4_000_000)
            stderr = asyncio.create_task(process.stderr.read())
            rpc = TrialRPC(process, scope)
            await rpc.request("initialize", {"clientInfo": {"name": "opensoom-trial", "version": "1.0"}, "capabilities": {"experimentalApi": True}})
            await rpc.send({"method": "initialized"})
            session = await rpc.request("thread/start", {"cwd": workspace, "ephemeral": True, "sandbox": "read-only", "approvalPolicy": "on-request",
                                        "model": base.MODEL, "modelProvider": "bounded", "baseInstructions": "Use the installed openSoom tool for this virtual trial. Preserve permissions."})
            thread = session["thread"]["id"]
            result["thread_id"] = thread
            if args.read_execution:
                if args.live:
                    raise ValueError("Recorded execution lookup uses a local host read, without model inference")
                inventory = await rpc.request("mcpServerStatus/list", {"threadId": thread, "limit": 20})
                server = next(item["name"] for item in inventory["data"] if item["name"] == "opensoom")
                response = await rpc.request("mcpServer/tool/call", {"threadId": thread, "server": server, "tool": "read_scenario_run",
                                            "arguments": {"facility_id": "learning-b", "execution_id": args.read_execution}})
                data = response["structuredContent"]
                assert not response.get("isError") and data["execution_id"] == args.read_execution and data.get("readback", {}).get("rqi")
                result.update(status="verified host read", mode="harness-selected read-only lookup",
                              user_prompt=None, authorized_scope={"facility_id": "learning-b", "execution_id": args.read_execution},
                              model=None, provider=None, model_selected_this_read=False,
                              host_readback=data, known_limits="The installed Codex host rereads the specified execution. This separate read does not author or run a new scenario.")
                return complete(result, args, proxy)
            await rpc.request("turn/start", {"threadId": thread, "input": [{"type": "text", "text": prompt}]})
            async with asyncio.timeout(150):
                while True:
                    event = await rpc.read()
                    item = event.get("params", {}).get("item", {})
                    if event.get("method") == "item/completed" and item.get("type") == "mcpToolCall":
                        result.setdefault("tool_calls", []).append(item)
                        data = base.structured_tool_result(item)
                        if item.get("status") == "completed" and item["tool"] == "test_virtual_scenario":
                            run = service.request("GET", "/api/runs/" + data["run_id"])
                            result["service_run"] = run
                            result["checks"] = verify_model_call(item, scope, run)
                            if all(result["checks"].values()):
                                result["status"] = "verified Codex authored trial"
                            break
                    if event.get("method") == "turn/completed":
                        result["host_status"] = event["params"]["turn"]["status"]
                        break
        except Exception as error:
            result["error"] = type(error).__name__ + ": " + str(error)[:300]
        finally:
            if process and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 8)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            if stderr:
                (folder / "host-stderr.log").write_bytes(await stderr)
            proxy.close()
    result["approvals"] = rpc.approval_decisions if rpc else []
    return complete(result, args, proxy)


def complete(result, args, proxy):
    result.update(provider_requests=proxy.records, shared_after=proxy.budget.snapshot())
    if not args.live and any(record.get("conservative_reserved_tokens") for record in proxy.records):
        result["status"] = "dry request captured"
    result = base.safe(result, proxy.secrets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "error": result.get("error"), "requests": [(r.get("conservative_reserved_tokens"),r.get("reason")) for r in proxy.records],
                      "remaining": result["shared_after"]["tokens_remaining"]}))
    return result["status"] in ("dry request captured", "verified Codex authored trial", "verified host read")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--read-execution", help="Read a known run from the installed host without model inference or a new virtual trial")
    parser.add_argument("--audit-restart", type=Path, help="After restarting the service, corroborate an original Codex capture and replay the same saved version")
    args = parser.parse_args()
    if args.audit_restart and (args.live or args.read_execution):
        parser.error("Use a separate offline-evidence audit without another model call")
    passed = audit_after_restart(args) if args.audit_restart else asyncio.run(rehearse(args))
    raise SystemExit(0 if passed else 1)
