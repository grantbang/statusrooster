"""
Seed demo data for testaccount1@statusrooster.com (user_id: eydllii8PyTWHyi4BlmL)

Creates:
  - 6 monitors (various states: up, down, paused, mixed uptime)
  - ~30 days of check history per monitor with realistic failure patterns
  - Several incidents (resolved + 1 ongoing)

Run:  cd /Applications/statusrooster && source venv/bin/activate && python scripts/seed_demo_data.py
"""

import sys, os, random
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_db
from app.models.monitor import generate_slug

USER_ID = "eydllii8PyTWHyi4BlmL"
NOW = datetime.now(timezone.utc)

# ── Monitor definitions ──────────────────────────────────────────────
MONITORS = [
    {
        "name": "StatusRooster Landing",
        "url": "https://statusrooster.com",
        "status": "up",
        "paused": False,
        "uptime_profile": "healthy",       # 99.9%+ uptime
        "alert_email": "testaccount1@statusrooster.com",
    },
    {
        "name": "API Server",
        "url": "https://api.statusrooster.com/health",
        "status": "up",
        "paused": False,
        "uptime_profile": "minor_issues",  # 98-99% — a few blips
        "alert_email": "testaccount1@statusrooster.com",
        "keyword": "ok",
    },
    {
        "name": "Blog (WordPress)",
        "url": "https://blog.statusrooster.com",
        "status": "down",
        "paused": False,
        "uptime_profile": "degraded",      # 92-96% — recent outage
        "alert_email": "testaccount1@statusrooster.com",
    },
    {
        "name": "Staging Environment",
        "url": "https://staging.statusrooster.com",
        "status": "up",
        "paused": True,
        "uptime_profile": "healthy",
        "alert_email": "",
    },
    {
        "name": "Payment Gateway",
        "url": "https://pay.statusrooster.com/ping",
        "status": "up",
        "paused": False,
        "uptime_profile": "minor_issues",
        "alert_email": "testaccount1@statusrooster.com",
        "response_threshold_ms": "> 2000",
    },
    {
        "name": "Documentation Site",
        "url": "https://docs.statusrooster.com",
        "status": "up",
        "paused": False,
        "uptime_profile": "healthy",
        "alert_email": "testaccount1@statusrooster.com",
        "keyword": "Getting Started",
    },
]

# ── Uptime profile configs ───────────────────────────────────────────
PROFILES = {
    "healthy": {
        # Very reliable — maybe 1 brief blip in 30 days
        "daily_fail_chance": 0.02,       # 2% chance a given day has any failures
        "fail_ratio_range": (0.005, 0.01),  # When failing, only 0.5-1% of checks fail
    },
    "minor_issues": {
        # Mostly fine but occasional issues
        "daily_fail_chance": 0.15,
        "fail_ratio_range": (0.01, 0.05),
    },
    "degraded": {
        # Noticeably unreliable, especially recently
        "daily_fail_chance": 0.35,
        "fail_ratio_range": (0.03, 0.15),
        "recent_outage": True,  # Force a multi-hour outage in last 2 days
    },
}


def build_checks_for_day(monitor_id: str, day_date, profile_name: str,
                         check_interval: int, force_down_hours: list | None = None):
    """Generate check records for one monitor on one day."""
    profile = PROFILES[profile_name]
    checks = []
    
    # Number of checks per day based on interval
    checks_per_day = (24 * 3600) // check_interval
    
    # Determine if this day has failures
    has_failures = random.random() < profile["daily_fail_chance"]
    fail_ratio = 0.0
    if has_failures:
        lo, hi = profile["fail_ratio_range"]
        fail_ratio = random.uniform(lo, hi)
    
    for i in range(checks_per_day):
        ts = datetime(day_date.year, day_date.month, day_date.day,
                      tzinfo=timezone.utc) + timedelta(seconds=i * check_interval)
        
        # Don't create checks in the future
        if ts > NOW:
            break
        
        hour = ts.hour
        
        # Check if this specific hour is forced down
        is_forced_down = force_down_hours and hour in force_down_hours
        
        if is_forced_down:
            is_up = False
        elif has_failures:
            is_up = random.random() > fail_ratio
        else:
            is_up = True
        
        if is_up:
            status_code = 200
            response_ms = round(random.gauss(180, 60), 1)
            response_ms = max(45, min(response_ms, 800))
        else:
            status_code = random.choice([0, 500, 502, 503, 504, 522, None])
            response_ms = round(random.gauss(5000, 2000), 1) if status_code else None
        
        checks.append({
            "monitor_id": monitor_id,
            "timestamp": ts,
            "status_code": status_code,
            "response_ms": response_ms,
            "is_up": is_up,
        })
    
    return checks


