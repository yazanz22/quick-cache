"""Policy checks beyond the Pydantic schema: known sites/areas/roads, sane hours."""
from __future__ import annotations

from ..models import Policy
from . import world


def _hhmm(s: str) -> bool:
    return (isinstance(s, str) and len(s) == 5 and s[2] == ":" and s[:2].isdigit() and s[3:].isdigit()
            and int(s[:2]) < 24 and int(s[3:]) < 60)


def policy_errors(p: Policy) -> list[str]:
    sites, areas = world.sites(), world.areas()
    errs = []
    for o in p.offices:
        if o.site_id not in sites:
            errs.append(f"unknown site_id {o.site_id!r}; valid: {sorted(sites)}")
        for d, (op, cl) in o.schedule.items():
            if not (_hhmm(op) and _hhmm(cl) and op < cl):
                errs.append(f"bad hours for office {o.id} on {d}: {op}-{cl}")
    for m in p.mobile_units:
        if m.area not in areas:
            errs.append(f"unknown area {m.area!r}; valid: {sorted(areas)}")
        if not (_hhmm(m.open) and _hhmm(m.close) and m.open < m.close):
            errs.append(f"bad mobile unit hours {m.open}-{m.close}")
    roads = world.roads()
    for r in p.closed_roads:
        if r not in roads:
            errs.append(f"unknown road {r!r}; valid: {sorted(roads)}")
    if p.fee_jd < 0:
        errs.append("fee_jd must be >= 0")
    if p.service != "id_renewal":
        errs.append("only the id_renewal service is modelled")
    return errs


def canonical(p: Policy) -> str:
    """Order-independent identity of a policy (for duplicate checks)."""
    import json
    d = p.model_dump(mode="json")
    d["offices"] = sorted(({**o, "schedule": dict(sorted(o["schedule"].items())), "name_ar": "", "name_en": ""}
                           for o in d["offices"]), key=lambda o: o["id"])
    d["mobile_units"] = sorted(d["mobile_units"], key=lambda m: (m["area"], m["day"], m["open"], m["close"]))
    d["closed_roads"] = sorted(set(d["closed_roads"]))
    return json.dumps(d, sort_keys=True)


def count_changes(before: Policy, after: Policy) -> int:
    """Rough number of distinct policy changes, for keeping AI proposals comparable to grid fixes.
    Each added/removed mobile unit = 1. Per office: moved, accessibility, days added, days removed,
    hours changed on existing days = 1 each. Each global setting changed = 1. Added/removed office = 1.
    Each road closed or reopened = 1."""
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
    n += len(set(before.closed_roads) ^ set(after.closed_roads))
    for f in ("online_enabled", "online_only", "appointment_required", "fee_jd", "visits_required"):
        n += getattr(before, f) != getattr(after, f)
    return n
