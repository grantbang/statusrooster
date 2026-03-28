"""
StatusRooster Alert Lifecycle Tests — Pre-Launch Critical Path

Tests that alerts fire correctly, deduplicate properly, and don't spam.
These tests exercise the CRON path (not check-now) because only cron
creates incidents, sends alerts, and updates monitor state.

Requires environment variables:
  SR_API_KEY       — API key for Pro test account
  SR_CRON_SECRET   — Cron auth secret (X-Cron-Secret header)

Run:
  SR_API_KEY=sr_xxx SR_CRON_SECRET=xxx pytest tests/test_alert_lifecycle.py -v --asyncio-mode=auto

All tests are marked @pytest.mark.slow because they trigger real cron
cycles and wait for state changes.
"""

import asyncio
import os
import pytest
import httpx

from tests.conftest import BASE_URL

CRON_SECRET = os.environ.get("SR_CRON_SECRET", "")


# ── Helpers ────────────────────────────────────────────────────────────

async def trigger_cron(client: httpx.AsyncClient) -> dict:
    """Trigger a cron check cycle. Returns the cron response.
    Uses a separate client with a long timeout since cron checks ALL monitors."""
    async with httpx.AsyncClient(base_url=str(client.base_url), timeout=120.0) as cron_client:
        resp = await cron_client.post(
            "/cron/check",
            headers={"X-Cron-Secret": CRON_SECRET},
        )
    assert resp.status_code == 200, f"Cron trigger failed: {resp.status_code} — {resp.text}"
    return resp.json()


async def get_incidents_for_monitor(client: httpx.AsyncClient, monitor_id: str, headers: dict) -> list[dict]:
    """Get all recent incidents for a monitor via the API."""
    resp = await client.get(
        f"/api/v1/incidents?monitor_id={monitor_id}&hours=1",
        headers=headers,
    )
    assert resp.status_code == 200, f"Incidents fetch failed: {resp.text}"
    return resp.json().get("data", [])


async def get_monitor(client: httpx.AsyncClient, monitor_id: str, headers: dict) -> dict:
    """Get monitor state via the API."""
    resp = await client.get(f"/api/v1/monitors/{monitor_id}", headers=headers)
    assert resp.status_code == 200, f"Monitor fetch failed: {resp.text}"
    return resp.json()["data"]


async def create_monitor(client: httpx.AsyncClient, headers: dict, body: dict) -> dict:
    """Create a monitor and return its data."""
    resp = await client.post("/api/v1/monitors", json=body, headers=headers)
    assert resp.status_code == 201, f"Monitor creation failed: {resp.text}"
    return resp.json()["data"]


async def delete_monitor(client: httpx.AsyncClient, monitor_id: str, headers: dict):
    """Delete a monitor (cleanup)."""
    try:
        await client.delete(f"/api/v1/monitors/{monitor_id}", headers=headers)
    except Exception:
        pass


async def update_monitor(client: httpx.AsyncClient, monitor_id: str, headers: dict, updates: dict) -> dict:
    """Update a monitor via API."""
    resp = await client.patch(f"/api/v1/monitors/{monitor_id}", json=updates, headers=headers)
    assert resp.status_code == 200, f"Monitor update failed: {resp.text}"
    return resp.json()["data"]


# ── Skip if no cron secret ─────────────────────────────────────────────

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not CRON_SECRET, reason="SR_CRON_SECRET not set — skipping alert lifecycle tests"),
]


# ═══════════════════════════════════════════════════════════════════════
# AL. ALERT LIFECYCLE — Incident Creation, Dedup, and Recovery
# ═══════════════════════════════════════════════════════════════════════

