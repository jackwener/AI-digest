import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List

from digest.collectors.base import Collector
from digest.models import NormalizedSession


class CodexCollector(Collector):
    def __init__(self, base_dir: str = "~/.codex/archived_sessions"):
        self.base_dir = Path(os.path.expanduser(base_dir))

    @property
    def source_name(self) -> str:
        return "Codex"

    def collect(self, target_date: date) -> List[NormalizedSession]:
        if not self.base_dir.exists():
            return []

        sessions = []
        for jsonl_file in self.base_dir.glob("rollout-*.jsonl"):
            # Format: rollout-YYYY-MM-DDTHH-MM-SS-...
            fname = jsonl_file.stem
            file_date = self._extract_date_from_filename(fname)
            if file_date and file_date != target_date:
                continue

            session = self._parse_session(jsonl_file, target_date)
            if session:
                sessions.append(session)

        return sorted(sessions, key=lambda s: s.start_time)

    def _extract_date_from_filename(self, filename: str) -> date | None:
        try:
            parts = filename.replace("rollout-", "")
            date_str = parts[:10]  # "YYYY-MM-DD"
            return date.fromisoformat(date_str)
        except (ValueError, IndexError):
            return None

    def _parse_session(
        self, filepath: Path, target_date: date
    ) -> NormalizedSession | None:
        meta = {}
        first_prompt = ""
        timestamps = []
        msg_count = 0

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
                    ts_str = obj.get("timestamp")

                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            timestamps.append(ts)
                        except ValueError:
                            pass

                    if msg_type == "session_meta":
                        meta = obj.get("payload", {})
                    elif msg_type == "message":
                        msg_count += 1
                        payload = obj.get("payload", {})
                        if isinstance(payload, dict) and payload.get("role") == "user":
                            if not first_prompt:
                                first_prompt = self._extract_content(payload)

        except (OSError, IOError):
            return None

        if not timestamps:
            return None

        start_time = min(timestamps)
        end_time = max(timestamps)

        if start_time.date() != target_date and end_time.date() != target_date:
            return None

        project = self._parse_project(meta.get("cwd", ""))
        session_id = meta.get("id", filepath.stem)

        return NormalizedSession(
            id=session_id,
            source=self.source_name,
            project_path=project,
            start_time=start_time,
            end_time=end_time,
            title_or_prompt=first_prompt[:120] if first_prompt else "Codex session",
            message_count=msg_count,
        )

    def _parse_project(self, cwd: str) -> str:
        if not cwd:
            return ""
        parts = Path(cwd).parts
        try:
            code_idx = list(parts).index("code")
            remaining = parts[code_idx + 1 :]
            return "/".join(remaining[:2]) if remaining else parts[-1]
        except ValueError:
            return parts[-1] if parts else ""

    def _extract_content(self, payload: dict) -> str:
        content = payload.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") in ("input_text", "text"):
                        texts.append(item.get("text", ""))
                elif isinstance(item, str):
                    texts.append(item)
            return " ".join(texts).strip()
        return ""
