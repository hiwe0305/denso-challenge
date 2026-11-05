"""Defect kinds and their design codes (design 27/10/2026 sections 9.2 and 10, fixed 3/11/2026).

Several kinds share one code, so a `Defect` carries the code in `code` and the kind in
`parameters["kind"]`: DA-31 scores recall per kind and precision per code.
"""

from collections.abc import Mapping
from types import MappingProxyType

DATA_DEFECT_CODES: Mapping[str, str] = MappingProxyType(
    {
        "nan_values": "D1",
        "timestamp_sync_offset": "D2",
        "drop_frames": "D2",
        "joint_jump": "D3",
        "joint_limit_exceeded": "D3",
        "unit_deg_rad": "D3",
        "holdout_seed_leak": "D5",
        "duplicate_episode": "D5",
        "corrupted_success_label": "D6",
        "wrong_task_instruction": "D6",
        "action_sign_flip": "D7",
    }
)

LOG_DEFECT_CODES: Mapping[str, str] = MappingProxyType(
    {
        "T1_divergence": "T1",
        "T2_not_learning": "T2",
        "T3_overfitting": "T3",
        "T4_group_imbalance": "T4",
        "T5_dead_dimension": "T5",
        "T6_mode_collapse": "T6",
        "T7_forgetting": "T7",
        "T8_gradient_anomaly": "T8",
        "R1_high_latency": "R1",
        "R2_buffer_depleted": "R2",
    }
)
