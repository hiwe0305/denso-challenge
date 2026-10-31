# Training telemetry examples

These synthetic examples illustrate possible signals; thresholds and detection
windows belong to DA-08. The T5 example requires a separate action layout to
identify unmasked dimensions. `NaN` is a JSON string so the log remains valid
JSON. Resume attempts start at zero and increment for each restart; consumers
must decide how to select repeated measurements across attempts. These choices,
including `vlm_frozen` in each record, require review by the contract owner.
