"""Medical exemption (Royal Court, uninsured citizens only): engine, proxy rule, fix grid, robustness, API, data.
Offline, no AI calls."""
import copy
import hashlib
import json
import re
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.data import seed_insurance
from app.main import app
from app.models import HomeVisits, Office, Policy
from app.sim import engine, fixgrid, sensitivity, warmup, world
from app.sim.assumptions import DEFAULT, SENSITIVITY_PARAMS_BY_SERVICE
from app.sim.compare import compare

from .test_engine import person

client = TestClient(app)
SERVICE = "medical_exemption"
TODAY, DEMO = "exemption_today", "exemption_online_only"
MSG = "exemption demo numbers changed: update HANDOFF, re-pick the exemption heroes and re-warm the AI cache"

# sha256 of each service's full engine snapshot (every preset vs its baseline: kpis, by_group, worst groups, flipped
# lists and all outcomes; the demo's whole fix grid with titles; robustness with and without the top fix), taken
# BEFORE the medical-exemption sector (uninsured tag, Royal Court site, engine rules) was added. Neither may move.
SNAPSHOT_SHA256 = {
    "id_renewal": "7aa1e3b4dd8da860756f2b0f65ee70b4ff6c7d724452aa6652c697b508cac457",
    "everyday_travel": "7e32914cdafdfd6143d8922daf75bfd6780eb57e2b2a666785f10c3c1ab4d217",
}


def snapshot(service: str) -> dict:
    base = world.scenario_policy(world.baseline_scenario_id(service))
    snap = {}
    for sid, sc in world.scenarios().items():
        if sc["service"] != service:
            continue
        cr = compare(base, world.scenario_policy(sid))
        snap[sid] = {"kpis": cr.scenario.kpis, "by_group": cr.scenario.by_group, "base_kpis": cr.baseline.kpis,
                     "worst": cr.worst_groups, "worse": cr.flipped_worse, "better": cr.flipped_better,
                     "outcomes": [o.model_dump() for o in cr.scenario.outcomes]}
    demo = world.scenario_policy(world.demo_scenario_id(service))
    b = fixgrid.build(demo)
    snap["fixgrid_demo"] = [(c["id"], c["title_ar"], c["title_en"], c["left_out_drop"], c["hardship_drop"]) for c in b]
    snap["sens"] = sensitivity.check(base, demo, b[0]["policy"]).model_dump()
    snap["sens0"] = sensitivity.check(base, demo, None).model_dump()
    return snap


def uninsured(**kw):
    c = person(**kw)
    c["tags"] = c["tags"] + ["uninsured"]
    c["has_health_insurance"] = False
    return c


def ex_policy(**kw) -> Policy:
    p = dict(service=SERVICE, offices=[], online_enabled=False, fee_jd=0.0, visits_required=2)
    p.update(kw)
    return Policy(**p)


def ex_office(close="15:00", accessible=True, days=("sun", "mon", "tue", "wed", "thu"), site="site_marka"):
    return Office(id="u1", name_ar="د", name_en="U", site_id=site, schedule={d: ("08:00", close) for d in days},
                  wheelchair_accessible=accessible)


def one(c, p):
    return engine.run(p, [c])[0]


# ------------------------------------------------------------------ other services untouched

@pytest.mark.parametrize("service", sorted(SNAPSHOT_SHA256))
def test_other_services_are_byte_identical(service):
    digest = hashlib.sha256(json.dumps(snapshot(service), sort_keys=True).encode()).hexdigest()
    assert digest == SNAPSHOT_SHA256[service]


def test_the_uninsured_tag_is_ignored_by_id_renewal_and_travel():
    pop = copy.deepcopy(world.population())
    for c in pop:
        c["tags"] = [t for t in c["tags"] if t != "uninsured"]
        c.pop("has_health_insurance", None)
    for sid in (world.demo_scenario_id(), world.demo_scenario_id("everyday_travel")):
        p = world.scenario_policy(sid)
        assert engine.run(p, pop) == engine.run(p)


