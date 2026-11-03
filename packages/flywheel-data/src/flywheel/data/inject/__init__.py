"""Defect injection package for generating benchmark datasets with known faults.

Implements Story DA-27 (Design 27/10/2026 sections 9.2 and 10).
"""

from flywheel.data.inject.config import DataDefectConfig, InjectConfig, load_inject_config
from flywheel.data.inject.data_defects import DataDefectInjector, EpisodeData
from flywheel.data.inject.dataset import (
    create_clean_dataset,
    create_defect_dataset,
    verify_release_barrier,
)
from flywheel.data.inject.log_defects import RTCLogDefectInjector, TrainLogDefectInjector
from flywheel.data.inject.manifest import (
    ManifestLock,
    load_manifest,
    manifest_sha256,
    seal_manifest,
)

__all__ = [
    "DataDefectInjector",
    "DataDefectConfig",
    "EpisodeData",
    "InjectConfig",
    "ManifestLock",
    "RTCLogDefectInjector",
    "TrainLogDefectInjector",
    "create_clean_dataset",
    "create_defect_dataset",
    "load_inject_config",
    "load_manifest",
    "manifest_sha256",
    "seal_manifest",
    "verify_release_barrier",
]
