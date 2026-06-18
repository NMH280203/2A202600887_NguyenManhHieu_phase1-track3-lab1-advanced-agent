from __future__ import annotations
import json
import os
import re
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_JSON_RETRY_HINT = "\n\nRespond with valid JSON only. No markdown, no extra text."
DEFAULT_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "90"))
DEFAULT_MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "256"))


def is_mock_mode() -> bool:
    return os.getenv("MOCK_MODE", "").lower() in {"1", "true", "yes"}


def is_ollama_backend() -> bool:
    if os.getenv("OLLAMA", "").lower() in {"1", "true", "yes"}:
        return True
    base = os.getenv("OPENAI_BASE_URL", "").lower()
    return "11434" in base or "ollama" in base


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json_response(text: str) -> dict[str, Any]:
    text = _strip_markdown_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Could not parse JSON from model response: {text[:300]}") from None


def _resolve_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key
    if is_ollama_backend():
        return "ollama"
    raise RuntimeError(
        "OPENAI_API_KEY is not set. For Ollama, set OLLAMA=1 or OPENAI_BASE_URL=http://localhost:11434/v1. "
        "Or run with MOCK_MODE=1 for deterministic mock runtime."
    )


def _build_client():
    from openai import OpenAI

    return OpenAI(
        api_key=_resolve_api_key(),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
        timeout=DEFAULT_TIMEOUT_S,
    )


def _create_completion(
    client: Any,
    *,
    model: str,
    system: str,
    user: str,
    json_mode: bool,
    max_output_tokens: int,
) -> Any:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_output_tokens,
    }

    use_native_json = json_mode and not is_ollama_backend()
    if use_native_json:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        return client.chat.completions.create(**kwargs)
    except Exception as first_error:
        if not json_mode:
            raise

        retry_messages = [
            {"role": "system", "content": system + _JSON_RETRY_HINT},
            {"role": "user", "content": user},
        ]
        try:
            return client.chat.completions.create(
                model=model,
                messages=retry_messages,
                temperature=0,
                max_tokens=max_output_tokens,
            )
        except Exception:
            raise first_error from None


def chat_completion(
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    max_output_tokens: int | None = None,
) -> tuple[str, int, int]:
    if is_mock_mode():
        return "", 0, 0

    client = _build_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    max_tokens = max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS

    start = time.perf_counter()
    response = _create_completion(
        client,
        model=model,
        system=system,
        user=user,
        json_mode=json_mode,
        max_output_tokens=max_tokens,
    )
    latency_ms = int((time.perf_counter() - start) * 1000)
    message = response.choices[0].message.content or ""
    usage = response.usage
    tokens = usage.total_tokens if usage else _estimate_tokens(system + user + message)
    return message, tokens, latency_ms


def chat_json(
    system: str,
    user: str,
    *,
    max_output_tokens: int | None = None,
) -> tuple[dict[str, Any], int, int]:
    text, tokens, latency_ms = chat_completion(
        system,
        user,
        json_mode=True,
        max_output_tokens=max_output_tokens,
    )
    return _parse_json_response(text), tokens, latency_ms
