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
from flywheel.contracts.entities import Score
from flywheel.contracts.training import TrainDiagnosis
from flywheel.eval.config import (
    load_scorer_config,
    load_stage_table,
    load_system_thresholds,
    load_train_thresholds,
)
from flywheel.eval.diagnosis.stage.artifact import (
    StageAttributionRecord,
    build_stage_record,
    write_stage_record,
)
from flywheel.eval.diagnosis.stage.attribute import EVIDENCE_RULES, attribute_stage
from flywheel.eval.diagnosis.system.artifact import (
    SystemDiagnosisRecord,
    build_system_record,
    write_system_record,
)
from flywheel.eval.diagnosis.system.check import diagnose_system
from flywheel.eval.diagnosis.system.reader import StageInputs, load_episode
from flywheel.eval.diagnosis.train.artifact import (
    build_artifact,
    diagnose_all,
    load_job,
    write_artifact,
)
from flywheel.eval.scorer.artifact import build_record, write_record
from flywheel.eval.scorer.reader import read_trace
from flywheel.eval.scorer.score import EpisodeScore, score_episode

DEFAULT_TRAIN_CONFIG = Path("configs") / "eval" / "diagnosis" / "train.yaml"
DEFAULT_SYSTEM_CONFIG = Path("configs") / "eval" / "diagnosis" / "system.yaml"
DEFAULT_STAGE_TABLE = Path("configs") / "eval" / "diagnosis" / "stage.yaml"
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


def score_record(score: EpisodeScore, level: int | None = None) -> Score:
    """The record of a score without writing it, for callers that keep their own store."""
    return build_record(score, level)


def diagnose_episode_system(
    episode_path: Path, config_path: Path = DEFAULT_SYSTEM_CONFIG
) -> SystemDiagnosisRecord:
    """Check one recorded episode for the F-SYS faults R1-R6 and return the record.

    `episode_path` is the trace directory `<trace_id>/` of decision G1 on
    PR #48 - the steps, the camera parameters and the RolloutResult carrying
    `infra_status`, named by the constants of `diagnosis/system/reader.py` - or
    the RolloutResult or steps file inside it. The RTC log is the job's, in the
    directory above, kept to this trace's `trace_id`; a RolloutResult whose
    `trace_ref` (trace id, directory, sha256 of the steps) is not about these
    steps raises `ReaderError`. The record carries the hash of every one
    of those files, not only the trace's. `config_path` is the
    threshold file; its hash travels in the record, so a finding can always be
    traced back to the numbers it was judged against (DA-13 AC 2).

    A record whose `findings` and `skipped` are both empty is an episode where
    every code ran and none fired. One with a `skipped` entry is an episode
    nobody could clear, which is not the same as a clean one (AC 1).

    Raises `ReaderError` on a trace, RTC log or camera file that cannot be read
    and `ConfigError` on a threshold file that cannot be trusted. Neither is a
    verdict about the episode, so neither comes back as a clean diagnosis.
    """
    thresholds, digest = load_system_thresholds(config_path)
    inputs = load_episode(episode_path)
    verdict = diagnose_system(inputs, thresholds)
    return build_system_record(verdict, digest, inputs)


def attribute_failure_stage(
    inputs: StageInputs,
    episode_id: str,
    table_path: Path = DEFAULT_STAGE_TABLE,
) -> StageAttributionRecord:
    """Propose which stage of Ψ₀ one failure is blamed on, with the probe evidence.

    The probe results are passed in rather than looked up, because whichever
    lane ran the probes is the lane that knows which checkpoint they belong to
    (07 section 2.0, rule 3). Every hypothesis comes back unconfirmed: it is a
    proposal for the engineer on the evidence card, never an intervention
    (AC 4).

    This runs after the system check and the data check have cleared the
    failure, and before the feasibility check of spec section 6.5.
    """
    table, digest = load_stage_table(table_path, EVIDENCE_RULES)
    attribution = attribute_stage(inputs, table)
    return build_stage_record(attribution, episode_id, digest, inputs.failed_step)


def store_system_diagnosis(record: SystemDiagnosisRecord, store_path: Path) -> Path:
    """Append a system diagnosis to the store, returning the file it went into.

    Append-only: checking the same episode again adds a record beside the
    first, and `config_sha256` is what tells two runs apart.
    """
    return write_system_record(record, store_path)


def store_stage_attribution(record: StageAttributionRecord, store_path: Path) -> Path:
    """Append a stage attribution to the store, returning the file it went into."""
    return write_stage_record(record, store_path)


def store_train_diagnosis(diagnosis: TrainDiagnosis, store_path: Path) -> Path:
    """Append a diagnosis to the store, returning the file it was appended to.

    Append-only: an earlier diagnosis of the same checkpoint is never replaced
    or removed, only followed.
    """
    return write_artifact(diagnosis, store_path)
