"""
StatusRooster E2E Test Suite — Automated Tests (Part 2 of Split Test Plan)

Covers sections A–I:
  A. Authentication
  B. Security
  C. API CRUD
  D. Monitor Type Validation
  E. Plan Enforcement
  F. Badges
  G. Error Handling
  H. Status Pages
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
        assert "already registered" in resp.json().get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_a5_signup_short_password(self, client):
        """A.5 — POST /api/auth/signup with password < 8 chars → 400"""
        resp = await client.post(
            "/api/auth/signup",
            json={"email": f"short-{uuid.uuid4().hex[:6]}@test.com", "password": "abc"},
        )
        assert resp.status_code == 400, f"A.5 FAIL: Expected 400, got {resp.status_code}"
        assert "8 characters" in resp.json().get("detail", "")

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
                json={"url": "https://httpstat.us/200"},
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
        # Get the ping_token from the monitor detail
        detail_resp = await client.get(
            f"/api/v1/monitors/{monitor['id']}",
            headers=pro_headers,
        )
        detail = detail_resp.json()["data"]
        ping_token = detail.get("ping_token", "")
        assert ping_token, "B.10 FAIL: Monitor has no ping_token"

        resp = await client.get(f"/api/ping/{monitor['id']}?token={ping_token}")
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
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
                "url": "https://httpstat.us/200",
                "monitor_type": "http",
                "http_method": method,
            })
            assert monitor["http_method"] == method, f"D.4 FAIL: Method {method} not stored"

    @pytest.mark.asyncio
    async def test_d6_bearer_token_stored(self, client, pro_headers, make_monitor):
        """D.6 — Create HTTP monitor with bearer_token → stored on doc"""
        monitor = await make_monitor({
            "name": "E2E-D6-bearer",
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
        # Get ping_token
        detail = await client.get(
            f"/api/v1/monitors/{monitor['id']}",
            headers=pro_headers,
        )
        ping_token = detail.json()["data"].get("ping_token", "")
        assert ping_token, "D.12 FAIL: No ping_token on monitor"

        resp = await client.get(f"/api/ping/{monitor['id']}?token={ping_token}")
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

    Create operations silently ignore Pro-only fields (no error).
    Update operations return 403 with a specific error message.
    """

    # ── E.1: Free user monitor limit (5) ──

    @pytest.mark.asyncio
    async def test_e1_free_monitor_limit(self, client, free_headers):
        """E.1 — Free user: 6th monitor → 403"""
        created = []
        try:
            for i in range(6):
                resp = await client.post(
                    "/api/v1/monitors",
                    json={"name": f"E2E-E1-free-{i}", "url": "https://httpstat.us/200", "monitor_type": "http"},
                    headers=free_headers,
                )
                if resp.status_code == 201:
                    created.append(resp.json()["data"]["id"])
                elif resp.status_code == 403:
                    # This is the expected outcome for the 6th monitor
                    assert i == 5, f"E.1 FAIL: Got 403 on monitor #{i+1}, expected on #6"
                    assert "Free plan" in str(resp.json()), "E.1 FAIL: Error should mention Free plan"
                    return  # Test passed
                else:
                    pytest.fail(f"E.1 FAIL: Unexpected status {resp.status_code} on monitor #{i+1}")
            pytest.fail("E.1 FAIL: Was able to create 6 monitors — limit not enforced")
        finally:
            for mid in created:
                try:
                    await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)
                except Exception:
                    pass

    # ── E.2: Free create silently strips slack_webhook ──

    @pytest.mark.asyncio
    async def test_e2_free_create_slack_stripped(self, client, free_headers):
        """E.2 — Free user: create with slack webhook → silently stripped (empty string)"""
        resp = await client.post(
            "/api/v1/monitors",
            json={
                "name": "E2E-E2-free-slack",
                "url": "https://httpstat.us/200",
                "monitor_type": "http",
                "alert_slack_webhook": "https://hooks.slack.com/services/TEST/TEST/TEST",
            },
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201, f"E.2 FAIL: Expected 201, got {resp.status_code}"
            mid = resp.json()["data"]["id"]
            data = resp.json()["data"]
            assert data.get("alert_slack_webhook", "") == "", \
                f"E.2 FAIL: Free user slack webhook should be silently stripped, got '{data.get('alert_slack_webhook')}'"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.3: Pro create KEEPS slack_webhook ──

    @pytest.mark.asyncio
    async def test_e3_pro_create_slack_kept(self, client, pro_headers, make_monitor):
        """E.3 — Pro user: create with slack webhook → stored"""
        monitor = await make_monitor({
            "name": "E2E-E3-pro-slack",
            "url": "https://httpstat.us/200",
            "monitor_type": "http",
            "alert_slack_webhook": "https://hooks.slack.com/services/TEST/TEST/TEST",
        })
        detail = await client.get(f"/api/v1/monitors/{monitor['id']}", headers=pro_headers)
        data = detail.json()["data"]
        assert data.get("alert_slack_webhook") == "https://hooks.slack.com/services/TEST/TEST/TEST", \
            "E.3 FAIL: Pro user should have slack webhook stored"

    # ── E.4: Free create silently strips webhook_url ──

    @pytest.mark.asyncio
    async def test_e4_free_create_webhook_stripped(self, client, free_headers):
        """E.4 — Free user: create with webhook_url → silently stripped"""
        resp = await client.post(
            "/api/v1/monitors",
            json={
                "name": "E2E-E4-free-webhook",
                "url": "https://httpstat.us/200",
                "monitor_type": "http",
                "webhook_url": "https://example.com/webhook",
            },
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201, f"E.4 FAIL: Expected 201, got {resp.status_code}"
            mid = resp.json()["data"]["id"]
            data = resp.json()["data"]
            assert data.get("webhook_url", "") == "", "E.4 FAIL: Free webhook_url should be stripped"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.5: Free create silently strips basic_auth ──

    @pytest.mark.asyncio
    async def test_e5_free_create_basic_auth_stripped(self, client, free_headers):
        """E.5 — Free user: create with basic_auth → silently stripped"""
        resp = await client.post(
            "/api/v1/monitors",
            json={
                "name": "E2E-E5-free-basic-auth",
                "url": "https://httpstat.us/200",
                "monitor_type": "http",
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
            assert data.get("basic_auth_user", "") == "", "E.5 FAIL: Free basic_auth_user should be stripped"
            assert data.get("basic_auth_pass", "") == "", "E.5 FAIL: Free basic_auth_pass should be stripped"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.6: Free UPDATE slack webhook → 403 ──

    @pytest.mark.asyncio
    async def test_e6_free_update_slack_403(self, client, free_headers):
        """E.6 — Free user: update with slack webhook → 403"""
        # Create a monitor first
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-E6-free-update-slack", "url": "https://httpstat.us/200", "monitor_type": "http"},
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201
            mid = resp.json()["data"]["id"]
            # Try to update with slack webhook
            update_resp = await client.patch(
                f"/api/v1/monitors/{mid}",
                json={"alert_slack_webhook": "https://hooks.slack.com/services/T/T/T"},
                headers=free_headers,
            )
            assert update_resp.status_code == 403, f"E.6 FAIL: Expected 403, got {update_resp.status_code}"
            assert "Slack" in str(update_resp.json()), "E.6 FAIL: Error should mention Slack"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.7: Free UPDATE webhook_url → 403 ──

    @pytest.mark.asyncio
    async def test_e7_free_update_webhook_403(self, client, free_headers):
        """E.7 — Free user: update with webhook_url → 403"""
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-E7-free-update-webhook", "url": "https://httpstat.us/200", "monitor_type": "http"},
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
            assert update_resp.status_code == 403, f"E.7 FAIL: Expected 403, got {update_resp.status_code}"
            assert "Webhook" in str(update_resp.json()), "E.7 FAIL: Error should mention Webhook"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.8: Free UPDATE check_interval → 403 ──

    @pytest.mark.asyncio
    async def test_e8_free_update_interval_403(self, client, free_headers):
        """E.8 — Free user: update check_interval → 403"""
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-E8-free-update-interval", "url": "https://httpstat.us/200", "monitor_type": "http"},
            headers=free_headers,
        )
        mid = None
        try:
            assert resp.status_code == 201
            mid = resp.json()["data"]["id"]
            update_resp = await client.patch(
                f"/api/v1/monitors/{mid}",
                json={"check_interval": 60},
                headers=free_headers,
            )
            assert update_resp.status_code == 403, f"E.8 FAIL: Expected 403, got {update_resp.status_code}"
            assert "interval" in str(update_resp.json()).lower(), "E.8 FAIL: Error should mention interval"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.9: Free UPDATE maintenance_windows → 403 ──

    @pytest.mark.asyncio
    async def test_e9_free_update_maintenance_403(self, client, free_headers):
        """E.9 — Free user: update maintenance_windows → 403"""
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-E9-free-maintenance", "url": "https://httpstat.us/200", "monitor_type": "http"},
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
            assert update_resp.status_code == 403, f"E.9 FAIL: Expected 403, got {update_resp.status_code}"
            assert "Maintenance" in str(update_resp.json()), "E.9 FAIL: Error should mention Maintenance"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.10: Free UPDATE basic_auth → 403 ──

    @pytest.mark.asyncio
    async def test_e10_free_update_basic_auth_403(self, client, free_headers):
        """E.10 — Free user: update basic_auth → 403"""
        resp = await client.post(
            "/api/v1/monitors",
            json={"name": "E2E-E10-free-basic-auth", "url": "https://httpstat.us/200", "monitor_type": "http"},
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
            assert update_resp.status_code == 403, f"E.10 FAIL: Expected 403, got {update_resp.status_code}"
            assert "Basic Auth" in str(update_resp.json()), "E.10 FAIL: Error should mention Basic Auth"
        finally:
            if mid:
                await client.delete(f"/api/v1/monitors/{mid}", headers=free_headers)

    # ── E.11: Free status page limit (1) ──

    @pytest.mark.asyncio
    async def test_e11_free_public_status_page_limit(self, client, free_headers):
        """E.11 — Free user: 2nd public monitor → 403 (status page limit=1)"""
        created = []
        try:
            # First public monitor should succeed
            resp = await client.post(
                "/api/v1/monitors",
                json={"name": "E2E-E11-free-public-1", "url": "https://httpstat.us/200", "monitor_type": "http", "public": True},
                headers=free_headers,
            )
            assert resp.status_code == 201, f"E.11 FAIL: First public should succeed, got {resp.status_code}"
            created.append(resp.json()["data"]["id"])

            # Second public monitor should fail
            resp2 = await client.post(
                "/api/v1/monitors",
                json={"name": "E2E-E11-free-public-2", "url": "https://httpstat.us/200", "monitor_type": "http", "public": True},
                headers=free_headers,
            )
            assert resp2.status_code == 403, f"E.11 FAIL: Second public should be 403, got {resp2.status_code}"
            assert "public status page" in str(resp2.json()).lower(), "E.11 FAIL: Error should mention status page limit"
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
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
    async def test_g7_api_create_name_no_url(self, client, pro_headers, make_monitor):
        """G.7 — POST /api/v1/monitors with name but no URL → 201 (url optional)"""
        monitor = await make_monitor({
            "name": "E2E-G7-no-url",
            "monitor_type": "http",
        })
        assert monitor["name"] == "E2E-G7-no-url"

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
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
            "url": "https://httpstat.us/200",
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
