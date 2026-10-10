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
TRAVEL = "everyday_travel"
TRAVEL_PENDING = "travel cache not warmed yet"
REQUESTS = json.loads((SCENARIOS_DIR / "demo_requests.json").read_text(encoding="utf-8"))
HEROES = json.loads((SCENARIOS_DIR / "heroes.json").read_text(encoding="utf-8"))
DEMO = HEROES["scenario"]

# Every request in demo_requests.json was warmed on 2026-10-10; a miss here is a real regression (a cache-key change or
# a deleted entry), so there is no xfail for requests any more.
# Hero voices not cached yet: (citizen, policy label). Only Amina after the AI fix is pending (Gemini voice models were out).
PENDING_VOICES = {("c_0020", "ai_fix")}


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
    expected = world.scenario_policy(d["expected"])
    assert canonical(r.policy) == canonical(expected)
    # The /fixes and voice cache keys keep list order (policy_json), so the parse must match the preset byte for byte,
    # or the cached AI fix would miss on stage right after the parse is applied.
    assert r.policy.model_dump(mode="json") == expected.model_dump(mode="json")


def _request_params():
    for x in REQUESTS["requests"]:
        # everyday_travel requests were added 2026-10-10 and are warmed later (quota): pending, not a regression.
        marks = [pytest.mark.xfail(strict=False, reason=TRAVEL_PENDING)] if x.get("service") == TRAVEL else []
        yield pytest.param(x, marks=marks, id=f"{x['apply_to']}:{x['text'][:40]}")


@pytest.mark.parametrize("x", list(_request_params()))
def test_rehearsed_request_hits(x):
    r = tasks.parse_policy(x["text"], world.scenario_policy(x["apply_to"]))
    assert r.source == "ai", f"cache miss for {x['text']!r} on {x['apply_to']}: re-run scripts.warm_cache --parse-only"
    assert r.status == x["expect"]


def test_ui_example_chips_are_cached_from_every_preset():
    """The four example chips in the policy box (i18n example_1..4, ar + en) can be clicked from any preset."""
    chips = ["خلّوا الكاونترات تسكر الساعة 1 الظهر، وما حدا يراجع المكتب إلا بموعد مسبق أونلاين", "اسكروا المكاتب يوم الخميس",
             "خلّوها مجانية لكبار السن", "ضيفوا وحدة متنقلة في ماركا يوم السبت",
             "Close the counters at 1 PM and require an online appointment for office visits", "Close all offices on Thursdays",
             "Make it free for people over 65", "Add a Saturday mobile van in Marka"]
    have = {(x["text"], x["apply_to"]) for x in REQUESTS["requests"]}
    for c in chips:
        for sid in ("baseline", "consolidate", DEMO):
            assert (c, sid) in have, f"chip {c!r} is not rehearsed on {sid}"


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
        for h in [h for h in HEROES["heroes"] if h.get("service", "id_renewal") == "id_renewal"]:
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


@pytest.mark.parametrize("fix", [None, "top_fix", "ai_fix"])
def test_report_from_policies_hits(fix):
    p = _policies()
    r = llm_routes.post_report(ReportRequest(baseline=p["baseline"], scenario=p["demo"], fix=p[fix] if fix else None))
    assert r.source == "ai"


# ------------------------------------------------------------------ everyday_travel (pending: not warmed yet)
# Same checks for the travel demo path (travel_today -> fuel_plus_25_fares). All xfail(strict=False) until
# `python -m scripts.warm_cache --service everyday_travel` has run online; then drop the marks.

travel_pending = pytest.mark.xfail(strict=False, reason=TRAVEL_PENDING)


@functools.lru_cache(maxsize=1)
def _travel_policies() -> dict:
    base = world.scenario_policy(world.baseline_scenario_id(TRAVEL))
    scen = world.scenario_policy(world.demo_scenario_id(TRAVEL))
    return {"baseline": base, "demo": scen, "top_fix": fixgrid.top_fixes(scen)[0].policy,
            "ai_fix": tasks.cached_ai_fix_policy(base, scen)}


@travel_pending
def test_travel_fixes_hit_with_the_ai_proposal_shown():
    p = _travel_policies()
    r = tasks.explain_and_propose_fixes(p["baseline"], p["demo"])
    assert r.source == "ai" and r.ai_proposal["status"] == "shown"


def _travel_voice_params():
    for label in ("baseline", "demo", "top_fix", "ai_fix"):
        for h in [h for h in HEROES["heroes"] if h.get("service") == TRAVEL]:
            yield pytest.param(h["citizen_id"], label, marks=[travel_pending], id=f"travel:{label}:{h['citizen_id']}")


@pytest.mark.parametrize("cid,label", list(_travel_voice_params()))
def test_travel_hero_voice_hits(cid, label):
    pol = _travel_policies()[label]
    assert pol is not None
    v = llm_routes.post_voice(VoiceRequest(citizen_id=cid, policy=pol))
    assert v.source == "ai"


@travel_pending
@pytest.mark.parametrize("fix", [None, "top_fix", "ai_fix"])
def test_travel_report_from_policies_hits(fix):
    p = _travel_policies()
    r = llm_routes.post_report(ReportRequest(baseline=p["baseline"], scenario=p["demo"], fix=p[fix] if fix else None))
    assert r.source == "ai"
