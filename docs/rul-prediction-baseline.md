# RUL Prediction Baseline

This module evaluates a lightweight remaining-useful-life baseline on the NASA
cycle feature table.

## Validation Rule

The evaluation uses leave-one-battery-out validation:

```text
train on three cells -> test on the held-out cell
```

This is stricter than randomly splitting cycles because it tests whether the
model generalizes to a new battery rather than memorizing neighboring cycles from
the same cell.

## Censored Cells

`B0007` and `B0018` do not reach the 70% SOH endpoint in the current data.
They are still scored with predictions, but numeric MAE/RMSE are not reported
for those held-out folds because the true RUL is right-censored rather than
observed.

## Usage

```powershell
python modules\rul_prediction\leave_one_battery_out.py
```

Outputs are written to:

```text
models/rul_prediction/nasa_li_ion_baseline/
```

The output files are local model artifacts and are ignored by Git.
