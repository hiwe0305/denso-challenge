"""Run SIMPLE's decoupled-WBC CLIs on the tray task without forking SIMPLE.

Registers the task and env id, then hands the remaining arguments to SIMPLE's
own command, as its console script would:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m flywheel_simple.tray.run teleop-decoupled-wbc \
        simple/G1WholebodyTrayTransferTeleop-v0 --sim-mode=mujoco
"""

from __future__ import annotations

import importlib
import sys

COMMANDS = {
    "teleop-decoupled-wbc": "simple.cli.teleop_decoupled_wbc",
    "eval-decoupled-wbc": "simple.cli.eval_decoupled_wbc",
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: run {{{','.join(COMMANDS)}}} [args...]", file=sys.stderr)
        return 2
    from flywheel_simple.tray.simple_task import register

    register()
    command, rest = argv[0], argv[1:]
    sys.argv = [command, *rest]
    importlib.import_module(COMMANDS[command]).typer_main()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
