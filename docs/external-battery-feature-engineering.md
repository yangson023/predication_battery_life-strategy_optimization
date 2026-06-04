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
| `cycle_features_sample.csv` | `cell_id`, `cycle_index`, source member | voltage/current/capacity/energy summaries, duration, charge/discharge state fractions |
| `rpt_features_sample.csv` | `cell_id`, `diagnostic_part`, source member | diagnostic capacity range, voltage drop, pulse SOC summary, pulse type count |
| `thermal_runaway_features_sample.csv` | source member, SOC, capacity, replicate | peak temperature, voltage minimum, max load/force, max displacement, safety event hint |

The non-sample `cycle_features.csv` and `rpt_features.csv` use the same feature
definitions, but they are built from `data/processed/external_battery_datasets/by_cell`.

The thermal runaway table is kept separate from SOH/RUL labels. It should feed
future safety-risk and strategy-constraint models, not the first RUL baseline.

## External Labels

`modules/feature_engineering/build_external_health_labels.py` converts cycle and
RPT feature tables into SOH/RUL-style labels. The default label keys are:

| Label key family | Source table | Default capacity column |
| --- | --- | --- |
| `capacity_eol_70/75/80` | `cycle_features_sample.csv` | `capacity_delta_ah` |
| `rpt_capacity_eol_70/75/80` | `rpt_features_sample.csv` | `capacity_delta_ah` |

Rows are marked with `label_quality`. Small samples usually remain censored or
`sample_only_less_than_3_observations`; full extraction is needed before using
these labels for final model training.

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
full chunked features per cell. Then define external SOH/RUL labels from cycle
capacity and RPT diagnostic capacity.
