# Setup Guide — Daily PDF Brief by Email

This guide gets the autonomous **Daily News Intelligence Brief** running: every
morning at **07:00 AM IST** the system collects news, builds a professional PDF,
and emails it to the configured recipient.

## 1. Configure environment

Copy `.env.example` → `.env` (root, for Docker) and/or edit `backend/.env`
(for local runs). Key values for the brief:

```dotenv
# Multiple recipients — each emailed at 7 AM in THEIR OWN timezone.
# Format per recipient: email|timezone|name|hour  (entries separated by ";")
BRIEF_RECIPIENTS=shresth.t.123@gmail.com|Asia/Kolkata|Shresth|7;friend@example.com|America/Los_Angeles|Friend|7
TOP_STORIES_OVERALL=20
FETCH_WINDOW_HOURS=24

# GroqCloud (actionable insights & summaries). Optional — falls back to heuristics.
GROQ_API_KEY=gsk_xxx
GROQ_MODEL=llama-3.3-70b-versatile   # or deepseek-r1-distill-llama-70b / llama-3.1-8b-instant
```

### How multi-timezone delivery works
An **APScheduler** job (`dispatch_due_briefs`) ticks every 5 minutes (no Redis/Celery).
It reads active users from the `users` table and, for each, checks whether it's their
local delivery time (e.g. 7 AM IST or 7 AM PST); if so — and they haven't already been
emailed today (`email_delivery_logs`) — it fetches fresh news and sends them a brand-new
report. Timezones (incl. daylight saving) are resolved with `zoneinfo`. Recipients are
seeded from `app/db/init_db.py:BRIEFING_USERS`; add more by inserting `users` rows.

## 2. Gmail SMTP (App Password)

Gmail blocks plain-password SMTP. Create an **App Password**:

1. Enable 2-Step Verification on the Google account.
2. Go to **Google Account → Security → App passwords**.
3. Generate one for "Mail" → you get a 16-character password.
4. Put it in `.env`:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_TLS=true
SMTP_USER=your.account@gmail.com
SMTP_PASSWORD=the-16-char-app-password
SMTP_FROM=AI News Agent <your.account@gmail.com>
```

> **Outlook/Office365**: `SMTP_HOST=smtp.office365.com`, `SMTP_PORT=587`.

## 3. Choose your Groq model

Set `GROQ_MODEL` to one of:
- `llama-3.3-70b-versatile` (default, best quality)
- `deepseek-r1-distill-llama-70b` (strong reasoning)
- `llama-3.1-8b-instant` (fastest / cheapest)

## 4. Run it

### Docker (full autonomy incl. the 7 AM schedule)
```bash
docker compose up --build
```
The `worker` service runs APScheduler, which builds and emails each user's PDF at their
local 7 AM automatically — no broker required.

### Send a brief right now (any environment)
```bash
# Docker:
docker compose exec backend python -m app.cli send-brief
# Local:
cd backend && .\.venv\Scripts\python.exe -m app.cli send-brief
```

This regenerates the latest report, builds `Daily_News_Brief_YYYY_MM_DD.pdf`
(saved under `backend/storage/reports/` and recorded in PostgreSQL), and emails
it to `BRIEF_RECIPIENT_EMAIL`.

## 5. Verify

- Generated PDFs: `backend/storage/reports/Daily_News_Brief_*.pdf`
- Delivery log: `GET /api/v1/admin/email-logs` (admin) or the `email_logs` table.
- Logs show `daily_brief_sent` / `brief_pdf_generated` events.

## Reliability behavior (built-in)

- **Source failures** are isolated — collection continues; reliability is tracked per source.
- **Fetch retries**: each source retried up to 2× with backoff.
- **Email retries**: up to 3× with backoff; failures recorded in `email_logs`.
- **PDF validation**: generation raises if the output is missing/too small.
- **Rate limits / API errors**: Groq calls degrade to deterministic fallbacks.
- **No SMTP / no Groq**: pipeline still completes; the email is logged as `failed`
  (SMTP unconfigured) and summaries use heuristics.

## Notes on PDF engine

The brief PDF is built with **fpdf2** (pure Python) + **matplotlib** charts, so it
works on Windows/macOS/Linux without GTK/Cairo. (WeasyPrint is used only for the
optional HTML-styled PDF and is skipped if its native libs are absent.)
