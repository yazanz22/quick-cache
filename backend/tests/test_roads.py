"""Road closures: data, engine, validation and AI-layer plumbing. Offline, no AI calls."""
from app.llm import fallbacks, tasks
from app.sim import engine, world
from app.sim.engine import STATUS_RANK
from app.sim.validate import canonical, count_changes, policy_errors


def _with(p, roads):
    return p.model_copy(update={"closed_roads": list(roads)})


def test_catalogue_has_15_to_20_roads_with_geometry_and_detours():
    roads, deltas = world.roads(), world.road_deltas()
    assert 15 <= len(roads) <= 20
    for rid, r in roads.items():
        assert r["name_ar"] and r["name_en"] and r["osm_ways"] > 0 and r["lines"]
        assert rid in deltas
    for per_road in deltas.values():
        for per_citizen in per_road.values():
            assert all(s > 0 and m >= 0 for s, m in per_citizen.values())


def test_no_closure_changes_nothing_and_shows_no_detour():
    p = world.scenario_policy("baseline")
    a, b = engine.run(p), engine.run(_with(p, []))
    assert a == b
    assert all(o["detour_minutes"] == 0 and o["detour_road"] is None for o in a)


def test_closures_never_help_anyone_and_detours_name_the_road():
    for sid in ["baseline", world.demo_scenario_id()]:
        p = world.scenario_policy(sid)
        before = engine.run(p)
        for rid in ["queen_rania", "prince_hasan", "zahran"]:
            after = engine.run(_with(p, [rid]))
            assert all(STATUS_RANK[o1["status"]] >= STATUS_RANK[o0["status"]] for o0, o1 in zip(before, after))
            for o in after:
                if o["detour_minutes"] > 0:
                    assert o["detour_road"] == rid and o["mode"] != "online"


def test_queen_rania_closure_tells_a_story_in_the_baseline():
    """Measured with scripts/road_impact.py: closing Queen Rania St pushes people into hardship."""
    p = world.scenario_policy("baseline")
    k0, _ = engine.summarize(engine.run(p))
    k1, _ = engine.summarize(engine.run(_with(p, ["queen_rania"])))
    assert k1["n_hardship"] > k0["n_hardship"]
    assert k1["n_detour"] > 0 and k1["avg_detour_min"] > 0 and k0["n_detour"] == 0


def test_more_closures_never_shorten_a_trip():
    """Several closures take the largest single-road detour (a lower bound on the true combined detour)."""
    pid = next(iter(world.road_deltas()["queen_rania"]))
    for dest in world.road_deltas()["queen_rania"][pid]:
        one = world.detour(pid, dest, ("queen_rania",))
        two = world.detour(pid, dest, ("queen_rania", "zahran"))
        assert two[0] >= one[0] > 0


def test_validation_canonical_and_change_count():
    p = world.scenario_policy("baseline")
    assert any("unknown road" in e for e in policy_errors(_with(p, ["not_a_road"])))
    assert not policy_errors(_with(p, ["zahran", "cairo"]))
    assert canonical(_with(p, ["zahran", "cairo"])) == canonical(_with(p, ["cairo", "zahran", "zahran"]))
    assert count_changes(p, _with(p, ["zahran", "cairo"])) == 2


def test_cache_keys_without_closures_are_unchanged():
    """policy_json drops an empty closed_roads, so AI cache entries made before closures existed still hit."""
    p = world.scenario_policy("baseline")
    assert "closed_roads" not in tasks.policy_json(p)
    assert tasks.policy_json(_with(p, ["zahran"]))["closed_roads"] == ["zahran"]


def test_voice_mentions_the_closed_road_only_when_it_lengthened_the_trip():
    p = world.scenario_policy("baseline")
    pop = world.population()
    out = engine.run(_with(p, ["queen_rania"]))
    i = next(i for i, o in enumerate(out) if o["detour_minutes"] >= 1)
    facts = tasks.voice_facts(pop[i], out[i])
    assert facts["outcome"]["closed_road_ar"] == world.roads()["queen_rania"]["name_ar"]
    ar, en = fallbacks.voice(pop[i], out[i])
    assert world.roads()["queen_rania"]["name_ar"] in ar and "Queen Rania" in en
    plain = engine.run(p)[i]
    assert "closed_road_ar" not in tasks.voice_facts(pop[i], plain)["outcome"]


def test_roads_route_and_unknown_road_is_a_422():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    roads = c.get("/roads").json()
    assert len(roads) == len(world.roads()) and roads[0]["lines"]
    pol = world.scenario_policy("baseline").model_dump(mode="json")
    r = c.post("/simulate", json={"policy": {**pol, "closed_roads": ["nope"]}})
    assert r.status_code == 422 and "unknown road" in r.text
    r = c.post("/simulate", json={"policy": {**pol, "closed_roads": ["queen_rania"]}})
    assert r.status_code == 200 and r.json()["kpis"]["n_detour"] > 0
