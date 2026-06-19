"""Analytics endpoints powering the dashboard analytics page."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import (
    ArticleCategory,
    DeduplicatedEvent,
    EmailLog,
    NewsSource,
    RawArticle,
    Report,
    User,
)
from app.db.session import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    return {
        "totals": {
            "reports": db.query(func.count(Report.id)).scalar() or 0,
            "articles": db.query(func.count(RawArticle.id)).scalar() or 0,
            "events": db.query(func.count(DeduplicatedEvent.id)).scalar() or 0,
            "sources": db.query(func.count(NewsSource.id)).scalar() or 0,
            "users": db.query(func.count(User.id)).scalar() or 0,
        },
        "last_7_days": {
            "articles": db.query(func.count(RawArticle.id))
            .filter(RawArticle.created_at >= week_ago)
            .scalar()
            or 0,
            "reports": db.query(func.count(Report.id))
            .filter(Report.created_at >= week_ago)
            .scalar()
            or 0,
        },
    }


@router.get("/categories")
def category_distribution(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.query(ArticleCategory.category, func.count(ArticleCategory.id))
        .group_by(ArticleCategory.category)
        .order_by(func.count(ArticleCategory.id).desc())
        .all()
    )
    return [{"category": c, "count": n} for c, n in rows]


@router.get("/sources")
def source_reliability(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    sources = db.query(NewsSource).order_by(NewsSource.reliability_score.desc()).all()
    return [
        {
            "slug": s.slug,
            "name": s.name,
            "reliability": s.reliability_score,
            "success": s.success_count,
            "failure": s.failure_count,
            "enabled": s.enabled,
        }
        for s in sources
    ]


@router.get("/email")
def email_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.query(EmailLog.status, func.count(EmailLog.id))
        .group_by(EmailLog.status)
        .all()
    )
    return {status: count for status, count in rows}


@router.get("/timeline")
def report_timeline(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.query(func.date(Report.report_date), func.sum(Report.event_count))
        .group_by(func.date(Report.report_date))
        .order_by(func.date(Report.report_date))
        .limit(60)
        .all()
    )
    return [{"date": str(d), "events": int(n or 0)} for d, n in rows]
