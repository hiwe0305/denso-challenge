# S1-11 · Bộ điều khiển teleop và motion planning (V3)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (SM tạo 22/10/2026 theo 02 bản 0.3; PO duyệt ở họp lập kế hoạch S1) |
| Story PRD | 1.9 · Epic 1 (story mới ở 02 bản 0.3, tách từ AC 5 cũ của 1.5) |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` · `spike` |
| Sprint | S1. **Bảng đối chiếu xong trước ngày 5 (thứ Sáu 30/10/2026).** Thử T1 và T2 song song tuần 1–2; chốt tuyến cuối tuần 2 ở review G0, chậm nhất S2 ngày 3 |
| Ước lượng | 18 giờ: Hưng 12 (bảng đối chiếu, T1, kết luận), Châu 6 (T2) |
| Phụ thuộc | Bước 1 không cần S1-02 (đọc cấu hình và mã SIMPLE). Thử T1, T2 cần S1-02. Dùng số liệu datagen của S1-05. Chặn 5.5, 5.1, 6.3, 6.4, 7.4, 7.11 |

## Story

Là kỹ sư simulation, tôi muốn biết rollout motion planning có cùng bộ điều khiển với demo teleop của task chính không, để nhánh B, C và B-fail có dữ liệu sinh hợp lệ hoặc chọn sớm tuyến thay thế.

## Tiêu chí chấp nhận

1. Trước ngày 5: bảng đối chiếu demo teleop task chính (`G1WholebodyBendPickAndPlaceTeleop-v0`) và rollout MP: env, robot, bộ điều khiển, không gian state, không gian action, tần số điều khiển, camera. Mỗi ô có nguồn là file cấu hình hoặc mã SIMPLE. Bảng ghi rõ System-0 của task chính là decoupled WBC (`g1_sonic`, env `SonicLocoManipEnv`) và AMO (`g1_wholebody`) là bộ điều khiển của pipeline MP.
2. Cùng bảng cho cặp task F1 (`G1WholebodyBendPickTeleop-v0`, `G1WholebodyBendPickMP-v0`). F1 chỉ được ghi là dự phòng cho Q2 khi bảng xác nhận cặp này cùng bộ điều khiển; nếu không, F1 chỉ giữ vai trò kiểm khả năng tổng quát của lõi (NFR7).
3. Cùng bộ điều khiển hoặc có ánh xạ tường minh: ghi ánh xạ, đề xuất `embodiment_id` cho từng nguồn; story 5.5 đóng với ghi chú "không cần".
4. Khác bộ điều khiển: thử song song trong tuần 1–2. T1 (Hưng): lấy quỹ đạo thân trên của rollout MP, suy lệnh thân dưới, chạy lại trong env WBC. T2 (Châu, 6 giờ): biến đổi một đoạn teleop theo tư thế vật mới, chạy bằng IK cộng WBC trong env Teleop. Mỗi tuyến ghi tỉ lệ thành công trên ít nhất 10 lượt và ước công sức xây đến mức chạy được (đầu vào cho 5.5). Chốt tuyến cuối tuần 2; T3, T4 chỉ chọn theo cây ở 04 mục 1.3.
5. Ghi kịch bản V3 âm cộng Q6 âm (Q6 lấy từ S1-07) vào RunPlan nháp và mục rủi ro: C chỉ còn kiểm demo mâu thuẫn, HT sụp, báo cáo phải nêu.
6. Kết luận ở `docs/g0/v3-planner-controller.md`; cập nhật dòng V3 của 03 §3.3 có change log và giá trị cờ `GenCapabilities.plan`; nháp cấu hình embodiment trong `configs/embodiments/`.

## Nhiệm vụ

- [ ] 1. Bảng đối chiếu (AC 1, 2), xong trước ngày 5
  - [ ] 1.1 Đọc cấu hình env, robot, bộ điều khiển của task chính và task MP; ghi bảng có nguồn
  - [ ] 1.2 Làm tương tự cho cặp F1
  - [ ] 1.3 Báo kết luận sơ bộ trong check-in thứ Sáu ngày 5; V3 âm thì báo Hiếu ngay
- [ ] 2. Nếu cùng bộ điều khiển hoặc có ánh xạ: ghi ánh xạ, đề xuất `embodiment_id`, đóng 5.5 (AC 3)
- [ ] 3. Nếu khác: Hưng thử T1 (AC 4)
- [ ] 4. Nếu khác: Châu thử T2 trong 6 giờ (AC 4)
- [ ] 5. Ghi kịch bản V3 âm cộng Q6 âm (AC 5)
- [ ] 6. Viết kết luận, đề xuất tuyến cho review G0, cập nhật 03 §3.3, nháp `configs/embodiments/` (AC 6)

## Ghi chú cho người làm

- Nguồn: 02 · 1.9, 1.5, 5.1, 5.5, 7.4, §8; spec 2.1, 2.3, 2.4 (V3), 4.1, 6.5, 6.6, 10 (bảng T1–T4); 03 §3.2 (dòng "Bộ điều khiển của task chính", "Sinh dữ liệu motion planning"), §3.3 V3, §5.2 (`control_spec`), §5.4, ADR-08, ADR-15, §12.2 (bảng tuyến); 05 mục 2.3 (DK1–DK4), R01, PM1, RL2; 06 mục 1.
- Story tách từ AC 5 cũ của 1.5 (S1-05 bản 0.1) theo 06 mục 1, để V3 có hạn riêng là ngày 5. S1-05 nay chỉ còn Q2.
- Theo 03 §3.2, mọi task `*Teleop-v0` dùng `g1_sonic` còn `*MP-v0` dùng AMO; F1 nhiều khả năng không chữa được V3 (05 DK4). Cần xác nhận, không giả định.
- Release sẽ cấm trộn embodiment không tương thích (ADR-08); kết luận của story này quyết định có cần ánh xạ hay tuyến khác.
- T1, T2 tranh máy 5090 với S1-03 và S1-04: Hưng xếp lịch máy từ ngày 1.
- Kết luận T3 thì báo Hiếu ngay để kích hoạt cắt giảm mức 2–4 (04 mục 7, 4.8). T4 cần Hiếu và mentor đồng ý; claim HS thu hẹp thành "sim thay sim".
- File sẽ tạo: `docs/g0/v3-planner-controller.md`, `scripts/g0/t1_replay_probe.py`, `scripts/g0/t2_variant_probe.py`, `configs/embodiments/g1_sonic_dwbc.yaml` và `configs/embodiments/g1_wholebody_amo.yaml` (bản nháp).

## Kiểm thử

- Bảng đối chiếu có nguồn (đường dẫn file cấu hình hoặc mã nguồn SIMPLE) cho từng ô; Long đối chiếu ngẫu nhiên 3 ô với mã SIMPLE.
- Người review chạy lại probe T1 hoặc T2 cho 5 lượt và ra tỉ lệ thành công cùng bậc.

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Hỗ trợ: Trần Trịnh Hoàng Châu (T2, 6 giờ)
- Review: Dương Đình Hiếu (tác động tới thí nghiệm), Nguyễn Thăng Long (embodiment trong catalog)
- Dự phòng: Trần Trịnh Hoàng Châu

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.9 (bản 0.3), tách V3 khỏi S1-05 theo 06 mục 1; hạn ngày 5, thử T1 và T2 song song, chốt cuối tuần 2 | SM (Bob) theo 06 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
