"""The four AI jobs (CLAUDE.md §2): parse, voice, report, explain + propose fixes.

Every task: cache first (re-checked) -> (live only) AI call -> validate (Pydantic / grounding) ->
retry once with the error -> else the deterministic fallback. Never a blank.

CACHE KEYS: the `inputs` of each task (voice_facts, the parse inputs, report_summary, the fixes inputs,
policy_json) are what the committed cache is keyed on. Changing what goes into them invalidates the
warmed demo cache. Prompts, checks and fallbacks are not part of any key.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import Counter
from typing import Callable, NamedTuple

from pydantic import ValidationError

from .. import config
from ..models import (CompareResult, FixCandidate, FixesResponse, ParseResult, Policy, ReportResponse,
                      SensitivityResult, VoiceResponse)
from ..sim import fixgrid, world
from ..sim.engine import STATUS_RANK, run, summarize
from ..sim.validate import canonical, count_changes, policy_errors
from . import cache, checks, fallbacks, prompts
from .client import LLMUnavailable, complete

log = logging.getLogger("nas.llm")


MAX_AI_CHANGES = 3  # keep the AI's idea comparable with grid pairs
# Group protections are manual levers (CLAUDE.md §6.4): an AI fix proposal must leave them as in the scenario.
PROTECTION_FIELDS = ("appointment_exempt_groups", "fee_discounts", "home_visits", "transport_vouchers", "hybrid_pickup")

TRAVEL = "everyday_travel"
# Policy fields by service. Under everyday_travel only the travel levers (+ transport_vouchers, shared) apply; under
# id_renewal the travel levers are no-ops. A parse or an AI fix must keep the other service's fields as they are.
ID_RENEWAL_FIELDS = ("offices", "online_enabled", "online_only", "mobile_units", "appointment_required", "fee_jd",
                     "visits_required", "appointment_exempt_groups", "fee_discounts", "home_visits", "hybrid_pickup")
TRAVEL_FIELDS = ("fuel_price_change_pct", "bus_fare_change_pct", "taxi_fare_change_pct", "cash_support")
# The only levers an AI fix proposal may use for everyday_travel (the fuel price is the decision under test).
TRAVEL_PROPOSAL_FIELDS = ("cash_support", "bus_fare_change_pct", "taxi_fare_change_pct", "transport_vouchers")
SENSITIVITY_PCT = 20  # the ±20% of the robustness check: allowed in report text, never part of the cache key


class Rejected(ValueError):
    pass


# Anything a check may raise on a bad AI shape (wrong types, missing keys, invalid policy).
_CHECK_ERRORS = (Rejected, ValidationError, KeyError, TypeError, ValueError, AttributeError)


class Answer(NamedTuple):
    out: object | None   # the checked output, or None (the caller uses its fallback)
    why: str             # "cache", "ai", "offline", "unavailable" (no answer / no time) or "rejected" (answered, failed checks)
    meta: dict           # provider/model of a fresh AI answer


def _loads(raw: str) -> dict:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        d = json.loads(raw)
    except json.JSONDecodeError as e:
        raise Rejected(f"not valid JSON: {e}") from e
    if not isinstance(d, dict):
        raise Rejected("expected a JSON object")
    return d


def _left(started_at: float | None) -> float | None:
    """What is left of this request's AI budget (LLM_TOTAL_BUDGET_S), counted from the request's start."""
    return None if started_at is None else config.LLM_TOTAL_BUDGET_S - (time.monotonic() - started_at)


def _ai(task: str, inputs, system: str, user: str, check: Callable[[str, bool], object], *,
        smart: bool, want_json: bool, use_cache: bool = True, budget: float | None = None,
        keep: Callable[[object], bool] | None = None) -> Answer:
    """Cached, validated AI call.

    A cache hit is re-checked (cheaply, with the same check as a fresh answer), so a stale entry, e.g. a parse
    or proposal naming a site that no longer exists, never reaches the engine; it then counts as a miss.
    budget: seconds left for the AI (default LLM_TOTAL_BUDGET_S); both attempts share it.
    keep: if given, a fresh answer is cached only when keep(out) is true (it is still returned)."""
    if use_cache:
        hit = cache.get(task, inputs)
        if hit is not None:
            try:
                return Answer(check(hit if isinstance(hit, str) else json.dumps(hit, ensure_ascii=False), True),
                              "cache", {})
            except _CHECK_ERRORS as e:
                log.warning("%s: cached answer fails today's checks, treating it as a miss: %s", task, str(e)[:300])
    if config.DEMO_OFFLINE:
        return Answer(None, "offline", {})
    msg = user
    deadline = time.monotonic() + (config.LLM_TOTAL_BUDGET_S if budget is None else budget)
    why = "unavailable"
    for attempt in range(2):
        left = deadline - time.monotonic()
        if attempt and left < 3.0:
            break  # no time for a retry; the caller uses the template
        try:
            raw = complete(task, system, msg, json_schema={} if want_json else None, smart=smart, budget_s=left)
        except LLMUnavailable as e:
            log.warning("%s: AI unavailable, using fallback (%s)", task, e)
            return Answer(None, "unavailable", {})
        try:
            out = check(raw, attempt == 1)
        except _CHECK_ERRORS as e:
            why = "rejected"
            log.warning("%s: rejected AI output (attempt %d): %s", task, attempt + 1, str(e)[:300])
            msg = f"{user}\n\nYour previous answer was rejected: {str(e)[:500]}\nFix it and answer again."
            continue
        meta = dict(getattr(raw, "meta", None) or {})
        if use_cache and (keep is None or keep(out)):
            cache.put(task, inputs, out, meta)
        return Answer(out, "ai", meta)
    return Answer(None, why, {})


def _sites_areas() -> dict:
    return {"sites": [{"id": s["id"], "area": s["area"], "name_en": s["name_en"], "name_ar": s["name_ar"],
                       "real_cspd_office": s.get("real", False)}
                      for s in world.sites().values()],
            "areas": [{"id": a["id"], "name_en": a["name_en"], "name_ar": a["name_ar"], "side": a["side"]}
                      for a in world.areas().values()]}


# Policy fields added after the AI cache was warmed, with their defaults.
_LATER_FIELDS = {"appointment_exempt_groups": [], "fee_discounts": {}, "home_visits": None,
                 "transport_vouchers": [], "hybrid_pickup": False,
                 # everyday_travel levers (2026-10-10): no-ops for id_renewal, so they stay out of its keys
                 "fuel_price_change_pct": 0.0, "bus_fare_change_pct": None, "taxi_fare_change_pct": None,
                 "cash_support": []}


def policy_json(p: Policy) -> dict:
    """A policy as JSON for cache keys. Fields added later are left out while at their default, so keys made
    before they existed (the warmed demo cache) still match."""
    d = p.model_dump(mode="json")
    for k, default in _LATER_FIELDS.items():
        if k in d and d[k] == default:
            d.pop(k)
    return d


def _str_or_none(d: dict, k: str):
    v = d.get(k)
    if v is not None and not isinstance(v, str):
        raise Rejected(f"{k} must be a string")
    return v


# ---------------------------------------------------------------------- parse

def _fields_changed(a: Policy, b: Policy, fields) -> list[str]:
    """Which of `fields` differ between two policies (order-independent, via validate.canonical)."""
    da, db = json.loads(canonical(a)), json.loads(canonical(b))
    return [f for f in fields if da.get(f) != db.get(f)]


def _other_service_fields(service: str) -> tuple[str, ...]:
    return ID_RENEWAL_FIELDS if service == TRAVEL else TRAVEL_FIELDS


def travel_reference() -> dict:
    """Public reference figures quoted in the travel parse prompt (not part of any cache key)."""
    return {"fuel_90_octane_jd_per_litre_oct_2026": 1.05, "last_rise_jd_per_litre": 0.05,
            "national_aid_fund_fuel_support_jd_month": [8, 14], "default_student_bus_voucher_jd_per_round_trip": 3}


def _check_parse(raw: str, cur: dict, text: str, current: Policy | None = None) -> dict:
    d = _loads(raw)
    status = d.get("status")
    if status == "ok":
        pol = Policy.model_validate(d.get("policy"))
        errs = policy_errors(pol)
        if errs:
            raise Rejected("; ".join(errs))
        if current is not None:
            if pol.service != current.service:
                raise Rejected(f'keep "service": "{current.service}" (the parse never switches the service)')
            other = _fields_changed(current, pol, _other_service_fields(current.service))
            if other:
                raise Rejected(f"under {current.service} these fields don't apply and must stay exactly as in the "
                               f"current policy: {', '.join(other)}")
        out = {"status": "ok", "policy": pol.model_dump(mode="json"), "changes_ar": d.get("changes_ar"),
               "changes_en": d.get("changes_en"), "message_ar": None, "message_en": None}
        if not out["changes_ar"] or not out["changes_en"]:
            raise Rejected("changes_ar and changes_en must list the changes")
        # The full response model, so a bad shape (e.g. changes_ar as a string) is a rejection here, not a
        # cached answer that fails later with a 500.
        ParseResult.model_validate({**out, "source": "ai"})
        also = travel_reference() if current is not None and current.service == TRAVEL else None
        bad = checks.ungrounded(" ".join(out["changes_ar"] + out["changes_en"]), [cur, out["policy"], text], also=also)
        if bad:
            raise Rejected(f"change list mentions numbers not in the policy: {bad}")
        return out
    if status == "unsupported":
        out = {"status": "unsupported", "policy": None, "changes_ar": [], "changes_en": [],
               "message_ar": d.get("message_ar"), "message_en": d.get("message_en")}
        if not out["message_ar"] or not out["message_en"]:
            raise Rejected("unsupported answers need message_ar and message_en")
        ParseResult.model_validate({**out, "source": "ai"})
        return out
    raise Rejected("status must be 'ok' or 'unsupported'")


def parse_policy(text: str, current: Policy, lang: str = "ar") -> ParseResult:
    """lang (the official's UI language) only goes into the prompt, not the cache key: the answer carries
    both languages either way."""
    cur = policy_json(current)
    inputs = {"text": cache.normalize_text(text), "current_policy": cur}   # the service is inside current_policy
    if current.service == TRAVEL:
        context = {"groups": list(world.ALL_GROUPS), "reference": travel_reference()}
    else:
        context = _sites_areas()
    user = json.dumps({"current_policy": cur, **context, "official_text": text, "official_ui_language": lang},
                      ensure_ascii=False)
    a = _ai("parse", inputs, prompts.system("parse", current.service), user,
            lambda raw, final: _check_parse(raw, cur, text, current), smart=True, want_json=True)
    if a.out is None:
        # "rejected": the AI answered but its output failed the checks twice; otherwise there was no AI answer.
        return fallbacks.parse_failed() if a.why == "rejected" else fallbacks.parse_unavailable()
    return ParseResult(**a.out, source="ai")


# ---------------------------------------------------------------------- voice

STATUS_MEANING_TRAVEL = {"served": "fine", "hardship": "squeezed", "left_out": "priced_out"}


def _r1(x) -> float:
    return round(float(x or 0), 1)


def travel_voice_facts(citizen: dict, o: dict) -> dict:
    """everyday_travel voice input (and cache key): the profile, the regular trip and its monthly money. Every number a
    travel voice may say comes from here (grounding check)."""
    a = world.areas()[citizen["area"]]
    facts = {
        "register": "msa", "service": TRAVEL,
        "profile": {
            "age": citizen["age"], "gender": citizen["gender"], "area_ar": a["name_ar"], "mobility": citizen["mobility"],
            "has_car": citizen["has_car"], "works": citizen["works"], "income_band": citizen["income_band"],
            "helper_relation_ar": fallbacks.msa_helper(citizen["helper_relation_ar"]),
        },
        "status": o["status"], "status_meaning": STATUS_MEANING_TRAVEL[o["status"]], "reasons": o.get("reasons", []),
    }
    if o.get("purpose") is None:  # channel "no_regular_trip"
        facts["regular_trip"] = False
        return facts
    hub = fallbacks.trip_hub(o)
    facts["regular_trip"] = True
    facts["trip"] = {
        "purpose": o["purpose"], "destination_ar": hub["name_ar"] if hub else o.get("channel_name_ar"),
        "mode": o.get("mode"), "bus_transfers": o.get("bus_transfers", 0), "days_per_week": o.get("days_per_week"),
        "travel_minutes_one_way": round(o.get("travel_minutes") or 0),
        "monthly_hours_in_transit": _r1(o.get("hours_lost")),
    }
    facts["money"] = {
        "monthly_cost_before_jd": _r1(o.get("monthly_cost_before_jd")), "monthly_cost_now_jd": _r1(o.get("cost_jd")),
        "extra_jd_month": _r1(o.get("extra_jd_month")), "income_share_pct": round(float(o.get("income_share_pct") or 0)),
        "cash_support_jd_month": _r1(o.get("cash_support_jd_month")),
    }
    return facts


def voice_facts(citizen: dict, o: dict) -> dict:
    """The voice input (and cache key). id_renewal facts are exactly what they always were (the warmed demo voices)."""
    if fallbacks.is_travel_outcome(o):
        return travel_voice_facts(citizen, o)
    a = world.areas()[citizen["area"]]
    facts = {
        "register": "msa",  # voices are فصحى; part of the cache key so old dialect voices are never reused
        "profile": {
            "age": citizen["age"], "gender": citizen["gender"], "area_ar": a["name_ar"],
            "mobility": citizen["mobility"], "has_car": citizen["has_car"], "has_smartphone": citizen["has_smartphone"],
            "digital_literacy": citizen["digital_literacy"], "works": citizen["works"],
            "work_start": citizen["work_start"], "work_end": citizen["work_end"],
            "income_band": citizen["income_band"], "helper_relation_ar": fallbacks.msa_helper(citizen["helper_relation_ar"]),
        },
        "outcome": {
            "status": o["status"], "reasons": o.get("reasons", []), "channel_name_ar": o.get("channel_name_ar"),
            "mode": o.get("mode"), "bus_transfers": o.get("bus_transfers", 0),
            "visit_day_ar": world.DAY_AR.get(o.get("visit_day") or "", None),
            "travel_minutes_one_way": round(o.get("travel_minutes", 0)),
            "total_cost_jd": round(o.get("cost_jd", 0), 1), "total_hours_lost_incl_waiting": round(o.get("hours_lost", 0), 1),
            "work_hours_missed": round(o.get("work_hours_missed", 0), 1),
        },
    }
    return facts


def voice_citizen(citizen: dict, outcome: dict, started_at: float | None = None) -> VoiceResponse:
    facts = voice_facts(citizen, outcome)
    travel = facts.get("service") == TRAVEL
    fb_ar, fb_en = fallbacks.voice(citizen, outcome)
    user = json.dumps(facts, ensure_ascii=False)
    helper = fallbacks.msa_helper(citizen["helper_relation_ar"])

    def check(raw: str, final: bool):
        t = (raw or "").strip().strip('"“”«»').strip()
        if not checks.has_arabic(t) or len(t) > 450:
            raise Rejected("must be 1-3 short Arabic sentences")
        bad = checks.ungrounded(t, facts)
        if bad:
            raise Rejected(f"numbers not in the facts: {bad}")
        extra = checks.foreign_people(t, helper)
        if extra:
            raise Rejected(f"mentions people other than the helper: {extra}")
        style = checks.voice_style_problems(t, helper) + (checks.travel_voice_problems(t) if travel else [])
        if style:
            raise Rejected("; ".join(style))
        return t

    a = _ai("voice", facts, prompts.system("voice", TRAVEL if travel else "id_renewal"), user, check, smart=False,
            want_json=False, budget=_left(started_at))
    if a.out is None:
        return VoiceResponse(text_ar=fb_ar, summary_en=fb_en, source="fallback")
    return VoiceResponse(text_ar=a.out, summary_en=fb_en, source="ai")


# --------------------------------------------------------------------- report

# The travel KPIs engine.summarize adds for everyday_travel outcomes that go into the travel report.
TRAVEL_REPORT_KPIS = ("avg_extra_jd_month", "avg_monthly_cost_jd", "n_cash_support", "by_purpose", "by_mode")


def is_travel_result(cr: CompareResult) -> bool:
    """The engine adds the travel KPIs (n_with_trip, ...) to everyday_travel results only."""
    return "n_with_trip" in cr.scenario.kpis


def report_summary(cr: CompareResult, sens: SensitivityResult | None, applied_fix: dict | None = None) -> dict:
    """The report's input (and cache key). Without an applied fix it is exactly what it always was, so the
    warmed report entries still hit; `applied_fix` (from fix_effect) adds one block. For everyday_travel (and only
    then) it also carries "service" and a "travel" block with the engine's travel KPIs."""
    keys = ["pct_served", "pct_hardship", "pct_left_out", "avg_hours_lost", "avg_cost_jd"]
    bg, sg = cr.baseline.by_group, cr.scenario.by_group
    reasons = Counter(r for o in cr.scenario.outcomes if o.status != "served" for r in o.reasons)
    summary = {
        "n_citizens": len(cr.scenario.outcomes),
        "baseline_kpis": {k: cr.baseline.kpis[k] for k in keys},
        "scenario_kpis": {k: cr.scenario.kpis[k] for k in keys},
        "kpi_delta": {k: cr.kpi_delta.get(k) for k in keys},
        "worst_groups": cr.worst_groups,
        "group_deltas": {g: round((sg[g]["left_out"] + sg[g]["hardship"]) - (bg[g]["left_out"] + bg[g]["hardship"]), 1)
                         for g in world.EQUITY_GROUPS},
        "group_scenario": {g: {"hardship": sg[g]["hardship"], "left_out": sg[g]["left_out"]} for g in world.EQUITY_GROUPS},
        "people_newly_worse": len(cr.flipped_worse),
        "top_reasons_not_served": dict(reasons.most_common(4)),
        "sensitivity": None if sens is None else {
            "runs": sens.runs, "ranking_held": sens.ranking_held,
            # Only report the fix check if a fix was actually tested.
            **({"fix_still_helps": sens.fix_still_helps, "passed": sens.passed} if sens.fix_checked else {}),
            "stable_top_group": sens.stable_top_group, "stable_top2": sens.stable_top2},
    }
    if is_travel_result(cr):
        summary["service"] = TRAVEL
        summary["travel"] = {side: {k: r.kpis[k] for k in TRAVEL_REPORT_KPIS if k in r.kpis}
                             for side, r in (("baseline", cr.baseline), ("scenario", cr.scenario))}
    if applied_fix is not None:
        summary["applied_fix"] = applied_fix
    return summary


def fix_effect(cr: CompareResult, fix: Policy) -> dict:
    """Engine numbers for a fix applied on top of the compared scenario: kpis after the fix, the drops (in
    percentage points) versus the scenario, and how many people are better off than under the scenario."""
    pop = world.population()
    outs = run(fix, pop)
    k, _ = summarize(outs, pop)
    sk = cr.scenario.kpis
    better = sum(STATUS_RANK[f["status"]] < STATUS_RANK[s.status] for f, s in zip(outs, cr.scenario.outcomes))
    keys = ("pct_served", "pct_hardship", "pct_left_out") + (("avg_extra_jd_month",) if "avg_extra_jd_month" in k else ())
    return {"kpis": {x: k[x] for x in keys},
            "left_out_drop": round(sk["pct_left_out"] - k["pct_left_out"], 1),
            "hardship_drop": round(sk["pct_hardship"] - k["pct_hardship"], 1),
            "people_better_off": better}


def write_report(cr: CompareResult, sens: SensitivityResult | None, applied_fix: dict | None = None,
                 started_at: float | None = None) -> ReportResponse:
    summary = report_summary(cr, sens, applied_fix)
    fb_ar, fb_en = fallbacks.report(summary)

    def check(raw: str, final: bool):
        d = _loads(raw)
        ar, en = _str_or_none(d, "summary_ar") or "", _str_or_none(d, "summary_en") or ""
        if not checks.has_arabic(ar) or not en.strip():
            raise Rejected("need summary_ar (Arabic) and summary_en")
        bad = checks.ungrounded(ar + " " + en, summary, also=[SENSITIVITY_PCT])
        if bad:
            raise Rejected(f"numbers not in the input: {bad}")
        return {"summary_ar": ar, "summary_en": en}

    a = _ai("report", summary, prompts.system("report", summary.get("service", "id_renewal")),
            json.dumps(summary, ensure_ascii=False), check, smart=True, want_json=True, budget=_left(started_at))
    if a.out is None:
        return ReportResponse(summary_ar=fb_ar, summary_en=fb_en, source="fallback")
    return ReportResponse(**a.out, source="ai")


# ---------------------------------------------------------------------- fixes

def _improved_groups(fix_groups: dict, scen_groups: dict) -> list[str]:
    gain = {g: (scen_groups[g]["left_out"] + scen_groups[g]["hardship"]) - (fix_groups[g]["left_out"] + fix_groups[g]["hardship"])
            for g in world.EQUITY_GROUPS}
    return [g for g, v in sorted(gain.items(), key=lambda kv: (-kv[1], kv[0])) if v > 0][:3]


def _fixes_context(scenario: Policy) -> dict:
    """Engine work for /fixes: the scenario's numbers, the ranked grid, its top 3 and the AI inputs (= cache key).
    The inputs must stay exactly as they are, or the warmed demo answer stops hitting."""
    pop = world.population()
    scen_out = run(scenario, pop)
    sk, sg = summarize(scen_out, pop)
    grid = fixgrid.build(scenario, pop)
    top = grid[:3]
    for c in top:
        c["improved_groups"] = _improved_groups(c["groups"], sg)
    inputs = {
        "scenario_policy": policy_json(scenario),
        "scenario_by_group": {g: {"hardship": sg[g]["hardship"], "left_out": sg[g]["left_out"]} for g in world.EQUITY_GROUPS},
        "scenario_kpis": {k: sk[k] for k in ["pct_served", "pct_hardship", "pct_left_out"]},
        "left_out_by_area": dict(sorted(Counter(c["area"] for c, o in zip(pop, scen_out)
                                                if o["status"] == "left_out").items())),
        "not_served_by_area": dict(sorted(Counter(c["area"] for c, o in zip(pop, scen_out)
                                                  if o["status"] != "served").items())),
        "reasons_not_served": dict(Counter(r for o in scen_out if o["status"] != "served" for r in o["reasons"]).most_common(6)),
        "engine_fixes": [{"id": c["id"], "title_ar": c["title_ar"], "title_en": c["title_en"],
                          "left_out_drop": c["left_out_drop"], "hardship_drop": c["hardship_drop"],
                          "improved_groups": c["improved_groups"]} for c in top],
    }
    if scenario.service == TRAVEL:
        # everyday_travel only (new keys; the id_renewal inputs above are untouched): who is squeezed or priced out
        # by travel mode and trip purpose, the average extra cost, and the proposal's spending limits.
        inputs["service"] = TRAVEL
        inputs["scenario_kpis"]["avg_extra_jd_month"] = sk.get("avg_extra_jd_month")
        inputs["scenario_by_mode"] = sk.get("by_mode")
        inputs["scenario_by_purpose"] = sk.get("by_purpose")
        inputs["proposal_limits"] = travel_proposal_limits()
    return {"sk": sk, "sg": sg, "grid": grid, "top": top, "ids": [c["id"] for c in top], "inputs": inputs}


def travel_proposal_limits() -> dict:
    """An AI travel fix may not spend more per person than the grid's largest cash support / voucher: it has to win
    by targeting, not by paying more."""
    cash, vouchers = getattr(fixgrid, "CASH_GRID", None) or [("", 20.0)], getattr(fixgrid, "VOUCHER_GRID", None) or [("", 0.5)]
    return {"max_cash_jd_month": max(a for _g, a in cash), "max_voucher_jd": max(a for _g, a in vouchers)}


def _travel_proposal_problems(scenario: Policy, pol: Policy, limits: dict) -> list[str]:
    """everyday_travel: the proposal may only use cash support, the bus/taxi fare settings and transport vouchers,
    never the fuel price, and stays within the grid's amounts."""
    probs = []
    if pol.service != scenario.service:
        probs.append(f'keep "service": "{scenario.service}"')
    if pol.fuel_price_change_pct != scenario.fuel_price_change_pct:
        probs.append("the fuel price (fuel_price_change_pct) is the decision being tested: keep it as in the scenario")
    other = [f for f in _fields_changed(scenario, pol, ID_RENEWAL_FIELDS + TRAVEL_FIELDS + ("transport_vouchers",))
             if f not in TRAVEL_PROPOSAL_FIELDS and f != "fuel_price_change_pct"]
    if other:
        probs.append(f"only cash_support, bus_fare_change_pct, taxi_fare_change_pct and transport_vouchers may change, "
                     f"not {', '.join(other)}")
    for name in ("bus_fare_change_pct", "taxi_fare_change_pct"):
        v = getattr(pol, name)
        if v is not None and v != getattr(scenario, name) and v < 0:
            probs.append(f"{name}: a freeze (0) or a rise, no fare cuts")
    old_cash = {(tuple(sorted(set(c.groups))), c.amount_jd_month) for c in scenario.cash_support}
    if any(c.amount_jd_month > limits["max_cash_jd_month"] for c in pol.cash_support
           if (tuple(sorted(set(c.groups))), c.amount_jd_month) not in old_cash):
        probs.append(f"cash support above {limits['max_cash_jd_month']:g} JD a month (proposal_limits)")
    old_v = {(tuple(sorted(set(v.groups))), v.amount_jd) for v in scenario.transport_vouchers}
    if any(v.amount_jd > limits["max_voucher_jd"] for v in pol.transport_vouchers
           if (tuple(sorted(set(v.groups))), v.amount_jd) not in old_v):
        probs.append(f"a transport voucher above {limits['max_voucher_jd']:g} JD per round trip (proposal_limits)")
    return probs


def _protections_changed(scenario: Policy, pol: Policy) -> list[str]:
    a, b = json.loads(canonical(scenario)), json.loads(canonical(pol))
    return [f for f in PROTECTION_FIELDS if a[f] != b[f]]


def _check_fixes(raw: str, final: bool, scenario: Policy, inputs: dict, ids: list[str]) -> dict:
    d = _loads(raw)
    exp_list = d.get("explanations") or []
    if not isinstance(exp_list, list):
        raise Rejected("explanations must be a list")
    exps = {e.get("id"): e for e in exp_list if isinstance(e, dict)}
    if set(ids) - set(exps):
        raise Rejected(f"need an explanation for each fix id: {ids}")
    # Each explanation is grounded against ITS OWN fix (drops, groups, title hours) and the scenario's numbers,
    # so it can't borrow another fix's numbers.
    own = {f["id"]: f for f in inputs["engine_fixes"]}
    shared = {"scenario_kpis": inputs["scenario_kpis"], "scenario_by_group": inputs["scenario_by_group"]}
    clean = []
    for i in ids:
        ar, en = _str_or_none(exps[i], "explanation_ar") or "", _str_or_none(exps[i], "explanation_en") or ""
        if not checks.has_arabic(ar) or not en.strip():
            raise Rejected(f"explanation for {i} needs Arabic and English text")
        bad = checks.ungrounded(ar + " " + en, [own[i], shared])
        if bad:
            raise Rejected(f"explanation for {i} has numbers that are not this fix's: {bad}")
        clean.append({"id": i, "explanation_ar": ar, "explanation_en": en})
    prop, perr = d.get("proposal"), None
    if isinstance(prop, dict):
        try:
            pol = Policy.model_validate(prop.get("policy"))
            errs = policy_errors(pol)
            if errs:
                raise Rejected("; ".join(errs))
            n = count_changes(scenario, pol)
            if n > MAX_AI_CHANGES:
                raise Rejected(f"proposal makes {n} changes; at most {MAX_AI_CHANGES} are allowed "
                               "(each van, each new opening day group, each toggle counts as one)")
            if scenario.service == TRAVEL:
                probs = _travel_proposal_problems(scenario, pol, inputs["proposal_limits"])
                if probs:
                    raise Rejected("; ".join(probs))
            else:
                used = _protections_changed(scenario, pol)
                if used:
                    raise Rejected(f"proposal must not change the group protections ({', '.join(used)}): use offices, "
                                   "hours, days, mobile units, wheelchair access, appointments or online settings")
                travel = _fields_changed(scenario, pol, TRAVEL_FIELDS) + (
                    ["service"] if pol.service != scenario.service else [])
                if travel:
                    raise Rejected(f"proposal must not change {', '.join(travel)}: this is the id_renewal service")
            t_ar, t_en = _str_or_none(prop, "title_ar"), _str_or_none(prop, "title_en")
            r_ar, r_en = _str_or_none(prop, "rationale_ar"), _str_or_none(prop, "rationale_en")
            if not t_ar or not t_en:
                raise Rejected("proposal needs title_ar and title_en")
            if checks.numbers_in((r_ar or "") + " " + (r_en or "")):
                raise Rejected("rationale must not contain numbers")
            pol_json = pol.model_dump(mode="json")
            bad = checks.ungrounded(t_ar + " " + t_en, pol_json)
            if bad:
                raise Rejected(f"proposal title has numbers that are not in its policy: {bad}")
            # The shape it will be shown in, so a bad field is a rejection now and not a 500 later.
            FixCandidate.model_validate({"id": "ai:check", "title_ar": t_ar, "title_en": t_en, "policy": pol_json,
                                         "source": "ai_proposed", "left_out_drop": 0.0, "hardship_drop": 0.0,
                                         "worsens_any_group": False, "n_changes": n,
                                         "explanation_ar": r_ar, "explanation_en": r_en})
            prop = {"title_ar": t_ar, "title_en": t_en, "rationale_ar": r_ar, "rationale_en": r_en, "policy": pol_json}
        except (Rejected, ValidationError) as e:
            perr = f"proposal policy invalid: {str(e)[:300]}"
    else:
        perr = "missing proposal"
    if perr and not final:
        raise Rejected(perr)  # retry once; on the final attempt keep the explanations and drop the proposal
    return {"explanations": clean, "proposal": None if perr else prop, "proposal_error": perr}


def explain_and_propose_fixes(baseline: Policy, scenario: Policy, hint: str | None = None,
                              use_cache: bool = True, started_at: float | None = None) -> FixesResponse:
    """baseline is not used (fixes are scored against the scenario); it is kept so the route and scripts
    pass the same pair as /compare. hint/use_cache are only for scripts/find_ai_fix.py (prompt variations
    for the demo path). started_at (time.monotonic() at request start) makes the engine work count against
    the request's AI budget."""
    ctx = _fixes_context(scenario)
    top, ids, inputs = ctx["top"], ctx["ids"], ctx["inputs"]
    if not top:
        return FixesResponse(fixes=[], source="fallback", ai_proposal={"status": "no_grid_fixes"})
    service = scenario.service
    extra = {"groups": list(world.ALL_GROUPS)} if service == TRAVEL else _sites_areas()
    user = json.dumps({**inputs, **extra}, ensure_ascii=False)
    if hint:
        user += f"\n\nIdea to consider for your proposal: {hint}"

    # An answer whose proposal was invalid or missing is not cached, so the next request tries again.
    keep = lambda out: out.get("proposal") is not None or config.DEMO_OFFLINE  # noqa: E731
    a = _ai("fixes", inputs, prompts.system("fixes", service), user,
            lambda raw, final: _check_fixes(raw, final, scenario, inputs, ids),
            smart=True, want_json=True, use_cache=use_cache, budget=_left(started_at), keep=keep)
    out = a.out

    fixes = []
    exp_by_id = {e["id"]: e for e in (out or {}).get("explanations", [])}
    for c in top:
        fc = fixgrid.to_candidate(c)
        if c["id"] in exp_by_id:
            fc.explanation_ar, fc.explanation_en = exp_by_id[c["id"]]["explanation_ar"], exp_by_id[c["id"]]["explanation_en"]
        else:
            fc.explanation_ar, fc.explanation_en = fallbacks.fix_explanation(c, c["improved_groups"], service)
        fixes.append(fc)

    prop = (out or {}).get("proposal")
    if out is None:
        ai_note = {"status": "ai_unavailable"}
    elif prop is None:
        ai_note = {"status": "invalid", "error": out.get("proposal_error")}
    else:
        ai_note, ai_fix = _verify_proposal(prop, scenario, ctx["grid"], ctx["sk"], ctx["sg"])
        if ai_fix is not None:
            fixes.append(ai_fix)
    if not use_cache and out is not None and ai_note.get("status") == "shown":
        cache.put("fixes", inputs, out, {**a.meta, "hint": hint})  # keep the verified winner for the demo
    return FixesResponse(fixes=fixes, source="ai" if exp_by_id else "fallback", ai_proposal=ai_note)


def _verify_proposal(prop: dict, scenario: Policy, grid: list[dict], sk: dict, sg: dict
                     ) -> tuple[dict, FixCandidate | None]:
    """The engine decides whether the AI's idea is shown (CLAUDE.md §8.7). Returns (note, candidate or None)."""
    try:
        pol = Policy.model_validate(prop["policy"])
    except (ValidationError, KeyError, TypeError) as e:
        return {"status": "invalid", "error": f"proposal policy invalid: {str(e)[:300]}"}, None
    errs = policy_errors(pol)
    if errs:  # never score a policy the engine can't run (e.g. a stale cached site id)
        return {"status": "invalid", "error": "; ".join(errs)[:300]}, None
    canon = canonical(pol)
    if canon == canonical(scenario):
        return {"status": "hidden_no_change"}, None
    if canon in {canonical(p) for p in fixgrid.all_policies(scenario)}:
        return {"status": "hidden_duplicate_of_grid", "title_en": prop["title_en"]}, None
    s = fixgrid.score(pol, sk, sg)
    best = grid[0]
    numbers = {"left_out_drop": s["left_out_drop"], "hardship_drop": s["hardship_drop"],
               "best_grid_left_out_drop": best["left_out_drop"], "best_grid_hardship_drop": best["hardship_drop"]}
    if s["worsens_any_group"]:
        return {"status": "hidden_worsens_a_group", "title_en": prop["title_en"], **numbers}, None
    if (s["left_out_drop"], s["hardship_drop"]) <= (best["left_out_drop"], best["hardship_drop"]):
        return {"status": "hidden_not_better", "title_en": prop["title_en"], **numbers}, None
    groups = _improved_groups(s["groups"], sg)
    fb_ar, fb_en = fallbacks.fix_explanation(
        {"title_ar": prop["title_ar"], "title_en": prop["title_en"], **numbers}, groups, scenario.service)
    fc = FixCandidate(
        id="ai:" + hashlib.sha256(canon.encode()).hexdigest()[:8], title_ar=prop["title_ar"], title_en=prop["title_en"],
        policy=pol, source="ai_proposed", left_out_drop=s["left_out_drop"], hardship_drop=s["hardship_drop"],
        worsens_any_group=False, n_changes=count_changes(scenario, pol), kpis=s["kpis"],
        explanation_ar=f"{prop.get('rationale_ar') or ''} — {fb_ar}".strip(" —"),
        explanation_en=f"{prop.get('rationale_en') or ''} — {fb_en}".strip(" —"))
    return {"status": "shown", "title_en": prop["title_en"], **numbers}, fc


def cached_ai_fix_policy(baseline: Policy, scenario: Policy) -> Policy | None:
    """The verified AI-proposed fix for this scenario, read from the AI cache ONLY (never calls a provider).
    Builds the /fixes inputs exactly as explain_and_propose_fixes does, re-checks the cached answer, and runs the
    engine's verification. Returns the fix policy if it would be shown, else None. Used by warm-up and warm_cache."""
    ctx = _fixes_context(scenario)
    if not ctx["top"]:
        return None
    hit = cache.get("fixes", ctx["inputs"])
    if hit is None:
        return None
    try:
        out = _check_fixes(json.dumps(hit, ensure_ascii=False), True, scenario, ctx["inputs"], ctx["ids"])
    except _CHECK_ERRORS as e:
        log.warning("cached fixes answer fails today's checks: %s", str(e)[:300])
        return None
    if not out.get("proposal"):
        return None
    _note, fc = _verify_proposal(out["proposal"], scenario, ctx["grid"], ctx["sk"], ctx["sg"])
    return fc.policy if fc is not None else None
