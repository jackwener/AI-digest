import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from digest.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_falls_back_to_anthropic_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "missing.yaml"
            with patch.dict(
                os.environ,
                {
                    "ANTHROPIC_API_KEY": "env-key",
                    "ANTHROPIC_MODEL": "claude-test",
                    "ANTHROPIC_BASE_URL": "https://anthropic.example",
                },
                clear=False,
            ):
                config = load_config(str(config_path))

            self.assertEqual(config.ai.provider, "anthropic")
            self.assertEqual(config.ai.api_key, "env-key")
            self.assertEqual(config.ai.model, "claude-test")
            self.assertEqual(config.ai.base_url, "https://anthropic.example")
            self.assertFalse(config_path.exists())


if __name__ == "__main__":
    unittest.main()
