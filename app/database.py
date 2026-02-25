from google.cloud import firestore
from app.config import settings

_db = None


def get_db() -> firestore.Client:
    """Returns a singleton Firestore client."""
    global _db
    if _db is None:
        _db = firestore.Client(project=settings.GCP_PROJECT_ID)
    return _db
