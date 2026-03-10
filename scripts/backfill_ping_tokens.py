"""
Backfill ping_token for existing heartbeat monitors.

Run once after deploying the ping_token feature to add a secure token
to all heartbeat monitors that were created before this feature existed.
Also updates their ping_url to include ?token=<token>.

Usage:
    cd /Applications/statusrooster
    source venv/bin/activate
    python scripts/backfill_ping_tokens.py [--dry-run]
"""

import sys
import secrets
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db
from app.config import settings

DRY_RUN = "--dry-run" in sys.argv


def main():
    db = get_db()
    print(f"{'[DRY RUN] ' if DRY_RUN else ''}Scanning heartbeat monitors for missing ping_token...\n")

    docs = (
        db.collection("monitors")
        .get()
    )

    updated = 0
    skipped = 0

    for doc in docs:
        m = doc.to_dict()
        monitor_id = doc.id
        name = m.get("name", monitor_id)

        # Only process heartbeat monitors
        if m.get("monitor_type") != "heartbeat":
            continue

        if m.get("ping_token"):
            print(f"  SKIP  {name} ({monitor_id}) — already has token")
            skipped += 1
            continue

        # Generate a new token and rebuild ping_url
        token = secrets.token_urlsafe(32)
        ping_url = f"{settings.APP_URL}/api/ping/{monitor_id}?token={token}"

        print(f"  {'WOULD UPDATE' if DRY_RUN else 'UPDATE'} {name} ({monitor_id})")
        print(f"           ping_url: {ping_url}")

        if not DRY_RUN:
            db.collection("monitors").document(monitor_id).update({
                "ping_token": token,
                "ping_url": ping_url,
                "url": ping_url,
            })
        updated += 1

    print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Done.")
    print(f"  Updated: {updated}")
    print(f"  Skipped (already had token): {skipped}")
    if DRY_RUN:
        print("\nRun without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
