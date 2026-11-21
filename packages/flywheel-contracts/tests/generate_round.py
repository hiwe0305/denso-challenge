"""Generate DA-43 contract examples (K1, K2) and the JSON schemas of the agentqa models.

The numbers are synthetic: they show the shape, not a result of any eval run.
"""

import json
from pathlib import Path
from typing import Any

from flywheel.contracts.agentqa import AgentReport, AgentReview, RoundDiagnosis
from flywheel.contracts.outcome import RolloutOutcome
from pydantic import BaseModel

root = Path(__file__).resolve().parents[3]
schemas = root / "packages/flywheel-contracts/schemas"
fixtures = root / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"

STEPS = ["approach_a", "grasp", "lift", "carry", "reach_b", "place", "release_stand"]
LEDGER = "led_01JD0000000000000000000000"


def outcome(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "episode_id": "ep_eval_0001",
        "run_plan_id": "rp_example",
        "task_id": "tray_transfer",
        "run": "example_run",
        "seed": 101,
        "level": 1,
        "repeat": 0,
        "sim_time_s": 24.0,
        "control_steps": 1200,
        "verdict": {
            "scorer_version": "2",
            "step_names": STEPS,
            "step_latched": [True] * 7,
            "step_latch_t": [2.0, 3.0, 4.0, 9.0, 15.0, 19.0, 22.0],
            "success": True,
        },
        "final": {
            "tray_to_target_m": 0.02,
            "yaw_error_deg": 3.0,
            "tray_on_target_table": True,
            "tray_pos_m": [1.5, 0.0, 0.8],
            "tray_quat": [1.0, 0.0, 0.0, 0.0],
        },
        "extrema": {"palm_handle_min_both_m": 0.03},
        "videos": ["videos/example_run/ep_eval_0001.mp4"],
    }
    base.update(over)
    return base


failed = outcome(
    episode_id="ep_eval_0002",
    seed=102,
    repeat=1,
    sim_time_s=30.0,
    control_steps=1500,
    verdict={
        "scorer_version": "2",
        "step_names": STEPS,
        "step_latched": [True, True, True, False, False, False, False],
        "step_latch_t": [2.5, 3.5, 5.0, None, None, None, None],
        "success": False,
        "failure_label": "L-TRAY-TILT",
        "failure_t": 7.5,
        "at_failure": {
            "tray_on_table": "none",
            "hand_contact_left": True,
            "hand_contact_right": False,
            "tilt_deg": 25.0,
            "tray_pos_m": [0.9, 0.1, 0.9],
            "tray_quat": [0.98, 0.2, 0.0, 0.0],
        },
    },
    other_verdicts=[
        {
            "scorer_version": "1",
            "step_names": STEPS,
            "step_latched": [False] * 7,
            "step_latch_t": [None] * 7,
            "success": False,
            "failure_label": "L-TRAY-TILT",
            "failure_t": 7.5,
        }
    ],
    final={
        "tray_to_target_m": 0.6,
        "yaw_error_deg": 40.0,
        "tray_on_target_table": False,
        "tray_pos_m": [0.9, 0.1, 0.0],
        "tray_quat": [0.7, 0.7, 0.0, 0.0],
    },
    extrema={
        "palm_handle_min_left_m": 0.02,
        "palm_handle_min_right_m": 0.04,
        "palm_handle_min_both_m": 0.04,
        "palm_handle_bar_min_left_m": 0.01,
        "palm_handle_bar_min_right_m": 0.03,
        "palm_handle_bar_min_both_m": 0.03,
    },
    videos=[],
)

