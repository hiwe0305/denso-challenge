"""Psi0's stage 1 EgoDex loader at `cda3fdf`, re-written for CI without torch (DA-18 AC 2).

Mirrors, line for line where it matters, `src/psi/data/egodex/egodex_dataset.py`
(`_scan_directory`, `get_item` on the delta-action path, `convert_to_delta_actions`,
`d9_to_mat44`, `delta_rpy_from_tfs`, `points_to_camera`) and the `bounds_q99` branch of
`ActionStateTransform` in `src/psi/config/transform.py`. Two substitutions, both
checked against Psi0 by `test_loader_contract`: scipy's `as_euler('xyz')` is the closed
form below, and torchcodec's frame decode is OpenCV's (converted to RGB). It reuses
nothing from the export it checks.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import h5py  # type: ignore[import-untyped]
import numpy as np

TRAIN_PARTS = ("part1", "part2", "part3", "part4", "part5", "extra")
FINGERS = ("ThumbTip", "IndexFingerTip", "MiddleFingerTip", "RingFingerTip", "LittleFingerTip")


def scan(root: Path, val: bool = False) -> list[dict[str, Any]]:
    """`_load_file_list` without the pickle cache: hdf5 files that have their mp4."""
    files = []
    for part in ("test",) if val else TRAIN_PARTS:
        part_dir = root / part
        if not part_dir.exists():
            continue
        for task_dir in part_dir.iterdir():
            if task_dir.is_dir():
                for hdf5 in task_dir.glob("*.hdf5"):
                    mp4 = task_dir / f"{hdf5.stem}.mp4"
                    if mp4.exists():
                        files.append({"hdf5": hdf5, "mp4": mp4, "task": task_dir.name})
    return files


def d9_to_mat44(nine_d: np.ndarray) -> np.ndarray:
    col0 = nine_d[3:6] / (np.linalg.norm(nine_d[3:6]) + 1e-8)
    col1 = nine_d[6:9] - np.dot(nine_d[6:9], col0) * col0
    col1 = col1 / (np.linalg.norm(col1) + 1e-8)
    mat44 = np.eye(4, dtype=nine_d.dtype)
    mat44[:3, 0], mat44[:3, 1], mat44[:3, 2] = col0, col1, np.cross(col0, col1)
    mat44[:3, 3] = nine_d[:3]
    return mat44


def as_euler_xyz(m: np.ndarray) -> np.ndarray:
    m = m.astype(np.float64)
    return np.array(
        [
            np.arctan2(m[2, 1], m[2, 2]),
            np.arcsin(np.clip(-m[2, 0], -1, 1)),
            np.arctan2(m[1, 0], m[0, 0]),
        ]
    )


def delta_rpy_from_tfs(tfs: np.ndarray) -> np.ndarray:
    out = np.zeros((tfs.shape[0] - 1, 3), dtype=np.float32)
    for i in range(tfs.shape[0] - 1):
        out[i] = as_euler_xyz(tfs[i + 1][:3, :3] @ tfs[i][:3, :3].T)
    return out


def points_to_camera(points: np.ndarray, cam_ext: np.ndarray) -> np.ndarray:
    homogeneous = np.hstack([points, np.ones((points.shape[0], 1))])
    return (np.linalg.inv(cam_ext) @ homogeneous.T).T[:, :3]


def convert_to_delta_actions(
    actions: np.ndarray, chunk_size: int, cam_ext: np.ndarray
) -> np.ndarray:
    blocks = []
    for base in (0, 24):
        wrist = np.empty((chunk_size, 4, 4), dtype=np.float32)
        tips = {f: np.empty((chunk_size, 3), dtype=np.float32) for f in FINGERS}
        for i in range(actions.shape[0]):
            wrist[i] = d9_to_mat44(actions[i, base : base + 9])
            for k, f in enumerate(FINGERS):
                tips[f][i] = actions[i, base + 9 + 3 * k : base + 12 + 3 * k]
        in_cam = np.linalg.inv(cam_ext)[None] @ wrist
        rpy = delta_rpy_from_tfs(in_cam)
        blocks += [in_cam[1:, :3, 3] - in_cam[:-1, :3, 3], rpy, np.zeros_like(rpy)]
        for f in FINGERS:
            points = points_to_camera(tips[f], cam_ext)
            blocks.append(points[1:] - points[:-1])
    return np.concatenate(blocks, axis=1)


def parse_img_data(
    mp4: Path, idx: int, img_history_size: int = 1, upsample_rate: int = 3
) -> np.ndarray:
    """(history, H, W, 3) RGB frames as Psi0's `parse_img_data`.

    With one image and rate 3 that is the single frame `max(idx - 2, 0)`, not `idx`:
    `range(idx - 2, idx + 1, 3)`. The fake keeps that two-frame lag of Psi0.
    """
    import cv2

    start_i = max(idx - img_history_size * upsample_rate + 1, 0)
    wanted = list(range(start_i, idx + 1, upsample_rate))
    capture = cv2.VideoCapture(str(mp4))
    frames = []
    for k in range(idx + 1):
        ok, frame = capture.read()
        assert ok, f"{mp4} has no frame {k}"
        if k in wanted:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    capture.release()
    return np.array(frames)[-img_history_size:]


def get_item(
    file_info: dict[str, Any], chunk_size: int = 1, upsample_rate: int = 3
) -> dict[str, Any]:
    """`EgoDexDataset.get_item` with `use_delta_actions=True`, `img_history_size=1`."""
    with h5py.File(file_info["hdf5"], "r") as root:
        if root.attrs["llm_type"] == "reversible":
            key = (
                "llm_description"
                if root.attrs["which_llm_description"] == "1"
                else "llm_description2"
            )
        else:
            key = "llm_description"
        instruction = root.attrs[key]
        instruction = (
            instruction.decode("utf-8") if isinstance(instruction, bytes) else instruction
        ).strip()
        total_frames = list(root["transforms"].values())[0].shape[0]
        max_index = total_frames - 2
        index = random.randint(0, max_index)
        current_action = root["actions_48d"][:][[index]].astype(np.float32)
        window = chunk_size + 1
        action_end = min(index + window * upsample_rate, max_index + 1)
        action_indices = list(range(index, action_end, upsample_rate))
        while len(action_indices) < window:
            action_indices.append(action_indices[-1] if action_indices else index + 1)
        actions = root["actions_48d"][:][action_indices[:window]].astype(np.float32)
        cam_ext = np.array(root["/transforms/camera"][index])
        root["/camera/intrinsic"][:]
        actions = convert_to_delta_actions(actions, window, cam_ext)
    assert actions.shape[0] == chunk_size
    return {
        "states": current_action,
        "actions": actions,
        "current_images": [parse_img_data(file_info["mp4"], index)],
        "instruction": instruction,
        "task": file_info["task"],
        "file_info": {
            "total_frames": total_frames,
            "selected_index": index,
            "action_indices": action_indices,
        },
    }


def normalize_bounds_q99(actions: np.ndarray, stats_path: Path, key: str = "egodex") -> np.ndarray:
    """`ActionStateTransform.__call__` with `action_norm_type="bounds_q99"`."""
    stats = json.loads(stats_path.read_text())[key]
    action_min = np.array(stats["q01"], dtype=np.float32)
    action_max = np.array(stats["q99"], dtype=np.float32)
    ill = np.abs(action_max - action_min) < 1e-4 * (np.abs(action_max) + np.abs(action_min) + 1e-8)
    action_max[ill] = 1.0
    normalized = np.where(ill, actions, (actions - action_min) / (action_max - action_min) * 2 - 1)
    return np.clip(normalized, -1, 1).astype(np.float32)
