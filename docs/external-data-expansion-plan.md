# External Battery Data Expansion Plan

This document records the next data expansion step before any stronger RUL
baseline is attempted. The current exploratory LOCO binary baseline has served
its purpose: it exposed data scarcity, cell-to-cell variability, and possible
batch confounding. It must not be interpreted as formal model performance.

## Current Gate Status

Current branch context: `codex/rul-prediction`.

Inputs reviewed:

- `outputs/label_audit/external_trainable_labels/trainable_label_summary.csv`
- `data/features/external_battery_datasets`
- `data/features/external_battery_datasets_candidates_high_obs`
- `models/rul_prediction/external_loco_binary_baseline/combined_main_input`
- `models/rul_prediction/external_loco_binary_baseline/combined_main_v2_input`
- `models/rul_prediction/external_loco_binary_baseline/combined_main/diagnostics`
- `models/rul_prediction/external_loco_binary_baseline/combined_main_v2/diagnostics`

No stronger baseline should be run at this stage.

## Current Usable Observed Labels

The current modeling gate accepts only:

- `source_table = cycle_features.csv`
- `protocol_regime_index = 2`
- `eol_observed = True`
- `eol_boundary_quality = away_from_protocol_boundary`
- `label_key in {capacity_eol_75, capacity_eol_80}`
- no RPT labels

Combined main contains 10 observed labels from 6 cells.

| Label key | Observed labels | Cells with observed labels | LOCO training positives per held-out fold |
| --- | ---: | ---: | ---: |
| `capacity_eol_75` | 4 | 4 | 3 |
| `capacity_eol_80` | 6 | 6 | 5 |

Observed label distribution by batch and part:

| Batch / part | `capacity_eol_75` | `capacity_eol_80` | Total |
| --- | ---: | ---: | ---: |
| `batch_1 / part_1` | 1 | 1 | 2 |
| `batch_2 / part_1` | 2 | 3 | 5 |
| `batch_2 / part_2` | 0 | 1 | 1 |
| `batch_2 / part_3` | 1 | 1 | 2 |

Observed label distribution by source run:

| Source pipeline run | `capacity_eol_75` | `capacity_eol_80` | Total |
| --- | ---: | ---: | ---: |
| `six_minobs20` | 2 | 3 | 5 |
| `high_minobs20` | 2 | 3 | 5 |

Cells currently contributing observed labels:

| Cell | Batch / part | Observed labels |
| --- | --- | --- |
| `G1C2` | `batch_2 / part_1` | `capacity_eol_75`, `capacity_eol_80` |
| `G1C3` | `batch_2 / part_1` | `capacity_eol_75`, `capacity_eol_80` |
| `G2C3` | `batch_2 / part_1` | `capacity_eol_80` |
| `G3C3` | `batch_1 / part_1` | `capacity_eol_75`, `capacity_eol_80` |
| `G11C3` | `batch_2 / part_2` | `capacity_eol_80` |
| `G16C3` | `batch_2 / part_3` | `capacity_eol_75`, `capacity_eol_80` |

## Current Model Diagnostics

The combined main full-feature exploratory baseline is the main reference.
The combined v2 run, which excludes `energy_wh_last`, is supplemental only.

| Diagnostic item | Combined main | Combined main v2 | Interpretation |
| --- | ---: | ---: | --- |
| Feature columns | 19 | 18 | v2 excludes `energy_wh_last` |
| Observed labels | 10 | 10 | Same label gate |
| Feature rows | 304 | 304 | Same aligned rows |
| Early false positive events | 30 | 31 | v2 does not improve the main threshold behavior |
| Missed EOL events | 0 | 0 | Both detect EOL at the exploratory threshold |
| Exact EOL hit folds | 1 | 0 | v2 loses the single exact timing fold |
| Batch risk features | 3 | 2 | v2 reduces one risk feature but is not better overall |

`energy_wh_last` should remain marked as `possible_confound_feature`, not
`must_remove`. It appears to carry both degradation signal and batch/cell offset.
The correct scientific conclusion is that current data are too sparse to decide
feature exclusion robustly.

## Why Stop Tuning Models Now

Model tuning must stop because the bottleneck is label coverage, not model
capacity.

Key blockers:

