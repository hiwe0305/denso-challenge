"""Dataset construction and release barrier verification (AC 4, AC 5)."""

import copy
import random
from collections.abc import Sequence

from flywheel.contracts.artifacts import Defect, DefectManifest
from flywheel.contracts.v0 import DatasetRef
from flywheel.data.inject.config import InjectConfig
from flywheel.data.inject.data_defects import DataDefectInjector, EpisodeData
from flywheel.data.inject.manifest import manifest_sha256


def create_defect_dataset(
    episodes: Sequence[EpisodeData],
    dataset_id: str = "ds_psi_data_injected",
    config: InjectConfig | None = None,
) -> tuple[list[EpisodeData], DefectManifest]:
    """Create a defective benchmark dataset by injecting faults into an episode copy.

    Never modifies original episodes.
    """
    cfg = config or InjectConfig()
    rng = random.Random(cfg.seed)
    injector = DataDefectInjector(cfg.data, rng_seed=cfg.seed)

    cloned_episodes = [copy.deepcopy(ep) for ep in episodes]
    total = len(cloned_episodes)
    num_to_inject = max(1, int(total * cfg.injection_rate))

    # All 11 data defect injection methods
    inject_methods = [
        injector.inject_drop_frames,
        injector.inject_timestamp_sync_offset,
        injector.inject_joint_jump,
        injector.inject_joint_limit_exceeded,
        injector.inject_nan_values,
        injector.inject_unit_deg_rad,
        injector.inject_action_sign_flip,
        injector.inject_corrupted_success_label,
        injector.inject_wrong_task_instruction,
        injector.inject_duplicate_episode,
        injector.inject_holdout_seed_leak,
    ]

    selected_indices = rng.sample(range(total), min(num_to_inject, total))
    defects: list[Defect] = []

    for i, idx in enumerate(selected_indices):
        method = inject_methods[i % len(inject_methods)]
        modified_ep, defect = method(cloned_episodes[idx])
        cloned_episodes[idx] = modified_ep
        defects.append(defect)

    manifest = DefectManifest(
        dataset_id=dataset_id,
        seed=cfg.seed,
        defects=defects,
    )

    return cloned_episodes, manifest


def create_clean_dataset(
    episodes: Sequence[EpisodeData],
    dataset_id: str = "ds_psi_data_clean",
) -> list[EpisodeData]:
    """Create a paired pristine clean dataset of identical size for false positive baseline."""
    clean = [copy.deepcopy(ep) for ep in episodes]
    for ep in clean:
        ep.meta = ep.meta.model_copy(update={"injected_defect": None})
    return clean


def verify_release_barrier(episodes: Sequence[EpisodeData]) -> list[EpisodeData]:
    """Enforce barrier: reject any episode with an injected defect from the release train.

    Raises ValueError if an injected defect is present in the release candidate set.
    """
    clean_episodes: list[EpisodeData] = []
    poisoned_ids: list[str] = []

    for ep in episodes:
        if ep.meta.injected_defect is not None:
            poisoned_ids.append(ep.episode_id)
        else:
            clean_episodes.append(ep)

    if poisoned_ids:
        raise ValueError(
            f"Release train barrier violation: {len(poisoned_ids)} defect-injected episodes "
            f"attempted to enter release: {poisoned_ids[:5]}"
        )

    return clean_episodes


def get_dataset_refs(
    dataset_id: str,
    manifest: DefectManifest,
) -> tuple[DatasetRef, str]:
    """Package dataset reference and manifest hash for DA-31 evaluation handoff."""
    ref = DatasetRef(
        dataset_id=dataset_id,
        uri=f"fwdata/benchmark/{dataset_id}",
    )
    return ref, manifest_sha256(manifest)
