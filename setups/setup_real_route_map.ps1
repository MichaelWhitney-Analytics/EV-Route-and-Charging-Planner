$ErrorActionPreference = 'Stop'
$page = 'web/trip_planner_visual_prototype.html'
$serverPath = 'src/web_route_server.py'
$testPath = 'tests/test_web_route_server.py'
foreach ($required in @($page, 'web/place_autocomplete.js', '.venv/Scripts/python.exe')) { if (-not (Test-Path $required)) { throw "Missing $required. Run from project root after the autocomplete milestone." } }
foreach ($path in @($serverPath, $testPath)) { if (Test-Path $path) { throw "Refusing to overwrite $path" } }
$html = [System.IO.File]::ReadAllText((Join-Path (Get-Location).Path $page))
$mapPattern = '(?s)<section class="map" aria-label="Schematic map-style route illustration, not a geographic driving route">.*?</section>'
$oldScriptPattern = '(?s)<script>\s*"use strict";\s*const keys=\["origin","first","second","destination"\];.*?</script>'
$timelinePattern = '(?s)<ol class="timeline">.*?</ol>'
foreach ($pattern in @($mapPattern, $oldScriptPattern, $timelinePattern)) { if (([regex]::Matches($html, $pattern)).Count -ne 1) { throw 'Unexpected prototype markup. No files changed.' } }
if (-not $html.Contains('<script src="place_autocomplete.js"></script>') -or -not $html.Contains('id="vehicle-mode"')) { throw 'Expected prior features are missing. No files changed.' }
$server = @'
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
'@
$tests = @'
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
'@
$map = @'
<section class="map" aria-label="Interactive road map"><div id="real-map" role="region" aria-label="Interactive road map showing selected locations and direct driving route"></div><div class="map-head"><strong>Real road map</strong><span id="map-caption">Select two suggested places, then draw a direct driving route.</span></div><div class="map-note">Direct road route only. No charging stops or battery outcomes calculated. Map data © OpenStreetMap contributors.</div></section>
'@
$timeline = @'
<ol class="timeline" id="route-timeline"><li><div class="stop-button"><strong id="from-label">Choose your starting place</strong><span class="detail">Select a suggestion from the From field.</span></div></li><li class="destination"><div class="stop-button"><strong id="to-label">Choose your destination</strong><span class="detail">Select a suggestion from the To field.</span></div></li></ol>
'@
$client = @'
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
"use strict";
const vehicleInputs=["vehicle-name","battery-kwh","consumption","charge-kw","connector","start-percent","reserve-percent"];
const vehicleMode=document.getElementById("vehicle-mode"),customDetails=document.getElementById("custom-vehicle-details"),vehicleSummary=document.getElementById("vehicle-summary");
function updateVehicleSummary(){const custom=vehicleMode.value==="custom";customDetails.hidden=!custom;for(const input of customDetails.querySelectorAll("input,select"))input.disabled=!custom;vehicleSummary.textContent=custom?"Custom vehicle values are not used in this direct-road-map preview. Battery outcomes remain uncalculated.":"Vehicle catalog is not available. Battery outcomes remain uncalculated."}
vehicleMode.addEventListener("change",updateVehicleSummary);for(const id of vehicleInputs){document.getElementById(id).addEventListener("input",updateVehicleSummary)}updateVehicleSummary();
const mapReady=typeof L!=="undefined";
const map=mapReady?L.map("real-map").setView([39.5,-98.35],4):null;
if(map){L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'}).addTo(map)}else{document.getElementById("map-caption").textContent="Map library unavailable. Check your internet connection."}
let routeLayer=null,pointLayers=[];
const metricCards=document.querySelectorAll(".metric");
metricCards[0].innerHTML="<strong>—</strong><span>Direct road distance</span>";
metricCards[1].innerHTML="<strong>—</strong><span>Driving time</span>";
metricCards[2].innerHTML="<strong>0</strong><span>Planned charge stops</span>";
const demoTag=document.querySelector(".demo");demoTag.textContent="DIRECT ROAD MAP · NO CHARGING PLAN";
document.querySelector(".map .map-note").textContent="Direct road route only; charging stops and battery outcomes have not been calculated. Map data © OpenStreetMap contributors.";
document.querySelector(".foot").textContent="This map is for route exploration. A drawn road line is not a verified charging itinerary. Vehicle battery, charger access, availability and trip completion remain unverified.";
document.querySelector(".notice").textContent="Choose a suggestion in each place field before drawing a direct road route. Vehicle inputs do not yet affect this map. No charging stops or battery estimates will be shown.";
const routeButton=document.querySelector('#trip-form button[type="submit"]');routeButton.textContent="Draw road route";
document.getElementById("trip-form").addEventListener("submit",async event=>{
 event.preventDefault();const selected=window.routewiseSelectedPlaces;
 const caption=document.getElementById("map-caption");
 if(!map){caption.textContent="Map library unavailable. Check your internet connection.";return}
 if(!selected||!selected.from||!selected.to){caption.textContent="Select a suggested From and To place first (typed labels alone are not enough).";return}
 routeButton.disabled=true;caption.textContent="Requesting a direct road route…";
 try{
  const response=await fetch("/api/route",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({origin:selected.from,destination:selected.to})});
  const data=await response.json();if(!response.ok)throw new Error(data.error||"Road route unavailable.");
  if(routeLayer)map.removeLayer(routeLayer);for(const marker of pointLayers)map.removeLayer(marker);pointLayers=[];
  routeLayer=L.geoJSON({type:"Feature",geometry:data.geometry,properties:{}},{style:{color:"#137eab",weight:6,opacity:.9}}).addTo(map);
  pointLayers.push(L.marker([selected.from.latitude,selected.from.longitude]).addTo(map).bindPopup("Origin"));
  pointLayers.push(L.marker([selected.to.latitude,selected.to.longitude]).addTo(map).bindPopup("Destination"));
  map.fitBounds(routeLayer.getBounds(),{padding:[32,32]});
  metricCards[0].querySelector("strong").textContent=`${data.distance_miles.toFixed(1)} mi`;
  metricCards[1].querySelector("strong").textContent=`${Math.round(data.driving_minutes)} min`;
  document.getElementById("from-label").textContent=selected.from.label;
  document.getElementById("to-label").textContent=selected.to.label;
  caption.textContent="Direct driving route · no charging stops or battery estimates calculated";
 }catch(error){caption.textContent=error.message||"Road route unavailable. Try again."}finally{routeButton.disabled=false}
});
document.getElementById("reset").addEventListener("click",()=>{if(routeLayer){map.removeLayer(routeLayer);routeLayer=null}for(const marker of pointLayers)map.removeLayer(marker);pointLayers=[];document.getElementById("map-caption").textContent="Select two suggested places, then draw a direct driving route.";for(const card of metricCards.slice(0,2))card.querySelector("strong").textContent="—";document.getElementById("from-label").textContent="Choose your starting place";document.getElementById("to-label").textContent="Choose your destination"});
</script>
'@
$html = [regex]::Replace($html, $mapPattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $map })
$html = [regex]::Replace($html, $timelinePattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $timeline })
$html = [regex]::Replace($html, $oldScriptPattern, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $client })
$html = $html.Replace('.map svg{width:100%;height:100%;display:block}', '')
$html = $html.Replace('</head>', '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">' + "`n" + '<style>#real-map{width:100%;height:100%;min-height:350px}.map .map-head{pointer-events:none}.map .map-note{pointer-events:none}</style>' + "`n" + '</head>')
$utf8 = [System.Text.UTF8Encoding]::new($false)
New-Item -ItemType Directory -Force -Path (Split-Path $serverPath -Parent) | Out-Null
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $serverPath), $server, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $testPath), $tests, $utf8)
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $page), $html, $utf8)
Write-Host "Updated $page; created $serverPath and $testPath"
$vehicleTestPath = 'tests/test_vehicle_controls_preview.py'
$vehicleTest = [System.IO.File]::ReadAllText($vehicleTestPath)
$vehicleTest = $vehicleTest.Replace('assert "example itinerary unchanged" in page', 'assert "Battery outcomes remain uncalculated" in page')
[System.IO.File]::WriteAllText($vehicleTestPath, $vehicleTest, $utf8)
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Offline tests passed. The road map requires the local server and ORS_API_KEY; do not open the HTML directly for routing.'