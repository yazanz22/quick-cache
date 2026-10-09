"""Deterministic simulation engine (CLAUDE.md §6.1). No AI, no randomness.

simulate(policy, population=None, assumptions=None) -> SimResult

Each channel (office, mobile unit, online) is evaluated per citizen and memoised by
(channel definition, policy-wide settings, assumptions), so the fix grid and the
robustness check, which re-run near-identical policies ~40 times, stay fast.
The memo never changes a result; it only skips repeated work.
"""
from __future__ import annotations

from ..models import CitizenOutcome, Policy, SimResult
from . import world
from .assumptions import DEFAULT, Assumptions
from .travel import bus, bus_transfers, car, road, taxi, to_min

DAY_ORDER = {d: i for i, d in enumerate(["sat", "sun", "mon", "tue", "wed", "thu", "fri"])}
WEEKEND = {"fri", "sat"}
REASON_ORDER = ["NO_SMARTPHONE", "LOW_DIGITAL_LITERACY", "TOO_FAR", "NO_TRANSPORT", "TOO_EXPENSIVE",
                "NOT_WHEELCHAIR_ACCESSIBLE", "HOURS_CONFLICT_WORK", "OFFICE_CLOSED_ON_AVAILABLE_DAYS"]
STATUS_RANK = {"served": 0, "hardship": 1, "left_out": 2}

_MEMO: dict = {}
_MEMO_MAX = 4000


def _sorted_reasons(rs) -> list[str]:
    return sorted(set(rs), key=REASON_ORDER.index)


# ------------------------------------------------------------------ channels

def _channels(policy: Policy) -> list[dict]:
    """Normalise the policy into channel dicts. online_only => online is the only channel."""
    areas, sites = world.areas(), world.sites()
    chans = []
    if policy.online_enabled or policy.online_only:
        chans.append({"kind": "online", "id": "online", "name_ar": "أونلاين", "name_en": "Online"})
    if policy.online_only:
        return chans
    for o in policy.offices:
        s = sites[o.site_id]
        ar = areas[s["area"]]
        chans.append({
            "kind": "office", "id": o.id, "dest": o.site_id, "lat": s["lat"], "lng": s["lng"], "area": s["area"],
            "accessible": o.wheelchair_accessible, "appointment": policy.appointment_required,
            "schedule": tuple(sorted((d, to_min(h[0]), to_min(h[1])) for d, h in o.schedule.items())),
            # Real CSPD offices carry their own name; generic sites are named after their area.
            "name_ar": s["name_ar"] if s.get("real") else f"مكتب الأحوال المدنية في {ar['name_ar']}",
            "name_en": s["name_en"] if s.get("real") else f"Civil Status office in {ar['name_en']}",
        })
    for m in policy.mobile_units:
        ar = areas[m.area]
        chans.append({
            "kind": "van", "id": f"mobile:{m.area}:{m.day}", "dest": f"area:{m.area}", "lat": ar["lat"], "lng": ar["lng"],
            "area": m.area, "accessible": True, "appointment": False,
            "schedule": ((m.day, to_min(m.open), to_min(m.close)),),
            "name_ar": f"الوحدة المتنقلة في {ar['name_ar']} يوم {world.DAY_AR[m.day]}",
            "name_en": f"Mobile unit in {ar['name_en']} on {world.DAY_EN[m.day]}",
        })
    return chans


def _channel_key(ch: dict, policy: Policy) -> tuple:
    if ch["kind"] == "online":
        return ("online", policy.fee_jd)
    return (ch["kind"], ch["id"], ch["dest"], ch["accessible"], ch["appointment"], ch["schedule"],
            policy.fee_jd, policy.visits_required)


# -------------------------------------------------------------- per citizen

def _online_ability(c: dict) -> tuple[bool, list[str]]:
    reasons = []
    if not c["has_smartphone"]:
        reasons.append("NO_SMARTPHONE")
    if c["digital_literacy"] == "low":
        reasons.append("LOW_DIGITAL_LITERACY")
    return not reasons, reasons


def _option(ch, *, burden, flags, hours, cost, work, mode, transfers, day, travel, reasons, a):
    served = burden < a.HARDSHIP_THRESHOLD and flags == 0
    rs = list(reasons)
    if not served and burden >= a.HARDSHIP_THRESHOLD and travel >= a.LONG_TRIP_MINUTES:
        rs.append("TOO_FAR")
    key = (0 if served else 1, round(burden, 6), flags, 0 if ch["kind"] == "online" else 1, ch["id"],
           DAY_ORDER.get(day, -1), mode)
    return {
        "key": key, "status": "served" if served else "hardship", "channel": ch["id"],
        "channel_name_ar": ch["name_ar"], "channel_name_en": ch["name_en"], "mode": mode,
        "bus_transfers": transfers, "visit_day": day, "travel_minutes": round(travel, 1),
        "cost_jd": round(cost, 2), "hours_lost": round(hours, 2), "work_hours_missed": round(work, 2),
        "reasons": _sorted_reasons(rs),
    }


