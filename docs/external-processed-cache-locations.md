# External Processed Cache Locations

This document records where large external battery datasets are stored after
the SSD migration on 2026-06-16.

The migrated data are lithium-ion method-development data. They are retained for
pipeline validation, low-memory feature-builder testing, label-audit rehearsal,
and possible transfer-learning experiments with explicit caveats. They are not
standalone lithium metal battery evidence.

## Current External SSD Root

```text
E:\battery_research_storage\li_ion_method_data
```

External SSD volume observed during migration:

| Drive | Volume label | Format | Capacity | Free after migration |
| --- | --- | --- | ---: | ---: |
| `E:\` | `AOC` | `exFAT` | 931.5 GB | 745.5 GB |

## Migrated Processed Cache

| Dataset cache | Current path on external SSD | Size | Files | Source after cleanup |
| --- | --- | ---: | ---: | --- |
| Workspace six-cell by-cell cache | `E:\battery_research_storage\li_ion_method_data\processed_cache\c_workspace_by_cell` | 29.035 GB | 15 | Deleted from C drive |
| Workspace high-observation by-cell cache | `E:\battery_research_storage\li_ion_method_data\processed_cache\c_workspace_by_cell_candidates_high_obs` | 29.056 GB | 11 | Deleted from C drive |
| Expansion Round 1a cache | `E:\battery_research_storage\li_ion_method_data\processed_cache\by_cell_expansion_round1a` | 37.895 GB | 20 | Deleted from D drive |
| Expansion Round 1b cache | `E:\battery_research_storage\li_ion_method_data\processed_cache\by_cell_expansion_round1b` | 29.363 GB | 15 | Deleted from D drive |
| Expansion Round 1c cache | `E:\battery_research_storage\li_ion_method_data\processed_cache\by_cell_expansion_round1c` | 35.710 GB | 19 | Deleted from D drive |

## Migrated Raw Archives

| Raw archive collection | Current external SSD path | Size | Files | Local copy status |
| --- | --- | ---: | ---: | --- |
| External battery archive ZIP collection | `E:\battery_research_storage\li_ion_method_data\raw_archives\battery_dataset_collection` | 24.917 GB | 10 | Also retained on D drive |

The D-drive copy is still present at:

```text
D:\battery_archive\battery_dataset_collection
```

Keep this D-drive raw archive copy for now. Raw archives are harder to recreate
than processed caches.

## Deleted Source Paths

The following processed-cache source directories were verified migrated and then
deleted:

```text
C:\Users\Lenovo\Documents\predication_battery_life & strategy_optimization\data\processed\external_battery_datasets\by_cell
C:\Users\Lenovo\Documents\predication_battery_life & strategy_optimization\data\processed\external_battery_datasets\by_cell_candidates_high_obs
D:\battery_archive\processed_cache\by_cell_expansion_round1a
D:\battery_archive\processed_cache\by_cell_expansion_round1b
D:\battery_archive\processed_cache\by_cell_expansion_round1c
```

## Migration Logs

Robocopy logs are stored at:

```text
E:\battery_research_storage\li_ion_method_data\migration_logs
```

Expected log files:

```text
c_workspace_by_cell.log
c_workspace_by_cell_candidates_high_obs.log
by_cell_expansion_round1a.log
by_cell_expansion_round1b.log
by_cell_expansion_round1c.log
battery_dataset_collection.log
```

Robocopy summaries showed `失败 = 0` for every migrated directory.

## Verification Summary

The final source-vs-destination checks showed matching file counts and byte
sizes:

| Cache | Source files | Destination files | Source size | Destination size |
| --- | ---: | ---: | ---: | ---: |
| C workspace by-cell | 15 | 15 | 29.035 GB | 29.035 GB |
| C high-observation by-cell | 11 | 11 | 29.056 GB | 29.056 GB |
| Round 1a | 20 | 20 | 37.895 GB | 37.895 GB |
| Round 1b | 15 | 15 | 29.363 GB | 29.363 GB |
| Round 1c | 19 | 19 | 35.710 GB | 35.710 GB |
| Raw archive ZIPs | 10 | 10 | 24.917 GB | 24.917 GB |

## Working Rules

- Do not regenerate deleted processed caches on C or D unless there is a clear
  reason.
- Use the E-drive paths above when a method-development processed cache is
  needed.
- Treat these datasets as `li_ion_method_data`, not LMB evidence.
- Keep raw ZIP archives in at least two locations until true LMB data storage is
  organized.
- Prefer manifests, summaries, and feature reports over rescanning large cache
  directories.

## Next Path Update

When true lithium metal battery data are obtained, store them under a separate
root such as:

```text
E:\battery_research_storage\true_lmb
```

Do not mix true LMB data with the current Li-ion method-development archive.
