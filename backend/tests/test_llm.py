from app.llm import cache, checks, fallbacks, tasks
from app.sim import engine, world


def test_grounding_handles_arabic_digits_and_times():
    inputs = {"travel_minutes": 45.3, "cost_jd": 3.8, "close": "13:00"}
    assert checks.ungrounded("الطريق ٤٥ دقيقة وكلفتني 3.8 دينار، بسكر الساعة 1", inputs) == []
    assert checks.ungrounded("الطريق 90 دقيقة", inputs) == [90.0]


def test_foreign_people_check():
    assert checks.foreign_people("ابني وصلني", "ابني") == []
    assert checks.foreign_people("جاري وصلني", "ابني") == ["جاري"]


def test_cache_key_normalises_text():
    a = cache.key("parse", {"text": cache.normalize_text("  أغلق   المكتب يوم الخميس ")})
    b = cache.key("parse", {"text": cache.normalize_text("اغلق المكتب يوم الخميس")})
    assert a == b


def test_every_reason_has_voice_text():
    from typing import get_args
    from app.models import ReasonCode
    assert set(fallbacks.REASON_VOICE) == set(get_args(ReasonCode))


def test_offline_tasks_fall_back_never_blank():
    pop = world.population()
    outs = engine.run(world.scenario_policy(world.demo_scenario_id()))
    for st in ["served", "hardship", "left_out"]:
        i = next(k for k, o in enumerate(outs) if o["status"] == st)
        v = tasks.voice_citizen(pop[i], outs[i])
        assert v.text_ar and v.summary_en and v.source in ("fallback", "ai")
        assert checks.has_arabic(v.text_ar)
    p = tasks.parse_policy("some text that is definitely not cached 12345", world.scenario_policy("baseline"))
    assert p.status == "unsupported" and p.source == "fallback"


def test_rate_limits_put_models_on_cooldown():
    import time
    from app.llm import client
    daily = client._classify(Exception("429 RESOURCE_EXHAUSTED quota exceeded, check your plan and billing details. "
                                       "quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier"))
    minute = client._classify(Exception("Error code: 429 - Rate limit reached on tokens per minute (TPM)"))
    busy = client._classify(Exception("503 UNAVAILABLE high demand"))
    assert daily[1] == "daily limit" and daily[0] > time.time() + 60
    assert minute[1] == "rate limit" and busy[1] == "overloaded"
    assert client._classify(ValueError("bad json")) is None
    no_credit = client._classify(Exception("429 insufficient_quota: You have no credits remaining"))
    assert no_credit[1] == "no credits" and no_credit[0] > time.time() + 60


def test_voice_style_checks():
    assert checks.voice_style_problems("دفعت 4.5 ليرات", "ابني")
    assert checks.voice_style_problems("اضطريت أجيب ابن يساعدني", "ابني")
    assert checks.voice_style_problems("ابني ساعدني ودفعت دينارين", "ابني") == []
    assert checks.voice_style_problems("ابن عمي", None) == []


def test_voice_template_does_not_repeat_the_day_and_counts_nouns():
    c = {"helper_relation_ar": "ابني", "helper_relation_en": "my son"}
    o = {"status": "served", "mode": "taxi", "bus_transfers": 0, "visit_day": "sat", "travel_minutes": 8.0,
         "cost_jd": 3.7, "hours_lost": 1.3, "work_hours_missed": 0.0, "reasons": [],
         "channel_name_ar": "الوحدة المتنقلة في ماركا يوم السبت", "channel_name_en": "Mobile unit in Marka on Saturday"}
    ar, en = fallbacks.voice(c, o)
    assert ar.count("السبت") == 1 and en.count("Saturday") == 1
    assert "8 دقائق" in ar and "1.3 ساعة" in ar


def test_fallback_providers_list_skips_missing_keys(monkeypatch):
    from app import config
    from app.llm import client
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "LLM_FALLBACK_PROVIDER", "groq, openai")
    keys = {"GEMINI_API_KEY": "x", "GROQ_API_KEY": "", "OPENAI_API_KEY": "y"}
    monkeypatch.setattr(config, "env", lambda name, default="": keys.get(name, default))
    assert client._providers() == ["gemini", "openai"]


# ------------------------------------------------------------------ stubbed AI (no network, temp cache)

import json  # noqa: E402

import pytest  # noqa: E402

from app import config  # noqa: E402
from app.llm.client import Completion, LLMUnavailable  # noqa: E402
from app.models import CashSupport, MobileUnit, Policy  # noqa: E402
from app.sim.compare import compare  # noqa: E402

