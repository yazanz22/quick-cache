"""All Pydantic schemas. This file is the API contract (CLAUDE.md §5).

The frontend reads these shapes only through nas-frontend/api.js (its normalisers).
If you change anything here, check api.js in the same commit.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Day = Literal["sat", "sun", "mon", "tue", "wed", "thu", "fri"]

# The services Nas can simulate. "id_renewal": a citizen goes through ID renewal (offices, online, vans...).
# "everyday_travel": a citizen's regular trip (work, university, hospital) under fuel and fare prices; the
# statuses keep the same keys but mean fine / squeezed / priced out (share of income spent on the trip).
# "medical_exemption": an UNINSURED citizen (tag "uninsured", ~44% of adults (44.1% in the population)) applies for a Royal Court medical
# exemption: today one office (the Citizen Services Unit), two visits, no online channel; a first-degree relative
# may apply on their behalf (proxy). Insured citizens are "not applicable" (channel "not_applicable") and are left
# out of every percentage.
Service = Literal["id_renewal", "everyday_travel", "medical_exemption"]

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
    # everyday_travel only:
    "TRANSPORT_OVER_BUDGET",   # the regular trip costs >= TRANSPORT_SHARE_* of per-capita income
    "FUEL_COST",               # the squeeze comes from private-car fuel (mode car / helper_car)
    "FARE_COST",               # the squeeze comes from bus or taxi fares
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
    # From data/seed_insurance.py (seed 42, UNINSURED_RATE_BY_BAND): False adds the "uninsured" tag. None = not assigned.
    has_health_insurance: bool | None = None
    # Optional, from seed_census.py: GAM district and neighbourhood of the home (display only, ignored by the engine).
    district: str | None = None
    neighbourhood: str | None = None
    neighbourhood_ar: str | None = None


class Hero(BaseModel):
    id: str
    note_ar: str | None = None
    note_en: str | None = None
    profile: str | None = None
    service: Service = "id_renewal"


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


Group = Literal["elderly", "disabled", "no_car", "offline", "low_income", "worker", "student", "uninsured"]


class HomeVisits(BaseModel):
    """A clerk renews the ID at the citizen's home. Slots are limited; they go to eligible citizens who are worst
    off without one (left out first, then the heaviest hardship)."""
    groups: list[Group] = ["disabled", "elderly"]
    slots: int = Field(default=20, ge=0, le=1000)   # home visits available for the 1,000 synthetic residents


class TransportVoucher(BaseModel):
    """Covers bus or taxi fares for these groups, up to amount_jd per round trip (not private-car costs)."""
    groups: list[Group]
    amount_jd: float = Field(ge=0, le=50)


class CashSupport(BaseModel):
    """Monthly cash paid to people in these groups (e.g. the National Aid Fund's fuel support, 8-14 JD a month).
    everyday_travel only: it offsets the monthly trip cost; a citizen gets their largest amount."""
    groups: list[Group]
    amount_jd_month: float = Field(ge=0, le=500)


class Policy(BaseModel):
    service: Service = "id_renewal"
    # --- id_renewal levers (ignored by everyday_travel) ---
    offices: list[Office]
    online_enabled: bool = True
    online_only: bool = False
    mobile_units: list[MobileUnit] = []
    appointment_required: bool = False
    fee_jd: float
    visits_required: int = Field(default=1, ge=1, le=5)
    # Protections for groups (a citizen belongs to a group by their tags):
    appointment_exempt_groups: list[Group] = []   # may walk in to an office without an online appointment
    fee_discounts: dict[Group, float] = {}        # percent off fee_jd (0-100); a citizen gets their largest discount
    home_visits: HomeVisits | None = None
    transport_vouchers: list[TransportVoucher] = []   # both services: bus/taxi fares paid up to X JD per round trip
    hybrid_pickup: bool = False   # apply online (yourself or via a helper), then one short visit to collect the card
    # --- everyday_travel levers (all no-ops at their defaults, so id_renewal results and cache keys are unchanged) ---
    fuel_price_change_pct: float = 0.0            # government fuel price change, e.g. +10 (90-octane was 1.050 JD/L in Oct 2026)
    bus_fare_change_pct: float | None = None      # None = fares follow fuel via BUS_FARE_FUEL_PASS_THROUGH; 0 = a fare freeze; N = set change
    taxi_fare_change_pct: float | None = None     # same for the taxi per-km tariff
    cash_support: list[CashSupport] = []          # monthly cash to groups, offsets the trip cost
    # --- medical_exemption lever (None = the service's default: True for medical_exemption, False otherwise) ---
    proxy_allowed: bool | None = None             # a first-degree relative (the citizen's helper) may make the visits instead


class Scenario(BaseModel):
    id: str
    name_ar: str
    name_en: str
    description_ar: str = ""
    description_en: str = ""
    policy: Policy
    demo: bool = False   # the demo path (CLAUDE.md §10): at most one per service
    service: Service = "id_renewal"


class ServiceInfo(BaseModel):
    """GET /services: what Nas can simulate. Labels for statuses and KPIs live in the frontend's i18n, keyed by id."""
    id: Service
    name_ar: str
    name_en: str
    description_ar: str = ""
    description_en: str = ""
    levers: list[str] = []        # which policy-panel sections apply, e.g. ["offices", "online", ...] or ["fuel", "fares", "cash_support", "transport_vouchers"]
    demo_scenario: str | None = None
    baseline_scenario: str | None = None


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
    # everyday_travel only (None for id_renewal). channel = "trip:<hub id>" or "no_regular_trip", mode = car / helper_car /
    # bus / taxi, travel_minutes = one way, cost_jd = monthly trip cost AFTER the policy, hours_lost = monthly hours in transit.
    purpose: Literal["work", "university", "hospital"] | None = None
    days_per_week: int | None = None
    monthly_cost_before_jd: float | None = None    # at today's prices (every travel lever at its default)
    extra_jd_month: float | None = None            # cost_jd - monthly_cost_before_jd (negative when support exceeds the rise)
    income_share_pct: float | None = None          # cost_jd / INCOME_JD_MONTH[band] * 100, after the policy
    cash_support_jd_month: float | None = None     # the support this citizen received under the policy


class SimResult(BaseModel):
    outcomes: list[CitizenOutcome]
    # kpis keys: pct_served, pct_hardship, pct_left_out, avg_hours_lost, avg_cost_jd, n, n_served, n_hardship,
    # n_left_out, n_home_visits, left_out_by_reason {reason: n people}, hardship_by_reason {reason: n people}
    # (a person with several reasons is counted under each; the n_* counts are distinct people).
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
    n_changes: int = 1            # distinct changes vs the scenario (validate.count_changes); AI fixes are capped at 3
    kpis: dict = {}               # the fix policy's SimResult.kpis (for "left out 9 -> 1" style readouts)
    explanation_ar: str | None = None
    explanation_en: str | None = None


class FixGridResponse(BaseModel):
    fixes: list[FixCandidate]     # top 3, engine only
    scenario_kpis: dict           # the scenario's SimResult.kpis, so the UI needs no extra /simulate calls


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
    # Preferred: send the policy and the backend recomputes this citizen's outcome itself (the AI only ever
    # sees engine numbers). `outcome` is accepted for older clients and is ignored when `policy` is given.
    policy: Policy | None = None
    outcome: CitizenOutcome | None = None


class VoiceResponse(BaseModel):
    text_ar: str
    summary_en: str
    source: Literal["ai", "fallback"]


class ReportRequest(BaseModel):
    # Preferred: send the policies and the backend recomputes the comparison, the robustness check and, when
    # `fix` is given, the effect of the applied fix, all server-side. `compare_result`/`sensitivity` are
    # accepted for older clients and are ignored when `baseline` and `scenario` are given.
    baseline: Policy | None = None
    scenario: Policy | None = None
    fix: Policy | None = None
    compare_result: CompareResult | None = None
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
