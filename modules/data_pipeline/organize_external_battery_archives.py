"""Organize large external battery data archives without full extraction.

The script builds a common manifest and file inventory for heterogeneous
battery datasets. It deliberately avoids full ZIP extraction because the
listed archives expand to well over 100 GB.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile


DEFAULT_ARCHIVE_PATHS = [
    r"C:\Users\Lenovo\Desktop\battery_dataset_collection\Batch 1 Part 1.zip",
    r"C:\Users\Lenovo\Desktop\battery_dataset_collection\Batch 1 Part 2.zip",
    r"C:\Users\Lenovo\Desktop\battery_dataset_collection\Batch 1 Part 3.zip",
    r"C:\Users\Lenovo\Desktop\battery_dataset_collection\Batch 2 Part 1.zip",
    r"C:\Users\Lenovo\Desktop\battery_dataset_collection\Batch 2 Part 2.zip",
    r"C:\Users\Lenovo\Desktop\battery_dataset_collection\Batch 2 Part 3.zip",
    r"C:\Users\Lenovo\Desktop\battery_dataset_collection\rpt_data.zip",
    r"C:\Users\Lenovo\Desktop\battery_dataset_collection\Mechanically Induced Thermal Runaway for Li-ion Batteries.zip",
]


@dataclass
class ArchiveManifestRecord:
    dataset_id: str
    dataset_family: str
    data_category: str
    chemistry: str
    source_archive_name: str
    source_archive_path: str
    organized_raw_dir: str
    archive_copied: bool
    copied_archive_path: str
    size_bytes: int
    entry_count: int
    file_count: int
    uncompressed_bytes: int
    dominant_extensions: str
    cell_count_estimate: int
    generated_at_utc: str
    notes: str


@dataclass
class FileInventoryRecord:
    dataset_id: str
    dataset_family: str
    data_category: str
    chemistry: str
    source_archive_name: str
    archive_member_path: str
    normalized_member_path: str
    file_extension: str
    compressed_size_bytes: int
    uncompressed_size_bytes: int
    cell_id: str
    batch_id: str
    part_id: str
    measurement_type: str
    cycle_index: str
    diagnostic_part: str
    nominal_capacity_mah: str
    replicate_id: str
    soc_percent: str
    header_preview: str
    notes: str


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return slug or "unknown"


def safe_member_path(path: str) -> str:
    return "/".join(part for part in path.replace("\\", "/").split("/") if part and part != "__MACOSX")


def is_data_member(member_path: str) -> bool:
    parts = [part for part in member_path.replace("\\", "/").split("/") if part]
    if not parts:
        return False
    if "__MACOSX" in parts:
        return False
    return not any(part.startswith("._") for part in parts)


def classify_archive(path: Path, member_names: list[str]) -> tuple[str, str, str, str]:
    lowered_name = path.name.lower()
    lowered_members = " ".join(name.lower() for name in member_names[:200])

    if "thermal runaway" in lowered_name or "thermal runaway" in lowered_members:
        return (
            "mechanical_thermal_runaway",
            "safety_abuse",
            "thermal_runaway",
            "li_ion",
        )
    if lowered_name == "rpt_data.zip" or "rpt_cell_" in lowered_members:
        return ("rpt_diagnostics", "diagnostics", "rpt", "li_ion")
    if re.search(r"batch\s+\d+\s+part\s+\d+", lowered_name) or "cycling " in lowered_members:
        return ("multi_cell_cycle_life", "cycle_life", "cycling", "li_ion")
    return ("external_battery_data", "unknown", "unknown", "unknown")


def parse_batch_part(source_archive_name: str) -> tuple[str, str]:
    match = re.search(r"Batch\s+(\d+)\s+Part\s+(\d+)", source_archive_name, re.IGNORECASE)
    if not match:
        return "", ""
    return f"batch_{match.group(1)}", f"part_{match.group(2)}"


def parse_member_metadata(
    source_archive_name: str,
    member_path: str,
    data_category: str,
) -> dict[str, str]:
    batch_id, part_id = parse_batch_part(source_archive_name)
    metadata = {
        "cell_id": "",
        "batch_id": batch_id,
        "part_id": part_id,
        "measurement_type": "",
        "cycle_index": "",
        "diagnostic_part": "",
        "nominal_capacity_mah": "",
        "replicate_id": "",
        "soc_percent": "",
        "notes": "",
    }

    normalized = safe_member_path(member_path)
    if data_category == "cycling":
        cell_match = re.search(r"/(G\d+C\d+)/", f"/{normalized}/", re.IGNORECASE)
        cycle_match = re.search(r"cycling\s+(\d+)\.csv$", normalized, re.IGNORECASE)
        rpt_match = re.search(r"RPT\s+(\d+)\.csv$", normalized, re.IGNORECASE)
        metadata["cell_id"] = cell_match.group(1).upper() if cell_match else ""
        if cycle_match:
            metadata["measurement_type"] = "cycle_timeseries"
            metadata["cycle_index"] = cycle_match.group(1)
        elif rpt_match:
            metadata["measurement_type"] = "rpt_diagnostic"
            metadata["diagnostic_part"] = rpt_match.group(1)
        else:
            metadata["measurement_type"] = "cell_file"
    elif data_category == "rpt":
        rpt_match = re.search(r"rpt_cell_(\d+)_part(\d+)\.csv$", normalized, re.IGNORECASE)
        metadata["cell_id"] = f"cell_{rpt_match.group(1)}" if rpt_match else ""
        metadata["measurement_type"] = "rpt_diagnostic"
        metadata["diagnostic_part"] = rpt_match.group(2) if rpt_match else ""
    elif data_category == "thermal_runaway":
        thermal_match = re.search(
            r"(\d+)mAh(\d+)-(\d+)S0C\.xlsx$",
            normalized,
            re.IGNORECASE,
        )
        stem = Path(normalized).stem
        flexible_thermal_match = re.search(
            r"(?P<prefix>.+?)[-_]?(?P<soc>\d+)SOC(?:[-_].*?cell(?P<cell>\d+))?",
            stem,
            re.IGNORECASE,
        )
        capacity_mah_match = re.search(r"(\d+(?:\.\d+)?)\s*mAh", stem, re.IGNORECASE)
        capacity_ah_match = re.search(r"(\d+(?:\.\d+)?)\s*Ah", stem, re.IGNORECASE)
        metadata["measurement_type"] = "abuse_test_timeseries"
        if thermal_match:
            metadata["nominal_capacity_mah"] = thermal_match.group(1)
            metadata["replicate_id"] = thermal_match.group(2)
            metadata["soc_percent"] = thermal_match.group(3)
            metadata["cell_id"] = (
                f"{thermal_match.group(1)}mAh_rep{thermal_match.group(2)}"
                f"_soc{thermal_match.group(3)}"
            )
            metadata["notes"] = "soc_percent parsed from filename token ending in S0C"
        elif flexible_thermal_match:
            prefix = flexible_thermal_match.group("prefix")
            metadata["soc_percent"] = flexible_thermal_match.group("soc")
            metadata["replicate_id"] = flexible_thermal_match.group("cell") or ""
            if capacity_mah_match:
                metadata["nominal_capacity_mah"] = capacity_mah_match.group(1)
            elif capacity_ah_match:
                metadata["nominal_capacity_mah"] = str(int(float(capacity_ah_match.group(1)) * 1000))
            metadata["cell_id"] = (
                f"{slugify(prefix)}"
                f"{'_cell' + metadata['replicate_id'] if metadata['replicate_id'] else ''}"
                f"_soc{metadata['soc_percent']}"
            )
            metadata["notes"] = "soc_percent and cell replicate parsed from flexible SOC filename"

    return metadata


def csv_header_preview(zf: ZipFile, member_path: str, max_bytes: int) -> str:
    if not member_path.lower().endswith(".csv") or max_bytes <= 0:
        return ""
    try:
        with zf.open(member_path) as handle:
            raw = handle.read(max_bytes)
    except Exception:
        return ""
    text = raw.decode("utf-8", errors="replace")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    return first_line[:500]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, rows: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def relative_or_string(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def organize_archive(
    archive_path: Path,
    project_root: Path,
    raw_root: Path,
    copy_archives: bool,
    header_bytes: int,
    generated_at: str,
) -> tuple[ArchiveManifestRecord, list[FileInventoryRecord]]:
    with ZipFile(archive_path) as zf:
        infos = zf.infolist()
        member_names = [info.filename for info in infos]
        dataset_family, data_family, data_category, chemistry = classify_archive(
            archive_path,
            member_names,
        )
        dataset_id = f"{dataset_family}_{slugify(archive_path.stem)}"
        archive_slug = slugify(archive_path.stem)
        organized_raw_dir = raw_root / data_family / data_category / archive_slug
        organized_raw_dir.mkdir(parents=True, exist_ok=True)

        copied_path = organized_raw_dir / archive_path.name
        archive_copied = False
        if copy_archives:
            shutil.copy2(archive_path, copied_path)
            archive_copied = True

        files = [info for info in infos if not info.is_dir() and is_data_member(info.filename)]
        extensions = Counter(Path(info.filename).suffix.lower() or "<no_ext>" for info in files)
        cell_ids: set[str] = set()
        inventory_records: list[FileInventoryRecord] = []

        for info in files:
            metadata = parse_member_metadata(archive_path.name, info.filename, data_category)
            if metadata["cell_id"]:
                cell_ids.add(metadata["cell_id"])
            normalized_member = safe_member_path(info.filename)
            inventory_records.append(
                FileInventoryRecord(
                    dataset_id=dataset_id,
                    dataset_family=dataset_family,
                    data_category=data_category,
                    chemistry=chemistry,
                    source_archive_name=archive_path.name,
                    archive_member_path=info.filename,
                    normalized_member_path=normalized_member,
                    file_extension=Path(info.filename).suffix.lower(),
                    compressed_size_bytes=int(info.compress_size),
                    uncompressed_size_bytes=int(info.file_size),
                    cell_id=metadata["cell_id"],
                    batch_id=metadata["batch_id"],
                    part_id=metadata["part_id"],
                    measurement_type=metadata["measurement_type"],
                    cycle_index=metadata["cycle_index"],
                    diagnostic_part=metadata["diagnostic_part"],
                    nominal_capacity_mah=metadata["nominal_capacity_mah"],
                    replicate_id=metadata["replicate_id"],
                    soc_percent=metadata["soc_percent"],
                    header_preview=csv_header_preview(zf, info.filename, header_bytes),
                    notes=metadata["notes"],
                )
            )

        source_manifest = {
            "dataset_id": dataset_id,
            "dataset_family": dataset_family,
            "data_family": data_family,
            "data_category": data_category,
            "chemistry": chemistry,
            "source_archive_path": str(archive_path),
            "source_archive_sha256": sha256_file(archive_path) if copy_archives else "",
            "archive_copied": archive_copied,
            "copied_archive_path": relative_or_string(copied_path, project_root)
            if archive_copied
            else "",
            "file_count": len(files),
            "cell_count_estimate": len(cell_ids),
            "generated_at_utc": generated_at,
        }
        write_json(organized_raw_dir / "source_manifest.json", source_manifest)

        manifest_record = ArchiveManifestRecord(
            dataset_id=dataset_id,
            dataset_family=dataset_family,
            data_category=data_category,
            chemistry=chemistry,
            source_archive_name=archive_path.name,
            source_archive_path=str(archive_path),
            organized_raw_dir=relative_or_string(organized_raw_dir, project_root),
            archive_copied=archive_copied,
            copied_archive_path=relative_or_string(copied_path, project_root)
            if archive_copied
            else "",
            size_bytes=int(archive_path.stat().st_size),
            entry_count=len(infos),
            file_count=len(files),
            uncompressed_bytes=int(sum(info.file_size for info in files)),
            dominant_extensions=json.dumps(extensions.most_common(8), ensure_ascii=False),
            cell_count_estimate=len(cell_ids),
            generated_at_utc=generated_at,
            notes="archive referenced in project; pass --copy-archives to duplicate raw zip"
            if not archive_copied
            else "archive copied into organized raw directory",
        )
        return manifest_record, inventory_records


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_category_summary(inventory: list[FileInventoryRecord]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[FileInventoryRecord]] = {}
    for record in inventory:
        grouped.setdefault((record.dataset_family, record.data_category), []).append(record)

    rows = []
    for (dataset_family, data_category), records in sorted(grouped.items()):
        cells = {record.cell_id for record in records if record.cell_id}
        rows.append(
            {
                "dataset_family": dataset_family,
                "data_category": data_category,
                "file_count": len(records),
                "cell_count_estimate": len(cells),
                "total_uncompressed_bytes": sum(record.uncompressed_size_bytes for record in records),
                "extensions": json.dumps(
                    Counter(record.file_extension or "<no_ext>" for record in records).most_common(),
                    ensure_ascii=False,
                ),
                "recommended_next_processing": recommended_next_processing(data_category),
            }
        )
    return rows


def build_measurement_summary(inventory: list[FileInventoryRecord]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[FileInventoryRecord]] = {}
    for record in inventory:
        key = (record.dataset_family, record.data_category, record.measurement_type or "unknown")
        grouped.setdefault(key, []).append(record)

    rows = []
    for (dataset_family, data_category, measurement_type), records in sorted(grouped.items()):
        cells = {record.cell_id for record in records if record.cell_id}
        rows.append(
            {
                "dataset_family": dataset_family,
                "data_category": data_category,
                "measurement_type": measurement_type,
                "file_count": len(records),
                "cell_count_estimate": len(cells),
                "total_uncompressed_bytes": sum(record.uncompressed_size_bytes for record in records),
                "example_source_archive": records[0].source_archive_name,
                "example_member_path": records[0].archive_member_path,
            }
        )
    return rows


def recommended_next_processing(data_category: str) -> str:
    if data_category == "cycling":
        return "chunk CSV by cell_id/cycle_index, derive cycle-level features, then link to RUL labels"
    if data_category == "rpt":
        return "chunk CSV by cell_id/diagnostic_part, derive reference capacity and resistance diagnostics"
    if data_category == "thermal_runaway":
        return "inspect XLSX sheets, derive safety event timing, peak temperature, voltage collapse features"
    return "inspect schema before feature extraction"


def build_schema_hints(inventory: list[FileInventoryRecord]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[FileInventoryRecord]] = {}
    for record in inventory:
        if record.header_preview:
            key = (record.dataset_family, record.data_category, record.header_preview)
            grouped.setdefault(key, []).append(record)

    rows = []
    for (dataset_family, data_category, header), records in sorted(grouped.items()):
        columns = [column.strip() for column in header.split(",")]
        rows.append(
            {
                "dataset_family": dataset_family,
                "data_category": data_category,
                "header_preview": header,
                "column_count_estimate": len(columns),
                "example_source_archive": records[0].source_archive_name,
                "example_member_path": records[0].archive_member_path,
                "matching_file_count": len(records),
            }
        )
    return rows


def write_outputs(
    project_root: Path,
    processed_root: Path,
    manifests: list[ArchiveManifestRecord],
    inventory: list[FileInventoryRecord],
) -> None:
    manifest_rows = [asdict(record) for record in manifests]
    inventory_rows = [asdict(record) for record in inventory]
    category_rows = build_category_summary(inventory)
    measurement_rows = build_measurement_summary(inventory)
    schema_rows = build_schema_hints(inventory)

    write_csv(
        processed_root / "archive_manifest.csv",
        manifest_rows,
        list(ArchiveManifestRecord.__dataclass_fields__.keys()),
    )
    write_json(processed_root / "archive_manifest.json", manifest_rows)
    write_csv(
        processed_root / "file_inventory.csv",
        inventory_rows,
        list(FileInventoryRecord.__dataclass_fields__.keys()),
    )
    write_json(processed_root / "file_inventory.json", inventory_rows)
    if category_rows:
        write_csv(processed_root / "category_summary.csv", category_rows, list(category_rows[0].keys()))
        write_json(processed_root / "category_summary.json", category_rows)
    if measurement_rows:
        write_csv(
            processed_root / "measurement_summary.csv",
            measurement_rows,
            list(measurement_rows[0].keys()),
        )
        write_json(processed_root / "measurement_summary.json", measurement_rows)
    if schema_rows:
        write_csv(processed_root / "schema_hints.csv", schema_rows, list(schema_rows[0].keys()))
        write_json(processed_root / "schema_hints.json", schema_rows)

    config_rows = [
        {
            "dataset_id": record.dataset_id,
            "dataset_family": record.dataset_family,
            "data_category": record.data_category,
            "chemistry": record.chemistry,
            "source_archive_name": record.source_archive_name,
            "source_archive_path": record.source_archive_path,
            "organized_raw_dir": record.organized_raw_dir,
            "file_count": record.file_count,
            "cell_count_estimate": record.cell_count_estimate,
            "notes": record.notes,
        }
        for record in manifests
    ]
    write_csv(
        project_root / "configs" / "datasets" / "external_battery_archives.csv",
        config_rows,
        list(config_rows[0].keys()) if config_rows else [],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify and inventory external battery ZIP datasets.",
    )
    parser.add_argument(
        "--archives",
        nargs="*",
        default=DEFAULT_ARCHIVE_PATHS,
        help="ZIP archives to classify. Defaults to the known Desktop dataset collection.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root used for relative paths.",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw/external_battery_datasets"),
        help="Organized raw data directory.",
    )
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=Path("data/processed/external_battery_datasets"),
        help="Output directory for manifests and inventories.",
    )
    parser.add_argument(
        "--copy-archives",
        action="store_true",
        help="Copy ZIP files into the organized raw directories. This can require about 27 GB.",
    )
    parser.add_argument(
        "--header-bytes",
        type=int,
        default=4096,
        help="Bytes to read from CSV members for header previews.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = args.project_root.resolve()
    raw_root = (project_root / args.raw_root).resolve() if not args.raw_root.is_absolute() else args.raw_root
    processed_root = (
        (project_root / args.processed_root).resolve()
        if not args.processed_root.is_absolute()
        else args.processed_root
    )
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    manifests: list[ArchiveManifestRecord] = []
    inventory: list[FileInventoryRecord] = []
    for archive in args.archives:
        archive_path = Path(archive).resolve()
        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")
        manifest, records = organize_archive(
            archive_path=archive_path,
            project_root=project_root,
            raw_root=raw_root,
            copy_archives=args.copy_archives,
            header_bytes=args.header_bytes,
            generated_at=generated_at,
        )
        manifests.append(manifest)
        inventory.extend(records)

    write_outputs(project_root, processed_root, manifests, inventory)
    print(f"Wrote {len(manifests)} archive records and {len(inventory)} file records.")
    print(f"Processed manifest directory: {processed_root}")
    print(f"Raw organization directory: {raw_root}")


if __name__ == "__main__":
    main()
