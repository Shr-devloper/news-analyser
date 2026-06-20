# Deployment Guide

**Architecture (no Redis, no Celery):**

```
PostgreSQL  ──►  FastAPI Web Service        (API + dashboard)
            └─►  Background Worker (APScheduler)
                      │ every 5 minutes
                      ├─ load active users from PostgreSQL
                      ├─ convert UTC → each user's timezone
                      ├─ is it their 07:00 and not sent today? (email_delivery_logs)
                      ├─ fetch live news (last 24h) → dedupe → rank → summarize (GroqCloud)
                      ├─ build a FRESH report + new PDF
                      └─ email the PDF via Gmail SMTP, then log the delivery
```

Scheduling is **in-process via APScheduler** — there is no broker to run.

---

## 1. Render (recommended, 24/7)

This repo ships a [`render.yaml`](../render.yaml) blueprint that creates three things:

| Resource | What it is |
|----------|------------|
| `news-db` | Render PostgreSQL |
| `news-api` | FastAPI **web service** (`uvicorn`) |
| `news-scheduler` | **background worker** running `python -m app.scheduler` |

Steps:

1. Push this repo to GitHub.
2. Render Dashboard → **New + → Blueprint** → select the repo. It reads `render.yaml`.
3. Set the secret env vars (marked `sync: false`) on **both** `news-api` and `news-scheduler`:
   - `GROQ_API_KEY` (optional — heuristic fallback if blank)
   - `SMTP_USER` (your Gmail address)
   - `SMTP_PASSWORD` (Gmail **App Password**, not your login password)
   - `SMTP_FROM` (e.g. `AI News Agent <you@gmail.com>`)
4. Deploy. `news-api` runs `alembic upgrade head` on boot (creates tables + seeds the
   two briefing users). The `news-scheduler` worker is what delivers emails daily.

> The **worker is the autonomous part** — it must stay always-on. Render workers have
> no free tier, so the scheduler uses the `starter` plan. (Alternatively, see §3 to run
> the scheduler inside the web service.)

---

## 2. Docker Compose (VPS / local, 24/7)

```bash
cp .env.example .env      # set SECRET_KEY, GROQ_API_KEY (optional), SMTP_*
docker compose up --build -d
```

Services & ports:

| Service  | Port | Notes |
|----------|------|-------|
| frontend | 3000 | Next.js dashboard |
| backend  | 8000 | FastAPI + Swagger at `/docs` |
| worker   |  –   | APScheduler heartbeat (`python -m app.scheduler`) |
| db       | 5432 | PostgreSQL 16 |

`backend` runs migrations + seeds users on boot; `worker` runs the scheduler.
Both have `restart: unless-stopped`, so they survive reboots.

Trigger a delivery manually (any time):

```bash
docker compose exec backend python -m app.cli dispatch                       # send to any user due now
docker compose exec backend python -m app.cli send-now --email supreetkhare2@gmail.com  # force one user
```

---

## 3. Single-service option (no separate worker)

If you'd rather run everything in one process (cheapest), let the web service run the
scheduler in a background thread:

```env
ENABLE_SCHEDULER=true
RUN_SCHEDULER_IN_WEB=true
```

Then you only need the `news-api` web service + `news-db`. (Trade-off: the scheduler
shares the web dyno; fine for 2 users, not for heavy multi-tenant use.)

---

## 4. Local development (without Docker)

Prereqs: Python 3.11, Node 20, a running PostgreSQL (or SQLite for quick starts).

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload          # terminal 1: API
python -m app.scheduler                # terminal 2: scheduler

# Frontend
cd ../frontend
npm install && npm run dev
```

> WeasyPrint (optional HTML→PDF path) needs native libs; the primary PDF engine is
> `fpdf2` (pure Python) so PDFs work everywhere, including Windows.

---

## 5. Production notes

- Set `ENVIRONMENT=production` and a strong `SECRET_KEY`.
- Use managed PostgreSQL; set `DATABASE_URL`. `postgres://`/`postgresql://` URLs are
  auto-normalized to the `postgresql+psycopg://` driver.
- Run **exactly one** scheduler (worker) so a user is never emailed twice.
- Gmail requires an **App Password** (2FA on). Outlook: `SMTP_HOST=smtp.office365.com`.
- Health checks: `GET /api/v1/health` (liveness), `GET /api/v1/health/ready`
  (readiness — DB), `GET /api/v1/metrics` (Prometheus).
- Recipients are seeded from `app/db/init_db.py:BRIEFING_USERS`; edit there or update
  the `users` table to change recipients/timezones/interests.

## 6. Environment variables

See [`.env.example`](../.env.example) for the full annotated list. There are **no Redis
or Celery variables** anymore.
