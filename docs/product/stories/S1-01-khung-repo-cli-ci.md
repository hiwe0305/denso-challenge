# S1-01 · Khung repo, CLI `fw` và CI

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt 22/10/2026) |
| Người làm | Long |
| Story PRD | 1.1 · Epic 1 |
| Nhãn | [Lõi] · `epic:1` · `gate:G0` · `area:data` |
| Sprint | S1 (tuần 1–2) |
| Ước lượng | 11 giờ (bản 0.1: 12 giờ; L0-lite bớt phụ thuộc) |
| Phụ thuộc | Không. Chặn S1-08, S1-10 |

## Story

Là kỹ sư data xây lõi, tôi muốn một monorepo uv workspace có CLI `fw` và CI chạy trên CPU, để cả đội thêm module mà không phá nhau và lõi không bao giờ dính vào SIMPLE hay Ψ₀.

## Tiêu chí chấp nhận

1. `uv sync` ở gốc repo dựng môi trường lõi bằng một lệnh; `uv.lock` được commit.
2. `fw --version` in phiên bản package và git SHA; cây bẩn thì thêm hậu tố `-dirty`.
3. Cây thư mục đúng 03 §7.1: `packages/flywheel/src/flywheel/` có đủ `contracts`, `store`, 12 module lõi, `testing`, `cli`; mỗi module có `__init__.py` với docstring ghi trách nhiệm theo 03 §5.1. Có `packages/flywheel-fakes/` rỗng với `pyproject.toml`.
4. Workflow mới `.github/workflows/core-ci.yml` chạy ruff, mypy, pytest, import-linter ở mỗi push và pull request, xong dưới 10 phút. Không sửa `pages.yml`.
5. Luật import: `flywheel` không được import `simple`, `psi0`, `lerobot`, `torch`, `isaacsim`, `mujoco` và các package `flywheel_simple`, `flywheel_psi0`, `flywheel_lerobot`. Thử một lần với import cố ý vi phạm: CI đỏ.
6. `.gitignore` thêm `fwdata/`, `*.ckpt`, `*.safetensors`, `*.pt`. Không đụng `website/`, `deliverables/`. Không thêm `mlruns/` vì L0-lite không dùng MLflow (03 ADR-13).
7. `packages/flywheel/README.md` ghi: cách chạy test, quy ước nhánh và PR, đường dẫn tới DoD ở 04 mục 5.

## Nhiệm vụ

- [x] 1. Dựng uv workspace (AC 1)
  - [x] 1.1 `pyproject.toml` gốc khai workspace `packages/*`; Python ≥ 3.10
  - [x] 1.2 `packages/flywheel/pyproject.toml` với phụ thuộc lõi của 03 §7.1 bản 0.3 (pydantic, pyarrow, duckdb, numpy, scipy, statsmodels, typer, structlog, jinja2); extra `hd` chứa `rerun-sdk`. Không thêm fsspec, MLflow, Streamlit (L0-lite)
  - [x] 1.3 Commit `uv.lock`
- [x] 2. CLI `fw` bằng Typer (AC 2)
  - [x] 2.1 Lệnh `fw --version` đọc phiên bản package và `git rev-parse HEAD`, kiểm cây bẩn
  - [x] 2.2 Khai entry point `fw` trong `pyproject.toml`
- [x] 3. Khung module (AC 3)
  - [x] 3.1 Tạo thư mục và docstring cho từng module
  - [x] 3.2 Tạo `packages/flywheel-fakes/` rỗng
- [x] 4. CI (AC 4, 5)
  - [x] 4.1 Cấu hình ruff, mypy, pytest trong `pyproject.toml`
  - [x] 4.2 Hợp đồng import-linter cho danh sách cấm ở AC 5
  - [x] 4.3 Viết `core-ci.yml`; chạy thử một PR có import vi phạm, ghi kết quả vào Ghi chép khi làm
