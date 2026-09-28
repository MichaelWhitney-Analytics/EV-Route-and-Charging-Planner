# BEV vehicle-data audit

Generated: 2026-09-28 20:24 UTC

## Source

- Dataset: [FuelEconomy.gov vehicle data](https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip)
- Local raw snapshot: `data/raw/fueleconomy_vehicles.csv`

## BEV selection rule

A record is included when:

- `fuelType1 = Electricity`
- `fuelType2` is blank or missing

This is an initial electricity-only classification rule. It should be
validated against source records before being treated as a complete
classification of every BEV and plug-in hybrid.

## Coverage

| Check | Result |
|---|---:|
| Total vehicle records downloaded | 50,409 |
| Records matching BEV selection rule | 1,610 |
| Distinct vehicle IDs | 1,610 |
| Model years represented | 1998–2027 |
| Selected records with positive `combE` | 1,610 |
| Selected records without positive `combE` | 0 |
| Missing vehicle IDs | 0 |
| Duplicate vehicle IDs | 0 |

## Sample selected records

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

This audit establishes a reproducible starting catalog. It does not make
every record trip-ready. The source may include future model-year vehicles,
and the planner still needs usable battery capacity, connector
compatibility, DC fast-charging behavior, and station data.

`combE` is a published electricity-use measure and can include charging
losses. The planner must document how it uses this value rather than
silently treating it as direct battery energy consumption.
