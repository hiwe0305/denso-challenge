# 07 · Chia việc 5 người và quy trình git khi dùng Claude

_Ngày 23/10/2026. Vai trò BMAD: Scrum Master cộng Product Owner. Đầu vào: [04 · Kế hoạch](04-delivery-plan.md) mục 3 (vai, RACI), [design 23/10/2026](../superpowers/specs/2026-10-23-data-pipeline-and-failure-eval-design.md) mục 11 (Pha A). Bản 0.1 là [Đề xuất]; Hiếu và Thông chốt ở họp lập kế hoạch Sprint 1 ngày 26/10/2026._

| Ngày | Phiên bản | Thay đổi | Tác giả |
|---|---|---|---|
| 23/10/2026 | 0.1 | Bản đầu: bản đồ sở hữu đường dẫn, 14 story Pha A, quy trình git và Claude, cách theo dõi theo nhiệm vụ con | SM, PO |

## 1. Ba lớp chống "chèn code vào nhau"

Năm người cùng dùng Claude trên một repo thì xung đột đến từ ba chỗ: hai người sửa cùng file, ai đó đổi file dùng chung (schema, cấu hình, lock file) mà người khác đang dựa vào, và một phiên Claude sửa lan ra ngoài việc được giao. Ba lớp dưới đây chặn từng chỗ.

| Lớp | Cách làm | Chặn gì |
|---|---|---|
| 1 · Sở hữu đường dẫn | Mỗi thư mục có một chủ (mục 2.1), ghi trong `.github/CODEOWNERS`. Story khai "Phạm vi file"; Claude chỉ sửa trong phạm vi đó (CLAUDE.md gốc) | Hai người sửa cùng file |
| 2 · Contract trước | File dùng chung chỉ đổi qua PR nhỏ riêng của chủ sở hữu, merge trước việc dựa vào nó (mục 3.2) | Đổi schema làm vỡ việc người khác |
| 3 · Một story, một nhánh, một worktree, một phiên Claude | Mỗi người làm trong worktree riêng, rebase lên `master` hằng ngày, PR nhỏ (mục 3.3) | Phiên Claude sửa lan; nhánh sống lâu rồi xung đột lớn |

## 2. Chia việc

### 2.1 Bản đồ sở hữu đường dẫn

Theo RACI ở 04 mục 3.3: chủ sở hữu là người A hoặc R chính của thành phần. Người dự phòng theo 04 mục 3.1 là người review mặc định. Đường dẫn của package lấy từ 03 mục 7.1; package chưa tồn tại thì được tạo đúng tên này.

| Đường dẫn | Chủ | Review mặc định |
|---|---|---|
| `packages/flywheel/src/flywheel/contracts/`, `store/` | Long | Thông |
| `.../catalog/`, `runner/`, `scenarios/`, `diagnosis/`, `decide/`, `acquisition/`, `reports/` | Long | Thông |
| `.../qa/`, `ledger/`, `gate/` | Thông | Long |
| `.../scorer/` | Châu | Hưng |
| `.../training/` | Hiếu | Châu |
| `.../cli/`, `testing/` | Long | Thông |
| `packages/flywheel-fakes/` | Long | Thông |
| `packages/flywheel-tasks/` (G1 và `DensoTrayToMachine`) | Châu | Hưng |
| `packages/flywheel-simple/`, `docker/` | Hưng | Châu |
| `packages/flywheel-isaac/` (robot DENSO, robot thay thế, cảnh trạm) | Hưng | Châu |
| `packages/flywheel-psi0/` phần policy và RUNBOOK | Châu | Hiếu |
| `packages/flywheel-psi0/` phần trainer và probe | Hiếu | Châu |
| `packages/flywheel-lerobot/` | Châu | Hưng |
| `packages/flywheel-ingest/teleop/`, `export/` | Thông | Long |
| `packages/flywheel-ingest/egocentric/` | Long | Thông |
| `packages/flywheel-nim/` client và định tuyến | Hiếu | Long |
| `packages/flywheel-nim/generators/` (Cosmos Transfer, Predict) | Hưng | Hiếu |
| `configs/embodiments/` | Hưng | Châu |
| `configs/tasks/` | Châu | Hưng |
| `configs/splits/` | Long | Thông |
| `configs/thresholds/`, `configs/pricebook/`, `ops/` | Thông | Long |
| `configs/runplans/`, `configs/recipes/` | Hiếu | Châu |
| `pyproject.toml` gốc, `uv.lock`, `.github/workflows/`, `scripts/` | Long | Thông |
| `docs/spec-v10-failure-to-data.md`, `docs/product/00`–`07`, `docs/superpowers/` | Hiếu | Thông |
| `docs/product/stories/` | Thông | Hiếu |
| `website/`, `deliverables/` | Hiếu | Long |

