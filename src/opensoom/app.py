"""Loopback development application; tokens fix server-side actor identity."""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from html import escape
from urllib.parse import urlsplit

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import maintenance
from .core import Core, OperationError, ROOT
from .models import ToolEnvelope, utcnow
from .onem2m import CSEError

core = Core()
credential_path = core.runtime / "service-credentials.json"
if not credential_path.exists():
    descriptor = os.open(credential_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({role + "_token": secrets.token_urlsafe(32) for role in ("operator", "maintenance", "admin", "observer")}, stream)
credentials = json.loads(credential_path.read_text())


def principal(request: Request):
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    for role in ("operator", "maintenance", "admin", "observer"):
        if secrets.compare_digest(token, credentials[role + "_token"]):
            return {"role": role, "facilities": core.actor_facilities(role)}
    raise HTTPException(401, {"code": "unauthorized", "message": "Connect with the configured openSoom service identity"})


def worker():
    time.sleep(1)
    bootstrapped = False
    while not core.stop_event.is_set():
        try:
            if not bootstrapped:
                core.bootstrap()
                bootstrapped = True
            core.tick()
        except Exception as exc:
            core.connected = False
            core.last_error = f"{type(exc).__name__}: {exc}"
            core.log("runtime_error", "Runtime setup needs attention", error=core.last_error)
        core.stop_event.wait(2)


def maintenance_sync():
    previous_error = None
    while not core.stop_event.wait(1):
        if not core.connected:
            continue
        try:
            maintenance.flush_outbox(core)
            maintenance.refresh_work_orders(core)
            previous_error = None
        except (CSEError, ValueError, KeyError) as exc:
            # Keep remote delivery and worker availability out of the control loop.
            message = str(exc)
            if message != previous_error:
                core.log("maintenance_sync_error", "Maintenance synchronization will retry", error=message)
                previous_error = message


@asynccontextmanager
async def lifespan(app):
    thread = threading.Thread(target=worker, name="opensoom-simulation", daemon=True)
    sync = threading.Thread(target=maintenance_sync, name="opensoom-maintenance-sync", daemon=True)
    thread.start()
    sync.start()
    yield
    core.stop_event.set()
    thread.join(timeout=15)
    sync.join(timeout=15)
    if core.mqtt:
        core.mqtt.close()
    core.cse.close()


app = FastAPI(title="openSoom", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def origin_and_headers(request, call_next):
    # A remote web page cannot use the loopback demo service as a CSRF target.
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
        return JSONResponse({"detail": {"code": "origin_denied", "message": "Use the same-origin local dashboard"}}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.exception_handler(OperationError)
async def operation_error(request, exc):
    return JSONResponse({"detail": {"code": exc.code, "message": exc.message}}, status_code=exc.status)


@app.exception_handler(CSEError)
async def cse_error(request, exc):
    return JSONResponse({"detail": {"code": "cse_error", "message": str(exc), "rsc": exc.rsc, "rqi": exc.result.get("rqi")}}, status_code=503)


@app.get("/", response_class=HTMLResponse)
def home():
    path = ROOT / "web/index.html"
    if not path.exists():
        return "<h1>openSoom</h1><p>Service is running. Dashboard assets are being prepared.</p>"
    html = path.read_text()
    meta = '<meta name="opensoom-token" content="' + credentials["operator_token"] + '">'
    if re.search(r'<meta\s+name=[\"\']opensoom-token', html):
        html = re.sub(r'<meta\s+name=[\"\']opensoom-token[\"\'][^>]*>', meta, html)
    else:
        html = html.replace("</head>", meta + "</head>")
    technician_url = os.getenv("OPENSOOM_TECHNICIAN_URL", "")
    facility = os.getenv("OPENSOOM_TECHNICIAN_FACILITY", "")
    if technician_url and facility:
        address = urlsplit(technician_url)
        allowed = address.scheme == "https" or (
            address.scheme == "http" and address.hostname in {"localhost", "127.0.0.1", "::1"}
        )
        if allowed and address.hostname and not (address.username or address.password or address.query or address.fragment):
            html = html.replace(
                "<!-- technician-workbench -->",
                f'<meta name="technician-workbench" content="{escape(technician_url)}" data-facility="{escape(facility)}">',
            )
    virtual_shaft_site = os.getenv("OPENSOOM_LOCAL_SHAFT_REPLAY_FACILITY")
    if virtual_shaft_site:
        html = html.replace(
            "<!-- local-shaft-replay -->",
            f'<meta name="local-shaft-replay" content="{escape(virtual_shaft_site)}">',
        )
    return html


@app.get("/api/health")
def health():
    return {"service": "opensoom", "status": "running", "cse_connected": core.connected, "configured_facilities": len(core.store.list("facilities")), "last_error": core.last_error, "simulation": True}


@app.get("/api/state")
def state(request: Request):
    return core.state(principal(request))


@app.get("/api/commands/{command_id}/air-quality")
def air_quality_history(command_id: str, request: Request, after: int = Query(0, ge=0),
                        limit: int = Query(50, ge=1, le=200)):
    return core.air_quality_history(command_id, principal(request), after, limit)


@app.post("/api/notify")
async def notification(request: Request, background: BackgroundTasks):
    payload = await request.json()
    if not payload.get("m2m:sgn", {}).get("vrq"):
        background.add_task(core.notification, payload)
    return JSONResponse({}, headers={"X-M2M-RSC": "2000", "X-M2M-RI": request.headers.get("X-M2M-RI", ""), "X-M2M-RVI": "4"})


@app.post("/api/demo/start")
def start_demo(body: dict, request: Request):
    return core.start_demo(body.get("facility_id", "food-a"), body.get("scenario", "normal"), bool(body.get("autorun", False)), principal(request))


@app.post("/api/tools/{name}")
def tool(name: str, body: ToolEnvelope, request: Request):
    actor = principal(request)
    run_id = request.headers.get("X-OpenSoom-Run-ID")
    try:
        return core.tool(name, body.arguments, actor, run_id)
    except (OperationError, CSEError, ValidationError) as exc:
        if run_id:
            run = core.store.get("runs", run_id)
            if run and run["facility_id"] in actor["facilities"] and run.get("principal_role") == actor["role"]:
                run["tool_calls"] = run.get("tool_calls", []) + [{"name": name, "at": utcnow(), "result_status": "denied" if isinstance(exc, OperationError) and exc.status == 403 else "error", "error": getattr(exc, "code", type(exc).__name__)}]
                core.store.put("runs", run_id, run)
        if isinstance(exc, ValidationError):
            raise OperationError("invalid_arguments", "Tool arguments do not match the declared schema", 422) from exc
        raise


@app.get("/api/runs/{run_id}")
def get_run(run_id: str, request: Request):
    run = core.store.get("runs", run_id)
    if not run:
        raise OperationError("unknown_run", "Run not found", 404)
    core.authorize(principal(request), run["facility_id"])
    return run


@app.post("/api/agent-runs")
def create_agent_run(body: dict, request: Request):
    actor = principal(request)
    fid = body.get("facility_id", "food-a")
    core.authorize(actor, fid)
    core.facility(fid)
    run_id = body.get("id") or "agent-" + uuid.uuid4().hex[:12]
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", run_id):
        raise OperationError("invalid_run_id", "Run ID is invalid")
    if core.store.get("runs", run_id):
        raise OperationError("run_exists", "Run already exists", 409)
    run = {"id": run_id, "run_id": run_id, "facility_id": fid, "scenario": body.get("scenario", core.facility(fid)["scenario"]), "mode": body.get("mode", "fixture"), "model": body.get("model"), "principal_role": actor["role"], "status": "running", "started_at": utcnow(), "tool_calls": [], "steps": []}
    core.store.put("runs", run_id, run)
    core.log("agent_started", "Agent workflow started", fid, run_id=run_id, mode=run["mode"])
    return run


@app.patch("/api/agent-runs/{run_id}")
def update_agent_run(run_id: str, body: dict, request: Request):
    run = get_run(run_id, request)
    actor = principal(request)
    if actor["role"] == "observer" or actor["role"] != run.get("principal_role"):
        raise OperationError("run_owner_required", "Only the run's owning operational identity can update its result", 403)
    names = {t["name"] for t in run.get("tool_calls", [])}
    commands = [c for c in core.store.list("commands") if c.get("run_id") == run_id]
    requested = body.get("outcome", "RUNNING")
    outcome = requested
    verified = any(c["status"] == "verified" and c.get("ack") and c.get("verification_rqi") for c in commands)
    stale_refusal = any(t["name"] == "read_evidence" and t.get("result_status") in ("stale", "missing") for t in run.get("tool_calls", [])) and not commands
    denied = "read_evidence" in names and any(t.get("error") in ("evidence_not_current", "action_denied", "facility_denied") for t in run.get("tool_calls", []))
    non_recovery = "verify_result" in names and any(c.get("ack") and c["status"] == "unresolved" and c.get("unresolved_samples", 0) >= 2 and c.get("verification_rqi") for c in commands)
    handled_failure = stale_refusal or denied or non_recovery
    if requested.startswith("PASS"):
        valid_flow = verified and {"read_evidence", "request_action", "verify_result"} <= names
        trial_id = body.get("scenario_execution_id")
        trial = core.store.get("scenario_runs", trial_id) if isinstance(trial_id, str) else None
        matched = {call["name"]: call["scenario_receipt"] for call in run.get("tool_calls", [])
                   if trial and call.get("scenario_receipt", {}).get("version") == trial["version"]
                   and (call["name"] == "save_scenario" or call["scenario_receipt"].get("execution_id") == trial_id)}
        authored = bool(trial and trial.get("agent_run_id") == run_id and trial.get("status") == "completed"
                        and trial.get("assertion_passed") and trial["facility_id"] == run["facility_id"]
                        and {"save_scenario", "run_scenario", "read_scenario_run"} <= matched.keys()
                        and matched["read_scenario_run"].get("readback_rqi"))
        if authored:
            run.update(scenario_execution_id=trial_id, scenario=trial["scenario_id"], expected=trial["expected_result"])
        if not valid_flow and not handled_failure and not authored:
            outcome = "FAIL"
        if "LLM" in requested and (not body.get("live_model") or run["mode"] == "fixture"):
            outcome = "FAIL"
        if "LLM" in requested and body.get("reported_outcome") != (trial["actual_result"] if authored else ("recovered" if verified else "unresolved")):
            outcome = "FAIL"
    run.update({k: body[k] for k in ("summary", "model", "steps", "usage", "live_model", "reported_outcome") if k in body})
    run.update(outcome=outcome, status="completed" if outcome.startswith("PASS") else ("running" if outcome == "RUNNING" else "failed"), completed_at=utcnow(), server_validation={"verified_recovery": verified, "handled_failure": handled_failure, "recorded_tool_calls": len(run.get("tool_calls", [])), "requested_outcome": requested})
    core.store.put("runs", run_id, run)
    core.log("agent_result", "Agent result: " + outcome, run["facility_id"], run_id=run_id, server_validation=run["server_validation"])
    return run


web_path = ROOT / "web"
web_path.mkdir(exist_ok=True)
app.mount("/assets", StaticFiles(directory=web_path), name="assets")
