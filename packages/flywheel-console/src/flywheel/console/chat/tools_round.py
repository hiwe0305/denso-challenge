# ruff: noqa: E501  (one fact per line of the model text)
"""``round_report``: the facts of one task's round in one tool result, for analysis questions.

"What do you make of the results", "why did the round not help", "what next", "which model is
best", "what did the round cost" need the test results, the diagnosis, the data order, the
outcome and the cost side by side. The tool reads them from the console index (``tasks.json``
for the task, its round and the role of each model, ``story.json`` for the numbers) and writes
them as full sentences in the language of the question (``ctx["lang"]``: vi or en), because a
small model that has to translate a fact gets it wrong. It also computes the points worth
raising and the options that follow from them, so the model comments on what the pages show and
cites nothing else. A task without a round reports what exists and says what is missing.
"""

from __future__ import annotations

import re
from typing import Any

from flywheel.console.index import hidden
from flywheel.console.paths import active

from .common import HOSTED, Result, catalog, cols, fail, jload, result, story, table, totals

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
STAGE_NAMES = ("dữ liệu", "kiểm định", "dạy model", "thi và chấm", "chẩn đoán", "lỗi → dữ liệu")
STAGE_NAMES_EN = ("data", "checks", "training", "test and scoring", "diagnosis", "failure → data")


# what the question is after, most specific first; "all" is a general comment on the round
FOCUS = [
    ("why", re.compile(r"vì sao|tại sao|\bwhy\b|chưa tốt|không tốt|không cải thiện|xấu đi|did not (improve|help)|not improve", re.I)),
    ("next", re.compile(r"nên làm|làm gì tiếp|bước tiếp|tiếp theo|what next|next step|should we|what to do", re.I)),
    ("cost", re.compile(r"\btốn\b|chi phí|bao nhiêu tiền|\bcost\b|\bCU\b|\bUSD\b|budget|ngân sách", re.I)),
    ("steps", re.compile(r"bước nào|từng bước|qua từng|which step|each step|per step|step by step", re.I)),
    ("diag", re.compile(r"chẩn đoán|nhóm lỗi|cụm lỗi|phiếu|diagnos|failure group|ticket", re.I)),
    ("fail", re.compile(r"hỏng|lỗi nào|lỗi gì|thất bại|\bfail|failure|điểm yếu|weak", re.I)),
    ("compare", re.compile(r"so sánh|khác nhau|khác gì|\bcompare|difference between", re.I)),
    ("best", re.compile(r"tốt nhất|\bbest\b|bản nào|which model", re.I)),
    ("qa", re.compile(r"kiểm định|lỗi cấy|planted|quality check|inspector", re.I)),
    ("data", re.compile(r"dữ liệu|bài mẫu|\bdata\b|demonstration", re.I)),
]


AFTER_RX = re.compile(r"sau vòng|bản mới|dạy lại|thi lại|after the round|retest|retrain", re.I)


def held_runs() -> list[str]:
    """Run ids whose test result some round of the manifest does not present."""
    return [str(x) for r in manifest().get("rounds") or [] for x in r.get("withhold_eval") or []]


def asks_held(question: Any) -> bool:
    """The question is about a run whose test result is not presented (by id, or 'after the round')."""
    q = str(question or "")
    held = held_runs()
    return bool(held) and (any(h.lower() in q.lower() for h in held) or bool(AFTER_RX.search(q)))


def focus_of(question: Any) -> str:
    q = str(question or "")
    if asks_held(q):
        return "held"
    return next((k for k, rx in FOCUS if rx.search(q)), "all")


def manifest() -> dict[str, Any]:
    d = jload(active().index / "tasks.json", {})
    d = d if isinstance(d, dict) else {}
    shown = hidden.tasks_doc(d, hidden.load(active()))  # withhold_runs, even in a stale index
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

    def role(self, r: Any) -> str:
        w = ROLE.get(str(r))
        return w[0 if self.vi else 1] if w else self("bản model", "model")

    def stage(self, n: str) -> str:
        i = int(n) - 1
        return f"{n} {(STAGE_NAMES if self.vi else STAGE_NAMES_EN)[i]}" if 0 <= i < 6 else n


def _pct(k: Any, n: Any) -> str:
    return f"{k}/{n} ({100 * k / n:.0f}%)" if isinstance(k, int) and isinstance(n, int) and n else f"{k}/{n}"


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
    rid = str(ctx.get("round") or "")
    ids = task.get("rounds") or []
    rid = rid if rid in ids else (ids[-1] if ids else "")
    rnd = next((r for r in m.get("rounds") or [] if r.get("id") == rid), None)
    return task, rnd


