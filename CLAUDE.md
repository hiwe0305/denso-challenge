# CLAUDE.md · Humanoid Data Flywheel

Hướng dẫn cho Claude Code (và người) làm việc trong repo này. Đội 5 người cùng dùng Claude; mục tiêu của file là để mọi phiên Claude làm cùng một cách và không giẫm lên việc của nhau. Bản tóm tắt cho người (công việc từng người, rule, quy trình một story) ở [RULE.md](RULE.md).

## Dự án

Đề xuất của đội ilovephysicalintelligence cho thử thách DENSO Factory Hacks. Lõi là **thuật toán Failure → Data**: khi policy robot hỏng trong mô phỏng, kiểm lỗi hệ thống trước, rồi chọn dữ liệu cần thu theo chi phí thật, có đối chứng. Model là Ψ₀ (dùng lại checkpoint của tác giả). Từ 27/10/2026 robot là Unitree G1 trong SIMPLE, đúng robot và model của paper; task chính là task hai bàn (gắp vật ở bàn này, đi sang bàn kia, đặt lên). Thu và sinh dữ liệu chạy MuJoCo thuần của SIMPLE, Isaac Sim chỉ render. Robot DENSO đã bỏ khỏi phạm vi.

Trạng thái 27/10/2026: S1-01 đã merge (khung `packages/`, CLI `fw`, CI); Sprint 1 bắt đầu 26/10/2026; demo ngày 17/11/2026. Người làm của story mới và story đổi hướng chờ Product Owner giao.

## Đọc gì trước

| Khi làm | Đọc |
|---|---|
| Bất kỳ việc gì | File story của mình trong `docs/product/stories/`, rồi [07 · Chia việc và quy trình git](docs/product/07-team-workflow.md) |
| Thuật toán, giả thuyết, thí nghiệm | [Spec v10.4](docs/spec-v10-failure-to-data.md) |
| Module lõi, adapter, schema, cây thư mục, luật import, artifact giữa làn | [03 · Kiến trúc](docs/product/03-architecture.md) |
| Task hai bàn, simulator, teleop bàn phím, sinh tự động, pipeline dữ liệu 6 tầng, LeRobot v2.1/v3, thí nghiệm HE, probe theo stage, Agent QA/QC và bộ lỗi cấy, bảng lỗi, kịch bản demo 17/11 | [Design 27/10/2026](docs/superpowers/specs/2026-10-27-g1-psi0-demo-design.md), design hiện hành duy nhất |
| Ai làm gì, sprint, Definition of Done | [04 · Kế hoạch](docs/product/04-delivery-plan.md) |
| Rule kiểm soát theo ngày, báo lỗi, nhãn nguyên nhân | [08 · Kiểm soát dự án theo ngày](docs/product/08-daily-control.md) |
| Thuật ngữ | Spec mục 12 |

Khi tài liệu mâu thuẫn: spec và design thắng PRD (02); 03 thắng mọi mô tả cấu trúc mã khác. Báo cho Product Owner (Hiếu) thay vì tự chọn.

## Quy tắc làm việc với story

1. **Một story = một nhánh = một worktree = một phiên Claude.** Không làm hai story trong một phiên.
2. Đọc mục "Tiêu chí chấp nhận", "Nhiệm vụ" và "Phạm vi file" của story trước khi sửa gì. Nếu story chưa có "Phạm vi file", hỏi người làm story trước khi bắt đầu.
3. **Chỉ sửa file trong phạm vi của story.** Cần sửa file ngoài phạm vi (nhất là `contracts/`, `configs/` dùng chung, `pyproject.toml` gốc, `uv.lock`, workflow CI) thì dừng lại, báo người làm story, và đề xuất một PR riêng cho chủ sở hữu file đó (07 mục 3.2).
4. Làm **từng nhiệm vụ con** theo số trong story (1.1, 1.2, 2.1…). Mỗi nhiệm vụ con xong là một commit, trong cùng commit đó đánh dấu `[x]` cho nhiệm vụ con trong file story.
5. Không đánh dấu xong khi chưa có bằng chứng: test chạy qua, output lệnh, hoặc file số đo. Ghi bằng chứng vào thân commit.

## Git

