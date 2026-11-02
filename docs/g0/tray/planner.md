# Planner kịch bản bê khay (DA-33 nhiệm vụ 3, 4)

Planner thay luồng PICO: mỗi bước đọc trạng thái cảnh, sinh lệnh đi, hướng, hai tư thế cổ tay và độ nắm cho `StandWalkController` ([plan DA-33](../../superpowers/plans/2026-10-31-da33-tray-synthetic.md) Task 3–4, [story DA-33](../../product/stories/DA-33-synthetic-s1-khay.md) AC 2, 3). Mã ở `flywheel_simple.tray.planner` và `flywheel_simple.tray.agent`; mọi giá trị ở `configs/sim/tray_planner.yaml`. Quyết định đi kèm ở [decisions.md](decisions.md) D-14 đến D-21 và D-25.

## Kết quả (3/11/2026)

Mọi số đo trên cùng 48 episode (mức 0 seed 0, mức 1 seed 1–47), máy `rtx3060`; các tham số được chỉnh trên 48 episode này. Cột "seed mới" là 48 episode mức 1 seed 48–95 không dùng khi chỉnh. Cùng seed cho cùng quỹ đạo trên laptop và `rtx3060` (bộ điều khiển chạy theo đồng hồ điều khiển, D-17).

| Cách cầm | Thành công | Seed mới | Lỗi còn lại | Thời gian một episode thành công |
|---|---|---|---|---|
| **Đỡ ngửa bàn tay, nâng tay ở 0,50 m, dừng hạ sớm, lùi tay khi nhả (mặc định từ 3/11/2026, D-25)** | **39/47** (mức 1 seed 1–47) | **44/48** | 3 đặt lệch, 3 tuột một tay, 2 nghiêng, 2 `timeout:LIFT` (seed mới 92, 93), 1 `timeout:ARRIVE_B`; không lần nào chạm bàn A khi tiếp cận | chưa đo |
| Như trên, nâng tay ở 0,40 m | 35/47 | 40/48 | Ngón trỏ quét vào cạnh bàn A khi nâng tay (22/22 episode); 6 tuột một tay, 5 `timeout:REACH` | chưa đo |
| Kẹp bằng ngón tay Dex3, tư thế tay tự nhiên, chuyển động mượt (D-19, D-20, D-21; cấu hình thay thế) | 48/48 | 43/48 | Seed mới: 3 đặt lệch (65, 68, 90), 2 `timeout:RELEASE` (48, 93) | 30,5 s mô phỏng trung bình, tối đa 34,8 s |
| Kẹp bằng ngón tay, chuyển động mượt (D-20, commit `874f45b`) | 40/48 | 34/48 | 4 `timeout:LIFT` (seed 4, 10: khay xa; 41, 46), 3 đặt lệch, 1 `timeout:RELEASE`; seed mới: 12 `timeout:LIFT` | 28,4 s, tối đa 33,2 s |
| Kẹp bằng ngón tay, trước D-20 (tay nhảy mục tiêu mỗi lần đổi pha) | 40/48 | chưa đo | 4 `timeout:LIFT` (khay xa, seed 4, 10, 13, 34), 2 nghiêng, 1 `timeout:ARRIVE_B`, 1 đặt lệch | 27,4 s, tối đa 32,5 s |
| Ép mu hai nắm tay (D-18, cấu hình thay thế; đo trước D-20, chưa đo lại) | 44/48 | chưa đo | 2 ngoài tầm với, 2 nghiêng | 24,4 s, tối đa 26,4 s |

Hiếu chọn kẹp ngón (1/11/2026) vì dữ liệu có đóng mở bàn tay thật như dữ liệu teleop Ψ₀; ép mu tay giữ bàn tay nắm cố định suốt episode. Lần thử hỏng chỉ bị loại và ghi sổ, nên tỉ lệ 83 % không chặn việc sinh dữ liệu.

## Đỡ ngửa bàn tay (D-25)

Hiếu đổi cách cầm (3/11/2026) vì tư thế kẹp ngón không giống người: cổ tay xoay −60° quyết định hướng cẳng tay, khuỷu chĩa ra. Đỡ ngửa bàn tay giống người bưng khay có quai: lòng bàn tay ngửa dưới gờ tay cầm, ngón chạy dọc gờ và khép lên ôm mép ngoài, khuỷu buông sát hông, cẳng tay chĩa tới.

