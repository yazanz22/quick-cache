"""Give every synthetic citizen a health-insurance status (seed 42, deterministic) -> population.json in place.

    python -m app.data.seed_insurance

Rule (ASSUMPTION, synthetic): a citizen is UNINSURED with probability UNINSURED_RATE_BY_BAND[income_band]
(sim/assumptions.py: low 0.65, middle 0.45, high 0.20, frozen before any medical-exemption scenario ran), drawn with
random.Random(42) once per citizen in id order. The result sets `has_health_insurance` (False = uninsured) and appends
the "uninsured" tag LAST, keeping every other tag exactly as it was and in the same order. Re-running is idempotent:
the field and the tag are recomputed from scratch.

Only the medical_exemption engine reads them (eligible = "uninsured" in tags); the id_renewal and everyday_travel
engines ignore both, so their outcomes do not move. Run it again after `seed_census --install` (which rewrites
population.json without these fields). data/census/* is not touched.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from ..sim.assumptions import DEFAULT

DATA = Path(__file__).resolve().parent
SEED = 42
TAG = "uninsured"


def assign(pop: list[dict], rates: dict | None = None) -> list[dict]:
    """New citizen dicts with has_health_insurance (placed right after "tags") and the uninsured tag."""
    rates = rates or DEFAULT.UNINSURED_RATE_BY_BAND
    rng = random.Random(SEED)
    out = []
    for c in sorted(pop, key=lambda c: c["id"]):
        uninsured = rng.random() < rates[c["income_band"]]
        tags = [t for t in c["tags"] if t != TAG] + ([TAG] if uninsured else [])
        row = {}
        for k, v in c.items():
            if k == "has_health_insurance":
                continue
            row[k] = tags if k == "tags" else v
            if k == "tags":
                row["has_health_insurance"] = not uninsured
        out.append(row)
    order = {c["id"]: i for i, c in enumerate(pop)}  # keep the file's own order
    return sorted(out, key=lambda c: order[c["id"]])


def shares(pop: list[dict]) -> dict:
    n = Counter(c["income_band"] for c in pop)
    u = Counter(c["income_band"] for c in pop if not c["has_health_insurance"])
    out = {b: round(100.0 * u[b] / n[b], 1) for b in sorted(n)}
    out["all"] = round(100.0 * sum(u.values()) / len(pop), 1)
    return out


def main() -> None:
    path = DATA / "population.json"
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    pop = assign(json.loads(raw.decode("utf-8")))
    text = json.dumps(pop, ensure_ascii=False, indent=1)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    n_u = sum(not c["has_health_insurance"] for c in pop)
    print(f"uninsured: {n_u} of {len(pop)}; % by band: {shares(pop)}")


if __name__ == "__main__":
    main()