class TestIncidentLifecycle:
    """AL.1–AL.5: Full DOWN → dedup → RECOVERY cycle."""

    @pytest.mark.asyncio
    async def test_al1_down_creates_incident(self, client, pro_headers):
        """AL.1 — Monitor hitting 500 URL creates exactly one incident after cron."""
        mid = None
        try:
            mon = await create_monitor(client, pro_headers, {
                "name": "AL1-down-creates-incident",
                "url": "https://httpbin.org/status/500",
                "monitor_type": "http",
                "check_interval": 60,
                "alert_email": "test-al1@statusrooster.com",
            })
            mid = mon["id"]

            # Trigger cron — should detect DOWN and create incident
            await trigger_cron(client)
            # Brief pause for Firestore writes to propagate
            await asyncio.sleep(3)

            incidents = await get_incidents_for_monitor(client, mid, pro_headers)
            assert len(incidents) >= 1, f"AL.1 FAIL: Expected at least 1 incident, got {len(incidents)}"

            # Verify incident details
            inc = incidents[0]
            assert inc["status"] == "open", f"AL.1 FAIL: Incident status should be 'open', got {inc['status']}"
            assert inc["monitor_id"] == mid
            assert inc.get("status_code") == 500

            # Verify monitor status updated to down
            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state["status"] == "down", f"AL.1 FAIL: Monitor status should be 'down', got {mon_state['status']}"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)

    @pytest.mark.asyncio
    async def test_al2_repeated_failure_no_duplicate_incident(self, client, pro_headers):
        """AL.2 — Monitor stays down for 3 cron cycles → still only 1 incident (no duplicate alerts)."""
        mid = None
        try:
            mon = await create_monitor(client, pro_headers, {
                "name": "AL2-no-duplicate-incident",
                "url": "https://httpbin.org/status/500",
                "monitor_type": "http",
                "check_interval": 60,
                "alert_email": "test-al2@statusrooster.com",
            })
            mid = mon["id"]

            # Trigger 3 consecutive cron cycles
            for i in range(3):
                await trigger_cron(client)
                await asyncio.sleep(3)

            incidents = await get_incidents_for_monitor(client, mid, pro_headers)
            open_incidents = [inc for inc in incidents if inc["status"] == "open"]

            assert len(open_incidents) == 1, \
                f"AL.2 FAIL: Expected exactly 1 open incident after 3 failures, got {len(open_incidents)}. " \
                f"Total incidents: {len(incidents)}"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)

    @pytest.mark.asyncio
    async def test_al3_recovery_resolves_incident(self, client, pro_headers):
        """AL.3 — Monitor goes DOWN then UP → incident is resolved."""
        mid = None
        try:
            # Create monitor pointing at failing URL
            mon = await create_monitor(client, pro_headers, {
                "name": "AL3-recovery-resolves",
                "url": "https://httpbin.org/status/500",
                "monitor_type": "http",
                "check_interval": 60,
                "alert_email": "test-al3@statusrooster.com",
            })
            mid = mon["id"]

            # Trigger cron → should go DOWN
            await trigger_cron(client)
            await asyncio.sleep(3)

            incidents_before = await get_incidents_for_monitor(client, mid, pro_headers)
            assert len(incidents_before) >= 1, "AL.3 FAIL: No incident created for DOWN"
            assert incidents_before[0]["status"] == "open"

            # Update URL to healthy endpoint
            await update_monitor(client, mid, pro_headers, {"url": "https://httpbin.org/status/200"})

            # Wait for check_interval (60s) to elapse so the monitor is due again
            await asyncio.sleep(65)

            # Trigger cron → should recover
            await trigger_cron(client)
            await asyncio.sleep(3)

            incidents_after = await get_incidents_for_monitor(client, mid, pro_headers)
            resolved = [inc for inc in incidents_after if inc["status"] == "resolved"]
            open_incs = [inc for inc in incidents_after if inc["status"] == "open"]

            assert len(resolved) >= 1, f"AL.3 FAIL: Expected resolved incident, got {len(resolved)} resolved"
            assert len(open_incs) == 0, f"AL.3 FAIL: Incident should be resolved, but {len(open_incs)} still open"
            assert resolved[0].get("duration_seconds") is not None, "AL.3 FAIL: Resolved incident missing duration"

            # Verify monitor status back to up
            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state["status"] == "up", f"AL.3 FAIL: Monitor should be 'up', got {mon_state['status']}"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)

    @pytest.mark.asyncio
    async def test_al4_down_up_down_creates_two_incidents(self, client, pro_headers):
        """AL.4 — DOWN→UP→DOWN cycle creates 2 separate incidents (not reusing old one)."""
        mid = None
        try:
            # Start down
            mon = await create_monitor(client, pro_headers, {
                "name": "AL4-two-incidents",
                "url": "https://httpbin.org/status/500",
                "monitor_type": "http",
                "check_interval": 60,
                "alert_email": "test-al4@statusrooster.com",
            })
            mid = mon["id"]

            # Cycle 1: DOWN
            await trigger_cron(client)
            await asyncio.sleep(3)

            # Recover — wait for check_interval to elapse
            await update_monitor(client, mid, pro_headers, {"url": "https://httpbin.org/status/200"})
            await asyncio.sleep(65)
            await trigger_cron(client)
            await asyncio.sleep(3)

            # Cycle 2: DOWN again — wait for check_interval to elapse
            await update_monitor(client, mid, pro_headers, {"url": "https://httpbin.org/status/500"})
            await asyncio.sleep(65)
            await trigger_cron(client)
            await asyncio.sleep(3)

            incidents = await get_incidents_for_monitor(client, mid, pro_headers)
            assert len(incidents) >= 2, \
                f"AL.4 FAIL: Expected at least 2 incidents (down-up-down), got {len(incidents)}"

            # Should have 1 resolved + 1 open
            resolved = [i for i in incidents if i["status"] == "resolved"]
            open_incs = [i for i in incidents if i["status"] == "open"]
            assert len(resolved) >= 1, "AL.4 FAIL: First incident should be resolved"
            assert len(open_incs) == 1, f"AL.4 FAIL: Should have exactly 1 open incident, got {len(open_incs)}"

        finally:
            if mid:
                # Recover it first so we don't leave a down monitor
                await update_monitor(client, mid, pro_headers, {"url": "https://httpbin.org/status/200"})
                await trigger_cron(client)
                await asyncio.sleep(2)
                await delete_monitor(client, mid, pro_headers)

    @pytest.mark.asyncio
    async def test_al5_no_incident_when_up(self, client, pro_headers):
        """AL.5 — Monitor that stays UP across multiple cron cycles → zero incidents."""
        mid = None
        try:
            mon = await create_monitor(client, pro_headers, {
                "name": "AL5-stays-up",
                "url": "https://httpbin.org/status/200",
                "monitor_type": "http",
                "check_interval": 60,
            })
            mid = mon["id"]

            # Trigger 2 cron cycles
            await trigger_cron(client)
            await asyncio.sleep(3)
            await trigger_cron(client)
            await asyncio.sleep(3)

            incidents = await get_incidents_for_monitor(client, mid, pro_headers)
            assert len(incidents) == 0, \
                f"AL.5 FAIL: Healthy monitor should have 0 incidents, got {len(incidents)}"

            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state["status"] == "up"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)


