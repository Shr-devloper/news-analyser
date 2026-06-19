"""Health checks and Prometheus metrics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok", "version": __version__, "environment": settings.ENVIRONMENT}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    checks = {"database": False, "redis": False}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # noqa: BLE001
        pass
    try:
        import redis

        client = redis.from_url(settings.REDIS_URL)
        client.ping()
        checks["redis"] = True
    except Exception:  # noqa: BLE001
        pass
    ready = all(checks.values())
    return {"ready": ready, "checks": checks, "groq_enabled": settings.groq_enabled}


@router.get("/metrics")
def metrics():
    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    except Exception:  # noqa: BLE001
        return Response(content="# metrics unavailable\n", media_type="text/plain")
