# Teleop ảo cho task bê khay (DA-35)

Teleop ảo là người điều khiển tự động phát tín hiệu tay cầm, cần gạt và nút vào ống teleop PICO của SIMPLE ([pico-teleop.md](pico-teleop.md)), vì đội không có kính PICO ([story DA-35](../../product/stories/DA-35-synthetic-s2-khay-pico.md)). Tài liệu này ghi dải phong cách đo từ teleop người của tác giả (nhiệm vụ 3), rồi sẽ ghi thêm thiết kế và số đo của teleop ảo (nhiệm vụ 4–7).

## Phong cách teleop người (nhiệm vụ 3)

### Nguồn và cách đo

| Mục | Giá trị |
|---|---|
| Dữ liệu | psi-data của tác giả trên Hugging Face `USC-PSI-Lab/psi-data`, thư mục `simple/`: `G1WholebodyPickAndPlaceAndHugContainerTeleop-v0` (94 episode, ôm thùng bằng hai tay rồi đi sang bàn khác) và `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` (99 episode, gắp vật, đi giữa hai bàn). Teleop PICO của người, decoupled WBC, 50 Hz, định dạng Ψ₀ (state 32, action 36) |
| Quyền dùng | Dataset không khai license (API Hugging Face, 3/11/2026). PO cho tải để đo thống kê phong cách; không train, không đưa vào release. Tải về `fwdata/psi-data/simple/`, chỉ giải nén `meta/` và `data/` |
| Đo trên | Lệnh khớp tay `action[14:28]` (mục tiêu sau IK, gần ý người điều khiển nhất), hướng thân `action[28:31]`, lệnh đi `action[32:35]` |
| Cổ tay, khuỷu | FK bằng robot model G1 của `decoupled_wbc`, eo bằng 0, nên vị trí tính trong khung thân. Frame `*_wrist_yaw_link`, `*_elbow_link` |
| Đoạn chuyển động | Cổ tay nhanh hơn 0,05 m/s, dừng khi dưới 0,03 m/s, dài ít nhất 0,2 s (`flywheel_simple.tray.pico.style`) |
| Lúc dừng | Hai cổ tay dưới 0,05 m/s và cả ba lệnh đi dưới 0,05, kéo dài ít nhất 0,3 s. Với ngưỡng 0,02 m/s thì không có lúc dừng nào: tay người qua PICO luôn rung nhẹ |
| Lệnh | `PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python scripts/g0/tray/pico/measure_teleop_style.py fwdata/psi-data/simple/<task> … --out fwdata/psi-data/style.json` |

### Kết quả

Mỗi ô là p10 / p50 / p90. Chỉ số theo episode lấy phân bố qua các episode; chỉ số `segment_*` và `pause_s` gộp mọi đoạn của mọi episode.

