"""Generic AI client for Messages-style APIs."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib import error, request


@dataclass
class AITextBlock:
    """Single text content block in a model response."""

    text: str


@dataclass
class AIResponse:
    """Normalized AI response payload."""

    content: List[AITextBlock]


class AIClient:
    """Small wrapper for a generic Messages-compatible API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        logger: Any = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or os.getenv("AI_API_KEY")
        self.base_url = (base_url or os.getenv("AI_BASE_URL") or "").rstrip("/")
        self.version = os.getenv("AI_API_VERSION")
        self.version_header = os.getenv("AI_API_VERSION_HEADER")
        self.timeout = timeout
        self.logger = logger

        if self.base_url and self.logger:
            self.logger.info(f"Using AI endpoint: {self.base_url}")

    def create_message(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
    ) -> AIResponse:
        """Send a message request and normalize the response."""
        if not self.api_key:
            raise ValueError("AI_API_KEY environment variable not set")
        if not self.base_url:
            raise ValueError("AI_BASE_URL environment variable not set")
        if not model:
            raise ValueError("AI model is not set")

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if system:
            payload["system"] = system

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.version and self.version_header:
            headers[self.version_header] = self.version

        endpoint = (
            self.base_url
            if self.base_url.endswith("/messages")
            else f"{self.base_url}/messages"
        )
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"AI request failed with status {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"AI request failed: {exc.reason}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid AI response: {raw[:500]}") from exc

        text = self._extract_text(data)
        return AIResponse(content=[AITextBlock(text=text)])

    def _extract_text(self, data: Dict[str, Any]) -> str:
        """Extract plain text from common response shapes."""
        content = data.get("content")
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return "\n".join(parts).strip()

        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            choice = choices[0]
            if isinstance(choice, dict):
                message = choice.get("message", {})
                if isinstance(message, dict):
                    content_text = message.get("content")
                    if isinstance(content_text, str) and content_text.strip():
                        return content_text.strip()

        output = data.get("output")
        if isinstance(output, list):
            parts = []
            for item in output:
                if not isinstance(item, dict):
                    continue
                for block in item.get("content", []):
                    if isinstance(block, dict) and isinstance(block.get("text"), str):
                        parts.append(block["text"])
            if parts:
                return "\n".join(parts).strip()

        raise RuntimeError(f"Unsupported AI response shape: {json.dumps(data)[:500]}")
