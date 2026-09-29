"""Report CSV field coverage without inferring vehicle charging specifications."""
import csv
import json
from pathlib import Path

RELEVANT_TERMS = ("batt", "charge", "connector", "plug", "electric", "range", "come", "id", "year", "make", "model")

def audit_csv(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("CSV has no header")
        columns = [name for name in reader.fieldnames if name and any(term in name.lower() for term in RELEVANT_TERMS)]
        present = {name: 0 for name in columns}
        rows = 0
        for row in reader:
            rows += 1
            for name in columns:
                if row.get(name) is not None and str(row[name]).strip() != "":
                    present[name] += 1
    return {"rows": rows, "relevant_columns_nonempty_counts": present,
            "all_columns": reader.fieldnames}

def audit_sources(raw_path, catalog_path):
    report = {"raw": audit_csv(raw_path), "processed": audit_csv(catalog_path),
              "limitations": "Field names and nonempty counts do not establish accuracy, usable battery capacity, DC charging power, connector compatibility, or reuse rights. No specs are inferred and no vehicle is marked charging-ready."}
    return report

def main():
    root = Path(__file__).resolve().parents[2]
    report = audit_sources(root / "data/raw/fueleconomy_vehicles.csv", root / "data/processed/vehicle_catalog.csv")
    destination = root / "output/vehicle_field_audit.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Vehicle field audit saved to output/vehicle_field_audit.json")
    for name in ("raw", "processed"):
        part = report[name]
        print(f"{name}: {part['rows']} rows; relevant fields: {part['relevant_columns_nonempty_counts']}")
    print(report["limitations"])

if __name__ == "__main__":
    main()
