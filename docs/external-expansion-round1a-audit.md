# External Expansion Round 1a Audit

This document is the commit-tracked summary of the Round 1a external battery
data expansion audit. The detailed local report is stored under
`outputs/label_audit/external_expansion_round1a/round1a_audit_report.md`, but
`outputs/` is intentionally ignored by Git.

## Data Locations

Raw external archives:

`D:\battery_archive\battery_dataset_collection`

Migrated processed cache:

`D:\battery_archive\processed_cache\by_cell_expansion_round1a`

Project-local feature outputs:

- `data/features/external_battery_datasets_expansion_round1a`
- `data/features/external_battery_datasets_expansion_round1a_minobs20`

## Extraction Summary

Round 1a was split into two non-overlapping passes to avoid re-extracting cells:

| Pass | Cells | Selected members | Written members | Failed members |
| --- | --- | ---: | ---: | ---: |
| core4 | `G3C2 G11C2 G18C1 G3C1` | 351 | 351 | 0 |
| append3 | `G7C3 G8C2 G15C3` | 217 | 217 | 0 |

All seven cells have both `cycle_timeseries.csv` and `rpt_diagnostic.csv` in the
migrated processed cache.

## Feature And Label Summary

Feature generation:

| Feature table | Rows in | Rows out |
| --- | ---: | ---: |
| `cycle_features.csv` | 121,843,584 | 280 |
| `rpt_features.csv` | 12,758,186 | 288 |

Label generation:

| Output | Label rows | Summary rows |
| --- | ---: | ---: |
| default min_obs=50 | 1,704 | 63 |
| sensitivity min_obs=20 | 1,704 | 63 |

Default min_obs=50 does not produce trainable cycle labels because all protocol
windows remain shorter than 50 observations.

## Strict Candidate Gate

Strict candidate labels must satisfy all of the following:

- `source_table = cycle_features.csv`
- `protocol_regime_index = 2`
- `label_key in {capacity_eol_75, capacity_eol_80}`
- `eol_observed = True`
- `eol_boundary_quality = away_from_protocol_boundary`
- no RPT labels

Under min_obs=20, Round 1a adds the following strict exploratory candidates:

| Cell | Batch / part | Label key | Regime observations | Distance to regime end |
| --- | --- | --- | ---: | ---: |
| `G18C1` | `batch_2 / part_3` | `capacity_eol_75` | 34 | 6 |
| `G18C1` | `batch_2 / part_3` | `capacity_eol_80` | 34 | 9 |
| `G3C2` | `batch_1 / part_1` | `capacity_eol_80` | 36 | 8 |
| `G7C3` | `batch_1 / part_2` | `capacity_eol_80` | 30 | 9 |
| `G8C2` | `batch_1 / part_2` | `capacity_eol_80` | 29 | 6 |

## Combined Label Gate Impact

After auditing the existing six-cell and high-observation min_obs=20 outputs
together with Round 1a:

| Label key | Strict candidate count |
| --- | ---: |
| `capacity_eol_75` | 5 |
| `capacity_eol_80` | 10 |

The current target remains:

- `capacity_eol_75 >= 9` observed cells
- `capacity_eol_80 >= 11` observed cells

Round 1a meaningfully improves `capacity_eol_80` coverage, but it does not solve
the `capacity_eol_75` bottleneck.

## Exclusions

RPT remains excluded from training. In the combined audit with Round 1a, RPT
accounts for 102 excluded rows.

Boundary-related exclusions remain substantial: 32 cycle summary rows are
excluded as unreliable boundary crossings.

## Decision

Training is still not allowed.

Stronger baselines remain forbidden. The next scientific action should target
additional cells likely to add away-from-boundary `capacity_eol_75` events,
preferably using D-drive processed cache paths rather than writing more large
processed files to C drive.
