# LMB Agent Workflow Reference

Use this reference when dividing work among Codex, Trae, and the user.

## Default Division

| Actor | Primary responsibility |
| --- | --- |
| Codex | Local verification, schemas, gates, small critical code, tests, final review |
| Trae | Draft implementation, literature summaries, scientific critique drafts, repetitive code scaffolds |
| User | Advisor feedback, lab-data field confirmation, long command execution, budget/hardware decisions |

## Handoff Pattern

```text
Codex defines scope and acceptance criteria
-> Trae drafts broad implementation or critique
-> user returns Trae output
-> Codex verifies locally and patches narrowly
-> user runs long commands if needed
-> Codex reviews reports and gate status
```

## Prompt Templates

Codex:

```text
Execution agent: Codex
Role: local verification and gatekeeping agent
Task goal:
Inputs:
Strict rules:
Expected outputs:
Forbidden:
```

Trae:

```text
Execution agent: Trae
Role: draft implementation or scientific critique agent
Task goal:
Context:
Expected draft:
Risks to inspect:
Do not claim final correctness; Codex will verify locally.
```

## Budget-Aware Rules

- Prefer `Conclusion / Evidence / Risk / Next step` responses.
- Ask Trae for drafts when the task is broad and local verification is not yet needed.
- Ask Codex for final local verification before accepting code, data, or claims.
- Let the user run long local commands and return manifest/report outputs.
- Do not duplicate Codex and Trae work.
- Do not scan or regenerate large data when manifest/report/schema checks answer the question.

## Big-Data Stop Conditions

Stop and ask for review if a processed cache already exists, schema check fails, output rows are unexpectedly zero, label gate changes unexpectedly, a script attempts full-table reads on multi-GB CSV files, or training is requested before label gates are reviewed.

## Standard Final Decision Language

- `Allowed: documentation or design only`
- `Allowed: synthetic validation only`
- `Allowed: tiny real-slice validation only`
- `Allowed: controlled full feature generation`
- `Blocked: label gate not passed`
- `Blocked: dataset is Li-ion method data only for LMB claims`
- `Blocked: training would be scientifically premature`
