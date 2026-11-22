# DA-45 · Catalog của Console đọc từ thẻ dataset

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (Hiếu mở ngày 22/11/2026) |
| Người làm | Hiếu |
| Làn | Ngoài ba làn: công cụ của đội (`flywheel.console`), không import làn hay adapter |
| Nguồn yêu cầu | Quyết định tổ chức dataset của Hiếu ngày 22/11/2026: mỗi lô là một kho tự chứa `fwdata/datasets/<store>/`, mỗi release có thẻ `cards/<release_id>.yaml` (schema `dataset-card/1`) |
| Nhãn | `area:console` |
| Sprint | Sau demo 17/11/2026 |
| Ước lượng | 4 giờ (ước lượng) |
| Phụ thuộc | Không chặn ai. Đọc thẻ trong `fwdata/datasets/` (ngoài git); không sửa gì dưới `fwdata/` |

## Story

Là người dùng Flywheel Console, tôi muốn danh mục dataset lấy từ thẻ dataset nằm cạnh dữ liệu, để release mới hiện lên đúng trạng thái, vị trí và lớp dữ liệu mà không ai phải sửa tay `seed/catalog.yaml`.

Hiện trạng ngày 22/11/2026: seed viết tay ngày 11/11/2026 thiếu hai release `tray_s1_bfbdcbcf719e` và `tray_s1_8631ace9b1b3`, ghi release cảnh cũ là `current`, ghi `s2-release-669` là `missing` dù `tray_s2_3618a579b15e` có trên laptop, sai vị trí của `tray_s1_868cc130985d`, và trỏ tới các thư mục `rtx3060:~/denso-*` đã xóa ngày 15/11/2026. Console còn gán cứng `data_class: public`, `license: unknown` cho dataset đưa vào bộ chạy việc.

## Tiêu chí chấp nhận

1. Bộ đọc thẻ đọc `$FW_ROOT/datasets/*/cards/*.yaml` và `$FW_ROOT/datasets/_cards/*.yaml`, kiểm schema `dataset-card/1` (trường bắt buộc, giá trị cho phép của `status`, `kind`, `data_class`, `id` trùng tên file, không trùng `id`). Thẻ sai làm `fw console index` dừng, thông báo nêu file và trường.
2. Thẻ thắng dòng seed cùng `id` theo bảng ánh xạ ở mục "Ghi chú cho người làm" (Hiếu duyệt 22/11/2026). Seed chỉ giữ thứ thẻ không có: `title`, `size`, gợi ý trình xem. Dòng seed không có thẻ (egocentric, pipeline, bộ điều kiện eval, bench, cut cũ, run) giữ nguyên. Khi `FW_ROOT` không có thẻ nào, catalog giống hệt trước story này.
3. Dòng seed `ALL` và `S70` giữ `id`, lấy số liệu từ thẻ qua trường `card:` (`cut-all-zone1.ALL`, `round-c70.S70`). Dòng `s2-release-669` đổi `id` thành `tray_s2_3618a579b15e`, `id` cũ thành bí danh, các cạnh viết lại.
4. Trạng thái `reference` của thẻ (psi-data) là một trạng thái mới trên giao diện, vẫn tính vào tổng số và vào các chỗ đang lọc `current`.
5. `DATASET_GLOBS` có thêm `datasets/*/releases/*/meta/info.json`. `data_class`, `license` và `source_detail` của dataset trong bộ chạy việc lấy từ thẻ; không có thẻ thì `data_class` là `restricted`.
6. Chỉ mục dựng trên laptop liệt kê `tray_s1_bfbdcbcf719e` và `tray_s1_8631ace9b1b3` là `current`, các release khay cũ là `superseded`.
7. `uv run ruff check`, `uv run mypy`, `uv run pytest`, `uv run lint-imports` sạch; `scripts/repo/pr_guard.py` qua.

## Nhiệm vụ

- [x] 1.1 Viết story (file này)
- [x] 2.1 Bộ đọc và kiểm thẻ `index/cards.py`, có test (AC 1)
- [x] 2.2 Ghép thẻ vào dòng catalog: `load_rows`, `catalog.build`, sửa seed (`card:` cho `ALL`, `S70`; đổi `id` dòng S2), trạng thái `reference`, có test (AC 2, 3, 4)
- [x] 3.1 `DATASET_GLOBS` và `data_class`, `license`, `source_detail` từ thẻ trong `server/kinds.py`, `server/runner.py`, có test (AC 5)
- [ ] 3.2 Nhãn trạng thái `reference`, `benchmark` trên giao diện; README của package (AC 4)
- [ ] 4.1 Chạy đủ kiểm tra, dựng catalog trên dữ liệu thật của laptop, `pr_guard` (AC 6, 7)

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-console/` (mã, seed, giao diện, test, README)

## Ghi chú cho người làm

Bảng ánh xạ thẻ sang dòng catalog (Hiếu duyệt 22/11/2026):

| Trường thẻ | Dòng catalog |
|---|---|
| `id` | `id` (trừ dòng seed có `card:`, giữ `id` của seed và thêm `id` thẻ vào bí danh) |
| `alias` | `name`, và thêm vào `aliases` |
| `status` | `status` |
| `task` | `task` |
| `kind` | `synthetic_s1`, `synthetic_s2` thành `release`; `cut` thành `subset-cut`; `teleop`, `egocentric` thành `raw source`. `data_type` suy từ `kind`; với `cut` lấy của seed, không có thì theo `source_detail` |
| `counts` | `episodes`, `frames`, `hours` |
| `format` | `format`; `fps` đọc từ chuỗi này |
| `quality.qa_decisions` | `qa` và `qa_counts`; `quality.replay_qa` thành `replay_qa`; `quality.known_issues` thành `notes` |
| `lineage.parents` | `parents` và cạnh mới (chỉ khi cha là một dòng có trong catalog) |
| `locations` | `locations`; bỏ mục có `role` bắt đầu bằng `deleted` |
| `data_class`, `license` | `data_class`, `licence` |
| `scene`, `superseded_by`, `lineage.story` | trường mới cùng tên trên dòng |

- Thẻ nằm ngoài git, nên CI và máy không có thẻ chạy bằng seed. Seed vì thế vẫn phải đủ trường.
- Không di chuyển, không sửa gì dưới `fwdata/`. Bằng chứng trên dữ liệu thật dựng ra thư mục tạm, không ghi vào `fwdata/console/`.
- Không gắn `lerobot` cho mọi release có thẻ: chỉ mục robot (ảnh đại diện từng tập) chỉ dựng cho dòng seed đã có gợi ý trình xem.
- Tài liệu BA Console 11/11/2026 không nêu tên `seed/catalog.yaml`, nên story này không sửa design.

## Kiểm thử

- `uv run pytest packages/flywheel-console`
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports` theo README gốc
- `python3 scripts/repo/check_links.py`

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/11/2026 | Tạo story; Hiếu chọn mã DA-45, duyệt bảng ánh xạ, giữ dòng không thẻ trong seed, giữ `id` `ALL`/`S70`, đổi `id` dòng S2 | Hiếu (soạn với Claude) |
