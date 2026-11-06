"""Draw one batch from a DA-18 export with Psi0's own stage 1 loader (DA-18 AC 2).

Runs in Psi0's environment (torch, torchcodec, scipy), from the Psi0 checkout at the
pinned commit, never in the workspace venv:

    cd $PSI0_ROOT && $PSI0_PYTHON <this file> <export_root> <stats.json> <out.json>

It builds `EgoDexDataset` exactly as `EgoDexDataConfig` does for the authors' recipe
(`upsample_rate` 3, `chunk_size` 1, delta actions, one image), normalizes with
`ActionStateTransform` (`bounds_q99`, key `egodex`), and writes the batch of
`loader_batch` for the train split and, if present, the val split (`test/`). The
loader writes `filelist_cache.pkl` into every part it scans; the probe removes the
ones it created, so the export stays as shipped.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd() / "src"))

from loader_batch import draw, record  # noqa: E402


def main(root: Path, stats: Path, out: Path) -> int:
    import psi
    from psi.config.transform import ActionStateTransform
    from psi.data.egodex.egodex_dataset import EgoDexDataset

    print(f"psi from {Path(psi.__file__).parent}")
    before = set(root.rglob("filelist_cache.pkl"))
    field = ActionStateTransform(
        stat_path=str(stats), action_norm_type="bounds_q99", stat_action_key="egodex"
    )
    batch = {}
    for val in (False, True):
        dataset = EgoDexDataset(
            data_root=str(root),
            upsample_rate=3,
            val=val,
            chunk_size=1,
            img_history_size=1,
            use_delta_actions=True,
        )
        index = {
            str(Path(f["hdf5"]).relative_to(root)): i for i, f in enumerate(dataset.data_files)
        }

        def get(path: str) -> dict:
            item = dataset.get_item(index[path])
            normalized = field({"actions": item["actions"].copy(), "states": item["states"]})
            return record(item, normalized["actions"])

        batch |= draw(list(index), get)
    for cache in set(root.rglob("filelist_cache.pkl")) - before:
        cache.unlink()
    out.write_text(json.dumps(batch, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{len(batch)} samples drawn by Psi0's EgoDexDataset into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3])))
