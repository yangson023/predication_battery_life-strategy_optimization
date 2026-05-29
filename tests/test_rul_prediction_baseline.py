import unittest

import pandas as pd

from modules.rul_prediction.leave_one_battery_out import (
    BASELINE_FEATURES,
    evaluate_leave_one_battery_out,
)


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

    def test_censored_test_cell_has_no_numeric_metrics(self) -> None:
        frame = self.sample_frame()
        frame.loc[frame["cell_id"].eq("C"), "rul_cycles"] = pd.NA
        frame.loc[frame["cell_id"].eq("C"), "rul_is_censored"] = True

        results, _ = evaluate_leave_one_battery_out(frame)
        censored = [result for result in results if result.test_cell_id == "C"][0]

        self.assertIsNone(censored.mae)
        self.assertEqual(censored.notes, "test_cell_has_no_observed_eol")


if __name__ == "__main__":
    unittest.main()
