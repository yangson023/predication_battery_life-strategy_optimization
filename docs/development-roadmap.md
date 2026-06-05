# Development Roadmap

## Phase 1: Research Data Foundation

- Define battery metadata schema.
- Normalize experimental log formats.
- Build cycle-level and time-series data tables.
- Create quality checks for missing values, unit mismatch, and abnormal readings.

## Phase 2: Health Feature System

- Extract capacity, energy, coulombic efficiency, DCIR, temperature, and curve-based features.
- Generate feature tables for SOH/RUL model training.
- Keep feature definitions versioned and reproducible.
- Detect protocol regime boundaries before interpreting external threshold crossings as EOL events.

## Phase 3: Prediction Models

- Build a general baseline model.
- Build chemistry-specific models for LFP, NMC, and NCA.
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
