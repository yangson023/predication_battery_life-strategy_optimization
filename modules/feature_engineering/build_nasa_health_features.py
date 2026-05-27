"""Build SOH/RUL labels and cycle-level features for NASA battery cells."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DATASET = "nasa"
BATTERY_TYPE = "li_ion"


@dataclass
class CellLabelSummary:
    cell_id: str
    discharge_cycles: int
    initial_capacity_ah: float
    last_capacity_ah: float
    minimum_soh: float
    last_soh: float
    eol_threshold: float
    eol_observed: bool
    eol_discharge_cycle: int | None
    censored_at_discharge_cycle: int | None


def find_first_sustained_crossing(
    values: pd.Series, threshold: float, consecutive_cycles: int
) -> int | None:
    """Return the positional index of the first threshold crossing run."""
    below = values.le(threshold).to_numpy()
    run_length = 0
    for index, crossed in enumerate(below):
        run_length = run_length + 1 if crossed else 0
        if run_length >= consecutive_cycles:
            return index - consecutive_cycles + 1
    return None


def add_rolling_slope(
    frame: pd.DataFrame, column: str, output_name: str, window: int
) -> None:
    def slope(values: np.ndarray) -> float:
        if values.size < 2 or np.isnan(values).any():
            return np.nan
        x = np.arange(values.size, dtype=float)
        return float(np.polyfit(x, values, deg=1)[0])

    frame[output_name] = (
        frame[column]
        .rolling(window=window, min_periods=2)
        .apply(lambda values: slope(values.to_numpy()), raw=False)
    )


def build_labels_for_cell(
    cycle_summary: pd.DataFrame,
    threshold: float,
    initial_capacity_window: int,
    consecutive_cycles: int,
) -> tuple[pd.DataFrame, CellLabelSummary]:
    discharge = (
        cycle_summary.loc[cycle_summary["cycle_type"].eq("discharge")]
        .sort_values("cycle_index")
        .reset_index(drop=True)
        .copy()
    )
    if discharge.empty:
        raise ValueError("No discharge cycles found.")
    if discharge["capacity_ah"].isna().any():
        raise ValueError("Discharge cycles contain missing capacity values.")

    cell_id = str(discharge["cell_id"].iloc[0])
    initial_capacity_ah = float(
        discharge["capacity_ah"].head(initial_capacity_window).mean()
    )
    discharge_cycle = discharge["cycle_number_within_type"].astype(int)
    soh = discharge["capacity_ah"] / initial_capacity_ah
    crossing_position = find_first_sustained_crossing(
        soh, threshold, consecutive_cycles
    )
    eol_observed = crossing_position is not None
    eol_cycle = (
        int(discharge_cycle.iloc[crossing_position])
        if crossing_position is not None
        else None
    )
    last_cycle = int(discharge_cycle.iloc[-1])

    labels = pd.DataFrame(
        {
            "dataset": discharge["dataset"],
            "battery_type": discharge["battery_type"],
            "cell_id": discharge["cell_id"],
            "cycle_index": discharge["cycle_index"].astype(int),
            "discharge_cycle": discharge_cycle,
            "start_time": discharge["start_time"],
            "capacity_ah": discharge["capacity_ah"],
            "initial_capacity_ah": initial_capacity_ah,
            "soh_capacity_ratio": soh,
            "capacity_loss_ah": initial_capacity_ah - discharge["capacity_ah"],
            "capacity_loss_ratio": 1.0 - soh,
            "eol_threshold": threshold,
            "eol_consecutive_cycles": consecutive_cycles,
            "eol_observed": eol_observed,
            "eol_discharge_cycle": eol_cycle,
            "is_eol_or_after": (
                discharge_cycle.ge(eol_cycle) if eol_cycle is not None else False
            ),
            "rul_cycles": (
                (eol_cycle - discharge_cycle).clip(lower=0)
                if eol_cycle is not None
                else np.nan
            ),
            "rul_is_censored": not eol_observed,
            "rul_lower_bound_cycles": (last_cycle - discharge_cycle).clip(lower=0),
        }
    )
    summary = CellLabelSummary(
        cell_id=cell_id,
        discharge_cycles=len(discharge),
        initial_capacity_ah=initial_capacity_ah,
        last_capacity_ah=float(discharge["capacity_ah"].iloc[-1]),
        minimum_soh=float(soh.min()),
        last_soh=float(soh.iloc[-1]),
        eol_threshold=threshold,
        eol_observed=eol_observed,
        eol_discharge_cycle=eol_cycle,
        censored_at_discharge_cycle=None if eol_observed else last_cycle,
    )
    return labels, summary


def prefixed_measurement_features(cycle_summary: pd.DataFrame, cycle_type: str) -> pd.DataFrame:
    excluded = {
        "dataset",
        "battery_type",
        "cell_id",
        "cycle_type",
        "cycle_number_within_type",
        "start_time",
        "capacity_ah",
    }
    source = (
        cycle_summary.loc[cycle_summary["cycle_type"].eq(cycle_type)]
        .sort_values("cycle_index")
        .copy()
    )
    columns = ["cycle_index"] + [
        column
        for column in source.columns
        if column not in excluded and column != "cycle_index"
        and source[column].notna().any()
    ]
    source = source.loc[:, columns]
    return source.rename(
        columns={
            column: f"latest_{cycle_type}_{column}"
            for column in source.columns
            if column != "cycle_index"
        }
    ).rename(columns={"cycle_index": f"latest_{cycle_type}_cycle_index"})


def merge_latest_prior_features(
    base: pd.DataFrame, cycle_summary: pd.DataFrame, cycle_type: str
) -> pd.DataFrame:
    prior = prefixed_measurement_features(cycle_summary, cycle_type)
    if prior.empty:
        return base
    merged = pd.merge_asof(
        base.sort_values("cycle_index"),
        prior.sort_values(f"latest_{cycle_type}_cycle_index"),
        left_on="cycle_index",
        right_on=f"latest_{cycle_type}_cycle_index",
        direction="backward",
        allow_exact_matches=True,
    )
    merged[f"cycles_since_latest_{cycle_type}"] = (
        merged["cycle_index"] - merged[f"latest_{cycle_type}_cycle_index"]
    )
    return merged


def build_features_for_cell(
    cycle_summary: pd.DataFrame, labels: pd.DataFrame
) -> pd.DataFrame:
    discharge = (
        cycle_summary.loc[cycle_summary["cycle_type"].eq("discharge")]
        .sort_values("cycle_index")
        .reset_index(drop=True)
        .copy()
    )
    label_columns = [
        "cycle_index",
        "discharge_cycle",
        "initial_capacity_ah",
        "soh_capacity_ratio",
        "capacity_loss_ah",
        "capacity_loss_ratio",
        "eol_threshold",
        "eol_observed",
        "eol_discharge_cycle",
        "is_eol_or_after",
        "rul_cycles",
        "rul_is_censored",
        "rul_lower_bound_cycles",
    ]
    features = discharge.merge(labels[label_columns], on="cycle_index", how="left")
    features = features.drop(columns=["cycle_type", "cycle_number_within_type"])
    features = features.rename(
        columns={
            column: f"discharge_{column}"
            for column in features.columns
            if column
            not in {
                "dataset",
                "battery_type",
                "cell_id",
                "cycle_index",
                "discharge_cycle",
                "start_time",
                "capacity_ah",
                "initial_capacity_ah",
                "soh_capacity_ratio",
                "capacity_loss_ah",
                "capacity_loss_ratio",
                "eol_threshold",
                "eol_observed",
                "eol_discharge_cycle",
                "is_eol_or_after",
                "rul_cycles",
                "rul_is_censored",
                "rul_lower_bound_cycles",
            }
        }
    )

    features = merge_latest_prior_features(features, cycle_summary, "charge")
    features = merge_latest_prior_features(features, cycle_summary, "impedance")

    features["available_discharge_history_cycles"] = features["discharge_cycle"]
    features["capacity_change_previous_ah"] = features["capacity_ah"].diff()
    features["soh_change_previous"] = features["soh_capacity_ratio"].diff()
    for window in (5, 10):
        features[f"capacity_rolling_mean_{window}_ah"] = features["capacity_ah"].rolling(
            window=window, min_periods=1
        ).mean()
        features[f"capacity_rolling_std_{window}_ah"] = features["capacity_ah"].rolling(
            window=window, min_periods=2
        ).std()
        features[f"soh_rolling_mean_{window}"] = features["soh_capacity_ratio"].rolling(
            window=window, min_periods=1
        ).mean()
        add_rolling_slope(
            features,
            "capacity_ah",
            f"capacity_slope_{window}_ah_per_cycle",
            window,
        )
        add_rolling_slope(
            features,
            "soh_capacity_ratio",
            f"soh_slope_{window}_per_cycle",
            window,
        )
    return features


def load_cell_summaries(input_root: Path) -> Iterable[tuple[str, pd.DataFrame]]:
    paths = sorted(input_root.glob("*/cycle_summary.csv"))
    if not paths:
        raise FileNotFoundError(f"No cycle_summary.csv files found under {input_root}")
    for path in paths:
        yield path.parent.name, pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate NASA lithium-ion SOH/RUL labels and cycle-level features."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("data/processed/nasa/li_ion"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/features/nasa/li_ion"),
    )
    parser.add_argument("--eol-threshold", type=float, default=0.70)
    parser.add_argument("--initial-capacity-window", type=int, default=1)
    parser.add_argument("--consecutive-eol-cycles", type=int, default=1)
    args = parser.parse_args()

    if not 0.0 < args.eol_threshold < 1.0:
        raise ValueError("--eol-threshold must be between 0 and 1.")
    if args.initial_capacity_window < 1 or args.consecutive_eol_cycles < 1:
        raise ValueError("Window and consecutive cycle arguments must be positive.")

    args.output_root.mkdir(parents=True, exist_ok=True)
    all_labels: list[pd.DataFrame] = []
    all_features: list[pd.DataFrame] = []
    summaries: list[CellLabelSummary] = []

    for cell_id, cycle_summary in load_cell_summaries(args.input_root):
        labels, summary = build_labels_for_cell(
            cycle_summary,
            threshold=args.eol_threshold,
            initial_capacity_window=args.initial_capacity_window,
            consecutive_cycles=args.consecutive_eol_cycles,
        )
        features = build_features_for_cell(cycle_summary, labels)
        cell_dir = args.output_root / cell_id
        cell_dir.mkdir(parents=True, exist_ok=True)
        labels.to_csv(cell_dir / "soh_rul_labels.csv", index=False)
        features.to_csv(cell_dir / "cycle_features.csv", index=False)
        all_labels.append(labels)
        all_features.append(features)
        summaries.append(summary)

    labels_table = pd.concat(all_labels, ignore_index=True)
    features_table = pd.concat(all_features, ignore_index=True)
    labels_table.to_csv(args.output_root / "soh_rul_labels.csv", index=False)
    features_table.to_csv(args.output_root / "cycle_features.csv", index=False)
    pd.DataFrame([asdict(item) for item in summaries]).to_csv(
        args.output_root / "label_summary.csv", index=False
    )
    with (args.output_root / "label_manifest.json").open("w", encoding="utf-8") as fh:
        json.dump([asdict(item) for item in summaries], fh, indent=2)

    for summary in summaries:
        endpoint = (
            f"EOL cycle {summary.eol_discharge_cycle}"
            if summary.eol_observed
            else f"right-censored at cycle {summary.censored_at_discharge_cycle}"
        )
        print(
            f"{summary.cell_id}: initial={summary.initial_capacity_ah:.4f} Ah, "
            f"minimum SOH={summary.minimum_soh:.4f}, {endpoint}"
        )


if __name__ == "__main__":
    main()
