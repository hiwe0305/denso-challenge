"""Configuration of the data lane."""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from flywheel.contracts.artifacts import ActionLayout

# 03 section 8.1: $FW_ROOT, by default ./fwdata, holds sources, releases and runs.
DEFAULT_STORE = Path("fwdata")


def store_root() -> Path:
    """The store root: $FW_ROOT when set, else ./fwdata, as an absolute path."""
    return Path(os.environ.get("FW_ROOT") or DEFAULT_STORE).resolve()


# --- QA thresholds: configs/data/qa.yaml (DA-03 AC 3) ---------------------------------
#
# Every key is required and no key has a default here: a threshold the file does not
# name is an error, not a value the code guesses (spec 4.4, design 10: thresholds live
# in configs/ with a hash). `threshold_version` of every QAReport is the file's
# `version` and the first 12 hex of the sha256 of the bytes that were parsed.

QADecision = Literal["pass", "flag", "quarantine", "reject"]
FAIL_ACTIONS = ("flag", "quarantine", "reject")
D_CODES = tuple(f"D{i}" for i in range(1, 9))
WHEN_MISSING = ("skip", "flag")
LINEAGE_FIELDS = ("source_id", "license", "seed", "generator_version", "parent_id")
# Checks run on every episode; a source adds its own from `source_checks`.
COMMON_CHECKS = (
    "timestamp_monotonic",
    "timestamp_step",
    "frame_index_contiguous",
    "image_state_sync",
    "finite_values",
    "joint_limits",
    "action_jump",
    "lineage",
    "replay_kinematic",
    "replay_dynamic",
    "split_seed",
)
SOURCE_CHECKS = ("video_rows_match", "task_instruction", "task_success", "replay_success")
REPLAY_CHECKS = ("replay_kinematic", "replay_dynamic", "task_success", "replay_success")
DATASET_CHECKS = ("stats_json", "episodes_stats")


class ConfigError(ValueError):
    """A QA config that is missing a key, has an unknown one, or a value of the wrong kind."""


@dataclass(frozen=True)
class CheckRule:
    code: str  # design 10 D-code
    threshold: float  # fails when the measured value is above it; unused by action_jump
    on_fail: QADecision
    when_missing: str | None = None  # replay checks: "skip" or "flag" without a ReplayReport


@dataclass(frozen=True)
class QAConfig:
    version: str
    sha256: str  # of the qa.yaml bytes parsed
    min_frames: int
    checks: dict[str, CheckRule]  # every name of COMMON_CHECKS, SOURCE_CHECKS, DATASET_CHECKS
    action_jump: dict[str, float]  # action group -> largest |a[t+1] - a[t]| of a clean demo
    action_jump_quantile: float
    action_jump_calibration: str  # where the action_jump thresholds were measured
    action_jump_wrapped: tuple[str, ...]  # groups that are angles: jumps go the short way
    source_checks: dict[str, tuple[str, ...]]  # source_detail -> extra checks
    lineage_required: dict[str, tuple[str, ...]]  # source_detail -> fields an episode needs
    groups: tuple[str, ...]  # action group of each of the 36 dims, from the ActionLayout
    limits: tuple[tuple[float, float] | None, ...]  # per dim, None: the layout has none
    train_seeds: tuple[int, int]  # [start, stop) of the train range of the SplitPlan

    @property
    def threshold_version(self) -> str:
        return f"{self.version}@{self.sha256[:12]}"