- `capacity_eol_75` has only 4 observed cells, giving only 3 training positives
  in each LOCO fold.
- `capacity_eol_80` has only 6 observed cells, giving only 5 training positives
  in each LOCO fold.
- `batch_2 / part_1` dominates the current label set.
- `batch_2 / part_2` contributes only one observed label.
- There are no observed labels from several available batch/part regions.
- Feature exclusion diagnostics show mixed fold-level effects, not a stable
  improvement.

With this amount of data, stronger models such as Random Forest, XGBoost, SVM,
or MLP would mostly test the model's ability to memorize cell and batch offsets.
They should remain forbidden until the data gate improves.

## Expansion Targets

The next goal is not to maximize total rows. The goal is to increase reliable
observed EOL cells under the same label gate.

Target before returning to baseline training:

| Label key | Current observed cells | Minimum target observed cells | Desired observed cells | Net new cells needed |
| --- | ---: | ---: | ---: | ---: |
| `capacity_eol_75` | 4 | 9 | 11 to 13 | +5 minimum, +7 to +9 desired |
| `capacity_eol_80` | 6 | 11 | 13 to 15 | +5 minimum, +7 to +9 desired |

The strict milestone is each LOCO fold having at least 8 to 10 training positives
per label key. This requires at least 9 to 11 observed cells for that label key.

## Candidate Cell Pool

The existing inventory shows only one not-yet-used cell with at least 45 cycle
files:

| Priority | Cell | Batch / part | Cycle files | RPT files | Reason |
| --- | --- | --- | ---: | ---: | --- |
| P0 | `G3C2` | `batch_1 / part_1` | 47 | 48 | Highest remaining observation count |

The broader not-yet-used pool with at least 30 cycle files includes:

| Priority | Cell | Batch / part | Cycle files | RPT files | Reason |
| --- | --- | --- | ---: | ---: | --- |
| P0 | `G3C2` | `batch_1 / part_1` | 47 | 48 | Closest to current high-observation cells |
| P1 | `G11C2` | `batch_2 / part_2` | 42 | 43 | Completes the G11 group and improves part 2 coverage |
| P1 | `G18C1` | `batch_2 / part_3` | 42 | 44 | Improves part 3 coverage |
| P1 | `G3C1` | `batch_1 / part_1` | 42 | 43 | Completes the G3 group |
| P1 | `G7C3` | `batch_1 / part_2` | 38 | 39 | Adds under-covered part 2 from batch 1 |
| P1 | `G8C2` | `batch_1 / part_2` | 38 | 39 | Adds under-covered part 2 from batch 1 |
| P1 | `G18C2` | `batch_2 / part_3` | 37 | 39 | Adds another part 3 cell |
| P1 | `G6C2` | `batch_1 / part_2` | 37 | 38 | Adds batch 1 part 2 diversity |
| P1 | `G8C3` | `batch_1 / part_2` | 37 | 38 | Adds batch 1 part 2 diversity |
| P1 | `G8C1` | `batch_1 / part_2` | 36 | 37 | Adds batch 1 part 2 diversity |
| P2 | `G16C2` | `batch_2 / part_3` | 35 | 36 | Completes G16 group, lower count |
| P2 | `G4C2` | `batch_2 / part_2` | 35 | 36 | Adds batch 2 part 2 coverage |
| P2 | `G6C3` | `batch_1 / part_2` | 35 | 36 | Adds batch 1 part 2 coverage |
| P2 | `G17C3` | `batch_2 / part_3` | 34 | 35 | Adds batch 2 part 3 coverage |
| P2 | `G5C2` | `batch_1 / part_1` | 34 | 35 | Adds batch 1 part 1 coverage |
| P2 | `G6C1` | `batch_1 / part_2` | 34 | 35 | Adds batch 1 part 2 coverage |
| P2 | `G7C2` | `batch_1 / part_2` | 33 | 34 | Adds batch 1 part 2 coverage |
| P2 | `G16C1` | `batch_2 / part_3` | 32 | 33 | Adds batch 2 part 3 coverage |
| P2 | `G5C3` | `batch_1 / part_1` | 32 | 33 | Adds batch 1 part 1 coverage |
| P2 | `G15C3` | `batch_1 / part_3` | 31 | 32 | Adds currently missing batch 1 part 3 coverage |
| P2 | `G17C1` | `batch_2 / part_3` | 31 | 32 | Adds batch 2 part 3 coverage |
| P2 | `G4C1` | `batch_2 / part_2` | 31 | 32 | Adds batch 2 part 2 coverage |
| P2 | `G13C1` | `batch_1 / part_3` | 30 | 31 | Adds currently missing batch 1 part 3 coverage |
| P2 | `G7C1` | `batch_1 / part_2` | 30 | 31 | Adds batch 1 part 2 coverage |

