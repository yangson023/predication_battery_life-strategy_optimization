import unittest

import pandas as pd

from modules.rul_prediction.leave_one_battery_out import (
    BASELINE_FEATURES,
    FEATURE_GROUPS,
    evaluate_leave_one_battery_out,
)
from modules.rul_prediction.feature_ablation import run_feature_ablation


class RulPredictionBaselineTests(unittest.TestCase):
    @staticmethod
    def sample_frame() -> pd.DataFrame:
        rows = []
        for cell_id in ["A", "B", "C"]:
            for cycle in range(1, 4):
                row = {
                    "dataset": "unit",
                    "battery_type": "li_ion",
                    "cell_id": cell_id,
                    "cycle_index": cycle,
                    "discharge_cycle": cycle,
                    "rul_cycles": 3 - cycle,
                    "rul_is_censored": False,
                    "rul_lower_bound_cycles": 3 - cycle,
                }
                for feature in BASELINE_FEATURES:
                    row[feature] = float(cycle)
                rows.append(row)
        return pd.DataFrame(rows)

    def test_leave_one_battery_out_returns_one_fold_per_cell(self) -> None:
        results, predictions = evaluate_leave_one_battery_out(self.sample_frame())

        self.assertEqual(len(results), 3)
        self.assertEqual(len(predictions), 9)
        self.assertTrue(all(result.train_rows == 6 for result in results))
        self.assertTrue(all(result.mae is not None for result in results))
        self.assertIn("predicted_rul_p10", predictions.columns)
        self.assertIn("predicted_rul_p50", predictions.columns)
        self.assertIn("predicted_rul_p90", predictions.columns)
        self.assertTrue(all(result.interval_coverage_80 is not None for result in results))

    def test_censored_test_cell_has_no_numeric_metrics(self) -> None:
        frame = self.sample_frame()
        frame.loc[frame["cell_id"].eq("C"), "rul_cycles"] = pd.NA
        frame.loc[frame["cell_id"].eq("C"), "rul_is_censored"] = True

        results, _ = evaluate_leave_one_battery_out(frame)
        censored = [result for result in results if result.test_cell_id == "C"][0]

        self.assertIsNone(censored.mae)
        self.assertEqual(censored.notes, "test_cell_has_no_observed_eol")

    def test_feature_ablation_runs_all_groups(self) -> None:
        ablation = run_feature_ablation(self.sample_frame())

        expected_names = {"all_features"} | {f"drop_{name}" for name in FEATURE_GROUPS}
        self.assertEqual(set(ablation["ablation_name"]), expected_names)
        self.assertEqual(
            len(ablation),
            len(expected_names) * self.sample_frame()["cell_id"].nunique(),
        )


if __name__ == "__main__":
    unittest.main()
