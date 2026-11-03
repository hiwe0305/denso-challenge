"""Public interface of the defect injector for the other data stories (plan 3/11, session 2).

DA-03 `release` calls `has_injected_defect` to keep benchmark copies out of the release
train (plan Q5); each side has its own test.
"""

from flywheel.contracts.artifacts import Episode


def has_injected_defect(episode: Episode) -> bool:
    """True when the episode belongs to a defect-injected benchmark copy."""
    return episode.meta.injected_defect is not None
