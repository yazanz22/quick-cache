"""Engine endpoints (CLAUDE.md §7). No AI here."""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, HTTPException

from ..config import SCENARIOS_DIR
from ..models import (CompareRequest, CompareResult, FixCandidate, Policy, SensitivityRequest, SensitivityResult,
                      SimResult, SimulateRequest)
from ..sim import assumptions as A
from ..sim import fixgrid, sensitivity, world
from ..sim.compare import compare
from ..sim.engine import simulate
from ..sim.travel import haversine_km
from ..sim.validate import policy_errors

router = APIRouter(tags=["engine"])
_SENS_CACHE: dict[str, SensitivityResult] = {}


def validate_policy(p: Policy) -> None:
    """Reject unknown sites/areas and impossible hours with a readable 422."""
    errs = policy_errors(p)
    if errs:
        raise HTTPException(422, "; ".join(errs))


@router.get("/population")
def get_population():
    return world.population()


@router.get("/scenarios")
def get_scenarios():
    return sorted(world.scenarios().values(), key=lambda s: s.get("order", 99))


@router.get("/sites")
def get_sites():
    return list(world.sites().values())


@router.get("/sites/nearest")
def nearest_site(lat: float, lng: float):
    """Snap a dragged office pin to the nearest candidate site."""
    return min(world.sites().values(), key=lambda s: haversine_km(lat, lng, s["lat"], s["lng"]))


@router.get("/heroes")
def get_heroes():
    """Hero citizens for the demo path (scenarios/heroes.json, made by scripts/pick_heroes.py)."""
    p = SCENARIOS_DIR / "heroes.json"
    if not p.exists():
        return []
    h = json.loads(p.read_text(encoding="utf-8"))
    return [{"id": x["citizen_id"], "note_ar": x.get("note_ar"), "note_en": x.get("note_en") or x.get("wanted"),
             "profile": x.get("profile")} for x in h.get("heroes", [])]


@router.get("/areas")
def get_areas():
    return list(world.areas().values())


@router.get("/assumptions")
def get_assumptions():
    return A.as_table()


@router.post("/simulate", response_model=SimResult)
def post_simulate(req: SimulateRequest):
    validate_policy(req.policy)
    return simulate(req.policy)


@router.post("/compare", response_model=CompareResult)
def post_compare(req: CompareRequest):
    validate_policy(req.baseline)
    validate_policy(req.scenario)
    return compare(req.baseline, req.scenario)


@router.post("/fixgrid", response_model=list[FixCandidate])
def post_fixgrid(req: CompareRequest):
    validate_policy(req.scenario)
    return fixgrid.top_fixes(req.scenario)


@router.post("/sensitivity", response_model=SensitivityResult)
def post_sensitivity(req: SensitivityRequest):
    for p in (req.baseline, req.scenario, req.fix):
        validate_policy(p)
    key = hashlib.sha256(json.dumps(req.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()
    if key not in _SENS_CACHE:
        _SENS_CACHE[key] = sensitivity.check(req.baseline, req.scenario, req.fix)
    return _SENS_CACHE[key]
