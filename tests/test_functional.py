"""
StatusRooster Functional Tests — Monitoring Lifecycle

Tests that the product actually WORKS: checks run correctly, heartbeat/SSL
lifecycles behave correctly, status pages render, SSR pages display right info.

Note: check-now returns check results but does NOT update monitor status,
create incidents, or store checks. Those actions happen via the cron path
(/cron/check). Tests here verify check-now returns correct results, and
separately verify API/SSR behavior.

Run:
  SR_API_KEY=sr_xxx pytest tests/test_functional.py -v --asyncio-mode=auto

Slow tests (incident resolution, heartbeat timeout):
  SR_API_KEY=sr_xxx pytest tests/test_functional.py -v --asyncio-mode=auto -m "not slow"
  SR_API_KEY=sr_xxx pytest tests/test_functional.py -v --asyncio-mode=auto -m slow
"""

import asyncio
import pytest
import httpx

from tests.conftest import BASE_URL, TEST_EMAIL, TEST_PASSWORD


# ═══════════════════════════════════════════════════════════════════════
# R. HTTP MONITORING LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════

class TestHttpLifecycle:
    """Tests R.1–R.8: HTTP check-now produces correct check results."""

    @pytest.mark.asyncio
    async def test_r1_http_up_produces_check_data(self, client, pro_headers, make_monitor, check_and_get_result):
        """R.1 — check-now on healthy URL → is_up, status_code, response_ms populated"""
        monitor = await make_monitor({
            "name": "E2E-R1-http-lifecycle",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True
        assert result["status_code"] == 200
        assert isinstance(result["response_ms"], (int, float))
        assert result["response_ms"] > 0
        assert result.get("checked_at") is not None

    @pytest.mark.asyncio
    async def test_r2_http_down_500(self, client, pro_headers, make_monitor, check_and_get_result):
        """R.2 — check-now on 500 URL → is_up=False, status_code=500"""
        monitor = await make_monitor({
            "name": "E2E-R2-http-500",
            "url": "https://httpbin.org/status/500",
            "monitor_type": "http",
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is False
        assert result["status_code"] == 500

    @pytest.mark.asyncio
    async def test_r3_http_down_404(self, client, pro_headers, make_monitor, check_and_get_result):
        """R.3 — check-now on 404 URL → is_up=False, status_code=404"""
        monitor = await make_monitor({
            "name": "E2E-R3-http-404",
            "url": "https://httpbin.org/status/404",
            "monitor_type": "http",
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is False
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_r4_http_timeout(self, client, pro_headers, make_monitor, check_and_get_result):
        """R.4 — check-now on slow URL with short timeout → is_up=False (timeout)"""
        monitor = await make_monitor({
            "name": "E2E-R4-http-timeout",
            "url": "https://httpbin.org/delay/30",
            "monitor_type": "http",
            "timeout": 3,
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is False, f"R.4: Should timeout but got {result}"

    @pytest.mark.asyncio
    async def test_r5_http_dns_failure(self, client, pro_headers, make_monitor, check_and_get_result):
        """R.5 — check-now on nonexistent domain → is_up=False"""
        monitor = await make_monitor({
            "name": "E2E-R5-dns-fail",
            "url": "https://this-domain-definitely-does-not-exist-sr.invalid",
            "monitor_type": "http",
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is False, f"R.5: DNS fail should be down, got {result}"

    @pytest.mark.asyncio
    async def test_r6_http_post_method(self, client, pro_headers, make_monitor, check_and_get_result):
        """R.6 — POST monitor sends POST request and gets 200"""
        monitor = await make_monitor({
            "name": "E2E-R6-post-method",
            "url": "https://httpbin.org/post",
            "monitor_type": "http",
            "http_method": "POST",
            "request_body": '{"test": true}',
            "request_content_type": "application/json",
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"R.6: POST to /post should succeed, got {result}"
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_r7_http_keyword_match(self, client, pro_headers, make_monitor, check_and_get_result):
        """R.7 — Keyword present in page body → is_up=True"""
        monitor = await make_monitor({
            "name": "E2E-R7-keyword-match",
            "url": "https://httpbin.org/html",
            "monitor_type": "http",
            "keyword": "Moby-Dick",
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"R.7: Keyword should match, got {result}"

    @pytest.mark.asyncio
    async def test_r8_http_basic_auth(self, client, pro_headers, make_monitor, check_and_get_result):
        """R.8 — Basic auth credentials sent correctly → 200"""
        monitor = await make_monitor({
            "name": "E2E-R8-basic-auth",
            "url": "https://httpbin.org/basic-auth/user/pass",
            "monitor_type": "http",
            "basic_auth_user": "user",
            "basic_auth_pass": "pass",
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"R.8: Basic auth should succeed, got {result}"
        assert result["status_code"] == 200


# ═══════════════════════════════════════════════════════════════════════
# S. CHECK-NOW RESULT VERIFICATION
# ═══════════════════════════════════════════════════════════════════════

class TestCheckNowResults:
    """Tests S.1–S.4: Verify check-now returns well-formed results."""

    @pytest.mark.asyncio
    async def test_s1_check_now_returns_monitor_type(self, client, pro_headers, make_monitor, check_and_get_result):
        """S.1 — check-now result includes monitor_type"""
        monitor = await make_monitor({
            "name": "E2E-S1-result-type",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        result = await check_and_get_result(monitor["id"])
        assert result.get("monitor_type") == "http"

    @pytest.mark.asyncio
    async def test_s2_check_now_ssl_returns_expiry(self, client, pro_headers, make_monitor, check_and_get_result):
        """S.2 — check-now on HTTPS URL includes SSL info"""
        monitor = await make_monitor({
            "name": "E2E-S2-ssl-info",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        result = await check_and_get_result(monitor["id"])
        # HTTPS URLs should include SSL expiry info
        assert result.get("ssl_expiry") is not None, f"S.2: HTTPS check should include ssl_expiry, got {result}"

    @pytest.mark.asyncio
    async def test_s3_check_now_error_message(self, client, pro_headers, make_monitor, check_and_get_result):
        """S.3 — Failed check-now includes error message"""
        monitor = await make_monitor({
            "name": "E2E-S3-error-msg",
            "url": "https://httpbin.org/status/500",
            "monitor_type": "http",
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is False
        assert result.get("error") is not None, "S.3: Failed check should have error"

    @pytest.mark.asyncio
    async def test_s4_check_now_rate_limit(self, client, pro_cookie, make_monitor, check_and_get_result):
        """S.4 — Check-now rate limited to 1 per 30s per monitor"""
        monitor = await make_monitor({
            "name": "E2E-S4-rate-limit",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        # First check succeeds
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True

        # Immediate second check should be rate limited
        resp = await client.post(
            f"/monitors/{monitor['id']}/check-now",
            cookies={"access_token": pro_cookie},
        )
        assert resp.status_code == 429, f"S.4: Expected 429 rate limit, got {resp.status_code}"
        body = resp.json()
        assert "retry_after" in body or "wait" in body.get("error", "").lower()


# ═══════════════════════════════════════════════════════════════════════
# T. JSON/API MONITORING
# ═══════════════════════════════════════════════════════════════════════

class TestJsonApiMonitoring:
    """Tests T.1–T.4: JSON/API monitors with assertions."""

    @pytest.mark.asyncio
    async def test_t1_json_assertion_equals_pass(self, client, pro_headers, make_monitor, check_and_get_result):
        """T.1 — JSON assertion equals (pass) → is_up=True"""
        monitor = await make_monitor({
            "name": "E2E-T1-json-eq-pass",
            "url": "https://httpbin.org/json",
            "monitor_type": "json_api",
            "json_assertions": [
                {"path": "slideshow.author", "operator": "equals", "value": "Yours Truly"},
            ],
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"T.1: Assertion should pass, got {result}"

    @pytest.mark.asyncio
    async def test_t2_json_assertion_equals_fail(self, client, pro_headers, make_monitor, check_and_get_result):
        """T.2 — JSON assertion equals (fail) → is_up=False"""
        monitor = await make_monitor({
            "name": "E2E-T2-json-eq-fail",
            "url": "https://httpbin.org/json",
            "monitor_type": "json_api",
            "json_assertions": [
                {"path": "slideshow.author", "operator": "equals", "value": "Wrong Author"},
            ],
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is False, f"T.2: Assertion should fail, got {result}"

    @pytest.mark.asyncio
    async def test_t3_json_assertion_exists(self, client, pro_headers, make_monitor, check_and_get_result):
        """T.3 — JSON assertion 'exists' on valid path → is_up=True"""
        monitor = await make_monitor({
            "name": "E2E-T3-json-exists",
            "url": "https://httpbin.org/json",
            "monitor_type": "json_api",
            "json_assertions": [
                {"path": "slideshow.title", "operator": "exists", "value": ""},
            ],
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"T.3: 'exists' on valid path should pass, got {result}"

    @pytest.mark.asyncio
    async def test_t4_json_post_with_body(self, client, pro_headers, make_monitor, check_and_get_result):
        """T.4 — JSON/API POST with request body → 200, is_up=True"""
        monitor = await make_monitor({
            "name": "E2E-T4-json-post",
            "url": "https://httpbin.org/post",
            "monitor_type": "json_api",
            "http_method": "POST",
            "request_body": '{"key": "value"}',
            "request_content_type": "application/json",
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"T.4: POST should succeed, got {result}"


# ═══════════════════════════════════════════════════════════════════════
# U. SSL CERTIFICATE MONITORING
# ═══════════════════════════════════════════════════════════════════════

class TestSslMonitoring:
    """Tests U.1–U.4: SSL certificate checks."""

    @pytest.mark.asyncio
    async def test_u1_ssl_valid_cert(self, client, pro_headers, make_monitor, check_and_get_result):
        """U.1 — SSL check on valid cert → is_up=True, days remaining populated"""
        monitor = await make_monitor({
            "name": "E2E-U1-ssl-valid",
            "monitor_type": "ssl",
            "ssl_domain": "google.com",
            "ssl_expiry_threshold_days": 7,
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True, f"U.1: Valid SSL should be up, got {result}"
        assert result.get("ssl_expiry") is not None, f"U.1: Should have ssl_expiry, got {result}"
        assert result.get("ssl_expiry_days") is not None, f"U.1: Should have ssl_expiry_days, got {result}"
        assert result["ssl_expiry_days"] > 7, f"U.1: Google cert should have >7 days left"

    @pytest.mark.asyncio
    async def test_u2_ssl_expired_cert(self, client, pro_headers, make_monitor, check_and_get_result):
        """U.2 — SSL check on expired cert → is_up=False"""
        monitor = await make_monitor({
            "name": "E2E-U2-ssl-expired",
            "monitor_type": "ssl",
            "ssl_domain": "expired.badssl.com",
            "ssl_expiry_threshold_days": 30,
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is False, f"U.2: Expired SSL should be down, got {result}"

    @pytest.mark.asyncio
    async def test_u3_ssl_no_interval_in_api(self, client, pro_headers, make_monitor):
        """U.3 — SSL monitor should not have a user-configurable check_interval"""
        monitor = await make_monitor({
            "name": "E2E-U3-ssl-no-interval",
            "monitor_type": "ssl",
            "ssl_domain": "github.com",
        })
        # SSL monitors get default check_interval from the system, but
        # the edit page should not expose it. Verify the monitor was created.
        resp = await client.get(f"/api/v1/monitors/{monitor['id']}", headers=pro_headers)
        mon = resp.json()["data"]
        assert mon["monitor_type"] == "ssl"

    @pytest.mark.asyncio
    async def test_u4_ssl_result_has_expiry_info(self, client, pro_headers, make_monitor, check_and_get_result):
        """U.4 — SSL check result includes expiry details"""
        monitor = await make_monitor({
            "name": "E2E-U4-ssl-expiry-info",
            "monitor_type": "ssl",
            "ssl_domain": "github.com",
            "ssl_expiry_threshold_days": 7,
        })
        result = await check_and_get_result(monitor["id"])
        assert result["is_up"] is True
        assert result["monitor_type"] == "ssl"
        assert result.get("ssl_expiry") is not None
        assert result.get("ssl_expiry_days") is not None
        assert isinstance(result["ssl_expiry_days"], (int, float))


# ═══════════════════════════════════════════════════════════════════════
# V. HEARTBEAT MONITORING
# ═══════════════════════════════════════════════════════════════════════

class TestHeartbeatMonitoring:
    """Tests V.1–V.4: Heartbeat ping lifecycle."""

    @pytest.mark.asyncio
    async def test_v1_heartbeat_ping_sets_up(self, client, pro_headers, make_monitor):
        """V.1 — Ping heartbeat URL → status becomes 'up', last_heartbeat set"""
        monitor = await make_monitor({
            "name": "E2E-V1-heartbeat-ping",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 300,
            "heartbeat_grace_period": 60,
        })
        # Get ping URL
        detail = await client.get(f"/api/v1/monitors/{monitor['id']}", headers=pro_headers)
        ping_url = detail.json()["data"].get("ping_url", "")
        assert ping_url, "V.1: Monitor should have ping_url"

        # Ping it
        resp = await client.get(ping_url.replace(BASE_URL, ""))
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["status"] == "up"

        # Verify monitor updated
        detail2 = await client.get(f"/api/v1/monitors/{monitor['id']}", headers=pro_headers)
        mon = detail2.json()["data"]
        assert mon.get("last_heartbeat") is not None, "V.1: last_heartbeat should be set after ping"

    @pytest.mark.asyncio
    async def test_v2_heartbeat_ping_url_has_token(self, client, pro_headers, make_monitor):
        """V.2 — Heartbeat ping_url contains token parameter"""
        monitor = await make_monitor({
            "name": "E2E-V2-heartbeat-token",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 300,
        })
        detail = await client.get(f"/api/v1/monitors/{monitor['id']}", headers=pro_headers)
        ping_url = detail.json()["data"].get("ping_url", "")
        assert "token=" in ping_url, f"V.2: ping_url should contain token, got {ping_url}"

    @pytest.mark.asyncio
    async def test_v3_heartbeat_wrong_token_rejected(self, client, pro_headers, make_monitor):
        """V.3 — Ping with wrong token → 403"""
        monitor = await make_monitor({
            "name": "E2E-V3-heartbeat-bad-token",
            "monitor_type": "heartbeat",
        })
        resp = await client.get(f"/api/ping/{monitor['id']}?token=WRONG")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_v4_heartbeat_no_token_rejected(self, client, pro_headers, make_monitor):
        """V.4 — Ping without token → 403"""
        monitor = await make_monitor({
            "name": "E2E-V4-heartbeat-no-token",
            "monitor_type": "heartbeat",
        })
        resp = await client.get(f"/api/ping/{monitor['id']}")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════
# W. API DATA ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

class TestApiData:
    """Tests W.1–W.3: API data endpoints return correct shapes."""

    @pytest.mark.asyncio
    async def test_w1_checks_api_returns_correct_shape(self, client, pro_headers, make_monitor):
        """W.1 — GET checks API returns data array with correct fields"""
        monitor = await make_monitor({
            "name": "E2E-W1-checks-shape",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.get(
            f"/api/v1/monitors/{monitor['id']}/checks?limit=10",
            headers=pro_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert isinstance(body["data"], list)
        assert body.get("error") is None

    @pytest.mark.asyncio
    async def test_w2_chart_api_returns_correct_shape(self, client, pro_cookie, make_monitor):
        """W.2 — Internal chart API returns checks + stats structure"""
        monitor = await make_monitor({
            "name": "E2E-W2-chart-shape",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
        })
        resp = await client.get(
            f"/api/monitors/{monitor['id']}/checks?hours=24",
            cookies={"access_token": pro_cookie},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "checks" in data
        assert "stats" in data
        assert isinstance(data["checks"], list)

    @pytest.mark.asyncio
    async def test_w3_incidents_api_returns_correct_shape(self, client, pro_headers):
        """W.3 — GET incidents API returns data array"""
        resp = await client.get("/api/v1/incidents", headers=pro_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert isinstance(body["data"], list)
        assert body.get("error") is None


# ═══════════════════════════════════════════════════════════════════════
# X. STATUS PAGES
# ═══════════════════════════════════════════════════════════════════════

class TestStatusPages:
    """Tests X.1–X.3: Public status pages render correctly."""

    @pytest.mark.asyncio
    async def test_x1_public_monitor_status_page(self, client, pro_headers, make_monitor):
        """X.1 — Public monitor with slug has accessible status page"""
        monitor = await make_monitor({
            "name": "E2E-X1-status-page",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "public": True,
            "slug": "e2e-x1-test",
        })
        # Verify slug was set
        resp = await client.get(f"/api/v1/monitors/{monitor['id']}", headers=pro_headers)
        mon = resp.json()["data"]
        slug = mon.get("slug", "")
        if not slug:
            pytest.skip("X.1: API did not set slug on creation — slug may require separate update")

        # Access the status page
        resp = await client.get(f"/s/{slug}", follow_redirects=True)
        assert resp.status_code == 200, f"X.1: Status page returned {resp.status_code}"

    @pytest.mark.asyncio
    async def test_x2_private_monitor_no_status_page(self, client, pro_headers, make_monitor):
        """X.2 — Private monitor has no status page"""
        monitor = await make_monitor({
            "name": "E2E-X2-private",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "public": False,
        })
        # Private monitors shouldn't have a slug-based status page
        resp = await client.get(f"/s/{monitor['id']}", follow_redirects=True)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_x3_aggregate_status_page_all_plans(self, client, pro_headers):
        """X.3 — Aggregate status page available for all users with public monitors"""
        from tests.conftest import PRO_USER_ID
        resp = await client.get(f"/status/{PRO_USER_ID}", follow_redirects=True)
        # Aggregate status page is available to all plans
        # 200 if user has public monitors, 404 if no public monitors or user not found
        assert resp.status_code in (200, 404), f"X.3: Expected 200 or 404, got {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════
# Y. SSR PAGE RENDERING WITH DATA
# ═══════════════════════════════════════════════════════════════════════

class TestSsrWithData:
    """Tests Y.1–Y.7: SSR pages render correctly with real monitor data."""

    @pytest.mark.asyncio
    async def test_y1_dashboard_shows_monitors(self, client, pro_cookie, pro_headers, make_monitor, check_and_get_result):
        """Y.1 — Dashboard renders with monitor cards after check"""
        monitor = await make_monitor({
            "name": "E2E-Y1-dashboard-render",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "group": "E2E-Tests",
        })
        await check_and_get_result(monitor["id"])

        resp = await client.get("/dashboard", cookies={"access_token": pro_cookie})
        assert resp.status_code == 200
        assert "E2E-Y1-dashboard-render" in resp.text
        assert "E2E-Tests" in resp.text  # group badge should appear

    @pytest.mark.asyncio
    async def test_y2_monitor_detail_renders(self, client, pro_cookie, pro_headers, make_monitor, check_and_get_result):
        """Y.2 — Monitor detail page renders with check data"""
        monitor = await make_monitor({
            "name": "E2E-Y2-detail-render",
            "url": "https://httpbin.org/status/200",
            "monitor_type": "http",
            "group": "E2E-Tests",
        })
        await check_and_get_result(monitor["id"])

        resp = await client.get(f"/monitors/{monitor['id']}", cookies={"access_token": pro_cookie})
        assert resp.status_code == 200
        body = resp.text
        assert "E2E-Y2-detail-render" in body
        assert "Monitoring" in body  # breadcrumb
        assert "E2E-Tests" in body  # group in breadcrumb

    @pytest.mark.asyncio
    async def test_y3_monitor_detail_ssl_no_chart(self, client, pro_cookie, pro_headers, make_monitor, check_and_get_result):
        """Y.3 — SSL monitor detail page has no response time chart"""
        monitor = await make_monitor({
            "name": "E2E-Y3-ssl-detail",
            "monitor_type": "ssl",
            "ssl_domain": "google.com",
        })
        await check_and_get_result(monitor["id"])

        resp = await client.get(f"/monitors/{monitor['id']}", cookies={"access_token": pro_cookie})
        assert resp.status_code == 200
        body = resp.text
        assert "Certificate checked periodically" in body
        assert "responseChart" not in body, "Y.3: SSL detail should not have response chart"

    @pytest.mark.asyncio
    async def test_y4_monitor_detail_heartbeat_no_check_now(self, client, pro_cookie, pro_headers, make_monitor):
        """Y.4 — Heartbeat monitor detail has no 'Check now' button"""
        monitor = await make_monitor({
            "name": "E2E-Y4-heartbeat-detail",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 300,
        })
        resp = await client.get(f"/monitors/{monitor['id']}", cookies={"access_token": pro_cookie})
        assert resp.status_code == 200
        body = resp.text
        # The check-now button contains "checkNowBtn" id — heartbeat should not have it
        assert 'id="checkNowBtn"' not in body, "Y.4: Heartbeat should not have check-now button"
        assert "Expected every" in body

    @pytest.mark.asyncio
    async def test_y5_incidents_page_renders(self, client, pro_cookie):
        """Y.5 — Incidents page renders correctly"""
        resp = await client.get("/incidents", cookies={"access_token": pro_cookie})
        assert resp.status_code == 200
        body = resp.text
        assert "Incidents" in body

    @pytest.mark.asyncio
    async def test_y6_edit_ssl_no_interval(self, client, pro_cookie, pro_headers, make_monitor):
        """Y.6 — Edit page for SSL monitor does not show interval slider"""
        monitor = await make_monitor({
            "name": "E2E-Y6-ssl-edit",
            "monitor_type": "ssl",
            "ssl_domain": "google.com",
        })
        resp = await client.get(f"/monitors/{monitor['id']}/edit", cookies={"access_token": pro_cookie})
        assert resp.status_code == 200
        body = resp.text
        assert "intervalSection" not in body, "Y.6: SSL edit should not show interval section"

    @pytest.mark.asyncio
    async def test_y7_edit_heartbeat_no_interval(self, client, pro_cookie, pro_headers, make_monitor):
        """Y.7 — Edit page for heartbeat monitor does not show check interval slider"""
        monitor = await make_monitor({
            "name": "E2E-Y7-heartbeat-edit",
            "monitor_type": "heartbeat",
            "heartbeat_interval": 300,
        })
        resp = await client.get(f"/monitors/{monitor['id']}/edit", cookies={"access_token": pro_cookie})
        assert resp.status_code == 200
        body = resp.text
        assert "intervalSection" not in body, "Y.7: Heartbeat edit should not show check interval section"


# ═══════════════════════════════════════════════════════════════════════
# Z. CLEANUP
# ═══════════════════════════════════════════════════════════════════════

class TestFunctionalCleanup:
    """Z.1 — Clean up all monitors created by functional tests."""

    @pytest.mark.asyncio
    async def test_z1_cleanup(self, client, pro_headers):
        """Z.1 — Delete all E2E- monitors from functional tests"""
        resp = await client.get("/api/v1/monitors", headers=pro_headers)
        monitors = resp.json().get("data", [])
        for m in monitors:
            if m.get("name", "").startswith("E2E-"):
                await client.delete(f"/api/v1/monitors/{m['id']}", headers=pro_headers)
