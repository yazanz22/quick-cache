"""Pick hero citizens for a service's demo path and write data/scenarios/heroes.json (CLAUDE.md §10).

id_renewal (default): 4 heroes. A hero must get worse under the demo scenario and better again under the engine's
top fix, so the "she's served now" moment really happens. Criteria are relaxed step by step if nobody matches exactly.

everyday_travel: 3 heroes (a long car commute, a low-income bus commuter with a change of bus, a student by bus).
First choice: worse off in status under the demo scenario than today and not worse than today with the top fix.
If nobody in a profile changes status (e.g. bus riders already priced out today), the fallback is: pays more each
month under the scenario and the top fix improves their status; the entry then says "worse_status": false.

Each run only replaces the heroes of its own service; the other service's entries are kept as they are.
Re-run after the population or scenarios change.

    python -m scripts.pick_heroes [scenario_id]
    python -m scripts.pick_heroes --service everyday_travel [scenario_id]
"""
import json
import sys

from app.config import SCENARIOS_DIR
from app.sim import engine, fixgrid, world
from app.sim.engine import STATUS_RANK

WANTED = [
    ("Elderly woman in east Amman with no car; a family member helps her",
     [lambda c: "elderly" in c["tags"] and c["gender"] == "f" and not c["has_car"] and c["has_helper"] and c["area"] == "marka",
      lambda c: "elderly" in c["tags"] and c["gender"] == "f" and not c["has_car"] and c["has_helper"],
      lambda c: "elderly" in c["tags"] and not c["has_car"]]),
    ("Wheelchair user",
     [lambda c: c["mobility"] == "wheelchair" and c["area"] == "wehdat",
      lambda c: c["mobility"] == "wheelchair",
      lambda c: c["mobility"] != "none"]),
    ("Factory worker on an early shift",
     [lambda c: c["works"] and c["work_start"] == "07:00" and c["area"] == "tabarbour",
      lambda c: c["works"] and c["work_start"] == "07:00",
      lambda c: c["works"] and "offline" in c["tags"]]),
    ("Offline resident with nobody to help",
     [lambda c: "offline" in c["tags"] and not c["has_helper"] and world.areas()[c["area"]]["side"] == "east",
      lambda c: "offline" in c["tags"] and not c["has_helper"]]),
]


NOTE_AR = {
    "Elderly woman in east Amman with no car; a family member helps her": "مسنّة في شرق عمّان بلا سيارة، يساعدها أحد أفراد عائلتها",
    "Wheelchair user": "مستخدم كرسي متحرك",
    "Factory worker on an early shift": "عامل في وردية صباحية مبكرة",
    "Offline resident with nobody to help": "مقيم غير متصل رقمياً وليس لديه من يساعده",
}


def profile(c: dict) -> str:
    """Factual one-liner, so the demo script never describes a hero wrongly."""
    where = c.get("neighbourhood") or c["area"]
    bits = [f"{c['age']}{c['gender']}", where, f"mobility {c['mobility']}", "car" if c["has_car"] else "no car",
            "smartphone" if c["has_smartphone"] else "no smartphone", f"digital literacy {c['digital_literacy']}",
            f"works {c['work_start']}-{c['work_end']}" if c["works"] else "not working",
            f"helper: {c['helper_relation_en']}" if c["has_helper"] else "no helper"]
    return ", ".join(bits)


def main(scenario_id: str | None = None) -> None:
    scenario_id = scenario_id or world.demo_scenario_id()
    pop = world.population()
    base = engine.run(world.scenario_policy("baseline"))
    scen = engine.run(world.scenario_policy(scenario_id))
    fix = engine.run(fixgrid.top_fixes(world.scenario_policy(scenario_id))[0].policy)
    rank = lambda o: STATUS_RANK[o["status"]]
    heroes, used = [], set()
    for note, tiers in WANTED:
        pick = None
        for strict in (True, False):  # first: worse in scenario AND better with the fix; then: just worse
            for test in tiers:
                for i, c in enumerate(pop):
                    if c["id"] in used or not test(c) or rank(scen[i]) <= rank(base[i]):
                        continue
                    if strict and rank(fix[i]) >= rank(scen[i]):
                        continue
                    pick = (i, c, strict)
                    break
                if pick:
                    break
            if pick:
                break
        if not pick:
            print("no match for:", note)
            continue
        i, c, strict = pick
        used.add(c["id"])
        heroes.append({"citizen_id": c["id"], "wanted": note, "note_en": note, "note_ar": NOTE_AR.get(note), "profile": profile(c), "name_en": c["name_en"], "area": c["area"],
                       "baseline": base[i]["status"], "scenario": scen[i]["status"], "with_top_fix": fix[i]["status"],
                       "recovers_with_fix": strict})
        print(f"{c['id']} {c['name_en']:12s} {c['area']:16s} {base[i]['status']:>9} -> {scen[i]['status']:<9} -> fix: {fix[i]['status']:<9} | {profile(c)}")
    _write("id_renewal", heroes, scenario_id)


