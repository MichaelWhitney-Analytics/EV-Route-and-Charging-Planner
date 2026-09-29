"""Source-backed charging profiles matched to a specific catalog vehicle ID.

An empty registry is valid. Unknown vehicles remain direct-route-only.
"""
import csv
import json
from datetime import date
from math import isfinite
from pathlib import Path
from urllib.parse import urlparse

CONNECTORS = frozenset({"CCS", "NACS", "CHADEMO"})
FIELDS = frozenset({"vehicle_id", "year", "make", "model", "usable_battery_kwh",
                    "max_dc_charge_kw", "connector", "source_urls", "verified_on"})

def load_catalog(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {"vehicle_id", "year", "make", "model"} <= set(reader.fieldnames):
            raise ValueError("Catalog is missing identity columns")
        vehicles = {}
        for row in reader:
            key = int(row["vehicle_id"])
            if key in vehicles:
                raise ValueError("Duplicate catalog vehicle ID")
            vehicles[key] = (int(row["year"]), row["make"].strip(), row["model"].strip())
        return vehicles

def validate_record(record, catalog):
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise ValueError("Profile requires exact identity, specifications and provenance fields")
    key = record["vehicle_id"]
    year = record["year"]
    if isinstance(key, bool) or not isinstance(key, int) or key not in catalog:
        raise ValueError("Unknown or invalid vehicle_id")
    if isinstance(year, bool) or not isinstance(year, int):
        raise ValueError("Invalid model year")
    identity = (year, record["make"], record["model"])
    if identity != catalog[key]:
        raise ValueError("Model year, make or model does not match catalog vehicle ID")
    for field in ("usable_battery_kwh", "max_dc_charge_kw"):
        value = record[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
            raise ValueError(f"{field} must be a finite positive number")
    if record["connector"] not in CONNECTORS:
        raise ValueError("Connector is unknown or unsupported; do not guess")
    sources = record["source_urls"]
    required = {"usable_battery_kwh", "max_dc_charge_kw", "connector"}
    if not isinstance(sources, dict) or set(sources) != required:
        raise ValueError("Each charging specification needs a source URL")
    for field, url in sources.items():
        if not isinstance(url, str) or not url.startswith("https://") or not urlparse(url).hostname:
            raise ValueError(f"{field} needs an HTTPS source URL")
    try:
        verified = date.fromisoformat(record["verified_on"])
    except (ValueError, TypeError):
        raise ValueError("verified_on must be a real ISO calendar date") from None
    if verified > date.today():
        raise ValueError("verified_on cannot be in the future")
    return record

def load_profiles(path, catalog):
    records = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(records, list):
        raise ValueError("Profile registry must be a list")
    profiles = {}
    for item in records:
        record = validate_record(item, catalog)
        key = record["vehicle_id"]
        if key in profiles:
            raise ValueError("Duplicate verified profile ID")
        profiles[key] = record
    return profiles

def coverage(catalog, profiles):
    return {"catalog_vehicle_count": len(catalog),
            "source_backed_profile_count": len(profiles),
            "direct_route_only_count": len(catalog) - len(profiles),
            "status": "No charging claim for entries without a complete, sourced profile. Field-specific source URLs are recorded but their claims are not authenticated by this module. Charger access and compatibility remain unverified."}

def main():
    root = Path(__file__).resolve().parents[2]
    catalog = load_catalog(root / "data/processed/vehicle_catalog.csv")
    profiles = load_profiles(root / "data/processed/verified_vehicle_profiles.json", catalog)
    result = coverage(catalog, profiles)
    output = root / "output/vehicle_profile_coverage.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
