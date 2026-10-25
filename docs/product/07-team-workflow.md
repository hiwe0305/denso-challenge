# 07 · Chia việc 5 người và quy trình git khi dùng Claude

_Ngày 23/10/2026. Vai trò BMAD: Scrum Master cộng Product Owner. Đầu vào: [04 · Kế hoạch](04-delivery-plan.md) mục 3 (vai, RACI), [design 23/10/2026](../superpowers/specs/2026-10-23-data-pipeline-and-failure-eval-design.md) mục 11 (Pha A). Bản 0.1 là [Đề xuất]; Hiếu và Thông chốt ở họp lập kế hoạch Sprint 1 ngày 26/10/2026._

| Ngày | Phiên bản | Thay đổi | Tác giả |
|---|---|---|---|
| 25/10/2026 | 0.4 | Theo [design chia làn ngày 25/10/2026](../superpowers/specs/2026-10-25-lanes-and-code-structure-design.md): mục 2.1 sở hữu theo nhân, ba làn, adapter, `denso-sim`, `ros2_ws`, `configs/` theo làn; mục 2.2 đổi chủ DA-01, DA-04, DA-08, DA-13, DA-17, DA-18, DA-20, DA-23, thêm DA-24, DA-25; mục 2.3 tải mới; mục 3.2 hợp đồng do Hiếu giữ; mục 3.6 PR `chore-restructure` | PO (Hiếu) |
| 25/10/2026 | 0.3 | Theo [design ngày 25/10/2026](../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md): mục 2.1 thêm `flywheel-mujoco`, `flywheel-agentqa`, cột review thành người bình luận vì Hiếu duyệt duy nhất; mục 2.2 thêm DA-15…DA-23, DA-07 gộp vào DA-19, DA-10 gộp vào DA-15, DA-11 dời sau demo, DA-03, DA-06, DA-12 đổi theo MuJoCo; khung package `flywheel-psi0` thuộc DA-19, `flywheel-ingest` thuộc DA-22; mục 2.3 tải mới; mục 3.4, 3.5 quy trình duyệt và merge | PO (Hiếu) |
| 24/10/2026 | 0.2 | Mục 2.1: thêm `scripts/g0/`, `docs/g0/` (chủ Hưng, review Hiếu); mục 3.2: bảng tổng hợp và sổ chi phí chung không sửa trong nhánh story | PO (Hiếu) |
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

**Bản 0.4** thay bảng cũ theo design chia làn mục 2–7. Đường dẫn theo cây ở 03 mục 7.1 (bản 0.6); trước PR `chore-restructure` (mục 3.6) các package mới chưa tồn tại.

| Đường dẫn | Chủ | Bình luận |
|---|---|---|
| `packages/flywheel-contracts/`, `packages/flywheel-store/`, `packages/flywheel-testkit/`, `packages/flywheel-cli/` (nhân) | Hiếu | Long |
| `packages/flywheel-data/` (làn Dữ liệu) | Thông | Hiếu |
| `packages/flywheel-eval/` (làn Đánh giá) | Châu | Hiếu |
| `packages/flywheel-loop/` (làn Vòng quyết định) | Long | Hiếu |
| `packages/denso-sim/`, `packages/flywheel-mujoco/`, `ros2_ws/` | Hưng | Hiếu |
| `packages/flywheel-psi0/`, `packages/flywheel-lerobot/`, `packages/flywheel-simple/`, `packages/flywheel-nim/` (trừ `generators/`) | Hiếu | Châu |
| `packages/flywheel-nim/generators/` | Hưng | Hiếu |
| `packages/flywheel-isaac/` (sau demo) | Hưng | Hiếu |
| `configs/kernel/`, `configs/models/` | Hiếu | Long |
| `configs/runplans/` | Hiếu duyệt, Long viết | Châu |
| `configs/embodiments/`, `configs/sim/` | Hưng | Hiếu |
| `configs/data/` | Thông | Hiếu |
| `configs/eval/` | Châu | Hiếu |
| `configs/loop/` | Long | Hiếu |
| `docker/ros2-sim/`, `.devcontainer/` | Hưng | Hiếu |
| `docker/simple/`, `docker/psi0/`, `compose.yaml` | Hiếu | Hưng |
| `tests/e2e/` | Hiếu | Long |
| `pyproject.toml` gốc, `uv.lock`, `.github/workflows/`, `scripts/` (sau PR restructure là `scripts/repo/`), `ops/` | Long | Hiếu |
| `scripts/g0/`, `docs/g0/` | Theo story; thư mục do Hưng giữ | Hiếu |
| `docs/spec-v10-failure-to-data.md`, `docs/product/00`–`08`, `docs/superpowers/` | Hiếu | Thông |
| `docs/product/stories/` | Thông | Hiếu |
| `website/`, `deliverables/` | Hiếu | Long |

