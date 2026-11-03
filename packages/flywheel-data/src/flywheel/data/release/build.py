"""Tier 5 (Release): a frozen, hashed release of QA'd episodes (DA-03 AC 4; spec 4.4).

`build_release` either refuses the whole release or freezes one; it never drops an
episode quietly. It refuses, listing every reason at once, when

- an episode belongs to a benchmark copy (`benchmark_copy_id`, defective or clean:
  design 6.1, 9.2; Q5). One such episode refuses the release;
- an episode's condition seed lies outside the `train` range of the SplitPlan
  (spec 4.4 "Chia tập": invalidate the release; design 10 D5), or a machine-made
  episode has no seed to check (03 invariant 10). A human demo whose source records
  no seed (psi-data) passes with `seed: null` in its item;
- an episode is not in split `train`, has no QAReport, or two inputs share an id;
- the included episodes span more than one `embodiment_id` (design 6.1: no mixing
  before a Decision on V3).

Otherwise every episode becomes an item (03 section 4, table Release): QA pass and
flag are included, quarantine and reject are kept with `excluded: true` and the
QA reasons (spec 4.4: rejected samples keep their reason). `manifest_sha256` is the
sha256 of the items as canonical JSON, so the same episodes and reports give the
same hash; the Release id is content-addressed over the whole record. `out` gets
`release.json` (the catalog `Release`, status frozen), `release_manifest.json`
(the v0 `ReleaseManifest` other lanes and the Psi0 export take) and `FROZEN`
holding the hash (03 line 271). `out` must be new or empty: a frozen release is
never written over.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flywheel.contracts.artifacts import Episode, QAReport
from flywheel.contracts.base import canonical_json
from flywheel.contracts.entities import Release
from flywheel.contracts.v0 import ReleaseManifest
from flywheel.data.config import load_train_seeds

INCLUDED = ("pass", "flag")
RELEASE_FILE = "release.json"
MANIFEST_FILE = "release_manifest.json"
FROZEN_FILE = "FROZEN"


class ReleaseRefused(ValueError):
    """The release as asked would break a rule; `problems` lists every one."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("release refused:\n" + "\n".join(f"- {p}" for p in problems))


def is_benchmark_copy(episode: Episode) -> bool:
    """Whether the episode belongs to a DA-27 benchmark copy, defective or clean.

    TODO(#53): call `flywheel.data.inject.api.has_injected_defect` once DA-27's PR
    #53 is on master; it checks the same field.
    """
    return episode.meta.benchmark_copy_id is not None


