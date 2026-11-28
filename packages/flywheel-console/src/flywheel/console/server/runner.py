# ruff: noqa: UP031
"""Job runner for the console.

Runs an allowlist of ``fw`` commands as subprocesses (argv lists, never a shell), keeps a
registry on disk under ``<fw_root>/console/jobs/<id>/{job.json,log.txt}``, opens one ssh tunnel
to the Ollama on rtx3060 when a model is needed, and derives the 6-stage ``/api/status``.
The client never supplies argv: it names a kind and params, and ``plan()`` builds the argv.
"""

from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from flywheel.console.index import cards, hidden
from flywheel.console.paths import ConsolePaths, active, guard
from flywheel.console.server import withhold

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".avi", ".webm")
TUNNEL_PORT = 11435
TUNNEL_URL = f"http://127.0.0.1:{TUNNEL_PORT}"
# loopback calls must never go through http_proxy
LOOPBACK = urllib.request.build_opener(urllib.request.ProxyHandler({}))
AGENT_MODEL = "hf.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB:Q4_K_M"
AGENT_REVISION = "1db54d5b12533ff1bcaa8e42cf4c667988a1f1be"

MAX_SLOTS = 2
_atexit_done = False


class NotFound(LookupError):
    """A requested job, work or episode does not exist (the server maps it to HTTP 404)."""


_slots = threading.BoundedSemaphore(MAX_SLOTS)
_model_lock = threading.Lock()
_lock = threading.RLock()
JOBREG: dict[str, dict[str, Any]] = {}  # id -> job dict
RT: dict[str, dict[str, Any]] = {}  # id -> {"cancel": Event, "proc": Popen | None, "child": id}

_P: ConsolePaths | None = None


def _p() -> ConsolePaths:
    return _P if _P is not None else active()


def _fw() -> Path:
    return _p().fw_root


def _repo() -> Path:
    return _p().repo


class ManifestUnreadable(RuntimeError):
    """``seed/tasks.yaml`` cannot be read, so which runs are held or hidden is unknown."""


_manifest_cache: tuple[tuple[Path, int, int], Any] | None = None


def _manifest() -> Any:
    """The seed task manifest, read again when the file changes.

    Unlike ``hidden.load``, a manifest that cannot be read raises: an empty list of held or hidden
    runs must mean "nothing is held", never "unknown"."""
    global _manifest_cache
    from flywheel.console.index import tasks as task_idx

    try:
        f = _p().seed / task_idx.FILE
        st = f.stat()
        key = (f, st.st_mtime_ns, st.st_size)
        hit = _manifest_cache
        if hit is None or hit[0] != key:
            hit = _manifest_cache = (key, task_idx.load(_p()))
    except Exception as e:  # missing, unreadable or invalid in any way
        raise ManifestUnreadable("seed/tasks.yaml cannot be read: results are not served") from e
    return hit[1]


def hidden_runs() -> hidden.Hidden:
    """The runs of ``withhold_runs``; raises ``ManifestUnreadable``."""
    return hidden.from_manifest(_manifest())


def _withheld_runs() -> set[str]:
    """Run ids under ``withhold_eval`` of any round in the **seed** manifest, never the index: a
    missing or broken index must not switch the filter off. Raises ``ManifestUnreadable``."""
    return {str(x) for r in _manifest().rounds for x in r.withhold_eval}


def jobs_dir() -> Path:
    return _p().jobs


def exports_dir() -> Path:
    return _p().exports


def aqa_dir() -> Path:
    """Agent QA output directory: ``<fw_root>/console/agentqa``."""
    return _p().console_dir / "agentqa"


def __getattr__(name: str) -> Path:
    if name == "AQA":
        return aqa_dir()
    raise AttributeError(name)


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def under(p: str | Path, base: str | Path) -> Path:
    """Resolve ``p`` and return it only when it is ``base`` or inside it; else ``ValueError``.

    Paths through ``vault/`` or a holdout are refused too (``PathDenied`` is a ``ValueError``).
    """
    return guard(p, [Path(base)])


def under_import(p: str | Path) -> Path:
    """``p`` under the home folder or the console upload folder."""
    for base in (Path.home(), _p().uploads):
        try:
            return under(p, base)
        except ValueError:
            continue
    raise ValueError("path outside allowed root")


_ffmpeg: list[str] = []


def ffmpeg_path() -> str:
    """ffmpeg (libx264) for the Human-1M export: $FW_FFMPEG, PATH, else imageio-ffmpeg via uvx."""
    if os.environ.get("FW_FFMPEG"):
        return os.environ["FW_FFMPEG"]
    found = shutil.which("ffmpeg")
    if found:
        return found
    if not _ffmpeg:
        try:
            uvx = shutil.which("uvx") or str(Path.home() / ".local/bin/uvx")
            r = subprocess.run(
                [uvx, "--from", "imageio-ffmpeg", "python", "-c",
                 "import imageio_ffmpeg as f; print(f.get_ffmpeg_exe())"],
                capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL,
            )  # fmt: skip
            out = r.stdout.strip().splitlines()
            _ffmpeg.append(out[-1] if r.returncode == 0 and out else "")
        except Exception:
            _ffmpeg.append("")
    return _ffmpeg[0]


def uv_bin() -> str:
    return shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")


def fw_cmd() -> list[str]:
    fw_bin = _repo() / ".venv" / "bin" / "fw"
    if fw_bin.exists():
        return [str(fw_bin)]
    return [uv_bin(), "run", "--project", str(_repo()), "fw"]


