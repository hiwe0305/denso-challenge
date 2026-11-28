# ruff: noqa: E501, UP031  (ported prompt, guard-regex and tool-schema strings stay on one line)
"""Tool registry of the chat: schemas, which tools a page and a question offer, and ``call``."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from .common import HOSTED, Result, catalog, fail, norm
from .resolve import resolve_dataset
from .tools_data import (
    catalog_search,
    dataset_stats,
    episode_get,
    episode_list,
    lineage,
    qa_summary,
)
from .tools_ops import KINDS, findings, job_get, job_list, open_page, propose_job
from .tools_project import failure_table, project_status, train_progress
from .tools_round import (
    RANK_RX,
    asks_held,
    asks_hidden,
    ego_summary,
    pair_comparisons,
    pair_runs_named,
    round_diagnosis,
    round_report,
    rounds_named,
    rounds_side_by_side,
    runs_named,
    strip_round_refs,
)
from .tools_runs import (
    eval_failures,
    eval_summary,
    ledger_query,
    log_tail,
    loop_proposals,
    run_compare,
    run_list,
    run_metrics,
)

ToolFn = Callable[[dict[str, Any], dict[str, Any]], Result]
MAX_OFFERED = 7  # plus open_page
ANALYSIS_TOOLS = ["round_report", "round_diagnosis", "pair_comparisons"]

# Tools a hosted model never gets: they read jobs, logs, findings and the egocentric pipeline,
# which name the team's own videos (internal data), and they have no public-only filter
# (CLAUDE.md: internal data never goes to a hosted API)
LOCAL_ONLY = frozenset({"ego_summary", "findings", "job_get", "job_list", "log_tail"})


def usable(name: str) -> bool:
    """False for a local-only tool while a hosted model answers the turn."""
    return not (HOSTED.get() and name in LOCAL_ONLY)


def P(**props: tuple[str, str]) -> dict[str, Any]:
    """JSON-schema helper: ``P(name=('string', 'desc'), ...)``; names ending in ``_REQ`` are required."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for k, (t, d) in props.items():
        if k.endswith("_REQ"):
            k = k[:-4]
            required.append(k)
        properties[k] = {"type": t, "description": d}
    return {"type": "object", "properties": properties, "required": required}


