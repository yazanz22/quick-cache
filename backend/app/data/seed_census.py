"""Census-anchored synthetic population for Nas, built from "Amman in a Box" (repo root).

    python -m app.data.seed_census                 # write app/data/census/* (does NOT touch population.json)
    python -m app.data.seed_census --n 1200        # any size, same proportions
    python -m app.data.seed_census --install       # also copy the Jordanian set into population.json
    # after --install, always:
    python -m app.data.fetch_map_data matrix  &&  python -m scripts.pick_heroes  &&  pytest -q

Two datasets come out of one generator (same seed, same rules):

  residents_all.csv / .json   Every resident aged 16+, to scale, INCLUDING the 36.2% non-Jordanians
                              (Syrian, Egyptian, Palestinian, Iraqi, Yemeni, other). Research-faithful.
  population_jordanian.json   Jordanian nationals aged 16+ only: the people who can actually renew a
                              Jordanian national ID at CSPD. This is the one the engine should run on.
                              Same schema as population.json: the engine's Citizen fields plus three optional
                              display fields (district, neighbourhood, neighbourhood_ar) that the engine ignores.

How "to scale" is enforced: headline marginals are hit EXACTLY with quota allocation (largest-remainder
counts, then weighted sampling without replacement to decide WHO gets the attribute). The weights carry the
realistic correlations (older -> fewer smartphones, poorer -> fewer cars, ...). Every number is tagged:
  ANCHORED       checked by the team against its source: only the MoDEE 2024 figures listed as ANCHORED in
                 data/anchors.json (95.6% internet use, 38.1% e-gov use; 99% smartphone households is context)
  CITED          quoted in the research doc with its source, NOT verified by the team (anchors.json: CITED_UNVERIFIED
                 or not listed). Never present a CITED figure as an official statistic.
  DERIVED        computed from cited/anchored values with one stated step
  ASSUMPTION     not in the research; a labelled modelling choice
(The JD 2 fee is TEAM_CONFIRMED in anchors.json; it lives in the scenarios, not here.)
Per-district variation (income, nationality mix) is always an ASSUMPTION.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter
from pathlib import Path

from . import seed  # names, helper relations, derive_tags: shared with the original seed

DATA = Path(__file__).resolve().parent
OUT = DATA / "census"
SEED = 42
N_DEFAULT = 1000

# ============================================================== TARGETS (all quoted in the research doc; see tags)
W = "https://en.wikipedia.org/wiki/Amman"
T = {
    "share_male": (0.53, "CITED", "DoS via Jordan Times (research §1)"),
    "disability_65plus": (0.493, "CITED", "UNFPA Jordan country profile 2024"),
    "disability_male": (0.117, "CITED", "Higher Council for Persons with Disabilities"),
    "disability_female": (0.108, "CITED", "Higher Council for Persons with Disabilities"),
    "difficulty_seeing": (0.09, "CITED", "2015 census via 2023 PFHS reporting"),
    "difficulty_walking": (0.07, "CITED", "2015 census via 2023 PFHS reporting"),
    "difficulty_cognition": (0.04, "CITED", "2015 census via 2023 PFHS reporting"),
    "disabled_employment_ratio": (16.1 / 36.6, "DERIVED", "16.1% employed (PwD) vs 36.6% (all), 2015 census"),
    "lfpr_male": (0.625, "CITED", "World Bank Gender Data Portal"),
    "lfpr_female": (0.16, "CITED", "World Bank Gender Data Portal"),
    "unemp_male": (0.19, "CITED", "ERF Forum 2025 (late-2024 DoS LFS)"),
    "unemp_female": (0.31, "CITED", "ERF Forum 2025 (late-2024 DoS LFS)"),
    "unemp_youth_male": (0.40, "CITED", "ERF Forum 2025, ages 15-24"),
    "unemp_youth_female": (0.66, "CITED", "ERF Forum 2025, ages 15-24"),
    "informal_25plus": (0.524, "CITED", "World Bank HCI 2022"),
    "informal_youth": (0.59, "CITED", "World Bank HCI 2022"),
    "poverty_rate_amman": (0.083, "CITED", "OCHA Jordan fact sheet"),
    "poverty_line_pc_month_jd": (100.0, "CITED", "DoS HEIS 2017/18 national line, JD 100 per person per month"),
    "drives_own_car": (0.50 * 0.932, "DERIVED", "~half of residents use own car (DoS) x 93.2% of car users hold a licence (MDPI 2023)"),
    "public_transport_share": (0.14, "CITED", "C40 BRT case study: PT mode share 14%"),
    "internet_user": (0.956, "ANCHORED", "MoDEE ICT household survey 2024 (proxy for personal smartphone)"),
    "skill_copy_paste": (0.796, "CITED", "MoDEE 2024"),
    "skill_presentation": (0.324, "CITED", "MoDEE 2024"),
    "egov_used": (0.381, "ANCHORED", "MoDEE 2024"),
    "household_size_mean": (4.8, "CITED", "DoS"),
}

# 22 GAM districts, 2015 census population (CITED: Wikipedia "Amman" table quoted in the research, not verified).
# Coordinates: centre of the populated part, ESTIMATED to ~1-2 km (no sourced coordinate was reachable).
# side: informal east/west split (ASSUMPTION). inc: household-income multiplier (ASSUMPTION).
# spread: jitter in degrees around the centre (ASSUMPTION, bigger for spread-out peri-urban districts).
#            id                name_en             name_ar                        pop2015  lat     lng     side   inc  spread
DISTRICTS = [
    ("al_madinah",      "Al-Madinah",       "المدينة",                       34988, 31.953, 35.933, "east", 0.80, 0.005),
    ("basman",          "Basman",           "بسمان",                        373981, 31.973, 35.945, "east", 0.85, 0.008),
    ("marka",           "Marka",            "ماركا",                        148100, 31.983, 35.995, "east", 0.80, 0.008),
    ("al_nasr",         "Al-Nasr",          "النصر",                        258829, 31.958, 35.967, "east", 0.70, 0.007),
    ("al_yarmouk",      "Al-Yarmouk",       "اليرموك",                      180773, 31.935, 35.946, "east", 0.75, 0.006),
    ("ras_al_ein",      "Ras Al-Ein",       "رأس العين",                    138024, 31.937, 35.923, "east", 0.80, 0.006),
    ("bader",           "Bader",            "بدر",                          229308, 31.937, 35.903, "east", 0.80, 0.007),
    ("zahran",          "Zahran",           "زهران",                        107529, 31.950, 35.885, "west", 1.90, 0.008),
    ("al_abdali",       "Al-Abdali",        "العبدلي",                      165333, 31.967, 35.905, "west", 1.30, 0.007),
    ("tariq",           "Tariq",            "طارق",                         175194, 32.000, 35.950, "east", 0.95, 0.009),
    ("qweismeh",        "Qweismeh",         "القويسمة",                     296763, 31.905, 35.950, "east", 0.75, 0.010),
    ("kherbet_al_souk", "Kherbet Al-Souk",  "خريبة السوق وجاوا واليادودة",  186158, 31.880, 35.918, "east", 0.75, 0.011),
    ("al_mgablein",     "Al-Mgablein",      "المقابلين",                     99738, 31.907, 35.900, "east", 0.80, 0.007),
    ("wadi_al_seer",    "Wadi Al-Seer",     "وادي السير",                   241830, 31.955, 35.835, "west", 1.50, 0.011),
    ("badr_al_jadeedah","Badr Al-Jadeedah", "بدر الجديدة",                   17891, 31.965, 35.770, "west", 0.85, 0.012),
    ("sweileh",         "Sweileh",          "صويلح",                        151016, 32.020, 35.840, "west", 1.05, 0.009),
    ("tla_al_ali",      "Tla' Al-Ali",      "تلاع العلي وأم السماق وخلدا",  251000, 31.990, 35.855, "west", 1.60, 0.009),
    ("jubeiha",         "Jubeiha",          "الجبيهة",                      197160, 32.020, 35.875, "west", 1.30, 0.009),
    ("shafa_badran",    "Shafa Badran",     "شفا بدران",                     72315, 32.045, 35.910, "west", 1.10, 0.010),
    ("abu_nseir",       "Abu Nseir",        "أبو نصير",                      72489, 32.050, 35.880, "west", 1.10, 0.007),
    ("uhod",            "Uhod",             "أحد",                           40000, 31.900, 36.030, "east", 0.70, 0.014),
    ("marj_al_hamam",   "Marj Al-Hamam",    "مرج الحمام",                    82788, 31.895, 35.835, "west", 1.25, 0.011),
]
# NOTE: the 22 district rows sum to 3,521,207, not the 4,007,526 total printed under the table (a 486,319 gap,
# probably areas not listed). Only the RELATIVE district shares are used, so the gap doesn't bias the sample.
DISTRICT_SUM = sum(d[3] for d in DISTRICTS)
assert DISTRICT_SUM == 3_521_207

# Non-Jordanian residents, 2015 census (CITED). The named groups sum to 1,431,044 while the stated total is
# 1,452,693; the 21,649 gap is added to "other" (DERIVED).
TOTAL_2015, NON_JO_2015 = 4_007_526, 1_452_693
NATIONALITY = {"jordanian": TOTAL_2015 - NON_JO_2015, "syrian": 435_578, "egyptian": 390_631,
               "palestinian": 308_091, "iraqi": 121_893, "yemeni": 27_109}
NATIONALITY["other"] = NON_JO_2015 - sum(v for k, v in NATIONALITY.items() if k != "jordanian")

# ---------------------------------------------------------------- ASSUMPTIONS (not in the research doc)
# Age of residents 16+. The research says the census has single-year ages but quotes no bands; these shares
# approximate Jordan's 2015 pyramid (65+ ~6.5% of adults). ASSUMPTION.
AGE_BANDS = [(16, 17, 0.055), (18, 24, 0.205), (25, 34, 0.250), (35, 44, 0.190),
             (45, 54, 0.140), (55, 64, 0.095), (65, 74, 0.045), (75, 90, 0.020)]
# WG disability ("a lot of difficulty") under 65, by age. Chosen so the 5-64 rate stays near the 11.2% national
# figure once the cited 49.3% for 65+ is added. ASSUMPTION (shape).
DISABILITY_UNDER_65 = {(16, 24): 0.05, (25, 44): 0.07, (45, 54): 0.13, (55, 64): 0.22}
# Domains not quoted in the research (WG short set has six). ASSUMPTION.
DIFFICULTY_OTHER = {"hearing": 0.25, "self_care": 0.15, "communication": 0.10}  # P(domain | disabled)
# Share of people with walking difficulty who use a wheelchair. Research: NOT FOUND. ASSUMPTION.
WHEELCHAIR_GIVEN_WALKING = {(16, 64): 0.10, (65, 74): 0.20, (75, 120): 0.30}
# Household-level size distribution, mean ~4.8 (cited mean, ASSUMED shape). Persons are drawn size-biased.
HH_SIZE = {1: .04, 2: .10, 3: .12, 4: .16, 5: .19, 6: .16, 7: .11, 8: .06, 9: .04, 10: .02}
# Labour-force propensity by age (ASSUMPTION shape; totals are rescaled to the cited LFPR by sex).
LF_AGE = [(16, 17, 0.10), (18, 24, 0.60), (25, 54, 1.00), (55, 64, 0.55), (65, 120, 0.08)]
# Nationality effects. ASSUMPTION (direction from the literature on migrant work / refugee livelihoods).
NAT = {  # (lf_weight, income_mult, car_weight, egov_weight, informal_weight, east_bias)
    "jordanian":   (1.0, 1.00, 1.00, 1.0, 1.0, 1.0),
    "syrian":      (0.8, 0.55, 0.30, 0.3, 2.0, 1.6),
    "egyptian":    (3.0, 0.60, 0.20, 0.2, 2.5, 1.6),
    "palestinian": (1.0, 0.60, 0.40, 0.3, 2.0, 1.6),
    "iraqi":       (0.6, 0.95, 0.80, 0.4, 1.5, 0.7),
    "yemeni":      (0.8, 0.55, 0.30, 0.3, 2.0, 1.4),
    "other":       (1.5, 0.80, 0.50, 0.4, 1.5, 1.0),
}
EGYPTIAN_MALE_WEIGHT = 4.0  # Egyptian residents are mostly male labour migrants; overall still exactly 53% male.
INCOME_SIGMA = 0.65          # log-normal spread of household income. ASSUMPTION.
INCOME_BAND_CUTS = (0.30, 0.80)  # engine income_band: bottom 30% per-capita = low, top 20% = high. ASSUMPTION.
NON_DRIVER_MODES = {"car_passenger": 0.60, "taxi": 0.20, "walk": 0.20}  # outside the 14% PT share. ASSUMPTION.
PT_SPLIT = {"bus_brt": 0.55, "service_taxi": 0.45}  # ASSUMPTION.
SHIFTS = seed.SHIFTS


# ============================================================================ helpers
def quotas(weights: dict, n: int) -> dict:
    """Largest-remainder rounding: integer counts that sum to n and match the shares."""
    tot = sum(weights.values())
    raw = {k: n * w / tot for k, w in weights.items()}
    out = {k: int(math.floor(v)) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[: n - sum(out.values())]:
        out[k] += 1
    return out


def pick(rng: random.Random, people: list, k: int, weight) -> list:
    """Weighted sampling WITHOUT replacement (Efraimidis-Spirakis): exactly k people, likelier if heavier."""
    k = max(0, min(k, len(people)))
    keyed = []
    for p in people:
        w = weight(p)
        keyed.append((rng.random() ** (1.0 / w) if w > 0 else -1.0, p["_i"], p))
    keyed.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [p for _, _, p in keyed[:k]]


def in_band(age: int, bands) -> object:
    for key in bands:
        lo, hi = key[0], key[1]
        if lo <= age <= hi:
            return key
    raise ValueError(age)


def haversine_km(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def engine_area(d) -> str:
    """Map a GAM district to the nearest of the engine's 8 areas on the same side of the city."""
    _, _, _, _, lat, lng, side, *_ = d
    same = [a for a in seed.AREAS if a["side"] == side] or seed.AREAS
    return min(same, key=lambda a: haversine_km(lat, lng, a["lat"], a["lng"]))["id"]


