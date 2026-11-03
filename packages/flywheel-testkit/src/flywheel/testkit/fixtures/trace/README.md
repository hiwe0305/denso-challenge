# Trace and Camera Parameter Fixtures for DA-13 (Issue #31)

This directory contains test fixtures for system fault detection (R3 tracking, R4 camera-state sync delay, R5 calibration offset, R6 infrastructure):

## Files

1. `clean.jsonl`: Clean rollout trace with 100 control cycles (50 Hz, `dt = 0.02s`). Camera frames rendered at 25 Hz (`t_image` present on even steps, `null` on odd steps). Upper body tracking error < 0.002 rad, lower body within 0.002 m and 0.002 rad. Paired with `camera_clean.json`.
2. `r4_sync_delay.jsonl`: Rollout trace where camera frames starting from step 20 experience a 120 ms sync delay (`t_state - t_image = 0.12s > tau_sync`), triggering fault R4 (LỆCH ĐỒNG BỘ).
3. `r5_calibration_offset.jsonl`: Clean motion trace, but paired with `camera_offset.json` where focal length and camera pitch angle diverge from nominal `reference_sha256` by > 10%, triggering fault R5 (LỆCH CALIBRATION).
4. `missing_signals.jsonl`: Trace representing data sources without lower body measurements (e.g. raw psi-data where `meas_lower` is `"NaN"`) and high dropped frame counts. Detectors must classify these as `CHƯA RÕ` rather than computing false tracking errors.
5. `camera_clean.json`: Nominal calibrated camera intrinsics (`fx=525`, `fy=525`, `cx=320`, `cy=240`) and pose quaternion `[0.05, 0.0, 0.15, 1.0, 0.0, 0.0, 0.0]` matching reference configuration.
6. `camera_offset.json`: Camera parameters with uncalibrated offset (`fx=580`, 15 degree pitch offset).

## Sparse Camera Recording Convention

Control loop operates at 50 Hz (`t_state` increments by `0.02s` every step). Camera sensors capture frames at 25 Hz.
- Steps with a newly rendered frame have `t_image` populated.
- Steps without a new camera frame have `t_image: null`. Reader implementations must treat `null` as "no measurement at this cycle" rather than duplicating old values or shifting step alignment.
