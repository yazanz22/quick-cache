"""Warm the AI cache for the demo (CLAUDE.md §12, H9-10). Run ONLINE, AFTER final scenario work.

Per service (id_renewal, everyday_travel), it caches: the rehearsed free-text requests (demo_requests.json; for
id_renewal also the stage sentence), the /fixes answer on the service's demo scenario (explanations + the verified AI
fix), the service's hero voices (heroes.json, by "service") under its baseline / demo scenario / top grid fix /
verified AI fix, and the reports (no fix, top fix, AI fix applied; for id_renewal also the old top-fix shape).
Voices and reports go through the same route functions the frontend calls, so the keys match exactly.
Already-cached items cost nothing; the rest is roughly one AI call each.

With DEMO_OFFLINE=1 it never calls the AI: it only reads the cache and ends with a list of MISSES
(what is still on a template, and why it matters). It always exits 0.

    python -m scripts.warm_cache [--parse-only] [--service id_renewal|everyday_travel]
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

SERVICES = ("id_renewal", "everyday_travel")
MISSES: list[tuple[str, str, str, str]] = []  # (service, task, item, why it matters)


def _miss(service: str, task: str, item: str, why: str) -> None:
    MISSES.append((service, task, item, why))


def _service_of(scenario_id: str) -> str | None:
    s = world.scenarios().get(scenario_id)
    return None if s is None else s.get("service", s["policy"].get("service", "id_renewal"))


def warm_parse(services=SERVICES) -> None:
    req = json.loads((SCENARIOS_DIR / "demo_requests.json").read_text(encoding="utf-8"))
    if "id_renewal" in services:
        demo = req["demo"]
        r = tasks.parse_policy(demo["text"], world.scenario_policy(demo["apply_to"]))
        same = r.policy is not None and canonical(r.policy) == canonical(world.scenario_policy(demo["expected"]))
        print(f"[demo parse] {r.source} {r.status} matches preset: {same} | {r.changes_en}")
        if r.source != "ai":
            _miss("id_renewal", "parse", f"stage sentence on {demo['apply_to']}",
                  "the on-stage free-text step: without it, click the demo preset instead")
    for x in req["requests"]:
        service = _service_of(x["apply_to"])
        if service is None:
            _miss(x.get("service", "?"), "parse", f"{x['text']!r} on {x['apply_to']}",
                  f"scenario {x['apply_to']!r} does not exist (yet): nothing to parse against")
            continue
        if service not in services:
            continue
        r = tasks.parse_policy(x["text"], world.scenario_policy(x["apply_to"]))
        flag = "-- " if r.source != "ai" else ("OK " if r.status == x["expect"] else "!! ")  # -- = not cached
        print(f"{flag}[parse] {x['apply_to'][:12]:12s} {x['text'][:50]:50s} -> {r.source} {r.status} "
              f"{r.changes_en or r.message_en}")
        if r.source != "ai":
            where = "the demo path" if x["apply_to"] == world.demo_scenario_id(service) else x["apply_to"]
            _miss(service, "parse", f"{x['text']!r} on {x['apply_to']}",
                  f"rehearsed judge request on {where}: offline it answers 'AI not available'")


def warm_service(service: str) -> None:
    """/fixes, hero voices and reports on the service's demo path."""
    heroes_doc = json.loads((SCENARIOS_DIR / "heroes.json").read_text(encoding="utf-8"))
    heroes = [h for h in heroes_doc["heroes"] if h.get("service", "id_renewal") == service]
    base_id = world.baseline_scenario_id(service)
    sid = heroes_doc["scenario"] if service == "id_renewal" else world.demo_scenario_id(service)
    base, scen = world.scenario_policy(base_id), world.scenario_policy(sid)
    print(f"\n== {service}: {base_id} -> {sid}, {len(heroes)} heroes ==")

    # Fixes first: the AI fix (and so its hero voices and report) comes from this answer.
    fx = tasks.explain_and_propose_fixes(base, scen)
    status = (fx.ai_proposal or {}).get("status")
    print(f"[fixes] {fx.source} ai_proposal={fx.ai_proposal}")
    if fx.source != "ai":
        _miss(service, "fixes", f"/fixes on {sid}", "fix explanations use the template and there is no AI-proposed fix")
    elif status != "shown":
        _miss(service, "fixes", f"/fixes on {sid}", f"the AI-proposed fix is not shown (status {status}); "
                                                     f"run scripts.find_ai_fix --service {service} online")
    tops = fixgrid.top_fixes(scen)
    top = tops[0].policy if tops else None
    ai_fix = tasks.cached_ai_fix_policy(base, scen)
    if ai_fix is None:
        print("[ai fix] none verified in the cache: its hero voices and report are skipped")

    policies = [(base_id, base), (sid, scen)] + ([("top fix", top)] if top else []) + \
               ([("AI fix", ai_fix)] if ai_fix else [])
    for label, pol in policies:
        for h in heroes:
            v = llm_routes.post_voice(VoiceRequest(citizen_id=h["citizen_id"], policy=pol))
            print(f"[voice] {label:26s} {h['citizen_id']} {v.source:8s} {v.text_ar}")
            if v.source != "ai":
                _miss(service, "voice", f"{h['citizen_id']} ({h.get('name_en', '')}) under {label}",
                      "clicking this hero shows the template voice")

    if service == "id_renewal" and top is not None:
        # The report as older clients send it (compare_result + the top-fix robustness result): cached since 2026-10-09.
        rep = tasks.write_report(compare(base, scen), sensitivity.check(base, scen, top))
        print(f"[report] old shape, top-fix robustness: {rep.source}: {rep.summary_en[:120]}")
        if rep.source != "ai":
            _miss(service, "report", "compare_result + top-fix sensitivity", "the report shows the template summary")
    # The report as the frontend now sends it (policies; the backend recomputes everything).
    for label, fix in [("no fix applied", None)] + ([("top fix applied", top)] if top else []) + \
                      ([("AI fix applied", ai_fix)] if ai_fix else []):
        rep = llm_routes.post_report(ReportRequest(baseline=base, scenario=scen, fix=fix))
        print(f"[report] {label:16s} {rep.source}: {rep.summary_en[:120]}")
        if rep.source != "ai":
            _miss(service, "report", f"{{baseline, scenario{', fix' if fix else ''}}} on {sid} ({label})",
                  "the report shows the template summary")


