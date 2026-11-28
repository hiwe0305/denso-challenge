"""``GET /api/kinds``: every job kind the console can start, described well enough that the
front end builds its "Chạy thử" panels from this list alone, plus the parts of the process
that cannot run on this laptop and how they are followed instead.

Read-only: it looks at files under ``fw_root`` and the job registry, and starts nothing.
Sample inputs are only offered when they exist on this machine; a sample that cannot run
says why (``available: false`` and ``reason``)."""

from __future__ import annotations

import statistics
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from flywheel.console.index import cards
from flywheel.console.server import runner

STAGES = ("data", "qa", "train", "eval", "diagnose", "loop", "ops")
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()
CACHE_S = 30.0


def _t(vi: str, en: str) -> dict[str, str]:
    return {"vi": vi, "en": en}


def _p(text: str) -> dict[str, str]:
    """A text that reads the same in both languages (a path, a command)."""
    return _t(text, text)


def _arg(
    name: str, typ: str, required: bool, vi: str, en: str, *, choices: list[str] | None = None,
    default: Any = None, source: dict[str, str] | None = None, root: str | None = None,
) -> dict[str, Any]:  # fmt: skip
    """One argument: ``type`` is string, enum, bool, int, path or list[path]; ``source`` names
    the kind and output field a value comes from (e.g. the work dir of a data.ingest job);
    ``root`` says where a path must lie."""
    a: dict[str, Any] = {"name": name, "type": typ, "required": required, "help": _t(vi, en)}
    if choices is not None:
        a["choices"] = choices
    if default is not None:
        a["default"] = default
    if source is not None:
        a["source"] = source
    if root is not None:
        a["root"] = root
    return a


WORK_EGO = {"kind": "ego.ingest", "output": "work"}
WORK_DATA = {"kind": "data.ingest", "output": "work"}
A_WORK_EGO = _arg("work", "path", True, "Work dir egocentric (fwdata/pipeline/src_…)",
                  "Egocentric work dir (fwdata/pipeline/src_…)", source=WORK_EGO,
                  root="fwdata/pipeline")  # fmt: skip
A_WORK_DATA = _arg("work", "path", True, "Work dir mà data.ingest của console viết",
                   "Work dir written by a console data.ingest", source=WORK_DATA,
                   root="fwdata/console/store/work")  # fmt: skip
A_DATASET = [
    _arg("dataset", "path", True, "Dataset LeRobot v2.1 dưới fwdata (được chép vào store của "
         "console, tối đa 2 GB)", "LeRobot v2.1 dataset under fwdata (copied into the console "
         "store, at most 2 GB)", root="fwdata"),
    _arg("source_detail", "enum", True, "Loại nguồn", "Source kind",
         choices=list(runner.SOURCE_DETAILS)),
    _arg("license", "string", False, "Giấy phép; 'unknown' khi chưa rõ",
         "Licence; 'unknown' when not known", default="unknown"),
    _arg("data_class", "enum", False, "Lớp dữ liệu; mặc định theo thẻ dataset, không có thẻ "
         "thì restricted", "Data class; defaults to the dataset card, restricted without one",
         choices=list(runner.DATA_CLASSES), default="restricted"),
    _arg("split", "enum", False, "Tách", "Split", choices=["train", "dev"], default="train"),
]  # fmt: skip
ROBOT_OUT = _t(
    "Mọi file (dataset đã chép, work dir, release, dòng sổ chi phí) nằm trong "
    "fwdata/console/store/, không thêm vào release hay sổ chi phí của dự án.",
    "Every file (staged dataset, work dir, release, ledger rows) stays in "
    "fwdata/console/store/; nothing is added to the project's releases or ledger.",
)

