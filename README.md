# StatusRooster 🐓

**Uptime monitoring for indie developers, not enterprises.**

Know when your site goes down. Before your customers do.

---

## What Is This

StatusRooster is a simple, fast, no-bullshit uptime monitoring service. You add a URL, we check it every 60 seconds, and we alert you the instant it goes down — via email, Slack, or SMS. Every account gets a free hosted public status page.

That's it. No dashboards with 47 tabs. No enterprise sales calls. No "contact us for pricing." Just monitoring that works.

---

## Why I'm Building This

### The Backstory

I'm Grant — CPA by training, builder by obsession. Over the past few months I've taught myself to ship web applications using AI-assisted development ("vibe coding") on a Python/FastAPI/GCP stack. I can take an idea from nothing to deployed on Google Cloud Run in a day.

Before this, I spent a couple weeks deep in affiliate marketing — got approved on CJ and MaxBounty, ran Facebook ad campaigns for insurance leads, tested VPN commission models. I learned a ton: I can run FB ads well (12%+ click-through rate, which is genuinely elite), I understand conversion funnels, and I can deploy and iterate fast. But the fundamental economics of affiliate marketing at small scale on paid social don't work. The payouts are too low, the margins are razor-thin, and you're always one platform change away from zero.

What I realized: **I don't care that much about the money. I care about building something real — a product with genuine utility, actual users, and the potential to scale if I want to.** The affiliate experience taught me the tools. Now I want to use them on something worth building.

### Why Uptime Monitoring

1. **The problem is permanent.** Servers crash. Deploys break things. DNS expires. Cloud providers have outages. This will never stop happening, which means demand never goes away. Not trend-dependent. Not crypto. Not AI hype. Infrastructure is evergreen.

2. **You can't self-solve it.** If your server crashes, any monitoring code on that server crashes with it. You *need* an external service on separate infrastructure watching from the outside. This isn't a "just build it yourself" problem — it's structurally impossible to DIY properly. Even developers who could build a checker still need to deploy and maintain a second, separate system just for monitoring. Most people would rather pay $9/month.

3. **The indie lane is wide open.** UptimeRobot has 2M+ users but feels like it was built in 2012. BetterUptime is beautiful but starts at $20+/month and targets teams. Pingdom is enterprise bloat. There's a clear gap for a clean, modern, $9/month tool for freelancers, indie devs, and small business owners.

4. **Built-in growth engine.** Every public status page has a "Powered by StatusRooster" footer. Users' customers see it, some have their own sites, they sign up. Same viral loop that grew Calendly and Typeform.

5. **Perfect founder-market fit.** I already know the stack (FastAPI, Cloud Run, Firestore). The core architecture is simple. I can ship an MVP in 10 days and iterate from there.

### What I'm Optimizing For

Honestly? I care less about hitting $5K/month than I do about building something real. I want:

- **A product that works.** Not a landing page. Not a waitlist. A thing people use every day because it solves a real problem.
- **Real users.** People who signed up because they needed this, not because I tricked them with an ad.
- **A foundation I can scale.** If it works at 100 users, it works at 10,000. The architecture doesn't change.
- **Proof I can ship.** Going from "I'm learning to code" to "I built a SaaS with paying customers" changes every conversation going forward.

The revenue is a byproduct. If I build something useful and get it in front of the right people, the revenue follows.

---

## My Skillset

| Skill | Level | Notes |
|-------|-------|-------|
| Python / FastAPI | Intermediate | Can build full APIs, Jinja2 templates, deploy to production |
| GCP (Cloud Run, Firestore) | Intermediate | Have used Firestore at work, deployed multiple apps to Cloud Run |
| Facebook/Meta Ads | Strong | 12%+ CTR on campaigns, understand targeting/funnels/pixels |
| Frontend (HTML/CSS/JS) | Functional | Server-rendered pages, no React — clean and simple |
| AI-Assisted Dev | Strong | Can use Copilot/GPT to ship features fast and debug effectively |
| Business/Finance | CPA | Understand unit economics, margins, and what "profitable" actually means |

**What I'm NOT:** A senior engineer. I'm not going to build a distributed systems masterpiece. I'm going to build a clean, simple product that works, using managed services (Cloud Run, Firestore, SendGrid, Stripe) to handle the hard parts.

---

## The Product

### Positioning

> **"Monitoring built for indie developers, not enterprises."**

We win by being simpler, faster, cleaner, and friendlier — not by having more features.

### Free Tier (Generous — This Is The Top of Funnel)

