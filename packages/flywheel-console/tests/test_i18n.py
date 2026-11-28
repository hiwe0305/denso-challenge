"""Dictionary and router checks for the rebuilt console web UI."""

from __future__ import annotations

import re
from pathlib import Path

from flywheel.console import budget

WEB = Path(budget.__file__).parent / "web"

# Keys constructed dynamically as t("prefix" + value). Every prefix in web/*.js must be listed here,
# and every resulting key must exist in both vi.js and en.js.
DYNAMIC: dict[str, list[str]] = {
    "nav.group.": ["start", "data", "ops", "exp", "f2d", "plan"],
    "nav.item.": [
        "tasks",
        "home",
        "chat",
        "data",
        "import",
        "pipeline",
        "export",
        "egoflow",
        "qa",
        "jobs",
        "runs",
        "eval",
        "sim",
        "base",
        "diagnose",
        "loop",
        "follow",
        "design",
        "cost",
        "report",
    ],
    "proc.stage.": [str(n) for n in range(0, 7)],
    "cat.group.": ["egocentric", "teleop", "s1", "s2", "eval", "other", "all"],
    # Design page rows (W12, 28/11): ids of story.demo.design; descriptions only for text rows.
    "design.item.": [
        "task",
        "station",
        "sim_episodes",
        "human_clips",
        "keyboard_teleop",
        "trained_model",
        "step_scores",
        "recommendation",
        "comparison",
        "sim_stack",
        "robot_model",
        "lerobot",
        "laptop",
        "rtx3060",
        "colab_train_gpu",
        "colab_serve_gpu",
        "head_camera",
        "train_cu",
        "train_cu_estimate",
        "test_cu",
        "gen_hours",
        "qa_hours",
        "gen_machine_hours",
        "gen_cu",
        "deid_first",
    ],
    "design.desc.": ["task", "station", "keyboard_teleop", "laptop", "head_camera", "deid_first"],
    "diag.check.": ["H1", "H2", "H3", "delay_sync_camera"],
    "diag.val.": ["unclear_scorer_threshold", "unclear_missing_signal", "policy_failure", "pass"],
    "diag.rule.": [
        "near_miss_placement",
        "scorer_latch_too_strict",
        "label_signal_missing",
        "none",
    ],
    "cost.line.": ["train_1", "train_2", "serve", "jig_train", "jig_eval"],
    "runs.metric.": ["loss", "val", "thr", "vram", "gn"],
    "runs.phase.": ["setup", "train"],
    "fail.": ["L-PLACE-POSE", "L-TRAY-TILT", "L-TIMEOUT", "L-PART-DROP", "L-ONE-HAND"],
    "field.": ["episodes", "frames", "clips", "exported", "models", "steps", "hours", "cu"],
    "tasks.inv.": ["store", "task"],
    "job.kind.": [
        "eval.diag_system",
        "data.release",
        "data.ingest",
        "data.report",
        "data.qa",
        "data.pipeline",
        "ego.ingest",
        "ego.deid",
        "ego.ea",
        "ego.pose",
        "ego.annotate",
        "ego.qa",
        "ego.report",
        "ego.pipeline",
        "ego.human1m",
        "agentqa.run",
        "agentqa.review",
        "export.zip",
    ],
    "status.state.": [
        "idle",
        "running",
        "queued",
        "done",
        "ok",
        "blocked",
        "waiting",
        "failed",
        "cancelled",
        "pass",
        "flag",
        "reject",
        "current",
        "upstream",
        "superseded",
        "archived",
        "missing",
        "test",
        "duplicate",
        "partial",
        "todo",
        "na",
        "up",
        "down",
        "warm",
        "cold",
        "busy",
        "stopped",
        "baseline",
        "control",
        "after_round",
        "continue",
        "f",
        "info",
    ],
    "cite.kind.": ["measured", "estimated", "description", "artifact", "cited", "file"],
    "home.stageId.": ["collect", "process", "release", "train", "eval", "loop"],
    "jobs.tab.": ["all", "pipeline", "import", "export", "machines"],
    "ds.tab.": ["overview", "content", "quality", "lineage", "jobs"],
    "ego.tier.": ["ingest", "deid", "ea", "pose", "annotate", "qa", "report"],
    "design.sec.": ["input", "output", "environment", "devices", "resource"],
}


