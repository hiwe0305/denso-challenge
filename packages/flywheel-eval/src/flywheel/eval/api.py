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

from flywheel.contracts import TaskDefinition
from flywheel.contracts.training import TrainDiagnosis
from flywheel.eval.config import load_scorer_config, load_train_thresholds
from flywheel.eval.diagnosis.train.artifact import (
    build_artifact,
    diagnose_all,
    load_job,
    write_artifact,
)
from flywheel.eval.scorer.artifact import ScoreRecord, build_record, write_record
from flywheel.eval.scorer.reader import read_trace
from flywheel.eval.scorer.score import EpisodeScore, score_episode

DEFAULT_TRAIN_CONFIG = Path("configs") / "eval" / "diagnosis" / "train.yaml"
SCORER_CONFIG_DIR = Path("configs") / "eval" / "scorer"


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


def score_trace(
    trace_path: Path,
    task: TaskDefinition,
    config_path: Path,
    episode_id: str | None = None,
) -> EpisodeScore:
    """Score one recorded episode against one task definition.

    `task` is passed in rather than looked up by name: the scorer holds no task
    registry, and whichever lane has the task definition - the two-table task
    at G1, the tray task of DA-32 - is the lane that knows which one to score
    with (07 section 2.0, rule 3).

    The hash of `config_path` travels in the result, so a step marked failed can
    always be traced back to the thresholds it was judged against (AC 5).

    Raises `TraceError` on a trace that cannot be read, `ConfigError` on a
    threshold file that cannot be trusted and `ScorerError` where the task and
    the config do not belong together. None of the three is a verdict about the
    episode, so none comes back as an episode that simply scored badly.
    """
    config, digest = load_scorer_config(config_path)
    trace = read_trace(trace_path, task, episode_id)
    return score_episode(trace, task, config, digest)


def store_score(score: EpisodeScore, store_path: Path, level: int | None = None) -> Path:
    """Append a score to the store, returning the file it was appended to.

    Append-only: scoring the same episode again adds a record beside the first
    one, and `scorer_version` with `config_sha256` is what tells them apart
    (03 section 4.4, rule 3).
    """
    return write_record(build_record(score, level), store_path)


def score_record(score: EpisodeScore, level: int | None = None) -> ScoreRecord:
    """The record of a score without writing it, for callers that keep their own store."""
    return build_record(score, level)


def store_train_diagnosis(diagnosis: TrainDiagnosis, store_path: Path) -> Path:
    """Append a diagnosis to the store, returning the file it was appended to.

    Append-only: an earlier diagnosis of the same checkpoint is never replaced
    or removed, only followed.
    """
    return write_artifact(diagnosis, store_path)
