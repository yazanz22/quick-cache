"""One-time build of the road-closure data. Run while online; outputs are committed so the engine
never routes or calls an API at simulate time (deterministic, offline-safe).

    python -m app.data.fetch_roads network   # Overpass -> data/_raw/road_network.json (gitignored, ~1 min)
    python -m app.data.fetch_roads build     # roads.json + road_deltas.json (pure Python routing, a few minutes)

How a closure is modelled:
1. The drivable OpenStreetMap network of Greater Amman is turned into a routing graph (one-way streets respected,
   free-flow speeds per road class, see SPEED_KMH). Turn restrictions are ignored.
2. Each catalogue road is identified by its OSM Arabic name (all ways with that exact name, plus any listed
   variants). Bridges and tunnels of OTHER streets crossing it stay open.
3. For every citizen and every destination in travel_matrix.json (15 sites + 8 area centres), and for each citizen's
   everyday-trip hub (daily_trips.json, hub_matrix.json), we route twice on this graph: with all roads open, and with the road's ways removed. The difference (extra seconds, extra metres) is
   the closure's detour. The engine adds it on top of the OSRM time and distance it already uses, so a closure
   never changes trips that don't use the road, and the open-road numbers stay exactly as before.
4. Detour metres are clamped at 0 (a detour can be shorter but slower; a closure never makes a trip cheaper).

Data © OpenStreetMap contributors, ODbL. Routing is our own (Dijkstra in pure Python), not a third-party service.
"""
from __future__ import annotations

import heapq
import json
import math
import sys
import time
from datetime import date
from pathlib import Path

from .fetch_map_data import overpass

DATA = Path(__file__).resolve().parent
RAW = DATA / "_raw" / "road_network.json"
BBOX = (31.70, 35.72, 32.10, 36.12)  # south, west, north, east: citizens, sites, areas and hubs (airport) + a margin

DRIVE = ("motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|"
         "motorway_link|trunk_link|primary_link|secondary_link|tertiary_link")
# Free-flow speeds used only to find the best route on our graph (the detour); the engine's own travel
# times still come from OSRM × TRAFFIC_FACTOR. Round values in the spirit of OSRM's car profile.
SPEED_KMH = {"motorway": 80, "trunk": 65, "primary": 50, "secondary": 40, "tertiary": 35, "unclassified": 30,
             "residential": 25, "living_street": 10, "motorway_link": 45, "trunk_link": 40, "primary_link": 35,
             "secondary_link": 30, "tertiary_link": 25}
SNAP_CLASSES = {"tertiary", "unclassified", "residential", "living_street"}  # homes and offices sit on local streets
MIN_DELTA_S = 1.0  # store only detours of at least a second
# Zarqa city (east) and the towns south of Amman (Na'ur, Madaba) have their own streets named Queen Rania, Army,
# Prince Al-Hasan, Al-Quds...; a road only includes ways inside Amman unless it sets its own "max_lng" / "min_lat"
# (the Amman-Zarqa highway runs east, Airport Road runs south to the airport).
AMMAN_MAX_LNG = 36.05
AMMAN_MIN_LAT = 31.82

