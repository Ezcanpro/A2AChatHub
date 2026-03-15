"""File: llm/client.py.

Optional model client for OpenAI-compatible chat completion endpoints.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib import error, request


class LLMConfigurationError(RuntimeError):
    """Raised when the selected backend is missing required configuration."""


@dataclass
class LLMClient:
    """Thin async wrapper around OpenAI-compatible chat completion APIs."""

    backend: str = "rule"
    model: str = "rule-based-demo"
    base_url: str = ""
    api_key: str = ""
    timeout: int = 60

    @classmethod
    def from_env(
        cls,
        backend: str = "rule",
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> "LLMClient":
        """Build a client from CLI arguments and environment variables."""

        resolved_backend = backend
        if resolved_backend == "auto":
            if os.getenv("OPENAI_API_KEY"):
                resolved_backend = "openai"
            elif os.getenv("A2A_BASE_URL"):
                resolved_backend = "local"
            else:
                resolved_backend = "rule"

        if resolved_backend == "openai":
            return cls(
                backend="openai",
                model=model or os.getenv("A2A_MODEL_NAME", "gpt-4.1-mini"),
                base_url=(base_url or os.getenv("A2A_BASE_URL") or "https://api.openai.com/v1").rstrip("/"),
                api_key=os.getenv("OPENAI_API_KEY", ""),
            )

        if resolved_backend == "local":
            return cls(
                backend="local",
                model=model or os.getenv("A2A_MODEL_NAME", "qwen2.5:7b-instruct"),
                base_url=(base_url or os.getenv("A2A_BASE_URL") or "http://127.0.0.1:11434/v1").rstrip("/"),
                api_key=os.getenv("A2A_API_KEY", ""),
            )

        return cls(
            backend="rule",
            model=model or "rule-based-demo",
            base_url=(base_url or "").rstrip("/"),
            api_key=os.getenv("A2A_API_KEY", ""),
        )

    @property
    def is_live_backend(self) -> bool:
        """Return whether the client is configured for a live HTTP backend."""

        return self.backend in {"openai", "local"}

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        conversation: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.3,
    ) -> str:
        """Generate a text completion from the selected backend."""

        if not self.is_live_backend:
            raise LLMConfigurationError("Live model backend is disabled.")

        return await asyncio.to_thread(
            self._generate_sync,
            system_prompt,
            user_prompt,
            conversation or [],
            temperature,
        )

    def _generate_sync(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation: List[Dict[str, str]],
        temperature: float,
    ) -> str:
        if self.backend == "openai" and not self.api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY is required when backend is 'openai'."
            )

        if not self.base_url:
            raise LLMConfigurationError(
                "A model base URL is required for live backends."
            )

        payload = {
            "model": self.model,
            "messages": self._build_messages(system_prompt, user_prompt, conversation),
            "temperature": temperature,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        api_request = request.Request(
            url=self._chat_completions_url(),
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(api_request, timeout=self.timeout) as response:
                raw_data = response.read().decode("utf-8")
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"Model request failed with HTTP {exc.code}: {details or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(
                f"Model request failed: unable to reach {self.base_url}. {exc.reason}"
            ) from exc

        parsed = json.loads(raw_data)
        return self._extract_content(parsed)

    def _chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    @staticmethod
    def _build_messages(
        system_prompt: str,
        user_prompt: str,
        conversation: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(conversation)
        messages.append({"role": "user", "content": user_prompt})
        return messages

    @staticmethod
    def _extract_content(payload: Dict[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                "Model response did not contain choices[0].message.content."
            ) from exc

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            text_parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
                elif isinstance(item, dict) and "text" in item:
                    text_parts.append(str(item["text"]))
            merged = "\n".join(part for part in text_parts if part.strip()).strip()
            if merged:
                return merged

        raise RuntimeError("Model response content was empty or unsupported.")
