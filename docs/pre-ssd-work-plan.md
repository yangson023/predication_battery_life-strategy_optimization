# Pre-SSD Work Plan

This plan lists the useful work to do before the external SSD arrives. The goal
is to avoid large processed-data writes while improving reproducibility,
scientific rigor, and the low-memory pipeline needed for the next expansion
rounds.

## Current Storage Constraint

Current large data are already close to the practical limit for the laptop:

- raw archives: `D:\battery_archive\battery_dataset_collection`
- Round 1a cache: `D:\battery_archive\processed_cache\by_cell_expansion_round1a`
- Round 1b cache: `D:\battery_archive\processed_cache\by_cell_expansion_round1b`
- Round 1c cache: `D:\battery_archive\processed_cache\by_cell_expansion_round1c`
- C-drive six/high processed caches are still large and should not be duplicated.

Do not run more full extraction rounds on the laptop before external storage is
available.

## Highest-Value Tasks Before SSD Arrival

### P0. Low-Memory Feature Builder

Build and test a chunked feature builder that can process large per-cell CSV
files without loading whole 4GB files into memory.

Acceptance criteria:

- reads CSV with `chunksize`
- outputs the same schema as `build_external_battery_features.py`
- reproduces existing Round 1b feature rows on a small sampled subset
- records chunk size and memory-safe mode in `feature_build_summary.csv`
- includes a unit test using synthetic small CSV files

Reason:

Round 1c processed data are present, but the current feature script is too
memory-heavy for a laptop.

### P0. Round 1c Pause Note

Document that Round 1c extraction is complete but feature generation is paused
until the low-memory builder is validated.

Acceptance criteria:

- records Round 1c cells
- records manifest summary: selected/written/failed
- records why original full-read feature builder is unsafe
- states that no model training occurred

### P1. Label Policy Memo

Write an internal label policy memo covering:

- why `capacity_eol_75` remains the strict gate
- why `capacity_eol_80` can be used as an easier exploratory target
- why RPT remains excluded from training
- how boundary artifacts are excluded
- when an EOL_77/EOL_78 sensitivity analysis would be allowed

This should not change label definitions yet. It only prepares the scientific
argument.

### P1. External Storage Migration Plan

Prepare the directory plan and path registry for the external SSD.

Target structure:

```text
battery_research_storage/
  raw_archives/
  processed_cache/
  features/
  label_audit/
  model_outputs/
  figures/
  backups/
```

Acceptance criteria:

- records what stays in Git
- records what stays local-only
- records which paths scripts should use after migration
- records checksum or manifest checks needed after moving data

### P1. Trae Review Packet

Prepare a concise review packet for Trae:

- Round 1a audit
- Round 1b audit
- Round 1c extraction status
- current EOL_75/EOL_80 bottleneck
- low-memory feature-builder plan

### P2. Dashboard / Development Log Cleanup

The dashboard and visualization files are currently separate work. They should
not be mixed with data pipeline commits. Before touching them:

- decide whether they belong on `codex/dashboard`
- keep commits separate from RUL data work
- avoid adding large images or generated artifacts to Git

## What Not To Do Before SSD Arrival

- do not run another full extraction round
- do not duplicate six/high processed data
- do not train a model
- do not run stronger baselines
- do not use RPT as a training source
- do not change the EOL threshold policy without a memo and review

## Recommended Immediate Sequence

1. Commit or push the current Round 1b audit commit if it is only local.
2. Implement the low-memory feature builder on `codex/feature-engineering`.
3. Validate it on synthetic data and a tiny sampled slice.
4. Use it for Round 1c feature generation only after the validation passes.
5. Generate Round 1c labels and audit.
6. Stop again before model training and ask for Trae review.
