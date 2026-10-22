# S1-09 · Tín hiệu từng bước và tập điều kiện đánh giá (V6, V7)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026) |
| Người làm | Châu |
| Story PRD | 1.8 (story mới do PO thêm) · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` · `spike` |
| Sprint | S1, tuần 2 |
| Ước lượng | 8 giờ |
| Phụ thuộc | S1-02. Là đầu vào cho 3.1a, 3.3, 3.4, 2.5 ở S2 |

## Story

Là kỹ sư simulation, tôi muốn biết SIMPLE cho lấy những tín hiệu nào khi rollout và sinh tập điều kiện thế nào, để scorer từng bước và việc chia tập không dựa trên giả định.

## Tiêu chí chấp nhận

1. V7: bảng tín hiệu lấy được khi rollout task chính: lệnh thân trên và lệnh thân dưới gửi cho WBC cùng giá trị đo tương ứng (03 §5.2 `control_spec`, ADR-15), tư thế vật, tiếp xúc tay–vật, va chạm, chiều cao và độ nghiêng thân, timestamp. Mỗi dòng ghi tần số và cách lấy (API, hook).
2. Đối chiếu bảng trên với tín hiệu scorer cần cho 6 bước (spec 5.1) và 9 kiểu lỗi (spec 5.2). Tín hiệu thiếu: dựng lại bằng phát lại trong sim được không; nếu không, scorer hạ xuống mức nào (03 §12.2).
3. V6 phần sim: `Task.reset(seed)` có tất định không: 10 seed, mỗi seed 2 lần, so layout.
4. V6 phần sim: tự sinh được tập điều kiện mới (90 dev, 150 holdout) theo định dạng `simple-eval` không, hay phải dùng tập có sẵn; nếu tự sinh được, ghi dải seed tác giả đã dùng để tránh trùng (05 TH13).
5. Ghi kết quả `decompose()` (`SubtaskSpec`) của task chính và đối chiếu với 6 bước của spec 5.1.
6. Kết quả ở `docs/g0/signals-conditions.md`; cập nhật dòng V6 (phần sim), V7 ở 03 §3.3 có change log.

## Nhiệm vụ

- [ ] 1. Liệt kê tín hiệu (AC 1)
  - [ ] 1.1 Đọc lớp env và robot của task chính; tìm điểm gắn hook ghi tín hiệu
  - [ ] 1.2 Chạy một episode, ghi mẫu từng tín hiệu
- [ ] 2. Đối chiếu với nhu cầu scorer (AC 2)
- [ ] 3. Kiểm `reset(seed)` tất định (AC 3)
- [ ] 4. Thử sinh tập điều kiện theo định dạng `simple-eval` (AC 4)
- [ ] 5. Ghi `decompose()` và đối chiếu bước (AC 5)
- [ ] 6. Viết tài liệu, cập nhật 03 (AC 6)

## Ghi chú cho người làm

- Nguồn: 02 · 1.8 (mới), 2.4, 2.5, 3.3, 3.4; spec 4.2, 4.3, 5.1, 5.2, 5.3; 03 §3.2 (dòng "Điều kiện ban đầu", "Ngẫu nhiên hóa"), §3.3 V6, V7, §8.3 (chia tập theo `layout_hash`), §12.2.
- Châu sẽ làm scorer (3.3) và hiệu chỉnh (3.5) ở S2, nên story này là bước chuẩn bị trực tiếp. Hưng dùng bảng tín hiệu để viết hook ghi tín hiệu trong 3.1a.
- Không đoán tín hiệu từ tài liệu; ghi tín hiệu đã thấy thật trong episode chạy thử.
- V11 (timestamp riêng cho state và từng khung ảnh, tham số camera; 03 §3.3) do Hưng chốt trong 3.1a ở S2. Nếu story này thấy được các trường đó thì ghi vào bảng để 3.1a dùng.
- Scorer ở S2 cần thêm lớp lỗi chung cho mỗi kiểu lỗi (02 · 3.3 AC 4); khi đối chiếu 9 kiểu lỗi, ghi bước hỏng tương ứng để gán lớp.
- File sẽ tạo: `scripts/g0/probe_signals.py`, `scripts/g0/probe_reset_determinism.py`, `docs/g0/signals-conditions.md`.

## Kiểm thử

- `probe_reset_determinism.py` trả mã khác 0 khi hai lần reset cùng seed cho layout khác nhau.
- Hưng đọc bảng tín hiệu và xác nhận viết được hook từ đó (review).

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Review: Trần Ngọc Hưng
- Dự phòng: Trần Ngọc Hưng

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.8 (PO thêm để phủ V6, V7) | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Đồng bộ 03 bản 0.3: tín hiệu lệnh theo giao diện WBC; ghi chú V11 và lớp lỗi chung; sửa mã trích 05 TN13 thành TH13. AC của 02 · 1.8 không đổi | SM (Bob) theo 06 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
