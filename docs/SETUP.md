# Setup Guide — Daily PDF Brief by Email

This guide gets the autonomous **Daily News Intelligence Brief** running: every
morning at **07:00 AM IST** the system collects news, builds a professional PDF,
and emails it to the configured recipient.

## 1. Configure environment

Copy `.env.example` → `.env` (root, for Docker) and/or edit `backend/.env`
(for local runs). Key values for the brief:

```dotenv
BRIEF_RECIPIENT_EMAIL=shresth.t.123@gmail.com
BRIEF_RECIPIENT_NAME=Shresth
REPORT_TIMEZONE=Asia/Kolkata        # makes 07:00 = 7 AM IST
TOP_STORIES_OVERALL=20
FETCH_WINDOW_HOURS=24

# GroqCloud (actionable insights & summaries). Optional — falls back to heuristics.
GROQ_API_KEY=gsk_xxx
GROQ_MODEL=llama-3.3-70b-versatile   # or deepseek-r1-distill-llama-70b / llama-3.1-8b-instant
```

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
`beat` schedules the daily brief; `worker` runs it; the PDF is emailed automatically.

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
