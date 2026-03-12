"""
Delete check records older than the retention period for each monitor's owner plan.

Free plan: 30 days retention
Pro plan: 90 days retention

Uses Firestore batch deletes (500 per batch) for efficiency.
Can be run standalone or called from the /cron/cleanup endpoint.

Usage:
    cd /Applications/statusrooster
    source venv/bin/activate
    python scripts/cleanup_old_checks.py [--dry-run]
"""

import sys
import os
import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)
DRY_RUN = "--dry-run" in sys.argv

BATCH_SIZE = 500


def cleanup_old_checks(dry_run: bool = False) -> dict:
    """Delete checks older than retention period. Returns summary stats."""
    db = get_db()

    # Build a map of user_id -> plan
    user_plans = {}

    # Get all monitors to determine owner plans
    monitors = db.collection("monitors").stream()
    monitor_owners = {}  # monitor_id -> user_id
    for doc in monitors:
        m = doc.to_dict()
        mid = doc.id
        uid = m.get("user_id", "")
        monitor_owners[mid] = uid
        if uid and uid not in user_plans:
            user_doc = db.collection("users").document(uid).get()
            if user_doc.exists:
                user_plans[uid] = user_doc.to_dict().get("plan", "free")
            else:
                user_plans[uid] = "free"

    # Calculate cutoffs
    free_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.FREE_DATA_RETENTION_DAYS)
    pro_cutoff = datetime.now(timezone.utc) - timedelta(days=settings.PRO_DATA_RETENTION_DAYS)

    # Delete old checks for free users (older than 30 days)
    deleted_free = _delete_checks_before(db, monitor_owners, user_plans, free_cutoff, "free", dry_run)

    # Delete old checks for pro users (older than 90 days)
    deleted_pro = _delete_checks_before(db, monitor_owners, user_plans, pro_cutoff, "pro", dry_run)

    summary = {
        "deleted_free": deleted_free,
        "deleted_pro": deleted_pro,
        "total_deleted": deleted_free + deleted_pro,
    }
    logger.info(f"[cleanup] {'DRY RUN ' if dry_run else ''}Deleted {summary['total_deleted']} old checks "
                f"(free: {deleted_free}, pro: {deleted_pro})")
    return summary


def _delete_checks_before(db, monitor_owners, user_plans, cutoff, plan, dry_run):
    """Delete checks older than cutoff for monitors owned by users on the given plan."""
    # Get monitor IDs for this plan
    target_mids = [
        mid for mid, uid in monitor_owners.items()
        if user_plans.get(uid, "free") == plan
    ]

    if not target_mids:
        return 0

    deleted = 0
    # Process in chunks of 30 (Firestore 'in' query limit)
    for i in range(0, len(target_mids), 30):
        chunk = target_mids[i:i + 30]
        docs = (
            db.collection("checks")
            .where("monitor_id", "in", chunk)
            .where("timestamp", "<", cutoff)
            .limit(BATCH_SIZE)
            .stream()
        )

        batch = db.batch()
        count = 0
        for doc in docs:
            if not dry_run:
                batch.delete(doc.reference)
            count += 1
            if count >= BATCH_SIZE:
                break

        if count > 0 and not dry_run:
            batch.commit()
        deleted += count

    return deleted


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    prefix = "[DRY RUN] " if DRY_RUN else ""
    print(f"{prefix}Cleaning up old check records...\n")

    summary = cleanup_old_checks(dry_run=DRY_RUN)

    print(f"\n{prefix}Done.")
    print(f"  Free plan checks deleted (>{settings.FREE_DATA_RETENTION_DAYS}d): {summary['deleted_free']}")
    print(f"  Pro plan checks deleted (>{settings.PRO_DATA_RETENTION_DAYS}d): {summary['deleted_pro']}")
    print(f"  Total: {summary['total_deleted']}")

    if DRY_RUN:
        print("\nRun without --dry-run to actually delete.")


if __name__ == "__main__":
    main()