# ============================================================================ generator
def generate(n: int = N_DEFAULT, scope: str = "jordanian", seed_: int = SEED) -> list[dict]:
    rng = random.Random(f"{seed_}:{scope}:{n}")
    P = [{"_i": i} for i in range(n)]

    # 1. District: exact census quotas.
    dq = quotas({d[0]: d[3] for d in DISTRICTS}, n)
    dist = {d[0]: d for d in DISTRICTS}
    slots = [k for k, c in dq.items() for _ in range(c)]
    rng.shuffle(slots)
    for p, k in zip(P, slots):
        d = dist[k]
        p.update(district=k, district_en=d[1], district_ar=d[2], side=d[6], area=engine_area(d))

    # 2. Nationality: exact quotas (or everyone Jordanian). Non-Jordanians lean east (ASSUMPTION).
    for p in P:
        p["nationality"] = "jordanian"
    if scope == "all":
        nq = quotas(NATIONALITY, n)
        free = list(P)
        for nat in ["egyptian", "syrian", "palestinian", "iraqi", "yemeni", "other"]:
            bias = NAT[nat][5]
            for p in pick(rng, free, nq[nat], lambda p: bias if p["side"] == "east" else 1.0):
                p["nationality"] = nat
            free = [p for p in free if p["nationality"] == "jordanian"]

    # 3. Sex: exactly 53% male.
    males = pick(rng, P, round(T["share_male"][0] * n),
                 lambda p: EGYPTIAN_MALE_WEIGHT if p["nationality"] == "egyptian" else 1.0)
    mset = {p["_i"] for p in males}
    for p in P:
        p["gender"] = "m" if p["_i"] in mset else "f"

    # 4. Age: exact band quotas; Egyptian labour migrants only fill working-age bands (ASSUMPTION).
    aq = quotas({(lo, hi): w for lo, hi, w in AGE_BANDS}, n)
    free = list(P)
    for (lo, hi) in sorted(aq, key=lambda b: -b[0]):  # oldest first, so the constraint can always be met
        ok = lambda p, lo=lo, hi=hi: (0.0 if p["nationality"] == "egyptian" and (lo >= 55 or hi < 18) else 1.0)
        chosen = pick(rng, free, aq[(lo, hi)], lambda p: ok(p) or 1e-9)
        for p in chosen:
            p["age"] = rng.randint(lo, hi)
        ids = {p["_i"] for p in chosen}
        free = [p for p in free if p["_i"] not in ids]

    # 5. Disability (Washington Group). 65+: exactly 49.3%. Under 65: age gradient x sex ratio.
    sex_mult = {"m": T["disability_male"][0] / 0.112, "f": T["disability_female"][0] / 0.112}
    old = [p for p in P if p["age"] >= 65]
    dis_old = {p["_i"] for p in pick(rng, old, round(T["disability_65plus"][0] * len(old)), lambda p: 1 + (p["age"] >= 75))}
    for p in P:
        if p["age"] >= 65:
            p["disabled"] = p["_i"] in dis_old
        else:
            p["disabled"] = rng.random() < DISABILITY_UNDER_65[in_band(p["age"], DISABILITY_UNDER_65)] * sex_mult[p["gender"]]
    dom_p = {"seeing": T["difficulty_seeing"][0] / 0.112, "walking": T["difficulty_walking"][0] / 0.112,
             "cognition": T["difficulty_cognition"][0] / 0.112, **DIFFICULTY_OTHER}
    for p in P:
        doms = []
        if p["disabled"]:
            for dname, pr in dom_p.items():
                if dname == "walking" and p["age"] >= 65:
                    pr = min(0.95, pr * 1.2)
                if rng.random() < pr:
                    doms.append(dname)
            if not doms:
                doms.append(seed.weighted(rng, [(k, v) for k, v in dom_p.items()])[0])
        p["difficulties"] = doms
        mob = "none"
        if "walking" in doms:
            mob = "wheelchair" if rng.random() < WHEELCHAIR_GIVEN_WALKING[in_band(p["age"], WHEELCHAIR_GIVEN_WALKING)] else "limited"
        p["mobility"] = mob

    # 6. Household size (size-biased person draw from a household distribution with mean ~4.8).
    for p in P:
        dist_ = dict(HH_SIZE)
        if p["age"] >= 65:  # older people more often live alone or as a couple (ASSUMPTION; research: NOT FOUND)
            dist_[1] *= 2.5; dist_[2] *= 2.0
        if p["nationality"] == "egyptian":
            dist_[1] *= 3.0; dist_[2] *= 2.0
        p["household_size"] = seed.weighted(rng, [(s, s * w) for s, w in dist_.items()])[0]

    # 7. Labour force: exact LFPR by sex; unemployment exact by sex x youth; informality exact by age.
    def lf_w(p):
        w = in_band(p["age"], LF_AGE)[2] * NAT[p["nationality"]][0]
        return w * (T["disabled_employment_ratio"][0] if p["disabled"] else 1.0) * (0.3 if p["mobility"] == "wheelchair" else 1.0)
    for sex, key in (("m", "lfpr_male"), ("f", "lfpr_female")):
        grp = [p for p in P if p["gender"] == sex]
        lf = {p["_i"] for p in pick(rng, grp, round(T[key][0] * len(grp)), lf_w)}
        for p in grp:
            p["in_labour_force"] = p["_i"] in lf
    for sex, tot_key, y_key in (("m", "unemp_male", "unemp_youth_male"), ("f", "unemp_female", "unemp_youth_female")):
        lf = [p for p in P if p["gender"] == sex and p["in_labour_force"]]
        youth = [p for p in lf if p["age"] <= 24]
        adult = [p for p in lf if p["age"] > 24]
        u_total = round(T[tot_key][0] * len(lf))
        u_youth = min(len(youth), round(T[y_key][0] * len(youth)))
        u_adult = max(0, min(len(adult), u_total - u_youth))  # DERIVED: adult rate solved so the total matches
        un = {p["_i"] for p in pick(rng, youth, u_youth, lambda p: 1.0)} | \
             {p["_i"] for p in pick(rng, adult, u_adult, lambda p: 1.0 + p["disabled"])}
        for p in lf:
            p["unemployed"] = p["_i"] in un
    for p in P:
        p["works"] = p.get("in_labour_force", False) and not p.get("unemployed", False)
        if p["works"]:
            p["employment_status"] = "employed"
        elif p.get("in_labour_force"):
            p["employment_status"] = "unemployed"
        elif p["age"] <= 24:
            p["employment_status"] = "student"
        elif p["age"] >= 60:
            p["employment_status"] = "retired"
        elif p["gender"] == "f":
            p["employment_status"] = "homemaker"
        else:
            p["employment_status"] = "out_of_labour_force"
    workers = [p for p in P if p["works"]]
    young_w, adult_w = [p for p in workers if p["age"] <= 24], [p for p in workers if p["age"] > 24]
    inf = {p["_i"] for p in pick(rng, young_w, round(T["informal_youth"][0] * len(young_w)), lambda p: NAT[p["nationality"]][4])} | \
          {p["_i"] for p in pick(rng, adult_w, round(T["informal_25plus"][0] * len(adult_w)), lambda p: NAT[p["nationality"]][4])}
    for p in P:
        p["informal_job"] = p["_i"] in inf if p["works"] else None
        p["work_start"] = p["work_end"] = None
        if p["works"]:
            early = 1.8 if (p["side"] == "east" or p["informal_job"]) else 1.0
            p["work_start"], p["work_end"], _ = seed.weighted(
                rng, [(s, e, w * (early if s == "07:00" else 1.0)) for s, e, w in SHIFTS])

    # 8. Income: log-normal household income, then ONE scale factor so exactly 8.3% fall under the
    #    JD 100 per person per month line (DERIVED calibration to the cited Amman poverty rate).
    for p in P:
        mult = dist[p["district"]][7] * NAT[p["nationality"]][1]
        mult *= 0.85 if p["disabled"] else 1.0
        mult *= 0.85 if p["age"] >= 65 else 1.0
        mult *= 1.15 if p["works"] else (0.8 if p["employment_status"] == "unemployed" else 1.0)
        mult *= 1 + 0.06 * (p["household_size"] - 1)  # bigger households pool more earners (ASSUMPTION)
        p["_raw"] = mult * math.exp(rng.gauss(0, INCOME_SIGMA))
    pc = sorted(p["_raw"] / p["household_size"] for p in P)
    k_poor = round(T["poverty_rate_amman"][0] * n)
    q = (pc[k_poor - 1] + pc[k_poor]) / 2  # the line sits between the k-th and (k+1)-th poorest
    scale = T["poverty_line_pc_month_jd"][0] / q
    for p in P:
        p["household_income_jd"] = round(p["_raw"] * scale)
        p["per_capita_income_jd"] = round(p["_raw"] * scale / p["household_size"], 1)
        p["below_poverty_line"] = p["_raw"] / p["household_size"] < q
    ranked = sorted(P, key=lambda p: (p["_raw"] / p["household_size"], p["_i"]))
    lo_cut, hi_cut = round(INCOME_BAND_CUTS[0] * n), round(INCOME_BAND_CUTS[1] * n)
    for r, p in enumerate(ranked):
        p["income_band"] = "low" if r < lo_cut else "high" if r >= hi_cut else "middle"
        p["_pct"] = r / max(1, n - 1)

    # 9. Drives own car: exactly 46.6% (DERIVED). Correlations via weights (ASSUMPTION).
    def car_w(p):
        a = p["age"]
        w = 0.0 if a < 18 else 0.6 if a < 25 else 1.0 if a < 65 else 0.6 if a < 75 else 0.25
        w *= 1.0 if p["gender"] == "m" else 0.45
        w *= 0.3 + 1.4 * p["_pct"]
        w *= {"none": 1.0, "limited": 0.6, "wheelchair": 0.1}[p["mobility"]]
        w *= 0.3 if "seeing" in p["difficulties"] else 1.0
        return w * NAT[p["nationality"]][2]
    cars = {p["_i"] for p in pick(rng, P, round(T["drives_own_car"][0] * n), car_w)}
    for p in P:
        p["has_car"] = p["_i"] in cars

    # 10. Main way of getting around: 14% public transport (CITED), rest split by ASSUMPTION.
    non_drivers = [p for p in P if not p["has_car"]]
    pt = {p["_i"] for p in pick(rng, non_drivers, round(T["public_transport_share"][0] * n),
                                lambda p: (2.0 if p["employment_status"] in ("student", "employed") else 1.0)
                                * (1.5 if p["income_band"] == "low" else 1.0) * (0.2 if p["mobility"] == "wheelchair" else 1.0))}
    for p in P:
        if p["has_car"]:
            p["main_mode"] = "car_driver"
        elif p["_i"] in pt:
            p["main_mode"] = seed.weighted(rng, list(PT_SPLIT.items()))[0]
        else:
            m = dict(NON_DRIVER_MODES)
            if p["mobility"] != "none":
                m["walk"] *= 0.2
            p["main_mode"] = seed.weighted(rng, list(m.items()))[0]

    # 11. Smartphone: exactly 95.6% (individual internet use as proxy). Who goes without: weighted (ASSUMPTION).
    def no_phone_w(p):
        a = p["age"]
        w = 12 if a >= 75 else 6 if a >= 65 else 2 if a >= 55 else 1
        w *= 2 if "cognition" in p["difficulties"] else 1
        w *= 2 if "seeing" in p["difficulties"] else 1
        return w * (1.5 if p["income_band"] == "low" else 1.0)
    no_phone = {p["_i"] for p in pick(rng, P, n - round(T["internet_user"][0] * n), no_phone_w)}
    for p in P:
        p["has_smartphone"] = p["_i"] not in no_phone

    # 12. Digital literacy: exactly 32.4% high (can make a presentation), 79.6% at least medium (copy/paste).
    def young_w(p):
        a = p["age"]
        return (3 if a < 35 else 2 if a < 50 else 1 if a < 65 else 0.25) * (0.5 + p["_pct"]) * (0.5 if "cognition" in p["difficulties"] else 1)
    phones = [p for p in P if p["has_smartphone"]]
    high = {p["_i"] for p in pick(rng, phones, round(T["skill_presentation"][0] * n), young_w)}
    rest = [p for p in phones if p["_i"] not in high]
    med = {p["_i"] for p in pick(rng, rest, round(T["skill_copy_paste"][0] * n) - len(high), young_w)}
    for p in P:
        p["digital_literacy"] = "high" if p["_i"] in high else "medium" if p["_i"] in med else "low"

    # 13. Has used an e-government service: exactly 38.1%.
    def egov_w(p):
        w = {"high": 3.0, "medium": 1.5, "low": 0.15}[p["digital_literacy"]]
        return w * (1.3 if 25 <= p["age"] <= 54 else 1.0) * NAT[p["nationality"]][3]
    eg = {p["_i"] for p in pick(rng, phones, round(T["egov_used"][0] * n), egov_w)}
    for p in P:
        p["used_egov"] = p["_i"] in eg

    # 14. Helper (family member/neighbour who can drive them or help online). ASSUMPTION, as in seed.py,
    #     but nobody in a one-person household has an in-home helper.
    for p in P:
        base = seed.HELPER_BY_AGE[seed.band(p["age"], "helper")]
        if p["household_size"] == 1:
            base = 0.25
        p["has_helper"] = rng.random() < base
        p["helper_relation_ar"] = p["helper_relation_en"] = None
        if p["has_helper"]:
            if p["household_size"] == 1:
                p["helper_relation_ar"], p["helper_relation_en"] = rng.choice(
                    [("جاري", "my neighbour"), ("ابني", "my son"), ("بنتي", "my daughter"), ("صاحبي", "my friend")])
            else:
                p["helper_relation_ar"], p["helper_relation_en"] = seed.helper_relation(rng, p["age"], p["gender"])

    # 15. Names, home location, tags.
    #     Home = a neighbourhood of the person's district (equal odds, ASSUMPTION: no neighbourhood populations
    #     in the research), then a spot near it. If home_points.json (OSM residential streets) exists, the spot
    #     is a real street point near the neighbourhood, so homes follow the built-up city; otherwise a ~550 m
    #     scatter around the neighbourhood point.
    streets = HomePoints.load()
    for i, p in enumerate(sorted(P, key=lambda p: p["_i"]), 1):
        p["id"] = f"c_{i:04d}" if scope == "jordanian" else f"r_{i:04d}"
        p["name_ar"], p["name_en"] = rng.choice(seed.NAMES_F if p["gender"] == "f" else seed.NAMES_M)
        hood = rng.choice(NEIGHBOURHOODS[p["district"]])
        p["neighbourhood"], p["neighbourhood_ar"] = hood[0], hood[1]
        spot = streets.near(rng, hood[2], hood[3]) if streets else None
        p["home_source"] = "osm_street" if spot is not None else "scatter"
        if spot is None:
            spot = (hood[2] + rng.gauss(0, HOOD_SCATTER_DEG), hood[3] + rng.gauss(0, HOOD_SCATTER_DEG * 1.18))
        p["lat"], p["lng"] = round(spot[0], 5), round(spot[1], 5)
        p["tags"] = seed.derive_tags(p)
    return sorted(P, key=lambda p: p["_i"])