def seed():
    db = get_db()
    print("🐓 StatusRooster Demo Data Seeder")
    print(f"   User: {USER_ID}")
    print(f"   Time: {NOW.isoformat()}")
    print()

    created_monitors = []

    # ── 1. Create monitors ────────────────────────────────────────────
    print("📡 Creating monitors...")
    for mdef in MONITORS:
        doc_ref = db.collection("monitors").document()
        slug = generate_slug(mdef["name"])
        
        # Pick a last_status_change time
        if mdef["status"] == "down":
            last_status_change = NOW - timedelta(hours=random.randint(1, 4))
        elif mdef.get("paused"):
            last_status_change = NOW - timedelta(days=random.randint(3, 10))
        else:
            last_status_change = NOW - timedelta(days=random.randint(1, 15))

        monitor_data = {
            "user_id": USER_ID,
            "url": mdef["url"],
            "name": mdef["name"],
            "check_interval": 60,  # Pro account
            "status": mdef["status"],
            "paused": mdef.get("paused", False),
            "last_checked": NOW - timedelta(seconds=random.randint(10, 55)),
            "last_status_code": 200 if mdef["status"] == "up" else 503,
            "last_response_ms": round(random.gauss(180, 40), 1) if mdef["status"] == "up" else None,
            "last_status_change": last_status_change,
            "uptime_percent": 100.0,  # Will be recalculated
            "checks_total": 0,
            "checks_failed": 0,
            "alert_email": mdef.get("alert_email", ""),
            "alert_slack_webhook": "",
            "alert_sms": "",
            "keyword": mdef.get("keyword", ""),
            "response_threshold_ms": mdef.get("response_threshold_ms"),
            "webhook_url": "",
            "ssl_expiry": (NOW + timedelta(days=random.randint(30, 365))).isoformat() if "https" in mdef["url"] else None,
            "ssl_issuer": random.choice(["Let's Encrypt", "DigiCert", "Cloudflare"]),
            "ssl_expiry_alerted_days": None,
            "maintenance_windows": [],
            "public": random.choice([True, False]),
            "slug": slug,
            "created_at": NOW - timedelta(days=32),
        }
        doc_ref.set(monitor_data)
        monitor_data["id"] = doc_ref.id
        monitor_data["_profile"] = mdef["uptime_profile"]
        created_monitors.append(monitor_data)
        status_label = "⏸ paused" if mdef.get("paused") else ("🔴 down" if mdef["status"] == "down" else "🟢 up")
        print(f"   ✓ {mdef['name']} ({status_label}) → {doc_ref.id}")

    print()

    # ── 2. Create checks (30 days of history) ────────────────────────
    print("📊 Generating 30 days of check history...")
    total_checks = 0
    today = NOW.date()
    
    for mon in created_monitors:
        mid = mon["id"]
        profile = mon["_profile"]
        
        all_checks = []
        checks_up = 0
        checks_total = 0
        
        for day_offset in range(30, -1, -1):
            day = today - timedelta(days=day_offset)
            
            # For "degraded" profile, force outage in last 2 days
            force_down_hours = None
            if profile == "degraded" and day_offset <= 1:
                # 3-6 hour outage block
                start_hour = random.randint(2, 14)
                length = random.randint(3, 6)
                force_down_hours = list(range(start_hour, min(start_hour + length, 24)))
            
            day_checks = build_checks_for_day(mid, day, profile, 60, force_down_hours)
            all_checks.extend(day_checks)
        
        # Write checks in batches (Firestore batch limit = 500)
        batch_size = 450
        for i in range(0, len(all_checks), batch_size):
            batch = db.batch()
            for check in all_checks[i:i + batch_size]:
                ref = db.collection("checks").document()
                batch.set(ref, check)
                checks_total += 1
                if check["is_up"]:
                    checks_up += 1
            batch.commit()
        
        # Update monitor uptime stats
        uptime_pct = round((checks_up / checks_total) * 100, 3) if checks_total > 0 else 100.0
        db.collection("monitors").document(mid).update({
            "uptime_percent": uptime_pct,
            "checks_total": checks_total,
            "checks_failed": checks_total - checks_up,
        })
        
        total_checks += len(all_checks)
        print(f"   ✓ {mon['name']}: {len(all_checks)} checks, {uptime_pct}% uptime")

    print(f"   Total checks created: {total_checks}")
    print()

    # ── 3. Create incidents ───────────────────────────────────────────
    print("🚨 Creating incidents...")
    
    incidents = [
        # Resolved incident — Blog went down 2 days ago for 3 hours
        {
            "monitor": next(m for m in created_monitors if "Blog" in m["name"]),
            "status": "resolved",
            "started_at": NOW - timedelta(days=2, hours=6),
            "duration_seconds": 3 * 3600 + 22 * 60,  # 3h 22m
            "status_code": 502,
            "response_ms": None,
        },
        # Resolved incident — API had a blip 5 days ago for 12 min
        {
            "monitor": next(m for m in created_monitors if "API" in m["name"]),
            "status": "resolved",
            "started_at": NOW - timedelta(days=5, hours=3),
            "duration_seconds": 12 * 60 + 34,  # 12m 34s
            "status_code": 503,
            "response_ms": 8200,
        },
        # Resolved incident — Payment Gateway had slow responses 8 days ago
        {
            "monitor": next(m for m in created_monitors if "Payment" in m["name"]),
            "status": "resolved",
            "started_at": NOW - timedelta(days=8, hours=14),
            "duration_seconds": 45 * 60 + 12,  # 45m 12s
            "status_code": 504,
            "response_ms": 15000,
        },
        # Resolved incident — Blog had another outage 12 days ago
        {
            "monitor": next(m for m in created_monitors if "Blog" in m["name"]),
            "status": "resolved",
            "started_at": NOW - timedelta(days=12, hours=20),
            "duration_seconds": 1 * 3600 + 5 * 60,  # 1h 5m
            "status_code": 500,
            "response_ms": None,
        },
        # OPEN incident — Blog is currently down
        {
            "monitor": next(m for m in created_monitors if "Blog" in m["name"]),
            "status": "open",
            "started_at": NOW - timedelta(hours=2, minutes=47),
            "duration_seconds": None,
            "status_code": 503,
            "response_ms": None,
        },
    ]

    for inc_def in incidents:
        mon = inc_def["monitor"]
        doc_ref = db.collection("incidents").document()
        
        started_at = inc_def["started_at"]
        resolved_at = None
        if inc_def["status"] == "resolved":
            resolved_at = started_at + timedelta(seconds=inc_def["duration_seconds"])
        
        incident_data = {
            "monitor_id": mon["id"],
            "monitor_name": mon["name"],
            "monitor_url": mon["url"],
            "status": inc_def["status"],
            "status_code": inc_def["status_code"],
            "response_ms": inc_def["response_ms"],
            "started_at": started_at,
            "resolved_at": resolved_at,
            "duration_seconds": inc_def["duration_seconds"],
        }
        doc_ref.set(incident_data)
        
        badge = "🔴 OPEN" if inc_def["status"] == "open" else "✅ resolved"
        duration_str = ""
        if inc_def["duration_seconds"]:
            h = inc_def["duration_seconds"] // 3600
            m = (inc_def["duration_seconds"] % 3600) // 60
            s = inc_def["duration_seconds"] % 60
            duration_str = f" ({h}h {m}m {s}s)"
        print(f"   ✓ {mon['name']} — {badge}{duration_str}")

    # ── 4. Update user monitors_count ─────────────────────────────────
    existing_count = len(db.collection("monitors").where("user_id", "==", USER_ID).get())
    db.collection("users").document(USER_ID).update({"monitors_count": existing_count})
    print(f"\n📋 Updated monitors_count to {existing_count}")

    print()
    print("═" * 50)
    print("✅ Demo data seeded successfully!")
    print(f"   {len(created_monitors)} monitors")
    print(f"   {total_checks} checks (30 days)")
    print(f"   {len(incidents)} incidents ({sum(1 for i in incidents if i['status']=='open')} open)")
    print("═" * 50)


if __name__ == "__main__":
    seed()