| Chỉ số | Ôm thùng (94) | Đi giữa hai bàn (99) |
|---|---|---|
| Thời lượng episode (s) | 7,35 / 8,9 / 11,2 | 10,9 / 12 / 15 |
| Pitch thân thấp nhất, p5 trong episode (°) | −1,31 / 0,03 / 0,94 | −0,30 / 0,78 / 1,56 |
| Pitch thân cao nhất, p95 trong episode (°) | 6,47 / 8,44 / 12,4 | 3,90 / 4,77 / 5,75 |
| Khoảng roll thân (°) | 6,33 / 7,26 / 8,23 | 10,0 / 10,3 / 10,7 |
| Khoảng yaw thân (°) | 5,24 / 7,67 / 10,6 | 5,05 / 7,52 / 12,7 |
| Số đoạn cổ tay mỗi phút | 56,7 / 75,2 / 90,8 | 29 / 40 / 61,6 |
| Jerk RMS cổ tay (m/s³) | 13,5 / 16,9 / 21,5 | 3,01 / 3,99 / 5,95 |
| Phần công suất vận tốc ở 4–12 Hz | 0,035 / 0,050 / 0,088 | 0,048 / 0,084 / 0,153 |
| \|y\| khuỷu (m) | 0,167 / 0,172 / 0,179 | 0,180 / 0,186 / 0,198 |
| \|y\| cổ tay (m) | 0,104 / 0,135 / 0,158 | 0,153 / 0,178 / 0,207 |
| Khoảng cách hai cổ tay (m) | 0,209 / 0,269 / 0,320 | 0,324 / 0,374 / 0,435 |
| z cổ tay p10 / p90 trong episode (m) | 0,10 / 0,20 (trung vị) | 0,115 / 0,181 (trung vị) |
| x cổ tay p90 (m, ra trước) | 0,241 / 0,276 / 0,307 | 0,218 / 0,230 / 0,245 |
| Phần thời gian đi | 0,049 / 0,171 / 0,312 | 0,228 / 0,278 / 0,311 |
| `vx` lệnh lớn nhất (m/s) | 0,245 / 0,5 / 0,5 | 0,5 / 0,5 / 0,5 |
| `vx` trung bình khi đi (m/s) | 0,198 / 0,322 / 0,438 | 0,425 / 0,471 / 0,494 |
| Gia tốc `vx`, p95 trong episode (m/s²) | 0,148 / 0,717 / 1,76 | 0 / 0,109 / 0,517 |
| `vyaw` lệnh lớn nhất (rad/s) | 0,442 / 0,653 / 0,817 | 0,668 / 0,996 / 1,0 |
| Tốc độ đỉnh mỗi đoạn (m/s) | 0,104 / 0,299 / 0,642 | 0,062 / 0,114 / 0,263 |
| Thời lượng đoạn (s) | 0,26 / 0,72 / 1,86 | 0,26 / 0,60 / 1,24 |
| Độ dài đoạn (m) | 0,024 / 0,105 / 0,394 | 0,014 / 0,045 / 0,134 |
| Độ cong đoạn | 0,053 / 0,294 / 1,02 | 0,030 / 0,096 / 0,432 |
| Vị trí đỉnh tốc độ trong đoạn (0,5 là min-jerk đối xứng) | 0,125 / 0,364 / 0,784 | 0,133 / 0,367 / 0,714 |
| Lúc dừng (s) | 0,34 / 0,42 / 0,68 | 0,34 / 0,50 / 0,78 |
| Số lúc dừng mỗi episode | 0 / 0 / 1 | 0 / 2 / 3,2 |

Hướng cổ tay trái ở giữa episode, trung vị roll, pitch, yaw: (−0,3°, −15,3°, 6,5°) khi ôm thùng; (4,5°, −1,8°, 2,5°) khi gắp và đi.

### Đọc kết quả

- Người chuyển động thành nhiều đoạn ngắn: một lần với tay là một đoạn chính rồi vài đoạn chỉnh nhỏ (độ dài đoạn trung vị chỉ 4,5–10,5 cm, 40–75 đoạn mỗi phút). Một đường min-jerk trơn từ đầu tới cuối không giống người.
- Đỉnh tốc độ đến sớm (trung vị 0,36 thời lượng đoạn): người lao tay nhanh rồi chậm dần khi tới gần. Min-jerk đối xứng đặt đỉnh ở 0,5.
- Đường tay cong rõ khi ôm (độ cong trung vị 0,29), ít cong khi chỉ gắp và đi (0,10).
- Thân có nghiêng: pitch cao nhất trong episode 6,5–12,4° khi ôm thùng, 3,9–5,8° khi gắp; roll và yaw dao động 5–13°. Đây là phần IK có eo của SIMPLE tạo ra từ tư thế tay, không phải lệnh riêng.
- Cần gạt gần như bật tắt: `vx` lớn nhất bằng 0,5 m/s (giới hạn của `PicoStreamer`) ở hầu hết episode, đi trung bình 0,32–0,49 m/s. Quay tới 0,44–1,0 rad/s.
- Có rung nhỏ: 3–15% công suất vận tốc cổ tay nằm ở 4–12 Hz.
- Khuỷu cách trục thân 17–20 cm (vai ở 10 cm), tức khuỷu sát thân. Khoảng cách hai tay là của task (thùng, vật), không chép sang khay: tay cầm khay cách nhau theo hình học khay.

Giới hạn: đo trên lệnh khớp sau IK và nội suy của WBC, không phải trên tay cầm PICO thô. Quy ước dấu pitch theo RPY của SIMPLE; giả định pitch dương là cúi về trước, chưa kiểm bằng ảnh. Số lượng: một người thu hay nhiều người thì dataset không ghi.