def test_both_dictionaries_have_the_same_keys() -> None:
    vi = budget.dict_entries(WEB / "i18n" / "vi.js")
    en = budget.dict_entries(WEB / "i18n" / "en.js")
    assert vi and set(vi) == set(en)
    assert vi["status.state.current"] == "Hiện hành"


def test_en_dictionary_has_no_vietnamese_diacritics() -> None:
    vi_chars = re.compile(
        r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]",
        re.I,
    )
    en = budget.dict_entries(WEB / "i18n" / "en.js")
    bad = [k for k, v in en.items() if vi_chars.search(v)]
    assert not bad, f"Vietnamese text in en.js keys: {bad}"


def test_every_t_call_has_a_key() -> None:
    vi = budget.dict_entries(WEB / "i18n" / "vi.js")
    used: set[str] = set()
    for f in WEB.glob("*.js"):
        used |= set(re.findall(r'\bt\("([a-zA-Z0-9_.]+)"\s*[,)]', f.read_text(encoding="utf-8")))
    assert used, "no t() calls found"
    assert not sorted(used - set(vi))


def test_dictionaries_respect_the_word_rule() -> None:
    for name in ("vi.js", "en.js"):
        assert budget.dict_violations(WEB / "i18n" / name) == [], name


def test_word_rule_catches_long_lead_and_long_station(tmp_path: Path) -> None:
    f = tmp_path / "x.js"
    long = " ".join(["chữ"] * 31)
    f.write_text(
        'export default {\n  "st.1.a": "'
        + long
        + '",\n  "st.2.q": "'
        + " ".join(["ab"] * 95)
        + '",\n};\n',
        encoding="utf-8",
    )
    v = budget.dict_violations(f)
    assert any("st.1.a" in x for x in v) and any("st.2" in x for x in v)


def test_dynamic_keys_are_listed_and_exist() -> None:
    prefixes: set[str] = set()
    for f in WEB.glob("*.js"):
        text = f.read_text(encoding="utf-8")
        prefixes |= set(re.findall(r'\bt\("([a-zA-Z0-9_.]+)"\s*\+', text))
    assert prefixes and not sorted(prefixes - set(DYNAMIC)), (
        f"unlisted dynamic prefixes: {sorted(prefixes - set(DYNAMIC))}"
    )
    for name in ("vi.js", "en.js"):
        keys = set(budget.dict_entries(WEB / "i18n" / name))
        missing = [p + v for p, vals in DYNAMIC.items() for v in vals if p + v not in keys]
        assert not missing, (name, missing)


def test_legacy_routes_redirect_per_ui_spec() -> None:
    src = (WEB / "app.js").read_text(encoding="utf-8")
    m = re.search(r"export const REDIRECT = \{(.*?)\};", src, flags=re.S)
    assert m
    red = dict(re.findall(r'"([\w/]+)":\s*"([^"]+)"', m.group(1)))
    assert red == {
        "overview": "home",
        "process": "jobs?view=pipeline",
        "training": "runs",
        "agent": "qa",
        "data/nhap": "jobs?panel=import",
        "data/xuat": "jobs?panel=export",
    }
    assert 'path === "home" && (query.has("s") || query.has("tour"))' in src
    assert 'path === "loop" && query.get("tab") === "cost"' in src
    assert "window.history.replaceState" in src


def test_dictionaries_use_steps_not_stations() -> None:
    for name in ("vi.js", "en.js"):
        vals = budget.dict_entries(WEB / "i18n" / name).values()
        assert not [v for v in vals if re.search(r"\b(trạm|station)\b", v, re.I)], name


def test_no_dictionary_value_ranks_runs() -> None:
    """Rule 4 of ``jig-m-rules``: M beside the DA-34 runs is never "better" (story DA-53)."""
    for name in ("vi.js", "en.js"):
        vals = budget.dict_entries(WEB / "i18n" / name)
        bad = [k for k, v in vals.items() if re.search(r"tốt hơn|\bbetter\b", v, re.I)]
        assert not bad, (name, bad)
