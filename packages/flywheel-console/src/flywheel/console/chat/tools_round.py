# ruff: noqa: E501  (one fact per line of the model text)
"""``round_report`` and its companions: the facts of one task's round, for analysis questions.

"What do you make of the results", "why did the round not help", "what next", "which model has
the most successes", "what did the round cost" need the test results, the reading marks, the
diagnosis, the data order, the outcome and the cost side by side. The tools read them from the
console index (``tasks.json`` for the task, its rounds and the role of each model, ``story.json``
for the numbers) and return them as DATA: one labelled row per line, ``SECTION | key=value | ...``,
after a ``ROUND`` header row. Values that are words are in the language of the question
(``ctx["lang"]``: vi or en), numbers keep its decimal style. The section the question asks about
comes first. The rows hold no prose to copy and no instruction: how to write the answer lives in
the system prompt (``llm.SYSTEM``). Doc references go apart, in ``Result["sources"]``.

A round reads its own block of the index: a round whose manifest lists ``story.jig`` (run M on
the jig scene) reads ``story.jig`` and its reading rules; a round built on ``story.pair`` (DA-34)
reads the pair, the round chain and the demo block. A round whose numbers are missing fails
instead of borrowing another round's numbers. Every result carries the id of the round its
numbers belong to (``Result["round"]``), so the turn can check the numbers against the round the
user is looking at.

A run whose test result is not presented (``withhold_eval`` of any round) never reaches a tool
text, on any round, and a question about it gets one fixed sentence (W5, Hiếu 28/11/2026) that
neither confirms nor denies a figure the user offers.
"""

from __future__ import annotations

import re
from typing import Any

from flywheel.console.index import hidden
from flywheel.console.paths import active

from .common import (
    HOSTED,
    MODEL_CHARS,
    Result,
    cap,
    catalog,
    cols,
    fail,
    hidden_runs,
    jload,
    result,
    story,
    table,
    totals,
    withheld_runs,
)

ROLE = {
    "baseline": ("bản gốc", "the baseline"),
    "after_round": ("bản sau vòng", "the model after the round"),
    "control": ("bản đối chứng", "a control"),
}
# failure labels of the scorer, in plain words (the codes never reach the model text)
FAIL = {
    "L-PLACE-POSE": ("Đặt lệch", "Misplaced"),
    "L-TRAY-TILT": ("Khay nghiêng", "Tray tilted"),
    "L-TIMEOUT": ("Hết giờ", "Timed out"),
    "L-PART-DROP": ("Rơi khay", "Tray dropped"),
    "L-ONE-HAND": ("Chỉ cầm một tay", "One hand only"),
}
STEP = {
    "approach_a": ("tới bàn A", "reach table A"), "grasp": ("cầm", "grasp"), "lift": ("nhấc", "lift"),
    "carry": ("mang", "carry"), "reach_b": ("tới bàn B", "reach table B"), "place": ("đặt", "place"),
    "release_stand": ("buông và đứng", "release and stand"),
}  # fmt: skip
DIAG_WORD = {"weak_skill": ("kỹ năng yếu", "weak skill"), "unknown": ("chưa rõ", "unknown")}
COST_LINE = {"train_1": ("train lần 1", "first training"), "train_2": ("train lần 2", "second training"), "serve": ("serve", "serving")}
STAGE_NAMES = ("dữ liệu", "kiểm định", "dạy model", "thi và chấm", "chẩn đoán", "lỗi → dữ liệu")
STAGE_NAMES_EN = ("data", "checks", "training", "test and scoring", "diagnosis", "failure → data")
COUNT_VI = {2: "hai", 3: "ba", 4: "bốn", 5: "năm", 6: "sáu"}
# step-4 verdicts as the index writes them (English), in Vietnamese words of tray.md §20.11
RESULT_VI = {"unclear (scorer threshold)": "CHƯA RÕ (ngưỡng bộ chấm)", "unclear (missing signal)": "CHƯA RÕ (thiếu tín hiệu)",
             "policy failure": "lỗi của policy", "pass": "qua"}

# W5 (Hiếu 28/11/2026): the one sentence for every place a result is not presented
WITHHELD = ("Kết quả thi lại của lượt này không trình bày ở bản demo.",
            "The re-test result of this run is not presented in this demo.")  # fmt: skip
# A question about a hidden run or story (run N, DA-50): a scoped, true sentence that neither
# confirms nor denies it (same rule as W5; Hiếu 28/11/2026)
NOT_PRESENTED = ("Trong dữ liệu trình bày ở bản demo không có tập dữ liệu hay run nào như vậy.",
                 "The data presented in this demo has no such dataset or run.")  # fmt: skip
# W6: two rounds differ in scene, eval set, scorer and number of steps
SIDE_BY_SIDE = ("Hai vòng khác cảnh, tập eval, bộ chấm và số bước, nên chỉ đặt cạnh nhau, không so như một kết quả.",
                "The two rounds differ in scene, eval set, scorer and number of steps, so they are only placed side by side, not compared as a result.")  # fmt: skip


# what the question is after, most specific first; "all" is a general comment on the round
FOCUS = [
    ("verdict", re.compile(r"đạt mốc|mốc \d|\bmốc\b|ngưỡng|\b\d+ ?%\s*\?|threshold|\bmeet|\breach(es|ed)? the|the \d+ ?% (mark|bar)", re.I)),
    ("why", re.compile(r"vì sao|tại sao|\bwhy\b|chưa tốt|không tốt|không cải thiện|xấu đi|did not (improve|help)|not improve", re.I)),
    ("next", re.compile(r"nên làm|làm gì tiếp|bước tiếp|tiếp theo|what next|next step|should we|what to do|should the team", re.I)),
    ("cost", re.compile(r"\btốn\b|chi phí|bao nhiêu tiền|\bcost|\bCU\b|\bUSD\b|budget|ngân sách", re.I)),
    ("steps", re.compile(r"bước nào|từng bước|qua từng|which step|each step|per step|step by step", re.I)),
    ("diag", re.compile(r"chẩn đoán|nhóm lỗi|cụm lỗi|phiếu|diagnos|failure group|ticket", re.I)),
    ("compare", re.compile(r"so sánh|khác nhau|khác gì|đặt cạnh|\bcompare|difference between|side by side|\bso\b.*\bvới\b|\bvs\.?\b|rollout", re.I)),
    ("fail", re.compile(r"hỏng|lỗi nào|lỗi gì|thất bại|\bfail|failure|điểm yếu|weak", re.I)),
    ("best", re.compile(r"tốt nhất|\bbest\b|bản nào|which model|cao nhất|nhiều nhất|most success", re.I)),
    ("qa", re.compile(r"kiểm định|lỗi cấy|planted|quality check|inspector", re.I)),
    ("data", re.compile(r"dữ liệu|bài mẫu|\bdata\b|demonstration", re.I)),
]

# a question that asks which run or model is best, or for a ranking: read from the test results
# (W3), never from the training loss (Website, 28/11/2026)
RANK_RX = re.compile(r"tốt nhất|tốt hơn|mạnh nhất|xếp hạng|hạng nhất|\bbest\b|\bbetter\b|\branks?\b|\branking\b|\bwinner\b|top run", re.I)
LOSS_RX = re.compile(r"\bloss\b|ema50|đường cong|curve", re.I)

AFTER_RX = re.compile(r"sau vòng|bản mới|dạy lại|thi lại|after the round|retest|re-test|retrain", re.I)
# a figure offered for the user to confirm ("... chỉ đạt 4/60 phải không?")
_FIGURE_RX = re.compile(r"\d+\s*/\s*\d+|\d+(?:[.,]\d+)?\s*%")
_CONFIRM_RX = re.compile(r"phải không|đúng không|có phải|đúng chứ|\bchỉ\b|right\?|isn't it|is it true|correct\?|\bonly\b|confirm", re.I)
_ROUND1_RX = re.compile(r"vòng 1|vòng này|round 1|this round|tray-r1|\bmới\b|\bnew\b|lần 2|second", re.I)


def held_runs() -> list[str]:
    """Run ids whose test result some round does not present: ``withhold_eval`` of the seed (raises
    ``ManifestUnreadable`` when it cannot be read), plus any the index lists."""
    seed = withheld_runs()
    index = {str(x) for r in manifest().get("rounds") or [] for x in r.get("withhold_eval") or []}
    return sorted(seed | index)


def _held_names() -> list[str]:
    """The held runs and the train sets only they use (C70_R1 trains on R181)."""
    held = set(held_runs())
    names = list(held)
    for r in manifest().get("rounds") or []:
        for x in r.get("runs") or []:
            ts = str(x.get("train_set") or "")
            if x.get("id") in held and ts and ts not in names:
                names.append(ts)
    return names


def _word_in(word: str, text: str, case: bool = False) -> bool:
    flags = 0 if case else re.I
    return bool(re.search(r"(?<![\w])" + re.escape(word) + r"(?![\w])", text, flags))


def asks_held(question: Any) -> bool:
    """The question is about a run whose test result is not presented: by id or train set, 'after
    the round', or a figure offered for confirmation about the round without naming a shown run."""
    q = str(question or "")
    held = held_runs()
    if not held:
        return False
    if any(_word_in(h, q) for h in _held_names()) or AFTER_RX.search(q):
        return True
    if _FIGURE_RX.search(q) and _CONFIRM_RX.search(q) and _ROUND1_RX.search(q):
        shown = [str(x.get("id")) for r in manifest().get("rounds") or [] for x in r.get("runs") or []
                 if x.get("id") not in held]  # fmt: skip
        return not any(_word_in(s, q, case=True) for s in shown)
    return False


def asks_hidden(question: Any) -> bool:
    """The question names a run or story that is not presented (``withhold_runs``): a hidden run
    as "run N" / "lượt N" / "bản N", one of its session or folder names, or a hidden story id."""
    q = str(question or "")
    h = hidden_runs()
    if not h:
        return False
    if h.mentions(q) or any(_word_in(s, q) for s in h.stories):
        return True
    ids = "|".join(re.escape(i) for i in sorted(h.ids))
    return bool(re.search(rf"(?i:lượt|bản|run|model|policy)\s+(?:{ids})(?![\w])", q))


def focus_of(question: Any) -> str:
    q = str(question or "")
    if asks_held(q):
        return "held"
    if RANK_RX.search(q):
        return "best"  # "which run is best, and why?" is a ranking question first
    return next((k for k, rx in FOCUS if rx.search(q)), "all")


