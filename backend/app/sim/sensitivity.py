"""Robustness check (CLAUDE.md §6.5): perturb the three most uncertain assumptions
one at a time by ±20% (6 runs), re-run baseline, scenario and the chosen fix.

Pass: the top-2 worst groups stay the same, in the same order, in all 6 runs,
and the fix still reduces left_out (or, for a scenario with nobody newly left
out, still reduces left_out + hardship). If the ranking flips we report it as is.
"""
from __future__ import annotations

from ..models import Policy, SensitivityResult
from . import world
from .assumptions import DEFAULT, SENSITIVITY_PARAMS, Assumptions, perturbed
from .compare import quick
from .engine import run, summarize

FACTORS = [0.8, 1.2]


def _fix_effect(scenario_kpis: dict, fix_kpis: dict) -> tuple[float, float]:
    return (round(scenario_kpis["pct_left_out"] - fix_kpis["pct_left_out"], 1),
            round(scenario_kpis["pct_hardship"] - fix_kpis["pct_hardship"], 1))


def check(baseline: Policy, scenario: Policy, fix: Policy, base_assumptions: Assumptions = DEFAULT,
          pop=None) -> SensitivityResult:
    pop = pop if pop is not None else world.population()
    ref = quick(baseline, scenario, pop, base_assumptions)
    ref_top2 = ref["worst_groups"][:2]
    ref_fix = summarize(run(fix, pop, base_assumptions), pop)[0]
    ref_lo_drop, _ = _fix_effect(ref["kpis"], ref_fix)
    # If the fix doesn't move left_out at the reference point, judge it on left_out + hardship.
    use_combined = ref_lo_drop <= 0

    details, held, helps, tops = [], 0, 0, [ref["worst_groups"][0]]
    top2_sets = [set(ref_top2)]
    for name in SENSITIVITY_PARAMS:
        for f in FACTORS:
            a = perturbed(base_assumptions, name, f)
            q = quick(baseline, scenario, pop, a)
            fk = summarize(run(fix, pop, a), pop)[0]
            lo_drop, h_drop = _fix_effect(q["kpis"], fk)
            ok_rank = q["worst_groups"][:2] == ref_top2
            ok_fix = (lo_drop + h_drop) > 0 if use_combined else lo_drop > 0
            held += ok_rank
            helps += ok_fix
            tops.append(q["worst_groups"][0])
            top2_sets.append(set(q["worst_groups"][:2]))
            details.append({"param": name, "factor": f, "value": round(getattr(a, name), 2),
                            "top2": q["worst_groups"][:2], "ranking_held": ok_rank,
                            "fix_left_out_drop": lo_drop, "fix_hardship_drop": h_drop, "fix_still_helps": ok_fix})
    runs = len(details)
    stable = tops[0] if all(t == tops[0] for t in tops) else None
    stable2 = ref_top2 if all(x == top2_sets[0] for x in top2_sets) else None
    details.insert(0, {"param": "reference", "factor": 1.0, "top2": ref_top2,
                       "fix_left_out_drop": ref_lo_drop, "judged_on": "left_out+hardship" if use_combined else "left_out"})
    return SensitivityResult(runs=runs, ranking_held=held, fix_still_helps=helps, stable_top_group=stable, stable_top2=stable2,
                             passed=held == runs and helps == runs, details=details)
