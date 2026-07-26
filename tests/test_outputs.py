from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


class GeneratedOutputContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = pd.read_csv(ROOT / "data" / "plant_loads_synthetic.csv")
        cls.intervals = pd.read_csv(ROOT / "data" / "interval_scenarios.csv")
        cls.network = pd.read_csv(ROOT / "data" / "scenario_summary.csv")
        cls.plants = pd.read_csv(ROOT / "data" / "plant_summary.csv")
        cls.artifact = json.loads((ROOT / "dashboard" / "artifact.json").read_text())

    def test_output_row_counts_and_keys(self) -> None:
        self.assertEqual(len(self.source), 6048)
        self.assertEqual(len(self.intervals), 24192)
        self.assertEqual(len(self.network), 4)
        self.assertEqual(len(self.plants), 12)
        self.assertFalse(self.source.duplicated(["plant_id", "timestamp"]).any())
        self.assertFalse(
            self.intervals.duplicated(["plant_id", "timestamp", "scenario"]).any()
        )

    def test_outputs_are_complete(self) -> None:
        for frame in [self.source, self.intervals, self.network, self.plants]:
            self.assertFalse(frame.isna().any().any())

    def test_headline_metrics_remain_in_expected_ranges(self) -> None:
        balanced = self.network.set_index("scenario").loc["Balanced"]
        self.assertGreater(balanced["cost_savings_eur"], 100_000)
        self.assertLess(balanced["cost_savings_eur"], 150_000)
        self.assertGreater(balanced["carbon_reduction_pct"], 0.005)
        self.assertLess(balanced["carbon_reduction_pct"], 0.02)
        self.assertGreater(balanced["peak_reduction_pct"], 0.015)
        self.assertLess(balanced["peak_reduction_pct"], 0.04)

    def test_dashboard_snapshot_is_ready(self) -> None:
        self.assertEqual(self.artifact["surface"], "dashboard")
        self.assertEqual(self.artifact["snapshot"]["status"], "ready")
        self.assertEqual(set(self.artifact["snapshot"]["datasets"]), {
            "kpi",
            "comparison",
            "tradeoff",
            "profile",
            "actions",
        })


if __name__ == "__main__":
    unittest.main()
