"""DA-20 task 1: the tool loop, run on the testkit's fake model (AC 1, 2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from flywheel.eval.agentqa.dialogue import DialogueError, ToolError, run_dialogue
from flywheel.eval.agentqa.settings import Prompt, load_prompt
from flywheel.testkit.fakes.llm import FakeLLM

PROTOCOL = load_prompt(
    Path(__file__).resolve().parents[5]
    / "configs"
    / "eval"
    / "agentqa"
    / "prompts"
    / "tool_protocol.md"
)
LIMITS = {"max_turns": 5, "max_prompt_chars": 100_000}


def _tool(name: str, artifact_id: str) -> str:
    return json.dumps({"tool": name, "id": artifact_id})


def _store(artifact_id: str) -> str:
    if artifact_id != "report":
        raise ToolError(f"no artifact {artifact_id!r}")
    return '{"failed": 12}'


def test_a_tool_call_is_answered_and_the_final_object_is_returned() -> None:
    llm = FakeLLM([_tool("read", "report"), '{"final": {"code": "D2"}}'])
    result = run_dialogue(llm, PROTOCOL, "Assess it.", {"read": _store}, **LIMITS)
    assert result.final == {"code": "D2"}
    assert result.turns == 2
    assert [(c.tool, c.id, c.ok) for c in result.calls] == [("read", "report", True)]
    # The second prompt carries the first reply and what the tool returned.
    assert '{"failed": 12}' in llm.requests[1]
    assert "Assess it." in llm.requests[0]
    assert PROTOCOL.text.strip() in llm.requests[0]
    assert "Tools: read" in llm.requests[0]


def test_a_refused_id_goes_back_to_the_model_as_an_error() -> None:
    llm = FakeLLM([_tool("read", "../vault/x"), '{"final": {}}'])
    result = run_dialogue(llm, PROTOCOL, "t", {"read": _store}, **LIMITS)
    assert [c.ok for c in result.calls] == [False]
    assert "no artifact" in llm.requests[1]


def test_an_unknown_tool_is_an_error_line_not_a_crash() -> None:
    llm = FakeLLM([_tool("run_job", "x"), '{"final": {}}'])
    result = run_dialogue(llm, PROTOCOL, "t", {"read": _store}, **LIMITS)
    assert [c.ok for c in result.calls] == [False]
    assert "unknown tool" in llm.requests[1]


@pytest.mark.parametrize(
    "bad",
    [
        "I will read the report now.",
        '{"tool": "read"}',
        '{"tool": "read", "id": "report", "extra": 1}',
        '{"final": "text, not an object"}',
        '{"final": {}} and then some prose',
        "[1, 2]",
    ],
)
def test_a_reply_that_is_not_one_valid_message_gets_a_reminder(bad: str) -> None:
    llm = FakeLLM([bad, '{"final": {"ok": true}}'])
    result = run_dialogue(llm, PROTOCOL, "t", {"read": _store}, **LIMITS)
    assert result.final == {"ok": True}
    assert result.calls == ()
    assert "not accepted" in llm.requests[1]


def test_a_markdown_fence_around_the_object_is_allowed() -> None:
    llm = FakeLLM(['```json\n{"final": {"a": 1}}\n```'])
    assert run_dialogue(llm, PROTOCOL, "t", {}, **LIMITS).final == {"a": 1}


def test_a_model_that_never_answers_properly_ends_the_run() -> None:
    llm = FakeLLM(["no"] * 5)
    with pytest.raises(DialogueError, match="after 5 turns"):
        run_dialogue(llm, PROTOCOL, "t", {}, **LIMITS)
    assert len(llm.requests) == 5


def test_a_prompt_over_the_limit_ends_the_run_before_the_model_sees_it() -> None:
    llm = FakeLLM(['{"final": {}}'])
    with pytest.raises(DialogueError, match="over the limit"):
        run_dialogue(llm, PROTOCOL, "x" * 500, {}, max_turns=3, max_prompt_chars=200)
    assert llm.requests == []


def test_a_transcript_that_grows_past_the_limit_ends_the_run() -> None:
    def big(_: str) -> str:
        return "y" * 400

    protocol = Prompt(name="p", text="Be brief.", sha256="0" * 64)
    llm = FakeLLM([_tool("read", "a"), _tool("read", "b")])
    with pytest.raises(DialogueError, match="over the limit"):
        run_dialogue(llm, protocol, "t", {"read": big}, max_turns=5, max_prompt_chars=700)
    assert len(llm.requests) == 2
