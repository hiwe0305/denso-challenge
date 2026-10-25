# DA-15 · Robot DENSO tương đương, cảnh và task khay → máy trên MuJoCo

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa theo design chia làn cùng ngày) |
| Người làm | Hưng |
| Làn | Simulation |
| Story PRD | Story mới của [design MuJoCo 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) và [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G0` · `area:sim` |
| Sprint | S1–S2. MJCF tối thiểu (nhiệm vụ con 1) trước 28/10 |
| Ước lượng | 32 giờ (khoảng 27–38, ước lượng của SM) |
| Phụ thuộc | Không phụ thuộc người khác. PR `chore-restructure` (07 mục 3.6, hết 27/10) tạo khung package `denso-sim`, `flywheel-mujoco`; trong lúc chờ làm file tham số robot và MJCF trong `assets/` |

## Story

Là kỹ sư simulation, tôi muốn có robot DENSO tương đương chạy task khay → máy trong MuJoCo, để đội thu teleop, kiểm dữ liệu, chạy các nhánh thí nghiệm và demo mà không chờ DENSO hay SIMPLE.

## Tiêu chí chấp nhận

1. MJCF tối thiểu: đế, cột nâng với **một bàn trượt mang cả hai vai**, hai tay, hai gripper hai ngón, camera đỉnh cột; mọi kích thước sinh từ `ros2_ws/src/denso_description/config/robot_params.yaml` (nguồn duy nhất, design chia làn mục 6.2); giá trị chưa có thông số ghi `# giả định` kèm nguồn (hình vẽ DENSO, design chia làn mục 11).
2. Khay theo câu Q-K: mặc định dựng **hai khay trên đế robot** như hình vẽ, có cờ cấu hình chuyển sang khay của trạm; máy có đồ gá. Dung sai đồ gá, khối lượng, ma sát trong `configs/sim/`, không nới cho dễ.
3. Camera theo câu Q-L: camera đỉnh cột bật; camera cổ tay khai trong MJCF, bật hay tắt bằng cấu hình.
4. Env khay → máy trong `denso_sim.task`: `reset(seed)` theo vector điều kiện (design MuJoCo mục 8); vị từ thành công tách khỏi scorer (03 ADR-21); `denso_sim.timing` chạy theo đồng hồ sim hoặc đồng hồ thật và chèn độ trễ cho eval bất đồng bộ.
5. `DensoMujocoSim` trong `flywheel-mujoco` thỏa `SimulatorAdapter`, gồm `replay()` hai chế độ (động học: đặt state từng khung; động lực học: áp action từ state đầu) và `materialize_conditions`; qua contract suite của `flywheel.testkit`; đăng ký qua entry point.
6. Planner S1 trong `denso_sim.planner` làm được task ở ít nhất 80% của 20 điều kiện Level 0.
7. Chấm độ giống so với hình vẽ theo design 23/10 mục 3.1; ghi "chấm so với hình vẽ". Video headless một episode planner, ngoài git. Ghi chi phí vào `docs/g0/ledger/DA-15.csv`, cột theo [docs/g0/README.md](../../g0/README.md).

## Nhiệm vụ

- [ ] 1. File tham số và MJCF tối thiểu, mở PR riêng (AC 1)
- [ ] 2. Khay, máy, đồ gá, camera theo cấu hình (AC 2, 3)
- [ ] 3. Env task, vị từ thành công, `timing` (AC 4)
- [ ] 4. `DensoMujocoSim`, `replay()`, contract suite (AC 5)
- [ ] 5. Planner S1 trên 20 điều kiện (AC 6)
- [ ] 6. Chấm độ giống, video, sổ chi phí (AC 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/denso-sim/src/denso_sim/robot/`, `packages/denso-sim/src/denso_sim/scene/`, `packages/denso-sim/src/denso_sim/task/`, `packages/denso-sim/src/denso_sim/control/`, `packages/denso-sim/src/denso_sim/planner/`, `packages/denso-sim/src/denso_sim/assets/`, `packages/denso-sim/src/denso_sim/timing.py`, `packages/denso-sim/src/denso_sim/__init__.py`
- `packages/denso-sim/pyproject.toml`, `packages/denso-sim/README.md`, `packages/denso-sim/tests/`
- `packages/flywheel-mujoco/src/flywheel_mujoco/`, `packages/flywheel-mujoco/pyproject.toml`, `packages/flywheel-mujoco/tests/`
- `ros2_ws/src/denso_description/config/robot_params.yaml`
- `configs/embodiments/denso.yaml`, `configs/sim/`
- `uv.lock`: chỉ tạo lại bằng lệnh uv lock sau khi rebase (07 mục 3.2 điểm 5)
- `docs/g0/denso-mujoco.md`, `docs/g0/ledger/DA-15.csv`

## Ghi chú cho người làm

- Nguồn: [design MuJoCo](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 3, 8; [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) mục 4.3, 6, 11; design 23/10 mục 3.1, 7.1; 03 ADR-18, ADR-21, ADR-23.
- `denso_sim` không import `flywheel` hay `rclpy` (luật import); `flywheel-mujoco` là chỗ duy nhất nối hai bên.
- `denso_sim.teleop` thuộc DA-16; phần còn lại của `ros2_ws/` thuộc DA-24.
- Hình vẽ robot không đưa vào repo (repo công khai, câu Q-N); mô tả ở design chia làn mục 11.

## Kiểm thử

- Cùng seed cho cùng layout; vị từ thành công đúng trên 3 trạng thái dựng tay (đạt, lệch đồ gá, rơi).
- Contract suite chạy với `DensoMujocoSim`; `replay()` động học một episode mẫu của testkit cho state trùng từng khung.
- Người bình luận chạy lại planner 5 điều kiện, ra tỉ lệ cùng bậc.

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Châu (vị từ thành công), Thông (`replay()`)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design MuJoCo 25/10/2026 mục 11.2 | PO (Hiếu) |
| 25/10/2026 | Viết lại theo design chia làn: đường dẫn `denso-sim`, `flywheel-mujoco`; thêm `replay()` từ DA-17, `timing` từ DA-23, khay và camera theo hình vẽ | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
