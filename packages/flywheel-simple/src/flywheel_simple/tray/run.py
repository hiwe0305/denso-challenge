"""Run SIMPLE's decoupled-WBC CLIs on the tray task without forking SIMPLE.

Registers the task and env id, then hands the remaining arguments to SIMPLE's
own command, as its console script would:

    MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
        -m flywheel_simple.tray.run teleop-decoupled-wbc \
        simple/G1WholebodyTrayTransferTeleop-v0 --sim-mode=mujoco

`replay-decoupled-wbc` runs on sim time (D-24): SIMPLE's replay agent and loop
read `time.monotonic()` and sleep to keep real time, and the WBC interpolates its
targets in that time, so the same recorded actions replayed differently on a
loaded machine (D-17). Their `time` module is swapped for one whose `monotonic`
is the live env's `mjData.time` and whose `sleep` returns at once, as
StandWalkController's control clock does when recording.

`eval-decoupled-wbc` runs on sim time too (decision of Hiếu 4/11/2026, DA-34
docs/he/tray.md section 8): replaying three S1 episodes through it passed 6/6 with
bit-identical repeats on sim time but 4/6 on the wall clock of a loaded rtx3060.
Its loop, the psi0 agent and the sonic WBC agent get the sim clock;
FLYWHEEL_TRAY_EVAL_CLOCK=wall keeps SIMPLE's wall clock. On reset the eval client
also sends the episode's condition seed as `history["seed"]`, so a Psi0 server can
seed its policy noise per episode (DA-34 docs/he/tray.md 8.5); servers ignore
unknown history keys.

`eval-decoupled-wbc --num-workers N` starts its workers with the spawn context.
A spawned worker imports this module as `__mp_main__` and never runs `main()`,
so the env id is registered and the eval patches are applied on that import too.
The command is unknown there (runpy sets `sys.argv[0]` to this file while it runs
the module); only eval starts workers.

`eval-decoupled-wbc --data-format lerobot` reads each condition with SIMPLE's
`get_episode_lerobot`, which rewrites `environment_config["dr_state_dict"]`'s
scene uid (a FIXME for its hssd scenes). Tray conditions have no `dr_state_dict`:
the tray env rebuilds the episode from the seed and level it recorded. The
function is swapped, in the parent and in spawned workers, for one that skips
that rewrite when the key is missing, and that decodes an episode's frames only
when one is read: SIMPLE's loads every frame (about 8 GB for a tray episode with
video) though only policy `vlt` uses them.
"""

from __future__ import annotations

import functools
import importlib
import json
import os
import sys
import time
from collections.abc import Callable, Sequence
from typing import Any

COMMANDS = {
    "teleop-decoupled-wbc": "simple.cli.teleop_decoupled_wbc",
    "eval-decoupled-wbc": "simple.cli.eval_decoupled_wbc",
    "replay-decoupled-wbc": "simple.cli.replay_decoupled_wbc",
}
SIM_TIME_MODULES = {
    "replay-decoupled-wbc": (
        "simple.agents.replay_decoupled_agent",
        "simple.cli.replay_decoupled_wbc",
    ),
    "eval-decoupled-wbc": (
        "simple.cli.eval_decoupled_wbc",
        "simple.baselines.psi0_decoupled_wbc",
        "simple.agents.sonic_decoupled_wbc_agent",
    ),
}
EVAL_CLOCK_ENV = "FLYWHEEL_TRAY_EVAL_CLOCK"  # "sim" (default) or "wall"


class SimTime:
    """Stand-in for the `time` module: monotonic() is sim time, sleep() does not wait."""

    def monotonic(self) -> float:
        from flywheel_simple.tray.simple_task import live_env

        env = live_env()
        if env is None:
            return time.monotonic()
        data = getattr(env, "mjData", None)  # set on the first reset; the agent reads before it
        return float(data.time) if data is not None else 0.0

    def sleep(self, seconds: float) -> None:
        del seconds

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)


def use_sim_time(module_names: tuple[str, ...]) -> None:
    for name in module_names:
        importlib.import_module(name).time = SimTime()  # type: ignore[attr-defined]


