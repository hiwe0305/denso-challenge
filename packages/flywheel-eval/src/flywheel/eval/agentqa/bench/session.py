"""One scoring session: results first, answer key last (DA-31 AC 1).

The session is told which copies make the benchmark, as (group, dataset_id) with
group `data` or `logs`. It takes the code layer's and the agent layer's run of
every copy, and only then opens the sealed `DefectManifest`s. Asking for the
answers earlier raises `BenchIncomplete` before any manifest is touched, so no
result can be written, or rewritten, with the answer in view.

Before opening, every ref a run says it read is checked against the rule of DA-27
(`docs/g0/defect-inject.md`, decided 4/11/2026): a run sees exactly one copy,
read-only, with no path to the other copy or to `answers/`. A ref into the answer
roots, to a manifest file, or naming another copy of the benchmark raises
`AnswerLeak`: the run could have read the answer, so its score would mean nothing.

Once open, each group must hold one copy with defects and one clean copy, the one
whose manifest is empty.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from flywheel.contracts.agentqa import AgentReview
from flywheel.contracts.artifacts import DefectManifest
from flywheel.eval.agentqa.bench.answers import (
    LOCK,
    MANIFEST,
    AnswerKeyError,
    find_answer_dir,
    open_sealed,
)
from flywheel.eval.agentqa.bench.detections import LAYERS, BenchInputError, Layer, LayerRun

ANSWERS_DIR = "answers"

Group = Literal["data", "logs"]
GROUPS: tuple[Group, ...] = ("data", "logs")


class BenchIncomplete(RuntimeError):
    """The answer key was asked for before every layer had run on every copy."""


class AnswerLeak(RuntimeError):
    """A run names something it must not see: the answer key or another copy."""


@dataclass(frozen=True)
class CopyResult:
    """Both layers' runs of one copy, with its opened answer key."""

    group: Group
    dataset_id: str
    job_finished_at: datetime | None
    runs: Mapping[Layer, LayerRun]
    manifest: DefectManifest

    @property
    def clean(self) -> bool:
        return not self.manifest.defects


@dataclass(frozen=True)
class GroupResult:
    """The copy with defects and the clean copy of one group, both opened."""

    group: Group
    injected: CopyResult
    clean: CopyResult


@dataclass(frozen=True)
class OpenedBench:
    """What the scorer works on: every group opened, and the engineer's reviews."""

    groups: tuple[GroupResult, ...]
    reviews: tuple[AgentReview, ...]
    manifest_sha256: Mapping[str, str]


class BenchSession:
    def __init__(
        self,
        copies: Sequence[tuple[Group, str]],
        answer_roots: Sequence[Path],
    ) -> None:
        ids = [dataset_id for _, dataset_id in copies]
        if len(ids) != len(set(ids)):
            raise BenchInputError("a copy is listed twice")
        unknown = sorted({group for group, _ in copies} - set(GROUPS))
        if unknown:
            raise BenchInputError(f"unknown group(s) {unknown}")
        self._groups: dict[str, Group] = {dataset_id: group for group, dataset_id in copies}
        self._roots = tuple(answer_roots)
        self._runs: dict[str, dict[Layer, LayerRun]] = {d: {} for d in ids}
        self._finished: dict[str, datetime | None] = {d: None for d in ids}
        self._reviews: list[AgentReview] = []
        self._opened = False

    def record(self, run: LayerRun, job_finished_at: datetime | None = None) -> None:
        """Take one layer's run of one copy; `job_finished_at` is when the job the
        layer reports on finished, the start of the time-to-report (AC 2)."""
        if self._opened:
            raise BenchInputError("the answer key is open; no run can be recorded after it")
        if run.dataset_id not in self._runs:
            raise BenchInputError(f"{run.dataset_id} is not a copy of this benchmark")
        if run.layer in self._runs[run.dataset_id]:
            raise BenchInputError(f"{run.layer} run of {run.dataset_id} is already recorded")
        if job_finished_at is not None:
            if job_finished_at.tzinfo is None:
                raise BenchInputError("job_finished_at must carry a time zone")
            self._finished[run.dataset_id] = job_finished_at
        self._runs[run.dataset_id][run.layer] = run

    def review(self, review: AgentReview) -> None:
        """Take the engineer's `AgentReview` of one agent report (fw review)."""
        if self._opened:
            raise BenchInputError("the answer key is open; no review can be recorded after it")
        self._reviews.append(review)

    def missing(self) -> list[str]:
        """`<layer>:<dataset_id>` of every run still to come."""
        return [
            f"{layer}:{dataset_id}"
            for dataset_id, runs in self._runs.items()
            for layer in LAYERS
            if layer not in runs
        ]

    def open_answers(self) -> OpenedBench:
        """Open the answer keys, once every layer has run on every copy and no run
        names the answer or another copy."""
        missing = self.missing()
        if missing:
            raise BenchIncomplete(f"runs still to come: {', '.join(missing)}")
        for dataset_id, runs in self._runs.items():
            for run in runs.values():
                self._check_no_leak(dataset_id, run)
        self._opened = True
        copies: dict[str, CopyResult] = {}
        digests: dict[str, str] = {}
        for dataset_id, runs in self._runs.items():
            answer_dir = find_answer_dir(self._roots, dataset_id)
            manifest = open_sealed(answer_dir, dataset_id)
            digests[dataset_id] = (answer_dir / LOCK).read_text(encoding="utf-8").strip()
            copies[dataset_id] = CopyResult(
                group=self._groups[dataset_id],
                dataset_id=dataset_id,
                job_finished_at=self._finished[dataset_id],
                runs=dict(runs),
                manifest=manifest,
            )
        return OpenedBench(
            groups=tuple(self._pair(group, copies) for group in GROUPS if group in
                         self._groups.values()),
            reviews=tuple(self._reviews),
            manifest_sha256=digests,
        )

    def _pair(self, group: Group, copies: Mapping[str, CopyResult]) -> GroupResult:
        mine = [c for c in copies.values() if c.group == group]
        clean = [c for c in mine if c.clean]
        injected = [c for c in mine if not c.clean]
        if len(clean) != 1 or len(injected) != 1:
            raise AnswerKeyError(
                f"group {group}: {len(injected)} copies with defects and {len(clean)} clean;"
                " the benchmark needs one of each"
            )
        return GroupResult(group, injected[0], clean[0])

    def _check_no_leak(self, dataset_id: str, run: LayerRun) -> None:
        others = set(self._runs) - {dataset_id}
        roots = [root.resolve() for root in self._roots]
        for ref in run.inputs:
            parts = PurePosixPath(ref.replace("\\", "/")).parts
            path = Path(ref)
            why = None
            if MANIFEST in parts or LOCK in parts:
                why = "names an answer key file"
            elif ANSWERS_DIR in parts:
                why = "points into answers/, which also holds the copy's lineage"
            elif any(other in ref for other in others):
                why = "names another copy of the benchmark"
            elif path.is_absolute() and any(path.resolve().is_relative_to(r) for r in roots):
                why = "points into the answer key"
            if why:
                raise AnswerLeak(f"{run.layer} run of {dataset_id}: {ref!r} {why}")
