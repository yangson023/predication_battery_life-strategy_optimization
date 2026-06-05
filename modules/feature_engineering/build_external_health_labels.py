"""Build SOH/RUL-style labels from external battery feature tables."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


IDENTITY_COLUMNS = [
    "dataset_id",
    "dataset_family",
    "data_category",
    "measurement_type",
    "chemistry",
    "cell_id",
    "batch_id",
    "part_id",
    "source_archive_name",
]

LABEL_CONTEXT_COLUMNS = [
    "protocol_regime_index",
    "protocol_boundary_flag",
    "protocol_boundary_reason",
]


@dataclass
class LabelBuildSummary:
    source_table: str
    label_key_prefix: str
    capacity_column: str
    group_id: str
    protocol_regime_index: object
    observations: int
    valid_capacity_observations: int
    initial_capacity_ah: float
    last_capacity_ah: float
    minimum_soh: float
    eol_threshold: float
    label_key: str
    eol_observed: bool
    eol_observation_index: float
    censored_at_observation_index: float
    duration_observations: int
    label_quality: str


def find_first_sustained_crossing(
    values: pd.Series,
    threshold: float,
    consecutive_observations: int,
) -> int | None:
    below = values.le(threshold).to_numpy()
    run_length = 0
    for index, crossed in enumerate(below):
        run_length = run_length + 1 if crossed else 0
        if run_length >= consecutive_observations:
            return index - consecutive_observations + 1
    return None


def numeric_or_nan(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def group_identity(frame: pd.DataFrame) -> dict[str, object]:
    identity = {}
    for column in [*IDENTITY_COLUMNS, *LABEL_CONTEXT_COLUMNS]:
        identity[column] = frame[column].iloc[0] if column in frame.columns else ""
    return identity


def sort_observations(frame: pd.DataFrame, observation_column: str) -> pd.DataFrame:
    sorted_frame = frame.copy()
    sorted_frame["_observation_sort_key"] = pd.to_numeric(
        sorted_frame[observation_column],
        errors="coerce",
    )
    return (
        sorted_frame.sort_values(["_observation_sort_key", observation_column], na_position="last")
        .drop(columns=["_observation_sort_key"])
        .reset_index(drop=True)
    )


def label_quality_for_group(
    valid_capacity: pd.Series,
    initial_capacity: float,
    minimum_observations_for_training: int,
) -> str:
    if valid_capacity.empty:
        return "invalid_no_positive_capacity"
    if not np.isfinite(initial_capacity) or initial_capacity <= 0:
        return "invalid_initial_capacity"
    if len(valid_capacity) < minimum_observations_for_training:
        return f"limited_window_less_than_{minimum_observations_for_training}_observations"
    if len(valid_capacity) < 3:
        return "sample_only_less_than_3_observations"
    return "usable"


def build_labels_for_feature_group(
    group: pd.DataFrame,
    source_table: str,
    label_key_prefix: str,
    observation_column: str,
    capacity_column: str,
    thresholds: list[float],
    initial_capacity_window: int,
    consecutive_eol_observations: int,
    minimum_valid_capacity_ah: float,
    minimum_observations_for_training: int = 3,
) -> tuple[pd.DataFrame, list[LabelBuildSummary]]:
    group = sort_observations(group, observation_column)
    capacity = pd.to_numeric(group[capacity_column], errors="coerce")
    valid_capacity = capacity.loc[capacity.gt(minimum_valid_capacity_ah)]
    initial_capacity = (
        float(valid_capacity.head(initial_capacity_window).mean())
        if not valid_capacity.empty
        else np.nan
    )
    quality = label_quality_for_group(
        valid_capacity,
        initial_capacity,
        minimum_observations_for_training,
    )
    labels_by_threshold = []
    summaries = []

    identity = group_identity(group)
    observation_values = pd.to_numeric(group[observation_column], errors="coerce")
    fallback_observation_numbers = pd.Series(np.arange(1, len(group) + 1), index=group.index)
    observation_numbers = observation_values.fillna(fallback_observation_numbers)
    last_observation_number = float(observation_numbers.iloc[-1]) if len(observation_numbers) else np.nan
    group_id = "|".join(
        str(identity.get(column, ""))
        for column in ["dataset_id", "cell_id", "source_archive_name", "protocol_regime_index"]
        if identity.get(column, "") != ""
    )
    label_context = {
        column: group[column].reset_index(drop=True)
        for column in LABEL_CONTEXT_COLUMNS
        if column in group.columns
    }

    for threshold in thresholds:
        label_key = f"{label_key_prefix}_eol_{int(round(threshold * 100))}"
        if quality.startswith("invalid"):
            soh = pd.Series([np.nan] * len(group), index=group.index)
            crossing_position = None
        else:
            usable_capacity = capacity.where(capacity.gt(minimum_valid_capacity_ah))
            soh = usable_capacity / initial_capacity
            crossing_position = find_first_sustained_crossing(
                soh,
                threshold,
                consecutive_eol_observations,
            )

        eol_observed = crossing_position is not None
        eol_observation_number = (
            float(observation_numbers.iloc[crossing_position])
            if crossing_position is not None
            else np.nan
        )
        lower_bound = (last_observation_number - observation_numbers).clip(lower=0)
        rul = (
            (eol_observation_number - observation_numbers).clip(lower=0)
            if eol_observed
            else pd.Series([np.nan] * len(group), index=group.index)
        )
        duration = (
            (eol_observation_number - observation_numbers).clip(lower=0)
            if eol_observed
            else lower_bound
        )

        label_frame = pd.DataFrame(
            {
                **{column: identity.get(column, "") for column in IDENTITY_COLUMNS},
                **label_context,
                "source_table": source_table,
                "label_key": label_key,
                "label_key_prefix": label_key_prefix,
                "label_source_column": capacity_column,
                "observation_column": observation_column,
                "observation_index": group[observation_column],
                "observation_number": observation_numbers,
                "capacity_ah": capacity,
                "initial_capacity_ah": initial_capacity,
                "soh_capacity_ratio": soh,
                "capacity_loss_ah": initial_capacity - capacity.where(
                    capacity.gt(minimum_valid_capacity_ah)
                ),
                "capacity_loss_ratio": 1.0 - soh,
                "eol_threshold": threshold,
                "eol_consecutive_observations": consecutive_eol_observations,
                "eol_observed": eol_observed,
                "eol_observation_index": eol_observation_number,
                "is_eol_or_after": (
                    observation_numbers.ge(eol_observation_number) if eol_observed else False
                ),
                "rul_observations": rul,
                "rul_is_censored": not eol_observed,
                "rul_lower_bound_observations": lower_bound,
                "event_observed": eol_observed,
                "duration_observations": duration,
                "label_quality": quality,
            }
        )
        labels_by_threshold.append(label_frame)
        summaries.append(
            LabelBuildSummary(
                source_table=source_table,
                label_key_prefix=label_key_prefix,
                capacity_column=capacity_column,
                group_id=group_id,
                protocol_regime_index=identity.get("protocol_regime_index", ""),
                observations=int(len(group)),
                valid_capacity_observations=int(len(valid_capacity)),
                initial_capacity_ah=initial_capacity,
                last_capacity_ah=float(capacity.dropna().iloc[-1]) if capacity.notna().any() else np.nan,
                minimum_soh=float(soh.min(skipna=True)) if soh.notna().any() else np.nan,
                eol_threshold=threshold,
                label_key=label_key,
                eol_observed=eol_observed,
                eol_observation_index=eol_observation_number,
                censored_at_observation_index=np.nan if eol_observed else last_observation_number,
                duration_observations=(
                    int(eol_observation_number)
                    if eol_observed and np.isfinite(eol_observation_number)
                    else int(last_observation_number)
                    if np.isfinite(last_observation_number)
                    else 0
                ),
                label_quality=quality,
            )
        )
    return pd.concat(labels_by_threshold, ignore_index=True), summaries


def build_labels_from_feature_table(
    frame: pd.DataFrame,
    source_table: str,
    label_key_prefix: str,
    observation_column: str,
    capacity_column: str,
    thresholds: list[float],
    initial_capacity_window: int,
    consecutive_eol_observations: int,
    minimum_valid_capacity_ah: float,
    minimum_observations_for_training: int = 3,
) -> tuple[pd.DataFrame, list[LabelBuildSummary]]:
    if frame.empty:
        return pd.DataFrame(), []
    if observation_column not in frame.columns:
        raise ValueError(f"Missing observation column: {observation_column}")
    if capacity_column not in frame.columns:
        raise ValueError(f"Missing capacity column: {capacity_column}")
    group_columns = [
        column
        for column in ["dataset_id", "cell_id", "source_archive_name", "protocol_regime_index"]
        if column in frame.columns
    ]
    all_labels = []
    all_summaries = []
    for _, group in frame.groupby(group_columns, dropna=False, sort=True):
        labels, summaries = build_labels_for_feature_group(
            group=group,
            source_table=source_table,
            label_key_prefix=label_key_prefix,
            observation_column=observation_column,
            capacity_column=capacity_column,
            thresholds=thresholds,
            initial_capacity_window=initial_capacity_window,
            consecutive_eol_observations=consecutive_eol_observations,
            minimum_valid_capacity_ah=minimum_valid_capacity_ah,
            minimum_observations_for_training=minimum_observations_for_training,
        )
        all_labels.append(labels)
        all_summaries.extend(summaries)
    return pd.concat(all_labels, ignore_index=True), all_summaries


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def write_json(path: Path, content: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(content), ensure_ascii=False, indent=2), encoding="utf-8")


def build_external_health_labels(
    input_root: Path,
    output_root: Path,
    thresholds: list[float],
    initial_capacity_window: int,
    consecutive_eol_observations: int,
    minimum_valid_capacity_ah: float,
    cycle_capacity_column: str,
    rpt_capacity_column: str,
    source_mode: str = "sample",
    minimum_observations_for_training: int = 50,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    suffix = "_sample" if source_mode == "sample" else ""
    jobs = [
        {
            "source_table": f"cycle_features{suffix}.csv",
            "path": input_root / f"cycle_features{suffix}.csv",
            "label_key_prefix": "capacity",
            "observation_column": "cycle_index",
            "capacity_column": cycle_capacity_column,
        },
        {
            "source_table": f"rpt_features{suffix}.csv",
            "path": input_root / f"rpt_features{suffix}.csv",
            "label_key_prefix": "rpt_capacity",
            "observation_column": "diagnostic_part",
            "capacity_column": rpt_capacity_column,
        },
    ]
    all_labels = []
    all_summaries = []
    for job in jobs:
        if not job["path"].exists():
            continue
        frame = pd.read_csv(job["path"])
        labels, summaries = build_labels_from_feature_table(
            frame=frame,
            source_table=job["source_table"],
            label_key_prefix=job["label_key_prefix"],
            observation_column=job["observation_column"],
            capacity_column=job["capacity_column"],
            thresholds=thresholds,
            initial_capacity_window=initial_capacity_window,
            consecutive_eol_observations=consecutive_eol_observations,
            minimum_valid_capacity_ah=minimum_valid_capacity_ah,
            minimum_observations_for_training=minimum_observations_for_training,
        )
        all_labels.append(labels)
        all_summaries.extend(summaries)
    labels_table = pd.concat(all_labels, ignore_index=True) if all_labels else pd.DataFrame()
    summary_table = pd.DataFrame([asdict(summary) for summary in all_summaries])

    output_root.mkdir(parents=True, exist_ok=True)
    write_csv(labels_table, output_root / f"external_health_labels{suffix}.csv")
    write_csv(summary_table, output_root / f"external_label_summary{suffix}.csv")
    write_json(
        output_root / f"external_label_manifest{suffix}.json",
        {
            "source_mode": source_mode,
            "thresholds": thresholds,
            "initial_capacity_window": initial_capacity_window,
            "consecutive_eol_observations": consecutive_eol_observations,
            "minimum_valid_capacity_ah": minimum_valid_capacity_ah,
            "minimum_observations_for_training": minimum_observations_for_training,
            "cycle_capacity_column": cycle_capacity_column,
            "rpt_capacity_column": rpt_capacity_column,
            "summaries": [asdict(summary) for summary in all_summaries],
        },
    )
    return labels_table, summary_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build external SOH/RUL labels from feature tables."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("data/features/external_battery_datasets"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/features/external_battery_datasets"),
    )
    parser.add_argument(
        "--eol-thresholds",
        type=float,
        nargs="+",
        default=[0.70, 0.75, 0.80],
    )
    parser.add_argument("--initial-capacity-window", type=int, default=1)
    parser.add_argument("--consecutive-eol-observations", type=int, default=1)
    parser.add_argument("--minimum-valid-capacity-ah", type=float, default=1e-6)
    parser.add_argument(
        "--minimum-observations-for-training",
        type=int,
        default=50,
        help="Groups below this count are marked as limited-window labels.",
    )
    parser.add_argument("--cycle-capacity-column", default="capacity_delta_ah")
    parser.add_argument("--rpt-capacity-column", default="capacity_delta_ah")
    parser.add_argument(
        "--source-mode",
        choices=["sample", "by_cell"],
        default="sample",
        help="Use sample feature files or non-sample per-cell feature files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    thresholds = sorted(set(args.eol_thresholds))
    if any(threshold <= 0 or threshold >= 1 for threshold in thresholds):
        raise ValueError("EOL thresholds must be between 0 and 1.")
    if args.initial_capacity_window < 1 or args.consecutive_eol_observations < 1:
        raise ValueError("Window and consecutive observation arguments must be positive.")
    labels, summary = build_external_health_labels(
        input_root=args.input_root,
        output_root=args.output_root,
        thresholds=thresholds,
        initial_capacity_window=args.initial_capacity_window,
        consecutive_eol_observations=args.consecutive_eol_observations,
        minimum_valid_capacity_ah=args.minimum_valid_capacity_ah,
        cycle_capacity_column=args.cycle_capacity_column,
        rpt_capacity_column=args.rpt_capacity_column,
        source_mode=args.source_mode,
        minimum_observations_for_training=args.minimum_observations_for_training,
    )
    suffix = "_sample" if args.source_mode == "sample" else ""
    print(
        f"external_health_labels{suffix}.csv: rows={len(labels)}, "
        f"summary_rows={len(summary)}"
    )


if __name__ == "__main__":
    main()
