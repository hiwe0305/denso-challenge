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

What the frames do not say is not invented. psi-data has no condition seed
anywhere (S1-07), and EpisodeFrames carries none for the tray sources either,
so each episode gets its own `cond_unknown_...` condition; ingest runs under no
RunPlan, so `run_plan_id` names the ingest of that source.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast, get_args

from flywheel.contracts.artifacts import Episode, EpisodeMetadata
from flywheel.data.ingest.lerobot import EpisodeFrames, read_info

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
class SourceRecord:
    source_id: str  # src_<hash of detail, license, data_class and every file hash>
    root: str  # absolute path the dataset was registered from
    source_detail: str
    license: str
    data_class: DataClass
    files: dict[str, str]  # path relative to root (posix) -> sha256
    total_bytes: int
    data_path: str  # info.json template of the episode parquet
    chunks_size: int


def register_source(
    root: Path,
    source_detail: str,
    license: str,
    data_class: Literal["public", "internal", "restricted"],
) -> SourceRecord:
    """Hash every file of the LeRobot dataset at root and record where it came from."""
    _profile(source_detail)
    if data_class not in get_args(DataClass):
        raise ValueError(f"data_class {data_class!r} is not one of {get_args(DataClass)}")
    if not license.strip():
        raise ValueError("license must be named; write 'unknown' when it is not known")
    info = read_info(root)
    root = root.resolve()
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
        source_detail=source_detail,
        license=license,
        data_class=data_class,
        files=files,
        total_bytes=total,
        data_path=str(info["data_path"]),
        chunks_size=int(info["chunks_size"]),
    )


def to_episode(frames: EpisodeFrames, source: SourceRecord, split: str) -> Episode:
    """The contract Episode of one episode of a registered source."""
    profile = _profile(source.source_detail)
    index = frames.episode_index
    key = hashlib.sha256(f"{source.source_id}:{index}".encode()).hexdigest()[:16]
    parquet = Path(source.root) / source.data_path.format(
        episode_chunk=index // source.chunks_size, episode_index=index
    )
    return Episode(
        episode_id=f"ep_{key}",
        kind=profile.kind,
        operator_kind="human" if profile.human else "machine",
        is_root=profile.human,
        condition_id=f"cond_unknown_{key}",
        source_id=source.source_id,
        run_plan_id=f"rp_ingest_{source.source_id}",
        bundle_uri=parquet.as_uri(),
        license=source.license,
        data_class=source.data_class,
        split=split,
        source_kind=profile.source_kind,
        action_quality=profile.action_quality,
        deid_status="raw",  # robot sim video: no person in it to blur
        embodiment_id=profile.embodiment_id,
        meta=EpisodeMetadata(
            source_detail=cast(SourceDetail, source.source_detail),
            renderer=profile.renderer,
            synthetic_tier=profile.synthetic_tier,
        ),
    )


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
