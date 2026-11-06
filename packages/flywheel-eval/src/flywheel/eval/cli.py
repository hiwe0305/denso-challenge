"""The `fw eval` commands of the evaluation lane (DA-08 AC 5).

Each command is a thin shell over `api.py`: it parses options, prints what it
found and writes the record. The printed table is for the engineer reading the
output now, the artifact is for the loop reading it later, and both come from
the same run so they cannot disagree.

What is printed always has two parts. The findings are the faults, and the
skipped codes are what the job could not be judged on - a run that prints no
finding and no skip is a clean checkpoint, and that difference has to be
visible without opening the artifact.

Nothing that stops a command halfway leaves a traceback behind. A trace that
cannot be read, a config that is not there or is not YAML, a task that cannot
be loaded or whose predicates blow up, and a store that cannot be written all
exit 2 with one line saying what could not be done, because exit 1 with a
traceback reads like a crash in the tool rather than an answer about the job
(review of #58, point 5).

The reasons a skip carries are Vietnamese, and the team runs this on Windows,
where the console hands Python a cp1252 stream that cannot encode them. Every
command therefore puts its streams on UTF-8 first: without it the command dies
halfway through printing a diagnosis it already computed.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TextIO

import typer
from flywheel.contracts import TaskDefinition
from flywheel.contracts.training import TrainDiagnosis
from flywheel.eval.api import (
    DEFAULT_SYSTEM_CONFIG,
    DEFAULT_TRAIN_CONFIG,
    SCORER_CONFIG_DIR,
    diagnose_episode_system,
    diagnose_train,
    score_trace,
    store_score,
    store_system_diagnosis,
    store_train_diagnosis,
)
from flywheel.eval.config import ConfigError
from flywheel.eval.diagnosis.system.artifact import SystemDiagnosisRecord, SystemFindingRecord
from flywheel.eval.diagnosis.system.reader import (
    CAMERA_NAME,
    ROLLOUT_NAME,
    RTC_NAME,
    STEPS_NAME,
)
from flywheel.eval.diagnosis.system.reader import ReaderError as SystemReaderError
from flywheel.eval.diagnosis.train.reader import ReaderError
from flywheel.eval.scorer.reader import TraceError
from flywheel.eval.scorer.score import EpisodeScore
from flywheel.eval.scorer.status import ScorerError, StepStatus

app = typer.Typer()

HEADER = f"{'code':<5} {'start_step':>10} {'group/dim':<28} {'value':>12} {'threshold':>12} stop"
SYSTEM_HEADER = f"{'code':<5} {'value':>12} {'threshold':>12} {'where':<24} detail"

# The names of spec section 6.4, for the engineer reading the table. The record
# keeps the enum values, so it stays readable either way.
DIAGNOSIS_NAMES: dict[str, str] = {
    "clean": "không thấy lỗi hệ thống",
    "unknown": "CHƯA RÕ",
    "controller": "LỖI CONTROLLER",
    "runtime": "LỖI RUNTIME",
    "sync": "LỖI ĐỒNG BỘ",
    "calibration": "LỖI CALIBRATION",
    "infra": "LỖI HẠ TẦNG (không tính là lỗi policy)",
}

# The rollout's mode, which decides whether R1 and R2 count (DA-13 AC 7).
TIMING_NAMES: dict[str | None, str] = {
    "sync": "đồng bộ (R1, R2 ghi nhận, không quy lỗi)",
    "async": "bất đồng bộ (R1, R2 tính)",
    None: "không rõ chế độ (R1, R2 tính)",
}

# The Vietnamese names of spec section 5.1, for the engineer reading the table.
# The artifact keeps the enum values, so it stays readable either way.
STATUS_NAMES: dict[StepStatus, str] = {
    "pass": "đạt",
    "fail": "trượt",
    "not_attempted": "chưa thử",
    "unknown": "chưa rõ",
}


@app.callback()
def root() -> None:
    """Evaluation lane commands."""


@app.command("diag-train")
def diag_train(
    job: Path = typer.Option(
        ...,
        "--job",
        help="Job directory holding metrics.jsonl and the probe results, or the log itself.",
    ),
    config: Path = typer.Option(
        DEFAULT_TRAIN_CONFIG,
        "--config",
        help="Threshold file; its hash is recorded with the diagnosis.",
    ),
    store: Path | None = typer.Option(
        None,
        "--store",
        help="Store directory to append the diagnosis to. Nothing is written without it.",
    ),
) -> None:
    """Diagnose a train job for the F-TRAIN (T1-T8) and F-OFF (O1-O4) faults."""
    use_utf8()
    try:
        diagnosis = diagnose_train(job, config)
    except (ReaderError, ConfigError) as error:
        # A file that cannot be read is not a clean checkpoint, so it must not
        # leave an artifact behind or exit as though the job were judged.
        typer.echo(f"không chẩn được: {error}", err=True)
        raise typer.Exit(code=2) from error
    _print(diagnosis)
    if store is not None:
        typer.echo(f"ghi vào: {store_train_diagnosis(diagnosis, store)}")


@app.command("diag-system")
def diag_system(
    episode: Path = typer.Option(
        ...,
        "--episode",
        help=f"Thư mục trace <trace_id>/ ({STEPS_NAME}, {CAMERA_NAME}, {ROLLOUT_NAME}; "
        f"{RTC_NAME} của job ở thư mục cha), hoặc file {ROLLOUT_NAME} hay {STEPS_NAME} "
        "trong thư mục đó.",
    ),
    config: Path = typer.Option(
        DEFAULT_SYSTEM_CONFIG,
        "--config",
        help="File ngưỡng; hash của nó được ghi cùng kết quả.",
    ),
    store: Path | None = typer.Option(
        None, "--store", help="Thư mục store để ghi kết quả. Không có thì không ghi gì."
    ),
) -> None:
    """Kiểm hệ thống F-SYS (R1-R6) trên một episode đã ghi."""
    use_utf8()
    try:
        record = diagnose_episode_system(episode, config)
    except (SystemReaderError, ConfigError) as error:
        # A file that cannot be read is not a clean episode, so it must not
        # leave a record behind or exit as though the episode were judged.
        typer.echo(f"không kiểm được: {error}", err=True)
        raise typer.Exit(code=2) from error
    _print_system(record)
    if store is None:
        return
    try:
        written = store_system_diagnosis(record, store)
    except OSError as error:
        typer.echo(f"kiểm được nhưng không ghi được vào `{store}`: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(f"ghi vào: {written}")


@app.command("score")
def score(
    trace: Path = typer.Option(..., "--trace", help="Trace đã ghi của một episode (JSONL)."),
    task: str = typer.Option(
        ...,
        "--task",
        help="Định nghĩa task, dạng `module:Lớp`, ví dụ `flywheel_simple.tray.task:TrayTask`.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        help=f"File ngưỡng; mặc định `{SCORER_CONFIG_DIR}/<task_id>.yaml`.",
    ),
    episode_id: str | None = typer.Option(
        None, "--episode-id", help="Ghi đè id episode lấy từ trace."
    ),
    level: int | None = typer.Option(None, "--level", help="Mức điều kiện của episode."),
    store: Path | None = typer.Option(
        None, "--store", help="Thư mục store để ghi `Score`. Không có thì không ghi gì."
    ),
) -> None:
    """Chấm từng bước của một episode từ trace đã ghi."""
    use_utf8()
    try:
        definition = load_task(task)
        scored = score_trace(trace, definition, config or _config_for(definition), episode_id)
    except (TraceError, ConfigError, ScorerError) as error:
        # None of these is a verdict about the episode, so none may leave an
        # artifact behind or exit as though the episode had been scored.
        typer.echo(f"không chấm được: {error}", err=True)
        raise typer.Exit(code=2) from error
    _print_score(scored)
    if store is None:
        return
    try:
        written = store_score(scored, store, level)
    except OSError as error:
        # The episode was scored; what failed is the writing. Saying so and
        # exiting 2 is the difference between a record that is missing and a
        # record nobody knows is missing.
        typer.echo(f"chấm được nhưng không ghi được vào `{store}`: {error}", err=True)
        raise typer.Exit(code=2) from error
    typer.echo(f"ghi vào: {written}")


def load_task(reference: str) -> TaskDefinition:
    """Load a `TaskDefinition` named as `module:attribute` on the command line.

    The task is named by the engineer and imported at that moment, so the lane
    still imports no adapter of its own (03 section 7.3): scoring a tray
    episode does not make `flywheel.eval` depend on `flywheel_simple`. What
    comes back is checked against the protocol, because a class that is nearly
    a task definition would otherwise fail somewhere less obvious.
    """
    module_name, _, attribute = reference.partition(":")
    if not module_name or not attribute:
        raise ScorerError(f"`--task {reference}` phải có dạng `module:Lớp`")
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, attribute)
    except (ImportError, AttributeError) as error:
        raise ScorerError(f"không nạp được task `{reference}`: {error}") from error
    try:
        definition = factory() if isinstance(factory, type) else factory
    except Exception as error:  # the task is somebody else's code
        # A task that needs arguments cannot be named on a command line, and
        # that is a thing to say, not a traceback to print.
        raise ScorerError(
            f"không dựng được task `{reference}`: {type(error).__name__}: {error}"
        ) from error
    if not isinstance(definition, TaskDefinition):
        raise ScorerError(f"`{reference}` không phải `TaskDefinition` theo flywheel.contracts")
    return definition


def _config_for(task: TaskDefinition) -> Path:
    """The default config of a task, found from the repo rather than from `cwd`.

    `configs/` sits at the top of the repo, so resolving the default against
    the current directory meant the command only worked when it was run from
    there (review of #58, point 5). The walk stops at the repo root, so it
    cannot reach a `configs/` tree belonging to something else, and where
    nothing is found the repo-relative path is returned so the error names the
    file the engineer expected.
    """
    relative = SCORER_CONFIG_DIR / f"{task.task_id}.yaml"
    here = Path.cwd()
    for folder in (here, *here.parents):
        candidate = folder / relative
        if candidate.is_file():
            return candidate
        if (folder / ".git").exists():  # the repo root, in a clone or a worktree
            break
    return relative


def _print_system(record: SystemDiagnosisRecord) -> None:
    typer.echo(f"episode: {record.episode_id}")
    typer.echo(f"config_sha256: {record.config_sha256}")
    typer.echo(f"chẩn đoán: {DIAGNOSIS_NAMES.get(record.diagnosis, record.diagnosis)}")
    if record.infra_status is not None:
        typer.echo(f"infra_status: {record.infra_status}")
    typer.echo(f"rollout: {TIMING_NAMES[record.timing]}")
    typer.echo(SYSTEM_HEADER)
    for finding in record.findings:
        typer.echo(_system_row(finding))
    typer.echo(f"phát hiện: {len(record.findings)}; bỏ qua: {len(record.skipped)}")
    for skip in record.skipped:
        typer.echo(f"bỏ qua {skip.code}: {skip.reason}")
    if record.recorded or record.recorded_skipped:
        # Decision (a), 5/11/2026: shown, so the latency is not lost, but apart
        # from the table above, because it decides nothing.
        typer.echo(
            f"ghi nhận, không quy lỗi: {len(record.recorded)}; "
            f"bỏ qua (ghi nhận): {len(record.recorded_skipped)}"
        )
        for finding in record.recorded:
            typer.echo(_system_row(finding))
        for skip in record.recorded_skipped:
            typer.echo(f"bỏ qua {skip.code}: {skip.reason}")


def _system_row(finding: SystemFindingRecord) -> str:
    where = finding.where or ""
    if finding.part is not None:
        where = f"{finding.part} {where}".strip()
    threshold = "-" if finding.threshold is None else f"{finding.threshold:.6g}"
    return (
        f"{finding.code:<5} {finding.value:>12.6g} {threshold:>12} "
        f"{where:<24} {finding.detail or ''}"
    )


def _print_score(score: EpisodeScore) -> None:
    typer.echo(f"episode: {score.episode_id}; task: {score.task_id} {score.scorer_version}")
    typer.echo(f"config_sha256: {score.config_sha256}")
    for index, step in enumerate(score.steps):
        reason = f"  {step.detail or step.reason}" if step.reason else ""
        typer.echo(f"{index:>2} {step.name:<16} {STATUS_NAMES[step.status]:<10}{reason}")
    verdict = {True: "đạt", False: "trượt", None: "chưa rõ"}[score.success]
    typer.echo(f"thành công theo scorer: {verdict}")
    if score.failure.failure_kind is not None:
        failed = score.failure.first_failed_step
        where = "không rõ bước" if failed is None else f"bước {failed}"
        kind = score.failure.failure_kind
        klass = score.failure.failure_class or "-"
        typer.echo(f"kiểu lỗi: {kind} ({klass}); hỏng trước ở: {where}")
    if score.failure.reason is not None:
        typer.echo(f"lý do không gán được kiểu: {score.failure.reason}")
    if score.balance.violated:
        balance = score.balance
        # The row of the trace, not a step of the task: turning one into the
        # other needs per-step times, which no task reports yet (review of
        # #58, point 6).
        typer.echo(
            f"thăng bằng: vi phạm ở dòng trace {balance.row}, {balance.signal}="
            f"{balance.value} (giới hạn {balance.limit})"
        )
    elif score.balance.unknown_reason is not None:
        typer.echo(f"thăng bằng: chưa rõ, {score.balance.unknown_reason}")
    if score.missing_signals:
        typer.echo("thiếu tín hiệu: " + ", ".join(score.missing_signals))


def use_utf8(*streams: TextIO) -> None:
    """Put the output streams on UTF-8, so a Vietnamese reason cannot kill a run.

    A stream that cannot be reconfigured - a pipe a caller supplied, a captured
    buffer in a test - is left as it is: printing in the wrong encoding is a
    worse outcome than printing nothing only if the diagnosis itself is lost,
    and it is not.
    """
    for stream in streams or (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):  # a stream that is not a real console
            continue


def _print(diagnosis: TrainDiagnosis) -> None:
    typer.echo(f"checkpoint: {diagnosis.checkpoint_id}")
    typer.echo(f"config_sha256: {diagnosis.config_sha256}")
    typer.echo(HEADER)
    for finding in diagnosis.findings:
        where = finding.group if finding.group is not None else ""
        if finding.dim is not None:
            where = f"{where}[{finding.dim}]" if where else f"dim {finding.dim}"
        threshold = "-" if finding.threshold is None else f"{finding.threshold:.6g}"
        value = finding.value if isinstance(finding.value, str) else f"{finding.value:.6g}"
        typer.echo(
            f"{finding.code:<5} {finding.start_step:>10} {where:<28} "
            f"{value:>12} {threshold:>12} {'yes' if finding.stop_job else ''}"
        )
    typer.echo(f"phát hiện: {len(diagnosis.findings)}; bỏ qua: {len(diagnosis.skipped)}")
    for skip in diagnosis.skipped:
        typer.echo(f"bỏ qua {skip.code}: {skip.reason}")