SPEC: dict[str, dict[str, Any]] = {
    "ego.ingest": {
        "title": _t("Nạp video egocentric", "Ingest egocentric video"),
        "command": "fw egocentric ingest {video|egodex}",
        "args": [
            _arg("source", "enum", True, "Nguồn", "Source", choices=["video", "egodex"]),
            _arg(
                "root",
                "path",
                False,
                "Thư mục video (khi source = video)",
                "Video folder (when source = video)",
                root="~ or fwdata/console/uploads",
            ),
            _arg(
                "split", "enum", False, "Tách", "Split", choices=["train", "dev"], default="train"
            ),
        ],
        "outputs": _t(
            "Work dir mới ở fwdata/pipeline/src_…", "A new work dir in fwdata/pipeline/src_…"
        ),
    },
    "ego.deid": {
        "title": _t("Che danh tính", "De-identify"),
        "command": "fw egocentric deid <work>",
        "args": [A_WORK_EGO],
        "outputs": _t("Bản .deid.mp4 trong work dir", ".deid.mp4 copies in the work dir"),
    },
    "ego.ea": {
        "title": _t("E-A: bàn tay + camera", "E-A: hands + camera"),
        "command": "fw egocentric pose <work> --job … ; estimate_job.py ; "
        "fw egocentric pose --estimates …",
        "args": [A_WORK_EGO],
        "outputs": _p("fwdata/console/estimates/<work>/out"),
    },
    "ego.pose": {
        "title": _p("Pose"),
        "command": "fw egocentric pose <work>",
        "args": [A_WORK_EGO],
        "outputs": _t("pose.npz từng tập", "pose.npz per episode"),
    },
    "ego.annotate": {
        "title": _t("Gắn nhãn bước", "Label sub-steps"),
        "command": "fw egocentric annotate <work> --endpoint <tunnel>",
        "args": [A_WORK_EGO],
        "needs": ["rtx3060_tunnel"],
        "outputs": _t("labels.json từng tập", "labels.json per episode"),
    },
    "ego.qa": {
        "title": _t("QA egocentric", "Egocentric QA"),
        "command": "fw egocentric qa <work>",
        "args": [A_WORK_EGO],
        "outputs": _p("qa/egocentric.jsonl"),
    },
    "ego.report": {
        "title": _t("Báo cáo egocentric", "Egocentric report"),
        "command": "fw egocentric report <work>",
        "args": [A_WORK_EGO],
        "outputs": _p("report/egocentric.json"),
    },
    "ego.pipeline": {
        "title": _t("Cả pipeline egocentric", "Whole egocentric pipeline"),
        "command": "ego.ingest → ego.deid → ego.ea → ego.pose → (ego.annotate) → ego.qa → "
        "ego.report",
        "chain": list(runner.CHAIN_STEPS),
        "args": [
            _arg(
                "work",
                "path",
                False,
                "Work dir có sẵn (bỏ bước ingest)",
                "Existing work dir (skips ingest)",
                source=WORK_EGO,
                root="fwdata/pipeline",
            ),
            _arg(
                "source",
                "enum",
                False,
                "Nguồn khi ingest",
                "Source when ingesting",
                choices=["video", "egodex"],
                default="video",
            ),
            _arg(
                "root",
                "path",
                False,
                "Thư mục video",
                "Video folder",
                root="~ or fwdata/console/uploads",
            ),
            _arg(
                "split", "enum", False, "Tách", "Split", choices=["train", "dev"], default="train"
            ),
            _arg(
                "annotate",
                "bool",
                False,
                "Gắn nhãn (cần tunnel rtx3060)",
                "Label sub-steps (needs the rtx3060 tunnel)",
                default=False,
            ),
        ],
        "outputs": _t("Như từng bước", "As each step"),
    },
    "ego.human1m": {
        "title": _t("Xuất Human-1M", "Export Human-1M"),
        "command": "fw egocentric human1m fwdata/human1m/<name> --work …",
        "args": [
            _arg("name", "string", True, "Tên bản xuất", "Export name"),
            _arg(
                "works",
                "list[path]",
                True,
                "1–20 work dir",
                "1–20 work dirs",
                source=WORK_EGO,
                root="fwdata/pipeline",
            ),
            _arg(
                "sample", "int", False, "Số tập mẫu (0–200)", "Sample episodes (0–200)", default=0
            ),
        ],
        "outputs": _p("fwdata/human1m/<name>"),
    },
    "export.zip": {
        "title": _p("Zip metadata"),
        "command": "(console) zip json/yaml/csv/md",
        "args": [
            _arg("path", "path", True, "Thư mục dưới fwdata", "Folder under fwdata", root="fwdata")
        ],
        "outputs": _p("fwdata/console/exports/*.zip"),
    },
    "agentqa.run": {
        "title": _p("Agent QA/QC"),
        "command": "fw agentqa run --input <artifact> --out fwdata/console/agentqa/<job>",
        "args": [
            _arg("input", "path", True, "Artifact cần đọc", "Artifact to read", root="fwdata")
        ],
        "needs": ["rtx3060_tunnel"],
        "outputs": _p("fwdata/console/agentqa/<job>/reports.jsonl"),
    },
    "agentqa.review": {
        "title": _t("Duyệt phát hiện của agent", "Review agent findings"),
        "command": "fw agentqa review --reports … --decide <id>=agree|override:<lý do>",
        "interactive": True,
        "args": [
            _arg(
                "reports",
                "path",
                True,
                "reports.jsonl của một lần agentqa.run",
                "reports.jsonl of an agentqa.run",
                source={"kind": "agentqa.run", "output": "out"},
                root="fwdata",
            ),
            _arg("report_id", "string", True, "Id báo cáo", "Report id"),
            _arg(
                "decisions",
                "list[object]",
                True,
                "{finding_id, decide: agree|override, reason}",
                "{finding_id, decide: agree|override, reason}",
            ),
        ],
        "outputs": _p("fwdata/console/agentqa/reviews"),
    },
    "data.ingest": {
        "title": _t("Nạp dữ liệu robot (tầng 1)", "Ingest robot data (tier 1)"),
        "command": "fw data ingest <dataset> --source-detail … --license … --data-class … "
        "--work fwdata/console/store/work/<job>",
        "args": A_DATASET,
        "outputs": ROBOT_OUT,
    },
    "data.qa": {
        "title": _t("QA dữ liệu robot (tầng 4)", "Robot data QA (tier 4)"),
        "command": "fw data qa <work>",
        "args": [A_WORK_DATA],
        "outputs": ROBOT_OUT,
        "configs": [
            "configs/data/qa.yaml",
            "configs/embodiments/g1.yaml",
            "configs/splits/default.yaml",
        ],
    },
    "data.release": {
        "title": _t("Release thử (tầng 5)", "Trial release (tier 5)"),
        "command": "fw data release <work> --out fwdata/console/store/releases/<job>",
        "args": [A_WORK_DATA, _arg("name", "string", False, "Tên release", "Release name")],
        "outputs": ROBOT_OUT,
        "configs": ["configs/splits/default.yaml"],
    },
    "data.report": {
        "title": _t("Báo cáo dataset", "Dataset report"),
        "command": "fw data report <work>",
        "args": [A_WORK_DATA],
        "outputs": ROBOT_OUT,
    },
    "data.pipeline": {
        "title": _t("Cả pipeline robot", "Whole robot pipeline"),
        "command": "data.ingest → data.qa → data.release → data.report",
        "chain": list(runner.DATA_CHAIN),
        "args": [
            *A_DATASET,
            _arg(
                "release",
                "bool",
                False,
                "Có chạy bước release thử",
                "Run the trial release step",
                default=True,
            ),
            _arg("name", "string", False, "Tên release", "Release name"),
        ],
        "outputs": ROBOT_OUT,
    },
    "eval.diag_system": {
        "title": _t("Kiểm hệ thống F-SYS (R1–R6)", "System check F-SYS (R1–R6)"),
        "command": "fw eval diag-system --episode <trace> --store fwdata/console/store/eval/<job>",
        "args": [
            _arg(
                "episode",
                "path",
                True,
                "Thư mục trace (steps.jsonl, camera_params.jsonl, rollout_result.json)",
                "Trace folder (steps.jsonl, camera_params.jsonl, rollout_result.json)",
                root="fwdata or the testkit trace fixtures",
            )
        ],
        "configs": ["configs/eval/diagnosis/system.yaml"],
        "outputs": _t(
            "fwdata/console/store/eval/<job>/diagnosis/system.jsonl",
            "fwdata/console/store/eval/<job>/diagnosis/system.jsonl",
        ),
    },
    "eval.diag_train": {
        "title": _t("Kiểm lỗi train F-TRAIN, F-OFF", "Train check F-TRAIN, F-OFF"),
        "command": "fw eval diag-train --job <train job> --store fwdata/console/store/eval/<job>",
        "args": [
            _arg(
                "job",
                "path",
                True,
                "Thư mục job train có metrics.jsonl (đã đồng bộ về)",
                "Train job folder with metrics.jsonl (synced back)",
                root="fwdata",
            )
        ],
        "configs": ["configs/eval/diagnosis/train.yaml"],
        "outputs": _p("fwdata/console/store/eval/<job>/…jsonl"),
    },
}

