# Validation report

## Overall assessment: Ready to share as a synthetic portfolio demonstration

The project answers its stated question: how transparent within-day load
shifting changes modeled cost, operational carbon and peak demand for a
fictional manufacturing network.

## Methodology review

- Population: three fictional plants over 21 complete days.
- Grain: one plant and one 15-minute interval; scenarios add a fourth key.
- Baseline: identical load, price and carbon inputs for every comparison.
- Optimization boundary: only the declared flexible portion moves.
- Comparison window: identical for all strategies.
- Claims: described as model outputs, not causal effects or company forecasts.

## Calculation spot-checks

- Source grain: verified at 6,048 unique plant-interval rows.
- Scenario grain: verified at 24,192 unique plant-interval-scenario rows.
- Daily energy conservation: verified within 0.0001 kWh.
- Baseline reproduction: exact within floating-point tolerance.
- Non-negative load and flexibility bounds: verified for every row.
- Balanced cost, carbon and peak direction: all improve against Baseline.
- Missing summary values: none.

## Presentation review

- KPI units and denominators are defined beside the model documentation.
- Cost comparison uses a bar chart; the trade-off uses a scatter plot; the
  daily pattern uses a line chart.
- All charts use compatible units without dual axes or causal language.
- Every quantitative dashboard element points to the reviewed scenario-output
  source.

## Caveats required for interpretation

- All inputs are deterministic synthetic data.
- The 21-day sample is annualized for comparability.
- No production schedule, safety constraint or real tariff contract is modeled.
- The dashboard is decision support, not an automatic dispatch recommendation.
