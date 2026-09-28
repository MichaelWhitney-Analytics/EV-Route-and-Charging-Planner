$ErrorActionPreference = 'Stop'
if (-not (Test-Path 'src/planning/vehicle_profile.py') -or -not (Test-Path 'src/ingestion/route_station_candidates.py') -or -not (Test-Path '.venv/Scripts/python.exe')) {
    throw 'Run from the EV-Route-and-Charging-Planner project root with its existing .venv.'
}
$files = @{
    'src/planning/connector_screening.py' = @'
"""Screen reported station connector labels against an explicit vehicle plug label."""

from src.planning.vehicle_profile import VehicleProfile


CONNECTOR_LABELS = {
    "CCS": "J1772COMBO",
    "CCS1": "J1772COMBO",
    "J1772COMBO": "J1772COMBO",
    "NACS": "TESLA",
    "TESLA": "TESLA",
    "CHADEMO": "CHADEMO",
}


def screen_station_connectors(profile: VehicleProfile, stations: list[dict]) -> dict:
    """Return possible matches by listed connector type, not verified access.

    Unknown plug types fail closed. No adapter or network-access inference is made.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")
    if not isinstance(stations, list):
        raise ValueError("stations must be a list")
    plug = CONNECTOR_LABELS.get(profile.connector.strip().upper())
    if plug is None:
        raise ValueError(
            f"Unknown connector '{profile.connector}'; use CCS, NACS/TESLA, or CHADEMO"
        )
    possible = []
    other = []
    for station in stations:
        if not isinstance(station, dict):
            raise ValueError("each station must be an object")
        labels = station.get("connector_types_reported")
        if not isinstance(labels, list):
            labels = []
        normalized = {item.upper() for item in labels if isinstance(item, str)}
        if plug in normalized:
            possible.append(station)
        else:
            other.append(station)
    return {
        "vehicle_connector": profile.connector,
        "required_reported_label": plug,
        "possible_matches": possible,
        "not_matched_or_unknown": other,
        "disclaimer": "Reported connector labels are only a preliminary screen. They do not verify vehicle charging capability, adapter support, station network access, availability, or working status.",
    }
'@
    'tests/test_connector_screening.py' = @'
import pytest

from src.planning.connector_screening import screen_station_connectors
from src.planning.vehicle_profile import VehicleProfile


@pytest.fixture
def profile():
    return VehicleProfile(
        name="Test EV", usable_battery_kwh=75.0,
        driving_kwh_per_100_miles=30.0, max_dc_charge_kw=150.0,
        connector="CCS", minimum_arrival_percent=10.0,
    )


def test_matches_reported_ccs_only(profile):
    stations = [
        {"id": 1, "connector_types_reported": ["J1772COMBO", "TESLA"]},
        {"id": 2, "connector_types_reported": ["TESLA"]},
        {"id": 3, "connector_types_reported": ["J1772"]},
        {"id": 4, "connector_types_reported": None},
    ]
    result = screen_station_connectors(profile, stations)
    assert [s["id"] for s in result["possible_matches"]] == [1]
    assert [s["id"] for s in result["not_matched_or_unknown"]] == [2, 3, 4]
    assert "preliminary screen" in result["disclaimer"]


def test_nacs_label_maps_to_reported_tesla():
    vehicle = VehicleProfile("Test", 75, 30, 150, "NACS")
    result = screen_station_connectors(vehicle, [
        {"id": 1, "connector_types_reported": ["TESLA"]}
    ])
    assert result["required_reported_label"] == "TESLA"
    assert result["possible_matches"][0]["id"] == 1


def test_unknown_connector_fails_closed():
    vehicle = VehicleProfile("Test", 75, 30, 150, "unverified")
    with pytest.raises(ValueError, match="Unknown connector"):
        screen_station_connectors(vehicle, [])


def test_rejects_invalid_station_collection(profile):
    with pytest.raises(ValueError, match="stations must be a list"):
        screen_station_connectors(profile, None)


def test_rejects_invalid_station_record(profile):
    with pytest.raises(ValueError, match="station must be an object"):
        screen_station_connectors(profile, [None])
'@
}
foreach ($path in $files.Keys) {
    if (Test-Path $path) { throw "Refusing to overwrite existing file: $path" }
}
foreach ($path in $files.Keys) {
    $parent = Split-Path $path -Parent
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $path), $files[$path], [System.Text.UTF8Encoding]::new($false))
    Write-Host "Created $path"
}
& .\.venv\Scripts\python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed (exit code $LASTEXITCODE). Do not commit yet." }
Write-Host 'Tests passed. This is a connector-label screen, not a real-world compatibility guarantee.'