def main(parse_only: bool = False, services=SERVICES) -> None:
    print(f"DEMO_OFFLINE={'1: cache only, no AI calls' if config.DEMO_OFFLINE else '0: misses call the AI'}"
          f" | services: {', '.join(services)}\n")
    warm_parse(services)
    if not parse_only:
        for service in services:
            warm_service(service)
    print()
    if MISSES:
        print(f"MISSES ({len(MISSES)}): still on a template" + (" (offline: not requested)" if config.DEMO_OFFLINE else ""))
        for service, task, item, why in MISSES:
            print(f"  - [{service}/{task}] {item}: {why}")
        for service in sorted({m[0] for m in MISSES}):
            n = sum(m[0] == service for m in MISSES)
            print(f"  {service}: {n} miss(es)")
        print("Fill them online (after the Gemini quota reset): .venv/Scripts/python -m scripts.warm_cache"
              + (" --parse-only" if parse_only else "")
              + (f" --service {services[0]}" if len(services) == 1 else "") + ", then commit backend/cache/.")
    else:
        print("No misses: everything above is cached.")
    if not config.DEMO_OFFLINE:
        print("Commit backend/cache/ so teammates and the demo machine have it.")


def _args(argv: list[str]) -> tuple[bool, tuple[str, ...]]:
    services = SERVICES
    if "--service" in argv:
        i = argv.index("--service")
        if i + 1 >= len(argv) or argv[i + 1] not in SERVICES:
            raise SystemExit(f"--service needs one of: {', '.join(SERVICES)}")
        services = (argv[i + 1],)
    return "--parse-only" in argv, services


if __name__ == "__main__":
    po, sv = _args(sys.argv[1:])
    main(parse_only=po, services=sv)
