#!/usr/bin/env python3
"""Verify an installed plugin in a fresh Codex CLI profile without a model turn.

Uses Codex 0.166.0's app-server protocol. This proves plugin discovery and actual
host MCP execution, separately from the standalone live-model acceptance run.
No normal Codex profile, authentication or security settings are modified.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from agent_install_plugin import prepare
from opensoom.mcp_server import ServiceProxy, redact


class CodexRPC:
    def __init__(self, process: asyncio.subprocess.Process):
        self.process = process
        self.counter = 0
        self.notifications: list[str] = []

    async def send(self, value: dict) -> None:
        self.process.stdin.write((json.dumps(value) + "\n").encode())
        await self.process.stdin.drain()

    async def request(self, method: str, params: dict) -> dict:
        self.counter += 1
        request_id = self.counter
        await self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        async with asyncio.timeout(45):
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    raise RuntimeError("Codex app-server exited before replying")
                response = json.loads(line)
                if response.get("id") == request_id and "method" not in response:
                    if "error" in response:
                        raise RuntimeError(f"Codex {method}: {response['error']}")
                    return response["result"]
                if "method" in response:
                    self.notifications.append(response["method"])
                    if "id" in response:
                        # This read-only host test does not grant interactive
                        # permissions or answer account authentication prompts.
                        await self.send({"jsonrpc": "2.0", "id": response["id"], "error": {
                            "code": -32601, "message": "Interactive request is outside this acceptance test"}})


def safe(value: object, root: Path) -> object:
    text = json.dumps(redact(value), ensure_ascii=False)
    text = text.replace(str(root), "<checkout>").replace(str(Path.home()), "<user-home>")
    return json.loads(text)


async def check(root: Path, facility: str) -> dict:
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("Codex CLI is missing")
    profile = root / ".runtime" / ("codex-acceptance-" + uuid.uuid4().hex[:8])
    profile.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not any(p in k for p in ("API_KEY", "TOKEN", "SECRET"))}
    env["CODEX_HOME"] = str(profile)
    catalog = prepare(root)
    result = {"test": "codex-plugin-host", "status": "RUNNING", "profile": "fresh isolated Codex data directory",
              "normal_user_profile_changed": False, "model_inference_calls": 0,
              "physical_devices": "simulated", "commands": [], "host_calls": [],
              "source_sha256": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted((root / "plugin").rglob("*")) if p.is_file()}}
    version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=15, env=env)
    result["codex_version"] = version.stdout.strip()
    for command in [
        ["plugin", "list", "--json"],
        ["plugin", "marketplace", "add", str(catalog), "--json"],
        ["plugin", "add", "opensoom@opensoom-local", "--json"],
        ["plugin", "list", "--json"],
    ]:
        proc = subprocess.run([executable, *command], cwd=root, env=env, capture_output=True, text=True, timeout=45)
        try:
            output = json.loads(proc.stdout)
        except ValueError:
            output = proc.stdout[:4000]
        result["commands"].append({"args": command, "exit_status": proc.returncode, "output": output})
        if proc.returncode:
            result.update(status="FAIL", error="Codex plugin registration failed")
            return safe(result, root)
    process = await asyncio.create_subprocess_exec(executable, "app-server", "--listen", "stdio://", cwd=root, env=env,
                                                 stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                 stderr=asyncio.subprocess.PIPE)
    stderr_task = asyncio.create_task(process.stderr.read())
    rpc = CodexRPC(process)
    try:
        initialized = await rpc.request("initialize", {"clientInfo": {"name": "opensoom-acceptance", "version": "0.1.0"},
                                                       "capabilities": {"experimentalApi": True}})
        result["host_initialize"] = initialized
        await rpc.send({"jsonrpc": "2.0", "method": "initialized"})
        plugins = await rpc.request("plugin/list", {"cwds": [str(root)], "forceRefetch": False})
        result["plugin_inventory"] = plugins
        thread = await rpc.request("thread/start", {"cwd": str(root), "ephemeral": True})
        thread_id = thread["thread"]["id"]
        servers = await rpc.request("mcpServerStatus/list", {"threadId": thread_id, "limit": 100})
        result["mcp_servers"] = servers
        candidates = [s for s in servers["data"] if "opensoom" in s["name"].lower()]
        if not candidates:
            raise RuntimeError("Installed plugin MCP server was not loaded by Codex; inspect local acceptance-stderr.log")
        server = candidates[0]
        for tool, arguments in [("doctor", {}), ("prepare_setup", {"profile_id": "food-production"}),
                                ("discover", {"facility_id": facility}), ("read_group", {"facility_id": facility}),
                                ("read_evidence", {"facility_id": facility}),
                                ("apply_setup", {"profile_id": "food-production"})]:
            response = await rpc.request("mcpServer/tool/call", {"threadId": thread_id, "server": server["name"],
                                                                "tool": tool, "arguments": arguments})
            result["host_calls"].append({"tool": tool, "arguments": arguments, "response": response})
            if tool == "apply_setup":
                if not response.get("isError") or "admin_required" not in json.dumps(response):
                    raise RuntimeError("Operator profile activation was not denied as expected")
                result["operator_cannot_activate_profile"] = True
            elif response.get("isError"):
                raise RuntimeError(f"Codex-hosted {tool} returned an error")
        correlated = [c["response"].get("structuredContent", {}).get("run_id")
                      for c in result["host_calls"] if "facility_id" in c["arguments"]]
        if not correlated or any(not run or run != correlated[0] for run in correlated):
            raise RuntimeError("Host tools did not preserve one facility run identity")
        run = ServiceProxy().request("GET", "/api/runs/" + correlated[0])
        result["service_run"] = run
        actual_tools = {call["name"] for call in run.get("tool_calls", [])}
        if run.get("mode") != "mcp_host" or not {"discover", "read_group", "read_evidence"} <= actual_tools:
            raise RuntimeError("Service did not persist the actual host facility tool calls")
        result["run_correlation_verified"] = True
        result["status"] = "PASS_HOST_MCP"
        result["limitations"] = ["No Codex model turn was executed; this is a host/plugin transport test.",
                                  "Live model decisions are tested separately by the standalone runner.",
                                  "Physical sensors and actuators are virtual."]
    except (RuntimeError, ValueError, KeyError, StopIteration, TimeoutError) as exc:
        result.update(status="FAIL", error=str(exc), error_type=type(exc).__name__)
    finally:
        result["notification_methods"] = sorted(set(rpc.notifications))
        if process.returncode is None:
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except TimeoutError:
            process.kill()
            await process.wait()
        stderr = await stderr_task
        # Keep raw local diagnostics out of public evidence and ordinary output.
        (profile / "acceptance-stderr.log").write_bytes(stderr)
        result["test_process_stopped"] = process.returncode is not None
    return safe(result, root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--facility", default="food-a")
    parser.add_argument("--output", type=Path, default=Path("evidence/agent/codex-host.json"))
    args = parser.parse_args()
    result = asyncio.run(check(args.project.resolve(), args.facility))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "codex_version": result["codex_version"],
                      "host_tool_calls": len(result["host_calls"]), "error": result.get("error")}, ensure_ascii=False))
    raise SystemExit(0 if result["status"].startswith("PASS") else 1)


if __name__ == "__main__":
    main()
