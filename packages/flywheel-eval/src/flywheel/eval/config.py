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
from collections.abc import Iterable, Mapping
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
class SignalLimits:
    """How incomplete a trace may be before the system check says CHƯA RÕ (DA-13 AC 1).

    Spec section 6.4 puts "thiếu tín hiệu" first in the ordered check and gives
    no number for it, so the numbers live here. A gap fraction of zero means
    one null cycle costs that code its verdict; a real rollout may need more
    room, and that is a calibration to make on the trace of SIMPLE rather than
    a constant to bury in a detector.

    `min_steps` exists because a percentile over three cycles is not a
    percentile. A trace shorter than this is not judged at all, which is CHƯA
    RÕ, not a system that behaved.
    """

    max_gap_fraction: float
    max_dropped_frames: int
    min_steps: int


@dataclass(frozen=True)
class R3Thresholds:
    """Tracking error of the WBC, upper and lower body against their own limits.

    Spec section 6.4 measures the norm of (command sent - state measured) and
    keeps the two halves apart, because the upper body tracks joint targets and
    the lower body tracks a base command: one threshold for both would hide a
    fault in whichever half moves less.

    `percentile` is the statistic taken over the cycles of the episode, written
    down rather than implied, so a run under a different statistic cannot be
    compared with this one by accident. `tau_track_*` is calibrated as the 99th
    percentile over successful teleop episodes (AC 2).
    """

    tau_track_upper: float
    tau_track_lower: float
    percentile: float


@dataclass(frozen=True)
class R1Thresholds:
    """Inference cycle latency: p99 over tau_lat is a runtime fault.

    tau_lat is calibrated as the 99th percentile over the reference run at G0
    (AC 2), so the question the check asks is whether this episode was slower
    than the machine is known to be, not whether it was slower than some
    absolute budget nobody measured.
    """

    tau_lat_s: float
    percentile: float


@dataclass(frozen=True)
class R2Thresholds:
    """Inference slower than real-time chunking can cover: delay_steps over max_delay.

    `delay_steps` of `RTCInferenceRecord` is ceil(latency * hz), the control
    steps a real-time loop would run while the chunk is computed (DA-19). RTC
    covers up to the model's `max_delay` of them - 8 for Ψ₀ stage 3 - so a
    chunk with `delay_steps > max_delay_steps` is one the robot would stall on
    on hardware. `buffer_level` is not read: it is the level when the request
    went out, which is always 0 under SIMPLE's refill-when-empty, so it says
    nothing about a stall (decision Q2 as corrected, 3/11/2026).

    `max_underruns` is how many such chunks an episode may contain before the
    runtime, not the policy, is what the engineer goes and fixes. A count, not
    a percentile: one stall is visible, and an average over a long episode
    hides it.
    """

    max_delay_steps: int
    max_underruns: int


@dataclass(frozen=True)
class R4Thresholds:
    """Image and state clocks drifting apart: the largest offset over tau_sync.

    The statistic is the maximum over the episode, because spec section 6.4
    says "lệch thời gian lớn nhất giữa khung ảnh và state"; tau_sync itself is
    calibrated as the 99th percentile over successful teleop demonstrations
    (AC 2). Those are two different percentiles on purpose: the threshold comes
    from what good data looks like, the measurement is the worst moment of this
    episode.
    """

    tau_sync_s: float


@dataclass(frozen=True)
class CameraReference:
    """The hashed reference calibration of one camera (AC 2).

    `pose` is [x, y, z, qw, qx, qy, qz] relative to the mount, the layout of
    `CameraParams` in Contract change #31.
    """

    mount: str
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    pose: tuple[float, ...]


