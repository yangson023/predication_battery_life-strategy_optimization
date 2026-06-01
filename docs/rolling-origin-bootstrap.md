# Rolling-Origin Bootstrap Evaluation

This workflow evaluates whether RUL prediction improves as more cycles are
observed.

## Method

For each held-out test cell:

1. Train on the other cells with observed RUL labels.
2. Choose rolling origins, such as cycles 20, 40, 60, 80, ...
3. At each origin, predict using the latest available sample at or before that
   discharge cycle.
4. Fit many bootstrap ridge models by resampling the training rows.
5. Use the bootstrap prediction distribution to produce mean, standard
   deviation, P10, P50, and P90.

## Recommended Label

Use `capacity_eol_80` first because all four NASA cells have observed 80% EOL
events.

## Usage

```powershell
python modules\rul_prediction\rolling_origin.py `
  --labels data\features\nasa\li_ion\soh_rul_labels_multi_threshold.csv `
  --label-key capacity_eol_80 `
  --origin-start 20 `
  --origin-step 20 `
  --bootstrap-models 100
```

Outputs:

```text
models/rul_prediction/nasa_li_ion_baseline/capacity_eol_80/rolling_origin_predictions.csv
models/rul_prediction/nasa_li_ion_baseline/capacity_eol_80/rolling_origin_summary.csv
```

These files are local artifacts and are ignored by Git.

## Current Interpretation

The bootstrap interval estimates model variance from resampled ridge baselines,
but it is not yet calibrated. If `coverage_80` is much lower than `0.80`, the
interval is too narrow. The next improvement should add conformal calibration or
a stronger nonlinear model before treating the interval as a reliable confidence
statement.
