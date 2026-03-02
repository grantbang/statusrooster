"""
Backfill daily_uptime_bars on all monitor documents from existing check data.

This reads the last 30 days of checks for each monitor and writes a
pre-computed daily_uptime_bars array to the monitor doc so the dashboard
can load instantly without scanning the checks collection.

Run:  cd /Applications/statusrooster && source venv/bin/activate && python scripts/backfill_daily_bars.py
"""

import sys, os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db

db = get_db()

DAYS = 30
cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS)
today = datetime.now(timezone.utc).date()

# Get all monitors
monitors = [doc.to_dict() | {"id": doc.id} for doc in db.collection("monitors").stream()]
print(f"Found {len(monitors)} monitors")

for monitor in monitors:
    mid = monitor["id"]
    print(f"\n  Processing {monitor.get('name', mid)} ({mid})...")

    # Query checks for this monitor in the last 30 days
    docs = (
        db.collection("checks")
        .where("monitor_id", "==", mid)
        .where("timestamp", ">=", cutoff)
        .order_by("timestamp")
        .get()
    )

    # Bucket by date
    buckets: dict[str, dict] = {}
    for doc in docs:
        c = doc.to_dict()
        ts = c.get("timestamp")
        if not ts:
            continue
        day_key = ts.strftime("%Y-%m-%d")
        if day_key not in buckets:
            buckets[day_key] = {"date": day_key, "total": 0, "up": 0}
        buckets[day_key]["total"] += 1
        if c.get("is_up"):
            buckets[day_key]["up"] += 1

    # Build array oldest → newest
    bars = []
    for i in range(DAYS - 1, -1, -1):
        d = today - timedelta(days=i)
        day_key = d.isoformat()
        if day_key in buckets:
            bars.append(buckets[day_key])
        # skip days with no data — checker will fill them going forward

    print(f"    {len(docs)} checks → {len(bars)} days with data")

    # Write to monitor doc
    db.collection("monitors").document(mid).update({"daily_uptime_bars": bars})
    print(f"    ✅ Updated monitor doc")

print("\n✅ Backfill complete!")
