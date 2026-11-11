"""Joint order, bones, the frame feature table and LeRobot v3.0 path templates.

Hands use the 21 keypoints of MediaPipe's hand model, which is also the 21-joint hand of
Human-1M: wrist, then four joints per finger from the base out. EgoDex (ARKit) has 25
joints a hand; its four metacarpals are not in the 21 and the forearm is dropped.
"""

from __future__ import annotations

from typing import Any

CODEBASE_VERSION = "v3.0"
CHUNK_SIZE = 1000
DATA_PATH = "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
VIDEO_PATH = "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"
EPISODES_PATH = "meta/episodes/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
CAMERA = "main"
VIDEO_KEY = f"observation.images.{CAMERA}"

FINGERS = ("thumb", "index", "middle", "ring", "little")
JOINTS = ("wrist",
          "thumb_cmc", "thumb_mcp", "thumb_ip", "thumb_tip",
          "index_mcp", "index_pip", "index_dip", "index_tip",
          "middle_mcp", "middle_pip", "middle_dip", "middle_tip",
          "ring_mcp", "ring_pip", "ring_dip", "ring_tip",
          "little_mcp", "little_pip", "little_dip", "little_tip")
TIPS = (4, 8, 12, 16, 20)
# (parent, child) of each bone; 20 bones from the wrist out
BONES = ((0, 1), (1, 2), (2, 3), (3, 4),
         (0, 5), (5, 6), (6, 7), (7, 8),
         (0, 9), (9, 10), (10, 11), (11, 12),
         (0, 13), (13, 14), (14, 15), (15, 16),
         (0, 17), (17, 18), (18, 19), (19, 20))

_ARKIT_FINGER = {"thumb": "Thumb", "index": "IndexFinger", "middle": "MiddleFinger",
                 "ring": "RingFinger", "little": "LittleFinger"}
_ARKIT_THUMB = ("Knuckle", "IntermediateBase", "IntermediateTip", "Tip")
_ARKIT_FINGER_PARTS = ("Knuckle", "IntermediateBase", "IntermediateTip", "Tip")


def arkit_joints(side: str) -> list[str]:
    """EgoDex transform names of the 21 joints of one hand, in `JOINTS` order. ARKit's
    thumb knuckle is the CMC joint; a finger's knuckle is its MCP."""
    names = [f"{side}Hand"]
    for finger in FINGERS:
        parts = _ARKIT_THUMB if finger == "thumb" else _ARKIT_FINGER_PARTS
        names += [f"{side}{_ARKIT_FINGER[finger]}{p}" for p in parts]
    return names


def _vec(n: int, names: list[str] | None = None) -> dict[str, Any]:
    return {"dtype": "float32", "shape": [n], "names": names}


def _xyz(side: str) -> list[str]:
    return [f"{side}_{j}_{a}" for j in JOINTS for a in "xyz"]


def _quat(side: str) -> list[str]:
    return [f"{side}_{j}_{a}" for j in JOINTS for a in ("qx", "qy", "qz", "qw")]


def _scalar(dtype: str) -> dict[str, Any]:
    return {"dtype": dtype, "shape": [1], "names": None}


HAND = {side: f"observation.state.hand_{side}_cam" for side in ("left", "right")}
HAND_ROT = {side: f"observation.state.hand_{side}_cam_rotation" for side in ("left", "right")}
CAM_POS = "observation.state.camera_position"
CAM_ROT = "observation.state.camera_rotation"
MASK = {side: f"{side}_hand_mask" for side in ("left", "right")}
CONF = {side: f"{side}_hand_confidence" for side in ("left", "right")}

# Per-frame columns of data/*.parquet, Human-1M names; the video feature is added by
# the writer with its codec and size.
FRAME_FEATURES: dict[str, dict[str, Any]] = {
    "index": _scalar("int64"),
    "episode_index": _scalar("int64"),
    "frame_index": _scalar("int64"),
    "timestamp": _scalar("float32"),
    "task_index": _scalar("int64"),
    "subtask_index": _scalar("int64"),
    HAND["left"]: _vec(63, _xyz("left")),
    HAND["right"]: _vec(63, _xyz("right")),
    HAND_ROT["left"]: _vec(84, _quat("left")),
    HAND_ROT["right"]: _vec(84, _quat("right")),
    CAM_POS: _vec(3, ["x", "y", "z"]),
    CAM_ROT: _vec(4, ["qx", "qy", "qz", "qw"]),
    "environment_index": _scalar("int64"),
    "scene_index": _scalar("int64"),
    "scene_id": _scalar("string"),
    "collector_id": _scalar("string"),
    MASK["left"]: _scalar("int64"),
    MASK["right"]: _scalar("int64"),
    CONF["left"]: _scalar("float32"),
    CONF["right"]: _scalar("float32"),
}