def _eval_online(c: dict, ch: dict, policy: Policy, a: Assumptions):
    ok, reasons = _online_ability(c)
    if not ok and not c["has_helper"]:
        return None, set(reasons)
    flags = 0 if ok else 1  # a helper doing it online for you is a hardship
    hours = a.ONLINE_MINUTES / 60
    cost = policy.fee_jd
    return _option(ch, burden=hours + a.COST_WEIGHT * cost, flags=flags, hours=hours, cost=cost, work=0.0,
                   mode="online", transfers=0, day=None, travel=0.0, reasons=[] if ok else reasons, a=a), set()


def _modes(c: dict, ch: dict, a: Assumptions, matrix: dict, sides: dict):
    """Day-independent travel modes: list of (mode, one-way min, round-trip cost, transfers, uses_helper)."""
    fails: set[str] = set()
    km, drive_min = road(c, ch["dest"], ch["lat"], ch["lng"], matrix, a)
    modes = []
    if c["has_car"] or c["has_helper"]:
        t, cost = car(km, drive_min, a)
        if t > a.MAX_TRAVEL_MINUTES:
            fails.add("TOO_FAR")
        else:
            if c["has_car"]:
                modes.append(("car", t, cost, 0, False))
            if c["has_helper"]:
                modes.append(("helper_car", t, cost, 0, True))
    if c["mobility"] != "wheelchair":
        n = bus_transfers(c["area"], ch["area"], sides)
        t, cost = bus(km, n, c["mobility"] == "limited", a)
        if t > a.MAX_TRAVEL_MINUTES:
            fails.add("TOO_FAR")
        else:
            modes.append(("bus", t, cost, n, False))
    t, cost = taxi(km, drive_min, a)
    if cost > a.TAXI_MAX_JD[c["income_band"]]:
        fails.add("TOO_EXPENSIVE")
    elif t > a.MAX_TRAVEL_MINUTES:
        fails.add("TOO_FAR")
    else:
        modes.append(("taxi", t, cost, 0, False))
    if not modes and not c["has_car"] and not c["has_helper"] and c["mobility"] == "wheelchair":
        fails.add("NO_TRANSPORT")
    return modes, fails


def _eval_in_person(c: dict, ch: dict, policy: Policy, a: Assumptions, matrix: dict, sides: dict):
    if c["mobility"] == "wheelchair" and not ch["accessible"]:
        return None, {"NOT_WHEELCHAIR_ACCESSIBLE"}
    modes, fails = _modes(c, ch, a, matrix, sides)
    if not modes:
        return None, fails or {"NO_TRANSPORT"}

    # Appointments (offices only, rule 3): book online yourself, via a helper (hardship),
    # or make one wasted trip first.
    visits = policy.visits_required
    book_flag, book_reasons, book_min = 0, [], 0.0
    if ch["appointment"]:
        ok, rs = _online_ability(c)
        book_min = a.ONLINE_MINUTES
        if not ok:
            book_flag, book_reasons = 1, rs
            if not c["has_helper"]:
                visits += 1
                book_min = 0.0

    helper_from = to_min(a.HELPER_FREE_FROM)
    works = c["works"]
    ws = to_min(c["work_start"]) if works else 0
    we = to_min(c["work_end"]) if works else 0
    S = a.SERVICE_MINUTES
    cap = a.MAX_WORK_HOURS_MISSED[c["income_band"]]
    fee = policy.fee_jd

    outside, during = [], []
    capped = False
    for day, op, cl in ch["schedule"]:
        weekend = day in WEEKEND
        for mode, t, rt_cost, transfers, uses_helper in modes:
            h_free = 0 if (not uses_helper or weekend) else helper_from
            visit_h = (2 * t + S) / 60
            hours = visit_h * visits + book_min / 60
            cost = fee + rt_cost * visits
            flags = int(uses_helper) + book_flag
            if works and not weekend:
                arr = max(op, max(we, h_free) + t)  # after work
                if arr + S <= cl:
                    outside.append((day, mode, t, transfers, hours, cost, 0.0, flags, []))
                arr = max(op, h_free + t)  # during work
                if arr + S <= cl and arr - t < we and arr + S + t > ws:
                    work = visit_h * visits
                    if work > cap:
                        capped = True
                    else:
                        during.append((day, mode, t, transfers, hours, cost, work, flags + 1, ["HOURS_CONFLICT_WORK"]))
            else:
                arr = max(op, h_free + t)
                if arr + S <= cl:
                    outside.append((day, mode, t, transfers, hours, cost, 0.0, flags, []))

    cands = outside or during  # rule 5: an outside-work slot always wins if one exists
    if not cands:
        return None, fails | ({"HOURS_CONFLICT_WORK"} if capped else {"OFFICE_CLOSED_ON_AVAILABLE_DAYS"})
    best = None
    for day, mode, t, transfers, hours, cost, work, flags, rs in cands:
        burden = hours + a.COST_WEIGHT * cost + a.WORK_WEIGHT * work
        opt = _option(ch, burden=burden, flags=flags, hours=hours, cost=cost, work=work, mode=mode,
                      transfers=transfers if mode == "bus" else 0, day=day, travel=t,
                      reasons=book_reasons + rs, a=a)
        if best is None or opt["key"] < best["key"]:
            best = opt
    return best, set()


