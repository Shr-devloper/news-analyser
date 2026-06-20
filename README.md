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
- **APScheduler** in-process scheduling (no broker), **PostgreSQL** storage.
- **Docker Compose** one-command spin-up, **GitHub Actions** CI, health checks & metrics.

---

## 🏗️ Architecture

```
                         ┌─────────────────────────────────────────┐
                         │     APScheduler worker (every 5 min)     │
                         │   per-user, per-timezone 07:00 delivery  │
                         └───────────────────┬─────────────────────┘
                                             │ calls in-process
                                             ▼
  RSS / HN ──► Agent1 Collector ──► Agent2 Dedup ──► Agent3 Classify ──► Agent4 Rank
                                                                            │
   Email ◄── Agent8 Email ◄── Agent7 Report ◄── Agent6 Briefing ◄── Agent5 Summarize
                                             │
                                       PostgreSQL
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

A default admin user is created from `.env` (`FIRST_SUPERUSER_*`).

### Trigger the pipeline manually
```bash
docker compose exec backend python -m app.cli run-pipeline      # build report only
docker compose exec backend python -m app.cli dispatch          # send to any user due now
docker compose exec backend python -m app.cli send-now --email supreetkhare2@gmail.com  # force one user
```

### 📨 Daily PDF Brief (autonomous)
An **APScheduler** worker checks every 5 minutes and, when a user's local **07:00**
arrives, collects the last 24h of news, ranks the **top 25** stories, writes a fresh
6–7 page professional PDF (`Daily_News_Brief_YYYY_MM_DD.pdf` with Executive Summary,
World / India / Tech & AI / Business sections, a personalized *"What Should {Name} Pay
Attention To Today?"* section, and run metadata) and **emails it** via Gmail SMTP.
Delivery is de-duplicated per user/day via `email_delivery_logs`. Recipients live in
the `users` table (Shresth → IST, Supreet → PST). Reports are stored in PostgreSQL and
`backend/storage/reports/`.

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
# in a separate shell — the autonomous scheduler (no broker needed):
python -m app.scheduler
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
| `DATABASE_URL` | PostgreSQL DSN (`postgres://` auto-normalized) |
| `SECRET_KEY` | JWT signing key |
| `SMTP_HOST/PORT/USER/PASSWORD` | Email delivery |
| `EMBEDDING_MODEL` | SentenceTransformers model name |
| `REPORT_TIMEZONE` | Local time for recap jobs |
| `SCHEDULER_INTERVAL_MINUTES` | How often the scheduler checks for due users (default 5) |
| `RUN_SCHEDULER_IN_WEB` | Run APScheduler inside the web process (single-service deploy) |

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
├── backend/      FastAPI + APScheduler + agents + AI layer
├── frontend/     Next.js + Tailwind dashboard
├── docs/         Deployment, API, architecture
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## 📜 License
MIT
