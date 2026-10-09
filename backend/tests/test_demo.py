"""Demo guard (offline, no AI): pins the numbers the 7-minute demo, HANDOFF §6, the heroes and the AI cache rely on.

If one of these fails, the engine, the population or a scenario changed. That may be fine, but then the story
on stage changed too: update HANDOFF §6 (and CLAUDE.md §13), re-pick the heroes and re-warm the AI cache.
"""
import json

import pytest

from app.config import SCENARIOS_DIR
from app.models import Policy
from app.sim import fixgrid, sensitivity, world
from app.sim.compare import compare
from app.sim.validate import policy_errors

MSG = "demo numbers changed: update HANDOFF §6, re-pick heroes and re-warm the cache before the demo"
RANK = {"served": 0, "hardship": 1, "left_out": 2}
NOT_SCENARIOS = {"heroes.json", "demo_requests.json"}


def _scenario_files():
    return [p for p in sorted(SCENARIOS_DIR.glob("*.json")) if p.name not in NOT_SCENARIOS]


@pytest.fixture(scope="module")
def demo():
    base = world.scenario_policy("baseline")
    scen = world.scenario_policy(world.demo_scenario_id())
    return base, scen, compare(base, scen)


@pytest.mark.parametrize("path", _scenario_files(), ids=lambda p: p.stem)
def test_every_scenario_is_a_valid_policy(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    assert d.get("id") == path.stem, f"{path.name}: id should match the file name"
    p = Policy.model_validate(d["policy"])
    assert policy_errors(p) == [], f"{path.name}: {policy_errors(p)}"
    sites = world.sites()
    assert all(o.site_id in sites for o in p.offices), f"{path.name}: unknown site_id"


def test_exactly_one_demo_scenario():
    flagged = [p.stem for p in _scenario_files() if json.loads(p.read_text(encoding="utf-8")).get("demo") is True]
    assert flagged == ["consolidate_digital_first"], f"exactly one scenario must have demo: true, got {flagged}"
    assert world.demo_scenario_id() == "consolidate_digital_first"


def test_pinned_demo_numbers(demo):
    _, _, r = demo
    b, s = r.baseline.kpis, r.scenario.kpis
    assert (b["pct_served"], b["pct_hardship"], b["pct_left_out"]) == (88.4, 11.5, 0.1), f"{MSG} (baseline: {b})"
    assert (s["pct_served"], s["pct_hardship"], s["pct_left_out"]) == (79.6, 19.5, 0.9), f"{MSG} (demo path: {s})"
    assert len(r.flipped_worse) == 93, f"{MSG} (worse off: {len(r.flipped_worse)})"
    assert r.worst_groups[:2] == ["elderly", "offline"], f"{MSG} (worst groups: {r.worst_groups[:2]})"


def test_heroes_get_worse_and_recover_with_the_top_fix(demo):
    base, scen, r = demo
    heroes = json.loads((SCENARIOS_DIR / "heroes.json").read_text(encoding="utf-8"))["heroes"]
    assert heroes, "heroes.json has no heroes"
    pop = world.population_by_id()
    fix = fixgrid.top_fixes(scen)[0].policy
    fixed = compare(base, fix)
    b = {o.citizen_id: o.status for o in r.baseline.outcomes}
    s = {o.citizen_id: o.status for o in r.scenario.outcomes}
    f = {o.citizen_id: o.status for o in fixed.scenario.outcomes}
    for h in heroes:
        cid = h["citizen_id"]
        assert cid in pop, f"{MSG} (hero {cid} is not in population.json)"
        assert RANK[s[cid]] > RANK[b[cid]], f"{MSG} (hero {cid}: {b[cid]} -> {s[cid]}, should get worse)"
        assert RANK[f[cid]] <= RANK[b[cid]], f"{MSG} (hero {cid}: {f[cid]} with the top fix, baseline {b[cid]})"


def test_robustness_ranking_holds_6_of_6(demo):
    base, scen, _ = demo
    res = sensitivity.check(base, scen)  # ranking only, as the badge shows before any fix
    assert res.runs == 6
    assert res.ranking_held == 6, f"{MSG} (ranking held {res.ranking_held}/6)"
