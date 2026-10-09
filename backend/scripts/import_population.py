"""Import an external citizen dataset (CSV or JSON) into data/population.json.

Columns/keys follow the Citizen schema (backend/app/models.py). Booleans accept true/false/1/0/yes/no.
Missing optional fields are filled deterministically (seed 42): id, names, gender-matched names,
lat/lng (jittered around the area centroid), helper relation. Tags are always re-derived with the
official rules, never taken from the file. Every row is validated with the Citizen model.

    python -m scripts.import_population path/to/citizens.csv
    python -m app.data.fetch_map_data matrix      # then refresh OSRM times for the new homes
    python -m scripts.pick_heroes                 # and re-pick heroes
"""
import csv
import json
import random
import sys
from pathlib import Path

from app.data import seed
from app.models import Citizen
from app.sim import world

BOOL = {"true": True, "1": True, "yes": True, "y": True, "false": False, "0": False, "no": False, "n": False, "": False}
AREA_ALIASES = {a["name_en"].lower(): a["id"] for a in world.areas().values()} | \
               {a["name_ar"]: a["id"] for a in world.areas().values()} | {k: k for k in world.areas()}


def _rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        d = json.loads(path.read_text(encoding="utf-8-sig"))
        return d["citizens"] if isinstance(d, dict) else d
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _b(v) -> bool:
    return v if isinstance(v, bool) else BOOL[str(v).strip().lower()]


def _none(v):
    return None if v is None or str(v).strip() in ("", "null", "None", "nan") else v


def convert(rows: list[dict]) -> list[dict]:
    rng = random.Random(42)
    out = []
    for n, r in enumerate(rows, 1):
        area = AREA_ALIASES.get(str(r["area"]).strip().lower(), AREA_ALIASES.get(str(r["area"]).strip()))
        if area is None:
            raise ValueError(f"row {n}: unknown area {r['area']!r}; valid: {sorted(world.areas())}")
        a = world.areas()[area]
        gender = str(r.get("gender", "m")).strip().lower()[0]
        name_ar, name_en = rng.choice(seed.NAMES_F if gender == "f" else seed.NAMES_M)
        works = _b(r.get("works", False))
        has_helper = _b(r.get("has_helper", False))
        c = {
            "id": _none(r.get("id")) or f"c_{n:04d}",
            "name_ar": _none(r.get("name_ar")) or name_ar, "name_en": _none(r.get("name_en")) or name_en,
            "age": int(float(r["age"])), "gender": gender, "area": area,
            "lat": float(_none(r.get("lat")) or a["lat"] + rng.gauss(0, 0.0055)),
            "lng": float(_none(r.get("lng")) or a["lng"] + rng.gauss(0, 0.0065)),
            "mobility": str(r.get("mobility", "none")).strip().lower() or "none",
            "has_car": _b(r.get("has_car", False)), "has_smartphone": _b(r.get("has_smartphone", False)),
            "digital_literacy": str(r.get("digital_literacy", "medium")).strip().lower(),
            "works": works,
            "work_start": (_none(r.get("work_start")) or "08:00") if works else None,
            "work_end": (_none(r.get("work_end")) or "16:00") if works else None,
            "income_band": str(r.get("income_band", "middle")).strip().lower(),
            "has_helper": has_helper,
            "helper_relation_ar": _none(r.get("helper_relation_ar")),
            "helper_relation_en": _none(r.get("helper_relation_en")),
        }
        c["lat"], c["lng"] = round(c["lat"], 5), round(c["lng"], 5)
        if has_helper and not c["helper_relation_ar"]:
            c["helper_relation_ar"], c["helper_relation_en"] = seed.helper_relation(rng, c["age"], gender)
        if not has_helper:
            c["helper_relation_ar"] = c["helper_relation_en"] = None
        c["tags"] = seed.derive_tags(c)
        Citizen.model_validate(c)
        out.append(c)
    ids = [c["id"] for c in out]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate citizen ids")
    return out


def main(path: str) -> None:
    pop = convert(_rows(Path(path)))
    (world.DATA_DIR / "population.json").write_text(json.dumps(pop, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(seed.summary(pop), indent=1))
    print("Now run: python -m app.data.fetch_map_data matrix  &&  python -m scripts.pick_heroes")


if __name__ == "__main__":
    main(sys.argv[1])