- **5 monitors**
- **60-second check intervals** (UptimeRobot free = 5 minutes. We're 5x faster.)
- **Email + Slack alerts**
- **Public status page**
- **7 days of history**

### Pro — $9/month (What Makes People Upgrade)

- **Unlimited monitors** ← *the trigger — people hit the 5-monitor limit fast*
- **30-second check intervals**
- **SMS alerts** (Twilio)
- **90 days of history**
- **Custom domain status page** (`status.yoursite.com`)
- **Multiple alert contacts** (free = just you; pro = notify your whole team)
- **SSL expiration monitoring**
- **Cron/job monitoring** ("alert me if this endpoint doesn't get hit every hour")

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
| **Web App / API** | Python, FastAPI | Already know it, fast to build, async-native |
| **Hosting** | Google Cloud Run | Scale to zero, pennies to run, no server management |
| **Database** | Google Firestore | Fast reads, scalable, generous free tier, used it at work |
| **Check Scheduler** | Google Cloud Scheduler | Triggers check endpoint on interval, free for 3 jobs |
| **Email Alerts** | SendGrid | 100/day free, simple API, reliable |
| **Slack Alerts** | Slack Incoming Webhooks | User provides URL, we POST to it, free |
| **SMS Alerts** | Twilio | $0.0079/SMS, Pro tier only |
| **Payments** | Stripe Checkout | Hosted payment page, ~20 lines of code |
| **Templates** | Jinja2 | Server-rendered, fast, no frontend framework needed |
| **Charts** | Chart.js | Response time graphs, lightweight |

### System Diagram

```
Cloud Scheduler (every 60s)
    │
    ▼
Cloud Run: /cron/check
    │
    ├── For each monitor:
    │     ├── HTTP GET → target URL
    │     ├── Record result → Firestore (checks collection)
    │     ├── Update monitor status (up/down, response_ms, uptime%)
    │     │
    │     └── If status changed:
    │           ├── UP → DOWN: Create incident, send alerts
    │           └── DOWN → UP: Close incident, send recovery alert
    │
    ▼
Cloud Run: FastAPI Web App
    ├── / (marketing/landing page)
    ├── /dashboard (user's monitors, charts)
    ├── /s/{slug} (public status page)
    ├── /api/monitors (CRUD)
    ├── /api/billing (Stripe checkout/webhook)
    └── /health
```

### Data Model (Firestore)

```
users/{user_id}
    email, password_hash, plan, stripe_customer_id, monitors_count, created_at

monitors/{monitor_id}
    user_id, url, name, check_interval, status, last_checked,
    last_status_code, last_response_ms, uptime_percent,
    checks_total, checks_failed, alert_email, alert_slack_webhook,
    alert_sms, public, slug, created_at

checks/{check_id}
    monitor_id, timestamp, status_code, response_ms, is_up

incidents/{incident_id}
    monitor_id, user_id, started_at, resolved_at, duration_seconds,
    cause, alert_sent
```

### Cost Structure

| Users | Cloud Run | Firestore | SendGrid | Twilio | Total |
|-------|-----------|-----------|----------|--------|-------|
| 100 | ~$2/mo | ~$0 | $0 | ~$1 | **~$3/mo** |
| 500 | ~$8/mo | ~$3/mo | $0 | ~$3 | **~$14/mo** |
| 1,000 | ~$15/mo | ~$8/mo | $15/mo | ~$5 | **~$43/mo** |

At 1,000 users with ~100 paid at $9/mo = **$900 MRR on $43 costs = 95% margin.**

---

## Build Plan

### Phase 1: Core Engine (Days 1-4)

**Goal:** A working monitoring system that checks URLs and sends alerts.

- [ ] **Day 1:** Project scaffolding — FastAPI structure, Firestore client, auth (email/password + JWT), base template, deploy skeleton to Cloud Run
- [ ] **Day 2:** Monitor CRUD + check engine — create/read/update/delete monitors, HTTP checker with timeout, Cloud Scheduler integration, false positive prevention (retry once before alerting)
- [ ] **Day 3:** Alert system — SendGrid email alerts, Slack webhook alerts, incident creation/resolution, alert deduplication
- [ ] **Day 4:** Dashboard — login/signup pages, monitor list view, add/edit/delete forms, response time chart (Chart.js), alert settings

**Day 4 Checkpoint:** Can sign up, add a URL, see it being checked, get an email when it goes down, see it come back up. Working product.

### Phase 2: Status Pages + Billing (Days 5-8)

- [ ] **Day 5:** Public status pages — `/s/{slug}`, 90-day uptime bars, incident history, "Powered by StatusRooster" footer
- [ ] **Day 6:** Stripe billing — Checkout integration, webhook for plan updates, plan enforcement (5-monitor limit on free), upgrade prompts
- [ ] **Day 7:** Marketing/landing page — hero, features, pricing table, FAQ
- [ ] **Day 8:** Polish — mobile responsive pass, error states, rate limiting, 404/500 pages, meta tags

**Day 8 Checkpoint:** Full product. Sign up, monitor sites, get alerts, status page, upgrade to paid, manage subscription. Ready for users.

### Phase 3: Launch (Days 9-10)

- [ ] **Day 9:** SSL expiration monitoring (bonus feature), end-to-end testing, self-monitoring setup, write Show HN draft, screenshots
- [ ] **Day 10:** �� Launch — Hacker News, Reddit, IndieHackers. Be in comments all day. Fix bugs in real-time.

### Phase 4: Post-Launch (Days 11-14)

- [ ] **Days 11-12:** Fix bugs from real user feedback, add most-requested small features
- [ ] **Days 13-14:** SEO blog posts, free SSL checker tool page, submit to directories (AlternativeTo, G2, Product Hunt)

---

## Growth Strategy

### Launch Channels (Week 1-2)
1. **Hacker News (Show HN)** — #1 channel for dev tools. Target: 50-200 signups.
2. **Reddit** — r/SideProject, r/webdev, r/SaaS — authentic build story.
3. **IndieHackers** — product listing + building-in-public post.
4. **Product Hunt** — week 3, after initial bugs fixed.

### Sustained Growth (Month 1+)
1. **SEO content** — "monitor website uptime free", "status page for SaaS", "UptimeRobot alternatives"
2. **Status page growth loop** — every public page = passive referral. Compounds over time.
3. **Free tool strategy** — standalone SSL checker page, ranks on Google, funnels to signup.
4. **Directory listings** — G2, AlternativeTo, StackShare — steady trickle.
5. **Facebook Ads (Month 2+)** — only after organic proves the unit economics. I already know how to get 12%+ CTR.

---

## Revenue Projections (Realistic)

| Timeframe | Free Users | Paid ($9/mo) | MRR |
|-----------|-----------|-------------|-----|
| Week 3 | 50-200 | 5-15 | $45-135 |
| Month 2 | 200-400 | 15-35 | $135-315 |
| Month 4 | 500-800 | 50-80 | $450-720 |
| Month 6 | 1,000-1,500 | 100-150 | $900-1,350 |
| Year 1 | 2,000-3,000 | 200-350 | $1,800-3,150 |

**Probability (honest):**
- 60% → $200-1,000/month (real product, real users, real credential)
- 30% → $1K-5K/month (meaningful side income)
- 8% → $5K-20K/month (could go full-time)
- 2% → becomes very large

---

## Expansion Path (Post-MVP)

StatusRooster starts as uptime monitoring. The long-term play is lightweight observability for indie developers:

- SSL expiration monitoring (launch feature)
- Cron/job monitoring
- Keyword/content monitoring
- Multi-region checks (US + EU)
- API health monitoring (POST, check response body)
- Incident tracking with public updates
- Webhook reliability monitoring

Each feature increases switching cost. None gets built until users ask for it.

---

## Competitive Landscape

| Competitor | Price | Weakness | Our Angle |
|-----------|-------|----------|-----------|
| UptimeRobot | Free / $7/mo | Stale UI, 5-min free checks | 60s checks free, modern UI |
| BetterUptime | $20+/mo | Expensive for indies | $9/mo, solo-founder focused |
| Pingdom | $15+/mo | Enterprise bloat | Simple, no BS |
| Hetrix Tools | Free / $10/mo | Unknown, bad marketing | Better brand + distribution |
| Datadog | $15+/host/mo | Overkill for small sites | 1/10th the complexity |

**We don't compete with Datadog.** We compete with "I should probably monitor my site but haven't set anything up yet." Our real competition is inaction.

---

## Current Status

| Phase | Status |
|-------|--------|
| Phase 1: Core Engine (Days 1-4) | 🔲 Not started |
| Phase 2: Status Pages + Billing (Days 5-8) | 🔲 Not started |
| Phase 3: Launch (Days 9-10) | 🔲 Not started |
| Phase 4: Post-Launch (Days 11-14) | 🔲 Not started |

**Start date:** February 25, 2026
**Target launch:** March 7, 2026

---

*Built with 🐓 energy and too much coffee.*