Chủ sở hữu không có nghĩa là người duy nhất được sửa. Người khác sửa được khi story của họ khai đường dẫn đó trong "Phạm vi file" và chủ sở hữu review PR.

**Bản 0.3, 0.4.** Hiếu là người duyệt và merge duy nhất vào `master` (mục 3.4). Chủ đường dẫn và người ở cột thứ ba bình luận, không chặn merge. Ba làn chỉ import nhân; import-linter chặn làn import lẫn nhau (03 mục 7.3).

### 2.2 Story Pha A của design

Đặt mã `DA-xx` (Design, Pha A) cho tới khi SM gắn vào sprint. Các story này chạy song song với story S1–S6 ở 04 mục 4. Giờ là ước lượng chi tiết hơn bảng ở 04 mục 4.9; tổng khoảng 185–255 giờ, cao hơn ước thô 160–220 giờ ban đầu của design; 04 mục 4.9 đã dùng con số này. Mỗi story ứng với một story 9.x của Epic 9 trong [02](02-prd.md).

| Mã | Story | Chủ | Phạm vi file chính | Phụ thuộc | Giờ | Sprint |
|---|---|---|---|---|---|---|
| DA-01 | Định dạng episode chung, `action_layout`, trường mới của Episode. Bản 0.4: Thông làm vì làn Dữ liệu cần đầu tiên; file nằm trong `flywheel-contracts`, Hiếu duyệt. | Thông (Hiếu giữ hợp đồng) | `flywheel-contracts/`, `configs/embodiments/` (schema) | S1-10 | 8–12 | S1 |
| DA-02 | Export LeRobot theo `action_layout`, `stats_psi0.json`, contract test bằng loader Ψ₀ | Thông | `flywheel-data/export/` | DA-01, 2.6 | 8–12 | S2 |
| DA-03 | Pipeline teleop: normalize, cắt đoạn, QA riêng nguồn. Bản 0.3: chạy trên teleop bàn phím (DA-16) và dataset BTC (DA-22) thay cho psi-data | Thông | `flywheel-data/ingest/`, `normalize/`, `annotate/`, `qa/` | DA-01, 2.2 | 20–25 | S2 |
| DA-04 | Pipeline egocentric E-A và E-B trên mẫu EgoDex: che danh tính, cắt đoạn, pose tay và camera, định dạng H-RDT, QA. Bản 0.4: chuyển sang làn Dữ liệu (`flywheel.data.ingest.egocentric`). | Thông | `flywheel-data/ingest/egocentric/` | DA-01 | 25–35 | S2–S3 |
| DA-05 | `NimClient`, định tuyến theo `data_class`, Cosmos Reason tự host trên 5090 | Hiếu | `flywheel-nim/` (trừ `generators/`) | DA-01 | 12–15 | S2 |
| DA-06 | Tầng S3: Cosmos Transfer, kiểm IoU với segmentation gốc. Bản 0.3: trên video render MuJoCo của robot DENSO thay cho video sim G1 | Hưng | `flywheel-nim/generators/` | DA-05, 3.1a | 15–20 | S3 |
| DA-07 | Log train theo nhóm action và theo vị trí trong chunk, checkpoint trung gian tự chạy P3. Bản 0.3: gộp vào DA-19 | Hiếu | `flywheel-psi0/` phần trainer | 4.2 | 10–14 | S2 |
| DA-08 | Bộ phát hiện lỗi F-TRAIN (T1–T8) và F-OFF (O1–O4) từ `metrics.jsonl`, đưa vào báo cáo. Bản 0.4: chuyển sang làn Đánh giá. | Châu | `flywheel-eval/diagnosis/` | DA-07 | 8–12 | S3 |
| DA-09 | Probe P1–P4 đóng băng có hash; chạy trên `pre.*`, `postpre.*` | Hiếu | `flywheel-psi0/` phần probe, `gate/` (khai) | S1-03 | 12–18 | S2–S3 |
| DA-10 | Robot thay thế tham số và lệnh `fw embodiment score`. Bản 0.3: gộp vào DA-15 (MJCF thay USD) | Hưng | `flywheel-isaac/`, `configs/embodiments/` | S1-02 phần Isaac Sim | 25–35 | S1–S3 |
| DA-11 | Cảnh trạm khay → máy và `DensoIsaacSim`. Bản 0.3: dời sau demo MuJoCo; cảnh MuJoCo nằm trong DA-15 | Hưng | `flywheel-isaac/` | DA-10 | 15–25 | Sau demo |
| DA-12 | `DensoTrayToMachine`: 6 bước, 10 kiểu lỗi, scorer. Bản 0.3: chạy trên MuJoCo, phụ thuộc DA-15 thay DA-11 | Châu | `flywheel-tasks/`, `configs/tasks/` | DA-15, 3.3 | 15–20 | S2 |
| DA-13 | Bước 4b quy lỗi về stage và quy tắc F-SYS trong `diagnosis`. Bản 0.4: chuyển sang làn Đánh giá (`flywheel.eval.diagnosis`). | Châu | `flywheel-eval/diagnosis/` | DA-09, 6.x | 8–10 | S4 |
| DA-14 | Gửi danh sách 21 mục cho DENSO, theo dõi trả lời, cập nhật design mục 9 | Hiếu | `docs/` | Không | 3 | S1 tuần 1 |
| DA-15 | Robot DENSO tương đương (MJCF từ file tham số), cảnh trạm, env task khay → máy với vị từ thành công, planner S1, chấm độ giống | Hưng | `denso-sim/`, `flywheel-mujoco/`, `configs/embodiments/`, `configs/sim/` | Không | 25–35 | S1–S2 |
| DA-16 | Teleop bàn phím trên ROS 2 (đầu tay qua IK), ghi rosbag2 MCAP theo bảng topic, mục sổ chi phí mỗi phiên. Bản 0.4: đổi sang ROS 2 và MCAP | Hưng | `denso-sim/teleop/`, `ros2_ws/src/denso_teleop/` | DA-15 (code trên MJCF tối thiểu) | 10–15 | S1 |
| DA-17 | Phát lại action động học và động lực học, video so sánh, ngưỡng hiệu chỉnh. Bản 0.4: phần kiểm dữ liệu thuộc làn Dữ liệu; hàm `replay()` thuộc DA-15. | Thông | `flywheel-data/replay_check/` | DA-15 (code trên MJCF tối thiểu) | 8–12 | S1–S2 |
| DA-18 | Egocentric thô → định dạng EgoDex cho stage 1, contract test bằng loader Ψ₀, stats. Bản 0.4: chuyển sang làn Dữ liệu; dùng RoboBrain 2.5-4B, Molmo2-4B để gán nhãn. | Thông | `flywheel-data/ingest/egocentric/`, `flywheel-data/export/` | DA-01, DA-04 | 20–30 | S2–S3 |
| DA-19 | Khung package `flywheel-psi0`; đọc code train của tác giả, lớp bọc log cho 3 stage (gồm phần DA-07), adapter train trên Colab. Bản 0.4: khung package chuyển vào PR restructure; thêm client RTC ghi log. | Hiếu | `flywheel-psi0/` | Không | 20–28 | S1–S2 |
| DA-20 | Agent QA/QC: serve Nemotron cục bộ, dựng hình từng stage, báo cáo HTML, bộ ca mẫu. Bản 0.4: chuyển sang làn Đánh giá (`flywheel.eval.agentqa`). | Châu | `flywheel-eval/agentqa/`, `configs/eval/` | DA-19 cho log thật (code trên log giả) | 20–30 | S2–S3 |
| DA-21 | Export LeRobot v3 từ v2.1, checklist chuẩn hóa trong contract test | Thông | `flywheel-data/export/` | DA-02 | 4–6 | S2 |
| DA-22 | Khung package `flywheel-ingest`; đọc và phân tích dataset BTC, bộ đọc `BtcDatasetSource`. Bản 0.4: khung package chuyển vào PR restructure. | Thông | `flywheel-data/ingest/` | Dataset từ BTC | 8–12 | S1 |
| DA-23 | Eval bất đồng bộ trên MuJoCo, log inference RTC, dòng thời gian. Bản 0.4: runner bất đồng bộ thuộc làn Vòng; `timing` của sim thuộc DA-15; client RTC thuộc DA-19. | Long | `flywheel-loop/runner/` | DA-15 (code trên policy giả) | 10–15 | S2 |
| DA-24 | Workspace ROS 2 và môi trường sim: `docker/ros2-sim`, devcontainer, `denso_description`, `denso_interfaces`, `denso_mujoco`, `denso_control`, `denso_bringup`, job CI `ros` | Hưng | `ros2_ws/`, `docker/ros2-sim/`, `.devcontainer/` | DA-15 nhiệm vụ con 1 | 25–35 | S1–S2 |
| DA-25 | Schema và file mẫu cho artifact mới giữa các làn (bảng topic MCAP, `ReplayReport`, log RTC, kết quả probe, `QAReport`) | Hiếu | `flywheel-contracts/`, `flywheel-testkit/` | PR restructure | 6–10 | S1, trước 29/10 |

