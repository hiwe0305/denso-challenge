"""Dictionary checks (one-site design 5.4, 5.5): same keys in both files, every t() key exists,
leads stay under 30 words and a station's explain band under 90."""

from __future__ import annotations

import re
from pathlib import Path

from flywheel.console import budget

WEB = Path(budget.__file__).parent / "web"


def test_both_dictionaries_have_the_same_keys() -> None:
    vi = budget.dict_entries(WEB / "i18n" / "vi.js")
    en = budget.dict_entries(WEB / "i18n" / "en.js")
    assert vi and set(vi) == set(en)


def test_every_t_call_has_a_key() -> None:
    vi = budget.dict_entries(WEB / "i18n" / "vi.js")
    used: set[str] = set()
    for f in WEB.glob("*.js"):
        used |= set(re.findall(r"\bt\(\"([a-zA-Z0-9_.]+)\"\s*[,)]", f.read_text(encoding="utf-8")))
    assert used, "no t() calls found"
    assert not sorted(used - set(vi))


def test_dictionaries_respect_the_word_rule() -> None:
    for name in ("vi.js", "en.js"):
        assert budget.dict_violations(WEB / "i18n" / name) == [], name


def test_word_rule_catches_long_lead_and_long_station(tmp_path: Path) -> None:
    f = tmp_path / "x.js"
    long = " ".join(["chữ"] * 31)
    f.write_text(
        'window.I18N.vi = {\n  "st.1.a": "'
        + long
        + '",\n  "st.2.q": "'
        + " ".join(["a" + "b"] * 95)
        + '",\n};\n',
        encoding="utf-8",
    )
    v = budget.dict_violations(f)
    assert any("st.1.a" in x for x in v) and any("st.2" in x for x in v)


# keys built at run time: t("prefix" + value). Every prefix in the JS must be listed here,
# and every value the data can produce must have a key in both dictionaries.
DYNAMIC = {
    "st.": [f"{n}.{k}" for n in range(0, 7) for k in ("name", "q", "a", "in", "do", "out", "risk")],
    "run.": ["C_ALL", "C_70", "B_ALL", "B_70", "C70_R1"],
    "fig.step.": ["approach_a", "grasp", "lift", "carry", "reach_b", "place", "release_stand"],
    "fig.mix.": ["coverage", "prev", "round", "teleop"],
    "fig.cut.": ["ALL", "S70", "C70_R1"],
    "fig.sha.": ["tar", "marker"],
    "fig.loop.": [str(i) for i in range(1, 7)],
    "fig.src.": [f"{s}.{k}" for s in ("ego", "tele", "sim") for k in ("t", "d")],
    "sim.tab.": ["gallery", "quality", "all"],
    "fol.s": [f"{i}.t" for i in range(1, 6)],
    "fail.": ["L-PLACE-POSE", "L-TIMEOUT", "L-ONE-HAND", "L-TRAY-TILT", "L-PART-DROP"],
}


def test_dynamic_keys_are_listed_and_exist() -> None:
    prefixes: set[str] = set()
    for f in WEB.glob("*.js"):
        text = f.read_text(encoding="utf-8")
        prefixes |= set(re.findall(r"\bt\(\"([a-zA-Z0-9_.]+)\"\s*\+", text))
    assert prefixes and not sorted(prefixes - set(DYNAMIC)), "list the new prefix in DYNAMIC"
    for name in ("vi.js", "en.js"):
        keys = set(budget.dict_entries(WEB / "i18n" / name))
        missing = [p + v for p, vals in DYNAMIC.items() for v in vals if p + v not in keys]
        assert not missing, (name, missing)


def test_old_routes_redirect_to_their_station() -> None:
    """Old hashes keep working (design 5.1); `process` belongs to step 2 (pipeline view).
    Flywheel v0.3 design 4: the old station 3 "packaging" (export panel) is part of step 1,
    #/diagnose is step 5."""
    src = (WEB / "app.js").read_text(encoding="utf-8")
    m = re.search(r"const REDIRECT = \{(.*?)\};", src)
    assert m
    red = dict(re.findall(r'"?([\w/]+)"?: "([^"]+)"', m.group(1)))
    assert red["process"] == "jobs?view=pipeline" and red["training"] == "runs"
    assert red["agent"] == "qa" and red["overview"] == "home"
    ex = (WEB / "explain.js").read_text(encoding="utf-8")
    assert 'qs.view === "pipeline")) return 2' in ex and 'qs.panel === "export") return 1' in ex
    assert 'p === "diagnose") return 5' in ex and 'p === "runs" || p === "training") return 3' in ex
    assert 'qs.tab === "cost" ? 0 : 6' in ex


def test_sidebar_uses_steps_not_stations() -> None:
    """Visible text says "bước" / "step", never "trạm" / "station" (flywheel v0.3, brief 4)."""
    for name in ("vi.js", "en.js"):
        vals = budget.dict_entries(WEB / "i18n" / name).values()
        assert not [v for v in vals if re.search(r"\b(trạm|station)\b", v, re.I)], name
