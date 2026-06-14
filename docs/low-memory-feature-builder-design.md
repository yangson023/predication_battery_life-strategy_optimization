# Low-Memory Feature Builder Design

This document designs a memory-safe feature builder for Round 1c external
battery data. It is a design-only document: no data are processed here, no model
is trained, and no processed cache is created.

## Purpose

Round 1c extraction has already produced large per-cell CSV files under:

`D:\battery_archive\processed_cache\by_cell_expansion_round1c`

Feature generation is currently paused because the original feature-building
path reads large CSV files into memory with full-table `pandas.read_csv`. That
approach is not reliable on the current laptop.

The proposed low-memory builder should stream files in chunks, accumulate only
the statistics needed for feature rows, and write the same feature table schema
as the existing feature pipeline.

This is especially useful before the external SSD arrives because it reduces
RAM pressure and avoids creating duplicate large processed data on the C drive.

## Why Full `read_csv` Is Not Feasible

Round 1c contains multi-GB per-cell cycle CSV files. Several examples are about
3.8-4.3 GB each. A full `pd.read_csv` call is unsafe for three reasons:

1. CSV parsing expands memory use beyond raw file size.
2. Pandas stores columns with dtype overhead, indexes, temporary parse buffers,
   and intermediate groupby objects.
3. Feature generation may require additional copies during filtering,
   aggregation, sorting, or type conversion.

A 4 GB CSV can therefore require far more than 4 GB of RAM during processing.
On a laptop, this can cause paging, stalled runs, kernel termination, or
partially written outputs.

The failure mode is also scientifically risky: if a run is interrupted after
partial output, later label generation could accidentally consume incomplete
features unless the builder records completion status and validates row counts.

## Chunked CSV Reading Strategy

The low-memory builder should read each per-cell CSV with `pd.read_csv(...,
chunksize=N)`, where `N` is configurable.

Recommended initial settings:

| Parameter | Default | Reason |
| --- | ---: | --- |
| `--chunksize` | `250000` | conservative for laptop memory |
| `--source-mode` | `by_cell` | matches current external pipeline |
| `--input-root` | user provided | supports D-drive processed cache |
| `--output-root` | user provided | writes small feature tables to project |
| `--overwrite` | false by default | avoids silently replacing prior outputs |

Processing should be file-by-file and cell-by-cell:

```text
for each cell directory:
  process cycle_timeseries.csv in chunks
  process rpt_diagnostic.csv in chunks
  finalize accumulated feature rows
write temporary outputs
validate temporary outputs
atomically replace final outputs
```

The builder should never concatenate all chunks into one DataFrame. Each chunk
should update an accumulator keyed by the grouping level used by the existing
schema, such as `cell_id`, `batch_id`, `part_id`, `cycle_index`, and
`protocol_regime_index` when present or derivable.

Temporary files should use a suffix such as `.tmp` or an isolated staging
directory. Final outputs should only be moved into place after all source files
finish and validation passes.

## `cycle_features` Statistics To Accumulate

The builder should reproduce the existing `cycle_features.csv` schema. At
minimum, it should support cumulative statistics commonly used by the current
label and baseline workflow.

### Identity And Grouping Fields

Required identity fields:

- `source_dataset`
- `batch_id`
- `part_id`
- `cell_id`
- `cycle_index`
- `protocol_regime_index`
- measurement source metadata, if present in the old schema

These fields are not model features by themselves, but they are required for
label generation, leave-one-cell-out grouping, and audit reports.

### Capacity And Health Fields

Fields needed for label construction and audit:

- cycle-level discharge capacity estimate
- capacity retention relative to the regime-specific initial capacity
- final or last observed capacity where the old schema includes it
- EOL-related helper fields only if the previous feature table included them

Important rule:

These fields may be needed for label generation and audit, but leakage-prone
health fields must later be removed from baseline model inputs by the
baseline-ready export step.

### Voltage Statistics

For voltage-like columns, accumulate:

