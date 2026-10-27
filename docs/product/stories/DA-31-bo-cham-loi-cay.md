# DA-31 · Bộ chấm lỗi cấy cho QA và Agent QA/QC

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 27/10/2026) |
| Người làm | Hưng |
| Làn | Đánh giá |
| Story PRD | 9.23 · Epic 9 · [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 9.2 · 03 ADR-26 |
| Nhãn | [Lõi] · `epic:9` · `gate:G1` · `area:core` |
| Sprint | S2; kết quả trước 13/11/2026 cho demo (DA-28) |
| Ước lượng | 6 giờ (khoảng 5–8, ước lượng) |
| Phụ thuộc | DA-25 (schema `DefectManifest`), DA-27 (bản cấy lỗi và bản sạch), DA-20 (báo cáo của agent). Trong lúc chờ: code trên file mẫu của testkit |

## Story

Là AI Engineer, tôi muốn chấm phép kiểm QA và Agent QA/QC trên bộ lỗi cấy có đáp án, để có số đo hiệu suất trước khi đội có log train thật.

## Tiêu chí chấp nhận

1. Đọc kết quả QA (QAReport của làn Dữ liệu) và báo cáo của agent (`QAReport` của DA-20) trên bản cấy lỗi và bản sạch; chỉ mở `DefectManifest` sau khi cả hai đã chạy xong (có test).
2. Precision và recall theo từng loại lỗi, không gộp; tỉ lệ báo nhầm trên bản sạch; thời gian từ lúc job xong tới lúc có báo cáo.
3. Tách hai cột: phần **phép kiểm bằng code** bắt được, và phần **Agent QA/QC** thêm vào (xếp hạng đúng, giải thích đúng, đề xuất đúng hay sai).
4. Báo cáo HTML tĩnh ghi rõ "trên lỗi cấy"; dùng trong demo 17/11 (DA-28).

## Nhiệm vụ

- [ ] 1. Đọc kết quả và mở đáp án đúng lúc (AC 1)
- [ ] 2. Precision, recall, báo nhầm, thời gian (AC 2)
- [ ] 3. Tách phần code và phần agent (AC 3)
- [ ] 4. Báo cáo (AC 4)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/agentqa/bench/`, `packages/flywheel-eval/tests/unit/agentqa/bench/`
- `docs/g0/defect-bench.md`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 9.2, 9.4; 03 mục 7.3 (artifact `DefectManifest`), ADR-26.
- Tách từ DA-27 ngày 27/10/2026 để mỗi story có một người làm: DA-27 (Thông) cấy lỗi, story này (Hưng) chấm.
- Chỉ import nhân; đọc kết quả của làn Dữ liệu như artifact, không import `flywheel.data`.

## Kiểm thử

- Bộ chấm có test trên đầu vào giả có đáp án biết trước (precision, recall tính đúng).
- Test chặn: agent không mở được `DefectManifest`.

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Dương Tiến Thông (DA-27)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 27/10/2026 | Tạo story, tách phần chấm từ DA-27 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
