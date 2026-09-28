import pytest

import src.ingestion.route_station_candidates as candidate_module
from src.ingestion.route_station_candidates import decode_polyline, find_route_station_candidates, sample_route


def test_decodes_known_polyline():
    assert decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [
        (38.5, -120.2), (40.7, -120.95), (43.252, -126.453),
    ]


@pytest.mark.parametrize("encoded", ["", "?", "!", "_p~iF"])
def test_rejects_malformed_polyline(encoded):
    with pytest.raises(ValueError):
        decode_polyline(encoded)


def test_samples_start_middle_and_end():
    samples = sample_route([(0, 0), (0, 1), (0, 2)])
    assert samples[0] == (0, 0)
    assert samples[1][1] == pytest.approx(1)
    assert samples[2] == (0, 2)


def test_deduplicates_station_ids(monkeypatch):
    monkeypatch.setattr(candidate_module, "get_road_route", lambda *args: {
        "distance_miles": 12, "estimated_driving_minutes": 20,
        "encoded_geometry": "_p~iF~ps|U_ulLnnqC_mqNvxq`@",
    })
    calls = []

    def fake_lookup(lat, lon, *, radius_miles, limit):
        calls.append((lat, lon, radius_miles, limit))
        return {"stations": [{"id": 123, "name": "Example"}]}

    monkeypatch.setattr(candidate_module, "find_nearby_dc_stations", fake_lookup)
    result = find_route_station_candidates(38.5, -120.2, 43.252, -126.453)
    assert len(calls) == 3
    assert len(result["candidate_stations"]) == 1
    assert result["candidate_stations"][0]["id"] == 123
    assert "no detour" in result["disclaimer"]