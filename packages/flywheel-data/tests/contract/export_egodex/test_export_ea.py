"""DA-18 AC 3: the team's own video (E-A, `pseudo`) in the same stage 1 format as EgoDex.

E-A episodes have no EgoDex HDF5: the export builds the transforms from `pose.npz`
(wrists as recorded, tips with an identity rotation) and takes the camera matrix from
its `intrinsic`. The fake loader of AC 2 reads both sources the same way. Egocentric
data of either source is stage 1 only (design 27/10/2026 7.8), which the last tests
pin on the two stage 3 paths of the lane.
"""

from __future__ import annotations

import json
from pathlib import Path

import h5py  # type: ignore[import-untyped]
import numpy as np
import pytest
from egodex_workdir import INTRINSIC, Spec, build, episode_record
from fake_loader import get_item, scan
from flywheel.contracts.artifacts import Episode, QAReport
from flywheel.data.api import ReleaseRefused, build_release, load_layout
from flywheel.data.export.checklist import check_lerobot_v21
from flywheel.data.export.egodex import META_FILE, TIPS, ExportRefused, export_stage1
from loader_batch import compare
from test_loader_contract import PSI0_ROOT, fake_batch, psi0_batch

ROOT = Path(__file__).resolve().parents[5]
SPLITS = ROOT / "configs/splits/default.yaml"
G1 = ROOT / "configs/embodiments/g1.yaml"
EA = [
    Spec("ea_1", 30, [(0, 14), (14, 30)], pose_source="E-A", deid_status="blurred"),
    Spec("ea_2", 12, [(3, 12)], pose_source="E-A", deid_status="verified", decision="flag"),
]


def export(work: Path, out: Path, **kwargs: object) -> dict:  # type: ignore[type-arg]
    export_stage1(work, out, store=out.parent / "store", **kwargs)  # type: ignore[arg-type]
    return json.loads((out / META_FILE).read_text())


def test_e_a_is_exported_from_pose_npz_in_the_same_format(tmp_path: Path) -> None:
    work = build(tmp_path / "work", EA)
    meta = export(work, tmp_path / "out", include_flag=True)
    assert meta["source"]["source_detail"] == "ego_video"
    assert meta["source"]["deid_waiver"] is None
    assert meta["counts"]["by_pose_source"] == {"E-A": 3}
    assert {s["action_quality"] for s in meta["samples"]} == {"pseudo"}
    sample = meta["samples"][1]  # ea_1 frames [14, 30)
    with (
        np.load(work / "egocentric/ea_1/pose.npz") as pose,
        h5py.File(tmp_path / "out" / sample["hdf5"], "r") as f,
    ):
        np.testing.assert_array_equal(f["transforms/leftHand"][:], pose["left_wrist"][14:30])
        np.testing.assert_array_equal(f["transforms/camera"][:], pose["camera"][14:30])
        for k, tip in enumerate(TIPS):
            tips = f[f"transforms/right{tip}"][:]
            np.testing.assert_array_equal(tips[:, :3, 3], pose["right_tips"][14:30, k])
            np.testing.assert_array_equal(tips[:, :3, :3], np.tile(np.eye(3), (16, 1, 1)))
        np.testing.assert_array_equal(f["camera/intrinsic"][:], INTRINSIC)
        actions = f["actions_48d"][:]
        np.testing.assert_array_equal(actions[:, 24:27], pose["right_wrist"][14:30, :3, 3])
        np.testing.assert_array_equal(actions[:, 45:48], pose["right_tips"][14:30, 4])
        assert f.attrs["pose_source"] == "E-A" and f.attrs["action_quality"] == "pseudo"
        assert sample["pose_confidence"]["right"]["mean"] == pytest.approx(
            float(pose["confidence_right"][14:30].mean()), abs=1e-6
        )


def test_the_fake_loader_reads_e_a_like_e_b(tmp_path: Path) -> None:
    out = tmp_path / "out"
    export(build(tmp_path / "work", EA), out)
    files = scan(out)
    assert len(files) == 2
    for info in files:
        item = get_item(info)
        assert item["actions"].shape == (1, 48) and np.isfinite(item["actions"]).all()
        assert item["current_images"][0].shape == (1, 64, 96, 3)


def test_raw_e_a_video_is_refused(tmp_path: Path) -> None:
    work = build(tmp_path / "work", [Spec("ea_1", 10, [(0, 10)], pose_source="E-A")])
    with pytest.raises(ExportRefused, match="deid_status raw"):
        export(work, tmp_path / "out")


def test_e_a_without_an_intrinsic_is_refused(tmp_path: Path) -> None:
    work = build(tmp_path / "work", EA[:1], intrinsic=False)
    with pytest.raises(ExportRefused, match="no 'intrinsic'"):
        export(work, tmp_path / "out")