File story DA-15…DA-25 nằm trong `docs/product/stories/` (bản 0.3, 0.4). Việc chưa có chủ: cập nhật website và Pitch theo spec v10.3 (khoảng 10–15 giờ), cập nhật 00–02, 05, 06. Hiếu chọn người ở họp lập kế hoạch.

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

**Bản 0.3 (25/10/2026).** Ước lượng thay đổi theo người sau khi đổi sang MuJoCo (giữa khoảng, 04 mục 4.10):

| Người | Bớt | Thêm | Thay đổi |
|---|---|---|---|
| Hiếu | DA-07 khoảng 12 | DA-19 khoảng 24; duyệt và merge mọi PR, ước 0,5–1 giờ mỗi ngày làm việc, khoảng 30–60 giờ trong 12 tuần | khoảng +40 đến +70 |
| Hưng | S1-05 6, S1-11 12, 5.5 khoảng 28, DA-10 30, DA-11 20 | DA-15 30, DA-16 12 | khoảng −55 |
| Châu | T2 của S1-11 6, 5.5 khoảng 8, phần thu nhỏ S1-06 4 | DA-17 10, DA-23 12 | khoảng +4 |
| Long | Không | DA-18 25 | khoảng +25 |
| Thông | S1-07 12 | DA-20 25, DA-21 5, DA-22 10 | khoảng +28 |

