"""Generates population.json deterministically (seed=42).

Run:  python -m app.data.seed

Every probability below is either read from anchors.json (status ANCHORED, with a
real source) or is a labelled SYNTHETIC ASSUMPTION. Per-area variation is always
a synthetic assumption. Names are generic first names, not real people.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent
N_CITIZENS = 800
SEED = 42

ANCHORS = json.loads((DATA / "anchors.json").read_text(encoding="utf-8"))["anchors"]
AREAS = json.loads((DATA / "areas.json").read_text(encoding="utf-8"))["areas"]


def anchor(key: str, fallback):
    """Use the sourced figure if one exists, else the labelled assumption."""
    a = ANCHORS.get(key) or {}
    if a.get("status") == "ANCHORED" and a.get("value") is not None and a.get("url"):
        return a["value"]
    return fallback


# --------------------------------------------------------------- assumptions
# Age bands of residents aged 16+ (ID-card age). ASSUMPTION unless anchored.
AGE_BANDS = [(16, 24, 0.22), (25, 34, 0.23), (35, 44, 0.19), (45, 54, 0.14),
             (55, 64, 0.10), (65, 74, 0.08), (75, 90, 0.04)]
SHARE_65_PLUS = anchor("share_65_plus_of_adults", None)  # rescales the 65+ bands if anchored
SHARE_FEMALE = anchor("share_female", 0.49)               # ASSUMPTION

# Per-area synthetic profile: (low-income shift, car multiplier, elderly multiplier). SYNTHETIC ASSUMPTION.
AREA_PROFILE = {
    "downtown":         (+0.15, 0.70, 1.4),
    "abdali":           (-0.05, 1.10, 0.9),
    "jabal_al_hussein": (+0.05, 0.90, 1.2),
    "marka":            (+0.15, 0.75, 1.1),
    "wehdat":           (+0.20, 0.70, 1.0),
    "tabarbour":        (+0.05, 0.90, 0.9),
    "sweileh":          (+0.00, 1.00, 0.9),
    "khalda":           (-0.20, 1.30, 0.9),
}
BASE_INCOME = {"low": 0.33, "middle": 0.47, "high": 0.20}  # ASSUMPTION

# Mobility difficulty by age: (limited, wheelchair). ASSUMPTION unless anchored.
MOBILITY_BY_AGE = anchor("disability_by_age", None) or {
    "16-44": (0.025, 0.004), "45-64": (0.07, 0.01), "65-74": (0.18, 0.03), "75+": (0.32, 0.08)}

# Can drive themselves to the office (licence + access to a car). ASSUMPTION.
CAR_BY_INCOME = {"low": 0.30, "middle": 0.55, "high": 0.85}
CAR_FEMALE_MULT = 0.6
CAR_AGE_MULT = {"16-17": 0.0, "18-24": 0.6, "25-64": 1.0, "65-74": 0.6, "75+": 0.3}

# Smartphone ownership by age. ASSUMPTION unless anchored.
SMARTPHONE_BY_AGE = anchor("smartphone_by_age", None) or {
    "16-24": 0.97, "25-44": 0.95, "45-54": 0.88, "55-64": 0.75, "65-74": 0.50, "75+": 0.28}
# Digital literacy (low, medium, high) by age. ASSUMPTION.
LITERACY_BY_AGE = {
    "16-24": (0.05, 0.35, 0.60), "25-44": (0.08, 0.47, 0.45), "45-64": (0.25, 0.50, 0.25), "65+": (0.62, 0.32, 0.06)}

# Employment by sex and age. ASSUMPTION unless anchored.
WORKS = {
    "m": {"16-17": 0.05, "18-24": 0.40, "25-59": 0.78, "60-64": 0.40, "65+": 0.06},
    "f": {"16-17": 0.01, "18-24": 0.10, "25-59": 0.20, "60-64": 0.05, "65+": 0.01},
}
# Shift patterns (start, end, weight). ASSUMPTION. East areas get more early factory shifts.
SHIFTS = [("07:00", "16:00", 0.20), ("08:00", "15:00", 0.25), ("08:00", "16:00", 0.25),
          ("09:00", "17:00", 0.20), ("10:00", "18:00", 0.10)]

# Has a family member or neighbour who can drive them or help online. ASSUMPTION.
HELPER_BY_AGE = {"16-24": 0.70, "25-64": 0.55, "65+": 0.72}

NAMES_M = [("محمد", "Mohammad"), ("أحمد", "Ahmad"), ("عمر", "Omar"), ("خالد", "Khaled"), ("يوسف", "Yousef"),
           ("إبراهيم", "Ibrahim"), ("علي", "Ali"), ("حسن", "Hasan"), ("محمود", "Mahmoud"), ("عبدالله", "Abdullah"),
           ("سامي", "Sami"), ("فادي", "Fadi"), ("زيد", "Zaid"), ("ليث", "Laith"), ("طارق", "Tareq"),
           ("ماهر", "Maher"), ("نبيل", "Nabil"), ("رامي", "Rami"), ("هاني", "Hani"), ("بلال", "Bilal"),
           ("أنس", "Anas"), ("مصطفى", "Mustafa"), ("سليمان", "Suleiman"), ("عيسى", "Issa"), ("جمال", "Jamal")]
NAMES_F = [("فاطمة", "Fatima"), ("مريم", "Maryam"), ("سارة", "Sara"), ("نور", "Noor"), ("هدى", "Huda"),
           ("رنا", "Rana"), ("ليلى", "Layla"), ("سلمى", "Salma"), ("آمنة", "Amina"), ("خديجة", "Khadija"),
           ("رهف", "Rahaf"), ("دانا", "Dana"), ("لينا", "Lina"), ("سعاد", "Suad"), ("نادية", "Nadia"),
           ("أم محمد", "Um Mohammad"), ("وفاء", "Wafaa"), ("سميرة", "Samira"), ("رولا", "Rula"), ("عبير", "Abeer"),
           ("هالة", "Hala"), ("زينب", "Zainab"), ("جميلة", "Jamila"), ("تهاني", "Tahani"), ("ريم", "Reem")]


def weighted(rng: random.Random, items):
    total = sum(w for *_, w in items)
    r = rng.random() * total
    for item in items:
        r -= item[-1]
        if r <= 0:
            return item
    return items[-1]


def band(age: int, kind: str) -> str:
    if kind == "mobility":
        return "16-44" if age < 45 else "45-64" if age < 65 else "65-74" if age < 75 else "75+"
    if kind == "car":
        return "16-17" if age < 18 else "18-24" if age < 25 else "25-64" if age < 65 else "65-74" if age < 75 else "75+"
    if kind == "phone":
        for lo, hi, key in [(16, 24, "16-24"), (25, 44, "25-44"), (45, 54, "45-54"), (55, 64, "55-64"), (65, 74, "65-74")]:
            if lo <= age <= hi:
                return key
        return "75+"
    if kind == "literacy":
        return "16-24" if age < 25 else "25-44" if age < 45 else "45-64" if age < 65 else "65+"
    if kind == "work":
        return "16-17" if age < 18 else "18-24" if age < 25 else "25-59" if age < 60 else "60-64" if age < 65 else "65+"
    if kind == "helper":
        return "16-24" if age < 25 else "25-64" if age < 65 else "65+"
    raise ValueError(kind)


def age_bands_for(area_id: str):
    elderly_mult = AREA_PROFILE[area_id][2]
    bands = [(lo, hi, w * (elderly_mult if lo >= 65 else 1.0)) for lo, hi, w in AGE_BANDS]
    if SHARE_65_PLUS is not None:  # rescale 65+ bands to the anchored share, keeping area variation
        old = sum(w for lo, _, w in bands if lo >= 65)
        young = sum(w for lo, _, w in bands if lo < 65)
        target = SHARE_65_PLUS * elderly_mult
        bands = [(lo, hi, (w / old * target) if lo >= 65 else (w / young * (1 - target))) for lo, hi, w in bands]
    return bands


def helper_relation(rng: random.Random, age: int, gender: str):
    if age >= 60:
        options = [("ابني", "my son", 0.45), ("بنتي", "my daughter", 0.35), ("حفيدي", "my grandson", 0.12), ("جاري", "my neighbour", 0.08)]
    elif age >= 25:
        spouse = ("زوجي", "my husband", 0.35) if gender == "f" else ("زوجتي", "my wife", 0.25)
        options = [spouse, ("أخوي", "my brother", 0.30), ("أختي", "my sister", 0.15), ("جاري", "my neighbour", 0.10)]
    else:
        options = [("أبوي", "my father", 0.45), ("أخوي", "my brother", 0.30), ("أمي", "my mother", 0.25)]
    ar, en, _ = weighted(rng, options)
    return ar, en


def derive_tags(c: dict) -> list[str]:
    tags = []
    if c["age"] >= 65: tags.append("elderly")
    if c["mobility"] != "none": tags.append("disabled")
    if c["income_band"] == "low": tags.append("low_income")
    if not c["has_car"]: tags.append("no_car")
    if not c["has_smartphone"] or c["digital_literacy"] == "low": tags.append("offline")
    if c["works"]: tags.append("worker")
    if 18 <= c["age"] <= 24 and not c["works"]: tags.append("student")
    return tags


def make_citizen(rng: random.Random, i: int) -> dict:
    area = weighted(rng, [(a, a["weight"]) for a in AREAS])[0]
    aid = area["id"]
    low_shift, car_mult, _ = AREA_PROFILE[aid]

    lo, hi, _ = weighted(rng, age_bands_for(aid))
    age = rng.randint(lo, hi)
    gender = "f" if rng.random() < SHARE_FEMALE else "m"
    name_ar, name_en = rng.choice(NAMES_F if gender == "f" else NAMES_M)

    limited, wheel = MOBILITY_BY_AGE[band(age, "mobility")]
    r = rng.random()
    mobility = "wheelchair" if r < wheel else "limited" if r < wheel + limited else "none"

    low = min(0.8, max(0.05, BASE_INCOME["low"] + low_shift + (0.10 if age >= 65 else 0.0)))
    high = max(0.03, BASE_INCOME["high"] - low_shift * 0.6)
    income_band = weighted(rng, [("low", low), ("middle", max(0.05, 1 - low - high)), ("high", high)])[0]

    p_car = CAR_BY_INCOME[income_band] * car_mult * CAR_AGE_MULT[band(age, "car")]
    p_car *= CAR_FEMALE_MULT if gender == "f" else 1.0
    p_car *= {"none": 1.0, "limited": 0.6, "wheelchair": 0.1}[mobility]
    has_car = rng.random() < min(0.95, p_car)

    p_phone = SMARTPHONE_BY_AGE[band(age, "phone")] - (0.05 if income_band == "low" else 0.0)
    has_smartphone = rng.random() < p_phone
    lit = LITERACY_BY_AGE[band(age, "literacy")]
    digital_literacy = weighted(rng, [("low", lit[0]), ("medium", lit[1]), ("high", lit[2])])[0]
    if not has_smartphone and digital_literacy == "high":
        digital_literacy = "medium"

    p_work = WORKS[gender][band(age, "work")] * (0.4 if mobility == "wheelchair" else 1.0)
    works = rng.random() < p_work
    work_start = work_end = None
    if works:
        shifts = [(s, e, w * (1.8 if s == "07:00" and area["side"] == "east" else 1.0)) for s, e, w in SHIFTS]
        work_start, work_end, _ = weighted(rng, shifts)

    has_helper = rng.random() < HELPER_BY_AGE[band(age, "helper")]
    rel_ar = rel_en = None
    if has_helper:
        rel_ar, rel_en = helper_relation(rng, age, gender)

    # Jitter ~600 m around the area centroid (1° lat ≈ 111 km, 1° lng ≈ 94 km at Amman's latitude).
    lat = area["lat"] + rng.gauss(0, 0.0055)
    lng = area["lng"] + rng.gauss(0, 0.0065)

    c = {
        "id": f"c_{i:04d}", "name_ar": name_ar, "name_en": name_en, "age": age, "gender": gender,
        "area": aid, "lat": round(lat, 5), "lng": round(lng, 5), "mobility": mobility,
        "has_car": has_car, "has_smartphone": has_smartphone, "digital_literacy": digital_literacy,
        "works": works, "work_start": work_start, "work_end": work_end, "income_band": income_band,
        "has_helper": has_helper, "helper_relation_ar": rel_ar, "helper_relation_en": rel_en,
    }
    c["tags"] = derive_tags(c)
    return c


def generate(n: int = N_CITIZENS, seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    return [make_citizen(rng, i + 1) for i in range(n)]


def summary(pop: list[dict]) -> dict:
    n = len(pop)
    tags = {}
    for c in pop:
        for t in c["tags"]:
            tags[t] = tags.get(t, 0) + 1
    return {"n": n, **{t: f"{100 * v / n:.1f}%" for t, v in sorted(tags.items())}}


if __name__ == "__main__":
    pop = generate()
    (DATA / "population.json").write_text(json.dumps(pop, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary(pop), indent=1))
