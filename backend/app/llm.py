"""The only module that talks to an LLM.

Provider is chosen by LLM_PROVIDER in backend/.env:
  openai_compatible  local Ollama, or any OpenAI-compatible server (POST {OPENAI_COMPAT_BASE}/chat/completions)
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


class LLMBadJSON(LLMError):
    """The LLM answered, but not with valid JSON, even after one stricter retry."""


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


def is_local(base: str) -> bool:
    """True when the server runs on this machine (Ollama), not a remote OpenAI-compatible host."""
    host = httpx.URL(base).host if base else ""
    return host in ("localhost", "127.0.0.1", "::1")


def max_context_blocks() -> int:
    """Blocks sent to the LLM per answer: 8 for a local model so generation stays fast, else 12."""
    cfg = config()
    return 8 if cfg.provider == "openai_compatible" and is_local(cfg.openai_base) else 12


# Reasoning that some local models write into the reply itself, before the JSON.
THINKING = re.compile(
    r"<(think|thinking|reasoning)>.*?</\1>|<\|channel\|?>thought.*?<\|?channel\|>|<\|?think\|?>.*?<\|?/?think\|?>",
    re.DOTALL | re.IGNORECASE,
)


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model text, tolerating thinking, code fences, and stray prose."""
    cleaned = THINKING.sub("", text).strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        cleaned = _escape_stray_quotes(cleaned)
        start = cleaned.find("{")
        if start == -1:
            raise
        # The first complete object; prose after it is ignored.
        value, end = json.JSONDecoder().raw_decode(cleaned, start)
        rest = cleaned[end:].strip()
        if rest.startswith(","):
            # Small local models close the object early and add keys after it:
            # {"status": ..., "reason": "..."},\n"suggestion": {...}  → move the brace to the end.
            try:
                value = json.loads(cleaned[start : end - 1] + rest + "}")
            except json.JSONDecodeError:
                pass
    if not isinstance(value, dict):
        raise json.JSONDecodeError("Expected a JSON object", cleaned, 0)
    return value


def _escape_stray_quotes(text: str) -> str:
    """Escape quotes a model copied into a string unescaped (… INPUT TAX." is stamped …).

    Without JSON mode, small models do this when quoting documents, whose quotes are often
    mismatched (“Invoice", “Cash Invoice"). The parse error ("Expecting ',' delimiter",
    "Expecting property name", ...) sits just after such a quote, so escape the last quote
    before it and try again (at most 20 times). A cut-off reply is left alone.
    """
    for _ in range(20):
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError as e:
            if not e.msg.startswith("Expecting") or e.pos >= len(text.rstrip()) - 1:
                return text
            quote = text.rfind('"', 0, e.pos)
            if quote <= 0 or text[quote - 1] == "\\":
                return text
            text = f'{text[:quote]}\\"{text[quote + 1:]}'
    return text


_json_mode_unsupported: set[str] = set()  # local models that refused response_format


def _call_openai_compatible(cfg: Config, system: str, user: str, max_tokens: int) -> str:
    body: dict[str, Any] = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    # The organizers' server (Claude Haiku behind Open WebUI) rejected `temperature` and
    # non-strict response formats, so remote servers get neither: JSON is enforced by the
    # prompt plus parse_json_object() and one retry. Local Ollama accepts both, and
    # reasoning_effort "none" turns off thinking so it can't eat the token budget.
    local = is_local(cfg.openai_base)
    if local:
        body.update(temperature=0, reasoning_effort=os.getenv("LLM_REASONING_EFFORT", "none").strip() or "none")
        if cfg.model not in _json_mode_unsupported:
            body["response_format"] = {"type": "json_object"}
    res = _post_chat(cfg, body)
    if local and "response_format" in body and res.status_code >= 400 and "structured output" in res.text:
        # Some Ollama models (gemma4 as of 0.40) have no JSON mode: remember, and ask without it.
        _json_mode_unsupported.add(cfg.model)
        del body["response_format"]
        res = _post_chat(cfg, body)

    if res.status_code in (401, 403):
        raise LLMError(f"LLM server rejected the key (HTTP {res.status_code})")
    if res.status_code >= 400:
        raise LLMError(f"LLM server error (HTTP {res.status_code}): {res.text[:200]}")
    try:
        content = res.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        raise LLMError("LLM server returned an unexpected response shape") from e
    return content or ""


def _post_chat(cfg: Config, body: dict[str, Any]) -> httpx.Response:
    try:
        return httpx.post(
            f"{cfg.openai_base}/chat/completions",
            headers={"Authorization": f"Bearer {cfg.openai_key}"},
            json=body,
            timeout=cfg.timeout,
        )
    except httpx.TimeoutException as e:
        raise LLMError(f"LLM server timed out after {cfg.timeout:.0f}s") from e
    except httpx.HTTPError as e:
        raise LLMError(f"Could not reach the LLM server ({type(e).__name__})") from e


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
        raise LLMBadJSON("LLM did not return valid JSON after a retry") from e


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


