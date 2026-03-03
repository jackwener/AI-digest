import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List

from digest.collectors.base import Collector
from digest.models import NormalizedSession


class CodexCollector(Collector):
    def __init__(self, base_dir: str = "~/.codex"):
        self.base_dir = Path(os.path.expanduser(base_dir))

    @property
    def source_name(self) -> str:
        return "Codex"

    def collect(self, target_date: date) -> List[NormalizedSession]:
        if not self.base_dir.exists():
            return []

        sessions = []
        for jsonl_file in self.base_dir.rglob("rollout-*.jsonl"):
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

    def _extract_timestamp_from_record(self, obj: dict) -> datetime | None:
        ts_str = obj.get("timestamp")
        if ts_str:
            try:
                # Handle 'Z' for UTC timezone
                return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None

    def _parse_session(
        self, filepath: Path, target_date: date
    ) -> NormalizedSession | None:
        messages_count = 0
        timestamps = []
        first_prompt = ""
        project_path = ""
        context_lines = []

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

                    ts = self._extract_timestamp_from_record(obj)
                    if ts:
                        timestamps.append(ts)

                    msg_type = obj.get("type", "")
                    
                    # Codex specific: extract project from metadata payload
                    if msg_type == "session_meta":
                        meta = obj.get("payload", {})
                        if "cwd" in meta and not project_path:
                            project_path = Path(meta["cwd"]).name
                            
                    elif msg_type == "response_item":
                        payload = obj.get("payload", {})
                        if isinstance(payload, dict) and payload.get("type") == "message":
                            role = payload.get("role")
                            if role in ("user", "assistant"):
                                messages_count += 1
                                content = self._extract_content(payload)
                                if content:
                                    role_name = "User" if role == "user" else "AI"
                                    context_lines.append(f"{role_name}: {content}")
                                
                                if role == "user" and not first_prompt:
                                    first_prompt = content

        except (OSError, IOError):
            return None

        if not timestamps:
            return None

        start_time = min(timestamps)
        end_time = max(timestamps)

        # Codex date is in filename, but double check with content timestamps
        if start_time.date() != target_date and end_time.date() != target_date:
            return None

        title = first_prompt[:120] if first_prompt else ""
        
        full_context = "\n".join(context_lines)
        if len(full_context) > 20000:
            full_context = full_context[:20000] + "\n...[Truncated]"

        return NormalizedSession(
            id=filepath.stem,
            source=self.source_name,
            project_path=project_path,
            start_time=start_time,
            end_time=end_time,
            title_or_prompt=title,
            message_count=messages_count,
            full_context=full_context,
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