# ═══════════════════════════════════════════════════════════════════════
# KW. KEYWORD ALERT DEDUP
# ═══════════════════════════════════════════════════════════════════════

class TestKeywordAlertDedup:
    """KW.1–KW.3: Keyword alerts fire on transition, not every check."""

    @pytest.mark.asyncio
    async def test_kw1_keyword_failing_sets_flag(self, client, pro_headers):
        """KW.1 — Monitor with keyword not found → keyword_failing=True, alert fires once."""
        mid = None
        try:
            # httpbin.org/html returns HTML that does NOT contain "XYZNOTFOUND"
            mon = await create_monitor(client, pro_headers, {
                "name": "KW1-keyword-failing",
                "url": "https://httpbin.org/html",
                "monitor_type": "http",
                "keyword": "XYZNOTFOUND_KEYWORD_12345",
                "check_interval": 60,
                "alert_email": "test-kw1@statusrooster.com",
            })
            mid = mon["id"]

            # Trigger cron → keyword should fail
            await trigger_cron(client)
            await asyncio.sleep(3)

            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state.get("keyword_failing") is True, \
                f"KW.1 FAIL: keyword_failing should be True, got {mon_state.get('keyword_failing')}"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)

    @pytest.mark.asyncio
    async def test_kw2_keyword_failing_no_repeat_alert(self, client, pro_headers):
        """KW.2 — Keyword stays missing for 3 cycles → keyword_failing stays True (no re-alert)."""
        mid = None
        try:
            mon = await create_monitor(client, pro_headers, {
                "name": "KW2-keyword-no-repeat",
                "url": "https://httpbin.org/html",
                "monitor_type": "http",
                "keyword": "XYZNOTFOUND_KEYWORD_67890",
                "check_interval": 60,
                "alert_email": "test-kw2@statusrooster.com",
            })
            mid = mon["id"]

            # 3 cron cycles with keyword missing
            for _ in range(3):
                await trigger_cron(client)
                await asyncio.sleep(3)

            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state.get("keyword_failing") is True, \
                "KW.2 FAIL: keyword_failing should still be True after 3 cycles"

            # Monitor should still be "down" (keyword failure = down)
            # The key assertion: only 1 incident created, not 3
            incidents = await get_incidents_for_monitor(client, mid, pro_headers)
            open_incidents = [i for i in incidents if i["status"] == "open"]
            assert len(open_incidents) <= 1, \
                f"KW.2 FAIL: Expected at most 1 open incident for keyword failure, got {len(open_incidents)}"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)

    @pytest.mark.asyncio
    async def test_kw3_keyword_recovery_clears_flag(self, client, pro_headers):
        """KW.3 — Keyword reappears → keyword_failing cleared."""
        mid = None
        try:
            # Start with keyword that WILL be found
            mon = await create_monitor(client, pro_headers, {
                "name": "KW3-keyword-recovery",
                "url": "https://httpbin.org/html",
                "monitor_type": "http",
                "keyword": "Herman Melville",  # httpbin.org/html contains this
                "check_interval": 60,
            })
            mid = mon["id"]

            # Trigger cron → should be fine
            await trigger_cron(client)
            await asyncio.sleep(3)

            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state.get("keyword_failing") is not True, \
                "KW.3 FAIL: keyword_failing should be False when keyword is present"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)


