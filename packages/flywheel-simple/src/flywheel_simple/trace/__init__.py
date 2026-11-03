"""Trace hook for SIMPLE rollouts (DA-38): per-cycle `TraceStep` and per-episode `CameraParams`.

`signals` and `camera` are pure numpy and run in workspace CI; the hook that reads
MuJoCo inside SIMPLE's `eval-decoupled-wbc` imports `simple` only inside functions.
"""
