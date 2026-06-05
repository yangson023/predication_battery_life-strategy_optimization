# External Battery Data Organization

This project now uses a manifest-first workflow for large external battery
datasets. The current ZIP archives expand to more than 100 GB, so the first
preprocessing step inventories them and creates stable category directories
without full extraction.

## Categories

| Category | Source archives | Intended use |
| --- | --- | --- |
| `cycle_life/cycling` | `Batch 1 Part *.zip`, `Batch 2 Part *.zip` | Multi-cell cycle-life modeling, SOH/RUL feature extraction, cross-cell validation |
| `diagnostics/rpt` | `rpt_data.zip` | Reference performance tests, capacity/resistance diagnostics, calibration labels |
| `safety_abuse/thermal_runaway` | `Mechanically Induced Thermal Runaway for Li-ion Batteries.zip` | Thermal runaway and abuse-test safety features, not direct RUL training labels |

## Generated Layout

Running the organizer creates:

```text
data/raw/external_battery_datasets/
  cycle_life/cycling/<archive_slug>/source_manifest.json
  diagnostics/rpt/<archive_slug>/source_manifest.json
  safety_abuse/thermal_runaway/<archive_slug>/source_manifest.json

data/processed/external_battery_datasets/
  archive_manifest.csv
  archive_manifest.json
  file_inventory.csv
  file_inventory.json
  category_summary.csv
  category_summary.json
  measurement_summary.csv
  measurement_summary.json
  schema_hints.csv
  schema_hints.json
  extracted/
    cycle_timeseries_sample.csv
    rpt_diagnostic_sample.csv
    abuse_test_timeseries_sample.csv
    extraction_summary.csv
    extraction_summary.json
  by_cell/
    <cell_id>/cycle_timeseries.csv
    <cell_id>/rpt_diagnostic.csv
    cell_extraction_summary.csv
    cell_extraction_manifest.json

configs/datasets/external_battery_archives.csv
configs/datasets/external_battery_schema_map.json
```

The raw ZIP files are referenced by default. Use `--copy-archives` only if you
want a second local copy inside the project; the current archive set needs about
27 GB compressed and far more if fully extracted.

## Command

```powershell
cd "C:\Users\Lenovo\Documents\predication_battery_life & strategy_optimization"
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\data_pipeline\organize_external_battery_archives.py
```

Optional raw ZIP copy:

```powershell
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\data_pipeline\organize_external_battery_archives.py --copy-archives
```

After inventory generation, create normalized sample tables without full
extraction:

```powershell
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\data_pipeline\extract_external_battery_tables.py
```

The default extraction reads two files per measurement type and 500 rows per
file. Increase the limits gradually:

```powershell
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\data_pipeline\extract_external_battery_tables.py --max-members-per-type 10 --rows-per-member 2000
```

Use `--max-members-per-type 0` only when ready for a much larger run. The
script still reads from ZIP members directly, but output CSV files can grow
quickly.

For model-scale feature engineering, extract ZIP members into per-cell chunks:

```powershell
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\data_pipeline\extract_external_battery_by_cell.py
```

The default run is intentionally small: two cells, two files per measurement
type, and 1000 rows per file. Default cell selection is anchored on
`cycle_timeseries`, so independent RPT-only cells are not selected unless you
ask for them. You can target explicit cells:

```powershell
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\data_pipeline\extract_external_battery_by_cell.py --cell-ids G3C1 G3C2 --max-members-per-cell-type 10 --rows-per-member 2000
```

Small trainable set used for the first external cycle-life experiments:

```powershell
& "C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" modules\data_pipeline\extract_external_battery_by_cell.py --cell-ids G1C1 G1C2 G1C3 --max-members-per-cell-type 10 --rows-per-member 0
```

This reads 10 cycle files and 10 RPT files for each listed cell. The current
run wrote 60 members with no failures and produced per-cell CSV chunks under
`data/processed/external_battery_datasets/by_cell`.

Use `--max-cells 0 --max-members-per-cell-type 0` only after checking available
disk space. Add `--rows-per-member 0` only when you intend to read every row
from selected ZIP members. The full cycle-life archives contain tens of GB of
CSV content.

## Why This Form Is Easier To Use

The generated `file_inventory.csv` gives every archive member a common schema:

- dataset family and category
- chemistry
- archive and member path
- cell ID where available
- batch and part ID
- cycle index for cycling data
- diagnostic part for RPT data
- nominal capacity, replicate, and SOC hints for thermal runaway XLSX files
- CSV header previews for schema grouping

The next processing layer should consume `file_inventory.csv`, then extract
only the rows/files needed for a specific model experiment.

`Batch` archives contain both `cycling *.csv` and `RPT *.csv` files. The
archive-level category remains `cycle_life/cycling`, while the file-level
`measurement_type` separates `cycle_timeseries` from `rpt_diagnostic`. macOS
resource files such as `._cycling 21.csv` are excluded from the inventory.

`configs/datasets/external_battery_schema_map.json` defines the first common
field contract. For example, `Current(A)` and `Current (A)` both normalize to
`current_a`, while `Voltage(V)` and `Voltage (V)` normalize to `voltage_v`.

`extract_external_battery_tables.py` applies that map and prepends identity
columns such as `dataset_id`, `measurement_type`, `cell_id`, `cycle_index`, and
`diagnostic_part`. These sample tables are the handoff point to feature
engineering.
