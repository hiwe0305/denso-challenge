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
