"""DA-18 AC 1: QA'd egocentric segments in Psi0's stage 1 EgoDex layout, with stats.

The input is a synthetic DA-04 work dir (`egodex_workdir`, plan 4.2a) whose numbers
are known, so each test checks the export against them.
"""

from __future__ import annotations

import json
from pathlib import Path

import h5py  # type: ignore[import-untyped]
import numpy as np
import pytest
from egodex_workdir import INTRINSIC, PIN, Spec, build, grey, write_pin, write_video
from fake_loader import scan
from flywheel.data.export.egodex import (
    CAMERA,
    JOINTS,
    META_FILE,
    STATS_FILE,
    ExportRefused,
    actions_48d,
    delta_actions,
    euler_xyz,
    export_stage1,
    main,
    sha256,
    stage1_stats,
)

SPECS = [
    Spec("ep_a", 40, [(0, 20), (20, 40)]),
    Spec("ep_b", 30, [(5, 29)], decision="flag"),
    Spec("ep_c", 25, [(0, 25)], decision=None),
    Spec("ep_d", 33, [(0, 33)], split="test"),
    Spec("ep_e", 21, [(0, 20), (20, 21)], decision="reject"),
]


@pytest.fixture(scope="module")
def work(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build(tmp_path_factory.mktemp("work"), SPECS)


def export(work: Path, out: Path, **kwargs: object) -> dict:  # type: ignore[type-arg]
    kwargs.setdefault("waiver_pin", work / PIN)
    export_stage1(work, out, store=out.parent / "store", **kwargs)  # type: ignore[arg-type]
    return json.loads((out / META_FILE).read_text())


def video_frames(path: Path) -> list[float]:
    import cv2

    capture = cv2.VideoCapture(str(path))
    means = []
    while True:
        ok, frame = capture.read()
        if not ok:
            return means
        means.append(float(frame.mean()))


# --- the numbers ----------------------------------------------------------------------


def test_actions_48d_follows_the_h_rdt_layout() -> None:
    rng = np.random.default_rng(1)
    transforms = {name: rng.standard_normal((3, 4, 4)).astype(np.float32) for name in JOINTS}
    actions = actions_48d(transforms)
    assert actions.shape == (3, 48) and actions.dtype == np.float32
    for base, side in ((0, "left"), (24, "right")):
        wrist = transforms[f"{side}Hand"]
        np.testing.assert_array_equal(actions[:, base : base + 3], wrist[:, :3, 3])
        np.testing.assert_array_equal(actions[:, base + 3 : base + 6], wrist[:, :3, 0])
        np.testing.assert_array_equal(actions[:, base + 6 : base + 9], wrist[:, :3, 1])
        np.testing.assert_array_equal(
            actions[:, base + 21 : base + 24], transforms[f"{side}LittleFingerTip"][:, :3, 3]
        )
        np.testing.assert_array_equal(
            actions[:, base + 9 : base + 12], transforms[f"{side}ThumbTip"][:, :3, 3]
        )


def test_euler_xyz_is_scipys_as_euler_xyz() -> None:
    rotation = pytest.importorskip("scipy.spatial.transform").Rotation
    matrices = rotation.random(200, random_state=3).as_matrix()
    np.testing.assert_allclose(
        euler_xyz(matrices), rotation.from_matrix(matrices).as_euler("xyz"), atol=1e-9
    )


def test_delta_actions_are_in_the_camera_frame_of_the_first_row() -> None:
    # camera turned 90 degrees about z: a world +x step of the wrist is a camera -y step
    camera = np.eye(4, dtype=np.float32)
    camera[:3, :3] = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
    camera[:3, 3] = [5, 5, 5]
    actions = np.zeros((2, 48), np.float32)
    actions[:, 3] = actions[:, 7] = actions[:, 27] = actions[:, 31] = 1  # identity rotations
    actions[1, 0] = 0.1  # left wrist x
    angle = 0.2
    actions[1, 27:33] = [np.cos(angle), np.sin(angle), 0, -np.sin(angle), np.cos(angle), 0]
    actions[1, 33] = 0.3  # right thumb tip x
    delta = delta_actions(actions, camera)
    assert delta.shape == (1, 48)
    np.testing.assert_allclose(delta[0, :3], [0, -0.1, 0], atol=1e-6)
    np.testing.assert_allclose(delta[0, 27:30], [0, 0, angle], atol=1e-6)  # yaw in camera
    np.testing.assert_allclose(delta[0, 33:36], [0, -0.3, 0], atol=1e-6)
    assert not delta[:, 6:9].any() and not delta[:, 30:33].any()


def test_stats_follow_calc_stat() -> None:
    rng = np.random.default_rng(2)
    files = []
    for frames in (10, 7, 2):  # the last has one row at rate 3: no delta, left out
        actions = rng.standard_normal((frames, 48)).astype(np.float32)
        actions[:, 3:9] = actions[:, 27:33] = [1, 0, 0, 0, 1, 0]
        files.append((actions, np.tile(np.eye(4, dtype=np.float32), (frames, 1, 1))))
    stats = stage1_stats(files, 3)["egodex"]
    every = np.concatenate([delta_actions(a[::3], c[0]) for a, c in files[:2]])
    assert every.shape == (3 + 2, 48)
    np.testing.assert_allclose(stats["min"], every.min(0))
    np.testing.assert_allclose(stats["q99"], np.quantile(every, 0.99, axis=0))
    np.testing.assert_allclose(stats["std"], every.std(0), atol=1e-7)
    assert set(stats) == {"min", "max", "q01", "q99", "mean", "std"}
    assert all(len(v) == 48 for v in stats.values())
    with pytest.raises(ValueError):
        stage1_stats(files[2:], 3)


# --- the files ------------------------------------------------------------------------


def test_each_qa_pass_segment_is_one_pair_in_the_loader_layout(work: Path, tmp_path: Path) -> None:
    meta = export(work, tmp_path / "out")
    names = sorted(str(p.relative_to(tmp_path / "out")) for p in (tmp_path / "out").rglob("*.*"))
    assert names == [
        STATS_FILE,
        META_FILE,
        "part1/pick_place_cup/0.hdf5",
        "part1/pick_place_cup/0.mp4",
        "part1/pick_place_cup/1.hdf5",
        "part1/pick_place_cup/1.mp4",
        "test/pick_place_cup/0.hdf5",
        "test/pick_place_cup/0.mp4",
    ]
    assert [(s["episode_id"], s["frame_start"], s["frame_end"]) for s in meta["samples"]] == [
        ("ep_a", 0, 20),
        ("ep_a", 20, 40),
        ("ep_d", 0, 33),
    ]
    assert {s["episode_id"]: s["reason"] for s in meta["skipped"]} == {
        "ep_b": "QA flag",
        "ep_c": "no QAReport",
        "ep_e": "QA reject",
    }
    assert not list((tmp_path / "out").rglob("filelist_cache.pkl"))
    assert not (tmp_path / "out" / "meta" / "info.json").exists()  # not a LeRobot dataset


def test_flag_is_exported_only_when_asked(work: Path, tmp_path: Path) -> None:
    meta = export(work, tmp_path / "out", include_flag=True)
    assert meta["include"] == ["pass", "flag"]
    assert ("ep_b", 5, 29, "flag") in [
        (s["episode_id"], s["frame_start"], s["frame_end"], s["qa_decision"])
        for s in meta["samples"]
    ]


def test_hdf5_has_what_the_loader_reads(work: Path, tmp_path: Path) -> None:
    meta = export(work, tmp_path / "out")
    sample = meta["samples"][1]  # ep_a frames [20, 40)
    source = work / "raw/pick_place_cup/0.hdf5"
    with h5py.File(tmp_path / "out" / sample["hdf5"], "r") as f, h5py.File(source, "r") as raw:
        assert sorted(f["transforms"]) == sorted((*JOINTS, CAMERA))
        for name in (*JOINTS, CAMERA):
            np.testing.assert_array_equal(
                f[f"transforms/{name}"][:], raw[f"transforms/{name}"][20:40]
            )
        assert f["actions_48d"].shape == (20, 48) and f["actions_48d"].dtype == np.float32
        assert f["actions_48d"].compression == "gzip"
        np.testing.assert_array_equal(
            f["actions_48d"][:], actions_48d({n: raw[f"transforms/{n}"][20:40] for n in JOINTS})
        )
        np.testing.assert_array_equal(f["camera/intrinsic"][:], INTRINSIC)
        assert f.attrs["llm_type"] != "reversible"
        assert f.attrs["llm_description"] == sample["description"] == "Place the cup ep_a"
        assert f.attrs["source_episode_id"] == "ep_a" and f.attrs["frame_start"] == 20


def test_mp4_is_the_same_frames_as_the_hdf5(work: Path, tmp_path: Path) -> None:
    import cv2

    meta = export(work, tmp_path / "out")
    for sample in meta["samples"]:
        bundle = json.loads((work / f"egocentric/{sample['episode_id']}/bundle.json").read_text())
        mp4 = tmp_path / "out" / sample["mp4"]
        capture = cv2.VideoCapture(str(mp4))
        # mp4v reads back as FFmpeg's MPEG-4 part 2 tag, as EgoDex's own videos do
        assert cv2.VideoWriter.fourcc(*"FMP4") == int(capture.get(cv2.CAP_PROP_FOURCC))
        assert capture.get(cv2.CAP_PROP_FPS) == 30
        capture.release()
        means = video_frames(mp4)
        assert len(means) == sample["frames"]
        # Frame k of a source is grey(k), 7 levels from its neighbours. Each mp4v
        # generation darkens every frame by about the same few levels, so the cut's
        # offset from its source frames is flat, and an off-by-one cut would be ~7 off.
        source = video_frames(Path(bundle["mp4"]))
        assert np.ptp(np.subtract(source, [grey(k) for k in range(len(source))])) < 2
        offset = np.subtract(means, source[sample["frame_start"] : sample["frame_end"]])
        assert np.ptp(offset) < 2 and abs(offset.mean()) < 3.5


def test_meta_records_source_quality_confidence_and_every_sha256(
    work: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    meta = export(work, out, release_id="rel_0123456789abcdef")
    assert meta["release_id"] == "rel_0123456789abcdef"
    assert meta["source"]["source_detail"] == "egodex" and meta["source"]["deid_waiver"]
    assert meta["recipe"]["chunk_size"] == 1 and meta["recipe"]["upsample_rate"] == 3
    assert meta["recipe"]["action_norm_type"] == "bounds_q99"
    assert meta["stage3"].startswith("refused")
    sample = meta["samples"][0]
    assert sample["action_quality"] == "retargeted" and sample["pose_source"] == "E-B"
    with np.load(work / "egocentric/ep_a/pose.npz") as pose:
        assert sample["pose_confidence"]["left"]["min"] == pytest.approx(
            float(pose["confidence_left"][0:20].min()), abs=1e-6
        )
    on_disk = {str(p.relative_to(out)): sha256(p) for p in out.rglob("*.*") if p.name != META_FILE}
    assert meta["files"] == on_disk
    assert sample["sha256"] == {"hdf5": on_disk[sample["hdf5"]], "mp4": on_disk[sample["mp4"]]}


def test_stats_file_is_calc_stat_over_the_exported_files(work: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    meta = export(work, out)
    files = []
    for sample in meta["samples"]:
        with h5py.File(out / sample["hdf5"], "r") as f:
            files.append((f["actions_48d"][:], f["transforms/camera"][:]))
    shipped = json.loads((out / STATS_FILE).read_text())
    assert shipped == json.loads(json.dumps(stage1_stats(files, 3)))
    assert meta["stats"]["files"] == 3


def test_the_same_work_dir_gives_the_same_bytes(work: Path, tmp_path: Path) -> None:
    first, second = export(work, tmp_path / "a"), export(work, tmp_path / "b")
    assert first["files"] == second["files"]
    assert first["export_id"] == second["export_id"]


def test_every_run_writes_an_estimate_and_a_measurement(work: Path, tmp_path: Path) -> None:
    meta = export(work, tmp_path / "out")
    [ledger] = (tmp_path / "store").rglob("ledger.jsonl")
    estimate, measured = (json.loads(line) for line in ledger.read_text().splitlines())
    assert estimate["activity"] == measured["activity"] == "export"
    assert estimate["measure_kind"] == "estimated" and "assumption" in estimate["note"]
    assert measured["measure_kind"] == "measured"
    assert measured["estimate_entry_id"] == estimate["id"]
    assert estimate["run_plan_id"].startswith("g0-DA-18-")
    assert meta["export_id"] in measured["note"]


# --- what is refused ------------------------------------------------------------------


def test_an_export_is_never_written_over(work: Path, tmp_path: Path) -> None:
    export(work, tmp_path / "out")
    with pytest.raises(ExportRefused, match="not empty"):
        export(work, tmp_path / "out")


def test_raw_video_without_the_egodex_waiver_is_refused(tmp_path: Path) -> None:
    work = build(tmp_path / "work", [Spec("ep_a", 10, [(0, 10)])], waiver=False)
    with pytest.raises(ExportRefused, match="EgoDex waiver"):
        export(work, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_a_deidentified_episode_needs_no_waiver(tmp_path: Path) -> None:
    work = build(
        tmp_path / "work", [Spec("ep_a", 10, [(0, 10)], deid_status="blurred")], waiver=False
    )
    assert len(export(work, tmp_path / "out")["samples"]) == 1


def test_robot_episodes_holdout_and_bad_ranges_are_refused(tmp_path: Path) -> None:
    specs = [
        Spec("ep_robot", 10, [(0, 10)], episode={"source_kind": "teleop"}),
        Spec("ep_vault", 10, [(0, 10)], split="holdout"),
        Spec("ep_long", 10, [(0, 11)]),
        Spec("ep_short", 10, [(0, 1), (1, 10)]),
    ]
    with pytest.raises(ExportRefused) as refused:
        export(build(tmp_path / "work", specs), tmp_path / "out")
    problems = "\n".join(refused.value.problems)
    assert "ep_robot: source_kind teleop" in problems
    assert "ep_vault: split 'holdout'" in problems
    assert "ep_long step_0 [0, 11): outside" in problems
    assert "ep_short" not in problems  # a one-frame segment is skipped, not refused


def test_a_one_frame_segment_is_skipped(tmp_path: Path) -> None:
    meta = export(build(tmp_path / "work", [Spec("ep_a", 10, [(0, 1), (1, 10)])]), tmp_path / "out")
    assert [s["frame_start"] for s in meta["samples"]] == [1]
    assert "under 2 frames" in meta["skipped"][0]["reason"]


def test_a_bundle_that_contradicts_its_episode_is_refused(tmp_path: Path) -> None:
    spec = Spec("ep_a", 10, [(0, 10)], episode={"action_quality": "pseudo"})
    with pytest.raises(ExportRefused, match="bundle retargeted, Episode pseudo"):
        export(build(tmp_path / "work", [spec]), tmp_path / "out")


def test_frames_without_a_recorded_confidence_are_reported_not_averaged(tmp_path: Path) -> None:
    # EgoDex files without a `confidences` group: DA-04 writes NaN for every frame
    specs = [Spec("ep_a", 10, [(0, 10)]), Spec("ep_b", 10, [(0, 10)], confidence_recorded=False)]
    meta = export(build(tmp_path / "work", specs), tmp_path / "out")
    recorded, missing = (s["pose_confidence"]["left"] for s in meta["samples"])
    assert recorded["recorded"] == 1.0 and recorded["mean"] is not None
    assert missing == {"mean": None, "min": None, "recorded": 0.0}


EPS = ("ep_a", "ep_b")


def set_bundle(work: Path, episode_id: str, **fields: object) -> dict:  # type: ignore[type-arg]
    path = work / "egocentric" / episode_id / "bundle.json"
    bundle = json.loads(path.read_text()) | fields
    path.write_text(json.dumps(bundle))
    return bundle  # type: ignore[no-any-return]


def test_a_dev_episode_lands_in_psi0s_val_set(tmp_path: Path) -> None:
    # DA-04 writes split train or dev; dev is our evaluation split, Psi0's test/ dir
    specs = [Spec("ep_a", 10, [(0, 10)]), Spec("ep_dev", 12, [(0, 12)], split="dev")]
    meta = export(build(tmp_path / "work", specs), tmp_path / "out")
    assert [(s["episode_id"], s["hdf5"]) for s in meta["samples"]] == [
        ("ep_a", "part1/pick_place_cup/0.hdf5"),
        ("ep_dev", "test/pick_place_cup/0.hdf5"),
    ]
    assert meta["counts"]["by_part"] == {"part1": 1, "test": 1}
    [val] = scan(tmp_path / "out", val=True)
    assert val["hdf5"] == tmp_path / "out/test/pick_place_cup/0.hdf5"


@pytest.mark.parametrize("fps", [25.0, 60.0])
def test_a_bundle_not_at_30_fps_is_refused(tmp_path: Path, fps: float) -> None:
    work = build(tmp_path / "work", [Spec("ep_a", 10, [(0, 10)])])
    set_bundle(work, "ep_a", fps=fps)
    with pytest.raises(ExportRefused, match=f"bundle.json says {fps:g} fps; upsample_rate 3"):
        export(work, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_a_video_not_at_30_fps_is_refused_whatever_the_bundle_says(tmp_path: Path) -> None:
    work = build(tmp_path / "work", [Spec("ep_a", 10, [(0, 10)], deid_status="blurred")])
    bundle = set_bundle(work, "ep_a")
    write_video(Path(bundle["mp4"]), 10, fps=60)
    with pytest.raises(ExportRefused, match="ep_a: 0.mp4 says 60 fps; .*resample"):
        export(work, tmp_path / "out")


def test_ntsc_29_97_fps_is_30_fps(tmp_path: Path) -> None:
    work = build(tmp_path / "work", [Spec("ep_a", 10, [(0, 10)])])
    set_bundle(work, "ep_a", fps=29.97)
    assert len(export(work, tmp_path / "out")["samples"]) == 1


def test_a_refused_export_leaves_nothing(tmp_path: Path) -> None:
    work = build(tmp_path / "work", [Spec(e, 10, [(0, 10)], deid_status="blurred") for e in EPS])
    write_video(Path(set_bundle(work, "ep_b")["mp4"]), 6)  # ep_a written, then ep_b fails
    with pytest.raises(ExportRefused, match="ended at frame 6"):
        export(work, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    [ledger] = (tmp_path / "store").rglob("ledger.jsonl")
    assert "failed: ExportRefused" in ledger.read_text().splitlines()[-1]


def test_a_refused_export_into_a_symlink_empties_its_target(tmp_path: Path) -> None:
    work = build(tmp_path / "work", [Spec(e, 10, [(0, 10)], deid_status="blurred") for e in EPS])
    write_video(Path(set_bundle(work, "ep_b")["mp4"]), 6)
    target = tmp_path / "target"
    target.mkdir()
    (tmp_path / "out").symlink_to(target)
    with pytest.raises(ExportRefused, match="ended at frame 6"):
        export(work, tmp_path / "out")
    assert (tmp_path / "out").is_symlink() and list(target.iterdir()) == []


def test_a_non_finite_camera_drops_its_segment_not_the_export(tmp_path: Path) -> None:
    specs = [Spec("ep_a", 10, [(0, 10)]), Spec("ep_b", 10, [(0, 5), (5, 10)])]
    work = build(tmp_path / "work", specs)
    bundle = json.loads((work / "egocentric/ep_b/bundle.json").read_text())
    with h5py.File(bundle["hdf5"], "r+") as f:
        f["transforms/camera"][7, 0, 3] = np.nan
    meta = export(work, tmp_path / "out")
    assert [(s["episode_id"], s["step_id"], s["hdf5"]) for s in meta["samples"]] == [
        ("ep_a", "step_0", "part1/pick_place_cup/0.hdf5"),
        ("ep_b", "step_0", "part1/pick_place_cup/1.hdf5"),
    ]
    assert meta["skipped"] == [
        {
            "episode_id": "ep_b",
            "step_id": "step_1",
            "frame_start": 5,
            "frame_end": 10,
            "reason": "not finite: camera in 1 of 5 frames",
        }
    ]


# --- the D2 waiver, checked against the pin --------------------------------------------


def waived(tmp_path: Path) -> Path:
    return build(tmp_path / "work", [Spec("ep_a", 10, [(0, 10)]), Spec("ep_b", 10, [(0, 10)])])


def test_a_raw_episode_is_waived_only_with_the_pin_named_in_source_json(tmp_path: Path) -> None:
    work = waived(tmp_path)
    meta = export(work, tmp_path / "out")
    pin_id = meta["source"]["deid_waiver_manifest"]
    assert pin_id.startswith("test-pin@") and len(meta["samples"]) == 2
    source = json.loads((work / "source.json").read_text()) | {"deid_waiver_manifest": None}
    (work / "source.json").write_text(json.dumps(source))
    with pytest.raises(ExportRefused, match="ep_a: deid_status raw and the source has no EgoDex"):
        export(work, tmp_path / "out2")


def test_a_pin_other_than_the_one_named_is_refused(tmp_path: Path) -> None:
    work = waived(tmp_path)
    pin = json.loads((work / PIN).read_text())
    other = write_pin(tmp_path, {k: work / "raw" / k for k in pin["files"]}, name="other-pin")
    with pytest.raises(
        ExportRefused, match=f"deid_waiver_manifest test-pin@.* is not the pin {other}"
    ):
        export(work, tmp_path / "out", waiver_pin=tmp_path / PIN)
    with pytest.raises(ExportRefused, match="the D2 pin .*missing.json is not there"):
        export(work, tmp_path / "out", waiver_pin=tmp_path / "missing.json")


def test_a_video_changed_or_not_pinned_is_not_waived(tmp_path: Path) -> None:
    # the labels say egodex and public, but the waiver rests on the video's sha256
    work = waived(tmp_path)
    write_video(Path(set_bundle(work, "ep_b")["mp4"]), 9)
    with pytest.raises(ExportRefused) as refused:
        export(work, tmp_path / "out")
    assert refused.value.problems == [
        f"ep_b: pick_place_cup/1.mp4 sha256 differs from the D2 pin {pin_id(work)}"
    ]
    source = json.loads((work / "source.json").read_text())
    source["deid_waiver_manifest"] = write_pin(
        work, {"pick_place_cup/0.mp4": work / "raw/pick_place_cup/0.mp4"}
    )
    (work / "source.json").write_text(json.dumps(source))
    with pytest.raises(ExportRefused, match="ep_b: pick_place_cup/1.mp4 is not in the D2 pin"):
        export(work, tmp_path / "out")


def test_the_cli_takes_no_other_pin(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # the pin is the PO's decision: a run must not swap in a pin of its own videos
    work = waived(tmp_path)
    argv = ["--work", str(work), "--out", str(tmp_path / "out"), "--store", str(tmp_path / "s")]
    with pytest.raises(SystemExit) as stopped:
        main([*argv, "--waiver-pin", str(work / PIN)])
    assert (
        stopped.value.code == 2
        and "unrecognized arguments: --waiver-pin" in capsys.readouterr().err
    )
    assert not (tmp_path / "out").exists()


def test_internal_data_is_never_waived(tmp_path: Path) -> None:
    spec = Spec("ep_a", 10, [(0, 10)], episode={"data_class": "internal"})
    with pytest.raises(ExportRefused, match="data_class internal is never waived"):
        export(build(tmp_path / "work", [spec]), tmp_path / "out")


def pin_id(work: Path) -> str:
    return str(json.loads((work / "source.json").read_text())["deid_waiver_manifest"])