- count of valid samples
- first valid value
- last valid value
- minimum
- maximum
- sum
- sum of squares if standard deviation is required
- optional quantile approximation only if the old schema requires quantiles

Typical output columns may include first/last/mean/min/max/std-style voltage
features. Exact names must match the previous `cycle_features.csv` schema.

### Current Statistics

For current-like columns, accumulate:

- first valid value
- last valid value
- mean
- minimum
- maximum
- standard deviation if present in old schema
- absolute-current aggregates if present in old schema

Current features have previously shown possible batch or protocol confounding
risk, so the builder should preserve them for audit but document them clearly.

### Temperature Statistics

For temperature-like columns, accumulate:

- mean
- minimum
- maximum
- standard deviation
- first and last values if present in old schema

Temperature features are useful for sanity checks and possible degradation
signals, but they may also reflect protocol or environment differences.

### Time, Energy, And Throughput Statistics

If source columns allow it, accumulate:

- elapsed time per cycle
- charge or discharge duration
- energy estimate, for example integrated voltage-current-time where the old
  schema expects it
- ampere-hour or watt-hour throughput where available

Integration-like features should be accumulated chunk by chunk using stable
running sums. If integration requires adjacent rows across chunk boundaries, the
builder must retain the last row of the previous chunk for each active group.

### Missingness And Quality Fields

For each feature group, track:

- number of rows read
- number of valid samples used for each major sensor family
- missing fraction for capacity, voltage, current, temperature, and time
- whether the group was finalized with insufficient raw samples

These fields help distinguish true degradation behavior from incomplete files or
parser issues.

## `rpt_features` Statistics To Accumulate

RPT features remain audit-only for the current project. They must not enter
training until RPT protocol-regime handling is solved.

The low-memory builder should still reproduce `rpt_features.csv` because RPT is
useful for data diagnostics.

### Identity Fields

Required fields:

- `source_dataset`
- `batch_id`
- `part_id`
- `cell_id`
- RPT index or diagnostic index
- measurement source metadata, if present in old schema

If `protocol_regime_index` cannot be defensibly assigned for RPT, the builder
should not invent it. The trainable-label audit should continue excluding RPT.

### RPT Diagnostic Fields

Accumulate:

- diagnostic capacity estimate
- diagnostic capacity retention when old schema supports it
- voltage statistics during diagnostic steps
- current statistics during diagnostic steps
- temperature statistics during diagnostic steps
- diagnostic duration or elapsed time if present
- row counts and missingness indicators

The output should be complete enough for audit while preserving the current
policy that RPT labels are excluded from trainable candidates.

## Maintaining Schema Compatibility

The low-memory builder is only acceptable if downstream scripts can consume its
outputs without modification.

Schema compatibility should be enforced by comparing against an existing
feature output, such as Round 1b:

`data/features/external_battery_datasets_expansion_round1b`

Compatibility checks:

1. `cycle_features.csv` has the same required columns as the old output.
2. `rpt_features.csv` has the same required columns as the old output.
3. Column names use the same spelling and casing.
4. Key identifier columns have the same dtype style after CSV round-trip.
5. Numeric columns are written in a stable format.
6. Missing optional columns are reported explicitly instead of silently ignored.
7. Extra diagnostic columns are either disabled by default or written to a
   separate summary file, not mixed into the main schema unless downstream
   scripts expect them.

Recommended support files:

- `feature_build_summary.csv`
- `feature_build_report.json`
- `feature_schema_check.csv`
- `feature_input_manifest.csv`

The report should record:

- input root
- output root
- processed cells
- source files processed
- raw rows read per source file
- chunksize
- wall-clock runtime
- failed files
- skipped files
- output row counts
- schema check result

## Small-Sample Validation

The builder should be validated before touching full Round 1c.

### Validation Level 1: Synthetic Unit Test

Create tiny synthetic CSV files with known values:

- two cells
- two cycles per cell
- one or two protocol regimes
- simple voltage/current/temperature/time columns
- known missing values

Expected checks:

- means are correct
- first and last values are correct
- min and max are correct
- counts and missingness are correct
- chunk boundaries do not change results
- output schema is stable

