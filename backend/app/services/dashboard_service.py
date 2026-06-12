"""Service layer for dashboard analytics aggregation queries."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, distinct, case, and_
from sqlalchemy.orm import Session

from app.models.chat_session import ChatMessageRecord
from app.models.file import File
from app.schemas.dashboard import (
    DashboardAnalytics,
    DeptDistribution,
    KPIData,
    QueryTrend,
    RecentActivity,
)


def _get_total_documents(db: Session) -> int:
    """Count total documents in the files table (excluding soft-deleted)."""
    return db.query(func.count(File.id)).filter(File.is_deleted == False).scalar() or 0


def _get_daily_queries(db: Session) -> int:
    """Count user messages created today (UTC)."""
    now_utc = datetime.now(timezone.utc)
    start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(func.count(ChatMessageRecord.id))
        .filter(
            ChatMessageRecord.role == "user",
            ChatMessageRecord.created_at >= start_of_day,
        )
        .scalar()
        or 0
    )


def _get_active_departments(db: Session) -> int:
    """Count distinct departments that have at least one (non-deleted) file."""
    return (
        db.query(func.count(distinct(File.department)))
        .filter(File.is_deleted == False)
        .scalar()
        or 0
    )


def _get_ai_accuracy(db: Session) -> float:
    """Compute AI accuracy as percentage of assistant messages with non-empty sources.

    Returns 0.0 if there are no assistant messages.
    """
    total_assistant = (
        db.query(func.count(ChatMessageRecord.id))
        .filter(ChatMessageRecord.role == "assistant")
        .scalar()
        or 0
    )
    if total_assistant == 0:
        return 0.0

    # Messages with non-empty sources: sources is not NULL and not an empty list '[]'
    with_sources = (
        db.query(func.count(ChatMessageRecord.id))
        .filter(
            ChatMessageRecord.role == "assistant",
            ChatMessageRecord.sources.isnot(None),
            ChatMessageRecord.sources != "[]",
            ChatMessageRecord.sources != "null",
        )
        .scalar()
        or 0
    )
    return round((with_sources / total_assistant) * 100, 1)


def _get_department_distribution(db: Session) -> list[DeptDistribution]:
    """Get query counts per department for the current week (Monday 00:00 UTC to now).

    Department is derived from the department field of files referenced in
    the chat_messages sources array. We query assistant messages (which have sources)
    and extract the department from each source attribution.
    """
    now_utc = datetime.now(timezone.utc)
    # Monday 00:00 UTC of the current week
    days_since_monday = now_utc.weekday()  # Monday=0
    start_of_week = (now_utc - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Get assistant messages with sources from this week
    messages = (
        db.query(ChatMessageRecord.sources)
        .filter(
            ChatMessageRecord.role == "assistant",
            ChatMessageRecord.created_at >= start_of_week,
            ChatMessageRecord.sources.isnot(None),
            ChatMessageRecord.sources != "[]",
            ChatMessageRecord.sources != "null",
        )
        .all()
    )

    # Aggregate department counts from sources
    dept_counts: dict[str, int] = {}
    for (sources,) in messages:
        if not sources or not isinstance(sources, list):
            continue
        # Track unique departments per message to count once per query
        seen_depts: set[str] = set()
        for source in sources:
            if isinstance(source, dict) and "department" in source:
                dept = source["department"]
                if dept not in seen_depts:
                    seen_depts.add(dept)
        for dept in seen_depts:
            dept_counts[dept] = dept_counts.get(dept, 0) + 1

    return [
        DeptDistribution(department=dept, query_count=count)
        for dept, count in sorted(dept_counts.items(), key=lambda x: x[1], reverse=True)
    ]


def _get_query_trend(db: Session) -> list[QueryTrend]:
    """Get daily query counts for the last 7 calendar days (UTC).

    Includes days with zero queries.
    """
    now_utc = datetime.now(timezone.utc)
    today = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    # Build list of last 7 days
    days = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        days.append(day)

    # Get counts for each day
    trend: list[QueryTrend] = []
    for day in days:
        next_day = day + timedelta(days=1)
        count = (
            db.query(func.count(ChatMessageRecord.id))
            .filter(
                ChatMessageRecord.role == "user",
                ChatMessageRecord.created_at >= day,
                ChatMessageRecord.created_at < next_day,
            )
            .scalar()
            or 0
        )
        trend.append(QueryTrend(date=day.strftime("%Y-%m-%d"), count=count))

    return trend


def _get_recent_activities(db: Session) -> list[RecentActivity]:
    """Get the 10 most recent activities combining uploads and user queries.

    Uploads come from the files table, queries from chat_messages (role=user).
    Results are ordered by most recent first.
    """
    # Get recent uploads (non-deleted files)
    recent_uploads = (
        db.query(File.department, File.name, File.created_at)
        .filter(File.is_deleted == False)
        .order_by(File.created_at.desc())
        .limit(10)
        .all()
    )

    # Get recent user queries
    recent_queries = (
        db.query(
            ChatMessageRecord.content,
            ChatMessageRecord.created_at,
            ChatMessageRecord.sources,
            ChatMessageRecord.session_id,
        )
        .filter(ChatMessageRecord.role == "user")
        .order_by(ChatMessageRecord.created_at.desc())
        .limit(10)
        .all()
    )

    # Convert to RecentActivity objects
    activities: list[RecentActivity] = []

    for dept, name, created_at in recent_uploads:
        activities.append(
            RecentActivity(
                department=dept,
                description=name,
                activity_type="upload",
                timestamp=created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                if created_at
                else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )

    for content, created_at, sources, session_id in recent_queries:
        # Derive department from the next assistant message's sources in the same session,
        # or fall back to "unknown"
        dept = "unknown"
        if sources and isinstance(sources, list) and len(sources) > 0:
            # User messages typically don't have sources, but check anyway
            first_source = sources[0]
            if isinstance(first_source, dict) and "department" in first_source:
                dept = first_source["department"]

        # If user message has no sources, look up the assistant response's sources
        if dept == "unknown":
            # Find the assistant reply to this query in the same session
            assistant_msg = (
                db.query(ChatMessageRecord.sources)
                .filter(
                    ChatMessageRecord.session_id == session_id,
                    ChatMessageRecord.role == "assistant",
                    ChatMessageRecord.created_at >= created_at,
                    ChatMessageRecord.sources.isnot(None),
                    ChatMessageRecord.sources != "[]",
                    ChatMessageRecord.sources != "null",
                )
                .order_by(ChatMessageRecord.created_at.asc())
                .first()
            )
            if assistant_msg and assistant_msg[0]:
                assistant_sources = assistant_msg[0]
                if isinstance(assistant_sources, list) and len(assistant_sources) > 0:
                    first_source = assistant_sources[0]
                    if isinstance(first_source, dict) and "department" in first_source:
                        dept = first_source["department"]

        description = (content or "")[:80]
        activities.append(
            RecentActivity(
                department=dept,
                description=description,
                activity_type="query",
                timestamp=created_at.strftime("%Y-%m-%dT%H:%M:%SZ")
                if created_at
                else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )

    # Sort all by timestamp descending, take top 10
    activities.sort(key=lambda a: a.timestamp, reverse=True)
    return activities[:10]


def get_dashboard_analytics(db: Session) -> DashboardAnalytics:
    """Aggregate all dashboard analytics into a single response."""
    kpi = KPIData(
        total_documents=_get_total_documents(db),
        total_queries_today=_get_daily_queries(db),
        active_departments=_get_active_departments(db),
        ai_accuracy=_get_ai_accuracy(db),
    )

    return DashboardAnalytics(
        kpi=kpi,
        department_distribution=_get_department_distribution(db),
        query_trend=_get_query_trend(db),
        recent_activities=_get_recent_activities(db),
    )
