import tempfile
import unittest
from pathlib import Path

import pandas as pd

from modules.feature_engineering.build_external_health_labels import (
    build_external_health_labels,
    build_labels_from_feature_table,
    find_first_sustained_crossing,
)


class ExternalHealthLabelTests(unittest.TestCase):
    def test_sustained_crossing_respects_consecutive_observations(self) -> None:
        values = pd.Series([1.0, 0.78, 0.82, 0.79, 0.77])

        self.assertEqual(find_first_sustained_crossing(values, 0.80, 1), 1)
        self.assertEqual(find_first_sustained_crossing(values, 0.80, 2), 3)

    def test_builds_observed_cycle_rul_labels(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 4,
                "dataset_family": ["multi_cell_cycle_life"] * 4,
                "data_category": ["cycling"] * 4,
                "measurement_type": ["cycle_timeseries"] * 4,
                "chemistry": ["li_ion"] * 4,
                "cell_id": ["G1C1"] * 4,
                "source_archive_name": ["unit.zip"] * 4,
                "cycle_index": [1, 2, 3, 4],
                "capacity_delta_ah": [2.0, 1.8, 1.58, 1.4],
            }
        )

        labels, summary = build_labels_from_feature_table(
            frame=frame,
            source_table="cycle_features_sample.csv",
            label_key_prefix="capacity",
            observation_column="cycle_index",
            capacity_column="capacity_delta_ah",
            thresholds=[0.8],
            initial_capacity_window=1,
            consecutive_eol_observations=1,
            minimum_valid_capacity_ah=1e-6,
        )

        self.assertEqual(labels["rul_observations"].tolist(), [2.0, 1.0, 0.0, 0.0])
        self.assertTrue(labels["eol_observed"].all())
        self.assertEqual(summary[0].label_key, "capacity_eol_80")
        self.assertEqual(summary[0].label_quality, "usable")

    def test_censored_when_eol_not_observed(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 2,
                "cell_id": ["G1C1"] * 2,
                "source_archive_name": ["unit.zip"] * 2,
                "diagnostic_part": [0, 1],
                "capacity_delta_ah": [2.0, 1.95],
            }
        )

        labels, summary = build_labels_from_feature_table(
            frame=frame,
            source_table="rpt_features_sample.csv",
            label_key_prefix="rpt_capacity",
            observation_column="diagnostic_part",
            capacity_column="capacity_delta_ah",
            thresholds=[0.8],
            initial_capacity_window=1,
            consecutive_eol_observations=1,
            minimum_valid_capacity_ah=1e-6,
        )

        self.assertTrue(labels["rul_observations"].isna().all())
        self.assertTrue(labels["rul_is_censored"].all())
        self.assertEqual(labels["rul_lower_bound_observations"].tolist(), [1.0, 0.0])
        self.assertFalse(summary[0].eol_observed)

    def test_invalid_initial_capacity_is_marked(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"],
                "cell_id": ["G1C1"],
                "source_archive_name": ["unit.zip"],
                "cycle_index": [1],
                "capacity_delta_ah": [0.0],
            }
        )

        labels, summary = build_labels_from_feature_table(
            frame=frame,
            source_table="cycle_features_sample.csv",
            label_key_prefix="capacity",
            observation_column="cycle_index",
            capacity_column="capacity_delta_ah",
            thresholds=[0.8],
            initial_capacity_window=1,
            consecutive_eol_observations=1,
            minimum_valid_capacity_ah=1e-6,
        )

        self.assertEqual(labels.loc[0, "label_quality"], "invalid_no_positive_capacity")
        self.assertEqual(summary[0].label_quality, "invalid_no_positive_capacity")

    def test_nonpositive_capacity_does_not_trigger_eol(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 2,
                "cell_id": ["G1C1"] * 2,
                "source_archive_name": ["unit.zip"] * 2,
                "diagnostic_part": [0, 1],
                "capacity_delta_ah": [0.0, 2.0],
            }
        )

        labels, summary = build_labels_from_feature_table(
            frame=frame,
            source_table="rpt_features_sample.csv",
            label_key_prefix="rpt_capacity",
            observation_column="diagnostic_part",
            capacity_column="capacity_delta_ah",
            thresholds=[0.8],
            initial_capacity_window=1,
            consecutive_eol_observations=1,
            minimum_valid_capacity_ah=1e-6,
        )

        self.assertTrue(labels["rul_observations"].isna().all())
        self.assertFalse(summary[0].eol_observed)
        self.assertTrue(pd.isna(labels.loc[0, "soh_capacity_ratio"]))

    def test_build_external_health_labels_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "features"
            input_root.mkdir()
            pd.DataFrame(
                {
                    "dataset_id": ["unit"] * 3,
                    "cell_id": ["G1C1"] * 3,
                    "source_archive_name": ["unit.zip"] * 3,
                    "cycle_index": [1, 2, 3],
                    "capacity_delta_ah": [2.0, 1.9, 1.7],
                }
            ).to_csv(input_root / "cycle_features_sample.csv", index=False)

            labels, summary = build_external_health_labels(
                input_root=input_root,
                output_root=input_root,
                thresholds=[0.8],
                initial_capacity_window=1,
                consecutive_eol_observations=1,
                minimum_valid_capacity_ah=1e-6,
                cycle_capacity_column="capacity_delta_ah",
                rpt_capacity_column="capacity_delta_ah",
            )

            self.assertFalse(labels.empty)
            self.assertFalse(summary.empty)
            self.assertTrue((input_root / "external_health_labels_sample.csv").exists())
            self.assertTrue((input_root / "external_label_summary_sample.csv").exists())


if __name__ == "__main__":
    unittest.main()
