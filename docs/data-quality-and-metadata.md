# Data Quality and Metadata

This data-pipeline step adds two things:

- a manually maintained NASA cell metadata table
- repeatable data quality reports with optional Parquet conversion

## Metadata

The NASA cell metadata table is:

```text
configs/datasets/nasa_li_ion_cells.csv
```

It records dataset name, battery type, cell id, nominal capacity, charge protocol,
discharge cutoff voltage, ambient set temperature, and EOL threshold. The cutoff
voltage is important because NASA cells B0005, B0006, B0007, and B0018 were not
all discharged to the same lower voltage.

## Quality Reports

Run:

```powershell
python modules\data_pipeline\quality_and_parquet.py
```

The script scans:

```text
data/processed/nasa/li_ion/<cell_id>/*.csv
```

and writes:

```text
data/processed/nasa/li_ion/quality_report.csv
data/processed/nasa/li_ion/quality_report.json
data/processed/nasa/li_ion/<cell_id>/quality_report.json
```

## Checks

- required processed files exist for each cell
- missing values and missing ratio
- duplicate rows
- time monotonicity within each cycle
- voltage, current, temperature, capacity, and impedance range checks
- discharge capacity jump warnings

## Parquet

If `pyarrow` or `fastparquet` is installed, the script writes a `.parquet` file
next to each `.csv` file. If no Parquet engine is available, the quality report
is still generated and `parquet_status` is set to `skipped_no_engine`.
