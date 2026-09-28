# BEV vehicle-data audit

Generated: 2026-09-28 20:09 UTC

## Source

- Dataset: [FuelEconomy.gov vehicle data](https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip)
- Local raw snapshot: `data/raw/fueleconomy_vehicles.csv`

## BEV selection rule

A record is treated as a battery-electric vehicle when:

- `fuelType1 = Electricity`
- `fuelType2` is blank or missing

This rule intentionally excludes plug-in hybrids, which have a second fuel
type because they can use another energy source in addition to electricity.

## Coverage

| Check | Result |
|---|---:|
| Total vehicle records downloaded | 50,409 |
| BEV records matching selection rule | 1,610 |
| Distinct vehicle IDs | 1,610 |
| Model years represented | 1998–2027 |
| BEV records with positive `combE` | 1,610 |
| BEV records without positive `combE` | 0 |
| Missing vehicle IDs | 0 |
| Duplicate vehicle IDs | 0 |

## Sample BEV records

| Year | Make | Model | Combined electricity use (kWh/100 mi) |
|---:|---|---|---:|
| 2027 | Audi | A6 e-tron | 30.341 |
| 2027 | Audi | A6 e-tron quattro | 31.9817 |
| 2027 | Audi | A6 e-tron quattro ultra | 28.7437 |
| 2027 | Audi | A6 e-tron ultra | 26.463 |
| 2027 | Audi | Q6 Sportback e-tron quattro | 32.5073 |
| 2027 | Audi | Q6 e-tron SB quattro (20 inch Tires) | 35.0867 |
| 2027 | Audi | Q6 e-tron quattro (19 inch Tires) | 32.5073 |
| 2027 | Audi | Q6 e-tron quattro (20 inch Tires) | 35.0867 |
| 2027 | Audi | RS e-tron GT Performance | 40.1788 |
| 2027 | Audi | S e-tron GT (20 inch wheels) | 37.6493 |

## Interpretation and limitations

This audit establishes a reproducible starting catalog for U.S. BEVs. It does
not yet make every record trip-ready. The route planner still needs usable
battery capacity, connector compatibility, DC fast-charging behavior, and
station availability data.

`combE` is a published electricity-use measure and can include charging
losses. The planner will document how this value is transformed, rather than
treating it as direct battery energy consumption without adjustment.
