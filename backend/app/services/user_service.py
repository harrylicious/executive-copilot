"""User service for CRUD operations on user accounts."""

from datetime import datetime, timezone

from fastapi import HTTPException
from passlib.context import CryptContext
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def create_user(db: Session, data: UserCreate) -> User:
    """Create a new user after verifying email uniqueness.

    Args:
        db: Database session.
        data: User creation payload.

    Returns:
        The newly created User instance.

    Raises:
        HTTPException: 409 if a user with the given email already exists.
    """
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A user with email '{data.email}' already exists",
        )

    user = User(
        name=data.name,
        email=data.email,
        role=data.role,
        department=data.department,
        password_hash=_hash_password(data.password),
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(
    db: Session,
    role: str | None = None,
    department: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> UserListResponse:
    """List users with optional filters and text search.

    Args:
        db: Database session.
        role: Filter by user role.
        department: Filter by department.
        status: Filter by status (active/inactive).
        search: Text search on name and email (case-insensitive LIKE).

    Returns:
        UserListResponse with matching items and total count.
    """
    query = db.query(User)

    if role:
        query = query.filter(User.role == role)
    if department:
        query = query.filter(User.department == department)
    if status:
        query = query.filter(User.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.name.ilike(pattern),
                User.email.ilike(pattern),
            )
        )

    total = query.count()
    users = query.all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
    )


def update_user(db: Session, user_id: int, data: UserUpdate) -> User:
    """Update an existing user's fields.

    Args:
        db: Database session.
        user_id: ID of the user to update.
        data: Partial update payload (only provided fields are applied).

    Returns:
        The updated User instance.

    Raises:
        HTTPException: 404 if the user is not found.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)

    if "password" in update_data:
        update_data["password_hash"] = _hash_password(update_data.pop("password"))

    for field, value in update_data.items():
        setattr(user, field, value)

    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> None:
    """Soft-delete a user by setting their status to inactive.

    Args:
        db: Database session.
        user_id: ID of the user to soft-delete.

    Raises:
        HTTPException: 404 if the user is not found.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = "inactive"
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
