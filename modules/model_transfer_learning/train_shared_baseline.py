"""Train a lightweight shared baseline on the common cycle feature contract."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from modules.model_transfer_learning.feature_contract import COMMON_CYCLE_V1
from modules.model_transfer_learning.model_router import ModelRegistry


@dataclass
class RidgeBaselineArtifact:
    model_key: str
    feature_contract: str
    target: str
    feature_columns: list[str]
    coefficients: list[float]
    intercept: float
    feature_means: dict[str, float]
    feature_stds: dict[str, float]
    ridge_alpha: float
    train_rows: int
    train_cells: list[str]
    excluded_rows: int


def prepare_training_table(frame: pd.DataFrame, target: str) -> tuple[pd.DataFrame, pd.Series]:
    COMMON_CYCLE_V1.validate(frame)
    train = frame.loc[frame[target].notna() & ~frame["rul_is_censored"].astype(bool)].copy()
    features = COMMON_CYCLE_V1.select_features(train)
    features = features.apply(pd.to_numeric, errors="coerce")
    features = features.replace([np.inf, -np.inf], np.nan)
    means = features.mean(numeric_only=True)
    features = features.fillna(means).fillna(0.0)
    target_values = train[target].astype(float)
    return features, target_values


def fit_ridge_closed_form(features: pd.DataFrame, target: pd.Series, alpha: float) -> RidgeBaselineArtifact:
    means = features.mean()
    stds = features.std(ddof=0).replace(0, 1.0).fillna(1.0)
    normalized = (features - means) / stds

    x = np.column_stack([np.ones(len(normalized)), normalized.to_numpy(dtype=float)])
    y = target.to_numpy(dtype=float)
    penalty = np.eye(x.shape[1]) * alpha
    penalty[0, 0] = 0.0
    weights = np.linalg.pinv(x.T @ x + penalty) @ x.T @ y
    return weights, means, stds


def train_shared_baseline(
    features_path: Path,
    registry_path: Path,
    output_path: Path | None,
    model_key: str,
    alpha: float,
) -> RidgeBaselineArtifact:
    registry = ModelRegistry.load(registry_path)
    model = registry.models[model_key]
    frame = pd.read_csv(features_path)
    features, target = prepare_training_table(frame, model.target)
    weights, means, stds = fit_ridge_closed_form(features, target, alpha)

    artifact = RidgeBaselineArtifact(
        model_key=model.key,
        feature_contract=model.feature_contract,
        target=model.target,
        feature_columns=list(features.columns),
        coefficients=[float(value) for value in weights[1:]],
        intercept=float(weights[0]),
        feature_means={column: float(means[column]) for column in features.columns},
        feature_stds={column: float(stds[column]) for column in features.columns},
        ridge_alpha=alpha,
        train_rows=int(len(features)),
        train_cells=sorted(frame.loc[frame[model.target].notna(), "cell_id"].unique().tolist()),
        excluded_rows=int(len(frame) - len(features)),
    )
    destination = output_path or Path(model.artifact_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as fh:
        json.dump(asdict(artifact), fh, indent=2)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/features/nasa/li_ion/cycle_features.csv"),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("configs/model_registry.json"),
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--model-key", default="shared_capacity_ridge")
    parser.add_argument("--alpha", type=float, default=1.0)
    args = parser.parse_args()

    artifact = train_shared_baseline(
        features_path=args.features,
        registry_path=args.registry,
        output_path=args.output,
        model_key=args.model_key,
        alpha=args.alpha,
    )
    print(
        f"trained {artifact.model_key}: rows={artifact.train_rows}, "
        f"features={len(artifact.feature_columns)}, excluded={artifact.excluded_rows}"
    )


if __name__ == "__main__":
    main()
