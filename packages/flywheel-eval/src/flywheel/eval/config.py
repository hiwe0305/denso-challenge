"""Thresholds of the evaluation lane, read from `configs/eval/diagnosis/` (DA-08 AC 3).

Two rules hold this module together. No threshold has a default in code: a key
missing from the config file raises, so a detector can never quietly compare
against a number nobody wrote down. And every result artifact carries
`config_sha256` of the file it ran on (AC 4), which is what lets a finding be
reproduced later, or be told apart from a finding made under other thresholds.

`load_train_thresholds` hashes the same bytes it parses, so the hash in an
artifact can only ever name the file that run actually read. Validation lives in
`from_mapping`, which takes a parsed mapping and knows nothing about the file
format.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """A threshold file a detector must not run on."""


@dataclass(frozen=True)
class BalanceLimits:
    """Which signals bound the body, and by how much (configured, never in code).

    It lives in this module rather than beside the check that uses it so the
    imports run one way only: every scorer module reads `config`, and `config`
    reads no scorer module.
    """

    min_height: float
    max_tilt: float
    height_signal: str
    tilt_signal: str

    def signals(self) -> tuple[str, ...]:
        return (self.height_signal, self.tilt_signal)


@dataclass(frozen=True)
class T1Thresholds:
    """Divergence: loss over `k` times the window minimum, or not finite at all."""

    k: float
    window_steps: int


@dataclass(frozen=True)
class T2Thresholds:
    """No learning: val loss still near its baseline after `n_steps`."""

    n_steps: int
    min_relative_drop: float
    baseline_val_count: int


@dataclass(frozen=True)
class T3Thresholds:
    """Overfitting: val loss up over `m_measurements` while smoothed train loss falls."""

    m_measurements: int


@dataclass(frozen=True)
class T4Thresholds:
    """Group imbalance: one action group barely improves while another does."""

    window_steps: int
    min_group_drop: float
    ref_group_drop: float


@dataclass(frozen=True)
class T5Thresholds:
    """Dead dimension: prediction variance under `epsilon` on an unmasked dimension."""

    window_steps: int
    epsilon: float


@dataclass(frozen=True)
class T6Thresholds:
    """Mode collapse: predicted std far under the target std of the same dimension."""

    min_std_ratio: float


@dataclass(frozen=True)
class T7Thresholds:
    """Forgetting: a probe score of the child checkpoint below its parent."""

    max_relative_drop: float


@dataclass(frozen=True)
class T8Thresholds:
    """Gradient faults: gradient on a frozen VLM, or repeated action-head spikes."""

    frozen_tolerance: float
    max_grad_norm: float
    max_exceedances: int


@dataclass(frozen=True)
class O1Thresholds:
    """Offline error of one action group, against its own budget or the group median."""

    max_error_by_group: dict[str, float]
    max_error_ratio: float


@dataclass(frozen=True)
class O2Thresholds:
    """Offline error growing along the action chunk."""

    max_slope: float
    max_ratio: float


@dataclass(frozen=True)
class O3Thresholds:
    """Hand events landing off the demonstrated step."""

    max_offset_steps: int


@dataclass(frozen=True)
class O4Thresholds:
    """Predicted actions outside the joint limits of the embodiment."""

    max_fraction: float


@dataclass(frozen=True)
class TrainThresholds:
    """Every threshold the F-TRAIN and F-OFF detectors of DA-08 read."""

    t1: T1Thresholds
    t2: T2Thresholds
    t3: T3Thresholds
    t4: T4Thresholds
    t5: T5Thresholds
    t6: T6Thresholds
    t7: T7Thresholds
    t8: T8Thresholds
    o1: O1Thresholds
    o2: O2Thresholds
    o3: O3Thresholds
    o4: O4Thresholds

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> TrainThresholds:
        """Validate a parsed threshold mapping; raise `ConfigError` on anything unclear."""
        _reject_unknown(data, tuple(cls.__dataclass_fields__), "train.yaml")
        t1, t2, t3, t4 = (_section(data, name) for name in ("t1", "t2", "t3", "t4"))
        t5, t6, t7, t8 = (_section(data, name) for name in ("t5", "t6", "t7", "t8"))
        o1, o2, o3, o4 = (_section(data, name) for name in ("o1", "o2", "o3", "o4"))
        return cls(
            t1=T1Thresholds(
                k=_number(t1, "k", "t1"),
                window_steps=_steps(t1, "window_steps", "t1"),
            ),
            t2=T2Thresholds(
                n_steps=_steps(t2, "n_steps", "t2"),
                min_relative_drop=_number(t2, "min_relative_drop", "t2"),
                baseline_val_count=_steps(t2, "baseline_val_count", "t2"),
            ),
            t3=T3Thresholds(m_measurements=_steps(t3, "m_measurements", "t3")),
            t4=T4Thresholds(
                window_steps=_steps(t4, "window_steps", "t4"),
                min_group_drop=_number(t4, "min_group_drop", "t4"),
                ref_group_drop=_number(t4, "ref_group_drop", "t4"),
            ),
            t5=T5Thresholds(
                window_steps=_steps(t5, "window_steps", "t5"),
                epsilon=_number(t5, "epsilon", "t5"),
            ),
            t6=T6Thresholds(min_std_ratio=_number(t6, "min_std_ratio", "t6")),
            t7=T7Thresholds(max_relative_drop=_number(t7, "max_relative_drop", "t7")),
            t8=T8Thresholds(
                frozen_tolerance=_number(t8, "frozen_tolerance", "t8"),
                max_grad_norm=_number(t8, "max_grad_norm", "t8"),
                max_exceedances=_steps(t8, "max_exceedances", "t8"),
            ),
            o1=O1Thresholds(
                max_error_by_group=_number_map(o1, "max_error_by_group", "o1"),
                max_error_ratio=_number(o1, "max_error_ratio", "o1"),
            ),
            o2=O2Thresholds(
                max_slope=_number(o2, "max_slope", "o2"),
                max_ratio=_number(o2, "max_ratio", "o2"),
            ),
            o3=O3Thresholds(max_offset_steps=_steps(o3, "max_offset_steps", "o3")),
            o4=O4Thresholds(max_fraction=_number(o4, "max_fraction", "o4")),
        )


@dataclass(frozen=True)
class ScorerConfig:
    """What `configs/eval/scorer/<task>.yaml` tells the scorer (DA-36 AC 5).

    `thresholds` is passed through to `TaskDefinition.evaluate()` untouched. The
    scorer reads no key of it: which predicate needs `r_reach` and which needs
    `T_stable` is the task's business, and a scorer that knew would be a scorer
    with one task's steps baked into it.

    `task_id` is checked against the task being scored, so a tray config cannot
    be used to score a two-table episode and quietly supply the wrong numbers.

    `step_signals` says which signals each step is judged on, and it is what
    lets the scorer hold the "chưa rõ" convention of AC 2 itself instead of
    trusting the task to hold it. Without it, a task that returns `True` for a
    step whose signal was never recorded scores as a pass and one that returns
    `False` scores as a failure, and spec section 5.1 says neither. `StageSpec`
    carries no signal list, so the declaration lives in config until it reaches
    the contract (Contract change #59); either way it is per task, so no task's
    steps are written in code.

    `episode_signals` are the signals no single step owns - the collision flag
    of the two-table task - and a missing one costs a clean episode its pass
    rather than one step its verdict. `class_from_failed_step` names the kinds
    whose shared class is the class of the failed step rather than one of their
    own: `L-COLLIDE` and `L-TIMEOUT` of spec section 5.2.
    """

    task_id: str
    scorer_version: str
    thresholds: dict[str, float]
    balance: BalanceLimits
    step_signals: dict[str, tuple[str, ...]]
    episode_signals: tuple[str, ...]
    class_from_failed_step: tuple[str, ...]

    def declared_signals(self) -> frozenset[str]:
        """Every signal the config accounts for, by step, by episode or by limit."""
        names = set(self.episode_signals) | set(self.balance.signals())
        for signals in self.step_signals.values():
            names |= set(signals)
        return frozenset(names)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ScorerConfig:
        """Validate a parsed scorer config; raise `ConfigError` on anything unclear."""
        _reject_unknown(data, tuple(cls.__dataclass_fields__), "scorer config")
        balance = _section(data, "balance")
        thresholds = _number_map(data, "thresholds", "scorer config")
        if not thresholds:
            raise ConfigError("`thresholds` không được rỗng: task nào cũng có ngưỡng vị từ")
        step_signals = _name_list_map(data, "step_signals", "scorer config")
        if not step_signals:
            raise ConfigError(
                "`step_signals` không được rỗng: mỗi bước phải khai tín hiệu nó "
                "được chấm trên, thiếu tín hiệu mà không khai thì thành đạt hoặc trượt (AC 2)"
            )
        return cls(
            task_id=_text(data, "task_id", "scorer config"),
            scorer_version=_text(data, "scorer_version", "scorer config"),
            thresholds=thresholds,
            balance=BalanceLimits(
                min_height=_number(balance, "min_height", "balance"),
                max_tilt=_number(balance, "max_tilt", "balance"),
                height_signal=_text(balance, "height_signal", "balance"),
                tilt_signal=_text(balance, "tilt_signal", "balance"),
            ),
            step_signals=step_signals,
            episode_signals=_name_list(data, "episode_signals", "scorer config"),
            class_from_failed_step=_name_list(data, "class_from_failed_step", "scorer config"),
        )


def load_scorer_config(path: Path) -> tuple[ScorerConfig, str]:
    """Read a scorer config; return it and the hash to record with every `Score`."""
    raw, parsed = _read_yaml(path)
    return ScorerConfig.from_mapping(parsed), _sha256(raw)


def load_train_thresholds(path: Path) -> tuple[TrainThresholds, str]:
    """Read a threshold file; return the thresholds and the hash to record with them.

    One read serves both answers, so the hash an artifact carries is the hash of
    the bytes the detectors actually ran on (AC 3, 4).
    """
    raw, parsed = _read_yaml(path)
    return TrainThresholds.from_mapping(parsed), _sha256(raw)


def _read_yaml(path: Path) -> tuple[bytes, Mapping[str, Any]]:
    """Read and parse a config file, hashing the same bytes that were parsed.

    One read serves both answers, so the hash in an artifact can only ever name
    the file that run actually read (AC 5; DA-08 AC 3, 4).

    A file that is not there and a file that is not YAML both come back as a
    `ConfigError`, so the command that asked for it can say what it could not
    do rather than hand the engineer a traceback (review of #58, point 5).
    """
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ConfigError(f"`{path}` không đọc được: {error}") from error
    try:
        parsed = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ConfigError(f"`{path}` không phải YAML đọc được: {error}") from error
    if not isinstance(parsed, Mapping):
        kind = type(parsed).__name__
        raise ConfigError(f"`{path}` must hold a mapping of sections, got {kind}")
    return raw, parsed


def config_sha256(path: Path) -> str:
    """Hash of the config file as it was read, for the result artifact (AC 3, 4)."""
    return _sha256(path.read_bytes())


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _section(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if name not in data:
        raise ConfigError(f"missing section `{name}`")
    section = data[name]
    if not isinstance(section, Mapping):
        raise ConfigError(f"section `{name}` must be a mapping, got {type(section).__name__}")
    _reject_unknown(section, _SECTION_FIELDS[name], name)
    return section


def _reject_unknown(data: Mapping[str, Any], expected: tuple[str, ...], where: str) -> None:
    # a key nobody reads means the number its author wrote is not the number in use
    unknown = sorted(set(data) - set(expected))
    if unknown:
        raise ConfigError(f"`{where}` has unknown key(s) {unknown}; expected {list(expected)}")


def _require(section: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in section:
        raise ConfigError(f"missing threshold `{where}.{key}`")
    return section[key]


def _text(section: Mapping[str, Any], key: str, where: str) -> str:
    value = _require(section, key, where)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"`{where}.{key}` must be a non-empty string, got {value!r}")
    return value


def _number(section: Mapping[str, Any], key: str, where: str) -> float:
    value = _require(section, key, where)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"`{where}.{key}` must be a number, got {value!r}")
    return float(value)


def _steps(section: Mapping[str, Any], key: str, where: str) -> int:
    value = _require(section, key, where)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"`{where}.{key}` must be a whole number of steps, got {value!r}")
    return value


def _number_map(section: Mapping[str, Any], key: str, where: str) -> dict[str, float]:
    value = _require(section, key, where)
    if not isinstance(value, Mapping):
        raise ConfigError(f"`{where}.{key}` must be a mapping of name to number, got {value!r}")
    budgets: dict[str, float] = {}
    for name, number in value.items():
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise ConfigError(f"`{where}.{key}.{name}` must be a number, got {number!r}")
        budgets[str(name)] = float(number)
    return budgets


def _name_list(section: Mapping[str, Any], key: str, where: str) -> tuple[str, ...]:
    value = _require(section, key, where)
    if not isinstance(value, list):
        raise ConfigError(f"`{where}.{key}` must be a list of names, got {value!r}")
    names = tuple(_name(item, f"{where}.{key}") for item in value)
    repeated = sorted({name for name in names if names.count(name) > 1})
    if repeated:
        raise ConfigError(f"`{where}.{key}` repeats {repeated}")
    return names


def _name_list_map(section: Mapping[str, Any], key: str, where: str) -> dict[str, tuple[str, ...]]:
    value = _require(section, key, where)
    if not isinstance(value, Mapping):
        raise ConfigError(f"`{where}.{key}` must be a mapping of name to list, got {value!r}")
    return {
        _name(name, f"{where}.{key}"): _name_list(value, str(name), f"{where}.{key}")
        for name in value
    }


def _name(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"`{where}` must hold non-empty names, got {value!r}")
    return value


_SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "balance": tuple(BalanceLimits.__dataclass_fields__),
    "t1": tuple(T1Thresholds.__dataclass_fields__),
    "t2": tuple(T2Thresholds.__dataclass_fields__),
    "t3": tuple(T3Thresholds.__dataclass_fields__),
    "t4": tuple(T4Thresholds.__dataclass_fields__),
    "t5": tuple(T5Thresholds.__dataclass_fields__),
    "t6": tuple(T6Thresholds.__dataclass_fields__),
    "t7": tuple(T7Thresholds.__dataclass_fields__),
    "t8": tuple(T8Thresholds.__dataclass_fields__),
    "o1": tuple(O1Thresholds.__dataclass_fields__),
    "o2": tuple(O2Thresholds.__dataclass_fields__),
    "o3": tuple(O3Thresholds.__dataclass_fields__),
    "o4": tuple(O4Thresholds.__dataclass_fields__),
}