# ------------------------------------------------------------------ eligibility

def test_insured_citizens_are_not_applicable_and_left_out_of_every_percentage():
    pop = world.population()
    res = engine.simulate(world.scenario_policy(DEMO))
    outs = engine.run(world.scenario_policy(DEMO))
    n_unins = sum("uninsured" in c["tags"] for c in pop)
    for c, o in zip(pop, outs):
        if "uninsured" in c["tags"]:
            assert o["channel"] != "not_applicable" and o["eligible"] is True
        else:
            assert o == {**o, "status": "served", "channel": "not_applicable", "mode": None, "cost_jd": 0.0,
                         "hours_lost": 0.0, "travel_minutes": 0.0, "work_hours_missed": 0.0, "reasons": [],
                         "eligible": False}
            assert o["channel_name_en"] == "Insured: no exemption needed"
            assert o["channel_name_ar"] == "مؤمَّن صحياً: لا يحتاج الإعفاء"
    k = res.kpis
    assert k["n_eligible"] == k["n"] == n_unins and k["n_not_applicable"] == len(pop) - n_unins
    assert k["n_served"] + k["n_hardship"] + k["n_left_out"] == n_unins
    assert k["pct_left_out"] == round(100.0 * k["n_left_out"] / n_unins, 1)
    assert res.by_group["all"]["n"] == n_unins
    assert "eligible" not in res.outcomes[0].model_dump()  # internal key, not part of the API contract


def test_id_renewal_and_travel_kpis_have_no_eligibility_keys():
    for sid in ("baseline", "travel_today"):
        k = engine.simulate(world.scenario_policy(sid)).kpis
        assert "n_eligible" not in k and "n_not_applicable" not in k


def test_home_visits_never_go_to_insured_citizens():
    p = world.scenario_policy(TODAY).model_copy(
        update={"home_visits": HomeVisits(groups=["elderly", "disabled", "no_car"], slots=50)})
    pop = world.population()
    outs = engine.run(p)
    got = [c for c, o in zip(pop, outs) if o["channel"] == "home_visit"]
    assert got and all("uninsured" in c["tags"] for c in got)


# ------------------------------------------------------------------ the proxy rule

def test_proxy_lets_the_helper_go_when_the_citizen_cannot():
    c = uninsured(mobility="wheelchair", has_helper=True, helper_relation_ar="ابني", helper_relation_en="my son")
    late = ex_policy(offices=[ex_office(close="19:00", accessible=False)])  # proxy_allowed None = allowed here
    o = one(c, late)
    assert o["status"] == "hardship" and o["mode"] == engine.PROXY_MODE and o["visit_day"] in ("sun", "mon", "tue",
                                                                                           "wed", "thu")
    assert o["work_hours_missed"] == 0.0
    t = o["travel_minutes"]  # the household has no car: the helper takes the bus (the citizen's wheelchair doesn't apply)
    assert o["hours_lost"] == round((2 * t + DEFAULT.EXEMPTION_VISIT_MINUTES) / 60 * 2, 2)
    # Not allowed: the citizen can't get in (office not accessible) -> left out.
    o = one(c, late.model_copy(update={"proxy_allowed": False}))
    assert o["status"] == "left_out" and "NOT_WHEELCHAIR_ACCESSIBLE" in o["reasons"]
    # ID renewal: proxy is off by default.
    o = one(c, late.model_copy(update={"service": "id_renewal"}))
    assert o["status"] == "left_out" and o["mode"] is None


