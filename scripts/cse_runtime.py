#!/usr/bin/env python3
"""Manage only project-owned ACME processes and generated runtime files."""
from __future__ import annotations

import argparse
import configparser
import json
import os
from pathlib import Path
import shutil
import signal
import secrets
import ssl
import subprocess
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
VENV = ROOT / "tmp/runtime/cse-venv"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "start", "stop", "status"])
    parser.add_argument("--name", default="single", choices=["single", "secure", "central", "food", "learning"])
    parser.add_argument("--port", type=int)
    parser.add_argument("--registrar-port", type=int, default=8080)
    parser.add_argument("--mqtt", action="store_true", help="Enable the real MQTT/TLS binding using the local broker on 8883")
    parser.add_argument("--reset", action="store_true", help="Reset this named openSoom CSE database when starting")
    args = parser.parse_args()
    python = VENV / "bin/python"
    if args.action == "install":
        uv = shutil.which("uv")
        if not uv:
            print(json.dumps({"error": "Install uv and Python 3.12, then rerun this command."}))
            return 2
        py = shutil.which("python3.12")
        if not py:
            print(json.dumps({"error": "Python 3.12 is required for the pinned CSE runtime."}))
            return 2
        if not python.exists():
            subprocess.run([uv, "--cache-dir", str(ROOT / "tmp/uv-cache"), "venv", "--python", py, str(VENV)], check=True)
        subprocess.run([uv, "--cache-dir", str(ROOT / "tmp/uv-cache"), "pip", "install", "--python", str(python), "-r", str(ROOT / "deploy/cse-requirements.txt")], check=True)
        return 0
    folder = RUNTIME / f"cse-{args.name}"
    pidfile = folder / "process.json"
    record = json.loads(pidfile.read_text()) if pidfile.exists() else None
    if args.action == "status":
        if not record:
            print(json.dumps({"name": args.name, "running": False}))
            return 1
        healthy = probe(record["url"], record["resource"], record.get("ca_file"))
        print(json.dumps({"name": args.name, "running": healthy, **record}))
        return 0 if healthy else 1
    if args.action == "stop":
        if not record:
            print(json.dumps({"name": args.name, "running": False}))
            return 0
        # Verify PID ownership before signaling; a stale pid must not kill another app.
        command = subprocess.run(["ps", "-p", str(record["pid"]), "-o", "command="], capture_output=True, text=True).stdout
        if str(folder) in command and "acmecse" in command:
            os.kill(record["pid"], signal.SIGTERM)
            for _ in range(50):
                if not probe(record["url"], record["resource"], record.get("ca_file")):
                    break
                time.sleep(0.1)
        pidfile.unlink(missing_ok=True)
        print(json.dumps({"name": args.name, "stopped": True}))
        return 0
    if not python.exists():
        print(json.dumps({"error": "CSE runtime missing. Run: python3 scripts/cse_runtime.py install"}))
        return 2
    if record and probe(record["url"], record["resource"], record.get("ca_file")):
        print(json.dumps({"name": args.name, "running": True, "already_running": True, **record}))
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(0o700)
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str  # ACME configuration interpolation is case-sensitive.
    config.read(ROOT / "deploy/acme-single.ini")
    secret_file = folder / "security.secret"
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(32))
        secret_file.chmod(0o600)
    config["basic.config"]["secret"] = secret_file.read_text().strip()
    name = "cse-in" if args.name == "single" else f"cse-{args.name}"
    cse_id = "opensoom-in" if args.name == "single" else f"opensoom-{args.name}"
    port = args.port or {"single": 8080, "secure": 8443, "central": 8080, "food": 8081, "learning": 8082}[args.name]
    config["basic.config"].update({"cseName": name, "cseID": cse_id, "httpPort": str(port)})
    if args.name not in ("single", "secure"):
        config["cse"]["enableRemoteCSE"] = "true"
        config["cse.registration"] = {"allowedCSROriginators": "/opensoom-food,/opensoom-learning,/opensoom-central", "checkInterval": "5", "unregisterWhenStopping": "false"}
        if args.name != "central":
            config["basic.config"].update({"cseType": "MN", "registrarCseID": "opensoom-central", "registrarCseName": "cse-central", "registrarCseHost": "127.0.0.1", "registrarCsePort": str(args.registrar_port)})
            config["cse.registrar"] = {"INCSEcseID": "/opensoom-central"}
    if args.name == "secure" or args.mqtt:
        pki = prepare_certificates()
        if args.name == "secure":
            config["http"]["address"] = f"https://127.0.0.1:{port}"
            # In ACME this flag controls required *client* certificates on its
            # server SSLContext. Clients still verify the server with our CA.
            config["http.security"] = {"useTLS": "true", "verifyCertificate": "false", "caCertificateFile": str(pki / "server.crt"), "caPrivateKeyFile": str(pki / "server.key")}
        if args.mqtt:
            config["mqtt"] = {"enable": "true", "address": "127.0.0.1", "port": "8883"}
            config["mqtt.security"] = {"useTLS": "true", "verifyCertificate": "true", "caCertificateFile": str(pki / "ca.crt")}
    with (folder / "acme.ini").open("w") as stream:
        config.write(stream)
    (folder / "acme.ini").chmod(0o600)
    command = [str(python), "-m", "acmecse", "--base-directory", str(folder), "--headless"]
    if args.reset:
        command.append("--db-reset")
    env = {k: v for k, v in os.environ.items() if k not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENSOOM_LLM_API_KEY"}}
    with (folder / "stdout.log").open("a") as log:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    record = {"pid": process.pid, "url": f"{'https' if args.name == 'secure' else 'http'}://127.0.0.1:{port}", "resource": name, "cse_id": f"/{cse_id}"}
    if args.name == "secure":
        record["ca_file"] = str(pki / "ca.crt")
    pidfile.write_text(json.dumps(record, indent=2) + "\n")
    readiness_deadline = time.monotonic() + 45
    while time.monotonic() < readiness_deadline:
        if process.poll() is not None:
            print(json.dumps({"error": "CSE process exited", "log": str(folder.relative_to(ROOT) / "stdout.log")}))
            return 1
        if probe(record["url"], name, record.get("ca_file")):
            print(json.dumps({"name": args.name, "running": True, **record}))
            return 0
        time.sleep(0.1)
    print(json.dumps({"error": "CSE readiness timed out", "log": str(folder.relative_to(ROOT) / "stdout.log")}))
    return 1


def prepare_certificates() -> Path:
    """Generate a private project CA and localhost leaf; never touch global trust."""
    pki = RUNTIME / "pki"
    pki.mkdir(parents=True, exist_ok=True)
    pki.chmod(0o700)
    if all((pki / name).exists() for name in ("ca.crt", "ca.key", "server.crt", "server.key", "server.ext")) and "authorityKeyIdentifier" in (pki / "server.ext").read_text():
        return pki
    commands = [
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30", "-subj", "/CN=openSoom local development CA", "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-keyout", str(pki / "ca.key"), "-out", str(pki / "ca.crt")],
        ["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=localhost", "-keyout", str(pki / "server.key"), "-out", str(pki / "server.csr")],
    ]
    (pki / "server.ext").write_text("subjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nauthorityKeyIdentifier=keyid,issuer\nsubjectKeyIdentifier=hash\n")
    commands.append(["openssl", "x509", "-req", "-in", str(pki / "server.csr"), "-CA", str(pki / "ca.crt"), "-CAkey", str(pki / "ca.key"), "-CAcreateserial", "-days", "30", "-extfile", str(pki / "server.ext"), "-out", str(pki / "server.crt")])
    for command in commands:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for path in pki.glob("*.key"):
        path.chmod(0o600)
    return pki


def probe(url: str, resource: str, ca_file: str | None = None) -> bool:
    try:
        req = urllib.request.Request(f"{url}/{resource}", headers={"X-M2M-Origin": "CAdmin", "X-M2M-RI": f"probe-{uuid.uuid4().hex}", "X-M2M-RVI": "4"})
        context = ssl.create_default_context(cafile=ca_file) if ca_file else None
        with urllib.request.urlopen(req, timeout=0.5, context=context) as response:
            return response.headers.get("X-M2M-RSC") == "2000"
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    raise SystemExit(main())
