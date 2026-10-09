"""Per-road closure impact: which closures tell a visible story? Engine only, no AI.

For each road in roads.json, close it on top of a scenario and compare with the same scenario with all roads open:
how many citizens change status, and how many extra one-way minutes the people who still travel lose.

    python -m scripts.road_impact [scenario_id ...]     # default: baseline, consolidate and the demo scenario
"""
import sys
from collections import Counter

from app.sim import world
from app.sim.engine import STATUS_RANK, run, summarize


def impact(scenario_id: str) -> None:
    pop = world.population()
    base = world.scenario_policy(scenario_id)
    b_out = run(base, pop)
    bk, _ = summarize(b_out, pop)
    print(f"\n== {scenario_id}: served {bk['pct_served']} / hardship {bk['pct_hardship']} / left out {bk['pct_left_out']}")
    print(f"{'road':18s} {'worse':>5s} {'->hard':>6s} {'->left':>6s} {'detour trips':>12s} {'avg +min':>8s} {'max +min':>8s}  worst groups")
    rows = []
    for rid in world.roads():
        p = base.model_copy(update={"closed_roads": [rid]})
        out = run(p, pop)
        worse = [i for i, (o0, o1) in enumerate(zip(b_out, out)) if STATUS_RANK[o1["status"]] > STATUS_RANK[o0["status"]]]
        to_h = sum(out[i]["status"] == "hardship" for i in worse)
        to_l = sum(out[i]["status"] == "left_out" for i in worse)
        det = [o["detour_minutes"] for o in out if o["detour_minutes"] > 0]
        groups = Counter(t for i in worse for t in pop[i]["tags"] if t in world.EQUITY_GROUPS)
        rows.append((len(worse), rid, to_h, to_l, det, groups))
    for n, rid, to_h, to_l, det, groups in sorted(rows, key=lambda r: (-r[0], r[1])):
        avg = sum(det) / len(det) if det else 0.0
        top = ", ".join(f"{g} {k}" for g, k in groups.most_common(3))
        print(f"{rid:18s} {n:5d} {to_h:6d} {to_l:6d} {len(det):12d} {avg:8.1f} {max(det, default=0):8.1f}  {top}")
    allp = base.model_copy(update={"closed_roads": list(world.roads())})
    out = run(allp, pop)
    k, _ = summarize(out, pop)
    worse = sum(STATUS_RANK[o1["status"]] > STATUS_RANK[o0["status"]] for o0, o1 in zip(b_out, out))
    print(f"{'ALL roads closed':18s} {worse:5d}   -> served {k['pct_served']} / hardship {k['pct_hardship']} / left out {k['pct_left_out']}")


if __name__ == "__main__":
    ids = sys.argv[1:] or ["baseline", "consolidate", world.demo_scenario_id()]
    for sid in ids:
        impact(sid)
