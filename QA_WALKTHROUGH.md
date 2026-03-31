# StatusRooster — Manual QA Walkthrough

Two parts:
1. **Visual/Interactive QA Checklist** — things to click and verify in the browser
2. **Monitor Setup Tour** — step-by-step guide to set up real monitors for statusrooster.com

---

## Part 1: Visual/Interactive QA Checklist

Open https://statusrooster.com on your phone AND desktop. Log in with your account.
Check each item off as you go. If something looks wrong, note it.

### Dashboard (`/dashboard`)

**Cards & Data:**
- [X] Each monitor card shows: status dot (green/red/yellow/gray), name, URL, uptime %, response time
- [X] 30-day uptime bars visible on each card — hover/tap a bar to see the tooltip (date + uptime %)
- [X] "Up for X" duration text visible below each monitor name
- [X] Cards are clickable — tapping one takes you to the detail page

**Status Strip (top bar):**
- [X] Shows count of Up / Down / Paused monitors
- [X] Numbers match what you see in the card list

**Aggregate Stats:**
- [X] Shows overall uptime %, average response time, incidents today
- [X] Numbers look reasonable (not NaN, not blank)

**Search & Filters:**
- [X] Type in the search box — cards filter by name/URL as you type
- [X] Click a status filter (Up/Down/Paused) — only matching cards show
- [X] Click a type filter (HTTP/SSL/Heartbeat/JSON) — only matching cards show
- [X] If you have groups, click a group filter — only that group shows
- [X] "Clear all" button removes all active filters
- [X] Each active filter shows as a pill/badge you can click to remove individually

**Sort:**
- [NOT_WORKING] Open the sort dropdown — options: Down first, A-Z, Z-A, Lowest uptime, Highest uptime
- [X] Pick "A-Z" — cards reorder alphabetically
- [CANT_TEST] Pick "Down first" — any down monitors jump to top

**Context Menu (right-click or three-dot menu on a card):**
- [X] Menu appears with: Edit, Pause/Resume, Clone, Copy URL, Delete
- [X] Click "Edit" — takes you to the edit form for that monitor
- [X] Click "Pause" — monitor status changes to paused (gray dot)
- [X] Click "Resume" — monitor goes back to active
- [X] Click "Clone" — creates a copy of the monitor
- [X] Click "Delete" — asks for confirmation, then removes the monitor

**Bulk Actions:**
- [X] Click checkboxes on multiple cards
- [X] Bulk action bar appears with Pause/Resume/Delete buttons
- [X] Click "Pause" — all selected monitors pause
- [X] Click "Delete" — asks confirmation, deletes all selected

**Mobile (check on phone):**
- [ ] Cards are readable, not cut off
- [ ] Filters wrap properly, not overflowing
- [ ] Search box is usable
- [ ] Sidebar nav is visible and functional

---

### Monitor Detail (`/monitors/{id}`)

**Header:**
- [X] Shows: status dot, monitor name, type badge, URL
- [X] Monitor ID visible (with copy button)
- [X] Status code badge visible for HTTP monitors (green 2xx, orange 4xx, red 5xx)

**Action Buttons:**
- [X] "Check Now" button — click it, see a brief loading state, then result appears
- [X] After clicking, 30-second cooldown prevents spamming
- [X] "Pause/Resume" button works — toggles monitor state
- [X] "Test Alert" button — sends a test alert to configured channels
- [X] "Edit" link takes you to the edit form

**Top Cards:**
- [X] Status duration card ("Up for 3d 2h" or "Down for 5m")
- [X] Last check time
- [Changed to "downtime (30D)"- good] MTBF (mean time between failures) — or "No incidents" if none

**Uptime Section:**
- [X] 24h / 7d / 30d toggle buttons work
- [X] Uptime percentage updates when you switch periods
- [X] Uptime bars change to match the selected period
- [X] Bars have correct colors (green = up, red = down, gray = no data)

