import json
from io import BytesIO

import pytest

import src.web_route_server as server


def test_coordinates_use_longitude_latitude_order():
    assert server.validate_point({"latitude": 39.7, "longitude": -105}) == [-105.0, 39.7]


@pytest.mark.parametrize("place", [None, {}, {"latitude": True, "longitude": 1}, {"latitude": 99, "longitude": 0}])
def test_invalid_places_are_rejected(place):
    with pytest.raises(ValueError):
        server.validate_point(place)


def test_route_proxy_returns_road_geometry_without_api_key(monkeypatch):
    class Response(BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()

    def fake_urlopen(req, timeout):
        assert req.full_url == server.ORS_URL
        assert req.headers["Authorization"] == "private-test-key"
        assert json.loads(req.data)["coordinates"] == [[-105.0, 39.7], [-104.9, 39.8]]
        assert timeout == 18
        data = {"features": [{"geometry": {"type": "LineString", "coordinates": [[-105, 39.7], [-104.95, 39.75], [-104.9, 39.8]]}, "properties": {"summary": {"distance": 16093.44, "duration": 1800}}}]}
        return Response(json.dumps(data).encode())

    monkeypatch.setattr(server.request, "urlopen", fake_urlopen)
    result = server.fetch_road_route({"latitude": 39.7, "longitude": -105}, {"latitude": 39.8, "longitude": -104.9}, "private-test-key")
    assert result["distance_miles"] == pytest.approx(10)
    assert result["driving_minutes"] == 30
    assert "key" not in result
    assert "No charging stops" in result["note"]


def test_missing_key_does_not_call_upstream():
    with pytest.raises(RuntimeError, match="ORS_API_KEY"):
        server.fetch_road_route({"latitude": 39.7, "longitude": -105}, {"latitude": 39.8, "longitude": -104.9}, "")