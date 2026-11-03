"""Public interface of the defect injector for the other data stories (plan 3/11, session 2).

DA-03 `release` calls `has_injected_defect` to keep benchmark copies out of the release
train (plan Q5); each side has its own test.
"""

from flywheel.contracts.artifacts import Episode


def has_injected_defect(episode: Episode) -> bool:
    """True when the episode belongs to a benchmark copy, defective or clean.

    Every episode of a copy carries `benchmark_copy_id` (design 6.1, 9.2; issue #62), so
    clean episodes of a copy stay out of the release train too.
    """
    return episode.meta.benchmark_copy_id is not None
