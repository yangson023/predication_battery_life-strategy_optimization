# Project Overview

This document is a concise explanation of the current battery-life prediction
project. It is written for lab discussion, advisor communication, and future
agent handoff.

## One-Sentence Definition

This project builds a reproducible lithium-ion battery health prognostics
workflow for constructing SOH/RUL labels, extracting cycle-level features, and
evaluating cross-cell prediction baselines under strict scientific gates.

The current results are data and label audits plus exploratory workflow
diagnostics. They are not formal model performance.

## Vision Versus Current Stage

The original long-term vision has three parts:

| Informal idea | Research/engineering term | Status |
| --- | --- | --- |
| "fortune teller" | SOH/RUL health prognostics | current focus |
| "nutritionist" | lifetime-aware charging/discharging strategy optimization | later |
| automatic mouse operation | GUI automation for non-API experimental devices | later |

The long-term goal is an intelligent closed-loop battery research system. The
current stage is narrower:

> Build the data, label, feature, audit, and baseline workflow needed before any
> closed-loop strategy optimization is scientifically meaningful.

This narrower stage is deliberate. A strategy optimizer is not useful if the
health labels and prediction targets are not yet reliable.

## Why Focus On The "Fortune Teller" First

The prediction component must come first because it defines the measurement of
success for later strategy optimization.

Before optimizing charging or discharging policies, the project must answer:

- What counts as end-of-life?
- Which cells have observed EOL instead of censored outcomes?
- Which crossings are reliable and which are protocol-boundary artifacts?
- Can a model generalize from several cells to a held-out cell?

Until these questions are answered, a reward function for "longer life" would be
poorly grounded.

## Current Data Flow

The current workflow is:

```text
raw archives
-> processed by-cell cache
-> cycle_features / rpt_features
-> health labels
-> trainable label audit
-> baseline-ready export
-> exploratory LOCO baseline
-> diagnostics
```

Current storage layout:

| Layer | Example path | Notes |
| --- | --- | --- |
| Raw archives | `D:\battery_archive\battery_dataset_collection` | active raw source |
| Processed cache | `D:\battery_archive\processed_cache\by_cell_expansion_round1a` | large local cache |
| Project features | `data/features/...` | small generated tables, ignored by Git |
| Label audit | `outputs/label_audit/...` | local audit outputs, ignored by Git |
| Documentation | `docs/...` | tracked project record |

Large processed caches should stay outside Git and, when possible, outside the C
drive.

## What Has Been Completed

### Data Organization

- NASA `.mat` cells were preprocessed into project-local structures.
- External public battery archives were inventoried.
- External cycle-life data were extracted into by-cell processed caches.
- Large Round 1a/1b/1c processed caches were moved to or created on D drive.

### Feature And Label Pipeline

- Cycle-level features and RPT features were generated for earlier rounds.
- Multi-threshold health labels were generated.
- The project now separates `capacity_eol_75` and `capacity_eol_80`.
- Protocol boundary guardrails were added to prevent unreliable EOL crossings
  from entering trainable labels.
- RPT labels are excluded from training until RPT protocol-regime handling is
  solved.

### Label Audits

Completed audits show:

| Stage | `capacity_eol_75` strict candidates | `capacity_eol_80` strict candidates | Decision |
| --- | ---: | ---: | --- |
| after Round 1a | 5 | 10 | not enough |
| after Round 1b | 6 | 12 | EOL_80 passed, EOL_75 insufficient |

Round 1c extraction has been completed, but feature generation is paused until a
low-memory builder is validated.

### Exploratory Baseline Work

The project has run guarded exploratory LOCO baseline and diagnostics on earlier
baseline-ready data. Those results helped reveal:

- early false positives
- batch/part feature risk
- data scarcity
- label availability limitations

Those exploratory results are not formal performance claims.

## What Cannot Be Done Yet

The project should not yet:

- train a new model on Round 1c
- run Random Forest, XGBoost, SVM, MLP, or other stronger baselines
- run RUL regression
- use random row splits
- mix RPT labels into training
- claim that a complete intelligent battery system has been built
- claim formal prediction performance from label audits

Reason:

`capacity_eol_75` has not passed the minimum strict-candidate gate, and Round 1c
features still require a low-memory builder.

## Current Bottlenecks

### 1. `capacity_eol_75` Is Still Insufficient

Current completed audit:

```text
capacity_eol_75 = 6 strict candidates
capacity_eol_80 = 12 strict candidates
```

The working gate is:

```text
capacity_eol_75 >= 9
capacity_eol_80 >= 11
```

`capacity_eol_80` has passed. `capacity_eol_75` remains the main scientific
bottleneck.

### 2. Round 1c Needs Low-Memory Feature Generation

Round 1c processed data exist, but each per-cell cycle CSV is several GB. The
current full-table `pd.read_csv` path can exceed laptop memory.

The next technical requirement is a chunked feature builder that:

- reads large CSV files in chunks
- keeps output schema compatible with existing `cycle_features.csv` and
  `rpt_features.csv`
- validates against small known cases before processing Round 1c

### 3. Storage Is A Real Constraint

The project is now data-heavy. Large caches must be treated as local research
infrastructure, not Git assets. External SSD migration is a practical
requirement, not a cosmetic improvement.

## How To Explain This To An Advisor

A clear explanation:

> I started from the broader idea of an intelligent battery system, but I have
> narrowed the current research stage to the prognostics foundation. I am
> building a reproducible workflow for battery SOH/RUL labels, cycle-level
> features, and cross-cell validation. The current work has shown that EOL_80 is
> easier to observe, while EOL_75 remains limited by observation windows and
> protocol-boundary filtering. Before training stronger models, I am auditing
> whether the labels are scientifically reliable.

If asked what has been achieved:

> The main achievement so far is not a high model score. It is a reproducible
> data and label gate that distinguishes usable observed labels from censored or
> boundary-contaminated cases. This gives a safer foundation for later baseline
> modeling.

If asked why not train now:

> Training now would risk producing a number from weak labels. The EOL_75 gate is
> still below target, and Round 1c features need a memory-safe builder before the
> label audit can be completed.

## One-Week Practical Task List

### Day 1-2: Low-Memory Feature Builder

- design a chunked CSV feature builder
- test it on synthetic small data
- compare output schema against existing feature tables

### Day 3: Round 1c Feature Generation

- run the low-memory builder on Round 1c
- generate `cycle_features.csv` and `rpt_features.csv`
- record chunk size and row counts

### Day 4: Round 1c Labels And Audit

- generate default labels
- generate `min_obs=20` sensitivity labels
- merge audits across six/high/round1a/round1b/round1c
- check whether `capacity_eol_75 >= 9`

### Day 5: Review And Decision

- prepare a Trae review packet
- decide whether to continue EOL_75 expansion or allow a limited EOL_80-only
  exploratory baseline

### Day 6-7: Documentation Cleanup

- update path registry after external SSD arrives
- separate dashboard/visualization work from data pipeline work
- write a short label policy memo

## Codex And Trae Division

| Agent | Responsibility |
| --- | --- |
| Codex | local execution, scripts, manifests, feature/label generation, audit reports |
| Trae | scientific review, challenge assumptions, inspect label validity, judge next-step readiness |

Codex should not train models unless the label gates pass or the user explicitly
asks for a documented exploratory exception.

Trae should challenge whether the project is making a defensible scientific
claim rather than only producing more files.

## Immediate Next Step

Do not run more extraction.

The next useful action is:

> Implement and validate the low-memory feature builder, then use it to complete
> Round 1c feature generation and label audit.

This is a focused, realistic step that moves the project forward without
overloading the laptop or overstating results.
