"""Parents DA-03's QA rejected seed no S2 job, and the filter fails closed (DA-35 task 12,
decision of 5/11/2026)."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[5] / "scripts" / "g0" / "tray" / "s2" / "generate_s2.py"
DECISIONS = {(0, 101): "reject", (1, 102): "quarantine", (1, 103): "flag"}  # the rest pass


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_s2", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def segments() -> list[dict[str, Any]]:
    """Six parents of batch `p` over two shards, as segment_parents writes them."""
    conditions = [(0, 100), (0, 101), (1, 102), (1, 103), (0, 104), (1, 105)]
    return [
        {"parent_id": f"p/shard-0{k % 2}/{k // 2}", "shard": f"shard-0{k % 2}",
         "episode_index": k // 2, "level": level, "seed": seed}
        for k, (level, seed) in enumerate(conditions)
    ]  # fmt: skip


def report(i: int, episode_id: str, decision: str, version: str = "qa-1@test") -> dict[str, Any]:
    reasons = [] if decision == "pass" else [f"{decision} reason"]
    return {"report_id": f"qa_{i}", "episode_id": episode_id, "threshold_version": version,
            "decision": decision, "reasons": reasons, "checks": []}  # fmt: skip


def qa_store(tmp_path: Path, segs: list[dict[str, Any]]) -> tuple[Path, Path]:
    """The parents' Psi0 export (in reverse order: positions are not parent order) and the
    `fw data ingest` work directory of it after `fw data qa`."""
    export, work = tmp_path / "export", tmp_path / "work"
    (export / "meta").mkdir(parents=True)
    (work / "qa").mkdir(parents=True)
    rows = []
    for s in reversed(segs):
        block = {"session": f"p-{s['shard'][-2:]}", "level": s["level"], "seed": s["seed"]}
        config = json.dumps({"flywheel": block})
        rows.append({"episode_index": len(rows), "environment_config": config})
    meta = export / "meta" / "episodes.jsonl"
    meta.write_text("".join(json.dumps(r) + "\n" for r in rows))
    sha = hashlib.sha256(meta.read_bytes()).hexdigest()
    (work / "source.json").write_text(json.dumps({"files": {"meta/episodes.jsonl": sha}}))
    index = {f"ep_{n}": n for n in range(len(rows))}
    (work / "episode_index.json").write_text(json.dumps(index))
    reports = []
    for n, r in enumerate(rows):
        block = json.loads(r["environment_config"])["flywheel"]
        decision = DECISIONS.get((block["level"], block["seed"]), "pass")
        reports.append(report(n, f"ep_{n}", decision))
    (work / "qa" / "reports.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reports))
    return work, export


def rewrite_reports(work: Path, edit: Any) -> None:
    path = work / "qa" / "reports.jsonl"
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    path.write_text("".join(json.dumps(r) + "\n" for r in edit(rows)))


def test_reject_and_quarantine_are_left_out_and_recorded(gen: ModuleType, tmp_path: Path) -> None:
    work, export = qa_store(tmp_path, segments())
    kept, record = gen.qa_filter(segments(), work, export)
    assert [(s["level"], s["seed"]) for s in kept] == [(0, 100), (1, 103), (0, 104), (1, 105)]
    assert [(x["seed"], x["decision"], x["reasons"]) for x in record["excluded"]] == [
        (101, "reject", ["reject reason"]),
        (102, "quarantine", ["quarantine reason"]),
    ]
    assert (record["parents"], record["kept"], record["threshold_version"]) == (6, 4, "qa-1@test")
    reports = work / "qa" / "reports.jsonl"
    assert record["reports_sha256"] == hashlib.sha256(reports.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("break_it", "why"),
    [
        ("other export", "QA of another export"),
        ("missing report", "no DA-03 QA report"),
        ("two reports", "two DA-03 QA reports"),
        ("mixed versions", "mixes threshold versions"),
        ("bad decision", "is not a QAReport"),
        ("parent not exported", "0 export episodes for parent p/shard-01/9"),
    ],
)
def test_the_filter_fails_closed(gen: ModuleType, tmp_path: Path, break_it: str, why: str) -> None:
    segs = segments()
    work, export = qa_store(tmp_path, segs)
    if break_it == "other export":
        meta = export / "meta" / "episodes.jsonl"
        meta.write_text(meta.read_text() + "\n")
    elif break_it == "missing report":
        rewrite_reports(work, lambda rows: rows[1:])
    elif break_it == "two reports":
        rewrite_reports(work, lambda rows: [*rows, {**rows[0], "report_id": "qa_again"}])
    elif break_it == "mixed versions":
        rewrite_reports(work, lambda rows: [{**rows[0], "threshold_version": "qa-2@x"}, *rows[1:]])
    elif break_it == "bad decision":
        rewrite_reports(work, lambda rows: [{**rows[0], "decision": "maybe"}, *rows[1:]])
    else:
        segs = [*segs, {**segs[-1], "parent_id": "p/shard-01/9", "seed": 199}]
    with pytest.raises(ValueError, match=why):
        gen.qa_filter(segs, work, export)


@pytest.fixture
def parents(tmp_path: Path) -> Path:
    path = tmp_path / "p"
    path.mkdir()
    (path / "s2_segments.jsonl").write_text("".join(json.dumps(s) + "\n" for s in segments()))
    return path


def test_variants_need_the_filter(gen: ModuleType, tmp_path: Path, parents: Path) -> None:
    argv = ["--parents", str(parents), "--out", str(tmp_path / "out"), "--variants", "10"]
    with pytest.raises(SystemExit):
        gen.main(argv)
    with pytest.raises(SystemExit):
        gen.main([*argv, "--qa-work", str(tmp_path)])  # without --qa-export


def test_jobs_come_from_the_kept_parents_only(
    gen: ModuleType, tmp_path: Path, parents: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from flywheel.data import ledger

    @contextlib.contextmanager
    def no_ledger(*_: Any, **__: Any) -> Iterator[Any]:
        yield SimpleNamespace(notes=[], run_plan_id="rp", job_id="job")

    launched: list[list[str]] = []

    def launch(args: Any, jobs: list[dict[str, Any]]) -> dict[int, Any]:
        launched.append([j["parent_id"] for j in jobs])
        return {}

    monkeypatch.setattr(ledger, "job_ledger", no_ledger)
    monkeypatch.setattr(gen, "launch", launch)
    work, export = qa_store(tmp_path, segments())
    out = tmp_path / "out"
    argv = ["--parents", str(parents), "--out", str(out), "--replay",
            "--qa-work", str(work), "--qa-export", str(export)]  # fmt: skip
    gen.main(argv)
    assert launched == [["p/shard-00/0", "p/shard-01/1", "p/shard-00/2", "p/shard-01/2"]]
    record = json.loads((out / "qa_parents.json").read_text())
    assert [x["seed"] for x in record["excluded"]] == [101, 102]


def test_a_refused_filter_starts_no_worker(
    gen: ModuleType, tmp_path: Path, parents: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work, export = qa_store(tmp_path, segments())
    rewrite_reports(work, lambda rows: rows[1:])
    monkeypatch.setattr(gen, "launch", lambda *_: pytest.fail("a worker started"))
    argv = ["--parents", str(parents), "--out", str(tmp_path / "out"), "--variants", "10",
            "--qa-work", str(work), "--qa-export", str(export)]  # fmt: skip
    assert gen.main(argv) == 1
    assert not (tmp_path / "out" / "qa_parents.json").exists()
