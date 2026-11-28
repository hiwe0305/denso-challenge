import re
from pathlib import Path

from flywheel.console import budget

WEB = Path(budget.__file__).parent / "web"
HEX6 = re.compile(r"#[0-9a-fA-F]{6}\b")
REQUIRED_TOKENS = (
    "--bg:",
    "--surface:",
    "--surface-muted:",
    "--text:",
    "--text-muted:",
    "--border:",
    "--accent:",
    "--success:",
    "--warning:",
    "--danger:",
    "--info:",
)


def _clean_inline_markdown_mirror(raw: str | None) -> str:
    """Reference mirror of core.js cleanInlineMarkdown for deterministic unit assertions."""
    if raw is None:
        return ""
    lines: list[str] = []
    for line in str(raw).split("\n"):
        s = line.replace("**", "").replace("`", "")
        s = re.sub(r"^\s*\|\s*", "", s)
        s = re.sub(r"\s*\|\s*$", "", s)
        s = re.sub(r"\s*\|\s*", " · ", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        if s:
            lines.append(s)
    return "\n".join(lines)


def test_clean_inline_markdown_function_and_quote_usage() -> None:
    core = (WEB / "core.js").read_text(encoding="utf-8")
    assert "export function cleanInlineMarkdown(" in core
    assert "const cleanedQuote = cleanInlineMarkdown(quote);" in core
    assert "innerHTML" not in core
    assert (
        _clean_inline_markdown_mirror("| Train lần 1 (dừng sớm) | 8,55 |")
        == "Train lần 1 (dừng sớm) · 8,55"
    )
    assert (
        _clean_inline_markdown_mirror("| **Tổng serve** | **khoảng 23,4**, so với 16,2 ước tính |")
        == "Tổng serve · khoảng 23,4, so với 16,2 ước tính"
    )
    assert (
        _clean_inline_markdown_mirror("**H1: chuỗi bước gãy ở `approach_a`.** CHƯA RÕ")
        == "H1: chuỗi bước gãy ở approach_a. CHƯA RÕ"
    )


def test_chat_defaults_closed_and_deduplicates_requests() -> None:
    core = (WEB / "core.js").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    chat = (WEB / "chat.js").read_text(encoding="utf-8")
    # Q3 / design P0-8 (28/11/2026): closed until the reader opens it, never auto-opened.
    assert "chatOpen: explicitChatPref !== null ? explicitChatPref : false," in core
    assert "window.innerWidth >= 1220" not in core + app
    assert "export async function ensureModels(" in core
    assert "if (!state.chatOpen) return;" in chat
    assert "toolsCache.has(" in chat


def test_diagnose_reads_english_cluster_words() -> None:
    # story.round.clusters / story.diag.clusters carry diagnosis_en, intervention_en (28/11)
    story = (WEB / "pages_story.js").read_text(encoding="utf-8")
    assert 'clusterText(c, "diagnosis")' in story
    assert 'clusterText(c, "intervention")' in story
    assert 'field + "_en"' in story


def test_place_rule_met_reading_uses_the_common_wording() -> None:
    # Rule 3 (place step) reads "Dat moc {pct}" like rules 1-2 (approved N4 wording, 28/11)
    for name in ("pages_story.js", "core.js", "i18n/vi.js", "i18n/en.js"):
        text = (WEB / name).read_text(encoding="utf-8")
        assert "exp.verdictPlaceMet" not in text, name
    assert '"exp.verdictMet": "Đạt mốc {pct}"' in (WEB / "i18n/vi.js").read_text(encoding="utf-8")
    assert '"exp.verdictMet": "Meets the {pct} target"' in (WEB / "i18n/en.js").read_text(
        encoding="utf-8"
    )


def test_default_round_and_round_links() -> None:
    # Hiếu 28/11 evening: open on tasks[].default_round, link the rounds both ways
    core = (WEB / "core.js").read_text(encoding="utf-8")
    assert "task.default_round" in core
    assert 'ROUND_PICK_KEY = "fw_round_pick"' in core
    # only an explicit pick is remembered; the old auto-saved key is not read any more
    assert 'readSession("fw_round")' not in core
    assert core.count("rememberSelection({ roundPicked: true })") == 2
    assert "export function renderRoundLinks" in core and "export function renderTimeline" in core
    # carried / placed come as bare numbers out of the link's n (index PR #266)
    assert "linkCount(L.carried, L.n)" in core and "linkCount(L.placed, L.n)" in core
    ops = (WEB / "pages_ops.js").read_text(encoding="utf-8")
    assert "renderRoundLinks(curRound)" in ops and "renderTimeline(state.storyRawDoc)" in ops
    for lang in ("vi", "en"):
        text = (WEB / "i18n" / f"{lang}.js").read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if '"round.link' in ln or '"home.timeline' in ln]
        assert len(lines) >= 8, lang
        # side by side only, never "better" or "+X points" (tray-jig.md §2, rule 4)
        for ln in lines:
            assert not re.search(r"tốt hơn|tăng|better|improv|\+\d", ln, re.I), ln


