# StatusRooster — E2E Test Plan

**Created:** March 10, 2026
**Purpose:** Comprehensive, manual, click-by-click testing of every feature before launch.
**Target Environment:** Production — `https://statusrooster.com`
**Test Account:** `testaccount1@statusrooster.com` / `password` (Pro plan)

---

## Test Infrastructure

### Controlled Test Targets

We use real endpoints on `statusrooster.com` to test against, plus external services we control. This creates a closed loop — StatusRooster monitoring itself.

| Target | URL | Purpose |
|--------|-----|---------|
| **SR Landing (always up)** | `https://statusrooster.com` | HTTP monitor — should always be UP |
| **SR Health endpoint** | `https://statusrooster.com/api/v1/monitors` | JSON/API monitor — returns JSON |
| **Google (always up)** | `https://www.google.com` | HTTP baseline — reliable UP |
| **httpstat.us (controllable errors)** | `https://httpstat.us/200` | Returns any status code on demand |
| **httpstat.us 500** | `https://httpstat.us/500` | Simulates server error → DOWN |
| **httpstat.us 503** | `https://httpstat.us/503` | Simulates service unavailable → DOWN |
| **httpstat.us timeout** | `https://httpstat.us/200?sleep=15000` | 15s delay → triggers timeout |
| **httpbin.org** | `https://httpbin.org` | Echo service for headers, auth, POST, etc. |
| **expired.badssl.com** | `https://expired.badssl.com` | SSL cert is expired → SSL DOWN |
| **StatusRooster SSL** | `statusrooster.com` | SSL monitor — valid cert |
| **Heartbeat (self-ping)** | *(auto-generated)* | We'll curl the ping URL manually |

### How to Simulate Failures

| Scenario | How |
|----------|-----|
| **HTTP 500 error** | Monitor `https://httpstat.us/500` |
| **HTTP 503 error** | Monitor `https://httpstat.us/503` |
| **Timeout** | Monitor `https://httpstat.us/200?sleep=15000` with timeout=5s |
| **SSL expired** | Monitor SSL for `expired.badssl.com` |
| **SSL expiring soon** | Monitor SSL for `statusrooster.com` — set threshold to 999 days so it triggers "warn" |
| **Heartbeat overdue** | Create heartbeat monitor with 60s interval, just never ping it |
| **Keyword missing** | Monitor `https://httpstat.us/200` with keyword `BANANA` (not in the response) |
| **Response too slow** | Monitor `https://httpstat.us/200?sleep=3000` with threshold `> 1000` |
| **JSON assertion fail** | Monitor `https://httpbin.org/json` with assertion `slideshow.title` equals `WRONG` |
| **Expected status mismatch** | Monitor `https://httpstat.us/201` with expected status = 200 |
| **Recovery** | Switch a DOWN monitor's URL from `httpstat.us/500` to `httpstat.us/200` via Edit |

---

## Phase 0: Pre-Flight Checklist

Before testing, verify the environment is ready.

- [ ] **0.1** Production is deployed — `curl -s -o /dev/null -w '%{http_code}' https://statusrooster.com` → `200`
- [ ] **0.2** Cron is running — check admin dashboard (`/admin`) → "Last check" < 2 min ago
- [ ] **0.3** Stripe is in **test mode** (we will NOT test live Stripe until final launch)
- [ ] **0.4** Test account exists — login at `https://statusrooster.com/login` with `testaccount1@statusrooster.com` / `password`
- [ ] **0.5** Test account is Pro plan — dashboard should show Pro badge / no plan limits
- [ ] **0.6** All monitors are deleted (clean slate) — dashboard shows empty state
- [ ] **0.7** Twilio A2P campaign approved *(optional — skip SMS tests if still pending)*

---

## Phase 1: Authentication & Account

### 1A — Signup (new user)

- [ ] **1A.1** Go to `https://statusrooster.com/signup`
- [ ] **1A.2** Sign up with a NEW email (e.g. `e2etest-MMDD@statusrooster.com` / `testpass123`)
- [ ] **1A.3** ✅ Redirects to `/dashboard` with welcome message
- [ ] **1A.4** ✅ Dashboard shows empty state (0 monitors)
- [ ] **1A.5** ✅ Plan shows "Free" — limited to 5 monitors, 5-min interval, email-only alerts
- [ ] **1A.6** Log out (top nav → Logout or `/logout`)

### 1B — Login (existing user)

- [ ] **1B.1** Go to `/login`
- [ ] **1B.2** Login with `testaccount1@statusrooster.com` / `password`
- [ ] **1B.3** ✅ Redirects to `/dashboard`
- [ ] **1B.4** ✅ Plan shows "Pro"

### 1C — Google OAuth (Login / Signup)

- [ ] **1C.1** Go to `/login` → click "Continue with Google"
- [ ] **1C.2** ✅ Redirects to Google consent screen (`accounts.google.com`)
- [ ] **1C.3** Select your Google account (use a personal Gmail)
- [ ] **1C.4** ✅ Redirected back to `/dashboard` — logged in successfully
- [ ] **1C.5** ✅ User created in Firestore with `auth_provider: "google"` (check admin → Users tab)
- [ ] **1C.6** Log out → go to `/login` → click "Continue with Google" again
- [ ] **1C.7** ✅ Logs in to the SAME account (no duplicate user created)
- [ ] **1C.8** ✅ Dashboard shows correct email from Google

