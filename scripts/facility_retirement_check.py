"""Verify the retired maintenance identity loses access to historical device data."""
import argparse
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

from maintenance_demo import ROOT, available_port
from opensoom.core import Core
from opensoom.onem2m import CSEClient, CSEError


class Notifications(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.send_response(200)
        self.send_header("X-M2M-RSC", "2000")
        self.send_header("X-M2M-RI", self.headers.get("X-M2M-RI", ""))
        self.send_header("X-M2M-RVI", "4")
        self.end_headers()

    def log_message(self, *_):
        pass


def access(cse, resource, origin):
    try:
        result = cse.retrieve(resource, origin=origin)
    except CSEError as exc:
        result = exc.result
    return {"rsc": int(result["rsc"]), "rqi": result["rqi"]}


def run():
    with ExitStack() as stack:
        directory = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="opensoom-retirement-")))
        server = ThreadingHTTPServer(("127.0.0.1", 0), Notifications)
        stack.callback(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        stack.callback(server.shutdown)
        port = available_port()
        env = {"OPENSOOM_CSE_RUNTIME_DIR": str(directory), "OPENSOOM_CSE_BASE": "cse-in",
               "OPENSOOM_NOTIFY_URL": f"http://127.0.0.1:{server.server_port}/notify", "OPENSOOM_FACILITY_IDS": "food-a,learning-b"}
        stack.enter_context(patch.dict(os.environ, env))
        runtime = [sys.executable, str(ROOT / "scripts/cse_runtime.py")]
        subprocess.run([*runtime, "start", "--name", "single", "--port", str(port)], check=True, stdout=subprocess.DEVNULL)
        stack.callback(subprocess.run, [*runtime, "stop", "--name", "single"], stdout=subprocess.DEVNULL)
        cse = stack.enter_context(CSEClient(f"http://127.0.0.1:{port}"))
        prior = Core(runtime=directory / "operations", cse=cse)
        prior.bootstrap()
        retired = prior.identities["maintenance:food-a"]
        reader, writer = prior.identities["operator"], prior.identities["adapter"]
        zone = prior.facility("food-a")["zones"][0]["path"]
        records = {}
        for stream in ("observations", "acks"):
            live = prior.create_content(zone + "/" + stream, {"simulated": True, "record": stream}, writer)
            ri = live["body"]["m2m:cin"]["ri"]
            records[stream] = {"ri": ri, "before": access(cse, ri, retired)}
        os.environ["OPENSOOM_FACILITY_IDS"] = "learning-b"
        current = Core(runtime=directory / "operations", cse=cse)
        current.bootstrap()
        for record in records.values():
            record["retired_after"] = access(cse, record["ri"], retired)
            record["operator_after"] = access(cse, record["ri"], reader)
            assert [record[k]["rsc"] for k in ("before", "retired_after", "operator_after")] == [2000, 4103, 2000]
        return {"status": "passed", "scope": "Actual ACME CSE on loopback, same historical CIN before and after a site is removed from configuration",
                "active_sites_after": list(current.registry), "records": records,
                "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in
                                  ("src/opensoom/core.py", "src/opensoom/maintenance.py", "scripts/facility_retirement_check.py")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    report = run()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
