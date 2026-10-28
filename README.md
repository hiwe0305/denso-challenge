# Humanoid Data Flywheel

Đề xuất của đội ilovephysicalintelligence cho thử thách H1 của DENSO Factory Hacks: huấn luyện humanoid nhanh, chính xác, ít công. Recipe hiện hành là **Ψ₀ + SIMPLE / G1**: fine-tune Ψ₀ trên dữ liệu teleop và dữ liệu sinh trong mô phỏng, rồi dùng thuật toán **Failure → Data** để chọn dữ liệu cần bổ sung sau mỗi lỗi, có đối chứng chất lượng và chi phí.

Từ 27/10/2026, demo ngày 17/11/2026 và mọi thí nghiệm chạy trên **Unitree G1 trong SIMPLE**, task hai bàn: gắp vật ở bàn này, đi sang bàn kia, đặt lên. Hệ thống có ba loại dữ liệu: egocentric của người, teleop, synthetic; cả ba qua pipeline 6 tầng về một định dạng chung. Nguồn để test bây giờ là dữ liệu công bố và sim (mẫu EgoDex, dataset teleop của tác giả Ψ₀, teleop bàn phím, synthetic S1 và S2 trong SIMPLE), sau đó video egocentric đội tự quay. Thí nghiệm HE kiểm claim của Ψ₀ rằng dữ liệu egocentric của người giúp cần ít demo robot hơn. Agent QA/QC đọc báo cáo dataset, log và output từng stage.

Trạng thái: đề xuất PoC, chưa chạy Ψ₀ hoặc robot thật. Số liệu hiệu quả là ước lượng có điều kiện. Website và hai file PowerPoint chưa cập nhật theo hướng 27/10/2026.

## Cấu trúc

| Đường dẫn | Nội dung |
|---|---|
| [docs/spec-v10-failure-to-data.md](docs/spec-v10-failure-to-data.md) | Đặc tả hiện hành (v10.4): giả thuyết HS, HTa, HTb, HD, HE, thuật toán Failure → Data 12 bước, PoC với các nhánh A, A₀.₇, B, B-fail, C, thí nghiệm HE, sổ chi phí, lộ trình 12 tuần, glossary |
| [docs/superpowers/specs/](docs/superpowers/specs/2026-10-27-g1-psi0-demo-design.md) | Design ngày 27/10/2026 (hiện hành duy nhất): task hai bàn, simulator, teleop bàn phím, sinh tự động, pipeline 6 tầng, thí nghiệm HE, Agent QA/QC và bộ lỗi cấy, bảng lỗi, kịch bản demo 17/11 |
| [docs/product/](docs/product/README.md) | Hồ sơ sản phẩm theo BMAD: brief, PRD, kiến trúc lõi flywheel, kế hoạch chia việc 5 người, phản biện và câu hỏi cho mentor, story Sprint 1 |
| [RULE.md](RULE.md) | **Đọc đầu tiên nếu bạn là thành viên đội:** công việc của từng người, một ngày làm việc, cách làm một story, rule R1–R9, điều không được phá, hỏi ai |
| [CLAUDE.md](CLAUDE.md) | Quy tắc chung cho mọi phiên Claude Code và cho người: đọc gì trước, phạm vi file, quy ước nhánh và commit, bất biến kiến trúc. Có thêm [docs/CLAUDE.md](docs/CLAUDE.md) và [website/CLAUDE.md](website/CLAUDE.md) |
| [scripts/repo/](scripts/repo) | `check_links.py` kiểm liên kết nội bộ; `progress.py` in tiến độ theo story; `pr_guard.py` và `daily_report.py` cho rule kiểm soát theo ngày ([08](docs/product/08-daily-control.md)); `setup_labels.sh` tạo label GitHub |
| [docs/challenge/](docs/challenge/README.md) | Đề bài của BTC, kèm tiêu chí 3 cấp |
| [docs/references/](docs/references/README.md) | Nguồn nghiên cứu; PDF giữ cục bộ, không commit |
| [deliverables/](deliverables) | [Pitch v10](deliverables/DENSO-ilovephysicalintelligence-1.pptx) và [deck workflow kỹ thuật](deliverables/DENSO-Platform-Visual-Workflow-2026-10-08-v1.pptx) |
| [website/](website/README.md) | Website trình bày 12 trang, build từ `website/content` và hai deck |
| [.github/workflows/pages.yml](.github/workflows/pages.yml) | Build, kiểm tra và đăng website lên GitHub Pages |

## Mở website

```bash
bash start-website.sh
```

Sau đó mở [website cục bộ](http://127.0.0.1:4175/#overview) và giữ cửa sổ máy chủ chạy trong lúc xem. Cách sửa nội dung và build lại nằm trong [website/README.md](website/README.md).

## Hồ sơ cũ

Hồ sơ của các thiết kế trước Pitch v10 (idea v3/v3.1 với FluxVLA / GR00T N1.5 / GR1, docs 01–14, kế hoạch skill-a1, các bản review, code reference MuJoCo, website đầy đủ) đã được gỡ khỏi thư mục làm việc và giữ trong tag git `archive/v3`.

```bash
git show archive/v3:IDEA.md
```

Lệnh trên in một file cũ ra màn hình. Muốn lấy lại cả thư mục, dùng `git checkout archive/v3 -- <đường dẫn>`.

## Thi?t l?p v? ki?m tra workspace

```bash
uv sync --locked
uv run fw --version
uv run ruff check
uv run mypy -p flywheel.contracts -p flywheel.store -p flywheel.testkit -p flywheel.cli -p flywheel.data -p flywheel.eval -p flywheel.loop -p flywheel_simple -p flywheel_psi0
uv run pytest
uv run lint-imports
python scripts/repo/check_links.py
```

C?c test c?n GPU ho?c simulator ???c b? qua m?c ??nh. C?i th?m c?ng c? HD b?ng `uv sync --all-packages --all-extras`.
