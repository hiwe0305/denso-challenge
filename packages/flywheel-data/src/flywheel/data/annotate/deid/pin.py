"""Pin the videos of DA-30's EgoDex sample by sha256: the only videos D2 waives.

DA-30's `fetch` copied the sample out of Apple's test zip and wrote `manifest.json`
with each member's name, size and CRC-32 from the zip directory (`zipfile` checked
the CRC on extraction). CRC-32 tells a copy error, not a different file made to
match, so the pin re-checks size and CRC-32 against that manifest and then records
the sha256 of each video. `gate.py` waives a source only when every video's name and
sha256 are in the pin (review of PR 152, 7/11/2026).

Only the `.mp4` files are pinned. De-identification is about the images; the HDF5
holds tracking, no image, and DA-30's copies no longer match the zip because the
H-RDT step adds `actions_48d` to them (all 218 differ, all 218 videos match, checked
7/11/2026):

    python -m flywheel.data.annotate.deid.pin <sample root> <egodex_pin.json>

`<sample root>` holds DA-30's `manifest.json` and its `split_dir`.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zlib
from pathlib import Path
from typing import Any

CHUNK = 1 << 22


def pin_key(relative: str) -> str:
    """`<task>/<i>.<ext>`: a sample file's name without the zip's or the store's prefix."""
    parts = relative.split("/")
    return "/".join(parts[-2:])


def build_pin(root: Path) -> dict[str, Any]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    split = root / manifest["split_dir"]
    files: dict[str, str] = {}
    for record in manifest["files"]:
        key = pin_key(record["member"])
        if not key.endswith(".mp4"):
            continue
        path = split / key
        size, crc, digest = 0, 0, hashlib.sha256()
        with path.open("rb") as f:
            while chunk := f.read(CHUNK):
                size += len(chunk)
                crc = zlib.crc32(chunk, crc)
                digest.update(chunk)
        if size != record["bytes"] or f"{crc:08x}" != record["crc32"]:
            raise ValueError(f"{path}: size {size} / CRC-32 {crc:08x} differ from the zip's"
                             f" {record['bytes']} / {record['crc32']}")
        files[key] = digest.hexdigest()
    return {
        "name": "egodex-test-da30-" + manifest["split_dir"],
        "source": manifest["source"],
        "check": "size and CRC-32 equal to the zip directory (DA-30 manifest.json), then sha256",
        "files": dict(sorted(files.items())),
    }


def main(argv: list[str] | None = None) -> int:
    root, out = (Path(a) for a in (argv or sys.argv[1:]))
    pin = build_pin(root)
    out.write_text(json.dumps(pin, indent=1) + "\n", encoding="utf-8")
    print(f"{len(pin['files'])} files pinned in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
