# DA-18 · Video egocentric thô thành dữ liệu fine-tune stage 1

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; sửa theo design chia làn cùng ngày) |
| Người làm | Thông |
| Làn | Dữ liệu |
| Story PRD | Story mới của [design MuJoCo 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) và [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `area:data` |
| Sprint | S2–S3 |
| Ước lượng | 27 giờ (khoảng 22–32, ước lượng của SM) |
| Phụ thuộc | DA-04 (che danh tính, cắt đoạn, pose; cùng người làm), DA-01. PR `chore-restructure` (07 mục 3.6, hết 27/10) tạo khung package `flywheel-data`. Code trên đoạn EgoDex mẫu |

## Story

Là kỹ sư dữ liệu, tôi muốn biến video egocentric thô hợp task DENSO thành dữ liệu mà code stage 1 của Ψ₀ đọc được, để Hiếu fine-tune VLM trên cảnh nhà máy.

## Tiêu chí chấp nhận

1. Che danh tính là bước đầu tiên; `deid_status` bắt buộc trước mọi bước sau.
2. Gán nhãn bằng model cục bộ (design chia làn mục 10.2): RoboBrain 2.5-4B gợi ý ranh giới 6 bước task, Molmo2-4B theo dõi tay và linh kiện; người duyệt mẫu. Vòng thử ở design chia làn mục 10.3 chạy trước khi chốt, ghi `Decision`.
3. Pose tay 3D và tư thế camera: E-B đọc từ thiết bị, E-A ước lượng, gắn `action_quality = pseudo`.
4. Xuất đúng định dạng mà `src/psi/data/egodex/egodex_dataset.py` của Ψ₀ ở commit ghim đọc; stats bằng `scripts/data/calc_egodex_stats.py`; contract test đọc lại một batch.
5. Câu lệnh mỗi đoạn và bộ câu hỏi đáp về linh kiện, khay, máy, bước đang làm (cho probe P1).
6. Dataset ghi `data_class` gộp theo mức chặt nhất; dữ liệu DENSO không lên Colab khi chưa có quyền.

## Nhiệm vụ

- [ ] 1. Nối che danh tính, cắt đoạn của DA-04 (AC 1)
- [ ] 2. Vòng thử model gán nhãn, chốt Decision (AC 2)
- [ ] 3. Pose E-A, E-B (AC 3)
- [ ] 4. Export EgoDex, stats, contract test (AC 4)
- [ ] 5. Câu lệnh, câu hỏi đáp, `data_class` (AC 5, 6)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-data/src/flywheel/data/ingest/egocentric/`, `packages/flywheel-data/src/flywheel/data/annotate/egocentric/`, `packages/flywheel-data/src/flywheel/data/export/egodex.py`
- `packages/flywheel-data/tests/unit/egocentric/`, `packages/flywheel-data/tests/contract/egocentric/`
- `configs/data/egocentric.yaml`
- `docs/g0/egocentric-stage1.md`

## Ghi chú cho người làm

- Nguồn: [design MuJoCo](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 5.2; [design chia làn](../../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md) mục 10, 11; design 23/10 mục 5.3, 6.1.
- Chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); không import làn khác hay adapter (03 mục 7.3). Thiếu trường trong schema thì báo Hiếu mở PR hợp đồng, không thêm trường tạm.
- Model gán nhãn chạy qua endpoint cục bộ khai trong `configs/models/` (Hiếu); dev dùng model giả của testkit.
- RunPlan fine-tune stage 1 do Hiếu viết và chạy; story này chỉ giao dataset.

## Kiểm thử

- Contract test AC 4 chạy trong CI trên đoạn mẫu nhỏ, không cần GPU.
- Đoạn chưa che danh tính bị từ chối ở mọi bước sau.

## Người phụ trách

- Làm: Dương Tiến Thông
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Hiếu (stage 1), Châu (probe P1)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story theo design MuJoCo 25/10/2026 mục 11.2 | PO (Hiếu) |
| 25/10/2026 | Viết lại theo design chia làn: chuyển sang làn Dữ liệu; thêm model gán nhãn và vòng thử; RunPlan stage 1 chuyển cho Hiếu | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
