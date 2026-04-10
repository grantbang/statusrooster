"""
Delete check records older than the retention period (90 days for all plans).

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

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.DATA_RETENTION_DAYS)

    # Get all monitor IDs
    monitors = db.collection("monitors").stream()
    monitor_ids = [doc.id for doc in monitors]

    if not monitor_ids:
        return {"total_deleted": 0}

    deleted = 0
    # Process in chunks of 30 (Firestore 'in' query limit)
    for i in range(0, len(monitor_ids), 30):
        chunk = monitor_ids[i:i + 30]
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

    summary = {"total_deleted": deleted}
    logger.info(f"[cleanup] {'DRY RUN ' if dry_run else ''}Deleted {deleted} old checks "
                f"(>{settings.DATA_RETENTION_DAYS}d)")
    return summary


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    prefix = "[DRY RUN] " if DRY_RUN else ""
    print(f"{prefix}Cleaning up old check records...\n")

    summary = cleanup_old_checks(dry_run=DRY_RUN)

    print(f"\n{prefix}Done.")
    print(f"  Checks deleted (>{settings.DATA_RETENTION_DAYS}d): {summary['total_deleted']}")

    if DRY_RUN:
        print("\nRun without --dry-run to actually delete.")


if __name__ == "__main__":
    main()
