"""User management router for CRUD operations on user accounts."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services.user_service import create_user, delete_user, list_users, update_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=UserListResponse)
def get_users(
    role: Optional[str] = Query(default=None, description="Filter by user role"),
    department: Optional[str] = Query(default=None, description="Filter by department"),
    status: Optional[str] = Query(default=None, description="Filter by status (active/inactive)"),
    search: Optional[str] = Query(default=None, description="Search by name or email"),
    db: Session = Depends(get_db),
):
    """List users with optional filters."""
    try:
        return list_users(db, role=role, department=department, status=status, search=search)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list users: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Users could not be retrieved. Please try again later.",
        )


@router.post("/", response_model=UserResponse, status_code=201)
def create_new_user(data: UserCreate, db: Session = Depends(get_db)):
    """Create a new user account."""
    try:
        return create_user(db, data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create user: %s", e)
        raise HTTPException(
            status_code=500,
            detail="User could not be created. Please try again later.",
        )


@router.patch("/{user_id}", response_model=UserResponse)
def update_existing_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db)):
    """Update an existing user's fields."""
    try:
        return update_user(db, user_id, data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update user %d: %s", user_id, e)
        raise HTTPException(
            status_code=500,
            detail="User could not be updated. Please try again later.",
        )


@router.delete("/{user_id}", status_code=204)
def soft_delete_user(user_id: int, db: Session = Depends(get_db)):
    """Soft-delete a user by setting their status to inactive."""
    try:
        delete_user(db, user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete user %d: %s", user_id, e)
        raise HTTPException(
            status_code=500,
            detail="User could not be deleted. Please try again later.",
        )