# Parts of the process with no runnable kind here: where they run and how they are followed.
REMOTE: list[dict[str, Any]] = [
    {
        "id": "train",
        "stage": "train",
        "title": _t("Dạy model (Ψ₀ stage 3)", "Model training (Ψ₀ stage 3)"),
        "where": _t("Colab, GPU A100", "Colab, A100 GPU"),
        "runs_on": ["colab_a100"],
        "observe": _t(
            "metrics.jsonl đồng bộ về fwdata/tray/pair60k/<nhánh>/<job>/ (trang Dạy model, "
            "/api/status), số dư Colab từ fwdata/colab/*/guard.jsonl; chạy eval.diag_train "
            "trên log đã đồng bộ.",
            "metrics.jsonl synced into fwdata/tray/pair60k/<branch>/<job>/ (training page, "
            "/api/status), Colab balance from fwdata/colab/*/guard.jsonl; run eval.diag_train "
            "on the synced log.",
        ),
        "docs": ["docs/product/09-data-flows.md#f5--train", "docs/he/tray.md"],
        "why": _t(
            "Cần GPU; console không chạy job GPU.", "Needs a GPU; the console runs no GPU job."
        ),
    },
    {
        "id": "eval_closed_loop",
        "stage": "eval",
        "title": _t("Thi closed-loop trong mô phỏng", "Closed-loop evaluation in simulation"),
        "where": _t("rtx3060 (MuJoCo) hoặc Colab", "rtx3060 (MuJoCo) or Colab"),
        "runs_on": ["rtx3060", "colab"],
        "observe": _t(
            "Kết quả đồng bộ về fwdata/tray/pair60k/stage1-60k/ và đọc vào index "
            "(story.json); trang Thi và chấm.",
            "Results synced into fwdata/tray/pair60k/stage1-60k/ and read into the index "
            "(story.json); evaluation page.",
        ),
        "docs": ["docs/product/09-data-flows.md#f6--eval-closed-loop", "docs/he/tray.md"],
        "why": _t(
            "Cần server policy GPU và máy mô phỏng.", "Needs a GPU policy server and the sim box."
        ),
    },
    {
        "id": "datagen",
        "stage": "data",
        "title": _t("Sinh dữ liệu mô phỏng S1, S2", "Simulated data generation S1, S2"),
        "where": _t("rtx3060, nhiều worker MuJoCo", "rtx3060, many MuJoCo workers"),
        "runs_on": ["rtx3060"],
        "observe": _t(
            "Release đồng bộ về fwdata/rtx3060/*/fwdata/releases/; nạp thử ở đây bằng "
            "data.ingest (mẫu 'tray').",
            "Releases synced into fwdata/rtx3060/*/fwdata/releases/; try them here with "
            "data.ingest (the 'tray' samples).",
        ),
        "docs": ["docs/he/tray.md", "docs/g0/data-pipeline.md"],
        "why": _t(
            "Hàng giờ máy, nhiều worker; không chạy trên laptop.",
            "Hours of machine time on many workers; not run on the laptop.",
        ),
    },
    {
        "id": "eval.score",
        "stage": "eval",
        "title": _t("Chấm từng bước (fw eval score)", "Per-step scoring (fw eval score)"),
        "where": _t("Chưa chạy được ở đâu", "Cannot run anywhere yet"),
        "runs_on": [],
        "observe": _t(
            "Số chấm từng bước của vòng đang trích từ tài liệu (docs/he/tray.md).",
            "The round's per-step scores are quoted from docs/he/tray.md.",
        ),
        "docs": ["docs/product/09-data-flows.md#72-khoảng-trống-trong-tài-liệu"],
        "why": _t(
            "Repo chưa có TaskDefinition của task khay hay hai bàn (lớp mà --help nêu, "
            "flywheel_simple.tray.task:TrayTask, không tồn tại). Task giả duy nhất, "
            "flywheel.testkit.fakes.task:ToyPickPlace, bị scorer từ chối: bước `approach` "
            "chưa khai StageSpec.signals.",
            "The repo has no TaskDefinition for the tray or two-table task (the class --help "
            "names, flywheel_simple.tray.task:TrayTask, does not exist). The only fake task, "
            "flywheel.testkit.fakes.task:ToyPickPlace, is refused by the scorer: step "
            "`approach` declares no StageSpec.signals.",
        ),
    },
    {
        "id": "loop",
        "stage": "loop",
        "title": _t("Gom cụm, chọn dữ liệu, cổng kiểm", "Clustering, data selection, gate"),
        "where": _t("Script của DA-34 trên rtx3060 và Colab", "DA-34 scripts on rtx3060 and Colab"),
        "runs_on": ["rtx3060", "colab"],
        "observe": _t(
            "Kết quả vòng đọc từ docs/he/tray.md và index (story.json · round).",
            "Round results read from docs/he/tray.md and the index (story.json · round).",
        ),
        "docs": [
            "docs/product/09-data-flows.md#f7--vòng-failure--data",
            "docs/spec-v10-failure-to-data.md",
        ],
        "why": _t(
            "`fw` chưa có lệnh cho vòng lặp (fw --help: agentqa, eval, console, data, "
            "egocentric); flywheel.loop chỉ là thư viện.",
            "`fw` has no loop command (fw --help: agentqa, eval, console, data, egocentric); "
            "flywheel.loop is a library only.",
        ),
    },
    {
        "id": "holdout",
        "stage": "loop",
        "title": _p("Holdout"),
        "where": _t("Chỉ module gate", "The gate module only"),
        "runs_on": [],
        "observe": _t("Console không đọc vault/.", "The console never reads vault/."),
        "docs": ["CLAUDE.md"],
        "why": _t(
            "Bất biến dự án: chỉ `fw holdout run` của gate.",
            "Project invariant: only the gate's `fw holdout run`.",
        ),
    },
]


