# Flywheel core

`flywheel` is the CPU-only core of the DENSO Humanoid Data Flywheel. Heavy adapters
for SIMPLE, Ψ₀, LeRobot, Isaac Sim, and MuJoCo run in separate environments and
communicate with this package through contracts and job files.

## Set up and verify

From the repository root:

```bash
uv sync
uv run fw --version
uv run ruff check
uv run mypy packages/flywheel/src
uv run pytest
uv run lint-imports
```

Install the optional Rerun tooling for the HD experiment with:

```bash
uv sync --all-packages --all-extras
```

The complete Definition of Done is in
[`docs/product/04-delivery-plan.md` section 5](../../docs/product/04-delivery-plan.md#5-định-nghĩa-sẵn-sàng-và-hoàn-thành).

## Branches and pull requests

Use one branch, worktree, and pull request per story. Name a story branch
`<story-id>-<short-description>` and a pull request `[<story-id>] <title>`. Each
subtask is a separate commit whose message includes its acceptance evidence and
the contributor's actual `Time-spent`. Run `scripts/pr_guard.py` before opening a
pull request. Do not push directly to `master`.
