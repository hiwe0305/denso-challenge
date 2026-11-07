# DA-18 · Egocentric sang dữ liệu stage 1 của Ψ₀

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 25/10/2026; xóa và khôi phục với nội dung mới 27/10/2026) |
| Người làm | Hiếu, làm cùng Claude (từ 6/11/2026, thay Hưng; 07 bản 1.9) |
| Làn | Dữ liệu |
| Story PRD | 9.25 · Epic 9 · [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 6.6, 7.8 |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:rl` |
| Sprint | S2; bản export EgoDex đọc được bằng loader trước 10/11/2026 để DA-30 chạy kịp demo · **Lịch 3/11/2026:** merge trước **8/11/2026** (thay 10/11) để DA-30 chạy |
| Ước lượng | 8 giờ (khoảng 6–10, ước lượng; phần stage 1 tách sang DA-30) |
| Phụ thuộc | DA-04 (đoạn egocentric đã qua QA). Trong lúc chờ: code export trên đoạn EgoDex mẫu của testkit. Chặn DA-30 |

## Story

Là kỹ sư dữ liệu, tôi muốn dữ liệu egocentric do pipeline của đội xử lý được xuất đúng định dạng stage 1 của Ψ₀, để DA-30 chạy được stage 1 trên đó mà không phải sửa dữ liệu.

## Tiêu chí chấp nhận

1. Export đoạn egocentric đã qua QA sang đúng định dạng mà `src/psi/data/egodex/egodex_dataset.py` của Ψ₀ đọc (biến đổi khớp tay cộng mp4; `chunk_size`, `upsample_rate`, delta action như config gốc; action 48 chiều theo tiền xử lý H-RDT), kèm stats theo `calc_egodex_stats.py`.
2. Contract test: loader stage 1 của Ψ₀ ở commit đã ghim đọc bản export ra đúng một batch mẫu đã lưu.
3. Xuất được cả hai nguồn: mẫu EgoDex (E-B) và video tự quay (E-A, `pseudo`), cùng định dạng; `meta` ghi nguồn và độ tin pose.

## Nhiệm vụ

- [x] 1. Export định dạng stage 1 và stats (AC 1)
- [x] 2. Contract test bằng loader của Ψ₀ (AC 2)
- [x] 3. Export cho video tự quay (AC 3)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-data/src/flywheel/data/export/egodex.py`, `packages/flywheel-data/tests/contract/export_egodex/`
- `docs/g0/ledger/DA-18.csv`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 5.0, 6.6, 7.8, 8.1, 8.3; spec mục 7.9; 03 mục 5.4.
- Trưởng nhóm chốt ngày 27/10/2026: chứng minh hệ thống trên dữ liệu công bố trước; còn thời gian thì dùng dữ liệu egocentric đội thu.
- Ψ₀ đã pretrain stage 1 trên EgoDex, nên fine-tune lại trên EgoDex không cho thông tin mới; vì vậy AC 3 chỉ là lần chạy ngắn.
- Story này chỉ import nhân; không import `flywheel-psi0`. Contract test đọc lại bằng loader của Ψ₀ chạy trong job có marker riêng; trong CI dùng loader giả cùng schema. Phần chạy stage 1 là DA-30 (Hiếu), nối qua `DatasetRef`.
- Trọng số không commit.

## Kiểm thử

- Contract test ở AC 2 chạy trong CI trên đoạn mẫu của testkit (không cần GPU).

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude (từ 6/11/2026; trước đó Trần Ngọc Hưng)
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/10/2026 | Tạo story: video egocentric thô của nhà máy DENSO thành dữ liệu fine-tune stage 1 | PO (Hiếu) theo design 25/10/2026 (đã xóa) |
| 27/10/2026 | Xóa cùng robot DENSO, rồi khôi phục cùng ngày với nội dung mới: nguồn là mẫu EgoDex và video đội tự quay; lần chạy ngắn trên EgoDex chứng minh đường đi; fine-tune thật chỉ trên video tự quay | PO (Hiếu) theo design 27/10/2026 |
| 27/10/2026 | Tách phần chạy stage 1 sang DA-30; giao cho Hưng theo 07 mục 2.0 (bản 0.6) | PO (Hiếu) |
| 3/11/2026 | Hạn mới theo lịch hoàn thiện 13/11/2026 (07 mục 2.4) | PO (Hiếu) |
| 6/11/2026 | Chuyển sang Hiếu làm cùng Claude theo [plan chia lại việc của Hưng](../../superpowers/plans/2026-11-06-hung-reassignment.md); bỏ bước che danh tính chỉ cho mẫu EgoDex công bố (D2); làm đủ mọi nhiệm vụ con (D3) | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực: 6,55 giờ (nhiệm vụ 1: 1,5 + 0,5 sửa sau khi chạy work dir thật của DA-04 + 0,5 sửa theo review PR #153; 2: 1,5 + 0,3 chạy loader thật trên laptop; 3: 1,5 + 0,75 sửa theo review), Hiếu làm cùng Claude từ 6/11/2026 (plan chia lại việc của Hưng).
- Công cụ AI đã dùng: Claude Code (Claude Opus 5.5).
- Ghi chú hoàn thành:
  - Đầu vào là work dir của DA-04 theo plan 6/11/2026 mục 4.2a; test dùng work dir tổng hợp theo đúng mục đó. DA-04 cần ghi thêm `intrinsic` (3, 3) vào `pose.npz` cho E-A **[Đề xuất]**: loader của Ψ₀ đọc `camera/intrinsic` ở mọi mẫu, còn episode E-A không có HDF5.
  - `actions_48d` khớp đúng từng số với bản do script H-RDT của tác giả tính trên 20 episode EgoDex; stats lệch tối đa 9e-8 so với `calc_stat.py` của tác giả.
  - Loader của Ψ₀ ở `cda3fdf` (image của tác giả trên `rtx3060`) đọc lại đúng batch đã lưu, cả 40 mẫu EgoDex thật và mẫu E-A.
  - Phát hiện: với `img_history_size` 1 và `upsample_rate` 3, `parse_img_data` của Ψ₀ lấy khung `index - 2` (không nhỏ hơn 0) chứ không phải khung `index`. Đây là hành vi của tác giả; bản export giữ video và HDF5 khớp từng khung.
  - Chạy trên work dir thật của DA-04 (`fwdata/pipeline/src_050b9bf56a4e843c`, 20 episode EgoDex, QA 13 pass, 7 flag) với `--include-flag`, trên laptop: 38 mẫu (25 pass, 13 flag), 4143 khung, 79 MB, 53 giây đo, ước tính 84 giây. Loader giả đọc đủ 38 mẫu, action chuẩn hóa hữu hạn.
  - 4 episode trong đó (8 mẫu) không có nhóm `confidences` trong file EgoDex, nên DA-04 ghi NaN. `meta` ghi `pose_confidence` với `mean`/`min` là `null` và `recorded` 0, không lấy trung bình NaN. Action có NaN hoặc Inf thì export từ chối và xóa thư mục đầu ra (thư mục đã được kiểm là mới hoặc rỗng), để lần chạy lại không bị chặn vì "không rỗng".
  - Sửa theo review PR #153 (7/11/2026):
    - Split `dev` của DA-04 vào thư mục `test/` của Ψ₀.
    - Từ chối fps khác 30 (trong `bundle.json` hoặc trong mp4), vì `upsample_rate` 3 giả định 30 Hz; 29,97 vẫn qua; resample để sau.
    - Từ chối trộn E-A với E-B trong một lượt export.
    - Đoạn có khung không hữu hạn (tay hoặc camera) bị bỏ nguyên đoạn và liệt kê trong `meta.json`; chỉ từ chối cả lượt khi không còn đoạn nào.
  - E-A thật (pose `pose_ea.npz` của DA-04 trên 20 episode EgoDex, tức `to_pose` của `fwdata/egocentric-ea/src_050b9bf56a4e843c-v2`), với `--include-flag`: **giữ 2 trên 38 đoạn** (109 trên 4143 khung). 36 đoạn bị bỏ vì tay không thấy ở ít nhất một khung. Với luật bỏ nguyên đoạn, E-A trên video EgoDex gần như không cho mẫu nào; cần PO xem lại luật hoặc đợi video đội tự quay.
  - Chưa xong ngoài phạm vi: `build_release` (DA-03) vẫn đóng băng release toàn egocentric với `kind` robot; test `xfail` strict ghi lại, đề xuất PR riêng cho DA-03.
- File đã tạo hoặc sửa: `packages/flywheel-data/src/flywheel/data/export/egodex.py`, `packages/flywheel-data/tests/contract/export_egodex/`, `docs/g0/ledger/DA-18.csv`.

### Chạy ở đâu, và lệnh để Hiếu chạy lại trên laptop

Quy tắc mới (Hiếu, 6/11/2026): chạy trên laptop nếu được; không được thì để lại lệnh.

| Việc | Chạy ở | Kết quả |
|---|---|---|
| Export, test CI (fake loader, batch đã lưu) | Laptop | 38 qua, 2 `xfail` strict |
| Export work dir thật của DA-04, đọc lại bằng loader giả | Laptop | 38 mẫu, 53 giây, đọc đủ |
| Export E-A thật (cùng 20 episode, pose của E-A) | Laptop | Giữ 2, bỏ 36 đoạn, 1,6 giây; loader giả đọc đủ 2 mẫu |
| So `actions_48d` với bản của tác giả, so stats với `calc_stat.py` (môi trường Ψ₀ `fwdata/psi0/Psi0/.venv-psi`) | Laptop | Khớp (lệch 0 và 9e-8) |
| Loader thật của Ψ₀ (`-k psi0`) | `rtx3060`, image Ψ₀ của tác giả, **trước khi có quy tắc mới** | 4 qua, rồi 2 qua (mục trên) |

Loader thật **không chạy được trên laptop** ngày 6/11/2026: torchcodec 0.4 của môi trường Ψ₀ cần thư viện chia sẻ FFmpeg 4–7, có cả `libavdevice` và `libavfilter`. Laptop chỉ có FFmpeg 8 (`libavutil.so.60`) và bản FFmpeg 6 trong snap thiếu hai thư viện đó. RAM trống lúc đó khoảng 1 GB.

Để chạy lại trên laptop:

1. Cài FFmpeg 7 dạng thư viện chia sẻ vào thư mục riêng, không đụng hệ thống. Ví dụ **[Đề xuất, chưa thử]**: `~/anaconda3/bin/conda create -y -p ~/ffmpeg7 -c conda-forge "ffmpeg=7.*"`. Kiểm tra: `ls ~/ffmpeg7/lib/libavdevice.so.61 ~/ffmpeg7/lib/libavutil.so.59`.
2. Kiểm `free -g`: cần khoảng 3 GB trống (torch nạp trên CPU).
3. Chọn vài episode: `mkdir -p /tmp/egodex4 && ln -s /home/hiwe/project/denso-challenge/fwdata/egodex-da30-probe/part1/{add_remove_lid,arrange_topple_dominoes} /tmp/egodex4/`.
4. Từ worktree của nhánh `DA-18-egodex-export`:

   ```bash
   PSI0_ROOT=/home/hiwe/project/denso-challenge/fwdata/psi0/Psi0 PSI0_FFMPEG_LIB=$HOME/ffmpeg7/lib EGODEX_PROBE=/tmp/egodex4 uv run pytest -v packages/flywheel-data/tests/contract/export_egodex -k psi0
   ```

   Kết quả mong đợi: `3 passed` (batch đã lưu, EgoDex thật với 8 mẫu từ 4 episode, E-A). `PSI0_FFMPEG_LIB` chỉ đặt `LD_LIBRARY_PATH` cho tiến trình Ψ₀. Lỗi `Could not load libtorchcodec` nghĩa là bước 1 chưa đúng; lỗi so sánh in đường dẫn mẫu, khóa và độ lệch lớn nhất.
