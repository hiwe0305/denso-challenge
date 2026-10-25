# DA-24 · Workspace ROS 2 và môi trường sim

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa theo design chia làn cùng ngày) |
| Người làm | Hưng |
| Làn | Simulation |
| Story PRD | Story mới của [design MuJoCo 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) và [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G0` · `area:sim` |
| Sprint | S1–S2 |
| Ước lượng | 30 giờ (khoảng 25–35, ước lượng của SM) |
| Phụ thuộc | DA-15 nhiệm vụ con 1 (file tham số, MJCF). Không chờ ai khác |

## Story

Là kỹ sư simulation, tôi muốn một workspace ROS 2 và môi trường Docker theo chuẩn dự án robotics, để ai cũng dựng được sim trên laptop, teleop qua ROS và có giao diện giống robot thật.

## Tiêu chí chấp nhận

1. Image `docker/ros2-sim/Dockerfile`: ROS 2 Jazzy, MuJoCo ghim phiên bản, colcon, rosdep; cài `denso-sim` từ workspace bằng `pip install -e`; `.devcontainer/` trỏ tới image; chạy được trên máy không GPU (render headless).
2. Package theo chuẩn: `denso_description` (xacro sinh URDF từ `robot_params.yaml`, meshes, RViz), `denso_interfaces` (msg, srv), `denso_mujoco` (node sim chạy `denso-sim`, xuất `/clock`, `/joint_states`, ảnh, TF), `denso_control` (cấu hình ros2_control), `denso_bringup` (`sim.launch.py`).
3. Quy ước: REP-103, REP-105; topic namespace `/denso/…`; `use_sim_time`; tham số trong YAML của package; phụ thuộc khai trong `package.xml`.
4. Chọn bridge MuJoCo–ROS 2 (plugin `ros2_control` có sẵn hay node tự viết); ghi `Decision`.
5. Bảng topic thực tế khớp bảng ở design chia làn mục 6.4; đề xuất bản chốt cho Hiếu đưa vào `flywheel.contracts` (DA-25).
6. Job CI `ros`: `colcon build`, `colcon test` trong image khi PR chạm `ros2_ws/` hoặc `packages/denso-sim/`; `ros2_ws/README.md` ghi cách build, chạy, bảng topic.

## Nhiệm vụ

- [ ] 1. Image Docker và devcontainer (AC 1)
- [ ] 2. `denso_description`, `denso_interfaces` (AC 2)
- [ ] 3. `denso_mujoco`, chọn bridge (AC 2, 4)
- [ ] 4. `denso_control`, `denso_bringup`, quy ước (AC 2, 3)
- [ ] 5. Bảng topic cho DA-25 (AC 5)
- [ ] 6. Job CI `ros`, README (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `ros2_ws/src/denso_description/`, `ros2_ws/src/denso_interfaces/`, `ros2_ws/src/denso_mujoco/`, `ros2_ws/src/denso_control/`, `ros2_ws/src/denso_bringup/`
- `ros2_ws/README.md`
- `docker/ros2-sim/`, `.devcontainer/`
- `.github/workflows/ros-ci.yml`
- `docs/g0/ros2-sim.md`, `docs/g0/ledger/DA-24.csv`

## Ghi chú cho người làm

- Nguồn: [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) mục 6; 03 ADR-23.
- `denso_teleop` và `record.launch.py`, `teleop.launch.py` thuộc DA-16.
- `robot_params.yaml` do DA-15 tạo; story này chỉ đọc nó.
- Workflow CI mới (`ros-ci.yml`) là file dùng chung; Long bình luận.

## Kiểm thử

- `colcon test` xanh trong image; `launch_testing` khởi động `sim.launch.py` và thấy `/clock`, `/joint_states`.
- Một người khác dựng devcontainer trên laptop không GPU theo README.

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Long (CI), Thông (bảng topic)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design chia làn | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
