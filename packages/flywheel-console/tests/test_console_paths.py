from pathlib import Path

import pytest
from flywheel.console.paths import ConsolePaths, PathDenied, deid_only, guard


def test_from_env_fw_root_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FW_ROOT", str(tmp_path))
    p = ConsolePaths.from_env(repo=tmp_path)
    assert p.fw_root == tmp_path
    assert p.index == tmp_path / "console" / "index"
    assert p.web.name == "web" and p.seed.name == "seed"


def test_guard_ok(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("x")
    assert guard(f, [tmp_path]) == f.resolve()


def test_guard_rejects_vault(tmp_path: Path) -> None:
    (tmp_path / "vault").mkdir()
    with pytest.raises(PathDenied):
        guard(tmp_path / "vault" / "x", [tmp_path])


def test_guard_rejects_holdout(tmp_path: Path) -> None:
    with pytest.raises(PathDenied):
        guard(tmp_path / "my_holdout_set" / "x", [tmp_path])


def test_guard_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside)
    with pytest.raises(PathDenied):
        guard(root / "link" / "f", [root])


def test_guard_rejects_dotdot(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(PathDenied):
        guard(root / ".." / "x", [root])


def test_deid_only() -> None:
    assert deid_only(Path("a.deid.mp4")) == Path("a.deid.mp4")
    with pytest.raises(PathDenied):
        deid_only(Path("a.mp4"))


def test_guard_rejects_vault_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "Vault").mkdir()
    with pytest.raises(PathDenied):
        guard(tmp_path / "Vault" / "x", [tmp_path])


def test_from_env_resolves_relative_fw_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "rel").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FW_ROOT", "rel")
    assert ConsolePaths.from_env(repo=tmp_path).fw_root == (tmp_path / "rel").resolve()
