"""Register a LeRobot dataset as a source and describe its episodes as contract Episodes.

This is tier 1 (ingest) of design 27/10 section 6 for the three robot sources
before the demo, all already in Psi0's LeRobot v2.1 layout (DA-03 AC 2):

    psi_data      the authors' two-table teleop   teleop     measured  -
    planner_wbc   tray S1 of DA-33                synthetic  planned   S1
    teleop_pico   tray S2 of DA-35                synthetic  planned   S2

`teleop_pico` is DA-35's virtual teleop and its S2 variants, which go through
SIMPLE's PICO teleop pipe; DA-35 records them as synthetic, never as teleop,
because no human drove them. Real PICO data, once the team has a headset, is
human teleop under the same `source_detail` and needs its own profile.

`SourceRecord` stays inside the lane (03 section 7.3): other lanes see only the
Episode, whose `source_id` points at it. The record holds the sha256 of every
file of the dataset as it was registered.

Lineage comes from the `flywheel` block the team's recorders put in each
episode's `environment_config` (DA-33 `FlywheelMeta`, DA-35 `flywheel_meta`):
condition seed, level, split, generator version, parent and root episode, and
the episode's own labels. `register_source` keeps it per episode in the
record. An Episode made by a machine needs a seed and a generator version, and
a variant needs its parent (03 invariant 10, 03 table T2); a label the episode
recorded that disagrees with the source profile is an error, not overwritten
(review #69 points 3, 8). The seed and the generator version stay in the
record: the Episode contract has no field for them yet.

What the data does not say is not invented. psi-data has no flywheel block and
no seed anywhere (S1-07), so each of its episodes gets its own
`cond_unknown_...` condition. Ingest runs under no RunPlan, so `run_plan_id`
names the ingest of that source.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast, get_args

from flywheel.contracts.artifacts import Episode, EpisodeMetadata
from flywheel.data.config import store_root
from flywheel.data.ingest.lerobot import (
    EpisodeFrames,
    IndexFinding,
    check_index,
    read_episode_rows,
    read_info,
)

DataClass = Literal["public", "internal", "restricted"]
SourceKind = Literal["teleop", "synthetic", "egocentric"]
ActionQuality = Literal["measured", "planned", "retargeted", "pseudo", "none"]
EpisodeKind = Literal["teleop_demo", "variant", "sim_rollout"]
SourceDetail = Literal["psi_data", "planner_wbc", "teleop_pico"]
Renderer = Literal["mujoco", "isaac"]
Tier = Literal["S1", "S2"]

# decoupled WBC of g1_sonic, which the authors' teleop, the tray planner (DA-33)
# and the PICO pipe (DA-35) all drive (design 27/10 section 6.1).
DWBC = "g1_sonic_dwbc@1"
CHUNK = 1 << 20
# Labels a recorder may write into the flywheel block; each must match the source.
LABELS = ("source_kind", "source_detail", "synthetic_tier", "action_quality",
          "embodiment_id", "renderer", "data_class")
GENERATOR_KEYS = ("generator_version", "planner_version", "wrapper_version")
# Splits an ingested episode may carry: configs/splits/default.yaml without holdout,
# which is sealed in vault/ and read only by gate (spec 7.3; a test keeps them equal).
SPLITS = ("train", "dev")
HOLDOUT = "holdout"


@dataclass(frozen=True)
class SourceProfile:
    source_kind: SourceKind
    action_quality: ActionQuality
    synthetic_tier: Tier | None
    kind: EpisodeKind
    human: bool
    embodiment_id: str
    renderer: Renderer | None  # None: not recorded with the data


PROFILES: dict[str, SourceProfile] = {
    "psi_data": SourceProfile("teleop", "measured", None, "teleop_demo", True, DWBC, None),
    "planner_wbc": SourceProfile(
        "synthetic", "planned", "S1", "sim_rollout", False, DWBC, "mujoco"
    ),
    "teleop_pico": SourceProfile("synthetic", "planned", "S2", "variant", False, DWBC, "mujoco"),
}


@dataclass(frozen=True)
class EpisodeLineage:
    """What an episode's `environment_config.flywheel` block says about where it came from."""

    seed: int | None = None  # condition seed of the scene
    level: int | None = None
    split: str | None = None
    task_uid: str | None = None  # environment_config uid
    parent_id: str | None = None
    root_id: str | None = None
    generator_version: str | None = None
    labels: tuple[tuple[str, str], ...] = ()  # recorded (label, value), see LABELS


