"""Files in and out of the scorer check (DA-37 AC 2): the half that touches disk.

`agreement.py` judges; this module reads what it judges and stores what it
said. Reading is strict, for the same reason as everywhere else in the lane: a
`Score` or a `RolloutResult` that does not parse is not an episode that
disagreed, it is an episode nobody can speak for, so it stops the run with the
file and line named instead of shrinking the set the rate is computed on.

The report is stored through `flywheel.store` (PO, 3/11/2026): its bytes go in
the content-addressed blob store, so the report *is* its hash, and one line
naming that hash is appended to `<store>/scorer/agreement.jsonl` so the reports
can be listed. Append-only: checking again appends a second line and, if the
episodes and the scorer are the same, points at the same blob; nothing that was
stored is rewritten (03 section 4.4, rule 3).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import TypeVar

from flywheel.contracts import RolloutResult
from flywheel.contracts.entities import Score
from flywheel.eval.scorer.agreement import AgreementReport
from flywheel.store.blobs import put_blob
from flywheel.store.paths import StorePaths
from pydantic import ValidationError

AGREEMENT_RECORDS = Path("scorer") / "agreement.jsonl"

_M = TypeVar("_M", Score, RolloutResult)


class CalibrationInputError(ValueError):
    """A `Score` or `RolloutResult` file the check must not run on."""


def read_scores(path: Path) -> list[Score]:
    """Every `Score` in a JSONL file, such as `<store>/scorer/score.jsonl`."""
    return [_parse(Score, line, f"{path}:{number}") for number, line in _lines(path)]


def read_rollouts(path: Path, name: str) -> list[RolloutResult]:
    """Every `RolloutResult` named `name` under a directory, or the one file given."""
    files = [path] if path.is_file() else sorted(path.rglob(name))
    if not files:
        raise CalibrationInputError(f"không có file `{name}` nào dưới `{path}`")
    return [_parse(RolloutResult, _text(file), str(file)) for file in files]


def store_report(report: AgreementReport, store_path: Path) -> tuple[str, Path]:
    """Put the report in the blob store and list it; return its hash and the list."""
    digest = put_blob(report.canonical(), StorePaths(store_path))
    line = {
        "report_sha256": digest,
        "task_id": report.task_id,
        "scorer_version": report.scorer_version,
        "config_sha256": report.config_sha256,
        "release_id": report.release_id,
        "counted": report.counted,
        "agreed": report.agreed,
        "agreement": report.agreement,
        "passed": report.passed,
        "unjudged": report.unjudged,
        "mismatches": len(report.mismatches),
    }
    index = store_path / AGREEMENT_RECORDS
    index.parent.mkdir(parents=True, exist_ok=True)
    with index.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line, sort_keys=True) + "\n")
    return digest, index


def _lines(path: Path) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(_text(path).splitlines(), start=1):
        if line.strip():
            yield number, line


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise CalibrationInputError(f"`{path}` không đọc được: {error}") from error


def _parse(model: type[_M], text: str, where: str) -> _M:
    try:
        return model.model_validate_json(text)
    except ValidationError as error:
        raise CalibrationInputError(
            f"{where} không hợp schema {model.__name__}: {error}"
        ) from error
