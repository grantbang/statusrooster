# StatusRooster — Split Test Plan
**Created:** March 10, 2026
**Purpose:** Efficiently validate every feature while building founder product intuition.

---

## Philosophy

**You test:** Anything where you need to *feel* the product — first impressions, flows, timing, friction, emotional response. You're not looking for bugs, you're looking for moments where you'd hesitate, get confused, or feel unsure as a user.

**Copilot tests:** Anything mechanical — does endpoint X return status code Y, does validation Z block bad input, do all 7 HTTP methods work. These are pass/fail with no subjective judgment needed.

---

## PART 1: YOUR MANUAL TESTING

> Estimated time: 90–120 minutes
> Mindset: You are a solo indie dev who just found StatusRooster. You've never seen it before.

---

### Session 1: First Touch (20 min)
*Goal: Feel what a brand new user feels*

Open an incognito/private browser window. You are NOT you — you are an indie dev named Alex who just launched a SaaS and needs monitoring.

**1.1 — Landing Page**
- [ ] Go to `https://statusrooster.com`
- [ ] Read the page top to bottom. Don't click anything yet. Ask yourself:
  - Do I understand what this does in the first 3 seconds?
  - Do I know who it's for?
  - Do I know what it costs?
  - Do I feel like this is for *me* (indie dev) or for some enterprise?
  - Is there a clear next step I want to take?
- [ ] Write down any moment of confusion, hesitation, or "meh" in a notebook. Even tiny ones. These are gold.

**1.2 — Public URL Checker**
- [ ] If the landing page has the URL checker teaser, paste your own SaaS URL (or `google.com`) and try it
- [ ] Note: Did the result make you want to sign up? Or was it just "cool, whatever"?
- [ ] Note: How fast did it respond? Did you feel like waiting?

**1.3 — Pricing Page**
- [ ] Click through to `/pricing`
- [ ] Read both tiers. Ask yourself:
  - Is the free tier generous enough that I'd actually try it?
  - Is Pro worth $9/mo to me?
  - What's the one feature that would make me upgrade?
  - Is anything confusing about what's included vs not?
- [ ] Write down your gut reaction to the price point