TOOLS: dict[str, tuple[ToolFn, str, str, dict[str, Any]]] = {
    "ego_summary": (ego_summary, "/ego", "The egocentric (human first-person video) pipeline in numbers: clips in, episodes exported, clips rejected by QA or left out, the QA reasons. Call this for any question about egocentric or human video clips as a whole (video người, clip egocentric, đã xuất, bị loại).", P()),
    "round_report": (round_report, "/round", "ALL facts of the selected task and ONE Failure -> Data round in one call, as labelled data rows in the user's language, tagged with the round they belong to: each model's test result with its confidence interval and the reading rules (marks met or not), the model with the most successes and whether the intervals tell the models apart, where the robot fails, the side-by-side table against earlier runs, the diagnosis summary, the data order, the cost of the round, the limits, the points worth raising and options for next steps. Also the status of a task that has no round yet. Call this FIRST for results, status, 'which model has the most successes', 'does it meet the mark', 'where does it fail', 'cost of the round', 'analyse', 'comment', 'assess', 'why', 'what next', 'summarise' (kết quả, đạt mốc, hỏng ở đâu, chi phí vòng, nhận xét, phân tích, đánh giá, vì sao, nên làm gì, tóm tắt).",
                     P()),
    "round_diagnosis": (round_diagnosis, "/diagnosis", "Diagnosis of the selected round: each failure group (c1-c8) with its diagnosis and whether it got data, the step-4 system checks (H1-H3) with their verdict and ticket, and the cost of generating and checking the data. Call this for 'why were these groups chosen', 'which system issues were ruled out', 'what did step 4 find', tickets (vì sao chọn cụm, lỗi hệ thống nào đã loại trừ, bước 4, phiếu).",
                        P()),
    "rounds_side_by_side": (rounds_side_by_side, "/round", "Two or more rounds the question names, each with its own facts under its own title, placed side by side (different scene, eval set and scorer: never compared as a result). Call this when the question names two rounds (vòng 1 và vòng đồ gá, both rounds).",
                            P(rounds=("array", "round ids, e.g. tray-r1, tray-jig-r1"))),
    "pair_comparisons": (pair_comparisons, "/comparisons", "The paired comparisons fixed in advance between the models of the DA-34 round, each with its difference, confidence interval and McNemar p, read descriptively. Call this for confidence intervals, significance, 'is the difference real' (khoảng tin cậy, phép so sánh, có khác biệt thật không).",
                         P()),
    "failure_table": (failure_table, "/failures", "Failure labels by run for every round of the task (or the round the question names): one row per failure label with the count of each run, then failed and n per run, the scorer version of each round and whether two rounds can be compared. Never a run whose result is not presented. Call this for every failure type, failure statistics, a table of failures (thống kê lỗi, toàn bộ loại lỗi, bảng lỗi, nhãn lỗi, lỗi theo run).",
                      P(round=("string", "round id, e.g. tray-r1 or tray-jig-r1; omit for every round"))),
    "train_progress": (train_progress, "/train", "Training progress of each run of the round(s): steps done of max, state, steps per second, VM hours by phase (setup, train, persist) and whether they cover the whole run, measured training CU, and the loss as a trend only (first value, end mean, late trend) with the note that training loss is not a measure of the result. Call this for training progress, phases, training logs, loss of a run (tiến độ train, các phase, log training, loss, train mất bao lâu).",
                       P(round=("string", "round id; omit for every round"))),
    "project_status": (project_status, "/status", "Where the project stands: the latest presented result with its numbers, the dated timeline of work since 18/11 with results, the next steps written in the docs, and how the rounds of the task link (default round, previous and next round). Says which parts the index does not have yet. Call this for project status, progress so far, what has been done, what is the latest result, what comes next (tình hình dự án, diễn tiến, đã làm gì, kết quả mới nhất, bước tiếp theo).",
                       P()),
    "catalog_search": (catalog_search, "/catalog", "List datasets in the catalog. Use for 'what datasets', 'which sets are teleop/egocentric/synthetic', find a dataset by text.",
                       P(q=("string", "free text"), data_type=("string", "egocentric | teleop | synthetic"), task=("string", "tray | two_table"), status=("string", "current | upstream"), limit=("integer", "max rows"))),
    "dataset_stats": (dataset_stats, "/stats", "Statistics of ONE dataset: episodes, hours, frames, fps, size, length histogram.",
                      P(dataset_id_REQ=("string", "dataset id or alias such as S70, S1, ALL, psi-two-table"))),
    "episode_list": (episode_list, "/eps", "List episodes of a dataset, filterable by QA status (pass|flag|reject) or reason, sortable (-s = longest first).",
                     P(dataset_id_REQ=("string", "dataset id"), qa=("string", "pass | flag | reject"), reason=("string", "QA reason text"), sort=("string", "field name, prefix - for descending"), limit=("integer", "max rows"))),
    "episode_get": (episode_get, "/ep", "Details of ONE episode: QA checks with value vs threshold, length, level, outcome.",
                    P(dataset_id_REQ=("string", "dataset id"), episode_id_REQ=("string", "episode index like 278 or id ep_..."))),
    "qa_summary": (qa_summary, "/qa", "QA result of a dataset: pass/flag/reject counts and the reasons (or failure reasons for simulator data).",
                   P(dataset_id_REQ=("string", "dataset id or work id"))),
    "run_list": (run_list, "/runs", "List training runs with step, loss and state.", P(state=("string", "running | stopped"))),
    "run_metrics": (run_metrics, "/metrics", "Training curve of ONE run (loss by default): first, last, min.",
                    P(run_id_REQ=("string", "run id or branch like B_70, C_70, C_ALL"), keys=("string", "metric names, comma separated"), from_step=("integer", "start step"), points=("integer", "points to plot"))),
    "run_compare": (run_compare, "/compare", "Overlay the curves of 2 to 4 runs and diff their config.",
                    P(run_ids_REQ=("array", "2 to 4 run ids or branches"), metric=("string", "default loss"))),
    "log_tail": (log_tail, "/log", "Last lines of a job log or a training run log, optional grep.",
                 P(job_id_REQ=("string", "job id j-... or run id"), n=("integer", "lines"), grep=("string", "filter text"))),
    "eval_summary": (eval_summary, "/eval", "The EARLIER evaluation of policy C (before the round, per level): success per level, pass rate per stage, failure labels. Use only when the user names policy C or a level.",
                     P(eval_id=("string", "C"))),
    "eval_failures": (eval_failures, "/fails", "Failures of the evaluation by label (L-PLACE-POSE ...), placement error in cm.",
                      P(eval_id=("string", "C"), label=("string", "failure label"), limit=("integer", "max rows"))),
    "loop_proposals": (loop_proposals, "/loop", "Failure clusters, diagnosis and data budget of the flywheel loop.", P(eval_id=("string", "C"))),
    "ledger_query": (ledger_query, "/ledger", "Cost ledger: estimated and measured kept as separate rows.",
                     P(group_by=("string", "story | host | kind"), measure_kind=("string", "estimated | measured"), since=("string", "ISO date or run prefix"))),
    "job_list": (job_list, "/jobs", "List console jobs (ingest, deid, qa, agentqa ...) with state and duration.", P(state=("string", "ok | failed | running | queued | cancelled"), kind=("string", "kind text"), limit=("integer", "max rows"))),
    "job_get": (job_get, "/job", "Details of ONE job: state, argv, duration, last log lines.", P(job_id_REQ=("string", "job id j-..."))),
    "findings": (findings, "/findings", "Agent QA and rule-layer findings with status. source rule|llm.",
                 P(input=("string", "filter text"), source=("string", "rule | llm"), status=("string", "open | accepted | rejected | flag"))),
    "lineage": (lineage, "/lineage", "Where a dataset comes from and what is built from it.",
                P(dataset_id_REQ=("string", "dataset id"), direction=("string", "up | down | both"))),
    "open_page": (open_page, "/open", "Navigate the console to a page: home, data, data/<id>, jobs, runs, eval, loop, qa.",
                  P(route_REQ=("string", "e.g. data/S70, runs, eval, #/jobs"))),
    "propose_job": (propose_job, "/run", "Propose a job (ingest, deid, pose, annotate, qa, report, pipeline, human1m, export.zip, agentqa.run). Starts nothing, shows a confirm card. Never training.",
                    P(kind_REQ=("string", "one of: " + ", ".join(KINDS)), params=("object", "e.g. {\"work\": \"src_158ec3c8\"} or {\"input\": \"fwdata/...\"}"))),
}  # fmt: skip

