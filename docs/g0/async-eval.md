# Đánh giá vòng kín đồng bộ và bất đồng bộ

Tài liệu kiến trúc runner đánh giá vòng kín (closed-loop eval runner) và hai chế độ định thời (DA-23, 03 ADR-20).

## 1. Bối cảnh và lý tưởng thiết kế

Khi triển khai robot thực tế, việc suy luận chính sách mạng nơ-ron (policy inference) tiêu tốn thời gian tính toán thực tế (khoảng 160 ms cho $\Psi_0$ mỗi lần gọi suy luận trên phần cứng chuẩn). Cơ chế Real-Time Chunking (RTC) truyền các đoạn hành động (action chunk) bất đồng bộ xuống bộ điều khiển robot, trong khi các khung quan sát tiếp theo được xử lý song song.

Mô phỏng đồng bộ truyền thống tạm dừng đồng hồ môi trường mô phỏng trong lúc tính toán đầu ra của policy, dẫn tới việc che giấu các lỗi do độ trễ gây ra:
- Cạn bộ đệm hành động (buffer starvation) và giật điều khiển.
- Phân kỳ trạng thái - hành động tại ranh giới các chunk (boundary jump).
- Vượt quá vị trí mục tiêu (overshooting) ở vận tốc cao do phản ứng chậm.

Nhằm vừa đảm bảo khả năng đối sánh tái lập với kết quả công bố của tác giả, vừa phản ánh đúng kiểm thử hệ thống trong thực tế, runner hỗ trợ hai chế độ đánh giá:
1. **Chế độ đồng bộ (`timing = "sync"`):** Đồng hồ mô phỏng dừng khi suy luận. Được dùng cho bài toán tái lập công thức G0 (`g0_repro`) và thử nghiệm lịch sử (`he`) để so sánh trực tiếp với bài báo gốc.
2. **Chế độ bất đồng bộ (`timing = "async"`):** Mô phỏng độ trễ suy luận chính sách thực tế dựa trên profile đo đạc thực nghiệm từ log suy luận thật. Chế độ này cung cấp chỉ số chính cho toàn bộ các nhánh vòng dữ liệu (`branch_train`, `round`, `holdout`).

## 2. Gom log suy luận thời gian thực (RTC Logging)

Trong chế độ bất đồng bộ, runner gom log viễn trắc suy luận của từng chunk vào `<job_dir>/rtc.jsonl`, tuân thủ hợp đồng `RTCInferenceRecord` và liên kết trực tiếp với `Trace`:
- `job_id`: Mã định danh công việc đánh giá.
- `trace_id`: Khóa liên kết với `TraceRef.trace_id` của bản ghi vết chuyển động.
- `chunk_index`: Chỉ số tăng dần của đoạn hành động.
- `observation_sent_s`: Mốc thời gian mô phỏng khi ảnh/trạng thái được chụp và gửi đi suy luận.
- `chunk_received_s`: Mốc thời gian mô phỏng khi đoạn hành động đến bộ điều khiển robot.
- `delay_steps`: Độ trễ tính theo số chu kỳ điều khiển rời rạc ($round(\text{delay\_s} \times \text{control\_hz})$).
- `buffer_level`: Số lượng hành động còn lại trong hàng đợi bộ đệm tại thời điểm nhận chunk mới.
- `boundary_jump`: Khoảng cách dịch chuyển thực tế giữa vị trí hiện tại và hành động đầu tiên của chunk mới (số thực $\ge 0.0$).

## 3. Cấu hình và tích hợp RunPlan

Cấu hình phân định chế độ được khai báo tập trung trong `configs/loop/eval.yaml`:

```yaml
default_timing: async

timing_by_purpose:
  g0_repro: sync
  he: sync
  branch_train: async
  round: async
  holdout: async

control_hz: 50.0
chunk_size: 16
```

Khi độ trễ được cấu hình bằng 0 (`fixed_delay_s = 0.0`), chế độ bất đồng bộ cho ra quỹ đạo và kết quả toán học hoàn toàn đồng nhất với chế độ đồng bộ trên cùng hạt giống ngẫu nhiên (seed parity).
