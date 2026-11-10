"""Code's half of the report: each finding keeps its own facts (issue #175)."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import pytest
from agentqa_build import SYSTEM_YAML, TRAIN_YAML, rtc_job, train_job
from flywheel.eval.agentqa.analyze import FLAG_WHEN, _direction, analyze_rtc, analyze_train
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
    # the threshold and its direction are facts both cite; the values are two
    assert values[0]["T6_threshold"] == values[1]["T6_threshold"]
    shared = {f.name for f in analysis.book.facts
              if f.fact_id in set(t6[0].evidence) & set(t6[1].evidence)}
    assert shared == {"T6_threshold", "T6_flag_when"}


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


def _named(analysis, cid_evidence):  # type: ignore[no-untyped-def]
    facts = {f.fact_id: f for f in analysis.book.facts}
    return {facts[e].name: facts[e].value for e in cid_evidence}


def test_a_threshold_comes_with_the_side_that_is_the_fault(tmp_path: Path) -> None:
    """T6 flags below its threshold; Nemotron read it the other way round (#175)."""
    metrics = collapsed_job(tmp_path / "train" / "job-t6", [0.05])
    analysis = analyze_train(load_file(metrics), "train/job-t6", TRAIN_YAML)
    (t6,) = [c for c in analysis.candidates if c.code == "T6"]
    assert _named(analysis, t6.evidence)["T6_flag_when"] == "value < threshold"


def test_the_direction_table_agrees_with_the_detectors(tmp_path: Path) -> None:
    """Every finding DA-08 and DA-13 raise here lies on the side FLAG_WHEN names."""
    jobs = [
        train_job(tmp_path / "train" / "spike", loss=lambda s: 50.0 if s == 90 else 1.0),
        train_job(tmp_path / "train" / "grad", grad_norm_vlm=0.5),
        collapsed_job(tmp_path / "train" / "collapse", [0.05, 0.1]),
        train_job(tmp_path / "train" / "dead", pred_var_by_dim=[0.0, 0.2],
                  steps=range(0, 2001, 100)),  # T5 needs a job longer than its window
    ]
    (tmp_path / "train" / "dead" / "action_layout.json").write_text(
        (tmp_path / "train" / "collapse" / "action_layout.json").read_text(), encoding="utf-8")
    seen = set()
    for metrics in jobs:
        analysis = analyze_train(load_file(metrics), f"train/{metrics.parent.name}", TRAIN_YAML)
        assert not [n for n in analysis.notes if "direction left out" in n]
        for c in analysis.candidates:
            named = _named(analysis, c.evidence)
            if any(k.startswith(f"{c.code}_threshold") for k in named):
                assert f"{c.code}_flag_when" in named
                seen.add(c.code)
    log = rtc_job(tmp_path / "rtc" / "slow", latency=0.3, delay_steps=20)
    rtc = analyze_rtc(load_file(log), "rtc/slow", SYSTEM_YAML)
    for c in rtc.candidates:
        assert f"{c.code}_flag_when" in _named(rtc, c.evidence)
        seen.add(c.code)
    assert {"T1", "T5", "T6", "T8", "R1", "R2"} <= seen
    assert set(FLAG_WHEN) == {f"T{i}" for i in range(1, 9)} | {"R1", "R2"}


def test_a_finding_on_the_wrong_side_gets_a_note_not_a_direction(tmp_path: Path) -> None:
    analysis = analyze_train(load_file(train_job(tmp_path / "train" / "j")), "train/j",
                             TRAIN_YAML)
    assert _direction(analysis, "T6", 0.9, 0.3, "m") is None
    assert "direction left out" in analysis.notes[-1]
    assert analysis.book.get(_direction(analysis, "T6", 0.1, 0.3, "m") or "").value == (
        "value < threshold"
    )