- Nhánh: `<story-id>-<mô-tả-ngắn>`, ví dụ `S1-01-repo-skeleton`, `DA-03-teleop-pipeline`. Tạo từ `origin/master` mới nhất.
- Worktree: `git worktree add ../denso-S1-01 -b S1-01-repo-skeleton origin/master`.
- Commit: dòng đầu `<story-id>/<nhiệm vụ con>: <việc đã làm, tiếng Anh, thể mệnh lệnh>`, ví dụ `S1-01/2.1: Add fw --version with git SHA`. Thân commit ghi AC liên quan, bằng chứng, và dòng cuối `Time-spent: <giờ>h` (giờ tập trung thực của nhiệm vụ con, ví dụ `Time-spent: 1.5h`). Khi viết commit hộ người dùng, hỏi họ số giờ thay vì tự đoán.
- Việc ngoài story dùng nhánh `docs-…`, `chore-…` hoặc `hotfix-…`. Nhánh `docs-…` chỉ được sửa tài liệu và website.
- Trước khi mở PR, chạy `python3 scripts/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"`; workflow `pr-guard` chạy lại đúng kiểm tra này và chặn PR nếu sai (08 mục 3, rule R6).
- Mỗi người commit bằng tài khoản git của chính mình. Không push thẳng lên `master`; luôn qua PR. Hiếu là người duyệt và merge duy nhất; không tạo nhánh từ nhánh chưa merge, dùng bản giả và file mẫu trong lúc chờ.
- Trước khi mở PR: `git fetch origin && git rebase origin/master`, chạy lại kiểm tra. Không force-push nhánh của người khác.
- Không commit: dữ liệu (`fwdata/`), checkpoint (`*.ckpt`, `*.safetensors`, `*.pt`), PDF trong `docs/references/papers/`, file `.env`, khóa API.

## Bất biến kiến trúc (không được phá)

- Package lõi `flywheel` không import `simple`, `psi0`, `lerobot`, `torch`, `isaacsim`, `mujoco` hay package adapter. Mọi thứ cụ thể đi qua 6 Protocol (03 mục 5.2).
- Từ 25/10/2026 (03 mục 7.3): ba làn `flywheel.data`, `flywheel.eval`, `flywheel.loop` không import lẫn nhau và không import adapter hay runtime; chỉ dùng nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`). Dữ liệu giữa hai làn là artifact có schema trong `flywheel.contracts`; cần trường mới thì dừng lại, báo người làm story và đề xuất PR hợp đồng cho Hiếu, không thêm trường tạm trong code làn. Chỉ `flywheel.cli` được import cả làn và adapter.
- Code của làn phải chạy được trên CPU với bộ giả của `flywheel.testkit`; job GPU chỉ Hiếu chạy, từ RunPlan.
- Bản ghi catalog và sổ chi phí là append-only; không xóa, chỉ đánh dấu kèm lý do.
- Holdout nằm trong `vault/`, chỉ module `gate` được đọc.
- Dữ liệu `restricted` hoặc `internal` (mọi dữ liệu DENSO) **không bao giờ** gửi tới API hosted bên ngoài, kể cả Colab; chỉ NIM tự host. Dữ liệu của demo (psi-data, sim G1) là `public` (design mục 8.4).
- Bản sao có lỗi cấy (`injected_defect`) không bao giờ vào release train; đáp án `DefectManifest` chỉ bộ chấm đọc.
- Video egocentric phải qua bước che danh tính trước mọi bước xử lý khác.
- Mọi job sinh `LedgerEntry`. Ước tính và thực đo là hai trường riêng.

## Ngôn ngữ và văn phong

- Tài liệu trong `docs/` viết tiếng Việt; quy ước riêng ở `docs/CLAUDE.md`.
- Mã, tên biến, comment trong mã, thông điệp commit: tiếng Anh.
- Số liệu chưa đo ghi là giả định hoặc ước lượng; không viết như kết quả.

## Kiểm tra trước khi báo xong

- Mã (sau S1-01): `uv run ruff check`, `uv run mypy`, `uv run pytest`, import-linter. Lệnh chính xác ghi trong `packages/flywheel/README.md`; sau PR `chore-restructure` (07 mục 3.6) mọi package đều được quét và lệnh ghi trong README gốc của workspace.
- Tài liệu: `python3 scripts/check_links.py` (liên kết nội bộ).
- Website: `python3 website/build.py` rồi `python3 website/verify.py`. `node website/test.js` cần Node; máy không có Node thì để CI chạy.

## Không làm

- Không sửa spec, 03 hay design mà không có quyết định của Product Owner; khi sửa phải thêm dòng change log.
- Không đổi tên giả thuyết, mã story hay ID đã dùng.
- Không thêm dịch vụ (DB server, MLflow, Streamlit, Kubernetes) ở L0 (03 mục 2.4).
- Không chạy holdout ngoài lệnh `fw holdout run` của `gate`.
