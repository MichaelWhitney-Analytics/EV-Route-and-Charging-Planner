"""Choose a few energy-feasible sites from an ordered, premeasured road graph.

No live station discovery, route lookup, charger verification, or timing model.
"""

from math import isfinite

from src.planning.ordered_itinerary import build_ordered_itinerary
from src.planning.route_energy import estimate_route_energy
from src.planning.vehicle_profile import VehicleProfile


def select_fewest_stops(
    profile: VehicleProfile,
    start_percent: float,
    origin: str,
    sites: list[str],
    destination: str,
    road_miles: list[list],
    *,
    destination_profile: VehicleProfile | None = None,
) -> dict:
    """Choose fewest supplied sites, then farther-forward stops, then miles.

    Node order is origin, ordered station sites, destination. ``road_miles[i][j]``
    is a measured forward road distance, or ``None`` when the edge was not
    measured. The standard graph supplies up to eight sites; a bounded recovery
    graph may supply up to 16. Charging at selected sites remains unverified.
    """
    if not isinstance(profile, VehicleProfile):
        raise TypeError("profile must be a VehicleProfile")

    if destination_profile is None:
        destination_profile = profile

    if not isinstance(destination_profile, VehicleProfile):
        raise TypeError("destination_profile must be a VehicleProfile")

    if (
        isinstance(start_percent, bool)
        or not isinstance(start_percent, (int, float))
        or not isfinite(start_percent)
        or not 0 <= start_percent <= 100
    ):
        raise ValueError(
            "start_percent must be a finite percentage from 0 to 100"
        )

    if (
        not isinstance(origin, str)
        or not origin.strip()
        or not isinstance(destination, str)
        or not destination.strip()
    ):
        raise ValueError("origin and destination must be named")

    if (
        not isinstance(sites, list)
        or len(sites) > 16
        or any(
            not isinstance(site, str) or not site.strip()
            for site in sites
        )
    ):
        raise ValueError(
            "sites must be up to 16 named places in travel order"
        )

    names = (
        [origin.strip()]
        + [site.strip() for site in sites]
        + [destination.strip()]
    )

    size = len(names)

    if (
        not isinstance(road_miles, list)
        or len(road_miles) != size
        or any(
            not isinstance(row, list) or len(row) != size
            for row in road_miles
        )
    ):
        raise ValueError(
            "road_miles must be a square matrix for every node"
        )

    for i, row in enumerate(road_miles):
        for j, value in enumerate(row):
            if value is None:
                continue

            if (
                j <= i
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value < 0
            ):
                raise ValueError(
                    "only finite, nonnegative forward road distances or None "
                    "are allowed"
                )

    # Costs are:
    # (charging-site count, negative site indexes, road miles, ordered path).
    #
    # Fewer charging stops win first. For equal stop counts, farther-forward
    # stations win; measured road mileage then breaks remaining ties.
    best = {0: (0, (), 0.0, [0])}

    for j in range(1, size):
        choices = []

        for i in range(j):
            if i not in best or road_miles[i][j] is None:
                continue

            departure = start_percent if i == 0 else 100.0
            leg_profile = (
                destination_profile
                if j == size - 1
                else profile
            )

            estimate = estimate_route_energy(
                leg_profile,
                road_miles[i][j],
                departure,
            )

            if estimate.reachable_without_charging:
                previous = best[i]

                choices.append(
                    (
                        previous[0] + (j != size - 1),
                        previous[1]
                        + ((-j,) if j != size - 1 else ()),
                        previous[2] + road_miles[i][j],
                        previous[3] + [j],
                    )
                )

        if choices:
            best[j] = min(choices)

    if size - 1 not in best:
        return {
            "status": "no_feasible_path_in_supplied_graph",
            "itinerary": None,
            "note": (
                "No checked sequence preserves reserve; unmeasured edges and "
                "unverified chargers may change the outcome."
            ),
        }

    path = best[size - 1][3]

    legs = [
        {
            "name": names[j],
            "kind": "destination" if j == size - 1 else "site",
            "distance_miles": road_miles[i][j],
        }
        for i, j in zip(path, path[1:])
    ]

    itinerary = build_ordered_itinerary(
        profile,
        start_percent,
        origin,
        legs,
        destination_profile=destination_profile,
    )

    charging_sites = [
        item
        for item in itinerary["timeline"]
        if item["kind"] == "site"
        and item["charge_needed_for_next_leg"]
    ]

    return {
        "status": "conditional_energy_path",
        "selected_site_names": [
            item["name"] for item in charging_sites
        ],
        "site_count": len(charging_sites),
        "itinerary": itinerary,
        "note": (
            "Fewest supplied sites, then farther-forward stops, then shorter "
            "measured road mileage; not fastest, optimal charging, or a "
            "verified usable itinerary. Selected-site access and ability to "
            "charge remain unverified."
        ),
    }