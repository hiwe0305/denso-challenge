# S1-10 · Mô hình dữ liệu L0-lite và kho lưu (phần a của 2.1)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Hoàn thành (Chờ review và merge) |
| Người làm | Long |
| Story PRD | 2.1, phần a · Epic 2. Phần b (RunPlan, `fw plan freeze`, test NFR7) làm ở S3 |
| Nhãn | [Lõi] · `epic:2` · `gate:G1` · `area:data` |
| Sprint | S1, tuần 1–2 · **Lịch 3/11/2026:** sửa CI của #36 và merge trước **5/11/2026** |
| Ước lượng | 10 giờ (bản 0.1: 14 giờ; L0-lite bớt phân vùng ngày, lệnh dựng lại chỉ mục, fsspec) |
| Phụ thuộc | PR `chore-restructure` (07 mục 3.6; mở PR 28/10, merge 29/10/2026). Dùng chung `contracts` với S1-08, cùng người làm. Long làm và giữ nhân; Hiếu duyệt mọi thay đổi schema (07 mục 2.0) |

## Story

Là kỹ sư data, tôi muốn schema có phiên bản và kho lưu bất biến cho 12 thực thể L0-lite, để dữ liệu từ nhiều nguồn và nhiều vòng truy được nguồn gốc mà không phải đổi schema khi lên L1–L4.

## Tiêu chí chấp nhận

1. Model Pydantic v2 cho đủ 12 thực thể L0-lite của 03 §4.3: Source (có `provenance`), Condition, Episode, QAReport, Release, Checkpoint, RunPlan, Score, Cluster, FixRateEvent, LedgerEntry, Decision. Trường mở rộng nằm trong `meta`. Score, Cluster, FixRateEvent, Decision ở story này chỉ cần khóa, cột chính và test ID; story dùng chúng bổ sung sau. RunPlan đóng băng làm ở 2.1b (S3).
2. Embodiment, Task (gồm ConditionSchema), SplitPlan, PriceBook là cấu hình YAML có hash trong `configs/`, có model Pydantic để validate, không là bảng catalog (bảng gộp ở 03 §4.3). Tên cũ của bản 0.2 (Job, Trace, ConditionSet, StageResult, EvidenceCard, …) chỉ là tên khái niệm.
3. Mọi bản ghi có `schema_version` và `meta`. `task_id`, `embodiment_id`, `site_id` là **cột thường có giá trị mặc định** theo 03 §4.1: `site_id = local`, `task_id` và `embodiment_id` lấy từ RunPlan. `domain` nằm trong cấu hình Embodiment. Episode có `license`, `data_class` (public, internal, restricted), `operator_kind` (human, machine). Test: tạo bản ghi không truyền ba cột này thì nhận giá trị mặc định.
4. ID: thực thể nội dung dùng tiền tố cộng 16 ký tự đầu sha256 của JSON chuẩn hóa; thực thể sự kiện dùng tiền tố cộng ULID (03 §4.1). Test: cùng nội dung cho cùng ID; đổi một trường cho ID khác; JSON chuẩn hóa ổn định giữa các lần chạy.
5. `flywheel.store` theo 03 §7.2: đường dẫn cục bộ qua `pathlib` (không fsspec); `$FW_ROOT` mặc định `./fwdata`, dữ liệu dưới `sites/local/`; blob theo sha256 ở `objects/sha256/ab/cd/<hash>`; bảng append-only ở `catalog/<bảng>/part-<ulid>.jsonl`, không phân vùng ngày; mỗi tiến trình ghi tệp part riêng.
6. Chỉ mục `index/fw.duckdb` chỉ chứa view, tự tạo khi mở (`CREATE OR REPLACE VIEW` trên glob của từng bảng, đọc bằng `read_json` với `union_by_name`). Xóa tệp rồi mở lại cho cùng kết quả truy vấn (có test). Không có lệnh `fw index rebuild` (hoãn tới L1, ADR-13).
7. `ledger.append(entry)` ghi LedgerEntry vào `ledger.jsonl` của thư mục job; ước tính và thực đo là hai dòng riêng (`measure_kind` bắt buộc), dòng thực đo có `estimate_entry_id`. Đây là nền cho `ledger.meter()` của runner ở S2.
8. Xuất JSON Schema của các model vào `packages/flywheel-contracts/schemas/` (ADR-06).
9. Test chạy trên CPU, không phụ thuộc adapter.

## Nhiệm vụ

- [x] 1. `contracts/base.py`: lớp bản ghi gốc có `schema_version`, `meta`, cột mặc định `site_id`, `task_id`, `embodiment_id`, JSON chuẩn hóa, hàm tạo ID (AC 3, 4); xong trước ngày 4 để S1-08 dùng
- [x] 2. Model 12 thực thể và model cấu hình (AC 1, 2)
- [x] 3. `flywheel.store` (AC 5)
  - [x] 3.1 Đường dẫn `pathlib` dưới `$FW_ROOT/sites/local/`
  - [x] 3.2 Blob theo sha256
  - [x] 3.3 Ghi bảng append-only `part-<ulid>.jsonl`
