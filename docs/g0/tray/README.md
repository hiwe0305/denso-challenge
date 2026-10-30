# Task bê khay trên SIMPLE (DA-32)

G1 bê khay 6 linh kiện bằng hai tay từ bàn A sang vùng đích trên bàn B, chạy trong SIMPLE ở `sim_mode=mujoco` với decoupled WBC ([design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md), [story DA-32](../../product/stories/DA-32-task-be-khay.md)). Asset hiển thị ở [assets.md](assets.md), quyết định ở [decisions.md](decisions.md).

## Thành phần

| Mã | Việc |
|---|---|
| `configs/sim/tray.yaml` | Mọi kích thước, khối lượng, ma sát, dung sai, ngưỡng |
| `flywheel_simple.wbc` | Đứng và đi bằng decoupled WBC: `GR00T-WholeBodyControl-Balance.onnx` khi lệnh đi gần 0, `GR00T-WholeBodyControl-Walk.onnx` khi có lệnh đi |
| `flywheel_simple.tray` | Cấu hình, hình học, MJCF, ngẫu nhiên hóa 3 mức, vị từ 7 bước, task và env id `simple/G1WholebodyTrayTransferTeleop-v0` |
| `scripts/g0/tray/import_simready.py` | Tải và đổi mesh SimReady cho lớp hiển thị |
| `scripts/g0/tray/view_scene.py` | Ghi video camera đầu và video toàn cảnh |

## Lệnh

Môi trường SIMPLE dựng theo [env-simple.md](../env-simple.md).

```bash
uv run --no-project --with usd-core --with pillow --with numpy \
    python scripts/g0/tray/import_simready.py --out fwdata/simple/tray/simready
```

```bash
uv run pytest packages/flywheel-simple
```

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray packages/flywheel-simple/tests/wbc -m sim
```

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/view_scene.py --seed 1000000 --level 2 --seconds 6 --walk 0.2
```

## Số đo (laptop RTX 3050 4 GB, 31/10/2026, một lần mỗi phép)

| Phép | Kết quả |
|---|---|
| Reset đầu của env khay | 9,5–9,8 s |
| Bước env (50 Hz, gồm vật lý, WBC, render 2 camera 640 × 360) | Trung vị 11,7–13,8 ms |
| Thả dây treo | Bước 85–86; hông 0,747 m; như task hai bàn |
| Đứng 2 s, đi `vx = 0,25` 2 s, đứng 2 s | Model Balance chạy 100/100 bước khi đứng; Walk chạy 97/100 bước khi đi (3 bước chuyển do lệnh nội suy); đi được 0,12 m, hông ≥ 0,736 m |
| Cảnh tĩnh 30 s | Khay xê dịch 2,04 mm, linh kiện 0,00 mm, xuyên tối đa 0,57 mm |

Video: `fwdata/simple/tray/view/head.mp4`, `overview.mp4` (không commit).