- [x] 5. `.gitignore` và README (AC 6, 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `pyproject.toml`, `uv.lock`: workspace gốc
- `packages/flywheel/pyproject.toml`, `packages/flywheel/README.md`
- `packages/flywheel/src/flywheel/`: chỉ file init có docstring của từng module và cli/main.py; nội dung module do story sau viết
- `packages/flywheel/tests/test_version.py`, `packages/flywheel/tests/test_import_rules.py`
- `packages/flywheel-fakes/pyproject.toml`
- `.github/workflows/core-ci.yml`
- `.gitignore`

## Ghi chú cho người làm

- Nguồn: 02 · 1.1, NFR1, NFR2, NFR12, mục 4 (chiến lược test); 03 §1.2 (nguyên tắc lõi), §2.4 (L0-lite), §3.1 (stack), §7.1 (cây mã), ADR-01, ADR-02, ADR-13.
- L0-lite (06 mục 9, 03 ADR-13): `store` dùng `pathlib`, chưa có fsspec, MinIO hay S3; theo dõi thí nghiệm bằng `metrics.jsonl`, không dựng MLflow; console HD là lệnh Typer, không Streamlit. Thêm lại ở L1 mà không đổi module khác.
- Lõi chạy trên Python 3.10 để dùng chung hợp đồng với worker trong container SIMPLE (03 §3.1). Không thêm torch vào lõi.
- File sẽ tạo: `pyproject.toml`, `uv.lock`, `packages/flywheel/pyproject.toml`, `packages/flywheel/src/flywheel/**/__init__.py`, `packages/flywheel/src/flywheel/cli/main.py`, `packages/flywheel/tests/test_version.py`, `packages/flywheel/tests/test_import_rules.py`, `packages/flywheel/README.md`, `packages/flywheel-fakes/pyproject.toml`, `.github/workflows/core-ci.yml`.
- File sẽ sửa: `.gitignore`.
- Story này là mẫu cho cả đội; giữ đơn giản để Thông và các bạn Simulation đọc được.

## Kiểm thử

- `uv run pytest`, `uv run ruff check`, `uv run mypy packages/flywheel/src`, `uv run lint-imports` đều xanh.
- `test_version.py`: `fw --version` trả mã 0 và chuỗi có SHA.
- `test_import_rules.py` hoặc cấu hình import-linter: một module giả import `torch` làm CI đỏ (chạy một lần, rồi bỏ).
- Người review chạy `uv sync` trên máy khác và `fw --version` ra cùng phiên bản.

## Người phụ trách

- Làm: Nguyễn Thăng Long
- Review: Dương Tiến Thông
- Dự phòng: Dương Tiến Thông

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 22/10/2026 | Tạo story từ 02 · 1.1 | SM (Bob), PO (Sarah) duyệt |
| 22/10/2026 | Theo L0-lite (06 mục 9, 03 bản 0.3): bỏ fsspec khỏi phụ thuộc lõi, thêm statsmodels và extra `hd`; bỏ `mlruns/` khỏi `.gitignore`; ước lượng 12 → 11 giờ | SM (Bob) theo 06 |
| 24/10/2026 | Thêm mục Phạm vi file (07 mục 3.1). AC không đổi | PO (Hiếu) |
| 24/10/2026 | Hoàn thành triển khai và kiểm thử cục bộ toàn bộ nhiệm vụ S1-01; chờ review PR | Nguyễn Thăng Long |

## Ghi chép khi làm

- Giờ thực: 1,1 giờ (1 giờ triển khai ban đầu; 0,1 giờ sửa review).
- Công cụ AI đã dùng: Codex.
- Ghi chú hoàn thành: Ruff, mypy, 5 pytest và import-linter đều xanh. Phép thử
  import cố ý `flywheel.catalog -> torch` làm Core CI đỏ tại
  `test_flywheel_has_no_forbidden_imports`; bằng chứng:
  <https://github.com/hiwe0305/denso-challenge/actions/runs/40057217059>.
  Import thử nghiệm đã được gỡ và cổng được chạy lại. Sau review, `fw --version`
  được neo vào thư mục package và có test gọi từ thư mục hiện hành ngoài repo.
- File đã tạo hoặc sửa: `pyproject.toml`, `uv.lock`, `.gitignore`,
  `.github/workflows/core-ci.yml`, `packages/flywheel/`, `packages/flywheel-fakes/`,
  và file story này.
