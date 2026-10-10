"""Everyday travel (fuel prices, fares, cash support): engine, fix grid, robustness, API. Offline, no AI calls."""
import copy
import hashlib
import json
import math
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import CashSupport, Policy, TransportVoucher
from app.routes import sim_routes
from app.sim import engine, fixgrid, sensitivity, travel_service, warmup, world
from app.sim.assumptions import DEFAULT, SENSITIVITY_PARAMS_BY_SERVICE
from app.sim.compare import compare, kpi_delta
from app.sim.engine import STATUS_RANK

from .test_engine import person

client = TestClient(app)
SERVICE = "everyday_travel"
TODAY, DEMO = "travel_today", "fuel_plus_25_fares"
MSG = "travel demo numbers changed: update HANDOFF, re-pick the travel heroes and re-warm the AI cache"

# sha256 of the id_renewal snapshot (every id_renewal preset's kpis, worst groups, flipped_worse and outcomes vs
# baseline, plus the demo fix-grid top 5) taken BEFORE the travel service was added. The travel service must not
# move a single id_renewal byte.
ID_RENEWAL_SNAPSHOT_SHA256 = "734299c9ceff65829bdc9cd6be6d5570c66b98dc92b78272700256706833c948"


def travel_policy(**kw) -> Policy:
    p = dict(service=SERVICE, offices=[], online_enabled=True, fee_jd=2.0)
    p.update(kw)
    return Policy(**p)


def commuter(hub="work_marka", days=5, **kw):
    """A synthetic citizen with their own trip, living in the hub's area (0 bus transfers), off the OSRM matrix."""
    h = world.hubs()[hub]
    c = person(area=travel_service.hub_area(h), lat=h["lat"] + 0.02, lng=h["lng"], **kw)
    c["trip"] = {"purpose": "work" if hub.startswith("work") else "university", "hub": hub, "days_per_week": days}
    return c


def one(c, p):
    return engine.run(p, [c])[0]


# ------------------------------------------------------------------ id_renewal untouched

def test_id_renewal_snapshot_is_byte_identical():
    base = world.scenario_policy("baseline")
    snap = {}
    for sid, sc in world.scenarios().items():
        if sc["service"] != "id_renewal":
            continue
        cr = compare(base, world.scenario_policy(sid))
        snap[sid] = {"kpis": cr.scenario.kpis, "worst": cr.worst_groups, "worse": cr.flipped_worse,
                     "outcomes": [o.model_dump() for o in cr.scenario.outcomes]}
    demo = world.scenario_policy("consolidate_digital_first")
    snap["fixgrid_demo"] = [(c["id"], c["left_out_drop"], c["hardship_drop"]) for c in fixgrid.build(demo)[:5]]
    digest = hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest()
    assert digest == ID_RENEWAL_SNAPSHOT_SHA256


def test_travel_levers_are_ignored_by_id_renewal():
    p = world.scenario_policy("consolidate_digital_first")
    q = p.model_copy(update={"fuel_price_change_pct": 50.0, "bus_fare_change_pct": 0.0,
                             "cash_support": [CashSupport(groups=["low_income"], amount_jd_month=20)]})
    assert engine.run(q) == engine.run(p)


# ------------------------------------------------------------------ engine

def test_deterministic_and_fast():
    p = travel_policy(fuel_price_change_pct=37.0)
    t0 = time.perf_counter()
    a = engine.run(p)  # a memo miss: a fuel change no other test uses
    secs = time.perf_counter() - t0
    assert a == engine.run(p) == engine.run(p, copy.deepcopy(world.population()))
    assert secs < 0.05, f"travel run took {secs * 1000:.0f} ms"


def test_outcomes_have_the_contract_fields():
    outs = engine.simulate(world.scenario_policy(DEMO)).outcomes
    assert len(outs) == len(world.population())
    for o in outs:
        assert o.visit_day is None and o.work_hours_missed == 0.0
        if o.purpose is None:
            continue
        assert o.channel.startswith("trip:") and o.mode in travel_service.MODES and o.days_per_week >= 1
        assert o.monthly_cost_before_jd is not None and o.income_share_pct is not None
        assert math.isclose(o.extra_jd_month, o.cost_jd - o.monthly_cost_before_jd, abs_tol=0.011)


