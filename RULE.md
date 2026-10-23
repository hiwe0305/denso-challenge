# RULE.md · Luật chơi và công việc của đội

Đọc file này trước khi bắt đầu. Đọc hết mất khoảng 10 phút. Chi tiết nằm ở các tài liệu được trỏ tới; file này chỉ giữ những gì cần nhớ hằng ngày.

## 1. Dự án trong 3 câu

1. Đội ilovephysicalintelligence làm **Humanoid Data Flywheel** cho DENSO Factory Hacks: khi policy robot hỏng trong mô phỏng, hệ thống kiểm lỗi hệ thống trước, rồi chọn dữ liệu cần thu theo chi phí thật (thuật toán **Failure → Data**).
2. Model là Ψ₀ (dùng lại checkpoint của tác giả, fine-tune). Robot chính là **mobile manipulator của DENSO** trong Isaac Sim, task lấy linh kiện từ khay đặt vào máy; **G1 trong SIMPLE** là bàn thử cho các giả thuyết HS, HT, HD.
3. Trạng thái 23/10/2026: thiết kế đã duyệt, chưa có code. Sprint 1 bắt đầu thứ Hai 26/10/2026.

Muốn hiểu sâu: [spec v10.2](docs/spec-v10-failure-to-data.md), [design 23/10/2026](docs/superpowers/specs/2026-10-23-data-pipeline-and-failure-eval-design.md), [03 · Kiến trúc](docs/product/03-architecture.md).

## 2. Công việc của từng người

Giờ là ước lượng (04 mục 4.7 cộng phần DA ở 07 mục 2.3). Ai cũng đang vượt mức kế hoạch 70%; nếu trễ thì chuyển phần trễ sang API trước khi cắt việc (mục 5, R5).

### Dương Đình Hiếu · Trưởng nhóm, Product Owner, Ψ₀

- **Việc trưởng nhóm:** đầu mối DENSO, BTC, mentor; chọn checkpoint gốc (Q0), D\*, ρ; duyệt kế hoạch vòng C; ký cổng G0–G6; rà claim và pitch.
- **Story:** S1-03 tái tạo đánh giá Ψ₀ · S2 TrainerAdapter Ψ₀ · S3 đường cong E1, D\*, power analysis · S4 train nhánh A, A₀.₇, B.
- **Pha A (robot DENSO):** DA-05 NimClient và định tuyến dữ liệu · DA-07 log train theo nhóm action · DA-09 probe P1–P4 · **DA-14 gửi DENSO danh sách 21 mục, tuần 1**.
- Sở hữu: `training/`, phần trainer và probe của `flywheel-psi0/`, `flywheel-nim/`, `configs/runplans/`, tài liệu, website. Tổng khoảng 205 giờ.

### Trần Ngọc Hưng · Simulation lead

- **Story:** S1-02 môi trường SIMPLE · S1-05 planner · **S1-11 bộ điều khiển V3, hạn ngày 5 (30/10)** · S2 `SimpleSimulator`, TaskDefinition G1, tuyến generator · S3 khôi phục trạng thái · S4 correction, B-fail · S5–S6 cấy lỗi, điều phối HD, holdout, video demo.
- **Pha A:** DA-06 Cosmos Transfer (tầng S3) · **DA-10 robot thay thế giống ≥ 95%** · **DA-11 cảnh trạm và `DensoIsaacSim`**.
- Sở hữu: `flywheel-simple/`, `flywheel-isaac/`, `docker/`, `configs/embodiments/`, generator của `flywheel-nim/`, `scripts/g0/`, `docs/g0/`. Tổng khoảng 260 giờ, cao nhất đội.

### Trần Trịnh Hoàng Châu · Scorer, ACT/DP, vận hành Ψ₀

- **Story:** S1-04 chi phí fine-tune · S1-06 khôi phục trạng thái · S1-09 tín hiệu từng bước · S2 `Psi0Policy`, khung và hiệu chỉnh scorer · S3 ACT/DP, vector điều kiện, kNN · S4 phép kiểm cần rollout · S5–S6 C cuối, khóa holdout, F-ACT, B-fail của ACT.
- **Pha A:** DA-12 `DensoTrayToMachine` (6 bước, 10 kiểu lỗi).
- Sở hữu: `scorer/`, `flywheel-tasks/`, `flywheel-lerobot/`, phần policy của `flywheel-psi0/`, `configs/tasks/`. Tổng khoảng 201 giờ. Châu dự phòng cho Hiếu (Ψ₀) và Hưng.

### Nguyễn Thăng Long · Tech lead lõi

- **Story:** **S1-01 khung repo, CLI, CI (chặn S1-08, S1-10)** · S1-08 khung lõi trên adapter giả · S2 chia tập, runner, release · S3 RunPlan, chẩn đoán, kiểm hệ thống · S4 chọn can thiệp, `fw review` · S5 vòng C · S6 báo cáo.
- **Pha A:** DA-01 định dạng episode chung · **DA-04 pipeline video egocentric** · DA-13 quy lỗi về stage.
- Sở hữu: `contracts/`, `store/`, `catalog/`, `runner/`, `scenarios/`, `diagnosis/`, `decide/`, `acquisition/`, `reports/`, `cli/`, `pyproject.toml` gốc, `uv.lock`, CI, `scripts/` (trừ `scripts/g0/`). Tổng khoảng 248 giờ. **Mọi thay đổi `contracts/` đi qua Long.**

