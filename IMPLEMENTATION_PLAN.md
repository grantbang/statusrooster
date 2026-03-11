# StatusRooster v2 — Implementation Plan
## Load this file into your codebase. Reference it in Copilot chat with: `@workspace See IMPLEMENTATION_PLAN.md`

**Build order:** Phase 2 → Phase 6 → Phase 1 → Phase 4 → Phase 3 → Phase 7
**Model guidance:** Use Sonnet for implementation. Switch to Opus for architecture decisions.

---

# PHASE 2: Multi-Region Monitoring
*The fun one. Distributed check workers across GCP regions.*
*Estimated effort: 15–25 hours across multiple sessions*

---

## 2.1 — Extract Shared Checker Core Module

> **Why:** The checker logic (HTTP requests, SSL checks, JSON assertions) needs to run in both the primary service AND the regional workers. Extract it into a shared module with zero Firestore dependencies.

### 2.1.1 — Create the checker_core package

- [x] Create directory `checker_core/`
- [x] Create file `checker_core/__init__.py`

### 2.1.2 — Move pure check functions from `app/services/checker.py` to `checker_core/__init__.py`

Move these functions exactly as-is (copy, don't modify logic):

- [x] `_PRIVATE_NETWORKS` list (the ipaddress network objects)
- [x] `validate_url_not_internal(url: str) -> None`
- [x] `check_url(url, timeout, expected_status_code, http_method, follow_redirects, basic_auth_user, basic_auth_pass, bearer_token, request_body, request_content_type, custom_headers, client) -> dict`
- [x] `check_url_with_retry(url, timeout, expected_status_code, http_method, follow_redirects, basic_auth_user, basic_auth_pass, bearer_token, request_body, request_content_type, custom_headers, client) -> dict`
- [x] `check_json_api(url, timeout, expected_status_code, auth_header, assertions, client) -> dict`
- [x] `_resolve_json_path(data, path) -> any`
- [x] `_evaluate_assertion(actual, operator, expected) -> bool`
- [x] `check_ssl_certificate(domain) -> dict`
- [x] `grab_ssl_info(url) -> dict`
- [x] `_check_keyword_expression(expression, body) -> bool`
- [x] `_check_threshold_condition(condition_str, actual_ms) -> bool`

### 2.1.3 — Move required imports into `checker_core/__init__.py`

The checker_core module needs these imports at the top:

- [x] `import httpx`
- [x] `import asyncio`
- [x] `import time`
- [x] `import ssl`
- [x] `import socket`
- [x] `import ipaddress`
- [x] `import random`
- [x] `import logging`
- [x] `from datetime import datetime, timezone`
- [x] `from urllib.parse import urlparse`

### 2.1.4 — Update `app/services/checker.py` to import from checker_core

- [x] Replace all moved function definitions with imports:

```python
from checker_core import (
    validate_url_not_internal,
    check_url,
    check_url_with_retry,
    check_json_api,
    check_ssl_certificate,
    grab_ssl_info,
    _check_keyword_expression,
    _check_threshold_condition,
    _resolve_json_path,
    _evaluate_assertion,
)
```

- [x] Remove the moved function bodies from `app/services/checker.py`
- [x] Keep in `app/services/checker.py` (do NOT move these — they depend on Firestore/alerts):
  - `_get_client()` and `_shared_client` and `close_client()`
  - `CHECK_CONCURRENCY` and `_check_semaphore`
  - `_percentile()`
  - `is_in_maintenance_window()`
  - `_check_single_monitor()` and `_check_single_monitor_inner()`
  - `check_monitor_now()`
  - `run_checks()`
  - All imports for Firestore models and alert services

### 2.1.5 — Verify extraction didn't break anything

- [x] Start the app locally: `uvicorn app.main:app --reload`
- [x] Confirm no import errors on startup
- [ ] Run a manual check-now on any monitor — confirm it still works
- [x] Run the security tests: `pytest tests/test_e2e.py::TestSecurity -v`
- [x] Confirm SSRF protection still works (the `validate_url_not_internal` import chain is intact)

### 2.1.6 — Create `checker_core/requirements.txt`

- [x] Create file with the dependencies checker_core needs (subset of main app):

```
httpx>=0.27.0
cryptography>=42.0.0
```

**Copilot prompt for 2.1:**
```
@workspace See IMPLEMENTATION_PLAN.md section 2.1. Extract the pure check functions from app/services/checker.py into a new checker_core/__init__.py module. Move only the functions listed in 2.1.2 — do NOT move anything that imports from app.database, app.models, or app.services.alerts. Update app/services/checker.py to import from checker_core instead. Keep all Firestore, incident, and alert logic in app/services/checker.py.
```

---

## 2.2 — Create the Worker Service

> **Why:** Lightweight Cloud Run service deployed to each region. Receives monitors to check, runs the checks, returns results. No Firestore, no auth, no web UI.

### 2.2.1 — Create worker directory structure

- [x] Create `worker/` directory at project root
- [x] Create `worker/__init__.py` (empty)
- [x] Create `worker/main.py`
- [x] Create `worker/Dockerfile`
- [x] Create `worker/requirements.txt`
- [x] Create `worker/.dockerignore`

### 2.2.2 — Create `worker/requirements.txt`

- [x] Contents:

```
fastapi>=0.110.0
uvicorn>=0.27.0
httpx>=0.27.0
cryptography>=42.0.0
pydantic>=2.0.0
```

### 2.2.3 — Create `worker/main.py`

- [x] FastAPI app with exactly two endpoints: `POST /check-batch` and `GET /health`
- [x] Environment variables: `WORKER_REGION` (string, e.g. "us-west1") and `WORKER_SECRET` (string, shared auth secret)
- [x] `POST /check-batch`:
  - [x] Accepts JSON body: `{"monitors": [list of monitor dicts]}`
  - [x] Authenticates via `X-Worker-Secret` header — returns 403 if doesn't match `WORKER_SECRET` env var
  - [x] For each monitor in the list:
    - [x] Read `monitor_type` field to determine check type
    - [x] If `monitor_type == "http"`: call `check_url_with_retry()` from `checker_core` with all HTTP fields (url, timeout, expected_status_code, http_method, follow_redirects, basic_auth_user, basic_auth_pass, bearer_token, request_body, request_content_type, custom_headers)
    - [x] If `monitor_type == "json_api"`: call `check_json_api()` from `checker_core` with fields (url, timeout, expected_status_code, auth_header, json_assertions)
    - [x] If `monitor_type == "ssl"`: call `check_ssl_certificate()` from `checker_core` with ssl_domain. Run in executor (it's synchronous). Normalize result to `{is_up, status_code, response_ms}`
    - [x] If `monitor_type == "heartbeat"`: skip (heartbeats are passive, not active checks). Do not include in results.
    - [x] Wrap each check in try/except — if a check throws, return `{is_up: false, error: str(e)}` for that monitor
  - [x] Returns JSON: `{"region": WORKER_REGION, "results": [list of result dicts]}`
  - [x] Each result dict: `{monitor_id, region, is_up, status_code, response_ms, error}`
- [x] `GET /health`:
  - [x] Returns: `{"status": "healthy", "region": WORKER_REGION}`
  - [x] No auth required (used by Cloud Run health checks)
- [x] Create a shared `httpx.AsyncClient` with connection pooling at module level (same pattern as primary service: lazy init, 100 max connections, 50 keepalive)
- [x] Import all check functions from `checker_core`

### 2.2.4 — Create `worker/Dockerfile`

- [x] Base image: `python:3.12-slim`
- [x] Working directory: `/app`
- [x] Copy `checker_core/` into the image
- [x] Copy `worker/requirements.txt` and install
- [x] Copy `worker/main.py`
- [x] CMD: `uvicorn main:app --host 0.0.0.0 --port 8080`

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY checker_core/ ./checker_core/
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY worker/main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 2.2.5 — Create `worker/.dockerignore`

- [x] Contents: `__pycache__`, `.git`, `.env`, `venv`, `*.pyc`

### 2.2.6 — Test worker locally

- [ ] Build: `cd worker && docker build -t sr-worker .`
- [ ] Run: `docker run -p 8081:8080 -e WORKER_REGION=local -e WORKER_SECRET=test123 sr-worker`
- [ ] Test health: `curl http://localhost:8081/health`
- [ ] Confirm: returns `{"status": "healthy", "region": "local"}`
- [ ] Test check-batch:

```bash
curl -X POST http://localhost:8081/check-batch \
  -H "Content-Type: application/json" \
  -H "X-Worker-Secret: test123" \
  -d '{"monitors": [{"id": "test1", "url": "https://httpstat.us/200", "monitor_type": "http", "timeout": 10}]}'
```

- [ ] Confirm: returns result with `is_up: true`, `status_code: 200`, `response_ms > 0`
- [ ] Test auth rejection: same request without `X-Worker-Secret` header → returns 403
- [ ] Test SSRF protection: send monitor with `url: "http://169.254.169.254"` → result has `is_up: false`

**Copilot prompt for 2.2:**
```
@workspace See IMPLEMENTATION_PLAN.md section 2.2. Create the worker service in worker/main.py. It's a FastAPI app with two endpoints: POST /check-batch (authenticated via X-Worker-Secret header) and GET /health. It imports check functions from checker_core and runs them against a list of monitors. See 2.2.3 for the exact spec of each endpoint. Also create worker/Dockerfile, worker/requirements.txt, and worker/.dockerignore per 2.2.4 and 2.2.5.
```

---

## 2.3 — Multi-Region Configuration

> **Why:** The primary service needs to know where the workers are and which regions each plan can use.

### 2.3.1 — Add worker config to `app/config.py`

- [x] Add environment variables:

```python
# Multi-region check workers
WORKER_SECRET: str = os.getenv("WORKER_SECRET", "")
WORKER_URL_US_EAST1: str = os.getenv("WORKER_URL_US_EAST1", "")  # Primary (empty = run locally)
WORKER_URL_US_WEST1: str = os.getenv("WORKER_URL_US_WEST1", "")
WORKER_URL_EU_WEST1: str = os.getenv("WORKER_URL_EU_WEST1", "")
WORKER_URL_ASIA_EAST1: str = os.getenv("WORKER_URL_ASIA_EAST1", "")
```

### 2.3.2 — Add region constants to `app/services/checker.py`

- [x] Add at the top of the file, after imports:

```python
from app.config import settings

# Region configuration
WORKER_REGIONS = {
    "us-east1": settings.WORKER_URL_US_EAST1,
    "us-west1": settings.WORKER_URL_US_WEST1,
    "europe-west1": settings.WORKER_URL_EU_WEST1,
    "asia-east1": settings.WORKER_URL_ASIA_EAST1,
}

# All users get the same 4 regions (australia-southeast1 dropped — GCP quota)
CHECK_REGIONS = ["us-east1", "us-west1", "europe-west1", "asia-east1"]
```

### 2.3.3 — Add `.env.example` entries

- [x] Add to `.env.example`:

```
# Multi-region workers (leave empty to disable multi-region)
WORKER_SECRET=
WORKER_URL_US_EAST1=
WORKER_URL_US_WEST1=
WORKER_URL_EU_WEST1=
WORKER_URL_ASIA_EAST1=
```

### 2.3.4 — Add `regions` field to monitor model

- [x] In `app/models/monitor.py` `create_monitor()`, add to `monitor_data`:

```python
"regions": [],  # Populated after checks — list of regions that checked this monitor
```

**Copilot prompt for 2.3:**
```
@workspace See IMPLEMENTATION_PLAN.md section 2.3. Add multi-region worker configuration to app/config.py (5 worker URL env vars + WORKER_SECRET). Add WORKER_REGIONS dict, FREE_REGIONS list, and PRO_REGIONS list to app/services/checker.py. Update .env.example with the new vars.
```

---

## 2.4 — Build the Multi-Region Dispatcher

> **Why:** This is the brain — it decides which regions to check from, dispatches to workers, and aggregates results. This is the most complex piece. Take your time.

### 2.4.1 — Create helper: serialize monitor for worker

- [x] Add to `app/services/checker.py`:

```python
def _serialize_monitor_for_worker(monitor: dict) -> dict:
    """Strip a monitor dict down to only fields needed for checking.
    Removes Firestore metadata, user info, and stats — keeps only
    the fields that checker_core functions need to run a check."""
    return {
        "id": monitor.get("id"),
        "url": monitor.get("url", ""),
        "monitor_type": monitor.get("monitor_type", "http"),
        "timeout": monitor.get("timeout", 10),
        "expected_status_code": monitor.get("expected_status_code"),
        "http_method": monitor.get("http_method", "GET"),
        "follow_redirects": monitor.get("follow_redirects", True),
        "basic_auth_user": monitor.get("basic_auth_user", ""),
        "basic_auth_pass": monitor.get("basic_auth_pass", ""),
        "bearer_token": monitor.get("bearer_token", ""),
        "request_body": monitor.get("request_body", ""),
        "request_content_type": monitor.get("request_content_type", ""),
        "custom_headers": monitor.get("custom_headers", []),
        "auth_header": monitor.get("auth_header", ""),
        "json_assertions": monitor.get("json_assertions", []),
        "keyword": monitor.get("keyword", ""),
        "ssl_domain": monitor.get("ssl_domain", ""),
    }
```

### 2.4.2 — Create helper: get user plan (cached)

- [x] The existing `_get_user_plan()` is in `app/services/alerts.py`. Either import it or create a lightweight version in checker.py:

```python
# Simple plan cache to avoid Firestore reads on every check
_plan_cache: dict[str, tuple[str, float]] = {}  # {user_id: (plan, timestamp)}
_PLAN_CACHE_TTL = 300  # 5 minutes

def _get_user_plan_cached(user_id: str) -> str:
    """Get user plan with 5-minute cache to reduce Firestore reads."""
    import time
    now = time.monotonic()
    cached = _plan_cache.get(user_id)
    if cached and (now - cached[1]) < _PLAN_CACHE_TTL:
        return cached[0]
    try:
        db = get_db()
        user_ref = db.collection("users").document(user_id).get()
        plan = user_ref.to_dict().get("plan", "free") if user_ref.exists else "free"
    except Exception:
        plan = "free"
    _plan_cache[user_id] = (plan, now)
    return plan
```

### 2.4.3 — Create helper: dispatch to a single worker region

- [x] Add to `app/services/checker.py`:

```python
async def _dispatch_to_worker(region: str, monitors: list[dict]) -> dict | None:
    """Send a batch of monitors to a regional worker and return results.
    
    Returns: {"region": str, "results": [list of result dicts]} or None on failure.
    Timeout: 30 seconds per worker call.
    """
    worker_url = WORKER_REGIONS.get(region, "")
    if not worker_url:
        return None
    
    try:
        client = await _get_client()
        resp = await client.post(
            f"{worker_url}/check-batch",
            json={"monitors": monitors},
            headers={
                "X-Worker-Secret": settings.WORKER_SECRET,
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning(f"[checker] Worker {region} returned {resp.status_code}: {resp.text[:200]}")
            return None
    except httpx.TimeoutException:
        logger.warning(f"[checker] Worker {region} timed out")
        return None
    except Exception as e:
        logger.warning(f"[checker] Worker {region} failed: {e}")
        return None
```

### 2.4.4 — Create the aggregation function

- [x] Add to `app/services/checker.py`:

```python
def _aggregate_multi_region_results(monitor: dict, local_result: dict, 
                                      worker_results: list[dict]) -> dict:
    """Combine results from local check + regional workers.
    
    Aggregation rules:
    1. is_up = True if MAJORITY of regions report UP
       (e.g., 3 of 4 regions)
       This prevents a single-region blip from triggering a false incident.
    2. response_ms = average across all regions
    3. response_ms_by_region = dict of {region: ms} for UI display
    4. status_code = from primary region (us-east1 / local)
    5. regions_checked = total number of regions that responded
    6. regions_up = number of regions that reported UP
    
    Args:
        monitor: the monitor dict
        local_result: result dict from the local check (primary region)
        worker_results: list of worker response dicts, each containing
                       {"region": str, "results": [{"monitor_id", "is_up", ...}]}
    
    Returns:
        Merged result dict compatible with the existing run_checks() processing.
        Same shape as what _check_single_monitor_inner() returns, but with
        extra fields: response_ms_by_region, regions_checked, regions_up.
    """
    all_results = []
    response_by_region = {}
    
    # Add local result
    local_is_up = local_result.get("result", {}).get("is_up", False)
    local_ms = local_result.get("result", {}).get("response_ms")
    all_results.append({"region": "us-east1", "is_up": local_is_up, "response_ms": local_ms})
    if local_ms and local_ms > 0:
        response_by_region["us-east1"] = local_ms
    
    # Add worker results
    for wr in worker_results:
        if not wr:
            continue
        region = wr.get("region", "unknown")
        for r in wr.get("results", []):
            if r.get("monitor_id") == monitor.get("id"):
                all_results.append({
                    "region": region,
                    "is_up": r.get("is_up", False),
                    "response_ms": r.get("response_ms"),
                })
                ms = r.get("response_ms")
                if ms and ms > 0:
                    response_by_region[region] = ms
    
    # Majority vote
    total = len(all_results)
    up_count = sum(1 for r in all_results if r["is_up"])
    majority_up = up_count > (total / 2)
    
    # Average response time
    response_times = [r["response_ms"] for r in all_results if r.get("response_ms") and r["response_ms"] > 0]
    avg_ms = round(sum(response_times) / len(response_times), 2) if response_times else None
    
    # Build merged result — start with local_result structure, overlay multi-region data
    merged = dict(local_result)
    merged["result"] = dict(local_result.get("result", {}))
    merged["result"]["is_up"] = majority_up
    merged["result"]["response_ms"] = avg_ms
    merged["result"]["response_ms_by_region"] = response_by_region
    merged["result"]["regions_checked"] = total
    merged["result"]["regions_up"] = up_count
    
    return merged
```

### 2.4.5 — Create the multi-region check function

- [x] Add to `app/services/checker.py`:

```python
async def _check_single_monitor_multi_region(monitor: dict, now: datetime) -> dict | None:
    """Check a monitor from multiple regions and aggregate results.
    
    Flow:
    1. Determine which regions are active (all users get the same 4 regions)
    2. Run local check (us-east1) — always happens, even if workers are down
    3. Dispatch to remote workers concurrently
    4. Wait for all results (with 30s timeout per worker)
    5. Aggregate using majority vote
    6. Return merged result dict
    
    Falls back to local-only check if:
    - No workers are configured (WORKER_SECRET empty or no WORKER_URLs set)
    - Monitor type is heartbeat (passive, not active)
    - Monitor type is ssl (certs are global, multi-region adds nothing)
    - All workers fail (local result is still used)
    """
    mtype = monitor.get("monitor_type", "http")
    
    # Heartbeat and SSL don't benefit from multi-region
    if mtype in ("heartbeat", "ssl"):
        return await _check_single_monitor_inner(monitor, now)
    
    # Check if multi-region is configured
    if not settings.WORKER_SECRET:
        return await _check_single_monitor_inner(monitor, now)
    
    # Determine active regions (all users get the same 4 regions)
    active_regions = [r for r in CHECK_REGIONS if r == "us-east1" or WORKER_REGIONS.get(r)]
    
    # If only primary region is available, fall back to local
    if len(active_regions) <= 1:
        return await _check_single_monitor_inner(monitor, now)
    
    # Step 1: Run local check (always, as baseline)
    local_result = await _check_single_monitor_inner(monitor, now)
    if local_result is None:
        return None  # Monitor was skipped (paused, misconfigured, etc.)
    
    # Step 2: Dispatch to remote workers concurrently
    remote_regions = [r for r in active_regions if r != "us-east1"]
    serialized = [_serialize_monitor_for_worker(monitor)]
    
    worker_tasks = [_dispatch_to_worker(r, serialized) for r in remote_regions]
    worker_results = await asyncio.gather(*worker_tasks, return_exceptions=True)
    
    # Filter out exceptions and None results
    valid_worker_results = [
        r for r in worker_results 
        if r is not None and not isinstance(r, Exception)
    ]
    
    # Step 3: Aggregate
    if not valid_worker_results:
        # All workers failed — use local result only, but tag it
        local_result.setdefault("result", {})["regions_checked"] = 1
        local_result["result"]["regions_up"] = 1 if local_result["result"].get("is_up") else 0
        local_result["result"]["response_ms_by_region"] = {"us-east1": local_result["result"].get("response_ms")}
        return local_result
    
    return _aggregate_multi_region_results(monitor, local_result, valid_worker_results)
```

### 2.4.6 — Wire multi-region into the check pipeline

- [x] In `app/services/checker.py`, update `_check_single_monitor()`:

```python
async def _check_single_monitor(monitor: dict, now: datetime) -> dict | None:
    """Perform the network check for a single monitor (with concurrency limiting).
    Routes to multi-region if configured, otherwise local-only."""
    async with _check_semaphore:
        # Use multi-region if workers are configured
        if settings.WORKER_SECRET and monitor.get("monitor_type") in ("http", "json_api"):
            return await _check_single_monitor_multi_region(monitor, now)
        return await _check_single_monitor_inner(monitor, now)
```

### 2.4.7 — Update `run_checks()` to handle multi-region result fields

- [x] In the Phase 3 processing loop in `run_checks()`, update the `monitor_updates` dict to store region data:

```python
# After the existing monitor_updates assignments, add:
regions_checked = result.get("regions_checked", 1)
regions_up = result.get("regions_up", regions_checked if result["is_up"] else 0)
response_by_region = result.get("response_ms_by_region", {})

monitor_updates["last_regions_checked"] = regions_checked
monitor_updates["last_regions_up"] = regions_up
monitor_updates["last_response_by_region"] = response_by_region
```

### 2.4.8 — Verify multi-region works locally (without real workers)

- [x] With no `WORKER_SECRET` set, confirm the app still works exactly as before (falls back to local-only checks)
- [ ] Run the E2E tests: `pytest tests/test_e2e.py -v --asyncio-mode=auto -k "not slow"`
- [ ] All tests should pass — multi-region is additive, not breaking

**Copilot prompt for 2.4:**
```
@workspace See IMPLEMENTATION_PLAN.md section 2.4. Build the multi-region dispatcher in app/services/checker.py. Create these functions in order: _serialize_monitor_for_worker (2.4.1), _get_user_plan_cached (2.4.2), _dispatch_to_worker (2.4.3), _aggregate_multi_region_results (2.4.4), _check_single_monitor_multi_region (2.4.5). Then update _check_single_monitor to route through the multi-region path when WORKER_SECRET is configured (2.4.6). Finally update run_checks() to store the region data on each monitor update (2.4.7). The multi-region path should gracefully fall back to local-only when no workers are configured.
```

---

## 2.5 — Update Check Model for Per-Region Data

### 2.5.1 — Update `create_check()` in `app/models/check.py`

- [x] Add optional parameters: `regions_checked: int = 1`, `regions_up: int = 1`, `response_ms_by_region: dict | None = None`
- [x] Store these in the check document

### 2.5.2 — Update `create_checks_batch()` in `app/models/check.py`

- [x] Accept and store the same regional fields in batch writes

### 2.5.3 — Update the batch accumulation in `run_checks()`

- [x] In `app/services/checker.py`, where `check_batch.append(...)` is called, include the region data:

```python
check_batch.append({
    "monitor_id": monitor["id"],
    "status_code": result["status_code"],
    "response_ms": result["response_ms"],
    "is_up": result["is_up"],
    "regions_checked": result.get("regions_checked", 1),
    "regions_up": result.get("regions_up", 1 if result["is_up"] else 0),
    "response_ms_by_region": result.get("response_ms_by_region", {}),
})
```

**Copilot prompt for 2.5:**
```
@workspace See IMPLEMENTATION_PLAN.md section 2.5. Update app/models/check.py to accept and store multi-region data: regions_checked (int), regions_up (int), response_ms_by_region (dict). Update both create_check() and create_checks_batch(). Then update the check_batch.append() call in app/services/checker.py run_checks() to include these fields.
```

---

## 2.6 — Monitor Detail UI — Per-Region Display

### 2.6.1 — Pass region data to monitor detail template

- [x] In `app/routers/pages.py` `monitor_detail()`, add to the template context:

```python
# Region response data (from last check)
"last_response_by_region": monitor.get("last_response_by_region", {}),
"last_regions_checked": monitor.get("last_regions_checked", 1),
"last_regions_up": monitor.get("last_regions_up", 0),
```

### 2.6.2 — Add region response section to `app/templates/monitor_detail.html`

- [x] Add a "Response by Region" card below the response time chart (only shown if `last_regions_checked > 1`):
- [x] For each region, show:
  - Region name (friendly: "US East", "US West", "Europe", "Asia")
  - Response time in ms
  - A simple bar visualization (width proportional to response time)
  - Green dot if that region reported UP, red if DOWN
- [x] All 4 regions shown for all users (no Pro gating)
- [x] Show average across all regions at the bottom

### 2.6.3 — Update dashboard cards (optional enhancement)

- [ ] On the dashboard monitor list, if multi-region is active, show the number of regions: e.g., "3/3 regions UP" or "2/3 regions UP" next to the status indicator
- [ ] This is optional — skip if it clutters the UI

**Copilot prompt for 2.6:**
```
@workspace See IMPLEMENTATION_PLAN.md section 2.6. Add a "Response by Region" section to app/templates/monitor_detail.html that shows per-region response times when multi-region is active (last_regions_checked > 1). Show each region as a row with region name, response time in ms, a colored bar, and up/down indicator. For Pro-only regions not available to free users, show a "Pro" badge. Pass last_response_by_region, last_regions_checked, and last_regions_up from the pages.py monitor_detail route to the template.
```

---

## 2.7 — Deploy Workers

> **Note:** This is infrastructure work, not code. Do this manually or with a deploy script.

### 2.7.1 — Generate a strong WORKER_SECRET

- [x] Run: `python -c "import secrets; print(secrets.token_hex(32))"`
- [x] Save the value — you'll use it for all workers and the primary service

### 2.7.2 — Deploy worker to us-west1

- [x] `cd` to project root (where `worker/` and `checker_core/` are)
- [x] Built image via Cloud Build: `us-central1-docker.pkg.dev/statusrooster/cloud-run-source-deploy/statusrooster-worker:latest`
- [x] Deployed from image to us-west1
- [x] URL: `https://statusrooster-worker-286329122172.us-west1.run.app`
- [x] Test: `curl /health` → `{"status":"healthy","region":"us-west1"}` ✅

### 2.7.3 — Deploy worker to europe-west1

- [x] Deployed from same image to europe-west1
- [x] URL: `https://statusrooster-worker-286329122172.europe-west1.run.app`
- [x] Test health endpoint ✅

### 2.7.4 — Deploy worker to asia-east1

- [x] Deployed from same image to asia-east1
- [x] URL: `https://statusrooster-worker-286329122172.asia-east1.run.app`
- [x] Test health endpoint ✅

### 2.7.5 — Australia region (dropped)

- [x] ⚠️ Dropped — GCP quota exceeded for australia-southeast1. Decision: all users get the same 4 regions (us-east1, us-west1, europe-west1, asia-east1). No plan-based region gating.
- [x] Removed `WORKER_URL_AU_SE1` from config.py, .env.example, and checker.py
- [x] Replaced `FREE_REGIONS` / `PRO_REGIONS` with single `CHECK_REGIONS` list
- [x] Removed `_get_user_plan_cached()` (no longer needed)
- [x] Removed Australia row and "Pro" badge upsell from monitor_detail.html

### 2.7.6 — Update primary service with worker URLs

- [x] Set WORKER_SECRET, WORKER_URL_US_WEST1, WORKER_URL_EU_WEST1, WORKER_URL_ASIA_EAST1 on primary Cloud Run service (us-east1)
- [x] Verified env vars are set correctly via `gcloud run services describe`
- [x] Verified workers reject requests without valid X-Worker-Secret (403)
- [x] Fixed `check_monitor_now()` to route through multi-region path (was calling `_check_single_monitor_inner` directly)
- [x] Redeployed primary service with fix

### 2.7.7 — End-to-end verification

- [x] All 3 worker health endpoints respond correctly
- [x] Workers execute real checks (google.com: 81ms from us-west1)
- [x] Workers reject unauthenticated requests (403)
- [x] SSRF protection active on workers (blocked httpstat.us → 127.0.0.1)
- [x] Created test HTTP monitor → "Check now" → "Response by Region" shows: US East 95ms, US West 61ms, Europe 16ms, Asia 63ms. Average 58ms across 4 regions. ✅
- [x] Fixed `check_monitor_now()` to use multi-region path + persist region data to monitor doc

---

# PHASE 6: Infrastructure Hardening
*Do this alongside or right after Phase 2*

---

## 6.1 — Cursor Pagination for get_due_monitors()

- [x] In `app/models/monitor.py`, replace the current `get_due_monitors()` with cursor-paginated version using `.stream()` and `start_after`
- [x] Add `import logging` and `logger = logging.getLogger(__name__)` at top of file
- [x] Verify: restart app, trigger a cron cycle, confirm monitors are still checked

```python
def get_due_monitors(db) -> list[dict]:
    """Get all non-paused monitors using Firestore cursor pagination.
    
    Fetches in batches of 500 using start_after cursors to handle
    collections larger than 500 documents without hitting memory limits.
    """
    monitors = []
    query = db.collection(COLLECTION).where("paused", "==", False)
    batch_size = 500
    last_doc = None  # This must be the raw Firestore DocumentSnapshot, not a dict

    while True:
        q = query.limit(batch_size)
        if last_doc:
            q = q.start_after(last_doc)

        docs = list(q.stream())  # Use .stream() for cursor support
        if not docs:
            break

        for doc in docs:
            m = doc.to_dict()
            m["id"] = doc.id
            monitors.append(m)

        last_doc = docs[-1]  # Pass the raw DocumentSnapshot to start_after

        if len(docs) < batch_size:
            break  # Last page

        logger.info(f"[monitor] get_due_monitors: fetched batch of {len(docs)}, total so far: {len(monitors)}")

    logger.info(f"[monitor] get_due_monitors: loaded {len(monitors)} monitors total")
    return monitors
```

- [ ] Add `import logging` and `logger = logging.getLogger(__name__)` at top of file if not present
- [ ] Verify: restart app, trigger a cron cycle, confirm monitors are still checked

**Copilot prompt for 6.1:**
```
@workspace See IMPLEMENTATION_PLAN.md section 6.1. Replace get_due_monitors() in app/models/monitor.py with a cursor-paginated version that fetches in batches of 500 using start_after. Use .stream() not .get() for cursor support. The start_after argument must be the raw Firestore DocumentSnapshot object, not a dict. Log the total count after loading.
```

---

## 6.2 — Rate Limiter Memory Leak Fix

- [x] In `app/routers/pages.py`, add a cleanup counter near the `_url_check_rate` dict
- [x] Inside `public_url_check()`, add periodic cleanup that runs every 100 requests and removes IPs whose last hit is older than 5 minutes

```python
_url_check_rate: dict[str, list] = {}
_url_check_cleanup_counter = 0
_URL_CHECK_LIMIT = 10
_URL_CHECK_WINDOW = 60
```

- [ ] Inside `public_url_check()`, after the line `_url_check_rate[client_ip] = hits`, add:

```python
# Periodic cleanup of stale IPs to prevent memory leak
global _url_check_cleanup_counter
_url_check_cleanup_counter += 1
if _url_check_cleanup_counter >= 100:
    _url_check_cleanup_counter = 0
    stale_cutoff = now_ts - (_URL_CHECK_WINDOW * 5)
    stale_ips = [ip for ip, h in _url_check_rate.items() if not h or h[-1] < stale_cutoff]
    for ip in stale_ips:
        del _url_check_rate[ip]
```

**Copilot prompt for 6.2:**
```
@workspace See IMPLEMENTATION_PLAN.md section 6.2. Fix the memory leak in the _url_check_rate dict in app/routers/pages.py public_url_check(). Add a cleanup counter that runs every 100 requests and removes IPs whose last hit is older than 5 minutes.
```

---

## 6.3 — Backfill Heartbeat Ping Tokens

- [x] Create `scripts/backfill_ping_tokens.py` (already existed — supports --dry-run default and --execute)
- [x] Test dry run: `python scripts/backfill_ping_tokens.py`
- [x] Execute: `python scripts/backfill_ping_tokens.py --execute`

```python
"""
Backfill ping_token for heartbeat monitors created before the token feature.

Usage:
  python scripts/backfill_ping_tokens.py           # Dry run (shows what would change)
  python scripts/backfill_ping_tokens.py --execute  # Actually update Firestore
"""
import secrets
import sys
from google.cloud import firestore

def main():
    dry_run = "--execute" not in sys.argv
    if dry_run:
        print("DRY RUN MODE — no changes will be made. Use --execute to apply.\n")

    db = firestore.Client(project="statusrooster")
    docs = (
        db.collection("monitors")
        .where("monitor_type", "==", "heartbeat")
        .stream()
    )

    count = 0
    for doc in docs:
        m = doc.to_dict()
        if not m.get("ping_token"):
            token = secrets.token_urlsafe(32)
            new_url = f"https://statusrooster.com/api/ping/{doc.id}?token={token}"

            if dry_run:
                print(f"  [DRY RUN] {m.get('name', doc.id)}: would set ping_token={token[:12]}...")
            else:
                doc.reference.update({
                    "ping_token": token,
                    "url": new_url,
                    "ping_url": new_url,
                })
                print(f"  [UPDATED] {m.get('name', doc.id)}: {new_url}")
            count += 1

    print(f"\n{'Would update' if dry_run else 'Updated'} {count} monitors")
    if dry_run and count > 0:
        print("Run with --execute to apply changes")

if __name__ == "__main__":
    main()
```

- [ ] Test dry run: `python scripts/backfill_ping_tokens.py`
- [ ] Execute: `python scripts/backfill_ping_tokens.py --execute`

**Copilot prompt for 6.3:**
```
@workspace See IMPLEMENTATION_PLAN.md section 6.3. Create scripts/backfill_ping_tokens.py that queries all heartbeat monitors without a ping_token field, generates one using secrets.token_urlsafe(32), and updates the monitor doc with the new ping_token and ping_url. Support --dry-run (default) and --execute modes.
```

---

## 6.4 — Firestore Composite Indexes

- [x] Create `firestore.indexes.json` at project root
- [ ] Deploy indexes: `firebase deploy --only firestore:indexes` (or via GCP console)

```json
{
  "indexes": [
    {
      "collectionGroup": "monitors",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "paused", "order": "ASCENDING"},
        {"fieldPath": "created_at", "order": "ASCENDING"}
      ]
    },
    {
      "collectionGroup": "checks",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "monitor_id", "order": "ASCENDING"},
        {"fieldPath": "timestamp", "order": "DESCENDING"}
      ]
    },
    {
      "collectionGroup": "checks",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "monitor_id", "order": "ASCENDING"},
        {"fieldPath": "timestamp", "order": "ASCENDING"}
      ]
    },
    {
      "collectionGroup": "incidents",
      "queryScope": "COLLECTION",
      "fields": [
        {"fieldPath": "monitor_id", "order": "ASCENDING"},
        {"fieldPath": "started_at", "order": "DESCENDING"}
      ]
    }
  ]
}
```

- [ ] Deploy indexes: `firebase deploy --only firestore:indexes` (or via GCP console)

---

# PHASE 1: Free Tier Unlocking
*Do this after Phase 2 so multi-region is ready to advertise*

---

## 1.1 — Update Plan Limit Constants

- [x] `app/routers/api_v1.py`: change `FREE_MONITOR_LIMIT = 5` → `100`, `PRO_MONITOR_LIMIT = 250` → `500`
- [x] `app/routers/monitors.py`: change `FREE_MONITOR_LIMIT = 5` → `100`, `PRO_MONITOR_LIMIT = 250` → `500`
- [x] Search entire codebase for any other hardcoded `5` in plan limit contexts or `250` for Pro
- [x] Verify: `grep -rn "FREE_MONITOR_LIMIT\|PRO_MONITOR_LIMIT\|plan.*5\|limit.*250" app/`

---

## 1.2 — Remove Free-Tier Feature Gates

For each file below, find every `if plan == "free"` or `if user.get("plan", "free") == "free"` or `if plan != "free"` block that gates a feature, and update it according to the new rules.

### Features to UNLOCK for free:

- [x] **Slack webhooks** — `app/routers/api_v1.py`: in `api_create_monitor()`, remove the `if plan != "free"` gate on `alert_slack_webhook`. Let all plans set it.
- [x] **Slack webhooks** — `app/routers/monitors.py`: in `create()`, remove `if user.get("plan", "free") != "free" else ""` on `alert_slack_webhook`. Pass it through for all plans.
- [x] **Slack webhooks** — `app/routers/pages.py`: in `add_monitor()`, same — remove the free gate on `alert_slack_webhook`
- [x] **Slack webhooks** — `app/routers/api_v1.py`: in `api_update_monitor()`, remove the 403 on updating `alert_slack_webhook` for free users
- [x] **Slack webhooks** — `app/routers/pages.py`: in `edit_monitor_submit()`, remove the free gate on `alert_slack_webhook`
- [x] **Webhook URL** — same pattern across all 5 locations (api_v1 create, api_v1 update, monitors create, pages add, pages edit)
- [x] **Maintenance windows** — same pattern across all locations (api_v1 create, api_v1 update, pages add, pages edit)
- [x] **Custom headers** — same pattern across all locations
- [x] **Basic Auth** — same pattern across all locations
- [x] **Custom check interval** — UPDATE the logic (don't just remove the gate):
  - Free: 60s–300s, default 60s
  - Pro: 30s–300s, default 30s
  - Update in `app/models/monitor.py` `create_monitor()` and in `api_v1.py` `api_update_monitor()` and `pages.py` `edit_monitor_submit()`

### Features to KEEP as Pro-only:

- [x] **SMS alerts** — keep all existing gates on `alert_sms`. Twilio costs real money per message.
- [x] **Aggregate status page** — keep the `if plan == "free": raise 404` in `app/routers/pages.py` `aggregate_status_page()`
- [x] **Check interval < 60s** — Pro can go to 30s, free minimum is 60s

### Status page limit update:

- [x] Change `public_limit = 10 if plan == "pro" else 1` to `public_limit = 10` everywhere:
  - `app/routers/api_v1.py` — `api_create_monitor()` and `api_update_monitor()`
  - `app/routers/pages.py` — `add_monitor()` and `edit_monitor_submit()`

**Copilot prompt for 1.2:**
```
@workspace See IMPLEMENTATION_PLAN.md section 1.2. Remove all free-tier gates on: Slack webhooks, webhook URLs, maintenance windows, custom headers, and Basic Auth. These features are now free for all users. Keep SMS alerts (alert_sms) as Pro-only. Update check interval logic: free users get 60s-300s (default 60s), Pro users get 30s-300s (default 30s). Update public status page limit to 10 for all plans. Search all files in app/routers/ and app/models/monitor.py for plan-gating logic and update each one.
```

---

## 1.3 — Update UI Templates

- [x] `app/templates/pricing.html` — rewrite with new tier comparison (100 free monitors, all features)
- [x] `app/templates/add_monitor.html` — remove all "PRO" badges and disabled states on: Slack, webhooks, maintenance windows, custom headers, auth. Keep "PRO" only on SMS and 30s interval.
- [x] `app/templates/edit_monitor.html` — same removals
- [x] `app/templates/dashboard.html` — remove upgrade CTAs for features that are now free
- [x] `app/templates/settings.html` — update plan description text (reviewed: no changes needed, upgrade link points to updated pricing page)

---

## 1.4 — Update Tests

- [x] Update `tests/test_e2e.py` `TestPlanEnforcement`:
  - [x] E.2 (free slack stripped) — should now PASS (slack allowed on free). Change assertion to expect webhook IS stored.
  - [x] E.4 (free webhook stripped) — same, expect it's stored now
  - [x] E.5 (free basic auth stripped) — same, expect it's stored now
  - [x] E.6 (free update slack 403) — should now succeed (200). Change assertion.
  - [x] E.7 (free update webhook 403) — should now succeed (200). Change assertion.
  - [x] E.9 (free update maintenance 403) — should now succeed (200). Change assertion.
  - [x] E.10 (free update basic auth 403) — should now succeed (200). Change assertion.
  - [x] E.1 (free 6th monitor limit) — change to test 101st monitor limit
  - [x] E.8 (free update interval 403) — update: free can set 60s+ but not below 60s. Test that setting 30s on free is rejected.
  - [x] Add new test: free user can set check_interval=60 (should succeed)
  - [x] Add new test: free user cannot set check_interval=30 (should fail)
  - [x] E.11 (free 2nd public page) — change to test 11th public page

---

# PHASE 4: Custom Branding
# PHASE 3: Data Retention
# PHASE 7: Viral Loop

*These are smaller phases. I've kept them concise since the whitepaper already has the full spec. Reference the whitepaper for implementation details.*

---

## Phase 4 Checklist — Custom Branding

- [ ] 4.1 Add branding fields to user model: `status_page_logo_url`, `status_page_brand_name`, `status_page_accent_color`, `hide_powered_by` (default False)
- [ ] 4.2 Add "Status Page Branding" section to `/settings` (Pro only): logo URL input, brand name input, accent color picker, "hide powered by" toggle
- [ ] 4.3 Create POST endpoint for saving branding settings
- [ ] 4.4 In `public_status_page()` and `aggregate_status_page()`: look up owner's branding settings, pass to template
- [ ] 4.5 Update `status_page.html`: use branding.brand_name, branding.accent_color, branding.logo_url. Only show "Powered by StatusRooster" if `branding.show_powered_by` is True.
- [ ] 4.6 Update `aggregate_status.html`: same branding logic
- [ ] 4.7 Verify: free user sees "Powered by" always. Pro user can toggle it off.

---

## Phase 3 Checklist — Data Retention

- [ ] 3.1 Add to `app/config.py`: `FREE_DATA_RETENTION_DAYS = 30`, `PRO_DATA_RETENTION_DAYS = 90`
- [ ] 3.2 Create helper `get_retention_cutoff(plan: str) -> datetime` in `app/models/check.py`
- [ ] 3.3 In `get_recent_checks()`, `get_daily_uptime()`, and `monitor_checks_api()`: apply retention cutoff based on the monitor owner's plan
- [ ] 3.4 Create `scripts/cleanup_old_checks.py`: query all monitors, determine owner plan, delete checks older than retention. Use Firestore batch deletes (500 per batch).
- [ ] 3.5 Add `/cron/cleanup` endpoint in `app/routers/cron.py` (same auth as `/cron/check`)
- [ ] 3.6 Schedule in Cloud Scheduler: `POST /cron/cleanup` once daily at 3am UTC

---

## Phase 7 Checklist — Viral Loop

- [ ] 7.1 Update "Powered by" footer in `status_page.html`: make it a clear bar with "Free uptime monitoring by StatusRooster — Create your status page →". Include `?ref=status-page&monitor={monitor_id}` in the link.
- [ ] 7.2 Add `referral_source` field to user model
- [ ] 7.3 In signup (both form and API): capture `ref` query param, store as `referral_source` on user doc
- [ ] 7.4 In `dashboard.html`: when user has 0 monitors, show onboarding card with "Add your first monitor" CTA and "You have 100 free monitors. No credit card required."
- [ ] 7.5 In admin dashboard: add a simple count of signups by referral source (status-page vs direct vs other)

---

# FINAL VERIFICATION CHECKLIST

Run after all phases are complete:

- [ ] All E2E tests pass (with updated plan enforcement tests)
- [ ] Security tests still pass (SSRF, cron auth, heartbeat tokens)
- [ ] Multi-region check produces results from 3+ regions
- [ ] Free user can: create 100 monitors, set Slack webhooks, set custom headers, set maintenance windows, create 10 public status pages, set check interval to 60s
- [ ] Free user CANNOT: send SMS, set check interval to 30s, access aggregate status page, create 101st monitor
- [ ] Pro user can: all of the above plus SMS, 30s intervals, 500 monitors, custom branding, hide "powered by"
- [ ] Status pages show "Powered by StatusRooster" for free users, optional for Pro
- [ ] Pricing page accurately reflects the new tiers
- [ ] Worker health endpoints respond in all deployed regions
- [ ] Monitor detail shows per-region response times when multi-region is active
- [ ] Heartbeat backfill script has been run on production
- [ ] Data cleanup cron is scheduled and runs daily
- [ ] Referral tracking captures source on new signups
