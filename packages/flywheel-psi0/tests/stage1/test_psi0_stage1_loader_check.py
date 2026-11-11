"""DA-30: the loader check's summary of how much of the actions Psi0 clips."""

from __future__ import annotations

from flywheel_psi0.stage1.loader_check import PAD_DIMS, action_clip_summary


def row(value: float, pads: float = 0.0) -> list[float]:
    return [pads if d in PAD_DIMS else value for d in range(48)]


def test_values_on_the_clip_are_counted_per_value_and_per_sample() -> None:
    edge = row(0.1)
    edge[0], edge[47] = 1.0, -1.0
    summary = action_clip_summary([edge, row(0.1), row(-1.0)])
    assert summary["samples"] == 3
    assert summary["clipped_value_share"] == round((2 + 42) / (3 * 42), 3)
    assert summary["samples_with_a_clipped_dim"] == round(2 / 3, 3)


def test_pad_dims_are_left_out() -> None:
    # Pads hold raw zeros in Psi0's output; a value there must not count either way.
    assert action_clip_summary([row(0.5, pads=1.0)])["clipped_value_share"] == 0.0


def test_no_rows_gives_no_shares() -> None:
    assert action_clip_summary([]) == {
        "samples": 0,
        "clipped_value_share": None,
        "samples_with_a_clipped_dim": None,
    }