### Dải phong cách cho teleop ảo [Đề xuất]

Mỗi episode rút đều trong dải, từ seed phong cách. Dải lấy từ p10–p90 ở trên, ưu tiên cột ôm thùng (hai tay, gần bê khay nhất); số là đề xuất ban đầu, chỉnh ở nhiệm vụ 6 khi so bảng chuyển động (AC 8).

| Tham số | Dải | Từ chỉ số |
|---|---|---|
| Tốc độ đỉnh của đoạn với chính | 0,25–0,65 m/s | Tốc độ đỉnh mỗi đoạn, nửa trên (đoạn với dài) |
| Vị trí đỉnh tốc độ trong đoạn | 0,15–0,75 | Vị trí đỉnh tốc độ |
| Độ cong đường với | 0,05–0,40 | Độ cong đoạn |
| Số đoạn chỉnh sau mỗi lần với | 1–3 | Số đoạn mỗi phút, độ dài đoạn ngắn |
| Độ dài đoạn chỉnh | 1–5 cm | Độ dài đoạn, nửa dưới |
| Thời lượng đoạn chỉnh | 0,26–0,6 s | Thời lượng đoạn, nửa dưới |
| Rung (phần công suất vận tốc 4–12 Hz) | 0,03–0,10 | Phần công suất 4–12 Hz |
| Số lúc dừng mỗi episode, thời lượng | 0–3; 0,34–0,78 s | Lúc dừng |
| `vx` khi đi | 0,30–0,50 m/s, phần lớn ở 0,5 | `vx` trung bình khi đi, `vx` lớn nhất |
| Gia tốc cần gạt `vx` | 0,15–1,8 m/s² | Gia tốc `vx` |
| `vyaw` khi quay | 0,45–1,0 rad/s | `vyaw` lớn nhất |
| \|y\| khuỷu khi nghỉ và khi mang | 0,17–0,20 m | \|y\| khuỷu |

Kiểm sau khi có teleop ảo (AC 8): cùng các chỉ số đo trên episode teleop ảo phải nằm trong p10–p90 của người, trừ khoảng cách hai tay, độ dài và thời lượng episode (riêng của task khay).

## Đồng hồ sim (nhiệm vụ 4)

Agent PICO của SIMPLE nội suy thân trên của WBC theo `time.monotonic()`, và CLI ngủ cho đủ 50 Hz thời gian thực. Với streamer kịch bản, kết quả khi đó phụ thuộc tốc độ máy. `flywheel_simple.tray.pico.clock.SimClock` tính thời gian từ số bước (`start + ticks · 0,02 s`, không cộng dồn sai số), quay về `start` ở mỗi lần reset episode, trước khi agent reset ống WBC. `StreamerDecoupledAgent(..., clock=SimClock())` thay `time` trong module agent PICO của SIMPLE bằng một proxy đọc đồng hồ này; vòng phiên tick một lần mỗi bước env và không ngủ. Proxy thay cho cả process, nên mỗi process chỉ có một agent có đồng hồ (mỗi worker một env). Teleop bằng kính thật vẫn dùng giờ thật.

| Đo (rtx3060, 3/11/2026) | Kết quả |
|---|---|
| Hai lần chạy cùng điều kiện `1:7`, streamer kịch bản, 250 bước | `action`, `action.eef`, `observation.state`, `observation.tray_pose` giống hệt từng bit (`assert_array_equal`) |
| Một lượt 1000 bước (20 s sim), ghi LeRobot thật | 21,3 s thời gian thực, khoảng 21 ms mỗi bước: gần 1× thời gian thực, không nhanh hơn rõ |
| Profile 500 bước | `env.step` khoảng 16 ms mỗi bước, trong đó render hai camera stereo 10,5 ms (chỉ mắt trái được ghi); phần còn lại là agent (WBC, IK) và ghi frame |

Hệ quả cho quy mô: mỗi worker chạy khoảng 1× thời gian thực, nên số episode mỗi giờ đến từ số worker (tối đa 22 trên rtx3060). Bỏ render mắt phải là chỗ tối ưu đầu tiên nếu cần (nhiệm vụ 12).

## Người điều khiển ảo (nhiệm vụ 5)