**Bản 0.4 (25/10/2026)**, sau khi chia làn (design chia làn mục 3.1). Ước lượng thô, giữa khoảng, so với bảng bản 0.3:

| Người | Bớt | Thêm | Tổng khoảng |
|---|---|---|---|
| Hiếu | Không | S1-02 8, S1-04 18, `Psi0Policy` khoảng 10, train ACT và DP khoảng 15, chạy F-ACT, C cuối, B-fail của ACT khoảng 20, client RTC khoảng 5, DA-25 8, giữ nhân khoảng 10 | **340–370** |
| Hưng | S1-02 8 | S1-06 4, S1-09 8, DA-24 30 | 235–240 |
| Châu | S1-04 18, DA-17 10, DA-23 12, S1-06 và S1-09 12, việc GPU khoảng 45 | DA-08 10, DA-13 9, DA-20 25, chẩn đoán và kiểm hệ thống khoảng 20, evidence card khoảng 10 | 180–185 |
| Long | DA-01 10, DA-04 30, DA-18 25, DA-13 9, chẩn đoán khoảng 20 | Sổ chi phí khoảng 10, cổng dev và bảng quyết định khoảng 15, N_B 5, công cụ HD 10, thống kê 10, backup 4, khóa holdout 5, DA-23 12, PR restructure khoảng 6 | 250–260 |
| Thông | Sổ chi phí, cổng dev, N_B, evidence card, công cụ HD, thống kê, backup khoảng 64, DA-08 10, DA-20 25 | DA-01 10, DA-04 30, DA-18 25, DA-17 10 | 240–250 |

