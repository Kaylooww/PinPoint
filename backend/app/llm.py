"""The only module that talks to an LLM.

Provider is chosen by LLM_PROVIDER in backend/.env:
  openai_compatible  the organizers' server (POST {OPENAI_COMPAT_BASE}/chat/completions)
  anthropic          Claude via the official Anthropic SDK (fallback)
  none               no LLM; callers fall back to extractive mode

Everything else in the app calls chat_json() and health(). Never log API keys.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROVIDERS = ("openai_compatible", "anthropic", "none")
JSON_INSTRUCTION = "Return only valid JSON."
STRICT_JSON_INSTRUCTION = (
    "Your previous reply was not valid JSON. Return ONLY a single JSON object: "
    "no prose, no markdown, no code fences."
)


class LLMError(Exception):
    """The LLM call failed. The message is safe to show and never contains keys."""


class LLMUnavailable(LLMError):
    """No LLM is configured (LLM_PROVIDER=none or missing settings)."""


@dataclass(frozen=True)
class Config:
    provider: str
    model: str
    timeout: float
    openai_base: str
    openai_key: str
    anthropic_key: str


def config() -> Config:
    provider = os.getenv("LLM_PROVIDER", "none").strip().lower() or "none"
    if provider not in PROVIDERS:
        provider = "none"
    if provider == "anthropic":
        model = os.getenv("ANTHROPIC_MODEL", "").strip() or "claude-haiku-5-5"
    elif provider == "openai_compatible":
        model = os.getenv("OPENAI_COMPAT_MODEL", "").strip()
    else:
        model = ""
    try:
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
    except ValueError:
        timeout = 45.0
    return Config(
        provider=provider,
        model=model,
        timeout=timeout,
        openai_base=os.getenv("OPENAI_COMPAT_BASE", "").strip().rstrip("/"),
        openai_key=os.getenv("OPENAI_COMPAT_KEY", "").strip(),
        anthropic_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
    )


def missing_settings(cfg: Config) -> list[str]:
    """Names of required settings that are empty for the chosen provider."""
    if cfg.provider == "anthropic":
        return [] if cfg.anthropic_key else ["ANTHROPIC_API_KEY"]
    if cfg.provider == "openai_compatible":
        required = {
            "OPENAI_COMPAT_BASE": cfg.openai_base,
            "OPENAI_COMPAT_KEY": cfg.openai_key,
            "OPENAI_COMPAT_MODEL": cfg.model,
        }
        return [name for name, value in required.items() if not value]
    return []


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model text, tolerating code fences and stray prose."""
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise json.JSONDecodeError("Expected a JSON object", cleaned, 0)
    return value


def _call_openai_compatible(cfg: Config, system: str, user: str, max_tokens: int) -> str:
    try:
        res = httpx.post(
            f"{cfg.openai_base}/chat/completions",
            headers={"Authorization": f"Bearer {cfg.openai_key}"},
            json={
                "model": cfg.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.1,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=cfg.timeout,
        )
    except httpx.TimeoutException as e:
        raise LLMError(f"LLM server timed out after {cfg.timeout:.0f}s") from e
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the LLM server ({type(e).__name__})") from e

    if res.status_code in (401, 403):
        raise LLMError(f"LLM server rejected the key (HTTP {res.status_code})")
    if res.status_code >= 400:
        raise LLMError(f"LLM server error (HTTP {res.status_code}): {res.text[:200]}")
    try:
        content = res.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LLMError("LLM server returned an unexpected response shape") from e
    return content or ""


def _call_anthropic(cfg: Config, system: str, user: str, max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.anthropic_key, timeout=cfg.timeout, max_retries=1)
    try:
        response = client.messages.create(
            model=cfg.model,
            max_tokens=max_tokens,
            system=system,
            # Short JSON replies: keep thinking off so it can't eat the token budget.
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError as e:
        raise LLMError("Anthropic rejected ANTHROPIC_API_KEY") from e
    except anthropic.NotFoundError as e:
        raise LLMError(f"Anthropic model not found: {cfg.model}") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Anthropic rate limit reached") from e
    except anthropic.APITimeoutError as e:
        raise LLMError(f"Anthropic timed out after {cfg.timeout:.0f}s") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic error (HTTP {e.status_code})") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the Anthropic API") from e

    if response.stop_reason == "refusal":
        raise LLMError("Anthropic declined the request")
    return "".join(block.text for block in response.content if block.type == "text")


def chat_json(system: str, user: str, max_tokens: int = 500) -> dict[str, Any]:
    """Send one system+user turn and return the reply parsed as a JSON object.

    Retries once with a stricter instruction if the reply isn't valid JSON.
    Raises LLMUnavailable when no provider is configured, LLMError otherwise.
    """
    cfg = config()
    if cfg.provider == "none":
        raise LLMUnavailable("LLM_PROVIDER is none (extractive mode)")
    missing = missing_settings(cfg)
    if missing:
        raise LLMUnavailable(f"Missing settings in backend/.env: {', '.join(missing)}")

    call = _call_anthropic if cfg.provider == "anthropic" else _call_openai_compatible
    prompt = f"{system}\n\n{JSON_INSTRUCTION}"
    text = call(cfg, prompt, user, max_tokens)
    try:
        return parse_json_object(text)
    except json.JSONDecodeError:
        pass
    text = call(cfg, f"{prompt}\n\n{STRICT_JSON_INSTRUCTION}", user, max_tokens)
    try:
        return parse_json_object(text)
    except json.JSONDecodeError as e:
        raise LLMError("LLM did not return valid JSON after a retry") from e


_HEALTH_TTL_SECONDS = 60.0
_health_cache: tuple[float, dict[str, Any]] | None = None


def health(force: bool = False) -> dict[str, Any]:
    """{"ok", "provider", "model", "latency_ms", "mode", "error"?} from one tiny live call.

    Cached for a minute so /api/health can be polled without spending tokens.
    """
    global _health_cache
    now = time.monotonic()
    if not force and _health_cache and now - _health_cache[0] < _HEALTH_TTL_SECONDS:
        return _health_cache[1]

    cfg = config()
    result: dict[str, Any] = {
        "ok": False,
        "provider": cfg.provider,
        "model": cfg.model or None,
        "latency_ms": None,
        "mode": "generate",
    }
    if cfg.provider == "none":
        result.update(ok=True, mode="extractive")
    elif missing := missing_settings(cfg):
        result.update(mode="extractive", error=f"Missing settings in backend/.env: {', '.join(missing)}")
    else:
        started = time.perf_counter()
        try:
            chat_json('Reply with {"ok": true}.', "ping", max_tokens=20)
            result["ok"] = True
        except LLMError as e:
            result.update(mode="extractive", error=str(e))
        result["latency_ms"] = round((time.perf_counter() - started) * 1000)

    _health_cache = (now, result)
    return result
