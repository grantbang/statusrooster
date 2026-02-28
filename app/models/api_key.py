"""API Key model — generate, hash, store, list, revoke."""

import secrets
import hashlib
from datetime import datetime, timezone

COLLECTION = "api_keys"

# Prefix so users can easily identify StatusRooster keys
KEY_PREFIX = "sr_"


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of the raw API key. We never store the raw key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key(db, user_id: str, label: str = "Default") -> dict:
    """
    Generate a new API key for a user.
    Returns the full key ONCE — after this it's only stored as a hash.
    """
    raw_key = KEY_PREFIX + secrets.token_urlsafe(32)
    key_hash = _hash_key(raw_key)

    doc_ref = db.collection(COLLECTION).document()
    key_data = {
        "user_id": user_id,
        "key_hash": key_hash,
        "label": label,
        "prefix": raw_key[:12],  # Store first 12 chars for display (sr_XXXXXXX)
        "created_at": datetime.now(timezone.utc),
        "last_used_at": None,
        "revoked": False,
    }
    doc_ref.set(key_data)

    # Return with raw key (only time it's visible)
    key_data["id"] = doc_ref.id
    key_data["raw_key"] = raw_key
    return key_data


def list_api_keys(db, user_id: str) -> list[dict]:
    """List all API keys for a user (active + revoked). Never returns the hash."""
    docs = (
        db.collection(COLLECTION)
        .where("user_id", "==", user_id)
        .order_by("created_at", direction="DESCENDING")
        .get()
    )
    keys = []
    for doc in docs:
        k = doc.to_dict()
        k["id"] = doc.id
        # Don't expose the hash
        k.pop("key_hash", None)
        keys.append(k)
    return keys


def get_user_by_api_key(db, raw_key: str) -> dict | None:
    """
    Look up a user by their raw API key.
    Hash the key, find the matching doc, return the user.
    """
    key_hash = _hash_key(raw_key)
    docs = (
        db.collection(COLLECTION)
        .where("key_hash", "==", key_hash)
        .where("revoked", "==", False)
        .limit(1)
        .get()
    )
    for doc in docs:
        key_data = doc.to_dict()
        # Update last_used_at
        doc.reference.update({"last_used_at": datetime.now(timezone.utc)})

        # Fetch the user
        from app.models.user import get_user_by_id
        return get_user_by_id(db, key_data["user_id"])

    return None


def revoke_api_key(db, key_id: str, user_id: str) -> bool:
    """Revoke an API key. Returns True if found and revoked."""
    doc = db.collection(COLLECTION).document(key_id).get()
    if not doc.exists:
        return False
    key_data = doc.to_dict()
    if key_data["user_id"] != user_id:
        return False
    doc.reference.update({"revoked": True})
    return True
