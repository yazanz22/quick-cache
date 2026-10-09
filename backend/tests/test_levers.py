"""Group protections and the hybrid process: walk-in exemption, fee discounts, home visits, transport vouchers,
apply-online-then-collect. Offline, no AI calls."""
from app.llm import fallbacks, tasks
from app.models import HomeVisits, TransportVoucher
from app.sim import engine, world
from app.sim.engine import STATUS_RANK
from app.sim.validate import canonical, count_changes, policy_errors

from .test_engine import office, person, policy

DEMO = world.demo_scenario_id()


def _with(p, **kw):
    return p.model_copy(update=kw)


def _never_worse(before, after):
    return all(STATUS_RANK[b["status"]] >= STATUS_RANK[a["status"]] for b, a in zip(before, after))


def test_no_lever_set_changes_nothing():
    for sid in ["baseline", DEMO]:
        p = world.scenario_policy(sid)
        assert engine.run(p) == engine.run(_with(p, appointment_exempt_groups=[], fee_discounts={}, home_visits=None,
                                                 transport_vouchers=[], hybrid_pickup=False))


def test_walk_in_exemption_skips_the_booking_for_that_group_only():
    offline_elder = person(age=70, has_smartphone=False, has_helper=True, helper_relation_ar="ابني")
    p = policy(appointment_required=True, online_enabled=False)
    booked = engine.run(p, [offline_elder])[0]
    exempt = engine.run(_with(p, appointment_exempt_groups=["elderly"]), [offline_elder])[0]
    assert "NO_SMARTPHONE" in booked["reasons"] and "NO_SMARTPHONE" not in exempt["reasons"]
    assert engine.run(_with(p, appointment_exempt_groups=["worker"]), [offline_elder])[0] == booked


def test_fee_discount_is_per_group_and_the_largest_applies():
    c = person(age=70, income_band="low")
    p = policy(fee_jd=4.0)
    full = engine.run(p, [c])[0]["cost_jd"]
    half = engine.run(_with(p, fee_discounts={"elderly": 50}), [c])[0]["cost_jd"]
    free = engine.run(_with(p, fee_discounts={"elderly": 50, "low_income": 100}), [c])[0]["cost_jd"]
    assert round(full - half, 2) == 2.0 and round(full - free, 2) == 4.0
    assert any("0-100" in e for e in policy_errors(_with(p, fee_discounts={"elderly": 150})))


def test_home_visits_go_to_the_worst_off_eligible_first_and_respect_the_cap():
    p = world.scenario_policy(DEMO)
    before = engine.run(p)
    after = engine.run(_with(p, home_visits=HomeVisits(groups=["disabled", "elderly"], slots=10)))
    pop = world.population()
    used = [i for i, o in enumerate(after) if o["channel"] == "home_visit"]
    assert len(used) == 10 and _never_worse(before, after)
    assert all({"disabled", "elderly"} & set(pop[i]["tags"]) for i in used)
    left_eligible = [i for i, o in enumerate(before) if o["status"] == "left_out" and {"disabled", "elderly"} & set(pop[i]["tags"])]
    assert all(after[i]["channel"] == "home_visit" for i in left_eligible[:10])  # left-out residents come first
    k, _ = engine.summarize(after)
    assert k["n_home_visits"] == 10


def test_transport_voucher_makes_a_taxi_affordable():
    c = person(mobility="wheelchair", income_band="low", area="sweileh", lat=32.02, lng=35.84)
    p = policy(online_enabled=False)  # office in Marka: far, taxi too expensive for a low income
    plain = engine.run(p, [c])[0]
    assert plain["status"] == "left_out" and "TOO_EXPENSIVE" in plain["reasons"]
    helped = engine.run(_with(p, transport_vouchers=[TransportVoucher(groups=["disabled"], amount_jd=15)]), [c])[0]
    assert helped["status"] != "left_out" and helped["mode"] == "taxi"


def test_hybrid_pickup_never_hurts_and_helps_without_online_renewal():
    for sid in ["baseline", DEMO]:
        p = world.scenario_policy(sid)
        assert _never_worse(engine.run(p), engine.run(_with(p, hybrid_pickup=True)))
    p = _with(world.scenario_policy("baseline"), online_enabled=False)
    k0, _ = engine.summarize(engine.run(p))
    k1, _ = engine.summarize(engine.run(_with(p, hybrid_pickup=True)))
    assert k1["pct_served"] > k0["pct_served"]


def test_change_count_canonical_and_cache_keys_for_the_new_fields():
    p = world.scenario_policy("baseline")
    q = _with(p, appointment_exempt_groups=["elderly"], fee_discounts={"elderly": 100},
              home_visits=HomeVisits(), hybrid_pickup=True)
    assert count_changes(p, q) == 4
    assert canonical(_with(q, appointment_exempt_groups=["elderly", "elderly"])) == canonical(q)
    assert set(tasks.policy_json(p)) == set(tasks.policy_json(world.scenario_policy("baseline")))
    assert "fee_discounts" not in tasks.policy_json(p) and "fee_discounts" in tasks.policy_json(q)


def test_home_visit_voice_template():
    c = person(age=82, mobility="wheelchair")
    o = {"status": "served", "mode": "home", "channel": "home_visit", "channel_name_ar": "زيارة منزلية",
         "channel_name_en": "Home visit", "cost_jd": 2.0, "hours_lost": 2.0, "travel_minutes": 0, "reasons": []}
    ar, en = fallbacks.voice(c, o)
    assert "بيتي" in ar and "home" in en
