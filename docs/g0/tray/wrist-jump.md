# Bước nhảy action cổ tay của synthetic S1 và lỗi x264 của bộ ghi (DA-33, 4/11/2026)

QA của DA-03 ([PR #86](https://github.com/hiwe0305/denso-challenge/pull/86)) gắn cờ `action_jump.arm` cho cả 102 episode của release `tray_s1_0d84cc87b1e5`. Lệch lớn nhất là ở `wrist_yaw` (chiều 20 và 27 của action 36 chiều), vượt ngưỡng p99.9 của psi-data (0,0869 rad mỗi bước), luôn quanh bước 205–211. Trang này ghi nguyên nhân, bằng chứng, bản sửa đã thử và việc cần Hiếu quyết. Phần cuối là lỗi crash x264 của bộ ghi mà DA-34 gặp khi sinh lô pool v2. Release: [synthetic-s1.md](synthetic-s1.md). Quyết định trước đó: D-20, D-24, D-25 ở [decisions.md](decisions.md).

## Kết luận

| Câu hỏi | Trả lời |
|---|---|
| Bước nhảy ở pha nào | REACH: cổ tay xoay từ tư thế sẵn sàng (−45°, 10°, 0°) sang tư thế đỡ ngửa (−90°, 10°, 0°, D-25). Ở seed 1000, REACH chạy bước 180–218 và GRASP bắt đầu ở bước 219. Hai cụm khác cùng cơ chế: APPROACH_A nâng tay ở bước 22–36 (102/102 episode, giống hệt nhau) và LOWER–RELEASE ở bước 1247–1594 (44/102). |
| Nhảy ở lệnh hay ở khớp đo | Ở lệnh. Mục tiêu cổ tay Cartesian của planner vẫn mượt theo min-jerk, quay tối đa 2,08 rad/s. Lời giải IK theo khớp thì vọt tới 7–14 rad/s. Khớp đo được bám theo nhưng trễ 3–4 bước và thấp hơn đỉnh của lệnh 0,1–0,23 rad. |
| Bản chất | Lỗi của nhãn action, không phải chuyển động nhanh có chủ ý. Tư thế đỡ ngửa đẩy `wrist_roll` vào giới hạn khớp (±1,972 rad) và `wrist_pitch` lên gần 90° (1,54 rad), ở đó trục roll và yaw gần trùng nhau. IK pink của decoupled_wbc không có giới hạn vận tốc thực sự, nên khi roll rời giới hạn, cánh tay đổi cấu hình trong null space với tốc độ tối đa. Trong lúc đó vị trí và hướng cổ tay trong lệnh vẫn nằm trên mục tiêu. |
| Sửa nhỏ nhất | **[Đề xuất]** Đặt `VelocityLimit` cho QP của IK sao cho mỗi khớp tay đi tối đa 0,08 rad mỗi bước điều khiển (`flywheel_simple.wbc.upper_body`, 0,533 rad/s theo đơn vị của IK). Trên 40 seed train mới chạy cặp: 39/40 thành công, so với 36/40 của bản hiện tại; bước nhảy tối đa 0,08 rad; không còn bước nào vượt ngưỡng; REACH không chậm đi. |
| Phải sinh lại không | Có, nếu nhận bản sửa: cả release 102 episode và lô pool v2 (`s1-pool-1103`, cùng planner `da33-planner-4+cfg.815b822a`, 60/60 episode đã quét vượt ngưỡng). **Chưa sinh lại, chờ Hiếu.** Tập cha S2 của DA-35 cũng bị, nhẹ hơn (111/129 episode). |
| Ngưỡng QA riêng cho nguồn này | Không đề xuất: bước nhảy là lỗi nhãn, nới ngưỡng chỉ che lỗi. |
| Crash x264 ở seed 1349 | Không xác định theo seed: chạy riêng seed 1349 không crash, và hai bản sao đúng trạng thái resume của shard 1 cũng không. Lỗi là tranh chấp luồng trong `VideoWriter` của decoupled_wbc, lộ ra khi máy tải nặng. Đã tái hiện bằng một test không cần sim. Sửa trong bộ ghi của DA-33, chi tiết ở mục cuối. |

## Bước nhảy nằm ở đâu

`scripts/g0/tray/wrist_jump.py` đọc release và lô gốc. Nó chia mỗi episode thành đoạn theo lệnh đã ghi (đối chiếu với log pha của planner, chạy lại bằng `wrist_jump_sim.py`), rồi đo trong từng cụm bước vượt ngưỡng:

- tốc độ quay của mục tiêu cổ tay `action.eef`;
- tốc độ khớp của lệnh;
- sai số IK: FK của khớp lệnh so với mục tiêu;
- tốc độ của khớp đo.

Mô hình động học là G1 của decoupled_wbc. Chạy lại seed 1000 cho đúng `action` của episode 0 tới từng bit.

| Đoạn | Episode | Bước | Bước vượt ngưỡng | Nhảy lớn nhất (rad/bước) | Khớp nhảy nhiều nhất | Mục tiêu quay tối đa (rad/s) | `wrist_pitch` lệnh tối đa (rad) |
|---|---|---|---|---|---|---|---|
| APPROACH_A nâng tay | 102 | 22–36 | 12 | 0,119 (mọi episode như nhau) | `left_wrist_roll` | 1,96 | 1,26 |
| REACH, GRASP | 102 | 190–426 | 5–26, trung vị 7 | 0,189 trung vị, 0,141–0,283 | `left_wrist_yaw` 49, `right_wrist_yaw` 29, `right_elbow` 19 | 1,94–2,08 | 1,49 trung vị, tối đa 1,54 |
| LOWER, RELEASE, RETREAT | 44 | 1247–1594 | 1–8 | 0,126 trung vị, tối đa 0,208 | `right_shoulder_yaw`, `left_elbow` | ≤ 1,08 | 1,52 |

Trong mọi cụm, `wrist_roll` của lệnh nằm ở giới hạn 1,972 rad. Đoạn APPROACH_A giống hệt nhau ở mọi episode vì robot luôn bắt đầu từ cùng tư thế đứng, trong khoảng `raise_at`. Planner nâng tay ngay từ đầu rồi mới đi.

Episode 0 (seed 1000), tay trái. "Lệnh" là action, "đo" là state, đơn vị rad; tay phải đối xứng.

| Bước | roll lệnh | pitch lệnh | yaw lệnh | yaw đo | Mục tiêu quay (rad/s) | Sai số IK (°) |
|---|---|---|---|---|---|---|
| 195 | −1,972 | 1,226 | 0,646 | 0,595 | 1,75 | 7,1 |
| 200 | −1,972 | 1,272 | 0,787 | 0,659 | 1,97 | 6,0 |
| 205 | −1,972 | 1,402 | 1,104 | 0,807 | 1,63 | 3,4 |
| 207 | −1,972 | 1,473 | 1,276 | 0,906 | 1,37 | 2,1 |
| 209 | −1,972 | 1,531 | 1,430 | 1,029 | 1,07 | 0,9 |
| 210 | −1,972 | 1,510 | 1,457 | 1,094 | 1,11 | 0,3 |
| 211 | −1,925 | 1,366 | 1,280 | 1,161 | 0,89 | 0,1 |
| 212 | −1,877 | 1,231 | 1,091 | 1,221 | 0,60 | 0,2 |
| 213 | −1,855 | 1,119 | 0,917 | 1,236 | 0,56 | 0,1 |
| 215 | −1,842 | 0,988 | 0,651 | 1,165 | 0,22 | 0,0 |
| 218 | −1,845 | 0,926 | 0,479 | 0,947 | 0,06 | 0,0 |
| 220 | −1,871 | 0,911 | 0,474 | 0,812 | 0,03 | 0,0 |

Đọc bảng:

- **Bước 195–209:** roll kẹt ở giới hạn, IK bám mục tiêu bằng pitch và yaw. IK chậm hơn mục tiêu tới 7° và khoảng 5 cm.
- **Bước 210–218:** mục tiêu gần như đứng yên, sai số IK về 0. Lệnh quay yaw ngược lại 1 rad trong 8 bước, pitch giảm 0,6 rad, roll rời giới hạn. Cổ tay trong lệnh vẫn đúng mục tiêu: đây là chuyển động trong null space.

Năm episode đầu, đỉnh của yaw lệnh và yaw đo trong REACH:

| Episode (seed) | Dim | Bước nhảy lớn nhất | Nhảy (rad/bước) | Đỉnh lệnh (bước, rad) | Đỉnh đo (bước, rad) | Bước đo lớn nhất (rad/bước) |
|---|---|---|---|---|---|---|
| 0 (1000) | 20 | 211 | 0,189 | 210, 1,457 | 213, 1,236 | 0,076 |
| 0 (1000) | 27 | 210 | 0,186 | 209, −1,431 | 213, −1,222 | 0,065 |
| 1 (1022) | 20 | 210 | 0,145 | 209, 1,416 | 212, 1,267 | 0,061 |
| 2 (1066) | 27 | 226 | 0,188 | 225, −1,425 | 228, −1,276 | 0,060 |
| 3 (1088) | 27 | 212 | 0,137 | 215, −0,020 | 239, −0,090 | 0,086 |
| 4 (1110) | 20 | 209 | 0,226 | 208, 1,491 | 211, 1,260 | 0,078 |

Bảng đủ 26 bước (195–220) của năm episode này nằm trong output của `wrist_jump.py`.

## Nguyên nhân

IK thân trên là `TeleopRetargetingIK` của decoupled_wbc (pink 4.4.0, `BodyIKSolver`):

- Mỗi bước điều khiển nó chạy 3 lần `q += v · dt` với `dt` = 0,05.
- Trọng số posture của `wrist_yaw` là 0,1, nên đây là khớp rẻ nhất.
- Sau mỗi lần nó gọi `clip_configuration`.
- pink mặc định có `VelocityLimit` lấy từ URDF (cổ tay 22–37 rad/s). Theo đơn vị của IK, giới hạn này cho phép tới 3,3–5,5 rad mỗi bước, nên không bao giờ chặn.

Tư thế đỡ ngửa (D-25) cần cẳng tay xoay quá giới hạn roll của cổ tay. Vì vậy roll nằm ở giới hạn từ lúc nâng tay, và pitch lên tới 88°. Ở đó roll và yaw là hai trục gần trùng nhau (điểm kỳ dị kiểu gimbal của cổ tay roll–pitch–yaw). Khi mục tiêu chậm lại ở cuối pha xoay, task posture kéo roll ra khỏi giới hạn. Phần hướng mà roll trả lại được yaw, pitch, khuỷu và vai bù trong cùng một bước, nên các khớp này nhảy 0,1–0,28 rad mỗi bước.

Planner không làm sai Cartesian: các blend min-jerk của D-20 vẫn đúng. psi-data đi qua cùng IK nhưng tay người không vào vùng này. Trung vị của bước tay lớn nhất mỗi episode ở psi-data là 0,02–0,03 rad (99 episode, chỉ 1 episode vượt 0,0869). Ở release khay là 0,15–0,26 rad.

## WBC có bám theo không

Khớp đo được bám theo hình dạng cú xoay nhưng chậm hơn và lệch đỉnh:

- trễ 3–4 bước (60–80 ms);
- đỉnh thấp hơn lệnh 0,1–0,23 rad;
- tốc độ của `wrist_yaw` đo tối đa 3,65 rad/s trung vị (2,7–5,1), tức khoảng 0,07 rad/bước, ngang ngưỡng QA.

Robot vì vậy thật sự xoay cổ tay khoảng 1 rad đi rồi về trong khoảng 0,4 s ngay trước GRASP. Chuyển động ở trên không, chưa chạm khay, nên episode vẫn thành công và QA phát lại vẫn trùng từng bit (D-24).

Sai số hướng cổ tay đo được so với mục tiêu (FK của khớp đo) có độ lệch tĩnh trung vị 22,4°, do tay võng dưới trọng lực và khung eo. Trong cụm REACH sai số này dao động 8–28°, không vượt ra ngoài dải tĩnh nhiều. Vì vậy trang này mô tả độ bám bằng khớp, không bằng góc Cartesian.

Ảnh hưởng tới train: Ψ₀ học action theo khớp. Nhãn có những cú vọt 7–14 rad/s mà robot không thực hiện, và cấu hình sau cú vọt phụ thuộc vào lịch sử warm start của IK. Policy sẽ học nhãn đó. Khi eval, action dự đoán đi thẳng vào WBC như lúc phát lại.

## Bản sửa đã thử

`scripts/g0/tray/wrist_jump_fix_trial.py` chạy planner và WBC của lô sinh, không ghi dữ liệu. Cùng 40 seed train mới (300000–300039, mức 1, chưa dùng ở đâu) chạy ở ba biến thể, trên `rtx3060`, mỗi worker một scope `systemd-run MemoryMax=6G`:

| Biến thể | Thành công | Hỏng | Nhảy tay lớn nhất (rad/bước) | Bước vượt 0,0869 | REACH (s, trung bình / tối đa) |
|---|---|---|---|---|---|
| Hiện tại | 36/40 | 3 `timeout:LIFT`, 1 `L-ONE-HAND` | 0,177 trung vị, tối đa 0,252 | 26 trung vị | 0,81 / 1,70 |
| Chặn lệnh sau IK 0,08 rad/bước | 34/40 | 2 `timeout:REACH`, 3 `L-TRAY-TILT`, 1 `timeout:RELEASE` | 0,08 | 0 | 0,80 / 0,86 |
| **Giới hạn vận tốc trong QP của IK, 0,08 rad/bước** | **39/40** | 1 `L-ONE-HAND` | 0,08 | 0 | 0,81 / 1,98 |

So từng seed giữa bản hiện tại và giới hạn trong IK: 4 seed chỉ thành công với bản sửa, 1 seed chỉ thành công với bản hiện tại. Với 40 seed, chênh lệch này chưa có ý nghĩa thống kê (McNemar chính xác p ≈ 0,38). Kết luận được là bản sửa không làm giảm tỉ lệ thành công; chưa kết luận được là nó tăng.

Chặn lệnh sau IK thì để lệnh lệch khỏi trạng thái warm start của IK. Hai lần REACH không hội tụ trong 5 s (seed 300011 và 300034) là do đó, nên phương án này bị loại.

0,08 rad/bước (4 rad/s) gần tốc độ mà khớp đo thực sự đạt (trung vị 3,65 rad/s) và dưới ngưỡng QA 0,0869. Các chuyển động min-jerk bình thường không chạm giới hạn này.

Sửa đề xuất **[Đề xuất]**:

- `UpperBodyIK` nhận `max_joint_step` (rad mỗi bước điều khiển) và đặt `model.velocity_limit = VelocityLimit(model, min(URDF, max_joint_step / (num_step_per_frame · dt)))` trên model của `BodyIKSolver`.
- `TrayAgent` truyền giá trị từ khóa mới `arm_step_max: 0.08` trong `tray_planner.yaml`.
- Tăng `PLANNER_VERSION` lên `da33-planner-5`.
- Thêm test: trên một episode sim, không bước nào của lệnh tay vượt 0,08.

Đường PICO ảo của DA-35 (`tray/pico/agent.py`) gọi thẳng `TeleopRetargetingIK`, không đi qua `UpperBodyIK`, nên bản sửa này không đổi dữ liệu S2. Nhưng S2 cũng có lỗi này: operator ảo cầm khay bằng cùng tư thế đỡ ngửa. Trong tập cha `parents-1103b` (129 episode), 111 episode vượt 0,0869; trung vị của bước tay lớn nhất mỗi episode là 0,099 rad, tối đa 0,181 (nhẹ hơn S1). Đặt cùng giới hạn vận tốc cho IK của `tray/pico/agent.py` là việc của DA-35.

Việc tiếp theo, theo quyết định ngày 4/11/2026 (mục cuối):

1. Sửa mã như trên trong một PR của DA-33 (nhiệm vụ 11).
2. Sau khi PR được merge: chạy smoke khoảng 20 seed train trên `rtx3060` bằng mã đã merge, rồi chạy QA của DA-03. Đạt khi không còn cờ `action_jump.arm` và tỉ lệ thành công tương đương 39/40 của lần thử.
3. Chỉ một lô: DA-34 sinh lại kho bằng supervisor của nó, 610 lượt, mức 1, seed 1000–1609. Release S1 cắt từ kho này, không sinh lô 130 lượt riêng: [tray.md](../../he/tray.md) mục 7 đã gộp seed 1000–1129 vào kho ("cả kho là một lô, một release"), và sim cùng WBC tất định (mục 8.1).
   - Lô sinh vào một `--out` mới. Sinh tiếp chỉ bỏ qua các seed đã có trong sổ, không xét phiên bản planner. Vì vậy `generate()` và `scripts/g0/tray/generate.py` từ chối thư mục đã có dòng của planner khác.
   - `export_psi0`, nên cả `release.py`, từ chối lô có episode đã ghi thuộc hai phiên bản planner.
4. QA phát lại, lọc, release, rồi chạy lại QA của DA-03. Nghiệm thu: không còn cờ `action_jump.arm`. Ngưỡng lọc giữ nguyên như đã chốt (nghiêng ≤ 10°, trôi ≤ 20 mm), không chỉnh lại trên kho mới.

## Lỗi x264 của bộ ghi (seed 1349, lô pool v2)

Hiện tượng (sổ của DA-34, `s1-pool-1103/supervise.log`):

- 01:45–01:53 ngày 4/11, các worker shard 0, 1, 2 chết với `rc=139` (SIGSEGV).
- Shard 1 chết lặp lại ở seed tiếp theo của nó, 1349: ba lần SIGSEGV, một lần `rc=134` với `x264_8_frame_push_unused: Assertion frame->i_reference_count > 0 failed`, kèm "internal error (invalid MB type)".
- Lần khởi động thứ năm có vẻ bị treo: video `episode_000051.mp4` được ghi xong lúc 01:55, nhưng tới lúc DA-34 dừng lô (02:07) sổ vẫn không có dòng của seed 1349.
- Scope 26 GB của lô không có `oom_kill` (đỉnh 22,9 GB), nên không phải lỗi hết bộ nhớ.

| Kiểm tra | Kết quả |
|---|---|
| Seed 1349 chạy riêng, dataset mới, máy tải khoảng 45 | Không crash. Episode hỏng `L-PLACE-POSE` ở 1758 bước nên bị `discard`; video đóng bình thường. |
| Bản sao đúng shard 1 (51 episode, cả file `episode_000051.mp4` còn sót), chạy tiếp bằng lệnh của supervisor | Không crash, qua 1349 rồi sang 1355. |
| Bản sao đó, bỏ file mp4 còn sót | Không crash. |
| Kích thước frame, số frame | 360 × 640 như psi-data; 1758 frame không có gì đặc biệt. Không phải ca biên của encoder. |
| `video_writer_race.py`, `VideoWriter` gốc, 50 frame mỗi video rồi `stop()` ngay | 3/3 lần chạy SIGSEGV trước video thứ 20. faulthandler cho thấy hai luồng cùng ở trong `stream.encode` của một encoder: luồng nền ở `video_writer.py:71` (frame cuối) và luồng chính ở `stop() → _flush_stream()` (dòng 76). |
| Một lần chạy `VideoWriter` gốc khác của cùng test | Treo: process đứng ở `futex_wait` 14 giờ, không ghi thêm video (thấy và dừng lúc 16:46 ngày 4/11). Cùng kiểu treo với shard 1 của DA-34. |
| Cùng test, `JoinedVideoWriter` (bản sửa) | 200/200 video, không lần gọi chồng nào, RSS tăng 66 MB. |
| Cùng test, `SyncVideoWriter` (encode ngay trong luồng sim) | 200/200 video, RSS tăng 69 MB; frame thật tốn 9,9 ms mỗi frame dưới tải 41, tức khoảng +20 % thời gian mỗi bước. |

Nguyên nhân nằm trong `third_party/decoupled_wbc/data/video_writer.py` của SIMPLE:

- `stop()` chỉ đợi `queue.empty()`. Hàng đợi rỗng nghĩa là luồng nền đã lấy frame cuối ra, chưa có nghĩa là đã encode xong.
- Ngay sau đó `stop()` flush encoder và đóng file từ luồng gọi, trong khi luồng nền có thể vẫn đang encode.
- libx264 không chịu được hai luồng cùng dùng một encoder. Kết quả là SIGSEGV, assert về đếm tham chiếu frame, hoặc treo.
- Máy tải nặng (load 50–59 trên 64 lõi) làm luồng nền chậm và khoảng hở này rộng ra. Vì thế các crash dồn vào lúc tải cao nhất và không lặp lại khi chạy riêng.
- Luồng nền không bao giờ thoát (`while True`, `frame is None: continue`), nên nó giữ writer cùng encoder cũ suốt đời process. Mức rò rỉ chưa đo được vì bản gốc crash trước khi đo.

Sửa đề xuất **[Đề xuất]**:

- `tray/recorder.py` thay `create_video_writer` của `Gr00tDataExporter` bằng `JoinedVideoWriter`: cùng giao diện, một luồng encode; `stop()` gửi sentinel và `join()` luồng trước khi flush; `cancel()` cũng vậy.
- Không sửa mã của SIMPLE.
- Giữ được việc encode song song với sim, không tốn thêm 10 ms mỗi bước như writer đồng bộ.
- `tray/pico/session.py` của DA-35 cũng ghi qua `Gr00tDataExporter`, nên nên dùng chung writer này.

Trong lúc chờ sửa: supervisor của DA-34 (khởi động lại shard theo seed) vẫn hoàn tất được lô. Một episode crash đúng lúc lưu sẽ được sinh lại cùng seed, và video còn sót bị ghi đè.

## Lệnh

Chạy trên `rtx3060` trong thư mục làm việc có SIMPLE venv. Đường dẫn dưới đây là của lần chạy này.

```bash
fwdata/simple/.venv/bin/python scripts/g0/tray/wrist_jump.py --release fwdata/releases/tray_s1_0d84cc87b1e5 --out fwdata/analysis/wrist_jump
```

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/wrist_jump_sim.py --seeds 1000 1022 --out fwdata/analysis/wrist_jump_sim
```

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/wrist_jump_fix_trial.py --variant ik_velocity --seeds 300000 300001 300002 300003 300004 --out fwdata/analysis/wrist_jump_trial/ik_velocity-0.jsonl
```

```bash
fwdata/simple/.venv/bin/python -X faulthandler scripts/g0/tray/video_writer_race.py --videos 200 --writer joined
```

Kết quả thô (không commit) ở `rtx3060:~/denso-da33-wristjump/`: `out/` (phân tích 102 episode), `sim/` (log pha seed 1000 và 1022), `trial/` (120 lượt thử), `race-*.log`, `x264/` (các bản sao tái hiện seed 1349).

## Đã chốt 4/11/2026

Hiếu nhận cả ba đề xuất (D-28 trong [decisions.md](decisions.md)):

1. Nhận giới hạn vận tốc trong IK (0,08 rad/bước) và sinh lại; không train trên dữ liệu có bước vọt, không che bước vọt khi train.
2. Nhận `JoinedVideoWriter` cho bộ ghi.
3. DA-35 tự đặt cùng giới hạn cho IK của operator ảo, gộp vào nhiệm vụ 10 của DA-35; DA-33 không sửa `tray/pico/`.

## Quyết định và bản sửa (4/11/2026)

Nhiệm vụ 11 của DA-33 làm theo đề xuất 1 và 2:

- `UpperBodyIK(robot_model, max_joint_step)` và `StandWalkController(robot, max_joint_step)` đặt `VelocityLimit` cho QP của IK: min(URDF, `max_joint_step` / (`num_step_per_frame` · `dt` · `amplify_factor`)). Không truyền thì giữ hành vi cũ, nên các đường khác (test WBC, script đo) không đổi.
- `TrayAgent` truyền `arm_step_max: 0.08` từ `tray_planner.yaml`; `PLANNER_VERSION` lên `da33-planner-5` (cấu hình hiện tại ghi `da33-planner-5+cfg.4e2a4505`).
- `tray/recorder.py` ghi video qua `JoinedVideoWriter`, gắn vào exporter bằng lớp con của `Gr00tDataExporter`; không sửa SIMPLE.

Bằng chứng trên `rtx3060` (bản sao nhánh ở `~/denso-da33-ikfix`, scope `MemoryMax`):

| Kiểm tra | Kết quả |
|---|---|
| Test sim (`test_video_writer.py`, `test_agent.py`, `test_recorder.py`, `tests/wbc`) | 25/25 qua |
| Test mới `test_arm_commands_move_at_most_arm_step_max_per_step`, seed 1 mức 1, có và không có giới hạn | Không giới hạn: bước tay lớn nhất 0,177, 24 bước vượt 0,0869, nên test bắt được lỗi. Có giới hạn: 0,08, không bước nào vượt. Cả hai đều thành công. |
| `generate.py` 6 lượt, seed 300000–300005, 2 worker | 5/6 thành công, 5/5 qua QA tối thiểu, hỏng 1 `L-ONE-HAND` (300004). Kết quả và số bước từng seed trùng lần thử `ik_velocity` ở trên. Mỗi episode ghi có số frame video bằng số dòng parquet; bước tay lớn nhất trong `action` đã ghi là 0,08. |

Việc còn lại là bước 2–4 của mục "Việc tiếp theo" ở trên. `tray/pico/session.py` của DA-35 vẫn ghi qua writer gốc; dùng `JoinedVideoWriter` ở đó là việc của DA-35.

## Kiểm chứng planner-5 trên 50 seed mới (4/11/2026)

Hiếu yêu cầu sửa dữ liệu tới khi đạt rồi mới train. Mẫu là 50 seed train chưa dùng ở đâu (300040–300089), mức 1, đồng hồ sim, trên `rtx3060`, chạy bằng mã của PR này. "planner-4" là cùng mã với `arm_step_max` 1000: giới hạn khi đó là giới hạn URDF, đúng `VelocityLimit` mặc định của pink. Kiểm lại: seed 1000 và 1022 chạy như vậy cho 1423 và 1358 bước, trùng sổ của release planner-4. Mỗi bản sinh 50 lượt (`generate.py`, 6 worker), QA phát lại, release, `fw data ingest`, report phát lại động học của DA-17 (`replay-1@cf2515483a8c`), `fw data qa --replay` (`qa-1@fb6ddaf9f48c`) và `flywheel_psi0.tray.quality`.

| Đo | planner-4 | planner-5 |
|---|---|---|
| Thành công (`check_success`), cùng 50 seed | 45/50 | 44/50 |
| Hỏng | 2 `L-ONE-HAND`, 1 `L-PLACE-POSE`, 1 `timeout:LIFT`, 1 `timeout:ARRIVE_B` | 2 `timeout:REACH`, 1 `L-ONE-HAND`, 1 `L-PLACE-POSE`, 1 `L-TRAY-TILT`, 1 `timeout:ARRIVE_B` |
| QA phát lại (D-24) | 45/45, lệch khay 0,0 mm | 44/44, lệch khay 0,0 mm |
| DA-17, phát lại động học | 2 episode có issue `joint_mapping`, cả hai ở `right_hand_middle_0_joint` (0,455 và −0,112, sàn 0,5) | 0 issue |
| DA-03 QA | 0 pass, 43 flag, 2 reject; `action_jump.arm` ở 45/45 | **44 pass, 0 flag, 0 reject** |
| Nghiêng khay khi mang, độ (trung vị / p90 / max) | 7,51 / 10,02 / 12,95 | 6,99 / 10,96 / 14,00 |
| Linh kiện trôi cuối episode, mm (trung vị / p90 / max) | 11,19 / 17,14 / 24,64 | 10,87 / 20,32 / 25,66 |
| Qua bộ lọc đã chốt (nghiêng ≤ 10°, trôi ≤ 20 mm) | 39/45 (87 %) | 32/44 (73 %) |
| Khay rơi khi nhả, m/s (trung vị / chậm nhất / nhanh nhất) | −0,47 / −0,25 / −0,72 | −0,46 / −0,20 / −0,76 |

Đọc bảng:

- **Dữ liệu planner-5 đạt QA.** Không còn cờ `action_jump.arm`, không reject, không còn cờ nào cần giải thích. Cùng seed với planner-4 thì cả 45 episode bị cờ. Dòng `stats_json.states` (D4, lệch 4,3e-4 ở `states.mean[2]`) là lỗi cấp dataset đã biết của `stats.json` từ script của tác giả, có cả ở psi-data và release cũ, việc của DA-02 ([data-pipeline.md](../data-pipeline.md) mục 3.3).
- **Thành công ngang nhau.** 44 so với 45; 4 seed chỉ thành công với planner-5, 5 seed chỉ với planner-4. Hai lỗi mới là `timeout:REACH` (300041, 300044): với giới hạn, lời giải IK của tay trái lệch đích 80–110 mm suốt 5 s của REACH, còn pitch cổ tay phải dao động 0,70 ↔ 1,10 rad. Cánh tay đi chậm qua đúng vùng gần suy biến mà bản cũ nhảy qua trong vài bước, và không về kịp. Lỗi này chỉ làm mất lượt sinh, không đưa lỗi vào dữ liệu. Lần thử trên 40 seed trước (300000–300039) không có ca nào như vậy.
- **Hiệu suất lọc thấp hơn: 73 % so với 87 %.** Trên 40 seed mà cả hai bản cùng thành công, 11 seed chỉ qua lọc với planner-4 và 4 seed chỉ qua với planner-5; kiểm định dấu cho p ≈ 0,12, nên chưa chắc là thật. Phần chênh nằm ở lúc đặt khay, không phải lúc mang. Trước giây cuối của cửa sổ mang, planner-5 còn ổn hơn (nghiêng p90 7,1° so với 8,1°). Trong giây cuối (khay chạm bàn B), p90 là 11,0° so với 9,9°, 6 so với 4 episode vượt 10°. Độ trôi cuối episode cũng tăng ở đuôi: 6 so với 1 episode vượt 20 mm. **[Giả định]** Khi hạ khay, hai tay bị giới hạn tốc độ nên không xuống đều nhau. Ngưỡng lọc giữ nguyên như đã chốt. Theo tỉ lệ của mẫu này, lô 610 lượt cho khoảng 610 × 0,88 × 0,73 ≈ 390 episode qua lọc, so với khoảng 470 nếu giữ tỉ lệ của planner-4 (ước lượng).
- **Khay rơi khi nhả không đổi.** Đây là thiết kế của D-25: nhả khi khay còn cách bàn 3,5 cm. Thử hạ sát hơn (`lower_tray_clear` 0,015) trên cùng seed thì tốc độ rơi trung vị giảm còn −0,32 m/s, nhưng thành công giảm từ 42/48 xuống 40/48 và thêm 2 `timeout:LOWER`. Như vậy không an toàn, nên giữ nguyên. Lý do cũ của D-25 vẫn đúng: hạ sát hơn thì cổ tay dưới gờ chạm bàn trước khay.
- **Episode kiểu `ep_7f0a5ca73db8348e` không còn trong mẫu.** Đó là seed 1098 của release cũ, với tương quan 0,349 ở `right_hand_middle_0_joint`. Release cũ có 1/102 episode dưới 0,5 và 2/102 dưới 0,7; mẫu planner-5 thấp nhất là 0,752. Cùng 50 seed, planner-4 sinh 2 episode như vậy, planner-5 không sinh episode nào. Bản thân seed 1098 với planner-5 hỏng `L-ONE-HAND`, nên không còn episode đó.
- **Hạ tầng.** Một shard của lần sinh planner-5 bị khởi động lại vì `EGL_NOT_INITIALIZED` (D-23). Ba shard của QA phát lại bị lỗi `Offscreen framebuffer is not complete` khi GPU 12 GB đã đầy 11,6 GB (do job khác), phải chạy lại. Lỗi này ghi thành `not_replayed` với mã thoát 0, nên trông như QA trượt. Không lần nào crash x264.
  - Nguyên nhân: CLI phát lại của SIMPLE (`replay_decoupled_wbc.py`) bắt mọi exception, in `An error occurred` rồi thoát 0. Episode nào không có kết quả phát lại thì bị chấm `not_replayed`.
  - Đã sửa sau #103: `replay_qa()` raise `ReplayIncomplete` và không ghi `replay_qa.jsonl`, nên export từ chối shard đó cho tới khi phát lại xong.
  - `scripts/g0/tray/replay_qa.py` thoát 1 và ghi tên shard vào `unjudged_shards` của `replay_summary.json`.

Chi phí: khoảng 13,4 giờ-worker (sinh 2,2; thử nghiệm không ghi 7,2; QA phát lại 2,4; chẩn đoán và kiểm 0,4; QA và lọc dưới 0,1). Kết quả thô ở `rtx3060:~/denso-da33-ikfix/val/` và `~/denso-da33-ikfix/fwroot/`.

## Thử planner-6 (D-29, 5/11/2026): không đạt

Planner-6 (`da33-planner-6+cfg.c39d02b1`, nhánh `DA-33-planner-6`, chưa merge) chạy cùng 50 seed train 300040–300089 với planner-5, mức 1, đồng hồ sim. Chuỗi kiểm giống hệt: sinh, QA phát lại, `fw data ingest`, phát lại động học DA-17, QA DA-03, quality. **Kết luận: trượt 2 trong 3 mức nhận của D-29, nên không nhận planner-6. Planner-5 v2 đóng băng như kế hoạch.** Không chạy thêm thử nghiệm nào sau khi biết kết quả.

| Mức nhận (D-29) | planner-5 | planner-6 | Đạt |
|---|---|---|---|
| QA DA-03: 0 cờ, 0 reject | 44 pass | 36 pass, **2 reject** (`replay_kinematic`) | Không |
| `check_success` ≥ 44/50 | 44/50 | **38/50** | Không |
| Qua lọc đã chốt (nghiêng ≤ 10°, lệch ≤ 20 mm) ≥ 85 % số thành công | 32/44 (72,7 %) | 33/38 (86,8 %) | Có |

Số đo khác (trung vị / p90 / lớn nhất trên các lượt thành công):

| Số đo | planner-5 | planner-6 |
|---|---|---|
| Nghiêng khay lúc mang (°) | 6,99 / 10,96 / 14,00 | 7,96 / 9,94 / 12,40 |
| Lệch vật cuối lượt (mm) | 10,87 / 20,32 / 25,66 | 9,37 / 15,38 / 23,93 |
| `drop_vz_min` trung vị (m/s) | −0,459 | −0,402 |
| Hỏng theo nhãn | `timeout:REACH` 2, `L-ONE-HAND` 1, `L-PLACE-POSE` 1, `L-TRAY-TILT` 1, `timeout:ARRIVE_B` 1 | `L-TRAY-TILT` 7, `L-PLACE-POSE` 2, `timeout:REACH` 2, `timeout:LOWER` 1 |
| QA phát lại (sai số khay) | 44/44 (0,0 mm) | 38/38 (0,0 mm) |
| Phát lại động học DA-17: số issue | 0 | 2: `joint_limit` 1, `joint_mapping` 1 |
| `wrist_roll` đo vượt giới hạn URDF, lớn nhất | 0 (không lượt nào vượt) | 3,67 mrad (seed 300076; 4 lượt vượt > 0, 1 lượt vượt dung sai 1,93 mrad) |
| Khoảng cách nhỏ nhất của `wrist_roll` tới giới hạn, trung vị theo lượt | 26,5 mrad | 17,4 mrad |

Theo seed: 34 seed thành công ở cả hai. Planner-6 cứu được 4 seed mà planner-5 hỏng, gồm cả 2 lượt `timeout:REACH` của planner-5 (300041, 300044), nhưng làm hỏng 10 seed mà planner-5 làm được. Trong 34 seed chung, 7 seed chỉ planner-6 qua lọc, 4 seed chỉ planner-5 qua lọc.

Hai lượt bị reject:

- **seed 300076, `joint_limit`.** `right_wrist_roll_joint` đo vượt giới hạn 3,67 mrad ở khung 1267–1311 (25,3–26,2 s, lúc hạ khay), so với dung sai 1,93 mrad. Lời giải IK đích của đoạn chuyển khớp nằm đúng trên giới hạn `wrist_roll`, và PD bám theo thì vượt một chút. Test sim `test_posture_changes_go_through_joint_transits` cũng thấy điều này ở seed 1: đích nâng tay của tay trái có `roll_margin` 0 và sai số tư thế 0,0177 (ngưỡng của test 0,01). Test đó trượt, nhưng chuỗi vẫn chạy tiếp để có số đo.
- **seed 300046, `joint_mapping`.** `right_hand_middle_0_joint` có tương quan action–state 0,441, dưới sàn 0,5. Đây là cùng kiểu lỗi ngón tay với 4 reject của pool planner-5; planner-6 không gây ra cũng không sửa nó.

Cái được và cái mất:

- **Được.** Đoạn REACH đi theo đường khớp nên không còn bò qua vùng cổ tay gần suy biến: 2 lượt `timeout:REACH` của planner-5 thành công. 2 lượt `timeout:REACH` mới (300087, 300088) hỏng ở 8,6 s, ngay trong đoạn chuyển khớp REACH, nên đường khớp cũng có lúc không xong trước `timeout_reach`.
- **Mất.** 7 lượt `L-TRAY-TILT` (planner-5: 1), cả 7 đều dừng ở 25,7–30,0 s. Trên các lượt đã ghi, nghiêng lớn nhất lúc mang của cả hai planner rơi vào lúc `reach_b` đã đặt mà `place` chưa đặt (planner-5 39/44 lượt, planner-6 32/38), tức là lúc hạ khay xuống bàn B. Nghi vấn chính là LOWER mới (min-jerk rồi bò 0,02 m/s), vì nó giữ khay lâu hơn ở sát mặt bàn, chứ không phải đoạn chuyển khớp, vốn kết thúc trước khi nhấc khay. **Chưa kiểm**: muốn tách hai thay đổi thì phải chạy lại 50 seed với `lower_ease: 0` (đường chuyển khớp giữ nguyên). Không chạy, vì D-29 bảo trượt thì dừng.

Nếu sau này vẫn muốn thử lại hướng này (Hiếu quyết, không phải bây giờ):

1. Chạy ablation `lower_ease: 0` ở trên.
2. Chọn đích IK có khoảng cách tối thiểu tới giới hạn `wrist_roll` (ví dụ 10 mrad), thay vì chấp nhận nghiệm nằm trên giới hạn khi không còn nhánh nào khác.
3. Kéo dài `timeout_reach` theo số bước của đoạn chuyển khớp.

Thêm nữa: `tray/pico/agent.py` của DA-35 dùng `TrayPlanner` với cùng YAML nhưng không có bộ chạy đoạn chuyển khớp. Nếu planner-6 được merge, nó sẽ nhận mục tiêu nâng tay và REACH không có blend, và hash `operator_version` của nó đổi theo khóa YAML mới. Phải xử lý chuyện này trước khi merge.

Chi phí: khoảng 2,2 giờ-worker trên rtx3060 (test sim 0,2; sinh 1,14; QA phát lại khoảng 0,85; chuỗi QA dưới 0,1), so với ước tính 3,0. Chạy ở 4 worker do DA-34 cấp, trong scope `MemoryMax=24G`, 00:00–00:44 ngày 5/11/2026. Kết quả thô ở `rtx3060:~/denso-da33-p6/val/` (`compare.txt`, `gen.log`, `out/p6-*`) và `~/denso-da33-p6/fwroot/` (release `tray_s1_da70bfc2da60`). Script so sánh: `p6_compare.py`, `wrist_roll_limits.py`, `tilt_phase.py` cùng thư mục.
