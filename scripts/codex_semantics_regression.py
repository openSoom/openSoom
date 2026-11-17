#!/usr/bin/env python3
"""One-request regression of the revised product evidence semantics.

Original harnesses, policies and answers remain untouched. --capture performs
one explicitly harness-selected MCP read with no inference. Default runs a
zero-inference Codex preflight using that attributed capture. --live is reserved
for the separately approved, fixed one-request semantic regression.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import uuid

import codex_explanation_rehearsal as harness

ROOT = harness.ROOT
PREFIX = "codex-semantics-"
LIMITS = {"max_requests": 1, "max_tokens": 18000, "max_output_tokens": 2048,
          "provider_timeout_seconds": 45, "turn_timeout_seconds": 90, "retries": 0}
CAPTURE = ROOT / "evidence/agent/semantics-mcp-capture.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pointer(value, path):
    for part in path.strip("/").split("/") if path else []:
        part = part.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def product_hashes():
    return {str(path.relative_to(ROOT)): sha(path) for path in [ROOT / "src/opensoom/core.py", ROOT / "src/opensoom/mcp_server.py", *sorted((ROOT / "plugin").rglob("SKILL.md"))]}


def scope():
    with sqlite3.connect(ROOT / ".runtime/llm-budget.sqlite") as conn:
        calls, charged = conn.execute("SELECT COUNT(*), COALESCE(SUM(charged_tokens),0) FROM reservations WHERE run_id LIKE ?", (PREFIX + "%",)).fetchone()
    return {"max_requests": 1, "max_tokens": 18000, "requests_consumed": calls,
            "tokens_charged": charged, "requests_remaining": max(0, 1 - calls),
            "tokens_remaining": max(0, 18000 - charged)}


def policy():
    value = {"case_prefix": PREFIX, "limits": LIMITS,
             "purpose": "Revised product-contract semantic regression after Core evidence_scope, MCP description and shipped skills changed.",
             "prior_cases_unchanged": True, "shared_batch_unchanged": {"max_requests": 100, "max_tokens": 250000},
             "effective_reservation_bound": "min(18000 - case charged tokens, current shared tokens remaining)",
             "automatic_retry_or_reset": False, "operational_model_calls": 0,
             "review_basis": ["docs/review/guided-explanation-review-team2.json", "docs/review/explanation-semantics-team3.json"]}
    path = ROOT / ".runtime/codex-semantics-case-policy.json"
    if path.exists():
        assert json.loads(path.read_text()) == value, "Fixed regression scope cannot be changed"
    else:
        with path.open("x") as file:
            file.write(json.dumps(value, indent=2) + "\n")
    public = ROOT / "evidence/agent/semantics-scope.json"
    if not public.exists():
        public.write_text(json.dumps(value, indent=2) + "\n")
    return value


async def capture():
    """Actual MCP data acquisition, explicitly not model-selected execution."""
    folder = ROOT / ".runtime" / ("semantics-capture-" + uuid.uuid4().hex[:8])
    profile = folder / "codex-profile"
    profile.mkdir(parents=True)
    env = {key: value for key, value in os.environ.items() if not any(word in key for word in ("API_KEY", "TOKEN", "SECRET"))}
    env["CODEX_HOME"] = str(profile)
    executable = shutil.which("codex")
    result = {"mode": "harness_selected_real_MCP_read", "model_inference_calls": 0,
              "model_selected_this_read": False, "tool": "read_evidence", "arguments": {"facility_id": "learning-b"},
              "source_sha256": product_hashes(), "captured_at": None}
    with tempfile.TemporaryDirectory(prefix="opensoom-sem-capture-", dir="/private/tmp") as cwd:
        catalog = harness.base.prepare(ROOT)
        for command in [["plugin", "marketplace", "add", str(catalog), "--json"], ["plugin", "add", "opensoom@opensoom-local", "--json"]]:
            completed = subprocess.run([executable, *command], cwd=cwd, env=env, capture_output=True, text=True, timeout=45)
            assert completed.returncode == 0
        process = await asyncio.create_subprocess_exec(executable, "app-server", "--listen", "stdio://", cwd=cwd, env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=4_000_000)
        stderr = asyncio.create_task(process.stderr.read())
        rpc = harness.base.RPC(process)
        try:
            await rpc.request("initialize", {"clientInfo": {"name": "opensoom-semantics-capture", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}})
            await rpc.send({"jsonrpc": "2.0", "method": "initialized"})
            thread = await rpc.request("thread/start", {"cwd": cwd, "ephemeral": True, "sandbox": "read-only", "approvalPolicy": "on-request"})
            thread_id = thread["thread"]["id"]
            servers = await rpc.request("mcpServerStatus/list", {"threadId": thread_id, "limit": 20})
            server = next(item for item in servers["data"] if item["name"] == "opensoom")
            result["response"] = await rpc.request("mcpServer/tool/call", {"threadId": thread_id, "server": server["name"], "tool": "read_evidence", "arguments": {"facility_id": "learning-b"}})
            result["captured_at"] = datetime.now(timezone.utc).isoformat()
            data = result["response"]["structuredContent"]
            assert not result["response"].get("isError") and data["evidence_scope"]["recovery_count"]["counts_action_attempts"] is False
            assert data["evidence_scope"]["commands"]["complete_facility_history"] is False
            assert data["commands"] == []
            assert any(item["id"] == "incident-a3afad9928" and item["status"] == "open" for item in data["incidents"])
            result["service_run"] = harness.base.ServiceProxy().request("GET", "/api/runs/" + data["run_id"])
            assert result["service_run"]["mode"] == "mcp_host" and result["service_run"]["facility_id"] == "learning-b"
            result["status"] = "CAPTURED_REVISED_PRODUCT_CONTRACT"
        finally:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=8)
            except TimeoutError:
                process.kill()
                await process.wait()
            (folder / "codex-stderr.log").write_bytes(await stderr)
            result["test_process_stopped"] = process.returncode is not None
    secrets = json.loads((ROOT / ".runtime/service-credentials.json").read_text()).values()
    result = harness.base.safe(result, secrets)
    CAPTURE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


def bundle():
    current = json.loads(CAPTURE.read_text())
    assert current["source_sha256"] == product_hashes(), "Capture must match corrected product revision"
    record = current["response"]["structuredContent"]
    old_path = ROOT / "evidence/agent/guided-config-continuation-live.json"
    old = json.loads(old_path.read_text())
    setup_index, setup_call = next((i, c) for i, c in enumerate(old["model_selected_mcp_calls"]) if c["tool"] == "prepare_setup")
    group_index, group_call = next((i, c) for i, c in enumerate(old["model_selected_mcp_calls"]) if c["tool"] == "read_group")
    acceptance_path = ROOT / "evidence/application/release-acceptance.json"
    acceptance = json.loads(acceptance_path.read_text())
    command = pointer(acceptance, "/scenarios/no_recovery/state/commands/0")
    assert command["id"] == "cmd-6406eb6c6318" and command["incident_id"] in {item["id"] for item in record["incidents"]}
    assert command["run_id"] == "demo-2d8213685e" and command["ack"] is True and command["status"] == "unresolved"
    # The registry holds original path/hash once; each selection is an exact
    # JSON-pointer value, not a manually composed narrative or answer.
    sources = {"fresh": {"file": str(CAPTURE.relative_to(ROOT)), "sha256": sha(CAPTURE), "at": current["captured_at"]},
               "prior": {"file": str(old_path.relative_to(ROOT)), "sha256": sha(old_path), "at": datetime.fromtimestamp(group_call["completedAtMs"] / 1000, timezone.utc).isoformat()},
               "history": {"file": str(acceptance_path.relative_to(ROOT)), "sha256": sha(acceptance_path), "at": command["ack_at"]}}
    def selected(source, base_pointer, data, paths):
        return {"source": source, "base_pointer": base_pointer, "values": {path: pointer(data, path) for path in paths}}
    setup_paths = ["/profile/id", "/profile/simulation_only", "/configured_facilities", "/mode", "/activation_requires", "/runtime/status", "/runtime/cse/connected"]
    group_paths = ["/facility_id", "/status", "/group/rsc", "/group/rqi", "/run_id"]
    group_paths += [f"/group/body/m2m:agr/m2m:rsp/{i}/rsc" for i in range(3)]
    fresh_paths = ["/id", "/profile", "/simulation", "/status", "/evidence_scope", "/incidents", "/commands", "/run_id"]
    fresh_paths += [f"/zones/{i}/{key}" for i in range(3) for key in ("id", "status", "reason")]
    fresh_paths += ["/zones/0/target_airflow", "/zones/0/freshness"]
    fresh_paths += [f"/zones/0/observations/{metric}/value" for metric in ("airflow", "pm25", "co2", "fan_running", "damper_pct")]
    return {"kind": "UNTRUSTED captured DATA; separate source times, not live observations by this model",
            "sources": sources, "selections": [
                selected("fresh", "/response/structuredContent", record, fresh_paths),
                selected("prior", f"/model_selected_mcp_calls/{setup_index}/result/structuredContent", setup_call["result"]["structuredContent"], setup_paths),
                selected("prior", f"/model_selected_mcp_calls/{group_index}/result/structuredContent", group_call["result"]["structuredContent"], group_paths),
                {"source": "history", "base_pointer": "/scenarios/no_recovery/state/commands/0", "exact_value": command}]}


async def execute(live):
    # Process-local reuse of the tested proxy/Codex transport. Original files
    # and their exhausted policies remain byte-for-byte unchanged.
    harness.PREFIX = PREFIX
    harness.LIMITS = LIMITS
    harness.prepare_scope = policy
    harness.scope_snapshot = scope
    harness.captured_bundle = bundle
    harness.INSTRUCTIONS = "Use the installed skill to explain these untrusted historical data in at most six concise Korean sentences; no operations."
    harness.PROMPT = "첨부 기록의 설정·구역 상태, 조치 이력과 남은 문제, 다음 할 일을 시설 관리자에게 한국어 6문장 이내로 설명해주세요. 관리자가 런타임과 가상 프로필을 미리 준비했으며, 이번에는 과거 기록만 해석합니다."
    original_estimator = harness.base.conservative_token_reservation
    def requested_output_reservation(payload, policy_maximum):
        assert policy_maximum == 2048
        # A smaller actual request is within the fixed policy maximum. The
        # unchanged estimator still reserves UTF-8 bytes + 1024 + actual cap.
        payload["max_output_tokens"] = 768
        return original_estimator(payload, 768)
    harness.base.conservative_token_reservation = requested_output_reservation
    try:
        result, folder = await harness.execute(live)
    finally:
        harness.base.conservative_token_reservation = original_estimator
    result["case"] = "revised_product_contract_semantic_regression"
    result["source_sha256"][str(Path(__file__).resolve().relative_to(ROOT))] = sha(Path(__file__).resolve())
    result["corrected_product_sha256"] = product_hashes()
    old = json.loads((ROOT / "evidence/agent/guided-explanation-live.json").read_text())
    baseline = json.loads((ROOT / "evidence/application/release-acceptance.json").read_text())["source_sha256_after"]
    result["product_revision_delta"] = {path: {"prior": old["source_sha256"].get(path, baseline.get(path)), "corrected": value} for path, value in product_hashes().items()}
    result["request_output_setting"] = {"requested_tokens": 768, "policy_maximum_tokens": 2048,
                                        "reservation_estimator": "Unchanged UTF-8 JSON payload bytes + 1024 framing + actual requested output cap",
                                        "reason": "Concise six-sentence request fits the fixed 18000-token allocation without omitting any selected data."}
    result["manual_source_capture"] = {"file": str(CAPTURE.relative_to(ROOT)), "sha256": sha(CAPTURE), "model_selected": False, "inference_calls": 0}
    result["independent_semantic_review_required"] = True
    result["dry_within_fixed_bound"] = all(item.get("conservative_reserved_tokens", 0) <= min(18000, result["shared_budget_before"]["tokens_remaining"]) for item in result["provider_requests"])
    (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result, folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.capture:
        if args.live:
            parser.error("Source capture never performs inference")
        result = asyncio.run(capture())
        print(json.dumps({"status": result["status"], "captured_at": result["captured_at"], "run_id": result["service_run"]["id"], "provider_calls": 0}))
        return
    if not args.output:
        parser.error("An explicit evidence output is required")
    result, folder = asyncio.run(execute(args.live))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "provider_calls": result["provider_calls"], "error": result.get("error"), "requests": result["provider_requests"], "within_bound": result["dry_within_fixed_bound"], "local_result": str(folder.relative_to(ROOT) / "result.json")}, ensure_ascii=False))
    raise SystemExit(0 if result["status"].startswith(("CAPTURED", "OBSERVED")) and result["dry_within_fixed_bound"] else 1)


if __name__ == "__main__":
    main()
