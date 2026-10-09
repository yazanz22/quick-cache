"""Every tunable constant of the engine (CLAUDE.md §6.2).

FREEZE RULE: these values were set once, to round plausible numbers, BEFORE any
scenario was run. If a scenario's story doesn't appear, change the scenario,
never these values. All 26 are tagged ASSUMPTION: none is an official statistic.
Where the desk research gives context for one (data/anchors.json, CITED_UNVERIFIED),
its `source` field in the assumptions table says so; the tag stays ASSUMPTION.

The engine takes an optional `Assumptions` override so sensitivity.py can
perturb SERVICE_MINUTES, BUS_WAIT_PLUS_TRANSFER_MIN and HARDSHIP_THRESHOLD.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace


@dataclass(frozen=True)
class Assumptions:
    # ASSUMPTION: queue + counter time for an ID renewal visit, in minutes.
    SERVICE_MINUTES: float = 60.0
    # ASSUMPTION: time to complete the service (or book an appointment) online.
    ONLINE_MINUTES: float = 20.0
    # ASSUMPTION: a home visit means waiting at home for a 2-hour visit window (policy lever "home visits").
    # Added 2026-10-09 with the lever, set before any scenario using it was run.
    HOME_VISIT_MINUTES: float = 120.0
    # ASSUMPTION: collecting a card already applied for online: a short counter visit (lever "hybrid pickup").
    # Added 2026-10-09 with the lever, set before any scenario using it was run.
    PICKUP_MINUTES: float = 15.0

    # Car times and road distances come from the OSRM matrix (data/travel_matrix.json, OpenStreetMap).
    # ASSUMPTION: OSRM times are free-flow; daytime Amman traffic makes trips this many times longer.
    TRAFFIC_FACTOR: float = 1.6
    # ASSUMPTION (fallback only, for citizens missing from the matrix): road km per straight-line km.
    # Rounded from the OSRM matrix median, about 1.4-1.5 (1.44 in the current matrix).
    ROAD_FACTOR: float = 1.5
    # ASSUMPTION (fallback only): average urban driving speed incl. traffic, km/h.
    CAR_SPEED_KMH: float = 30.0
    # ASSUMPTION: parking + walking to the counter, minutes per one-way trip.
    CAR_PARK_MIN: float = 10.0
    # ASSUMPTION: fuel + wear cost per km for a private car, JD.
    CAR_COST_PER_KM_JD: float = 0.08

    # ASSUMPTION: average bus/service-taxi speed incl. stops, km/h.
    BUS_SPEED_KMH: float = 15.0
    # ASSUMPTION: walking to and from stops, minutes per one-way trip.
    BUS_WALK_MIN: float = 10.0
    # ASSUMPTION: people with limited mobility walk to stops this many times slower.
    LIMITED_MOBILITY_WALK_FACTOR: float = 2.0
    # ASSUMPTION: waiting for the first bus, minutes (off-peak; a 2017 study cited by the research measured
    # ~25 min at peak: anchors.json bus_wait_peak_minutes, CITED_UNVERIFIED).
    BUS_FIRST_WAIT_MIN: float = 10.0
    # ASSUMPTION: extra wait + walk for each transfer, minutes.
    BUS_WAIT_PLUS_TRANSFER_MIN: float = 15.0
    # ASSUMPTION: fare per bus boarding, JD (the research cites 0.34-0.55 JD: anchors.json bus_fare_jd_range,
    # CITED_UNVERIFIED).
    BUS_FARE_JD: float = 0.45

    # ASSUMPTION: waiting for / hailing a taxi, minutes.
    TAXI_WAIT_MIN: float = 5.0
    # ASSUMPTION: taxi flag-fall, JD (no verified LTRC tariff found; not in anchors.json).
    TAXI_BASE_JD: float = 0.40
    # ASSUMPTION: taxi rate per road km, JD (no verified LTRC tariff found; not in anchors.json).
    TAXI_PER_KM_JD: float = 0.30
    # ASSUMPTION: most a household would spend on a round-trip taxi for one visit, JD.
    TAXI_MAX_JD: dict = field(default_factory=lambda: {"low": 3.0, "middle": 8.0, "high": 25.0})

    # ASSUMPTION: a one-way trip longer than this is not realistic for an errand, minutes.
    MAX_TRAVEL_MINUTES: float = 90.0
    # ASSUMPTION: a one-way trip this long counts as a far trip in hardship reasons, minutes.
    LONG_TRIP_MINUTES: float = 45.0

    # ASSUMPTION: most work hours someone can miss for this service, by income band.
    # Daily-wage workers can't lose more than half a day.
    MAX_WORK_HOURS_MISSED: dict = field(default_factory=lambda: {"low": 4.0, "middle": 8.0, "high": 8.0})
    # ASSUMPTION: a working helper is free to drive from this time on Sun–Thu.
    HELPER_FREE_FROM: str = "16:00"

    # ASSUMPTION: burden (hour-equivalents) at or above which the visit is a hardship: half a working day.
    HARDSHIP_THRESHOLD: float = 4.0
    # ASSUMPTION: hours of burden per JD spent (1 JD ~ 30 minutes of effort).
    COST_WEIGHT: float = 0.5
    # ASSUMPTION: extra burden per hour of work missed, on top of the hours themselves.
    WORK_WEIGHT: float = 1.0

    def key(self) -> tuple:
        """Hashable identity, used by the engine's memo cache."""
        d = asdict(self)
        return tuple((k, tuple(sorted(v.items())) if isinstance(v, dict) else v) for k, v in sorted(d.items()))


DEFAULT = Assumptions()

