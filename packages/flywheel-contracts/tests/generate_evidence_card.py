"""Generate the shared EvidenceCard example and its JSON Schema (DA-39).

One L-GRASP cluster of the two-table task at level 1: 7 failures on the dev
set, 5 representatives drawn with a recorded seed. Three lack coverage, one
started step 2 from a bad state, and one could not be judged on R5 because its
camera parameters were never written, so it is CHƯA RÕ and its data checks are
not judged either. Thresholds are those of configs/eval/diagnosis/system.yaml
and stage.yaml of DA-13 (assumptions until DA-37 calibrates them); the camera
reference is the G0 hash DA-38 pinned. Ids of the cluster, scores and run plan
are computed by the catalog entities, so they are the ids those records get.

Run from the repo root: uv run python packages/flywheel-contracts/tests/generate_evidence_card.py
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from flywheel.contracts.base import event_id, new_ulid
from flywheel.contracts.entities import Cluster, RunPlan, Score
from flywheel.contracts.evidence import EvidenceCard

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "packages/flywheel-contracts/schemas/EvidenceCard.json"
EXAMPLE = (
    ROOT / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/EvidenceCard.json"
)

TASK = "g1_locomotion_pick_between_tables"
EMBODIMENT = "g1_sonic_dwbc@1"
CAMERA_REFERENCE = "fc7f9c90ebbf8c4662fd70e58de5aed668c0fbc5ccfbbd951dce705729cdeea2"
# 4/11/2026 00:00 UTC, so the ULIDs are stable from one run to the next.
T0 = 1793750400000


def sha(text: str) -> str:
    """Stand-in hash of a file this example has no copy of."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ulid_id(prefix: str, n: int) -> str:
    return event_id(prefix, new_ulid(T0 + n, n.to_bytes(10, "big")))


SYSTEM_CONFIG = sha("configs/eval/diagnosis/system.yaml@DA-13")
STAGE_TABLE = sha("configs/eval/diagnosis/stage.yaml@DA-13")
SCORER_CONFIG = sha("configs/eval/scorer/two_table.yaml@DA-36")

run_plan = RunPlan(
    name="he1-dev-two-table-round1", purpose="round", task_id=TASK, embodiment_id=EMBODIMENT
)
members = [ulid_id("ep", n) for n in range(1, 8)]
cluster = Cluster(
    task_id=TASK,
    embodiment_id=EMBODIMENT,
    run_plan_id=run_plan.id,
    first_failed_step=2,
    failure_kind="L-GRASP",
    level=1,
    failure_class="grasp",
    representative_seed=20261104,
    member_episode_ids=members,
)


def score(episode_id: str) -> Score:
    return Score(
        task_id=TASK,
        embodiment_id=EMBODIMENT,
        episode_id=episode_id,
        config_sha256=SCORER_CONFIG,
        trace_sha256=sha(f"trace/{episode_id}"),
        scorer_version="0.1.0",
        success=False,
        step_status=["pass", "fail", *["not_attempted"] * 4],
        first_failed_step=2,
        failure_kind="L-GRASP",
        failure_class="grasp",
        level=1,
    )


def judged(
    check: str, value: object, threshold: object, fired: bool, **extra: object
) -> dict[str, Any]:
    outcome = "fired" if fired else "not_fired"
    return {"check": check, "outcome": outcome, "value": value, "threshold": threshold, **extra}


def not_judged(
    check: str, reason: str, threshold: object = None, **extra: object
) -> dict[str, Any]:
    return {
        "check": check,
        "outcome": "not_judged",
        "threshold": threshold,
        "skipped_reason": reason,
        **extra,
    }


def system_checks(
    latency: float, upper: float, lower: float, sync: float, camera: bool
) -> list[dict[str, Any]]:
    checks = [
        judged("infra_status", "ok", ["ok"], False),
        judged("tracking_error", upper, 0.10, False, part="upper_body"),
        judged("tracking_error", lower, 0.15, False, part="lower_body"),
        judged("latency_p99", latency, 0.15, False),
        judged("buffer_underruns", 0.0, 0.0, False),
        judged("sync_offset", sync, 0.02, False),
    ]
    if camera:
        checks.append(judged("camera_reference", CAMERA_REFERENCE, CAMERA_REFERENCE, False))
    else:
        reason = "không có camera_params.jsonl trong thư mục trace: R5 CHƯA RÕ"
        checks.append(not_judged("camera_reference", reason, CAMERA_REFERENCE))
    return checks


def data_checks(reset: int, distance: float | None) -> list[dict[str, Any]]:
    checks = [
        judged("planner_feasible", True, None, False),
        judged("reset_success", reset / 10, 0.8, reset >= 8, n_success=reset, n_runs=10),
    ]
    if distance is None:
        reason = "dừng ở bước 6: s_k ≥ τ_k là TRẠNG THÁI ĐẦU XẤU (spec mục 6.6)"
        return [
            *checks,
            not_judged("nominal_visuals", reason),
            not_judged("in_train_domain", reason),
            not_judged("coverage_distance", reason, 0.12),
        ]
    return [
        *checks,
        judged("nominal_visuals", False, None, False),
        judged("in_train_domain", True, None, False),
        judged("coverage_distance", distance, 0.12, distance > 0.12),
    ]


