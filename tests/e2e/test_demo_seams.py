"""Seams of the 13/11 demo chain: every artifact that crosses from one lane to another.

Each seam names who writes the artifact, who reads it and the contract both sides
agree on (07 section 2.0, 03 section 7.3). A seam holds when its contract exists in
`flywheel.contracts` and its shared example in `flywheel.testkit` validates against
it, so writer and reader code against the same file instead of examples of their
own. Where both sides already have code, a test below runs the writer's output
through the reader.

A missing contract or example is a gap, not a bug: `gap_outcome` decides from the
story's deadline whether it is reported as an expected failure or fails the run.
An example that exists but does not validate always fails.
"""

from __future__ import annotations

import importlib
import json
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, NoReturn

import pytest
import yaml
from flywheel.contracts.artifacts import ActionLayout
from flywheel.contracts.training import TrainDiagnosis
from flywheel.contracts.v0 import ControlSpec
from flywheel.eval.api import diagnose_train
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures"
TRAIN_CONFIG = ROOT / "configs/eval/diagnosis/train.yaml"
G1_EMBODIMENT = ROOT / "configs/embodiments/g1.yaml"
DA19_SAMPLE = ROOT / "packages/flywheel-psi0/tests/unit/trainer/fixtures/metrics_sample.jsonl"

MERGE_FREEZE = date(2026, 11, 11)


@dataclass(frozen=True)
class Seam:
    part: int  # demo part of design 27/10 section 11
    artifact: str
    writer: str
    reader: str
    contract: str  # "module:Class" under flywheel.contracts
    example: str  # path under the testkit fixtures, .json or .jsonl
    story: str
    due: str | None  # "d/m" of 2026; None while unassigned

    @property
    def deadline(self) -> date | None:
        if self.due is None:
            return None
        day, month = self.due.split("/")
        return date(2026, int(month), int(day))


# Demo part, artifact, writer, reader, contract under flywheel.contracts, shared example under
# the testkit fixtures, story, merge deadline of 07 section 2.4 (None while unassigned).
# fmt: off
SEAMS = tuple(Seam(*row) for row in (
    (3, "ActionLayout", "Long (DA-01)", "mọi làn",
     "artifacts:ActionLayout", "artifacts/ActionLayout.json", "DA-01", "5/11"),
    (3, "Episode", "Thông (DA-03), Hưng (DA-04)", "Long (catalog), Châu",
     "artifacts:Episode", "artifacts/Episode.json", "DA-03", "9/11"),
    (3, "QAReport", "Thông (DA-03)", "Hưng (DA-20)",
     "artifacts:QAReport", "artifacts/QAReport.json", "DA-03", "9/11"),
    (3, "ReplayReport", "Thông (DA-17)", "Hưng (DA-20)",
     "artifacts:ReplayReport", "artifacts/ReplayReport.json", "DA-17", "9/11"),
    (3, "DatasetReport", "Thông (DA-03)", "Hưng (DA-20)",
     "artifacts:DatasetReport", "artifacts/DatasetReport.json", "DA-03", "9/11"),
    (3, "ReleaseManifest", "Thông (DA-03)", "Châu, Hiếu (export)",
     "v0:ReleaseManifest", "artifacts/ReleaseManifest.json", "DA-03", "9/11"),
    (4, "DefectManifest", "Thông (DA-27)", "Châu (DA-31)",
     "artifacts:DefectManifest", "artifacts/DefectManifest.json", "DA-27", "6/11"),
    (4, "RTCInferenceRecord", "Hiếu", "Châu, Hưng",
     "artifacts:RTCInferenceRecord", "artifacts/RTCInferenceRecord.json", "DA-23", "10/11"),
    (4, "AgentReport", "Hưng (DA-20)", "Long (fw review), Châu (DA-31)",
     "agentqa:AgentReport", "artifacts/AgentReport.json", "#34", "5/11"),
    (4, "AgentReview", "kỹ sư (fw review)", "Long",
     "agentqa:AgentReview", "artifacts/AgentReview.json", "#34", "5/11"),
    (6, "TrainingMetric", "Hiếu (DA-19)", "Châu (DA-08)",
     "training:TrainingMetric", "training/clean.jsonl", "DA-19", "6/11"),
    (6, "TrainDiagnosis", "Châu (DA-08)", "Long (decide), Hưng (DA-20)",
     "training:TrainDiagnosis", "training/diagnosis.json", "DA-08", "2/11"),
    (6, "RolloutResult", "Hiếu (SimpleSim; DA-38 hook)", "Châu (scorer, DA-13 R6)",
     "v0:RolloutResult", "artifacts/RolloutResult.json", "DA-23", "10/11"),
    (6, "TraceStep", "Hiếu (DA-38 hook: steps.jsonl)", "Châu (DA-13)",
     "trace:TraceStep", "artifacts/TraceStep.json", "#31", "6/11"),
    (6, "CameraParams", "Hiếu (DA-38 hook: camera_params.jsonl)", "Châu (DA-13)",
     "trace:CameraParams", "artifacts/CameraParams.json", "#31", "6/11"),
    (6, "Score", "Châu (scorer)", "Long (decide), Hưng",
     "entities:Score", "artifacts/Score.json", "scorer 3.3", "8/11"),
    (6, "Cluster", "Châu (scorer)", "Long (decide), Hưng",
     "entities:Cluster", "artifacts/Cluster.json", "scorer 3.3", "8/11"),
    (6, "EvidenceCard", "làn Đánh giá (hợp đồng: Hiếu, DA-39)", "Long (decide)",
     "evidence:EvidenceCard", "artifacts/EvidenceCard.json", "DA-39", "11/11"),
    (6, "Decision", "Long (decide)", "Long (ledger, reports)",
     "entities:Decision", "artifacts/Decision.json", "S1-10", "5/11"),
    (6, "LedgerEntry", "mọi job", "Long (ledger)",
     "entities:LedgerEntry", "artifacts/LedgerEntry.json", "S1-10", "5/11"),
))
# fmt: on


