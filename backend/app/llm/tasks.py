"""The four AI jobs (CLAUDE.md §2): parse, voice, report, explain + propose fixes.

Every task: cache first -> (live only) AI call -> validate (Pydantic / grounding) ->
retry once with the error -> else the deterministic fallback. Never a blank.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections import Counter
from typing import Callable

from pydantic import ValidationError

from .. import config
from ..models import (CompareResult, FixCandidate, FixesResponse, ParseResult, Policy, ReportResponse,
                      SensitivityResult, VoiceResponse)
from ..sim import fixgrid, world
from ..sim.engine import run, summarize
from ..sim.validate import canonical, count_changes, policy_errors
from . import cache, checks, fallbacks, prompts
from .client import LLMUnavailable, complete, last_meta

log = logging.getLogger("nas.llm")


MAX_AI_CHANGES = 3  # keep the AI's idea comparable with grid pairs


class Rejected(ValueError):
    pass


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


def _ai(task: str, inputs, system: str, user: str, check: Callable[[str, bool], object], *,
        smart: bool, want_json: bool, use_cache: bool = True):
    """Cached, validated AI call. Returns the checked output, or None (caller uses the fallback)."""
    hit = cache.get(task, inputs) if use_cache else None
    if hit is not None:
        return hit
    if config.DEMO_OFFLINE:
        return None
    msg = user
    deadline = time.monotonic() + config.LLM_TOTAL_BUDGET_S  # both attempts share one request's budget
    for attempt in range(2):
        left = deadline - time.monotonic()
        if attempt and left < 3.0:
            break  # no time for a retry; the caller uses the template
        try:
            raw = complete(task, system, msg, json_schema={} if want_json else None, smart=smart, budget_s=left)
        except LLMUnavailable as e:
            log.warning("%s: AI unavailable, using fallback (%s)", task, e)
            return None
        try:
            out = check(raw, attempt == 1)
        except (Rejected, ValidationError, KeyError, TypeError) as e:
            log.warning("%s: rejected AI output (attempt %d): %s", task, attempt + 1, str(e)[:300])
            msg = f"{user}\n\nYour previous answer was rejected: {str(e)[:500]}\nFix it and answer again."
            continue
        if use_cache:
            cache.put(task, inputs, out, dict(last_meta))
        return out
    return None


def _sites_areas() -> dict:
    return {"sites": [{"id": s["id"], "area": s["area"], "name_en": s["name_en"], "name_ar": s["name_ar"],
                       "real_cspd_office": s.get("real", False)}
                      for s in world.sites().values()],
            "areas": [{"id": a["id"], "name_en": a["name_en"], "name_ar": a["name_ar"], "side": a["side"]}
                      for a in world.areas().values()],
            "roads": [{"id": r["id"], "name_en": r["name_en"], "name_ar": r["name_ar"]} for r in world.roads().values()]}


# Policy fields added after the AI cache was warmed, with their defaults.
_LATER_FIELDS = {"closed_roads": [], "appointment_exempt_groups": [], "fee_discounts": {}, "home_visits": None,
                 "transport_vouchers": [], "hybrid_pickup": False}


def policy_json(p: Policy) -> dict:
    """A policy as JSON for cache keys. Fields added later are left out while at their default, so keys made
    before they existed (the warmed demo cache) still match."""
    d = p.model_dump(mode="json")
    for k, default in _LATER_FIELDS.items():
        if k in d and d[k] == default:
            d.pop(k)
    return d


# ---------------------------------------------------------------------- parse

_ROAD_WORDS = re.compile(r"^(شارع|طريق)\s+|\s+(street|st|road|rd)$")


def roads_named_in(text: str) -> list[str]:
    """Catalogue roads whose name (Arabic, English or OSM, without "Street"/"شارع") appears in the text.
    A deterministic hint for the parser; the AI still decides what the official meant."""
    t = " " + re.sub(r"[^\w\s]", " ", cache.normalize_text(text)) + " "
    t = re.sub(r"\s+", " ", t)
    out = []
    for r in world.roads().values():
        names = [r["name_en"], r["name_ar"], *r.get("osm_names", [])]
        names += re.findall(r"\(([^)]+)\)", r["name_en"] + r["name_ar"])  # "... (Gardens)" -> Gardens, الجاردنز
        for n in names:
            n = re.sub(r"\s*\([^)]*\)", "", n)
            n = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", cache.normalize_text(n))).strip()
            n = _ROAD_WORDS.sub("", n).strip()
            if len(n) >= 4 and f" {n} " in t:
                out.append(r["id"])
                break
    return out


def parse_policy(text: str, current: Policy, lang: str = "ar") -> ParseResult:
    cur = policy_json(current)
    inputs = {"text": cache.normalize_text(text), "current_policy": cur}
    hint = {"roads_named_in_text": roads_named_in(text)} if world.roads() else {}
    user = json.dumps({"current_policy": cur, **_sites_areas(), **hint, "official_text": text}, ensure_ascii=False)

    def check(raw: str, final: bool):
        d = _loads(raw)
        status = d.get("status")
        if status == "ok":
            pol = Policy.model_validate(d.get("policy"))
            errs = policy_errors(pol)
            if errs:
                raise Rejected("; ".join(errs))
            if not d.get("changes_ar") or not d.get("changes_en"):
                raise Rejected("changes_ar and changes_en must list the changes")
            bad = checks.ungrounded(" ".join(d["changes_ar"] + d["changes_en"]), [cur, pol.model_dump(mode="json"), text])
            if bad:
                raise Rejected(f"change list mentions numbers not in the policy: {bad}")
            return {"status": "ok", "policy": pol.model_dump(mode="json"), "changes_ar": d["changes_ar"],
                    "changes_en": d["changes_en"], "message_ar": None, "message_en": None}
        if status == "unsupported":
            if not d.get("message_ar") or not d.get("message_en"):
                raise Rejected("unsupported answers need message_ar and message_en")
            return {"status": "unsupported", "policy": None, "changes_ar": [], "changes_en": [],
                    "message_ar": d["message_ar"], "message_en": d["message_en"]}
        raise Rejected("status must be 'ok' or 'unsupported'")

    out = _ai("parse", inputs, prompts.PARSE_SYSTEM, user, check, smart=True, want_json=True)
    if out is None:
        return fallbacks.parse_failed()
    return ParseResult(**out, source="ai")


# ---------------------------------------------------------------------- voice

def voice_facts(citizen: dict, o: dict) -> dict:
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
    road = world.roads().get(o.get("detour_road") or "")
    if road and round(o.get("detour_minutes", 0)) >= 1:  # only when a closed road really lengthened the trip
        facts["outcome"]["closed_road_ar"] = road["name_ar"]
        facts["outcome"]["detour_minutes_one_way"] = round(o["detour_minutes"])
    return facts


def voice_citizen(citizen: dict, outcome: dict) -> VoiceResponse:
    facts = voice_facts(citizen, outcome)
    fb_ar, fb_en = fallbacks.voice(citizen, outcome)
    user = json.dumps(facts, ensure_ascii=False)

    def check(raw: str, final: bool):
        t = (raw or "").strip().strip('"“”«»').strip()
        if not checks.has_arabic(t) or len(t) > 450:
            raise Rejected("must be 1-3 short Arabic sentences")
        bad = checks.ungrounded(t, facts)
        if bad:
            raise Rejected(f"numbers not in the facts: {bad}")
        helper = fallbacks.msa_helper(citizen["helper_relation_ar"])
        extra = checks.foreign_people(t, helper)
        if extra:
            raise Rejected(f"mentions people other than the helper: {extra}")
        style = checks.voice_style_problems(t, helper)
        if style:
            raise Rejected("; ".join(style))
        return t

    out = _ai("voice", facts, prompts.VOICE_SYSTEM, user, check, smart=False, want_json=False)
    if out is None:
        return VoiceResponse(text_ar=fb_ar, summary_en=fb_en, source="fallback")
    return VoiceResponse(text_ar=out, summary_en=fb_en, source="ai")


# --------------------------------------------------------------------- report

def report_summary(cr: CompareResult, sens: SensitivityResult | None) -> dict:
    keys = ["pct_served", "pct_hardship", "pct_left_out", "avg_hours_lost", "avg_cost_jd"]
    bg, sg = cr.baseline.by_group, cr.scenario.by_group
    reasons = Counter(r for o in cr.scenario.outcomes if o.status != "served" for r in o.reasons)
    return {
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


def write_report(cr: CompareResult, sens: SensitivityResult | None) -> ReportResponse:
    summary = report_summary(cr, sens)
    fb_ar, fb_en = fallbacks.report(summary)

    def check(raw: str, final: bool):
        d = _loads(raw)
        ar, en = d.get("summary_ar") or "", d.get("summary_en") or ""
        if not checks.has_arabic(ar) or not en:
            raise Rejected("need summary_ar (Arabic) and summary_en")
        bad = checks.ungrounded(ar + " " + en, summary)
        if bad:
            raise Rejected(f"numbers not in the input: {bad}")
        return {"summary_ar": ar, "summary_en": en}

    out = _ai("report", summary, prompts.REPORT_SYSTEM, json.dumps(summary, ensure_ascii=False), check,
              smart=True, want_json=True)
    if out is None:
        return ReportResponse(summary_ar=fb_ar, summary_en=fb_en, source="fallback")
    return ReportResponse(**out, source="ai")


# ---------------------------------------------------------------------- fixes

def _improved_groups(fix_groups: dict, scen_groups: dict) -> list[str]:
    gain = {g: (scen_groups[g]["left_out"] + scen_groups[g]["hardship"]) - (fix_groups[g]["left_out"] + fix_groups[g]["hardship"])
            for g in world.EQUITY_GROUPS}
    return [g for g, v in sorted(gain.items(), key=lambda kv: (-kv[1], kv[0])) if v > 0][:3]


def explain_and_propose_fixes(baseline: Policy, scenario: Policy, hint: str | None = None,
                              use_cache: bool = True) -> FixesResponse:
    """hint/use_cache are only for scripts/find_ai_fix.py (prompt variations for the demo path)."""
    pop = world.population()
    scen_out = run(scenario, pop)
    sk, sg = summarize(scen_out, pop)
    grid = fixgrid.build(scenario, pop)
    top = grid[:3]
    if not top:
        return FixesResponse(fixes=[], source="fallback", ai_proposal={"status": "no_grid_fixes"})
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
    ids = [c["id"] for c in top]
    user = json.dumps({**inputs, **_sites_areas()}, ensure_ascii=False)
    if hint:
        user += f"\n\nIdea to consider for your proposal: {hint}"

    def check(raw: str, final: bool):
        d = _loads(raw)
        exps = {e.get("id"): e for e in d.get("explanations") or [] if isinstance(e, dict)}
        if set(ids) - set(exps):
            raise Rejected(f"need an explanation for each fix id: {ids}")
        clean = []
        for i in ids:
            ar, en = exps[i].get("explanation_ar") or "", exps[i].get("explanation_en") or ""
            if not checks.has_arabic(ar) or not en:
                raise Rejected(f"explanation for {i} needs Arabic and English text")
            bad = checks.ungrounded(ar + " " + en, inputs)
            if bad:
                raise Rejected(f"explanation for {i} has numbers not in the input: {bad}")
            clean.append({"id": i, "explanation_ar": ar, "explanation_en": en})
        prop, perr = d.get("proposal"), None
        if isinstance(prop, dict):
            try:
                pol = Policy.model_validate(prop.get("policy"))
                errs = policy_errors(pol)
                if errs:
                    raise Rejected("; ".join(errs))
                if sorted(set(pol.closed_roads)) != sorted(set(scenario.closed_roads)):
                    raise Rejected("keep closed_roads exactly as in the scenario: road works are not the service's "
                                   f"decision; closed_roads must be {sorted(set(scenario.closed_roads))}")
                n = count_changes(scenario, pol)
                if n > MAX_AI_CHANGES:
                    raise Rejected(f"proposal makes {n} changes; at most {MAX_AI_CHANGES} are allowed "
                                   "(each van, each new opening day group, each toggle counts as one)")
                if checks.numbers_in((prop.get("rationale_ar") or "") + (prop.get("rationale_en") or "")):
                    raise Rejected("rationale must not contain numbers")
                if not prop.get("title_ar") or not prop.get("title_en"):
                    raise Rejected("proposal needs title_ar and title_en")
                prop = {k: prop.get(k) for k in ["title_ar", "title_en", "rationale_ar", "rationale_en"]}
                prop["policy"] = pol.model_dump(mode="json")
            except (Rejected, ValidationError) as e:
                perr = f"proposal policy invalid: {str(e)[:300]}"
        else:
            perr = "missing proposal"
        if perr and not final:
            raise Rejected(perr)  # retry once; on the final attempt keep the explanations and drop the proposal
        return {"explanations": clean, "proposal": None if perr else prop, "proposal_error": perr}

    out = _ai("fixes", inputs, prompts.FIXES_SYSTEM, user, check, smart=True, want_json=True, use_cache=use_cache)

    fixes = []
    exp_by_id = {e["id"]: e for e in (out or {}).get("explanations", [])}
    for c in top:
        fc = fixgrid.to_candidate(c)
        if c["id"] in exp_by_id:
            fc.explanation_ar, fc.explanation_en = exp_by_id[c["id"]]["explanation_ar"], exp_by_id[c["id"]]["explanation_en"]
        else:
            fc.explanation_ar, fc.explanation_en = fallbacks.fix_explanation(c, c["improved_groups"])
        fixes.append(fc)

    ai_note = {"status": "none"}
    prop = (out or {}).get("proposal")
    if out is None:
        ai_note = {"status": "ai_unavailable"}
    elif prop is None:
        ai_note = {"status": "invalid", "error": out.get("proposal_error")}
    else:
        ai_note = _verify_proposal(prop, scenario, grid, sk, sg, fixes)
    if not use_cache and out is not None and ai_note.get("status") == "shown":
        cache.put("fixes", inputs, out, {**last_meta, "hint": hint})  # keep the verified winner for the demo
    return FixesResponse(fixes=fixes, source="ai" if exp_by_id else "fallback", ai_proposal=ai_note)


def _verify_proposal(prop: dict, scenario: Policy, grid: list[dict], sk: dict, sg: dict,
                     fixes: list[FixCandidate]) -> dict:
    """The engine decides whether the AI's idea is shown (CLAUDE.md §8.7)."""
    pol = Policy.model_validate(prop["policy"])
    canon = canonical(pol)
    if canon == canonical(scenario):
        return {"status": "hidden_no_change"}
    if canon in {canonical(p) for p in fixgrid.all_policies(scenario)}:
        return {"status": "hidden_duplicate_of_grid", "title_en": prop["title_en"]}
    s = fixgrid.score(pol, sk, sg)
    best = grid[0]
    numbers = {"left_out_drop": s["left_out_drop"], "hardship_drop": s["hardship_drop"],
               "best_grid_left_out_drop": best["left_out_drop"], "best_grid_hardship_drop": best["hardship_drop"]}
    if s["worsens_any_group"]:
        return {"status": "hidden_worsens_a_group", "title_en": prop["title_en"], **numbers}
    if (s["left_out_drop"], s["hardship_drop"]) <= (best["left_out_drop"], best["hardship_drop"]):
        return {"status": "hidden_not_better", "title_en": prop["title_en"], **numbers}
    groups = _improved_groups(s["groups"], sg)
    fb_ar, fb_en = fallbacks.fix_explanation(
        {"title_ar": prop["title_ar"], "title_en": prop["title_en"], **numbers}, groups)
    fc = FixCandidate(
        id="ai:" + hashlib.sha256(canon.encode()).hexdigest()[:8], title_ar=prop["title_ar"], title_en=prop["title_en"],
        policy=pol, source="ai_proposed", left_out_drop=s["left_out_drop"], hardship_drop=s["hardship_drop"],
        worsens_any_group=False,
        explanation_ar=f"{prop.get('rationale_ar') or ''} — {fb_ar}".strip(" —"),
        explanation_en=f"{prop.get('rationale_en') or ''} — {fb_en}".strip(" —"))
    fixes.append(fc)
    return {"status": "shown", "title_en": prop["title_en"], **numbers}
