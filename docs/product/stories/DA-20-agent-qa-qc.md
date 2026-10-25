# DA-20 · Agent QA/QC cho train, eval và inference

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026 theo design 25/10/2026) |
| Người làm | Thông |
| Story PRD | Story mới của [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.2 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `area:core` |
| Sprint | S2–S3 |
| Ước lượng | 25 giờ (khoảng 20–30, ước lượng của SM) |
| Phụ thuộc | DA-19 cho log thật, DA-17 cho video phát lại, DA-23 cho log RTC. Code trên `metrics.jsonl` giả của `FakeTrainer` và log RTC giả trong lúc chờ |

## Story

Là AI Engineer, tôi muốn một agent đọc log và output từng stage rồi đưa insight và ước lượng có căn cứ, để quyết định thêm dữ liệu gì và làm gì nhanh hơn mà không mất quyền quyết.

## Tiêu chí chấp nhận

1. Serve Nemotron 3.5 Bolt E4B 4GB cục bộ trên RTX 3060, ghim revision trên Hugging Face; đo VRAM và độ trễ một báo cáo.
2. Đầu vào là tệp do code sinh: `metrics.jsonl`, kết quả probe, tóm tắt eval, log inference RTC, metadata của hình và video. Agent không đọc `vault/`, không chạy job, không chọn dữ liệu (có test).
3. Code tính mọi con số (CI, xu hướng loss, độ trễ p99, sai số theo nhóm); agent chỉ diễn giải và trích dẫn số; câu nào nêu số không có trong đầu vào thì báo cáo bị đánh dấu hỏng.
4. Dựng hình cho người: stage 1 là bảng ảnh khung hình, câu hỏi, câu trả lời của VLM, khung xương tay dự đoán; stage 2–3 là đồ thị action dự đoán so với thật và link video phát lại MuJoCo; inference là dòng thời gian RTC (design 25/10 mục 7.2).
5. Báo cáo HTML tĩnh mỗi job: phát hiện, bằng chứng, insight, ước lượng có khoảng, đề xuất; kỹ sư ghi đồng ý hoặc ghi đè kèm lý do.
6. Bộ ca mẫu ít nhất 10 ca có đáp án (train bình thường, loss phân kỳ, chiều action chết, gripper sụp mode, độ trễ vượt chu kỳ, giật ở ranh giới chunk, buffer cạn); báo tỉ lệ agent bắt đúng trước khi dùng.
7. Mỗi ước lượng của agent được lưu; khi có kết quả đo, so lại và báo sai số.

## Nhiệm vụ

- [ ] 1. Serve Nemotron cục bộ, đo VRAM, độ trễ (AC 1)
- [ ] 2. Đọc đầu vào, chặn `vault/`, kiểm số trích dẫn (AC 2, 3)
- [ ] 3. Dựng hình từng stage (AC 4)
- [ ] 4. Báo cáo HTML và ghi quyết định của kỹ sư (AC 5)
- [ ] 5. Bộ ca mẫu và chấm agent (AC 6)
- [ ] 6. Lưu và so ước lượng (AC 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-agentqa/`
- `uv.lock`: chỉ tạo lại bằng lệnh uv lock sau khi rebase (07 mục 3.2 điểm 5)
- `docs/g0/agent-qa.md`

## Ghi chú cho người làm

- Nguồn: [design 25/10](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 7; 03 ADR-19; spec glossary "Agent QA/QC".
- Nemotron chỉ đọc chữ theo tài liệu NVIDIA; kiểm thị giác vẫn thuộc Cosmos Reason hoặc người.
- Giấy phép OpenMDW-1.1: ghi vào Source trước khi dùng cho sản phẩm giao DENSO.
- Lõi `flywheel` không import package này; agent đọc tệp, không gọi vào lõi.

## Kiểm thử

- Bộ ca mẫu chạy được không cần GPU bằng model giả trả lời cố định; chạy với Nemotron thật trên máy 3060.
- Test: đường dẫn trong `vault/` bị từ chối; câu nêu số không có trong đầu vào bị đánh dấu.

## Người phụ trách

- Làm: Dương Tiến Thông
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Long (báo cáo, lõi), Hiếu (log train)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design 25/10/2026 mục 11.2 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
