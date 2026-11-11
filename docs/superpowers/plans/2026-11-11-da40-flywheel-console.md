# DA-40 Flywheel Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the v5 Flywheel Console prototype into the repo as the package `flywheel-console`, with an indexer that rebuilds all console data from `fwdata/`, the `fw console index|serve|bench` commands, CPU tests, and the four open gaps of BA 15.1b fixed.

**Architecture:** A uv workspace package `packages/flywheel-console` (module `flywheel.console`, typer app registered on `flywheel.commands`). `flywheel.console.index` turns `fwdata/` + a seed catalog + cited numbers into JSON under `$FW_ROOT/console/index/` (same shapes as v5 `data/`). `flywheel.console.server` is the v5 stdlib server, runner and media code, serving the vanilla-JS UI from `flywheel/console/web/` and the index at `/data/`. `flywheel.console.chat` is the v5 Nemotron chatbot and its tools. The console never imports lanes or adapters; it runs `fw` in a subprocess.

**Tech Stack:** Python 3.10 stdlib `http.server`, typer, pyyaml, numpy, pyarrow, opencv-python-headless; vanilla JS + vendored ECharts (no Node, no build).

**Spec:** BA `docs/superpowers/specs/2026-11-11-flywheel-console-design.md` v0.5 (PR #193, read it with `git show origin/docs-flywheel-console-ba:docs/superpowers/specs/2026-11-11-flywheel-console-design.md`), sections 11, 12, 15.1a, 15.1b, 17. Story: `docs/product/stories/DA-40-flywheel-console.md`. Prototype source: `.superpowers/brainstorm/mockups/v5/` in the worktree `/home/hiwe/project/denso-challenge/.claude/worktrees/denso-website-analysis-d49f4f` (untracked): `CONTRACTS.md` (routes, UI API, chat SSE, tools, guardrails), `DESIGN.md`, `MERGE.md`, the code, `data/` (reference output shapes) and `_gen/` (the three scripts that produced `data/`: `catalog_inventory.py` → `datasets.json`, `build_data.py` → `catalog.json` + `ds/*`, `build_story.py` → most of `story.json`; its `eval` block was hand-copied from `docs/he/tray.md` §16.6).

## Global Constraints

- Server binds `127.0.0.1` only. POST accepted only when `Host` and `Origin` are the console itself.
- Model endpoint is exactly `http://127.0.0.1:11435/v1` (SSH tunnel to Ollama on `rtx3060`); no hosted API, no fallback model.
- Never read `vault/` or any path containing `holdout`; egocentric frames only from `*.deid.mp4`.
- Writes only under `$FW_ROOT/console/` (index, cache, jobs, chat, config, exports, uploads); never into `configs/`, `docs/` or package dirs at runtime.
- Job runner accepts only `ego.ingest, ego.deid, ego.ea, ego.pose, ego.annotate, ego.qa, ego.report, ego.pipeline, ego.human1m, agentqa.run, agentqa.review, export.zip`; at most 2 concurrent laptop jobs; model-calling jobs run one at a time; no training or eval kinds.
- Chat caps per turn: 3 tool rounds, 20 s, `num_ctx` 16384, `keep_alive` 30m. QA pass/flag/reject comes only from rule-layer files.
- No absolute `/home/...` path in code or seed; every path comes from `ConsolePaths`.
- `flywheel.console` imports no `flywheel.data`, `flywheel.eval`, `flywheel.loop`, `flywheel.cli`, `flywheel_simple`, `flywheel_psi0`, `torch`, `mujoco`, `lerobot`, `isaacsim`.
- Python ≥ 3.10, ruff line length 100, mypy `strict = true` on the whole package (no blanket `ignore_errors`).
- UI: labels ≤ 3 words, no static text node > 8 words (word budget), every page opens with a visual, no CDN.
- Code, comments, commits in English. Never commit `fwdata/`, v5 `data/`, v5 `cache/`.
- Subagents do not commit and do not edit the story file; the lead reviews each task, ticks the story box and commits `DA-40/<n>: ...` with `Time-spent`.

## Review Focus

1. **Missing data on this laptop** (rtx3060-only sets, no pair60k metrics, empty `fwdata/`): index still builds, rows marked `rtx3060 only` / `missing`, pages show empty states. Test `test_build_all_on_empty_fw_root` in Task 4.
2. **Path tricks** (`/data/../`, `%2e%2e`, symlink out of `fwdata`, `vault/` inside `fwdata`, upload filename `../x.mp4`): 403/400. Tests `test_guard_*` in Task 1 and `test_static_traversal` in Task 5.
3. **Tunnel down or model cold**: chat stream emits `error` with `fallback: "slash"` within the 20 s cap, slash commands still work. Test `test_stream_endpoint_down` in Task 6.
4. **Large files** (`train.log` ~900 KB, `metrics.jsonl` ~6 MB): series down-sampled to ≤ 2 000 points, log tail by offset. Test `test_downsample_cap` in Task 4.
5. **Started from another cwd or with `FW_ROOT` set**: everything resolves through `ConsolePaths`. Test `test_from_env_fw_root_override` in Task 1.

---

### Task 1: Package skeleton, paths and guards, `fw console`

**Files:**
- Create: `packages/flywheel-console/pyproject.toml`, `README.md` (English, from v5 `CONTRACTS.md` + `DESIGN.md` merged and shortened), `src/flywheel/console/{__init__.py,py.typed,paths.py,cli.py}`
- Modify: root `pyproject.toml` (dependency, `tool.uv.sources`, `mypy_path`, mypy override `cv2` `ignore_missing_imports` if needed, import-linter contract), `uv.lock` (`uv lock`)
- Test: `packages/flywheel-console/tests/test_console_paths.py`, `tests/test_cli.py`

**Interfaces:**
- Produces (`flywheel.console.paths`):
  - `@dataclass(frozen=True) class ConsolePaths: repo: Path; fw_root: Path` with properties `console_dir = fw_root/"console"`, `index`, `cache`, `jobs`, `chat`, `config`, `exports`, `uploads` (all under `console_dir`), `web` (package `web/` dir), `seed` (package `seed/` dir).
  - `ConsolePaths.from_env(repo: Path | None = None) -> ConsolePaths`: `repo` defaults to the nearest parent of cwd whose `pyproject.toml` has `[tool.uv.workspace]`; `fw_root` = `$FW_ROOT` if set else `repo/"fwdata"`.
  - `set_active(p: ConsolePaths) -> None`, `active() -> ConsolePaths` (lazy `from_env()`); ported modules read paths only through `active()`.
  - `class PathDenied(ValueError)`; `guard(p: Path | str, roots: Sequence[Path]) -> Path` (resolve symlinks; must be under a root; any part equal to `vault` or containing `holdout` → `PathDenied`); `deid_only(p: Path) -> Path` (name must end `.deid.mp4`).
- Produces (`flywheel.console.cli`): `app = typer.Typer(no_args_is_help=True)` with commands `index [--only catalog,robot,ego,story]`, `serve [--port 4178]`, `bench [--tag TEXT]`; bodies call `flywheel.console.index.build_all`, `flywheel.console.server.app.serve`, `flywheel.console.chat.bench.run` (imported inside the command so Task 1 lands before them).
- Entry point: `[project.entry-points."flywheel.commands"] console = "flywheel.console.cli:app"`.

- [ ] **Step 1: Write failing tests** `test_from_env_fw_root_override` (monkeypatch `FW_ROOT=tmp_path` → `fw_root == tmp_path`, `index == tmp_path/"console"/"index"`), `test_guard_rejects_vault`, `test_guard_rejects_holdout`, `test_guard_rejects_symlink_escape`, `test_guard_rejects_dotdot`, `test_deid_only`, `test_fw_console_help` (typer `CliRunner` on `flywheel.cli.main` app shows `console`).
- [ ] **Step 2:** `uv run pytest packages/flywheel-console -q` → FAIL (module missing).
- [ ] **Step 3:** Create package and the code above; dependencies `typer`, `pyyaml`, `numpy`, `pyarrow`, `opencv-python-headless>=4.10`; add import-linter contract `name = "Console reads files, never lanes or adapters"`, `type = "forbidden"`, `source_modules = ["flywheel.console"]`, forbidden list from Global Constraints; run `uv lock`.
- [ ] **Step 4:** `uv run pytest packages/flywheel-console -q && uv run ruff check packages/flywheel-console && uv run mypy packages/flywheel-console && uv run lint-imports` → all pass.

### Task 2: Catalog index and cited numbers

**Files:**
- Create: `src/flywheel/console/seed/catalog.yaml`, `seed/cited.yaml`, `src/flywheel/console/index/{__init__.py (empty for now),catalog.py,cited.py}`
- Test: `tests/index/test_catalog.py`, `tests/index/test_cited.py`

**Interfaces:**
- Consumes: `ConsolePaths`, `guard`.
- Produces: `catalog.build(paths: ConsolePaths, out: Path) -> dict[str, int]` writes `out/"catalog.json"` = `{"generated", "rows", "edges", "runs"}` with row fields exactly as v5 `data/catalog.json` rows (read it for the shape). `cited.load(paths) -> list[Cited]` where `Cited` is a frozen dataclass `(key: str, value: Any, doc: str, section: str, quote: str)`; `cited.verify(paths) -> list[str]` returns the keys whose `quote` is not found in `paths.repo/doc`.
- Seed: `catalog.yaml` is `_gen/datasets.json` (60 rows) plus `TITLES` from `_gen/build_data.py`, as YAML; locations stay `laptop:fwdata/...`, `rtx3060:~/...` or URLs; add optional fields `lerobot: <fw-relative dir>` (S70, ALL from `build_data.py` `LR`), `ego_viewer: <fw-relative dir>` (h1m viewer from `EGO`), `aliases: [..]` (give the current S1 pool row alias `S1`, S70 `S70`, ALL `ALL`). Local presence is computed at build time (`exists` per location), not stored.
- Cited: `eval` block (levels L0/L1/L2/L1–2 with n, succ, Wilson CI, funnel, failure labels; copy the keys of v5 `story.json["eval"]`) from `docs/he/tray.md` §16.6, and the loop chain 240 → 131 → 262 → 229 → 177 from §16.6/§17 (`177 / 226 giữ lại` is in §17). Each value carries its quote.

- [ ] **Step 1: Failing tests:** `test_catalog_has_60_rows_and_edges` (build on `tmp_path` FW root: 60 rows, every edge endpoint is a row or run id), `test_catalog_marks_missing_locally` (empty FW root → every `laptop:` location `exists: false`), `test_aliases_resolve_s1` (row with alias `S1` exists and has `data_type == "synthetic"`), `test_cited_quotes_present_in_docs` (`cited.verify(ConsolePaths.from_env()) == []` against the real repo), `test_cited_eval_numbers` (`succ` of L1–2 is `20/240`, Wilson `5.5–12.5`).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement, porting the catalog section of `_gen/build_data.py` (lines ~103–180, 380–392).
- [ ] **Step 4:** pytest, ruff, mypy on the new files → pass.

### Task 3: Robot and egocentric dataset index, posters

**Files:**
- Create: `src/flywheel/console/index/{robot.py,egocentric.py,posters.py}`
- Test: `tests/index/test_robot.py`, `tests/index/test_egocentric.py`, `tests/index/test_posters.py`, `tests/conftest.py` (fixture builders)

**Interfaces:**
- Consumes: `ConsolePaths`, catalog rows with `lerobot` / `ego_viewer` (read `paths.seed/"catalog.yaml"` directly).
- Produces: `robot.build(paths, out) -> dict[str, int]` writes, for each seed row with a local `lerobot` dir, `out/ds/<row id>/{episodes.json, env.json, quality.json, method.json, posters/<i>.jpg}` in the v5 shapes; `egocentric.build(paths, out) -> dict[str, int]` does the same for `ego_viewer` rows and every `fwdata/pipeline/src_*` work dir (posters only from `*.deid.mp4`); `posters.poster_jpeg(video: Path, width: int = 320) -> bytes` (middle frame, JPEG q70) and `posters.strip_jpeg(video: Path, n: int = 8, height: int = 72) -> bytes` (horizontal strip of n evenly spaced frames). Both raise `FileNotFoundError` when the video is missing.
- Reuse of S70 posters for ALL (same cut, same mp4 size) as in `build_data.py`; use a `multiprocessing.Pool(6)` only when > 50 posters.

- [ ] **Step 1: Failing tests** with fixtures built in `tmp_path`: a 3-episode LeRobot v2.1 dir (`meta/info.json`, `meta/episodes.jsonl`, one parquet per episode via pyarrow, a 10-frame mp4 per episode via `cv2.VideoWriter`) and a pipeline work dir with one `ep_x/bundle.json` pointing at a `.deid.mp4` and one at a raw `.mp4`: `test_robot_episodes_shape` (3 rows; keys equal those of the first row of v5 `data/ds/S70/episodes.json`), `test_robot_posters_written`, `test_ego_poster_only_from_deid` (raw-mp4 episode gets no poster), `test_poster_jpeg_width`, `test_strip_jpeg_frame_count` (width ≈ n × frame width), `test_missing_video_raises`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement by porting `build_robot`, `build_quality_robot`, `method_robot`, `poster_job` and the ego section of `_gen/build_data.py`.
- [ ] **Step 4:** pytest, ruff, mypy → pass.

### Task 4: Story index (runs, eval, loop, cost) and `build_all`

**Files:**
- Create: `src/flywheel/console/index/story.py`; fill `src/flywheel/console/index/__init__.py`
- Test: `tests/index/test_story.py`, `tests/index/test_build_all.py`

**Interfaces:**
- Consumes: `catalog.build`, `robot.build`, `egocentric.build` (Tasks 2–3), `cited.load`.
- Produces: `story.build(paths, out) -> dict[str, int]` writes `out/"story.json"` with the keys of v5 `story.json` (`runs, train_log_tail, vm_phases, sources, heat, reasons, qa_sample, h1m, ledger, colab_balance, colab_sessions, ds, eval`), porting `_gen/build_story.py`; `eval` and the loop chain come from `cited.load`. `downsample(points: list[tuple[float, float]], cap: int = 2000) -> list[tuple[float, float]]` keeps first and last point.
- Produces: `build_all(paths: ConsolePaths, only: set[str] | None = None) -> dict[str, dict[str, int]]` runs `catalog`, `robot`, `ego`, `story` into a temp dir then atomically renames it to `paths.index` (old index kept until the new one is complete).

- [ ] **Step 1: Failing tests:** `test_downsample_cap` (100 000 points → ≤ 2 000, first and last kept), `test_story_keys`, `test_story_eval_from_cited`, `test_build_all_on_empty_fw_root` (writes `catalog.json`, `story.json`; no exception), `test_build_all_atomic` (an exception in `story.build` leaves the previous index untouched).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** pytest, ruff, mypy → pass; `FW_ROOT=<real fwdata> uv run fw console index` prints per-part counts (catalog 60 rows, S70 425 episodes).

### Task 5: Server, media, job runner

**Files:**
- Create: `src/flywheel/console/server/{__init__.py,app.py,media.py,runner.py}`
- Test: `tests/server/test_app.py`, `tests/server/test_runner.py`, `tests/server/test_media.py`

**Interfaces:**
- Consumes: `active()`, `guard`, `deid_only`, `posters.poster_jpeg/strip_jpeg`; `flywheel.console.chat.llm.stream(body: dict[str, Any]) -> Iterator[bytes]`, `chat.llm.nemotron_status() -> str`, `chat.llm.prewarm() -> dict[str, Any]`, `chat.llm.list_traces(limit: int) -> list[dict[str, Any]]`, `chat.llm.get_trace(turn_id: str) -> dict[str, Any] | None`, `chat.llm.latest_bench() -> dict[str, Any] | None`, `chat.registry.call(name: str, args: dict[str, Any], context: dict[str, Any] | None) -> dict[str, Any]`, `chat.registry.describe(route: str | None) -> list[dict[str, Any]]` (Task 6; import lazily inside handlers and test with monkeypatched stubs).
- Produces: `app.serve(paths: ConsolePaths, port: int = 4178) -> None`; every v5 route of `serve.py` keeps its path and JSON shape; `/` serves `paths.web`, `/data/*` serves `paths.index`, `/vendor/*` from `paths.web/"vendor"`. New: `GET /api/ego_strip?work=&ep=<episode_id>&n=8` → `strip_jpeg` of that episode's `*.deid.mp4`, 404 if none. `/api/poster` takes `ep=<episode_id>` (as fixed on 11/11). `runner.KINDS: frozenset[str]` (Global Constraints list); `runner.submit(kind: str, params: dict[str, Any]) -> dict[str, Any]` raises `ValueError` for other kinds; `runner.init(paths)`.
- Port `serve.py`, `runner.py`, and `tools.work_episodes/poster_jpeg/_deid_path/_work_dir` into `media.py`. Replace `FW`, `ROOT`, `HOME`, `HERE` constants with `active()`; keep `ssh` tunnel logic in `runner.Tunnel`.

- [ ] **Step 1: Failing tests** (start `ThreadingHTTPServer` on port 0 in a fixture with `FW_ROOT=tmp_path`): `test_binds_loopback`, `test_range_returns_206`, `test_static_traversal` (`/data/../pyproject.toml`, `/data/%2e%2e/x` → 403/404, never file content), `test_post_rejects_foreign_origin` (403), `test_poster_404_without_deid`, `test_ego_strip_from_deid`, `test_runner_rejects_unknown_kind`, `test_runner_two_concurrent_max` (third laptop job queued), `test_fs_denies_vault`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Port and implement.
- [ ] **Step 4:** pytest, ruff, mypy → pass.

### Task 6: Chatbot, tools, bench

**Files:**
- Create: `src/flywheel/console/chat/{__init__.py,llm.py,registry.py,resolve.py,tools_data.py,tools_runs.py,tools_ops.py,bench.py,bench.jsonl}`
- Test: `tests/chat/test_registry.py`, `tests/chat/test_guardrails.py`, `tests/chat/test_llm.py`

**Interfaces:**
- Consumes: `active()`, `guard`, `deid_only`, index files under `active().index`.
- Produces: the `chat.llm` and `chat.registry` functions listed in Task 5 Consumes, plus `bench.run(tag: str | None = None) -> dict[str, Any]` (writes `active().chat/"bench-<ts>.json"` with the v5 summary keys `n, tool_accuracy, arg_accuracy, guardrail_pass, no_tool_pass, grounded_numbers, latency_p50_s, latency_p95_s, by_group, markup_leaks`).
- Port `tools.py` split by page group: `resolve.py` (`_pick`, `resolve_dataset/run/job`, aliases from catalog rows), `tools_data.py` (catalog_search, dataset_stats, episode_list, episode_get, qa_summary, lineage), `tools_runs.py` (run_list, run_metrics, run_compare, log_tail, ledger_query, eval_summary, eval_failures, loop_proposals), `tools_ops.py` (job_list, job_get, findings, open_page, propose_job), `registry.py` (schemas, page_of, intent_tools, offered_names, context_defaults, call). Port `chat.py` to `llm.py`, `chat_bench.py` + `chat_bench.jsonl` to `bench.py` + `bench.jsonl`. `ENDPOINT` constant stays `http://127.0.0.1:11435`.
- Gap fixes: `resolve_dataset("S1")` returns the alias row (not candidates); `offered_names(route, question)` unions the tool sets of up to two pages when the question names two page topics (keyword map in `intent_tools`), still ≤ 7 + `open_page`.

- [ ] **Step 1: Failing tests:** `test_resolve_alias_s1`, `test_offered_names_cross_page` ("loss của C_70 và lỗi QA của S70" on route `runs` offers `run_metrics` and `qa_summary`), `test_offered_names_cap` (≤ 8), `test_tool_denies_vault_path`, `test_episode_frames_deid_only`, `test_qa_status_from_rule_layer` (S70 → 425 pass, `generation_failures` separate), `test_propose_job_starts_nothing` (returns `confirm` spec, runner untouched), `test_endpoint_is_loopback_tunnel`, `test_stream_endpoint_down` (no server on 11435 → events end with `error` carrying `fallback: "slash"` in < 20 s), `test_ground_marks_unknown_numbers`. Tests use a tiny index written in `tmp_path` (catalog with S70, S1 alias, one run).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Port and implement; add a bench item for the cross-page question above.
- [ ] **Step 4:** pytest, ruff, mypy → pass.

### Task 7: Web UI, open gaps, word budget

**Files:**
- Create: `src/flywheel/console/web/` (copy of v5 `index.html, style.css, core.js, app.js, chat.js, chat.css, tour.js, tour.css, ring.js, pages_data.js, pages_story.js, pages_ops.js, vendor/echarts.min.js`), `src/flywheel/console/budget.py` (port of `tools/word_budget.py`: `count(web: Path) -> dict[str, tuple[int, int]]` file → (words, budget)), `tests/test_budget.py`, `tests/test_web_static.py`

**Interfaces:**
- Consumes: routes and `/api/ego_strip` of Task 5 (no Python import).
- Produces: nothing other tasks import.
- Gap fixes:
  - **Light theme:** pages build ECharts options from `UI.colors()` only; the theme toggle re-renders the current route. No hex colour literals in `pages_*.js`.
  - **Sankey labels (Failure→Data):** no overlapping labels at 1 440 px: labels below nodes or alternating top/bottom, `nodeGap` ≥ 12, numbers in the label (`131 place-pose`).
  - **Ego filmstrip:** egocentric gallery items (`pages_data.js`) and pipeline thumbs (`pages_ops.js`) pass `strip: "/api/ego_strip?work=…&ep=…"`.

- [ ] **Step 1: Failing tests:** `test_word_budget_within_limits` (every file words ≤ budget), `test_no_hex_in_pages` (regex `#[0-9a-fA-F]{6}\b` absent from `pages_*.js`), `test_no_cdn` (no `http://` or `https://` script/link src in `index.html`), `test_ego_strip_wired` (`/api/ego_strip` appears in `pages_data.js` and `pages_ops.js`).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Copy and fix.
- [ ] **Step 4:** pytest, ruff, mypy → pass.

### Task 8: Integration on real data (lead)

- [ ] **Step 1:** `uv run fw console index` on the real `fwdata/`; compare counts with v5 `data/` (catalog 60 rows; S70 425 episodes and posters; ALL 606).
- [ ] **Step 2:** `uv run fw console serve --port 4180` via `.claude/launch.json`; in the browser pane check at 1 440 × 900 dark and light and 1 920 × 1 080: `#/home`, `#/data`, `#/data/S70`, `#/data/S70/ep/278`, `#/jobs?view=pipeline`, `#/runs`, `#/eval`, `#/loop`, `#/loop?tab=cost`, `#/qa`; sidebar `[`, panel `⌘.`; no console errors; sankey labels readable; ego hover strip shows.
- [ ] **Step 3:** `uv run fw console bench --tag da40` (needs the tunnel): tool/arg ≥ 33/36, guardrail 6/6, cross ≥ 5/6, the S1 item passes.
- [ ] **Step 4:** `uv run ruff check && uv run mypy && uv run pytest && uv run lint-imports && python3 scripts/repo/check_links.py && python3 scripts/repo/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"`.
- [ ] **Step 5:** Commit `DA-40/8`, tick the story, report to Hiếu with screenshots and the bench numbers.

## Execution order

Task 1 first (everything imports `paths`). Then Tasks 2, 3, 5, 6, 7 in parallel (disjoint files; Task 5 stubs the chat functions in tests). Task 4 after Tasks 2 and 3. Task 8 last. Each task: one Sonnet implementer, then a review by the lead before its commit.
