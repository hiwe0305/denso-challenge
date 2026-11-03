"""Dynamic replay of one episode, as the SIMPLE adapter measured it (DA-17 AC 2).

The adapter (`flywheel_simple.replay`) starts each episode from its recorded
scene, feeds the recorded action to SIMPLE's decoupled WBC on MuJoCo and
appends one line per episode to `replay_outcomes.jsonl`. The lane only reads
that file; it never imports the adapter (03 section 7.3). One line:

    episode_index                    the dataset's episode_index
    success                          SIMPLE's check_success after the replay
    state_error_by_group             largest |replayed - recorded| joint state of
                                     each action group over the episode, rad
    hand_event_offset_steps          replayed minus recorded step at which a hand
                                     closes (the hand whose gap is largest); null
                                     when no hand closes in the recording
    state_error_peak_frame_by_group  frame of each group's largest error
    replayed_frames, recorded_frames how far the replay went

A failed replay, a group over its `state_error` threshold and a hand event
further off than `hand_event_offset_steps` are issues. Design 6.3: a dynamic
issue flags the episode for an engineer (qa.yaml `replay_dynamic`); the replay's
success also reaches QA as `sim_success`, which `task_success` judges.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flywheel.contracts.artifacts import ReplayIssue, ReplayReport

if TYPE_CHECKING:
    from flywheel.data.replay_check.thresholds import ReplayThresholds

REQUIRED = ("episode_index", "success", "state_error_by_group", "hand_event_offset_steps")
OPTIONAL = ("state_error_peak_frame_by_group", "replayed_frames", "recorded_frames")


@dataclass(frozen=True)
class ReplayOutcome:
    """One line of replay_outcomes.jsonl."""

    episode_index: int
    success: bool
    state_error_by_group: Mapping[str, float]
    hand_event_offset_steps: int | None
    state_error_peak_frame_by_group: Mapping[str, int] = field(default_factory=dict)
    replayed_frames: int | None = None
    recorded_frames: int | None = None

    @classmethod
    def from_json(cls, line: str) -> ReplayOutcome:
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError(f"replay outcome must be an object, got {line[:80]!r}")
        missing = [k for k in REQUIRED if k not in data]
        unknown = [k for k in data if k not in REQUIRED + OPTIONAL]
        if missing or unknown:
            raise ValueError(f"replay outcome: missing {missing}, unknown {unknown}")
        offset = data["hand_event_offset_steps"]
        return cls(
            episode_index=_int(data["episode_index"], "episode_index"),
            success=_bool(data["success"]),
            state_error_by_group={
                str(k): _float(v, k) for k, v in _dict(data["state_error_by_group"]).items()
            },
            hand_event_offset_steps=None if offset is None else _int(offset, "hand offset"),
            state_error_peak_frame_by_group={
                str(k): _int(v, k)
                for k, v in _dict(data.get("state_error_peak_frame_by_group", {})).items()
            },
            replayed_frames=_optional_int(data.get("replayed_frames"), "replayed_frames"),
            recorded_frames=_optional_int(data.get("recorded_frames"), "recorded_frames"),
        )


def read_outcomes(path: Path) -> dict[int, ReplayOutcome]:
    """episode_index -> outcome of a replay_outcomes.jsonl; an index twice raises."""
    outcomes: dict[int, ReplayOutcome] = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            outcome = ReplayOutcome.from_json(line)
        except ValueError as error:
            raise ValueError(f"{path}:{number}: {error}") from error
        if outcome.episode_index in outcomes:
            raise ValueError(f"{path}:{number}: episode {outcome.episode_index} replayed twice")
        outcomes[outcome.episode_index] = outcome
    return outcomes


def report_from_outcome(
    episode_id: str, outcome: ReplayOutcome, th: ReplayThresholds
) -> ReplayReport:
    """The dynamic ReplayReport of one episode."""
    issues = []
    if not outcome.success:
        went = f" after {outcome.replayed_frames} of {outcome.recorded_frames} frames"
        detail = "replay did not succeed by check_success" + (
            went if outcome.replayed_frames is not None else ""
        )
        issues.append(ReplayIssue(code="replay_failed", frames=[], detail=detail))
    for group, error in sorted(outcome.state_error_by_group.items()):
        limit = th.state_error.get(group)
        if limit is not None and not error <= limit:
            peak = outcome.state_error_peak_frame_by_group.get(group)
            issues.append(
                ReplayIssue(
                    code="state_error",
                    frames=[] if peak is None else [peak],
                    detail=f"{group}: replayed state off the recording by {error:.3g} rad"
                    f" (threshold {limit:.3g})",
                )
            )
    offset = outcome.hand_event_offset_steps
    if offset is not None and abs(offset) > th.hand_event_offset_steps:
        detail = (
            f"hand closes {offset:+d} steps off the recording"
            f" (threshold {th.hand_event_offset_steps})"
        )
        issues.append(ReplayIssue(code="hand_event_offset", frames=[], detail=detail))
    return ReplayReport(
        episode_id=episode_id,
        mode="dynamic",
        issues=issues,
        error_by_group=dict(outcome.state_error_by_group),
        hand_event_offset_steps=offset,
        sim_success=outcome.success,
    )


def _dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"expected an object, got {value!r}")
    return value


def _int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    return value


def _optional_int(value: Any, name: str) -> int | None:
    return None if value is None else _int(value, name)


def _float(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    return float(value)


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"success must be true or false, got {value!r}")
    return value