**Hiếu vượt xa mọi người** (khoảng 1,7 lần Châu). Cách giảm đã ghi ở design chia làn mục 9: job GPU chạy từ RunPlan bằng một lệnh; nhân viết một lần rồi đóng băng; Long hoặc Thông viết PR nhân khi Hiếu giao. Nếu báo cáo tracking cho thấy PR chờ quá 1 ngày lặp lại hoặc job GPU trễ, xét chuyển phần viết code của DA-09 (probe) sang Châu và DA-05 (NimClient) sang Long, Hiếu chỉ chạy job.

Bản 0.3: Hưng không còn là người tải cao nhất. Hiếu tăng nhiều nhất vì duyệt một mình; nếu hàng chờ PR quá 1 ngày lặp lại (báo cáo tracking), chuyển DA-05 hoặc DA-09 cho người khác trước khi cắt phạm vi.

Theo quyết định ngày 23/10/2026 (04 mục 4.9): giữ đủ phạm vi; đo k sau Sprint 1; vượt thì chuyển phần trễ sang API trước, rồi mới cắt. Hưng và Long tải cao nhất; story của hai người này là ứng viên đầu tiên cho việc chuyển sang API (ví dụ dùng TIAGo++ thay DA-10, model pose có sẵn cho DA-04).

## 3. Quy trình git khi dùng Claude

### 3.1 Phạm vi file của story

Mỗi story có mục "Phạm vi file": danh sách thư mục hoặc file được sửa. CLAUDE.md gốc yêu cầu Claude dừng lại khi cần sửa ngoài danh sách này. Người review kiểm `git diff --stat origin/master...` chỉ chạm các đường dẫn đã khai.

### 3.2 File dùng chung: contract trước

File dùng chung: `contracts/`, schema trong `configs/`, `pyproject.toml` gốc, `uv.lock`, `.github/workflows/`.

1. Người cần đổi mở issue "Contract change: …" mô tả trường cần thêm và lý do.
2. Chủ sở hữu (bản 0.4: Hiếu giữ `flywheel-contracts`, `flywheel-testkit`; người khác viết khi Hiếu giao) làm một PR nhỏ chỉ đổi contract, kèm schema, file mẫu trong `flywheel-testkit` và test; nhánh `<story-id>-contract`.
3. PR contract merge trước. Người cần dùng rebase lên `master` rồi làm tiếp.
4. Bảng tổng hợp và sổ chi phí chung (bản 0.2): nhánh story không sửa 03 §3.3 hay một file sổ chi phí dùng chung. Story ghi kết quả và chi phí vào file của mình; chủ của bảng gom lại vào mốc cố định. Quy ước cho G0 ở [docs/g0/README.md](../g0/README.md).
5. Thêm phụ thuộc Python: người cần thêm sửa `pyproject.toml` của package mình; `uv.lock` chỉ được tạo lại bằng `uv lock` sau khi rebase, không sửa tay; xung đột ở `uv.lock` thì lấy bản của `master` rồi chạy lại `uv lock`.

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
- Review (bản 0.3, thay quy tắc cũ "Hiếu không là người review duy nhất"): **Hiếu là người duyệt và merge duy nhất** vào `master`. Chủ sở hữu đường dẫn và người ở cột thứ ba của mục 2.1 bình luận, không chặn merge. Trước khi xin duyệt, PR phải xanh ở `core` và `guard`. Lịch tracking tự động (10:00, 14:00, 18:00) liệt kê PR chờ Hiếu; tổng kết 21:30 đề xuất thứ tự duyệt, ưu tiên PR đang chặn người khác và PR sửa `contracts/`.
- Không ai chờ PR của người khác để code tiếp: dùng schema trong `contracts`, bản giả trong `flywheel-fakes` và file mẫu (design 25/10 mục 10.1); không tạo nhánh từ nhánh chưa merge.
- Merge bằng **Rebase and merge** để giữ từng commit nhiệm vụ con trên `master`, lịch sử thẳng. Không dùng squash, vì squash gộp mất ranh giới nhiệm vụ con.

