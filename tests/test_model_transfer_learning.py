import tempfile
import unittest
from pathlib import Path

import pandas as pd

from modules.model_transfer_learning.feature_contract import COMMON_CYCLE_V1
from modules.model_transfer_learning.model_router import ModelRegistry
from modules.model_transfer_learning.train_shared_baseline import train_shared_baseline


class ModelTransferTests(unittest.TestCase):
    def test_feature_contract_reports_missing_columns(self) -> None:
        missing = COMMON_CYCLE_V1.missing_columns(["dataset", "battery_type"])
        self.assertIn("cell_id", missing)
        self.assertIn("capacity_ah", missing)

    def test_registry_routes_specific_and_unknown_battery_types(self) -> None:
        registry = ModelRegistry.load(Path("configs/model_registry.json"))

        self.assertEqual(registry.resolve("li_ion").key, "li_ion_capacity_ridge")
        self.assertEqual(registry.resolve("lfp").key, "lfp_capacity_head")
        self.assertEqual(registry.resolve("unknown").key, "shared_capacity_ridge")
        self.assertEqual(
            [spec.key for spec in registry.fallback_chain("nmc")],
            ["nmc_capacity_head", "shared_capacity_ridge"],
        )

    def test_train_shared_baseline_writes_artifact(self) -> None:
        rows = []
        for idx in range(4):
            row = {
                "dataset": "unit",
                "battery_type": "li_ion",
                "cell_id": "BTEST",
                "cycle_index": idx + 1,
                "rul_cycles": 3 - idx,
                "rul_is_censored": False,
            }
            for column in COMMON_CYCLE_V1.feature_columns:
                row[column] = float(idx + 1)
            rows.append(row)
        frame = pd.DataFrame(rows)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            features_path = tmp_path / "features.csv"
            output_path = tmp_path / "artifact.json"
            frame.to_csv(features_path, index=False)
            artifact = train_shared_baseline(
                features_path=features_path,
                registry_path=Path("configs/model_registry.json"),
                output_path=output_path,
                model_key="shared_capacity_ridge",
                alpha=1.0,
            )

            self.assertTrue(output_path.exists())
            self.assertEqual(artifact.train_rows, 4)
            self.assertEqual(len(artifact.feature_columns), len(COMMON_CYCLE_V1.feature_columns))


if __name__ == "__main__":
    unittest.main()
