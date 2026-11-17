#!/usr/bin/env python3
"""Project-owned loopback MQTT/TLS broker for the virtual-device lab."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path
import shutil
import signal
import socket
import ssl
import subprocess
import time
from cse_runtime import ROOT, RUNTIME, prepare_certificates

VENV = ROOT / "tmp/runtime/mqtt-venv"
FOLDER = RUNTIME / "mqtt"


def ready() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8883), timeout=0.4) as sock:
            with ssl.create_default_context(cafile=str(RUNTIME / "pki/ca.crt")).wrap_socket(sock, server_hostname="localhost"):
                return True
    except OSError:
        return False


async def serve():
    from amqtt.broker import Broker
    pki = prepare_certificates()
    broker = Broker({"listeners": {"default": {"type": "tcp", "bind": "127.0.0.1:8883", "ssl": True, "cafile": str(pki / "ca.crt"), "certfile": str(pki / "server.crt"), "keyfile": str(pki / "server.key"), "client_cert": "none"}}, "plugins": {"amqtt.plugins.authentication.AnonymousAuthPlugin": {"allow_anonymous": True}}})
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await broker.start()
    await stop.wait()
    await broker.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "start", "stop", "status", "serve"])
    action = parser.parse_args().action
    python = VENV / "bin/python"
    if action == "install":
        uv = shutil.which("uv")
        py = shutil.which("python3.12")
        if not uv or not py:
            raise SystemExit("uv and Python 3.12 required")
        if not python.exists():
            subprocess.run([uv, "--cache-dir", str(ROOT / "tmp/uv-cache"), "venv", "--python", py, str(VENV)], check=True)
        subprocess.run([uv, "--cache-dir", str(ROOT / "tmp/uv-cache"), "pip", "install", "--python", str(python), "-r", str(ROOT / "deploy/mqtt-requirements.txt")], check=True)
        return
    if action == "serve":
        logging.basicConfig(level=logging.ERROR)
        asyncio.run(serve())
        return
    pidfile = FOLDER / "process.json"
    record = json.loads(pidfile.read_text()) if pidfile.exists() else None
    if action == "status":
        print(json.dumps({"mqtt_tls_ready": ready(), "port": 8883}))
        return
    if action == "stop":
        if record:
            command = subprocess.run(["ps", "-p", str(record["pid"]), "-o", "command="], capture_output=True, text=True).stdout
            if str(ROOT / "scripts/cse_broker.py") in command and "serve" in command:
                os.kill(record["pid"], signal.SIGTERM)
            pidfile.unlink(missing_ok=True)
        print(json.dumps({"stopped": True}))
        return
    if ready():
        print(json.dumps({"mqtt_tls_ready": True, "already_running": True}))
        return
    if not python.exists():
        raise SystemExit("Run python3 scripts/cse_broker.py install")
    FOLDER.mkdir(parents=True, exist_ok=True)
    FOLDER.chmod(0o700)
    prepare_certificates()
    env = {k: v for k, v in os.environ.items() if k not in {"OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENSOOM_LLM_API_KEY"}}
    with (FOLDER / "stdout.log").open("a") as log:
        process = subprocess.Popen([str(python), str(ROOT / "scripts/cse_broker.py"), "serve"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    pidfile.write_text(json.dumps({"pid": process.pid}))
    for _ in range(100):
        if process.poll() is not None:
            raise SystemExit("MQTT broker exited; inspect .runtime/mqtt/stdout.log")
        if ready():
            print(json.dumps({"mqtt_tls_ready": True, "port": 8883, "pid": process.pid}))
            return
        time.sleep(0.1)
    raise SystemExit("MQTT broker readiness timed out; inspect .runtime/mqtt/stdout.log")


if __name__ == "__main__":
    main()
