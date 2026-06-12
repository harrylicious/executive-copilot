"""Feedback router for chat message like/dislike ratings."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat_feedback import ChatFeedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    """Request schema for submitting feedback."""

    message_id: str = Field(..., min_length=1, max_length=128)
    session_id: Optional[str] = Field(None, max_length=128)
    rating: str = Field(..., pattern="^(like|dislike)$")
    reason: Optional[str] = Field(None, max_length=2000)


class FeedbackResponse(BaseModel):
    """Response schema after submitting feedback."""

    id: int
    message_id: str
    rating: str
    success: bool = True


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(body: FeedbackRequest, db: Session = Depends(get_db)) -> FeedbackResponse:
    """Submit like/dislike feedback for a chat message.

    If feedback already exists for the same message_id, it will be updated
    (upsert behavior) rather than creating a duplicate.

    Returns:
        FeedbackResponse with the feedback ID and confirmation.
    """
    # Check for existing feedback on this message
    existing = db.query(ChatFeedback).filter(ChatFeedback.message_id == body.message_id).first()

    if existing:
        # Update existing feedback
        existing.rating = body.rating
        existing.reason = body.reason
        db.commit()
        db.refresh(existing)
        return FeedbackResponse(id=existing.id, message_id=existing.message_id, rating=existing.rating)

    # Create new feedback
    feedback = ChatFeedback(
        message_id=body.message_id,
        session_id=body.session_id,
        rating=body.rating,
        reason=body.reason,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return FeedbackResponse(id=feedback.id, message_id=feedback.message_id, rating=feedback.rating)


class FeedbackItem(BaseModel):
    """A single feedback entry for a message."""

    message_id: str
    rating: str
    reason: Optional[str] = None


@router.get("/session/{session_id}", response_model=list[FeedbackItem])
async def get_session_feedback(session_id: str, db: Session = Depends(get_db)) -> list[FeedbackItem]:
    """Get all feedback entries for a given session.

    Returns:
        List of feedback items with message_id, rating, and optional reason.
    """
    feedbacks = db.query(ChatFeedback).filter(ChatFeedback.session_id == session_id).all()
    return [
        FeedbackItem(message_id=f.message_id, rating=f.rating, reason=f.reason)
        for f in feedbacks
    ]
