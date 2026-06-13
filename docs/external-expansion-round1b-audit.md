# External Expansion Round 1b Audit

This document is the commit-tracked summary of the Round 1b external battery
data expansion audit. It is a data and label gate report only. No RUL model was
trained.

## Data Locations

Raw external archives:

`D:\battery_archive\battery_dataset_collection`

Round 1b processed cache:

`D:\battery_archive\processed_cache\by_cell_expansion_round1b`

Project-local feature outputs:

- `data/features/external_battery_datasets_expansion_round1b`
- `data/features/external_battery_datasets_expansion_round1b_minobs20`

Combined local label audit:

`outputs/label_audit/external_trainable_labels_with_round1b`

## Extraction Summary

Round 1b extracted the targeted six-cell subset:

`G18C2 G16C2 G6C2 G8C3 G8C1 G4C2`

Manifest summary:

| Selected members | Written members | Failed members |
| ---: | ---: | ---: |
| 441 | 441 | 0 |

All six cells have both `cycle_timeseries.csv` and `rpt_diagnostic.csv`.

## Feature And Label Summary

Feature generation:

| Feature table | Rows in | Rows out |
| --- | ---: | ---: |
| `cycle_features.csv` | 94,669,710 | 217 |
| `rpt_features.csv` | 9,678,976 | 224 |

Label generation:

| Output | Label rows | Summary rows |
| --- | ---: | ---: |
| default min_obs=50 | 1,323 | 54 |
| sensitivity min_obs=20 | 1,323 | 54 |

Default min_obs=50 does not produce trainable cycle labels because all protocol
windows remain shorter than 50 observations.

## Round 1b Strict Candidates

Strict candidate labels must satisfy all of the following:

- `source_table = cycle_features.csv`
- `protocol_regime_index = 2`
- `label_key in {capacity_eol_75, capacity_eol_80}`
- `eol_observed = True`
- `eol_boundary_quality = away_from_protocol_boundary`
- no RPT labels

Under min_obs=20, Round 1b adds:

| Cell | Batch / part | Label key | Regime observations | Distance to regime end |
| --- | --- | --- | ---: | ---: |
| `G4C2` | `batch_2 / part_2` | `capacity_eol_75` | 25 | 6 |
| `G4C2` | `batch_2 / part_2` | `capacity_eol_80` | 25 | 9 |
| `G8C3` | `batch_1 / part_2` | `capacity_eol_80` | 29 | 7 |

## Combined Gate After Round 1b

Combined audit inputs:

- `six_minobs20`
- `high_minobs20`
- `round1a_minobs20`
- `round1b_minobs20`

Combined strict candidate counts:

| Label key | Strict candidate count | Target | Status |
| --- | ---: | ---: | --- |
| `capacity_eol_75` | 6 | 9 | insufficient |
| `capacity_eol_80` | 12 | 11 | passed |

Round 1b therefore improves `capacity_eol_80` beyond target, but it does not
solve the `capacity_eol_75` bottleneck.

## Batch And Part Coverage

Strict candidates after Round 1b:

| Batch / part | `capacity_eol_75` | `capacity_eol_80` |
| --- | ---: | ---: |
| `batch_1 / part_1` | 1 | 2 |
| `batch_1 / part_2` | 0 | 3 |
| `batch_2 / part_1` | 2 | 3 |
| `batch_2 / part_2` | 1 | 2 |
| `batch_2 / part_3` | 2 | 2 |

`capacity_eol_75` remains concentrated in batch 2, with no accepted
`batch_1 / part_2` candidate.

## Exclusions

Combined audit exclusions:

| Exclusion type | Count |
| --- | ---: |
| cycle unreliable boundary crossing | 47 |
| cycle limited window below 20 observations | 69 |
| RPT unknown or unmapped | 69 |

RPT remains excluded from training because RPT protocol regime assignment has not
been solved.

## Decision

Training is still not allowed.

The reason is narrow and explicit: `capacity_eol_75` has only 6 strict
candidates, below the minimum target of 9. `capacity_eol_80` has passed the
target, but this alone is not sufficient to re-enter modeling.

Next action should focus on either:

1. another targeted data expansion for likely `capacity_eol_75` events, or
2. Trae review of whether the `capacity_eol_75` gate is too strict for this
   dataset slice.

Do not run Random Forest, XGBoost, SVM, MLP, RUL regression, or random row split.
