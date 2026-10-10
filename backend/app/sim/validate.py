"""Policy checks beyond the Pydantic schema: known sites/areas, sane hours, finite numbers, no contradictions.
Messages are short readable English (the UI shows its own translated message next to them)."""
from __future__ import annotations

import json
import math

from ..models import Policy
from . import world
from .assumptions import DEFAULT
from .travel import to_min

MAX_FEE_JD = 1000
TRAVEL_PCT_RANGE = (-50, 200)   # fuel and fare changes, percent (everyday_travel)


def _hhmm(s: str) -> bool:
    return (isinstance(s, str) and len(s) == 5 and s[2] == ":" and s[:2].isdigit() and s[3:].isdigit()
            and int(s[:2]) < 24 and int(s[3:]) < 60)


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def _window_errors(what: str, op: str, cl: str) -> list[str]:
    """Hours must be HH:MM, open before close, and long enough for one visit at the counter."""
    if not (_hhmm(op) and _hhmm(cl) and op < cl):
        return [f"bad hours for {what}: {op}-{cl}"]
    need = DEFAULT.SERVICE_MINUTES
    if to_min(cl) - to_min(op) < need:
        return [f"{what} is open {op}-{cl}, shorter than one visit ({need:g} min)"]
    return []


def policy_errors(p: Policy) -> list[str]:
    sites, areas = world.sites(), world.areas()
    errs = []
    for o in p.offices:
        if o.site_id not in sites:
            errs.append(f"unknown site_id {o.site_id!r}; valid: {sorted(sites)}")
        for d, (op, cl) in o.schedule.items():  # an empty schedule (closed every day) is allowed
            errs += _window_errors(f"office {o.id} on {d}", op, cl)
    for m in p.mobile_units:
        if m.area not in areas:
            errs.append(f"unknown area {m.area!r}; valid: {sorted(areas)}")
        errs += _window_errors(f"mobile unit in {m.area} on {m.day}", m.open, m.close)
    for g, pct in p.fee_discounts.items():
        if not (_finite(pct) and 0 <= pct <= 100):
            errs.append(f"fee discount for {g} must be 0-100 percent, got {pct}")
    if p.home_visits is not None and not p.home_visits.groups:
        errs.append("home_visits needs at least one eligible group")
    for v in p.transport_vouchers:
        if not v.groups:
            errs.append("each transport voucher needs at least one group")
        if not _finite(v.amount_jd):
            errs.append(f"transport voucher amount_jd must be a finite number, got {v.amount_jd}")
    if not _finite(p.fee_jd):
        errs.append(f"fee_jd must be a finite number, got {p.fee_jd}")
    elif p.fee_jd < 0:
        errs.append("fee_jd must be >= 0")
    elif p.fee_jd > MAX_FEE_JD:
        errs.append(f"fee_jd must be at most {MAX_FEE_JD} JD")
    if p.online_only and not p.online_enabled:
        errs.append("online_only needs online_enabled (online-only with online switched off is a contradiction)")
    lo, hi = TRAVEL_PCT_RANGE
    for name in ("fuel_price_change_pct", "bus_fare_change_pct", "taxi_fare_change_pct"):
        v = getattr(p, name)
        if v is None and name != "fuel_price_change_pct":
            continue
        if not _finite(v):
            errs.append(f"{name} must be a finite number, got {v}")
        elif not lo <= v <= hi:
            errs.append(f"{name} must be between {lo} and {hi} percent, got {v:g}")
    for s in p.cash_support:
        if not s.groups:
            errs.append("each cash support entry needs at least one group")
        if not _finite(s.amount_jd_month):
            errs.append(f"cash support amount_jd_month must be a finite number, got {s.amount_jd_month}")
    if p.service not in ("id_renewal", "everyday_travel"):
        errs.append(f"unknown service {p.service!r}")
    return errs


def canonical(p: Policy) -> str:
    """Order-independent identity of a policy (for duplicate checks)."""
    d = p.model_dump(mode="json")
    d["offices"] = sorted(({**o, "schedule": dict(sorted(o["schedule"].items())), "name_ar": "", "name_en": ""}
                           for o in d["offices"]), key=lambda o: o["id"])
    d["mobile_units"] = sorted(d["mobile_units"], key=lambda m: (m["area"], m["day"], m["open"], m["close"]))
    d["appointment_exempt_groups"] = sorted(set(d["appointment_exempt_groups"]))
    d["transport_vouchers"] = sorted(({**v, "groups": sorted(set(v["groups"]))} for v in d["transport_vouchers"]),
                                     key=lambda v: (v["groups"], v["amount_jd"]))
    if d["home_visits"]:
        d["home_visits"]["groups"] = sorted(set(d["home_visits"]["groups"]))
    d["cash_support"] = sorted(({**s, "groups": sorted(set(s["groups"]))} for s in d["cash_support"]),
                               key=lambda s: (s["groups"], s["amount_jd_month"]))
    return json.dumps(d, sort_keys=True)


def count_changes(before: Policy, after: Policy) -> int:
    """Rough number of distinct policy changes, for keeping AI proposals comparable to grid fixes.
    Each added/removed mobile unit = 1. Per office: moved, accessibility, days added, days removed,
    hours changed on existing days = 1 each. Each global setting changed = 1. Added/removed office = 1.
    Each group protection changed (walk-in exemptions, fee discounts, home
    visits, transport vouchers, hybrid pickup) = 1. everyday_travel: the fuel change, the bus fare and the taxi fare
    setting = 1 each; cash support = 1 per group set whose amount changed."""
    n = 0
    mu = lambda p: {(m.area, m.day, m.open, m.close) for m in p.mobile_units}
    n += len(mu(before) ^ mu(after))
    bo, ao = {o.id: o for o in before.offices}, {o.id: o for o in after.offices}
    n += len(set(bo) ^ set(ao))
    for oid in set(bo) & set(ao):
        b, a = bo[oid], ao[oid]
        n += b.site_id != a.site_id
        n += b.wheelchair_accessible != a.wheelchair_accessible
        n += bool(set(a.schedule) - set(b.schedule))
        n += bool(set(b.schedule) - set(a.schedule))
        n += any(tuple(b.schedule[d]) != tuple(a.schedule[d]) for d in set(a.schedule) & set(b.schedule))
    bd, ad = json.loads(canonical(before)), json.loads(canonical(after))
    for f in ("appointment_exempt_groups", "fee_discounts", "home_visits", "transport_vouchers", "hybrid_pickup"):
        n += bd[f] != ad[f]
    for f in ("online_enabled", "online_only", "appointment_required", "fee_jd", "visits_required",
              "fuel_price_change_pct", "bus_fare_change_pct", "taxi_fare_change_pct", "service"):
        n += getattr(before, f) != getattr(after, f)
    cash = lambda p: {tuple(sorted(set(s.groups))): max(x.amount_jd_month for x in p.cash_support
                                                         if set(x.groups) == set(s.groups)) for s in p.cash_support}
    cb, ca = cash(before), cash(after)
    n += sum(cb.get(k) != ca.get(k) for k in set(cb) | set(ca))
    return n
