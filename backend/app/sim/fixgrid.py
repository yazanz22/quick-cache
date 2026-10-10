"""Candidate-fix grid (CLAUDE.md §6.4). Engine only, no AI, deterministic.

Each candidate is a full Policy = scenario + one change (or a pair of changes),
scored against the scenario it fixes.
"""
from __future__ import annotations

from itertools import combinations

from ..models import CashSupport, FixCandidate, MobileUnit, Office, Policy, TransportVoucher
from . import world
from .assumptions import Assumptions
from .engine import proxy_allowed, run, summarize

VAN_DAYS = ["sat", "thu"]
VAN_HOURS = ("09:00", "14:00")
LATE_CLOSE = "19:00"
TOP_SINGLES_FOR_PAIRS = 5
EPS = 0.05  # percentage points; smaller moves are rounding noise

# ------------------------------------------------------------------ changes

def _van(area: str, day: str):
    a = world.areas()[area]
    def apply(p: Policy) -> Policy:
        q = p.model_copy(deep=True)
        q.mobile_units.append(MobileUnit(area=area, day=day, open=VAN_HOURS[0], close=VAN_HOURS[1]))
        return q
    return {
        "id": f"van:{area}:{day}", "kind": "van", "area": area, "apply": apply,
        "title_ar": f"وحدة متنقلة في {a['name_ar']} يوم {world.DAY_AR[day]} (٩–٢، بدون موعد)",
        "title_en": f"Mobile unit in {a['name_en']} on {world.DAY_EN[day]} (09:00–14:00, walk-in)",
    }

def _late_thu(p: Policy) -> Policy:
    """Keep every office that opens on Thursday open until LATE_CLOSE (same start time). An office closed on
    Thursday stays closed: this toggle extends hours, it never adds an opening day."""
    q = p.model_copy(deep=True)
    for o in q.offices:
        if "thu" in o.schedule and o.schedule["thu"][1] < LATE_CLOSE:
            o.schedule["thu"] = (o.schedule["thu"][0], LATE_CLOSE)
    return q

def _no_appointments(p: Policy) -> Policy:
    q = p.model_copy(deep=True)
    q.appointment_required = False
    return q

def _accessible(p: Policy) -> Policy:
    q = p.model_copy(deep=True)
    for o in q.offices:
        o.wheelchair_accessible = True
    return q

TOGGLES = [
    {"id": "late_thu", "kind": "toggle", "apply": _late_thu,
     "title_ar": "دوام مسائي يوم الخميس لحد الساعة ٧ بكل المكاتب", "title_en": "Late Thursday until 19:00 at every office"},
    {"id": "no_appointments", "kind": "toggle", "apply": _no_appointments,
     "title_ar": "إلغاء شرط الموعد المسبق", "title_en": "Remove the appointment requirement"},
    {"id": "accessible", "kind": "toggle", "apply": _accessible,
     "title_ar": "تجهيز كل المكاتب لذوي الإعاقة الحركية", "title_en": "Make every office wheelchair accessible"},
]

# ------------------------------------------------- everyday_travel changes
# A travel fix never touches fuel_price_change_pct: the fuel price is the government decision being tested.
# Titles use Western digits (CLAUDE.md §9.1).
CASH_GRID = [("low_income", 8.0), ("low_income", 14.0), ("low_income", 20.0),
             ("no_car", 14.0), ("worker", 14.0), ("student", 14.0)]
VOUCHER_GRID = [("low_income", 0.5), ("no_car", 0.5)]
GROUP_AR = {"low_income": "لذوي الدخل المحدود", "no_car": "لمن لا يملكون سيارة", "worker": "للعاملين",
            "student": "للطلاب", "elderly": "لكبار السن", "disabled": "لذوي الإعاقة", "offline": "لغير المتصلين رقمياً"}
GROUP_EN = {"low_income": "low-income people", "no_car": "people without a car", "worker": "workers",
            "student": "students", "elderly": "older people", "disabled": "disabled people", "offline": "offline people"}


def _num(x: float) -> str:
    return f"{x:g}"


def _dinars_ar(x: float) -> str:
    """Arabic counted noun for whole dinars: 3-10 take the plural, others the accusative singular."""
    return f"{_num(x)} دنانير" if float(x).is_integer() and 3 <= x <= 10 else f"{_num(x)} ديناراً"


