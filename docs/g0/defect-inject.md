# Báo cáo và thiết kế Bộ cấy lỗi (DA-27)

Tài liệu kỹ thuật theo [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 9.2 và mục 10. Phục vụ bộ chấm DA-31 và Agent QA/QC DA-20 trước khi train model.

---

## 1. Mục tiêu và nguyên tắc thiết kế

1. **Không sửa bản gốc:** Mọi thao tác cấy lỗi chỉ thực hiện trên bản sao (deep copy), bảo toàn toàn vẹn dữ liệu gốc của `psi-data`.
2. **Khóa đáp án trước (Answer Key Lock):** Danh sách lỗi cấy và tham số được ghi vào `DefectManifest` của `flywheel.contracts` (mỗi lỗi là một `Defect`), băm SHA-256 lưu thành file `.sha256`. Agent QA/QC và bộ kiểm tra thông thường bị chặn không được đọc file đáp án này.
3. **Đối chứng sạch (Clean Baseline):** Luôn sinh kèm một tập sạch có kích thước tương đương để đo tỉ lệ báo nhầm (False Positive Rate).
4. **Rào chắn Release (Release Barrier):** Bất kỳ episode nào mang `EpisodeMetadata.injected_defect` (`InjectedDefect` của hợp đồng) đều bị từ chối và chặn đứng hoàn toàn nếu cố tình đưa vào tập huấn luyện hoặc release chính thức.

---

## 2. Danh mục 11 loại lỗi dữ liệu (F-DATA)

Cấu hình tại `configs/data/inject.yaml`. Mã lỗi theo bảng ánh xạ của design mục 9.2 (sửa 3/11/2026, issue #34): `Defect.code` ghi mã mục 10, `parameters["kind"]` ghi tên loại. Recall của DA-31 tính theo loại, precision tính theo mã.

| Mã | Loại (`kind`) | Tên lỗi | Mô tả cơ chế cấy | Tham số cấu hình |
|---|---|---|---|---|
| D1 | `nan_values` | Giá trị NaN/Inf | Gán giá trị NaN vào quan sát hoặc hành động | `nan_ratio: 0.05` |
| D2 | `drop_frames` | Rơi khung ảnh | Loại bỏ ngẫu nhiên 10–20% khung hình ảnh | `drop_rate: 0.15` |
| D2 | `timestamp_sync_offset` | Lệch đồng bộ camera và state | Dịch chuyển mốc thời gian của ảnh so với state | `offset_seconds: 0.08` (> τ_sync 0.033s) |
| D3 | `joint_jump` | Nhảy khớp đột ngột | Cộng bước nhảy lớn vào giá trị khớp giữa episode | `jump_magnitude: 1.5` rad/s |
| D3 | `joint_limit_exceeded` | Vượt giới hạn khớp | Nhân giá trị khớp vượt ngưỡng cơ học $>\pi$ | `excess_factor: 1.25` |
| D3 | `unit_deg_rad` | Sai đơn vị góc | Nhân nhầm giữa độ (deg) và radian (rad) | `scale: 57.2957795` ($180/\pi$) |
| D5 | `duplicate_episode` | Trùng lặp episode | Nhân bản episode với dữ liệu giống hệt | `dup_id` |
| D5 | `holdout_seed_leak` | Rò hạt giống holdout | Gán seed ngẫu nhiên nằm trong dải bí mật holdout | `holdout_seed_range: [9000, 9999]` |
| D6 | `corrupted_success_label` | Sai nhãn thành công | Đảo nhãn `sim_success` (thất bại gán thành công) | boolean flip |
| D6 | `wrong_task_instruction` | Sai câu lệnh task | Đổi câu lệnh gốc thành câu lệnh sai lệch | `corrupted_prompt` |
| D7 | `action_sign_flip` | Đảo dấu action | Đổi dấu các chiều điều khiển (ví dụ cánh tay) | `dimensions: [0, 6]` |

---

## 3. Lỗi log huấn luyện (F-TRAIN) và log RTC (F-SYS)

Hỗ trợ sinh log giả định theo đúng schema của `FakeTrainer` và RTC log. `Defect.code` là mã T1–T8, R1–R2; `parameters["kind"]` giữ tên đầy đủ (ví dụ `T1_divergence`).

* **T1 (Phân kỳ):** Loss NaN hoặc tăng đột biến $> 15\times$ mức cực tiểu.
* **T2 (Không học):** Loss validation không giảm sau nhiều epoch.
* **T3 (Quá khớp):** Loss train giảm liên tục trong khi loss validation tăng $M$ lần đo.
* **T4 (Mất cân bằng nhóm):** Loss nhóm cánh tay phải đứng yên trong khi các nhóm khác giảm.
* **T5 (Chiều chết):** Phương sai dự đoán của một chiều action bằng 0.
* **T6 (Sụp mode):** Độ lệch chuẩn dự đoán $< 10^{-4}$.
* **T7 (Quên):** Điểm đánh giá P4 giảm $> 40\%$ so với checkpoint cha.
* **T8 (Gradient bất thường):** Gradient của VLM khác 0 khi đang khai báo đóng băng (frozen).
* **R1 (Độ trễ cao):** Độ trễ p99 vượt quá 120ms (ngưỡng 40ms).
* **R2 (Cạn buffer):** Bộ đệm lệnh rỗng (`buffer_level == 0`) trong 10 bước liên tiếp.

---

## 4. Kiểm thử và Nghiệm thu

* **Unit tests:** 34 test case tự động tại `packages/flywheel-data/tests/unit/inject/`.
* **Độ bao phủ:** 100% các loại lỗi cấy đều có test kiểm chứng.
* **Độc lập kiến trúc:** Không import vòng, tuân thủ nghiêm ngặt 3 hợp đồng kiến trúc của repo.