### 1D — GitHub OAuth (Login / Signup)

- [ ] **1D.1** Go to `/login` → click "Continue with GitHub"
- [ ] **1D.2** ✅ Redirects to GitHub authorize page (`github.com/login/oauth/authorize`)
- [ ] **1D.3** Click "Authorize" (or sign in to GitHub first if needed)
- [ ] **1D.4** ✅ Redirected back to `/dashboard` — logged in successfully
- [ ] **1D.5** ✅ User created in Firestore with `auth_provider: "github"` (check admin → Users tab)
- [ ] **1D.6** Log out → go to `/login` → click "Continue with GitHub" again
- [ ] **1D.7** ✅ Logs in to the SAME account (no duplicate user created)
- [ ] **1D.8** ✅ Dashboard shows correct email from GitHub

### 1E — OAuth from Signup Page

- [ ] **1E.1** Go to `/signup` → ✅ Both "Continue with Google" and "Continue with GitHub" buttons visible
- [ ] **1E.2** Click "Continue with Google" from signup → ✅ Same flow as 1C (creates account if new)
- [ ] **1E.3** Click "Continue with GitHub" from signup → ✅ Same flow as 1D (creates account if new)

### 1F — OAuth Edge Cases

- [ ] **1F.1** Sign up with email `you@gmail.com` via password, then log in with Google OAuth using same email → ✅ Links accounts (`auth_provider` becomes `"email,google"`)
- [ ] **1F.2** Sign up with email via password, then log in with GitHub OAuth using same email → ✅ Links accounts (`auth_provider` becomes `"email,github"`)
- [ ] **1F.3** Cancel Google consent screen → ✅ Redirected to `/login?error=Google+login+cancelled`
- [ ] **1F.4** Cancel GitHub authorize → ✅ Redirected to `/login?error=GitHub+login+cancelled`
- [ ] **1F.5** OAuth user can access all features (add monitor, settings, etc.) same as email user

### 1G — Auth Edge Cases

- [ ] **1G.1** Visit `/dashboard` while logged out → redirects to `/login`
- [ ] **1G.2** Visit `/monitors/add` while logged out → redirects to `/login`
- [ ] **1G.3** Visit `/settings` while logged out → redirects to `/login`
- [ ] **1G.4** Login with wrong password → error message shown
- [ ] **1G.5** Login with non-existent email → error message shown

---

## Phase 2: Monitor Creation — All 4 Types

> **Important:** After creating each monitor, wait for at least 1 cron cycle (60s) and verify the checker picks it up. Use the "Check now" button on monitor detail for immediate feedback.

### 2A — HTTP Monitor (Minimal)

- [ ] **2A.1** Click "Add Monitor" from dashboard
- [ ] **2A.2** Type: HTTP/HTTPS (default)
- [ ] **2A.3** URL: `https://www.google.com`
- [ ] **2A.4** Name: `E2E — Google (basic)`
- [ ] **2A.5** Leave all other fields at defaults
- [ ] **2A.6** Click "Add monitor"
- [ ] **2A.7** ✅ Redirects to dashboard with success flash message
- [ ] **2A.8** ✅ Monitor appears in dashboard list with status "pending" (grey)
- [ ] **2A.9** Click into monitor detail → Click "Check now"
- [ ] **2A.10** ✅ Status changes to "up" (green), response time shown

### 2B — HTTP Monitor (All Fields)

- [ ] **2B.1** Add Monitor → HTTP/HTTPS
- [ ] **2B.2** URL: `https://httpbin.org/post`
- [ ] **2B.3** Name: `E2E — httpbin POST (full)`
- [ ] **2B.4** Group: `E2E Tests`
- [ ] **2B.5** **Notifications:**
  - [ ] Email: keep default (testaccount1@statusrooster.com)
  - [ ] Slack: toggle ON → enter a test Slack webhook URL (or real one if available)
  - [ ] Webhook: toggle ON → enter `https://httpbin.org/post` (echo service)
  - [ ] SMS: toggle ON → enter your real phone number (e.g. `+14791234567`)
- [ ] **2B.6** Interval: slide to `120s` (2 minutes)
- [ ] **2B.7** Expand "Advanced settings"
- [ ] **2B.8** Timeout: `15`
- [ ] **2B.9** Expected status code: `200`
- [ ] **2B.10** HTTP method: click **POST**
  - [ ] ✅ Request body field appears
