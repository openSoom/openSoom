#!/usr/bin/env python3
"""Submit and read a site administrator's preconfigured virtual sensor-provider request."""
import argparse
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", default="http://127.0.0.1:8090")
    parser.add_argument("--facility", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--request-id", default=None, help="Reuse this value after an interruption")
    parser.add_argument("--runtime", type=Path, default=Path(".runtime"))
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    target = urlsplit(args.service)
    if (target.scheme not in ("https", "http") or not target.hostname or target.username or target.password
            or target.query or target.fragment or target.path not in ("", "/")
            or (target.scheme == "http" and target.hostname not in ("127.0.0.1", "localhost", "::1"))):
        parser.error("Use a verified HTTPS endpoint or an SSH-forwarded loopback endpoint")
    token = os.environ.get("OPENSOOM_COMMISSION_TOKEN")
    if not token:
        token = json.loads((args.runtime / "service-credentials.json").read_text())["admin_token"]
    body = {"arguments":{"facility_id":args.facility, "provider_profile":args.profile,
                         "request_id":args.request_id or "enable-" + uuid.uuid4().hex[:16]}}
    deadline = time.monotonic() + args.timeout
    with httpx.Client(base_url=args.service, headers={"Authorization":"Bearer " + token}, follow_redirects=False,
                      verify=os.environ.get("OPENSOOM_CSE_CA") or True, trust_env=False, timeout=10) as client:
        name = "commission_provider"
        while True:
            response = client.post("/api/tools/" + name, json=body)
            response.raise_for_status()
            result = response.json()
            if name == "commission_provider" or result["status"] != "pending":
                print(json.dumps(result), flush=True)
            if result["status"] != "pending":
                return 0 if result["status"] in ("enabled", "already_enabled") else 1
            if time.monotonic() >= deadline:
                raise SystemExit("Result is still pending. Retry with the printed request_id.")
            time.sleep(1)
            name = "read_provider_result"


if __name__ == "__main__":
    raise SystemExit(main())
