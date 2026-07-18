"""Scan audit-only lithium metal battery label candidates.

This script reads canonical LMB feature tables and emits reviewable event
scans. It does not create trainable labels, train models, split rows, or enter
the RUL prediction pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


LI_CU_LABEL_KEYS = [
    "incomplete_capacity_event",
    "ce_collapse",
    "ce_instability",
    "ce_sustained_degradation",
    "protocol_censored",
]

LI_LI_LABEL_KEYS = [
    "polarization_growth",
    "voltage_hysteresis_failure",
    "voltage_instability",
    "soft_short_warning",
    "protocol_censored",
]

SCAN_COLUMNS = [
    "cell_group",
    "source_folder_name",
    "selected_dataset_name",
    "cycle_index",
    "label_key",
    "audit_status",
    "signal_value",
    "threshold",
    "sustained_window",
    "observed_candidate",
    "censored_candidate",
    "protocol_censored",
    "limited_window_label",
    "audit_only",
    "trainable_label",
    "leakage_risk",
    "readiness",
    "evidence",
]

SUMMARY_COLUMNS = [
    "cell_group",
    "source_folder_name",
    "selected_dataset_name",
    "label_key",
    "rows_scanned",
    "observed_candidate_count",
    "censored_candidate_count",
    "limited_window_count",
    "protocol_censored_count",
    "first_observed_candidate_cycle",
    "last_cycle_index",
    "readiness",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
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
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def parse_int(value: object) -> int | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def format_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 6)
    return value


def median(values: Iterable[float]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return statistics.median(clean)


def group_feature_rows(rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row.get("source_folder_name", ""), row.get("selected_dataset_name", ""))
        grouped[key].append(row)
    for key, group_rows in grouped.items():
        grouped[key] = sorted(group_rows, key=lambda row: parse_int(row.get("cycle_index")) or 0)
    return grouped


def scan_row(
    *,
    cell_group: str,
    row: dict[str, str],
    label_key: str,
    audit_status: str,
    signal_value: object = "",
    threshold: object = "",
    sustained_window: object = "",
    observed_candidate: bool = False,
    censored_candidate: bool = False,
    protocol_censored: bool = False,
    limited_window_label: bool = False,
    leakage_risk: str = "low",
    readiness: str = "audit_only",
    evidence: str = "",
) -> dict[str, object]:
    return {
        "cell_group": cell_group,
        "source_folder_name": row.get("source_folder_name", ""),
        "selected_dataset_name": row.get("selected_dataset_name", ""),
        "cycle_index": row.get("cycle_index", ""),
        "label_key": label_key,
        "audit_status": audit_status,
        "signal_value": format_value(signal_value),
        "threshold": threshold,
        "sustained_window": sustained_window,
        "observed_candidate": observed_candidate,
        "censored_candidate": censored_candidate,
        "protocol_censored": protocol_censored,
        "limited_window_label": limited_window_label,
        "audit_only": True,
        "trainable_label": False,
        "leakage_risk": leakage_risk,
        "readiness": readiness,
        "evidence": evidence,
    }


def future_values(rows: list[dict[str, str]], start_index: int, column: str, window: int) -> list[float]:
    values: list[float] = []
    for future_row in rows[start_index + 1 : start_index + 1 + window]:
        value = parse_float(future_row.get(column))
        if value is not None:
            values.append(value)
    return values


def scan_licu_rows(
    rows: list[dict[str, str]],
    *,
    future_window: int,
    ce_collapse_threshold: float,
    ce_instability_std_threshold: float,
    ce_degradation_threshold: float,
) -> list[dict[str, object]]:
    scan_rows: list[dict[str, object]] = []
    last_row = rows[-1] if rows else {}
    for index, row in enumerate(rows):
        incomplete = parse_bool(row.get("incomplete_cycle_flag")) or parse_bool(row.get("exclude_from_label_training"))
        charge = parse_float(row.get("charge_capacity_mah"))
        discharge = parse_float(row.get("discharge_capacity_mah"))
        if charge is not None and discharge is not None and (charge <= 0 or discharge <= 0):
            incomplete = True
        scan_rows.append(
            scan_row(
                cell_group="Li||Cu",
                row=row,
                label_key="incomplete_capacity_event",
                audit_status="observed_candidate" if incomplete else "not_observed",
                signal_value=f"charge={format_value(charge)};discharge={format_value(discharge)}",
                threshold="incomplete flag or nonpositive charge/discharge capacity",
                sustained_window=1,
                observed_candidate=incomplete,
                censored_candidate=not incomplete,
                leakage_risk="low_to_medium",
                readiness="candidate_audit_first",
                evidence="capacity completeness signal",
            )
        )

        future_ce = future_values(rows, index, "coulombic_efficiency_percent", future_window)
        limited = len(future_ce) < future_window
        collapsed = len(future_ce) > 0 and min(future_ce) < ce_collapse_threshold
        scan_rows.append(
            scan_row(
                cell_group="Li||Cu",
                row=row,
                label_key="ce_collapse",
                audit_status="observed_candidate" if collapsed else ("limited_window" if limited else "not_observed"),
                signal_value=min(future_ce) if future_ce else "",
                threshold=ce_collapse_threshold,
                sustained_window=f"future_{future_window}_cycles",
                observed_candidate=collapsed,
                censored_candidate=not collapsed,
                limited_window_label=limited,
                leakage_risk="high_if_current_ce_is_used_as_label",
                readiness="audit_only_time_shift_required",
                evidence="future CE minimum; current cycle CE is not used as the event decision",
            )
        )

        ce_std = parse_float(row.get("ce_rolling_std_past_5"))
        ce_warning = parse_bool(row.get("ce_warning_flag"))
        unstable = ce_warning or (ce_std is not None and ce_std > ce_instability_std_threshold)
        scan_rows.append(
            scan_row(
                cell_group="Li||Cu",
                row=row,
                label_key="ce_instability",
                audit_status="observed_candidate" if unstable else "not_observed",
                signal_value=ce_std,
                threshold=f"ce_warning_flag or past rolling std > {ce_instability_std_threshold}",
                sustained_window="past_5_cycles",
                observed_candidate=unstable,
                censored_candidate=not unstable,
                leakage_risk="medium",
                readiness="audit_only_threshold_review_required",
                evidence="past-only CE volatility signal",
            )
        )

        future_degradation = future_values(rows, index, "coulombic_efficiency_percent", future_window)
        sustained_degraded = (
            len(future_degradation) == future_window
            and all(value < ce_degradation_threshold for value in future_degradation)
        )
        scan_rows.append(
            scan_row(
                cell_group="Li||Cu",
                row=row,
                label_key="ce_sustained_degradation",
                audit_status="observed_candidate"
                if sustained_degraded
                else ("limited_window" if len(future_degradation) < future_window else "not_observed"),
                signal_value=min(future_degradation) if future_degradation else "",
                threshold=f"all future CE < {ce_degradation_threshold}",
                sustained_window=f"future_{future_window}_cycles",
                observed_candidate=sustained_degraded,
                censored_candidate=not sustained_degraded,
                limited_window_label=len(future_degradation) < future_window,
                leakage_risk="high_if_time_shift_not_enforced",
                readiness="audit_only",
                evidence="future sustained CE degradation scan",
            )
        )

    if last_row:
        scan_rows.append(
            scan_row(
                cell_group="Li||Cu",
                row=last_row,
                label_key="protocol_censored",
                audit_status="protocol_censored",
                protocol_censored=True,
                censored_candidate=True,
                limited_window_label=True,
                leakage_risk="low",
                readiness="required_censoring_metadata",
                evidence="final cycle reached; stop reason requires metadata review",
            )
        )
    return scan_rows


def scan_lili_rows(
    rows: list[dict[str, str]],
    *,
    hysteresis_multiplier: float,
    hysteresis_slope_threshold: float,
    voltage_std_threshold: float,
    rest_drop_threshold: float,
) -> list[dict[str, object]]:
    scan_rows: list[dict[str, object]] = []
    hysteresis_values = [
        parse_float(row.get("voltage_hysteresis_v"))
        for row in rows[: min(5, len(rows))]
    ]
    hysteresis_baseline = median([value for value in hysteresis_values if value is not None]) or 0.0
    hysteresis_threshold = abs(hysteresis_baseline) * hysteresis_multiplier
    last_row = rows[-1] if rows else {}
    for row in rows:
        rolling_hysteresis = parse_float(row.get("hysteresis_rolling_mean_past_5"))
        slope_value = parse_float(row.get("hysteresis_slope_past_10"))
        polarization = (
            rolling_hysteresis is not None
            and rolling_hysteresis > hysteresis_threshold
            and (slope_value is None or slope_value > hysteresis_slope_threshold)
        )
        scan_rows.append(
            scan_row(
                cell_group="Li||Li",
                row=row,
                label_key="polarization_growth",
                audit_status="observed_candidate" if polarization else "not_observed",
                signal_value=rolling_hysteresis,
                threshold=f"past rolling hysteresis > {format_value(hysteresis_threshold)} and slope > {hysteresis_slope_threshold}",
                sustained_window="past_5_to_10_cycles",
                observed_candidate=polarization,
                censored_candidate=not polarization,
                leakage_risk="low",
                readiness="audit_only_voltage_threshold_review_required",
                evidence="past-only hysteresis growth signal",
            )
        )

        hysteresis = parse_float(row.get("voltage_hysteresis_v"))
        end_gap = parse_float(row.get("end_voltage_gap_v"))
        hysteresis_failure = (
            (hysteresis is not None and abs(hysteresis) > hysteresis_threshold)
            or (end_gap is not None and abs(end_gap) > max(hysteresis_threshold, 0.5))
        )
        scan_rows.append(
            scan_row(
                cell_group="Li||Li",
                row=row,
                label_key="voltage_hysteresis_failure",
                audit_status="observed_candidate" if hysteresis_failure else "not_observed",
                signal_value=f"hysteresis={format_value(hysteresis)};end_gap={format_value(end_gap)}",
                threshold=f"|hysteresis| > {format_value(hysteresis_threshold)} or |end_gap| > {format_value(max(hysteresis_threshold, 0.5))}",
                sustained_window="single_cycle_audit",
                observed_candidate=hysteresis_failure,
                censored_candidate=not hysteresis_failure,
                leakage_risk="low",
                readiness="audit_only_threshold_review_required",
                evidence="voltage-domain hysteresis scan",
            )
        )

        voltage_std = parse_float(row.get("record_voltage_std_v"))
        instability = parse_bool(row.get("voltage_instability_warning")) or (
            voltage_std is not None and voltage_std > voltage_std_threshold
        )
        scan_rows.append(
            scan_row(
                cell_group="Li||Li",
                row=row,
                label_key="voltage_instability",
                audit_status="observed_candidate" if instability else "not_observed",
                signal_value=voltage_std,
                threshold=f"warning flag or record voltage std > {voltage_std_threshold}",
                sustained_window="sample_limited",
                observed_candidate=instability,
                censored_candidate=not instability,
                leakage_risk="low",
                readiness="audit_only_record_sample_limited",
                evidence="voltage warning or sampled record volatility",
            )
        )

        rest_drop = parse_float(row.get("rest_voltage_drop_mv_per_hour"))
        soft_short = rest_drop is not None and abs(rest_drop) > rest_drop_threshold
        scan_rows.append(
            scan_row(
                cell_group="Li||Li",
                row=row,
                label_key="soft_short_warning",
                audit_status="observed_candidate" if soft_short else "not_observed",
                signal_value=rest_drop,
                threshold=f"|rest voltage drop| > {rest_drop_threshold} mV/hour",
                sustained_window="sample_limited",
                observed_candidate=soft_short,
                censored_candidate=not soft_short,
                leakage_risk="low",
                readiness="audit_only_full_record_preferred",
                evidence="rest-voltage drop scan from available sampled records",
            )
        )

        incomplete = parse_bool(row.get("incomplete_cycle_warning"))
        scan_rows.append(
            scan_row(
                cell_group="Li||Li",
                row=row,
                label_key="incomplete_cycle_warning",
                audit_status="observed_candidate" if incomplete else "not_observed",
                observed_candidate=incomplete,
                censored_candidate=not incomplete,
                leakage_risk="low",
                readiness="secondary_audit_signal",
                evidence="Li||Li incomplete cycle warning is not a primary failure label",
            )
        )

    if last_row:
        scan_rows.append(
            scan_row(
                cell_group="Li||Li",
                row=last_row,
                label_key="protocol_censored",
                audit_status="protocol_censored",
                protocol_censored=True,
                censored_candidate=True,
                limited_window_label=True,
                leakage_risk="low",
                readiness="required_censoring_metadata",
                evidence="final cycle reached; stop reason requires metadata review",
            )
        )
    return scan_rows


def summarize_scan(scan_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in scan_rows:
        key = (
            str(row["cell_group"]),
            str(row["source_folder_name"]),
            str(row["selected_dataset_name"]),
            str(row["label_key"]),
        )
        grouped[key].append(row)
    summaries: list[dict[str, object]] = []
    for (cell_group, source, dataset, label_key), rows in sorted(grouped.items()):
        observed = [row for row in rows if parse_bool(row["observed_candidate"])]
        censored = [row for row in rows if parse_bool(row["censored_candidate"])]
        limited = [row for row in rows if parse_bool(row["limited_window_label"])]
        protocol = [row for row in rows if parse_bool(row["protocol_censored"])]
        cycle_indices = [parse_int(row["cycle_index"]) for row in rows]
        cycle_indices = [cycle for cycle in cycle_indices if cycle is not None]
        first_observed = ""
        if observed:
            observed_cycles = [parse_int(row["cycle_index"]) for row in observed]
            observed_cycles = [cycle for cycle in observed_cycles if cycle is not None]
            first_observed = min(observed_cycles) if observed_cycles else ""
        readiness_counts = Counter(str(row["readiness"]) for row in rows)
        readiness = readiness_counts.most_common(1)[0][0] if readiness_counts else "audit_only"
        summaries.append(
            {
                "cell_group": cell_group,
                "source_folder_name": source,
                "selected_dataset_name": dataset,
                "label_key": label_key,
                "rows_scanned": len(rows),
                "observed_candidate_count": len(observed),
                "censored_candidate_count": len(censored),
                "limited_window_count": len(limited),
                "protocol_censored_count": len(protocol),
                "first_observed_candidate_cycle": first_observed,
                "last_cycle_index": max(cycle_indices) if cycle_indices else "",
                "readiness": readiness,
            }
        )
    return summaries


def schema_checks(scan_rows: list[dict[str, object]], summary_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    trainable_values = {str(row.get("trainable_label")) for row in scan_rows}
    forbidden_tokens = ["eol", "rul", "target"]
    columns = set(scan_rows[0].keys()) if scan_rows else set()
    forbidden_present = sorted(
        column for column in columns for token in forbidden_tokens if token in column.lower()
    )
    return [
        {
            "check": "audit_scan_rows_exist",
            "status": "pass" if scan_rows else "fail",
            "details": len(scan_rows),
        },
        {
            "check": "summary_rows_exist",
            "status": "pass" if summary_rows else "fail",
            "details": len(summary_rows),
        },
        {
            "check": "trainable_label_always_false",
            "status": "pass" if trainable_values <= {"False", "false"} else "fail",
            "details": ";".join(sorted(trainable_values)),
        },
        {
            "check": "no_forbidden_training_columns",
            "status": "pass" if not forbidden_present else "fail",
            "details": ";".join(forbidden_present),
        },
    ]


def write_report(
    output_root: Path,
    scan_rows: list[dict[str, object]],
    summary_rows: list[dict[str, object]],
    checks: list[dict[str, object]],
) -> dict[str, object]:
    by_group = Counter(str(row["cell_group"]) for row in scan_rows)
    observed_by_label = Counter(
        str(row["label_key"]) for row in scan_rows if parse_bool(row["observed_candidate"])
    )
    protocol_censored = sum(1 for row in scan_rows if parse_bool(row["protocol_censored"]))
    report = {
        "training_allowed_now": False,
        "label_builder_allowed": True,
        "baseline_ready_labels_exported": False,
        "model_training_allowed": False,
        "audit_scan_rows": len(scan_rows),
        "summary_rows": len(summary_rows),
        "rows_by_cell_group": dict(by_group),
        "observed_candidates_by_label_key": dict(observed_by_label),
        "protocol_censored_rows": protocol_censored,
        "schema_checks": checks,
        "notes": [
            "This output is an audit-only event scan, not trainable labels.",
            "Li||Li and Li||Cu are scanned separately.",
            "CE collapse uses future-window evidence and remains high leakage risk until trainability audit.",
        ],
    }
    with (output_root / "lmb_audit_label_scan_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    markdown = [
        "# LMB Audit-Only Label Scan Report",
        "",
        "This report summarizes candidate LMB label signals. It is not a model result and does not export trainable labels.",
        "",
        f"- Audit scan rows: {len(scan_rows)}",
        f"- Summary rows: {len(summary_rows)}",
        f"- Training allowed now: {report['training_allowed_now']}",
        f"- Baseline-ready labels exported: {report['baseline_ready_labels_exported']}",
        "",
        "## Observed Candidate Counts",
        "",
        "| label_key | observed_candidate_count |",
        "| --- | ---: |",
    ]
    for label_key, count in sorted(observed_by_label.items()):
        markdown.append(f"| `{label_key}` | {count} |")
    markdown.extend(
        [
            "",
            "## Gate Decision",
            "",
            "- `label_builder_allowed = True`",
            "- `model_training_allowed = False`",
            "- Next step: review event thresholds, then build a trainability audit.",
        ]
    )
    (output_root / "lmb_audit_label_scan_report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return report


def scan_lmb_audit_only_labels(
    feature_root: Path,
    output_root: Path,
    *,
    overwrite: bool = False,
    future_window: int = 5,
    ce_collapse_threshold: float = 50.0,
    ce_instability_std_threshold: float = 20.0,
    ce_degradation_threshold: float = 80.0,
    hysteresis_multiplier: float = 2.0,
    hysteresis_slope_threshold: float = 0.0,
    voltage_std_threshold: float = 0.2,
    rest_drop_threshold: float = 50.0,
) -> dict[str, object]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root already exists and is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    lili_rows = read_csv(feature_root / "lili_cycle_features.csv")
    licu_rows = read_csv(feature_root / "licu_cycle_features.csv")

    scan_rows: list[dict[str, object]] = []
    for rows in group_feature_rows(licu_rows).values():
        scan_rows.extend(
            scan_licu_rows(
                rows,
                future_window=future_window,
                ce_collapse_threshold=ce_collapse_threshold,
                ce_instability_std_threshold=ce_instability_std_threshold,
                ce_degradation_threshold=ce_degradation_threshold,
            )
        )
    for rows in group_feature_rows(lili_rows).values():
        scan_rows.extend(
            scan_lili_rows(
                rows,
                hysteresis_multiplier=hysteresis_multiplier,
                hysteresis_slope_threshold=hysteresis_slope_threshold,
                voltage_std_threshold=voltage_std_threshold,
                rest_drop_threshold=rest_drop_threshold,
            )
        )

    summary_rows = summarize_scan(scan_rows)
    checks = schema_checks(scan_rows, summary_rows)
    write_csv(output_root / "lmb_audit_event_scan.csv", scan_rows, SCAN_COLUMNS)
    write_csv(output_root / "per_cell_audit_label_summary.csv", summary_rows, SUMMARY_COLUMNS)
    write_csv(output_root / "audit_label_schema_check.csv", checks, ["check", "status", "details"])
    return write_report(output_root, scan_rows, summary_rows, checks)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--future-window", type=int, default=5)
    parser.add_argument("--ce-collapse-threshold", type=float, default=50.0)
    parser.add_argument("--ce-instability-std-threshold", type=float, default=20.0)
    parser.add_argument("--ce-degradation-threshold", type=float, default=80.0)
    parser.add_argument("--hysteresis-multiplier", type=float, default=2.0)
    parser.add_argument("--hysteresis-slope-threshold", type=float, default=0.0)
    parser.add_argument("--voltage-std-threshold", type=float, default=0.2)
    parser.add_argument("--rest-drop-threshold", type=float, default=50.0)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    report = scan_lmb_audit_only_labels(
        feature_root=Path(args.feature_root),
        output_root=Path(args.output_root),
        overwrite=args.overwrite,
        future_window=args.future_window,
        ce_collapse_threshold=args.ce_collapse_threshold,
        ce_instability_std_threshold=args.ce_instability_std_threshold,
        ce_degradation_threshold=args.ce_degradation_threshold,
        hysteresis_multiplier=args.hysteresis_multiplier,
        hysteresis_slope_threshold=args.hysteresis_slope_threshold,
        voltage_std_threshold=args.voltage_std_threshold,
        rest_drop_threshold=args.rest_drop_threshold,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
