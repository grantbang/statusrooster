#!/usr/bin/env python3
"""
StatusRooster — Exhaustive Test Scenario Seeder

Creates monitors across all types and configurations to exercise every UX path,
including monitors that WILL FAIL to generate real incidents.

Usage:
  SR_API_KEY=sr_xxx python tests/seed_test_scenarios.py [--cleanup]

With --cleanup: deletes all monitors whose name starts with "[TEST]"
Without:        creates all test scenarios

Environment:
  SR_API_KEY      — required, your API key
  SR_BASE_URL     — optional, defaults to https://statusrooster.com
  SR_COOKIE       — optional, access_token cookie for check-now triggers
"""

import os
import sys
import time
import httpx

BASE_URL = os.environ.get("SR_BASE_URL", "https://statusrooster.com")
API_KEY = os.environ.get("SR_API_KEY", "")
COOKIE = os.environ.get("SR_COOKIE", "")

if not API_KEY:
    print("ERROR: Set SR_API_KEY environment variable")
    sys.exit(1)

HEADERS = {"X-API-Key": API_KEY}
TAG = "[TEST]"  # prefix for all test monitors — used for cleanup


# ═══════════════════════════════════════════════════════════════════════
# Test Scenarios
# ═══════════════════════════════════════════════════════════════════════

