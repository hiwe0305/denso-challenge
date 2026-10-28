# RULE.md · Luật chơi và công việc của đội

Đọc file này trước khi bắt đầu. Đọc hết mất khoảng 10 phút. Chi tiết nằm ở các tài liệu được trỏ tới; file này chỉ giữ những gì cần nhớ hằng ngày.

## 1. Dự án trong 3 câu

1. Đội ilovephysicalintelligence làm **Humanoid Data Flywheel** cho DENSO Factory Hacks: khi policy robot hỏng trong mô phỏng, hệ thống kiểm lỗi hệ thống trước, rồi chọn dữ liệu cần thu theo chi phí thật (thuật toán **Failure → Data**).
2. Model là Ψ₀ (dùng lại checkpoint và code train của tác giả). Từ 27/10/2026 robot là **Unitree G1 trong SIMPLE**, đúng robot và model của paper; task chính là **task hai bàn**: gắp vật ở bàn này, đi sang bàn kia, đặt lên. Thu và sinh dữ liệu chạy MuJoCo thuần, Isaac Sim chỉ render. Robot DENSO đã bỏ khỏi phạm vi.
3. Trạng thái 27/10/2026: hướng G1 + Ψ₀ đã duyệt ([design 27/10/2026](docs/superpowers/specs/2026-10-27-g1-psi0-demo-design.md), design hiện hành duy nhất); S1-01 đã merge; Sprint 1 bắt đầu thứ Hai 26/10/2026; **demo ngày 17/11/2026**. **Hiếu là người duyệt và merge duy nhất vào `master`.**

Muốn hiểu sâu: [spec v10.4](docs/spec-v10-failure-to-data.md), [design 27/10/2026](docs/superpowers/specs/2026-10-27-g1-psi0-demo-design.md), [03 · Kiến trúc](docs/product/03-architecture.md).

## 2. Công việc của từng người

**Phân công ngày 27/10/2026** (07 mục 2.0): bốn người làm toàn bộ **data flywheel** (nhân và ba làn, chạy được trên CPU với bộ giả); Hiếu làm **phần còn lại** (SIMPLE, Ψ₀, GPU, thí nghiệm) và duyệt, merge mọi PR. Mỗi người chỉ sửa đường dẫn của mình (07 mục 2.1); dữ liệu giữa hai người chỉ đi qua artifact có schema trong `flywheel.contracts`; không import code bên trong phần của người khác. Giờ là ước lượng ở 07 mục 2.3.

### Nguyễn Thăng Long · Nhân và Vòng quyết định

- **Một lần:** merge S1-08, mở **PR `chore-restructure`** ngày 28/10, merge 29/10 (07 mục 3.6); **DA-25 schema và file mẫu của mọi artifact trước 30/10**.
- **Nhân:** `flywheel-contracts`, `flywheel-store`, `flywheel-testkit`, `flywheel-cli`, `tests/e2e/`; S1-10 mô hình dữ liệu và kho; DA-01 định dạng episode. Mọi thay đổi schema do Hiếu duyệt.
- **Làn Vòng (`flywheel-loop`):** RunPlan và `fw plan freeze` · runner, DA-23 eval bất đồng bộ · sổ chi phí · decide, `fw review` · acquisition · gate, cổng dev, A/A test, tỉ lệ sửa được, holdout · báo cáo, thống kê · công cụ HD · backup · **DA-28 kịch bản demo 17/11**.
- Sở hữu: nhân, `flywheel-loop`, `configs/kernel/`, `configs/loop/`, công cụ RunPlan, `pyproject.toml` gốc, `uv.lock`, `.github/`, `scripts/repo/`, `ops/`, `scripts/demo/`, `docs/demo/`.

### Dương Tiến Thông · Scrum Master, Dữ liệu robot

- **Việc SM:** bảng công việc, check-in, bản tin tuần, viết file story (kể cả "Phạm vi file"), sổ can thiệp ở 08; **viết file story DA-01, DA-02, DA-03, DA-08, DA-13 ngày 28/10**.
- **Dữ liệu robot (`flywheel-data`, trừ phần egocentric):** S1-07 phân tích psi-data task hai bàn · DA-03 pipeline teleop và synthetic qua 6 tầng, báo cáo dataset · DA-17 phát lại action · release và chia tập · DA-02, DA-21 export LeRobot v2.1, v3 · DA-27 cấy lỗi · S6 SOP.
- Sở hữu: `flywheel-data` trừ `ingest/egocentric/`, `annotate/deid/`, `qa/egocentric.py`, `export/egodex.py`; `configs/data/` trừ `egocentric.yaml`; `docs/product/stories/`. Giữ `pyproject.toml`, `api.py`, `cli.py` của `flywheel-data`.