def _channel_results(ch: dict, policy: Policy, pop: list[dict], a: Assumptions) -> list:
    key = (id(pop), _channel_key(ch, policy), a.key())
    hit = _MEMO.get(key)
    if hit is not None:
        return hit[1]
    matrix, sides = world.travel_matrix(), world.sides()
    if ch["kind"] == "online":
        res = [_eval_online(c, ch, policy, a) for c in pop]
    else:
        res = [_eval_in_person(c, ch, policy, a, matrix, sides) for c in pop]
    if len(_MEMO) > _MEMO_MAX:
        _MEMO.clear()
    _MEMO[key] = (pop, res)  # keep a reference to pop so id(pop) stays unique
    return res


# ------------------------------------------------------------------- public

def run(policy: Policy, population: list[dict] | None = None, assumptions: Assumptions | None = None) -> list[dict]:
    """Fast path: list of outcome dicts, index-aligned with the population."""
    pop = population if population is not None else world.population()
    a = assumptions or DEFAULT
    per_channel = [_channel_results(ch, policy, pop, a) for ch in _channels(policy)]
    out = []
    for i, c in enumerate(pop):
        best, reasons = None, set()
        for res in per_channel:
            opt, fails = res[i]
            reasons |= fails
            if opt is not None and (best is None or opt["key"] < best["key"]):
                best = opt
        if best is None:
            out.append({"citizen_id": c["id"], "status": "left_out", "channel": None, "channel_name_ar": None,
                        "channel_name_en": None, "mode": None, "bus_transfers": 0, "visit_day": None,
                        "travel_minutes": 0.0, "cost_jd": 0.0, "hours_lost": 0.0, "work_hours_missed": 0.0,
                        "reasons": _sorted_reasons(reasons or {"OFFICE_CLOSED_ON_AVAILABLE_DAYS"})})
        else:
            o = {k: v for k, v in best.items() if k != "key"}
            o["citizen_id"] = c["id"]
            out.append(o)
    return out


def summarize(outcomes: list[dict], pop: list[dict] | None = None) -> tuple[dict, dict]:
    pop = pop if pop is not None else world.population()
    n = len(outcomes)
    counts = {"served": 0, "hardship": 0, "left_out": 0}
    groups = {g: {"served": 0, "hardship": 0, "left_out": 0, "n": 0} for g in ["all"] + world.ALL_GROUPS}
    hours = cost = 0.0
    reached = 0
    for c, o in zip(pop, outcomes):
        st = o["status"]
        counts[st] += 1
        if st != "left_out":
            reached += 1
            hours += o["hours_lost"]
            cost += o["cost_jd"]
        for g in ["all"] + [t for t in c["tags"] if t in groups]:
            groups[g][st] += 1
            groups[g]["n"] += 1
    pct = lambda x, d: round(100.0 * x / d, 1) if d else 0.0
    kpis = {
        "pct_served": pct(counts["served"], n), "pct_hardship": pct(counts["hardship"], n),
        "pct_left_out": pct(counts["left_out"], n),
        "avg_hours_lost": round(hours / reached, 2) if reached else 0.0,
        "avg_cost_jd": round(cost / reached, 2) if reached else 0.0,
        "n": n, "n_served": counts["served"], "n_hardship": counts["hardship"], "n_left_out": counts["left_out"],
    }
    by_group = {g: {"served": pct(v["served"], v["n"]), "hardship": pct(v["hardship"], v["n"]),
                    "left_out": pct(v["left_out"], v["n"]), "n": v["n"]} for g, v in groups.items()}
    return kpis, by_group


def simulate(policy: Policy, population: list[dict] | None = None,
             assumptions: Assumptions | None = None) -> SimResult:
    pop = population if population is not None else world.population()
    outcomes = run(policy, pop, assumptions)
    kpis, by_group = summarize(outcomes, pop)
    return SimResult(outcomes=[CitizenOutcome.model_validate(o) for o in outcomes], kpis=kpis, by_group=by_group)