def _cash(group: str, amount: float):
    def apply(p: Policy) -> Policy:
        q = p.model_copy(deep=True)
        q.cash_support.append(CashSupport(groups=[group], amount_jd_month=amount))
        return q
    return {"id": f"cash:{group}:{_num(amount)}", "kind": "cash", "group": group, "apply": apply,
            "title_ar": f"دعم نقدي {_dinars_ar(amount)} شهرياً {GROUP_AR[group]}",
            "title_en": f"{_num(amount)} JD a month cash support for {GROUP_EN[group]}"}


def _voucher(group: str, amount: float):
    def apply(p: Policy) -> Policy:
        q = p.model_copy(deep=True)
        q.transport_vouchers.append(TransportVoucher(groups=[group], amount_jd=amount))
        return q
    return {"id": f"voucher:{group}:{_num(amount)}", "kind": "voucher", "group": group, "apply": apply,
            "title_ar": f"تغطية أجرة الحافلة أو التاكسي حتى {_num(amount)} دينار لكل رحلة ذهاب وإياب {GROUP_AR[group]}",
            "title_en": f"Bus or taxi fares covered up to {_num(amount)} JD per round trip for {GROUP_EN[group]}"}


def _freeze(field: str):
    def apply(p: Policy) -> Policy:
        return p.model_copy(update={field: 0.0}, deep=True)
    return apply


TRAVEL_TOGGLES = [
    {"id": "freeze_bus_fares", "kind": "toggle", "field": "bus_fare_change_pct", "apply": _freeze("bus_fare_change_pct"),
     "title_ar": "تجميد أجور الحافلات", "title_en": "Freeze bus fares"},
    {"id": "freeze_taxi_fares", "kind": "toggle", "field": "taxi_fare_change_pct",
     "apply": _freeze("taxi_fare_change_pct"), "title_ar": "تجميد تعرفة التاكسي", "title_en": "Freeze taxi fares"},
]


def _travel_singles(scenario: Policy) -> list[dict]:
    """Cash support, fare freezes and transport vouchers. A single is skipped when the scenario already gives that
    group at least as much, or already freezes that fare."""
    def has(entries, group, amount, attr):
        return any(set(e.groups) == {group} and getattr(e, attr) >= amount for e in entries)
    out = [_cash(g, amt) for g, amt in CASH_GRID if not has(scenario.cash_support, g, amt, "amount_jd_month")]
    out += [t for t in TRAVEL_TOGGLES if getattr(scenario, t["field"]) != 0]
    out += [_voucher(g, amt) for g, amt in VOUCHER_GRID if not has(scenario.transport_vouchers, g, amt, "amount_jd")]
    return out


# ----------------------------------------------- medical_exemption changes
# The id_renewal grid with exemption wording (titles in Western digits, CLAUDE.md §9.1) plus three toggles: hybrid
# (apply on Sanad, collect the letter in person), regional intake (intake at the 7 real CSPD offices with the unit's
# hours) and proxy (a relative may make the visits). A fix never changes the service.
#
# Under an online-only scenario (offices ignored), an in-person fix first lifts online_only: Sanad stays on and the
# scenario's offices stay closed (offices = []), then the change adds its channel (a mobile intake day, the CSPD
# intake points). Hybrid is the one fix that reopens the scenario's own offices (for the short collection visit;
# they then also take full applications). Each change is a closure over the scenario, so pairs are order-independent.
EXEMPTION_UNIT_SITE = "royal_court_csu"
DEFAULT_INTAKE_SCHEDULE = {d: ("08:00", "15:00") for d in ("sun", "mon", "tue", "wed", "thu")}


def _lift(p: Policy) -> Policy:
    """A copy of p with in-person channels possible: online_only off (Sanad stays on, the closed offices stay
    closed). A copy of p unchanged when it isn't online-only."""
    q = p.model_copy(deep=True)
    if q.online_only:
        q.online_only, q.online_enabled, q.offices = False, True, []
    return q


def _exemption_van(area: str, day: str):
    a = world.areas()[area]
    def apply(p: Policy) -> Policy:
        q = _lift(p)
        q.mobile_units.append(MobileUnit(area=area, day=day, open=VAN_HOURS[0], close=VAN_HOURS[1]))
        return q
    return {"id": f"van:{area}:{day}", "kind": "van", "area": area, "apply": apply,
            "title_ar": f"يوم استقبال متنقل في {a['name_ar']} يوم {world.DAY_AR[day]} (9:00–14:00، بدون موعد)",
            "title_en": f"Mobile intake day in {a['name_en']} on {world.DAY_EN[day]} (09:00–14:00, walk-in)"}