def gap_outcome(deadline: date | None, today: date) -> Literal["xfail", "fail"]:
    """Whether a missing contract or example is still expected on `today`.

    "xfail" keeps CI green and lists the gap in the report; "fail" turns CI red
    for every PR until the gap is closed.

    A late story alone does not turn CI red: that would block every unrelated PR
    the morning after someone else's deadline, and lateness already shows in the
    daily report (issue #2). From the day after the last team merge the chain has
    to be whole for the dry run of 12/11, so a gap past its deadline fails; a seam
    without an owner or deadline fails too, since nobody is going to close it.
    """
    if today <= MERGE_FREEZE:
        return "xfail"
    if deadline is None or today > deadline:
        return "fail"
    return "xfail"


def gap(seam: Seam, what: str) -> NoReturn:
    deadline = f"hạn {seam.due}" if seam.due else "chưa có hạn"
    message = (
        f"phần {seam.part} · {seam.artifact}: {what} · {seam.writer} → {seam.reader} · "
        f"{seam.story}, {deadline}"
    )
    if gap_outcome(seam.deadline, date.today()) == "fail":
        pytest.fail(message)
    pytest.xfail(message)


def resolve(seam: Seam) -> type[BaseModel]:
    module_name, _, name = f"flywheel.contracts.{seam.contract}".partition(":")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != module_name:
            raise  # the contract module exists but is broken
        gap(seam, f"chưa có `{module_name}`")
    model = getattr(module, name, None)
    if model is None:
        gap(seam, f"chưa có hợp đồng `{name}`")
    return model  # type: ignore[no-any-return]


@pytest.mark.e2e_fake
@pytest.mark.parametrize("seam", SEAMS, ids=lambda seam: f"{seam.part}-{seam.artifact}")
def test_seam_has_contract_and_shared_example(seam: Seam) -> None:
    model = resolve(seam)
    path = FIXTURES / seam.example
    if not path.exists():
        gap(seam, f"chưa có file mẫu `{seam.example}` trong testkit")
    lines = (
        path.read_text(encoding="utf-8").splitlines()
        if path.suffix == ".jsonl"
        else [path.read_text()]
    )
    for line in lines:
        value = model.model_validate_json(line)
        assert model.model_validate_json(value.model_dump_json()) == value


def g1_layout() -> ActionLayout:
    seam = SEAMS[0]
    if not G1_EMBODIMENT.exists():
        gap(seam, "chưa có `configs/embodiments/g1.yaml`")
    raw = yaml.safe_load(G1_EMBODIMENT.read_text(encoding="utf-8"))
    return ActionLayout.model_validate(raw["action_layout"])


# ACTION_SLICES_36D of Psi0 at cda3fdf (design 27/10 section 9.2): hands, arms,
# waist, torso height, relative velocity, turn flag, target heading.
G1_SLICES = ((0, 14), (14, 28), (28, 31), (31, 32), (32, 34), (34, 35), (35, 36))


@pytest.mark.e2e_fake
def test_g1_action_layout_follows_psi0_slices() -> None:
    layout = g1_layout()
    dims = layout.dimensions
    assert len(dims) == 36, "G1 action has 36 dims with no padding (design 27/10 section 6.1)"
    assert not any(dim.masked for dim in dims)
    groups = [{dims[i].group for i in range(start, end)} for start, end in G1_SLICES]
    assert all(len(group) == 1 for group in groups), "one group per Psi0 slice"
    labels = [group.pop() for group in groups]
    assert all(a != b for a, b in zip(labels, labels[1:], strict=False)), "adjacent slices differ"


@pytest.mark.e2e_fake
def test_g1_control_spec_pairs_every_action_dim_once() -> None:
    """Decoupled WBC channels (03 section 5.2, ADR-15): each action dim commanded once."""
    layout = g1_layout()
    raw = yaml.safe_load(G1_EMBODIMENT.read_text(encoding="utf-8"))
    spec = ControlSpec.model_validate(raw["control_spec"])
    assert spec.controller == "decoupled_wbc"
    assert [group.name for group in spec.groups] == ["upper_body", "lower_body"]
    for group in spec.groups:
        assert len(group.command_channels) == len(group.state_channels), group.name
    commands = [channel for group in spec.groups for channel in group.command_channels]
    assert commands == [dim.name for dim in layout.dimensions]


