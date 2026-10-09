"""Provider-agnostic LLM client (CLAUDE.md §3). The only module that imports provider SDKs.

complete(task, system, user, json_schema=None, smart=False) -> str

On a rate limit / overload / timeout: back off once, then try LLM_FALLBACK_PROVIDER,
then raise LLMUnavailable so the task can use its non-AI fallback.
"""
from __future__ import annotations

import logging
import time

from .. import config

log = logging.getLogger("nas.llm")

# Records which provider/model answered the most recent call, for cache metadata.
last_meta: dict = {}


class LLMUnavailable(Exception):
    pass


def _models(provider: str) -> tuple[str, str]:
    if provider == "gemini":
        return config.env("MODEL_FAST"), config.env("MODEL_SMART")
    if provider == "groq":
        return config.env("GROQ_MODEL_FAST"), config.env("GROQ_MODEL_SMART")
    if provider == "anthropic":
        return config.env("ANTHROPIC_MODEL_FAST"), config.env("ANTHROPIC_MODEL_SMART")
    return "", ""


# ------------------------------------------------------------------ adapters

def _gemini(model: str, system: str, user: str, want_json: bool) -> str:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.env("GEMINI_API_KEY"),
                          http_options=types.HttpOptions(timeout=int(config.LLM_TIMEOUT_S * 1000)))
    cfg = types.GenerateContentConfig(
        system_instruction=system, temperature=0.4,
        response_mime_type="application/json" if want_json else None,
        thinking_config=types.ThinkingConfig(thinking_level="low"),
    )
    r = client.models.generate_content(model=model, contents=user, config=cfg)
    return r.text or ""


def _groq(model: str, system: str, user: str, want_json: bool) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.env("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1",
                    timeout=config.LLM_TIMEOUT_S, max_retries=0)
    kw = {"response_format": {"type": "json_object"}} if want_json else {}
    r = client.chat.completions.create(model=model, temperature=0.4,
                                       messages=[{"role": "system", "content": system},
                                                 {"role": "user", "content": user}], **kw)
    return r.choices[0].message.content or ""


def _anthropic(model: str, system: str, user: str, want_json: bool) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY"), timeout=config.LLM_TIMEOUT_S, max_retries=0)
    r = client.messages.create(model=model, max_tokens=4000, system=system,
                               messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")


ADAPTERS = {"gemini": _gemini, "groq": _groq, "anthropic": _anthropic}
KEYS = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def _is_transient(e: Exception) -> bool:
    s = f"{type(e).__name__} {e}".lower()
    return any(k in s for k in ("429", "rate", "quota", "resource_exhausted", "503", "unavailable",
                                "overloaded", "500", "502", "504", "timeout", "timed out", "deadline"))


def _providers() -> list[str]:
    out = []
    for p in (config.LLM_PROVIDER, config.LLM_FALLBACK_PROVIDER):
        if p and p in ADAPTERS and p not in out and config.env(KEYS[p]):
            out.append(p)
    return out


def complete(task: str, system: str, user: str, json_schema: dict | None = None, smart: bool = False) -> str:
    """Return the model's text. json_schema (or any truthy value) asks for JSON output."""
    if config.DEMO_OFFLINE:
        raise LLMUnavailable("DEMO_OFFLINE=1")
    want_json = json_schema is not None
    errors = []
    for i, provider in enumerate(_providers()):
        fast, smart_m = _models(provider)
        model = smart_m if smart else fast
        if not model:
            errors.append(f"{provider}: no model configured")
            continue
        attempts = 2 if i == 0 else 1  # back off once on the primary, then move on
        for attempt in range(attempts):
            t0 = time.perf_counter()
            try:
                text = ADAPTERS[provider](model, system, user, want_json)
                last_meta.clear()
                last_meta.update(provider=provider, model=model, seconds=round(time.perf_counter() - t0, 2))
                log.info("llm %s via %s/%s in %.1fs", task, provider, model, last_meta["seconds"])
                return text
            except Exception as e:  # noqa: BLE001 - any provider failure falls through to the next option
                errors.append(f"{provider}/{model}: {type(e).__name__}: {str(e)[:200]}")
                log.warning("llm %s failed on %s: %s", task, provider, errors[-1])
                if attempt + 1 < attempts and _is_transient(e) and "timeout" not in str(e).lower():
                    time.sleep(2.0)
                    continue
                break
    raise LLMUnavailable("; ".join(errors) or "no provider configured")