Mọi số trên 22 episode (mức 1, seed 100–121), `rtx3060`:

| Thử | Thành công | Nguyên nhân đo được |
|---|---|---|
| Chi phí khuỷu trong IK (kẹp ngón giữ nguyên), `elbow_cost` 2 / 8 | 4/8, 0/8 | Khuỷu chỉ vào gần thân 5 cm khi cổ tay lệch đích; hướng bàn tay quyết định hướng cẳng tay. Đã bỏ |
| Lòng bàn tay hướng vào, (0°, 20°, 10°) và (−30°, 25°, 10°) | mang được ở seed 100 | Khuỷu nhấc cao hơn vai |
| Đỡ ngửa (−90°, 10°, 0°) | 14/22 | 5 đặt lệch: cổ tay dưới gờ chạm bàn B trước khay, khay kê nghiêng 5° rồi bị kéo khi rút tay |
| Đỡ ngửa, chúc 20° / xoay −75° | 12/22, 8/22 | Đặt lệch, nghiêng |
| Đỡ ngửa, xoay bàn tay vào 30° / 45° / 60° | 0/22 | Tay không với tới tay cầm từ ngoài khay |
| Đỡ ngửa, cầm gần đầu ngón (`grip_x` 0,14 / 0,16 / 0,18) | 12 / 6 / 0 | Tay trượt khỏi gờ |
| Đỡ ngửa, `release_dz` 0 / −0,02 / −0,035 | 14 / 14 / 15 | Như trên |
| Dừng hạ khi khay còn cách bàn `lower_tray_clear` 2 / 2,5 / 3,5 cm | 14 / 14 / 17 | Hết đặt lệch; cổ tay trái kẹt dưới đầu gờ gần robot khi rút ra (`timeout:RELEASE`, seed 118) |
| 3,5 cm, lùi tay `release_back` 5 cm khi nhả | 19/22 | 2 tuột một tay, 1 `timeout:RELEASE`; lùi 3 cm hoặc 8 cm, dừng ở 4,5 cm: 17/22 |
| **Nâng tay khi hông cách mép bàn A `raise_at` 0,50 m (0,40 / 0,45 / 0,50)** | **21/22** (19 / 19 / 21) | Ở 0,40 cổ tay xoay tới −45° khi nâng, ngón trỏ cong quét vào cạnh bàn A trong cả 22 episode; ở 0,45 và 0,50 không lần nào chạm |

Ảnh so sánh ba cách cầm (toàn thân và cận cảnh bàn tay) được dựng bằng `fwdata/tune/grasp_look.py` trên `rtx3060`, không commit. Độ chĩa khuỷu đo bằng `scripts/g0/tray/measure_arm_pose.py` (khuỷu so với vai, trung bình khi cầm khay): kẹp ngón +13,8 cm, đỡ ngửa +11,7 cm; khác biệt nhìn thấy chủ yếu là cẳng tay không còn xoắn.

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

## Chuyển động mượt (D-20)

decoupled_wbc chỉ nội suy mục tiêu một bước điều khiển (20 ms). Trước D-20, mỗi lần đổi pha planner đổi mục tiêu cổ tay ngay trong một bước, nên tay lao tới: lòng bàn tay đạt 1,37 m/s. Tay người với tới theo đường cong tốc độ hình chuông trong khoảng 0,5–1 s, và dữ liệu synthetic cho Ψ₀ nên giống vậy.

Cách làm (`TrayPlanner._smoothed`, `_hand_closure`, `_arrived`):

