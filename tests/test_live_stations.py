import pytest
import requests

from src.ingestion.live_stations import find_nearby_dc_stations


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "fuel_stations": [
                {
                    "id": 123, "station_name": "Example public charger",
                    "fuel_type_code": "ELEC", "status_code": "E",
                    "access_code": "public", "ev_dc_fast_num": 2,
                    "distance": 2.3, "ev_connector_types": ["J1772COMBO"],
                },
                {
                    "id": 124, "fuel_type_code": "ELEC",
                    "status_code": "P", "access_code": "public", "ev_dc_fast_num": 2,
                },
            ]
        }


def test_queries_public_available_dc_stations(monkeypatch):
    captured = {}

    def fake_get(url, *, params, timeout):
        captured.update(url=url, params=params, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(requests, "get", fake_get)
    result = find_nearby_dc_stations(39.7, -105.0, api_key="test-key")
    assert captured["params"]["fuel_type"] == "ELEC"
    assert captured["params"]["ev_charging_level"] == "dc_fast"
    assert captured["params"]["access"] == "public"
    assert captured["params"]["status"] == "E"
    assert captured["timeout"] == 20
    assert result["stations"][0]["id"] == 123
    assert len(result["stations"]) == 1
    assert "test-key" not in str(result)


def test_missing_key_stops_before_network(monkeypatch):
    monkeypatch.delenv("NLR_API_KEY", raising=False)
    with pytest.raises(ValueError, match="NLR_API_KEY"):
        find_nearby_dc_stations(39.7, -105.0)


@pytest.mark.parametrize("lat, lon", [(91, 0), (0, -181), (float("nan"), 0), (True, 0)])
def test_rejects_invalid_coordinates(lat, lon):
    with pytest.raises(ValueError):
        find_nearby_dc_stations(lat, lon, api_key="test-key")


def test_rejects_invalid_limit():
    with pytest.raises(ValueError, match="limit"):
        find_nearby_dc_stations(39.7, -105.0, limit=201, api_key="test-key")


def test_network_error_does_not_reveal_key(monkeypatch):
    def fake_get(url, *, params, timeout):
        raise requests.RequestException("sensitive test-key")

    monkeypatch.setattr(requests, "get", fake_get)
    with pytest.raises(RuntimeError) as exc:
        find_nearby_dc_stations(39.7, -105.0, api_key="test-key")
    assert "test-key" not in str(exc.value)