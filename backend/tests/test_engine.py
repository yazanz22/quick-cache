import json
import time

from app.data import seed
from app.models import Citizen, MobileUnit, Office, Policy
from app.sim import engine, world
from app.sim.compare import compare

WD = ["sun", "mon", "tue", "wed", "thu"]


def person(**kw):
    c = {"id": "t_1", "name_ar": "س", "name_en": "S", "age": 40, "gender": "f", "area": "marka",
         "lat": 31.975, "lng": 35.985, "mobility": "none", "has_car": False, "has_smartphone": True,
         "digital_literacy": "medium", "works": False, "work_start": None, "work_end": None,
         "income_band": "middle", "has_helper": False, "helper_relation_ar": None, "helper_relation_en": None}
    c.update(kw)
    c["tags"] = seed.derive_tags(c)
    return c


def office(site="site_marka", close="15:00", accessible=True, days=WD):
    return Office(id="o1", name_ar="م", name_en="O", site_id=site, schedule={d: ("08:00", close) for d in days},
                  wheelchair_accessible=accessible)


def policy(**kw):
    p = dict(offices=[office()], online_enabled=True, fee_jd=2.0)
    p.update(kw)
    return Policy(**p)


def one(c, p):
    return engine.run(p, [c])[0]


def test_seed_is_deterministic():
    assert seed.generate(50) == seed.generate(50)


def test_committed_population_is_valid_and_tags_are_derived():
    committed = json.loads((world.DATA_DIR / "population.json").read_text(encoding="utf-8"))
    assert len({c["id"] for c in committed}) == len(committed) > 0
    for c in committed:
        Citizen.model_validate(c)
        assert c["tags"] == seed.derive_tags(c)
        assert c["area"] in world.areas()


def test_every_citizen_has_osrm_travel_times():
    matrix = world.travel_matrix()
    dests = set(world.sites()) | {f"area:{a}" for a in world.areas()}
    assert all(c["id"] in matrix and dests <= set(matrix[c["id"]]) for c in world.population())


def test_simulate_is_deterministic_and_fast():
    p = world.scenario_policy(world.demo_scenario_id())
    engine._MEMO.clear()
    t = time.perf_counter()
    a = engine.run(p)
    cold = time.perf_counter() - t
    t = time.perf_counter()
    b = engine.run(p)
    warm = time.perf_counter() - t
    engine._MEMO.clear()
    assert a == b == engine.run(p)
    assert cold < 0.5 and warm < 0.05


def test_online_capable_citizen_is_served_online():
    o = one(person(), policy())
    assert o["status"] == "served" and o["channel"] == "online" and o["reasons"] == []


def test_online_only_offline_without_helper_is_left_out():
    o = one(person(has_smartphone=False, digital_literacy="low"), policy(online_only=True))
    assert o["status"] == "left_out"
    assert o["reasons"] == ["NO_SMARTPHONE", "LOW_DIGITAL_LITERACY"]


def test_online_only_offline_with_helper_is_hardship():
    c = person(has_smartphone=False, has_helper=True, helper_relation_ar="ابني", helper_relation_en="my son")
    o = one(c, policy(online_only=True))
    assert o["status"] == "hardship" and o["mode"] == "online" and o["reasons"] == ["NO_SMARTPHONE"]


def test_wheelchair_user_and_inaccessible_office():
    c = person(mobility="wheelchair", has_car=True, has_smartphone=False)
    o = one(c, policy(online_enabled=False, offices=[office(accessible=False)]))
    assert o["status"] == "left_out" and "NOT_WHEELCHAIR_ACCESSIBLE" in o["reasons"]
    assert one(c, policy(online_enabled=False))["status"] != "left_out"


def test_appointment_without_booking_ability_costs_a_wasted_trip():
    c = person(has_smartphone=False, has_car=True)
    walk_in = one(c, policy())
    appt = one(c, policy(appointment_required=True))
    assert appt["status"] == "hardship"
    assert appt["hours_lost"] > walk_in["hours_lost"] * 1.5  # two trips instead of one
    assert "NO_SMARTPHONE" in appt["reasons"]


def test_mobile_units_never_need_appointments():
    c = person(has_smartphone=False, has_car=True)
    p = policy(appointment_required=True, offices=[],
               mobile_units=[MobileUnit(area="marka", day="sat", open="09:00", close="14:00")])
    o = one(c, p)
    assert o["channel"] == "mobile:marka:sat" and o["status"] == "served"


def test_worker_misses_work_unless_an_outside_work_slot_exists():
    c = person(works=True, work_start="08:00", work_end="16:00", has_smartphone=False, has_car=True)
    o = one(c, policy())
    assert o["status"] == "hardship" and o["work_hours_missed"] > 0 and o["reasons"] == ["HOURS_CONFLICT_WORK"]
    o2 = one(c, policy(offices=[office(close="19:00")]))
    assert o2["work_hours_missed"] == 0 and o2["status"] == "served"


def test_helper_only_drives_on_weekends_or_after_work_hours():
    c = person(mobility="wheelchair", has_smartphone=False, income_band="low", has_helper=True,
               helper_relation_ar="ابني", helper_relation_en="my son", area="khalda", lat=31.995, lng=35.835)
    weekday = one(c, policy(online_enabled=False))  # Marka office, 08-15, far from Khalda
    assert weekday["status"] == "left_out"
    sat_van = policy(online_enabled=False,
                     mobile_units=[MobileUnit(area="marka", day="sat", open="09:00", close="14:00")])
    o = one(c, sat_van)
    assert o["status"] == "hardship" and o["mode"] == "helper_car" and o["visit_day"] == "sat"


def test_taxi_above_income_cap_is_too_expensive():
    c = person(mobility="wheelchair", income_band="low", has_smartphone=False, area="khalda", lat=31.995, lng=35.835)
    o = one(c, policy(online_enabled=False))
    assert o["status"] == "left_out" and "TOO_EXPENSIVE" in o["reasons"] and "NO_TRANSPORT" in o["reasons"]


def test_closed_office_reason():
    c = person(has_smartphone=False, has_car=True)
    o = one(c, policy(online_enabled=False, offices=[office(days=[])]))
    assert o["status"] == "left_out" and o["reasons"] == ["OFFICE_CLOSED_ON_AVAILABLE_DAYS"]


def test_compare_flips_and_groups():
    cr = compare(world.scenario_policy("baseline"), world.scenario_policy("online_only"))
    assert cr.flipped_worse and not cr.flipped_better
    assert set(cr.worst_groups) == set(world.EQUITY_GROUPS)
    assert cr.kpi_delta["pct_left_out"] > 0
    assert abs(sum(cr.scenario.kpis[k] for k in ["pct_served", "pct_hardship", "pct_left_out"]) - 100) < 0.2


def test_every_assumption_has_arabic_and_english_labels():
    from app.sim import assumptions as A
    from app.sim.assumption_labels import label_rows
    rows = label_rows(A.as_table())
    assert all(r["label_ar"] and r["label_en"] and r["rationale_ar"] for r in rows)
