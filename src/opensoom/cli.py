from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.parse import urlparse

import httpx

from .core import Core, ROOT

RUNTIME_KEYS = ("OPENSOOM_CSE_URL", "OPENSOOM_CSE_BASE", "OPENSOOM_CSE_CA", "OPENSOOM_MQTT_HOST", "OPENSOOM_MQTT_PORT", "OPENSOOM_MQTT_CSE_ID", "OPENSOOM_NOTIFY_URL", "OPENSOOM_RUNTIME_DIR", "OPENSOOM_FACILITY_IDS", "OPENSOOM_CENTRAL_ORIGIN")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def resolve_config(root: Path, saved: dict, environment: dict, port: int | None, secure: bool) -> dict:
    """Persist declared runtime settings only, never provider/service secrets."""
    values = {k: str(v) for k, v in saved.get("environment", {}).items() if k in RUNTIME_KEYS}
    if secure:
        values.update(OPENSOOM_CSE_URL="https://127.0.0.1:8443", OPENSOOM_CSE_BASE="cse-secure", OPENSOOM_CSE_CA=str(root / ".runtime/pki/ca.crt"), OPENSOOM_MQTT_HOST="127.0.0.1", OPENSOOM_MQTT_PORT="8883", OPENSOOM_MQTT_CSE_ID="opensoom-secure")
    values.update({k: environment[k] for k in RUNTIME_KEYS if k in environment})
    chosen_port = port if port is not None else int(saved.get("port", 8090))
    if not 1 <= chosen_port <= 65535:
        raise ValueError("Service port must be between 1 and 65535")
    old_default = f"http://127.0.0.1:{saved.get('port', 8090)}/api/notify"
    if "OPENSOOM_NOTIFY_URL" not in values or (port is not None and values["OPENSOOM_NOTIFY_URL"] == old_default and "OPENSOOM_NOTIFY_URL" not in environment):
        values["OPENSOOM_NOTIFY_URL"] = f"http://127.0.0.1:{chosen_port}/api/notify"
    for key in ("OPENSOOM_CSE_URL", "OPENSOOM_NOTIFY_URL"):
        parsed = urlparse(values.get(key, ""))
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(f"{key} must not contain credentials, query parameters or fragments")
    return {"version": 1, "port": chosen_port, "environment": values}


def process_info(pid: int, root: Path) -> tuple[bool, bool]:
    """Return running/owned; zombies are exited, unrelated PIDs are untouched."""
    result = subprocess.run(["ps", "-p", str(pid), "-o", "stat=", "-o", "command="], capture_output=True, text=True)
    content = result.stdout.strip()
    if result.returncode or not content or content.split()[0].startswith("Z"):
        return False, False
    proc_cwd = Path(f"/proc/{pid}/cwd")
    if proc_cwd.exists():
        owned_cwd = proc_cwd.resolve() == root.resolve()
    else:
        cwd = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True, text=True)
        owned_cwd = "n" + str(root.resolve()) in cwd.stdout.splitlines()
    return True, owned_cwd and " -m opensoom.cli serve" in content