def test_status_follows_the_income_share_thresholds_everywhere():
    a = DEFAULT
    pop = world.population()
    for o, c in zip(engine.run(world.scenario_policy(DEMO)), pop):
        share = o["cost_jd"] / a.INCOME_JD_MONTH[c["income_band"]]
        want = ("left_out" if share >= a.TRANSPORT_SHARE_PRICED_OUT
                else "hardship" if share >= a.TRANSPORT_SHARE_SQUEEZED else "served")
        assert o["status"] == want
        assert o["reasons"] == ([] if want == "served" else
                                ["TRANSPORT_OVER_BUDGET", "FUEL_COST" if o["mode"] in ("car", "helper_car") else "FARE_COST"])


def test_thresholds_10_and_20_percent_of_income():
    # Low income (130 JD/month), bus within the area: 2 * 0.45 JD a round trip, 4.33 weeks a month.
    p = travel_policy()
    rt = 2 * DEFAULT.BUS_FARE_JD
    for days, want in [(1, "served"), (3, "served"), (4, "hardship"), (6, "hardship"), (7, "left_out")]:
        o = one(commuter(days=days, income_band="low"), p)
        assert o["mode"] == "bus" and o["bus_transfers"] == 0
        assert o["cost_jd"] == round(rt * days * DEFAULT.WEEKS_PER_MONTH, 2)
        assert o["status"] == want, (days, o["income_share_pct"])
    # Crossing 10% by a fuel rise: 3 days a week is 9.0% today; fares follow fuel by 30%, so +50% fuel = +15% fare.
    c = commuter(days=3, income_band="low")
    assert one(c, p)["status"] == "served"
    hit = one(c, travel_policy(fuel_price_change_pct=50.0))
    assert hit["status"] == "hardship" and hit["reasons"] == ["TRANSPORT_OVER_BUDGET", "FARE_COST"]


def test_car_cost_rises_with_the_fuel_share_only():
    c = commuter(has_car=True)
    before = one(c, travel_policy())
    after = one(c, travel_policy(fuel_price_change_pct=25.0))
    assert after["mode"] == "car"
    assert math.isclose(after["cost_jd"], before["cost_jd"] * (1 + 0.25 * DEFAULT.FUEL_SHARE_OF_CAR_COST), abs_tol=0.011)
    assert after["monthly_cost_before_jd"] == before["cost_jd"]


def test_cash_support_floors_at_zero_and_only_for_eligible_groups():
    low = commuter(income_band="low")
    mid = commuter(income_band="middle")
    p = travel_policy(fuel_price_change_pct=25.0, cash_support=[CashSupport(groups=["low_income"], amount_jd_month=500)])
    lo = one(low, p)
    assert lo["cost_jd"] == 0.0 and lo["status"] == "served" and lo["cash_support_jd_month"] == 500
    assert lo["extra_jd_month"] == -lo["monthly_cost_before_jd"]
    assert one(mid, p) == one(mid, travel_policy(fuel_price_change_pct=25.0))  # not eligible: nothing changes
    # The largest eligible amount applies, never the sum.
    two = travel_policy(cash_support=[CashSupport(groups=["low_income"], amount_jd_month=5),
                                      CashSupport(groups=["worker", "low_income"], amount_jd_month=8)])
    base = one(low, travel_policy())["cost_jd"]
    assert one(low, two)["cost_jd"] == round(base - 8, 2) and one(low, two)["cash_support_jd_month"] == 8


def test_fare_freezes():
    bus_rider, car_owner = commuter(), commuter(has_car=True)
    taxi_rider = commuter(mobility="wheelchair")
    up = travel_policy(fuel_price_change_pct=50.0)
    frozen = travel_policy(fuel_price_change_pct=50.0, bus_fare_change_pct=0.0, taxi_fare_change_pct=0.0)
    assert one(taxi_rider, up)["mode"] == "taxi"
    for c in (bus_rider, taxi_rider):
        assert one(c, frozen)["cost_jd"] == one(c, travel_policy())["cost_jd"] < one(c, up)["cost_jd"]
    assert one(car_owner, frozen)["cost_jd"] == one(car_owner, up)["cost_jd"] > one(car_owner, travel_policy())["cost_jd"]
    # A set fare change overrides the fuel pass-through.
    plus10 = one(bus_rider, travel_policy(bus_fare_change_pct=10.0))
    assert math.isclose(plus10["cost_jd"], one(bus_rider, travel_policy())["cost_jd"] * 1.1, abs_tol=0.011)


