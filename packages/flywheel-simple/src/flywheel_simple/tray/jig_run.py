"""`flywheel_simple.tray.run` on DA-41's jig scene: registers the jig env id too.

`run` registers only DA-33's tray env. Replaying an episode recorded in the jig
scene through it rebuilds the episode in that scene instead (no jig, target
jittered): SIMPLE warns "env/dataset task mismatch" and overrides the uid, and the
replay judges the episode against the wrong target. This module registers
`jig_task.JIG_ENV_ID`, then hands the arguments to `run.main`:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m flywheel_simple.tray.jig_run replay-decoupled-wbc \
        simple/G1WholebodyTrayTransferJigTeleop-v0 --data-dir <raw> --sim-mode mujoco ...

A spawned eval worker imports this module as `__mp_main__` (see `run`), so the
jig env id is registered there too.
"""

from __future__ import annotations

import sys

from flywheel_simple.tray import run


def prepare() -> None:
    """`run.prepare` plus the jig env id; safe to call again."""
    from flywheel_simple.tray.jig_task import register

    run.prepare()
    register()


def main(argv: list[str]) -> int:
    prepare()
    return run.main(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

if __name__ == "__mp_main__":
    prepare()
