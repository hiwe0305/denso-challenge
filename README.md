# Humanoid Data Flywheel

Đề xuất của đội ilovephysicalintelligence cho thử thách H1 của DENSO Factory Hacks: huấn luyện humanoid nhanh, chính xác, ít công. Recipe hiện hành là **Ψ₀ + SIMPLE / G1**: fine-tune Ψ₀ trên dữ liệu teleop và dữ liệu sinh trong mô phỏng, rồi dùng thuật toán **Failure → Data** để chọn dữ liệu cần bổ sung sau mỗi lỗi, có đối chứng chất lượng và chi phí.

Từ 23/10/2026, robot chính là **mobile manipulator của DENSO** chạy trong Isaac Sim, với task lấy linh kiện từ khay đặt vào máy; G1 trong SIMPLE là bàn thử. Dữ liệu teleop, video egocentric và synthetic (qua NVIDIA NIM) đi qua cùng một pipeline; mỗi stage của Ψ₀ được chấm riêng để quy lỗi về stage.

Trạng thái: đề xuất PoC, chưa chạy Ψ₀ hoặc robot thật. Số liệu hiệu quả là ước lượng có điều kiện.

## Cấu trúc

| Đường dẫn | Nội dung |
|---|---|
| [docs/spec-v10-failure-to-data.md](docs/spec-v10-failure-to-data.md) | Đặc tả hiện hành (v10.2): giả thuyết HS, HTa, HTb, HD, thuật toán Failure → Data 12 bước, PoC với các nhánh A, A₀.₇, B, B-fail, C, robot DENSO và robot thay thế, sổ chi phí, lộ trình 12 tuần, glossary |
| [docs/superpowers/specs/](docs/superpowers/specs/2026-10-23-data-pipeline-and-failure-eval-design.md) | Design ngày 23/10/2026: pipeline dữ liệu ba nguồn, synthetic S1–S4 qua NIM, output từng stage Ψ₀, bảng lỗi, thông tin cần xin DENSO |
| [docs/product/](docs/product/README.md) | Hồ sơ sản phẩm theo BMAD: phân tích idea, brief, PRD, kiến trúc lõi flywheel, kế hoạch chia việc 5 người, phản biện và câu hỏi cho mentor, story Sprint 1 |
| [CLAUDE.md](CLAUDE.md) | Quy tắc chung cho mọi phiên Claude Code và cho người: đọc gì trước, phạm vi file, quy ước nhánh và commit, bất biến kiến trúc. Có thêm [docs/CLAUDE.md](docs/CLAUDE.md) và [website/CLAUDE.md](website/CLAUDE.md) |
| [scripts/](scripts) | `check_links.py` kiểm liên kết nội bộ; `progress.py` in tiến độ nhiệm vụ con theo story |
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
