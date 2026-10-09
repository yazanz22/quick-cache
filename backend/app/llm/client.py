"""Provider-agnostic LLM client (CLAUDE.md §3). The only module that imports provider SDKs.

complete(task, system, user, json_schema=None, smart=False) -> str

The whole chain shares LLM_TOTAL_BUDGET_S (default 17 s), so an answer, or the task's template,
always arrives before the frontend's 20 s request timeout.

Free tiers limit requests PER MODEL (e.g. 20/day for a Gemini Flash model), so each slot is a
comma-separated CHAIN of models in .env (MODEL_FAST, MODEL_SMART, GROQ_MODEL_FAST, GROQ_MODEL_SMART).
A call tries the primary provider's chain, then LLM_FALLBACK_PROVIDER's chain, then raises
LLMUnavailable so the task uses its non-AI fallback. A model that hits a limit is put on cooldown
(daily limit: until the next reset; per-minute limit or overload: a short pause) and skipped, so an
exhausted model never costs a wasted request.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from .. import config

log = logging.getLogger("nas.llm")

# Records which provider/model answered the most recent call, for cache metadata.
last_meta: dict = {}
# (provider, model) -> unix time until which the model is skipped, and why.
_cooldown: dict[tuple[str, str], tuple[float, str]] = {}
# (provider, model) -> successful calls since the server started (shown by GET /llm/status).
_calls: dict[tuple[str, str], int] = {}

SHORT_COOLDOWN_S = 65.0   # per-minute limits reset within a minute
OVERLOAD_COOLDOWN_S = 30.0


class LLMUnavailable(Exception):
    pass


def _chain(provider: str, smart: bool) -> list[str]:
    prefix = {"gemini": "", "groq": "GROQ_", "openai": "OPENAI_", "anthropic": "ANTHROPIC_"}.get(provider)
    if prefix is None:
        return []
    raw = config.env(f"{prefix}MODEL_{'SMART' if smart else 'FAST'}")
    return [m.strip() for m in raw.split(",") if m.strip()]


# ------------------------------------------------------------------ adapters

def _gemini(model: str, system: str, user: str, want_json: bool, timeout: float) -> str:
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=config.env("GEMINI_API_KEY"), http_options=types.HttpOptions(timeout=int(timeout * 1000)))
    kw = {"thinking_config": types.ThinkingConfig(thinking_level="low")} if "lite" not in model else {}
    cfg = types.GenerateContentConfig(system_instruction=system, temperature=0.4,
                                      response_mime_type="application/json" if want_json else None, **kw)
    r = client.models.generate_content(model=model, contents=user, config=cfg)
    return r.text or ""


def _groq(model: str, system: str, user: str, want_json: bool, timeout: float) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.env("GROQ_API_KEY"), base_url="https://api.groq.com/openai/v1",
                    timeout=timeout, max_retries=0)
    kw = {"response_format": {"type": "json_object"}} if want_json else {}
    r = client.chat.completions.create(model=model, temperature=0.4,
                                       messages=[{"role": "system", "content": system},
                                                 {"role": "user", "content": user}], **kw)
    return r.choices[0].message.content or ""


def _openai(model: str, system: str, user: str, want_json: bool, timeout: float) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=config.env("OPENAI_API_KEY"), timeout=timeout, max_retries=0)
    kw = {"response_format": {"type": "json_object"}} if want_json else {}
    # No temperature: some current OpenAI models only accept the default.
    r = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system},
                                                              {"role": "user", "content": user}], **kw)
    return r.choices[0].message.content or ""


def _anthropic(model: str, system: str, user: str, want_json: bool, timeout: float) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY"), timeout=timeout, max_retries=0)
    r = client.messages.create(model=model, max_tokens=4000, system=system,
                               messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")


ADAPTERS = {"gemini": _gemini, "groq": _groq, "openai": _openai, "anthropic": _anthropic}
KEYS = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def _next_daily_reset() -> float:
    """Gemini's daily quota resets at midnight Pacific time (~UTC-7/-8); use 08:00 UTC to be safe."""
    now = datetime.now(timezone.utc)
    reset = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if reset <= now:
        reset += timedelta(days=1)
    return reset.timestamp()