# ============================================================================ where people live
HOOD_SCATTER_DEG = 0.0050   # ~550 m scatter around a neighbourhood point when no street data. ASSUMPTION.
STREET_RADIUS_KM = 0.9      # pick a residential street point within this distance of the neighbourhood. ASSUMPTION.

# Neighbourhoods per GAM district: (name_en, name_ar, lat, lng). Points marked W are Who's On First gazetteer
# coordinates (whosonfirst.org, CC-BY); the rest are estimates (±1 km). District membership follows GAM's
# district names and the neighbourhoods each one is known for; borderline ones are a best guess.
NEIGHBOURHOODS = {
    "al_madinah": [("Al-Balad (Downtown)", "البلد", 31.9516, 35.9346), ("Jabal Al-Qal'a", "جبل القلعة", 31.9513, 35.9364),   # W
                   ("Jabal Al-Jofeh", "جبل الجوفة", 31.9484, 35.9443)],                                                          # W
    "basman": [("Al-Hashmi Al-Shamali", "الهاشمي الشمالي", 31.9705, 35.9505), ("Al-Hashmi Al-Janoubi", "الهاشمي الجنوبي", 31.9595, 35.9516),  # W
               ("Jabal Al-Nuzha", "جبل النزهة", 31.9755, 35.9335), ("Raghadan", "رغدان", 31.9620, 35.9420),
               ("Al-Mahatta", "المحطة", 31.9672, 35.9712), ("Al-Qusour", "القصور", 31.9805, 35.9545)],                          # W
    "marka": [("Marka Al-Janoubiya", "ماركا الجنوبية", 31.9693, 35.9792), ("Marka Al-Shamaliya", "ماركا الشمالية", 31.9970, 36.0022),  # W W
              ("Al-Rasha", "الرشا", 31.9732, 35.9821), ("Marka (airport side)", "ماركا - المطار", 31.9810, 35.9890)],          # W
    "al_nasr": [("Jabal Al-Nasr", "جبل النصر", 31.9610, 35.9625), ("Jabal Al-Taj", "جبل التاج", 31.9541, 35.9561),           # W
                ("Prince Hassan Camp", "مخيم الأمير حسن", 31.9665, 35.9600), ("Al-Manara", "المنارة", 31.9465, 35.9600),
                ("Al-Hussein Al-Sharqi", "الحسين الشرقي", 31.9555, 35.9487)],                                                 # W
    "al_yarmouk": [("Al-Wehdat", "الوحدات", 31.9330, 35.9440), ("Hay Al-Awda", "حي العودة", 31.9280, 35.9500),
                   ("Jabal Al-Ashrafiyeh", "جبل الأشرفية", 31.9469, 35.9287), ("Al-Hilal (Al-Yarmouk)", "الهلال (اليرموك)", 31.9380, 35.9370)],  # W
    "ras_al_ein": [("Ras Al-Ein", "رأس العين", 31.9436, 35.9188), ("Al-Muhajireen", "المهاجرين", 31.9494, 35.9316),        # W
                   ("Jabal Al-Rawda", "جبل الروضة", 31.9172, 35.9280), ("Jabal Al-Nadhif", "جبل النظيف", 31.9412, 35.9297),  # W W
                   ("Al-Zuhour", "الزهور", 31.9250, 35.9150)],
    "bader": [("Jabal Nazzal", "جبل النزال", 31.9390, 35.9050), ("Al-Hilal (Bader)", "الهلال (بدر)", 31.9312, 35.9033),                       # W
              ("Al-Dustour", "الدستور", 31.9350, 35.8960), ("Airport Road (Bader)", "طريق المطار - بدر", 31.9270, 35.9100)],
    "zahran": [("Abdoun", "عبدون", 31.9440, 35.8830), ("Hay Zahran", "حي زهران", 31.9471, 35.8860),                            # W
               ("Jabal Amman", "جبل عمان", 31.9520, 35.9080), ("Umm Uthaina", "أم أذينة", 31.9663, 35.8693),                   # W
               ("Deir Ghbar", "دير غبار", 31.9440, 35.8650), ("Wadi Abdoun", "وادي عبدون", 31.9452, 35.9006),                  # W
               ("Al-Rabieh", "الرابية", 31.9800, 35.8830)],
    "al_abdali": [("Al-Abdali", "العبدلي", 31.9613, 35.9129), ("Al-Shmeisani", "الشميساني", 31.9706, 35.8972),               # W W
                  ("Jabal Al-Weibdeh", "جبل اللويبدة", 31.9568, 35.9185), ("Jabal Al-Hussein", "جبل الحسين", 31.9686, 35.9143),  # W W
                  ("Sport City", "المدينة الرياضية", 31.9877, 35.8952), ("Al-Abdaliyeh", "العبدلية", 31.9790, 35.8937)],   # W W
    "tariq": [("Tabarbour", "طبربور", 32.0000, 35.9400), ("Tareq", "طارق", 31.9900, 35.9438),                                 # W
              ("Ain Ghazal", "عين غزال", 31.9860, 35.9600), ("Abu Ulya", "أبو عليا", 32.0060, 35.9620),
              ("Qatna", "قطنة", 31.9998, 35.9215), ("Dahiyat Al-Amir Hamzeh", "ضاحية الأمير حمزة", 32.0225, 35.9240)],      # W W
    "qweismeh": [("Al-Qweismeh", "القويسمة", 31.9219, 35.9555), ("Abu Alanda", "أبو علندا", 31.9026, 35.9624),              # W W
                 ("Al-Jweideh", "الجويدة", 31.8871, 35.9314), ("Jabal Al-Hadid", "جبل الحديد", 31.9079, 35.9637),           # W W
                 ("Al-Raqim", "الرقيم", 31.8960, 35.9420)],
    "kherbet_al_souk": [("Khraibet Al-Souk", "خريبة السوق", 31.8705, 35.9244), ("Jawa", "جاوا", 31.8525, 35.9393),          # W W
                        ("Al-Yadudeh", "اليادودة", 31.8656, 35.9129)],                                                       # W
    "al_mgablein": [("Al-Muqabalain", "المقابلين", 31.8959, 35.8850), ("Umm Quseir", "أم قصير", 31.8900, 35.9050),            # W
                    ("Al-Bunayyat Al-Shamaliya", "البنيات الشمالية", 31.8930, 35.8931),                                       # W
                    ("Al-Bunayyat Al-Janoubiya", "البنيات الجنوبية", 31.8790, 35.8882)],                                      # W
    "wadi_al_seer": [("Wadi Al-Seer", "وادي السير", 31.9513, 35.8198), ("Al-Sweifieh", "الصويفية", 31.9553, 35.8662),         # W W
                     ("Al-Bayader", "البيادر", 31.9597, 35.8427), ("Al-Rawabi", "الروابي", 31.9620, 35.8540),               # W
                     ("Al-Kursi", "الكرسي", 31.9700, 35.8360)],
    "badr_al_jadeedah": [("Al-Suwaysa", "السويسة", 31.9488, 35.7644), ("Zubda", "زبدة", 31.9459, 35.7560),                   # W W
                         ("Umm Al-Aswad", "أم الأسود", 31.9716, 35.7824), ("Al-Ghurus", "الغروس", 31.9629, 35.7786)],        # W W
    "sweileh": [("Sweileh", "صويلح", 32.0239, 35.8403), ("Sweileh West", "صويلح الغربي", 32.0300, 35.8300),                   # W
                ("Al-Kamaliyeh", "الكمالية", 32.0080, 35.8220)],
    "tla_al_ali": [("Tla' Al-Ali", "تلاع العلي", 31.9950, 35.8650), ("Khalda", "خلدا", 31.9950, 35.8400),
                   ("Umm Al-Summaq", "أم السماق", 31.9786, 35.8469), ("Dabouq", "دابوق", 31.9847, 35.8288),                 # W W
                   ("Al-Gardens", "الجاردنز", 31.9880, 35.8790), ("Hay Al-Salam", "حي السلام", 31.9843, 35.8762)],          # W
    "jubeiha": [("Al-Jubeiha", "الجبيهة", 32.0258, 35.8646), ("Jubeiha East", "الجبيهة الشرقية", 32.0230, 35.8769),          # W W
                ("University of Jordan area", "منطقة الجامعة الأردنية", 32.0150, 35.8720)],
    "shafa_badran": [("Shafa Badran", "شفا بدران", 32.0450, 35.9100), ("Applied Science University area", "منطقة جامعة العلوم التطبيقية", 32.0298, 35.9085),  # W
                     ("Shafa Badran North", "شفا بدران الشمالية", 32.0560, 35.9050)],
    "abu_nseir": [("Abu Nseir Housing", "إسكان أبو نصير", 32.0459, 35.8926), ("Abu Nseir West", "أبو نصير الغربي", 32.0520, 35.8820)],  # W
    "uhod": [("Al-Mushayrifah", "المشيرفة", 31.8940, 36.0115), ("Al-Kashafiya", "الكشافية", 31.9050, 36.0200),               # W
             ("Al-Manakher", "المناخر", 31.8933, 36.0774)],                                                                   # W
    "marj_al_hamam": [("Marj Al-Hamam", "مرج الحمام", 31.8950, 35.8350), ("Iskan Alia", "إسكان عالية", 31.8870, 35.8450),
                      ("Circassian Quarter", "الحي الشركسي", 31.9000, 35.8300)],
}
assert set(NEIGHBOURHOODS) == {d[0] for d in DISTRICTS}