`flywheel_simple.tray.pico.operator.VirtualOperator` lấy ý định từ `TrayPlanner` của DA-33 và phát tín hiệu như `PicoStreamer`; `flywheel_simple.tray.pico.agent.VirtualPicoStreamer` cắm nó vào chỗ của kính trong `StreamerDecoupledAgent`. Lệnh phiên:

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
    -m flywheel_simple.tray.pico.session --conditions 0:0 --operator op-virtual --streamer virtual
```

| Planner ra | Người điều khiển ảo phát |
|---|---|
| Hai cổ tay, khung đế | Tư thế hai tay cầm: `robot_to_teleop` của mục tiêu (qua lớp phong cách nếu có), với `ctrl0` lúc kích hoạt và tư thế hiệu chuẩn đọc từ `WristsPreProcessor` |
| Độ đóng bàn tay 0–1 | Từ 0,5 trở lên: cò cộng grip (kiểu đóng "middle" của PICO); dưới: mở |
| `vx`, `vy` | Cần trái, giới hạn gia tốc (`JoystickShaper`) |
| Hướng thân | Cần phải, vòng kín trên yaw thân đo được (`YawStick`); `target_yaw` là tích phân của cần như `PicoStreamer`. Luật lái sửa ở nhiệm vụ 6 |
| ABORT, hoặc DONE mà chưa đạt | Bỏ lượt bằng nút reset sau `give_up_s` hoặc `done_wait_s` |

Một episode bắt đầu như với kính: robot đứng vững, người ảo bấm kích hoạt với tay cầm ở `ctrl0` (bộ tiền xử lý hiệu chuẩn lúc đó), giữ yên `engage_s` cho SIMPLE đưa tay về tư thế hiệu chuẩn, rồi chạy planner từ tư thế đó. Tham số ở `configs/sim/tray_virtual_teleop.yaml`; mỗi lượt ghi dòng thời gian pha và lý do abort vào `attempts.jsonl`.

Quyết định **[Đề xuất]**:

| Quyết định | Lý do | Nếu sai |
|---|---|---|
| Bàn tay chỉ dùng ba mức đóng của PICO, chọn cò cộng grip; tư thế nghỉ (planner đóng 0,3) thành mở | Dữ liệu cùng dạng với PICO thật (story, mục Bàn tay). Kiểu "middle" không xoay ngón cái, gần cách kẹp ngón D-19 nhất. Đo: cầm và đặt được (bảng dưới), nên không cần hỏi PO về bàn tay đóng liên tục | Đổi `grasp` (0 cò, 2 grip) |
| Yaw lái vòng kín (bản nhiệm vụ 5: đẩy cần theo sai số của thân; bản hiện hành ở nhiệm vụ 6) | Thân dưới chỉ quay khi \|vyaw\| ≥ 0,1, còn `PicoStreamer` tích phân `target_yaw` từ cần. Cờ giữ hướng 0,1 của S1 (D-10) với `target_yaw` đứng yên thì PICO không phát được | Chỉnh ngưỡng, hoặc quay về cờ giữ hướng (lệch khỏi dữ liệu PICO) |
| Planner bắt đầu từ tư thế cổ tay hiệu chuẩn, không từ tư thế đứng (nhiệm vụ 6 lùi tư thế này 5 cm) | Lúc kích hoạt ống PICO đưa tay tới tư thế này; planner dùng nó làm tư thế nghỉ lúc đi và lúc xong | |
| Người ảo bỏ lượt 1 s sau khi planner abort, 5 s sau DONE mà chưa đạt | Như người thu giữ hai grip để reset; không chạy hết 90 s | Chỉnh tham số |

Số đo (rtx3060, 3/11/2026, chưa có lớp phong cách):

| Đo | Kết quả |
|---|---|
| Test CPU trên thế giới giả của planner, qua đường tín hiệu PICO (đổi thuận của bộ tiền xử lý, ba mức đóng, cờ quay) | Đạt ở mức 0 seed 0 và mức 1 seed 3; `target_yaw` bằng tích phân của `vyaw`; cần quay khi đẩy luôn ≥ 0,1 |
| Một lượt mức 0 seed 0 qua phiên thu thật, ghi LeRobot | Đạt `check_success`, đủ 7 bước, 35,0 s sim, 1751 frame |
| 8 lượt, mức 0 seed 1–4 và mức 1 seed 1–4, mỗi worker một lượt | 7/8 đạt (31,0–35,0 s sim). Mức 1 seed 4 hỏng `L-TRAY-TILT` lúc quay |
| Thời gian máy | Chưa đo sạch: lúc đo, lô S1 của DA-33 (22 worker) chạy cùng máy, load 47–80. Một lượt một mình 144 s thực cho 35 s sim; profile 1000 bước: `env.step` 46 ms (render 31 ms), agent PICO 19 ms, vật lý 10 ms. Đo lại khi máy rảnh (nhiệm vụ 7) |

## Phong cách mỗi episode (nhiệm vụ 6)

Mỗi lượt thử rút một bộ phong cách từ seed `style_seed_for(style_base, level, seed, lần thử)` (`SeedSequence`): cùng điều kiện, cùng lần thử thì cùng phong cách; lần thử khác thì phong cách khác. `--style-base` đổi cả họ seed, `--no-style` chạy planner không phong cách. Episode lưu ghi khối `flywheel` theo AC 3, cùng tên trường với meta S1 của DA-33:

| Trường | Giá trị |
|---|---|
| `source_kind`, `synthetic_tier`, `source_detail`, `action_quality` | `synthetic`, `S1`, `virtual_teleop`, `planned` |
| `style_base`, `style_seed`, `style`, `condition_attempt` | Họ seed, seed của lượt, bộ tham số (7 số), lần thử |
| `level`, `seed`, `split` | Điều kiện; chỉ seed train |
| `operator_version` | `da35-virtual-1+cfg.<hash>`: hash của cấu hình người ảo, cấu hình planner và dải phong cách |
| `wrapper_version`, `simple_commit`, `embodiment_id`, `renderer`, `data_class` | `da35-pico-2`, commit SIMPLE, `g1_sonic_dwbc@1`, `mujoco`, `public` |

`attempts.jsonl` ghi thêm `style_seed`, dòng thời gian pha và lý do abort của mọi lượt.

### Chỉnh để phong cách không làm hỏng task

Đo trên cùng 16 điều kiện (mức 0 và 1, seed 12 và 20–26), rtx3060, 3/11/2026. "Đủ cờ" là lượt đạt có cả 7 cờ bước của `StepTracker`, cần để cắt demo ở nhiệm vụ 8.

| Bản | Đạt | Đủ cờ | Hỏng chính |
|---|---|---|---|
| Không phong cách (luật cần gạt của nhiệm vụ 5) | 14 | 13 | |
| Phong cách trên tay mọi pha | 9 | 3 | Bộ bù chùng tay của planner tích phân độ trễ của tay, rồi giữ nguyên trong GRASP: tay lệch tay cầm 4 cm (thế giới giả) |
| Như trên, planner thấy tay "như người ảo định đặt" | 7–9 | 1–3 | Lòng bàn tay cách tâm tay cầm 10,3–11,3 cm khi kẹp, quá 10 cm (`r_reach`) nên cờ bước 1 không bật |
| Tắt dần phong cách tay khi chạm khay | 13 | 3 | Như trên |
| Chỉ cần gạt có phong cách (8 điều kiện hỏng ở bản trên) | 7/8 | 7/8 | Phong cách tay là nguyên nhân |
| Tay có phong cách chỉ khi xa khay, bỏ "tay như định đặt" | 11 | 10 | Kẹt ở APPROACH_A, quá giờ ARRIVE_B |
| Luật cần phải mới, kéo tay về sát người, buông cần khi planner không xin quay (bản hiện hành) | **16** | **16** | |

Quyết định **[Đề xuất]**:

| Quyết định | Lý do | Nếu sai |
|---|---|---|
| Phong cách tay (trễ, vọt lố, đường cong, rung) chỉ có khi tay ở xa khay: APPROACH_A (nâng tay khi đi tới) và RETREAT (hạ tay khi lùi); tắt và bật dần trong `style_fade_s` = 0,3 s. Cần gạt có phong cách suốt episode | Bảng trên: phong cách tay gần khay làm hỏng kẹp và đặt. Người thật cũng chậm lại khi chạm vật | Mở thêm pha trong `STYLED_PHASES` (`operator.py`) và đo lại |
| Bỏ việc đưa planner lòng bàn tay "như người ảo định đặt" | Nó làm các kiểm tra an toàn của planner (tay đã cao hơn mặt bàn chưa, tay đã tới chưa) nhìn tay không có độ trễ, trong khi tay thật còn ở dưới | |
| Cần phải lái `target_yaw` về hướng planner cộng phần đi trước `yaw_lead` × sai số (tối đa 2°), thả khi cả thân lẫn target tới nơi; giữ chiều quay khi còn cách hơn 90°; buông cần khi planner không gửi cờ quay | Đẩy cần theo sai số của thân làm `target_yaw` trôi khỏi hướng (−0,36 rad khi hướng là −0,15), rồi cờ quay kéo thân về phía target: mức 1 seed 20 không tiến được 10 s. Ở 180° sai số đổi dấu theo mỗi lần thân lắc nên cần rung tại chỗ. Giữ cần khi planner muốn đứng yên làm thân lắc 6°, trượt 5 cm, ARRIVE_B không ổn định | |
| Sau kích hoạt, hai tay đi theo min-jerk từ tư thế hiệu chuẩn về tư thế nghỉ lùi 5 cm (`rest_dx`) trong `engage_s` | PICO không có bàn tay đóng một phần, nên ngón duỗi thẳng vươn xa hơn tư thế nghỉ co 30% của DA-33 (D-21) và chạm mép bàn A ngay trước điểm planner nâng tay (thân cách mép 0,41 m, xoay 8°). Khuỷu sát thân hơn | Chỉnh `rest_dx`, `rest_dz` |
| Dải gia tốc cần trái 0,5–1,8 m/s² (người: 0,15–1,8) | Dưới 0,5 m/s², các bước chỉnh 0,12 m/s của planner ở bàn B lên tốc quá chậm | |
| Thêm `turn_rate` vào phong cách, dải 0,45–0,75 rad/s (người: 0,45–1,0) | Quay nhanh hơn làm nghiêng khay đang mang | |
| Bấm nút đóng ngay khi planner đóng, không chờ tay bắt kịp | Phong cách tay đã tắt khi kẹp; bản chờ tay (tới 0,3 s) cho 7/16 đạt | |

Giới hạn đã biết **[Đã chốt]** (PO duyệt 3/11/2026, giữ như trên): dữ liệu teleop ảo không có phong cách tay khi tay ở gần khay (REACH, GRASP, LIFT, mang khay, PLACE, RELEASE), nên chỉ phần nâng tay và hạ tay mang trễ, vọt lố, đường cong và rung của người; dải gia tốc cần trái (0,5–1,8 m/s²) và tốc độ quay (0,45–0,75 rad/s) hẹp hơn dải đo trên người (0,15–1,8 m/s² và 0,45–1,0 rad/s). So với người ở AC 8 (nhiệm vụ 12) cần tính hai giới hạn này.

Chưa làm: lúc dừng giữa pha (0–3 lần mỗi episode ở người). Dừng tay khi planner đang chạy đồng hồ pha sẽ làm lệch các mốc giờ của planner; planner đã có các lúc chờ riêng (giữ khi kẹp, khi nâng, khi tới bàn B). So chuyển động với người (AC 8) để nhiệm vụ 12.

## Lô demo cha (nhiệm vụ 7)

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid \
    fwdata/simple/.venv/bin/python scripts/g0/tray/pico/generate_parents.py \
    --out fwdata/simple/tray/virtual/parents-1103b --levels 0,1 --seeds 100-179 --workers 16 \
    < /dev/null > parents-1103b.log 2>&1 &
```

