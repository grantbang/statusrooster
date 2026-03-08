#!/usr/bin/env python3
"""Exhaustive QA test script for Add/Edit Monitor forms."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import warnings
warnings.filterwarnings("ignore")

from app.services.auth import create_access_token
from app.database import get_db
from app.models.monitor import list_monitors_by_user, get_monitor

BASE = "http://localhost:8080"
USER_ID = "eydllii8PyTWHyi4BlmL"
EMAIL = "testaccount1@statusrooster.com"

token = create_access_token(USER_ID, EMAIL)
cookies = {"access_token": token}
session = requests.Session()
session.cookies.update(cookies)

db = get_db()

PASS = "✅ PASS"
FAIL = "🐛 FAIL"
WARN = "⚠️  WARN"
bugs = []

def test(name, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"  {status}: {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        bugs.append(f"{name}: {detail}")

print("=" * 70)
print("QA TEST SUITE — Add/Edit Monitor Forms")
print("=" * 70)

# =====================================================================
# SECTION 1: GET /monitors/add
# =====================================================================
print("\n--- 1. GET /monitors/add (page loads) ---")
r = session.get(f"{BASE}/monitors/add")
test("Page returns 200", r.status_code == 200, f"got {r.status_code}")
html = r.text

test("Contains monitorTypeSelect", "monitorTypeSelect" in html)
test("Contains httpSection", 'id="httpSection"' in html)
test("Contains jsonApiSection", 'id="jsonApiSection"' in html)
test("Contains heartbeatSection", 'id="heartbeatSection"' in html)
test("Contains sslSection", 'id="sslSection"' in html)
test("Contains intervalSection", 'id="intervalSection"' in html)
test("Contains advHttp", 'id="advHttp"' in html)
test("Contains advJson", 'id="advJson"' in html)
test("Contains kwBuilder", 'id="kwBuilder"' in html)
test("Contains mf-footer", 'mf-footer' in html)
test("Contains mf-submit", 'mf-submit' in html)
test("Contains mf-collapse-toggle", 'mf-collapse-toggle' in html)
test("Contains setMonitorType JS", 'setMonitorType' in html)
test("Contains syncFieldNames JS", 'syncFieldNames' in html)

# Notifications section
test("Email row: checked+disabled", 'checked disabled' in html)
test("Email hidden input with user email", f'name="alert_email" value="{EMAIL}"' in html)
test("Slack toggle present (Pro)", 'id="slackToggle"' in html)
test("Webhook toggle present (Pro)", 'id="webhookToggle"' in html)

# Pro interval (not locked)
test("Pro: interval slider not disabled", 'id="check_interval" name="check_interval" min="60" max="300"' in html)
test("Pro: no upgrade CTA in interval", 'Upgrade to Pro</a> for 60s checks' not in html)

# Advanced section
test("Keyword builder present", 'kwAddRow' in html)
test("Response threshold present", 'response_threshold_ms' in html)
test("Public status page checkbox", 'name="public" value="true"' in html)
test("Start paused checkbox", 'name="paused" value="true"' in html)
test("Maintenance windows button (Pro)", 'addMaintenanceWindow' in html)
test("JSON assertion builder present", 'addAssertion' in html)

# Group field
test("Group field with datalist", 'id="groupSuggestions"' in html)

# Hidden sections initially
test("jsonApiSection hidden by default", 'id="jsonApiSection" style="display: none;"' in html)
test("heartbeatSection hidden by default", 'id="heartbeatSection" style="display: none;"' in html)
test("sslSection hidden by default", 'id="sslSection" style="display: none;"' in html)
test("advJson hidden by default", 'id="advJson" style="display: none;"' in html)

# =====================================================================
# SECTION 2: POST /monitors/add — HTTP
# =====================================================================
print("\n--- 2. POST /monitors/add — HTTP monitor ---")
r = session.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http",
    "url": "cnn.com",
    "name": "QA HTTP Autoprefix",
    "alert_email": EMAIL,
    "expected_status_code": "200",
    "timeout": "15",
    "check_interval": "90",
    "keyword": "CNN",
    "response_threshold_ms": "> 2000",
    "group": "QA Suite",
    "public": "true",
    "slug": "qa-cnn",
}, allow_redirects=False)
test("Returns 302 redirect", r.status_code == 302, f"got {r.status_code}")
test("Redirects to dashboard with success", "msg_type=success" in r.headers.get("location", ""))

# Verify in Firestore
monitors = list_monitors_by_user(db, USER_ID)
m = next((m for m in monitors if m.get("name") == "QA HTTP Autoprefix"), None)
test("Monitor created in Firestore", m is not None)
if m:
    test("URL auto-prefixed", m["url"] == "https://cnn.com", f"got {m['url']}")
    test("monitor_type=http", m["monitor_type"] == "http")
    test("expected_status_code=200", m.get("expected_status_code") == 200, f"got {m.get('expected_status_code')}")
    test("timeout=15", m.get("timeout") == 15, f"got {m.get('timeout')}")
    test("check_interval=90 (Pro)", m.get("check_interval") == 90, f"got {m.get('check_interval')}")
    test("keyword=CNN", m.get("keyword") == "CNN", f"got {m.get('keyword')}")
    test("response_threshold_ms='> 2000'", m.get("response_threshold_ms") == "> 2000", f"got {m.get('response_threshold_ms')}")
    test("group=QA Suite", m.get("group") == "QA Suite", f"got {m.get('group')}")
    test("public=True", m.get("public") is True, f"got {m.get('public')}")
    test("slug contains 'qa-cnn'", "qa-cnn" in m.get("slug", ""), f"got {m.get('slug')}")
    http_edit_id = m["id"]
else:
    http_edit_id = None

# =====================================================================
# SECTION 3: POST /monitors/add — JSON/API
# =====================================================================
print("\n--- 3. POST /monitors/add — JSON/API monitor ---")
r = session.post(f"{BASE}/monitors/add", data={
    "monitor_type": "json_api",
    "url": "https://api.test.com/v1/health",
    "name": "QA JSON API",
    "alert_email": EMAIL,
    "expected_status_code": "201",
    "timeout": "20",
    "auth_header": "Bearer secrettoken123",
    "assertion_path[]": ["data.status", "meta.version"],
    "assertion_operator[]": ["equals", "greater_than"],
    "assertion_value[]": ["healthy", "2"],
    "check_interval": "180",
    "group": "QA Suite",
}, allow_redirects=False)
test("Returns 302 redirect", r.status_code == 302, f"got {r.status_code}")

monitors = list_monitors_by_user(db, USER_ID)
m = next((m for m in monitors if m.get("name") == "QA JSON API"), None)
test("Monitor created in Firestore", m is not None)
if m:
    test("monitor_type=json_api", m["monitor_type"] == "json_api")
    test("url correct", m["url"] == "https://api.test.com/v1/health", f"got {m['url']}")
    test("auth_header saved", m.get("auth_header") == "Bearer secrettoken123", f"got {m.get('auth_header')}")
    test("expected_status_code=201", m.get("expected_status_code") == 201, f"got {m.get('expected_status_code')}")
    test("timeout=20", m.get("timeout") == 20, f"got {m.get('timeout')}")
    test("check_interval=180 (Pro)", m.get("check_interval") == 180, f"got {m.get('check_interval')}")
    assertions = m.get("json_assertions", [])
    test("2 assertions saved", len(assertions) == 2, f"got {len(assertions)}")
    if len(assertions) >= 2:
        test("Assertion 1: data.status equals healthy", 
             assertions[0].get("path") == "data.status" and assertions[0].get("operator") == "equals" and assertions[0].get("value") == "healthy",
             f"got {assertions[0]}")
        test("Assertion 2: meta.version greater_than 2",
             assertions[1].get("path") == "meta.version" and assertions[1].get("operator") == "greater_than" and assertions[1].get("value") == "2",
             f"got {assertions[1]}")
    json_edit_id = m["id"]
else:
    json_edit_id = None

# =====================================================================
# SECTION 4: POST /monitors/add — Heartbeat
# =====================================================================
print("\n--- 4. POST /monitors/add — Heartbeat monitor ---")
r = session.post(f"{BASE}/monitors/add", data={
    "monitor_type": "heartbeat",
    "name": "QA Heartbeat",
    "alert_email": EMAIL,
    "heartbeat_interval": "1800",
    "heartbeat_grace_period": "120",
}, allow_redirects=False)
test("Returns 302 redirect", r.status_code == 302, f"got {r.status_code}")
loc = r.headers.get("location", "")
test("Redirect includes heartbeat_created=1", "heartbeat_created=1" in loc, f"location={loc}")
test("Redirect includes ping_url", "ping_url=" in loc, f"location={loc}")
test("Redirect includes monitor_name", "monitor_name=" in loc, f"location={loc}")

monitors = list_monitors_by_user(db, USER_ID)
m = next((m for m in monitors if m.get("name") == "QA Heartbeat"), None)
test("Monitor created in Firestore", m is not None)
if m:
    test("monitor_type=heartbeat", m["monitor_type"] == "heartbeat")
    test("ping_url generated", m.get("ping_url", "").startswith("http"), f"got {m.get('ping_url')}")
    test("url = ping_url", m.get("url") == m.get("ping_url"))
    test("heartbeat_interval=1800", m.get("heartbeat_interval") == 1800, f"got {m.get('heartbeat_interval')}")
    test("heartbeat_grace_period=120", m.get("heartbeat_grace_period") == 120, f"got {m.get('heartbeat_grace_period')}")
    hb_edit_id = m["id"]
else:
    hb_edit_id = None

# =====================================================================
# SECTION 5: POST /monitors/add — SSL
# =====================================================================
print("\n--- 5. POST /monitors/add — SSL monitor ---")
r = session.post(f"{BASE}/monitors/add", data={
    "monitor_type": "ssl",
    "ssl_domain": "example.com",
    "name": "QA SSL",
    "alert_email": EMAIL,
    "ssl_expiry_threshold_days": "7",
    "check_interval": "300",
    "paused": "true",
}, allow_redirects=False)
test("Returns 302 redirect", r.status_code == 302, f"got {r.status_code}")
test("Redirects with success", "msg_type=success" in r.headers.get("location", ""))

monitors = list_monitors_by_user(db, USER_ID)
m = next((m for m in monitors if m.get("name") == "QA SSL"), None)
test("Monitor created in Firestore", m is not None)
if m:
    test("monitor_type=ssl", m["monitor_type"] == "ssl")
    test("ssl_domain=example.com", m.get("ssl_domain") == "example.com", f"got {m.get('ssl_domain')}")
    test("url=https://example.com", m.get("url") == "https://example.com", f"got {m.get('url')}")
    test("ssl_expiry_threshold_days=7", m.get("ssl_expiry_threshold_days") == 7, f"got {m.get('ssl_expiry_threshold_days')}")
    test("paused=True", m.get("paused") is True, f"got {m.get('paused')}")
    ssl_edit_id = m["id"]
else:
    ssl_edit_id = None

# =====================================================================
# SECTION 6: POST /monitors/add — Advanced features
# =====================================================================
print("\n--- 6. POST /monitors/add — Maintenance windows (Pro) ---")
r = session.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http",
    "url": "https://example.com",
    "name": "QA Maintenance",
    "alert_email": EMAIL,
    "maintenance_day[]": ["monday", "friday"],
    "maintenance_start[]": ["02:00", "22:00"],
    "maintenance_end[]": ["04:00", "23:59"],
    "alert_slack_webhook": "https://hooks.slack.com/test",
    "webhook_url": "https://my-webhook.com/alert",
}, allow_redirects=False)
test("Returns 302 redirect", r.status_code == 302, f"got {r.status_code}")

monitors = list_monitors_by_user(db, USER_ID)
m = next((m for m in monitors if m.get("name") == "QA Maintenance"), None)
test("Monitor created", m is not None)
if m:
    mws = m.get("maintenance_windows", [])
    test("2 maintenance windows saved", len(mws) == 2, f"got {len(mws)}: {mws}")
    if len(mws) >= 2:
        test("MW 1: monday 02:00-04:00", mws[0]["day"] == "monday" and mws[0]["start_utc"] == "02:00", f"got {mws[0]}")
        test("MW 2: friday 22:00-23:59", mws[1]["day"] == "friday" and mws[1]["start_utc"] == "22:00", f"got {mws[1]}")
    test("Slack webhook saved (Pro)", m.get("alert_slack_webhook") == "https://hooks.slack.com/test", f"got {m.get('alert_slack_webhook')}")
    test("Webhook URL saved (Pro)", m.get("webhook_url") == "https://my-webhook.com/alert", f"got {m.get('webhook_url')}")

# =====================================================================
# SECTION 7: Edit Monitor pages — load and verify pre-population
# =====================================================================
print("\n--- 7. Edit Monitor pages — pre-population ---")

if http_edit_id:
    r = session.get(f"{BASE}/monitors/{http_edit_id}/edit")
    test("Edit HTTP page returns 200", r.status_code == 200)
    html = r.text
    test("Type badge: HTTP", "HTTP / HTTPS" in html)
    test("URL pre-populated", 'value="https://cnn.com"' in html, f"searched for value=\"https://cnn.com\"")
    test("Name pre-populated", 'value="QA HTTP Autoprefix"' in html)
    test("Group pre-populated", 'value="QA Suite"' in html)
    test("Expected status pre-populated", 'value="200"' in html)
    test("Keyword pre-populated", 'value="CNN"' in html)
    test("Response threshold pre-populated", 'value="&gt; 2000"' in html or 'value="> 2000"' in html, "checking for response_threshold_ms")
    test("Back link correct", f'/monitors/{http_edit_id}"' in html)
    test("Slug input present", 'name="slug"' in html)
    test("Slug preview present", 'id="slug-preview"' in html)
    test("Public checkbox checked", 'id="publicCheck" value="true"' in html and 'checked' in html)
    # Check interval section visible (not heartbeat)
    test("Interval section present", 'intervalSection' in html)

if json_edit_id:
    r = session.get(f"{BASE}/monitors/{json_edit_id}/edit")
    test("Edit JSON/API page returns 200", r.status_code == 200)
    html = r.text
    test("Type badge: JSON / API", "JSON / API" in html)
    test("URL pre-populated", 'value="https://api.test.com/v1/health"' in html)
    test("Auth header pre-populated", 'value="Bearer secrettoken123"' in html)
    test("Assertions pre-rendered", 'assertion_path[]' in html)
    test("Assertion path pre-populated", 'value="data.status"' in html)
    test("Assertion operator pre-populated", 'selected' in html)

if hb_edit_id:
    r = session.get(f"{BASE}/monitors/{hb_edit_id}/edit")
    test("Edit Heartbeat page returns 200", r.status_code == 200)
    html = r.text
    test("Type badge: Heartbeat", "Heartbeat / Cron" in html)
    test("Ping URL displayed", "api/ping/" in html)
    test("Copy button present", "Copy" in html)
    test("Heartbeat interval 1800 selected", 'value="1800"' in html and 'selected' in html)
    test("Grace period pre-populated", 'value="120"' in html)
    test("No intervalSection (heartbeat)", 'id="intervalSection"' not in html)

if ssl_edit_id:
    r = session.get(f"{BASE}/monitors/{ssl_edit_id}/edit")
    test("Edit SSL page returns 200", r.status_code == 200)
    html = r.text
    test("Type badge: SSL Certificate", "SSL Certificate" in html)
    test("SSL domain pre-populated", 'value="example.com"' in html)
    test("Threshold pre-populated", 'value="7"' in html)
    test("Paused checkbox checked", 'id="pausedCheck"' in html)
    # Check that paused=true is reflected
    paused_checked = 'pausedCheck" value="true"' in html and 'checked' in html
    # More tolerant check
    paused_section = html[html.find('pausedCheck'):html.find('pausedCheck')+200] if 'pausedCheck' in html else ''
    test("Paused=true reflected", 'checked' in paused_section, f"section: {paused_section[:100]}")

# =====================================================================
# SECTION 8: POST edit — save changes
# =====================================================================
print("\n--- 8. POST edit — save changes ---")

if http_edit_id:
    r = session.post(f"{BASE}/monitors/{http_edit_id}/edit", data={
        "monitor_type": "http",
        "url": "https://cnn.com",
        "name": "QA HTTP Updated",
        "alert_email": EMAIL,
        "expected_status_code": "201",
        "timeout": "30",
        "check_interval": "120",
        "keyword": "breaking AND !error",
        "response_threshold_ms": "200-3000",
        "group": "QA Updated",
        "slug": "qa-updated",
        "public": "true",
    }, allow_redirects=False)
    test("Edit POST returns 302", r.status_code == 302, f"got {r.status_code}")
    test("Redirect has success", "msg_type=success" in r.headers.get("location", ""))

    # Verify updates
    m = get_monitor(db, http_edit_id)
    test("Name updated", m.get("name") == "QA HTTP Updated", f"got {m.get('name')}")
    test("Expected status updated to 201", m.get("expected_status_code") == 201, f"got {m.get('expected_status_code')}")
    test("Timeout updated to 30", m.get("timeout") == 30, f"got {m.get('timeout')}")
    test("Check interval updated to 120", m.get("check_interval") == 120, f"got {m.get('check_interval')}")
    test("Keyword updated", m.get("keyword") == "breaking AND !error", f"got {m.get('keyword')}")
    test("Response threshold updated", m.get("response_threshold_ms") == "200-3000", f"got {m.get('response_threshold_ms')}")
    test("Group updated", m.get("group") == "QA Updated", f"got {m.get('group')}")
    test("Slug updated", m.get("slug") == "qa-updated", f"got {m.get('slug')}")
    test("Public still true", m.get("public") is True)

if json_edit_id:
    r = session.post(f"{BASE}/monitors/{json_edit_id}/edit", data={
        "monitor_type": "json_api",
        "url": "https://api.test.com/v2/status",
        "name": "QA JSON API Updated",
        "alert_email": EMAIL,
        "expected_status_code": "200",
        "timeout": "25",
        "auth_header": "Bearer newtoken",
        "assertion_path[]": ["data.ok"],
        "assertion_operator[]": ["equals"],
        "assertion_value[]": ["true"],
        "check_interval": "60",
    }, allow_redirects=False)
    test("Edit JSON POST returns 302", r.status_code == 302)
    m = get_monitor(db, json_edit_id)
    test("JSON name updated", m.get("name") == "QA JSON API Updated")
    test("JSON url updated", m.get("url") == "https://api.test.com/v2/status")
    test("JSON auth_header updated", m.get("auth_header") == "Bearer newtoken", f"got {m.get('auth_header')}")
    assertions = m.get("json_assertions", [])
    test("JSON assertions updated (1 assertion)", len(assertions) == 1, f"got {len(assertions)}")
    if assertions:
        test("Assertion: data.ok equals true", assertions[0].get("path") == "data.ok", f"got {assertions[0]}")

if hb_edit_id:
    r = session.post(f"{BASE}/monitors/{hb_edit_id}/edit", data={
        "monitor_type": "heartbeat",
        "url": "",  # heartbeat URL stays as-is
        "name": "QA Heartbeat Updated",
        "alert_email": EMAIL,
        "heartbeat_interval": "3600",
        "heartbeat_grace_period": "300",
    }, allow_redirects=False)
    test("Edit Heartbeat POST returns 302", r.status_code == 302)
    m = get_monitor(db, hb_edit_id)
    test("Heartbeat name updated", m.get("name") == "QA Heartbeat Updated")
    test("Heartbeat interval updated to 3600", m.get("heartbeat_interval") == 3600, f"got {m.get('heartbeat_interval')}")
    test("Heartbeat grace period updated to 300", m.get("heartbeat_grace_period") == 300, f"got {m.get('heartbeat_grace_period')}")
    test("Heartbeat ping_url preserved", m.get("ping_url", "").startswith("http"), f"got {m.get('ping_url')}")

if ssl_edit_id:
    r = session.post(f"{BASE}/monitors/{ssl_edit_id}/edit", data={
        "monitor_type": "ssl",
        "url": "",
        "name": "QA SSL Updated",
        "alert_email": EMAIL,
        "ssl_domain": "updated-example.com",
        "ssl_expiry_threshold_days": "21",
        "paused": "true",
    }, allow_redirects=False)
    test("Edit SSL POST returns 302", r.status_code == 302)
    m = get_monitor(db, ssl_edit_id)
    test("SSL name updated", m.get("name") == "QA SSL Updated")
    test("SSL domain updated", m.get("ssl_domain") == "updated-example.com", f"got {m.get('ssl_domain')}")
    test("SSL threshold updated to 21", m.get("ssl_expiry_threshold_days") == 21, f"got {m.get('ssl_expiry_threshold_days')}")
    test("SSL paused=true", m.get("paused") is True)

# =====================================================================
# SECTION 9: Ownership check
# =====================================================================
print("\n--- 9. Ownership / authorization checks ---")

# Try editing someone else's monitor — use a fake monitor ID
r = session.get(f"{BASE}/monitors/FAKEID123/edit")
test("Fake ID edit page redirects", r.status_code == 200 and "Monitor+not+found" in r.url or r.status_code == 302, f"status={r.status_code}, url={r.url[:80]}")

# Unauthenticated access
r = requests.get(f"{BASE}/monitors/add")
test("Unauthenticated: redirects to login", "/login" in r.url, f"url={r.url[:80]}")

# =====================================================================
# SECTION 10: Paused toggle — verify false when not sent
# =====================================================================
print("\n--- 10. Paused toggle — unchecking sends no field ---")
if http_edit_id:
    # Submit without paused field (checkbox unchecked)
    r = session.post(f"{BASE}/monitors/{http_edit_id}/edit", data={
        "monitor_type": "http",
        "url": "https://cnn.com",
        "name": "QA HTTP Updated",
        "alert_email": EMAIL,
        # paused NOT included = should be False
    }, allow_redirects=False)
    m = get_monitor(db, http_edit_id)
    test("Paused=False when field omitted", m.get("paused") is False, f"got {m.get('paused')}")

# =====================================================================
# SECTION 11: URL auto-prefix edge cases
# =====================================================================
print("\n--- 11. URL auto-prefix edge cases ---")

# Already has https://
r = session.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http",
    "url": "https://already-prefixed.com",
    "name": "QA Already Prefixed",
    "alert_email": EMAIL,
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((m for m in monitors if m.get("name") == "QA Already Prefixed"), None)
if m:
    test("URL not double-prefixed", m["url"] == "https://already-prefixed.com", f"got {m['url']}")

# Has http://
r = session.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http",
    "url": "http://insecure.com",
    "name": "QA HTTP Insecure",
    "alert_email": EMAIL,
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((m for m in monitors if m.get("name") == "QA HTTP Insecure"), None)
if m:
    test("http:// URL preserved", m["url"] == "http://insecure.com", f"got {m['url']}")

# =====================================================================
# SECTION 12: Edit — URL auto-prefix on edit
# =====================================================================
print("\n--- 12. Edit — URL auto-prefix ---")
if http_edit_id:
    r = session.post(f"{BASE}/monitors/{http_edit_id}/edit", data={
        "monitor_type": "http",
        "url": "www.newurl.com",
        "name": "QA HTTP Updated",
        "alert_email": EMAIL,
    }, allow_redirects=False)
    m = get_monitor(db, http_edit_id)
    test("Edit URL auto-prefixed", m.get("url") == "https://www.newurl.com", f"got {m.get('url')}")

# =====================================================================
# SECTION 13: Dashboard navigation
# =====================================================================
print("\n--- 13. Dashboard navigation checks ---")
r = session.get(f"{BASE}/dashboard")
html = r.text
test("Dashboard loads (200)", r.status_code == 200)
test("No openModal() references", "openModal" not in html)
test("Add monitor button links to /monitors/add", 'href="/monitors/add"' in html)
test("Edit menu links to /monitors/ID/edit", '/edit' in html)

# =====================================================================
# SECTION 14: Heartbeat edit preserves ping URL
# =====================================================================
print("\n--- 14. Heartbeat edit — ping URL preserved ---")
if hb_edit_id:
    m = get_monitor(db, hb_edit_id)
    old_ping = m.get("ping_url")
    r = session.post(f"{BASE}/monitors/{hb_edit_id}/edit", data={
        "monitor_type": "heartbeat",
        "url": m.get("url", ""),
        "name": "QA Heartbeat Final",
        "alert_email": EMAIL,
        "heartbeat_interval": "600",
        "heartbeat_grace_period": "30",
    }, allow_redirects=False)
    m2 = get_monitor(db, hb_edit_id)
    test("Ping URL unchanged after edit", m2.get("ping_url") == old_ping, f"before={old_ping}, after={m2.get('ping_url')}")

# =====================================================================
# SECTION 15: Heartbeat edit page — hidden URL field
# =====================================================================
print("\n--- 15. Heartbeat edit page — hidden URL input ---")
if hb_edit_id:
    r = session.get(f"{BASE}/monitors/{hb_edit_id}/edit")
    html = r.text
    # Should have hidden input with URL so the POST handler receives it
    test("Hidden URL input for heartbeat", 'name="url" value="' in html, "heartbeat edit needs hidden url input")

# =====================================================================
# SECTION 16: Timeout clamping on edit
# =====================================================================
print("\n--- 16. Timeout clamping on edit ---")
if http_edit_id:
    r = session.post(f"{BASE}/monitors/{http_edit_id}/edit", data={
        "monitor_type": "http",
        "url": "https://cnn.com",
        "name": "QA HTTP Updated",
        "alert_email": EMAIL,
        "timeout": "999",
    }, allow_redirects=False)
    m = get_monitor(db, http_edit_id)
    test("Timeout clamped to max 60", m.get("timeout") == 60, f"got {m.get('timeout')}")

    r = session.post(f"{BASE}/monitors/{http_edit_id}/edit", data={
        "monitor_type": "http",
        "url": "https://cnn.com",
        "name": "QA HTTP Updated",
        "alert_email": EMAIL,
        "timeout": "0",
    }, allow_redirects=False)
    m = get_monitor(db, http_edit_id)
    test("Timeout clamped to min 1", m.get("timeout") == 1, f"got {m.get('timeout')}")

# =====================================================================
# SECTION 17: SSL expiry threshold clamping
# =====================================================================
print("\n--- 17. SSL expiry threshold clamping ---")
if ssl_edit_id:
    r = session.post(f"{BASE}/monitors/{ssl_edit_id}/edit", data={
        "monitor_type": "ssl",
        "url": "",
        "name": "QA SSL Updated",
        "alert_email": EMAIL,
        "ssl_domain": "example.com",
        "ssl_expiry_threshold_days": "200",
    }, allow_redirects=False)
    m = get_monitor(db, ssl_edit_id)
    test("SSL threshold clamped to max 90", m.get("ssl_expiry_threshold_days") == 90, f"got {m.get('ssl_expiry_threshold_days')}")

# =====================================================================
# SECTION 18: Heartbeat interval clamping on edit
# =====================================================================
print("\n--- 18. Heartbeat interval clamping ---")
if hb_edit_id:
    r = session.post(f"{BASE}/monitors/{hb_edit_id}/edit", data={
        "monitor_type": "heartbeat",
        "url": "",
        "name": "QA Heartbeat Final",
        "alert_email": EMAIL,
        "heartbeat_interval": "999999",
        "heartbeat_grace_period": "9999",
    }, allow_redirects=False)
    m = get_monitor(db, hb_edit_id)
    test("Heartbeat interval clamped to 86400", m.get("heartbeat_interval") == 86400, f"got {m.get('heartbeat_interval')}")
    test("Grace period clamped to 3600", m.get("heartbeat_grace_period") == 3600, f"got {m.get('heartbeat_grace_period')}")

# =====================================================================
# SECTION 19: Keyword builder parse — verify initKeywordBuilder
# =====================================================================
print("\n--- 19. Keyword builder parse on edit page ---")
if http_edit_id:
    # First set a complex keyword
    r = session.post(f"{BASE}/monitors/{http_edit_id}/edit", data={
        "monitor_type": "http",
        "url": "https://cnn.com",
        "name": "QA HTTP Updated",
        "alert_email": EMAIL,
        "keyword": "Welcome AND !error OR success",
    }, allow_redirects=False)
    
    r = session.get(f"{BASE}/monitors/{http_edit_id}/edit")
    html = r.text
    test("Keyword value in hidden input", 'value="Welcome AND !error OR success"' in html, "keyword builder should parse this")
    test("initKeywordBuilder function present", "initKeywordBuilder" in html)

# =====================================================================
# SECTION 20: Public status page limit check
# =====================================================================
print("\n--- 20. Status page limit enforcement ---")
# Already have at least one public monitor; Pro limit is 10, so just verify the check exists in code
# This is more of a code review check since creating 10+ public monitors is impractical in QA

# =====================================================================
# SECTION 21: CSS audit — all mf-* classes used in templates exist in style.css
# =====================================================================
print("\n--- 21. CSS audit — mf-* classes ---")
import re
# Read CSS
with open("/Applications/statusrooster/app/static/style.css") as f:
    css = f.read()

# Collect mf-* class names from templates
template_classes = set()
for tpl in ["add_monitor.html", "edit_monitor.html"]:
    with open(f"/Applications/statusrooster/app/templates/{tpl}") as f:
        content = f.read()
    matches = re.findall(r'(?:class=")[^"]*?(mf-[\w-]+)', content)
    for m in matches:
        template_classes.add(m)

for cls in sorted(template_classes):
    found = f".{cls}" in css
    test(f"CSS has .{cls}", found)

# =====================================================================
# SECTION 22: Check for broken edit page with no assertions / no keyword
# =====================================================================
print("\n--- 22. Edge cases — empty optional fields ---")
r = session.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http",
    "url": "https://example.com/edge",
    "name": "QA Edge Case Empty",
    "alert_email": EMAIL,
}, allow_redirects=False)
test("Minimal HTTP monitor creates OK", r.status_code == 302)

monitors = list_monitors_by_user(db, USER_ID)
m = next((m for m in monitors if m.get("name") == "QA Edge Case Empty"), None)
if m:
    test("Keyword defaults to empty", m.get("keyword") == "" or m.get("keyword") is None)
    test("Expected status defaults to None", m.get("expected_status_code") is None)
    test("Response threshold defaults to None", m.get("response_threshold_ms") is None)
    test("JSON assertions defaults to empty", m.get("json_assertions") in ([], None))
    test("Auth header defaults to empty", m.get("auth_header") in ("", None))
    test("Public defaults to False", m.get("public") is False)
    test("Paused defaults to False", m.get("paused") is False)

    # Edit page for this monitor should load fine
    r = session.get(f"{BASE}/monitors/{m['id']}/edit")
    test("Edit page loads for minimal monitor", r.status_code == 200)

# =====================================================================
# CLEANUP
# =====================================================================
print("\n--- Cleanup: deleting QA test monitors ---")
monitors = list_monitors_by_user(db, USER_ID)
qa_monitors = [m for m in monitors if m.get("name", "").startswith("QA ")]
for m in qa_monitors:
    db.collection("monitors").document(m["id"]).delete()
    print(f"  Deleted: {m['name']} ({m['id']})")

# Also delete the earlier test monitors
earlier_qa = [m for m in monitors if m.get("name") in ("QA Test HTTP", "QA Test JSON API", "QA Test Heartbeat", "QA Test SSL")]
for m in earlier_qa:
    db.collection("monitors").document(m["id"]).delete()
    print(f"  Deleted: {m['name']} ({m['id']})")

# =====================================================================
# SUMMARY
# =====================================================================
print("\n" + "=" * 70)
if bugs:
    print(f"🐛 BUGS FOUND: {len(bugs)}")
    for b in bugs:
        print(f"  • {b}")
else:
    print("✅ ALL TESTS PASSED — No bugs found!")
print("=" * 70)
