"""Pydantic schemas for dashboard analytics API responses."""

from pydantic import BaseModel, Field


class KPIData(BaseModel):
    """Key performance indicator metrics for the dashboard."""

    total_documents: int = Field(..., description="Total number of documents in the files table")
    total_queries_today: int = Field(..., description="Total user queries for the current UTC day")
    active_departments: int = Field(..., description="Number of departments with at least one file")
    ai_accuracy: float = Field(..., description="Percentage of assistant messages with non-empty sources")


class DeptDistribution(BaseModel):
    """Query count breakdown per department for the current week."""

    department: str = Field(..., description="Department name")
    query_count: int = Field(..., description="Number of queries attributed to this department")


class QueryTrend(BaseModel):
    """Daily query count for trend visualization."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    count: int = Field(..., description="Number of queries on this date")


class RecentActivity(BaseModel):
    """A recent activity entry (upload or query)."""

    department: str = Field(..., description="Department associated with the activity")
    description: str = Field(..., description="Activity description (file name or message excerpt)")
    activity_type: str = Field(..., description="Type of activity: 'upload' or 'query'")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp of the activity")


class DashboardAnalytics(BaseModel):
    """Top-level response model for GET /api/dashboard/analytics."""

    kpi: KPIData
    department_distribution: list[DeptDistribution]
    query_trend: list[QueryTrend]
    recent_activities: list[RecentActivity]
