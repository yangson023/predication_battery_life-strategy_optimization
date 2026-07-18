# REG-002 Public LMB Full-Cell Tiny Validation

```text
source_data_audit_only=True
tiny_validation_only=True
model_training_allowed=False
formal_training_set_created=False
```

## Conclusion

REG-002 Uppaluri/Onori OSF is currently the strongest public LMB full-cell data candidate in this project. The downloaded small `*_capacity_degradation.mat` files are machine-readable and contain per-cell charge capacity, discharge capacity, and equivalent cycle arrays.

This is not a formal training set yet. It is a successful tiny validation and label audit.

## Parsed Data

Output directory:

`outputs/lmb_public_source_data/reg002_capacity_tiny_validation_20260706`

Generated files:

- `reg002_capacity_degradation_long.csv`
- `reg002_cell_summary.csv`
- `reg002_capacity_label_audit.csv`
- `reg002_trainability_gate.csv`
- `reg002_capacity_tiny_validation_report.json`
- `reg002_capacity_tiny_validation_report.md`

Key results:

| item | value |
| --- | ---: |
| Parsed MAT files | 20 |
| Long rows | 9604 |
| `capacity_eol_80` observed cells | 16 |
| `capacity_eol_70` observed cells | 3 |

## Trainability Decision

REG-002 can proceed to exploratory label-design / baseline-ready export planning, but not formal model training.

Formal training is blocked by:

- missing terminal reason
- missing planned cycle count
- missing protocol metadata in the small MAT files
- missing step/record layer in the small MAT files

## Next Step

The next reasonable step is a REG-002 exploratory baseline-ready export design:

1. Keep only past-cycle features.
2. Define `capacity_eol_80` target carefully.
3. Separate observed and right-censored cells.
4. Use leave-one-cell-out planning only.
5. Do not use random row split.
6. Do not call the result formal model performance.

If protocol/metadata can be recovered from the paper or larger `*_Data.mat` files, then REG-002 may become the first public LMB full-cell exploratory baseline dataset in this project.
