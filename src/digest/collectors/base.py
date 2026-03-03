from abc import ABC, abstractmethod
from datetime import date
from typing import List

from digest.models import NormalizedSession


class Collector(ABC):
    """Base class for all AI agent data collectors."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the data source (e.g. 'claude-code')."""
        pass

    @abstractmethod
    def collect(self, target_date: date) -> List[NormalizedSession]:
        """Collect and normalize sessions for the given date."""
        pass
