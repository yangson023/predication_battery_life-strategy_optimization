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
