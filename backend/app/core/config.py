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

    # ---- Redis / Celery ----
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

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

    # ---- Scheduling ----
    REPORT_TIMEZONE: str = "Asia/Kolkata"
    ENABLE_BEAT: bool = True

    # ---- Pipeline tuning ----
    MAX_ARTICLES_PER_SOURCE: int = 40
    TOP_STORIES_PER_SECTION: int = 10
    TOP_STORIES_OVERALL: int = 20
    FETCH_WINDOW_HOURS: int = 24

    # ---- Daily brief (single-recipient PDF email) ----
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
