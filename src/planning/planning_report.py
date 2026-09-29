"""Human-readable, uncertainty-aware display of a limited EV planning summary."""


def _clean(value: object) -> str:
    """Keep untrusted station labels to one terminal line."""
    text = " ".join(str(value if value is not None else "Unknown").split())
    return text[:100] + ("..." if len(text) > 100 else "")


def _station_line(candidate: dict, label: str) -> str:
    station = candidate["station"]
    name = _clean(station.get("name") or "Unnamed site")
    parts = [station.get("address"), station.get("city"), station.get("state")]
    location = ", ".join(_clean(part) for part in parts if part)
    label_text = f"{name} ({location})" if location else name
    arrival = candidate.get("arrival_estimate", {}).get("estimated_arrival_percent")
    arrival_text = f"; estimated arrival {arrival:.1f}%" if isinstance(arrival, (int, float)) else ""
    charge = candidate.get("charge_for_next_leg")
    added = charge.get("energy_to_add_kwh") if isinstance(charge, dict) else None
    energy_text = f"; estimated energy to add {added:.1f} kWh" if isinstance(added, (int, float)) else ""
    return f"- {label_text} [ID: {_clean(station.get('id'))}]: {label}{arrival_text}{energy_text}"


def format_planning_report(summary: dict) -> str:
    """Render counts and every assessed candidate without claiming recommendations."""
    groups = summary["categories"]
    lines = [
        "EV ROUTE AND CHARGING CHECK",
        "Exploratory estimate - not a charger reservation or a trip guarantee.",
        f"Vehicle: {_clean(summary['vehicle_name'])} | Starting charge: {summary['start_percent']:.1f}%",
        f"Direct driving route: {summary['route_distance_miles']:.1f} miles",
        f"Station records: {summary['discovered_record_count']} found; {summary['reported_connector_match_record_count']} reported connector matches; {summary['distinct_reported_address_count']} distinct reported addresses.",
        f"Road-detour sites checked: {summary['road_detours_assessed_count']} | Not checked: {summary['not_assessed_count']}",
        "Not checked may include sites beyond the check limit or sites without usable coordinates.",
        "",
        "ASSESSED SITES (grouped by outcome, not ranked)",
    ]
    labels = (
        ("no_charging_needed", "No charging needed for the next leg under these assumptions"),
        ("charging_needed_if_usable", "Charging needed for the next leg; charger usability unverified"),
        ("unreachable_with_reserve", "Station not reachable with the configured reserve"),
        ("next_leg_exceeds_full_battery_with_reserve", "Next leg exceeds a full battery with the configured reserve"),
    )
    count = 0
    for key, label in labels:
        for candidate in groups[key]:
            lines.append(_station_line(candidate, label))
            count += 1
    if not count:
        lines.append("No candidate sites received an energy assessment.")
    lines.extend(("", "LIMITATIONS", summary["disclaimer"]))
    return "\n".join(lines)