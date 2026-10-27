# Design: demo G1 + Ψ₀ trên SIMPLE, thí nghiệm dữ liệu egocentric và data flywheel đầy đủ

_Ngày 27/10/2026. Trạng thái: **đã duyệt hướng** (trưởng nhóm, 27/10/2026, sau buổi gặp DENSO), chưa có code. Tài liệu này là design hiện hành duy nhất. Nó thay ba design cũ (23/10 về pipeline dữ liệu và robot DENSO; 25/10 về MuJoCo và Agent QA/QC; 25/10 về chia làn); phần còn dùng được của ba tài liệu đó đã chép vào đây, phần còn lại bị bỏ (mục 14). Ba file cũ đã xóa khỏi repo; xem lại bằng `git log --all -- docs/superpowers/specs/`. Đã đưa vào spec v10.4, 01 bản 0.5, 02 bản 0.5, 03 bản 0.7, 04 bản 0.7, 07 bản 0.5, RULE, CLAUDE.md, README và file story ngày 27/10/2026._

Quy ước: **[Đã chốt]** là quyết định của trưởng nhóm (Hiếu). **[Đề xuất]** là lựa chọn của người viết, cần duyệt. **[Option]** là nhiều phương án song song. Số liệu của tác giả paper ghi rõ là số tác giả báo; số chưa đo ghi là giả định hoặc ước lượng.

## 0. Đọc nhanh

1. **Demo ngày 17/11/2026 dùng đúng robot và model của paper**: Unitree G1 trong SIMPLE, Ψ₀ với checkpoint của tác giả [Đã chốt]. Robot DENSO trên MuJoCo bị bỏ hẳn [Đã chốt].
2. **Cảnh chính là hai bàn**: G1 gắp vật ở bàn này, đi sang bàn kia, đặt vật lên đó. SIMPLE có sẵn đúng task này, `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`, kèm dữ liệu teleop và checkpoint công bố (mục 3).
3. **Thu dữ liệu trên sim, giảm compute của Isaac Sim**: vật lý và thu dữ liệu chạy MuJoCo thuần (`--sim-mode=mujoco`); Isaac Sim chỉ render lại khi cần ảnh đẹp hoặc so với số công bố. Nguồn dữ liệu robot: dataset có sẵn của tác giả, teleop bằng bàn phím (đội tự viết, vì SIMPLE chỉ hỗ trợ kính PICO), và sinh tự động bằng motion planning (mục 4, 5).
4. **Giả thuyết mới HE**: dữ liệu egocentric của người giúp Ψ₀ cần ít demo robot hơn. Kiểm bằng ba checkpoint ablation mà tác giả đã công bố (có EgoDex, 10% EgoDex, không EgoDex), fine-tune ở nhiều mức demo, ra đường cong success theo số demo. Paper chưa có đường cong này (mục 7).
5. **Data flywheel xây đủ kiến trúc**, gồm cả xử lý và chuẩn hóa dataset (6 tầng: Ingest → Normalize → Annotate → QA → Release → Export) [Đã chốt] (mục 6).
6. **Agent QA/QC demo trên dữ liệu thật có cài lỗi**: cấy lỗi có đáp án vào dataset của tác giả, đo precision và recall theo loại lỗi. Có số đo thật trước khi đội train model; sau khi train thì chạy trên log và output thật (mục 9).
7. **Website và hai file PowerPoint chưa sửa**; chỉ tính tới khi chuẩn bị demo 17/11 [Đã chốt]. Người làm từng story do Product Owner giao sau [Đã chốt].

## 1. Bối cảnh và lý do

Ngày 27/10/2026 trưởng nhóm gặp DENSO và chốt bốn ý:

| # | Ý | Quyết định [Đã chốt] |
|---|---|---|
| 1 | Robot và model của demo | Demo tới dùng humanoid của paper và model Ψ₀; tập trung vào đó trước |
| 2 | Thu dữ liệu | Dựng cảnh đơn giản trên Isaac Sim và MuJoCo, giảm compute trên Isaac Sim; sinh dữ liệu tự động hoặc bằng bàn phím |
| 3 | Bằng chứng | Chứng minh điều Ψ₀ nói: dữ liệu egocentric của người giúp cần ít dữ liệu robot hơn mà hiệu quả cao hơn; benchmark rõ như paper, video demo rõ; chạy trên dataset có sẵn, rồi trên dataset tự xây ở ý 2; cảnh hai bàn |
| 4 | Data flywheel | Ưu tiên xây đủ kiến trúc, gồm xử lý và chuẩn hóa dataset; Agent QA/QC có demo trên dữ liệu (giả định trước khi train, phân tích trên dữ liệu thật sau); demo được toàn bộ luồng và hiệu suất |

Cùng ngày trưởng nhóm chốt thêm: bỏ hẳn robot DENSO trên MuJoCo; xóa tài liệu và story lỗi thời; chưa sửa website và hai file PowerPoint; sửa tài liệu trên nền nhánh `docs-denso-mujoco-pivot`.

**Những gì người viết kiểm ngày 27/10/2026** (tài liệu SIMPLE, README Ψ₀ ở commit `cda3fdf`, Hugging Face `USC-PSI-Lab`, paper arXiv 2603.12263):

| Điểm | Kết quả |
|---|---|
| Teleop trong SIMPLE | Cần kính PICO 4 (hoặc 4 Ultra), hai tay cầm và hai tracker đeo cổ chân, qua XRoboToolkit. Tài liệu không có đường bàn phím hay gamepad |
| Lệnh teleop | `python -m simple.cli.teleop_decoupled_wbc simple/$TASK --sim-mode=mujoco --record --no-headless`; ghi vào `data/teleop_decoupled_wbc/simple/$TASK/level-0/`; bước "Replay & Render" render lại bằng Isaac Sim |
| Sinh tự động | `uv run datagen simple/<Task>MP-v0 --num-episodes=N`: cuRobo lập quỹ đạo hai tay, AMO giữ thân dưới, đế đi theo script; chỉ lưu episode thành công; xuất LeRobot |
| Chế độ sim | `mujoco` (vật lý và render MuJoCo) và `mujoco_isaac` (vật lý MuJoCo, render Isaac Sim) |
| Task hai bàn | `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`: dữ liệu teleop 203 MB trong `psi-data/simple`; checkpoint fine-tune trong `psi-model/psi0/simple-checkpoints` có ba bản: `…teleop-v0`, `…mixed-v0`, `…variant5-v0-processed`. Ψ₀ công bố 7/5/6 thành công trên 10 lượt mỗi mức (spec mục 7.1) |
| Checkpoint ablation | VLM chỉ train trên Humanoid Everyday (HE) `psi0/pre.abl.only.he.2512311516.48k` kèm action expert `psi0/postpre.abl.only.he.2602050012`; VLM 10% EgoDex `psi0/pre.abl.ego.10per.2602021632.46k` kèm `psi0/postpre.abl.ego.10per.2602050006`; bản chính EgoDex + HE `psi0/pre.fast.1by1.2601091803.ckpt.ego200k.he30k` kèm `psi0/postpre.1by1.pad36.2601131206.ckpt.he30k` |
| Bằng chứng của paper cho egocentric | Ablation trên 2 task robot thật, 10 lượt: không pretrain 2/10; 10% EgoDex 1/10 so với 8/10 khi đủ (task gắp đồ chơi); chỉ HE 4/10 so với 8/10 và 7/10. Fine-tune luôn dùng 80 trajectory mỗi task. **Không có đường cong success theo số demo robot**, không có số trên SIMPLE trong paper (số tác giả báo) |
| Thời gian eval | 6–10 phút mỗi episode ở `mujoco_isaac`, vì Isaac Sim render đồng bộ (README Ψ₀) |