PAGE_TOOLS: dict[str, list[str]] = {
    "data": [
        "catalog_search",
        "dataset_stats",
        "episode_list",
        "episode_get",
        "qa_summary",
        "lineage",
    ],
    "runs": ["run_list", "run_metrics", "run_compare", "log_tail", "ledger_query"],
    "eval": ["eval_summary", "eval_failures", "loop_proposals", "run_list"],
    "loop": ["eval_summary", "eval_failures", "loop_proposals", "run_list"],
    "jobs": ["job_list", "job_get", "log_tail", "propose_job", "qa_summary"],
    "qa": ["findings", "job_get", "log_tail", "propose_job"],
    "home": ["catalog_search", "run_list", "eval_summary", "job_list", "findings", "ledger_query"],
}


ROUND_PAGES = {"home", "tasks", "report", "follow", "base", "design", "loop", "diagnose", "eval", "cost"}


def page_of(route: Any) -> str:
    r = str(route or "").lstrip("#").lstrip("/")
    return r.split("?", 1)[0].split("/", 1)[0] or "home"


def tool_names_for(route: Any) -> list[str]:
    return list(PAGE_TOOLS.get(page_of(route), PAGE_TOOLS["home"])) + ["open_page"]


def describe(route: Any = None) -> list[dict[str, Any]]:
    names = tool_names_for(route) if route is not None else list(TOOLS)
    return [
        {"name": n, "description": TOOLS[n][2], "parameters": TOOLS[n][3], "slash": TOOLS[n][1]}
        for n in names
    ]