- Mục tiêu danh nghĩa gồm điểm lòng bàn tay và hướng cổ tay, tính cả góc cân bằng khay. Khi mục tiêu này nhảy lúc đổi pha (hoặc đổi đoạn trong một pha), bước nhảy thành một độ lệch giảm dần theo hồ sơ min-jerk 10τ³ − 15τ⁴ + 6τ⁵. Thời lượng là max(`smooth_min_s` 0,6 s; quãng / `smooth_speed` 0,30 m/s; góc / `smooth_rot_speed_deg` 60°/s), chung cho hai tay. Hướng nội suy theo vector quay (như slerp). Các độ lệch cộng dồn, nên một bước nhảy mới khi bước cũ chưa giảm hết vẫn giữ liên tục cả vị trí lẫn vận tốc.
- Phần đổi liên tục đi thẳng qua, không làm mượt: dốc nhấc, dốc hạ, dịch đặt khay (`place_gain`), bù võng, cân bằng khay.
- Bước đầu đi từ tư thế cổ tay hiện tại của robot (`TrayAgent.start` gọi `TrayPlanner.start`). Trước đây đây là bước nhảy lớn nhất: 28,75 cm và 78,6° trong 20 ms.
- Độ nắm đổi theo min-jerk trong `hand_close_s` (0,5 s), không còn nhảy 0 → 1.
- Kiểm tra "tay đã tới" (REACH kết thúc, GRASP bắt đầu khép) chờ quỹ đạo kết thúc rồi mới so lòng bàn tay đo với đích cuối. So với đích cuối thôi là không đủ: tay võng nên lòng bàn tay đo ở tư thế sẵn sàng đã cách đích pre-grasp dưới `palm_tol`.
- Bù võng tích phân sai số giữa lòng bàn tay đo và đích đã làm mượt của bước trước, nên bù cả trên đường đi mà không tích phân chính chuyển động.
- RELEASE mở tay trước, giữ cổ tay như cuối LOWER trong `hand_close_s`, rồi mới đưa tay ra ngoài và xuống. D-21 đổi thành mở tay trong khi hạ `release_dz`.

Số đo trên 48 episode, trước và sau. Bước nhảy là thay đổi lớn nhất của lệnh lòng bàn tay trong 20 ms. Tốc độ và gia tốc lấy từ lòng bàn tay đo trong khung thân, sai phân ở 50 Hz.

| Pha | Bước nhảy lệnh (cm) | Tốc độ tối đa (m/s) | Gia tốc p95 (m/s²) |
|---|---|---|---|
| APPROACH_A | 28,75 → 0,82 | 1,37 → 0,47 | 9,8 → 5,6 |
| REACH | 16,28 → 1,33 | 1,09 → 0,69 | 25,3 → 5,7 |
| GRASP | 7,97 → 1,39 | 1,19 → 0,64 | 10,9 → 5,8 |
| LIFT | 0,83 → 0,77 | 0,49 → 0,33 | 1,2 → 1,0 |
| LOWER | 5,00 → 0,47 | 0,55 → 0,18 | 1,8 → 0,8 |
| RELEASE | 6,36 → 0,76 | 0,76 → 0,54 | 8,5 → 2,9 |
| BACK_OFF đến ARRIVE_B, RETREAT (đi) | 0–0,18 → 0–0,27 | 0,37–0,43 → 0,38–0,45 | 4,4–8,1 → 4,9–8,1 |

Bước xoay lớn nhất của lệnh cổ tay giảm từ 78,6° (đầu APPROACH_A) và 20° (RELEASE bỏ góc cân bằng) xuống 2,25°. Bước độ nắm lớn nhất giảm từ 1,0 xuống 0,075. Khi đi, tay đứng yên trong khung thân; tốc độ và gia tốc ở các pha này do hông lắc theo dáng đi, nên không đổi. Riêng seed 22 mức 1: tốc độ tối đa 1,37 → 0,47 m/s, gia tốc p95 trong GRASP 13,3 → 5,1 m/s².

Cách cầm kẹp ngón đã chỉnh trước D-20 dựa vào cú lao tay, nên phải chỉnh lại:

| Bước | Thành công | Nguyên nhân đo được |
|---|---|---|
| Làm mượt; kiểm tra ra pha so với đích cuối | 9/48 | Lòng bàn tay đo ở tư thế sẵn sàng đã gần đích pre-grasp: REACH kết thúc sau 0,16 s, tay cắt góc xuống gờ (seed 22) |
| Chờ quỹ đạo kết thúc; bù võng tắt khi tay đang đi | 1/48 | Ngón nằm trên bàn A, robot bị đẩy lùi ~18 cm trong GRASP. Trước D-20, bù z trong GRASP kéo ngón xuống dưới gờ trong 0,2 s |
| Bù võng theo đích đã làm mượt của bước trước | 10/22 | RELEASE: tay vừa mở vừa ra, ngón cái còn móc kéo khay nghiêng 9,9° |
| RELEASE mở tay trước rồi mới ra | 11/22 | Khép muộn (`grasp_close_after` 1,5 s), hông trượt lùi khi chờ |
| `grasp_close_after` 0,5 s | 13/22 | Chỉ còn 1 `timeout:LIFT`; cổ tay kẹt dưới gờ khi nhả (8 `timeout:RELEASE`) |
| `pregrasp_offset` 0,06 → 0,12 m (nhả tay ra xa hơn) | 33/48 | — |
| `grasp_close_after` 0,35 s, `smooth_speed` 0,25 → 0,30 m/s | **40/48** | — |

