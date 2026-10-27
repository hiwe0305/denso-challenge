# S1-03 · Tái tạo đánh giá Ψ₀, chọn checkpoint gốc, đo độ không tất định

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; thêm task hai bàn 27/10/2026) |
| Người làm | Hiếu |
| Story PRD | 1.3 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:rl` |
| Sprint | S1 (tuần 1–2) |
| Ước lượng | 28 giờ (bản 22/10: 20 giờ; thêm task hai bàn và chế độ `mujoco`) |
| Phụ thuộc | S1-02 cho phần chạy trong SIMPLE. Phần serve Ψ₀ và Q0 bắt đầu ngày 1 |

## Story

Là kỹ sư robot learning, tôi muốn chạy checkpoint Ψ₀ công bố trên một task SIMPLE đã công bố và biết checkpoint nào là gốc hợp lệ, để biết recipe có tái tạo được không trước khi tiêu GPU vào thí nghiệm.

## Tiêu chí chấp nhận

1. Chọn task công bố chạy cùng stack decoupled WBC với task chính (một task `*Teleop-v0`), ưu tiên `XMoveBendPickTeleop` (công bố 10/9/9, spec 2.3). Không dùng `BendPickMP` làm phép tái tạo chính vì task MP chạy AMO (03 §3.2). Nếu không có checkpoint phù hợp, dùng task khác và ghi lý do.
2. Serve Ψ₀, `GET /health` trả về bình thường; chạy client SIMPLE **30 lượt mỗi mức** Level 0, 1, 2 (02 · 1.3 AC 1, 06 mục 2). RunPlan của phép tái tạo có `purpose = g0_repro`.
3. Tiêu chí đạt thay cho "lệch không quá 1/10": ở mỗi mức, kiểm nhị thức một phía (α = 0,05) không cho thấy tỉ lệ thành công thấp hơn số công bố; ghi p-value từng mức (với số công bố 10/10, so với cận dưới Wilson 95% khoảng 72%, spec 9). Nếu thấp hơn có ý nghĩa, ghi nguyên nhân nghi ngờ và việc đã thử.
4. Ghi VRAM đỉnh khi suy luận, p99 độ trễ chu kỳ (nền cho τ_lat), và giao thức `act()`: HTTP hay WebSocket, khóa quan sát, chiều action, kích thước chunk, cổng thật (V2).
5. Chạy cùng 20 điều kiện hai lần; ghi tỉ lệ kết quả đổi chiều (NFR1, 03 §8.2).
6. Q0: liệt kê các thư mục trong `psi0/` của `USC-PSI-Lab/psi-model` ở một revision ghim; chọn checkpoint gốc cho E1 và mọi nhánh **trong nhóm `pre.*` hoặc `postpre.*`**, đã xác nhận không train trên dữ liệu SIMPLE hoặc sonic của task chính (hỏi PSI Lab). Ghi provenance và bằng chứng vào thực thể Source (`clean_for_main_task`: true, false hoặc unknown). Chưa có xác nhận thì chọn checkpoint ít post-train nhất (`pre.*`) và ghi giới hạn (spec 2.4 Q0, 05 TH12). Câu hỏi provenance được gửi cho PSI Lab cùng email giấy phép.
7. `simple-checkpoints` và `sonic-checkpoints` chỉ dùng cho phép tái tạo ở AC 2–3 (RunPlan `g0_repro`); không dùng cho E1 và các nhánh (06 mục 8, 03 §8.1).
8. Kết quả ghi ở `docs/g0/psi0-eval.md`, có mục "Đề xuất cho 03 §3.3" với dòng V2 và phần suy luận của V8 ([docs/g0/README.md](../../g0/README.md)); chi phí vào `docs/g0/ledger/S1-03.csv`. Hiếu gom vào 03 §3.3 ở review G0.
9. (27/10/2026, [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 3, 4.2) Tái tạo thêm trên task hai bàn `G1WholebodyLocomotionPickBetweenTablesTeleop-v0` bằng checkpoint `…locomotionpickbetweentablesteleop-v0` của tác giả: 30 lượt mỗi mức ở `mujoco_isaac`, so với số công bố 7/5/6 theo cùng kiểm nhị thức của AC 3. Đây là mốc so của thí nghiệm HE (DA-26).
10. (27/10/2026) Chạy cùng checkpoint ở `--sim-mode=mujoco`, 30 lượt Level 0: thành công có giữ như ở `mujoco_isaac` không (câu Q-27C của design). Kết luận quyết định renderer của HE.
11. (27/10/2026) Q0 mở rộng cho sáu checkpoint ablation của HE (`pre.abl.*`, `postpre.abl.*`, `pre.fast.1by1…`, `postpre.1by1…`): liệt kê, ghi revision, hỏi PSI Lab số bước và recipe của từng run (câu Q-27E).

## Nhiệm vụ

- [ ] 1. Q0 và chọn task tái tạo (AC 1, 6)
  - [ ] 1.1 Liệt kê checkpoint trong `psi0/` ở revision ghim; ghi tên, ngày, kích thước
  - [ ] 1.2 Chọn checkpoint gốc trong `pre.*` hoặc `postpre.*` và task tái tạo; ghi provenance vào Source; ghi rủi ro nếu chưa chắc (AC 6, 7)
  - [ ] 1.3 Soạn câu hỏi provenance, gửi chung email giấy phép (việc trưởng nhóm)
- [ ] 2. Serve Ψ₀ (AC 2, 4)
  - [ ] 2.1 Dựng môi trường Ψ₀ (Python 3.11, torch 2.7, flash-attn 2.7.4.post1) trong image riêng ở `docker/psi0/`, dùng chung với S1-04; ghi lỗi nếu flash-attn không chạy trên 5090
  - [ ] 2.2 `scripts/g0/serve_psi0.sh` với `--action-exec-horizon`, `--rtc` theo README Ψ₀
  - [ ] 2.3 Đo VRAM, độ trễ; ghi giao thức `act()`
- [ ] 3. Chạy đánh giá 3 mức × 30 lượt, kiểm nhị thức một phía từng mức (AC 2, 3), cùng Hưng
- [ ] 4. Đo độ không tất định trên 20 điều kiện (AC 5)
- [ ] 5. Viết `docs/g0/psi0-eval.md` kèm đề xuất cho 03 §3.3, ghi sổ chi phí (AC 8)
- [ ] 6. Tái tạo task hai bàn ở `mujoco_isaac`, 3 mức × 30 lượt (AC 9)
- [ ] 7. Chạy task hai bàn ở `mujoco`, so với AC 9 (AC 10)
- [ ] 8. Liệt kê checkpoint ablation, gửi câu hỏi cho PSI Lab (AC 11)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `docker/psi0/`: image Ψ₀ dùng chung với S1-04; Hưng review vì là chủ thư mục docker
- `scripts/g0/serve_psi0.sh`, `scripts/g0/eval_psi0.sh`
- `docs/g0/psi0-eval.md`
- `docs/g0/ledger/S1-03.csv`

## Ghi chú cho người làm

- Nguồn: 02 · 1.3 (bản 0.3); spec 2.1, 2.3, 2.4 (Q0), 7.3, 9; 03 §3.2 (dòng "Đánh giá client–server", "Ψ₀: cài đặt, train, serve"), §3.3 Q0, V2, V8, §4.3 (Source), §8.1, §8.2, §8.3; 05 TH12, TH14, RL1, SI3, SI4; 06 mục 2, 8.
- 30 lượt × 3 mức là 90 episode, khoảng 1,5–3 giờ máy với 60–120 giây mỗi episode; giờ người tăng ít.
- Ψ₀ và SIMPLE xung đột phiên bản Python; giữ hai môi trường tách nhau (ADR-02).
- Ví dụ client dùng cổng 21000 hoặc 9000 còn server nghe 22085 (03 V2): ghi cổng thật đã dùng.
- Tên đầy đủ của `XMoveBendPickTeleop` trong SIMPLE cần đối chiếu; không đoán.
- Trọng số không commit; để trong `fwdata/` hoặc cache Hugging Face.
- File sẽ tạo: `docker/psi0/Dockerfile`, `scripts/g0/serve_psi0.sh`, `scripts/g0/eval_psi0.sh`, `docs/g0/psi0-eval.md`, `docs/g0/ledger/S1-03.csv`.

## Kiểm thử

- `scripts/g0/eval_psi0.sh` chạy lại cho cùng cấu hình, ghi revision checkpoint và commit SIMPLE vào đầu ra.
- Châu chạy lại một mức từ tài liệu (để làm dự phòng Ψ₀).

## Người phụ trách

- Làm: Dương Đình Hiếu
- Hỗ trợ: Trần Ngọc Hưng (client SIMPLE, khoảng 2 giờ)
- Review: Trần Trịnh Hoàng Châu
- Dự phòng: Trần Trịnh Hoàng Châu

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.3, thêm Q0 và quy tắc chạy thêm 20 lượt khi lệch đúng biên | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Theo 02 · 1.3 bản 0.3 (06 mục 2, 8): 30 lượt mỗi mức, kiểm nhị thức một phía thay quy tắc 1/10 và chạy thêm 20 lượt; Q0 chọn trong `pre.*`, `postpre.*`, provenance vào Source; thêm AC 7 về `simple-checkpoints`, kết quả thành AC 8; sửa mã trích 05 TN thành TH; ước lượng 18 → 20 giờ | SM (Bob) theo 06 |
| 27/10/2026 | Thêm AC 9–11 và nhiệm vụ con 6–8: tái tạo task hai bàn (mốc của HE), so `mujoco` với `mujoco_isaac`, Q0 cho checkpoint ablation; giữ số nhiệm vụ con cũ vì nhánh S1-03 đang mở; 20 → 28 giờ | PO (Hiếu) theo design 27/10/2026 |
| 24/10/2026 | Thêm mục Phạm vi file. AC 8: đề xuất dòng V2, V8 (phần suy luận) ghi trong file kết quả, Hiếu gom vào 03 §3.3 ở review G0; sổ chi phí riêng của story. Nhiệm vụ con 2.1 giữ image Ψ₀ ở `docker/psi0/` cho cả S1-04 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
