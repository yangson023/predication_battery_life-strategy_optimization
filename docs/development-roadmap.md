# Development Roadmap

This roadmap is the lightweight development log MVP for the project. It tracks
which parts are complete enough to discuss in the initial pass-check defense,
which parts are still exploratory, and which artifacts can be used as evidence.

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

## Initial Pass-Check MVP Status

| Area | Status | Current evidence | Defense-safe interpretation |
| --- | --- | --- | --- |
| Project scope and research positioning | Completed | `README.md`, `docs/research-rigor-prompt.md`, `docs/research-notes.md` | The project is positioned as a battery SOH/RUL prediction and later strategy-optimization system. |
| NASA data preprocessing | Completed | `data/processed/nasa/li_ion/dataset_manifest.json`, cell-level `cycle_summary.csv`, `charge_timeseries.csv`, `discharge_timeseries.csv`, `impedance_spectra.csv` | NASA raw `.mat` files have been converted into structured cycle, time-series, impedance, and quality-report tables. |
| NASA SOH/RUL labels | Completed | `data/features/nasa/li_ion/soh_rul_labels.csv`, `soh_rul_labels_multi_threshold.csv`, `label_summary.csv` | Capacity-based SOH/RUL labels are available, including multi-threshold EOL definitions and censored-cell handling. |
| NASA cycle-level features | Completed | `data/features/nasa/li_ion/cycle_features.csv` | Cycle features include capacity, SOH, prior charge/impedance joins, rolling statistics, and trailing trend slopes. |
| External battery feature engineering | Completed for current per-cell sample scope | `data/features/external_battery_datasets/cycle_features.csv`, `rpt_features.csv`, `protocol_regime_summary.csv` | External cycle and RPT features are built, with protocol-regime diagnostics for current data scope. |
| External data expansion audit | Completed for Round 1a | `docs/external-expansion-round1a-audit.md`, `outputs/label_audit/external_trainable_labels_with_round1a/` | Round 1a added seven cells and improved strict `capacity_eol_80` coverage from 6 to 10 cells, but `capacity_eol_75` remains below the training gate. |
| External health labels | Completed for current data scope | `data/features/external_battery_datasets/external_health_labels.csv`, `external_label_summary.csv` | External SOH/RUL-style labels are generated, but not all labels are safe for training. |
| Trainable label audit | Completed | `outputs/label_audit/external_trainable_labels/label_audit_report.md` | 13 label summaries are currently trainable; 167 are excluded because of limited windows, unreliable protocol-boundary crossings, or unmapped RPT protocol assignment. |
| Trainable label audit with Round 1a | Completed | `outputs/label_audit/external_trainable_labels_with_round1a/label_audit_report.md` | 19 label summaries are currently trainable after Round 1a; 287 are excluded under the same conservative audit rules. |
| Unit tests | Completed | `tests/`, latest run: 20 tests passed on 2026-06-12 | The implemented data, feature, label, export, LOCO baseline, diagnostics, and feature-exclusion logic has focused unit-test coverage. |
| Defense figures | Completed | `outputs/demo/figures/*.png` | Five PPT-ready figures are available for the initial pass-check defense. |
| Pass-check material draft | Completed as draft | `outputs/demo/pass_check_materials/通关材料整合稿.md` | A report/PPT/answer-script mother draft is available and should be adapted to the official template. |
| Prediction modeling | Exploratory only | NASA LOBO baseline outputs, external LOCO binary baseline outputs, and diagnostic reports under `models/rul_prediction/` | The current baselines should be described as workflow diagnostics and data-gate checks, not final model performance. |
| External baseline diagnostics | Completed as exploratory diagnostics | `models/rul_prediction/external_loco_binary_baseline/combined_main/diagnostics/`, `feature_exclusion_diagnostics/` | Diagnostics show early false positives, batch-feature risk, and `energy_wh_last` as a possible confound feature; stronger models remain blocked by label coverage. |
| Strategy optimization | Not started beyond planning | `configs/reward_config.yaml`, `configs/experiment_protocols.yaml` placeholders | Strategy optimization remains a next-stage plan after a reliable predictor and safety constraints are defined. |

## Evidence Artifacts for PPT and Report

