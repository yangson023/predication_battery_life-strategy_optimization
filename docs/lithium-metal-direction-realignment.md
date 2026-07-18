# Lithium Metal Battery Direction Realignment

This document corrects the project direction after advisor feedback. The main
research object is lithium metal batteries, not conventional lithium-ion
batteries.

## Conclusion

The project is still viable.

Most completed work belongs to reusable battery prognostics infrastructure:

```text
raw data -> processed cache -> features -> health labels -> label audit -> baseline gate
```

That infrastructure can transfer to lithium metal battery research. However,
the scientific claims must be realigned. Existing lithium-ion datasets and
outputs are method-development assets, not lithium metal battery conclusions.

## What Changed

Previous working assumption:

> The first research target was general lithium-ion battery lifetime prediction.

Corrected research target:

> The project should focus on lithium metal battery lifetime prediction and
> strategy optimization, with special attention to lithium-metal-specific
> degradation, instability, and safety indicators.

This correction matters because lithium metal batteries have different dominant
failure mechanisms and different useful features.

## What Remains Useful

The following work remains valuable:

| Existing asset | Why it still matters |
| --- | --- |
| Data provenance and manifest tracking | Lithium metal experiments also need traceable cell/protocol/source records |
| Low-memory CSV feature builder | Large experimental logs still need chunked processing |
| Feature/label separation | Lithium metal labels also need explicit definitions before training |
| Observed vs censored label handling | Many lithium metal cells may not reach a clean EOL in a finite window |
| Protocol-boundary guard | Lithium metal cells are highly protocol-sensitive |
| Leave-one-cell-out thinking | Cross-cell generalization remains the correct validation direction |
| Label audit before modeling | Prevents training on unstable or weakly defined outcomes |
| Codex/Trae workflow | Still useful for budget-aware research execution |

These are not wasted effort. They are the reusable foundation.

## What Must Be Reinterpreted

The current external lithium-ion datasets should be described as:

- pipeline validation data
- feature-engineering stress tests
- label-audit prototypes
- baseline-method rehearsal data
- possible pretraining or transfer-learning reference, only with clear caveats

They should not be described as:

- final lithium metal battery evidence
- proof of lithium metal lifetime prediction performance
- sufficient data for lithium metal strategy optimization

## Lithium-Metal-Specific Variables To Add

Future lithium metal datasets should prioritize fields that reflect plating,
stripping, interface stability, and short-circuit risk.

| Category | Important variables |
| --- | --- |
| Cell design | lithium metal type, anode-free or Li-metal excess, N/P ratio, areal capacity, cathode loading |
| Electrolyte/interface | electrolyte formulation, salt, solvent, additive, SEI strategy, artificial interphase |
| Protocol | current density, areal capacity per cycle, charge/discharge cutoff, rest time, stack pressure if available |
| Coulombic behavior | Coulombic efficiency, CE trend, CE variance, sustained CE drop |
| Voltage behavior | overpotential, voltage hysteresis, nucleation overpotential, plateau shape, polarization growth |
| Capacity behavior | discharge capacity, charge capacity, capacity retention, irreversible capacity |
| Impedance/diagnostics | EIS, DCIR, pulse response, relaxation behavior if available |
| Safety/instability | soft-short indicators, sudden voltage drop, abnormal self-discharge, noisy voltage signatures |

## Label System Changes

Capacity EOL labels remain useful, but they are not enough for lithium metal
batteries.

Future label families should include:

| Label family | Example meaning |
| --- | --- |
| Capacity EOL | capacity retention drops below a threshold |
| CE failure | CE falls below or fluctuates beyond a defined stability threshold |
| Polarization failure | overpotential or hysteresis exceeds a threshold |
| Soft-short warning | voltage instability or abnormal self-discharge indicates possible shorting |
| Protocol-limited censoring | cell did not fail, but experiment ended or protocol changed |

Every label must specify:

- threshold
- observation window
- sustained-crossing rule
- censoring handling
- protocol regime
- whether it is a training label or audit-only diagnostic

## Revised Research Statement

The corrected project statement is:

> This project develops a reproducible lithium metal battery prognostics and
> strategy-optimization foundation. The immediate goal is to build reliable data
> processing, feature extraction, label auditing, and validation protocols. The
> current lithium-ion datasets are used only to prototype and stress-test the
> workflow before lithium-metal-specific data and labels are introduced.

## Advisor Explanation

A concise explanation:

> I found that the correct target is lithium metal batteries. Fortunately, the
> current work has mostly been infrastructure: data organization, feature
> building, label auditing, and validation rules. I will now treat the lithium-ion
> data as method-development data only, and shift the scientific feature and
> label definitions toward lithium metal mechanisms such as Coulombic efficiency,
> overpotential, polarization, plating/stripping behavior, and soft-short risk.

If asked whether previous work was wasted:

> No. The previous work built the pipeline needed before modeling. What changes
> is the scientific interpretation and the next data requirements.

## Immediate Action Plan

1. Update project docs so the final research object is lithium metal battery.
2. Keep existing lithium-ion feature work as pipeline validation only.
3. Create a lithium-metal feature and label requirements table.
4. Ask the advisor what lithium metal data fields are available from the lab.
5. Before any model training, verify whether lithium-metal-specific labels can
   be constructed from the available experimental logs.

## Agent Reminder

Codex and Trae must not default to lithium-ion as the final research object.

Allowed phrasing:

- lithium-ion data as pipeline validation
- lithium metal battery as the target system
- lithium-metal-specific labels and features
- no final LMB claim from Li-ion-only data

Forbidden phrasing:

- final lithium metal performance from current Li-ion data
- complete intelligent lithium metal system already built
- capacity-only labels are sufficient for LMB without justification
