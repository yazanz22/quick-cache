"""All Pydantic schemas. This file is the API contract (CLAUDE.md §5).

The frontend reads these shapes only through nas-frontend/api.js (its normalisers).
If you change anything here, check api.js in the same commit.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Day = Literal["sat", "sun", "mon", "tue", "wed", "thu", "fri"]

Status = Literal["served", "hardship", "left_out"]

ReasonCode = Literal[
    "TOO_FAR",
    "NO_TRANSPORT",
    "HOURS_CONFLICT_WORK",
    "NO_SMARTPHONE",
    "LOW_DIGITAL_LITERACY",
    "NOT_WHEELCHAIR_ACCESSIBLE",
    "TOO_EXPENSIVE",
    "OFFICE_CLOSED_ON_AVAILABLE_DAYS",
]

# ---------------------------------------------------------------- population

class Citizen(BaseModel):
    id: str
    name_ar: str
    name_en: str
    age: int
    gender: Literal["m", "f"]
    area: str
    lat: float
    lng: float
    mobility: Literal["none", "limited", "wheelchair"]
    has_car: bool
    has_smartphone: bool
    digital_literacy: Literal["low", "medium", "high"]
    works: bool
    work_start: str | None = None
    work_end: str | None = None
    income_band: Literal["low", "middle", "high"]
    has_helper: bool
    helper_relation_ar: str | None = None
    helper_relation_en: str | None = None
    tags: list[str] = []
    # Optional, from seed_census.py: GAM district and neighbourhood of the home (display only, ignored by the engine).
    district: str | None = None
    neighbourhood: str | None = None
    neighbourhood_ar: str | None = None


class Hero(BaseModel):
    id: str
    note_ar: str | None = None
    note_en: str | None = None
    profile: str | None = None


class Area(BaseModel):
    id: str
    name_ar: str
    name_en: str
    lat: float
    lng: float
    side: Literal["east", "west"]


class Site(BaseModel):
    id: str
    area: str
    name_ar: str
    name_en: str
    lat: float
    lng: float
    real: bool = False               # True for the 7 real CSPD offices in Amman
    address_en: str | None = None    # CSPD's published address (real sites only)
    geocode: str | None = None       # how the coordinates were found, with precision


# -------------------------------------------------------------------- policy

class Office(BaseModel):
    id: str
    name_ar: str
    name_en: str
    site_id: str
    schedule: dict[Day, tuple[str, str]]
    wheelchair_accessible: bool = True


class MobileUnit(BaseModel):
    area: str
    day: Day
    open: str
    close: str


class Policy(BaseModel):
    service: str = "id_renewal"
    offices: list[Office]
    online_enabled: bool = True
    online_only: bool = False
    mobile_units: list[MobileUnit] = []
    appointment_required: bool = False
    fee_jd: float
    visits_required: int = Field(default=1, ge=1, le=5)


class Scenario(BaseModel):
    id: str
    name_ar: str
    name_en: str
    description_ar: str = ""
    description_en: str = ""
    policy: Policy
    demo: bool = False   # the demo path (CLAUDE.md §10)


# ---------------------------------------------------------------- simulation

class CitizenOutcome(BaseModel):
    citizen_id: str
    status: Status
    channel: str | None = None
    channel_name_ar: str | None = None
    channel_name_en: str | None = None
    mode: str | None = None
    bus_transfers: int = 0
    visit_day: Day | None = None
    travel_minutes: float = 0.0
    cost_jd: float = 0.0
    hours_lost: float = 0.0
    work_hours_missed: float = 0.0
    reasons: list[ReasonCode] = []


class SimResult(BaseModel):
    outcomes: list[CitizenOutcome]
    kpis: dict
    by_group: dict


class CompareResult(BaseModel):
    baseline: SimResult
    scenario: SimResult
    flipped_worse: list[str]
    flipped_better: list[str]
    kpi_delta: dict
    worst_groups: list[str]


# --------------------------------------------------- fixes, parse, robustness

class FixCandidate(BaseModel):
    id: str
    title_ar: str
    title_en: str
    policy: Policy
    source: Literal["engine_grid", "ai_proposed"]
    left_out_drop: float
    hardship_drop: float
    worsens_any_group: bool
    explanation_ar: str | None = None
    explanation_en: str | None = None


class ParseResult(BaseModel):
    status: Literal["ok", "unsupported"]
    policy: Policy | None = None
    changes_ar: list[str] = []
    changes_en: list[str] = []
    message_ar: str | None = None
    message_en: str | None = None
    source: Literal["ai", "fallback"] = "ai"


class SensitivityResult(BaseModel):
    runs: int
    ranking_held: int
    fix_checked: bool = True               # False when no fix was sent (ranking-only check)
    fix_still_helps: int
    stable_top_group: str | None = None
    stable_top2: list[str] | None = None   # the top-2 groups as a set, if the same in every run (order may flip)
    passed: bool
    details: list[dict] = []


# ------------------------------------------------------------ request bodies

class SimulateRequest(BaseModel):
    policy: Policy


class CompareRequest(BaseModel):
    baseline: Policy
    scenario: Policy


class SensitivityRequest(BaseModel):
    baseline: Policy
    scenario: Policy
    fix: Policy | None = None   # optional: without a fix only the ranking is checked


class ParseRequest(BaseModel):
    text: str
    current_policy: Policy
    lang: Literal["ar", "en"] = "ar"


class VoiceRequest(BaseModel):
    citizen_id: str
    outcome: CitizenOutcome


class VoiceResponse(BaseModel):
    text_ar: str
    summary_en: str
    source: Literal["ai", "fallback"]


class ReportRequest(BaseModel):
    compare_result: CompareResult
    sensitivity: SensitivityResult | None = None


class ReportResponse(BaseModel):
    summary_ar: str
    summary_en: str
    source: Literal["ai", "fallback"]


class FixesResponse(BaseModel):
    fixes: list[FixCandidate]
    source: Literal["ai", "fallback"]
    # What happened to the AI's off-grid idea: status is "shown", "hidden_not_better", "hidden_worsens_a_group",
    # "hidden_duplicate_of_grid", "hidden_no_change", "invalid", "ai_unavailable" or "no_grid_fixes".
    ai_proposal: dict | None = None
