# Deployment Guide

## 1. Local (Docker Compose) — recommended

```bash
cp .env.example .env
# Edit at least: SECRET_KEY, GROQ_API_KEY (optional), SMTP_* (for email)
docker compose up --build
```

Services & ports:

| Service  | Port | Notes |
|----------|------|-------|
| frontend | 3000 | Next.js dashboard |
| backend  | 8000 | FastAPI + Swagger at `/docs` |
| flower   | 5555 | Celery monitoring |
| db       | 5432 | PostgreSQL 16 |
| redis    | 6379 | broker/result backend |

Migrations run automatically (`alembic upgrade head`) on backend start, and the
first superuser, default sources **and the briefing users** (Shresth → 7 AM IST,
Supreet → 7 AM PST) are seeded on first boot from
`backend/app/db/init_db.py:BRIEFING_USERS`.

Generate the first report immediately:

```bash
docker compose exec backend python -m app.cli run-pipeline   # shared report, no email
docker compose exec backend python -m app.cli dispatch       # send to any user due now
docker compose exec backend python -m app.cli send-now --email supreetkhare2@gmail.com  # force one user
```

## How autonomous delivery works (the important part)

The system is **fully DB-driven and timezone-aware** — no manual steps after boot:

1. **Celery Beat** fires `app.tasks.pipeline.dispatch_due_briefs` **every 5 minutes**.
2. The task loads every active, `briefing_enabled` user from the `users` table.
3. For each user it converts UTC → the user's `timezone` (DST-aware via `zoneinfo`)
   and checks whether the local time is inside their delivery window
   (`delivery_hour:delivery_minute` … +5 min).
4. It consults `email_delivery_logs` (unique on `user_id, delivery_date`) so a user
   is emailed **at most once per local day**.
5. For due users it runs the **fresh** pipeline once
   (collect → dedupe → classify → rank → summarize), then builds a
   **personalized** report + brand-new PDF per user and emails it (3 retries).

**Freshness guarantee:** reports only ever include events whose `event_date` is
within the last `FETCH_WINDOW_HOURS` (24h). Yesterday's stories, summaries, PDFs
and HTML are never reused — every PDF is regenerated with a unique `report_uid`
and filename (`Daily_News_Brief_YYYY_MM_DD_<id>.pdf`).

## 2. Local (without Docker)

Prereqs: Python 3.11, Node 20, a running PostgreSQL and Redis.

```bash
# Backend
cd backend
python -m venv .venv && . .venv/Scripts/activate     # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
# point DATABASE_URL / REDIS_URL at local services in your .env
alembic upgrade head
uvicorn app.main:app --reload

# Worker + scheduler (separate terminals)
celery -A app.core.celery_app.celery_app worker -l info
celery -A app.core.celery_app.celery_app beat -l info

# Frontend
cd ../frontend
npm install
npm run dev
```

> WeasyPrint (PDF) needs native libs (Pango/Cairo). On Windows the easiest path
> is Docker. Without them, PDF is skipped gracefully; HTML & Markdown still work.

## 3. Production notes

- Set `ENVIRONMENT=production` (enables JSON logging) and a strong `SECRET_KEY`.
- Use managed PostgreSQL + Redis; set the matching `DATABASE_URL`/`REDIS_URL`.
- Run `backend`, `worker`, and `beat` as separate processes/replicas.
  Run exactly **one** `beat` instance.
- Put the API behind TLS (nginx/Caddy/cloud LB) and restrict `BACKEND_CORS_ORIGINS`.
- Gmail requires an **App Password** (not your account password) with 2FA on.
  Outlook: `SMTP_HOST=smtp.office365.com`, `SMTP_PORT=587`.
- Persist the `reports` volume for downloadable artifacts.
- Health checks: `GET /api/v1/health` (liveness), `GET /api/v1/health/ready`
  (readiness — DB + Redis), `GET /api/v1/metrics` (Prometheus).

## 4. Cloud (24/7) — Railway / Render / VPS / AWS

The platform must keep running when your laptop is off, so deploy the three
backend processes plus managed Postgres + Redis. Each process uses the same
image/repo, only the start command differs:

| Process | Start command |
|---------|---------------|
| api     | `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| worker  | `celery -A app.core.celery_app.celery_app worker -l info` |
| beat    | `celery -A app.core.celery_app.celery_app beat -l info` (exactly **one**) |

**Railway / Render:** create a service per process from this repo (root
`backend/`), add the Postgres and Redis plugins, then set the env vars below.
The `beat` process is what makes delivery autonomous — keep it always-on.

**VPS / AWS (systemd or docker compose):** `docker compose up -d` already starts
`backend`, `worker`, `beat`, `db`, `redis`. Put it behind nginx/Caddy for TLS and
enable restart-on-boot (`restart: unless-stopped` is set in compose).

Minimum env for cloud:

```env
GROQ_API_KEY=...            # optional; heuristic fallback if absent
EMAIL_USER=you@gmail.com    # == SMTP_USER
EMAIL_PASSWORD=app-password # == SMTP_PASSWORD (Gmail App Password)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/news
REDIS_URL=redis://host:6379/0
CELERY_BROKER_URL=redis://host:6379/1
CELERY_RESULT_BACKEND=redis://host:6379/2
ENABLE_BEAT=true
```

Recipients are seeded into the DB automatically; to change them edit
`BRIEFING_USERS` in `app/db/init_db.py` (or update the `users` rows directly).

## 5. Environment variables

See [`.env.example`](../.env.example) for the full annotated list.
