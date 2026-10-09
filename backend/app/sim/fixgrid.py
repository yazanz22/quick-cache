"""Candidate-fix grid (CLAUDE.md §6.4). Engine only, no AI, deterministic.

Each candidate is a full Policy = scenario + one change (or a pair of changes),
scored against the scenario it fixes.
"""
from __future__ import annotations

from itertools import combinations

from ..models import FixCandidate, MobileUnit, Policy
from . import world
from .assumptions import Assumptions
from .engine import run, summarize

VAN_DAYS = ["sat", "thu"]
VAN_HOURS = ("09:00", "14:00")
LATE_CLOSE = "19:00"
TOP_SINGLES_FOR_PAIRS = 5
EPS = 0.05  # percentage points; smaller moves are rounding noise

# ------------------------------------------------------------------ changes

def _van(area: str, day: str):
    a = world.areas()[area]
    def apply(p: Policy) -> Policy:
        q = p.model_copy(deep=True)
        q.mobile_units.append(MobileUnit(area=area, day=day, open=VAN_HOURS[0], close=VAN_HOURS[1]))
        return q
    return {
        "id": f"van:{area}:{day}", "kind": "van", "area": area, "apply": apply,
        "title_ar": f"وحدة متنقلة في {a['name_ar']} يوم {world.DAY_AR[day]} (٩–٢، بدون موعد)",
        "title_en": f"Mobile unit in {a['name_en']} on {world.DAY_EN[day]} (09:00–14:00, walk-in)",
    }

def _late_thu(p: Policy) -> Policy:
    q = p.model_copy(deep=True)
    for o in q.offices:
        start = o.schedule["thu"][0] if "thu" in o.schedule else "08:00"
        o.schedule["thu"] = (start, LATE_CLOSE)
    return q

def _no_appointments(p: Policy) -> Policy:
    q = p.model_copy(deep=True)
    q.appointment_required = False
    return q

def _accessible(p: Policy) -> Policy:
    q = p.model_copy(deep=True)
    for o in q.offices:
        o.wheelchair_accessible = True
    return q

TOGGLES = [
    {"id": "late_thu", "kind": "toggle", "apply": _late_thu,
     "title_ar": "دوام مسائي يوم الخميس لحد الساعة ٧ بكل المكاتب", "title_en": "Late Thursday until 19:00 at every office"},
    {"id": "no_appointments", "kind": "toggle", "apply": _no_appointments,
     "title_ar": "إلغاء شرط الموعد المسبق", "title_en": "Remove the appointment requirement"},
    {"id": "accessible", "kind": "toggle", "apply": _accessible,
     "title_ar": "تجهيز كل المكاتب لذوي الإعاقة الحركية", "title_en": "Make every office wheelchair accessible"},
]

def singles(scenario: Policy) -> list[dict]:
    out = []
    existing = {(m.area, m.day) for m in scenario.mobile_units}
    if not scenario.online_only:  # online_only ignores vans and offices entirely
        for area in world.areas():
            for day in VAN_DAYS:
                if (area, day) not in existing:
                    out.append(_van(area, day))
    for t in TOGGLES:
        if t["apply"](scenario).model_dump() != scenario.model_dump():  # skip toggles that change nothing
            out.append(t)
    return out

# ------------------------------------------------------------------ scoring

def score(policy: Policy, scen_kpis: dict, scen_groups: dict, pop=None, assumptions: Assumptions | None = None) -> dict:
    pop = pop if pop is not None else world.population()
    k, g = summarize(run(policy, pop, assumptions), pop)
    worsens = any(
        g[x]["left_out"] > scen_groups[x]["left_out"] + EPS
        or (g[x]["left_out"] + g[x]["hardship"]) > (scen_groups[x]["left_out"] + scen_groups[x]["hardship"]) + EPS
        for x in world.EQUITY_GROUPS)
    return {"left_out_drop": round(scen_kpis["pct_left_out"] - k["pct_left_out"], 1),
            "hardship_drop": round(scen_kpis["pct_hardship"] - k["pct_hardship"], 1),
            "worsens_any_group": worsens, "kpis": k, "groups": g}

def rank_key(c: dict):
    return (-c["left_out_drop"], -c["hardship_drop"], c["n_changes"], c["id"])

def build(scenario: Policy, pop=None, assumptions: Assumptions | None = None) -> list[dict]:
    """All scored candidates (singles + pairs), ranked, excluding ones that worsen a group or don't help."""
    pop = pop if pop is not None else world.population()
    sk, sg = summarize(run(scenario, pop, assumptions), pop)

    scored = []
    for ch in singles(scenario):
        p = ch["apply"](scenario)
        scored.append({**ch, "policy": p, "n_changes": 1, "parts": [ch], **score(p, sk, sg, pop, assumptions)})
    useful = sorted([c for c in scored if not c["worsens_any_group"]
                     and (c["left_out_drop"] > 0 or c["hardship_drop"] > 0)], key=rank_key)

    pairs = []
    for a, b in combinations(useful[:TOP_SINGLES_FOR_PAIRS], 2):
        if a["kind"] == "van" and b["kind"] == "van" and a["area"] == b["area"]:
            continue
        p = b["apply"](a["apply"](scenario))
        pairs.append({
            "id": f"pair:{a['id']}+{b['id']}", "kind": "pair", "policy": p, "n_changes": 2, "parts": [a, b],
            "title_ar": f"{a['title_ar']} + {b['title_ar']}", "title_en": f"{a['title_en']} + {b['title_en']}",
            **score(p, sk, sg, pop, assumptions)})
    allc = useful + [c for c in pairs if not c["worsens_any_group"] and (c["left_out_drop"] > 0 or c["hardship_drop"] > 0)]
    return sorted(allc, key=rank_key)

def to_candidate(c: dict, source: str = "engine_grid") -> FixCandidate:
    return FixCandidate(id=c["id"], title_ar=c["title_ar"], title_en=c["title_en"], policy=c["policy"], source=source,
                        left_out_drop=c["left_out_drop"], hardship_drop=c["hardship_drop"],
                        worsens_any_group=c["worsens_any_group"])

def top_fixes(scenario: Policy, n: int = 3, pop=None, assumptions: Assumptions | None = None) -> list[FixCandidate]:
    return [to_candidate(c) for c in build(scenario, pop, assumptions)[:n]]

def all_policies(scenario: Policy) -> list[Policy]:
    """Every grid policy (singles + all pairs), for the AI-proposal duplicate check."""
    sing = singles(scenario)
    out = [s["apply"](scenario) for s in sing]
    out += [b["apply"](a["apply"](scenario)) for a, b in combinations(sing, 2)]
    return out
