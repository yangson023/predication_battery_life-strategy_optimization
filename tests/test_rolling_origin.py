import unittest

import pandas as pd

from modules.rul_prediction.leave_one_battery_out import BASELINE_FEATURES
from modules.rul_prediction.rolling_origin import origin_cycles, run_rolling_origin


class RollingOriginTests(unittest.TestCase):
    @staticmethod
    def sample_frame() -> pd.DataFrame:
        rows = []
        for cell_id in ["A", "B", "C"]:
            for cycle in range(1, 7):
                row = {
                    "dataset": "unit",
                    "battery_type": "li_ion",
                    "cell_id": cell_id,
                    "cycle_index": cycle,
                    "discharge_cycle": cycle,
                    "rul_cycles": 6 - cycle,
                    "rul_is_censored": False,
                    "rul_lower_bound_cycles": 6 - cycle,
                }
                for feature in BASELINE_FEATURES:
                    row[feature] = float(cycle)
                rows.append(row)
        return pd.DataFrame(rows)

    def test_origin_cycles(self) -> None:
        self.assertEqual(origin_cycles(10, start=3, step=3), [3, 6, 9])

    def test_rolling_origin_outputs_predictions_and_summary(self) -> None:
        predictions, summary = run_rolling_origin(
            self.sample_frame(),
            origin_start=2,
            origin_step=2,
            bootstrap_models=5,
            random_seed=7,
        )

        self.assertFalse(predictions.empty)
        self.assertFalse(summary.empty)
        self.assertIn("predicted_rul_p10", predictions.columns)
        self.assertIn("predicted_rul_p90", predictions.columns)
        self.assertEqual(set(summary["test_cell_id"]), {"A", "B", "C"})


if __name__ == "__main__":
    unittest.main()
