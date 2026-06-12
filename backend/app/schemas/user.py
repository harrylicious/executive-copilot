"""Pydantic schemas for user API requests and responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


def _to_camel(field_name: str) -> str:
    """Convert a snake_case field name to camelCase for JSON serialization."""
    parts = field_name.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class UserCreate(BaseModel):
    """Schema for creating a new user."""

    name: str = Field(..., min_length=1, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    role: str = Field(..., min_length=1, description="User's role")
    department: str = Field(..., min_length=1, description="User's department")
    password: str = Field(..., min_length=8, description="Plaintext password (will be hashed)")


class UserUpdate(BaseModel):
    """Schema for updating an existing user. All fields are optional."""

    name: str | None = Field(default=None, min_length=1, description="User's full name")
    email: EmailStr | None = Field(default=None, description="User's email address")
    role: str | None = Field(default=None, min_length=1, description="User's role")
    department: str | None = Field(default=None, min_length=1, description="User's department")
    password: str | None = Field(default=None, min_length=8, description="New password (will be hashed)")
    status: str | None = Field(default=None, description="User status (active, inactive)")
    phone: str | None = Field(default=None, description="User's phone number")
    bio: str | None = Field(default=None, description="User's biography")
    avatar: str | None = Field(default=None, description="URL to user's avatar image")


class UserResponse(BaseModel):
    """Response schema for a single user. Excludes password_hash."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    id: int
    name: str
    email: str
    role: str
    department: str
    status: str
    phone: str | None = None
    bio: str | None = None
    avatar: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    """Paginated response for listing users."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    items: list[UserResponse]
    total: int = Field(description="Total number of users matching the query")
