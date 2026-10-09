"""Every tunable constant of the engine (CLAUDE.md §6.2).

FREEZE RULE: these values were set once, to round plausible numbers, BEFORE any
scenario was run. If a scenario's story doesn't appear, change the scenario,
never these values. None of them is an official statistic unless tagged
ANCHORED with a source in data/anchors.json.

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

    # Car times and road distances come from the OSRM matrix (data/travel_matrix.json, OpenStreetMap).
    # ASSUMPTION: OSRM times are free-flow; daytime Amman traffic makes trips this many times longer.
    TRAFFIC_FACTOR: float = 1.6
    # ASSUMPTION (fallback only, for citizens missing from the matrix): road km per straight-line km.
    # Rounded from the OSRM matrix median of 1.51.
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
    # ASSUMPTION: waiting for the first bus, minutes.
    BUS_FIRST_WAIT_MIN: float = 10.0
    # ASSUMPTION: extra wait + walk for each transfer, minutes.
    BUS_WAIT_PLUS_TRANSFER_MIN: float = 15.0
    # ASSUMPTION: fare per bus boarding, JD.
    BUS_FARE_JD: float = 0.45

    # ASSUMPTION: waiting for / hailing a taxi, minutes.
    TAXI_WAIT_MIN: float = 5.0
    # ASSUMPTION: taxi flag-fall, JD (pending LTRC figure in anchors.json).
    TAXI_BASE_JD: float = 0.40
    # ASSUMPTION: taxi rate per road km, JD (pending LTRC figure in anchors.json).
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
    "SERVICE_MINUTES": "min", "ONLINE_MINUTES": "min", "TRAFFIC_FACTOR": "×", "ROAD_FACTOR": "×", "CAR_SPEED_KMH": "km/h",
    "CAR_PARK_MIN": "min", "CAR_COST_PER_KM_JD": "JD/km", "BUS_SPEED_KMH": "km/h", "BUS_WALK_MIN": "min",
    "LIMITED_MOBILITY_WALK_FACTOR": "×", "BUS_FIRST_WAIT_MIN": "min", "BUS_WAIT_PLUS_TRANSFER_MIN": "min/transfer",
    "BUS_FARE_JD": "JD", "TAXI_WAIT_MIN": "min", "TAXI_BASE_JD": "JD", "TAXI_PER_KM_JD": "JD/km",
    "TAXI_MAX_JD": "JD", "MAX_TRAVEL_MINUTES": "min", "LONG_TRIP_MINUTES": "min",
    "MAX_WORK_HOURS_MISSED": "h", "HELPER_FREE_FROM": "HH:MM", "HARDSHIP_THRESHOLD": "h-equiv",
    "COST_WEIGHT": "h/JD", "WORK_WEIGHT": "×",
}

# Shown in the AssumptionsTable. Tag is ASSUMPTION unless a real source exists in anchors.json.
META = {
    "SERVICE_MINUTES": ("Queue + counter time for one visit", "ASSUMPTION"),
    "ONLINE_MINUTES": ("Time to finish online or book an appointment", "ASSUMPTION"),
    "TRAFFIC_FACTOR": ("Daytime traffic vs OSRM free-flow car times (road times themselves are OpenStreetMap data)", "ASSUMPTION"),
    "ROAD_FACTOR": ("Fallback only: road vs straight-line km (OSRM median is 1.51)", "ASSUMPTION"),
    "CAR_SPEED_KMH": ("Fallback only: urban car speed incl. traffic", "ASSUMPTION"),
    "CAR_PARK_MIN": ("Parking and walking to the counter", "ASSUMPTION"),
    "CAR_COST_PER_KM_JD": ("Fuel and wear per km", "ASSUMPTION"),
    "BUS_SPEED_KMH": ("Bus speed incl. stops", "ASSUMPTION"),
    "BUS_WALK_MIN": ("Walking to and from stops", "ASSUMPTION"),
    "LIMITED_MOBILITY_WALK_FACTOR": ("Slower walking with limited mobility", "ASSUMPTION"),
    "BUS_FIRST_WAIT_MIN": ("Waiting for the first bus", "ASSUMPTION"),
    "BUS_WAIT_PLUS_TRANSFER_MIN": ("Extra wait per transfer", "ASSUMPTION"),
    "BUS_FARE_JD": ("Fare per boarding", "ASSUMPTION"),
    "TAXI_WAIT_MIN": ("Waiting for a taxi", "ASSUMPTION"),
    "TAXI_BASE_JD": ("Taxi flag-fall", "ASSUMPTION"),
    "TAXI_PER_KM_JD": ("Taxi rate per km", "ASSUMPTION"),
    "TAXI_MAX_JD": ("Most a household spends on a round-trip taxi, by income", "ASSUMPTION"),
    "MAX_TRAVEL_MINUTES": ("Longest realistic one-way trip for an errand", "ASSUMPTION"),
    "LONG_TRIP_MINUTES": ("One-way trip counted as 'far' in hardship reasons", "ASSUMPTION"),
    "MAX_WORK_HOURS_MISSED": ("Most work hours one can miss, by income", "ASSUMPTION"),
    "HELPER_FREE_FROM": ("When a working family member can drive on workdays", "ASSUMPTION"),
    "HARDSHIP_THRESHOLD": ("Burden that counts as hardship: half a working day", "ASSUMPTION"),
    "COST_WEIGHT": ("Hours of burden per JD spent", "ASSUMPTION"),
    "WORK_WEIGHT": ("Extra weight on missed work hours", "ASSUMPTION"),
}

# The three uncertain constants perturbed by the robustness check (§6.5).
SENSITIVITY_PARAMS = ["SERVICE_MINUTES", "BUS_WAIT_PLUS_TRANSFER_MIN", "HARDSHIP_THRESHOLD"]


def perturbed(base: Assumptions, name: str, factor: float) -> Assumptions:
    return replace(base, **{name: getattr(base, name) * factor})


def as_table(a: Assumptions = DEFAULT) -> list[dict]:
    rows = []
    for name, value in asdict(a).items():
        rationale, tag = META[name]
        rows.append({
            "name": name, "value": value, "unit": UNITS.get(name, ""),
            "rationale": rationale, "tag": tag, "source": None,
            "perturbed_in_robustness_check": name in SENSITIVITY_PARAMS,
        })
    return rows
