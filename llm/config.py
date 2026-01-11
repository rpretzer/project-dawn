"""
LLM configuration persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from data_paths import data_root


CONFIG_PATH = Path("vault") / "llm_config.json"


@dataclass
class LLMConfig:
    provider: str = "ollama"
    endpoint: str = "http://localhost:11434"
    model: str = ""
    system_prompt: str = "You are a helpful, conversational assistant."

    def to_dict(self) -> dict:
        return asdict(self)


def load_config(path: Optional[Path] = None) -> LLMConfig:
    target = (data_root() / CONFIG_PATH) if path is None else path
    if not target.exists():
        return LLMConfig()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return LLMConfig()
    return LLMConfig(
        provider=payload.get("provider", "ollama"),
        endpoint=payload.get("endpoint", "http://localhost:11434"),
        model=payload.get("model", ""),
        system_prompt=payload.get("system_prompt", "You are a helpful, conversational assistant."),
    )


def save_config(config: LLMConfig, path: Optional[Path] = None) -> Path:
    target = (data_root() / CONFIG_PATH) if path is None else path
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp_path.replace(target)
    return target