class HomePoints:
    """Residential street points from OpenStreetMap (data/home_points.json, made by
    `python -m app.data.fetch_map_data homes`). Optional: without it, homes scatter around neighbourhood points."""
    CELL = 0.01  # ~1 km grid for neighbour lookups

    def __init__(self, pts):
        self.grid = {}
        for lat, lng in pts:
            self.grid.setdefault((int(lat / self.CELL), int(lng / self.CELL)), []).append((lat, lng))

    @classmethod
    def load(cls):
        f = DATA / "home_points.json"
        if not f.exists():
            return None
        return cls(json.loads(f.read_text(encoding="utf-8"))["points"])

    def near(self, rng, lat, lng):
        ci, cj = int(lat / self.CELL), int(lng / self.CELL)
        cand = [q for di in (-1, 0, 1) for dj in (-1, 0, 1) for q in self.grid.get((ci + di, cj + dj), [])
                if haversine_km(lat, lng, q[0], q[1]) <= STREET_RADIUS_KM]
        if not cand:
            return None
        q = rng.choice(sorted(cand))
        return q[0] + rng.gauss(0, 0.00015), q[1] + rng.gauss(0, 0.00015)  # ~15 m off the street centreline


# ============================================================================ output
SCHEMA = ["id", "name_ar", "name_en", "age", "gender", "area", "lat", "lng", "mobility", "has_car", "has_smartphone",
          "digital_literacy", "works", "work_start", "work_end", "income_band", "has_helper",
          "helper_relation_ar", "helper_relation_en", "tags"]