# ------------------------------------------------------------------ samples
def _cached(key: str, fn: Any) -> Any:
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_S:
            return hit[1]
    v = fn()
    with _cache_lock:
        _cache[key] = (time.time(), v)
    return v


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


DATASET_GLOBS = (
    "he/subset-check/src/*/meta/info.json",
    "psi-data/*/*/meta/info.json",
    "rtx3060/*/fwdata/releases/*/meta/info.json",
    "rtx3060/*/cut/*/*/meta/info.json",
    "datasets/*/releases/*/meta/info.json",
)


def _source_detail(path: Path) -> str | None:
    s = str(path).lower()
    if "psi-data" in s or "pickbetweentables" in s or "hugcontainer" in s:
        return "psi_data"
    if "tray" in s:
        return "planner_wbc"
    return None


def _mb(n: int) -> str:
    return "%.0f MB" % (n / 1e6) if n < 1e9 else "%.1f GB" % (n / 1e9)


def dataset_samples() -> list[dict[str, Any]]:
    fw = runner._fw()
    found = cards.load_cards_lenient(fw)
    gone = runner.hidden_data_names(runner.hidden_runs())
    out: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for pat in DATASET_GLOBS:
        for info_f in sorted(fw.glob(pat)):
            ds = info_f.parent.parent
            try:
                ds = runner.lerobot_dataset(str(ds))
            except ValueError:
                continue
            if ds in seen or gone.intersection(ds.parts):
                continue
            seen.add(ds)
            info = runner.jread(info_f, {}) or {}
            n_files, size = runner._tree_size(ds)
            vids = info.get("total_videos") or 0
            n_mp4 = sum(1 for _ in ds.glob("videos/**/*.mp4")) if vids else 0
            dc, lic, card_sd = runner.card_defaults(ds, found)
            sd = card_sd or _source_detail(ds)
            rel = str(ds.relative_to(fw.resolve()))
            eps = info.get("total_episodes")
            label = f"{rel} · {eps} tập · {_mb(size)}"
            s: dict[str, Any] = {
                "label": _t(label, label.replace(" tập", " episodes")),
                "params": {"dataset": rel, "source_detail": sd, "license": lic,
                           "data_class": dc, "split": "train"},
                "task": runner.task_of(ds), "fixture": False, "available": True,
                "episodes": eps, "frames": info.get("total_frames"), "bytes": size,
                "staged": not runner.stage_needed(ds, runner.staged_path(ds)),
            }  # fmt: skip
            if vids and n_mp4 < vids:
                s.update(available=False, reason=_t(
                    f"thiếu video: {n_mp4}/{vids} mp4 (QA sẽ loại các tập thiếu)",
                    f"missing videos: {n_mp4}/{vids} mp4 (QA would reject those episodes)",
                ))  # fmt: skip
            elif size > runner.STAGE_MAX_BYTES and not s["staged"]:
                s.update(available=False, reason=_t(
                    f"{_mb(size)} lớn hơn giới hạn chép 2 GB",
                    f"{_mb(size)} is over the 2 GB copy limit"))  # fmt: skip
            elif sd not in runner.SOURCE_DETAILS:
                s.update(available=False, reason=_t("không rõ loại nguồn",
                                                    "unknown source kind"))  # fmt: skip
            out.append(s)
    out.sort(key=lambda s: (not s["available"], s["bytes"]))
    return out


