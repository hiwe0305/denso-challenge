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
    corrupted_prompt: str = "move to random location and stop"
    # Inclusive holdout seeds of configs/splits/default.yaml ([2000000, 2001000)).
    holdout_seed_range: tuple[int, int] = (2_000_000, 2_000_999)
    # Inclusive train seeds of the split plan ([0, 1000000)), for scaffold condition seeds.
    scaffold_seed_range: tuple[int, int] = (0, 999_999)
    success_label_keep_fraction: float = 0.5


@dataclass(frozen=True)
class LogDefectConfig:
    """Log defects, each set past its threshold in configs/eval/diagnosis/*.yaml."""

    jobs_per_kind: int = 3
    extra_clean_train_jobs: int = 6
    extra_clean_rtc_jobs: int = 4
    steps: int = 3000
    train_every: int = 50
    val_every: int = 250
    t2_val_drop: float = 0.01  # under t2.min_relative_drop 0.05
    t3_val_rises: int = 5  # over t3.m_measurements 3
    t5_window_steps: int = 1000  # t5.window_steps; the dead dim covers twice that
    t6_std_ratio: float = 0.1  # under t6.min_std_ratio 0.30
    t7_p1_drop: float = 0.25  # over t7.max_relative_drop 0.10
    t8_frozen_grad: float = 0.5  # over t8.frozen_tolerance 0
    rtc_chunks: int = 200
    control_hz: float = 50.0
    r1_latency_s: float = 0.155  # over r1.tau_lat_s 0.15; ceil(0.155 * 50) = 8, not over r2
    r1_fraction: float = 0.05  # enough chunks to lift the 99th percentile
    r2_latency_s: float = 0.24  # one chunk, delay 12 over r2.max_delay_steps 8


@dataclass(frozen=True)
class InjectConfig:
    version: str = "1.0.0"
    seed: int = 42
    episodes_per_kind: int = 3
    data: DataDefectConfig = field(default_factory=DataDefectConfig)
    logs: LogDefectConfig = field(default_factory=LogDefectConfig)

    @classmethod
    def default_path(cls) -> Path:
        return Path(__file__).resolve().parents[6] / "configs" / "data" / "inject.yaml"


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
        corrupted_prompt=str(
            dd_data.get("wrong_task_instruction", {}).get(
                "corrupted_prompt", "move to random location and stop"
            )
        ),
        success_label_keep_fraction=float(
            dd_data.get("corrupted_success_label", {}).get("keep_fraction", 0.5)
        ),
        holdout_seed_range=tuple(
            int(x)
            for x in dd_data.get("holdout_seed_leak", {}).get(
                "holdout_seed_range", [2_000_000, 2_000_999]
            )
        ),  # type: ignore[arg-type]
    )

    return InjectConfig(
        version=str(data.get("version", "1.0.0")),
        seed=int(data.get("seed", 42)),
        episodes_per_kind=int(data.get("episodes_per_kind", 3)),
        data=data_cfg,
        logs=LogDefectConfig(
            jobs_per_kind=int(data.get("log_defects", {}).get("jobs_per_kind", 3)),
        ),
    )