### Trần Ngọc Hưng · Dữ liệu egocentric và Agent QA/QC

- **Egocentric (trong `flywheel-data`):** DA-04 pipeline egocentric (che danh tính, cắt đoạn, pose E-A và E-B, QA) trên mẫu EgoDex rồi video tự quay · DA-18 xuất định dạng stage 1 của Ψ₀ · vòng thử model gán nhãn (RoboBrain 2.5-4B, Molmo2-4B).
- **Agent QA/QC (trong `flywheel-eval`):** DA-20 Agent QA/QC với Nemotron 3.5 Bolt E4B · DA-31 bộ chấm lỗi cấy.
- Không cần chạy SIMPLE: code trên bộ giả và file mẫu; model chạy thật qua job trên máy 3060.
- Sở hữu: `flywheel-data/.../ingest/egocentric/`, `annotate/deid/`, `qa/egocentric.py`, `export/egodex.py`; `flywheel-eval/.../agentqa/`; `configs/data/egocentric.yaml`, `configs/eval/agentqa/`. Xuất API và lệnh `fw` qua module và entry point riêng, không sửa tệp chung của chủ package.

### Trần Trịnh Hoàng Châu · Đánh giá

- **Làn Đánh giá (`flywheel-eval`, trừ `agentqa/`):** tập điều kiện, chia tập, guard gần trùng, vector điều kiện, kNN · TaskDefinition và scorer của task hai bàn, hiệu chỉnh scorer · chuỗi chẩn đoán, kiểm hệ thống · DA-08 phát hiện lỗi train và offline · DA-13 quy lỗi về stage · evidence card · code các phép kiểm cần rollout (Hiếu chạy).
- Sở hữu: `flywheel-eval` trừ `agentqa/`; `configs/eval/` trừ `agentqa/`. Giữ `pyproject.toml`, `api.py`, `cli.py` của `flywheel-eval`.

### Dương Đình Hiếu · Trưởng nhóm, phần còn lại, duyệt cuối

- **Việc trưởng nhóm:** đầu mối DENSO, BTC, mentor; chọn checkpoint gốc (Q0), D\*, ρ; duyệt kế hoạch vòng C; ký cổng G0–G6; rà claim và pitch; **duyệt và merge mọi PR**, kể cả PR schema; thảo luận tổng kết cuối ngày lúc 21:30.
- **SIMPLE và sinh dữ liệu:** S1-02 · S1-05 sinh tự động S1 · S1-06 · S1-09 · S1-11 (V3) · DA-16 teleop bàn phím · DA-29 synthetic S2 · story 3.1a `SimpleSim`.
- **Ψ₀ và GPU:** S1-03 · S1-04 · DA-19 code train, log, Colab, client RTC · DA-09 probe · DA-26 thí nghiệm HE · DA-30 stage 1 trên egocentric · `Psi0Policy`, ACT, DP · mọi job GPU.
- Sở hữu: `flywheel-simple`, `flywheel-psi0`, `flywheel-lerobot`, `flywheel-nim`, `configs/models/`, `configs/embodiments/`, `configs/sim/`, RunPlan, `docker/`, `compose.yaml`, `scripts/g0/`, `docs/g0/`, tài liệu, website. **Tải cao nhất đội** (07 mục 2.3); nếu Hưng có máy chạy SIMPLE, chuyển S1-06, S1-09, DA-16 cho Hưng trước.

Bảng đầy đủ: sở hữu đường dẫn ở [07 mục 2.1](docs/product/07-team-workflow.md), story DA ở [07 mục 2.2](docs/product/07-team-workflow.md), sprint ở [04 mục 4](docs/product/04-delivery-plan.md), RACI ở [04 mục 3.3](docs/product/04-delivery-plan.md).

## 3. Một ngày làm việc

| Giờ | Việc |
|---|---|
| 9:00 | Bot đăng báo cáo ngày vào issue **"Báo cáo ngày"**; trang **Tiến độ** trên website cập nhật |
| Trước 10:00 | Trả lời dưới báo cáo 3 dòng: **Xong**, **Tiếp theo**, **Bị chặn** |
| Trong ngày | Làm story; xử lý rule có tên mình trong báo cáo |
| 10:00, 14:00, 18:00 | Tracking tự động trên máy của Hiếu: PR chờ duyệt, ai bị chặn, vi phạm rule (08 mục 5) |
| 21:30 | Tổng kết cuối ngày; Hiếu và Claude thảo luận, chốt thứ tự duyệt PR cho hôm sau |
| Thứ Sáu | Thông tổng hợp tuần: k, top nguyên nhân lỗi, can thiệp mới |

