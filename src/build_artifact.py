"""Build the canonical dashboard artifact from reviewed model outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
GENERATED_AT = "2026-07-26T00:00:00Z"


def rounded_records(frame: pd.DataFrame, digits: int = 4) -> list[dict[str, object]]:
    output = frame.copy()
    numeric = output.select_dtypes(include="number").columns
    output[numeric] = output[numeric].round(digits)
    return output.to_dict(orient="records")


def build_datasets() -> dict[str, list[dict[str, object]]]:
    network = pd.read_csv(ROOT / "data" / "scenario_summary.csv")
    plants = pd.read_csv(ROOT / "data" / "plant_summary.csv")
    summary = pd.concat([network, plants], ignore_index=True)
    summary["carbon_t"] = summary["carbon_kg"] / 1000

    intervals = pd.read_csv(ROOT / "data" / "interval_scenarios.csv", parse_dates=["timestamp"])
    intervals["hour"] = intervals["timestamp"].dt.hour

    plant_profile = (
        intervals.groupby(["plant_name", "scenario", "hour"], as_index=False)["optimized_load_kw"]
        .mean()
        .rename(columns={"plant_name": "plant", "optimized_load_kw": "average_load_kw"})
    )
    network_interval = (
        intervals.groupby(["timestamp", "scenario"], as_index=False)
        .agg(optimized_load_kw=("optimized_load_kw", "sum"))
    )
    network_interval["hour"] = network_interval["timestamp"].dt.hour
    network_profile = (
        network_interval.groupby(["scenario", "hour"], as_index=False)["optimized_load_kw"]
        .mean()
        .rename(columns={"optimized_load_kw": "average_load_kw"})
    )
    network_profile["plant"] = "Network"
    profile_all = pd.concat([network_profile, plant_profile], ignore_index=True)

    profile_rows: list[pd.DataFrame] = []
    for selected in ["Cost First", "Carbon First", "Balanced"]:
        subset = profile_all[profile_all["scenario"].isin(["Baseline", selected])].copy()
        subset["selection_scenario"] = selected
        subset["series"] = subset["scenario"].replace({selected: selected})
        profile_rows.append(subset)
    profile = pd.concat(profile_rows, ignore_index=True)

    optimized = intervals[intervals["scenario"] != "Baseline"].copy()
    optimized["absolute_shift_kw"] = optimized["shifted_kw"].abs()
    optimized["direction"] = optimized["shifted_kw"].map(
        lambda value: "Increase / pre-load" if value > 0 else "Reduce / defer"
    )
    plant_actions = (
        optimized.sort_values("absolute_shift_kw", ascending=False)
        .groupby(["plant_name", "scenario"], as_index=False, group_keys=False)
        .head(8)
        .rename(columns={"plant_name": "plant"})
    )

    network_actions = (
        optimized.groupby(["timestamp", "scenario"], as_index=False)
        .agg(
            shifted_kw=("shifted_kw", "sum"),
            price_eur_mwh=("price_eur_mwh", "first"),
            carbon_g_kwh=("carbon_g_kwh", "first"),
        )
    )
    network_actions["absolute_shift_kw"] = network_actions["shifted_kw"].abs()
    network_actions["direction"] = network_actions["shifted_kw"].map(
        lambda value: "Increase / pre-load" if value > 0 else "Reduce / defer"
    )
    network_actions["plant"] = "Network"
    network_actions = (
        network_actions.sort_values("absolute_shift_kw", ascending=False)
        .groupby("scenario", as_index=False, group_keys=False)
        .head(8)
    )
    actions = pd.concat([network_actions, plant_actions], ignore_index=True)
    actions["timestamp"] = pd.to_datetime(actions["timestamp"]).dt.strftime("%d %b %H:%M")
    actions = actions[
        [
            "timestamp",
            "plant",
            "scenario",
            "direction",
            "shifted_kw",
            "absolute_shift_kw",
            "price_eur_mwh",
            "carbon_g_kwh",
        ]
    ]

    kpi_columns = [
        "plant",
        "scenario",
        "cost_savings_eur",
        "cost_savings_pct",
        "carbon_reduction_pct",
        "peak_reduction_pct",
        "flex_shifted_mwh",
    ]
    comparison_columns = [
        "plant",
        "scenario",
        "annual_cost_eur",
        "carbon_t",
        "peak_kw",
        "cost_savings_eur",
    ]
    kpi = summary[kpi_columns].copy()
    plant_order = ["Network", "North Plant", "Central Plant", "South Plant"]
    scenario_order = ["Balanced", "Cost First", "Carbon First", "Baseline"]
    kpi["plant"] = pd.Categorical(kpi["plant"], plant_order, ordered=True)
    kpi["scenario"] = pd.Categorical(kpi["scenario"], scenario_order, ordered=True)
    kpi = kpi.sort_values(["plant", "scenario"]).astype({"plant": str, "scenario": str})
    return {
        "kpi": rounded_records(kpi),
        "comparison": rounded_records(summary[comparison_columns]),
        "tradeoff": rounded_records(summary[comparison_columns]),
        "profile": rounded_records(
            profile[["plant", "selection_scenario", "series", "hour", "average_load_kw"]]
        ),
        "actions": rounded_records(actions),
    }


def source_definitions() -> list[dict[str, object]]:
    return [
        {
            "id": "synthetic_inputs",
            "label": "Synthetic 15-minute plant telemetry",
            "path": "data/plant_loads_synthetic.csv",
            "query": {
                "engine": "python",
                "language": "python",
                "sql": "python src/generate_data.py",
                "description": "Deterministic generation of fictional plant load, price and carbon-intensity inputs.",
                "executed_at": GENERATED_AT,
                "tables_used": ["data/plant_loads_synthetic.csv"],
                "filters": ["21 complete days", "three fictional plants", "15-minute intervals"],
                "metric_definitions": {
                    "load_kw": "Average electrical demand during each 15-minute interval.",
                    "flexible_share": "Share of interval load that may move within the same plant-day.",
                },
            },
        },
        {
            "id": "scenario_model",
            "label": "Reproducible flexibility scenarios",
            "path": "data/scenario_summary.csv",
            "query": {
                "engine": "duckdb",
                "language": "sql",
                "sql": (
                    "SELECT * FROM read_csv_auto('data/scenario_summary.csv') "
                    "UNION ALL BY NAME "
                    "SELECT * FROM read_csv_auto('data/plant_summary.csv')"
                ),
                "description": "Reviewed scenario metrics produced by the bounded Python load-shifting model.",
                "executed_at": GENERATED_AT,
                "tables_used": [
                    "data/plant_loads_synthetic.csv",
                    "data/interval_scenarios.csv",
                    "data/scenario_summary.csv",
                    "data/plant_summary.csv",
                ],
                "filters": [
                    "daily energy conserved",
                    "45%-165% bounds on the flexible portion",
                    "no production volume or service-level change modeled",
                ],
                "metric_definitions": {
                    "annual_cost_eur": "21-day energy cost annualized to 365 days plus twelve monthly demand charges at €10/kW.",
                    "cost_savings_eur": "Baseline annual cost less scenario annual cost.",
                    "carbon_reduction_pct": "One minus scenario carbon divided by baseline carbon for the same period.",
                    "peak_reduction_pct": "One minus scenario peak demand divided by baseline peak demand.",
                    "flex_shifted_mwh": "Half the absolute interval load movement, avoiding double counting energy moved out and back in.",
                },
            },
        },
    ]


def build_artifact() -> dict[str, object]:
    datasets = build_datasets()
    sources = source_definitions()
    return {
        "surface": "dashboard",
        "manifest": {
            "version": 1,
            "surface": "dashboard",
            "title": "Industrial Energy Flexibility Optimizer",
            "description": "Decision dashboard for cost, carbon and peak-load trade-offs across a fictional German manufacturing network.",
            "generatedAt": GENERATED_AT,
            "filters": [
                {
                    "id": "plant",
                    "label": "Plant",
                    "dataset": "kpi",
                    "field": "plant",
                    "defaultValue": "Network",
                    "includeAll": False,
                    "targets": [
                        {"dataset": "comparison", "field": "plant"},
                        {"dataset": "tradeoff", "field": "plant"},
                        {"dataset": "profile", "field": "plant"},
                        {"dataset": "actions", "field": "plant"},
                    ],
                },
                {
                    "id": "scenario",
                    "label": "Operating strategy",
                    "dataset": "kpi",
                    "field": "scenario",
                    "defaultValue": "Balanced",
                    "includeAll": False,
                    "targets": [
                        {"dataset": "profile", "field": "selection_scenario"},
                        {"dataset": "actions", "field": "scenario"},
                    ],
                },
            ],
            "cards": [
                {
                    "id": "cost_saving",
                    "description": "Annualized energy and peak-demand cost improvement against the unchanged-load baseline.",
                    "dataset": "kpi",
                    "sourceId": "scenario_model",
                    "metrics": [
                        {"label": "Annualized cost saving", "field": "cost_savings_eur", "format": "currency"},
                        {"label": "Relative saving", "field": "cost_savings_pct", "format": "percent", "signed": True},
                    ],
                },
                {
                    "id": "peak_reduction",
                    "description": "Reduction in maximum coincident electrical demand for the selected plant or network.",
                    "dataset": "kpi",
                    "sourceId": "scenario_model",
                    "metrics": [
                        {"label": "Peak-load reduction", "field": "peak_reduction_pct", "format": "percent"}
                    ],
                },
                {
                    "id": "carbon_reduction",
                    "description": "Operational electricity emissions avoided through time shifting only.",
                    "dataset": "kpi",
                    "sourceId": "scenario_model",
                    "metrics": [
                        {"label": "Carbon reduction", "field": "carbon_reduction_pct", "format": "percent"}
                    ],
                },
                {
                    "id": "flex_volume",
                    "description": "Energy moved to another interval while daily site energy remains unchanged.",
                    "dataset": "kpi",
                    "sourceId": "scenario_model",
                    "metrics": [
                        {"label": "Flexible energy shifted", "field": "flex_shifted_mwh", "format": "number", "unit": "MWh"}
                    ],
                },
            ],
            "charts": [
                {
                    "id": "cost_comparison",
                    "title": "Annualized electricity cost by strategy",
                    "subtitle": "Includes interval energy prices and a transparent monthly peak-demand charge.",
                    "type": "bar",
                    "dataset": "comparison",
                    "sourceId": "scenario_model",
                    "encodings": {
                        "x": {"field": "scenario", "type": "nominal", "label": "Strategy"},
                        "y": {"field": "annual_cost_eur", "type": "quantitative", "label": "Annual cost", "format": "currency"},
                    },
                    "yAxisTitle": "Annual cost",
                    "valueFormat": "currency",
                    "layout": "full",
                },
                {
                    "id": "cost_carbon_tradeoff",
                    "title": "Cost and operational-carbon trade-off",
                    "subtitle": "Each point is a strategy for the selected plant or full network.",
                    "type": "scatter",
                    "dataset": "tradeoff",
                    "sourceId": "scenario_model",
                    "encodings": {
                        "x": {"field": "annual_cost_eur", "type": "quantitative", "label": "Annual cost", "format": "currency"},
                        "y": {"field": "carbon_t", "type": "quantitative", "label": "Carbon", "format": "number"},
                        "color": {"field": "scenario", "type": "nominal", "label": "Strategy"},
                    },
                    "xAxisTitle": "Annual cost",
                    "yAxisTitle": "Operational carbon (t)",
                    "layout": "full",
                },
                {
                    "id": "load_profile",
                    "title": "Average 24-hour load profile",
                    "subtitle": "Baseline compared with the selected operating strategy.",
                    "type": "line",
                    "dataset": "profile",
                    "sourceId": "scenario_model",
                    "encodings": {
                        "x": {"field": "hour", "type": "ordinal", "label": "Hour of day"},
                        "y": {"field": "average_load_kw", "type": "quantitative", "label": "Average load", "format": "number"},
                        "color": {"field": "series", "type": "nominal", "label": "Series"},
                    },
                    "yAxisTitle": "Average load (kW)",
                    "layout": "full",
                },
            ],
            "tables": [
                {
                    "id": "largest_actions",
                    "title": "Largest flexibility actions",
                    "subtitle": "Intervals with the greatest modeled increase or reduction for the selected strategy.",
                    "dataset": "actions",
                    "sourceId": "scenario_model",
                    "defaultSort": {"field": "absolute_shift_kw", "direction": "desc"},
                    "density": "dense",
                    "layout": "full",
                    "columns": [
                        {"field": "timestamp", "label": "Interval", "type": "text"},
                        {"field": "plant", "label": "Plant", "type": "text"},
                        {"field": "direction", "label": "Action", "type": "text"},
                        {"field": "shifted_kw", "label": "Load change", "format": "number", "unit": "kW", "movement": True},
                        {"field": "price_eur_mwh", "label": "Energy price", "format": "currency", "unit": "/MWh"},
                        {"field": "carbon_g_kwh", "label": "Grid carbon", "format": "number", "unit": "g/kWh"},
                        {"field": "absolute_shift_kw", "label": "Absolute change", "format": "number", "unit": "kW"},
                    ],
                }
            ],
            "sources": sources,
            "blocks": [
                {
                    "id": "intro",
                    "type": "markdown",
                    "body": "## Decision view\n\nCompare transparent operating strategies for a fictional manufacturing network. All inputs are deterministic and synthetic; no company or team-project data are used.",
                },
                {"id": "metrics", "type": "metric-strip", "cardIds": ["cost_saving", "peak_reduction", "carbon_reduction", "flex_volume"]},
                {"id": "cost", "type": "chart", "chartId": "cost_comparison", "layout": "full"},
                {"id": "tradeoff", "type": "chart", "chartId": "cost_carbon_tradeoff", "layout": "full"},
                {"id": "profile", "type": "chart", "chartId": "load_profile", "layout": "full"},
                {"id": "actions_table", "type": "table", "tableId": "largest_actions", "layout": "full"},
                {
                    "id": "method",
                    "type": "markdown",
                    "body": "## Method and guardrails\n\nFlexible load moves only within the same plant-day. Daily energy is conserved, the non-flexible portion never moves, and each interval has explicit lower and upper bounds. The scenarios are decision-support examples—not production schedules or forecasts.",
                },
            ],
        },
        "snapshot": {
            "version": 1,
            "generatedAt": GENERATED_AT,
            "status": "ready",
            "datasets": datasets,
        },
        "sources": sources,
        "package_info": {
            "root": "industrial-energy-flexibility-optimizer",
            "manifestPath": "dashboard/artifact.json",
            "snapshotPath": "dashboard/artifact.json",
        },
    }


def main() -> None:
    output = ROOT / "dashboard" / "artifact.json"
    output.write_text(json.dumps(build_artifact(), indent=2), encoding="utf-8")
    print(f"Wrote {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
