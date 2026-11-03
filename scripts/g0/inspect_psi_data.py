#!/usr/bin/env python3
"""Measure the psi-data bundles of the two-table task and F1 (S1-07).

Every number this script prints is read from the bundles or from the Hugging Face API at
a pinned revision; nothing is assumed. The bundles stay zipped: subcommands read members
straight from the archive, so no unpacked copy is kept.

    python3 scripts/g0/inspect_psi_data.py fetch --revision e78fb93 \
        --out fwdata/psi-data/e78fb93 simple/G1WholebodyBendPickTeleop-v0.zip ...
    python3 scripts/g0/inspect_psi_data.py hash FILE...
    python3 scripts/g0/inspect_psi_data.py layout BUNDLE.zip --psi0-slices FILE \
        --psi0-stage3 FILE --names-from action_layout.json --json OUT.json

`fetch` and `hash` use the standard library only; the others need numpy and pyarrow.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import re
import sys
import urllib.request
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
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


# --- reading a zipped LeRobot v2.1 dataset ---------------------------------------------


@dataclass
class Dataset:
    """One LeRobot dataset inside a bundle zip (a bundle may hold several, e.g. eval levels)."""

    zf: zipfile.ZipFile
    root: str  # member prefix ending in "/"

    def json(self, rel: str) -> Any:
        return json.loads(self.zf.read(self.root + rel))

    def jsonl(self, rel: str) -> list[Any]:
        text = self.zf.read(self.root + rel).decode()
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def has(self, rel: str) -> bool:
        return self.root + rel in self.zf.NameToInfo

    def parquet_names(self) -> list[str]:
        return sorted(n for n in self.zf.namelist()
                      if n.startswith(self.root + "data/") and n.endswith(".parquet"))

    def video_names(self) -> list[str]:
        return sorted(n for n in self.zf.namelist()
                      if n.startswith(self.root + "videos/") and n.endswith(".mp4"))

    def episodes(self) -> Iterator[tuple[str, dict[str, Any]]]:
        """(member name, columns as numpy arrays) for every episode parquet."""
        import numpy as np
        import pyarrow.parquet as pq

        for name in self.parquet_names():
            table = pq.read_table(io.BytesIO(self.zf.read(name)))
            cols: dict[str, Any] = {}
            for col in table.column_names:
                values = table.column(col).to_pylist()
                cols[col] = np.asarray(values, dtype=float if col != "next.done" else bool)
            yield name, cols


def datasets(zf: zipfile.ZipFile) -> list[Dataset]:
    roots = sorted(n[: -len("meta/info.json")] for n in zf.namelist()
                   if n.endswith("meta/info.json"))
    return [Dataset(zf, r) for r in roots]


def single_dataset(path: Path) -> Dataset:
    found = datasets(zipfile.ZipFile(path))
    if len(found) != 1:
        raise SystemExit(f"{path}: expected one LeRobot dataset, found {len(found)}")
    return found[0]


# --- layout (AC 3, V1) -------------------------------------------------------------------


def psi0_slices(source: str) -> list[tuple[str, int, int]]:
    """ACTION_SLICES_36D from the source of Psi0's src/psi/data/simple/__init__.py."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "ACTION_SLICES_36D" for t in node.targets
        ):
            return [tuple(e) for e in ast.literal_eval(node.value)]  # type: ignore[misc]
    raise SystemExit("ACTION_SLICES_36D not found")


def psi0_layout_comment(source: str) -> dict[int, str]:
    """index -> the line of the 36-D layout comment block at the top of that file."""
    out: dict[int, str] = {}
    for line in source.splitlines():
        m = re.match(r"#\s+\[(\d+)(?::(\d+))?\]\s+(.*\S)", line)
        if m:
            start = int(m.group(1))
            stop = int(m.group(2)) if m.group(2) else start + 1
            for i in range(start, stop):
                out[i] = " ".join(m.group(3).split())
    return out


def pad_dims(script: str) -> dict[str, int]:
    """--data.transform.*.pad-{action,state}-dim values of a Psi0 training script."""
    found: dict[str, set[int]] = {}
    for m in re.finditer(r"pad-(action|state)-dim=(\d+)", script):
        found.setdefault(m.group(1), set()).add(int(m.group(2)))
    if any(len(v) != 1 for v in found.values()) or set(found) != {"action", "state"}:
        raise SystemExit(f"ambiguous pad dims in stage-3 script: {found}")
    return {k: v.pop() for k, v in found.items()}


def column_stats(ds: Dataset, column: str) -> dict[str, Any]:
    import numpy as np

    frames = np.concatenate([cols[column] for _, cols in ds.episodes()])
    return {
        "dim": int(frames.shape[1]),
        "frames": int(frames.shape[0]),
        "min": frames.min(axis=0).tolist(),
        "max": frames.max(axis=0).tolist(),
        "std": frames.std(axis=0).tolist(),
        "distinct": [int(len(np.unique(frames[:, i]))) for i in range(frames.shape[1])],
    }


