"""The `fw eval` commands of the evaluation lane (DA-08 AC 5).

Each command is a thin shell over `api.py`: it parses options, prints what it
found and writes the record. The printed table is for the engineer reading the
output now, the artifact is for the loop reading it later, and both come from
the same run so they cannot disagree.

What is printed always has two parts. The findings are the faults, and the
skipped codes are what the job could not be judged on - a run that prints no
finding and no skip is a clean checkpoint, and that difference has to be
visible without opening the artifact.

The reasons a skip carries are Vietnamese, and the team runs this on Windows,
where the console hands Python a cp1252 stream that cannot encode them. Every
command therefore puts its streams on UTF-8 first: without it the command dies
halfway through printing a diagnosis it already computed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO

import typer
from flywheel.contracts.training import TrainDiagnosis
from flywheel.eval.api import DEFAULT_TRAIN_CONFIG, diagnose_train, store_train_diagnosis
from flywheel.eval.config import ConfigError
from flywheel.eval.diagnosis.train.reader import ReaderError

app = typer.Typer()

HEADER = f"{'code':<5} {'start_step':>10} {'group/dim':<28} {'value':>12} {'threshold':>12} stop"


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