- [x] 4. View DuckDB tự tạo khi mở và test xóa rồi mở lại (AC 6)
- [x] 5. `ledger.append` và test (AC 7)
- [x] 6. Xuất JSON Schema (AC 8)
- [x] 7. Sửa feedback review PR #36 của Hiếu (AC 1, 2, 7, 8)
- [x] 8. Sửa review PO ngày 3/11/2026 sau `8458371` trên PR #36 (AC 1, 5, 6, 7)
  - [x] 8.1 `Score.task_id` bắt buộc, không còn mặc định `"default"`
  - [x] 8.2 `Score` thêm `trace_sha256` để `ScoreRecord` của DA-36 chuyển sang `Score` không mất trường (#59 mục 7)
  - [x] 8.3 View DuckDB không đếm trùng: một `id` ra một dòng; kho vẫn append-only
  - [x] 8.4 Sổ chi phí từ chối dòng thực đo trỏ tới ước tính không có hoặc trỏ tới dòng thực đo; `reverses_entry_id` phải là dòng có thật
  - [x] 8.5 `blob_path` chỉ nhận sha256 64 ký tự hex, không thoát ra ngoài kho
  - [x] 8.6 Bốn file mẫu chung trong testkit: `Score.json`, `Cluster.json`, `Decision.json`, `LedgerEntry.json`
  - [x] 8.7 Cột kiểu `X | None` trong view có kiểu SQL thật (`BOOLEAN`, `BIGINT`, …), không phải `VARCHAR`
  - [ ] 8.8 `StorePaths` kiểm mọi đoạn đường dẫn (cả `.` và `site`); bảng ngoài danh sách catalog bị từ chối khi ghi

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-contracts/src/flywheel/contracts/base.py`, `packages/flywheel-contracts/src/flywheel/contracts/configs.py`
- `packages/flywheel-contracts/src/flywheel/contracts/entities.py` hoặc `packages/flywheel-contracts/src/flywheel/contracts/entities/`
- `packages/flywheel-contracts/src/flywheel/contracts/artifacts.py`
- `packages/flywheel-contracts/schemas/`, `packages/flywheel-contracts/tests/`
- `packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/`
- `packages/flywheel-store/src/flywheel/store/` (gồm `ledger_append.py`: ghi sổ chi phí append-only)
- `packages/flywheel-store/tests/`
- `configs/splits/default.yaml`

## Ghi chú cho người làm

- Nguồn: 02 · 2.1 (bản 0.3), FR1–FR4, NFR6, NFR7, NFR12; 03 §2.4 (L0-lite), §4 (bản 0.3), §7.2, ADR-03, ADR-04, ADR-05, ADR-06, ADR-08, ADR-12, ADR-13; bảng tên ở 04 mục 1.4.
- L0-lite (06 mục 9, 03 ADR-13) thay quyết định P27 của bản 0.1: 12 thực thể thay 28; hoãn MLflow, Streamlit, fsspec S3, phân vùng ngày, lệnh dựng lại chỉ mục, revision card. Giữ `task_id`, `embodiment_id`, `site_id` vì gần như không tốn công và giữ đường L1–L4.
- Holdout không nằm ở bảng Condition mà trong vault (03 §4.3); story này không tạo vault.
- Sinh ULID: dùng thư viện nhỏ hoặc tự viết; nếu thêm phụ thuộc mới ngoài danh sách 03 §7.1, ghi vào PR.
- Mặc định PO cho psi-data: `license = unknown`, `data_class = restricted`.
- File sẽ tạo: `packages/flywheel-contracts/src/flywheel/contracts/base.py`, `contracts/entities.py` (hoặc thư mục `contracts/entities/`), `contracts/configs.py`, `packages/flywheel-store/src/flywheel/store/{paths,blobs,tables,views}.py`, `packages/flywheel-store/src/flywheel/store/ledger_append.py`, `packages/flywheel-contracts/schemas/*.json`, test tương ứng trong `tests/` của từng package.

## Kiểm thử

- Unit test ID và JSON chuẩn hóa, gồm property test bằng hypothesis: hoán vị khóa không đổi ID.
- Test cột mặc định: bản ghi thiếu `site_id`, `task_id`, `embodiment_id` nhận giá trị mặc định; thêm embodiment giả không đổi schema.
- Test kho: ghi, đọc lại, hash khớp; hai tiến trình ghi song song không đè nhau.
- Test chỉ mục: xóa `fw.duckdb`, mở lại, cùng kết quả truy vấn.
- Long review phần ranh giới với `contracts/protocols.py`.

## Người phụ trách

- Làm: Nguyễn Thăng Long
- Chịu trách nhiệm cuối và review: Nguyễn Thăng Long
- Dự phòng: Nguyễn Thăng Long

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 2.1, tách phần a cho S1; phụ thuộc đổi thành 1.1 (04 P17) | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Theo L0-lite (06 mục 9, 02 · 2.1 bản 0.3, 03 §2.4, §4.3): 12 thực thể, cấu hình ngoài catalog, `task_id`, `embodiment_id`, `site_id` là cột có mặc định; JSONL không phân vùng ngày, view DuckDB tự tạo, bỏ `fw index rebuild`, bỏ fsspec; ước lượng 14 → 10 giờ | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file. AC không đổi | PO (Hiếu) |
| 25/10/2026 | Đường dẫn theo nhân mới: `flywheel-contracts`, `flywheel-store`; hàm ghi sổ chi phí nằm trong kho vì mọi làn đều ghi; phân tích sổ chi phí thuộc làn Vòng (Long) | PO (Hiếu) theo design chia làn |
| 27/10/2026 | Giao cho Long theo 07 mục 2.0 (bản 0.6) | PO (Hiếu) |
| 28/10/2026 | Sửa dòng Phụ thuộc: Long làm và giữ nhân, hạn PR `chore-restructure` mới | PO (Hiếu) |
| 02/11/2026 | Hoàn thành toàn bộ AC 1–9, hoàn thành các nhiệm vụ con 1–6, cập nhật tiến độ | Nguyễn Thăng Long |
| 3/11/2026 | Hạn mới theo lịch hoàn thiện 13/11/2026 (07 mục 2.4) | PO (Hiếu) |
| 03/11/2026 | Sửa 7 điểm feedback review của Hiếu trên PR #36: LedgerEntry hai dòng, tái sử dụng Episode/QAReport, kiểm tra schema, type action_layout, SplitPlanConfig | Nguyễn Thăng Long |
| 03/11/2026 | Sửa 2 lỗi chặn merge (episode_id catalog theo DA-25, DuckDB view khi kho rỗng) và hoàn thiện Issue #62 (benchmark_copy_id, Score task_id/config_sha256, path traversal guard, TableWriter validation) | Nguyễn Thăng Long |
| 03/11/2026 | Thêm nhiệm vụ 8, sửa 6 điểm review PO sau `8458371`: `Score.task_id` bắt buộc, thêm `Score.trace_sha256`, view lọc trùng theo `id`, sổ chi phí kiểm dòng được trỏ tới, `blob_path` chỉ nhận sha256, bốn file mẫu chung. AC không đổi | Hiếu (cùng Claude) |

## Ghi chép khi làm

- Giờ thực: 15h (12.5h của Long; 2.5h nhiệm vụ 8 do Hiếu cùng Claude làm ngày 3/11/2026)
- Công cụ AI đã dùng: Antigravity
- Ghi chú hoàn thành: Đã hiện thực đầy đủ BaseRecord, 12 thực thể L0-lite, 4 cấu hình YAML, StorePaths, sha256 blobs, TableWriter, tự tạo view DuckDB khi kết nối, LedgerStore và xuất JSON Schema. Sửa theo toàn bộ 7 mục góp ý của Hiếu trên PR #36. Tất cả test unit và e2e đều đạt.
- File đã tạo hoặc sửa:
  - packages/flywheel-contracts/src/flywheel/contracts/base.py
  - packages/flywheel-contracts/src/flywheel/contracts/configs.py
  - packages/flywheel-contracts/src/flywheel/contracts/entities.py
  - packages/flywheel-contracts/schemas/*.json
  - packages/flywheel-contracts/tests/unit/test_base.py
  - packages/flywheel-contracts/tests/unit/test_configs.py
  - packages/flywheel-contracts/tests/unit/test_entities.py
  - packages/flywheel-contracts/tests/unit/test_schemas.py
  - packages/flywheel-store/src/flywheel/store/paths.py
  - packages/flywheel-store/src/flywheel/store/blobs.py
  - packages/flywheel-store/src/flywheel/store/tables.py
  - packages/flywheel-store/src/flywheel/store/views.py
  - packages/flywheel-store/src/flywheel/store/ledger_append.py
  - packages/flywheel-store/tests/unit/test_paths.py
  - packages/flywheel-store/tests/unit/test_blobs.py
  - packages/flywheel-store/tests/unit/test_tables.py
  - packages/flywheel-store/tests/unit/test_views.py
  - packages/flywheel-store/tests/unit/test_ledger_append.py
  - docs/product/stories/S1-10-mo-hinh-du-lieu-va-kho.md
