"""Deterministic simulation engine (CLAUDE.md §6.1). No AI, no randomness.

simulate(policy, population=None, assumptions=None) -> SimResult

Each channel (office, mobile unit, online) is evaluated per citizen and memoised by
(channel definition, policy-wide settings, assumptions), so the fix grid and the
robustness check, which re-run near-identical policies ~40 times, stay fast.
The memo never changes a result; it only skips repeated work. It is a small LRU
(_MEMO_MAX entries) of compact per-citizen tuples, so memory stays bounded on a
512 MB host however many policies are tried; outcome dicts are built only for the
winning option of each citizen, in run().
"""
from __future__ import annotations

import threading
from collections import Counter, OrderedDict

from ..models import CitizenOutcome, Policy, SimResult
from . import world
from .assumptions import DEFAULT, Assumptions
from .travel import bus, bus_transfers, car, road, taxi, to_min

DAY_ORDER = {d: i for i, d in enumerate(["sat", "sun", "mon", "tue", "wed", "thu", "fri"])}
WEEKEND = {"fri", "sat"}
REASON_ORDER = ["NO_SMARTPHONE", "LOW_DIGITAL_LITERACY", "TOO_FAR", "NO_TRANSPORT", "TOO_EXPENSIVE",
                "NOT_WHEELCHAIR_ACCESSIBLE", "HOURS_CONFLICT_WORK", "OFFICE_CLOSED_ON_AVAILABLE_DAYS"]
STATUS_RANK = {"served": 0, "hardship": 1, "left_out": 2}

# LRU memo: key -> (pop, opts, fails). One entry = one channel evaluated for the whole population.
# The warm-up (demo path + fix grid + robustness runs) needs ~110 entries; one policy edit adds ~20.
_MEMO: OrderedDict = OrderedDict()
_MEMO_MAX = 150
_MEMO_LOCK = threading.Lock()  # the warm-up thread and request threads share the memo

# A feasible option is a compact tuple (built once per citizen and channel, kept in the memo):
#   (key, served, mode, bus_transfers, visit_day, travel_minutes, cost_jd, hours_lost, work_hours_missed, reasons)
# `key` orders options (lower is better); the channel itself is known from where the option came from.
K, SERVED, MODE, TRANSFERS, DAY, TRAVEL, COST, HOURS, WORK, REASONS = range(10)
_EMPTY: frozenset = frozenset()
_INTERN: dict = {}  # shared reason tuples / failure sets, so 1,000 citizens don't each hold their own copy


def _intern(x):
    return _INTERN.setdefault(x, x)


def _sorted_reasons(rs) -> tuple[str, ...]:
    return _intern(tuple(sorted(set(rs), key=REASON_ORDER.index)))


def _fails(rs) -> frozenset:
    return _intern(frozenset(rs)) if rs else _EMPTY


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


def _terms(policy: Policy) -> tuple:
    """The per-citizen policy terms (group protections), hashable for the memo key."""
    return (tuple(sorted(set(policy.appointment_exempt_groups))), tuple(sorted(policy.fee_discounts.items())),
            tuple(sorted((tuple(sorted(set(v.groups))), v.amount_jd) for v in policy.transport_vouchers)),
            policy.hybrid_pickup)


def _channel_key(ch: dict, policy: Policy) -> tuple:
    if ch["kind"] == "online":
        return ("online", policy.fee_jd, tuple(sorted(policy.fee_discounts.items())))
    return (ch["kind"], ch["id"], ch["dest"], ch["accessible"], ch["appointment"], ch["schedule"],
            policy.fee_jd, policy.visits_required, _terms(policy))


# -------------------------------------------------------------- per citizen

def _fee(c: dict, policy: Policy) -> float:
    """The fee this citizen pays: fee_jd minus their largest group discount (percent)."""
    d = max((policy.fee_discounts.get(t, 0.0) for t in c["tags"]), default=0.0)
    return policy.fee_jd * (1 - min(max(d, 0.0), 100.0) / 100)


