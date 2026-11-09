"""The team's stage 1 export as the dataset of a stage 1 RunPlan (DA-30 task 2).

DA-18's `flywheel.data.export.egodex.export_stage1` writes Psi0's EgoDex layout:

    <root>/part1/<task>/<i>.hdf5 + <i>.mp4    one sample each, `actions_48d` included
    <root>/egodex_stat.json                   the export's own stats (not used to train)
    <root>/meta.json                          export_id, per-file sha256, source

A RunPlan pins it by `export_id` and by the sha256 of one tarball of that directory,
which `pack` writes and the VM gets from Google Drive:

    python -m flywheel_psi0.stage1.export_source pack --export <root> --out <tar>
    python -m flywheel_psi0.stage1.export_source verify --export <root> --export-id <id>

`pack` checks the export first and writes a tar that depends only on the files
(sorted, mtime 0, no owner), so the same export always gives the same sha256.
`fetch` copies the tarball from Drive to the VM, refuses it unless its sha256 is the
plan's, unpacks it (regular files and directories only) and runs `verify_export`:
the `export_id` is the plan's and the one `meta.json`'s files hash to, every file's
sha256 is the one `meta.json` lists, no file is on disk that `meta.json` does not
list (Psi0's loader would train on it), and `layout_problems` is empty.

Standard library and `flywheel.contracts` (pydantic) only: `setup` runs this in the
VM's python before Psi0's environment exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from flywheel.contracts.base import content_id

from flywheel_psi0.stage1.egodex_sample import layout_problems

META_FILE = "meta.json"
STATS_FILE = "egodex_stat.json"
FORMAT = "psi0-stage1-egodex"  # `flywheel.data.export.egodex.FORMAT`
_CHUNK = 1 << 22


class ExportRefused(RuntimeError):
    """The export or its tarball is not the one the plan pins; `problems` lists why."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = list(problems)
        super().__init__("export refused:\n" + "\n".join(f"- {p}" for p in self.problems))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def verify_export(
    root: Path, export_id: str, split_dir: str, data_class: str | None = None
) -> list[str]:
    """Why `root` is not the export `export_id`; empty when it is."""
    meta_path = root / META_FILE
    if not meta_path.is_file():
        return [f"{meta_path} is missing"]
    meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if meta.get("format") != FORMAT:
        problems.append(f"format {meta.get('format')!r}, want {FORMAT!r}")
    if meta.get("export_id") != export_id:
        problems.append(f"meta.json export_id {meta.get('export_id')}, the plan pins {export_id}")
    files: dict[str, str] = meta.get("files") or {}
    content = {"format": meta.get("format"), "recipe": meta.get("recipe"), "files": files}
    hashed = content_id("egx", content)
    if hashed != meta.get("export_id"):
        problems.append(f"meta.json files hash to {hashed}, not its export_id")
    for name, want in sorted(files.items()):
        path = root / name
        if not path.is_file():
            problems.append(f"{name} is listed in meta.json but missing")
        elif sha256(path) != want:
            problems.append(f"{name} sha256 differs from meta.json")
    on_disk = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    extra = sorted(on_disk - set(files) - {META_FILE})
    if extra:
        problems.append(f"{len(extra)} file(s) not in meta.json, e.g. {extra[:3]}")
    if data_class is not None and (meta.get("source") or {}).get("data_class") != data_class:
        problems.append(
            f"meta.json source data_class {(meta.get('source') or {}).get('data_class')!r}, "
            f"the plan says {data_class!r}"
        )
    if (meta.get("source") or {}).get("deid_waiver") is not None:
        problems.append("meta.json source has a de-identification waiver: not the team's video")
    by_part = (meta.get("counts") or {}).get("by_part") or {}
    if not by_part.get(split_dir):
        problems.append(f"meta.json counts no sample under {split_dir}/")
    problems += layout_problems(root, split_dir)
    return problems


