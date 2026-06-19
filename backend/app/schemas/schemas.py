"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---- Auth / users ----
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime


# ---- Preferences ----
class PreferenceUpdate(BaseModel):
    interests: list[str] | None = None
    categories: list[str] | None = None
    email_enabled: bool | None = None
    send_hour: int | None = Field(default=None, ge=0, le=23)
    timezone: str | None = None


class PreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    interests: list[str]
    categories: list[str]
    email_enabled: bool
    send_hour: int
    timezone: str


# ---- Sources ----
class SourceCreate(BaseModel):
    slug: str
    name: str
    connector: str = "rss"
    url: str
    category_hint: str | None = None
    country: str | None = None
    enabled: bool = True


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    name: str
    connector: str
    url: str
    enabled: bool
    reliability_score: float
    success_count: int
    failure_count: int
    last_fetched_at: datetime | None


# ---- Reports ----
class ReportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    kind: str
    report_date: datetime
    event_count: int
    executive_summary: str | None


class ReportDetail(ReportSummary):
    data: dict | None
    html_path: str | None
    pdf_path: str | None
    markdown_path: str | None


# ---- Email logs ----
class EmailLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recipient: str
    subject: str
    status: str
    attempts: int
    sent_at: datetime | None
    created_at: datetime
