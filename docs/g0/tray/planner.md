# Planner kịch bản bê khay (DA-33 nhiệm vụ 3, 4)

Planner thay luồng PICO: mỗi bước đọc trạng thái cảnh, sinh lệnh đi, hướng, hai tư thế cổ tay và độ nắm cho `StandWalkController` ([plan DA-33](../../superpowers/plans/2026-10-31-da33-tray-synthetic.md) Task 3–4, [story DA-33](../../product/stories/DA-33-synthetic-s1-khay.md) AC 2, 3). Mã ở `flywheel_simple.tray.planner` và `flywheel_simple.tray.agent`; mọi giá trị ở `configs/sim/tray_planner.yaml`. Quyết định đi kèm ở [decisions.md](decisions.md) D-14 đến D-18.

## Kết quả (1/11/2026)

| Phép | Kết quả |
|---|---|
| Episode đầu thành công | Mức 0, seed 0: đủ 7 bước scorer, 22–24 s mô phỏng |
| Tỉ lệ thành công, cấu hình cuối | **44/48** (mức 0 seed 0, mức 1 seed 1–47), máy `rtx3060` |
| Thời gian một episode thành công | 24,4 s mô phỏng trung bình, tối đa 26,4 s (giới hạn 90 s) |
| Lỗi còn lại | 2 khay ngoài tầm với (`timeout:REACH`, seed 14, 42), 2 khay nghiêng (`L-TRAY-TILT`, seed 33, 38) |
| Tái lập | Cùng seed cho cùng quỹ đạo trên laptop và `rtx3060` (bộ điều khiển chạy theo đồng hồ điều khiển, D-17) |

## Cách cầm: ép hai mu bàn tay

Tay cầm là gờ đặc 12 × 4 × 2 cm, không có chỗ luồn ngón. Với khay 6 cm, mặt dưới gờ chỉ cách mặt bàn 4 cm: quét động học 16 tư thế kẹp gờ, tư thế nào ngón tay cũng chạm bàn A. Planner ép khay bằng mu hai bàn tay nắm lại (cổ tay xoay 180°), ép `squeeze` vào trong mặt ngoài gờ và nhấc bằng ma sát (D-18).

Hai tiếp xúc điểm hoạt động như một bản lề. Khay xoay dần quanh đường nối hai tiếp xúc cho tới khi trọng tâm treo dưới đường đó. Tiếp xúc lệch trọng tâm 1,4 cm cho góc cân bằng khoảng 19°, quá ngưỡng 15°, nên khay "trôi" tới lỗi khi lùi và quay. Vì vậy tiếp xúc phải nằm đúng trên trọng tâm; đây là tham số nhạy nhất:

| `grip_x` (m), góc xoay vào −20° | Thành công |
|---|---|
| 0,10 | 11/24 |
| 0,11 | **44/48** |
| 0,115 | 40/48 |
| 0,12 | 30/48 |
| 0,13 | 5/24 |

Góc xoay vào (`grasp_yaw_deg`) cũng nhạy: −15° nghiêng 46–47/48 episode, −25° kém hơn −20°.

## Những gì đã thử và kết quả

| Thay đổi | Ảnh hưởng đo được |
|---|---|
| Đứng gần bàn hơn (`standoff` 0,30 → 0,10 m) | Lòng bàn tay chỉ với được ~0,40 m trước hông; thân chạm bàn A khi cách mép ~0,065 m |
| Tiếp cận vuông góc với khay (hướng theo góc khay, căn giữa) | Cần cho mức 1: khay lệch 5 cm, xoay 10° |
| Giữ chỗ khi với tay (`keep_tol`, `keep_vx`) | Hông trượt lùi ~5 cm khi hai tay vươn ra |
| Mục tiêu GRASP cố định trong khung thế giới | Tay không đuổi theo khay khi hông trượt |
| Nhấc theo dốc (`lift_speed`), kết thúc LIFT theo khay đã nhấc | Bước nhảy 10 cm làm giật khay; tay mang tải chỉ lên được một phần mục tiêu |
| `squeeze` 0,03 → 0,05, `lift_height` 0,10 → 0,15 | Khay lên đủ trên 3 cm (trước đó 2,2 cm, `timeout:LIFT`) |
| Tốc độ lùi, quay, mang chậm hơn; lùi xa hơn; nhấc cao hơn | Không đổi số thành công: lỗi nghiêng là trôi tới cân bằng, không do va chạm hay gia tốc |
| Hạ: dịch hai tay theo sai số vị trí khay, chỉ nhả khi khay nằm phẳng | Hết `L-PLACE-POSE` (trước đó lệch tới 5,9 cm) |

## Việc còn mở

1. **Khay ngoài tầm với.** Khay cách mép 0,23–0,25 m (mức 1 dịch +5 cm) thì tay cầm xa quá tầm với khi robot đã đứng sát bàn. Hướng: cúi người bằng eo (pitch) khi với, hoặc giảm `tray_edge_offset` thêm (cần quyết định mới).
2. **Ma sát xoắn của tay cầm.** Hình học va chạm của tay cầm có `condim 4` nhưng hệ số ma sát xoắn chỉ 0,005: với lực ép ~15 N, mô-men cản quay chỉ ~0,08 N·m, so với ~0,25 N·m do trọng tâm lệch 2 cm. Một vùng tiếp xúc mu bàn tay thật cỡ 0,03. Tăng hệ số này giảm độ nhạy của `grip_x`; là thay đổi vật lý của task, cần quyết định.

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
