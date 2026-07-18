# Low-Memory Feature Builder Design

This document describes the memory-safe external battery feature builder used
before running Round 1c feature generation. It is a design and implementation
guide only; it is not a model-training result.

## Why Full `read_csv` Is Unsafe

Round 1c has per-cell cycle CSV files of several GB each. Loading one of these
files with full-table `pandas.read_csv` can require much more memory than the
raw file size because pandas allocates parsed columns, indexes, temporary parse
buffers, grouped objects, and intermediate copies.

On a laptop this can cause paging, stalled runs, or interrupted feature outputs.
Interrupted outputs are risky because downstream label generation could consume
incomplete features if completion checks are weak.

## Chunked CSV Strategy

The low-memory builder is implemented at:

`modules/feature_engineering/build_external_battery_features_low_memory.py`

It supports:

```text
--source-mode by_cell
--input-root
--output-root
--chunksize
--overwrite
```

The builder processes one per-cell CSV at a time with pandas `chunksize`. It
updates per-cycle or per-RPT accumulators and never concatenates the raw chunks
into a full source table.

The default command shape is:

```powershell
python modules\feature_engineering\build_external_battery_features_low_memory.py `
  --source-mode by_cell `
  --input-root "D:\battery_archive\processed_cache\by_cell_expansion_round1c" `
  --output-root data\features\external_battery_datasets_expansion_round1c `
  --chunksize 250000
```

Do not run this command on Round 1c until synthetic and tiny real-slice
validation pass.

## Cycle Feature Statistics

For `cycle_features.csv`, the builder accumulates:

- identity columns such as dataset, cell, batch, part, archive, and member path
- `cycle_index`
- raw sample count
- duration from `elapsed_time_s`, `relative_time_raw`, or time-like columns
- current mean, standard deviation, minimum, maximum, and last value
- voltage mean, standard deviation, minimum, maximum, and last value
- capacity mean, standard deviation, minimum, maximum, and last value
- energy mean, standard deviation, minimum, maximum, and last value
- charge/discharge state fractions
- absolute current mean
- capacity delta
- protocol boundary diagnostics after cycle-level rows are finalized

Protocol diagnostics are still computed with the existing logic from
`build_external_battery_features.py` so downstream label guards keep the same
meaning.

## RPT Feature Statistics

For `rpt_features.csv`, the builder accumulates:

- identity columns
- `diagnostic_part`
- raw sample count
- duration
- current, voltage, capacity, energy, and pulse-SOC numeric summaries
- capacity delta
- voltage drop
- pulse type count

RPT remains audit-only. The builder writes RPT features for diagnostics, but it
does not change the project rule that RPT labels are excluded from trainable
outputs until reliable protocol-regime assignment exists.

## Schema Compatibility

The low-memory output is intended to match the existing by-cell feature schema:

- `cycle_features.csv`
- `rpt_features.csv`
- `protocol_regime_summary.csv`
- `feature_build_summary.csv`
- `feature_build_summary.json`
- `feature_build_report.json`
- `feature_schema_check.csv`

`feature_schema_check.csv` records whether the generated cycle and RPT feature
tables match the expected column sets. Extra diagnostic fields are kept in
reports instead of being mixed into the main feature tables.

## Small-Sample Validation

Validation must happen before Round 1c full processing.

Required checks:

1. synthetic tiny CSV files finish with very small chunks, such as
   `--chunksize 1` or `--chunksize 2`
2. first/last/mean/min/max/count/missingness accumulators behave correctly
3. chunk boundaries do not change feature values
4. raw chunks are not concatenated into a full DataFrame
5. output schema check passes
6. existing feature-builder tests still pass

Current unit test:

```powershell
python -m unittest tests.test_build_external_battery_features_low_memory
```

## Tiny Real-Slice Validation

A tiny real-slice validation was run on one Round 1c cell only:

| Item | Value |
| --- | --- |
| Source cell | `G4C1` |
| Source root | `D:\battery_archive\processed_cache\by_cell_expansion_round1c` |
| Tiny input root | `data/processed/external_battery_datasets/by_cell_round1c_tiny_validation` |
| Feature output root | `data/features/external_battery_datasets_expansion_round1c_tiny_validation` |
| Label compatibility output root | `data/features/external_battery_datasets_expansion_round1c_tiny_validation_labels` |
| Cycle rows sampled | 5000 |
| RPT rows sampled | 5000 |
| Builder chunksize | 1000 |

Feature output check:

| Output | Result |
| --- | ---: |
| `cycle_features.csv` | 1 row, 43 columns |
| `rpt_features.csv` | 1 row, 41 columns |
| `protocol_regime_summary.csv` | 1 row, 12 columns |
| `feature_schema_check.csv` | pass for cycle and RPT |
| `feature_build_report.json` | completion status `complete` |

Label-builder compatibility check:

| Output | Result |
| --- | ---: |
| `external_health_labels.csv` | 6 rows |
| `external_label_summary.csv` | 6 rows |
| `label_quality` | all `limited_window_less_than_50_observations` |
| source tables | 3 cycle labels, 3 RPT labels |

This validation only proves that the low-memory builder can read a real Round
1c slice, emit the expected schema, and produce feature outputs that the label
builder can consume. It is not evidence of model performance and does not create
trainable labels.

## Handling Round 1c After Validation

Synthetic tests and the G4C1 tiny real-slice validation have passed. The next
step can be controlled Round 1c feature generation, provided the run is treated
as feature engineering only and monitored for memory, runtime, and output
completeness.

Round 1c feature generation should write only small feature outputs under:

`data/features/external_battery_datasets_expansion_round1c`

It must not create new processed cache data, and it must not train a model.

After Round 1c features are generated:

1. inspect `feature_build_report.json`
2. inspect `feature_schema_check.csv`
3. generate default labels
4. generate min_obs=20 sensitivity labels
5. merge the label audit with six/high/Round 1a/Round 1b/Round 1c
6. check whether `capacity_eol_75 >= 9`

## Risks And Rollback

| Risk | Mitigation | Rollback |
| --- | --- | --- |
| schema drift | run `feature_schema_check.csv` | discard feature output and fix builder |
| chunk boundary errors | test with tiny chunks | rerun after accumulator fix |
| interrupted output | use output-root overwrite protection | delete incomplete feature directory |
| RPT misuse | keep RPT audit-only in reports | invalidate any export using RPT labels |
| batch/protocol confounding | preserve diagnostics and remove risky columns later | remove risky columns in baseline-ready export |

The current builder is an engineering step for reliable feature generation. It
does not authorize model training or stronger baselines.