Chủ sở hữu không có nghĩa là người duy nhất được sửa. Người khác sửa được khi story của họ khai đường dẫn đó trong "Phạm vi file" và chủ sở hữu review PR.

### 2.2 Story Pha A của design

Đặt mã `DA-xx` (Design, Pha A) cho tới khi SM gắn vào sprint. Các story này chạy song song với story S1–S6 ở 04 mục 4. Giờ là ước lượng chi tiết hơn bảng ở 04 mục 4.9; tổng khoảng 185–255 giờ, cao hơn khoảng 160–220 giờ đã ghi, nên SM cập nhật 04 mục 4.9 sau họp lập kế hoạch.

| Mã | Story | Chủ | Phạm vi file chính | Phụ thuộc | Giờ | Sprint |
|---|---|---|---|---|---|---|
| DA-01 | Định dạng episode chung, `action_layout`, trường mới của Episode | Long | `contracts/`, `configs/embodiments/` (schema) | S1-10 | 8–12 | S1 |
| DA-02 | Export LeRobot theo `action_layout`, `stats_psi0.json`, contract test bằng loader Ψ₀ | Thông | `flywheel-ingest/export/` | DA-01, 2.6 | 8–12 | S2 |
| DA-03 | Pipeline teleop trên psi-data: normalize, cắt đoạn, QA riêng nguồn | Thông | `flywheel-ingest/teleop/` | DA-01, 2.2 | 20–25 | S2 |
| DA-04 | Pipeline egocentric E-A và E-B trên mẫu EgoDex: che danh tính, cắt đoạn, pose tay và camera, định dạng H-RDT, QA | Long | `flywheel-ingest/egocentric/` | DA-01 | 25–35 | S2–S3 |
| DA-05 | `NimClient`, định tuyến theo `data_class`, Cosmos Reason tự host trên 5090 | Hiếu | `flywheel-nim/` (trừ `generators/`) | DA-01 | 12–15 | S2 |
| DA-06 | Tầng S3: Cosmos Transfer trên video sim G1, kiểm IoU với segmentation gốc | Hưng | `flywheel-nim/generators/` | DA-05, 3.1a | 15–20 | S3 |
| DA-07 | Log train theo nhóm action và theo vị trí trong chunk, checkpoint trung gian tự chạy P3 | Hiếu | `flywheel-psi0/` phần trainer | 4.2 | 10–14 | S2 |
| DA-08 | Bộ phát hiện lỗi F-TRAIN (T1–T8) và F-OFF (O1–O4) từ `metrics.jsonl`, đưa vào báo cáo | Thông | `gate/`, `reports/` (khai trong story) | DA-07 | 8–12 | S3 |
| DA-09 | Probe P1–P4 đóng băng có hash; chạy trên `pre.*`, `postpre.*` | Hiếu | `flywheel-psi0/` phần probe, `gate/` (khai) | S1-03 | 12–18 | S2–S3 |
| DA-10 | Robot thay thế tham số và lệnh `fw embodiment score` | Hưng | `flywheel-isaac/`, `configs/embodiments/` | S1-02 phần Isaac Sim | 25–35 | S1–S3 |
| DA-11 | Cảnh trạm khay → máy và `DensoIsaacSim` | Hưng | `flywheel-isaac/` | DA-10 | 15–25 | S3 |
| DA-12 | `DensoTrayToMachine`: 6 bước, 10 kiểu lỗi, scorer | Châu | `flywheel-tasks/`, `configs/tasks/` | DA-11, 3.3 | 15–20 | S3 |
| DA-13 | Bước 4b quy lỗi về stage và quy tắc F-SYS trong `diagnosis` | Long | `diagnosis/` | DA-09, 6.x | 8–10 | S4 |
| DA-14 | Gửi danh sách 21 mục cho DENSO, theo dõi trả lời, cập nhật design mục 9 | Hiếu | `docs/` | Không | 3 | S1 tuần 1 |

