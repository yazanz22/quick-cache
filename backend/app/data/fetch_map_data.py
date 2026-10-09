"""One-time fetch of real map data. Run while online; outputs are committed so the
engine never calls an API at simulate time (deterministic, offline-safe).

    python -m app.data.fetch_map_data matrix    # OSRM     -> travel_matrix.json
    python -m app.data.fetch_map_data homes     # Overpass -> home_points.json (residential streets, for seed_census)

Data © OpenStreetMap contributors, ODbL. Routing by the public OSRM demo server
(router.project-osrm.org), used lightly: one table request per 77 citizens (100 coordinates minus the
23 destinations), so 13 requests for 1,000 citizens.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent
UA = {"User-Agent": "nas-hackathon-ai-quest/1.0 (synthetic population demo)"}
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
OSRM = "https://router.project-osrm.org/table/v1/driving/"


def _get(url: str, data: bytes | None = None, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def overpass(query: str) -> list[dict]:
    for attempt in range(2):
        for url in OVERPASS_MIRRORS:
            try:
                return _get(url, urllib.parse.urlencode({"data": query}).encode())["elements"]
            except Exception as e:  # public servers sometimes return a busy page
                print("overpass busy:", url, type(e).__name__, getattr(e, "code", ""))
        time.sleep(10)
    raise RuntimeError("Overpass unavailable")


GAM_BBOX = (31.84, 35.74, 32.09, 36.10)  # south, west, north, east: all 22 GAM districts
HOME_GRID = 0.0006                       # ~60 m: one candidate home point per grid cell


def fetch_homes() -> None:
    """Points every ~60 m along OSM residential streets in Greater Amman. seed_census places each synthetic
    home on one of these near its neighbourhood, so homes follow the built-up city, not open land."""
    s, w, n, e = GAM_BBOX
    q = f"""[out:json][timeout:180][maxsize:536870912];
way["highway"~"^(residential|living_street)$"]({s},{w},{n},{e});
out geom;"""
    els = overpass(q)
    cells: set[tuple[int, int]] = set()
    for x in els:
        g = x.get("geometry") or []
        for a, b in zip(g, g[1:]):
            dy, dx = (b["lat"] - a["lat"]) * 111.0, (b["lon"] - a["lon"]) * 94.4
            steps = max(1, int((dy * dy + dx * dx) ** 0.5 / 0.06))
            for k in range(steps + 1):
                lat = a["lat"] + (b["lat"] - a["lat"]) * k / steps
                lon = a["lon"] + (b["lon"] - a["lon"]) * k / steps
                cells.add((round(lat / HOME_GRID), round(lon / HOME_GRID)))
    pts = sorted([round(i * HOME_GRID, 5), round(j * HOME_GRID, 5)] for i, j in cells)
    (DATA / "home_points.json").write_text(json.dumps({
        "_source": "OpenStreetMap via Overpass API, ODbL. highway=residential|living_street, sampled every ~60 m.",
        "_fetched": date.today().isoformat(), "bbox": GAM_BBOX, "ways": len(els), "count": len(pts),
        "points": pts}, separators=(",", ":")), encoding="utf-8")
    print(f"residential streets: {len(els)} ways -> {len(pts)} home points")


def fetch_matrix() -> None:
    """Driving duration (s) and distance (m) from every citizen to every site and area centroid."""
    pop = json.loads((DATA / "population.json").read_text(encoding="utf-8"))
    sites = json.loads((DATA / "sites.json").read_text(encoding="utf-8"))["sites"]
    areas = json.loads((DATA / "areas.json").read_text(encoding="utf-8"))["areas"]
    dests = [(s["id"], s["lat"], s["lng"]) for s in sites] + [(f"area:{a['id']}", a["lat"], a["lng"]) for a in areas]
    out = _osrm_table(pop, dests)
    (DATA / "travel_matrix.json").write_text(json.dumps({
        "_source": "OSRM public demo server (router.project-osrm.org), OpenStreetMap data, ODbL. Free-flow car times.",
        "_fetched": date.today().isoformat(),
        "_format": "citizen_id -> destination -> [duration_seconds, distance_meters]; destinations are site ids and area:<id> centroids",
        "matrix": out}, separators=(",", ":")), encoding="utf-8")
    print("saved travel_matrix.json")


def _osrm_table(pop: list[dict], dests: list[tuple]) -> dict:
    chunk = 100 - len(dests)
    out: dict[str, dict[str, list[float]]] = {}
    for i in range(0, len(pop), chunk):
        part = pop[i:i + chunk]
        coords = [(c["lng"], c["lat"]) for c in part] + [(d[2], d[1]) for d in dests]
        path = ";".join(f"{x:.5f},{y:.5f}" for x, y in coords)
        src = ";".join(str(k) for k in range(len(part)))
        dst = ";".join(str(len(part) + k) for k in range(len(dests)))
        url = f"{OSRM}{path}?sources={src}&destinations={dst}&annotations=duration,distance"
        for attempt in range(3):
            try:
                r = _get(url)
                if r.get("code") == "Ok":
                    break
                raise RuntimeError(r.get("code"))
            except Exception as e:
                print("osrm retry", attempt + 1, e)
                time.sleep(5)
        else:
            raise RuntimeError("OSRM unavailable")
        for k, c in enumerate(part):
            row = {}
            for j, d in enumerate(dests):
                dur, dist = r["durations"][k][j], r["distances"][k][j]
                if dur is None or dist is None:  # OSRM found no route: the engine falls back to straight-line km
                    print(f"warning: no OSRM route {c['id']} -> {d[0]}; skipped (straight-line fallback)")
                    continue
                row[d[0]] = [round(dur, 1), round(dist, 1)]
            out[c["id"]] = row
        print(f"matrix rows {i + len(part)}/{len(pop)}")
        time.sleep(1.5)  # be polite to the demo server
    return out


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("homes", "all"):
        fetch_homes()
    if what in ("matrix", "all"):
        fetch_matrix()
