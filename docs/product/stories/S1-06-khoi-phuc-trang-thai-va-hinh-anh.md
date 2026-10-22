# S1-06 · Khôi phục trạng thái và tách hình ảnh (Q3, Q4)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026) |
| Người làm | Châu |
| Story PRD | 1.5, phần Q3 và Q4 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` · `spike` |
| Sprint | S1. Câu trả lời ở G0 được phép là "tạm"; chốt cuối trong story 6.4 (S3) |
| Ước lượng | 8 giờ |
| Phụ thuộc | S1-02 |

## Story

Là kỹ sư simulation, tôi muốn biết SIMPLE có khôi phục được trạng thái giữa episode và đổi được hình ảnh mà giữ nguyên vật lý không, để biết phép kiểm khoanh vùng và kiểm thị giác của chẩn đoán có chạy được không.

## Tiêu chí chấp nhận

1. Q3, V4: lưu trạng thái giữa một episode, khôi phục, chạy tiếp cùng chuỗi action; so với chạy liền một mạch: sai số tư thế vật và góc khớp sau 1 giây. Ghi rõ có khôi phục được trạng thái bên trong WBC và hàng đợi action, RTC của policy không, hoặc chưa kiểm được.
2. Q4, V5: giữ layout vật lý, chỉ đặt ánh sáng và vật liệu về mức Level 0; kiểm tư thế vật và robot không đổi. Đối chiếu mã nguồn `DRManager` vì tài liệu SIMPLE mô tả mức DR theo hai cách ngược nhau.
3. Mỗi câu có một trong ba trả lời: "có", "không", "tạm" kèm việc còn thiếu. Đề xuất giá trị `SimCapabilities.restore_state` và `visual_override`.
4. Kết quả ở `docs/g0/q3-q4-restore-visual.md`; cập nhật dòng V4, V5 ở 03 §3.3 có change log.

## Nhiệm vụ

- [ ] 1. Thử lưu và khôi phục (AC 1)
  - [ ] 1.1 Dùng `get_states()`, `set_states()` của simulator và `state_dict()`, `load_state_dict()` của task
  - [ ] 1.2 So quỹ đạo khôi phục với quỹ đạo liền; ghi ngưỡng sai số đã dùng
  - [ ] 1.3 Ghi phần trạng thái WBC và policy có hay không được khôi phục
- [ ] 2. Thử đổi hình ảnh giữ vật lý (AC 2)
  - [ ] 2.1 Đọc mã `DRManager.load_state_dict(state_dict, dr_level)`, `LightingDR`, `MaterialDR`
  - [ ] 2.2 So trạng thái vật lý từng bước có và không có ghi đè hình ảnh
- [ ] 3. Viết kết luận, cập nhật 03 (AC 3, 4)

## Ghi chú cho người làm

- Nguồn: 02 · 1.5, 6.4; spec 2.4 Q3, Q4, 6.6, 6.7, 10; 03 §3.2 (dòng "Hai simulator trong một env", "Điều kiện ban đầu", "Ngẫu nhiên hóa"), §3.3 V4, V5, §5.3 quy tắc 1 (khai năng lực trung thực), §12.2; 05 SI1, SI2, mục 3 (dòng "Khoanh vùng", "Kiểm thị giác").
- PO cho phép câu trả lời tạm ở G0 vì hai phép kiểm này chỉ cần từ S4. Nếu câu trả lời là "không", spec 10 đã có phương án thay (chạy lại cùng hạt giống, để planner tiếp quản).
- Không giả lập khôi phục bằng cách chạy lại từ đầu mà vẫn báo `restore_state = True`.
- File sẽ tạo: `scripts/g0/restore_probe.py`, `scripts/g0/visual_override_probe.py`, `docs/g0/q3-q4-restore-visual.md`.

## Kiểm thử

- Script in ra sai số so với chạy liền và trả mã khác 0 nếu vượt ngưỡng đã ghi.
- Hưng chạy lại một lần và ra cùng kết luận.

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Review: Trần Ngọc Hưng
- Dự phòng: Trần Ngọc Hưng

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.5 (phần Q3, Q4); cho phép câu trả lời tạm ở G0 | SM (Bob), PO (Sarah) duyệt |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