def _stage_word(task: dict[str, Any], sid: Any, say: Say) -> str:
    for s in task.get("stages") or []:
        if s.get("id") == sid:
            return say.name(s)
    return str(sid)


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
            lines.append(say(f"- Lượt thi ({say.name(e.get('label'))}): đạt {_pct(e.get('successes'), e.get('n'))}. Đây là model của tác giả, chưa phải model đội dạy.",
                             f"- Test ({say.name(e.get('label'))}): passed {_pct(e.get('successes'), e.get('n'))}. This is the authors' model, not one the team trained."))  # fmt: skip
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


def round_report(args: dict[str, Any], ctx: dict[str, Any]) -> Result:
    say = Say(ctx.get("lang"))
    task, rnd = _pick(args, ctx)
    if task is None:
        return fail("No task manifest in the index (run: fw console index).")
    if rnd is None:
        return _no_round(task, say)
    s = story()
    pair, R, demo = s.get("pair") or {}, s.get("round") or {}, s.get("demo") or {}
    # runs whose test result the round does not present (manifest withhold_eval): the tool never
    # reads their result, so the model cannot be asked into quoting it
    held = set(rnd.get("withhold_eval") or [])
    runs = {r.get("run"): r for r in pair.get("runs") or [] if r.get("run") not in held}
    if held:
        pair = {**pair, "comparisons": [c for c in pair.get("comparisons") or []
                                        if c.get("variant") not in held and c.get("baseline") not in held]}  # fmt: skip
        demo = {**demo, "round1_reading": {}}
    if not runs:
        return fail("The index has no test results for this round (run: fw console index).")
    spec = {r.get("id"): r for r in rnd.get("runs") or []}
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
    for rid in [i for i in spec if i in runs]:
        r, lad = runs[rid], ladder.get(rid) or {}
        rel = (lad.get("relaxed") or {}).get("7.5")
        rows.append({"model": rid, "role": say.role((spec.get(rid) or {}).get("role")), "train_set": (spec.get(rid) or {}).get("train_set"),
                     "passed": f"{r.get('successes')}/{r.get('n')}", "on_table_B": lad.get("on_table_b"), "within_7.5cm": rel})  # fmt: skip
        each.append(say(f"{who(rid)} đạt {_pct(r.get('successes'), r.get('n'))}", f"{who(rid)} passed {_pct(r.get('successes'), r.get('n'))}"))
    F["each"] = say("Kết quả thi của từng bản model: ", "Test result of each model: ") + "; ".join(each) + "."
    if pair.get("best") in runs:
        bst = pair["best"]
        F["best"] = say(f"Bản tốt nhất là {who(bst)}, đạt {_pct(runs[bst].get('successes'), n)} lượt thi.", f"The best model is {who(bst)}, which passed {_pct(runs[bst].get('successes'), n)} test runs.")
    if b and a:
        F["outcome"] = say(f"Trước vòng, {who(base)} đạt {_pct(b.get('successes'), n)}; sau vòng, {who(after)} đạt {_pct(a.get('successes'), n)}.",
                           f"Before the round {who(base)} passed {_pct(b.get('successes'), n)}; after it {who(after)} passed {_pct(a.get('successes'), n)}.")  # fmt: skip
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
        F["order"] = say(f"Đơn dữ liệu sinh {ch.get('generated')} bài mẫu mới; qua kiểm định và chọn lọc còn {ch.get('selected')} bài đưa vào dạy lại.",
                         f"The data order generated {ch.get('generated')} new demonstrations; after checks and selection {ch.get('selected')} went into retraining.")  # fmt: skip
    rd = demo.get("round1_reading") or {}
    rb, ra = (lb.get("relaxed") or {}).get("7.5"), (la.get("relaxed") or {}).get("7.5")
    opts: list[str] = []
    if tickets:
        k = sum(len(v) for v in tickets.values())
        F["tickets"] = say(f"{k} nhóm lỗi không phải lỗi dữ liệu và còn mở ở các phiếu {tk}: thu thêm dữ liệu không sửa được chúng.",
                           f"{k} failure groups are not data problems and stay open as tickets {tk}: more data cannot fix them.")  # fmt: skip
        opts.append(say(f"Đóng các phiếu {tk} trước khi đặt đơn dữ liệu tiếp, để các lỗi đang bị che được chẩn đoán.",
                        f"Close the tickets {tk} before the next data order, so the failures they hide can be diagnosed."))  # fmt: skip
    cmp_ = next((c for c in pair.get("comparisons") or [] if c.get("variant") == after and c.get("baseline") == base), None)
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
        F["near"] = say(f"Số lượt suýt đạt (lệch hơn dung sai nhưng chưa quá 7,5 cm) tăng từ {nb} lên {na} sau vòng: dữ liệu mới kéo robot về gần đích hơn nhưng chưa đủ để lọt vào dung sai.",
                        f"Near misses (outside the tolerance but within 7.5 cm) went from {nb} to {na} after the round: the new data pulled the robot closer to the target, not yet inside the tolerance.")  # fmt: skip
        if na > nb:
            opts.append(say("Nhắm đơn dữ liệu tiếp theo vào vài centimet cuối lúc đặt, nơi có các lượt suýt đạt, và báo số lượt trong 7,5 cm cạnh số lượt đạt.",
                            "Aim the next data order at the last centimetres of placing, where the near misses are, and report the 7.5 cm figure next to the pass count."))  # fmt: skip
    tilt = (rd.get("tilt_at_place") or {}).get("value") or {}
    if base in tilt and after in tilt:
        F["tilt"] = say(f"Số lượt vật bị nghiêng lúc đặt tăng từ {tilt[base]} lên {tilt[after]} sau vòng.", f"Runs where the object tilted while placing went from {tilt[base]} to {tilt[after]} after the round.")
    if ((rd.get("stop") or {}).get("value") or {}).get("stop"):
        F["decision"] = say("Theo luật đã định trước, vòng dừng ở đây và không chạy giai đoạn 2.", "By the rule fixed in advance the round stops here and stage 2 is not run.")
    cost = demo.get("round_cost") or {}
    if cost.get("total_cu") is not None:
        F["cost"] = say(f"Cả vòng tốn {cost['total_cu']} CU đo được, khoảng {cost.get('total_usd')} USD.", f"The whole round cost {cost['total_cu']} CU measured, about {cost.get('total_usd')} USD.")
        if ch.get("generated") and ch.get("selected"):
            F["eff"] = say(f"Giữ lại {ch['selected']} trên {ch['generated']} bài mẫu sinh ra ({100 * ch['selected'] / ch['generated']:.0f}%), tức {cost['total_cu'] / ch['selected']:.2f} CU cho mỗi bài được giữ, tính cả dạy lại và thi lại.",
                           f"{ch['selected']} of {ch['generated']} generated demonstrations were kept ({100 * ch['selected'] / ch['generated']:.0f}%), which is {cost['total_cu'] / ch['selected']:.2f} CU per kept demonstration, retraining and retest included.")  # fmt: skip
    if held:
        F["withheld"] = say("Kết quả thi lại của bản sau vòng không trình bày ở bản này, nên chưa thể nói vòng có làm robot tốt lên hay không.",
                            "The retest result of the model after the round is not shown in this version, so whether the round made the robot better cannot be said here.")  # fmt: skip
    F["untested"] = say("Chưa kiểm vì sao robot đặt lệch; mọi lý do nêu ra lúc này là phỏng đoán.", "Why the robot places off target has not been tested; any reason given now is a guess.")
    steps = b.get("step_pass") or {}
    if steps:
        st_txt = ", ".join(f"{_stage_word(task, k, say)} {100 * v:.0f}%" for k, v in steps.items())
        F["steps"] = say(f"Tỉ lệ lượt thi của bản gốc qua được từng bước: {st_txt}. Tỉ lệ tụt mạnh nhất ở bước đặt.",
                         f"Share of the baseline's test runs that pass each step: {st_txt}. The sharpest drop is at placing.")  # fmt: skip
    cis = [c.get("ci") or [0, 0] for c in pair.get("comparisons") or []]
    if cis and all(lo < 0 < hi for lo, hi in cis):
        F["noclear"] = say(f"Trong {len(cis)} phép so sánh đã định trước, không cặp nào khác biệt chắc chắn: mọi khoảng tin cậy đều chứa 0.",
                           f"Of the {len(cis)} comparisons fixed in advance, none shows a sure difference: every interval includes 0.")  # fmt: skip
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
    focus = focus_of(ctx.get("question"))
    # the sentence that answers the question, then the facts that support it
    PLAN = {
        "best": ("best", ["each", "strength"]),
        "fail": ("dominant", ["strength", "bigstage", "tickets", "untested"]),
        "why": ("ci", ["outcome", "near", "tilt", "tickets", "untested"]),
        "next": (None, ["outcome", "strength", "near", "ci", "tickets"]),
        "cost": ("cost", ["eff", "order", "outcome"]),
        "steps": ("steps", ["strength", "dominant", "bigstage"]),
        "compare": ("each", ["best", "noclear", "strength"]),
        "data": ("data", ["order", "qa"]),
        "qa": ("qa", ["data"]),
        "diag": ("diag", ["bigstage", "tickets", "untested"]),
        "all": ("outcome", ["strength", "dominant", "near", "ci", "tickets", "diag", "order", "decision", "cost", "untested"]),
    }  # fmt: skip
    PLAN["held"] = ("withheld", ["order", "best"])
    if held:  # no outcome to lead with: the question about the round gets the plain statement
        PLAN["why"] = ("withheld", ["strength", "dominant", "tickets", "untested"])
        PLAN["all"] = ("best", ["each", "strength", "dominant", "diag", "order", "withheld", "tickets", "cost", "untested"])
        PLAN["next"] = (None, ["strength", "dominant", "tickets", "withheld"])
    first, more = PLAN[focus]
    title = f"{say.name(task.get('name'))}, {say.name(rnd.get('title'))}"
    lines = [say(f"TASK {title}. Mọi bản model thi cùng {n} lượt; một lượt chỉ đạt khi vật nằm trong {tol} cm quanh đích.",
                 f"TASK {title}. Every model is tested on the same {n} runs; a run passes only when the object ends within {tol} cm of the target.")]  # fmt: skip
    if first and F.get(first):
        lines += [say("CÂU TRẢ LỜI THẲNG (mở đầu bằng câu này):", "DIRECT ANSWER (open with this sentence):"), "- " + F[first]]
    lines.append(say("SỐ LIỆU VÀ NHẬN XÉT LIÊN QUAN:", "RELATED NUMBERS AND READINGS:"))
    lines += ["- " + F[k] for k in more if F.get(k) and k != first]
    want_opts = focus in ("next", "why", "all", "fail")
    if opts and want_opts:
        lines.append(say("PHƯƠNG ÁN BƯỚC TIẾP (đề xuất, chưa phải quyết định):", "OPTIONS FOR NEXT STEPS (proposals, not decisions):"))
        lines += ["- " + o for o in (opts if focus in ("next", "all") else opts[:1])]
        lines.append(say("ĐÃ LÀM RỒI, đừng đề xuất lại: so sánh các bản model, chẩn đoán, đặt đơn dữ liệu, dạy lại, thi lại.",
                         "ALREADY DONE, do not propose again: comparing the models, the diagnosis, the data order, the retraining, the retest."))  # fmt: skip
    lines.append(_how(say, focus))
    if held:
        lines.append(say("QUY TẮC: không viết rằng bản sau vòng chưa thi lại hay chưa có kết quả; nếu nhắc tới thì chỉ viết kết quả thi lại không trình bày ở bản này.",
                         "RULE: never write that the model after the round was not retested or has no result; if you mention it, write only that its retest result is not shown in this version."))  # fmt: skip
    ui = table("Round · " + say.name(rnd.get("title")), cols("model", "role", "train_set", "passed", "on_table_B", "within_7.5cm"), rows, link="#/report")
    out = result(ui, "\n".join(lines))
    if focus == "held":
        # a question about a withheld result gets this sentence as it stands: no model words it
        out["answer"] = " ".join(F[k] for k in ("withheld", "order") if F.get(k))
    return out


