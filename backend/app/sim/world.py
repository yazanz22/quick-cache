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
