"""
Ollama client helpers.
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import Any, Dict, List, Optional


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _get_json(url: str) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=15) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def list_models(endpoint: str) -> List[str]:
    payload = _get_json(f"{endpoint.rstrip('/')}/api/tags")
    models = payload.get("models", [])
    return [model.get("name", "") for model in models if model.get("name")]


async def list_models_async(endpoint: str) -> List[str]:
    return await asyncio.to_thread(list_models, endpoint)


def chat(
    endpoint: str,
    model: str,
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
) -> str:
    payload_messages = list(messages)
    if system_prompt:
        payload_messages.insert(0, {"role": "system", "content": system_prompt})
    payload = {
        "model": model,
        "messages": payload_messages,
        "stream": False,
    }
    response = _post_json(f"{endpoint.rstrip('/')}/api/chat", payload)
    message = response.get("message", {})
    return message.get("content", "")


async def chat_async(
    endpoint: str,
    model: str,
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
) -> str:
    return await asyncio.to_thread(chat, endpoint, model, messages, system_prompt)
