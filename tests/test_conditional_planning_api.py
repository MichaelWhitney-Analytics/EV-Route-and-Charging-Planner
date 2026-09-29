import pytest
import src.web_route_server as server


PLACE_A = {"latitude": 39., "longitude": -105., "label": "A"}
PLACE_B = {"latitude": 40., "longitude": -104., "label": "B"}
VEHICLE = {"name": "My EV", "usable_battery_kwh": 75.,
           "driving_kwh_per_100_miles": 30., "max_dc_charge_kw": 150.,
           "connector": "CCS", "minimum_arrival_percent": 10.}


def request():
    return {"origin": PLACE_A.copy(), "destination": PLACE_B.copy(),
            "vehicle": VEHICLE.copy(), "start_percent": 80.}


def test_explicit_planning_returns_conditional_timeline(monkeypatch):
    calls = []
    def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return {"selection": {"status": "conditional_energy_path", "selected_site_names": ["Station"],
                              "itinerary": {"timeline": [{"kind": "site", "arrival_percent": 25., "site_usable": "unverified"}]},
                              "note": "Unverified charger."},
                "ordered_sites": [{"name": "Station", "station_ids": [1]}],
                "baseline_road_miles": 190., "disclaimer": "Sparse search."}
    monkeypatch.setattr(server, "build_measured_candidate_graph", fake)
    result = server.build_conditional_plan(request())
    assert result["status"] == "conditional_energy_path"
    assert result["itinerary"]["timeline"][0]["site_usable"] == "unverified"
    assert "Sparse search" in result["disclaimer"]
    assert calls[0][1]["max_sites"] == 2
    assert calls[0][0][3] == (39., -105.)


@pytest.mark.parametrize("change", [
    lambda p: p.update(start_percent=True),
    lambda p: p["origin"].pop("label"),
    lambda p: p["vehicle"].update(usable_battery_kwh=-1),
    lambda p: p.update(vehicle={}),
])
def test_invalid_input_never_calls_network(monkeypatch, change):
    monkeypatch.setattr(server, "build_measured_candidate_graph", lambda *a, **k: pytest.fail("network called"))
    payload = request()
    change(payload)
    with pytest.raises(ValueError):
        server.build_conditional_plan(payload)


def test_server_route_is_opt_in():
    from pathlib import Path
    text = Path(server.__file__).read_text(encoding="utf-8")
    assert 'self.path == "/api/conditional-plan"' in text
    assert 'self.path not in ("/api/route", "/api/conditional-plan")' in text


def test_sourced_catalog_id_builds_opt_in_profile(monkeypatch):
    captured = []

    def fake(profile, *args, **kwargs):
        captured.append((profile, kwargs))
        return {
            "selection": {
                "status": "no_charge_needed",
                "selected_site_names": [],
                "itinerary": {"timeline": []},
                "note": "Conditional estimate.",
            },
            "ordered_sites": [],
            "baseline_road_miles": 20.0,
            "disclaimer": "Unverified stations.",
        }

    monkeypatch.setattr(server, "build_measured_candidate_graph", fake)
    payload = request()
    payload.pop("vehicle")
    payload["vehicle_id"] = 49612

    result = server.build_conditional_plan(payload)
    profile, kwargs = captured[0]

    assert result["status"] == "no_charge_needed"
    assert profile.name == "2026 Audi Q4 45 e-tron"
    assert profile.usable_battery_kwh == 77.0
    assert profile.max_dc_charge_kw == 175.0
    assert profile.connector == "CCS"
    assert profile.driving_kwh_per_100_miles == pytest.approx(29.4031)
    assert profile.minimum_arrival_percent == 10.0
    assert kwargs["max_sites"] == 2


@pytest.mark.parametrize("bad_id", [True, "49612", 999999])
def test_unsourced_or_invalid_catalog_id_never_calls_network(monkeypatch, bad_id):
    monkeypatch.setattr(
        server,
        "build_measured_candidate_graph",
        lambda *args, **kwargs: pytest.fail("network called"),
    )
    payload = request()
    payload.pop("vehicle")
    payload["vehicle_id"] = bad_id
    with pytest.raises(ValueError):
        server.build_conditional_plan(payload)


def test_cannot_override_sourced_catalog_profile(monkeypatch):
    monkeypatch.setattr(
        server,
        "build_measured_candidate_graph",
        lambda *args, **kwargs: pytest.fail("network called"),
    )
    payload = request()
    payload["vehicle_id"] = 49612
    with pytest.raises(ValueError, match="either"):
        server.build_conditional_plan(payload)
