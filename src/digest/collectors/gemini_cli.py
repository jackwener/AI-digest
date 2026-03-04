import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List

from digest.collectors.base import Collector
from digest.models import NormalizedSession, to_local


class GeminiCliCollector(Collector):
    def __init__(self, base_dir: str = "~/.gemini/history"):
        self.base_dir = Path(os.path.expanduser(base_dir))

    @property
    def source_name(self) -> str:
        return "Gemini CLI"

    def collect(self, target_date: date) -> List[NormalizedSession]:
        if not self.base_dir.exists():
            return []

        sessions = []
        # Gemini CLI currently stores very little locally (just .project_root files)
        # We will use the mtime of the project history directory as a proxy for an "active session"
        for project_dir in self.base_dir.iterdir():
            if not project_dir.is_dir():
                continue

            session = self._parse_from_dir_mtime(project_dir, target_date)
            if session:
                sessions.append(session)

        return sorted(sessions, key=lambda s: s.start_time)

    def _parse_from_dir_mtime(
        self, project_dir: Path, target_date: date
    ) -> NormalizedSession | None:
        try:
            mtime = to_local(datetime.fromtimestamp(
                project_dir.stat().st_mtime, tz=timezone.utc
            ))
        except OSError:
            return None

        if mtime.date() != target_date:
            # Also check if any files inside were modified on target date
            has_activity = False
            try:
                for f in project_dir.glob("*"):
                    fmtime = to_local(datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc))
                    if fmtime.date() == target_date:
                        has_activity = True
                        mtime = fmtime
                        break
            except OSError:
                pass
            
            if not has_activity:
                return None

        project_name = project_dir.name

        return NormalizedSession(
            id=f"gemini-{project_name}-{mtime.strftime('%Y%m%d')}",
            source=self.source_name,
            project_path=project_name,
            start_time=mtime,
            end_time=mtime,
            title_or_prompt=f"Gemini CLI session in {project_name}",
            message_count=0,
            full_context="No expanded logs currently available offline for Gemini CLI.",
        )
