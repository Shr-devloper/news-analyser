"""User topic/email preferences."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User, UserPreference
from app.db.session import get_db
from app.schemas.schemas import PreferenceOut, PreferenceUpdate

router = APIRouter(prefix="/preferences", tags=["preferences"])


def _ensure(db: Session, user: User) -> UserPreference:
    if user.preferences is None:
        user.preferences = UserPreference(interests=[], categories=[])
        db.add(user.preferences)
        db.commit()
        db.refresh(user)
    return user.preferences


@router.get("", response_model=PreferenceOut)
def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _ensure(db, user)


@router.put("", response_model=PreferenceOut)
def update_preferences(
    payload: PreferenceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = _ensure(db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)
    db.commit()
    db.refresh(prefs)
    return prefs