class EpisodeFrames(Sequence[Any]):
    """The frames dataset[start:stop] of one episode, each decoded when it is read."""

    def __init__(self, dataset: Any, start: int, stop: int) -> None:
        self.dataset, self.start, self.stop = dataset, start, stop

    def __len__(self) -> int:
        return self.stop - self.start

    def __getitem__(self, i: Any) -> Any:
        if isinstance(i, slice):
            return [self[j] for j in range(*i.indices(len(self)))]
        if not -len(self) <= i < len(self):
            raise IndexError(i)
        return self.dataset[self.start + i % len(self)]


def get_episode_lerobot(
    dataset: Any, eps_idx: int, data_format: Any = None
) -> tuple[dict[str, Any], EpisodeFrames]:
    """SIMPLE's `simple.datasets.lerobot.get_episode_lerobot` (@ 6d10628), whose scene
    uid rewrite applies only to conditions that have `dr_state_dict` and whose frames
    are decoded on access."""

    def _to_int(value: Any) -> int:
        item = getattr(value, "item", None)
        if callable(item):
            return int(item())
        return int(value)

    from_idx = _to_int(dataset.episode_data_index["from"][eps_idx])
    to_idx = _to_int(dataset.episode_data_index["to"][eps_idx])
    episode = EpisodeFrames(dataset, from_idx, to_idx)

    env_conf: dict[str, Any] = json.loads(dataset.meta.episodes[eps_idx]["environment_config"])
    if "dr_state_dict" in env_conf:
        scene = env_conf["dr_state_dict"]["scene"]
        scene["uid"] = scene["uid"].replace("102344280", "scene3")
    return env_conf, episode


def prepare() -> None:
    """Register the tray env id and swap SIMPLE's condition reader; safe to call again."""
    from flywheel_simple.tray.simple_task import register

    register()
    lerobot = importlib.import_module("simple.datasets.lerobot")
    lerobot.get_episode_lerobot = get_episode_lerobot  # type: ignore[attr-defined]


def eval_clock() -> str:
    clock = os.environ.get(EVAL_CLOCK_ENV, "sim")
    if clock not in ("sim", "wall"):
        raise ValueError(f"{EVAL_CLOCK_ENV} must be sim or wall, not {clock!r}")
    return clock


def condition_seed() -> int | None:
    """The condition seed of the live tray env's current episode, once it was reset."""
    from flywheel_simple.tray.simple_task import live_env

    sample = getattr(getattr(live_env(), "task", None), "sample", None)
    return None if sample is None else int(sample.seed)


def with_condition_seed(query_action: Callable[..., Any]) -> Callable[..., Any]:
    """HttpActionClient.query_action that adds the condition seed to a reset request."""

    @functools.wraps(query_action)
    def query(
        self: Any,
        image_dict: Any,
        instruction: Any,
        state_dict: Any,
        condition_dict: Any,
        history: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if history and "reset" in history and (seed := condition_seed()) is not None:
            history = {**history, "seed": seed}
        return query_action(
            self, image_dict, instruction, state_dict, condition_dict, history, *args, **kwargs
        )

    query.flywheel_condition_seed = True  # type: ignore[attr-defined]
    return query


def prepare_eval() -> None:
    """Sim clock (unless FLYWHEEL_TRAY_EVAL_CLOCK=wall) and the seeded reset for eval."""
    if eval_clock() == "sim":
        use_sim_time(SIM_TIME_MODULES["eval-decoupled-wbc"])
    client = importlib.import_module("simple.baselines.client").HttpActionClient
    if not getattr(client.query_action, "flywheel_condition_seed", False):
        client.query_action = with_condition_seed(client.query_action)


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: run {{{','.join(COMMANDS)}}} [args...]", file=sys.stderr)
        return 2
    prepare()
    command, rest = argv[0], argv[1:]
    if command == "eval-decoupled-wbc":
        prepare_eval()
    else:
        use_sim_time(SIM_TIME_MODULES.get(command, ()))
    sys.argv = [command, *rest]
    importlib.import_module(COMMANDS[command]).typer_main()
    return 0


if __name__ == "__mp_main__":  # only eval-decoupled-wbc spawns workers
    prepare()
    prepare_eval()

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