**1.4 — Signup**
- [ ] Click signup (use a fresh email you haven't used before — or `e2etest-MMDD@gmail.com`)
- [ ] Note: How many fields? How long did it take? Any friction?
- [ ] After signup, note: Where did I land? Do I know what to do next?
- [ ] You should be on an empty dashboard. Note: Does the empty state guide me or leave me lost?

---

### Session 2: First Monitor — The Critical 60 Seconds (15 min)
*Goal: Feel the "add your first URL" experience. This is the make-or-break moment for retention.*

Still logged in as your new free user.

**2.1 — Add Your First HTTP Monitor**
- [ ] Click "Add Monitor"
- [ ] Type your own real website/SaaS URL (or a URL you care about — NOT a test URL)
- [ ] Give it a real name
- [ ] Leave everything else at defaults
- [ ] Click "Add monitor"
- [ ] Note the time. How long from signup to first monitor? Under 30 seconds is great. Over 60 is a problem.
- [ ] Note: Was I tempted to change any default? Did any field confuse me?

**2.2 — Waiting for First Check**
- [ ] You're back on the dashboard. Your monitor says "pending"
- [ ] Click into the monitor detail
- [ ] Click "Check now"
- [ ] Note: How did it feel waiting? Was the feedback clear? Did I know it was working?
- [ ] When it comes back UP: Note your emotional response. Relief? Satisfaction? Nothing?

**2.3 — Add a Second Monitor (Different Type)**
- [ ] Go back and add a Heartbeat monitor
- [ ] Name it `My Cron Job` or something real-sounding
- [ ] After creation, note: Is the ping URL obvious? Would I know how to set up my cron job to ping it?
- [ ] Copy the ping URL and curl it from your terminal: `curl "PASTE_URL_HERE"`
- [ ] Check the dashboard — did it register?

**2.4 — Add an SSL Monitor**
- [ ] Add an SSL Cert monitor for `statusrooster.com` (or your own domain)
- [ ] Note: Is it clear what this does vs the HTTP monitor? Or does it feel redundant?

---

### Session 3: The Dashboard Experience (15 min)
*Goal: Feel what "managing monitors daily" is like*

**3.1 — Dashboard Overview**
- [ ] Look at the dashboard with 3+ monitors
- [ ] Note: Can I see at a glance — what's up, what's down, what needs attention?
- [ ] Note: Are the uptime bars useful? Can I tell the difference between "all good" and "had problems"?
- [ ] Note: Does the status strip at the top (uptime %, avg response, incidents) feel informative or cluttered?

**3.2 — Filtering and Search**
- [ ] Type part of a monitor name in the search box — does it filter?
- [ ] Click the status filters (Up, Down, Paused) — intuitive?
- [ ] If you have a group, try filtering by group

**3.3 — Quick Actions**
- [ ] Pause a monitor from the dashboard (click the ··· menu or pause button)
- [ ] Note: Was the feedback clear? Did it feel immediate?
- [ ] Resume it

---

### Session 4: Drill Into a Monitor (15 min)
*Goal: Feel what "investigating a problem" is like*

**4.1 — Monitor Detail Page**
- [ ] Click into your HTTP monitor's detail page
- [ ] Look at the status cards (Current Status, Last Check, MTBF)
- [ ] Note: Do I understand what MTBF means? (Most indie devs won't — is that okay?)
- [ ] Look at the uptime bars — switch between 24h / 7d / 30d
- [ ] Look at the response time chart — switch time ranges
- [ ] Note: Is this the right amount of data? Too much? Too little?

**4.2 — Force a Failure and Watch Recovery**
- [ ] Edit your HTTP monitor → change URL to `https://httpstat.us/500`
- [ ] Save → wait for cron (or "Check now")
- [ ] Watch it go DOWN. Note: How does it feel? Is the red alarming enough?
- [ ] Check your email for the DOWN alert. Note: Did it arrive? How fast? Is the email useful?
- [ ] Now edit the monitor → change URL back to the real one
- [ ] Wait for recovery. Note: Did you get a recovery email? How did it feel when it came back up?

**4.3 — Incident Detail**
- [ ] Go to the Incidents page
- [ ] Click into the incident you just created
- [ ] Note: Is the timeline clear? Do I understand what happened and when?
- [ ] Note: Is the "root cause" label useful? (e.g., "HTTP 500 Server Error")

---

### Session 5: Settings and API (10 min)
*Goal: Feel what "configuring your account" is like*

**5.1 — Settings Page**
- [ ] Go to Settings
- [ ] Note: Can I find everything I'd expect? (email, timezone, API keys, plan info)
- [ ] Generate an API key
- [ ] Note: Is the "copy it now, you won't see it again" warning clear?

**5.2 — Quick API Test**
- [ ] Open terminal and run:
  ```
  curl -s -H "X-API-Key: YOUR_KEY" https://statusrooster.com/api/v1/monitors | python3 -m json.tool
  ```
- [ ] Note: Does the response make sense? Is it what you'd expect?

**5.3 — Status Page**
- [ ] Make one of your monitors public (edit → toggle public ON, give it a slug)
- [ ] Visit the public status page URL
- [ ] Note: Would you embed this in your SaaS? Does it look trustworthy to YOUR users?
- [ ] Check the SVG badge: `https://statusrooster.com/badge/{monitor_id}.svg`
- [ ] Note: Would you put this in your README?

---

### Session 6: Upgrade Flow (10 min)
*Goal: Feel the billing experience*

**6.1 — Hit the Free Limit**
- [ ] As your free user, add monitors until you hit the 5-monitor limit
- [ ] Try to add a 6th
- [ ] Note: Is the upgrade prompt compelling or annoying?
- [ ] Note: Do you know exactly what Pro gives you that Free doesn't?

**6.2 — Upgrade to Pro (Stripe Test Mode)**
- [ ] Click the upgrade link
- [ ] Use test card `4242 4242 4242 4242`
- [ ] Complete the flow
- [ ] Note: Was the redirect smooth? Did your plan update immediately?
- [ ] Note: What's the first thing you want to do now that you're Pro?

**6.3 — Try a Pro Feature**
- [ ] Add a Slack webhook to a monitor (use a real Slack webhook if you have one, or just test the form)
- [ ] Set a custom check interval (e.g., 60s)
- [ ] Add a maintenance window
- [ ] Note: Did any of these feel harder than they should?

---

### Session 7: Mobile Quick Check (5 min)
*Goal: Just the pages real users will actually view on their phone*

Pull up your phone (or Chrome DevTools mobile mode).

- [ ] Landing page — does it look right, is the CTA tappable?
- [ ] Dashboard — can you see monitor status at a glance?
- [ ] A public status page — this is the one your USERS' users see on mobile

That's it for mobile. Don't test forms, settings, or admin on mobile — your users won't use those on a phone.

---

### After Your Manual Session: Write Down

Before you move on, spend 5 minutes writing answers to these:

1. **What was the single biggest moment of friction?**
2. **What was the single most satisfying moment?**
3. **If I were Alex the indie dev, would I pay $9/mo for this? Why or why not?**
4. **What's the one thing I'd want that's missing?**
5. **Did I ever feel lost or unsure what to do next?**

These answers are more valuable than 200 automated test results.

---

## PART 2: COPILOT AUTOMATED TESTS

> Give this entire section to Copilot. Prompt it with:
> `@workspace Read E2E_SPLIT_TEST_PLAN.md Part 2. Create a pytest test suite in tests/test_e2e.py that covers every automated test listed. Use httpx AsyncClient for API tests. Run against the production URL https://statusrooster.com. Use environment variable SR_API_KEY for the API key and SR_TEST_PASSWORD for the test account password.`

---

### Test File Structure

```
tests/
  conftest.py           # Fixtures (API key, base URL, httpx client, test accounts)
  test_e2e.py           # Main E2E test file (sections A–I)
```

### Key Fixtures Needed

```python
# conftest.py should provide:
# - base_url: str (from SR_BASE_URL env var, default https://statusrooster.com)
# - api_key: str (from SR_API_KEY env var — Pro user's API key)
# - client: httpx.AsyncClient (with base_url set)
# - pro_api_headers: dict ({"X-API-Key": api_key})
# - free_user_api_key: str (created during test setup via signup + key generation)
# - created_monitor_ids: list (track IDs for cleanup in teardown)
```

---

### A. Authentication Tests

```
Test ID | What to test | Expected
--------|-------------|----------
A.1  | POST /api/auth/login with valid credentials | 200, returns {token, user_id, email}
A.2  | POST /api/auth/login with wrong password | 401
A.3  | POST /api/auth/login with non-existent email | 401
A.4  | POST /api/auth/signup with existing email | 400, "Email already registered"
A.5  | POST /api/auth/signup with password < 8 chars | 400, "Password must be at least 8 characters"
A.6  | GET /dashboard without cookie | 302 redirect to /login
A.7  | GET /monitors/add without cookie | 302 redirect to /login
A.8  | GET /settings without cookie | 302 redirect to /login
A.9  | POST /api/auth/signup with invalid email format | 422 (Pydantic validation)
```

---

### B. Security Tests (P1 Verification)

```
Test ID | What to test | Expected
--------|-------------|----------
B.1  | POST /cron/check without X-Cron-Secret | 403
B.2  | POST /cron/check with User-Agent: Google-Cloud-Scheduler (no secret) | 403
B.3  | POST /cron/check with wrong X-Cron-Secret | 403
B.4  | POST /api/check-url with URL http://169.254.169.254/latest/meta-data/ | 400 with SSRF error
B.5  | POST /api/check-url with URL http://127.0.0.1 | 400 with SSRF error
B.6  | POST /api/check-url with URL http://10.0.0.1 | 400 with SSRF error
B.7  | POST /api/check-url — send 11 requests rapidly from same IP | 11th returns 429
B.8  | GET /api/ping/{heartbeat_monitor_id} without token param | 403
B.9  | GET /api/ping/{heartbeat_monitor_id}?token=WRONG | 403
B.10 | GET /api/ping/{heartbeat_monitor_id}?token=CORRECT | 200
```

---

### C. API CRUD Tests

```
Test ID | What to test | Expected
--------|-------------|----------
C.1  | GET /api/v1/monitors (with valid API key) | 200, returns list
C.2  | GET /api/v1/monitors (no API key) | 401
C.3  | GET /api/v1/monitors (invalid API key) | 401
C.4  | POST /api/v1/monitors — create HTTP monitor (minimal: name + url) | 201
C.5  | POST /api/v1/monitors — create JSON/API monitor with assertions | 201
C.6  | POST /api/v1/monitors — create heartbeat monitor | 201, response includes ping_url with token
C.7  | POST /api/v1/monitors — create SSL monitor | 201
C.8  | GET /api/v1/monitors/{id} | 200, correct monitor
C.9  | GET /api/v1/monitors/{fake_id} | 404
C.10 | PUT /api/v1/monitors/{id} — update name | 200, name changed
C.11 | PATCH /api/v1/monitors/{id} — update paused=true | 200
C.12 | DELETE /api/v1/monitors/{id} | 200, deleted=true
C.13 | GET /api/v1/monitors/{deleted_id} | 404
C.14 | GET /api/v1/monitors/{id}/checks?limit=5 | 200, ≤5 checks
C.15 | GET /api/v1/incidents | 200, returns list
C.16 | GET /api/v1/incidents/{id} | 200, returns incident
```

---

### D. Monitor Type Validation Tests

> These tests create monitors via API, then trigger a check via the cron endpoint (or "check now")
> and verify the check result. Some tests only verify creation succeeded.

```
Test ID | What to test | Expected
--------|-------------|----------
D.1  | Create HTTP monitor for https://httpstat.us/200, trigger check | is_up = true, status_code = 200
D.2  | Create HTTP monitor for https://httpstat.us/500, trigger check | is_up = false, status_code = 500
D.3  | Create HTTP monitor for https://httpstat.us/201 with expected_status=200, trigger check | is_up = false (201 ≠ 200)
D.4  | Create HTTP monitor with each method: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS | All return 201 (monitor created)
D.5  | Create HTTP monitor with basic_auth_user=admin, basic_auth_pass=secret for httpbin basic-auth endpoint, trigger check | is_up = true
D.6  | Create HTTP monitor with bearer_token="test-token-123" | 201, bearer_token stored on monitor doc
D.7  | Create HTTP monitor with follow_redirects=false for a 301 URL (e.g. http://google.com), trigger check | is_up = false (301 not followed, not 2xx)
D.8  | Create JSON/API monitor for httpbin.org/json, trigger check | is_up = true
D.9  | Create JSON/API with assertion: slideshow.author equals "Yours Truly", trigger check | is_up = true
D.10 | Create JSON/API with assertion: slideshow.title equals "WRONG", trigger check | is_up = false
D.11 | Create JSON/API — test operators: equals, not_equals, contains, not_contains, exists, not_exists | All return expected pass/fail
D.12 | Create heartbeat monitor, ping URL with correct token | 200, response includes status=up
D.13 | Create heartbeat monitor — don't ping — wait for cron check | status=down (overdue)
D.14 | Create SSL monitor for statusrooster.com, trigger check | is_up = true, ssl_expiry_days > 0
D.15 | Create SSL monitor for expired.badssl.com, trigger check | is_up = false (expired cert)
```

---

### E. Plan Enforcement Tests

```
Test ID | What to test | Expected
--------|-------------|----------
E.1  | Free user: create 6th monitor via API | 403 with limit message
E.2  | Free user: set check_interval via API (PUT/PATCH) | 403, "Custom check intervals require a Pro plan"
E.3  | Free user: create monitor with alert_slack_webhook via API | 201 but slack webhook silently empty
E.4  | Free user: update webhook_url via API (PUT/PATCH) | 403, "Webhook notifications require a Pro plan"
E.5  | Free user: update maintenance_windows via API (PUT/PATCH) | 403, "Maintenance windows require a Pro plan"
E.6  | Free user: create monitor with basic_auth_user via API | 201 but basic auth silently empty
E.7  | Free user: create monitor with custom_headers via API | 201 but custom headers silently empty
E.8  | Free user: update basic_auth_user via API (PUT/PATCH) | 403, "Basic Auth requires a Pro plan"
E.9  | Free user: update custom_headers via API (PUT/PATCH) | 403, "Custom request headers require a Pro plan"
E.10 | Free user: update alert_slack_webhook via API (PUT/PATCH) | 403, "Slack alerts require a Pro plan"
E.11 | Free user: create 2nd public status page | 403
E.12 | Pro user: create 11th public status page | 403
```

---

### F. Badge Tests

```
Test ID | What to test | Expected
--------|-------------|----------
F.1  | GET /badge/{public_monitor_id}.svg | 200, content-type: image/svg+xml
F.2  | GET /badge/{public_monitor_id}/status.svg | 200, SVG content
F.3  | GET /badge/{public_monitor_id}/response.svg | 200, SVG content
F.4  | GET /badge/{private_monitor_id}.svg | 200, shows "not found"
F.5  | GET /badge/FAKE_ID.svg | 200, shows "not found"
```

---

### G. Error Handling Tests

```
Test ID | What to test | Expected
--------|-------------|----------
G.1  | GET /nonexistent-page | 404 (custom HTML 404 page)
G.2  | GET /api/v1/nonexistent | 404 (JSON {"detail": ...})
G.3  | GET /monitors/FAKE_ID (authenticated) | 302 redirect with error flash
G.4  | GET /s/nonexistent-slug | 404
G.5  | GET /incidents/FAKE_ID (authenticated) | 404 or redirect
G.6  | POST /api/v1/monitors with empty body | 422 (Pydantic validation)
G.7  | POST /api/v1/monitors with name but no URL (http type) | 201 (url is optional in schema) — verify monitor created
G.8  | PUT /api/v1/monitors/{other_users_monitor_id} | 404 (not 403 — don't reveal existence)
G.9  | DELETE /api/v1/monitors/{other_users_monitor_id} | 404 (not 403)
G.10 | GET /api/v1/monitors/{other_users_monitor_id} | 404 (not 403)
```

---

### H. Status Page Tests

```
Test ID | What to test | Expected
--------|-------------|----------
H.1  | GET /s/{valid_public_slug} (no auth) | 200, renders status page HTML
H.2  | GET /s/{slug_of_private_monitor} | 404
H.3  | GET /s/nonexistent-slug | 404
H.4  | GET /status/{pro_user_id} (user has public monitors) | 200, aggregate page
H.5  | GET /status/{pro_user_id_no_public_monitors} | 404 ("No public monitors found")
H.6  | GET /status/{free_user_id} | 404 (aggregate is Pro-only)
H.7  | GET /status/{nonexistent_user_id} | 404
```

---

### I. Cleanup — Run After All Tests

```
Test ID | What to test | Expected
--------|-------------|----------
I.1  | Delete all monitors created during test run via API | All return 200
I.2  | Verify /api/v1/monitors returns empty or original state | Clean state
```

---

### Copilot Instructions for Test Creation

When you hand this to Copilot, include these instructions:

```
@workspace Create the test suite based on E2E_SPLIT_TEST_PLAN.md Part 2.

Rules:
1. Use pytest with pytest-asyncio and httpx.AsyncClient
2. Base URL: https://statusrooster.com (or SR_BASE_URL env var)
3. API key from SR_API_KEY env var (for Pro user test account)
4. Test account: SR_TEST_EMAIL / SR_TEST_PASSWORD env vars
5. Group tests into classes: TestAuth, TestSecurity, TestAPICrud, etc.
6. Each test should be independent (create what it needs, clean up after)
7. Use fixtures for shared state (API key, base URL, auth cookies)
8. For tests that need a monitor to exist, create it in a fixture and delete in teardown
9. Mark slow tests (ones that wait for cron) with @pytest.mark.slow
10. All assertions should have descriptive messages
11. Print the test ID (e.g., "B.1") in each test name for cross-referencing

API patterns to know:
- Auth endpoints: POST /api/auth/login, POST /api/auth/signup (JSON body)
- API v1: X-API-Key header, responses shaped as {"data": ..., "error": null}
- API errors: {"detail": {"data": null, "error": "message"}}
- Pydantic validation errors: 422 with {"detail": [...]}
- SSR pages (dashboard, monitors, settings): return 302 to /login if no cookie
- The err() helper raises HTTPException — all API errors come as {"detail": {"data": null, "error": "..."}}

For plan enforcement tests (Section E), you'll need a FREE user.
Either create one via /api/auth/signup, or use SR_FREE_EMAIL / SR_FREE_PASSWORD env vars.

DO NOT test:
- OAuth flows (requires browser interaction)
- Stripe checkout (requires browser + test cards)
- Responsive/mobile layout (visual, not API-testable)
- Admin dashboard (internal tool, tested manually)

Output: tests/conftest.py and tests/test_e2e.py
```

---

## Execution Order

```
Day 1 — Morning (you):
  Sessions 1-4 (landing → first monitor → dashboard → incident lifecycle)
  ≈ 65 minutes

Day 1 — Afternoon (Copilot):
  Generate test suite from Part 2
  Run tests, fix any failures
  ≈ 30 min to generate, 30 min to run and fix

Day 1 — Evening (you):
  Sessions 5-7 (settings, upgrade, mobile)
  ≈ 25 minutes

Day 1 — Night:
  Review Copilot test results
  Write down your 5 answers from the reflection exercise
  Decide: ship or fix?
```

---

## What "Done" Looks Like

**Manual (you):** You've felt every major flow, written down your friction points, and can honestly answer "would I pay $9/mo for this?"

**Automated (Copilot):** All tests in Part 2 sections A–I pass green. Any failures are either fixed or documented as "known issue, not blocking launch" with a reason.

**Ship when:** Zero manual blockers + zero automated P1 failures + you'd pay for your own product.
