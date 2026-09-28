"""Group candidate station records that report the same street address."""


def group_station_sites(stations: list[dict]) -> list[dict]:
    """Group by complete address, otherwise keep each station ID separate.

    This does not merge chargers by physical proximity alone or verify access.
    """
    if not isinstance(stations, list):
        raise ValueError("stations must be a list")
    sites = {}
    for station in stations:
        if not isinstance(station, dict):
            raise ValueError("each station must be an object")
        address = station.get("address")
        city = station.get("city")
        state = station.get("state")
        if all(isinstance(item, str) and item.strip() for item in (address, city, state)):
            key = tuple(item.strip().casefold() for item in (address, city, state))
        else:
            key = ("record", len(sites))
        if key not in sites:
            sites[key] = {"representative": station, "station_ids": []}
        sites[key]["station_ids"].append(station.get("id"))
    return list(sites.values())