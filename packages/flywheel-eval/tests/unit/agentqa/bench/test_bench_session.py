"""DA-31 AC 1: read both layers on both copies, open the answer key only after that."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from conftest import CLEAN, INJECTED, T0, QAWork, Report, Seal
from flywheel.contracts.artifacts import Defect
from flywheel.eval.agentqa.bench import (
    AnswerKeyError,
    AnswerLeak,
    BenchIncomplete,
    BenchInputError,
    BenchSession,
    agent_run,
    read_qa_work,
)
from flywheel.eval.agentqa.bench import session as session_module
from flywheel.eval.agentqa.bench.detections import resolve_target

NAN = Defect(target_ref="episode_000001", code="D1", parameters={"kind": "nan_values"})


def _sealed(tmp_path: Path, seal: Seal) -> Path:
    answers = tmp_path / "answers"
    seal(answers, INJECTED, [NAN])
    seal(answers, CLEAN, [])
    return answers


def _session(answers: Path) -> BenchSession:
    return BenchSession([("data", INJECTED), ("data", CLEAN)], [answers])


def test_qa_work_gives_episode_refs_and_codes(tmp_path: Path, qa_work: QAWork) -> None:
    reasons = {
        1: ["finite_values (D3): NaN or Inf values = 12 > 0"],
        2: ["min_frames: episode has 3 frame(s), QA needs at least 10"],
    }
    run = read_qa_work(qa_work(tmp_path, INJECTED, 3, reasons), INJECTED)
    assert run.units == ("episode_000000", "episode_000001", "episode_000002")
    assert [(d.target, d.code) for d in run.detections] == [("episode_000001", "D3")]
    assert run.uncoded == ("episode_000002: min_frames: episode has 3 frame(s), QA needs at"
                           " least 10",)
    assert run.reported_at is not None and run.reported_at.tzinfo is not None


def test_qa_work_of_another_copy_is_refused(tmp_path: Path, qa_work: QAWork) -> None:
    work = qa_work(tmp_path, CLEAN, 2, {})
    with pytest.raises(BenchInputError, match="not of copy"):
        read_qa_work(work, INJECTED)


def test_agent_targets_resolve_to_the_manifest_ids(tmp_path: Path, qa_work: QAWork,
                                                    report: Report) -> None:
    code = read_qa_work(qa_work(tmp_path, INJECTED, 3, {}), INJECTED)
    ingest_id = next(k for k, v in code.aliases.items() if v == "episode_000002")
    rep = report("r1", [
        ("episode_000000", "D1"),
        (ingest_id, "D2"),
        ("data/chunk-000/episode_000001.parquet", "D3"),
        ("dataset", "D4"),
    ])
    run = agent_run([rep], INJECTED, code.units, code.aliases)
    assert [d.target for d in run.detections] == [
        "episode_000000", "episode_000002", "episode_000001", "dataset"
    ]
    jobs = ["train/job-1", "rtc/job-2"]
    assert resolve_target("C:\\x\\train\\job-1\\metrics.jsonl", jobs, {}) == "train/job-1"
    assert resolve_target("copies/b/rtc/job-2", jobs, {}) == "rtc/job-2"
    assert resolve_target("train\\job-9", jobs, {}) == "train/job-9"


def test_answers_stay_shut_until_both_layers_ran_on_both_copies(
    tmp_path: Path, qa_work: QAWork, report: Report, seal: Seal,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    real = session_module.open_sealed

    def spy(folder: Path, dataset_id: str):  # type: ignore[no-untyped-def]
        opened.append(dataset_id)
        return real(folder, dataset_id)

    monkeypatch.setattr(session_module, "open_sealed", spy)
    bench = _session(_sealed(tmp_path, seal))
    for copy_id in (INJECTED, CLEAN):
        code = read_qa_work(qa_work(tmp_path, copy_id, 2, {}), copy_id)
        bench.record(code, job_finished_at=T0)
        if copy_id == INJECTED:
            # one copy has both layers, the other only code: still shut
            bench.record(agent_run([report("r-i", [])], copy_id, code.units, code.aliases))
            with pytest.raises(BenchIncomplete, match="code:bench-bbbbbbbbbbbb|agent:bench-b"):
                bench.open_answers()
    with pytest.raises(BenchIncomplete, match=f"agent:{CLEAN}"):
        bench.open_answers()
    assert opened == []
    code = read_qa_work(tmp_path / f"work-{CLEAN}", CLEAN)
    bench.record(agent_run([report("r-c", [])], CLEAN, code.units, code.aliases))
    result = bench.open_answers()
    assert sorted(opened) == sorted([INJECTED, CLEAN])
    (group,) = result.groups
    assert group.injected.dataset_id == INJECTED and group.clean.dataset_id == CLEAN
    assert group.injected.job_finished_at == T0
    with pytest.raises(BenchInputError, match="answer key is open"):
        bench.record(code)


@pytest.mark.parametrize(
    "ref, why",
    [
        ("fwdata/inject/answers/bench-aaaaaaaaaaaa/defect_manifest.json", "answer key file"),
        ("fwdata/inject/answers/bench-aaaaaaaaaaaa/flywheel_lineage.jsonl", "answers/"),
        (f"fwdata/inject/copies/{CLEAN}/data/chunk-000/episode_000001.parquet", "another copy"),
    ],
)
def test_an_agent_that_could_have_read_the_answer_is_refused(
    tmp_path: Path, qa_work: QAWork, report: Report, seal: Seal, ref: str, why: str
) -> None:
    bench = _session(_sealed(tmp_path, seal))
    for copy_id in (INJECTED, CLEAN):
        code = read_qa_work(qa_work(tmp_path, copy_id, 2, {}), copy_id)
        bench.record(code)
        inputs = (ref,) if copy_id == INJECTED else ("copies/x/meta/info.json",)
        bench.record(agent_run([report(f"r-{copy_id}", [], inputs=inputs)], copy_id,
                               code.units, code.aliases))
    with pytest.raises(AnswerLeak, match=why):
        bench.open_answers()


def test_a_tampered_answer_key_is_refused(tmp_path: Path, qa_work: QAWork, report: Report,
                                          seal: Seal) -> None:
    answers = _sealed(tmp_path, seal)
    path = answers / INJECTED / "defect_manifest.json"
    path.write_text(path.read_text().replace("episode_000001", "episode_000000"))
    bench = _session(answers)
    for copy_id in (INJECTED, CLEAN):
        code = read_qa_work(qa_work(tmp_path, copy_id, 2, {}), copy_id)
        bench.record(code)
        bench.record(agent_run([report(f"r-{copy_id}", [])], copy_id, code.units, code.aliases))
    with pytest.raises(AnswerKeyError, match="does not match its seal"):
        bench.open_answers()


def test_a_group_needs_one_clean_and_one_injected_copy(tmp_path: Path, qa_work: QAWork,
                                                       report: Report, seal: Seal) -> None:
    answers = tmp_path / "answers"
    seal(answers, INJECTED, [NAN])
    seal(answers, CLEAN, [NAN.model_copy(update={"target_ref": "episode_000000"})])
    bench = _session(answers)
    for copy_id in (INJECTED, CLEAN):
        code = read_qa_work(qa_work(tmp_path, copy_id, 2, {}), copy_id)
        bench.record(code, job_finished_at=T0 - timedelta(minutes=1))
        bench.record(agent_run([report(f"r-{copy_id}", [])], copy_id, code.units, code.aliases))
    with pytest.raises(AnswerKeyError, match="2 copies with defects and 0 clean"):
        bench.open_answers()