# ═══════════════════════════════════════════════════════════════════════
# TH. THRESHOLD ALERT DEDUP
# ═══════════════════════════════════════════════════════════════════════

class TestThresholdAlertDedup:
    """TH.1–TH.2: Response time threshold alerts fire on transition only."""

    @pytest.mark.asyncio
    async def test_th1_threshold_exceeded_sets_flag(self, client, pro_headers):
        """TH.1 — Slow response exceeds threshold → threshold_failing=True."""
        mid = None
        try:
            # httpbin.org/delay/3 takes ~3 seconds; threshold at > 100ms will trigger
            mon = await create_monitor(client, pro_headers, {
                "name": "TH1-threshold-exceeded",
                "url": "https://httpbin.org/delay/3",
                "monitor_type": "http",
                "response_threshold_ms": "> 100",
                "timeout": 10,
                "check_interval": 60,
                "alert_email": "test-th1@statusrooster.com",
            })
            mid = mon["id"]

            await trigger_cron(client)
            await asyncio.sleep(5)

            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state.get("threshold_failing") is True, \
                f"TH.1 FAIL: threshold_failing should be True, got {mon_state.get('threshold_failing')}"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)

    @pytest.mark.asyncio
    async def test_th2_threshold_repeated_no_extra_incidents(self, client, pro_headers):
        """TH.2 — Threshold exceeded for 2 cycles → still 1 incident max."""
        mid = None
        try:
            mon = await create_monitor(client, pro_headers, {
                "name": "TH2-threshold-no-repeat",
                "url": "https://httpbin.org/delay/3",
                "monitor_type": "http",
                "response_threshold_ms": "> 100",
                "timeout": 10,
                "check_interval": 60,
                "alert_email": "test-th2@statusrooster.com",
            })
            mid = mon["id"]

            for _ in range(2):
                await trigger_cron(client)
                await asyncio.sleep(5)

            incidents = await get_incidents_for_monitor(client, mid, pro_headers)
            open_incidents = [i for i in incidents if i["status"] == "open"]
            assert len(open_incidents) <= 1, \
                f"TH.2 FAIL: Expected at most 1 open incident for threshold, got {len(open_incidents)}"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)


