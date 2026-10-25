# S1-02 · Môi trường SIMPLE ghim phiên bản

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; sửa 25/10/2026) |
| Người làm | Hưng |
| Story PRD | 1.2 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` |
| Sprint | S1, tuần 1 |
| Ước lượng | 8 giờ (bản trước: 16 giờ) |
| Phụ thuộc | Không. Chặn S1-03. Không còn chặn S1-05, S1-06, S1-09, S1-11 (25/10/2026) |

## Story

Là kỹ sư simulation, tôi muốn dựng SIMPLE trên Isaac Sim 4.5 bằng một lệnh với phiên bản ghim, để mọi máy và mọi người chạy cùng một môi trường và số liệu G0 tái lập được.

## Tiêu chí chấp nhận

_Thu nhỏ ngày 25/10/2026 ([design 25/10/2026](../../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.1): SIMPLE chỉ còn là benchmark G0, nên môi trường chỉ cần đủ cho S1-03 tái tạo số công bố._

1. Một lệnh dựng SIMPLE từ image ghim theo digest (03 §3.1) hoặc bằng uv; `docs/g0/env-simple.md` ghi commit SIMPLE, digest image, phiên bản Isaac Sim, MuJoCo, driver NVIDIA, CUDA, hệ điều hành.
2. Chạy headless được một episode của task mà S1-03 dùng để tái tạo (phát lại một demo hoặc action rỗng) và lưu video MP4 ra ngoài git.
3. Đo thời gian mỗi episode (trung bình và p95 trên ít nhất 5 episode) và VRAM đỉnh trên máy S1-03 chạy. Máy 5090 chờ xác nhận (design 25/10 câu Q-C); nếu không có, ghi máy thay thế.
4. Ghi các mục chi phí vào `docs/g0/ledger/S1-02.csv`, cột theo [docs/g0/README.md](../../g0/README.md).

## Nhiệm vụ

- [ ] 1. Dựng môi trường (AC 1)
  - [ ] 1.1 Lấy digest image `ghcr.io/physical-superintelligence-lab/simple`; viết service `simple-worker` trong `docker/compose.yaml`, chạy người dùng không phải root
  - [ ] 1.2 Nếu Docker gặp vấn đề GPU, thử uv hoặc Nix theo README SIMPLE; ghi lý do chọn
  - [ ] 1.3 Viết `scripts/g0/setup_simple.sh` và ghi phiên bản vào `docs/g0/env-simple.md`
- [ ] 2. Chạy một episode và lưu video (AC 2)
- [ ] 3. Đo thời gian và VRAM (AC 3)
- [ ] 4. Ghi chi phí vào `docs/g0/ledger/S1-02.csv` (AC 4)
- [ ] 5. Báo Hiếu khi môi trường sẵn sàng cho S1-03

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `docker/compose.yaml`: service simple-worker
- `scripts/g0/setup_simple.sh`, `scripts/g0/run_one_episode.sh`
- `docs/g0/env-simple.md`
- `docs/g0/ledger/S1-02.csv`

## Ghi chú cho người làm

- Nguồn: 02 · 1.2; 03 §3.1 (Docker, ghim digest), §3.2 (dòng "Nền simulator", "Đánh giá client–server", "Đầu ra đánh giá"), §10.3 (container không chạy root, bí mật qua `.env`); spec 2.2, 9 (G0).
- Tập đánh giá có sẵn của task chính nằm trong `psi-data/simple-eval/` (khoảng 378 KB); client SIMPLE nhận `--data-format lerobot --data-dir data/evals/simple-eval/<task>/<level> --headless`.
- Token Hugging Face chỉ để trong `.env`, không ghi vào script hay log.
- Video, dữ liệu tải về để trong `fwdata/` (đã gitignore ở S1-01) hoặc thư mục ngoài repo.
- Số đo ở AC 3 là đầu vào cho câu hỏi mở 05 MO2 (thông lượng F-ACT, khoảng 630–850 rollout mỗi vòng). Nếu baseline ACT của SIMPLE chạy được trong tuần 2, ghi thêm số worker W khi policy là ACT (03 §3.3 V8, V10); nếu chưa, ghi "chưa đo" để 4.1 đo ở S2.
- Cột của sổ chi phí G0 và quy ước `branch`, `person` ở [docs/g0/README.md](../../g0/README.md).
- File sẽ tạo: `docker/compose.yaml`, `scripts/g0/setup_simple.sh`, `scripts/g0/run_one_episode.sh`, `docs/g0/env-simple.md`, `docs/g0/ledger/S1-02.csv`.

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
| 24/10/2026 | Thêm mục Phạm vi file. Sổ chi phí G0 tách theo story: AC 5 ghi vào `docs/g0/ledger/S1-02.csv` thay vì tạo `ledger-g0.csv` chung | PO (Hiếu) |
| 25/10/2026 | Thu nhỏ: SIMPLE chỉ cho G0; bỏ thử trên 3060 và bỏ chặn S1-05, S1-06, S1-09, S1-11; 16 → 8 giờ | PO (Hiếu) theo design 25/10/2026 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
