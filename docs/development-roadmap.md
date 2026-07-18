# Development Roadmap

## Direction Realignment

Advisor feedback clarified that the target research object is lithium metal
batteries, not conventional lithium-ion batteries. Existing lithium-ion datasets
and external cycle-life tables remain useful as pipeline validation and
method-development data, but they must not be treated as final lithium metal
battery evidence.

The corrected near-term goal is to build a reproducible lithium metal battery
prognostics foundation: data provenance, low-memory feature engineering, label
auditing, and validation gates before any model or strategy-optimization claim.

## Phase 1: Research Data Foundation

- Define battery metadata schema.
- Normalize experimental log formats.
- Build cycle-level and time-series data tables.
- Create quality checks for missing values, unit mismatch, and abnormal readings.
- Add lithium-metal-specific metadata fields such as anode type, anode-free
  status, areal capacity, N/P ratio, electrolyte formulation, separator,
  pressure, and protocol details.

## Phase 2: Health Feature System

- Extract capacity, energy, coulombic efficiency, DCIR, temperature, and curve-based features.
- Generate feature tables for SOH/RUL model training.
- Keep feature definitions versioned and reproducible.
- Detect protocol regime boundaries before interpreting external threshold crossings as EOL events.
- Add lithium-metal-specific features: CE trend/variance, overpotential,
  voltage hysteresis, polarization growth, nucleation overpotential,
  plating/stripping profile summaries, and soft-short warning indicators.

## Phase 3: Prediction Models

- Build a general baseline model.
- Treat existing lithium-ion baselines as method prototypes only.
- Build lithium-metal-specific models only after LMB labels and fields are
  available and audited.
- Add online update and uncertainty estimation.

## Phase 4: Strategy Optimization

- Define charge/discharge action space.
- Design reward and penalty terms.
- Add hard safety constraints.
- Start with offline/simulation optimization before real equipment control.

## Phase 5: Closed-Loop Experiment System

- Connect prediction, strategy selection, execution, data collection, and reward update.
- Add experiment tracking and dashboard.
- Validate against controlled baseline protocols.

## Development Log

| Date | Priority | Item | Status | Notes |
| --- | --- | --- | --- | --- |
| 2026-06-05 | P0 | Verify 6-cell external labels before RUL baseline training | Executed | All labels remain `limited_window_less_than_50_observations`; short-window crossings must be treated as diagnostics only. |
| 2026-06-05 | P0 | Add protocol regime diagnostics to external cycle features | Executed | `cycle_features.csv` now flags current, charge-fraction, and duration shifts; by-cell builds write `protocol_regime_summary.csv`. |
| 2026-06-05 | P0 | Increase per-cell observation window before expanding model claims | Not executed | Recommended next step is 20+ cycle files per selected cell, then regenerate features and labels. |
| 2026-06-05 | P1 | Stabilize external initial capacity definition | Not executed | Evaluate `initial_capacity_window=5` after protocol-consistent windows are available. |
| 2026-06-05 | P1 | Filter complete RPT capacity diagnostics before fusion | Not executed | Candidate rule: compare `pulse_type_count`, `capacity_delta_ah`, and cycle capacity consistency. |
| 2026-06-08 | P0 | Add trainability guards for external health labels | Executed | Cycle EOL crossings near protocol-regime boundaries are excluded from training; RPT labels are excluded until protocol-regime assignment exists. |
| 2026-06-08 | P0 | Export trainable label audit artifacts before modeling | Executed | Trainable cycle labels, excluded labels, coverage matrix, and audit reports are generated before any exploratory baseline. |
| 2026-06-09 | P0 | Export baseline-ready high-observation external dataset | Executed | Main export keeps only high_minobs20 observed cycle labels for `capacity_eol_75/80`; RPT, censored, boundary, direct-capacity, and protocol-helper fields are excluded before modeling. |
| 2026-06-09 | P0 | Review baseline-ready export before entering RUL branch | Not executed | Trae/Codex should inspect `baseline_ready_dataset_report.*`, `alignment_check.csv`, and `feature_statistics_per_batch.csv` before any exploratory model training. |
| 2026-06-15 | P0 | Realign project target to lithium metal batteries | Executed | Current Li-ion datasets are retained as pipeline validation only; future scientific labels/features must include lithium-metal-specific mechanisms such as CE, overpotential, polarization, and soft-short risk. |
