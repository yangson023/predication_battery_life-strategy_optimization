# LMB Label Policy

本文档定义当前锂金属电池项目的标签政策。它只用于指导后续 label builder 和 label audit，不生成标签 CSV，不训练模型，不进入 `rul-prediction`。

## 当前阶段

项目已经完成：

- BTSDA 三层 CSV tiny validation。
- canonical export audit。
- quality flag type audit。
- 第一版 canonical feature builder。

当前允许进入：

```text
label policy design -> label builder audit scan
```

当前仍禁止：

```text
model training
random row split
baseline performance claims
Li||Li / Li||Cu mixed-task labels
```

当前 feature tables：

```text
data/features/lmb_lab/canonical_features_20260618/lili_cycle_features.csv
data/features/lmb_lab/canonical_features_20260618/licu_cycle_features.csv
```

当前数据规模：

| cell group | canonical cells | feature rows | status |
| --- | ---: | ---: | --- |
| Li||Li | 3 | 810 | label scan allowed; trainable labels blocked for now |
| Li||Cu | 4 | 734 | label scan allowed; trainability audit required |

## Label Type Definitions

| label type | definition | training use |
| --- | --- | --- |
| `observed` | Failure or warning event is directly observed inside the available cycling window. | Can be considered for trainability after audit. |
| `censored` | No event is observed before the experiment ends. The cell may still fail later. | Can support survival-style audit, not ordinary positive/negative training without care. |
| `protocol_censored` | Experiment ends or changes because of protocol, equipment, manual stop, or export window, not natural failure. | Audit only unless protocol metadata is explicit. |
| `audit_only` | Signal is scientifically interesting but not yet reliable as a trainable target. | Not trainable. |
| `trainable_label` | Label has a defined signal, threshold, window, censoring rule, and leakage check. | Eligible for exploratory baseline only after label audit. |
| `limited_window_label` | Label is computed from a short observation window, often low-cycle cells. | Feature/audit use; training requires explicit warning. |

## Li||Cu Label Policy

Li||Cu CE half-cells are primarily CE and plating/stripping efficiency systems. Labels should focus on CE instability, capacity incompleteness, and lithium inventory depletion proxies. CE-derived labels are high leakage risk and must use temporal offsets.

| label key | signal source | candidate threshold | sustained window | observed rule | censored rule | trainability | leakage risk | current readiness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `incomplete_capacity_event` | `charge_capacity_mah`, `discharge_capacity_mah`, `incomplete_cycle_flag` | charge or discharge capacity below protocol-relevant floor, initially `charge_capacity_mah < 0.5` or zero-cap flag | 1 cycle for terminal audit; 2-3 cycles for stable event | First cycle where capacity incompleteness appears and does not recover within next few cycles. | No incomplete event before final cycle. | P0 audit label; candidate trainable after manual review. | Low-to-medium. It is not CE-derived, but still close to failure. | Best first label for Li||Cu. |
| `ce_collapse` | future CE sequence from `coulombic_efficiency_percent` | future CE below 50 percent or abrupt collapse relative to previous window | future `K >= 5` cycles recommended | At cycle `i`, event is observed if `min(CE[i+1:i+K]) < threshold`. | No future collapse before end; final `K` cycles are right-censored. | Candidate trainable only with time-shifted labels. | High if current CE is used directly. | Useful, but label builder must enforce future-window rule. |
| `ce_instability` | `ce_rolling_std_past_5`, CE trajectory | rolling std above cell-specific baseline, e.g. `> 3x` early-cycle baseline | 3-5 cycles | Sustained CE volatility above threshold. | No sustained instability before end. | Audit first; trainability depends on threshold stability. | Medium, because CE features and CE label share source. | Good audit label. |
| `ce_sustained_degradation` | CE rolling trend, `ce_rolling_mean_past_5`, future CE window | sustained drift away from early-cycle CE, or future CE crossing a reviewed threshold | 5-10 cycles | CE remains degraded for the full sustained window. | No crossing, or insufficient future window. | Candidate after leakage audit. | High unless future label and past-only features are separated. | Conditional. |
| `lithium_inventory_loss_proxy` | `cumulative_irreversible_capacity_past`, incomplete capacity flags | cumulative irreversible capacity exceeds reviewed fraction of nominal charge amount | 5+ cycles | Proxy crosses threshold and aligns with capacity incompleteness. | No crossing before end. | Audit only until material metadata is available. | Medium; CE-derived and protocol-dependent. | Not first training target. |
| `protocol_censored` | experiment end, export window, manual stop, protocol metadata | final cycle reached without reviewed failure event | not applicable | Not an event label; records that failure was not naturally observed. | Cell ended without event or with unclear stop reason. | Not trainable as failure. | Low. | Required for every Li||Cu cell. |

