"""The committed AI cache still answers the demo (offline: conftest sets DEMO_OFFLINE=1, so source "ai" = a hit).

If one of the strict tests fails, a change touched a cache key (voice_facts, the parse inputs, report_summary,
the /fixes inputs, tasks.policy_json) or the scenarios/engine numbers behind it. Entries that were never warmed
are xfail(strict=False), so the suite stays green but the list of pending warm calls stays visible; fill them
with `python -m scripts.warm_cache` (online, after the Gemini quota reset), then commit backend/cache/.
"""
import functools
import json

import pytest

from app.config import SCENARIOS_DIR
from app.llm import tasks
from app.models import ReportRequest, VoiceRequest
from app.routes import llm_routes
from app.sim import fixgrid, sensitivity, world
from app.sim.compare import compare
from app.sim.validate import canonical

PENDING = "needs scripts.warm_cache after the Gemini quota reset"
REQUESTS = json.loads((SCENARIOS_DIR / "demo_requests.json").read_text(encoding="utf-8"))
HEROES = json.loads((SCENARIOS_DIR / "heroes.json").read_text(encoding="utf-8"))
DEMO = HEROES["scenario"]

# Rehearsed requests cached on 2026-10-09 (the rest of demo_requests.json was added later).
CACHED_REQUESTS = {
    ("اسكروا المكاتب يوم الخميس", "baseline"), ("Close all offices on Thursdays", "baseline"),
    ("Close the Marka office", "baseline"), ("Reopen the Marka office", "consolidate"),
    ("Make it online-only but keep a Saturday van in Wehdat", "baseline"), ("Double the fee", "baseline"),
    ("Require two visits", "baseline"), ("Make it free for people over 65", "baseline"),
    ("خلّوها مجانية لكبار السن", "baseline"), ("خلّوا كبار السن وذوي الإعاقة يراجعوا بدون موعد", DEMO),
    ("Home visits for wheelchair users, 30 visits", DEMO), ("ادفعوا أجرة التكسي لذوي الدخل المحدود لحد 3 دنانير", DEMO),
    ("Let people apply online and just pick up the card", "baseline"), ("افتحوا مكتب جديد في ماركا", "consolidate"),
    ("Add more staff at the Marka office", "baseline"), ("سكّروا شارع زهران", "baseline"),
}
# Hero voices not cached yet: (citizen, policy label).
PENDING_VOICES = {("c_0837", "top_fix"), ("c_0020", "top_fix"), ("c_0837", "ai_fix"), ("c_0020", "ai_fix")}


@functools.lru_cache(maxsize=1)
def _policies() -> dict:
    """Read-only: tests must not mutate these."""
    base, scen = world.scenario_policy("baseline"), world.scenario_policy(DEMO)
    return {"baseline": base, "demo": scen, "top_fix": fixgrid.top_fixes(scen)[0].policy,
            "ai_fix": tasks.cached_ai_fix_policy(base, scen)}


def test_stage_sentence_hits_and_equals_the_demo_preset():
    d = REQUESTS["demo"]
    r = tasks.parse_policy(d["text"], world.scenario_policy(d["apply_to"]))
    assert r.source == "ai" and r.status == "ok"
    assert canonical(r.policy) == canonical(world.scenario_policy(d["expected"]))


def _request_params():
    for x in REQUESTS["requests"]:
        marks = [] if (x["text"], x["apply_to"]) in CACHED_REQUESTS else [pytest.mark.xfail(strict=False, reason=PENDING)]
        yield pytest.param(x, marks=marks, id=f"{x['apply_to']}:{x['text'][:40]}")


@pytest.mark.parametrize("x", list(_request_params()))
def test_rehearsed_request_hits(x):
    r = tasks.parse_policy(x["text"], world.scenario_policy(x["apply_to"]))
    assert r.source == "ai" and r.status == x["expect"]


def test_every_baseline_request_is_cached_today():
    assert {(x["text"], x["apply_to"]) for x in REQUESTS["requests"] if x["apply_to"] == "baseline"} <= CACHED_REQUESTS


def test_demo_fixes_hit_with_the_ai_proposal_shown():
    r = tasks.explain_and_propose_fixes(world.scenario_policy("baseline"), world.scenario_policy(DEMO))
    assert r.source == "ai" and r.ai_proposal["status"] == "shown"
    ai = [f for f in r.fixes if f.source == "ai_proposed"]
    assert len(ai) == 1 and ai[0].n_changes <= tasks.MAX_AI_CHANGES and ai[0].kpis


def test_cached_ai_fix_policy_reads_the_cache_only():
    p = _policies()["ai_fix"]
    assert p is not None
    assert sorted((m.area, m.day) for m in p.mobile_units) == [("downtown", "sat"), ("sweileh", "sat"), ("wehdat", "sat")]


def _voice_params():
    for label in ("baseline", "demo", "top_fix", "ai_fix"):
        for h in HEROES["heroes"]:
            cid = h["citizen_id"]
            marks = [pytest.mark.xfail(strict=False, reason=PENDING)] if (cid, label) in PENDING_VOICES else []
            yield pytest.param(cid, label, marks=marks, id=f"{label}:{cid}")


@pytest.mark.parametrize("cid,label", list(_voice_params()))
def test_hero_voice_hits(cid, label):
    pol = _policies()[label]
    assert pol is not None
    v = llm_routes.post_voice(VoiceRequest(citizen_id=cid, policy=pol))
    assert v.source == "ai"


def test_report_with_top_fix_robustness_hits():
    """The report as older clients send it: compare_result + the top-fix robustness result."""
    p = _policies()
    r = tasks.write_report(compare(p["baseline"], p["demo"]), sensitivity.check(p["baseline"], p["demo"], p["top_fix"]))
    assert r.source == "ai"


@pytest.mark.xfail(strict=False, reason=PENDING)
@pytest.mark.parametrize("fix", [None, "top_fix", "ai_fix"])
def test_report_from_policies_hits(fix):
    p = _policies()
    r = llm_routes.post_report(ReportRequest(baseline=p["baseline"], scenario=p["demo"], fix=p[fix] if fix else None))
    assert r.source == "ai"