- `outputs/demo/figures/05_project_pipeline_overview.png`: overall project workflow.
- `outputs/demo/figures/01_nasa_soh_degradation_curves.png`: NASA SOH degradation curves.
- `outputs/demo/figures/02_nasa_label_summary.png`: NASA capacity fade and censoring/EOL summary.
- `outputs/demo/figures/03_external_protocol_regimes.png`: external protocol-regime diagnostics.
- `outputs/demo/figures/04_external_label_audit.png`: trainable-label audit summary.
- `outputs/diagnostics/nasa_rul_prediction_sample_diagnostic.png`: optional baseline diagnostic figure.

## Development Log

| Date | Priority | Item | Status | Notes |
| --- | --- | --- | --- | --- |
| 2026-05-22 | P0 | Initialize project structure | Executed | Created the working layout for `data`, `modules`, `docs`, `configs`, `models`, `notebooks`, and `tests`. |
| 2026-05-22 | P0 | Establish research scope | Executed | Repository scope set to battery SOH/RUL prediction, strategy optimization, execution control, and experiment tracking. |
| 2026-05-29 | P0 | Prepare model artifact area | Executed | `models/.gitkeep` reserves the model-output location; no final model artifact is claimed yet. |
| 2026-06-05 | P0 | Verify 6-cell external labels before RUL baseline training | Executed | All labels remained limited-window diagnostics at that stage; short-window crossings were not treated as final EOL evidence. |
| 2026-06-05 | P0 | Add protocol regime diagnostics to external cycle features | Executed | `cycle_features.csv` now flags current, charge-fraction, and duration shifts; by-cell builds write `protocol_regime_summary.csv`. |
| 2026-06-05 | P0 | Increase per-cell observation window before expanding model claims | Not executed | Recommended next step was 20+ cycle files per selected cell, then regenerate features and labels. |
| 2026-06-05 | P1 | Stabilize external initial capacity definition | Not executed | Evaluate `initial_capacity_window=5` after protocol-consistent windows are available. |
| 2026-06-05 | P1 | Filter complete RPT capacity diagnostics before fusion | Not executed | Candidate rule: compare `pulse_type_count`, `capacity_delta_ah`, and cycle capacity consistency. |
| 2026-06-08 | P0 | Add trainability guards for external health labels | Executed | Cycle EOL crossings near protocol-regime boundaries are excluded from training; RPT labels are excluded until protocol-regime assignment exists. |
| 2026-06-08 | P0 | Export trainable label audit artifacts before modeling | Executed | Trainable cycle labels, excluded labels, coverage matrix, and audit reports are generated before any exploratory baseline. |
| 2026-06-09 | P0 | Confirm initial pass-check requirements | Executed | The college notice requires a pass-check report before June 22 and a PPT defense within 6 minutes near late June. |
| 2026-06-09 | P0 | Generate PPT-ready demo figures | Executed | `modules/visualization/make_demo_figures.py` writes five figures under `outputs/demo/figures`. |
| 2026-06-09 | P0 | Draft pass-check report and PPT storyline | Executed | `outputs/demo/pass_check_materials/通关材料整合稿.md` consolidates report text, PPT structure, speaking notes, innovation claims, and Q&A. |
| 2026-06-09 | P0 | Run focused unit-test suite | Executed | `python -m unittest discover -s tests` previously passed the focused suite. |
| 2026-06-11 | P0 | Audit external data expansion Round 1a | Executed | Seven additional cells were processed from D-drive cache; strict `capacity_eol_80` candidates increased to 10, while `capacity_eol_75` remained insufficient at 5. |
| 2026-06-11 | P0 | Plan external expansion Round 1b | Executed | `docs/external-expansion-round1b-plan.md` defines a storage-safe D-drive expansion plan and keeps model training forbidden until the label gate passes. |
| 2026-06-12 | P0 | Re-run current unit-test suite | Executed | `python -m unittest discover -s tests` ran 20 tests successfully. |

## Next Milestones Before Initial Pass-Check

| Target date | Priority | Item | Expected output |
| --- | --- | --- | --- |
| 2026-06-12 | P0 | Fill the official pass-check report template | Completed report draft for advisor review. |
| 2026-06-15 | P0 | Build the 6-minute PPT from the seven-page storyline | Defense slides using the five generated figures. |
| 2026-06-17 | P0 | Rehearse and tighten the defense script | Script shortened to less than 6 minutes with backup answers. |
| 2026-06-20 | P0 | Advisor review and signature | Final report ready before the June 22 submission deadline. |
| After pass-check | P1 | Implement protocol-aware reliability-weighted RUL baseline | Compare ordinary baseline, trainable-label-only baseline, and reliability-weighted baseline. |
