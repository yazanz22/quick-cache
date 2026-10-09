"""Baseline vs scenario diff + equity breakdown (CLAUDE.md §5 CompareResult)."""
from __future__ import annotations

from ..models import CompareResult, Policy, SimResult
from . import world
from .assumptions import Assumptions
from .engine import STATUS_RANK, run, summarize, simulate


def worst_groups(base_by_group: dict, scen_by_group: dict) -> list[str]:
    """Equity groups ranked by Δ(left_out% + hardship%), worst first. Ties: larger Δleft_out, then name."""
    def delta(g):
        b, s = base_by_group[g], scen_by_group[g]
        return (s["left_out"] + s["hardship"]) - (b["left_out"] + b["hardship"]), s["left_out"] - b["left_out"]
    return sorted(world.EQUITY_GROUPS, key=lambda g: (-delta(g)[0], -delta(g)[1], g))


def kpi_delta(base: dict, scen: dict) -> dict:
    return {k: round(scen[k] - base[k], 2) for k in base if isinstance(base[k], (int, float))}


def quick(baseline: Policy, scenario: Policy, pop=None, assumptions: Assumptions | None = None) -> dict:
    """Numbers only, no outcome lists; used by fixgrid and sensitivity."""
    pop = pop if pop is not None else world.population()
    bk, bg = summarize(run(baseline, pop, assumptions), pop)
    sk, sg = summarize(run(scenario, pop, assumptions), pop)
    return {"base_kpis": bk, "base_groups": bg, "kpis": sk, "groups": sg, "worst_groups": worst_groups(bg, sg)}


def compare(baseline: Policy, scenario: Policy, pop=None, assumptions: Assumptions | None = None) -> CompareResult:
    pop = pop if pop is not None else world.population()
    b: SimResult = simulate(baseline, pop, assumptions)
    s: SimResult = simulate(scenario, pop, assumptions)
    worse, better = [], []
    for ob, os_ in zip(b.outcomes, s.outcomes):
        d = STATUS_RANK[os_.status] - STATUS_RANK[ob.status]
        if d > 0:
            worse.append(ob.citizen_id)
        elif d < 0:
            better.append(ob.citizen_id)
    return CompareResult(baseline=b, scenario=s, flipped_worse=worse, flipped_better=better,
                         kpi_delta=kpi_delta(b.kpis, s.kpis), worst_groups=worst_groups(b.by_group, s.by_group))
