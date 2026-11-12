"""The jobs of an S2 batch DA-03 kept, and running a listed job file (DA-35 task 12)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

S2_SCRIPTS = Path(__file__).resolve().parents[5] / "scripts" / "g0" / "tray" / "s2"
# job index -> decision of its episode; jobs 1 and 5 failed and have no episode
DECISIONS = {0: "pass", 2: "reject", 3: "flag", 4: "quarantine", 6: "pass"}


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, S2_SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def qpj() -> ModuleType:
    return load("qa_pass_jobs")


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    return load("generate_s2")


def job(i: int) -> dict[str, Any]:
    return {"parent_id": f"p/shard-0{i % 2}/{i // 2}", "level": i % 2, "seed": 500 + i,
            "gen_seed": 9000 + i}  # fmt: skip


def block(i: int, **over: Any) -> dict[str, Any]:
    j = job(i)
    keys = {"parent_episode": j["parent_id"], "level": j["level"], "seed": j["seed"],
            "gen_seed": j["gen_seed"], "s2_mode": "variant", "outcome": "success"}  # fmt: skip
    return {**keys, **over}


def gate(tmp_path: Path, blocks: list[dict[str, Any]] | None = None,
         version: Any = "qa-1@test") -> tuple[Path, Path, Path]:  # fmt: skip
    """A batch of 7 jobs, the Psi0 export of its 5 episodes (shard order, not job order)
    and the ingest work directory after `fw data qa`."""
    batch, export, work = tmp_path / "batch", tmp_path / "export", tmp_path / "work"
    for d in (batch, export / "meta", work / "qa"):
        d.mkdir(parents=True)
    (batch / "jobs.jsonl").write_text("".join(json.dumps(job(i)) + "\n" for i in range(7)))
    order = [6, 0, 4, 2, 3]
    blocks = blocks if blocks is not None else [block(i) for i in order]
    rows = [{"episode_index": n, "environment_config": json.dumps({"flywheel": b})}
            for n, b in enumerate(blocks)]  # fmt: skip
    meta = export / "meta" / "episodes.jsonl"
    meta.write_text("".join(json.dumps(r) + "\n" for r in rows))
    sha = hashlib.sha256(meta.read_bytes()).hexdigest()
    (work / "source.json").write_text(json.dumps({"files": {"meta/episodes.jsonl": sha}}))
    (work / "episode_index.json").write_text(json.dumps({f"ep_{n}": n for n in range(len(rows))}))
    reports = []
    for n, i in enumerate(order[: len(rows)]):
        v = version(n) if callable(version) else version
        reasons = [] if DECISIONS[i] == "pass" else ["x"]
        reports.append({"report_id": f"qa_{n}", "episode_id": f"ep_{n}", "threshold_version": v,
                        "decision": DECISIONS[i], "reasons": reasons, "checks": []})  # fmt: skip
    (work / "qa" / "reports.jsonl").write_text("".join(json.dumps(r) + "\n" for r in reports))
    return work, export, batch


def test_pass_and_flag_jobs_come_back_in_job_order(qpj: ModuleType, tmp_path: Path) -> None:
    work, export, batch = gate(tmp_path)
    kept, record = qpj.kept_jobs(work, export, batch)
    assert kept == [job(0), job(3), job(6)]
    assert record["decisions"] == {"flag": 1, "pass": 2, "quarantine": 1, "reject": 1}
    assert (record["episodes"], record["kept"], record["threshold_version"]) == (5, 3, "qa-1@test")


def test_main_writes_the_list_and_its_record(qpj: ModuleType, tmp_path: Path) -> None:
    work, export, batch = gate(tmp_path)
    out = tmp_path / "pass-jobs.jsonl"
    argv = ["--qa-work", str(work), "--qa-export", str(export), "--batch", str(batch)]
    assert qpj.main([*argv, "--out", str(out)]) == 0
    assert [json.loads(x) for x in out.read_text().splitlines()] == [job(0), job(3), job(6)]
    record = json.loads((tmp_path / "pass-jobs.jsonl.record.json").read_text())
    assert record["out_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()


def test_qa_of_another_export_is_refused(qpj: ModuleType, tmp_path: Path) -> None:
    work, export, batch = gate(tmp_path)
    (work / "source.json").write_text(json.dumps({"files": {"meta/episodes.jsonl": "0" * 64}}))
    with pytest.raises(ValueError, match="another export"):
        qpj.kept_jobs(work, export, batch)


def test_an_episode_without_a_report_is_refused(qpj: ModuleType, tmp_path: Path) -> None:
    work, export, batch = gate(tmp_path)
    path = work / "qa" / "reports.jsonl"
    path.write_text("".join(path.read_text().splitlines(keepends=True)[:-1]))
    with pytest.raises(ValueError, match="no DA-03 QA report"):
        qpj.kept_jobs(work, export, batch)


def test_mixed_threshold_versions_are_refused(qpj: ModuleType, tmp_path: Path) -> None:
    work, export, batch = gate(tmp_path, version=lambda n: f"qa-{n % 2}@test")
    with pytest.raises(ValueError, match="mixes threshold versions"):
        qpj.kept_jobs(work, export, batch)


@pytest.mark.parametrize(
    ("blocks", "match"),
    [
        ([block(6), block(0, gen_seed=1), block(4), block(2), block(3)], "no job of"),
        ([block(6), block(6), block(4), block(2), block(3)], "two export episodes"),
        ([block(6), block(0, s2_mode="exact"), block(4), block(2), block(3)], "not a successful"),
        ([block(6), block(0, outcome="failure"), block(4), block(2), block(3)], "not a successful"),
    ],
)
def test_an_episode_that_is_not_one_kept_job_is_refused(
    qpj: ModuleType, tmp_path: Path, blocks: list[dict[str, Any]], match: str
) -> None:
    work, export, batch = gate(tmp_path, blocks=blocks)
    with pytest.raises(ValueError, match=match):
        qpj.kept_jobs(work, export, batch)


def segments(ids: list[int]) -> list[dict[str, Any]]:
    return [{"parent_id": job(i)["parent_id"], "level": job(i)["level"], "seed": 0} for i in ids]


def write_jobs(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def test_listed_jobs_keep_only_the_job_keys(gen: ModuleType, tmp_path: Path) -> None:
    rows = [{**job(0), "extra": 1}, job(3)]
    jobs = gen.listed_jobs(write_jobs(tmp_path / "j.jsonl", rows), segments([0, 3]))
    assert jobs == [job(0), job(3)]


@pytest.mark.parametrize(
    ("rows", "match"),
    [
        ([job(0), job(5)], "not a kept parent"),
        ([job(0), job(0)], "listed twice"),
        ([{k: v for k, v in job(0).items() if k != "gen_seed"}], "no \\['gen_seed'\\]"),
        ([], "lists no job"),
    ],
)
def test_a_listed_job_file_fails_closed(
    gen: ModuleType, tmp_path: Path, rows: list[dict[str, Any]], match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        gen.listed_jobs(write_jobs(tmp_path / "j.jsonl", rows), segments([0, 3]))


def test_a_listed_job_file_needs_the_qa_filter(gen: ModuleType, tmp_path: Path) -> None:
    jobs = write_jobs(tmp_path / "j.jsonl", [job(0)])
    argv = ["--parents", str(tmp_path), "--out", str(tmp_path / "out"), "--jobs-file", str(jobs)]
    with pytest.raises(SystemExit):
        gen.main(argv)


def test_a_refused_job_file_starts_nothing(gen: ModuleType, tmp_path: Path) -> None:
    parents = tmp_path / "parents"
    parents.mkdir()
    write_jobs(parents / "s2_segments.jsonl", segments([0]))
    jobs = write_jobs(tmp_path / "j.jsonl", [job(5)])
    argv = ["--parents", str(parents), "--out", str(tmp_path / "out"), "--jobs-file", str(jobs),
            "--no-qa"]  # fmt: skip
    assert gen.main(argv) == 1
    assert not (tmp_path / "out").exists()