def test_vouchers_reduce_fares_not_car_costs():
    p = travel_policy(transport_vouchers=[TransportVoucher(groups=["low_income"], amount_jd=0.5)])
    rider, driver = commuter(income_band="low"), commuter(income_band="low", has_car=True)
    trips = 5 * DEFAULT.WEEKS_PER_MONTH
    assert math.isclose(one(rider, p)["cost_jd"], one(rider, travel_policy())["cost_jd"] - 0.5 * trips, abs_tol=0.011)
    assert one(driver, p) == one(driver, travel_policy())
    big = travel_policy(transport_vouchers=[TransportVoucher(groups=["low_income"], amount_jd=50)])
    assert one(rider, big)["cost_jd"] == 0.0


def test_no_trip_citizens_are_served_at_zero_cost():
    plan = world.daily_trips()
    pop = world.population()
    outs = engine.run(world.scenario_policy(DEMO))
    none = [o for c, o in zip(pop, outs) if c["id"] not in plan]
    assert len(none) == len(pop) - sum(c["id"] in plan for c in pop) > 0
    for o in none:
        assert o["status"] == "served" and o["channel"] == "no_regular_trip" and o["mode"] is None
        assert o["cost_jd"] == 0.0 and o["purpose"] is None and o["channel_name_ar"] == "لا رحلة منتظمة"


def test_travel_kpis():
    r = engine.simulate(world.scenario_policy(DEMO))
    k = r.kpis
    for key in ("avg_monthly_cost_jd", "avg_extra_jd_month", "total_extra_jd_month", "n_cash_support",
                "avg_income_share_pct", "by_purpose", "by_mode", "n_with_trip"):
        assert key in k
    assert sum(v["n"] for v in k["by_purpose"].values()) == sum(v["n"] for v in k["by_mode"].values()) == k["n_with_trip"]
    assert k["avg_extra_jd_month"] > 0 and k["n_cash_support"] == 0
    d = kpi_delta(engine.simulate(world.scenario_policy(TODAY)).kpis, k)
    assert "by_purpose" not in d and "by_mode" not in d and "avg_extra_jd_month" in d
    # id_renewal kpis don't get the travel keys.
    assert "by_purpose" not in engine.simulate(world.scenario_policy("baseline")).kpis


def test_pinned_travel_demo_numbers():
    r = compare(world.scenario_policy(TODAY), world.scenario_policy(DEMO))
    b, s = r.baseline.kpis, r.scenario.kpis
    assert (b["pct_served"], b["pct_hardship"], b["pct_left_out"]) == (72.2, 17.8, 10.0), f"{MSG} ({b})"
    assert (s["pct_served"], s["pct_hardship"], s["pct_left_out"]) == (70.2, 14.6, 15.2), f"{MSG} ({s})"
    assert len(r.flipped_worse) == 72 and not r.flipped_better, MSG
    assert r.worst_groups[:2] == ["worker", "offline"], f"{MSG} ({r.worst_groups})"


# ------------------------------------------------------------------ fix grid + robustness

@pytest.mark.parametrize("sid", ["fuel_plus_5", "fuel_plus_25", DEMO, "fuel_plus_25_support"])
def test_travel_fixes_never_touch_the_fuel_price_or_worsen_a_group(sid):
    scen = world.scenario_policy(sid)
    singles = fixgrid.singles(scen)
    assert singles and all(s["apply"](scen).fuel_price_change_pct == scen.fuel_price_change_pct for s in singles)
    built = fixgrid.build(scen)
    assert built
    for c in built:
        assert c["policy"].fuel_price_change_pct == scen.fuel_price_change_pct
        assert c["policy"].service == SERVICE and not c["worsens_any_group"]
        assert c["left_out_drop"] > 0 or c["hardship_drop"] > 0
    assert [c["id"] for c in built] == [c["id"] for c in sorted(built, key=fixgrid.rank_key)]
    for c in built:  # never two cash supports for the same group in one pair
        cash = [p["group"] for p in c["parts"] if p["kind"] == "cash"]
        assert len(cash) == len(set(cash))


