"""Authentication router for login."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.user_service import pwd_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """Login request payload."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response with user info."""

    id: int
    name: str
    email: str
    role: str
    department: str
    avatar: str | None = None


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user with email and password."""
    user = db.query(User).filter(User.email == data.email, User.status == "active").first()

    if not user or not pwd_context.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email atau password salah.")

    # Update last_login_at
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return LoginResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        department=user.department,
        avatar=user.avatar,
    )
