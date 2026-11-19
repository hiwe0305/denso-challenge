# Humanoid Data Flywheel

Đề xuất của đội ilovephysicalintelligence cho thử thách H1 của DENSO Factory Hacks: huấn luyện humanoid nhanh, chính xác, ít công. Recipe là **Ψ₀ + SIMPLE / G1**: fine-tune Ψ₀ trên dữ liệu sinh trong mô phỏng và dữ liệu của người, rồi dùng thuật toán **Failure → Data** để chọn dữ liệu cần bổ sung sau mỗi lỗi, có đối chứng chất lượng và chi phí.

Mọi thí nghiệm chạy trên **Unitree G1 trong SIMPLE** (MuJoCo). Có hai task: task hai bàn của paper Ψ₀ (tái tạo kết quả của tác giả, thí nghiệm HE-1) và **task bê khay** (từ DA-32, task của vòng Failure → Data đầy đủ ở DA-34). Hệ thống có ba loại dữ liệu: egocentric của người, teleop, synthetic; cả ba qua cùng pipeline về định dạng LeRobot của Ψ₀. Agent QA/QC đọc báo cáo dataset, log và output từng stage.

Trạng thái 19/11/2026: demo ngày 17/11/2026 đã trình bày trên **Flywheel Console** (`packages/flywheel-console`). Số đo là sơ bộ trong sim (dev, 1 seed); chi tiết và giới hạn ở [docs/he/tray.md](docs/he/tray.md). Chưa chạy trên robot thật.

## Cấu trúc

| Đường dẫn | Nội dung |
|---|---|
| [docs/spec-v10-failure-to-data.md](docs/spec-v10-failure-to-data.md) | Đặc tả hiện hành (v10.6): giả thuyết HS, HTa, HTb, HD, HE, thuật toán Failure → Data 12 bước, PoC có đối chứng, sổ chi phí, glossary |
| [docs/superpowers/specs/](docs/superpowers/specs) | Design: [27/10/2026](docs/superpowers/specs/2026-10-27-g1-psi0-demo-design.md) (G1 + Ψ₀, pipeline dữ liệu, HE, Agent QA/QC), [28/10/2026](docs/superpowers/specs/2026-10-28-tray-transfer-he-design.md) (task bê khay), [11/11](docs/superpowers/specs/2026-11-11-flywheel-console-design.md) và [15/11/2026](docs/superpowers/specs/2026-11-15-console-one-site-design.md) (Flywheel Console) |
| [docs/he/](docs/he/tray.md) | Thí nghiệm và số đo: task khay ([tray.md](docs/he/tray.md)), HE-1, stage 1, chẩn đoán task hai bàn |
| [docs/g0/](docs/g0/README.md) | Runbook và ghi chép kỹ thuật: SIMPLE, Ψ₀, dữ liệu, Agent QA/QC, sổ chi phí theo story |
| [docs/demo/](docs/demo) | Kịch bản video và script thuyết trình demo 17/11/2026 |
| [docs/product/](docs/product/README.md) | Hồ sơ sản phẩm theo BMAD: brief, PRD, kiến trúc lõi flywheel, kế hoạch chia việc 5 người, phản biện và câu hỏi cho mentor, story Sprint 1 |
| [RULE.md](RULE.md) | **Đọc đầu tiên nếu bạn là thành viên đội:** công việc của từng người, một ngày làm việc, cách làm một story, rule R1–R10, điều không được phá, hỏi ai |
| [CLAUDE.md](CLAUDE.md) | Quy tắc chung cho mọi phiên Claude Code và cho người: đọc gì trước, phạm vi file, quy ước nhánh và commit, bất biến kiến trúc. Có thêm [docs/CLAUDE.md](docs/CLAUDE.md) |
| [scripts/repo/](scripts/repo) | `check_links.py` kiểm liên kết nội bộ; `progress.py` in tiến độ theo story; `pr_guard.py` (workflow `pr-guard`) và `daily_report.py` (chạy tại máy) cho rule kiểm soát theo ngày ([08](docs/product/08-daily-control.md)); `setup_labels.sh` tạo label GitHub |
| [docs/challenge/](docs/challenge/README.md) | Đề bài của BTC, kèm tiêu chí 3 cấp |
| [docs/references/](docs/references/README.md) | Nguồn nghiên cứu; PDF giữ cục bộ, không commit |

## Mở Flywheel Console

```bash
uv run fw console index
uv run fw console serve
```

Console đọc `fwdata/` (hoặc thư mục trong `FW_ROOT`). Cờ `--lock` từ chối mọi việc ghi; `--chat` bật chat. Cách dùng và giới hạn ở [design 15/11/2026](docs/superpowers/specs/2026-11-15-console-one-site-design.md) và [kịch bản video](docs/demo/2026-11-17-kich-ban-video.md).

## Hồ sơ cũ

Hồ sơ của các thiết kế trước Pitch v10 (idea v3/v3.1 với FluxVLA / GR00T N1.5 / GR1, docs 01–14, kế hoạch skill-a1, các bản review, code reference MuJoCo, website đầy đủ) đã được gỡ khỏi thư mục làm việc và giữ trong tag git `archive/v3`.

```bash
git show archive/v3:IDEA.md
```

Lệnh trên in một file cũ ra màn hình. Muốn lấy lại cả thư mục, dùng `git checkout archive/v3 -- <đường dẫn>`.

Ngày 19/11/2026 gỡ thêm website trình bày cũ (`website/`, sửa lần cuối 29/10/2026), workflow đăng GitHub Pages và báo cáo ngày, hai deck trong `deliverables/`. Lấy lại từ commit cha của commit gỡ: `git log --diff-filter=D -- website/` cho biết commit đó.

## Thiết lập và kiểm tra workspace

```bash
uv sync --locked
uv run fw --version
uv run ruff check
uv run mypy -p flywheel.contracts -p flywheel.store -p flywheel.testkit -p flywheel.cli -p flywheel.data -p flywheel.eval -p flywheel.loop -p flywheel.console -p flywheel_simple -p flywheel_psi0
uv run pytest
uv run lint-imports
python scripts/repo/check_links.py
```

Các test cần GPU hoặc simulator được bỏ qua mặc định. Cài thêm công cụ HD bằng `uv sync --all-packages --all-extras`.