- [ ] **2B.11** Content type: `application/json`
- [ ] **2B.12** Request body: `{"test": "statusrooster"}`
- [ ] **2B.13** Follow redirects: leave checked
- [ ] **2B.14** Authentication: select **Bearer Token** → enter `test-bearer-token-123`
- [ ] **2B.15** Custom headers: click "+ Add header" → Key: `X-Test-Header`, Value: `e2e-test`
- [ ] **2B.16** Keyword check: click "+ Add keyword" → Contains: `httpbin`
- [ ] **2B.17** Response threshold: `> 5000`
- [ ] **2B.18** Status page: toggle public ON → slug: `e2e-httpbin`
- [ ] **2B.19** Maintenance window: click "+ Add maintenance window" → Day: `Daily`, Start: `04:00`, End: `04:30`
- [ ] **2B.20** Click "Add monitor"
- [ ] **2B.21** ✅ Redirects to dashboard with success message
- [ ] **2B.22** Click into monitor detail → "Check now"
- [ ] **2B.23** ✅ Status = UP (httpbin returns 200 with "httpbin" in body)
- [ ] **2B.24** ✅ Click "Edit" → verify ALL fields persisted correctly:
  - [ ] URL = `https://httpbin.org/post`
  - [ ] HTTP method = POST
  - [ ] Timeout = 15
  - [ ] Expected status = 200
  - [ ] Bearer token = `test-bearer-token-123`
  - [ ] Custom header: `X-Test-Header` = `e2e-test`
  - [ ] Keyword = `httpbin`
  - [ ] Threshold = `> 5000`
  - [ ] Interval slider at 120s
  - [ ] Public toggle ON, slug = `e2e-httpbin`
  - [ ] Maintenance window: Daily 04:00–04:30
  - [ ] Slack webhook filled
  - [ ] Webhook URL filled
  - [ ] SMS number filled

### 2C — HTTP Monitor with Basic Auth

- [ ] **2C.1** Add Monitor → HTTP/HTTPS
- [ ] **2C.2** URL: `https://httpbin.org/basic-auth/admin/secret`
- [ ] **2C.3** Name: `E2E — Basic Auth`
- [ ] **2C.4** Advanced → Authentication: **Basic Auth** → Username: `admin`, Password: `secret`
- [ ] **2C.5** Expected status code: `200`
- [ ] **2C.6** Click "Add monitor"
- [ ] **2C.7** Monitor detail → "Check now"
- [ ] **2C.8** ✅ Status = UP (httpbin validates the Basic Auth credentials and returns 200)

### 2D — HTTP Monitor (Expected to be DOWN)

- [ ] **2D.1** Add Monitor → HTTP/HTTPS
- [ ] **2D.2** URL: `https://httpstat.us/500`
- [ ] **2D.3** Name: `E2E — Forced 500 (should be DOWN)`
- [ ] **2D.4** Click "Add monitor"
- [ ] **2D.5** Monitor detail → "Check now"
- [ ] **2D.6** ✅ Status = DOWN (red) — 500 is not 2xx/3xx
- [ ] **2D.7** ✅ An incident is created — check Incidents page

### 2E — HTTP Monitor with Keyword (Negative — Expected DOWN)

