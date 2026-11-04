"""Generate DA-13 contract examples and JSON schemas."""

import json
from pathlib import Path

from flywheel.contracts.diagnosis import StageAttribution, SystemDiagnosis

root = Path(__file__).resolve().parents[3]
schemas = root / "packages/flywheel-contracts/schemas"
fixtures = root / "packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts"
examples = {
    SystemDiagnosis: {
        "episode_id": "ep_1",
        "diagnosis": "controller",
        "config_sha256": "a" * 64,
        "trace_sha256": "b" * 64,
        "rtc_sha256": "c" * 64,
        "camera_sha256": None,
        "infra_sha256": "d" * 64,
        "infra_status": "ok",
        "findings": [{"code": "R3", "value": 0.2, "threshold": 0.1, "part": "upper"}],
        "skipped": [{"code": "R5", "reason": "camera reference unavailable"}],
    },
    StageAttribution: {
        "episode_id": "ep_1",
        "table_sha256": "e" * 64,
        "failed_step": 2,
        "hypotheses": [
            {
                "row_id": "stage3_action_group",
                "attribute_to": "stage3",
                "intervention": "collect arm demonstrations",
                "consumes_budget": True,
                "evidence": [{"probe": "P3", "where": "arm", "value": 0.9, "threshold": 0.5}],
            }
        ],
        "unavailable": [{"code": "stage1_perception", "reason": "P1 unavailable"}],
    },
}
for model, example in examples.items():
    schemas.joinpath(model.__name__ + ".json").write_text(
        json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
    )
    fixtures.joinpath(model.__name__ + ".json").write_text(
        model.model_validate(example).model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
