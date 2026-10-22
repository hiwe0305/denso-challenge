# S1-05 · Planner của SIMPLE cho task chính (Q2)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; SM sửa phạm vi theo 02 bản 0.3 cùng ngày) |
| Người làm | Hưng |
| Story PRD | 1.5, phần Q2 (AC 1 và AC 4 cho cờ `plan`) · Epic 1. V3 (AC 5 cũ của 1.5) chuyển sang story 1.9, file [S1-11](S1-11-bo-dieu-khien-v3.md) |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` · `spike` |
| Sprint | S1, tuần 1; chạy song song S1-11 |
| Ước lượng | 6 giờ (bản 0.1: 12 giờ gồm cả V3) |
| Phụ thuộc | S1-02. Kết quả datagen là đầu vào cho bảng đối chiếu và thử T1 của S1-11 |

## Story

Là kỹ sư simulation, tôi muốn biết pipeline motion planning của SIMPLE có cấu hình được cho task chính không, và có lập kế hoạch được từ trạng thái giữa episode không, để biết nhánh B và các phép kiểm khả thi có nguồn sinh dữ liệu hay phải dựa vào tuyến khác.

## Tiêu chí chấp nhận

1. Q2: chạy datagen motion planning cho task MP gần nhất (`G1WholebodyPickAndBendPlaceMP-v0`) và thử cấu hình cho task chính; ghi tỉ lệ sinh đạt trên ít nhất 20 lượt và thời gian mỗi lượt.
2. Kiểm planner có chạy được từ một trạng thái lưu giữa episode không (cần cho kiểm khả thi, trạng thái chuẩn, correction do máy sinh; 02 · 5.5 AC 4).
3. Đề xuất giá trị cờ khả năng liên quan cho SimulatorAdapter và GeneratorAdapter (02 · 1.5 AC 4). Giá trị cuối của `GenCapabilities.plan` chốt cùng kết luận V3 ở S1-11, vì planner dưới AMO không chứng minh khả thi dưới WBC.
4. Không ghi task F1 là dự phòng cho Q2, trừ khi S1-11 xác nhận cặp task của F1 cùng bộ điều khiển (06 mục 1, 02 · 1.9 AC 2).
5. Kết quả ở `docs/g0/q2-planner.md`; chi phí vào `docs/g0/ledger-g0.csv`.

## Nhiệm vụ

- [ ] 1. Chạy datagen cho task MP gần nhất và thử cho task chính (AC 1)
- [ ] 2. Kiểm planner từ trạng thái lưu (AC 2)
- [ ] 3. Đề xuất cờ khả năng, chuyển số liệu cho S1-11 (AC 3, 4)
- [ ] 4. Viết `docs/g0/q2-planner.md`, ghi sổ chi phí (AC 5)

## Ghi chú cho người làm

- Nguồn: 02 · 1.5 (bản 0.3), 1.9, 5.1, 5.5; spec 2.4 Q2, 6.5, 6.6, 10; 03 §3.2 (dòng "Sinh dữ liệu motion planning"), §5.2 (`GenCapabilities`), §5.4; 05 DK3, DK4.
- Theo 06 mục 1, V3 tách thành story riêng có hạn ngày 5 (S1-11). Story này chỉ trả lời Q2; bảng đối chiếu bộ điều khiển và thử T1, T2 nằm ở S1-11.
- Theo 03 §3.2, task `*MP-v0` chạy AMO (`g1_wholebody`), khác bộ điều khiển với task chính. Rollout từ datagen ở story này chưa được trộn vào release nào cho tới khi S1-11 kết luận (ADR-08).
- File sẽ tạo: `scripts/g0/datagen_probe.sh`, `docs/g0/q2-planner.md`. Dùng chung `datagen_probe.sh` với S1-11.

## Kiểm thử

- Người review chạy lại `scripts/g0/datagen_probe.sh` cho 5 lượt và ra tỉ lệ sinh đạt cùng bậc.
- Kết quả kiểm từ trạng thái lưu có script chạy lại được.

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Review: Trần Trịnh Hoàng Châu
- Dự phòng: Trần Trịnh Hoàng Châu

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.5 (phần Q2) và AC V3 mới; tách khỏi Q3, Q4 (S1-06) | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Theo 02 bản 0.3 (06 mục 1): V3 tách sang story 1.9, file S1-11; story này chỉ còn Q2 và kiểm planner từ trạng thái lưu; bỏ F1 khỏi vai dự phòng cho Q2; ước lượng 12 → 6 giờ; review chuyển sang Châu | SM (Bob) theo 06 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