def _voucher(c: dict, policy: Policy) -> float:
    """JD of bus/taxi fare covered per round trip for this citizen (their largest voucher)."""
    tags = set(c["tags"])
    return max((v.amount_jd for v in policy.transport_vouchers if tags & set(v.groups)), default=0.0)


def _online_ability(c: dict) -> tuple[bool, list[str]]:
    reasons = []
    if not c["has_smartphone"]:
        reasons.append("NO_SMARTPHONE")
    if c["digital_literacy"] == "low":
        reasons.append("LOW_DIGITAL_LITERACY")
    return not reasons, reasons


def _key(ch, burden, flags, day, mode, a) -> tuple:
    """Option order: served before hardship, then lower burden, fewer hardship flags, online before in person,
    channel id, day, mode."""
    served = burden < a.HARDSHIP_THRESHOLD and flags == 0
    return (0 if served else 1, round(burden, 6), flags, 0 if ch["kind"] == "online" else 1, ch["id"],
            DAY_ORDER.get(day, -1), mode)


def _option(ch, *, burden, flags, hours, cost, work, mode, transfers, day, travel, reasons, a, key=None) -> tuple:
    served = burden < a.HARDSHIP_THRESHOLD and flags == 0
    rs = list(reasons)
    if not served and burden >= a.HARDSHIP_THRESHOLD and travel >= a.LONG_TRIP_MINUTES:
        rs.append("TOO_FAR")
    return (key or _key(ch, burden, flags, day, mode, a), served, mode, transfers, day, round(travel, 1),
            round(cost, 2), round(hours, 2), round(work, 2), _sorted_reasons(rs))


def _eval_online(c: dict, ch: dict, policy: Policy, a: Assumptions):
    ok, reasons = _online_ability(c)
    if not ok and not c["has_helper"]:
        return None, _fails(reasons)
    flags = 0 if ok else 1  # a helper doing it online for you is a hardship
    hours = a.ONLINE_MINUTES / 60
    cost = _fee(c, policy)
    return _option(ch, burden=hours + a.COST_WEIGHT * cost, flags=flags, hours=hours, cost=cost, work=0.0,
                   mode="online", transfers=0, day=None, travel=0.0, reasons=[] if ok else reasons, a=a), _EMPTY


