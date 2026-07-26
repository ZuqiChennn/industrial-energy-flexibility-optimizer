from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.generate_data import DAYS, INTERVAL_MINUTES, PLANTS, generate
from src.optimize import INTERVAL_HOURS, build_summaries, optimize


class FlexibilityModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = generate()
        cls.intervals = optimize(cls.source)
        cls.network, cls.plants = build_summaries(cls.intervals)

    def test_expected_source_grain(self) -> None:
        expected = len(PLANTS) * DAYS * 24 * 60 // INTERVAL_MINUTES
        self.assertEqual(len(self.source), expected)
        self.assertFalse(self.source.duplicated(["plant_id", "timestamp"]).any())

    def test_daily_energy_is_conserved(self) -> None:
        grouped = self.intervals.groupby(["plant_id", "date", "scenario"])
        baseline_kwh = grouped["load_kw"].sum() * INTERVAL_HOURS
        optimized_kwh = grouped["optimized_load_kw"].sum() * INTERVAL_HOURS
        np.testing.assert_allclose(baseline_kwh, optimized_kwh, rtol=0, atol=1e-4)

    def test_load_is_non_negative_and_bounded(self) -> None:
        self.assertTrue((self.intervals["optimized_load_kw"] >= 0).all())
        inflexible = self.intervals["load_kw"] * (1 - self.intervals["flexible_share"])
        lower = inflexible + self.intervals["load_kw"] * self.intervals["flexible_share"] * 0.45
        upper = inflexible + self.intervals["load_kw"] * self.intervals["flexible_share"] * 1.65
        self.assertTrue((self.intervals["optimized_load_kw"] >= lower - 1e-5).all())
        self.assertTrue((self.intervals["optimized_load_kw"] <= upper + 1e-5).all())

    def test_baseline_is_unchanged(self) -> None:
        baseline = self.intervals[self.intervals["scenario"] == "Baseline"]
        np.testing.assert_allclose(baseline["optimized_load_kw"], baseline["load_kw"], atol=1e-8)

    def test_balanced_scenario_improves_cost_and_carbon(self) -> None:
        balanced = self.network.set_index("scenario").loc["Balanced"]
        self.assertGreater(balanced["cost_savings_eur"], 0)
        self.assertGreater(balanced["carbon_reduction_pct"], 0)
        self.assertGreater(balanced["peak_reduction_pct"], 0)

    def test_summary_has_no_missing_values(self) -> None:
        self.assertFalse(pd.concat([self.network, self.plants]).isna().any().any())


if __name__ == "__main__":
    unittest.main()
