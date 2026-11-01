# Planner kịch bản bê khay (DA-33 nhiệm vụ 3, 4)

Planner thay luồng PICO: mỗi bước đọc trạng thái cảnh, sinh lệnh đi, hướng, hai tư thế cổ tay và độ nắm cho `StandWalkController` ([plan DA-33](../../superpowers/plans/2026-10-31-da33-tray-synthetic.md) Task 3–4, [story DA-33](../../product/stories/DA-33-synthetic-s1-khay.md) AC 2, 3). Mã ở `flywheel_simple.tray.planner` và `flywheel_simple.tray.agent`; mọi giá trị ở `configs/sim/tray_planner.yaml`. Quyết định đi kèm ở [decisions.md](decisions.md) D-14 đến D-19.

## Kết quả (2/11/2026)

Mọi số đo trên cùng 48 episode (mức 0 seed 0, mức 1 seed 1–47), máy `rtx3060`. Cùng seed cho cùng quỹ đạo trên laptop và `rtx3060` (bộ điều khiển chạy theo đồng hồ điều khiển, D-17).

| Cách cầm | Thành công | Lỗi còn lại | Thời gian một episode thành công |
|---|---|---|---|
| **Kẹp bằng ngón tay Dex3 (mặc định, D-19)** | **40/48** | 4 `timeout:LIFT` (khay xa, seed 4, 10, 13, 34), 2 nghiêng, 1 `timeout:ARRIVE_B`, 1 đặt lệch | 27,4 s mô phỏng trung bình, tối đa 32,5 s |
| Ép mu hai nắm tay (D-18, cấu hình thay thế) | 44/48 | 2 ngoài tầm với, 2 nghiêng | 24,4 s, tối đa 26,4 s |

Hiếu chọn kẹp ngón (1/11/2026) vì dữ liệu có đóng mở bàn tay thật như dữ liệu teleop Ψ₀; ép mu tay giữ bàn tay nắm cố định suốt episode. Lần thử hỏng chỉ bị loại và ghi sổ, nên tỉ lệ 83 % không chặn việc sinh dữ liệu.

## Kẹp bằng ngón tay

Tay cầm là gờ đặc 12 × 4 × 2 cm. Với khay 9 cm (D-16), mặt dưới gờ cách mặt bàn 7 cm, đủ cho ngón luồn vào. Lòng bàn tay ngửa, cổ tay xoay −60°, nghiêng 30°, xoay vào 15°: ngón giữa móc dưới gờ, ngón cái kẹp mặt ngoài gờ. Khay lên khoảng 13 cm trên mặt bàn (ép mu tay chỉ được ~3 cm). Tay mở khi tiếp cận và chỉ khép khi tới gờ (`grasp_close_after`).

Từng bước đã đưa tỉ lệ từ 30/48 lên 40/48:

| Thay đổi | Thành công | Nguyên nhân đo được |
|---|---|---|
| Bộ thông số kẹp ngón đầu tiên | 30/48 | — |
| Nhả khi khay đã nằm trên B đủ `lower_settle` (1 s) | 31/48 | Tay giữ khay nghiêng 4–6°, khay không bao giờ "phẳng" |
| ARRIVE_B bước tới đích theo cả trước và ngang (`arrive_lat_tol` 4 cm) | 35/48 | CARRY dừng theo khoảng cách phía trước; lệch ngang tới 8,6 cm |
| Cân bằng khay: xoay hai cổ tay ngược độ chúi của khay (`level_gain` +0,05) | 37/48 | Khay chúi 10–14° quanh trục hai tay; tiếp xúc không trượt, tay xoay theo khay |
| Đích của ARRIVE_B lấy từ sai số khay khi vào pha; nhả tay đi xuống rồi ra (`release_dz`) | **40/48** | Khay xê dịch trong tay trên đường (5,7 cm); ngón móc dưới gờ còn chạm khi chỉ đi ra |

