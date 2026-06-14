# Research Problem Definition

This document translates the original project vision into a focused research
problem. It should be used as a standing reference before Codex or Trae starts a
new task.

## Original Vision

The long-term vision is an intelligent battery research system with three
connected parts:

1. A "fortune teller" that estimates SOH/RUL from experimental battery data.
2. A "nutritionist" that recommends charging/discharging strategies to extend
   battery lifetime.
3. A GUI automation layer that can operate experimental software when devices do
   not expose a usable API.

The full long-term system can be described scientifically as:

> An intelligent closed-loop lithium-ion battery research system that combines
> online health prognostics, lifetime-aware charging strategy optimization, and
> human-interface automation for experimental equipment.

This is the long-term direction, not the immediate research claim.

## Current Research Scope

The current project stage focuses only on the prognostics part:

> Build a reproducible workflow for lithium-ion battery SOH/RUL label
> construction, feature extraction, and cross-cell baseline evaluation using
> public aging datasets.

The current stage does not claim to solve closed-loop control or charging
strategy optimization.

## Working Title

Chinese:

> 面向锂离子电池寿命预测的可复现标签构建与跨电池泛化评估研究

English:

> Reproducible Label Construction and Cross-Cell Baseline Evaluation for
> Lithium-Ion Battery Health Prognostics

## Research Questions

### RQ1. Label Availability

How do different EOL thresholds affect the availability of reliable observed
labels?

Current working thresholds:

- `capacity_eol_80`
- `capacity_eol_75`

Current finding:

- `capacity_eol_80` is easier to observe.
- `capacity_eol_75` is stricter and often censored by limited observation
  windows.

### RQ2. Protocol Boundary Artifacts

Can protocol regime changes create false EOL crossings?

Current label gate requires:

- `protocol_regime_index = 2`
- `eol_boundary_quality = away_from_protocol_boundary`

Crossings near protocol boundaries must be excluded from trainable labels.

### RQ3. Cross-Cell Generalization

Can a baseline model trained on several cells generalize to a held-out cell?

Required validation style:

- leave-one-cell-out
- no random row split
- per-cell reporting

### RQ4. Early Prediction Feasibility

How much early-cycle information is needed before EOL risk becomes predictable?

This question should only be revisited after label gates are adequate.

## Inputs And Outputs

Inputs:

- raw public battery aging archives
- processed by-cell cycle time series
- cycle-level features
- label summary tables

Outputs:

- reproducible feature tables
- trainable label audit
- baseline-ready dataset exports
- exploratory LOCO baseline results
- diagnostics explaining false positives, missed EOL, and batch risk

## Current Scientific Gates

Before modeling, the dataset must pass:

- `source_table = cycle_features.csv`
- `protocol_regime_index = 2`
- `label_key in {capacity_eol_75, capacity_eol_80}`
- `eol_observed = True`
- `eol_boundary_quality = away_from_protocol_boundary`
- RPT labels excluded from training

Current minimum label targets:

- `capacity_eol_75 >= 9` strict candidate cells
- `capacity_eol_80 >= 11` strict candidate cells

If either gate fails, do not train a new model.

## Current Status

As of the latest completed audit:

- `capacity_eol_80` has passed the minimum gate.
- `capacity_eol_75` remains the main bottleneck.
- Round 1c extraction has been completed, but feature generation should use a
  low-memory chunked builder before labels are generated.

## Out Of Scope For Now

The following are important but not part of the immediate research claim:

- reinforcement learning charging strategy optimization
- closed-loop experimental control
- GUI automation of laboratory software
- Random Forest, XGBoost, SVM, MLP, or other stronger baselines
- RUL regression
- RPT-based training labels

These can become later phases after the prognostics workflow is reproducible and
scientifically defensible.

## Roadmap

| Phase | Focus | Status |
| --- | --- | --- |
| Phase 1 | SOH/RUL label construction and baseline evaluation | current |
| Phase 2 | robust uncertainty and calibration | later |
| Phase 3 | charging/discharging strategy optimization | later |
| Phase 4 | GUI automation for experimental devices | later |
| Phase 5 | closed-loop intelligent battery system | long-term |

## Working Principle

The project should prefer a small, reproducible, scientifically defensible
workflow over a broad system that cannot yet be validated.
