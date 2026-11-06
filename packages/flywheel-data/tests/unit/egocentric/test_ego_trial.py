"""DA-04 task 3: the labelling-model trial with fake models (design 6.7.4; D3).

The real trial calls RoboBrain 2.5 and Molmo2 on rtx3060; here the fakes answer by
how many images they get, so the measured numbers are known in advance.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from ego_data import write_mp4
from flywheel.contracts.entities import Decision
from flywheel.data.ingest.egocentric import api, trial
from flywheel.data.ingest.egocentric.config import EgoConfig
from flywheel.data.ingest.egocentric.source import register_egodex

SIMPLE_FRAMES = 90


class Fake:
    def __init__(self, image: int, point: str) -> None:
        self.image, self.answer, self.latencies_s = image, point, []  # type: list[float]

    def complete(self, prompt: str, images: Sequence[bytes]) -> str:
        self.latencies_s.append(0.5)
        return f"Image {self.image}" if len(images) > 1 else self.answer


def simple_dataset(root: Path) -> Path:
    (root / "meta").mkdir(parents=True)
    (root / "meta" / "info.json").write_text(json.dumps({"fps": 30, "features": {
        "observation.images.egocentric": {"shape": [36, 64, 3]}}}))
    for index in range(trial.CLIPS):
        hand = np.zeros((SIMPLE_FRAMES, 14))
        hand[:, 7] = np.linspace(0, 1, SIMPLE_FRAMES)  # the right hand closes steadily
        table = pa.table({trial.SIMPLE_HAND: list(hand)})
        path = root / trial.SIMPLE_DATA.format(index=index)
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, path)
        write_mp4(root / trial.SIMPLE_VIDEO.format(index=index), SIMPLE_FRAMES)
    return root


def test_simple_grasp_is_where_the_moving_hand_is_half_way() -> None:
    hand = np.zeros((100, 14))
    hand[:, 9] = np.linspace(0, 2, 100)
    assert trial.simple_grasp(hand) == 50


def test_the_trial_measures_boundaries_points_and_latency(
    tmp_path: Path, store: Path, cfg: EgoConfig
) -> None:
    work = tmp_path / "work"
    api.ingest(register_egodex(store, cfg), work, cfg, store, "train")
    api.write_eb_poses(work)
    api.annotate(work, cfg)
    simple = simple_dataset(tmp_path / "psi")
    grasp = trial.simple_grasp(np.linspace(0, 1, SIMPLE_FRAMES)[:, None] * np.eye(14)[7])
    frames = trial.clip_frames(grasp, SIMPLE_FRAMES, 30)
    marked = {str(f): [0.5, 0.5] for f in frames}
    marked[str(frames[0])] = None  # the object is hidden in this frame
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({"episodes": {str(i): marked for i in range(trial.CLIPS)},
                                     "object": "box", "instruction": "pick the box",
                                     "marked_by": "test"}))
    # image 6 of 10 is the frame closest after the grasp; (500, 500) is the image centre
    models = {"robobrain": Fake(6, "[(500, 500)]"), "molmo": Fake(1, "nothing to point at")}
    result = trial.run(work, simple, reference, models, cfg, tmp_path / "out", {"molmo": "cpu"})

    summary = result["summary"]
    robobrain = summary["robobrain"]
    assert robobrain["simple"]["point_frames"] == trial.CLIPS * (trial.PER_CLIP - 1)
    assert robobrain["simple"]["point_hit_rate"] == 1.0
    assert robobrain["simple"]["boundary_median_frames"] == abs(frames[5] - grasp)
    assert summary["molmo"]["simple"]["point_unparsed"] == trial.CLIPS * (trial.PER_CLIP - 1)
    assert summary["molmo"]["vram"] == "cpu" and summary["robobrain"]["latency_median_s"] == 0.5
    clips = 1 + trial.CLIPS  # the synthetic EgoDex episodes share one instruction
    assert robobrain["queries"] == clips * (1 + trial.PER_CLIP)
    assert summary["rule_on_ea"]["boundary_errors_frames"] == [None]  # no E-A in the work dir

    decision = Decision.model_validate_json((tmp_path / "out" / "decision.json").read_text())
    assert decision.verdict == "open" and decision.subject_kind == "labelling_model"
    assert decision.id == result["decision"]
    assert "Pointing: robobrain" in decision.reason and "marked by test" in decision.reason
    rows = json.loads((tmp_path / "out" / "rows.json").read_text())
    assert len(rows["clips"]) == clips


def test_a_model_left_out_of_boundary_only_points(
    tmp_path: Path, store: Path, cfg: EgoConfig
) -> None:
    work = tmp_path / "work"
    api.ingest(register_egodex(store, cfg), work, cfg, store, "train")
    api.write_eb_poses(work)
    api.annotate(work, cfg)
    simple = simple_dataset(tmp_path / "psi")
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({"episodes": {"0": {}}, "object": "box"}))
    models = {"robobrain": Fake(9, "[(500, 500)]"), "molmo": Fake(1, "[(500, 500)]")}
    result = trial.run(work, simple, reference, models, cfg, tmp_path / "out",
                       boundary={"robobrain"})
    molmo = result["summary"]["molmo"]
    assert molmo["egodex"]["boundary_errors_frames"] == []
    assert molmo["boundary_seconds_median"] is None and molmo["point_seconds_median"] is not None
    assert models["molmo"].latencies_s and len(models["molmo"].latencies_s) == 2 * trial.PER_CLIP
    decision = Decision.model_validate_json((tmp_path / "out" / "decision.json").read_text())
    assert decision.reason.startswith("Boundary: robobrain")
