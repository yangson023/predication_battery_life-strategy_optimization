"""Extract normalized external battery data into per-cell chunk files."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.data_pipeline.extract_external_battery_tables import (
    append_frame,
    load_archive_paths,
    normalize_frame,
    numeric_sort_key,
    read_csv_rows,
    read_json,
    read_member_frame,
)


DEFAULT_MEASUREMENT_TYPES = ["cycle_timeseries", "rpt_diagnostic"]


@dataclass
class CellExtractionSummaryRecord:
    cell_id: str
    measurement_type: str
    source_archive_name: str
    archive_member_path: str
    status: str
    rows_read: int
    columns_read: int
    output_file: str
    notes: str


def slugify_cell_id(cell_id: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in cell_id).strip("_")


def natural_cell_sort_key(cell_id: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", cell_id)
    return tuple(int(part) if part.isdigit() else part.lower() for part in parts)


def unique_sorted_cell_ids(rows: list[dict[str, str]]) -> list[str]:
    return sorted(
        {row.get("cell_id", "") for row in rows if row.get("cell_id", "")},
        key=natural_cell_sort_key,
    )


def select_cells(
    rows: list[dict[str, str]],
    requested_cells: list[str],
    max_cells: int,
    anchor_measurement_type: str,
) -> list[str]:
    if requested_cells:
        available = set(unique_sorted_cell_ids(rows))
        return [cell_id for cell_id in requested_cells if cell_id in available]
    candidate_rows = (
        rows
        if anchor_measurement_type in {"", "any"}
        else [row for row in rows if row.get("measurement_type", "") == anchor_measurement_type]
    )
    cells = unique_sorted_cell_ids(candidate_rows)
    return cells if max_cells == 0 else cells[:max_cells]


def selected_rows_by_cell(
    inventory_rows: list[dict[str, str]],
    measurement_types: list[str],
    requested_cells: list[str],
    max_cells: int,
    max_members_per_cell_type: int,
    anchor_measurement_type: str = "cycle_timeseries",
) -> list[dict[str, str]]:
    filtered = [
        row
        for row in inventory_rows
        if row.get("cell_id", "")
        and row.get("measurement_type", "") in measurement_types
        and row.get("file_extension", "").lower() == ".csv"
    ]
    cells = set(select_cells(filtered, requested_cells, max_cells, anchor_measurement_type))
    rows = [row for row in filtered if row.get("cell_id", "") in cells]
    rows.sort(
        key=lambda row: (
            row.get("cell_id", ""),
            row.get("measurement_type", ""),
            row.get("source_archive_name", ""),
            numeric_sort_key(row.get("cycle_index") or row.get("diagnostic_part")),
            row.get("archive_member_path", ""),
        )
    )

    selected: list[dict[str, str]] = []
    counts: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row.get("cell_id", ""), row.get("measurement_type", ""))
        counts[key] = counts.get(key, 0) + 1
        if max_members_per_cell_type and counts[key] > max_members_per_cell_type:
            continue
        selected.append(row)
    return selected


def output_path_for_row(output_root: Path, row: dict[str, str]) -> Path:
    cell_id = slugify_cell_id(row.get("cell_id", "") or "unknown_cell")
    measurement_type = row.get("measurement_type", "unknown_measurement")
    return output_root / cell_id / f"{measurement_type}.csv"


def write_summary_csv(path: Path, rows: list[CellExtractionSummaryRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(CellExtractionSummaryRecord.__dataclass_fields__.keys()),
        )
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def write_json(path: Path, content: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_selected_outputs(output_root: Path, rows: list[dict[str, str]]) -> None:
    for row in rows:
        path = output_path_for_row(output_root, row)
        if path.exists():
            path.unlink()


def clear_output_root(output_root: Path) -> None:
    if output_root.exists():
        shutil.rmtree(output_root)


def extract_by_cell(
    inventory_path: Path,
    archive_manifest_path: Path,
    schema_map_path: Path,
    output_root: Path,
    measurement_types: list[str],
    cell_ids: list[str],
    max_cells: int,
    max_members_per_cell_type: int,
    rows_per_member: int,
    anchor_measurement_type: str = "cycle_timeseries",
    clear_output: bool = True,
) -> list[CellExtractionSummaryRecord]:
    inventory_rows = read_csv_rows(inventory_path)
    archive_paths = load_archive_paths(archive_manifest_path)
    aliases = read_json(schema_map_path).get("column_aliases", {})
    if not isinstance(aliases, dict):
        raise ValueError("schema map must contain a column_aliases object")

    selected_rows = selected_rows_by_cell(
        inventory_rows=inventory_rows,
        measurement_types=measurement_types,
        requested_cells=cell_ids,
        max_cells=max_cells,
        max_members_per_cell_type=max_members_per_cell_type,
        anchor_measurement_type=anchor_measurement_type,
    )
    if clear_output:
        clear_output_root(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    if not clear_output:
        clear_selected_outputs(output_root, selected_rows)

    summary: list[CellExtractionSummaryRecord] = []
    for row in selected_rows:
        output_file = output_path_for_row(output_root, row)
        archive_name = row.get("source_archive_name", "")
        archive_path = archive_paths.get(archive_name)
        if archive_path is None:
            summary.append(
                CellExtractionSummaryRecord(
                    cell_id=row.get("cell_id", ""),
                    measurement_type=row.get("measurement_type", ""),
                    source_archive_name=archive_name,
                    archive_member_path=row.get("archive_member_path", ""),
                    status="skipped",
                    rows_read=0,
                    columns_read=0,
                    output_file=str(output_file),
                    notes="archive path not found in manifest",
                )
            )
            continue
        try:
            frame = read_member_frame(
                archive_path=archive_path,
                member_path=row["archive_member_path"],
                file_extension=row.get("file_extension", ""),
                rows_per_member=rows_per_member,
            )
            normalized = normalize_frame(frame, row, aliases)
            append_frame(output_file, normalized)
            summary.append(
                CellExtractionSummaryRecord(
                    cell_id=row.get("cell_id", ""),
                    measurement_type=row.get("measurement_type", ""),
                    source_archive_name=archive_name,
                    archive_member_path=row.get("archive_member_path", ""),
                    status="written",
                    rows_read=int(normalized.shape[0]),
                    columns_read=int(normalized.shape[1]),
                    output_file=str(output_file),
                    notes="",
                )
            )
        except Exception as exc:
            summary.append(
                CellExtractionSummaryRecord(
                    cell_id=row.get("cell_id", ""),
                    measurement_type=row.get("measurement_type", ""),
                    source_archive_name=archive_name,
                    archive_member_path=row.get("archive_member_path", ""),
                    status="failed",
                    rows_read=0,
                    columns_read=0,
                    output_file=str(output_file),
                    notes=str(exc),
                )
            )

    write_summary_csv(output_root / "cell_extraction_summary.csv", summary)
    write_json(output_root / "cell_extraction_summary.json", [asdict(row) for row in summary])
    write_json(
        output_root / "cell_extraction_manifest.json",
        {
            "measurement_types": measurement_types,
            "cell_ids": sorted({row.cell_id for row in summary if row.cell_id}),
            "max_cells": max_cells,
            "max_members_per_cell_type": max_members_per_cell_type,
            "rows_per_member": rows_per_member,
            "anchor_measurement_type": anchor_measurement_type,
            "selected_members": len(selected_rows),
            "written_members": sum(1 for row in summary if row.status == "written"),
            "failed_members": sum(1 for row in summary if row.status == "failed"),
        },
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract normalized external battery data into per-cell chunk files.",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("data/processed/external_battery_datasets/file_inventory.csv"),
    )
    parser.add_argument(
        "--archive-manifest",
        type=Path,
        default=Path("configs/datasets/external_battery_archives.csv"),
    )
    parser.add_argument(
        "--schema-map",
        type=Path,
        default=Path("configs/datasets/external_battery_schema_map.json"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/processed/external_battery_datasets/by_cell"),
    )
    parser.add_argument(
        "--measurement-types",
        nargs="*",
        default=DEFAULT_MEASUREMENT_TYPES,
    )
    parser.add_argument(
        "--cell-ids",
        nargs="*",
        default=[],
        help="Optional explicit cell IDs such as G3C1 G3C2. Overrides --max-cells.",
    )
    parser.add_argument(
        "--max-cells",
        type=int,
        default=2,
        help="Number of cells to extract when --cell-ids is omitted. Use 0 for all cells.",
    )
    parser.add_argument(
        "--max-members-per-cell-type",
        type=int,
        default=2,
        help="Maximum files per cell and measurement type. Use 0 for all files.",
    )
    parser.add_argument(
        "--anchor-measurement-type",
        default="cycle_timeseries",
        help="Measurement type used to choose default cells. Use 'any' to choose from all selected types.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing per-cell files instead of clearing the output root first.",
    )
    parser.add_argument(
        "--rows-per-member",
        type=int,
        default=1000,
        help="Rows per ZIP member. Use 0 for all rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = extract_by_cell(
        inventory_path=args.inventory,
        archive_manifest_path=args.archive_manifest,
        schema_map_path=args.schema_map,
        output_root=args.output_root,
        measurement_types=args.measurement_types,
        cell_ids=args.cell_ids,
        max_cells=args.max_cells,
        max_members_per_cell_type=args.max_members_per_cell_type,
        rows_per_member=args.rows_per_member,
        anchor_measurement_type=args.anchor_measurement_type,
        clear_output=not args.append,
    )
    written = sum(1 for row in summary if row.status == "written")
    failed = sum(1 for row in summary if row.status == "failed")
    cells = sorted({row.cell_id for row in summary if row.cell_id})
    print(f"Cell extraction complete: cells={len(cells)}, written={written}, failed={failed}")
    print(f"Output directory: {args.output_root}")


if __name__ == "__main__":
    main()
