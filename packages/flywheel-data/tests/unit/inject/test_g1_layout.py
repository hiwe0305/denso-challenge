"""The injector on the real G1 action layout of configs/embodiments/g1.yaml (DA-01).

If g1.yaml changes (dims, limits, masks), this test breaks instead of the benchmark
going silently wrong.
"""

import random
import statistics
from pathlib import Path

import pytest
import yaml
from flywheel.contracts.artifacts import ActionLayout, DefectManifest
from flywheel.data.inject.applied import defect_applied
from flywheel.data.inject.data_defects import ANGLE_ACTION_DIMS, JOINT_ACTION_DIMS, EpisodeData
from flywheel.data.inject.dataset import create_defect_dataset

REPO = Path(__file__).resolve().parents[5]
G1_YAML = REPO / "configs/embodiments/g1.yaml"


@pytest.fixture(scope="module")
def layout() -> ActionLayout:
    raw = yaml.safe_load(G1_YAML.read_text(encoding="utf-8"))
    return ActionLayout.model_validate(raw["action_layout"])


def _episodes(layout: ActionLayout, n: int = 99, steps: int = 20) -> list[EpisodeData]:
    """36-D episodes shaped like psi-data: hands at zero, arms and waist inside their limits."""
    rng = random.Random(0)
    dims = layout.dimensions

    def centre(d: int) -> float:
        low, high = dims[d].limit_low, dims[d].limit_high
        assert low is not None and high is not None
        return (low + high) / 2

    episodes = []
    for i in range(n):
        actions = [
            [0.0] * 14
            + [centre(d) + 0.05 * rng.uniform(-1, 1) for d in range(14, 31)]
            + [0.75, 0.1 * rng.random(), 0.0, 0.0, 0.3 * rng.random()]
            for _ in range(steps)
        ]
        stamps = [t * 0.02 for t in range(steps)]
        episodes.append(
            EpisodeData(
                episode_id=f"ep_{i:03d}",
                timestamps_state=stamps,
                timestamps_image=list(stamps),
                states=[[0.0] * 32 for _ in range(steps)],
                actions=actions,
                images=[f"f{t}.jpg" for t in range(steps)],
                seed=1000 + i,
            )
        )
    return episodes


@pytest.fixture(scope="module")
def run(
    layout: ActionLayout,
) -> tuple[list[EpisodeData], list[EpisodeData], DefectManifest]:
    episodes = _episodes(layout)
    injected, manifest = create_defect_dataset(episodes, layout=layout)
    return episodes, injected, manifest


def _entries(manifest: DefectManifest, kind: str) -> list:
    entries = [d for d in manifest.defects if d.parameters["kind"] == kind]
    assert len(entries) == 3, kind
    return entries


def test_g1_layout_has_the_36_dims_the_injector_assumes(layout: ActionLayout) -> None:
    assert len(layout.dimensions) == 36
    assert all(layout.dimensions[d].limit_high is not None for d in JOINT_ACTION_DIMS)


def test_every_manifest_entry_is_applied(
    run: tuple[list[EpisodeData], list[EpisodeData], DefectManifest],
) -> None:
    episodes, injected, manifest = run
    before = {ep.episode_id: ep for ep in episodes}
    after = {ep.episode_id: ep for ep in injected}
    assert len(manifest.defects) == 33
    for d in manifest.defects:
        source = before.get(str(d.parameters.get("original_id", "")))
        assert defect_applied(before[d.target_ref], after[d.target_ref], d, source), d


def test_joint_limit_picks_a_joint_and_lands_above_its_limit(
    layout: ActionLayout, run: tuple[list[EpisodeData], list[EpisodeData], DefectManifest]
) -> None:
    _, injected, manifest = run
    after = {ep.episode_id: ep for ep in injected}
    for d in _entries(manifest, "joint_limit_exceeded"):
        dim = int(d.parameters["dimension"])
        high = layout.dimensions[dim].limit_high
        assert dim in JOINT_ACTION_DIMS
        assert d.parameters["limit_high"] == high
        assert high is not None
        assert all(a[dim] > high for a in after[d.target_ref].actions)


def test_unit_and_sign_defects_touch_only_the_dims_design_allows(
    run: tuple[list[EpisodeData], list[EpisodeData], DefectManifest],
) -> None:
    episodes, injected, manifest = run
    before = {ep.episode_id: ep for ep in episodes}
    after = {ep.episode_id: ep for ep in injected}
    for kind in ("unit_deg_rad", "action_sign_flip"):
        for d in _entries(manifest, kind):
            old, new = before[d.target_ref].actions, after[d.target_ref].actions
            changed = {dim for dim in range(36) if [a[dim] for a in old] != [a[dim] for a in new]}
            dim = int(d.parameters["dimension"])
            assert changed == {dim}, (kind, changed)
            if kind == "unit_deg_rad":
                # Design 9.2: only angle dims (0-30, 35).
                assert dim in ANGLE_ACTION_DIMS
            else:
                # Design 9.2: a dim whose std is not zero on the episode.
                assert statistics.pstdev(a[dim] for a in old) > 0
