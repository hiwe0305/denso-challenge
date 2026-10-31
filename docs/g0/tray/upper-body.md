# Cổ tay và bàn tay của G1 trên decoupled WBC (DA-33 nhiệm vụ 2)

Planner đưa hai tư thế cổ tay vào `TeleopRetargetingIK` của decoupled_wbc thay cho luồng PICO, và đóng mở bàn tay Dex3 bằng một hệ số 0–1 ([plan DA-33](../../superpowers/plans/2026-10-31-da33-tray-synthetic.md) Task 2, [story DA-33](../../product/stories/DA-33-synthetic-s1-khay.md) AC 1). Quyết định đi kèm ở [decisions.md](decisions.md) D-12, D-13.

## Đường lệnh

| Bước | Thành phần | Ghi chú |
|---|---|---|
| 1 | `UpperBodyIK.solve(left, right)` (`flywheel_simple.wbc.upper_body`) | `TeleopRetargetingIK(robot_model, …, body_active_joint_groups=["arms"])`, `set_goal({"body_data": {"left_wrist_yaw_link": L, "right_wrist_yaw_link": R}, …})`, rồi `get_action()`: mục tiêu 31 khớp nhóm `upper_body` (eo 3, tay 14, bàn tay 14) |
| 2 | `hand_q(side, closure)` | Ghi đè 7 khớp mỗi bàn tay trong mục tiêu, bỏ qua IK bàn tay |
| 3 | `StandWalkController.action(sim_obs, navigate_cmd, wrist_pose, hand_closure)` | Đưa mục tiêu vào `G1DecoupledWholeBodyPolicy` như PICO; `last_record` giữ các trường bộ ghi teleop của SIMPLE đọc |

## Số đo (laptop RTX 3050, 31/10/2026, seed 0, mức 0)

| Phép | Kết quả |
|---|---|
| Khung của `body_data` | Khung hông (gốc của model G1 trong decoupled_wbc, không có floating base, 43 khớp). FK của model cho cổ tay trái (0,193; 0,187; 0,062) m, trùng vị trí cổ tay trong MuJoCo tính theo khung hông |
| Đi một vòng FK → IK, tư thế đứng | Lệch tay tối đa 0,056 rad với mục tiêu tư thế mặc định của IK; 0,003 rad khi neo posture ở khớp hiện tại |
| IK cả eo (nhóm `upper_body` như PICO), cổ tay trái tiến 10 cm | IK quay eo −0,26 rad (−15°), gập 0,14 rad; thân dưới xoay hông bù, lòng bàn tay gần như không tiến trong khung thế giới |
| IK chỉ tay (nhóm `arms`), cùng mục tiêu, sau 3 s đứng | Cổ tay tiến 7,9 cm trong khung IK, 6,5–7 cm trong khung thế giới; hông xê dịch ≤ 1 cm |
| Giữ cổ tay ở tư thế hiện tại qua IK | Cổ tay tụt 2,3 cm: PD của SIMPLE không bù trọng lực, IK neo ở tư thế đã võng |
| Hông ngay sau khi thả dây treo, không lệnh tay | Lùi 8,8 cm và chúi 4° trong 0,6 s đầu, rồi về −6 cm ở 1,5 s |
| Đóng bàn tay hết cỡ (`closure` 1) | Ngón trỏ và giữa đạt 66 % mục tiêu sau 0,5 s, 87 % sau 1 s, 95 % sau 2 s; ngón cái 97 % sau 1 s |

## Hệ quả cho planner

1. **Khung cổ tay là khung hông với eo thẳng**, tức khung thân cộng một độ lệch cố định. IK không dùng eo; Balance giữ eo quanh 0 (đo: yaw −0,004, roll −0,022, pitch 0,06 rad).
2. **Cổ tay võng 2–3 cm và chúi khoảng 10°** so với mục tiêu, vì `decoupled_wbc` trong SIMPLE chỉ có PD (`kp·(q* − q) − kd·dq`) cho thân. Dữ liệu teleop PICO cũng ghi dưới PD này. Planner đóng vòng theo vị trí lòng bàn tay đo được (pha REACH rời khi lệch ≤ 0,02 m), không tin mục tiêu mở vòng.
3. **Bàn tay mềm**: PD ngón `kp` 2,5–5, `kd` 1, nên đóng chậm (khoảng 2 s mới tới 95 %) và lực nắm nhỏ. Pha GRASP chờ tiếp xúc tay cầm, không chờ khớp đạt mục tiêu. Khay trượt khỏi tay là rủi ro chính của Task 4 (design mục 9).
4. **Chờ hông ổn định sau khi thả dây.** Hông còn trượt sau 0,5 s. Task 5 bắt đầu ghi khi hông chậm hơn 0,05 m/s, không theo một mốc thời gian cố định.

## Môi trường

`TeleopRetargetingIK` cần `pin-pink` và `qpsolvers[quadprog]`, hai phụ thuộc của decoupled_wbc mà `scripts/g0/setup_simple.sh` (S1-02) chưa cài vì cài decoupled_wbc bằng `--no-deps`. Máy laptop đã cài thêm `pin-pink==4.4.0`, `qpsolvers[quadprog]==4.13.0` (kéo theo `quadprog==0.1.13`, `loop-rate-limiters==1.2.0`); không gói nào bị nâng cấp. Máy `rtx3060` cần cùng hai gói; sửa `setup_simple.sh` nằm ngoài Phạm vi file của DA-33, nên đi bằng PR riêng.

`meshcat-shapes` (visualizer, cùng IPython, tornado, pyngrok) không cài: `upper_body.py` đặt một module giữ chỗ cho visualizer khi gói này vắng, vì visualisation luôn tắt.
