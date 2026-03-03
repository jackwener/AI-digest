import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List

from digest.collectors.base import Collector
from digest.models import NormalizedSession


class OpenCodeCollector(Collector):
    def __init__(self, base_dir: str = "~/Library/Application Support/ai.opencode.desktop"):
        self.base_dir = Path(os.path.expanduser(base_dir))

    @property
    def source_name(self) -> str:
        return "OpenCode"

    def collect(self, target_date: date) -> List[NormalizedSession]:
        if not self.base_dir.exists():
            return []

        sessions = []
        for workspace_file in self.base_dir.glob("opencode.workspace.*.dat"):
            session = self._parse_workspace_file(workspace_file, target_date)
            # A single workspace file can contain multiple sessions
            if session:
                sessions.extend(session)

        return sorted(sessions, key=lambda s: s.start_time)

    def _parse_workspace_file(
        self, filepath: Path, target_date: date
    ) -> List[NormalizedSession]:
        sessions = []
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(data, dict):
            return []

        # Find all session keys
        # format: "session:ses_...:prompt" or "session:ses_...:comments"
        session_data = {}
        for key, value_str in data.items():
            if key.startswith("session:"):
                parts = key.split(":")
                if len(parts) >= 3:
                    sess_id = parts[1]
                    field_type = parts[2]
                    
                    if sess_id not in session_data:
                        session_data[sess_id] = {"prompts": [], "mtime": None}
                    
                    try:
                        val = json.loads(value_str)
                        if field_type == "prompt" and isinstance(val, dict):
                            prompts = val.get("prompt", [])
                            if isinstance(prompts, list):
                                for p in prompts:
                                    if p.get("type") == "text" and p.get("content"):
                                        session_data[sess_id]["prompts"].append(p["content"])
                    except json.JSONDecodeError:
                        pass

        # Since workspace dat files don't store distinct timestamps per session accurately inside the JSON,
        # we will use the file's modification time as a proxy, and check if it falls on target_date.
        try:
            mtime = datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return []

        if mtime.date() != target_date:
            return []

        for sess_id, sdata in session_data.items():
            prompts = sdata["prompts"]
            if not prompts:
                title = f"OpenCode session"
            else:
                title = prompts[0][:120]

            sessions.append(
                NormalizedSession(
                    id=sess_id,
                    source=self.source_name,
                    project_path="", # Hard to decode from "L1Vz..." encoded name robustly
                    start_time=mtime,
                    end_time=mtime,
                    title_or_prompt=title,
                    message_count=len(prompts),
                )
            )

        return sessions
