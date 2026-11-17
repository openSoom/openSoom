#!/usr/bin/env python3
"""Lossless, measurement-complete captured-record regression; dry by default."""
from __future__ import annotations

import argparse
import ast
import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import codex_explanation_rehearsal as harness

ROOT = harness.ROOT
PREFIX = "codex-units-"
LIMITS = {"max_requests": 1, "max_tokens": 14000, "max_output_tokens": 2048,
          "provider_timeout_seconds": 45, "turn_timeout_seconds": 90, "retries": 0}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get(value, path):
    for part in path.strip("/").split("/") if path else []:
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def put(root, path, value):
    parts = path.strip("/").split("/")
    current = root
    for i, part in enumerate(parts[:-1]):
        following_is_index = parts[i + 1].isdigit()
        if isinstance(current, list):
            index = int(part)
            while len(current) <= index:
                current.append(None)
            if current[index] is None:
                current[index] = [] if following_is_index else {}
            current = current[index]
        else:
            current = current.setdefault(part, [] if following_is_index else {})
    last = parts[-1]
    if isinstance(current, list):
        index = int(last)
        while len(current) <= index:
            current.append(None)
        current[index] = copy.deepcopy(value)
    else:
        current[last] = copy.deepcopy(value)


def prepare_packet():
    original_path = ROOT / "evidence/agent/semantics-live.json"
    original = json.loads(original_path.read_text())["input_provenance"]
    packet, mappings = {}, []
    for selection, label in zip(original["selections"], ("revised_evidence", "prior_setup", "prior_group", "prior_command")):
        source = original["sources"][selection["source"]]
        source_path = ROOT / source["file"]
        assert sha(source_path) == source["sha256"]
        full = json.loads(source_path.read_text())
        source_value = get(full, selection["base_pointer"])
        data = {} if "values" in selection else copy.deepcopy(selection["exact_value"])
        pairs = selection.get("values", {"": selection.get("exact_value")})
        for path, value in pairs.items():
            assert get(source_value, path) == value
            if path:
                put(data, path, value)
            mappings.append({"source_file": source["file"], "source_sha256": source["sha256"],
                             "source_pointer": selection["base_pointer"] + path,
                             "packet_pointer": "/" + label + "/data" + path})
        if label == "revised_evidence":
            captured_at = full["captured_at"]
        elif label in {"prior_setup", "prior_group"}:
            index = int(selection["base_pointer"].split("/")[2])
            captured_at = datetime.fromtimestamp(full["model_selected_mcp_calls"][index]["completedAtMs"] / 1000, timezone.utc).isoformat()
        else:
            captured_at = full["completed_at"]
        packet[label] = {"captured_at": captured_at, "data": data}

    capture_path = ROOT / "evidence/agent/semantics-mcp-capture.json"
    capture = json.loads(capture_path.read_text())
    observations = capture["response"]["structuredContent"]["zones"][0]["observations"]
    for metric in ("airflow", "pm25", "co2", "fan_running", "damper_pct"):
        obj = observations[metric]
        assert {"value", "unit", "observed_at", "received_at", "source", "quality"} <= set(obj)
        assert obj["unit"] and obj["observed_at"] and obj["received_at"]
        packet["revised_evidence"]["data"]["zones"][0]["observations"][metric] = copy.deepcopy(obj)
        mappings.append({"source_file": str(capture_path.relative_to(ROOT)), "source_sha256": sha(capture_path),
                         "source_pointer": "/response/structuredContent/zones/0/observations/" + metric,
                         "packet_pointer": "/revised_evidence/data/zones/0/observations/" + metric,
                         "restoration": "Entire original metric object; no value conversion or invented unit"})

    core_path = ROOT / "src/opensoom/core.py"
    units = next(ast.literal_eval(node.value) for node in ast.parse(core_path.read_text()).body
                 if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "UNITS" for target in node.targets))
    assert units["airflow"] == observations["airflow"]["unit"]
    packet["revised_evidence"]["data"]["zones"][0]["target_airflow_unit"] = units["airflow"]
    packet["prior_command"]["data"]["value_unit"] = units["damper_pct"]
    assert packet["prior_command"]["data"]["action"] == "set_damper"

    for mapping in mappings:
        original_source = json.loads((ROOT / mapping["source_file"]).read_text())
        # The historical complete command receives an additive canonical-unit
        # qualifier. Every original command attribute remains identical.
        expected = get(original_source, mapping["source_pointer"])
        actual = get(packet, mapping["packet_pointer"])
        if mapping["packet_pointer"] == "/prior_command/data":
            assert {key: actual[key] for key in expected} == expected
        else:
            assert actual == expected
    packet_path = ROOT / "evidence/agent/units-model-packet.json"
    compact = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
    packet_path.write_text(compact + "\n")
    manifest = {"purpose": "Correct the documented lossy measurement projection; all old cases remain unchanged.",
                "source_packet": str(original_path.relative_to(ROOT)), "source_packet_sha256": sha(original_path),
                "original_source_registry": original["sources"], "packet_file": str(packet_path.relative_to(ROOT)),
                "packet_sha256": sha(packet_path), "model_packet_bytes": len(compact.encode()),
                "all_previously_selected_values_preserved": True, "original_to_packet_mappings": mappings,
                "all_five_measurements_restored_exactly": True,
                "canonical_unit_associations": {"source_file": str(core_path.relative_to(ROOT)), "source_sha256": sha(core_path),
                    "AST_constant": "UNITS", "target_airflow": {"key": "airflow", "value": units["airflow"]},
                    "set_damper_value": {"key": "damper_pct", "value": units["damper_pct"]},
                    "meaning": "Canonical target/command unit associations from the existing product, no conversion."},
                "timestamps": "Each model-facing captured_at is the original capture completion; observation and ACK event timestamps remain in their exact objects.",
                "forensic_provenance_outside_provider_payload": True, "no_prior_answer_or_fake_chat_history": True}
    (ROOT / "evidence/agent/units-input-map.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return packet


def scope():
    with sqlite3.connect(ROOT / ".runtime/llm-budget.sqlite") as conn:
        calls, charged = conn.execute("SELECT COUNT(*), COALESCE(SUM(charged_tokens),0) FROM reservations WHERE run_id LIKE ?", (PREFIX + "%",)).fetchone()
    return {"max_requests": 1, "max_tokens": 14000, "requests_consumed": calls, "tokens_charged": charged,
            "requests_remaining": max(0, 1 - calls), "tokens_remaining": max(0, 14000 - charged)}


def policy():
    value = {"case_prefix": PREFIX, "limits": LIMITS, "requested_output_tokens": 768,
             "purpose": "Measurement-complete corrected-input regression, not retry/reset of any prior case.",
             "sandbox": "read-only", "approval_policy": "never", "operational_tools": 0,
             "stricter_policy_rationale": "The isolated explanation turn cannot request escalation; ordinary Codex-generated restrictions are preserved verbatim. No outside-sandbox execution is allowed.",
             "disabled_unrelated_builtin_skills": ["imagegen", "openai-docs", "skill-creator", "skill-installer"],
             "shipped_opensoom_setup_skill": "installed and selected unchanged",
             "shared_budget_unchanged": {"max_requests": 100, "max_tokens": 250000},
             "effective_reservation_bound": "min(14000 - case charged tokens, actual remaining shared tokens)",
             "automatic_retry_or_reset": False}
    path = ROOT / ".runtime/codex-units-case-policy.json"
    if path.exists():
        assert json.loads(path.read_text()) == value
    else:
        with path.open("x") as handle:
            handle.write(json.dumps(value, indent=2) + "\n")
    public = ROOT / "evidence/agent/units-scope.json"
    if not public.exists():
        public.write_text(json.dumps(value, indent=2) + "\n")
    return value


async def execute(live):
    changes = []
    original_rpc = harness.base.RPC
    class StrictRPC(original_rpc):
        async def request(self, method, params):
            if method == "thread/start":
                for name in ("imagegen", "openai-docs", "skill-creator", "skill-installer"):
                    response = await super().request("skills/config/write", {"name": name, "enabled": False})
                    assert response["effectiveEnabled"] is False
                    changes.append({"method": "skills/config/write", "name": name, "enabled": False, "profile_scope": "fresh isolated child CODEX_HOME"})
                params = {**params, "sandbox": "read-only", "approvalPolicy": "never"}
            return await super().request(method, params)
    harness.base.RPC = StrictRPC
    harness.PREFIX, harness.LIMITS = PREFIX, LIMITS
    harness.prepare_scope, harness.scope_snapshot, harness.captured_bundle = policy, scope, prepare_packet
    harness.INSTRUCTIONS = "Use the installed skill to interpret these historical records in at most six concise Korean sentences; no operations."
    harness.PROMPT = "관리자가 미리 준비한 가상 openSoom의 첨부 기록을 해석해 설정·구역 상태, 조치 이력·남은 문제와 다음 할 일을 한국어 6문장 이내로 설명해주세요. 이번에는 과거 기록만 해석합니다."
    original_estimator = harness.base.conservative_token_reservation
    def reservation(payload, maximum):
        assert maximum == 2048
        payload["max_output_tokens"] = 768
        return original_estimator(payload, 768)
    harness.base.conservative_token_reservation = reservation
    try:
        result, folder = await harness.execute(live)
    finally:
        harness.base.RPC = original_rpc
        harness.base.conservative_token_reservation = original_estimator
    result["case"] = "measurement_complete_corrected_input_regression"
    result["isolated_profile_changes"] = changes
    result["input_map_sha256"] = sha(ROOT / "evidence/agent/units-input-map.json")
    result["source_sha256"][str(Path(__file__).resolve().relative_to(ROOT))] = sha(Path(__file__).resolve())
    result["requested_output_tokens"] = 768
    result["policy_maximum_output_tokens"] = 2048
    payload = json.loads((folder / "request-1.json").read_text())
    permissions = [part["text"] for message in payload["input"] for part in message.get("content", []) if "<permissions instructions>" in part.get("text", "")]
    result["official_generated_permission_instructions"] = permissions
    result["reservation_within_fixed_bound"] = all(item.get("conservative_reserved_tokens", 0) <= min(14000, result["shared_budget_before"]["tokens_remaining"]) for item in result["provider_requests"])
    result["independent_fact_review_required"] = True
    (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result, folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result, folder = asyncio.run(execute(args.live))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "provider_calls": result["provider_calls"], "error": result.get("error"), "requests": result["provider_requests"], "within_bound": result["reservation_within_fixed_bound"], "generated_permissions": result["official_generated_permission_instructions"], "local_result": str(folder.relative_to(ROOT) / "result.json")}, ensure_ascii=False))
    raise SystemExit(0 if result["status"].startswith(("CAPTURED", "OBSERVED")) and result["reservation_within_fixed_bound"] else 1)


if __name__ == "__main__":
    main()