# Embeddings: any OpenAI-compatible /embeddings endpoint (local Ollama with embeddinggemma).

EMBED_BATCH = 32
EMBED_RETRY_AFTER_SECONDS = 60.0
_embed_down_until = 0.0  # after a failure, skip embeddings briefly so asks stay fast


@dataclass(frozen=True)
class EmbedConfig:
    base: str
    key: str
    model: str
    dimensions: int
    timeout: float


def embed_config() -> EmbedConfig:
    try:
        dims = int(os.getenv("EMBED_DIMENSIONS", "512"))
    except ValueError:
        dims = 512
    try:
        timeout = float(os.getenv("EMBED_TIMEOUT_SECONDS", "3"))
    except ValueError:
        timeout = 3.0
    return EmbedConfig(
        base=os.getenv("EMBED_BASE", "").strip().rstrip("/"),
        key=os.getenv("EMBED_KEY", "").strip(),
        model=os.getenv("EMBED_MODEL", "").strip(),
        dimensions=dims,
        timeout=timeout,
    )


def embeddings_enabled() -> bool:
    """Off with LLM_PROVIDER=none (zero outbound calls) or when EMBED_BASE/EMBED_MODEL are unset."""
    cfg = embed_config()
    return config().provider != "none" and bool(cfg.base and cfg.model)


def embed(texts: list[str]) -> list[list[float]]:
    """One vector per text, in order. Raises LLMUnavailable or LLMError; callers fall back to BM25."""
    global _embed_down_until
    if not embeddings_enabled():
        raise LLMUnavailable("Embeddings are off (LLM_PROVIDER=none or EMBED_* not set)")
    if time.monotonic() < _embed_down_until:
        raise LLMError("Embedding server failed recently; using BM25 for a minute")
    try:
        return _embed(texts)
    except LLMError:
        _embed_down_until = time.monotonic() + EMBED_RETRY_AFTER_SECONDS
        raise


def _embed(texts: list[str]) -> list[list[float]]:
    cfg = embed_config()
    headers = {"Authorization": f"Bearer {cfg.key}"} if cfg.key else {}
    vectors: list[list[float]] = []
    for start in range(0, len(texts), EMBED_BATCH):
        batch = texts[start : start + EMBED_BATCH]
        try:
            res = httpx.post(
                f"{cfg.base}/embeddings",
                headers=headers,
                json={"model": cfg.model, "input": batch, "dimensions": cfg.dimensions},
                timeout=cfg.timeout,
            )
        except httpx.TimeoutException as e:
            raise LLMError(f"Embedding server timed out after {cfg.timeout:.0f}s") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Could not reach the embedding server ({type(e).__name__})") from e
        if res.status_code >= 400:
            raise LLMError(f"Embedding server error (HTTP {res.status_code})")
        try:
            data = sorted(res.json()["data"], key=lambda d: d.get("index", 0))
            batch_vectors = [list(map(float, d["embedding"])) for d in data]
        except (ValueError, KeyError, TypeError) as e:
            raise LLMError("Embedding server returned an unexpected response shape") from e
        if len(batch_vectors) != len(batch):
            raise LLMError("Embedding server returned the wrong number of vectors")
        vectors.extend(batch_vectors)
    return vectors


_embed_health_cache: tuple[float, dict[str, Any]] | None = None


def embed_health(force: bool = False) -> dict[str, Any]:
    """{"ok", "model", "dimensions", "latency_ms", "error"?} from one tiny call, cached for a minute."""
    global _embed_health_cache
    now = time.monotonic()
    if not force and _embed_health_cache and now - _embed_health_cache[0] < _HEALTH_TTL_SECONDS:
        return _embed_health_cache[1]
    cfg = embed_config()
    result: dict[str, Any] = {"ok": False, "model": cfg.model or None, "dimensions": None, "latency_ms": None}
    if not embeddings_enabled():
        result["error"] = "off (LLM_PROVIDER=none or EMBED_* not set); search uses BM25 only"
    else:
        started = time.perf_counter()
        try:
            dims = len(embed(["ping"])[0])
            result.update(ok=dims == cfg.dimensions, dimensions=dims)
            if dims != cfg.dimensions:
                result["error"] = f"expected {cfg.dimensions} dimensions, got {dims}"
        except LLMError as e:
            result["error"] = str(e)
        result["latency_ms"] = round((time.perf_counter() - started) * 1000)
    _embed_health_cache = (now, result)
    return result
