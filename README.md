# StatusRooster

**Uptime monitoring for indie developers, not enterprises.**

Know when your site goes down. Before your customers do.

---

## What Is This

StatusRooster is a simple, fast, no-bullshit uptime monitoring service. You add a URL, we check it every 60 seconds from four global regions, and we alert you the instant it goes down — via email, Slack, webhook, or SMS. Every account gets a free hosted public status page.

No dashboards with 47 tabs. No enterprise sales calls. No "contact us for pricing." Just monitoring that works.

### Monitor Types

- **HTTP** — check any URL, verify status codes, keywords, response thresholds, custom headers, auth
- **JSON/API** — monitor API endpoints with JSON path assertions, supports all HTTP methods (GET/POST/PUT/PATCH)
- **Heartbeat/Cron** — monitor scheduled jobs via ping URL — if your cron stops hitting the endpoint, we alert you
- **SSL Certificate** — track certificate expiry, alert at configurable thresholds before they expire

### Multi-Region Verification

Every check runs from **four regions** (US East, US West, Europe, Asia) simultaneously. Results are aggregated via majority-vote consensus — no false alarms from a single region blip. Incident reports show per-region corroboration so you can see exactly which regions were affected.

---

## Why I Built This

### The Backstory

I'm Grant — a CPA with Big 4 accounting experience and blue-chip technical data governance and solution architecture background. I'm always interested in data and process. Over the past few months I've taught myself to ship web applications using AI-assisted development on a Python/FastAPI/GCP stack. I can take an idea from nothing to deployed on Google Cloud Run in a day.

### Why Uptime Monitoring

1. **The problem is permanent.** Servers crash. Deploys break things. DNS expires. Cloud providers have outages. This will never stop happening, which means demand never goes away. Not trend-dependent. Not crypto. Not AI hype. Infrastructure is evergreen.

2. **You can't self-solve it.** If your server crashes, any monitoring code on that server crashes with it. You *need* an external service on separate infrastructure watching from the outside. This isn't a "just build it yourself" problem — it's structurally impossible to DIY properly.

3. **The indie lane is wide open.** UptimeRobot has 2M+ users but feels like it was built in 2012. BetterUptime is beautiful but starts at $20+/month and targets teams. Pingdom is enterprise bloat. There's a clear gap for a clean, modern, $9/month tool for freelancers, indie devs, and small business owners.

4. **Built-in growth engine.** Every public status page has a "Powered by StatusRooster" footer. Users' customers see it, some have their own sites, they sign up. Same viral loop that grew Calendly and Typeform.

### What I'm Optimizing For

- **A product that works.** Not a landing page. Not a waitlist. A thing people use every day because it solves a real problem.
- **Real users.** People who signed up because they needed this, not because I tricked them with an ad.
- **A foundation that scales.** If it works at 100 users, it works at 10,000. The architecture doesn't change.
- **Proof I can ship.** Going from "I'm learning to code" to "I built a SaaS with paying customers" changes every conversation going forward.

---

## The Product

### Pricing

