# DA-34 · Thí nghiệm egocentric thay một phần demo robot trên task bê khay

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Nháp (PO duyệt hướng 28/10/2026); nhiệm vụ con chi tiết viết khi DA-33 có episode thành công đầu tiên |
| Người làm | Hiếu |
| Làn | Adapter Ψ₀ (`flywheel-psi0`), RunPlan |
| Story PRD | Story của [design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 6, 7 (M4, M5) |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:train` |
| Sprint | S2; M4 12/11/2026, M5 15/11/2026; nhánh B sau demo |
| Ước lượng | 15 giờ trước demo (ước lượng), không tính GPU-giờ |
| Phụ thuộc | DA-33 (release synthetic), DA-19 (adapter fine-tune trên Colab; kiểm đường `eval-decoupled-wbc` của Ψ₀), S1-03 (Q0, serve Ψ₀), S1-04 (giờ fine-tune) |

## Story

Là trưởng nhóm, tôi muốn so Ψ₀ fine-tune với đủ demo robot, với một nửa demo, và với một nửa demo trên checkpoint không có EgoDex, để biết task khay nhạy với số demo đến đâu và egocentric có bù được không.

## Tiêu chí chấp nhận

1. RunPlan cho nhánh A (N = 80), C (N = 40), C-NOEGO (N = 40, checkpoint ablation không EgoDex) với cùng recipe, cùng số bước, cùng hạt giống điều kiện; tập 40 là tập con của 80, cố định bằng hash.
2. Ba lần fine-tune stage 3 chạy trên Colab Pro hoặc server thuê, tiếp tục được từ checkpoint, ghi sổ chi phí.
3. Eval 30 điều kiện dev × 3 mức ở `sim_mode=mujoco`, đồng bộ, qua `eval-decoupled-wbc` (decoupled WBC); Ψ₀ tự xuất lệnh đi.
4. Bảng theo design mục 6.3, khoảng tin cậy bootstrap, diễn giải theo design mục 6.4 ghi "sơ bộ, trên dev"; video rollout cạnh nhau.
5. Sau khi có video egocentric: stage 1 và stage 3 của nhánh B, eval B, cập nhật bảng.

## Nhiệm vụ

- [ ] 1. RunPlan ba nhánh, chọn tập demo có hash (AC 1)
- [ ] 2. Fine-tune A, C, C-NOEGO (AC 2)
- [ ] 3. Eval và bảng kết quả, video (AC 3, 4)
- [ ] 4. Nhánh B khi có video (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `configs/runplans/tray/`
- `packages/flywheel-psi0/src/flywheel_psi0/tray/`, `packages/flywheel-psi0/tests/tray/`
- `docs/he/tray.md`, `docs/g0/ledger/DA-34.csv`

## Ghi chú cho người làm

- Quy tắc diễn giải chốt trước khi chạy (design mục 6.4); không đổi sau khi thấy kết quả.
- Kết quả trên ảnh MuJoCo không so được với số công bố của tác giả; báo cáo ghi renderer ở mọi con số.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 28/10/2026 | Tạo story nháp theo design 28/10/2026 | PO (Hiếu) |
| 28/10/2026 | Eval qua `eval-decoupled-wbc` thay đường MP với AMO | PO (Hiếu) |

## Ghi chép khi làm