def stop_service(pidfile: Path, root: Path, timeout: float = 20) -> None:
    if not pidfile.exists():
        return
    pid = int(read_json(pidfile)["pid"])
    running, owned = process_info(pid, root)
    if running and not owned:
        raise RuntimeError("Recorded PID no longer belongs to this openSoom checkout; refusing to stop it")
    if running:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            running, owned = process_info(pid, root)
            if not running:
                break
            # During teardown ps can still see a process after its cwd has
            # disappeared. Do not signal again or treat that transient state
            # as successful exit; wait until dead or retain the record on timeout.
            time.sleep(0.1)
        else:
            raise RuntimeError("Service did not stop within the deadline; process record retained and cleanup cancelled")
    pidfile.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(prog="opensoom")
    parser.add_argument("command", choices=["serve", "start", "stop", "restart", "doctor", "validate", "cleanup"])
    parser.add_argument("--port", type=int, help="Reuse saved port unless explicitly overridden; first-start default is 8090")
    parser.add_argument("--secure", action="store_true", help="Use bundled HTTPS/native MQTT-TLS defaults; explicit runtime environment overrides remain effective")
    args = parser.parse_args()
    control = ROOT / ".runtime"
    control.mkdir(exist_ok=True)
    pidfile, configfile = control / "service-process.json", control / "service-config.json"
    previous = read_json(pidfile)
    # Upgrade before stop removes a legacy PID file containing secure settings.
    if not configfile.exists() and previous:
        write_json(configfile, resolve_config(ROOT, previous, {}, None, False))
    config = resolve_config(ROOT, read_json(configfile), os.environ, args.port, args.secure)
    os.environ.update(config["environment"])
    runtime = Path(config["environment"].get("OPENSOOM_RUNTIME_DIR", str(control)))
    runtime.mkdir(parents=True, exist_ok=True)
    if args.command == "validate":
        profiles = Core.load_profiles()
        registry = Core.load_registry(profiles)
        print(json.dumps({"status": "valid", "profiles": list(profiles), "facility_registry": registry}))
        return
    if args.command == "doctor":
        core = Core()
        try:
            result = core.doctor()
        finally:
            core.cse.close()
        running, owned = process_info(int(previous["pid"]), ROOT) if previous else (False, False)
        reachable = False
        if running and owned:
            try:
                with httpx.Client(timeout=2, trust_env=False) as client:
                    reachable = client.get(f"http://127.0.0.1:{config['port']}/api/health").is_success
            except httpx.HTTPError:
                pass
        result["service"] = {"running": running and owned, "reachable": reachable, "port": config["port"]}
        if not reachable:
            result.update(status="not_ready", next_step="Run opensoom start using the saved runtime configuration")
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result["status"] == "ready" else 1)
    if args.command == "serve":
        if previous and int(previous["pid"]) != os.getpid():
            running, _ = process_info(int(previous["pid"]), ROOT)
            if running:
                raise RuntimeError("A recorded service is already running; use restart")
        write_json(configfile, config)
        write_json(pidfile, {"pid": os.getpid(), "interpreter": str(ROOT / ".venv/bin/python"), "port": config["port"]})
        import uvicorn
        try:
            uvicorn.run("opensoom.app:app", host="127.0.0.1", port=config["port"], access_log=False)
        finally:
            if read_json(pidfile).get("pid") == os.getpid():
                pidfile.unlink(missing_ok=True)
        return
    if args.command in ("stop", "restart", "cleanup"):
        stop_service(pidfile, ROOT)
    if args.command == "cleanup":
        for name in ("operations.sqlite", "operations.sqlite-wal", "operations.sqlite-shm", "service-credentials.json", "service.log", "cse-requests.jsonl", "mqtt-requests.jsonl"):
            (runtime / name).unlink(missing_ok=True)
        print(json.dumps({"status": "cleaned", "retained": ["service-config.json", "CSE state", "shared LLM budget"]}))
    elif args.command == "stop":
        print(json.dumps({"status": "stopped", "configuration_retained": True}))
    if args.command in ("start", "restart"):
        if pidfile.exists():
            raise RuntimeError("Service has a recorded process. Use doctor or restart")
        write_json(configfile, config)
        interpreter = str(ROOT / ".venv/bin/python")
        with (runtime / "service.log").open("a") as log:
            process = subprocess.Popen([interpreter, "-m", "opensoom.cli", "serve", "--port", str(config["port"])], cwd=ROOT, env=os.environ.copy(), stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        write_json(pidfile, {"pid": process.pid, "interpreter": interpreter, "port": config["port"]})
        print(json.dumps({"pid": process.pid, "url": f"http://127.0.0.1:{config['port']}", "status": "starting"}))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(json.dumps({"status": "error", "message": str(error)}))
        raise SystemExit(1) from None
