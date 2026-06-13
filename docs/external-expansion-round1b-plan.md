# External Expansion Round 1b Plan

Round 1b should continue data expansion without training a model. The Round 1a
audit improved `capacity_eol_80` coverage but left `capacity_eol_75` below the
minimum gate.

## Current Gate After Round 1a

| Label key | Strict candidate cells | Minimum target | Status |
| --- | ---: | ---: | --- |
| `capacity_eol_75` | 5 | 9 | insufficient |
| `capacity_eol_80` | 10 | 11 | near target |

Training remains forbidden until both targets pass.

## Storage Rule

Do not write new large processed outputs to C drive.

Round 1b processed output should be stored on D drive:

`D:\battery_archive\processed_cache\by_cell_expansion_round1b`

Project-local outputs may remain small feature/label tables:

- `data/features/external_battery_datasets_expansion_round1b`
- `data/features/external_battery_datasets_expansion_round1b_minobs20`

## Candidate Pool

Remaining not-yet-used cells with at least 30 cycle files:

| Priority | Cell | Batch / part | Cycle files | RPT files | Reason |
| --- | --- | --- | ---: | ---: | --- |
| P0 | `G18C2` | `batch_2 / part_3` | 37 | 39 | Same group as productive `G18C1`; may add EOL_75 |
| P0 | `G16C2` | `batch_2 / part_3` | 35 | 36 | Same group as productive `G16C3`; may add EOL_75 |
| P0 | `G6C2` | `batch_1 / part_2` | 37 | 38 | Adds batch_1/part_2 diversity |
| P0 | `G8C3` | `batch_1 / part_2` | 37 | 38 | Same group as productive `G8C2` |
| P0 | `G8C1` | `batch_1 / part_2` | 36 | 37 | Same group as productive `G8C2` |
| P1 | `G4C2` | `batch_2 / part_2` | 35 | 36 | Improves batch_2/part_2 coverage |
| P1 | `G6C3` | `batch_1 / part_2` | 35 | 36 | Adds batch_1/part_2 coverage |
| P1 | `G17C3` | `batch_2 / part_3` | 34 | 35 | Adds batch_2/part_3 coverage |
| P1 | `G5C2` | `batch_1 / part_1` | 34 | 35 | Adds batch_1/part_1 coverage |
| P1 | `G6C1` | `batch_1 / part_2` | 34 | 35 | Adds batch_1/part_2 coverage |
| P2 | `G7C2` | `batch_1 / part_2` | 33 | 34 | Same group as productive `G7C3` |
| P2 | `G16C1` | `batch_2 / part_3` | 32 | 33 | Same group as productive `G16C3` |
| P2 | `G5C3` | `batch_1 / part_1` | 32 | 33 | Adds batch_1/part_1 coverage |
| P2 | `G17C1` | `batch_2 / part_3` | 31 | 32 | Adds batch_2/part_3 coverage |
| P2 | `G4C1` | `batch_2 / part_2` | 31 | 32 | Adds batch_2/part_2 coverage |
| P2 | `G13C1` | `batch_1 / part_3` | 30 | 31 | Adds scarce batch_1/part_3 coverage |
| P2 | `G7C1` | `batch_1 / part_2` | 30 | 31 | Same group as productive `G7C3` |

## Recommended First Batch

Start with a targeted six-cell Round 1b subset:

`G18C2 G16C2 G6C2 G8C3 G8C1 G4C2`

Rationale:

- favors cells related to productive Round 1a or previously productive groups
- includes batch_1/part_2, batch_2/part_2, and batch_2/part_3
- keeps the first D-drive expansion smaller than extracting all remaining cells

## Gate After Extraction

Use the same strict gate:

- `source_table = cycle_features.csv`
- `protocol_regime_index = 2`
- `label_key in {capacity_eol_75, capacity_eol_80}`
- `eol_observed = True`
- `eol_boundary_quality = away_from_protocol_boundary`
- no RPT labels

Round 1b is successful only if it adds at least four new
`capacity_eol_75` strict candidates, raising the combined count from 5 to 9.

If it adds fewer than two new `capacity_eol_75` candidates, stop and ask Trae to
review whether the EOL_75 threshold is too strict for the current dataset slice.

## Forbidden Actions

- no RUL model training
- no stronger baseline
- no random row split
- no RPT training
- no claim of formal performance
