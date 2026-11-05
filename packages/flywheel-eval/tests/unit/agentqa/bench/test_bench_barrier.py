"""DA-31 test: the agent cannot open the DefectManifest (design 27/10/2026 section 9.2).

Only `flywheel.eval.agentqa.bench` reads the answer key. Every other module of
`flywheel.eval` (the agent of DA-20 under `agentqa/`, and the detectors the code
layer runs) must neither name the manifest nor import the bench, so nothing the
agent runs can reach the answer through this lane.
"""

from __future__ import annotations

import ast
from pathlib import Path

import flywheel.eval

LANE = Path(flywheel.eval.__file__).resolve().parent
BENCH = LANE / "agentqa" / "bench"
FORBIDDEN_NAMES = ("DefectManifest", "defect_manifest", "load_manifest", "open_sealed")


def _outside_bench() -> list[Path]:
    return [p for p in sorted(LANE.rglob("*.py")) if BENCH not in p.parents]


def test_no_module_outside_the_bench_names_the_answer_key() -> None:
    hits = [
        f"{path.relative_to(LANE)}: {name}"
        for path in _outside_bench()
        for name in FORBIDDEN_NAMES
        if name in path.read_text(encoding="utf-8")
    ]
    assert hits == []


def test_no_module_outside_the_bench_imports_it() -> None:
    hits = []
    for path in _outside_bench():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names] if isinstance(node, ast.Import)
                else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            )
            hits += [f"{path.relative_to(LANE)}: {n}" for n in names if ".bench" in n]
    assert hits == []


def test_the_barrier_scans_the_agent_package() -> None:
    scanned = {p.relative_to(LANE).as_posix() for p in _outside_bench()}
    assert "agentqa/cli.py" in scanned
    assert not any(name.startswith("agentqa/bench/") for name in scanned)
