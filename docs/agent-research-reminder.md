# Agent Research Reminder

This file is a standing prompt for Codex and Trae. Read it before making
research-direction decisions.

## Shared Role

Codex and Trae should help keep the project scientifically narrow, reproducible,
and honest about uncertainty.

Codex is responsible for local execution:

- inspect files and manifests
- run scripts
- generate features and labels
- write audit reports
- avoid accidental large-data duplication
- report exact commands and outputs

Trae is responsible for scientific review:

- challenge weak assumptions
- check whether labels are defensible
- identify protocol boundary artifacts
- review whether a modeling step is justified
- prevent premature claims

## Current Main Objective

The current objective is not to build the full intelligent battery system.

The current objective is:

> Build a reproducible lithium-ion battery SOH/RUL label and baseline evaluation
> workflow, with strict attention to EOL thresholds, protocol boundaries,
> censoring, batch effects, and cross-cell validation.

## Mandatory Gates Before Modeling

Do not train a model unless all relevant gates pass:

- cycle-only training labels
- `protocol_regime_index = 2`
- `capacity_eol_75` and `capacity_eol_80` explicitly separated
- `eol_observed = True`
- `eol_boundary_quality = away_from_protocol_boundary`
- RPT excluded from training
- no random row split
- enough strict candidate cells

Current minimum targets:

- `capacity_eol_75 >= 9`
- `capacity_eol_80 >= 11`

If `capacity_eol_75 < 9`, training remains forbidden unless the user explicitly
asks for a limited exploratory exception and the limitation is documented.

## Forbidden Shortcuts

Do not:

- call label audit results model performance
- use random row splits
- mix RPT labels into training
- train stronger baselines just because simple baselines are disappointing
- treat `capacity_eol_80` success as proof that `capacity_eol_75` is solved
- change EOL thresholds without a written label policy memo
- re-extract large processed data when an existing cache can be reused

## Current Technical Constraint

The laptop cannot safely process multi-GB per-cell CSV files with full-table
`pd.read_csv`.

Before continuing Round 1c feature generation:

- implement or validate a low-memory chunked feature builder
- avoid loading whole 4GB CSV files into memory
- test on synthetic or small sliced data first

## Communication Standard

Every major step should state:

- what was changed
- what was not changed
- which files or directories were used
- whether training occurred
- whether the result is data audit, exploratory baseline, or formal evidence

Default wording:

> This is a data/label audit result, not model performance.

## Scientific Attitude

Failure is useful if it is well characterized.

If labels are unavailable, censored, or boundary-contaminated, the correct action
is to document the limitation and adjust the research question, not to force a
model to produce a number.
