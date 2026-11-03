"""Nothing in a benchmark copy but the defects themselves gives the answer away.

Stats are recomputed from each copy's own data, both copies hold the same files, the
writer's lineage goes to the scorer's side, and no file outside the copy marker names
injection, defects, duplication or the benchmark.
"""

import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import pytest
from flywheel.data.ingest.lerobot import iter_episodes, read_episode_rows
from flywheel.data.inject.build import build_benchmark
from flywheel.data.inject.manifest import load_manifest
from lerobot_data import make_dataset

MARKER = "meta/benchmark_copy.json"
WORDS = (b"inject", b"defect", b"duplicate", b"bench")


def stats_block(arr: np.ndarray) -> dict[str, list[float]]:
    """SIMPLE scripts/postprocess_psi0_sonic.py @ 6d10628, `stats_block`, verbatim."""
    arr = np.asarray(arr)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    return {
        "mean": arr.mean(axis=0).astype(np.float32).tolist(),
        "std": arr.std(axis=0).astype(np.float32).tolist(),
        "min": arr.min(axis=0).astype(np.float32).tolist(),
        "max": arr.max(axis=0).astype(np.float32).tolist(),
        "q01": np.quantile(arr, 0.01, axis=0).astype(np.float32).tolist(),
        "q99": np.quantile(arr, 0.99, axis=0).astype(np.float32).tolist(),
    }


@pytest.fixture(scope="module")
def copies(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Path]]:
    base = tmp_path_factory.mktemp("sym")
    make_dataset(base / "psi", count=40, length=8)
    result = build_benchmark(base / "psi", base / "inject")
    roots = {"defect": Path(result.defect.ref.uri), "clean": Path(result.clean.ref.uri)}
    return base / "inject", roots