# The catalogue: 18 major Amman roads. `osm` = exact OSM `name` values (Arabic) of the ways that make up the road.
ROADS = [
    {"id": "airport_road", "name_ar": "طريق المطار", "name_en": "Airport Road",
     "osm": ["شارع مطار الملكة علياء"], "min_lat": 31.70},
    {"id": "zahran", "name_ar": "شارع زهران", "name_en": "Zahran Street", "osm": ["شارع زهران"]},
    {"id": "queen_rania", "name_ar": "شارع الملكة رانيا", "name_en": "Queen Rania Street",
     "osm": ["شارع الملكة رانيا العبد الله", "شارع الملكة رانيا العبدالله"]},
    {"id": "mecca", "name_ar": "شارع مكة المكرمة", "name_en": "Mecca Street", "osm": ["شارع مكة المكرمة"]},
    {"id": "medina", "name_ar": "شارع المدينة المنورة", "name_en": "Medina Street", "osm": ["شارع المدينة المنورة"]},
    {"id": "gardens", "name_ar": "شارع وصفي التل (الجاردنز)", "name_en": "Wasfi Al-Tal St (Gardens)",
     "osm": ["شارع الشهيد وصفي التل"]},
    {"id": "prince_hashem", "name_ar": "شارع الأمير هاشم", "name_en": "Prince Hashem Street",
     "osm": ["شارع الأمير هاشم بن الحسين"]},
    {"id": "al_quds", "name_ar": "شارع القدس", "name_en": "Al-Quds Street", "osm": ["شارع القدس"]},
    {"id": "army", "name_ar": "شارع الجيش", "name_en": "Army Street", "osm": ["شارع الجيش"]},
    {"id": "al_hurriya", "name_ar": "شارع الحرية", "name_en": "Al-Hurriya Street", "osm": ["شارع الحرية"]},
    {"id": "king_abdullah_ii", "name_ar": "شارع الملك عبدالله الثاني", "name_en": "King Abdullah II Street",
     "osm": ["شارع الملك عبدالله بن الحسين الثاني"]},
    {"id": "jordan_street", "name_ar": "شارع الأردن", "name_en": "Jordan Street", "osm": ["شارع الأردن"]},
    {"id": "al_istiqlal", "name_ar": "شارع الاستقلال", "name_en": "Al-Istiqlal Street", "osm": ["شارع الاستقلال"]},
    {"id": "al_shaheed", "name_ar": "شارع الشهيد", "name_en": "Al-Shaheed Street", "osm": ["شارع الشهيد"]},
    {"id": "amman_zarqa", "name_ar": "أوتوستراد عمّان - الزرقاء", "name_en": "Amman-Zarqa Highway",
     "osm": ["أوتوستراد عمان - الزرقاء"], "max_lng": 36.2},
    {"id": "al_salt", "name_ar": "شارع السلط", "name_en": "Al-Salt Street", "osm": ["شارع السلط"]},
    {"id": "yajouz", "name_ar": "شارع ياجوز", "name_en": "Yajouz Street", "osm": ["شارع ياجوز"]},
    {"id": "prince_hasan", "name_ar": "شارع الأمير الحسن", "name_en": "Prince Al-Hasan Street",
     "osm": ["شارع الأمير الحسن"]},
]


# --------------------------------------------------------------------- fetch