Ba điều rút ra:

- Phần tốn compute nhất của SIMPLE là **eval có render Isaac**, không phải thu dữ liệu. Thu dữ liệu đã chạy MuJoCo thuần.
- Checkpoint ablation công khai biến claim của paper thành một thí nghiệm có đối chứng đội chạy lại được mà không phải pretrain lại.
- Câu V3 (teleop và motion planning có cùng bộ điều khiển không) quay lại đường găng, vì dữ liệu tự động và dữ liệu teleop của task hai bàn có thể chạy hai bộ điều khiển khác nhau (mục 5.3).

## 2. Mục tiêu, không làm, phản mục tiêu

**Mục tiêu**

- M1. Tái tạo Ψ₀ trên task hai bàn trong SIMPLE, so với số công bố (G0).
- M2. Ba nguồn dữ liệu robot cho task hai bàn: dataset của tác giả, teleop bàn phím, sinh tự động; cả ba ra cùng định dạng episode chung.
- M3. Pipeline data flywheel đủ 6 tầng chạy trên cả ba nguồn, xuất LeRobot v2.1 đọc được bằng loader Ψ₀; có báo cáo dataset (số episode, pass, flag, reject, stats).
- M4. Thí nghiệm HE: ba checkpoint ablation × lưới số demo, đường cong success theo số demo, trên dataset có sẵn rồi trên dataset tự xây; video rollout cạnh nhau.
- M5. Agent QA/QC có số đo hiệu suất trên bộ lỗi cấy (dữ liệu, log train, log inference) trước khi train; chạy trên log thật sau khi train.
- M6. Demo 17/11 chạy trọn một vòng: dữ liệu thô → QA → release → train hoặc chọn checkpoint → eval → thất bại → chẩn đoán → đề xuất dữ liệu → sổ chi phí.
- M7. Giữ lộ trình 12 tuần của spec (HS, HT, HD) trên G1 sau demo.

**Không làm**

- Robot DENSO, MuJoCo riêng ngoài SIMPLE, ROS 2, dataset của BTC, video egocentric của nhà máy [Đã chốt: bỏ hẳn robot DENSO trên MuJoCo].
- Pretrain lại stage 1 hay post-train lại stage 2 từ đầu; chỉ fine-tune stage 3 từ checkpoint của tác giả.
- Thiết bị PICO cho teleop; chỉ dùng khi đội tự mua (mục 4.4).
- Website và Pitch trước khi chuẩn bị demo 17/11.
- Synthetic tầng S3, S4 (Cosmos qua NIM) trước demo.

**Phản mục tiêu** (vẫn chạy được nhưng coi là hỏng)

- Kết luận "egocentric giúp" khi ba biến thể khác nhau ở chỗ khác ngoài dữ liệu pretrain (số bước fine-tune, dữ liệu fine-tune, chế độ render, hạt giống điều kiện).
- Đường cong HE chỉ có một seed ở mọi điểm rồi viết như kết quả chắc chắn.
- Train trên ảnh render MuJoCo rồi eval trên ảnh render Isaac (hoặc ngược lại) mà không báo.
- Agent QA/QC tự đưa con số không có trong đầu vào, hoặc tự chọn dữ liệu thay kỹ sư.
- Số đo của Agent QA/QC trên lỗi cấy được viết như số đo trên lỗi tự nhiên.

## 3. Task và cảnh

**Task chính** [Đã chốt cảnh hai bàn; chọn task SIMPLE là Đề xuất]: `G1WholebodyLocomotionPickBetweenTablesTeleop-v0`. Dùng nguyên task của SIMPLE, không dựng cảnh mới, vì (a) có số công bố để so ở G0, (b) có dataset và checkpoint sẵn, (c) Ψ₀ công bố 7/5/6 nên còn dư địa để đo khác biệt, không chạm trần như `BendPickMP` (10/10/10). Biến thể của đội chỉ đổi qua cấu hình domain randomization của SIMPLE (vật, vị trí, ánh sáng), không sửa mã task.

**Các bước của task** [Đề xuất], dùng cho scorer từng bước (spec mục 5). Vị từ đối chiếu với cờ thành công của SIMPLE ở G1:

| Bước | Tên | Vị từ đạt |
|---|---|---|
| 1 | Tiếp cận | Bàn tay trong bán kính r_reach quanh vật trên bàn nguồn |
| 2 | Gắp | Có tiếp xúc tay–vật, vật rời mặt bàn quá h_grasp |
| 3 | Đi | Thân robot rời vùng bàn nguồn, vật vẫn trong tay, thân trong giới hạn thăng bằng |
| 4 | Tới bàn đích | Thân dừng trong vùng trước bàn đích; vật vẫn trong tay |
| 5 | Đặt | Vật trong vùng đích trên bàn đích, độ cao dưới h_place |
| 6 | Nhả và ổn định | Hết tiếp xúc tay–vật; vật đứng yên T_stable giây |

Kiểu lỗi giữ bảng spec mục 5.2, thêm **L-WALK** (dừng hoặc đi sai hướng ở bước 3–4, lớp chung `mang`). Điều kiện chạy suốt episode: thăng bằng (L-BALANCE).

**Task phụ F1** giữ như spec mục 2.3 (`BendPickTeleop` và `BendPickMP`) để kiểm lõi trên task thứ hai.

**Vector điều kiện** theo spec mục 4.2, thêm vị trí tương đối của hai bàn (khoảng cách, góc) nếu SIMPLE cho ngẫu nhiên hóa (kiểm ở S1-06, S1-09).

## 4. Simulator và chi phí tính toán

### 4.1 Phân vai

| Chế độ | Dùng cho | Ghi chú |
|---|---|---|
| `--sim-mode=mujoco` | Teleop bàn phím, sinh tự động, phát lại action để kiểm dữ liệu, eval nhanh, chạy nhiều điều kiện | Không cần Isaac Sim; chạy được trên RTX 3060 (cần đo ở G0) |
| `--sim-mode=mujoco_isaac` | Eval so với số công bố (G0), video demo đẹp, dữ liệu train nếu chọn render Isaac | 6–10 phút mỗi episode theo README Ψ₀ |
| Replay & Render của SIMPLE | Render lại episode đã thu bằng MuJoCo sang ảnh Isaac | Vật lý không đổi; chỉ đổi ảnh |

### 4.2 Quy tắc render

