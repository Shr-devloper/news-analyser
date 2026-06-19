"""News source management (admin can mutate; all users can view)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.models import NewsSource, User
from app.db.session import get_db
from app.schemas.schemas import SourceCreate, SourceOut

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(NewsSource).order_by(NewsSource.name).all()


@router.post("", response_model=SourceOut, status_code=201)
def create_source(
    payload: SourceCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    if db.query(NewsSource).filter(NewsSource.slug == payload.slug).first():
        raise HTTPException(status_code=400, detail="Source slug already exists")
    source = NewsSource(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.patch("/{source_id}/toggle", response_model=SourceOut)
def toggle_source(
    source_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    source = db.get(NewsSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.enabled = not source.enabled
    db.commit()
    db.refresh(source)
    return source
