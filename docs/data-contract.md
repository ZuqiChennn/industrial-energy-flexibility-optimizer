# Data contract

## Source table: `plant_loads_synthetic.csv`

Grain: one fictional plant and one 15-minute interval.

| Field | Type | Unit | Definition |
|---|---|---:|---|
| `timestamp` | datetime | Europe/Berlin local time | Interval start |
| `plant_id` | string | — | Stable fictional site identifier |
| `plant_name` | string | — | Reader-facing fictional site name |
| `process` | string | — | Aggregated process family |
| `load_kw` | float | kW | Average electrical demand in the interval |
| `flexible_share` | float | ratio | Share eligible to move within the plant-day |
| `price_eur_mwh` | float | €/MWh | Synthetic interval electricity price |
| `carbon_g_kwh` | float | g/kWh | Synthetic grid carbon intensity |
| `temperature_c` | float | °C | Synthetic ambient temperature |
| `production_index` | float | index | Synthetic relative production activity |

Primary key: (`plant_id`, `timestamp`).

## Scenario table: `interval_scenarios.csv`

Grain: one fictional plant, 15-minute interval and operating scenario.

The table preserves every input field and adds:

| Field | Unit | Definition |
|---|---:|---|
| `scenario` | — | Baseline, Cost First, Carbon First or Balanced |
| `optimized_load_kw` | kW | Load after bounded daily redistribution |
| `shifted_kw` | kW | Optimized load minus baseline load |
| `interval_cost_eur` | € | Interval energy cost |
| `interval_carbon_kg` | kgCO₂e | Interval operational electricity emissions |

Primary key: (`plant_id`, `timestamp`, `scenario`).

## Required validation rules

- Exactly three fictional plants.
- Exactly 21 complete days per plant.
- No duplicate primary keys.
- No missing values in required fields.
- Daily energy is conserved for every plant and scenario.
- Optimized load is non-negative.
- Flexible load remains between 45% and 165% of its baseline interval value.
- The Baseline scenario exactly reproduces input load.
- Network summary equals the sum of plant-level energy and emissions.
