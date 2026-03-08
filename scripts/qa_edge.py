#!/usr/bin/env python3
"""Edge case QA tests."""
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
    print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        bugs.append(f"{name}: {detail}")

print("=== EDGE CASE TESTS ===")

# 1) Heartbeat empty URL edit
print("\n--- Heartbeat edit with empty URL ---")
r = s.post(f"{BASE}/monitors/add", data={"monitor_type":"heartbeat","name":"QA HB Edge","alert_email":EMAIL}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name")=="QA HB Edge"), None)
if m:
    orig = m.get("url")
    r2 = s.post(f"{BASE}/monitors/{m['id']}/edit", data={"monitor_type":"heartbeat","url":"","name":"QA HB Edge Ed","alert_email":EMAIL,"heartbeat_interval":"600"}, allow_redirects=False)
    m2 = get_monitor(db, m["id"])
    t("HB URL not overwritten to 'https://'", m2.get("url") != "https://", f"got {m2.get('url')}")
    db.collection("monitors").document(m["id"]).delete()

# 2) SSL domain with protocol 
print("\n--- SSL domain with protocol ---")
r = s.post(f"{BASE}/monitors/add", data={"monitor_type":"ssl","ssl_domain":"https://github.com","name":"QA SSL Proto","alert_email":EMAIL}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name")=="QA SSL Proto"), None)
if m:
    t("SSL URL uses domain as-is when it has protocol", m.get("url")=="https://github.com", f"got {m.get('url')}")
    db.collection("monitors").document(m["id"]).delete()

# 3) Public off on edit
print("\n--- Public toggle OFF ---")
r = s.post(f"{BASE}/monitors/add", data={"monitor_type":"http","url":"https://ex.com","name":"QA Pub Toggle","alert_email":EMAIL,"public":"true"}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name")=="QA Pub Toggle"), None)
if m:
    t("Created as public", m.get("public") is True)
    r2 = s.post(f"{BASE}/monitors/{m['id']}/edit", data={"monitor_type":"http","url":"https://ex.com","name":"QA Pub Toggle","alert_email":EMAIL}, allow_redirects=False)
    m2 = get_monitor(db, m["id"])
    t("Public toggled OFF", m2.get("public") is False, f"got {m2.get('public')}")
    db.collection("monitors").document(m["id"]).delete()

# 4) Expected status clearing
print("\n--- Expected status code clearing ---")
r = s.post(f"{BASE}/monitors/add", data={"monitor_type":"http","url":"https://ex.com","name":"QA SC Clear","alert_email":EMAIL,"expected_status_code":"201"}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name")=="QA SC Clear"), None)
if m:
    t("Status code set to 201", m.get("expected_status_code")==201)
    r2 = s.post(f"{BASE}/monitors/{m['id']}/edit", data={"monitor_type":"http","url":"https://ex.com","name":"QA SC Clear","alert_email":EMAIL,"expected_status_code":""}, allow_redirects=False)
    m2 = get_monitor(db, m["id"])
    t("Status code cleared to None", m2.get("expected_status_code") is None, f"got {m2.get('expected_status_code')}")
    db.collection("monitors").document(m["id"]).delete()

# 5) Slug ignored on create
print("\n--- Slug field on Add form ---")
r = s.post(f"{BASE}/monitors/add", data={"monitor_type":"http","url":"https://ex.com","name":"QA Slug Test","alert_email":EMAIL,"slug":"my-custom-slug","public":"true"}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name")=="QA Slug Test"), None)
if m:
    t("Custom slug used on create", m.get("slug")=="my-custom-slug", f"got {m.get('slug')} (auto-generated, not custom)")
    db.collection("monitors").document(m["id"]).delete()

# 6) Edit monitor — update slug
print("\n--- Slug update on Edit ---")
r = s.post(f"{BASE}/monitors/add", data={"monitor_type":"http","url":"https://ex.com","name":"QA Slug Edit","alert_email":EMAIL,"public":"true"}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name")=="QA Slug Edit"), None)
if m:
    r2 = s.post(f"{BASE}/monitors/{m['id']}/edit", data={"monitor_type":"http","url":"https://ex.com","name":"QA Slug Edit","alert_email":EMAIL,"slug":"custom-edit-slug","public":"true"}, allow_redirects=False)
    m2 = get_monitor(db, m["id"])
    t("Slug updated on edit", m2.get("slug")=="custom-edit-slug", f"got {m2.get('slug')}")
    db.collection("monitors").document(m["id"]).delete()

# 7) Heartbeat URL auto-prefix on create (edge: empty URL gets https://)
print("\n--- Heartbeat create — empty URL auto-prefix ---")
r = s.post(f"{BASE}/monitors/add", data={"monitor_type":"heartbeat","name":"QA HB Prefix","alert_email":EMAIL}, allow_redirects=False)
monitors = list_monitors_by_user(db, USER_ID)
m = next((x for x in monitors if x.get("name")=="QA HB Prefix"), None)
if m:
    # The URL auto-prefix turns "" into "https://" before create_monitor
    # But after create, update_monitor sets url to ping_url
    # So final state should be correct, but initial create gets url="https://"
    t("Heartbeat final URL is ping_url", m.get("url","").startswith("https://statusrooster.com"), f"got {m.get('url')}")
    db.collection("monitors").document(m["id"]).delete()

print("\n" + "=" * 50)
if bugs:
    print(f"🐛 BUGS FOUND: {len(bugs)}")
    for b in bugs:
        print(f"  • {b}")
else:
    print("✅ ALL EDGE CASE TESTS PASSED!")
print("=" * 50)