def _how(say: Say, focus: str) -> str:
    """How to shape the answer for this kind of question, in the user's language."""
    if focus == "held":
        return say("CÁCH TRẢ LỜI: chỉ nói câu trả lời thẳng, rồi một câu về đơn dữ liệu. Không nêu con số nào cho bản sau vòng, không suy đoán kết quả của nó.",
                   "HOW TO ANSWER: give the direct answer only, then one sentence on the data order. State no figure for the model after the round and do not guess its result.")  # fmt: skip
    if focus in ("best", "cost", "steps", "compare", "data", "qa", "diag"):
        return say("CÁCH TRẢ LỜI: câu trả lời thẳng, rồi một hoặc hai câu nhận xét lấy từ các ý trên. Không chia phần, không thêm việc nên làm.",
                   "HOW TO ANSWER: the direct answer, then one or two sentences of reading taken from the lines above. No parts, no next steps.")  # fmt: skip
    if focus == "next":
        return say("CÁCH TRẢ LỜI: một câu nêu tình hình, rồi từng phương án ở trên kèm lý do của nó (lấy từ số liệu liên quan). Mở đầu phần phương án bằng 'Việc nên làm:'.",
                   "HOW TO ANSWER: one sentence on where things stand, then each option above with its reason (from the related numbers). Open the options with 'Next steps:'.")  # fmt: skip
    return say("CÁCH TRẢ LỜI: ba phần ngắn có nhãn 'Số liệu:', 'Nhận xét:', 'Việc nên làm:'. Số liệu mở đầu bằng câu trả lời thẳng. Nhận xét dùng hai hoặc ba ý liên quan nhất ở trên và nói rõ ý nào là phỏng đoán. Việc nên làm lấy từ các phương án.",
               "HOW TO ANSWER: three short parts labelled 'Numbers:', 'Reading:', 'Next steps:'. Numbers opens with the direct answer. Reading uses the two or three most relevant lines above and says which is a guess. Next steps come from the options.")  # fmt: skip


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
