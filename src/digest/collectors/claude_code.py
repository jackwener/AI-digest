import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List

from digest.collectors.base import Collector
from digest.models import NormalizedSession


class ClaudeCodeCollector(Collector):
    def __init__(self, base_dir: str = "~/.claude/projects"):
        self.base_dir = Path(os.path.expanduser(base_dir))

    @property
    def source_name(self) -> str:
        return "Claude Code"

    def collect(self, target_date: date) -> List[NormalizedSession]:
        if not self.base_dir.exists():
            return []

        sessions = []
        for project_dir in self.base_dir.iterdir():
            if not project_dir.is_dir():
                continue

            project_name = self._parse_project_name(project_dir.name)

            for jsonl_file in project_dir.glob("*.jsonl"):
                if "subagent" in str(jsonl_file):
                    continue
                session = self._parse_session(jsonl_file, project_name, target_date)
                if session:
                    sessions.append(session)

        return sorted(sessions, key=lambda s: s.start_time)

    def _parse_project_name(self, dir_name: str) -> str:
        parts = dir_name.strip("-").split("-")
        skip_prefixes = {"Users", "jakevin", "code", "home"}
        meaningful = [p for p in parts if p not in skip_prefixes]
        return "-".join(meaningful[-2:]) if meaningful else dir_name

    def _parse_session(
        self, filepath: Path, project: str, target_date: date
    ) -> NormalizedSession | None:
        messages = 0
        timestamps = []
        first_prompt = ""
        summary_text = ""

        try:
            with open(filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg_type = obj.get("type", "")
                    ts = self._extract_timestamp(obj)
                    if ts:
                        timestamps.append(ts)

                    if msg_type in ("human", "assistant"):
                        messages += 1
                        if msg_type == "human" and not first_prompt:
                            first_prompt = self._extract_content(obj.get("message", {}))

                    elif msg_type == "summary":
                        summary_text = obj.get("summary", "")

        except (OSError, IOError):
            return None

        if not timestamps:
            return None

        start_time = min(timestamps)
        end_time = max(timestamps)

        if start_time.date() != target_date and end_time.date() != target_date:
            return None

        title = summary_text[:120] if summary_text else first_prompt[:120]

        return NormalizedSession(
            id=filepath.stem,
            source=self.source_name,
            project_path=project,
            start_time=start_time,
            end_time=end_time,
            title_or_prompt=title,
            message_count=messages,
        )

    def _extract_timestamp(self, obj: dict) -> datetime | None:
        for field in ("timestamp", "cacheBreaker"):
            val = obj.get(field)
            if isinstance(val, str):
                try:
                    return datetime.fromisoformat(val.replace("Z", "+00:00"))
                except ValueError:
                    pass

        snapshot = obj.get("snapshot", {})
        if isinstance(snapshot, dict):
            ts_val = snapshot.get("timestamp")
            if isinstance(ts_val, str):
                try:
                    return datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                except ValueError:
                    pass

        msg = obj.get("message", {})
        if isinstance(msg, dict):
            for field in ("timestamp", "cacheBreaker"):
                val = msg.get(field)
                if isinstance(val, str):
                    try:
                        return datetime.fromisoformat(val.replace("Z", "+00:00"))
                    except ValueError:
                        pass
        return None

    def _extract_content(self, message: dict) -> str:
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif isinstance(item, str):
                    texts.append(item)
            return " ".join(texts).strip()
        return ""
