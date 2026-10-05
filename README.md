# Humanoid Skill Learning

**Công cụ giúp đội AI/robotics huấn luyện kỹ năng humanoid từ mẫu robot, video người và dữ liệu bổ sung phù hợp, nhằm giảm công thu thập và thử nghiệm ở cùng chất lượng.**

Case đại diện: humanoid fixed-base lấy linh kiện cứng vào ô khay. Đường chính: FluxVLA + GR00T N1.5 + GR1/RoboCasa/MuJoCo, Robot baseline trước; human/video/Cosmos có gate, bốn nguồn là catalog và SOP. Core15 runs (6 R0 +9 T/F/A); ít nhất hai cách học thật trong report. Task DENSO chưa chốt; lựa chọn này là thiết kế, chưa integration/training result.

Website hỗ trợ bản nộp idea H1; deck theo mẫu BTC vẫn là hồ sơ chính. [Bảng chấm nội bộ trước PoC](docs/reviews/idea-review.md) được giữ làm tham chiếu lịch sử, không dùng làm điểm đánh giá vòng idea hoặc điểm BTC.

## Đọc và phát triển

| Tài liệu canonical | Vai trò |
|---|---|
| [Product](docs/01-product.md) | Vấn đề, case/acceptance, contribution, phạm vi và quyết định sản phẩm |
| [PRD](docs/08-prd.md) | Requirements/user stories, acceptance từng chức năng và NFR |
| [Architecture](docs/02-system-architecture.md) | Components/runtime/API/storage và production boundaries |
| [Data Core](docs/03-data-core.md) | Import/QA/signals/lineage/splits/releases |
| [Learning Core](docs/04-learning-core.md) | Chọn model/sim/objectives/fallback và inference |
| [Contracts](docs/05-contracts.md) | Schema và invariants để triển khai |
| [Protocol, roadmap, risks](docs/06-validation-and-roadmap.md) | E0–E4, success/cost, 12 tuần và technical risks |
| [Business case](docs/07-business-case.md) | Dự toán từng khoản có nguồn, sensitivity và chi phí vận hành có phạm vi |
| [SOP](docs/10-data-collection-sop.md) | Thu và QA các nguồn, tận dụng teleop đúng splits |
| [Survey](docs/11-method-survey.md) | 13 phương pháp/source chính thức, chọn/tái sử dụng thay vì SOTA leaderboard |
| [Public examples](docs/12-public-data-examples.md) | G1/HumanEgo/LIBERO numerical previews và media provenance |
| [Expected outcomes](docs/13-expected-outcomes.md) | Kết quả bàn giao, task example và tiêu chuẩn nghiệm thu |

Không xóa PRD/TDD/contracts vì chúng có requirements, interfaces và invariants riêng phục vụ hiện thực sản phẩm. Risk register đã hợp nhất vào protocol; biểu mẫu chưa đối chiếu BTC đã bỏ vì lặp product/pitch. Giữ [PROMPT](PROMPT.md), [đề gốc](docs/information-challenge/infor.md) và [paper index](docs/references/README.md) làm nguồn yêu cầu/tham khảo, không phải specification thứ hai.

## Website trên GitHub Pages

Repository: [hiwe0305/denso-challenge](https://github.com/hiwe0305/denso-challenge).

1. Mở **Settings → Pages**, chọn **Source: GitHub Actions**.
2. Mở **Actions → Deploy website to GitHub Pages → Run workflow**, chọn nhánh `master`.
3. Sau khi deploy thành công, mở [website](https://hiwe0305.github.io/denso-challenge/#overview).

Workflow kiểm tra và xuất bản riêng `presentation-site/dist`, không xuất bản toàn bộ hồ sơ hoặc PDF. Khi Pages chưa bật đúng source, bước deploy được bỏ qua; sau khi bật, chạy workflow một lần. Các lần push tiếp theo lên `master`/`main` tự cập nhật website. [Hướng dẫn GitHub](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

## Website và proposal

[Website local](http://127.0.0.1:4175/#overview) chứa đầy đủ idea, survey và ví dụ thật. [Cách chạy/build/kiểm tra](presentation-site/README.md). [Pitch outline](deliverables/Human-first-Humanoid-Pitch.md) là bản tóm tắt cho người trình bày, không deck template đã hoàn thiện.

Website BTC hiện ghi [H1](https://densohackathon.vn/theme). [Thể lệ](https://densohackathon.vn/challenges) yêu cầu slide theo mẫu chính thức; website là tài liệu bổ sung và localhost không truy cập được từ BTC.

Tạo hai gói bàn giao local bằng `python3 presentation-site/package.py`: website và hồ sơ sản phẩm, lưu trong `deliverables/`. ZIP là output có thể tạo lại nên không commit. Video stream từ tác giả, không đóng gói remote media. Chưa có kết quả huấn luyện, tiết kiệm hoặc production ML của đội.

Thư viện PDF nghiên cứu giữ local tại `docs/references/papers/`, không commit hoặc đưa vào Pages. Nguồn chính thức được dẫn trong paper index và catalog. File tạm, cache, ảnh preview cũ và Git repository lồng đã được dọn; chỉ repository ở gốc quản lý project.

Bản cải thiện05/10/2026: T expert teleop / F fixed mixture / A condition-cost từ R0; repair tách khỏi data comparison; augmentation cơ bản trước Cosmos. Chi phí có ba phạm vi, planner R&D và acquisition ledger giữ unknown; full-source stress scenario gốc và điểm6,5 giữ nguyên. [Protocol](docs/06-validation-and-roadmap.md) · [Budget assumptions](presentation-site/content/pilot-budget.json).
