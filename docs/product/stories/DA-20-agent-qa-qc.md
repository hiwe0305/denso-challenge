# DA-20 · Agent QA/QC cho train, eval và inference

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa theo design chia làn cùng ngày) |
| Người làm | Châu |
| Làn | Đánh giá |
| Story PRD | Story mới của [design MuJoCo 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) và [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `area:core` |
| Sprint | S2–S3 |
| Ước lượng | 25 giờ (khoảng 20–30, ước lượng của SM) |
| Phụ thuộc | DA-25 (schema `QAReport`, log RTC, kết quả probe). Code trên file mẫu của testkit; log thật của DA-19 và report của DA-17 chỉ cần khi chạy thật. PR `chore-restructure` (07 mục 3.6, hết 27/10) tạo khung package `flywheel-eval` |

## Story

Là AI Engineer, tôi muốn một agent đọc log và output từng stage rồi đưa insight và ước lượng có căn cứ, để quyết định thêm dữ liệu gì và làm gì nhanh hơn mà không mất quyền quyết.

## Tiêu chí chấp nhận

1. Gọi Nemotron 3.5 Bolt E4B 4GB qua endpoint cục bộ khai trong `configs/models/` (Hiếu serve trên máy 3060); dev và CI dùng model giả của testkit.
2. Đầu vào là artifact đúng schema: `metrics.jsonl`, kết quả probe, `Score`, `Cluster`, log RTC, `ReplayReport`. Không đọc `vault/`, không chạy job, không chọn dữ liệu (có test).
3. Code tính mọi con số; agent chỉ diễn giải và trích dẫn; câu nêu số không có trong đầu vào thì báo cáo bị đánh dấu hỏng.
4. Dựng hình cho người: bảng ảnh stage 1 (khung hình, câu hỏi, câu trả lời của VLM, khung xương tay); đồ thị action dự đoán so với thật kèm link video phát lại; dòng thời gian RTC.
5. Ra `QAReport` đúng schema và báo cáo HTML tĩnh; kỹ sư ghi đồng ý hoặc ghi đè kèm lý do.
6. Bộ ca mẫu ≥ 10 ca có đáp án; báo tỉ lệ agent bắt đúng trước khi dùng; mỗi ước lượng lưu lại và so với kết quả đo.
7. Câu Q-M: nếu trưởng nhóm muốn agent tự nhìn hình thì thêm Qwen3.5-4B qua endpoint thứ hai, cùng bộ ca mẫu.

## Nhiệm vụ

- [ ] 1. Gọi endpoint cục bộ, model giả cho CI (AC 1)
- [ ] 2. Đọc artifact, chặn `vault/`, kiểm số trích dẫn (AC 2, 3)
- [ ] 3. Dựng hình từng stage (AC 4)
- [ ] 4. `QAReport`, HTML, quyết định của kỹ sư (AC 5)
- [ ] 5. Bộ ca mẫu, chấm agent, lưu ước lượng (AC 6)
- [ ] 6. Qwen3.5-4B nếu Q-M là có (AC 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/agentqa/`
- `packages/flywheel-eval/tests/unit/agentqa/`, `packages/flywheel-eval/tests/contract/agentqa/`
- `configs/eval/agentqa/`
- `docs/g0/agent-qa.md`

## Ghi chú cho người làm

- Nguồn: [design MuJoCo](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 7; [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) mục 10; 03 ADR-19, ADR-24.
- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import làn khác hay adapter (03 mục 7.3). Thiếu trường trong schema thì báo Hiếu mở PR hợp đồng, không thêm trường tạm.
- Nemotron chỉ đọc chữ; hình do code dựng, agent đọc metadata và số đi kèm.
- Giấy phép OpenMDW-1.1 ghi vào Source trước khi dùng cho sản phẩm giao DENSO.

## Kiểm thử

- Bộ ca mẫu chạy được trong CI bằng model giả; chạy với Nemotron thật trên máy Hiếu.
- Đường dẫn trong `vault/` bị từ chối; câu nêu số không có trong đầu vào bị đánh dấu.

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (endpoint, log), Long (báo cáo)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design MuJoCo 25/10/2026 mục 11.2 | PO (Hiếu) |
| 25/10/2026 | Viết lại theo design chia làn: chuyển sang làn Đánh giá; serve model do Hiếu; thêm Qwen3.5-4B tùy chọn | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