SCENARIOS = [
    # ─── GROUP 1: Dogfooding — Monitor StatusRooster itself ───────────
    {
        "name": f"{TAG} SR Homepage (dogfood)",
        "url": "https://statusrooster.com",
        "monitor_type": "http",
        "group": "Dogfood",
        "check_interval": 60,
        "keyword": "StatusRooster",
        "response_threshold_ms": ">2000",
        "public": False,
    },
    {
        "name": f"{TAG} SR API Health (dogfood)",
        "url": "https://statusrooster.com/api/v1/monitors",
        "monitor_type": "json_api",
        "group": "Dogfood",
        "check_interval": 60,
        "json_assertions": [
            {"path": "$.error", "operator": "eq", "value": None},
        ],
        "public": False,
    },
    {
        "name": f"{TAG} SR Login Page (dogfood)",
        "url": "https://statusrooster.com/login",
        "monitor_type": "http",
        "group": "Dogfood",
        "check_interval": 120,
        "keyword": "Sign in",
        "public": False,
    },
    {
        "name": f"{TAG} SR Docs (dogfood)",
        "url": "https://statusrooster.com/docs/api",
        "monitor_type": "http",
        "group": "Dogfood",
        "check_interval": 300,
        "keyword": "API",
        "public": False,
    },
    {
        "name": f"{TAG} SR SSL Cert (dogfood)",
        "monitor_type": "ssl",
        "ssl_domain": "statusrooster.com",
        "ssl_expiry_threshold_days": 14,
        "group": "Dogfood",
        "public": False,
    },

    # ─── GROUP 2: HTTP monitors — various configs ─────────────────────
    {
        "name": f"{TAG} HTTP Basic (UP)",
        "url": "https://httpbin.org/get",
        "monitor_type": "http",
        "group": "HTTP Tests",
        "check_interval": 300,
        "public": False,
    },
    {
        "name": f"{TAG} HTTP POST Method",
        "url": "https://httpbin.org/post",
        "monitor_type": "http",
        "http_method": "POST",
        "request_body": '{"test": true}',
        "request_content_type": "application/json",
        "group": "HTTP Tests",
        "check_interval": 300,
        "public": False,
    },
    {
        "name": f"{TAG} HTTP PUT Method",
        "url": "https://httpbin.org/put",
        "monitor_type": "http",
        "http_method": "PUT",
        "group": "HTTP Tests",
        "check_interval": 300,
        "public": False,
    },
    {
        "name": f"{TAG} HTTP HEAD Method",
        "url": "https://httpbin.org/get",
        "monitor_type": "http",
        "http_method": "HEAD",
        "group": "HTTP Tests",
        "check_interval": 300,
        "public": False,
    },
    {
        "name": f"{TAG} HTTP w/ Keyword (match)",
        "url": "https://httpbin.org/html",
        "monitor_type": "http",
        "keyword": "Moby-Dick",
        "group": "HTTP Tests",
        "check_interval": 300,
        "public": False,
    },
    {
        "name": f"{TAG} HTTP w/ Response Threshold",
        "url": "https://httpbin.org/delay/1",
        "monitor_type": "http",
        "response_threshold_ms": ">500",
        "group": "HTTP Tests",
        "check_interval": 300,
        "public": False,
    },
    {
        "name": f"{TAG} HTTP w/ Auth Header",
        "url": "https://httpbin.org/bearer",
        "monitor_type": "http",
        "bearer_token": "test-token-123",
        "group": "HTTP Tests",
        "check_interval": 300,
        "public": False,
    },
    {
        "name": f"{TAG} HTTP w/ Basic Auth",
        "url": "https://httpbin.org/basic-auth/user/pass",
        "monitor_type": "http",
        "basic_auth_user": "user",
        "basic_auth_pass": "pass",
        "group": "HTTP Tests",
        "check_interval": 300,
        "public": False,
    },

    # ─── GROUP 3: Monitors that WILL FAIL (incident generators) ───────
    {
        "name": f"{TAG} FAIL: 500 Server Error",
        "url": "https://httpbin.org/status/500",
        "monitor_type": "http",
        "group": "Fail Scenarios",
        "check_interval": 60,
        "public": False,
    },
    {
        "name": f"{TAG} FAIL: 404 Not Found",
        "url": "https://httpbin.org/status/404",
        "monitor_type": "http",
        "group": "Fail Scenarios",
        "check_interval": 60,
    },
    {
        "name": f"{TAG} FAIL: 403 Forbidden",
        "url": "https://httpbin.org/status/403",
        "monitor_type": "http",
        "group": "Fail Scenarios",
        "check_interval": 60,
    },
    {
        "name": f"{TAG} FAIL: 502 Bad Gateway",
        "url": "https://httpbin.org/status/502",
        "monitor_type": "http",
        "group": "Fail Scenarios",
        "check_interval": 60,
    },
    {
        "name": f"{TAG} FAIL: Timeout",
        "url": "https://httpbin.org/delay/30",
        "monitor_type": "http",
        "timeout": 3,
        "group": "Fail Scenarios",
        "check_interval": 60,
    },
    {
        "name": f"{TAG} FAIL: DNS Resolution",
        "url": "https://this-domain-does-not-exist-sr-test.invalid",
        "monitor_type": "http",
        "group": "Fail Scenarios",
        "check_interval": 60,
    },
    {
        "name": f"{TAG} FAIL: Keyword Missing",
        "url": "https://httpbin.org/html",
        "monitor_type": "http",
        "keyword": "THIS_KEYWORD_WILL_NEVER_EXIST_XYZZY",
        "group": "Fail Scenarios",
        "check_interval": 60,
    },

    # ─── GROUP 4: JSON/API monitors ───────────────────────────────────
    {
        "name": f"{TAG} JSON API (UP)",
        "url": "https://httpbin.org/json",
        "monitor_type": "json_api",
        "group": "JSON Tests",
        "check_interval": 300,
    },
    {
        "name": f"{TAG} JSON POST w/ Body",
        "url": "https://httpbin.org/post",
        "monitor_type": "json_api",
        "http_method": "POST",
        "request_body": '{"key": "value"}',
        "request_content_type": "application/json",
        "group": "JSON Tests",
        "check_interval": 300,
    },
    {
        "name": f"{TAG} FAIL: JSON Assertion Fail",
        "url": "https://httpbin.org/json",
        "monitor_type": "json_api",
        "json_assertions": [
            {"path": "$.doesNotExist", "operator": "eq", "value": "impossible"},
        ],
        "group": "Fail Scenarios",
        "check_interval": 60,
    },

    # ─── GROUP 5: Heartbeat monitors ──────────────────────────────────
    {
        "name": f"{TAG} Heartbeat (will miss)",
        "monitor_type": "heartbeat",
        "heartbeat_interval": 60,
        "heartbeat_grace_period": 30,
        "group": "Heartbeat Tests",
    },
    {
        "name": f"{TAG} Heartbeat (long interval)",
        "monitor_type": "heartbeat",
        "heartbeat_interval": 3600,
        "heartbeat_grace_period": 300,
        "group": "Heartbeat Tests",
    },

    # ─── GROUP 6: SSL monitors ────────────────────────────────────────
    {
        "name": f"{TAG} SSL Valid (Google)",
        "monitor_type": "ssl",
        "ssl_domain": "google.com",
        "ssl_expiry_threshold_days": 7,
        "group": "SSL Tests",
    },
    {
        "name": f"{TAG} SSL Valid (GitHub)",
        "monitor_type": "ssl",
        "ssl_domain": "github.com",
        "ssl_expiry_threshold_days": 14,
        "group": "SSL Tests",
    },
    {
        "name": f"{TAG} FAIL: SSL Expired",
        "monitor_type": "ssl",
        "ssl_domain": "expired.badssl.com",
        "ssl_expiry_threshold_days": 30,
        "group": "Fail Scenarios",
    },

    # ─── GROUP 7: Paused monitor (verify paused UX) ──────────────────
    {
        "name": f"{TAG} Paused Monitor",
        "url": "https://httpbin.org/get",
        "monitor_type": "http",
        "paused": True,
        "group": "Edge Cases",
        "check_interval": 300,
    },

    # ─── GROUP 8: No group (verify ungrouped display) ─────────────────
    {
        "name": f"{TAG} Ungrouped HTTP",
        "url": "https://httpbin.org/get",
        "monitor_type": "http",
        "check_interval": 300,
    },
]


