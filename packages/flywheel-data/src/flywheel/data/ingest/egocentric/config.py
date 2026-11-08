"""`configs/data/egocentric.yaml`: the egocentric pipeline's pinned subset and thresholds.

Every key is required and an unknown key is an error, as in `qa.yaml` (spec 4.4): a
threshold the file does not name is not guessed here. The lane's own `config.py` is
DA-03's, so the egocentric settings load here. The de-identification waiver is not a
setting: it is a PO decision and lives in code (`annotate/deid/gate.py`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from flywheel.data.annotate.deid.blur import BlurParams
from flywheel.data.api import ConfigError

DEFAULT = Path("configs/data/egocentric.yaml")
Layout = Literal["pick_place", "two_table"]
DECISIONS = ("pass", "flag", "quarantine", "reject")
QA_CHECKS = ("min_frames", "video_frames", "pose_finite", "hand_pose_nan", "pose_low_confidence",
             "hand_out_of_frame", "camera_jitter_deg_s", "instruction", "segments",
             "segment_count", "segment_ambiguous", "deid_gate")


@dataclass(frozen=True)
class SourceConfig:
    license: str
    data_class: Literal["public", "internal", "restricted"]
    layout: Layout
    embodiment_id: str
    root: str | None = None
    split_dir: str | None = None
    episodes_per_task: int | None = None
    tasks: tuple[str, ...] = ()


@dataclass(frozen=True)
class SegmentConfig:
    smooth_frames: int
    still_speed_m_s: float
    min_dwell_frames: int
    min_path_m: float
    close_delta_m: float
    min_confidence: float
    min_gap_frames: int
    model_window_frames: int
    model_frames: int
    walk_speed_rel: float
    steps: dict[str, dict[str, str]]  # layout -> step_id -> sentence template


@dataclass(frozen=True)
class QARule:
    threshold: float
    on_fail: str
    below: float | None = None  # pose_low_confidence: a frame counts when below this
    when_missing: str | None = None
    code: str | None = None  # design 10 D-code, as robot QA's (qa.yaml), in the reason


@dataclass(frozen=True)
class ModelConfig:
    name: str  # the model as published
    served: str  # the name the endpoint serves it under
    revision: str  # commit of the weights that are served


@dataclass(frozen=True)
class DeidConfig:
    """`deid`: the face model, pinned by sha256, and how its boxes are covered."""

    model: ModelConfig
    path: str  # the model file, relative to the store root
    url: str
    sha256: str
    params: BlurParams


@dataclass(frozen=True)
class EgoConfig:
    version: str
    sha256: str
    sources: dict[str, SourceConfig]
    segment: SegmentConfig
    qa: dict[str, QARule]
    pose_ea: dict[str, Any]
    models: dict[str, ModelConfig]
    timeout_s: float
    max_image_side_px: int
    local_hosts: tuple[str, ...]
    review_share: float
    review_seed: int
    deid: DeidConfig

    @property
    def threshold_version(self) -> str:
        return f"{self.version}@{self.sha256[:12]}"


def load_config(path: Path = DEFAULT) -> EgoConfig:
    raw = path.read_bytes()
    data = _mapping(yaml.safe_load(raw), str(path))
    _keys(data, ("version", "sources", "segment", "qa", "pose_ea", "models", "review", "deid"),
          str(path))
    segment = _mapping(data["segment"], "segment")
    steps = _mapping(segment.pop("steps"), "segment.steps")
    qa = _mapping(data["qa"], "qa")
    _keys(qa, QA_CHECKS, "qa")
    models = _mapping(data["models"], "models")
    review = _mapping(data["review"], "review")
    _keys(review, ("sample_share", "seed"), "review")
    try:
        seg = SegmentConfig(**segment, steps={k: dict(v) for k, v in steps.items()})
        rules = {name: QARule(**_mapping(v, f"qa.{name}")) for name, v in qa.items()}
        sources = {name: SourceConfig(**{**_mapping(v, f"sources.{name}"),
                                         "tasks": tuple(v.get("tasks", ()))})
                   for name, v in _mapping(data["sources"], "sources").items()}
        roles = {k: ModelConfig(**_mapping(v, f"models.{k}")) for k, v in models.items()
                 if k not in ("timeout_s", "max_image_side_px", "local_hosts")}
        deid = _deid(_mapping(data["deid"], "deid"))
    except TypeError as error:
        raise ConfigError(f"{path}: {error}") from error
    for name, rule in rules.items():
        if rule.on_fail not in DECISIONS[1:]:
            raise ConfigError(f"qa.{name}.on_fail {rule.on_fail!r} is not flag/quarantine/reject")
    for name, source in sources.items():
        if source.layout not in seg.steps:
            raise ConfigError(f"sources.{name}.layout {source.layout!r} has no segment.steps")
    return EgoConfig(
        version=str(data["version"]),
        sha256=hashlib.sha256(raw).hexdigest(),
        sources=sources,
        segment=seg,
        qa=rules,
        pose_ea=dict(_mapping(data["pose_ea"], "pose_ea")),
        models=roles,
        timeout_s=float(models["timeout_s"]),
        max_image_side_px=int(models["max_image_side_px"]),
        local_hosts=_hosts(models.get("local_hosts", [])),
        review_share=float(review["sample_share"]),
        review_seed=int(review["seed"]),
        deid=deid,
    )


def _deid(data: dict[str, Any]) -> DeidConfig:
    model = _mapping(data.pop("model", None), "deid.model")
    _keys(model, ("name", "path", "url", "revision", "sha256"), "deid.model")
    return DeidConfig(
        model=ModelConfig(name=str(model["name"]), served="opencv.FaceDetectorYN",
                          revision=str(model["revision"])),
        path=str(model["path"]), url=str(model["url"]), sha256=str(model["sha256"]),
        params=BlurParams(**data),
    )


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{where} must be a mapping")
    return cast(dict[str, Any], dict(value))


def _hosts(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(h, str) and h for h in value):
        raise ConfigError("models.local_hosts must be a list of host names")
    return tuple(value)


def _keys(data: dict[str, Any], names: tuple[str, ...], where: str) -> None:
    missing = [n for n in names if n not in data]
    extra = [n for n in data if n not in names]
    if missing or extra:
        raise ConfigError(f"{where}: missing {missing}, unknown {extra}")
