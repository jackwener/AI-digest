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
