# ruff: noqa: E501  (one fact per line of the model text)
"""``round_report`` and its two companions: the facts of one task's round, for analysis questions.

"What do you make of the results", "why did the round not help", "what next", "which model has
the most successes", "what did the round cost" need the test results, the reading rules, the
diagnosis, the data order, the outcome and the cost side by side. The tools read them from the
console index (``tasks.json`` for the task, its rounds and the role of each model, ``story.json``
for the numbers) and write them as full sentences in the language of the question
(``ctx["lang"]``: vi or en), because a small model that has to translate a fact gets it wrong.
They also compute the points worth raising and the options that follow from them, so the model
comments on what the pages show and cites nothing else.

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
    Result,
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
# failure labels of the scorer, in plain words
FAIL = {
    "L-PLACE-POSE": ("đặt lệch vị trí", "placed off target"),
    "L-TRAY-TILT": ("vật bị nghiêng", "object tilted"),
    "L-TIMEOUT": ("hết giờ", "ran out of time"),
    "L-ONE-HAND": ("chỉ cầm một tay", "held with one hand"),
    "L-PART-DROP": ("rơi vật", "dropped a part"),
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
SIDE_BY_SIDE = ("Hai vòng khác cảnh, tập eval, bộ chấm và số bước, nên chỉ đặt cạnh nhau, không so như một kết quả: không viết vòng nào tốt hơn hay tăng bao nhiêu.",
                "The two rounds differ in scene, eval set, scorer and number of steps, so they are only placed side by side, not compared as a result: never write which is better or by how much.")  # fmt: skip


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
    return next((k for k, rx in FOCUS if rx.search(q)), "all")


def focuses_of(question: Any) -> list[str]:
    """Every part the question asks about, in FOCUS order ("đạt mốc 80% không, và đặt cạnh bảng
    60 rollout" asks for the verdict and the comparison)."""
    q = str(question or "")
    return [k for k, rx in FOCUS if rx.search(q)]


def _with_extra(plan: dict[str, tuple[str | None, list[str]]], focus: str, extra: list[str]) -> tuple[str | None, list[str]]:
    """The facts of the main focus, then the lead and facts of each other focus of the question."""
    first, more = plan.get(focus, plan["all"])
    more = list(more)
    for e in extra:
        if e != focus and e in plan:
            f2, m2 = plan[e]
            more += ([f2] if f2 else []) + list(m2)
    return first, list(dict.fromkeys(more))


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

    def fail(self, label: str) -> str:
        w = FAIL.get(label)
        return f"{w[0 if self.vi else 1]} ({label})" if w else label

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

    def ci(self, ci: Any) -> str:
        lo, hi = (ci or [None, None])[:2]
        return f"{self.pct(lo)}–{self.pct(hi)}"

    def count(self, n: int) -> str:
        return COUNT_VI.get(n, str(n)) if self.vi else str(n)


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _pct(k: Any, n: Any) -> str:
    return f"{k}/{n} ({100 * k / n:.0f}%)" if isinstance(k, int) and isinstance(n, int) and n else f"{k}/{n}"


def _succ(say: Say, k: Any, n: Any) -> str:
    """W1: a count of runs is "lượt thành công", never "đạt"."""
    return say(f"{_pct(k, n)} lượt thành công", f"{_pct(k, n)} successful runs")


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
    name = say.name(task.get("name"))
    eps = sum(v.get("episodes") or 0 for k, v in (task.get("catalog_totals") or {}).items() if k != "all" and isinstance(v, dict))
    lines = [say("CÂU TRẢ LỜI THẲNG (mở đầu bằng câu này):", "DIRECT ANSWER (open with this sentence):"),
             say(f"- Task {name} mới đi được phần đầu của dây chuyền: có {eps} bài mẫu trong kho và kết quả thi của model tác giả, chưa có model do đội dạy và chưa chạy vòng Lỗi → Dữ liệu nào.",
                 f"- The task {name} has gone through the first part of the pipeline only: {eps} demonstrations in the store and a test of the authors' model; no model trained by the team and no Failure → Data round yet.")]  # fmt: skip
    lines.append(say("SỐ LIỆU:", "NUMBERS:"))
    for k, v in (task.get("catalog_totals") or {}).items():
        if k != "all" and isinstance(v, dict):
            lines.append(say(f"- Dữ liệu {k} trong kho: {v.get('episodes')} bài mẫu.", f"- {k} data in the store: {v.get('episodes')} demonstrations."))
    for e in task.get("evals") or []:
        if e.get("n") is not None:
            lines.append(say(f"- Lượt thi ({say.name(e.get('label'))}): {_succ(say, e.get('successes'), e.get('n'))}. Đây là model của tác giả, chưa phải model đội dạy.",
                             f"- Test ({say.name(e.get('label'))}): {_succ(say, e.get('successes'), e.get('n'))}. This is the authors' model, not one the team trained."))  # fmt: skip
    cl = task.get("clusters") or {}
    items = (cl.get("items") if isinstance(cl, dict) else []) or []
    for c in items:
        st = _stage_word(task, c.get("stage"), say)
        lines.append(say(f"- Nhóm lỗi {c.get('id')}: {c.get('members')} lượt hỏng ở bước {st}.", f"- Failure group {c.get('id')}: {c.get('members')} failed runs at step {st}."))
    if items:
        lines.append(say("- Chẩn đoán của các nhóm lỗi: chưa rõ, vì còn một kiểm tra hệ thống chưa được chấm nên chưa được phép nêu nguyên nhân.",
                         "- Diagnosis of the failure groups: unknown, because one system check is not judged yet, so no cause may be named."))  # fmt: skip
    have = set(task.get("index") or []) | {"catalog"}
    done = ({"4"} if task.get("evals") else set()) | ({"5"} if items else set())
    todo = [n for n, p in sorted((task.get("process") or {}).items()) if n != "0" and n not in done
            and isinstance(p, dict) and not all(k in have for k in p.get("needs") or [])]  # fmt: skip
    lines.append(say("ĐIỂM ĐÁNG NÓI:", "POINTS TO RAISE:"))
    if todo:
        lines.append(say("- Các bước chưa có kết quả: " + ", ".join(say.stage(n) for n in todo) + ". Task mới đi được một phần dây chuyền.",
                         "- Stages without a result yet: " + ", ".join(say.stage(n) for n in todo) + ". The task has gone through part of the pipeline only."))  # fmt: skip
    lines.append(say("- Kết quả thi hiện có chỉ cho biết model của tác giả làm được đến đâu, chưa nói gì về dữ liệu của đội.",
                     "- The test result so far shows how far the authors' model gets; it says nothing about the team's data yet."))  # fmt: skip
    lines.append(say("PHƯƠNG ÁN BƯỚC TIẾP (đề xuất, chưa phải quyết định):", "OPTIONS FOR NEXT STEPS (proposals, not decisions):"))
    if todo:
        lines.append(say(f"- Chạy bước {say.stage(todo[0])} cho task này trước.", f"- Run stage {say.stage(todo[0])} for this task first."))
    if items:
        lines.append(say("- Chấm xong kiểm tra hệ thống còn treo, để các nhóm lỗi có chẩn đoán rồi mới đặt đơn dữ liệu.",
                         "- Settle the open system check so the failure groups get a diagnosis before a data order is placed."))  # fmt: skip
    lines.append(_how(say, "all"))
    text = "\n".join(lines)
    return result({"type": "text", "text": text}, text)


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
        text = say("CÂU TRẢ LỜI THẲNG: " + WITHHELD[0], "DIRECT ANSWER: " + WITHHELD[1])
        out = result({"type": "text", "text": text}, text)
        out["round"] = str(rnd.get("id"))
        return _held_answer(out, say)
    if "story.jig" in (rnd.get("index") or []):
        out = _jig_report(task, rnd, say, focus, extra)
    else:
        out = _pair_report(task, rnd, say, focus, extra)
    out["round"] = str(rnd.get("id"))
    return out


def rounds_side_by_side(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """Two or more rounds the question names, each read by ``round_report`` under its own title,
    with the W6 sentence first: they are placed side by side, never compared as a result."""
    say = Say(ctx.get("lang"))
    want = [str(x) for x in args.get("rounds") or [] if x] or rounds_named(ctx.get("question"))
    cur = str(ctx.get("round") or "")
    want = sorted(dict.fromkeys(want), key=lambda r: r != cur)  # the selected round first
    if len(want) < 2:
        return round_report(args, ctx)
    parts = [say("CÂU TRẢ LỜI THẲNG (mở đầu bằng câu này): " + SIDE_BY_SIDE[0],
                 "DIRECT ANSWER (open with this sentence): " + SIDE_BY_SIDE[1])]  # fmt: skip
    for rid in want:
        res = round_report({}, {**ctx, "round": rid, "question": "", "deep": False})
        if res.get("round") != rid:
            parts.append(say(f"VÒNG {rid}: index chưa có số liệu của vòng này.", f"ROUND {rid}: the index has no numbers for this round."))
            continue
        how = _how(say, "all")
        body = [ln for ln in str(res["model"]).splitlines() if ln.strip() and ln != how]
        # each round's own "direct answer" is one of its points here; the answer opens with W6
        body = [re.sub(r"^(CÂU TRẢ LỜI THẲNG|DIRECT ANSWER)\b[^:]*:", say("Ý CHÍNH CỦA VÒNG NÀY:", "KEY POINT OF THIS ROUND:"), ln) for ln in body]
        parts.append("\n".join(body))
    parts.append(say("CÁCH TRẢ LỜI: câu trả lời thẳng ở trên, rồi với mỗi vòng một hoặc hai câu (kết quả, chỗ hỏng, chi phí), nêu tên vòng và run cho mọi số; giữ số của mỗi vòng dưới tên vòng đó.",
                     "HOW TO ANSWER: the direct answer above, then one or two sentences per round (result, where it fails, cost), naming the round and run for every number; keep each round's numbers under its own name."))  # fmt: skip
    text = "\n\n".join(parts)
    out = result({"type": "text", "text": text}, text)
    out["round"] = want[0]  # the selected round; the others are named in the text
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


def _verdict(say: Say, reading: dict[str, Any], thr: Any, what: str) -> str:
    """Reading rules 1-3 of tray-jig.md §2 as the index wrote them (``readings[].verdict``: "met",
    "not_met", or None with ``why``). The chat never computes a verdict itself, so it cannot
    disagree with the pages (the index reads "at or above" the mark, after rounding)."""
    t = say.pct(reading.get("threshold", thr)).replace(",0", "").replace(".0", "")
    v = reading.get("verdict")
    if v not in ("met", "not_met"):
        if reading.get("why") == "blocked":
            return say(f"chưa đọc theo mốc {t} % vì tập eval chưa khớp luật đọc", f"not read against the {t}% mark: the eval set does not match the reading rules")
        if not reading:
            return say(f"index chưa ghi kết quả đọc theo mốc {t} %", f"the index has no reading against the {t}% mark")
        return say(f"chưa có CI nên chưa đọc theo mốc {t} %", f"no CI yet, so not read against the {t}% mark")
    met = v == "met"
    return say(f"đạt mốc {t} %", f"meets the {t}% mark") if met else say(f"chưa đạt mốc {t} %", f"below the {t}% mark")


KIND_WORD = {"measured": ("thực đo", "measured"), "estimated": ("ước tính", "estimated")}
PART_WORD = {"train": ("train", "training"), "eval": ("eval", "evaluation")}


def _jig_cost(say: Say, c: dict[str, Any]) -> str:
    """``story.jig.cost`` (PR #258): each part with its CU, its ``measure_kind`` and its ledger
    story, then the total; a part without ``measure_kind`` is said as unlabelled."""
    def cu(x: Any) -> str:  # 56,15 and 6,8 as the doc writes them, never 6,80
        t = say.num(x, 2)
        return t.rstrip("0").rstrip(",.") if ("," in t or "." in t) else t

    parts = []
    kinds = set()
    for key, v in c.items():
        if not isinstance(v, dict) or v.get("cu") is None:
            continue
        kind = v.get("measure_kind")
        kinds.add(kind)
        kw = KIND_WORD.get(str(kind), (say("chưa ghi thực đo hay ước tính", "not marked measured or estimated"),) * 2)[0 if say.vi else 1]
        pw = PART_WORD.get(str(key), (str(key), str(key)))[0 if say.vi else 1]
        story_id = f", {v['story']}" if v.get("story") else ""
        parts.append(f"{pw} {cu(v['cu'])} CU ({kw}{story_id})")
    total = cu(c["total_cu"])
    tk = KIND_WORD.get(str(next(iter(kinds))), ("", ""))[0 if say.vi else 1] if len(kinds) == 1 else ""
    head = say(f"Chi phí của vòng: {total} CU" + (f" {tk}" if tk else ""), f"Cost of the round: {total} CU" + (f" {tk}" if tk else ""))
    return head + (say(", gồm ", ", made of ") + say(" và ", " and ").join(parts) if parts else "") + "."


def _jig_report(task: dict[str, Any], rnd: dict[str, Any], say: Say, focus: str, extra: list[str] | None = None) -> Result:
    j = _jig_block(rnd)
    if j is None:
        return fail(f"The index has no test result for round {rnd.get('id')} (story.jig; run: fw console index). "
                    "No number of another round may be given for it.")  # fmt: skip
    held = set(held_runs())
    ev = next((e for e in j.get("evals") or [] if e.get("run") not in held and (e.get("headline") or {}).get("n")), None)
    if ev is None:
        return fail(f"The index has no test result for round {rnd.get('id')} (run: fw console index).")
    run = str(ev.get("run"))
    h = ev.get("headline") or {}
    rules = j.get("rules") or rnd.get("rules") or {}
    meta: dict[str, Any] = next((r for r in j.get("runs") or [] if r.get("branch") == run), {})
    ckpt = meta.get("ckpt_step")
    out_m: dict[str, Any] = next((o for o in j.get("outcomes") or [] if o.get("run") == run), {})
    n, k = h.get("n"), h.get("successes")
    lv = ev.get("levels") or {}
    F: dict[str, str] = {}
    src = j.get("doc") or rnd.get("doc") or ""
    F["headline"] = say(f"Run {run}: cả task {say.pct(h.get('p'))} % ({k}/{n} lượt thành công), CI {say.ci(h.get('ci'))}: {_verdict(say, _reading(ev, 'whole_task'), rules.get('whole_task', 0.8), 'task')} (đọc ở cận dưới của CI, luật 1).",
                        f"Run {run}: whole task {say.pct(h.get('p'))}% ({k}/{n} successful runs), CI {say.ci(h.get('ci'))}: {_verdict(say, _reading(ev, 'whole_task'), rules.get('whole_task', 0.8), 'task')} (read at the CI lower bound, rule 1).")  # fmt: skip
    lvl_txt = []
    for key in sorted(lv):
        x = lv[key] or {}
        lvl_txt.append(say(f"mức {key}: {say.pct(x.get('p'))} % ({x.get('successes')}/{x.get('n')}), CI {say.ci(x.get('ci'))}, {_verdict(say, _reading(ev, 'level', key), rules.get('per_level', 0.7), 'level')}",
                           f"level {key}: {say.pct(x.get('p'))}% ({x.get('successes')}/{x.get('n')}), CI {say.ci(x.get('ci'))}, {_verdict(say, _reading(ev, 'level', key), rules.get('per_level', 0.7), 'level')}"))  # fmt: skip
    if lvl_txt:
        F["levels"] = say("Từng mức (luật 2): ", "Per level (rule 2): ") + "; ".join(lvl_txt) + "."
    pl = ev.get("place") or {}
    if pl.get("n"):
        ci_txt = say(f", CI {say.ci(pl['ci'])}", f", CI {say.ci(pl['ci'])}") if pl.get("ci") else ""
        F["place"] = say(f"Bước đặt (luật 3): {say.pct(pl.get('p'))} % ({pl.get('successes')}/{pl.get('n')} lượt qua bước đặt){ci_txt}, {_verdict(say, _reading(ev, 'place'), rules.get('place', 0.5), 'place')}.",
                         f"Placing step (rule 3): {say.pct(pl.get('p'))}% ({pl.get('successes')}/{pl.get('n')} runs pass the placing step){ci_txt}, {_verdict(say, _reading(ev, 'place'), rules.get('place', 0.5), 'place')}.")  # fmt: skip
    if h.get("wilson"):
        F["wilson"] = say(f"Khoảng Wilson 95 % ({say.ci(h['wilson'])}) chỉ để mô tả; CI để đọc luật là bootstrap theo điều kiện.",
                          f"The Wilson 95% interval ({say.ci(h['wilson'])}) is descriptive only; the CI used by the rules is a bootstrap over conditions.")  # fmt: skip
    fails = sorted((h.get("failures") or {}).items(), key=lambda kv: -kv[1])
    failed = (n or 0) - (k or 0)
    if fails and failed:
        per = []
        for lab, v in fails:
            by = [f"{say('mức', 'level')} {key} {((lv.get(key) or {}).get('failures') or {}).get(lab, 0)}" for key in sorted(lv)]
            per.append(f"{say.fail(lab)} {v}" + (f" ({', '.join(by)})" if by else ""))
        F["fails"] = say(f"Nhãn lỗi của {failed} lượt hỏng: " + "; ".join(per) + ".", f"Failure labels of the {failed} failed runs: " + "; ".join(per) + ".")
        F["dominant"] = say(f"Lỗi nhiều nhất là {say.fail(fails[0][0])}: {fails[0][1]} trong {failed} lượt hỏng.",
                            f"The most common failure is {say.fail(fails[0][0])}: {fails[0][1]} of {failed} failed runs.")  # fmt: skip
    weak = min(lv, key=lambda key: (lv[key] or {}).get("p", 1)) if lv else None
    sp = h.get("step_pass") or {}
    if sp:
        st = ", ".join(f"{say.step(s)} {say.pct(v)} %" for s, v in sp.items())
        drop = min(zip(list(sp)[1:], [b - a for a, b in zip(list(sp.values()), list(sp.values())[1:])]), key=lambda kv: kv[1], default=None)
        F["steps"] = say(f"Tỉ lệ lượt qua từng bước: {st}." + (f" Tụt mạnh nhất ở bước {say.step(drop[0])}." if drop else ""),
                         f"Share of runs passing each step: {st}." + (f" The sharpest drop is at {say.step(drop[0])}." if drop else ""))  # fmt: skip
    rel = out_m.get("relaxed") or {}
    tol = next((t for t in sorted(rel, key=float) if rel[t] == k), None)
    more = [(t, v) for t, v in sorted(rel.items(), key=lambda kv: float(kv[0])) if tol and float(t) > float(tol)][:2]
    if tol and more:
        F["near"] = say(f"Nới dung sai đặt (chuẩn {say.num(tol)} cm): " + ", ".join(f"{v}/{n} lượt trong {say.num(t)} cm" for t, v in more) + ". Phần lớn lượt đặt lệch nằm gần đích.",
                        f"Relaxing the placing tolerance ({say.num(tol, 1)} cm standard): " + ", ".join(f"{v}/{n} runs within {say.num(t)} cm" for t, v in more) + ". Most off-target placements land near the target.")  # fmt: skip
    reps = [r for r in out_m.get("repeats") or [] if r.get("n")]
    if reps:
        F["repeats"] = say("Ba lượt lặp của cùng tập điều kiện: " + ", ".join(f"{r.get('successes')}/{r.get('n')}" for r in reps) + ".",
                           "The repeats over the same conditions: " + ", ".join(f"{r.get('successes')}/{r.get('n')}" for r in reps) + ".")  # fmt: skip
    c60 = j.get("compare60") or {}
    earlier = [e for e in c60.get("earlier") or [] if e.get("run") not in held]
    if c60.get("n") and earlier:
        side = ", ".join(f"{e.get('run')} {e.get('successes')}/{e.get('n')}" for e in sorted(earlier, key=lambda e: -(e.get("successes") or 0)))
        F["compare60"] = say(f"Đặt cạnh các run của DA-34 trên 60 rollout: {c60.get('run', run)} {c60.get('successes')}/{c60.get('n')} (lượt lặp {c60.get('repeat', 0)}); {side}. Khác cảnh, tập eval, bộ chấm, số bước: chỉ đặt cạnh nhau, không nói tốt hơn hay tăng bao nhiêu (luật 4).",
                             f"Next to the DA-34 runs on 60 rollouts: {c60.get('run', run)} {c60.get('successes')}/{c60.get('n')} (repeat {c60.get('repeat', 0)}); {side}. Different scene, eval set, scorer and number of steps: side by side only, never 'better' or 'up by' (rule 4).")  # fmt: skip
    runs_here = [x.get("id") for x in rnd.get("runs") or []]
    if len(runs_here) <= 1:
        F["rule5"] = say(f"Chưa có run đối chứng K trên cùng tập điều kiện, nên không quy kết quả của run {run} cho dữ liệu bước đặt (luật 5): run {run} đổi cùng lúc cảnh, dữ liệu và số bước.",
                         f"There is no control run K on the same conditions, so run {run}'s result is not credited to the placing data (rule 5): run {run} changed scene, data and number of steps at once.")  # fmt: skip
    F["limits"] = say("Giới hạn: số liệu sơ bộ; một seed train, một lần train, chạy trong mô phỏng.", "Limits: one training seed, one training run, in simulation; the numbers are preliminary.")
    if ckpt:
        F["what"] = say(f"Số chính là của checkpoint {ckpt} (luật 6).", f"The main numbers are those of checkpoint {ckpt} (rule 6).")
    F["untested"] = say("Chưa xem video các lượt hỏng; mọi lý do nêu cho lỗi lúc này là phỏng đoán.", "The failed runs have not been reviewed on video; any reason given for a failure now is a guess.")
    F["cost"] = say("Index chưa có chi phí theo CU của vòng này; xem trang Chi phí.", "The index has no CU cost for this round yet; see the Cost page.")
    if isinstance(j.get("cost"), dict) and j["cost"].get("total_cu") is not None:
        F["cost"] = _jig_cost(say, j["cost"])
    F["source"] = say(f"Nguồn: {src}; index story.jig.", f"Source: {src}; index story.jig.")
    opts: list[str] = []
    if weak and len(lv) > 1:
        wf = sorted(((lv[weak] or {}).get("failures") or {}).items(), key=lambda kv: -kv[1])
        wtxt = say(f", nơi {say.fail(wf[0][0])} chiếm {wf[0][1]} lượt hỏng", f", where {say.fail(wf[0][0])} accounts for {wf[0][1]} failed runs") if wf else ""
        opts.append(say(f"Nhắm dữ liệu tiếp theo vào vài centimet cuối lúc đặt ở mức {weak}{wtxt}.", f"Aim the next data at the last centimetres of placing at level {weak}{wtxt}."))
    if "rule5" in F:
        opts.append(say("Train run K trên cùng tập điều kiện nếu muốn biết dữ liệu bước đặt có giúp không (luật 5).", "Train run K on the same conditions to learn whether the placing data helps (rule 5)."))
    opts.append(say("Thêm seed train, vì số hiện tại đến từ một seed.", "Add training seeds, since the numbers come from one seed."))
    PLAN = {
        "verdict": ("headline", ["levels", "place", "wilson", "limits"]),
        "best": ("headline", ["levels", "compare60", "rule5"]),
        "compare": ("compare60", ["headline", "levels", "rule5", "limits"]),
        "fail": ("dominant", ["fails", "steps", "near", "untested"]),
        "why": ("dominant", ["fails", "levels", "near", "untested", "rule5"]),
        "next": (None, ["headline", "levels", "fails", "rule5"]),
        "cost": ("cost", ["headline"]),
        "steps": ("steps", ["place", "dominant"]),
        "diag": ("fails", ["dominant", "untested"]),
        "data": ("rule5", ["headline"]),
        "qa": ("headline", ["fails"]),
        "all": ("headline", ["levels", "place", "fails", "near", "compare60", "rule5", "wilson", "limits"]),
    }  # fmt: skip
    first, more_k = _with_extra(PLAN, focus, extra or [])
    title = f"{say.name(task.get('name'))}, {say.name(rnd.get('title'))}"
    conds = h.get("conditions")
    lines = [say(f"VÒNG {rnd.get('id')} ({title}). Run {run}" + (f", checkpoint {ckpt}" if ckpt else "") + f", cảnh {j.get('scene', '')}, bộ chấm bản {j.get('scorer_version', '')}: {n} rollout" + (f" ({conds} điều kiện × {n // conds} lượt)" if conds and n else "") + ". Mọi số dưới đây thuộc vòng này; đơn vị thống kê là điều kiện.",
                 f"ROUND {rnd.get('id')} ({title}). Run {run}" + (f", checkpoint {ckpt}" if ckpt else "") + f", scene {j.get('scene', '')}, scorer v{j.get('scorer_version', '')}: {n} rollouts" + (f" ({conds} conditions × {n // conds} repeats)" if conds and n else "") + ". Every number below belongs to this round; the statistical unit is the condition.")]  # fmt: skip
    if first and F.get(first):
        lines += [say("CÂU TRẢ LỜI THẲNG (mở đầu bằng câu này):", "DIRECT ANSWER (open with this sentence):"), "- " + _cap(F[first])]
    lines.append(say("SỐ LIỆU VÀ NHẬN XÉT LIÊN QUAN:", "RELATED NUMBERS AND READINGS:"))
    lines += ["- " + _cap(F[x]) for x in more_k if F.get(x) and x != first]
    if focus in ("next", "why", "all", "fail"):
        lines.append(say("PHƯƠNG ÁN BƯỚC TIẾP (đề xuất, chưa phải quyết định):", "OPTIONS FOR NEXT STEPS (proposals, not decisions):"))
        lines += ["- " + o for o in (opts if focus in ("next", "all") else opts[:1])]
    lines.append("- " + F["source"])
    lines.append(_how(say, focus))
    lines.append(say("QUY TẮC: không gắn số của vòng tray-r1 (DA-34) cho vòng này; không viết 'tốt hơn' hay 'tăng' so với DA-34.",
                     "RULE: never give the numbers of round tray-r1 (DA-34) for this round; never write 'better' or 'up' against DA-34."))  # fmt: skip
    rows = [{"run": run, "scope": say("cả task", "whole task"), "successes": f"{k}/{n}", "ci": say.ci(h.get("ci")), "reading": _verdict(say, _reading(ev, "whole_task"), rules.get("whole_task", 0.8), "task")}]
    for key in sorted(lv):
        x = lv[key] or {}
        rows.append({"run": run, "scope": say(f"mức {key}", f"level {key}"), "successes": f"{x.get('successes')}/{x.get('n')}", "ci": say.ci(x.get("ci")),
                     "reading": _verdict(say, _reading(ev, "level", key), rules.get("per_level", 0.7), "level")})  # fmt: skip
    ui = table(say.name(rnd.get("title")), cols("run", "scope", "successes", "ci", "reading"), rows, link="#/eval")
    return result(ui, "\n".join(lines))


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
    ladder = (demo.get("ladder") or {}).get("runs") or {}
    tol = (demo.get("ladder") or {}).get("standard_cm")
    base, after = rnd.get("baseline"), rnd.get("after_round")
    n = next(iter(runs.values())).get("n")
    b, a = runs.get(base) or {}, runs.get(after) or {}
    lb, la = ladder.get(base) or {}, ladder.get(after) or {}

    def who(rid: Any) -> str:
        return f"{say.role((spec.get(rid) or {}).get('role'))} {rid}"

    F: dict[str, str] = {}  # one sentence per fact, keyed
    rows, each = [], []
    shown = [i for i in spec if i in runs]
    for rid in shown:
        r, lad = runs[rid], ladder.get(rid) or {}
        rel = (lad.get("relaxed") or {}).get("7.5")
        rows.append({"model": rid, "role": say.role((spec.get(rid) or {}).get("role")), "train_set": (spec.get(rid) or {}).get("train_set"),
                     "successes": f"{r.get('successes')}/{r.get('n')}", "on_table_B": lad.get("on_table_b"), "within_7.5cm": rel})  # fmt: skip
        each.append(f"{who(rid)}: {_succ(say, r.get('successes'), r.get('n'))}")
    F["each"] = say("Kết quả thi của từng bản model: ", "Test result of each model: ") + "; ".join(each) + "."
    bst = pair.get("best") if pair.get("best") in shown else max(shown, key=lambda i: runs[i].get("successes") or 0)
    ws = [runs[i].get("wilson") for i in shown if runs[i].get("wilson")]
    overlap = len(ws) == len(shown) and len(ws) > 1 and max(w[0] for w in ws) < min(w[1] for w in ws)
    nocmp = bool(cmps) and all((c.get("ci") or [0, 0])[0] < 0 < (c.get("ci") or [0, 0])[1] for c in cmps)
    k_best = runs[bst].get("successes")
    if overlap or nocmp:
        # W3: no "best": the highest count, and that the intervals do not tell the models apart
        F["best"] = say(f"{who(bst)} có số lượt thành công cao nhất, {k_best}/{n}, nhưng khoảng tin cậy của {say.count(len(shown))} bản chồng nhau, nên chưa phân biệt được.",
                        f"{who(bst)} has the most successful runs, {k_best}/{n}, but the intervals of the {len(shown)} models overlap, so they cannot be told apart.")  # fmt: skip
    else:
        F["best"] = say(f"{who(bst)} có số lượt thành công cao nhất, {k_best}/{n}.", f"{who(bst)} has the most successful runs, {k_best}/{n}.")
    if b and a:
        F["outcome"] = say(f"Trước vòng, {who(base)}: {_succ(say, b.get('successes'), n)}; sau vòng, {who(after)}: {_succ(say, a.get('successes'), n)}.",
                           f"Before the round {who(base)}: {_succ(say, b.get('successes'), n)}; after it {who(after)}: {_succ(say, a.get('successes'), n)}.")  # fmt: skip
    if lb.get("on_table_b") is not None:
        F["strength"] = say(f"Điểm mạnh: robot mang được vật sang bàn đích trong {lb['on_table_b']}/{n} lượt. Điểm yếu: chỉ {b.get('successes')}/{n} lượt đặt đúng trong dung sai {tol} cm. Chỗ hỏng là độ chính xác lúc đặt, không phải lúc đi và mang.",
                            f"Strength: the robot brings the object to the target table in {lb['on_table_b']}/{n} runs. Weakness: only {b.get('successes')}/{n} runs place it within the {tol} cm tolerance. The failure is precision at placing, not walking or carrying.")  # fmt: skip
    fails = sorted((b.get("failures") or {}).items(), key=lambda kv: -kv[1])
    failed = n - b.get("successes", 0) if n else 0
    if fails and failed:
        rest = ", ".join(f"{say.fail(k)} {v}" for k, v in fails[1:3])
        F["dominant"] = say(f"Lỗi nhiều nhất là {say.fail(fails[0][0])}: {fails[0][1]} trong {failed} lượt hỏng của bản gốc. Sau đó là {rest}.",
                            f"The most common failure is {say.fail(fails[0][0])}: {fails[0][1]} of the baseline's {failed} failed runs. Then {rest}.")  # fmt: skip
    cl = R.get("clusters") or []
    dg = demo.get("diagnose") or {}
    ch = R.get("chain") or {}
    to_data = set(dg.get("to_data") or [])
    tickets = dg.get("tickets") or {}
    tk = ", ".join(tickets)
    if cl:
        F["diag"] = say(f"Chẩn đoán chia lỗi của bản gốc thành {len(cl)} nhóm: {len(to_data)} nhóm thành đơn thu dữ liệu, {len(cl) - len(to_data)} nhóm là lỗi hệ thống nên thành phiếu sửa ({tk}).",
                        f"The diagnosis split the baseline's failures into {len(cl)} groups: {len(to_data)} became data orders, {len(cl) - len(to_data)} were system issues and became tickets ({tk}).")  # fmt: skip
        big = max((c for c in cl if c.get("n")), key=lambda c: c.get("n", 0), default=None)
        if big:
            st = _stage_word(task, big.get("stage"), say)
            F["bigstage"] = say(f"Nhóm lỗi lớn nhất nằm ở bước {st}, {big.get('n')} lượt.", f"The largest failure group is at step {st}, {big.get('n')} runs.")
    if ch.get("generated") and ch.get("selected"):
        if ch.get("recorded") and ch.get("quality"):
            # N6 (Hiếu 28/11/2026): the funnel in runs, not "demonstrations generated"
            F["order"] = say(f"Đơn dữ liệu: {ch['generated']} lượt sinh, {ch['recorded']} ghi được, {ch['quality']} qua bộ lọc, chọn {ch['selected']} đưa vào dạy lại.",
                             f"The data order: {ch['generated']} generation runs, {ch['recorded']} recorded, {ch['quality']} through the filter, {ch['selected']} chosen for retraining.")  # fmt: skip
        else:
            F["order"] = say(f"Đơn dữ liệu: {ch['generated']} lượt sinh, chọn {ch['selected']} đưa vào dạy lại.", f"The data order: {ch['generated']} generation runs, {ch['selected']} chosen for retraining.")
    rd = demo.get("round1_reading") or {}
    rb, ra = (lb.get("relaxed") or {}).get("7.5"), (la.get("relaxed") or {}).get("7.5")
    opts: list[str] = []
    if tickets:
        k = sum(len(v) for v in tickets.values())
        F["tickets"] = say(f"{k} nhóm lỗi không phải lỗi dữ liệu và còn mở ở các phiếu {tk}: thu thêm dữ liệu không sửa được chúng.",
                           f"{k} failure groups are not data problems and stay open as tickets {tk}: more data cannot fix them.")  # fmt: skip
        opts.append(say(f"Đóng các phiếu {tk} trước khi đặt đơn dữ liệu tiếp, để các lỗi đang bị che được chẩn đoán.",
                        f"Close the tickets {tk} before the next data order, so the failures they hide can be diagnosed."))  # fmt: skip
    cmp_ = next((c for c in cmps if c.get("variant") == after and c.get("baseline") == base), None)
    if cmp_:
        lo, hi = cmp_.get("ci") or [0, 0]
        d = cmp_.get("variant_succ", 0) - cmp_.get("baseline_succ", 0)
        if lo < 0 < hi:
            pl, ph = f"{100 * lo:+.1f}", f"{100 * hi:+.1f}"
            F["ci"] = say(f"Chưa kết luận được là vòng làm kết quả xấu đi: chênh {d} lượt trên {cmp_.get('n')}, khoảng tin cậy của mức chênh đi từ {pl} đến {ph} điểm phần trăm, còn chứa 0. Với {cmp_.get('n')} lượt thi, khác biệt nhỏ và không khác biệt trông giống nhau.",
                          f"A drop is not established: the difference is {d} runs of {cmp_.get('n')}, and its interval runs from {pl} to {ph} percentage points, which includes 0. With {cmp_.get('n')} test runs a small effect and no effect look the same.")  # fmt: skip
            opts.append(say(f"Cho mỗi bản model thi nhiều hơn {cmp_.get('n')} lượt trước khi kết luận về vòng.", f"Test each model on more than {cmp_.get('n')} runs before judging the round."))
    if None not in (rb, ra) and a:
        nb, na = rb - b.get("successes", 0), ra - a.get("successes", 0)
        F["near"] = say(f"Số lượt suýt thành công (lệch hơn dung sai nhưng chưa quá 7,5 cm) tăng từ {nb} lên {na} sau vòng: dữ liệu mới kéo robot về gần đích hơn nhưng chưa đủ để lọt vào dung sai.",
                        f"Near misses (outside the tolerance but within 7.5 cm) went from {nb} to {na} after the round: the new data pulled the robot closer to the target, not yet inside the tolerance.")  # fmt: skip
        if na > nb:
            opts.append(say("Nhắm đơn dữ liệu tiếp theo vào vài centimet cuối lúc đặt, nơi có các lượt suýt thành công, và báo số lượt trong 7,5 cm cạnh số lượt thành công.",
                            "Aim the next data order at the last centimetres of placing, where the near misses are, and report the 7.5 cm figure next to the success count."))  # fmt: skip
    tilt = (rd.get("tilt_at_place") or {}).get("value") or {}
    if base in tilt and after in tilt:
        F["tilt"] = say(f"Số lượt vật bị nghiêng lúc đặt tăng từ {tilt[base]} lên {tilt[after]} sau vòng.", f"Runs where the object tilted while placing went from {tilt[base]} to {tilt[after]} after the round.")
    if ((rd.get("stop") or {}).get("value") or {}).get("stop"):
        F["decision"] = say("Theo luật đã định trước, vòng dừng ở đây và không chạy giai đoạn 2.", "By the rule fixed in advance the round stops here and stage 2 is not run.")
    cost = demo.get("round_cost") or {}
    if cost.get("total_cu") is not None:
        parts = [f"{say(*COST_LINE[x['id']]) if x.get('id') in COST_LINE else x.get('id')} {say.num(x.get('value'), 2).rstrip('0').rstrip(',.')}" for x in cost.get("lines") or [] if x.get("value") is not None]
        # N5 (Hiếu 28/11/2026): training and serving apart from collecting the data
        F["cost"] = say(f"Train và serve của vòng: {say.num(cost['total_cu'], 2)} CU thực đo, khoảng {say.num(cost.get('total_usd'), 2)} USD" + (f" ({', '.join(parts)})" if parts else "") + ".",
                        f"Training and serving in the round: {say.num(cost['total_cu'], 2)} CU measured, about {say.num(cost.get('total_usd'), 2)} USD" + (f" ({', '.join(parts)})" if parts else "") + ".")  # fmt: skip
        ec = (cost.get("eval_client") or {}).get("value") or {}
        if ec.get("hours") is not None:
            F["evalcost"] = say(f"Eval client chạy trên rtx3060: {say.num(ec['hours'])} giờ, {ec.get('cu', 0)} CU.", f"The eval client ran on rtx3060: {say.num(ec['hours'])} hours, {ec.get('cu', 0)} CU.")
    gq = _gen_qa((s.get("diag") or {}).get("gen_qa_cost")) if isinstance(s.get("diag"), dict) else None
    if gq is not None:
        hrs = [say(f"sinh {say.num(gq['gen_hours'], 2)} giờ", f"generation {say.num(gq['gen_hours'], 2)} h") if gq.get("gen_hours") is not None else "",
               say(f"QA {say.num(gq['qa_hours'], 2)} giờ", f"QA {say.num(gq['qa_hours'], 2)} h") if gq.get("qa_hours") is not None else ""]  # fmt: skip
        hrs_t = ", ".join(x for x in hrs if x)
        F["gencost"] = say(f"Thu dữ liệu {gq['cu']} CU (sinh và QA trên {gq['host']}" + (f": {hrs_t}" if hrs_t else "") + ").",
                           f"Collecting the data: {gq['cu']} CU (generation and QA on {gq['host']}" + (f": {hrs_t}" if hrs_t else "") + ").")  # fmt: skip
    else:
        F["gencost"] = say("Chi phí sinh và QA dữ liệu chưa có trong index.", "The cost of generating and checking the data is not in the index yet.")
    if held_here:
        F["withheld"] = say(*WITHHELD)
    F["untested"] = say("Chưa kiểm vì sao robot đặt lệch; mọi lý do nêu ra lúc này là phỏng đoán.", "Why the robot places off target has not been tested; any reason given now is a guess.")
    steps = b.get("step_pass") or {}
    if steps:
        st_txt = ", ".join(f"{_stage_word(task, k, say)} {100 * v:.0f}%" for k, v in steps.items())
        F["steps"] = say(f"Tỉ lệ lượt thi của bản gốc qua được từng bước: {st_txt}. Tỉ lệ tụt mạnh nhất ở bước đặt.",
                         f"Share of the baseline's test runs that pass each step: {st_txt}. The sharpest drop is at placing.")  # fmt: skip
    if nocmp:
        F["noclear"] = say(f"Trong {len(cmps)} phép so sánh đã định trước, không cặp nào khác biệt chắc chắn: mọi khoảng tin cậy đều chứa 0.",
                           f"Of the {len(cmps)} comparisons fixed in advance, none shows a sure difference: every interval includes 0.")  # fmt: skip
    tot = catalog().get("totals") or {}
    if (tot.get("all") or {}).get("episodes"):
        ep = {k: (v or {}).get("episodes") or 0 for k, v in tot.items()}
        F["data"] = say(f"Cả kho có {ep.get('all')} tập không trùng: {ep.get('egocentric', 0)} clip video người, {ep.get('teleop', 0)} tập teleop và {ep.get('s1', 0) + ep.get('s2', 0)} bài mẫu do máy sinh trong mô phỏng.",
                        f"The store holds {ep.get('all')} unique episodes: {ep.get('egocentric', 0)} human video clips, {ep.get('teleop', 0)} teleop episodes and {ep.get('s1', 0) + ep.get('s2', 0)} demonstrations generated in simulation.")  # fmt: skip
    qb = demo.get("qa_bench") or {}
    cl_, ag = qb.get("code_layer") or {}, (qb.get("agent_layer_nemotron") or {}).get("value") or {}
    if cl_.get("planted"):
        F["qa"] = say(f"Trên bộ lỗi cấy, lớp kiểm bằng mã bắt {cl_.get('caught')}/{cl_.get('planted')} lỗi và báo nhầm {cl_.get('false_alarms')}/{cl_.get('clean_units')} lần trên dữ liệu sạch"
                      + (f"; lớp agent bắt {ag.get('caught')}/{ag.get('planted')} và báo nhầm {ag.get('false_alarms')}/{ag.get('clean_units')}." if ag else "."),
                      f"On the planted-defect set the code layer caught {cl_.get('caught')}/{cl_.get('planted')} defects with {cl_.get('false_alarms')}/{cl_.get('clean_units')} false alarms on clean data"
                      + (f"; the agent layer caught {ag.get('caught')}/{ag.get('planted')} with {ag.get('false_alarms')}/{ag.get('clean_units')} false alarms." if ag else "."))  # fmt: skip
    if rnd.get("doc"):
        F["source"] = say(f"Nguồn: {rnd['doc']}.", f"Source: {rnd['doc']}.")
    # the sentence that answers the question, then the facts that support it
    PLAN = {
        "best": ("best", ["each", "noclear", "strength"]),
        "verdict": ("best", ["each", "noclear"]),
        "fail": ("dominant", ["strength", "bigstage", "tickets", "untested"]),
        "why": ("ci", ["outcome", "near", "tilt", "tickets", "untested"]),
        "next": (None, ["outcome", "strength", "near", "ci", "tickets"]),
        "cost": ("cost", ["gencost", "evalcost", "order"]),
        "steps": ("steps", ["strength", "dominant", "bigstage"]),
        "compare": ("each", ["best", "noclear", "strength"]),
        "data": ("data", ["order", "qa"]),
        "qa": ("qa", ["data"]),
        "diag": ("diag", ["bigstage", "tickets", "untested"]),
        "all": ("outcome", ["strength", "dominant", "near", "ci", "tickets", "diag", "order", "decision", "cost", "untested"]),
    }  # fmt: skip
    if held_here:  # no outcome to lead with: the question about the round gets the plain statement
        PLAN["why"] = ("dominant", ["strength", "tickets", "withheld", "untested"])
        PLAN["all"] = ("best", ["each", "strength", "dominant", "diag", "order", "withheld", "tickets", "cost", "untested"])
        PLAN["next"] = (None, ["strength", "dominant", "tickets", "withheld"])
    first, more = _with_extra(PLAN, focus, extra or [])
    title = f"{say.name(task.get('name'))}, {say.name(rnd.get('title'))}"
    lines = [say(f"VÒNG {rnd.get('id')} ({title}). Mọi bản model thi cùng {n} lượt; một lượt chỉ thành công khi vật nằm trong {tol} cm quanh đích. Mọi số dưới đây thuộc vòng này.",
                 f"ROUND {rnd.get('id')} ({title}). Every model is tested on the same {n} runs; a run succeeds only when the object ends within {tol} cm of the target. Every number below belongs to this round.")]  # fmt: skip
    if first and F.get(first):
        lines += [say("CÂU TRẢ LỜI THẲNG (mở đầu bằng câu này):", "DIRECT ANSWER (open with this sentence):"), "- " + _cap(F[first])]
    lines.append(say("SỐ LIỆU VÀ NHẬN XÉT LIÊN QUAN:", "RELATED NUMBERS AND READINGS:"))
    lines += ["- " + _cap(F[k]) for k in more if F.get(k) and k != first]
    want_opts = focus in ("next", "why", "all", "fail")
    if opts and want_opts:
        lines.append(say("PHƯƠNG ÁN BƯỚC TIẾP (đề xuất, chưa phải quyết định):", "OPTIONS FOR NEXT STEPS (proposals, not decisions):"))
        lines += ["- " + o for o in (opts if focus in ("next", "all") else opts[:1])]
        lines.append(say("ĐÃ LÀM RỒI, đừng đề xuất lại: so sánh các bản model, chẩn đoán, đặt đơn dữ liệu, dạy lại, thi lại.",
                         "ALREADY DONE, do not propose again: comparing the models, the diagnosis, the data order, the retraining, the retest."))  # fmt: skip
    if F.get("source"):
        lines.append("- " + F["source"])
    lines.append(_how(say, focus))
    if held_here:
        lines.append(say(f"QUY TẮC: không viết rằng bản sau vòng chưa thi lại hay chưa có kết quả; nếu nhắc tới thì chỉ viết đúng câu: {WITHHELD[0]} Không xác nhận, không phủ nhận con số người hỏi đưa ra.",
                         f"RULE: never write that the model after the round was not retested or has no result; if you mention it, write only: {WITHHELD[1]} Neither confirm nor deny a figure the user offers."))  # fmt: skip
    ui = table("Round · " + say.name(rnd.get("title")), cols("model", "role", "train_set", "successes", "on_table_B", "within_7.5cm"), rows, link="#/report")
    return result(ui, "\n".join(lines))


def _how(say: Say, focus: str) -> str:
    """How to shape the answer for this kind of question, in the user's language."""
    if focus in ("best", "cost", "steps", "compare", "data", "qa", "diag", "verdict"):
        return say("CÁCH TRẢ LỜI: câu trả lời thẳng, rồi một hoặc hai câu nhận xét lấy từ các ý trên, nêu tên vòng và run cho mọi số. Không chia phần, không thêm việc nên làm.",
                   "HOW TO ANSWER: the direct answer, then one or two sentences of reading taken from the lines above, naming the round once and the run next to each number. No parts, no next steps.")  # fmt: skip
    if focus == "next":
        return say("CÁCH TRẢ LỜI: một câu nêu tình hình, rồi từng phương án ở trên kèm lý do của nó (lấy từ số liệu liên quan). Mở đầu phần phương án bằng 'Việc nên làm:'.",
                   "HOW TO ANSWER: one sentence on where things stand, then each option above with its reason (from the related numbers). Open the options with 'Next steps:'.")  # fmt: skip
    return say("CÁCH TRẢ LỜI: ba phần ngắn có nhãn 'Số liệu:', 'Nhận xét:', 'Việc nên làm:'. Số liệu mở đầu bằng câu trả lời thẳng. Nhận xét dùng hai hoặc ba ý liên quan nhất ở trên và nói rõ ý nào là phỏng đoán. Việc nên làm lấy từ các phương án.",
               "HOW TO ANSWER: three short parts labelled 'Numbers:', 'Reading:', 'Next steps:'. Numbers opens with the direct answer. Reading uses the two or three most relevant lines above and says which is a guess. Next steps come from the options.")  # fmt: skip


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
    and ticket, and the cost of generating and checking the data (``story.diag``)."""
    say = Say(ctx.get("lang"))
    task, rnd = _pick(args, ctx)
    if task is None or rnd is None:
        return fail("No round in the index manifest (run: fw console index).")
    rid = str(rnd.get("id"))
    s = story()
    held = set(held_runs())
    lines = [say(f"VÒNG {rid} ({say.name(rnd.get('title'))}). Mọi số dưới đây thuộc vòng này.", f"ROUND {rid} ({say.name(rnd.get('title'))}). Every number below belongs to this round.")]
    rows: list[dict[str, Any]] = []
    if "story.jig" in (rnd.get("index") or []):
        j = _jig_block(rnd) or {}
        case = next((a for a in j.get("agentqa") or [] if a.get("clusters")), None)
        lines.append(say("Vòng này chưa có bước 4 (kiểm hệ thống) và chưa có cụm lỗi c1–c8; c1–c8 và H1–H3 thuộc vòng tray-r1.",
                         "This round has no step 4 (system checks) and no failure groups c1–c8; c1–c8 and H1–H3 belong to round tray-r1."))  # fmt: skip
        if case:
            cl = sorted([c for c in case["clusters"] if c.get("run") not in held], key=lambda c: -(c.get("size") or 0))[:5]
            lines.append(say(f"Agent QA (ca {case.get('case_id')}, trạng thái {case.get('status')}: giả thuyết của agent, chưa ai kiểm) gom lỗi thành các cụm:",
                             f"Agent QA (case {case.get('case_id')}, status {case.get('status')}: the agent's hypotheses, not checked by anyone) grouped the failures into clusters:"))  # fmt: skip
            for c in cl:
                dw = DIAG_WORD.get(str(c.get("diagnosis")), (str(c.get("diagnosis")), str(c.get("diagnosis"))))[0 if say.vi else 1]
                lines.append(say(f"- {c.get('label')} ở bước {say.step(str(c.get('step')))}, mức {c.get('level')}: {c.get('size')} lượt, chẩn đoán {dw} ({c.get('support_count', 0)} lượt ủng hộ).",
                                 f"- {c.get('label')} at {say.step(str(c.get('step')))}, level {c.get('level')}: {c.get('size')} runs, diagnosis {dw} ({c.get('support_count', 0)} supporting runs)."))  # fmt: skip
                rows.append({"cluster": c.get("cluster_id"), "runs": c.get("size"), "diagnosis": dw})
        else:
            lines.append(say("Index chưa có kết quả chẩn đoán nào cho vòng này.", "The index has no diagnosis for this round."))
        lines.append(say(f"Nguồn: {j.get('doc', rnd.get('doc', ''))}; index story.jig.agentqa.", f"Source: {j.get('doc', rnd.get('doc', ''))}; index story.jig.agentqa."))
    else:
        d: dict[str, Any] = s["diag"] if isinstance(s.get("diag"), dict) else {}
        if d.get("round") and d.get("round") != rid:
            d = {}
        R, dg = s.get("round") or {}, (s.get("demo") or {}).get("diagnose") or {}
        clusters = d.get("clusters") if isinstance(d.get("clusters"), list) else R.get("clusters") or []
        checks: list[Any] = d["step4"] if isinstance(d.get("step4"), list) else dg.get("checks") or []
        to_data = set(dg.get("to_data") or [])
        if clusters:
            lines.append(say(f"Cụm lỗi của bản gốc ({len(clusters)} cụm):", f"Failure groups of the baseline ({len(clusters)} groups):"))
            # a cluster's ticket lives on the step-4 check that covers it (story.diag shape)
            ticket_of = {str(x): c["ticket"] for c in map(_check_fields, checks) if c.get("ticket") for x in (c["clusters"] if isinstance(c["clusters"], list) else [])}
            for c in (_cluster_fields(x, to_data, not say.vi) for x in clusters):
                takes = c["takes"]
                if not takes and not c.get("intervention") and ticket_of.get(str(c.get("id"))):
                    c["intervention"] = say(f"phiếu {ticket_of[str(c.get('id'))]}", f"ticket {ticket_of[str(c.get('id'))]}")
                where = say(f"bước {say.step(str(c.get('stage')))}", f"step {say.step(str(c.get('stage')))}") if c.get("stage") not in (None, "—") else say("không gắn bước", "no step")
                nn = say(f", {c.get('n')} lượt", f", {c.get('n')} runs") if c.get("n") else ""
                goes = say("nhận dữ liệu", "gets data") if takes else (say(f"thành {c.get('intervention')}", f"becomes {c.get('intervention')}") if c.get("intervention") else say("không nhận dữ liệu", "gets no data"))
                lines.append(f"- {c.get('id')}: {where}{nn}; {say('chẩn đoán', 'diagnosis')} {c.get('diagnosis', '—')}; {goes}.")
                rows.append({"cluster": c.get("id"), "runs": c.get("n"), "diagnosis": c.get("diagnosis"), "data": takes})
        else:
            lines.append(say("Index chưa có cụm lỗi của vòng này.", "The index has no failure groups for this round."))
        if checks:
            lines.append(say("Bước 4, kiểm hệ thống trước mọi dữ liệu:", "Step 4, system checks before any data:"))
            for c in (_check_fields(x, not say.vi) for x in checks):
                cl_ = c["clusters"]
                cl_t = ", ".join(cl_) if isinstance(cl_, list) else say("mọi cụm", "all groups") if cl_ == "all" else str(cl_ or "")
                if c.get("claim"):
                    cl_t += f"; {c['claim']}"
                tail = say(f", thành phiếu {c['ticket']}", f", ticket {c['ticket']}") if c.get("ticket") else (say(", đọc là lỗi của policy, đi tiếp sang dữ liệu", ", read as a policy failure, goes on to data") if c.get("goes_to") == "data" else "")
                res_t = RESULT_VI.get(str(c.get("result")), c.get("result")) if say.vi else c.get("result")
                lines.append(f"- {c['id']} ({cl_t}): {res_t}{tail}" + (f" [{c['source']}]" if c.get("source") else "") + ".")
            lines.append(say("Phiếu không tiêu ngân sách dữ liệu: thu thêm dữ liệu không sửa được lỗi hệ thống.", "Tickets spend no data budget: more data cannot fix a system issue."))
        else:
            lines.append(say("Index chưa có kết quả bước 4 của vòng này.", "The index has no step-4 result for this round."))
        gq = _gen_qa(d.get("gen_qa_cost"))
        if gq is not None:
            lines.append(say(f"Chi phí sinh và QA dữ liệu: {gq['cu']} CU trên {gq['host']}" + (f", sinh {say.num(gq['gen_hours'], 2)} giờ" if gq.get("gen_hours") is not None else "") + (f", QA {say.num(gq['qa_hours'], 2)} giờ" if gq.get("qa_hours") is not None else "") + ".",
                             f"Cost of generating and checking the data: {gq['cu']} CU on {gq['host']}" + (f", generation {say.num(gq['gen_hours'], 2)} h" if gq.get("gen_hours") is not None else "") + (f", QA {say.num(gq['qa_hours'], 2)} h" if gq.get("qa_hours") is not None else "") + "."))  # fmt: skip
        else:
            lines.append(say("Chi phí sinh và QA dữ liệu: chưa có trong index.", "Cost of generating and checking the data: not in the index yet."))
        src = _src(d.get("source")) or _src(dg.get("source")) or rnd.get("doc") or ""
        lines.append(say(f"Nguồn: {src}.", f"Source: {src}."))
    lines.append(say("CÁCH TRẢ LỜI: trả lời đúng câu hỏi từ các dòng trên, nêu tên vòng, giữ nguyên chẩn đoán và mã phiếu; phần nào index chưa có thì nói chưa có dữ liệu, không suy diễn lý do.",
                     "HOW TO ANSWER: answer the question from the lines above, name the round, keep the diagnoses and ticket ids as written; where the index has nothing, say so and do not infer a reason."))  # fmt: skip
    out = result(table(say("Chẩn đoán · ", "Diagnosis · ") + say.name(rnd.get("title")), cols("cluster", "runs", "diagnosis", "data"), rows, link="#/diagnose"), "\n".join(lines))
    out["round"] = rid
    return out


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
    lines = []
    if rnd is not None and str(rnd.get("id")) != rid:
        lines.append(say(f"Vòng {rnd.get('id')} chỉ có một run nên không có phép so sánh ghép cặp. Các phép dưới đây thuộc vòng {rid} (DA-34), không phải vòng đang chọn.",
                         f"Round {rnd.get('id')} has one run, so it has no paired comparison. The comparisons below belong to round {rid} (DA-34), not the selected round."))  # fmt: skip
    lines.append(say(f"VÒNG {rid}: các phép so sánh định trước, cùng {cmps[0].get('n')} lượt thi ghép cặp theo điều kiện:", f"ROUND {rid}: comparisons fixed in advance, on the same {cmps[0].get('n')} paired test runs:"))
    rows = []
    for c in cmps:
        lo, hi = (c.get("ci") or [0, 0])[:2]
        d = c.get("diff", (c.get("variant_succ", 0) - c.get("baseline_succ", 0)) / (c.get("n") or 1))
        pts = [say.num(100 * x, 1) for x in (d, lo, hi)]
        pts = [("+" if not t.startswith("-") else "") + t for t in pts]
        reading = (say("CI chứa 0: chưa phân biệt được", "CI includes 0: not told apart") if lo < 0 < hi
                   else say("CI nằm hẳn trên 0", "CI wholly above 0") if lo >= 0 else say("CI nằm hẳn dưới 0", "CI wholly below 0"))  # fmt: skip
        lines.append(say(f"- ({c.get('tag')}) {c.get('variant')} so với {c.get('baseline')}: {c.get('variant_succ')}/{c.get('n')} và {c.get('baseline_succ')}/{c.get('n')}, chênh {pts[0]} điểm, CI {pts[1]} đến {pts[2]}, McNemar p = {say.num(c.get('mcnemar_p'), 3)}; {reading}.",
                         f"- ({c.get('tag')}) {c.get('variant')} vs {c.get('baseline')}: {c.get('variant_succ')}/{c.get('n')} and {c.get('baseline_succ')}/{c.get('n')}, difference {pts[0]} points, CI {pts[1]} to {pts[2]}, McNemar p = {say.num(c.get('mcnemar_p'), 3)}; {reading}."))  # fmt: skip
        rows.append({"tag": c.get("tag"), "variant": c.get("variant"), "baseline": c.get("baseline"), "diff_pts": round(100 * d, 1), "ci": f"{100 * lo:+.1f}..{100 * hi:+.1f}", "reading": reading})
    lines.append(say("Đây chỉ là mô tả; một khoảng tin cậy chứa 0 nghĩa là với số lượt này chưa phân biệt được hai bản.", "This is descriptive only; an interval that includes 0 means the two models cannot be told apart with this many runs."))
    lines.append(say("CÁCH TRẢ LỜI: nêu vòng, từng phép so sánh người hỏi cần với CI của nó, và câu về CI chứa 0. Không viết 'tốt nhất' hay 'tiếp tục'.",
                     "HOW TO ANSWER: name the round, each comparison asked about with its CI, and the sentence on intervals that include 0. Never write 'best' or 'continue'."))  # fmt: skip
    out = result(table(say("Phép so sánh · ", "Comparisons · ") + rid, cols("tag", "variant", "baseline", "diff_pts", "ci", "reading"), rows, link="#/eval"), "\n".join(lines))
    out["round"] = rid
    return out


def round_context(task_id: Any, round_id: Any, question: Any = None) -> str:
    """One line on the round the user is looking at, for the system prompt (A14)."""
    rid = round_named(question, round_id)
    rnd = next((r for r in _rounds() if r["id"] == rid), None)
    if rnd is None:
        return ""
    held = set(held_runs())
    runs = [str(x.get("id")) for x in rnd.get("runs") or [] if x.get("id") not in held]
    txt = f"Selected round: {rid} ({Say('en').name(rnd.get('title'))}); runs shown: {', '.join(runs) or '-'}"
    if set(rnd.get("withhold_eval") or []) & {x.get("id") for x in rnd.get("runs") or []}:
        txt += "; the re-test result of the model after the round is not presented"
    rules = rnd.get("rules") or {}
    if rules:
        txt += (f"; reading rules: whole task {round(100 * rules.get('whole_task', 0))}%, each level {round(100 * rules.get('per_level', 0))}%, "
                f"placing {round(100 * rules.get('place', 0))}%, read at the CI lower bound")  # fmt: skip
    if rnd.get("doc"):
        txt += f"; doc {rnd['doc']}"
    return txt + "."


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
    wt = ", ".join(f"{QA_REASON.get(k, (k, k))[0 if say.vi else 1]} {v}" for k, v in why)
    lines = [
        say("CÂU TRẢ LỜI THẲNG (mở đầu bằng câu này):", "DIRECT ANSWER (open with this sentence):"),
        say(f"- Dây chuyền video người nhận {h.get('clips')} clip: xuất ra {d.get('exported')} episode, kiểm định loại {d.get('rejected_qa')} clip, để ngoài {d.get('excluded')} clip.",
            f"- The human-video pipeline took in {h.get('clips')} clips: {d.get('exported')} episodes exported, {d.get('rejected_qa')} clips rejected by the checks, {d.get('excluded')} left out."),  # fmt: skip
        say("SỐ LIỆU VÀ NHẬN XÉT LIÊN QUAN:", "RELATED NUMBERS AND READINGS:"),
        say(f"- Kết quả kiểm định trên {h.get('clips')} clip: {q.get('pass')} đạt, {q.get('flag')} gắn cờ (vẫn dùng được, có ghi chú), {q.get('reject')} loại.",
            f"- Check results on the {h.get('clips')} clips: {q.get('pass')} pass, {q.get('flag')} flagged (usable, with a note), {q.get('reject')} rejected."),  # fmt: skip
        say(f"- Lý do bị gắn cờ hoặc loại nhiều nhất: {wt}.", f"- Most common reasons for a flag or a reject: {wt}."),
        say(f"- Bản xuất dài {60 * (h.get('exported_hours') or 0):.0f} phút; {100 * (h.get('exported_hands_visible_ge_95') or 0):.0f}% số episode thấy tay trong hơn 95% số khung hình.",
            f"- The export is {60 * (h.get('exported_hours') or 0):.0f} minutes long; {100 * (h.get('exported_hands_visible_ge_95') or 0):.0f}% of its episodes show the hands in over 95% of frames."),  # fmt: skip
        say("- Phần lớn clip bị gắn cờ chứ không đạt hẳn, chủ yếu vì luật cắt đoạn không chắc lúc tay nắm và buông; đây là chỗ cần người duyệt hoặc model gợi ý ranh giới.",
            "- Most clips are flagged rather than passed, mainly because the cutting rule is unsure when the hand grasps and releases; this is where a reviewer or a boundary-suggesting model is needed."),  # fmt: skip
        say("CÁCH TRẢ LỜI: câu trả lời thẳng, rồi một hoặc hai câu nhận xét lấy từ các ý trên.", "HOW TO ANSWER: the direct answer, then one or two sentences of reading taken from the lines above."),
    ]
    text = "\n".join(lines)
    return result({"type": "text", "text": text}, text)
