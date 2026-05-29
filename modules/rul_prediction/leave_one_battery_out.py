"""Leave-one-battery-out RUL baseline evaluation for NASA feature tables."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


BASELINE_FEATURES = [
    "discharge_cycle",
    "available_discharge_history_cycles",
    "capacity_ah",
    "soh_capacity_ratio",
    "capacity_loss_ratio",
    "capacity_change_previous_ah",
    "soh_change_previous",
    "capacity_rolling_mean_5_ah",
    "capacity_rolling_std_5_ah",
    "capacity_slope_5_ah_per_cycle",
    "soh_slope_5_per_cycle",
    "capacity_rolling_mean_10_ah",
    "capacity_rolling_std_10_ah",
    "capacity_slope_10_ah_per_cycle",
    "soh_slope_10_per_cycle",
    "discharge_duration_s",
    "discharge_voltage_measured_v_min",
    "discharge_voltage_measured_v_max",
    "discharge_voltage_measured_v_mean",
    "discharge_current_measured_a_mean",
    "discharge_temperature_measured_c_max",
    "discharge_temperature_measured_c_mean",
    "latest_charge_duration_s",
    "latest_charge_voltage_measured_v_mean",
    "latest_charge_current_measured_a_mean",
    "latest_charge_temperature_measured_c_mean",
    "latest_impedance_re_ohm",
    "latest_impedance_rct_ohm",
    "cycles_since_latest_charge",
    "cycles_since_latest_impedance",
]


@dataclass
class FoldResult:
    test_cell_id: str
    train_rows: int
    test_rows: int
    labeled_test_rows: int
    censored_test_rows: int
    mae: float | None
    rmse: float | None
    mean_error: float | None
    max_abs_error: float | None
    notes: str


def validate_columns(frame: pd.DataFrame, feature_columns: list[str], target: str) -> None:
    required = {"cell_id", target, "rul_is_censored", *feature_columns}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def prepare_features(
    frame: pd.DataFrame, feature_columns: list[str], fill_values: pd.Series | None = None
) -> tuple[pd.DataFrame, pd.Series]:
    features = frame.loc[:, feature_columns].apply(pd.to_numeric, errors="coerce")
    features = features.replace([np.inf, -np.inf], np.nan)
    if fill_values is None:
        fill_values = features.mean(numeric_only=True).fillna(0.0)
    features = features.fillna(fill_values).fillna(0.0)
    return features, fill_values


def fit_ridge(features: pd.DataFrame, target: pd.Series, alpha: float) -> np.ndarray:
    x = np.column_stack([np.ones(len(features)), features.to_numpy(dtype=float)])
    y = target.to_numpy(dtype=float)
    penalty = np.eye(x.shape[1]) * alpha
    penalty[0, 0] = 0.0
    return np.linalg.pinv(x.T @ x + penalty) @ x.T @ y


def predict_ridge(features: pd.DataFrame, weights: np.ndarray) -> np.ndarray:
    x = np.column_stack([np.ones(len(features)), features.to_numpy(dtype=float)])
    return x @ weights


def evaluate_predictions(actual: pd.Series, predicted: np.ndarray) -> dict[str, float]:
    error = predicted - actual.to_numpy(dtype=float)
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "mean_error": float(np.mean(error)),
        "max_abs_error": float(np.max(np.abs(error))),
    }


def evaluate_leave_one_battery_out(
    frame: pd.DataFrame,
    feature_columns: list[str] = BASELINE_FEATURES,
    target: str = "rul_cycles",
    alpha: float = 1.0,
) -> tuple[list[FoldResult], pd.DataFrame]:
    validate_columns(frame, feature_columns, target)
    results: list[FoldResult] = []
    predictions: list[pd.DataFrame] = []

    for test_cell_id in sorted(frame["cell_id"].unique()):
        train = frame.loc[
            frame["cell_id"].ne(test_cell_id)
            & frame[target].notna()
            & ~frame["rul_is_censored"].astype(bool)
        ].copy()
        test = frame.loc[frame["cell_id"].eq(test_cell_id)].copy()
        labeled_test = test.loc[test[target].notna() & ~test["rul_is_censored"].astype(bool)].copy()
        censored_test = test.loc[test["rul_is_censored"].astype(bool)].copy()

        if train.empty:
            results.append(
                FoldResult(
                    test_cell_id=str(test_cell_id),
                    train_rows=0,
                    test_rows=len(test),
                    labeled_test_rows=len(labeled_test),
                    censored_test_rows=len(censored_test),
                    mae=None,
                    rmse=None,
                    mean_error=None,
                    max_abs_error=None,
                    notes="no_training_rows",
                )
            )
            continue

        x_train_raw, fill_values = prepare_features(train, feature_columns)
        means = x_train_raw.mean()
        stds = x_train_raw.std(ddof=0).replace(0, 1.0).fillna(1.0)
        x_train = (x_train_raw - means) / stds
        weights = fit_ridge(x_train, train[target].astype(float), alpha)

        x_test_raw, _ = prepare_features(test, feature_columns, fill_values)
        x_test = (x_test_raw - means) / stds
        predicted = np.clip(predict_ridge(x_test, weights), a_min=0.0, a_max=None)
        fold_predictions = test.loc[
            :,
            [
                "dataset",
                "battery_type",
                "cell_id",
                "cycle_index",
                "discharge_cycle",
                target,
                "rul_is_censored",
                "rul_lower_bound_cycles",
            ],
        ].copy()
        fold_predictions["predicted_rul_cycles"] = predicted
        predictions.append(fold_predictions)

        if labeled_test.empty:
            results.append(
                FoldResult(
                    test_cell_id=str(test_cell_id),
                    train_rows=len(train),
                    test_rows=len(test),
                    labeled_test_rows=0,
                    censored_test_rows=len(censored_test),
                    mae=None,
                    rmse=None,
                    mean_error=None,
                    max_abs_error=None,
                    notes="test_cell_has_no_observed_eol",
                )
            )
            continue

        labeled_positions = test.index.isin(labeled_test.index)
        metrics = evaluate_predictions(labeled_test[target], predicted[labeled_positions])
        results.append(
            FoldResult(
                test_cell_id=str(test_cell_id),
                train_rows=len(train),
                test_rows=len(test),
                labeled_test_rows=len(labeled_test),
                censored_test_rows=len(censored_test),
                mae=metrics["mae"],
                rmse=metrics["rmse"],
                mean_error=metrics["mean_error"],
                max_abs_error=metrics["max_abs_error"],
                notes="ok",
            )
        )

    prediction_frame = pd.concat(predictions, ignore_index=True) if predictions else pd.DataFrame()
    return results, prediction_frame


def write_results(
    results: list[FoldResult], predictions: pd.DataFrame, output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_rows = [asdict(result) for result in results]
    pd.DataFrame(result_rows).to_csv(output_dir / "leave_one_battery_out_metrics.csv", index=False)
    predictions.to_csv(output_dir / "leave_one_battery_out_predictions.csv", index=False)
    with (output_dir / "leave_one_battery_out_metrics.json").open("w", encoding="utf-8") as fh:
        json.dump(result_rows, fh, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/features/nasa/li_ion/cycle_features.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/rul_prediction/nasa_li_ion_baseline"),
    )
    parser.add_argument("--alpha", type=float, default=1.0)
    args = parser.parse_args()

    frame = pd.read_csv(args.features)
    results, predictions = evaluate_leave_one_battery_out(frame, alpha=args.alpha)
    write_results(results, predictions, args.output_dir)
    for result in results:
        if result.mae is None:
            print(
                f"{result.test_cell_id}: train={result.train_rows}, "
                f"test={result.test_rows}, {result.notes}"
            )
        else:
            print(
                f"{result.test_cell_id}: train={result.train_rows}, "
                f"test={result.labeled_test_rows}, MAE={result.mae:.3f}, "
                f"RMSE={result.rmse:.3f}"
            )


if __name__ == "__main__":
    main()
