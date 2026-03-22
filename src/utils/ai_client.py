"""Generic AI client for Messages-style APIs."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from .env import apply_env_aliases
from .config import get_config


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
        timeout: Optional[int] = None,
    ):
        apply_env_aliases()
        config = get_config()
        self.api_key = api_key or os.getenv("AI_API_KEY")
        self.base_url = (base_url or os.getenv("AI_BASE_URL") or "").rstrip("/")
        self.version = os.getenv("AI_API_VERSION")
        self.version_header = os.getenv("AI_API_VERSION_HEADER")
        self.request_style = (os.getenv("AI_API_STYLE") or "").strip().lower() or None
        configured_timeout = config.get("ai.request_timeout_seconds", 45)
        self.timeout = int(timeout or configured_timeout or 45)
        self.request_retries = max(0, int(config.get("ai.request_retries", 2) or 0))
        self.retry_backoff_seconds = float(config.get("ai.request_retry_backoff_seconds", 1.0) or 1.0)
        self.logger = logger
        self.api_style: Optional[str] = None

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

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.version and self.version_header:
            headers[self.version_header] = self.version

        preferred_style = self._resolve_api_style(model)

        if preferred_style == "messages":
            try:
                data = self._post_messages(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    headers=headers,
                )
                self.api_style = "messages"
            except RuntimeError as exc:
                if not self._should_try_chat_fallback(exc):
                    raise
                data = self._post_chat_completions(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    headers=headers,
                )
                self.api_style = "chat_completions"
                if self.logger:
                    self.logger.info("Falling back to OpenAI-style /chat/completions API")
        elif preferred_style == "chat_completions":
            try:
                data = self._post_chat_completions(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    headers=headers,
                )
                self.api_style = "chat_completions"
            except RuntimeError as exc:
                if not self._should_try_messages_fallback(exc):
                    raise
                data = self._post_messages(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    headers=headers,
                )
                self.api_style = "messages"
                if self.logger:
                    self.logger.info("Falling back to Messages-style /messages API")
        else:
            try:
                data = self._post_messages(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    headers=headers,
                )
                self.api_style = "messages"
            except RuntimeError as exc:
                if not self._should_try_chat_fallback(exc):
                    raise
                data = self._post_chat_completions(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    headers=headers,
                )
                self.api_style = "chat_completions"
                if self.logger:
                    self.logger.info("Falling back to OpenAI-style /chat/completions API")

        text = self._extract_text(data)
        return AIResponse(content=[AITextBlock(text=text)])

    def _resolve_api_style(self, model: str) -> Optional[str]:
        """Choose the most likely API style before the first request."""
        if self.api_style in {"messages", "chat_completions"}:
            return self.api_style

        if self.request_style in {"messages", "chat_completions"}:
            return self.request_style

        model_name = (model or "").strip().lower()
        if model_name.startswith(("gpt-", "o1", "o3", "o4")):
            return "chat_completions"
        if model_name.startswith("claude"):
            return "messages"

        return None

    def _post_messages(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        temperature: Optional[float],
        system: Optional[str],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if system:
            payload["system"] = system

        endpoint = (
            self.base_url
            if self.base_url.endswith("/messages")
            else f"{self.base_url}/messages"
        )
        return self._post_json(endpoint, payload, headers)

    def _post_chat_completions(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        temperature: Optional[float],
        system: Optional[str],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        payload_messages: List[Dict[str, Any]] = []
        if system:
            payload_messages.append({"role": "system", "content": system})

        for message in messages:
            converted = dict(message)
            converted["content"] = self._convert_content_for_chat(message.get("content"))
            payload_messages.append(converted)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": payload_messages,
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        endpoint = (
            self.base_url
            if self.base_url.endswith("/chat/completions")
            else f"{self.base_url}/chat/completions"
        )
        return self._post_json(endpoint, payload, headers)

    def _post_json(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
    ) -> Dict[str, Any]:
        attempts = self.request_retries + 1

        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                if attempt < attempts:
                    self._sleep_before_retry(
                        f"AI request transport failure on attempt {attempt}/{attempts}: {exc}"
                    )
                    continue
                raise RuntimeError(f"AI request failed: {exc}") from exc

            if response.status_code >= 500 and attempt < attempts:
                detail = response.text.strip()
                self._sleep_before_retry(
                    f"AI request server failure on attempt {attempt}/{attempts}: status {response.status_code}: {detail[:240]}"
                )
                continue

            if response.status_code >= 400:
                detail = response.text.strip()
                raise RuntimeError(
                    f"AI request failed with status {response.status_code}: {detail}"
                )

            try:
                return response.json()
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid AI response: {response.text[:500]}") from exc

        raise RuntimeError("AI request failed after retries")

    def _sleep_before_retry(self, message: str) -> None:
        """Log and delay briefly before retrying a transient failure."""
        if self.logger:
            self.logger.warning(message)
        time.sleep(self.retry_backoff_seconds)

    def _convert_content_for_chat(self, content: Any) -> Any:
        """Convert Anthropic-style content blocks to chat.completions format."""
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return content

        converted: List[Dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text")
                if isinstance(text, str):
                    converted.append({"type": "text", "text": text})
            elif block_type == "image":
                source = block.get("source", {})
                media_type = source.get("media_type", "image/png")
                data = source.get("data")
                if isinstance(data, str):
                    converted.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{data}"},
                    })
            elif block_type == "image_url":
                converted.append(block)

        return converted or content

    def _should_try_chat_fallback(self, exc: RuntimeError) -> bool:
        """Decide whether a failed /messages request should try /chat/completions."""
        message = str(exc)
        return any(status in message for status in ("status 400", "status 403", "status 404", "status 405"))

    def _should_try_messages_fallback(self, exc: RuntimeError) -> bool:
        """Decide whether a failed /chat/completions request should try /messages."""
        message = str(exc)
        return any(status in message for status in ("status 400", "status 403", "status 404", "status 405"))

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
                    if isinstance(content_text, list):
                        parts = []
                        for block in content_text:
                            if isinstance(block, dict) and isinstance(block.get("text"), str):
                                parts.append(block["text"])
                        if parts:
                            return "\n".join(parts).strip()

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