## 4. Làm một story từ đầu tới cuối

1. **Nhận story.** Mở file story trong `docs/product/stories/`. Kiểm có đủ "Tiêu chí chấp nhận", "Nhiệm vụ" và "Phạm vi file". Thiếu "Phạm vi file" thì báo Thông trước khi làm.
2. **Tạo nhánh và worktree riêng:**

   ```bash
   git fetch origin && git worktree add ../denso-DA-03 -b DA-03-teleop-pipeline origin/master
   ```

3. **Mở một phiên Claude mới trong worktree đó** và dán:

   ```text
   Đọc CLAUDE.md và docs/product/stories/DA-03-*.md. Chỉ sửa file trong "Phạm vi file" của story.
   Làm nhiệm vụ con 1. Xong thì chạy kiểm tra, cho tôi xem diff và bằng chứng, rồi commit theo quy ước
   "DA-03/1: ..." và đánh dấu [x] trong file story. Dừng lại chờ tôi trước khi sang nhiệm vụ con kế.
   ```

4. **Mỗi nhiệm vụ con là một commit**, dạng:

   ```text
   DA-03/2: Resample teleop state to control rate

   AC 2: timestamps aligned within tau_sync on 40 episodes (pytest tests/ingest/test_sync.py).

   Time-spent: 2.5h
   ```

   `Time-spent` là giờ tập trung thực của bạn. Đây là số duy nhất cần nhập tay; nó dùng để tính hệ số k của đội.
5. **Mỗi ngày rebase một lần:** `git fetch origin && git rebase origin/master`.
6. **Trước khi mở PR, tự kiểm:**

   ```bash
   python3 scripts/repo/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"
   ```

7. **Mở PR** tiêu đề `[DA-03] ...`, điền template (nhiệm vụ con, bằng chứng cho từng AC). PR nên ≤ 400 dòng.
8. **Review:** **Hiếu duyệt và merge, là người duy nhất.** Chủ sở hữu đường dẫn bình luận, không chặn merge. PR phải xanh ở `core` và `guard` trước khi xin duyệt. Merge bằng **Rebase and merge**, không squash. PR đã xanh mà vẫn hiện **BLOCKED** là bình thường: ruleset "Only Hiếu merges into master" chỉ cho vai Admin cập nhật `master`, nên Hiếu merge bằng `gh pr merge <số> --admin --rebase` sau khi đã xem diff và CI, gom vào các khung 10:00, 14:00, 18:00 và 21:30. Trong lúc chờ duyệt, làm tiếp nhiệm vụ con khác trên bản giả và file mẫu; không tạo nhánh mới từ nhánh chưa merge.
9. **Dọn:** `git worktree remove ../denso-DA-03 && git branch -d DA-03-teleop-pipeline`.

Việc ngoài story dùng nhánh `docs-…` (chỉ sửa tài liệu và website), `chore-…` hoặc `hotfix-…`.

## 5. RULE

### 5.1 Rule kiểm soát theo ngày

Máy phát hiện (pr-guard hoặc báo cáo ngày); người làm theo cột "Làm gì". Chi tiết và ngưỡng ở [08](docs/product/08-daily-control.md).

| # | Khi nào | Làm gì |
|---|---|---|
| R1 | CI trên `master` đỏ | Ngừng merge; người gây lỗi sửa trong 4 giờ hoặc revert |
| R2 | PR chờ review quá 1 ngày làm việc | Hiếu duyệt hoặc ghi lý do chờ dưới PR; quá 2 ngày thì nêu ở check-in |
| R3 | Bạn có quá 2 PR đang mở | Không mở story mới |
| R4 | Story đã bắt đầu, 2 ngày làm việc không có commit | Ghi vào issue của story đang bị chặn ở đâu |
| R5 | k của bạn (7 ngày) > 1,3 | Hiếu và Thông xét chuyển phần trễ sang API, hoặc ước lại story |
| R6 | Sai tên nhánh, sai định dạng commit, thiếu `Time-spent`, sửa file ngoài phạm vi | pr-guard chặn PR; sửa rồi push lại |
| R7 | Lỗi `severity:high` (rò holdout, gửi dữ liệu DENSO ra ngoài, sai kết luận, mất dữ liệu) | Đổi thành `type:incident`; postmortem 1 trang trong 2 ngày |
| R8 | Cùng một nguyên nhân lỗi ≥ 3 lần trong 7 ngày | Thêm một can thiệp (rule, test, sửa CLAUDE.md), ghi vào sổ can thiệp |
| R9 | PR > 400 dòng | Được gắn `size:large`; nên tách story |

