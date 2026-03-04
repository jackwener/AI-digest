import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List

from digest.collectors.base import Collector
from digest.models import NormalizedSession, to_local


class AntigravityCollector(Collector):
    def __init__(
        self,
        brain_dir: str = "~/.gemini/antigravity/brain",
        conv_dir: str = "~/.gemini/antigravity/conversations",
    ):
        self.brain_dir = Path(os.path.expanduser(brain_dir))
        self.conv_dir = Path(os.path.expanduser(conv_dir))

    @property
    def source_name(self) -> str:
        return "Antigravity"

    def collect(self, target_date: date) -> List[NormalizedSession]:
        sessions = []

        if self.brain_dir.exists():
            for session_dir in self.brain_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                session = self._parse_from_brain(session_dir, target_date)
                if session:
                    sessions.append(session)

        seen_ids = {s.id for s in sessions}
        if self.conv_dir.exists():
            for pb_file in self.conv_dir.glob("*.pb"):
                session_id = pb_file.stem
                if session_id in seen_ids:
                    continue
                session = self._parse_from_pb_metadata(pb_file, target_date)
                if session:
                    sessions.append(session)

        return sorted(sessions, key=lambda s: s.start_time)

    def _parse_from_brain(
        self, session_dir: Path, target_date: date
    ) -> NormalizedSession | None:
        session_id = session_dir.name
        timestamps = []
        title = ""
        project_path = ""
        context_lines = []
        summaries = []

        artifact_files = list(session_dir.glob("*.metadata.json"))
        for meta_file in artifact_files:
            try:
                with open(meta_file) as f:
                    meta = json.load(f)

                for ts_field in ("createdAt", "updatedAt", "lastModified"):
                    ts_val = meta.get(ts_field)
                    if ts_val:
                        ts = self._parse_ts(ts_val)
                        if ts:
                            timestamps.append(ts)

                summary = meta.get("summary", "")
                if summary:
                    summaries.append(summary)
            except (json.JSONDecodeError, OSError):
                continue

        # Build title from summaries (prefer the longest/most descriptive one)
        if summaries:
            best_summary = max(summaries, key=len)
            title = best_summary[:150]

        md_files = list(session_dir.glob("*.md"))
        for md_file in md_files:
            if md_file.name.endswith(".metadata.json"):
                continue
            try:
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime, tz=timezone.utc)
                timestamps.append(mtime)

                with open(md_file) as f:
                    content_text = f.read()
                    
                context_lines.append(f"Artifact Context [File: {md_file.name}]:")
                context_lines.append(content_text)
                
                if not title:
                    lines = content_text.splitlines()
                    for i, line in enumerate(lines):
                        if i >= 5:
                            break
                        line = line.strip()
                        if line.startswith("# "):
                            title = line[2:].strip()[:120]
                            break
            except OSError:
                continue

        sys_gen_dir = session_dir / ".system_generated"
        if sys_gen_dir.exists():
            for log_file in sys_gen_dir.rglob("*"):
                if log_file.is_file():
                    try:
                        mtime = datetime.fromtimestamp(
                            log_file.stat().st_mtime, tz=timezone.utc
                        )
                        timestamps.append(mtime)
                        
                        # specifically target overview.txt for user requests
                        if log_file.name == "overview.txt":
                            with open(log_file) as f:
                                overview_text = f.read()
                                context_lines.append("Activity Log Profile:")
                                context_lines.append(overview_text)
                                # Try to extract project from workspace URIs in overview
                                for oline in overview_text.splitlines():
                                    if "/Users/" in oline and "/code/" in oline:
                                        parts = oline.split("/code/")
                                        if len(parts) > 1:
                                            project_path = parts[1].split("/")[0].split()[0]
                                            break
                    except OSError:
                        pass

        if not timestamps:
            try:
                mtime = datetime.fromtimestamp(
                    session_dir.stat().st_mtime, tz=timezone.utc
                )
                timestamps.append(mtime)
            except OSError:
                return None

        start_time = to_local(min(timestamps))
        end_time = to_local(max(timestamps))

        if start_time.date() != target_date and end_time.date() != target_date:
            return None

        full_context = "\n".join(context_lines)
        if len(full_context) > 20000:
            full_context = full_context[:20000] + "\n...[Truncated]"

        return NormalizedSession(
            id=session_id,
            source=self.source_name,
            project_path=project_path,
            start_time=start_time,
            end_time=end_time,
            title_or_prompt=title or f"Antigravity session",
            message_count=len(md_files),
            full_context=full_context,
        )

    def _parse_from_pb_metadata(
        self, pb_file: Path, target_date: date
    ) -> NormalizedSession | None:
        try:
            stat = pb_file.stat()
            mtime = to_local(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc))
            ctime = to_local(datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc))
        except (OSError, AttributeError):
            return None

        if mtime.date() != target_date and ctime.date() != target_date:
            return None

        return NormalizedSession(
            id=pb_file.stem,
            source=self.source_name,
            project_path="",
            start_time=ctime,
            end_time=mtime,
            title_or_prompt=f"Antigravity session",
            message_count=0,
        )

    def _parse_ts(self, value) -> datetime | None:
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
            except (ValueError, OSError):
                pass
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None
