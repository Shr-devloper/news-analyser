# 🧠 AI News Intelligence Agent

An autonomous, production-grade AI system that collects news from 12+ trusted sources every morning, removes duplicates with embeddings, categorizes & ranks stories, generates executive summaries with **GroqCloud LLMs** orchestrated via **LangGraph**, builds professional **PDF / HTML / Markdown** reports, and emails them to users automatically — all on a schedule, fully unattended.

> Collect → Deduplicate → Categorize → Rank → Summarize → Personalize → Report → Email

---

## ✨ Features

- **8 specialized agents** wired into a LangGraph pipeline (Collector, Deduplication, Classification, Ranking, Summarization, Briefing, Report, Email).
- **12 source connectors** (Reuters, BBC, CNN, AP, NPR, Economic Times, The Hindu, Times of India, TechCrunch, Ars Technica, Hacker News, Google News) with a pluggable registry to add more in minutes.
- **Embedding-based deduplication & clustering** with vector similarity.
- **Importance scoring (1–100)** based on coverage, global/economic/political/tech impact, recency and audience relevance.
- **Personalized briefings** per user interests (AI, DSA, Startups, Finance, Career growth…).
- **Executive reports** in PDF, HTML and Markdown.
- **Automated email delivery** (Gmail/Outlook SMTP) with retries and delivery tracking.
- **Next.js + Tailwind dashboard**: auth, preferences, historical reports, search/filter, downloads, analytics.
- **JWT auth, RBAC, rate limiting, input validation, audit logs.**
- **Celery + Celery Beat** scheduling, **Redis** broker, **PostgreSQL** storage.
- **Docker Compose** one-command spin-up, **GitHub Actions** CI, health checks & metrics.

---

## 🏗️ Architecture

```
                         ┌─────────────────────────────────────────┐
                         │              Celery Beat                 │
                         │   06:00 collect → 06:45 email (daily)    │
                         └───────────────────┬─────────────────────┘
                                             │ enqueue
                                             ▼
  RSS / HN ──► Agent1 Collector ──► Agent2 Dedup ──► Agent3 Classify ──► Agent4 Rank
                                                                            │
   Email ◄── Agent8 Email ◄── Agent7 Report ◄── Agent6 Briefing ◄── Agent5 Summarize
                                             │
                                   PostgreSQL + Redis
                                             │
                              FastAPI  ◄──►  Next.js Dashboard
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for full detail.

---

## 🚀 Quick Start (Docker — recommended)

```bash
git clone <your-repo> news-analyser && cd news-analyser
cp .env.example .env          # then edit secrets (GROQ_API_KEY, SMTP_*)
docker compose up --build
```

| Service        | URL                          |
|----------------|------------------------------|
| Frontend       | http://localhost:3000        |
| Backend API    | http://localhost:8000        |
| API Docs       | http://localhost:8000/docs   |
| Flower (Celery)| http://localhost:5555        |

A default admin user is created from `.env` (`FIRST_SUPERUSER_*`).

### Trigger the pipeline manually
```bash
docker compose exec backend python -m app.cli run-pipeline      # build report only
docker compose exec backend python -m app.cli send-brief        # build PDF + email it
```

### 📨 Daily PDF Brief (autonomous)
Every day at **07:00 AM IST** (`REPORT_TIMEZONE=Asia/Kolkata`) the agent collects the
last 24h of news, ranks the **top 20** stories, writes a professional PDF
(`Daily_News_Brief_YYYY_MM_DD.pdf` — cover page, table of contents, charts, source
references, and a personalized *"What Should Shresth Pay Attention To Today?"* section)
and **emails it** to `BRIEF_RECIPIENT_EMAIL` via Gmail SMTP. Reports are stored in
PostgreSQL and `backend/storage/reports/`.

Groq model is configurable via `GROQ_MODEL` (`llama-3.3-70b-versatile`,
`deepseek-r1-distill-llama-70b`, or `llama-3.1-8b-instant`).

➡️ Full email/Gmail setup: [`docs/SETUP.md`](docs/SETUP.md)

---

## 🧑‍💻 Local development (without Docker)

Backend:
```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
# in separate shells:
celery -A app.core.celery_app.celery_app worker -l info
celery -A app.core.celery_app.celery_app beat -l info
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## ⚙️ Configuration

All config is environment-driven. Copy `.env.example` → `.env`. Key vars:

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | GroqCloud API key (LLM summaries/classification) |
| `DATABASE_URL` | PostgreSQL DSN |
| `REDIS_URL` | Redis broker/result backend |
| `SECRET_KEY` | JWT signing key |
| `SMTP_HOST/PORT/USER/PASSWORD` | Email delivery |
| `EMBEDDING_MODEL` | SentenceTransformers model name |
| `REPORT_TIMEZONE` | Local time for the 07:00 schedule |

If `GROQ_API_KEY` is unset, the system gracefully falls back to deterministic heuristic summaries so the pipeline still runs end-to-end.

---

## 📚 Docs

- [Deployment guide](docs/DEPLOYMENT.md)
- [API reference](docs/API.md)
- [Architecture](docs/ARCHITECTURE.md)

---

## 🧪 Tests

```bash
cd backend
pytest -q
```

---

## 📂 Project layout

```
.
├── backend/      FastAPI + Celery + agents + AI layer
├── frontend/     Next.js + Tailwind dashboard
├── docs/         Deployment, API, architecture
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## 📜 License
MIT
