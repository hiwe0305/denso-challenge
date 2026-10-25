# S1-06 · Khôi phục trạng thái và tách hình ảnh (Q3, Q4)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; sửa 25/10/2026) |
| Người làm | Hưng |
| Story PRD | 1.5, phần Q3 và Q4 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` · `spike` |
| Sprint | S1. Câu trả lời ở G0 được phép là "tạm"; chốt cuối trong story 6.4 (S3) |
| Ước lượng | 4 giờ (bản trước: 8 giờ) |
| Phụ thuộc | DA-15 nhiệm vụ con 1 (MJCF tối thiểu của robot DENSO). Không còn phụ thuộc S1-02 |

## Story

Là kỹ sư simulation, tôi muốn biết SIMPLE có khôi phục được trạng thái giữa episode và đổi được hình ảnh mà giữ nguyên vật lý không, để biết phép kiểm khoanh vùng và kiểm thị giác của chẩn đoán có chạy được không.

## Tiêu chí chấp nhận

_Đổi ngày 25/10/2026 ([design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.1): Q3, Q4 trả lời trên env MuJoCo của robot DENSO thay cho SIMPLE. MuJoCo đặt state trực tiếp nên phần còn lại chủ yếu là trạng thái nằm ngoài sim._

1. Q3: lưu trạng thái MuJoCo giữa một episode (`qpos`, `qvel`, `act`, thời gian, trạng thái bộ điều khiển), khôi phục, chạy tiếp cùng chuỗi action; so với chạy liền: sai số tư thế linh kiện và góc khớp sau 1 giây. Liệt kê trạng thái nằm ngoài sim cần lưu thêm (hàng đợi action, buffer RTC của policy).
2. Q4: đổi ánh sáng và vật liệu (màu, texture) mà giữ vật lý; kiểm trạng thái vật lý từng bước trùng với khi không đổi.
3. Mỗi câu có một trong ba trả lời: "có", "không", "tạm" kèm việc còn thiếu. Đề xuất giá trị `SimCapabilities.restore_state` và `visual_override` cho `DensoMujocoSim`.
4. Kết quả ở `docs/g0/q3-q4-restore-visual.md`, có mục "Đề xuất cho 03 §3.3" ([docs/g0/README.md](../../g0/README.md)).

## Nhiệm vụ

- [ ] 1. Thử lưu và khôi phục trên MuJoCo, ghi trạng thái ngoài sim (AC 1)
- [ ] 2. Thử đổi hình ảnh giữ vật lý (AC 2)
- [ ] 3. Viết kết luận kèm đề xuất cho 03 §3.3 (AC 3, 4)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `scripts/g0/restore_probe.py`, `scripts/g0/visual_override_probe.py`
- `docs/g0/q3-q4-restore-visual.md`
- `docs/g0/ledger/S1-06.csv`

## Ghi chú cho người làm

- Nguồn: 02 · 1.5, 6.4; spec 2.4 Q3, Q4, 6.6, 6.7, 10; 03 §3.2 (dòng "Hai simulator trong một env", "Điều kiện ban đầu", "Ngẫu nhiên hóa"), §3.3 V4, V5, §5.3 quy tắc 1 (khai năng lực trung thực), §12.2; 05 SI1, SI2, mục 3 (dòng "Khoanh vùng", "Kiểm thị giác").
- PO cho phép câu trả lời tạm ở G0 vì hai phép kiểm này chỉ cần từ S4. Nếu câu trả lời là "không", spec 10 đã có phương án thay (chạy lại cùng hạt giống, để planner tiếp quản).
- Không giả lập khôi phục bằng cách chạy lại từ đầu mà vẫn báo `restore_state = True`.
- File sẽ tạo: `scripts/g0/restore_probe.py`, `scripts/g0/visual_override_probe.py`, `docs/g0/q3-q4-restore-visual.md`.

## Kiểm thử

- Script in ra sai số so với chạy liền và trả mã khác 0 nếu vượt ngưỡng đã ghi.
- Châu chạy lại một lần và ra cùng kết luận (bình luận).

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Trần Trịnh Hoàng Châu

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.5 (phần Q3, Q4); cho phép câu trả lời tạm ở G0 | SM (Bob), PO (Sarah) duyệt |
| 24/10/2026 | Thêm mục Phạm vi file. AC 4: đề xuất dòng V4, V5 ghi trong file kết quả, Hiếu gom vào 03 §3.3 ở review G0 | PO (Hiếu) |
| 25/10/2026 | Đổi sang env MuJoCo của robot DENSO; phụ thuộc DA-15 thay S1-02; 8 → 4 giờ | PO (Hiếu) theo design 25/10/2026 |
| 25/10/2026 | Chuyển cho Hưng: là khả năng của env MuJoCo (design chia làn mục 3.1) | PO (Hiếu) theo design chia làn |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
