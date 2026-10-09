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
    assert set(fallbacks.REASON_VOICE) == set(fallbacks.REASON_LABELS)


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
    daily = client._classify(Exception("429 RESOURCE_EXHAUSTED quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier"))
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
