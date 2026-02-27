# StatusRooster — End-to-End Testing Guide 🐓

**Purpose:** Walk through every feature manually, verify it works, and understand exactly what's happening in the backend at each step.

**Prerequisites:**
- Local server running (`uvicorn app.main:app --port 8080 --reload`)
- Browser open to `http://localhost:8080`
- Terminal open for checking Firestore/logs

---

## Test 1: Signup Flow

### What to do:
1. Go to `http://localhost:8080/signup`
2. Try submitting with mismatched passwords → should see error
3. Try submitting with a 5-character password → should see "at least 8 characters"
4. Fill in a real email + matching password (8+ chars) → submit

### What to verify:
- [ ] Error messages appear inline (red box, no page crash)
- [ ] On success, you're redirected to `/dashboard`
- [ ] Nav bar now shows "Dashboard" and "Log out" (not "Log in" / "Sign up free")

### What's happening in the backend:
```
POST /signup
  → pages.py: signup_submit()
  → Validates password match + length
  → models/user.py: get_user_by_email() — checks Firestore "users" collection
  → models/user.py: create_user() — bcrypt hashes password, writes to Firestore
  → services/auth.py: create_access_token() — creates JWT with user_id + email, 72hr expiry
  → Sets httpOnly cookie "access_token" with the JWT
  → 302 redirect → /dashboard
```

**Firestore check:** After signup, a new doc exists in `users` collection with:
- `email`, `password_hash` (bcrypt), `plan: "free"`, `monitors_count: 0`, `created_at`

---

## Test 2: Logout + Login Flow

### What to do:
1. Click "Log out" in the nav
2. Try visiting `http://localhost:8080/dashboard` directly → should redirect to `/login`
3. Try logging in with wrong password → should see error
4. Log in with correct credentials → should land on `/dashboard`

