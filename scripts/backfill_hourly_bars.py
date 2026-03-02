"""
Backfill hourly_uptime_bars on all monitor documents.

Reads the last 24 hours of checks from Firestore,
buckets by hour, and writes the pre-computed array
to each monitor doc — same format the checker uses
for incremental updates.

Usage:
    python -m scripts.backfill_hourly_bars
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone, timedelta
from app.database import get_db

def main():
    db = get_db()
    monitors = db.collection("monitors").get()
    monitor_list = [(doc.id, doc.to_dict()) for doc in monitors]
    print(f"Found {len(monitor_list)} monitors")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    for mid, monitor in monitor_list:
        name = monitor.get("name", mid)
        print(f"\n--- {name} ({mid}) ---")

        # Fetch checks for last 24h
        docs = (
            db.collection("checks")
            .where("monitor_id", "==", mid)
            .where("timestamp", ">=", cutoff)
            .order_by("timestamp")
            .get()
        )
        checks = [d.to_dict() for d in docs]
        print(f"  {len(checks)} checks in last 24h")

        # Bucket by hour
        buckets = {}
        for c in checks:
            ts = c.get("timestamp")
            if not ts:
                continue
            hour_key = ts.strftime("%Y-%m-%d-%H")
            if hour_key not in buckets:
                buckets[hour_key] = {"hour": hour_key, "total": 0, "up": 0}
            buckets[hour_key]["total"] += 1
            if c.get("is_up"):
                buckets[hour_key]["up"] += 1

        # Build sorted array
        hbars = sorted(buckets.values(), key=lambda b: b["hour"])
        print(f"  {len(hbars)} hourly buckets")

        # Write to monitor doc
        db.collection("monitors").document(mid).update({
            "hourly_uptime_bars": hbars,
        })
        print(f"  ✅ Written")

    print(f"\n🎉 Backfill complete for {len(monitor_list)} monitors")

if __name__ == "__main__":
    main()
