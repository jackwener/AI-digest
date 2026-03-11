from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

class AIConfig(BaseModel):
    api_key: str
    model: str = "gpt-4o-mini"
    base_url: Optional[str] = None
    provider: str = "openai"

class DigestConfig(BaseModel):
    ai: AIConfig

def load_config(config_path: str = "config.yaml") -> DigestConfig:
    path = Path(os.path.expanduser(config_path))
    if not path.exists():
        env_api_key = os.getenv("ANTHROPIC_API_KEY")
        if env_api_key:
            return DigestConfig(
                ai=AIConfig(
                    api_key=env_api_key,
                    model=os.getenv("ANTHROPIC_MODEL", "claude-3-7-sonnet-latest"),
                    base_url=os.getenv("ANTHROPIC_BASE_URL"),
                    provider="anthropic",
                )
            )

        # Auto-create template if missing
        path.parent.mkdir(parents=True, exist_ok=True)
        template = {
            "ai": {
                "api_key": "YOUR_API_KEY",
                "model": "gpt-4o-mini",
                "base_url": "https://api.openai.com/v1",
                "provider": "openai"
            }
        }
        with open(path, "w") as f:
            yaml.dump(template, f, default_flow_style=False)
        raise FileNotFoundError(f"Config file not found. Created template at {path}. Please edit it with your API key.")
    
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Config file {path} is empty.")

    config = DigestConfig(**data)

    if config.ai.provider.lower() == "anthropic" and config.ai.api_key == "YOUR_API_KEY":
        env_api_key = os.getenv("ANTHROPIC_API_KEY")
        if env_api_key:
            config.ai.api_key = env_api_key
            config.ai.model = os.getenv("ANTHROPIC_MODEL", config.ai.model)
            config.ai.base_url = os.getenv("ANTHROPIC_BASE_URL", config.ai.base_url)

    return config
