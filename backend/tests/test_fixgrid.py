import time

from app.sim import fixgrid, sensitivity, world
from app.sim.validate import count_changes


def test_fixgrid_top3_ranked_safe_and_fast():
    scen = world.scenario_policy(world.demo_scenario_id())
    t = time.perf_counter()
    allc = fixgrid.build(scen)
    assert time.perf_counter() - t < 3.0
    top = fixgrid.top_fixes(scen)
    assert 1 <= len(top) <= 3
    assert [c.id for c in top] == [c["id"] for c in allc[:3]]
    keys = [fixgrid.rank_key(c) for c in allc]
    assert keys == sorted(keys)
    assert not any(c["worsens_any_group"] for c in allc)
    assert all(c["left_out_drop"] > 0 or c["hardship_drop"] > 0 for c in allc)
    assert [c.id for c in fixgrid.top_fixes(scen)] == [c.id for c in top]  # deterministic


def test_fixgrid_skips_toggles_that_change_nothing():
    base = world.scenario_policy("baseline")  # walk-in + accessible already
    ids = {s["id"] for s in fixgrid.singles(base)}
    assert "no_appointments" not in ids and "accessible" not in ids and "late_thu" in ids


def test_sensitivity_runs_six_times():
    base, scen = world.scenario_policy("baseline"), world.scenario_policy(world.demo_scenario_id())
    fix = fixgrid.top_fixes(scen)[0].policy
    s = sensitivity.check(base, scen, fix)
    assert s.runs == 6 and len(s.details) == 7
    assert s.passed == (s.ranking_held == 6 and s.fix_still_helps == 6)


def test_count_changes():
    scen = world.scenario_policy(world.demo_scenario_id())
    pair = fixgrid.build(scen)[0]["policy"]
    assert count_changes(scen, scen) == 0
    assert count_changes(scen, pair) == 2


def test_sensitivity_without_a_fix_checks_the_ranking_only():
    base, scen = world.scenario_policy("baseline"), world.scenario_policy(world.demo_scenario_id())
    s = sensitivity.check(base, scen, None)
    assert s.runs == 6 and not s.fix_checked and not s.passed and s.fix_still_helps == 0
    assert all("fix_still_helps" not in d for d in s.details)


def test_warm_up_primes_the_robustness_cache():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routes import sim_routes
    sim_routes._SENS_CACHE.clear()
    with TestClient(app) as c:  # runs the start-up warm-up
        assert len(sim_routes._SENS_CACHE) == 2
        base = world.scenarios()["baseline"]["policy"]
        demo = world.scenarios()[world.demo_scenario_id()]["policy"]
        r = c.post("/sensitivity", json={"baseline": base, "scenario": demo, "fix": None})
        assert r.status_code == 200 and r.json()["ranking_held"] == 6
        assert len(sim_routes._SENS_CACHE) == 2  # served from the primed cache, nothing new computed