def schemas(route: Any, names: list[str] | None = None) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {"name": n, "description": TOOLS[n][2], "parameters": TOOLS[n][3]},
        }
        for n in (names or tool_names_for(route))
    ]


_RUN_RX = re.compile(
    r"\b(B_70|C_70|C_ALL)\b|\b(loss|run|runs|train|training|checkpoint|step|steps)\b|huấn luyện",
    re.I,
)
_EVAL_RX = re.compile(
    r"\b(eval|evaluation|success|failure|failures|policy)\b|thành công|hỏng|bước nào|đánh giá|lỗi eval",
    re.I,
)
_JOB_RX = re.compile(r"\b(job|jobs|log|logs|pipeline|duration)\b|chạy mất|việc", re.I)
_COST_RX = re.compile(r"\b(cost|ledger|CU|budget)\b|chi phí|ngân sách", re.I)
_LOOP_RX = re.compile(r"\b(loop|cluster)\b|sinh thêm|cụm|vòng lặp", re.I)
_ANALYSE_RX = re.compile(
    r"\b(analy[sz]e|analysis|comment|assess|review|why|summar\w+|conclusion|what next|next step|improve|insight|recommend\w*)\b|"
    r"nhận xét|phân tích|đánh giá|vì sao|tại sao|nên làm|làm gì tiếp|tóm tắt|kết luận|cải thiện|bài học|có tốt|ổn không|"
    r"\bround\b|vòng 1|vòng này|của vòng|kết quả|tốt nhất|\bbest\b|hỏng ở|hỏng nhiều|fails? (at|where|most)|where does .* fail|điểm mạnh|điểm yếu|task này|this task|"
    r"đang ở đâu|còn thiếu|thiếu gì|tình hình|tiến độ|where does it stand|\bstatus\b|what is missing|\btốn\b|bao nhiêu tiền|"
    r"so sánh|khác nhau|bước nào|từng bước|bài mẫu|dữ liệu|kiểm định|lỗi cấy|chẩn đoán|nhóm lỗi|cụm lỗi|"
    r"\bcompare|which step|each step|demonstration|planted|diagnos|failure group",
    re.I,
)
_EGO_RX = re.compile(r"egocentric|\bego\b|video người|human video|first-person|góc nhìn người", re.I)
_QA_RX = re.compile(r"\bQA\b|flag|reject|\bfindings?\b|phát hiện", re.I)

# Which page group a question topic belongs to (the page whose tool set it pulls in).
TOPIC_PAGE = {
    "data": "data",
    "qa": "qa",
    "runs": "runs",
    "eval": "eval",
    "loop": "loop",
    "jobs": "jobs",
    "cost": "runs",
}


def _dataset_in(q: str) -> list[str]:
    """Dataset ids or aliases written in the question: an id-looking token, or a short src hash."""
    ids: dict[str, str] = {}
    for r in catalog().get("rows", []):
        ids[norm(r["id"])] = r["id"]
        for a in r.get("aliases") or []:
            ids[norm(a)] = r["id"]
    hit: list[str] = []
    for tok in re.findall(r"[A-Za-z0-9_+\-]+", q):
        looks = bool(re.search(r"[0-9_\-]", tok)) or (tok.isupper() and len(tok) >= 3)
        if looks and norm(tok) in ids:
            hit.append(ids[norm(tok)])
        elif re.fullmatch(r"[0-9a-f]{8}", tok.lower()) and resolve_dataset(tok)[0] == "ok":
            hit.append(tok)
    return hit