def focuses_of(question: Any) -> list[str]:
    """Every part the question asks about, in FOCUS order ("đạt mốc 80% không, và đặt cạnh bảng
    60 rollout" asks for the verdict and the comparison)."""
    q = str(question or "")
    return [k for k, rx in FOCUS if rx.search(q)]


def manifest() -> dict[str, Any]:
    d = jload(active().index / "tasks.json", {})
    d = d if isinstance(d, dict) else {}
    shown = hidden.tasks_doc(d, hidden_runs())  # withhold_runs of the seed, even in a stale index
    d = shown if isinstance(shown, dict) else d
    if not HOSTED.get():
        return d
    # with a hosted model each task lists and totals its public rows only, as catalog() does
    rows = catalog().get("rows", [])
    keep = {r.get("id") for r in rows}
    tasks = []
    for t in d.get("tasks") or []:
        if isinstance(t, dict):
            mine = [r for r in rows if r.get("task") == t.get("catalog_task")]
            t = {**t, "catalog_totals": totals(mine) if mine else {},
                 "catalog_rows": [r for r in t.get("catalog_rows") or [] if r.get("id") in keep]}  # fmt: skip
        tasks.append(t)
    return {**d, "tasks": tasks}


def _rounds() -> list[dict[str, Any]]:
    return [r for r in manifest().get("rounds") or [] if isinstance(r, dict) and r.get("id")]


def _plain_runs(rnd: dict[str, Any]) -> list[str]:
    """Run ids of a round written as plain letters ("M"): the question names them as words."""
    return [str(x.get("id")) for x in rnd.get("runs") or [] if re.fullmatch(r"[A-Z][A-Za-z]{0,3}", str(x.get("id") or ""))]


def _covers(rnd: dict[str, Any]) -> set[str]:
    """Run ids a round's report gives numbers for: its own runs and, for the jig round, the runs
    of the 60-rollout table it sets side by side (story.jig.compare60)."""
    ids = {str(x.get("id")) for x in rnd.get("runs") or [] if x.get("id")}
    if "story.jig" in (rnd.get("index") or []):
        c60 = (story().get("jig") or {}).get("compare60") or {}
        ids |= {str(e.get("run")) for e in c60.get("earlier") or [] if e.get("run")}
        if c60.get("run"):
            ids.add(str(c60["run"]))
    return ids


def _named_rounds(q: str, rounds: list[dict[str, Any]]) -> list[str]:
    """Rounds the question names by id, by number ("vòng 1") or by scene ("đồ gá", "jig")."""
    out: list[str] = []
    for r in sorted(rounds, key=lambda r: -len(str(r["id"]))):
        if re.search(r"(?<![\w-])" + re.escape(str(r["id"])) + r"(?![\w-])", q, re.I):
            out.append(str(r["id"]))
    # The scene word goes before "vòng N": "vòng đồ gá" or "jig" names the jig round even when the
    # question also says "vòng 1" (e.g. "so vòng 1 với vòng đồ gá").
    if re.search(r"đồ gá|\bjig", q, re.I):
        out += [str(r["id"]) for r in rounds if r.get("scene") or "story.jig" in (r.get("index") or [])]
    for m in re.finditer(r"(?:vòng|round)\s*(\d)\b", q, re.I):
        out += [str(r["id"]) for r in rounds if str(r.get("number")) == m.group(1)]
    return list(dict.fromkeys(out))


def runs_named(question: Any) -> set[str]:
    """Run ids of the rounds the question names: plain letters ("M") as case-sensitive words, other
    ids ("C_70", "C_ALL") as words in any case."""
    q = str(question or "")
    rounds = _rounds()
    runs = {run for r in rounds for run in _plain_runs(r) if _word_in(run, q, case=True)}
    runs |= {str(x.get("id")) for r in rounds for x in r.get("runs") or []
             if x.get("id") and not re.fullmatch(r"[A-Z][A-Za-z]{0,3}", str(x["id"])) and _word_in(str(x["id"]), q)}  # fmt: skip
    return runs


def pair_runs_named(question: Any) -> set[str]:
    """Runs named in the question that belong to the pair round (DA-34: C_70, C_ALL...), whose
    diagnosis ``story.diag`` holds."""
    pid = _pair_round_id()
    own = {str(x.get("id")) for r in _rounds() if str(r.get("id")) == pid for x in r.get("runs") or []}
    return runs_named(question) & own


def rounds_named(question: Any) -> list[str]:
    """Every round the question names by id, number or scene, in the order ``_named_rounds`` gives."""
    return _named_rounds(str(question or ""), _rounds())


def round_named(question: Any, current: Any = None) -> str:
    """The round a question is about, from every round it names and every run it names.

    A run named in the question ("run M", "C_ALL") picks a round whose report covers all of them
    (the jig round covers its run M and the DA-34 runs of its 60-rollout table); among those, the
    one the question also names, then ``current``. With no run named: ``current`` when the
    question names it, else the first round named. Else ``current`` (the top bar)."""
    q = str(question or "")
    cur = str(current or "")
    rounds = _rounds()
    named = _named_rounds(q, rounds)
    runs = runs_named(q)
    if runs:
        cover = [str(r["id"]) for r in rounds if runs <= _covers(r)]
        if cover:
            both = [x for x in cover if x in named]
            if cur in both or (not both and cur in cover):
                return cur
            return (both or cover)[0]
    if named:
        return cur if cur in named else named[0]
    return cur


def strip_round_refs(question: Any) -> str:
    """The question without its round references (round ids, "vòng 1", "run M"), so the router
    does not take them for a dataset or a run lookup."""
    q = str(question or "")
    for r in _rounds():
        q = re.sub(re.escape(str(r["id"])), " ", q, flags=re.I)
        for run in _plain_runs(r):
            q = re.sub(r"(?<![\w])(?:run\s+)?" + re.escape(run) + r"(?![\w])", " ", q)
    return re.sub(r"(?:vòng|round)\s*\d\b", " ", q, flags=re.I)


class Say:
    """Pick the Vietnamese or the English wording of a fact."""

    def __init__(self, lang: Any) -> None:
        self.vi = str(lang or "vi").lower().startswith("vi")

    def __call__(self, vi: str, en: str) -> str:
        return vi if self.vi else en

    def name(self, o: Any) -> str:
        if isinstance(o, dict):
            return str((o.get("vi") if self.vi else o.get("en")) or o.get("vi") or o.get("en") or "")
        return str(o or "")

    def fail(self, label: Any) -> str:
        """A failure label in plain words; an unknown code without its ``L-`` prefix."""
        w = FAIL.get(str(label))
        return w[0 if self.vi else 1] if w else re.sub(r"^L-", "", str(label)).replace("-", " ").lower()

    def step(self, s: str) -> str:
        w = STEP.get(s)
        return w[0 if self.vi else 1] if w else s

    def role(self, r: Any) -> str:
        w = ROLE.get(str(r))
        return w[0 if self.vi else 1] if w else self("bản model", "model")

    def stage(self, n: str) -> str:
        i = int(n) - 1
        return f"{n} {(STAGE_NAMES if self.vi else STAGE_NAMES_EN)[i]}" if 0 <= i < 6 else n

    def num(self, x: Any, d: int = 1) -> str:
        """A decimal in the reader's convention: 75,6 in Vietnamese, 75.6 in English."""
        try:
            s = f"{float(x):.{d}f}"
        except (TypeError, ValueError):
            return str(x)
        return s.replace(".", ",") if self.vi else s

    def pct(self, p: Any) -> str:
        """A share 0..1 as a percentage with one decimal ("75,6")."""
        try:
            return self.num(100 * float(p), 1)
        except (TypeError, ValueError):
            return str(p)

    def rate(self, p: Any) -> str:
        """A share 0..1 as a rate with its sign: "75,6 %" in Vietnamese, "75.6%" in English."""
        return self.pct(p) + (" %" if self.vi else "%")

    def frac(self, k: Any, n: Any) -> str | None:
        """The rate of ``k`` successes out of ``n``; None without a count."""
        if isinstance(k, (int, float)) and isinstance(n, (int, float)) and n:
            return self.rate(k / n)
        return None

    @staticmethod
    def yes(b: Any) -> str:
        """A flag of a row: "yes" or "no" in every language (the system prompt reads them)."""
        return "yes" if b else "no"

    def scene(self, scene: Any) -> str:
        """The scene of a round in words: "có đồ gá jig2" / "không đồ gá"."""
        return self(f"có đồ gá {scene}", f"jig fixture {scene}") if scene else self("không đồ gá", "no jig fixture")

    def scorer(self, v: Any) -> str:
        return self(f"bản {v}", f"v{v}")

    def ci(self, ci: Any) -> str:
        lo, hi = (ci or [None, None])[:2]
        return f"{self.pct(lo)}–{self.pct(hi)}"

    def count(self, n: int) -> str:
        return COUNT_VI.get(n, str(n)) if self.vi else str(n)


def _v(v: Any) -> str:
    """One value of a row: on one line, without the column separator."""
    return re.sub(r"\s+", " ", str(v)).replace("|", "/").strip()


def _row(section: str, **kv: Any) -> str:
    """One labelled data row, ``SECTION | key=value | ...``; empty values are left out."""
    return " | ".join([section, *(f"{k}={_v(v)}" for k, v in kv.items() if v is not None and _v(v) != "")])


def _done(ui: dict[str, Any], lines: list[str], sources: list[Any], rid: Any = None) -> Result:
    """A tool result whose model text is the rows, with its doc references apart (``sources``)."""
    out = result(ui, "\n".join(ln for ln in lines if ln))
    out["sources"] = list(dict.fromkeys(ref for s in sources if s for ref in _doc_refs(s)))
    if rid:
        out["round"] = str(rid)
    return out


def _doc_refs(v: Any) -> list[str]:
    """The doc references of a source note ("docs/he/tray.md §20.3; clusters from story.round"
    gives the doc part only): the parts that name a file under docs/ or seed/."""
    parts = v if isinstance(v, list) else re.split(r";\s*", str(v))
    return [str(p).strip() for p in parts if re.search(r"\b(docs|seed)/", str(p))]