def _cspd_sites() -> list[str]:
    return sorted(s for s in world.sites() if s.startswith("cspd_"))


def _regional_intake(scenario: Policy):
    """Add an exemption intake office at every real CSPD site that has no office yet, with the hours of the Royal
    Court unit in the scenario (or of its first office; Sun-Thu 08:00-15:00 if it has none)."""
    src = next((o for o in scenario.offices if o.site_id == EXEMPTION_UNIT_SITE),
               scenario.offices[0] if scenario.offices else None)
    schedule = dict(src.schedule) if src else dict(DEFAULT_INTAKE_SCHEDULE)
    def apply(p: Policy) -> Policy:
        q = _lift(p)
        have, sites = {o.site_id for o in q.offices}, world.sites()
        for sid in _cspd_sites():
            if sid not in have:
                s = sites[sid]
                q.offices.append(Office(id=f"intake_{sid.removeprefix('cspd_')}", site_id=sid, schedule=dict(schedule),
                                        name_ar=f"استقبال طلبات الإعفاء في {s['name_ar']}",
                                        name_en=f"Exemption intake at {s['name_en']}", wheelchair_accessible=True))
        return q
    return {"id": "regional_intake", "kind": "toggle", "apply": apply,
            "title_ar": "استقبال طلبات الإعفاء في مكاتب الأحوال المدنية السبعة بساعات الدائرة نفسها",
            "title_en": "Exemption intake at the 7 Civil Status offices, same hours as the unit"}


def _hybrid(scenario: Policy):
    reopen = list(scenario.offices) if scenario.online_only else []
    def apply(p: Policy) -> Policy:
        q = _lift(p)
        q.hybrid_pickup, q.online_enabled = True, True
        ids = {o.id for o in q.offices}
        q.offices += [o.model_copy(deep=True) for o in reopen if o.id not in ids]
        return q
    if reopen:
        title_ar = "إبقاء منصة سند وإعادة فتح المكتب: التقديم عبر سند ثم زيارة واحدة قصيرة لاستلام الكتاب"
        title_en = "Keep Sanad and reopen the office: apply online, then one short visit to collect the letter"
    else:
        title_ar = "التقديم عبر منصة سند ثم زيارة واحدة قصيرة لاستلام الكتاب"
        title_en = "Apply online via Sanad, then one short visit to collect the letter"
    return {"id": "hybrid", "kind": "toggle", "apply": apply, "title_ar": title_ar, "title_en": title_en}


def _proxy(p: Policy) -> Policy:
    return p.model_copy(update={"proxy_allowed": True}, deep=True)


EXEMPTION_OFFICE_TOGGLES = [  # meaningful only with offices in play (skipped under online_only)
    {"id": "late_thu", "kind": "toggle", "apply": _late_thu,
     "title_ar": "دوام مسائي يوم الخميس حتى الساعة 19:00 في كل المكاتب", "title_en": "Late Thursday until 19:00 at every office"},
    {"id": "no_appointments", "kind": "toggle", "apply": _no_appointments,
     "title_ar": "إلغاء شرط الموعد المسبق", "title_en": "Remove the appointment requirement"},
    {"id": "accessible", "kind": "toggle", "apply": _accessible,
     "title_ar": "تجهيز كل المكاتب لذوي الإعاقة الحركية", "title_en": "Make every office wheelchair accessible"},
    {"id": "proxy", "kind": "toggle", "apply": _proxy,
     "title_ar": "السماح لقريب من الدرجة الأولى بالمراجعة نيابة عن المريض",
     "title_en": "Let a first-degree relative make the visits on the patient's behalf"},
]


def _exemption_singles(scenario: Policy) -> list[dict]:
    """Mobile intake days (8 areas x Sat/Thu), then hybrid, regional intake and, with offices in play, late Thursday,
    no appointments, accessible and proxy. A change that leaves the policy as it is, is skipped; so is proxy when the
    scenario already allows it (explicitly or by the service default)."""
    existing = {(m.area, m.day) for m in scenario.mobile_units}
    out = [_exemption_van(area, day) for area in world.areas() for day in VAN_DAYS if (area, day) not in existing]
    toggles = [_hybrid(scenario), _regional_intake(scenario)]
    if not scenario.online_only:
        toggles += [t for t in EXEMPTION_OFFICE_TOGGLES if not (t["id"] == "proxy" and proxy_allowed(scenario))]
    out += [t for t in toggles if t["apply"](scenario).model_dump() != scenario.model_dump()]
    return out