def topics_of(question: Any) -> dict[str, list[str]]:
    """Topics a question's words point at, in detection order, each with its tools in priority."""
    q = str(question or "")
    out: dict[str, list[str]] = {}
    if _dataset_in(q):
        out["data"] = ["dataset_stats", "qa_summary", "episode_list"]
    elif _QA_RX.search(q):
        out["qa"] = ["qa_summary", "findings"]
    if _RUN_RX.search(q):
        out["runs"] = ["run_list", "run_compare", "run_metrics"]
    if _EVAL_RX.search(q):
        out["eval"] = ["eval_summary", "eval_failures"]
    if _LOOP_RX.search(q):
        out["loop"] = ["loop_proposals"]
    if _JOB_RX.search(q):
        out["jobs"] = ["job_list", "log_tail", "job_get"]
    if _COST_RX.search(q):
        out["cost"] = ["ledger_query"]
    return out


def intent_tools(question: Any) -> list[str]:
    """Deterministic prefilter: tools a question's words point at. Two topics are interleaved."""
    per = list(topics_of(question).values())
    names: list[str] = []
    for i in range(max((len(p) for p in per), default=0)):
        names += [p[i] for p in per if i < len(p)]
    return list(dict.fromkeys(names))


_SPECIFIC_RX = re.compile(
    r"\b(src_|ep_|egx_|j-)\w+|\b[A-Z][A-Za-z]*_?\d\w*\b|\b(B_70|C_70|C_ALL|B_ALL)\b|policy C|eval C|\bQA\b|\bloss\b|"
    r"\bjobs?\b|\bruns?\b|dataset|\btập\b|liệt kê|\blist\b|story|ledger|sổ",
    re.I,
)
_COUNT_RX = re.compile(r"bao nhiêu|how many|đã xuất|export|bị loại|reject|tổng|total|tóm tắt|summar", re.I)


def _specific(q: str) -> bool:
    """The question names one dataset, run, job or policy, or asks for a list: a lookup, not a reading."""
    return bool(_dataset_in(q)) or bool(_SPECIFIC_RX.search(q))


_LOOKUP_RX = re.compile(r"\bloss\b|\blogs?\b|\bstep\b|checkpoint|curve|đường cong|throughput|vram", re.I)
_DIAG_RX = re.compile(r"\bc[1-8]\b|\bH[1-3]\b|bước 4|step 4|loại trừ|ruled? out|lỗi hệ thống|system (issue|check|fault|problem)s?|kiểm hệ thống", re.I)
_PAIR_RX = re.compile(r"phép so sánh|\bcomparisons?\b|mcnemar|khoảng tin cậy|\bCI\b|confidence interval|ý nghĩa thống kê|significan", re.I)


# a cost question about the whole project, not one round: the ledger of every story
_PROJECT_RX = re.compile(r"cả dự án|toàn (bộ )?dự án|toàn bộ|mọi story|các story|tất cả|whole project|entire project|all stories|"
                         r"project[- ]wide|\bproject\b|\boverall\b|\bin total\b", re.I)  # fmt: skip
# a run named with a question about its test result or why it fails, not its training
_RESULT_RX = re.compile(r"vì sao|tại sao|\bwhy\b|hỏng|thất bại|\bfail|thành công|\bsuccess|đạt|kết quả|\bresult|"
                        r"bước đặt|\bplac(e|ing)\b|chỗ nào|ở đâu|\bwhere\b|điểm yếu|phân tích|nhận xét|\banaly", re.I)  # fmt: skip
_TRAINING_RX = re.compile(r"\b(train|training|trained|checkpoint|lr|batch)\b|huấn luyện|dạy|bao lâu|mất bao", re.I)
# the earlier eval of policy C is asked for by name: its own lookup (eval_summary)
_EARLIER_RX = re.compile(r"\bpolicy C\b|\beval C\b|40k|lần thi trước", re.I)
_WHY_RX = re.compile(r"vì sao|tại sao|\bwhy\b|hỏng|thất bại|\bfail|lỗi|điểm yếu|\bweak", re.I)


