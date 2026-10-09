import time

from app.sim import engine, fixgrid, sensitivity, world
from app.sim.validate import count_changes

from .test_engine import WD, office, policy


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
    sim_routes.WARM_DONE.clear()
    with TestClient(app) as c:  # starts the warm-up in a background thread
        assert c.get("/health").json()["ok"]  # answers while the warm-up is still running
        assert sim_routes.WARM_DONE.wait(120)
        n = len(sim_routes._SENS_CACHE)
        assert n >= 2  # no fix + the top grid fix (+ the cached AI fix when the AI cache has it)
        base = world.scenarios()["baseline"]["policy"]
        demo = world.scenarios()[world.demo_scenario_id()]["policy"]
        r = c.post("/sensitivity", json={"baseline": base, "scenario": demo, "fix": None})
        assert r.status_code == 200 and r.json()["ranking_held"] == 6
        top = c.post("/fixgrid", json={"baseline": base, "scenario": demo}).json()["fixes"][0]["policy"]
        r = c.post("/sensitivity", json={"baseline": base, "scenario": demo, "fix": top})
        assert r.status_code == 200 and r.json()["fix_checked"]
        assert len(sim_routes._SENS_CACHE) == n  # served from the primed cache, nothing new computed


def test_warm_up_failure_is_logged_and_the_server_still_starts(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routes import sim_routes
    from app.sim import warmup

    def boom():
        raise RuntimeError("no data")
    monkeypatch.setattr(warmup, "warm", boom)
    sim_routes.WARM_DONE.clear()
    with TestClient(app) as c:
        assert sim_routes.WARM_DONE.wait(10)
        assert c.get("/health").status_code == 200


def test_late_thursday_extends_only_offices_open_on_thursday():
    open_thu = office()  # Sun-Thu 08:00-15:00
    open_thu.schedule["thu"] = ("09:30", "13:00")
    closed_thu = office(days=["sun", "mon"]).model_copy(update={"id": "o2"})
    late = fixgrid._late_thu(policy(offices=[open_thu, closed_thu]))
    a, b = late.offices
    assert a.schedule["thu"] == ("09:30", "19:00")  # real start time kept
    assert "thu" not in b.schedule and b.schedule == closed_thu.schedule  # never reopens a closed Thursday
    assert all(a.schedule[d] == ("08:00", "15:00") for d in WD if d != "thu")
    # With no office open on Thursday the toggle changes nothing, so the grid drops it.
    no_thu = policy(offices=[office(days=["sun", "mon", "tue"])])
    assert "late_thu" not in {s["id"] for s in fixgrid.singles(no_thu)}
    assert "late_thu" in {s["id"] for s in fixgrid.singles(policy())}


def test_pairs_skip_two_vans_in_the_same_area(monkeypatch):
    scen = world.scenario_policy(world.demo_scenario_id())
    real = fixgrid.singles(scen)
    picked = [s for s in real if s["id"] in ("van:sweileh:sat", "van:sweileh:thu", "van:downtown:sat")]
    assert len(picked) == 3
    monkeypatch.setattr(fixgrid, "singles", lambda _p: picked)
    ids = {c["id"] for c in fixgrid.build(scen)}
    assert "pair:van:sweileh:sat+van:sweileh:thu" not in ids
    assert not any(c["kind"] == "pair" and c["parts"][0]["area"] == c["parts"][1]["area"]
                   for c in fixgrid.build(scen) if c["kind"] == "pair")
    assert any(i.startswith("pair:") and "downtown" in i for i in ids)


def test_fix_candidates_carry_their_kpis_and_change_count():
    scen = world.scenario_policy(world.demo_scenario_id())
    sk, _ = engine.summarize(engine.run(scen))
    for fc, c in zip(fixgrid.top_fixes(scen), fixgrid.build(scen)):
        assert fc.n_changes == c["n_changes"] == (2 if c["kind"] == "pair" else 1)
        assert fc.kpis == engine.summarize(engine.run(fc.policy))[0]
        assert round(sk["pct_left_out"] - fc.kpis["pct_left_out"], 1) == fc.left_out_drop
        assert "left_out_by_reason" in fc.kpis
