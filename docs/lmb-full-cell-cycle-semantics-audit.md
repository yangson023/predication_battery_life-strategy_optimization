# LMB Full-Cell BTSDA Cycle Semantics Audit

Before a full-cell BTSDA export enters feature engineering, inspect whether its
exported `循环号` means one physical charge/discharge cycle. It may instead
contain formation steps, protocol transitions, multiple charge/discharge pairs,
or an export-specific counter.

Use `modules/data_pipeline/audit_btsda_full_cell_cycle_semantics.py` first.
It reports complete charge/discharge pairing, step-pattern regimes, and the
relationship to the experiment-recorded planned cycle count.

If the count is not aligned, do not use `循环号` as a lifetime index, EOL index,
or horizon coordinate. Obtain the BTS XML or experiment log and create an
explicit mapping first.

This is a schema and protocol audit only:

```text
model_training_allowed=False
```

## 2026-07-10 Full-Cell XML Evidence

Two NCM811 protocol XML files were reviewed locally. Both define an initial
12-hour rest, a short loop of three charge/discharge cycles, then a long-cycle
loop with an upper limit of 500 cycles. The XML loop maximum is not a recorded
termination reason.

| XML protocol | Short-loop current | Long-loop current | Voltage cutoffs | Current data match |
| --- | --- | --- | --- | --- |
| stale filename `9.8 mm`; actual LHCE 1.2 cm, 0.2C charge / 0.5C discharge | 0.281 mA charge/discharge | 0.562 mA charge; 1.406 mA discharge | 4.20 / 2.70 V | Partner confirmed this XML belongs to `26-0610-1 LHCE`; the filename geometry was not updated. |
| 12 mm, 0.5C charge / 0.5C discharge | 0.281 mA charge/discharge | 1.406 mA charge/discharge | 4.20 / 2.70 V | `26-0610 LB-085` record currents match. |

`26-0602 LB-085` uses a 0.98 cm cathode. Its protocol is derived by scaling the
LHCE XML current values by the electrode-area ratio `(0.98 / 1.20)^2 =
0.666944`: 0.281/0.562/1.406 mA become approximately
0.187/0.375/0.938 mA, consistent with its observed 0.182/0.365/0.911 mA.

Therefore, no present export may be labelled `protocol_censored` merely because
it ended before the XML's long-loop maximum. The partner or lab log must state
whether termination was intentional, ongoing export, device interruption, or
observed failure.

## Current Use Decision

The `26-0610-1 LHCE` batch is retained as a true-LMB failure-statistics and
anomaly case only. Per partner decision, it is excluded from the current
full-cell feature table, label audit, and model-development mainline. Its raw
data and protocol audit remain archived for later failure-mechanism review.
