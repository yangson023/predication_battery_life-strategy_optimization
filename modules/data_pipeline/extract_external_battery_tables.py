"""Extract normalized sample tables from inventoried external battery archives.

This module reads archive members directly from ZIP files and writes compact
CSV samples. It is intentionally chunk-oriented: use small limits while
developing schema logic, then increase limits when ready for larger feature
extraction jobs.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


DEFAULT_MEASUREMENT_TYPES = [
    "cycle_timeseries",
    "rpt_diagnostic",
    "abuse_test_timeseries",
]

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
    "archive_member_path",
    "cycle_index",
    "diagnostic_part",
    "nominal_capacity_mah",
    "replicate_id",
    "soc_percent",
]


@dataclass
class ExtractionSummaryRecord:
    measurement_type: str
    source_archive_name: str
    archive_member_path: str
    status: str
    rows_read: int
    columns_read: int
    output_file: str
    notes: str


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return slug or "unknown"


def parquet_engine_available() -> bool:
    return (
        importlib.util.find_spec("pyarrow") is not None
        or importlib.util.find_spec("fastparquet") is not None
    )


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_archive_paths(archive_manifest_path: Path) -> dict[str, Path]:
    rows = read_csv_rows(archive_manifest_path)
    return {row["source_archive_name"]: Path(row["source_archive_path"]) for row in rows}


def numeric_sort_key(value: str | None) -> tuple[int, str]:
    if value is None or value == "":
        return (10**9, "")
    try:
        return (int(float(value)), "")
    except ValueError:
        return (10**9, value)


def select_inventory_rows(
    inventory_rows: list[dict[str, str]],
    measurement_types: list[str],
    max_members_per_type: int,
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for measurement_type in measurement_types:
        rows = [
            row
            for row in inventory_rows
            if row.get("measurement_type") == measurement_type
        ]
        rows.sort(
            key=lambda row: (
                row.get("source_archive_name", ""),
                row.get("cell_id", ""),
                numeric_sort_key(row.get("cycle_index") or row.get("diagnostic_part")),
                row.get("archive_member_path", ""),
            )
        )
        if max_members_per_type > 0:
            rows = rows[:max_members_per_type]
        selected.extend(rows)
    return selected


def normalize_column_name(column: object, aliases: dict[str, str]) -> str:
    raw = str(column).replace("\ufeff", "").strip()
    if raw in aliases:
        return aliases[raw]
    if raw.lower().startswith("unnamed:"):
        return slugify(raw)
    return slugify(raw)


def make_unique_columns(columns: list[str]) -> list[str]:
    counts: Counter[str] = Counter()
    unique = []
    for column in columns:
        counts[column] += 1
        unique.append(column if counts[column] == 1 else f"{column}_{counts[column]}")
    return unique


def normalize_frame(frame: pd.DataFrame, row: dict[str, str], aliases: dict[str, str]) -> pd.DataFrame:
    normalized = frame.copy()
    normalized.columns = make_unique_columns(
        [normalize_column_name(column, aliases) for column in normalized.columns]
    )

    for key in IDENTITY_COLUMNS:
        normalized[key] = row.get(key, "")

    ordered = [column for column in IDENTITY_COLUMNS if column in normalized.columns]
    rest = [column for column in normalized.columns if column not in ordered]
    return normalized[ordered + rest]


def read_member_frame(
    archive_path: Path,
    member_path: str,
    file_extension: str,
    rows_per_member: int,
) -> pd.DataFrame:
    with ZipFile(archive_path) as zf:
        with zf.open(member_path) as handle:
            if file_extension.lower() == ".csv":
                return pd.read_csv(handle, nrows=rows_per_member)
            if file_extension.lower() in {".xlsx", ".xls"}:
                data = handle.read()
                return pd.read_excel(BytesIO(data), nrows=rows_per_member)
    raise ValueError(f"Unsupported file extension: {file_extension}")


def append_frame(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, mode="a", header=not path.exists(), index=False)


def write_json(path: Path, rows: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_summary_csv(path: Path, rows: list[ExtractionSummaryRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(ExtractionSummaryRecord.__dataclass_fields__.keys()),
        )
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def maybe_write_parquet(csv_path: Path, parquet_path: Path) -> str:
    if not parquet_engine_available():
        return "skipped_no_engine"
    try:
        frame = pd.read_csv(csv_path)
        frame.to_parquet(parquet_path, index=False)
    except Exception as exc:  # pragma: no cover - optional engine/runtime dependent
        return f"write_failed: {exc}"
    return "written"


def extract_tables(
    inventory_path: Path,
    archive_manifest_path: Path,
    schema_map_path: Path,
    output_dir: Path,
    measurement_types: list[str],
    max_members_per_type: int,
    rows_per_member: int,
    write_parquet: bool,
) -> list[ExtractionSummaryRecord]:
    inventory_rows = read_csv_rows(inventory_path)
    archive_paths = load_archive_paths(archive_manifest_path)
    aliases = read_json(schema_map_path).get("column_aliases", {})
    if not isinstance(aliases, dict):
        raise ValueError("schema map must contain a column_aliases object")

    output_dir.mkdir(parents=True, exist_ok=True)
    for measurement_type in measurement_types:
        csv_path = output_dir / f"{measurement_type}_sample.csv"
        parquet_path = output_dir / f"{measurement_type}_sample.parquet"
        if csv_path.exists():
            csv_path.unlink()
        if parquet_path.exists():
            parquet_path.unlink()

    summary: list[ExtractionSummaryRecord] = []
    for row in select_inventory_rows(inventory_rows, measurement_types, max_members_per_type):
        measurement_type = row.get("measurement_type", "unknown")
        output_file = output_dir / f"{measurement_type}_sample.csv"
        archive_name = row.get("source_archive_name", "")
        archive_path = archive_paths.get(archive_name)
        if archive_path is None:
            summary.append(
                ExtractionSummaryRecord(
                    measurement_type=measurement_type,
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
                ExtractionSummaryRecord(
                    measurement_type=measurement_type,
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
                ExtractionSummaryRecord(
                    measurement_type=measurement_type,
                    source_archive_name=archive_name,
                    archive_member_path=row.get("archive_member_path", ""),
                    status="failed",
                    rows_read=0,
                    columns_read=0,
                    output_file=str(output_file),
                    notes=str(exc),
                )
            )

    if write_parquet:
        for measurement_type in measurement_types:
            csv_path = output_dir / f"{measurement_type}_sample.csv"
            if not csv_path.exists():
                continue
            status = maybe_write_parquet(csv_path, output_dir / f"{measurement_type}_sample.parquet")
            summary.append(
                ExtractionSummaryRecord(
                    measurement_type=measurement_type,
                    source_archive_name="",
                    archive_member_path="",
                    status="parquet",
                    rows_read=0,
                    columns_read=0,
                    output_file=str(output_dir / f"{measurement_type}_sample.parquet"),
                    notes=status,
                )
            )

    write_summary_csv(output_dir / "extraction_summary.csv", summary)
    write_json(output_dir / "extraction_summary.json", [asdict(row) for row in summary])
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract normalized sample tables from external battery archives.",
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=Path("data/processed/external_battery_datasets/file_inventory.csv"),
        help="Inventory generated by organize_external_battery_archives.py.",
    )
    parser.add_argument(
        "--archive-manifest",
        type=Path,
        default=Path("configs/datasets/external_battery_archives.csv"),
        help="Archive manifest with source paths.",
    )
    parser.add_argument(
        "--schema-map",
        type=Path,
        default=Path("configs/datasets/external_battery_schema_map.json"),
        help="Column alias map for normalized output.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/external_battery_datasets/extracted"),
        help="Directory for normalized sample CSV files.",
    )
    parser.add_argument(
        "--measurement-types",
        nargs="*",
        default=DEFAULT_MEASUREMENT_TYPES,
        help="Measurement types to extract.",
    )
    parser.add_argument(
        "--max-members-per-type",
        type=int,
        default=2,
        help="Maximum archive members per measurement type. Use 0 for all members.",
    )
    parser.add_argument(
        "--rows-per-member",
        type=int,
        default=500,
        help="Rows to read from each archive member.",
    )
    parser.add_argument(
        "--write-parquet",
        action="store_true",
        help="Also write Parquet files when pyarrow or fastparquet is installed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = extract_tables(
        inventory_path=args.inventory,
        archive_manifest_path=args.archive_manifest,
        schema_map_path=args.schema_map,
        output_dir=args.output_dir,
        measurement_types=args.measurement_types,
        max_members_per_type=args.max_members_per_type,
        rows_per_member=args.rows_per_member,
        write_parquet=args.write_parquet,
    )
    written = sum(1 for row in summary if row.status == "written")
    failed = sum(1 for row in summary if row.status == "failed")
    print(f"Extraction complete: written={written}, failed={failed}")
    print(f"Output directory: {args.output_dir}")


if __name__ == "__main__":
    main()
