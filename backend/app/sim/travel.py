"""Travel model: distances, mode times and costs (CLAUDE.md §6.1 rule 4). Pure functions.

Road distances and free-flow car times come from the OSRM matrix (data/travel_matrix.json),
fetched once from OpenStreetMap routing. Citizens missing from the matrix fall back to
straight-line distance × ROAD_FACTOR at CAR_SPEED_KMH.
"""
from __future__ import annotations

import math

from .assumptions import Assumptions


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def bus_transfers(from_area: str, to_area: str, sides: dict[str, str]) -> int:
    """0 within an area, 1 across areas on the same side, 2 between east and west Amman (ASSUMPTION)."""
    if from_area == to_area:
        return 0
    return 1 if sides[from_area] == sides[to_area] else 2


def road(citizen: dict, dest_key: str, dest_lat: float, dest_lng: float,
         matrix: dict, a: Assumptions) -> tuple[float, float]:
    """(road km, driving minutes in daytime traffic) from a citizen's home to a destination."""
    row = matrix.get(citizen["id"])
    if row and dest_key in row:
        seconds, meters = row[dest_key]
        return meters / 1000.0, seconds / 60.0 * a.TRAFFIC_FACTOR
    km = haversine_km(citizen["lat"], citizen["lng"], dest_lat, dest_lng) * a.ROAD_FACTOR
    return km, km / a.CAR_SPEED_KMH * 60


def car(km: float, drive_min: float, a: Assumptions) -> tuple[float, float]:
    """(one-way minutes, round-trip cost JD)."""
    return drive_min + a.CAR_PARK_MIN, 2 * km * a.CAR_COST_PER_KM_JD


def bus(km: float, transfers: int, limited_mobility: bool, a: Assumptions) -> tuple[float, float]:
    walk = a.BUS_WALK_MIN * (a.LIMITED_MOBILITY_WALK_FACTOR if limited_mobility else 1.0)
    minutes = walk + a.BUS_FIRST_WAIT_MIN + km / a.BUS_SPEED_KMH * 60 + transfers * a.BUS_WAIT_PLUS_TRANSFER_MIN
    return minutes, 2 * (transfers + 1) * a.BUS_FARE_JD


def taxi(km: float, drive_min: float, a: Assumptions) -> tuple[float, float]:
    return drive_min + a.TAXI_WAIT_MIN, 2 * (a.TAXI_BASE_JD + km * a.TAXI_PER_KM_JD)


def to_min(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)
