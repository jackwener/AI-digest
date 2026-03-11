import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from digest.collectors.antigravity import AntigravityCollector
from digest.collectors.claude_code import ClaudeCodeCollector
from digest.collectors.codex import CodexCollector


class CollectorOverlapTests(unittest.TestCase):
    def test_codex_includes_session_overlapping_target_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "rollout-2026-03-03T23-50-00-test.jsonl"
            records = [
                {"timestamp": "2026-03-03T15:50:00Z", "type": "session_meta", "payload": {"cwd": "/tmp/demo"}},
                {
                    "timestamp": "2026-03-05T16:10:00Z",
                    "type": "response_item",
                    "payload": {"type": "message", "role": "user", "content": "hello"},
                },
            ]
            path.write_text("\n".join(json.dumps(record) for record in records))

            sessions = CodexCollector(base_dir=tmpdir).collect(date(2026, 3, 4))

            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].project_path, "demo")

    def test_claude_code_includes_session_overlapping_target_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "Users-jakevin-code-demo"
            project_dir.mkdir()
            session_file = project_dir / "session.jsonl"
            records = [
                {"type": "human", "timestamp": "2026-03-03T15:50:00Z", "message": {"content": "start"}},
                {"type": "assistant", "timestamp": "2026-03-05T16:10:00Z", "message": {"content": "finish"}},
            ]
            session_file.write_text("\n".join(json.dumps(record) for record in records))

            sessions = ClaudeCodeCollector(base_dir=tmpdir).collect(date(2026, 3, 4))

            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].project_path, "demo")

    def test_antigravity_includes_session_overlapping_target_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            brain_dir = Path(tmpdir) / "brain"
            conv_dir = Path(tmpdir) / "conv"
            brain_dir.mkdir()
            conv_dir.mkdir()
            session_dir = brain_dir / "session-1"
            session_dir.mkdir()
            meta_file = session_dir / "artifact.metadata.json"
            meta_file.write_text(
                json.dumps(
                    {
                        "createdAt": "2026-03-03T15:50:00Z",
                        "updatedAt": "2026-03-05T16:10:00Z",
                        "summary": "demo summary",
                    }
                )
            )

            sessions = AntigravityCollector(brain_dir=str(brain_dir), conv_dir=str(conv_dir)).collect(
                date(2026, 3, 4)
            )

            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].id, "session-1")


if __name__ == "__main__":
    unittest.main()
