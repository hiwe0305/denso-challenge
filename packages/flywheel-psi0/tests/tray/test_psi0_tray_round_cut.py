"""C70_R1's dataset: S70 byte for byte, then the targeted set, with ALL's stats (DA-34 7.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flywheel.data.ingest.lerobot import iter_episodes
from flywheel_psi0.tray import round_cut
from flywheel_psi0.tray.pair_cut import MARKER, STATS, sha256, subset_cut
from flywheel_psi0.tray.pairplan import TrayPairPlan
from flywheel_psi0.tray.pairround import TrayPairRoundPlan
from flywheel_psi0.tray.round_cut import (
    base_problems,
    bounds_problems,
    join_round,
    round_problems,
)
from test_psi0_tray_pair_cut import ENV, PARTS, _part, _setup
from test_psi0_tray_pairround import ROWS, _raw, _rows

# Targeted episodes in the train seed window, not in seed order; values inside ALL's
# range (the fake ALL holds 1002 .. 2109): base + seed = 1500 .. 1510.
ROUND = {"seeds": [100009, 100002, 100005], "lengths": [3, 5, 4], "base": -98500.0}


def _round_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spec: dict[str, Any] = ROUND
) -> tuple[Path, Path, TrayPairRoundPlan, TrayPairPlan, Path]:
    """S70 of the fake ALL, a targeted cut, and a round plan pinning that cut."""
    cut, pair, repo = _setup(tmp_path)
    base = tmp_path / "S70" / ENV
    subset_cut(cut, base, pair, "S70", repo)
    monkeypatch.setitem(PARTS, "rnd", spec)
    targeted = _part(tmp_path / "tgt" / ENV, "rnd")
    (repo / ROWS).parent.mkdir(parents=True, exist_ok=True)
    (repo / ROWS).write_text("".join(json.dumps(r) + "\n" for r in _rows()))
    raw = _raw(repo)
    raw["targets"].update(
        seeds=sorted(spec["seeds"]),
        set_hash="r" * 8,
        release={"id": "rel-rnd", "release_hash": "r" * 64, "location": "here",
                 "data_class": "public"},
    )  # fmt: skip
    return base, targeted, TrayPairRoundPlan.model_validate(raw), pair, repo


def test_the_round_keeps_s70_and_alls_stats_and_appends_the_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base, targeted, plan, pair, repo = _round_setup(tmp_path, monkeypatch)
    out = tmp_path / "C70_R1" / ENV
    marker = join_round(base, targeted, out, plan, pair, repo)
    assert round_problems(out, plan, pair, repo) == []
    assert base_problems(out, base) == []
    n = 7  # the fake S70
    assert (marker["n"], marker["targeted"]["first_episode_index"]) == (n + 3, n)
    episodes = sorted(iter_episodes(out), key=lambda e: e.episode_index)
    assert [e.episode_index for e in episodes] == list(range(n + 3))
    # each new index holds its own seed's episode, in the targeted cut's order
    seeds = [e["seed"] for e in marker["targeted"]["episodes"]]
    assert seeds == ROUND["seeds"]
    assert [float(e.action[0, 0]) for e in episodes[n:]] == [ROUND["base"] + s for s in seeds]
    # S70's files and ALL's stats, byte for byte; no recomputed stats
    for name in (STATS, "stats.json"):
        assert (out / "meta" / name).read_bytes() == (base / "meta" / name).read_bytes()
    assert sha256(out / "meta" / STATS) == pair.cut.stats_sha256
    info = json.loads((out / "meta/info.json").read_text())
    assert info["total_episodes"] == n + 3
    assert info["splits"] == {"train": f"0:{n + 3}"}
    assert info["total_frames"] == pair.subsets[0].frames + sum(ROUND["lengths"])  # type: ignore[index]
    video = out / f"videos/chunk-000/observation.images.egocentric/episode_{n:06d}.mp4"
    assert video.read_bytes().endswith(b"rnd-100009")
    stats_rows = (out / "meta/episodes_stats.jsonl").read_text().splitlines()
    assert [json.loads(r)["episode_index"] for r in stats_rows] == list(range(n + 3))
    with pytest.raises(FileExistsError):
        join_round(base, targeted, out, plan, pair, repo)


def test_checks_catch_a_changed_base_wrong_targets_and_own_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base, targeted, plan, pair, repo = _round_setup(tmp_path, monkeypatch)
    out = tmp_path / "C70_R1" / ENV
    join_round(base, targeted, out, plan, pair, repo)
    parquet = out / "data/chunk-000/episode_000000.parquet"
    parquet.write_bytes(parquet.read_bytes() + b"\0")
    assert any("episode_000000.parquet is not S70's" in p for p in base_problems(out, base))
    stats = out / "meta" / STATS
    stats.write_text("{}")  # what recomputed stats would look like to the check
    assert any("stats_psi0.json sha256" in p for p in round_problems(out, plan, pair, repo))
    raw = json.loads(plan.model_dump_json())
    raw["targets"]["seeds"] = [100001, 100002, 100005]
    other = TrayPairRoundPlan.model_validate(raw)
    problems = round_problems(out, other, pair, repo)
    assert any("own seeds are not targets.seeds" in p for p in problems)
    marker = json.loads((out / "meta" / MARKER).read_text())
    marker["base"]["parts"][0]["episodes"][0]["seed"] = 1001  # not in S70
    (out / "meta" / MARKER).write_text(json.dumps(marker))
    problems = round_problems(out, plan, pair, repo)
    assert any("seeds are not S70's list" in p for p in problems)
    assert any("not S70's, row by row" in p for p in problems)


def test_join_refuses_targets_outside_alls_stats_or_not_the_rounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    far = {**ROUND, "base": 0.0}  # values ~100000: far outside ALL's range
    base, targeted, plan, pair, repo = _round_setup(tmp_path, monkeypatch, far)
    stats = json.loads((base / "meta" / STATS).read_text())
    outside = bounds_problems(targeted, stats)
    assert [p.split(":")[0] for p in outside] == ["action", "states"]
    assert "12 of 12 frames" in outside[0]
    with pytest.raises(ValueError, match="leaves ALL's stats"):
        join_round(base, targeted, tmp_path / "out" / ENV, plan, pair, repo)
    raw = json.loads(plan.model_dump_json())
    raw["targets"]["set_hash"] = "x" * 8
    with pytest.raises(ValueError, match="set_hash"):
        join_round(
            base, targeted, tmp_path / "out2" / ENV, TrayPairRoundPlan.model_validate(raw), pair,
            repo,
        )  # fmt: skip
    assert not (tmp_path / "out" / ENV).exists()


def _bounds_decision(path: Path, plan: TrayPairRoundPlan, outside: list[str], **kw: Any) -> Path:
    from flywheel.contracts.entities import Decision

    fields: dict[str, Any] = {
        "site_id": "local", "task_id": "t", "embodiment_id": "e", "kind": "dev_gate",
        "subject_kind": "round_plan", "subject_id": plan.name, "verdict": "approved",
        "metrics": {"bounds_outside": outside}, "signed_by": "Hiếu", "reason": "R13",
    }  # fmt: skip
    path.write_text(Decision(**{**fields, **kw}).model_dump_json(indent=1))
    return path


def test_a_signed_decision_lets_exactly_the_reported_excess_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # tray.md 20.6 / 20.15 R13: outside ALL's stats means stop and record a Decision; the
    # join then goes on only for the very excess the Decision quotes, and records it
    far = {**ROUND, "base": 0.0}
    base, targeted, plan, pair, repo = _round_setup(tmp_path, monkeypatch, far)
    outside = bounds_problems(targeted, json.loads((base / "meta" / STATS).read_text()))
    wrong = _bounds_decision(tmp_path / "wrong.json", plan, outside[:1])
    with pytest.raises(ValueError, match="does not accept"):
        join_round(base, targeted, tmp_path / "o1" / ENV, plan, pair, repo, accept=wrong)
    other = _bounds_decision(tmp_path / "other.json", plan, outside, subject_id="another-round")
    with pytest.raises(ValueError, match="does not accept"):
        join_round(base, targeted, tmp_path / "o2" / ENV, plan, pair, repo, accept=other)
    unsigned = _bounds_decision(tmp_path / "open.json", plan, outside, verdict="open")
    with pytest.raises(ValueError, match="does not accept"):
        join_round(base, targeted, tmp_path / "o3" / ENV, plan, pair, repo, accept=unsigned)
    good = _bounds_decision(tmp_path / "good.json", plan, outside)
    out = tmp_path / "ok" / ENV
    marker = join_round(base, targeted, out, plan, pair, repo, accept=good)
    assert marker["bounds"]["outside"] == outside
    assert marker["bounds"]["decision_sha256"] == sha256(good)
    assert round_problems(out, plan, pair, repo) == []
    assert not any((tmp_path / d).exists() for d in ("o1", "o2", "o3"))


def test_bounds_are_float32_per_dimension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base, targeted, _, _, _ = _round_setup(tmp_path, monkeypatch)
    stats = json.loads((base / "meta" / STATS).read_text())
    assert bounds_problems(targeted, stats) == []
    # tighten one action dim to just below the targeted values: only that dim is reported
    stats["action"]["max"][5] = float(np.float32(1501.0))
    outside = bounds_problems(targeted, stats)
    assert len(outside) == 1 and "dims [5]" in outside[0]
    assert bounds_problems(targeted, stats, first=99) == []


def test_cli_check_and_pack_read_the_round(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base, targeted, plan, pair, repo = _round_setup(tmp_path, monkeypatch)
    out = tmp_path / "C70_R1" / ENV
    join_round(base, targeted, out, plan, pair, repo)
    monkeypatch.setattr(round_cut, "_load", lambda path, repo: (plan, pair))
    monkeypatch.setattr(round_cut, "REPO", repo)
    args = ["--round", "plan.yaml", "--data", str(out)]
    assert round_cut.main(["check", *args, "--base", str(base)]) == 0
    tar = tmp_path / "C70_R1.tar"
    assert round_cut.main(["pack", *args, "--out", str(tar)]) == 0
    assert json.loads(Path(f"{tar}.json").read_text())["name"] == "C70_R1"
