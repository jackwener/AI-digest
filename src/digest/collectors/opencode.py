import json
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Tuple

from digest.collectors.base import Collector
from digest.models import NormalizedSession, to_local


class OpenCodeCollector(Collector):
    def __init__(
        self,
        db_path: str = "~/.local/share/opencode/opencode.db",
        legacy_base_dir: str = "~/Library/Application Support/ai.opencode.desktop",
    ):
        self.db_path = Path(os.path.expanduser(db_path))
        self.legacy_base_dir = Path(os.path.expanduser(legacy_base_dir))

    @property
    def source_name(self) -> str:
        return "OpenCode"

    def collect(self, target_date: date) -> List[NormalizedSession]:
        sessions: List[NormalizedSession] = []

        if self.db_path.exists():
            sessions.extend(self._collect_from_sqlite(target_date))

        if self.legacy_base_dir.exists():
            for workspace_file in self.legacy_base_dir.glob("opencode.workspace.*.dat"):
                session_list = self._parse_workspace(workspace_file, target_date)
                if session_list:
                    sessions.extend(session_list)

        deduped = {}
        for s in sessions:
            prev = deduped.get(s.id)
            if prev is None or s.end_time > prev.end_time:
                deduped[s.id] = s

        return sorted(deduped.values(), key=lambda s: s.start_time)

    def _collect_from_sqlite(self, target_date: date) -> List[NormalizedSession]:
        sessions = []
        target_date_str = target_date.isoformat()

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
        except sqlite3.Error:
            return []

        try:
            rows = conn.execute(
                """
                SELECT
                    s.id,
                    s.title,
                    s.directory,
                    s.time_created,
                    s.time_updated,
                    COALESCE(
                        (
                            SELECT COUNT(*)
                            FROM message m
                            WHERE m.session_id = s.id
                              AND json_extract(m.data, '$.role') IN ('user', 'assistant')
                        ),
                        0
                    ) AS message_count
                FROM session s
                WHERE DATE(DATETIME(s.time_created / 1000, 'unixepoch', 'localtime')) = ?
                   OR DATE(DATETIME(s.time_updated / 1000, 'unixepoch', 'localtime')) = ?
                ORDER BY s.time_created ASC
                """,
                (target_date_str, target_date_str),
            ).fetchall()

            for row in rows:
                sess_id = row["id"]
                start_time = to_local(
                    datetime.fromtimestamp(row["time_created"] / 1000, tz=timezone.utc)
                )
                end_time = to_local(
                    datetime.fromtimestamp(row["time_updated"] / 1000, tz=timezone.utc)
                )

                first_prompt, full_context = self._build_context_from_sqlite(conn, sess_id)
                title = first_prompt[:120] if first_prompt else (row["title"] or "OpenCode session")

                project_name = ""
                if row["directory"]:
                    project_name = Path(row["directory"]).name

                sessions.append(
                    NormalizedSession(
                        id=sess_id,
                        source=self.source_name,
                        project_path=project_name,
                        start_time=start_time,
                        end_time=end_time,
                        title_or_prompt=title,
                        message_count=row["message_count"],
                        full_context=full_context,
                    )
                )
        except sqlite3.Error:
            return []
        finally:
            conn.close()

        return sessions

    def _build_context_from_sqlite(self, conn: sqlite3.Connection, session_id: str) -> Tuple[str, str]:
        first_prompt = ""
        context_lines = []

        rows = conn.execute(
            """
            SELECT
                json_extract(m.data, '$.role') AS role,
                json_extract(p.data, '$.text') AS text
            FROM part p
            JOIN message m ON m.id = p.message_id
            WHERE p.session_id = ?
              AND json_extract(p.data, '$.type') = 'text'
              AND json_extract(m.data, '$.role') IN ('user', 'assistant')
            ORDER BY p.time_created ASC
            """,
            (session_id,),
        ).fetchall()

        for row in rows:
            text = row["text"]
            role = row["role"]
            if not isinstance(text, str) or not text.strip():
                continue
            text = text.strip()

            if role == "user":
                if not first_prompt:
                    first_prompt = text
                context_lines.append(f"User: {text}")
            elif role == "assistant":
                context_lines.append(f"AI: {text}")

        full_context = "\n".join(context_lines)
        if len(full_context) > 20000:
            full_context = full_context[:20000] + "\n...[Truncated]"

        return first_prompt, full_context

    def _parse_workspace(
        self, filepath: Path, target_date: date
    ) -> List[NormalizedSession]:
        sessions = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(data, dict):
            return []

        try:
            mtime = to_local(datetime.fromtimestamp(filepath.stat().st_mtime, tz=timezone.utc))
        except OSError:
            return []

        if mtime.date() != target_date:
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
                        session_data[sess_id] = {"prompts": [], "mtime": mtime}

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

        for sess_id, sdata in session_data.items():
            prompts = sdata["prompts"]

            first_prompt_text = ""
            context_lines = []
            for p in prompts:
                if isinstance(p, str):
                    if not first_prompt_text:
                        first_prompt_text = p
                    context_lines.append(f"User: {p}")
            
            if not prompts:
                title = "OpenCode session"
            else:
                title = first_prompt_text[:120]

            full_context = "\n".join(context_lines)
            if len(full_context) > 20000:
                full_context = full_context[:20000] + "\n...[Truncated]"

            sessions.append(
                NormalizedSession(
                    id=sess_id,
                    source=self.source_name,
                    project_path="", # Hard to decode from "L1Vz..." encoded name robustly
                    start_time=mtime,
                    end_time=mtime,
                    title_or_prompt=title,
                    message_count=len(prompts),
                    full_context=full_context,
                )
            )

        return sessions
