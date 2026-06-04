# Research Rigor Prompt

Use this reminder before changing data, labels, models, evaluation, or strategy
optimization code in this project.

## Core Attitude

Treat every result as a scientific claim that must be traceable, falsifiable,
and reproducible. Prefer a slower, auditable pipeline over a fast result whose
data source, label definition, or validation boundary is unclear.

## Non-Negotiable Rules

- Record data provenance: source archive, cell ID, protocol family, chemistry,
  preprocessing script, and generated manifest must stay connected.
- Do not mix task families without an explicit reason. Cycle-life and RPT data
  can support SOH/RUL; thermal runaway data should support safety constraints
  and abuse-risk modeling unless a separate research question is defined.
- State label definitions before training. Include threshold, initial capacity
  window, sustained crossing rule, censoring handling, and capacity source.
- Mark right-censored batteries honestly. Do not convert unobserved EOL into a
  false observed lifetime.
- Split validation by cell, batch, protocol, or source dataset when testing
  generalization. Random row splits are insufficient for battery-life claims.
- Keep uncertainty visible. Report interval coverage, calibration status, and
  failure cases, not only point-error metrics.
- Preserve negative results and warnings. A failed extraction, poor coverage, or
  unstable label is information, not clutter.
- Avoid strategy optimization claims unless the predictor, safety constraints,
  and reward definition have all been documented.

## Development Checklist

Before committing a scientific pipeline change, check:

- Which files or archives were read?
- Which rows, cells, batches, and measurement types were included or excluded?
- Which columns were used as capacity, time, current, voltage, temperature, or
  safety signals?
- Are labels observed, censored, or sample-only?
- Are outputs deterministic under the same inputs and parameters?
- Did tests cover at least one normal case and one failure or edge case?

## Interpretation Guardrail

Never describe a sample run as final model evidence. Sample runs validate code
paths and schema assumptions. Scientific conclusions require sufficient cells,
documented protocols, held-out validation, and calibrated uncertainty.
