from datetime import datetime, timezone
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

COLLECTION = "users"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_user(db, email: str, password: str) -> dict:
    """Create a new user. Returns the user dict with id."""
    doc_ref = db.collection(COLLECTION).document()
    user_data = {
        "email": email.lower().strip(),
        "password_hash": hash_password(password),
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
