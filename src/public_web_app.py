"""Limited public-facing portfolio demo. Keep ORS_API_KEY server-side."""
import os
import threading
import time

from flask import Flask, jsonify, redirect, request, send_from_directory

from src.web_route_server import (
    WEB_ROOT,
    build_conditional_plan,
    fetch_road_route,
    read_charging_profile_ids,
    read_vehicle_choices,
    validate_point,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4096

_lock = threading.Lock()
_window_start = time.monotonic()
_counts = {"route": 0, "plan": 0}
_limits = {"route": 30, "plan": 10}


def reserve_request(kind):
    """Small process-local, rolling-24-hour demo cap; not a provider quota."""
    global _window_start
    with _lock:
        now = time.monotonic()
        if now - _window_start >= 86400:
            _window_start = now
            _counts.update(route=0, plan=0)
        if _counts[kind] >= _limits[kind]:
            return False
        _counts[kind] += 1
        return True


@app.after_request
def no_store_api(response):
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def home():
    return redirect("/trip_planner_visual_prototype.html")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/api/vehicles")
def vehicles():
    try:
        return jsonify(read_vehicle_choices())
    except (RuntimeError, ValueError, OSError) as exc:
        return jsonify(error=str(exc)), 503


@app.get("/api/charging-profile-ids")
def charging_profile_ids():
    try:
        return jsonify(read_charging_profile_ids())
    except (RuntimeError, ValueError, OSError) as exc:
        return jsonify(error=str(exc)), 503


@app.post("/api/<kind>")
def plan_or_route(kind):
    if kind not in ("route", "conditional-plan"):
        return jsonify(error="Not found."), 404
    if not request.is_json:
        return jsonify(error="Send a JSON request."), 400
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="Select two locations before planning."), 400
    try:
        origin, destination = payload.get("origin"), payload.get("destination")
        validate_point(origin)
        validate_point(destination)
        quota_kind = "plan" if kind == "conditional-plan" else "route"
        if not reserve_request(quota_kind):
            return jsonify(error="Demo request limit reached. Please try again later."), 429
        if kind == "conditional-plan":
            result = build_conditional_plan(payload)
        else:
            result = fetch_road_route(
                origin, destination, os.environ.get("ORS_API_KEY")
            )
        return jsonify(result)
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    except Exception:
        app.logger.exception("Public route request failed")
        return jsonify(error="Route service temporarily unavailable."), 503


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify(error="Route request is too large."), 413


@app.get("/<path:filename>")
def static_file(filename):
    if filename not in (
        "trip_planner_visual_prototype.html",
        "place_autocomplete.js",
    ):
        return jsonify(error="Not found."), 404
    return send_from_directory(WEB_ROOT, filename)