def _write(service: str, heroes: list[dict], scenario_id: str | None = None) -> None:
    """Replace this service's heroes in heroes.json and keep the other service's entries as they are.
    Entries without "service" are id_renewal heroes; the top-level "scenario" is the id_renewal demo scenario."""
    path = SCENARIOS_DIR / "heroes.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    keep = [h for h in old.get("heroes", []) if h.get("service", "id_renewal") != service]
    out = {"scenario": scenario_id if service == "id_renewal" else old.get("scenario", world.demo_scenario_id()),
           "_note": "Generated by scripts/pick_heroes.py. Synthetic citizens.",
           "heroes": heroes + keep if service == "id_renewal" else keep + heroes}
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------------- everyday_travel

def _when(o: dict) -> tuple[str, str]:
    return ("every workday", "كل يوم عمل") if o["days_per_week"] >= 5 else ("once a week", "مرة في الأسبوع")


def _change_of_bus(n: int) -> tuple[str, str]:
    return {0: ("", ""), 1: (", with one change of bus", "، مع تبديل حافلة واحدة"),
            2: (", with two changes of bus", "، مع تبديل حافلتين")}[n]


def _note_car(c: dict, o: dict) -> tuple[str, str]:
    en_when, ar_when = _when(o)
    f = c["gender"] == "f"
    return (f"Commutes by car to {o['channel_name_en']} {en_when}, a long drive each way",
            f"{'تتنقّل بسيارتها' if f else 'يتنقّل بسيارته'} إلى {o['channel_name_ar']} {ar_when}، في رحلة طويلة ذهاباً وإياباً")


def _note_bus(c: dict, o: dict) -> tuple[str, str]:
    en_when, ar_when = _when(o)
    en_ch, ar_ch = _change_of_bus(o["bus_transfers"])
    f = c["gender"] == "f"
    return (f"Low-income resident who takes the bus to {o['channel_name_en']} {en_when}{en_ch}",
            f"{'من ذوات' if f else 'من ذوي'} الدخل المحدود، {'تتنقّل' if f else 'يتنقّل'} بالحافلة إلى "
            f"{o['channel_name_ar']} {ar_when}{ar_ch}")


def _note_student(c: dict, o: dict) -> tuple[str, str]:
    en_ch, ar_ch = _change_of_bus(o["bus_transfers"])
    f = c["gender"] == "f"
    return (f"Student who takes the bus to {o['channel_name_en']} every weekday{en_ch}",
            f"{'طالبة تذهب' if f else 'طالب يذهب'} بالحافلة إلى {o['channel_name_ar']} كل يوم دراسي{ar_ch}")


LONG_HUBS = {"trip:work_sahab", "trip:work_airport"}
# (wanted, tiers of tests on (citizen, outcome under the scenario), sort key among matches, note builder)
TRAVEL_WANTED = [
    ("Long car commute, middle or low income",
     [lambda c, o: o["mode"] == "car" and o["channel"] in LONG_HUBS and c["income_band"] in ("low", "middle"),
      lambda c, o: o["mode"] == "car" and o["purpose"] == "work" and c["income_band"] in ("low", "middle")],
     lambda c, o: -o["travel_minutes"], _note_car),
    ("Low-income bus commuter with a change of bus",
     [lambda c, o: o["mode"] == "bus" and o["purpose"] == "work" and "low_income" in c["tags"]
      and o["bus_transfers"] >= 1 and o["travel_minutes"] <= 90,
      lambda c, o: o["mode"] == "bus" and o["purpose"] == "work" and "low_income" in c["tags"] and o["bus_transfers"] >= 1],
     lambda c, o: o["travel_minutes"], _note_bus),
    ("Student by bus",
     [lambda c, o: o["mode"] == "bus" and o["purpose"] == "university" and o["bus_transfers"] >= 1
      and o["travel_minutes"] <= 90,
      lambda c, o: o["mode"] == "bus" and o["purpose"] == "university"],
     lambda c, o: o["travel_minutes"], _note_student),
]


