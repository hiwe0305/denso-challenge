"""Generate checked-in contract examples and JSON Schemas for DA-25."""

import json
from pathlib import Path

from flywheel.contracts import artifacts as a
from flywheel.contracts.v0 import RolloutRequest

root = Path(__file__).resolve().parents[3]
schemas = root / "packages/flywheel-contracts/schemas"
fixtures = root / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"
fixtures.mkdir(parents=True, exist_ok=True)
sha = "a" * 64
p1 = {
    "checkpoint_id": "ckpt_1",
    "dataset_sha256": sha,
    "accuracy_by_question_type": {"object": 0.9},
}
p3 = {
    "checkpoint_id": "ckpt_1",
    "dataset_sha256": sha,
    "error_by_group": {"arm": 0.2},
    "error_by_chunk_pos": [0.1, 0.2],
    "hand_event_offset_steps": 1,
    "out_of_limit_dims": [],
}
examples = {
    a.ActionLayout: {
        "dimensions": [
            {"name": "arm_0", "group": "arm", "masked": False, "limit_low": -1.0, "limit_high": 1.0}
        ]
    },
    a.EpisodeMetadata: {"source_detail": "psi_data", "renderer": "mujoco"},
    a.Episode: {
        "episode_id": "ep_1",
        "kind": "teleop_demo",
        "operator_kind": "human",
        "is_root": True,
        "condition_id": "cond_1",
        "run_plan_id": "rp_1",
        "bundle_uri": "data/ep_1",
        "license": "example",
        "data_class": "public",
        "split": "train",
        "source_kind": "teleop",
        "action_quality": "measured",
        "deid_status": "verified",
        "embodiment_id": "g1_sonic_dwbc@1",
        "meta": {"source_detail": "psi_data", "renderer": "mujoco"},
    },
    a.ReplayReport: {"episode_id": "ep_1", "mode": "kinematic", "issues": []},
    a.DatasetReport: {
        "dataset_id": "ds_1",
        "episode_count": 1,
        "counts_by_source": {"psi_data": 1},
        "failed_checks_by_source": {},
    },
    a.DefectManifest: {
        "dataset_id": "ds_1",
        "seed": 5,
        "defects": [{"target_ref": "ep_1", "code": "D1", "parameters": {"frame": 1}}],
    },
    a.RTCInferenceRecord: {
        "job_id": "job_1",
        "trace_id": "trace_1",
        "chunk_index": 0,
        "observation_sent_s": 1.0,
        "chunk_received_s": 1.1,
        "delay_steps": 1,
        "buffer_level": 4,
        "boundary_jump": 0.0,
    },
    a.ProbeP1: p1,
    a.ProbeP2: {"checkpoint_id": "ckpt_1", "dataset_sha256": sha, "token_loss": 0.4},
    a.ProbeP3: p3,
    a.ProbeP4: {"checkpoint_id": "ckpt_1", "parent_checkpoint_id": "ckpt_0", "p1": p1, "p3": p3},
    a.QAReport: {
        "report_id": "qa_1",
        "episode_id": "ep_1",
        "threshold_version": "v1",
        "decision": "pass",
        "reasons": [],
        "checks": [{"name": "sync", "value": 0.01, "threshold": 0.1, "passed": True}],
    },
}
for model, example in examples.items():
    data = model.model_validate(example).model_dump(mode="json")
    (fixtures / (model.__name__ + ".json")).write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    (schemas / (model.__name__ + ".json")).write_text(
        json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
    )
(fixtures / "invalid-QAReport.json").write_text(
    json.dumps(
        {
            "report_id": "qa_1",
            "episode_id": "ep_1",
            "threshold_version": "v1",
            "decision": "invalid",
            "reasons": [],
            "checks": [],
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
request = RolloutRequest.model_validate(
    {
        "job_id": "job_1",
        "task": {"task_id": "task_1"},
        "condition": {"condition_id": "cond_1", "task": {"task_id": "task_1"}, "seed": 1},
        "level": 0,
        "rollout_seed": 1,
        "max_steps": 10,
        "timing": "async",
        "latency_profile_ref": "latency.json",
    }
)
(fixtures / "RolloutRequest.json").write_text(
    request.model_dump_json(indent=2) + "\n", encoding="utf-8"
)
(schemas / "RolloutRequest.json").write_text(
    json.dumps(RolloutRequest.model_json_schema(), indent=2) + "\n", encoding="utf-8"
)