### 5.2 Không bao giờ được phá

1. Lõi `flywheel` không import `simple`, `psi0`, `lerobot`, `torch`, `isaacsim`, `mujoco` hay package adapter.
2. **Dữ liệu DENSO không bao giờ được gửi tới API hosted bên ngoài**; chỉ dùng NIM tự host.
3. Video egocentric phải được che danh tính trước mọi bước xử lý khác.
4. Holdout nằm trong `vault/`, chỉ `gate` được đọc; chỉ chạy bằng `fw holdout run`.
5. Catalog và sổ chi phí chỉ ghi thêm; không xóa, chỉ đánh dấu kèm lý do.
6. Mọi job tiêu GPU hoặc giờ người đều có mục sổ chi phí.
7. Không commit dữ liệu, checkpoint, PDF paper, file `.env`, khóa API.
8. Không push thẳng lên `master`; luôn qua PR.

### 5.3 Phối hợp

- **Cần sửa file của người khác:** khai đường dẫn đó trong "Phạm vi file" của story và để chủ sở hữu review.
- **Cần đổi file dùng chung** (`contracts/`, schema trong `configs/`, `pyproject.toml` gốc, `uv.lock`, CI): mở issue "Contract change: …", chủ sở hữu làm một PR nhỏ riêng, merge trước rồi bạn mới rebase và làm tiếp.
- **Tài liệu mâu thuẫn:** spec và design thắng PRD; 03 thắng mọi mô tả cấu trúc mã. Báo Hiếu, không tự chọn.
- **Số liệu chưa đo** ghi là ước lượng hoặc giả định, không viết như kết quả.

## 6. Báo lỗi

Mở issue bằng template **"Lỗi"**. Gắn đúng một label mức độ và, khi đã rõ, một label nguyên nhân:

- Mức độ: `severity:high`, `severity:medium`, `severity:low`.
- Nguyên nhân: `cause:spec-unclear`, `cause:contract`, `cause:env-gpu`, `cause:ai-generated`, `cause:review-miss`, `cause:test-gap`, `cause:data`, `cause:denso-wait`.

Label nguyên nhân quan trọng hơn số lượng lỗi: nhờ nó đội biết nên sửa quy trình ở đâu (R8).

## 7. Hỏi ai

| Chủ đề | Hỏi |
|---|---|
| DENSO, BTC, mentor, quyết định phạm vi, duyệt hợp đồng; Ψ₀, ACT, DP, SIMPLE ở chế độ MuJoCo, teleop bàn phím, sinh tự động, Isaac Sim render, job GPU, Colab | Hiếu |
| Schema và file mẫu giữa các làn (`flywheel-contracts`, `flywheel-testkit`), RunPlan, runner, decide, cổng dev, holdout, sổ chi phí, báo cáo, CI, cấu trúc repo, kịch bản demo | Long |
| Story, bảng công việc, ingest, QA dữ liệu teleop và synthetic, phát lại để kiểm, LeRobot v2.1/v3, cấy lỗi, rule ở 08 | Thông |
| Egocentric (che danh tính, pose, export stage 1), Agent QA/QC, bộ chấm lỗi cấy | Hưng |
| Task và scorer, tập điều kiện, chẩn đoán, evidence card | Châu |

## 8. Lệnh hay dùng

| Việc | Lệnh |
|---|---|
| Tiến độ mọi story | `python3 scripts/repo/progress.py` |
| Báo cáo ngày tại máy | `python3 scripts/repo/daily_report.py` |
| Kiểm nhánh trước PR | `python3 scripts/repo/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"` |
| Kiểm liên kết tài liệu | `python3 scripts/repo/check_links.py` |
| Xem website | `bash start-website.sh` |

## 9. Tài liệu để đọc tiếp

| Muốn biết | Đọc |
|---|---|
| Quy tắc cho phiên Claude | [CLAUDE.md](CLAUDE.md) |
| Chia việc, sở hữu đường dẫn, quy trình git | [07](docs/product/07-team-workflow.md) |
| Rule theo ngày, chỉ số, sổ can thiệp | [08](docs/product/08-daily-control.md) |
| Sprint, Definition of Done | [04](docs/product/04-delivery-plan.md) |
| Yêu cầu và story theo epic | [02 · PRD](docs/product/02-prd.md) |
| Thuật toán và giả thuyết | [Spec v10.4](docs/spec-v10-failure-to-data.md) |
| Task hai bàn, dữ liệu, HE, Agent QA/QC, demo 17/11 | [Design 27/10/2026](docs/superpowers/specs/2026-10-27-g1-psi0-demo-design.md) |