Li||Cu first label builder priority:

1. `incomplete_capacity_event`
2. `ce_collapse` with future-window offset
3. `ce_instability` audit scan
4. `protocol_censored`
5. `lithium_inventory_loss_proxy` later, after metadata review

## Li||Li Label Policy

Li||Li symmetric cells are voltage-domain systems. Capacity and CE flags are not primary failure definitions. Current data show stable low-flag behavior, so Li||Li trainable labels are blocked until voltage-domain events are reviewed.

| label key | signal source | candidate threshold | sustained window | observed rule | censored rule | trainability | need full record | current readiness |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `polarization_growth` | `voltage_hysteresis_v`, `hysteresis_rolling_mean_past_5`, `hysteresis_slope_past_10` | hysteresis exceeds `2x` early baseline or slope remains positive above reviewed threshold | 10 cycles | Sustained hysteresis growth beyond threshold. | No sustained growth before end. | Audit only for now; may become trainable with more observed events. | No for first audit; full record helps. | Good audit label. |
| `voltage_hysteresis_failure` | `voltage_hysteresis_v`, `end_voltage_gap_v` | absolute hysteresis or end voltage gap crosses reviewed limit | 3-5 cycles | Persistent high hysteresis/gap event. | No crossing before final cycle. | Audit only until thresholds are reviewed. | No for first scan. | Candidate audit. |
| `voltage_instability` | `voltage_instability_warning`, `record_voltage_std_v`, hysteresis deviation | warning true or voltage std/deviation above baseline | 3 cycles | Repeated instability warnings. | No repeated warnings. | Audit only; record sample is limited. | Full record preferred. | Useful but sample-limited. |
| `soft_short_warning` | `rest_voltage_drop_mv_per_hour`, rest voltage relaxation | rest voltage drop exceeds reviewed mV/hour threshold | 1-3 rest events | Rest voltage drop is abnormal and repeats or coincides with other voltage instability. | No abnormal rest drop before end. | Audit only until full record or expert threshold is reviewed. | Full record strongly recommended. | Important future label, not trainable now. |
| `incomplete_cycle_warning` | `incomplete_cycle_warning`, capacity completeness flags | warning true | 1 cycle | Incomplete cycle appears near end or with voltage abnormality. | No warning. | Audit only for Li||Li; not primary target. | No. | Secondary audit signal. |
| `protocol_censored` | experiment end, manual stop, export window | final cycle reached without reviewed voltage event | not applicable | Not an event label. | Cell ends without observed failure. | Not trainable as failure. | No. | Required for every Li||Li cell. |

Li||Li first label builder priority:

1. `polarization_growth` audit scan
2. `voltage_hysteresis_failure` audit scan
3. `soft_short_warning` audit scan
4. `protocol_censored`
5. No trainable Li||Li labels until observed voltage-domain events are confirmed

## Leakage Protection Rules

