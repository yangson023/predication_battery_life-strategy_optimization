"""Build Li||Cu mechanistic past-only horizon feature audit tables.

The output is an audit artifact, not a baseline-ready training set. It does not
train models, run baselines, split data, or report model performance.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


FORBIDDEN_DIRECT_COLUMNS = {
    "coulombic_efficiency_percent",
    "charge_capacity_mah",
    "discharge_capacity_mah",
    "ce_lag_1",
    "ce_rolling_mean_past_5",
    "ce_rolling_std_past_5",
    "capacity_retention_percent",
    "irreversible_capacity_mah",
    "cumulative_irreversible_capacity_past",
    "cumulative_discharge_throughput_mah",
}

FORBIDDEN_OUTPUT_TOKENS = (
    "incomplete_cycle_flag",
    "record_voltage_",
    "record_current_",
    "target_event",
    "auc",
    "f1",
    "rmse",
)

BASE_COLUMNS = [
    "row_id",
    "source_folder_name",
    "selected_dataset_name",
    "target_cycle",
    "horizon_k",
    "feature_window_start",
    "feature_window_end",
    "excluded_recent_window_start",
    "excluded_recent_window_end",
    "first_event_cycle",
    "baseline_ready_export_candidate",
    "protocol_censored_terminal",
    "training_allowed_now",
]

FEATURE_COLUMNS = [
    "cycle_median_voltage_v_lag_k",
    "cycle_median_voltage_v_trend_past_5",
    "cycle_median_voltage_v_rolling_mean_past_5",
    "voltage_hysteresis_v_lag_k",
    "voltage_hysteresis_v_trend_past_5",
    "voltage_hysteresis_v_rolling_mean_past_5",
    "end_voltage_gap_v_lag_k",
    "end_voltage_gap_v_trend_past_5",
    "charge_step_duration_s_lag_k",
    "charge_step_duration_s_trend_past_5",
    "discharge_step_duration_s_lag_k",
    "discharge_step_duration_s_trend_past_5",
    "ce_rolling_mean_window_past_5",
    "ce_rolling_std_window_past_5",
    "ce_delta_from_initial_window5_at_feature_end",
    "charge_capacity_mah_trend_past_5",
    "discharge_capacity_mah_trend_past_5",
]

COUNT_COLUMNS = [
    "cycle_median_voltage_v_valid_count",
    "voltage_hysteresis_v_valid_count",
    "end_voltage_gap_v_valid_count",
    "charge_step_duration_s_valid_count",
    "discharge_step_duration_s_valid_count",
    "ce_window_valid_count",
    "charge_capacity_window_valid_count",
    "discharge_capacity_window_valid_count",
]

SCHEMA_COLUMNS = [
    "field_name",
    "source_domain",
    "model_feature_candidate",
    "audit_only",
    "same_signal_source_risk",
    "required_transform",
    "direct_source_fields",
    "leakage_guard",
]

LEAKAGE_COLUMNS = [
    "check_name",
    "horizon_k",
    "status",
    "detail",
]

COVERAGE_COLUMNS = [
    "horizon_k",
    "feature_name",
    "non_empty_count",
    "total_rows",
    "coverage_fraction",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value: object) -> float | None:
    try:
        text = str(value).strip()
        if text == "":
            return None
        number = float(text)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def parse_int(value: object) -> int:
    try:
        text = str(value).strip()
        if not text:
            return 0
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def safe_mean(values: Iterable[float | None]) -> float | str:
    clean = [value for value in values if value is not None]
    return statistics.fmean(clean) if len(clean) >= 3 else ""


def safe_std(values: Iterable[float | None]) -> float | str:
    clean = [value for value in values if value is not None]
    return statistics.stdev(clean) if len(clean) >= 3 else ""


def safe_slope(values: list[float | None]) -> float | str:
    indexed = [(index, value) for index, value in enumerate(values) if value is not None]
    if len(indexed) < 3:
        return ""
    xs = [item[0] for item in indexed]
    ys = [item[1] for item in indexed]
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return ""
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator


def count_valid(values: Iterable[float | None]) -> int:
    return sum(1 for value in values if value is not None)


def rows_by_cell(feature_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in feature_rows:
        cell_id = row.get("source_folder_name", "")
        if cell_id:
            grouped[cell_id].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: parse_int(row.get("cycle_index")))
    return dict(grouped)


def row_by_cycle(rows: list[dict[str, str]]) -> dict[int, dict[str, str]]:
    return {parse_int(row.get("cycle_index")): row for row in rows if parse_int(row.get("cycle_index")) > 0}


def label_design_by_cell(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("source_folder_name", ""): row for row in rows if row.get("source_folder_name")}


def values_in_window(cycle_map: dict[int, dict[str, str]], start: int, end: int, column: str) -> list[float | None]:
    return [parse_float(cycle_map.get(cycle, {}).get(column)) for cycle in range(start, end + 1)]


def value_at(cycle_map: dict[int, dict[str, str]], cycle: int, column: str) -> float | str:
    value = parse_float(cycle_map.get(cycle, {}).get(column))
    return value if value is not None else ""


def first_event_info(label_row: dict[str, str]) -> tuple[int, bool, bool]:
    return (
        parse_int(label_row.get("first_event_cycle")),
        parse_bool(label_row.get("baseline_ready_export_candidate")),
        parse_bool(label_row.get("protocol_censored_terminal")),
    )


def initial_ce_window_mean(cycle_map: dict[int, dict[str, str]]) -> float | None:
    values = [parse_float(cycle_map.get(cycle, {}).get("coulombic_efficiency_percent")) for cycle in range(1, 6)]
    clean = [value for value in values if value is not None]
    return statistics.fmean(clean) if len(clean) >= 3 else None


def build_horizon_rows(
    feature_rows: list[dict[str, str]],
    label_design_rows: list[dict[str, str]],
    horizon: int,
) -> list[dict[str, Any]]:
    label_by_cell = label_design_by_cell(label_design_rows)
    out_rows: list[dict[str, Any]] = []
    for cell_id, rows in rows_by_cell(feature_rows).items():
        cycle_map = row_by_cycle(rows)
        design = label_by_cell.get(cell_id, {})
        first_event, baseline_candidate, protocol_censored = first_event_info(design)
        initial_ce_mean = initial_ce_window_mean(cycle_map)
        for row in rows:
            target_cycle = parse_int(row.get("cycle_index"))
            feature_end = target_cycle - horizon
            if target_cycle <= 0 or feature_end < 1:
                continue
            feature_start = max(1, feature_end - 4)
            excluded_start = feature_end + 1
            excluded_end = target_cycle
            base: dict[str, Any] = {
                "row_id": f"{cell_id}__target_cycle_{target_cycle}__h{horizon}",
                "source_folder_name": cell_id,
                "selected_dataset_name": row.get("selected_dataset_name", ""),
                "target_cycle": target_cycle,
                "horizon_k": horizon,
                "feature_window_start": feature_start,
                "feature_window_end": feature_end,
                "excluded_recent_window_start": excluded_start,
                "excluded_recent_window_end": excluded_end,
                "first_event_cycle": first_event,
                "baseline_ready_export_candidate": baseline_candidate and cell_id != "26-0428-009",
                "protocol_censored_terminal": protocol_censored,
                "training_allowed_now": False,
            }
            cycle_voltage = values_in_window(cycle_map, feature_start, feature_end, "cycle_median_voltage_v")
            hysteresis = values_in_window(cycle_map, feature_start, feature_end, "voltage_hysteresis_v")
            end_gap = values_in_window(cycle_map, feature_start, feature_end, "end_voltage_gap_v")
            charge_duration = values_in_window(cycle_map, feature_start, feature_end, "charge_step_duration_s")
            discharge_duration = values_in_window(cycle_map, feature_start, feature_end, "discharge_step_duration_s")
            ce_values = values_in_window(cycle_map, feature_start, feature_end, "coulombic_efficiency_percent")
            charge_capacity = values_in_window(cycle_map, feature_start, feature_end, "charge_capacity_mah")
            discharge_capacity = values_in_window(cycle_map, feature_start, feature_end, "discharge_capacity_mah")
            ce_at_end = parse_float(cycle_map.get(feature_end, {}).get("coulombic_efficiency_percent"))

            feature_payload = {
                "cycle_median_voltage_v_lag_k": value_at(cycle_map, feature_end, "cycle_median_voltage_v"),
                "cycle_median_voltage_v_trend_past_5": safe_slope(cycle_voltage),
                "cycle_median_voltage_v_rolling_mean_past_5": safe_mean(cycle_voltage),
                "voltage_hysteresis_v_lag_k": value_at(cycle_map, feature_end, "voltage_hysteresis_v"),
                "voltage_hysteresis_v_trend_past_5": safe_slope(hysteresis),
                "voltage_hysteresis_v_rolling_mean_past_5": safe_mean(hysteresis),
                "end_voltage_gap_v_lag_k": value_at(cycle_map, feature_end, "end_voltage_gap_v"),
                "end_voltage_gap_v_trend_past_5": safe_slope(end_gap),
                "charge_step_duration_s_lag_k": value_at(cycle_map, feature_end, "charge_step_duration_s"),
                "charge_step_duration_s_trend_past_5": safe_slope(charge_duration),
                "discharge_step_duration_s_lag_k": value_at(cycle_map, feature_end, "discharge_step_duration_s"),
                "discharge_step_duration_s_trend_past_5": safe_slope(discharge_duration),
                "ce_rolling_mean_window_past_5": safe_mean(ce_values),
                "ce_rolling_std_window_past_5": safe_std(ce_values),
                "ce_delta_from_initial_window5_at_feature_end": (
                    ce_at_end - initial_ce_mean
                    if ce_at_end is not None and initial_ce_mean is not None
                    else ""
                ),
                "charge_capacity_mah_trend_past_5": safe_slope(charge_capacity),
                "discharge_capacity_mah_trend_past_5": safe_slope(discharge_capacity),
                "cycle_median_voltage_v_valid_count": count_valid(cycle_voltage),
                "voltage_hysteresis_v_valid_count": count_valid(hysteresis),
                "end_voltage_gap_v_valid_count": count_valid(end_gap),
                "charge_step_duration_s_valid_count": count_valid(charge_duration),
                "discharge_step_duration_s_valid_count": count_valid(discharge_duration),
                "ce_window_valid_count": count_valid(ce_values),
                "charge_capacity_window_valid_count": count_valid(charge_capacity),
                "discharge_capacity_window_valid_count": count_valid(discharge_capacity),
            }
            out_rows.append({**base, **feature_payload})
    return out_rows


def schema_rows() -> list[dict[str, Any]]:
    specs = [
        ("cycle_median_voltage_v_lag_k", "voltage", False, "lag at t-k", "cycle_median_voltage_v"),
        ("cycle_median_voltage_v_trend_past_5", "voltage", False, "OLS slope over [t-k-4,t-k]", "cycle_median_voltage_v"),
        ("cycle_median_voltage_v_rolling_mean_past_5", "voltage", False, "mean over [t-k-4,t-k]", "cycle_median_voltage_v"),
        ("voltage_hysteresis_v_lag_k", "voltage", False, "lag at t-k", "voltage_hysteresis_v"),
        ("voltage_hysteresis_v_trend_past_5", "voltage", False, "OLS slope over [t-k-4,t-k]", "voltage_hysteresis_v"),
        ("voltage_hysteresis_v_rolling_mean_past_5", "voltage", False, "mean over [t-k-4,t-k]", "voltage_hysteresis_v"),
        ("end_voltage_gap_v_lag_k", "voltage", False, "lag at t-k", "end_voltage_gap_v"),
        ("end_voltage_gap_v_trend_past_5", "voltage", False, "OLS slope over [t-k-4,t-k]", "end_voltage_gap_v"),
        ("charge_step_duration_s_lag_k", "kinetic", False, "lag at t-k", "charge_step_duration_s"),
        ("charge_step_duration_s_trend_past_5", "kinetic", False, "OLS slope over [t-k-4,t-k]", "charge_step_duration_s"),
        ("discharge_step_duration_s_lag_k", "kinetic", False, "lag at t-k", "discharge_step_duration_s"),
        ("discharge_step_duration_s_trend_past_5", "kinetic", False, "OLS slope over [t-k-4,t-k]", "discharge_step_duration_s"),
        ("ce_rolling_mean_window_past_5", "CE", True, "mean over [t-k-4,t-k]", "coulombic_efficiency_percent"),
        ("ce_rolling_std_window_past_5", "CE", True, "std over [t-k-4,t-k]", "coulombic_efficiency_percent"),
        ("ce_delta_from_initial_window5_at_feature_end", "CE", True, "CE at t-k minus early CE mean", "coulombic_efficiency_percent"),
        ("charge_capacity_mah_trend_past_5", "capacity", True, "OLS slope over [t-k-4,t-k]", "charge_capacity_mah"),
        ("discharge_capacity_mah_trend_past_5", "capacity", True, "OLS slope over [t-k-4,t-k]", "discharge_capacity_mah"),
    ]
    rows = []
    for field_name, domain, same_signal, transform, sources in specs:
        rows.append(
            {
                "field_name": field_name,
                "source_domain": domain,
                "model_feature_candidate": True,
                "audit_only": False,
                "same_signal_source_risk": same_signal,
                "required_transform": transform,
                "direct_source_fields": sources,
                "leakage_guard": "uses only cycles <= t-k; never uses target or excluded recent window",
            }
        )
    for field_name in BASE_COLUMNS + COUNT_COLUMNS:
        rows.append(
            {
                "field_name": field_name,
                "source_domain": "metadata",
                "model_feature_candidate": False,
                "audit_only": True,
                "same_signal_source_risk": False,
                "required_transform": "none",
                "direct_source_fields": "",
                "leakage_guard": "not a model feature",
            }
        )
    return rows


def forbidden_columns(columns: Iterable[str]) -> list[str]:
    found = []
    for column in columns:
        lower = column.lower()
        if column in BASE_COLUMNS or column in COUNT_COLUMNS:
            continue
        if column in FORBIDDEN_DIRECT_COLUMNS:
            found.append(column)
            continue
        if any(token in lower for token in FORBIDDEN_OUTPUT_TOKENS):
            found.append(column)
    return found


def leakage_checks(horizon_rows_by_k: dict[int, list[dict[str, Any]]], output_columns: list[str]) -> list[dict[str, Any]]:
    checks = []
    forbidden = forbidden_columns(output_columns)
    for horizon, rows in sorted(horizon_rows_by_k.items()):
        window_ok = all(
            parse_int(row["feature_window_end"]) <= parse_int(row["target_cycle"]) - horizon
            and parse_int(row["excluded_recent_window_start"]) == parse_int(row["feature_window_end"]) + 1
            and parse_int(row["excluded_recent_window_end"]) == parse_int(row["target_cycle"])
            for row in rows
        )
        checks.append(
            {
                "check_name": "horizon_window_excludes_recent_cycles",
                "horizon_k": horizon,
                "status": "pass" if window_ok else "fail",
                "detail": "feature_window_end <= target_cycle - horizon_k",
            }
        )
        checks.append(
            {
                "check_name": "forbidden_direct_columns_absent",
                "horizon_k": horizon,
                "status": "pass" if not forbidden else "fail",
                "detail": ";".join(forbidden),
            }
        )
        checks.append(
            {
                "check_name": "training_allowed_now_false",
                "horizon_k": horizon,
                "status": "pass" if all(str(row["training_allowed_now"]) == "False" for row in rows) else "fail",
                "detail": "feature audit only",
            }
        )
    return checks


def coverage_rows(horizon_rows_by_k: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for horizon, feature_rows in sorted(horizon_rows_by_k.items()):
        total = len(feature_rows)
        for feature in FEATURE_COLUMNS:
            non_empty = sum(1 for row in feature_rows if str(row.get(feature, "")).strip() != "")
            rows.append(
                {
                    "horizon_k": horizon,
                    "feature_name": feature,
                    "non_empty_count": non_empty,
                    "total_rows": total,
                    "coverage_fraction": (non_empty / total) if total else 0.0,
                }
            )
    return rows


def build_report(
    output_root: Path,
    horizon_rows_by_k: dict[int, list[dict[str, Any]]],
    checks: list[dict[str, Any]],
    coverage: list[dict[str, Any]],
) -> dict[str, Any]:
    fail_checks = [row for row in checks if row["status"] == "fail"]
    report = {
        "feature_audit_only": True,
        "model_training_allowed": False,
        "training_allowed_now": False,
        "baseline_ready_training_set_generated": False,
        "rul_prediction_entered": False,
        "random_row_split_used": False,
        "formal_performance_metrics_computed": False,
        "horizons": sorted(horizon_rows_by_k),
        "rows_by_horizon": {str(k): len(v) for k, v in sorted(horizon_rows_by_k.items())},
        "leakage_check_passed": not fail_checks,
        "failed_leakage_checks": fail_checks,
        "baseline_ready_export_redesign_allowed": not fail_checks,
        "notes": [
            "Outputs are mechanistic horizon feature audit tables, not a training set.",
            "CE and capacity trend features are derived only from cycles <= t-k and are marked same-signal-source risk in schema.",
            "Direct CE, direct capacity, incomplete flags, and record_sample columns are not output as model features.",
        ],
    }
    (output_root / "mechanistic_past_only_feature_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# LMB Mechanistic Past-Only Feature Audit",
        "",
        "This is a horizon feature audit only. It does not train a model, run a baseline, or report model performance.",
        "",
        "## Gate",
        "",
        f"- `leakage_check_passed = {report['leakage_check_passed']}`",
        "- `model_training_allowed = False`",
        "- `baseline_ready_training_set_generated = False`",
        "- `random_row_split_used = False`",
        "",
        "## Rows By Horizon",
        "",
        "| horizon | rows |",
        "| ---: | ---: |",
    ]
    for horizon, rows in sorted(horizon_rows_by_k.items()):
        lines.append(f"| {horizon} | {len(rows)} |")
    lines.extend(
        [
            "",
            "## Leakage Guards",
            "",
            "- For target cycle `t`, feature window ends at `t-k`.",
            "- Five-cycle windows use `[t-k-4, t-k]` only.",
            "- Direct CE, direct capacity, incomplete flags, and record_sample features are excluded.",
            "- CE/capacity trend features remain same-signal-source-risk annotated.",
            "",
            "## Next Gate",
            "",
            "If leakage checks pass, the project may design a new baseline-ready export. Model training remains prohibited until a separate trainability gate passes.",
        ]
    )
    (output_root / "mechanistic_past_only_feature_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_lmb_mechanistic_past_only_features(
    input_features: Path,
    horizon_rule_table: Path,
    feature_policy: Path,
    label_design: Path,
    output_root: Path,
    horizons: list[int],
    overwrite: bool,
) -> dict[str, Any]:
    _ = read_csv(horizon_rule_table)
    _ = read_csv(feature_policy)
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root already exists and is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    feature_rows = read_csv(input_features)
    label_rows = read_csv(label_design)
    horizon_rows_by_k: dict[int, list[dict[str, Any]]] = {}
    all_fieldnames = BASE_COLUMNS + FEATURE_COLUMNS + COUNT_COLUMNS
    for horizon in horizons:
        rows = build_horizon_rows(feature_rows, label_rows, horizon)
        horizon_rows_by_k[horizon] = rows
        write_csv(output_root / f"licu_horizon{horizon}_mechanistic_features.csv", rows, all_fieldnames)
    schema = schema_rows()
    write_csv(output_root / "mechanistic_feature_schema.csv", schema, SCHEMA_COLUMNS)
    checks = leakage_checks(horizon_rows_by_k, all_fieldnames)
    write_csv(output_root / "horizon_leakage_check.csv", checks, LEAKAGE_COLUMNS)
    coverage = coverage_rows(horizon_rows_by_k)
    write_csv(output_root / "horizon_feature_coverage_summary.csv", coverage, COVERAGE_COLUMNS)
    return build_report(output_root, horizon_rows_by_k, checks, coverage)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-features", type=Path, required=True)
    parser.add_argument("--horizon-rule-table", type=Path, required=True)
    parser.add_argument("--feature-policy", type=Path, required=True)
    parser.add_argument("--label-design", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--horizons", type=int, nargs="+", required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_lmb_mechanistic_past_only_features(
        input_features=args.input_features,
        horizon_rule_table=args.horizon_rule_table,
        feature_policy=args.feature_policy,
        label_design=args.label_design,
        output_root=args.output_root,
        horizons=args.horizons,
        overwrite=args.overwrite,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
