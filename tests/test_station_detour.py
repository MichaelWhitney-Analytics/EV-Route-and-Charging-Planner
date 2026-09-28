import json

import pytest

import src.planning.station_detour as module
from src.planning.station_detour import compare_station_detour, main


@pytest.fixture
def fake_routes(monkeypatch):
    calls = []
    routes = [(10, 20), (6, 12), (7, 14)]

    def fake_route(*coords):
        calls.append(coords)
        miles, minutes = routes[len(calls) - 1]
        return {"distance_miles": miles, "estimated_driving_minutes": minutes}

    monkeypatch.setattr(module, "get_road_route", fake_route)
    return calls


def test_compares_driving_detour(fake_routes):
    result = compare_station_detour(39.7, -105.0, 39.75, -104.95, 39.8, -104.9)
    assert result["direct_distance_miles"] == 10
    assert result["via_station_distance_miles"] == 13
    assert result["additional_driving_miles"] == 3
    assert result["additional_driving_minutes"] == 6
    assert result["start_to_station_distance_miles"] == 6
    assert len(fake_routes) == 3
    assert fake_routes[1] == (39.7, -105.0, 39.75, -104.95)


def test_command_prints_json(fake_routes, capsys):
    assert main(["39.7", "-105", "39.75", "-104.95", "39.8", "-104.9"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["additional_driving_miles"] == 3


@pytest.mark.parametrize("bad", [91, float("nan"), True])
def test_rejects_invalid_coordinates_before_network(bad):
    with pytest.raises(ValueError, match="start_lat"):
        compare_station_detour(bad, -105, 39.75, -104.95, 39.8, -104.9)


def test_routing_error_is_not_silently_ignored(monkeypatch):
    def failing_route(*coords):
        raise RuntimeError("Road routing failed")

    monkeypatch.setattr(module, "get_road_route", failing_route)
    with pytest.raises(RuntimeError, match="Road routing failed"):
        compare_station_detour(39.7, -105, 39.75, -104.95, 39.8, -104.9)