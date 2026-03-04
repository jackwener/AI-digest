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
    
    return DigestConfig(**data)