def test_no_hex_in_pages() -> None:
    pages = sorted(WEB.glob("pages_*.js"))
    assert pages, "expected pages_*.js modules in web/"
    for f in pages:
        assert not HEX6.search(f.read_text(encoding="utf-8")), f"hex colour literal in {f.name}"


def test_no_cdn_or_external_fonts() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "style.css").read_text(encoding="utf-8")
    assert not re.search(r"""(?:src|href)\s*=\s*["']https?://""", html)
    assert not re.search(r"""url\(\s*["']?https?://""", css)
    assert "@import" not in css
    assert (WEB / "vendor" / "echarts.min.js").is_file()


def test_light_and_dark_theme_tokens() -> None:
    css = (WEB / "style.css").read_text(encoding="utf-8")
    light = css.split(':root[data-theme="light"]', 1)[1].split("}", 1)[0]
    dark = css.split(':root[data-theme="dark"]', 1)[1].split("}", 1)[0]
    for tok in REQUIRED_TOKENS:
        assert tok in light, f"missing {tok} in light theme"
        assert tok in dark, f"missing {tok} in dark theme"
    for i in range(1, 9):
        assert f"--s{i}:" in light
        assert f"--s{i}:" in dark


def test_ego_strip_wired_in_data_pages() -> None:
    src = (WEB / "pages_data.js").read_text(encoding="utf-8")
    assert "/api/ego_strip" in src
    assert "/api/poster" in src


def test_pipeline_runners_come_from_kinds_endpoint() -> None:
    ops = (WEB / "pages_ops.js").read_text(encoding="utf-8")
    core = (WEB / "core.js").read_text(encoding="utf-8")
    assert 'getJSON("/api/kinds")' in core
    assert 'postJSON("/api/jobs"' in ops
    assert not re.search(r'kind:\s*"(?:data|eval|ego|agentqa)\.', ops)


def test_loop_numbers_come_from_story_not_literals() -> None:
    code = re.compile(r"""(?<![\w.])(?<!W = )(?:262|229|177|160|240)(?![\w.])|131/240""")
    text = (WEB / "pages_story.js").read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))
    hits = [m.group(0) for m in code.finditer(text)]
    assert not hits, f"pages_story.js: hard-coded loop numbers {hits}"


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


def test_no_round_ids_seed_or_step_count_in_web() -> None:
    """Run ids, follow seed and step count live in seed/tasks.yaml, not in web JS or i18n."""
    typed = re.compile(r"\b(?:C_70|C70_R1|C_ALL|B_ALL|B_70|1000107|60000|60_000)\b")
    for f in sorted(WEB.glob("*.js")) + sorted((WEB / "i18n").glob("*.js")):
        text = re.sub(r"/\*.*?\*/", "", f.read_text(encoding="utf-8"), flags=re.S)
        text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))
        hits = sorted({m.group(0) for m in typed.finditer(text)})
        assert not hits, f"{f.name}: typed round facts {hits}; read them from data/tasks.json"


def test_shared_api_client_surfaces_errors_and_respects_lock() -> None:
    core = (WEB / "core.js").read_text(encoding="utf-8")
    assert "export async function getJSON(" in core
    assert "export async function postJSON(" in core
    assert "payload.error" in core
    assert "showErrorBanner" in core
    assert "filterWithheldStory" in core
    assert '"/api/chat"' in core and '"/api/models/prewarm"' in core

    app = (WEB / "app.js").read_text(encoding="utf-8")
    assert 'getJSON("/api/status"' in app
    assert 'getJSON("data/tasks.json"' in app


def test_lock_mode_guards_chat_traces() -> None:
    chat = (WEB / "chat.js").read_text(encoding="utf-8")
    body = chat.split("async function loadChatDiagnostics", 1)[1]
    assert body.index("if (!state.locked)") < body.index('tryGetJSON("/api/chat/traces')


def test_only_contract_endpoints_used() -> None:
    allowed_prefixes = (
        "/api/",
        "data/",
        "/media/",
        "/simmedia/",
        "/demomedia/",
        "/ego/",
    )
    url_pat = re.compile(r"""["`']((?:/api/|data/|https?://)[^"`'$]*)["`']""")
    for f in sorted(WEB.glob("*.js")):
        src = f.read_text(encoding="utf-8")
        for m in url_pat.finditer(src):
            u = m.group(1)
            if u == "http://www.w3.org/2000/svg":
                continue  # XML namespace of inline SVG icons (icons.js), never fetched
            assert not u.startswith(("http://", "https://")), f"external URL in {f.name}: {u}"
            assert u.startswith(allowed_prefixes), f"non-contract URL in {f.name}: {u}"