### What to verify:
- [ ] Logout clears the cookie and sends you to `/login`
- [ ] `/dashboard` is protected — redirects to `/login` when not authenticated
- [ ] Wrong password shows "Invalid email or password" (doesn't reveal which field is wrong — security!)
- [ ] Successful login redirects to `/dashboard`

### What's happening in the backend:
```
GET /logout
  → Deletes "access_token" cookie
  → 302 redirect → /login

GET /dashboard (no cookie)
  → pages.py: get_user_from_cookie() returns None
  → 302 redirect → /login

POST /login
  → models/user.py: get_user_by_email() — finds user in Firestore
  → models/user.py: verify_password() — bcrypt compares plain text vs stored hash
  → services/auth.py: create_access_token() — new JWT
  → Sets cookie, 302 → /dashboard
```

**Security note:** The error says "Invalid email or password" for BOTH wrong email and wrong password. This prevents attackers from discovering which emails are registered.

---

## Test 3: Add a Monitor

### What to do:
1. On the dashboard, click "+ Add Monitor"
2. Fill in:
   - **URL:** `https://httpstat.us/200` (a test URL that always returns 200)
   - **Name:** `Always Up Test`
   - **Alert Email:** your email (pre-filled)
   - **Slack Webhook:** leave blank for now
3. Click "Add Monitor →"

### What to verify:
- [ ] Green flash message appears: "Monitor 'Always Up Test' added!"
- [ ] Monitor card appears with ⚪ (pending) status badge
- [ ] URL and name are displayed on the card
- [ ] Uptime shows 100%, Response shows "—" (no checks yet)

### What's happening in the backend:
```
POST /monitors/add
  → pages.py: add_monitor()
  → get_user_from_cookie() — validates JWT from cookie
  → list_monitors_by_user() — counts existing monitors for plan enforcement (< 5 for free)
  → Prepends "https://" if missing
  → models/monitor.py: create_monitor()
      → generate_slug() — creates URL-safe slug like "always-up-test-a3f2c1"
      → Writes to Firestore "monitors" collection:
        {user_id, url, name, status: "pending", slug, alert_email, 
         uptime_percent: 100, checks_total: 0, checks_failed: 0, ...}
  → 302 redirect → /dashboard with flash message in query params
```

**Firestore check:** New doc in `monitors` collection. Status is `"pending"` because no check has run yet.

---

## Test 4: Add a Second Monitor (one that will go DOWN)

### What to do:
1. Click "+ Add Monitor" again
2. Fill in:
   - **URL:** `https://httpstat.us/500` (always returns 500 Internal Server Error)
   - **Name:** `Always Down Test`
   - **Alert Email:** your email
3. Click "Add Monitor →"

### What to verify:
- [ ] Flash message confirms it was added
- [ ] Now you have 2 monitor cards, both showing ⚪ pending

### Why this matters:
This monitor will trigger the DOWN alert flow when the cron checker runs. You'll see the full incident lifecycle play out.

---

## Test 5: Watch the Cron Checker Run

### What to do:
1. In your terminal, manually trigger the cron check:
```bash
curl -X POST http://localhost:8080/cron/check \
  -H "X-Cron-Secret: temp-change-me-later"
```
2. Watch the terminal where uvicorn is running for log output
3. Refresh the dashboard in your browser

### What to verify:
- [ ] Curl returns JSON: `{"status": "completed", "results": {"total": 2, "up": 1, "down": 1}}`
- [ ] Server logs show:
  - `[checker] INCIDENT CREATED: Always Down Test is DOWN`
  - `[alert] Email sent to [your email]`
- [ ] Dashboard now shows:
  - `Always Up Test` → 🟢 Up, with response time in ms
  - `Always Down Test` → 🔴 Down
- [ ] You receive a DOWN alert email from `alerts@statusrooster.com`

### What's happening in the backend:
```
POST /cron/check
  → routers/cron.py: cron_check()
  → Verifies X-Cron-Secret header matches JWT_SECRET
  → services/checker.py: run_checks()
      → models/monitor.py: get_all_monitors() — fetches ALL monitors across ALL users
      → For each monitor:
          → check_url_with_retry(url)
              → HTTP GET with 10s timeout
              → If DOWN: wait 5s, retry once (false positive prevention!)
              → Returns {status_code, response_ms, is_up}
          → models/check.py: create_check() — writes to "checks" collection
          → Updates monitor doc: status, last_checked, response_ms, uptime%
          → STATUS CHANGE DETECTION:
              Previous = "pending", New = "down"? → status_changed = True
              → models/incident.py: get_open_incident() — dedup check (none exists)
              → models/incident.py: create_incident() — writes to "incidents" collection
              → services/alerts.py: send_down_alert()
                  → send_email() via SendGrid API
                  → send_slack() via webhook (if configured)
```

**Key concept — False Positive Prevention:** If a URL fails the first check, the checker waits 5 seconds and tries again before marking it as DOWN. This prevents alerts from transient network blips.

**Key concept — Alert Deduplication:** Before creating an incident, it checks `get_open_incident()`. If one already exists for this monitor, it skips alerting. This means you only get ONE "site is down" email, not one every 60 seconds.

---

## Test 6: Monitor Detail View + Chart

### What to do:
1. Click on the "Always Up Test" monitor card on the dashboard
2. Look at the detail page

### What to verify:
- [ ] Status banner shows "🟢 Currently UP — all good!"
- [ ] Stats grid shows: Uptime %, Last Response (ms), Total Checks, Status Code (200)
- [ ] Response Time chart has at least 1 data point
- [ ] Alert Settings section shows your email as "active" (green)
- [ ] Slack shows "Not configured" (gray italic)
- [ ] Recent Incidents section shows "No incidents recorded yet. 🎉"

### Now check the "Always Down Test" monitor:
3. Go back to dashboard, click on "Always Down Test"

### What to verify:
- [ ] Status banner shows "🔴 Currently DOWN — we're alerting you"
- [ ] Status Code shows 500
- [ ] Recent Incidents shows one "🔴 Ongoing" incident with timestamp

### What's happening in the backend:
```
GET /monitors/{monitor_id}
  → pages.py: monitor_detail()
  → get_user_from_cookie() — auth check
  → get_monitor() — fetches monitor doc, verifies user_id matches (ownership check!)
  → models/check.py: get_recent_checks(limit=1440) — last 24h of checks
  → models/incident.py: list_incidents_by_monitor(limit=10) — recent incidents
  → Renders template with Chart.js consuming the checks data as JSON
```

**Key concept — Ownership check:** Every monitor route verifies `monitor["user_id"] != user["id"]`. User A can never see or modify User B's monitors, even if they guess the monitor ID.

---

## Test 7: Edit a Monitor

### What to do:
1. On the dashboard, click the ✏️ edit button on "Always Up Test"
2. Change the name to "StatusRooster Health"
3. Click "Save Changes →"

### What to verify:
- [ ] Edit form is pre-filled with current values
- [ ] After save, flash message shows "Monitor 'StatusRooster Health' updated!"
- [ ] Monitor card on dashboard now shows the new name

### What's happening:
```
GET /monitors/{id}/edit → loads monitor from Firestore, renders form
POST /monitors/{id}/edit → updates monitor doc with new field values
```

---

## Test 8: Run Cron Again — Observe Recovery

### What to do:
1. First, edit "Always Down Test" and change its URL to `https://httpstat.us/200`
2. Now trigger the cron check again:
```bash
curl -X POST http://localhost:8080/cron/check \
  -H "X-Cron-Secret: temp-change-me-later"
```
3. Watch the uvicorn logs
4. Refresh the dashboard

### What to verify:
- [ ] Server logs show: `[checker] INCIDENT RESOLVED: Always Down Test is UP (down for Xs)`
- [ ] Server logs show: `[alert] Email sent` (recovery email)
- [ ] Dashboard: "Always Down Test" now shows 🟢 Up
- [ ] You receive a RECOVERY email from `alerts@statusrooster.com`
- [ ] Monitor detail page → incident now shows "✅ Resolved" with duration

### What's happening in the backend:
```
Status change: "down" → "up"
  → models/incident.py: get_open_incident() — finds the open incident
  → models/incident.py: resolve_incident()
      → Sets resolved_at = now
      → Calculates duration_seconds = resolved_at - started_at
      → Updates incident status to "resolved"
  → services/alerts.py: send_recovery_alert()
      → Formats duration as human-readable (e.g., "2m 30s")
      → Sends email + Slack with recovery details
```

**Key concept — Incident lifecycle:** `open` → `resolved`. Duration is calculated automatically. This data feeds into status pages later (Day 5).

---

## Test 9: Delete a Monitor

### What to do:
1. On the dashboard, click the 🗑️ delete button on "Always Down Test"
2. Confirm the browser dialog

### What to verify:
- [ ] Confirmation dialog appears: "Delete Always Down Test? This cannot be undone."
- [ ] After confirming, flash message: "Monitor 'Always Down Test' deleted"
- [ ] Monitor is gone from dashboard
- [ ] Only 1 monitor remains

### What's happening:
```
POST /monitors/{id}/delete
  → models/monitor.py: delete_monitor()
      → Deletes all docs in "checks" collection where monitor_id matches
      → Deletes all docs in "incidents" collection where monitor_id matches
      → Deletes the monitor doc itself
  → Cascade delete! No orphaned data left in Firestore.
```

---

## Test 10: Plan Enforcement (Free Tier Limit)

### What to do:
1. Add monitors until you have 5 total (you have 1 now, so add 4 more)
   - Use any URLs: `https://google.com`, `https://github.com`, etc.
2. Try to add a 6th monitor

### What to verify:
- [ ] First 5 monitors all save successfully
- [ ] 6th attempt shows error flash: "Free plan limited to 5 monitors. Upgrade to Pro!"
- [ ] No 6th monitor is created

### What's happening:
```
POST /monitors/add
  → list_monitors_by_user() — counts current monitors
  → user.plan == "free" AND count >= 5?
  → 302 redirect with error flash message
  → Monitor is NOT created
```

**Business logic:** This is the paywall. Free = 5 monitors max. Pro = unlimited (coming Day 6 with Stripe).

---

## Test 11: Auth Protection

### What to do:
1. Open an incognito/private browser window
2. Try visiting these URLs directly:
   - `http://localhost:8080/dashboard`
   - `http://localhost:8080/monitors/add`
   - `http://localhost:8080/monitors/some-fake-id`

### What to verify:
- [ ] All redirect to `/login` — no data leak, no errors
- [ ] After logging in, you land on `/dashboard` (not the originally requested page — that's a Day 8 improvement)

### What's happening:
Every protected route calls `get_user_from_cookie()` first. If it returns `None`, instant redirect to `/login`. No Firestore queries, no data exposure.

---

## Test 12: Duplicate Signup Prevention

### What to do:
1. Go to `/signup`
2. Try signing up with the same email you already used

### What to verify:
- [ ] Error message: "Email already registered"
- [ ] No duplicate user created in Firestore

---

## Cleanup After Testing

Delete the test monitors you created (keep your dashboard clean):
1. Delete all test monitors from the dashboard (🗑️ button on each)
2. Or keep 1-2 real ones you want to actually monitor

---

## Quick Reference: Data Flow Architecture

```
User Browser
    ↓ (HTTP requests with cookie)
FastAPI (pages.py) ← renders HTML templates
    ↓
Firestore (users, monitors, checks, incidents)
    
Cloud Scheduler (every 60s)
    ↓ POST /cron/check
FastAPI (cron.py → checker.py)
    ↓ HTTP GET each monitor URL
    ↓ Write check results
    ↓ Detect status changes
    ↓ Create/resolve incidents
    ↓
Alert Service (alerts.py)
    ├→ SendGrid API (email)
    ├→ Slack Webhook (message)
    └→ SMS (placeholder)
```

## Firestore Collections

| Collection | Purpose | Key Fields |
|-----------|---------|------------|
| `users` | User accounts | email, password_hash, plan, monitors_count |
| `monitors` | URLs being watched | user_id, url, name, status, uptime_percent, slug |
| `checks` | Individual check results | monitor_id, timestamp, status_code, response_ms, is_up |
| `incidents` | Downtime events | monitor_id, status (open/resolved), started_at, resolved_at, duration_seconds |

---

**After completing all 12 tests, you've verified the entire Day 1-4 feature set.** 🐓