DEMO = "consolidate_digital_first"


@pytest.fixture
def live_ai(monkeypatch, tmp_path):
    """Pretend we are online: `complete` answers from a queue (a dict/str answer, or an exception to raise).
    Cache writes go to a temp dir, never to backend/cache/."""
    monkeypatch.setattr(config, "DEMO_OFFLINE", False)
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    calls = []

    def install(*answers):
        queue = list(answers)

        def fake_complete(task, system, user, json_schema=None, smart=False, budget_s=None):
            calls.append({"task": task, "user": user, "budget_s": budget_s})
            if not queue:
                raise LLMUnavailable("stub: no more answers")
            a = queue.pop(0)
            if isinstance(a, Exception):
                raise a
            return a if isinstance(a, str) else json.dumps(a, ensure_ascii=False)
        monkeypatch.setattr(tasks, "complete", fake_complete)
        return calls
    install.dir = tmp_path
    return install


def _cached_files(tmp_path, task):
    d = tmp_path / task
    return list(d.glob("*.json")) if d.exists() else []


def _parse_ok(policy: Policy, changes_ar, changes_en):
    return {"status": "ok", "policy": policy.model_dump(mode="json"), "changes_ar": changes_ar,
            "changes_en": changes_en, "message_ar": None, "message_en": None}


def test_parse_bad_shape_is_rejected_not_cached(live_ai):
    base = world.scenario_policy("baseline")
    two = base.model_copy(update={"visits_required": 2})
    bad = _parse_ok(two, "زيارتان", ["Two visits"])          # changes_ar as a string (A4)
    live_ai(bad, bad)
    r = tasks.parse_policy("Require two visits (stub 1)", base)
    assert r.source == "fallback" and r.status == "unsupported"
    assert r.message_en.startswith("Couldn't understand")    # the AI answered but was rejected twice
    assert _cached_files(live_ai.dir, "parse") == []


def test_parse_retry_then_ok_is_cached(live_ai):
    base = world.scenario_policy("baseline")
    two = base.model_copy(update={"visits_required": 2})
    calls = live_ai({"status": "ok", "policy": two.model_dump(mode="json"), "changes_ar": [1], "changes_en": ["x"]},
                    _parse_ok(two, ["زيارتان مطلوبتان"], ["Two visits required"]))
    r = tasks.parse_policy("Require two visits (stub 2)", base, lang="en")
    assert r.source == "ai" and r.status == "ok" and r.policy.visits_required == 2
    assert "rejected" in calls[1]["user"] and '"official_ui_language": "en"' in calls[0]["user"]
    assert len(_cached_files(live_ai.dir, "parse")) == 1


def test_parse_rejects_unknown_site_and_bad_hours(live_ai):
    base = world.scenario_policy("baseline")
    d = base.model_dump(mode="json")
    d["offices"][0]["site_id"] = "site_mars"
    e = base.model_dump(mode="json")
    e["offices"][0]["schedule"]["sun"] = ["15:00", "09:00"]
    calls = live_ai({**_parse_ok(base, ["x"], ["x"]), "policy": d}, {**_parse_ok(base, ["x"], ["x"]), "policy": e})
    r = tasks.parse_policy("Move the office to Mars (stub)", base)
    assert r.source == "fallback" and r.message_en.startswith("Couldn't understand")
    assert "site_mars" in calls[1]["user"]


def test_parse_ai_unavailable_says_so(live_ai):
    live_ai(LLMUnavailable("all providers down"))
    r = tasks.parse_policy("Double the fee (stub)", world.scenario_policy("baseline"))
    assert r.source == "fallback" and r.status == "unsupported" and "not available" in r.message_en
    assert "غير متاحة" in r.message_ar


def test_offline_miss_says_ai_unavailable():
    r = tasks.parse_policy("text that is not cached 98765", world.scenario_policy("baseline"))
    assert r.source == "fallback" and "not available" in r.message_en


def test_stale_cached_parse_is_revalidated(monkeypatch, tmp_path):
    """A cached parse naming a site that doesn't exist (any more) must not reach the engine (A35)."""
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    base = world.scenario_policy("baseline")
    d = base.model_dump(mode="json")
    d["offices"][0]["site_id"] = "site_gone"
    text = "stale stub request"
    cache.put("parse", {"text": cache.normalize_text(text), "current_policy": tasks.policy_json(base)},
              {**_parse_ok(base, ["x"], ["x"]), "policy": d})
    r = tasks.parse_policy(text, base)
    assert r.source == "fallback" and r.policy is None