Các dòng x/22 đo trên 22 episode đầu (mức 0 seed 0, mức 1 seed 1–21); trên 22 episode này cấu hình trước D-20 đạt 17/22. Đã thử và bỏ: bù GRASP và LIFT theo đích cuối (7/48), bỏ bù trong REACH (16/48), ngắm thấp hơn (`grasp_dz` −0,01 / −0,02 / −0,03 → 1 / 0 / 1 của 22), pre-grasp thấp hơn (`pregrasp_dz` 0,02 / 0 → 5 / 3 của 22), `palm_correction_gain` 0,2 (8/22), `release_dz` 0 / −0,04 / +0,01 (13/22, như cũ), `hand_close_s` 0,4 (27/48), `smooth_min_s` 0,5 (33/48).

Tỉ lệ thành công nhạy với `grasp_close_after`: ở `smooth_speed` 0,25 thì 0,6 / 0,5 / 0,45 / 0,4 / 0,35 s cho 31 / 33 / 29 / 37 / 36 của 48. 40/48 là điểm tốt nhất tìm được, không phải một vùng ổn định. Bộ episode thành công cũng đổi: seed 13, 34 (khay xa) và 14, 19, 28, 29 nay thành công; 31, 33, 37, 38, 41, 46 nay hỏng.

## Tư thế tay tự nhiên (D-21)

Sau D-20 tay di chuyển mượt, nhưng tư thế vẫn lạ: suốt lúc đi tới bàn A, hai tay giơ ngang ngực, khuỷu dạng ra, cổ tay đã xoay ngửa theo tư thế kẹp, ngón xòe hết cỡ. Người thật đi với tay buông, tới bàn mới nâng tay, và xoay cổ tay khi với tới tay cầm. Hiếu chọn cách này (3/11/2026).

Đo ở tư thế đứng mặc định của decoupled WBC (`TrayAgent.start` lấy tư thế này làm tư thế nghỉ): lòng bàn tay ở (0,25; ±0,19; +0,05) m so với hông, cổ tay gần trung tính (lật ±10°, ngửa 10°). Ngón giữa vươn 0,35 m trước hông, ngang hông, thấp hơn mặt bàn 10 cm. Robot bắt đầu cách mép bàn A 0,53 m và dừng ở 0,10 m.

Trình tự mới:

| Đoạn | Tay | Điều kiện chuyển |
|---|---|---|
| APPROACH_A, đi | Tư thế đứng, ngón hơi cong (`hand_closure_rest` 0,3) | Hông cách mép bàn A `raise_at` 0,40 m: đầu ngón còn cách mép ~5 cm (từ D-25: 0,50 m, xem mục đỡ ngửa) |
| APPROACH_A, nâng tay | Dừng, nâng lòng bàn tay lên (0,15; ±0,32; 0,26) m, cổ tay xoay nửa đường tới tư thế kẹp (−25°, 20°, 8°) | Lòng bàn tay cao hơn mặt bàn `ready_clear`, rồi đi tiếp |
| REACH | Xoay nốt cổ tay sang tư thế kẹp, mở ngón | Như D-20 |
| RELEASE | Mở tay trong khi hạ `release_dz` 2 cm, rồi đưa tay ra | Như D-20 |
| RETREAT | Lùi `retreat` 0,35 m (đầu ngón ra khỏi bàn B), rồi hạ tay về tư thế đứng, ngón hơi cong | Tay đã về tư thế đứng: DONE |

Trong sim, env kết thúc ngay khi `check_success` đạt, thường lúc robot đang lùi, nên đoạn hạ tay cuối RETREAT ít khi hiện trong episode. Test thế giới giả có kiểm tra đoạn này.

Những gì đo được khi chỉnh:

