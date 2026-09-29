"""Local-only static web server and limited ORS road-route proxy.

Run with ORS_API_KEY set. Never commit or expose the API key to browser JS.
"""

import json
import math
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request

ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
WEB_ROOT = Path(__file__).resolve().parents[1] / "web"


def validate_point(value):
    if not isinstance(value, dict):
        raise ValueError("Select a place from each suggestion list.")
    lat, lon = value.get("latitude"), value.get("longitude")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (lat, lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Selected place coordinates are invalid.")
    return [float(lon), float(lat)]


def fetch_road_route(origin, destination, key):
    if not key:
        raise RuntimeError("ORS_API_KEY is not set in the server terminal.")
    coordinates = [validate_point(origin), validate_point(destination)]
    payload = json.dumps({"coordinates": coordinates}).encode("utf-8")
    req = request.Request(ORS_URL, data=payload, method="POST", headers={
        "Authorization": key, "Content-Type": "application/json", "Accept": "application/geo+json",
    })
    try:
        with request.urlopen(req, timeout=18) as response:
            data = json.load(response)
    except (error.HTTPError, error.URLError, TimeoutError) as exc:
        raise RuntimeError("Road routing is unavailable. Check selected places and try again.") from exc
    features = data.get("features") if isinstance(data, dict) else None
    if not isinstance(features, list) or not features:
        raise RuntimeError("No road route was returned for these places.")
    feature = features[0]
    geometry = feature.get("geometry", {})
    summary = feature.get("properties", {}).get("summary", {})
    distance, duration = summary.get("distance"), summary.get("duration")
    points = geometry.get("coordinates") if geometry.get("type") == "LineString" else None
    if (not isinstance(points, list) or len(points) < 2 or len(points) > 100000
            or any(not isinstance(point, list) or len(point) < 2
                   or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                          for v in point[:2]) for point in points)
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
                   for v in (distance, duration))):
        raise RuntimeError("Road routing returned incomplete or invalid geometry.")
    return {"geometry": geometry, "distance_miles": distance / 1609.344,
            "driving_minutes": duration / 60, "origin": coordinates[0], "destination": coordinates[1],
            "note": "Direct road route only. No charging stops or battery outcomes have been calculated."}


class RouteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def do_POST(self):
        if self.path != "/api/route":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("Route request is empty or too large.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Select two locations before planning.")
            origin, destination = payload.get("origin"), payload.get("destination")
            validate_point(origin)
            validate_point(destination)
            result = fetch_road_route(origin, destination, os.environ.get("ORS_API_KEY"))
            status = 200
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            result, status = {"error": str(exc)}, 400
        except RuntimeError as exc:
            result, status = {"error": str(exc)}, 503
        data = json.dumps(result).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    if not os.environ.get("ORS_API_KEY"):
        raise SystemExit("Set ORS_API_KEY in this terminal before starting the local map server.")
    server = ThreadingHTTPServer(("127.0.0.1", 8765), RouteHandler)
    print("Local trip map: http://127.0.0.1:8765/trip_planner_visual_prototype.html")
    print("Press Ctrl+C to stop. Never expose this development server publicly.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()