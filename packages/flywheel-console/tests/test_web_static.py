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
    for name in ("pages_story.js",):
        text = (WEB / name).read_text(encoding="utf-8")
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))
        hits = [m.group(0) for m in code.finditer(text)]
        assert not hits, f"{name}: hard-coded loop numbers {hits}"


def test_no_round_ids_seed_or_step_count_in_web() -> None:
    """Run ids, follow seed and step count live in seed/tasks.yaml (read through TASK, core.js)."""
    typed = re.compile(r"\b(?:C_70|C70_R1|C_ALL|B_ALL|B_70|1000107|60000|60_000)\b")
    for f in sorted(WEB.glob("*.js")) + sorted((WEB / "i18n").glob("*.js")):
        text = re.sub(r"/\*.*?\*/", "", f.read_text(encoding="utf-8"), flags=re.S)
        text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))
        hits = sorted({m.group(0) for m in typed.finditer(text)})
        assert not hits, f"{f.name}: typed round facts {hits}; read them from TASK"


def test_dead_demo_files_and_run_tables_are_gone() -> None:
    """Brief 2 · T2: v4 ring, caption tour and the 40k C/C+ tables (dead code naming runs)."""
    for name in ("ring.js", "tour.js", "tour.css"):
        assert not (WEB / name).exists(), name
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert "ring.js" not in html and "tour.js" not in html and "pages_proc.js" in html
    story = (WEB / "pages_story.js").read_text(encoding="utf-8")
    assert "STATIC_RUNS" not in story and '"C+"' not in story


def test_try_panels_come_from_the_kinds_endpoint() -> None:
    """Chạy thử lists what /api/kinds returns; no kind or sample list is typed in the page."""
    src = (WEB / "pages_proc.js").read_text(encoding="utf-8")
    assert 'fetch("/api/kinds")' in src
    assert '"/api/jobs", { method: "POST"' in src
    assert not re.search(r'kind: "(?:data|eval|ego|agentqa)\.', src)


def test_lock_mode_sends_no_refused_requests() -> None:
    """A locked server answers 403 to /api/chat/traces: the QA page and the chat must not ask."""
    story = (WEB / "pages_story.js").read_text(encoding="utf-8")
    assert 'UI.locked ? Promise.resolve(null) : tryApi("/api/chat/traces' in story
    chat = (WEB / "chat.js").read_text(encoding="utf-8")
    body = chat.split("async function showTraces()", 1)[1]
    assert body.index("if (UI.locked)") < body.index('fetch("/api/chat/traces')


def test_lock_mode_hides_nothing() -> None:
    """Lock mode is read-only, not another site: no rule hides side groups, panel or selectors."""
    css = (WEB / "style.css").read_text(encoding="utf-8")
    hidden = (
        "html.locked #rp",
        "html.locked #task",
        "html.locked #side .sg.ops",
        "html.locked #srch",
    )
    for sel in hidden:
        assert sel not in css, sel