**Free tier** — generous, this is the top of funnel:
- **100 monitors** (UptimeRobot free = 50)
- **60-second check intervals** (UptimeRobot free = 5 minutes. We're 5x faster.)
- **Email + Slack + webhook alerts**
- **Multi-region checks from 4 regions**
- **10 public status pages**
- **30 days of history**
- **All monitor types** (HTTP, JSON/API, Heartbeat, SSL)

**Pro — $9/month:**
- **500 monitors**
- **30-second check intervals**
- **SMS alerts** (Twilio)
- **90 days of history**
- **Aggregate status page** (all monitors on one page)
- **Custom branding** (logo, colors, hide "Powered by")

### Who It's For

- **Freelance web developers** managing 5-15 client sites
- **Indie SaaS founders** running a product with real users
- **Small e-commerce stores** where downtime = lost revenue
- **Agencies** managing client infrastructure

### Who It's NOT For

- Enterprise teams with 500+ services (use Datadog)
- People who need APM, log aggregation, or distributed tracing
- Anyone who wants a 45-minute onboarding call

---

## Architecture

### Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **Web App / API** | Python, FastAPI | Async-native, fast to build, fast to run |
| **Templates** | Jinja2 (server-rendered) | No frontend framework needed, fast page loads |
| **Hosting** | Google Cloud Run (4 regions) | Scale to zero, pennies to run, no server management |
| **Database** | Google Firestore | Fast reads, scalable, generous free tier |
| **Scheduler** | Google Cloud Scheduler | Triggers check cycle every minute |
| **Email Alerts** | SendGrid | 100/day free, simple API |
| **SMS Alerts** | Twilio | $0.0079/SMS, Pro tier only |
| **Payments** | Stripe Checkout | Hosted payment page, webhook-driven |
| **Charts** | Chart.js | Response time graphs, per-region overlays |

### System Design

Three deployable units:

```
Cloud Scheduler (every 60s)
    |
    v
Cloud Run: Primary App (us-east1)
    |
    |-- /cron/check
    |     |-- For each monitor due for check:
    |     |     |-- Dispatch to 3 regional workers (parallel)
    |     |     |-- Run local check (us-east1)
    |     |     |-- Aggregate 4 results via majority vote
    |     |     |-- Store result, update monitor status
    |     |     |-- If status changed: create incident, fire alerts
    |     |
    |-- Web App (dashboard, detail pages, settings)
    |-- Public API v1 (API-key authenticated)
    |-- Status pages (/s/{slug}, /status/{user_id})
    |
Cloud Run: Regional Workers
    |-- us-west1    (worker/main.py)
    |-- europe-west1
    |-- asia-east1
    |
    Shared: checker_core/ (pure check logic, zero DB dependencies)
```

**Key design decisions:**
- **SSR-first** — all pages are server-rendered Jinja2. JavaScript only for charts, AJAX actions, and client-side filtering. No React, no Vue, no HTMX.
- **Pre-computed dashboards** — monitor Firestore docs hold `daily_uptime_bars`, `uptime_percent`, `last_response_by_region`, etc. Dashboard reads zero queries from the checks collection.
- **Worker isolation** — `checker_core/` is a pure library with no Firestore imports. Workers are stateless HTTP services that accept a batch of monitors and return results.

### Data Model (Firestore)

```
users/{user_id}
    email, password_hash, plan, stripe_customer_id, created_at, ...

monitors/{monitor_id}
    user_id, url, name, monitor_type, check_interval, status,
    last_checked, last_status_code, last_response_ms, uptime_percent,
    daily_uptime_bars[], last_response_by_region{}, region_results[], ...

checks/{check_id}
    monitor_id, timestamp, status_code, response_ms, is_up,
    response_ms_by_region{}, regions_checked, regions_up

incidents/{incident_id}
    monitor_id, user_id, started_at, resolved_at, duration_seconds,
    cause, region_results[], failure_response_body, ...
```

---

## Competitive Landscape

| Competitor | Price | Weakness | Our Angle |
|-----------|-------|----------|-----------|
| UptimeRobot | Free / $7/mo | Stale UI, 5-min free checks, 50 free monitors | 60s checks, 100 monitors, modern UI |
| BetterUptime | $20+/mo | Expensive for solo devs | $9/mo, indie-focused |
| Pingdom | $15+/mo | Enterprise bloat | Simple, no BS |
| Hetrix Tools | Free / $10/mo | Poor UX, limited awareness | Better UX + distribution |
| Datadog | $15+/host/mo | Overkill for small sites | 1/10th the complexity |

**We don't compete with Datadog.** We compete with "I should probably monitor my site but haven't set anything up yet." Our real competition is inaction.

---

## Development

```bash
# Start dev server
source venv/bin/activate
uvicorn app.main:app --reload --port 8080

# Run E2E tests (need a valid API key)
SR_API_KEY=sr_xxx pytest tests/test_e2e.py -v --asyncio-mode=auto -k "not slow"

# Run functional tests
SR_API_KEY=sr_xxx pytest tests/test_functional.py -v --asyncio-mode=auto
```

Local dev uses production Firestore (same project). Cloud Scheduler cron and multi-region workers don't run locally — set `WORKER_SECRET=""` in `.env` to fall back to local-only checks.

### Key Files

| Path | Purpose |
|------|---------|
| `app/main.py` | FastAPI entry point |
| `app/routers/pages.py` | All SSR page routes + AJAX endpoints |
| `app/routers/api_v1.py` | Public API v1 (API-key authed) |
| `app/routers/cron.py` | Cloud Scheduler endpoints |
| `app/services/checker.py` | Check orchestrator — multi-region dispatch + aggregation |
| `app/services/alerts.py` | Email, Slack, SMS, webhook dispatch |
| `checker_core/__init__.py` | Pure check logic (HTTP, JSON, SSL, heartbeat) |
| `worker/main.py` | Regional worker service |
| `app/static/style.css` | Unified CSS with design tokens |

### Project Docs

| File | Purpose |
|------|---------|
| `CLAUDE.md` | AI coding conventions, architecture reference |
| `PROJECT_STATUS.md` | Sprint tracker — what's done, what's next |

---

## Growth Strategy

1. **Status page viral loop** — every public page = passive referral. "Powered by StatusRooster" compounds over time.
2. **SEO content** — "monitor website uptime free", "status page for SaaS", "UptimeRobot alternatives"
3. **Free tool strategy** — standalone SSL checker page, ranks on Google, funnels to signup
4. **Launch channels** — Hacker News (Show HN), Reddit (r/SideProject, r/webdev), IndieHackers, Product Hunt
5. **Directory listings** — G2, AlternativeTo, StackShare

---

## Cost Structure

| Users | Cloud Run | Firestore | SendGrid | Twilio | Total |
|-------|-----------|-----------|----------|--------|-------|
| 100 | ~$2/mo | ~$0 | $0 | ~$1 | **~$3/mo** |
| 500 | ~$8/mo | ~$3/mo | $0 | ~$3 | **~$14/mo** |
| 1,000 | ~$15/mo | ~$8/mo | $15/mo | ~$5 | **~$43/mo** |

At 1,000 users with ~100 paid at $9/mo = **$900 MRR on $43 costs = 95% margin.**

GCP costs are tracked in real-time via BigQuery billing export on the admin dashboard.

---

*Built with focus, coffee, and Claude Code.*
