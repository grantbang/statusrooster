from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
import secrets
import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

COLLECTION = "users"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    return pwd_context.verify(plain, hashed)


def create_user(db, email: str, password: str) -> dict:
    """Create a new user with email/password. Returns the user dict with id."""
    doc_ref = db.collection(COLLECTION).document()
    user_data = {
        "email": email.lower().strip(),
        "password_hash": hash_password(password),
        "auth_provider": "email",
        "plan": "free",
        "stripe_customer_id": None,
        "monitors_count": 0,
        "created_at": datetime.now(timezone.utc),
    }
    doc_ref.set(user_data)
    user_data["id"] = doc_ref.id
    return user_data


def create_oauth_user(db, email: str, provider: str, name: str = None) -> dict:
    """Create a new user from OAuth (no password). Returns the user dict with id."""
    doc_ref = db.collection(COLLECTION).document()
    user_data = {
        "email": email.lower().strip(),
        "password_hash": None,
        "auth_provider": provider,
        "name": name,
        "plan": "free",
        "stripe_customer_id": None,
        "monitors_count": 0,
        "created_at": datetime.now(timezone.utc),
    }
    doc_ref.set(user_data)
    user_data["id"] = doc_ref.id
    return user_data


def get_user_by_email(db, email: str) -> dict | None:
    """Look up a user by email. Returns user dict with id, or None."""
    docs = (
        db.collection(COLLECTION)
        .where("email", "==", email.lower().strip())
        .limit(1)
        .get()
    )
    for doc in docs:
        user = doc.to_dict()
        user["id"] = doc.id
        return user
    return None


def get_user_by_id(db, user_id: str) -> dict | None:
    """Look up a user by document ID. Returns user dict with id, or None."""
    doc = db.collection(COLLECTION).document(user_id).get()
    if doc.exists:
        user = doc.to_dict()
        user["id"] = doc.id
        return user
    return None


def update_user(db, user_id: str, updates: dict) -> None:
    """Update fields on a user document."""
    db.collection(COLLECTION).document(user_id).update(updates)


def delete_user(db, user_id: str) -> None:
    """Delete a user and all their associated data (monitors, API keys, incidents)."""
    # Delete monitors
    monitors = db.collection("monitors").where("user_id", "==", user_id).get()
    for mon in monitors:
        # Delete checks for this monitor
        checks = db.collection("checks").where("monitor_id", "==", mon.id).limit(500).get()
        for check in checks:
            check.reference.delete()
        # Delete incidents for this monitor
        incidents = db.collection("incidents").where("monitor_id", "==", mon.id).get()
        for inc in incidents:
            # Delete incident events
            events = inc.reference.collection("events").get()
            for ev in events:
                ev.reference.delete()
            inc.reference.delete()
        mon.reference.delete()

    # Delete API keys
    api_keys = db.collection("api_keys").where("user_id", "==", user_id).get()
    for key in api_keys:
        key.reference.delete()

    # Delete status pages
    status_pages = db.collection("status_pages").where("user_id", "==", user_id).get()
    for page in status_pages:
        page.reference.delete()

    # Delete user document
    db.collection(COLLECTION).document(user_id).delete()


# ---------------------------------------------------------------------------
# Password reset tokens
# ---------------------------------------------------------------------------

RESET_COLLECTION = "password_resets"
RESET_TOKEN_EXPIRY_MINUTES = 30


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_password_reset_token(db, user_id: str, email: str) -> str:
    """Create a password reset token. Returns the raw token (only shown once)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    # Invalidate any existing tokens for this user
    existing = db.collection(RESET_COLLECTION).where("user_id", "==", user_id).get()
    for doc in existing:
        doc.reference.delete()

    db.collection(RESET_COLLECTION).document().set({
        "token_hash": token_hash,
        "user_id": user_id,
        "email": email,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES),
        "used": False,
    })

    return raw_token


def verify_password_reset_token(db, raw_token: str) -> dict | None:
    """Verify a reset token. Returns the token doc dict (with id) if valid, None otherwise."""
    token_hash = _hash_token(raw_token)
    docs = (
        db.collection(RESET_COLLECTION)
        .where("token_hash", "==", token_hash)
        .where("used", "==", False)
        .limit(1)
        .get()
    )
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        if data["expires_at"].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None
        return data
    return None


def consume_password_reset_token(db, token_doc_id: str) -> None:
    """Mark a reset token as used."""
    db.collection(RESET_COLLECTION).document(token_doc_id).update({"used": True})
