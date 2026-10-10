"""Engine endpoints (CLAUDE.md §7). No AI here."""
from __future__ import annotations

import hashlib
import json
import threading

from fastapi import APIRouter, HTTPException

from ..config import SCENARIOS_DIR
from ..models import (Area, Citizen, CompareRequest, CompareResult, FixGridResponse, Hero, Policy, Scenario,
                      SensitivityRequest, SensitivityResult, Service, ServiceInfo, SimResult, SimulateRequest, Site)
from ..sim import assumptions as A
from ..sim.assumption_labels import label_rows
from ..sim import fixgrid, sensitivity, warmup, world
from ..sim.compare import compare
from ..sim.engine import run, simulate, summarize
from ..sim.validate import policy_errors

router = APIRouter(tags=["engine"])
_SENS_CACHE: dict[str, SensitivityResult] = {}
_SENS_MAX = 500           # robustness results kept; the cache is cleared when it grows past this
_SENS_LOCK = threading.Lock()  # written by the start-up warm-up thread and by request threads
WARM_DONE = threading.Event()  # set when the start-up warm-up has finished (or failed)


def validate_policy(p: Policy) -> None:
    """Reject unknown sites/areas and impossible hours with a readable 422."""
    errs = policy_errors(p)
    if errs:
        raise HTTPException(422, "; ".join(errs))


def same_service(*policies: Policy | None) -> None:
    """A comparison only makes sense within one service (e.g. ID renewal vs ID renewal): 422 otherwise."""
    found = sorted({p.service for p in policies if p is not None})
    if len(found) > 1:
        raise HTTPException(422, f"policies are for different services ({', '.join(found)}); "
                                 "compare a policy with one of the same service")


@router.get("/services", response_model=list[ServiceInfo])
def get_services():
    """What Nas can simulate, each with its levers, baseline and demo scenario."""
    return world.services()


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
def get_heroes(service: Service = "id_renewal"):
    """Hero citizens of a service's demo path (scenarios/heroes.json, made by scripts/pick_heroes.py).
    Entries without a "service" are id_renewal heroes."""
    p = SCENARIOS_DIR / "heroes.json"
    if not p.exists():
        return []
    h = json.loads(p.read_text(encoding="utf-8"))
    return [{"id": x["citizen_id"], "note_ar": x.get("note_ar"), "note_en": x.get("note_en") or x.get("wanted"),
             "profile": x.get("profile"), "service": x.get("service", "id_renewal")}
            for x in h.get("heroes", []) if x.get("service", "id_renewal") == service]


@router.get("/areas", response_model=list[Area])
def get_areas():
    return list(world.areas().values())


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
    same_service(req.baseline, req.scenario)
    return compare(req.baseline, req.scenario)


@router.post("/fixgrid", response_model=FixGridResponse)
def post_fixgrid(req: CompareRequest):
    """Top 3 engine fixes (each with its own kpis and n_changes) plus the scenario's kpis."""
    validate_policy(req.scenario)
    same_service(req.baseline, req.scenario)
    fixes = fixgrid.top_fixes(req.scenario)
    scenario_kpis, _ = summarize(run(req.scenario))  # memo hits: build() just ran the scenario
    return FixGridResponse(fixes=fixes, scenario_kpis=scenario_kpis)


def _sens_key(req: SensitivityRequest) -> str:
    return hashlib.sha256(json.dumps(req.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()


def _sens_put(key: str, res: SensitivityResult) -> None:
    with _SENS_LOCK:
        if len(_SENS_CACHE) >= _SENS_MAX and key not in _SENS_CACHE:
            _SENS_CACHE.clear()
        _SENS_CACHE[key] = res


def _store_warm(w: dict) -> None:
    s = w["sensitivity"]
    _sens_put(_sens_key(SensitivityRequest(baseline=w["base"], scenario=w["demo"])), s["ranking_only"])
    if "top_fix" in s:
        req = SensitivityRequest(baseline=w["base"], scenario=w["demo"], fix=w["top"][0]["policy"])
        _sens_put(_sens_key(req), s["top_fix"])
    if "ai_fix" in s:
        req = SensitivityRequest(baseline=w["base"], scenario=w["demo"], fix=w["ai_fix"])
        _sens_put(_sens_key(req), s["ai_fix"])


def warm_up() -> float:
    """Run each service's demo path once (engine memo + robustness results for: no fix, the top grid fix and, for
    ID renewal when the AI cache has it, the verified AI fix). Returns seconds taken. main.py runs it in a
    background thread."""
    try:
        w = warmup.warm()
        _store_warm(w)
        t = warmup.warm_travel()
        _store_warm(t)
        return round(w["seconds"] + t["seconds"], 1)
    finally:
        WARM_DONE.set()


@router.post("/sensitivity", response_model=SensitivityResult)
def post_sensitivity(req: SensitivityRequest):
    for p in (req.baseline, req.scenario, req.fix):
        if p is not None:
            validate_policy(p)
    same_service(req.baseline, req.scenario, req.fix)
    key = _sens_key(req)
    hit = _SENS_CACHE.get(key)
    if hit is None:
        hit = sensitivity.check(req.baseline, req.scenario, req.fix)  # computed outside the lock
        _sens_put(key, hit)
    return hit
