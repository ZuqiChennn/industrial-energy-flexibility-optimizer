"""Build transparent load-shifting scenarios for fictional industrial sites."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "plant_loads_synthetic.csv"
INTERVAL_HOURS = 0.25
DEMAND_CHARGE_EUR_KW_MONTH = 10.0
ANNUALIZATION_DAYS = 365


@dataclass(frozen=True)
class Scenario:
    name: str
    cost_weight: float
    carbon_weight: float
    peak_weight: float
    aggression: float


SCENARIOS = [
    Scenario("Baseline", 0.0, 0.0, 0.0, 0.0),
    Scenario("Cost First", 0.72, 0.08, 0.20, 2.2),
    Scenario("Carbon First", 0.08, 0.72, 0.20, 2.2),
    Scenario("Balanced", 0.45, 0.30, 0.25, 2.0),
]


def _normalize(values: np.ndarray) -> np.ndarray:
    low = float(np.min(values))
    high = float(np.max(values))
    if np.isclose(low, high):
        return np.zeros_like(values, dtype=float)
    return (values - low) / (high - low)


def _bounded_allocate(
    baseline_flexible_kw: np.ndarray,
    score: np.ndarray,
    aggression: float,
    lower: np.ndarray | None = None,
    upper: np.ndarray | None = None,
) -> np.ndarray:
    """Redistribute flexible load while preserving energy and interval bounds."""

    if aggression == 0:
        return baseline_flexible_kw.copy()

    if lower is None:
        lower = baseline_flexible_kw * 0.45
    if upper is None:
        upper = baseline_flexible_kw * 1.65
    total = float(np.sum(baseline_flexible_kw))
    weights = np.exp(-aggression * _normalize(score))
    allocation = total * weights / weights.sum()
    allocation = np.clip(allocation, lower, upper)

    for _ in range(100):
        difference = total - float(allocation.sum())
        if abs(difference) < 1e-8:
            break
        eligible = allocation < upper - 1e-10 if difference > 0 else allocation > lower + 1e-10
        if not np.any(eligible):
            break
        room = (upper - allocation) if difference > 0 else (allocation - lower)
        basis = weights if difference > 0 else 1 / np.maximum(weights, 1e-12)
        basis = np.where(eligible, basis, 0)
        proposal = abs(difference) * basis / basis.sum()
        step = np.minimum(proposal, room)
        allocation += step if difference > 0 else -step

    correction = total - float(allocation.sum())
    if abs(correction) > 1e-7:
        eligible = np.where(allocation < upper - 1e-8)[0] if correction > 0 else np.where(allocation > lower + 1e-8)[0]
        allocation[eligible[0]] += correction
    return allocation


def optimize(data: pd.DataFrame) -> pd.DataFrame:
    working = data.copy()
    working["timestamp"] = pd.to_datetime(working["timestamp"])
    working["date"] = working["timestamp"].dt.date.astype(str)
    frames: list[pd.DataFrame] = []

    for scenario in SCENARIOS:
        for (_, _), group in working.groupby(["plant_id", "date"], sort=False):
            group = group.copy()
            baseline = group["load_kw"].to_numpy(float)
            flex = baseline * group["flexible_share"].to_numpy(float)
            inflexible = baseline - flex
            score = (
                scenario.cost_weight * _normalize(group["price_eur_mwh"].to_numpy(float))
                + scenario.carbon_weight * _normalize(group["carbon_g_kwh"].to_numpy(float))
                + scenario.peak_weight * _normalize(baseline)
            )
            lower_flex = flex * 0.45
            physical_upper = flex * 1.65
            low_cap = float(np.max(inflexible + lower_flex))
            high_cap = float(np.max(baseline))
            for _ in range(50):
                candidate_cap = (low_cap + high_cap) / 2
                candidate_upper = np.minimum(
                    physical_upper,
                    np.maximum(lower_flex, candidate_cap - inflexible),
                )
                if candidate_upper.sum() >= flex.sum():
                    high_cap = candidate_cap
                else:
                    low_cap = candidate_cap
            minimum_feasible_cap = high_cap
            scenario_cap = float(np.max(baseline)) - scenario.peak_weight * 0.85 * (
                float(np.max(baseline)) - minimum_feasible_cap
            )
            constrained_upper = np.minimum(
                physical_upper,
                np.maximum(lower_flex, scenario_cap - inflexible),
            )
            allocated_flex = _bounded_allocate(
                flex,
                score,
                scenario.aggression,
                lower=lower_flex,
                upper=constrained_upper,
            )
            optimized = inflexible + allocated_flex
            group["scenario"] = scenario.name
            group["optimized_load_kw"] = np.round(optimized, 6)
            group["shifted_kw"] = np.round(optimized - baseline, 6)
            group["interval_cost_eur"] = (
                optimized * INTERVAL_HOURS / 1000 * group["price_eur_mwh"].to_numpy(float)
            )
            group["interval_carbon_kg"] = (
                optimized * INTERVAL_HOURS * group["carbon_g_kwh"].to_numpy(float) / 1000
            )
            frames.append(group)

    return pd.concat(frames, ignore_index=True)


def _summarize_group(group: pd.DataFrame, days: int) -> dict[str, float]:
    energy_cost = float(group["interval_cost_eur"].sum())
    peak_kw = float(group.groupby("plant_id")["optimized_load_kw"].max().sum())
    annual_cost = energy_cost * ANNUALIZATION_DAYS / days + peak_kw * DEMAND_CHARGE_EUR_KW_MONTH * 12
    return {
        "energy_mwh": float((group["optimized_load_kw"] * INTERVAL_HOURS).sum() / 1000),
        "annual_cost_eur": annual_cost,
        "carbon_kg": float(group["interval_carbon_kg"].sum()),
        "peak_kw": peak_kw,
        "flex_shifted_mwh": float((group["shifted_kw"].abs() * INTERVAL_HOURS).sum() / 2000),
    }


def build_summaries(intervals: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    days = intervals["date"].nunique()
    plant_rows: list[dict[str, object]] = []
    for (plant, scenario), group in intervals.groupby(["plant_name", "scenario"], sort=False):
        plant_rows.append({"plant": plant, "scenario": scenario, **_summarize_group(group, days)})

    network_rows: list[dict[str, object]] = []
    for scenario, group in intervals.groupby("scenario", sort=False):
        network_rows.append({"plant": "Network", "scenario": scenario, **_summarize_group(group, days)})

    summary = pd.DataFrame(network_rows + plant_rows)
    baseline = (
        summary[summary["scenario"] == "Baseline"]
        .set_index("plant")[["annual_cost_eur", "carbon_kg", "peak_kw"]]
        .add_prefix("baseline_")
    )
    summary = summary.join(baseline, on="plant")
    summary["cost_savings_eur"] = summary["baseline_annual_cost_eur"] - summary["annual_cost_eur"]
    summary["cost_savings_pct"] = summary["cost_savings_eur"] / summary["baseline_annual_cost_eur"]
    summary["carbon_reduction_pct"] = 1 - summary["carbon_kg"] / summary["baseline_carbon_kg"]
    summary["peak_reduction_pct"] = 1 - summary["peak_kw"] / summary["baseline_peak_kw"]
    summary = summary.round(6)

    network = summary[summary["plant"] == "Network"].reset_index(drop=True)
    plants = summary[summary["plant"] != "Network"].reset_index(drop=True)
    return network, plants


def main() -> None:
    source = pd.read_csv(INPUT, parse_dates=["timestamp"])
    intervals = optimize(source)
    scenario_summary, plant_summary = build_summaries(intervals)
    intervals.to_csv(ROOT / "data" / "interval_scenarios.csv", index=False)
    scenario_summary.to_csv(ROOT / "data" / "scenario_summary.csv", index=False)
    plant_summary.to_csv(ROOT / "data" / "plant_summary.csv", index=False)
    print(
        f"Wrote {len(intervals):,} scenario rows; "
        f"best annual saving €{scenario_summary['cost_savings_eur'].max():,.0f}"
    )


if __name__ == "__main__":
    main()
