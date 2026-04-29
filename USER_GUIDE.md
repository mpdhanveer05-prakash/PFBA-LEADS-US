# Pathfinder — User Guide

AI-powered property tax appeal lead management system.

---

## Table of Contents

1. [Starting the Application](#1-starting-the-application)
2. [Logging In](#2-logging-in)
3. [Dashboard](#3-dashboard)
4. [Leads](#4-leads)
5. [Map View](#5-map-view)
6. [Verification](#6-verification)
7. [Appeals Pipeline](#7-appeals-pipeline)
8. [Outreach Engine](#8-outreach-engine)
9. [Appeal Packets](#9-appeal-packets)
10. [Counties](#10-counties)
11. [Sync Center](#11-sync-center)
12. [Running Scrapers](#12-running-scrapers)
13. [Scoring Leads](#13-scoring-leads)
14. [API & Swagger Docs](#14-api--swagger-docs)
15. [Monitoring](#15-monitoring)
16. [Service URLs](#16-service-urls)
17. [User Accounts](#17-user-accounts)
18. [Workflow — End to End](#18-workflow--end-to-end)
19. [Troubleshooting](#19-troubleshooting)

---

## 1. Starting the Application

**Local:**
```bash
cd PFBA-LEADS-US
docker compose up -d
sleep 15
docker compose exec backend alembic upgrade head
```
Open http://localhost:13000

**EC2 (already deployed):**
Open http://3.237.254.21:13000

**Stopping:**
```bash
docker compose down          # stop containers, keep data
docker compose down -v       # stop containers AND delete all data
```

**Rebuild after code changes:**
```bash
docker compose build backend && docker compose up -d --no-deps backend
docker compose build frontend && docker compose up -d --no-deps frontend
```

---

## 2. Logging In

Open the app URL — the login page appears automatically.

| Username | Password | Role | Access |
|----------|----------|------|--------|
| admin | admin123 | Admin | Full access — create counties, all routes |
| manager | manager123 | Manager | Leads, appeals, counties (read) |
| agent | agent123 | Agent | Leads, appeals (read/assign) |

> JWT tokens are stored in memory only — refreshing the browser logs you out.

---

## 3. Dashboard

**URL:** `/dashboard`

Real-time overview of all leads and appeal activity.

### KPI Cards

| Card | What it shows |
|------|---------------|
| Total Leads | All scored properties in the system |
| Total Est. Savings | Sum of estimated annual savings across all leads |
| Avg. Probability | Mean appeal success probability |
| Urgent Deadlines | Appeals with deadline < 30 days (shown in red) |

### Charts

- **Tier Distribution** — bar chart of leads per tier (A/B/C/D)
- **County Comparison** — horizontal bar showing avg assessment gap % by county
- **Appeal Pipeline** — pie chart of appeal status breakdown
- **ROI Cards** — agency revenue estimate (10% contingency fee), avg savings per lead

### Data Source Filter

Toggle between **Live** (real county data) and **Generated** (seed data) using the buttons in the header. All charts and KPI cards update instantly.

### Tier Definitions

| Tier | Criteria | Priority |
|------|----------|----------|
| A | Probability ≥ 75% AND gap ≥ 15% | Highest ROI |
| B | Probability ≥ 55% AND gap ≥ 10% | High |
| C | Probability ≥ 35% AND gap ≥ 5% | Medium |
| D | Everything else | Monitor only |

---

## 4. Leads

**URL:** `/leads`

### Browsing Leads

- **Tier filter buttons** — click A, B, C, D to filter. Multiple tiers can be active simultaneously.
- **Data Source filter** — toggle Live / Generated data.
- **Column sorting** — click any column header to sort ascending/descending.
- **Pagination** — 25 leads per page.

### Lead Columns

| Column | Description |
|--------|-------------|
| Tier | A/B/C/D pill — color coded green/blue/yellow/grey |
| Address | Property street address and city/state |
| County | County name |
| Type | RESIDENTIAL, COMMERCIAL, etc. |
| Assessed | Current assessed value from the county |
| Market Est. | Estimated fair market value (from comparable sales) |
| Gap % | Over-assessment percentage. Higher = stronger appeal |
| Probability | Color bar showing appeal success probability |
| Est. Savings | Projected annual tax savings if appeal succeeds |
| Deadline | Days until appeal deadline. Red = urgent (< 30 days) |

### Lead Detail Drawer

Click any row to open the detail drawer.

**Sections:**
1. **Key Metrics** — assessed value, market estimate, gap amount, gap %, estimated savings, deadline
2. **Appeal Probability** — visual bar with percentage
3. **Top Model Features** — SHAP explanation showing which factors drove the score
4. **Comparable Sales** — up to 5 nearby sales with $/sqft, distance, similarity score
5. **Actions:**
   - **Assign** — assign an agent, creates an appeal record
   - **Export CSV** — download a single-row CSV for CRM import
   - **Generate Appeal Doc** — download a pre-filled appeal letter

---

## 5. Map View

**URL:** `/map`

Geographic visualization of all scored leads on an OpenStreetMap base layer.

### Controls

- **Tier filter** — A/B/C/D toggle buttons in the toolbar
- **County filter** — dropdown to show leads for a single county
- **Data Source filter** — Live / Generated toggle

### Map Markers

Each lead appears as a colored circle:
- 🟢 Green = Tier A
- 🔵 Blue = Tier B
- 🟡 Yellow = Tier C
- ⚪ Grey = Tier D

Click a marker to see a popup with address, tier, gap %, estimated savings, and a link to the full lead detail.

---

## 6. Verification

**URL:** `/verification`

Agents review leads for data quality before assigning or filing.

### Filters

- **Tier filter** — A/B/C/D buttons
- **Data Source filter** — Live / Generated toggle
- **Status filter** — Unverified / Verified / All

### Verifying a Lead

1. Review the property data, assessment values, and comparable sales
2. Click **Verify** to confirm the lead is valid — a green badge appears
3. Click **Unverify** to revert if you find a data issue

Verified leads are locked for assignment and show a verified badge throughout the platform.

---

## 7. Appeals Pipeline

**URL:** `/appeals`

Kanban-style board tracking every appeal from creation to outcome.

### Columns

```
NEW → ASSIGNED → FILED → WON / LOST / WITHDRAWN
```

Each card shows:
- Assigned agent name
- Deadline date (red border = urgent, < 30 days)
- Actual savings amount (shown on WON cards)

### Moving an Appeal

Click the `→ STATUS` button on a card to advance its status. Changes save immediately.

### Recording an Outcome

When marking as **WON**, enter the actual savings amount. This data feeds back into the ML model accuracy metrics.

---

## 8. Outreach Engine

**URL:** `/outreach`

AI-powered owner contact system — generate pitch emails and track campaigns.

### Tab 1: Select Leads

Shows all scored leads with tier, savings, and probability metrics.

1. Find the lead you want to contact
2. Click **Generate Pitch** — an AI-personalized email is generated instantly
3. A **preview modal** opens showing:
   - Subject line (pre-filled with property address and estimated savings)
   - Recipient email address (from property owner data)
   - Full pitch email body with O'Connor branding and assessment analysis

4. Choose:
   - **Send Now** — sends immediately via SMTP (requires SMTP env vars)
   - **Save as Draft** — saves the campaign for review before sending

### Tab 2: Campaign Tracker

Tracks all generated campaigns with status progression:

```
DRAFT → SENT → OPENED → RESPONDED → OPTED_OUT
```

**Status filter buttons:** ALL / DRAFT / SENT / OPENED / RESPONDED / OPTED_OUT

**Actions per campaign:**
- **Send** — sends a DRAFT campaign via email
- **Mark Responded** — records a positive response
- **Opt Out** — records the owner's opt-out request

### Summary Stats (top cards)

Total campaigns · Draft · Sent · Responded · Opted Out

### SMTP Configuration (for sending real emails)

Add to your `.env`:
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

Without SMTP configured, campaigns can still be saved as DRAFT and viewed.

---

## 9. Appeal Packets

**URL:** `/packets`

Generate professional 4-page PDF appeal packets and download them.

### Tab 1: Generate Packets

Shows all leads with their key metrics.

1. Find the lead you want to generate a packet for
2. Click **Generate PDF** — ReportLab builds the packet in seconds
3. You are automatically switched to the My Packets tab

### What's in the PDF

**Page 1 — Cover:** Petition header, property info, assessment summary, O'Connor branding

**Page 2 — Assessment Analysis:** Assessed vs. market value comparison, gap analysis, assessment history

**Page 3 — Comparable Sales Evidence:** Table of up to 5 nearby sold properties with sale price, $/sqft, distance, and similarity score

**Page 4 — Certification:** Signature page and appeal grounds statement

### Tab 2: My Packets

Lists all generated packets.

**Status filter:** ALL / DRAFT / READY / FILED

**Downloading:** Click **Download PDF** to save the packet to your computer. The file is named `appeal_packet_<id>.pdf`.

---

## 10. Counties

**URL:** `/counties`

Lists all configured county scrapers.

| Column | Description |
|--------|-------------|
| Adapter | Scraper module name (e.g. `cook_il`, `nyc_ny`) |
| Deadline Days | Days before the county's appeal window closes |
| Approval Rate | Historical appeal approval rate for this county |
| Properties / Leads | How many records scraped and scored |
| Last Scraped | Green dot = has been run; grey = never run |

### Adding a County (admin only)

```bash
curl -X POST http://localhost:18000/api/counties \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cook",
    "state": "IL",
    "portal_url": "https://www.cookcountyassessor.com",
    "scraper_adapter": "cook_il",
    "appeal_deadline_days": 30,
    "approval_rate_hist": 0.38
  }'
```

---

## 11. Sync Center

**URL:** `/sync`

Trigger data sync operations and monitor their progress.

### Available Operations

- **Sync County Data** — triggers the scraper for a specific county
- **Score Leads** — runs the ML scoring pipeline on unscored assessments
- **Fetch Real Comps** — pulls actual comparable sales from Socrata APIs

### Monitoring Sync Jobs

All background jobs run via Celery. Monitor them at:
- **Flower UI:** http://localhost:15555 (or http://3.237.254.21:15555 on EC2)

---

## 12. Running Scrapers

Scrapers pull property and assessment data from county portals.

### Automatic
Scrapers run every night at **02:00 UTC** for all configured counties.

### Manual via CLI

```bash
# Run a specific county scraper
docker compose exec backend python -m app.scrapers.run --county cook_il
docker compose exec backend python -m app.scrapers.run --county nyc_ny
docker compose exec backend python -m app.scrapers.run --county sf_ca
docker compose exec backend python -m app.scrapers.run --county philly_pa
```

### Manual via Celery

```bash
docker compose exec backend python -c "
from app.workers.scraper_tasks import scrape_county
scrape_county.delay('cook_il')
print('Queued')
"
```

### Raw Data Storage

All raw data stored in MinIO:
- Open http://localhost:19001 (login: `minioadmin` / `minioadmin`)
- Bucket: `pathfinder-raw`

---

## 13. Scoring Leads

### Automatic
Scoring runs automatically after every scraper batch.

### Manual

```bash
docker compose exec backend python -c "
from app.workers.scoring_tasks import score_new_assessments
score_new_assessments.delay()
print('Scoring queued')
"
```

### ML Model

- Loaded from **MLflow** at startup (http://localhost:15001)
- Falls back to rule-based scorer if no trained model is found
- SHAP values stored per lead — visible in the Lead Detail drawer
- Train a new model:
  ```bash
  cd ml && python train.py --county all --year 2024
  ```

---

## 14. API & Swagger Docs

**URL:** http://localhost:18000/docs (or http://3.237.254.21:18000/docs)

### Authenticate in Swagger

1. Call `POST /api/auth/login` with `{"username": "admin", "password": "admin123"}`
2. Copy the `access_token`
3. Click **Authorize** and paste the token

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Get JWT token |
| GET | `/api/leads` | List leads (paginated, filterable) |
| GET | `/api/leads/{id}` | Lead detail with comps + SHAP |
| POST | `/api/leads/{id}/assign` | Assign agent |
| POST | `/api/leads/{id}/export` | Download CSV |
| GET | `/api/dashboard/stats` | Dashboard summary |
| GET | `/api/counties` | List counties |
| GET | `/api/appeals` | List appeals |
| POST | `/api/appeals` | Create appeal |
| PATCH | `/api/appeals/{id}` | Update appeal status |
| POST | `/api/outreach/generate/{lead_id}` | Generate pitch email |
| GET | `/api/outreach/campaigns` | List campaigns |
| POST | `/api/outreach/campaigns/{id}/send` | Send campaign |
| PATCH | `/api/outreach/campaigns/{id}/status` | Update campaign status |
| POST | `/api/packets/generate/{lead_id}` | Generate appeal packet PDF |
| GET | `/api/packets` | List packets |
| GET | `/api/packets/{id}/download` | Download PDF |
| GET | `/health` | Health check |

---

## 15. Monitoring

### Grafana — http://localhost:13001
Login: `admin` / `admin`

Pre-built **Pathfinder Overview** dashboard shows API request rate, error rate, and response time percentiles (P50/P95/P99).

### Prometheus — http://localhost:19090

```promql
# Request rate
rate(http_requests_total{job="pathfinder-backend"}[1m])

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m])
```

### Flower (Celery Monitor) — http://localhost:15555

- Active workers and queues
- Task history (success / failure / retries)
- Real-time throughput

---

## 16. Service URLs

### Local

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:13000 | admin / admin123 |
| Backend API | http://localhost:18000 | Bearer token |
| API Docs | http://localhost:18000/docs | Bearer token |
| MLflow UI | http://localhost:15001 | — |
| Flower | http://localhost:15555 | — |
| MinIO Console | http://localhost:19001 | minioadmin / minioadmin |
| Grafana | http://localhost:13001 | admin / admin |
| Prometheus | http://localhost:19090 | — |

### EC2 (http://3.237.254.21)

| Service | URL |
|---------|-----|
| Frontend | http://3.237.254.21:13000 |
| Backend API | http://3.237.254.21:18000 |
| API Docs | http://3.237.254.21:18000/docs |
| MLflow UI | http://3.237.254.21:15001 |
| Flower | http://3.237.254.21:15555 |
| MinIO Console | http://3.237.254.21:19001 |
| Grafana | http://3.237.254.21:13001 |

---

## 17. User Accounts

| Action | Agent | Manager | Admin |
|--------|-------|---------|-------|
| View leads, counties, appeals | ✅ | ✅ | ✅ |
| Assign leads | ✅ | ✅ | ✅ |
| Verify leads | ✅ | ✅ | ✅ |
| Update appeal status | ✅ | ✅ | ✅ |
| Generate outreach campaigns | ✅ | ✅ | ✅ |
| Generate appeal packets | ✅ | ✅ | ✅ |
| Export CSV | ✅ | ✅ | ✅ |
| Create counties | ❌ | ❌ | ✅ |

---

## 18. Workflow — End to End

### Step 1 — Login
Open the app, enter `admin` / `admin123`.

### Step 2 — Add a County (first time only)
Go to API Docs → `POST /api/counties`:
```json
{
  "name": "Cook",
  "state": "IL",
  "portal_url": "https://www.cookcountyassessor.com",
  "scraper_adapter": "cook_il",
  "appeal_deadline_days": 30,
  "approval_rate_hist": 0.38
}
```

### Step 3 — Run the Scraper
```bash
docker compose exec backend python -m app.scrapers.run --county cook_il
```

### Step 4 — Score Leads
Scoring runs automatically. To trigger manually:
```bash
docker compose exec backend python -c "
from app.workers.scoring_tasks import score_new_assessments
score_new_assessments.delay()
"
```

### Step 5 — Review Dashboard
Open `/dashboard` — check KPI cards and Tier Distribution chart.

### Step 6 — Filter Leads
Open `/leads` → click **A** tier → sort by **Gap %** descending.

### Step 7 — Verify the Lead
Open `/verification` → click **Verify** on confirmed leads.

### Step 8 — Generate Outreach Email
Open `/outreach` → click **Generate Pitch** → preview the email → **Send Now**.

### Step 9 — Generate Appeal Packet
Open `/packets` → click **Generate PDF** → **Download PDF**.

### Step 10 — Assign to Agent
In the Lead Detail drawer → type agent name → click **Assign**.

### Step 11 — Track the Appeal
Open `/appeals` → move card through: `ASSIGNED → FILED → WON`.

### Step 12 — Record Outcome
Click **WON** → enter actual savings amount.

---

## 19. Troubleshooting

| Problem | Fix |
|---------|-----|
| App won't load | Check `docker compose ps` — all services should be `Up` |
| 502 Bad Gateway | Backend crashed — run `docker compose logs backend` |
| Login fails | Use exact credentials. Case-sensitive. |
| No leads showing | Run a scraper first — no data in database yet |
| "reportlab not installed" | Rebuild backend: `docker compose build --no-cache backend` |
| Port already allocated | Run `sudo fuser -k <port>/tcp` then `docker compose up -d` |
| No space left on device | Extend EC2 EBS volume to 30 GB min (AWS Console → Volumes) |
| Container keeps restarting | `docker compose logs <service>` to diagnose |
| Appeal packet download fails | Check MinIO is running and bucket `pathfinder-raw` exists |
| Email send fails | Verify SMTP_HOST, SMTP_USER, SMTP_PASS are set in `.env` |
| Tier filter not working | Hard-refresh browser (Ctrl+Shift+R) to clear cached JS |

---

*Pathfinder v2.0 — Built for AI Hackathon 2026 · O'Connor & Associates*
