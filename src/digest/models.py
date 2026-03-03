from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


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
    highlights: list[str]
    activities: list[ActivityItem]