def _classify(e: Exception) -> tuple[float, str] | None:
    """Cooldown for a failed call, or None if the error isn't about limits/availability."""
    s = f"{type(e).__name__} {e}".lower()
    if "perday" in s or "per day" in s or "requests per day" in s or "rpd" in s:
        return _next_daily_reset(), "daily limit"
    if "insufficient_quota" in s or "no credits" in s:  # (Gemini's daily-limit text also mentions "billing")
        return _next_daily_reset(), "no credits"
    if any(k in s for k in ("429", "rate limit", "rate_limit", "resource_exhausted", "quota", "tokens per minute")):
        return time.time() + SHORT_COOLDOWN_S, "rate limit"
    if any(k in s for k in ("503", "unavailable", "overloaded", "high demand", "500", "502", "504")):
        return time.time() + OVERLOAD_COOLDOWN_S, "overloaded"
    if any(k in s for k in ("timeout", "timed out", "deadline")):
        return time.time() + OVERLOAD_COOLDOWN_S, "timeout"
    return None


def _providers() -> list[str]:
    """Primary provider, then each fallback in order (LLM_FALLBACK_PROVIDER may list several: "groq,openai").
    Providers without a key are skipped."""
    out = []
    for p in [config.LLM_PROVIDER] + [x.strip() for x in config.LLM_FALLBACK_PROVIDER.split(",")]:
        if p and p in ADAPTERS and p not in out and config.env(KEYS[p]):
            out.append(p)
    return out


def complete(task: str, system: str, user: str, json_schema: dict | None = None, smart: bool = False,
             budget_s: float | None = None) -> str:
    """Return the model's text. json_schema (or any non-None value) asks for JSON output.
    budget_s overrides LLM_TOTAL_BUDGET_S (used when a task retries within one request)."""
    if config.DEMO_OFFLINE:
        raise LLMUnavailable("DEMO_OFFLINE=1")
    want_json = json_schema is not None
    errors = []
    deadline = time.monotonic() + (config.LLM_TOTAL_BUDGET_S if budget_s is None else budget_s)
    for provider in _providers():
        for model in _chain(provider, smart):
            until, why = _cooldown.get((provider, model), (0.0, ""))
            if until > time.time():
                errors.append(f"{provider}/{model}: skipped ({why})")
                continue
            left = deadline - time.monotonic()
            if left < 2.0:  # not worth starting another call; the task's template answers instead
                errors.append("time budget used up")
                raise LLMUnavailable("; ".join(errors))
            t0 = time.perf_counter()
            try:
                text = ADAPTERS[provider](model, system, user, want_json, min(config.LLM_TIMEOUT_S, left))
            except Exception as e:  # noqa: BLE001 - any failure moves on to the next model
                cd = _classify(e)
                if cd:
                    _cooldown[(provider, model)] = cd
                errors.append(f"{provider}/{model}: {type(e).__name__}: {str(e)[:160]}")
                log.warning("llm %s failed on %s/%s (%s)", task, provider, model, cd[1] if cd else type(e).__name__)
                continue
            _calls[(provider, model)] = _calls.get((provider, model), 0) + 1
            last_meta.clear()
            last_meta.update(provider=provider, model=model, seconds=round(time.perf_counter() - t0, 2))
            log.info("llm %s via %s/%s in %.1fs", task, provider, model, last_meta["seconds"])
            return text
    raise LLMUnavailable("; ".join(errors) or "no provider configured")


def status() -> dict:
    """Which models are configured, how often each answered, and which are cooling down."""
    now = time.time()
    out = {"offline": config.DEMO_OFFLINE, "providers": _providers(), "models": []}
    for p in _providers():
        for slot, smart in (("fast", False), ("smart", True)):
            for m in _chain(p, smart):
                until, why = _cooldown.get((p, m), (0.0, ""))
                out["models"].append({
                    "provider": p, "slot": slot, "model": m, "calls_since_start": _calls.get((p, m), 0),
                    "available": until <= now,
                    "cooldown": None if until <= now else {"reason": why, "seconds_left": round(until - now)}})
    return out
