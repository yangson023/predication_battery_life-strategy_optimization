# Model Transfer Learning Plan

This branch implements the first version of the "shared feature system plus
chemistry-specific model" strategy.

## Core Idea

Use one common cycle-level feature contract across all battery data, then route
each sample to a battery-type-specific model when available. If a chemistry model
does not exist yet, fall back to a shared baseline.

```text
common_cycle_v1 features
  -> shared_capacity_ridge
  -> li_ion_capacity_ridge
  -> future lfp/nmc/nca model heads
```

## Current Implementation

- `configs/model_registry.json` declares shared and chemistry-specific model specs.
- `feature_contract.py` defines required metadata and common cycle features.
- `model_router.py` resolves model specs by `battery_type`.
- `train_shared_baseline.py` trains a lightweight ridge baseline without requiring
  scikit-learn.

## Why This Matters

This keeps the data and feature language unified while allowing LFP, NMC, NCA,
and other chemistries to learn different degradation behavior. New chemistries
can start from the shared baseline, then fine-tune or replace their own model
head once enough data exists.

## Next Steps

- Train a real shared baseline on observed-RUL samples.
- Add chemistry-specific fine-tuning once LFP/NMC/NCA datasets are available.
- Add model evaluation with leave-one-battery-out validation in the RUL branch.
- Replace the lightweight baseline with scikit-learn or XGBoost when project
  dependencies are formalized.
