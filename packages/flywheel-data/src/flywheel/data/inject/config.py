"""Configuration for defect injection, loaded from configs/data/inject.yaml."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DataDefectConfig:
    drop_frames_rate: float = 0.15
    timestamp_offset_seconds: float = 0.08
    joint_jump_magnitude: float = 1.5
    joint_limit_excess_factor: float = 1.25
    nan_ratio: float = 0.05
    unit_deg_rad_scale: float = 57.2957795
    action_sign_flip_dims: tuple[int, ...] = (0, 6)
    corrupted_prompt: str = "move to random location and stop"
    holdout_seed_range: tuple[int, int] = (9000, 9999)


@dataclass(frozen=True)
class TrainDefectConfig:
    t1_loss_multiplier: float = 15.0
    t2_decay_rate: float = 0.001
    t3_val_loss_steps: int = 5
    t4_frozen_group: str = "right_arm"
    t5_dead_dim: int = 12
    t6_std_threshold: float = 1e-4
    t7_drop_ratio: float = 0.40
    t8_frozen_grad_norm: float = 2.5


@dataclass(frozen=True)
class RTCDefectConfig:
    r1_p99_latency_ms: float = 120.0
    r2_depleted_steps: int = 10


@dataclass(frozen=True)
class InjectConfig:
    version: str = "1.0.0"
    seed: int = 42
    episodes_per_kind: int = 3
    data: DataDefectConfig = field(default_factory=DataDefectConfig)
    train: TrainDefectConfig = field(default_factory=TrainDefectConfig)
    rtc: RTCDefectConfig = field(default_factory=RTCDefectConfig)

    @classmethod
    def default_path(cls) -> Path:
        return Path(__file__).resolve().parents[5] / "configs" / "data" / "inject.yaml"


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse hierarchical yaml subset without external dependencies."""
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for line in text.splitlines():
        stripped = line.split("#", 1)[0].rstrip()
        if not stripped:
            continue
        indent = len(stripped) - len(stripped.lstrip())
        content = stripped.strip()

        while stack and stack[-1][0] >= indent:
            stack.pop()

        current_dict = stack[-1][1]

        if ":" in content:
            key, val = content.split(":", 1)
            key = key.strip()
            val = val.strip()

            if not val:
                new_dict: dict[str, Any] = {}
                current_dict[key] = new_dict
                stack.append((indent, new_dict))
            else:
                current_dict[key] = _parse_val(val)

    return root


def _parse_val(v: str) -> Any:
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.startswith("[") and v.endswith("]"):
        items = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        return [_parse_val(x) for x in items]
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    try:
        if "." in v or "e" in v.lower():
            return float(v)
        return int(v)
    except ValueError:
        return v


def load_inject_config(path: Path | None = None) -> InjectConfig:
    target_path = path or InjectConfig.default_path()
    if not target_path.exists():
        return InjectConfig()

    data = parse_simple_yaml(target_path.read_text(encoding="utf-8"))
    dd_data = data.get("data_defects", {})
    tr_data = data.get("train_defects", {})
    rtc_data = data.get("rtc_defects", {})

    data_cfg = DataDefectConfig(
        drop_frames_rate=float(dd_data.get("drop_frames", {}).get("drop_rate", 0.15)),
        timestamp_offset_seconds=float(
            dd_data.get("timestamp_sync_offset", {}).get("offset_seconds", 0.08)
        ),
        joint_jump_magnitude=float(dd_data.get("joint_jump", {}).get("jump_magnitude", 1.5)),
        joint_limit_excess_factor=float(
            dd_data.get("joint_limit_exceeded", {}).get("excess_factor", 1.25)
        ),
        nan_ratio=float(dd_data.get("nan_values", {}).get("nan_ratio", 0.05)),
        unit_deg_rad_scale=float(dd_data.get("unit_deg_rad", {}).get("scale", 57.2957795)),
        action_sign_flip_dims=tuple(
            int(x) for x in dd_data.get("action_sign_flip", {}).get("dimensions", [0, 6])
        ),
        corrupted_prompt=str(
            dd_data.get("wrong_task_instruction", {}).get(
                "corrupted_prompt", "move to random location and stop"
            )
        ),
        holdout_seed_range=tuple(
            int(x)
            for x in dd_data.get("holdout_seed_leak", {}).get("holdout_seed_range", [9000, 9999])
        ),  # type: ignore[arg-type]
    )

    train_cfg = TrainDefectConfig(
        t1_loss_multiplier=float(tr_data.get("T1_divergence", {}).get("loss_multiplier", 15.0)),
        t2_decay_rate=float(tr_data.get("T2_not_learning", {}).get("decay_rate", 0.001)),
        t3_val_loss_steps=int(tr_data.get("T3_overfitting", {}).get("val_loss_increase_steps", 5)),
        t4_frozen_group=str(tr_data.get("T4_group_imbalance", {}).get("frozen_group", "right_arm")),
        t5_dead_dim=int(tr_data.get("T5_dead_dim", {}).get("dim", 12)),
        t6_std_threshold=float(tr_data.get("T6_mode_collapse", {}).get("std_threshold", 1e-4)),
        t7_drop_ratio=float(tr_data.get("T7_forgetting", {}).get("drop_ratio", 0.40)),
        t8_frozen_grad_norm=float(
            tr_data.get("T8_gradient_anomaly", {}).get("frozen_grad_norm", 2.5)
        ),
    )

    rtc_cfg = RTCDefectConfig(
        r1_p99_latency_ms=float(rtc_data.get("R1_high_latency", {}).get("p99_latency_ms", 120.0)),
        r2_depleted_steps=int(rtc_data.get("R2_buffer_depleted", {}).get("depleted_steps", 10)),
    )

    return InjectConfig(
        version=str(data.get("version", "1.0.0")),
        seed=int(data.get("seed", 42)),
        episodes_per_kind=int(data.get("episodes_per_kind", 3)),
        data=data_cfg,
        train=train_cfg,
        rtc=rtc_cfg,
    )
