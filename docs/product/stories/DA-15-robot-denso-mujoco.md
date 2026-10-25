# DA-15 · Robot DENSO tương đương, cảnh trạm và task khay → máy trên MuJoCo

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026 theo design 25/10/2026) |
| Người làm | Hưng |
| Story PRD | Story mới của [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.2 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G0` · `area:sim` |
| Sprint | S1–S2. MJCF tối thiểu (nhiệm vụ con 1) trong 3 ngày đầu Sprint 1 |
| Ước lượng | 30 giờ (khoảng 25–35, ước lượng của SM) |
| Phụ thuộc | Không. Chặn thật DA-16, DA-17, DA-23, S1-06, S1-09, DA-12 ở phần chạy trên robot; các story đó code trên MJCF tối thiểu trong lúc chờ |

## Story

Là kỹ sư simulation, tôi muốn có robot DENSO tương đương chạy task khay → máy trong MuJoCo, để đội thu teleop, phát lại dữ liệu, chạy các nhánh thí nghiệm và demo mà không chờ DENSO hay SIMPLE.

## Tiêu chí chấp nhận

1. MJCF tối thiểu (nhiệm vụ con 1): đế, cột nâng, hai tay, hai gripper, camera đỉnh cột; mọi kích thước sinh từ một file tham số trong `configs/embodiments/` như `denso_mm_proxy` của [design 23/10](../../superpowers/specs/2026-10-23-data-pipeline-and-failure-eval-design.md) mục 3.1; giá trị chưa có thông số ghi là giả định kèm nguồn (hình vẽ trong `docs/challenge/`).
2. Cảnh trạm: khay có linh kiện, máy có đồ gá, theo layout hình vẽ; dung sai đồ gá, khối lượng linh kiện, ma sát ghi trong file tham số, không nới để task dễ hơn (design 25/10 mục 2, phản mục tiêu).
3. Env task khay → máy: `reset(seed)` theo vector điều kiện của design 25/10 mục 8; vị từ thành công (`sim_success`) viết tách khỏi scorer (03 ADR-21); `control_spec` theo nhóm `base`, `lift`, `arm_l`, `arm_r`, `gripper_l`, `gripper_r`, `head`, đệm 36 chiều.
4. `DensoMujocoSim` thỏa `SimulatorAdapter` của 03 mục 5.2 và qua contract suite của S1-08 (`flywheel.testing`).
5. Planner S1: IK cộng planner cho robot DENSO làm được task từ ít nhất 80% của 20 điều kiện Level 0; ghi tỉ lệ thành công và thời gian mỗi episode.
6. Lệnh chấm độ giống so với hình vẽ theo design 23/10 mục 3.1; báo "chấm so với hình vẽ", không ghi đã đạt 95% so với robot thật.
7. Video headless một episode planner, lưu ngoài git. Ghi chi phí vào `docs/g0/ledger/DA-15.csv`, cột theo [docs/g0/README.md](../../g0/README.md).

## Nhiệm vụ

- [ ] 1. MJCF tối thiểu từ file tham số, mở PR riêng (AC 1)
- [ ] 2. Cảnh trạm, khay, linh kiện, máy, đồ gá (AC 2)
- [ ] 3. Env task: `reset(seed)`, vị từ thành công, `control_spec` (AC 3)
- [ ] 4. `DensoMujocoSim` và contract suite (AC 4)
- [ ] 5. Planner S1 trên 20 điều kiện (AC 5)
- [ ] 6. Chấm độ giống so với hình vẽ, ghi Decision (AC 6)
- [ ] 7. Video, sổ chi phí (AC 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-mujoco/pyproject.toml`, `packages/flywheel-mujoco/README.md`
- `packages/flywheel-mujoco/src/flywheel_mujoco/robot/`, `packages/flywheel-mujoco/src/flywheel_mujoco/scene/`, `packages/flywheel-mujoco/src/flywheel_mujoco/env/`, `packages/flywheel-mujoco/src/flywheel_mujoco/planner/`, `packages/flywheel-mujoco/src/flywheel_mujoco/assets/`, `packages/flywheel-mujoco/src/flywheel_mujoco/__init__.py`
- `packages/flywheel-mujoco/tests/robot/`, `packages/flywheel-mujoco/tests/env/`, `packages/flywheel-mujoco/tests/planner/`
- `configs/embodiments/denso_mm_proxy.yaml`
- `uv.lock`: chỉ tạo lại bằng lệnh uv lock sau khi rebase (07 mục 3.2 điểm 5)
- `docs/g0/denso-mujoco.md`, `docs/g0/ledger/DA-15.csv`

## Ghi chú cho người làm

- Nguồn: [design 25/10](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 3, 8, 11.2; design 23/10 mục 3.1, 7.1; 03 mục 5.2, 5.4 (bản 0.5), ADR-18, ADR-21.
- Nhiệm vụ con 1 mở PR riêng sớm để người khác code trên phần này (design 25/10 mục 10.1); trong lúc chờ duyệt, làm tiếp nhiệm vụ con sau, không tạo nhánh từ nhánh chưa merge.
- Lõi `flywheel` không import `mujoco`; mọi thứ cụ thể nằm trong `flywheel-mujoco` (bất biến kiến trúc).
- Thư mục `teleop/` (DA-16), `replay/` (DA-17), `eval/` (DA-23) của cùng package thuộc story khác; story này tạo khung package và không sửa các thư mục đó.
- Tay kiểu Kinova Gen3 là phán đoán từ hình vẽ, chưa xác nhận; khi BTC gửi URDF/USD thì chuyển sang MJCF và chấm lại, ghi Decision.
- Thông số chưa có ghi kèm chữ "giả định"; mọi kết quả trên robot này ghi "trên tham số giả định".

## Kiểm thử

- Unit test: cùng seed cho cùng layout; vị từ thành công đúng trên 3 trạng thái dựng tay (đạt, linh kiện lệch đồ gá, linh kiện rơi).
- Contract suite của S1-08 chạy với `DensoMujocoSim`.
- Người bình luận chạy lại planner trên 5 điều kiện và ra tỉ lệ cùng bậc.

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Châu (task, scorer), Long (contract suite)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design 25/10/2026 mục 11.2 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