def build_release(
    episodes: Sequence[Episode],
    reports: Sequence[QAReport],
    split_plan: Path,
    out: Path,
    *,
    seeds: Mapping[str, int | None] | None = None,
    name: str | None = None,
    now: datetime | None = None,
) -> ReleaseManifest:
    """Freeze the release of `episodes` under `out`, or raise ReleaseRefused.

    `seeds` maps episode_id to its condition seed (ingest's SourceRecord.lineage);
    an episode it does not name has no known seed. `name` defaults to out's name.
    """
    start, stop = load_train_seeds(split_plan)
    seeds = seeds or {}
    by_episode = _reports_by_episode(reports)
    problems = _problems(episodes, by_episode, seeds, (start, stop))
    included = [e for e in episodes if not _excluded(by_episode.get(e.episode_id))]
    embodiments = sorted({e.embodiment_id for e in included})
    if len(embodiments) > 1:
        problems.append(
            f"included episodes span embodiments {embodiments}; mixing needs a Decision on V3"
            " (design 6.1)"
        )
    if problems:
        raise ReleaseRefused(problems)
    items = [_item(e, by_episode[e.episode_id], seeds.get(e.episode_id)) for e in episodes]
    items.sort(key=lambda item: str(item["episode_id"]))
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} is not empty; a frozen release is never written over")

    split_sha = hashlib.sha256(split_plan.read_bytes()).hexdigest()
    manifest_sha = hashlib.sha256(canonical_json(items).encode()).hexdigest()
    release = Release(
        name=name or out.name,
        kind="robot",
        embodiment_id=embodiments[0] if embodiments else "default",
        split_plan_cfg_id=f"splits_{split_sha[:16]}",
        status="frozen",
        manifest_sha256=manifest_sha,
        holdout_guard_passed=True,
        combined_license=" AND ".join(sorted({e.license for e in included})) or None,
        counts=_counts(episodes, by_episode, included, seeds),
        items=items,
        frozen_at=(now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
        meta={"split_plan_sha256": split_sha, "train_seeds": [start, stop]},
    )
    manifest = ReleaseManifest(release_id=release.id, frozen=True)
    out.mkdir(parents=True, exist_ok=True)
    (out / RELEASE_FILE).write_text(release.to_canonical_json() + "\n")
    (out / MANIFEST_FILE).write_text(manifest.model_dump_json(indent=2) + "\n")
    (out / FROZEN_FILE).write_text(f"{manifest_sha}\n")
    return manifest


def read_release(out: Path) -> Release:
    """The Release frozen under `out`, after checking its manifest hash and FROZEN file."""
    release = Release.model_validate_json((out / RELEASE_FILE).read_text())
    digest = hashlib.sha256(canonical_json(release.items).encode()).hexdigest()
    frozen = (out / FROZEN_FILE).read_text().strip()
    if digest != release.manifest_sha256 or frozen != digest:
        raise ValueError(f"{out}: items hash {digest}, manifest {release.manifest_sha256},"
                         f" FROZEN {frozen}")
    return release


def _reports_by_episode(reports: Sequence[QAReport]) -> dict[str, QAReport]:
    by_episode: dict[str, QAReport] = {}
    for report in reports:
        if report.episode_id in by_episode:
            raise ReleaseRefused([f"two QAReports for episode {report.episode_id}"])
        by_episode[report.episode_id] = report
    return by_episode


def _problems(
    episodes: Sequence[Episode],
    reports: Mapping[str, QAReport],
    seeds: Mapping[str, int | None],
    train: tuple[int, int],
) -> list[str]:
    problems = []
    ids = Counter(e.episode_id for e in episodes)
    problems += [f"episode id {i} given {n} times" for i, n in ids.items() if n > 1]
    copies = [e for e in episodes if is_benchmark_copy(e)]
    if copies:
        names = sorted({str(e.meta.benchmark_copy_id) for e in copies})
        problems.append(
            f"{len(copies)} episode(s) belong to benchmark copies {names}: a copy never"
            f" enters a release (design 9.2), e.g. {copies[0].episode_id}"
        )
    start, stop = train
    for e in episodes:
        seed = seeds.get(e.episode_id)
        if e.split != "train":
            problems.append(f"{e.episode_id}: split {e.split!r}, a release takes only train")
        if seed is not None and not start <= seed < stop:
            problems.append(
                f"{e.episode_id}: condition seed {seed} outside train [{start}, {stop}) (D5)"
            )
        if seed is None and e.operator_kind == "machine":
            problems.append(f"{e.episode_id}: machine-made episode without a seed to check")
        if e.episode_id not in reports:
            problems.append(f"{e.episode_id}: no QAReport")
    known = set(ids)
    problems += [f"QAReport {r.report_id} is for {i}, not an episode given"
                 for i, r in reports.items() if i not in known]
    return problems


def _excluded(report: QAReport | None) -> bool:
    return report is None or report.decision not in INCLUDED


def _item(episode: Episode, report: QAReport, seed: int | None) -> dict[str, Any]:
    return {
        "episode_id": episode.episode_id,
        "weight": 1.0,
        "excluded": _excluded(report),
        "decision": report.decision,
        "reasons": list(report.reasons),
        "qa_report_id": report.report_id,
        "threshold_version": report.threshold_version,
        "kind": episode.kind,
        "is_root": episode.is_root,
        "source_id": episode.source_id,
        "source_detail": episode.meta.source_detail,
        "condition_id": episode.condition_id,
        "seed": seed,
        "license": episode.license,
        "bundle_uri": episode.bundle_uri,
    }


def _counts(
    episodes: Sequence[Episode],
    reports: Mapping[str, QAReport],
    included: Sequence[Episode],
    seeds: Mapping[str, int | None],
) -> dict[str, Any]:
    return {
        "episodes": len(episodes),
        "included": len(included),
        "excluded": len(episodes) - len(included),
        "by_decision": dict(Counter(reports[e.episode_id].decision for e in episodes)),
        "by_kind": dict(Counter(e.kind for e in included)),
        "by_is_root": {str(k).lower(): v for k, v in Counter(e.is_root for e in included).items()},
        "by_source": dict(Counter(str(e.meta.source_detail) for e in included)),
        "seed_unknown": sum(seeds.get(e.episode_id) is None for e in episodes),
    }
