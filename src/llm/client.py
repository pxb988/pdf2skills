"""OpenAI-compatible LLM chat client.

Works with any provider that exposes a ``/chat/completions`` endpoint
compatible with the OpenAI API format (OpenAI, DeepSeek, Zhipu GLM,
Qwen / DashScope, SiliconFlow, and custom endpoints).
"""

from __future__ import annotations

from dataclasses import dataclass

import time

import requests

from ..pipeline.config import LLMProviderConfig


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMClientError(Exception):
    """Raised when the LLM API returns an error."""


class LLMClient:
    """Minimal OpenAI-compatible chat completions client."""

    def __init__(self, config: LLMProviderConfig) -> None:
        if not config.api_key:
            raise ValueError("LLMProviderConfig.api_key is required")
        if not config.base_url:
            raise ValueError("LLMProviderConfig.base_url is required")
        self._config = config

    @property
    def model(self) -> str:
        return self._config.model

    def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Send a chat completion request and return the assistant reply."""
        url = self._config.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._config.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        max_retries = 2
        for attempt in range(max_retries + 1):
            resp = requests.post(url, json=payload, headers=headers, timeout=300)

            if resp.status_code >= 500 and attempt < max_retries:
                wait = 5 * (attempt + 1)
                print(f"  [LLM] {resp.status_code} error, retrying in {wait}s (attempt {attempt + 1}/{max_retries})...", flush=True)
                time.sleep(wait)
                continue
            break

        if resp.status_code != 200:
            raise LLMClientError(
                f"LLM API error {resp.status_code}: {resp.text[:500]}"
            )

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise LLMClientError(f"LLM API returned no choices: {data}")

        return choices[0]["message"]["content"]