Đã thử và bỏ: kéo tay về phía thân khi nhấc (`lift_pull` 0,06 / 0,12 → 27 / 13 của 48), đứng gần bàn hơn (`standoff` 0,08 → nghiêng nhiều hơn), ngắm thấp hơn (`grasp_dz` −0,005 / −0,01 → 34 / 27), tiếp cận thấp hơn (`pregrasp_dz` 0 / −0,01), cân bằng ngược dấu (`level_gain` −0,05 → 1/48).

## Ép mu hai nắm tay (cấu hình thay thế)

Cổ tay xoay 180° cho mu bàn tay hướng vào khay, nắm tay lại, xoay vào −20°; hai mu tay ép `squeeze` 5 cm vào trong mặt ngoài gờ và nhấc bằng ma sát. Hai tiếp xúc điểm là một bản lề: khay trôi tới khi trọng tâm treo dưới đường nối hai tiếp xúc, nên tiếp xúc phải nằm đúng trên trọng tâm (lệch 1,4 cm cho góc cân bằng ~19°, quá ngưỡng 15°). Đổi lại bằng các khóa:

| Khóa | Giá trị |
|---|---|
| `grasp_roll_deg`, `grasp_pitch_deg`, `grasp_yaw_deg` | 180, 0, −20 |
| `grip_x`, `grip_y`, `grip_z` | 0,11, 0,02, 0 |
| `grasp_dy`, `squeeze` | 0,02, 0,05 |
| `hand_closure_open`, `grasp_close_after` | 1 (nắm tay), 0 |
| `arrive_lat_tol`, `level_gain` | 1,0 (tắt), 0 |

| `grip_x` (m), xoay vào −20° | Thành công |
|---|---|
| 0,10 | 11/24 |
| 0,11 | **44/48** |
| 0,115 | 40/48 |
| 0,12 | 30/48 |
| 0,13 | 5/24 |

## Chung cho hai cách cầm

| Thay đổi | Ảnh hưởng đo được |
|---|---|
| Đứng gần bàn hơn (`standoff` 0,30 → 0,10 m) | Lòng bàn tay chỉ với được ~0,40 m trước hông; thân chạm bàn A khi cách mép ~0,065 m |
| Tiếp cận vuông góc với khay (hướng theo góc khay, căn giữa) | Cần cho mức 1: khay lệch 5 cm, xoay 10° |
| Giữ chỗ khi với tay (`keep_tol`, `keep_vx`) | Hông trượt lùi ~5 cm khi hai tay vươn ra |
| Mục tiêu GRASP cố định trong khung thế giới | Tay không đuổi theo khay khi hông trượt |
| Nhấc theo dốc (`lift_speed`), kết thúc LIFT theo khay đã nhấc | Bước nhảy 10 cm làm giật khay; tay mang tải chỉ lên được một phần mục tiêu |
| Hạ: hai tay dịch khay theo sai số tới đích, bù liên tục (`place_gain`) | Tay mang tải kéo khay lùi khi hạ (6 cm ở seed 7) |

## Việc còn mở

1. **Khay xa ngoài tầm nhấc** (4/48, luôn là seed 4, 10, 13, 34): khay cách mép 0,23–0,25 m (mức 1 dịch +5 cm), tay vươn hết cỡ thì không nhấc nổi. Hướng: cúi người bằng eo khi với, hoặc giảm `tray_edge_offset` thêm (cần quyết định mới).
2. **Ma sát xoắn của tay cầm.** Hình học va chạm của tay cầm có `condim 4` nhưng hệ số ma sát xoắn chỉ 0,005. Một vùng tiếp xúc tay thật cỡ 0,03 sẽ giảm lỗi nghiêng của cả hai cách cầm; đây là thay đổi vật lý của task, cần quyết định.

## Chạy

Một episode có video và báo cáo:

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/view_scene.py --agent planner --seed 0 --level 0 --out fwdata/simple/tray/planner
```

Test sim của planner:

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray/test_agent.py -m sim -v
```

Quét tham số chạy song song trên `rtx3060` bằng một script nháp trong `fwdata/tune/` (không commit): mỗi tiến trình giữ một env, khoảng 3,3 GB RAM, tối đa khoảng 24 tiến trình trên máy 94 GB.