def _text(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def _files(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def test_stats_of_both_copies_are_their_own_data(
    copies: tuple[Path, dict[str, Path]],
) -> None:
    _, roots = copies
    for root in roots.values():
        tasks = {
            json.loads(line)["task"]: json.loads(line)["task_index"]
            for line in (root / "meta/tasks.jsonl").read_text().splitlines()
        }
        stored = [
            json.loads(line)
            for line in (root / "meta/episodes_stats.jsonl").read_text().splitlines()
        ]
        columns: dict[str, list[np.ndarray]] = {
            k: []
            for k in (
                "states",
                "action",
                "timestamp",
                "frame_index",
                "episode_index",
                "index",
                "task_index",
                "next.done",
            )
        }
        expected = []
        for f in iter_episodes(root):
            n = len(f.timestamp)
            expected.append(
                {
                    "episode_index": f.episode_index,
                    "stats": {
                        "action": {**stats_block(f.action), "count": [n]},
                        "timestamp": {**stats_block(f.timestamp), "count": [n]},
                    },
                }
            )
            path = root / f"data/chunk-000/episode_{f.episode_index:06d}.parquet"
            done = np.zeros(n, dtype=bool)
            done[-1] = True
            for name, values in (
                ("states", f.states),
                ("action", f.action),
                ("timestamp", f.timestamp),
                ("frame_index", f.frame_index),
                ("episode_index", np.full(n, f.episode_index, np.int64)),
                ("index", pq.read_table(path, columns=["index"]).column("index").to_numpy()),
                ("task_index", np.full(n, tasks[f.task], np.int64)),
                ("next.done", done.astype(np.float32)),
            ):
                columns[name].append(values)
        # Compare as JSON text: a NaN-injected episode has NaN stats, and NaN != NaN.
        assert _text(stored) == _text(expected), root.name
        dataset = {k: stats_block(np.concatenate(v, axis=0)) for k, v in columns.items()}
        assert _text(json.loads((root / "meta/stats.json").read_text())) == _text(dataset)
        assert _text(json.loads((root / "meta/stats_psi0.json").read_text())) == _text(dataset)
        assert json.loads((root / "meta/relative_stats.json").read_text()) == {}


def test_stats_follow_the_injected_data(copies: tuple[Path, dict[str, Path]]) -> None:
    out, roots = copies
    manifest = load_manifest(out / "answers" / roots["defect"].name / "defect_manifest.json")
    flipped = next(d for d in manifest.defects if d.parameters["kind"] == "action_sign_flip")
    index = int(flipped.target_ref.removeprefix("episode_"))

    def row(root: Path) -> dict[str, object]:
        rows = [
            json.loads(x) for x in (root / "meta/episodes_stats.jsonl").read_text().splitlines()
        ]
        return next(r for r in rows if r["episode_index"] == index)

    assert row(roots["defect"]) != row(roots["clean"])


def test_both_copies_hold_the_same_files_and_no_lineage(
    copies: tuple[Path, dict[str, Path]],
) -> None:
    out, roots = copies
    assert _files(roots["defect"]) == _files(roots["clean"])
    for root in roots.values():
        assert not (root / "meta/flywheel_lineage.jsonl").exists()
    # The writer's renumbering record is kept, on the scorer's side.
    kept = list((out / "answers").glob("*/flywheel_lineage.jsonl"))
    assert kept, "the defect copy's shortened episodes renumber the ones after them"


def test_no_file_but_the_marker_names_the_benchmark(
    copies: tuple[Path, dict[str, Path]],
) -> None:
    # A word counts only where a copy holds it more often than the source file:
    # psi-data's own environment_config says "allow_duplicates" in every row.
    out, roots = copies
    source = out.parent / "psi"

    def count(path: Path, word: bytes) -> int:
        return path.read_bytes().lower().count(word) if path.is_file() else 0

    for root in roots.values():
        for name in _files(root):
            if name == MARKER:
                continue
            added = [w for w in WORDS if count(root / name, w) > count(source / name, w)]
            assert not added, (root.name, name)


def test_every_file_of_both_copies_has_one_mtime(copies: tuple[Path, dict[str, Path]]) -> None:
    _, roots = copies
    stamps = {(r / n).stat().st_mtime for r in roots.values() for n in _files(r)}
    assert len(stamps) == 1


def test_episode_meta_rows_have_the_same_keys(copies: tuple[Path, dict[str, Path]]) -> None:
    _, roots = copies
    keys = [sorted({k for r in read_episode_rows(root) for k in r}) for root in roots.values()]
    assert keys[0] == keys[1]


def test_untouched_episodes_have_the_same_stats_in_both_copies(
    copies: tuple[Path, dict[str, Path]],
) -> None:
    out, roots = copies
    manifest = load_manifest(out / "answers" / roots["defect"].name / "defect_manifest.json")
    targets = {int(d.target_ref.removeprefix("episode_")) for d in manifest.defects}

    def rows(root: Path) -> dict[int, str]:
        lines = (root / "meta/episodes_stats.jsonl").read_text().splitlines()
        return {json.loads(x)["episode_index"]: x for x in lines}

    defect, clean = rows(roots["defect"]), rows(roots["clean"])
    untouched = [i for i in clean if i not in targets]
    assert len(untouched) == 7
    assert all(defect[i] == clean[i] for i in untouched)


def test_stats_the_lane_cannot_recompute_follow_the_episode_video(tmp_path: Path) -> None:
    # Image stats need decoded video, which the lane never decodes: they are carried
    # from the episode whose video the copy now holds, the source's for a duplicate.
    src = tmp_path / "psi"
    make_dataset(src, count=40, length=8)
    meta = src / "meta"
    image = {f"ep{i}": {"mean": [[[float(i)]]], "count": [8]} for i in range(40)}
    meta.joinpath("episodes_stats.jsonl").write_text(
        "".join(
            json.dumps(
                {"episode_index": i, "stats": {"observation.images.egocentric": image[f"ep{i}"]}}
            )
            + "\n"
            for i in range(40)
        )
    )
    meta.joinpath("stats.json").write_text(
        json.dumps({"observation.images.egocentric": {"mean": [1.0]}})
    )
    result = build_benchmark(src, tmp_path / "inject")
    manifest = load_manifest(result.defect.manifest_path)
    duplicates = {
        int(d.target_ref.removeprefix("episode_")): int(
            str(d.parameters["original_id"]).removeprefix("episode_")
        )
        for d in manifest.defects
        if d.parameters["kind"] == "duplicate_episode"
    }
    for root in (Path(result.defect.ref.uri), Path(result.clean.ref.uri)):
        rows = [
            json.loads(x) for x in (root / "meta/episodes_stats.jsonl").read_text().splitlines()
        ]
        for row in rows:
            index = row["episode_index"]
            owner = (
                duplicates.get(index, index) if root.name == result.defect.ref.dataset_id else index
            )
            assert list(row["stats"]) == ["observation.images.egocentric", "action", "timestamp"]
            assert row["stats"]["observation.images.egocentric"] == image[f"ep{owner}"]
        dataset = json.loads((root / "meta/stats.json").read_text())
        assert list(dataset)[0] == "observation.images.egocentric"
        assert dataset["observation.images.egocentric"] == {"mean": [1.0]}
