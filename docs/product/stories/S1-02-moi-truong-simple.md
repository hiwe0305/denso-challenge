# S1-02 · Môi trường SIMPLE ghim phiên bản

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026; sửa 25/10/2026; mở rộng lại 27/10/2026) |
| Người làm | Hiếu |
| Story PRD | 1.2 · Epic 1 |
| Nhãn | [Adapter] · `epic:1` · `gate:G0` · `area:sim` |
| Sprint | S1, tuần 1 |
| Ước lượng | 14 giờ (bản 25/10: 8 giờ; bản đầu: 16 giờ) |
| Phụ thuộc | Không. Chặn S1-03, S1-05, S1-06, S1-09, S1-11, DA-16, DA-17 |

## Story

Là kỹ sư simulation, tôi muốn dựng SIMPLE bằng một lệnh với phiên bản ghim, chạy được cả chế độ MuJoCo thuần và chế độ render Isaac Sim, để mọi người thu dữ liệu, sinh dữ liệu và eval task hai bàn trên cùng một môi trường.

## Tiêu chí chấp nhận

_Mở rộng lại ngày 27/10/2026 theo [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 4: SIMPLE là simulator chính của demo; task chính là `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`._

1. Một lệnh dựng SIMPLE từ image ghim theo digest (03 §3.1) hoặc bằng uv; `docs/g0/env-simple.md` ghi commit SIMPLE, digest image, phiên bản Isaac Sim, MuJoCo, driver NVIDIA, CUDA, hệ điều hành.
2. Chạy headless một episode của task hai bàn ở `--sim-mode=mujoco` và một episode ở `--sim-mode=mujoco_isaac` (phát lại một demo của psi-data hoặc action rỗng); lưu video MP4 ra ngoài git.
3. Gọi được ba entry point mà các story sau dùng: `teleop_decoupled_wbc` (chạy tới bước chờ thiết bị, không cần PICO), `datagen` trên một task MP có sẵn (ví dụ `G1WholebodyBendPickMP-v0`, 1 episode), Replay & Render một episode đã ghi bằng MuJoCo sang ảnh Isaac.
4. Đo thời gian mỗi episode (trung bình và p95 trên ít nhất 5 episode) và VRAM đỉnh ở cả hai chế độ, trên máy RTX 3060 12 GB và trên máy có Isaac Sim nếu khác máy.
5. Ghi các mục chi phí vào `docs/g0/ledger/S1-02.csv`, cột theo [docs/g0/README.md](../../g0/README.md).

## Nhiệm vụ

- [ ] 1. Dựng môi trường (AC 1)
  - [ ] 1.1 Lấy digest image `ghcr.io/physical-superintelligence-lab/simple`; viết service `simple-worker` trong `compose.yaml`, chạy người dùng không phải root
  - [ ] 1.2 Nếu Docker gặp vấn đề GPU, thử uv hoặc Nix theo README SIMPLE; ghi lý do chọn
  - [ ] 1.3 Viết `scripts/g0/setup_simple.sh` và ghi phiên bản vào `docs/g0/env-simple.md`
- [ ] 2. Chạy một episode task hai bàn ở hai chế độ và lưu video (AC 2)
- [ ] 3. Gọi `teleop_decoupled_wbc`, `datagen`, Replay & Render (AC 3)
- [ ] 4. Đo thời gian và VRAM ở hai chế độ (AC 4)
- [ ] 5. Ghi chi phí vào `docs/g0/ledger/S1-02.csv` (AC 5)
- [ ] 6. Báo các story bị chặn khi môi trường sẵn sàng

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `compose.yaml`: service simple-worker
- `docker/simple/`
- `scripts/g0/setup_simple.sh`, `scripts/g0/run_one_episode.sh`
- `docs/g0/env-simple.md`
- `docs/g0/ledger/S1-02.csv`

## Ghi chú cho người làm

- Nguồn: 02 · 1.2; 03 §3.1 (Docker, ghim digest), §3.2 (dòng "Nền simulator", "Đánh giá client–server", "Đầu ra đánh giá"), §10.3 (container không chạy root, bí mật qua `.env`); spec 2.2, 2.5, 9 (G0); design 27/10 mục 4.
- Lệnh teleop theo tài liệu SIMPLE: `python -m simple.cli.teleop_decoupled_wbc simple/$TASK --sim-mode=mujoco --record --no-headless`, cần `MUJOCO_GL=egl`. Lệnh sinh tự động: `uv run datagen simple/<Task>MP-v0 --num-episodes=N`.
- Theo README Ψ₀, eval ở `mujoco_isaac` mất 6–10 phút mỗi episode vì Isaac Sim render đồng bộ. Số đo ở AC 4 là đầu vào cho S1-04 và cho lịch eval của HE (DA-26).
- Tập đánh giá có sẵn nằm trong `psi-data/simple-eval/`; client SIMPLE nhận `--data-format lerobot --data-dir data/evals/simple-eval/<task>/<level> --headless`.
- Token Hugging Face chỉ để trong `.env`, không ghi vào script hay log.
- Video, dữ liệu tải về để trong `fwdata/` (đã gitignore ở S1-01) hoặc thư mục ngoài repo.
- Nếu baseline ACT của SIMPLE chạy được trong tuần 2, ghi thêm số worker W khi policy là ACT (03 §3.3 V8, V10); nếu chưa, ghi "chưa đo".

## Kiểm thử

- Chạy lại `scripts/g0/setup_simple.sh` trên máy sạch hoặc container mới cho cùng phiên bản đã ghi.
- `scripts/g0/run_one_episode.sh` trả mã 0 và tạo file MP4 không rỗng ở cả hai chế độ.
- Một người khác chạy lại một episode từ tài liệu mà không cần hỏi.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.2 | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Thêm S1-11 vào danh sách chặn; ghi chú đo W khi policy là ACT cho 05 MO2. AC không đổi | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file. Sổ chi phí G0 tách theo story: AC 5 ghi vào `docs/g0/ledger/S1-02.csv` thay vì tạo `ledger-g0.csv` chung | PO (Hiếu) |
| 25/10/2026 | Thu nhỏ: SIMPLE chỉ cho G0; bỏ thử trên 3060 và bỏ chặn S1-05, S1-06, S1-09, S1-11; 16 → 8 giờ | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 25/10/2026 | Chuyển cho Hiếu vì chỉ Hiếu có phần cứng; image theo `docker/simple/` và `compose.yaml` gốc | PO (Hiếu) theo design chia làn (đã xóa) |
| 27/10/2026 | Mở rộng lại: SIMPLE là simulator chính; task hai bàn; hai chế độ `mujoco` và `mujoco_isaac`; gọi được teleop, datagen, Replay & Render; đo trên 3060; chặn lại S1-05, S1-06, S1-09, S1-11, DA-16, DA-17; 8 → 14 giờ | PO (Hiếu) theo design 27/10/2026 |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
