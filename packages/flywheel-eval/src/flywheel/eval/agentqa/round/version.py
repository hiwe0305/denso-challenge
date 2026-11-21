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


def agent_hash(task_id: str, root: Path = CONFIG_ROOT) -> str:
    """sha256 over the (relative path, file sha256) pairs of what decides a round's verdict.

    The task view and the plan of `task_id`, every rule file, the check catalog and the cost keys; a
    file that does not exist is skipped.
    """
    files = [root / "tasks" / f"{task_id}.yaml", root / "plans" / f"{task_id}.yaml",
             *sorted((root / "rules").glob("*.yaml")), root / "checks.yaml", root / "costs.yaml"]
    pairs = sorted((f.relative_to(root).as_posix(), hashlib.sha256(f.read_bytes()).hexdigest())
                   for f in files if f.is_file())
    return hashlib.sha256("\n".join(f"{p} {h}" for p, h in pairs).encode()).hexdigest()