@dataclass(frozen=True)
class R5Thresholds:
    """Camera calibration against the reference fixed at G0.

    Two things can be wrong and they are different faults to report.
    `CameraParams.reference_sha256` is the hash of the G0-pinned reference the
    episode ran against, copied by the hook from the RunPlan (decision Q3,
    3/11/2026): an episode run against another reference is not comparable
    with the rest of the run even if its numbers happen to be close. The
    numbers themselves are then compared with `cameras` within a tolerance,
    whatever the hash said, since a render pipeline does not reproduce a
    float exactly.

    The tolerances are kept apart because the quantities are: pixels for the
    intrinsics, metres for the camera position, and a unitless quaternion
    component for its orientation.

    `reference_sha256` is None where no reference is pinned (`system.yaml`
    ships the two-table task's, pinned at G0 on 3/11/2026). R5 is then skipped
    with that reason rather than compared against numbers nobody has measured:
    a placeholder hash would make every episode a calibration fault, and
    declared numbers behind an unpinned reference are not evidence. A skip is
    the honest answer and `combine` keeps the episode from being cleared on it
    (AC 2).
    """

    reference_sha256: str | None
    cameras: dict[str, CameraReference]
    tolerance_intrinsics_px: float
    tolerance_position_m: float
    tolerance_quaternion: float


@dataclass(frozen=True)
class R6Thresholds:
    """Which `infra_status` values mean the infrastructure was fine.

    R6 is not a statement about the policy (AC 1; 03 section 4.3, rule 8), so
    there is no number here: there is a list of the statuses that count as
    healthy, and anything else is the server, not the robot.
    """

    ok_statuses: tuple[str, ...]


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


@dataclass(frozen=True)
class StageRow:
    """One row of the stage attribution table (DA-13 AC 3; spec section 6.4).

    `evidence` names the rule in code that decides whether the row applies.
    The wording, what the row blames and what it suggests all live in
    `stage.yaml` so they change without touching code, but the rules
    themselves are code: a row whose `evidence` nothing implements is a row
    that would silently never fire, so the loader refuses it.

    `consumes_budget` is False on the rows that only report. The Stage 1 row
    is one of them: spec section 7.3 fixes visual augmentation for every
    branch, so there is no data intervention left for it to ask for, and
    saying so here keeps `decide` from costing a budget against it (decision
    of 30/10/2026).
    """

    row_id: str
    evidence: str
    attribute_to: str
    intervention: str
    consumes_budget: bool


@dataclass(frozen=True)
class StageThresholds:
    """What counts as a wrong P1 answer and as a high or low P3 error.

    `p3_high_error_by_group` lets one action group carry its own budget, the
    way `o1.max_error_by_group` of DA-08 does; a group with no entry falls back
    to `p3_high_error`.
    """

    p1_min_accuracy: float
    p3_high_error: float
    p3_high_error_by_group: dict[str, float]
    p3_low_error: float


@dataclass(frozen=True)
class StageTable:
    """The one stage attribution table (AC 3).

    One table, no key selecting a variant: spec section 6.4 and design section
    10 are the same table since 30/10/2026, and a second copy is a second
    answer to the same question.
    """

    thresholds: StageThresholds
    rows: tuple[StageRow, ...]

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], known: Iterable[str]) -> StageTable:
        """Validate a parsed stage table; `known` is the evidence rules in code."""
        _reject_unknown(data, tuple(cls.__dataclass_fields__), "stage.yaml")
        thresholds = _section(data, "thresholds")
        rows = _require(data, "rows", "stage.yaml")
        if not isinstance(rows, list) or not rows:
            raise ConfigError("`stage.yaml.rows` must be a non-empty list of rows")
        parsed = tuple(_stage_row(row, index, known) for index, row in enumerate(rows))
        repeated = sorted({row.row_id for row in parsed if _count(parsed, row.row_id) > 1})
        if repeated:
            raise ConfigError(f"`stage.yaml.rows` repeats row_id {repeated}")
        return cls(
            thresholds=StageThresholds(
                p1_min_accuracy=_fraction(thresholds, "p1_min_accuracy", "thresholds"),
                p3_high_error=_number(thresholds, "p3_high_error", "thresholds"),
                p3_high_error_by_group=_number_map(
                    thresholds, "p3_high_error_by_group", "thresholds"
                ),
                p3_low_error=_number(thresholds, "p3_low_error", "thresholds"),
            ),
            rows=parsed,
        )

    def row(self, evidence: str) -> StageRow | None:
        """The row one evidence rule belongs to, or None where the table omits it."""
        for row in self.rows:
            if row.evidence == evidence:
                return row
        return None


