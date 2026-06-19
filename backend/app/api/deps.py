"""Shared API dependencies: auth, RBAC, audit logging."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_token
from app.db.models import AuditLog, User
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise credentials_exc
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise credentials_exc
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def audit(
    db: Session, *, user_id: int | None, action: str, request: Request | None = None,
    resource: str | None = None, detail: dict | None = None,
) -> None:
    ip = None
    if request and request.client:
        ip = request.client.host
    db.add(
        AuditLog(user_id=user_id, action=action, resource=resource, ip_address=ip, detail=detail)
    )
    db.commit()