Việc chưa có chủ: cập nhật website và Pitch theo spec v10.2 (khoảng 10–15 giờ), cập nhật 00–02, 05, 06. Hiếu chọn người ở họp lập kế hoạch.

**Nhiệm vụ con gợi ý** (người làm story viết đủ vào file story, mỗi dòng là một commit):

- DA-01: 1 schema Episode thêm trường mới; 2 schema `action_layout` và mask; 3 `segments.parquet`; 4 test tính chất cho validate.
- DA-03: 1 bộ đọc psi-data sang bundle chung; 2 đồng bộ thời gian và nội suy; 3 cắt đoạn theo luật; 4 QA riêng nguồn; 5 chạy trên toàn bộ gói task chính, báo số pass, flag, reject.
- DA-04: 1 che danh tính và kiểm `deid_status`; 2 cắt đoạn (luật, gợi ý Cosmos Reason qua DA-05); 3 pose E-B đọc từ dữ liệu EgoDex; 4 pose E-A ước lượng từ RGB; 5 so độ lệch E-A với E-B trên cùng mẫu; 6 xuất định dạng H-RDT.
- DA-10: 1 file tham số và URDF sinh từ tham số; 2 nhập vào Isaac Sim; 3 bộ chấm giống (điều kiện bắt buộc, 6 điểm thành phần); 4 chấm so với hình vẽ, ghi Decision.
- DA-09: 1 bộ câu hỏi P1 có đáp án và hash; 2 P2 trên mẫu EgoDex; 3 P3 trên episode held-out; 4 P4 so checkpoint cha; 5 báo cáo theo checkpoint.

### 2.3 Tải thêm theo người

Lấy giữa khoảng ở bảng 2.2, cộng vào tải sau cắt mức 1–7 ở 04 mục 4.8.

| Người | Tải ở 04 mục 4.8 | Pha A thêm | Tổng | So với mức 70% ở H = 20 (146 giờ) |
|---|---|---|---|---|
| Hiếu | 163 | DA-05, DA-07, DA-09, DA-14: khoảng 42 | khoảng 205 | 140% |
| Hưng | 192 | DA-06, DA-10, DA-11: khoảng 68 | khoảng 260 | 178% |
| Châu | 183 | DA-12: khoảng 18 | khoảng 201 | 138% |
| Long | 199 | DA-01, DA-04, DA-13: khoảng 49 | khoảng 248 | 170% |
| Thông | 198 | DA-02, DA-03, DA-08: khoảng 43 | khoảng 241 | 165% |

Theo quyết định ngày 23/10/2026 (04 mục 4.9): giữ đủ phạm vi; đo k sau Sprint 1; vượt thì chuyển phần trễ sang API trước, rồi mới cắt. Hưng và Long tải cao nhất; story của hai người này là ứng viên đầu tiên cho việc chuyển sang API (ví dụ dùng TIAGo++ thay DA-10, model pose có sẵn cho DA-04).

## 3. Quy trình git khi dùng Claude

### 3.1 Phạm vi file của story

Mỗi story có mục "Phạm vi file": danh sách thư mục hoặc file được sửa. CLAUDE.md gốc yêu cầu Claude dừng lại khi cần sửa ngoài danh sách này. Người review kiểm `git diff --stat origin/master...` chỉ chạm các đường dẫn đã khai.

### 3.2 File dùng chung: contract trước

File dùng chung: `contracts/`, schema trong `configs/`, `pyproject.toml` gốc, `uv.lock`, `.github/workflows/`.

1. Người cần đổi mở issue "Contract change: …" mô tả trường cần thêm và lý do.
2. Chủ sở hữu (Long, hoặc người ở mục 2.1) làm một PR nhỏ chỉ đổi contract, kèm test; nhánh `<story-id>-contract`.
3. PR contract merge trước. Người cần dùng rebase lên `master` rồi làm tiếp.
4. Thêm phụ thuộc Python: người cần thêm sửa `pyproject.toml` của package mình; `uv.lock` chỉ được tạo lại bằng `uv lock` sau khi rebase, không sửa tay; xung đột ở `uv.lock` thì lấy bản của `master` rồi chạy lại `uv lock`.