Run the same test with very small chunksize, for example `--chunksize 2`, to
force boundary conditions.

### Validation Level 2: Tiny Real Slice

Use a small copied or sampled real slice, not the full Round 1c files.

Checks:

- builder finishes without high memory use
- output files are created
- row counts are plausible
- schema matches old Round 1b feature schema
- label builder can read the output

This validation should not be interpreted as a model result.

### Validation Level 3: Round 1b Comparison

If practical, run the low-memory builder on a small subset already handled by
the old builder and compare:

- row counts
- key columns
- major numeric features within tolerance
- label generation behavior

This is the best way to confirm compatibility before Round 1c.

## Processing Round 1c After Validation

Only after validation passes should the builder process Round 1c.

Recommended command shape:

```powershell
python modules/feature_engineering/build_external_battery_features_low_memory.py `
  --source-mode by_cell `
  --input-root "D:\battery_archive\processed_cache\by_cell_expansion_round1c" `
  --output-root "data\features\external_battery_datasets_expansion_round1c" `
  --chunksize 250000
```

After feature generation:

1. inspect `feature_build_report.json`
2. confirm all intended cells were processed
3. confirm no failed files
4. confirm `cycle_features.csv` and `rpt_features.csv` exist
5. confirm row counts are plausible
6. run label generation only after feature validation passes
7. generate min_obs=20 sensitivity labels
8. merge label audit with prior six/high/Round 1a/Round 1b results
9. check whether strict `capacity_eol_75 >= 9` is finally reached

Training remains forbidden until the label gate is reviewed.

## Risks And Rollback Plan

### Risk 1: Schema Drift

The low-memory builder may accidentally produce columns that differ from the old
feature schema.

Mitigation:

- run schema checks before writing final outputs
- keep main output schema locked to the old script
- write new diagnostics to separate report files

Rollback:

- delete only the failed feature output directory
- keep processed cache untouched
- keep prior Round 1a/Round 1b outputs unchanged

### Risk 2: Chunk Boundary Errors

Features based on first/last rows or time integration can be wrong if a cycle
continues across chunks.

Mitigation:

- keep per-group state between chunks
- preserve previous last row when integration needs adjacent samples
- test with deliberately tiny chunks

Rollback:

- mark affected output as invalid
- do not run label generation from invalid features
- fix accumulator logic and rerun validation

### Risk 3: Partial Output After Interruption

Laptop memory pressure or manual interruption may leave incomplete files.

Mitigation:

- write to staging files
- include a completion marker in the report
- move to final output only after validation

Rollback:

- remove the staging directory
- never treat incomplete outputs as valid inputs

### Risk 4: RPT Misuse

Because RPT still lacks reliable protocol-regime assignment, RPT labels could be
mistakenly used in training.

Mitigation:

- keep RPT trainability exclusion in label audit
- state in reports that RPT is audit-only
- ensure baseline-ready exports accept only `cycle_features.csv`

Rollback:

- invalidate any export that includes RPT rows
- regenerate audit with RPT exclusion enforced

### Risk 5: Hidden Batch Or Protocol Confounding

Low-memory processing may correctly compute features that are still unsuitable
as model inputs because they reflect batch or protocol identity.

Mitigation:

- preserve features for audit
- rely on baseline-ready export to remove leakage-prone columns
- continue leave-one-cell-out and batch-effect diagnostics before any stronger
  modeling

Rollback:

- remove risky columns from baseline-ready exports
- keep raw feature tables for traceability

## Decision Gate

This design supports the next engineering step, but it does not authorize model
training.

The next approved action is:

1. implement the low-memory builder on the feature-engineering branch
2. validate it on synthetic data and a tiny real slice
3. only then process Round 1c features

The scientific gate remains:

```text
capacity_eol_75 >= 9 strict candidates
capacity_eol_80 >= 11 strict candidates
```

Until that gate passes and is reviewed, Round 1c remains a data and label audit
task, not a modeling task.
