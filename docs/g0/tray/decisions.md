# Quyết định của task bê khay (DA-32)

Quyết định nhỏ khi làm DA-32, theo [design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md) và [plan DA-32](../../superpowers/plans/2026-10-28-da32-tray-task.md). Mỗi dòng ghi lý do và giá phải trả nếu sai.

| Mã | Ngày | Quyết định | Lý do | Nếu sai |
|---|---|---|---|---|
| D-01 | 30/10/2026 | Va chạm dựng bằng hộp từ `tray.yaml`; mesh SimReady (CC-BY-4.0) chỉ để render, `contype = 0`, không khối lượng; hộp bị mesh che chuyển sang group 3 (không vẽ). Tay cầm và vách chia vẫn hiện vì thùng SimReady không có **[Đã chốt, Hiếu]** | MuJoCo va chạm mesh bằng bao lồi, nên thùng rỗng thành khối đặc; payload MuJoCo của SimReady cũng khai `convexHull`. Ảnh camera giống nhà máy hơn hộp màu trơn | Bỏ lớp render; vật lý không đổi. Đo 30 s cảnh tĩnh: khay xê dịch 2,04 mm, xuyên tối đa 0,57 mm, giống hệt nhau khi có và không có mesh |
| D-02 | 30/10/2026 | `tray.yaml` là YAML phẳng `khóa: số`, đọc bằng loader nhỏ trong `config.py` **[Đề xuất]** | Workspace không có PyYAML; thêm phụ thuộc phải sửa `pyproject.toml` và `uv.lock`, nằm ngoài Phạm vi file của DA-32 | Đổi sang `yaml.safe_load` khi có PR phụ thuộc |
| D-03 | 30/10/2026 | Tâm khay cách mép bàn A phía hành lang 0,25 m (plan: 0,15 m) **[Đề xuất]** | Ở 0,15 m, khay rộng 0,30 m nằm sát mép, nên mọi dịch chuyển ở mức ngẫu nhiên hóa 1 đều đẩy khay ra ngoài bàn. 0,25 m ≥ nửa bề ngang khi xoay 10° (0,187 m) cộng 0,05 m | Robot phải với xa thêm 0,10 m; chỉ sửa một giá trị config |
| D-04 | 30/10/2026 | Độ thẳng người đo trên `torso_link` (plan: hông) **[Đề xuất]** | Ngưỡng ≥ 0,99 của AC 1 lấy từ số đo S1-02 trên `torso_link`; hông lắc tới 0,983 khi đi | Sửa một dòng helper test |
