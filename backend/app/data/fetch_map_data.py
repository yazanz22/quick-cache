"""One-time fetch of real map data. Run while online; outputs are committed so the
engine never calls an API at simulate time (deterministic, offline-safe).

    python -m app.data.fetch_map_data stops     # Overpass -> bus_stops.json, cspd_offices.json
    python -m app.data.fetch_map_data matrix    # OSRM     -> travel_matrix.json

Data © OpenStreetMap contributors, ODbL. Routing by the public OSRM demo server
(router.project-osrm.org), used lightly: ~10 table requests in total.
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
BBOX = (31.90, 35.79, 32.06, 36.03)  # south, west, north, east: covers the 8 areas


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


def fetch_stops() -> None:
    s, w, n, e = BBOX
    q = f"""[out:json][timeout:90];
(
  node["highway"="bus_stop"]({s},{w},{n},{e});
  node["public_transport"="platform"]["bus"="yes"]({s},{w},{n},{e});
  node["public_transport"="stop_position"]["bus"="yes"]({s},{w},{n},{e});
);
out;"""
    els = overpass(q)
    stops = sorted({(round(x["lat"], 5), round(x["lon"], 5)) for x in els})
    (DATA / "bus_stops.json").write_text(json.dumps({
        "_source": "OpenStreetMap via Overpass API, ODbL. highway=bus_stop + bus platforms/stop positions.",
        "_fetched": date.today().isoformat(), "bbox": BBOX, "count": len(stops),
        "stops": [[a, b] for a, b in stops]}, indent=0), encoding="utf-8")
    print("bus stops:", len(stops))

    q2 = """[out:json][timeout:90];
(
  nwr["name"~"أحوال المدنية|الأحوال المدنية|Civil Status|Civil Registry",i](31.80,35.70,32.15,36.10);
  nwr["name:en"~"Civil Status|Civil Registry",i](31.80,35.70,32.15,36.10);
);
out center tags;"""
    offices = []
    for x in overpass(q2):
        lat = x.get("lat") or x.get("center", {}).get("lat")
        lon = x.get("lon") or x.get("center", {}).get("lon")
        t = x.get("tags", {})
        offices.append({"osm": f'{x["type"]}/{x["id"]}', "lat": lat, "lng": lon,
                        "name": t.get("name"), "name_en": t.get("name:en"), "tags": t})
    (DATA / "cspd_offices.json").write_text(json.dumps({
        "_source": "OpenStreetMap via Overpass API, ODbL. Features named like Civil Status offices.",
        "_fetched": date.today().isoformat(), "offices": offices}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("civil status features:", len(offices))
    for o in offices:
        print(" ", o["osm"], o["lat"], o["lng"], o["name"], "|", o["name_en"])


def fetch_matrix() -> None:
    """Driving duration (s) and distance (m) from every citizen to every site and area centroid."""
    pop = json.loads((DATA / "population.json").read_text(encoding="utf-8"))
    sites = json.loads((DATA / "sites.json").read_text(encoding="utf-8"))["sites"]
    areas = json.loads((DATA / "areas.json").read_text(encoding="utf-8"))["areas"]
    dests = [(s["id"], s["lat"], s["lng"]) for s in sites] + [(f"area:{a['id']}", a["lat"], a["lng"]) for a in areas]
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
            out[c["id"]] = {d[0]: [round(r["durations"][k][j], 1), round(r["distances"][k][j], 1)]
                            for j, d in enumerate(dests)}
        print(f"matrix rows {i + len(part)}/{len(pop)}")
        time.sleep(1.5)  # be polite to the demo server
    (DATA / "travel_matrix.json").write_text(json.dumps({
        "_source": "OSRM public demo server (router.project-osrm.org), OpenStreetMap data, ODbL. Free-flow car times.",
        "_fetched": date.today().isoformat(),
        "_format": "citizen_id -> destination -> [duration_seconds, distance_meters]; destinations are site ids and area:<id> centroids",
        "matrix": out}, separators=(",", ":")), encoding="utf-8")
    print("saved travel_matrix.json")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("stops", "all"):
        fetch_stops()
    if what in ("matrix", "all"):
        fetch_matrix()