fact = {"unit": "", "source_ref": "eval/example_run/outcomes.jsonl"}
diagnosis = {
    "round_id": "round_example",
    "task_id": "tray_transfer",
    "data_class": "public",
    "created_at": "2026-11-21T10:00:00Z",
    "agent_version": "4.0.0",
    "agent_hash": "b" * 64,
    "status": "degraded",
    "problems": ["no model profile was configured: every item is the code floor"],
    "report_ids": ["rep_eval_001"],
    "facts": [
        {"fact_id": "F1", "name": "carry_pass_rate", "value": 0.5, **fact, "origin": "code"},
        {"fact_id": "F2", "name": "tracking_p99_exceeds_tau", "value": True, **fact},
        {"fact_id": "F3", "name": "scorer_versions_agree", "value": False, **fact},
        {
            "fact_id": "F4",
            "name": "tray_tilted_in_frame",
            "value": True,
            **fact,
            "origin": "vision",
        },
    ],
    "clusters": [
        {
            "cluster_id": "example_run/carry/L-TRAY-TILT/l1",
            "run": "example_run",
            "step": "carry",
            "label": "L-TRAY-TILT",
            "level": 1,
            "size": 6,
            "blocked_data_spend": True,
        }
    ],
    "headline_cluster_id": "example_run/carry/L-TRAY-TILT/l1",
    "hypotheses": [
        {
            "hypothesis_id": "H1",
            "cluster_id": "example_run/carry/L-TRAY-TILT/l1",
            "diagnosis": "controller",
            "note": "arm tracking lags the command while carrying",
            "rule_id": "runtime.tracking",
            "rank": 1,
            "support": ["F2", "F4"],
            "contra": [],
            "explanation": "Tracking exceeds its bound ({F2}) while only {F1} of rollouts pass.",
            "source": "code",
        },
        {
            "hypothesis_id": "H2",
            "cluster_id": "example_run/carry/L-TRAY-TILT/l1",
            "diagnosis": "weak_skill",
            "note": "the policy tilts the tray when it turns",
            "rule_id": "data.weak_skill",
            "rank": 2,
            "support": ["F1"],
            "contra": ["F2", "F3"],
            "explanation": "",
            "source": "code",
        },
    ],
    "checks": [
        {
            "check_id": "C1",
            "name": "replay_command_open_loop",
            "cluster_id": "example_run/carry/L-TRAY-TILT/l1",
            "separates": [["H1", "H2"]],
            "cost": {
                "measure_kind": "estimated",
                "usd_amount": 0.5,
                "human_hours": 0.0,
                "ledger_entry_ids": [LEDGER],
            },
            "source": "code",
        }
    ],
    "proposals": [
        {
            "proposal_id": "P1",
            "hypothesis_id": "H1",
            "proposal": {
                "kind": "repair_ticket",
                "description": "Open a ticket on the arm tracking gains of the controller.",
                "consumes_budget": False,
            },
            "source": "code",
        }
    ],
    "not_judged": [
        {"what": "camera calibration", "reason": "no camera reference in the pack"},
    ],
}
invalid_diagnosis = json.loads(json.dumps(diagnosis))
invalid_diagnosis["hypotheses"][1]["explanation"] = "Only 3 of 6 rollouts pass the carry step."

examples: dict[str, tuple[type[BaseModel], dict[str, Any]]] = {
    "RolloutOutcome": (RolloutOutcome, outcome()),
    "RolloutOutcome-failed": (RolloutOutcome, failed),
    "RoundDiagnosis": (RoundDiagnosis, diagnosis),
}
invalid: dict[str, dict[str, Any]] = {
    # The successful rollout carrying a failure label.
    "invalid-RolloutOutcome": outcome(
        verdict={**outcome()["verdict"], "failure_label": "L-TIMEOUT", "failure_t": 20.0}
    ),
    "invalid-RoundDiagnosis": invalid_diagnosis,
}

for name, (model, example) in examples.items():
    fixtures.joinpath(name + ".json").write_text(
        model.model_validate(example).model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
for name, example in invalid.items():
    fixtures.joinpath(name + ".json").write_text(
        json.dumps(example, indent=2) + "\n", encoding="utf-8"
    )
for model in (RolloutOutcome, RoundDiagnosis, AgentReport, AgentReview):
    schemas.joinpath(model.__name__ + ".json").write_text(
        json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
    )