1. Feature builder and label builder must remain separate scripts.
2. CE rolling features must use only past cycles. For cycle `i`, rolling CE features may use only cycles `< i`.
3. If a label uses future CE crossing, the feature row for cycle `i` must not include CE values from `i+1` or later.
4. A label such as `label(i) = CE_i < threshold` is prohibited for model training if `CE_i` is also present in the same feature row.
5. `coulombic_efficiency_percent` and `irreversible_capacity_mah` are label-proximal for Li||Cu. They must be re-audited before any model feature selection.
6. `exclude_from_label_training` and `audit_warning_only` are quality gate fields, not target labels.
7. Label output must not be merged with feature output until trainable-label audit passes.

## Current Data Readiness

| group | cells | readiness |
| --- | --- | --- |
| Li||Li | `26-0414`, `26-0421`, `26-0429-009(li-li)` | Audit scans allowed. Trainable labels blocked because observed voltage-domain EOL is not confirmed. |
| Li||Cu | `26-0428-009`, `26-0428-085`, `26-0429-002(li-Cu)`, `26-0512(li-Cu)` | Label scan allowed. `incomplete_capacity_event` is the safest first candidate. CE labels require leakage controls. |

Low-cycle handling:

- `26-0429-009(li-li)` and `26-0512(li-Cu)` should remain in audit and early-cycle feature checks.
- Low-cycle cells may produce `limited_window_label`.
- Low-cycle cells should not be used to claim final model performance.

Labels currently possible for audit:

- Li||Cu: `incomplete_capacity_event`, `ce_collapse`, `ce_instability`, `protocol_censored`.
- Li||Li: `polarization_growth`, `voltage_hysteresis_failure`, `voltage_instability`, `soft_short_warning`, `protocol_censored`.

Labels temporarily blocked for training:

- All Li||Li trainable labels.
- Li||Cu CE labels until time-shift and leakage audit are implemented.
- Any label requiring full record until full-record feature extraction exists.

## First Label Builder Order

The first label builder should be an audit builder, not a training-label exporter.

Recommended order:

1. Implement audit-only label scan for Li||Cu `incomplete_capacity_event`.
2. Implement Li||Cu future-window `ce_collapse` scan with `K >= 5`.
3. Implement Li||Cu `protocol_censored` and final-window censoring.
4. Implement Li||Li `polarization_growth` and `voltage_hysteresis_failure` scans as audit-only.
5. Implement Li||Li `soft_short_warning` only as sample-limited audit.
6. Generate trainability audit.
7. Only after trainability audit, export baseline-ready labels.

## Next Gate

```text
label_builder_allowed = True
model_training_allowed = False
```

The next implementation may create an audit label scan, but must not train a model and must not call generated labels final training labels until trainability audit passes.

## Audit-Only Scanner Status

The first audit-only scanner has been added:

```text
modules/feature_engineering/scan_lmb_audit_only_labels.py
```

Current output:

```text
outputs/lmb_lab_intake/lmb_audit_label_scan_20260618
```

This scanner produces event review files only:

- `lmb_audit_event_scan.csv`
- `per_cell_audit_label_summary.csv`
- `audit_label_schema_check.csv`
- `lmb_audit_label_scan_report.json`
- `lmb_audit_label_scan_report.md`

Current findings:

| label key | observed candidate count | interpretation |
| --- | ---: | --- |
| `incomplete_capacity_event` | 357 | Best Li||Cu first review target. |
| `ce_collapse` | 20 | Useful terminal/future-window candidate; high leakage risk until reviewed. |
| `ce_instability` | 677 | Too frequent for direct training; threshold-sensitive audit signal. |
| `polarization_growth` | 103 | Mainly Li||Li `26-0414`; needs voltage-domain review. |
| `voltage_hysteresis_failure` | 123 | Mainly Li||Li `26-0414`; candidate audit signal. |
| `voltage_instability` | 69 | Sample-limited voltage audit signal. |
| `incomplete_cycle_warning` | 3 | Secondary audit signal. |

Gate decision after this scan:

```text
trainability_audit_allowed = True
baseline_ready_label_export_allowed = False
model_training_allowed = False
```

The next step should review thresholds and build a trainability audit, not a
model.