def _modes(c: dict, ch: dict, a: Assumptions, matrix: dict, sides: dict, voucher: float = 0.0):
    """Day-independent travel modes: list of (mode, one-way min, round-trip cost, transfers, uses_helper).
    A transport voucher pays bus or taxi fares up to `voucher` JD per round trip (costs = what the citizen pays)."""
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
        limited = c["mobility"] == "limited"
        t, cost = bus(km, n, limited, a)
        if t > a.MAX_TRAVEL_MINUTES:
            fails.add("TOO_FAR")
        else:
            modes.append(("bus", t, max(0.0, cost - voucher), n, False))
    t, cost = taxi(km, drive_min, a)
    cost = max(0.0, cost - voucher)
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
        return None, _fails({"NOT_WHEELCHAIR_ACCESSIBLE"})
    modes, fails = _modes(c, ch, a, matrix, sides, _voucher(c, policy))
    if not modes:
        # `fails` is never empty here: _modes always tries the taxi, which adds either a mode or a failure reason.
        return None, _fails(fails)

    # Appointments (offices only, rule 3): book online yourself, via a helper (hardship),
    # or make one wasted trip first. Citizens in an exempt group walk in.
    visits = policy.visits_required
    variants = []  # (service minutes at the counter, visits, booking minutes, booking flag, booking reasons)
    appointment = ch["appointment"] and not (set(c["tags"]) & set(policy.appointment_exempt_groups))
    if appointment:
        ok, rs = _online_ability(c)
        if ok:
            variants.append((a.SERVICE_MINUTES, visits, a.ONLINE_MINUTES, 0, []))
        elif c["has_helper"]:
            variants.append((a.SERVICE_MINUTES, visits, a.ONLINE_MINUTES, 1, rs))
        else:
            variants.append((a.SERVICE_MINUTES, visits + 1, 0.0, 1, rs))
    else:
        variants.append((a.SERVICE_MINUTES, visits, 0.0, 0, []))
    if policy.hybrid_pickup:
        # Also possible: apply online (yourself, or a helper does it: hardship), then one short visit to collect the
        # card. The online application replaces any appointment. The citizen takes whichever option is better.
        ok, rs = _online_ability(c)
        if ok or c["has_helper"]:
            variants.append((a.PICKUP_MINUTES, 1, a.ONLINE_MINUTES, 0 if ok else 1, [] if ok else rs))

    helper_from = to_min(a.HELPER_FREE_FROM)
    works = c["works"]
    ws = to_min(c["work_start"]) if works else 0
    we = to_min(c["work_end"]) if works else 0
    cap = a.MAX_WORK_HOURS_MISSED[c["income_band"]]
    fee = _fee(c, policy)

    best_key, best_args, capped = None, None, False
    for S, n_visits, book_min, book_flag, book_reasons in variants:
        outside, during = [], []
        for day, op, cl in ch["schedule"]:
            weekend = day in WEEKEND
            for mode, t, rt_cost, transfers, uses_helper in modes:
                h_free = 0 if (not uses_helper or weekend) else helper_from
                visit_h = (2 * t + S) / 60
                hours = visit_h * n_visits + book_min / 60
                cost = fee + rt_cost * n_visits
                flags = int(uses_helper) + book_flag
                if works and not weekend:
                    arr = max(op, max(we, h_free) + t)  # after work
                    if arr + S <= cl:
                        outside.append((day, mode, t, transfers, hours, cost, 0.0, flags, []))
                    arr = max(op, h_free + t)  # during work
                    if arr + S <= cl and arr - t < we and arr + S + t > ws:
                        work = visit_h * n_visits
                        if work > cap:
                            capped = True
                        else:
                            during.append((day, mode, t, transfers, hours, cost, work, flags + 1,
                                           ["HOURS_CONFLICT_WORK"]))
                else:
                    arr = max(op, h_free + t)
                    if arr + S <= cl:
                        outside.append((day, mode, t, transfers, hours, cost, 0.0, flags, []))
        for day, mode, t, transfers, hours, cost, work, flags, rs in outside or during:  # rule 5
            burden = hours + a.COST_WEIGHT * cost + a.WORK_WEIGHT * work
            k = _key(ch, burden, flags, day, mode, a)
            if best_key is None or k < best_key:  # only the winner is turned into an option tuple
                best_key = k
                best_args = dict(burden=burden, flags=flags, hours=hours, cost=cost, work=work, mode=mode,
                                 transfers=transfers if mode == "bus" else 0, day=day, travel=t,
                                 reasons=book_reasons + rs)
    if best_key is None:
        return None, _fails(fails | ({"HOURS_CONFLICT_WORK"} if capped else {"OFFICE_CLOSED_ON_AVAILABLE_DAYS"}))
    return _option(ch, a=a, key=best_key, **best_args), _EMPTY


def _channel_results(ch: dict, policy: Policy, pop: list[dict], a: Assumptions) -> tuple[list, list]:
    """(opts, fails), index-aligned with pop: the citizen's best option on this channel (or None) and, when
    infeasible, the reasons why. Memoised in a bounded LRU."""
    key = (id(pop), _channel_key(ch, policy), a.key())
    with _MEMO_LOCK:
        hit = _MEMO.get(key)
        if hit is not None:
            _MEMO.move_to_end(key)
            return hit[1], hit[2]
    matrix, sides = world.travel_matrix(), world.sides()
    if ch["kind"] == "online":
        res = [_eval_online(c, ch, policy, a) for c in pop]
    else:
        res = [_eval_in_person(c, ch, policy, a, matrix, sides) for c in pop]
    opts, fails = [r[0] for r in res], [r[1] for r in res]
    with _MEMO_LOCK:
        _MEMO[key] = (pop, opts, fails)  # keep a reference to pop so id(pop) stays unique while cached
        _MEMO.move_to_end(key)
        while len(_MEMO) > _MEMO_MAX:
            _MEMO.popitem(last=False)
    return opts, fails


