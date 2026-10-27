# DA-20 · Agent QA/QC cho train, eval và inference

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa 27/10/2026) |
| Người làm | Hưng |
| Làn | Đánh giá |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 9 · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `area:core` |
| Sprint | S2; kết quả trên bộ lỗi cấy trước 13/11/2026 cho demo (DA-28) |
| Ước lượng | 25 giờ (khoảng 20–30, ước lượng của SM) |
| Phụ thuộc | DA-25 (schema `QAReport`, `DatasetReport`, log RTC, kết quả probe), DA-27 (bộ lỗi cấy), DA-31 (bộ chấm, cùng người làm). Code trên file mẫu của testkit; log thật của DA-19 và report của DA-17 chỉ cần khi chạy thật. PR `chore-restructure` (07 mục 3.6, hết 27/10) tạo khung package `flywheel-eval` |

## Story

Là AI Engineer, tôi muốn một agent đọc báo cáo dataset, log và output từng stage rồi đưa insight và ước lượng có căn cứ, để quyết định thêm dữ liệu gì và làm gì nhanh hơn mà không mất quyền quyết.

## Tiêu chí chấp nhận

1. Gọi Nemotron 3.5 Bolt E4B 4GB qua endpoint cục bộ khai trong `configs/models/` (Hiếu serve trên máy 3060); dev và CI dùng model giả của testkit.
2. Đầu vào là artifact đúng schema: `DatasetReport`, `ReplayReport`, `metrics.jsonl`, kết quả probe, `Score`, `Cluster`, log RTC. Không đọc `vault/`, không chạy job, không chọn dữ liệu (có test).
3. Code tính mọi con số; agent chỉ diễn giải và trích dẫn; câu nêu số không có trong đầu vào thì báo cáo bị đánh dấu hỏng.
4. Dựng hình cho người: báo cáo dataset (phép kiểm trượt nhiều nhất theo nguồn); bảng ảnh stage 1 (khung hình SIMPLE, câu hỏi, câu trả lời của VLM); đồ thị action dự đoán so với thật kèm link video phát lại; dòng thời gian RTC.
5. Ra `QAReport` đúng schema và báo cáo HTML tĩnh; kỹ sư ghi đồng ý hoặc ghi đè kèm lý do.
6. Chạy trên bộ lỗi cấy của DA-27, chấm bằng DA-31, trước khi dùng: precision, recall theo loại lỗi, báo nhầm trên bản sạch; tách phần phép kiểm bằng code bắt được khỏi phần agent thêm (design mục 9.2). Mỗi ước lượng lưu lại và so với kết quả đo.
8. Sau khi đội có log fine-tune thật (DA-19, DA-26): chạy trên log thật, báo riêng với kết quả trên lỗi cấy.
7. Câu Q-M: nếu trưởng nhóm muốn agent tự nhìn hình thì thêm Qwen3.5-4B qua endpoint thứ hai, cùng bộ ca mẫu.

## Nhiệm vụ

- [ ] 1. Gọi endpoint cục bộ, model giả cho CI (AC 1)
- [ ] 2. Đọc artifact, chặn `vault/`, kiểm số trích dẫn (AC 2, 3)
- [ ] 3. Dựng hình từng stage (AC 4)
- [ ] 4. `QAReport`, HTML, quyết định của kỹ sư (AC 5)
- [ ] 5. Bộ ca mẫu, chấm agent, lưu ước lượng (AC 6)
- [ ] 6. Qwen3.5-4B nếu Q-M là có (AC 7)
- [ ] 7. Chạy trên log thật, báo riêng (AC 8)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/agentqa/`
- `packages/flywheel-eval/tests/unit/agentqa/`, `packages/flywheel-eval/tests/contract/agentqa/`
- `configs/eval/agentqa/`
- `docs/g0/agent-qa.md`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 6.7, 9; 03 ADR-19, ADR-24, ADR-26.
- Model: Nemotron 3.5 Bolt E4B 4GB (NVIDIA, ra 23/10/2026; dựng trên Gemma-4-E4B-it; 8B tổng, 4B hiệu dụng; ngữ cảnh 64K; chỉ đọc chữ theo tài liệu NVIDIA; gọi được tool; bản Q4 khoảng 3–4 GB VRAM). Prompt trong `configs/eval/agentqa/` có hash; log dài do code tóm tắt theo cửa sổ để vừa 64K; tool chỉ đọc artifact theo ID.
- Vòng thử chung với DA-04 (design mục 6.7.4) quyết có cần Qwen3.5-4B để nhìn hình (AC 7). Đáp án của bộ lỗi cấy (`DefectManifest`) chỉ bộ chấm đọc, sau khi agent đã chạy.
- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import làn khác hay adapter (03 mục 7.3). Thiếu trường trong schema thì báo Hiếu mở PR hợp đồng, không thêm trường tạm.
- Nemotron chỉ đọc chữ; hình do code dựng, agent đọc metadata và số đi kèm.
- Giấy phép OpenMDW-1.1 của Nemotron ghi vào Source trước khi dùng cho sản phẩm giao DENSO.

## Kiểm thử

- Bộ ca mẫu chạy được trong CI bằng model giả; chạy với Nemotron thật trên máy Hiếu.
- Đường dẫn trong `vault/` bị từ chối; câu nêu số không có trong đầu vào bị đánh dấu.

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (endpoint, log), Long (báo cáo)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 25/10/2026 | Chuyển sang làn Đánh giá; serve model do Hiếu; thêm Qwen3.5-4B tùy chọn | PO (Hiếu) theo design chia làn (đã xóa) |
| 27/10/2026 | Thêm báo cáo dataset vào đầu vào; AC 6 chấm trên bộ lỗi cấy của DA-27 thay bộ ca mẫu tự viết; thêm AC 8 và nhiệm vụ con 7 chạy trên log thật | PO (Hiếu) theo design 27/10/2026 |
| 27/10/2026 | Giao cho Hưng theo 07 mục 2.0 (bản 0.6) | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