def _same_slot(a: dict, b: dict) -> bool:
    """Two singles that can't be paired: two vans in the same area, or two cash supports for the same group."""
    return a["kind"] == b["kind"] and (
        (a["kind"] == "van" and a["area"] == b["area"]) or (a["kind"] == "cash" and a["group"] == b["group"]))


def singles(scenario: Policy) -> list[dict]:
    if scenario.service == "everyday_travel":
        return _travel_singles(scenario)
    if scenario.service == "medical_exemption":
        return _exemption_singles(scenario)
    out = []
    existing = {(m.area, m.day) for m in scenario.mobile_units}
    if not scenario.online_only:  # online_only ignores vans and offices entirely
        for area in world.areas():
            for day in VAN_DAYS:
                if (area, day) not in existing:
                    out.append(_van(area, day))
    for t in TOGGLES:
        if t["apply"](scenario).model_dump() != scenario.model_dump():  # skip toggles that change nothing
            out.append(t)
    return out

# ------------------------------------------------------------------ scoring

def score(policy: Policy, scen_kpis: dict, scen_groups: dict, pop=None, assumptions: Assumptions | None = None) -> dict:
    pop = pop if pop is not None else world.population()
    k, g = summarize(run(policy, pop, assumptions), pop)
    worsens = any(
        g[x]["left_out"] > scen_groups[x]["left_out"] + EPS
        or (g[x]["left_out"] + g[x]["hardship"]) > (scen_groups[x]["left_out"] + scen_groups[x]["hardship"]) + EPS
        for x in world.EQUITY_GROUPS)
    return {"left_out_drop": round(scen_kpis["pct_left_out"] - k["pct_left_out"], 1),
            "hardship_drop": round(scen_kpis["pct_hardship"] - k["pct_hardship"], 1),
            "worsens_any_group": worsens, "kpis": k, "groups": g}

def rank_key(c: dict):
    return (-c["left_out_drop"], -c["hardship_drop"], c["n_changes"], c["id"])

def build(scenario: Policy, pop=None, assumptions: Assumptions | None = None) -> list[dict]:
    """All scored candidates (singles + pairs), ranked, excluding ones that worsen a group or don't help."""
    pop = pop if pop is not None else world.population()
    sk, sg = summarize(run(scenario, pop, assumptions), pop)

    scored = []
    for ch in singles(scenario):
        p = ch["apply"](scenario)
        scored.append({**ch, "policy": p, "n_changes": 1, "parts": [ch], **score(p, sk, sg, pop, assumptions)})
    useful = sorted([c for c in scored if not c["worsens_any_group"]
                     and (c["left_out_drop"] > 0 or c["hardship_drop"] > 0)], key=rank_key)

    pairs = []
    for a, b in combinations(useful[:TOP_SINGLES_FOR_PAIRS], 2):
        if _same_slot(a, b):
            continue
        p = b["apply"](a["apply"](scenario))
        pairs.append({
            "id": f"pair:{a['id']}+{b['id']}", "kind": "pair", "policy": p, "n_changes": 2, "parts": [a, b],
            "title_ar": f"{a['title_ar']} + {b['title_ar']}", "title_en": f"{a['title_en']} + {b['title_en']}",
            **score(p, sk, sg, pop, assumptions)})
    allc = useful + [c for c in pairs if not c["worsens_any_group"] and (c["left_out_drop"] > 0 or c["hardship_drop"] > 0)]
    return sorted(allc, key=rank_key)

def to_candidate(c: dict, source: str = "engine_grid") -> FixCandidate:
    """A scored candidate (from build() or score()) as the API's FixCandidate, with the fix policy's kpis."""
    return FixCandidate(id=c["id"], title_ar=c["title_ar"], title_en=c["title_en"], policy=c["policy"], source=source,
                        left_out_drop=c["left_out_drop"], hardship_drop=c["hardship_drop"],
                        worsens_any_group=c["worsens_any_group"], n_changes=c.get("n_changes", 1),
                        kpis=c.get("kpis") or {})

def top_fixes(scenario: Policy, n: int = 3, pop=None, assumptions: Assumptions | None = None) -> list[FixCandidate]:
    return [to_candidate(c) for c in build(scenario, pop, assumptions)[:n]]

def all_policies(scenario: Policy) -> list[Policy]:
    """Every grid policy (singles + all pairs), for the AI-proposal duplicate check."""
    sing = singles(scenario)
    out = [s["apply"](scenario) for s in sing]
    out += [b["apply"](a["apply"](scenario)) for a, b in combinations(sing, 2)]
    return out
