"""The exchange between the agent and the artifacts it may read (DA-20 AC 1, 2).

The model has one way to see an artifact: name a tool and an id. A reply is one JSON
object, either `{"tool": name, "id": artifact_id}` or `{"final": {...}}`. This is plain
text over `LLMClient.complete`, so the same loop runs on the fake in CI and on Nemotron;
nothing in it depends on a model's own tool-calling format.

What the loop guarantees, whatever the model says:

* **A tool is a function of an id.** The model never supplies a path or a command. What
  an id means, and which ids are refused, is the tool's business (task 2).
* **A bad tool call is an answer, not a crash.** An unknown tool, or a tool that refuses
  an id, comes back to the model as an error line; the model may then read something else.
* **A reply that is not one JSON object gets one reminder per turn**, and every turn
  counts toward `max_turns`, so a model that cannot follow the format ends the run
  instead of looping.
* **The prompt has a size limit.** The whole transcript is sent each turn; one that grows
  past `max_prompt_chars` ends the run rather than being cut silently. Long logs are
  summarised by code before they reach the agent, not truncated here.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from flywheel.eval.agentqa.llm import LLMClient
from flywheel.eval.agentqa.settings import Prompt

Tool = Callable[[str], str]

_REMINDER = (
    "Your last reply was not accepted: reply with exactly one JSON object, either "
    '{"tool": "<name>", "id": "<id>"} or {"final": {...}}.'
)


class DialogueError(RuntimeError):
    """The run ended without a final answer: too many turns, or a prompt too long."""


class ToolError(Exception):
    """A tool refuses an id; the message goes back to the model."""


@dataclass(frozen=True)
class ToolCall:
    tool: str
    id: str
    ok: bool


@dataclass(frozen=True)
class DialogueResult:
    final: Mapping[str, Any]
    calls: tuple[ToolCall, ...]
    turns: int


def _first_object(reply: str) -> dict[str, Any] | None:
    """The one JSON object a reply holds, allowing a Markdown fence around it."""
    text = reply.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    try:
        value, end = json.JSONDecoder().raw_decode(text.strip())
    except ValueError:
        return None
    if text.strip()[end:].strip() or not isinstance(value, dict):
        return None
    return value


def run_dialogue(
    llm: LLMClient,
    protocol: Prompt,
    task: str,
    tools: Mapping[str, Tool],
    *,
    max_turns: int,
    max_prompt_chars: int,
) -> DialogueResult:
    """Ask until the model gives a final answer, answering its tool calls on the way."""
    names = ", ".join(sorted(tools)) or "none"
    head = f"{protocol.text.rstrip()}\n\nTools: {names}\n\n# Task\n{task}"
    exchange: list[str] = []
    calls: list[ToolCall] = []
    for turn in range(1, max_turns + 1):
        prompt = "\n\n".join([head, *exchange])
        if len(prompt) > max_prompt_chars:
            raise DialogueError(
                f"turn {turn}: prompt is {len(prompt)} characters, over the limit "
                f"{max_prompt_chars}; summarise the inputs before they reach the agent"
            )
        reply = llm.complete(prompt)
        exchange.append(f"[assistant]\n{reply.strip()}")
        message = _first_object(reply)
        if message is not None and set(message) == {"final"} and isinstance(message["final"], dict):
            return DialogueResult(final=message["final"], calls=tuple(calls), turns=turn)
        if (
            message is not None
            and set(message) == {"tool", "id"}
            and isinstance(message["tool"], str)
            and isinstance(message["id"], str)
        ):
            name, artifact_id = message["tool"], message["id"]
            result, ok = _call(tools, name, artifact_id)
            calls.append(ToolCall(name, artifact_id, ok))
            exchange.append(f"[tool {name} {artifact_id}]\n{result}")
        else:
            exchange.append(f"[system]\n{_REMINDER}")
    raise DialogueError(f"no final answer after {max_turns} turns")


def _call(tools: Mapping[str, Tool], name: str, artifact_id: str) -> tuple[str, bool]:
    tool = tools.get(name)
    if tool is None:
        return json.dumps({"error": f"unknown tool {name!r}"}), False
    try:
        return tool(artifact_id), True
    except ToolError as exc:
        return json.dumps({"error": str(exc)}), False
