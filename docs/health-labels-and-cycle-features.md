# SOH/RUL Labels and Cycle Features

The feature engineering pipeline reads discharge-cycle summaries from:

```text
data/processed/nasa/li_ion/<cell_id>/cycle_summary.csv
```

and writes model-ready tables to:

```text
data/features/nasa/li_ion/
```

## Label Rules

- `SOH` is capacity-based: current discharge capacity divided by the initial discharge capacity.
- Default end of life (`EOL`) is the first discharge cycle with `SOH <= 0.70`.
- `RUL` is reported in discharge cycles until EOL.
- A cell that does not reach the EOL threshold before its recorded data ends is marked `rul_is_censored = True`; it does not receive an invented numeric RUL target.
- The EOL threshold and number of consecutive below-threshold cycles are command-line configurable.

## Generated Tables

- `soh_rul_labels.csv`: combined SOH/RUL label table across cells.
- `cycle_features.csv`: combined discharge-cycle feature table across cells.
- `label_summary.csv`: one-row-per-cell endpoint summary.
- `<cell_id>/soh_rul_labels.csv`: single-cell label table.
- `<cell_id>/cycle_features.csv`: single-cell feature table.

## Feature Construction

The feature table contains:

- discharge cycle measurements already available in the processed summaries
- the latest available charge and impedance summary at or before each discharge cycle
- trailing-only rolling capacity and SOH statistics for 5 and 10 cycle windows
- trailing-only capacity and SOH trend slopes

Only previous or current observations are used when adding history features. Later
cycles are not joined into earlier samples.

## Usage

```powershell
python modules\feature_engineering\build_nasa_health_features.py
```

To use an 80% capacity endpoint:

```powershell
python modules\feature_engineering\build_nasa_health_features.py --eol-threshold 0.80
```

For current-SOH estimation, avoid using `capacity_ah`, `soh_capacity_ratio`, or
features derived from current capacity as model inputs, because those fields define
the target. They are appropriate as observed state inputs for future-RUL prediction.
