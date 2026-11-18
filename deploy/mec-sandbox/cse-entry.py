"""Start one CSE; keep the provider's authority independent of the facility."""
import configparser
import os
from pathlib import Path
import secrets
import sys

role = os.environ["OPENSOOM_CSE_ROLE"]
if role not in {"in", "mn", "provider"}:
    raise ValueError("Unknown CSE role")
folder = Path("/var/lib/opensoom")
folder.mkdir(exist_ok=True, parents=True)
config = configparser.ConfigParser(interpolation=None)
config.optionxform = str
config.read("/opt/base.ini")
secret_path = folder / "security.secret"
if not secret_path.exists():
    secret_path.write_text(secrets.token_urlsafe(32))
    secret_path.chmod(0o600)
config["basic.config"].update({
    "cseType": "MN" if role == "mn" else "IN", "secret": secret_path.read_text().strip(),
    "cseID": f"opensoom-{role}", "cseName": f"cse-{role}", "httpPort": "8080",
    "adminID": "CProviderOwner" if role == "provider" else "CAdmin",
    "networkInterface": "0.0.0.0", "cseHost": f"opensoom-{role}.default.svc.cluster.local"
})
config["cse"]["enableRemoteCSE"] = str(role != "provider").lower()
if role != "provider":
    config["cse.registration"] = {
        "allowedCSROriginators": "/opensoom-mn,/opensoom-in", "checkInterval": "5",
        "unregisterWhenStopping": "false"}
if role == "mn":
    config["basic.config"].update({"registrarCseID":"opensoom-in","registrarCseName":"cse-in",
                                  "registrarCseHost":"opensoom-in.default.svc.cluster.local","registrarCsePort":"8080"})
    config["cse.registrar"] = {"INCSEcseID": "/opensoom-in"}
with (folder / "acme.ini").open("w") as stream:
    config.write(stream)
os.execv(sys.executable, [sys.executable, "-m", "acmecse", "--base-directory", str(folder), "--headless"])
