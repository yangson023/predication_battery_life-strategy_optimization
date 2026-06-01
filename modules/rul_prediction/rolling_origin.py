"""Rolling-origin RUL evaluation with bootstrap ridge uncertainty."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from modules.rul_prediction.leave_one_battery_out import (
    BASELINE_FEATURES,
    fit_ridge,
    load_feature_table,
    predict_ridge,
    prepare_features,
    validate_columns,
)


@dataclass
class RollingOriginResult:
    test_cell_id: str
    origin_cycle: int
    cycle_index: int
    train_rows: int
    bootstrap_models: int
    true_rul_cycles: float
    predicted_rul_mean: float
    predicted_rul_std: float
    predicted_rul_p10: float
    predicted_rul_p50: float
    predicted_rul_p90: float
    absolute_error: float
    interval_coverage_80: bool
    prediction_interval_width: float


@dataclass
class RollingOriginSummary:
    test_cell_id: str
    origins: int
    mae: float
    rmse: float
    coverage_80: float
    mean_interval_width: float
    mean_prediction_std: float


def origin_cycles(max_cycle: int, start: int, step: int) -> list[int]:
    if start < 1 or step < 1:
        raise ValueError("origin start and step must be positive.")
    return list(range(start, max_cycle + 1, step))


def latest_sample_at_origin(test: pd.DataFrame, origin_cycle: int) -> pd.Series | None:
    available = test.loc[test["discharge_cycle"].le(origin_cycle)].sort_values(
        "discharge_cycle"
    )
    if available.empty:
        return None
    return available.iloc[-1]


def bootstrap_predictions(
    train: pd.DataFrame,
    sample: pd.DataFrame,
    feature_columns: list[str],
    target: str,
    alpha: float,
    bootstrap_models: int,
    rng: np.random.Generator,
) -> np.ndarray:
    x_train_raw, fill_values = prepare_features(train, feature_columns)
    x_sample_raw, _ = prepare_features(sample, feature_columns, fill_values)
    predictions = []
    train_indices = np.arange(len(train))
    for _ in range(bootstrap_models):
        sampled_positions = rng.choice(train_indices, size=len(train_indices), replace=True)
        sampled_features = x_train_raw.iloc[sampled_positions].reset_index(drop=True)
        sampled_target = train[target].iloc[sampled_positions].astype(float).reset_index(drop=True)
        means = sampled_features.mean()
        stds = sampled_features.std(ddof=0).replace(0, 1.0).fillna(1.0)
        x_boot = (sampled_features - means) / stds
        weights = fit_ridge(x_boot, sampled_target, alpha)
        x_sample = (x_sample_raw - means) / stds
        predictions.append(float(np.clip(predict_ridge(x_sample, weights)[0], 0.0, None)))
    return np.asarray(predictions, dtype=float)


def summarize_predictions(
    test_cell_id: str,
    sample: pd.Series,
    train_rows: int,
    bootstrap_models: int,
    predictions: np.ndarray,
    target: str,
) -> RollingOriginResult:
    true_rul = float(sample[target])
    p10, p50, p90 = np.quantile(predictions, [0.10, 0.50, 0.90])
    mean = float(np.mean(predictions))
    std = float(np.std(predictions, ddof=0))
    return RollingOriginResult(
        test_cell_id=test_cell_id,
        origin_cycle=int(sample["discharge_cycle"]),
        cycle_index=int(sample["cycle_index"]),
        train_rows=train_rows,
        bootstrap_models=bootstrap_models,
        true_rul_cycles=true_rul,
        predicted_rul_mean=mean,
        predicted_rul_std=std,
        predicted_rul_p10=float(p10),
        predicted_rul_p50=float(p50),
        predicted_rul_p90=float(p90),
        absolute_error=float(abs(mean - true_rul)),
        interval_coverage_80=bool(p10 <= true_rul <= p90),
        prediction_interval_width=float(p90 - p10),
    )


def run_rolling_origin(
    frame: pd.DataFrame,
    feature_columns: list[str] = BASELINE_FEATURES,
    target: str = "rul_cycles",
    origin_start: int = 20,
    origin_step: int = 20,
    bootstrap_models: int = 100,
    alpha: float = 1.0,
    random_seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    validate_columns(frame, feature_columns, target)
    rng = np.random.default_rng(random_seed)
    results: list[RollingOriginResult] = []

    for test_cell_id in sorted(frame["cell_id"].unique()):
        train = frame.loc[
            frame["cell_id"].ne(test_cell_id)
            & frame[target].notna()
            & ~frame["rul_is_censored"].astype(bool)
        ].copy()
        test = frame.loc[
            frame["cell_id"].eq(test_cell_id)
            & frame[target].notna()
            & ~frame["rul_is_censored"].astype(bool)
        ].copy()
        if train.empty or test.empty:
            continue

        max_cycle = int(test["discharge_cycle"].max())
        for requested_origin in origin_cycles(max_cycle, origin_start, origin_step):
            sample = latest_sample_at_origin(test, requested_origin)
            if sample is None:
                continue
            sample_frame = pd.DataFrame([sample])
            predictions = bootstrap_predictions(
                train=train,
                sample=sample_frame,
                feature_columns=feature_columns,
                target=target,
                alpha=alpha,
                bootstrap_models=bootstrap_models,
                rng=rng,
            )
            results.append(
                summarize_predictions(
                    test_cell_id=str(test_cell_id),
                    sample=sample,
                    train_rows=len(train),
                    bootstrap_models=bootstrap_models,
                    predictions=predictions,
                    target=target,
                )
            )

    predictions_table = pd.DataFrame([asdict(result) for result in results])
    if predictions_table.empty:
        return predictions_table, pd.DataFrame()
    summary = (
        predictions_table.groupby("test_cell_id")
        .agg(
            origins=("origin_cycle", "count"),
            mae=("absolute_error", "mean"),
            rmse=("absolute_error", lambda value: float(np.sqrt(np.mean(np.square(value))))),
            coverage_80=("interval_coverage_80", "mean"),
            mean_interval_width=("prediction_interval_width", "mean"),
            mean_prediction_std=("predicted_rul_std", "mean"),
        )
        .reset_index()
    )
    return predictions_table, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/features/nasa/li_ion/cycle_features.csv"),
    )
    parser.add_argument("--labels", type=Path, default=None)
    parser.add_argument("--label-key", default="capacity_eol_80")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("models/rul_prediction/nasa_li_ion_baseline"),
    )
    parser.add_argument("--origin-start", type=int, default=20)
    parser.add_argument("--origin-step", type=int, default=20)
    parser.add_argument("--bootstrap-models", type=int, default=100)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()

    frame = load_feature_table(args.features, args.labels, args.label_key)
    output_dir = args.output_dir / args.label_key if args.label_key else args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions, summary = run_rolling_origin(
        frame,
        origin_start=args.origin_start,
        origin_step=args.origin_step,
        bootstrap_models=args.bootstrap_models,
        alpha=args.alpha,
        random_seed=args.random_seed,
    )
    predictions.to_csv(output_dir / "rolling_origin_predictions.csv", index=False)
    summary.to_csv(output_dir / "rolling_origin_summary.csv", index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
