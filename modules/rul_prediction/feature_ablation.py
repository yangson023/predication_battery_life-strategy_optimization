"""Feature group ablation for the NASA RUL baseline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from modules.rul_prediction.leave_one_battery_out import (
    BASELINE_FEATURES,
    FEATURE_GROUPS,
    evaluate_leave_one_battery_out,
)


def features_without(group_name: str) -> list[str]:
    removed = set(FEATURE_GROUPS[group_name])
    return [feature for feature in BASELINE_FEATURES if feature not in removed]


def run_feature_ablation(frame: pd.DataFrame, alpha: float = 1.0) -> pd.DataFrame:
    rows = []
    experiments = [("all_features", None, BASELINE_FEATURES)]
    experiments.extend(
        (f"drop_{group_name}", group_name, features_without(group_name))
        for group_name in FEATURE_GROUPS
    )

    for ablation_name, removed_group, feature_columns in experiments:
        results, _ = evaluate_leave_one_battery_out(
            frame,
            feature_columns=feature_columns,
            alpha=alpha,
        )
        for result in results:
            row = {
                "ablation_name": ablation_name,
                "removed_group": removed_group or "",
                "feature_count": len(feature_columns),
                **result.__dict__,
            }
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/features/nasa/li_ion/cycle_features.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("models/rul_prediction/nasa_li_ion_baseline/feature_ablation.csv"),
    )
    parser.add_argument("--alpha", type=float, default=1.0)
    args = parser.parse_args()

    frame = pd.read_csv(args.features)
    ablation = run_feature_ablation(frame, alpha=args.alpha)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ablation.to_csv(args.output, index=False)

    observed = ablation.loc[ablation["mae"].notna()].copy()
    summary = (
        observed.groupby(["ablation_name", "removed_group", "feature_count"], dropna=False)
        .agg(mean_mae=("mae", "mean"), mean_rmse=("rmse", "mean"))
        .reset_index()
        .sort_values(["mean_mae", "ablation_name"])
    )
    summary_path = args.output.with_name("feature_ablation_summary.csv")
    summary.to_csv(summary_path, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
