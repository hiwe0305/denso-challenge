"""Camera values as MuJoCo renders them, and the hash of a reference set (DA-38 AC 3).

SIMPLE (`engines/mujoco.py`, `_mujoco_camera_intrinsic_kwargs`) builds each camera
in one of two ways:

* no `CameraCfg.intrinsics`: `fovy = 2 atan(H / (2 fy))`, so the render has square
  pixels, f = (H / 2) / tan(fovy / 2), and the principal point at the image centre;
* with intrinsics: `sensor_size = [W, H]`, `focal_pixel = [fx, fy]` and
  `principal_pixel = [cx - W/2, cy - H/2]`, stored by MuJoCo as `cam_sensorsize` and
  `cam_intrinsic` (focal x, focal y, principal x, principal y in sensor units).

`mujoco_intrinsics` inverts both from the compiled model and the render size, so
the recorded values are those of the image the policy saw, not those of the config.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass

# decimals kept when hashing: 1e-9 px and 1e-9 m/quaternion units are below any calibration change
_HASH_DECIMALS = 9


@dataclass(frozen=True)
class CameraValues:
    """One camera of one episode: render size, pixel intrinsics, pose to its mount body.

    `pose` is (x, y, z, qw, qx, qy, qz), MuJoCo's camera frame relative to the body it is
    attached to (issue #31).
    """

    uid: str
    mount: str
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    pose: tuple[float, ...]


def mujoco_intrinsics(
    width: int,
    height: int,
    fovy_deg: float,
    *,
    sensorsize: Sequence[float],
    intrinsic: Sequence[float] | None,
) -> tuple[float, float, float, float]:
    """(fx, fy, cx, cy) in pixels of a `width` x `height` render of one MuJoCo camera."""
    sw, sh = (float(v) for v in sensorsize)
    if sw > 0 and sh > 0:
        if intrinsic is None:
            raise ValueError("a sensor-size camera needs cam_intrinsic")
        fx_s, fy_s, px_s, py_s = (float(v) for v in intrinsic)
        kx, ky = width / sw, height / sh
        return fx_s * kx, fy_s * ky, width / 2 + px_s * kx, height / 2 + py_s * ky
    if fovy_deg <= 0:
        raise ValueError(f"a fovy camera needs fovy > 0, got {fovy_deg}")
    f = (height / 2) / math.tan(math.radians(fovy_deg) / 2)
    return f, f, width / 2, height / 2


def _canonical(cam: CameraValues) -> dict[str, object]:
    record = asdict(cam)
    for key in ("fx", "fy", "cx", "cy"):
        record[key] = round(float(record[key]), _HASH_DECIMALS)
    record["pose"] = [round(float(v), _HASH_DECIMALS) + 0.0 for v in cam.pose]
    return record


def reference_sha256(cameras: Iterable[CameraValues]) -> str:
    """sha256 of a camera set, independent of camera order and of float noise below 1e-9."""
    records = sorted((_canonical(c) for c in cameras), key=lambda r: str(r["uid"]))
    payload = json.dumps(records, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
