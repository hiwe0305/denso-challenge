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


def agent_hash(task_id: str, plan: Path | None = None, root: Path = CONFIG_ROOT,
               gateway_root: Path | None = None) -> str:
    """sha256 over the (name, file sha256) pairs of what decides a round's verdict.

    The task view of `task_id`, the plan actually used (`plan`, by default the task's plan
    under `root`), every rule file, the check catalog, the cost keys and the model
    gateway's `routing.yaml` and `hosted.yaml` (architecture section 11; the hosted file
    holds key variable names, never keys), `agent.yaml` (model, revision and endpoint of
    the local models, and the limits and prompt file of the adjudicate role),
    `../diagnosis/system.yaml` (the tau_track values `trace_stats` reads, R1 and R2),
    `../diagnosis/train.yaml` (T1-T8, which the adjudicate role's train subjects run),
    the model roles' limits `roles.yaml` and every prompt `prompts/*.md` (rank, and
    version 3's `system.md` the adjudicate role sends). A file that does not exist is
    skipped.

    `gateway_root` is the directory the gateway read `routing.yaml` and `hosted.yaml`
    from; by default (or when it is `root`) the hash is the one of `root` alone.
    """
    plan = plan if plan is not None else root / "plans" / f"{task_id}.yaml"
    gateway = gateway_root is not None and gateway_root.resolve() != root.resolve()
    files = [root / "tasks" / f"{task_id}.yaml", *sorted((root / "rules").glob("*.yaml")),
             root / "checks.yaml", root / "costs.yaml",
             *([] if gateway else [root / "routing.yaml", root / "hosted.yaml"]),
             root / "agent.yaml", root.parent / "diagnosis" / "system.yaml",
             root.parent / "diagnosis" / "train.yaml", root / "roles.yaml",
             *sorted((root / "prompts").glob("*.md"))]
    pairs = sorted((f.relative_to(root.parent).as_posix(),
                    hashlib.sha256(f.read_bytes()).hexdigest()) for f in files if f.is_file())
    if gateway_root is not None and gateway:
        pairs += sorted((f"gateway/{name}", hashlib.sha256(path.read_bytes()).hexdigest())
                        for name in ("routing.yaml", "hosted.yaml")
                        if (path := gateway_root / name).is_file())
    if plan.is_file():
        pairs.append(("plan", hashlib.sha256(plan.read_bytes()).hexdigest()))
    return hashlib.sha256("\n".join(f"{p} {h}" for p, h in pairs).encode()).hexdigest()
