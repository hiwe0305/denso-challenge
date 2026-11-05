"""DA-20 task 1: the fake model of the testkit and the real client are the same kind of thing.

CI never reaches Nemotron, so the only thing that makes the fake a fair stand-in is that
both satisfy the one interface the agent calls (AC 1).
"""

from __future__ import annotations

from pathlib import Path

from flywheel.eval.agentqa.llm import ChatEndpointClient, LLMClient
from flywheel.eval.agentqa.settings import load_endpoint
from flywheel.testkit.fakes.llm import FakeLLM

ENDPOINT = Path(__file__).resolve().parents[5] / "configs" / "eval" / "agentqa" / "endpoint.yaml"


def test_the_fake_and_the_real_client_both_satisfy_llm_client() -> None:
    assert isinstance(FakeLLM(["x"]), LLMClient)
    assert isinstance(ChatEndpointClient(load_endpoint(ENDPOINT)), LLMClient)


def test_the_fake_answers_in_order_and_records_prompts() -> None:
    fake = FakeLLM(["a", "b"])
    assert [fake.complete("1"), fake.complete("2")] == ["a", "b"]
    assert fake.requests == ["1", "2"]
