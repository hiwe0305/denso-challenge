"""Records of the files the pipeline steps hand to each other (architecture section 24).

Private to the eval lane: written and read here, so they are not contracts. Only what
crosses a lane boundary (`RoundDiagnosis`, the eval outcome) goes to `flywheel.contracts`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

DataClass = Literal["public", "internal", "restricted"]
CLASS_ORDER: dict[str, int] = {"public": 0, "internal": 1, "restricted": 2}
SHA256 = r"^[0-9a-f]{64}$"


def highest(classes: list[DataClass]) -> DataClass:
    """The most restrictive class of `classes`; `restricted` when there is none."""
    return max(classes, key=CLASS_ORDER.__getitem__, default="restricted")


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PackEntry(Record):
    """One artifact file of a round: where it is, what it is, whose it is."""

    ref: str = Field(min_length=1, description="Path under the pack root, POSIX form.")
    kind: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA256)
    bytes: int = Field(ge=0)
    data_class: DataClass
    subject: dict[str, str] = Field(default_factory=dict)


class PackLink(Record):
    """A declared relation between two entries (eval run -> checkpoint -> train job ...)."""

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    relation: str = Field(min_length=1)


class Pack(Record):
    """`pack.json`: the frozen list of what one round gives the agent (step B0)."""

    pack_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    created_at: AwareDatetime
    declared_by: str = Field(min_length=1)
    entries: list[PackEntry] = Field(min_length=1)
    links: list[PackLink] = Field(default_factory=list)


class Rejected(Record):
    ref: str
    reason: str


class Admission(Record):
    """`admission.json`: what step B1 let through, and which models may see it."""

    pack_id: str
    pack_sha256: str = Field(pattern=SHA256)
    accepted: list[str]
    rejected: list[Rejected] = Field(default_factory=list)
    missing_kinds: list[str] = Field(default_factory=list)
    data_class: DataClass
    data_class_basis: list[str] = Field(
        default_factory=list,
        description="Entries whose own records carry a data class and all say public.")
    unconfirmed: list[str] = Field(
        default_factory=list,
        description="Accepted entries no source record vouches for, directly or by a link.")
    hosted_allowed: bool
