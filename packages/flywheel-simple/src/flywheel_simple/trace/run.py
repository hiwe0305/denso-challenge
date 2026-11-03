"""Run SIMPLE's `eval-decoupled-wbc` with the trace hook installed (DA-38 task 3.3).

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src \
    FW_TRACE_JOB_DIR=fwdata/traces/<job_id> FW_JOB_ID=<job_id> \
    FW_RUN_PLAN_ID=g0-DA-38-20261105 FW_CAMERA_REFERENCE_SHA256=<pinned hash> \
        fwdata/simple/.venv/bin/python -m flywheel_simple.trace.run \
        simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0 psi0_decoupled_wbc \
        --data-format lerobot --data-dir <conditions> --sim-mode mujoco --headless ...

Arguments are those of SIMPLE's `eval-decoupled-wbc`. The job spec comes from the
environment, not from arguments: `--num-workers N` starts spawned workers, which
inherit the environment, import this module as `__mp_main__` and never run `main()`.
So the hook is installed on import under both names, and each worker writes the
traces of the episodes it runs under the same job directory.

`FW_CAMERA_REFERENCE_SHA256` is the camera reference pinned at G0 for the task
(`docs/g0/camera-reference-<task>.yaml`); without it no `camera_params.jsonl` is
written. The tray task's env id and condition reader are set up as in
`flywheel_simple.tray.run`.
"""

from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# flywheel.contracts.trace.G0_RUN_PLAN_ID (PO decision G2); SIMPLE's venv has no flywheel
G0_RUN_PLAN_ID = re.compile(r"^g0-[A-Z][A-Z0-9]*-[0-9]+-[0-9]{8}$")


@dataclass(frozen=True)
class JobSpec:
    job_dir: Path
    job_id: str
    run_plan_id: str
    camera_reference_sha256: str | None

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> JobSpec:
        required = ("FW_TRACE_JOB_DIR", "FW_JOB_ID", "FW_RUN_PLAN_ID")
        missing = [key for key in required if not environ.get(key)]
        if missing:
            raise ValueError(f"trace hook needs {', '.join(missing)} in the environment")
        run_plan_id = environ["FW_RUN_PLAN_ID"]
        if run_plan_id.startswith("g0-") and not G0_RUN_PLAN_ID.match(run_plan_id):
            raise ValueError(
                f"FW_RUN_PLAN_ID {run_plan_id!r} must read g0-<story>-<yyyymmdd>, "
                "for example g0-DA-38-20261105"
            )
        return cls(
            job_dir=Path(environ["FW_TRACE_JOB_DIR"]),
            job_id=environ["FW_JOB_ID"],
            run_plan_id=run_plan_id,
            camera_reference_sha256=environ.get("FW_CAMERA_REFERENCE_SHA256") or None,
        )


def simple_version() -> str:
    """HEAD of the imported SIMPLE checkout, for `RolloutResult.adapter_info.version`."""
    simple = importlib.import_module("simple")
    root = Path(str(simple.__file__)).resolve().parents[2]
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"simple@{head.stdout.strip()}"


def install_from_env(environ: Mapping[str, str]) -> JobSpec:
    from flywheel_simple.trace.files import EpisodeDirSink
    from flywheel_simple.trace.hook import TraceRecorder, install
    from flywheel_simple.tray.run import prepare

    spec = JobSpec.from_env(environ)
    prepare()
    psi0_decoupled_wbc = importlib.import_module("simple.baselines.psi0_decoupled_wbc")
    eval_decoupled_wbc = importlib.import_module("simple.cli.eval_decoupled_wbc")
    sink = EpisodeDirSink(
        spec.job_dir,
        job_id=spec.job_id,
        camera_reference_sha256=spec.camera_reference_sha256,
        adapter_version=simple_version(),
    )
    recorder = TraceRecorder(sink, run_plan_id=spec.run_plan_id, job_id=spec.job_id)
    install(eval_decoupled_wbc, psi0_decoupled_wbc, recorder)
    return spec


def main(argv: list[str]) -> int:
    sys.argv = ["eval-decoupled-wbc", *argv]
    importlib.import_module("simple.cli.eval_decoupled_wbc").typer_main()
    return 0


if __name__ in ("__main__", "__mp_main__"):
    install_from_env(os.environ)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