`generate_parents.py` chia điều kiện xoay vòng cho các worker; mỗi worker là một phiên `--streamer virtual` với env và dataset LeRobot riêng ở `<out>/shard-NN/`. Chạy lại thì bỏ qua điều kiện shard đã ghi. Cuối lô ghi `<out>/summary.json`: số lượt, kết quả, nhãn lỗi, giây sim, giây worker, danh sách demo cha đủ 7 cờ bước (shard, chỉ số episode, level, seed, seed phong cách).

Trong lúc làm nhiệm vụ 5–7, DA-33 merge vào master cách cầm ngửa lòng bàn tay dưới tay cầm (D-25, Hiếu chọn 3/11/2026), thay cho cách kẹp ngón D-19 mà nhiệm vụ 5, 6 đã chỉnh trên đó. Vì vậy có hai lô, cùng 160 điều kiện (mức 0 và 1, seed train 100–179, mỗi điều kiện một lượt, `style_base` 0, cùng seed phong cách), rtx3060, 3/11/2026. **Bộ demo cha cho S2 là `parents-1103b`** **[Đã chốt]** (PO chọn 3/11/2026): cùng planner với mã đang commit và với S1 của DA-33, một kiểu cầm duy nhất. `parents-1103` (D-19) giữ để tham khảo, không trộn vào S2. Cả hai lô đã bị thay thế (PO review PR #84, 4/11/2026): chúng chạy khi trạng thái hiệu chuẩn của decoupled_wbc còn rò giữa các episode, và sẽ được sinh lại sau bản sửa ở nhiệm vụ 10 của DA-35 ([s2.md](s2.md)).

| Đo | `parents-1103b` (D-25, mã hiện hành) | `parents-1103` (D-19, trước khi rebase) |
|---|---|---|
| `operator_version` | `da35-virtual-1+cfg.69a57a6c` | `da35-virtual-1+cfg.cdc6ee44` |
| Đạt `check_success` | 129/160 (80,6%) | 139/160 (86,9%) |
| Demo cha đủ 7 cờ bước | **129**: mức 0 62/80, mức 1 67/80 | 138: mức 0 68/80, mức 1 70/80 |
| Hỏng | `L-TRAY-TILT` 16, `timeout:ARRIVE_B` 11, `L-PLACE-POSE` 3, `timeout:RELEASE` 1 | `timeout:ARRIVE_B` 15, `L-PLACE-POSE` 4, `L-TRAY-TILT` 2 |
| Dữ liệu (rtx3060, `~/denso-da35/fwdata/simple/tray/virtual/`, không commit) | 129 episode, 203 782 frame (1,13 giờ ở 50 Hz), 1,2 GB | 139 episode, 228 844 frame (1,27 giờ), 1,4 GB |
| Meta | Cả lô: `synthetic`, `S1`, `virtual_teleop`, `planned`, `train`, `public`; mỗi episode một seed phong cách | Như bên trái |
| Lô (thực) | 18,6 phút (0,311 giờ), 16 worker | 20,7 phút (0,345 giờ), 14 worker |
| Giây worker | 4,35 giờ; **121 s mỗi demo cha** | 4,21 giờ; 110 s mỗi demo cha |
| Máy dùng chung | Hai server Ψ₀ của phiên khác (GPU và CPU) | Một server Ψ₀ trên GPU |

Một lượt chạy 2,9–3,2 lần chậm hơn thời gian thực khi chạy 14–16 worker (94–98 s thực cho 30–33 s sim). Kiểm tra trước lô D-25 trên 16 điều kiện của nhiệm vụ 6: 15/16 đạt, cả 15 đủ cờ (một `timeout:ARRIVE_B`).

Sổ chi phí: [DA-35.csv](../ledger/DA-35.csv) (mỗi lô một dòng ước lượng trước khi chạy và một dòng đo).

Khoảng trống đã biết:

- Với D-25, `L-TRAY-TILT` thành lỗi chính (10%): PICO chỉ có ba kiểu đóng bàn tay cố định, kiểu "middle" giữ khay ngửa tay kém chắc hơn khi quay và đi. Chưa chỉnh; đủ demo cha cho S2.
- `timeout:ARRIVE_B` (7–9%): planner bước tới khi khay cách đích dưới 2 cm và thân lắc khi bước.
- Khi lượt **cuối** của một shard hỏng, bộ xuất của SIMPLE vẫn ghi video của episode bị bỏ (`parents-1103`: 2 file thừa ở `shard-02` episode 11 và `shard-06` episode 8). Meta và parquet không có chúng; công cụ đọc theo `meta/episodes.jsonl` thì không ảnh hưởng.
- Bảng chỉnh ở nhiệm vụ 6 đo với planner D-19; với D-25 chỉ đo lại bản cuối (15/16).
