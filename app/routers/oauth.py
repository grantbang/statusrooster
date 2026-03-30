"""
OAuth login routes — Google and GitHub.
Handles redirect → callback → create/find user → set cookie → dashboard.
"""

import secrets
import httpx
from urllib.parse import urlencode
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.config import settings
from app.database import get_db
from app.models.user import get_user_by_email, create_oauth_user, update_user
from app.services.auth import create_access_token

router = APIRouter(tags=["oauth"], include_in_schema=False)


# ---------------------------------------------------------------------------
# Helper: set JWT cookie and redirect to dashboard
# ---------------------------------------------------------------------------

def _login_and_redirect(user: dict) -> RedirectResponse:
    """Create JWT, set cookie, redirect to /dashboard."""
    token = create_access_token(user_id=user["id"], email=user["email"])
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=72 * 3600,
    )
    return response


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@router.get("/auth/google")
async def google_login(request: Request):
    """Redirect user to Google consent screen."""
    if not settings.GOOGLE_CLIENT_ID:
        return RedirectResponse(url="/login?error=Google+login+not+configured", status_code=302)

    # Generate state token for CSRF protection
    state = secrets.token_urlsafe(32)

    redirect_uri = f"{settings.APP_URL}/auth/google/callback"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }

    # Store state in cookie for verification
    response = RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=302)
    response.set_cookie("oauth_state", state, httponly=True, secure=True, samesite="lax", max_age=600)
    return response


@router.get("/auth/google/callback")
async def google_callback(request: Request, code: str = None, error: str = None, state: str = None):
    """Handle Google OAuth callback."""
    if error or not code:
        return RedirectResponse(url="/login?error=Google+login+cancelled", status_code=302)

    # Verify state
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        return RedirectResponse(url="/login?error=Invalid+OAuth+state", status_code=302)

    redirect_uri = f"{settings.APP_URL}/auth/google/callback"

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        })

        if token_resp.status_code != 200:
            return RedirectResponse(url="/login?error=Google+login+failed", status_code=302)

        tokens = token_resp.json()
        access_token = tokens.get("access_token")

        # Get user info
        userinfo_resp = await client.get(GOOGLE_USERINFO_URL, headers={
            "Authorization": f"Bearer {access_token}",
        })

        if userinfo_resp.status_code != 200:
            return RedirectResponse(url="/login?error=Could+not+get+Google+profile", status_code=302)

        userinfo = userinfo_resp.json()

    email = userinfo.get("email", "").lower().strip()
    name = userinfo.get("name")

    if not email:
        return RedirectResponse(url="/login?error=No+email+from+Google", status_code=302)

    # Find or create user
    db = get_db()
    user = get_user_by_email(db, email)

    if user:
        # Existing user — link provider if not already set
        provider = user.get("auth_provider") or "email"
        if "google" not in provider:
            update_user(db, user["id"], {"auth_provider": f"{provider},google"})
    else:
        # New user
        user = create_oauth_user(db, email, "google", name=name)

    response = _login_and_redirect(user)
    response.delete_cookie("oauth_state")
    return response


# ---------------------------------------------------------------------------
# GitHub OAuth
# ---------------------------------------------------------------------------

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


@router.get("/auth/github")
async def github_login(request: Request):
    """Redirect user to GitHub authorize page."""
    if not settings.GITHUB_CLIENT_ID:
        return RedirectResponse(url="/login?error=GitHub+login+not+configured", status_code=302)

    state = secrets.token_urlsafe(32)

    redirect_uri = f"{settings.APP_URL}/auth/github/callback"
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "user:email",
        "state": state,
    }

    response = RedirectResponse(url=f"{GITHUB_AUTH_URL}?{urlencode(params)}", status_code=302)
    response.set_cookie("oauth_state", state, httponly=True, secure=True, samesite="lax", max_age=600)
    return response


@router.get("/auth/github/callback")
async def github_callback(request: Request, code: str = None, error: str = None, state: str = None):
    """Handle GitHub OAuth callback."""
    if error or not code:
        return RedirectResponse(url="/login?error=GitHub+login+cancelled", status_code=302)

    # Verify state
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or stored_state != state:
        return RedirectResponse(url="/login?error=Invalid+OAuth+state", status_code=302)

    redirect_uri = f"{settings.APP_URL}/auth/github/callback"

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(GITHUB_TOKEN_URL, data={
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
        }, headers={"Accept": "application/json"})

        if token_resp.status_code != 200:
            return RedirectResponse(url="/login?error=GitHub+login+failed", status_code=302)

        tokens = token_resp.json()
        access_token = tokens.get("access_token")

        if not access_token:
            return RedirectResponse(url="/login?error=GitHub+login+failed", status_code=302)

        gh_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        # Get user profile
        user_resp = await client.get(GITHUB_USER_URL, headers=gh_headers)
        if user_resp.status_code != 200:
            return RedirectResponse(url="/login?error=Could+not+get+GitHub+profile", status_code=302)

        gh_user = user_resp.json()
        name = gh_user.get("name") or gh_user.get("login")
        email = (gh_user.get("email") or "").lower().strip()

        # If email is private, fetch from emails endpoint
        if not email:
            emails_resp = await client.get(GITHUB_EMAILS_URL, headers=gh_headers)
            if emails_resp.status_code == 200:
                for em in emails_resp.json():
                    if em.get("primary") and em.get("verified"):
                        email = em["email"].lower().strip()
                        break
                # Fallback: first verified email
                if not email:
                    for em in emails_resp.json():
                        if em.get("verified"):
                            email = em["email"].lower().strip()
                            break

    if not email:
        return RedirectResponse(url="/login?error=No+email+from+GitHub.+Make+sure+your+GitHub+email+is+verified.", status_code=302)

    # Find or create user
    db = get_db()
    user = get_user_by_email(db, email)

    if user:
        provider = user.get("auth_provider") or "email"
        if "github" not in provider:
            update_user(db, user["id"], {"auth_provider": f"{provider},github"})
    else:
        user = create_oauth_user(db, email, "github", name=name)

    response = _login_and_redirect(user)
    response.delete_cookie("oauth_state")
    return response