@dataclass(frozen=True)
class SystemThresholds:
    """Every threshold the F-SYS checks of DA-13 read, from `system.yaml` (AC 2)."""

    signals: SignalLimits
    r1: R1Thresholds
    r2: R2Thresholds
    r3: R3Thresholds
    r4: R4Thresholds
    r5: R5Thresholds
    r6: R6Thresholds

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> SystemThresholds:
        """Validate a parsed system-threshold mapping; raise on anything unclear."""
        _reject_unknown(data, tuple(cls.__dataclass_fields__), "system.yaml")
        signals = _section(data, "signals")
        r1, r2, r3 = (_section(data, name) for name in ("r1", "r2", "r3"))
        r4, r5, r6 = (_section(data, name) for name in ("r4", "r5", "r6"))
        return cls(
            signals=SignalLimits(
                max_gap_fraction=_fraction(signals, "max_gap_fraction", "signals"),
                max_dropped_frames=_steps(signals, "max_dropped_frames", "signals"),
                min_steps=_steps(signals, "min_steps", "signals"),
            ),
            r1=R1Thresholds(
                tau_lat_s=_number(r1, "tau_lat_s", "r1"),
                percentile=_percentile(r1, "percentile", "r1"),
            ),
            r2=R2Thresholds(
                max_delay_steps=_steps(r2, "max_delay_steps", "r2"),
                max_underruns=_steps(r2, "max_underruns", "r2"),
            ),
            r3=R3Thresholds(
                tau_track_upper=_number(r3, "tau_track_upper", "r3"),
                tau_track_lower=_number(r3, "tau_track_lower", "r3"),
                percentile=_percentile(r3, "percentile", "r3"),
            ),
            r4=R4Thresholds(tau_sync_s=_number(r4, "tau_sync_s", "r4")),
            r5=R5Thresholds(
                reference_sha256=_optional_digest(r5, "reference_sha256", "r5"),
                cameras=_cameras(r5, "cameras", "r5"),
                tolerance_intrinsics_px=_number(r5, "tolerance_intrinsics_px", "r5"),
                tolerance_position_m=_number(r5, "tolerance_position_m", "r5"),
                tolerance_quaternion=_number(r5, "tolerance_quaternion", "r5"),
            ),
            r6=R6Thresholds(ok_statuses=_name_list(r6, "ok_statuses", "r6")),
        )


def load_scorer_config(path: Path) -> tuple[ScorerConfig, str]:
    """Read a scorer config; return it and the hash to record with every `Score`."""
    raw, parsed = _read_yaml(path)
    return ScorerConfig.from_mapping(parsed), _sha256(raw)


def load_stage_table(path: Path, known: Iterable[str]) -> tuple[StageTable, str]:
    """Read `stage.yaml`; return the table and the hash to record with a hypothesis."""
    raw, parsed = _read_yaml(path)
    return StageTable.from_mapping(parsed, known), _sha256(raw)


def load_system_thresholds(path: Path) -> tuple[SystemThresholds, str]:
    """Read `system.yaml`; return the thresholds and the hash to record with them.

    One read serves both answers, so the hash in a record can only ever name
    the file the checks actually ran on (DA-13 AC 2).
    """
    raw, parsed = _read_yaml(path)
    return SystemThresholds.from_mapping(parsed), _sha256(raw)


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


def _stage_row(row: Any, index: int, known: Iterable[str]) -> StageRow:
    place = f"stage.yaml.rows[{index}]"
    if not isinstance(row, Mapping):
        raise ConfigError(f"`{place}` must be a mapping, got {row!r}")
    _reject_unknown(row, tuple(StageRow.__dataclass_fields__), place)
    evidence = _text(row, "evidence", place)
    if evidence not in set(known):
        # A row nothing implements would never fire and nobody would notice.
        raise ConfigError(
            f"`{place}.evidence` là `{evidence}`, không có luật nào trong mã; "
            f"luật đang có: {sorted(known)}"
        )
    return StageRow(
        row_id=_text(row, "row_id", place),
        evidence=evidence,
        attribute_to=_text(row, "attribute_to", place),
        intervention=_text(row, "intervention", place),
        consumes_budget=_flag(row, "consumes_budget", place),
    )