- [ ] **2E.1** Add Monitor → HTTP/HTTPS
- [ ] **2E.2** URL: `https://httpstat.us/200`
- [ ] **2E.3** Name: `E2E — Keyword Missing`
- [ ] **2E.4** Advanced → Keyword: `BANANA_SPLIT_SUNDAE` (not in the response)
- [ ] **2E.5** Click "Add monitor"
- [ ] **2E.6** Monitor detail → "Check now"
- [ ] **2E.7** ✅ Status = UP (keyword check fires as alert but doesn't change status to down)
- [ ] **2E.8** ✅ Keyword alert email received

### 2F — HTTP Monitor with Timeout (Expected DOWN)

- [ ] **2F.1** Add Monitor → HTTP/HTTPS
- [ ] **2F.2** URL: `https://httpstat.us/200?sleep=15000`
- [ ] **2F.3** Name: `E2E — Timeout Test`
- [ ] **2F.4** Advanced → Timeout: `3` seconds
- [ ] **2F.5** Click "Add monitor"
- [ ] **2F.6** Monitor detail → "Check now"
- [ ] **2F.7** ✅ Status = DOWN (request times out at 3s, but endpoint takes 15s)

### 2G — HTTP Monitor with Status Code Mismatch

- [ ] **2G.1** Add Monitor → HTTP/HTTPS
- [ ] **2G.2** URL: `https://httpstat.us/201`
- [ ] **2G.3** Name: `E2E — Wrong Status Code`
- [ ] **2G.4** Advanced → Expected status code: `200`
- [ ] **2G.5** Click "Add monitor"
- [ ] **2G.6** Monitor detail → "Check now"
- [ ] **2G.7** ✅ Status = DOWN (endpoint returns 201, but we expected 200)

### 2H — HTTP Monitor with HEAD method

- [ ] **2H.1** Add Monitor → HTTP/HTTPS
- [ ] **2H.2** URL: `https://www.google.com`
- [ ] **2H.3** Name: `E2E — HEAD Method`
- [ ] **2H.4** Advanced → HTTP method: **HEAD**
- [ ] **2H.5** Click "Add monitor"
- [ ] **2H.6** Monitor detail → "Check now"
- [ ] **2H.7** ✅ Status = UP

### 2I — HTTP Monitor (Start Paused)

- [ ] **2I.1** Add Monitor → HTTP/HTTPS
- [ ] **2I.2** URL: `https://www.google.com`
- [ ] **2I.3** Name: `E2E — Paused Monitor`
- [ ] **2I.4** Advanced → toggle "Start paused" ON
- [ ] **2I.5** Click "Add monitor"
- [ ] **2I.6** ✅ Dashboard shows paused icon/badge on this monitor
- [ ] **2I.7** ✅ Cron does NOT check it (status stays "pending" after 2+ minutes)
- [ ] **2I.8** Click the pause/resume button → ✅ Monitor resumes, next cron cycle checks it

---

### 2J — JSON/API Monitor (Minimal)

- [ ] **2J.1** Add Monitor → JSON / API
- [ ] **2J.2** URL: `https://httpbin.org/json`
- [ ] **2J.3** Name: `E2E — JSON Basic`
- [ ] **2J.4** Click "Add monitor"
- [ ] **2J.5** Monitor detail → "Check now"
- [ ] **2J.6** ✅ Status = UP (valid JSON, 200)

### 2K — JSON/API Monitor (Full — Assertions)

- [ ] **2K.1** Add Monitor → JSON / API
- [ ] **2K.2** URL: `https://httpbin.org/json`
- [ ] **2K.3** Name: `E2E — JSON Assertions`
- [ ] **2K.4** Advanced → Auth header: `Bearer test-token-123`
- [ ] **2K.5** Expected status: `200`
- [ ] **2K.6** Timeout: `10`
- [ ] **2K.7** Assertion 1: Path `slideshow.author` → Equals → `Yours Truly`
- [ ] **2K.8** Assertion 2: Path `slideshow.title` → Contains → `Sample`
- [ ] **2K.9** Assertion 3: Path `slideshow.slides` → Exists
- [ ] **2K.10** Click "Add monitor"
- [ ] **2K.11** Monitor detail → "Check now"
- [ ] **2K.12** ✅ Status = UP (all assertions pass)
- [ ] **2K.13** Edit → verify assertions persisted correctly

### 2L — JSON/API Monitor (Assertion Failure — Expected DOWN)

- [ ] **2L.1** Add Monitor → JSON / API
- [ ] **2L.2** URL: `https://httpbin.org/json`
- [ ] **2L.3** Name: `E2E — JSON Assertion FAIL`
- [ ] **2L.4** Assertion: Path `slideshow.title` → Equals → `WRONG_VALUE`
- [ ] **2L.5** Click "Add monitor"
- [ ] **2L.6** Monitor detail → "Check now"
- [ ] **2L.7** ✅ Status = DOWN (assertion failed)

### 2M — JSON/API Monitor (All Assertion Operators)

- [ ] **2M.1** Add Monitor → JSON / API
- [ ] **2M.2** URL: `https://httpbin.org/json`
- [ ] **2M.3** Name: `E2E — JSON Operators`
- [ ] **2M.4** Add these assertions:
  - `slideshow.author` **equals** `Yours Truly` → ✅ pass
  - `slideshow.author` **not_equals** `Someone Else` → ✅ pass
  - `slideshow.title` **contains** `Sample` → ✅ pass
  - `slideshow.title` **not_contains** `BANANA` → ✅ pass
  - `slideshow.slides` **exists** → ✅ pass
  - `slideshow.nonexistent` **not_exists** → ✅ pass
- [ ] **2M.5** Click "Add monitor"
- [ ] **2M.6** Monitor detail → "Check now"
- [ ] **2M.7** ✅ Status = UP (all assertions pass)

---

### 2N — Heartbeat Monitor

- [ ] **2N.1** Add Monitor → Heartbeat
- [ ] **2N.2** Name: `E2E — Heartbeat Cron`
- [ ] **2N.3** Expected ping interval: `Every 5 minutes` (300s)
- [ ] **2N.4** Grace period: `60` seconds
- [ ] **2N.5** Click "Add monitor"
- [ ] **2N.6** ✅ Dashboard redirect shows ping URL in a modal/flash
- [ ] **2N.7** Copy the ping URL (should be like `https://statusrooster.com/api/ping/{id}?token={token}`)
- [ ] **2N.8** In terminal: `curl -s "PASTE_PING_URL_HERE"`
- [ ] **2N.9** ✅ Response: `{"ok": true, "status": "up", ...}`
- [ ] **2N.10** Monitor detail → ✅ Status = UP, "Last heartbeat" shows recent timestamp
- [ ] **2N.11** Wait 6+ minutes without pinging → ✅ Status changes to DOWN after cron runs
- [ ] **2N.12** Ping again → ✅ Status returns to UP on next cron cycle

### 2O — Heartbeat Monitor (Immediately Overdue)

- [ ] **2O.1** Add Monitor → Heartbeat
- [ ] **2O.2** Name: `E2E — Heartbeat Overdue`
- [ ] **2O.3** Interval: `Every 1 minute` (60s), Grace: `0`
- [ ] **2O.4** Click "Add monitor"
- [ ] **2O.5** Do NOT ping it
- [ ] **2O.6** Wait ~2 minutes for cron
- [ ] **2O.7** ✅ Status = DOWN (never received a ping, interval + grace exceeded)
- [ ] **2O.8** ✅ Incident created

---

### 2P — SSL Monitor (Valid Cert)

- [ ] **2P.1** Add Monitor → SSL Cert
- [ ] **2P.2** Domain: `statusrooster.com`
- [ ] **2P.3** Name: `E2E — SR SSL`
- [ ] **2P.4** Warning threshold: `14` days
- [ ] **2P.5** Click "Add monitor"
- [ ] **2P.6** Monitor detail → "Check now"
- [ ] **2P.7** ✅ Status = UP, shows cert issuer, expiry date, days remaining

### 2Q — SSL Monitor (Expired Cert — Expected DOWN)

- [ ] **2Q.1** Add Monitor → SSL Cert
- [ ] **2Q.2** Domain: `expired.badssl.com`
- [ ] **2Q.3** Name: `E2E — Expired SSL`
- [ ] **2Q.4** Threshold: `14` days
- [ ] **2Q.5** Click "Add monitor"
- [ ] **2Q.6** Monitor detail → "Check now"
- [ ] **2Q.7** ✅ Status = DOWN (expired certificate)
- [ ] **2Q.8** ✅ Incident created

### 2R — SSL Monitor (Warning — High Threshold)

- [ ] **2R.1** Add Monitor → SSL Cert
- [ ] **2R.2** Domain: `statusrooster.com`
- [ ] **2R.3** Name: `E2E — SSL Warn Test`
- [ ] **2R.4** Threshold: `90` days (if cert expires in < 90 days, status = warn)
- [ ] **2R.5** Click "Add monitor"
- [ ] **2R.6** Monitor detail → "Check now"
- [ ] **2R.7** ✅ Status = "warn" (yellow) if cert expires within 90 days, or "up" if > 90 days
- [ ] **2R.8** Note the status and verify it makes sense given the actual cert expiry

---

## Phase 3: Dashboard Verification

> After creating all monitors above (~15–18), verify the dashboard renders correctly.

- [ ] **3.1** Dashboard shows all monitors in card rows
- [ ] **3.2** Status indicators: green (up), red (down), yellow (warn), grey (pending), blue (paused)
- [ ] **3.3** Uptime bars visible for monitors with check history (at least 1 bar)
- [ ] **3.4** Response time shown for HTTP/JSON monitors
- [ ] **3.5** Group filter: type `E2E Tests` in search → only monitors in that group shown
- [ ] **3.6** Status filter: click "Down" filter → only DOWN monitors shown
- [ ] **3.7** Sort: try sorting by Name, Status, Response Time
- [ ] **3.8** Search: type a monitor name → filters live
- [ ] **3.9** ✅ Monitor count in header matches actual number

### 3B — Bulk Actions

- [ ] **3B.1** Select 2+ monitors using checkboxes (if bulk actions exist)
- [ ] **3B.2** Test bulk pause → ✅ Selected monitors pause
- [ ] **3B.3** Test bulk resume → ✅ Selected monitors resume
- [ ] **3B.4** Test bulk delete → ✅ Selected monitors removed

---

## Phase 4: Monitor Detail Page

Pick one UP HTTP monitor (e.g., `E2E — Google (basic)`) for these tests.

- [ ] **4.1** Click monitor row in dashboard → opens `/monitors/{id}` detail page
- [ ] **4.2** ✅ Status badge shows UP (green)
- [ ] **4.3** ✅ Response time chart renders (Chart.js) — at least 1 data point
- [ ] **4.4** ✅ Uptime percentage shown
- [ ] **4.5** ✅ Uptime bars (daily / hourly) render with tooltips
- [ ] **4.6** Click period slicer (24h / 7d / 30d) → ✅ Data updates
- [ ] **4.7** "Check now" button → ✅ Shows result inline, updates chart
- [ ] **4.8** Incident history section → ✅ Shows incidents (or "No incidents" if none)
- [ ] **4.9** ✅ Monitor info panel shows URL, type, interval, notifications, etc.

Pick the DOWN monitor (`E2E — Forced 500`):

- [ ] **4.10** ✅ Status shows DOWN (red)
- [ ] **4.11** ✅ Active incident shown with timestamp
- [ ] **4.12** ✅ Response code shows 500

---

## Phase 5: Edit Monitor

### 5A — Edit and Verify Persistence

- [ ] **5A.1** Go to monitor detail for `E2E — httpbin POST (full)` → click "Edit"
- [ ] **5A.2** Change name to `E2E — httpbin POST (edited)`
- [ ] **5A.3** Change timeout from 15 → 20
- [ ] **5A.4** Change interval from 120s → 180s
- [ ] **5A.5** Remove the custom header
- [ ] **5A.6** Add a new keyword: `org` (AND)
- [ ] **5A.7** Change maintenance window to Tuesday 02:00–03:00
- [ ] **5A.8** Click "Save"
- [ ] **5A.9** ✅ Redirects to dashboard with success message
- [ ] **5A.10** Re-open Edit → ✅ All changes persisted:
  - Name = `E2E — httpbin POST (edited)`
  - Timeout = 20
  - Interval = 180s
  - No custom headers
  - Keywords include `org`
  - Maintenance = Tuesday 02:00–03:00

### 5B — Edit SSL Monitor

- [ ] **5B.1** Edit `E2E — SR SSL`
- [ ] **5B.2** Change threshold from 14 → 30 days
- [ ] **5B.3** Save → re-open Edit → ✅ Threshold = 30

### 5C — Edit Heartbeat Monitor

- [ ] **5C.1** Edit `E2E — Heartbeat Cron`
- [ ] **5C.2** Change interval from 5 min → 10 min
- [ ] **5C.3** Change grace period from 60s → 120s
- [ ] **5C.4** Save → re-open Edit → ✅ Interval = 600s, Grace = 120s

### 5D — Edit JSON/API Monitor

- [ ] **5D.1** Edit `E2E — JSON Assertions`
- [ ] **5D.2** Add assertion: `slideshow.date` → Equals → `date of publication`
- [ ] **5D.3** Remove assertion #3 (`slides` → Exists)
- [ ] **5D.4** Save → re-open Edit → ✅ 3 assertions total, correct values

---

## Phase 6: Incidents & Alerts

### 6A — Incident Lifecycle (DOWN → Recovery)

- [ ] **6A.1** Go to monitor `E2E — Forced 500 (should be DOWN)` → confirm it's DOWN with open incident
- [ ] **6A.2** Click "Edit" → change URL to `https://httpstat.us/200`
- [ ] **6A.3** Save → go to monitor detail → "Check now"
- [ ] **6A.4** ✅ Status changes from DOWN → UP
- [ ] **6A.5** ✅ Incident is auto-resolved (shows "Resolved" with duration)
- [ ] **6A.6** ✅ Recovery alert email received
- [ ] **6A.7** Go to Incidents page (`/incidents`) → ✅ Incident listed with resolved status

### 6B — Incident Detail Page

- [ ] **6B.1** Click into a resolved incident from the Incidents list
- [ ] **6B.2** ✅ Shows: monitor name, started at, resolved at, duration, root cause (status code)
- [ ] **6B.3** ✅ Timeline/event log shows: detected → alert sent → resolved

### 6C — Incidents List

- [ ] **6C.1** Go to `/incidents`
- [ ] **6C.2** ✅ All incidents shown (both open and resolved)
- [ ] **6C.3** Filter by status: "Open" → only open incidents
- [ ] **6C.4** Filter by status: "Resolved" → only resolved incidents
- [ ] **6C.5** Filter by monitor → ✅ Shows only that monitor's incidents
- [ ] **6C.6** Search by monitor name → ✅ Filters correctly
- [ ] **6C.7** Sort by duration, started at → ✅ Works

### 6D — Alert Channels Verification

> For each DOWN→UP cycle, verify alerts arrive on all configured channels.

- [ ] **6D.1** **Email:** Check inbox for down alert and recovery alert from `alerts@statusrooster.com`
- [ ] **6D.2** **Slack:** If webhook configured, check Slack channel for alert messages
- [ ] **6D.3** **Webhook:** If using httpbin, check httpbin.org response or use a webhook.site URL
- [ ] **6D.4** **SMS:** If Twilio A2P approved and phone number configured, check phone for SMS
- [ ] **6D.5** **Test alert button:** On monitor detail, click "Send test alert" → ✅ Test alert sent to all configured channels

### 6E — Alert Suppression (Maintenance Window)

- [ ] **6E.1** Edit a monitor → set maintenance window to cover the current UTC time
- [ ] **6E.2** Change URL to `https://httpstat.us/500` → save
- [ ] **6E.3** Wait for cron cycle → monitor goes DOWN
- [ ] **6E.4** ✅ NO down alert email/SMS/Slack received (suppressed by maintenance)
- [ ] **6E.5** ✅ Incident still created (maintenance suppresses alerts, not checks)
- [ ] **6E.6** Remove the maintenance window → change URL back to `https://httpstat.us/200`

---

## Phase 7: Dashboard Actions

- [ ] **7.1** **Pause/Resume:** Click pause button on a monitor → ✅ Shows paused state → Click again → ✅ Resumes
- [ ] **7.2** **Clone:** Click clone on a monitor → ✅ Creates a copy with "(copy)" suffix
- [ ] **7.3** **Delete:** Click delete on a monitor → ✅ Confirm dialog → ✅ Monitor removed
- [ ] **7.4** **Delete cloned monitor** to clean up

---

## Phase 8: Status Pages & Badges

### 8A — Public Status Page (by slug)

- [ ] **8A.1** Monitor `E2E — httpbin POST (edited)` was set to public with slug `e2e-httpbin`
- [ ] **8A.2** Visit `https://statusrooster.com/s/e2e-httpbin`
- [ ] **8A.3** ✅ Public status page renders with monitor name, status, uptime bars
- [ ] **8A.4** ✅ No login required
- [ ] **8A.5** ✅ "Powered by StatusRooster" link shown

### 8B — Aggregate Status Page

- [ ] **8B.1** Visit `https://statusrooster.com/status/{user_id}` (get user_id from admin or settings)
- [ ] **8B.2** ✅ Shows all public monitors for that user
- [ ] **8B.3** ✅ Overall status indicator (all up / some down)

### 8C — Uptime Badges

- [ ] **8C.1** Get a monitor ID from the dashboard (any UP monitor)
- [ ] **8C.2** Visit `https://statusrooster.com/badge/{monitor_id}.svg`
- [ ] **8C.3** ✅ SVG badge renders with uptime percentage
- [ ] **8C.4** Visit `https://statusrooster.com/badge/{monitor_id}/status.svg`
- [ ] **8C.5** ✅ SVG badge renders with UP/DOWN status
- [ ] **8C.6** Visit `https://statusrooster.com/badge/{monitor_id}/response.svg`
- [ ] **8C.7** ✅ SVG badge renders with response time

---

## Phase 9: Settings & API Keys

### 9A — Settings Page

- [ ] **9A.1** Go to `/settings`
- [ ] **9A.2** ✅ Shows email, plan (Pro), account info
- [ ] **9A.3** Change notification email → save → ✅ Updated
- [ ] **9A.4** Change password → ✅ Can log out and log back in with new password
- [ ] **9A.5** *(Reset password back to `password` for test account)*

### 9B — API Keys

- [ ] **9B.1** Settings → generate a new API key
- [ ] **9B.2** ✅ Key shown once (copy it!)
- [ ] **9B.3** Test the API key with curl:
  ```
  curl -s -H "X-API-Key: YOUR_KEY" https://statusrooster.com/api/v1/monitors | head
  ```
- [ ] **9B.4** ✅ Returns JSON with `{"data": [...monitors...], ...}`
- [ ] **9B.5** Revoke the API key → ✅ Key no longer works (401)

---

## Phase 10: Public API (v1)

> Use a valid API key from Phase 9B for all requests.

### 10A — List Monitors

```bash
curl -s -H "X-API-Key: KEY" https://statusrooster.com/api/v1/monitors | python3 -m json.tool
```

- [ ] **10A.1** ✅ Returns list of all monitors with correct fields
- [ ] **10A.2** ✅ Each monitor has: id, name, url, status, monitor_type, uptime_percent, etc.

### 10B — Get Single Monitor

```bash
curl -s -H "X-API-Key: KEY" https://statusrooster.com/api/v1/monitors/{MONITOR_ID}
```

- [ ] **10B.1** ✅ Returns single monitor detail
- [ ] **10B.2** With invalid ID → ✅ Returns 404

### 10C — Get Checks

```bash
curl -s -H "X-API-Key: KEY" "https://statusrooster.com/api/v1/monitors/{MONITOR_ID}/checks?limit=5"
```

- [ ] **10C.1** ✅ Returns recent checks with status_code, response_ms, is_up, timestamp

### 10D — List Incidents

```bash
curl -s -H "X-API-Key: KEY" https://statusrooster.com/api/v1/incidents
```

- [ ] **10D.1** ✅ Returns list of incidents

### 10E — Get Incident

```bash
curl -s -H "X-API-Key: KEY" https://statusrooster.com/api/v1/incidents/{INCIDENT_ID}
```

- [ ] **10E.1** ✅ Returns incident detail with timeline events

### 10F — Create Monitor via API

```bash
curl -s -X POST -H "X-API-Key: KEY" -H "Content-Type: application/json" \
  -d '{"name":"API Created Monitor","url":"https://httpstat.us/200","monitor_type":"http"}' \
  https://statusrooster.com/api/v1/monitors
```

- [ ] **10F.1** ✅ Returns 201 with created monitor
- [ ] **10F.2** ✅ Monitor appears in dashboard

### 10G — Update Monitor via API

```bash
curl -s -X PUT -H "X-API-Key: KEY" -H "Content-Type: application/json" \
  -d '{"name":"API Updated Monitor"}' \
  https://statusrooster.com/api/v1/monitors/{MONITOR_ID}
```

- [ ] **10G.1** ✅ Returns updated monitor

### 10H — Delete Monitor via API

```bash
curl -s -X DELETE -H "X-API-Key: KEY" \
  https://statusrooster.com/api/v1/monitors/{MONITOR_ID}
```

- [ ] **10H.1** ✅ Returns `{"deleted": true}` (or similar)
- [ ] **10H.2** ✅ Monitor removed from dashboard

### 10I — API Auth Edge Cases

- [ ] **10I.1** Request without API key → ✅ Returns 401
- [ ] **10I.2** Request with invalid API key → ✅ Returns 401
- [ ] **10I.3** Request to another user's monitor → ✅ Returns 403

---

## Phase 11: Billing (Stripe)

> ⚠️ Use Stripe **test mode** cards. Do NOT enter real payment info.

### 11A — Free Plan Limits

- [ ] **11A.1** Log in as the FREE user created in Phase 1A
- [ ] **11A.2** Add 5 monitors (all HTTP, simple URLs)
- [ ] **11A.3** Try to add a 6th → ✅ Blocked with upgrade CTA
- [ ] **11A.4** ✅ Interval locked at 5 min (slider disabled)
- [ ] **11A.5** ✅ Slack/Webhook/SMS show "PRO" badge, not toggleable
- [ ] **11A.6** ✅ Maintenance windows show "Upgrade to Pro"
- [ ] **11A.7** ✅ Custom headers show "Upgrade to Pro"
- [ ] **11A.8** ✅ Basic Auth / Bearer Token show "(Pro)" in dropdown

### 11B — Upgrade to Pro

- [ ] **11B.1** Click any "Upgrade to Pro" link
- [ ] **11B.2** ✅ Redirects to Stripe Checkout
- [ ] **11B.3** Use test card: `4242 4242 4242 4242`, any future expiry, any CVC
- [ ] **11B.4** ✅ After payment, redirects back to StatusRooster
- [ ] **11B.5** ✅ Plan now shows "Pro"
- [ ] **11B.6** ✅ Can add more than 5 monitors
- [ ] **11B.7** ✅ Interval slider unlocked (60s–300s)
- [ ] **11B.8** ✅ Slack/Webhook/SMS now toggleable

---

## Phase 12: Responsive / Mobile

> Use Chrome DevTools (Cmd+Shift+M) or a real phone.

- [ ] **12.1** Landing page — ✅ Responsive, hamburger nav on <768px
- [ ] **12.2** Dashboard — ✅ Sidebar collapses, monitor cards stack vertically
- [ ] **12.3** Add monitor form — ✅ Type buttons wrap, fields full-width
- [ ] **12.4** Monitor detail — ✅ Chart resizes, panels stack
- [ ] **12.5** Incidents list — ✅ Columns don't overflow
- [ ] **12.6** Settings — ✅ Readable on mobile
- [ ] **12.7** Status page — ✅ Clean on mobile
- [ ] **12.8** Login/Signup — ✅ Full-width forms

---

## Phase 13: Error Pages & Edge Cases

- [ ] **13.1** Visit `https://statusrooster.com/nonexistent-page` → ✅ Shows custom 404 page
- [ ] **13.2** Visit `https://statusrooster.com/monitors/FAKE_ID` → ✅ Redirects or shows 404
- [ ] **13.3** Visit `https://statusrooster.com/s/nonexistent-slug` → ✅ Shows 404
- [ ] **13.4** Submit add monitor form with empty URL → ✅ Client-side validation blocks
- [ ] **13.5** Submit add monitor form with empty name → ✅ Client-side validation blocks
- [ ] **13.6** Try to access another user's monitor detail by ID → ✅ 403 or redirect
- [ ] **13.7** Double-click "Add monitor" button rapidly → ✅ Doesn't create duplicates

---

## Phase 14: Admin Dashboard

- [ ] **14.1** Login as `gjbangerter@gmail.com` / `adminpass123`
- [ ] **14.2** Visit `https://statusrooster.com/admin`
- [ ] **14.3** ✅ KPI cards show correct totals (users, monitors, MRR, checks today)
- [ ] **14.4** ✅ Cron health shows "Last check" < 2 min ago
- [ ] **14.5** ✅ Recent signups table populated
- [ ] **14.6** Users tab → ✅ Per-user stats (monitor count, types, uptime)
- [ ] **14.7** Monitors tab → ✅ All monitors listed with status
- [ ] **14.8** ✅ Auto-refresh countdown visible, page refreshes every 60s
- [ ] **14.9** Login as non-admin → visit `/admin` → ✅ Returns 404

---

## Phase 15: Self-Monitoring (StatusRooster monitors itself)

This is the final "dogfooding" step — leave these monitors running permanently.

- [ ] **15.1** Create HTTP monitor: `StatusRooster Landing` → `https://statusrooster.com`
- [ ] **15.2** Create HTTP monitor: `StatusRooster Dashboard` → `https://statusrooster.com/dashboard` (expected 302 → should follow redirects to login → check with expected status 200 on landing)
- [ ] **15.3** Create SSL monitor: `StatusRooster SSL` → domain `statusrooster.com`, threshold 14 days
- [ ] **15.4** Create JSON/API monitor: `SR API Health` → `https://statusrooster.com/api/v1/monitors` → expected 401 (no key) → set expected status = 401
- [ ] **15.5** Set all to 60s interval, email alerts to `gjbangerter@gmail.com`
- [ ] **15.6** Make `StatusRooster Landing` public with slug `statusrooster`
- [ ] **15.7** ✅ All 4 monitors show UP after first cron cycle
- [ ] **15.8** ✅ Status page at `/s/statusrooster` shows StatusRooster monitoring itself 🐔

---

## Cleanup Checklist

After testing is complete:

- [ ] Delete the FREE test user created in Phase 1A (or leave for future testing)
- [ ] Remove test monitors that are intentionally DOWN (httpstat.us/500, expired SSL, etc.)
- [ ] Keep self-monitoring monitors (Phase 15) running permanently
- [ ] Ensure test account `testaccount1@statusrooster.com` password is reset to `password`
- [ ] Verify admin password for `gjbangerter@gmail.com` is `adminpass123`

---

## Results Summary

| Phase | Name | Tests | Passed | Failed | Notes |
|-------|------|-------|--------|--------|-------|
| 0 | Pre-Flight | 7 | | | |
| 1 | Auth | 28 | | | |
| 2 | Monitor Creation | ~50 | | | |
| 3 | Dashboard | 13 | | | |
| 4 | Monitor Detail | 12 | | | |
| 5 | Edit Monitor | 11 | | | |
| 6 | Incidents & Alerts | 18 | | | |
| 7 | Dashboard Actions | 4 | | | |
| 8 | Status Pages & Badges | 10 | | | |
| 9 | Settings & API Keys | 7 | | | |
| 10 | Public API | 14 | | | |
| 11 | Billing (Stripe) | 10 | | | |
| 12 | Responsive | 8 | | | |
| 13 | Error Pages | 7 | | | |
| 14 | Admin | 9 | | | |
| 15 | Self-Monitoring | 8 | | | |
| **TOTAL** | | **~206** | | | |

---

## Test Services Reference

| Service | URL | What It Does |
|---------|-----|--------------|
| httpstat.us | `https://httpstat.us/{code}` | Returns any HTTP status code |
| httpstat.us (slow) | `https://httpstat.us/200?sleep={ms}` | Returns 200 after delay (ms) |
| httpbin.org | `https://httpbin.org` | HTTP echo/testing service |
| httpbin.org/json | `https://httpbin.org/json` | Returns sample JSON payload |
| httpbin.org/post | `https://httpbin.org/post` | Echoes POST data back as JSON |
| httpbin.org/basic-auth | `https://httpbin.org/basic-auth/{user}/{pass}` | Validates Basic Auth |
| badssl.com | `https://expired.badssl.com` | Expired SSL certificate |
| badssl.com | `https://wrong.host.badssl.com` | Wrong host SSL certificate |
| webhook.site | `https://webhook.site` | Free webhook receiver (sign up for URL) |