def _sections(plan: dict[str, list[str]], focus: str, extra: list[str]) -> list[str]:
    """The sections of the main focus, then those of each other focus of the question."""
    keys = list(plan.get(focus, plan["all"]))
    for e in extra:
        if e != focus and e in plan:
            keys += plan[e]
    return list(dict.fromkeys(keys))


def _shown(entry: Any) -> bool:
    """An index entry (timeline, next step, latest) that names no hidden or held run or story."""
    if not isinstance(entry, dict):
        return False
    h = hidden_runs()
    text = " ".join(str(v) for v in entry.values())
    if h and (h.run(entry.get("run")) or h.story(entry.get("story")) or h.mentions(text)
              or any(_word_in(x, text) for x in h.stories)):  # fmt: skip
        return False
    return not any(_word_in(x, text) for x in _held_names())


def _say_text(say: Say, v: Any) -> str:
    """A {vi, en} text of the index (or a plain string) in the user's language."""
    return say.name(v) if isinstance(v, dict) else str(v or "")


def _round_by_id(rid: Any) -> dict[str, Any] | None:
    return next((r for r in _rounds() if str(r.get("id")) == str(rid)), None)


def _scene_of(rnd: dict[str, Any]) -> Any:
    if rnd.get("scene"):
        return rnd["scene"]
    if "story.jig" in (rnd.get("index") or []):
        return (story().get("jig") or {}).get("scene")
    return None


def _scorer_of(rnd: dict[str, Any]) -> Any:
    """The scorer version of a round; a round without one was scored before the scorer had
    versions (bản 1: version 2 came with DA-42)."""
    if rnd.get("scorer_version"):
        return rnd["scorer_version"]
    if "story.jig" in (rnd.get("index") or []):
        v = (story().get("jig") or {}).get("scorer_version")
        if v:
            return v
    return 1


def _differs(say: Say, a: dict[str, Any], b: dict[str, Any], link: dict[str, Any] | None = None) -> list[str]:
    """What sets two rounds apart, from the link of the index when it says, else from the rounds."""
    link = link or {}
    scene = link["scene_differs"] if "scene_differs" in link else _scene_of(a) != _scene_of(b)
    scorer = link["scorer_differs"] if "scorer_differs" in link else str(_scorer_of(a)) != str(_scorer_of(b))
    out = []
    if scene:
        out.append(say("cảnh", "scene"))
        out.append(say("tập eval", "eval set"))  # another scene is another set of conditions
    if scorer:
        out.append(say("bộ chấm", "scorer"))
    if a.get("max_steps") and b.get("max_steps") and a["max_steps"] != b["max_steps"]:
        out.append(say("số bước train", "training steps"))
    return out


def _run_numbers(rnd: dict[str, Any], run: Any) -> dict[str, Any]:
    """{successes, n} of a presented run of a round, from the round's own block of the index."""
    held = set(held_runs())
    if not run or run in held or hidden_runs().run(run):
        return {}
    s = story()
    if "story.jig" in (rnd.get("index") or []):
        j = s.get("jig") or {}
        ev = next((e for e in j.get("evals") or [] if e.get("run") == run), None)
        h = (ev or {}).get("headline") or {}
        return {"successes": h.get("successes"), "n": h.get("n")} if h.get("n") else {}
    r = next((x for x in (s.get("pair") or {}).get("runs") or [] if x.get("run") == run), None)
    if not r:
        return {}
    lad = (((s.get("demo") or {}).get("ladder") or {}).get("runs") or {}).get(run) or {}
    return {"successes": r.get("successes"), "n": r.get("n"), "carried": lad.get("on_table_b"), "placed": r.get("successes")}


def _link(task: dict[str, Any], rnd: dict[str, Any], which: str) -> dict[str, Any] | None:
    """The round before or after this one (``rounds[].links.prev|next`` of the index; else the
    neighbour in the task's list of rounds, with its baseline run's numbers). None without one,
    or when its run is not presented."""
    held = set(held_runs())
    links: dict[str, Any] = rnd["links"] if isinstance(rnd.get("links"), dict) else {}
    ln = links.get(which)
    if isinstance(ln, dict) and ln.get("round"):
        return None if (ln.get("run") in held or hidden_runs().run(ln.get("run"))) else ln
    ids = [str(x) for x in task.get("rounds") or []]
    rid = str(rnd.get("id"))
    if rid not in ids:
        return None
    i = ids.index(rid) + (-1 if which == "prev" else 1)
    other = _round_by_id(ids[i]) if 0 <= i < len(ids) else None
    if other is None:
        return None
    run = other.get("baseline")
    nums = _run_numbers(other, run)
    if not nums:
        return None
    a, b = (other, rnd) if which == "prev" else (rnd, other)
    return {"round": other.get("id"), "run": run, **nums, "scene_differs": _scene_of(a) != _scene_of(b),
            "scorer_differs": str(_scorer_of(a)) != str(_scorer_of(b))}  # fmt: skip


def _next_steps(say: Say, rid: str, sources: list[Any]) -> list[str] | None:
    """OPTION rows from ``story.next_steps`` for this round: written in the docs, never one marked
    ``historical`` (work already done, e.g. DA-38 closed 6/11). None when the index has no
    ``next_steps``."""
    steps = story().get("next_steps")
    if not isinstance(steps, list):
        return None
    past = _historical_tickets(say, story())
    out = []
    for e in steps:
        if not _shown(e) or str(e.get("round") or "") != rid or e.get("historical") or e.get("closed") or e.get("handled_by"):
            continue
        if any(_word_in(t, " ".join(str(v) for v in e.values())) for t in past):
            continue  # work already closed or handled elsewhere (DA-38, DA-37)
        out.append(_row("OPTION", text=_say_text(say, e.get("text"))))
        sources.append(e.get("doc"))
    return out


def _past_state(say: Say, c: dict[str, Any]) -> str:
    """The state of an intervention marked ``historical``: closed on a date (DA-38, 6/11), or
    handled by later work (``handled_by``: DA-42, the scorer of version 2)."""
    if c.get("handled_by"):
        return say(f"đã xử lý ở {c['handled_by']}", f"handled by {c['handled_by']}")
    if c.get("closed"):
        return say(f"đã đóng {c['closed']}", f"closed {c['closed']}")
    return say("đã xong", "done")


def _historical_tickets(say: Say, s: dict[str, Any]) -> dict[str, str]:
    """Tickets of an intervention marked ``historical`` (index PR #266: ``closed`` or
    ``handled_by``), with their state; such work is never offered as a next step."""
    out: dict[str, str] = {}
    d: dict[str, Any] = s["diag"] if isinstance(s.get("diag"), dict) else {}
    dg = (s.get("demo") or {}).get("diagnose") or {}
    items = [*((s.get("round") or {}).get("clusters") or []), *(d.get("clusters") or []), *(d.get("step4") or []), *(dg.get("checks") or [])]
    for c in items:
        if isinstance(c, dict) and c.get("historical"):
            v = c["value"] if isinstance(c.get("value"), dict) else {}
            found = [str(c.get("ticket") or v.get("ticket") or "")] + re.findall(r"\b[A-Z]{2,}-\d+\b", str(c.get("intervention") or ""))
            for t in found:
                if t:
                    out.setdefault(t, _past_state(say, c))
    for t in dg.get("historical") or []:
        out.setdefault(str(t), say("đã xong", "done"))
    return out


def _latest(say: Say) -> dict[str, Any]:
    """{latest, latest_date} from ``story.latest``; {missing} when the index has none."""
    lt = story().get("latest")
    if isinstance(lt, dict) and lt.get("run") and _shown(lt):
        return {"latest": lt.get("run"), "latest_round": lt.get("round"), "latest_date": lt.get("date")}
    return {"missing": say("kết quả mới nhất", "latest result")}