# the questions the audit of 28/11/2026 found with no lookup of their own (05-danh-gia-chat-2811.md)
FAILURE_TABLE_RX = re.compile(r"thống kê.{0,40}lỗi|loại lỗi|nhãn lỗi|bảng lỗi|(các|mọi|toàn bộ|tất cả)( các)? (loại )?lỗi|lỗi (của )?(các|mọi|từng) run|"
                              r"failure (table|labels?|types?|breakdown|counts?|statistics)|(types?|kinds?) of failures?|all (the )?failures|failures? (by|per) run|error types", re.I)  # fmt: skip
TRAIN_PROGRESS_RX = re.compile(r"tiến độ.{0,30}(train|huấn luyện)|(train|training|huấn luyện).{0,40}(tiến độ|phase|log)|\bphases?\b|\blogs? (train|training)|"
                               r"training (log|progress|phases?)|đánh giá.{0,30}\blogs?\b|train (đến đâu|tới đâu|bao nhiêu bước)", re.I)  # fmt: skip
PROJECT_STATUS_RX = re.compile(r"tiến độ (của )?dự án|dự án.{0,30}(đến đâu|tới đâu|thế nào|ra sao|tiến độ|diễn tiến)|diễn tiến|timeline|dòng thời gian|"
                               r"(đã|vừa) làm (được )?(những )?gì|gần đây (đã|có) gì|project (status|progress|timeline)|where (is the project|are we)|what has been done|what('s| is) new", re.I)  # fmt: skip
# "what should we do / how to improve": the weak points of the latest presented result and the
# next steps the documents give (sample C)
NEXT_RX = re.compile(r"nên làm gì|cần làm gì|làm gì (tiếp|để|bây giờ|nữa)|cải thiện|bước tiếp|việc tiếp|hướng tiếp|"
                     r"what (should|do) (we|i) do|next steps?|\bimprove", re.I)  # fmt: skip
# words that mean the newest result, not the round in the top bar ("mới nhất", "hiện tại")
_LATEST_RX = re.compile(r"tốt nhất|cao nhất|mới nhất|gần nhất|hiện tại|hiện giờ|bây giờ|\bbest\b|highest|latest|newest|most recent|\bcurrent\b|\bnow\b", re.I)
# ... unless the question points at the selected round itself
_THIS_ROUND_RX = re.compile(r"vòng này|round này|this round|the selected round", re.I)


def asks_latest(question: Any) -> bool:
    """True for a best / latest / what-next question that names no round and no run: it is about
    the latest presented result (run M), whatever round the top bar shows (Hiếu, 28/11/2026)."""
    q = str(question or "")
    if _THIS_ROUND_RX.search(q) or rounds_named(q) or runs_named(q):
        return False
    return bool(_LATEST_RX.search(q) or RANK_RX.search(q) or NEXT_RX.search(q))


def latest_round(task: Any = None) -> str:
    """The round of the latest presented result: ``story.latest.round``, else the task's
    ``default_round``, else the task's round with the highest number. Empty when none is known."""
    from .common import story
    from .tools_round import manifest

    m = manifest()
    rounds = [r for r in m.get("rounds") or [] if isinstance(r, dict) and r.get("id")]
    ids = {str(r["id"]) for r in rounds}
    try:
        latest = (story().get("latest") or {}).get("round")
    except Exception:
        latest = None
    if latest and str(latest) in ids:
        return str(latest)
    tasks = [t for t in m.get("tasks") or [] if isinstance(t, dict)]
    t = next((x for x in tasks if x.get("id") == task), tasks[0] if tasks else None)
    if t and str(t.get("default_round") or "") in ids:
        return str(t["default_round"])
    mine = [r for r in rounds if not t or r.get("task") == t.get("id")]
    best = max(mine, key=lambda r: int(r.get("number") or 0), default=None)
    return str(best["id"]) if best else ""


