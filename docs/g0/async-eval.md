# Đánh giá vòng kín đồng bộ và bất đồng bộ

Runner closed-loop eval của làn Vòng có hai chế độ định thời (DA-23, 03 ADR-20, design 27/10 mục 8.5). Mã ở `packages/flywheel-loop/src/flywheel/loop/runner/`.

## 1. Vì sao cần chế độ bất đồng bộ

Ψ₀ cần khoảng 160 ms mỗi lần suy luận (số tác giả báo) và dùng real-time chunking (RTC). SIMPLE bước sim đồng bộ: trong lúc client RTC chờ chunk, sim không chạy. Vì vậy trace của sim không bao giờ cho thấy một chunk về muộn. Trên robot thật, trong lúc chờ, robot vẫn chạy nốt các action còn trong buffer; hết buffer mà chunk mới chưa về thì robot không có action để chạy (buffer cạn, mã R2).

| Chế độ | Dùng cho | Chỉ số |
|---|---|---|
| `sync` | G0 (`g0_repro`) và HE (`he`), để so được với tác giả | `sim_success` của sim |
| `async` | Các nhánh HS, HT (`branch_train`, `round`, `holdout`) | `sim_success` của sim, rồi xét lại bằng log RTC (mục 3) |

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

Ở chế độ `async`, runner kiểm log trước khi chấm. Log hỏng thì rollout bị báo `infra_status = policy_error`, `sim_success = None`, lý do ghi vào `runner.json`, và lần chạy sau sẽ chạy lại. Log bị coi là hỏng khi:

- không có file, file rỗng, hoặc có dòng không đúng schema;
- `job_id` hoặc `trace_id` khác với rollout;
- `chunk_index` không đếm 0, 1, … theo thứ tự;
- request gửi đi trước khi chunk trước về (client chỉ có một request mỗi lúc);
- `delay_steps` khác `ceil((chunk_received_s − observation_sent_s) × hz)`;
- `buffer_level` lớn hơn kích thước chunk.

`hz` và kích thước chunk lấy từ `PolicySpec`.

## 3. Chấm ở chế độ bất đồng bộ

**[Đề xuất]** Runner phát lại log trên đồng hồ thời gian thực. Với chunk thứ k ≥ 1, robot không có action trong `max(0, delay_steps − buffer_level)` bước. Chunk 0 không tính, vì robot chưa chạy. Tổng số bước này lớn hơn `max_starved_steps` trong `configs/loop/eval.yaml` (mặc định 0) thì rollout hỏng ở chế độ `async`, dù sim báo thành công. `runner.json` giữ cả kết quả của sim (`adapter_sim_success`) và tóm tắt lịch (`rtc`: số chunk, độ trễ lớn nhất, số bước và số chunk bị cạn).

Hệ quả: client gửi request khi buffer đã hết (`refill_at = 0`) thì mọi độ trễ khác 0 đều làm robot dừng sau mỗi chunk. Muốn qua, client phải gửi request sớm, khi buffer còn ít nhất `delay_steps` action. Ví dụ: chunk 16, 50 Hz, trễ 160 ms (8 bước) thì cần gửi khi buffer còn 8.

Với độ trễ bằng 0, log có `delay_steps = 0` ở mọi chunk, nên hai chế độ cho cùng kết quả trên cùng seed.

Chèn độ trễ vào chính lúc bước sim (`timing` phía sim) thuộc story 3.1a. Khi có phần đó, `sim_success` của sim cũng phản ánh độ trễ, còn phép kiểm ở mục này vẫn giữ nguyên.

## 4. Bộ đệm kết quả

Runner dùng lại kết quả chỉ khi `runner.json` có cùng khóa và `infra_status = ok`. Khóa là hash của request (chế độ, seed, điều kiện, giới hạn bước), endpoint policy (chứa mã checkpoint), simulator, config eval, `hz`, kích thước chunk và nội dung file profile trễ. Khóa khác thì runner xóa thư mục job rồi chạy lại, vì client RTC ghi thêm vào `rtc.jsonl`.

## 5. Cấu hình

`configs/loop/eval.yaml` khai chế độ theo mục đích của RunPlan, `hz` và kích thước chunk dùng khi không có `PolicySpec`, các profile trễ, và `max_starved_steps`. Khóa lạ trong file bị từ chối.