@dataclass(frozen=True)
class SourceRecord:
    source_id: str  # src_<hash of detail, license, data_class and every file hash>
    root: str  # absolute path the dataset was registered from
    store_path: str  # the same dataset, relative to the store root (posix)
    source_detail: str
    license: str
    data_class: DataClass
    files: dict[str, str]  # path relative to root (posix) -> sha256
    total_bytes: int
    data_path: str  # info.json template of the episode parquet
    chunks_size: int
    lineage: dict[int, EpisodeLineage]  # episode_index -> lineage from its meta row
    # Episodes whose parquet `index` breaks LeRobot v2.1's numbering, as registered;
    # the ingest report shows them (psi-data e78fb93: 95 of 99, review #69 point 1).
    index_findings: tuple[IndexFinding, ...] = ()


def register_source(
    root: Path,
    source_detail: str,
    license: str,
    data_class: Literal["public", "internal", "restricted"],
    *,
    store: Path | None = None,
) -> SourceRecord:
    """Hash every file of the LeRobot dataset at root and record where it came from.

    The dataset must sit under the store root (`store`, else $FW_ROOT, else
    ./fwdata): Episodes point at it relative to that root, so a store copied to
    another machine keeps working (Q6, decided by the PO 3/11/2026).
    """
    _profile(source_detail)
    if data_class not in get_args(DataClass):
        raise ValueError(f"data_class {data_class!r} is not one of {get_args(DataClass)}")
    if not license.strip():
        raise ValueError("license must be named; write 'unknown' when it is not known")
    info = read_info(root)
    root = root.resolve()
    base = (store or store_root()).resolve()
    if not root.is_relative_to(base):
        raise ValueError(
            f"{root} is not under the store root {base}; set FW_ROOT or pass store="
        )
    files: dict[str, str] = {}
    total = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        files[path.relative_to(root).as_posix()] = _sha256(path)
        total += path.stat().st_size
    identity = hashlib.sha256(f"{source_detail}\n{license}\n{data_class}\n".encode())
    for name, digest in files.items():
        identity.update(f"{digest}  {name}\n".encode())
    return SourceRecord(
        source_id=f"src_{identity.hexdigest()[:16]}",
        root=str(root),
        store_path=root.relative_to(base).as_posix(),
        source_detail=source_detail,
        license=license,
        data_class=data_class,
        files=files,
        total_bytes=total,
        data_path=str(info["data_path"]),
        chunks_size=int(info["chunks_size"]),
        lineage={int(r["episode_index"]): _lineage(r) for r in read_episode_rows(root)},
        index_findings=tuple(check_index(root)),
    )


def to_episode(frames: EpisodeFrames, source: SourceRecord, split: str) -> Episode:
    """The contract Episode of one episode of a registered source."""
    profile = _profile(source.source_detail)
    index = frames.episode_index
    if index not in source.lineage:
        raise ValueError(f"episode {index} is not in source {source.source_id}")
    lineage = source.lineage[index]
    renderer = _check_labels(index, lineage, profile, source)
    _check_split(index, lineage, split)
    key = hashlib.sha256(f"{source.source_id}:{index}".encode()).hexdigest()[:16]
    if not profile.human:
        needed = {"seed": lineage.seed, "generator version": lineage.generator_version}
        missing = [name for name, value in needed.items() if value is None]
        if missing:
            raise ValueError(
                f"episode {index} of {source.source_id} is machine-made but its flywheel"
                f" block has no {' and no '.join(missing)} (03 invariant 10)"
            )
    if profile.kind == "variant" and lineage.parent_id is None:
        raise ValueError(
            f"episode {index} of {source.source_id} is a variant without parent_episode"
        )
    parquet = PurePosixPath(source.store_path) / source.data_path.format(
        episode_chunk=index // source.chunks_size, episode_index=index
    )
    return Episode(
        episode_id=f"ep_{key}",
        kind=profile.kind,
        operator_kind="human" if profile.human else "machine",
        is_root=profile.human,
        root_id=lineage.root_id,
        parent_id=lineage.parent_id,
        condition_id=_condition_id(lineage, key),
        source_id=source.source_id,
        run_plan_id=f"rp_ingest_{source.source_id}",
        bundle_uri=parquet.as_posix(),  # relative to the store root (Q6)
        license=source.license,
        data_class=source.data_class,
        split=split,
        source_kind=profile.source_kind,
        action_quality=profile.action_quality,
        deid_status="raw",  # robot sim video: no person in it to blur
        embodiment_id=profile.embodiment_id,
        meta=EpisodeMetadata(
            source_detail=cast(SourceDetail, source.source_detail),
            renderer=renderer,
            synthetic_tier=profile.synthetic_tier,
        ),
    )


