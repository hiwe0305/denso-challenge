"""`bench_result.json` của DA-31 vào web (DESIGN.md §4.4c, bản 0.6).

File này không phải artifact hợp đồng, nên không có schema nào để so. Thay vào
đó test dựng một kết quả bằng **chính hàm** của DA-31
(`flywheel.eval.agentqa.bench.report.bench_result`) và so cây khoá của nó với
bộ mock: DA-31 thêm, bớt hay đổi tên một khoá thì test này đỏ trước khi bộ nạp
âm thầm bỏ một con số. Đó là bài học của W13: dạng mock phải theo dạng lõi
thật ghi ra, không theo dạng web đoán.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.artifacts import Defect
from flywheel.eval.agentqa.bench.layers import AgentQuality, FindingJudgement, KindSplit
from flywheel.eval.agentqa.bench.report import BENCH_VERSION, GroupReport, ModelUse, bench_result
from flywheel.eval.agentqa.bench.score import GroupScore, LayerScore, Rate

from web.fwsync.mapping import BENCH_VERSIONS, MappingError, map_bench_result
from web.fwsync.runner import run_import
from web.fwsync.sink import JsonlSink

ROOT = Path(__file__).resolve().parents[2]
MOCK = ROOT / "mock" / "demo-17-11"
MOCK_RESULT = json.loads((MOCK / "bench_result.json").read_text(encoding="utf-8"))


def _layer(layer: str) -> LayerScore:
    return LayerScore(
        layer=layer,  # type: ignore[arg-type]
        recall_by_kind={"nan_values": Rate(1, 1)},
        masked_by_kind={"nan_values": 0},
        recall_unmasked_by_kind={"nan_values": Rate(1, 1)},
        precision_by_code={"D3": Rate(1, 1)},
        false_alarm=Rate(0, 4),
        not_a_unit=(),
        clean_reports=(("episode_000001", "D3"),),
        natural=(("episode_000002", "D2"),),
        seconds_to_report={"inj": 1.0, "clean": None},
        verdicts=(),
        caught=frozenset({0}),
        uncoded={"inj": ("a line",)},
    )


def _real_result() -> dict[str, Any]:
    defect = Defect(target_ref="episode_000001", code="D3", parameters={"kind": "nan_values"})
    score = GroupScore(
        group="data", injected_id="inj", clean_id="clean",
        kinds=(("nan_values", "D3"),), defects=(defect,),
        layers={"code": _layer("code"), "agent": _layer("agent")},
    )
    quality = AgentQuality(
        ranking=Rate(1, 1),
        reviews={"hit": {"agree": 1}},
        findings=(FindingJudgement("inj", "r1", "r1-f0", 1, "episode_000001", "D3", "hit",
                                   "agree", ""),),
    )
    split = (KindSplit("nan_values", "D3", 1, 1, 0, 1),)
    models = (ModelUse("inj", "m", "r", 0.0, "0" * 64, 1),)
    return bench_result(
        [GroupReport(score, split, quality, models)],
        created_at=datetime(2026, 11, 12, tzinfo=timezone.utc),
        manifest_sha256={"inj": "0" * 64},
        inputs={"spec_sha256": "1" * 64},
    )


def _shape(value: Any, path: str = "$") -> set[str]:
    """Cây khoá: khoá của dict, và khoá của phần tử đầu mỗi danh sách.

    Khoá động (mã lỗi, loại lỗi, mã bản sao) không phải dạng, nên dict mà
    khoá của nó là dữ liệu được gom về `*`.
    """
    out: set[str] = set()
    if path.endswith(".uncoded"):
        return out  # {mã bản sao: [dòng]}; bộ mock không có dòng không mã nào
    if isinstance(value, dict):
        dynamic = path.endswith(
            ("_by_kind", "_by_code", "seconds_to_report", "uncoded", "manifest_sha256",
             "reviews", "inputs")
        ) or path.endswith(".reviews.*")
        for key, child in value.items():
            name = "*" if dynamic else key
            out.add(f"{path}.{name}")
            out |= _shape(child, f"{path}.{name}")
    elif isinstance(value, list) and value and not isinstance(value[0], list):
        out |= _shape(value[0], f"{path}[]")
    return out


def test_the_mock_has_the_shape_da31_writes() -> None:
    real, mock = _shape(_real_result()), _shape(MOCK_RESULT)
    assert real == mock, (
        f"chỉ DA-31 có: {sorted(real - mock)}; chỉ mock có: {sorted(mock - real)}"
    )


def test_the_loader_reads_the_version_da31_writes_today() -> None:
    # The core installed here writes the newest version the loader knows.
    assert BENCH_VERSION == BENCH_VERSIONS[-1]
    assert MOCK_RESULT["bench_version"] == BENCH_VERSIONS[-1] == "da31-3"


def test_a_real_result_maps_without_loss() -> None:
    rows = map_bench_result(_real_result(), "a" * 64)
    (group,) = rows["defect_bench_groups"]
    assert group["injected_copy"] == "inj" and group["agent_ranking_total"] == 1
    assert group["natural"]["code"] == [["episode_000002", "D2"]]
    assert group["agent_models"] == [{"copy": "inj", "name": "m", "revision": "r",
                                      "temperature": 0.0, "prompt_sha256": "0" * 64,
                                      "reports": 1}]
    metrics = sorted((r["layer"], r["metric"], r["subject"]) for r in rows["defect_scores"])
    assert metrics == sorted(
        (layer, metric, subject)
        for layer in ("code", "agent")
        for metric, subject in (("recall", "nan_values"), ("recall_unmasked", "nan_values"),
                                ("precision", "D3"), ("false_alarm", "*"))
    )


def test_every_rate_of_the_mock_becomes_one_row() -> None:
    rows = map_bench_result(MOCK_RESULT, "b" * 64)
    expected = 0
    for group in MOCK_RESULT["groups"]:
        for layer in group["layers"].values():
            expected += len(layer["recall_by_kind"]) + len(layer["recall_unmasked_by_kind"])
            expected += len(layer["precision_by_code"]) + 1
    assert len(rows["defect_scores"]) == expected
    assert len(rows["defect_bench_groups"]) == 2
    recall = [r for r in rows["defect_scores"] if r["metric"] == "recall"]
    assert all(r["masked"] is not None for r in recall)
    alarms = [r for r in rows["defect_scores"] if r["metric"] == "false_alarm"]
    assert {r["bound"] for r in alarms} == {"upper"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r.update(bench_version="da31-1"), "bench_version"),
        (lambda r: r.update(groups=[]), "rỗng"),
        (lambda r: r["groups"][0]["layers"].pop("agent"), "layers"),
        (lambda r: r["groups"][0]["layers"]["code"].pop("recall_unmasked_by_kind"), "thiếu"),
        (lambda r: r["groups"][0]["layers"]["code"]["precision_by_code"].update(
            D1={"hit": 2, "total": 1, "value": 2.0}), "hit"),
        (lambda r: r["groups"][0]["layers"]["code"]["false_alarm_on_clean"].pop("bound"),
         "bound"),
        (lambda r: r["groups"][0].pop("agent_models"), "agent_models"),
        (lambda r: r["groups"][0]["agent_models"][0].pop("prompt_sha256"), "thiếu"),
        (lambda r: r["groups"][0]["agent_models"][0].update(copy="bench_other"), "không thuộc"),
        (lambda r: r["groups"][0]["agent_models"][0].update(prompt_sha256="abc"), "sha256"),
        (lambda r: r["groups"][0]["agent_models"][0].update(reports=0), "reports"),
    ],
)
def test_a_result_the_loader_cannot_trust_is_refused(change: Any, message: str) -> None:
    result = json.loads(json.dumps(MOCK_RESULT))
    change(result)
    with pytest.raises(MappingError, match=message):
        map_bench_result(result, "c" * 64)


def test_each_group_keeps_the_model_behind_each_copy() -> None:
    rows = map_bench_result(MOCK_RESULT, "d" * 64)
    for group, raw in zip(rows["defect_bench_groups"], MOCK_RESULT["groups"], strict=True):
        assert group["agent_models"] == raw["agent_models"]
        assert {m["copy"] for m in group["agent_models"]} == {
            group["injected_copy"], group["clean_copy"]}


def test_a_da31_2_result_loads_without_a_model_rather_than_a_guessed_one() -> None:
    old = json.loads(json.dumps(MOCK_RESULT))
    old["bench_version"] = "da31-2"
    for group in old["groups"]:
        del group["agent_models"]
    rows = map_bench_result(old, "e" * 64)
    assert [g["agent_models"] for g in rows["defect_bench_groups"]] == [None, None]


def test_import_loads_both_tables_keyed_by_the_result_hash(tmp_path: Path) -> None:
    sink = tmp_path / "sink"
    result = run_import(MOCK, JsonlSink(directory=sink), origin="mock")
    assert result.status == "ok", result.errors
    lock = (MOCK / "bench_result.sha256").read_text(encoding="utf-8").strip()
    lines = (sink / "defect_bench_groups.jsonl").read_text(encoding="utf-8").splitlines()
    groups = [json.loads(line) for line in lines]
    assert {g["result_sha256"] for g in groups} == {lock}
    assert {g["origin"] for g in groups} == {"mock"}
    again = run_import(MOCK, JsonlSink(directory=sink), origin="mock")
    assert again.counts["defect_scores"]["inserted"] == 0  # append-only: không chèn lại


def test_a_result_edited_after_scoring_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "core"
    source.mkdir()
    shutil.copy(MOCK / "bench_result.sha256", source / "bench_result.sha256")
    edited = json.loads(json.dumps(MOCK_RESULT))
    edited["groups"][0]["split"][0]["by_code"] = 0
    (source / "bench_result.json").write_text(
        json.dumps(edited, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    result = run_import(source, JsonlSink(directory=tmp_path / "sink"), origin="core")
    assert result.status == "failed"
    assert "đã bị sửa" in result.errors[0]["message"]


def test_without_a_lock_file_the_hash_is_taken_from_the_text(tmp_path: Path) -> None:
    source = tmp_path / "core"
    source.mkdir()
    text = (MOCK / "bench_result.json").read_text(encoding="utf-8")
    (source / "bench_result.json").write_text(text, encoding="utf-8")
    run_import(source, JsonlSink(directory=tmp_path / "sink"), origin="core")
    rows = (tmp_path / "sink" / "defect_bench_groups.jsonl").read_text(encoding="utf-8")
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() in rows
