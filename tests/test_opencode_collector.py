import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from digest.collectors.opencode import OpenCodeCollector
from digest.models import LOCAL_TZ


class OpenCodeCollectorTests(unittest.TestCase):
    def _create_sqlite_db(self, db_path: Path) -> None:
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE session (
                id text PRIMARY KEY,
                project_id text NOT NULL,
                parent_id text,
                slug text NOT NULL,
                directory text NOT NULL,
                title text NOT NULL,
                version text NOT NULL,
                share_url text,
                summary_additions integer,
                summary_deletions integer,
                summary_files integer,
                summary_diffs text,
                revert text,
                permission text,
                time_created integer NOT NULL,
                time_updated integer NOT NULL,
                time_compacting integer,
                time_archived integer
            );
            CREATE TABLE message (
                id text PRIMARY KEY,
                session_id text NOT NULL,
                time_created integer NOT NULL,
                time_updated integer NOT NULL,
                data text NOT NULL
            );
            CREATE TABLE part (
                id text PRIMARY KEY,
                message_id text NOT NULL,
                session_id text NOT NULL,
                time_created integer NOT NULL,
                time_updated integer NOT NULL,
                data text NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()

    def _insert_session(
        self,
        db_path: Path,
        *,
        session_id: str,
        directory: str,
        title: str,
        created_local: datetime,
        updated_local: datetime,
        prompt: str = "hello",
        response: str = "world",
    ) -> None:
        conn = sqlite3.connect(db_path)
        created_ms = int(created_local.astimezone(LOCAL_TZ).timestamp() * 1000)
        updated_ms = int(updated_local.astimezone(LOCAL_TZ).timestamp() * 1000)
        conn.execute(
            """
            INSERT INTO session (
                id, project_id, parent_id, slug, directory, title, version, time_created, time_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "proj",
                None,
                "slug",
                directory,
                title,
                "1",
                created_ms,
                updated_ms,
            ),
        )
        conn.execute(
            """
            INSERT INTO message (id, session_id, time_created, time_updated, data)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("msg-user", session_id, created_ms, created_ms, json.dumps({"role": "user"})),
        )
        conn.execute(
            """
            INSERT INTO part (id, message_id, session_id, time_created, time_updated, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "part-user",
                "msg-user",
                session_id,
                created_ms,
                created_ms,
                json.dumps({"type": "text", "text": prompt}),
            ),
        )
        conn.execute(
            """
            INSERT INTO message (id, session_id, time_created, time_updated, data)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("msg-ai", session_id, updated_ms, updated_ms, json.dumps({"role": "assistant"})),
        )
        conn.execute(
            """
            INSERT INTO part (id, message_id, session_id, time_created, time_updated, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "part-ai",
                "msg-ai",
                session_id,
                updated_ms,
                updated_ms,
                json.dumps({"type": "text", "text": response}),
            ),
        )
        conn.commit()
        conn.close()

    def test_collect_includes_sessions_overlapping_target_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "opencode.db"
            self._create_sqlite_db(db_path)
            self._insert_session(
                db_path,
                session_id="ses-span",
                directory="/tmp/demo",
                title="Span session",
                created_local=datetime(2026, 3, 3, 23, 50, tzinfo=LOCAL_TZ),
                updated_local=datetime(2026, 3, 5, 0, 10, tzinfo=LOCAL_TZ),
            )

            collector = OpenCodeCollector(db_path=str(db_path), legacy_base_dir=str(Path(tmpdir) / "legacy"))
            sessions = collector.collect(date(2026, 3, 4))

            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].id, "ses-span")
            self.assertEqual(sessions[0].project_path, "demo")

    def test_collect_prefers_sqlite_when_legacy_has_same_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "opencode.db"
            legacy_dir = Path(tmpdir) / "legacy"
            legacy_dir.mkdir()
            self._create_sqlite_db(db_path)
            self._insert_session(
                db_path,
                session_id="ses-shared",
                directory="/tmp/sqlite-project",
                title="SQLite title",
                created_local=datetime(2026, 2, 21, 15, 0, tzinfo=LOCAL_TZ),
                updated_local=datetime(2026, 2, 21, 15, 30, tzinfo=LOCAL_TZ),
                prompt="SQLite prompt",
                response="SQLite answer",
            )

            legacy_file = legacy_dir / "opencode.workspace.test.dat"
            legacy_file.write_text(json.dumps({"session:ses-shared:prompt": json.dumps({"prompt": []})}))
            later_mtime = datetime(2026, 2, 21, 16, 0, tzinfo=LOCAL_TZ).timestamp()
            os.utime(legacy_file, (later_mtime, later_mtime))

            collector = OpenCodeCollector(db_path=str(db_path), legacy_base_dir=str(legacy_dir))
            sessions = collector.collect(date(2026, 2, 21))

            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].id, "ses-shared")
            self.assertEqual(sessions[0].project_path, "sqlite-project")
            self.assertEqual(sessions[0].title_or_prompt, "SQLite prompt")
            self.assertEqual(sessions[0].message_count, 2)


if __name__ == "__main__":
    unittest.main()