def forced_tools(question: Any) -> list[str]:
    """Every tool the code runs itself, in order, before the model writes anything (see
    ``forced_tool``). Three questions need more than one lookup or a lookup ``forced_tool`` does
    not give:

    - a run of a round named with a question about its result or why it fails ("Vì sao C_70 hỏng
      nhiều ở bước đặt?"): the round's report for that run and the round's diagnosis, never the
      earlier eval of policy C, whose numbers are not the run's own;
    - two rounds named ("vòng 1 so với vòng đồ gá"): both side by side;
    - the cost of the whole project: the ledger of every story.
    """
    q = str(question or "")
    if asks_held(q) and not _LOOKUP_RX.search(q):
        return ["round_report"]
    if RANK_RX.search(q) and not _dataset_in(strip_round_refs(q)):
        # "which run is best / better", a ranking: the test results of the round, never the loss
        return ["round_report"]
    if FAILURE_TABLE_RX.search(q) and not _dataset_in(strip_round_refs(q)):
        return ["failure_table"]  # every run's failure labels, every round (sample A)
    if TRAIN_PROGRESS_RX.search(q) and not _dataset_in(strip_round_refs(q)) and not asks_hidden(q):
        # the loss of one run ("Loss của C_70 thế nào?") stays the model's curve lookup (run_metrics)
        return ["train_progress"]  # phases, steps, hours, CU; loss as a trend only
    if PROJECT_STATUS_RX.search(q) and not rounds_named(q) and not runs_named(q):
        return ["project_status"]
    if NEXT_RX.search(q) and not _dataset_in(strip_round_refs(q)) and not _COST_RX.search(q):
        return ["round_report"]  # weak points of the latest result and the documented next steps (sample C)
    if _COST_RX.search(q) and _PROJECT_RX.search(q) and not rounds_named(q) and not runs_named(q):
        return ["ledger_query"]
    if len(rounds_named(q)) >= 2 and not runs_named(q) and not _LOOKUP_RX.search(q):
        # rounds as wholes; a run named ("run M ... so với vòng 1") is read by its round's report
        return ["rounds_side_by_side"]
    if (pair_runs_named(q) and _RESULT_RX.search(q) and not _LOOKUP_RX.search(q) and not _TRAINING_RX.search(q)
            and not _EARLIER_RX.search(q) and not _dataset_in(strip_round_refs(q))):  # fmt: skip
        return ["round_report", "round_diagnosis"] if _WHY_RX.search(q) else ["round_report"]
    one = forced_tool(q)
    return [one] if one else []


def forced_tool(question: Any) -> str | None:
    """The tool the code runs itself, before the model writes anything.

    For a question about the round, the task or the egocentric clips as a whole there is one
    right lookup and it takes no argument. A small model asked to make that call sometimes writes
    it as text instead (seen 16/11/2026), so the code makes it and the model only answers. A
    round named in the question (``tray-r1``, "vòng 1", "run M") selects that round; it is not a
    dataset or run lookup.
    """
    q = str(question or "")
    if asks_held(q) and not _LOOKUP_RX.search(q):
        return "round_report"  # its test result is not presented: one fixed answer, no other lookup
    if _DIAG_RX.search(q) and not _LOOKUP_RX.search(q):
        return "round_diagnosis"  # failure groups and step-4 checks: one lookup, no argument
    bare = strip_round_refs(q)
    if bare != q and not _LOOKUP_RX.search(q) and not _dataset_in(bare):
        return "round_report"  # the question names a round or a run only that round has
    if _specific(bare):
        return None  # a named dataset, run, job, policy or a list request: the model picks the lookup
    if _EGO_RX.search(q):
        return "ego_summary" if _COUNT_RX.search(q) and usable("ego_summary") else None
    return "round_report" if _ANALYSE_RX.search(q) else None


def analysis_question(question: Any) -> bool:
    """A question about the round as a whole (no single dataset, run or job named)."""
    q = str(question or "")
    return any(t in ANALYSIS_TOOLS or t == "rounds_side_by_side" for t in forced_tools(q)) or bool(_PAIR_RX.search(q))


