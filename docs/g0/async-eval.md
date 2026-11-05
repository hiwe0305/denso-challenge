# Đánh giá vòng kín đồng bộ và bất đồng bộ

Runner closed-loop eval của làn Vòng có hai chế độ định thời (DA-23, 03 ADR-20, design 27/10 mục 8.5). Mã ở `packages/flywheel-loop/src/flywheel/loop/runner/`.

## 1. Vì sao cần chế độ bất đồng bộ

Ψ₀ cần khoảng 160 ms mỗi lần suy luận (số tác giả báo) và dùng real-time chunking (RTC). SIMPLE bước sim đồng bộ: trong lúc client RTC chờ chunk, sim không chạy. Vì vậy trace của sim không bao giờ cho thấy một chunk về muộn. Trên robot thật, trong lúc chờ, robot vẫn chạy nốt các action còn trong buffer; hết buffer mà chunk mới chưa về thì robot không có action để chạy (buffer cạn, mã R2).

| Chế độ | Dùng cho | Chỉ số |
|---|---|---|
| `sync` | G0 (`g0_repro`) và HE (`he`), để so được với tác giả | `sim_success` của sim |
| `async` | Các nhánh HS, HT (`branch_train`, `round`, `holdout`) | `sim_success` của sim và kết luận định thời từ log RTC (mục 3) |

`Runner.run_plan_eval` chọn chế độ từ `RunPlan.purpose` qua `EvalConfig` và yêu cầu `latency_profile_ref` khi chọn `async`; profile nghiệm thu phải lấy từ log RTC thật. Hàm tạo request mới và giữ nguyên request đầu vào. Hiện contract `RunPlan` chưa lưu timing và profile trong bản đóng băng, cũng chưa có purpose `he`; vì vậy API này chưa thay thế việc chốt contract để tái lập và chưa hoàn tất AC 4.

## 2. Thư mục job và log RTC

Mỗi rollout có một thư mục job `<staging_root>/<job_id>/`. Simulator adapter và client RTC của policy (DA-19, `flywheel_psi0/policy/rtc.py`) phải dùng chung thư mục này. Client ghi thêm (append) một `RTCInferenceRecord` cho mỗi chunk vào `<job_dir>/rtc.jsonl`. Làn Vòng chỉ đọc log qua hợp đồng `RTCInferenceRecord`, không import adapter.

| Trường | Nghĩa (theo client DA-19) |
|---|---|
| `job_id`, `trace_id` | Job và trace của rollout |
| `chunk_index` | 0, 1, … trong trace |
| `observation_sent_s`, `chunk_received_s` | Giây tính từ đầu trace |
| `delay_steps` | `ceil(độ trễ × hz)`: số bước điều khiển trôi qua trong lúc suy luận |
| `buffer_level` | Số action còn trong buffer khi gửi request |
| `boundary_jump` | Thay đổi lớn nhất theo từng chiều giữa action cuối của chunk cũ và action đầu của chunk mới |

Ở chế độ `async`, runner kiểm log trước khi chấm. Log hỏng thì rollout có `timing_verdict = not_checked`. `sim_success` và `infra_status` vẫn là của adapter: sim và policy đã chạy đúng, chỉ phần định thời là không chấm được, nên rollout không bị tính là lỗi hạ tầng (R6 của DA-13). Lý do ghi vào `runner.json`, và lần chạy sau sẽ chạy lại. Log bị coi là hỏng khi:

- không có file, file rỗng, hoặc có dòng không đúng schema;
- `job_id` hoặc `trace_id` khác với rollout;
- `chunk_index` không đếm 0, 1, … theo thứ tự;
- request gửi đi trước khi chunk trước về (client chỉ có một request mỗi lúc);
- `delay_steps` khác `ceil((chunk_received_s − observation_sent_s) × hz)`;
- `buffer_level` lớn hơn kích thước chunk.

`hz` và kích thước chunk lấy từ `PolicySpec`.

## 3. Chấm ở chế độ bất đồng bộ

**[Đã chốt 3/11/2026]** Runner phát lại log trên đồng hồ thời gian thực. SIMPLE bước sim đồng bộ, và client RTC chỉ xin chunk khi buffer đã hết (`refill_at = 0`, giống code tác giả), nên `buffer_level` trong log luôn bằng 0 và không nói gì về phần cứng. Runner giả định một client phần cứng gửi request khi buffer còn `refill_level` action (`configs/loop/eval.yaml`, bằng 8, là `max_delay` của Ψ₀ stage 3 theo [psi0-logging.md](psi0-logging.md), cùng số DA-13 dùng cho R2), và chạy nốt số action đó trong lúc suy luận.

| Đại lượng | Cách tính |
|---|---|
| Bước bị cạn ở chunk k ≥ 1 | `max(0, delay_steps − refill_level)`; `refill_level` không vượt kích thước chunk |
| Chunk 0 | Không tính, vì robot chưa chạy |
| Kết luận định thời | `starved` khi tổng số bước bị cạn lớn hơn `max_starved_steps` (mặc định 0); còn lại `ok` |

Ví dụ: chunk 16, 50 Hz. Trễ 3 bước không làm cạn. Trễ 9 bước làm cạn 1 bước ở mỗi chunk từ chunk 1.

Kết quả nằm trong `RolloutResult` (03 bản 1.1, quyết định E2):

| Trường | `sync` | `async`, log dùng được | `async`, không có log dùng được |
|---|---|---|---|
| `sim_success` | Kết luận của sim | Kết luận của sim | Kết luận của sim |
| `infra_status` | Của adapter | Của adapter | Của adapter |
| `timing_verdict` | `None` | `ok` hoặc `starved` | `not_checked` |
| `starved_steps` | `None` | Tổng số bước bị cạn | `None` |

"Không có log dùng được" gồm cả rollout mà chính adapter đã báo `infra_status` khác `ok`; runner giữ nguyên mã đó. `runner.json` giữ một bản sao của `timing_verdict` cùng tóm tắt lịch (`rtc`: số chunk, độ trễ lớn nhất, `refill_level`, số bước và số chunk bị cạn) để tra lại.

Với độ trễ bằng 0, log có `delay_steps = 0` ở mọi chunk, nên hai chế độ cho cùng kết quả trên cùng seed.

Chèn độ trễ vào chính lúc bước sim (`timing` phía sim) thuộc story 3.1a. Khi có phần đó, `sim_success` của sim cũng phản ánh độ trễ, còn phép kiểm ở mục này vẫn giữ nguyên.

## 4. Bộ đệm kết quả

Runner dùng lại kết quả chỉ khi `runner.json` có cùng khóa, `infra_status = ok` và `timing_verdict` khác `not_checked`. Khóa là hash của request (chế độ, seed, điều kiện, giới hạn bước), endpoint policy (chứa mã checkpoint), simulator, config eval, `hz`, kích thước chunk và nội dung file profile trễ. Khóa khác thì runner xóa thư mục job rồi chạy lại, vì client RTC ghi thêm vào `rtc.jsonl`.

## 5. Cấu hình

`configs/loop/eval.yaml` khai chế độ theo mục đích của RunPlan, `hz` và kích thước chunk dùng khi không có `PolicySpec`, các profile trễ, và `max_starved_steps`. Khóa lạ trong file bị từ chối.
