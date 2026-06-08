# External Battery Feature Engineering

The external battery datasets are converted in two steps:

1. `modules/data_pipeline/extract_external_battery_tables.py` reads selected
   ZIP members and normalizes raw columns.
2. `modules/feature_engineering/build_external_battery_features.py` aggregates
   those normalized samples into model-facing feature tables.
3. For model-scale experiments,
   `modules/data_pipeline/extract_external_battery_by_cell.py` writes per-cell
   chunks and the feature builder can consume those chunks with
   `--source-mode by_cell`.

## Outputs

```text
data/features/external_battery_datasets/
  cycle_features.csv
  rpt_features.csv
  external_health_labels.csv
  external_label_summary.csv
  external_label_manifest.json
  protocol_regime_summary.csv
  cycle_features_sample.csv
  rpt_features_sample.csv
  thermal_runaway_features_sample.csv
  external_health_labels_sample.csv
  external_label_summary_sample.csv
  external_label_manifest_sample.json
  feature_build_summary.csv
  feature_build_summary.json
```

## Current Feature Groups

| Table | Grouping | Examples |
| --- | --- | --- |
| `cycle_features_sample.csv` | `cell_id`, `cycle_index`, source member | voltage/current/capacity/energy summaries, duration, charge/discharge state fractions, protocol boundary diagnostics |
| `rpt_features_sample.csv` | `cell_id`, `diagnostic_part`, source member | diagnostic capacity range, voltage drop, pulse SOC summary, pulse type count |
| `thermal_runaway_features_sample.csv` | source member, SOC, capacity, replicate | peak temperature, voltage minimum, max load/force, max displacement, safety event hint |

The non-sample `cycle_features.csv` and `rpt_features.csv` use the same feature
definitions, but they are built from `data/processed/external_battery_datasets/by_cell`.
When building by-cell features, the pipeline also writes
`protocol_regime_summary.csv`.

## Protocol Diagnostics

External cycle-life data may contain early formation effects or explicit protocol
changes. A local capacity drop after such a change is not automatically a
full-life EOL event.

`cycle_features.csv` therefore includes protocol diagnostic fields:

| Field | Meaning |
| --- | --- |
| `protocol_current_relative_change` | Relative change in `absolute_current_mean_a` from the previous cycle in the same cell |
| `protocol_charge_fraction_delta` | Absolute change in `charge_state_fraction` from the previous cycle |
| `protocol_duration_relative_change` | Relative change in cycle duration from the previous cycle |
| `protocol_boundary_flag` | True when current, charge-state fraction, or duration crosses the configured shift threshold |
| `protocol_boundary_reason` | Semicolon-separated reason for the boundary flag |
| `protocol_regime_index` | Consecutive protocol segment number within each cell |

`protocol_regime_summary.csv` aggregates each cell/regime segment and marks
short segments as `limited_protocol_window_less_than_50_observations`. RUL
training should not treat a threshold crossing inside such a segment as a final
EOL claim.

The thermal runaway table is kept separate from SOH/RUL labels. It should feed
future safety-risk and strategy-constraint models, not the first RUL baseline.

## External Labels

`modules/feature_engineering/build_external_health_labels.py` converts cycle and
RPT feature tables into SOH/RUL-style labels. The default label keys are:

| Label key family | Source table | Default capacity column |
| --- | --- | --- |
| `capacity_eol_70/75/80` | `cycle_features_sample.csv` | `capacity_delta_ah` |
| `rpt_capacity_eol_70/75/80` | `rpt_features_sample.csv` | `capacity_delta_ah` |

Rows are marked with `label_quality`. Short extraction windows are marked as
`limited_window_less_than_50_observations`; full extraction is needed before
using these labels for final model training. A threshold crossing inside a
short extraction window is a local diagnostic, not a confirmed full-life EOL
claim.

When `cycle_features.csv` includes `protocol_regime_index`, external cycle
labels are generated separately for each protocol regime. This prevents an
initial capacity from one protocol segment from being used to define EOL in a
later segment with a different current, duration, or charge/discharge state mix.

`label_quality` only describes observation-count and capacity validity. It does
not mean a row is safe for training. The label builder also writes trainability
guard fields:

| Field | Meaning |
| --- | --- |
| `protocol_assignment_quality` | Whether the label group has a usable protocol-regime assignment |
| `eol_boundary_quality` | Whether an observed EOL crossing is away from protocol-regime boundaries |
| `eol_distance_from_regime_start` | Observed EOL distance from the start of the current protocol regime |
| `eol_distance_to_regime_end` | Observed EOL distance to the end of the current protocol regime |
| `trainable_label` | True only when the label is usable, protocol-consistent, and not a boundary crossing |
| `trainable_label_quality` | Reason why the label is trainable or excluded |

By default, observed EOL crossings within five observations of a protocol-regime
start or end are marked `excluded_unreliable_boundary_crossing`. RPT labels are
marked `excluded_unknown_or_unmapped` until a reliable RPT-to-protocol-regime
assignment is implemented. RPT labels may be used as diagnostics, but not as
training targets.

Before any exploratory model work, run
`modules/feature_engineering/audit_external_trainable_labels.py`. The audit
exports trainable cycle-only labels, excluded labels, a label coverage matrix,
and a JSON/Markdown report under `outputs/label_audit/external_trainable_labels`.
This audit is a data-readiness artifact, not a model-performance result.

## Command

```powershell
cd "C:\Users\Lenovo\Documents\predication_battery_life & strategy_optimization"
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\feature_engineering\build_external_battery_features.py
```

Build per-cell features after running the by-cell extractor:

```powershell
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\feature_engineering\build_external_battery_features.py --source-mode by_cell --input-root data\processed\external_battery_datasets\by_cell
```

Then build preliminary external SOH/RUL labels:

```powershell
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\feature_engineering\build_external_health_labels.py
```

Build non-sample labels from per-cell features:

```powershell
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\feature_engineering\build_external_health_labels.py --source-mode by_cell
```

Run the data extraction step first if sample inputs are missing:

```powershell
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\data_pipeline\extract_external_battery_tables.py
```

## Next Step

Once the sample feature tables look stable, increase extraction limits and build
larger chunked features per cell. Before training on external labels, inspect
`protocol_regime_summary.csv` and confirm that each target label is computed
inside a sufficiently long and protocol-consistent observation window.
