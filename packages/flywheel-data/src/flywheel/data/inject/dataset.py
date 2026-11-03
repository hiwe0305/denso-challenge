"""Dataset construction and release barrier verification (AC 4, AC 5)."""

import copy
import random
from collections.abc import Sequence

from flywheel.contracts.artifacts import ActionLayout, Defect, DefectManifest
from flywheel.contracts.v0 import DatasetRef
from flywheel.data.inject.applied import content, defect_applied
from flywheel.data.inject.codes import DATA_DEFECT_CODES
from flywheel.data.inject.config import InjectConfig
from flywheel.data.inject.data_defects import DataDefectInjector, EpisodeData, NotApplicable
from flywheel.data.inject.manifest import manifest_sha256

_REVEALING_WORDS = ("clean", "defect", "inject", "pristine", "dirty")


def copy_ids(seed: int, namespace: str = "data") -> tuple[str, str]:
    """Neutral ids of the defect copy and the clean copy, in that order.

    Both share one format so the agent under test cannot tell the copies apart; which id
    holds defects is recorded only in the DefectManifest that the scorer reads. The log
    copies use namespace "logs", so their ids differ from the data copies'.
    """
    key = f"benchmark-copy-ids:{seed}" if namespace == "data" else f"copy-ids:{namespace}:{seed}"
    rng = random.Random(key)
    first, second = (f"bench-{rng.getrandbits(48):012x}" for _ in range(2))
    return first, second


def _neutral(dataset_id: str) -> str:
    if any(word in dataset_id.lower() for word in _REVEALING_WORDS):
        raise ValueError(f"dataset_id {dataset_id!r} reveals which benchmark copy it is")
    return dataset_id


def create_defect_dataset(
    episodes: Sequence[EpisodeData],
    dataset_id: str | None = None,
    config: InjectConfig | None = None,
    layout: ActionLayout | None = None,
) -> tuple[list[EpisodeData], DefectManifest]:
    """Create a defective benchmark dataset by injecting faults into an episode copy.

    Each data defect kind goes into exactly `episodes_per_kind` distinct episodes
    (PO decision 3/11/2026: 3 per kind, 33 of 99). Never modifies original episodes.
    `dataset_id` defaults to the first of `copy_ids(seed)`. With `layout`, action defects
    skip masked dims and joint limits come from the layout.
    """
    cfg = config or InjectConfig()
    dataset_id = _neutral(dataset_id or copy_ids(cfg.seed)[0])
    rng = random.Random(cfg.seed)
    injector = DataDefectInjector(cfg.data, rng_seed=cfg.seed, layout=layout)

    cloned_episodes = [copy.deepcopy(ep) for ep in episodes]
    total = len(cloned_episodes)
    per_kind = cfg.episodes_per_kind
    needed = len(DATA_DEFECT_CODES) * per_kind
    # One defect per episode (PO decision 3/11/2026), plus at least one untouched episode
    # to serve as the source of the duplicates.
    if total <= needed:
        raise ValueError(
            f"Injecting {per_kind} episodes per kind needs more than {needed} episodes, got {total}"
        )

    # Duplicates go last: their sources are reserved, so no later defect changes them.
    kinds = [k for k in DATA_DEFECT_CODES if k != "duplicate_episode"] + ["duplicate_episode"]
    order = list(range(total))
    rng.shuffle(order)
    taken: set[int] = set()
    defects: list[Defect] = []

    for kind in kinds:
        placed = 0
        for idx in order:
            if placed == per_kind:
                break
            if idx in taken:
                continue
            before = cloned_episodes[idx]
            source: EpisodeData | None = None
            try:
                if kind == "duplicate_episode":
                    # The slot becomes a copy of an untouched episode, so the set keeps its
                    # size and the original stays unmarked; only the copy counts as injected.
                    free = [
                        i
                        for i in order
                        if i not in taken and content(cloned_episodes[i]) != content(before)
                    ]
                    if not free:
                        raise NotApplicable("duplicate_episode: no untouched source left")
                    src_idx = rng.choice(free)
                    taken.add(src_idx)
                    source = cloned_episodes[src_idx]
                    after, defect = injector.inject_duplicate_episode(
                        source, dup_id=before.episode_id
                    )
                else:
                    after, defect = getattr(injector, f"inject_{kind}")(before)
            except NotApplicable:
                continue
            if not defect_applied(before, after, defect, source):
                raise RuntimeError(f"{kind} listed for {before.episode_id} but not applied")
            cloned_episodes[idx] = after
            taken.add(idx)
            defects.append(defect)
            placed += 1
        if placed < per_kind:
            raise ValueError(f"Only {placed} of {total} episodes can take {kind}; need {per_kind}")

    _mark_benchmark_copy(cloned_episodes, dataset_id)
    manifest = DefectManifest(
        dataset_id=dataset_id,
        seed=cfg.seed,
        defects=defects,
    )

    return cloned_episodes, manifest


def _mark_benchmark_copy(episodes: list[EpisodeData], dataset_id: str) -> None:
    """Mark every episode of a benchmark copy, defective or not (design 6.1, 9.2)."""
    for ep in episodes:
        ep.meta = ep.meta.model_copy(update={"benchmark_copy_id": dataset_id})


def create_clean_dataset(
    episodes: Sequence[EpisodeData],
    dataset_id: str | None = None,
    config: InjectConfig | None = None,
) -> tuple[list[EpisodeData], DefectManifest]:
    """Create a paired pristine clean dataset of identical size for false positive baseline.

    Pass the original episodes. The empty DefectManifest is what marks this copy as the
    clean one for the scorer; `dataset_id` defaults to the second of `copy_ids(seed)`.
    """
    cfg = config or InjectConfig()
    dataset_id = _neutral(dataset_id or copy_ids(cfg.seed)[1])
    clean = [copy.deepcopy(ep) for ep in episodes]
    _mark_benchmark_copy(clean, dataset_id)
    return clean, DefectManifest(dataset_id=dataset_id, seed=cfg.seed, defects=[])


def verify_release_barrier(episodes: Sequence[EpisodeData]) -> list[EpisodeData]:
    """Enforce barrier: reject every episode of a benchmark copy from the release train.

    Raises ValueError if any episode carries `benchmark_copy_id`, defective or clean.
    """
    clean_episodes: list[EpisodeData] = []
    poisoned_ids: list[str] = []

    for ep in episodes:
        if ep.meta.benchmark_copy_id is not None:
            poisoned_ids.append(ep.episode_id)
        else:
            clean_episodes.append(ep)

    if poisoned_ids:
        raise ValueError(
            f"Release train barrier violation: {len(poisoned_ids)} benchmark copy episodes "
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