UNITS = {
    "SERVICE_MINUTES": "min", "ONLINE_MINUTES": "min", "HOME_VISIT_MINUTES": "min", "PICKUP_MINUTES": "min", "TRAFFIC_FACTOR": "×", "ROAD_FACTOR": "×", "CAR_SPEED_KMH": "km/h",
    "CAR_PARK_MIN": "min", "CAR_COST_PER_KM_JD": "JD/km", "BUS_SPEED_KMH": "km/h", "BUS_WALK_MIN": "min",
    "LIMITED_MOBILITY_WALK_FACTOR": "×", "BUS_FIRST_WAIT_MIN": "min", "BUS_WAIT_PLUS_TRANSFER_MIN": "min/transfer",
    "BUS_FARE_JD": "JD", "TAXI_WAIT_MIN": "min", "TAXI_BASE_JD": "JD", "TAXI_PER_KM_JD": "JD/km",
    "TAXI_MAX_JD": "JD", "MAX_TRAVEL_MINUTES": "min", "LONG_TRIP_MINUTES": "min",
    "MAX_WORK_HOURS_MISSED": "h", "HELPER_FREE_FROM": "HH:MM", "HARDSHIP_THRESHOLD": "h-equiv",
    "COST_WEIGHT": "h/JD", "WORK_WEIGHT": "×",
}

# Shown in the AssumptionsTable: name -> (rationale, tag, source). Every tag is ASSUMPTION. `source` is a short
# note on where context for the value comes from (None if there is none); it never upgrades the tag.
META = {
    "SERVICE_MINUTES": ("Queue + counter time for one visit", "ASSUMPTION", None),
    "ONLINE_MINUTES": ("Time to finish online or book an appointment", "ASSUMPTION", None),
    "HOME_VISIT_MINUTES": ("Home visit: waiting at home for a 2-hour visit window", "ASSUMPTION", None),
    "PICKUP_MINUTES": ("Collecting a card applied for online: a short counter visit", "ASSUMPTION", None),
    "TRAFFIC_FACTOR": ("Daytime traffic vs OSRM free-flow car times (road times themselves are OpenStreetMap data)", "ASSUMPTION", "Multiplies OSRM free-flow car times (OpenStreetMap); no Amman congestion data found"),
    "ROAD_FACTOR": ("Fallback only: road vs straight-line km (OSRM median about 1.4-1.5)", "ASSUMPTION", "OSRM matrix: median road/straight-line ratio 1.44"),
    "CAR_SPEED_KMH": ("Fallback only: urban car speed incl. traffic", "ASSUMPTION", None),
    "CAR_PARK_MIN": ("Parking and walking to the counter", "ASSUMPTION", None),
    "CAR_COST_PER_KM_JD": ("Fuel and wear per km", "ASSUMPTION", None),
    "BUS_SPEED_KMH": ("Bus speed incl. stops", "ASSUMPTION", None),
    "BUS_WALK_MIN": ("Walking to and from stops", "ASSUMPTION", None),
    "LIMITED_MOBILITY_WALK_FACTOR": ("Slower walking with limited mobility", "ASSUMPTION", None),
    "BUS_FIRST_WAIT_MIN": ("Waiting for the first bus", "ASSUMPTION", "A 2017 study cited by our research measured ~25 min peak waits (unverified); we assume 10 + 15 per transfer, off-peak"),
    "BUS_WAIT_PLUS_TRANSFER_MIN": ("Extra wait per transfer", "ASSUMPTION", "Same 2017 peak-wait study as the first wait (unverified); tested at ±20%"),
    "BUS_FARE_JD": ("Fare per boarding", "ASSUMPTION", "Public fares 0.34-0.55 JD per boarding, from our research, unverified"),
    "TAXI_WAIT_MIN": ("Waiting for a taxi", "ASSUMPTION", None),
    "TAXI_BASE_JD": ("Taxi flag-fall", "ASSUMPTION", "No verified LTRC taxi tariff found"),
    "TAXI_PER_KM_JD": ("Taxi rate per km", "ASSUMPTION", "No verified LTRC taxi tariff found"),
    "TAXI_MAX_JD": ("Most a household spends on a round-trip taxi, by income", "ASSUMPTION", None),
    "MAX_TRAVEL_MINUTES": ("Longest realistic one-way trip for an errand", "ASSUMPTION", None),
    "LONG_TRIP_MINUTES": ("One-way trip counted as 'far' in hardship reasons", "ASSUMPTION", None),
    "MAX_WORK_HOURS_MISSED": ("Most work hours one can miss, by income", "ASSUMPTION", None),
    "HELPER_FREE_FROM": ("When a working family member can drive on workdays", "ASSUMPTION", None),
    "HARDSHIP_THRESHOLD": ("Burden that counts as hardship: half a working day", "ASSUMPTION", None),
    "COST_WEIGHT": ("Hours of burden per JD spent", "ASSUMPTION", None),
    "WORK_WEIGHT": ("Extra weight on missed work hours", "ASSUMPTION", None),
}

# The three uncertain constants perturbed by the robustness check (§6.5).
SENSITIVITY_PARAMS = ["SERVICE_MINUTES", "BUS_WAIT_PLUS_TRANSFER_MIN", "HARDSHIP_THRESHOLD"]


def perturbed(base: Assumptions, name: str, factor: float) -> Assumptions:
    return replace(base, **{name: getattr(base, name) * factor})


def as_table(a: Assumptions = DEFAULT) -> list[dict]:
    rows = []
    for name, value in asdict(a).items():
        rationale, tag, source = META[name]
        rows.append({
            "name": name, "value": value, "unit": UNITS.get(name, ""),
            "rationale": rationale, "tag": tag, "source": source,
            "perturbed_in_robustness_check": name in SENSITIVITY_PARAMS,
        })
    return rows
