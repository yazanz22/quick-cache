"""Pre-compute the demo path at server start, so the first visit after a cold start (e.g. Render's
free plan waking up) is as fast as every later one. Fills the engine's per-channel memo and the
robustness results; no AI calls (the AI fix policy is read from the committed AI cache only).

main.py runs this in a background thread: requests that arrive before it finishes simply compute live.
"""
from __future__ import annotations

import logging
import time

from ..models import Policy
from . import fixgrid, sensitivity, world
from .compare import compare
from .engine import run

log = logging.getLogger("nas.warmup")


def cached_ai_fix(base: Policy, demo: Policy) -> Policy | None:
    """The demo path's verified AI fix, from the AI cache only (never calls a provider). None if unavailable."""
    try:
        from ..llm import tasks
        fn = getattr(tasks, "cached_ai_fix_policy", None)
        return fn(base, demo) if fn else None
    except Exception:  # the warm-up must never fail because of the AI layer
        log.exception("could not read the cached AI fix; skipping it")
        return None


def warm() -> dict:
    """Returns {seconds, base, demo, top, ai_fix, sensitivity: {ranking_only, top_fix?, ai_fix?}}.
    The scenario comparisons run last, so the channels the demo shows first are the most recently used
    entries of the engine's LRU memo (the whole warm-up needs ~115 entries, below engine._MEMO_MAX)."""
    t0 = time.perf_counter()
    base = world.scenario_policy("baseline")
    demo = world.scenario_policy(world.demo_scenario_id())
    top = fixgrid.build(demo)[:3]
    ai_fix = cached_ai_fix(base, demo)
    results = {"ranking_only": sensitivity.check(base, demo, None)}
    if top:  # the badge after "Suggest fixes" and after applying the top fix
        results["top_fix"] = sensitivity.check(base, demo, top[0]["policy"])
    if ai_fix is not None:  # the badge after applying the AI-proposed fix
        results["ai_fix"] = sensitivity.check(base, demo, ai_fix)
        run(ai_fix)  # its "after Apply" compare is then a memo hit
    for sid, sc in world.scenarios().items():
        if sc["service"] == "id_renewal":
            compare(base, world.scenario_policy(sid))
    secs = round(time.perf_counter() - t0, 1)
    log.info("warm-up done in %.1fs (AI fix %s)", secs, "warmed" if ai_fix is not None else "not available")
    return {"seconds": secs, "base": base, "demo": demo, "top": top, "ai_fix": ai_fix, "sensitivity": results}


def warm_service(service: str) -> dict:
    """A non-id_renewal service's demo path: its fix grid, the ranking-only and top-fix robustness checks, and every
    preset of the service compared with its baseline. Same shape as warm() (ai_fix is always None here).
    everyday_travel has its own memo (travel_service) and medical_exemption its own engine memo (engine._MEMOS),
    so this never evicts the ID-renewal entries."""
    t0 = time.perf_counter()
    base = world.scenario_policy(world.baseline_scenario_id(service))
    demo = world.scenario_policy(world.demo_scenario_id(service))
    top = fixgrid.build(demo)[:3]
    results = {"ranking_only": sensitivity.check(base, demo, None)}
    if top:
        results["top_fix"] = sensitivity.check(base, demo, top[0]["policy"])
    for sid, sc in world.scenarios().items():
        if sc["service"] == service:
            compare(base, world.scenario_policy(sid))
    secs = round(time.perf_counter() - t0, 1)
    log.info("%s warm-up done in %.1fs", service, secs)
    return {"seconds": secs, "base": base, "demo": demo, "top": top, "ai_fix": None, "sensitivity": results}


def warm_travel() -> dict:
    """The everyday_travel demo path (warm_service)."""
    return warm_service("everyday_travel")


def warm_exemption() -> dict:
    """The medical_exemption demo path (warm_service)."""
    return warm_service("medical_exemption")
