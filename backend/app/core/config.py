"""Centralised, environment-driven application settings.

All configuration is read from environment variables (or a local ``.env`` file).
Using ``pydantic-settings`` gives us validation and typed access everywhere.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # ---- General ----
    PROJECT_NAME: str = "AI News Intelligence Agent"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"

    # ---- Security ----
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ALGORITHM: str = "HS256"
    BACKEND_CORS_ORIGINS: list[str] | str = "http://localhost:3000"

    # ---- First superuser ----
    FIRST_SUPERUSER_EMAIL: str = "admin@news.ai"
    FIRST_SUPERUSER_PASSWORD: str = "ChangeMe123!"
    FIRST_SUPERUSER_NAME: str = "Administrator"

    # ---- Database ----
    DATABASE_URL: str = "postgresql+psycopg://news:news@localhost:5432/news"

    # ---- AI / GroqCloud ----
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    DEDUP_SIMILARITY_THRESHOLD: float = 0.78

    # ---- Email / SMTP ----
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "AI News Agent <no-reply@news.ai>"
    SMTP_TLS: bool = True

    # ---- Scheduling (APScheduler — no broker/Redis) ----
    REPORT_TIMEZONE: str = "Asia/Kolkata"
    ENABLE_SCHEDULER: bool = True            # master switch for the APScheduler worker
    SCHEDULER_INTERVAL_MINUTES: int = 5      # how often to check for due users
    # When true, the FastAPI web process ALSO runs the scheduler in a background
    # thread (handy for single-service deploys). On Render we use a separate worker.
    RUN_SCHEDULER_IN_WEB: bool = False

    # ---- Pipeline tuning ----
    MAX_ARTICLES_PER_SOURCE: int = 40
    TOP_STORIES_PER_SECTION: int = 10
    TOP_STORIES_OVERALL: int = 25  # spec: select at most 25 most important stories
    FETCH_WINDOW_HOURS: int = 24

    # ---- Daily brief recipients ----
    # Multiple recipients, each emailed at 7 AM in THEIR OWN timezone.
    # Format: "email|timezone|name|hour" entries separated by ";".
    # Example: "a@x.com|Asia/Kolkata|Asha|7;b@y.com|America/Los_Angeles|Bob|7"
    BRIEF_RECIPIENTS: str = ""
    BRIEF_SEND_HOUR: int = 7  # default local send hour if not given per-recipient
    # Backward-compatible single recipient (used when BRIEF_RECIPIENTS is empty).
    BRIEF_RECIPIENT_EMAIL: str = "shresth.t.123@gmail.com"
    BRIEF_RECIPIENT_NAME: str = "Shresth"
    BRIEF_INTERESTS: list[str] | str = (
        "Artificial Intelligence,Software Engineering,Programming,DSA,"
        "Startups,Career Growth,Productivity,Emerging Technologies"
    )

    # ---- Storage ----
    REPORTS_DIR: str = "storage/reports"

    @field_validator("BACKEND_CORS_ORIGINS", "BRIEF_INTERESTS", mode="before")
    @classmethod
    def _split_csv(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        # Render/Heroku hand out `postgres://` or `postgresql://`; SQLAlchemy + psycopg3
        # needs the `postgresql+psycopg://` driver scheme. Normalize it transparently.
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return "postgresql+psycopg://" + v[len("postgres://"):]
            if v.startswith("postgresql://"):
                return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def brief_recipients(self) -> list[dict]:
        """Parse BRIEF_RECIPIENTS into [{email, timezone, name, hour}].

        Falls back to the single BRIEF_RECIPIENT_* config when unset.
        """
        out: list[dict] = []
        raw = (self.BRIEF_RECIPIENTS or "").strip()
        if raw:
            for chunk in raw.split(";"):
                chunk = chunk.strip()
                if not chunk:
                    continue
                parts = [p.strip() for p in chunk.split("|")]
                email = parts[0]
                if not email:
                    continue
                tz = parts[1] if len(parts) > 1 and parts[1] else self.REPORT_TIMEZONE
                name = parts[2] if len(parts) > 2 and parts[2] else email.split("@")[0]
                try:
                    hour = int(parts[3]) if len(parts) > 3 and parts[3] else self.BRIEF_SEND_HOUR
                except ValueError:
                    hour = self.BRIEF_SEND_HOUR
                out.append({"email": email, "timezone": tz, "name": name, "hour": hour})
        else:
            out.append({
                "email": self.BRIEF_RECIPIENT_EMAIL,
                "timezone": self.REPORT_TIMEZONE,
                "name": self.BRIEF_RECIPIENT_NAME,
                "hour": self.BRIEF_SEND_HOUR,
            })
        return out

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def groq_enabled(self) -> bool:
        return bool(self.GROQ_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