def test_e_a_must_be_pseudo_without_an_hdf5(tmp_path: Path) -> None:
    spec = Spec("ea_1", 10, [(0, 10)], pose_source="E-A", deid_status="blurred")
    work = build(tmp_path / "work", [spec])
    bundle = work / "egocentric/ea_1/bundle.json"
    raw = json.loads(bundle.read_text()) | {"action_quality": "retargeted"}
    bundle.write_text(json.dumps(raw))
    with pytest.raises(ExportRefused, match="E-A needs action_quality pseudo and no EgoDex hdf5"):
        export(work, tmp_path / "out")


def nan_frames(work: Path, episode_id: str, key: str, frames: list[int]) -> None:
    """NaN in `key` of pose.npz at `frames`, as DA-04's `to_pose` writes an unseen hand."""
    path = work / "egocentric" / episode_id / "pose.npz"
    with np.load(path) as npz:
        pose = {k: npz[k] for k in npz.files}
    pose[key][frames] = np.nan
    np.savez(path, **pose)


def test_a_segment_with_a_nan_frame_is_dropped_whole_and_listed(tmp_path: Path) -> None:
    work = build(tmp_path / "work", EA)
    nan_frames(work, "ea_1", "left_wrist", [3, 4, 5])  # in step_0, frames [0, 14)
    nan_frames(work, "ea_1", "right_tips", [13])
    meta = export(work, tmp_path / "out", include_flag=True)
    assert [(s["episode_id"], s["step_id"], s["hdf5"]) for s in meta["samples"]] == [
        ("ea_1", "step_1", "part1/pick_place_cup/0.hdf5"),
        ("ea_2", "step_0", "part1/pick_place_cup/1.hdf5"),  # flag: DA-04 flags NaN episodes
    ]
    assert meta["skipped"] == [
        {
            "episode_id": "ea_1",
            "step_id": "step_0",
            "frame_start": 0,
            "frame_end": 14,
            "reason": "not finite: left hand in 3 of 14 frames, right hand in 1 of 14 frames",
        }
    ]
    assert len(scan(tmp_path / "out")) == 2


def test_an_e_a_run_with_no_finite_segment_is_refused(tmp_path: Path) -> None:
    work = build(tmp_path / "work", EA[:1])
    nan_frames(work, "ea_1", "right_tips", [0, 20])
    with pytest.raises(ExportRefused, match=r"no segment to export \(2 skipped: 2 not finite\)"):
        export(work, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_e_a_and_e_b_in_one_run_are_refused(tmp_path: Path) -> None:
    specs = [
        Spec("eb_1", 10, [(0, 10)], deid_status="blurred"),
        Spec("ea_1", 10, [(0, 10)], pose_source="E-A", deid_status="blurred"),
    ]
    with pytest.raises(
        ExportRefused, match="one pose source, this work dir has E-A: ea_1; E-B: eb_1"
    ):
        export(build(tmp_path / "work", specs), tmp_path / "out")


@pytest.mark.skipif(PSI0_ROOT is None, reason="PSI0_ROOT not set: Psi0's own loader not run")
def test_psi0s_loader_and_the_fake_agree_on_e_a(tmp_path: Path) -> None:
    out = tmp_path / "out"
    export(build(tmp_path / "work", EA, seed=3), out, include_flag=True)
    assert compare(psi0_batch(out, tmp_path), fake_batch(out)) == []


# --- stage 3 refuses egocentric data --------------------------------------------------


def test_the_lerobot_v21_checklist_cannot_read_an_export(tmp_path: Path) -> None:
    out = tmp_path / "out"
    export(build(tmp_path / "work", EA[:1]), out)
    with pytest.raises(FileNotFoundError, match="info.json"):
        check_lerobot_v21(out, load_layout(G1))


@pytest.mark.xfail(
    strict=True,
    reason=(
        "build_release (DA-03, release/build.py) freezes an all-egocentric release as kind "
        "robot on 6/11/2026; DA-18 proposes that it refuse egocentric episodes or mark the "
        "release kind egocentric, which stage 3 then refuses"
    ),
)
@pytest.mark.parametrize("source", ["E-B", "E-A"])
def test_an_egocentric_episode_never_lands_in_a_robot_release(tmp_path: Path, source: str) -> None:
    spec = Spec("ep_1", 10, [(0, 10)], pose_source=source, deid_status="verified")
    episode = Episode.model_validate(episode_record(spec, "src_1"))
    report = QAReport(
        report_id="qa_1",
        episode_id="ep_1",
        threshold_version="egocentric-1",
        decision="pass",
        reasons=[],
        checks=[],
    )
    try:
        build_release([episode], [report], SPLITS, tmp_path / "rel")
    except ReleaseRefused:
        return
    assert json.loads((tmp_path / "rel/release.json").read_text())["kind"] != "robot"