def unjudged_data_checks() -> list[dict[str, Any]]:
    reason = "chưa chạy: kiểm hệ thống chưa xong (spec mục 6.9, hệ thống trước)"
    return [
        not_judged("planner_feasible", reason),
        not_judged("reset_success", reason, 0.8),
        not_judged("nominal_visuals", reason),
        not_judged("in_train_domain", reason),
        not_judged("coverage_distance", reason, 0.12),
    ]


def unjudged_stage() -> list[dict[str, Any]]:
    reason = "chưa chạy: quy lỗi về stage đi sau kiểm hệ thống (spec mục 6.4, bước 4b)"
    rows = [
        "stage1_perception",
        "stage3_action_group",
        "runtime_distribution_shift",
        "stage3_forgetting",
        "out_of_domain",
    ]
    return [{"row_id": row, "reason": reason} for row in rows]


def stage(hand_error: float) -> dict[str, Any]:
    return {
        "stage_table_sha256": STAGE_TABLE,
        "stage_hypotheses": [
            {
                "row_id": "stage3_action_group",
                "attribute_to": "Stage 3 · học action nhóm đó",
                "intervention": "Thêm demo hoặc dữ liệu sinh (S1, S2) cho bước k",
                "consumes_budget": True,
                "confirmed": True,
                "evidence": [
                    {
                        "probe": "P3",
                        "where": "nhóm action `hand`",
                        "value": hand_error,
                        "threshold": 0.3,
                    },
                ],
            }
        ],
        "stage_unavailable": [
            {
                "row_id": "stage3_forgetting",
                "reason": "không có P4: checkpoint gốc của tác giả, không có checkpoint cha",
            }
        ],
    }


def representative(
    n: int, diagnosis: str, checks: list[dict[str, Any]], **rest: object
) -> dict[str, Any]:
    episode_id = members[n]
    return {
        "episode_id": episode_id,
        "score_id": score(episode_id).id,
        "condition_seed": 9100 + n,
        "trace_sha256": sha(f"trace/{episode_id}"),
        "system_config_sha256": SYSTEM_CONFIG,
        "checks": checks,
        "diagnosis": diagnosis,
        **rest,
    }


gain = {
    "n_failures": 7,
    "cap": 10,
    "n_effective": 7,
    "n_dev": 90,
    "fix_rate_alpha": 1.0,
    "fix_rate_beta": 1.0,
    "expected_gain_pp": 100.0 * 7 / 90 * 0.5,
}
card = {
    "cluster_id": cluster.id,
    "run_plan_id": run_plan.id,
    "task_id": TASK,
    "embodiment_id": EMBODIMENT,
    "level": 1,
    "first_failed_step": 2,
    "failure_kind": "L-GRASP",
    "failure_class": "grasp",
    "member_episode_ids": members,
    "representative_seed": 20261104,
    "representatives": [
        representative(
            0,
            "coverage_gap",
            system_checks(0.083, 0.041, 0.063, 0.008, True) + data_checks(3, 0.19),
            **stage(0.41),
        ),
        representative(
            2,
            "coverage_gap",
            system_checks(0.091, 0.038, 0.071, 0.011, True) + data_checks(4, 0.23),
            **stage(0.44),
        ),
        representative(
            3,
            "bad_start_state",
            system_checks(0.079, 0.044, 0.058, 0.009, True) + data_checks(9, None),
            **stage(0.33),
        ),
        representative(
            5,
            "coverage_gap",
            system_checks(0.087, 0.036, 0.066, 0.007, True) + data_checks(2, 0.17),
            **stage(0.38),
        ),
        representative(
            6,
            "unknown",
            system_checks(0.085, 0.040, 0.061, 0.010, False) + unjudged_data_checks(),
            stage_unavailable=unjudged_stage(),
        ),
    ],
    "diagnosis": "coverage_gap",
    "proposal": {
        "kind": "sim_s1",
        "description": (
            "Sinh 20 rollout S1 đạt QA cho mỗi lỗi, điều kiện lấy đều trong bán kính τ_cov "
            "quanh điều kiện lỗi và trong miền train (spec mục 6.10)"
        ),
        "consumes_budget": True,
        "quantity": 140,
        "unit": "rollout",
        "gain": gain,
        "cost": {
            "measure_kind": "estimated",
            "usd_amount": 0.42,
            "human_hours": 0.5,
            "ledger_entry_ids": [ulid_id("led", 20)],
        },
        "intervention_id": ulid_id("iv", 21),
    },
    "decision": {
        "verdict": "accept",
        "decision_id": ulid_id("dec", 22),
        "signed_by": "hieu",
        "reason": "3/5 đại diện thiếu vùng phủ, P3 nhóm `hand` cao trên cả ba",
    },
}

if __name__ == "__main__":
    data = EvidenceCard.model_validate(card).model_dump(mode="json")
    EXAMPLE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SCHEMA.write_text(
        json.dumps(EvidenceCard.model_json_schema(), indent=2) + "\n", encoding="utf-8"
    )
