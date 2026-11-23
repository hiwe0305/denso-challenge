"""Steps B1 and B2 keep no large file in memory, and never read a file that changed.

Real packs hold 1.5 GB of trace lines: step B1 validates them one line at a time and keeps
none, and a tool reads a trace or a metrics file again when it needs it, checking the
sha256 the pack records on every read.
"""

from __future__ import annotations

import gc
from pathlib import Path

import pytest
import yaml
from flywheel.contracts.trace import TraceStep
from flywheel.eval.agentqa.round.admit import Records, admit
from flywheel.eval.agentqa.round.measure import _context
from flywheel.eval.agentqa.round.pack import PackRefused, build_pack, read_pack, write_pack
from helpers_tools import metric, rollout, score

CYCLES = 2000  # large enough that keeping them would show, small enough for a unit test


def lines(models: list) -> str:  # type: ignore[type-arg]
    return "".join(m.model_dump_json() + "\n" for m in models)


def make(root: Path) -> Path:
    root.mkdir()
    (root / "scores.jsonl").write_text(lines([score("R", "ok", True), score("R", "bad", False)]))
    (root / "trace.jsonl").write_text(lines(
        rollout("R", "ok", CYCLES // 2, upper_gap=0.01)
        + rollout("R", "bad", CYCLES // 2, upper_gap=0.5)))
    (root / "metrics.jsonl").write_text(lines([metric("J", 10, 1.0), metric("J", 20, 0.5)]))
    entries = [{"path": "scores.jsonl", "kind": "scores", "subject": {"run": "R"}},
               {"path": "trace.jsonl", "kind": "trace", "subject": {"run": "R"}},
               {"path": "metrics.jsonl", "kind": "metrics", "subject": {"job": "J"}}]
    decl = root / "round.yaml"
    decl.write_text(yaml.safe_dump({"task_id": "tray", "declared_by": "test",
                                    "data_class": "public", "entries": entries}))
    return write_pack(build_pack(decl), root)


def live_steps() -> int:
    gc.collect()
    return sum(isinstance(o, TraceStep) for o in gc.get_objects())


def test_admit_validates_the_trace_but_keeps_none_of_its_records(tmp_path: Path) -> None:
    pack = make(tmp_path / "p")
    before = live_steps()
    got = admit(pack)
    assert "trace.jsonl" in got.admission.accepted
    assert live_steps() == before  # every line was parsed, and none of them is held
    assert isinstance(got.records, Records)
    # A consumer that asks gets the records, parsed now and not kept afterwards.
    first = got.records["trace.jsonl"]
    assert len(first) == CYCLES and all(isinstance(s, TraceStep) for s in first)
    assert got.records["trace.jsonl"] is not first  # a large kind is parsed on every access
    del first
    assert live_steps() == before
    assert got.records["scores.jsonl"] is got.records["scores.jsonl"]  # a small kind is kept
    assert sum(1 for _ in got.stream("trace.jsonl")) == CYCLES


def test_the_tool_inputs_read_a_trace_file_only_when_asked(tmp_path: Path) -> None:
    pack = make(tmp_path / "p")
    admitted = admit(pack)
    ctx, _ = _context(read_pack(pack), admitted)
    before = live_steps()
    (file,) = ctx.traces["R"].files
    assert live_steps() == before  # building the context read no cycle
    assert len(file.read()) == CYCLES
    assert [r.step for r in ctx.jobs["J"].iter_rows()] == [10, 20]


@pytest.mark.parametrize("change", [b'{"not": "a step"}\n', b"\xff\n"])
def test_a_file_changed_after_admit_is_refused_when_a_tool_reads_it(
        tmp_path: Path, change: bytes) -> None:
    pack = make(tmp_path / "p")
    admitted = admit(pack)
    ctx, _ = _context(read_pack(pack), admitted)
    with (tmp_path / "p" / "trace.jsonl").open("ab") as f:
        f.write(change)  # whether or not the new line parses: the file is not that file
    with pytest.raises(PackRefused, match="trace.jsonl: the file changed after it was packed"):
        ctx.traces["R"].files[0].read()
    with pytest.raises(PackRefused, match="the file changed after it was packed"):
        admitted.records["trace.jsonl"]


def test_a_file_removed_after_admit_is_refused_when_a_tool_reads_it(tmp_path: Path) -> None:
    pack = make(tmp_path / "p")
    admitted = admit(pack)
    ctx, _ = _context(read_pack(pack), admitted)
    (tmp_path / "p" / "metrics.jsonl").unlink()
    with pytest.raises(PackRefused, match="metrics.jsonl: the file of the pack is gone"):
        list(ctx.jobs["J"].iter_rows())


@pytest.mark.parametrize("bad", [b"\xff", b"\xe2\x82", b"ok\xc3("])
def test_a_line_that_is_not_utf8_is_rejected_with_the_whole_file_message(
        tmp_path: Path, bad: bytes) -> None:
    root = tmp_path / "p"
    pack = make(root)
    raw = (root / "trace.jsonl").read_bytes() + bad + b"\n"
    (root / "trace.jsonl").write_bytes(raw)
    decl = yaml.safe_load((root / "round.yaml").read_text())
    (root / "pack.json").unlink()
    (root / "round.yaml").write_text(yaml.safe_dump(decl))
    pack = write_pack(build_pack(root / "round.yaml"), root)
    with pytest.raises(UnicodeDecodeError) as whole:
        raw.decode("utf-8")
    (rejected,) = admit(pack).admission.rejected
    assert rejected.reason == f"does not parse as trace: {whole.value}"
