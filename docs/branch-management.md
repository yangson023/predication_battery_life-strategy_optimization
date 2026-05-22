# Branch Management

## Recommended Branches

| Branch | Module | Responsibility |
|---|---|---|
| `codex/data-pipeline` | `modules/data_pipeline` | Raw data import, parsing, cleaning, unit normalization, timestamp alignment |
| `codex/feature-engineering` | `modules/feature_engineering` | Capacity, coulombic efficiency, internal resistance, temperature, dQ/dV, dV/dQ features |
| `codex/rul-prediction` | `modules/rul_prediction` | SOH/RUL model training, online inference, uncertainty, evaluation |
| `codex/strategy-optimizer` | `modules/strategy_optimizer` | Action space, reward design, safe optimization, RL/Bayesian optimization prototypes |
| `codex/experiment-control` | `modules/experiment_control` | API-based charger, cycler, BMS, thermal chamber control |
| `codex/gui-automation` | `modules/gui_automation` | Mouse/keyboard automation, screenshot recognition, OCR, state validation |
| `codex/safety-guardrails` | `modules/safety_guardrails` | Voltage, current, temperature, SOC, and abnormal trend protection |
| `codex/experiment-tracking` | `modules/experiment_tracking` | Cell, protocol, run, model, reward, and artifact traceability |
| `codex/dashboard` | `modules/dashboard` | Real-time monitoring UI, RUL curves, strategy status, alarms |
| `codex/integration-closed-loop` | `modules/integration_closed_loop` | End-to-end prediction-decision-execution-feedback loop |
| `codex/model-lfp` | `modules/model_lfp` | LFP-specific prediction and strategy behavior |
| `codex/model-nmc` | `modules/model_nmc` | NMC-specific prediction and strategy behavior |
| `codex/model-nca` | `modules/model_nca` | NCA-specific prediction and strategy behavior |
| `codex/model-transfer-learning` | `modules/model_transfer_learning` | Transfer learning, fine-tuning, cold-start models |
| `codex/battery-metadata-schema` | `modules/battery_metadata_schema` | Battery type, chemistry, manufacturer, capacity, protocol metadata schema |

## Suggested Order

1. `codex/battery-metadata-schema`
2. `codex/data-pipeline`
3. `codex/feature-engineering`
4. `codex/rul-prediction`
5. `codex/model-lfp`, `codex/model-nmc`, `codex/model-nca`
6. `codex/model-transfer-learning`
7. `codex/strategy-optimizer`
8. `codex/safety-guardrails`
9. `codex/experiment-control`
10. `codex/gui-automation`
11. `codex/experiment-tracking`
12. `codex/dashboard`
13. `codex/integration-closed-loop`

## Management Rules

- Keep one branch focused on one module or one clearly bounded feature.
- Merge shared schema and data contracts before model-specific work.
- Do not mix raw experimental data cleaning with model changes in the same branch.
- Every strategy optimization change should document its reward function and safety limits.
- GUI automation changes must include before-action and after-action verification logic.