def stats_coverage(export: dict[str, Any], shipped: dict[str, Any]) -> dict[str, Any]:
    """How the export's q01..q99 per dim sits in the training stats' (`egodex` blocks).

    The run normalizes with the shipped stats, and Psi0 clips the normalized action to
    [-1, 1] (`config/transform.py:682` at the pin): a dim whose export range reaches past
    the shipped q01..q99 loses its tails to the clip. Dims where the shipped range is
    zero (the pads, 6:9 and 30:33) are left out. Reported, never a refusal.
    """
    low, high = export["egodex"]["q01"], export["egodex"]["q99"]
    ship_low, ship_high = shipped["egodex"]["q01"], shipped["egodex"]["q99"]
    ratios: dict[int, float] = {}
    outside: list[int] = []
    for dim, (lo, hi, slo, shi) in enumerate(zip(low, high, ship_low, ship_high, strict=True)):
        if shi - slo <= 0:
            continue
        ratios[dim] = (hi - lo) / (shi - slo)
        if lo < slo or hi > shi:
            outside.append(dim)
    spans = sorted(ratios.values())
    return {
        "dims": len(ratios),
        "dims_outside_shipped_q01_q99": outside,
        "span_ratio_median": round(spans[len(spans) // 2], 3) if spans else None,
        "span_ratio_max": round(spans[-1], 3) if spans else None,
        "span_ratio_max_dim": max(ratios, key=lambda d: ratios[d]) if ratios else None,
    }


def _members(root: Path) -> list[Path]:
    return sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix())


def pack(export: Path, out: Path) -> dict[str, Any]:
    """Write `export` as an uncompressed, reproducible tar at `out`; returns its pin."""
    meta = json.loads((export / META_FILE).read_text(encoding="utf-8"))
    problems = verify_export(export, str(meta.get("export_id")), "part1")
    if problems:
        raise ExportRefused(problems)
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".part")
    with tarfile.open(partial, "w", format=tarfile.PAX_FORMAT) as tar:
        for path in _members(export):
            info = tarfile.TarInfo(path.relative_to(export).as_posix())
            info.size, info.mode, info.mtime = path.stat().st_size, 0o644, 0
            with path.open("rb") as f:
                tar.addfile(info, f)
    partial.replace(out)
    return {
        "export_id": meta["export_id"],
        "sha256": sha256(out),
        "bytes": out.stat().st_size,
        "samples": int(meta["counts"]["samples"]),
    }


def _safe_members(tar: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = tar.getmembers()
    bad = [
        m.name
        for m in members
        if not (m.isfile() or m.isdir()) or m.name.startswith("/") or ".." in Path(m.name).parts
    ]
    if bad:
        raise ExportRefused([f"tarball member {n!r} is not a plain relative path" for n in bad])
    return members


def fetch(
    tarball: Path,
    want_sha256: str,
    root: Path,
    export_id: str,
    split_dir: str,
    data_class: str | None = None,
) -> dict[str, Any]:
    """Copy `tarball` beside `root`, check it, unpack it into `root` and verify the export.

    `root` must be missing or empty: an export is never unpacked over another one.
    """
    if root.exists() and any(root.iterdir()):
        raise ExportRefused([f"{root} is not empty"])
    if not tarball.is_file():
        raise ExportRefused([f"{tarball} not found (is Drive mounted?)"])
    local = root.parent / f"{export_id}.tar"
    local.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tarball, local)
    got = sha256(local)
    if got != want_sha256:
        local.unlink()
        raise ExportRefused([f"{tarball} sha256 {got}, the plan pins {want_sha256}"])
    root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(local) as tar:
        for member in _safe_members(tar):
            tar.extract(member, root, set_attrs=False, filter="data")
    local.unlink()
    problems = verify_export(root, export_id, split_dir, data_class)
    if problems:
        raise ExportRefused(problems)
    meta = json.loads((root / META_FILE).read_text(encoding="utf-8"))
    return {
        "export_id": export_id,
        "tarball_sha256": got,
        "samples": int(meta["counts"]["samples"]),
        "frames": int(meta["counts"]["frames"]),
        "bytes": sum(p.stat().st_size for p in _members(root)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("command", choices=["pack", "verify"])
    parser.add_argument("--export", type=Path, required=True, help="the export root")
    parser.add_argument("--out", type=Path, help="pack: the tarball to write")
    parser.add_argument("--export-id", help="verify: the export_id to expect")
    parser.add_argument("--split-dir", default="part1")
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            if args.out is None:
                parser.error("pack needs --out")
            print(json.dumps(pack(args.export, args.out)))
            return 0
        if args.export_id is None:
            parser.error("verify needs --export-id")
        problems = verify_export(args.export, args.export_id, args.split_dir)
    except ExportRefused as refused:
        problems = refused.problems
    for problem in problems:
        print(f"FAIL {problem}", file=sys.stderr)
    if not problems:
        print(f"OK {args.export_id}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
