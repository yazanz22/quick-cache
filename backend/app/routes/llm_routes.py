"""AI endpoints (CLAUDE.md §7). Each always answers: AI output or a labelled fallback."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..llm import fallbacks, tasks
from ..models import (CompareRequest, FixesResponse, ParseRequest, ParseResult, ReportRequest, ReportResponse,
                      VoiceRequest, VoiceResponse)
from ..sim import world
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
    c = world.population_by_id().get(req.citizen_id)
    if c is None:
        raise HTTPException(404, f"unknown citizen {req.citizen_id}")
    return tasks.voice_citizen(c, req.outcome.model_dump(mode="json"))


@router.post("/report", response_model=ReportResponse)
def post_report(req: ReportRequest):
    return tasks.write_report(req.compare_result, req.sensitivity)


@router.post("/fixes", response_model=FixesResponse)
def post_fixes(req: CompareRequest):
    validate_policy(req.scenario)
    return tasks.explain_and_propose_fixes(req.baseline, req.scenario)


@router.get("/llm/status")
def llm_status():
    """Configured model chains, calls per model since start, and which models are cooling down."""
    from ..llm import client
    return client.status()
