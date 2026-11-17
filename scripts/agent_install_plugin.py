#!/usr/bin/env python3
"""Prepare/install the local plugin without editing application source or secrets.

The default check uses a new project-local Codex data directory. --current-host
selects the user's normal Codex installation explicitly; no global security or
authentication settings are changed by this script.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def prepare(root: Path) -> Path:
    root = root.resolve()
    python = root / ".venv/bin/python"
    if not python.is_file():
        raise RuntimeError("Project Python environment missing. Run the README dependency setup first.")
    catalog = root / ".runtime/plugin-marketplace"
    target = catalog / "plugin"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(root / "plugin", target, dirs_exist_ok=True)
    mcp = json.loads((target / "mcp.json").read_text())
    mcp["mcpServers"]["opensoom"].update({
        # Portable Agent Plugins allow a bare executable or a contained ./
        # script, not an absolute executable path. uv selects the project's
        # pinned environment without installing anything (--no-sync).
        "command": "uv", "args": ["--directory", str(root), "run", "--no-sync", "python", "-m", "opensoom.mcp_server"],
        "env": {"OPENSOOM_PROJECT_DIR": str(root), "OPENSOOM_SERVICE_URL": "http://127.0.0.1:8090"},
    })
    (target / "mcp.json").write_text(json.dumps(mcp, indent=2) + "\n")
    directory = catalog / ".agents/plugins"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "marketplace.json").write_text(json.dumps({
        "name": "opensoom-local", "interface": {"displayName": "openSoom local development"},
        "plugins": [{"name": "opensoom", "source": {"source": "local", "path": "./plugin"},
                     "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, "category": "Productivity"}],
    }, indent=2) + "\n")
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--current-host", action="store_true", help="Install into the current Codex profile instead of isolated verification data")
    args = parser.parse_args()
    root = args.project.resolve()
    catalog = prepare(root)
    results = {"prepared": True, "marketplace": ".runtime/plugin-marketplace", "installed": False,
               "host_scope": "current" if args.current_host else "isolated", "commands": []}
    if args.install:
        executable = shutil.which("codex")
        if not executable:
            raise SystemExit("Codex executable missing; install Codex before plugin installation.")
        env = os.environ.copy()
        isolated_home = root / ".runtime/codex-plugin-check"
        if not args.current_host:
            isolated_home.mkdir(parents=True, exist_ok=True)
            # This is the documented Codex data-directory setting, scoped only
            # to these child processes; the user's environment is untouched.
            env["CODEX_HOME"] = str(isolated_home)
        commands = [
            [executable, "plugin", "marketplace", "add", str(catalog), "--json"],
            [executable, "plugin", "add", "opensoom@opensoom-local", "--json"],
            [executable, "plugin", "list", "--json"],
        ]
        for command in commands:
            proc = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=60)
            output = (proc.stdout + proc.stderr).replace(str(root), "<checkout>").replace(str(Path.home()), "<user-home>")
            results["commands"].append({"command": [Path(command[0]).name, *[p.replace(str(root), "<checkout>") for p in command[1:]]],
                                        "exit_status": proc.returncode, "output": output})
            if proc.returncode:
                print(json.dumps(results, indent=2))
                raise SystemExit(proc.returncode)
        results["installed"] = True
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
