import unittest
from datetime import datetime

from digest.analyzer import Analyzer
from digest.config import DigestConfig, AIConfig
from digest.models import LOCAL_TZ, NormalizedSession


class AnalyzerTests(unittest.TestCase):
    def test_build_context_text_respects_global_budget(self) -> None:
        analyzer = Analyzer(DigestConfig(ai=AIConfig(api_key="test")))
        sessions = [
            NormalizedSession(
                id=f"s{i}",
                source="Codex",
                project_path="demo",
                start_time=datetime(2026, 3, 4, 10, i, tzinfo=LOCAL_TZ),
                end_time=datetime(2026, 3, 4, 10, i, tzinfo=LOCAL_TZ),
                title_or_prompt="demo",
                message_count=1,
                full_context="x" * 30000,
            )
            for i in range(3)
        ]

        text = analyzer._build_context_text(sessions)

        self.assertLessEqual(len(text), analyzer.MAX_CONTEXT_CHARS + 200)
        self.assertIn("...[Truncated]", text)


if __name__ == "__main__":
    unittest.main()