def jread(path: str | Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def tail_text(path: str | Path, n: int = 4096) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            sz = f.tell()
            f.seek(max(0, sz - n))
            return f.read().decode("utf-8", "replace")
    except Exception:
        return ""


# ------------------------------------------------------------------ ssh tunnel
class Tunnel:
    """One on-demand ssh -L to the Ollama of rtx3060. The only ssh command this module runs."""

    CMD = [
        "ssh", "-N", "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
        "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
        "-L", f"127.0.0.1:{TUNNEL_PORT}:127.0.0.1:11434", "rtx3060",
    ]  # fmt: skip

    def __init__(self) -> None:
        self.proc: subprocess.Popen[bytes] | None = None
        self.lk = threading.Lock()
        self.err: str | None = None
        self.external = False
        self._tags: tuple[float, list[Any] | None] = (0.0, None)

    def tags(self, fresh: bool = False) -> list[Any] | None:
        t, v = self._tags
        if not fresh and time.time() - t < 4:
            return v
        try:
            with LOOPBACK.open(TUNNEL_URL + "/api/tags", timeout=3) as r:
                v = [m["name"] for m in json.load(r).get("models", [])]
        except Exception:
            v = None
        self._tags = (time.time(), v)
        return v

    def state(self) -> str:
        return "up" if self.tags() is not None else "down"

    def ensure(self, timeout: float = 15) -> bool:
        """Start the tunnel if it is not healthy; return True when /api/tags answers."""
        with self.lk:
            if self.tags(True) is not None:
                return True
            if self.proc is None or self.proc.poll() is not None:
                self.err = None
                self.proc = subprocess.Popen(
                    self.CMD, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE, start_new_session=True,
                )  # fmt: skip
            end = time.time() + timeout
            while time.time() < end:
                if self.proc.poll() is not None:
                    try:
                        err = self.proc.stderr.read() if self.proc.stderr else b""
                        self.err = err.decode("utf-8", "replace")[-300:]
                    except Exception:
                        pass
                    return False
                if self.tags(True) is not None:
                    return True
                time.sleep(0.5)
            return False

    def close(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except Exception:
                pass


TUNNEL = Tunnel()


def models_info() -> dict[str, Any]:
    tags = TUNNEL.tags()
    return {
        "tunnel": "up" if tags is not None else "down", "models": tags or [],
        "agent_model": AGENT_MODEL, "agent_ready": bool(tags and AGENT_MODEL in tags),
        "error": TUNNEL.err,
    }  # fmt: skip


# ------------------------------------------------------------------ work dirs
def work_path(p: str | Path) -> Path:
    w = under(p, _fw() / "pipeline")
    if not (w / "source.json").is_file():
        raise ValueError(f"not a pipeline work dir (no source.json): {w.name}")
    return w


def deid_done(work: str | Path) -> bool:
    """True when later tiers may read this work dir: every video has a de-identified copy, or
    the source carries a documented waiver (EgoDex). Project rule: de-identify first."""
    s = jread(Path(work) / "source.json", {})
    if s.get("deid_waiver"):
        return True
    n = len(s.get("episodes") or [])
    return n > 0 and len(s.get("deid_copies") or {}) >= n


def _count_lines(f: Path) -> int:
    with open(f) as fh:
        return sum(1 for _ in fh)


def _qa_counts(f: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    if not f.is_file():
        return out
    with open(f) as fh:
        for ln in fh:
            try:
                d = json.loads(ln).get("decision")
            except Exception:
                continue
            if d:
                out[d] = out.get(d, 0) + 1
    return out


def tiers(work: str | Path) -> list[dict[str, Any]]:
    work = Path(work)
    s = jread(work / "source.json", {})
    n = len(s.get("episodes") or [])
    eps = (
        [d for d in (work / "egocentric").glob("ep_*") if d.is_dir()]
        if (work / "egocentric").is_dir()
        else []
    )
    npose = sum(1 for d in eps if (d / "pose.npz").exists())
    nlab = sum(1 for d in eps if (d / "labels.json").exists())
    qa = work / "qa" / "egocentric.jsonl"
    nqa = _count_lines(qa) if qa.is_file() else 0
    rep = (work / "report" / "egocentric.json").is_file()
    ncopies = len(s.get("deid_copies") or {})
    waived = bool(s.get("deid_waiver"))

    def st(k: int, total: int) -> str:
        return "done" if total and k >= total else ("partial" if k else "todo")

    isvid = s.get("source_detail") == "ego_video"
    nea = sum(1 for d in eps if (d / "pose_ea.npz").exists())
    rj = jread(work / "report" / "egocentric.json", {}) or {}
    qc = _qa_counts(qa) if nqa else {}
    rep_txt = "{} khung · {:.1f} s".format(rj.get("frames"), rj.get("seconds") or 0) if rep else ""
    src_txt = "%d tập · %.1f MB" % (n, (s.get("total_bytes") or 0) / 1e6) if s else ""
    srcs = rj.get("label_sources") or {}
    seg_txt = (
        "{} đoạn · nhãn {}".format(
            rj.get("segments"), ", ".join("{} {}".format(*kv) for kv in srcs.items())
        )
        if rj.get("segments")
        else ("%d tập có nhãn" % nlab if nlab else "")
    )
    return [
        {"id": "ingest", "label": "Ingest", "state": "done" if s else "todo", "n": n, "total": n,
         "note": "%d tập, %s" % (n, s.get("source_detail") or "?"), "result": src_txt},
        {"id": "deid", "label": "Che mặt", "state": "done" if deid_done(work) else st(ncopies, n),
         "n": ncopies, "total": n,
         "note": "miễn (EgoDex, có văn bản miễn)" if waived else "%d/%d bản đã che" % (ncopies, n),
         "result": "không che (miễn)" if waived
         else ("%d bản .deid.mp4" % ncopies if ncopies else "")},
        {"id": "ea", "label": "E-A (bàn tay + camera)",
         "state": ("done" if nea >= n and n else st(nea, n)) if isvid else "na",
         "n": nea, "total": n,
         "note": "%d/%d" % (nea, n) if isvid else "không cần: EgoDex có E-B",
         "result": "%d tập có pose E-A" % nea if nea else ""},
        {"id": "pose", "label": "Pose", "state": st(npose, n), "n": npose, "total": n,
         "note": "%d/%d" % (npose, n), "result": "%d tập có pose.npz" % npose if npose else ""},
        {"id": "annotate", "label": "Gắn nhãn bước", "state": st(nlab, n), "n": nlab,
         "total": n, "note": "%d/%d" % (nlab, n), "result": seg_txt},
        {"id": "qa", "label": "QA", "state": st(nqa, n), "n": nqa, "total": n,
         "note": "%d/%d" % (nqa, n), "result": " · ".join("%d %s" % (v, k) for k, v in qc.items())},
        {"id": "report", "label": "Báo cáo", "state": "done" if rep else "todo", "n": int(rep),
         "total": 1, "note": "có" if rep else "chưa có",
         "result": rep_txt},
    ]  # fmt: skip


def work_summary(work: str | Path) -> dict[str, Any]:
    work = Path(work)
    rep = jread(work / "report" / "egocentric.json", {}) or {}
    qa = {"pass": 0, "flag": 0, "reject": 0}
    for k, v in _qa_counts(work / "qa" / "egocentric.jsonl").items():
        qa[k] = qa.get(k, 0) + v
    s = jread(work / "source.json", {})
    return {
        "episodes": rep.get("episodes"), "frames": rep.get("frames"),
        "seconds": rep.get("seconds"), "segments": rep.get("segments"),
        "steps": rep.get("steps"), "label_sources": rep.get("label_sources"),
        "qa": qa, "source_id": s.get("source_id"), "root": s.get("root"),
        "data_class": s.get("data_class"), "has_report": bool(rep),
    }  # fmt: skip


def list_works() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    pd = _fw() / "pipeline"
    with _lock:
        jobs = list(JOBREG.values())
    for d in sorted(pd.glob("src_*"), key=lambda p: -p.stat().st_mtime):
        if not (d / "source.json").is_file():
            continue
        t = tiers(d)
        for x in t:
            js = [
                j for j in jobs
                if j["kind"] == "ego." + x["id"] and j["state"] == "ok"
                and j["outputs"].get("work") == str(d) and j.get("started") and j.get("ended")
            ]  # fmt: skip
            if js:
                j = max(js, key=lambda j: j["ended"])
                span = datetime.fromisoformat(j["ended"]) - datetime.fromisoformat(j["started"])
                x["took"] = round(span.total_seconds())
        s = jread(d / "source.json", {})
        mtime = datetime.fromtimestamp(d.stat().st_mtime).astimezone().isoformat(timespec="seconds")
        out.append(
            {
                "name": d.name, "path": str(d), "source_detail": s.get("source_detail"),
                "root": s.get("root"), "episodes": len(s.get("episodes") or []), "tiers": t,
                "summary": work_summary(d), "mtime": mtime,
            }
        )  # fmt: skip
    return out


# ------------------------------------------------------------------ planning
GATED = ("ego.ea", "ego.pose", "ego.annotate", "ego.qa", "ego.report")
STEP_STAGE = {
    "ego.ingest": "collect", "ego.deid": "process", "ego.ea": "process", "ego.pose": "process",
    "ego.annotate": "process", "ego.qa": "process", "ego.report": "process",
    "ego.pipeline": "process", "ego.human1m": "release", "export.zip": "release",
    "agentqa.run": "process", "agentqa.review": "process",
    "data.ingest": "collect", "data.qa": "process", "data.release": "release",
    "data.report": "process", "data.pipeline": "process",
    "eval.diag_system": "eval", "eval.diag_train": "eval",
}  # fmt: skip
KIND_LABEL = {
    "ego.ingest": "Ingest", "ego.deid": "Che mặt", "ego.ea": "E-A (bàn tay + camera)",
    "ego.pose": "Pose", "ego.annotate": "Gắn nhãn bước", "ego.qa": "QA", "ego.report": "Báo cáo",
    "ego.pipeline": "Cả pipeline", "ego.human1m": "Xuất Human-1M", "export.zip": "Zip metadata",
    "agentqa.run": "Agent QA", "agentqa.review": "Duyệt phát hiện",
    "data.ingest": "Ingest robot", "data.qa": "QA robot", "data.release": "Release robot",
    "data.report": "Báo cáo robot", "data.pipeline": "Pipeline robot",
    "eval.diag_system": "Kiểm hệ thống", "eval.diag_train": "Kiểm lỗi train",
}  # fmt: skip
KINDS: frozenset[str] = frozenset(KIND_LABEL)
# Process stage of each kind, as the console's six stages name them (one of
# data, qa, train, eval, diagnose, loop, ops); /api/kinds and job.json carry it.
PROCESS_STAGE = {
    "ego.ingest": "data", "ego.deid": "data", "ego.ea": "data", "ego.pose": "data",
    "ego.annotate": "data", "ego.qa": "qa", "ego.report": "data", "ego.pipeline": "data",
    "ego.human1m": "data", "export.zip": "ops", "agentqa.run": "qa", "agentqa.review": "qa",
    "data.ingest": "data", "data.qa": "qa", "data.release": "data", "data.report": "data",
    "data.pipeline": "data", "eval.diag_system": "diagnose", "eval.diag_train": "diagnose",
}  # fmt: skip
CHAIN_KINDS = ("ego.pipeline", "data.pipeline")
DATA_CHAIN = ["data.ingest", "data.qa", "data.release", "data.report"]
SOURCE_DETAILS = ("psi_data", "planner_wbc", "teleop_pico")
DATA_CLASSES = ("public", "internal", "restricted")
LICENSE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+-]{0,63}$")
STAGE_MAX_BYTES = 2 << 30  # a dataset is copied into the console store; refuse larger ones
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def agent_config_file() -> Path:
    """Copy of configs/eval/agentqa/agent.yaml pointed at the tunnel; prompt path made absolute."""
    import yaml

    src = _repo() / "configs" / "eval" / "agentqa" / "agent.yaml"
    cfg = yaml.safe_load(src.read_text())
    for key in ("agent", "vision"):
        cfg["models"][key]["base_url"] = TUNNEL_URL + "/v1"
    cfg["models"]["agent"]["model"] = AGENT_MODEL
    cfg["models"]["agent"]["revision"] = AGENT_REVISION
    cfg["prompt"] = str(src.parent / cfg["prompt"])
    _p().config.mkdir(parents=True, exist_ok=True)
    out = _p().config / "agent.yaml"
    body = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
    out.write_text(
        "# generated by the console runner from configs/eval/agentqa/agent.yaml\n" + body
    )
    return out


def _est_script() -> Path:
    return (
        _repo() / "packages" / "flywheel-data" / "src" / "flywheel" / "data" / "ingest"
        / "egocentric" / "estimate_job.py"
    )  # fmt: skip


def auto_estimates(work: str | Path, explicit: str | None) -> list[str]:
    """``--estimates`` for the E-A output this console produced for ``work``."""
    if explicit:
        ed = under(explicit, _fw())
        if not ed.is_dir():
            raise ValueError("estimates is not a folder")
        return ["--estimates", str(ed)]
    ed = _p().console_dir / "estimates" / Path(work).name / "out"
    return ["--estimates", str(ed)] if ed.is_dir() and next(ed.glob("ep_*.npz"), None) else []


def _reviewer() -> str:
    """Reviewer name: ``FW_REVIEWER``, else the repo's ``git config user.name``, else refuse."""
    name = os.environ.get("FW_REVIEWER", "").strip()
    if not name:
        try:
            r = subprocess.run(
                ["git", "-C", str(_repo()), "config", "user.name"],
                capture_output=True, text=True, timeout=5, check=False,
            )  # fmt: skip
            name = r.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            name = ""
    if not name:
        raise ValueError("no reviewer: set FW_REVIEWER or git config user.name")
    return name


def _plan_agentqa_review(p: dict[str, Any], fw: list[str]) -> dict[str, Any]:
    rep = under(p.get("reports") or "", _fw())
    if not rep.is_file():
        raise ValueError("reports.jsonl not found")
    rid = str(p.get("report_id") or "")
    if not ID_RE.match(rid):
        raise ValueError("bad report_id")
    decs = p.get("decisions") or []
    if not decs or len(decs) > 50:
        raise ValueError("cần quyết định cho từng phát hiện (agree hoặc override + lý do)")
    ds: list[str] = []
    for x in decs:
        fid = str(x.get("finding_id") or "")
        if not ID_RE.match(fid):
            raise ValueError("bad finding_id")
        if x.get("decide") == "agree":
            ds.append(fid + "=agree")
        elif x.get("decide") == "override":
            why = str(x.get("reason") or "").strip()
            if not why or len(why) > 500:
                raise ValueError(f"cần lý do (<= 500 ký tự) cho {fid}")
            ds.append(fid + "=override:" + why)
        else:
            raise ValueError("decide must be agree or override")
    out = aqa_dir() / "reviews"
    argv = fw + ["agentqa", "review", "--reports", str(rep), "--report-id", rid]
    argv += ["--reviewer", _reviewer()]
    argv += [x for d in ds for x in ("--decide", d)] + ["--out", str(out)]
    return {"argv": argv, "outputs": {"out": str(out)}}


# ------------------------------------------------------------------ robot data and eval kinds
# `fw data` resolves every dataset against $FW_ROOT and appends LedgerEntry rows under
# $FW_ROOT/sites/local/runs; `fw data release` freezes into $FW_ROOT/releases. A console
# job runs with FW_ROOT set to the console's own store, so none of that touches the
# project's sources, releases or ledger. A dataset outside the store is copied in first.
def store_dir() -> Path:
    return _p().store


def trace_fixtures() -> Path:
    """The testkit's recorded-trace fixtures (four two-table traces, not real runs)."""
    return (
        _repo() / "packages" / "flywheel-testkit" / "src" / "flywheel" / "testkit" / "fixtures"
        / "trace"
    )  # fmt: skip


def task_of(path: Path) -> str | None:
    """The task a LeRobot dataset or a train job is about, read from its path."""
    s = str(path).lower()
    if "tray" in s:
        return "tray"
    if "pickbetweentables" in s or "two_table" in s or "two-table" in s:
        return "two_table"
    return None


def _tree_size(d: Path) -> tuple[int, int]:
    n = tot = 0
    for dp, _dns, fns in os.walk(d):
        for fn in fns:
            try:
                tot += (Path(dp) / fn).stat().st_size
                n += 1
            except OSError:
                continue
    return n, tot


def staged_path(ds: Path) -> Path:
    """Where ``ds`` lives inside the console store (itself when it is already there)."""
    store = store_dir().resolve()
    if ds.is_relative_to(store):
        return ds
    rel = ds.relative_to(_fw().resolve()).as_posix()
    return store / "datasets" / re.sub(r"[^A-Za-z0-9_.-]", "_", rel.replace("/", "__"))[:200]


def lerobot_dataset(raw: Any) -> Path:
    """A LeRobot v2.1 dataset under ``fw_root`` (not the vault, not other console folders)."""
    raw = str(raw or "")
    if not raw:
        raise ValueError("dataset: cần đường dẫn tới một dataset LeRobot v2.1")
    fwr = _fw()
    ds = under(raw if Path(raw).is_absolute() else fwr / raw, fwr)
    cd = _p().console_dir.resolve()
    if ds.is_relative_to(cd) and not ds.is_relative_to(store_dir().resolve() / "datasets"):
        raise ValueError("dataset: thư mục của console không phải dataset")
    info = jread(ds / "meta" / "info.json")
    if not isinstance(info, dict):
        raise ValueError("dataset: không có meta/info.json")
    if info.get("codebase_version") != "v2.1":
        raise ValueError(
            "dataset: codebase_version {} không phải v2.1".format(info.get("codebase_version"))
        )
    return ds


def stage_needed(src: Path, dst: Path) -> bool:
    """True unless ``dst`` already holds a copy with the same file count and bytes."""
    if src == dst:
        return False
    if not (dst / "meta" / "info.json").is_file():
        return True
    return _tree_size(src) != _tree_size(dst)


def data_work(raw: Any) -> Path:
    """A work dir that a console ``data.ingest`` wrote (under the store, with source.json)."""
    w = under(str(raw or "") or "/nonexistent", store_dir() / "work")
    if not (w / "source.json").is_file():
        raise ValueError(f"không phải work dir của data.ingest (thiếu source.json): {w.name}")
    return w


def safe_license(raw: Any) -> str:
    """A card licence made fit for ``--license``: characters outside ``LICENSE_RE`` dropped,
    spaces collapsed, at most 64; ``unknown`` when nothing is left. The catalogue keeps the
    card's own string."""
    s = re.sub(r"[^A-Za-z0-9 ._+-]", "", str(raw or ""))
    s = re.sub(r"\s+", " ", s).strip(" ._+-")[:64].strip()
    return s if LICENSE_RE.match(s) else "unknown"


def card_defaults(ds: Path, found: list[cards.Card] | None = None) -> tuple[str, str, str | None]:
    """``(data_class, license, source_detail)`` of a dataset from its card under ``fw_root``.

    No card: ``restricted``, ``unknown`` and no source detail. Bad cards are skipped."""
    found = cards.load_cards_lenient(_fw()) if found is None else found
    c = cards.card_for_path(found, _fw(), ds)
    if c is None:
        return "restricted", "unknown", None
    sd = c.data.get("source_detail")
    return str(c.data["data_class"]), safe_license(c.data["license"]), sd or None


def _choice(p: dict[str, Any], key: str, choices: tuple[str, ...], default: str | None) -> str:
    v = str(p.get(key) or default or "")
    if v not in choices:
        raise ValueError("{} phải là một trong {}".format(key, ", ".join(choices)))
    return v


def _plan_data(kind: str, p: dict[str, Any], job_id: str, fw: list[str]) -> dict[str, Any]:
    store = store_dir()
    base: dict[str, Any] = {"fw_root": str(store)}
    if kind == "data.ingest":
        ds = lerobot_dataset(p.get("dataset"))
        sd = _choice(p, "source_detail", SOURCE_DETAILS, None)
        card_dc, card_lic, _sd = card_defaults(ds)  # omitted params follow the dataset card
        dc = _choice(p, "data_class", DATA_CLASSES, card_dc)
        split = _choice(p, "split", ("train", "dev"), "train")
        lic = str(p.get("license") or card_lic).strip()
        if not LICENSE_RE.match(lic):
            raise ValueError("license: chữ, số, khoảng trắng và . _ + - (tối đa 64)")
        dst = staged_path(ds)
        steps: list[list[str]] = []
        if stage_needed(ds, dst):
            n, size = _tree_size(ds)
            if size > STAGE_MAX_BYTES:
                raise ValueError(
                    "dataset %.1f GB, quá giới hạn chép %.0f GB vào store của console"
                    % (size / 1e9, STAGE_MAX_BYTES / 1e9)
                )
            steps.append(["python:stage", str(ds), str(dst)])
        work = store / "work" / job_id
        steps.append(fw + ["data", "ingest", str(dst), "--source-detail", sd, "--license", lic,
                           "--data-class", dc, "--split", split, "--work", str(work)])  # fmt: skip
        return base | {
            "argv": steps[-1], "steps": steps, "task": task_of(ds),
            "outputs": {"work": str(work), "dataset": str(ds), "staged": str(dst)},
        }  # fmt: skip
    work = data_work(p.get("work"))
    out: dict[str, Any] = {"work": str(work)}
    if kind == "data.qa":
        argv = fw + ["data", "qa", str(work)]
        out["reports"] = str(work / "qa" / "reports.jsonl")
    elif kind == "data.release":
        if not (work / "qa" / "reports.jsonl").is_file():
            raise ValueError("chưa có QA cho work dir này: chạy data.qa trước")
        rel = store / "releases" / job_id
        argv = fw + ["data", "release", str(work), "--out", str(rel)]
        name = str(p.get("name") or "")
        if name:
            if not NAME_RE.match(name):
                raise ValueError("name: chỉ chữ, số, - _ .")
            argv += ["--name", name]
        out["release"] = str(rel)
    elif kind == "data.report":
        if not (work / "qa" / "summary.json").is_file():
            raise ValueError("chưa có QA cho work dir này: chạy data.qa trước")
        argv = fw + ["data", "report", str(work)]
        out["page"] = str(work / "report" / "index.html")
    else:
        raise ValueError(f"unknown kind: {kind}")
    src = jread(work / "source.json", {}) or {}
    return base | {"argv": argv, "outputs": out, "task": task_of(Path(str(src.get("root"))))}


def trace_input(raw: Any) -> tuple[Path, bool]:
    """A recorded trace for ``fw eval diag-system``: under fw_root, or a testkit fixture.

    Returns the path and whether it is a fixture."""
    raw = str(raw or "")
    if not raw:
        raise ValueError("episode: cần thư mục trace (steps.jsonl, rollout_result.json)")
    inside = False
    for root, is_fx in ((trace_fixtures(), True), (_fw(), False)):
        cand = Path(raw) if Path(raw).is_absolute() else root / raw
        try:
            ep = under(cand, root)
        except ValueError:
            continue
        inside = True
        if ep.is_dir() and (ep / "steps.jsonl").is_file():
            return ep, is_fx
        if ep.is_file() and ep.name in ("steps.jsonl", "rollout_result.json"):
            return ep, is_fx
    if inside:
        raise ValueError("episode: không thấy steps.jsonl hay rollout_result.json")
    raise ValueError("episode: path outside allowed roots")


def _plan_eval(kind: str, p: dict[str, Any], job_id: str, fw: list[str]) -> dict[str, Any]:
    store = store_dir() / "eval" / job_id
    if kind == "eval.diag_system":
        ep, is_fx = trace_input(p.get("episode"))
        argv = fw + ["eval", "diag-system", "--episode", str(ep), "--store", str(store)]
        return {
            "argv": argv, "fw_root": str(store_dir()), "task": "two_table" if is_fx else None,
            "outputs": {"episode": str(ep), "store": str(store), "fixture": is_fx},
        }  # fmt: skip
    raw = str(p.get("job") or "")
    if not raw:
        raise ValueError("job: cần thư mục job train có metrics.jsonl")
    j = under(raw if Path(raw).is_absolute() else _fw() / raw, _fw())
    if not ((j.is_dir() and (j / "metrics.jsonl").is_file()) or j.name == "metrics.jsonl"):
        raise ValueError("job: không thấy metrics.jsonl")
    argv = fw + ["eval", "diag-train", "--job", str(j), "--store", str(store)]
    return {"argv": argv, "fw_root": str(store_dir()), "task": task_of(j),
            "outputs": {"job": str(j), "store": str(store)}}  # fmt: skip


def plan(kind: str, p: dict[str, Any] | None, job_id: str) -> dict[str, Any]:
    """Validate params and build ``{argv, outputs, ...}`` or raise ``ValueError``.

    Pure: starts no process, opens no tunnel. The client never supplies argv.
    """
    p = p or {}
    fw = fw_cmd()
    fwr = _fw()
    if kind == "ego.ingest":
        src = p.get("source")
        split = p.get("split") or "train"
        if split not in ("train", "dev"):
            raise ValueError("split must be train or dev")
        if src == "video":
            root = under_import(p.get("root") or "")
            if not root.is_dir():
                raise ValueError("root is not a folder")
            return {"argv": fw + ["egocentric", "ingest", "video", "--root", str(root),
                                  "--split", split]}  # fmt: skip
        if src == "egodex":
            return {"argv": fw + ["egocentric", "ingest", "egodex", "--split", split]}
        raise ValueError("source must be video or egodex")
    if kind == "ego.ea":
        work = work_path(p.get("work") or "")
        if not deid_done(work):
            raise ValueError("chưa che mặt xong: chạy bước Che mặt trước")
        src = jread(work / "source.json", {})
        if src.get("source_detail") != "ego_video":
            raise ValueError("E-A chỉ dành cho video tự quay; EgoDex dùng E-B có sẵn")
        ed = _p().console_dir / "estimates" / work.name
        mp = fwr / "models" / "mediapipe" / "hand_landmarker.task"
        steps = [
            fw + ["egocentric", "pose", str(work), "--job", str(ed / "jobs.json")],
            [uv_bin(), "run", "--no-project", "--python", "3.10", "--with", "mediapipe==1.2.2",
             "--with", "opencv-python-headless==5.0.0.93",
             "--with", "opencv-contrib-python==5.0.0.93", "python", str(_est_script()),
             "--manifest", str(ed / "jobs.json"), "--root", str(src.get("root")),
             "--out", str(ed / "out"), "--model", str(mp)],
            fw + ["egocentric", "pose", str(work), "--estimates", str(ed / "out")],
        ]  # fmt: skip
        return {"argv": steps[0], "steps": steps, "pre": str(ed),
                "outputs": {"work": str(work), "estimates": str(ed / "out")}}  # fmt: skip
    if kind in ("ego.deid", "ego.pose", "ego.annotate", "ego.qa", "ego.report"):
        work = work_path(p.get("work") or "")
        if kind in GATED and not deid_done(work):
            raise ValueError(
                "chưa che mặt xong: chạy bước Che mặt trước "
                "(video egocentric phải che mặt trước mọi bước khác)"
            )
        sub = kind.split(".")[1]
        argv = fw + ["egocentric", sub, str(work)]
        pl: dict[str, Any] = {"outputs": {"work": str(work)}}
        if sub == "annotate":
            argv += ["--endpoint", TUNNEL_URL + "/v1"]
            pl["model"] = True
            pl["tunnel"] = True
        if sub == "pose":
            argv += auto_estimates(work, p.get("estimates"))
        pl["argv"] = argv
        return pl
    if kind == "ego.human1m":
        name = str(p.get("name") or "")
        if not NAME_RE.match(name):
            raise ValueError("name: chỉ chữ, số, - _ .")
        works = p.get("works") or []
        if not works or not isinstance(works, list) or len(works) > 20:
            raise ValueError("chọn 1-20 work dir")
        argv = fw + ["egocentric", "human1m", str(fwr / "human1m" / name), "--workers", "2"]
        for w in works:
            argv += ["--work", str(work_path(w))]
        for w in works:
            argv += auto_estimates(work_path(w), None)
        for e in p.get("estimates") or []:
            ed = under(e, fwr)
            if not ed.is_dir():
                raise ValueError("estimates is not a folder")
            argv += ["--estimates", str(ed)]
        sample = int(p.get("sample") or 0)
        if not 0 <= sample <= 200:
            raise ValueError("sample 0-200")
        if sample:
            argv += ["--sample", str(sample)]
        return {"argv": argv, "outputs": {"out": str(fwr / "human1m" / name)}}
    if kind == "export.zip":
        raw = str(p.get("path") or "")
        d = under(raw if Path(raw).is_absolute() else fwr / raw, fwr)
        if not d.is_dir():
            raise ValueError("not a folder")
        if "console" in d.relative_to(fwr.resolve()).parts:
            raise ValueError("the console's own folder is not exportable")
        return {"argv": ["python:export.zip", str(d)], "outputs": {"dir": str(d)}, "python": True}
    if kind == "agentqa.run":
        inp = under(p.get("input") or "", fwr)
        if not inp.exists():
            raise ValueError("input not found")
        out = aqa_dir() / job_id
        cfg = _p().config / "agent.yaml"
        return {
            "argv": fw + ["agentqa", "run", "--input", str(inp), "--out", str(out),
                          "--config", str(cfg)],
            "outputs": {"out": str(out), "input": str(inp)}, "model": True, "tunnel": True,
        }  # fmt: skip
    if kind == "agentqa.review":
        return _plan_agentqa_review(p, fw)
    if kind in ("data.ingest", "data.qa", "data.release", "data.report"):
        return _plan_data(kind, p, job_id, fw)
    if kind in ("eval.diag_system", "eval.diag_train"):
        return _plan_eval(kind, p, job_id, fw)
    raise ValueError(f"unknown kind: {kind}")


def prepare(kind: str) -> None:
    """Side effects a real run needs before it starts (the tunnel and the agent config)."""
    if kind != "agentqa.run":
        return
    if not TUNNEL.ensure():
        raise ValueError(
            "model chưa sẵn sàng: tunnel tới rtx3060 không lên (%s)"
            % (TUNNEL.err or "hết thời gian")
        )
    if not models_info()["agent_ready"]:
        raise ValueError(f"model chưa sẵn sàng: {AGENT_MODEL} chưa có trên rtx3060")
    agent_config_file()
    aqa_dir().mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------ registry
def new_id() -> str:
    return "j-{}-{}".format(datetime.now().strftime("%Y%m%d-%H%M%S"), os.urandom(2).hex())


def save(job: dict[str, Any]) -> None:
    with _lock:
        d = jobs_dir() / job["id"]
        tmp = d / "job.json.tmp"
        tmp.write_text(json.dumps(job, ensure_ascii=False, indent=1, default=str))
        os.replace(tmp, d / "job.json")


def make_job(
    kind: str, params: dict[str, Any], chain_id: str | None = None, task: str = "tray",
    pl: dict[str, Any] | None = None, job_id: str | None = None,
) -> dict[str, Any]:  # fmt: skip
    jid = job_id or new_id()
    (jobs_dir() / jid).mkdir(parents=True, exist_ok=True)
    if pl and "task" in pl:  # data.* and eval.* kinds read the task from their input
        task = pl["task"] or "unknown"
    job: dict[str, Any] = {
        "id": jid, "kind": kind, "stage": STEP_STAGE.get(kind, "process"),
        "process_stage": PROCESS_STAGE.get(kind, "ops"), "task": task,
        "params": params, "argv": (pl or {}).get("argv", []), "cwd": str(_repo()),
        "host": "laptop", "state": "queued", "rc": None, "created": now(), "started": None,
        "ended": None, "outputs": dict((pl or {}).get("outputs") or {}),
    }  # fmt: skip
    if chain_id:
        job["chain_id"] = chain_id
    with _lock:
        JOBREG[jid] = job
        RT[jid] = {"cancel": threading.Event(), "proc": None}
    (jobs_dir() / jid / "log.txt").touch()
    save(job)
    return job


def jlog(job: dict[str, Any], text: str) -> None:
    with open(jobs_dir() / job["id"] / "log.txt", "ab") as f:
        f.write(text.encode("utf-8", "replace"))


def finish(job: dict[str, Any], state: str, rc: int | None = None, note: str | None = None) -> None:
    job["state"] = state
    job["rc"] = rc
    job["ended"] = now()
    t0 = job.pop("_t0", None)
    if t0 is not None:  # wall seconds at sub-second precision, for /api/kinds durations
        job["seconds"] = round(time.time() - t0, 2)
    if note:
        job["note"] = note
    save(job)


def pid_alive(pid: Any) -> bool:
    """True when ``pid`` is a live process; a zombie or foreign pid counts as dead."""
    try:
        pid = int(pid)
        os.kill(pid, 0)
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (TypeError, ValueError, ProcessLookupError, FileNotFoundError, IndexError):
        return False
    except PermissionError:
        return True


def job_alive(j: dict[str, Any]) -> bool:
    """A queued/running record whose process (or, for a chain, one of its children) is alive."""
    if pid_alive(j.get("pid")):
        return True
    if j.get("kind") in CHAIN_KINDS:
        for cid in (j.get("outputs") or {}).get("children", []):
            c = jread(jobs_dir() / cid / "job.json", {}) or {}
            if c.get("state") in ("queued", "running") and pid_alive(c.get("pid")):
                return True
    return False


def watch_foreign(jid: str) -> None:
    """Follow a job owned by another console server until it ends; if its process dies without a
    recorded result, mark it failed once."""

    def loop() -> None:
        while True:
            time.sleep(2)
            j = jread(jobs_dir() / jid / "job.json", {}) or {}
            if j.get("state") not in ("queued", "running"):
                if j:
                    JOBREG[jid].update(j)
                return
            if not job_alive(j):
                if RT.get(jid, {}).get("cancel") and RT[jid]["cancel"].is_set():
                    j["state"], j["ended"] = "cancelled", now()
                    j["note"] = "cancelled from the console"
                else:
                    j["state"], j["ended"] = "failed", now()
                    j["note"] = "process ended without a recorded result"
                save(j)
                JOBREG[jid].update(j)
                return
            JOBREG[jid].update(j)

    threading.Thread(target=loop, daemon=True).start()


def load_registry() -> None:
    jobs_dir().mkdir(parents=True, exist_ok=True)
    for d in jobs_dir().iterdir():
        j = jread(d / "job.json")
        if not j:
            continue
        if j["state"] in ("queued", "running"):
            if job_alive(j):
                RT[j["id"]] = {"cancel": threading.Event(), "proc": None}
                JOBREG[j["id"]] = j
                watch_foreign(j["id"])  # another server still owns it: do not fail it
                continue
            was = j["state"]
            j["state"] = "failed"
            j["ended"] = now()
            j["note"] = (
                f"server restarted while this job was {was}; "
                f"process may still be running (pid {j.get('pid')})"
            )
            (d / "job.json").write_text(json.dumps(j, ensure_ascii=False, indent=1))
        JOBREG[j["id"]] = j
        RT[j["id"]] = {"cancel": threading.Event(), "proc": None}


def parse_outputs(job: dict[str, Any]) -> None:
    """Pick facts out of the log: the work dir that ingest printed."""
    if job["kind"].startswith(("data.", "eval.")):
        data_outputs(job)
        return
    if job["kind"] != "ego.ingest":
        return
    txt = (jobs_dir() / job["id"] / "log.txt").read_text(errors="replace")
    m = re.findall(r"(/[^\s'\"]*?/pipeline/src_[0-9a-f]+)", txt)
    if m:
        job["outputs"]["work"] = m[-1]
        return
    m = re.findall(r"(pipeline/src_[0-9a-f]+)", txt)
    if m:
        job["outputs"]["work"] = str(_fw() / m[-1])


def data_outputs(job: dict[str, Any]) -> None:
    """Results of a data.* or eval.* job, read back from the files it wrote (only when ok)."""
    out = job["outputs"]
    kind = job["kind"]
    if kind == "data.ingest":
        ing = jread(Path(out["work"]) / "ingest.json", {}) or {}
        for k in ("source_id", "episodes", "frames", "files", "bytes", "index_findings"):
            if k in ing:
                out[k] = ing[k]
    elif kind == "data.qa":
        counts = _qa_counts(Path(out["work"]) / "qa" / "reports.jsonl")
        if counts:
            out["decisions"] = counts
    elif kind == "data.release":
        rel = jread(Path(out["release"]) / "release.json", {}) or {}
        if rel:
            out.update(release_id=rel.get("id"), release_name=rel.get("name"),
                       release_status=rel.get("status"), counts=rel.get("counts"),
                       combined_license=rel.get("combined_license"))  # fmt: skip
    elif kind == "data.report":
        rep = jread(Path(out["work"]) / "report" / "dataset_report.json", {}) or {}
        if rep:
            out["dataset_report"] = str(Path(out["work"]) / "report" / "dataset_report.json")
            out["episode_count"] = rep.get("episode_count")
    else:
        txt = tail_text(jobs_dir() / job["id"] / "log.txt", 20000)
        m = re.search(r"^chẩn đoán: (.+)$", txt, re.M)
        if m:
            out["verdict"] = m.group(1).strip()
        m = re.search(r"^phát hiện: (\d+); bỏ qua: (\d+)", txt, re.M)
        if m:
            out["findings"], out["skipped"] = int(m.group(1)), int(m.group(2))
        recs = sorted(Path(out["store"]).glob("**/*.jsonl"))
        if recs:
            out["record"] = str(recs[0])
    if kind.startswith("data."):
        out["ledger"] = str(store_dir() / "sites" / "local" / "runs")


def stage_dataset(job: dict[str, Any], rt: dict[str, Any], src: Path, dst: Path) -> int:
    """Copy a dataset into the console store (``<dst>.part-<job>`` then rename); 0 when done.

    Each job copies into its own temporary dir, and the swap into ``dst`` holds a lock, so two
    jobs staging the same dataset never write into one copy. Symlinks are not followed: a link
    may point outside the dataset (into ``vault/``, say), so it is skipped and logged."""
    dst = under(dst, store_dir() / "datasets")
    tmp = dst.with_name(f"{dst.name}.part-{job['id']}")
    shutil.rmtree(tmp, ignore_errors=True)
    t0 = time.time()
    n = tot = 0
    links: list[str] = []
    for dp, dns, fns in os.walk(src):
        links += [str(Path(dp, d).relative_to(src)) for d in dns if Path(dp, d).is_symlink()]
        dns[:] = sorted(d for d in dns if not Path(dp, d).is_symlink())
        rel = Path(dp).relative_to(src)
        (tmp / rel).mkdir(parents=True, exist_ok=True)
        for fn in sorted(fns):
            if rt["cancel"].is_set():
                shutil.rmtree(tmp, ignore_errors=True)
                return 1
            fp = Path(dp) / fn
            if fp.is_symlink():
                links.append(str(rel / fn))
                continue
            shutil.copyfile(fp, tmp / rel / fn)
            n += 1
            tot += fp.stat().st_size
    with _stage_lock:
        shutil.rmtree(dst, ignore_errors=True)
        os.replace(tmp, dst)
    if links:
        shown = ", ".join(links[:10])
        jlog(job, "[console] bỏ qua %d symlink (không chép): %s\n" % (len(links), shown))
    jlog(job, "[console] chép %d file (%.1f MB) vào store của console trong %.1f s: %s\n"
         % (n, tot / 1e6, time.time() - t0, _rel_fw(dst)))  # fmt: skip
    return 0


_stage_lock = threading.Lock()


def kill_group(proc: subprocess.Popen[Any]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        return

    def hard() -> None:
        time.sleep(6)
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass

    threading.Thread(target=hard, daemon=True).start()


def _run_steps(job: dict[str, Any], rt: dict[str, Any], pl: dict[str, Any]) -> str:
    kind = job["kind"]
    fw_root = pl.get("fw_root") or str(_fw())  # data.* / eval.*: the console's own store
    env = dict(os.environ, FW_ROOT=fw_root, PYTHONUNBUFFERED="1", NO_COLOR="1", TERM="dumb")
    if kind == "ego.human1m":
        ff = ffmpeg_path()
        if ff:
            env["FW_FFMPEG"] = ff
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
        env.pop(k, None)
    if pl.get("pre"):
        os.makedirs(pl["pre"], exist_ok=True)
    rc = 0
    steps = pl.get("steps") or [job["argv"]]
    with open(jobs_dir() / job["id"] / "log.txt", "ab") as lf:
        for si, argv in enumerate(steps):
            if pl.get("steps"):
                tail = " ".join(argv[-6:])
                lf.write(("[console] bước %d/%d: %s\n" % (si + 1, len(steps), tail)).encode())
                lf.flush()
            if argv[0] == "python:stage":
                rc = stage_dataset(job, rt, Path(argv[1]), Path(argv[2]))
                if rc != 0 or rt["cancel"].is_set():
                    break
                continue
            proc = subprocess.Popen(
                argv, cwd=job["cwd"], env=env, stdin=subprocess.DEVNULL, stdout=lf,
                stderr=subprocess.STDOUT, start_new_session=True,
            )  # fmt: skip
            rt["proc"] = proc
            job["pid"] = proc.pid
            save(job)
            killed = False
            while proc.poll() is None:
                if rt["cancel"].is_set() and not killed:
                    killed = True
                    kill_group(proc)
                time.sleep(0.3)
            rc = proc.returncode
            if rc != 0 or rt["cancel"].is_set():
                break
    parse_outputs(job)
    if rt["cancel"].is_set():
        finish(job, "cancelled", rc, "cancelled by user")
        return "cancelled"
    finish(job, "ok" if rc == 0 else "failed", rc)
    return str(job["state"])


def execute(job: dict[str, Any]) -> str:
    """Run one job to completion in the calling thread (queue, run, finish). Returns final state."""
    rt = RT[job["id"]]
    kind = job["kind"]
    pl = job.pop("_plan", None) or {}
    model = pl.get("model", False)
    if model:
        _model_lock.acquire()
    try:
        _slots.acquire()
        try:
            if rt["cancel"].is_set():
                finish(job, "cancelled", note="cancelled while queued")
                return "cancelled"
            job["state"] = "running"
            job["started"] = now()
            job["_t0"] = time.time()
            save(job)
            if pl.get("tunnel"):
                jlog(job, "[console] mở tunnel ssh tới rtx3060 (Ollama)…\n")
                if not TUNNEL.ensure():
                    jlog(job, "[console] tunnel không lên: %s\n" % (TUNNEL.err or "hết thời gian"))
                    finish(job, "failed", 1, "tunnel to rtx3060 is down")
                    return "failed"
                jlog(
                    job,
                    "[console] tunnel up, models: {}\n".format(", ".join(TUNNEL.tags(True) or [])),
                )
            if kind in GATED and not deid_done(job["params"].get("work") or ""):
                jlog(job, "[console] TỪ CHỐI: chưa che mặt xong; bước này chỉ đọc bản đã che.\n")
                finish(job, "failed", 2, "de-identification not complete")
                return "failed"
            if pl.get("python"):
                return run_python(job, rt)
            return _run_steps(job, rt, pl)
        finally:
            _slots.release()
    except Exception as e:
        jlog(job, f"[console] lỗi runner: {e!r}\n")
        finish(job, "failed", None, f"runner error: {e!r}")
        return "failed"
    finally:
        if model:
            _model_lock.release()


# ------------------------------------------------------------------ export.zip
ZIP_EXT = {".json", ".jsonl", ".md", ".html", ".yaml", ".yml", ".csv", ".txt", ".log"}
ZIP_SKIP_DIRS = {
    "videos",
    "data",
    "vm-logs",
    "psi0",
    ".git",
    "__pycache__",
    "viewer",
    "viewer-sample",
}


def _skip_dir(name: str) -> bool:
    """Directories an export never enters: the vault, holdouts, hidden dirs, the console's own."""
    return _hidden(name) or name == "console" or name in ZIP_SKIP_DIRS


def run_python(job: dict[str, Any], rt: dict[str, Any]) -> str:
    d = Path(job["outputs"]["dir"])  # the path plan() resolved and checked, never the raw param
    exports_dir().mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", d.name)[:60]
    name = "{}-{}.zip".format(stem, datetime.now().strftime("%Y%m%d-%H%M%S"))
    out = exports_dir() / name
    n = tot = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dns, fns in os.walk(d):
            dns[:] = [x for x in dns if not _skip_dir(x)]
            for fn in sorted(fns):
                fp = Path(dp) / fn
                if fp.suffix.lower() not in ZIP_EXT or fp.is_symlink():
                    continue
                try:
                    sz = fp.stat().st_size
                except OSError:
                    continue
                if sz > 50 * 1024 * 1024:
                    jlog(job, f"bỏ qua (>50 MB): {fp.relative_to(d)}\n")
                    continue
                z.write(fp, str(Path(d.name) / fp.relative_to(d)))
                n += 1
                tot += sz
            if rt["cancel"].is_set():
                break
    if rt["cancel"].is_set():
        out.unlink(missing_ok=True)
        finish(job, "cancelled", None, "cancelled by user")
        return "cancelled"
    jlog(job, "zip %s: %d file, %.1f MB chưa nén -> %.1f MB\n" % (
        name, n, tot / 1e6, out.stat().st_size / 1e6))  # fmt: skip
    job["outputs"].update({"zip": str(out), "name": name, "files": n, "bytes": out.stat().st_size})
    finish(job, "ok", 0)
    return "ok"


def _iso_mtime(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def _rel_fw(p: Path) -> str:
    try:
        return str(p.relative_to(_fw()))
    except ValueError:
        return str(p)


def list_estimates() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for base in (_p().uploads, _fw() / "egocentric-ea"):
        if base.is_dir():
            for d in sorted(base.iterdir()):
                if d.is_dir() and next(d.glob("ep_*.npz"), None):
                    n = len(list(d.glob("ep_*.npz")))
                    out.append({"path": str(d), "label": "%s (%d npz)" % (_rel_fw(d), n)})
    return out


def list_exports() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    ex = exports_dir()
    if ex.is_dir():
        for f in sorted(ex.glob("*.zip"), key=lambda p: -p.stat().st_mtime):
            out.append(
                {"kind": "zip", "name": f.name, "size": f.stat().st_size,
                 "url": "/api/exports/" + f.name, "time": _iso_mtime(f)}
            )  # fmt: skip
    hd = _fw() / "human1m"
    if hd.is_dir():
        for d in sorted(hd.iterdir(), key=lambda p: -p.stat().st_mtime):
            if d.is_dir():
                out.append(
                    {"kind": "human1m", "name": d.name, "path": str(d), "size": None,
                     "time": _iso_mtime(d), "viewer": "/ego/" if _is_viewer_export(d) else None}
                )  # fmt: skip
    return out


def _is_viewer_export(d: Path) -> bool:
    """True when this export holds the viewer folder that the console mounts at ``/ego/``."""
    from flywheel.console.server.media import ego_viewer_dir

    v = ego_viewer_dir()
    return v is not None and v.parent == d


# ------------------------------------------------------------------ chains
CHAIN_STEPS = [
    "ego.ingest",
    "ego.deid",
    "ego.ea",
    "ego.pose",
    "ego.annotate",
    "ego.qa",
    "ego.report",
]


def plan_for_chain(kind: str, cp: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    if kind in GATED and kind != "ego.ea":
        # the gate is re-checked inside execute() once deid has run; plan without it here
        work = work_path(cp["work"])
        sub = kind.split(".")[1]
        argv = fw_cmd() + ["egocentric", sub, str(work)]
        pl: dict[str, Any] = {"outputs": {"work": str(work)}}
        if sub == "annotate":
            argv += ["--endpoint", TUNNEL_URL + "/v1"]
            pl.update(model=True, tunnel=True)
        if sub == "pose":
            argv += auto_estimates(work, None)
        pl["argv"] = argv
        return pl
    return plan(kind, cp, job["id"])


def run_chain(job: dict[str, Any], params: dict[str, Any]) -> None:
    rt = RT[job["id"]]
    job["state"] = "running"
    job["started"] = now()
    job["_t0"] = time.time()
    job["outputs"]["children"] = []
    save(job)
    work: Any = params.get("work")
    steps = list(CHAIN_STEPS)
    if not params.get("annotate"):
        steps.remove("ego.annotate")
    if work:
        steps.remove("ego.ingest")
    state = "ok"
    for kind in steps:
        if rt["cancel"].is_set():
            state = "cancelled"
            break
        if (
            kind == "ego.ea"
            and (jread(Path(work) / "source.json", {}) or {}).get("source_detail") != "ego_video"
        ):
            continue  # EgoDex keeps E-B
        try:
            cp = (
                {"work": work}
                if kind != "ego.ingest"
                else {"source": params.get("source") or "video", "root": params.get("root"),
                      "split": params.get("split") or "train"}
            )  # fmt: skip
            pl = plan_for_chain(kind, cp, job)
        except ValueError as e:
            jlog(job, f"[{now()}] {kind}: không chạy được: {e}\n")
            state = "failed"
            break
        child = make_job(kind, cp, chain_id=job["id"], pl=pl)
        child["_plan"] = pl
        job["outputs"]["children"].append(child["id"])
        job["outputs"]["current"] = child["id"]
        save(job)
        jlog(job, "[{}] {} -> {}\n".format(now(), KIND_LABEL[kind], child["id"]))
        RT[job["id"]]["child"] = child["id"]
        res = execute(child)
        jlog(job, "[{}] {}: {} (rc={})\n".format(now(), KIND_LABEL[kind], res, child.get("rc")))
        if res != "ok":
            state = res
            break
        if kind == "ego.pose":
            pt = [t for t in tiers(work) if t["id"] == "pose"][0]
            if pt["state"] != "done":
                jlog(job, "Pose mới {}: kiểm tra log bước E-A.\n".format(pt["note"]))
                state = "failed"
                job["note"] = "pose incomplete after E-A"
                break
        if kind == "ego.ingest":
            work = child["outputs"].get("work")
            job["outputs"]["work"] = work
            if not work:
                jlog(job, "không đọc được work dir từ log ingest\n")
                state = "failed"
                break
    if state == "ok":
        job["outputs"]["work"] = work
    finish(job, state, 0 if state == "ok" else 1)


def data_chain_steps(params: dict[str, Any]) -> list[str]:
    steps = list(DATA_CHAIN)
    if params.get("release") is False:
        steps.remove("data.release")
    return steps


def run_data_chain(job: dict[str, Any], params: dict[str, Any]) -> None:
    """data.ingest -> data.qa -> data.release -> data.report, each a child job.

    Each step is planned right before it runs, since it reads what the previous one wrote."""
    rt = RT[job["id"]]
    job["state"] = "running"
    job["started"] = now()
    job["_t0"] = time.time()
    job["outputs"]["children"] = []
    save(job)
    work: str | None = None
    state = "ok"
    for kind in data_chain_steps(params):
        if rt["cancel"].is_set():
            state = "cancelled"
            break
        if kind == "data.ingest":
            keys = ("dataset", "source_detail", "license", "data_class", "split")
            cp: dict[str, Any] = {k: params[k] for k in keys if k in params}
        else:
            cp = {"work": work}
        if kind == "data.release" and params.get("name"):
            cp["name"] = params["name"]
        cid = new_id()
        try:
            pl = plan(kind, cp, cid)
        except ValueError as e:
            jlog(job, f"[{now()}] {kind}: không chạy được: {e}\n")
            state = "failed"
            break
        child = make_job(kind, cp, chain_id=job["id"], pl=pl, job_id=cid)
        child["_plan"] = pl
        job["outputs"]["children"].append(cid)
        job["outputs"]["current"] = cid
        save(job)
        jlog(job, f"[{now()}] {KIND_LABEL[kind]} -> {cid}\n")
        rt["child"] = cid
        res = execute(child)
        jlog(job, "[{}] {}: {} (rc={})\n".format(now(), KIND_LABEL[kind], res, child.get("rc")))
        if res != "ok":
            state = res
            break
        if kind == "data.ingest":
            work = child["outputs"]["work"]
            job["outputs"].update(work=work, task=child.get("task"))
        for k in ("release", "page", "decisions", "source_id", "release_id"):
            if k in child["outputs"]:
                job["outputs"][k] = child["outputs"][k]
        save(job)
    finish(job, state, 0 if state == "ok" else 1)


def submit(kind: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create and start a job (or chain); returns the job dict. ``ValueError`` on bad input."""
    if kind not in KINDS:
        raise ValueError("unknown kind")
    if kind == "data.pipeline":
        params = dict(params or {})
        if "release" in params and not isinstance(params["release"], bool):
            raise ValueError("release phải là true hoặc false")
        first = plan("data.ingest", params, "x")  # validates the input before anything starts
        job = make_job(kind, params, pl={"argv": ["chain"], "task": first.get("task")})
        threading.Thread(target=run_data_chain, args=(job, params), daemon=True).start()
        return job
    if kind == "ego.pipeline":
        params = dict(params or {})
        if params.get("work"):
            params["work"] = str(work_path(params["work"]))
        else:
            first = {
                "source": params.get("source") or "video",
                "root": params.get("root"),
                "split": params.get("split") or "train",
            }
            plan("ego.ingest", first, "x")
        if params.get("annotate") and TUNNEL.state() != "up" and not TUNNEL.ensure():
            raise ValueError("bật gắn nhãn cần tunnel rtx3060 nhưng tunnel không lên")
        job = make_job(kind, params, pl={"argv": ["chain"]})
        threading.Thread(target=run_chain, args=(job, params), daemon=True).start()
        return job
    params = dict(params or {})
    jid = new_id()
    pl = plan(kind, params, jid)
    prepare(kind)
    job = make_job(kind, params, pl=pl, job_id=jid)
    job["_plan"] = pl
    threading.Thread(target=execute, args=(job,), daemon=True).start()
    return job


def pub(job: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in job.items() if not k.startswith("_")}


def list_jobs(limit: int = 100) -> list[dict[str, Any]]:
    with _lock:
        js = sorted(JOBREG.values(), key=lambda j: j["created"], reverse=True)
    return [pub(j) for j in js[:limit]]


def cancel(jid: str) -> dict[str, Any]:
    job = JOBREG.get(jid)
    if not job:
        raise NotFound(jid)
    rt = RT[jid]
    rt["cancel"].set()
    child = rt.get("child")
    if child and child in RT:
        RT[child]["cancel"].set()
    if rt.get("proc") is None and job["state"] in ("queued", "running"):
        _kill_foreign(job)  # left by an earlier server: no thread here watches the cancel flag
    if job["state"] == "queued":
        finish(job, "cancelled", note="cancelled while queued")
    return pub(job)


def _kill_foreign(job: dict[str, Any]) -> None:
    """SIGTERM the process groups of a job (and its chain children) this server did not start.

    Each step runs with ``start_new_session``, so its pid is its group id; ``watch_foreign`` then
    records the job as cancelled once the processes are gone."""
    pids = [job.get("pid")]
    if job.get("kind") in CHAIN_KINDS:
        for cid in (job.get("outputs") or {}).get("children", []):
            c = jread(jobs_dir() / cid / "job.json", {}) or {}
            if c.get("state") in ("queued", "running"):
                pids.append(c.get("pid"))
    for pid in pids:
        if pid is not None and pid_alive(pid):  # never killpg(0): that is this server's group
            try:
                os.killpg(int(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, ValueError):
                pass


def read_log(jid: str, offset: int) -> dict[str, Any]:
    f = jobs_dir() / jid / "log.txt"
    if jid not in JOBREG or not f.exists():
        raise NotFound(jid)
    with open(f, "rb") as fh:
        fh.seek(offset)
        b = fh.read(1 << 20)
    return {"text": b.decode("utf-8", "replace"), "offset": offset + len(b),
            "state": JOBREG[jid]["state"]}  # fmt: skip


# ------------------------------------------------------------------ artifacts for agent QA
def _train_dirs() -> list[tuple[str, str]]:
    """Return ``(task_id, train_dir)`` pairs from the task manifest, or tray fallback.

    A round that names a train folder per run (``tray-jig-r1``) has no ``train_dir``; its jobs
    are listed by the ``tray/jig-*`` glob of ``train_runs``, as before.
    """
    try:
        from flywheel.console.index import tasks as task_idx

        m = task_idx.load(_p())
        dirs = list(dict.fromkeys((r.task, d) for r in m.rounds if (d := r.train_dir)))
    except Exception:
        dirs = []
    return dirs or [("tray", "tray/pair60k")]


def list_artifacts() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    fwr = _fw()
    for d in sorted(fwr.glob("pipeline/*/report")):
        if d.is_dir():
            s = jread(d.parent / "source.json", {})
            label = "Báo cáo dữ liệu · %s (%s, %d tập)" % (
                d.parent.name, s.get("source_detail"), len(s.get("episodes") or []),
            )  # fmt: skip
            out.append({"label": label, "path": str(d), "kind": "dataset_report"})
    for _task, tdir in _train_dirs():
        for d in sorted(fwr.glob(f"{tdir}/*/*")):
            if d.is_dir() and (d / "metrics.jsonl").is_file():
                out.append({"label": f"Log train · {d.name}", "path": str(d),
                            "kind": "train_job"})  # fmt: skip
    for f in sorted(fwr.glob("da34-dryrun/**/report/*.json"))[:20]:
        out.append({"label": f"Báo cáo · {f.relative_to(fwr)}", "path": str(f),
                    "kind": "report_json"})  # fmt: skip
    return out


def agent_stats() -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    with _lock:
        jobs = list(JOBREG.values())
    for j in jobs:
        if j["kind"] != "agentqa.run" or j["state"] != "ok" or not j["outputs"].get("out"):
            continue
        n_f, model = 0, ""
        rf = Path(j["outputs"]["out"]) / "reports.jsonl"
        if rf.is_file():
            with open(rf) as fh:
                for ln in fh:
                    try:
                        r = json.loads(ln)
                    except Exception:
                        continue
                    n_f += len(r.get("findings") or [])
                    model = (r.get("model") or {}).get("name") or model
        runs.append(
            {"id": j["id"], "time": j["ended"],
             "input": Path(j["outputs"].get("input", "")).name or "?", "findings": n_f,
             "model": model, "nemotron": "nemotron" in model.lower()}
        )  # fmt: skip
    runs.sort(key=lambda r: r["time"], reverse=True)
    nem = [r for r in runs if r["nemotron"]]
    return {
        "runs": runs[:30], "nemotron_runs": len(nem), "findings": sum(r["findings"] for r in nem),
        "last_time": runs[0]["time"] if runs else None,
        "last_job": runs[0]["id"] if runs else None,
        "last_with_findings": next((r["id"] for r in runs if r["findings"]), None),
    }  # fmt: skip


def agent_results(out_dir: str) -> dict[str, Any]:
    """Reports produced by one agentqa.run: parse reports.jsonl and list html files."""
    d = under(out_dir, aqa_dir())
    reps: list[Any] = []
    rf = d / "reports.jsonl"
    if rf.is_file():
        with open(rf) as fh:
            for ln in fh:
                try:
                    reps.append(json.loads(ln))
                except Exception:
                    pass
    htmls = sorted(str(p) for p in d.glob("**/*.html"))
    revs: list[dict[str, Any]] = []
    rd = aqa_dir() / "reviews"
    if rd.is_dir():
        for p in rd.glob("**/*.json*"):
            try:
                revs.append({"file": p.name, "text": p.read_text()[:4000]})
            except Exception:
                pass
    return {"reports": reps, "reports_path": str(rf) if rf.is_file() else None, "html": htmls,
            "reviews": revs}  # fmt: skip


# ------------------------------------------------------------------ status
def max_steps(job_dir: Path) -> int | None:
    """``--train.max_training_steps`` from launch.json, result.json, or expected-100000.json."""
    launch = jread(job_dir / "launch.json", {}) or {}
    for a in launch.get("argv") or [] if isinstance(launch, dict) else []:
        m = re.match(r"^--train\.max_training_steps=(\d+)$", str(a))
        if m:
            return int(m.group(1))
    for fn, key in (("result.json", "checkpoint_step"), ("expected-100000.json", "ckpt_step")):
        res = jread(job_dir / fn, {}) or {}
        if isinstance(res, dict) and isinstance(res.get(key), int):
            return int(res[key])
    return None


def train_runs() -> list[dict[str, Any]]:
    """Training runs with a ``metrics.jsonl``; a run in ``withhold_runs`` is left out, and no
    run is listed when the manifest cannot say which those are."""
    try:
        hide = hidden_runs()
    except ManifestUnreadable:
        return []
    runs: list[dict[str, Any]] = []
    seen: set[Path] = set()
    candidates: list[tuple[str, str, Path]] = []
    for task_id, tdir in _train_dirs():
        for f in sorted(_fw().glob(f"{tdir}/*/*/metrics.jsonl")):
            if ".attempt" in f.parent.parent.name:
                continue
            candidates.append((task_id, f.parent.parent.name, f))
    for f in sorted(_fw().glob("tray/jig-*/*/metrics.jsonl")):
        parent_name = f.parent.parent.name
        if ".attempt" in parent_name:
            continue
        branch = parent_name.removeprefix("jig-").upper() or parent_name
        candidates.append(("tray", branch, f))
    for task_id, branch, f in candidates:
        if f in seen or hide.run(branch) or hide.mentions(f.parent.name):
            continue
        seen.add(f)
        try:
            ln = [x for x in tail_text(f, 6000).splitlines() if x.strip().startswith("{")]
            last = json.loads(ln[-1])
        except Exception:
            continue
        age = time.time() - f.stat().st_mtime
        exp_ckpt = (jread(f.parent / "expected-100000.json", {}) or {}).get("ckpt_step")
        step_val = exp_ckpt if isinstance(exp_ckpt, int) else last.get("step")
        is_running = (age < 1200) and not isinstance(exp_ckpt, int)
        runs.append(
            {"name": f.parent.name, "branch": branch, "task": task_id,
             "step": step_val, "max": max_steps(f.parent), "loss": last.get("loss"),
             "running": is_running, "age_min": round(age / 60, 1)}
        )  # fmt: skip
    return runs


def _hidden_endpoints(hide: hidden.Hidden) -> set[str]:
    """Colab VM endpoints of the sessions of hidden runs (``colab/*/<session>.json``)."""
    out: set[str] = set()
    if not hide:
        return out
    for f in _fw().glob("colab/*/*.json"):
        if hide.session(f.stem):
            ep = (jread(f, {}) or {}).get("endpoint") if f.is_file() else None
            if isinstance(ep, str) and ep:
                out.add(ep)
    return out


def colab_state() -> dict[str, Any]:
    """Balance and listed VMs of the newest guard log. A guard of a hidden run's session folder
    is skipped, and VMs of hidden runs' sessions are left out of ``sessions``. Empty when the
    manifest cannot say which sessions those are."""
    out: dict[str, Any] = {"balance": None, "sessions": [], "time": None}
    try:
        hide = hidden_runs()
    except ManifestUnreadable:
        return out
    best: Path | None = None
    for f in _fw().glob("colab/*/guard.jsonl"):
        if hide.session(f.parent.name):
            continue
        if best is None or f.stat().st_mtime > best.stat().st_mtime:
            best = f
    if best is None:
        return out
    for ln in reversed(tail_text(best, 12000).splitlines()):
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("event") == "poll":
            gone = _hidden_endpoints(hide)
            listed = [x for x in d.get("listed") or [] if not hide.session(x) and x not in gone]
            out.update(
                balance=d.get("balance"), sessions=listed, time=d.get("time"),
                rate=d.get("rate"), fresh=(time.time() - best.stat().st_mtime) < 900,
            )  # fmt: skip
            break
    return out


def _stage_jobs(stage: str) -> list[dict[str, Any]]:
    with _lock:
        js = sorted(JOBREG.values(), key=lambda j: j["created"], reverse=True)
    return [j for j in js if j["stage"] == stage and not j.get("chain_id")]


def last_line(job: dict[str, Any]) -> str:
    t = tail_text(jobs_dir() / job["id"] / "log.txt", 3000).replace("\r", "\n")
    ls = [x.strip() for x in t.splitlines() if x.strip()]
    return ls[-1][:200] if ls else ""


def fmt_k(x: Any) -> str:
    return "%.1fk" % (x / 1000.0) if isinstance(x, (int, float)) else "?"


def _new_stage(sid: str, label: str, link: str, tm: str) -> dict[str, Any]:
    return {"id": sid, "label": label, "state": "idle", "task": "tray", "now": "", "issue": None,
            "how": None, "jobs": [], "link": link, "updated": tm}  # fmt: skip


def _eval_loop_text() -> tuple[str, str]:
    """Eval and loop lines from the indexed pair60k reads; the best run's fraction comes first.

    Raises when the manifest or the shape of ``story.json`` does not let the held runs be
    filtered out."""
    hide = hidden_runs()
    held = _withheld_runs()  # a run whose test result is not presented stays out of the status
    try:
        doc = json.loads((_p().index / "story.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "", ""
    if not isinstance(doc, dict):
        return "", ""
    doc = withhold.story(hidden.story(doc, hide), held)  # also cleans an index built earlier
    pair = doc.get("pair") or {}
    runs = {r.get("run"): r for r in pair.get("runs") or []
            if isinstance(r, dict) and r.get("run") not in held}  # fmt: skip
    best = runs.get(pair.get("best"))
    if not best:
        return "", ""
    frac = "{}/{}".format
    ev = "Tốt nhất {} {}".format(best["run"], frac(best.get("successes"), best.get("n")))
    # the jig round's featured run (story.jig of index/jig.py): its results.json headline, only
    # when the eval is "ready"; nothing about a run that is hidden or not yet evaluated
    jig = doc.get("jig")
    jig_dict: dict[str, Any] = jig if isinstance(jig, dict) else {}
    feat = jig_dict.get("featured")
    jev = next(
        (e for e in jig_dict.get("evals") or []
         if isinstance(e, dict) and e.get("run") == feat and e.get("status") == "ready"),
        None,
    )  # fmt: skip
    jhead = jev.get("headline") if jev else None
    jig_ev_suffix = (
        " · Cảnh jig2: {} {}".format(feat, frac(jhead.get("successes"), jhead.get("n")))
        if isinstance(jhead, dict) and feat not in held
        else ""
    )
    rnd = next((r for name, r in runs.items() if re.search(r"_R\d+$", name or "")), None)
    if not rnd:
        sel = ((doc.get("round") or {}).get("chain") or {}).get("selected")
        if held and sel:  # the round ran; its retest is not presented, which is not "waiting"
            return (
                ev + jig_ev_suffix,
                f"Đã chọn {sel} tập nhắm lỗi · kết quả thi lại không trình bày",
            )
        return ev + jig_ev_suffix, ""
    ev += " · vòng {} {}".format(rnd["run"], frac(rnd.get("successes"), rnd.get("n")))
    ev += jig_ev_suffix
    outs = [
        c.get("outcome") for c in pair.get("comparisons") or [] if c.get("variant") == rnd["run"]
    ]
    chain = (doc.get("round") or {}).get("chain") or {}
    if not outs or not chain:
        return ev, ""
    stop = all(o == "F" for o in outs)
    lp = "Vòng {}: chọn {} tập → {} → {}".format(
        rnd["run"],
        chain.get("selected", "?"),
        frac(rnd.get("successes"), rnd.get("n")),
        "dừng (F)" if stop else "tiếp (" + ", ".join(sorted({str(o) for o in outs})) + ")",
    )
    return ev, lp


def status() -> dict[str, Any]:
    tm = now()
    stages = {
        "collect": _new_stage("collect", "Thu dữ liệu", "#/data/nhap", tm),
        "process": _new_stage("process", "Xử lý", "#/jobs?view=pipeline", tm),
        "release": _new_stage("release", "Phát hành", "#/data/xuat", tm),
        "train": _new_stage("train", "Huấn luyện", "#/training", tm),
        "eval": _new_stage("eval", "Đánh giá", "#/eval", tm),
        "loop": _new_stage("loop", "Vòng lặp", "#/loop", tm),
    }
    idle_text = {
        "collect": "Chưa có việc nhập mới",
        "process": "Chưa có việc xử lý đang chạy",
        "release": "Chưa có lần xuất mới",
    }
    for sid in ("collect", "process", "release"):
        s = stages[sid]
        js = _stage_jobs(sid)
        running = [j for j in js if j["state"] in ("running", "queued")]
        if running:
            j = running[0]
            s.update(
                state="running",
                now="Đang chạy: {}".format(KIND_LABEL.get(j["kind"], j["kind"])),
                jobs=[x["id"] for x in running],
                updated=j.get("started") or j["created"],
            )
            cur = RT.get(j["id"], {}).get("child") if j["kind"] in CHAIN_KINDS else None
            if cur and cur in JOBREG:
                s["now"] = "Pipeline: {}".format(KIND_LABEL.get(JOBREG[cur]["kind"], ""))
                if JOBREG[cur].get("stage") != sid:
                    s["now"] += " (bước của stage xử lý)"
            continue
        last = js[0] if js else None
        if last and last["state"] == "failed":
            s.update(
                state="blocked",
                now="Việc cuối bị lỗi: {}".format(KIND_LABEL.get(last["kind"], last["kind"])),
                issue=(last.get("note") or last_line(last) or "lỗi không rõ"),
                how="Mở log trong ngăn Việc, sửa nguyên nhân rồi chạy lại",
                jobs=[last["id"]], updated=last.get("ended") or last["created"],
            )  # fmt: skip
        elif last and last["state"] == "ok":
            s.update(
                state="done",
                now="Xong: {}".format(KIND_LABEL.get(last["kind"], last["kind"])),
                jobs=[last["id"]],
                updated=last.get("ended") or last["created"],
            )
        else:
            s["now"] = idle_text[sid]
    # chain children that belong to other stages: show the parent's running state in process
    with _lock:
        all_jobs = list(JOBREG.values())
    for j in all_jobs:
        if j["kind"] in CHAIN_KINDS and j["state"] == "running":
            s = stages["process"]
            s["state"] = "running"
            cur = RT.get(j["id"], {}).get("child")
            kl = KIND_LABEL.get(JOBREG[cur]["kind"], "") if cur in JOBREG else "đang khởi động"
            name = "egocentric" if j["kind"] == "ego.pipeline" else "robot"
            s["now"] = f"Pipeline {name}: {kl}"
            s["jobs"] = [j["id"]] + ([cur] if cur else [])
    runs = train_runs()
    s = stages["train"]
    if runs:
        run_now = [r for r in runs if r["running"]]
        txt = ", ".join(
            "{} {}/{}".format(r["branch"], fmt_k(r["step"]), fmt_k(r["max"]))
            for r in (run_now or runs)
        )
        s.update(state="running" if run_now else "done",
                 now=("Đang train: " if run_now else "Lần train gần nhất: ") + txt,
                 jobs=[r["name"] for r in runs], updated=tm)  # fmt: skip
    else:
        s.update(state="idle", now="Chưa thấy metrics.jsonl của lần train nào")
    s["runs"] = runs
    # eval and loop have no live source on the laptop: read the index, else show waiting
    refused: tuple[str, str] | None = None
    ev, lp = "", ""
    try:
        ev, lp = _eval_loop_text()
    except ManifestUnreadable:
        refused = ("Không đọc được seed/tasks.yaml nên không hiện kết quả",
                   "Sửa seed/tasks.yaml rồi tải lại trang")  # fmt: skip
    except Exception:  # story.json of an unexpected shape: show nothing rather than unfiltered
        refused = ("Không đọc được story.json nên không hiện kết quả",
                   "Chạy lại fw console index")  # fmt: skip
    if ev:
        stages["eval"].update(state="done", now=ev, static=True, how="Xem trang Eval")
    else:
        stages["eval"].update(state="waiting", now="Eval chạy ở Colab hoặc 3060", static=True,
                              how="Chờ checkpoint mới")  # fmt: skip
    if lp:
        stages["loop"].update(state="done", now=lp, static=True, how="Xem trang Vòng lặp")
    else:
        stages["loop"].update(state="waiting", now="Vòng lặp chờ kết quả eval", static=True,
                              how="Xem trang Vòng lặp")  # fmt: skip
    if refused:
        for sid in ("eval", "loop"):
            stages[sid].update(state="blocked", now=refused[0], issue=refused[0], how=refused[1],
                               static=True)  # fmt: skip
    jobs = list_jobs(10)
    mi = models_info()
    # an ego.pipeline parent holds no slot; only its child jobs do
    n_run = sum(1 for j in all_jobs if j["state"] == "running" and j["kind"] not in CHAIN_KINDS)
    keys = ("id", "kind", "stage", "state", "created", "started", "ended", "rc", "chain_id")
    return {
        "time": tm,
        "fw_root": str(_fw()),
        "stages": [stages[k] for k in ("collect", "process", "release", "train", "eval", "loop")],
        "jobs": [{k: j.get(k) for k in keys} for j in jobs],
        "machines": {
            "laptop": {"running_jobs": n_run, "slots": MAX_SLOTS},
            "rtx3060": {"tunnel": mi["tunnel"], "models": mi["models"],
                        "agent_ready": mi["agent_ready"]},
            "colab": colab_state(),
        },
    }  # fmt: skip


def init(paths: ConsolePaths | None = None) -> None:
    """Bind the runner to ``paths``, create its folders, reload the job registry."""
    global _P, _atexit_done
    _P = paths if paths is not None else active()
    for d in (jobs_dir(), exports_dir(), aqa_dir(), _p().config, _p().uploads):
        d.mkdir(parents=True, exist_ok=True)
    with _lock:
        JOBREG.clear()
        RT.clear()
    # port 11435 may already serve Ollama (another server's ssh): reuse it, spawn nothing
    TUNNEL.external = TUNNEL.tags(True) is not None
    load_registry()
    if not _atexit_done:
        _atexit_done = True
        atexit.register(TUNNEL.close)


# ------------------------------------------------------------------ folder picker + upload helpers
def _hidden(name: str) -> bool:
    return name.startswith(".") or name == "vault" or "holdout" in name.lower()


def _run_folder(name: str, hide: hidden.Hidden) -> bool:
    """``name`` is a job, outcome or session folder (or file) of a run in ``withhold_runs``.

    A manifest name also covers what starts with it and a separator, so a later job of the run is
    hidden too (``jig-n`` covers ``jig-n-60000-r3``, not ``jig-new``)."""
    return hide.session(name) or any(
        name == n or name.startswith((f"{n}-", f"{n}_", f"{n}.")) for n in hide.names
    )


def _browsable(p: Path, hide: hidden.Hidden) -> Path:
    """Refuse the folder of a hidden run, or a dot folder, anywhere on the way to ``p``.

    Dot folders are counted below ``fw_root`` when ``p`` is inside it (a git worktree keeps its
    data under ``.claude/``), else below the home folder. The message is the one of a folder that
    does not exist."""
    below = p
    for base in (_fw().resolve(), Path.home().resolve()):
        if p.is_relative_to(base):
            below = p.relative_to(base)
            break
    if any(_run_folder(x, hide) for x in p.parts) or any(x.startswith(".") for x in below.parts):
        raise ValueError("not a folder")
    return p


def fs_list(path: str) -> dict[str, Any]:
    home = Path.home()
    hide = hidden_runs()
    p = _browsable(under(path or str(home), home), hide)
    if not p.is_dir():
        raise ValueError("not a folder")
    dirs: list[dict[str, Any]] = []
    vids: list[dict[str, Any]] = []
    for e in sorted(p.iterdir(), key=lambda x: x.name.lower()):
        if _hidden(e.name) or _run_folder(e.name, hide):
            continue
        try:
            if e.is_dir():
                dirs.append({"name": e.name, "path": str(e)})
            elif e.suffix.lower() in VIDEO_EXT:
                vids.append({"name": e.name, "size": e.stat().st_size})
        except OSError:
            pass
    par = str(p.parent) if p != home.resolve() else None
    return {"path": str(p), "parent": par, "dirs": dirs[:500], "videos": vids[:500],
            "has_device": (p / "device.json").is_file()}  # fmt: skip


def dir_check(path: str) -> dict[str, Any]:
    hide = hidden_runs()
    p = _browsable(under_import(path), hide)
    return {
        "has_device": (p / "device.json").is_file(),
        "tasks": sorted(
            x.name
            for x in p.iterdir()
            if x.is_dir() and not _run_folder(x.name, hide) and any(x.glob("*.mp4"))
        ),
    }


def safe_name(n: str) -> str:
    n = os.path.basename(n or "")
    n = re.sub(r"[^A-Za-z0-9._ -]", "_", n).strip(" .")
    return n[:120] or "clip"


def ensure_device(d: Path, video_path: Path) -> None:
    """Write device.json for an upload batch from its first clip (assumed 90 deg HFOV)."""
    dj = d / "device.json"
    if dj.exists():
        return
    w, hh, fps = 0, 0, 30.0
    try:
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        hh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        cap.release()
    except Exception:
        pass
    if not w:
        w, hh = 1280, 720
    dj.write_text(
        json.dumps(
            {
                "device": "upload (intrinsic assumed: 90 deg HFOV, centred principal point)",
                "fps": round(fps, 3),
                "width": w,
                "height": hh,
                "intrinsic": [[w / 2, 0, w / 2], [0, w / 2, hh / 2], [0, 0, 1]],
                "tasks": {
                    "tray": "carry the tray with both hands from table A to table B "
                    "and place it on the target zone",
                    "two_table": "pick a box on one table, walk to the other table "
                    "and place it in the basket",
                },
                "objects": ["tray", "box"],
            },
            indent=1,
        )  # fmt: skip
    )
