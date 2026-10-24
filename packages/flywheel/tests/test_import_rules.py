"""Regression tests for the core package import boundary."""

from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_ROOTS = {
    "flywheel_lerobot",
    "flywheel_psi0",
    "flywheel_simple",
    "isaacsim",
    "lerobot",
    "mujoco",
    "psi0",
    "simple",
    "torch",
}


def find_forbidden_imports(source_root: Path) -> list[str]:
    """Return stable file/module descriptions for forbidden imports."""
    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if module.split(".", maxsplit=1)[0] in FORBIDDEN_ROOTS:
                    violations.append(f"{path.relative_to(source_root)}:{node.lineno}:{module}")
    return violations


def test_flywheel_has_no_forbidden_imports() -> None:
    source_root = Path(__file__).parents[1] / "src" / "flywheel"

    assert find_forbidden_imports(source_root) == []


def test_guard_rejects_an_intentional_torch_import(tmp_path: Path) -> None:
    module = tmp_path / "bad_module.py"
    module.write_text("import torch\n", encoding="utf-8")

    assert find_forbidden_imports(tmp_path) == ["bad_module.py:1:torch"]
