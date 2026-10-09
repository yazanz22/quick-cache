"""Warm the AI cache for the demo (CLAUDE.md §12, H9-10). Run ONLINE, AFTER final scenario work.

Caches: the demo parse sentence + rehearsed judge requests (on baseline and on the demo path), the /fixes
answer (explanations + the verified AI fix), hero voices under baseline / demo scenario / top grid fix /
verified AI fix, and the reports (the old top-fix one, ranking-only, and with the top or the AI fix applied).
Voices and reports go through the same route functions the frontend calls, so the keys match exactly.
Already-cached items cost nothing; the rest is roughly one AI call each.

With DEMO_OFFLINE=1 it never calls the AI: it only reads the cache and ends with a list of MISSES
(what is still on a template, and why it matters). It always exits 0.

    python -m scripts.warm_cache [--parse-only]
"""
import json
import sys

from app import config
from app.config import SCENARIOS_DIR
from app.llm import tasks
from app.models import ReportRequest, VoiceRequest
from app.routes import llm_routes
from app.sim import fixgrid, sensitivity, world
from app.sim.compare import compare
from app.sim.validate import canonical

MISSES: list[tuple[str, str, str]] = []  # (task, item, why it matters)


def _miss(task: str, item: str, why: str) -> None:
    MISSES.append((task, item, why))


def warm_parse() -> None:
    req = json.loads((SCENARIOS_DIR / "demo_requests.json").read_text(encoding="utf-8"))
    demo = req["demo"]
    r = tasks.parse_policy(demo["text"], world.scenario_policy(demo["apply_to"]))
    same = r.policy is not None and canonical(r.policy) == canonical(world.scenario_policy(demo["expected"]))
    print(f"[demo parse] {r.source} {r.status} matches preset: {same} | {r.changes_en}")
    if r.source != "ai":
        _miss("parse", f"stage sentence on {demo['apply_to']}",
              "the on-stage free-text step: without it, click the demo preset instead")
    for x in req["requests"]:
        r = tasks.parse_policy(x["text"], world.scenario_policy(x["apply_to"]))
        flag = "-- " if r.source != "ai" else ("OK " if r.status == x["expect"] else "!! ")  # -- = not cached
        print(f"{flag}[parse] {x['apply_to'][:12]:12s} {x['text'][:50]:50s} -> {r.source} {r.status} "
              f"{r.changes_en or r.message_en}")
        if r.source != "ai":
            where = "the demo path" if x["apply_to"] == world.demo_scenario_id() else x["apply_to"]
            _miss("parse", f"{x['text']!r} on {x['apply_to']}",
                  f"rehearsed judge request on {where}: offline it answers 'AI not available'")


def main(parse_only: bool = False) -> None:
    print(f"DEMO_OFFLINE={'1: cache only, no AI calls' if config.DEMO_OFFLINE else '0: misses call the AI'}\n")
    warm_parse()
    if not parse_only:
        warm_rest()
    print()
    if MISSES:
        print(f"MISSES ({len(MISSES)}): still on a template" + (" (offline: not requested)" if config.DEMO_OFFLINE else ""))
        for task, item, why in MISSES:
            print(f"  - [{task}] {item}: {why}")
        print("Fill them online (after the Gemini quota reset): .venv/Scripts/python -m scripts.warm_cache"
              + (" --parse-only" if parse_only else "") + ", then commit backend/cache/.")
    else:
        print("No misses: everything above is cached.")
    if not config.DEMO_OFFLINE:
        print("Commit backend/cache/ so teammates and the demo machine have it.")


def warm_rest() -> None:
    heroes = json.loads((SCENARIOS_DIR / "heroes.json").read_text(encoding="utf-8"))
    sid = heroes["scenario"]
    base, scen = world.scenario_policy("baseline"), world.scenario_policy(sid)

    # Fixes first: the AI fix (and so its hero voices and report) comes from this answer.
    fx = tasks.explain_and_propose_fixes(base, scen)
    status = (fx.ai_proposal or {}).get("status")
    print(f"[fixes] {fx.source} ai_proposal={fx.ai_proposal}")
    if fx.source != "ai":
        _miss("fixes", f"/fixes on {sid}", "fix explanations use the template and there is no AI-proposed fix")
    elif status != "shown":
        _miss("fixes", f"/fixes on {sid}", f"the AI-proposed fix is not shown (status {status}); "
                                            "run scripts.find_ai_fix online")
    top = fixgrid.top_fixes(scen)[0].policy
    ai_fix = tasks.cached_ai_fix_policy(base, scen)
    if ai_fix is None:
        print("[ai fix] none verified in the cache: its hero voices and report are skipped")

    policies = [("baseline", base), (sid, scen), ("top fix", top)] + ([("AI fix", ai_fix)] if ai_fix else [])
    for label, pol in policies:
        for h in heroes["heroes"]:
            v = llm_routes.post_voice(VoiceRequest(citizen_id=h["citizen_id"], policy=pol))
            print(f"[voice] {label:26s} {h['citizen_id']} {v.source:8s} {v.text_ar}")
            if v.source != "ai":
                _miss("voice", f"{h['citizen_id']} ({h.get('name_en', '')}) under {label}",
                      "clicking this hero shows the template voice")

    # The report as older clients send it (compare_result + the top-fix robustness result): cached since 2026-10-09.
    rep = tasks.write_report(compare(base, scen), sensitivity.check(base, scen, top))
    print(f"[report] old shape, top-fix robustness: {rep.source}: {rep.summary_en[:120]}")
    if rep.source != "ai":
        _miss("report", "compare_result + top-fix sensitivity", "the report shows the template summary")
    # The report as the frontend now sends it (policies; the backend recomputes everything).
    for label, fix in [("no fix applied", None), ("top fix applied", top)] + ([("AI fix applied", ai_fix)] if ai_fix else []):
        rep = llm_routes.post_report(ReportRequest(baseline=base, scenario=scen, fix=fix))
        print(f"[report] {label:16s} {rep.source}: {rep.summary_en[:120]}")
        if rep.source != "ai":
            _miss("report", f"{{baseline, scenario{', fix' if fix else ''}}} ({label})",
                  "the report shows the template summary")


if __name__ == "__main__":
    main(parse_only="--parse-only" in sys.argv)