def test_kin_words_with_prefixes():
    assert checks.foreign_people("ذهبت مع وأخي", "ابني") == ["أخي"]
    assert checks.foreign_people("أوصلني ولأمي شكر", None) == ["أمي"]
    assert checks.foreign_people("ذهبت بأختي", "ابني") == ["أختي"]
    assert checks.foreign_people("كأبي تماماً", "ابني") == ["أبي"]
    assert checks.foreign_people("فلأبي الفضل", "ابني") == ["أبي"]
    assert checks.foreign_people("ساعدني عمي وخالتي", "ابني") == ["عمي", "خالتي"]
    assert checks.foreign_people("ساعدني والدي", None) == ["والدي"]
    assert checks.foreign_people("أولادي وأبنائي مشغولون", None) == ["أولادي", "أبنائي"]
    # The helper's own word, with or without a prefix, is allowed; so is a multi-word helper.
    assert checks.foreign_people("ساعدتني أمي، ثم ذهبت مع أمي ولأمي الفضل", "أمي") == []
    assert checks.foreign_people("أوصلني ابن عمي وشكرت لابن عمي", "ابن عمي") == []
    assert checks.foreign_people("ساعدني اخي", "أخي") == []          # hamza variants are the same word


def test_voice_style_skips_two_letter_stems():
    assert checks.voice_style_problems("ساعدتني أمي، أم أنني أخطأت؟", "أمي") == []
    assert checks.voice_style_problems("ساعدني أبي", "أبي") == []
    assert checks.voice_style_problems("ساعدني جار", "جاري")          # 3-letter stems are still checked


def test_report_grounding_allows_the_20_percent_only(live_ai):
    cr = compare(world.scenario_policy("baseline"), world.scenario_policy(DEMO))
    s = cr.scenario.kpis["pct_served"]
    good = {"summary_ar": f"سكان افتراضيون: نسبة الخدمة {s}%، والترتيب ثابت عند ±20%.",
            "summary_en": f"Synthetic population: {s}% served; the ranking holds at ±20%."}
    bad = {"summary_ar": "نسبة الخدمة 37.3%.", "summary_en": "37.3% served."}
    live_ai(bad, good)
    r = tasks.write_report(cr, None)
    assert r.source == "ai" and "±20%" in r.summary_en
    live_ai(bad, bad)
    applied = {"kpis": {"pct_served": 1, "pct_hardship": 2, "pct_left_out": 3}, "left_out_drop": 4,
               "hardship_drop": 5, "people_better_off": 6}
    assert tasks.write_report(cr, None, applied).source == "fallback"


def test_report_summary_unchanged_without_a_fix():
    """The report's cache key must not change when no fix is applied (warmed demo report)."""
    cr = compare(world.scenario_policy("baseline"), world.scenario_policy(DEMO))
    assert "applied_fix" not in tasks.report_summary(cr, None)
    assert cache.key("report", tasks.report_summary(cr, None)) == cache.key("report", tasks.report_summary(cr, None, None))


# ------------------------------------------------------------------ fixes flow (stubbed AI, real engine)

def _fix_ctx():
    scen = world.scenario_policy(DEMO)
    return scen, tasks._fixes_context(scen)


def _explanations(ctx):
    return [{"id": f["id"],
             "explanation_ar": f"يخفض المستبعدين {f['left_out_drop']} نقطة والصعوبة {f['hardship_drop']} نقطة.",
             "explanation_en": f"Left out down {f['left_out_drop']} pts, hardship down {f['hardship_drop']} pts."}
            for f in ctx["inputs"]["engine_fixes"]]


def _vans(scen, *specs):
    p = scen.model_copy(deep=True)
    p.mobile_units += [MobileUnit(area=a, day=d, open="09:00", close="14:00") for a, d in specs]
    return p


def _answer(ctx, pol, title_ar="وحدات متنقلة يوم السبت", title_en="Saturday mobile units"):
    prop = {"title_ar": title_ar, "title_en": title_en, "rationale_ar": "خدمة قريبة يوم العطلة.",
            "rationale_en": "Service close to home on the weekend.", "policy": pol.model_dump(mode="json")}
    return {"explanations": _explanations(ctx), "proposal": prop}


def _fixes(scen):
    return tasks.explain_and_propose_fixes(world.scenario_policy("baseline"), scen)


def _three_vans(scen):
    return _vans(scen, ("sweileh", "sat"), ("wehdat", "sat"), ("downtown", "sat"))