### Dương Tiến Thông · Scrum Master, dữ liệu và đo lường

- **Việc SM:** bảng công việc, check-in, bản tin tuần, viết file story (kể cả mục "Phạm vi file"), sổ can thiệp ở 08.
- **Story:** S1-07 phân tích psi-data · S1-10 mô hình dữ liệu · S2 nhập psi-data, QA, sổ chi phí · S3 cổng dev, bảng quyết định, backup · S4 N_B, evidence card · S5 công cụ HD · S6 thống kê, SOP.
- **Pha A:** DA-02 export LeRobot · DA-03 pipeline teleop · DA-08 phát hiện lỗi train.
- Sở hữu: `qa/`, `ledger/`, `gate/`, `flywheel-ingest/teleop/`, `export/`, `configs/thresholds/`, `configs/pricebook/`, `ops/`, `docs/product/stories/`. Tổng khoảng 241 giờ.

Bảng đầy đủ: sở hữu đường dẫn ở [07 mục 2.1](docs/product/07-team-workflow.md), story Pha A ở [07 mục 2.2](docs/product/07-team-workflow.md), sprint ở [04 mục 4](docs/product/04-delivery-plan.md), RACI ở [04 mục 3.3](docs/product/04-delivery-plan.md).

## 3. Một ngày làm việc

| Giờ | Việc |
|---|---|
| 9:00 | Bot đăng báo cáo ngày vào issue **"Báo cáo ngày"**; trang **Tiến độ** trên website cập nhật |
| Trước 10:00 | Trả lời dưới báo cáo 3 dòng: **Xong**, **Tiếp theo**, **Bị chặn** |
| Trong ngày | Làm story; xử lý rule có tên mình trong báo cáo |
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
   python3 scripts/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"
   ```

7. **Mở PR** tiêu đề `[DA-03] ...`, điền template (nhiệm vụ con, bằng chứng cho từng AC). PR nên ≤ 400 dòng.
8. **Review:** chủ sở hữu đường dẫn và người dự phòng duyệt. Merge bằng **Rebase and merge**, không squash.
9. **Dọn:** `git worktree remove ../denso-DA-03 && git branch -d DA-03-teleop-pipeline`.

Việc ngoài story dùng nhánh `docs-…` (chỉ sửa tài liệu và website), `chore-…` hoặc `hotfix-…`.

## 5. RULE

### 5.1 Rule kiểm soát theo ngày

Máy phát hiện (pr-guard hoặc báo cáo ngày); người làm theo cột "Làm gì". Chi tiết và ngưỡng ở [08](docs/product/08-daily-control.md).

| # | Khi nào | Làm gì |
|---|---|---|
| R1 | CI trên `master` đỏ | Ngừng merge; người gây lỗi sửa trong 4 giờ hoặc revert |
| R2 | PR chờ review quá 1 ngày làm việc | Người review dự phòng nhận; quá 2 ngày thì nêu ở check-in |
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
| DENSO, BTC, mentor, Ψ₀ (checkpoint, cấu hình train), quyết định phạm vi | Hiếu |
| SIMPLE, Isaac Sim, robot thay thế, generator, holdout | Hưng |
| Scorer, TaskDefinition, ACT, Diffusion Policy, vận hành Ψ₀ trên A100 | Châu |
| Lõi `flywheel`, `contracts`, CI, cấu trúc repo | Long |
| Story, bảng công việc, QA dữ liệu, sổ chi phí, thống kê, rule ở 08 | Thông |

## 8. Lệnh hay dùng

| Việc | Lệnh |
|---|---|
| Tiến độ mọi story | `python3 scripts/progress.py` |
| Báo cáo ngày tại máy | `python3 scripts/daily_report.py` |
| Kiểm nhánh trước PR | `python3 scripts/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"` |
| Kiểm liên kết tài liệu | `python3 scripts/check_links.py` |
| Xem website | `bash start-website.sh` |

## 9. Tài liệu để đọc tiếp

| Muốn biết | Đọc |
|---|---|
| Quy tắc cho phiên Claude | [CLAUDE.md](CLAUDE.md) |
| Chia việc, sở hữu đường dẫn, quy trình git | [07](docs/product/07-team-workflow.md) |
| Rule theo ngày, chỉ số, sổ can thiệp | [08](docs/product/08-daily-control.md) |
| Sprint, Definition of Done | [04](docs/product/04-delivery-plan.md) |
| Yêu cầu và story theo epic | [02 · PRD](docs/product/02-prd.md) |
| Thuật toán và giả thuyết | [Spec v10.2](docs/spec-v10-failure-to-data.md) |
| Pipeline dữ liệu, robot DENSO, bảng lỗi | [Design 23/10/2026](docs/superpowers/specs/2026-10-23-data-pipeline-and-failure-eval-design.md) |
