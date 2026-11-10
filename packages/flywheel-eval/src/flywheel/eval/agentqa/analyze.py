"""Code's half of each report: facts and candidates per stage (DA-20 AC 2, 3).

One function per stage of design 9.3. Each reads loaded artifacts, adds facts to
the book and proposes candidates; none of them calls a model.

    dataset    QA reports of `fw data qa` (one finding per coded QA reason), replay
               reports, the dataset report; hint: episodes with the same QA
               fingerprint (D5), since no QA check compares episodes (DA-31 doc 7)
    train      DA-08's `diagnose_train` on the job's metrics.jsonl (T1-T8), loss summary
    inference  DA-13's R1 and R2 on an RTC log, latency p50/p99, boundary jumps
    stage1     probe P1 accuracy by question type
    stage3     probe P3: O1-O4 against `offline` thresholds of agent.yaml
    eval       Score and Cluster: success rate, first failed step, failure kinds

Targets are spelled as DA-31 matches them: `episode_000012` on a dataset copy,
`train/<job>` and `rtc/<job>` on a log copy.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from flywheel.contracts.agentqa import FINDING_CODE
from flywheel.contracts.artifacts import (
    DatasetReport,
    ProbeP1,
    ProbeP3,
    QAReport,
    ReplayReport,
    RTCInferenceRecord,
)
from flywheel.contracts.entities import Cluster, Score
from flywheel.contracts.training import TrainingMetric
from flywheel.eval.agentqa.facts import Analysis
from flywheel.eval.agentqa.inputs import InputSet, Loaded
from flywheel.eval.api import DEFAULT_SYSTEM_CONFIG, DEFAULT_TRAIN_CONFIG, diagnose_train

# A QA reason starts "<check> (<code>): ..." (flywheel.data.qa.checks._judge).
_REASON = re.compile(r"^(?P<check>\S+) \((?P<code>[A-Z][0-9]+)\):\s*(?P<detail>.*)$")
_CODE = re.compile(FINDING_CODE)


# Which side of its threshold a lane detector flags (#175: Nemotron read T6's
# "value below threshold" as healthy). DA-08's `Finding` and DA-13's
# `SystemFinding` carry no direction, so it is copied here from the detectors
# (diagnosis/train/*.py, diagnosis/system/runtime.py) and checked on every
# finding they raise (`_direction`): a finding that disagrees gets no direction
# fact and a note, never a wrong one.
FLAG_WHEN: dict[str, str] = {
    "T1": ">",   # loss above k times the minimum of its window
    "T2": "<",   # val loss dropped less than min_relative_drop
    "T3": ">=",  # val rose while train fell, at least m_measurements in a row
    "T4": "<",   # a group's loss dropped less than min_group_drop
    "T5": "<",   # predicted variance of a dim under epsilon
    "T6": "<",   # pred_std / target_std under min_std_ratio
    "T7": ">",   # relative drop of a P4 metric over max_relative_drop
    "T8": ">",   # gradient norm over the frozen tolerance or max_grad_norm
    "R1": ">",   # latency percentile over tau_lat_s
    "R2": ">",   # chunks over the RTC delay, more than max_underruns
}
_HOLDS = {">": float.__gt__, "<": float.__lt__, ">=": float.__ge__}


def flag_rule(op: str, left: str = "value") -> str:
    """The text of a direction fact: `value < threshold` is the faulty side."""
    return f"{left} {op} threshold"


def _direction(analysis: Analysis, code: str, value: object, threshold: float,
               ref: str) -> str | None:
    """The direction fact of `code`, if the finding lies on the side the table says."""
    op = FLAG_WHEN.get(code)
    if op is None or not isinstance(value, (int, float)):
        return None
    if not _HOLDS[op](float(value), float(threshold)):
        analysis.notes.append(
            f"{code}: value {value} is not {op} threshold {threshold}; direction left out"
        )
        return None
    return analysis.book.add(f"{code}_flag_when", flag_rule(op), ref)


def episode_ref(index: int) -> str:
    """The parquet stem DA-27's manifest names an episode by."""
    return f"episode_{index:06d}"


@dataclass(frozen=True)
class OfflineThresholds:
    """O1-O4 of design 10 on probe P3. All values are assumptions until calibrated."""

    group_error: float = 0.3
    chunk_growth: float = 2.0  # last chunk position error / first
    hand_event_steps: float = 3.0