def _count(rows: tuple[StageRow, ...], row_id: str) -> int:
    return sum(1 for row in rows if row.row_id == row_id)


def _flag(section: Mapping[str, Any], key: str, where: str) -> bool:
    value = _require(section, key, where)
    if not isinstance(value, bool):
        raise ConfigError(f"`{where}.{key}` must be true or false, got {value!r}")
    return value


def _optional_digest(section: Mapping[str, Any], key: str, where: str) -> str | None:
    """A hash, or None where the thing it names has not been pinned yet.

    The key must still be present: leaving it out would be an author who
    forgot, and writing `null` is an author who means "not pinned".
    """
    value = _require(section, key, where)
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 64:
        raise ConfigError(f"`{where}.{key}` must be 64 hex characters or null, got {value!r}")
    if any(char not in "0123456789abcdef" for char in value):
        raise ConfigError(f"`{where}.{key}` must be lowercase hex, got {value!r}")
    return value


def _cameras(section: Mapping[str, Any], key: str, where: str) -> dict[str, CameraReference]:
    """The reference calibration of each camera, keyed by `CameraParams.uid`."""
    value = _require(section, key, where)
    if not isinstance(value, Mapping):
        raise ConfigError(
            f"`{where}.{key}` must be a mapping of camera uid to calibration, got {value!r}"
        )
    cameras: dict[str, CameraReference] = {}
    for uid in value:
        name = _name(uid, f"{where}.{key}")
        entry = value[uid]
        if not isinstance(entry, Mapping):
            raise ConfigError(f"`{where}.{key}.{name}` must be a mapping, got {entry!r}")
        place = f"{where}.{key}.{name}"
        _reject_unknown(entry, tuple(CameraReference.__dataclass_fields__), place)
        pose = _numbers(entry, "pose", place)
        if len(pose) != 7:
            raise ConfigError(
                f"`{place}.pose` must be 7 numbers [x, y, z, qw, qx, qy, qz], got {len(pose)}"
            )
        cameras[name] = CameraReference(
            mount=_text(entry, "mount", place),
            width=_steps(entry, "width", place),
            height=_steps(entry, "height", place),
            fx=_number(entry, "fx", place),
            fy=_number(entry, "fy", place),
            cx=_number(entry, "cx", place),
            cy=_number(entry, "cy", place),
            pose=pose,
        )
    return cameras


def _numbers(section: Mapping[str, Any], key: str, where: str) -> tuple[float, ...]:
    value = _require(section, key, where)
    if not isinstance(value, list):
        raise ConfigError(f"`{where}.{key}` must be a list of numbers, got {value!r}")
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ConfigError(f"`{where}.{key}` must hold numbers, got {item!r}")
    return tuple(float(item) for item in value)


def _fraction(section: Mapping[str, Any], key: str, where: str) -> float:
    value = _number(section, key, where)
    if not 0.0 <= value <= 1.0:
        raise ConfigError(f"`{where}.{key}` must be a fraction in [0, 1], got {value!r}")
    return value


def _percentile(section: Mapping[str, Any], key: str, where: str) -> float:
    # The statistic a threshold is compared against; 0 or 100 would make the
    # comparison the minimum or the maximum, which are both legitimate asks.
    value = _number(section, key, where)
    if not 0.0 <= value <= 100.0:
        raise ConfigError(f"`{where}.{key}` must be a percentile in [0, 100], got {value!r}")
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
    "thresholds": tuple(StageThresholds.__dataclass_fields__),
    "signals": tuple(SignalLimits.__dataclass_fields__),
    "r1": tuple(R1Thresholds.__dataclass_fields__),
    "r2": tuple(R2Thresholds.__dataclass_fields__),
    "r3": tuple(R3Thresholds.__dataclass_fields__),
    "r4": tuple(R4Thresholds.__dataclass_fields__),
    "r5": tuple(R5Thresholds.__dataclass_fields__),
    "r6": tuple(R6Thresholds.__dataclass_fields__),
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
