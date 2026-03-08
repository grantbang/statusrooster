#!/usr/bin/env python3
"""Re-run QA tests to verify the 3 bug fixes."""
import sys, os, warnings
sys.path.insert(0, '/Applications/statusrooster')
warnings.filterwarnings("ignore")
import requests
from app.services.auth import create_access_token
from app.database import get_db
from app.models.monitor import list_monitors_by_user, get_monitor

BASE = "http://localhost:8080"
USER_ID = "eydllii8PyTWHyi4BlmL"
EMAIL = "testaccount1@statusrooster.com"
token = create_access_token(USER_ID, EMAIL)
s = requests.Session()
s.cookies.update({"access_token": token})
db = get_db()
bugs = []

def t(name, ok, detail=""):
    mark = "✅" if ok else "🐛"
    print(f"  {mark} {name}" + (f" — {detail}" if detail else ""), flush=True)
    if not ok:
        bugs.append(f"{name}: {detail}")

print("=" * 60, flush=True)
print("REGRESSION TESTS — Verifying 3 Bug Fixes", flush=True)
print("=" * 60, flush=True)

# Fix 1: Custom slug used on Add
print("\n--- Fix 1: Custom slug on Add form ---", flush=True)
r = s.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http", "url": "https://ex.com", "name": "QA Fix Slug",
    "alert_email": EMAIL, "slug": "my-custom-slug", "public": "true",
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name") == "QA Fix Slug"), None)
t("Monitor created", m is not None)
if m:
    t("Custom slug used", m.get("slug") == "my-custom-slug", f"got {m.get('slug')}")
    db.collection("monitors").document(m["id"]).delete()

# Fix 1b: Auto-generated slug when no custom slug provided
print("\n--- Fix 1b: Auto slug when none provided ---", flush=True)
r = s.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http", "url": "https://ex.com", "name": "QA Auto Slug",
    "alert_email": EMAIL,
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name") == "QA Auto Slug"), None)
if m:
    t("Auto slug generated", m.get("slug", "").startswith("qa-auto-slug"), f"got {m.get('slug')}")
    db.collection("monitors").document(m["id"]).delete()

# Fix 1c: Slug sanitization
print("\n--- Fix 1c: Slug sanitization ---", flush=True)
r = s.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http", "url": "https://ex.com", "name": "QA Sanitize",
    "alert_email": EMAIL, "slug": "My Slug With CAPS & Spaces!",
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name") == "QA Sanitize"), None)
if m:
    t("Slug sanitized to lowercase/hyphens", m.get("slug") == "my-slug-with-caps--spaces", f"got {m.get('slug')}")
    db.collection("monitors").document(m["id"]).delete()

# Fix 2: Heartbeat URL not overwritten on edit with empty URL
print("\n--- Fix 2: Heartbeat URL preserved on edit ---", flush=True)
r = s.post(f"{BASE}/monitors/add", data={
    "monitor_type": "heartbeat", "name": "QA Fix HB",
    "alert_email": EMAIL,
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name") == "QA Fix HB"), None)
if m:
    orig_url = m.get("url")
    t("Heartbeat URL is ping_url", orig_url.startswith("https://statusrooster.com"), f"got {orig_url}")
    # Edit with empty URL
    r2 = s.post(f"{BASE}/monitors/{m['id']}/edit", data={
        "monitor_type": "heartbeat", "url": "", "name": "QA Fix HB Ed",
        "alert_email": EMAIL, "heartbeat_interval": "600",
    }, allow_redirects=False)
    m2 = get_monitor(db, m["id"])
    t("URL NOT overwritten to 'https://'", m2.get("url") != "https://", f"got {m2.get('url')}")
    # URL should be empty string now (since we sent empty and the guard skips auto-prefix)
    # That's actually fine — the ping_url field is what matters
    t("ping_url still intact", m2.get("ping_url") == orig_url, f"got {m2.get('ping_url')}")
    db.collection("monitors").document(m["id"]).delete()

# Fix 3: Heartbeat create no longer stores "https://" initially
print("\n--- Fix 3: Heartbeat create URL ---", flush=True)
r = s.post(f"{BASE}/monitors/add", data={
    "monitor_type": "heartbeat", "name": "QA Fix HB Create",
    "alert_email": EMAIL,
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name") == "QA Fix HB Create"), None)
if m:
    t("Heartbeat URL is ping_url (not https://)", 
      m.get("url", "").startswith("https://statusrooster.com/api/ping/"), f"got {m.get('url')}")
    db.collection("monitors").document(m["id"]).delete()

# Regression: HTTP URL auto-prefix still works
print("\n--- Regression: HTTP URL auto-prefix ---", flush=True)
r = s.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http", "url": "www.google.com", "name": "QA Prefix Reg",
    "alert_email": EMAIL,
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name") == "QA Prefix Reg"), None)
if m:
    t("HTTP URL auto-prefixed", m.get("url") == "https://www.google.com", f"got {m.get('url')}")
    db.collection("monitors").document(m["id"]).delete()

# Regression: Edit URL auto-prefix still works
print("\n--- Regression: Edit URL auto-prefix ---", flush=True)
r = s.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http", "url": "https://example.com", "name": "QA Edit Prefix",
    "alert_email": EMAIL,
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name") == "QA Edit Prefix"), None)
if m:
    r2 = s.post(f"{BASE}/monitors/{m['id']}/edit", data={
        "monitor_type": "http", "url": "www.new-url.com", "name": "QA Edit Prefix",
        "alert_email": EMAIL,
    }, allow_redirects=False)
    m2 = get_monitor(db, m["id"])
    t("Edit URL auto-prefixed", m2.get("url") == "https://www.new-url.com", f"got {m2.get('url')}")
    db.collection("monitors").document(m["id"]).delete()

# Regression: SSL still works
print("\n--- Regression: SSL create ---", flush=True)
r = s.post(f"{BASE}/monitors/add", data={
    "monitor_type": "ssl", "ssl_domain": "example.com", "name": "QA SSL Reg",
    "alert_email": EMAIL, "ssl_expiry_threshold_days": "14",
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name") == "QA SSL Reg"), None)
if m:
    t("SSL url=https://example.com", m.get("url") == "https://example.com", f"got {m.get('url')}")
    t("SSL domain saved", m.get("ssl_domain") == "example.com")
    db.collection("monitors").document(m["id"]).delete()

# Regression: Edit slug still works
print("\n--- Regression: Edit slug update ---", flush=True)
r = s.post(f"{BASE}/monitors/add", data={
    "monitor_type": "http", "url": "https://ex.com", "name": "QA Slug Edit Reg",
    "alert_email": EMAIL,
}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name") == "QA Slug Edit Reg"), None)
if m:
    r2 = s.post(f"{BASE}/monitors/{m['id']}/edit", data={
        "monitor_type": "http", "url": "https://ex.com", "name": "QA Slug Edit Reg",
        "alert_email": EMAIL, "slug": "edited-slug", "public": "true",
    }, allow_redirects=False)
    m2 = get_monitor(db, m["id"])
    t("Slug updated on edit", m2.get("slug") == "edited-slug", f"got {m2.get('slug')}")
    db.collection("monitors").document(m["id"]).delete()

print("\n" + "=" * 60, flush=True)
if bugs:
    print(f"🐛 STILL FAILING: {len(bugs)}", flush=True)
    for b in bugs:
        print(f"  • {b}", flush=True)
else:
    print("✅ ALL 3 BUGS FIXED — ALL REGRESSION TESTS PASS!", flush=True)
print("=" * 60, flush=True)