### 3.3 Vòng đời một story

```text
Issue story (template) → nhánh và worktree → phiên Claude → commit theo nhiệm vụ con
→ rebase hằng ngày → PR (template) → review của chủ sở hữu → Rebase and merge → xóa nhánh, xóa worktree
```

Lệnh mẫu:

```bash
git fetch origin && git worktree add ../denso-DA-03 -b DA-03-teleop-pipeline origin/master
```

```bash
git fetch origin && git rebase origin/master
```

```bash
git worktree remove ../denso-DA-03 && git branch -d DA-03-teleop-pipeline
```

Câu mở phiên Claude gợi ý, dán vào phiên mới mở trong worktree:

```text
Đọc CLAUDE.md và docs/product/stories/DA-03-*.md. Chỉ sửa file trong "Phạm vi file" của story.
Làm nhiệm vụ con 1. Xong thì chạy kiểm tra, cho tôi xem diff và bằng chứng, rồi commit theo quy ước
"DA-03/1: ..." và đánh dấu [x] trong file story. Dừng lại chờ tôi trước khi sang nhiệm vụ con kế.
```

Dừng sau mỗi nhiệm vụ con giữ cho mỗi commit nhỏ, người làm xem được diff trước khi commit, và lịch sử khớp đúng danh sách nhiệm vụ.

### 3.4 PR và merge

- Một PR cho một story; tiêu đề `[DA-03] Teleop pipeline on psi-data`.
- Kích thước: khoảng 400 dòng thay đổi trở xuống, không tính lock file và fixture sinh ra. Lớn hơn thì tách story.
- Review: chủ sở hữu đường dẫn (CODEOWNERS) và người dự phòng; Hiếu không là người review duy nhất của PR nào (04 mục 3.2).
- Merge bằng **Rebase and merge** để giữ từng commit nhiệm vụ con trên `master`, lịch sử thẳng. Không dùng squash, vì squash gộp mất ranh giới nhiệm vụ con.

### 3.5 Cài đặt GitHub (Hiếu làm một lần)

1. Thêm 4 người làm collaborator; điền tên GitHub vào `.github/CODEOWNERS` (các dòng đang để trống).
2. Settings → Branches → luật cho `master`: bắt buộc PR, 1 approval, review của Code Owners, status check (`core-ci` khi S1-01 xong, build website), lịch sử thẳng, cấm force-push và cấm xóa.
3. Settings → General → Pull Requests: chỉ bật "Allow rebase merging"; bật tự xóa nhánh sau merge.
4. Tạo label `person:hieu`, `person:hung`, `person:chau`, `person:long`, `person:thong`, `sprint:S1`–`sprint:S6`, `area:core`, `area:adapter`, `area:data`, `area:docs`, `contract-change`.
5. Tạo GitHub Project kiểu board: cột Todo, In progress, Review, Done; trường Sprint, Người, Cổng.

## 4. Theo dõi và đánh giá theo nhiệm vụ con

Đơn vị theo dõi là **nhiệm vụ con**: một dòng `- [ ]` trong file story, một commit `<story-id>/<số>: …`, một dòng trong checklist của issue.

| Muốn biết | Cách xem |
|---|---|
| Tiến độ mọi story theo người | `python3 scripts/progress.py` (đếm nhiệm vụ con đã đánh dấu trong file story) |
| Nhiệm vụ con nào của một story đã vào `master` | `git log origin/master --oneline --grep '^DA-03/'` |
| Ai đang làm gì | Board của GitHub Project; `gh pr list --state open` |
| Bằng chứng của một nhiệm vụ con | Thân commit và mục "Bằng chứng" của PR |

Khi review một nhiệm vụ con, chấm theo 4 câu, ghi trong PR:

1. AC liên quan có bằng chứng chạy lại được không (lệnh và output, test, file số đo)?
2. Diff có nằm trong "Phạm vi file" không?
3. Có đổi file dùng chung mà không qua PR contract không?
4. Số liệu mới có ghi là ước lượng hay thực đo không?

Thông tổng hợp trong bản tin tuần (04 mục 2.2): số nhiệm vụ con xong theo người, PR chờ review quá 2 ngày, nhiệm vụ con bị mở lại.
