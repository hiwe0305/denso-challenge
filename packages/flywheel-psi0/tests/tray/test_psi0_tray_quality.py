"""Episode quality of tray demos and the quality filter of the demo sets, on CPU (DA-34)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from flywheel_psi0.tray.demo_sets import ReleaseEpisode, apply_quality, nested_sets, rank
from flywheel_psi0.tray.quality import EpisodeQuality, QualityFilter, episode_quality

T = 100
LIMITS = QualityFilter(max_tilt_carry_deg=10, max_part_shift_end_mm=20)


def _quat(roll: float = 0.0, yaw: float = 0.0) -> list[float]:
    """wxyz of a yaw then roll rotation (enough for these tests)."""
    cy, sy, cr, sr = math.cos(yaw / 2), math.sin(yaw / 2), math.cos(roll / 2), math.sin(roll / 2)
    return [cy * cr, cy * sr, sy * sr, sy * cr]


def _episode(
    tilt_deg: np.ndarray | None = None, yaw: np.ndarray | None = None, slide: float = 0.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tilt = np.zeros(T) if tilt_deg is None else tilt_deg
    yaws = np.zeros(T) if yaw is None else yaw
    pose = np.array(
        [
            [0.1 * t / T, 0.0, 0.8, *_quat(math.radians(a), y)]
            for t, a, y in zip(range(T), tilt, yaws)
        ]
    )
    parts = np.zeros((T, 6, 3))
    for t in range(T):
        c, s = math.cos(yaws[t]), math.sin(yaws[t])
        local = np.array([[0.05 * k, 0.02, 0.01] for k in range(6)])
        local[0, 0] += slide * t / (T - 1)  # part 0 slides along the tray x axis
        parts[t] = pose[t, :3] + local @ np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
    steps = np.zeros((T, 7))
    steps[20:, :3] = 1  # lift reached at frame 20
    steps[80:, 3:6] = 1  # place reached at frame 80
    return pose, parts.reshape(T, 18), steps


def test_flat_still_episode_is_clean() -> None:
    q = episode_quality(1, *_episode())
    assert q.tilt_carry_max_deg == pytest.approx(0, abs=1e-6)
    assert q.part_shift_end_mm == pytest.approx(0, abs=1e-6)
    assert LIMITS.passes(q)


def test_tilt_counts_only_while_carried() -> None:
    tilt = np.zeros(T)
    tilt[:20] = 14  # before lift: ignored
    tilt[85:] = 14  # after place: ignored
    tilt[50] = 7
    q = episode_quality(1, *_episode(tilt_deg=tilt))
    assert q.tilt_carry_max_deg == pytest.approx(7, abs=1e-3)
    tilt[60] = 12
    assert not LIMITS.passes(episode_quality(1, *_episode(tilt_deg=tilt)))


def test_part_shift_is_in_the_tray_frame() -> None:
    # The tray turns 90 deg with the parts riding along: no shift.
    turned = episode_quality(1, *_episode(yaw=np.linspace(0, math.pi / 2, T)))
    assert turned.part_shift_end_mm == pytest.approx(0, abs=1e-6)
    slid = episode_quality(1, *_episode(yaw=np.linspace(0, math.pi / 2, T), slide=0.025))
    assert slid.part_shift_end_mm == pytest.approx(25, abs=1e-3)
    assert not LIMITS.passes(slid)


def _row(seed: int, tilt: float = 5.0, shift: float = 5.0) -> EpisodeQuality:
    return EpisodeQuality(
        seed=seed,
        frames=T,
        tilt_carry_max_deg=tilt,
        part_shift_end_mm=shift,
        part_shift_max_mm=shift,
        drop_vz_min=-0.4,
    )


def test_filter_drops_rough_episodes_and_keeps_the_ranking(tmp_path: Path) -> None:
    episodes = [ReleaseEpisode(episode_index=i, seed=2000 + i) for i in range(60)]
    rough = {2003: (12.0, 5.0), 2010: (5.0, 25.0), 2042: (11.0, 30.0)}
    rows = [_row(e.seed, *rough.get(e.seed, (5.0, 5.0))) for e in episodes]
    path = tmp_path / "quality.jsonl"
    path.write_text("".join(r.model_dump_json() + "\n" for r in rows))

    kept, pin = apply_quality(episodes, path, LIMITS)
    assert (pin.kept, pin.dropped) == (57, 3)
    assert not {e.seed for e in kept} & set(rough)
    sets = nested_sets("r", "a" * 64, kept, {"A": 40, "C": 20}, quality=pin).sets
    assert set(sets["C"].seeds) < set(sets["A"].seeds)
    # The filter removes episodes from the ranking; the rest keep their order.
    full = [s for s in rank("a" * 64, episodes) if s not in rough]
    assert sets["A"].seeds == sorted(full[:40])


def test_filter_needs_a_row_for_every_episode(tmp_path: Path) -> None:
    path = tmp_path / "quality.jsonl"
    path.write_text(_row(1).model_dump_json() + "\n")
    with pytest.raises(ValueError, match="no row for seeds"):
        apply_quality([ReleaseEpisode(episode_index=0, seed=2)], path, LIMITS)
