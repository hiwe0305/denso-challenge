"""Dataset construction and release barrier verification (AC 4, AC 5)."""

import copy
import random
from collections.abc import Sequence

from flywheel.contracts.artifacts import Defect, DefectManifest
from flywheel.contracts.v0 import DatasetRef
from flywheel.data.inject.codes import DATA_DEFECT_CODES
from flywheel.data.inject.config import InjectConfig
from flywheel.data.inject.data_defects import DataDefectInjector, EpisodeData
from flywheel.data.inject.manifest import manifest_sha256


def create_defect_dataset(
    episodes: Sequence[EpisodeData],
    dataset_id: str = "ds_psi_data_injected",
    config: InjectConfig | None = None,
) -> tuple[list[EpisodeData], DefectManifest]:
    """Create a defective benchmark dataset by injecting faults into an episode copy.

    Each data defect kind goes into exactly `episodes_per_kind` distinct episodes
    (PO decision 3/11/2026: 3 per kind, 33 of 99). Never modifies original episodes.
    """
    cfg = config or InjectConfig()
    rng = random.Random(cfg.seed)
    injector = DataDefectInjector(cfg.data, rng_seed=cfg.seed)

    cloned_episodes = [copy.deepcopy(ep) for ep in episodes]
    total = len(cloned_episodes)
    kinds = list(DATA_DEFECT_CODES)
    needed = len(kinds) * cfg.episodes_per_kind
    # One defect per episode (the contract holds a single injected_defect), plus at least
    # one untouched episode to serve as the source of the duplicates.
    if total <= needed:
        raise ValueError(
            f"Injecting {cfg.episodes_per_kind} episodes per kind needs more than "
            f"{needed} episodes, got {total}"
        )

    selected_indices = rng.sample(range(total), needed)
    untouched = sorted(set(range(total)) - set(selected_indices))
    defects: list[Defect] = []

    for i, idx in enumerate(selected_indices):
        kind = kinds[i // cfg.episodes_per_kind]
        if kind == "duplicate_episode":
            # The slot becomes a copy of an untouched episode, so the set keeps its size
            # and the original stays unmarked; only the copy counts as injected.
            source = cloned_episodes[rng.choice(untouched)]
            modified_ep, defect = injector.inject_duplicate_episode(
                source, dup_id=cloned_episodes[idx].episode_id
            )
        else:
            modified_ep, defect = getattr(injector, f"inject_{kind}")(cloned_episodes[idx])
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
