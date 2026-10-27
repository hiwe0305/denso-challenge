# S1-06 · Khôi phục trạng thái và tách hình ảnh (Q3, Q4)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; sửa 25/10/2026; về lại SIMPLE 27/10/2026) |
| Người làm | Hiếu |
| Story PRD | 1.5, phần Q3 và Q4 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` · `spike` |
| Sprint | S1. Câu trả lời ở G0 được phép là "tạm"; chốt cuối trong story 6.4 (S3) |
| Ước lượng | 8 giờ (bản 25/10: 4 giờ trên MuJoCo riêng) |
| Phụ thuộc | S1-02 |

## Story

Là kỹ sư simulation, tôi muốn biết SIMPLE có khôi phục được trạng thái giữa episode và đổi được hình ảnh mà giữ nguyên vật lý không, để biết phép kiểm khoanh vùng và kiểm thị giác của chẩn đoán có chạy được không.

## Tiêu chí chấp nhận

_Về lại SIMPLE ngày 27/10/2026 ([design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 4) trên task hai bàn._

1. Q3: dùng `get_states()` và `set_states()` của SIMPLE lưu trạng thái giữa một episode task hai bàn (MuJoCo, trạng thái bên trong decoupled WBC, thời gian), khôi phục, chạy tiếp cùng chuỗi action; so với chạy liền: sai số tư thế vật, tư thế thân và góc khớp sau 1 giây. Liệt kê trạng thái nằm ngoài sim cần lưu thêm (hàng đợi action, buffer RTC của policy).
2. Q4: đổi ánh sáng và vật liệu (màu, texture) qua domain randomization của SIMPLE mà giữ vật lý; kiểm trạng thái vật lý từng bước trùng với khi không đổi, ở cả `mujoco` và `mujoco_isaac`.
3. Ghi tham số ngẫu nhiên hóa nào của task hai bàn đổi được: vị trí vật, vị trí và khoảng cách hai bàn, ánh sáng, vật liệu (đầu vào cho vector điều kiện, S1-09).
4. Mỗi câu có một trong ba trả lời: "có", "không", "tạm" kèm việc còn thiếu. Đề xuất giá trị `SimCapabilities.restore_state` và `visual_override` cho `SimpleSim`.
5. Kết quả ở `docs/g0/q3-q4-restore-visual.md`, có mục "Đề xuất cho 03 §3.3" ([docs/g0/README.md](../../g0/README.md)).

## Nhiệm vụ

- [ ] 1. Thử lưu và khôi phục trên task hai bàn, ghi trạng thái ngoài sim (AC 1)
- [ ] 2. Thử đổi hình ảnh giữ vật lý ở hai chế độ (AC 2)
- [ ] 3. Liệt kê tham số ngẫu nhiên hóa đổi được (AC 3)
- [ ] 4. Viết kết luận kèm đề xuất cho 03 §3.3 (AC 4, 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `scripts/g0/restore_probe.py`, `scripts/g0/visual_override_probe.py`
- `docs/g0/q3-q4-restore-visual.md`
- `docs/g0/ledger/S1-06.csv`

## Ghi chú cho người làm

- Nguồn: 02 · 1.5, 6.4; spec 2.4 Q3, Q4, 6.6, 6.7, 10; 03 §3.2 (dòng "Hai simulator trong một env", "Điều kiện ban đầu", "Ngẫu nhiên hóa"), §3.3 V4, V5, §5.3 quy tắc 1 (khai năng lực trung thực), §12.2.
- PO cho phép câu trả lời tạm ở G0 vì hai phép kiểm này chỉ cần từ S4. Nếu câu trả lời là "không", spec 10 đã có phương án thay (chạy lại cùng hạt giống, để planner tiếp quản).
- Rủi ro đã biết (03 §12.2): `set_states()` có thể không khôi phục trạng thái WBC và hàng đợi action.
- Không giả lập khôi phục bằng cách chạy lại từ đầu mà vẫn báo `restore_state = True`.
- File sẽ tạo: `scripts/g0/restore_probe.py`, `scripts/g0/visual_override_probe.py`, `docs/g0/q3-q4-restore-visual.md`.

## Kiểm thử

- Script in ra sai số so với chạy liền và trả mã khác 0 nếu vượt ngưỡng đã ghi.
- Một người khác chạy lại một lần và ra cùng kết luận.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.5 (phần Q3, Q4); cho phép câu trả lời tạm ở G0 | SM (Bob), PO (Sarah) duyệt |
| 24/10/2026 | Thêm mục Phạm vi file. AC 4: đề xuất dòng V4, V5 ghi trong file kết quả, Hiếu gom vào 03 §3.3 ở review G0 | PO (Hiếu) |
| 25/10/2026 | Đổi sang env MuJoCo của robot DENSO; 8 → 4 giờ; chuyển cho Hưng | PO (Hiếu) theo hai design 25/10/2026 (đã xóa) |
| 27/10/2026 | Về lại SIMPLE trên task hai bàn; thêm AC 3 (tham số ngẫu nhiên hóa đổi được); phụ thuộc S1-02; người làm chờ PO giao; 4 → 8 giờ | PO (Hiếu) theo design 27/10/2026 |
| 27/10/2026 | Giao cho Hiếu theo 07 mục 2.0 (bản 0.6) | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
