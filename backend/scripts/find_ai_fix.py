"""Find a guaranteed "AI-proposed · verified" fix for the demo path (CLAUDE.md §10).

Tries the plain prompt, then a few prompt hints, bypassing the cache, until the engine
verifies that the AI's off-grid proposal beats the best grid fix. The winner is written
to the cache under the normal /fixes key, so the demo always shows it (also offline).

    python -m scripts.find_ai_fix [scenario_id]
"""
import json
import sys

from app.llm import tasks
from app.sim import world

HINTS = [
    None,
    "mobile units in two different high-need areas on different days (e.g. Friday and Saturday), with longer hours",
    "a late weekday opening until 19:00 at the office plus one Saturday mobile unit where most people struggle",
    "a Saturday opening at the office plus one mobile unit with longer hours (08:00-17:00) in the area with most people not served",
    "a second office at another site that serves east Amman, open on weekdays and Saturday",
    "three mobile units on Saturday in the three areas with most people not served",
    "cover every area in left_out_by_area with a Saturday mobile unit, then use any remaining change for hardship",
]


def main(scenario_id: str = "abdali_digital_first") -> None:
    base, scen = world.scenario_policy("baseline"), world.scenario_policy(scenario_id)
    for i, hint in enumerate(HINTS):
        r = tasks.explain_and_propose_fixes(base, scen, hint=hint, use_cache=False)
        note = r.ai_proposal or {}
        print(f"[{i}] hint={hint!r}\n    -> {json.dumps(note, ensure_ascii=False)}")
        if note.get("status") == "shown":
            ai = next(f for f in r.fixes if f.source == "ai_proposed")
            print("\nFOUND and cached:", ai.title_en, "| left_out_drop", ai.left_out_drop, "| hardship_drop", ai.hardship_drop)
            return
    print("\nNo AI proposal beat the best grid fix. Say so honestly on stage (CLAUDE.md §10).")


if __name__ == "__main__":
    main(*sys.argv[1:])
