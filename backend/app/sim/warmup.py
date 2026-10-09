"""Pre-compute the demo path at server start, so the first visit after a cold start (e.g. Render's
free plan waking up) is as fast as every later one. Fills the engine's per-channel memo and the
robustness results; no AI calls."""
from __future__ import annotations

import logging
import time

from . import fixgrid, sensitivity, world
from .compare import compare

log = logging.getLogger("nas.warmup")


def warm() -> dict:
    t0 = time.perf_counter()
    base = world.scenario_policy("baseline")
    demo = world.scenario_policy(world.demo_scenario_id())
    for sid in world.scenarios():
        compare(base, world.scenario_policy(sid))
    top = fixgrid.build(demo)[:3]
    results = {"ranking_only": sensitivity.check(base, demo, None)}
    if top:
        results["top_fix"] = sensitivity.check(base, demo, top[0]["policy"])
    secs = round(time.perf_counter() - t0, 1)
    log.info("warm-up done in %.1fs", secs)
    return {"seconds": secs, "base": base, "demo": demo, "top": top, "sensitivity": results}
