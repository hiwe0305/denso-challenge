# Phân tích gói psi-data (Q1, V1, V6, V9)

_Ngày 29/10/2026. Story [S1-07](../product/stories/S1-07-phan-tich-psi-data.md), cổng G0. Người thực hiện: Dương Tiến Thông. Duyệt và merge: Dương Đình Hiếu._

Tài liệu này tổng hợp kết quả phân tích gói dữ liệu teleop task hai bàn (`G1WholebodyLocomotionPickBetweenTablesTeleop-v0`) và tập eval trong `USC-PSI-Lab/psi-data`.

---

## 1. Tải và mã băm SHA-256 (AC 1)

Dữ liệu được lưu trữ ngoài git tại `fwdata/psi-data/`. Mã băm sha256 đối chứng:

| Gói dữ liệu | File cục bộ | Kích thước | SHA-256 |
|---|---|---|---|
| Task hai bàn Teleop | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | 203 MB | `6cdf9022c23649f68d2faf418a97c47c01aca9d1fac27e9af366116d69927586` |
| Task hai bàn Eval | `simple-eval-G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | 378 KB | `8a4b0ff7d068967dac8baec2c4a4deca4f644215a1ee15e921739f3dfe90e7e0` |
| F1 BendPick Teleop | `G1WholebodyBendPickTeleop-v0.zip` | ~180 MB | `7299a94f56fca554909a5b3a886b722ee26a11e49cbda0865efad324424900a3` |
| F1 BendPick MP | `G1WholebodyBendPickMP-v0.zip` | ~195 MB | `81f1295b95ba07897cbb1a982f63507cf2724490f0559eb412f94c34cb299401` |

---

## 2. Kết quả QA sơ bộ và đếm N_teleop (AC 2 · Q1)

Kiểm tra 7 phép kiểm QA sơ bộ trên toàn bộ episode teleop của task hai bàn:

| Tiêu chí | Kết quả | Ghi chú |
|---|---|---|
| Tổng số episode kiểm tra | `99` | Số episode có trong bundle |
| Timestamp tăng đơn điệu | `99/99` | Không bị lùi hay đứt quãng thời gian |
| Không chứa giá trị NaN / Inf | `99/99` | Giá trị sensor và action số thực hợp lệ |
| Độ dài hợp lý ($\ge 0.5$ s) | `99/99` | Đủ độ dài cho cả chu trình gắp và đi |
| Đạt cờ thành công | `99/99` | Tiêu chí hoàn thành task |
| **N_teleop đạt chuẩn QA** | **99** | **Đạt ngưỡng tối thiểu** |

> **Kết luận cho lưới HE:** N_teleop = 99 >= 80. HE grid keeps 80 demo endpoint (10, 20, 40, 80).

---

## 3. Cấu trúc LeRobot và đối chiếu action_layout (AC 3 · V1)

Thông tin trích xuất từ `meta/info.json` của LeRobot dataset:

* **Phiên bản codebase (`codebase_version`):** `v2.1`
* **Tần số điều khiển (`fps`):** `50 Hz` (chu kỳ 20 ms)
* **Robot:** `g1` (Unitree G1)
* **Số chiều Observation State:** `32` chiều (khớp góc khớp, vận tốc góc, IMU thân)
* **Số chiều Action:** `36` chiều
* **Camera quan sát:** 1 camera (observation.images.egocentric)
* **Độ phân giải camera:** observation.images.egocentric: 360x640

### So sánh với action_layout 36 chiều của $\Psi_0$ (`pad36`)

* $\Psi_0$ yêu cầu vector hành động chuẩn hóa 36 chiều:
  * 12 bậc tự do chân (6 bậc mỗi chân).
  * 3 bậc tự do thắt lưng (yaw, roll, pitch).
  * 14 bậc tự do cánh tay (7 bậc mỗi tay).
  * 2 bậc tự do bàn tay Dex3 (lệnh kẹp/mở).
  * 5 chiều đệm (zero-padded) có mask kèm theo.
* **Đối chiếu:** Vector action thô trong dữ liệu là `36` chiều. Khi nạp vào pipeline Flywheel (`Normalize` $\rightarrow$ `Export`), module `Normalize` sẽ map các kênh vào đúng vị trí và đệm 0 thành 36 chiều chuẩn theo config `configs/embodiments/g1.yaml`.

---

## 4. Phân tích Seed và Ngẫu nhiên hóa (AC 4 · V6)

* **Episode có ghi seed không:** Không ghi trường seed riêng lẻ trên từng dòng parquet của LeRobot v2.1; trạng thái ban đầu được tuần tự hóa thông qua `state_dict` trong cấu hình môi trường SIMPLE.
* **Dải seed của `simple-eval`:** Tác giả sử dụng tập seed cố định cho các episode đánh giá từ `0` đến `24` (`simple-eval/`).
* **Đề xuất tách dải seed cho đội:**
  * Dải `dev`: `1000..1999`.
  * Dải `gate` (cổng dev): `2000..2999`.
  * Dải `holdout` (đánh giá độc quyền): `9000..9999` (được bảo vệ trong `vault/`, chỉ `gate` được đọc qua lệnh `fw holdout run`).

---

## 5. Bảng trạng thái Giấy phép & Câu hỏi (AC 5 · V9)

| Tài sản | Nguồn | Giấy phép tìm thấy | Kết luận sử dụng |
|---|---|---|---|
| `USC-PSI-Lab/psi-data` | Hugging Face Dataset | Không ghi LICENSE rõ ràng | `license = unknown`, `data_class = restricted`. Dùng nghiên cứu nội bộ, xin xác nhận trước khi demo thương mại. |
| `USC-PSI-Lab/psi-model` | Hugging Face / GitHub | Apache 2.0 (code) | Checkpoint mở cho nghiên cứu; tuân thủ Apache 2.0. |
| `SIMPLE Simulator` | GitHub | MIT License | Đầy đủ quyền tích hợp và phát triển. |
| `Cảnh HSSD (Habitat)` | Habitat-Sim / AllenAI | CC-BY-NC | Chỉ học thuật. Môi trường MuJoCo của đội dùng sàn phẳng độc lập với HSSD. |
| `Tài sản Objaverse` | Objaverse 1.0 | CC-BY 4.0 / CC0 | Ghi danh tác giả trong manifest release. |

### Thư gửi tác giả PSI Lab:
```text
Kinh gui USC PSI Lab,

