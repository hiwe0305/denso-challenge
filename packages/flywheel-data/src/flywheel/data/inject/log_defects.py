"""Synthetic train log and RTC inference log defect injection (Design 27/10/2026 section 10).

Covers F-TRAIN (T1-T8) and F-SYS RTC (R1, R2).
"""

import copy
import random
from typing import Any

from flywheel.contracts.artifacts import Defect
from flywheel.data.inject.config import RTCDefectConfig, TrainDefectConfig


class TrainLogDefectInjector:
    """Injects T1-T8 defects into training metrics log entries."""

    def __init__(self, config: TrainDefectConfig | None = None, rng_seed: int = 42):
        self.config = config or TrainDefectConfig()
        self.rng = random.Random(rng_seed)

    def generate_clean_train_log(self, total_steps: int = 20) -> list[dict[str, Any]]:
        records = []
        train_loss = 2.0
        val_loss = 2.2
        for step in range(1, total_steps + 1):
            train_loss *= 0.92
            val_loss *= 0.93
            records.append(
                {
                    "step": step,
                    "train_loss": round(train_loss, 4),
                    "val_loss": round(val_loss, 4),
                    "loss_groups": {
                        "left_arm": round(train_loss * 0.4, 4),
                        "right_arm": round(train_loss * 0.4, 4),
                        "legs": round(train_loss * 0.2, 4),
                    },
                    "pred_variance": [0.05 + 0.01 * (step % 5) for _ in range(36)],
                    "pred_std": 0.22,
                    "grad_norm": 0.85,
                    "frozen_vlm_grad": 0.0,
                    "p4_score": round(0.5 + 0.02 * step, 3),
                }
            )
        return records

    def inject_t1_divergence(
        self, logs: list[dict[str, Any]], target_job: str = "job_train_t1"
    ) -> tuple[list[dict[str, Any]], Defect]:
        new_logs = copy.deepcopy(logs)
        mid = len(new_logs) // 2
        for i in range(mid, len(new_logs)):
            mult = self.config.t1_loss_multiplier
            val = float("nan") if i == mid + 2 else new_logs[i]["train_loss"] * mult
            new_logs[i]["train_loss"] = val
        defect = Defect(
            target_ref=target_job,
            code="T1_divergence",
            parameters={"step_started": mid, "multiplier": self.config.t1_loss_multiplier},
        )
        return new_logs, defect

    def inject_t2_not_learning(
        self, logs: list[dict[str, Any]], target_job: str = "job_train_t2"
    ) -> tuple[list[dict[str, Any]], Defect]:
        new_logs = copy.deepcopy(logs)
        initial_val = new_logs[0]["val_loss"]
        for entry in new_logs:
            entry["val_loss"] = initial_val - (entry["step"] * self.config.t2_decay_rate)
        defect = Defect(
            target_ref=target_job,
            code="T2_not_learning",
            parameters={"decay_rate": self.config.t2_decay_rate},
        )
        return new_logs, defect

    def inject_t3_overfitting(
        self, logs: list[dict[str, Any]], target_job: str = "job_train_t3"
    ) -> tuple[list[dict[str, Any]], Defect]:
        new_logs = copy.deepcopy(logs)
        start = max(1, len(new_logs) - self.config.t3_val_loss_steps)
        for i in range(start, len(new_logs)):
            new_logs[i]["train_loss"] *= 0.85
            new_logs[i]["val_loss"] = new_logs[i - 1]["val_loss"] * 1.15
        defect = Defect(
            target_ref=target_job,
            code="T3_overfitting",
            parameters={"consecutive_val_increases": self.config.t3_val_loss_steps},
        )
        return new_logs, defect

    def inject_t4_group_imbalance(
        self, logs: list[dict[str, Any]], target_job: str = "job_train_t4"
    ) -> tuple[list[dict[str, Any]], Defect]:
        new_logs = copy.deepcopy(logs)
        grp = self.config.t4_frozen_group
        for entry in new_logs:
            entry["loss_groups"][grp] = 1.85  # constant flat high loss
        defect = Defect(
            target_ref=target_job,
            code="T4_group_imbalance",
            parameters={"stuck_group": grp},
        )
        return new_logs, defect

    def inject_t5_dead_dimension(
        self, logs: list[dict[str, Any]], target_job: str = "job_train_t5"
    ) -> tuple[list[dict[str, Any]], Defect]:
        new_logs = copy.deepcopy(logs)
        dim = self.config.t5_dead_dim
        for entry in new_logs:
            entry["pred_variance"][dim] = 0.0
        defect = Defect(
            target_ref=target_job,
            code="T5_dead_dimension",
            parameters={"dead_dimension": dim},
        )
        return new_logs, defect

    def inject_t6_mode_collapse(
        self, logs: list[dict[str, Any]], target_job: str = "job_train_t6"
    ) -> tuple[list[dict[str, Any]], Defect]:
        new_logs = copy.deepcopy(logs)
        thresh = self.config.t6_std_threshold
        for entry in new_logs:
            entry["pred_std"] = thresh * 0.1
        defect = Defect(
            target_ref=target_job,
            code="T6_mode_collapse",
            parameters={"std_value": thresh * 0.1},
        )
        return new_logs, defect

    def inject_t7_forgetting(
        self, logs: list[dict[str, Any]], target_job: str = "job_train_t7"
    ) -> tuple[list[dict[str, Any]], Defect]:
        new_logs = copy.deepcopy(logs)
        drop = self.config.t7_drop_ratio
        for entry in new_logs[len(new_logs) // 2 :]:
            entry["p4_score"] = round(entry["p4_score"] * (1.0 - drop), 3)
        defect = Defect(
            target_ref=target_job,
            code="T7_forgetting",
            parameters={"score_drop_ratio": drop},
        )
        return new_logs, defect

    def inject_t8_gradient_anomaly(
        self, logs: list[dict[str, Any]], target_job: str = "job_train_t8"
    ) -> tuple[list[dict[str, Any]], Defect]:
        new_logs = copy.deepcopy(logs)
        norm = self.config.t8_frozen_grad_norm
        for entry in new_logs:
            entry["frozen_vlm_grad"] = norm
        defect = Defect(
            target_ref=target_job,
            code="T8_gradient_anomaly",
            parameters={"frozen_vlm_grad": norm},
        )
        return new_logs, defect


class RTCLogDefectInjector:
    """Injects R1, R2 defects into real-time inference log entries."""

    def __init__(self, config: RTCDefectConfig | None = None):
        self.config = config or RTCDefectConfig()

    def generate_clean_rtc_log(self, total_chunks: int = 20) -> list[dict[str, Any]]:
        records = []
        for i in range(total_chunks):
            sent = i * 0.05
            recv = sent + 0.025
            records.append(
                {
                    "job_id": "job_rtc_001",
                    "trace_id": "trace_clean",
                    "chunk_index": i,
                    "observation_sent_s": sent,
                    "chunk_received_s": recv,
                    "latency_ms": 25.0,
                    "delay_steps": 1,
                    "buffer_level": 4,
                    "boundary_jump": 0.01,
                }
            )
        return records

    def inject_r1_high_latency(
        self, logs: list[dict[str, Any]], target_job: str = "job_rtc_r1"
    ) -> tuple[list[dict[str, Any]], Defect]:
        new_logs = copy.deepcopy(logs)
        lat = self.config.r1_p99_latency_ms
        for entry in new_logs[len(new_logs) // 2 :]:
            entry["latency_ms"] = lat
            entry["chunk_received_s"] = entry["observation_sent_s"] + (lat / 1000.0)
            entry["delay_steps"] = 5
        defect = Defect(
            target_ref=target_job,
            code="R1_high_latency",
            parameters={"p99_latency_ms": lat},
        )
        return new_logs, defect

    def inject_r2_buffer_depleted(
        self, logs: list[dict[str, Any]], target_job: str = "job_rtc_r2"
    ) -> tuple[list[dict[str, Any]], Defect]:
        new_logs = copy.deepcopy(logs)
        depleted = self.config.r2_depleted_steps
        for entry in new_logs[-depleted:]:
            entry["buffer_level"] = 0
        defect = Defect(
            target_ref=target_job,
            code="R2_buffer_depleted",
            parameters={"depleted_steps": depleted},
        )
        return new_logs, defect