def test_travel_singles_skip_what_the_scenario_already_has():
    ids = {s["id"] for s in fixgrid.singles(world.scenario_policy("fuel_plus_25_support"))}
    assert "cash:low_income:14" not in ids and "cash:low_income:8" not in ids and "cash:low_income:20" in ids
    frozen = travel_policy(fuel_price_change_pct=25.0, bus_fare_change_pct=0.0)
    assert "freeze_bus_fares" not in {s["id"] for s in fixgrid.singles(frozen)}
    titles = {s["id"]: (s["title_ar"], s["title_en"]) for s in fixgrid.singles(world.scenario_policy(DEMO))}
    assert titles["cash:low_income:14"] == ("دعم نقدي 14 ديناراً شهرياً لذوي الدخل المحدود",
                                            "14 JD a month cash support for low-income people")
    assert titles["freeze_bus_fares"] == ("تجميد أجور الحافلات", "Freeze bus fares")


def test_sensitivity_uses_the_travel_params():
    base, scen = world.scenario_policy(TODAY), world.scenario_policy(DEMO)
    top = fixgrid.top_fixes(scen)[0].policy
    res = sensitivity.check(base, scen, top)
    params = {d["param"] for d in res.details} - {"reference"}
    assert params == set(SENSITIVITY_PARAMS_BY_SERVICE[SERVICE]) and res.runs == 6
    assert res.fix_still_helps == 6 and res.stable_top_group == "worker"


def test_travel_heroes_pay_more_and_recover_with_the_top_fix():
    heroes = [h for h in json.loads((world.SCENARIOS_DIR / "heroes.json").read_text(encoding="utf-8"))["heroes"]
              if h.get("service") == SERVICE]
    assert len(heroes) == 3
    pop = world.population()
    idx = {c["id"]: i for i, c in enumerate(pop)}
    today, scen = engine.run(world.scenario_policy(TODAY)), engine.run(world.scenario_policy(DEMO))
    fix = engine.run(fixgrid.top_fixes(world.scenario_policy(DEMO))[0].policy)
    for h in heroes:
        i = idx[h["citizen_id"]]
        assert scen[i]["extra_jd_month"] > 0 and STATUS_RANK[scen[i]["status"]] >= STATUS_RANK[today[i]["status"]]
        if h.get("recovers_with_fix", True):
            assert STATUS_RANK[fix[i]["status"]] <= STATUS_RANK[today[i]["status"]]
        else:  # a hero kept on purpose because the top fix does NOT reach them (the honest "who is still missed" moment)
            assert STATUS_RANK[fix[i]["status"]] > STATUS_RANK[today[i]["status"]]
        assert (h["baseline"], h["scenario"], h["with_top_fix"]) == (today[i]["status"], scen[i]["status"], fix[i]["status"])
        assert h["note_ar"] and h["note_en"]
    assert sum(1 for h in heroes if not h.get("recovers_with_fix", True)) <= 1


# ------------------------------------------------------------------ API

def _p(sid):
    return copy.deepcopy(world.scenarios()[sid]["policy"])


def test_services_endpoint():
    r = client.get("/services")
    assert r.status_code == 200
    by_id = {s["id"]: s for s in r.json()}
    assert set(by_id) == {"id_renewal", SERVICE, "medical_exemption"}
    assert by_id[SERVICE]["demo_scenario"] == DEMO and by_id[SERVICE]["baseline_scenario"] == TODAY
    assert by_id["id_renewal"]["demo_scenario"] == world.demo_scenario_id()
    for s in by_id.values():
        assert s["demo_scenario"] in world.scenarios() and s["baseline_scenario"] in world.scenarios()


