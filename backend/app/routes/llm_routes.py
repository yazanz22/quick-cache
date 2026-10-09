"""AI endpoints (CLAUDE.md §7). Each always answers: AI output or a labelled fallback.

The engine numbers the AI sees are computed here, server-side, whenever the client sends policies:
/citizen/voice recomputes the citizen's outcome from `policy`, /report recomputes the comparison, the
robustness check and the applied fix's effect from `baseline`, `scenario` and `fix`.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from ..llm import fallbacks, tasks
from ..models import (CompareRequest, FixesResponse, ParseRequest, ParseResult, ReportRequest, ReportResponse,
                      SensitivityRequest, VoiceRequest, VoiceResponse)
from ..sim import engine, world
from ..sim.compare import compare
from . import sim_routes
from .sim_routes import validate_policy

router = APIRouter(tags=["ai"])


@router.post("/policy/parse", response_model=ParseResult)
def post_parse(req: ParseRequest):
    validate_policy(req.current_policy)
    if not req.text.strip():
        return fallbacks.parse_failed()
    return tasks.parse_policy(req.text, req.current_policy, req.lang)


@router.post("/citizen/voice", response_model=VoiceResponse)
def post_voice(req: VoiceRequest):
    started = time.monotonic()
    c = world.population_by_id().get(req.citizen_id)
    if c is None:
        raise HTTPException(404, f"unknown citizen {req.citizen_id}")
    if req.policy is not None:
        # The engine's own outcome for this citizen (memoised per channel, ~50 ms cold); any client outcome is ignored.
        validate_policy(req.policy)
        pop = world.population()
        i = next(k for k, x in enumerate(pop) if x["id"] == req.citizen_id)
        outcome = engine.run(req.policy, pop)[i]
    elif req.outcome is not None:
        if req.outcome.citizen_id != req.citizen_id:
            raise HTTPException(422, "outcome.citizen_id does not match citizen_id")
        outcome = req.outcome.model_dump(mode="json")  # older clients: the outcome they got from /compare
    else:
        raise HTTPException(422, "send policy (preferred) or outcome")
    return tasks.voice_citizen(c, outcome, started_at=started)


@router.post("/report", response_model=ReportResponse)
def post_report(req: ReportRequest):
    started = time.monotonic()
    if req.baseline is not None and req.scenario is not None:
        for p in (req.baseline, req.scenario, req.fix):
            if p is not None:
                validate_policy(p)
        cr = compare(req.baseline, req.scenario)
        # Same robustness result (and cache) as /sensitivity: with the applied fix, or ranking-only without one.
        sens = sim_routes.post_sensitivity(SensitivityRequest(baseline=req.baseline, scenario=req.scenario, fix=req.fix))
        applied = tasks.fix_effect(cr, req.fix) if req.fix is not None else None
        return tasks.write_report(cr, sens, applied, started_at=started)
    if req.compare_result is not None:
        return tasks.write_report(req.compare_result, req.sensitivity, started_at=started)  # older clients
    raise HTTPException(422, "send baseline and scenario (preferred), or compare_result")


@router.post("/fixes", response_model=FixesResponse)
def post_fixes(req: CompareRequest):
    started = time.monotonic()
    validate_policy(req.scenario)
    return tasks.explain_and_propose_fixes(req.baseline, req.scenario, started_at=started)


@router.get("/llm/status")
def llm_status():
    """Configured model chains, calls per model since start, and which models are cooling down."""
    from ..llm import client
    return client.status()