def test_fixes_verified_ai_proposal_is_shown_and_cached(live_ai):
    scen, ctx = _fix_ctx()
    live_ai(_answer(ctx, _three_vans(scen), title_en="Saturday vans 09:00-14:00 in three areas"))
    r = _fixes(scen)
    assert r.source == "ai" and r.ai_proposal["status"] == "shown"
    ai = [f for f in r.fixes if f.source == "ai_proposed"][0]
    assert ai.n_changes == 3 and ai.kpis["pct_left_out"] < ctx["sk"]["pct_left_out"]
    assert len(_cached_files(live_ai.dir, "fixes")) == 1


@pytest.mark.parametrize("make,status", [
    (lambda s: _vans(s, ("sweileh", "sat"), ("downtown", "sat")), "hidden_duplicate_of_grid"),
    (lambda s: s.model_copy(update={"offices": [o for o in s.offices if o.id != "office_jabal_amman"]}),
     "hidden_worsens_a_group"),
    (lambda s: _vans(s, ("khalda", "fri")), "hidden_not_better"),
])
def test_fixes_engine_hides_weak_proposals(live_ai, make, status):
    scen, ctx = _fix_ctx()
    live_ai(_answer(ctx, make(scen)))
    r = _fixes(scen)
    assert r.ai_proposal["status"] == status and all(f.source == "engine_grid" for f in r.fixes)
    assert len(_cached_files(live_ai.dir, "fixes")) == 1   # a valid (if hidden) proposal is cached


@pytest.mark.parametrize("make,why", [
    (lambda s: _vans(s, ("sweileh", "sat"), ("wehdat", "sat"), ("downtown", "sat"), ("marka", "sat")), "4 changes"),
    (lambda s: s.model_copy(update={"fee_discounts": {"elderly": 100.0}}), "uses a group protection"),
    (lambda s: _vans(s, ("atlantis", "sat")), "unknown area"),
])
def test_fixes_invalid_proposal_dropped_after_retry_and_not_cached(live_ai, make, why):
    scen, ctx = _fix_ctx()
    calls = live_ai(_answer(ctx, make(scen)), _answer(ctx, make(scen)))
    r = _fixes(scen)
    assert len(calls) == 2 and "rejected" in calls[1]["user"]
    assert r.source == "ai" and r.ai_proposal["status"] == "invalid", why
    assert all(f.explanation_en.startswith("Left out down") for f in r.fixes)   # explanations kept
    assert _cached_files(live_ai.dir, "fixes") == []                          # next request tries again (C18)


def test_fixes_invalid_then_valid_on_retry(live_ai):
    scen, ctx = _fix_ctx()
    live_ai(_answer(ctx, _vans(scen, ("atlantis", "sat"))), _answer(ctx, _three_vans(scen)))
    assert _fixes(scen).ai_proposal["status"] == "shown"


def test_fixes_title_and_shape_checks(live_ai):
    scen, ctx = _fix_ctx()
    pol = _three_vans(scen)
    live_ai(_answer(ctx, pol, title_en="Saturday vans for 40 percent more people"), _answer(ctx, pol, title_ar=["x"]))
    assert _fixes(scen).ai_proposal["status"] == "invalid"


def test_fix_explanations_are_grounded_in_their_own_numbers(live_ai):
    scen, ctx = _fix_ctx()
    own0 = ctx["inputs"]["engine_fixes"][0]
    shared = {"scenario_kpis": ctx["inputs"]["scenario_kpis"], "scenario_by_group": ctx["inputs"]["scenario_by_group"]}
    other = ctx["inputs"]["engine_fixes"][2]["hardship_drop"]
    assert checks.ungrounded(str(other), [own0, shared]), "the test needs a number that only another fix has"
    ans = _answer(ctx, _three_vans(scen))
    ans["explanations"][0]["explanation_en"] = f"Hardship down {other} pts."
    live_ai(ans, ans)
    r = _fixes(scen)
    assert r.source == "fallback" and r.ai_proposal["status"] == "ai_unavailable"


def test_fixes_budget_counts_from_request_start(live_ai):
    import time
    scen, ctx = _fix_ctx()
    calls = live_ai(_answer(ctx, _three_vans(scen)))
    tasks.explain_and_propose_fixes(world.scenario_policy("baseline"), scen, started_at=time.monotonic() - 10)
    assert calls[0]["budget_s"] <= config.LLM_TOTAL_BUDGET_S - 10 + 0.01


# ------------------------------------------------------------------ client

