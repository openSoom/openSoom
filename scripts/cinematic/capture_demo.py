"""Record the actual dashboard against an isolated ACME CSE, then stop both processes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/demo-film/capture")
    parser.add_argument("--take", choices=["demo","food-unresolved"], default="demo")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / "tmp", prefix="film-runtime-") as directory:
        work = Path(directory)
        (work / "scripts").mkdir()
        (work / "tmp/runtime").mkdir(parents=True)
        shutil.copy(ROOT / "scripts/cse_runtime.py", work / "scripts/")
        (work / "deploy").symlink_to(ROOT / "deploy", target_is_directory=True)
        (work / "tmp/runtime/cse-venv").symlink_to(ROOT / "tmp/runtime/cse-venv", target_is_directory=True)
        ports = set()
        while len(ports) < 2:
            ports.add(free_port())
        cse_port, api_port = sorted(ports)
        cse = [sys.executable, str(work / "scripts/cse_runtime.py")]
        env = {k: v for k,v in os.environ.items() if not k.startswith("OPENSOOM_")}
        app_url = f"http://127.0.0.1:{api_port}"
        env.update(OPENSOOM_RUNTIME_DIR=str(work / "service"), OPENSOOM_CSE_URL=f"http://127.0.0.1:{cse_port}",
                   OPENSOOM_CSE_BASE="cse-in", OPENSOOM_NOTIFY_URL=app_url + "/api/notify")
        env["OPENSOOM_FILM_TAKE"]=args.take
        service = None
        try:
            subprocess.run(cse + ["start", "--name", "single", "--port", str(cse_port)], check=True, cwd=work, env=env)
            with (work / "api.log").open("w") as log:
                service = subprocess.Popen([str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "opensoom.app:app",
                    "--host", "127.0.0.1", "--port", str(api_port)], cwd=ROOT, env=env, stdout=log, stderr=log)
                for tick in range(80):
                    try:
                        with urllib.request.urlopen(app_url + "/api/health",timeout=2) as res:
                            if json.load(res)["cse_connected"]:
                                break
                    except OSError:
                        pass
                    time.sleep(.5)
                else:
                    raise RuntimeError("Isolated dashboard did not become ready")
                subprocess.run(["node", str(ROOT / "scripts/cinematic/capture_demo.cjs"), app_url, str(out)],
                               cwd=ROOT, env=env, check=True)
        finally:
            if service:
                service.terminate()
                service.wait(timeout=25)
            subprocess.run(cse + ["stop", "--name", "single"], check=True, cwd=work, env=env)


if __name__ == "__main__":
    main()
