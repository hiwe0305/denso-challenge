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