| Thử | Thành công | Nguyên nhân đo được |
|---|---|---|
| Cổ tay trung tính khi nâng tay, (0,15; ±0,30; 0,22) | 15/48 | Ngón cái thò vào trong tới y ≈ 0,25 m, trong mép ngoài tay cầm (0,265 m): khi đi vào thì chạm tay cầm, khi REACH xoay cổ tay thì quét vào khay, đẩy khay 2–5 cm (seed 0, 1) |
| Cổ tay đúng tư thế kẹp khi nâng tay, z 0,22 | 0/22 | Lòng bàn tay không lên tới `ready_clear`, robot đứng chờ tới hết giờ |
| Cổ tay nửa đường, (0,15; ±0,32; 0,26) | 39/48 | Hết lỗi nhấc, kể cả khay xa; 9 đặt lệch: ngón mở ngay dưới gờ cạy khay lên 2,9 cm, nghiêng 8,4° (seed 0) |
| RELEASE mở tay trong khi hạ | 40/48 | 8 đặt lệch: khay đã đặt lệch 4,1 cm (còn trong 5 cm), ngón cái đẩy thêm 2,7 cm khi nhả (seed 1) |
| `arrive_lat_tol` 0,04 → 0,02 m: bước tới đích sát hơn trước khi hạ | **48/48** | 0,015 cũng 48/48, 0,025 cho 44/48, 0,03 cho 42/48 |

Trên 22 episode đầu (mức 0 seed 0, mức 1 seed 1–21), với tay ở (0,15; ±0,30; 0,26), cổ tay khi nâng tay cho: trung tính 0/22, nửa đường 18/22, đúng tư thế kẹp 15/22. Rộng 0,30 / 0,32 / 0,34 m ở z 0,26 cho 34 / 39 / 37 của 48; z 0,24 cho 28/48. Đã thử và bỏ: `raise_at` 0,45 (13/48 trước khi sửa cổ tay), `release_dz` −0,01 / −0,03 / −0,04 (39 / 39 / 37), `hand_close_s` 0,3 (39), `place_shift_max` 0,07 (44).

Độ mượt trên 48 episode vẫn như D-20: bước nhảy lệnh tối đa 1,26 cm, xoay 2,33°, độ nắm 0,075 mỗi bước 20 ms. Riêng APPROACH_A, tốc độ lòng bàn tay đo lên tới 0,99 m/s (lệnh tối đa 0,56 m/s ở đỉnh hồ sơ min-jerk khi nâng tay): tay vọt quá khi nâng lên.

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

1. **Khay xa ngoài tầm nhấc**: trước D-20 là 4/48 (seed 4, 10, 13, 34); với D-21 không còn lỗi nhấc nào trên 96 episode: khay cách mép 0,23–0,25 m (mức 1 dịch +5 cm), tay vươn hết cỡ thì không nhấc nổi. Hướng: cúi người bằng eo khi với, hoặc giảm `tray_edge_offset` thêm (cần quyết định mới).
2. **Đặt và nhả khay.** Với đỡ ngửa (D-25), khay rơi 3,5 cm khi tay rút ra; còn 3 đặt lệch, 1 `timeout:RELEASE` trên 95 episode. Tay đỡ võng ~10 cm khi mang nên 6 lần tuột một tay. Với kẹp ngón, trên seed mới còn 3 đặt lệch và 2 `timeout:RELEASE`: ngón cái vẫn đẩy khay 2–3 cm khi nhả. Cấu hình ép mu tay (D-18) chưa đo lại với D-20, D-21; phải chỉnh lại trước khi dùng (cần `hand_closure_rest` 1).
3. **Ma sát xoắn của tay cầm.** Hình học va chạm của tay cầm có `condim 4` nhưng hệ số ma sát xoắn chỉ 0,005. Một vùng tiếp xúc tay thật cỡ 0,03 sẽ giảm lỗi nghiêng của cả hai cách cầm; đây là thay đổi vật lý của task, cần quyết định.

## Chạy

Một episode có video và báo cáo:

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/view_scene.py --agent planner --seed 0 --level 0 --out fwdata/simple/tray/planner
```

Test sim của planner:

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python -m pytest packages/flywheel-simple/tests/tray/test_agent.py -m sim -v
```

Quét tham số chạy song song trên `rtx3060` bằng script nháp trong `fwdata/tune/` (không commit; `smooth_sweep.py` ghi thêm lệnh và lòng bàn tay đo từng bước để tính số đo độ mượt): mỗi tiến trình giữ một env, khoảng 3,3 GB RAM, tối đa khoảng 24 tiến trình trên máy 94 GB.