def test_proxy_respects_the_helpers_free_time():
    c = uninsured(mobility="wheelchair", has_helper=True, helper_relation_ar="ابني", helper_relation_en="my son")
    # Weekdays the helper is free only from HELPER_FREE_FROM (16:00): a 15:00 or 18:00 close leaves no 2-hour slot.
    for close in ("15:00", "18:00"):
        assert one(c, ex_policy(offices=[ex_office(close=close, accessible=False)]))["status"] == "left_out"
    # On a Saturday the helper is free all day.
    o = one(c, ex_policy(offices=[ex_office(close="15:00", accessible=False, days=("sat",))]))
    assert o["mode"] == engine.PROXY_MODE and o["visit_day"] == "sat"
    # Without a helper there is no proxy.
    assert one(uninsured(mobility="wheelchair"), ex_policy(offices=[ex_office(close="19:00", accessible=False)])
               )["status"] == "left_out"


def test_proxy_spares_a_worker_the_lost_work_hours():
    # Works until 18:00: going themselves means two visits during work; the helper (free from 16:00) fits before 19:00.
    c = uninsured(works=True, work_start="08:00", work_end="18:00", has_helper=True, helper_relation_ar="أخي",
                  helper_relation_en="my brother", income_band="high")
    p = ex_policy(offices=[ex_office(close="19:00")])
    self_only = one(c, p.model_copy(update={"proxy_allowed": False}))
    with_proxy = one(c, p)
    assert self_only["status"] == "hardship" and self_only["work_hours_missed"] > 0
    assert "HOURS_CONFLICT_WORK" in self_only["reasons"]
    assert with_proxy["status"] == "hardship" and with_proxy["mode"] == engine.PROXY_MODE
    assert with_proxy["work_hours_missed"] == 0.0 and with_proxy["reasons"] == []


def test_resolved_proxy_flag_and_memo_keys():
    p = world.scenario_policy(TODAY)
    assert p.proxy_allowed is None and engine.proxy_allowed(p) is True
    assert engine.proxy_allowed(world.scenario_policy("baseline")) is False
    assert engine.proxy_allowed(world.scenario_policy("exemption_no_proxy")) is False
    engine.run(p)
    keys = list(engine._MEMOS[SERVICE])
    assert keys and all(k[0] == SERVICE and k[1] in (True, False) for k in keys)


# ------------------------------------------------------------------ the visit minutes

def test_exemption_visit_minutes_drive_exemption_outcomes_only():
    a = replace(DEFAULT, EXEMPTION_VISIT_MINUTES=DEFAULT.EXEMPTION_VISIT_MINUTES * 1.2)
    ex = world.scenario_policy(TODAY)
    assert engine.run(ex, None, a) != engine.run(ex)
    ids = world.scenario_policy(world.demo_scenario_id())
    assert engine.run(ids, None, a) == engine.run(ids)
    # Two 120-minute visits are 4 hours at the counter alone: nobody in person is "served" today.
    k = engine.simulate(ex).kpis
    assert k["pct_served"] == 0.0


# ------------------------------------------------------------------ fix grid

def test_fixgrid_candidates_for_today_and_the_demo():
    today = world.scenario_policy(TODAY)
    ids = {s["id"] for s in fixgrid.singles(today)}
    assert {"hybrid", "regional_intake", "late_thu", "van:marka:sat", "van:khalda:thu"} <= ids
    assert "proxy" not in ids  # already allowed by the service default
    assert "proxy" in {s["id"] for s in fixgrid.singles(world.scenario_policy("exemption_no_proxy"))}
    demo = world.scenario_policy(DEMO)
    dids = {s["id"] for s in fixgrid.singles(demo)}
    assert {"hybrid", "regional_intake", "van:wehdat:sat"} <= dids and "late_thu" not in dids
    for scen in (today, demo):
        for c in fixgrid.build(scen):
            assert c["policy"].service == SERVICE
            assert not re.search("[٠-٩]", c["title_ar"])  # Western digits in the new titles
    # Under Sanad-only an intake day lifts online_only but keeps the closed office closed; hybrid reopens it.
    van = next(s for s in fixgrid.singles(demo) if s["id"] == "van:wehdat:sat")["apply"](demo)
    assert not van.online_only and van.online_enabled and van.offices == [] and len(van.mobile_units) == 1
    hyb = next(s for s in fixgrid.singles(demo) if s["id"] == "hybrid")["apply"](demo)
    assert not hyb.online_only and hyb.hybrid_pickup and [o.site_id for o in hyb.offices] == ["royal_court_csu"]
    reg = next(s for s in fixgrid.singles(today) if s["id"] == "regional_intake")["apply"](today)
    assert sorted(o.site_id for o in reg.offices) == sorted(["royal_court_csu"] + [s for s in world.sites()
                                                                                    if s.startswith("cspd_")])
    assert all(o.schedule == today.offices[0].schedule for o in reg.offices)