def _pick(args: dict[str, Any], ctx: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    m = manifest()
    tasks = [t for t in m.get("tasks") or [] if isinstance(t, dict)]
    # a task named in the question wins over the one selected in the top bar; the model passes no task
    q = " " + str(ctx.get("question") or "").lower() + " "
    named = None
    for t in tasks:
        tid = str(t.get("id") or "")
        nm: dict[str, Any] = t["name"] if isinstance(t.get("name"), dict) else {}
        words = [tid, tid.replace("_", " "), tid.replace("_", "-"), str(nm.get("vi") or ""), str(nm.get("en") or "")]
        # whole words only: the run id M_NEW must not select a task called "new"
        if any(w and re.search(r"(?<![\w])" + re.escape(w.lower()) + r"(?![\w])", q) for w in words):
            named = tid
            break
    want = named or str(args.get("task") or ctx.get("task") or "")
    task = next((t for t in tasks if t.get("id") == want), None)
    task = task or next((t for t in tasks if t.get("rounds")), None) or (tasks[0] if tasks else None)
    if task is None:
        return None, None
    ids = task.get("rounds") or []
    rid = round_named(ctx.get("question"), ctx.get("round"))
    rid = rid if rid in ids else (ids[0] if ids else "")  # the UI opens on the first round
    rnd = next((r for r in m.get("rounds") or [] if r.get("id") == rid), None)
    return task, rnd


def _stage_word(task: dict[str, Any], sid: Any, say: Say) -> str:
    for s in task.get("stages") or []:
        if s.get("id") == sid:
            return say.name(s)
    return say.step(str(sid))


def _no_round(task: dict[str, Any], say: Say) -> Result:
    """A task without a round: what it has so far, as rows."""
    eps = sum(v.get("episodes") or 0 for k, v in (task.get("catalog_totals") or {}).items() if k != "all" and isinstance(v, dict))
    lines = [_row("TASK", id=task.get("id"), name=say.name(task.get("name")), rounds=0, demonstrations=eps,
                  team_model=say("chưa có", "none yet"), failure_to_data_round=say("chưa chạy", "not run yet"))]  # fmt: skip
    for k, v in (task.get("catalog_totals") or {}).items():
        if k != "all" and isinstance(v, dict):
            lines.append(_row("DATA", group=k, episodes=v.get("episodes")))
    for e in task.get("evals") or []:
        if e.get("n") is not None:
            lines.append(_row("EVAL", label=say.name(e.get("label")), model=say("của tác giả", "the authors'"),
                              successes=e.get("successes"), n=e.get("n"), rate=say.frac(e.get("successes"), e.get("n"))))  # fmt: skip
    cl = task.get("clusters") or {}
    items = (cl.get("items") if isinstance(cl, dict) else []) or []
    for c in items:
        lines.append(_row("FAILURE_GROUP", id=c.get("id"), failed_runs=c.get("members"), step=_stage_word(task, c.get("stage"), say)))
    if items:
        lines.append(_row("DIAGNOSIS", state=say("chưa rõ", "unknown"), why=say("còn một kiểm tra hệ thống chưa chấm", "one system check is not judged yet")))
    have = set(task.get("index") or []) | {"catalog"}
    done = ({"4"} if task.get("evals") else set()) | ({"5"} if items else set())
    todo = [n for n, p in sorted((task.get("process") or {}).items()) if n != "0" and n not in done
            and isinstance(p, dict) and not all(k in have for k in p.get("needs") or [])]  # fmt: skip
    if todo:
        lines.append(_row("STAGES", without_result=", ".join(say.stage(n) for n in todo)))
    return _done({"type": "text", "text": "\n".join(lines)}, lines, [])


def _held_answer(out: Result, say: Say) -> Result:
    """A question about a withheld result gets the W5 sentence as it stands: no model words it."""
    out["answer"] = say(*WITHHELD)
    return out


def round_report(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    say = Say(ctx.get("lang"))
    task, rnd = _pick(args, ctx)
    if task is None:
        return fail("No task manifest in the index (run: fw console index).")
    if rnd is None:
        return _no_round(task, say)
    focus = focus_of(ctx.get("question"))
    extra = focuses_of(ctx.get("question"))[1:] if focus != "held" else []
    if ctx.get("deep") and focus != "held":
        focus = "all"  # a deep analysis reads the whole round: marks, failures, controls, limits
    if focus == "held":
        # the sentence alone; the tool reads no number of any round for it
        text = _row("ROUND", id=rnd.get("id"), result=say(*WITHHELD))
        out = _done({"type": "text", "text": say(*WITHHELD)}, [text], [], rnd.get("id"))
        return _held_answer(out, say)
    if "story.jig" in (rnd.get("index") or []):
        out = _jig_report(task, rnd, say, focus, extra)
    else:
        out = _pair_report(task, rnd, say, focus, extra)
    if out.get("ok") and focus == "best" and LOSS_RX.search(str(ctx.get("question") or "")):
        out["model"] = out["model"] + "\n" + _row("READING", result_measure=say("số lượt thành công khi thi", "successful test runs"),
                                                  training_loss=say("không phải thước đo kết quả", "not a measure of the result"))  # fmt: skip
    out["round"] = str(rnd.get("id"))
    return out


def rounds_side_by_side(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """Two or more rounds the question names, each read by ``round_report`` under its own ROUND
    row, after one row that says they are not comparable and why (W6)."""
    say = Say(ctx.get("lang"))
    want = [str(x) for x in args.get("rounds") or [] if x] or rounds_named(ctx.get("question"))
    cur = str(ctx.get("round") or "")
    want = sorted(dict.fromkeys(want), key=lambda r: r != cur)  # the selected round first
    if len(want) < 2:
        return round_report(args, ctx)
    known = [r for r in (_round_by_id(x) for x in want) if r is not None]
    why: list[str] = []
    for a in known[1:]:
        why += _differs(say, known[0], a)
    why = list(dict.fromkeys(why))
    parts = [_row("SIDE_BY_SIDE", rounds=", ".join(want), comparable=say.yes(not why), why=say("khác ", "different ") + ", ".join(why) if why else None)]
    sources: list[Any] = []
    for rid in want:
        res = round_report({}, {**ctx, "round": rid, "question": "", "deep": False})
        if res.get("round") != rid or not res.get("ok"):
            parts.append(_row("ROUND", id=rid, missing=say("số liệu của vòng trong index", "the round's numbers in the index")))
            continue
        # next-step options are not part of a side-by-side
        parts.append("\n".join(ln for ln in str(res["model"]).splitlines() if ln.strip() and not ln.startswith(("OPTION", "NEXT_ROUND"))))
        sources += res.get("sources") or []
    text = "\n".join(parts)
    out = _done({"type": "text", "text": text}, parts, sources, want[0])
    out["model"] = cap(text, len(want) * MODEL_CHARS)  # one round's room per round
    out["rounds"] = want
    return out


# ------------------------------------------------------------------ jig round (run M)
def _jig_block(rnd: dict[str, Any]) -> dict[str, Any] | None:
    j = story().get("jig") or {}
    if not isinstance(j, dict) or not j.get("evals"):
        return None
    if j.get("round") and j.get("round") != rnd.get("id"):
        return None  # the index holds another round's jig block: never shown under this title
    return j


def _reading(ev: dict[str, Any], scope: str, level: Any = None) -> dict[str, Any]:
    """The index's reading of one rule (``evals[].readings``: rule 1 whole_task, rule 2 per level,
    rule 3 place); {} when the index has none."""
    for r in ev.get("readings") or []:
        if isinstance(r, dict) and r.get("scope") == scope and (level is None or str(r.get("level")) == str(level)):
            return r
    return {}



def _mark(say: Say, reading: dict[str, Any], thr: Any) -> dict[str, str]:
    """A reading of tray-jig.md §2 as the index wrote it (``readings[].verdict``: "met",
    "not_met", or None with ``why``), as {mark, verdict}. The chat never computes a verdict
    itself, so it cannot disagree with the pages (the index reads "at or above" the mark)."""
    t = say.pct(reading.get("threshold", thr)).replace(",0", "").replace(".0", "")
    v = reading.get("verdict")
    if v == "met":
        verdict = say("đạt", "met")
    elif v == "not_met":
        verdict = say("chưa đạt", "not met")
    elif reading.get("why") == "blocked":
        verdict = say("chưa đọc: tập eval chưa khớp luật đọc", "not read: the eval set does not match the reading rules")
    elif not reading:
        verdict = say("index chưa ghi kết quả đọc", "no reading in the index")
    else:
        verdict = say("chưa đọc: chưa có CI", "not read: no CI yet")
    return {"mark": t + (" %" if say.vi else "%"), "verdict": verdict}


KIND_WORD = {"measured": ("thực đo", "measured"), "estimated": ("ước tính", "estimated")}
PART_WORD = {"train": ("train", "training"), "eval": ("eval", "evaluation")}


def _cu(say: Say, x: Any) -> str:
    """56,15 and 6,8 as the docs write them, never 6,80."""
    t = say.num(x, 2)
    return t.rstrip("0").rstrip(",.") if ("," in t or "." in t) else t


def _jig_cost(say: Say, c: dict[str, Any]) -> list[str]:
    """``story.jig.cost`` (PR #258): one row per part with its CU, ``measure_kind`` and ledger
    story, then the total; a part without ``measure_kind`` is said as unlabelled."""
    rows, kinds = [], set()
    for key, v in c.items():
        if not isinstance(v, dict) or v.get("cu") is None:
            continue
        kind = v.get("measure_kind")
        kinds.add(kind)
        kw = KIND_WORD.get(str(kind), (say("chưa ghi thực đo hay ước tính", "not marked measured or estimated"),) * 2)[0 if say.vi else 1]
        pw = PART_WORD.get(str(key), (str(key), str(key)))[0 if say.vi else 1]
        rows.append(_row("COST", part=pw, cu=_cu(say, v["cu"]), kind=kw, story=v.get("story")))
    tk = KIND_WORD.get(str(next(iter(kinds))), ("", ""))[0 if say.vi else 1] if len(kinds) == 1 else None
    return [_row("COST", scope=say("cả vòng", "whole round"), total_cu=_cu(say, c["total_cu"]), kind=tk), *rows]


def _jig_report(task: dict[str, Any], rnd: dict[str, Any], say: Say, focus: str, extra: list[str] | None = None) -> Result:
    j = _jig_block(rnd)
    if j is None:
        return fail(f"The index has no test result for round {rnd.get('id')} (story.jig; run: fw console index). "
                    "No number of another round may be given for it.")  # fmt: skip
    held = set(held_runs())
    ev = next((e for e in j.get("evals") or [] if e.get("run") not in held and (e.get("headline") or {}).get("n")), None)
    if ev is None:
        return fail(f"The index has no test result for round {rnd.get('id')} (run: fw console index).")
    rid = str(rnd.get("id"))
    run = str(ev.get("run"))
    h = ev.get("headline") or {}
    rules = j.get("rules") or rnd.get("rules") or {}
    meta: dict[str, Any] = next((r for r in j.get("runs") or [] if r.get("branch") == run), {})
    out_m: dict[str, Any] = next((o for o in j.get("outcomes") or [] if o.get("run") == run), {})
    n, k = h.get("n"), h.get("successes")
    lv = ev.get("levels") or {}
    sources: list[Any] = [j.get("doc") or rnd.get("doc")]
    src_of: dict[str, list[Any]] = {}  # the doc references of a section, given when it is shown
    whole = _mark(say, _reading(ev, "whole_task"), rules.get("whole_task", 0.8))
    lvl_mark = {key: _mark(say, _reading(ev, "level", key), rules.get("per_level", 0.7)) for key in sorted(lv)}
    F: dict[str, list[str]] = {}
    F["result"] = [_row("RESULT", run=run, scope=say("cả task", "whole task"), successes=k, n=n, rate=say.rate(h.get("p")),
                        ci=say.ci(h.get("ci")), **whole, read_at=say("cận dưới CI", "CI lower bound"))]  # fmt: skip
    F["levels"] = [_row("LEVEL", run=run, level=key, successes=(lv[key] or {}).get("successes"), n=(lv[key] or {}).get("n"),
                        rate=say.rate((lv[key] or {}).get("p")), ci=say.ci((lv[key] or {}).get("ci")), **lvl_mark[key]) for key in sorted(lv)]  # fmt: skip
    pl = ev.get("place") or {}
    if pl.get("n"):
        F["place"] = [_row("PLACE_STEP", run=run, passed=pl.get("successes"), n=pl.get("n"), rate=say.rate(pl.get("p")),
                           ci=say.ci(pl["ci"]) if pl.get("ci") else None, **_mark(say, _reading(ev, "place"), rules.get("place", 0.5)))]  # fmt: skip
    if h.get("wilson"):
        F["interval"] = [_row("INTERVAL", run=run, wilson_95=say.ci(h["wilson"]), use=say("chỉ mô tả", "descriptive only"),
                              marks_read_on=say("CI bootstrap theo điều kiện", "bootstrap CI over conditions"))]  # fmt: skip
    fails = sorted((h.get("failures") or {}).items(), key=lambda kv: -kv[1])
    failed = (n or 0) - (k or 0)
    weak = min(lv, key=lambda key: (lv[key] or {}).get("p", 1)) if lv else None
    if fails and failed:
        F["fails"] = [_row("FAILURES", run=run, scope=say("cả task", "whole task"), failed=failed, n=n, **{say.fail(lab): v for lab, v in fails})]
        for key in sorted(lv):
            x = lv[key] or {}
            lf = sorted((x.get("failures") or {}).items(), key=lambda kv: -kv[1])
            if lf and x.get("n"):
                F["fails"].append(_row("FAILURES", run=run, scope=say(f"mức {key}", f"level {key}"), failed=(x.get("n") or 0) - (x.get("successes") or 0),
                                       n=x.get("n"), **{say.fail(lab): v for lab, v in lf}))  # fmt: skip
        top = fails[0][0]
        F["dominant"] = [_row("MOST_COMMON_FAILURE", run=run, failure=say.fail(top), count=fails[0][1], of_failed=failed,
                              **{say(f"mức_{key}", f"level_{key}"): ((lv.get(key) or {}).get("failures") or {}).get(top, 0) for key in sorted(lv)})]  # fmt: skip
    sp = h.get("step_pass") or {}
    if sp:
        drop = min(zip(list(sp)[1:], [b - a for a, b in zip(list(sp.values()), list(sp.values())[1:])]), key=lambda kv: kv[1], default=None)
        F["steps"] = [_row("STEP_PASS", run=run, step=say.step(s), rate=say.rate(v)) for s, v in sp.items()]
        if drop:
            F["steps"].append(_row("STEP_PASS", run=run, sharpest_drop=say.step(drop[0])))
    rel = out_m.get("relaxed") or {}
    tol = next((t for t in sorted(rel, key=float) if rel[t] == k), None)
    more = [(t, v) for t, v in sorted(rel.items(), key=lambda kv: float(kv[0])) if tol and float(t) > float(tol)][:2]
    if tol and more:
        F["near"] = [_row("NEAR_MISS", run=run, standard_cm=say.num(tol), n=n, **{f"within_{say.num(t)}_cm": v for t, v in more})]
    reps = [r for r in out_m.get("repeats") or [] if r.get("n")]
    if reps:
        F["repeats"] = [_row("REPEATS", run=run, n_each=reps[0].get("n"), successes=", ".join(str(r.get("successes")) for r in reps))]
    # the runs of earlier rounds, side by side: never ranked against this round's run (W6)
    c60 = j.get("compare60") or {}
    prev = _link(task, rnd, "prev")
    prev_rnd = _round_by_id((prev or {}).get("round")) or _round_by_id(_pair_round_id()) or {}
    scene, ver = _scene_of(rnd), _scorer_of(rnd)
    side = [_row("SIDE_BY_SIDE", run=run, round=rid, scene=say.scene(scene), scorer=say.scorer(ver), successes=k, n=n, rate=say.frac(k, n),
                 on_60_rollouts=f"{c60.get('successes')}/{c60.get('n')}" if c60.get("n") and c60.get("run", run) == run else None)]  # fmt: skip
    earlier = [e for e in c60.get("earlier") or [] if e.get("run") not in held and e.get("n")]
    if not earlier and prev:
        earlier = [prev]
    for e in sorted(earlier, key=lambda e: -(e.get("successes") or 0)):
        side.append(_row("SIDE_BY_SIDE", run=e.get("run"), round=(prev or {}).get("round") or prev_rnd.get("id"), scene=say.scene(_scene_of(prev_rnd) if prev_rnd else None),
                         scorer=say.scorer(_scorer_of(prev_rnd) if prev_rnd else 1), successes=e.get("successes"), n=e.get("n"), rate=say.frac(e.get("successes"), e.get("n"))))  # fmt: skip
    if len(side) > 1:
        F["side"] = side
        if c60.get("earlier_doc"):
            src_of["side"] = [c60["earlier_doc"]]
    why = _differs(say, prev_rnd, rnd, prev) if prev_rnd else []
    if why:
        F["comparable"] = [_row("LIMITS", comparable="no", with_round=prev_rnd.get("id"), why=say("khác ", "different ") + ", ".join(why))]
    # best: the highest rate of the presented runs, and the latest result
    rates = [(run, (k or 0) / n if n else 0.0)] + [(str(e.get("run")), (e.get("successes") or 0) / e["n"]) for e in earlier if e.get("n")]
    F["reading"] = [_row("READING", highest=max(rates, key=lambda x: x[1])[0], **_latest(say), runs_in_round=len(rnd.get("runs") or []))]
    # where the run comes from: the earlier round's carry and place, then the steps of this round
    origin = []
    if prev:
        origin.append(_row("ORIGIN", round=prev.get("round"), run=prev.get("run"), successes=prev.get("successes"), n=prev.get("n"),
                           carried_to_table_b=prev.get("carried"), placed=prev.get("placed")))  # fmt: skip
    tl = story().get("timeline")
    steps_tl = [e for e in tl if _shown(e) and str(e.get("round") or "") == rid] if isinstance(tl, list) else []
    for e in steps_tl:
        origin.append(_row("ORIGIN_STEP", date=e.get("date"), story=e.get("story"), title=_say_text(say, e.get("title")), result=_say_text(say, e.get("result")) or None))
        src_of.setdefault("origin", []).append(e.get("doc"))
    if not steps_tl:
        origin.append(_row("ORIGIN_STEP", run=run, train_steps=meta.get("max_steps") or rnd.get("max_steps"), train_episodes=meta.get("episodes"),
                           missing=say("diễn tiến của vòng (timeline)", "the round's timeline")))  # fmt: skip
    F["origin"] = origin
    if len(rnd.get("runs") or []) <= 1:
        F["control"] = [_row("LIMITS", control_run=say("chưa có run đối chứng K trên cùng tập điều kiện", "no control run K on the same conditions"),
                             effect=say("chưa tách được phần do đồ gá và phần do dữ liệu bước đặt", "the share of the jig and of the placing data cannot be told apart"))]  # fmt: skip
    F["limits"] = [_row("LIMITS", numbers=say("sơ bộ", "preliminary"), train_seeds=1, train_runs=1, where=say("mô phỏng", "simulation"))]
    F["untested"] = [_row("LIMITS", failed_runs_video=say("chưa xem", "not reviewed"), failure_reasons=say("phỏng đoán", "guesses"))]
    if isinstance(j.get("cost"), dict) and j["cost"].get("total_cu") is not None:
        F["cost"] = _jig_cost(say, j["cost"])
    else:
        F["cost"] = [_row("COST", missing=say("chi phí CU của vòng", "the round's CU cost"))]
    # what is still weak, for "what next": the levels and the task below their mark, the main failure
    weak_rows = []
    for key in sorted(lv):
        x = lv[key] or {}
        name = "WEAK" if lvl_mark[key]["verdict"] != say("đạt", "met") else "LEVEL"
        weak_rows.append(_row(name, run=run, level=key, successes=x.get("successes"), n=x.get("n"), rate=say.rate(x.get("p")), **lvl_mark[key]))
    if fails and failed:
        top = fails[0][0]
        at = ((lv.get(weak) or {}).get("failures") or {}).get(top) if weak else None
        weak_rows.append(_row("WEAK", run=run, failure=say.fail(top), count=fails[0][1], of_failed=failed, **({say(f"ở_mức_{weak}", f"at_level_{weak}"): at} if at is not None else {})))
    if whole["verdict"] != say("đạt", "met"):
        lo = (h.get("ci") or [None])[0]
        weak_rows.append(_row("WEAK", run=run, scope=say("cả task", "whole task"), rate=say.rate(h.get("p")), ci_lower=say.rate(lo) if lo is not None else None, **whole))
    F["weak"] = weak_rows
    opts = _next_steps(say, rid, src_of.setdefault("options", []))
    F["options"] = opts if opts else [_row("OPTION", missing=say("việc tiếp theo ghi trong tài liệu", "next steps written in the docs"))]
    PLAN = {
        "verdict": ["result", "levels", "place", "interval", "limits"],
        "best": ["result", "place", "side", "reading", "origin", "comparable", "control"],
        "compare": ["side", "repeats", "result", "levels", "comparable", "control"],
        "fail": ["dominant", "fails", "steps", "near", "untested"],
        "why": ["dominant", "fails", "levels", "near", "untested", "control"],
        "next": ["weak", "options", "control"],
        "cost": ["cost", "result"],
        "steps": ["steps", "place", "dominant"],
        "diag": ["fails", "dominant", "untested"],
        "data": ["origin", "control", "result"],
        "qa": ["result", "fails"],
        "all": ["result", "levels", "place", "fails", "near", "side", "comparable", "control", "interval", "limits"],
    }
    conds = h.get("conditions")
    lines = [_row("ROUND", id=rid, title=f"{say.name(task.get('name'))}, {say.name(rnd.get('title'))}", task=task.get("id"), scene=scene or say("không đồ gá", "none"),
                  scorer=say.scorer(ver), run=run, checkpoint=meta.get("ckpt_step"), n=n, conditions=conds,
                  repeats=n // conds if conds and n else None, unit=say("điều kiện", "condition"))]  # fmt: skip
    for key in _sections(PLAN, focus, extra or []):
        lines += F.get(key) or []
        sources += src_of.get(key, []) if F.get(key) else []
    rows = [{"run": run, "scope": say("cả task", "whole task"), "successes": f"{k}/{n}", "ci": say.ci(h.get("ci")), "reading": f"{whole['verdict']} {whole['mark']}"}]
    for key in sorted(lv):
        x = lv[key] or {}
        rows.append({"run": run, "scope": say(f"mức {key}", f"level {key}"), "successes": f"{x.get('successes')}/{x.get('n')}", "ci": say.ci(x.get("ci")),
                     "reading": f"{lvl_mark[key]['verdict']} {lvl_mark[key]['mark']}"})  # fmt: skip
    ui = table(say.name(rnd.get("title")), cols("run", "scope", "successes", "ci", "reading"), rows, link="#/eval")
    return _done(ui, lines, sources)


# ------------------------------------------------------------------ pair round (DA-34)
def _pair_report(task: dict[str, Any], rnd: dict[str, Any], say: Say, focus: str, extra: list[str] | None = None) -> Result:
    s = story()
    pair, R, demo = s.get("pair") or {}, s.get("round") or {}, s.get("demo") or {}
    # runs whose test result some round does not present (manifest withhold_eval): the tool never
    # reads their result, on any round, so the model cannot be asked into quoting it (A11)
    all_held = set(held_runs())
    held_here = set(rnd.get("withhold_eval") or []) | (all_held & {x.get("id") for x in rnd.get("runs") or []})
    runs = {r.get("run"): r for r in pair.get("runs") or [] if r.get("run") not in all_held}
    cmps = [c for c in pair.get("comparisons") or [] if c.get("variant") not in all_held and c.get("baseline") not in all_held]
    if all_held:
        demo = {**demo, "round1_reading": {}}  # read from a withheld result: never on any round
    spec = {r.get("id"): r for r in rnd.get("runs") or []}
    if not runs or not any(i in runs for i in spec):
        return fail(f"The index has no test results for round {rnd.get('id')} (run: fw console index). "
                    "No number of another round may be given for it.")  # fmt: skip
    rid = str(rnd.get("id"))
    ladder = (demo.get("ladder") or {}).get("runs") or {}
    tol = (demo.get("ladder") or {}).get("standard_cm")
    base, after = rnd.get("baseline"), rnd.get("after_round")
    n = next(iter(runs.values())).get("n")
    b, a = runs.get(base) or {}, runs.get(after) or {}
    lb, la = ladder.get(base) or {}, ladder.get(after) or {}
    sources: list[Any] = [rnd.get("doc")]
    src_of: dict[str, list[Any]] = {}  # the doc references of a section, given when it is shown

    def role(rid_: Any) -> str:
        return say.role((spec.get(rid_) or {}).get("role"))

    F: dict[str, list[str]] = {}
    rows = []
    shown = [i for i in spec if i in runs]
    for i in shown:
        r, lad = runs[i], ladder.get(i) or {}
        rows.append({"model": i, "role": role(i), "train_set": (spec.get(i) or {}).get("train_set"),
                     "successes": f"{r.get('successes')}/{r.get('n')}", "on_table_B": lad.get("on_table_b"), "within_7.5cm": (lad.get("relaxed") or {}).get("7.5")})  # fmt: skip
    order = sorted(shown, key=lambda i: -(runs[i].get("successes") or 0)) if focus in ("best", "verdict") else shown
    F["each"] = [_row("RESULT", run=i, role=role(i), train_set=(spec.get(i) or {}).get("train_set"), successes=runs[i].get("successes"), n=runs[i].get("n"),
                      rate=say.frac(runs[i].get("successes"), runs[i].get("n")), wilson_95=say.ci(runs[i]["wilson"]) if runs[i].get("wilson") else None) for i in order]  # fmt: skip
    bst = pair.get("best") if pair.get("best") in shown else max(shown, key=lambda i: runs[i].get("successes") or 0)
    ws = [runs[i].get("wilson") for i in shown if runs[i].get("wilson")]
    overlap = len(ws) == len(shown) and len(ws) > 1 and max(w[0] for w in ws) < min(w[1] for w in ws)
    sure = [c for c in cmps if not ((c.get("ci") or [0, 0])[0] < 0 < (c.get("ci") or [0, 0])[1])]
    # W3: the highest count, whether the intervals tell the models apart, and how many of the
    # comparisons fixed in advance are decisive
    F["reading"] = [_row("READING", highest=bst, highest_successes=runs[bst].get("successes"), n=n, intervals_overlap=say.yes(overlap) if len(ws) > 1 else None,
                         decisive_comparisons=say(f"{len(sure)} trên {len(cmps)}", f"{len(sure)} of {len(cmps)}") if cmps else None)]  # fmt: skip
    if cmps:
        F["comparisons"] = [_row("COMPARISONS", fixed_in_advance=len(cmps), decisive=len(sure), all_ci_include_0=say.yes(not sure))]
    if b and a:
        F["outcome"] = [_row("BEFORE_AFTER", before_run=base, before_successes=b.get("successes"), after_run=after, after_successes=a.get("successes"), n=n)]
    if lb.get("on_table_b") is not None:
        F["strength"] = [_row("CARRY_PLACE", run=base, role=role(base), carried_to_table_b=lb["on_table_b"], placed_within_cm=tol, placed=b.get("successes"), n=n,
                              weak_point=say("độ chính xác lúc đặt", "precision at placing"))]  # fmt: skip
    fails = sorted((b.get("failures") or {}).items(), key=lambda kv: -kv[1])
    failed = n - b.get("successes", 0) if n else 0
    if fails and failed:
        F["dominant"] = [_row("MOST_COMMON_FAILURE", run=base, role=role(base), failure=say.fail(fails[0][0]), count=fails[0][1], of_failed=failed,
                              then=", ".join(f"{say.fail(x)} {v}" for x, v in fails[1:3]) or None)]  # fmt: skip
    F["fails"] = []
    for i in shown:
        r = runs[i]
        rf = sorted((r.get("failures") or {}).items(), key=lambda kv: -kv[1])
        if rf and r.get("n"):
            F["fails"].append(_row("FAILURES", run=i, failed=(r.get("n") or 0) - (r.get("successes") or 0), n=r.get("n"), **{say.fail(x): v for x, v in rf}))
    cl = R.get("clusters") or []
    dg = demo.get("diagnose") or {}
    ch = R.get("chain") or {}
    to_data = set(dg.get("to_data") or [])
    tickets = dg.get("tickets") or {}
    old = _historical_tickets(say, s)
    if cl:
        big = max((c for c in cl if c.get("n")), key=lambda c: c.get("n", 0), default=None)
        F["diag"] = [_row("DIAGNOSIS", run=base, groups=len(cl), to_data=len(to_data), to_tickets=len(cl) - len(to_data), tickets=", ".join(tickets) or None,
                          largest_group_step=_stage_word(task, big.get("stage"), say) if big else None, largest_group_runs=big.get("n") if big else None)]  # fmt: skip
        if dg.get("source"):
            src_of["diag"] = [dg["source"]]
    if ch.get("generated") and ch.get("selected"):
        # N6 (Hiếu 28/11/2026): the funnel in runs, not "demonstrations generated"
        F["order"] = [_row("DATA_ORDER", generated_runs=ch["generated"], recorded=ch.get("recorded"), passed_filter=ch.get("quality"), selected=ch["selected"])]
    for t, groups in tickets.items():
        F.setdefault("tickets", []).append(_row("TICKET", id=t, groups=len(groups), kind=say("lỗi hệ thống", "system issue"), fixed_by_data="no",
                                                state=old.get(t)))  # fmt: skip
    rd = demo.get("round1_reading") or {}
    rb, ra = (lb.get("relaxed") or {}).get("7.5"), (la.get("relaxed") or {}).get("7.5")
    opts: list[str] = []
    cmp_ = next((c for c in cmps if c.get("variant") == after and c.get("baseline") == base), None)
    if cmp_:
        lo, hi = cmp_.get("ci") or [0, 0]
        d = cmp_.get("variant_succ", 0) - cmp_.get("baseline_succ", 0)
        F["ci"] = [_row("BEFORE_AFTER", diff_runs=f"{d:+d}", n=cmp_.get("n"), ci_pts=f"{100 * lo:+.1f} → {100 * hi:+.1f}".replace(".", "," if say.vi else "."),
                        ci_includes_0=say.yes(lo < 0 < hi))]  # fmt: skip
        if lo < 0 < hi:
            opts.append(_row("OPTION", action=say(f"thi mỗi bản model nhiều hơn {cmp_.get('n')} lượt", f"test each model on more than {cmp_.get('n')} runs"),
                             why=say("CI của mức chênh chứa 0", "the CI of the difference includes 0")))  # fmt: skip
    if None not in (rb, ra) and a:
        nb, na = rb - b.get("successes", 0), ra - a.get("successes", 0)
        F["near"] = [_row("NEAR_MISS", band=say(f"ngoài {tol} cm, trong 7,5 cm", f"outside {tol} cm, within 7.5 cm"), before=nb, after=na)]
        if na > nb:
            opts.append(_row("OPTION", action=say("nhắm dữ liệu tiếp theo vào vài centimet cuối lúc đặt", "aim the next data at the last centimetres of placing"),
                             why=say(f"lượt suýt thành công tăng {nb} → {na}", f"near misses went {nb} → {na}")))  # fmt: skip
    tilt = (rd.get("tilt_at_place") or {}).get("value") or {}
    if base in tilt and after in tilt:
        F["tilt"] = [_row("TILT_AT_PLACE", before=tilt[base], after=tilt[after])]
    if ((rd.get("stop") or {}).get("value") or {}).get("stop"):
        F["decision"] = [_row("DECISION", stage_2=say("không chạy", "not run"), by=say("luật dừng định trước", "the stopping rule fixed in advance"))]
    cost = demo.get("round_cost") or {}
    F["cost"] = []
    if cost.get("total_cu") is not None:
        # N5 (Hiếu 28/11/2026): training and serving apart from collecting the data
        F["cost"].append(_row("COST", scope=say("train và serve", "training and serving"), total_cu=say.num(cost["total_cu"], 2), kind=say("thực đo", "measured"),
                              usd=say.num(cost.get("total_usd"), 2) if cost.get("total_usd") is not None else None))  # fmt: skip
        for x in cost.get("lines") or []:
            if x.get("value") is not None:
                F["cost"].append(_row("COST", part=say(*COST_LINE[x["id"]]) if x.get("id") in COST_LINE else x.get("id"), cu=_cu(say, x.get("value"))))
        ec = (cost.get("eval_client") or {}).get("value") or {}
        if ec.get("hours") is not None:
            F["evalcost"] = [_row("COST", part="eval client", host="rtx3060", hours=say.num(ec["hours"]), cu=ec.get("cu", 0))]
    gq = _gen_qa((s.get("diag") or {}).get("gen_qa_cost")) if isinstance(s.get("diag"), dict) else None
    if gq is not None:
        F["gencost"] = [_row("COST", part=say("sinh và QA dữ liệu", "generating and checking the data"), cu=gq["cu"], host=gq["host"],
                             gen_hours=say.num(gq["gen_hours"], 2) if gq.get("gen_hours") is not None else None,
                             qa_hours=say.num(gq["qa_hours"], 2) if gq.get("qa_hours") is not None else None)]  # fmt: skip
    else:
        F["gencost"] = [_row("COST", part=say("sinh và QA dữ liệu", "generating and checking the data"), missing=say("chưa có trong index", "not in the index yet"))]
    F["untested"] = [_row("LIMITS", place_error_cause=say("chưa kiểm", "not tested"), reasons_now=say("phỏng đoán", "guesses"))]
    steps = b.get("step_pass") or {}
    if steps:
        F["steps"] = [_row("STEP_PASS", run=base, step=_stage_word(task, x, say), rate=say.rate(v)) for x, v in steps.items()]
        drop = min(zip(list(steps)[1:], [q - p for p, q in zip(list(steps.values()), list(steps.values())[1:])]), key=lambda kv: kv[1], default=None)
        if drop:
            F["steps"].append(_row("STEP_PASS", run=base, sharpest_drop=_stage_word(task, drop[0], say)))
    tot = catalog().get("totals") or {}
    if (tot.get("all") or {}).get("episodes"):
        ep = {x: (v or {}).get("episodes") or 0 for x, v in tot.items()}
        F["data"] = [_row("DATA_STORE", unique_episodes=ep.get("all"), egocentric_clips=ep.get("egocentric", 0), teleop=ep.get("teleop", 0),
                          generated_in_sim=ep.get("s1", 0) + ep.get("s2", 0))]  # fmt: skip
    qb = demo.get("qa_bench") or {}
    cl_, ag = qb.get("code_layer") or {}, (qb.get("agent_layer_nemotron") or {}).get("value") or {}
    if cl_.get("planted"):
        F["qa"] = [_row("QA_BENCH", layer=say("lớp mã", "code layer"), caught=cl_.get("caught"), planted=cl_.get("planted"),
                        false_alarms=cl_.get("false_alarms"), clean_units=cl_.get("clean_units"))]  # fmt: skip
        if ag:
            F["qa"].append(_row("QA_BENCH", layer=say("lớp agent", "agent layer"), caught=ag.get("caught"), planted=ag.get("planted"),
                                false_alarms=ag.get("false_alarms"), clean_units=ag.get("clean_units")))  # fmt: skip
    # next steps: those written in the docs for this round, else the ones the numbers point to
    # (never a ticket: closing tickets is work of DA-37/DA-38, not a data step)
    written = _next_steps(say, rid, src_of.setdefault("options", []))
    F["options"] = written if written else opts
    nxt = _link(task, rnd, "next")
    if nxt:
        F["next_round"] = [_row("NEXT_ROUND", round=nxt.get("round"), run=nxt.get("run"), successes=nxt.get("successes"), n=nxt.get("n"),
                                rate=say.frac(nxt.get("successes"), nxt.get("n")), scene_differs=say.yes(nxt.get("scene_differs")),
                                scorer_differs=say.yes(nxt.get("scorer_differs")))]  # fmt: skip
    PLAN = {
        "best": ["each", "reading", "comparisons", "strength"],
        "verdict": ["each", "reading", "comparisons"],
        "fail": ["dominant", "fails", "strength", "diag", "tickets", "untested"],
        "why": ["ci", "outcome", "near", "tilt", "dominant", "strength", "tickets", "untested"],
        "next": ["strength", "dominant", "outcome", "near", "ci", "options", "next_round"],
        "cost": ["cost", "evalcost", "gencost", "order"],
        "steps": ["steps", "strength", "dominant", "diag"],
        "compare": ["each", "reading", "comparisons", "strength"],
        "data": ["data", "order", "qa"],
        "qa": ["qa", "data"],
        "diag": ["diag", "tickets", "untested"],
        "all": ["outcome", "each", "strength", "dominant", "near", "ci", "tickets", "diag", "order", "decision", "cost", "untested", "next_round"],
    }
    if held_here:  # no outcome to lead with; W5 is said only when the question asks for it
        PLAN["why"] = ["dominant", "strength", "tickets", "untested"]
        PLAN["all"] = ["each", "reading", "strength", "dominant", "diag", "order", "tickets", "cost", "untested", "next_round"]
        PLAN["next"] = ["strength", "dominant", "options", "next_round"]
    lines = [_row("ROUND", id=rid, title=f"{say.name(task.get('name'))}, {say.name(rnd.get('title'))}", task=task.get("id"), scene=_scene_of(rnd) or say("không đồ gá", "none"),
                  scorer=say.scorer(_scorer_of(rnd)), n=n, success_within_cm=tol, unit=say("lượt thi", "test run"))]  # fmt: skip
    for key in _sections(PLAN, focus, extra or []):
        lines += F.get(key) or []
        sources += src_of.get(key, []) if F.get(key) else []
    ui = table("Round · " + say.name(rnd.get("title")), cols("model", "role", "train_set", "successes", "on_table_B", "within_7.5cm"), rows, link="#/report")
    return _done(ui, lines, sources)


# ------------------------------------------------------------------ diagnosis and comparisons
def _pair_round_id() -> str:
    """The round whose numbers ``story.pair`` / ``story.round`` hold (DA-34)."""
    return next((str(r["id"]) for r in _rounds() if "story.pair" in (r.get("index") or []) or "story.round" in (r.get("index") or [])), "")


def _loc(c: dict[str, Any], key: str, en: bool) -> Any:
    """``c[key]``, or its English ``c[key + "_en"]`` (seed values the index session adds) when the
    answer is in English; the Vietnamese value when the English one is missing."""
    if en and c.get(f"{key}_en") not in (None, ""):
        return c[f"{key}_en"]
    return c.get(key)


def _check_fields(c: dict[str, Any], en: bool = False) -> dict[str, Any]:
    """A step-4 check as {id, clusters, result, ticket, goes_to}. Accepts story.diag.step4 (``verdict``,
    PR #258, docs/console/api-contract.md §2.2) and the demo.diagnose shape (``value``)."""
    v: dict[str, Any] = c["value"] if isinstance(c.get("value"), dict) else {}
    res = _loc(c, "verdict", en) if c.get("verdict") is not None else c.get("result", v.get("result"))
    return {"id": c.get("id"), "clusters": c.get("clusters", v.get("clusters")), "result": res, "claim": _loc(c, "claim", en),
            "ticket": c.get("ticket", v.get("ticket")), "goes_to": c.get("goes_to", v.get("goes_to")), "source": _src(c.get("source"))}  # fmt: skip


def _src(v: Any) -> str:
    return ", ".join(str(x) for x in v) if isinstance(v, list) else str(v or "")


def _cluster_fields(c: dict[str, Any], to_data: set[str], en: bool = False) -> dict[str, Any]:
    """A failure group as {id, stage, label, level, n, diagnosis, takes, intervention}; accepts
    story.diag.clusters (``key``, ``n_fail``, ``gets_data``) and story.round.clusters."""
    k: dict[str, Any] = c["key"] if isinstance(c.get("key"), dict) else {}
    takes = c.get("gets_data", c.get("to_data"))
    return {"id": c.get("id"), "stage": c.get("stage", k.get("step")), "label": c.get("label", k.get("label")),
            "level": c.get("level", k.get("level")), "n": c.get("n", c.get("n_fail")), "diagnosis": _loc(c, "diagnosis", en),
            "takes": (c.get("id") in to_data) if takes is None else bool(takes), "intervention": _loc(c, "intervention", en)}  # fmt: skip


def _gen_qa(gq: Any) -> dict[str, Any] | None:
    """story.diag.gen_qa_cost as {cu, host, gen_hours, qa_hours}; None when absent or without CU."""
    if not isinstance(gq, dict) or gq.get("cu") is None:
        return None
    g: dict[str, Any] = gq["generation"] if isinstance(gq.get("generation"), dict) else {}
    q: dict[str, Any] = gq["qa"] if isinstance(gq.get("qa"), dict) else {}
    return {"cu": gq["cu"], "host": gq.get("host") or "rtx3060",
            "gen_hours": gq.get("gen_hours", g.get("hours")), "qa_hours": gq.get("qa_hours", q.get("hours"))}  # fmt: skip




def round_diagnosis(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """Failure groups of a round with their diagnosis, the step-4 system checks with their verdict
    and ticket, and the cost of generating and checking the data (``story.diag``), as rows."""
    say = Say(ctx.get("lang"))
    task, rnd = _pick(args, ctx)
    if task is None or rnd is None:
        return fail("No round in the index manifest (run: fw console index).")
    rid = str(rnd.get("id"))
    s = story()
    held = set(held_runs())
    lines = [_row("ROUND", id=rid, title=f"{say.name(task.get('name'))}, {say.name(rnd.get('title'))}", task=task.get("id"))]
    rows: list[dict[str, Any]] = []
    sources: list[Any] = []
    if "story.jig" in (rnd.get("index") or []):
        j = _jig_block(rnd) or {}
        case = next((a for a in j.get("agentqa") or [] if a.get("clusters")), None)
        lines.append(_row("DIAGNOSIS", system_checks=say("chưa có ở vòng này", "none in this round"),
                          groups_c1_c8=say(f"thuộc vòng {_pair_round_id()}", f"belong to round {_pair_round_id()}")))  # fmt: skip
        if case:
            lines.append(_row("AGENT_QA", status=case.get("status"), kind=say("giả thuyết của agent", "the agent's hypotheses"), checked_by_person="no"))
            cl = sorted([c for c in case["clusters"] if c.get("run") not in held], key=lambda c: -(c.get("size") or 0))[:5]
            for c in cl:
                dw = DIAG_WORD.get(str(c.get("diagnosis")), (str(c.get("diagnosis")), str(c.get("diagnosis"))))[0 if say.vi else 1]
                lines.append(_row("CLUSTER", run=c.get("run"), failure=say.fail(c.get("label")), step=say.step(str(c.get("step"))), level=c.get("level"),
                                  runs=c.get("size"), diagnosis=dw, supporting_runs=c.get("support_count", 0)))  # fmt: skip
                rows.append({"cluster": c.get("cluster_id"), "runs": c.get("size"), "diagnosis": dw})
        else:
            lines.append(_row("CLUSTER", missing=say("chẩn đoán của vòng này", "a diagnosis of this round")))
        sources.append(j.get("doc", rnd.get("doc", "")))
    else:
        d: dict[str, Any] = s["diag"] if isinstance(s.get("diag"), dict) else {}
        if d.get("round") and d.get("round") != rid:
            d = {}
        R, dg = s.get("round") or {}, (s.get("demo") or {}).get("diagnose") or {}
        clusters = d.get("clusters") if isinstance(d.get("clusters"), list) else R.get("clusters") or []
        checks: list[Any] = d["step4"] if isinstance(d.get("step4"), list) else dg.get("checks") or []
        to_data = set(dg.get("to_data") or [])
        old = _historical_tickets(say, s)
        if clusters:
            lines.append(_row("DIAGNOSIS", run=rnd.get("baseline"), role=say.role("baseline"), groups=len(clusters)))
            # a cluster's ticket lives on the step-4 check that covers it (story.diag shape)
            ticket_of = {str(x): c["ticket"] for c in map(_check_fields, checks) if c.get("ticket") for x in (c["clusters"] if isinstance(c["clusters"], list) else [])}
            for raw in clusters:
                c = _cluster_fields(raw, to_data, not say.vi)
                tk = ticket_of.get(str(c.get("id")))
                if not tk:
                    m = re.search(r"\b[A-Z]{2,}-\d+\b", str(raw.get("intervention") or ""))
                    tk = m.group(0) if m else None
                takes = c["takes"]
                goes = (say("nhận dữ liệu", "gets data") if takes else c.get("intervention") or (say(f"phiếu {tk}", f"ticket {tk}") if tk else say("không nhận dữ liệu", "gets no data")))
                step = say.step(str(c.get("stage"))) if c.get("stage") not in (None, "—") else say("không gắn bước", "no step")
                lines.append(_row("CLUSTER", id=c.get("id"), step=step, failure=say.fail(c["label"]) if c.get("label") else None, level=c.get("level"),
                                  runs=c.get("n"), diagnosis=c.get("diagnosis") or "—", goes_to=goes,
                                  ticket_state=_past_state(say, raw) if raw.get("historical") else (old.get(tk) if not takes and tk else None)))  # fmt: skip
                rows.append({"cluster": c.get("id"), "runs": c.get("n"), "diagnosis": c.get("diagnosis"), "data": takes})
        else:
            lines.append(_row("CLUSTER", missing=say("cụm lỗi của vòng này", "the failure groups of this round")))
        if checks:
            for raw in checks:
                c = _check_fields(raw, not say.vi)
                cl_ = c["clusters"]
                groups = ", ".join(cl_) if isinstance(cl_, list) else say("mọi cụm", "all groups") if cl_ == "all" else str(cl_ or "")
                res_t = RESULT_VI.get(str(c.get("result")), c.get("result")) if say.vi else c.get("result")
                goes = say("dữ liệu (lỗi của policy)", "data (a policy failure)") if c.get("goes_to") == "data" else None
                lines.append(_row("CHECK", id=c["id"], groups=groups, claim=c.get("claim"), result=res_t, ticket=c.get("ticket"), goes_to=goes,
                                  ticket_state=_past_state(say, raw) if raw.get("historical") else old.get(str(c.get("ticket"))) if c.get("ticket") else None))  # fmt: skip
                sources.append(c.get("source"))
            lines.append(_row("TICKETS", data_budget=say("không tiêu", "none spent"), why=say("thêm dữ liệu không sửa được lỗi hệ thống", "more data cannot fix a system issue")))
        else:
            lines.append(_row("CHECK", missing=say("kết quả kiểm hệ thống của vòng này", "the system checks of this round")))
        gq = _gen_qa(d.get("gen_qa_cost"))
        part = say("sinh và QA dữ liệu", "generating and checking the data")
        if gq is not None:
            lines.append(_row("COST", part=part, cu=gq["cu"], host=gq["host"], gen_hours=say.num(gq["gen_hours"], 2) if gq.get("gen_hours") is not None else None,
                              qa_hours=say.num(gq["qa_hours"], 2) if gq.get("qa_hours") is not None else None))  # fmt: skip
        else:
            lines.append(_row("COST", part=part, missing=say("chưa có trong index", "not in the index yet")))
        sources = [_src(d.get("source")) or _src(dg.get("source")) or rnd.get("doc"), *sources]
    ui = table(say("Chẩn đoán · ", "Diagnosis · ") + say.name(rnd.get("title")), cols("cluster", "runs", "diagnosis", "data"), rows, link="#/diagnose")
    return _done(ui, lines, sources, rid)


def pair_comparisons(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """The comparisons fixed in advance (story.pair), without any withheld run, with their CI and
    McNemar p and a descriptive reading only (W4)."""
    say = Say(ctx.get("lang"))
    held = set(held_runs())
    cmps = [c for c in (story().get("pair") or {}).get("comparisons") or []
            if c.get("variant") not in held and c.get("baseline") not in held]  # fmt: skip
    rid = _pair_round_id()
    if not cmps:
        return fail("The index has no paired comparisons (run: fw console index).")
    _, rnd = _pick(args, ctx)
    pr = _round_by_id(rid) or {}
    lines = [_row("ROUND", id=rid, title=say.name(pr.get("title")) or None, paired_runs=cmps[0].get("n"), pairing=say("theo điều kiện", "by condition"))]
    if rnd is not None and str(rnd.get("id")) != rid:
        lines.append(_row("SCOPE", selected_round=rnd.get("id"), paired_comparisons=say("không có (một run)", "none (one run)"), rows_below=say(f"vòng {rid}", f"round {rid}")))
    rows = []
    for c in cmps:
        lo, hi = (c.get("ci") or [0, 0])[:2]
        d = c.get("diff", (c.get("variant_succ", 0) - c.get("baseline_succ", 0)) / (c.get("n") or 1))
        pts = [say.num(100 * x, 1) for x in (d, lo, hi)]
        pts = [("+" if not t.startswith("-") else "") + t for t in pts]
        reading = (say("CI chứa 0: chưa phân biệt được", "CI includes 0: not told apart") if lo < 0 < hi
                   else say("CI nằm hẳn trên 0", "CI wholly above 0") if lo >= 0 else say("CI nằm hẳn dưới 0", "CI wholly below 0"))  # fmt: skip
        lines.append(_row("COMPARISON", tag=c.get("tag"), variant=c.get("variant"), baseline=c.get("baseline"), variant_successes=c.get("variant_succ"),
                          baseline_successes=c.get("baseline_succ"), n=c.get("n"), diff_pts=pts[0], ci_pts=f"{pts[1]} → {pts[2]}",
                          mcnemar_p=say.num(c.get("mcnemar_p"), 3), reading=reading))  # fmt: skip
        rows.append({"tag": c.get("tag"), "variant": c.get("variant"), "baseline": c.get("baseline"), "diff_pts": round(100 * d, 1), "ci": f"{100 * lo:+.1f}..{100 * hi:+.1f}", "reading": reading})
    lines.append(_row("READING", kind=say("chỉ mô tả", "descriptive only"), ci_includes_0=say("chưa phân biệt được hai bản với số lượt này", "the two models cannot be told apart with this many runs")))
    ui = table(say("Phép so sánh · ", "Comparisons · ") + rid, cols("tag", "variant", "baseline", "diff_pts", "ci", "reading"), rows, link="#/eval")
    return _done(ui, lines, [pr.get("doc")], rid)


def round_context(task_id: Any, round_id: Any, question: Any = None) -> str:
    """One row on the round the user is looking at, for the system prompt (A14)."""
    rid = round_named(question, round_id)
    rnd = _round_by_id(rid)
    if rnd is None:
        return ""
    held = set(held_runs())
    runs = [str(x.get("id")) for x in rnd.get("runs") or [] if x.get("id") not in held]
    kv: dict[str, Any] = {"id": rid, "title": Say("en").name(rnd.get("title")), "runs_shown": ", ".join(runs) or "-"}
    if set(rnd.get("withhold_eval") or []) & {x.get("id") for x in rnd.get("runs") or []}:
        kv["after_round_retest"] = "not presented"
    rules = rnd.get("rules") or {}
    if rules:
        kv |= {"whole_task_mark": f"{round(100 * rules.get('whole_task', 0))}%", "level_mark": f"{round(100 * rules.get('per_level', 0))}%",
               "placing_mark": f"{round(100 * rules.get('place', 0))}%", "read_at": "CI lower bound"}  # fmt: skip
    return _row("SELECTED_ROUND", **kv)


# ------------------------------------------------------------------ egocentric
QA_REASON = {
    "segment_ambiguous": ("đoạn cắt mơ hồ", "ambiguous cut"),
    "hand_pose_nan": ("mất dấu bàn tay", "hand pose lost"),
    "segment_count": ("thiếu đoạn nắm hoặc đặt", "too few segments"),
    "hand_out_of_frame": ("tay ra ngoài khung hình", "hand out of frame"),
    "segments": ("đoạn cắt sai", "bad segments"),
    "pose_low_confidence": ("tay nhận dạng kém tin cậy", "low-confidence hand pose"),
}



def ego_summary(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """The egocentric (human video) pipeline in numbers: clips in, exported, rejected, why."""
    say = Say(ctx.get("lang"))
    h = story().get("h1m") or {}
    if not h.get("clips"):
        return fail("The index has no egocentric export summary (run: fw console index).")
    d, q = h.get("decisions") or {}, h.get("qa") or {}
    why = sorted((h.get("qa_reasons") or {}).items(), key=lambda kv: -kv[1])[:3]
    lines = [
        _row("EGO_PIPELINE", clips_in=h.get("clips"), exported_episodes=d.get("exported"), rejected_by_checks=d.get("rejected_qa"), left_out=d.get("excluded")),
        _row("EGO_QA", clips=h.get("clips"), passed=q.get("pass"), flagged=q.get("flag"), rejected=q.get("reject"),
             flagged_means=say("vẫn dùng được, có ghi chú", "usable, with a note")),  # fmt: skip
        *(_row("EGO_QA_REASON", reason=QA_REASON.get(k, (k, k))[0 if say.vi else 1], clips=v) for k, v in why),
        _row("EGO_EXPORT", minutes=f"{60 * (h.get('exported_hours') or 0):.0f}",
             episodes_hands_visible_over_95_pct_frames=f"{100 * (h.get('exported_hands_visible_ge_95') or 0):.0f}" + (" %" if say.vi else "%")),  # fmt: skip
    ]
    return _done({"type": "text", "text": "\n".join(lines)}, lines, [h.get("source")] if isinstance(h.get("source"), str) else [])
