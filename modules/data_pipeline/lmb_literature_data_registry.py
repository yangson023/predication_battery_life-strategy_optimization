"""Audit LMB literature and public-data candidates before downloading data.

This tool is intentionally lightweight. It does not crawl websites, download
files, process raw data, or train models. It turns a manually curated source
registry into a repeatable readiness audit.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TEMPLATE_COLUMNS = [
    "source_name",
    "url_or_doi",
    "current_role",
    "is_lmb",
    "cell_type",
    "is_direct_download_available",
    "has_raw_cycling_table",
    "has_charge_capacity",
    "has_discharge_capacity",
    "has_ce",
    "has_voltage_current_curve",
    "has_lmb_metadata",
    "has_protocol_or_conditions",
    "has_failure_or_stopping_reason",
    "license_or_terms_clear",
    "recommended_storage",
    "notes",
]

YES_VALUES = {"yes", "y", "true", "1", "available", "direct", "calculated"}
NO_VALUES = {"no", "n", "false", "0", "unavailable", "none"}

VALID_ROLES = {
    "true_lmb_candidate",
    "transfer_auxiliary_data",
    "diagnostic_only",
    "li_ion_method_data",
    "unknown",
}

TRUE_LMB_STORAGE = r"E:\battery_research_storage\true_lmb"
TRANSFER_STORAGE = r"E:\battery_research_storage\transfer_auxiliary_data"
DIAGNOSTIC_STORAGE = r"E:\battery_research_storage\diagnostic_only"
UNKNOWN_STORAGE = r"E:\battery_research_storage\unknown"


@dataclass(frozen=True)
class SourceAudit:
    source_name: str
    url_or_doi: str
    current_role: str
    recommended_role: str
    data_readiness_score: int
    evidence_fields_present: int
    missing_critical_fields: str
    intake_decision: str
    recommended_storage: str
    needs_author_contact: bool
    caution: str


def normalize_value(value: object) -> str:
    return str(value or "").strip().lower()


def is_yes(value: object) -> bool:
    return normalize_value(value) in YES_VALUES


def is_no(value: object) -> bool:
    return normalize_value(value) in NO_VALUES


def load_registry(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [col for col in TEMPLATE_COLUMNS if col not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Registry is missing required columns: {', '.join(missing)}")
        return [{col: row.get(col, "") for col in TEMPLATE_COLUMNS} for row in reader]


def write_csv(path: Path, rows: Iterable[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def write_template(path: Path) -> None:
    example = {
        "source_name": "example_lmb_paper",
        "url_or_doi": "https://doi.org/example",
        "current_role": "unknown",
        "is_lmb": "unknown",
        "cell_type": "Li||NMC / Li||Cu / anode-free / unclear",
        "is_direct_download_available": "unknown",
        "has_raw_cycling_table": "unknown",
        "has_charge_capacity": "unknown",
        "has_discharge_capacity": "unknown",
        "has_ce": "unknown",
        "has_voltage_current_curve": "unknown",
        "has_lmb_metadata": "unknown",
        "has_protocol_or_conditions": "unknown",
        "has_failure_or_stopping_reason": "unknown",
        "license_or_terms_clear": "unknown",
        "recommended_storage": "",
        "notes": "Replace this example row before using the audit.",
    }
    write_csv(path, [example], TEMPLATE_COLUMNS)


def audit_source(row: dict[str, str]) -> SourceAudit:
    role = normalize_value(row.get("current_role")) or "unknown"
    if role not in VALID_ROLES:
        role = "unknown"

    critical = [
        "is_lmb",
        "has_raw_cycling_table",
        "has_charge_capacity",
        "has_discharge_capacity",
        "has_lmb_metadata",
    ]
    useful = [
        "has_ce",
        "has_voltage_current_curve",
        "has_protocol_or_conditions",
        "has_failure_or_stopping_reason",
        "license_or_terms_clear",
        "is_direct_download_available",
    ]
    present = [field for field in critical + useful if is_yes(row.get(field))]
    missing_critical = [field for field in critical if not is_yes(row.get(field))]
    score = len(present)

    lmb_confirmed = is_yes(row.get("is_lmb"))
    raw_cycle = is_yes(row.get("has_raw_cycling_table"))
    metadata = is_yes(row.get("has_lmb_metadata"))
    direct_download = is_yes(row.get("is_direct_download_available"))
    voltage_curve = is_yes(row.get("has_voltage_current_curve"))
    protocol = is_yes(row.get("has_protocol_or_conditions"))

    if lmb_confirmed and raw_cycle and metadata:
        recommended_role = "true_lmb_candidate"
        storage = row.get("recommended_storage") or TRUE_LMB_STORAGE
        if direct_download:
            decision = "download_then_tiny_validation"
            needs_contact = False
        else:
            decision = "contact_author_or_lab_before_download"
            needs_contact = True
        caution = "Candidate only until raw schema, protocol, and label quality are audited."
    elif lmb_confirmed and (voltage_curve or protocol or role == "diagnostic_only"):
        recommended_role = "diagnostic_only"
        storage = row.get("recommended_storage") or DIAGNOSTIC_STORAGE
        decision = "record_for_mechanism_or_label_design"
        needs_contact = not direct_download
        caution = "Do not use as trainable lifetime data without cycle-level alignment."
    elif role in {"transfer_auxiliary_data", "li_ion_method_data"}:
        recommended_role = role
        storage = row.get("recommended_storage") or TRANSFER_STORAGE
        decision = "method_or_transfer_reference_only"
        needs_contact = False
        caution = "Do not present as direct LMB evidence."
    else:
        recommended_role = "unknown"
        storage = row.get("recommended_storage") or UNKNOWN_STORAGE
        decision = "metadata_recovery_before_use"
        needs_contact = not direct_download
        caution = "Cannot train or claim LMB conclusions until role is resolved."

    return SourceAudit(
        source_name=row.get("source_name", ""),
        url_or_doi=row.get("url_or_doi", ""),
        current_role=row.get("current_role", ""),
        recommended_role=recommended_role,
        data_readiness_score=score,
        evidence_fields_present=len(present),
        missing_critical_fields=";".join(missing_critical),
        intake_decision=decision,
        recommended_storage=storage,
        needs_author_contact=needs_contact,
        caution=caution,
    )


def audit_registry(input_path: Path, output_root: Path) -> dict[str, object]:
    rows = load_registry(input_path)
    audits = [audit_source(row) for row in rows]
    audit_rows = [audit.__dict__ for audit in audits]

    output_root.mkdir(parents=True, exist_ok=True)
    audit_csv = output_root / "lmb_literature_source_audit.csv"
    columns = list(SourceAudit.__dataclass_fields__.keys())
    write_csv(audit_csv, audit_rows, columns)

    role_counts = Counter(a.recommended_role for a in audits)
    decision_counts = Counter(a.intake_decision for a in audits)
    ready_for_tiny = [
        a.source_name
        for a in audits
        if a.intake_decision == "download_then_tiny_validation"
    ]
    report = {
        "input_path": str(input_path),
        "output_root": str(output_root),
        "source_count": len(audits),
        "recommended_role_counts": dict(sorted(role_counts.items())),
        "intake_decision_counts": dict(sorted(decision_counts.items())),
        "ready_for_tiny_validation_count": len(ready_for_tiny),
        "ready_for_tiny_validation_sources": ready_for_tiny,
        "training_allowed": False,
        "training_gate_note": "This registry is only an intake audit. Training requires true LMB raw data, tiny validation, processed features, labels, and label audit.",
    }

    with (output_root / "lmb_literature_source_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    write_markdown_report(output_root / "lmb_literature_source_report.md", report, audits)
    return report


def write_markdown_report(path: Path, report: dict[str, object], audits: list[SourceAudit]) -> None:
    lines = [
        "# LMB Literature Source Audit Report",
        "",
        "This report classifies literature and public-data candidates. It does not download data, process files, or report model performance.",
        "",
        "## Summary",
        "",
        f"- Source count: {report['source_count']}",
        f"- Ready for tiny validation: {report['ready_for_tiny_validation_count']}",
        f"- Training allowed: {report['training_allowed']}",
        f"- Gate note: {report['training_gate_note']}",
        "",
        "## Recommended Role Counts",
        "",
    ]
    for role, count in report["recommended_role_counts"].items():
        lines.append(f"- `{role}`: {count}")

    lines.extend(["", "## Intake Decision Counts", ""])
    for decision, count in report["intake_decision_counts"].items():
        lines.append(f"- `{decision}`: {count}")

    lines.extend(
        [
            "",
            "## Source Decisions",
            "",
            "| Source | Recommended role | Score | Decision | Missing critical fields |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for audit in audits:
        lines.append(
            "| "
            + " | ".join(
                [
                    audit.source_name or "(unnamed)",
                    f"`{audit.recommended_role}`",
                    str(audit.data_readiness_score),
                    f"`{audit.intake_decision}`",
                    audit.missing_critical_fields or "none",
                ]
            )
            + " |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Input LMB source registry CSV.")
    parser.add_argument("--output-root", type=Path, default=Path("outputs/lmb_literature_registry"))
    parser.add_argument("--init-template", type=Path, help="Write an empty registry template CSV and exit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.init_template:
        write_template(args.init_template)
        return
    if not args.input:
        raise SystemExit("--input is required unless --init-template is used")
    audit_registry(args.input, args.output_root)


if __name__ == "__main__":
    main()
