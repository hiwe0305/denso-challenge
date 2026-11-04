"""scripts/repo/pr_guard.py against a throwaway git repository.

Regression for PR #91: GitHub kept `pull_request.base.sha` on an old ancestor of master
after the branch was rebased, so master's newer commits and files were judged as the PR's.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "repo"))

import pr_guard  # noqa: E402
import storylib  # noqa: E402

STORY = """# DA-99 · Test story

## Phạm vi file

- `pkg/`

## Nhiệm vụ

- [ ] 1.1 Add thing
"""


def _git(root: Path, *args: str) -> str:
    identity = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
    return subprocess.run(
        ["git", *identity, *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(root: Path, path: str, text: str, message: str) -> str:
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(text, encoding="utf-8")
    _git(root, "add", path)
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def rebased(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """master: stale -> other; branch DA-99-thing rebased on `other` with one own commit."""
    _git(tmp_path, "init", "-q", "-b", "master")
    stale = _commit(tmp_path, "docs/product/stories/DA-99-thing.md", STORY, "chore: Add story")
    _commit(tmp_path, "other/tool.py", "x = 1\n", "chore: Land another PR on master")
    _git(tmp_path, "checkout", "-q", "-b", "DA-99-thing")
    head = _commit(tmp_path, "pkg/a.py", "a = 1\nb = 2\n", "DA-99/1.1: Add thing\n\nTime-spent: 1h")
    monkeypatch.setattr(pr_guard, "ROOT", tmp_path)
    monkeypatch.setattr(storylib, "ROOT", tmp_path)
    monkeypatch.setattr(storylib, "STORIES", tmp_path / "docs" / "product" / "stories")
    return {"stale": stale, "head": head}


def test_current_base_tip_checks_only_the_branch_commits(rebased: dict[str, str]) -> None:
    errors, warnings, size = pr_guard.check("master", rebased["head"], "DA-99-thing")
    assert (errors, warnings, size) == ([], [], 2)


def test_stale_base_counts_master_commits_as_the_pr(rebased: dict[str, str]) -> None:
    errors, _, size = pr_guard.check(rebased["stale"], rebased["head"], "DA-99-thing")
    assert any("chore: Land another PR on master" in error for error in errors)
    assert any("`other/tool.py`" in error for error in errors)
    assert size == 3


def test_workflow_passes_the_base_branch_tip() -> None:
    workflow = (REPO / ".github" / "workflows" / "pr-guard.yml").read_text(encoding="utf-8")
    assert "pull_request.base.sha" not in workflow
    assert "origin/${{ github.base_ref }}" in workflow
    assert '--base "$BASE_REF"' in workflow
