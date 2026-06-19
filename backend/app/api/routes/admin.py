"""Admin operations: trigger the pipeline on-demand and inspect email logs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import audit, require_admin
from app.db.models import EmailLog, User
from app.db.session import get_db
from app.schemas.schemas import EmailLogOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/pipeline/run")
def run_pipeline_now(
    request: Request,
    send_email: bool = True,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Queue the full daily pipeline as a Celery task (non-blocking)."""
    from app.tasks.pipeline import run_daily_pipeline

    task = run_daily_pipeline.delay(send_email=send_email)
    audit(db, user_id=user.id, action="pipeline.trigger", request=request,
          detail={"task_id": task.id, "send_email": send_email})
    return {"status": "queued", "task_id": task.id}


@router.get("/email-logs", response_model=list[EmailLogOut])
def email_logs(
    limit: int = 50,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(EmailLog).order_by(EmailLog.created_at.desc()).limit(limit).all()
