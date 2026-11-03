"""The record one stage attribution leaves behind (DA-13 AC 3, 4).

03 section 4.3 keeps this in `meta` of `Cluster`, which `decide` of the Vòng
lane owns and writes. Nothing in `flywheel.contracts` carries it yet, so the
record below is the lane's own, written field for field as the contract change
asks for it - the way DA-36 held `ScoreRecord` until `Score` landed. The switch
is registered as a task of the story.

The record is answered per failure, not per episode: the table asks about the
step that broke and the action groups behind it, so one episode with two
failures has two of these while it has one system diagnosis.

Two things it has to keep. `unavailable` travels with `hypotheses`, so a record
with both lists empty means every row was judged and none applied, rather than
a failure nobody had probes for (FR21). And `confirmed` is written as False
with nothing in this lane setting it, because the hypothesis is a proposal the
engineer confirms on the evidence card (AC 4).
"""

from __future__ import annotations

from pathlib import Path

from flywheel.eval.diagnosis.stage.attribute import StageAttribution
from flywheel.eval.diagnosis.system.artifact import SystemSkipRecord, append_line
from pydantic import BaseModel, ConfigDict, Field

STAGE_RECORDS = Path("diagnosis") / "stage.jsonl"


class EvidenceRecord(BaseModel):
    """One probe measurement behind a hypothesis (AC 3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    probe: str
    where: str
    value: float
    threshold: float | None = None


class StageHypothesisRecord(BaseModel):
    """One row of the attribution table that applied, as a proposal (AC 3, 4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    row_id: str
    attribute_to: str
    intervention: str
    consumes_budget: bool
    confirmed: bool = False
    evidence: list[EvidenceRecord] = Field(default_factory=list)


class StageAttributionRecord(BaseModel):
    """The stage hypotheses of one failure, and the rows left unjudged (AC 3, 4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    episode_id: str
    table_sha256: str
    failed_step: int | None = None
    hypotheses: list[StageHypothesisRecord] = Field(default_factory=list)
    unavailable: list[SystemSkipRecord] = Field(default_factory=list)


def build_stage_record(
    attribution: StageAttribution,
    episode_id: str,
    table_sha256: str,
    failed_step: int | None = None,
) -> StageAttributionRecord:
    """The record of one stage attribution; every hypothesis unconfirmed (AC 4)."""
    return StageAttributionRecord(
        episode_id=episode_id,
        table_sha256=table_sha256,
        failed_step=failed_step,
        hypotheses=[
            StageHypothesisRecord(
                row_id=hypothesis.row_id,
                attribute_to=hypothesis.attribute_to,
                intervention=hypothesis.intervention,
                consumes_budget=hypothesis.consumes_budget,
                confirmed=False,
                evidence=[
                    EvidenceRecord(
                        probe=item.probe,
                        where=item.where,
                        value=item.value,
                        threshold=item.threshold,
                    )
                    for item in hypothesis.evidence
                ],
            )
            for hypothesis in attribution.hypotheses
        ],
        unavailable=[
            SystemSkipRecord(code=item.row_id, reason=item.reason)
            for item in attribution.unavailable
        ],
    )


def write_stage_record(record: StageAttributionRecord, store_path: Path) -> Path:
    """Append a stage attribution to the store; return the file it went into.

    Append-only: attributing the same failure again adds a record beside the
    first, and `table_sha256` is what tells two runs under two tables apart
    (03 section 4.4, rule 3).
    """
    return append_line(record.model_dump_json(), store_path / STAGE_RECORDS)
