# S1-04 · Đo chi phí fine-tune Ψ₀ (Q5)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; sửa 25/10/2026) |
| Người làm | Hiếu |
| Story PRD | 1.4 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:rl` |
| Sprint | S1 (tuần 1–2), bắt đầu ngày 1 |
| Ước lượng | 18 giờ (bản trước: 12 giờ) |
| Phụ thuộc | S1-03 nhiệm vụ con 2.1 cho image Ψ₀ ở `docker/psi0/`; nhiệm vụ con 1.2 bắt đầu ngày 1. Cần ngân sách thuê GPU nếu 5090 không đủ. Từ 25/10/2026: máy là RTX 3060 12 GB và Colab Pro (A100, H100); 5090 chờ xác nhận |

## Story

Là kỹ sư robot learning, tôi muốn đo VRAM và GPU-giờ của fine-tune Ψ₀ trên dữ liệu task chính, để chốt phần cứng, cấu hình và số seed trước khi lập kế hoạch thí nghiệm.

## Tiêu chí chấp nhận

1. Chạy fine-tune ngắn (vài trăm bước) bằng script công bố của Ψ₀ trên gói task chính, từ checkpoint gốc chọn ở S1-03 (Q0, nhóm `pre.*` hoặc `postpre.*`; không dùng `simple-checkpoints`, `sonic-checkpoints`). Thứ tự thử: RTX 5090 toàn phần; nếu hết bộ nhớ thì LoRA hoặc đóng băng VLM (nếu script hỗ trợ, nếu không thì ghi lại); rồi A100 80 GB thuê.
2. Với mỗi cấu hình đã thử: VRAM đỉnh, giây mỗi bước, batch toàn cục, có hết bộ nhớ không.
3. Ước tính GPU-giờ cho S bước (S theo cấu hình công bố, spec 7.3) và cho khối lượng spec 9 bản v10.1 (khoảng 22 lần train Ψ₀ mặc định, tối đa khoảng 33 nếu thêm seed theo luật MDE hoặc mở B-fail trên Ψ₀); quy ra USD theo đơn giá A100 $1,59/giờ (giả định, spec 8.1). Ghi vào `docs/g0/ledger/S1-04.csv`, tách `estimated` và `measured`.
4. Đề xuất cấu hình (toàn phần, LoRA, đóng băng VLM), phần cứng, số seed; Hiếu duyệt. Ghi vào `configs/runplans/draft-g0.yaml`.
5. Không commit trọng số; xóa trạng thái optimizer sau khi đo và ghi chú vào sổ (03 §9.2).
6. Kết quả ở `docs/g0/psi0-finetune-cost.md`, có mục "Đề xuất cho 03 §3.3" với phần fine-tune của V8 ([docs/g0/README.md](../../g0/README.md)). Hiếu gom vào 03 §3.3 ở review G0.
7. (25/10/2026, [design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 6.3) Đo trên một A100 hoặc H100 của Colab: giây mỗi bước và VRAM cho stage 3 (`finetune-*`) và stage 2 (`posttrain-*`) với `action_layout` của robot DENSO đệm 36 chiều (dữ liệu giả cùng shape nếu chưa có dữ liệu thật); quy ra compute unit cho khối lượng spec mục 9. Dữ liệu DENSO không lên Colab (design 25/10 mục 9).
8. (25/10/2026) Đo inference Ψ₀ trên RTX 3060 12 GB: VRAM, độ trễ p50 và p99 mỗi lần suy luận, so với chu kỳ điều khiển; là đầu vào cho DA-23.

## Nhiệm vụ

- [ ] 1. Chuẩn bị (AC 1)
  - [ ] 1.1 Dùng image Ψ₀ ở `docker/psi0/` của S1-03, không dựng môi trường riêng; tải gói task chính ở revision ghim
  - [ ] 1.2 Đọc `scripts/train/psi0/finetune-simple-psi0.sh`, ghi S, batch, learning rate mặc định
- [ ] 2. Chạy thử theo thứ tự 5090 → LoRA hoặc đóng băng VLM → A100 (AC 1, 2)
- [ ] 3. Tính GPU-giờ và USD, ghi sổ (AC 3)
- [ ] 4. Viết đề xuất, Hiếu duyệt, tạo RunPlan nháp (AC 4)
- [ ] 5. Dọn trọng số, optimizer; viết tài liệu kèm đề xuất cho 03 §3.3 (AC 5, 6)
- [ ] 6. Đo stage 2 và stage 3 trên Colab, quy ra compute unit (AC 7)
- [ ] 7. Đo inference trên 3060 (AC 8)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `scripts/g0/finetune_probe.sh`
- `docs/g0/psi0-finetune-cost.md`
- `configs/runplans/draft-g0.yaml`
- `docs/g0/ledger/S1-04.csv`
- `scripts/g0/colab_train_probe.sh`, `scripts/g0/infer_latency_probe.py`
- Không sửa thư mục docker/psi0 của S1-03; cần đổi image thì báo Hiếu sửa trong nhánh S1-03

## Ghi chú cho người làm

- Nguồn: 02 · 1.4; spec 2.1, 2.4 (Q0), 7.3, 7.5 (luật MDE), 8.1, 9, 10; 03 §2.1 (bố trí máy), §3.2 (dòng Ψ₀: batch toàn cục 128), §9.2 (mỗi checkpoint khoảng 5 GB); 05 KT4, RL3, PM3.
- Đây là lần đầu Châu làm fine-tune model lớn: làm cặp với Hiếu buổi đầu, sau đó tự chạy. Mục tiêu phụ là Châu thành người dự phòng cho việc train Ψ₀.
- Thuê GPU cần ngân sách do Hiếu hỏi BTC trong tuần 1. Chưa có ngân sách thì chỉ đo trên 5090 và ước tính phần A100.
- Ghi rõ nếu cấu hình khác (LoRA, đóng băng VLM) thì phải dùng chung cho mọi nhánh (spec 7.3).
- File sẽ tạo: `scripts/g0/finetune_probe.sh`, `docs/g0/psi0-finetune-cost.md`, `configs/runplans/draft-g0.yaml`, `docs/g0/ledger/S1-04.csv`.

## Kiểm thử

- Hiếu chạy lại `scripts/g0/finetune_probe.sh` với một cấu hình và ra số giây mỗi bước sai khác không quá 10%.
- Số GPU-giờ trong sổ khớp giờ tường của job (và hóa đơn nếu thuê).

## Người phụ trách

- Làm: Dương Đình Hiếu (tiếp tục trên nhánh `S1-04-finetune-cost`, giữ commit 1.2 của Châu)
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Trần Trịnh Hoàng Châu

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.4; giao Châu làm, Hiếu duyệt, theo 04 mục 3.2 | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Đồng bộ spec v10.1: checkpoint gốc trong `pre.*`, `postpre.*`; khối lượng 22 lần train Ψ₀ mặc định, tối đa 33. AC của 02 · 1.4 không đổi | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file. Dùng image Ψ₀ của S1-03 thay vì dựng chung; AC 6: đề xuất V8 (phần fine-tune) ghi trong file kết quả, Hiếu gom vào 03 §3.3; sổ chi phí riêng của story | PO (Hiếu) |
| 25/10/2026 | Thêm AC 7, 8 và nhiệm vụ con 6, 7: đo stage 2, 3 trên Colab và inference trên 3060; giữ nguyên số nhiệm vụ con cũ vì nhánh S1-04 đang mở; 12 → 18 giờ | PO (Hiếu) theo design 25/10/2026 |
| 25/10/2026 | Chuyển cho Hiếu vì cần phần cứng; nhánh đang mở giữ nguyên, nhiệm vụ con 1.2 vẫn tính cho Châu | PO (Hiếu) theo design chia làn |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
