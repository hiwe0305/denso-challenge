"""Builders of the record-binding tests (DA-54 task 3.1): a public small pack and its runs.

A plain module, as `helpers_mcp`. Its importer puts the round tests' directory on
`sys.path` first (the small pack of the investigate-verify tests is built there).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from flywheel.contracts.entities import Source
from flywheel.eval.agentqa.round.pipeline import run_round
from helpers_mcp import repacked
from helpers_round import NOW, SHA
from test_agentqa_round_investigate import Bot, factory_of
from test_agentqa_round_investigate_verify import small_pack

HEAD = "R/place/L-PLACE-POSE/l1"
OFFSET = {"cluster": HEAD, "measure": "final.offset_m", "against": "successes_same_level"}


def _public(declared: dict[str, Any]) -> None:
    declared["entries"].append({"path": "sources.jsonl", "kind": "sources"})
    declared["links"] = [{"source": e["path"], "target": "sources.jsonl", "relation": "data_of"}
                         for e in declared["entries"] if e["kind"] in ("scores", "outcomes")]


def public_pack(root: Path) -> Path:
    """The small outcome pack, declared again with a public source so the server opens it."""
    source = Source(uri="hf://psi-data", sha256=SHA, downloaded_at="2026-11-01",
                    data_class="public").model_dump_json() + "\n"
    return repacked(small_pack(root / "raw"), "public", _public, {"sources.jsonl": source})


def floor_run(pack: Path, out: Path, store: Path) -> Path:
    """A no-model run of `pack` into `out` (the code floor)."""
    run_round(pack, out, now=NOW, store=store, no_model=True)
    return out


def model_run(pack: Path, out: Path, store: Path) -> Path:
    """A model run of `pack` into `out`, the rank role answered by the fake `Bot`."""
    run_round(pack, out, now=NOW, store=store, no_model=False, gateway_factory=factory_of(Bot()))
    return out


def hashes(directory: Path) -> dict[str, str]:
    """Relative path -> sha256 of every file under `directory`."""
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*")) if p.is_file()}
