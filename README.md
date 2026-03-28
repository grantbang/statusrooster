# StatusRooster

**Uptime monitoring for developers who ship.**

Monitor your app, your APIs, and the services your stack depends on. 100 monitors, 60-second checks from 4 global regions, full REST API — free forever. Pro at $9/mo when you need more.

[Website](https://statusrooster.com) · [API Docs](https://statusrooster.com/docs/api) · [Pricing](https://statusrooster.com/pricing) · [Status Page](https://statusrooster.com/s/statusrooster-com-d0f7a4)

<!-- TODO: Add screenshot of dashboard -->
<!-- ![Dashboard](docs/screenshots/dashboard.png) -->

---

## What You Get

### Four Monitor Types — All Free

- **HTTP** — Check any URL. Verify status codes, keywords, response time thresholds, custom headers, basic/bearer auth.
- **JSON / API** — Assert on response fields with JSONPath selectors. Catch APIs that return 200 with bad data. Supports GET, POST, PUT, PATCH.
- **Heartbeat / Cron** — Unique ping URL for your scheduled jobs. If your cron misses its window, you know immediately.
- **SSL Certificate** — Track cert expiry across your stack. Alert at 14, 7, and 3 days before expiration.

### Multi-Region Consensus

Every check runs from **US-East, US-West, Europe, and Asia** simultaneously. Results are aggregated via majority vote — a single region blip won't page you at 3am. Incident reports show exactly which regions saw the failure.

### Alerts That Actually Work

Email, Slack, webhooks (JSON POST), and SMS (Pro). Edge-triggered — you get one alert when something breaks and one when it recovers. No spam.

### Public Status Pages

Share a hosted status page with your users at `statusrooster.com/s/your-slug`. 30-day uptime history, live status, incident log. Pro users can add their logo, brand colors, and hide the "Powered by" footer.

### Full REST API

Create monitors, pull check data, wire monitoring into CI/CD. OpenAPI spec included. Free on every plan.

```bash
curl -X POST https://statusrooster.com/api/v1/monitors \
  -H "X-API-Key: sr_live_abc123" \
  -d '{"url": "https://api.stripe.com", "name": "Stripe API"}'
```

---

## Why I Built This

I'm Grant — a CPA by training, with Big 4 audit and blue-chip corporate accounting on my resume, followed by years in technical data governance and solution architecture. I've spent my career at the intersection of data, process, and systems.

I'm someone who builds things. Woodworking, a custom Harley, raised on a farm where you fix what's broken with whatever you've got. That same instinct carried into my professional life — I built a data catalog web app and a certification tracking app at my day job, automated SAP GUI workflows with VBA, implemented Alteryx processes, wrote more Excel macros than I can count. Not a traditional developer, but someone who's been solving real problems with code for a long time. The tooling has finally caught up to a point where people with deep functional knowledge can just build what they need — and I think that's a good thing.

StatusRooster started because I wanted to build a real product — not a landing page, not a waitlist, not something chasing a trend. Uptime monitoring is an evergreen problem: servers crash, deploys break things, SSL certs expire, cloud providers have outages. If your server goes down, any monitoring code on that server goes down with it. You need an external service watching from the outside. That structural reality isn't going away.

I'm not trying to compete with the UptimeRobots of the world, and I'm not trying to get rich quick. I want to build a useful tool that people actually rely on, get enough paid subscribers to cover infrastructure costs, and keep shipping features. That's it.

This entire application — every line of code, every deploy, every production bug fix — was built with AI-assisted development using [Claude Code](https://claude.ai/claude-code). I'm transparent about that because I think it's the future: domain experts who understand problems deeply, shipping production software with AI as a force multiplier.

But AI-assisted doesn't mean AI-autonomous. I've spent countless hours manually testing every flow, clicking through every page, tweaking copy, catching edge cases the AI missed, and making judgment calls about what to ship and what to rework. Claude writes the code — I decide what gets built, verify it actually works, and own every line that hits production. The AI is the tool. The product decisions, the QA, and the accountability are mine.

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Web framework** | Python / FastAPI | Async-native, handles API + SSR in one service |
| **Rendering** | Jinja2 (server-side) | No frontend framework. JS only for charts and AJAX. |
| **Database** | Google Firestore | NoSQL document store, real-time capable |
| **Hosting** | Google Cloud Run | 4 regions, scales to zero, pennies at low traffic |
| **Scheduling** | Google Cloud Scheduler | Triggers `/cron/check` every 60 seconds |
| **CI/CD** | GitHub Actions | Push to main → test → build → deploy to Cloud Run |
| **Email alerts** | SendGrid | Transactional email API |
| **SMS alerts** | Twilio | Pro tier, ~$0.008/message |
| **Payments** | Stripe Checkout + Webhooks | Hosted payment flow, subscription management |
| **Charts** | Chart.js | Response time graphs, per-region overlays |
| **SSL/TLS** | Google-managed certs | Auto-provisioned on Cloud Run custom domain |

### Architecture

```
Cloud Scheduler (every 60s)
    │
    ▼
Primary App — Cloud Run (us-east1)
    ├── /cron/check → for each due monitor:
    │     ├── Dispatch to 3 regional workers (parallel)
    │     ├── Run local check (us-east1)
    │     ├── Aggregate via majority vote (3 of 4 must agree)
    │     ├── Update monitor doc (status, uptime bars, response times)
    │     └── On status change → create incident, fire alerts
    │
    ├── Web app (dashboard, monitor detail, settings)
    ├── Public API v1 (API-key auth)
    └── Status pages (/s/{slug})

Regional Workers — Cloud Run
    ├── us-west1
    ├── europe-west1
    └── asia-east1
    │
    └── Shared: checker_core/ (pure check logic, zero DB imports)
```

**Key design decisions:**

- **SSR-first** — Every page is server-rendered HTML. No React, no Vue, no build step. JavaScript is only for Chart.js graphs, AJAX actions, and client-side filtering.
- **Pre-computed dashboards** — Monitor documents hold `daily_uptime_bars`, `hourly_uptime_bars`, `uptime_percent`, `last_response_by_region`. The dashboard loads by reading monitor docs only — zero queries to the checks collection.
- **Worker isolation** — `checker_core/` is a pure Python library with no database imports. Workers are stateless HTTP services that accept a batch of URLs and return results. They can be deployed, scaled, and updated independently.
- **Edge-triggered alerts** — Flags on each monitor doc (`keyword_failing`, `threshold_failing`, `ssl_expiry_alerted_days`) ensure alerts fire once on state change, not on every check cycle.

### Security

- SSRF protection blocks all private/reserved IP ranges in outbound checks
- JWT secret validated on startup — app refuses to boot with default value in production
- Heartbeat monitors use `secrets.token_urlsafe(32)` ping tokens
- Rate limiting on public endpoints (URL checker, check-now)
- Cron endpoints authenticated via `X-Cron-Secret` header
- Worker endpoints authenticated via `X-Worker-Secret` header

---

## Roadmap

### Shipping Now

- **Auto-Discovery** — Enter a domain, we scan sitemap.xml, robots.txt, crawl links, and probe common paths (/api/health, /graphql, /.well-known). Select which endpoints to monitor, bulk-create in one click.

### Planned

- **Repository Ingester** — Connect a GitHub repo, we parse route files (Express, FastAPI, Rails, Next.js) and surface every endpoint worth monitoring. Zero manual URL entry.
- **Synthetic Checks** — Multi-step flows (login → navigate → assert). Catch broken user journeys, not just broken servers.
- **Team Accounts** — Shared dashboards, role-based access, on-call rotation. For when your side project becomes a real company.

---

## Pricing

| | Free | Pro — $9/mo |
|---|---|---|
| **Monitors** | 100 | 200 |
| **Check interval** | 60 seconds | 60 seconds |
| **Regions** | 4 | 4 |
| **Monitor types** | All 4 | All 4 |
| **Alerts** | Email, Slack, Webhook | + SMS |
| **Status pages** | 10 (with "Powered by") | 10 (custom branding, remove footer) |
| **History** | 30 days | 90 days |
| **API access** | Full | Full |
| **Aggregate status page** | — | Included |

[See full pricing →](https://statusrooster.com/pricing)

---

## Quick Start

```bash
# 1. Sign up (30 seconds, no credit card)
https://statusrooster.com/signup

# 2. Add your first monitor via the dashboard
#    or use the API:
curl -X POST https://statusrooster.com/api/v1/monitors \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.com",
    "name": "Production",
    "alert_email": "you@example.com"
  }'

# 3. That's it. We start checking in < 60 seconds.
```

---

## Project Structure

```
statusrooster/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py             # Settings, env vars, worker config
│   ├── routers/
│   │   ├── pages.py          # SSR routes + AJAX endpoints
│   │   ├── api_v1.py         # Public REST API (API-key auth)
│   │   ├── cron.py           # Cloud Scheduler handlers
│   │   └── heartbeat.py      # Heartbeat ping endpoint
│   ├── models/               # Firestore data access (monitor, check, incident, user)
│   ├── services/
│   │   ├── checker.py        # Check orchestrator (dispatch, aggregate, store)
│   │   └── alerts.py         # Email, Slack, SMS, webhook dispatch
│   ├── templates/            # Jinja2 templates (SSR)
│   └── static/               # CSS, favicon, images
├── checker_core/             # Pure check logic (shared with workers)
├── worker/                   # Regional worker service
├── tests/
│   ├── test_e2e.py           # 80+ E2E tests against live API
│   └── test_functional.py    # 38 functional tests
├── .github/workflows/        # CI/CD (test → build → deploy)
└── PROJECT_STATUS.md         # Sprint tracker
```

---

## Help Me Build This

If any of this resonates with you — the idea that domain experts can ship real software, that indie tools deserve to exist alongside the big players, that a solo builder can put out something worth using — I'd love your help.

- **Try it out.** Sign up, add a few monitors, kick the tires.
- **Try to break it.** Seriously. Find bugs, hit edge cases, test on weird browsers. I want to know.
- **Tell me what's missing.** What would make this useful enough that you'd actually switch from whatever you're using now?
- **Share it.** If you know someone who'd find it useful, send them the link.

You can reach me at [support@statusrooster.com](mailto:support@statusrooster.com) or open an issue on this repo.

---

## License

Proprietary. Source code is public for transparency, not for redistribution. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with focus, sawdust under the fingernails, and <a href="https://claude.ai/claude-code">Claude Code</a>.
</p>
