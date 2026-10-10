"""Find a guaranteed "AI-proposed · verified" fix for a service's demo path (CLAUDE.md §10).

Tries the plain prompt, then a few prompt hints, bypassing the cache, until the engine
verifies that the AI's off-grid proposal beats the best grid fix. The winner is written
to the cache under the normal /fixes key, so the demo always shows it (also offline).
Each try is one AI call (at most len(HINTS) calls per run).

    python -m scripts.find_ai_fix [--service id_renewal|everyday_travel] [scenario_id]
"""
import json
import sys

from app import config
from app.llm import tasks
from app.sim import world

HINTS = {
    "id_renewal": [
        None,
        "mobile units in two different high-need areas on different days (e.g. Friday and Saturday), with longer hours",
        "a late weekday opening until 19:00 at the office plus one Saturday mobile unit where most people struggle",
        "a Saturday opening at the office plus one mobile unit with longer hours (08:00-17:00) in the area with most people not served",
        "a second office at another site that serves east Amman, open on weekdays and Saturday",
        "three mobile units on Saturday in the three areas with most people not served",
        "cover every area in left_out_by_area with a Saturday mobile unit, then use any remaining change for hardship",
    ],
    "everyday_travel": [
        None,
        "cash support for low_income plus a bus fare freeze, since most people priced out ride the bus",
        "one cash support entry for two groups at once (e.g. low_income and student) at the largest allowed amount, "
        "plus a bus fare freeze",
        "cash support for low_income and for worker at the largest allowed amount, plus a transport voucher for no_car",
        "a bus fare freeze and a taxi fare freeze plus cash support for the group with the highest priced-out share",
        "target the groups with the most people priced out in scenario_by_group with cash support, and freeze bus fares",
    ],
}


def main(argv: list[str]) -> None:
    service = "id_renewal"
    if "--service" in argv:
        i = argv.index("--service")
        if i + 1 >= len(argv) or argv[i + 1] not in HINTS:
            raise SystemExit(f"--service needs one of: {', '.join(HINTS)}")
        service = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if config.DEMO_OFFLINE:
        print("DEMO_OFFLINE=1: this script needs the AI (it bypasses the cache). Nothing done.")
        return
    scenario_id = argv[0] if argv else world.demo_scenario_id(service)
    base, scen = world.scenario_policy(world.baseline_scenario_id(service)), world.scenario_policy(scenario_id)
    if scen.service != service:
        raise SystemExit(f"{scenario_id} is a {scen.service} scenario, not {service}")
    for i, hint in enumerate(HINTS[service]):
        r = tasks.explain_and_propose_fixes(base, scen, hint=hint, use_cache=False)
        note = r.ai_proposal or {}
        print(f"[{i}] hint={hint!r}\n    -> {json.dumps(note, ensure_ascii=False)}")
        if note.get("status") == "shown":
            ai = next(f for f in r.fixes if f.source == "ai_proposed")
            print("\nFOUND and cached:", ai.title_en, "| left_out_drop", ai.left_out_drop, "| hardship_drop", ai.hardship_drop)
            return
    print("\nNo AI proposal beat the best grid fix. Say so honestly on stage (CLAUDE.md §10).")


if __name__ == "__main__":
    main(sys.argv[1:])