def job_dir(tmp_path: Path, log: Path, layout: ActionLayout) -> Path:
    shutil.copy(log, tmp_path / "metrics.jsonl")
    (tmp_path / "action_layout.json").write_text(layout.model_dump_json(), encoding="utf-8")
    return tmp_path


TRAINING_EXAMPLES = sorted((FIXTURES / "training").glob("*.jsonl"))


@pytest.mark.e2e_fake
@pytest.mark.parametrize("log", TRAINING_EXAMPLES, ids=lambda path: path.stem)
def test_train_diagnosis_reads_every_shared_training_example(log: Path, tmp_path: Path) -> None:
    layout = ActionLayout.model_validate_json(
        (FIXTURES / "training/action_layout.json").read_text()
    )
    diagnosis = diagnose_train(job_dir(tmp_path, log, layout), TRAIN_CONFIG)

    expected = set() if log.stem == "clean" else {log.stem.split("_")[0].upper()}
    assert {finding.code for finding in diagnosis.findings} == expected
    # What decide and the Agent QA/QC read back.
    assert TrainDiagnosis.model_validate_json(diagnosis.model_dump_json()) == diagnosis


@pytest.mark.e2e_fake
def test_psi0_metrics_log_is_diagnosed_on_the_g1_layout(tmp_path: Path) -> None:
    """DA-19's wrapper output, read by DA-08 against DA-01's layout."""
    layout = g1_layout()
    diagnosis = diagnose_train(job_dir(tmp_path, DA19_SAMPLE, layout), TRAIN_CONFIG)
    assert diagnosis.findings == [], [finding.code for finding in diagnosis.findings]


@pytest.mark.e2e_fake
def test_catalog_stores_the_shared_episode() -> None:
    """S1-10's catalog has to accept the Episode every writer validates against."""
    seam = Seam(3, "Episode → catalog", "Thông, Hưng", "Long (catalog)", "entities:Episode",
                "artifacts/Episode.json", "S1-10", "5/11")
    catalog_episode = resolve(seam)
    example = json.loads((FIXTURES / seam.example).read_text(encoding="utf-8"))
    catalog_episode.model_validate(example)


def seam_of(artifact: str) -> Seam:
    return next(seam for seam in SEAMS if seam.artifact == artifact)


@pytest.mark.e2e_fake
def test_simple_trace_hook_files_are_the_contracts_the_system_checks_read(tmp_path: Path) -> None:
    """DA-38's files of one episode, read through the contracts of DA-13's checks.

    The layout is `<job>/<trace_id>/steps.jsonl, camera_params.jsonl` (G1 on PR #48)
    plus the episode's `RolloutResult` beside them; `rtc.jsonl` is per job and joins on
    `trace_id` (PO review 3/11/2026, B1).
    """
    from flywheel_simple.trace.camera import CameraValues
    from flywheel_simple.trace.files import CAMERA_NAME, RESULT_NAME, STEPS_NAME, EpisodeDirSink
    from flywheel_simple.trace.hook import CycleRecord, EpisodeTrace

    trace_step = resolve(seam_of("TraceStep"))
    camera_params = resolve(seam_of("CameraParams"))
    rollout_result = resolve(seam_of("RolloutResult"))
    pose = (0.06, 0.02, 0.43, 0.66, 0.26, -0.26, -0.66)
    episode = EpisodeTrace(
        trace_id="job-seams-0123456789ab",
        episode_id="episode_0",
        run_plan_id="g0-DA-38-seams",
        cameras=[CameraValues("head_stereo_left", "eye_in_head", 640, 360, 224.0, 224.0,
                              320.0, 180.0, pose)],  # fmt: skip
        cycles=[CycleRecord(step, 0.02 * step, 0.0 if step == 0 else None, [0.0] * 28,
                            [0.0] * 28, [0.0] * 7, [0.0] * 7) for step in range(3)],  # fmt: skip
        sim_success=False,
    )
    EpisodeDirSink(
        tmp_path, job_id="job-seams", camera_reference_sha256="0" * 64, adapter_version="test"
    ).write(episode)

    directory = tmp_path / episode.trace_id
    steps = [
        trace_step.model_validate_json(line)
        for line in (directory / STEPS_NAME).read_text(encoding="utf-8").splitlines()
    ]
    cameras = [
        camera_params.model_validate_json(line)
        for line in (directory / CAMERA_NAME).read_text(encoding="utf-8").splitlines()
    ]
    result = rollout_result.model_validate_json((directory / RESULT_NAME).read_text())
    assert result.trace_ref.uri == directory.as_posix()  # type: ignore[attr-defined]
    trace_ids = {step.trace_id for step in steps} | {cam.trace_id for cam in cameras}  # type: ignore[attr-defined]
    assert trace_ids == {result.trace_ref.trace_id}  # type: ignore[attr-defined]
    assert result.infra_status == "ok"  # type: ignore[attr-defined]
