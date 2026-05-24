# NASA Battery Data Preprocessing

The NASA `.mat` files are organized as one lithium-ion dataset with separate cell folders.

## Folder Layout

```text
data/
  raw/
    nasa/
      li_ion/
        B0005/B0005.mat
        B0006/B0006.mat
        B0007/B0007.mat
        B0018/B0018.mat
  processed/
    nasa/
      li_ion/
        dataset_manifest.csv
        dataset_manifest.json
        B0005/
          cycle_summary.csv
          charge_timeseries.csv
          discharge_timeseries.csv
          impedance_spectra.csv
          manifest.json
```

## Output Files

- `cycle_summary.csv`: one row per charge, discharge, or impedance cycle.
- `charge_timeseries.csv`: sample-level charging voltage, current, temperature, and elapsed time.
- `discharge_timeseries.csv`: sample-level discharging voltage, current, temperature, elapsed time, and cycle capacity.
- `impedance_spectra.csv`: sample-level complex impedance fields split into real, imaginary, magnitude, and phase columns.
- `manifest.json`: per-cell source and cycle counts.
- `dataset_manifest.csv`: dataset-level index across all processed cells.

## Battery Type

All four provided NASA cells are stored under `li_ion`. If future datasets include LFP, NMC, NCA, or other chemistries, create sibling folders such as:

```text
data/raw/<dataset>/lfp/<cell_id>/
data/processed/<dataset>/lfp/<cell_id>/
```

The preprocessing script is located at:

```text
modules/data_pipeline/preprocess_nasa_mat.py
```
