# Methodology

## Purpose

The model demonstrates how an energy manager could compare transparent
load-flexibility strategies before committing to control-system integration.
It is designed for explainability and reproducibility, not production dispatch.

## Synthetic input model

Three fictional sites receive deterministic 15-minute load profiles for 21
days. Load varies by shift pattern, weekday, process family, temperature and a
small seeded disturbance. Price and carbon signals share realistic qualitative
features—morning/evening pressure and lower midday values—but are not copied
from a market or grid operator.

## Flexibility boundary

Each interval is decomposed into:

```text
baseline load = inflexible load + flexible load
```

Only the flexible portion can move. Redistribution is performed separately for
each plant-day, so the model cannot move production energy between days or
sites.

The flexible portion in each interval is bounded to 45%-165% of its baseline
value. A scenario-specific peak cap prevents the optimizer from creating an
artificial new demand spike.

## Scenario objectives

| Scenario | Price weight | Carbon weight | Peak weight |
|---|---:|---:|---:|
| Cost First | 0.72 | 0.08 | 0.20 |
| Carbon First | 0.08 | 0.72 | 0.20 |
| Balanced | 0.45 | 0.30 | 0.25 |

The Baseline scenario performs no redistribution. For the other scenarios,
lower-scoring intervals receive a larger share of the daily flexible energy,
subject to the bounds and peak cap.

## Calculations

Interval energy cost:

```text
optimized_load_kw × 0.25 h ÷ 1,000 × price_eur_mwh
```

Interval operational carbon:

```text
optimized_load_kw × 0.25 h × carbon_g_kwh ÷ 1,000
```

Annualized cost combines the 21-day energy-cost sample scaled to 365 days with
twelve modeled monthly demand charges at €10/kW.

## Limitations

- Synthetic signals are useful for demonstrating method, not estimating a real
  business case.
- Production output is represented by daily energy conservation, not a
  machine-level schedule.
- Start-up cost, minimum run time, maintenance, labor and material-flow
  constraints are outside scope.
- Price and carbon forecasts are treated as known.
- The model does not control physical equipment.
- Reported emissions cover purchased-electricity operations only.

## Production extension

A deployable version would add approved process windows, live forecasts,
mixed-integer scheduling, uncertainty bands, equipment telemetry, tariff
contracts, operator overrides, audit logging and safety validation.
