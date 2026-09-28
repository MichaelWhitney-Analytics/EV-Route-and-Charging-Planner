import pytest
import requests

from src.ingestion.live_road_route import get_road_route


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"routes": [{"summary": {"distance": 16093.44, "duration": 900}, "geometry": "encoded-example"}]}


def test_returns_road_distance_and_duration(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, body=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    result = get_road_route(39.7, -105.0, 39.8, -104.9, api_key="test-key")
    assert captured["body"]["coordinates"] == [[-105.0, 39.7], [-104.9, 39.8]]
    assert result["distance_miles"] == pytest.approx(10)
    assert result["estimated_driving_minutes"] == pytest.approx(15)
    assert result["encoded_geometry"] == "encoded-example"
    assert "test-key" not in str(result)


def test_missing_key_prevents_request(monkeypatch):
    monkeypatch.delenv("ORS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ORS_API_KEY"):
        get_road_route(39.7, -105.0, 39.8, -104.9)


@pytest.mark.parametrize("value", [91, float("nan"), True])
def test_rejects_invalid_latitude(value):
    with pytest.raises(ValueError, match="start_latitude"):
        get_road_route(value, -105.0, 39.8, -104.9, api_key="test-key")


def test_network_error_hides_key(monkeypatch):
    def fake_post(url, *, headers, json, timeout):
        raise requests.RequestException("test-key is sensitive")

    monkeypatch.setattr(requests, "post", fake_post)
    with pytest.raises(RuntimeError) as exc:
        get_road_route(39.7, -105.0, 39.8, -104.9, api_key="test-key")
    assert "test-key" not in str(exc.value)