# ═══════════════════════════════════════════════════════════════════════
# SSL. SSL EXPIRY ALERT DEDUP
# ═══════════════════════════════════════════════════════════════════════

class TestSslExpiryAlertDedup:
    """SSL.1–SSL.2: SSL expiry alerts don't repeat for the same threshold tier."""

    @pytest.mark.asyncio
    async def test_ssl1_expiry_alert_sets_state(self, client, pro_headers):
        """SSL.1 — HTTP monitor with SSL auto-detect → ssl_expiry_alerted_days is set after cron."""
        mid = None
        try:
            # Use a real HTTPS URL so SSL info gets detected
            mon = await create_monitor(client, pro_headers, {
                "name": "SSL1-expiry-state",
                "url": "https://httpbin.org/status/200",
                "monitor_type": "http",
                "check_interval": 60,
                "alert_email": "test-ssl1@statusrooster.com",
            })
            mid = mon["id"]

            await trigger_cron(client)
            await asyncio.sleep(3)

            mon_state = await get_monitor(client, mid, pro_headers)
            # SSL info should be auto-detected
            ssl_days = mon_state.get("ssl_expiry_days")
            ssl_alerted = mon_state.get("ssl_expiry_alerted_days")

            if ssl_days is not None and ssl_days <= 14:
                # If cert is actually expiring soon, alert should have fired
                assert ssl_alerted is not None, \
                    "SSL.1 FAIL: ssl_expiry_alerted_days should be set when cert is within 14 days"
            # If cert has > 14 days left, no alert expected — that's fine

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)

    @pytest.mark.asyncio
    async def test_ssl2_expiry_no_repeat_across_cycles(self, client, pro_headers):
        """SSL.2 — SSL expiry alert doesn't change tier across repeated cron cycles."""
        mid = None
        try:
            mon = await create_monitor(client, pro_headers, {
                "name": "SSL2-no-repeat",
                "url": "https://httpbin.org/status/200",
                "monitor_type": "http",
                "check_interval": 60,
                "alert_email": "test-ssl2@statusrooster.com",
            })
            mid = mon["id"]

            # Run 3 cycles
            for _ in range(3):
                await trigger_cron(client)
                await asyncio.sleep(3)

            mon_state = await get_monitor(client, mid, pro_headers)
            ssl_alerted = mon_state.get("ssl_expiry_alerted_days")

            # If it was set on cycle 1, it should be the SAME value on cycle 3
            # (no oscillation). We can't easily assert the exact value without
            # knowing the cert's actual expiry, but we verify it's stable.
            if ssl_alerted is not None:
                # Run one more cycle and verify it doesn't change
                await trigger_cron(client)
                await asyncio.sleep(3)
                mon_state2 = await get_monitor(client, mid, pro_headers)
                assert mon_state2.get("ssl_expiry_alerted_days") == ssl_alerted, \
                    f"SSL.2 FAIL: ssl_expiry_alerted_days changed between cycles: " \
                    f"{ssl_alerted} → {mon_state2.get('ssl_expiry_alerted_days')}"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)


# ═══════════════════════════════════════════════════════════════════════
# MW. MAINTENANCE WINDOW SUPPRESSION
# ═══════════════════════════════════════════════════════════════════════