def fetch_network() -> None:
    s, w, n, e = BBOX
    q = f"""[out:json][timeout:300][maxsize:1073741824];
way["highway"~"^({DRIVE})$"]["access"!~"^(private|no)$"]({s},{w},{n},{e});
out body;
>;
out skel qt;"""
    t0 = time.time()
    els = overpass(q)
    nodes = {x["id"]: [round(x["lat"], 6), round(x["lon"], 6)] for x in els if x["type"] == "node"}
    ways = [{"id": x["id"], "nodes": x["nodes"],
             "tags": {k: v for k, v in x.get("tags", {}).items()
                      if k in ("highway", "name", "name:en", "oneway", "junction", "maxspeed")}}
            for x in els if x["type"] == "way"]
    RAW.parent.mkdir(exist_ok=True)
    RAW.write_text(json.dumps({"_source": "OpenStreetMap via Overpass API, ODbL", "_fetched": date.today().isoformat(),
                               "bbox": BBOX, "nodes": nodes, "ways": ways}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"network: {len(ways)} ways, {len(nodes)} nodes in {time.time() - t0:.0f} s -> {RAW}")


# --------------------------------------------------------------------- graph

def _meters(a, b) -> float:
    lat = math.radians((a[0] + b[0]) / 2)
    dy = (b[0] - a[0]) * 111_195.0
    dx = (b[1] - a[1]) * 111_195.0 * math.cos(lat)
    return math.hypot(dx, dy)


def _speed(tags: dict) -> float:
    ms = (tags.get("maxspeed") or "").split(" ")[0]
    if ms.isdigit() and 5 <= int(ms) <= 120:
        return min(float(ms), SPEED_KMH.get(tags["highway"], 30) * 1.25)
    return float(SPEED_KMH.get(tags["highway"], 30))


def _road_of(name: str | None, lat: float, lng: float) -> int:
    """Catalogue index of a way (by its OSM name and position), or -1 for any other street."""
    for i, r in enumerate(ROADS):
        if name in r["osm"] and lng <= r.get("max_lng", AMMAN_MAX_LNG) and lat >= r.get("min_lat", AMMAN_MIN_LAT):
            return i
    return -1


class Graph:
    """Contracted graph: vertices are way endpoints and shared nodes (intersections). Edges carry seconds,
    metres and the catalogue road index (-1 for other streets). `rev[v]` holds edges INTO v, so a Dijkstra
    from a destination over `rev` gives every vertex's time TO that destination."""

    def __init__(self, raw: dict):
        coords = {int(k): v for k, v in raw["nodes"].items()}
        ways = [w for w in raw["ways"] if all(n in coords for n in w["nodes"]) and len(w["nodes"]) > 1]
        use: dict[int, int] = {}
        for w in ways:
            for n in w["nodes"]:
                use[n] = use.get(n, 0) + 1
        key = set()
        for w in ways:
            key.add(w["nodes"][0]); key.add(w["nodes"][-1])
            key.update(n for n in w["nodes"] if use[n] > 1)
        self.osm_ids = sorted(key)
        idx = {n: i for i, n in enumerate(self.osm_ids)}
        self.coords = [coords[n] for n in self.osm_ids]
        self.rev: list[list[tuple[int, float, float, int]]] = [[] for _ in self.osm_ids]
        self.fwd: list[list[int]] = [[] for _ in self.osm_ids]
        self.snap_ok = [False] * len(self.osm_ids)
        self.on_road = [False] * len(self.osm_ids)
        self.road_ways: dict[int, list[list[list[float]]]] = {i: [] for i in range(len(ROADS))}
        n_edges = 0
        for w in ways:
            t = w["tags"]
            hw = t["highway"]
            r = _road_of(t.get("name"), sum(coords[n][0] for n in w["nodes"]) / len(w["nodes"]),
                         sum(coords[n][1] for n in w["nodes"]) / len(w["nodes"]))
            ow = t.get("oneway")
            forward_only = ow in ("yes", "true", "1") or hw == "motorway" or t.get("junction") in ("roundabout", "circular")
            backward_only = ow == "-1"
            if ow == "no":
                forward_only = False
            v_ms = _speed(t) / 3.6
            if r >= 0:
                self.road_ways[r].append([coords[n] for n in w["nodes"]])
            seg_start, m = w["nodes"][0], 0.0
            for a, b in zip(w["nodes"], w["nodes"][1:]):
                m += _meters(coords[a], coords[b])
                if b not in key:
                    continue
                u, v = idx[seg_start], idx[b]
                s = m / v_ms
                if not backward_only:
                    self.rev[v].append((u, s, m, r)); self.fwd[u].append(v)
                if not forward_only:
                    self.rev[u].append((v, s, m, r)); self.fwd[v].append(u)
                n_edges += 1
                for x in (u, v):
                    if r >= 0:
                        self.on_road[x] = True
                    elif hw in SNAP_CLASSES:
                        self.snap_ok[x] = True
                seg_start, m = b, 0.0
        print(f"graph: {len(self.osm_ids)} vertices, {n_edges} segments")
        self.main = self._largest_scc()
        print(f"largest strongly connected component: {sum(self.main)} vertices")
        self._grid = {}
        for i, (lat, lng) in enumerate(self.coords):
            if self.snap_ok[i] and not self.on_road[i] and self.main[i]:
                self._grid.setdefault((int(lat / 0.005), int(lng / 0.005)), []).append(i)

    def _largest_scc(self) -> list[bool]:
        """Kosaraju, iterative. fwd = out-edges, rev = in-edges."""
        n = len(self.coords)
        seen, order = [False] * n, []
        for s in range(n):
            if seen[s]:
                continue
            seen[s] = True
            stack = [(s, iter(self.fwd[s]))]
            while stack:
                v, it = stack[-1]
                nxt = next((w for w in it if not seen[w]), None)
                if nxt is None:
                    order.append(v); stack.pop()
                else:
                    seen[nxt] = True
                    stack.append((nxt, iter(self.fwd[nxt])))
        comp = [-1] * n
        sizes = []
        for s in reversed(order):
            if comp[s] >= 0:
                continue
            c = len(sizes); comp[s] = c; size = 0
            stack = [s]
            while stack:
                v = stack.pop(); size += 1
                for u, *_ in self.rev[v]:
                    if comp[u] < 0:
                        comp[u] = c; stack.append(u)
            sizes.append(size)
        big = max(range(len(sizes)), key=sizes.__getitem__)
        return [c == big for c in comp]

    def snap(self, lat: float, lng: float) -> int:
        gi, gj = int(lat / 0.005), int(lng / 0.005)
        for r in range(1, 12):
            cands = [v for di in range(-r, r + 1) for dj in range(-r, r + 1) for v in self._grid.get((gi + di, gj + dj), [])]
            if cands:
                return min(cands, key=lambda v: (_meters((lat, lng), self.coords[v]), v))
        raise RuntimeError(f"no snappable vertex near {lat},{lng}")

    def to_target(self, target: int, closed: int = -1) -> tuple[list[float], list[float]]:
        """Seconds and metres of the fastest route from every vertex TO target, avoiding road `closed`."""
        INF = math.inf
        sec, met = [INF] * len(self.coords), [INF] * len(self.coords)
        sec[target], met[target] = 0.0, 0.0
        pq = [(0.0, 0.0, target)]
        rev = self.rev
        while pq:
            s, m, v = heapq.heappop(pq)
            if s > sec[v]:
                continue
            for u, es, em, r in rev[v]:
                if r == closed and r >= 0:
                    continue
                ns = s + es
                if ns < sec[u]:
                    sec[u], met[u] = ns, m + em
                    heapq.heappush(pq, (ns, m + em, u))
        return sec, met

    def route(self, src: int, target: int, closed: int = -1) -> tuple[list[int], float]:
        """Vertices of the fastest route src -> target avoiding road `closed`, and its free-flow seconds."""
        INF = math.inf
        sec, par = [INF] * len(self.coords), [-1] * len(self.coords)
        sec[target] = 0.0
        pq = [(0.0, target)]
        while pq:
            s, v = heapq.heappop(pq)
            if s > sec[v]:
                continue
            if v == src:
                break
            for u, es, em, r in self.rev[v]:
                if r == closed and r >= 0:
                    continue
                if s + es < sec[u]:
                    sec[u], par[u] = s + es, v
                    heapq.heappush(pq, (s + es, u))
        if not math.isfinite(sec[src]):
            return [], INF
        path, v = [src], src
        while v != target:
            v = par[v]
            path.append(v)
        return path, sec[src]


# --------------------------------------------------------------------- build

def _simplify(line: list[list[float]], step_m: float = 60.0) -> list[list[float]]:
    out = [line[0]]
    for p in line[1:-1]:
        if _meters(out[-1], p) >= step_m:
            out.append(p)
    out.append(line[-1])
    return [[round(a, 5), round(b, 5)] for a, b in out]


def build() -> None:
    t0 = time.time()
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    g = Graph(raw)
    pop = json.loads((DATA / "population.json").read_text(encoding="utf-8"))
    sites = json.loads((DATA / "sites.json").read_text(encoding="utf-8"))["sites"]
    areas = json.loads((DATA / "areas.json").read_text(encoding="utf-8"))["areas"]
    dests = [(s["id"], s["lat"], s["lng"]) for s in sites] + [(f"area:{a['id']}", a["lat"], a["lng"]) for a in areas]
    # Everyday-trip hubs: only the citizens assigned to each hub need its detours.
    hubs = json.loads((DATA / "hubs.json").read_text(encoding="utf-8"))["hubs"]
    trips = json.loads((DATA / "daily_trips.json").read_text(encoding="utf-8"))["trips"]
    dests += [(f"hub:{h['id']}", h["lat"], h["lng"]) for h in hubs]
    who = {f"hub:{h['id']}": {cid for cid, t in trips.items() if t["hub"] == h["id"]} for h in hubs}
    home = [g.snap(c["lat"], c["lng"]) for c in pop]
    dest_v = {d: g.snap(lat, lng) for d, lat, lng in dests}

    catalogue = []
    for i, r in enumerate(ROADS):
        lines = g.road_ways[i]
        km = sum(_meters(a, b) for ln in lines for a, b in zip(ln, ln[1:])) / 1000
        catalogue.append({"id": r["id"], "name_ar": r["name_ar"], "name_en": r["name_en"], "osm_names": r["osm"],
                          "osm_ways": len(lines), "km": round(km, 1), "lines": [_simplify(ln) for ln in lines]})
        print(f"  {r['id']:18s} {len(lines):4d} ways {km:6.1f} km")
        if not lines:
            raise RuntimeError(f"road {r['id']} not found in OSM; fix its name")

    deltas: dict[str, dict[str, dict[str, list[float]]]] = {r["id"]: {} for r in ROADS}
    cut = {r["id"]: 0 for r in ROADS}
    for d, v in dest_v.items():
        open_s, open_m = g.to_target(v)
        for i, r in enumerate(ROADS):
            cs, cm = g.to_target(v, closed=i)
            for c, h in zip(pop, home):
                if d in who and c["id"] not in who[d]:
                    continue
                if not math.isfinite(open_s[h]):
                    continue
                if not math.isfinite(cs[h]):
                    cut[r["id"]] += 1  # home opens onto the road: residents keep local access, no detour stored
                    continue
                ds = cs[h] - open_s[h]
                if ds >= MIN_DELTA_S:
                    dm = max(0.0, cm[h] - open_m[h])
                    deltas[r["id"]].setdefault(c["id"], {})[d] = [round(ds, 1), round(dm, 1)]
        print(f"  {d:28s} done ({time.time() - t0:.0f} s)")

    meta = {"_source": "OpenStreetMap via Overpass API (ODbL), routed with our own Dijkstra in app/data/fetch_roads.py",
            "_fetched": raw["_fetched"], "_built": date.today().isoformat()}
    (DATA / "roads.json").write_text(json.dumps({
        **meta, "_note": "Catalogue of closable major roads. lines = simplified OSM geometry [lat, lng] for the map.",
        "speeds_kmh": SPEED_KMH, "roads": catalogue}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DATA / "road_deltas.json").write_text(json.dumps({
        **meta, "_format": "road_id -> citizen_id -> destination -> [extra_seconds, extra_meters] when that road alone is "
                           "closed (free-flow; the engine scales seconds by TRAFFIC_FACTOR like OSRM times). "
                           "Missing = no detour. unreachable_pairs: homes with no other way out keep local access (no detour).",
        "unreachable_pairs": cut, "deltas": deltas}, separators=(",", ":")), encoding="utf-8")
    n = sum(len(x) for r in deltas.values() for x in r.values())
    print(f"saved roads.json and road_deltas.json: {n} citizen-destination detours, unreachable {sum(cut.values())}, "
          f"{time.time() - t0:.0f} s")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("network", "all"):
        fetch_network()
    if what in ("build", "all"):
        build()