HOME = {"kind": "home", "id": "home_visit", "name_ar": "زيارة منزلية", "name_en": "Home visit"}


def _allocate_home_visits(policy: Policy, pop: list[dict], bests: list, best_ch: list, a: Assumptions) -> None:
    """Home-visit slots go to eligible citizens who are worst off without one: left out first, then the heaviest
    hardship (ties by id). A slot is used only if the home visit is better for that citizen. Deterministic."""
    hv = policy.home_visits
    if not hv or hv.slots <= 0 or policy.online_only:
        return
    groups = set(hv.groups)
    queue = sorted((0 if b is None else 1, -(b[K][1] if b else 0.0), c["id"], i)
                   for i, (c, b) in enumerate(zip(pop, bests))
                   if groups & set(c["tags"]) and (b is None or not b[SERVED]))
    for *_, i in queue[:hv.slots]:
        c = pop[i]
        hours = a.HOME_VISIT_MINUTES / 60 * policy.visits_required
        cost = _fee(c, policy)
        opt = _option(HOME, burden=hours + a.COST_WEIGHT * cost, flags=0, hours=hours, cost=cost, work=0.0,
                      mode="home", transfers=0, day=None, travel=0.0, reasons=[], a=a)
        if bests[i] is None or opt[K] < bests[i][K]:
            bests[i], best_ch[i] = opt, HOME


# ------------------------------------------------------------------- public

def run(policy: Policy, population: list[dict] | None = None, assumptions: Assumptions | None = None) -> list[dict]:
    """Fast path: list of outcome dicts, index-aligned with the population."""
    pop = population if population is not None else world.population()
    a = assumptions or DEFAULT
    per_channel = [(ch, *_channel_results(ch, policy, pop, a)) for ch in _channels(policy)]
    bests, best_ch, fails_by = [], [], []
    for i in range(len(pop)):
        best, bch, reasons = None, None, set()
        for ch, opts, fails in per_channel:
            if fails[i]:
                reasons |= fails[i]
            opt = opts[i]
            if opt is not None and (best is None or opt[K] < best[K]):
                best, bch = opt, ch
        bests.append(best)
        best_ch.append(bch)
        fails_by.append(reasons)
    _allocate_home_visits(policy, pop, bests, best_ch, a)
    out = []
    for c, best, ch, reasons in zip(pop, bests, best_ch, fails_by):
        if best is None:
            out.append({"citizen_id": c["id"], "status": "left_out", "channel": None, "channel_name_ar": None,
                        "channel_name_en": None, "mode": None, "bus_transfers": 0, "visit_day": None,
                        "travel_minutes": 0.0, "cost_jd": 0.0, "hours_lost": 0.0, "work_hours_missed": 0.0,
                        "reasons": list(_sorted_reasons(reasons or {"OFFICE_CLOSED_ON_AVAILABLE_DAYS"}))})
        else:
            out.append({"status": "served" if best[SERVED] else "hardship", "channel": ch["id"],
                        "channel_name_ar": ch["name_ar"], "channel_name_en": ch["name_en"], "mode": best[MODE],
                        "bus_transfers": best[TRANSFERS], "visit_day": best[DAY], "travel_minutes": best[TRAVEL],
                        "cost_jd": best[COST], "hours_lost": best[HOURS], "work_hours_missed": best[WORK],
                        "reasons": list(best[REASONS]),  # a fresh list: callers may mutate it
                        "citizen_id": c["id"]})
    return out


def _count_reasons(outcomes) -> dict[str, int]:
    n = Counter(r for o in outcomes for r in set(o["reasons"]))
    return dict(sorted(n.items(), key=lambda kv: (-kv[1], kv[0])))


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
        "n_home_visits": sum(o.get("channel") == "home_visit" for o in outcomes),
        # People per reason (someone with two reasons counts under both), most common first, then by name.
        "left_out_by_reason": _count_reasons(o for o in outcomes if o["status"] == "left_out"),
        "hardship_by_reason": _count_reasons(o for o in outcomes if o["status"] == "hardship"),
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