1. Trong một thí nghiệm, ảnh train và ảnh eval cùng một renderer [Đề xuất]. Mặc định là render Isaac qua Replay & Render cho dữ liệu train, eval ở `mujoco_isaac`, vì checkpoint của tác giả train trên ảnh Isaac. Nếu G0 cho thấy Ψ₀ giữ được độ chính xác ở `mujoco`, chuyển sang `mujoco` cho mọi bước và ghi `Decision`.
2. Video demo luôn render Isaac.
3. Báo cáo ghi renderer ở mọi con số.

### 4.3 Ước lượng chi phí eval

Ước lượng (chưa đo): một điểm của đường cong HE (một biến thể, một mức demo, một seed) chạy 30 điều kiện × 3 mức = 90 episode. Với 8 phút mỗi episode ở `mujoco_isaac`, mỗi điểm khoảng 12 giờ máy; 3 biến thể × 4 mức demo × 1 seed là 12 điểm, khoảng 144 giờ máy. Đây là lý do S1-04 phải đo thời gian thật ở cả hai chế độ, và lý do mục 7.4 có phương án rút gọn.

### 4.4 Thiết bị teleop

PICO không có trong kế hoạch. Nếu đội mua được bộ PICO 4 cùng tracker, dùng thẳng đường teleop của tác giả; bàn phím vẫn giữ để thu correction nhanh.

## 5. Ba nguồn dữ liệu robot

### 5.1 Dataset có sẵn của tác giả