def test_fix_pairs_are_order_independent_under_online_only():
    demo = world.scenario_policy(DEMO)
    s = {x["id"]: x for x in fixgrid.singles(demo)}
    for a, b in [("hybrid", "van:wehdat:sat"), ("hybrid", "regional_intake"), ("regional_intake", "van:marka:sat")]:
        ab, ba = s[b]["apply"](s[a]["apply"](demo)), s[a]["apply"](s[b]["apply"](demo))
        assert engine.run(ab) == engine.run(ba)


def test_demo_numbers():
    """The rehearsed exemption demo (HANDOFF). If this fails on purpose: update HANDOFF, heroes and the AI cache."""
    cr = compare(world.scenario_policy(TODAY), world.scenario_policy(DEMO))
    k, b = cr.scenario.kpis, cr.baseline.kpis
    assert (b["pct_served"], b["pct_hardship"], b["pct_left_out"]) == (0.0, 74.8, 25.2), MSG
    assert (k["pct_served"], k["pct_hardship"], k["pct_left_out"]) == (77.6, 14.1, 8.4), MSG
    assert k["n_eligible"] == 441 and len(cr.flipped_worse) == 30, MSG
    assert cr.worst_groups[:2] == ["offline", "elderly"], MSG
    top = fixgrid.top_fixes(world.scenario_policy(DEMO))
    assert top[0].id == "pair:regional_intake+van:downtown:sat" and top[0].left_out_drop == 8.2, MSG


# ------------------------------------------------------------------ robustness

def test_robustness_perturbs_the_exemption_params():
    base, demo = world.scenario_policy(TODAY), world.scenario_policy(DEMO)
    fix = fixgrid.top_fixes(demo)[0].policy
    r = sensitivity.check(base, demo, fix)
    params = [d["param"] for d in r.details[1:]]
    assert params == [p for p in SENSITIVITY_PARAMS_BY_SERVICE[SERVICE] for _ in (0, 1)]
    assert "EXEMPTION_VISIT_MINUTES" in params and r.runs == 6
    assert (r.ranking_held, r.fix_still_helps, r.passed) == (6, 6, True), MSG


def test_warm_up_covers_the_exemption_demo():
    w = warmup.warm_exemption()
    assert w["demo"] == world.scenario_policy(DEMO) and w["base"] == world.scenario_policy(TODAY)
    assert w["top"] and {"ranking_only", "top_fix"} <= set(w["sensitivity"])
    assert len(engine._MEMOS[SERVICE]) <= engine._MEMO_MAXES[SERVICE]


# ------------------------------------------------------------------ scenarios and heroes

def test_exemption_presets():
    rows = {s["id"]: s for s in world.scenarios().values() if s["service"] == SERVICE}
    assert set(rows) == {TODAY, DEMO, "exemption_hybrid", "exemption_regional", "exemption_no_proxy"}
    assert world.demo_scenario_id(SERVICE) == DEMO and world.baseline_scenario_id(SERVICE) == TODAY
    for s in rows.values():
        p = Policy.model_validate(s["policy"])
        assert p.service == SERVICE and p.fee_jd == 0 and p.visits_required == 2 and not p.appointment_required
        assert s["order"] >= 20 and s["name_ar"] and s["description_en"]
    assert world.scenario_policy(TODAY).offices[0].site_id == "royal_court_csu"
    assert not world.scenario_policy(TODAY).online_enabled
    site = world.sites()["royal_court_csu"]
    assert site["real"] and site["area"] == "downtown"