def offered_names(route: Any, question: Any) -> list[str]:
    """Question-driven tools first, then the page tools, at most 7 plus ``open_page``.

    A question that names two page topics (loss of a run and QA of a dataset) gets the tool sets
    of both pages, the current page first, so the model can answer from either.
    """
    names = intent_tools(question)
    here = page_of(route)
    # an analysis question, or a page about the task as a whole, gets the round's facts first
    q = str(question or "")
    has_id = _specific(strip_round_refs(q))
    if _EGO_RX.search(q) and _COUNT_RX.search(q) and not has_id:
        names = ["ego_summary"] + names
    elif analysis_question(q) or (_ANALYSE_RX.search(q) and not has_id):
        # the round's tools only, no page to open: a model otherwise spends rounds on lookups or pages
        return [n for n in ANALYSIS_TOOLS if usable(n)]
    elif here in ROUND_PAGES and not names:
        names = ["round_report"] + names
    pages = list(dict.fromkeys(TOPIC_PAGE[t] for t in topics_of(question)))
    if len(pages) >= 2:
        pages = ([here] if here in pages else []) + [p for p in pages if p != here]
        pages = pages[:2]
    else:
        pages = [here]
    for pg in pages:
        for n in PAGE_TOOLS.get(pg, PAGE_TOOLS["home"]):
            if n not in names:
                names.append(n)
    return [n for n in names if n != "open_page" and usable(n)][:MAX_OFFERED] + ["open_page"]


def context_defaults(context: Any) -> dict[str, Any]:
    """Page context {route, selection?, filters?} -> default ids a pronoun can mean."""
    context = context or {}
    route = str(context.get("route") or "")
    d: dict[str, Any] = {}
    for k in ("task", "round", "lang", "question"):  # the (task, round) chosen in the top bar; the question's language
        if isinstance(context.get(k), str) and context[k]:
            d[k] = context[k]
    if context.get("deep") is True:
        d["deep"] = True  # a deep analysis: round_report reads the whole round
    m = re.search(r"data/([^/?#]+)(?:/ep/([^/?#]+))?", route)
    if m:
        d["dataset_id"] = m.group(1)
        if m.group(2):
            d["episode_id"] = m.group(2)
    q = dict(re.findall(r"[?&]([a-z]+)=([^&]+)", route))
    if q.get("sel"):
        d["run_ids"] = q["sel"].split(",")
    if q.get("cmp"):
        d["eval_id"] = q["cmp"].split(",")[0]
    if q.get("job"):
        d["job_id"] = q["job"]
    sel = context.get("selection")
    if isinstance(sel, dict):
        pairs = (("dataset", "dataset_id"), ("dataset_id", "dataset_id"), ("episode", "episode_id"),
                 ("episode_id", "episode_id"), ("job", "job_id"), ("job_id", "job_id"))  # fmt: skip
        for k_in, k_out in pairs:
            if sel.get(k_in) not in (None, ""):
                d[k_out] = str(sel[k_in])
        for k_in in ("run", "run_id"):
            if sel.get(k_in):
                d["run_ids"] = [str(sel[k_in])]
        if sel.get("runs"):
            d["run_ids"] = [str(x) for x in sel["runs"]]
    elif isinstance(sel, str) and sel:
        m2 = re.search(r"ep(?:isode)?\s*[#_]?\s*(\d+|ep_\w+)", sel, re.I)
        if m2:
            d["episode_id"] = m2.group(1)
    return d


def call(name: str, args: Any, context: Any = None) -> Result:
    """Run a tool. Never raises: errors come back as ``ok=False`` results."""
    if name not in TOOLS:
        return fail(f"Unknown tool '{name}'.")
    if not usable(name):
        return fail(f"{name} is not available while a hosted model answers: it reads data that stays on this machine.")
    if not isinstance(args, dict):
        args = {}
    try:
        return TOOLS[name][0](args, context_defaults(context))
    except Exception as e:
        return fail(f"{name} failed: {e}")
