"""A record bound to a run (DA-54 task 3.1, AC 4): its fact ids continue the run's.

The pack is the public small pack of the record tests; the run is its code floor, which
calls no `measure_compare`, so a compare of the chat gives new facts after the run's.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "round"))
sys.path.insert(0, str(_HERE))
from flywheel.eval.agentqa.mcp import server as mcp_server  # noqa: E402
from flywheel.eval.agentqa.mcp.records import (  # noqa: E402
    ANSWER,
    DROP,
    PROPOSE,
    RECORD_FILE,
    Recorder,
    RecordRefused,
    bind_record,
)
from flywheel.eval.agentqa.mcp.server import open_public_session  # noqa: E402
from flywheel.eval.agentqa.round.judge import COMPARISON_MARKERS  # noqa: E402
from flywheel.eval.agentqa.round.measure import CALLS_FILE, FACTS_FILE  # noqa: E402
from flywheel.eval.agentqa.round.records import FactRecord, ToolCallRecord  # noqa: E402
from flywheel.eval.agentqa.round.verify import INVESTIGATION_FACTS_FILE  # noqa: E402
from helpers_binding import OFFSET, floor_run, hashes, public_pack  # noqa: E402
from helpers_round import isolated_store, pack_maker  # noqa: E402, F401
from test_agentqa_mcp_records import propose  # noqa: E402


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    return public_pack(tmp_path)


@pytest.fixture
def run(pack: Path, tmp_path: Path) -> Path:
    return floor_run(pack, tmp_path / "run", tmp_path / "store")


def _open(pack: Path, record: Path, run: Path | None = None) -> Recorder:
    opened = open_public_session(pack)
    return Recorder.open(record, opened.session, opened.admission.pack_id,
                         opened.admission.pack_sha256, markers=COMPARISON_MARKERS, run=run)


def _facts(path: Path) -> list[FactRecord]:
    return [FactRecord.model_validate_json(x) for x in path.read_text().splitlines()]


def _number(fact_id: str) -> int:
    return int(fact_id[1:])


def test_a_bound_record_numbers_its_facts_after_the_runs(
        pack: Path, run: Path, tmp_path: Path) -> None:
    record = tmp_path / "record"
    recorder = _open(pack, record, run)
    head = json.loads((record / RECORD_FILE).read_text())
    run_json = json.loads((run / "run.json").read_text())
    assert head["run_id"] == run_json["run_id"] and head["run_dir"] == str(run.resolve())
    assert len(head["run_facts_sha256"]) == 64
    base = _facts(run / FACTS_FILE)
    outcome, call_id = recorder.call("measure_compare", OFFSET)
    assert outcome.status == "ran" and call_id == "M1"
    own = _facts(record / INVESTIGATION_FACTS_FILE)
    assert own and [f.fact_id for f in own] == [
        f"F{k}" for k in range(len(base) + 1, len(base) + len(own) + 1)]
    assert {f.tool_call_id for f in own} == {"M1"}


def test_a_tool_called_again_returns_the_runs_ids_and_writes_no_fact(
        pack: Path, run: Path, tmp_path: Path) -> None:
    record = tmp_path / "record"
    recorder = _open(pack, record, run)
    first = ToolCallRecord.model_validate_json(
        (run / CALLS_FILE).read_text().splitlines()[0])
    outcome, _ = recorder.call(first.tool, first.params)
    assert list(outcome.fact_ids) == first.fact_ids and first.fact_ids
    assert not (record / INVESTIGATION_FACTS_FILE).exists()


def test_run_facts_are_cited_with_their_values_and_provenance(
        pack: Path, run: Path, tmp_path: Path) -> None:
    recorder = _open(pack, tmp_path / "record", run)
    base = _facts(run / FACTS_FILE)
    fact = next(f for f in base if isinstance(f.value, int) and not isinstance(f.value, bool))
    answer = recorder.record(ANSWER, {"text": "See {" + fact.fact_id + "}.",
                                      "cites": [fact.fact_id]})
    assert not answer.is_error, answer.reasons
    assert answer.payload is not None
    assert answer.payload["facts"][0]["value"] == fact.value
    f: dict[str, str] = {}
    outcome, _ = recorder.call("measure_compare", OFFSET)
    by_id = {x.fact_id: x for x in _facts(tmp_path / "record" / INVESTIGATION_FACTS_FILE)}
    for fid in outcome.fact_ids:
        f[by_id[fid].name.rsplit("successes_same_level", 1)[-1]] = fid
    kept = recorder.record(PROPOSE, propose([f["_separated"], fact.fact_id]))
    assert not kept.is_error and kept.payload is not None
    assert kept.payload["verdict"] == "kept"


def test_hypothesis_ids_continue_after_the_runs_rules(
        pack: Path, run: Path, tmp_path: Path) -> None:
    recorder = _open(pack, tmp_path / "record", run)
    rules = [json.loads(x)["hypothesis_id"]
             for x in (run / "hypotheses.jsonl").read_text().splitlines()]
    assert rules
    outcome, _ = recorder.call("measure_compare", OFFSET)
    by_id = {x.fact_id: x for x in _facts(tmp_path / "record" / INVESTIGATION_FACTS_FILE)}
    sep = next(fid for fid in outcome.fact_ids if by_id[fid].name.endswith("_separated"))
    kept = recorder.record(PROPOSE, propose([sep]))
    assert kept.payload is not None
    assert kept.payload["hypothesis"] == f"H{1 + max(int(h[1:]) for h in rules)}"
    refused = recorder.record(DROP, {"hypothesis": rules[0], "refuted_by": [sep]})
    assert refused.is_error and "is a rule hypothesis" in refused.reasons[0]


def test_reopening_follows_the_binding_without_run(
        pack: Path, run: Path, tmp_path: Path) -> None:
    record = tmp_path / "record"
    first = _open(pack, record, run)
    ids = first.call("measure_compare", OFFSET)[0].fact_ids
    snapshot = hashes(record)
    again = _open(pack, record)
    assert hashes(record) == snapshot  # opening writes nothing
    assert again.call("measure_compare", OFFSET)[0].fact_ids == ids
    assert len(again.session.book.facts) == len(first.session.book.facts)
    assert _open(pack, record, run).session.book.facts  # the same run again is fine


def test_an_unbound_record_keeps_its_head_and_numbering(pack: Path, tmp_path: Path) -> None:
    record = tmp_path / "record"
    recorder = _open(pack, record)
    head = json.loads((record / RECORD_FILE).read_text())
    assert set(head) == {"pack_id", "pack_sha256"}
    recorder.call("measure_compare", OFFSET)
    assert _facts(record / INVESTIGATION_FACTS_FILE)[0].fact_id == "F1"


def _refused(pack: Path, record: Path, run: Path | None, match: str) -> None:
    before = hashes(record) if record.exists() else None
    with pytest.raises(RecordRefused, match=match):
        _open(pack, record, run)
    assert (hashes(record) if record.exists() else None) == before


def test_every_refusal_writes_nothing(pack: Path, run: Path, tmp_path: Path) -> None:
    store = tmp_path / "store"
    # a run of another pack
    other_pack = pack_maker(tmp_path)("other")
    other_run = floor_run(other_pack, tmp_path / "other-run", store)
    _refused(pack, tmp_path / "r1", other_run, "another pack")
    assert not (tmp_path / "r1").exists()
    # not a run directory
    _refused(pack, tmp_path / "r2", tmp_path / "nowhere", "not a run directory")
    # a run argument that disagrees with the binding
    bound = tmp_path / "bound"
    _open(pack, bound, run)
    assert _open(pack, bound, floor_run(pack, tmp_path / "same", store))  # same id and facts
    second = tmp_path / "run2"
    shutil.copytree(run, second)
    record = json.loads((second / "run.json").read_text())
    (second / "run.json").write_text(json.dumps({**record, "run_id": "run_another"}))
    _refused(pack, bound, second, "is bound to run")
    # binding a record that already holds records made without a run
    loose = tmp_path / "loose"
    _open(pack, loose).call("measure_compare", OFFSET)
    _refused(pack, loose, run, "without a run")
    # the bound run's facts changed since
    moved = tmp_path / "moved"
    shutil.copytree(run, moved)
    held = tmp_path / "held"
    _open(pack, held, moved)
    with (moved / FACTS_FILE).open("a") as handle:
        handle.write("\n")
    _refused(pack, held, None, "changed since")
    _refused(pack, held, moved, "is bound to run")
    # the bound run is gone
    shutil.rmtree(moved)
    _refused(pack, held, None, "which is gone")


def test_bind_record_writes_the_head_only(pack: Path, run: Path, tmp_path: Path) -> None:
    opened = open_public_session(pack)
    record = tmp_path / "record"
    head = bind_record(record, opened.admission.pack_id, opened.admission.pack_sha256, run)
    assert sorted(p.name for p in record.iterdir()) == [RECORD_FILE]
    assert json.loads((record / RECORD_FILE).read_text()) == head
    assert bind_record(record, opened.admission.pack_id, opened.admission.pack_sha256,
                       None) == head
    # an unbound, empty record gains the binding
    empty = tmp_path / "empty"
    _open(pack, empty)
    bound = bind_record(empty, opened.admission.pack_id, opened.admission.pack_sha256, run)
    assert bound["run_id"] == head["run_id"]


def test_the_server_refuses_run_without_record(
        pack: Path, run: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert mcp_server.run(pack, None, None, run) == 2
    assert "--record" in capsys.readouterr().err


def test_the_server_refuses_a_run_of_another_pack(
        pack: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    other = floor_run(pack_maker(tmp_path)("other"), tmp_path / "other-run",
                      tmp_path / "store")
    assert mcp_server.run(pack, tmp_path / "log.jsonl", tmp_path / "rec", other) == 2
    assert not (tmp_path / "rec").exists()
    assert "another pack" in capsys.readouterr().err
