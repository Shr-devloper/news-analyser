# Architecture

## Overview

The system is a monorepo with two deployable apps (`backend`, `frontend`) plus
Celery workers, backed by PostgreSQL and Redis.

```
┌──────────┐   HTTP    ┌─────────────┐   SQL    ┌────────────┐
│ Next.js  │ ───────► │  FastAPI    │ ──────► │ PostgreSQL │
│ Dashboard│           │  REST API   │          └────────────┘
└──────────┘           └─────────────┘                ▲
                              │ enqueue                │
                              ▼                        │
                       ┌─────────────┐   tasks   ┌──────────┐
                       │   Redis     │ ◄──────── │  Celery  │
                       │  (broker)   │ ────────► │  worker  │
                       └─────────────┘           └────┬─────┘
                              ▲                        │ runs
                       ┌──────┴──────┐                 ▼
                       │ Celery Beat │          ┌──────────────┐
                       │ (scheduler) │          │ LangGraph    │
                       └─────────────┘          │ agent pipeline│
                                                 └──────────────┘
```

## The agent pipeline (LangGraph)

`app/ai/graph.py` compiles a `StateGraph`:

```
collect → deduplicate → classify → rank → summarize → report → email
```

Each node is one agent in `app/agents/`. A shared `PipelineState` dict carries
run statistics and the generated `report_id`. If LangGraph can't be imported,
`run_pipeline` falls back to an equivalent sequential executor.

| # | Agent | Module | Output |
|---|-------|--------|--------|
| 1 | Collector | `agents/collector.py` | `raw_articles` + source reliability |
| 2 | Deduplication | `agents/deduplication.py` | `deduplicated_events` (embedding clusters) |
| 3 | Classification | `agents/classification.py` | `article_categories` |
| 4 | Ranking | `agents/ranking.py` | `rankings` (score 1–100) |
| 5 | Summarization | `agents/summarization.py` | `summaries` |
| 6 | Briefing | `agents/briefing.py` | personalized per-user items |
| 7 | Report | `agents/report.py` | `reports` + HTML/PDF/MD files |
| 8 | Email | `agents/email.py` | `email_logs` + delivered emails |

## AI layer

- **GroqCloud** (`ai/groq_client.py`) powers classification, impact scoring
  refinement, summaries and the executive summary. Strict-JSON responses are
  parsed defensively. Without an API key the system uses deterministic
  heuristics so it always runs.
- **Embeddings** (`ai/embeddings.py`) use SentenceTransformers, with a
  hashing-based fallback. Cosine similarity drives deduplication and the
  semantic personalized briefing.

## Scheduling

`app/core/celery_app.py` defines Beat entries:
- `daily-news-pipeline` — 06:00 local (`REPORT_TIMEZONE`)
- `weekly-recap` — Monday 08:00
- `monthly-recap` — 1st of month 08:30

Granular per-stage tasks also exist for operators wanting the exact
06:00→06:45 timetable.

## Extensibility

Add a source: append to `DEFAULT_SOURCES` in `sources/registry.py` (RSS) or
implement a new `Connector` subclass and register it in `CONNECTORS`.
Everything downstream consumes the normalized `FetchedArticle`.
