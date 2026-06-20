"""FastAPI application entrypoint.

Wires middleware (CORS, rate limiting), routers, structured logging, and a
startup hook that seeds the first superuser + default sources.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app import __version__
from app.api.routes import admin, analytics, auth, health, preferences, reports, sources
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.init_db import init_db
from app.db.session import SessionLocal

configure_logging()
log = get_logger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        init_db(db)
    except Exception as exc:  # noqa: BLE001
        log.warning("init_db_failed", error=str(exc))
    finally:
        db.close()

    # Optionally run the APScheduler heartbeat inside the web process
    # (single-service deploys). On Render we run a dedicated worker instead.
    scheduler = None
    if settings.ENABLE_SCHEDULER and settings.RUN_SCHEDULER_IN_WEB:
        from app.scheduler import create_scheduler

        scheduler = create_scheduler(blocking=False)
        scheduler.start()
        log.info("scheduler_started_in_web", interval_min=settings.SCHEDULER_INTERVAL_MINUTES)

    log.info("app_started", version=__version__, env=settings.ENVIRONMENT)
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    log.info("app_stopping")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=__version__,
    description="Autonomous AI agent that collects, dedupes, ranks, summarizes and emails news daily.",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
prefix = settings.API_V1_PREFIX
app.include_router(health.router, prefix=prefix)
app.include_router(auth.router, prefix=prefix)
app.include_router(preferences.router, prefix=prefix)
app.include_router(reports.router, prefix=prefix)
app.include_router(sources.router, prefix=prefix)
app.include_router(analytics.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)


@app.get("/")
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": __version__,
        "docs": "/docs",
        "health": f"{prefix}/health",
    }