def test_client_meta_and_timeout_cooldown(monkeypatch):
    from app.llm import client
    monkeypatch.setattr(config, "DEMO_OFFLINE", False)
    monkeypatch.setattr(config, "LLM_TIMEOUT_S", 15.0)
    monkeypatch.setattr(client, "_providers", lambda: ["gemini"])
    monkeypatch.setattr(client, "_chain", lambda p, smart: ["m1"])
    monkeypatch.setattr(client, "_cooldown", {})
    monkeypatch.setattr(client, "_calls", {})
    monkeypatch.setitem(client.ADAPTERS, "gemini", lambda *a: "hello")
    out = client.complete("t", "s", "u")
    assert isinstance(out, Completion) and out == "hello" and out.meta["model"] == "m1"

    def slow(*a):
        raise TimeoutError("timed out")
    monkeypatch.setitem(client.ADAPTERS, "gemini", slow)
    with pytest.raises(LLMUnavailable):
        client.complete("t", "s", "u", budget_s=5.0)      # only a leftover budget: not the model's fault
    assert client._cooldown == {}
    with pytest.raises(LLMUnavailable):
        client.complete("t", "s", "u", budget_s=30.0)     # a full LLM_TIMEOUT_S call timed out: bench it
    assert client._cooldown[("gemini", "m1")][1] == "timeout"


# ------------------------------------------------------------------ fallback grammar

def test_count_ar_forms():
    c = fallbacks.count_ar
    assert c(1, "dinar", "nom") == "دينار واحد" and c(1, "dinar") == "ديناراً واحداً"
    assert c(2, "dinar", "nom") == "ديناران" and c(2, "dinar") == "دينارين" and c(2, "hour", "gen") == "ساعتين"
    assert c(2, "minute", "nom") == "دقيقتان"
    assert c(3, "dinar") == "3 دنانير" and c(10, "point") == "10 نقاط"
    assert c(15, "dinar") == "15 ديناراً" and c(15, "minute") == "15 دقيقة"
    assert c(130, "person") == "130 شخصاً" and c(100, "person") == "100 شخص" and c(103, "person") == "103 أشخاص"
    assert c(2.5, "dinar") == "2.5 دينار" and c(1.3, "hour") == "1.3 ساعة"


def test_voice_template_grammar():
    mom = {"helper_relation_ar": "أمي", "helper_relation_en": "my mother"}
    o = {"status": "hardship", "mode": "online", "reasons": ["NO_SMARTPHONE"], "cost_jd": 2.0}
    ar, en = fallbacks.voice(mom, o)
    assert ar.startswith("أنجزت أمي") and en == "My mother did it online for me because I don't have a smartphone."
    son = {"helper_relation_ar": "ابني", "helper_relation_en": "my son"}
    assert fallbacks.voice(son, o)[0].startswith("أنجز ابني")
    drive = {"status": "hardship", "mode": "helper_car", "channel_name_ar": "مكتب طبربور",
             "channel_name_en": "Tabarbour office", "visit_day": "sat", "travel_minutes": 2, "cost_jd": 1.0,
             "hours_lost": 2.0, "reasons": []}
    ar, _ = fallbacks.voice(mom, drive)
    assert "وأوصلتني أمي" in ar and "دقيقتين" in ar and "ساعتين" in ar and "ديناراً واحداً" in ar
    free = {"status": "served", "mode": "online", "reasons": [], "cost_jd": 0.0}
    ar, en = fallbacks.voice(son, free)
    assert "دون أي رسوم" in ar and "free of charge" in en
    assert "دينارين" in fallbacks.voice(son, {**free, "cost_jd": 2.0})[0]


def test_fix_and_report_templates_handle_signs():
    ar, en = fallbacks.fix_explanation({"title_ar": "ت", "title_en": "T", "left_out_drop": -1.2, "hardship_drop": 2}, [])
    assert "ترتفع نسبة المستبعدين بمقدار 1.2 نقطة" in ar and "تنخفض نسبة من يواجهون صعوبة بمقدار نقطتين" in ar
    assert "rises by 1.2 pts" in en and "-1.2" not in en and "-1.2" not in ar
    k = {"pct_served": 90, "pct_hardship": 10, "pct_left_out": 0, "avg_hours_lost": 1, "avg_cost_jd": 2}
    s = {"baseline_kpis": k, "scenario_kpis": k, "worst_groups": ["elderly", "offline"],
         "group_deltas": {"elderly": 0.0, "offline": -1.0}, "sensitivity": None,
         "applied_fix": {"kpis": {"pct_served": 95, "pct_hardship": 5, "pct_left_out": 0}, "left_out_drop": 0,
                         "hardship_drop": 5, "people_better_off": 130}}
    ar, en = fallbacks.report(s)
    assert "لا تسوء أوضاع أي فئة" in ar and "No group is worse off" in en
    assert "130 شخصاً" in ar and "130 people better off" in en