Gói `psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (203 MB), định dạng LeRobot của fork Ψ₀ (`CODEBASE_VERSION = "v2.1"`). Đây là "bộ dataset có sẵn" của ý 3. Số episode, số đạt QA (N_teleop, câu Q1) và tần số chưa biết; S1-07 đo.

### 5.2 Teleop bàn phím [Đã chốt có bàn phím; cách làm là Đề xuất]

SIMPLE không có bàn phím, nên đội viết một **thiết bị bàn phím** cắm vào đường teleop decoupled WBC của SIMPLE, thay cho luồng PICO. Nhờ vậy dữ liệu bàn phím chạy **cùng bộ điều khiển** với dữ liệu teleop của tác giả.

| Phần | Cách làm |
|---|---|
| Chỗ cắm | Lớp nhận lệnh của `teleop_decoupled_wbc`: thay đầu vào tư thế đầu và cổ tay của PICO bằng tư thế sinh từ phím; lệnh đi bộ đi qua chế độ PLANNER (joystick) của WBC. Cách cắm cụ thể kiểm khi đọc mã SIMPLE ở nhiệm vụ con đầu của DA-16 |
| Đi | Phím vận tốc tiến, lùi, sang ngang, xoay (đi vào planner đi bộ của WBC) |
| Tay | Chọn tay trái hoặc phải; phím dịch cổ tay theo x, y, z và xoay; IK của SIMPLE đổi thành tư thế thân trên |
| Bàn tay | Một phím đóng, một phím mở cho mỗi tay |
| Episode | Phím bắt đầu, thành công, thất bại, reset; scorer chấm lại sau, nhãn của người chỉ để đối chiếu |
| Ghi | Bộ ghi LeRobot có sẵn của SIMPLE (`--record`), cộng `meta` riêng: `source = teleop_keyboard`, người điều khiển, hạt giống điều kiện, phiên bản SIMPLE |
| Giờ người | Mỗi phiên ghi một mục sổ chi phí: phút người, số episode, số episode đạt |

Giới hạn phải nêu: demo bàn phím chậm và kém mượt hơn PICO. Dùng tốt để so các phương pháp với nhau trên cùng nguồn, và để thu correction từ trạng thái lỗi; không dùng để nói số tuyệt đối về dữ liệu người thật. Đo giờ người cho 20 demo thử ở tuần đầu rồi mới chốt số demo cần thu.

### 5.3 Sinh tự động

Hai tuyến, chọn bằng câu V3 (spec mục 2.4) ở G0 [Option]:

| Tuyến | Cách làm | Bộ điều khiển | Ưu | Nhược |
|---|---|---|---|---|
| A · Planner trong env WBC | Script đi bộ (lệnh vận tốc tới WBC) cộng cuRobo cho đích hai tay, chạy trong env Teleop của task hai bàn | Decoupled WBC, giống dữ liệu teleop | Trộn được với teleop như cùng một nguồn | Phải tự viết; tương ứng tuyến T3 của spec mục 10 |
| B · Biến thể MP của SIMPLE | Viết task `G1WholebodyLocomotionPickBetweenTablesMP-v0` theo mẫu của `PickAndBendPlaceMP-v0` (đế đi theo script, cuRobo, AMO), chạy bằng `datagen` | AMO | Dùng gần như nguyên đường `datagen` của tác giả | Khác bộ điều khiển với teleop; trộn với teleop là câu V3, tương ứng tuyến T4 |

Checkpoint `…locomotionpickbetweentablesmixed-v0` của tác giả gợi ý họ đã trộn hai nguồn cho đúng task này. Nhiệm vụ con đầu của S1-11 đọc `run_config.json` và `argv.txt` của checkpoint đó để biết họ trộn gì và qua bộ điều khiển nào, trước khi chọn tuyến.

Sau demo: biến thể kiểu MimicGen từ đoạn teleop (tầng S2) và correction từ trạng thái lỗi đã lưu.

Mỗi episode sinh tự động ghi `source_kind = synthetic`, `synthetic_tier = S1`, `action_quality = planned`, tuyến và phiên bản planner. Không sinh với tham số của Level 1 hoặc Level 2 (spec mục 7.3).

## 6. Pipeline data flywheel: xử lý và chuẩn hóa dataset

[Đã chốt: data flywheel gồm cả xử lý và chuẩn hóa dataset.] Mọi nguồn đi qua cùng sáu tầng; mỗi nguồn hiện thực khác nhau ở tầng 1–4.

```text
1 Ingest      tải thô, sha256, Source kèm giấy phép và data_class
2 Normalize   giải mã, đồng bộ thời gian, đổi đơn vị và khung, ánh xạ vào action_layout
3 Annotate    cắt đoạn theo bước task, nhãn ngôn ngữ
4 QA          7 phép kiểm của spec mục 4.4, phép kiểm riêng của nguồn, phát lại action
5 Release     manifest đóng băng, guard chia tập, giấy phép gộp
6 Export      LeRobot v2.1 cho Ψ₀ (bắt buộc), v3 (tùy chọn), stats, contract test
```

### 6.1 Định dạng episode chung

Bundle theo 03 mục 7.2 (`frames.parquet`, `signals.parquet`, `videos/`, `meta.json`), thêm:

| Trường | Ở đâu | Nội dung |
|---|---|---|
| `source_kind` | Episode | `teleop`, `synthetic`, `egocentric` |
| `source_detail` | Episode `meta` | `psi_data`, `teleop_keyboard`, `teleop_pico`, `planner_wbc`, `planner_amo` |
| `synthetic_tier` | Episode `meta` | `S1`–`S4`, null nếu không phải synthetic |
| `action_quality` | Episode | `measured`, `planned`, `retargeted`, `pseudo`, `none` |
| `embodiment_id` | Episode | `g1_sonic_dwbc@1` (teleop, planner WBC), `g1_wholebody_amo@1` (planner AMO), `human_ego@1` |
| `renderer` | Episode `meta` | `mujoco`, `isaac` |
| Nhóm state và action | `frames.parquet` | Cột theo `action_layout`, hậu tố `_cmd` (lệnh gửi) và `_meas` (đo được) |
| Camera | `meta.json` | Nội và ngoại tham số, fps, `t_image` từng khung |
| Ngôn ngữ | `segments.parquet` | Mỗi dòng một đoạn: `t_start`, `t_end`, `step_id`, mô tả, nguồn nhãn (`rule`, `human`, `model`) |
| Lỗi cấy | Episode `meta` | `injected_defect` (mã lỗi, tham số) chỉ trên bản sao dùng để chấm Agent QA/QC; không bao giờ có trong release train |

Quy tắc: episode `planned` và `measured` khác `embodiment_id` không trộn trong một release nếu chưa có `Decision` của câu V3 (ADR-08 của 03). Episode `pseudo` hoặc `retargeted` không vào train nếu RunPlan không cho phép.

### 6.2 Normalize

| Việc | Cách làm |
|---|---|
| Đồng bộ | Mọi luồng về đồng hồ chung; nội suy state về tần số điều khiển; giữ `t_image` riêng từng camera |
| Đơn vị và khung | SI, radian; khung theo URDF của G1 trong SIMPLE |
| Ánh xạ action | Vào `action_layout` của G1 đệm 36 chiều như Ψ₀ (`pad36`), kèm mask cho chiều đệm |
| Ảnh | Đổi kích thước theo config fine-tune SIMPLE của Ψ₀ (180 × 320), giữ bản gốc |
| Ngôn ngữ | Câu lệnh task chuẩn hóa một mẫu cho mọi nguồn |
| Nguồn AMO | Bộ ánh xạ riêng từ không gian lệnh AMO sang `action_layout`; chỉ dùng khi V3 cho phép |

### 6.3 QA

Bảy phép kiểm của spec mục 4.4, ngưỡng hiệu chỉnh từ episode thành công của dataset tác giả. Thêm theo nguồn:

| Nguồn | Phép kiểm thêm |
|---|---|
| psi-data | Số khung video khớp số dòng; `tasks` có câu lệnh |
| Bàn phím | Khoảng dừng dài (người buông phím); bước nhảy lệnh cổ tay; episode người bấm "thành công" mà scorer chấm hỏng |
| Sinh tự động | Rollout lại trong sim đạt; tỉ lệ sinh đạt theo tuyến |

**Phát lại action** trên MuJoCo của SIMPLE cho mọi episode có action robot [giữ từ design 25/10]:

| Chế độ | Cách chạy | Bắt được | Đầu ra |
|---|---|---|---|
| Động học | Đặt `qpos` theo state đã ghi, từng khung | Sai ánh xạ khớp, sai đơn vị, vượt giới hạn, ảnh lệch thời gian với state | Video ghép cạnh video gốc; danh sách khung lỗi |
| Động lực học | Từ state đầu, áp action đã ghi qua bộ điều khiển của sim | Action không tái tạo được state (sai tần số, delta hay tuyệt đối, sai dấu), thời điểm đóng mở tay lệch | Sai lệch state theo thời gian và theo nhóm action; kết quả task khi phát lại |

Ngưỡng động lực học lấy phân vị 99 trên episode thành công. Trượt động học thì loại; trượt động lực học thì đánh dấu cho kỹ sư xem. Chỗ cắm là `SimulatorAdapter.replay()` của adapter SIMPLE.

Mẫu bị loại vẫn giữ cùng lý do và chi phí; không xóa âm thầm.

### 6.4 Export

| Đích | Yêu cầu |
|---|---|
| LeRobot v2.1 (bắt buộc) | Đúng fork `songlin/lerobot@09929d8`; `stats_psi0.json` tính trên đúng release; contract test đọc lại bằng loader Ψ₀ ở commit đã ghim |
| LeRobot v3 (tùy chọn) | Chuyển từ bản v2.1 bằng script chính thức của LeRobot; đọc lại bằng `lerobot` bản mới |

**Checklist chuẩn hóa LeRobot**, chạy tự động trong contract test:

1. `meta/info.json`: `codebase_version`, `fps`, `robot_type`, `features` khớp shape và tên từng chiều với `action_layout`.
2. `episode_index`, `index` liên tục; `frame_index` bắt đầu từ 0 mỗi episode.
3. `timestamp` khớp `frame_index / fps` trong dung sai nửa chu kỳ.
4. Video giải mã được, số khung khớp số dòng; codec và độ phân giải đúng khai báo.
5. `tasks` có câu lệnh cho mọi episode.
6. Stats tính trên đúng release, không NaN; chiều đệm có mask.
7. Đọc lại bằng loader Ψ₀ ra đúng một batch mẫu đã lưu (so từng giá trị).

### 6.5 Báo cáo dataset

Mỗi release có một trang HTML tĩnh: số episode theo nguồn, pass, flag, reject theo phép kiểm; phân bố điều kiện so với dải train; độ dài episode; stats theo nhóm action; vài video phát lại cạnh video gốc. Đây là phần "hiệu suất pipeline" của demo 17/11.

### 6.6 Egocentric

Thí nghiệm HE dùng checkpoint của tác giả nên **không cần** pipeline egocentric trước demo. Sau demo, nếu còn thời gian: nạp mẫu EgoDex qua cùng 6 tầng (`source_kind = egocentric`, không có action robot) để bộ probe P1, P2 có dữ liệu (mục 8.3).

## 7. Thí nghiệm HE: dữ liệu egocentric giảm demo robot cần

### 7.1 Giả thuyết

**HE · Prior egocentric giảm demo robot cần.** Với cùng số demo robot fine-tune, Ψ₀ có VLM pretrain trên EgoDex đạt tỉ lệ thành công cao hơn Ψ₀ có VLM không pretrain trên EgoDex; tương đương, nó đạt cùng tỉ lệ thành công với ít demo robot hơn.

Đây là **kiểm lại** claim của tác giả, trên một task mới (hai bàn trong SIMPLE) và theo một cách tác giả chưa báo (đường cong theo số demo). Không phải đóng góp thuật toán.

### 7.2 Biến thể

| Mã | VLM (stage 1) | Action expert (stage 2) | Dữ liệu egocentric |
|---|---|---|---|
| V-EGO | `pre.fast.1by1.2601091803.ckpt.ego200k.he30k` | `postpre.1by1.pad36.2601131206.ckpt.he30k` | EgoDex đủ, cộng HE |
| V-EGO10 | `pre.abl.ego.10per.2602021632.46k` | `postpre.abl.ego.10per.2602050006` | 10% EgoDex |
| V-NOEGO | `pre.abl.only.he.2512311516.48k` | `postpre.abl.only.he.2602050012` | Không EgoDex, chỉ HE |

V-EGO10 là tùy chọn, chạy khi còn ngân sách sau V-EGO và V-NOEGO [Đề xuất].

**Giới hạn phải nêu**: ba biến thể khác nhau cả số bước pretrain (200k + 30k, 46k, 48k) và có action expert post-train riêng. Đây là cách tác giả làm ablation; đội không tách được hai yếu tố. Ghi rõ trong báo cáo, và hỏi PSI Lab số bước của từng run nếu chưa rõ.

### 7.3 Thiết kế

| Mục | Giá trị [Đề xuất] |
|---|---|
| Task | Task hai bàn (mục 3) |
| Lưới demo | N ∈ {10, 20, 40, 80} demo teleop đạt QA; 80 là mức tác giả dùng. Nếu N_teleop < 80 thì điểm cuối là N_teleop |
| Chọn demo | Một danh sách lồng nhau: 10 ⊂ 20 ⊂ 40 ⊂ 80, cố định bằng hash trong RunPlan, dùng chung cho mọi biến thể |
| Fine-tune | Recipe `finetune-simple-psi0.sh` của tác giả; cùng số bước, batch, learning rate cho mọi điểm; ghi trong RunPlan |
| Seed | 1 seed mọi điểm; thêm seed thứ hai ở N = 20 và N = 40 cho V-EGO và V-NOEGO (vùng dự kiến khác nhau nhiều nhất) |
| Eval | 30 điều kiện dev × 3 mức (Level 0, 1, 2 của SIMPLE), cùng hạt giống cho mọi biến thể; chế độ render theo mục 4.2 |
| Mốc so | Checkpoint `…locomotionpickbetweentablesteleop-v0` của tác giả, eval cùng điều kiện (G0) |
| Chỉ số chính | Tỉ lệ thành công theo cờ của SIMPLE, gộp ba mức, theo N |
| Chỉ số phụ | Theo từng mức; tỉ lệ đạt từng bước của scorer; **N₅₀**: số demo nhỏ nhất để đạt 50% (nội suy trên đường cong); chênh lệch V-EGO − V-NOEGO tại mỗi N |
| Khoảng tin cậy | Bootstrap theo điều kiện (và theo seed nếu có 2 seed), như spec mục 7.5 |

### 7.4 Hai giai đoạn

| Giai đoạn | Dữ liệu fine-tune | Hạn [Đề xuất] |
|---|---|---|
| HE-1 · dataset có sẵn | Demo teleop của tác giả cho task hai bàn | Kết quả sơ bộ (ít nhất N = 20 và N = 80 cho V-EGO, V-NOEGO) trước demo 17/11 |
| HE-2 · dataset tự xây | Demo bàn phím cộng dữ liệu sinh tự động qua pipeline mục 6 | Sau demo, khi đủ demo đạt QA |

**Phương án rút gọn** khi đo ở S1-04 cho thấy không đủ máy: eval ở `mujoco` nếu G0 cho phép (mục 4.2); giảm còn 20 điều kiện mỗi mức; bỏ V-EGO10; giữ hai điểm N = 20 và N = 80. Mọi rút gọn ghi `Decision` và ghi trong báo cáo.

### 7.5 Quy tắc diễn giải (chốt trước khi chạy)

- **HE đạt** khi cận dưới CI 95% của (V-EGO − V-NOEGO) > 0 ở ít nhất hai mức N, và N₅₀ của V-EGO nhỏ hơn của V-NOEGO.
- **HE âm** (hai đường chồng nhau hoặc V-NOEGO cao hơn) là kết quả hợp lệ và phải báo, kèm giải thích có thể: task trong sim gần phân phối của HE nhiều hơn EgoDex, hoặc khác biệt chỉ rõ ở N nhỏ hơn lưới.
- Kết quả trong sim; không suy ra số trên robot thật.

### 7.6 Benchmark và video demo

Báo cáo theo khuôn bảng của paper (thành công trên số lượt, theo mức) cộng đường cong theo N. Video: cùng điều kiện, ba cột V-EGO, V-NOEGO và checkpoint của tác giả, ở hai mức N; render Isaac.

### 7.7 Quan hệ với spec

HE dùng lại lưới E1 của spec mục 7.1 cho Ψ₀ (thêm biến thể V-NOEGO). Lưới chung giúp E1 và HE dùng chung một lần fine-tune V-EGO ở mỗi N. HS, HT, HD giữ nguyên và chạy sau demo.

## 8. Training, máy chạy và log

### 8.1 Code của tác giả

| Stage | Code | Đội dùng thế nào |
|---|---|---|
| 1 · VLM | `pretrain-*-psi0-fast.sh`, `trainers/pretrain.py` | Không train; dùng checkpoint `pre.*` |
| 2 · Action expert | `posttrain-*-psi0.sh`, `trainers/posttrain.py` | Không train; dùng `postpre.*` |
| 3 · Task | `finetune-simple-psi0.sh`, `trainers/finetune.py` | Fine-tune mọi điểm của HE, E1 và các nhánh |
| Baseline | `baselines/act`, `baselines/dp` | ACT, Diffusion Policy cho so sánh phương pháp (spec mục 3, M) |

Code của tác giả ghim commit trong RunPlan; adapter `TrainerAdapter` gọi script của họ, không sửa repo của họ.

### 8.2 Log

Log qua `accelerate` tới W&B có sẵn: `train/loss`, `lr`, `epoch`, `grad_norm_*`, `eval/*`. Không có sẵn: loss theo nhóm action, loss theo vị trí trong chunk, phương sai action dự đoán, phân bố độ mở bàn tay. Lớp bọc tính lại phần thiếu trên batch val từ output của model, ghi `metrics.jsonl` (nguồn sự thật), W&B offline chạy song song. Mỗi lần đổi commit ghim thì chạy lại bước đọc code, ghi bảng "có sẵn / thiếu / cách lấy" vào `docs/g0/`.

Mỗi lần train lưu: định danh (hash RunPlan, release, `action_layout`, checkpoint cha, commit Ψ₀), loss theo nhóm, động học tối ưu, dự đoán, tài nguyên (VRAM, thông lượng, GPU-giờ), checkpoint trung gian, eval closed-loop cuối job.

### 8.3 Probe theo stage

Checkpoint công bố không kèm log train, nên "output của stage" là kết quả chạy bộ probe cố định (có hash) trên checkpoint:

| Probe | Checkpoint | Đo gì |
|---|---|---|
| P1 · Hiểu cảnh | `pre.*` | Hỏi đáp có đáp án về vật, bàn, bước đang làm trên khung hình SIMPLE |
| P2 · Token action | `pre.*` | Loss token FAST trên egocentric giữ lại (mẫu EgoDex, sau demo) |
| P3 · Action offline | `postpre.*`, checkpoint fine-tune | Sai số action open-loop theo nhóm và vị trí trong chunk trên episode held-out |
| P4 · Giữ năng lực | Sau fine-tune | Chạy lại P1, P3 trên dữ liệu gốc để đo quên |

P1 chạy trên ba VLM của HE cho thấy biến thể nào hiểu cảnh hai bàn tốt hơn, là bằng chứng phụ cho HE.

### 8.4 Máy chạy

| Máy | Dùng cho |
|---|---|
| RTX 3060 12 GB | Dev, SIMPLE ở `mujoco`, teleop bàn phím, phát lại, Agent QA/QC (Nemotron Q4), ACT, DP, thử inference Ψ₀ |
| Colab Pro (A100, H100, qua CLI) | Fine-tune Ψ₀; eval nặng nếu chạy được Isaac Sim trên Colab (kiểm ở S1-04) |
| Laptop RTX 3050 4 GB | Chỉ dev không GPU |

Mọi dữ liệu của demo là `public` (psi-data, sim G1 đội tự sinh), nên **Colab dùng được cho mọi job** [Đề xuất]. Quy tắc `data_class` vẫn giữ trong mã: dữ liệu `internal` hay `restricted` không bao giờ đi ra dịch vụ hosted.

Job trên Colab phải tiếp tục được từ checkpoint (`--train.resume_from_checkpoint=latest`), lưu checkpoint ra kho bền định kỳ, và ghi compute unit vào sổ chi phí. Tổng GPU-giờ của HE cộng E1 là rủi ro ngân sách lớn nhất; S1-04 đo trước.

### 8.5 Eval bất đồng bộ

Ψ₀ cần khoảng 160 ms mỗi lần suy luận (số tác giả báo) và dùng real-time chunking. Chạy sim đồng bộ thì lỗi do trễ không bao giờ xuất hiện. Closed-loop eval có hai chế độ: **đồng bộ** để gỡ lỗi và so với code tác giả; **bất đồng bộ** (chèn độ trễ đo được từ log inference) để báo chỉ số của các nhánh HS, HT sau demo. HE và G0 báo ở chế độ đồng bộ để so được với tác giả [Đề xuất]. Log inference ghi đủ trường để dựng dòng thời gian (mục 9.3).

## 9. Agent QA/QC

### 9.1 Vị trí và quy tắc

```text
job dữ liệu / train / eval / infer ─► code tính số và dựng hình ─► Agent QA/QC viết báo cáo ─► AI Engineer duyệt (fw review)
```

| Điểm | Quyết định |
|---|---|
| Model | Nemotron 3.5 Bolt E4B 4GB chạy cục bộ trên 3060, ghim revision [Đã chốt 25/10] |
| Phạm vi | Báo cáo dataset (mục 6.5), log train, output từng stage, log inference, kết quả eval |
| Không được | Đọc `vault/`; tự chạy job; tự chọn dữ liệu; đưa số không có trong đầu vào |
| Số liệu | Mọi con số do code tính; agent diễn giải, xếp hạng, viết đề xuất và trích số |
| Ước lượng | Có khoảng, được lưu; khi có kết quả đo thì so lại để biết agent đáng tin tới đâu |
| Đầu ra | Báo cáo HTML tĩnh mỗi job: phát hiện, bằng chứng (đường dẫn hình và số), insight, đề xuất; kỹ sư ghi đồng ý hoặc ghi đè kèm lý do |

Nemotron chỉ đọc chữ: agent đọc metadata, số và chú thích đi kèm hình do code dựng, không nhìn ảnh hay video. Qwen3.5-4B là tùy chọn nếu trưởng nhóm muốn agent tự xem hình.

### 9.2 Bộ lỗi cấy: demo hiệu suất trước khi train [Đã chốt có demo trên dữ liệu; cách làm là Đề xuất]

Trưởng nhóm muốn Agent QA/QC có demo trên dữ liệu trước khi đội train model. Thay cho dữ liệu bịa, đội **cấy lỗi có đáp án vào dữ liệu thật** của tác giả:

| Nhóm | Lỗi cấy | Mã lỗi (mục 10) |
|---|---|---|
| Dữ liệu | Rơi khung ảnh; lệch thời gian ảnh và state; nhảy khớp; vượt giới hạn khớp; NaN; sai đơn vị (độ thay radian); đảo dấu một chiều action; episode hỏng nhưng gắn nhãn thành công; sai câu lệnh task; trùng episode; rò hạt giống holdout | D1–D8 |
| Log train | Phân kỳ; không học; quá khớp; một nhóm action không giảm; chiều chết; gradient VLM khác 0 khi khai đóng băng | T1–T8 |
| Log inference | Độ trễ p99 vượt ngưỡng; buffer cạn; giật ở ranh giới chunk | R1, R2 |

Log train và log inference cấy lỗi sinh từ `FakeTrainer` và log RTC giả của `flywheel-testkit` cho tới khi có log thật.

**Cách chấm**:

- Tỉ lệ cấy mỗi loại khoảng 5–10% số episode [Đề xuất]; đáp án khóa trước (hash) trong một file mà agent và code phát hiện không đọc được.
- **Precision và recall theo từng loại lỗi**, không gộp; **tỉ lệ báo nhầm** trên bản sạch (không cấy); thời gian từ lúc job xong tới lúc có báo cáo.
- Tách hai lớp: phép kiểm bằng code (QA tầng 4) bắt được gì, và agent thêm được gì (xếp hạng, giải thích, đề xuất đúng hay sai). Như vậy số đo không đổ công của code cho agent.
- Báo rõ "trên lỗi cấy". Lỗi tự nhiên của dữ liệu thật báo riêng khi có.

### 9.3 Biểu diễn output từng stage cho người

| Stage | Code dựng gì | Agent đọc gì |
|---|---|---|
| Dataset | Báo cáo mục 6.5 | Phép kiểm trượt nhiều nhất, nguồn tệ nhất, đề xuất sửa |
| 1 · VLM | Bảng ảnh: khung hình, câu hỏi, câu trả lời, đáp án | Tỉ lệ đúng P1 theo loại câu hỏi, các ca sai tiêu biểu |
| 3 · Action | Đồ thị action dự đoán so với thật theo nhóm và vị trí trong chunk; video MuJoCo phát lại action dự đoán cạnh action thật | Sai số theo nhóm, vị trí trong chunk bắt đầu lệch |
| Inference (RTC) | Dòng thời gian: gửi quan sát, độ trễ, chunk về, mức buffer, bước nhảy ở ranh giới chunk | Độ trễ p50, p99 so với chu kỳ điều khiển; tần suất buffer cạn |
| Eval closed-loop | Thành công theo mức, bước hỏng, video lượt lỗi | Cụm lỗi, liên kết tới evidence card |

### 9.4 Kiểm agent

Trước khi dùng trên log thật: chạy bộ lỗi cấy ở mục 9.2 làm bộ ca mẫu; chạy lại khi đổi model hoặc prompt; lưu kết quả có hash.

## 10. Định nghĩa lỗi

Lỗi chia theo nguồn tín hiệu. Ngưỡng hiệu chỉnh từ episode thành công và A/A test, lưu trong `configs/` có hash.

**F-DATA · Dữ liệu và pipeline** (QA và export; chặn train)

| Mã | Lỗi | Phát hiện | Xử lý |
|---|---|---|---|
| D1 | Sai schema | Thiếu cột của `action_layout` hoặc sai kiểu | Từ chối ingest |
| D2 | Lệch đồng bộ | Lệch `t_image` và `t_state` p99 > τ_sync | Cách ly, sửa bộ đọc |
| D3 | Action ngoài giới hạn | Vượt giới hạn khớp, vận tốc, gia tốc | Cách ly |
| D4 | Stats sai | `stats_psi0.json` không tính trên đúng release, hoặc chiều có độ lệch chuẩn 0 mà không mask | Chặn export |
| D5 | Rò chia tập | Trùng hạt giống hoặc gần trùng với holdout | Chặn release |
| D6 | Nhãn sai | Câu lệnh hoặc đoạn không khớp bước theo luật; nhãn thành công mâu thuẫn scorer | Đưa người duyệt |
| D7 | Phát lại trượt | Phát lại động học trượt (loại) hoặc động lực học vượt ngưỡng (đánh dấu) | Theo mục 6.3 |
| D8 | Synthetic hỏng | Rollout lại không đạt | Loại, ghi lý do và chi phí |

**F-TRAIN · Động học train** (từ `metrics.jsonl`; đánh dấu checkpoint, chỉ T1 dừng job)

| Mã | Lỗi | Phát hiện |
|---|---|---|
| T1 | Phân kỳ | Loss NaN hoặc Inf, hoặc tăng quá k lần giá trị nhỏ nhất trong cửa sổ W |
| T2 | Không học | Loss val giảm dưới x% sau N bước đầu |
| T3 | Quá khớp | Loss train giảm trong khi loss val tăng liên tiếp M lần đo |
| T4 | Mất cân bằng nhóm | Loss một nhóm không giảm trong khi nhóm khác giảm |
| T5 | Chiều chết | Phương sai dự đoán của một chiều không mask < ε |
| T6 | Sụp mode | Độ lệch chuẩn dự đoán so với thật dưới ngưỡng |
| T7 | Quên | P4 giảm quá ngưỡng so với checkpoint cha |
| T8 | Gradient bất thường | Gradient VLM khác 0 khi khai đóng băng; chuẩn gradient vượt ngưỡng nhiều lần |

**F-OFF · Offline** (P3): O1 sai số nhóm cao; O2 sai số tăng theo vị trí trong chunk; O3 lệch thời điểm đóng mở bàn tay; O4 action sau khử chuẩn hóa ngoài giới hạn.

**F-CL · Closed-loop**: kiểu lỗi của task (mục 3, spec mục 5.2), chấm bằng scorer từng bước.

**F-SYS · Runtime và hệ thống**: R1 độ trễ p99 > τ_lat; R2 buffer cạn; R3 bám lệnh WBC kém (`_cmd` so với `_meas` > τ_track); R4 lệch đồng bộ trên trace; R5 lệch calibration camera; R6 server lỗi (ghi `infra_status`, không tính là lỗi policy).

**Quy lỗi về stage** (sau kiểm hệ thống và kiểm dữ liệu, trước kiểm khả thi; kỹ sư xác nhận trên evidence card):

| Bằng chứng | Quy về | Can thiệp gợi ý |
|---|---|---|
| P1 sai trên khung hình của lượt lỗi | Stage 1 · nhận thức | Tăng cường thị giác; dữ liệu thêm ở điều kiện hình ảnh đó |
| P1 đúng, P3 nhóm liên quan cao | Stage 3 · học action nhóm đó | Thêm demo hoặc dữ liệu sinh cho bước k |
| P1 đúng, P3 thấp, closed-loop vẫn hỏng | Lệch phân phối khi chạy | Correction từ trạng thái lỗi |
| Lỗi mới sau fine-tune kèm T7 | Stage 3 · quên | Giảm learning rate, tăng replay |
| Ngoài miền train | Không phải lỗi stage | Chỉ báo cáo |

## 11. Demo ngày 17/11/2026

**Kịch bản** [Đề xuất], một lệnh chạy lại được cho mỗi phần:

| # | Phần | Cho thấy | Bằng chứng |
|---|---|---|---|
| 1 | Tái tạo Ψ₀ | Checkpoint của tác giả trên task hai bàn trong SIMPLE | Bảng so với 7/5/6; video Isaac |
| 2 | Thu dữ liệu | Teleop bàn phím một episode trực tiếp; vài episode sinh tự động | Video MuJoCo; mục sổ chi phí của phiên |
| 3 | Pipeline | Ba nguồn qua 6 tầng ra một release LeRobot v2.1 | Báo cáo dataset (mục 6.5); contract test xanh |
| 4 | Agent QA/QC | Chạy trên bản cài lỗi | Bảng precision, recall theo loại; một báo cáo mẫu |
| 5 | HE-1 | Đường cong sơ bộ V-EGO so với V-NOEGO | Đồ thị, bảng theo mức, video ba cột |
| 6 | Một vòng Failure → Data | Lượt thất bại → scorer → chẩn đoán → evidence card → đề xuất dữ liệu → sổ chi phí | Evidence card thật trên một cụm lỗi của eval HE |

**Chưa có ở demo** (nói thẳng khi trình bày): HE-2 trên dataset tự xây, HS, HT, HD, holdout.

**Thứ tự để kịp** [Đề xuất]: tuần 26/10 đọc mã và đo (S1-02, S1-03, S1-04, S1-07, S1-11 nhiệm vụ con đầu); tuần 2/11 thiết bị bàn phím, tuyến sinh tự động, pipeline trên psi-data, bộ lỗi cấy, fine-tune HE-1 đầu tiên; tuần 9/11 eval HE-1, Agent QA/QC trên bộ lỗi cấy, vòng Failure → Data trên eval HE, ghép kịch bản demo; 16/11 chạy thử toàn bộ.

## 12. Kiến trúc và cấu trúc mã

Giữ cấu trúc nhân và ba làn của 03 mục 7 (bản 0.6), bỏ phần robot DENSO:

| Thay đổi | Nội dung |
|---|---|
| Bỏ | `packages/denso-sim/`, `packages/flywheel-mujoco/`, `ros2_ws/`, `docker/ros2-sim/`, `.devcontainer/` cho ROS, `configs/embodiments/denso.yaml`, bảng topic MCAP |
| `flywheel-simple` | Từ "chỉ cho G0" thành **adapter simulator chính**: `SimpleSim` (`SimulatorAdapter`, gồm `replay()`), thiết bị bàn phím, tuyến sinh tự động, worker chạy trong môi trường SIMPLE |
| `configs/embodiments/g1.yaml` | `action_layout` 36 chiều của G1, `control_spec` theo decoupled WBC; bản AMO riêng nếu dùng tuyến B |
| `configs/sim/` | Tham số domain randomization của task hai bàn, dải hạt giống, chế độ render |
| Làn | Dữ liệu (`flywheel-data`), Đánh giá (`flywheel-eval`, gồm Agent QA/QC), Vòng quyết định (`flywheel-loop`) giữ nguyên; nhân giữ nguyên |

Lõi không đổi nguyên tắc: không import `simple`, `psi0`, `lerobot`, `torch`, `isaacsim`, `mujoco`.

## 13. Story

Người làm do Product Owner giao sau [Đã chốt]. Bảng dưới chỉ ghi việc.

| Story | Thay đổi |
|---|---|
| S1-01 | Đã xong |
| S1-02 | Mở rộng lại: SIMPLE đủ cho thu dữ liệu, sinh tự động và eval cả hai chế độ, task hai bàn |
| S1-03 | Giữ; thêm task hai bàn vào phần tái tạo |
| S1-04 | Giữ; đo trên task hai bàn, thêm thời gian eval ở `mujoco` và `mujoco_isaac`, thêm Colab |
| S1-05 | Mở lại: sinh tự động cho task hai bàn (Q2), tuyến A hoặc B theo S1-11 |
| S1-06 | Về lại SIMPLE: khôi phục trạng thái (Q3) và tách hình ảnh (Q4) |
| S1-07 | Mở lại: phân tích gói psi-data của task hai bàn (Q1, V1) |
| S1-08, S1-10 | Giữ |
| S1-09 | Về lại SIMPLE: tín hiệu từng bước và tập điều kiện cho task hai bàn |
| S1-11 | Mở lại: V3 cho task hai bàn, đọc checkpoint `…mixed-v0`, chọn tuyến |
| DA-15, DA-18, DA-22, DA-24 | Xóa (robot DENSO, video nhà máy, dataset BTC, ROS 2) |
| DA-16 | Viết lại: thiết bị bàn phím cho teleop decoupled WBC của SIMPLE |
| DA-17 | Viết lại: phát lại action trên MuJoCo của SIMPLE |
| DA-19, DA-21 | Giữ, bỏ phần DENSO |
| DA-20 | Giữ; thêm chạy trên bộ lỗi cấy (DA-27) |
| DA-23 | Viết lại: eval bất đồng bộ trên SIMPLE |
| DA-25 | Giữ, bỏ bảng topic MCAP |
| DA-26 (mới) | Thí nghiệm HE (mục 7) |
| DA-27 (mới) | Bộ lỗi cấy cho Agent QA/QC (mục 9.2) |
| DA-28 (mới) | Kịch bản demo 17/11 chạy trọn luồng (mục 11) |
| DA-01…DA-14 (chưa có file) | Giữ DA-01, DA-02, DA-03 (chạy trên psi-data, bàn phím, sinh tự động), DA-08, DA-09, DA-13; hoãn sau demo DA-04, DA-05, DA-06; bỏ DA-10, DA-11, DA-12, DA-14 (robot DENSO); DA-07 đã gộp vào DA-19 |

## 14. Câu hỏi còn mở

| Mã | Câu hỏi | Ai trả lời | Ảnh hưởng |
|---|---|---|---|
| Q-27A | Gói dữ liệu task hai bàn có bao nhiêu demo đạt QA (N_teleop)? | S1-07 | Điểm cuối của lưới HE |
| Q-27B | Checkpoint `…mixed-v0` trộn nguồn gì, qua bộ điều khiển nào? | S1-11 | Chọn tuyến sinh tự động |
| Q-27C | Ψ₀ eval ở `mujoco` có giữ độ chính xác như ở `mujoco_isaac`? | S1-03, S1-04 | Chế độ render của HE (mục 4.2), chi phí eval |
| Q-27D | Isaac Sim chạy được trên Colab không, hay eval Isaac phải chạy trên máy đội? | S1-04 | Lịch eval HE |
| Q-27E | Số bước pretrain của từng checkpoint ablation, và ablation có cùng recipe post-train không? | Hiếu hỏi PSI Lab | Giới hạn của HE (mục 7.2) |
| Q-27F | Đội có mua bộ PICO không? | Hiếu | Nguồn teleop thứ hai (mục 4.4) |
| Q0 | Checkpoint `pre.*`, `postpre.*` nào đã xác nhận không thấy dữ liệu task hai bàn? | Hiếu hỏi PSI Lab | Ghi giới hạn cho HE và E1 (spec mục 2.4) |

**Lựa chọn của người viết** (cần Hiếu xem khi duyệt): task hai bàn của SIMPLE thay cảnh tự dựng (mục 3); bước L-WALK (mục 3); quy tắc render (mục 4.2); cách cắm bàn phím (mục 5.2); hai tuyến sinh tự động (mục 5.3); lưới, seed và quy tắc diễn giải của HE (mục 7); Colab cho mọi dữ liệu public (mục 8.4); HE báo ở chế độ đồng bộ (mục 8.5); tỉ lệ cấy lỗi và cách chấm (mục 9.2); kịch bản demo (mục 11); danh sách story (mục 13).

## 15. Tài liệu bị thay

| Tài liệu | Xử lý |
|---|---|
| Design 23/10/2026 (pipeline dữ liệu, robot DENSO, bảng lỗi) | Đã xóa. Còn dùng: định dạng episode, 6 tầng, bảng lỗi, probe, quy lỗi về stage (mục 6, 8.3, 10). Bỏ: robot DENSO, robot thay thế 95%, task khay → máy, 21 mục xin DENSO, NIM trước demo |
| Design 25/10/2026 (MuJoCo, Agent QA/QC) | Đã xóa. Còn dùng: checklist LeRobot, phát lại action, code train và log, Agent QA/QC, eval bất đồng bộ (mục 6, 8, 9). Bỏ: robot DENSO trên MuJoCo, teleop bàn phím trên MuJoCo riêng, dataset BTC, egocentric nhà máy |
| Design chia làn 25/10/2026 | Đã xóa. Cấu trúc nhân và ba làn đã nằm trong 03 mục 7. Bỏ: `denso-sim`, ROS 2, hình vẽ robot DENSO. Người làm do PO giao lại |
| Spec v10.3 → v10.4 | Bỏ phần robot DENSO và MuJoCo riêng; task chính đổi sang task hai bàn; thêm HE; lộ trình theo demo 17/11 |
| 00 · Phân tích idea | Đã xóa: nội dung đã nằm trong spec và 01 |
| 05, 06 | Giữ làm lưu trữ, có ghi chú ở đầu file: 02, 03, 04 trích mã của chúng (ví dụ "06 #3", "05 AR3") làm vết quyết định |
| Story | Xóa DA-15, DA-18, DA-22, DA-24; viết lại hoặc mở lại theo mục 13 |

## Nguồn

- Ψ₀: [repo](https://github.com/physical-superintelligence-lab/Psi0) (README ở commit `cda3fdf`), [paper](https://arxiv.org/abs/2603.12263), [checkpoint](https://huggingface.co/USC-PSI-Lab/psi-model).
- SIMPLE: [repo](https://github.com/physical-superintelligence-lab/SIMPLE), [teleop decoupled WBC](https://psi-lab.ai/SIMPLE/docs/decoupled-wbc/teleoperation.html), [cài đặt teleop](https://psi-lab.ai/SIMPLE/docs/decoupled-wbc/teleop_decoupled_setup.html), [sinh bằng motion planning](https://psi-lab.ai/SIMPLE/docs/data_gen_mp.html), [task G1 decoupled](https://psi-lab.ai/SIMPLE/docs/tasks/g1_decoupled.html), [task G1 MP](https://psi-lab.ai/SIMPLE/docs/tasks/g1_mp_amo.html).
- Dữ liệu: [psi-data/simple](https://huggingface.co/datasets/USC-PSI-Lab/psi-data/tree/main/simple).
- Fork LeRobot của Ψ₀: <https://github.com/songlin/lerobot/tree/09929d8057b044b53aecaf5c6d7eb71f99e8beb9>.
- Nemotron 3.5 Bolt E4B 4GB: <https://research.nvidia.com/labs/nemotron/Nemotron-3.5-Bolt-E4B-4GB/>.
- Tổng hợp paper flywheel: [data-flywheel.md](../../references/data-flywheel.md).
