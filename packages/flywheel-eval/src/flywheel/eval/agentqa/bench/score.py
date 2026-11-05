"""Precision, recall, false alarms and time to report, per layer (DA-31 AC 2).

Rules of design 27/10/2026 section 9.2 (decided 3/11/2026, issue #34):

- Recall is per defect kind, never pooled: a defect counts as caught when the
  layer reports its target with the defect's code.
- Precision is per code, since a finding carries a code and not a kind: of the
  (target, code) pairs the layer reported on the copy with defects, the share that
  match a defect.
- False alarm rate is on the clean copy: units (episodes or jobs) with at least
  one report, over all units. A target that names no unit (the agent writes
  `dataset`, or a path outside the copy) is a report too: each such target adds
  one to the count, the units stay the denominator.
- Time to report: from when the job finished to when the layer's report existed.

Two rules of this scorer, written down because the design leaves them open:

- **Natural findings.** The clean copy is the same data without the injected
  defects, so a (target, code) a layer reports on both copies is about the data
  itself, not about an injected defect: the check would have fired anyway. It is
  listed as natural and left out of precision and recall; a defect whose own
  (target, code) is natural is counted as masked, never as caught. On psi-data
  this matters: DA-17 found 73 of 99 episodes fail their replay, which a QA check
  reports as D6 on both copies.
- **Duplicates.** A `duplicate_episode` defect writes a copy of episode A over
  slot B; a detector of duplicates can name either one, so a report of A or of B
  with the defect's code catches it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from flywheel.contracts.artifacts import Defect
from flywheel.eval.agentqa.bench.detections import LAYERS, Detection, Layer
from flywheel.eval.agentqa.bench.session import CopyResult, GroupResult

DUPLICATE_KIND = "duplicate_episode"


@dataclass(frozen=True)
class Rate:
    """`hit` of `total`; `value` is None when there is nothing to divide by."""

    hit: int
    total: int

    @property
    def value(self) -> float | None:
        return self.hit / self.total if self.total else None


@dataclass(frozen=True)
class Verdict:
    """One reported (target, code) on the copy with defects, judged against the key."""

    detection: Detection
    label: str  # "hit", "false" or "natural"
    defects: tuple[int, ...] = ()  # indexes into the manifest's defects it catches


@dataclass(frozen=True)
class LayerScore:
    """Everything AC 2 asks for, for one layer on one group."""

    layer: Layer
    recall_by_kind: Mapping[str, Rate]
    masked_by_kind: Mapping[str, int]
    precision_by_code: Mapping[str, Rate]
    false_alarm: Rate
    not_a_unit: tuple[str, ...]  # clean-copy targets that name no unit, in `false_alarm`
    clean_reports: tuple[tuple[str, str], ...]
    natural: tuple[tuple[str, str], ...]
    seconds_to_report: Mapping[str, float | None]
    verdicts: tuple[Verdict, ...]
    caught: frozenset[int]
    uncoded: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class GroupScore:
    group: str
    injected_id: str
    clean_id: str
    kinds: tuple[tuple[str, str], ...]  # (kind, code) in manifest order
    defects: tuple[Defect, ...]
    layers: Mapping[Layer, LayerScore]


def kind_of(defect: Defect) -> str:
    kind = defect.parameters.get("kind")
    return kind if isinstance(kind, str) and kind else defect.code


def matches(detection: Detection, defect: Defect) -> bool:
    """Whether a reported (target, code) is a report of `defect`."""
    if detection.code != defect.code:
        return False
    if detection.target == defect.target_ref:
        return True
    original = defect.parameters.get("original_id")
    return kind_of(defect) == DUPLICATE_KIND and detection.target == original


def judge(injected: CopyResult, clean: CopyResult, layer: Layer) -> tuple[Verdict, ...]:
    """Label every (target, code) the layer reported on the copy with defects.

    Several findings with the same (target, code), as an agent may write, are
    judged once each; precision counts the distinct pairs (`score_layer`).
    """
    natural = _pairs(clean.runs[layer].detections)
    defects = injected.manifest.defects
    verdicts = []
    for detection in injected.runs[layer].detections:
        if (detection.target, detection.code) in natural:
            verdicts.append(Verdict(detection, "natural"))
            continue
        caught = tuple(i for i, d in enumerate(defects) if matches(detection, d))
        verdicts.append(Verdict(detection, "hit" if caught else "false", caught))
    return tuple(verdicts)


def score_layer(group: GroupResult, layer: Layer) -> LayerScore:
    injected, clean = group.injected, group.clean
    defects = injected.manifest.defects
    verdicts = judge(injected, clean, layer)
    natural_pairs = _pairs(clean.runs[layer].detections)
    caught = frozenset(i for v in verdicts for i in v.defects)
    masked = {
        i for i, d in enumerate(defects)
        if any((t, d.code) in natural_pairs for t in _targets(d))
    }
    kinds = list(dict.fromkeys(kind_of(d) for d in defects))
    recall = {
        kind: Rate(
            hit=sum(1 for i, d in enumerate(defects) if kind_of(d) == kind and i in caught),
            total=sum(1 for d in defects if kind_of(d) == kind),
        )
        for kind in kinds
    }
    masked_by_kind = {
        kind: sum(1 for i in masked if kind_of(defects[i]) == kind) for kind in kinds
    }
    labels: dict[tuple[str, str], str] = {}
    for v in verdicts:
        pair = (v.detection.target, v.detection.code)
        if v.label == "hit" or pair not in labels:
            labels[pair] = v.label
    codes = sorted({d.code for d in defects} | {code for (_, code) in labels})
    precision = {
        code: Rate(
            hit=sum(1 for (_, c), lab in labels.items() if c == code and lab == "hit"),
            total=sum(1 for (_, c), lab in labels.items() if c == code and lab != "natural"),
        )
        for code in codes
    }
    clean_run = clean.runs[layer]
    targets = {d.target for d in clean_run.detections}
    flagged = targets & set(clean_run.units)
    not_a_unit = tuple(sorted(targets - flagged))
    return LayerScore(
        layer=layer,
        recall_by_kind=recall,
        masked_by_kind=masked_by_kind,
        precision_by_code=precision,
        false_alarm=Rate(len(flagged) + len(not_a_unit), len(clean_run.units)),
        not_a_unit=not_a_unit,
        clean_reports=tuple(sorted(_pairs(clean_run.detections))),
        natural=tuple(sorted(p for p, lab in labels.items() if lab == "natural")),
        seconds_to_report={c.dataset_id: _seconds(c, layer) for c in (injected, clean)},
        verdicts=verdicts,
        caught=caught,
        uncoded={c.dataset_id: c.runs[layer].uncoded for c in (injected, clean)
                 if c.runs[layer].uncoded},
    )


def score_group(group: GroupResult) -> GroupScore:
    defects = tuple(group.injected.manifest.defects)
    return GroupScore(
        group=group.group,
        injected_id=group.injected.dataset_id,
        clean_id=group.clean.dataset_id,
        kinds=tuple(dict.fromkeys((kind_of(d), d.code) for d in defects)),
        defects=defects,
        layers={layer: score_layer(group, layer) for layer in LAYERS},
    )


def _pairs(detections: Iterable[Detection]) -> set[tuple[str, str]]:
    return {(d.target, d.code) for d in detections}


def _targets(defect: Defect) -> list[str]:
    original = defect.parameters.get("original_id")
    if kind_of(defect) == DUPLICATE_KIND and isinstance(original, str):
        return [defect.target_ref, original]
    return [defect.target_ref]


def _seconds(copy: CopyResult, layer: Layer) -> float | None:
    reported = copy.runs[layer].reported_at
    if copy.job_finished_at is None or reported is None:
        return None
    return (reported - copy.job_finished_at).total_seconds()