# ------------------------------------------------------------------ id_renewal cache keys (snapshot)

def test_id_renewal_voice_facts_and_report_summary_unchanged():
    """The everyday_travel work must not touch an id_renewal cache key: the demo hero's voice facts and the demo
    report summary are snapshotted (as warmed in backend/cache/)."""
    pop = world.population()
    i = next(k for k, c in enumerate(pop) if c["id"] == "c_0028")
    demo = world.scenario_policy(DEMO)
    facts = tasks.voice_facts(pop[i], engine.run(demo, pop)[i])
    assert facts == {
        "register": "msa",
        "profile": {"age": 71, "gender": "f", "area_ar": "وسط البلد", "mobility": "none", "has_car": False,
                    "has_smartphone": False, "digital_literacy": "low", "works": False, "work_start": None,
                    "work_end": None, "income_band": "middle", "helper_relation_ar": "ابني"},
        "outcome": {"status": "hardship", "reasons": ["NO_SMARTPHONE", "LOW_DIGITAL_LITERACY"],
                    "channel_name_ar": "أونلاين", "mode": "online", "bus_transfers": 0, "visit_day_ar": None,
                    "travel_minutes_one_way": 0, "total_cost_jd": 2.0, "total_hours_lost_incl_waiting": 0.3,
                    "work_hours_missed": 0.0}}
    assert cache.key("voice", facts) == "9248f3a3f256af0bf91ef98cfd2bb7468a592229202be1899660ea98f117eacc"
    base_out = engine.run(world.scenario_policy("baseline"), pop)[i]
    assert cache.key("voice", tasks.voice_facts(pop[i], base_out)) == \
        "a92d23aa839f209625870dcaaa1ea94063fcea4960bd004e9ffb6d98e1f33d8f"
    summary = tasks.report_summary(compare(world.scenario_policy("baseline"), demo), None)
    assert "service" not in summary and "travel" not in summary
    assert cache.key("report", summary) == "f71692de2d7accb5bf3c9875bbd2fee5debd57662408a9bd8841a62bf125a09b"
    assert cache.key("fixes", tasks._fixes_context(demo)["inputs"]) == \
        "833ed362ce93ef1ad8133d48be45d476182167ffb09f6af1ed605798006138bf"


# ------------------------------------------------------------------ everyday_travel

TRAVEL_DEMO = "fuel_plus_25_fares"


def _trip(**kw):
    o = {"citizen_id": "c_0028", "status": "hardship", "channel": "trip:work_sahab", "channel_name_ar": "سحاب",
         "channel_name_en": "Sahab", "mode": "car", "bus_transfers": 0, "visit_day": None, "travel_minutes": 41.6,
         "cost_jd": 37.2, "hours_lost": 30.0, "work_hours_missed": 0.0, "reasons": ["TRANSPORT_OVER_BUDGET", "FUEL_COST"],
         "purpose": "work", "days_per_week": 5, "monthly_cost_before_jd": 32.3, "extra_jd_month": 4.9,
         "income_share_pct": 28.4, "cash_support_jd_month": 0.0}
    o.update(kw)
    return o


def _citizen(**kw):
    c = dict(next(c for c in world.population() if c["id"] == "c_0028"))
    c.update(kw)
    return c


def test_travel_voice_facts_are_rounded_and_grounded():
    c = _citizen()
    o = _trip()
    f = tasks.voice_facts(c, o)
    assert f["service"] == "everyday_travel" and f["status_meaning"] == "squeezed" and f["regular_trip"] is True
    assert f["trip"]["destination_ar"].startswith("مدينة الملك عبدالله الثاني الصناعية")   # from hubs.json
    assert f["trip"]["travel_minutes_one_way"] == 42 and f["trip"]["days_per_week"] == 5
    assert f["money"] == {"monthly_cost_before_jd": 32.3, "monthly_cost_now_jd": 37.2, "extra_jd_month": 4.9,
                          "income_share_pct": 28, "cash_support_jd_month": 0.0}
    assert "has_smartphone" not in f["profile"]
    ar, en = fallbacks.voice(c, o)
    assert ar.startswith("أذهب إلى عملي في مدينة الملك عبدالله الثاني الصناعية (سحاب) بسيارتي 5 أيام في الأسبوع.")
    assert "كانت رحلتي تكلّفني 32 ديناراً في الشهر، وبعد القرار الجديد أصبحت تكلّفني 37 ديناراً، أي 28% من دخلي." in ar
    assert ar.endswith("هذا يضغط على ميزانيتي بسبب غلاء وقود سيارتي.")
    assert "32 JD a month" in en and "37 JD" in en and "28% of my income" in en
    assert checks.ungrounded(ar, f) == [] and checks.travel_voice_problems(ar) == []
    # The id_renewal wording is caught in a travel voice.
    assert checks.travel_voice_problems("لم أتمكن من تجديد هويتي")
    assert checks.travel_voice_problems("لم أتمكن من إنجاز المعاملة")


