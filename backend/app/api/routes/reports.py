"""Report listing, search/filter, detail and downloads."""

from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import Report, User
from app.db.session import get_db
from app.schemas.schemas import ReportDetail, ReportSummary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportSummary])
def list_reports(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    q: str | None = Query(default=None, description="Full-text search in title/summary"),
    kind: str | None = Query(default=None),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=30, le=100),
    offset: int = 0,
):
    query = db.query(Report)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Report.title.ilike(like), Report.executive_summary.ilike(like)))
    if kind:
        query = query.filter(Report.kind == kind)
    if date_from:
        query = query.filter(Report.report_date >= date_from)
    if date_to:
        query = query.filter(Report.report_date <= date_to)
    return (
        query.order_by(Report.report_date.desc()).offset(offset).limit(limit).all()
    )


@router.get("/latest", response_model=ReportDetail)
def latest_report(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    report = db.query(Report).order_by(Report.report_date.desc()).first()
    if not report:
        raise HTTPException(status_code=404, detail="No reports yet")
    return report


@router.get("/{report_id}", response_model=ReportDetail)
def get_report(report_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/download/{fmt}")
def download_report(
    report_id: int,
    fmt: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    path_map = {
        "pdf": (report.pdf_path, "application/pdf"),
        "html": (report.html_path, "text/html"),
        "md": (report.markdown_path, "text/markdown"),
        "markdown": (report.markdown_path, "text/markdown"),
    }
    if fmt not in path_map:
        raise HTTPException(status_code=400, detail="Unsupported format")
    path, media = path_map[fmt]
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"{fmt} not available for this report")
    return FileResponse(path, media_type=media, filename=os.path.basename(path))
