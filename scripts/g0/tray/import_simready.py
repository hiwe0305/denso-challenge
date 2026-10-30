"""Fetch the tray scene's render-only meshes from nvidia/simready-assets and convert them.

Downloads, at a pinned dataset revision, the USD geometry and albedo texture of
each asset below, checks every file against the sha256 Hugging Face records for
it, converts the mesh to OBJ (triangulated, faceVarying UVs kept) and the
texture to a 512 px PNG, and writes manifest.json for flywheel_simple.tray.visuals.
Collision never uses these meshes (see flywheel_simple/tray/mjcf.py).

Licence: CC-BY-4.0 (attribution in docs/g0/tray/assets.md). Output goes under
fwdata/, which is not committed.

    uv run --no-project --with usd-core --with pillow --with numpy \
        python scripts/g0/tray/import_simready.py --out fwdata/simple/tray/simready
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image
from pxr import Usd, UsdGeom

REPO = "nvidia/simready-assets"
REVISION = "4763fbfaa4f8e97658e68b57d01b4c86659e08b5"  # main on 2026-10-29
TEXTURE_PX = 512

# role, asset folder, albedo texture file name, fallback colour
ASSETS = [
    ("tray", "crate_green_a20", "T_Plastic_Green_A_Albedo.png", (0.30, 0.62, 0.35, 1.0)),
    ("table", "table_metal_stainless_a03", "T_Steel_A1_Albedo.png", (0.70, 0.72, 0.74, 1.0)),
    ("part", "factory_nut_m20_loose", "t_metal_steelScratched_a01_alb.png", (0.6, 0.6, 0.62, 1.0)),
    ("part", "consumable_bearing_ball_a01", "t_consumable_bearing_ball_a01_alb.png",
     (0.25, 0.25, 0.27, 1.0)),
]


def lfs_hashes(asset: str) -> dict[str, str]:
    url = f"https://huggingface.co/api/datasets/{REPO}/tree/{REVISION}/{asset}?recursive=true"
    with urllib.request.urlopen(url) as r:
        entries = json.load(r)
    return {e["path"]: e["lfs"]["oid"] for e in entries if e.get("lfs")}


def fetch(path: str, sha256: str) -> bytes:
    url = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{path}"
    with urllib.request.urlopen(url) as r:
        blob = r.read()
    got = hashlib.sha256(blob).hexdigest()
    if got != sha256:
        raise RuntimeError(f"{path}: sha256 {got} != recorded {sha256}")
    return blob


def usd_to_obj(usd_path: Path, obj_path: Path) -> tuple[list[float], list[float]]:
    """Merge every mesh of the stage into one OBJ in metres, z up; return its bounding box."""
    stage = Usd.Stage.Open(str(usd_path))
    if UsdGeom.GetStageUpAxis(stage) != UsdGeom.Tokens.z:
        raise RuntimeError(f"{usd_path}: up axis is not z")
    mpu = UsdGeom.GetStageMetersPerUnit(stage)
    verts, uvs, faces = [], [], []
    v_off = vt_off = 0
    for prim in stage.Traverse():
        if not prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(prim)
        xf = np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))
        pts = np.array(mesh.GetPointsAttr().Get(), dtype=float)
        pts = (np.c_[pts, np.ones(len(pts))] @ xf)[:, :3] * mpu
        counts = np.array(mesh.GetFaceVertexCountsAttr().Get())
        index = np.array(mesh.GetFaceVertexIndicesAttr().Get())
        st = UsdGeom.PrimvarsAPI(prim).GetPrimvar("st")
        if st and st.GetInterpolation() == UsdGeom.Tokens.faceVarying:
            per_corner = np.array(st.ComputeFlattened(), dtype=float)
        else:  # no usable UVs: map everything to one texel
            per_corner = np.zeros((len(index), 2))
        start = 0
        for n in counts:
            corners = range(start, start + n)
            for k in range(1, n - 1):  # fan triangulation
                tri = (corners[0], corners[k], corners[k + 1])
                faces.append([(index[c] + v_off + 1, c + vt_off + 1) for c in tri])
            start += n
        verts.append(pts)
        uvs.append(per_corner)
        v_off += len(pts)
        vt_off += len(per_corner)
    all_v, all_vt = np.vstack(verts), np.vstack(uvs)
    lines = [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in all_v]
    lines += [f"vt {u:.6f} {v:.6f}" for u, v in all_vt]
    lines += ["f " + " ".join(f"{v}/{t}" for v, t in face) for face in faces]
    obj_path.write_text("\n".join(lines) + "\n")
    return all_v.min(axis=0).tolist(), all_v.max(axis=0).tolist()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out: Path = args.out
    manifest = {"source": REPO, "revision": REVISION, "license": "CC-BY-4.0", "assets": []}
    for role, asset, texture_name, rgba in ASSETS:
        hashes = lfs_hashes(asset)
        folder = out / asset
        folder.mkdir(parents=True, exist_ok=True)
        geo = f"{asset}/simready_usd/payloads/geometries.usd"
        (folder / "geometries.usd").write_bytes(fetch(geo, hashes[geo]))
        bbox_min, bbox_max = usd_to_obj(folder / "geometries.usd", folder / "mesh.obj")
        tex = f"{asset}/simready_usd/Textures/{texture_name}"
        image = Image.open(io.BytesIO(fetch(tex, hashes[tex]))).convert("RGB")
        image.resize((TEXTURE_PX, TEXTURE_PX), Image.LANCZOS).save(folder / "albedo.png")
        manifest["assets"].append({
            "role": role, "asset": asset, "obj": f"{asset}/mesh.obj",
            "texture": f"{asset}/albedo.png", "rgba": list(rgba),
            "bbox_min": bbox_min, "bbox_max": bbox_max,
            "sha256": {geo: hashes[geo], tex: hashes[tex]},
        })
        size = np.subtract(bbox_max, bbox_min).round(4).tolist()
        print(f"{role:5s} {asset}: size {size} m")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"wrote {out / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
