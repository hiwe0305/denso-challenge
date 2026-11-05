"""build_release refuses a whole release or freezes it with a hash (DA-03 AC 4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from flywheel.contracts.artifacts import Episode, QAReport
from flywheel.contracts.entities import Release
from flywheel.contracts.v0 import ReleaseManifest
from flywheel.data.release.build import ReleaseRefused, build_release, read_release
from qa_data import SPLITS, episode_of

NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


def report(episode_id: str, decision: str = "pass", reasons: tuple[str, ...] = ()) -> QAReport:
    return QAReport(report_id=f"qa_{episode_id}", episode_id=episode_id, threshold_version="qa-1@x",
                    decision=decision, reasons=list(reasons), checks=[])  # type: ignore[arg-type]


def batch() -> tuple[list[Episode], list[QAReport], dict[str, int | None]]:
    episodes = [episode_of("psi_data", "ep_a"), episode_of("planner_wbc", "ep_b"),
                episode_of("planner_wbc", "ep_c")]
    reports = [report("ep_a"), report("ep_b", "flag", ("action_jump.arm (D3): ...",)),
               report("ep_c", "reject", ("joint_limits (D3): ...",))]
    return episodes, reports, {"ep_a": None, "ep_b": 7, "ep_c": 999_999}


def build(tmp_path: Path, **change: object) -> ReleaseManifest:
    episodes, reports, seeds = batch()
    args = {"episodes": episodes, "reports": reports, "seeds": seeds, **change}
    return build_release(args["episodes"], args["reports"], SPLITS, tmp_path / "rel",  # type: ignore[arg-type]
                         seeds=args["seeds"], now=NOW)  # type: ignore[arg-type]


def test_a_release_keeps_rejected_episodes_with_their_reasons(tmp_path: Path) -> None:
    manifest = build(tmp_path)
    release = read_release(tmp_path / "rel")

    assert manifest == ReleaseManifest(release_id=release.id, frozen=True)
    assert release.status == "frozen" and release.holdout_guard_passed
    items = {i["episode_id"]: i for i in release.items}
    assert [i["episode_id"] for i in release.items] == ["ep_a", "ep_b", "ep_c"]
    assert (items["ep_a"]["excluded"], items["ep_b"]["excluded"]) == (False, False)  # flag stays
    assert items["ep_c"]["excluded"] and items["ep_c"]["reasons"] == ["joint_limits (D3): ..."]
    assert items["ep_a"]["seed"] is None and items["ep_b"]["seed"] == 7
    assert release.counts["included"] == 2 and release.counts["by_decision"]["reject"] == 1
    assert release.counts["seed_unknown"] == 1
    assert release.combined_license == "example"
    written = (tmp_path / "rel/release_manifest.json").read_text()
    assert ReleaseManifest.model_validate_json(written) == manifest
    assert (tmp_path / "rel/FROZEN").read_text().strip() == release.manifest_sha256


def test_the_same_inputs_give_the_same_hash(tmp_path: Path) -> None:
    first = build(tmp_path / "1")
    second = build(tmp_path / "2")
    assert first == second
    episodes, reports, seeds = batch()
    reports[2] = report("ep_c", "reject", ("another reason",))
    third = build(tmp_path / "3", reports=reports)
    assert third.release_id != first.release_id


@pytest.mark.parametrize("which", [0, 2])
def test_one_benchmark_copy_episode_refuses_the_whole_release(tmp_path: Path, which: int) -> None:
    episodes, _, _ = batch()
    meta = episodes[which].meta.model_copy(update={"benchmark_copy_id": "bench-1e258c0a78ca"})
    episodes[which] = episodes[which].model_copy(update={"meta": meta})
    with pytest.raises(ReleaseRefused, match="benchmark copies \\['bench-1e258c0a78ca'\\]"):
        build(tmp_path, episodes=episodes)
    assert not (tmp_path / "rel").exists()


@pytest.mark.parametrize("seed", [1_000_000, 1_000_999, 2_000_124])  # dev and holdout ranges
def test_a_seed_outside_train_refuses_the_release(tmp_path: Path, seed: int) -> None:
    _, _, seeds = batch()
    seeds["ep_c"] = seed  # even an episode QA rejected: the data set itself leaks
    with pytest.raises(ReleaseRefused, match=f"ep_c: condition seed {seed} outside train"):
        build(tmp_path, seeds=seeds)


def test_every_problem_is_listed_at_once(tmp_path: Path) -> None:
    episodes, reports, seeds = batch()
    episodes[0] = episodes[0].model_copy(update={"split": "dev"})
    seeds["ep_b"] = None
    with pytest.raises(ReleaseRefused) as refused:
        build(tmp_path, episodes=episodes, reports=reports[:2], seeds=seeds)
    assert refused.value.problems == [
        "ep_a: split 'dev', a release takes only train",
        "ep_b: machine-made episode without a seed to check",
        "ep_c: no QAReport",
    ]


def test_included_episodes_of_two_embodiments_are_refused(tmp_path: Path) -> None:
    episodes, _, _ = batch()
    episodes[1] = episodes[1].model_copy(update={"embodiment_id": "g1_wholebody_amo@1"})
    with pytest.raises(ReleaseRefused, match="span embodiments"):
        build(tmp_path, episodes=episodes)


def test_a_frozen_release_is_never_written_over(tmp_path: Path) -> None:
    build(tmp_path)
    with pytest.raises(FileExistsError):
        build(tmp_path)


def test_an_edited_release_no_longer_reads(tmp_path: Path) -> None:
    build(tmp_path)
    path = tmp_path / "rel/release.json"
    data = json.loads(path.read_text())
    data["items"][2]["excluded"] = False
    data["id"] = ""
    path.write_text(Release.model_validate(data).to_canonical_json())
    with pytest.raises(ValueError, match="items hash"):
        read_release(tmp_path / "rel")
