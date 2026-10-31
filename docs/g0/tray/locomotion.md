# Đi và quay của G1 trong cảnh khay (DA-33 nhiệm vụ 1)

Số đo đi và quay của G1 trên decoupled WBC của SIMPLE ở `sim_mode=mujoco`, làm đầu vào cho planner ([plan DA-33](../../superpowers/plans/2026-10-31-da33-tray-synthetic.md) Task 1, [story DA-33](../../product/stories/DA-33-synthetic-s1-khay.md)). Quyết định đi kèm ở [decisions.md](decisions.md) D-10, D-11.

## Cách đo

| Trường | Giá trị |
|---|---|
| Máy | Laptop i5-11400H, RTX 3050 Laptop 4 GB, 31/10/2026; MuJoCo 3.3.6, SIMPLE `6d10628` |
| Env | `simple/G1WholebodyTrayTransferTeleop-v0`, seed 0, mức 0, `physics_dt` 0,005, `render_hz` 50 |
| Bộ điều khiển | `StandWalkController` (DA-32): thân trên giữ tư thế mặc định, thân dưới chạy `GR00T-WholeBodyControl-Balance.onnx` khi ‖(vx, vy, cờ quay)‖ < 0,1 và `Walk.onnx` khi lớn hơn |
| Lệnh | `NavIntegrator` (`flywheel_simple.wbc.navigate`) dựng `navigate_cmd = [vx, vy, vyaw, target_yaw]` như `PicoStreamer` |
| Mỗi phép | Reset mới, thả dây treo, rồi giữ lệnh 4 s (đi) hoặc tới khi hướng lệch ≤ 5° trong 0,5 s (quay) |
| Sàn | Đi và quay đo với hai bàn cách nhau 8 m (`corridor: 8.0`, cùng sàn, robot và vật lý); một phép đi trong cảnh mặc định 1,8 m |
| Lệnh chạy | `scripts/g0/tray/measure_locomotion.py`; log từng bước ở `fwdata/simple/tray/locomotion/` (không commit) |

`navigate_cmd[2]` không phải tốc độ quay. `G1GearWbcPolicy.get_action` chỉ đọc nó như cờ: khi |cờ| ≥ 0,1, thân dưới quay với tốc độ `(target_yaw − yaw) / 0,5` rad/s (chặn ở 1 rad/s) về hướng tuyệt đối `target_yaw`; khi |cờ| < 0,1 nó không quay và không giữ hướng. Vì thế `NavIntegrator.command` có thêm `limit_yaw`: `target_yaw` dừng ở hướng đích còn cờ vẫn bật, nên robot tự sửa về đúng hướng.

## Đi thẳng, 4 s

"Ổn định" là tốc độ trung bình trong 2 s cuối. "Trễ" là thời gian tới khi đạt nửa tốc độ ổn định. "Giữ hướng" là cờ quay 0,1 với `target_yaw` cố định ở hướng xuất phát.

| vx lệnh (m/s) | Giữ hướng | Quãng 4 s (m) | Ổn định (m/s) | Ổn định / lệnh | Trễ (s) | Lệch ngang (m) | Hướng cuối (°) |
|---|---|---|---|---|---|---|---|
| 0,1 | không | 0,193 | 0,079 | 0,79 | 0,00 | −0,037 | −2,5 |
| 0,2 | không | 0,486 | 0,162 | 0,81 | 0,72 | −0,045 | −3,5 |
| 0,3 | không | 0,812 | 0,250 | 0,83 | 0,54 | −0,032 | −3,4 |
| 0,4 | không | 1,164 | 0,344 | 0,86 | 0,46 | −0,069 | −0,9 |
| 0,5 | không | 1,537 | 0,449 | 0,90 | 0,42 | −0,083 | −0,8 |
| −0,1 | không | −0,479 | −0,099 | 0,99 | 0,00 | +0,018 | −5,1 |
| −0,25 | không | −1,021 | −0,256 | 1,02 | 0,12 | −0,153 | −0,3 |
| −0,4 | không | −1,588 | −0,428 | 1,07 | 0,20 | −0,130 | −0,8 |
| 0,1 | có | 0,190 | 0,078 | 0,78 | 0,08 | −0,025 | +0,2 |
| 0,2 | có | 0,478 | 0,161 | 0,80 | 0,72 | −0,032 | 0,0 |
| 0,3 | có | 0,798 | 0,245 | 0,82 | 0,54 | −0,010 | −1,6 |
| 0,4 | có | 1,150 | 0,338 | 0,85 | 0,46 | −0,022 | −0,1 |
| 0,5 | có | 1,513 | 0,438 | 0,88 | 0,42 | −0,026 | +1,0 |
| −0,1 | có | −0,448 | −0,096 | 0,96 | 0,00 | +0,006 | −1,4 |
| −0,25 | có | −0,998 | −0,252 | 1,01 | 0,10 | −0,004 | −0,4 |
| −0,4 | có | −1,588 | −0,429 | 1,07 | 0,20 | −0,119 | +0,5 |