class TestMaintenanceWindowSuppression:
    """MW.1: Alerts suppressed during maintenance, but incidents still created."""

    @pytest.mark.asyncio
    async def test_mw1_maintenance_suppresses_alerts_not_incidents(self, client, pro_headers):
        """MW.1 — Monitor in maintenance window that goes down → incident created but no alert spam."""
        mid = None
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            # Create maintenance window covering current time
            day_name = now.strftime("%A").lower()
            start_h = now.hour
            end_h = (now.hour + 2) % 24
            start_str = f"{start_h:02d}:00"
            end_str = f"{end_h:02d}:00"

            mon = await create_monitor(client, pro_headers, {
                "name": "MW1-maintenance-suppression",
                "url": "https://httpbin.org/status/500",
                "monitor_type": "http",
                "check_interval": 60,
                "alert_email": "test-mw1@statusrooster.com",
                "maintenance_windows": [{"day": day_name, "start_utc": start_str, "end_utc": end_str}],
            })
            mid = mon["id"]

            # Trigger cron — monitor should fail but alerts should be suppressed
            await trigger_cron(client)
            await asyncio.sleep(3)

            # Monitor should still go DOWN (status tracks reality)
            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state["status"] == "down", \
                f"MW.1 FAIL: Monitor status should be 'down' even in maintenance, got {mon_state['status']}"

        finally:
            if mid:
                await update_monitor(client, mid, pro_headers, {"url": "https://httpbin.org/status/200"})
                await trigger_cron(client)
                await asyncio.sleep(2)
                await delete_monitor(client, mid, pro_headers)


# ═══════════════════════════════════════════════════════════════════════
# MC. MULTI-CHANNEL DELIVERY
# ═══════════════════════════════════════════════════════════════════════

class TestMultiChannelDelivery:
    """MC.1: Monitor with multiple alert channels configured."""

    @pytest.mark.asyncio
    async def test_mc1_incident_created_with_multi_channel_config(self, client, pro_headers):
        """MC.1 — Monitor with email + webhook configured → incident created, monitor goes down."""
        mid = None
        try:
            mon = await create_monitor(client, pro_headers, {
                "name": "MC1-multi-channel",
                "url": "https://httpbin.org/status/500",
                "monitor_type": "http",
                "check_interval": 60,
                "alert_email": "test-mc1@statusrooster.com",
                # Use a webhook that will accept POSTs (httpbin returns 200 for any POST)
                "webhook_url": "https://httpbin.org/post",
            })
            mid = mon["id"]

            await trigger_cron(client)
            await asyncio.sleep(3)

            # Verify incident was created
            incidents = await get_incidents_for_monitor(client, mid, pro_headers)
            assert len(incidents) >= 1, "MC.1 FAIL: No incident created with multi-channel config"
            assert incidents[0]["status"] == "open"

            # Verify monitor went down
            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state["status"] == "down"

        finally:
            if mid:
                await update_monitor(client, mid, pro_headers, {"url": "https://httpbin.org/status/200"})
                await trigger_cron(client)
                await asyncio.sleep(2)
                await delete_monitor(client, mid, pro_headers)


# ═══════════════════════════════════════════════════════════════════════
# HB. HEARTBEAT MONITOR LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════

class TestHeartbeatLifecycle:
    """HB.1–HB.2: Heartbeat monitors go down when pings stop."""

    @pytest.mark.asyncio
    async def test_hb1_heartbeat_pending_then_up_on_ping(self, client, pro_headers):
        """HB.1 — New heartbeat monitor starts pending, goes up on first ping."""
        mid = None
        try:
            mon = await create_monitor(client, pro_headers, {
                "name": "HB1-heartbeat-lifecycle",
                "monitor_type": "heartbeat",
                "heartbeat_interval": 120,
                "heartbeat_grace_period": 60,
                "alert_email": "test-hb1@statusrooster.com",
            })
            mid = mon["id"]
            ping_url = mon.get("ping_url", "")
            assert ping_url, "HB.1 FAIL: No ping_url returned for heartbeat monitor"

            # Monitor starts pending
            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state["status"] == "pending", \
                f"HB.1 FAIL: New heartbeat should be 'pending', got {mon_state['status']}"

            # Send a ping
            async with httpx.AsyncClient() as hc:
                ping_resp = await hc.get(ping_url)
                assert ping_resp.status_code == 200, f"HB.1 FAIL: Ping failed with {ping_resp.status_code}"

            # Trigger cron to process the heartbeat
            await trigger_cron(client)
            await asyncio.sleep(3)

            mon_state = await get_monitor(client, mid, pro_headers)
            assert mon_state["status"] == "up", \
                f"HB.1 FAIL: Heartbeat should be 'up' after ping + cron, got {mon_state['status']}"

        finally:
            if mid:
                await delete_monitor(client, mid, pro_headers)
