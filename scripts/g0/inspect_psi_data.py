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
from collections.abc import Iterator, Sequence
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
        match = "có" if r["match"] else "KHÔNG"
        print(f"| `{r['path']}` | {r['size']:,} | `{r['sha256']}` | {match} |")
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
            return [(str(n), int(a), int(b)) for n, a, b in ast.literal_eval(node.value)]
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


# --- preliminary QA (AC 2, Q1) -----------------------------------------------------------

QA_CHECKS = ("frames_match_meta", "frame_index_contiguous", "timestamp_monotonic",
             "finite", "length_in_range", "done_at_last_frame_only", "video_present")
SUCCESS_KEYS = re.compile(r"success|is_success|succeeded", re.IGNORECASE)


def success_fields(ds: Dataset, meta_rows: list[dict[str, Any]], columns: set[str]) -> list[str]:
    """Names of any per-episode success flag in episodes.jsonl or the parquet columns."""
    keys = {k for row in meta_rows for k in row} | columns
    return sorted(k for k in keys if SUCCESS_KEYS.search(k))


def qa_dataset(ds: Dataset, min_s: float, max_s: float) -> dict[str, Any]:
    import numpy as np

    info = ds.json("meta/info.json")
    fps = float(info["fps"])
    meta = {int(r["episode_index"]): r for r in ds.jsonl("meta/episodes.jsonl")}
    videos = {Path(n).stem for n in ds.video_names()}
    episodes: list[dict[str, Any]] = []
    columns: set[str] = set()
    for name, cols in ds.episodes():
        columns |= set(cols)
        idx = int(cols["episode_index"][0])
        t = cols["timestamp"]
        n = len(t)
        numeric = [v for k, v in cols.items() if v.dtype.kind == "f"]
        done = cols["next.done"]
        dt = np.diff(t)
        checks = {
            "frames_match_meta": idx in meta and int(meta[idx]["length"]) == n,
            "frame_index_contiguous": bool(np.array_equal(cols["frame_index"], np.arange(n))),
            "timestamp_monotonic": bool(n > 0 and np.all(dt > 0)),
            "finite": all(bool(np.isfinite(v).all()) for v in numeric),
            "length_in_range": min_s <= n / fps <= max_s,
            "done_at_last_frame_only": bool(n > 0 and done[-1] and not done[:-1].any()),
            "video_present": f"episode_{idx:06d}" in videos,
        }
        episodes.append({
            "episode_index": idx,
            "member": name,
            "frames": n,
            "seconds": n / fps,
            "max_timestamp_drift_s": float(np.abs(t - np.arange(n) / fps).max()) if n else None,
            "checks": checks,
            "passed": all(checks.values()),
        })
    flags = success_fields(ds, list(meta.values()), columns)
    counts = {c: sum(e["checks"][c] for e in episodes) for c in QA_CHECKS}
    return {
        "root": ds.root,
        "fps": fps,
        "info_total_episodes": info["total_episodes"],
        "info_total_frames": info["total_frames"],
        "parquet_episodes": len(episodes),
        "parquet_frames": sum(e["frames"] for e in episodes),
        "meta_episodes": len(meta),
        "videos": len(videos),
        "success_fields": flags,
        "thresholds": {"min_seconds": min_s, "max_seconds": max_s},
        "counts": counts,
        "n_passed": sum(e["passed"] for e in episodes),
        "max_timestamp_drift_s": max((e["max_timestamp_drift_s"] or 0.0) for e in episodes),
        "failed": [{"episode_index": e["episode_index"],
                    "failed_checks": [c for c, ok in e["checks"].items() if not ok]}
                   for e in episodes if not e["passed"]],
        "episodes": episodes,
    }


def cmd_qa(args: argparse.Namespace) -> int:
    ds = single_dataset(args.bundle)
    r = qa_dataset(ds, args.min_seconds, args.max_seconds)
    if args.json:
        args.json.write_text(json.dumps(r, indent=2) + "\n")
    n = r["parquet_episodes"]
    print(f"`{args.bundle.name}`: `info.json` {r['info_total_episodes']} episode, "
          f"{r['info_total_frames']:,} khung; parquet {n} episode, {r['parquet_frames']:,} khung; "
          f"`episodes.jsonl` {r['meta_episodes']} dòng; video {r['videos']}\n")
    labels = {
        "frames_match_meta": "Số khung parquet = `length` trong `episodes.jsonl`",
        "frame_index_contiguous": "`frame_index` = 0, 1, …, T−1",
        "timestamp_monotonic": "`timestamp` tăng nghiêm ngặt",
        "finite": "Không NaN hay Inf ở mọi cột số thực",
        "length_in_range": (f"Độ dài trong [{args.min_seconds:g} s, {args.max_seconds:g} s] "
                            "(ngưỡng giả định)"),
        "done_at_last_frame_only": "`next.done` chỉ đúng ở khung cuối",
        "video_present": "Có file video của episode",
    }
    print("| Phép kiểm | Đạt |\n|---|---|")
    for c in QA_CHECKS:
        print(f"| {labels[c]} | {r['counts'][c]}/{n} |")
    flag = ", ".join(f"`{f}`" for f in r["success_fields"]) or "không có trường nào"
    print(f"| Cờ thành công | {flag} |")
    print(f"| **Đạt mọi phép kiểm** | **{r['n_passed']}/{n}** |")
    print(f"\nLệch lớn nhất giữa `timestamp` và `frame_index / fps`: "
          f"{r['max_timestamp_drift_s']:.3g} s")
    if r["failed"]:
        print("\nEpisode trượt:", json.dumps(r["failed"]))
    return 0