Chung toi la doi nghien cuu ilovephysicalintelligence dang thuc hien du an nghien cuu mo ve Humanoid Data Flywheel tren nen tang SIMPLE va mo hinh Psi-0 (arXiv:2603.12263).
Chung toi dang thu nghiem danh gia va tai tao tren task hai ban (G1WholebodyLocomotionPickBetweenTablesTeleop-v0).
Xin hoi phong Lab:
1. Goi dataset USC-PSI-Lab/psi-data duoc phat hanh theo giay phep ban quyen nao (Apache 2.0, MIT, hay CC-BY)?
2. Cac checkpoint cong bo trong USC-PSI-Lab/psi-model co duoc phep fine-tune va cong bo ket qua benchmark doi chung khong?
3. So buoc pretraining chinh xac cua cac checkpoint ablation (V-EGO, V-EGO10, V-NOEGO) la bao nhieu?

Tran trong cam on!
```

---

## 6. Thống kê mô tả Dataset (AC 6)

* **Tổng số episode:** 99
* **Tỉ lệ thành công:** 100.0%
* **Độ dài trung bình:** 634.0 frames (12.68 giây ở 50 Hz)
* **Độ dài ngắn nhất:** 482 frames (9.64 s)
* **Độ dài dài nhất:** 1248 frames (24.96 s)
* **Độ dài trung vị:** 598.0 frames

---

## 7. Đề xuất cho 03 §3.3 (AC 7)

Căn cứ vào kết quả spike S1-07, đề xuất cập nhật các dòng tương ứng trong mục 3.3 của [03 · Kiến trúc](../product/03-architecture.md):

| Dòng | Câu trả lời đề xuất | Trạng thái | Bằng chứng |
|---|---|---|---|
| **V1** | Gói task hai bàn mang `codebase_version = "v2.1"`, fps = 50, action = 36 chiều (chuẩn hóa 36 chiều pad36), state = 32 chiều, camera egocentric 360x640. | Có | `meta/info.json` và phân tích trong `scripts/g0/inspect_psi_data.py`. |
| **V6 (dữ liệu)** | Episode không ghi seed trực tiếp mà qua layout blob `state_dict`. `simple-eval` dùng seed cố định 0..24. Đội tách dải dev `1000..1999` và holdout `9000..9999`. | Có | Cấu trúc `episodes.jsonl` và `simple-eval/`. |
| **V9** | `psi-data` chưa có LICENSE rõ ràng (`unknown` / `restricted`); `psi-model` Apache 2.0; SIMPLE MIT; HSSD CC-BY-NC (đội tách cảnh sàn MuJoCo khỏi HSSD). Đã soạn thư hỏi PSI Lab. | Có | Bảng kiểm soát giấy phép mục 5; quyết định PO 04 §1.3. |
