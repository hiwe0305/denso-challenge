# DA-04 · Pipeline egocentric trên mẫu EgoDex và video tự quay

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 27/10/2026) |
| Người làm | Chờ PO giao |
| Làn | Dữ liệu |
| Story PRD | 9.4 · Epic 9 · [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 5.0, 6.6 |
| Nhãn | [Lõi] · `epic:9` · `gate:G1` · `area:data` |
| Sprint | S1–S2; mẫu EgoDex qua đủ 6 tầng trước 10/11/2026 cho demo; video tự quay khi có |
| Ước lượng | 30 giờ (khoảng 25–35, ước lượng) |
| Phụ thuộc | DA-01 (trường `deid_status`, `source_kind = egocentric`), DA-25 (schema). PR `chore-restructure` tạo khung `flywheel-data`. Trong lúc chờ: code trên vài đoạn EgoDex mẫu trong testkit |

## Story

Là kỹ sư dữ liệu, tôi muốn video egocentric của người đi qua cùng sáu tầng của data flywheel, để loại dữ liệu egocentric có pipeline chạy được ngay trên dữ liệu công bố và nhận được video đội tự quay hay video nhà máy sau này mà không đổi gì.

## Tiêu chí chấp nhận

1. Ingest mẫu EgoDex ở một tập con ghim (task gần gắp và đặt, câu Q-27H của design), ghi sha256, giấy phép, `data_class`; dữ liệu ngoài git.
2. **Che danh tính trước mọi bước khác**: mặt, thẻ tên, màn hình; `deid_status` đi từ `raw` sang `blurred` hoặc `verified`; catalog chặn episode `raw` rời tầng Annotate (NFR13, có test).
3. Cắt đoạn theo 6 bước của task hai bàn khi video là task hai bàn; với EgoDex cắt theo đoạn gắp và đặt; luật trước, model gợi ý khi luật mơ hồ, người duyệt mẫu; mỗi đoạn có câu lệnh ngôn ngữ (`segments.parquet`).
4. Pose tay và camera: E-B đọc trực tiếp từ EgoDex; E-A ước lượng từ RGB bằng model hand pose và SLAM, gắn `action_quality = pseudo`.
5. QA riêng của egocentric: độ tin của pose, tỉ lệ tay ra khỏi khung, độ rung; so E-A với E-B trên cùng mẫu EgoDex (bỏ dữ liệu tracking) và báo độ lệch pose.
6. Bộ đọc video đội tự quay (`EgoVideoSource`) dùng cùng pipeline; chạy được trên ít nhất một video thử khi có.
7. Báo cáo dataset (design mục 6.5) có phần egocentric: số đoạn, pass, flag, reject theo phép kiểm.

## Nhiệm vụ

- [ ] 1. Ingest tập con EgoDex, hash, nguồn (AC 1)
- [ ] 2. Che danh tính và chặn `raw` (AC 2)
- [ ] 3. Cắt đoạn và nhãn ngôn ngữ (AC 3)
- [ ] 4. Pose E-B đọc từ EgoDex (AC 4)
- [ ] 5. Pose E-A ước lượng từ RGB, so với E-B (AC 4, 5)
- [ ] 6. QA riêng và phần egocentric của báo cáo dataset (AC 5, 7)
- [ ] 7. Bộ đọc video tự quay (AC 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-data/src/flywheel/data/ingest/egocentric/`
- `packages/flywheel-data/src/flywheel/data/qa/egocentric.py`
- `packages/flywheel-data/tests/unit/egocentric/`, `packages/flywheel-data/tests/contract/egocentric/`
- `configs/data/egocentric.yaml`
- `docs/g0/egocentric.md`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 5.0, 6.6; spec mục 2.5; 02 FR50, NFR13; 03 mục 5.4 (dòng "Nguồn egocentric").
- Episode egocentric không có action robot: không bao giờ vào stage 3 (có test ở release).
- Model hand pose, SLAM và model gợi ý cắt đoạn phải chạy cục bộ; ghi model và revision trong `configs/`.
- Xuất sang định dạng stage 1 của Ψ₀ thuộc DA-18, không thuộc story này.
- Chỉ import nhân; không import làn khác hay adapter (03 mục 7.3).

## Kiểm thử

- Một episode `raw` cố đi qua Annotate bị chặn.
- Chạy lại pipeline trên cùng tập con EgoDex cho cùng số đoạn và cùng hash.
- Độ lệch E-A so với E-B được tính trên cùng khung hình, có test với dữ liệu giả biết trước đáp án.

## Người phụ trách

- Làm: chờ PO giao
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 27/10/2026 | Tạo file story; trước đó DA-04 chỉ có trong bảng 07 mục 2.2. Mở lại theo quyết định ba loại dữ liệu (design 27/10 mục 1, câu 5–7) | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
