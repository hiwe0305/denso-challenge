"""Unit tests for train log and RTC log defect injection (AC 2)."""

import math

from flywheel.data.inject.log_defects import RTCLogDefectInjector, TrainLogDefectInjector


def test_train_clean_log_generation() -> None:
    injector = TrainLogDefectInjector()
    logs = injector.generate_clean_train_log(total_steps=10)
    assert len(logs) == 10
    assert logs[0]["train_loss"] > logs[-1]["train_loss"]
    assert logs[0]["frozen_vlm_grad"] == 0.0


def test_inject_t1_divergence() -> None:
    injector = TrainLogDefectInjector()
    logs = injector.generate_clean_train_log(total_steps=10)
    mod, defect = injector.inject_t1_divergence(logs)
    assert defect.code == "T1_divergence"
    # Contains NaN in loss
    assert any(math.isnan(entry["train_loss"]) for entry in mod)


def test_inject_t2_not_learning() -> None:
    injector = TrainLogDefectInjector()
    logs = injector.generate_clean_train_log(total_steps=10)
    mod, defect = injector.inject_t2_not_learning(logs)
    assert defect.code == "T2_not_learning"
    assert mod[-1]["val_loss"] >= mod[0]["val_loss"] - 0.05


def test_inject_t3_overfitting() -> None:
    injector = TrainLogDefectInjector()
    logs = injector.generate_clean_train_log(total_steps=10)
    mod, defect = injector.inject_t3_overfitting(logs)
    assert defect.code == "T3_overfitting"
    # Later val losses increase
    assert mod[-1]["val_loss"] > mod[-2]["val_loss"]


def test_inject_t4_group_imbalance() -> None:
    injector = TrainLogDefectInjector()
    logs = injector.generate_clean_train_log(total_steps=10)
    mod, defect = injector.inject_t4_group_imbalance(logs)
    assert defect.code == "T4_group_imbalance"
    assert mod[-1]["loss_groups"]["right_arm"] == 1.85


def test_inject_t5_dead_dimension() -> None:
    injector = TrainLogDefectInjector()
    logs = injector.generate_clean_train_log(total_steps=10)
    mod, defect = injector.inject_t5_dead_dimension(logs)
    assert defect.code == "T5_dead_dimension"
    assert mod[-1]["pred_variance"][12] == 0.0


def test_inject_t6_mode_collapse() -> None:
    injector = TrainLogDefectInjector()
    logs = injector.generate_clean_train_log(total_steps=10)
    mod, defect = injector.inject_t6_mode_collapse(logs)
    assert defect.code == "T6_mode_collapse"
    assert mod[-1]["pred_std"] < 1e-4


def test_inject_t7_forgetting() -> None:
    injector = TrainLogDefectInjector()
    logs = injector.generate_clean_train_log(total_steps=10)
    mod, defect = injector.inject_t7_forgetting(logs)
    assert defect.code == "T7_forgetting"
    assert mod[-1]["p4_score"] < logs[-1]["p4_score"]


def test_inject_t8_gradient_anomaly() -> None:
    injector = TrainLogDefectInjector()
    logs = injector.generate_clean_train_log(total_steps=10)
    mod, defect = injector.inject_t8_gradient_anomaly(logs)
    assert defect.code == "T8_gradient_anomaly"
    assert mod[-1]["frozen_vlm_grad"] == 2.5


def test_rtc_clean_log_generation() -> None:
    injector = RTCLogDefectInjector()
    logs = injector.generate_clean_rtc_log(total_chunks=10)
    assert len(logs) == 10
    assert logs[0]["delay_steps"] == 1
    assert logs[0]["buffer_level"] == 4


def test_inject_r1_high_latency() -> None:
    injector = RTCLogDefectInjector()
    logs = injector.generate_clean_rtc_log(total_chunks=10)
    mod, defect = injector.inject_r1_high_latency(logs)
    assert defect.code == "R1_high_latency"
    assert mod[-1]["latency_ms"] == 120.0
    assert mod[-1]["delay_steps"] == 5


def test_inject_r2_buffer_depleted() -> None:
    injector = RTCLogDefectInjector()
    logs = injector.generate_clean_rtc_log(total_chunks=10)
    mod, defect = injector.inject_r2_buffer_depleted(logs)
    assert defect.code == "R2_buffer_depleted"
    assert mod[-1]["buffer_level"] == 0
