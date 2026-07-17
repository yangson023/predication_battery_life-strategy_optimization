# LMB Label Policy Reference

Use this reference when defining, auditing, or reviewing lithium metal battery labels.

## Label Principle

Lithium metal battery failure is not always captured by capacity retention. Use capacity labels as one family, not the entire target definition.

Every label must define source table, source signal, threshold, observation window, sustained-crossing rule, censoring rule, protocol regime, and trainable vs audit-only status.

## Candidate Label Families

| Label family | Example definition | Notes |
| --- | --- | --- |
| Capacity EOL | Capacity retention falls below 80%, 75%, or task-specific threshold | Useful but not sufficient alone |
| CE failure | CE stays below a threshold for N cycles | Threshold depends on cell design and data quality |
| CE instability | Rolling CE std or CE jump exceeds a threshold | Useful for unstable plating/stripping |
| Polarization failure | Voltage hysteresis or overpotential exceeds threshold | Strong LMB mechanism link |
| Voltage instability | Sudden abnormal voltage drop, noise, or rest decay | Possible soft-short indicator |
| Soft-short warning | Rest voltage decay, CE anomaly, or abnormal voltage path | Audit carefully; do not overclaim |
| Safety stop | Experiment stopped due to safety or device protection | Requires explicit failure reason |
| Protocol-censored | Protocol changed or experiment ended before clean failure | Not an observed EOL |

## Trainability Gates

A label is trainable only if dataset classification is valid, provenance is known, source signal is valid, observation window is long enough, censoring is honest, observed crossing is not a protocol-boundary artifact, and diagnostic sources have protocol-regime assignment when used for training.

A label is audit-only if it comes from Li-ion method-development data for LMB claims, RPT/diagnostics without protocol assignment, unobserved/censored EOL, protocol-boundary crossing, or unknown cell chemistry.

## Censoring Rules

| Status | Meaning |
| --- | --- |
| `observed` | Failure event occurs inside the valid protocol window |
| `right_censored` | Experiment ends before event occurs |
| `protocol_censored` | Protocol change prevents continuous interpretation |
| `diagnostic_only` | Source is useful for audit but not trainable |
| `unknown` | Metadata or signal quality is insufficient |

## Prohibited Claims

- Do not convert censored cells into observed lifetime.
- Do not claim LMB performance from Li-ion-only labels.
- Do not call label coverage model performance.
- Do not compare labels across cell designs without metadata controls.
