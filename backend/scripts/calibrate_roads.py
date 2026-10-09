"""Calibrate road-closure detours against real typical traffic (TomTom Routing API). Run online, once.

    python -m scripts.calibrate_roads [--samples 15] [road_id ...]

Our own routing (app/data/fetch_roads.py) finds each closure's detour on the OSM network with round default speeds
per road class. TomTom has measured speeds for each road segment, so for each road this script takes a seeded
sample of trips that the closure lengthens, rebuilds BOTH our open route and our detour route on TomTom
(supportingPoints: TomTom follows our path, it doesn't pick its own) and reads TomTom's travel times. Then

    factor = sum(TomTom detour) / sum(our detour)          (both without traffic)

and the engine scales that road's detours by it (world.road_calibration); daytime traffic is then the same frozen
TRAFFIC_FACTOR as every other trip. TomTom has NO traffic data for Amman (checked 2026-10-09: no-traffic, historic
and live times are identical at 03:00 and 08:00, while Dubai's differ), so congestion from diverted traffic is still
not modelled; the historic-traffic time is recorded anyway in case coverage appears. Only the aggregate factors and sample
statistics are saved (data/road_calibration.json); raw responses stay in data/_raw/tomtom/ (gitignored) so a re-run
never calls TomTom twice for the same trip. Needs TOMTOM_API_KEY in the repo-root .env (free plan: 2,500 calls/day;
19 roads × 15 trips × 2 routes ≈ 570 calls).
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

from app import config
from app.data.fetch_roads import RAW, ROADS, Graph
from app.sim import world
from app.sim.assumptions import DEFAULT

API = "https://api.tomtom.com/routing/1/calculateRoute/{a}:{b}/json"
CACHE = RAW.parent / "tomtom"
MIN_DETOUR_S = 60.0       # sample trips the closure lengthens by at least a minute (free-flow)
FACTOR_RANGE = (0.5, 6.0)
SEED = 42


def next_sunday_8am() -> str:
    amman = timezone(timedelta(hours=3))
    now = datetime.now(amman)
    days = (6 - now.weekday()) % 7 or 7          # Monday=0 ... Sunday=6
    d = (now + timedelta(days=days)).replace(hour=8, minute=0, second=0, microsecond=0)
    return d.isoformat()


def tomtom(points: list[list[float]], depart: str, key: str) -> dict:
    """Travel time along exactly these points (route reconstruction), with traffic for `depart`."""
    pts = points[:1] + [p for i, p in enumerate(points[1:-1], 1) if i % max(1, len(points) // 150) == 0] + points[-1:]
    h = hashlib.sha256(json.dumps([pts, depart[:10] and "sun08"]).encode()).hexdigest()[:24]
    f = CACHE / f"{h}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    a, b = pts[0], pts[-1]
    url = (API.format(a=f"{a[0]},{a[1]}", b=f"{b[0]},{b[1]}") + f"?key={key}&traffic=true&travelMode=car"
           f"&routeType=fastest&computeTravelTimeFor=all&departAt={urllib.parse.quote(depart)}")
    body = json.dumps({"supportingPoints": [{"latitude": p[0], "longitude": p[1]} for p in pts]}).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=30).read())
            s = r["routes"][0]["summary"]
            out = {k: s.get(k) for k in ("lengthInMeters", "travelTimeInSeconds", "noTrafficTravelTimeInSeconds",
                                          "historicTrafficTravelTimeInSeconds", "liveTrafficIncidentsTravelTimeInSeconds")}
            CACHE.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(out), encoding="utf-8")
            time.sleep(0.25)  # free plan: at most 5 calls per second
            return out
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:200]
            if e.code in (403, 429) and attempt < 2:
                print("  tomtom", e.code, msg); time.sleep(5); continue
            raise RuntimeError(f"TomTom HTTP {e.code}: {msg}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:  # network hiccup: wait and retry
            print("  tomtom network", type(e).__name__)
            time.sleep(5)
    raise RuntimeError("TomTom unavailable")


def main() -> None:
    key = config.env("TOMTOM_API_KEY")
    if not key:
        sys.exit("TOMTOM_API_KEY is missing from the repo-root .env")
    args = sys.argv[1:]
    n = 15
    if "--samples" in args:
        i = args.index("--samples"); n = int(args[i + 1]); del args[i:i + 2]
    only = set(args)
    depart = next_sunday_8am()
    print("departAt", depart)

    g = Graph(json.loads(RAW.read_text(encoding="utf-8")))
    pop = world.population_by_id()
    dest_ll = {s["id"]: (s["lat"], s["lng"]) for s in world.sites().values()}
    dest_ll |= {f"area:{a['id']}": (a["lat"], a["lng"]) for a in world.areas().values()}
    dest_ll |= {f"hub:{h['id']}": (h["lat"], h["lng"]) for h in world.hubs().values()}
    deltas = world.road_deltas()
    tf = DEFAULT.TRAFFIC_FACTOR

    out_path = config.DATA_DIR / "road_calibration.json"
    saved = json.loads(out_path.read_text(encoding="utf-8"))["roads"] if out_path.exists() else {}
    for ri, r in enumerate(ROADS):
        if only and r["id"] not in only:
            continue
        pairs = sorted((cid, d) for cid, per in deltas.get(r["id"], {}).items() for d, v in per.items()
                       if v[0] >= MIN_DETOUR_S)
        # Prefer everyday trips (what the user cares about), then service trips; one trip per citizen.
        rng = random.Random(f"{SEED}:{r['id']}")
        rng.shuffle(pairs)
        pairs.sort(key=lambda p: not p[1].startswith("hub:"))
        seen, sample = set(), []
        for cid, d in pairs:
            if cid not in seen:
                seen.add(cid); sample.append((cid, d))
            if len(sample) == n:
                break
        rows = []
        for cid, d in sample:
            c = pop[cid]
            h, t = g.snap(c["lat"], c["lng"]), g.snap(*dest_ll[d])
            p_open, s_open = g.route(h, t)
            p_closed, s_closed = g.route(h, t, closed=ri)
            if not p_open or not p_closed:
                continue
            try:
                a = tomtom([g.coords[v] for v in p_open], depart, key)
                b = tomtom([g.coords[v] for v in p_closed], depart, key)
            except RuntimeError as e:
                print("  skip", cid, d, e)
                continue
            rows.append({"citizen": cid, "dest": d, "ours_s": round(s_closed - s_open, 1),
                         "tt_traffic_s": b["historicTrafficTravelTimeInSeconds"] - a["historicTrafficTravelTimeInSeconds"],
                         "tt_free_s": b["noTrafficTravelTimeInSeconds"] - a["noTrafficTravelTimeInSeconds"]})
        if not rows:
            # No trip the closure lengthens by a minute: use the median factor of the sampled roads.
            sampled = sorted(v["factor"] for k, v in saved.items() if v.get("samples"))
            if sampled:
                saved[r["id"]] = {"factor": sampled[len(sampled) // 2], "samples": 0,
                                  "note": "no trip long enough to sample; median factor of the other roads"}
            print(f"{r['id']:18s} no usable samples -> median factor {saved.get(r['id'], {}).get('factor')}")
            continue
        ours = sum(x["ours_s"] for x in rows)
        traffic = sum(x["tt_traffic_s"] for x in rows)
        free = sum(x["tt_free_s"] for x in rows)
        factor = min(max(free / ours, FACTOR_RANGE[0]), FACTOR_RANGE[1]) if ours > 0 else 1.0
        saved[r["id"]] = {"factor": round(factor, 2), "samples": len(rows),
                          "ours_free_flow_min": round(ours / 60 / len(rows), 1),
                          "tomtom_free_flow_min": round(free / 60 / len(rows), 1),
                          "tomtom_traffic_min": round(traffic / 60 / len(rows), 1)}
        print(f"{r['id']:18s} n={len(rows):2d} avg detour: ours {ours / 60 / len(rows):5.1f} min | TomTom "
              f"{free / 60 / len(rows):5.1f} (Sunday 08:00 traffic {traffic / 60 / len(rows):5.1f})  -> factor {factor:.2f}")
        out_path.write_text(json.dumps({
            "_source": "TomTom Routing API (calculateRoute with supportingPoints = our OSM routes): TomTom's measured road "
                       "speeds. TomTom has no traffic data for Amman. Made by scripts/calibrate_roads.py.",
            "_built": date.today().isoformat(), "_departAt": depart,
            "_format": "road id -> factor on that road's free-flow detour seconds (= TomTom detour / our detour on the "
                       "samples; the engine then applies TRAFFIC_FACTOR like every trip), plus sample averages per trip in minutes",
            "roads": saved}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
