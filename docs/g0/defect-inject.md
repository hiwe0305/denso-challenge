# Báo cáo và thiết kế Bộ cấy lỗi (DA-27)

Tài liệu kỹ thuật theo [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 9.2 và mục 10. Phục vụ bộ chấm DA-31 và Agent QA/QC DA-20 trước khi train model.

---

## 1. Mục tiêu và nguyên tắc thiết kế

1. **Không sửa bản gốc:** Mọi thao tác cấy lỗi chỉ thực hiện trên bản sao (deep copy), bảo toàn toàn vẹn dữ liệu gốc của `psi-data`.
2. **Khóa đáp án trước (Answer Key Lock):** Danh sách lỗi cấy và tham số được ghi vào `DefectManifest` của `flywheel.contracts` (mỗi lỗi là một `Defect`). `seal_manifest` ghi `defect_manifest.json` và `defect_manifest.sha256` ở thư mục đáp án riêng, và từ chối ghi vào bên trong thư mục bản sao mà agent đọc (`copy_roots`). Chỉ bộ chấm (`flywheel.eval.agentqa.bench`, DA-31) đọc file này; test `test_read_barrier.py` quét mã của agent (`flywheel.eval.agentqa`, trừ `bench/`) và của phép kiểm (`flywheel.data`, trừ `inject/`, `cli.py`, `api.py`) và đỏ nếu có chỗ nào nhắc tới `DefectManifest`, `defect_manifest` hay `load_manifest`.
3. **Đối chứng sạch (Clean Baseline):** Luôn sinh kèm một tập sạch có kích thước tương đương để đo tỉ lệ báo nhầm (False Positive Rate). Bản sạch chép từ bản gốc, không từ bản cấy. Hai bản sao mang id trung tính cùng dạng `bench-<12 hex>` (`copy_ids(seed)`), không chứa chữ nào lộ vai trò như `clean`, `defect`; bản nào là bản sạch chỉ thấy trong `DefectManifest` (bản sạch có `defects` rỗng), file chỉ bộ chấm đọc.
4. **Rào chắn Release (Release Barrier):** mọi episode của hai bản sao chấm, cả episode có lỗi lẫn episode sạch, mang `EpisodeMetadata.benchmark_copy_id` (bằng `dataset_id` của bản sao) và bị từ chối nếu đưa vào tập huấn luyện hoặc release chính thức. Đáp án chỉ nằm trong `DefectManifest`, không ghi lên episode, nên agent đọc episode không biết episode nào có lỗi (design mục 6.1, 9.2; 03 bản 1.0 mục 4.3; issue #62). `release` của DA-03 gọi `flywheel.data.inject.api.has_injected_defect(episode)` trên `Episode` của hợp đồng.

---

## 2. Danh mục 11 loại lỗi dữ liệu (F-DATA)

Cấu hình tại `configs/data/inject.yaml`. Mã lỗi theo bảng ánh xạ của design mục 9.2 (sửa 3/11/2026, issue #34): `Defect.code` ghi mã mục 10, `parameters["kind"]` ghi tên loại. Recall của DA-31 tính theo loại, precision tính theo mã.

Số episode cấy (quyết định PO 3/11/2026): mỗi loại đúng 3 episode khác nhau (`episodes_per_kind: 3`), tổng 33 trên 99; mỗi episode mang tối đa một lỗi. Với `duplicate_episode`, chỗ được chọn bị ghi đè bằng bản sao của một episode không cấy; bản gốc giữ nguyên, chỉ bản sao tính là episode cấy. Cùng `seed` cho cùng manifest.

Chỉ ghi lỗi đã cấy thật (DA-31 tính recall theo loại từ manifest): episode không có gì để lỗi đó thay đổi (ví dụ mọi chiều góc của action bằng 0) bị bỏ qua, bộ cấy chọn episode khác; sau khi cấy, `flywheel.data.inject.applied.defect_applied` kiểm từng dòng manifest đúng là đã đổi dữ liệu ở chỗ nó ghi, sai thì dừng. Chiều action theo layout 36 chiều của G1 (design mục 9.2). Khi truyền `ActionLayout` (ví dụ `meta/action_layout.json` của export), lỗi trên action bỏ qua chiều bị mask và chiều layout không có.

| Mã | Loại (`kind`) | Tên lỗi | Mô tả cơ chế cấy | Tham số cấu hình |
|---|---|---|---|---|
| D1 | `nan_values` | Giá trị NaN/Inf | Gán giá trị NaN vào quan sát hoặc hành động | `nan_ratio: 0.05` |
| D2 | `drop_frames` | Rơi khung ảnh | Loại bỏ ngẫu nhiên 10–20% khung hình ảnh | `drop_rate: 0.15` |
| D2 | `timestamp_sync_offset` | Lệch đồng bộ camera và state | Dịch chuyển mốc thời gian của ảnh so với state | `offset_seconds: 0.08` (> τ_sync 0.033s) |
| D3 | `joint_jump` | Nhảy khớp đột ngột | Cộng bước nhảy vào một chiều khớp (0–30) của action ở giữa episode | `jump_magnitude: 1.5` |
| D3 | `joint_limit_exceeded` | Vượt giới hạn khớp | Đặt một chiều khớp (0–30) của action vượt `limit_high` của `ActionLayout` thêm 25% biên độ khớp; không có layout thì dùng ±π | `excess_factor: 1.25` |
| D3 | `unit_deg_rad` | Sai đơn vị góc | Nhân một chiều góc (0–30, 35) của action, khác 0 trên episode, với $180/\pi$ | `scale: 57.2957795` |
| D5 | `duplicate_episode` | Trùng lặp episode | Nhân bản episode với dữ liệu giống hệt | `dup_id` |
| D5 | `holdout_seed_leak` | Rò hạt giống holdout | Gán seed ngẫu nhiên nằm trong dải bí mật holdout | `holdout_seed_range: [9000, 9999]` |
| D6 | `corrupted_success_label` | Sai nhãn thành công | Đảo nhãn `sim_success` (thất bại gán thành công) | boolean flip |
| D6 | `wrong_task_instruction` | Sai câu lệnh task | Đổi câu lệnh gốc thành câu lệnh sai lệch | `corrupted_prompt` |
| D7 | `action_sign_flip` | Đảo dấu action | Đổi dấu một chiều action có độ lệch chuẩn khác 0 trên episode | chọn theo episode |

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

* **Unit tests:** 62 test case tự động tại `packages/flywheel-data/tests/unit/inject/`.
* **Độ bao phủ:** 100% các loại lỗi cấy đều có test kiểm chứng.
* **Độc lập kiến trúc:** Không import vòng, tuân thủ nghiêm ngặt 3 hợp đồng kiến trúc của repo.
