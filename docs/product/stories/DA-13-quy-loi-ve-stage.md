# DA-13 · Kiểm hệ thống F-SYS và quy lỗi về stage trong `diagnosis`

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 28/10/2026, từ nháp của Châu ở issue #6) |
| Người làm | Châu |
| Làn | Đánh giá |
| Story PRD | 9.13 · Epic 9 · FR55; [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 8.3, 10; spec mục 6.4 |
| Nhãn | [Lõi] · `epic:9` · `gate:G4` · `area:core` |
| Sprint | S3 · **Lịch 3/11/2026:** kéo lên S2: merge trước **10/11/2026** cho phần 6 của demo (thay S3) |
| Ước lượng | 9 giờ (khoảng 8–10, 07 mục 2.2) |
| Phụ thuộc | DA-25 (file mẫu probe, log RTC); DA-09 (probe P1–P4 thật; **3/11/2026:** dời sau demo, phần quy lỗi theo probe của demo chạy trên file mẫu probe của DA-25); DA-08 (cờ T7); `Trace` từ SIMPLE (khoảng 6/11). **3/11/2026:** hợp đồng `TraceStep`, `CameraParams` và 4 file mẫu (issue #31, Long, 6/11); hook `SimpleSim` ghi trace thật (Hiếu, 8/11). Trên psi-data chỉ R3 thân trên tính được; R3 thân dưới, R4, R5 ra CHƯA RÕ vì gói không ghi tín hiệu đo. Trong lúc chờ code trên file mẫu |

## Story

Là kỹ sư đánh giá, tôi muốn mỗi cụm lỗi closed-loop được kiểm hệ thống trước (R1–R6), rồi gắn giả thuyết về stage của Ψ₀ gây lỗi kèm bằng chứng probe, để evidence card chỉ đề xuất dữ liệu khi lỗi không đến từ hệ thống.

## Tiêu chí chấp nhận

1. Kiểm F-SYS chỉ từ log, đúng thứ tự spec mục 6.4: thiếu tín hiệu → sai số bám lệnh (R3, tách thân trên và thân dưới) → độ trễ (R1, R2) → đồng bộ cảm biến (R4) → camera chuẩn (R5). Thiếu tín hiệu cho ra CHƯA RÕ. R6 (server lỗi) ghi `infra_status`, không tính là lỗi policy.
2. Ngưỡng τ_track, τ_lat, τ_sync và bản tham chiếu camera nằm trong `configs/eval/diagnosis/system.yaml`, có hash; τ lấy phân vị 99 trên episode teleop thành công hoặc lần chạy chuẩn G0, ghi cách tính.
3. Cụm đã qua kiểm hệ thống và kiểm dữ liệu được gắn giả thuyết stage theo bảng quy lỗi (P1, P3, P4, T7, ngoài miền), mỗi giả thuyết kèm bằng chứng: probe nào, trên khung hình hay episode nào, giá trị.
4. Giả thuyết là đề xuất cho kỹ sư xác nhận trên evidence card; không tự chuyển thành can thiệp.
5. Trên bộ lỗi cấy hệ thống: trễ camera ra LỖI ĐỒNG BỘ, lệch calibration ra LỖI CALIBRATION; episode sạch không bị báo lỗi hệ thống (spec mục 7.6).
6. Chạy trên CPU với `Trace` và kết quả probe mẫu của testkit.
7. (Thêm 5/11/2026, quyết định (a), (b) của PO.) R1, R2 đo theo RTC thật của Ψ₀ trên cấu hình serve của đội: R2 so `delay_steps` với độ trễ RTC d của server, ghi trong `system.yaml` kèm nguồn; chunk 0 của trace không tính vào R1 lẫn R2. Trên rollout đồng bộ, R1, R2 vẫn đo và ghi nhưng là **ghi nhận, không quy lỗi**: không chặn quy lỗi về dữ liệu. Chỉ rollout bất đồng bộ (DA-23) tính R1, R2 là lỗi hệ thống. Episode không rõ chế độ không được coi là đồng bộ (FR21). Trên bộ lỗi cấy DA-27, lỗi R1 chỉ ra R1, lỗi R2 chỉ ra R2.

## Nhiệm vụ

- [x] 1. Bộ đọc `Trace`, log RTC, kết quả probe qua contracts (AC 1, 3)
- [x] 2. Kiểm thiếu tín hiệu và R3 sai số bám lệnh (AC 1)
- [x] 3. R1, R2 độ trễ và buffer; R4 đồng bộ; R5 camera; R6 hạ tầng (AC 1)
- [x] 4. Cấu hình ngưỡng có hash (AC 2)
- [x] 5. Bảng quy lỗi về stage, bằng chứng gắn kèm (AC 3, 4)
- [x] 6. Test trên lỗi cấy hệ thống và đối chứng sạch (AC 5, 6)
- [x] 7. `api.py`, lệnh `fw eval diag-system` và artifact kết quả của hai bước (AC 1-4). Phạm vi file đã có `api.py`, `cli.py` nhưng không nhiệm vụ con nào dùng tới; phần 6 của demo cần một điểm vào
- [x] 8. Issue Contract change cho bản ghi kết quả (**issue #70**): `DiagnosisFinding.code` của `flywheel.contracts.training` là `Literal` trên T1-T8, O1-O4 nên mã R không vào được `TrainDiagnosis`; 03 mục 4.3 để `CheckResult` trong `meta` của Cluster (Long giữ). Trong lúc chờ, bản ghi nằm trong làn như `ScoreRecord` của DA-36
- [x] 9. Đổi bộ đọc sang `flywheel.contracts.trace.TraceStep`, `CameraParams` khi #48 merge (PR #79): bỏ `TraceRow`, `CameraView` của làn; test đọc file mẫu trace của testkit trên master thay cho bản chép (AC 1, 3)
- [x] 10. R3 nửa dưới: so hướng thân `yaw` theo đường ngắn quanh vòng tròn (atan2(sin d, cos d)), để ±π không đọc thành gần 2π sai số; khớp hông không quấn vì là khớp có giới hạn (AC 1)
- [x] 11. R1, R2 theo RTC thật của Ψ₀ (review PO 5/11/2026; quyết định (a), (b) của PO) (AC 7)
  - [x] 11.1 R2 so `delay_steps` với d của server: khóa `r2.rtc_inference_delay_steps: 6` trong `system.yaml`, comment dẫn `serve_psi0_simple.py:161-171` ở Ψ₀ `cda3fdf` và cờ serve `--action-exec-horizon 24 --rtc` (Tp 30, s = Ta = 24, max_delay 8, nên d = max(1, min(24 // 2, 30 - 24, 8 - 1)) = 6); đứng máy là `delay_steps > d`. Chunk 0 ra khỏi R2 và khỏi phân vị của R1; test: chỉ chunk 0 chậm thì không ra mã nào
  - [x] 11.2 Rollout đồng bộ: R1, R2 cho kết quả ghi nhận, không chặn (`verdict.py`), detail tiếng Việt nói lý do; rollout bất đồng bộ tính như cũ. Chế độ lấy từ hợp đồng (`RolloutRequest.timing`, `RolloutResult.timing_verdict`); không rõ chế độ thì không coi là đồng bộ. Nếu hợp đồng chưa có trường để phân biệt: dừng, viết đề xuất hợp đồng cho Long, Hiếu, không thêm trường trong code làn
  - [x] 11.3 DA-27: lỗi cấy R1 và R2 tách được theo luật mới. R1 trễ kéo dài mà không chunk nào vượt d, nên τ_lat ≤ d / hz = 0,12 s (đề xuất τ_lat 0,10 s, giả định; độ trễ cấy 0,11 s, `delay_steps` 6); R2 không cấy ở chunk 0. Cập nhật `docs/g0/defect-inject.md`; kiểm `agentqa/bench/logs.py` của DA-31 (nhánh `DA-31-defect-bench-scorer`, chỉ đọc) không đếm chéo
  - [x] 11.4 Sửa câu `inference_delay = Tp - Ta` và câu so với `max_delay` trong docstring `flywheel_psi0/policy/rtc.py`; thêm một dòng ở design 27/10 mục 10 kèm ghi chú sửa

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/diagnosis/system/`, `packages/flywheel-eval/src/flywheel/eval/diagnosis/stage/`
- `packages/flywheel-eval/src/flywheel/eval/api.py`, `packages/flywheel-eval/src/flywheel/eval/cli.py`, `packages/flywheel-eval/src/flywheel/eval/config.py`
- `packages/flywheel-eval/tests/unit/diagnosis/system/`, `packages/flywheel-eval/tests/unit/diagnosis/stage/`
- `packages/flywheel-eval/tests/contract/diagnosis/system/` (thêm 3/11/2026 cùng nhiệm vụ con 7: lệnh `fw eval diag-system` phải có test lái qua CLI, như DA-36 có `tests/contract/scorer/`)
- `configs/eval/diagnosis/system.yaml`, `configs/eval/diagnosis/stage.yaml`
- Thêm 5/11/2026 cho nhiệm vụ con 11: bộ cấy lỗi RTC của DA-27 `packages/flywheel-data/src/flywheel/data/inject/config.py`, `packages/flywheel-data/src/flywheel/data/inject/log_defects.py`, `packages/flywheel-data/tests/unit/inject/test_log_defects.py`, `tests/e2e/test_log_defects_detected.py`, `docs/g0/defect-inject.md`; docstring `packages/flywheel-psi0/src/flywheel_psi0/policy/rtc.py`; một dòng mục 10 và ghi chú sửa của `docs/superpowers/specs/2026-10-27-g1-psi0-demo-design.md`

## Ghi chú cho người làm

- Nguồn: spec mục 6.4 (thứ tự kiểm hệ thống, bước 4b), 7.6 (nghiệm thu trên lỗi cấy); design 27/10 mục 8.3, 10.
- **Bảng quy lỗi về stage** [Đã chốt 30/10/2026]: dùng một bảng chung ở spec v10.5 mục 6.4 và design mục 10 (năm dòng: Stage 1, Stage 3 học action, lệch phân phối, quên, ngoài miền). Dòng Stage 1 chỉ ghi nhận và báo cáo, không đề xuất can thiệp dữ liệu. Bảng vẫn để trong `stage.yaml` để đổi không cần sửa mã, nhưng chỉ một bản, không có khóa chọn biến thể.
- Trường "lệnh gửi" và "trạng thái đo" của WBC chốt ở G0 theo agent `psi0_decoupled_wbc` (spec 6.4); trước đó dùng trường của `Trace` mẫu.
- Chỉ import nhân; `diagnosis/` dùng chung với DA-08: story này chỉ sửa `diagnosis/system/` và `diagnosis/stage/`.

## Kiểm thử

- Lỗi cấy hệ thống ra đúng lớp; episode sạch không bị báo; chạy CPU.

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (DA-09 probe, `Trace`), Long (`decide`, evidence card), Thông (bộ lỗi cấy DA-27)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 28/10/2026 | Nháp story theo spec mục 6.4 và design 27/10 mục 10 | Châu (chờ SM, PO) |
| 28/10/2026 | Đưa nháp của Châu (issue #6) vào repo; nhãn theo 02 bản 0.5 (story 9.13, Epic 9, cổng G4). Bảng quy lỗi về stage (spec 6.4 khác design mục 10) chưa chốt, để trong `stage.yaml` | PO (Hiếu) |
| 30/10/2026 | Chốt bảng quy lỗi về stage theo spec v10.5 mục 6.4 (khớp design mục 10); sửa ghi chú cho người làm | PO (Hiếu) |
| 3/11/2026 | Hạn mới theo lịch hoàn thiện 13/11/2026 (07 mục 2.4) | PO (Hiếu) |
| 3/11/2026 | Phụ thuộc: hợp đồng `TraceStep`, `CameraParams` (issue #31) và hook `SimpleSim`; nguồn tín hiệu R3–R5 trên psi-data | PO (Hiếu) theo issue #31 |
| 3/11/2026 | DA-09 dời sau demo: probe của demo dùng file mẫu (07 mục 2.4, bản 1.2) | PO (Hiếu) |
| 3/11/2026 | Phạm vi file: thêm `packages/flywheel-eval/tests/contract/diagnosis/system/` cho test lái lệnh `fw eval diag-system` của nhiệm vụ con 7 (pr-guard R6) | Châu |
| 3/11/2026 | Thêm nhiệm vụ con 7 (`api.py`, `fw eval diag-system`, artifact) và 8 (issue Contract change cho bản ghi kết quả). Nhiệm vụ 1-6 không phủ `api.py`, `cli.py` dù hai file nằm trong phạm vi, và phần 6 của demo cần điểm vào. `TraceStep`, `CameraParams` (issue #31, PR #48) chưa merge nên bộ đọc giữ đúng tên trường của đề xuất, đổi sang contract khi #48 merge | Châu |
| 3/11/2026 | Sửa theo review PO của PR #71 (14 lỗi), theo quyết định Q1–Q3 của PO: R6 đứng đầu, nhãn `infra` khi `infra_status` khác `ok` (Q1); R2 đếm chunk có `delay_steps > buffer_level`, bỏ `r2.min_buffer_level` (Q2, sau đó sửa, xem dòng dưới); `CameraParams.reference_sha256` là hash bản tham chiếu ghim ở G0, R5 so hash rồi so giá trị trong dung sai (Q3). Bộ đọc coi `t_image: null` là không có khung mới, lọc `rtc.jsonl` theo `trace_id`, hash mọi file đầu vào; R3 bỏ qua theo nửa thân; `episode.json` ghi là tạm thời chờ hook DA-38. Test đọc 4 file mẫu trace của PR #48 (chép làm dữ liệu test của làn) | Hiếu, cùng Claude |
| 3/11/2026 | Q2 sửa lại, PO chốt: R2 đếm chunk có `delay_steps > max_delay_steps` (`r2.max_delay_steps: 8`, max_delay của Ψ₀ stage 3), không đọc `buffer_level` vì nó luôn bằng 0 khi SIMPLE hỏi server lúc hàng đợi rỗng; giữ `max_underruns` | Hiếu, cùng Claude |
| 3/11/2026 | Theo hook SimpleSim (DA-38, nhánh `DA-38-trace-hook-v2` @ `f94d5bc`): ghim khối `r5` của `system.yaml` bằng bản tham chiếu G0 task hai bàn (`fc7f9c90…`, `head_stereo_left`/`right`); bộ đọc theo bố cục `<job>/rtc.jsonl` và `<job>/<episode>/`, đọc `episode.json` qua `RolloutResult` v0 | Hiếu, cùng Claude |
| 3/11/2026 | Bộ đọc theo quyết định G1 của PO trên PR #48: trace là thư mục `<trace_id>/` gồm `steps.jsonl` và `camera_params.jsonl` (mỗi dòng một camera, có `trace_id`); `RolloutResult` đọc từ `<trace_id>/rollout_result.json` (đề xuất, chờ PO chốt); `rtc.jsonl` ở thư mục job. Tên file là hằng số trong `reader.py` | Hiếu, cùng Claude |
| 3/11/2026 | Bộ đọc kiểm `trace_ref` của `RolloutResult` (đúng `trace_id`, `uri` trỏ đúng thư mục `<trace_id>/`, `sha256` khớp `steps.jsonl`), sai thì báo lỗi; nhận thư mục trace hoặc file `rollout_result.json` làm đầu vào. Test nối với đầu ra thật của hook DA-38 (`207e276`) | Hiếu, cùng Claude |
| 3/11/2026 | PO chốt G1b: `RolloutResult` ở `<job_dir>/<trace_id>/rollout_result.json`; `ROLLOUT_NAME` của `reader.py` và ghi chú bố cục ghi là đã chốt | Hiếu, cùng Claude |
| 4/11/2026 | Thêm nhiệm vụ con 9 và làm xong: #48 merge thành PR #79, bộ đọc nhận mỗi dòng `steps.jsonl` qua `TraceStep` và mỗi dòng `camera_params.jsonl` qua `CameraParams`; bỏ `TraceRow`, `CameraView`. Dòng hợp đồng từ chối (thiếu trường, vector khác 28/7 kênh, `NaN` trần của JSON, vector null) báo lỗi kèm số dòng; chuỗi `"NaN"`, `"Infinity"`, `"-Infinity"` vẫn là chỗ thiếu tín hiệu, `t_image: null` vẫn là không có khung mới. Tên file trong `<trace_id>/` lấy từ hợp đồng. Test đọc 4 file mẫu trace của testkit với `system.yaml` như khi phát hành; bỏ bản chép `data/trace_pr48/` | Hiếu, cùng Claude |
| 4/11/2026 | Thêm nhiệm vụ con 10 và làm xong, theo kiểm tra đầu cuối của PO trên master + #71 + hook #80: lệnh `yaw` 3,13 rad với `yaw` đo -3,13 rad (lệch 0,023 rad) ra lỗi bộ điều khiển [R3] vì sai số trừ thẳng giá trị thô. Kênh có tính tuần hoàn chọn theo tên trong `LOWER_BODY` của hợp đồng (`PERIODIC_CHANNELS` trong `reader.py`); chỉ `yaw` (hướng thân, hệ thế giới). Khớp hông roll, pitch, yaw có giới hạn (±0,52; ±2,618 rad trong `configs/embodiments/g1.yaml`) nên không quấn: sai số trên π của khớp là khoảng khớp phải đi thật | Hiếu, cùng Claude |
| 5/11/2026 | Thêm AC 7 và nhiệm vụ con 11, theo review PO trên Ψ₀ `cda3fdf`: độ trễ `/act` đo được 350 ms (máy) và 460 ms (qua tunnel), `delay_steps` khoảng 18 ở 50 Hz, nên R1 và R2 bắn trên mọi episode thật, trong khi SIMPLE bước sim đồng bộ nên độ trễ không gây được hỏng trong sim (như R4). R2 so với d = 6 của server, không với max_delay 8 (đúng ra là `d < max_delay` và sai đại lượng); `7226dc78` làm mất phần bỏ chunk 0 của `48486ede`. Quyết định (a): trên rollout đồng bộ R1, R2 ghi nhận, không quy lỗi; (b): ngưỡng của R2 là d của server, ghi trong config cùng nguồn, kiểm với `/info` lúc serve nếu làm được. Phạm vi file thêm bộ cấy lỗi RTC của DA-27, docstring `rtc.py` và một dòng design mục 10 | Hiếu, cùng Claude |

## Ghi chép khi làm

- Giờ thực: 15h (nhiệm vụ 1-7; ước lượng story là 9h, vượt vì hai bộ ngưỡng và bảng quy lỗi đều phải có test đối chứng)
- Công cụ AI đã dùng: Claude Code (Opus 5)
- Ghi chú sau review PO (3/11/2026): R2 không đọc `buffer_level`, vì SIMPLE chỉ hỏi server khi hàng đợi action rỗng nên mức này luôn bằng 0; R2 so `delay_steps` với `max_delay` của Ψ₀ (8 ở stage 3), kiểm lại khi đổi checkpoint. Trên rollout SIMPLE, R4 luôn bằng 0 do sim chạy đồng bộ (`t_image = t_state`); "R4 sạch" trên sim không phải bằng chứng đã kiểm đồng bộ cảm biến. P1 hiện là số trên cả tập probe; P1 theo từng lượt là đề xuất hợp đồng (issue #70). Vế "lỗi mới sau fine-tune" của dòng 4 chưa kiểm.
- **Điểm mở cho Hiếu (4/11/2026):** `cmd_lower` của `yaw` là hướng đích của WBC (`target_yaw`), không phải hướng thân tức thời; khi robot đang quay bình thường, lệnh đi trước hướng đo, nên sai số bám lệnh nửa dưới lớn lên mà bộ điều khiển không hỏng. `tau_track_lower` vì vậy phải hiệu chỉnh trên các lượt chạy có quay (đoạn đi sang bàn kia), không chỉ trên lượt đứng yên; trước khi hiệu chỉnh, R3/lower trên lượt có quay có thể báo nhầm. Cần quyết định: hiệu chỉnh ngưỡng chung, hay tách `yaw` khỏi chuẩn chung của nửa dưới.
- **Điểm mở cho Long, Hiếu (5/11/2026, nhiệm vụ con 11.2): đề xuất hợp đồng [Đề xuất].** Hợp đồng chưa phân biệt được rollout đồng bộ với bất đồng bộ: `RolloutResult.timing_verdict` là None cả khi sync lẫn khi producer không ghi, hook SimpleSim ghi `rollout_result.json` trước khi runner của DA-23 điền nó, và `RolloutRequest.timing` không được ghi ra đĩa. `SystemDiagnosis` cũng không có chỗ cho R1, R2 "ghi nhận, không quy lỗi" (validator từ chối `clean` khi có finding). Đề xuất: `RolloutResult.timing` (adapter chép từ `RolloutRequest.timing`); `SystemDiagnosis.timing`, `recorded`, `recorded_skipped`. Trong lúc chờ: `verdict.py` đã có đường ghi nhận, không chặn cho rollout sync (có test); bộ đọc chỉ đọc async khi có `timing_verdict`, còn lại là không rõ, R1, R2 tính như async và detail nói chế độ không rõ; `build_system_record` từ chối verdict có R1, R2 ghi nhận thay vì bỏ chúng. Hệ quả cho phần 6 của demo: tới khi hợp đồng đổi, mọi episode thật vẫn ra `runtime` vì độ trễ `/act` đo 350–460 ms (`delay_steps` khoảng 18, trên d = 6).
- Kiểm d với `/info` lúc serve (quyết định (b), "nếu làm được"): ngoài phạm vi file của DA-13 (client RTC của DA-19 hoặc client eval của DA-26 đọc `rtc_inference_delay` của `/info` và so với `r2.rtc_inference_delay_steps`); đề xuất PR riêng.
- Bố cục trace mà `diagnosis/system` đọc (quyết định G1 trên PR #48; tên file lấy từ `flywheel.contracts.trace`, xuất lại trong `reader.py`): `<job_dir>/<trace_id>/steps.jsonl` (mỗi dòng một `TraceStep`), `<job_dir>/<trace_id>/camera_params.jsonl` (mỗi dòng một `CameraParams`, có `trace_id`; không có file thì R5 ra CHƯA RÕ), `<job_dir>/<trace_id>/rollout_result.json` (`RolloutResult` v0; tên file đã chốt 3/11/2026 [Hiếu], G1b) và `<job_dir>/rtc.jsonl` (DA-19, ghép theo `trace_id`). `trace_ref.uri` trỏ thư mục `<trace_id>/`, `trace_ref.sha256` là sha256 của `steps.jsonl`.
- Ghi chú hoàn thành: AC 1-6 đạt trên trace tổng hợp và file mẫu probe của testkit. Chưa chạy trên `Trace` thật của SIMPLE (hook của Hiếu, 8/11) và chưa chạy trên probe thật (DA-09 dời sau demo). R5 dùng bản tham chiếu camera G0 của task hai bàn (SIMPLE `b75c678`, ghim 3/11/2026); task khác ra CHƯA RÕ cho tới khi được ghim. Mọi ngưỡng trong hai file config là giả định, cách hiệu chỉnh ghi ngay trên dòng.
- File đã tạo hoặc sửa:
  - `packages/flywheel-eval/src/flywheel/eval/diagnosis/system/`: `reader.py`, `verdict.py`, `signals.py`, `tracking.py`, `runtime.py`, `check.py`, `artifact.py`
  - `packages/flywheel-eval/src/flywheel/eval/diagnosis/stage/`: `attribute.py`, `artifact.py`
  - `packages/flywheel-eval/src/flywheel/eval/`: `config.py`, `api.py`, `cli.py`
  - `configs/eval/diagnosis/system.yaml`, `configs/eval/diagnosis/stage.yaml`
  - `packages/flywheel-eval/tests/unit/diagnosis/system/`, `packages/flywheel-eval/tests/unit/diagnosis/stage/`, `packages/flywheel-eval/tests/contract/diagnosis/system/`