**Response Chart:**
- [X] Chart renders with response time data
- [X] Time range buttons: 1h, 6h, 24h, 7d, 30d — click each, chart updates
- [X] If threshold is set, dashed red line visible at threshold value
- [X] "Show regions" toggle (if multi-region) — per-region colored lines appear
- [X] Response stats below chart: avg, min, max — update with time range
- [X] Loading spinner shows briefly when switching ranges

**Response by Region:**
- [X] Section visible for multi-region monitors
- [X] Shows each region with its response time
- [CAN'T TEST?] Hidden when no region data exists

**Incidents Table:**
- [X] Lists recent incidents for this monitor
- [X] Each row shows: date, status, duration, root cause
- [X] Clicking a row takes you to the incident detail page
- [X] "View all incidents" link works
- [WE SHOULD HAVE MORE INFO HERE - LIKE MONITOR ID, ETC. ALSO NEED TO CONSIDER UNIQUE INCIDENT DETILS AND WHERE WE SHOW THIW IN THE UI?] "Export CSV" downloads a file

**Monitor-Type-Specific:**
- [NO - WE'RE NOT SHOWING ANY OF THIS - NEED TO TAKE A LOOK - LOKKS JUST LIKE A REGULAR HTTP DETAIL SCREEN NEED TO COMPLETLEY TAYLOR THIS] **SSL monitors:** SSL certificate section shows issuer, expiry, days remaining
- [X] **Heartbeat monitors:** Ping URL bar visible at top with copy button, no "Check Now" button
- [X] **JSON/API monitors:** Assertions section shows configured assertions

**Mobile:**
- [ ] All sections stack vertically, nothing overflows
- [ ] Chart is usable (can see data points)
- [ ] Action buttons wrap gracefully

---

### Add/Edit Monitor (`/monitors/add`, `/monitors/{id}/edit`)

**Add Form:**
- [X] Type selector: HTTP, JSON/API, Heartbeat, SSL — clicking each shows the right fields
- [K NEED TO CONSIDER IF ANY OF THIS SHOULD BE MOVED OUT OF ADVANCED SETTIGNS AND INTO TOP SECITON -A LL REQUIRED OR RECOMMENDED FIELDS SHOUDL BE INTHE TOP SECTION] **HTTP:** Shows URL, name, method, expected status, timeout, keyword, threshold, headers, auth
- [WE HAVE "CUSTOM HEADERS" HERE TOO] **JSON/API:** Shows URL, name, assertions builder, expected status, timeout
- [X] **Heartbeat:** Shows name only (plus interval, grace period)
- [X] **SSL:** Shows domain, name, expiry threshold
- [X] All types show: check interval, alert channels, group, public toggle, pause toggle

**Validation:**
- [NEED TO MAKE REQUIRED FIELDS BETTER] Submit with empty name — error message appears
- [X] Submit HTTP with empty URL — error message appears
- [X] Submit HTTP with invalid URL (e.g. "not-a-url") — error message appears
- [FAIL] Submit with valid data — redirects to monitor detail page

**Edit Form:**
- [X] All existing values pre-populated correctly
- [X] Change name, save — name updates on detail page
- [X] Monitor type is shown but not changeable

---

### Incidents (`/incidents`)

**List:**
- [X] Page shows all incidents across all monitors
- [X] Status strip: ongoing count, resolved count
- [X] Each row shows: status badge (ongoing/resolved), monitor name, root cause, started time, duration
- [CAN'T TEST] Ongoing incidents show elapsed timer ("Ongoing 2h 34m")
- [CAN'T TEST] Severity color-coding: red border for 5xx, orange for 4xx

**Filters:**
- [X] Filter by status (ongoing/resolved)
- [X] Filter by time range
- [X] Search by monitor name
- [X] Sort: newest, oldest, name, duration

**Detail (`/incidents/{id}`):**
- [X] Hero section: status, root cause badge, monitor name, URL
- [X] Details grid: started, resolved, duration, status code, failed checks count
- [X] Region corroboration: "Confirmed down from X/Y regions"
- [THIS IS IN THE ACTIVITY SECTION] Collapsible per-region table: region name, status, code, time, error
- [X] Response body preview (if available)
- [X] Activity timeline with events

### Settings (`/settings`)

**Layout & Navigation:**
- [X] Two-column layout: sticky section nav on left, content on right
- [X] Section nav links highlight as you scroll (scroll-spy)
- [X] Click a nav link — page scrolls to that section
- [X] "Danger Zone" nav link is styled red
- [X] On mobile (375px): section nav is hidden, sections stack vertically

**Sidebar Avatar:**
- [X] Sidebar avatar + username is clickable — links to `/settings`
- [X] If display name is set, sidebar shows display name instead of email prefix
- [X] Hover state visible on the avatar/username area

**Profile (new):**
- [X] Display name input — type a name, click "Save profile" — success flash
- [No auth provider badge -- I'm logged in w/ Google now and nothign - let's make this a lot better] Email shown as read-only with auth provider badge ("Email account" / "Google" / "GitHub")
- [X] "Contact support to change email" hint visible
- [X] Member since date displayed
- [X] After saving display name, sidebar updates to show it (on next page load)

**Password (new, email-auth only):**
- [NO] Section visible ONLY for email-auth users (hidden for Google/GitHub OAuth)
- [yes but badges are at top of screen outside of view ] Enter wrong current password — error flash "Current password is incorrect"
- [X] Enter new password < 8 chars — error flash about minimum length
- [not tested] Enter mismatched new/confirm passwords — error flash "do not match"
- [not tested] Enter correct current password + valid new password — success flash
- [i guess my account for gjbangerter@gmail.com was set up using auth?  it's saying that password change is only ] Log out and log back in with new password — works
- there's a major bug in this section - if you forget your password there's no way to request a reset automtaically?? this is terrible - let's make this whole password thing a lot better - this whole seciton neeeds some work. 

**Notifications (new):**
- [X] Default alert email pre-filled with login email
- [YES but notificaiton is at top of screen out of site] Change it, save — success flash
- [X] "Send recovery notifications" checkbox — checked by default
- [not tested] Uncheck it, save — recovery alerts stop being sent
- [yes but lets scratch this] "Weekly uptime digest" checkbox — unchecked, with "Coming soon" badge
- [not tested] Toggle it on, save — preference saved (no emails yet)

**Subscription & Billing (existing):**
- [X] **Plan card:** Shows Free or Pro badge, email, monitor count
- [yes and let's work on the content we show on the stip page - let's make this a lot better.] **Upgrade button** (free users): clicking it goes to Stripe checkout
- [yes and let's say somethign about "get you invoice history here strip - understand?] **Manage billing** (Pro users): opens Stripe billing portal

**Timezone (existing):**
- [X] Select a timezone, save — should show success message

**Status Page Branding (Pro only, existing):**
- [not tested] Section only visible for Pro users
- [coudl we make this better? make this an actual tab in the app instead of burried in settings?  and also enhance?] Logo URL, brand name, accent color, hide powered-by checkbox

**API Keys (existing):**
- [X] Generate a new key — key appears with copy button
- [X] Key shows "Copy" button — clicking copies to clipboard
- [X] Key table shows: label, prefix, status (active), created date
- [X] Revoke a key — confirms, then key shows as "Revoked"
- yikes - when new key is geneated erros to a 500 pg. but the key acutally gets created you can see it when you nav back to settibgs - bad issue

**Danger Zone (new):**
- [X] Red-bordered section at bottom of page
- [not tested] "Delete account" button — click it, confirmation form appears
- [not tested] Type wrong email — error flash "did not match"
- [not teted] Type correct email, click "Permanently delete my account" — JS confirm dialog appears
- [not tested] Confirm — account deleted, redirected to landing page, logged out
- [not tested] All user data removed (monitors, incidents, API keys, status pages)

---

### API Docs (`/docs/api`)

- [X] Sidebar nav visible when logged in
- [X] Top nav visible when logged out
- [X] All endpoint sections expandable/collapsible
- [not tested] Parameter tables readable (scrollable on mobile)
- [X] Code examples have copy buttons
- [X] **Request Builder:** Type tabs (HTTP, JSON, Heartbeat, SSL) work
- [X] Fill in fields — generated code updates live
- [X] Language tabs (curl, Python, JavaScript) switch the code
- [X] Copy button copies the generated code
- [X] **Keyword builder** (HTTP type): Add groups, add terms, preview updates
- ** NEED TO LOOK INTO THIS - IN THE API DOCUMENTATION, THE HEARTBEAT/CHRON GET/POST/HEAD /api/ping/{monitor_id} path is missing "v1" after API?  look into this?
- ** can't direclty copy the endpoint paths from the card dropdown - terrible annoying

---

### Landing Page (`/`)

- [ ] Hero text readable, buttons visible
- [ ] "Start monitoring free" button goes to /signup
- [ ] "View API docs" button goes to /docs/api
- [ ] URL checker: paste a URL, click "Check" — results appear
- [ ] Versus cards: pricing comparisons render correctly
- [ ] Screenshot tabs: Dashboard / Monitor detail / Status page — click each, image switches
- [ ] Pricing cards: Free and Pro side by side (stacked on mobile)
- [ ] Bottom CTA button works
- **WE NEED TO TAKEA HYPERCIRITAL LOOK AT OUR MESSAGING FOR THE LANDING PAGE - MAKE SURE WE REALLY HAVE THAG ONE LINER SALES LINE DOWN AND THE USER CAN UNDERSTAND IN 5 SECONDS WHAT WE CAN DO FOR THEM

**Mobile:**
- [ ] Nav bar spans full width (no gap on right)
- [ ] Hero text not cut off
- [ ] Buttons stack vertically on small phones
- [ ] Versus cards single column
- [ ] URL checker usable

---

### Status Pages

- [X] Public monitor page (`/s/{slug}`) loads without login
- [X] Shows: monitor name, status, uptime bars, recent incidents
- [NOT TESTED] "Powered by StatusRooster" footer visible (free users)
- [NOT TESTED] Non-existent slug returns 404 page (not a crash)

### Some other oddds and ends important things that need address after this round of QA
- what's up with "value clamping" per the API docs - why are we doing that - I got feedback that is bad? 
- when looking at the "logged out" API documention - the left hand nav panel isn't anchored to the top of the page - it goes away as you scroll down 

---
---

## Part 2: Monitor Setup Tour — Monitoring statusrooster.com

We're going to set up 4 real monitors for StatusRooster itself — one of each type.
This way StatusRooster monitors itself. Very meta.

---

### Monitor 1: HTTP Monitor — "Is the website up?"

This checks that the main website loads and returns a 200 status code every 60 seconds.

#### Via the UI:

1. Go to https://statusrooster.com/dashboard
2. Click the **"+ Add monitor"** button (top right)
3. You'll see the monitor type selector at the top. **Click "HTTP / HTTPS"** (it's probably already selected)
4. Fill in these fields:
   - **Name:** `Website - Homepage`
   - **URL:** `https://statusrooster.com`
   - **HTTP Method:** Leave as `GET` (we're just loading the page, not submitting anything)
   - **Expected Status Code:** Leave as `200` (200 means "OK, page loaded fine")
   - **Timeout:** Leave as `30` seconds (if the page takes longer than 30 seconds to load, consider it down)
   - **Keyword:** Type `StatusRooster` (this makes the monitor also check that the word "StatusRooster" appears in the page — catches cases where the page loads but shows an error or blank content)
   - **Response Threshold:** Type `5000` (this means "warn me if the page takes longer than 5 seconds to load" — it won't mark it as down, but you'll see it on the chart)
5. Scroll down to **Alert Channels:**
   - **Email:** Enter your email address (you'll get an email if the site goes down)
   - **Slack webhook:** If you have one, paste it here. If not, skip it.
   - **Webhook URL:** Skip for now
6. Scroll down to **Options:**
   - **Check Interval:** Leave as `60` seconds (checks every minute)
   - **Group:** Type `StatusRooster` (this groups all our self-monitoring monitors together)
   - **Public:** Toggle ON (this creates a public status page anyone can see)
7. Click **"Create monitor"**
8. You'll land on the monitor detail page. It'll show "Pending" status — within 60 seconds, the first check will run and you'll see it go green.

#### Via the API (same thing, one command):

Open your terminal and paste this:

```bash
curl -X POST https://statusrooster.com/api/v1/monitors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -d '{
    "name": "Website - Homepage",
    "url": "https://statusrooster.com",
    "monitor_type": "http",
    "expected_status_code": 200,
    "timeout": 30,
    "keyword": "StatusRooster",
    "response_threshold_ms": "5000",
    "alert_email": "your@email.com",
    "check_interval": 60,
    "group": "StatusRooster",
    "public": true
  }'
```

Replace `YOUR_API_KEY_HERE` with your actual API key (find it at /settings under API Keys).

**What you'll get back:** A JSON response with the monitor's ID, status "pending", and all the settings you just configured. Within 60 seconds, the checker will visit statusrooster.com from 4 regions around the world, verify it returns 200, check that "StatusRooster" appears in the response, and record the response time.

---

### Monitor 2: API Monitor — "Is the API working?"

This checks that the REST API is responding correctly by hitting the health endpoint and verifying the JSON response.

#### Via the UI:

1. Go to https://statusrooster.com/dashboard
2. Click **"+ Add monitor"**
3. Click **"JSON / API"** in the type selector
4. Fill in:
   - **Name:** `API - Health Check`
   - **URL:** `https://statusrooster.com/health`
   - **Expected Status Code:** `200`
   - **Timeout:** `10` (API should respond fast — 10 seconds is generous)
5. Scroll to **JSON Assertions** (this is the special part — you can check specific fields in the JSON response):
   - Click **"+ Add assertion"**
   - **Path:** `status` (this is the JSON field name — the health endpoint returns `{"status": "healthy"}`)
   - **Operator:** `equals`
   - **Value:** `healthy`
   - This assertion says: "check that the `status` field in the JSON response equals `healthy`"
6. Alert channels: same as before (your email)
7. Options:
   - **Check Interval:** `60`
   - **Group:** `StatusRooster`
   - **Public:** ON
8. Click **"Create monitor"**

#### Via the API:

```bash
curl -X POST https://statusrooster.com/api/v1/monitors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -d '{
    "name": "API - Health Check",
    "url": "https://statusrooster.com/health",
    "monitor_type": "json_api",
    "expected_status_code": 200,
    "timeout": 10,
    "json_assertions": [
      {"path": "status", "operator": "equals", "value": "healthy"}
    ],
    "alert_email": "your@email.com",
    "check_interval": 60,
    "group": "StatusRooster",
    "public": true
  }'
```

**Why this is useful:** A regular HTTP monitor just checks "did the page load?" This JSON/API monitor checks "did the API return the *right data*?" Your homepage could load fine while the API is broken — this catches that.

---

### Monitor 3: SSL Certificate Monitor — "Is our SSL cert about to expire?"

SSL certificates expire. If yours expires, browsers show a scary "NOT SECURE" warning and users can't access your site. This monitor watches the certificate and alerts you before it expires.

#### Via the UI:

1. Go to https://statusrooster.com/dashboard
2. Click **"+ Add monitor"**
3. Click **"SSL Certificate"** in the type selector
4. Fill in:
   - **Name:** `SSL - statusrooster.com`
   - **Domain:** `statusrooster.com` (just the domain, no https://)
   - **Expiry Threshold:** `30` (alert me 30 days before the cert expires — gives you plenty of time to renew)
5. Alert channels: your email
6. Options:
   - **Group:** `StatusRooster`
   - **Public:** ON
7. Click **"Create monitor"**

#### Via the API:

```bash
curl -X POST https://statusrooster.com/api/v1/monitors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -d '{
    "name": "SSL - statusrooster.com",
    "monitor_type": "ssl",
    "ssl_domain": "statusrooster.com",
    "ssl_expiry_threshold_days": 30,
    "alert_email": "your@email.com",
    "group": "StatusRooster",
    "public": true
  }'
```

**What happens:** The monitor connects to statusrooster.com on port 443, reads the SSL certificate, checks the expiry date, and reports back. If the cert has less than 30 days left, it goes to "warning" status. If it's already expired, it goes to "down."

---

### Monitor 4: Heartbeat Monitor — "Is the cron job running?"

This one works backwards from the others. Instead of StatusRooster visiting YOUR server, YOUR server pings StatusRooster. If the ping stops coming, StatusRooster alerts you.

We'll use this to monitor the `/cron/check` job — the thing that runs every minute to trigger all monitor checks. If that cron stops running, nothing gets checked, so this is critical.

#### Via the UI:

1. Go to https://statusrooster.com/dashboard
2. Click **"+ Add monitor"**
3. Click **"Heartbeat / Cron"** in the type selector
4. Fill in:
   - **Name:** `Cron - Check Runner`
   - **Expected Interval:** `120` seconds (the cron runs every 60 seconds, so we give it a 120-second window — if 2 minutes pass with no ping, something is wrong)
   - **Grace Period:** `60` seconds (extra buffer before marking as down — accounts for occasional slowness)
5. Alert channels: your email
6. Options:
   - **Group:** `StatusRooster`
7. Click **"Create monitor"**
8. **Important:** After creation, you'll see a **Ping URL** bar at the top of the detail page. It looks like:
   ```
   https://statusrooster.com/api/ping/m_XXXXX?token=YYYYYY
   ```
   Copy this URL. Your cron job needs to call this URL every time it runs successfully.

#### Via the API:

```bash
curl -X POST https://statusrooster.com/api/v1/monitors \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -d '{
    "name": "Cron - Check Runner",
    "monitor_type": "heartbeat",
    "heartbeat_interval": 120,
    "heartbeat_grace_period": 60,
    "alert_email": "your@email.com",
    "group": "StatusRooster"
  }'
```

The response will include `ping_url` — that's the URL your cron job needs to hit.

**How to wire it up:** To actually make this work, you'd add a ping call to the end of your `/cron/check` handler — after all checks complete successfully, it calls the heartbeat ping URL. That way, if the cron job stops running OR starts failing, the heartbeat goes stale and you get alerted. We can wire that up after you create the monitor.

---

### After Setup: What to Verify

Once all 4 monitors are created, go back to the dashboard and check:

1. [ ] All 4 monitors appear in the "StatusRooster" group
2. [ ] Filter by group "StatusRooster" — only these 4 show
3. [ ] Within 1-2 minutes, all should show green status (except heartbeat — it stays pending until it receives its first ping)
4. [ ] Click into the HTTP monitor — response chart starts populating
5. [ ] Click into the SSL monitor — shows cert issuer, expiry date, days remaining
6. [ ] Visit the public status page for any of the public monitors (`/s/{slug}`)
7. [ ] Try the "Check Now" button on the HTTP monitor — should show a quick result

---

### Quick Reference: Your 4 Monitors

| Monitor | Type | What it watches | Alerts when |
|---------|------|----------------|-------------|
| Website - Homepage | HTTP | statusrooster.com loads with 200 + keyword | Site down, keyword missing, or slow (>5s) |
| API - Health Check | JSON/API | /health returns `{"status":"healthy"}` | API broken or wrong response |
| SSL - statusrooster.com | SSL | Certificate expiry | Cert expires in <30 days |
| Cron - Check Runner | Heartbeat | Cron job pings every 2 min | Cron stops running |
