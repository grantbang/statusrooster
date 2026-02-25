from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import HTTPException, Request
from app.config import settings


def create_access_token(user_id: str, email: str) -> str:
    """Create a JWT token for a user."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT token. Returns payload dict."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(request: Request) -> dict:
    """Extract current user from JWT in cookie or Authorization header."""
    token = None

    # Check cookie first
    token = request.cookies.get("access_token")

    # Fall back to Authorization header
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(token)

    from app.database import get_db
    from app.models.user import get_user_by_id

    user = get_user_by_id(get_db(), payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