def test_exemption_heroes_get_worse_and_recover():
    heroes = client.get("/heroes", params={"service": SERVICE}).json()
    assert len(heroes) == 3 and all(h["service"] == SERVICE and h["note_ar"] and h["note_en"] for h in heroes)
    pop = world.population_by_id()
    base = {o["citizen_id"]: o for o in engine.run(world.scenario_policy(TODAY))}
    demo = {o["citizen_id"]: o for o in engine.run(world.scenario_policy(DEMO))}
    fix = {o["citizen_id"]: o for o in engine.run(fixgrid.top_fixes(world.scenario_policy(DEMO))[0].policy)}
    R = engine.STATUS_RANK
    recovered = 0
    for h in heroes:
        i = h["id"]
        assert "uninsured" in pop[i]["tags"]
        assert R[demo[i]["status"]] > R[base[i]["status"]], MSG
        recovered += R[fix[i]["status"]] <= R[base[i]["status"]]
    assert recovered >= 2, MSG
    assert len(client.get("/heroes").json()) == 4  # the ID-renewal heroes are untouched


# ------------------------------------------------------------------ API

def test_services_endpoint_lists_three():
    rows = {s["id"]: s for s in client.get("/services").json()}
    assert set(rows) == {"id_renewal", "everyday_travel", SERVICE}
    assert rows[SERVICE]["baseline_scenario"] == TODAY and rows[SERVICE]["demo_scenario"] == DEMO


def _p(sid):
    return copy.deepcopy(world.scenarios()[sid]["policy"])


def test_simulate_compare_and_fixgrid_endpoints():
    r = client.post("/simulate", json={"policy": _p(DEMO)})
    assert r.status_code == 200 and r.json()["kpis"]["n_eligible"] == 441
    r = client.post("/compare", json={"baseline": _p(TODAY), "scenario": _p(DEMO)})
    assert r.status_code == 200 and len(r.json()["flipped_worse"]) == 30
    r = client.post("/fixgrid", json={"baseline": _p(TODAY), "scenario": _p(DEMO)})
    assert r.status_code == 200 and len(r.json()["fixes"]) == 3
    assert all(f["policy"]["service"] == SERVICE for f in r.json()["fixes"])


@pytest.mark.parametrize("path", ["/compare", "/fixgrid", "/sensitivity"])
def test_service_mismatch_is_422(path):
    r = client.post(path, json={"baseline": _p("baseline"), "scenario": _p(DEMO)})
    assert r.status_code == 422 and "different services" in r.json()["detail"]


# ------------------------------------------------------------------ data

def test_seed_insurance_is_deterministic_and_matches_the_committed_population():
    committed = world.population()
    stripped = copy.deepcopy(committed)
    for c in stripped:
        c.pop("has_health_insurance")
        c["tags"] = [t for t in c["tags"] if t != "uninsured"]
    a, b = seed_insurance.assign(stripped), seed_insurance.assign(copy.deepcopy(stripped))
    assert a == b == committed
    assert list(committed[0]).index("has_health_insurance") == list(committed[0]).index("tags") + 1
    for c in committed:
        assert ("uninsured" in c["tags"]) == (not c["has_health_insurance"])
        assert c["tags"].count("uninsured") <= 1 and (c["tags"][-1:] == ["uninsured"]) == (not c["has_health_insurance"])


def test_uninsured_share_is_near_the_calibration_target():
    s = seed_insurance.shares(world.population())
    assert 44.0 <= s["all"] <= 48.0
    assert s["low"] > s["middle"] > s["high"]
