# DA-28 · Kịch bản demo 17/11/2026 chạy trọn luồng

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt hướng 27/10/2026) |
| Người làm | Chờ PO giao |
| Làn | Vòng quyết định (ghép luồng); dùng lệnh của mọi làn qua `fw` |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 11 · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `gate:G1` · `area:core` |
| Sprint | S2; chạy thử toàn bộ ngày 16/11/2026 |
| Ước lượng | 10 giờ (khoảng 8–12, ước lượng) |
| Phụ thuộc | S1-03, S1-05, DA-03, DA-04, DA-16, DA-18, DA-20, DA-26 (sơ bộ), DA-27, DA-29; một vòng Failure → Data cần scorer, chẩn đoán và evidence card của S2 |

## Story

Là trưởng nhóm, tôi muốn một kịch bản demo chạy lại được, mỗi phần một lệnh, để ngày 17/11 cho DENSO thấy toàn bộ luồng data flywheel và số đo của nó trên G1 + Ψ₀.

## Tiêu chí chấp nhận

1. Kịch bản sáu phần theo design mục 11: tái tạo Ψ₀ trên task hai bàn; thu ba loại dữ liệu (mẫu EgoDex, một episode bàn phím trực tiếp, vài episode synthetic S1 và S2); ba loại qua pipeline 6 tầng (egocentric ra định dạng stage 1 kèm lần chạy stage 1 ngắn, teleop và synthetic ra release LeRobot v2.1) và báo cáo dataset; Agent QA/QC trên bộ lỗi cấy; HE-1 sơ bộ; một vòng Failure → Data trên lượt lỗi của eval HE (scorer → chẩn đoán → evidence card → đề xuất dữ liệu → sổ chi phí).
2. Mỗi phần một lệnh trong `scripts/demo/`, chạy được từ máy sạch theo `docs/demo/README.md`; phần cần GPU có bản ghi sẵn (video, báo cáo) để demo không phụ thuộc mạng.
3. Mỗi con số trên màn hình demo trỏ tới file nguồn (báo cáo, sổ chi phí, RunPlan); số sơ bộ hoặc trên lỗi cấy ghi rõ như vậy.
4. Mục "Chưa có ở demo" ghi thẳng: video egocentric đội tự quay, HE-2, S3, S4, HS, HT, HD, holdout.
5. Chạy thử toàn bộ ngày 16/11/2026, ghi thời gian từng phần và lỗi gặp phải.

## Nhiệm vụ

- [ ] 1. Viết kịch bản và danh sách lệnh (AC 1, 4)
- [ ] 2. Script từng phần và bản ghi sẵn cho phần GPU (AC 2)
- [ ] 3. Trỏ nguồn cho mọi con số (AC 3)
- [ ] 4. Chạy thử 16/11, sửa, ghi kết quả (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `scripts/demo/`
- `docs/demo/`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 11; spec mục 0 (đầu ra), 9 (demo ở tuần 4).
- Website và hai file PowerPoint không thuộc story này; trưởng nhóm quyết khi chuẩn bị demo.
- Không chạy holdout trong demo (CLAUDE.md, mục "Không làm").

## Kiểm thử

- Một người không viết script chạy lại sáu phần từ `docs/demo/README.md` mà không cần hỏi.

## Người phụ trách

- Làm: chờ PO giao
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 27/10/2026 | Tạo story theo design 27/10/2026 mục 11 | PO (Hiếu) |
| 27/10/2026 | Thêm ba loại dữ liệu vào phần thu và pipeline (EgoDex, S2) | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
