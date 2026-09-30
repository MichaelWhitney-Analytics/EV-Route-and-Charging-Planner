from unittest.mock import patch

from src import public_web_app


def test_public_pages_and_catalog():
    client = public_web_app.app.test_client()
    assert client.get("/health").json == {"status": "ok"}
    assert client.get("/").status_code == 302
    assert client.get("/trip_planner_visual_prototype.html").status_code == 200
    assert client.get("/place_autocomplete.js").status_code == 200
    assert client.get("/requirements.txt").status_code == 404
    assert client.get("/api/vehicles").status_code == 200
    assert client.get("/api/charging-profile-ids").status_code == 200


def test_public_route_uses_server_side_key_only():
    client = public_web_app.app.test_client()
    payload = {
        "origin": {"latitude": 39.7, "longitude": -104.9},
        "destination": {"latitude": 40.0, "longitude": -105.2},
    }
    with patch.dict(public_web_app._counts, {"route": 0}):
        with patch.dict("os.environ", {"ORS_API_KEY": "test-only-key"}):
            with patch.object(
                public_web_app, "fetch_road_route", return_value={"ok": True}
            ) as fetch:
                response = client.post("/api/route", json=payload)
                assert response.status_code == 200
                assert response.json == {"ok": True}
                assert fetch.call_args.args[2] == "test-only-key"


def test_public_request_limit_rejects_before_outbound_call():
    client = public_web_app.app.test_client()
    payload = {
        "origin": {"latitude": 39.7, "longitude": -104.9},
        "destination": {"latitude": 40.0, "longitude": -105.2},
    }
    with patch.dict(public_web_app._counts, {"route": public_web_app._limits["route"]}):
        with patch.object(public_web_app, "fetch_road_route") as fetch:
            response = client.post("/api/route", json=payload)
            assert response.status_code == 429
            fetch.assert_not_called()


def test_public_bad_or_oversized_json():
    client = public_web_app.app.test_client()
    assert client.post(
        "/api/route", data="bad json", content_type="application/json"
    ).status_code == 400
    assert client.post(
        "/api/route", data="x" * 4097, content_type="application/json"
    ).status_code == 413
