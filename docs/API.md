# API Reference

Base URL: `http://localhost:8000`  ·  Prefix: `/api/v1`
Interactive docs: `GET /docs` (Swagger) · `GET /redoc`

Auth: send `Authorization: Bearer <token>` obtained from `/auth/login`.

## Auth

| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | `{email, password, full_name?}` | Create account |
| POST | `/auth/login` | form: `username`(email), `password` | Returns JWT |
| GET  | `/auth/me` | — | Current user |

```bash
# Register
curl -X POST localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"me@x.io","password":"supersecret1","full_name":"Me"}'

# Login (form-encoded)
curl -X POST localhost:8000/api/v1/auth/login \
  -d 'username=me@x.io&password=supersecret1'
```

## Preferences

| Method | Path | Description |
|--------|------|-------------|
| GET | `/preferences` | Get current user's preferences |
| PUT | `/preferences` | Update `{interests, categories, email_enabled, send_hour, timezone}` |

## Reports

| Method | Path | Description |
|--------|------|-------------|
| GET | `/reports?q=&kind=&date_from=&date_to=&limit=&offset=` | List/search/filter |
| GET | `/reports/latest` | Most recent report (full detail) |
| GET | `/reports/{id}` | Report detail (structured `data`) |
| GET | `/reports/{id}/download/{pdf\|html\|md}` | Download artifact |

## Sources

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sources` | List sources + reliability |
| POST | `/sources` | (admin) Add a source |
| PATCH | `/sources/{id}/toggle` | (admin) Enable/disable |

## Analytics

| Method | Path | Description |
|--------|------|-------------|
| GET | `/analytics/overview` | Totals + last-7-days |
| GET | `/analytics/categories` | Category distribution |
| GET | `/analytics/sources` | Source reliability |
| GET | `/analytics/email` | Delivery status counts |
| GET | `/analytics/timeline` | Events per day |

## Admin

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/pipeline/run?send_email=` | (admin) Queue full pipeline |
| GET | `/admin/email-logs` | (admin) Recent email logs |

## Health & Ops

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Liveness |
| GET | `/api/v1/health/ready` | Readiness (DB) |
| GET | `/api/v1/metrics` | Prometheus metrics |