def modality_keys(modality: dict[str, Any], kind: str, dim: int) -> list[tuple[str, bool]]:
    """(modality.json key, absolute) for each index of `kind` ("action" or "state")."""
    keys: list[tuple[str, bool] | None] = [None] * dim
    for key, spec in modality[kind].items():
        for i in range(spec["start"], spec["end"]):
            keys[i] = (key, bool(spec["absolute"]))
    if any(k is None for k in keys):
        raise SystemExit(f"modality.json does not cover every {kind} index")
    return keys  # type: ignore[return-value]


def cmd_layout(args: argparse.Namespace) -> int:
    ds = single_dataset(args.bundle)
    info = ds.json("meta/info.json")
    modality = ds.json("meta/modality.json")
    slices_src = args.psi0_slices.read_text()
    pads = pad_dims(args.psi0_stage3.read_text())
    action = column_stats(ds, "action")
    state = column_stats(ds, "states")
    names = json.loads(args.names_from.read_text())["dimensions"]

    psi0_label = {i: n for n, a, b in psi0_slices(slices_src) for i in range(a, b)}
    comment = psi0_layout_comment(slices_src)
    mod = modality_keys(modality, "action", action["dim"])
    rows = []
    for i in range(pads["action"]):
        raw = i < action["dim"]
        rows.append({
            "index": i,
            "name": names[i]["name"] if raw else None,
            "group": names[i]["group"] if raw else "padding",
            "masked": not raw,
            "modality_key": mod[i][0] if raw else None,
            "absolute": mod[i][1] if raw else None,
            "psi0_slice": psi0_label.get(i),
            "psi0_comment": comment.get(i),
            "min": action["min"][i] if raw else None,
            "max": action["max"][i] if raw else None,
            "std": action["std"][i] if raw else None,
            "distinct": action["distinct"][i] if raw else None,
        })
    features = {k: {"dtype": v["dtype"], "shape": v["shape"], "names": v.get("names")}
                for k, v in info["features"].items()}
    result = {
        "bundle": str(args.bundle),
        "codebase_version": info["codebase_version"],
        "fps": info["fps"],
        "robot_type": info["robot_type"],
        "features": features,
        "action_dim": action["dim"],
        "state_dim": state["dim"],
        "frames": action["frames"],
        "pad_dims": pads,
        "state_padded_indices": list(range(state["dim"], pads["state"])),
        "state_modality": modality["state"],
        "action": rows,
    }
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n")

    print(f"`{args.bundle.name}`: codebase_version `{info['codebase_version']}`, "
          f"fps {info['fps']}, robot_type `{info['robot_type']}`, {action['frames']:,} khung\n")
    print("| Trường | dtype | shape trong `info.json` | names |\n|---|---|---|---|")
    for k, v in features.items():
        print(f"| `{k}` | {v['dtype']} | {v['shape']} | {v['names']} |")
    print(f"\nĐo trên parquet: `action` {action['dim']} chiều, `states` {state['dim']} chiều. "
          f"Ψ₀ stage 3: pad-action-dim {pads['action']}, pad-state-dim {pads['state']}; "
          f"chỉ số state được đệm: {result['state_padded_indices']}.\n")
    print("| index | name | group | masked | key `modality.json` | Ψ₀ `ACTION_SLICES_36D` "
          "| chú thích Ψ₀ | min | max | số giá trị khác nhau |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        absolute = "" if r["absolute"] is None else (" (abs)" if r["absolute"] else " (rel)")
        print(f"| {r['index']} | `{r['name']}` | {r['group']} | {str(r['masked']).lower()} "
              f"| `{r['modality_key']}`{absolute} | {r['psi0_slice'] or '—'} "
              f"| {r['psi0_comment'] or '—'} | {r['min']:.4g} | {r['max']:.4g} "
              f"| {r['distinct']:,} |")
    constant = [r["index"] for r in rows if r["distinct"] == 1]
    print(f"\nChiều action hằng số trên mọi khung (1 giá trị): {constant}")
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

    p = sub.add_parser("layout", help="fields of info.json and the 36-row action table")
    p.add_argument("bundle", type=Path)
    p.add_argument("--psi0-slices", type=Path, required=True,
                   help="Psi0 src/psi/data/simple/__init__.py at the pinned commit")
    p.add_argument("--psi0-stage3", type=Path, required=True,
                   help="Psi0 stage-3 script holding pad-action-dim and pad-state-dim")
    p.add_argument("--names-from", type=Path, required=True,
                   help="an ActionLayout JSON naming the 36 dims (SIMPLE g1_sonic joints)")
    p.add_argument("--json", type=Path)
    p.set_defaults(func=cmd_layout)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
