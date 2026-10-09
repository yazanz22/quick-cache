"""Loads the static data (population, areas, sites, scenarios) once."""
from __future__ import annotations

import json
from functools import lru_cache

from ..config import DATA_DIR, SCENARIOS_DIR
from ..models import Policy

DAY_AR = {"sat": "السبت", "sun": "الأحد", "mon": "الاثنين", "tue": "الثلاثاء", "wed": "الأربعاء", "thu": "الخميس", "fri": "الجمعة"}
DAY_EN = {"sat": "Saturday", "sun": "Sunday", "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday"}

# Groups shown in the equity bars and ranked in worst_groups.
EQUITY_GROUPS = ["elderly", "disabled", "no_car", "offline", "low_income", "worker"]
ALL_GROUPS = EQUITY_GROUPS + ["student"]


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def population() -> list[dict]:
    return _load("population.json")


@lru_cache(maxsize=1)
def population_by_id() -> dict[str, dict]:
    return {c["id"]: c for c in population()}


@lru_cache(maxsize=1)
def areas() -> dict[str, dict]:
    return {a["id"]: a for a in _load("areas.json")["areas"]}


@lru_cache(maxsize=1)
def sites() -> dict[str, dict]:
    return {s["id"]: s for s in _load("sites.json")["sites"]}


@lru_cache(maxsize=1)
def travel_matrix() -> dict:
    p = DATA_DIR / "travel_matrix.json"
    return json.loads(p.read_text(encoding="utf-8"))["matrix"] if p.exists() else {}


@lru_cache(maxsize=1)
def roads() -> dict[str, dict]:
    """Closable major roads (data/roads.json), in catalogue order."""
    p = DATA_DIR / "roads.json"
    return {r["id"]: r for r in json.loads(p.read_text(encoding="utf-8"))["roads"]} if p.exists() else {}


@lru_cache(maxsize=1)
def road_deltas() -> dict:
    p = DATA_DIR / "road_deltas.json"
    return json.loads(p.read_text(encoding="utf-8"))["deltas"] if p.exists() else {}


@lru_cache(maxsize=1)
def road_calibration() -> dict[str, float]:
    """road id -> factor on its detour seconds, from real typical traffic (scripts/calibrate_roads.py, TomTom).
    Missing file or road = 1.0: the free-flow detour, a minimum."""
    p = DATA_DIR / "road_calibration.json"
    return {k: v["factor"] for k, v in json.loads(p.read_text(encoding="utf-8"))["roads"].items()} if p.exists() else {}


def detour(citizen_id: str, dest_key: str, closed: tuple[str, ...]) -> tuple[float, float, str | None]:
    """(extra seconds, extra metres, road id) for a trip when the `closed` roads are closed.
    Each road's detour was routed on its own (fetch_roads.py), then scaled by its traffic calibration if any.
    With several roads closed the trip takes the largest single-road detour: a lower bound, since closing
    more roads can never make a trip faster."""
    best = (0.0, 0.0, None)
    deltas, cal = road_deltas(), road_calibration()
    for r in closed:
        d = deltas.get(r, {}).get(citizen_id, {}).get(dest_key)
        if d and d[0] * cal.get(r, 1.0) > best[0]:
            best = (d[0] * cal.get(r, 1.0), d[1], r)
    return best


@lru_cache(maxsize=1)
def hubs() -> dict[str, dict]:
    p = DATA_DIR / "hubs.json"
    return {h["id"]: h for h in json.loads(p.read_text(encoding="utf-8"))["hubs"]} if p.exists() else {}


@lru_cache(maxsize=1)
def daily_trips() -> dict[str, dict]:
    p = DATA_DIR / "daily_trips.json"
    return json.loads(p.read_text(encoding="utf-8"))["trips"] if p.exists() else {}


@lru_cache(maxsize=1)
def hub_matrix() -> dict:
    p = DATA_DIR / "hub_matrix.json"
    return json.loads(p.read_text(encoding="utf-8"))["matrix"] if p.exists() else {}


def sides() -> dict[str, str]:
    return {k: v["side"] for k, v in areas().items()}


@lru_cache(maxsize=1)
def scenarios() -> dict[str, dict]:
    out = {}
    for p in sorted(SCENARIOS_DIR.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and "policy" in d:
            out[d["id"]] = d
    return out


def demo_scenario_id() -> str:
    """The demo path: the scenario marked "demo": true (CLAUDE.md §10)."""
    return next(s["id"] for s in scenarios().values() if s.get("demo"))


def scenario_policy(scenario_id: str) -> Policy:
    return Policy.model_validate(scenarios()[scenario_id]["policy"])
