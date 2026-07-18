import unittest

import pandas as pd

from modules.feature_engineering.build_nasa_health_features import (
    build_features_for_cell,
    build_labels_for_cell,
    build_multi_threshold_labels_for_cell,
)


class HealthFeatureTests(unittest.TestCase):
    @staticmethod
    def discharge_summary(capacities: list[float]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "dataset": ["nasa"] * len(capacities),
                "battery_type": ["li_ion"] * len(capacities),
                "cell_id": ["BTEST"] * len(capacities),
                "cycle_index": [2, 4, 6, 8][: len(capacities)],
                "cycle_type": ["discharge"] * len(capacities),
                "cycle_number_within_type": list(range(1, len(capacities) + 1)),
                "start_time": [""] * len(capacities),
                "capacity_ah": capacities,
                "duration_s": [100.0] * len(capacities),
            }
        )

    def test_observed_eol_generates_rul(self) -> None:
        labels, summary = build_labels_for_cell(
            self.discharge_summary([2.0, 1.8, 1.39, 1.35]),
            threshold=0.70,
            initial_capacity_window=1,
            consecutive_cycles=1,
        )

        self.assertTrue(summary.eol_observed)
        self.assertEqual(summary.eol_discharge_cycle, 3)
        self.assertEqual(labels["rul_cycles"].tolist(), [2, 1, 0, 0])
        self.assertTrue(labels["is_eol_or_after"].iloc[2])
        self.assertTrue(labels["event_observed"].all())
        self.assertEqual(labels["duration_cycles"].tolist(), [2, 1, 0, 0])

    def test_unobserved_eol_is_censored(self) -> None:
        labels, summary = build_labels_for_cell(
            self.discharge_summary([2.0, 1.9, 1.8]),
            threshold=0.70,
            initial_capacity_window=1,
            consecutive_cycles=1,
        )

        self.assertFalse(summary.eol_observed)
        self.assertTrue(labels["rul_cycles"].isna().all())
        self.assertTrue(labels["rul_is_censored"].all())
        self.assertEqual(labels["rul_lower_bound_cycles"].tolist(), [2, 1, 0])
        self.assertFalse(labels["event_observed"].any())
        self.assertEqual(labels["duration_cycles"].tolist(), [2, 1, 0])

    def test_multi_threshold_labels_keep_endpoint_versions(self) -> None:
        labels, summary = build_multi_threshold_labels_for_cell(
            self.discharge_summary([2.0, 1.7, 1.48, 1.35]),
            thresholds=[0.70, 0.75, 0.80],
            initial_capacity_window=1,
            consecutive_cycles=1,
        )

        self.assertEqual(
            sorted(labels["label_key"].unique().tolist()),
            ["capacity_eol_70", "capacity_eol_75", "capacity_eol_80"],
        )
        eol_by_threshold = dict(
            zip(summary["eol_threshold"], summary["eol_discharge_cycle"])
        )
        self.assertEqual(eol_by_threshold[0.8], 3)
        self.assertEqual(eol_by_threshold[0.7], 4)

    def test_feature_table_adds_trailing_capacity_features(self) -> None:
        cycle_summary = self.discharge_summary([2.0, 1.9, 1.8])
        labels, _ = build_labels_for_cell(cycle_summary, 0.70, 1, 1)
        features = build_features_for_cell(cycle_summary, labels)

        self.assertIn("capacity_rolling_mean_5_ah", features.columns)
        self.assertIn("capacity_slope_5_ah_per_cycle", features.columns)
        self.assertIn("event_observed", features.columns)
        self.assertIn("duration_cycles", features.columns)
        self.assertAlmostEqual(features["capacity_rolling_mean_5_ah"].iloc[2], 1.9)


if __name__ == "__main__":
    unittest.main()
