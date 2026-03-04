from datetime import date, datetime, timezone
from typing import Optional
from pydantic import BaseModel

# System local timezone for display and date filtering
LOCAL_TZ = datetime.now().astimezone().tzinfo


def to_local(dt: datetime) -> datetime:
    """Convert a UTC-aware datetime to system local timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ)


class NormalizedSession(BaseModel):
    """A standardized interaction session from any AI tool."""

    id: str
    source: str
    project_path: str = ""
    start_time: datetime
    end_time: datetime
    title_or_prompt: str = ""
    message_count: int = 0
    full_context: str = ""


class ActivityItem(BaseModel):
    """A high-level clustered activity deduced by LLM."""

    time_range: str
    project: str
    category: str
    summary: str
    details: list[str]


class DailySummary(BaseModel):
    """The final structured LLM daily report."""

    date: str
    highlights: list[str] | str
    activities: list[ActivityItem]

