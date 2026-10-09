"""HTTP-level checks of the engine endpoints (FastAPI TestClient, offline, no AI calls, no start-up warm-up)."""
import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.sim import world

client = TestClient(app)  # not used as a context manager: the lifespan (warm-up thread) doesn't run


def _base():
    return copy.deepcopy(world.scenarios()["baseline"]["policy"])


def _demo():
    return copy.deepcopy(world.scenarios()[world.demo_scenario_id()]["policy"])


def _post_raw(path, body: dict):
    """json.dumps writes NaN/Infinity tokens (httpx's json= refuses them), the way a buggy client would."""
    return client.post(path, content=json.dumps(body), headers={"content-type": "application/json"})


def test_simulate_happy_path():
    r = client.post("/simulate", json={"policy": _base()})
    assert r.status_code == 200
    d = r.json()
    assert len(d["outcomes"]) == len(world.population())
    k = d["kpis"]
    assert {"pct_served", "pct_hardship", "pct_left_out", "left_out_by_reason", "hardship_by_reason"} <= set(k)
    assert abs(k["pct_served"] + k["pct_hardship"] + k["pct_left_out"] - 100) < 0.2


def test_compare_happy_path():
    r = client.post("/compare", json={"baseline": _base(), "scenario": _demo()})
    assert r.status_code == 200
    d = r.json()
    assert d["flipped_worse"] and d["worst_groups"][:2] == ["elderly", "offline"]
    assert all(isinstance(v, (int, float)) for v in d["kpi_delta"].values())


def test_fixgrid_returns_fixes_with_kpis_and_the_scenario_kpis():
    r = client.post("/fixgrid", json={"baseline": _base(), "scenario": _demo()})
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {"fixes", "scenario_kpis"} and 1 <= len(d["fixes"]) <= 3
    sk = d["scenario_kpis"]
    for f in d["fixes"]:
        assert f["source"] == "engine_grid" and f["n_changes"] in (1, 2)
        assert round(sk["pct_left_out"] - f["kpis"]["pct_left_out"], 1) == f["left_out_drop"]


def test_compare_is_gzipped_when_the_client_accepts_it():
    body = {"baseline": _base(), "scenario": _demo()}
    plain = client.post("/compare", json=body, headers={"accept-encoding": "identity"})
    zipped = client.post("/compare", json=body, headers={"accept-encoding": "gzip"})
    assert plain.status_code == zipped.status_code == 200
    assert "content-encoding" not in plain.headers and zipped.headers["content-encoding"] == "gzip"
    assert zipped.json() == plain.json()  # httpx decodes it transparently
    assert int(zipped.headers["content-length"]) < len(plain.content) / 4  # bytes on the wire


def _expect_422(path, body, raw=False, text=None):
    r = _post_raw(path, body) if raw else client.post(path, json=body)
    assert r.status_code == 422, r.text
    if text:
        assert text in json.dumps(r.json()), r.text
    return r


def test_unknown_site_is_422():
    p = _base()
    p["offices"][0]["site_id"] = "site_moon"
    _expect_422("/simulate", {"policy": p}, text="unknown site_id")


@pytest.mark.parametrize("hours", [("15:00", "08:00"), ("8am", "16:00"), ("25:00", "26:00")])
def test_bad_hours_are_422(hours):
    p = _base()
    p["offices"][0]["schedule"]["sun"] = list(hours)
    _expect_422("/simulate", {"policy": p}, text="bad hours")


def test_window_shorter_than_one_visit_is_422():
    p = _base()
    p["offices"][0]["schedule"]["sun"] = ["08:00", "08:30"]
    _expect_422("/simulate", {"policy": p}, text="shorter than one visit")
    p = _base()
    p["mobile_units"] = [{"area": "marka", "day": "sat", "open": "09:00", "close": "09:20"}]
    _expect_422("/simulate", {"policy": p}, text="shorter than one visit")


def test_empty_schedule_is_allowed():
    p = _base()
    p["offices"][0]["schedule"] = {}
    assert client.post("/simulate", json={"policy": p}).status_code == 200


@pytest.mark.parametrize("fee", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_fee_is_422(fee):
    p = _base()
    p["fee_jd"] = fee
    _expect_422("/simulate", {"policy": p}, raw=True, text="fee_jd")


def test_huge_fee_is_422():
    p = _base()
    p["fee_jd"] = 5000
    _expect_422("/compare", {"baseline": _base(), "scenario": p}, text="at most 1000")


def test_nan_voucher_is_a_clean_422_not_a_500():
    p = _base()
    p["transport_vouchers"] = [{"groups": ["low_income"], "amount_jd": float("nan")}]
    r = _expect_422("/simulate", {"policy": p}, raw=True)
    assert r.json()["detail"][0]["loc"][-1] == "amount_jd"


def test_nan_discount_is_422():
    p = _base()
    p["fee_discounts"] = {"elderly": float("nan")}
    _expect_422("/simulate", {"policy": p}, raw=True, text="fee discount")


def test_online_only_with_online_switched_off_is_422():
    p = _base()
    p["online_only"], p["online_enabled"] = True, False
    _expect_422("/simulate", {"policy": p}, text="online_only needs online_enabled")
    _expect_422("/fixgrid", {"baseline": _base(), "scenario": p}, text="online_only")


def test_sensitivity_rejects_a_bad_fix():
    fix = _demo()
    fix["fee_jd"] = float("nan")
    _expect_422("/sensitivity", {"baseline": _base(), "scenario": _demo(), "fix": fix}, raw=True, text="fee_jd")


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True
