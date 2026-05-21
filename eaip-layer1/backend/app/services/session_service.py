"""Service layer for chat session and message persistence."""

from sqlalchemy.orm import Session

from app.models.chat_session import ChatMessageRecord, ChatSession


def list_sessions(db: Session) -> list[ChatSession]:
    """Return all sessions ordered by most recently updated."""
    return db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()


def get_session(db: Session, session_id: str) -> ChatSession | None:
    """Return a single session by ID, or None if not found."""
    return db.query(ChatSession).filter(ChatSession.id == session_id).first()


def get_session_messages(db: Session, session_id: str) -> list[ChatMessageRecord]:
    """Return all messages for a session ordered by timestamp."""
    return (
        db.query(ChatMessageRecord)
        .filter(ChatMessageRecord.session_id == session_id)
        .order_by(ChatMessageRecord.timestamp.asc())
        .all()
    )


def save_session(
    db: Session,
    session_id: str,
    title: str | None = None,
    retrieval_mode: str | None = "combined",
    top_k: int | None = None,
    max_tokens: int | None = None,
    messages: list[dict] | None = None,
) -> ChatSession:
    """Create or update a session and its messages.

    Messages are upserted: existing messages (by ID) are updated,
    new messages are inserted.
    """
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

    if session is None:
        session = ChatSession(
            id=session_id,
            title=title,
            retrieval_mode=retrieval_mode,
            top_k=top_k,
            max_tokens=max_tokens,
        )
        db.add(session)
    else:
        if title is not None:
            session.title = title
        if retrieval_mode is not None:
            session.retrieval_mode = retrieval_mode
        if top_k is not None:
            session.top_k = top_k
        if max_tokens is not None:
            session.max_tokens = max_tokens

    if messages is not None:
        # Get existing message IDs for this session
        existing_ids = {
            row.id
            for row in db.query(ChatMessageRecord.id)
            .filter(ChatMessageRecord.session_id == session_id)
            .all()
        }

        for msg in messages:
            if msg["id"] in existing_ids:
                # Update existing message (content may have grown during streaming)
                db.query(ChatMessageRecord).filter(
                    ChatMessageRecord.id == msg["id"]
                ).update(
                    {
                        "content": msg.get("content", ""),
                        "sources": msg.get("sources"),
                        "metadata_json": msg.get("metadata_json"),
                        "error": msg.get("error"),
                    }
                )
            else:
                record = ChatMessageRecord(
                    id=msg["id"],
                    session_id=session_id,
                    role=msg["role"],
                    content=msg.get("content", ""),
                    sources=msg.get("sources"),
                    metadata_json=msg.get("metadata_json"),
                    error=msg.get("error"),
                    timestamp=msg["timestamp"],
                )
                db.add(record)

    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session_id: str) -> bool:
    """Delete a session and all its messages. Returns True if found."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session is None:
        return False

    db.query(ChatMessageRecord).filter(
        ChatMessageRecord.session_id == session_id
    ).delete()
    db.delete(session)
    db.commit()
    return True
