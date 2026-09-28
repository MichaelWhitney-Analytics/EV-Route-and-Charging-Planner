# Vehicle profile-field audit

Generated: 2026-09-28 20:28 UTC

Source: `data/raw/fueleconomy_vehicles.csv`

## Model-year coverage

The source catalog may include vehicles with model years later than the
calendar year in which this audit runs. A future model year does not by
itself establish whether a vehicle is available to a driver.

| Check | Records |
|---|---:|
| Records matching the electricity-only selection rule | 1,610 |
| Model year 2026 or earlier | 1,437 |
| Model year after 2026 | 173 |
| Missing model year | 0 |

### Most recent model years in the source

| Model year | Records |
|---:|---:|
| 2027 | 173 |
| 2026 | 321 |
| 2025 | 326 |
| 2024 | 266 |
| 2023 | 144 |
| 2022 | 89 |
| 2021 | 51 |
| 2020 | 38 |
| 2019 | 35 |
| 2018 | 24 |

## Potential vehicle-profile fields

The names below matched terms such as battery, charge, connector, range,
electric, or fuel. This is a field-name search, **not** a claim that each
field is suitable for route planning.

| Source column | Nonmissing selected records | Coverage |
|---|---:|---:|
| `charge120` | 1,610 | 100.0% |
| `charge240` | 1,610 | 100.0% |
| `fuelCost08` | 1,610 | 100.0% |
| `fuelCostA08` | 1,610 | 100.0% |
| `fuelType` | 1,610 | 100.0% |
| `fuelType1` | 1,610 | 100.0% |
| `range` | 1,610 | 100.0% |
| `rangeCity` | 1,610 | 100.0% |
| `rangeCityA` | 1,610 | 100.0% |
| `rangeHwy` | 1,610 | 100.0% |
| `rangeHwyA` | 1,610 | 100.0% |
| `tCharger` | 0 | 0.0% |
| `sCharger` | 0 | 0.0% |
| `fuelType2` | 0 | 0.0% |
| `rangeA` | 0 | 0.0% |
| `charge240b` | 1,610 | 100.0% |

## Questions for review

- Is usable battery capacity present, or must we source it separately?
- Is connector compatibility present and specific to model year/variant?
- Is DC fast-charging capability or a charging curve present?
- Which fields describe driving energy versus wall-outlet energy?