def load_qa_config(path: Path, layout: ActionLayout, split_plan: Path) -> QAConfig:
    """Read qa.yaml; the action layout gives groups and joint limits, the SplitPlan the
    train seed range (configs/splits/default.yaml)."""
    raw = _read(path)
    data = _mapping(_parse(raw, path), str(path))
    _exact_keys(data, ("version", "min_frames", "checks", "action_jump", "source_checks",
                       "lineage_required"), str(path))
    checks_raw = _mapping(data["checks"], "checks")
    _exact_keys(checks_raw, (*COMMON_CHECKS, *SOURCE_CHECKS, *DATASET_CHECKS), "checks")
    checks = {name: _rule(name, value) for name, value in checks_raw.items()}
    jump = _mapping(data["action_jump"], "action_jump")
    _exact_keys(jump, ("quantile", "calibration", "wrapped", "thresholds"), "action_jump")
    groups = tuple(dim.group for dim in layout.dimensions)
    thresholds = _mapping(jump["thresholds"], "action_jump.thresholds")
    _exact_keys(thresholds, tuple(dict.fromkeys(groups)), "action_jump.thresholds")
    sources = _mapping(data["source_checks"], "source_checks")
    lineage = _mapping(data["lineage_required"], "lineage_required")
    _exact_keys(lineage, tuple(sources), "lineage_required")
    return QAConfig(
        version=_text(data["version"], "version"),
        sha256=hashlib.sha256(raw).hexdigest(),
        min_frames=_integer(data["min_frames"], "min_frames"),
        checks=checks,
        action_jump={g: _number(v, f"action_jump.thresholds.{g}") for g, v in thresholds.items()},
        action_jump_quantile=_number(jump["quantile"], "action_jump.quantile"),
        action_jump_calibration=_text(jump["calibration"], "action_jump.calibration"),
        action_jump_wrapped=_names(jump["wrapped"], groups, "action_jump.wrapped"),
        source_checks={s: _names(v, SOURCE_CHECKS, f"source_checks.{s}")
                       for s, v in sources.items()},
        lineage_required={s: _names(v, LINEAGE_FIELDS, f"lineage_required.{s}")
                          for s, v in lineage.items()},
        groups=groups,
        limits=tuple(
            None if d.limit_low is None or d.limit_high is None else (d.limit_low, d.limit_high)
            for d in layout.dimensions
        ),
        train_seeds=load_train_seeds(split_plan),
    )


def load_layout(embodiment: Path) -> ActionLayout:
    """The `action_layout` of an embodiment config (configs/embodiments/g1.yaml)."""
    data = _mapping(_parse(_read(embodiment), embodiment), str(embodiment))
    if "action_layout" not in data:
        raise ConfigError(f"{embodiment}: no action_layout")
    return ActionLayout.model_validate(data["action_layout"])


def load_train_seeds(split_plan: Path) -> tuple[int, int]:
    """[start, stop) of the train seed range of a SplitPlan."""
    data = _mapping(_parse(_read(split_plan), split_plan), str(split_plan))
    try:
        train = data["seed_ranges"]["train"]
        return int(train["start"]), int(train["stop"])
    except (KeyError, TypeError) as error:
        raise ConfigError(f"{split_plan}: no seed_ranges.train start and stop") from error


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise ConfigError(f"{path}: cannot be read: {error}") from error


def _parse(raw: bytes, path: Path) -> Any:
    try:
        return yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ConfigError(f"{path}: not YAML: {error}") from error


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{where} must be a mapping, got {type(value).__name__}")
    return value


def _exact_keys(data: dict[str, Any], expected: tuple[str, ...], where: str) -> None:
    missing = [k for k in expected if k not in data]
    unknown = [k for k in data if k not in expected]
    if missing or unknown:
        raise ConfigError(f"{where}: missing {missing}, unknown {unknown}")


def _rule(name: str, value: Any) -> CheckRule:
    rule = _mapping(value, f"checks.{name}")
    # action_jump has one threshold per action group, in the action_jump section.
    keys = ("code", "on_fail") + (() if name == "action_jump" else ("threshold",))
    keys += ("when_missing",) if name in REPLAY_CHECKS else ()
    _exact_keys(rule, keys, f"checks.{name}")
    code = _text(rule["code"], f"checks.{name}.code")
    if code not in D_CODES:
        raise ConfigError(f"checks.{name}.code {code!r} is not one of {D_CODES} (design 10)")
    action = rule["on_fail"]
    if action not in FAIL_ACTIONS:
        raise ConfigError(f"checks.{name}.on_fail {action!r} is not one of {FAIL_ACTIONS}")
    missing = rule.get("when_missing")
    if name in REPLAY_CHECKS and missing not in WHEN_MISSING:
        raise ConfigError(f"checks.{name}.when_missing {missing!r} is not one of {WHEN_MISSING}")
    where = f"checks.{name}.threshold"
    threshold = 0.0 if name == "action_jump" else _number(rule["threshold"], where)
    return CheckRule(code, threshold, cast(QADecision, action), missing)


def _names(value: Any, allowed: tuple[str, ...], where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{where} must be a list of names")
    unknown = [v for v in value if v not in allowed]
    if unknown:
        raise ConfigError(f"{where}: {unknown} not among {allowed}")
    return tuple(value)


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where} must be a non-empty string")
    return value


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ConfigError(f"{where} must be a finite number, got {value!r}")
    return float(value)


def _integer(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{where} must be an integer, got {value!r}")
    return value
