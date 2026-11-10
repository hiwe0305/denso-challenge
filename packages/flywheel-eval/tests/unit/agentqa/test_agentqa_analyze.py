"""Code's half of the report: each finding keeps its own facts (issue #175)."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import pytest
from agentqa_build import TRAIN_YAML, train_job
from flywheel.eval.agentqa.analyze import analyze_train
from flywheel.eval.agentqa.facts import FactBook, FactClash
from flywheel.eval.agentqa.inputs import load_file


def collapsed_job(root: Path, ratios: list[float]) -> Path:
    """A train job whose dims have pred_std / target_std = `ratios`, with a layout that wide."""
    layout = json.loads((files("flywheel.testkit") / "fixtures/artifacts/ActionLayout.json")
                        .read_text())
    first = layout["dimensions"][0]
    layout["dimensions"] = [{**first, "name": f"{first['name']}_{i}"} for i in range(len(ratios))]
    metrics = train_job(root, pred_std=ratios, target_std=[1.0] * len(ratios))
    (root / "action_layout.json").write_text(json.dumps(layout), encoding="utf-8")
    return metrics


def test_two_findings_of_one_code_on_two_dims_cite_their_own_values(tmp_path: Path) -> None:
    metrics = collapsed_job(tmp_path / "train" / "job-t6", [0.05, 0.9, 0.12])
    analysis = analyze_train(load_file(metrics), "train/job-t6", TRAIN_YAML)
    t6 = [c for c in analysis.candidates if c.code == "T6"]
    assert [c.detail for c in t6] == ["DA-08 T6 dim 0", "DA-08 T6 dim 2"]
    facts = {f.fact_id: f for f in analysis.book.facts}
    values = [{facts[e].name: facts[e].value for e in c.evidence} for c in t6]
    assert values[0]["T6_value_dim0"] == pytest.approx(0.05)
    assert values[1]["T6_value_dim2"] == pytest.approx(0.12)
    # the threshold is one fact both cite; the values are two
    assert values[0]["T6_threshold"] == values[1]["T6_threshold"]
    assert set(t6[0].evidence) & set(t6[1].evidence) == {
        next(f.fact_id for f in analysis.book.facts if f.name == "T6_threshold")
    }


def test_a_name_given_a_second_value_is_refused_not_dropped() -> None:
    book = FactBook()
    first = book.add("T6_value", 0.1, "m.jsonl")
    assert book.add("T6_value", 0.1, "m.jsonl") == first
    with pytest.raises(FactClash, match="needs its own name"):
        book.add("T6_value", 0.2, "m.jsonl")
    assert book.add("T6_value", float("nan"), "other.jsonl") == "F2"
    assert book.add("T6_value", float("nan"), "other.jsonl") == "F2"


def test_a_shared_fact_takes_its_own_name_when_values_differ() -> None:
    book = FactBook()
    a = book.shared("T1_threshold", "T1_threshold_2", 3.0, "m.jsonl")
    assert book.shared("T1_threshold", "T1_threshold_3", 3.0, "m.jsonl") == a
    b = book.shared("T1_threshold", "T1_threshold_2", 5.0, "m.jsonl")
    assert b != a and book.get(b).name == "T1_threshold_2"
