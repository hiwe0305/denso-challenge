"""An S2 batch DA-03 kept whole becomes a hashed release; anything else is refused
(DA-35 task 12, AC 7)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from flywheel_simple.tray.release import verify_manifest

SCRIPT = Path(__file__).resolve().parents[5] / "scripts" / "g0" / "tray" / "s2" / "release_s2.py"


@pytest.fixture(scope="module")
def rel() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_s2", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def block(n: int, **over: Any) -> dict[str, Any]:
    keys = {"source_kind": "synthetic", "synthetic_tier": "S2", "s2_mode": "variant",
            "outcome": "success", "source_detail": "s2", "level": n % 2, "seed": 10 + n,
            "parent_episode": f"p/shard-00/{n % 2}", "visuals_revision": "rev+zone1",
            "generator_version": "da35-s2-3+cfg.x"}  # fmt: skip
    return {**keys, **over}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup(tmp_path: Path, blocks: list[dict[str, Any]] | None = None,
          decisions: list[str] | None = None) -> tuple[Path, Path, Path, Path]:  # fmt: skip
    """A 3-episode export, its gate (on a relabelled copy) and the batch directory."""
    export, work, batch, releases = (tmp_path / d for d in ("stage", "work", "batch", "rel"))
    blocks = blocks if blocks is not None else [block(n) for n in range(3)]
    decisions = decisions if decisions is not None else ["pass", "flag", "pass"]
    for d in (export / "meta", work / "qa", batch, releases):
        d.mkdir(parents=True)
    for n in range(len(blocks)):
        parquet = (f"data/chunk-000/episode_{n:06d}.parquet", b"rows%d" % n)
        video = (f"videos/chunk-000/ego/episode_{n:06d}.mp4", b"mp4%d" % n)
        for rel_path, body in (parquet, video):
            path = export / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
    (export / "meta" / "info.json").write_text("{}")
    rows = [{"episode_index": n, "length": 100 + n,
             "environment_config": json.dumps({"flywheel": b})}
            for n, b in enumerate(blocks)]  # fmt: skip
    (export / "meta" / "episodes.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    files = {p.relative_to(export).as_posix(): sha(p) for p in export.rglob("*") if p.is_file()}
    files["meta/episodes.jsonl"] = "f" * 64  # the gated copy was relabelled
    (work / "source.json").write_text(json.dumps({"files": files}))
    (work / "episode_index.json").write_text(json.dumps({f"ep_{n}": n for n in range(len(rows))}))
    reports = [{"report_id": f"qa_{n}", "episode_id": f"ep_{n}", "threshold_version": "qa-1@t",
                "decision": d, "reasons": [] if d == "pass" else ["x"], "checks": []}
               for n, d in enumerate(decisions)]  # fmt: skip
    (work / "qa" / "reports.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reports))
    for name in ("summary.json", "jobs.jsonl", "qa_parents.json"):
        (batch / name).write_text("{}\n")
    return export, work, batch, releases


def test_a_kept_batch_becomes_a_hashed_release(rel: ModuleType, tmp_path: Path) -> None:
    export, work, batch, releases = setup(tmp_path)
    out = rel.release(export, work, batch, releases)
    final = Path(out["release"])
    assert final.name == f"tray_s2_{out['release_hash'][:12]}" and final.parent == releases
    assert not export.exists() and verify_manifest(final)
    assert (out["episodes"], out["frames"], out["parents"]) == (3, 303, 2)
    assert out["decisions"] == {"flag": 1, "pass": 2}
    assert (out["visuals_revision"], out["threshold_version"]) == ("rev+zone1", "qa-1@t")
    for name in ("batch_summary.json", "batch_jobs.jsonl", "batch_qa_parents.json",
                 "da03_qa_reports.jsonl", "release_info.json"):  # fmt: skip
        assert (final / "meta" / name).is_file()
    info = json.loads((final / "meta" / "release_info.json").read_text())
    assert info["levels"] == {"0": 2, "1": 1}


def test_a_rejected_episode_stops_the_release(rel: ModuleType, tmp_path: Path) -> None:
    export, work, batch, releases = setup(tmp_path, decisions=["pass", "reject", "pass"])
    with pytest.raises(ValueError, match="DA-03 left out"):
        rel.release(export, work, batch, releases)
    assert export.exists() and not any(releases.iterdir())


def test_a_file_that_differs_from_the_gated_copy_is_refused(
    rel: ModuleType, tmp_path: Path
) -> None:
    export, work, batch, releases = setup(tmp_path)
    (export / "data" / "chunk-000" / "episode_000001.parquet").write_bytes(b"other")
    with pytest.raises(ValueError, match="differs"):
        rel.release(export, work, batch, releases)


def test_a_file_the_gate_never_saw_is_refused(rel: ModuleType, tmp_path: Path) -> None:
    export, work, batch, releases = setup(tmp_path)
    (export / "meta" / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="other files"):
        rel.release(export, work, batch, releases)


@pytest.mark.parametrize(
    ("blocks", "match"),
    [
        ([block(0), block(1, visuals_revision="rev"), block(2)], "mix visuals_revision"),
        ([block(0), block(1, generator_version="g2"), block(2)], "mix generator_version"),
        ([block(0), block(1, synthetic_tier="S1"), block(2)], "not a successful S2"),
        ([block(0), block(1, outcome="failure"), block(2)], "not a successful S2"),
    ],
)
def test_episodes_that_are_not_one_s2_batch_are_refused(
    rel: ModuleType, tmp_path: Path, blocks: list[dict[str, Any]], match: str
) -> None:
    export, work, batch, releases = setup(tmp_path, blocks=blocks)
    with pytest.raises(ValueError, match=match):
        rel.release(export, work, batch, releases)


def test_a_missing_report_is_refused(rel: ModuleType, tmp_path: Path) -> None:
    export, work, batch, releases = setup(tmp_path, decisions=["pass", "pass"])
    with pytest.raises(ValueError, match="2 DA-03 QA reports for 3 episodes"):
        rel.release(export, work, batch, releases)