Mọi phép giữ độ thẳng thân (trục z của `torso_link`) ≥ 0,998, không ngã. Bảng là lần chạy thứ hai; quãng 4 s của hai lần chạy cùng phép lệch nhau tới 2,9 cm (vx = −0,25, không giữ hướng).

Trong cảnh mặc định, đi tới bàn A ở vx = 0,3 chỉ được 0,057 m trong 4 s.

## Quay tại chỗ 180°

| Tốc độ tích phân `vyaw` (rad/s) | Quay được (°) | Thời gian Walk.onnx chạy (s) | Hông xê dịch (m) |
|---|---|---|---|
| 0,3 | 179,0 | 11,3 | 0,055 |
| 0,5 | 177,6 | 7,3 | 0,084 |
| 1,0 | 178,8 | 4,6 | 0,091 |

Thời gian gồm 0,5 s giữ trong dung sai 5°. Trong cảnh mặc định (cách bàn A 0,45 m), quay 180° ở 0,5 rad/s cũng đạt dung sai 10°, hông xê dịch ≤ 0,2 m (test `test_turns_in_place_by_pi`).

## Nguyên nhân và hệ quả cho planner

1. **Bị bàn A chặn, không phải đi chậm.** Ở tư thế thân trên mặc định, đầu ngón tay G1 ở cao 0,76 m và vươn trước hông khoảng 0,35 m, thấp hơn mặt bàn 0,85 m. Robot spawn cách mép bàn A 0,45 m, nên sau khoảng 6 cm ngón trỏ hai tay chạm thân bàn (`left/right_hand_index_1_link` với `table_a`) và hông dừng ở x = 0,505 m. Đây là nguyên nhân của số đo 31/10/2026: đi tới 0,28 m trong 9,1 s, đi lùi 0,78 m trong 3,8 s. Planner phải đưa tay lên trên mặt bàn trước khi tiến, hoặc chỉ tiến khi tay đã ở tư thế với.
2. **Walk.onnx đi tới chậm hơn lệnh.** Tốc độ ổn định khi đi tới bằng 0,79–0,90 lệnh và trễ khoảng 0,5–0,7 s; đi lùi bám lệnh (0,96–1,07). Đây là hành vi của policy GR00T, không sửa được trong package của đội (D-10). Planner điều khiển theo quãng đo được, không theo thời gian × lệnh.
3. **Cần bật cờ quay khi đi.** Không có cờ, thân dưới không giữ hướng: hướng trôi tới 5° và đi lùi lệch ngang tới 0,15 m. Có cờ 0,1, hướng giữ trong ±1,6°; lệch ngang khi đi tới ≤ 0,03 m, đi lùi nhanh vẫn tới 0,12 m. Bật cờ cũng giữ Walk.onnx chạy ở vx nhỏ.
4. **Quay 180° mất 4,6–7,3 s.** Tốc độ quay thực do sai số hướng đặt (P-gain 2 s⁻¹, chặn 1 rad/s), nên `vyaw` chỉ quyết định `target_yaw` chạy nhanh bao nhiêu. Giá trị đầu của planner: `vyaw` 0,5 rad/s, dung sai 5°.
5. **Mỗi process chỉ một env sống.** SIMPLE giữ một Task và một Robot cho mỗi uid trong cả process (D-11).
