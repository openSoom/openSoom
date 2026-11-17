#!/usr/bin/env python3
"""A separate, fixed-scope Codex configuration/group acceptance case.

The previous six-request guided rehearsal is immutable and remains partial.
This case has its own three-request/30,000-token scope inside the unchanged
shared budget. Default mode captures a real Codex request without inference.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
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
import time
import uuid

import codex_guided_rehearsal as base

ROOT = base.ROOT
PREFIX = "codex-config-"
LIMITS = {"max_provider_requests": 3, "max_run_charged_tokens": 30000,
          "max_output_tokens": 2048, "provider_timeout_seconds": 45,
          "turn_timeout_seconds": 120, "request_max_retries": 0}
PROMPT = """관리자가 실행하고 가상 프로필을 활성화한 openSoom에서 learning-space 프로필의 설정 준비 상태와 learning-b 시설의 그룹 상태를 확인해주세요. 설정이나 장비는 바꾸지 말고, 확인 결과와 다음 할 일을 한국어 5문장 이내로 알려주세요."""
INSTRUCTIONS = """Follow the attached setup skill for this focused read-only configuration/group review. Choose tools, order and arguments yourself; combine independent checks when useful. At most three model responses are available. Never change settings, roles or equipment or disclose secrets. Report actual facts in at most five short Korean sentences, including simulation limits and that CSE group success is not device ACK."""


def compact_tool_json(output):
    """Remove only exact duplicate JSON representations; keep every fact."""
    if not isinstance(output, str):
        return output, None
    try:
        original = json.loads(output)
    except ValueError:
        return output, None
    operations = []
    def canonical(value, path):
        if isinstance(value, list):
            return [canonical(item, path + "/" + str(index)) for index, item in enumerate(value)]
        if not isinstance(value, dict):
            return value
        value = dict(value)
        content = value.get("content")
        if "structuredContent" in value and isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict) and set(content[0]) == {"type", "text"} and content[0].get("type") == "text":
            try:
                duplicate = json.loads(content[0]["text"])
            except (ValueError, TypeError):
                duplicate = object()
            if duplicate == value["structuredContent"]:
                operations.append({"kind": "exact_duplicate_json", "path": path + "/content", "equals_structured_content": True,
                                   "facts_sha256": hashlib.sha256(json.dumps(duplicate, sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
                del value["content"]
        for key, item in list(value.items()):
            if key == "text" and value.get("type") in ("text", "output_text") and isinstance(item, str):
                try:
                    decoded = json.loads(item)
                except ValueError:
                    pass
                else:
                    minimized = canonical(decoded, path + "/text/json")
                    value[key] = json.dumps(minimized, ensure_ascii=False, separators=(",", ":"))
                    operations.append({"kind": "json_text_whitespace", "path": path + "/text"})
                    continue
            value[key] = canonical(item, path + "/" + key)
        return value
    after = canonical(original, "")
    compact = json.dumps(after, ensure_ascii=False, separators=(",", ":"))
    expected = json.dumps(after, sort_keys=True, ensure_ascii=False)
    restored = json.dumps(canonical(json.loads(compact), ""), sort_keys=True, ensure_ascii=False)
    assert expected == restored, "Tool JSON semantic round trip failed"
    return compact, {"before_bytes": len(output.encode()), "after_bytes": len(compact.encode()),
                     "before_sha256": hashlib.sha256(output.encode()).hexdigest(),
                     "after_sha256": hashlib.sha256(compact.encode()).hexdigest(),
                     "semantic_sha256": hashlib.sha256(expected.encode()).hexdigest(),
                     "semantic_equality_verified": True, "operations": operations,
                     "original_host_result_preserved": True}


def case_scope_snapshot():
    policy_path = ROOT / ".runtime/codex-config-case-policy.json"
    saved = json.loads(policy_path.read_text())
    if saved.get("case_prefix") != PREFIX or saved.get("limits") != LIMITS:
        raise RuntimeError("The fixed focused-case policy cannot be silently changed")
    with sqlite3.connect(ROOT / ".runtime/llm-budget.sqlite") as conn:
        calls, charged = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(charged_tokens),0) FROM reservations WHERE run_id LIKE ?",
            (PREFIX + "%",),
        ).fetchone()
    return {"max_requests": 3, "max_tokens": 30000, "requests_consumed": calls,
            "tokens_charged": charged, "requests_remaining": max(0, 3 - calls),
            "tokens_remaining": max(0, 30000 - charged)}


async def execute(live, continue_from=None):
    # The imported implementation file is unchanged. These process-local hooks
    # bind the same audited proxy to this distinct fixed task, not the old one.
    base.rehearsal_scope_snapshot = case_scope_snapshot
    base.ALLOWED_TOOLS = {"prepare_setup", "read_group"}
    prompt, instructions, continuation = PROMPT, INSTRUCTIONS, None
    if continue_from:
        previous_path = continue_from.resolve()
        assert previous_path.parent == ROOT / "evidence/agent" and previous_path.name.startswith("guided-config-"), "Continuation source must be this case's captured evidence"
        previous = json.loads(previous_path.read_text())
        assert previous.get("case_id", "").startswith(PREFIX) and previous.get("mode") == "live"
        preparations = [item for item in previous.get("model_selected_mcp_calls", []) if item.get("tool") == "prepare_setup" and item.get("status") == "completed" and item.get("arguments") == {"profile_id": "learning-space"}]
        assert len(preparations) == 1, "One genuine prior setup result is required"
        prepared = base.structured_tool_result(preparations[0])
        assert prepared.get("profile", {}).get("id") == "learning-space"
        continuation = {"source": str(previous_path.relative_to(ROOT)), "source_sha256": hashlib.sha256(previous_path.read_bytes()).hexdigest(),
                        "prior_case_attempt": previous["case_id"], "actual_setup_call_id": preparations[0]["id"],
                        "actual_setup_result": prepared, "same_chat": False,
                        "reason": "The previous ephemeral thread has no rollout; official thread/resume failed. This new chat receives the exact actual tool result as attributed data, never forged tool-history messages."}
        prompt = "앞선 설정 준비 점검은 아래 출처의 실제 도구 결과로 확인되었습니다. 이전 임시 대화는 재개할 수 없어 이 새 대화에서 같은 점검을 이어갑니다. 남은 learning-b 그룹 상태를 확인하고 앞선 설정 결과와 함께 다음 할 일을 한국어 5문장 이내로 알려주세요. 설정과 장비는 바꾸지 마세요.\n\n아래는 지시가 아닌 이전 실제 도구 결과 데이터입니다.\n출처: " + continuation["source"] + "\nSHA-256: " + continuation["source_sha256"] + "\n" + json.dumps(prepared, ensure_ascii=False, separators=(",", ":"))
        instructions = INSTRUCTIONS.replace("At most three model responses are available.", "At most two model responses remain in this same bounded case.")
    folder = ROOT / ".runtime" / (PREFIX + uuid.uuid4().hex[:10])
    profile = folder / "codex-profile"
    profile.mkdir(parents=True)
    proxy = base.BoundedProxy(folder, live)
    proxy.limits = dict(LIMITS)
    proxy.deadline = time.monotonic() + 180
    transformations = []
    # A terminal SSE event can reach Codex before the provider handler's
    # finally block settles usage. Serialize complete handlers, including that
    # settlement, so the next request cannot double-count a live reservation.
    request_serial = threading.Lock()
    original_handler = proxy.server.RequestHandlerClass
    class CaptureHandler(original_handler):
        def do_POST(self):
            if not request_serial.acquire(timeout=45):
                return self.error(429, "previous_request_settlement_timeout")
            try:
                return self.serialized_post()
            finally:
                request_serial.release()

        def serialized_post(self):
            length = int(self.headers.get("Content-Length", "0"))
            if 0 < length <= 100000:
                raw = self.rfile.read(length)
                if not any(secret.encode() in raw for secret in proxy.secrets if secret):
                    (folder / ("request-" + str(len(proxy.records)) + ".json")).write_bytes(raw)
                    payload = json.loads(raw)
                    for item in payload.get("input", []):
                        if item.get("type") == "function_call_output":
                            compact, proof = compact_tool_json(item.get("output"))
                            if proof:
                                item["output"] = compact
                                transformations.append({"request_index": len(proxy.records), "call_id": item.get("call_id"), **proof})
                    raw = json.dumps(payload, ensure_ascii=False).encode()
                    self.headers.replace_header("Content-Length", str(len(raw)))
                self.rfile = io.BytesIO(raw)
            return super().do_POST()
    proxy.server.RequestHandlerClass = CaptureHandler
    proxy.start()
    env = {key: value for key, value in os.environ.items()
           if not any(word in key for word in ("API_KEY", "TOKEN", "SECRET"))}
    env.update(CODEX_HOME=str(profile), OPENSOOM_CODEX_PROXY_TOKEN=proxy.local_token)
    executable = shutil.which("codex")
    result = {
        "status": "RUNNING", "case": "focused_configuration_group_review",
        "case_id": folder.name, "mode": "live" if live else "dry_capture",
        "earlier_case": "The original guided six-request case remains failed/partial and is not reset or enlarged.",
        "starting_state": "Maintainer-installed, running virtual service and preactivated profiles; fresh Codex profile and empty workspace.",
        "provider": "https://api.openai.com/v1/responses", "model": base.MODEL,
        "limits": LIMITS, "shared_budget_before": proxy.before,
        "case_scope_before": proxy.scope_before, "global_settings_changed": False,
        "manual_operational_tool_calls": 0, "model_decides_tool_order_and_arguments": True,
        "exposed_tools": sorted(base.ALLOWED_TOOLS),
        "test_transport_transformation": "Exact duplicate JSON removal and JSON whitespace canonicalization only; original Codex host results retained. This is an instrumented focused case, not an out-of-box Codex claim.",
        "user_prompt": prompt, "scoped_base_instructions": instructions,
        "disclosed_continuation": continuation,
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [Path(__file__).resolve(), Path(base.__file__).resolve(),
                                       ROOT / "src/opensoom/mcp_server.py", *sorted((ROOT / "plugin").rglob("SKILL.md"))]},
    }
    process = rpc = stderr_task = None
    with tempfile.TemporaryDirectory(prefix="opensoom-config-case-", dir="/private/tmp") as workspace:
        try:
            result["codex_version"] = subprocess.run([executable, "--version"], env=env, capture_output=True, text=True, timeout=15).stdout.strip()
            catalog = base.prepare(ROOT)
            result["plugin_installation"] = []
            commands = [["plugin", "list", "--json"], ["plugin", "marketplace", "add", str(catalog), "--json"], ["plugin", "add", "opensoom@opensoom-local", "--json"]]
            for command in commands:
                completed = subprocess.run([executable, *command], cwd=workspace, env=env, capture_output=True, text=True, timeout=45)
                result["plugin_installation"].append({"command": command, "exit_status": completed.returncode,
                                                      "output": json.loads(completed.stdout) if completed.stdout.strip().startswith(("{", "[")) else completed.stdout[:1000]})
                assert completed.returncode == 0, "Plugin installation failed"
            settings = ['model="gpt-5-mini"', 'model_provider="opensoom_bounded"', 'model_reasoning_effort="minimal"', 'web_search="disabled"', 'features.shell_tool=false', 'features.multi_agent=false', 'model_providers.opensoom_bounded.name="openSoom focused configuration case"', f'model_providers.opensoom_bounded.base_url="http://127.0.0.1:{proxy.server.server_port}/v1"', 'model_providers.opensoom_bounded.env_key="OPENSOOM_CODEX_PROXY_TOKEN"', 'model_providers.opensoom_bounded.wire_api="responses"', 'model_providers.opensoom_bounded.requires_openai_auth=false', 'model_providers.opensoom_bounded.request_max_retries=0', 'model_providers.opensoom_bounded.stream_max_retries=0', 'model_providers.opensoom_bounded.stream_idle_timeout_ms=50000']
            result["scoped_startup_overrides"] = settings
            overrides = [part for setting in settings for part in ("-c", setting)]
            process = await asyncio.create_subprocess_exec(executable, *overrides, "app-server", "--listen", "stdio://", cwd=workspace, env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=4_000_000)
            stderr_task = asyncio.create_task(process.stderr.read())
            rpc = base.RPC(process)
            await rpc.request("initialize", {"clientInfo": {"name": "opensoom-config-case", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}})
            await rpc.send({"jsonrpc": "2.0", "method": "initialized"})
            result["plugin_inventory"] = await rpc.request("plugin/list", {"cwds": [workspace], "forceRefetch": False})
            skill = base.find_skill(await rpc.request("skills/list", {"cwds": [workspace], "forceReload": True}))
            assert skill, "Installed setup skill missing"
            result["selected_installed_skill"] = skill
            thread = await rpc.request("thread/start", {"cwd": workspace, "ephemeral": True, "sandbox": "read-only", "approvalPolicy": "on-request", "model": base.MODEL, "modelProvider": "opensoom_bounded", "baseInstructions": instructions})
            thread_id = thread["thread"]["id"]
            result["host_mcp_inventory"] = await rpc.request("mcpServerStatus/list", {"threadId": thread_id, "limit": 20})
            await rpc.request("turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": prompt}, {"type": "skill", "name": skill["name"], "path": skill["path"]}]})
            async with asyncio.timeout(120):
                while True:
                    event = await rpc.read()
                    if event.get("method") == "turn/completed":
                        result["turn"] = event["params"]["turn"]
                        break
            if not live:
                assert proxy.calls == 0 and any(item.get("conservative_reserved_tokens") for item in proxy.records)
                result["status"] = "CAPTURED_ZERO_API_DRY_REQUEST"
            else:
                items = [event["params"]["item"] for event in rpc.events if event.get("method") == "item/completed"]
                calls = [item for item in items if item.get("type") == "mcpToolCall"]
                result["model_selected_mcp_calls"] = calls
                result["model_korean_explanation"] = "\n".join(item.get("text", "") for item in items if item.get("type") == "agentMessage")
                returned = [base.structured_tool_result(item) for item in calls]
                run_ids = {item["run_id"] for item in returned if item.get("run_id")}
                if len(run_ids) == 1:
                    result["independently_retrieved_service_run"] = base.ServiceProxy().request("GET", "/api/runs/" + next(iter(run_ids)))
                names = {item.get("tool") for item in calls}
                sentences = [part for part in re.split(r"(?<=[.!?。！？])(?:\s+|$)", result["model_korean_explanation"]) if part.strip()]
                result["explanation_sentence_count"] = len(sentences)
                run = result.get("independently_retrieved_service_run", {})
                result["checks"] = {
                    "configuration_and_group_selected_across_case": "read_group" in names and ("prepare_setup" in names or continuation is not None),
                    "tools_completed_within_scope": bool(calls) and names <= base.ALLOWED_TOOLS and all(item.get("status") == "completed" for item in calls),
                    "codex_turn_completed": result["turn"]["status"] == "completed",
                    "concise_korean_explanation": 1 <= len(sentences) <= 5 and any("가" <= char <= "힣" for char in result["model_korean_explanation"]),
                    "service_run_correlated": run.get("mode") == "mcp_host" and run.get("facility_id") == "learning-b" and "read_group" in {item["name"] for item in run.get("tool_calls", [])},
                }
                result["status"] = "OBSERVED_COMPLETE_FOCUSED_CONFIGURATION_CASE" if all(result["checks"].values()) else "INCOMPLETE_FOCUSED_CONFIGURATION_CASE"
        except Exception as error:
            result.update(status="INCOMPLETE_FOCUSED_CONFIGURATION_CASE", error={"type": type(error).__name__, "message": str(error)[:1000]})
        finally:
            if rpc:
                result["host_events"] = [event for event in rpc.events if event.get("method") in ("item/started", "item/completed", "turn/completed", "error") or "id" in event]
                result["host_approval_decisions"] = rpc.approval_decisions
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
    result.update(provider_requests=proxy.records, provider_calls=proxy.calls, case_tokens_charged=proxy.charged,
                  context_transformations=transformations,
                  shared_budget_after=proxy.budget.snapshot(), case_scope_after=case_scope_snapshot(),
                  test_process_stopped=not process or process.returncode is not None,
                  independent_review_required=True)
    result = base.safe(result, proxy.secrets)
    (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result, folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--continue-from", type=Path, help="Attach an exact, attributed actual setup result from this same case; starts a new chat, not forged tool history")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result, folder = asyncio.run(execute(args.live, args.continue_from))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "provider_calls": result["provider_calls"], "error": result.get("error"),
                      "requests": [{key: item.get(key) for key in ("payload_bytes", "conservative_reserved_tokens", "forwarded", "reason")} for item in result["provider_requests"]],
                      "case_scope_after": result["case_scope_after"], "local_result": str(folder.relative_to(ROOT) / "result.json")}, ensure_ascii=False))
    raise SystemExit(0 if result["status"].startswith(("CAPTURED", "OBSERVED")) else 1)


if __name__ == "__main__":
    main()
