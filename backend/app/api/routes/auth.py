"""Authentication: register, login (JWT), current user."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import audit, get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User, UserPreference
from app.db.session import get_db
from app.schemas.schemas import Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, request: Request, db: Session = Depends(get_db)) -> User:
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role="user",
    )
    user.preferences = UserPreference(interests=[], categories=[])
    db.add(user)
    db.commit()
    db.refresh(user)
    audit(db, user_id=user.id, action="user.register", request=request)
    return user


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    # OAuth2 form uses ``username`` field; we treat it as email.
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    audit(db, user_id=user.id, action="user.login", request=request)
    token = create_access_token(user.id, extra={"role": user.role})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
