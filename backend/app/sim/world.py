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


def sides() -> dict[str, str]:
    return {k: v["side"] for k, v in areas().items()}


@lru_cache(maxsize=1)
def hubs() -> dict[str, dict]:
    """Everyday-trip destinations (work hubs, universities, hospitals), by id."""
    return {h["id"]: h for h in _load("hubs.json")["hubs"]}


@lru_cache(maxsize=1)
def daily_trips() -> dict[str, dict]:
    """citizen id -> {purpose, hub, days_per_week}: each citizen's one regular trip (seed_daily.py). Some have none."""
    return _load("daily_trips.json")["trips"]


@lru_cache(maxsize=1)
def hub_matrix() -> dict:
    """citizen id -> "hub:<id>" -> [free-flow seconds, metres] (OSRM)."""
    p = DATA_DIR / "hub_matrix.json"
    return json.loads(p.read_text(encoding="utf-8"))["matrix"] if p.exists() else {}


@lru_cache(maxsize=1)
def services() -> list[dict]:
    """What Nas can simulate (services.json, models.ServiceInfo)."""
    return list(_load("services.json")["services"])


@lru_cache(maxsize=1)
def scenarios() -> dict[str, dict]:
    """Preset scenarios by id. Each carries "service" (from the file, else its policy's service)."""
    out = {}
    for p in sorted(SCENARIOS_DIR.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and "policy" in d:
            d.setdefault("service", d["policy"].get("service", "id_renewal"))
            out[d["id"]] = d
    return out


def demo_scenario_id(service: str = "id_renewal") -> str:
    """The demo path of a service: its scenario marked "demo": true (CLAUDE.md §10)."""
    return next(s["id"] for s in scenarios().values() if s.get("demo") and s["service"] == service)


def baseline_scenario_id(service: str = "id_renewal") -> str:
    """The "today" scenario of a service (services.json baseline_scenario)."""
    return next(s["baseline_scenario"] for s in services() if s["id"] == service)


def scenario_policy(scenario_id: str) -> Policy:
    return Policy.model_validate(scenarios()[scenario_id]["policy"])
