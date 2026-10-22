# S1-02 · Môi trường SIMPLE ghim phiên bản

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026) |
| Người làm | Hưng |
| Story PRD | 1.2 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` |
| Sprint | S1, xong trong tuần 1 |
| Ước lượng | 16 giờ |
| Phụ thuộc | Không. Chặn S1-03, S1-05, S1-06, S1-09 và phần thử T1, T2 của S1-11 |

## Story

Là kỹ sư simulation, tôi muốn dựng SIMPLE trên Isaac Sim 4.5 bằng một lệnh với phiên bản ghim, để mọi máy và mọi người chạy cùng một môi trường và số liệu G0 tái lập được.

## Tiêu chí chấp nhận

1. Một lệnh dựng SIMPLE từ image ghim theo digest (03 §3.1) hoặc bằng uv; `docs/g0/env-simple.md` ghi commit SIMPLE, digest image, phiên bản Isaac Sim, MuJoCo, driver NVIDIA, CUDA, hệ điều hành.
2. Chạy headless được một episode của `G1WholebodyBendPickAndPlaceTeleop-v0` (phát lại một demo hoặc action rỗng) và lưu video MP4 ra ngoài git.
3. Đo thời gian mỗi episode đánh giá trên RTX 5090 (trung bình và p95 trên ít nhất 5 episode) và VRAM đỉnh của simulator. Đây là đầu vào cho V8 và số worker W.
4. Thử trên RTX 3060 12 GB trong ngày 1–3 và ghi kết quả: chạy được, chạy được nhưng chậm, hay không chạy (05 SI3, KT4).
5. Tạo `docs/g0/ledger-g0.csv` với cột theo LedgerEntry (03 §4.3) và ghi các mục chi phí của story này.

## Nhiệm vụ

- [ ] 1. Dựng môi trường (AC 1)
  - [ ] 1.1 Lấy digest image `ghcr.io/physical-superintelligence-lab/simple`; viết service `simple-worker` trong `docker/compose.yaml`, chạy người dùng không phải root
  - [ ] 1.2 Nếu Docker gặp vấn đề GPU, thử uv hoặc Nix theo README SIMPLE; ghi lý do chọn
  - [ ] 1.3 Viết `scripts/g0/setup_simple.sh` và ghi phiên bản vào `docs/g0/env-simple.md`
- [ ] 2. Chạy một episode và lưu video (AC 2)
- [ ] 3. Đo thời gian và VRAM (AC 3, 4)
  - [ ] 3.1 Trên 5090
  - [ ] 3.2 Trên 3060
- [ ] 4. Tạo `docs/g0/ledger-g0.csv` và ghi chi phí (AC 5)
- [ ] 5. Báo nhóm trong check-in khi môi trường sẵn sàng để S1-03, S1-05, S1-06, S1-09, S1-11 bắt đầu

## Ghi chú cho người làm

- Nguồn: 02 · 1.2; 03 §3.1 (Docker, ghim digest), §3.2 (dòng "Nền simulator", "Đánh giá client–server", "Đầu ra đánh giá"), §10.3 (container không chạy root, bí mật qua `.env`); spec 2.2, 9 (G0).
- Tập đánh giá có sẵn của task chính nằm trong `psi-data/simple-eval/` (khoảng 378 KB); client SIMPLE nhận `--data-format lerobot --data-dir data/evals/simple-eval/<task>/<level> --headless`.
- Token Hugging Face chỉ để trong `.env`, không ghi vào script hay log.
- Video, dữ liệu tải về để trong `fwdata/` (đã gitignore ở S1-01) hoặc thư mục ngoài repo.
- Số đo ở AC 3 là đầu vào cho câu hỏi mở 05 MO2 (thông lượng F-ACT, khoảng 630–850 rollout mỗi vòng). Nếu baseline ACT của SIMPLE chạy được trong tuần 2, ghi thêm số worker W khi policy là ACT (03 §3.3 V8, V10); nếu chưa, ghi "chưa đo" để 4.1 đo ở S2.
- Cột gợi ý cho `ledger-g0.csv`: `date, activity, resource_type, quantity, unit, unit_price_usd, amount_usd, estimated_or_measured, branch, round, job, person, note`. `branch` ghi `g0`; `person` dùng mã giả danh (03 §10.3).
- File sẽ tạo: `docker/compose.yaml`, `scripts/g0/setup_simple.sh`, `scripts/g0/run_one_episode.sh`, `docs/g0/env-simple.md`, `docs/g0/ledger-g0.csv`.

## Kiểm thử

- Chạy lại `scripts/g0/setup_simple.sh` trên máy sạch hoặc container mới cho cùng phiên bản đã ghi.
- `scripts/g0/run_one_episode.sh` trả mã 0 và tạo file MP4 không rỗng.
- Người review (Châu) chạy lại một episode từ tài liệu mà không cần hỏi.

## Người phụ trách

- Làm: Trần Ngọc Hưng
- Review: Trần Trịnh Hoàng Châu; Nguyễn Thăng Long xem phần compose
- Dự phòng: Trần Trịnh Hoàng Châu

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.2 | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Thêm S1-11 vào danh sách chặn; ghi chú đo W khi policy là ACT cho 05 MO2. AC không đổi | SM (Bob) theo 06 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
