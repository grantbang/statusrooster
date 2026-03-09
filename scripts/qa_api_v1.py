"""
Phase 11E — API v1 functional tests.
Tests all gate checks: auth, CRUD, validation, PATCH, response shape.
Run from repo root: python scripts/qa_api_v1.py
Requires: dev server running on localhost:8080
          test account API key exported or hardcoded below.
"""

import sys
import os
import json

# ── Grab API key from env or first CLI arg ──────────────────────────────────
API_KEY = os.environ.get("SR_API_KEY") or (sys.argv[1] if len(sys.argv) > 1 else None)
BASE = "http://localhost:8080/api/v1"

# ── Bootstrap FastAPI test client (no live server needed) ───────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

PASS = 0
FAIL = 0
BUGS = []


def check(label: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        print(f"  ✅ PASS: {label}")
        PASS += 1
    else:
        print(f"  ❌ FAIL: {label}" + (f" — {detail}" if detail else ""))
        FAIL += 1
        BUGS.append(f"{label}: {detail}")


def hdr(valid=True):
    return {"X-API-Key": API_KEY} if valid else {}


# ── Resolve a real API key from the test account if none supplied ────────────
_temp_key_id = None
if not API_KEY:
    from app.database import get_db
    from app.models.api_key import generate_api_key, revoke_api_key

    db = get_db()
    key_data = generate_api_key(db, "eydllii8PyTWHyi4BlmL", label="qa-api-v1-test")
    API_KEY = key_data["raw_key"]
    _temp_key_id = key_data["id"]
    print(f"Generated temporary API key: {API_KEY[:12]}…")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
print("\n--- 11E.1  Auth: missing key → 401 ---")
r = client.get(f"{BASE}/monitors")
check("missing key → 401 (not 403)", r.status_code == 401, f"got {r.status_code}")

print("\n--- 11E.2  Auth: invalid key → 401 ---")
r = client.get(f"{BASE}/monitors", headers={"X-API-Key": "sr_invalid_key_xyz"})
check("invalid key → 401", r.status_code == 401, f"got {r.status_code}")

print("\n--- 11E.3  Auth: valid key → 200 ---")
r = client.get(f"{BASE}/monitors", headers=hdr())
check("valid key → 200", r.status_code == 200, f"got {r.status_code}")

print("\n--- 11E.4  List monitors — response shape ---")
body = r.json()
check("has 'data' key", "data" in body)
check("has 'error' key", "error" in body)
check("has 'meta' key", "meta" in body)
check("data is list", isinstance(body.get("data"), list))

print("\n--- 11E.5a  GET single monitor — valid ---")
monitors = body.get("data", [])
if monitors:
    mid = monitors[0]["id"]
    r = client.get(f"{BASE}/monitors/{mid}", headers=hdr())
    check("GET /monitors/{id} → 200", r.status_code == 200, f"got {r.status_code}")
else:
    print("  ⚠️  SKIP: no monitors found for test account")

print("\n--- 11E.5b  GET single monitor — invalid id → 404 ---")
r = client.get(f"{BASE}/monitors/nonexistent_id_zzz", headers=hdr())
check("invalid id → 404", r.status_code == 404, f"got {r.status_code}")

# ── Create helpers (track IDs for cleanup) ──────────────────────────────────
created_ids = []

print("\n--- 11E.6  Create HTTP monitor → 201 ---")
r = client.post(f"{BASE}/monitors", headers=hdr(), json={
    "name": "QA API HTTP",
    "monitor_type": "http",
    "url": "https://example.com",
    "interval": 300,
})
check("POST HTTP → 201", r.status_code == 201, f"got {r.status_code}")
if r.status_code == 201:
    d = r.json().get("data", {})
    created_ids.append(d.get("id"))
    check("http_method in response", "http_method" in d, str(d.keys()))
    check("follow_redirects in response", "follow_redirects" in d, str(d.keys()))

print("\n--- 11E.7  Create JSON/API monitor → 201 ---")
r = client.post(f"{BASE}/monitors", headers=hdr(), json={
    "name": "QA API JSON",
    "monitor_type": "json_api",
    "url": "https://api.github.com/zen",
    "interval": 300,
})
check("POST json_api → 201", r.status_code == 201, f"got {r.status_code}")
if r.status_code == 201:
    d = r.json().get("data", {})
    created_ids.append(d.get("id"))
    check("json_assertions in response", "json_assertions" in d, str(d.keys()))

print("\n--- 11E.8  Create Heartbeat monitor → 201 ---")
r = client.post(f"{BASE}/monitors", headers=hdr(), json={
    "name": "QA API Heartbeat",
    "monitor_type": "heartbeat",
    "interval": 300,
})
check("POST heartbeat → 201", r.status_code == 201, f"got {r.status_code}")
if r.status_code == 201:
    d = r.json().get("data", {})
    created_ids.append(d.get("id"))
    check("ping_url in response", "ping_url" in d, str(d.keys()))
    check("heartbeat_interval in response", "heartbeat_interval" in d, str(d.keys()))

print("\n--- 11E.9  Create SSL monitor → 201 ---")
r = client.post(f"{BASE}/monitors", headers=hdr(), json={
    "name": "QA API SSL",
    "monitor_type": "ssl",
    "url": "https://google.com",
    "interval": 300,
})
check("POST ssl → 201", r.status_code == 201, f"got {r.status_code}")
if r.status_code == 201:
    d = r.json().get("data", {})
    created_ids.append(d.get("id"))
    check("ssl_domain in response", "ssl_domain" in d, str(d.keys()))
    check("ssl_expiry_threshold_days in response", "ssl_expiry_threshold_days" in d, str(d.keys()))

print("\n--- 11E.11a  Validation: missing name → 422 ---")
r = client.post(f"{BASE}/monitors", headers=hdr(), json={
    "monitor_type": "http",
    "url": "https://example.com",
    "interval": 300,
})
check("missing name → 422", r.status_code == 422, f"got {r.status_code}")

print("\n--- 11E.11b  Validation: invalid monitor_type → 422 ---")
r = client.post(f"{BASE}/monitors", headers=hdr(), json={
    "name": "Bad Type",
    "monitor_type": "tcp",
    "url": "https://example.com",
})
check("invalid monitor_type → 422", r.status_code == 422, f"got {r.status_code}")

print("\n--- 11E.12  PATCH is alias for PUT → 200 ---")
if created_ids and created_ids[0]:
    mid = created_ids[0]
    r = client.patch(f"{BASE}/monitors/{mid}", headers=hdr(), json={"name": "QA API HTTP Updated"})
    check("PATCH /monitors/{id} → 200 (not 405)", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        d = r.json().get("data", {})
        check("name updated in response", d.get("name") == "QA API HTTP Updated", d.get("name"))
else:
    print("  ⚠️  SKIP: no HTTP monitor created to PATCH")

print("\n--- 11E.15  Delete → 200, then GET → 404 ---")
if created_ids and created_ids[0]:
    mid = created_ids[0]
    r = client.delete(f"{BASE}/monitors/{mid}", headers=hdr())
    check("DELETE → 200", r.status_code == 200, f"got {r.status_code}")
    r2 = client.get(f"{BASE}/monitors/{mid}", headers=hdr())
    check("GET after delete → 404", r2.status_code == 404, f"got {r2.status_code}")
    created_ids[0] = None  # already deleted

print("\n--- 11E.16  Check history → 200 with meta ---")
if monitors:
    mid = monitors[0]["id"]
    r = client.get(f"{BASE}/monitors/{mid}/checks", headers=hdr())
    check("GET /checks → 200", r.status_code == 200, f"got {r.status_code}")
    if r.status_code == 200:
        body = r.json()
        check("checks has meta", "meta" in body)
        check("checks has data list", isinstance(body.get("data"), list))

print("\n--- 11E.17  List incidents → 200 ---")
r = client.get(f"{BASE}/incidents", headers=hdr())
check("GET /incidents → 200", r.status_code == 200, f"got {r.status_code}")
if r.status_code == 200:
    body = r.json()
    check("incidents has data", "data" in body)
    check("incidents has error", "error" in body)

print("\n--- 11E.19  Response shape on all 3 base endpoints ---")
for ep in ["/monitors", "/incidents"]:
    r = client.get(f"{BASE}{ep}", headers=hdr())
    b = r.json()
    check(f"{ep} has {{data,error}} shape", "data" in b and "error" in b)

# ── Cleanup remaining test monitors ─────────────────────────────────────────
print("\n--- Cleanup: deleting QA API test monitors ---")
for mid in created_ids:
    if mid:
        r = client.delete(f"{BASE}/monitors/{mid}", headers=hdr())
        status = "✅" if r.status_code == 200 else "⚠️"
        print(f"  {status} Deleted {mid}")

if _temp_key_id:
    from app.models.api_key import revoke_api_key
    from app.database import get_db as _get_db
    revoke_api_key(_get_db(), _temp_key_id, "eydllii8PyTWHyi4BlmL")
    print(f"  🔑 Revoked temporary API key {_temp_key_id[:8]}…")

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
total = PASS + FAIL
print(f"Results: {PASS}/{total} passed")
if BUGS:
    print(f"🐛 FAILURES ({len(BUGS)}):")
    for b in BUGS:
        print(f"  • {b}")
else:
    print("✅ All API v1 gate tests PASS")
print(f"{'='*70}")
sys.exit(0 if FAIL == 0 else 1)
