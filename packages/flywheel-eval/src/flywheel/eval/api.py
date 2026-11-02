"""The public surface of the evaluation lane (07 section 2.0, rule 3).

Other lanes call these functions. They do not import the modules behind them:
`decide` of the Vòng lane and the Agent QA/QC of the egocentric lane read a
`TrainDiagnosis` record, which is a contract type, so the lane can rearrange
`diagnosis/` without breaking either caller.

Everything here is CPU-only and reads files that already exist. Nothing in this
module runs a model, a simulator or a train job.
"""

from __future__ import annotations

from pathlib import Path

from flywheel.contracts.training import TrainDiagnosis
from flywheel.eval.config import load_train_thresholds
from flywheel.eval.diagnosis.train.artifact import (
    build_artifact,
    diagnose_all,
    load_job,
    write_artifact,
)

DEFAULT_TRAIN_CONFIG = Path("configs") / "eval" / "diagnosis" / "train.yaml"


def diagnose_train(job_path: Path, config_path: Path = DEFAULT_TRAIN_CONFIG) -> TrainDiagnosis:
    """Diagnose one train job and return the record, without writing anything.

    `job_path` is the job directory, which holds `metrics.jsonl` and the probe
    results beside it, or the log itself. `config_path` is the threshold file;
    its hash travels in the record, so a finding can always be traced back to
    the numbers it was judged against (AC 3, 4).

    Raises `ReaderError` on a log or probe file that cannot be read and
    `ConfigError` on a threshold file that cannot be trusted. Neither is a
    verdict about the checkpoint, so neither comes back as an empty diagnosis.
    """
    thresholds, digest = load_train_thresholds(config_path)
    job = load_job(job_path)
    return build_artifact(job, diagnose_all(job, thresholds), digest)


def store_train_diagnosis(diagnosis: TrainDiagnosis, store_path: Path) -> Path:
    """Append a diagnosis to the store, returning the file it was appended to.

    Append-only: an earlier diagnosis of the same checkpoint is never replaced
    or removed, only followed.
    """
    return write_artifact(diagnosis, store_path)
