"""Engine endpoints (CLAUDE.md §7). No AI here."""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, HTTPException

from ..config import SCENARIOS_DIR
from ..models import (Area, Citizen, CompareRequest, CompareResult, FixCandidate, Hero, Policy, Road, Scenario,
                      SensitivityRequest, SensitivityResult, SimResult, SimulateRequest, Site)
from ..sim import assumptions as A
from ..sim.assumption_labels import label_rows
from ..sim import fixgrid, sensitivity, warmup, world
from ..sim.compare import compare
from ..sim.engine import simulate
from ..sim.validate import policy_errors

router = APIRouter(tags=["engine"])
_SENS_CACHE: dict[str, SensitivityResult] = {}


def validate_policy(p: Policy) -> None:
    """Reject unknown sites/areas and impossible hours with a readable 422."""
    errs = policy_errors(p)
    if errs:
        raise HTTPException(422, "; ".join(errs))


@router.get("/population", response_model=list[Citizen])
def get_population():
    return world.population()


@router.get("/scenarios", response_model=list[Scenario])
def get_scenarios():
    return sorted(world.scenarios().values(), key=lambda s: s.get("order", 99))


@router.get("/sites", response_model=list[Site])
def get_sites():
    return list(world.sites().values())


@router.get("/heroes", response_model=list[Hero])
def get_heroes():
    """Hero citizens for the demo path (scenarios/heroes.json, made by scripts/pick_heroes.py)."""
    p = SCENARIOS_DIR / "heroes.json"
    if not p.exists():
        return []
    h = json.loads(p.read_text(encoding="utf-8"))
    return [{"id": x["citizen_id"], "note_ar": x.get("note_ar"), "note_en": x.get("note_en") or x.get("wanted"),
             "profile": x.get("profile")} for x in h.get("heroes", [])]


@router.get("/areas", response_model=list[Area])
def get_areas():
    return list(world.areas().values())


@router.get("/roads", response_model=list[Road])
def get_roads():
    """Closable major roads with their map geometry (data/roads.json, from OpenStreetMap)."""
    return list(world.roads().values())


@router.get("/assumptions")
def get_assumptions():
    return label_rows(A.as_table())


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


def _sens_key(req: SensitivityRequest) -> str:
    return hashlib.sha256(json.dumps(req.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


def warm_up() -> float:
    """Run the demo path once at start-up (engine memo + robustness results). Returns seconds taken."""
    w = warmup.warm()
    s = w["sensitivity"]
    _SENS_CACHE[_sens_key(SensitivityRequest(baseline=w["base"], scenario=w["demo"]))] = s["ranking_only"]
    if "top_fix" in s:
        fix = SensitivityRequest(baseline=w["base"], scenario=w["demo"], fix=w["top"][0]["policy"])
        _SENS_CACHE[_sens_key(fix)] = s["top_fix"]
    return w["seconds"]


@router.post("/sensitivity", response_model=SensitivityResult)
def post_sensitivity(req: SensitivityRequest):
    for p in (req.baseline, req.scenario, req.fix):
        if p is not None:
            validate_policy(p)
    key = _sens_key(req)
    if key not in _SENS_CACHE:
        _SENS_CACHE[key] = sensitivity.check(req.baseline, req.scenario, req.fix)
    return _SENS_CACHE[key]
