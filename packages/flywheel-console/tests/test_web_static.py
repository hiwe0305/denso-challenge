import re
from pathlib import Path

from flywheel.console import budget

WEB = Path(budget.__file__).parent / "web"
HEX6 = re.compile(r"#[0-9a-fA-F]{6}\b")


def test_no_hex_in_pages() -> None:
    for f in sorted(WEB.glob("pages_*.js")):
        assert not HEX6.search(f.read_text(encoding="utf-8")), f"hex colour literal in {f.name}"


def test_no_cdn() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"""(?:src|href)\s*=\s*["']https?://""", html)
    assert (WEB / "vendor" / "echarts.min.js").is_file()


def test_ego_strip_wired() -> None:
    for name in ("pages_data.js", "pages_ops.js"):
        assert "/api/ego_strip" in (WEB / name).read_text(encoding="utf-8"), name


def test_light_theme_series_tokens() -> None:
    css = (WEB / "style.css").read_text(encoding="utf-8")
    light = css.split(':root[data-theme="light"]', 1)[1].split("}", 1)[0]
    for i in range(1, 9):
        assert f"--s{i}:" in light


def test_sankey_labels_carry_numbers() -> None:
    for name in ("pages_data.js", "pages_story.js"):
        src = (WEB / name).read_text(encoding="utf-8")
        assert 'type: "sankey"' in src
        assert re.search(r"nodeGap: (\d{2,})", src), name


def test_story_sankey_labels_alternate_by_column() -> None:
    """Neighbouring columns put labels on opposite sides; index parity did not (DA-40/8)."""
    src = (WEB / "pages_story.js").read_text(encoding="utf-8")
    assert "const CHAIN = {" in src and "CHAIN[n.name] % 2" in src
    assert "i % 2 ?" not in src


def test_episode_bracket_keys_go_through_ui_keys() -> None:
    """A raw keydown listener for [ ran alongside the global sidebar toggle (DA-40/8)."""
    src = (WEB / "pages_data.js").read_text(encoding="utf-8")
    assert 'UI.keys.bind({ "[":' in src
    assert 'ev.key === "["' not in src


def test_no_machine_paths_in_package() -> None:
    root = Path(budget.__file__).parent
    bad: list[str] = []
    for f in root.rglob("*"):
        if not f.is_file() or "vendor" in f.parts or f.suffix not in {
            ".py", ".js", ".yaml", ".yml", ".html", ".css", ".json", ".jsonl",
        }:  # fmt: skip
            continue
        text = f.read_text(encoding="utf-8")
        if "/home/" in text or "/Users/" in text:
            bad.append(str(f.relative_to(root)))
    assert not bad, bad


def test_episode_page_maps_404_to_empty_state() -> None:
    src = (WEB / "pages_data.js").read_text(encoding="utf-8")
    assert '/ 404$/.test(e.message) ? "no data"' in src


def test_loop_numbers_come_from_story_not_literals() -> None:
    code = re.compile(r"""(?<![\w.])(?<!W = )(?:262|229|177|160|240)(?![\w.])|131/240""")
    for name in ("pages_story.js", "ring.js"):
        text = (WEB / name).read_text(encoding="utf-8")
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))
        hits = [m.group(0) for m in code.finditer(text)]
        assert not hits, f"{name}: hard-coded loop numbers {hits}"