### 3.5 Cài đặt GitHub (Hiếu làm một lần)

1. Thêm 4 người làm collaborator; điền tên GitHub vào `.github/CODEOWNERS` (các dòng đang để trống).
2. Settings → Branches → luật cho `master`: bắt buộc PR, 1 approval, review của Code Owners (bản 0.3: CODEOWNERS chỉ có dòng `*` là Hiếu; muốn bắt buộc thật thì bật "Require review from Code Owners" và tắt "Do not allow bypassing" để Hiếu merge được PR của chính mình, chờ Hiếu quyết, design 25/10 câu Q-E). Ruleset "Only Hiếu merges into master" đã bật ngày 24/10/2026. Còn lại: status check (`core-ci` khi S1-01 xong, build website), lịch sử thẳng, cấm force-push và cấm xóa.
3. Settings → General → Pull Requests: chỉ bật "Allow rebase merging"; bật tự xóa nhánh sau merge.
4. Tạo label `person:hieu`, `person:hung`, `person:chau`, `person:long`, `person:thong`, `sprint:S1`–`sprint:S6`, `area:core`, `area:adapter`, `area:data`, `area:docs`, `contract-change`.
5. Tạo GitHub Project kiểu board: cột Todo, In progress, Review, Done; trường Sprint, Người, Cổng.

### 3.6 PR `chore-restructure` (bản 0.4)

Một lần, trước khi các làn viết code (design chia làn mục 8):

1. Merge S1-08 như hiện tại.
2. Long mở nhánh `chore-restructure` từ `origin/master`: tách `packages/flywheel` thành `flywheel-contracts`, `flywheel-store`, `flywheel-testkit` (gồm `flywheel-fakes`), `flywheel-cli`; tạo khung rỗng `flywheel-data`, `flywheel-eval`, `flywheel-loop`, `flywheel-mujoco`, `flywheel-psi0`, `denso-sim`; chuyển test e2e ra `tests/e2e/`; sửa ruff, mypy, pytest, import-linter, CI; dời `scripts/*.py` vào `scripts/repo/` và sửa đường dẫn trong workflow, `CLAUDE.md`, `RULE.md`, `08`.
3. Chỉ di chuyển file và sửa cấu hình; không đổi logic. Bằng chứng: CI xanh, `uv run pytest` chạy cả test của testkit, `lint-imports` báo đủ các luật mới.
4. Hạn: hết ngày 27/10/2026. Ngày 26–27/10 các làn làm nhiệm vụ con không nằm trong package mới (đọc, kiểm kê, file tham số robot, `docs/g0/`).

## 4. Theo dõi và đánh giá theo nhiệm vụ con

Rule kiểm soát theo ngày (R1–R9), báo cáo ngày tự động, nhãn nguyên nhân lỗi và trang Tiến độ nằm ở [08 · Kiểm soát dự án theo ngày](08-daily-control.md). Label ở mục 3.5 được tạo bằng `bash scripts/setup_labels.sh`.

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
