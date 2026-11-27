"""`fw agentqa chat-page` and `record_page` (DA-54 task 3.1, AC 4).

A record bound to a run of the public small pack gets two hypotheses on the level-1 place
cluster (one cites separation on `offset_m`, a measure the scorer does not threshold, so it
keeps; one cites only a median, not enough evidence) and one checked answer. The page is
built on a code-floor run and on a model run; the run and the record stay untouched.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "round"))
sys.path.insert(0, str(_HERE.parent / "mcp"))
from flywheel.eval.agentqa.chat.page import (  # noqa: E402
    RECORD_NOTE,
    SOURCE_FILE,
    PageRefused,
    record_page,
)
from flywheel.eval.agentqa.cli import app  # noqa: E402
from flywheel.eval.agentqa.mcp.records import (  # noqa: E402
    ANSWER,
    ANSWERS_FILE,
    PROPOSE,
    Recorder,
)
from flywheel.eval.agentqa.mcp.server import open_public_session  # noqa: E402
from flywheel.eval.agentqa.round.assemble import ASSEMBLY_FILE  # noqa: E402
from flywheel.eval.agentqa.round.judge import COMPARISON_MARKERS  # noqa: E402
from flywheel.eval.agentqa.round.records import Assembly, RunRecord  # noqa: E402
from flywheel.eval.agentqa.round.render import INDEX_FILE  # noqa: E402
from flywheel.eval.agentqa.round.verify import INVESTIGATED_FILE  # noqa: E402
from helpers_binding import (  # noqa: E402
    HEAD,
    OFFSET,
    floor_run,
    hashes,
    model_run,
    public_pack,
)
from helpers_round import isolated_store, pack_maker  # noqa: E402, F401
from test_agentqa_mcp_records import propose  # noqa: E402

QUESTION = "Why does the level one place cluster fail?"


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    return public_pack(tmp_path)


@pytest.fixture
def floor(pack: Path, tmp_path: Path) -> Path:
    return floor_run(pack, tmp_path / "floor", tmp_path / "store")


def _recorder(pack: Path, record: Path, run: Path | None) -> Recorder:
    opened = open_public_session(pack)
    return Recorder.open(record, opened.session, opened.admission.pack_id,
                         opened.admission.pack_sha256, markers=COMPARISON_MARKERS, run=run)


def chat_record(pack: Path, record: Path, run: Path | None) -> dict[str, str]:
    """Two hypotheses (kept, not enough evidence) and one answer; fact suffix -> id."""
    recorder = _recorder(pack, record, run)
    outcome, _ = recorder.call("measure_compare", OFFSET)
    names = {f.fact_id: f.name for f in recorder.session.book.facts}
    f = {names[fid].rsplit("successes_same_level", 1)[-1]: fid for fid in outcome.fact_ids}
    assert not recorder.record(PROPOSE, propose([f["_separated"]])).is_error
    assert not recorder.record(PROPOSE, propose([f["_median"]])).is_error
    answer = recorder.record(ANSWER, {"text": "The median offset is {" + f["_median"] + "}.",
                                      "cites": [f["_median"]]})
    assert not answer.is_error, answer.reasons
    return f


def _assembly(out: Path) -> Assembly:
    return Assembly.model_validate_json((out / ASSEMBLY_FILE).read_text())


def _head(a: Assembly) -> Any:
    return next(c for c in a.clusters if c.cluster.cluster_id == HEAD)


def _check_page(out: Path, run: Path, f: dict[str, str]) -> Assembly:
    a = _assembly(out)
    shown = [(h.hypothesis_id, h.origin, h.evidence) for h in _head(a).hypotheses]
    rules = [json.loads(x)["hypothesis_id"] for x in (run / "hypotheses.jsonl").read_text()
             .splitlines()]
    after = 1 + max(int(h[1:]) for h in rules)  # the record's ids continue the rules'
    kept, thin = f"H{after}", f"H{after + 1}"
    assert (kept, "model", "kept") in shown
    assert shown[-1] == (thin, "model", "insufficient")
    assert [h for h, origin, _ in shown if origin == "rule"] == [
        r for r in rules if r in {h for h, _, _ in shown}]
    assert RECORD_NOTE in a.notes
    assert "Model investigation: 1 kept, 1 not enough evidence, 0 rejected." in a.notes
    assert [x.answer_id for x in a.chat_answers] == ["A1"]
    assert a.chat_answers[0].cites == [f["_median"]]
    page = (out / INDEX_FILE).read_text()
    assert "Checked answers (chat)" in page
    assert "Model&#x27;s words, values filled in by code:" in page
    assert "The median offset is 0.05 m." in page
    assert f"Cited facts: {f['_median']}" in page
    run_json = RunRecord.model_validate_json((out / "run.json").read_text())
    base = RunRecord.model_validate_json((run / "run.json").read_text())
    assert run_json.derived_from == base.run_id == run_json.run_id
    source = json.loads((out / SOURCE_FILE).read_text())
    assert source["base_run_id"] == base.run_id
    assert set(source["files"]) == {INVESTIGATED_FILE, "investigation_facts.jsonl",
                                    "investigation_calls.jsonl", ANSWERS_FILE}
    assert not (out / "verdicts_live.jsonl").exists()
    return a


def test_a_floor_run_gets_the_chat_hypotheses_and_answers(
        pack: Path, floor: Path, tmp_path: Path) -> None:
    record = tmp_path / "record"
    f = chat_record(pack, record, floor)
    before = hashes(floor), hashes(record)
    out = tmp_path / "page"
    index = record_page(floor, record, out)
    assert index == out / INDEX_FILE
    assert (hashes(floor), hashes(record)) == before
    a = _check_page(out, floor, f)
    assert a.notes[0].startswith("No model ranked this round")
    # the rest of the floor stands: the rule hypotheses keep their order below
    plain = _assembly(floor)
    rules = [h.hypothesis_id for h in _head(a).hypotheses if h.origin == "rule"]
    assert rules == [h.hypothesis_id for h in _head(plain).hypotheses]


def test_a_model_run_gets_the_chat_hypotheses_and_keeps_its_ranking(
        pack: Path, tmp_path: Path) -> None:
    run = model_run(pack, tmp_path / "model", tmp_path / "store")
    record = tmp_path / "record"
    f = chat_record(pack, record, run)
    before = hashes(run), hashes(record)
    out = tmp_path / "page"
    record_page(run, record, out)
    assert (hashes(run), hashes(record)) == before
    a = _check_page(out, run, f)
    plain = _assembly(run)
    assert a.notes[0] == plain.notes[0] and a.notes[0].startswith("Model ranking:")
    assert a.model == plain.model


def test_the_command_builds_the_page(pack: Path, floor: Path, tmp_path: Path) -> None:
    record = tmp_path / "record"
    chat_record(pack, record, floor)
    out = tmp_path / "page"
    result = CliRunner().invoke(app, ["chat-page", "--run", str(floor), "--record",
                                      str(record), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert "2 model hypotheses shown, 1 checked answers" in result.stdout
    again = CliRunner().invoke(app, ["chat-page", "--run", str(floor), "--record",
                                     str(record), "--out", str(out)])
    assert again.exit_code == 2 and again.stderr.startswith("error: ")
    assert "not an empty directory" in again.stderr


def _refused(run: Path, record: Path, out: Path, match: str) -> None:
    before = hashes(run), hashes(record)
    with pytest.raises(PageRefused, match=match):
        record_page(run, record, out)
    assert (hashes(run), hashes(record)) == before
    assert not out.exists() or not any(out.iterdir())


def test_every_refusal_writes_nothing(pack: Path, floor: Path, tmp_path: Path) -> None:
    record = tmp_path / "record"
    chat_record(pack, record, floor)
    # the output exists and is not empty
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "x").write_text("")
    with pytest.raises(PageRefused, match="not an empty directory"):
        record_page(floor, record, busy)
    # an unbound record
    loose = tmp_path / "loose"
    chat_record(pack, loose, None)
    _refused(floor, loose, tmp_path / "o1", "not bound to a run")
    # a record bound to another run of the same pack
    other = tmp_path / "other"
    shutil.copytree(floor, other)
    run_json = json.loads((other / "run.json").read_text())
    (other / "run.json").write_text(json.dumps({**run_json, "run_id": "run_another"}))
    _refused(other, record, tmp_path / "o2", "is bound to run")
    # a record of another pack
    elsewhere = floor_run(pack_maker(tmp_path)("elsewhere"), tmp_path / "elsewhere-run",
                          tmp_path / "store")
    _refused(elsewhere, record, tmp_path / "o3", "another pack")
    # a run that already holds model hypotheses
    held = tmp_path / "held"
    shutil.copytree(floor, held)
    shutil.copyfile(record / INVESTIGATED_FILE, held / INVESTIGATED_FILE)
    _refused(held, record, tmp_path / "o4", "one source of model hypotheses")
    # an answer whose recorded text no longer reads from its facts
    tampered = tmp_path / "tampered"
    shutil.copytree(record, tampered)
    line = json.loads((tampered / ANSWERS_FILE).read_text())
    line["rendered"] = line["rendered"].replace("0.05", "0.01")
    (tampered / ANSWERS_FILE).write_text(json.dumps(line) + "\n")
    _refused(floor, tampered, tmp_path / "o5", "does not read the same")
    # a hypothesis id of the record that is a rule hypothesis's of the run
    clash = tmp_path / "clash"
    shutil.copytree(record, clash)
    lines = (clash / INVESTIGATED_FILE).read_text().splitlines()
    first = json.loads(lines[0])
    (clash / INVESTIGATED_FILE).write_text(
        "\n".join([json.dumps({**first, "hypothesis_id": "H1"}), *lines[1:]]) + "\n")
    _refused(floor, clash, tmp_path / "o6", "id of a rule hypothesis")
    # the output inside the run
    _refused(floor, record, floor / "page", "overlaps the run")


def test_a_question_recorded_with_an_answer_is_shown(
        pack: Path, floor: Path, tmp_path: Path) -> None:
    record = tmp_path / "record"
    chat_record(pack, record, floor)
    line = json.loads((record / ANSWERS_FILE).read_text())
    (record / ANSWERS_FILE).write_text(json.dumps({**line, "question": QUESTION}) + "\n")
    out = tmp_path / "page"
    record_page(floor, record, out)
    assert _assembly(out).chat_answers[0].question == QUESTION
    assert f"<strong>Question:</strong> {QUESTION}" in (out / INDEX_FILE).read_text()
