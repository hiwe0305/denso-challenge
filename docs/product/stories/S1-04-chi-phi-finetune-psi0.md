# S1-04 · Đo chi phí fine-tune Ψ₀ (Q5)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026) |
| Người làm | Châu |
| Story PRD | 1.4 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:rl` |
| Sprint | S1 (tuần 1–2), bắt đầu ngày 1 |
| Ước lượng | 12 giờ |
| Phụ thuộc | Không (dùng chung môi trường Ψ₀ với S1-03). Cần ngân sách thuê GPU nếu 5090 không đủ |

## Story

Là kỹ sư robot learning, tôi muốn đo VRAM và GPU-giờ của fine-tune Ψ₀ trên dữ liệu task chính, để chốt phần cứng, cấu hình và số seed trước khi lập kế hoạch thí nghiệm.

## Tiêu chí chấp nhận

1. Chạy fine-tune ngắn (vài trăm bước) bằng script công bố của Ψ₀ trên gói task chính, từ checkpoint gốc chọn ở S1-03 (Q0, nhóm `pre.*` hoặc `postpre.*`; không dùng `simple-checkpoints`, `sonic-checkpoints`). Thứ tự thử: RTX 5090 toàn phần; nếu hết bộ nhớ thì LoRA hoặc đóng băng VLM (nếu script hỗ trợ, nếu không thì ghi lại); rồi A100 80 GB thuê.
2. Với mỗi cấu hình đã thử: VRAM đỉnh, giây mỗi bước, batch toàn cục, có hết bộ nhớ không.
3. Ước tính GPU-giờ cho S bước (S theo cấu hình công bố, spec 7.3) và cho khối lượng spec 9 bản v10.1 (khoảng 22 lần train Ψ₀ mặc định, tối đa khoảng 33 nếu thêm seed theo luật MDE hoặc mở B-fail trên Ψ₀); quy ra USD theo đơn giá A100 $1,59/giờ (giả định, spec 8.1). Ghi vào `docs/g0/ledger-g0.csv`, tách `estimated` và `measured`.
4. Đề xuất cấu hình (toàn phần, LoRA, đóng băng VLM), phần cứng, số seed; Hiếu duyệt. Ghi vào `configs/runplans/draft-g0.yaml`.
5. Không commit trọng số; xóa trạng thái optimizer sau khi đo và ghi chú vào sổ (03 §9.2).
6. Kết quả ở `docs/g0/psi0-finetune-cost.md`; cập nhật V8 ở 03 §3.3 có change log.

## Nhiệm vụ

- [ ] 1. Chuẩn bị (AC 1)
  - [ ] 1.1 Dùng môi trường Ψ₀ của S1-03; tải gói task chính ở revision ghim
  - [ ] 1.2 Đọc `scripts/train/psi0/finetune-simple-psi0.sh`, ghi S, batch, learning rate mặc định
- [ ] 2. Chạy thử theo thứ tự 5090 → LoRA hoặc đóng băng VLM → A100 (AC 1, 2)
- [ ] 3. Tính GPU-giờ và USD, ghi sổ (AC 3)
- [ ] 4. Viết đề xuất, Hiếu duyệt, tạo RunPlan nháp (AC 4)
- [ ] 5. Dọn trọng số, optimizer; viết tài liệu, cập nhật 03 (AC 5, 6)

## Ghi chú cho người làm

- Nguồn: 02 · 1.4; spec 2.1, 2.4 (Q0), 7.3, 7.5 (luật MDE), 8.1, 9, 10; 03 §2.1 (bố trí máy), §3.2 (dòng Ψ₀: batch toàn cục 128), §9.2 (mỗi checkpoint khoảng 5 GB); 05 KT4, RL3, PM3.
- Đây là lần đầu Châu làm fine-tune model lớn: làm cặp với Hiếu buổi đầu, sau đó tự chạy. Mục tiêu phụ là Châu thành người dự phòng cho việc train Ψ₀.
- Thuê GPU cần ngân sách do Hiếu hỏi BTC trong tuần 1. Chưa có ngân sách thì chỉ đo trên 5090 và ước tính phần A100.
- Ghi rõ nếu cấu hình khác (LoRA, đóng băng VLM) thì phải dùng chung cho mọi nhánh (spec 7.3).
- File sẽ tạo: `scripts/g0/finetune_probe.sh`, `docs/g0/psi0-finetune-cost.md`, `configs/runplans/draft-g0.yaml`.

## Kiểm thử

- Hiếu chạy lại `scripts/g0/finetune_probe.sh` với một cấu hình và ra số giây mỗi bước sai khác không quá 10%.
- Số GPU-giờ trong sổ khớp giờ tường của job (và hóa đơn nếu thuê).

## Người phụ trách

- Làm: Trần Trịnh Hoàng Châu
- Chịu trách nhiệm cuối và review: Dương Đình Hiếu
- Dự phòng: Dương Đình Hiếu

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.4; giao Châu làm, Hiếu duyệt, theo 04 mục 3.2 | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Đồng bộ spec v10.1: checkpoint gốc trong `pre.*`, `postpre.*`; khối lượng 22 lần train Ψ₀ mặc định, tối đa 33. AC của 02 · 1.4 không đổi | SM (Bob) theo 06 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
