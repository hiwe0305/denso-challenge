# DA-27 · Bộ lỗi cấy: cấy lỗi có đáp án

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt hướng 27/10/2026) |
| Người làm | Thông |
| Làn | Dữ liệu |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 9.2 · Epic 9 · 03 ADR-26 |
| Nhãn | [Lõi] · `epic:9` · `gate:G1` · `area:data` |
| Sprint | S2; bộ lỗi dữ liệu xong trước 10/11/2026 để DA-20 chấm kịp demo |
| Ước lượng | 7 giờ (khoảng 6–8, ước lượng; bộ chấm tách sang DA-31) |
| Phụ thuộc | DA-25 (schema `DefectManifest`, trường `injected_defect`), S1-07 (gói psi-data task hai bàn). Log train và log RTC cấy lỗi dựng trên `FakeTrainer` và log RTC giả của testkit cho tới khi có log thật |

## Story

Là kỹ sư dữ liệu, tôi muốn một bộ dữ liệu và log thật được cấy lỗi có đáp án khóa trước, để bộ chấm (DA-31) đo được phép kiểm QA và Agent QA/QC bắt đúng bao nhiêu trước khi đội train model.

## Tiêu chí chấp nhận

1. Bộ cấy chạy trên bản sao của gói psi-data task hai bàn (không sửa bản gốc): mỗi loại lỗi dữ liệu ở design mục 9.2 (rơi khung ảnh; lệch thời gian ảnh và state; nhảy khớp; vượt giới hạn khớp; NaN; sai đơn vị độ và radian; đảo dấu một chiều action; episode hỏng gắn nhãn thành công; sai câu lệnh task; trùng episode; rò hạt giống holdout) có tham số, tỉ lệ cấy khoảng 5–10% số episode, hạt giống ghi lại.
2. Log train cấy lỗi T1–T8 và log RTC cấy lỗi R1, R2 sinh từ bộ giả, cùng schema với log thật.
3. Đáp án ghi vào `DefectManifest`, hash khóa trước khi chạy QA và agent; agent và phép kiểm không đọc được file này (có test).
4. Một bản sạch (không cấy) cùng kích thước để đo báo nhầm.
5. Bản cấy lỗi và bản sạch giao cho DA-31 qua `DatasetRef` và `DefectManifest`; bản cấy lỗi không vào release train (có test).

## Nhiệm vụ

- [ ] 1. Bộ cấy lỗi dữ liệu trên bản sao psi-data (AC 1)
- [ ] 2. Log train và log RTC cấy lỗi từ bộ giả (AC 2)
- [ ] 3. `DefectManifest` có hash, chặn agent đọc (AC 3)
- [ ] 4. Bản sạch (AC 4)
- [ ] 5. Giao bản cấy và bản sạch, test chặn release (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-data/src/flywheel/data/inject/`, `packages/flywheel-data/tests/unit/inject/`
- `configs/data/inject.yaml`
- `docs/g0/defect-inject.md`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 9.2, 10 (mã lỗi D, T, R); spec mục 7.6 (lỗi cấy cho HD dùng cùng ý tưởng); 03 mục 7.3 (artifact), ADR-26.
- Phần chấm là DA-31 (Hưng, làn Đánh giá); hai phần chỉ nối qua `DefectManifest` trong `flywheel.contracts`, không import nhau.
- Bản sao cấy lỗi không bao giờ vào release train (có test chặn theo `injected_defect`).
- Dữ liệu cấy lỗi để trong `fwdata/`, không commit; chỉ commit cấu hình và mã.

## Kiểm thử

- Mỗi loại lỗi có một test: cấy một lần, phép kiểm tương ứng bắt được.
- Test chặn: release từ chối episode có `injected_defect`.

## Người phụ trách

- Làm: Dương Tiến Thông
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 27/10/2026 | Tạo story theo design 27/10/2026 mục 9.2 | PO (Hiếu) |
| 27/10/2026 | Tách bộ chấm sang DA-31; giao cho Thông theo 07 mục 2.0 (bản 0.6) | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