EXTRA = ["district", "district_en", "district_ar", "neighbourhood", "neighbourhood_ar", "home_source", "side", "nationality", "household_size", "disabled", "difficulties",
         "employment_status", "informal_job", "household_income_jd", "per_capita_income_jd", "below_poverty_line",
         "main_mode", "used_egov"]


def engine_rows(pop):
    return [{**{k: p[k] for k in SCHEMA}, "district": p["district"], "neighbourhood": p["neighbourhood"],
             "neighbourhood_ar": p["neighbourhood_ar"]} for p in pop]


def full_rows(pop):
    return [{k: p[k] for k in SCHEMA[:-1] + EXTRA + ["tags"]} for p in pop]


def write_csv(path: Path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("|".join(v) if isinstance(v, list) else "" if v is None else v) for k, v in r.items()})


def report(pop, title) -> str:
    n = len(pop)
    sh = lambda f, sub=None: (lambda s: (sum(1 for p in s if f(p)), len(s)))(sub if sub is not None else pop)
    pct = lambda a_b: f"{100 * a_b[0] / a_b[1]:.1f}% ({a_b[0]}/{a_b[1]})" if a_b[1] else "n/a"
    males = [p for p in pop if p["gender"] == "m"]; females = [p for p in pop if p["gender"] == "f"]
    old = [p for p in pop if p["age"] >= 65]
    lf_m = [p for p in males if p["in_labour_force"]]; lf_f = [p for p in females if p["in_labour_force"]]
    yl_m = [p for p in lf_m if p["age"] <= 24]; yl_f = [p for p in lf_f if p["age"] <= 24]
    wk = [p for p in pop if p["works"]]
    rows = [
        ("Male", "53%", pct(sh(lambda p: p["gender"] == "m")), "CITED"),
        ("Aged 65+ (of 16+)", "~6.5%", pct(sh(lambda p: p["age"] >= 65)), "ASSUMPTION"),
        ("Disability (WG), 65+", "49.3%", pct(sh(lambda p: p["disabled"], old)), "CITED"),
        ("Disability (WG), all 16+", "≥11.2% (11.2% is for 5+)", pct(sh(lambda p: p["disabled"])), "check"),
        ("Difficulty seeing", "9% (see note)", pct(sh(lambda p: "seeing" in p["difficulties"])), "CITED*"),
        ("Difficulty walking", "7% (see note)", pct(sh(lambda p: "walking" in p["difficulties"])), "CITED*"),
        ("Difficulty remembering", "4% (see note)", pct(sh(lambda p: "cognition" in p["difficulties"])), "CITED*"),
        ("Wheelchair users", "NOT FOUND", pct(sh(lambda p: p["mobility"] == "wheelchair")), "ASSUMPTION"),
        ("Labour-force participation, men", "62.5%", pct(sh(lambda p: p["in_labour_force"], males)), "CITED"),
        ("Labour-force participation, women", "16%", pct(sh(lambda p: p["in_labour_force"], females)), "CITED"),
        ("Unemployment, men", "19%", pct(sh(lambda p: p["unemployed"], lf_m)), "CITED"),
        ("Unemployment, women", "31%", pct(sh(lambda p: p["unemployed"], lf_f)), "CITED"),
        ("Youth unemployment, men 16-24", "40%", pct(sh(lambda p: p["unemployed"], yl_m)), "CITED"),
        ("Youth unemployment, women 16-24", "66%", pct(sh(lambda p: p["unemployed"], yl_f)), "CITED"),
        ("Informal, workers 25+", "52.4%", pct(sh(lambda p: p["informal_job"], [p for p in wk if p["age"] > 24])), "CITED"),
        ("Informal, workers 16-24", "59%", pct(sh(lambda p: p["informal_job"], [p for p in wk if p["age"] <= 24])), "CITED"),
        ("Employment rate, people with disability", "16.1%", pct(sh(lambda p: p["works"], [p for p in pop if p["disabled"]])), "CITED"),
        ("Employment rate, everyone", "36.6% (conflicts with LFPR x unemployment = 32%)", pct(sh(lambda p: p["works"])), "check"),
        ("Below poverty line (JD 100/person/month)", "8.3%", pct(sh(lambda p: p["below_poverty_line"])), "CITED"),
        ("Drives own car", "46.6%", pct(sh(lambda p: p["has_car"])), "DERIVED"),
        ("Public transport main mode", "14%", pct(sh(lambda p: p["main_mode"] in ("bus_brt", "service_taxi"))), "CITED"),
        ("Smartphone / internet user", "95.6%", pct(sh(lambda p: p["has_smartphone"])), "ANCHORED"),
        ("Digital skill: copy/paste (medium+high)", "79.6%", pct(sh(lambda p: p["digital_literacy"] != "low")), "CITED"),
        ("Digital skill: presentation (high)", "32.4%", pct(sh(lambda p: p["digital_literacy"] == "high")), "CITED"),
        ("Used an e-government service", "38.1%", pct(sh(lambda p: p["used_egov"])), "ANCHORED"),
    ]
    hh = sum(p["household_size"] for p in pop) / n
    hh_level = n / sum(1 / p["household_size"] for p in pop)  # undo size bias: household-level mean
    med_pc = sorted(p["per_capita_income_jd"] for p in pop)[n // 2]
    out = [f"## {title}  (n = {n})", "",
           "| Indicator | Research target | Generated | Tag |", "|---|---|---|---|"]
    out += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    out += [f"| Household size (household-level mean) | 4.8 | {hh_level:.2f} (person-level {hh:.2f}) | CITED |",
            f"| Median income per person | not in research | JD {med_pc:.0f}/month | ASSUMPTION shape, calibrated to poverty rate |", ""]
    dc = Counter(p["district_en"] for p in pop)
    tot = sum(d[3] for d in DISTRICTS)
    out += ["| District | 2015 census share | Expected n | Generated n | Engine area |", "|---|---|---|---|---|"]
    for d in DISTRICTS:
        out.append(f"| {d[1]} | {100 * d[3] / tot:.2f}% | {n * d[3] / tot:.1f} | {dc[d[1]]} | {engine_area(d)} |")
    nc = Counter(p["nationality"] for p in pop)
    out += ["", "| Nationality | 2015 census share | Generated |", "|---|---|---|"]
    for k, v in NATIONALITY.items():
        out.append(f"| {k} | {100 * v / TOTAL_2015:.1f}% | {pct((nc[k], n))} |")
    hoods = Counter(p["neighbourhood"] for p in pop)
    src = Counter(p["home_source"] for p in pop)
    out += ["", f"Homes spread over {len(hoods)} neighbourhoods; placement: " + ", ".join(f"{k} {v}" for k, v in src.items())]
    tags = Counter(t for p in pop for t in p["tags"])
    out += ["", "Engine groups: " + ", ".join(f"{k} {v} ({100 * v / n:.1f}%)" for k, v in sorted(tags.items())), ""]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_DEFAULT)
    ap.add_argument("--install", action="store_true", help="also overwrite app/data/population.json with the Jordanian set")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    allres = generate(args.n, "all")
    jo = generate(args.n, "jordanian")
    write_csv(OUT / "residents_all.csv", full_rows(allres))
    (OUT / "residents_all.json").write_text(json.dumps(full_rows(allres), ensure_ascii=False, indent=1), encoding="utf-8")
    write_csv(OUT / "population_jordanian.csv", full_rows(jo))
    (OUT / "population_jordanian.json").write_text(json.dumps(engine_rows(jo), ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "targets.json").write_text(json.dumps(
        {"targets": {k: {"value": v, "tag": t, "source": s} for k, (v, t, s) in T.items()},
         "districts_2015": {d[0]: {"name_en": d[1], "name_ar": d[2], "population_2015": d[3], "lat_est": d[4],
                                   "lng_est": d[5], "engine_area": engine_area(d)} for d in DISTRICTS},
         "nationality_2015": NATIONALITY, "census_source": W}, ensure_ascii=False, indent=1), encoding="utf-8")

    notes = """# Census-anchored population: validation report

Generated by `python -m app.data.seed_census` (seed 42). Source: *Amman in a Box: A Verified Statistical
Blueprint for Policy Simulation* (repo root). Synthetic people, not real residents.

**Legend.** ANCHORED = checked by the team against its source: only the MoDEE 2024 figures marked ANCHORED in
`data/anchors.json` (95.6% internet use and 38.1% e-gov use here; the third, 99% smartphone households, is context).
CITED = quoted in the desk research with a source, NOT verified by the team (CITED_UNVERIFIED or not listed in
`anchors.json`); never present it as an official statistic. DERIVED = computed from cited or anchored values in one
stated step. ASSUMPTION = not in the research, a labelled modelling choice. "check" = the research figures conflict
(see notes). Headline marginals are hit exactly by quota; small gaps come from rounding.

**Notes on the research figures**
- *Difficulty types (9% / 7% / 4%)* add up to more than the 11.2% disability rate, so they can't all be
  "a lot of difficulty" shares of the whole population. They are used as relative weights among people with a
  WG disability (seeing 80%, walking 63%, remembering 36% of them). The generated whole-population shares are
  therefore lower than 9/7/4%.
- *"JD 703 per month" poverty line*: this is very likely JD 703 per person **per year** (DoS 2010 Amman line).
  Per household per month it would put far more than 8.3% of Amman under the line. The generator uses the
  DoS 2017/18 line the research also quotes, JD 100 per person per month, and calibrates incomes so exactly
  8.3% (the Amman rate) fall under it.
- *District table*: the 22 district rows add up to 3,521,207, not the 4,007,526 total printed under the
  table. Only relative district shares are used, so the gap does not bias the sample.
- *Drives own car (46.6%)* = "about half of residents use their own car" × "93.2% of car users hold a licence".
  Household car ownership was NOT FOUND.
- *Employment rate*: LFPR (62.5% / 16%) × (1 − unemployment 19% / 31%) gives ~32% employed, not the 36.6%
  the disability source quotes for 2015. The generator follows the newer LFPR/unemployment figures.
- *Unemployment and participation* are national figures used as an Amman proxy, as the research advises.
- *Wheelchair use, elderly living alone, age bands*: NOT FOUND in the research; labelled assumptions.
- *Homes*: each person gets a neighbourhood of their district (equal odds; no neighbourhood populations in
  the research), then a residential street point within 900 m of it from OpenStreetMap (`home_points.json`),
  or a ~550 m scatter if that file is absent. Neighbourhood points come from Who's On First where available.
- *District coordinates* are estimates of each district's populated centre (±1-2 km), not sourced points.
- Non-Jordanians cannot renew a Jordanian national ID, so the engine population is Jordanians only.

"""
    rep = notes + report(jo, "Engine population: Jordanian nationals 16+") + "\n\n" + report(allres, "All residents 16+ (incl. non-Jordanians)")
    (OUT / "VALIDATION.md").write_text(rep, encoding="utf-8")
    print(rep)

    if args.install:
        (DATA / "population.json").write_text(json.dumps(engine_rows(jo), ensure_ascii=False, indent=1), encoding="utf-8")
        print("\nInstalled population.json. Now run:\n  python -m app.data.fetch_map_data matrix\n"
              "  python -m scripts.pick_heroes\n  pytest -q")


if __name__ == "__main__":
    main()
