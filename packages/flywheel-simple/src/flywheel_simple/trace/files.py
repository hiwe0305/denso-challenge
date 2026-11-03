"""Write each traced episode as the files DA-13 reads (DA-38 task 3; PO review 3/11/2026, B1).

One SIMPLE eval run is one job; each of its episodes is one trace, in a directory named
after its `trace_id` (PO decision G1 on PR #48, 3/11/2026):

    <job_dir>/
      rtc.jsonl                 # DA-19 RTC client, per job, keyed by trace_id; not written here
      <trace_id>/               # RolloutResult.trace_ref.uri
        steps.jsonl             # one TraceStep per control cycle
        camera_params.jsonl     # one CameraParams per line, one per camera the policy sees
        rollout_result.json     # RolloutResult of the episode: sim_success, infra_status
                                # (PO decision G1b, 3/11/2026: RESULT_NAME)

Field names are those of `flywheel.contracts.trace` (Contract change #31, PR #48 at
5b373e2) and `flywheel.contracts.v0.RolloutResult`. The writer runs inside SIMPLE's
venv, which has no flywheel package, so it writes plain JSON and the tests validate
it against the contracts.

`CameraParams.reference_sha256` is the camera reference pinned at G0 for the task,
handed in from the job spec (PO decision Q3, 3/11/2026). Without one there is no
`camera_params.jsonl`, so R5 says CHƯA RÕ instead of passing on a hash nobody pinned.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from flywheel_simple.trace.hook import EpisodeTrace
from flywheel_simple.trace.signals import encode, encode_all

STEPS_NAME = "steps.jsonl"
CAMERA_NAME = "camera_params.jsonl"
RESULT_NAME = "rollout_result.json"  # Đã chốt 3/11/2026 [Hiếu], G1b

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _trace_step(episode: EpisodeTrace, cycle: Any) -> dict[str, Any]:
    return {
        "trace_id": episode.trace_id,
        "episode_id": episode.episode_id,
        "run_plan_id": episode.run_plan_id,
        "step": cycle.step,
        "t_state": encode(cycle.t_state),
        "t_image": None if cycle.t_image is None else encode(cycle.t_image),
        "cmd_upper": encode_all(cycle.cmd_upper),
        "meas_upper": encode_all(cycle.meas_upper),
        "cmd_lower": encode_all(cycle.cmd_lower),
        "meas_lower": encode_all(cycle.meas_lower),
        "dropped_frames": cycle.dropped_frames,
    }


class EpisodeDirSink:
    """`TraceSink` writing one `<trace_id>/` directory per episode under `job_dir`."""

    def __init__(
        self,
        job_dir: Path,
        *,
        job_id: str,
        camera_reference_sha256: str | None,
        adapter_version: str,
    ) -> None:
        if camera_reference_sha256 is not None and not _SHA256.match(camera_reference_sha256):
            raise ValueError(
                f"camera reference must be a sha256 hex digest, got {camera_reference_sha256!r}"
            )
        self.job_dir = job_dir
        self.job_id = job_id
        self.camera_reference_sha256 = camera_reference_sha256
        self.adapter_version = adapter_version

    def write(self, episode: EpisodeTrace) -> None:
        directory = self.job_dir / episode.trace_id
        directory.mkdir(parents=True, exist_ok=True)
        steps_path = directory / STEPS_NAME
        lines = [json.dumps(_trace_step(episode, c), allow_nan=False) for c in episode.cycles]
        data = "".join(line + "\n" for line in lines).encode("utf-8")
        steps_path.write_bytes(data)
        if self.camera_reference_sha256 is not None and episode.cameras:
            cameras = [
                {
                    "trace_id": episode.trace_id,
                    "episode_id": episode.episode_id,
                    "uid": c.uid,
                    "mount": c.mount,
                    "width": c.width,
                    "height": c.height,
                    "fx": c.fx,
                    "fy": c.fy,
                    "cx": c.cx,
                    "cy": c.cy,
                    "pose": list(c.pose),
                    "reference_sha256": self.camera_reference_sha256,
                }
                for c in episode.cameras
            ]
            camera_lines = "".join(json.dumps(c, allow_nan=False) + "\n" for c in cameras)
            (directory / CAMERA_NAME).write_text(camera_lines, encoding="utf-8")
        result = {
            "job_id": self.job_id,
            "trace_ref": {
                "trace_id": episode.trace_id,
                "uri": directory.as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),  # of steps.jsonl
            },
            "sim_success": episode.sim_success,
            # SIMPLE reports every episode it finishes; one it never reported was cut off
            # by the simulator process (crash, or the env closed mid-episode)
            "infra_status": "ok" if episode.sim_success is not None else "simulator_error",
            "usage": {"wall_seconds": episode.wall_seconds, "gpu_seconds": 0.0},
            "camera_params_hash": self.camera_reference_sha256,
            "adapter_info": {"name": "flywheel-simple.trace", "version": self.adapter_version},
        }
        (directory / RESULT_NAME).write_text(json.dumps(result, indent=1), encoding="utf-8")