def test_lock_mode_hides_no_navigation_shell() -> None:
    css = (WEB / "style.css").read_text(encoding="utf-8")
    forbidden = (
        "html.locked #chat-panel",
        "html.locked #task-select",
        "html.locked #round-select",
        "html.locked #sidebar",
    )
    for sel in forbidden:
        assert sel not in css, sel


def _code(name: str) -> str:
    """A web module without its comments."""
    text = re.sub(r"/\*.*?\*/", "", (WEB / name).read_text(encoding="utf-8"), flags=re.S)
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//"))


def _function(name: str, fn: str) -> str:
    """The source of ``export function fn`` in a web module, up to the next top-level function."""
    text = _code(name)
    start = text.index(f"function {fn}(")
    nxt = re.search(r"\n(?:export )?function \w+\(", text[start + 1 :])
    return text[start : start + 1 + nxt.start()] if nxt else text[start:]


def test_jig_pages_have_no_threshold_literals() -> None:
    """DA-53 2.4: the rule thresholds come from story.jig readings (seed/tasks.yaml), not JS."""
    lit = re.compile(r"(?<![\w.])0\.[578](?!\d)")
    for name in ("pages_story.js", "pages_ops.js", "core.js"):
        hits = lit.findall(_code(name))
        assert not hits, f"{name}: threshold literals {hits}"


def test_train_page_reads_jig_runs_when_story_runs_is_out_of_scope() -> None:
    src = _function("pages_story.js", "renderRunsPage")
    assert 'hasIndexAccess("story.runs")' in src and 'hasIndexAccess("story.jig")' in src
    assert "const src = topScope ? story : jigDoc;" in src
    for key in ("src.runs", "src.train_log_tail", "src.vm_phases", "jigDoc.log_run"):
        assert key in src, key
    # the old campaign chips and the jig banner are gone
    assert "campFilter" not in src and "runsJigBanner" not in src
    assert 'fetched_final === false && matched.fetched_train !== "done"' in src


def test_eval_page_renders_readings_from_the_jig_block() -> None:
    src = _function("pages_story.js", "renderEvalPage")
    assert "jig.evals" in src and "ev.readings" in src and "jig.outcomes" in src
    for code in ('rd.verdict === "met"', 'rd.verdict === "not_met"', 'rd.why === "blocked"'):
        assert code in src, code
    assert 'status === "missing"' in src and "ev.command" in src
    assert "jig.runs" not in src  # train entries, never eval rows
    assert "paired" not in src


def test_no_old_jig_keys_or_hidden_run_text_in_web() -> None:
    """``jig.best`` and eval rows in ``jig.runs`` are gone (DA-53); run N is never presented."""
    files = sorted(WEB.glob("*.js")) + sorted((WEB / "i18n").glob("*.js"))
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"\bjig\w*\.best\b", text), f.name
        for needle in ("N.tar", "run N", "da50", "jig-n", "next_cut", "n_ckpt_done"):
            assert needle not in text, (f.name, needle)


def test_withhold_filter_covers_the_jig_block() -> None:
    src = _function("core.js", "filterWithheldStory")
    assert "out.jig" in src
    for key in ("evals", "outcomes", "rollouts", "conditions", "compare60", "featured"):
        assert f"out.jig.{key}" in src or f"nextJig.{key}" in src, key


def test_reasoning_block_shows_steps_and_never_the_thinking() -> None:
    """'Quá trình suy luận' under each chat answer (Hiếu 28/11): saved steps only, open while
    the answer streams."""
    src = (WEB / "pages_chat.js").read_text(encoding="utf-8")
    block = src[src.index("const renderReasoning") : src.index("const renderStudioTurn")]
    assert "tr.steps" in block and "chatToolLabel(st.name)" in block and "stepRows(st.ui)" in block
    assert "choice === undefined ? isRunning : choice" in block
    for needle in ("tr.thinking", "system", "/api/chat/traces"):
        assert needle not in block, needle
    assert 'reason !== "theme"' in src and "ResizeObserver" in src and "resizeChatCharts" in src


def test_compare60_ladder_is_descriptive_and_filtered() -> None:
    """The 60-rollout ladder on the eval page: counts only, no winner wording or colour scale."""
    src = (WEB / "pages_story.js").read_text(encoding="utf-8")
    start = src.index("export function compare60Ladder")
    ladder = src[start : src.index("// Numbers inside a preformatted")]
    assert "getRoundsForTask" in ladder and "visualMap" not in ladder
    for lang in ("vi", "en"):
        lines = [
            ln
            for ln in (WEB / "i18n" / f"{lang}.js").read_text(encoding="utf-8").splitlines()
            if '"exp.ladder' in ln
        ]
        assert len(lines) >= 15
        for ln in lines:
            assert not re.search(r"tốt hơn|cao hơn|tăng|better|higher|improv|\+\d", ln), ln
    assert "keepLadder" in _function("core.js", "filterWithheldStory")