def test_travel_voice_template_modes_support_and_no_trip():
    son = _citizen(helper_relation_ar="ابني", helper_relation_en="my son")
    mom = _citizen(helper_relation_ar="أمي", helper_relation_en="my mother")
    bus = _trip(mode="bus", bus_transfers=1, reasons=["TRANSPORT_OVER_BUDGET", "FARE_COST"], status="left_out")
    ar, en = fallbacks.voice(son, bus)
    assert "بحافلتين" in ar and "لم أعد أستطيع تحمّل كلفتها بسبب ارتفاع أجور الحافلات." in ar
    assert "on two buses" in en and "can no longer afford it" in en
    ar, _ = fallbacks.voice(mom, _trip(mode="helper_car", purpose="hospital", days_per_week=1,
                                       channel="trip:hosp_bashir", status="served", reasons=[]))
    assert ar.startswith("أراجع مستشفى البشير مرة واحدة في الأسبوع، وتوصلني أمي بالسيارة.")
    assert "ما زالت كلفتها في حدود قدرتي" in ar
    cash = _trip(cash_support_jd_month=14.0, cost_jd=23.2, extra_jd_month=-9.1, status="served", reasons=[])
    ar, en = fallbacks.voice(son, cash)
    assert "ومع دعم نقدي شهري قدره 14 ديناراً أصبحت تكلّفني 23 ديناراً" in ar and "14 JD a month in cash support" in en
    assert checks.ungrounded(ar, tasks.voice_facts(son, cash)) == []
    small = _trip(monthly_cost_before_jd=19.6, cost_jd=20.1)        # whole dinars would read "20 -> 20"
    assert "19.6 دينار" in fallbacks.voice(son, small)[0] and "20.1 دينار" in fallbacks.voice(son, small)[0]
    none = {"citizen_id": "c_0028", "status": "served", "channel": "no_regular_trip", "mode": None, "purpose": None,
            "cost_jd": 0.0, "reasons": [], "cash_support_jd_month": 0.0}
    ar, en = fallbacks.voice(son, none)
    assert ar == "ليست لي رحلة منتظمة، فلا يغيّر سعر الوقود شيئاً في يومي."
    assert tasks.voice_facts(son, none)["regular_trip"] is False


def test_travel_templates_from_the_engine_are_grounded():
    pop = world.population()
    for sid in ("travel_today", TRAVEL_DEMO, "fuel_plus_25_support"):
        for c, o in zip(pop, engine.run(world.scenario_policy(sid), pop)):
            ar, _ = fallbacks.voice(c, o)
            assert checks.ungrounded(ar, tasks.voice_facts(c, o)) == [], (sid, c["id"], ar)
            assert not checks.travel_voice_problems(ar), ar
            assert not checks.foreign_people(ar, fallbacks.msa_helper(c["helper_relation_ar"])), ar


def test_travel_report_template_and_summary():
    cr = compare(world.scenario_policy("travel_today"), world.scenario_policy(TRAVEL_DEMO))
    s = tasks.report_summary(cr, None)
    assert s["service"] == "everyday_travel" and "avg_extra_jd_month" in s["travel"]["scenario"]
    assert "by_mode" in s["travel"]["scenario"] and "by_purpose" in s["travel"]["scenario"]
    ar, en = fallbacks.report(s)
    assert "من تُضغط ميزانيتهم" in ar and "يعجزون عن تحمّل كلفة التنقل" in ar and "تمت خدمتهم" not in ar
    assert "squeezed" in en and "priced out" in en and "served" not in en
    assert checks.ungrounded(ar + " " + en, s) == []
    r = tasks.write_report(cr, None)   # offline: a template, never blank
    assert r.source == "fallback" and r.summary_ar


def test_parse_raise_petrol_on_travel(live_ai):
    cur = world.scenario_policy("travel_today")
    want = cur.model_copy(update={"fuel_price_change_pct": 10.0})
    calls = live_ai(_parse_ok(want, ["رفع سعر الوقود 10%"], ["Fuel price +10%"]))
    r = tasks.parse_policy("raise petrol by 10% (stub)", cur, lang="en")
    assert r.source == "ai" and r.status == "ok" and r.policy.fuel_price_change_pct == 10
    assert r.policy.service == "everyday_travel"
    assert '"reference"' in calls[0]["user"] and '"sites"' not in calls[0]["user"]


