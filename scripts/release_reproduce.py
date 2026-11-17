#!/usr/bin/env python3
"""Install and exercise a separate checkout, HTTPS CSE and service lifecycle.

No model calls or existing service/CSE restarts. Dependency caches may be reused;
both Python environments, CSE database and application store are newly created.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-port", type=int, default=8179)
    parser.add_argument("--cse-port", type=int, default=8643)
    parser.add_argument("--output", type=Path, default=Path("evidence/release/clean-lifecycle.json"))
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    checkout = source / ".runtime" / ("lifecycle-" + uuid.uuid4().hex[:8]) / "checkout"
    checkout.mkdir(parents=True)
    for name in ("src", "profiles", "schemas", "config", "scenarios", "web", "plugin", "scripts", "deploy", "docs"):
        shutil.copytree(source / name, checkout / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("pyproject.toml", "uv.lock", "README.md", "LICENSE", "LICENSE-CONTENT"):
        if (source / name).is_file():
            shutil.copy2(source / name, checkout / name)
    env = {k: v for k, v in os.environ.items() if not k.startswith("OPENSOOM_") and not any(s in k for s in ("API_KEY", "TOKEN", "SECRET"))}
    evidence = {"status": "RUNNING", "isolation": "new source copy, two new Python environments, new HTTPS CSE database and application store",
                "ports": {"api": args.api_port, "cse_https": args.cse_port}, "model_calls": 0,
                "physical_devices": "simulated", "steps": [], "source_cli_sha256": hashlib.sha256((source / "src/opensoom/cli.py").read_bytes()).hexdigest()}
    main_record = source / ".runtime/service-process.json"
    main_pid = json.loads(main_record.read_text()).get("pid") if main_record.exists() else None
    python = checkout / ".venv/bin/python"
    def run(label, command, *, extra=None, expected=0, timeout=120):
        process = subprocess.run([str(v) for v in command], cwd=checkout, env={**env, **(extra or {})},
                                 capture_output=True, text=True, timeout=timeout)
        text = (process.stdout + process.stderr)[-5000:]
        evidence["steps"].append({"label": label, "command": [str(v) for v in command], "exit_status": process.returncode, "output": text})
        if process.returncode != expected:
            raise RuntimeError(f"{label} returned {process.returncode}, expected {expected}")
        return process.stdout
    def ready(label):
        deadline = time.monotonic() + 25
        last = None
        while time.monotonic() < deadline:
            process = subprocess.run([str(python), "-m", "opensoom.cli", "doctor"], cwd=checkout, env=env, capture_output=True, text=True, timeout=8)
            last = process.stdout
            if process.returncode == 0:
                data = json.loads(last)
                if data["cse"]["base"] != "cse-secure" or data["service"]["port"] != args.api_port:
                    raise RuntimeError("Saved secure endpoint or port was not used")
                evidence["steps"].append({"label": label, "command": ["opensoom", "doctor"], "exit_status": 0, "result": data})
                return
            time.sleep(0.4)
        raise RuntimeError(f"{label} did not become ready: {last}")
    service_started = cse_started = False
    try:
        cache = source / "tmp/uv-cache"
        (checkout / "tmp").mkdir()
        (checkout / "tmp/uv-cache").symlink_to(cache, target_is_directory=True)
        run("install_application", ["uv", "--cache-dir", cache, "sync", "--frozen", "--python", "python3.12"])
        run("install_cse", [python, "scripts/cse_runtime.py", "install"], timeout=180)
        run("start_isolated_https_cse", [python, "scripts/cse_runtime.py", "start", "--name", "secure", "--port", args.cse_port], timeout=60)
        cse_started = True
        run("validate_profiles_and_registry", [python, "-m", "opensoom.cli", "validate"])
        config_env = {"OPENSOOM_CSE_URL": f"https://127.0.0.1:{args.cse_port}", "OPENSOOM_CSE_BASE": "cse-secure",
                      "OPENSOOM_CSE_CA": str(checkout / ".runtime/pki/ca.crt"), "OPENSOOM_MQTT_HOST": ""}
        run("before_start_diagnostic", [python, "-m", "opensoom.cli", "doctor", "--port", args.api_port], extra=config_env, expected=1)
        run("start_secure", [python, "-m", "opensoom.cli", "start", "--secure", "--port", args.api_port], extra=config_env)
        service_started = True
        ready("doctor_without_original_environment")
        runtime = checkout / ".runtime"
        credentials = json.loads((runtime / "service-credentials.json").read_text())
        with httpx.Client(base_url=f"http://127.0.0.1:{args.api_port}", headers={"Authorization": "Bearer " + credentials["operator_token"]}, timeout=15, trust_env=False) as client:
            response = client.post("/api/tools/read_evidence", json={"arguments": {"facility_id": "food-a"}})
            response.raise_for_status()
            data = response.json()
            evidence["diagnosis"] = {"status": data["status"], "zones": [{"id": z["id"], "status": z["status"]} for z in data["zones"]]}
        run("fixture_recovery", [python, "-m", "opensoom.llm_runner", "--mode", "fixture", "--facility", "food-a", "--scenario", "exhaust_fault", "--expect", "recovered", "--prepare-scenario", "--output", runtime / "fixture.json"], extra={"OPENSOOM_SERVICE_URL": f"http://127.0.0.1:{args.api_port}", "OPENSOOM_PROJECT_DIR": str(checkout)})
        fixture = json.loads((runtime / "fixture.json").read_text())
        evidence["fixture"] = {k: fixture.get(k) for k in ("id", "outcome", "trace_verification", "service_verification")}
        run("seed_budget_preservation_check", [python, "-c", "from opensoom.llm_budget import SharedBudget,BudgetLimits; b=SharedBudget('.runtime/llm-budget.sqlite',BudgetLimits('isolated-lifecycle-test-no-model-calls',1,1)); b.reserve('sentinel','test',1); print(b.snapshot())"])
        budget_before = hashlib.sha256((runtime / "llm-budget.sqlite").read_bytes()).hexdigest()
        config_before = json.loads((runtime / "service-config.json").read_text())
        run("stop", [python, "-m", "opensoom.cli", "stop"])
        service_started = False
        run("stopped_diagnostic", [python, "-m", "opensoom.cli", "doctor"], expected=1)
        run("start_without_flags_or_environment", [python, "-m", "opensoom.cli", "start"])
        service_started = True
        ready("doctor_after_stop_start")
        run("restart_without_flags_or_environment", [python, "-m", "opensoom.cli", "restart"])
        ready("doctor_after_restart")
        run("cleanup_running_service", [python, "-m", "opensoom.cli", "cleanup"])
        service_started = False
        evidence["cleanup"] = {"operations_removed": not (runtime / "operations.sqlite").exists(),
                               "credentials_removed": not (runtime / "service-credentials.json").exists(),
                               "process_record_removed": not (runtime / "service-process.json").exists(),
                               "configuration_preserved": json.loads((runtime / "service-config.json").read_text()) == config_before,
                               "budget_preserved": hashlib.sha256((runtime / "llm-budget.sqlite").read_bytes()).hexdigest() == budget_before}
        if not all(evidence["cleanup"].values()):
            raise RuntimeError("Cleanup did not satisfy the preservation contract")
        run("cse_survives_service_cleanup", [python, "scripts/cse_runtime.py", "status", "--name", "secure"])
        evidence["status"] = "PASS_ISOLATED_LIFECYCLE"
    except Exception as exc:
        evidence.update(status="FAIL", error=str(exc), error_type=type(exc).__name__)
    finally:
        # A startup error can occur after a process record was created. Always
        # attempt only this checkout's recorded processes and retain a failure
        # report even if one of those processes refuses to stop.
        cleanup_commands = []
        if service_started or (checkout / ".runtime/service-process.json").exists():
            cleanup_commands.append(("finally_stop_service", [python, "-m", "opensoom.cli", "stop"]))
        if cse_started or (checkout / ".runtime/cse-secure/process.json").exists():
            cleanup_commands.append(("stop_isolated_cse", [python, "scripts/cse_runtime.py", "stop", "--name", "secure"]))
        for label, command in cleanup_commands:
            try:
                run(label, command)
            except Exception as exc:
                evidence["status"] = "FAIL"
                evidence.setdefault("cleanup_errors", []).append({"step": label, "error": str(exc)})
        evidence["main_service_record_unchanged"] = (json.loads(main_record.read_text()).get("pid") if main_record.exists() else None) == main_pid
        evidence["scope_note"] = "CLI/application onboarding and HTTPS CSE lifecycle; MQTT binding and Codex desktop UI are separate checks. The budget sentinel is synthetic and performs no provider request."
        content = json.dumps(evidence, ensure_ascii=False, indent=2).replace(str(checkout), "<isolated-checkout>").replace(str(source), "<source-checkout>").replace(str(Path.home()), "<user-home>")
        output = args.output if args.output.is_absolute() else source / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content + "\n")
    print(json.dumps({"status": evidence["status"], "steps": len(evidence["steps"]), "error": evidence.get("error"), "main_service_record_unchanged": evidence["main_service_record_unchanged"]}))
    raise SystemExit(0 if evidence["status"].startswith("PASS") else 1)


if __name__ == "__main__":
    main()
