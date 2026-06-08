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

    def test_limited_window_quality_marks_short_training_groups(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 10,
                "cell_id": ["G1C1"] * 10,
                "source_archive_name": ["unit.zip"] * 10,
                "cycle_index": list(range(1, 11)),
                "capacity_delta_ah": [2.0, 1.95, 1.9, 1.85, 1.8, 1.75, 1.7, 1.6, 1.55, 1.5],
            }
        )

        labels, summary = build_labels_from_feature_table(
            frame=frame,
            source_table="cycle_features.csv",
            label_key_prefix="capacity",
            observation_column="cycle_index",
            capacity_column="capacity_delta_ah",
            thresholds=[0.8],
            initial_capacity_window=1,
            consecutive_eol_observations=1,
            minimum_valid_capacity_ah=1e-6,
            minimum_observations_for_training=50,
        )

        self.assertEqual(
            labels["label_quality"].unique().tolist(),
            ["limited_window_less_than_50_observations"],
        )
        self.assertEqual(
            summary[0].label_quality,
            "limited_window_less_than_50_observations",
        )

    def test_protocol_regime_index_splits_label_groups(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 6,
                "cell_id": ["G1C1"] * 6,
                "source_archive_name": ["unit.zip"] * 6,
                "protocol_regime_index": [1, 1, 1, 2, 2, 2],
                "protocol_boundary_flag": [False, False, False, True, False, False],
                "cycle_index": [1, 2, 3, 4, 5, 6],
                "capacity_delta_ah": [2.0, 1.9, 1.8, 1.0, 0.95, 0.9],
            }
        )

        labels, summary = build_labels_from_feature_table(
            frame=frame,
            source_table="cycle_features.csv",
            label_key_prefix="capacity",
            observation_column="cycle_index",
            capacity_column="capacity_delta_ah",
            thresholds=[0.8],
            initial_capacity_window=1,
            consecutive_eol_observations=1,
            minimum_valid_capacity_ah=1e-6,
        )

        self.assertEqual(len(summary), 2)
        self.assertEqual(set(labels["protocol_regime_index"]), {1, 2})
        self.assertTrue(labels["eol_observed"].eq(False).all())
        self.assertIn("1", summary[0].group_id)
        self.assertIn("2", summary[1].group_id)

    def test_cycle_eol_far_from_protocol_boundary_is_trainable(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 20,
                "cell_id": ["G1C1"] * 20,
                "source_archive_name": ["unit.zip"] * 20,
                "protocol_regime_index": [2] * 20,
                "cycle_index": list(range(1, 21)),
                "capacity_delta_ah": [
                    2.0,
                    1.95,
                    1.9,
                    1.85,
                    1.8,
                    1.75,
                    1.7,
                    1.65,
                    1.6,
                    1.55,
                    1.5,
                    1.45,
                    1.4,
                    1.35,
                    1.3,
                    1.25,
                    1.2,
                    1.15,
                    1.1,
                    1.05,
                ],
            }
        )

        labels, summary = build_labels_from_feature_table(
            frame=frame,
            source_table="cycle_features.csv",
            label_key_prefix="capacity",
            observation_column="cycle_index",
            capacity_column="capacity_delta_ah",
            thresholds=[0.8],
            initial_capacity_window=1,
            consecutive_eol_observations=1,
            minimum_valid_capacity_ah=1e-6,
            minimum_observations_for_training=20,
            protocol_boundary_exclusion_observations=5,
        )

        self.assertTrue(labels["trainable_label"].all())
        self.assertEqual(summary[0].eol_boundary_quality, "away_from_protocol_boundary")
        self.assertTrue(summary[0].trainable_label)
        self.assertEqual(summary[0].trainable_label_quality, "trainable_observed_protocol_consistent")

    def test_cycle_eol_near_protocol_boundary_is_not_trainable(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 20,
                "cell_id": ["G1C1"] * 20,
                "source_archive_name": ["unit.zip"] * 20,
                "protocol_regime_index": [2] * 20,
                "cycle_index": list(range(1, 21)),
                "capacity_delta_ah": [
                    2.0,
                    1.95,
                    1.9,
                    1.85,
                    1.8,
                    1.75,
                    1.7,
                    1.65,
                    1.6,
                    1.55,
                    1.5,
                    1.45,
                    1.4,
                    1.35,
                    1.3,
                    1.25,
                    1.1,
                    1.0,
                    0.9,
                    0.8,
                ],
            }
        )

        labels, summary = build_labels_from_feature_table(
            frame=frame,
            source_table="cycle_features.csv",
            label_key_prefix="capacity",
            observation_column="cycle_index",
            capacity_column="capacity_delta_ah",
            thresholds=[0.6],
            initial_capacity_window=1,
            consecutive_eol_observations=1,
            minimum_valid_capacity_ah=1e-6,
            minimum_observations_for_training=20,
            protocol_boundary_exclusion_observations=5,
        )

        self.assertFalse(labels["trainable_label"].any())
        self.assertEqual(summary[0].eol_boundary_quality, "unreliable_boundary_crossing")
        self.assertFalse(summary[0].trainable_label)
        self.assertEqual(summary[0].trainable_label_quality, "excluded_unreliable_boundary_crossing")

    def test_rpt_labels_are_excluded_without_protocol_assignment(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 20,
                "cell_id": ["G1C1"] * 20,
                "source_archive_name": ["unit.zip"] * 20,
                "diagnostic_part": list(range(20)),
                "capacity_delta_ah": [2.0 - index * 0.05 for index in range(20)],
            }
        )

        labels, summary = build_labels_from_feature_table(
            frame=frame,
            source_table="rpt_features.csv",
            label_key_prefix="rpt_capacity",
            observation_column="diagnostic_part",
            capacity_column="capacity_delta_ah",
            thresholds=[0.8],
            initial_capacity_window=1,
            consecutive_eol_observations=1,
            minimum_valid_capacity_ah=1e-6,
            minimum_observations_for_training=20,
        )

        self.assertEqual(labels["label_quality"].unique().tolist(), ["usable"])
        self.assertEqual(labels["protocol_assignment_quality"].unique().tolist(), ["unknown_or_unmapped"])
        self.assertFalse(labels["trainable_label"].any())
        self.assertEqual(summary[0].trainable_label_quality, "excluded_unknown_or_unmapped")

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
                source_mode="sample",
            )

            self.assertFalse(labels.empty)
            self.assertFalse(summary.empty)
            self.assertTrue((input_root / "external_health_labels_sample.csv").exists())
            self.assertTrue((input_root / "external_label_summary_sample.csv").exists())

    def test_build_external_health_labels_by_cell_mode_writes_full_names(self) -> None:
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
            ).to_csv(input_root / "cycle_features.csv", index=False)

            labels, _ = build_external_health_labels(
                input_root=input_root,
                output_root=input_root,
                thresholds=[0.8],
                initial_capacity_window=1,
                consecutive_eol_observations=1,
                minimum_valid_capacity_ah=1e-6,
                cycle_capacity_column="capacity_delta_ah",
                rpt_capacity_column="capacity_delta_ah",
                source_mode="by_cell",
            )

            self.assertFalse(labels.empty)
            self.assertTrue((input_root / "external_health_labels.csv").exists())
            self.assertTrue((input_root / "external_label_summary.csv").exists())


if __name__ == "__main__":
    unittest.main()
