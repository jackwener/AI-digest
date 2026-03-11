from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional, Union
from pydantic import BaseModel

# System local timezone for display and date filtering
LOCAL_TZ = datetime.now().astimezone().tzinfo


def to_local(dt: datetime) -> datetime:
    """Convert a UTC-aware datetime to system local timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ)


def overlaps_target_date(start_time: datetime, end_time: datetime, target_date: date) -> bool:
    """Return True when a local-time interval overlaps the given local date."""
    local_start = to_local(start_time)
    local_end = to_local(end_time)
    day_start = datetime.combine(target_date, time.min, tzinfo=LOCAL_TZ)
    next_day = day_start + timedelta(days=1)
    return local_start < next_day and local_end >= day_start


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
    details: List[str]


class DailySummary(BaseModel):
    """The final structured LLM daily report."""

    date: str
    highlights: Union[List[str], str]
    activities: list[ActivityItem]