def test_scenarios_carry_their_service_and_travel_comes_after_id_renewal():
    rows = client.get("/scenarios").json()
    services = [s["service"] for s in rows]
    assert set(services) == {"id_renewal", SERVICE, "medical_exemption"}
    rank = {"id_renewal": 0, SERVICE: 1, "medical_exemption": 2}  # id_renewal, then travel, then exemptions
    assert services == sorted(services, key=rank.get)
    travel = {s["id"] for s in rows if s["service"] == SERVICE}
    assert travel == {TODAY, "fuel_plus_5", "fuel_plus_25", DEMO, "fuel_plus_25_support"}
    assert [s["id"] for s in rows if s["demo"]] == ["consolidate_digital_first", DEMO, "exemption_online_only"]


def test_heroes_by_service():
    ids = client.get("/heroes").json()
    travel = client.get("/heroes", params={"service": SERVICE}).json()
    assert len(ids) == 4 and all(h["service"] == "id_renewal" for h in ids)
    assert len(travel) == 3 and all(h["service"] == SERVICE for h in travel)
    assert client.get("/heroes", params={"service": "nope"}).status_code == 422


def test_travel_endpoints_dispatch():
    r = client.post("/simulate", json={"policy": _p(DEMO)})
    assert r.status_code == 200 and "by_purpose" in r.json()["kpis"]
    r = client.post("/compare", json={"baseline": _p(TODAY), "scenario": _p(DEMO)})
    assert r.status_code == 200 and len(r.json()["flipped_worse"]) == 72
    r = client.post("/fixgrid", json={"baseline": _p(TODAY), "scenario": _p(DEMO)})
    assert r.status_code == 200
    d = r.json()
    assert 1 <= len(d["fixes"]) <= 3 and "by_mode" in d["scenario_kpis"]
    assert all(f["policy"]["fuel_price_change_pct"] == 25.0 for f in d["fixes"])
    r = client.post("/sensitivity", json={"baseline": _p(TODAY), "scenario": _p(DEMO)})
    assert r.status_code == 200 and {x["param"] for x in r.json()["details"]} >= set(SENSITIVITY_PARAMS_BY_SERVICE[SERVICE])


@pytest.mark.parametrize("path", ["/compare", "/fixgrid", "/sensitivity"])
def test_service_mismatch_is_422(path):
    r = client.post(path, json={"baseline": _p("baseline"), "scenario": _p(DEMO)})
    assert r.status_code == 422 and "different services" in r.json()["detail"]


def test_sensitivity_fix_of_another_service_is_422():
    r = client.post("/sensitivity", json={"baseline": _p(TODAY), "scenario": _p(DEMO), "fix": _p("baseline")})
    assert r.status_code == 422


@pytest.mark.parametrize("field,value", [("fuel_price_change_pct", 500), ("fuel_price_change_pct", -80),
                                         ("bus_fare_change_pct", 250), ("taxi_fare_change_pct", -51)])
def test_out_of_range_pct_is_422(field, value):
    p = _p(DEMO)
    p[field] = value
    r = client.post("/simulate", json={"policy": p})
    assert r.status_code == 422 and field in r.json()["detail"]


def test_nan_pct_and_groupless_cash_support_are_422():
    p = _p(DEMO)
    p["fuel_price_change_pct"] = float("nan")
    r = client.post("/simulate", content=json.dumps({"policy": p}), headers={"content-type": "application/json"})
    assert r.status_code == 422
    q = _p(DEMO)
    q["cash_support"] = [{"groups": [], "amount_jd_month": 10}]
    assert client.post("/simulate", json={"policy": q}).status_code == 422


# ------------------------------------------------------------------ warm-up

def test_warm_up_covers_the_travel_demo():
    w = warmup.warm_travel()
    assert w["demo"] == world.scenario_policy(DEMO) and w["base"] == world.scenario_policy(TODAY)
    assert w["top"] and {"ranking_only", "top_fix"} <= set(w["sensitivity"])
    sim_routes._store_warm(w)
    req = sim_routes.SensitivityRequest(baseline=w["base"], scenario=w["demo"], fix=w["top"][0]["policy"])
    assert sim_routes._SENS_CACHE[sim_routes._sens_key(req)] is w["sensitivity"]["top_fix"]
    assert travel_service.memo_entries()["results"] > 0