def travel_profile(c: dict, o: dict) -> str:
    """Factual one-liner (no occupation): the trip, how, how often, how long."""
    where = c.get("neighbourhood") or c["area"]
    transfers = f" ({o['bus_transfers']} transfer{'s' if o['bus_transfers'] > 1 else ''})" if o["bus_transfers"] else ""
    return (f"{c['age']}{c['gender']}, {where}, income {c['income_band']}, {'car' if c['has_car'] else 'no car'}, "
            f"mobility {c['mobility']}, {o['purpose']} trip to {o['channel_name_en']} {o['days_per_week']} days/week "
            f"by {o['mode']}{transfers}, {o['travel_minutes']:g} min each way")


def main_travel(scenario_id: str | None = None) -> None:
    service = "everyday_travel"
    scenario_id = scenario_id or world.demo_scenario_id(service)
    pop = world.population()
    base = engine.run(world.scenario_policy(world.baseline_scenario_id(service)))
    scen_policy = world.scenario_policy(scenario_id)
    scen = engine.run(scen_policy)
    top = fixgrid.top_fixes(scen_policy)[0]
    fix = engine.run(top.policy)
    rank = lambda o: STATUS_RANK[o["status"]]
    strict_ok = lambda i: rank(scen[i]) > rank(base[i]) and rank(fix[i]) <= rank(base[i])
    relaxed_ok = lambda i: (scen[i]["extra_jd_month"] or 0) > 0 and rank(fix[i]) < rank(scen[i])
    heroes, used = [], set()
    for wanted, tiers, order, note in TRAVEL_WANTED:
        pick = None
        for strict in (True, False):
            for test in tiers:
                found = [i for i, c in enumerate(pop) if c["id"] not in used and scen[i]["purpose"]
                         and test(c, scen[i]) and (strict_ok(i) if strict else relaxed_ok(i))]
                if found:
                    pick = (min(found, key=lambda j: (order(pop[j], scen[j]), pop[j]["id"])), strict)
                    break
            if pick:
                break
        if not pick:
            print("no match for:", wanted)
            continue
        i, strict = pick
        c, o = pop[i], scen[i]
        used.add(c["id"])
        note_en, note_ar = note(c, o)
        heroes.append({
            "citizen_id": c["id"], "service": service, "scenario_id": scenario_id, "wanted": wanted,
            "note_en": note_en, "note_ar": note_ar, "profile": travel_profile(c, o), "name_en": c["name_en"],
            "area": c["area"], "baseline": base[i]["status"], "scenario": o["status"], "with_top_fix": fix[i]["status"],
            "top_fix": top.id,
            "monthly_cost_jd": {"baseline": base[i]["cost_jd"], "scenario": o["cost_jd"], "with_top_fix": fix[i]["cost_jd"]},
            "income_share_pct": {"baseline": base[i]["income_share_pct"], "scenario": o["income_share_pct"],
                                 "with_top_fix": fix[i]["income_share_pct"]},
            "worse_status": rank(o) > rank(base[i]), "recovers_with_fix": rank(fix[i]) <= rank(base[i]),
        })
        print(f"{c['id']} {c['name_en']:12s} {base[i]['status']:>9} -> {o['status']:<9} -> fix: {fix[i]['status']:<9}"
              f" | {base[i]['cost_jd']} -> {o['cost_jd']} -> {fix[i]['cost_jd']} JD/month"
              f" | {'strict' if strict else 'fallback'} | {travel_profile(c, o)}")
    _write(service, heroes)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--service"]:
        service, args = args[1], args[2:]
        (main_travel if service == "everyday_travel" else main)(*args)
    else:
        main(*args)
