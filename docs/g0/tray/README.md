# Task bê khay trên SIMPLE (DA-32)

G1 bê khay 6 linh kiện bằng hai tay từ bàn A sang vùng đích trên bàn B, chạy trong SIMPLE ở `sim_mode=mujoco` với decoupled WBC ([design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md), [story DA-32](../../product/stories/DA-32-task-be-khay.md)). Asset hiển thị ở [assets.md](assets.md), quyết định ở [decisions.md](decisions.md).

## Thành phần

| Mã | Việc |
|---|---|
| `configs/sim/tray.yaml` | Mọi kích thước, khối lượng, ma sát, dung sai, ngưỡng |
| `flywheel_simple.wbc` | Đứng và đi bằng decoupled WBC: `GR00T-WholeBodyControl-Balance.onnx` khi lệnh đi gần 0, `GR00T-WholeBodyControl-Walk.onnx` khi có lệnh đi; mục tiêu cổ tay qua `TeleopRetargetingIK` và đóng mở bàn tay Dex3 (DA-33, [upper-body.md](upper-body.md)) |
| `flywheel_simple.tray` | Cấu hình, hình học, MJCF, ngẫu nhiên hóa 3 mức, vị từ 7 bước, task và env id `simple/G1WholebodyTrayTransferTeleop-v0` |
| `flywheel_simple.tray.planner`, `configs/sim/tray_planner.yaml` | Máy pha của planner kịch bản theo 7 bước scorer (DA-33, D-15, [planner.md](planner.md)) |
| `flywheel_simple.tray.agent` | Chạy planner trong sim từ reset tới DONE hoặc ABORT (DA-33) |
| `flywheel_simple.tray.recorder` | Ghi episode của planner thành dataset LeRobot v2.1 cùng trường với teleop của SIMPLE, thêm tư thế khay, vị trí linh kiện, 7 cờ bước và khối `flywheel` trong `environment_config` (DA-33, D-22) |
| `flywheel_simple.tray.generate`, `scripts/g0/tray/generate.py` | Sinh episode hàng loạt theo shard song song (mỗi process một env), sổ lượt sinh `gen_log.jsonl` chỉ ghi thêm, QA tối thiểu, chạy lại cùng lệnh để tiếp tục (DA-33, D-23) |
| `flywheel_simple.tray.targets`, `generate.py --conditions` | Sinh nhắm lỗi cho vòng Failure → Data: chọn seed train có cảnh gần điều kiện lỗi nhất, ghi kế hoạch `targets.jsonl`, đánh dấu `purpose = failure_targeted` và `cluster_id` (DA-33, D-27) |
| `flywheel_simple.tray.replay_qa`, `scripts/g0/tray/replay_qa.py` | QA: phát lại episode đã ghi qua `replay-decoupled-wbc` của SIMPLE theo đồng hồ mô phỏng, so tư thế khay cuối với bản ghi; chạy song song theo shard (DA-33, D-24) |
| `flywheel_simple.tray.export`, `scripts/g0/tray/export_psi0.py` | Xuất episode qua cả hai bước QA sang định dạng Ψ₀ (LeRobot v2.1, action 36, state 32) bằng `postprocess_psi0_sonic.py` của SIMPLE, kèm `meta/action_layout.json` và `meta/flywheel_export.json` (DA-33, D-26) |
| `flywheel_simple.tray.release`, `scripts/g0/tray/release.py` | Xuất lô đã QA, ghi `release_manifest.json` (sha256 từng file, `release_hash`) và đặt tên thư mục `tray_s1_<release_hash[:12]>`; release đầu tiên ở [synthetic-s1.md](synthetic-s1.md) (DA-33) |
| `scripts/g0/tray/import_simready.py` | Tải và đổi mesh SimReady cho lớp hiển thị |
| `scripts/g0/tray/view_scene.py` | Ghi video camera đầu và video toàn cảnh |
| `scripts/g0/tray/measure_arm_pose.py` | Đo tư thế tay khi cầm khay (khuỷu so với vai và đường vai–cổ tay) và tỉ lệ thành công theo biến thể cấu hình, song song nhiều process (DA-33, D-25) |
| `scripts/g0/tray/wrist_jump.py`, `wrist_jump_sim.py`, `wrist_jump_fix_trial.py`, `video_writer_race.py` | Phân tích cờ `action_jump.arm` của release S1: bước nhảy khớp tay theo pha planner, sai số IK, độ bám của WBC; thử bản sửa giới hạn vận tốc của IK; test tranh chấp luồng của `VideoWriter` ([wrist-jump.md](wrist-jump.md)) |
| `scripts/g0/tray/measure_locomotion.py` | Đo tốc độ đi và quay của G1 (DA-33, [locomotion.md](locomotion.md)) |

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
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/generate.py \
    --out fwdata/simple/tray/gen/<lô> --n 130 --level 1 --seed-start 100 --workers 14
```

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/generate.py \
    --out fwdata/simple/tray/gen/<lô nhắm lỗi> --conditions <điều kiện lỗi>.jsonl --workers 14
```

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/replay_qa.py \
    --out fwdata/simple/tray/gen/<lô> --workers 14
```

```bash
PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/export_psi0.py \
    --batch fwdata/simple/tray/gen/<lô> --out fwdata/simple/tray/export/<lô>
```

```bash
PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/release.py \
    --batch fwdata/simple/tray/gen/<lô> --releases fwdata/releases
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
