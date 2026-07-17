---
name: lithium-metal-battery-research
description: "Use for lithium metal battery (LMB) research tasks involving battery life prediction, SOH/RUL framing, feature engineering, label policy, data auditing, strategy optimization planning, advisor-facing explanations, or Codex/Trae/user task division. Trigger when the project may otherwise default to lithium-ion assumptions, when Li-ion data must be treated as pipeline validation only, or when LMB-specific variables such as Coulombic efficiency, overpotential, voltage hysteresis, polarization growth, plating/stripping behavior, soft-short indicators, areal capacity, current density, N/P ratio, electrolyte, separator, pressure, or temperature matter."
---

# Lithium Metal Battery Research

## Core Rule

Treat lithium metal batteries as the target research system. Treat current Li-ion datasets only as pipeline validation or method-development data unless the user provides true LMB data.

Never state Li-ion-only results as lithium metal battery conclusions.

## Default Workflow

Use this order for LMB prognostics and strategy tasks:

```text
problem definition -> data inventory -> feature schema -> label policy -> audit gates -> tiny validation -> full run -> model gate -> strategy gate
```

For large data paths, require:

```text
synthetic test -> tiny real slice -> full run
```

Do not skip tiny validation for new parsers, feature builders, label builders, or extraction paths.

## LMB Research Guardrails

- State whether the dataset is true LMB data or Li-ion method-development data.
- Record cell design, electrolyte, separator, pressure, protocol, and measurement provenance when available.
- Do not rely on capacity EOL alone without checking whether CE, overpotential, polarization, or soft-short behavior is more appropriate.
- Keep observed, censored, protocol-censored, and audit-only labels separate.
- Do not use random row splits for battery lifetime claims.
- Do not train models before data gates and label audits pass.
- Do not call label audit, schema validation, or tiny validation model performance.
- Do not use RPT or diagnostic data for training unless protocol-regime assignment is explicit and reviewed.

## Codex / Trae / User Division

Use Codex for project structure, schemas, gates, local checks, tests, validation, small critical code, and final review.

Use Trae for large implementation drafts, literature summaries, scientific critique drafts, repetitive parser scaffolds, and alternative plan review.

Use the user for long local commands, big data runs, hardware/disk monitoring, advisor feedback, and lab data availability confirmation.

Avoid having Codex and Trae independently do the same task.

## Budget-Aware Response Mode

Default to concise responses:

```text
Conclusion:
Evidence:
Risk:
Next step:
```

Use longer explanations only for scientific definition, method design, paper reading, advisor reports, or major architecture decisions. If the user says quota pressure is gone, relax compression.

## Reference Loading

Load reference files only when needed:

- Read `references/lmb-feature-schema.md` for LMB metadata, raw data, and feature requirements.
- Read `references/lmb-label-policy.md` for LMB label definitions, censoring, and trainability gates.
- Read `references/lmb-agent-workflow.md` for Codex/Trae/user handoff rules and prompt patterns.

## Standard Phrasing

Allowed:

- Current Li-ion data are pipeline validation data.
- LMB claims require LMB-specific data or a clearly stated transfer-learning limitation.
- Capacity EOL is one label family, not the whole LMB failure definition.

Forbidden:

- The current Li-ion baseline proves LMB prediction performance.
- Capacity-only labels are sufficient for lithium metal batteries by default.
- Tiny validation or label audit is model performance.