# --- seeds and randomization (AC 4, V6) --------------------------------------------------

SEED_KEY = re.compile(r"seed", re.IGNORECASE)


def find_seed_keys(value: Any, path: str = "") -> list[tuple[str, Any]]:
    """(json path, value) of every key matching 'seed', descending into JSON strings too."""
    if isinstance(value, str) and value[:1] in "{[":
        try:
            value = json.loads(value)
        except ValueError:
            return []
    found: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for k, v in value.items():
            if SEED_KEY.search(k):
                found.append((f"{path}.{k}", v))
            found += find_seed_keys(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found += find_seed_keys(v, f"{path}[{i}]")
    return found


def canonical(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def spatial_positions(env: dict[str, Any]) -> dict[str, list[float]]:
    """Initial position of every actor drawn by SpatialDR (`dr_state_dict.spatial`)."""
    return {k: v["position"] for k, v in env.get("dr_state_dict", {}).get("spatial", {}).items()}


def seeds_dataset(ds: Dataset) -> dict[str, Any]:
    meta_files = sorted(n[len(ds.root):] for n in ds.zf.namelist()
                        if n.startswith(ds.root + "meta/") and n.endswith((".json", ".jsonl")))
    seed_hits: list[tuple[str, Any]] = []
    for rel in meta_files:
        doc = ds.jsonl(rel) if rel.endswith(".jsonl") else ds.json(rel)
        seed_hits += [(rel + p, v) for p, v in find_seed_keys(doc)]
    columns = set(next(ds.episodes())[1]) if ds.parquet_names() else set()
    rows = ds.jsonl("meta/episodes.jsonl")
    envs = {int(r["episode_index"]): json.loads(r["environment_config"])
            for r in rows if "environment_config" in r}
    return {
        "root": ds.root,
        "episodes": len(rows),
        "meta_files": meta_files,
        "seed_keys": [{"path": p, "value": v} for p, v in seed_hits],
        "seed_columns": sorted(c for c in columns if SEED_KEY.search(c)),
        "split": sorted({str(e["metadata"].get("split")) for e in envs.values()}),
        "dr_level": sorted({str(e["metadata"].get("dr_level")) for e in envs.values()}),
        "with_layout": sum("layout" in e for e in envs.values()),
        "with_dr_state_dict": sum("dr_state_dict" in e for e in envs.values()),
        "distinct_dr_cfgs": len({canonical(e.get("dr_cfgs")) for e in envs.values()}),
        "conditions": {i: canonical(e.get("dr_state_dict")) for i, e in envs.items()},
        "spatial": {i: spatial_positions(e) for i, e in envs.items()},
    }


def same_index_matches(train: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    """Per spatial actor: episodes i of `other` whose initial position equals train episode i's.

    SpatialDR draws positions in a fixed order from the episode's RNG, so equal floats at the
    same index mean the two episodes started from the same random stream (the same seed).
    """
    # Distractors are keyed by asset uid and change per episode; compare the actors every
    # episode of both datasets has (robot, container, target).
    common = set.intersection(*(set(p) for p in [*train["spatial"].values(),
                                                  *other["spatial"].values()]))
    actors = {a: 0 for a in sorted(common)}
    for i, pos in other["spatial"].items():
        ref = train["spatial"].get(i, {})
        for actor in common:
            actors[actor] += int(ref.get(actor) == pos[actor])
    equal_condition = sum(train["conditions"].get(i) == h for i, h in other["conditions"].items())
    any_condition = len(set(other["conditions"].values()) & set(train["conditions"].values()))
    return {"actors": actors, "equal_condition_same_index": equal_condition,
            "condition_in_train": any_condition}


def label(bundle: Path) -> str:
    return f"{bundle.parent.parent.name}/{bundle.parent.name}/{bundle.name}"


def cmd_seeds(args: argparse.Namespace) -> int:
    report = []
    for bundle in [args.train, *args.bundles]:
        for ds in datasets(zipfile.ZipFile(bundle)):
            report.append({"bundle": label(bundle), "sha256": sha256_file(bundle),
                           **seeds_dataset(ds)})
    train = report[0]
    for r in report[1:]:
        r["vs_train"] = same_index_matches(train, r)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    print("| Gói (sha256) | Dataset | Episode | Khóa `seed` trong meta | Cột `seed` "
          "| `split` | `dr_level` | Có `layout` | Có `dr_state_dict` | `dr_cfgs` khác nhau |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in report:
        keys = len(r["seed_keys"]) or "không"
        print(f"| `{r['bundle']}` (`{r['sha256'][:8]}`) | `{r['root'].rstrip('/')}` "
              f"| {r['episodes']} | {keys} | {', '.join(r['seed_columns']) or 'không'} "
              f"| {', '.join(r['split'])} | {', '.join(r['dr_level'])} "
              f"| {r['with_layout']}/{r['episodes']} | {r['with_dr_state_dict']}/{r['episodes']} "
              f"| {r['distinct_dr_cfgs']} |")
    print(f"\nSo với gói train `{train['bundle']}`: số episode i có vị trí ban đầu trùng đúng "
          "từng số với episode i của train, theo từng vật có mặt ở mọi episode của "
          "`dr_state_dict.spatial` (vật gây nhiễu đổi theo episode nên không so).\n")
    print("| Gói | Dataset | Episode | Vị trí trùng theo vật | `dr_state_dict` trùng cùng chỉ số "
          "| `dr_state_dict` có trong train |\n|---|---|---|---|---|---|")
    for r in report[1:]:
        v = r["vs_train"]
        actors = ", ".join(f"`{a}` {n}" for a, n in v["actors"].items())
        print(f"| `{r['bundle']}` | `{r['root'].rstrip('/')}` | {r['episodes']} | {actors} "
              f"| {v['equal_condition_same_index']} | {v['condition_in_train']} |")
    for r in report:
        for k in r["seed_keys"][:20]:
            print(f"- seed `{r['root']}{k['path']}` = {k['value']!r}")
    return 0


# --- descriptive statistics (AC 6) -------------------------------------------------------


def describe(values: Sequence[float]) -> dict[str, float]:
    import numpy as np

    a = np.asarray(values, dtype=float)
    q = np.percentile(a, [0, 10, 50, 90, 100])
    return {"n": int(a.size), "mean": float(a.mean()), "std": float(a.std()),
            "min": float(q[0]), "p10": float(q[1]), "median": float(q[2]),
            "p90": float(q[3]), "max": float(q[4])}


def stats_dataset(ds: Dataset) -> dict[str, Any]:
    info = ds.json("meta/info.json")
    fps = float(info["fps"])
    rows = ds.jsonl("meta/episodes.jsonl")
    lengths = [int(r["length"]) for r in rows]
    positions: dict[str, list[list[float]]] = {}
    tables: dict[str, list[list[float]]] = {}
    labels: dict[str, dict[str, int]] = {"target": {}, "container": {}}
    distractors: list[int] = []
    for r in rows:
        env = json.loads(r["environment_config"])
        dr = env.get("dr_state_dict", {})
        spatial = dr.get("spatial", {})
        robot = env["robot_cfg"]["uid"]
        target = dr.get("target", {}).get("uid")
        named = {"robot": spatial.get(robot), "target": spatial.get(str(target)),
                 "container": spatial.get("container_0")}
        for role, p in named.items():
            if p is not None:
                positions.setdefault(role, []).append(p["position"])
        for role in labels:
            if role in dr:
                lab = dr[role]["label"]
                labels[role][lab] = labels[role].get(lab, 0) + 1
        distractors.append(len(dr.get("distractors", {})))
        for name, actor in env.get("layout", {}).get("actors", {}).items():
            if name.startswith("table"):
                tables.setdefault(name, []).append(actor["pose"]["position"])
    axes = "xyz"
    pos_stats = {role: {axes[k]: describe([p[k] for p in ps]) for k in range(2)}
                 for role, ps in positions.items()}
    table_stats = {name: {axes[k]: describe([p[k] for p in ps]) for k in range(3)}
                   for name, ps in tables.items()}
    return {
        "root": ds.root,
        "episodes": len(rows),
        "frames": sum(lengths),
        "length_frames": describe(lengths),
        "length_seconds": describe([n / fps for n in lengths]),
        "success_rate": None,  # no success flag in the bundle (qa: success_fields == [])
        "initial_xy": pos_stats,
        "tables": table_stats,
        "labels": labels,
        "distractors_per_episode": describe(distractors),
    }


def cmd_stats(args: argparse.Namespace) -> int:
    report = []
    for bundle in args.bundles:
        for ds in datasets(zipfile.ZipFile(bundle)):
            report.append({"bundle": label(bundle), **stats_dataset(ds)})
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    print("| Dataset | Episode | Khung | Độ dài (s): min · p10 · trung vị · p90 · max · TB ± ĐLC "
          "| Tỉ lệ thành công |\n|---|---|---|---|---|")
    for r in report:
        s = r["length_seconds"]
        print(f"| `{r['root'].rstrip('/')}` | {r['episodes']} | {r['frames']:,} "
              f"| {s['min']:.2f} · {s['p10']:.2f} · {s['median']:.2f} · {s['p90']:.2f} "
              f"· {s['max']:.2f} · {s['mean']:.2f} ± {s['std']:.2f} | không suy được |")
    print("\nVị trí ban đầu (m, hệ thế giới, từ `dr_state_dict.spatial`): min … max (TB ± ĐLC)\n")
    print("| Dataset | Vật | x | y |\n|---|---|---|---|")
    for r in report:
        for role, ax in r["initial_xy"].items():
            cells = [f"{a['min']:.3f} … {a['max']:.3f} ({a['mean']:.3f} ± {a['std']:.3f})"
                     for a in ax.values()]
            print(f"| `{r['root'].rstrip('/')}` | {role} | " + " | ".join(cells) + " |")
    print("\nBàn (tâm, m, từ `layout.actors`): min … max\n")
    print("| Dataset | Bàn | x | y | z |\n|---|---|---|---|---|")
    for r in report:
        for name, ax in r["tables"].items():
            cells = [f"{a['min']:.3f} … {a['max']:.3f}" for a in ax.values()]
            print(f"| `{r['root'].rstrip('/')}` | `{name}` | " + " | ".join(cells) + " |")
    print("\n| Dataset | Vật cần gắp | Thùng | Số vật gây nhiễu mỗi episode |\n|---|---|---|---|")
    for r in report:
        tgt = ", ".join(f"`{k}` {v}" for k, v in r["labels"]["target"].items()) or "—"
        con = ", ".join(f"`{k}` {v}" for k, v in r["labels"]["container"].items()) or "—"
        d = r["distractors_per_episode"]
        print(f"| `{r['root'].rstrip('/')}` | {tgt} | {con} | {d['min']:.0f}–{d['max']:.0f} |")
    return 0


# --- asset sources (AC 5, V9) ------------------------------------------------------------


def asset_refs(value: Any, out: dict[str, set[str]]) -> None:
    """Collect res_id of assets, scene rooms and material libraries from an env config."""
    if isinstance(value, dict):
        if "res_id" in value and "uid" in value:
            out.setdefault("res_id", set()).add(str(value["res_id"]))
        for k, v in value.items():
            if k == "room_choices":
                out.setdefault("room", set()).update(map(str, v))
            elif k == "path" and isinstance(v, str) and v.endswith(".mdl"):
                out.setdefault("material", set()).add(v.split("/")[1] if "/" in v else v)
            asset_refs(v, out)
    elif isinstance(value, list):
        for v in value:
            asset_refs(v, out)


def cmd_assets(args: argparse.Namespace) -> int:
    print("| Gói | Dataset | `res_id` của vật | Cảnh (`room_choices`) | Thư viện vật liệu |")
    print("|---|---|---|---|---|")
    for bundle in args.bundles:
        for ds in datasets(zipfile.ZipFile(bundle)):
            refs: dict[str, set[str]] = {}
            for row in ds.jsonl("meta/episodes.jsonl"):
                asset_refs(json.loads(row.get("environment_config", "{}")), refs)
            cells = [", ".join(f"`{x}`" for x in sorted(refs.get(k, ()))) or "—"
                     for k in ("res_id", "room", "material")]
            print(f"| `{label(bundle)}` | `{ds.root.rstrip('/')}` | " + " | ".join(cells) + " |")
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

    p = sub.add_parser("qa", help="preliminary QA per episode and N passing (AC 2, Q1)")
    p.add_argument("bundle", type=Path)
    p.add_argument("--min-seconds", type=float, required=True)
    p.add_argument("--max-seconds", type=float, required=True)
    p.add_argument("--json", type=Path)
    p.set_defaults(func=cmd_qa)

    p = sub.add_parser("seeds", help="seed, layout and randomization fields (AC 4, V6)")
    p.add_argument("--train", type=Path, required=True, help="the task's train bundle")
    p.add_argument("bundles", nargs="+", type=Path, help="eval or other bundles of the task")
    p.add_argument("--json", type=Path)
    p.set_defaults(func=cmd_seeds)

    p = sub.add_parser("stats", help="descriptive statistics for the dataset report (AC 6)")
    p.add_argument("bundles", nargs="+", type=Path)
    p.add_argument("--json", type=Path)
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("assets", help="asset sources the episodes reference (AC 5, V9)")
    p.add_argument("bundles", nargs="+", type=Path)
    p.set_defaults(func=cmd_assets)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
