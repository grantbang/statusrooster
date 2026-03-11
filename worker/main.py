"""
StatusRooster Regional Check Worker

Lightweight FastAPI service deployed to each GCP region.
Receives monitors to check via POST /check-batch, runs the checks
using checker_core, and returns results. No Firestore, no auth, no web UI.

Auth: X-Worker-Secret header must match WORKER_SECRET env var.
"""

import os
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from checker_core import (
    check_url_with_retry,
    check_json_api,
    check_ssl_certificate,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Configuration ──────────────────────────────────────────────────────────────

WORKER_REGION = os.getenv("WORKER_REGION", "unknown")
WORKER_SECRET = os.getenv("WORKER_SECRET", "")

# ── Shared httpx client ───────────────────────────────────────────────────────

_shared_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx.AsyncClient with connection pooling."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=50),
            timeout=httpx.Timeout(30.0),
        )
        logger.info(f"[worker:{WORKER_REGION}] Created shared httpx.AsyncClient")
    return _shared_client


# ── FastAPI App ────────────────────────────────────────────────────────────────

app = FastAPI(title=f"StatusRooster Worker ({WORKER_REGION})", docs_url=None, redoc_url=None)


class MonitorPayload(BaseModel):
    monitors: list[dict]


@app.on_event("shutdown")
async def shutdown():
    global _shared_client
    if _shared_client and not _shared_client.is_closed:
        await _shared_client.aclose()
        logger.info(f"[worker:{WORKER_REGION}] Closed shared httpx.AsyncClient")


@app.get("/health")
async def health():
    """Health check endpoint — no auth required (used by Cloud Run)."""
    return {"status": "healthy", "region": WORKER_REGION}


@app.post("/check-batch")
async def check_batch(request: Request):
    """Run checks for a batch of monitors and return results.
    
    Expects JSON body: {"monitors": [list of monitor dicts]}
    Auth: X-Worker-Secret header must match WORKER_SECRET env var.
    
    Returns: {"region": str, "results": [list of result dicts]}
    Each result: {monitor_id, region, is_up, status_code, response_ms, error}
    """
    # ── Auth ──
    secret = request.headers.get("X-Worker-Secret", "")
    if not WORKER_SECRET or secret != WORKER_SECRET:
        return JSONResponse(status_code=403, content={"error": "Invalid worker secret"})

    # ── Parse body ──
    try:
        body = await request.json()
        monitors = body.get("monitors", [])
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Invalid JSON: {e}"})

    if not monitors:
        return {"region": WORKER_REGION, "results": []}

    # ── Run checks concurrently ──
    client = await _get_client()
    tasks = [_check_single(m, client) for m in monitors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # ── Format results ──
    formatted = []
    for i, r in enumerate(results):
        monitor_id = monitors[i].get("id", f"unknown-{i}")
        if isinstance(r, Exception):
            formatted.append({
                "monitor_id": monitor_id,
                "region": WORKER_REGION,
                "is_up": False,
                "status_code": None,
                "response_ms": None,
                "error": str(r),
            })
        elif r is None:
            # Skipped (e.g., heartbeat monitor)
            continue
        else:
            formatted.append({
                "monitor_id": monitor_id,
                "region": WORKER_REGION,
                **r,
            })

    logger.info(f"[worker:{WORKER_REGION}] Checked {len(monitors)} monitors, {len(formatted)} results")
    return {"region": WORKER_REGION, "results": formatted}


async def _check_single(monitor: dict, client: httpx.AsyncClient) -> dict | None:
    """Run a single monitor check and return a normalized result dict.
    
    Returns: {is_up, status_code, response_ms, error} or None if skipped.
    """
    monitor_type = monitor.get("monitor_type", "http")

    try:
        if monitor_type == "heartbeat":
            # Heartbeats are passive — workers don't check them
            return None

        elif monitor_type == "ssl":
            # SSL checks are synchronous — run in executor
            ssl_domain = monitor.get("ssl_domain", "")
            if not ssl_domain:
                return {"is_up": False, "status_code": None, "response_ms": None, "error": "No ssl_domain"}

            loop = asyncio.get_event_loop()
            ssl_result = await loop.run_in_executor(None, check_ssl_certificate, ssl_domain)

            is_up = ssl_result.get("is_valid", False)
            return {
                "is_up": is_up,
                "status_code": 200 if is_up else None,
                "response_ms": 0,
                "error": ssl_result.get("error"),
            }

        elif monitor_type == "json_api":
            result = await check_json_api(
                url=monitor.get("url", ""),
                timeout=monitor.get("timeout", 10),
                expected_status_code=monitor.get("expected_status_code"),
                auth_header=monitor.get("auth_header", ""),
                assertions=monitor.get("json_assertions", []),
                client=client,
            )
            return {
                "is_up": result.get("is_up", False),
                "status_code": result.get("status_code"),
                "response_ms": result.get("response_ms"),
                "error": result.get("error"),
            }

        else:
            # HTTP monitor (default)
            result = await check_url_with_retry(
                url=monitor.get("url", ""),
                timeout=monitor.get("timeout", 10),
                expected_status_code=monitor.get("expected_status_code"),
                http_method=monitor.get("http_method", "GET"),
                follow_redirects=monitor.get("follow_redirects", True),
                basic_auth_user=monitor.get("basic_auth_user", ""),
                basic_auth_pass=monitor.get("basic_auth_pass", ""),
                bearer_token=monitor.get("bearer_token", ""),
                request_body=monitor.get("request_body", ""),
                request_content_type=monitor.get("request_content_type", ""),
                custom_headers=monitor.get("custom_headers", []),
                client=client,
            )
            return {
                "is_up": result.get("is_up", False),
                "status_code": result.get("status_code"),
                "response_ms": result.get("response_ms"),
                "error": result.get("error"),
            }

    except Exception as e:
        logger.error(f"[worker:{WORKER_REGION}] Check failed for {monitor.get('id')}: {e}")
        return {
            "is_up": False,
            "status_code": None,
            "response_ms": None,
            "error": str(e),
        }
