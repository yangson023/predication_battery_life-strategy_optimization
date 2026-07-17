"""Parse BTS Step XML files as LMB metadata suggestions.

This parser reads BTS step/protocol XML files only. It does not read BTSDA raw
cycle/step/record data, create labels, train models, enter the RUL prediction
pipeline, or overwrite partner metadata Excel files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


STEP_TYPE_MAP = {
    "1": "cc_charge_or_plating",
    "2": "cc_discharge_or_stripping",
    "3": "cv_charge",
    "4": "rest",
    "5": "loop",
    "6": "stop",
}

SUMMARY_COLUMNS = [
    "xml_label",
    "source_xml_path",
    "xml_guid",
    "xml_hash_sha256",
    "parsed_at_utc",
    "decode_codec",
    "config_date_raw",
    "config_date_parsed",
    "inferred_experiment_date",
    "date_confidence",
    "creator",
    "remark_raw",
    "electrolyte_hint",
    "electrolyte_hint_confidence",
    "pn_code",
    "record_interval_ms",
    "step_count",
    "rest_time_ms",
    "rest_time_hours",
    "current_ma",
    "capacity_limit_raw",
    "capacity_limit_raw_unit_guess",
    "capacity_limit_mah_if_mas",
    "stop_voltage_raw",
    "stop_voltage_v_if_raw_10000_scale",
    "cycle_count",
    "start_step",
    "voltage_protect_upper_raw",
    "voltage_protect_lower_raw",
    "voltage_protect_confidence",
    "inferred_protocol_summary",
    "fields_safe_to_fill",
    "fields_need_manual_confirmation",
    "unit_flagged_fields",
    "training_allowed_now",
]

STEP_COLUMNS = [
    "xml_label",
    "source_xml_path",
    "step_id",
    "step_type_raw",
    "step_type_name",
    "record_interval_ms",
    "limit_time_ms",
    "limit_current_ma",
    "limit_capacity_raw",
    "limit_stop_voltage_raw",
    "cycle_count",
    "start_step",
    "voltage_protect_upper_raw",
    "voltage_protect_lower_raw",
]


@dataclass
class BtsStepXmlMetadata:
    xml_label: str
    source_xml_path: str
    xml_guid: str
    xml_hash_sha256: str
    parsed_at_utc: str
    decode_codec: str
    config_date_raw: str
    config_date_parsed: str
    inferred_experiment_date: str
    date_confidence: str
    creator: str
    remark_raw: str
    electrolyte_hint: str
    electrolyte_hint_confidence: str
    pn_code: str
    record_interval_ms: int | str
    step_count: int
    rest_time_ms: int | str
    rest_time_hours: float | str
    current_ma: float | str
    capacity_limit_raw: int | str
    capacity_limit_raw_unit_guess: str
    capacity_limit_mah_if_mas: float | str
    stop_voltage_raw: int | str
    stop_voltage_v_if_raw_10000_scale: float | str
    cycle_count: int | str
    start_step: int | str
    voltage_protect_upper_raw: int | str
    voltage_protect_lower_raw: int | str
    voltage_protect_confidence: str
    inferred_protocol_summary: str
    fields_safe_to_fill: list[str]
    fields_need_manual_confirmation: list[str]
    unit_flagged_fields: list[str]
    training_allowed_now: bool
    steps: list[dict[str, Any]]


def decode_xml_bytes(raw_bytes: bytes) -> tuple[str, str]:
    """Decode BTS XML bytes.

    Some BTS files declare GB2312 even when the bytes are UTF-8. Try UTF-8
    first to preserve Chinese remarks, then common Simplified Chinese codecs.
    """

    for codec in ("utf-8", "gb18030", "gbk", "gb2312"):
        try:
            return raw_bytes.decode(codec), codec
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace"), "utf-8-replace"


def parse_xml_text(raw_bytes: bytes) -> tuple[ET.Element, str]:
    text, codec = decode_xml_bytes(raw_bytes)
    text = re.sub(r'encoding\s*=\s*["\'][^"\']+["\']', 'encoding="UTF-8"', text, count=1)
    return ET.fromstring(text.encode("utf-8")), codec


def attr(element: ET.Element | None, name: str = "Value", default: str = "") -> str:
    if element is None:
        return default
    value = element.get(name)
    return value if value is not None else default


def to_int(value: str) -> int | str:
    if value == "":
        return ""
    try:
        return int(float(value))
    except ValueError:
        return ""


def to_float(value: str) -> float | str:
    if value == "":
        return ""
    try:
        return float(value)
    except ValueError:
        return ""


def parse_bts_date(raw: str) -> str:
    if not raw:
        return ""
    for fmt, size in [("%Y%m%d%H%M%S", 14), ("%Y%m%d", 8)]:
        try:
            return datetime.strptime(raw[:size], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def electrolyte_hint_from_remark(remark: str) -> str:
    if not remark:
        return ""
    hints: list[str] = []
    checks = [
        ("醚", "ether_based"),
        ("酯", "ester_based"),
        ("碳酸酯", "carbonate_based"),
        ("LHCE", "LHCE_code_hint"),
        ("HCE", "HCE_code_hint"),
        ("LiFSI", "LiFSI_hint"),
        ("LiTFSI", "LiTFSI_hint"),
        ("LiPF6", "LiPF6_hint"),
        ("LiNO3", "LiNO3_hint"),
        ("DME", "DME_hint"),
        ("DOL", "DOL_hint"),
        ("EC", "EC_hint"),
        ("DEC", "DEC_hint"),
        ("DMC", "DMC_hint"),
        ("FEC", "FEC_hint"),
    ]
    for token, code in checks:
        if token.lower() in remark.lower():
            hints.append(code)
    return ";".join(dict.fromkeys(hints))


def capacity_unit_guess(raw_value: int | str, current_ma: float | str) -> str:
    if raw_value == "" or current_ma == "":
        return "unit_needs_confirmation"
    raw_float = float(raw_value)
    current_float = float(current_ma)
    if current_float == 0:
        return "unit_needs_confirmation"
    if abs(raw_float / 3600.0 - current_float) <= abs(current_float * 0.3):
        return "probable_mAs"
    return "unit_needs_confirmation"


def first_nonblank(values: list[Any]) -> Any:
    for value in values:
        if value not in ("", None):
            return value
    return ""


def extract_step_rows(config: ET.Element, xml_label: str, source_path: Path) -> list[dict[str, Any]]:
    step_info = config.find("Step_Info")
    if step_info is None:
        return []
    rows: list[dict[str, Any]] = []
    for step in list(step_info):
        if not step.tag.startswith("Step"):
            continue
        step_type = step.get("Step_Type", "")
        protect = step.find("Protect/Main/Volt")
        row = {
            "xml_label": xml_label,
            "source_xml_path": str(source_path.resolve()),
            "step_id": step.get("Step_ID", ""),
            "step_type_raw": step_type,
            "step_type_name": STEP_TYPE_MAP.get(step_type, f"unknown_{step_type}"),
            "record_interval_ms": to_int(attr(step.find("Record/Main/Time"))),
            "limit_time_ms": to_int(attr(step.find("Limit/Main/Time"))),
            "limit_current_ma": to_float(attr(step.find("Limit/Main/Curr"))),
            "limit_capacity_raw": to_int(attr(step.find("Limit/Main/Cap"))),
            "limit_stop_voltage_raw": to_int(attr(step.find("Limit/Main/Stop_Volt"))),
            "cycle_count": to_int(attr(step.find("Limit/Other/Cycle_Count"))),
            "start_step": to_int(attr(step.find("Limit/Other/Start_Step"))),
            "voltage_protect_upper_raw": to_int(attr(protect.find("Upper") if protect is not None else None)),
            "voltage_protect_lower_raw": to_int(attr(protect.find("Lower") if protect is not None else None)),
        }
        rows.append(row)
    return rows


def voltage_protect_confidence(upper: int | str, lower: int | str) -> str:
    if upper == 40000 and lower == -40000:
        return "likely_bts_default_protection_not_active_limit"
    if upper == "" and lower == "":
        return "not_available"
    return "needs_confirmation"


def protocol_summary(rest_ms: int | str, current_ma: float | str, capacity_raw: int | str, stop_voltage_raw: int | str, cycle_count: int | str, start_step: int | str) -> str:
    rest_hours = round(float(rest_ms) / 3_600_000.0, 3) if rest_ms != "" else "unknown"
    return (
        f"rest={rest_hours}h; current={current_ma or 'unknown'}mA; "
        f"capacity_limit_raw={capacity_raw or 'unknown'}; stop_voltage_raw={stop_voltage_raw or 'unknown'}; "
        f"cycle_count={cycle_count or 'unknown'}; loop_start_step={start_step or 'unknown'}"
    )


def parse_bts_step_xml(xml_path: Path, xml_label: str | None = None) -> BtsStepXmlMetadata:
    if not xml_path.exists():
        raise FileNotFoundError(xml_path)
    label = xml_label or xml_path.stem
    raw_bytes = xml_path.read_bytes()
    root, codec = parse_xml_text(raw_bytes)
    config = root.find("config")
    if config is None:
        raise ValueError("Missing <config> element")

    head = config.find("Head_Info")
    config_date_raw = config.get("date", "")
    config_date = parse_bts_date(config_date_raw)
    creator = attr(head.find("Creator") if head is not None else None)
    remark = attr(head.find("Remark") if head is not None else None)
    pn_code = attr(head.find("PN") if head is not None else None)
    record_interval = to_int(attr(config.find("Whole_Prt/Record/Main/Time")))
    step_rows = extract_step_rows(config, label, xml_path)
    step_count_raw = config.find("Step_Info").get("Num", "") if config.find("Step_Info") is not None else ""
    step_count = int(step_count_raw) if step_count_raw else len(step_rows)

    rest_time = first_nonblank([row["limit_time_ms"] for row in step_rows if row["step_type_raw"] == "4"])
    current_ma = first_nonblank([row["limit_current_ma"] for row in step_rows if row["limit_current_ma"] != ""])
    capacity_raw = first_nonblank([row["limit_capacity_raw"] for row in step_rows if row["limit_capacity_raw"] != ""])
    stop_voltage = first_nonblank([row["limit_stop_voltage_raw"] for row in step_rows if row["limit_stop_voltage_raw"] != ""])
    # A BTS program can contain a short formation loop followed by a long-cycle
    # loop. Preserve every loop rather than silently reporting only the first.
    cycle_counts = [row["cycle_count"] for row in step_rows if row["cycle_count"] != ""]
    start_steps = [row["start_step"] for row in step_rows if row["start_step"] != ""]
    cycle_count = ";".join(str(value) for value in cycle_counts)
    start_step = ";".join(str(value) for value in start_steps)
    upper = first_nonblank([row["voltage_protect_upper_raw"] for row in step_rows if row["voltage_protect_upper_raw"] != ""])
    lower = first_nonblank([row["voltage_protect_lower_raw"] for row in step_rows if row["voltage_protect_lower_raw"] != ""])
    cap_guess = capacity_unit_guess(capacity_raw, current_ma)
    cap_mah = round(float(capacity_raw) / 3600.0, 6) if cap_guess == "probable_mAs" else ""

    safe_to_fill = [
        field
        for field, value in [
            ("实验日期", config_date),
            ("操作者", creator),
            ("静置时间", rest_time),
            ("循环协议", step_rows),
            ("截止条件", stop_voltage or capacity_raw),
        ]
        if value not in ("", None, [])
    ]
    fields_need_manual_confirmation = [
        "终止原因",
        "失效模式/现象",
        "完整电解液配方",
        "锂盐",
        "锂盐浓度",
        "电解液添加剂",
        "电流密度(mA/cm²)需要电极面积确认",
        "面容量(mAh/cm²)需要电极面积和 Cap 单位确认",
        "化成协议",
        "隔膜材料/型号",
    ]
    unit_flags = []
    if capacity_raw != "":
        unit_flags.append("capacity_limit_raw_unit_needs_confirmation")
    if upper != "" or lower != "":
        unit_flags.append("voltage_protect_raw_unit_and_role_need_confirmation")

    rest_hours = round(float(rest_time) / 3_600_000.0, 6) if rest_time != "" else ""
    stop_v = round(float(stop_voltage) / 10000.0, 6) if stop_voltage != "" else ""
    return BtsStepXmlMetadata(
        xml_label=label,
        source_xml_path=str(xml_path.resolve()),
        xml_guid=config.get("Guid", ""),
        xml_hash_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        parsed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        decode_codec=codec,
        config_date_raw=config_date_raw,
        config_date_parsed=config_date,
        inferred_experiment_date=config_date,
        date_confidence="direct" if config_date else "unavailable",
        creator=creator,
        remark_raw=remark,
        electrolyte_hint=electrolyte_hint_from_remark(remark),
        electrolyte_hint_confidence="hint_only" if remark else "unavailable",
        pn_code=pn_code,
        record_interval_ms=record_interval,
        step_count=step_count,
        rest_time_ms=rest_time,
        rest_time_hours=rest_hours,
        current_ma=current_ma,
        capacity_limit_raw=capacity_raw,
        capacity_limit_raw_unit_guess=cap_guess,
        capacity_limit_mah_if_mas=cap_mah,
        stop_voltage_raw=stop_voltage,
        stop_voltage_v_if_raw_10000_scale=stop_v,
        cycle_count=cycle_count,
        start_step=start_step,
        voltage_protect_upper_raw=upper,
        voltage_protect_lower_raw=lower,
        voltage_protect_confidence=voltage_protect_confidence(upper, lower),
        inferred_protocol_summary=protocol_summary(rest_time, current_ma, capacity_raw, stop_voltage, cycle_count, start_step),
        fields_safe_to_fill=safe_to_fill,
        fields_need_manual_confirmation=fields_need_manual_confirmation,
        unit_flagged_fields=unit_flags,
        training_allowed_now=False,
        steps=step_rows,
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_report(metadata: BtsStepXmlMetadata) -> str:
    lines = [
        "# BTS Step XML Metadata Report",
        "",
        "This is a metadata suggestion report. It is not model performance and does not create training labels.",
        "",
        f"- XML label: `{metadata.xml_label}`",
        f"- Inferred experiment date: `{metadata.inferred_experiment_date or 'N/A'}`",
        f"- Creator: `{metadata.creator or 'N/A'}`",
        f"- Remark: `{metadata.remark_raw or 'N/A'}`",
        f"- Electrolyte hint: `{metadata.electrolyte_hint or 'N/A'}`",
        f"- Protocol summary: `{metadata.inferred_protocol_summary}`",
        f"- Training allowed now: `{metadata.training_allowed_now}`",
        "",
        "## Safe To Fill As Suggestions",
        "",
    ]
    lines.extend(f"- `{field}`" for field in metadata.fields_safe_to_fill)
    lines.extend(["", "## Needs Manual Confirmation", ""])
    lines.extend(f"- `{field}`" for field in metadata.fields_need_manual_confirmation)
    lines.extend(["", "## Unit-Flagged Fields", ""])
    lines.extend(f"- `{field}`" for field in metadata.unit_flagged_fields)
    lines.extend(
        [
            "",
            "## Gate",
            "",
            "- `training_allowed_now = False`",
            "- `model_training_allowed = False`",
            "- XML planned cycle count must not be treated as actual termination reason.",
            "- `electrolyte_hint` is not a full electrolyte formulation.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_and_write(input_xml: Path, output_dir: Path, xml_label: str | None = None) -> BtsStepXmlMetadata:
    metadata = parse_bts_step_xml(input_xml, xml_label=xml_label)
    output_dir.mkdir(parents=True, exist_ok=True)
    flat = asdict(metadata).copy()
    flat["fields_safe_to_fill"] = ";".join(metadata.fields_safe_to_fill)
    flat["fields_need_manual_confirmation"] = ";".join(metadata.fields_need_manual_confirmation)
    flat["unit_flagged_fields"] = ";".join(metadata.unit_flagged_fields)
    flat.pop("steps", None)
    write_csv(output_dir / "bts_step_xml_metadata_summary.csv", [flat], SUMMARY_COLUMNS)
    write_csv(output_dir / "bts_step_protocol_steps.csv", metadata.steps, STEP_COLUMNS)
    with (output_dir / "bts_step_metadata_report.json").open("w", encoding="utf-8") as handle:
        json.dump(asdict(metadata), handle, ensure_ascii=False, indent=2)
    (output_dir / "bts_step_metadata_report.md").write_text(build_report(metadata), encoding="utf-8")
    return metadata


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-xml", required=True)
    parser.add_argument("--xml-label", default=None)
    parser.add_argument("--output-dir", default="outputs/lmb_lab_intake/bts_step_xml_metadata_audit")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_arg_parser().parse_args()
    metadata = parse_and_write(Path(args.input_xml), Path(args.output_dir), args.xml_label)
    print(json.dumps({"xml_label": metadata.xml_label, "training_allowed_now": False}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
