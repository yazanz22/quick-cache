"""Warm the AI cache for the demo (CLAUDE.md §12, H9-10). Run ONLINE, AFTER final scenario work.

Caches: the demo parse sentence + rehearsed judge requests, hero voices under baseline /
scenario / top fix, the report, and the /fixes explanations. Then the demo also works with
DEMO_OFFLINE=1. Uses roughly 25-30 AI calls; already-cached items cost nothing.

    python -m scripts.warm_cache
"""
import json

from app.config import SCENARIOS_DIR
from app.llm import tasks
from app.models import Policy
from app.sim import engine, fixgrid, sensitivity, world
from app.sim.compare import compare
from app.sim.validate import canonical


def main() -> None:
    req = json.loads((SCENARIOS_DIR / "demo_requests.json").read_text(encoding="utf-8"))
    demo = req["demo"]
    r = tasks.parse_policy(demo["text"], world.scenario_policy(demo["apply_to"]))
    same = r.policy is not None and canonical(r.policy) == canonical(world.scenario_policy(demo["expected"]))
    print(f"[demo parse] {r.source} {r.status} matches preset: {same} | {r.changes_en}")
    for x in req["requests"]:
        r = tasks.parse_policy(x["text"], world.scenario_policy(x["apply_to"]))
        flag = "OK " if r.status == x["expect"] else "!! "
        print(f"{flag}[parse] {x['text'][:50]:50s} -> {r.source} {r.status} {r.changes_en or r.message_en}")

    heroes = json.loads((SCENARIOS_DIR / "heroes.json").read_text(encoding="utf-8"))
    sid = heroes["scenario"]
    base, scen = world.scenario_policy("baseline"), world.scenario_policy(sid)
    fix = fixgrid.top_fixes(scen)[0].policy
    by_id = world.population_by_id()
    idx = {c["id"]: i for i, c in enumerate(world.population())}
    for label, pol in [("baseline", base), (sid, scen), ("top fix", fix)]:
        outs = engine.run(pol)
        for h in heroes["heroes"]:
            v = tasks.voice_citizen(by_id[h["citizen_id"]], outs[idx[h["citizen_id"]]])
            print(f"[voice] {label:22s} {h['citizen_id']} {v.source:8s} {v.text_ar}")

    cr = compare(base, scen)
    sens = sensitivity.check(base, scen, fix)
    rep = tasks.write_report(cr, sens)
    print(f"[report] {rep.source}: {rep.summary_en[:160]}")
    fx = tasks.explain_and_propose_fixes(base, scen)
    print(f"[fixes] {fx.source} ai_proposal={fx.ai_proposal}")
    print("\nDone. Commit backend/cache/ so teammates and the demo machine have it.")


if __name__ == "__main__":
    main()
