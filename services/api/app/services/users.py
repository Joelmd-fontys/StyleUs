"""User persistence helpers."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.user import User


def sync_authenticated_user(db: Session, *, user_id: uuid.UUID, email: str) -> User:
    """Ensure the application user row matches the authenticated identity."""
    normalized_email = email.strip().lower()
    user = db.get(User, user_id)

    if user is None:
        user = User(id=user_id, email=normalized_email)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    if user.email != normalized_email:
        user.email = normalized_email
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
