"""The version and the content hash of the agent's configuration (architecture section 11)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

AGENT_CONFIG = Path("configs") / "eval" / "agentqa" / "agent.yaml"  # from the repo root
CONFIG_ROOT = Path("configs") / "eval" / "agentqa"


def agent_version(config: Path = AGENT_CONFIG) -> str:
    """The `version` value of the agent config as text; "" when there is none."""
    raw = yaml.safe_load(config.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") is None:
        return ""
    return str(raw["version"])


def agent_hash(task_id: str, plan: Path | None = None, root: Path = CONFIG_ROOT) -> str:
    """sha256 over the (name, file sha256) pairs of what decides a round's verdict.

    The task view of `task_id`, the plan actually used (`plan`, by default the task's plan
    under `root`), every rule file, the check catalog, the cost keys and the model
    gateway's `routing.yaml` and `hosted.yaml` (architecture section 11; the hosted file
    holds key variable names, never keys), `agent.yaml` (model, revision and endpoint of
    the local models) and `../diagnosis/system.yaml` (the tau_track values `trace_stats`
    reads). A file that does not exist is skipped.
    """
    plan = plan if plan is not None else root / "plans" / f"{task_id}.yaml"
    files = [root / "tasks" / f"{task_id}.yaml", *sorted((root / "rules").glob("*.yaml")),
             root / "checks.yaml", root / "costs.yaml", root / "routing.yaml",
             root / "hosted.yaml", root / "agent.yaml", root.parent / "diagnosis" / "system.yaml"]
    pairs = sorted((f.relative_to(root.parent).as_posix(),
                    hashlib.sha256(f.read_bytes()).hexdigest()) for f in files if f.is_file())
    if plan.is_file():
        pairs.append(("plan", hashlib.sha256(plan.read_bytes()).hexdigest()))
    return hashlib.sha256("\n".join(f"{p} {h}" for p, h in pairs).encode()).hexdigest()
