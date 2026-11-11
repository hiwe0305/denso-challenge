"""The core's own store, written by the core's own writers, loads strictly (review #72 points 1, 2).

Every artifact here is built with the contract models of `flywheel.contracts`
and written with `flywheel.store` (`TableWriter`, `append_ledger_entry`), so
the layout is the one the core really writes: `catalog/<singular>/part-*.jsonl`
and `runs/<run_plan>/<job>/ledger.jsonl`. Hand-written JSON could only prove
the loader agrees with itself.

Before this, the loader looked for plural web names (`decisions/`, `ledger/`)
and web keys (`decision_ref`, `entry_ref`), so every real `Decision` and
`LedgerEntry` was refused and M8 showed $0.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from flywheel.contracts.entities import (
    Checkpoint,
    Cluster,
    Decision,
    Episode,
    FixRateEvent,
    LedgerEntry,
    QAReport,
    Release,
    RunPlan,
    Score,
    Source,
)
from flywheel.store.ledger_append import append_ledger_entry
from flywheel.store.paths import StorePaths
from flywheel.store.tables import TableWriter
from pydantic import BaseModel

from web.api.readmodel import SinkReadModel, SinkTables
from web.fwsync.mapping import (
    DROPPED_FIELDS,
    ENTITY_TABLES,
    MAPPED_FIELDS,
    map_checkpoint,
    map_decision,
    map_fix_rate_event,
    map_ledger_entry,
    map_release,
    map_run_plan,
    map_source,
)
from web.fwsync.runner import run_import
from web.fwsync.sink import JsonlSink
from web.tests.test_loader_matches_schema import _columns, _resolves

FIXTURES = (
    Path(__file__).resolve().parents[2]
    / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"
)
SHA = "a" * 64

MODELS: dict[str, type[BaseModel]] = {
    "Source": Source, "RunPlan": RunPlan, "Release": Release, "Checkpoint": Checkpoint,
    "Cluster": Cluster, "FixRateEvent": FixRateEvent, "Decision": Decision,
    "LedgerEntry": LedgerEntry,
}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


@pytest.fixture
def core(tmp_path: Path) -> dict[str, Any]:
    """A store root holding one of everything the core writes, plus the web rows it needs.

    `datasets.jsonl` and `recommendation.json` are web artifacts: the contract
    has no dataset or recommendation entity, and the loader resolves an
    episode's lot and a cluster's round through them (W12).
    """
    root = tmp_path / "fw"
    paths = StorePaths(root)
    source = Source.model_validate({
        "uri": "hf://datasets/psi/demo", "sha256": SHA, "downloaded_at": "2026-11-01T00:00:00Z",
        "data_class": "public", "license": "cc-by-4.0", "path": "two_table/",
    })
    plan = RunPlan.model_validate({
        "name": "round 1", "purpose": "round", "status": "frozen", "lock_path": "runplan.lock.json",
        "lock_sha256": SHA, "frozen_at": "2026-11-02T00:00:00Z", "task_id": "two_table",
    })
    draft = RunPlan.model_validate({"name": "round 2", "purpose": "round"})
    episode = Episode.model_validate({**json.loads((FIXTURES / "Episode.json").read_text()),
                                      "source_id": source.id})
    report = QAReport.model_validate({**json.loads((FIXTURES / "QAReport.json").read_text()),
                                      "episode_id": episode.episode_id})
    release = Release.model_validate({
        "name": "rel 1", "status": "frozen", "manifest_sha256": SHA,
        "frozen_at": "2026-11-03T00:00:00Z",
        "items": [{"episode_id": episode.episode_id, "weight": 1.0, "excluded": False,
                   "reasons": []},
                  {"episode_id": "ep_gone", "weight": 1.0, "excluded": True,
                   "reasons": ["sync", "jerk"]}],
    })
    checkpoint = Checkpoint.model_validate({"weights_sha256": SHA, "uri": "ckpt/a", "step": 100,
                                            "release_id": release.id})
    cluster = Cluster.model_validate({**json.loads((FIXTURES / "Cluster.json").read_text()),
                                      "id": "", "run_plan_id": plan.id})
    event = FixRateEvent.model_validate({"cluster_id": cluster.id, "intervention_id": "iv_1",
                                         "n_conditions": 4, "fixed": 2, "p_parent": 0.2,
                                         "p_candidate": 0.6})
    decision = Decision.model_validate(json.loads((FIXTURES / "Decision.json").read_text()))
    estimate = LedgerEntry.model_validate({
        "activity": "train", "resource_type": "gpu_hour_rtx3060", "quantity": 1.5,
        "unit": "hour", "usd_amount": 0.3, "measure_kind": "estimated",
        "run_plan_id": plan.id, "job_id": "job_train_1", "human_hours": 0.5,
    })
    measured = LedgerEntry.model_validate({
        "activity": "train", "resource_type": "gpu_hour_rtx3060", "quantity": 2.0,
        "unit": "hour", "usd_amount": 0.4, "measure_kind": "measured",
        "estimate_entry_id": estimate.id, "run_plan_id": plan.id, "job_id": "job_train_1",
    })
    for table, rows in (
        ("source", [source]), ("run_plan", [plan, draft]), ("episode", [episode]),
        ("qa_report", [report]), ("release", [release]), ("checkpoint", [checkpoint]),
        ("cluster", [cluster]), ("fix_rate_event", [event]), ("decision", [decision]),
        ("score", [Score.model_validate(json.loads((FIXTURES / "Score.json").read_text()))]),
    ):
        TableWriter(table, paths=paths).append_many(list(rows))
    append_ledger_entry(estimate, paths)
    append_ledger_entry(measured, paths)
    _write_json(root / "datasets.jsonl", {
        "dataset_code": "ds_psi", "source_ref": source.id, "source_kind": "teleop",
        "data_class": "public", "license": "cc-by-4.0", "status": "READY_FOR_TRAINING",
        "has_seeded_faults": False, "episode_count": 1,
    })
    _write_json(root / "recommendation.json", {
        "recommendation_ref": "rec_1", "run_plan_ref": plan.id, "task_id": "two_table",
        "checkpoint_ref": None, "evaluation_ref": None,
        "round_no": 1, "status": "AWAITING_REVIEW", "budget_usd": 100.0,
        "budget_human_minutes": 60.0, "budget_gpu_hours": 10.0,
    })
    return {"root": root, "source": source, "plan": plan, "draft": draft, "release": release,
            "checkpoint": checkpoint, "cluster": cluster, "event": event,
            "decision": decision, "estimate": estimate, "measured": measured,
            "episode": episode, "report": report}


def _rows(sink: Path, table: str) -> list[dict[str, Any]]:
    path = sink / f"{table}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_the_core_store_loads_with_no_rejected_row(core: dict[str, Any], tmp_path: Path) -> None:
    sink = tmp_path / "sink"
    result = run_import(core["root"], JsonlSink(directory=sink))

    assert result.status == "ok", result.errors
    expected = {
        "sources": 1, "run_plans": 1, "episodes": 1, "episode_qa_reports": 1, "releases": 1,
        "release_items": 2, "model_checkpoints": 1, "failure_clusters": 1,
        "fix_rate_events": 1, "decisions": 1, "cost_ledger_entries": 2,
    }
    assert {table: len(_rows(sink, table)) for table in expected} == expected


def test_a_real_decision_and_ledger_entry_keep_their_ids_and_amounts(
    core: dict[str, Any], tmp_path: Path
) -> None:
    # Hiếu's probe: these two were refused for missing `decision_ref`/`entry_ref`.
    sink = tmp_path / "sink"
    run_import(core["root"], JsonlSink(directory=sink))

    [decision] = _rows(sink, "decisions")
    assert decision["decision_ref"] == core["decision"].id
    assert decision["conclusion"] == "pass"
    assert decision["meta"]["signed_by"] == "hieu"
    ledger = {row["entry_ref"]: row for row in _rows(sink, "cost_ledger_entries")}
    estimate, measured = ledger[core["estimate"].id], ledger[core["measured"].id]
    assert (estimate["measure_kind"], estimate["usd_amount"]) == ("estimated", 0.3)
    assert (measured["measure_kind"], measured["usd_amount"]) == ("measured", 0.4)
    assert measured["estimate_entry_ref"] == core["estimate"].id
    assert estimate["human_minutes"] == 30.0
    assert measured["gpu_hours"] == 2.0
    assert measured["run_plan_ref"] == core["plan"].id
    # The round is found through the run plan, so BR-07 sees the spend.
    assert measured["recommendation_ref"] == "rec_1"


def test_m8_shows_the_real_spend_and_its_forecast_error(
    core: dict[str, Any], tmp_path: Path
) -> None:
    sink = tmp_path / "sink"
    run_import(core["root"], JsonlSink(directory=sink))
    model = SinkReadModel(SinkTables(sink))

    ledger = model.ledger()
    assert sorted(row["measure_kind"] for row in ledger) == ["estimated", "measured"]
    [row] = model.cost_by_branch()["rows"]
    assert row["measured_usd"] == 0.4
    assert row["estimated_usd"] == 0.3
    assert row["forecast_pairs"] == 1
    assert row["usd_forecast_error"] == pytest.approx(0.1)
    recommendation = model.recommendation("rec_1")
    assert recommendation is not None
    budget = {line["resource"]: line for line in recommendation["budget"]}
    assert budget["usd"]["used"] == 0.4
    assert budget["gpu_hours"]["used"] == 2.0


def test_a_draft_run_plan_is_listed_not_refused(core: dict[str, Any], tmp_path: Path) -> None:
    result = run_import(core["root"], JsonlSink(directory=tmp_path / "sink"))

    assert any(core["draft"].id in line and "draft" in line for line in result.ignored)
    assert not any(core["draft"].id in error["message"] for error in result.errors)


def test_a_core_table_the_web_has_no_place_for_is_listed_with_a_reason(
    core: dict[str, Any], tmp_path: Path
) -> None:
    result = run_import(core["root"], JsonlSink(directory=tmp_path / "sink"))

    score = [line for line in result.ignored if "score" in line]
    assert score and all("chưa có bảng" in line for line in score)


def test_a_web_field_on_a_core_row_is_refused(core: dict[str, Any], tmp_path: Path) -> None:
    # The catalog path is strict: the contract forbids extra fields.
    part = next((core["root"] / "sites/local/catalog/decision").glob("part-*.jsonl"))
    row = json.loads(part.read_text(encoding="utf-8"))
    part.write_text(json.dumps({**row, "decision_ref": "dec_web"}) + "\n", encoding="utf-8")

    result = run_import(core["root"], JsonlSink(directory=tmp_path / "sink"))

    assert result.status == "partial"
    assert any("decision_ref" in error["message"] for error in result.errors)


def test_a_cluster_whose_round_cannot_be_found_is_refused(
    core: dict[str, Any], tmp_path: Path
) -> None:
    (core["root"] / "recommendation.json").unlink()
    result = run_import(core["root"], JsonlSink(directory=tmp_path / "sink"))

    assert any(error["table"] == "failure_clusters" for error in result.errors)


def test_a_measured_mock_row_without_its_estimate_is_refused(tmp_path: Path) -> None:
    # R5 holds for the mock too: the tolerant path checks it.
    _write_json(tmp_path / "src" / "ledger.jsonl", {
        "entry_ref": "led_x", "entry_kind": "ENTRY", "activity": "train",
        "resource_type": "gpu_hours", "quantity": 1, "unit": "hour", "price_book_name": "p",
        "measure_kind": "measured", "estimate_entry_ref": None, "usd_amount": 2.0,
        "experiment_code": "exp_A",
    })
    result = run_import(tmp_path / "src", JsonlSink(directory=tmp_path / "sink"))

    assert result.status == "failed"
    assert "estimate_entry_ref" in result.errors[0]["message"]


@pytest.mark.parametrize("name", sorted(MAPPED_FIELDS))
def test_every_contract_field_is_mapped_or_dropped(name: str) -> None:
    fields = set(MODELS[name].model_fields)
    dropped = {key.split(".", 1)[1] for key in DROPPED_FIELDS if key.startswith(f"{name}.")}
    assert not MAPPED_FIELDS[name] & dropped, "a field is both mapped and dropped"
    assert MAPPED_FIELDS[name] | dropped == fields, (
        f"{name}: unaccounted {sorted(fields - MAPPED_FIELDS[name] - dropped)}, "
        f"stale {sorted((MAPPED_FIELDS[name] | dropped) - fields)}"
    )


def test_every_column_a_contract_mapper_writes_exists_in_the_schema(
    core: dict[str, Any],
) -> None:
    schema = _columns()
    rows: list[tuple[str, dict[str, Any]]] = [
        ("sources", map_source(core["source"].model_dump(mode="json"))),
        ("run_plans", map_run_plan(core["plan"].model_dump(mode="json"))),
        *map_release(core["release"].model_dump(mode="json")),
        ("model_checkpoints", map_checkpoint(core["checkpoint"].model_dump(mode="json"))),
        ("fix_rate_events", map_fix_rate_event(core["event"].model_dump(mode="json"))),
        ("decisions", map_decision(core["decision"].model_dump(mode="json"))),
    ]
    from web.fwsync.mapping import CatalogLookups

    rows.append(("cost_ledger_entries",
                 map_ledger_entry(core["measured"].model_dump(mode="json"), CatalogLookups())))
    assert set(ENTITY_TABLES.values()) - {"failure_clusters"} <= {table for table, _ in rows}
    for table, row in rows:
        homeless = sorted(column for column in row if not _resolves(column, schema[table]))
        assert not homeless, f"{table}: {homeless} have no column"
