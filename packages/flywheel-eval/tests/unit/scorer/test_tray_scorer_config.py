"""The tray scorer config reads the numbers of the tray task (DA-36 task 9.1, AC 8).

`configs/eval/scorer/tray.yaml` copies its thresholds from
`configs/sim/tray.yaml`, the file the DA-32 predicates and `check_success()`
read. A copy drifts, so this test holds every copied number to its source:
change a tolerance of the task and this fails until the scorer config follows.
The sim file is flat `key: number` lines and is read here as text, so the
lane imports nothing of `flywheel-simple` (03 section 7.3).
"""

from __future__ import annotations

from pathlib import Path

from flywheel.eval.api import SCORER_CONFIG_DIR
from flywheel.eval.config import load_scorer_config

TRAY = SCORER_CONFIG_DIR / "tray.yaml"
SIM = Path("configs") / "sim" / "tray.yaml"


def sim_numbers() -> dict[str, float]:
    numbers: dict[str, float] = {}
    for line in SIM.read_text(encoding="utf-8").splitlines():
        text = line.split("#", 1)[0].strip()
        if not text:
            continue
        key, value = (part.strip() for part in text.split(":", 1))
        numbers[key] = float(value)
    return numbers


def test_every_threshold_is_the_tray_task_s_own_number() -> None:
    config, _ = load_scorer_config(TRAY)
    sim = sim_numbers()

    assert set(config.thresholds) <= set(sim), sorted(set(config.thresholds) - set(sim))
    for key, value in config.thresholds.items():
        assert value == sim[key], key


def test_the_fall_height_is_the_tray_task_s_own() -> None:
    config, _ = load_scorer_config(TRAY)

    assert config.balance.min_height == sim_numbers()["fall_height"]
    assert config.balance.height_signal == "pelvis_height"


def test_the_tray_config_is_its_own_task_s() -> None:
    config, digest = load_scorer_config(TRAY)
    two_table, other = load_scorer_config(SCORER_CONFIG_DIR / "two-table.yaml")

    assert config.task_id == "tray"
    assert config.scorer_version == two_table.scorer_version
    assert config.episode_signals == ("collision",)
    assert digest != other
