from copy import deepcopy

import pytest

from src.validation.trip_request import validate_trip_request


@pytest.fixture
def valid_trip():
    return {
        "vehicle": {
            "name": "Test EV",
            "usable_battery_kwh": 75.0,
            "driving_kwh_per_100_miles": 30.0,
            "max_dc_charge_kw": 150.0,
            "connector": "CCS",
            "minimum_arrival_percent": 10.0,
        },
        "leg_distances_miles": [100, 100],
        "start_percent": 80,
        "effective_stop_powers_kw": [75],
    }


def test_accepts_complete_valid_trip(valid_trip):
    assert validate_trip_request(valid_trip) is None


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "trip",
    ],
)
def test_rejects_non_object_trip(payload):
    with pytest.raises(ValueError, match="JSON object"):
        validate_trip_request(payload)


def test_rejects_unknown_top_level_field(valid_trip):
    payload = deepcopy(valid_trip)
    payload["unexpected"] = True

    with pytest.raises(ValueError, match="unknown trip fields"):
        validate_trip_request(payload)


def test_rejects_missing_vehicle_field(valid_trip):
    payload = deepcopy(valid_trip)
    del payload["vehicle"]["connector"]

    with pytest.raises(ValueError, match="missing vehicle fields"):
        validate_trip_request(payload)


def test_rejects_unknown_vehicle_field(valid_trip):
    payload = deepcopy(valid_trip)
    payload["vehicle"]["advertised_range"] = 300

    with pytest.raises(ValueError, match="unknown vehicle fields"):
        validate_trip_request(payload)


@pytest.mark.parametrize(
    "legs",
    [
        [],
        [50, -1],
        [50, float("nan")],
        "50",
    ],
)
def test_rejects_invalid_legs(valid_trip, legs):
    payload = deepcopy(valid_trip)
    payload["leg_distances_miles"] = legs

    if isinstance(legs, list) and len(legs) != 2:
        payload["effective_stop_powers_kw"] = []

    with pytest.raises(ValueError):
        validate_trip_request(payload)


def test_rejects_wrong_stop_power_count(valid_trip):
    payload = deepcopy(valid_trip)
    payload["effective_stop_powers_kw"] = []

    with pytest.raises(ValueError, match="one value"):
        validate_trip_request(payload)


def test_rejects_invalid_start_percent(valid_trip):
    payload = deepcopy(valid_trip)
    payload["start_percent"] = 101

    with pytest.raises(ValueError, match="start_percent"):
        validate_trip_request(payload)


def test_rejects_boolean_numeric_value(valid_trip):
    payload = deepcopy(valid_trip)
    payload["vehicle"]["usable_battery_kwh"] = True

    with pytest.raises(ValueError, match="usable_battery_kwh"):
        validate_trip_request(payload)