def test_parse_on_travel_must_keep_service_and_id_fields(live_ai):
    cur = world.scenario_policy("travel_today")
    switched = cur.model_copy(update={"service": "id_renewal", "fuel_price_change_pct": 10.0})
    fee = cur.model_copy(update={"fee_jd": 5.0, "fuel_price_change_pct": 10.0})
    calls = live_ai(_parse_ok(switched, ["x"], ["x"]), _parse_ok(fee, ["x"], ["x"]))
    r = tasks.parse_policy("raise petrol by 10% (stub 2)", cur)
    assert r.source == "fallback" and len(calls) == 2
    assert "service" in calls[1]["user"]


def test_parse_id_renewal_must_not_set_travel_levers(live_ai):
    base = world.scenario_policy("baseline")
    live_ai(_parse_ok(base.model_copy(update={"fuel_price_change_pct": 10.0}), ["x"], ["x"]),
            _parse_ok(base.model_copy(update={"fuel_price_change_pct": 10.0}), ["x"], ["x"]))
    assert tasks.parse_policy("raise petrol by 10% (stub 3)", base).source == "fallback"


def _travel_answer(ctx, pol, title_ar="دعم نقدي للعاملين", title_en="Cash support for workers"):
    prop = {"title_ar": title_ar, "title_en": title_en, "rationale_ar": "دعم يصل إلى من يتنقلون كل يوم.",
            "rationale_en": "Support for the people who travel every day.", "policy": pol.model_dump(mode="json")}
    return {"explanations": _explanations(ctx), "proposal": prop}


def _travel_fix_ctx():
    scen = world.scenario_policy(TRAVEL_DEMO)
    return scen, tasks._fixes_context(scen)


def _travel_fixes(scen):
    return tasks.explain_and_propose_fixes(world.scenario_policy("travel_today"), scen)


def test_travel_fixes_inputs_are_service_aware():
    scen, ctx = _travel_fix_ctx()
    inp = ctx["inputs"]
    assert inp["service"] == "everyday_travel" and inp["scenario_by_mode"] and inp["scenario_by_purpose"]
    assert inp["proposal_limits"] == {"max_cash_jd_month": 20.0, "max_voucher_jd": 0.5}
    r = _travel_fixes(scen)   # offline: grid fixes with template explanations
    assert r.source == "fallback" and len(r.fixes) == 3
    assert all("يعجزون عن تحمّل كلفة التنقل" in f.explanation_ar and "priced out" in f.explanation_en for f in r.fixes)


@pytest.mark.parametrize("change,why", [
    ({"fuel_price_change_pct": 10.0}, "the fuel price"),
    ({"fee_jd": 0.0}, "an id_renewal field"),
    ({"bus_fare_change_pct": -20.0}, "a fare cut"),
    ({"cash_support": [{"groups": ["worker"], "amount_jd_month": 50.0}]}, "above the cash limit"),
    ({"transport_vouchers": [{"groups": ["student"], "amount_jd": 3.0}]}, "above the voucher limit"),
])
def test_travel_proposal_outside_its_levers_is_rejected(live_ai, change, why):
    scen, ctx = _travel_fix_ctx()
    pol = Policy.model_validate({**scen.model_dump(mode="json"), **change})
    calls = live_ai(_travel_answer(ctx, pol), _travel_answer(ctx, pol))
    r = _travel_fixes(scen)
    assert len(calls) == 2 and "rejected" in calls[1]["user"], why
    assert r.source == "ai" and r.ai_proposal["status"] == "invalid", why
    assert _cached_files(live_ai.dir, "fixes") == []


def test_travel_proposal_within_its_levers_is_scored_by_the_engine(live_ai):
    scen, ctx = _travel_fix_ctx()
    pol = scen.model_copy(update={"cash_support": [CashSupport(groups=["no_car"], amount_jd_month=20.0),
                                                   CashSupport(groups=["worker"], amount_jd_month=20.0)],
                                  "bus_fare_change_pct": 0.0})
    live_ai(_travel_answer(ctx, pol, title_ar="دعم نقدي 20 ديناراً شهرياً وتجميد أجور الحافلات",
                           title_en="20 JD a month cash support and a bus fare freeze"))
    r = _travel_fixes(scen)
    assert r.ai_proposal["status"] in ("shown", "hidden_not_better", "hidden_worsens_a_group"), r.ai_proposal
