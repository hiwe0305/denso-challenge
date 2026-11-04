"""Stand-in for the DA-18 export: a few EgoDex test episodes in Psi0's stage 1 layout.

Psi0's `EgoDexDataset` reads `<root>/<part>/<task>/<i>.hdf5` with its `<i>.mp4`, and
needs `actions_48d` in each HDF5, which the authors' H-RDT script adds. Apple's test
set is one 17 GB zip; a short run needs a few hundred episodes, so `fetch` reads the
zip's directory and only the chosen members through HTTP range requests:

    python3 -m flywheel_psi0.stage1.egodex_sample fetch --plan <plan.yaml> --out <root>

Standard library and PyYAML only, both in the VM's python before Psi0's environment
exists. The choice is deterministic: tasks in name order, the `episodes_per_task`
lowest episode numbers that have both files. `manifest.json` records what was taken
(name, size, CRC-32 from the zip, which `zipfile` checks on extraction).
"""

from __future__ import annotations

import argparse
import http.client
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# A dropped connection mid-request (seen on 4/11/2026 after ~1.5 GB) is retried with
# backoff; a whole `fetch` can also be rerun, it keeps the files already written.
RETRIES = 6
_TRANSIENT = (http.client.HTTPException, urllib.error.URLError, OSError)

_EPISODE = re.compile(r"^[^/]+/(?P<task>[^/]+)/(?P<index>\d+)\.(?P<ext>hdf5|mp4)$")


class RangeReader(io.RawIOBase):
    """A read-only, seekable view of a remote file, one HTTP range request per read."""

    def __init__(self, url: str, size: int | None = None) -> None:
        self.url = url
        if size is None:
            head = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(head, timeout=60) as response:
                size = int(response.headers["Content-Length"])
                self.etag: str | None = response.headers.get("ETag")
        else:
            self.etag = None
        self.size = size
        self._pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self.size}[whence]
        self._pos = base + offset
        return self._pos

    def readinto(self, buffer: Any) -> int:
        count = min(len(buffer), self.size - self._pos)
        if count <= 0:
            return 0
        headers = {"Range": f"bytes={self._pos}-{self._pos + count - 1}"}
        request = urllib.request.Request(self.url, headers=headers)
        for attempt in range(RETRIES):
            try:
                with urllib.request.urlopen(request, timeout=300) as response:
                    data = response.read()
                if len(data) == count:
                    break
            except _TRANSIENT:
                if attempt == RETRIES - 1:
                    raise
            time.sleep(min(2**attempt, 30))
        else:
            raise OSError(f"{self.url}: {len(data)} of {count} bytes after {RETRIES} tries")
        buffer[: len(data)] = data
        self._pos += len(data)
        return len(data)


def select(names: Iterable[str], per_task: int) -> list[tuple[str, int]]:
    """`(task, index)` of the first `per_task` complete episodes of each task."""
    found: dict[tuple[str, int], set[str]] = defaultdict(set)
    for name in names:
        match = _EPISODE.match(name)
        if match:
            found[(match["task"], int(match["index"]))].add(match["ext"])
    by_task: dict[str, list[int]] = defaultdict(list)
    for (task, index), extensions in found.items():
        if extensions == {"hdf5", "mp4"}:
            by_task[task].append(index)
    return [(task, i) for task in sorted(by_task) for i in sorted(by_task[task])[:per_task]]


def extract(
    archive: zipfile.ZipFile, chosen: list[tuple[str, int]], out: Path
) -> list[dict[str, Any]]:
    """Copy the chosen pairs to `out/<task>/<i>.{hdf5,mp4}`; an intact file is kept."""
    by_name = {
        (m["task"], int(m["index"]), m["ext"]): info
        for info in archive.infolist()
        if (m := _EPISODE.match(info.filename))
    }
    records = []
    for task, index in chosen:
        for ext in ("hdf5", "mp4"):
            info = by_name[(task, index, ext)]
            target = out / task / f"{index}.{ext}"
            if not (target.exists() and target.stat().st_size == info.file_size):
                target.parent.mkdir(parents=True, exist_ok=True)
                partial = target.with_suffix(f".{ext}.part")
                with archive.open(info) as source, partial.open("wb") as sink:
                    while chunk := source.read(1 << 22):
                        sink.write(chunk)
                partial.replace(target)
            records.append(
                {"member": info.filename, "bytes": info.file_size, "crc32": f"{info.CRC:08x}"}
            )
    return records


def fetch(
    url: str, out_root: Path, split_dir: str, per_task: int, etag: str | None
) -> dict[str, Any]:
    reader = RangeReader(url)
    if etag is not None and reader.etag is not None and reader.etag != etag:
        raise RuntimeError(f"{url} changed: ETag {reader.etag}, the plan pins {etag}")
    with zipfile.ZipFile(io.BufferedReader(reader, buffer_size=1 << 22)) as archive:
        chosen = select(archive.namelist(), per_task)
        files = extract(archive, chosen, out_root / split_dir)
    manifest = {
        "source": {"url": url, "bytes": reader.size, "etag": reader.etag},
        "split_dir": split_dir,
        "episodes_per_task": per_task,
        "episodes": len(chosen),
        "tasks": len({task for task, _ in chosen}),
        "bytes": sum(record["bytes"] for record in files),
        "files": files,
    }
    (out_root / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def layout_problems(root: Path, split_dir: str) -> list[str]:
    """What keeps Psi0's loader from seeing every episode under `root/split_dir`."""
    split = root / split_dir
    if not split.is_dir():
        return [f"{split} is missing"]
    problems = []
    episodes = 0
    for task in sorted(p for p in split.iterdir() if p.is_dir()):
        for hdf5 in sorted(task.glob("*.hdf5")):
            episodes += 1
            if not hdf5.with_suffix(".mp4").exists():
                problems.append(f"{hdf5} has no .mp4")
    if episodes == 0:
        problems.append(f"no episode under {split}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("command", choices=["fetch", "check"])
    parser.add_argument("--plan", type=Path, required=True, help="stage 1 RunPlan YAML")
    parser.add_argument("--out", type=Path, required=True, help="export root")
    args = parser.parse_args(argv)
    import yaml

    dataset = yaml.safe_load(args.plan.read_text(encoding="utf-8"))["dataset"]
    if args.command == "fetch":
        manifest = fetch(
            dataset["source"]["url"],
            args.out,
            dataset["split_dir"],
            int(dataset["episodes_per_task"]),
            dataset["source"]["etag"],
        )
        print(json.dumps({k: v for k, v in manifest.items() if k != "files"}))
    problems = layout_problems(args.out, dataset["split_dir"])
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
