"""Kiểm hệ thống thật của làn DA-13 tới được web (W13, DESIGN.md §4.4b).

Hai chỗ hở của bản 0.5, mỗi chỗ một nhóm test:

* **Tên file.** Làn ghi `<store>/diagnosis/system.jsonl`; trước bản 0.7 bộ nạp
  bỏ qua file đó kèm log, nên M6 trên dữ liệu thật hiện "chưa kiểm hệ thống"
  cho mọi episode mà không gì báo.
* **Khoá nối.** `SystemDiagnosis.episode_id` là `episode_N`, đếm lại ở mỗi lượt
  eval. Bản ghi nối với `eval_episodes` bằng `trace_sha256`, và dòng không nối
  được bị từ chối thay vì gán vào một episode bất kỳ.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from web.fwsync.mapping import (
    DROPPED_FIELDS,
    MappingError,
    TraceLookup,
    map_system_diagnosis,
)
from web.fwsync.runner import run_import
from web.fwsync.sink import JsonlSink
from web.fwsync.source import scan, table_of

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/SystemDiagnosis.json"
)
TRACE_A = "a1" * 32
TRACE_B = "b2" * 32


def _diagnosis(trace_sha256: str, episode_id: str = "episode_3", **extra: Any) -> dict[str, Any]:
    """Một bản ghi đúng hợp đồng, như `write_system_record` của DA-13 ghi ra."""
    payload: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload.update(episode_id=episode_id, trace_sha256=trace_sha256, **extra)
    return payload


def _eval_episode(ref: str, index: int, trace_sha256: str | None) -> dict[str, Any]:
    return {
        "eval_episode_ref": ref, "evaluation_ref": "ev_real", "episode_index": index,
        "condition_id": f"cond_{index}", "level": 0, "episode_seed": 100 + index,
        "scorer_version": "0.2.0", "sim_success": False, "scorer_success": False,
        "infra_status": "ok", "step_status": ["pass", "fail"], "details": {},
        "trace_sha256": trace_sha256,
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8", newline="\n"
    )


def _rows(sink_dir: Path, table: str) -> list[dict[str, Any]]:
    path = sink_dir / f"{table}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture
def store(tmp_path: Path) -> Path:
    """Một store nhỏ: hai episode eval có trace, một episode chưa có."""
    folder = tmp_path / "store"
    _write_jsonl(
        folder / "eval_episodes.jsonl",
        [
            _eval_episode("ee_real_00", 0, TRACE_A),
            _eval_episode("ee_real_01", 1, TRACE_B),
            _eval_episode("ee_real_02", 2, None),
        ],
    )
    return folder


# ---------------------------------------------------------------------------
# tên file
# ---------------------------------------------------------------------------


def test_the_lane_file_is_read_as_system_diagnoses(tmp_path: Path) -> None:
    assert table_of(tmp_path / "diagnosis" / "system.jsonl") == "system_diagnoses"


def test_a_bare_system_file_elsewhere_is_still_ignored(store: Path) -> None:
    # Khoá là cặp thư mục và tên; `system.jsonl` ở chỗ khác không phải của làn.
    _write_jsonl(store / "logs" / "system.jsonl", [{"a": 1}])

    found = scan(store)

    assert "logs/system.jsonl" in [name.replace("\\", "/") for name in found.ignored]


def test_records_from_the_lane_file_take_the_strict_path(store: Path) -> None:
    _write_jsonl(store / "diagnosis" / "system.jsonl", [_diagnosis(TRACE_A)])
    _write_jsonl(store / "system_diagnoses.jsonl", [{"eval_episode_ref": "ee_real_01"}])

    found = scan(store)

    flags = sorted((r.path.name, r.contract) for r in found.by_table("system_diagnoses"))
    assert flags == [("system.jsonl", True), ("system_diagnoses.jsonl", False)]


# ---------------------------------------------------------------------------
# khoá nối
# ---------------------------------------------------------------------------


def test_a_lane_record_joins_its_episode_by_trace_hash(store: Path, tmp_path: Path) -> None:
    # Hai lượt eval khác nhau cùng có `episode_3`; chỉ hash nói được là trace nào.
    _write_jsonl(
        store / "diagnosis" / "system.jsonl",
        [_diagnosis(TRACE_A, "episode_3"), _diagnosis(TRACE_B, "episode_3")],
    )
    sink = JsonlSink(directory=tmp_path / "sink")

    result = run_import(store, sink, origin="core")

    assert result.errors == []
    rows = {row["trace_sha256"]: row for row in _rows(tmp_path / "sink", "system_diagnoses")}
    assert rows[TRACE_A]["eval_episode_ref"] == "ee_real_00"
    assert rows[TRACE_B]["eval_episode_ref"] == "ee_real_01"
    assert all(row["origin"] == "core" for row in rows.values())


def test_a_lane_record_keeps_every_contract_field_but_the_episode_name(
    store: Path, tmp_path: Path
) -> None:
    _write_jsonl(store / "diagnosis" / "system.jsonl", [_diagnosis(TRACE_A)])

    run_import(store, JsonlSink(directory=tmp_path / "sink"))

    (row,) = _rows(tmp_path / "sink", "system_diagnoses")
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for name in ("diagnosis", "config_sha256", "rtc_sha256", "camera_sha256",
                 "infra_sha256", "infra_status", "timing"):
        assert row[name] == expected[name], name
    assert row["findings"] == expected["findings"]
    assert row["skipped"] == expected["skipped"]
    assert row["recorded"] == expected["recorded"]
    assert row["recorded_skipped"] == expected["recorded_skipped"]
    # Hợp đồng không có `measurements`; `{}` thay vì bịa số.
    assert row["measurements"] == {}
    assert "episode_id" not in row
    assert "SystemDiagnosis.episode_id" in DROPPED_FIELDS


def test_a_record_whose_trace_is_unknown_is_refused(store: Path, tmp_path: Path) -> None:
    _write_jsonl(
        store / "diagnosis" / "system.jsonl", [_diagnosis(TRACE_A), _diagnosis("c3" * 32)]
    )

    result = run_import(store, JsonlSink(directory=tmp_path / "sink"))

    assert [row["eval_episode_ref"] for row in _rows(tmp_path / "sink", "system_diagnoses")] == [
        "ee_real_00"
    ]
    (error,) = result.errors
    assert error["table"] == "system_diagnoses"
    assert "trace_sha256" in error["message"]
    assert result.status == "partial"


def test_a_trace_hash_on_two_episodes_is_refused_not_guessed(tmp_path: Path) -> None:
    folder = tmp_path / "store"
    _write_jsonl(
        folder / "eval_episodes.jsonl",
        [_eval_episode("ee_real_00", 0, TRACE_A), _eval_episode("ee_real_01", 1, TRACE_A)],
    )
    _write_jsonl(folder / "diagnosis" / "system.jsonl", [_diagnosis(TRACE_A)])

    result = run_import(folder, JsonlSink(directory=tmp_path / "sink"))

    assert _rows(tmp_path / "sink", "system_diagnoses") == []
    (error,) = result.errors
    assert "nhiều dòng" in error["message"]


def test_a_record_that_breaks_the_contract_is_refused(store: Path, tmp_path: Path) -> None:
    # `clean` kèm mã bị bỏ qua: hợp đồng từ chối, không đợi C17 của Postgres.
    bad = _diagnosis(TRACE_A, diagnosis="clean", findings=[], recorded=[], recorded_skipped=[])
    _write_jsonl(store / "diagnosis" / "system.jsonl", [bad])

    result = run_import(store, JsonlSink(directory=tmp_path / "sink"))

    assert _rows(tmp_path / "sink", "system_diagnoses") == []
    (error,) = result.errors
    assert "SystemDiagnosis" in error["message"]


def test_reimporting_the_lane_file_gives_the_same_rows(store: Path, tmp_path: Path) -> None:
    _write_jsonl(store / "diagnosis" / "system.jsonl", [_diagnosis(TRACE_A)])
    sink_dir = tmp_path / "sink"

    run_import(store, JsonlSink(directory=sink_dir))
    first = _rows(sink_dir, "system_diagnoses")
    run_import(store, JsonlSink(directory=sink_dir))

    assert _rows(sink_dir, "system_diagnoses") == first


def test_mock_rows_still_load_through_the_tolerant_path(store: Path, tmp_path: Path) -> None:
    # Dòng của bộ mock đã mang `eval_episode_ref`; nó không đi qua bảng tra.
    _write_jsonl(
        store / "system_diagnoses.jsonl",
        [{
            "eval_episode_ref": "ee_real_02", "diagnosis": "unknown",
            "config_sha256": "e" * 64, "trace_sha256": "f" * 64, "findings": [],
            "skipped": [{"code": "R1", "reason": "không có log RTC"}],
        }],
    )

    result = run_import(store, JsonlSink(directory=tmp_path / "sink"), origin="mock")

    assert result.errors == []
    (row,) = _rows(tmp_path / "sink", "system_diagnoses")
    assert row["eval_episode_ref"] == "ee_real_02"


# ---------------------------------------------------------------------------
# mapper thuần
# ---------------------------------------------------------------------------


def test_the_mapper_needs_no_eval_episode_name() -> None:
    lookup = TraceLookup(by_trace={TRACE_A: "ee_real_00"})

    row = map_system_diagnosis(_diagnosis(TRACE_A, episode_id="episode_0"), lookup)

    assert row["eval_episode_ref"] == "ee_real_00"


def test_the_mapper_refuses_rather_than_guesses() -> None:
    with pytest.raises(MappingError, match="W13"):
        map_system_diagnosis(_diagnosis(TRACE_A), TraceLookup(by_trace={}))
