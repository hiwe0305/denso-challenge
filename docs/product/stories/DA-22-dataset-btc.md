# DA-22 · Đọc và phân tích dataset của BTC DENSO

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026 theo design 25/10/2026) |
| Người làm | Thông |
| Story PRD | Story mới của [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.2 · Epic 9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G0` · `area:data` |
| Sprint | S1 |
| Ước lượng | 10 giờ (khoảng 8–12, ước lượng của SM) |
| Phụ thuộc | Dataset từ BTC (Hiếu lấy). Thay S1-07 |

## Story

Là kỹ sư dữ liệu, tôi muốn biết dataset của BTC gồm gì và đọc nó vào định dạng chung, để biết còn phải thu bao nhiêu demo bằng bàn phím.

## Tiêu chí chấp nhận

1. Bảng kiểm kê: robot, task, định dạng, số episode, camera, fps, chiều state và action, dung lượng, giấy phép, quyền dùng, `data_class`; có câu trả lời cho câu Q-A của design 25/10 mục 12.
2. `BtcDatasetSource` đọc dataset vào episode bundle chung; QA của spec mục 4.4 chạy được; báo số pass, flag, reject.
3. Nếu robot trong dataset khớp robot DENSO tương đương: phát lại 5 episode bằng DA-17 và ghi kết quả.
4. Kết luận: dataset bù được bao nhiêu phần trong 100–200 demo cần cho E1 (design 25/10 mục 4.3), còn phải thu bao nhiêu bằng bàn phím.
5. Dữ liệu ở máy cục bộ, không lên Colab hay dịch vụ ngoài khi chưa có quyền (design 25/10 mục 9). Ghi chi phí vào `docs/g0/ledger/DA-22.csv`, cột theo [docs/g0/README.md](../../g0/README.md).

## Nhiệm vụ

- [ ] 1. Kiểm kê dataset (AC 1)
- [ ] 2. `BtcDatasetSource` và QA (AC 2)
- [ ] 3. Phát lại mẫu nếu robot khớp (AC 3)
- [ ] 4. Kết luận số demo còn thiếu (AC 4)
- [ ] 5. Sổ chi phí (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-ingest/src/flywheel_ingest/teleop/btc/`
- `packages/flywheel-ingest/tests/teleop/`
- `docs/g0/btc-dataset.md`, `docs/g0/ledger/DA-22.csv`

## Ghi chú cho người làm

- Nguồn: [design 25/10](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 4.2, 4.3, 9, 12.
- Không commit dữ liệu; chỉ commit thống kê và mô tả.
- Story thay S1-07 (đã hủy).

## Kiểm thử

- Bộ đọc chạy trên 3 episode mẫu và ra bundle qua validate của `contracts`.

## Người phụ trách

- Làm: Dương Tiến Thông
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hưng (robot), Châu (phát lại)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design 25/10/2026 mục 11.2 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