def analyze_dataset(found: InputSet, subject_ref: str) -> Analysis:
    analysis = Analysis(subject_ref, "dataset", [x.to_input() for x in found.loaded])
    book = analysis.book
    index: dict[str, int] = {}
    for item in found.of("episode_index"):
        index.update(item.records[0])
    aliases = {episode_id: episode_ref(i) for episode_id, i in index.items()}

    def target(episode_id: str) -> str:
        return aliases.get(episode_id, episode_id)

    analysis.units = tuple(sorted(set(aliases.values())))
    report = found.one("dataset_report")
    if report is not None:
        dr: DatasetReport = report.records[0]
        book.add("episode_count", dr.episode_count, report.ref, "episodes")
        for source, failed in dr.failed_checks_by_source.items():
            for check, count in sorted(failed.items(), key=lambda kv: -kv[1])[:5]:
                book.add(f"failed_{check}@{source}", count, report.ref, "episodes")

    qa = found.one("qa_reports")
    if qa is not None:
        reports: Sequence[QAReport] = qa.records
        decisions = Counter(r.decision for r in reports)
        for decision in ("pass", "flag", "quarantine", "reject"):
            book.add(f"qa_{decision}", decisions.get(decision, 0), qa.ref, "episodes")
        failed_by_check: Counter[str] = Counter()
        for r in reports:
            failed_by_check.update(c.name for c in r.checks if not c.passed)
        for check, count in failed_by_check.most_common():
            book.add(f"qa_failed_{check}", count, qa.ref, "episodes")
        for r in reports:
            unit = target(r.episode_id)
            by_name = {c.name: c for c in r.checks}
            for reason in r.reasons:
                m = _REASON.match(reason)
                if not m or not _CODE.fullmatch(m["code"]):
                    analysis.notes.append(f"{unit}: uncoded QA reason: {reason}")
                    continue
                qa_check = by_name.get(m["check"])
                evidence = []
                if qa_check is not None:
                    evidence.append(book.add(f"{m['check']}_value@{unit}", qa_check.value, qa.ref))
                    evidence.append(book.shared(
                        f"{m['check']}_threshold", f"{m['check']}_threshold@{unit}",
                        qa_check.threshold, qa.ref,
                    ))
                    # A QA check states no direction either; a failed one lies on its
                    # faulty side (most fail above, min_frames below).
                    if not qa_check.passed and qa_check.value != qa_check.threshold:
                        op = ">" if qa_check.value > qa_check.threshold else "<"
                        evidence.append(book.shared(
                            f"{m['check']}_flag_when", f"{m['check']}_flag_when@{unit}",
                            flag_rule(op), qa.ref,
                        ))
                evidence.append(book.add(f"decision@{unit}", r.decision, qa.ref))
                analysis.propose(m["code"], unit, evidence, "code", reason)
        _duplicate_hint(analysis, reports, target, qa)

    for item in found.of("replay_reports"):
        for rr in item.records:
            _replay(analysis, rr, target(rr.episode_id), item)
    return analysis


def _duplicate_hint(
    analysis: Analysis, reports: Sequence[QAReport], target: Callable[[str], str], qa: Loaded
) -> None:
    """Episodes whose QA check values agree to 9 digits: maybe the same recording twice."""
    groups: dict[tuple[tuple[str, float], ...], list[str]] = defaultdict(list)
    for r in reports:
        values = tuple(sorted((c.name, round(c.value, 9)) for c in r.checks))
        if len(values) >= 3 and any(v != 0 for _, v in values):
            groups[values].append(target(r.episode_id))
    for members in groups.values():
        if len(members) < 2:
            continue
        members = sorted(members)
        group_id = analysis.book.add(
            f"same_qa_fingerprint:{'+'.join(members)}", len(members), qa.ref, "episodes"
        )
        for unit in members[1:]:
            analysis.propose(
                "D5",
                unit,
                [group_id],
                "hint",
                f"QA check values of {unit} equal those of {members[0]} (possible duplicate)",
            )


def _replay(analysis: Analysis, rr: ReplayReport, unit: str, item: Loaded) -> None:
    for issue in rr.issues:
        if not _CODE.fullmatch(issue.code):
            continue
        evidence = [analysis.book.add(f"replay_{rr.mode}_{issue.code}_frames@{unit}",
                                      len(issue.frames), item.ref, "frames")]
        for group, error in sorted(rr.error_by_group.items()):
            evidence.append(
                analysis.book.add(f"replay_{rr.mode}_error_{group}@{unit}", error, item.ref)
            )
        analysis.propose(issue.code, unit, evidence, "code", f"replay {rr.mode}: {issue.detail}")


def job_unit(path: Path, part: str) -> str:
    """`train/<job>` or `rtc/<job>`: the job dir name under its part."""
    return f"{part}/{path.parent.name}"


