"""Give every synthetic citizen one regular everyday trip (seed 42, deterministic) -> daily_trips.json.

    python -m app.data.seed_daily

Rules (all ASSUMPTION, synthetic):
- Workers commute to a work hub Sun-Thu (5 round trips a week). The hub is drawn with probability
  proportional to weight × exp(-km / WORK_DECAY_KM): bigger and nearer job areas are likelier.
- Students (18-24, not working) go to a university Sun-Thu, drawn the same way with UNI_DECAY_KM.
- Adults 25+ who don't work make a weekly round trip to their nearest public hospital (straight-line).
- 16-17-year-olds go to a local school on foot: no road trip.
How they travel (car, bus, taxi, a helper's car) is decided by the engine from the citizen's profile (sim/daily.py).
Re-run after the population or hubs change, then rebuild the road data (fetch_roads.py hubs + build).
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent
SEED = 42
WORK_DECAY_KM = 8.0    # ASSUMPTION: most commutes in Amman stay within ~10-15 km
UNI_DECAY_KM = 12.0    # ASSUMPTION: students travel further for their university
DAYS = {"work": 5, "university": 5, "hospital": 1}


def _km(a_lat, a_lng, b_lat, b_lng) -> float:
    return math.hypot((a_lat - b_lat) * 111.0, (a_lng - b_lng) * 111.0 * math.cos(math.radians(a_lat)))


def assign(pop: list[dict], hubs: list[dict]) -> dict:
    rng = random.Random(SEED)
    by_kind = {k: [h for h in hubs if h["kind"] == k] for k in ("work", "university", "hospital")}
    out = {}
    for c in pop:
        if c["works"]:
            kind, decay = "work", WORK_DECAY_KM
        elif "student" in c["tags"]:
            kind, decay = "university", UNI_DECAY_KM
        elif c["age"] >= 25:
            kind, decay = "hospital", None
        else:
            continue
        cands = by_kind[kind]
        if decay is None:
            hub = min(cands, key=lambda h: (_km(c["lat"], c["lng"], h["lat"], h["lng"]), h["id"]))
        else:
            w = [h["weight"] * math.exp(-_km(c["lat"], c["lng"], h["lat"], h["lng"]) / decay) for h in cands]
            hub = rng.choices(cands, weights=w, k=1)[0]
        out[c["id"]] = {"purpose": kind, "hub": hub["id"], "days_per_week": DAYS[kind]}
    return out


def main() -> None:
    pop = json.loads((DATA / "population.json").read_text(encoding="utf-8"))
    hubs = json.loads((DATA / "hubs.json").read_text(encoding="utf-8"))["hubs"]
    trips = assign(pop, hubs)
    (DATA / "daily_trips.json").write_text(json.dumps({
        "_source": "app/data/seed_daily.py, seed 42. SYNTHETIC: one regular trip per citizen, see the rules in that file.",
        "_format": "citizen_id -> {purpose: work|university|hospital, hub: id in hubs.json, days_per_week}",
        "trips": trips}, ensure_ascii=False, indent=0), encoding="utf-8")
    from collections import Counter
    print("trips:", len(trips), Counter(t["purpose"] for t in trips.values()))
    print("hubs:", Counter(t["hub"] for t in trips.values()).most_common())


if __name__ == "__main__":
    main()