def _lineage(row: dict[str, Any]) -> EpisodeLineage:
    config = row.get("environment_config") or {}
    if isinstance(config, str):
        config = json.loads(config)
    block = config.get("flywheel") or {}
    index = row["episode_index"]

    def episode_ref(*keys: str) -> str | None:
        value = next((block[k] for k in keys if block.get(k) is not None), None)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"episode {index}: {keys[0]} {value!r} is not an episode id")
        return value

    def number(key: str) -> int | None:
        return None if block.get(key) is None else int(block[key])

    version = next((str(block[k]) for k in GENERATOR_KEYS if block.get(k)), None)
    return EpisodeLineage(
        seed=number("seed"),
        level=number("level"),
        split=None if block.get("split") is None else str(block["split"]),
        task_uid=None if config.get("uid") is None else str(config["uid"]),
        parent_id=episode_ref("parent_episode", "parent_id"),
        root_id=episode_ref("root_episode", "root_id"),
        generator_version=version,
        labels=tuple((k, str(block[k])) for k in LABELS if block.get(k) is not None),
    )


def _check_labels(
    index: int, lineage: EpisodeLineage, profile: SourceProfile, source: SourceRecord
) -> Renderer | None:
    """The renderer of the episode, after checking its recorded labels against the source."""
    expected = {
        "source_kind": profile.source_kind,
        "source_detail": source.source_detail,
        "synthetic_tier": profile.synthetic_tier,
        "action_quality": profile.action_quality,
        "embodiment_id": profile.embodiment_id,
        "renderer": profile.renderer,
        "data_class": source.data_class,
    }
    recorded = dict(lineage.labels)
    for label, value in recorded.items():
        if expected[label] is not None and value != expected[label]:
            raise ValueError(
                f"episode {index} of {source.source_id} recorded {label}={value!r}, but"
                f" source {source.source_detail!r} gives {expected[label]!r}"
            )
    renderer = recorded.get("renderer", profile.renderer)
    if renderer is not None and renderer not in get_args(Renderer):
        raise ValueError(f"episode {index}: renderer {renderer!r} is not mujoco or isaac")
    return cast("Renderer | None", renderer)


def _check_split(index: int, lineage: EpisodeLineage, split: str) -> None:
    if split == HOLDOUT:
        raise ValueError(
            "split 'holdout' is never ingested: holdout lives only in vault/ and only gate"
            " reads it (fw holdout run)"
        )
    if split not in SPLITS:
        raise ValueError(f"split {split!r} is not one of {', '.join(SPLITS)}")
    if lineage.split is not None and lineage.split != split:
        raise ValueError(f"episode {index} was recorded in split {lineage.split!r}, not {split!r}")


def _condition_id(lineage: EpisodeLineage, key: str) -> str:
    if lineage.seed is None:
        return f"cond_unknown_{key}"
    scene = f"{lineage.task_uid}|{lineage.level}|{lineage.seed}"
    return f"cond_{hashlib.sha256(scene.encode()).hexdigest()[:16]}"


def _profile(source_detail: str) -> SourceProfile:
    if source_detail not in PROFILES:
        raise ValueError(
            f"source_detail {source_detail!r} has no ingest profile; one of {', '.join(PROFILES)}"
        )
    return PROFILES[source_detail]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()
