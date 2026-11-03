"""Per-episode quality of tray demos beyond pass/fail QA (DA-34, decision of 3/11/2026).

Every released episode already passed `check_success`, the minimal QA and replay
QA. They still differ in how cleanly the tray travels, so the demo sets keep only
episodes under fixed limits, written down before the pool was generated
(docs/he/tray.md section 7):

- `tilt_carry_max_deg`: largest tray tilt while the scorer counts it as carried
  (step `lift` reached, `place` not yet). The scorer fails an episode at 15 deg.
- `part_shift_end_mm`: largest distance a part ends from where it started, in the
  tray frame. A part is 35 mm wide; 20 mm means it slid across its compartment.
- `drop_vz_min`: fastest downward tray speed (m/s). Recorded, not filtered: every
  S1 episode drops the tray about 3.5 cm when the hands let go (planner D-25).

Reads the raw LeRobot episodes of a generate.py batch, which keep the privileged
`observation.tray_pose` (pos, quat wxyz), `observation.part_pos` and
`observation.tray_steps` columns that the Psi0 export drops.

    python -m flywheel_psi0.tray.quality --batch fwdata/simple/tray/gen/<run> --out quality.jsonl
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

FPS = 50
LIFT, PLACE = 2, 5  # indices in the scorer's STEP_NAMES
COLUMNS = ["observation.tray_pose", "observation.part_pos", "observation.tray_steps"]


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EpisodeQuality(_Frozen):
    seed: int
    frames: int
    tilt_carry_max_deg: float
    part_shift_end_mm: float
    part_shift_max_mm: float
    drop_vz_min: float


class QualityFilter(_Frozen):
    max_tilt_carry_deg: float = Field(gt=0)
    max_part_shift_end_mm: float = Field(gt=0)

    def passes(self, q: EpisodeQuality) -> bool:
        return (
            q.tilt_carry_max_deg <= self.max_tilt_carry_deg
            and q.part_shift_end_mm <= self.max_part_shift_end_mm
        )


def _rotations(quat_wxyz: NDArray[np.float64]) -> NDArray[np.float64]:
    q = quat_wxyz / np.linalg.norm(quat_wxyz, axis=1, keepdims=True)
    w, x, y, z = q.T
    return np.stack(
        [
            np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
            np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
            np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1),
        ],
        -2,
    )


def episode_quality(
    seed: int,
    tray_pose: NDArray[np.float64],
    part_pos: NDArray[np.float64],
    tray_steps: NDArray[np.float64],
) -> EpisodeQuality:
    """Quality of one episode from its (T, 7) tray pose, (T, 18) parts and (T, 7) steps."""
    rot = _rotations(tray_pose[:, 3:7])  # (T, 3, 3), tray -> world
    tilt = np.degrees(np.arccos(np.clip(rot[:, 2, 2], -1.0, 1.0)))
    carrying = (tray_steps[:, LIFT] > 0.5) & (tray_steps[:, PLACE] < 0.5)
    parts = part_pos.reshape(len(tray_pose), -1, 3) - tray_pose[:, None, :3]
    local = np.einsum("tij,tki->tkj", rot, parts)  # world -> tray frame
    shift = np.linalg.norm(local - local[0], axis=-1).max(axis=1)
    vz = np.diff(tray_pose[:, 2]) * FPS
    return EpisodeQuality(
        seed=seed,
        frames=len(tray_pose),
        tilt_carry_max_deg=round(float(tilt[carrying].max()) if carrying.any() else 0.0, 3),
        part_shift_end_mm=round(float(shift[-1]) * 1000, 2),
        part_shift_max_mm=round(float(shift.max()) * 1000, 2),
        drop_vz_min=round(float(vz.min()) if len(vz) else 0.0, 4),
    )


def batch_quality(batch: Path) -> list[EpisodeQuality]:
    """Quality of every recorded, QA-passed episode of a generate.py batch, by seed."""
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    out = []
    for log in sorted(batch.glob("shard-*/gen_log.jsonl")):
        for line in log.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if not (entry.get("recorded") and entry.get("qa") == "pass"):
                continue
            path = (
                log.parent / "raw/data/chunk-000" / f"episode_{entry['episode_index']:06d}.parquet"
            )
            table = pq.read_table(path, columns=COLUMNS).to_pydict()
            out.append(
                episode_quality(
                    int(entry["seed"]),
                    np.asarray(table[COLUMNS[0]], dtype=np.float64),
                    np.asarray(table[COLUMNS[1]], dtype=np.float64),
                    np.asarray(table[COLUMNS[2]], dtype=np.float64),
                )
            )
    return sorted(out, key=lambda q: q.seed)


def read_quality(path: Path) -> list[EpisodeQuality]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [EpisodeQuality.model_validate_json(line) for line in lines if line]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--batch", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = batch_quality(args.batch)
    args.out.write_text("".join(q.model_dump_json() + "\n" for q in rows), encoding="utf-8")
    print(f"wrote {args.out}: {len(rows)} episodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