def analyze_train(
    metrics: Loaded, unit: str, config: Path = DEFAULT_TRAIN_CONFIG
) -> Analysis:
    analysis = Analysis(metrics.ref, "train", [metrics.to_input()], units=(unit,))
    book = analysis.book
    rows: Sequence[TrainingMetric] = metrics.records
    train = [r for r in rows if r.split == "train"]
    val = [r for r in rows if r.split == "val"]
    book.add("steps_logged", len(rows), metrics.ref, "rows")
    for name, series in (("train", train), ("val", val)):
        losses = np.array([float(r.loss) for r in series], dtype=np.float64)
        if losses.size == 0:
            continue
        finite = losses[np.isfinite(losses)]
        book.add(f"{name}_loss_first", float(losses[0]), metrics.ref)
        book.add(f"{name}_loss_last", float(losses[-1]), metrics.ref)
        if finite.size:
            book.add(f"{name}_loss_min", float(finite.min()), metrics.ref)
        book.add(f"{name}_nonfinite_losses", int(losses.size - finite.size), metrics.ref, "rows")
        book.add(f"{name}_last_step", series[-1].step, metrics.ref, "steps")
    if train:
        last = train[-1]
        for group, loss in sorted(last.loss_by_group.items()):
            book.add(f"loss_last_{group}", loss, metrics.ref)
    diagnosis = diagnose_train(metrics.path, config)
    seen: Counter[str] = Counter()
    for finding in diagnosis.findings:
        # Each finding's own value and start step under its own name (#175): one T6 per
        # dimension used to share the facts of dimension 0. Thresholds are shared.
        code = finding.code
        suffix = fact_suffix(finding.group, finding.dim)
        seen[code + suffix] += 1
        if seen[code + suffix] > 1:  # two findings of one code on no group or dim (T8 a, b)
            suffix += f"_{seen[code + suffix]}"
        evidence = [book.add(f"{code}_value{suffix}", _num(finding.value), metrics.ref)]
        if finding.threshold is not None:
            evidence.append(book.shared(f"{code}_threshold", f"{code}_threshold{suffix}",
                                        finding.threshold, metrics.ref))
            flag = _direction(analysis, code, finding.value, finding.threshold, metrics.ref)
            if flag is not None:
                evidence.append(flag)
        evidence.append(
            book.add(f"{code}_start_step{suffix}", finding.start_step, metrics.ref, "steps")
        )
        where = f" group {finding.group}" if finding.group else ""
        where += f" dim {finding.dim}" if finding.dim is not None else ""
        analysis.propose(code, unit, evidence, "code", f"DA-08 {code}{where}")
    for skip in diagnosis.skipped:
        analysis.notes.append(f"{skip.code} not judged: {skip.reason}")
    return analysis


def fact_suffix(group: str | None, dim: int | None) -> str:
    """`_<group>`, `_dim<n>` or both: what tells one finding's facts from another's."""
    suffix = f"_{group}" if group else ""
    return suffix + (f"_dim{dim}" if dim is not None else "")


def _num(value: float | str) -> float | str:
    return value if isinstance(value, str) else float(value)


def analyze_rtc(log: Loaded, unit: str, config: Path = DEFAULT_SYSTEM_CONFIG) -> Analysis:
    # No api function takes an RTC log alone yet (diagnose_episode_system needs a whole
    # trace), so R1 and R2 are called as DA-31's code layer calls them.
    from flywheel.eval.config import load_system_thresholds
    from flywheel.eval.diagnosis.system.runtime import check_r1, check_r2

    analysis = Analysis(log.ref, "inference", [log.to_input()], units=(unit,))
    book = analysis.book
    records: tuple[RTCInferenceRecord, ...] = tuple(log.records)
    book.add("chunks", len(records), log.ref, "chunks")
    after = [r for r in records if r.chunk_index > 0]
    if after:
        latency = np.array([r.chunk_received_s - r.observation_sent_s for r in after])
        book.add("latency_p50_s", float(np.percentile(latency, 50)), log.ref, "s")
        book.add("latency_p99_s", float(np.percentile(latency, 99)), log.ref, "s")
        book.add("latency_max_s", float(latency.max()), log.ref, "s")
        delay = np.array([r.delay_steps for r in after])
        book.add("delay_steps_max", int(delay.max()), log.ref, "steps")
        jumps = np.array([r.boundary_jump for r in after])
        book.add("boundary_jump_p99", float(np.percentile(jumps, 99)), log.ref)
    system, _ = load_system_thresholds(config)
    for check, cfg in ((check_r1, system.r1), (check_r2, system.r2)):
        result = check(records, cfg)  # type: ignore[arg-type]
        for finding in result.findings:
            evidence = [book.add(f"{finding.code}_value", finding.value, log.ref)]
            if finding.threshold is not None:
                evidence.append(book.add(f"{finding.code}_threshold", finding.threshold, log.ref))
                flag = _direction(analysis, finding.code, finding.value, finding.threshold,
                                  log.ref)
                if flag is not None:
                    evidence.append(flag)
            analysis.propose(
                finding.code, unit, evidence, "code", f"DA-13 {finding.code} at {finding.where}"
            )
        for skip in result.skipped:
            analysis.notes.append(f"{skip.code} not judged: {skip.reason}")
    return analysis


