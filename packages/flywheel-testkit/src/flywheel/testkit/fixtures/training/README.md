# Training telemetry examples

These synthetic examples illustrate possible signals; thresholds and detection
windows belong to DA-08. `action_layout.json` describes the two unmasked
dimensions in the training logs; use it for the T5 and T6 examples. The logs
are constructed to trigger their named code using the proposed thresholds in
DA-08 PR #32, which are assumptions pending calibration, not measured limits.
T4 uses two groups, while T3 has four validation measurements and T2 and T4
span the required 2000 steps. The examples are individual positive cases,
not a complete clean job or a substitute for the evaluation lane's tests.

`NaN` is a JSON string so the log remains valid JSON. Resume attempts start at
zero and increment for each restart; consumers must decide how to select
repeated measurements across attempts.
