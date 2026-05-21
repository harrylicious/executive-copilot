"""Router for chat session persistence (CRUD)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.session import (
    MessageSchema,
    SaveSessionRequest,
    SessionSchema,
    SessionWithMessagesSchema,
    UpdateSessionTitleRequest,
)
from app.services.session_service import (
    delete_session,
    get_session,
    get_session_messages,
    list_sessions,
    save_session,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSchema])
def get_sessions(db: Session = Depends(get_db)):
    """List all chat sessions, most recent first."""
    sessions = list_sessions(db)
    return [
        SessionSchema(
            id=s.id,
            title=s.title,
            retrieval_mode=s.retrieval_mode,
            top_k=s.top_k,
            max_tokens=s.max_tokens,
            created_at=s.created_at.isoformat() if s.created_at else None,
            updated_at=s.updated_at.isoformat() if s.updated_at else None,
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionWithMessagesSchema)
def get_session_detail(session_id: str, db: Session = Depends(get_db)):
    """Get a session with all its messages."""
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = get_session_messages(db, session_id)
    return SessionWithMessagesSchema(
        id=session.id,
        title=session.title,
        retrieval_mode=session.retrieval_mode,
        top_k=session.top_k,
        max_tokens=session.max_tokens,
        created_at=session.created_at.isoformat() if session.created_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
        messages=[
            MessageSchema(
                id=m.id,
                session_id=m.session_id,
                role=m.role,
                content=m.content,
                sources=m.sources,
                metadata_json=m.metadata_json,
                error=m.error,
                timestamp=m.timestamp,
            )
            for m in messages
        ],
    )


@router.post("", response_model=SessionSchema)
def save_session_endpoint(body: SaveSessionRequest, db: Session = Depends(get_db)):
    """Create or update a session and its messages."""
    messages_data = [
        {
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
            "metadata_json": m.metadata_json,
            "error": m.error,
            "timestamp": m.timestamp,
        }
        for m in body.messages
    ]

    session = save_session(
        db=db,
        session_id=body.id,
        title=body.title,
        retrieval_mode=body.retrieval_mode,
        top_k=body.top_k,
        max_tokens=body.max_tokens,
        messages=messages_data,
    )

    return SessionSchema(
        id=session.id,
        title=session.title,
        retrieval_mode=session.retrieval_mode,
        top_k=session.top_k,
        max_tokens=session.max_tokens,
        created_at=session.created_at.isoformat() if session.created_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
    )


@router.patch("/{session_id}/title", response_model=SessionSchema)
def update_title(
    session_id: str, body: UpdateSessionTitleRequest, db: Session = Depends(get_db)
):
    """Update a session's title."""
    session = get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session.title = body.title
    db.commit()
    db.refresh(session)

    return SessionSchema(
        id=session.id,
        title=session.title,
        retrieval_mode=session.retrieval_mode,
        top_k=session.top_k,
        max_tokens=session.max_tokens,
        created_at=session.created_at.isoformat() if session.created_at else None,
        updated_at=session.updated_at.isoformat() if session.updated_at else None,
    )


@router.delete("/{session_id}", status_code=204)
def delete_session_endpoint(session_id: str, db: Session = Depends(get_db)):
    """Delete a session and all its messages."""
    deleted = delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