def analyze_stage1(probe: Loaded) -> Analysis:
    p1: ProbeP1 = probe.records[0]
    analysis = Analysis(probe.ref, "stage1", [probe.to_input()], units=(p1.checkpoint_id,))
    for question_type, accuracy in sorted(p1.accuracy_by_question_type.items()):
        analysis.book.add(f"p1_accuracy_{question_type}", accuracy, probe.ref)
    return analysis


def analyze_stage3(probe: Loaded, thresholds: OfflineThresholds) -> Analysis:
    p3: ProbeP3 = probe.records[0]
    unit = p3.checkpoint_id
    analysis = Analysis(probe.ref, "stage3", [probe.to_input()], units=(unit,))
    book = analysis.book
    limit = book.add("o1_group_error_threshold", thresholds.group_error, probe.ref)
    for group, error in sorted(p3.error_by_group.items()):
        fid = book.add(f"p3_error_{group}", error, probe.ref)
        if error > thresholds.group_error:
            flag = book.add("O1_flag_when", flag_rule(">", "p3_error"), probe.ref)
            analysis.propose("O1", unit, [fid, limit, flag], "code", f"P3 error of {group}")
    pos = p3.error_by_chunk_pos
    if len(pos) >= 2 and pos[0] > 0:
        first = book.add("p3_error_chunk_first", pos[0], probe.ref)
        last = book.add("p3_error_chunk_last", pos[-1], probe.ref)
        if pos[-1] / pos[0] > thresholds.chunk_growth:
            growth = book.add("o2_growth_threshold", thresholds.chunk_growth, probe.ref)
            flag = book.add("O2_flag_when", flag_rule(">", "last / first"), probe.ref)
            analysis.propose("O2", unit, [first, last, growth, flag], "code",
                             "error grows in chunk")
    hand = book.add("p3_hand_event_offset_steps", p3.hand_event_offset_steps, probe.ref, "steps")
    if abs(p3.hand_event_offset_steps) > thresholds.hand_event_steps:
        lim = book.add("o3_threshold_steps", thresholds.hand_event_steps, probe.ref, "steps")
        flag = book.add("O3_flag_when", flag_rule(">", "|offset|"), probe.ref)
        analysis.propose("O3", unit, [hand, lim, flag], "code", "hand open/close offset")
    if p3.out_of_limit_dims:
        fid = book.add("p3_out_of_limit_dims", len(p3.out_of_limit_dims), probe.ref, "dims")
        analysis.propose("O4", unit, [fid], "code", f"dims {p3.out_of_limit_dims}")
    return analysis


def analyze_eval(found: InputSet, subject_ref: str) -> Analysis:
    analysis = Analysis(subject_ref, "eval", [x.to_input() for x in found.loaded])
    book = analysis.book
    for item in found.of("scores"):
        scores: Sequence[Score] = item.records
        book.add("episodes_scored", len(scores), item.ref, "episodes")
        book.add("success", sum(1 for s in scores if s.success), item.ref, "episodes")
        if scores:
            won = sum(1 for s in scores if s.success)
            book.add("success_rate", won / len(scores), item.ref)
        steps = Counter(s.first_failed_step for s in scores if s.first_failed_step is not None)
        for step, count in sorted(steps.items()):
            book.add(f"first_failed_step_{step}", count, item.ref, "episodes")
        kinds = Counter(s.failure_kind for s in scores if s.failure_kind)
        for kind, count in kinds.most_common():
            book.add(f"failure_kind_{kind}", count, item.ref, "episodes")
    for item in found.of("clusters"):
        clusters: Sequence[Cluster] = item.records
        for c in clusters:
            book.add(f"cluster_{c.id}_members", len(c.member_episode_ids), item.ref, "episodes")
    analysis.units = tuple(
        s.episode_id for item in found.of("scores") for s in item.records
    )
    return analysis
