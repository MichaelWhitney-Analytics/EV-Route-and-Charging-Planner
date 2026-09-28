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