"""Tier 1 for egocentric video: pick the episodes of a source and hash them (AC 1, AC 6).

Two readers feed the same pipeline (03 section 5.4, "Nguồn egocentric"):

    EgoDexSource    Apple's EgoDex: <root>/<split_dir>/<task>/<i>.hdf5 + <i>.mp4, pose
                    tracked (E-B); the subset is pinned in configs/data/egocentric.yaml
    EgoVideoSource  the team's own recordings (`video_source.py`), pose estimated (E-A)

The EgoDex choice is deterministic, as DA-30's sample: the configured tasks in name
order, the `episodes_per_task` lowest episode numbers that have both files.

`EgoSourceRecord` is what `source.json` holds (plan 6/11/2026 4.2a, read by DA-18):
`source_id`, `source_detail`, `license`, `data_class`, `root`, `files` (path relative
to root -> sha256), `deid_waiver` (D2 reason or null), `deid_waiver_manifest` (the pin
of Apple's videos the waiver was checked against, or null; `annotate/deid/gate.py`)
and the chosen `episodes`.
`source_id` hashes the detail, licence, data class and every file hash, so the same
files give the same id and the same episode ids. Data stays out of git: `root` is a
directory of the store (`$FW_ROOT`, else ./fwdata).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from flywheel.data.annotate.deid.gate import deid_waiver
from flywheel.data.ingest.egocentric.config import EgoConfig, SourceConfig

SourceDetail = Literal["egodex", "ego_video"]
CHUNK = 1 << 20
DEVICE_FILE = "device.json"
_INDEX = re.compile(r"^\d+$")


@dataclass(frozen=True)
class EgoEpisodeFile:
    task: str
    index: int
    mp4: str  # relative to the source root (posix)
    hdf5: str | None  # None for a recording without tracking


@dataclass(frozen=True)
class EgoSourceRecord:
    source_id: str
    source_detail: str
    license: str
    data_class: Literal["public", "internal", "restricted"]
    root: str  # absolute
    files: dict[str, str]  # relative posix path -> sha256
    deid_waiver: str | None
    episodes: tuple[EgoEpisodeFile, ...]
    total_bytes: int = 0
    config_version: str = ""
    device: dict[str, Any] = field(default_factory=dict)  # EgoVideoSource's device.json
    deid_waiver_manifest: str | None = None  # pin id, set with deid_waiver

    def path(self, relative: str) -> Path:
        return Path(self.root) / relative


def select_egodex(split: Path, tasks: tuple[str, ...], per_task: int) -> list[EgoEpisodeFile]:
    """The first `per_task` complete episodes of each task, tasks in name order."""
    chosen = []
    for task in sorted(tasks):
        folder = split / task
        if not folder.is_dir():
            raise ValueError(f"{folder}: the pinned task {task!r} is not in the sample")
        indices = sorted(
            int(p.stem) for p in folder.glob("*.hdf5")
            if _INDEX.match(p.stem) and p.with_suffix(".mp4").is_file()
        )
        if len(indices) < per_task:
            raise ValueError(f"{folder}: {len(indices)} complete episodes, {per_task} pinned")
        base = split.name
        chosen += [EgoEpisodeFile(task, i, f"{base}/{task}/{i}.mp4", f"{base}/{task}/{i}.hdf5")
                   for i in indices[:per_task]]
    return chosen


def register_egodex(store: Path, cfg: EgoConfig) -> EgoSourceRecord:
    """EgoDexSource: the pinned subset of the EgoDex sample under the store."""
    source = cfg.sources["egodex"]
    if source.root is None or source.split_dir is None or source.episodes_per_task is None:
        raise ValueError("sources.egodex needs root, split_dir and episodes_per_task")
    root = (store / source.root).resolve()
    chosen = select_egodex(root / source.split_dir, source.tasks, source.episodes_per_task)
    return make_record("egodex", source, root, chosen, cfg, {})


def dump_record(record: EgoSourceRecord) -> str:
    return json.dumps(asdict(record), indent=2, sort_keys=True)


def load_record(text: str) -> EgoSourceRecord:
    data = json.loads(text)
    data["episodes"] = tuple(EgoEpisodeFile(**e) for e in data["episodes"])
    return EgoSourceRecord(**data)


def changed_files(record: EgoSourceRecord) -> list[str]:
    """Files whose sha256 differs from the record, or that are gone."""
    return [name for name, digest in record.files.items()
            if not record.path(name).is_file() or _sha256(record.path(name)) != digest]


def make_record(
    detail: str, source: SourceConfig, root: Path, chosen: list[EgoEpisodeFile],
    cfg: EgoConfig, device: dict[str, Any],
) -> EgoSourceRecord:
    names = [n for e in chosen for n in (e.hdf5, e.mp4) if n is not None]
    if device:
        names.append(DEVICE_FILE)
    files = {name: _sha256(root / name) for name in sorted(names)}
    waiver, pin = deid_waiver(detail, source.data_class, files)
    identity = hashlib.sha256(f"{detail}\n{source.license}\n{source.data_class}\n".encode())
    for name, digest in files.items():
        identity.update(f"{digest}  {name}\n".encode())
    return EgoSourceRecord(
        source_id=f"src_{identity.hexdigest()[:16]}",
        source_detail=detail,
        license=source.license,
        data_class=source.data_class,
        root=str(root),
        files=files,
        deid_waiver=waiver,
        episodes=tuple(chosen),
        total_bytes=sum((root / n).stat().st_size for n in files),
        config_version=cfg.threshold_version,
        device=device,
        deid_waiver_manifest=pin,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()
