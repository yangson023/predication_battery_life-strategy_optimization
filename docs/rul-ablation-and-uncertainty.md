# RUL Feature Ablation and Uncertainty

This step extends the RUL baseline in two ways:

- residual-interval uncertainty estimation
- feature group ablation

## Residual Interval

For each leave-one-battery-out fold, the model computes residuals on the training
cells:

```text
residual = actual_rul - predicted_rul
```

The 10%, 50%, and 90% residual quantiles are added to each test prediction to
produce:

```text
predicted_rul_p10
predicted_rul_p50
predicted_rul_p90
prediction_interval_width
```

For folds with observed EOL labels, the report includes:

- `interval_coverage_80`
- `interval_width_mean`

## Feature Ablation

Feature groups are defined in `leave_one_battery_out.py`:

- history
- capacity
- trend
- voltage
- current
- temperature
- charge
- impedance

`feature_ablation.py` runs the baseline once with all features and then once per
removed feature group.

## Usage

```powershell
python modules\rul_prediction\leave_one_battery_out.py
python modules\rul_prediction\feature_ablation.py
```

Outputs are written under:

```text
models/rul_prediction/nasa_li_ion_baseline/
```

These files are local model artifacts and are ignored by Git.
