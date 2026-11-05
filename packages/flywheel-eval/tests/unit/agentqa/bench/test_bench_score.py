"""DA-31 AC 2: precision per code, recall per kind, false alarms, time to report.

Inputs are built with a known answer, so every number below is worked out by hand.
"""

from __future__ import annotations

from datetime import timedelta

from conftest import CLEAN, INJECTED, T0
from flywheel.contracts.artifacts import Defect, DefectManifest
from flywheel.eval.agentqa.bench.detections import Detection, Layer, LayerRun
from flywheel.eval.agentqa.bench.score import score_group
from flywheel.eval.agentqa.bench.session import CopyResult, GroupResult

UNITS = tuple(f"e{i}" for i in range(10))


def _defect(target: str, code: str, kind: str, **params: str) -> Defect:
    return Defect(target_ref=target, code=code, parameters={"kind": kind, **params})


DEFECTS = [
    _defect("e1", "D1", "nan_values"),
    _defect("e2", "D2", "drop_frames"),
    _defect("e3", "D2", "timestamp_sync_offset"),
    _defect("e4", "D5", "duplicate_episode", original_id="e0"),
    _defect("e5", "D6", "corrupted_success_label"),
]


def _run(layer: Layer, dataset_id: str, pairs: list[tuple[str, str]],
         seconds: float | None = None) -> LayerRun:
    return LayerRun(
        layer=layer,
        dataset_id=dataset_id,
        units=UNITS,
        detections=tuple(Detection(t, c) for t, c in pairs),
        reported_at=None if seconds is None else T0 + timedelta(seconds=seconds),
    )


def _copy(dataset_id: str, defects: list[Defect], code: list[tuple[str, str]],
          agent: list[tuple[str, str]]) -> CopyResult:
    return CopyResult(
        group="data",
        dataset_id=dataset_id,
        job_finished_at=T0,
        runs={"code": _run("code", dataset_id, code, 60.0),
              "agent": _run("agent", dataset_id, agent, 600.0)},
        manifest=DefectManifest(dataset_id=dataset_id, seed=1, defects=defects),
    )


def _group() -> GroupResult:
    injected = _copy(
        INJECTED, DEFECTS,
        code=[("e1", "D1"), ("e2", "D2"), ("e7", "D2"), ("e5", "D6"), ("e8", "D6"),
              ("e0", "D5")],
        agent=[("e3", "D2"), ("e9", "D7"), ("e3", "D2")],
    )
    clean = _copy(CLEAN, [], code=[("e5", "D6"), ("e8", "D6")], agent=[])
    return GroupResult("data", injected, clean)


def test_recall_is_per_kind_and_never_pooled() -> None:
    code = score_group(_group()).layers["code"]
    recall = {k: (r.hit, r.total) for k, r in code.recall_by_kind.items()}
    assert recall == {
        "nan_values": (1, 1),
        "drop_frames": (1, 1),
        "timestamp_sync_offset": (0, 1),  # same code D2 as drop_frames, still apart
        "duplicate_episode": (1, 1),  # reported on the source episode e0
        "corrupted_success_label": (0, 1),
    }
    assert code.masked_by_kind["corrupted_success_label"] == 1


def test_precision_is_per_code_and_leaves_natural_findings_out() -> None:
    code = score_group(_group()).layers["code"]
    precision = {c: (r.hit, r.total, r.value) for c, r in code.precision_by_code.items()}
    assert precision == {
        "D1": (1, 1, 1.0),
        "D2": (1, 2, 0.5),
        "D5": (1, 1, 1.0),
        "D6": (0, 0, None),  # e5 and e8 fire on the clean copy too
    }
    assert code.natural == (("e5", "D6"), ("e8", "D6"))


def test_false_alarms_are_counted_on_the_clean_copy_by_unit() -> None:
    layers = score_group(_group()).layers
    assert (layers["code"].false_alarm.hit, layers["code"].false_alarm.total) == (2, 10)
    assert layers["code"].false_alarm.value == 0.2
    assert layers["agent"].false_alarm.value == 0.0


def test_agent_findings_count_once_per_target_and_code() -> None:
    agent = score_group(_group()).layers["agent"]
    assert agent.recall_by_kind["timestamp_sync_offset"].hit == 1
    assert (agent.precision_by_code["D2"].hit, agent.precision_by_code["D2"].total) == (1, 1)
    assert (agent.precision_by_code["D7"].hit, agent.precision_by_code["D7"].total) == (0, 1)


def test_time_to_report_runs_from_job_end_and_is_unknown_without_it() -> None:
    group = _group()
    score = score_group(group).layers
    assert score["code"].seconds_to_report == {INJECTED: 60.0, CLEAN: 60.0}
    assert score["agent"].seconds_to_report[INJECTED] == 600.0
    unknown = CopyResult("data", CLEAN, None, group.clean.runs, group.clean.manifest)
    later = score_group(GroupResult("data", group.injected, unknown)).layers
    assert later["code"].seconds_to_report[CLEAN] is None


def test_a_clean_report_on_no_unit_counts_as_a_false_alarm() -> None:
    group = _group()
    clean = _copy(CLEAN, [], code=[("e5", "D6"), ("e8", "D6")],
                  agent=[("dataset", "T2"), ("dataset", "D6"), ("e4", "D1")])
    agent = score_group(GroupResult("data", group.injected, clean)).layers["agent"]
    # e4 is a unit; "dataset" is not, and counts once for its two codes: (1 + 1) / 10
    assert agent.not_a_unit == ("dataset",)
    assert (agent.false_alarm.hit, agent.false_alarm.total) == (2, 10)
    assert agent.false_alarm.value == 0.2
    assert ("dataset", "T2") in agent.clean_reports
