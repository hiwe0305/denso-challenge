# CLAUDE.md · Humanoid Data Flywheel

Hướng dẫn cho Claude Code (và người) làm việc trong repo này. Đội 5 người cùng dùng Claude; mục tiêu của file là để mọi phiên Claude làm cùng một cách và không giẫm lên việc của nhau. Bản tóm tắt cho người (công việc từng người, rule, quy trình một story) ở [RULE.md](RULE.md).

## Dự án

Đề xuất của đội ilovephysicalintelligence cho thử thách DENSO Factory Hacks. Lõi là **thuật toán Failure → Data**: khi policy robot hỏng trong mô phỏng, kiểm lỗi hệ thống trước, rồi chọn dữ liệu cần thu theo chi phí thật, có đối chứng. Model là Ψ₀ (dùng lại checkpoint của tác giả). Robot chính là mobile manipulator của DENSO trong Isaac Sim, task lấy linh kiện từ khay đặt vào máy; G1 trong SIMPLE là bàn thử.

Trạng thái: thiết kế đã duyệt, **chưa có code**. Package `packages/` sẽ được tạo ở story S1-01.

## Đọc gì trước

| Khi làm | Đọc |
|---|---|
| Bất kỳ việc gì | File story của mình trong `docs/product/stories/`, rồi [07 · Chia việc và quy trình git](docs/product/07-team-workflow.md) |
| Thuật toán, giả thuyết, thí nghiệm | [Spec v10.2](docs/spec-v10-failure-to-data.md) |
| Module lõi, adapter, schema, cây thư mục | [03 · Kiến trúc](docs/product/03-architecture.md) |
| Pipeline dữ liệu, synthetic, NIM, probe theo stage, bảng lỗi, robot DENSO | [Design 23/10/2026](docs/superpowers/specs/2026-10-23-data-pipeline-and-failure-eval-design.md) |
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
- Mỗi người commit bằng tài khoản git của chính mình. Không push thẳng lên `master`; luôn qua PR.
- Trước khi mở PR: `git fetch origin && git rebase origin/master`, chạy lại kiểm tra. Không force-push nhánh của người khác.
- Không commit: dữ liệu (`fwdata/`), checkpoint (`*.ckpt`, `*.safetensors`, `*.pt`), PDF trong `docs/references/papers/`, file `.env`, khóa API.

## Bất biến kiến trúc (không được phá)

- Package lõi `flywheel` không import `simple`, `psi0`, `lerobot`, `torch`, `isaacsim`, `mujoco` hay package adapter. Mọi thứ cụ thể đi qua 6 Protocol (03 mục 5.2).
- Bản ghi catalog và sổ chi phí là append-only; không xóa, chỉ đánh dấu kèm lý do.
- Holdout nằm trong `vault/`, chỉ module `gate` được đọc.
- Dữ liệu `restricted` hoặc `internal` (mọi dữ liệu DENSO) **không bao giờ** gửi tới API hosted bên ngoài; chỉ NIM tự host (design mục 5.4).
- Video egocentric phải qua bước che danh tính trước mọi bước xử lý khác.
- Mọi job sinh `LedgerEntry`. Ước tính và thực đo là hai trường riêng.

## Ngôn ngữ và văn phong

- Tài liệu trong `docs/` viết tiếng Việt; quy ước riêng ở `docs/CLAUDE.md`.
- Mã, tên biến, comment trong mã, thông điệp commit: tiếng Anh.
- Số liệu chưa đo ghi là giả định hoặc ước lượng; không viết như kết quả.

## Kiểm tra trước khi báo xong

- Mã (sau S1-01): `uv run ruff check`, `uv run mypy`, `uv run pytest`, import-linter. Lệnh chính xác ghi trong `packages/flywheel/README.md`.
- Tài liệu: `python3 scripts/check_links.py` (liên kết nội bộ).
- Website: `python3 website/build.py` rồi `python3 website/verify.py`. `node website/test.js` cần Node; máy không có Node thì để CI chạy.

## Không làm

- Không sửa spec, 03 hay design mà không có quyết định của Product Owner; khi sửa phải thêm dòng change log.
- Không đổi tên giả thuyết, mã story hay ID đã dùng.
- Không thêm dịch vụ (DB server, MLflow, Streamlit, Kubernetes) ở L0 (03 mục 2.4).
- Không chạy holdout ngoài lệnh `fw holdout run` của `gate`.