## Extraction Rules

Use a new processed output directory. Do not overwrite current six-cell or
high-observation outputs.

Recommended next processed output:

`data/processed/external_battery_datasets/by_cell_expansion_round1`

Recommended next feature output:

`data/features/external_battery_datasets_expansion_round1`

Recommended candidate cells for round 1:

`G3C2 G11C2 G18C1 G3C1 G7C3 G8C2 G18C2 G6C2 G8C3 G8C1 G16C2 G4C2 G6C3 G17C3 G5C2 G6C1`

Round 1 should include:

- all available cycle files for each selected cell
- all available RPT files copied for audit only
- no RPT labels in trainable output
- no random row split
- no model training

## Label Gate After Expansion

After extraction and feature generation, labels must pass the same scientific
gate before entering any exploratory baseline:

1. `source_table = cycle_features.csv`
2. `protocol_regime_index = 2`
3. `label_key in {capacity_eol_75, capacity_eol_80}`
4. `eol_observed = True`
5. `eol_boundary_quality = away_from_protocol_boundary`
6. `trainable_label = True`
7. no RPT labels
8. no boundary-crossing labels
9. no censored labels for the first baseline rerun

## Success Criteria

The expansion round is successful only if all criteria below are met:

- at least 5 new observed `capacity_eol_75` cells are found
- at least 5 new observed `capacity_eol_80` cells are found
- every accepted label is away from protocol boundary
- accepted labels are not dominated by a single batch/part
- each LOCO fold would have at least 8 training positives for the target label
- feature and target alignment checks pass
- no RPT rows enter trainable or baseline-ready exports

## Failure Criteria

The expansion round should be treated as insufficient if any condition below
occurs:

- most new cells are censored before `capacity_eol_75`
- observed EOL events are mostly boundary artifacts
- accepted cells come from only one batch/part
- `capacity_eol_75` remains below 9 observed cells
- `capacity_eol_80` remains below 11 observed cells
- alignment checks fail
- feature leakage columns reappear in baseline-ready exports

## Trae And Codex Division

Trae should act as the external scientific review agent.

Trae responsibilities:

- review candidate cell selection before extraction
- check whether the selected cells improve batch/part diversity
- challenge any label that may be a protocol boundary artifact
- review whether `capacity_eol_75` and `capacity_eol_80` remain appropriate
- reject any attempt to describe exploratory diagnostics as formal performance

Codex should act as the local execution and verification agent.

Codex responsibilities:

- inspect manifests and inventories
- run extraction into new directories only
- regenerate features and labels
- run label audit and baseline-ready export gates
- write audit tables and reports
- update this plan with actual expansion results
- avoid model training until the data gate passes

## Next Checklist

1. Commit or stash unrelated dashboard and roadmap changes before data-pipeline
   work if they are not part of the current task.
2. Switch to `codex/data-pipeline`.
3. Extract round 1 candidate cells into
   `data/processed/external_battery_datasets/by_cell_expansion_round1`.
4. Verify manifest counts, failed members, requested cells, and per-cell files.
5. Switch to `codex/feature-engineering`.
6. Generate features into
   `data/features/external_battery_datasets_expansion_round1`.
7. Generate default labels and `min_obs=20` sensitivity labels into separate
   directories.
8. Run trainable label audit.
9. Export baseline-ready candidates only if the label gate passes.
10. Ask Trae to review the label audit before any new baseline run.

## Current Decision

Training is not allowed yet.

The next approved work is data expansion planning, candidate extraction,
feature generation, label audit, and baseline-ready export validation. Stronger
baselines remain forbidden until the observed-label gate improves.
