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
first superuser + default sources are seeded on first boot.

Generate the first report immediately:

```bash
docker compose exec backend python -m app.cli run-pipeline
```

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

## 4. Environment variables

See [`.env.example`](../.env.example) for the full annotated list.
