# DA-29 · Synthetic S2: biến thể từ đoạn teleop

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt hướng 27/10/2026) |
| Người làm | Chờ PO giao |
| Làn | Adapter simulator (`flywheel-simple`) |
| Story PRD | 9.26 · Epic 9 · [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 5.4 · spec mục 6.10, tuyến T2 ở mục 10 |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:sim` |
| Sprint | S2; ít nhất 30 biến thể đạt trước 13/11/2026 cho demo |
| Ước lượng | 18 giờ (khoảng 15–20, ước lượng) |
| Phụ thuộc | S1-02 (SIMPLE), S1-06 (Q3, cho phần correction), DA-03 (đoạn teleop đã cắt theo bước). Trong lúc chờ DA-03: cắt tay vài đoạn psi-data |

## Story

Là kỹ sư simulation, tôi muốn sinh biến thể từ đoạn teleop của task hai bàn theo tư thế vật và vị trí bàn mới, để có synthetic tầng S2 chạy cùng bộ điều khiển với teleop và để thuật toán Failure → Data có loại can thiệp "biến thể" và "correction".

## Tiêu chí chấp nhận

1. Từ một đoạn teleop đạt QA (psi-data hoặc bàn phím) đã cắt theo 6 bước: đoạn gần vật (tiếp cận, gắp, đặt) biến đổi theo tư thế vật và vị trí bàn mới kiểu MimicGen; đoạn đi bộ sinh lại bằng lệnh vận tốc tới decoupled WBC; nối bằng IK của SIMPLE; chạy ở `--sim-mode=mujoco` trong env Teleop.
2. Điều kiện mới lấy trong miền train, không dùng tham số Level 1, Level 2 (spec mục 7.3).
3. Chỉ nhận biến thể chạy lại trong sim đạt `check_success`; lượt hỏng vẫn ghi lý do và chi phí.
4. Mỗi biến thể ghi `synthetic_tier = S2`, `action_quality = planned`, episode cha, tham số biến đổi, khoảng cách điều kiện tới demo gốc.
5. Correction: từ một trạng thái lỗi đã lưu của policy (`SimulatorAdapter.snapshot()`), sinh đoạn phục hồi bằng planner tới hết bước k; chỉ làm khi S1-06 trả lời Q3 là "có" hoặc "tạm".
6. Đo tỉ lệ sinh đạt, thời gian và chi phí mỗi biến thể; ghi sổ chi phí. Có ít nhất 30 biến thể đạt cho demo (DA-28).

## Nhiệm vụ

- [ ] 1. Biến đổi đoạn gần vật theo tư thế vật mới (AC 1)
- [ ] 2. Sinh lại đoạn đi bộ, nối đoạn, chạy trong env Teleop (AC 1, 2)
- [ ] 3. Lọc theo `check_success`, ghi `meta` và lineage (AC 3, 4)
- [ ] 4. Correction từ trạng thái lỗi (AC 5)
- [ ] 5. Đo tỉ lệ sinh đạt và chi phí, sinh 30 biến thể cho demo (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-simple/src/flywheel_simple/generators/variants/`, `packages/flywheel-simple/tests/generators/variants/`
- `configs/sim/variants.yaml`
- `docs/g0/s2-variants.md`, `docs/g0/ledger/DA-29.csv`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 5.4; spec mục 4.1 (biến thể không tính là demo gốc), 6.10, 10 (tuyến T2); 03 mục 5.4 (`TeleopVariantGenerator`).
- Cúi người và đi bộ làm phép biến đổi khó hơn tay cố định (spec mục 10, rủi ro của T2); ghi rõ phần nào của task biến đổi được.
- Trước PR `chore-restructure`, nếu `packages/flywheel-simple/` chưa có, để mã tạm ở `scripts/g0/s2/` và báo Hiếu.
- Dữ liệu sinh ra để trong `fwdata/`, không commit.

## Kiểm thử

- Với một đoạn mẫu và một điều kiện cố định, biến thể sinh ra tất định theo hạt giống.
- Người review chạy lại 5 biến thể và ra tỉ lệ sinh đạt cùng bậc.

## Người phụ trách

- Làm: chờ PO giao
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 27/10/2026 | Tạo story: trưởng nhóm chốt synthetic S1 và S2 trước demo | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
