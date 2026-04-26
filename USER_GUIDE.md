# Pathfinder — User Guide

AI-powered property tax appeal lead management system.

---

## Table of Contents

1. [Starting the Application](#1-starting-the-application)
2. [Logging In](#2-logging-in)
3. [Dashboard](#3-dashboard)
4. [Leads](#4-leads)
5. [Appeals Pipeline](#5-appeals-pipeline)
6. [Counties](#6-counties)
7. [Running Scrapers](#7-running-scrapers)
8. [Scoring Leads](#8-scoring-leads)
9. [API & Swagger Docs](#9-api--swagger-docs)
10. [Monitoring](#10-monitoring)
11. [Service URLs](#11-service-urls)
12. [User Accounts](#12-user-accounts)
13. [Workflow — End to End (Step by Step)](#13-workflow--end-to-end)

---

## 1. Starting the Application

```bash
cd pathfinder
cp .env.example .env        # first time only
docker-compose up -d
```

Wait ~30 seconds for all services to become healthy, then open http://localhost:13000.

**Stopping:**
```bash
docker-compose down          # stop containers, keep data
docker-compose down -v       # stop containers AND delete all data
```

**Restarting after code changes:**
The backend auto-reloads on file save (uvicorn `--reload`).
For frontend changes, rebuild the image:
```bash
docker-compose build frontend && docker-compose up -d frontend
```

---

## 2. Logging In

Open http://localhost:13000 — you will see the login page.

| Username | Password   | Role    | Access                                  |
|----------|------------|---------|------------------------------------------|
| admin    | admin123   | Admin   | Full access — create counties, all routes |
| manager  | manager123 | Manager | Leads, appeals, counties (read)          |
| agent    | agent123   | Agent   | Leads, appeals (read/assign)             |

> **Note:** JWT tokens are stored in memory only — refreshing the browser will log you out.

---

## 3. Dashboard

**URL:** http://localhost:13000/dashboard

The dashboard gives a real-time overview of all leads and appeal activity.

| Card | What it shows |
|------|---------------|
| Total Leads | All scored properties in the system |
| Total Est. Savings | Sum of estimated annual savings across all leads |
| Avg. Probability | Mean appeal success probability |
| Urgent Deadlines | Appeals with deadline < 30 days (shown in red) |

**Charts:**
- **Tier Distribution** — bar chart of how many leads are in each tier (A/B/C/D)
- **Appeal Pipeline** — pie chart of appeal status breakdown (New → Filed → Won/Lost)
- **Tier Summary** — tile breakdown with counts and qualifying criteria per tier

**Tier definitions:**

| Tier | Criteria | Priority |
|------|----------|----------|
| A | Probability ≥ 75% AND gap ≥ 15% | Highest ROI |
| B | Probability ≥ 55% AND gap ≥ 10% | High |
| C | Probability ≥ 35% AND gap ≥ 5%  | Medium |
| D | Everything else | Monitor only |

---

## 4. Leads

**URL:** http://localhost:13000/leads

### Browsing Leads

- **Tier filter buttons** (top right) — click A, B, C, or D to filter. Click again to deselect. Multiple tiers can be active simultaneously.
- **Column sorting** — click any column header to sort ascending/descending.
- **Pagination** — 25 leads per page. Use Prev / Next buttons.

### Lead Columns Explained

| Column | Description |
|--------|-------------|
| Tier | A/B/C/D pill — color coded green/blue/yellow/grey |
| Address | Property street address and city/state |
| County | County name |
| Type | RESIDENTIAL, COMMERCIAL, etc. |
| Assessed | Current assessed value from the county |
| Market Est. | Pathfinder's estimated fair market value (from comps) |
| Gap % | How much the property is over-assessed. Green = high gap |
| Probability | Color bar showing appeal success probability |
| Est. Savings | Projected annual tax savings if appeal succeeds |
| Deadline | Days until appeal deadline. Red = urgent (< 30 days) |

### Lead Detail Drawer

Click any row to open the detail drawer on the right side.

**Sections in the drawer:**

1. **Key Metrics** — assessed value, market estimate, gap amount, gap %, estimated savings, deadline
2. **Appeal Probability** — visual bar with percentage
3. **Top Model Features** — SHAP explanation showing which factors drove the score (green = positive, red = negative impact)
4. **Comparable Sales** — up to 5 similar nearby sales used to estimate market value, with $/sqft, distance, and match score
5. **Actions:**
   - **Assign** — type an agent name or email and click Assign. Creates an appeal record with ASSIGNED status.
   - **Export CSV** — downloads a single-row CSV with all lead fields for CRM import.
   - **Generate Appeal Doc** — downloads a plain-text appeal letter template pre-filled with property data and comparable sales.

---

## 5. Appeals Pipeline

**URL:** http://localhost:13000/appeals

Kanban-style board with six columns:

```
NEW → ASSIGNED → FILED → WON / LOST / WITHDRAWN
```

Each card shows:
- Assigned agent name
- Deadline date (red border = urgent)
- Actual savings (shown on WON cards)

**Moving an appeal:** Click the `→ STATUS` quick buttons on each card to advance or change the status. Changes save immediately.

**Creating an appeal manually:** Use the API at `POST /api/appeals` (see Swagger docs) or by assigning a lead from the Leads drawer.

---

## 6. Counties

**URL:** http://localhost:13000/counties

Lists all configured county scrapers with:
- **Adapter** — the scraper module (e.g. `travis_tx`, `miami_dade_fl`)
- **Deadline Days** — how many days before the county's appeal deadline
- **Approval Rate** — historical appeal approval rate for this county
- **Properties / Leads** — how many records have been scraped and scored
- **Last Scraped** — green dot = has been run, grey = never run

**Adding a new county** (admin only — via API):
```bash
curl -X POST http://localhost:18000/api/counties \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Travis",
    "state": "TX",
    "portal_url": "https://www.traviscad.org",
    "scraper_adapter": "travis_tx",
    "appeal_deadline_days": 45,
    "approval_rate_hist": 0.35
  }'
```

---

## 7. Running Scrapers

Scrapers pull property and assessment data from county portals and store it in the database.

### Automatic (Scheduled)
Scrapers run automatically every night at **02:00 UTC** for all configured counties. No action needed.

### Manual — via CLI
```bash
# Run Travis County scraper
docker-compose exec backend python -m app.scrapers.run --county travis_tx

# Run Miami-Dade scraper
docker-compose exec backend python -m app.scrapers.run --county miami_dade_fl

# Run San Diego scraper
docker-compose exec backend python -m app.scrapers.run --county san_diego_ca
```

### Manual — via Celery task
```bash
# Trigger scrape via Celery (runs in background)
docker-compose exec backend python -c "
from app.workers.scraper_tasks import scrape_county
from app.database import SessionLocal
from app.services.county_repository import CountyRepository
db = SessionLocal()
counties = CountyRepository(db).list()
for c in counties:
    scrape_county.delay(str(c.id))
    print(f'Queued: {c.name}')
db.close()
"
```

### Monitor Scraper Jobs
Open **Flower** at http://localhost:15555 — shows all Celery task history, active workers, success/failure rates.

### Raw Data Storage
All raw HTML/PDF files scraped from county portals are stored in **MinIO**:
- Open http://localhost:19001 (login: `minioadmin` / `minioadmin`)
- Bucket: `pathfinder-raw`
- Path format: `raw/<county_slug>/<apn>/<date>/data.html`

---

## 8. Scoring Leads

After scraping, properties need to be scored to generate leads.

### Automatic
Scoring runs automatically after every scraper batch completes (triggered by the `score_new_assessments` Celery task).

### Manual
```bash
# Score all unscored assessments
docker-compose exec backend python -c "
from app.workers.scoring_tasks import score_new_assessments
score_new_assessments.delay()
print('Scoring task queued')
"

# Score a specific county only
docker-compose exec backend python -c "
from app.workers.scoring_tasks import score_new_assessments
score_new_assessments.delay(county_id='<county-uuid-here>')
"
```

### ML Model
- The scoring model is loaded from **MLflow** at startup.
- If no trained model is found, it falls back to a **rule-based scorer** (gap_pct × county approval rate).
- To train a real model once you have historical appeal outcome data:
  ```bash
  cd ml
  pip install -r ../backend/requirements.txt
  python train.py --county all --year 2024
  ```
- View experiments at http://localhost:15001 (MLflow UI).

---

## 9. API & Swagger Docs

**Interactive API docs:** http://localhost:18000/docs

All endpoints require a Bearer token. To authenticate in Swagger:
1. Call `POST /api/auth/login` with `{"username": "admin", "password": "admin123"}`
2. Copy the `access_token` from the response
3. Click **Authorize** (top right) and paste the token

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/login` | Get JWT token |
| GET | `/api/auth/me` | Current user info |
| GET | `/api/leads` | List leads (paginated, filterable) |
| GET | `/api/leads/{id}` | Lead detail with comps + SHAP |
| POST | `/api/leads/{id}/assign` | Assign agent to lead |
| POST | `/api/leads/{id}/export` | Download lead as CSV |
| GET | `/api/counties` | List counties with stats |
| POST | `/api/counties` | Add a county (admin) |
| GET | `/api/dashboard/stats` | Dashboard summary metrics |
| GET | `/api/appeals` | List all appeals |
| POST | `/api/appeals` | Create an appeal |
| PATCH | `/api/appeals/{id}` | Update appeal status/outcome |
| GET | `/health` | Health check |

### Query Parameters for `/api/leads`

| Parameter | Example | Description |
|-----------|---------|-------------|
| `page` | `1` | Page number |
| `page_size` | `25` | Results per page (max 100) |
| `tier` | `A&tier=B` | Filter by tier (repeatable) |
| `county_id` | `<uuid>` | Filter by county |
| `property_type` | `RESIDENTIAL` | Filter by type |
| `sort_by` | `gap_pct` | Sort field |
| `sort_dir` | `desc` | `asc` or `desc` |

---

## 10. Monitoring

### Grafana — http://localhost:13001
Login: `admin` / `admin`

Pre-built **Pathfinder Overview** dashboard shows:
- API request rate
- Error rate
- P50 / P95 / P99 response times
- Slowest endpoints table

### Prometheus — http://localhost:19090
Raw metrics. Query examples:
```promql
# Request rate
rate(http_requests_total{job="pathfinder-backend"}[1m])

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m])
```

### Flower (Celery Monitor) — http://localhost:15555
- Active workers and task queues
- Task history (success / failure / retries)
- Real-time task throughput

---

## 11. Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend App | http://localhost:13000 | admin / admin123 |
| Backend API | http://localhost:18000 | Bearer token |
| Swagger Docs | http://localhost:18000/docs | Bearer token |
| MLflow UI | http://localhost:15001 | No auth |
| Flower (Celery) | http://localhost:15555 | No auth |
| MinIO Console | http://localhost:19001 | minioadmin / minioadmin |
| Grafana | http://localhost:13001 | admin / admin |
| Prometheus | http://localhost:19090 | No auth |
| PostgreSQL | localhost:15432 | pathfinder / pathfinder |
| Redis | localhost:16379 | No auth |

---

## 12. User Accounts

Three hardcoded dev accounts are built into the backend. To change passwords or add users, edit [backend/app/api/auth.py](backend/app/api/auth.py):

```python
_DEV_USERS = {
    "admin":   {"password": "admin123",   "role": "admin"},
    "agent":   {"password": "agent123",   "role": "agent"},
    "manager": {"password": "manager123", "role": "manager"},
}
```

**Role permissions:**

| Action | Agent | Manager | Admin |
|--------|-------|---------|-------|
| View leads, counties, appeals | ✅ | ✅ | ✅ |
| Assign leads | ✅ | ✅ | ✅ |
| Update appeal status | ✅ | ✅ | ✅ |
| Create counties | ❌ | ❌ | ✅ |
| Export CSV | ✅ | ✅ | ✅ |

---

## 13. Workflow — End to End

Complete step-by-step guide from zero to a filed appeal.

---

### Step 1 — Get a Login Token

Open http://localhost:18000/docs in your browser.

1. Find `POST /api/auth/login` → click **Try it out**
2. Enter the request body:
```json
{
  "username": "admin",
  "password": "admin123"
}
```
3. Click **Execute**
4. Copy the `access_token` from the response

Then click **Authorize** (top right of Swagger UI) and paste the token.

---

### Step 2 — Add a County

Still in Swagger, find `POST /api/counties` → **Try it out** → paste:

```json
{
  "name": "Travis",
  "state": "TX",
  "portal_url": "https://www.traviscad.org",
  "scraper_adapter": "travis_tx",
  "appeal_deadline_days": 45,
  "approval_rate_hist": 0.35
}
```

Click **Execute**. You should get a `201` response with the county's UUID — copy that ID.

To verify it was added, open http://localhost:13000/counties — you should see Travis TX in the table.

---

### Step 3 — Run the Scraper

Open a terminal in the `pathfinder` folder and run:

```bash
docker-compose exec backend python -m app.scrapers.run --county travis_tx
```

This scrapes property and assessment data from Travis County and stores it in the database. It takes 1–3 minutes. To watch it live:

```bash
docker-compose logs backend -f
```

---

### Step 4 — Score the Properties

Scoring runs automatically after scraping. To trigger it manually if it did not run:

```bash
docker-compose exec backend python -c "
from app.workers.scoring_tasks import score_new_assessments
score_new_assessments.delay()
print('Scoring queued')
"
```

Watch Flower at http://localhost:15555 to see the task complete.

---

### Step 5 — Check the Dashboard

Open http://localhost:13000/dashboard

You should now see:
- **Total Leads** — count of scored properties
- **Total Est. Savings** — sum of projected savings across all leads
- **Avg. Probability** — mean appeal success probability
- **Tier Distribution** — bar chart (A/B/C/D)

---

### Step 6 — Browse Leads

Open http://localhost:13000/leads

| What to do | How |
|-----------|-----|
| Filter high-priority | Click **A** tier button (top right) |
| Sort by best gap | Click the **Gap %** column header |
| Sort by best probability | Click **Probability** column header |
| See property details | Click any row |

---

### Step 7 — Review a Lead Detail

Click any row — a drawer opens on the right showing:

- **Gap %** — how much the county over-assessed the property
- **Appeal Probability** — color bar (green = high confidence)
- **SHAP Features** — which factors drove the score
- **Comparable Sales** — nearby properties that sold recently

---

### Step 8 — Assign to an Agent

In the lead drawer:
1. Type an agent name in the **Assign** field (e.g. `John Smith`)
2. Click **Assign**
3. This creates an appeal record with status `ASSIGNED`

---

### Step 9 — Track the Appeal

Open http://localhost:13000/appeals — the Kanban board.

Move the card through stages by clicking the `→ STATUS` button:
```
NEW → ASSIGNED → FILED → WON / LOST / WITHDRAWN
```

When you mark it **WON**, enter the actual savings amount on the card.

---

### Step 10 — Export / Generate Docs

In the lead drawer:
- **Export CSV** — downloads a CSV row ready for your CRM
- **Generate Appeal Doc** — downloads a pre-filled appeal letter with the property data and comparable sales

---

### Optional — Add More Counties

```json
// Miami-Dade, FL
{
  "name": "Miami-Dade",
  "state": "FL",
  "portal_url": "https://www.miamidade.gov/pa",
  "scraper_adapter": "miami_dade_fl",
  "appeal_deadline_days": 30,
  "approval_rate_hist": 0.28
}

// San Diego, CA
{
  "name": "San Diego",
  "state": "CA",
  "portal_url": "https://www.sandiegocounty.gov/content/sdc/arcc.html",
  "scraper_adapter": "san_diego_ca",
  "appeal_deadline_days": 60,
  "approval_rate_hist": 0.42
}
```

Then run the respective scrapers:
```bash
docker-compose exec backend python -m app.scrapers.run --county miami_dade_fl
docker-compose exec backend python -m app.scrapers.run --county san_diego_ca
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| 502 Bad Gateway on login | Backend crashed — run `docker-compose logs backend` to see the error |
| Login fails with "Invalid credentials" | Use exact credentials from table above. Case-sensitive. |
| No leads showing | No data yet — run a scraper first (step 7) |
| Leads show but no market estimate | No comparable sales data — ComparableSalesService needs sales records |
| Scoring uses "rule-based-v1" | No trained MLflow model — scoring still works with rule-based fallback |
| Port already allocated error | Change ports in `docker-compose.yml` (all 13000–19000 range) |
| Container keeps restarting | Run `docker-compose logs <service>` to diagnose |

---

*Pathfinder v1.0 — Built for AI Hackathon 2026*
