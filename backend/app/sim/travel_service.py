"""Everyday travel under fuel prices, fares and cash support (service "everyday_travel"). Deterministic, no AI.

Every synthetic citizen has at most one regular trip (data/daily_trips.json, made by seed_daily.py): workers to a work
hub and students to a university on workdays, other adults 25+ to their nearest public hospital once a week. This
module prices that trip per month under a policy and compares it with the citizen's income:

- Mode by profile, as in the old everyday-trips module: own car if they have one; wheelchair users go in a helper's car
  (if they have a helper) or by taxi; everyone else by bus. We don't model switching modes when prices change (a
  driver who would take the bus at +50% still drives): that is the next module, not this one.
- Distances and free-flow times from the OSRM hub matrix (data/hub_matrix.json) x TRAFFIC_FACTOR, through the same
  travel model as the ID-renewal engine (travel.py, frozen assumptions).
- Round-trip cost at fuel change `pct`: car / helper_car 2*km*CAR_COST_PER_KM_JD*(1 + pct/100*FUEL_SHARE_OF_CAR_COST);
  bus 2*(transfers+1)*BUS_FARE_JD*(1 + bus_pct/100); taxi 2*(TAXI_BASE_JD + km*TAXI_PER_KM_JD*(1 + taxi_pct/100)).
  Fares follow fuel by their pass-through share unless the policy sets them (0 = a freeze). Transport vouchers cut the
  bus/taxi round-trip fare (floor 0), never car costs. Cash support (monthly) comes off the monthly cost (floor 0).
- Status by the share of the band's representative income spent on the trip each month: below
  TRANSPORT_SHARE_SQUEEZED "served" (fine), from it "hardship" (squeezed), from TRANSPORT_SHARE_PRICED_OUT "left_out"
  (priced out). Citizens with no regular trip are "served" at zero cost.

run() returns outcome dicts with the same keys as engine.run plus the travel fields of models.CitizenOutcome.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

from ..models import Policy
from . import world
from .assumptions import DEFAULT, Assumptions
from .travel import bus, bus_transfers, car, haversine_km, road, taxi

PURPOSES = ("work", "university", "hospital")
MODES = ("car", "helper_car", "bus", "taxi")
NO_TRIP = {"id": "no_regular_trip", "name_ar": "لا رحلة منتظمة", "name_en": "No regular trip"}

# Per-citizen trip geometry (policy-independent), by (id(pop), assumptions): a handful of entries (default + the
# 6 robustness perturbations). Per-policy results, by (id(pop), travel terms, assumptions): compact tuples, LRU.
_BASE: OrderedDict = OrderedDict()
_BASE_MAX = 16
_MEMO: OrderedDict = OrderedDict()
_MEMO_MAX = 80
_LOCK = threading.Lock()

# A compact per-citizen result: (status, cost_jd, hours_lost, extra_jd, share_pct, cash_jd) or None (no trip).
STATUS, COST, HOURS, EXTRA, SHARE, CASH = range(6)


def mode_for(c: dict) -> str:
    """How a citizen makes their regular trip (no switching with price)."""
    if c["has_car"]:
        return "car"
    if c["mobility"] == "wheelchair":
        return "helper_car" if c["has_helper"] else "taxi"
    return "bus"


def hub_area(h: dict) -> str:
    """The engine area nearest a hub (for bus transfers). Ties by area id."""
    areas = world.areas()
    return min(areas, key=lambda k: (haversine_km(h["lat"], h["lng"], areas[k]["lat"], areas[k]["lng"]), k))


def terms(policy: Policy) -> tuple:
    """The travel levers of a policy, hashable (memo key). Everything else in the policy is ignored."""
    return (float(policy.fuel_price_change_pct), policy.bus_fare_change_pct, policy.taxi_fare_change_pct,
            tuple(sorted((tuple(sorted(set(s.groups))), float(s.amount_jd_month)) for s in policy.cash_support)),
            tuple(sorted((tuple(sorted(set(v.groups))), float(v.amount_jd)) for v in policy.transport_vouchers)))


DEFAULT_TERMS = (0.0, None, None, (), ())


def _fare_pcts(t: tuple, a: Assumptions) -> tuple[float, float, float]:
    pct, bus_pct, taxi_pct = t[0], t[1], t[2]
    return (pct, pct * a.BUS_FARE_FUEL_PASS_THROUGH if bus_pct is None else bus_pct,
            pct * a.TAXI_FARE_FUEL_PASS_THROUGH if taxi_pct is None else taxi_pct)


def _largest(entries: tuple, tags: set) -> float:
    return max((amt for groups, amt in entries if tags & set(groups)), default=0.0)


def round_trip_cost(mode: str, km: float, transfers: int, t: tuple, tags: set, a: Assumptions) -> float:
    """What the citizen pays for one round trip under travel terms `t` (see the module docstring)."""
    pct, bus_pct, taxi_pct = _fare_pcts(t, a)
    if mode in ("car", "helper_car"):
        return 2 * km * a.CAR_COST_PER_KM_JD * (1 + pct / 100 * a.FUEL_SHARE_OF_CAR_COST)
    voucher = _largest(t[4], tags)
    if mode == "bus":
        fare = 2 * (transfers + 1) * a.BUS_FARE_JD * (1 + bus_pct / 100)
    else:
        fare = 2 * (a.TAXI_BASE_JD + km * a.TAXI_PER_KM_JD * (1 + taxi_pct / 100))
    return max(0.0, fare - voucher)


def _geometry(pop: list[dict], a: Assumptions) -> list:
    """Per citizen: None (no regular trip) or (trip, hub, mode, transfers, km, one-way minutes, trips/month,
    monthly cost at today's prices). Memoised by (id(pop), assumptions)."""
    key = (id(pop), a.key())
    with _LOCK:
        hit = _BASE.get(key)
        if hit is not None:
            _BASE.move_to_end(key)
            return hit[1]
    hubs, plan, matrix, sides = world.hubs(), world.daily_trips(), world.hub_matrix(), world.sides()
    areas_of_hubs: dict[str, str] = {}
    out = []
    for c in pop:
        trip = c.get("trip") or plan.get(c["id"])  # a citizen dict may carry its own trip (tests)
        if not trip:
            out.append(None)
            continue
        h = hubs[trip["hub"]]
        if h["id"] not in areas_of_hubs:
            areas_of_hubs[h["id"]] = hub_area(h)
        mode = mode_for(c)
        km, drive_min = road(c, f"hub:{h['id']}", h["lat"], h["lng"], matrix, a)
        transfers = 0
        if mode in ("car", "helper_car"):
            minutes, _ = car(km, drive_min, a)
        elif mode == "taxi":
            minutes, _ = taxi(km, drive_min, a)
        else:
            transfers = bus_transfers(c["area"], areas_of_hubs[h["id"]], sides)
            minutes, _ = bus(km, transfers, c["mobility"] == "limited", a)
        trips = trip["days_per_week"] * a.WEEKS_PER_MONTH
        before = round(round_trip_cost(mode, km, transfers, DEFAULT_TERMS, set(), a) * trips, 2)
        out.append((trip, h, mode, transfers, km, minutes, trips, before))
    with _LOCK:
        _BASE[key] = (pop, out)  # keep pop referenced so id(pop) stays unique while cached
        _BASE.move_to_end(key)
        while len(_BASE) > _BASE_MAX:
            _BASE.popitem(last=False)
    return out


def _evaluate(c: dict, g, t: tuple, a: Assumptions):
    if g is None:
        return None
    _trip, _h, mode, transfers, km, minutes, trips, before = g
    tags = set(c["tags"])
    cash = _largest(t[3], tags)
    cost = round(max(0.0, round_trip_cost(mode, km, transfers, t, tags, a) * trips - cash), 2)
    income = a.INCOME_JD_MONTH[c["income_band"]]
    share = cost / income
    status = ("left_out" if share >= a.TRANSPORT_SHARE_PRICED_OUT
              else "hardship" if share >= a.TRANSPORT_SHARE_SQUEEZED else "served")
    hours = round(2 * minutes * trips / 60, 2)
    return (status, cost, hours, round(cost - before, 2), round(share * 100, 1), round(cash, 2))


def _results(policy: Policy, pop: list[dict], a: Assumptions) -> tuple[list, list]:
    """(geometry, compact results), index-aligned with pop. Memoised in a bounded LRU."""
    t = terms(policy)
    geo = _geometry(pop, a)
    key = (id(pop), t, a.key())
    with _LOCK:
        hit = _MEMO.get(key)
        if hit is not None:
            _MEMO.move_to_end(key)
            return geo, hit[1]
    res = [_evaluate(c, g, t, a) for c, g in zip(pop, geo)]
    with _LOCK:
        _MEMO[key] = (pop, res)
        _MEMO.move_to_end(key)
        while len(_MEMO) > _MEMO_MAX:
            _MEMO.popitem(last=False)
    return geo, res


def run(policy: Policy, population: list[dict] | None = None, assumptions: Assumptions | None = None) -> list[dict]:
    """Outcome dicts, index-aligned with the population (same keys as engine.run plus the travel fields)."""
    pop = population if population is not None else world.population()
    a = assumptions or DEFAULT
    geo, res = _results(policy, pop, a)
    out = []
    for c, g, r in zip(pop, geo, res):
        if r is None:
            out.append({"citizen_id": c["id"], "status": "served", "channel": NO_TRIP["id"],
                        "channel_name_ar": NO_TRIP["name_ar"], "channel_name_en": NO_TRIP["name_en"], "mode": None,
                        "bus_transfers": 0, "visit_day": None, "travel_minutes": 0.0, "cost_jd": 0.0,
                        "hours_lost": 0.0, "work_hours_missed": 0.0, "reasons": [], "purpose": None,
                        "days_per_week": None, "monthly_cost_before_jd": 0.0, "extra_jd_month": 0.0,
                        "income_share_pct": 0.0, "cash_support_jd_month": 0.0})
            continue
        trip, h, mode, transfers, _km, minutes, _trips, before = g
        status = r[STATUS]
        reasons = ([] if status == "served" else
                   ["TRANSPORT_OVER_BUDGET", "FUEL_COST" if mode in ("car", "helper_car") else "FARE_COST"])
        out.append({"citizen_id": c["id"], "status": status, "channel": f"trip:{h['id']}",
                    "channel_name_ar": h["name_ar"], "channel_name_en": h["name_en"], "mode": mode,
                    "bus_transfers": transfers, "visit_day": None, "travel_minutes": round(minutes, 1),
                    "cost_jd": r[COST], "hours_lost": r[HOURS], "work_hours_missed": 0.0, "reasons": reasons,
                    "purpose": trip["purpose"], "days_per_week": trip["days_per_week"],
                    "monthly_cost_before_jd": before, "extra_jd_month": r[EXTRA], "income_share_pct": r[SHARE],
                    "cash_support_jd_month": r[CASH]})
    return out


def is_travel(outcomes: list[dict]) -> bool:
    return bool(outcomes) and "income_share_pct" in outcomes[0]


def kpis(outcomes: list[dict]) -> dict:
    """Travel-only KPIs, added to engine.summarize's. Averages are over the citizens with a regular trip
    (n_with_trip); by_purpose / by_mode are percentages of each subgroup, with its size n."""
    trips = [o for o in outcomes if o["purpose"] is not None]
    n = len(trips)
    avg = lambda xs: round(sum(xs) / n, 2) if n else 0.0
    pct = lambda x, d: round(100.0 * x / d, 1) if d else 0.0

    def split(key, values):
        out = {}
        for v in values:
            sub = [o for o in trips if o[key] == v]
            out[v] = {s: pct(sum(o["status"] == s for o in sub), len(sub)) for s in ("served", "hardship", "left_out")}
            out[v]["n"] = len(sub)
        return out

    return {
        "n_with_trip": n,
        "avg_monthly_cost_jd": avg([o["cost_jd"] for o in trips]),
        "avg_extra_jd_month": avg([o["extra_jd_month"] for o in trips]),
        "total_extra_jd_month": round(sum(o["extra_jd_month"] for o in trips), 1),
        "n_cash_support": sum((o["cash_support_jd_month"] or 0) > 0 for o in trips),
        "avg_income_share_pct": round(sum(o["income_share_pct"] for o in trips) / n, 1) if n else 0.0,
        "by_purpose": split("purpose", PURPOSES),
        "by_mode": split("mode", MODES),
    }


def memo_entries() -> dict:
    return {"geometry": len(_BASE), "results": len(_MEMO)}
