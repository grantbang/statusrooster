"""
Shared fixtures for StatusRooster E2E tests.

Environment variables:
  SR_BASE_URL       — Target URL (default: https://statusrooster.com)
  SR_API_KEY        — API key for Pro test account (testaccount1@statusrooster.com)
  SR_TEST_EMAIL     — Pro test account email (default: testaccount1@statusrooster.com)
  SR_TEST_PASSWORD  — Pro test account password (default: password)
"""

import os
import re
import asyncio
import uuid
import pytest
import pytest_asyncio
import httpx

# ── Config ──────────────────────────────────────────────────────────

BASE_URL = os.environ.get("SR_BASE_URL", "https://statusrooster.com")
API_KEY = os.environ.get("SR_API_KEY", "")
TEST_EMAIL = os.environ.get("SR_TEST_EMAIL", "testaccount1@statusrooster.com")
TEST_PASSWORD = os.environ.get("SR_TEST_PASSWORD", "password")
PRO_USER_ID = os.environ.get("SR_PRO_USER_ID", "eydllii8PyTWHyi4BlmL")

assert PRO_USER_ID, "SR_PRO_USER_ID is required (default: eydllii8PyTWHyi4BlmL)"


# ── Async HTTP client ───────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def client():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, follow_redirects=False) as c:
        yield c


# ── Pro user API headers ────────────────────────────────────────────

@pytest.fixture(scope="session")
def api_key():
    assert API_KEY, "SR_API_KEY environment variable is required. Generate one in Settings."
    return API_KEY


@pytest.fixture(scope="session")
def pro_headers(api_key):
    return {"X-API-Key": api_key}


# ── Free user (created once per session, cleaned up at end) ─────────

@pytest_asyncio.fixture(scope="session")
async def free_user(client):
    """Sign up a fresh free user and return {email, password, token, user_id}."""
    email = f"e2e-free-{uuid.uuid4().hex[:8]}@statusrooster.com"
    password = "testpass123"

    resp = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Free user signup failed: {resp.text}"
    data = resp.json()

    return {
        "email": email,
        "password": password,
        "token": data["token"],
        "user_id": data["user_id"],
    }


@pytest_asyncio.fixture(scope="session")
async def free_api_key(client, free_user):
    """
    Generate an API key for the free user.
    Uses the Settings form endpoint: POST /settings/api-keys/generate
    The raw key is returned in a `new_api_key` cookie.
    """
    # Step 1: Login via form to get access_token cookie
    login_resp = await client.post(
        "/login",
        data={"email": free_user["email"], "password": free_user["password"]},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # Extract access_token from set-cookie header
    token_cookie = None
    for header_val in login_resp.headers.get_list("set-cookie"):
        if "access_token=" in header_val:
            match = re.search(r"access_token=([^;]+)", header_val)
            if match:
                token_cookie = match.group(1)
                break

    if not token_cookie:
        pytest.skip("Could not log in as free user — no access_token cookie")

    # Step 2: POST to generate API key (form data, cookie auth)
    gen_resp = await client.post(
        "/settings/api-keys/generate",
        data={"label": "E2E-free-test"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        cookies={"access_token": token_cookie},
    )

    # Step 3: Extract raw key from the new_api_key cookie on the redirect response
    raw_key = None
    for header_val in gen_resp.headers.get_list("set-cookie"):
        if "new_api_key=" in header_val:
            match = re.search(r"new_api_key=([^;]+)", header_val)
            if match:
                raw_key = match.group(1)
                break

    if not raw_key:
        pytest.skip("Could not generate API key for free user (no new_api_key cookie)")

    return raw_key


@pytest.fixture(scope="session")
def free_headers(free_api_key):
    return {"X-API-Key": free_api_key}


# ── Monitor cleanup tracker ────────────────────────────────────────

@pytest.fixture(scope="session")
def created_monitor_ids():
    """Track monitor IDs created during tests for cleanup."""
    ids = []
    yield ids


# ── Pro user login cookie (for check-now and other cookie-auth endpoints) ──

@pytest_asyncio.fixture(scope="session")
async def pro_cookie(client):
    """Login as the Pro test user and return the access_token cookie value."""
    resp = await client.post(
        "/login",
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    for header_val in resp.headers.get_list("set-cookie"):
        if "access_token=" in header_val:
            match = re.search(r"access_token=([^;]+)", header_val)
            if match:
                return match.group(1)
    pytest.fail("Could not log in as Pro test user — no access_token cookie")


@pytest_asyncio.fixture(scope="session")
async def free_cookie(client, free_user):
    """Login as the Free test user and return the access_token cookie value."""
    resp = await client.post(
        "/login",
        data={"email": free_user["email"], "password": free_user["password"]},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    for header_val in resp.headers.get_list("set-cookie"):
        if "access_token=" in header_val:
            match = re.search(r"access_token=([^;]+)", header_val)
            if match:
                return match.group(1)
    pytest.fail("Could not log in as Free test user — no access_token cookie")


# ── Check-now helper ───────────────────────────────────────────────

@pytest.fixture(scope="session")
def check_and_get_result(client, pro_cookie):
    """
    Factory: trigger check-now for a monitor and return the result dict.
    Uses cookie auth (POST /monitors/{id}/check-now).
    Returns: {"is_up": bool, "status_code": int|None, "response_ms": int|None, ...}
    """
    async def _check(monitor_id: str) -> dict:
        resp = await client.post(
            f"/monitors/{monitor_id}/check-now",
            cookies={"access_token": pro_cookie},
        )
        if resp.status_code == 429:
            # Rate limited — wait and retry once
            retry_after = resp.json().get("retry_after", 31)
            await asyncio.sleep(retry_after)
            resp = await client.post(
                f"/monitors/{monitor_id}/check-now",
                cookies={"access_token": pro_cookie},
            )
        assert resp.status_code == 200, f"check-now failed: {resp.status_code} — {resp.text}"
        return resp.json()

    return _check


# ── Helper to create + cleanup a monitor ───────────────────────────

@pytest_asyncio.fixture
async def make_monitor(client, pro_headers, created_monitor_ids):
    """Factory fixture: create a monitor and auto-delete after test."""
    ids = []

    async def _create(body: dict) -> dict:
        resp = await client.post(
            "/api/v1/monitors",
            json=body,
            headers=pro_headers,
        )
        assert resp.status_code == 201, f"Monitor creation failed: {resp.text}"
        data = resp.json()["data"]
        ids.append(data["id"])
        created_monitor_ids.append(data["id"])
        return data

    yield _create

    # Cleanup
    for mid in ids:
        try:
            await client.delete(f"/api/v1/monitors/{mid}", headers=pro_headers)
        except Exception:
            pass
