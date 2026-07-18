# Resource-Aware Agent Workflow

This document defines a budget-aware collaboration workflow for the battery
life prediction project. The goal is to reduce repeated work, avoid accidental
large-data runs, and protect student-level usage budgets while preserving
scientific rigor.

These rules are active by default while the user has quota or cost pressure. If
the user later says the quota pressure is gone, these compression rules can be
relaxed.

## Core Principle

Use the most expensive local reasoning and execution only where it changes the
scientific or engineering decision.

The project should save effort by:

- checking manifests, reports, schemas, and summaries before touching raw data
- using tiny validation before full data runs
- separating drafting, execution, and review across agents
- avoiding repeated extraction or duplicate processed caches
- keeping model training behind explicit data gates

Saving quota must not mean lowering scientific standards.

## Team Roles

| Role | Best tasks | Avoid |
| --- | --- | --- |
| User | running long local commands, approving branch switches, checking disk/thermal limits, sharing Trae output | manually interpreting complex audit tables without support |
| Codex | local file inspection, code changes, unit tests, schema checks, manifests, reports, final gate decisions | broad literature drafting or repeated large-data scans |
| Trae | scientific critique, draft plans, risk review, prompt review, literature-direction brainstorming | local execution, final file verification, duplicate Codex work |

The default pattern is:

```text
Trae drafts or critiques -> Codex verifies locally -> user runs long commands when needed
```

## Tasks That Should Start With Trae

Use Trae first when the task is mainly scientific judgment or draft planning:

- deciding whether a label definition is scientifically defensible
- reviewing whether a threshold such as `capacity_eol_75` is too strict
- challenging whether a result may be a protocol artifact
- drafting advisor-facing explanations
- outlining literature themes or paper-reading priorities
- reviewing whether the next experiment is worthwhile
- checking if two proposed agents would duplicate work

Codex should then verify Trae's draft against local files, reports, and code
before accepting it as project state.

## Tasks That Should Go Directly To Codex

Use Codex directly when the task requires local repository state:

- checking `git status`
- reading manifests and report JSON files
- writing or updating scripts
- adding tests
- running unit tests
- validating schema compatibility
- generating small audit documents
- checking whether output files exist
- deciding whether a gate passed based on concrete local outputs

Codex should keep these responses compact unless the user explicitly asks for a
full explanation.

## Tasks The User Should Run Locally

The user should run long or resource-heavy commands when possible, then send the
result back for Codex to inspect.

Examples:

- full external archive extraction
- full Round 1c feature generation
- long label-audit merge jobs
- disk migration commands
- commands writing large files to `D:\battery_archive`
- operations that may heat the laptop or run for a long time

Codex should provide complete PowerShell commands, expected outputs, and stop
conditions. After the user runs them, Codex should inspect only the relevant
manifest/report/schema files.

## Big-Data Saving Rules

Before running a big-data task, check whether the result already exists.

Minimum checks:

- manifest exists
- selected/written/failed counts are plausible
- feature report exists
- schema check passes
- label summary exists
- audit report exists
- target row counts are documented

Do not repeat extraction just because the previous run is old. Repeat only when:

- inputs changed
- code changed in a way that affects the output
- a prior run failed or was interrupted
- the previous output lacks a required manifest or report
- the user explicitly asks for regeneration

For large tasks, the order is:

```text
design -> synthetic test -> tiny real slice -> full run -> audit -> gate decision
```

Never skip tiny validation for a new large-data path.

## Default Response Format

Unless the user asks for a detailed explanation, Codex should default to:

```text
Conclusion:
Evidence:
Risk:
Next step:
```

For implementation work, use:

```text
Changed:
Verified:
Blocked or risky:
Next command:
```

For Trae handoff prompts, use:

```text
Execution agent:
Role:
Task goal:
Inputs:
Strict rules:
Expected output:
Forbidden:
```

This keeps the project clear and saves quota.

## When Long Answers Are Worth It

Longer explanations are allowed when they directly support research quality:

- defining the scientific problem
- designing a method or validation protocol
- explaining label policy
- reading and synthesizing papers
- preparing advisor or group-meeting material
- making a major branch or architecture decision
- explaining a failed gate or a serious risk

Even then, the answer should separate conclusion from detail.

## Hard Prohibitions

The following are not allowed unless the user explicitly overrides them with a
documented reason:

- training models before data gates pass
- running stronger baselines without a gate review
- using random row splits for battery lifetime claims
- repeating large extraction without checking existing manifests
- creating duplicate processed caches
- letting Codex and Trae do the same task independently
- treating label audits as model performance
- treating tiny validation as a scientific result
- using RPT labels for training before protocol-regime assignment is solved

## Current Project-Specific Gates

The current external battery gate remains:

```text
capacity_eol_75 >= 9 strict candidates
capacity_eol_80 >= 11 strict candidates
```

`capacity_eol_80` is basically ready, but `capacity_eol_75` is still the key
constraint until Round 1c feature generation and audit are completed.

Round 1c must use the low-memory feature builder. Full-table `read_csv` on
multi-GB per-cell files is not acceptable on the current laptop.

## Practical Application

For the next phase:

1. Codex should finish code and tiny validation tasks.
2. The user should run any full Round 1c feature command locally if it is long.
3. Codex should inspect `feature_build_report.json`, `feature_schema_check.csv`,
   and label summaries after the run.
4. Trae should review whether the updated strict labels justify moving back to
   exploratory baseline design.

This workflow is not a downgrade. It is a disciplined way to spend compute,
quota, and attention only where they improve the research.