def create_all():
    """Create all test scenario monitors."""
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)
    created = []
    heartbeat_pings = []

    for i, scenario in enumerate(SCENARIOS, 1):
        # Default to private unless explicitly set public
        if "public" not in scenario:
            scenario["public"] = False
        print(f"  [{i:2d}/{len(SCENARIOS)}] Creating: {scenario['name']}...", end=" ", flush=True)
        try:
            resp = client.post("/api/v1/monitors", json=scenario, headers=HEADERS)
            if resp.status_code == 201:
                data = resp.json()["data"]
                mid = data["id"]
                created.append(mid)
                print(f"OK  (id={mid})")

                # Track heartbeat ping URLs
                if scenario.get("monitor_type") == "heartbeat":
                    ping_url = data.get("ping_url") or data.get("url", "")
                    heartbeat_pings.append((scenario["name"], ping_url))
            else:
                print(f"FAIL ({resp.status_code}: {resp.text[:100]})")
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\n{'='*60}")
    print(f"Created {len(created)} monitors")

    if heartbeat_pings:
        print(f"\n--- Heartbeat Ping URLs ---")
        print("Ping one of these to test 'UP' state; leave the other to trigger 'DOWN':")
        for name, url in heartbeat_pings:
            print(f"  {name}")
            print(f"    curl {url}")
        print()

    # Trigger check-now on fail scenarios to generate incidents immediately
    if COOKIE:
        print("\n--- Triggering check-now on fail scenarios ---")
        fail_ids = []
        # Re-fetch monitors to find the fail ones
        resp = client.get("/api/v1/monitors", headers=HEADERS)
        if resp.status_code == 200:
            monitors = resp.json()["data"]
            fail_ids = [m["id"] for m in monitors if m.get("name", "").startswith(f"{TAG} FAIL:")]

        for mid in fail_ids:
            print(f"  Checking {mid}...", end=" ", flush=True)
            try:
                resp = client.post(
                    f"/monitors/{mid}/check-now",
                    cookies={"access_token": COOKIE},
                )
                if resp.status_code == 200:
                    result = resp.json()
                    status = "UP" if result.get("is_up") else "DOWN"
                    print(f"{status} (code={result.get('status_code')})")
                elif resp.status_code == 429:
                    print("rate-limited, skipping")
                else:
                    print(f"HTTP {resp.status_code}")
            except Exception as e:
                print(f"error: {e}")
            time.sleep(1)  # avoid rate limiting
    else:
        print("\nTip: Set SR_COOKIE=<access_token> to trigger immediate checks on fail monitors.")
        print("     This generates incidents right away instead of waiting for the cron.")

    # Ping one heartbeat to make it "up", leave the other to go "down"
    if heartbeat_pings and len(heartbeat_pings) >= 2:
        print(f"\n--- Pinging the long-interval heartbeat to mark it UP ---")
        _, ping_url = heartbeat_pings[1]  # the long-interval one
        try:
            resp = client.get(ping_url)
            print(f"  Pinged: {resp.status_code}")
        except Exception as e:
            print(f"  Error: {e}")
        print(f"  (Leaving short-interval heartbeat un-pinged — it will go DOWN after grace period)")

    print(f"\n{'='*60}")
    print("WHAT TO VERIFY:")
    print("="*60)
    print("""
DASHBOARD:
  [ ] Group badges show for "Dogfood", "HTTP Tests", etc.
  [ ] No group badge on "Ungrouped HTTP"
  [ ] Type labels correct: HTTP, JSON/API, Heartbeat, SSL
  [ ] SSL monitors show days remaining, NOT response time
  [ ] SSL monitors do NOT show check interval badge
  [ ] Heartbeat monitors show "No ping yet" or "✓ Pinged"
  [ ] Paused monitor shows ⏸ and gray styling
  [ ] "Up for X" / "Down for X" status durations appear
  [ ] 30-day uptime bars render (will be mostly gray/empty for new monitors)
  [ ] Filter by group works (Dogfood, HTTP Tests, Fail Scenarios, etc.)
  [ ] Filter by type works (HTTP, JSON/API, Heartbeat, SSL)
  [ ] Filter by status works (once checks run: Up, Down)
  [ ] Sort "Down first" pushes failed monitors to top

MONITOR DETAIL (check each type):
  HTTP monitor:
    [ ] Status code badge (200 = green) in subtitle
    [ ] "Checked every 60s" in stat card
    [ ] Response time chart shows with threshold line (for threshold monitor)
    [ ] "Check now" button works
  HTTP POST monitor:
    [ ] "POST" method badge in subtitle
  JSON/API monitor:
    [ ] "{ } JSON/API monitor for" in subtitle
    [ ] Assertions section visible
  Heartbeat monitor:
    [ ] "Expected every 1m (30s grace)" in subtitle
    [ ] Ping URL bar visible
    [ ] NO "Check now" button (passive monitor)
    [ ] "Expected every 1m" in stat card (not "Checked every 60s")
  SSL monitor:
    [ ] "SSL certificate monitor for" in subtitle
    [ ] "Certificate checked periodically" in stat card
    [ ] NO response time chart
    [ ] SSL details section visible
    [ ] NO check interval badge
  Paused monitor:
    [ ] "Paused" status, "Checks suspended"
    [ ] "Resume" button shown
  Group breadcrumb:
    [ ] Grouped monitors show "Monitoring / GroupName" breadcrumb
    [ ] Ungrouped monitor shows only "Monitoring" back link

INCIDENTS (after fail monitors run):
  [ ] Ongoing incidents show red left border (5xx) or orange (4xx) or gray (timeout)
  [ ] "Ongoing (Xm)" elapsed timer ticks live
  [ ] Incident rows clickable → detail page
  [ ] Severity colors match: 500→red, 404→orange, timeout→gray

INCIDENT DETAIL:
  [ ] Failed check count shown
  [ ] Regions data shown (if multi-region check)
  [ ] Root cause text correct per type
  [ ] Activity timeline shows "detected" event
  [ ] Duration shows "ongoing"

EDIT MONITOR:
  [ ] HTTP: check interval slider visible
  [ ] SSL: NO check interval slider
  [ ] Heartbeat: NO check interval slider (heartbeat interval in its own section)

RESPONSIVE (resize browser or use devtools):
  375px:  [ ] Cards readable, uptime bars hidden, incident grid stacks
  768px:  [ ] Incident group/type columns hidden
  1024px: [ ] Full layout works
  1440px: [ ] Full layout works

STATUS PAGES:
  [ ] /s/<slug> works for public monitors
  [ ] Dogfood monitors visible on status page
""")
    client.close()


def cleanup():
    """Delete all monitors with the test tag."""
    client = httpx.Client(base_url=BASE_URL, timeout=30.0)
    resp = client.get("/api/v1/monitors", headers=HEADERS)
    if resp.status_code != 200:
        print(f"Failed to list monitors: {resp.status_code}")
        return

    monitors = resp.json()["data"]
    test_monitors = [m for m in monitors if m.get("name", "").startswith(TAG)]

    if not test_monitors:
        print("No test monitors found.")
        return

    print(f"Found {len(test_monitors)} test monitors to delete:")
    for m in test_monitors:
        print(f"  Deleting: {m['name']} ({m['id']})...", end=" ", flush=True)
        try:
            resp = client.delete(f"/api/v1/monitors/{m['id']}", headers=HEADERS)
            print("OK" if resp.status_code == 200 else f"FAIL ({resp.status_code})")
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\nCleanup complete.")
    client.close()


if __name__ == "__main__":
    if "--cleanup" in sys.argv:
        print("=== CLEANUP MODE ===")
        cleanup()
    else:
        print("=== CREATING TEST SCENARIOS ===")
        print(f"Target: {BASE_URL}")
        print(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
        print()
        create_all()
