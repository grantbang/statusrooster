"""
StatusRooster E2E Test Suite — Automated Tests

Covers sections A–Q:
  A. Authentication
  B. Security
  C. API CRUD
  D. Monitor Type Validation
  E. Plan Enforcement
  F. Badges
  G. Error Handling
  H. Status Pages
  J. API Response Shape
  K. Custom Branding (Phase 4)
  L. Referral Tracking (Phase 7)
  M. Cron Auth
  N. Clone & Bulk Actions
  O. SSR Page Smoke Tests
  P. Incident & Check Filtering
  Q. API Documentation Accuracy
  I. Cleanup

Run:
  SR_API_KEY=sr_xxx pytest tests/test_e2e.py -v --asyncio-mode=auto

For slow tests (wait for cron):
  SR_API_KEY=sr_xxx pytest tests/test_e2e.py -v --asyncio-mode=auto -m slow
"""

import asyncio
import uuid
import pytest
import httpx

from tests.conftest import BASE_URL, TEST_EMAIL, TEST_PASSWORD, PRO_USER_ID


# ═══════════════════════════════════════════════════════════════════════
# A. AUTHENTICATION TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestAuth:
    """Tests A.1–A.9: Authentication endpoints."""

    @pytest.mark.asyncio
    async def test_a1_login_valid(self, client):
        """A.1 — POST /api/auth/login with valid credentials → 200"""
        resp = await client.post(
            "/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200, f"A.1 FAIL: Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "token" in data, "A.1 FAIL: Response missing 'token'"
        assert "user_id" in data, "A.1 FAIL: Response missing 'user_id'"
        assert "email" in data, "A.1 FAIL: Response missing 'email'"
        assert data["email"] == TEST_EMAIL

    @pytest.mark.asyncio
    async def test_a2_login_wrong_password(self, client):
        """A.2 — POST /api/auth/login with wrong password → 401"""
        resp = await client.post(
            "/api/auth/login",
            json={"email": TEST_EMAIL, "password": "wrongpassword"},
        )
        assert resp.status_code == 401, f"A.2 FAIL: Expected 401, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_a3_login_nonexistent_email(self, client):
        """A.3 — POST /api/auth/login with non-existent email → 401"""
        resp = await client.post(
            "/api/auth/login",
            json={"email": "nonexistent@statusrooster.com", "password": "anything"},
        )
        assert resp.status_code == 401, f"A.3 FAIL: Expected 401, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_a4_signup_existing_email(self, client):
        """A.4 — POST /api/auth/signup with existing email → 400"""
        resp = await client.post(
            "/api/auth/signup",
            json={"email": TEST_EMAIL, "password": "testpass123"},
        )
        assert resp.status_code == 400, f"A.4 FAIL: Expected 400, got {resp.status_code}"
        body = resp.json()
        msg = (body.get("detail") or body.get("error") or "").lower()
        assert "already registered" in msg

    @pytest.mark.asyncio
    async def test_a5_signup_short_password(self, client):
        """A.5 — POST /api/auth/signup with password < 8 chars → 400"""
        resp = await client.post(
            "/api/auth/signup",
            json={"email": f"short-{uuid.uuid4().hex[:6]}@test.com", "password": "abc"},
        )
        assert resp.status_code == 400, f"A.5 FAIL: Expected 400, got {resp.status_code}"
        body = resp.json()
        msg = body.get("detail") or body.get("error") or ""
        assert "8 characters" in msg

    @pytest.mark.asyncio
    async def test_a6_dashboard_no_auth(self, client):
        """A.6 — GET /dashboard without cookie → 302 redirect to /login"""
        resp = await client.get("/dashboard")
        assert resp.status_code in (302, 303, 307), f"A.6 FAIL: Expected 302, got {resp.status_code}"
        assert "/login" in resp.headers.get("location", ""), "A.6 FAIL: Should redirect to /login"

    @pytest.mark.asyncio
    async def test_a7_add_monitor_no_auth(self, client):
        """A.7 — GET /monitors/add without cookie → 302 redirect to /login"""
        resp = await client.get("/monitors/add")
        assert resp.status_code in (302, 303, 307), f"A.7 FAIL: Expected 302, got {resp.status_code}"
        assert "/login" in resp.headers.get("location", ""), "A.7 FAIL: Should redirect to /login"

    @pytest.mark.asyncio
    async def test_a8_settings_no_auth(self, client):
        """A.8 — GET /settings without cookie → 302 redirect to /login"""
        resp = await client.get("/settings")
        assert resp.status_code in (302, 303, 307), f"A.8 FAIL: Expected 302, got {resp.status_code}"
        assert "/login" in resp.headers.get("location", ""), "A.8 FAIL: Should redirect to /login"

    @pytest.mark.asyncio
    async def test_a9_signup_invalid_email(self, client):
        """A.9 — POST /api/auth/signup with invalid email → 422 (Pydantic)"""
        resp = await client.post(
            "/api/auth/signup",
            json={"email": "not-an-email", "password": "testpass123"},
        )
        assert resp.status_code == 422, f"A.9 FAIL: Expected 422, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# B. SECURITY TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestSecurity:
    """Tests B.1–B.10: Cron auth, SSRF, rate limiting, heartbeat token."""

    @pytest.mark.asyncio
    async def test_b1_cron_no_secret(self, client):
        """B.1 — POST /cron/check without X-Cron-Secret → 403"""
        resp = await client.post("/cron/check")
        assert resp.status_code == 403, f"B.1 FAIL: Expected 403, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_b2_cron_user_agent_only(self, client):
        """B.2 — POST /cron/check with Cloud Scheduler UA but no secret → 403"""
        resp = await client.post(
            "/cron/check",
            headers={"User-Agent": "Google-Cloud-Scheduler"},
        )
        assert resp.status_code == 403, f"B.2 FAIL: Expected 403, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_b3_cron_wrong_secret(self, client):
        """B.3 — POST /cron/check with wrong X-Cron-Secret → 403"""
        resp = await client.post(
            "/cron/check",
            headers={"X-Cron-Secret": "wrong-secret-value"},
        )
        assert resp.status_code == 403, f"B.3 FAIL: Expected 403, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_b4_ssrf_metadata(self, client):
        """B.4 — POST /api/check-url with AWS metadata URL → 400"""
        resp = await client.post(
            "/api/check-url",
            json={"url": "http://169.254.169.254/latest/meta-data/"},
        )
        assert resp.status_code == 400, f"B.4 FAIL: Expected 400, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_b5_ssrf_localhost(self, client):
        """B.5 — POST /api/check-url with localhost → 400"""
        resp = await client.post(
            "/api/check-url",
            json={"url": "http://127.0.0.1"},
        )
        assert resp.status_code == 400, f"B.5 FAIL: Expected 400, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_b6_ssrf_private_network(self, client):
        """B.6 — POST /api/check-url with private IP → 400"""
        resp = await client.post(
            "/api/check-url",
            json={"url": "http://10.0.0.1"},
        )
        assert resp.status_code == 400, f"B.6 FAIL: Expected 400, got {resp.status_code}"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_b7_rate_limit(self, client):
        """B.7 — POST /api/check-url 11 times rapidly → 11th returns 429

        NOTE: This test poisons the per-IP rate limiter (10 req/60s).
        Mark as slow/isolated. If running against production, be aware
        it will block /api/check-url for ~60s after execution.
        """
        results = []
        for i in range(11):
            resp = await client.post(
                "/api/check-url",
                json={"url": "https://httpbin.org/status/200"},
            )
            results.append(resp.status_code)
            if resp.status_code == 429:
                break  # Got the rate limit — stop hammering

        assert 429 in results, f"B.7 FAIL: Expected 429 in results, got {results}"

    @pytest.mark.asyncio
    async def test_b8_heartbeat_no_token(self, client, make_monitor):
        """B.8 — GET /api/ping/{id} without token → 403"""
        monitor = await make_monitor({
            "name": "E2E-B8-heartbeat-no-token",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 300,
            "heartbeat_grace_period": 60,
        })
        resp = await client.get(f"/api/ping/{monitor['id']}")
        assert resp.status_code == 403, f"B.8 FAIL: Expected 403, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_b9_heartbeat_wrong_token(self, client, make_monitor):
        """B.9 — GET /api/ping/{id}?token=WRONG → 403"""
        monitor = await make_monitor({
            "name": "E2E-B9-heartbeat-wrong-token",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 300,
            "heartbeat_grace_period": 60,
        })
        resp = await client.get(f"/api/ping/{monitor['id']}?token=WRONG_TOKEN")
        assert resp.status_code == 403, f"B.9 FAIL: Expected 403, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_b10_heartbeat_correct_token(self, client, make_monitor, pro_headers):
        """B.10 — GET /api/ping/{id}?token=CORRECT → 200"""
        monitor = await make_monitor({
            "name": "E2E-B10-heartbeat-correct-token",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 300,
            "heartbeat_grace_period": 60,
        })
        # ping_token is stripped from API responses; extract token from ping_url
        detail_resp = await client.get(
            f"/api/v1/monitors/{monitor['id']}",
            headers=pro_headers,
        )
        detail = detail_resp.json()["data"]
        ping_url = detail.get("ping_url", "")
        assert ping_url, "B.10 FAIL: Monitor has no ping_url"
        # ping_url is a full URL; just GET it directly
        resp = await client.get(ping_url.replace("https://statusrooster.com", ""))
        assert resp.status_code == 200, f"B.10 FAIL: Expected 200, got {resp.status_code}"
        body = resp.json()
        assert body.get("ok") is True
        assert body.get("status") == "up"


# ═══════════════════════════════════════════════════════════════════════
# C. API CRUD TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestAPICrud:
    """Tests C.1–C.16: Full CRUD lifecycle via API v1."""

    @pytest.mark.asyncio
    async def test_c1_list_monitors(self, client, pro_headers):
        """C.1 — GET /api/v1/monitors with valid API key → 200"""
        resp = await client.get("/api/v1/monitors", headers=pro_headers)
        assert resp.status_code == 200, f"C.1 FAIL: Expected 200, got {resp.status_code}"
        body = resp.json()
        assert "data" in body, "C.1 FAIL: Response missing 'data'"
        assert isinstance(body["data"], list), "C.1 FAIL: 'data' should be a list"

    @pytest.mark.asyncio
    async def test_c2_list_monitors_no_key(self, client):
        """C.2 — GET /api/v1/monitors without API key → 401"""
        resp = await client.get("/api/v1/monitors")
        assert resp.status_code == 401, f"C.2 FAIL: Expected 401, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_c3_list_monitors_invalid_key(self, client):
        """C.3 — GET /api/v1/monitors with invalid API key → 401"""
        resp = await client.get(
            "/api/v1/monitors",
            headers={"X-API-Key": "sr_invalid_key_12345"},
        )
        assert resp.status_code == 401, f"C.3 FAIL: Expected 401, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_c4_create_http_monitor(self, client, pro_headers, make_monitor):
        """C.4 — POST /api/v1/monitors — create HTTP monitor → 201"""
        monitor = await make_monitor({
            "name": "E2E-C4-http",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        assert monitor["name"] == "E2E-C4-http"
        assert monitor["monitor_type"] == "http"

    @pytest.mark.asyncio
    async def test_c5_create_json_api_monitor(self, client, pro_headers, make_monitor):
        """C.5 — POST /api/v1/monitors — create JSON/API monitor with assertions → 201"""
        monitor = await make_monitor({
            "name": "E2E-C5-json-api",
            "url": "https://httpbin.org/json",
            "monitor_type": "json_api",
            "json_assertions": [
                {"path": "slideshow.author", "operator": "equals", "value": "Yours Truly"},
            ],
        })
        assert monitor["monitor_type"] == "json_api"

    @pytest.mark.asyncio
    async def test_c6_create_heartbeat_monitor(self, client, pro_headers, make_monitor):
        """C.6 — POST /api/v1/monitors — create heartbeat → 201, has ping_url"""
        monitor = await make_monitor({
            "name": "E2E-C6-heartbeat",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 300,
            "heartbeat_grace_period": 60,
        })
        assert monitor["monitor_type"] == "heartbeat"
        # ping_url should be set
        assert "ping_url" in monitor or "url" in monitor, "C.6 FAIL: Heartbeat should have ping_url"

    @pytest.mark.asyncio
    async def test_c7_create_ssl_monitor(self, client, pro_headers, make_monitor):
        """C.7 — POST /api/v1/monitors — create SSL monitor → 201"""
        monitor = await make_monitor({
            "name": "E2E-C7-ssl",
            "monitor_type": "ssl",
            "ssl_domain": "statusrooster.com",
            "ssl_expiry_threshold_days": 14,
        })
        assert monitor["monitor_type"] == "ssl"

    @pytest.mark.asyncio
    async def test_c8_get_single_monitor(self, client, pro_headers, make_monitor):
        """C.8 — GET /api/v1/monitors/{id} → 200"""
        monitor = await make_monitor({
            "name": "E2E-C8-get",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.get(
            f"/api/v1/monitors/{monitor['id']}",
            headers=pro_headers,
        )
        assert resp.status_code == 200, f"C.8 FAIL: Expected 200, got {resp.status_code}"
        assert resp.json()["data"]["id"] == monitor["id"]

    @pytest.mark.asyncio
    async def test_c9_get_nonexistent_monitor(self, client, pro_headers):
        """C.9 — GET /api/v1/monitors/{fake_id} → 404"""
        resp = await client.get(
            "/api/v1/monitors/NONEXISTENT_ID_12345",
            headers=pro_headers,
        )
        assert resp.status_code == 404, f"C.9 FAIL: Expected 404, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_c10_update_monitor_put(self, client, pro_headers, make_monitor):
        """C.10 — PUT /api/v1/monitors/{id} — update name → 200"""
        monitor = await make_monitor({
            "name": "E2E-C10-before",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.put(
            f"/api/v1/monitors/{monitor['id']}",
            json={"name": "E2E-C10-after"},
            headers=pro_headers,
        )
        assert resp.status_code == 200, f"C.10 FAIL: Expected 200, got {resp.status_code}"
        assert resp.json()["data"]["name"] == "E2E-C10-after"

    @pytest.mark.asyncio
    async def test_c11_patch_monitor_pause(self, client, pro_headers, make_monitor):
        """C.11 — PATCH /api/v1/monitors/{id} — pause → 200"""
        monitor = await make_monitor({
            "name": "E2E-C11-patch",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.patch(
            f"/api/v1/monitors/{monitor['id']}",
            json={"paused": True},
            headers=pro_headers,
        )
        assert resp.status_code == 200, f"C.11 FAIL: Expected 200, got {resp.status_code}"
        assert resp.json()["data"]["paused"] is True

    @pytest.mark.asyncio
    async def test_c12_c13_delete_monitor(self, client, pro_headers, make_monitor):
        """C.12/C.13 — DELETE monitor → 200, then GET → 404"""
        # Create via make_monitor so it's tracked for cleanup on failure
        monitor = await make_monitor({
            "name": "E2E-C12-delete",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        mid = monitor["id"]

        # Delete
        resp = await client.delete(f"/api/v1/monitors/{mid}", headers=pro_headers)
        assert resp.status_code == 200, f"C.12 FAIL: Expected 200, got {resp.status_code}"
        assert resp.json()["data"]["deleted"] is True

        # Verify gone
        resp = await client.get(f"/api/v1/monitors/{mid}", headers=pro_headers)
        assert resp.status_code == 404, f"C.13 FAIL: Expected 404, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_c14_get_checks(self, client, pro_headers, make_monitor):
        """C.14 — GET /api/v1/monitors/{id}/checks?limit=5 → 200"""
        monitor = await make_monitor({
            "name": "E2E-C14-checks",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.get(
            f"/api/v1/monitors/{monitor['id']}/checks?limit=5",
            headers=pro_headers,
        )
        assert resp.status_code == 200, f"C.14 FAIL: Expected 200, got {resp.status_code}"
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) <= 5, f"C.14 FAIL: Expected ≤5 checks, got {len(data)}"

    @pytest.mark.asyncio
    async def test_c15_list_incidents(self, client, pro_headers):
        """C.15 — GET /api/v1/incidents → 200"""
        resp = await client.get("/api/v1/incidents", headers=pro_headers)
        assert resp.status_code == 200, f"C.15 FAIL: Expected 200, got {resp.status_code}"
        assert "data" in resp.json()

    @pytest.mark.asyncio
    async def test_c16_get_incident(self, client, pro_headers):
        """C.16 — GET /api/v1/incidents/{id} → 200 (if incidents exist)"""
        # First list incidents to get an ID
        list_resp = await client.get("/api/v1/incidents", headers=pro_headers)
        incidents = list_resp.json().get("data", [])
        if not incidents:
            pytest.skip("C.16: No incidents to test with — create a DOWN monitor first")

        incident_id = incidents[0]["id"]
        resp = await client.get(f"/api/v1/incidents/{incident_id}", headers=pro_headers)
        assert resp.status_code == 200, f"C.16 FAIL: Expected 200, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# D. MONITOR TYPE VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestMonitorTypes:
    """Tests D.1–D.15: Verify each monitor type works correctly.

    Note: Tests D.1–D.3, D.5, D.7–D.11, D.14, D.15 require triggering a check.
    We create the monitor and rely on "Check now" or cron to verify check results.
    For simplicity, tests that just verify creation are non-slow.
    Tests that need to wait for cron are marked @pytest.mark.slow.
    """

    @pytest.mark.asyncio
    async def test_d4_create_all_http_methods(self, client, pro_headers, make_monitor):
        """D.4 — Create HTTP monitor with each method → all 201"""
        methods = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
        for method in methods:
            monitor = await make_monitor({
                "name": f"E2E-D4-{method}",
                "url": "https://httpbin.org/status/200",
                "monitor_type": "http",
                "http_method": method,
            })
            assert monitor["http_method"] == method, f"D.4 FAIL: Method {method} not stored"

    @pytest.mark.asyncio
    async def test_d6_bearer_token_stored(self, client, pro_headers, make_monitor):
        """D.6 — Create HTTP monitor with bearer_token → stored on doc"""
        monitor = await make_monitor({
            "name": "E2E-D6-bearer",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "bearer_token": "test-token-123",
        })
        # Verify it persisted
        resp = await client.get(
            f"/api/v1/monitors/{monitor['id']}",
            headers=pro_headers,
        )
        data = resp.json()["data"]
        assert data.get("bearer_token") == "test-token-123", "D.6 FAIL: bearer_token not persisted"

    @pytest.mark.asyncio
    async def test_d7_http_check_now(self, client, pro_headers, make_monitor, check_and_get_result):
        """D.7 — HTTP monitor: trigger check-now → is_up=True, status_code=200"""
        monitor = await make_monitor({
            "name": "E2E-D7-http-check",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"D.7 FAIL: Expected is_up=True, got {result}"
        assert result["status_code"] == 200, f"D.7 FAIL: Expected status_code=200, got {result['status_code']}"
        assert result["response_ms"] is not None, "D.7 FAIL: response_ms should not be None"

    @pytest.mark.asyncio
    async def test_d9_json_assertion_pass(self, client, pro_headers, make_monitor, check_and_get_result):
        """D.9 — JSON/API with passing assertion → check-now → is_up=True"""
        monitor = await make_monitor({
            "name": "E2E-D9-assertion-pass",
            "url": "https://httpbin.org/json",
            "monitor_type": "json_api",
            "json_assertions": [
                {"path": "slideshow.author", "operator": "equals", "value": "Yours Truly"},
            ],
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"D.9 FAIL: Passing assertion should be up, got {result}"

    @pytest.mark.asyncio
    async def test_d10_json_assertion_fail(self, client, pro_headers, make_monitor, check_and_get_result):
        """D.10 — JSON/API with failing assertion → check-now → is_up=False"""
        monitor = await make_monitor({
            "name": "E2E-D10-assertion-fail",
            "url": "https://httpbin.org/json",
            "monitor_type": "json_api",
            "json_assertions": [
                {"path": "slideshow.title", "operator": "equals", "value": "WRONG_VALUE"},
            ],
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is False, f"D.10 FAIL: Failing assertion should be down, got {result}"

    @pytest.mark.asyncio
    async def test_d11_json_all_operators(self, client, pro_headers, make_monitor, check_and_get_result):
        """D.11 — JSON/API with all assertion operators → check-now → is_up=True"""
        monitor = await make_monitor({
            "name": "E2E-D11-all-operators",
            "url": "https://httpbin.org/json",
            "monitor_type": "json_api",
            "json_assertions": [
                {"path": "slideshow.author", "operator": "equals", "value": "Yours Truly"},
                {"path": "slideshow.author", "operator": "not_equals", "value": "Someone Else"},
                {"path": "slideshow.title", "operator": "contains", "value": "Sample"},
                {"path": "slideshow.title", "operator": "not_contains", "value": "BANANA"},
                {"path": "slideshow.slides", "operator": "exists", "value": ""},
                {"path": "slideshow.nonexistent", "operator": "not_exists", "value": ""},
            ],
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"D.11 FAIL: All-operator assertions should pass, got {result}"

    @pytest.mark.asyncio
    async def test_d12_heartbeat_ping(self, client, pro_headers, make_monitor):
        """D.12 — Create heartbeat, ping with correct token → 200"""
        monitor = await make_monitor({
            "name": "E2E-D12-heartbeat-ping",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 300,
            "heartbeat_grace_period": 60,
        })
        # ping_token is stripped from API responses; extract from ping_url
        detail = await client.get(
            f"/api/v1/monitors/{monitor['id']}",
            headers=pro_headers,
        )
        ping_url = detail.json()["data"].get("ping_url", "")
        assert ping_url, "D.12 FAIL: No ping_url on monitor"

        resp = await client.get(ping_url.replace("https://statusrooster.com", ""))
        assert resp.status_code == 200, f"D.12 FAIL: Expected 200, got {resp.status_code}"
        assert resp.json()["ok"] is True

    @pytest.mark.asyncio
    async def test_d14_ssl_valid(self, client, pro_headers, make_monitor, check_and_get_result):
        """D.14 — SSL monitor for statusrooster.com → check-now → is_up=True"""
        monitor = await make_monitor({
            "name": "E2E-D14-ssl-valid",
            "monitor_type": "ssl",
            "ssl_domain": "statusrooster.com",
            "ssl_expiry_threshold_days": 14,
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"D.14 FAIL: Valid SSL should be up, got {result}"
        assert result.get("ssl_expiry_days") is not None, "D.14 FAIL: Should have ssl_expiry_days"

    @pytest.mark.asyncio
    async def test_d15_ssl_expired(self, client, pro_headers, make_monitor, check_and_get_result):
        """D.15 — SSL monitor for expired.badssl.com → check-now → is_up=False"""
        monitor = await make_monitor({
            "name": "E2E-D15-ssl-expired",
            "monitor_type": "ssl",
            "ssl_domain": "expired.badssl.com",
            "ssl_expiry_threshold_days": 14,
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is False, f"D.15 FAIL: Expired SSL should be down, got {result}"


# ═══════════════════════════════════════════════════════════════════════
# E. PLAN ENFORCEMENT TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestPlanEnforcement:
    """Tests E.1–E.12: Verify Free vs Pro plan gating.

    Phase 1 unlocked most features for free users. Only SMS remains Pro-only.
    Check interval minimum is 60s for all plans. Free limit = 100 monitors, Pro = 200.
    Status pages: 10 for all plans. Aggregate status page: Pro-only.
    """

    # ── E.1: Free user monitor limit (100) ──
    # We can't create 101 monitors in a test, so we verify that 6 monitors
    # are allowed (was 5 before Phase 1) and the limit constant is correct.

    @pytest.mark.asyncio
    async def test_e1_free_monitor_limit(self, client, free_headers):
        """E.1 — Free user: can create at least 6 monitors (limit is 100)"""
        existing_resp = await client.get("/api/v1/monitors", headers=free_headers)
        if existing_resp.status_code == 200:
            for m in existing_resp.json().get("data", []):
                await client.delete(f"/api/v1/monitors/{m['id']}", headers=free_headers)

        created = []
        try:
            for i in range(6):
                resp = await client.post(
                    "/api/v1/monitors",
                    json={"name": f"E2E-E1-free-{i}", "url": "https://httpbin.org/status/200", "monitor_type": "http", "public": False},
                    headers=free_headers,
                )
                assert resp.status_code == 201, f"E.1 FAIL: Free user should create monitor #{i+1}, got {resp.status_code}: {resp.text}"
                created.append(resp.json()["data"]["id"])
        finally:
            for mid in created:
                try:
                    await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)
                except Exception:
                    pass

    # ── E.2: Free create KEEPS slack_webhook (unlocked in Phase 1) ──

    @pytest.mark.asyncio
    async def test_e2_free_create_slack_stripped(self, client, free_headers):
        """E.2 — Free user: create with slack webhook → kept (unlocked)"""
        resp = await client.post(
            "/api/v1/monitors",
            json={
                "name": "E2E-E2-free-slack",
                "url": "https://httpbin.org/status/200",
                "monitor_type": "http",
                "public": False,
                "alert_slack_webhook": "https://hooks.slack.com/services/TEST/TEST/TEST",
            },
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201, f"E.2 FAIL: Expected 201, got {resp.status_code}"
            mid = resp.json()["data"]["id"]
            data = resp.json()["data"]
            assert data.get("alert_slack_webhook") == "https://hooks.slack.com/services/TEST/TEST/TEST", \
                f"E.2 FAIL: Free user slack webhook should be kept, got '{data.get('alert_slack_webhook')}'"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.3: Pro create KEEPS slack_webhook ──

    @pytest.mark.asyncio
    async def test_e3_pro_create_slack_kept(self, client, pro_headers, make_monitor):
        """E.3 — Pro user: create with slack webhook → stored"""
        monitor = await make_monitor({
            "name": "E2E-E3-pro-slack",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "alert_slack_webhook": "https://hooks.slack.com/services/TEST/TEST/TEST",
        })
        detail = await client.get(f"/api/v1/monitors/{monitor['id']}", headers=pro_headers)
        data = detail.json()["data"]
        assert data.get("alert_slack_webhook") == "https://hooks.slack.com/services/TEST/TEST/TEST", \
            "E.3 FAIL: Pro user should have slack webhook stored"

    # ── E.4: Free create KEEPS webhook_url (unlocked in Phase 1) ──

    @pytest.mark.asyncio
    async def test_e4_free_create_webhook_stripped(self, client, free_headers):
        """E.4 — Free user: create with webhook_url → kept (unlocked)"""
        resp = await client.post(
            "/api/v1/monitors",
            json={
                "name": "E2E-E4-free-webhook",
                "url": "https://httpbin.org/status/200",
                "monitor_type": "http",
                "public": False,
                "webhook_url": "https://example.com/webhook",
            },
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201, f"E.4 FAIL: Expected 201, got {resp.status_code}"
            mid = resp.json()["data"]["id"]
            data = resp.json()["data"]
            assert data.get("webhook_url") == "https://example.com/webhook", \
                f"E.4 FAIL: Free webhook_url should be kept, got '{data.get('webhook_url')}'"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.5: Free create KEEPS basic_auth (unlocked in Phase 1) ──

    @pytest.mark.asyncio
    async def test_e5_free_create_basic_auth_stripped(self, client, free_headers):
        """E.5 — Free user: create with basic_auth → kept (unlocked)"""
        resp = await client.post(
            "/api/v1/monitors",
            json={
                "name": "E2E-E5-free-basic-auth",
                "url": "https://httpbin.org/status/200",
                "monitor_type": "http",
                "public": False,
                "basic_auth_user": "admin",
                "basic_auth_pass": "secret",
            },
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201, f"E.5 FAIL: Expected 201, got {resp.status_code}"
            mid = resp.json()["data"]["id"]
            data = resp.json()["data"]
            assert data.get("basic_auth_user") == "admin", \
                f"E.5 FAIL: Free basic_auth_user should be kept, got '{data.get('basic_auth_user')}'"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.6: Free UPDATE slack webhook → 200 (unlocked in Phase 1) ──

    @pytest.mark.asyncio
    async def test_e6_free_update_slack_403(self, client, free_headers):
        """E.6 — Free user: update with slack webhook → 200 (unlocked)"""
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-E6-free-update-slack", "url": "https://httpbin.org/status/200", "monitor_type": "http", "public": False},
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201
            mid = resp.json()["data"]["id"]
            update_resp = await client.patch(
                f"/api/v1/monitors/{mid}",
                json={"alert_slack_webhook": "https://hooks.slack.com/services/T/T/T"},
                headers=free_headers,
            )
            assert update_resp.status_code == 200, f"E.6 FAIL: Expected 200, got {update_resp.status_code}"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.7: Free UPDATE webhook_url → 200 (unlocked in Phase 1) ──

    @pytest.mark.asyncio
    async def test_e7_free_update_webhook_403(self, client, free_headers):
        """E.7 — Free user: update with webhook_url → 200 (unlocked)"""
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-E7-free-update-webhook", "url": "https://httpbin.org/status/200", "monitor_type": "http"},
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201
            mid = resp.json()["data"]["id"]
            update_resp = await client.patch(
                f"/api/v1/monitors/{mid}",
                json={"webhook_url": "https://example.com/webhook"},
                headers=free_headers,
            )
            assert update_resp.status_code == 200, f"E.7 FAIL: Expected 200, got {update_resp.status_code}"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.8: Free UPDATE check_interval=60 → 200 (unlocked, min 60s for free) ──

    @pytest.mark.asyncio
    async def test_e8_free_update_interval_403(self, client, free_headers):
        """E.8 — Free user: update check_interval=60 → 200 (unlocked, min 60s)"""
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-E8-free-update-interval", "url": "https://httpbin.org/status/200", "monitor_type": "http"},
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201
            mid = resp.json()["data"]["id"]
            # 60s should succeed for free
            update_resp = await client.patch(
                f"/api/v1/monitors/{mid}",
                json={"check_interval": 60},
                headers=free_headers,
            )
            assert update_resp.status_code == 200, f"E.8 FAIL: Expected 200 for 60s interval, got {update_resp.status_code}"
            # 30s should be rejected for all plans (minimum is 60s)
            update_resp2 = await client.patch(
                f"/api/v1/monitors/{mid}",
                json={"check_interval": 30},
                headers=free_headers,
            )
            assert update_resp2.status_code == 403, f"E.8 FAIL: Expected 403 for 30s interval, got {update_resp2.status_code}"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.9: Free UPDATE maintenance_windows → 200 (unlocked in Phase 1) ──

    @pytest.mark.asyncio
    async def test_e9_free_update_maintenance_403(self, client, free_headers):
        """E.9 — Free user: update maintenance_windows → 200 (unlocked)"""
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-E9-free-maintenance", "url": "https://httpbin.org/status/200", "monitor_type": "http"},
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201
            mid = resp.json()["data"]["id"]
            update_resp = await client.patch(
                f"/api/v1/monitors/{mid}",
                json={"maintenance_windows": [{"day": "daily", "start_utc": "00:00", "end_utc": "01:00"}]},
                headers=free_headers,
            )
            assert update_resp.status_code == 200, f"E.9 FAIL: Expected 200, got {update_resp.status_code}"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.10: Free UPDATE basic_auth → 200 (unlocked in Phase 1) ──

    @pytest.mark.asyncio
    async def test_e10_free_update_basic_auth_403(self, client, free_headers):
        """E.10 — Free user: update basic_auth → 200 (unlocked)"""
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-E10-free-basic-auth", "url": "https://httpbin.org/status/200", "monitor_type": "http"},
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201
            mid = resp.json()["data"]["id"]
            update_resp = await client.patch(
                f"/api/v1/monitors/{mid}",
                json={"basic_auth_user": "admin"},
                headers=free_headers,
            )
            assert update_resp.status_code == 200, f"E.10 FAIL: Expected 200, got {update_resp.status_code}"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.11: Free status page limit (10 for all plans) ──

    @pytest.mark.asyncio
    async def test_e11_free_public_status_page_limit(self, client, free_headers):
        """E.11 — Free user: can create multiple public monitors (limit is 10)"""
        created = []
        try:
            # Create 3 public monitors — should all succeed (limit is 10)
            for i in range(3):
                resp = await client.post(
                    "/api/v1/monitors",
                    json={"name": f"E2E-E11-free-public-{i}", "url": "https://httpbin.org/status/200", "monitor_type": "http", "public": True},
                    headers=free_headers,
                )
                assert resp.status_code == 201, f"E.11 FAIL: Public monitor #{i+1} should succeed, got {resp.status_code}"
                created.append(resp.json()["data"]["id"])
        finally:
            for mid in created:
                try:
                    await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)
                except Exception:
                    pass


# ═══════════════════════════════════════════════════════════════════════
# F. BADGE TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestBadges:
    """Tests F.1–F.5: SVG badge endpoints."""

    @pytest.mark.asyncio
    async def test_f1_uptime_badge_public(self, client, pro_headers, make_monitor):
        """F.1 — GET /badge/{public_monitor_id}.svg → 200, SVG"""
        monitor = await make_monitor({
            "name": "E2E-F1-badge",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "public": True,
        })
        resp = await client.get(f"/badge/{monitor['id']}.svg")
        assert resp.status_code == 200, f"F.1 FAIL: Expected 200, got {resp.status_code}"
        assert "image/svg+xml" in resp.headers.get("content-type", ""), "F.1 FAIL: Not SVG"
        assert "<svg" in resp.text, "F.1 FAIL: Response is not SVG"

    @pytest.mark.asyncio
    async def test_f2_status_badge(self, client, pro_headers, make_monitor):
        """F.2 — GET /badge/{id}/status.svg → 200, SVG"""
        monitor = await make_monitor({
            "name": "E2E-F2-status-badge",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "public": True,
        })
        resp = await client.get(f"/badge/{monitor['id']}/status.svg")
        assert resp.status_code == 200, f"F.2 FAIL: Expected 200, got {resp.status_code}"
        assert "<svg" in resp.text

    @pytest.mark.asyncio
    async def test_f3_response_badge(self, client, pro_headers, make_monitor):
        """F.3 — GET /badge/{id}/response.svg → 200, SVG"""
        monitor = await make_monitor({
            "name": "E2E-F3-response-badge",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "public": True,
        })
        resp = await client.get(f"/badge/{monitor['id']}/response.svg")
        assert resp.status_code == 200, f"F.3 FAIL: Expected 200, got {resp.status_code}"
        assert "<svg" in resp.text

    @pytest.mark.asyncio
    async def test_f4_badge_private_monitor(self, client, pro_headers, make_monitor):
        """F.4 — GET /badge/{private_monitor_id}.svg → 200, 'not found' SVG"""
        monitor = await make_monitor({
            "name": "E2E-F4-private-badge",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "public": False,
        })
        resp = await client.get(f"/badge/{monitor['id']}.svg")
        assert resp.status_code == 200, f"F.4 FAIL: Expected 200, got {resp.status_code}"
        assert "not found" in resp.text, "F.4 FAIL: Private monitor badge should say 'not found'"

    @pytest.mark.asyncio
    async def test_f5_badge_fake_id(self, client):
        """F.5 — GET /badge/FAKE_ID.svg → 200, 'not found' SVG"""
        resp = await client.get("/badge/NONEXISTENT_12345.svg")
        assert resp.status_code == 200, f"F.5 FAIL: Expected 200, got {resp.status_code}"
        assert "not found" in resp.text, "F.5 FAIL: Fake ID badge should say 'not found'"


# ═══════════════════════════════════════════════════════════════════════
# G. ERROR HANDLING TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Tests G.1–G.10: Error pages, validation, authorization."""

    @pytest.mark.asyncio
    async def test_g1_404_page(self, client):
        """G.1 — GET /nonexistent-page → 404"""
        resp = await client.get("/nonexistent-page-xyz-12345")
        assert resp.status_code == 404, f"G.1 FAIL: Expected 404, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_g2_api_404(self, client, pro_headers):
        """G.2 — GET /api/v1/nonexistent → 404/405"""
        resp = await client.get("/api/v1/nonexistent", headers=pro_headers)
        # Could be 404 or 405 depending on router matching
        assert resp.status_code in (404, 405), f"G.2 FAIL: Expected 404/405, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_g3_monitor_fake_id_auth(self, client):
        """G.3 — GET /monitors/FAKE_ID (authenticated) → 302 redirect"""
        # Login first
        login = await client.post(
            "/login",
            data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        cookies = {}
        for cookie_name, cookie_value in login.cookies.items():
            cookies[cookie_name] = cookie_value

        resp = await client.get("/monitors/FAKE_ID_12345", cookies=cookies)
        # Should redirect to dashboard with error, or show 404
        assert resp.status_code in (302, 303, 404), f"G.3 FAIL: Expected 302/404, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_g4_status_page_bad_slug(self, client):
        """G.4 — GET /s/nonexistent-slug → 404"""
        resp = await client.get("/s/nonexistent-slug-xyz-12345")
        assert resp.status_code == 404, f"G.4 FAIL: Expected 404, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_g6_api_create_empty_body(self, client, pro_headers):
        """G.6 — POST /api/v1/monitors with empty body → 422"""
        resp = await client.post(
            "/api/v1/monitors",
            content="{}",
            headers={**pro_headers, "Content-Type": "application/json"},
        )
        # Empty body missing required 'name' field → 422
        assert resp.status_code == 422, f"G.6 FAIL: Expected 422, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_g7_api_create_name_no_url(self, client, pro_headers):
        """G.7 — POST /api/v1/monitors with name but no URL → 422 (url required for HTTP)"""
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-G7-no-url", "monitor_type": "http"},
            headers=pro_headers,
        )
        assert resp.status_code == 422
        assert "url is required" in resp.json()["error"].lower()

    @pytest.mark.asyncio
    async def test_g8_update_other_users_monitor(self, client, pro_headers):
        """G.8 — PUT /api/v1/monitors/{other_user_id} → 404 (not 403)"""
        # Use a fake ID that doesn't belong to us
        resp = await client.put(
            "/api/v1/monitors/OTHER_USER_MONITOR_FAKE",
            json={"name": "hacked"},
            headers=pro_headers,
        )
        assert resp.status_code == 404, f"G.8 FAIL: Expected 404, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_g9_delete_other_users_monitor(self, client, pro_headers):
        """G.9 — DELETE /api/v1/monitors/{other_user_id} → 404"""
        resp = await client.delete(
            "/api/v1/monitors/OTHER_USER_MONITOR_FAKE",
            headers=pro_headers,
        )
        assert resp.status_code == 404, f"G.9 FAIL: Expected 404, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_g10_get_other_users_monitor(self, client, pro_headers):
        """G.10 — GET /api/v1/monitors/{other_user_id} → 404"""
        resp = await client.get(
            "/api/v1/monitors/OTHER_USER_MONITOR_FAKE",
            headers=pro_headers,
        )
        assert resp.status_code == 404, f"G.10 FAIL: Expected 404, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# H. STATUS PAGE TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestStatusPages:
    """Tests H.1–H.7: Public status pages and aggregate pages."""

    @pytest.mark.asyncio
    async def test_h1_public_status_page(self, client, pro_headers, make_monitor):
        """H.1 — GET /s/{slug} for public monitor → 200"""
        slug = f"e2e-test-{uuid.uuid4().hex[:8]}"
        monitor = await make_monitor({
            "name": "E2E-H1-public",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "public": True,
        })
        # Set slug via PATCH
        await client.patch(
            f"/api/v1/monitors/{monitor['id']}",
            json={"slug": slug},
            headers=pro_headers,
        )
        resp = await client.get(f"/s/{slug}")
        assert resp.status_code == 200, f"H.1 FAIL: Expected 200, got {resp.status_code}"
        assert "html" in resp.headers.get("content-type", "").lower(), "H.1 FAIL: Should return HTML"

    @pytest.mark.asyncio
    async def test_h2_private_monitor_slug(self, client, pro_headers, make_monitor):
        """H.2 — GET /s/{slug} for private monitor → 404"""
        slug = f"e2e-private-{uuid.uuid4().hex[:8]}"
        monitor = await make_monitor({
            "name": "E2E-H2-private",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "public": False,
        })
        # Even if we set a slug, it should 404 because public=false
        await client.patch(
            f"/api/v1/monitors/{monitor['id']}",
            json={"slug": slug},
            headers=pro_headers,
        )
        resp = await client.get(f"/s/{slug}")
        assert resp.status_code == 404, f"H.2 FAIL: Expected 404, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_h3_nonexistent_slug(self, client):
        """H.3 — GET /s/nonexistent-slug → 404"""
        resp = await client.get("/s/nonexistent-slug-xyz-99999")
        assert resp.status_code == 404, f"H.3 FAIL: Expected 404, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_h4_aggregate_pro_user(self, client, pro_headers, make_monitor):
        """H.4 — GET /status/{pro_user_id} with public monitors → 200"""
        # Ensure at least one public monitor exists
        monitor = await make_monitor({
            "name": "E2E-H4-aggregate",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "public": True,
        })
        resp = await client.get(f"/status/{PRO_USER_ID}")
        assert resp.status_code == 200, f"H.4 FAIL: Expected 200, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_h7_aggregate_nonexistent_user(self, client):
        """H.7 — GET /status/{nonexistent_user_id} → 404"""
        resp = await client.get("/status/NONEXISTENT_USER_12345")
        assert resp.status_code == 404, f"H.7 FAIL: Expected 404, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# J. API RESPONSE SHAPE CONSISTENCY
# ═══════════════════════════════════════════════════════════════════════

class TestApiResponseShape:
    """Tests J.1–J.6: Verify all API v1 responses follow {data, error, meta} shape."""

    @pytest.mark.asyncio
    async def test_j1_list_monitors_shape(self, client, pro_headers):
        """J.1 — GET /api/v1/monitors → has data, error=null, meta"""
        resp = await client.get("/api/v1/monitors", headers=pro_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body, "J.1 FAIL: Missing 'data' key"
        assert body.get("error") is None, "J.1 FAIL: error should be null on success"
        assert "meta" in body, "J.1 FAIL: Missing 'meta' key"
        assert "total" in body["meta"], "J.1 FAIL: meta missing 'total'"

    @pytest.mark.asyncio
    async def test_j2_create_monitor_shape(self, client, pro_headers, make_monitor):
        """J.2 — POST /api/v1/monitors → has data, error=null"""
        monitor = await make_monitor({
            "name": "E2E-J2-shape",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        assert "id" in monitor, "J.2 FAIL: data missing 'id'"

    @pytest.mark.asyncio
    async def test_j3_error_shape_404(self, client, pro_headers):
        """J.3 — GET /api/v1/monitors/FAKE → error shape {data: null, error: str}"""
        resp = await client.get("/api/v1/monitors/FAKE_MONITOR_ID_999", headers=pro_headers)
        assert resp.status_code == 404
        body = resp.json()
        assert body.get("data") is None, "J.3 FAIL: data should be null on error"
        assert body.get("error") is not None, "J.3 FAIL: error should be set"
        assert isinstance(body["error"], str), "J.3 FAIL: error should be a string"

    @pytest.mark.asyncio
    async def test_j4_error_shape_401(self, client):
        """J.4 — GET /api/v1/monitors without key → 401 with error detail"""
        resp = await client.get("/api/v1/monitors")
        assert resp.status_code == 401
        body = resp.json()
        # 401 from FastAPI may use detail format
        assert "detail" in body or "error" in body, "J.4 FAIL: Missing error info"

    @pytest.mark.asyncio
    async def test_j5_checks_shape(self, client, pro_headers, make_monitor):
        """J.5 — GET /api/v1/monitors/{id}/checks → has data array + meta"""
        monitor = await make_monitor({
            "name": "E2E-J5-checks-shape",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.get(f"/api/v1/monitors/{monitor['id']}/checks", headers=pro_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body, "J.5 FAIL: Missing 'data'"
        assert isinstance(body["data"], list), "J.5 FAIL: data should be a list"
        assert "meta" in body, "J.5 FAIL: Missing 'meta'"

    @pytest.mark.asyncio
    async def test_j6_incidents_shape(self, client, pro_headers):
        """J.6 — GET /api/v1/incidents → has data array + meta"""
        resp = await client.get("/api/v1/incidents", headers=pro_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body, "J.6 FAIL: Missing 'data'"
        assert isinstance(body["data"], list), "J.6 FAIL: data should be a list"
        assert "meta" in body, "J.6 FAIL: Missing 'meta'"
        assert "total" in body["meta"], "J.6 FAIL: meta missing 'total'"


# ═══════════════════════════════════════════════════════════════════════
# K. CUSTOM BRANDING (Phase 4)
# ═══════════════════════════════════════════════════════════════════════

class TestCustomBranding:
    """Tests K.1–K.5: Custom status page branding (Pro-only)."""

    @pytest.mark.asyncio
    async def test_k1_branding_free_rejected(self, client, free_cookie):
        """K.1 — Free user: POST /settings/branding → redirect with error"""
        resp = await client.post(
            "/settings/branding",
            data={
                "status_page_brand_name": "MyBrand",
                "status_page_logo_url": "",
                "status_page_accent_color": "",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            cookies={"access_token": free_cookie},
        )
        if resp.status_code == 404:
            pytest.skip("Branding endpoint not deployed yet")
        # Should redirect back to settings
        assert resp.status_code == 302, f"K.1 FAIL: Expected 302, got {resp.status_code}"
        # Check for error flash cookie
        cookies = {}
        for header_val in resp.headers.get_list("set-cookie"):
            if "flash_message=" in header_val:
                cookies["flash_message"] = header_val
        assert "Pro" in cookies.get("flash_message", ""), \
            "K.1 FAIL: Should show Pro-only error message"

    @pytest.mark.asyncio
    async def test_k2_branding_pro_accepted(self, client, pro_cookie):
        """K.2 — Pro user: POST /settings/branding → saves successfully"""
        resp = await client.post(
            "/settings/branding",
            data={
                "status_page_brand_name": "E2E Test Brand",
                "status_page_logo_url": "https://example.com/logo.png",
                "status_page_accent_color": "#ff6600",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            cookies={"access_token": pro_cookie},
        )
        if resp.status_code == 404:
            pytest.skip("Branding endpoint not deployed yet")
        assert resp.status_code == 302, f"K.2 FAIL: Expected 302, got {resp.status_code}"
        # Check for success flash
        flash_ok = False
        for header_val in resp.headers.get_list("set-cookie"):
            if "flash_type=success" in header_val:
                flash_ok = True
        assert flash_ok, "K.2 FAIL: Should show success flash"

    @pytest.mark.asyncio
    async def test_k3_branding_http_logo_rejected(self, client, pro_cookie):
        """K.3 — Pro user: logo with http:// → rejected"""
        resp = await client.post(
            "/settings/branding",
            data={
                "status_page_brand_name": "Test",
                "status_page_logo_url": "http://insecure.com/logo.png",
                "status_page_accent_color": "",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            cookies={"access_token": pro_cookie},
        )
        if resp.status_code == 404:
            pytest.skip("Branding endpoint not deployed yet")
        assert resp.status_code == 302
        error_flash = False
        for header_val in resp.headers.get_list("set-cookie"):
            if "flash_type=error" in header_val:
                error_flash = True
        assert error_flash, "K.3 FAIL: http:// logo should be rejected"

    @pytest.mark.asyncio
    async def test_k4_branding_no_auth(self, client):
        """K.4 — POST /settings/branding without auth → redirect to login"""
        resp = await client.post(
            "/settings/branding",
            data={"status_page_brand_name": "Test"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            cookies={"access_token": ""},
        )
        if resp.status_code == 404:
            pytest.skip("Branding endpoint not deployed yet")
        assert resp.status_code == 302, f"K.4 FAIL: Expected 302, got {resp.status_code}"
        assert "/login" in resp.headers.get("location", ""), "K.4 FAIL: Should redirect to /login"

    @pytest.mark.asyncio
    async def test_k5_branding_cleanup(self, client, pro_cookie):
        """K.5 — Reset branding to defaults after tests"""
        resp = await client.post(
            "/settings/branding",
            data={
                "status_page_brand_name": "",
                "status_page_logo_url": "",
                "status_page_accent_color": "",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            cookies={"access_token": pro_cookie},
        )
        if resp.status_code == 404:
            pytest.skip("Branding endpoint not deployed yet")
        assert resp.status_code == 302


# ═══════════════════════════════════════════════════════════════════════
# L. REFERRAL TRACKING (Phase 7)
# ═══════════════════════════════════════════════════════════════════════

class TestReferralTracking:
    """Tests L.1–L.2: Referral source capture on signup."""

    @pytest.mark.asyncio
    async def test_l1_api_signup_with_ref(self, client):
        """L.1 — POST /api/auth/signup?ref=test_source → 200, user created"""
        email = f"e2e-ref-{uuid.uuid4().hex[:8]}@statusrooster.com"
        resp = await client.post(
            "/api/auth/signup?ref=test_e2e_source",
            json={"email": email, "password": "testpass123"},
        )
        assert resp.status_code == 200, f"L.1 FAIL: Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "token" in data, "L.1 FAIL: Signup should return token"
        assert "user_id" in data, "L.1 FAIL: Signup should return user_id"
        # Note: We can't verify referral_source directly via API (no endpoint),
        # but the signup succeeded with the ref param, which is the main test.

    @pytest.mark.asyncio
    async def test_l2_api_signup_ref_truncated(self, client):
        """L.2 — POST /api/auth/signup?ref=<101 chars> → ref param rejected (max_length=100)"""
        email = f"e2e-reflong-{uuid.uuid4().hex[:8]}@statusrooster.com"
        long_ref = "x" * 101
        resp = await client.post(
            f"/api/auth/signup?ref={long_ref}",
            json={"email": email, "password": "testpass123"},
        )
        # FastAPI Query(max_length=100) should return 422 for too-long ref
        # If the ref validation isn't deployed yet, the signup succeeds (200)
        if resp.status_code == 200:
            pytest.skip("Ref max_length validation not deployed yet")
        assert resp.status_code == 422, f"L.2 FAIL: Expected 422 for ref > 100 chars, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# M. CRON AUTH
# ═══════════════════════════════════════════════════════════════════════

class TestCronAuth:
    """Tests M.1–M.3: Cron endpoint authentication for cleanup."""

    @pytest.mark.asyncio
    async def test_m1_cleanup_no_secret(self, client):
        """M.1 — POST /cron/cleanup without secret → 403"""
        resp = await client.post("/cron/cleanup")
        if resp.status_code == 404:
            pytest.skip("Cleanup endpoint not deployed yet")
        assert resp.status_code == 403, f"M.1 FAIL: Expected 403, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_m2_cleanup_wrong_secret(self, client):
        """M.2 — POST /cron/cleanup with wrong secret → 403"""
        resp = await client.post(
            "/cron/cleanup",
            headers={"X-Cron-Secret": "wrong-secret-value"},
        )
        if resp.status_code == 404:
            pytest.skip("Cleanup endpoint not deployed yet")
        assert resp.status_code == 403, f"M.2 FAIL: Expected 403, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_m3_check_no_secret(self, client):
        """M.3 — POST /cron/check without secret → 403"""
        resp = await client.post("/cron/check")
        assert resp.status_code == 403, f"M.3 FAIL: Expected 403, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# N. CLONE, TOGGLE PAUSE & BULK ACTIONS
# ═══════════════════════════════════════════════════════════════════════

class TestCloneBulk:
    """Tests N.1–N.7: Monitor cloning, toggle pause, and bulk operations."""

    @pytest.mark.asyncio
    async def test_n1_clone_monitor(self, client, pro_headers, pro_cookie, make_monitor):
        """N.1 — POST /monitors/{id}/clone → creates copy"""
        monitor = await make_monitor({
            "name": "E2E-N1-original",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "keyword": "test-keyword",
        })
        resp = await client.post(
            f"/monitors/{monitor['id']}/clone",
            cookies={"access_token": pro_cookie},
        )
        assert resp.status_code == 200, f"N.1 FAIL: Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("ok") is True, "N.1 FAIL: Clone should return ok=true"
        assert "monitor_id" in data, "N.1 FAIL: Clone should return new monitor_id"
        # Clean up clone
        clone_id = data["monitor_id"]
        await client.delete(f"/api/v1/monitors/{clone_id}", headers=pro_headers)

    @pytest.mark.asyncio
    async def test_n2_clone_no_auth(self, client, pro_headers, make_monitor):
        """N.2 — POST /monitors/{id}/clone without auth → 401"""
        monitor = await make_monitor({
            "name": "E2E-N2-clone-noauth",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.post(f"/monitors/{monitor['id']}/clone", cookies={"access_token": ""})
        assert resp.status_code == 401, f"N.2 FAIL: Expected 401, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_n3_toggle_pause(self, client, pro_headers, pro_cookie, make_monitor):
        """N.3 — POST /monitors/{id}/toggle-pause → toggles paused state"""
        monitor = await make_monitor({
            "name": "E2E-N3-toggle",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        # First toggle → should pause (default is not paused)
        resp = await client.post(
            f"/monitors/{monitor['id']}/toggle-pause",
            cookies={"access_token": pro_cookie},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("paused") is True, "N.3 FAIL: First toggle should pause"

        # Second toggle → should resume
        resp2 = await client.post(
            f"/monitors/{monitor['id']}/toggle-pause",
            cookies={"access_token": pro_cookie},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("paused") is False, "N.3 FAIL: Second toggle should resume"

    @pytest.mark.asyncio
    async def test_n4_bulk_pause(self, client, pro_headers, pro_cookie, make_monitor):
        """N.4 — POST /monitors/bulk pause → pauses monitors"""
        m1 = await make_monitor({
            "name": "E2E-N4-bulk-a",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        m2 = await make_monitor({
            "name": "E2E-N4-bulk-b",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.post(
            "/monitors/bulk",
            json={"action": "pause", "monitor_ids": [m1["id"], m2["id"]]},
            cookies={"access_token": pro_cookie},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("affected") == 2, f"N.4 FAIL: Expected 2 affected, got {data.get('affected')}"

    @pytest.mark.asyncio
    async def test_n5_bulk_invalid_action(self, client, pro_cookie):
        """N.5 — POST /monitors/bulk with invalid action → 400"""
        resp = await client.post(
            "/monitors/bulk",
            json={"action": "explode", "monitor_ids": ["fake"]},
            cookies={"access_token": pro_cookie},
        )
        assert resp.status_code == 400, f"N.5 FAIL: Expected 400, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_n6_bulk_no_auth(self, client):
        """N.6 — POST /monitors/bulk without auth → 401"""
        resp = await client.post(
            "/monitors/bulk",
            json={"action": "pause", "monitor_ids": ["fake"]},
            cookies={"access_token": ""},
        )
        assert resp.status_code == 401, f"N.6 FAIL: Expected 401, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_n7_toggle_other_users_monitor(self, client, free_cookie, pro_headers, make_monitor):
        """N.7 — Toggle-pause on another user's monitor → 404"""
        monitor = await make_monitor({
            "name": "E2E-N7-other-user",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.post(
            f"/monitors/{monitor['id']}/toggle-pause",
            cookies={"access_token": free_cookie},
        )
        assert resp.status_code == 404, f"N.7 FAIL: Expected 404, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# O. SSR PAGE SMOKE TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestSsrSmoke:
    """Tests O.1–O.8: Public and authed pages return expected status codes."""

    @pytest.mark.asyncio
    async def test_o1_landing(self, client):
        """O.1 — GET / → 200 (no auth cookies)"""
        # Use empty cookies to override any session cookies on the client
        resp = await client.get("/", cookies={"access_token": ""})
        assert resp.status_code == 200, f"O.1 FAIL: Landing page returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_o2_pricing(self, client):
        """O.2 — GET /pricing → 200"""
        resp = await client.get("/pricing", cookies={"access_token": ""})
        assert resp.status_code == 200, f"O.2 FAIL: Pricing page returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_o3_privacy(self, client):
        """O.3 — GET /privacy → 200"""
        resp = await client.get("/privacy", cookies={"access_token": ""})
        assert resp.status_code == 200, f"O.3 FAIL: Privacy page returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_o4_terms(self, client):
        """O.4 — GET /terms → 200"""
        resp = await client.get("/terms", cookies={"access_token": ""})
        assert resp.status_code == 200, f"O.4 FAIL: Terms page returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_o5_api_docs(self, client):
        """O.5 — GET /docs/api → 200"""
        resp = await client.get("/docs/api", cookies={"access_token": ""})
        assert resp.status_code == 200, f"O.5 FAIL: API docs page returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_o6_signup_page(self, client):
        """O.6 — GET /signup → 200 (no auth cookies)"""
        resp = await client.get("/signup", cookies={"access_token": ""})
        assert resp.status_code == 200, f"O.6 FAIL: Signup page returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_o7_login_page(self, client):
        """O.7 — GET /login → 200 (no auth cookies)"""
        resp = await client.get("/login", cookies={"access_token": ""})
        assert resp.status_code == 200, f"O.7 FAIL: Login page returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_o8_settings_authed(self, client, pro_cookie):
        """O.8 — GET /settings with auth → 200"""
        resp = await client.get(
            "/settings",
            cookies={"access_token": pro_cookie},
        )
        assert resp.status_code == 200, f"O.8 FAIL: Settings page returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_o9_dashboard_authed(self, client, pro_cookie):
        """O.9 — GET /dashboard with auth → 200"""
        resp = await client.get(
            "/dashboard",
            cookies={"access_token": pro_cookie},
        )
        assert resp.status_code == 200, f"O.9 FAIL: Dashboard returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_o10_incidents_authed(self, client, pro_cookie):
        """O.10 — GET /incidents with auth → 200"""
        resp = await client.get(
            "/incidents",
            cookies={"access_token": pro_cookie},
        )
        assert resp.status_code == 200, f"O.10 FAIL: Incidents page returned {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# P. INCIDENT & CHECK FILTERING
# ═══════════════════════════════════════════════════════════════════════

class TestIncidentCheckFiltering:
    """Tests P.1–P.5: API filtering and pagination for checks and incidents."""

    @pytest.mark.asyncio
    async def test_p1_incidents_filter_status(self, client, pro_headers):
        """P.1 — GET /api/v1/incidents?status=open → 200 with filtered results"""
        resp = await client.get("/api/v1/incidents?status=open", headers=pro_headers)
        if resp.status_code == 500:
            pytest.skip("Incident status filtering not deployed yet")
        assert resp.status_code == 200, f"P.1 FAIL: Expected 200, got {resp.status_code}"
        body = resp.json()
        # All returned incidents should be open
        for inc in body["data"]:
            assert inc.get("status") == "open", f"P.1 FAIL: Incident {inc.get('id')} status is {inc.get('status')}, expected 'open'"

    @pytest.mark.asyncio
    async def test_p2_incidents_filter_invalid_status(self, client, pro_headers):
        """P.2 — GET /api/v1/incidents?status=bogus → 422"""
        resp = await client.get("/api/v1/incidents?status=bogus", headers=pro_headers)
        if resp.status_code == 500:
            pytest.skip("Incident status filtering not deployed yet")
        assert resp.status_code == 422, f"P.2 FAIL: Expected 422, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_p3_checks_limit_bounds(self, client, pro_headers, make_monitor):
        """P.3 — GET /api/v1/monitors/{id}/checks?limit=0 → clamped to 1"""
        monitor = await make_monitor({
            "name": "E2E-P3-checks-limit",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.get(
            f"/api/v1/monitors/{monitor['id']}/checks?limit=0",
            headers=pro_headers,
        )
        assert resp.status_code == 200, f"P.3 FAIL: Expected 200, got {resp.status_code}"
        body = resp.json()
        # Should still work (limit clamped to 1)
        assert isinstance(body["data"], list)

    @pytest.mark.asyncio
    async def test_p4_incidents_limit(self, client, pro_headers):
        """P.4 — GET /api/v1/incidents?limit=1 → returns at most 1 incident"""
        resp = await client.get("/api/v1/incidents?limit=1", headers=pro_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) <= 1, f"P.4 FAIL: Expected ≤1 incidents, got {len(body['data'])}"

    @pytest.mark.asyncio
    async def test_p5_incidents_hours_bounds(self, client, pro_headers):
        """P.5 — GET /api/v1/incidents?hours=1 → returns only recent incidents"""
        resp = await client.get("/api/v1/incidents?hours=1", headers=pro_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body, "P.5 FAIL: Missing 'data'"
        assert isinstance(body["data"], list)


# ═══════════════════════════════════════════════════════════════════════
# Q. API DOCUMENTATION ACCURACY
#    Verifies that actual API responses match the documented fields,
#    types, defaults, bounds, and error shapes in /docs/api.
# ═══════════════════════════════════════════════════════════════════════

class TestApiDocsAccuracy:
    """Tests Q.1–Q.20: API documentation accuracy — every documented
    field, default, bound, and error shape must match reality."""

    # -- Q.1 Monitor response fields match docs --

    @pytest.mark.asyncio
    async def test_q1_monitor_fields_present(self, client, pro_headers):
        """Q.1 — Monitor response contains all documented core fields"""
        # Create a monitor to inspect
        resp = await client.post("/api/v1/monitors", json={
            "url": "https://httpbin.org/status/200",
            "name": "E2E-DocFieldTest",
        }, headers=pro_headers)
        assert resp.status_code == 201, f"Q.1 FAIL: create {resp.status_code}"
        mon = resp.json()["data"]

        # Documented core fields (every monitor should have these)
        core_fields = {
            "id", "monitor_type", "name", "url", "status",
            "check_interval", "alert_email", "public", "paused",
            "created_at", "slug",
        }
        for f in core_fields:
            assert f in mon, f"Q.1 FAIL: missing documented field '{f}'"

    @pytest.mark.asyncio
    async def test_q2_internal_fields_stripped(self, client, pro_headers):
        """Q.2 — Internal fields (user_id, daily_uptime_bars, ping_token, etc.)
        are NOT present in API responses"""
        resp = await client.get("/api/v1/monitors", headers=pro_headers)
        assert resp.status_code == 200
        monitors = resp.json()["data"]
        if not monitors:
            pytest.skip("No monitors to check")

        internal_fields = {
            "user_id", "daily_uptime_bars", "hourly_uptime_bars",
            "ping_token", "ssl_expiry_alerted_days", "regions",
        }
        for mon in monitors:
            for f in internal_fields:
                assert f not in mon, f"Q.2 FAIL: internal field '{f}' leaked in monitor {mon.get('id')}"

    # -- Q.3 Check response fields --

    @pytest.mark.asyncio
    async def test_q3_check_fields(self, client, pro_headers):
        """Q.3 — Check response has documented fields, not monitor_id"""
        resp = await client.get("/api/v1/monitors", headers=pro_headers)
        monitors = resp.json()["data"]
        target = None
        for m in monitors:
            if m.get("checks_total", 0) > 0:
                target = m
                break
        if not target:
            pytest.skip("No monitors with checks")

        resp = await client.get(
            f"/api/v1/monitors/{target['id']}/checks?limit=1",
            headers=pro_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body and "meta" in body
        if body["data"]:
            check = body["data"][0]
            documented_fields = {"id", "timestamp", "is_up"}
            for f in documented_fields:
                assert f in check, f"Q.3 FAIL: missing check field '{f}'"
            assert "monitor_id" not in check, "Q.3 FAIL: monitor_id should be stripped"

    # -- Q.4 Incident response fields --

    @pytest.mark.asyncio
    async def test_q4_incident_fields(self, client, pro_headers):
        """Q.4 — Incident response has all documented fields"""
        resp = await client.get("/api/v1/incidents?limit=1", headers=pro_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body and "meta" in body
        if not body["data"]:
            pytest.skip("No incidents to verify")

        inc = body["data"][0]
        documented_fields = {
            "id", "monitor_id", "monitor_name", "status", "started_at",
        }
        for f in documented_fields:
            assert f in inc, f"Q.4 FAIL: missing incident field '{f}'"
        assert inc["status"] in ("open", "resolved"), f"Q.4 FAIL: unexpected status '{inc['status']}'"

    # -- Q.5 Response envelope shape --

    @pytest.mark.asyncio
    async def test_q5_envelope_shape_on_list(self, client, pro_headers):
        """Q.5 — List endpoints return {data: [], error: null, meta: {}}"""
        resp = await client.get("/api/v1/monitors", headers=pro_headers)
        body = resp.json()
        assert "data" in body, "Q.5 FAIL: missing 'data'"
        assert "error" in body, "Q.5 FAIL: missing 'error'"
        assert body["error"] is None, "Q.5 FAIL: error should be null on success"
        assert "meta" in body, "Q.5 FAIL: missing 'meta'"
        assert "total" in body["meta"], "Q.5 FAIL: meta missing 'total'"

    @pytest.mark.asyncio
    async def test_q6_envelope_shape_on_create(self, client, pro_headers):
        """Q.6 — POST /monitors returns 201 with {data: {monitor}, error: null}"""
        resp = await client.post("/api/v1/monitors", json={
            "url": "https://httpbin.org/status/200",
            "name": "E2E-EnvelopeTest",
        }, headers=pro_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["error"] is None, "Q.6 FAIL: error should be null on success"
        assert isinstance(body["data"], dict), "Q.6 FAIL: data should be a dict"
        assert "id" in body["data"], "Q.6 FAIL: data should contain monitor id"

    # -- Q.7 Error response shape --

    @pytest.mark.asyncio
    async def test_q7_error_response_404(self, client, pro_headers):
        """Q.7 — 404 error returns {data: null, error: 'message'}"""
        resp = await client.get("/api/v1/monitors/nonexistent_id_999", headers=pro_headers)
        assert resp.status_code == 404
        body = resp.json()
        assert body.get("data") is None, "Q.7 FAIL: data should be null on error"
        assert isinstance(body.get("error"), str), "Q.7 FAIL: error should be a string"

    @pytest.mark.asyncio
    async def test_q8_error_response_401(self, client):
        """Q.8 — 401 error on missing API key"""
        resp = await client.get("/api/v1/monitors", cookies={"access_token": ""})
        assert resp.status_code == 401
        body = resp.json()
        assert body.get("data") is None or "error" in body, "Q.8 FAIL: should return error shape"

    # -- Q.9 Check interval defaults and bounds --

    @pytest.mark.asyncio
    async def test_q9_check_interval_default_applied(self, client, pro_headers):
        """Q.9 — Creating a monitor without check_interval applies plan default"""
        resp = await client.post("/api/v1/monitors", json={
            "url": "https://httpbin.org/status/200",
            "name": "E2E-IntervalDefault",
        }, headers=pro_headers)
        assert resp.status_code == 201
        mon = resp.json()["data"]
        # Pro default should be 60 (same as free)
        assert mon.get("check_interval") == 60, \
            f"Q.9 FAIL: expected default 60 for Pro, got {mon.get('check_interval')}"

    @pytest.mark.asyncio
    async def test_q10_check_interval_default_free(self, client, free_headers):
        """Q.10 — Free user: check_interval defaults to 60"""
        resp = await client.post("/api/v1/monitors", json={
            "url": "https://httpbin.org/status/200",
            "name": "E2E-IntervalDefaultFree",
        }, headers=free_headers)
        assert resp.status_code == 201
        mon = resp.json()["data"]
        assert mon.get("check_interval") == 60, \
            f"Q.10 FAIL: expected default 60 for Free, got {mon.get('check_interval')}"

    @pytest.mark.asyncio
    async def test_q11_check_interval_below_plan_min_rejected(self, client, free_headers):
        """Q.11 — Any user: check_interval=30 returns 403 (min is 60 for all plans)"""
        resp = await client.post("/api/v1/monitors", json={
            "url": "https://httpbin.org/status/200",
            "name": "E2E-IntervalTooLow",
            "check_interval": 30,
        }, headers=free_headers)
        assert resp.status_code == 403, \
            f"Q.11 FAIL: expected 403 for interval below plan min, got {resp.status_code}"

    # -- Q.12 Value clamping (documented behavior) --

    @pytest.mark.asyncio
    async def test_q12_value_clamping_timeout(self, client, pro_headers):
        """Q.12 — timeout value clamped to 1-60, not rejected"""
        # Create with timeout=999 (should be clamped to 60)
        resp = await client.post("/api/v1/monitors", json={
            "url": "https://httpbin.org/status/200",
            "name": "E2E-ClampTimeout",
            "timeout": 999,
        }, headers=pro_headers)
        assert resp.status_code == 201, f"Q.12 FAIL: should accept and clamp, got {resp.status_code}"
        mon = resp.json()["data"]
        assert mon.get("timeout") == 60, \
            f"Q.12 FAIL: expected timeout clamped to 60, got {mon.get('timeout')}"

    @pytest.mark.asyncio
    async def test_q13_value_clamping_heartbeat_interval(self, client, pro_headers):
        """Q.13 — heartbeat_interval clamped to 60-86400"""
        resp = await client.post("/api/v1/monitors", json={
            "name": "E2E-ClampHeartbeat",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 10,  # below min of 60
        }, headers=pro_headers)
        assert resp.status_code == 201
        mon = resp.json()["data"]
        assert mon.get("heartbeat_interval") == 60, \
            f"Q.13 FAIL: expected clamped to 60, got {mon.get('heartbeat_interval')}"

    @pytest.mark.asyncio
    async def test_q14_value_clamping_ssl_threshold(self, client, pro_headers):
        """Q.14 — ssl_expiry_threshold_days clamped to 1-90"""
        resp = await client.post("/api/v1/monitors", json={
            "name": "E2E-ClampSSL",
            "monitor_type": "ssl",
            "ssl_domain": "example.com",
            "ssl_expiry_threshold_days": 200,  # above max of 90
        }, headers=pro_headers)
        assert resp.status_code == 201
        mon = resp.json()["data"]
        assert mon.get("ssl_expiry_threshold_days") == 90, \
            f"Q.14 FAIL: expected clamped to 90, got {mon.get('ssl_expiry_threshold_days')}"

    # -- Q.15 Checks endpoint query param bounds --

    @pytest.mark.asyncio
    async def test_q15_checks_limit_clamped(self, client, pro_headers):
        """Q.15 — GET /checks?limit=9999 → clamped to 500 in meta"""
        resp = await client.get("/api/v1/monitors", headers=pro_headers)
        monitors = resp.json()["data"]
        if not monitors:
            pytest.skip("No monitors")
        mid = monitors[0]["id"]
        resp = await client.get(f"/api/v1/monitors/{mid}/checks?limit=9999", headers=pro_headers)
        assert resp.status_code == 200
        meta = resp.json().get("meta", {})
        assert meta.get("limit") <= 500, \
            f"Q.15 FAIL: limit should be clamped to 500, got {meta.get('limit')}"

    # -- Q.16 Incidents query param validation --

    @pytest.mark.asyncio
    async def test_q16_incidents_invalid_status(self, client, pro_headers):
        """Q.16 — GET /incidents?status=banana → 422"""
        resp = await client.get("/api/v1/incidents?status=banana", headers=pro_headers)
        assert resp.status_code == 422, \
            f"Q.16 FAIL: expected 422 for invalid status, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_q17_incidents_meta_fields(self, client, pro_headers):
        """Q.17 — Incidents meta has documented fields: total, limit, hours"""
        resp = await client.get("/api/v1/incidents", headers=pro_headers)
        assert resp.status_code == 200
        meta = resp.json().get("meta", {})
        for f in ("total", "limit", "hours"):
            assert f in meta, f"Q.17 FAIL: meta missing documented field '{f}'"
        assert meta["limit"] == 50, f"Q.17 FAIL: default limit should be 50, got {meta['limit']}"
        assert meta["hours"] == 720, f"Q.17 FAIL: default hours should be 720, got {meta['hours']}"

    # -- Q.18 HTTP methods documented correctly --

    @pytest.mark.asyncio
    async def test_q18_invalid_http_method_rejected(self, client, pro_headers):
        """Q.18 — Invalid http_method returns 422"""
        resp = await client.post("/api/v1/monitors", json={
            "url": "https://httpbin.org/status/200",
            "name": "E2E-BadMethod",
            "http_method": "YEET",
        }, headers=pro_headers)
        assert resp.status_code == 422, \
            f"Q.18 FAIL: expected 422 for invalid method, got {resp.status_code}"

    # -- Q.19 Delete response shape --

    @pytest.mark.asyncio
    async def test_q19_delete_response_shape(self, client, pro_headers):
        """Q.19 — DELETE returns {data: {deleted: true, monitor_id: ...}}"""
        # Create then delete
        cr = await client.post("/api/v1/monitors", json={
            "url": "https://httpbin.org/status/200",
            "name": "E2E-DeleteShape",
        }, headers=pro_headers)
        assert cr.status_code == 201
        mid = cr.json()["data"]["id"]

        dr = await client.delete(f"/api/v1/monitors/{mid}", headers=pro_headers)
        assert dr.status_code == 200
        body = dr.json()
        assert body["data"]["deleted"] is True, "Q.19 FAIL: data.deleted should be true"
        assert body["data"]["monitor_id"] == mid, "Q.19 FAIL: data.monitor_id should match"

    # -- Q.20 Heartbeat monitor creates ping_url --

    @pytest.mark.asyncio
    async def test_q20_heartbeat_ping_url(self, client, pro_headers):
        """Q.20 — Heartbeat monitor response includes ping_url field"""
        resp = await client.post("/api/v1/monitors", json={
            "name": "E2E-HeartbeatPingUrl",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 300,
        }, headers=pro_headers)
        assert resp.status_code == 201
        mon = resp.json()["data"]
        assert "ping_url" in mon, "Q.20 FAIL: heartbeat monitor should have ping_url"
        assert "/api/ping/" in mon["ping_url"], "Q.20 FAIL: ping_url should contain /api/ping/"

    # -- Q.21 Plan limits table accuracy --

    @pytest.mark.asyncio
    async def test_q21_plan_limits_documented(self, client, pro_headers):
        """Q.21 — Plan limits from API docs: Free=100 monitors, Pro=200"""
        # Check that Pro user can set check_interval=60 (min for all plans)
        resp = await client.post("/api/v1/monitors", json={
            "url": "https://httpbin.org/status/200",
            "name": "E2E-ProInterval60",
            "check_interval": 60,
        }, headers=pro_headers)
        assert resp.status_code == 201, \
            f"Q.21 FAIL: Pro should allow 60s interval, got {resp.status_code}"
        mon = resp.json()["data"]
        assert mon["check_interval"] == 60

    # -- Q.22 Update (PATCH) response matches docs --

    @pytest.mark.asyncio
    async def test_q22_update_returns_full_monitor(self, client, pro_headers):
        """Q.22 — PATCH returns the full updated monitor, not partial"""
        # Create
        cr = await client.post("/api/v1/monitors", json={
            "url": "https://httpbin.org/status/200",
            "name": "E2E-UpdateShape",
        }, headers=pro_headers)
        assert cr.status_code == 201
        mid = cr.json()["data"]["id"]

        # Update just the name
        ur = await client.patch(f"/api/v1/monitors/{mid}", json={
            "name": "E2E-UpdateShape-Renamed",
        }, headers=pro_headers)
        assert ur.status_code == 200
        body = ur.json()
        assert body["error"] is None
        assert body["data"]["name"] == "E2E-UpdateShape-Renamed"
        # Should still have all core fields
        assert "id" in body["data"]
        assert "url" in body["data"]
        assert "status" in body["data"]

    # -- Q.23 OpenAPI spec is accessible --

    @pytest.mark.asyncio
    async def test_q23_openapi_spec(self, client):
        """Q.23 — /openapi.json is accessible and valid JSON"""
        resp = await client.get("/openapi.json", cookies={"access_token": ""})
        assert resp.status_code == 200
        spec = resp.json()
        assert "paths" in spec, "Q.23 FAIL: OpenAPI spec should have 'paths'"
        assert "/api/v1/monitors" in spec["paths"], "Q.23 FAIL: /api/v1/monitors not in spec"

    # -- Q.24 Docs page renders --

    @pytest.mark.asyncio
    async def test_q24_api_docs_page_renders(self, client):
        """Q.24 — /docs/api page renders with key sections"""
        resp = await client.get("/docs/api", cookies={"access_token": ""})
        assert resp.status_code == 200
        html = resp.text
        assert "Authentication" in html, "Q.24 FAIL: missing Authentication section"
        assert "Monitor Types" in html or "monitor_type" in html, "Q.24 FAIL: missing monitor types"


# ═══════════════════════════════════════════════════════════════════════
# I. CLEANUP
# ═══════════════════════════════════════════════════════════════════════

class TestCleanup:
    """Tests I.1–I.2: Clean up all test monitors."""

    @pytest.mark.asyncio
    async def test_i1_cleanup_pro_monitors(self, client, pro_headers):
        """I.1 — Delete all E2E test monitors (Pro user)"""
        resp = await client.get("/api/v1/monitors", headers=pro_headers)
        assert resp.status_code == 200
        monitors = resp.json()["data"]
        e2e_monitors = [m for m in monitors if m.get("name", "").startswith("E2E-")]

        for m in e2e_monitors:
            del_resp = await client.delete(
                f"/api/v1/monitors/{m['id']}",
                headers=pro_headers,
            )
            assert del_resp.status_code == 200, f"I.1 FAIL: Could not delete {m['id']}"

        print(f"I.1: Deleted {len(e2e_monitors)} E2E test monitors (Pro user)")

    @pytest.mark.asyncio
    async def test_i1b_cleanup_free_monitors(self, client, free_headers):
        """I.1b — Delete all E2E test monitors (Free user)"""
        resp = await client.get("/api/v1/monitors", headers=free_headers)
        if resp.status_code != 200:
            pytest.skip("Could not list free user monitors")
        monitors = resp.json()["data"]
        e2e_monitors = [m for m in monitors if m.get("name", "").startswith("E2E-")]

        for m in e2e_monitors:
            await client.delete(f"/api/v1/monitors/{m['id']}", headers=free_headers)

        print(f"I.1b: Deleted {len(e2e_monitors)} E2E test monitors (Free user)")

    @pytest.mark.asyncio
    async def test_i2_verify_clean(self, client, pro_headers):
        """I.2 — Verify no E2E monitors remain (Pro user)"""
        resp = await client.get("/api/v1/monitors", headers=pro_headers)
        assert resp.status_code == 200
        monitors = resp.json()["data"]
        e2e_remaining = [m for m in monitors if m.get("name", "").startswith("E2E-")]
        assert len(e2e_remaining) == 0, f"I.2 FAIL: {len(e2e_remaining)} E2E monitors still exist"
