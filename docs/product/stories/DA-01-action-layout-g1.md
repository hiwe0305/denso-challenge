# DA-01 · Định dạng episode chung và `action_layout` của G1

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (Hiếu viết cùng Claude 3/11/2026, theo quyết định PO 3/11/2026: Hiếu và Claude làm song song mọi việc đang mở) |
| Người làm | Long (chủ story, 07 mục 2.2); phần `configs/embodiments/g1.yaml` do Hiếu và Claude làm |
| Làn | Nhân (`flywheel-contracts`) và cấu hình embodiment (`configs/embodiments/`, chủ là Hiếu, 07 mục 2.1) |
| Story PRD | 9.1 · Epic 9 · FR48; [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 6.1, 6.2, 9.2 |
| Nhãn | [Lõi] · `epic:9` · `gate:G1` · `area:core` |
| Sprint | S1 · **Lịch 3/11/2026:** merge trước **5/11/2026** (07 mục 2.4) |
| Ước lượng | 10 giờ (07 mục 2.3, ước lượng) |
| Phụ thuộc | S1-10. Schema `Episode`, `ActionLayout`, `ActionDimension` đã có trên master qua DA-25 (`1111387`); `ControlSpec` có trong `flywheel.contracts.v0` (S1-08) |

## Story

Là người của mọi làn, tôi muốn một file `configs/embodiments/g1.yaml` mô tả đúng 36 chiều action của G1 trong SIMPLE và cặp kênh lệnh, đo của decoupled WBC, để chẩn đoán train (DA-08), phát lại (DA-17), lỗi cấy (DA-27) và export (DA-02) cùng đọc một layout thay vì mỗi làn tự chép một bản.

## Tiêu chí chấp nhận

1. `configs/embodiments/g1.yaml` có khóa `action_layout` validate được bằng `ActionLayout` của `flywheel.contracts.artifacts` như trên master, không thêm trường mới vào hợp đồng.
2. Đúng 36 chiều thật, không chiều nào `masked` (design mục 6.2, sửa 3/11/2026). Mỗi đoạn của layout Ψ₀ `cda3fdf` là một nhóm riêng, hai đoạn kề nhau khác nhóm: 0–13 bàn tay, 14–27 cánh tay, 28–30 hông roll/pitch/yaw, 31 chiều cao thân (m), 32–33 vận tốc tương đối, 34 lệnh rẽ, 35 hướng đích (rad).
3. Chiều 34 ghi là giá trị liên tục (input thô của cần điều khiển), WBC chỉ quay khi |giá trị| ≥ 0,1 (design mục 9.2, sửa 3/11/2026). Chiều 31 ghi là hằng số 0,74 m trên task hai bàn.
4. Mỗi sự thật trong file trích nguồn theo commit: Ψ₀ `cda3fdf`, `songlin/decoupled_wbc@5b304e4`, SIMPLE, psi-data `e78fb93`. Giới hạn khớp của chiều 0–30 lấy từ MJCF `g1_sonic`, có sha256 của file; chiều 31–35 không có giới hạn khớp.
5. `control_spec` theo decoupled WBC, validate được bằng `ControlSpec` của `flywheel.contracts.v0`: hai nhóm thân trên, thân dưới (03 mục 5.2, ADR-15); mỗi nhóm có số kênh lệnh bằng số kênh đo; kênh lệnh phủ đủ 36 chiều action, mỗi chiều đúng một lần.
6. Hai seam của demo trong `tests/e2e/test_demo_seams.py` qua, không xfail: `test_g1_action_layout_follows_psi0_slices`, `test_psi0_metrics_log_is_diagnosed_on_the_g1_layout`.

## Nhiệm vụ

- [x] 1. Viết file story (AC 1–6)
- [ ] 2. `action_layout` 36 chiều của G1 trong `configs/embodiments/g1.yaml`, trích nguồn theo commit (AC 1–4, 6)
- [ ] 3. `control_spec` theo decoupled WBC và test validate `ControlSpec` (AC 5)
- [ ] 4. `segments.parquet` của bundle episode (07 mục 2.2 nhiệm vụ con gợi ý 3; chưa làm trong PR này)
- [ ] 5. Test tính chất cho validate `Episode`, `ActionLayout` (07 mục 2.2 nhiệm vụ con gợi ý 4; chưa làm trong PR này)

Nhiệm vụ con gợi ý 1 và 2 của 07 mục 2.2 (schema Episode có trường mới, schema `action_layout` và mask) đã có trên master qua DA-25, nên không lặp lại ở đây.

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `configs/embodiments/`
- `tests/e2e/test_demo_seams.py`: chỉ thêm test `control_spec` của AC 5 cạnh hai seam đã có

## Chỗ cần PO quyết hoặc biết

1. **`ACTION_SLICES_36D` của Ψ₀ không phủ 36 chiều.** Ở `cda3fdf` (`src/psi/data/simple/__init__.py`, sha256 `ddb135a2…`), danh sách `ACTION_SLICES_36D` chỉ có 6 đoạn cho chiều 0–27 (`left_arm`, `right_arm`, `left_hand_thumb`, `left_hand_index`, `left_hand_middle`, `right_hand`). Chiều 28–35 chỉ có trong khối chú thích đầu file. Design mục 9.2 và comment của seam ghi layout 7 đoạn là "`ACTION_SLICES_36D`"; đúng về nội dung, nhưng nguồn chính xác là khối chú thích. Không sửa design; `g1.yaml` trích cả hai.
2. **Chú thích Ψ₀ đặt mốc `base_height` là 0,75 m**; dữ liệu psi-data và `height_cmd` của config WBC là 0,74 m. File ghi 0,74 là giá trị trên task hai bàn.
3. **Tên ngón tay trái 3–6.** Chú thích Ψ₀ gọi 3:5 là `index`, 5:7 là `middle`; dữ liệu giữ `middle` ở 3–4, `index` ở 5–6 theo thứ tự của `postprocess_psi0_sonic.py` của SIMPLE ([psi-data](../../g0/psi-data.md) mục 2). Tên chiều trong `g1.yaml` theo SIMPLE.
4. **Nhóm khác với export khay.** `meta/action_layout.json` của export khay DA-33 chia nhóm mịn hơn (`left_hand`, `right_hand`, `left_arm`, `right_arm`, `waist`, `base_height`, `navigate`) và không qua được seam của AC 2. `g1.yaml` dùng đúng tên nhóm DA-19 đang ghi trong `loss_by_group` (`hand`, `arm`, `torso_rpy`, `height`, `base_velocity`, `turn`, `target_yaw`). Đổi export cho khớp là việc của chủ `flywheel-simple` (Hiếu), PR riêng.

## Ghi chú cho người làm

- Seam đọc `raw["action_layout"]`; khóa khác trong file (`control_spec`, `sources`) không ảnh hưởng `ActionLayout`.
- Giới hạn khớp đọc từ `data/robots/g1_sonic/g1_29dof_with_hand.xml`, file SIMPLE tự tải từ Hugging Face `USC-PSI-Lab/SIMPLE` (không nằm trong git của SIMPLE), nên trích bằng sha256 của file thay cho commit.
- Tên kênh đo của `control_spec` là khóa observation của `G1GearWbcPolicy`; tên chính xác chốt ở V2 và V7 (03 mục 5.2).

## Kiểm thử

- `uv run pytest tests/e2e/test_demo_seams.py`
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports` theo README gốc; `python3 scripts/repo/check_links.py`.

## Người phụ trách

- Chủ story: Long
- Làm phần `g1.yaml`: Dương Đình Hiếu cùng Claude (quyết định PO 3/11/2026)
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Long (hợp đồng `ActionLayout`, `ControlSpec`), Châu (DA-08 đọc layout)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 3/11/2026 | Viết file story; nhiệm vụ 1–3 cho `configs/embodiments/g1.yaml`; nhiệm vụ 4, 5 để lại cho chủ story | Hiếu cùng Claude |

## Ghi chép khi làm

- Giờ thực: xem `Time-spent` của từng commit.
