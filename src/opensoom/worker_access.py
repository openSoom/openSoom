"""Bind scoped worker bearer credentials to provisioned oneM2M AE originators."""
from __future__ import annotations

import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response


def create_app() -> FastAPI:
    upstream = os.environ["OPENSOOM_CSE_URL"].rstrip("/")
    parsed = urlsplit(upstream)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Configure a fixed internal CSE URL")
    tokens = json.loads(Path(os.environ["OPENSOOM_WORKER_CREDENTIALS_FILE"]).read_text())
    if not tokens or any(not origin.startswith("C") or origin == "CAdmin" or not isinstance(token, str) or len(token) < 32 for origin, token in tokens.items()):
        raise ValueError("Each provisioned worker AE needs its own credential")
    if len(set(tokens.values())) != len(tokens):
        raise ValueError("Worker AE credentials must be distinct")

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(verify=os.environ.get("OPENSOOM_CSE_CA") or True, trust_env=False,
                                     follow_redirects=False, timeout=10) as client:
            app.state.upstream = client
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def forward(path: str, request: Request):
        headers = request.headers
        credential = headers.get("authorization", "")
        origin = headers.get("x-m2m-origin", "")
        token = tokens.get(origin)
        response_headers = {"X-M2M-RI": headers.get("x-m2m-ri", ""), "X-M2M-RVI": "4"}
        if token is None or not secrets.compare_digest(credential.encode(), ("Bearer " + token).encode()):
            return JSONResponse({"m2m:dbg": "Worker credential does not match the AE origin"},
                                status_code=403, headers={**response_headers, "X-M2M-RSC": "4103"})
        parts = path.split("/")
        if any(part in ("", ".", "..") for part in parts) or any(c in path for c in "?#%\\"):
            return JSONResponse({"m2m:dbg": "Invalid CSE resource path"}, status_code=400,
                                headers={**response_headers, "X-M2M-RSC": "4000"})
        # Every worker operation is on an existing facility stream. Provisioning
        # AEs, subscriptions and policies stays on the private management path.
        in_facility = len(parts) >= 5 and parts[1:3] == ["opensoom", "facilities"]
        body = await request.body()
        if request.method == "POST":
            try:
                is_cin = set(json.loads(body)) == {"m2m:cin"}
            except (ValueError, TypeError):
                is_cin = False
            media_type = headers.get("content-type", "").lower().replace(" ", "")
            allowed = in_facility and is_cin and media_type == "application/json;ty=4"
        else:
            allowed = in_facility
        if not allowed:
            return JSONResponse({"m2m:dbg": "Operation outside the facility worker interface"}, status_code=403,
                                headers={**response_headers, "X-M2M-RSC": "4103"})
        forwarded = {k: headers[k] for k in ("x-m2m-ri", "x-m2m-rvi", "accept", "content-type") if k in headers}
        forwarded["X-M2M-Origin"] = origin
        try:
            response = await app.state.upstream.request(request.method, upstream + "/" + path,
                headers=forwarded, params=request.query_params.multi_items(), content=body)
        except httpx.RequestError:
            return JSONResponse({"m2m:dbg": "Upstream CSE unavailable"}, status_code=502,
                                headers={**response_headers, "X-M2M-RSC": "5103"})
        allowed_headers = {k: v for k, v in response.headers.items() if k.startswith("x-m2m-") or k == "content-type"}
        return Response(response.content, status_code=response.status_code, headers=allowed_headers)

    return app