def data_work_samples(need_qa: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    wd = runner.store_dir() / "work"
    if not wd.is_dir():
        return out
    for w in sorted(wd.iterdir(), key=lambda p: -p.stat().st_mtime):
        if not (w / "source.json").is_file():
            continue
        ing = runner.jread(w / "ingest.json", {}) or {}
        src = runner.jread(w / "source.json", {}) or {}
        has_qa = (w / "qa" / "summary.json").is_file()
        label = "{} · {} · {} tập{}".format(
            w.name, ing.get("source_id", "?"), ing.get("episodes", "?"),
            " · đã QA" if has_qa else "")  # fmt: skip
        s: dict[str, Any] = {
            "label": _t(label, label.replace(" tập", " episodes").replace("đã QA", "QA done")),
            "params": {"work": str(w)}, "task": runner.task_of(Path(str(src.get("root")))),
            "fixture": False, "available": True,
        }  # fmt: skip
        if need_qa and not has_qa:
            s.update(available=False, reason=_t("chưa chạy data.qa", "data.qa has not run"))
        out.append(s)
    return out[:20]


FIXTURE_CASE = {
    "tr_clean": _t("sạch, không lỗi", "clean, no finding"),
    "tr_sync_delay": _t("ảnh trễ 0,12 s (R4)", "frames 0.12 s late (R4)"),
    "tr_calib_offset": _t("camera lệch calibration (R5)", "camera calibration offset (R5)"),
    "tr_missing": _t("thiếu tín hiệu (CHƯA RÕ)", "missing signals (UNCLEAR)"),
}


def trace_samples() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    fx = runner.trace_fixtures()
    for name, case in FIXTURE_CASE.items():
        d = fx / name
        if (d / "steps.jsonl").is_file():
            out.append({
                "label": _t("Fixture testkit {}: {}".format(name, case["vi"]),
                            "Testkit fixture {}: {}".format(name, case["en"])),
                "params": {"episode": str(d)}, "task": "two_table", "fixture": True,
                "available": True,
            })  # fmt: skip
    return out


def train_samples() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for task_id, tdir in runner._train_dirs():
        for f in sorted(runner._fw().glob(f"{tdir}/*/*/metrics.jsonl")):
            if ".attempt" in f.parent.parent.name:
                continue
            rel = str(f.parent.relative_to(runner._fw()))
            label = f"{f.parent.parent.name} · metrics.jsonl {_mb(f.stat().st_size)}"
            out.append({"label": _t(label, label), "params": {"job": rel}, "task": task_id,
                        "fixture": False, "available": True})  # fmt: skip
    return out


def ego_work_samples(gated: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pd = runner._fw() / "pipeline"
    for d in sorted(pd.glob("src_*"), key=lambda p: -p.stat().st_mtime) if pd.is_dir() else []:
        s = runner.jread(d / "source.json")
        if not isinstance(s, dict):
            continue
        label = "{} · {} · {} tập".format(d.name, s.get("source_detail"),
                                          len(s.get("episodes") or []))  # fmt: skip
        smp: dict[str, Any] = {
            "label": _t(label, label.replace(" tập", " episodes")), "params": {"work": str(d)},
            "task": None, "fixture": False, "available": True,
        }  # fmt: skip
        if gated and not runner.deid_done(d):
            smp.update(available=False, reason=_t("chưa che mặt xong", "not de-identified yet"))
        out.append(smp)
    return out[:20]


def artifact_samples() -> list[dict[str, Any]]:
    return [{"label": _p(a["label"]), "params": {"input": a["path"]}, "task": None,
             "fixture": False, "available": True}
            for a in runner.list_artifacts()[:20]]  # fmt: skip


def samples_for(kind: str) -> list[dict[str, Any]]:
    if kind in ("data.ingest", "data.pipeline"):
        return [dict(s) for s in _cached("datasets", dataset_samples)]
    if kind == "data.qa":
        return data_work_samples(False)
    if kind in ("data.release", "data.report"):
        return data_work_samples(True)
    if kind == "eval.diag_system":
        return trace_samples()
    if kind == "eval.diag_train":
        return train_samples()
    if kind == "ego.ingest":
        return [{"label": _t("EgoDex (tập con đã ghim)", "EgoDex (pinned subset)"),
                 "params": {"source": "egodex"}, "task": None, "fixture": False,
                 "available": True}]  # fmt: skip
    if kind in ("ego.deid", "ego.ea", "ego.pose", "ego.annotate", "ego.qa", "ego.report"):
        return ego_work_samples(kind in runner.GATED)
    if kind == "ego.pipeline":
        return ego_work_samples(False)
    if kind == "agentqa.run":
        return artifact_samples()
    return []


# ------------------------------------------------------------------ durations
def _seconds(j: dict[str, Any]) -> float | None:
    """The job's measured wall seconds; older records only have whole-second timestamps."""
    if isinstance(j.get("seconds"), (int, float)):
        return float(j["seconds"])
    try:
        a = datetime.fromisoformat(j["started"])
        b = datetime.fromisoformat(j["ended"])
    except (KeyError, TypeError, ValueError):
        return None
    return (b - a).total_seconds()


def durations() -> dict[str, list[tuple[dict[str, Any], float]]]:
    """Wall seconds of the ok jobs of each kind, from the job registry."""
    out: dict[str, list[tuple[dict[str, Any], float]]] = {}
    with runner._lock:
        jobs = sorted(runner.JOBREG.values(), key=lambda j: str(j.get("ended")))
    for j in jobs:  # oldest first, so the last entry of a kind is its latest run
        if j.get("state") != "ok":
            continue
        s = _seconds(j)
        if s is not None:
            out.setdefault(j["kind"], []).append((j.get("params") or {}, s))
    return out


def _same(past: dict[str, Any], sample: dict[str, Any]) -> bool:
    """A past job ran on this sample: every key both name agrees (defaults may be omitted)."""
    shared = [k for k, v in sample.items() if v is not None and k in past]
    return bool(shared) and all(str(past[k]) == str(sample[k]) for k in shared)


def catalog(locked: bool = False) -> dict[str, Any]:
    """The body of ``GET /api/kinds``."""
    dur = durations()
    tunnel = runner.TUNNEL.state()
    kinds: list[dict[str, Any]] = []
    for kind in sorted(runner.KINDS, key=lambda k: (STAGES.index(runner.PROCESS_STAGE[k]), k)):
        sp = SPEC[kind]
        needs = list(sp.get("needs") or [])
        samples = samples_for(kind)
        runs = dur.get(kind, [])
        for s in samples:
            past = [sec for p, sec in runs if _same(p, s["params"])]
            if past:
                s["last_seconds"] = round(past[-1], 1)
        e: dict[str, Any] = {
            "kind": kind, "stage": runner.PROCESS_STAGE[kind], "title": sp["title"],
            "label": runner.KIND_LABEL[kind], "command": sp["command"], "args": sp["args"],
            "samples": samples, "needs": needs, "runs_on": "laptop",
            "typical_seconds": round(statistics.median(s for _, s in runs), 1) if runs else None,
            "n_ok_runs": len(runs), "outputs": sp.get("outputs"), "available": True,
            "reason": None,
        }  # fmt: skip
        for k in ("chain", "configs", "interactive"):
            if k in sp:
                e[k] = sp[k]
        if "rtx3060_tunnel" in needs:  # the runner opens the tunnel when such a job starts
            e["needs_state"] = {"rtx3060_tunnel": tunnel}
        if locked:
            e.update(
                available=False, reason=_t("chế độ chỉ đọc (--lock)", "read-only mode (--lock)")
            )
        kinds.append(e)
    return {
        "time": runner.now(),
        "locked": locked,
        "stages": list(STAGES),
        "machines": {"laptop": {"slots": runner.MAX_SLOTS}, "rtx3060_tunnel": tunnel},
        "kinds": kinds,
        "remote": REMOTE,
    }
