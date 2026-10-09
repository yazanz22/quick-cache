"""Everyday trips under road closures. Deterministic, no AI.

Every synthetic citizen has one regular trip (data/daily_trips.json, made by seed_daily.py): workers to a work hub
and students to a university Sun-Thu, other adults 25+ to their nearest public hospital once a week. This module
measures how closed roads change those trips: extra minutes each way, hours lost per week and extra cost.

How each citizen travels follows their profile, with the same travel model as the service engine (travel.py,
frozen assumptions): own car if they have one; otherwise the bus, or, for wheelchair users, a helper's car or a taxi.
Trip times = OSRM road time (hub_matrix.json) × TRAFFIC_FACTOR, plus the closure detour (world.detour).
"""
from __future__ import annotations

from ..models import DailyResult, DailyTrip
from . import world
from .assumptions import DEFAULT, Assumptions
from .travel import bus, bus_transfers, car, haversine_km, road, taxi

# Display bands for the extra one-way minutes (presentation only, not assumptions).
LEVELS = [(15.0, "severe"), (5.0, "moderate"), (1.0, "minor")]
_MEMO: dict = {}


def level(extra_min: float) -> str:
    return next((name for cut, name in LEVELS if extra_min >= cut), "none")


def _mode(c: dict) -> str:
    if c["has_car"]:
        return "car"
    if c["mobility"] == "wheelchair":
        return "helper_car" if c["has_helper"] else "taxi"
    return "bus"


def _hub_area(h: dict) -> str:
    areas = world.areas()
    return min(areas, key=lambda k: (haversine_km(h["lat"], h["lng"], areas[k]["lat"], areas[k]["lng"]), k))


def _one_way(c: dict, mode: str, km: float, drive_min: float, transfers: int, a: Assumptions) -> tuple[float, float]:
    """(one-way minutes, one-way cost JD) for an everyday trip."""
    if mode in ("car", "helper_car"):
        t, rt = car(km, drive_min, a)
    elif mode == "taxi":
        t, rt = taxi(km, drive_min, a)
    else:
        t, rt = bus(km, transfers, c["mobility"] == "limited", a)
    return t, rt / 2


def trips(closed: tuple[str, ...], a: Assumptions | None = None) -> list[dict]:
    a = a or DEFAULT
    key = (tuple(sorted(set(closed))), a.key())
    if key in _MEMO:
        return _MEMO[key]
    hubs, plan, matrix, sides = world.hubs(), world.daily_trips(), world.hub_matrix(), world.sides()
    hub_area = {h: _hub_area(x) for h, x in hubs.items()}
    out = []
    for c in world.population():
        t = plan.get(c["id"])
        if not t:
            continue
        h = hubs[t["hub"]]
        dest = f"hub:{h['id']}"
        mode = _mode(c)
        transfers = bus_transfers(c["area"], hub_area[h["id"]], sides) if mode == "bus" else 0
        km0, d0 = road(c, dest, h["lat"], h["lng"], matrix, a)
        t0, cost0 = _one_way(c, mode, km0, d0, transfers, a)
        ds, dm, rid = world.detour(c["id"], dest, key[0]) if key[0] else (0.0, 0.0, None)
        if rid:
            km1, d1 = road(c, dest, h["lat"], h["lng"], matrix, a, (ds, dm))
            t1, cost1 = _one_way(c, mode, km1, d1, transfers, a)
        else:
            t1, cost1 = t0, cost0
        extra = max(0.0, t1 - t0)
        week = 2 * t["days_per_week"]
        out.append({
            "citizen_id": c["id"], "purpose": t["purpose"], "hub": h["id"], "hub_name_ar": h["name_ar"],
            "hub_name_en": h["name_en"], "mode": mode, "bus_transfers": transfers, "days_per_week": t["days_per_week"],
            "minutes_open": round(t0, 1), "minutes_closed": round(t1, 1), "extra_minutes": round(extra, 1),
            "extra_hours_week": round(extra * week / 60, 2), "extra_cost_jd_week": round(max(0.0, cost1 - cost0) * week, 2),
            "road": rid if extra >= 0.05 else None, "level": level(extra),
        })
    if len(_MEMO) > 200:
        _MEMO.clear()
    _MEMO[key] = out
    return out


def _summary(rows: list[dict]) -> dict:
    hit = [r for r in rows if r["level"] != "none"]
    n = len(rows)
    return {
        "n": n, "n_affected": len(hit), "pct_affected": round(100.0 * len(hit) / n, 1) if n else 0.0,
        "n_severe": sum(r["level"] == "severe" for r in rows),
        "avg_extra_minutes": round(sum(r["extra_minutes"] for r in hit) / len(hit), 1) if hit else 0.0,
        "max_extra_minutes": max((r["extra_minutes"] for r in rows), default=0.0),
        "extra_hours_week": round(sum(r["extra_hours_week"] for r in rows), 1),
        "extra_cost_jd_week": round(sum(r["extra_cost_jd_week"] for r in rows), 1),
    }


def impact(closed: list[str], a: Assumptions | None = None) -> DailyResult:
    rows = trips(tuple(closed), a)
    pop = world.population_by_id()
    groups = {g: _summary([r for r in rows if g in pop[r["citizen_id"]]["tags"]]) for g in world.ALL_GROUPS}
    purposes = {p: _summary([r for r in rows if r["purpose"] == p]) for p in ("work", "university", "hospital")}
    by_road = {}
    for r in rows:
        if r["road"]:
            by_road[r["road"]] = by_road.get(r["road"], 0) + 1
    return DailyResult(
        closed_roads=sorted(set(closed)), kpis=_summary(rows), by_group=groups, by_purpose=purposes,
        by_road=by_road, calibrated=bool(world.road_calibration()) and any(r in world.road_calibration() for r in closed),
        trips=[DailyTrip(**r) for r in rows])
