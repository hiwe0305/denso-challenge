"""Running the scorer check again gives the same report (DA-37 task 6, AC 6).

The episodes are built here and go the whole way a real run goes: a trace on
disk, scored by `score_trace` under the two-table config, appended to the store
as a `Score`, next to a `rollout_result.json` that carries SIMPLE's flag. Then
the check runs twice, and the two reports have to be the same bytes, the same
hash and the same blob. The thresholds τ of tasks 3 and 4 join this test when
those tasks land; until then AC 6 is held for the report only.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from flywheel.contracts import TaskDefinition
from flywheel.eval.api import (
    SCORER_CONFIG_DIR,
    check_scorer_agreement,
    score_trace,
    store_score,
    store_scorer_agreement,
)
from flywheel.eval.scorer.artifact import STORE_RECORDS
from flywheel.eval.scorer.calibration import AGREEMENT_RECORDS
from flywheel.store.blobs import get_blob
from flywheel.store.paths import StorePaths

MakeRows = Callable[..., list[dict[str, object]]]
CONFIG = SCORER_CONFIG_DIR / "two-table.yaml"
RELEASE = "rel_demo_1"


def _rollout(trace_id: str, sim: bool | None, infra: str = "ok") -> dict[str, Any]:
    return {
        "job_id": "job1",
        "trace_ref": {"trace_id": trace_id, "uri": f"traces/{trace_id}", "sha256": None},
        "sim_success": sim,
        "infra_status": infra,
        "usage": {"wall_seconds": 10.0, "gpu_seconds": 0.0},
        "camera_params_hash": None,
        "adapter_info": {
            "name": "simple",
            "version": "0.1.0",
            "image_digest": None,
            "nondeterminism": [],
        },
        "timing": "sync",
    }


def _build(
    root: Path, task: TaskDefinition, make_rows: MakeRows, sig: Any, config: Path = CONFIG
) -> tuple[Path, Path]:
    """Five episodes: two clean, one dropped object, one with no contact signal,
    one infra failure. SIMPLE passes the first three and fails the dropped one,
    so the set holds an agreement of each kind and one of each mismatch."""
    episodes: list[tuple[str, list[dict[str, object]], bool | None, str]] = [
        ("job1-aaa", make_rows(), True, "ok"),
        ("job1-bbb", make_rows(), True, "ok"),
        ("job1-ccc", make_rows(hand_object_contact=sig.const(0.0)), True, "ok"),
        ("job1-ddd", make_rows(hand_object_contact=sig.const(0.0)), False, "ok"),
        ("job1-eee", make_rows(), None, "timeout"),
    ]
    store = root / "store"
    rollouts = root / "eval"
    for trace_id, rows, sim, infra in episodes:
        folder = rollouts / trace_id
        folder.mkdir(parents=True)
        trace = folder / "signals.jsonl"
        trace.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        (folder / "rollout_result.json").write_text(
            json.dumps(_rollout(trace_id, sim, infra)), encoding="utf-8"
        )
        store_score(score_trace(trace, task, config, episode_id=trace_id), store)
    return store, rollouts


def test_the_same_episodes_give_the_same_report_twice(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows, sig: Any
) -> None:
    store, rollouts = _build(tmp_path, task, make_rows, sig)

    first = check_scorer_agreement(store / STORE_RECORDS, rollouts, RELEASE)
    second = check_scorer_agreement(store / STORE_RECORDS, rollouts, RELEASE)

    assert first.canonical() == second.canonical()
    assert first.sha256 == second.sha256
    # The set really holds both answers and a mismatch, not five easy passes.
    assert (first.counted, first.sim_successes, first.sim_failures) == (4, 3, 1)
    assert [m.episode_id for m in first.mismatches] == ["job1-ccc"]
    assert [item.episode_id for item in first.excluded] == ["job1-eee"]


def test_rebuilding_the_set_from_scratch_gives_the_same_hash(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows, sig: Any
) -> None:
    # Two stores written separately, with nothing shared but the inputs: the
    # hash depends on the episodes and the scorer, not on paths or order.
    a_store, a_rollouts = _build(tmp_path / "a", task, make_rows, sig)
    b_store, b_rollouts = _build(tmp_path / "b", task, make_rows, sig)

    a = check_scorer_agreement(a_store / STORE_RECORDS, a_rollouts, RELEASE)
    b = check_scorer_agreement(b_store / STORE_RECORDS, b_rollouts, RELEASE)

    assert a.sha256 == b.sha256


def test_storing_the_rerun_points_at_the_same_blob(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows, sig: Any
) -> None:
    store, rollouts = _build(tmp_path, task, make_rows, sig)

    digests = [
        store_scorer_agreement(
            check_scorer_agreement(store / STORE_RECORDS, rollouts, RELEASE), store
        )[0]
        for _ in range(2)
    ]

    assert digests[0] == digests[1]
    lines = (store / AGREEMENT_RECORDS).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["report_sha256"] for line in lines] == digests
    assert get_blob(digests[0], StorePaths(store))


def test_another_config_is_another_report(
    tmp_path: Path, task: TaskDefinition, make_rows: MakeRows, sig: Any
) -> None:
    # Same thresholds, different bytes: the config hash changes, so the report
    # cannot pass for the one made under the original file.
    other = tmp_path / "two-table.yaml"
    shutil.copyfile(CONFIG, other)
    with other.open("a", encoding="utf-8") as handle:
        handle.write("\n# copy\n")
    base_store, base_rollouts = _build(tmp_path / "base", task, make_rows, sig)
    copy_store, copy_rollouts = _build(tmp_path / "copy", task, make_rows, sig, other)

    base = check_scorer_agreement(base_store / STORE_RECORDS, base_rollouts, RELEASE)
    copy = check_scorer_agreement(copy_store / STORE_RECORDS, copy_rollouts, RELEASE)

    assert base.config_sha256 != copy.config_sha256
    assert base.sha256 != copy.sha256
    assert base.agreement == copy.agreement
