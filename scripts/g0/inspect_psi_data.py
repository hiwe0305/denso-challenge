#!/usr/bin/env python3
"""Measure the psi-data bundles of the two-table task and F1 (S1-07).

Every number this script prints is read from the bundles or from the Hugging Face API at
a pinned revision; nothing is assumed. The bundles stay zipped: subcommands read members
straight from the archive, so no unpacked copy is kept.

    python3 scripts/g0/inspect_psi_data.py fetch --revision e78fb93 \
        --out fwdata/psi-data/e78fb93 simple/G1WholebodyBendPickTeleop-v0.zip ...
    python3 scripts/g0/inspect_psi_data.py hash FILE...

`fetch` and `hash` use the standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

REPO = "USC-PSI-Lab/psi-data"
HF_REVISION = "https://huggingface.co/api/datasets/{repo}/revision/{rev}"
HF_TREE = "https://huggingface.co/api/datasets/{repo}/tree/{rev}?recursive=true"
HF_FILE = "https://huggingface.co/datasets/{repo}/resolve/{rev}/{path}"
CHUNK = 1 << 20


def _get_json(url: str) -> Any:
    with urllib.request.urlopen(url) as resp:
        return json.load(resp)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def resolve_revision(rev: str) -> str:
    """Full commit sha of a (possibly short) revision of the dataset repo."""
    return str(_get_json(HF_REVISION.format(repo=REPO, rev=rev))["sha"])


def remote_files(sha: str) -> dict[str, dict[str, Any]]:
    """path -> {size, oid} of every file at the revision; oid is the LFS sha256 if any."""
    tree = _get_json(HF_TREE.format(repo=REPO, rev=sha))
    return {
        e["path"]: {"size": e["size"], "oid": (e.get("lfs") or {}).get("oid")}
        for e in tree
        if e["type"] == "file"
    }


def download(url: str, dest: Path) -> str:
    """Stream url to dest, returning the sha256 of the bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    h = hashlib.sha256()
    with urllib.request.urlopen(url) as resp, part.open("wb") as out:
        while chunk := resp.read(CHUNK):
            h.update(chunk)
            out.write(chunk)
    part.replace(dest)
    return h.hexdigest()


def cmd_fetch(args: argparse.Namespace) -> int:
    sha = resolve_revision(args.revision)
    remote = remote_files(sha)
    rows = []
    for path in args.paths:
        if path not in remote:
            raise SystemExit(f"{path} is not in {REPO}@{sha}")
        expected = remote[path]
        dest = args.out / path
        if dest.exists() and dest.stat().st_size == expected["size"]:
            digest = sha256_file(dest)
        else:
            digest = download(HF_FILE.format(repo=REPO, rev=sha, path=path), dest)
        size = dest.stat().st_size
        ok = size == expected["size"] and digest == expected["oid"]
        rows.append({"path": path, "local": str(dest), "size": size, "sha256": digest,
                     "hf_size": expected["size"], "hf_oid": expected["oid"], "match": ok})
    record = {"repo": REPO, "revision": sha, "files": rows}
    (args.out / "fetch.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"{REPO} @ {sha}\n")
    print("| Đường dẫn trên HF | Kích thước (B) | sha256 | Khớp `lfs.oid` của HF |")
    print("|---|---|---|---|")
    for r in rows:
        print(f"| `{r['path']}` | {r['size']:,} | `{r['sha256']}` | {'có' if r['match'] else 'KHÔNG'} |")
    return 0 if all(r["match"] for r in rows) else 1


def cmd_hash(args: argparse.Namespace) -> int:
    for path in args.files:
        print(f"{sha256_file(path)}  {path.stat().st_size:>12,}  {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("fetch", help="download bundles at a pinned revision, check sha256")
    p.add_argument("--revision", required=True)
    p.add_argument("--out", type=Path, required=True, help="root; files land at OUT/<hf path>")
    p.add_argument("paths", nargs="+", help="paths inside the dataset repo")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("hash", help="sha256 and size of local files")
    p.add_argument("files", nargs="+", type=Path)
    p.set_defaults(func=cmd_hash)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
