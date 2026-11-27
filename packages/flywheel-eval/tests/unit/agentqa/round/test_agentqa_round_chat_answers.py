"""Assemble and render with a chat page's extras (DA-54 task 3.1, AC 4).

A round passes no notes and no answers: assembling and rendering its directory again
gives the same bytes as the round wrote, in both modes. With answers, the page shows them
under their own heading, as recorded.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from flywheel.eval.agentqa.round.assemble import ASSEMBLY_FILE, NO_COST_NOTE, assemble
from flywheel.eval.agentqa.round.pipeline import RUN_FILE, run_round
from flywheel.eval.agentqa.round.records import ChatAnswer, RunRecord
from flywheel.eval.agentqa.round.render import INDEX_FILE, render
from helpers_round import NOW, isolated_store, pack_maker  # noqa: F401  (an autouse fixture)
from test_agentqa_round_investigate import Bot, factory_of

ANSWER = ChatAnswer(answer_id="A1", question="Why <this>?",
                    rendered="It is 3 rollouts & more.\n\nCited facts:\n- F2 n: 3 rollouts",
                    cites=["F2"])


def _again(out: Path, no_model: bool) -> tuple[bytes, bytes]:
    before = (out / ASSEMBLY_FILE).read_bytes(), (out / INDEX_FILE).read_bytes()
    run = RunRecord.model_validate_json((out / RUN_FILE).read_text())
    assemble(out, run, no_model)
    render(out)
    assert ((out / ASSEMBLY_FILE).read_bytes(), (out / INDEX_FILE).read_bytes()) == before
    return before


def test_a_floor_round_assembles_and_renders_to_the_same_bytes(tmp_path: Path) -> None:
    out = tmp_path / "run"
    run_round(pack_maker(tmp_path)(), out, now=NOW, store=tmp_path / "store", no_model=True)
    assembly, page = _again(out, True)
    assert b"chat_answers" not in assembly and b"Checked answers" not in page


def test_a_model_round_assembles_and_renders_to_the_same_bytes(tmp_path: Path) -> None:
    out = tmp_path / "run"
    run_round(pack_maker(tmp_path)(), out, now=NOW, store=tmp_path / "store", no_model=False,
              gateway_factory=factory_of(Bot()))
    _again(out, False)


def test_answers_and_notes_are_shown_as_given(tmp_path: Path) -> None:
    out = tmp_path / "run"
    run_round(pack_maker(tmp_path)(), out, now=NOW, store=tmp_path / "store", no_model=True)
    copy = tmp_path / "copy"
    shutil.copytree(out, copy)
    run = RunRecord.model_validate_json((copy / RUN_FILE).read_text())
    a = assemble(copy, run, True, notes=["From a chat record."], answers=[ANSWER])
    assert a.notes[-2:] == ["From a chat record.", NO_COST_NOTE]
    assert json.loads((copy / ASSEMBLY_FILE).read_text())["chat_answers"] == [
        ANSWER.model_dump(mode="json")]
    page = render(copy).read_text()
    assert "<h2>Checked answers (chat)</h2>" in page
    assert "<strong>Question:</strong> Why &lt;this&gt;?" in page
    assert "It is 3 rollouts &amp; more.<br><br>Cited facts:<br>- F2 n: 3 rollouts" in page
    assert "Cited facts: F2</p>" in page
    plain = (out / INDEX_FILE).read_text()
    assert page.replace(page[page.index("<h2>Checked answers"):page.index("<h2>Tool tables")],
                        "").count("<h2>") == plain.count("<h2>")
