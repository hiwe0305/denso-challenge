# Design: pipeline dữ liệu đa nguồn, scale bằng synthetic và định nghĩa lỗi cho Ψ₀ trên G1 và robot DENSO

_Ngày 23/10/2026. Trạng thái: **đã duyệt** (trưởng nhóm, 23/10/2026), chưa có code. Đã đưa vào [spec v10.2](../../spec-v10-failure-to-data.md), [03-architecture](../../product/03-architecture.md) bản 0.4 và [07 · Chia việc](../../product/07-team-workflow.md); tài liệu này giữ phần chi tiết, không thay thế các tài liệu đó._

Quy ước trong tài liệu: **[Đã chốt]** là quyết định của trưởng nhóm trong buổi thảo luận 22–23/10/2026. **[Đề xuất]** là lựa chọn của người viết, trưởng nhóm cần xem lại. **[Option]** là hai phương án song song vì còn chờ DENSO trả lời.

## 1. Bối cảnh và lý do

Spec v10.1 dựng PoC trên Unitree G1 trong SIMPLE với Ψ₀. Ngày 23/10/2026 trưởng nhóm bổ sung ba điều:

1. **Robot chính là robot của DENSO** [Đã chốt]: một mobile manipulator gồm đế bánh xe, cột nâng thẳng đứng, hai tay nhiều khớp, gripper hai ngón và camera trên đỉnh cột (theo hình vẽ DENSO cung cấp). G1 vẫn được giữ.
2. **Dữ liệu thật đến từ nhà máy DENSO** [Đã chốt]: video egocentric của công nhân và dữ liệu teleop của robot DENSO.
3. **Cách dùng Ψ₀** [Đã chốt]: dùng lại checkpoint của tác giả. Stage 1 (VLM) giữ nguyên để transfer. Stage 2 (action expert) phải train lại cho robot DENSO. Stage 3 fine-tune theo task.

Ba nhu cầu cần tài liệu này trả lời:

- Một hệ thống nhận, xử lý và chuẩn hóa ba nguồn dữ liệu (egocentric, synthetic, teleop) thành dữ liệu train được cho Ψ₀.
- Một cách scale dữ liệu bằng synthetic, ưu tiên model trên NVIDIA NIM [Đã chốt].
- Một định nghĩa rõ ràng về "lỗi" đọc được từ log train, log fine-tune, kết quả eval và log inference. Mỗi stage phải ra được output để đánh giá riêng.

Task đầu tiên [Đã chốt]: **lấy linh kiện từ khay, đặt vào máy**, kèm layout trạm làm việc.

Hai quyết định thêm ngày 23/10/2026 [Đã chốt]: giữ đủ phạm vi, không cắt trước (mục 11); nếu DENSO gửi thông tin muộn thì dùng robot thay thế giống robot DENSO ít nhất 95% (mục 3.1).

## 2. Mục tiêu, không làm, phản mục tiêu

**Mục tiêu**

- G1. Một định dạng episode chung cho cả hai robot và ba nguồn dữ liệu, xuất được sang LeRobot đúng phiên bản loader của Ψ₀.
- G2. Pipeline xử lý cho từng nguồn, chạy được ngay trên dữ liệu công khai (psi-data cho G1, mẫu EgoDex cho egocentric) trong lúc chờ dữ liệu DENSO.
- G3. Thang synthetic nhiều tầng, mỗi mẫu ghi tầng sinh, chi phí và nguồn gốc, để sổ chi phí so được giá trị của từng tầng.
- G4. Mỗi lần train Ψ₀ lưu đủ log và output của từng stage để chấm riêng; checkpoint của tác giả cũng được chấm bằng bộ probe.
- G5. Một bảng phân loại lỗi thống nhất cho 5 nguồn tín hiệu (dữ liệu, train, eval offline, eval closed-loop, runtime), có quy tắc phát hiện và quy tắc quy lỗi về stage.
- G6. Danh sách thông tin cần xin DENSO (mục 9).

**Không làm**

- Không train lại stage 1 từ đầu. Continued pretraining stage 1 trên video DENSO chỉ là phương án tùy chọn (mục 5.3).
- Không deploy lên robot DENSO thật trong 12 tuần; robot DENSO chạy trong Isaac Sim. Robot thật thuộc L2.
- Không làm UI web; báo cáo vẫn là HTML tĩnh như 03-architecture.

**Phản mục tiêu** (vẫn chạy được nhưng coi là thất bại)

- Dữ liệu synthetic đẩy số thành công trong sim lên nhưng không có đối chứng cùng ngân sách, nên không biết nó có đáng tiền không.
- Gộp dữ liệu hai robot vào một release mà không có ánh xạ action rõ ràng (vi phạm ADR-08).
- Gửi dữ liệu nhà máy lên API bên ngoài khi DENSO chưa cho phép.
- Kết luận "lỗi do stage X" mà không có phép kiểm làm bằng chứng.

## 3. Hai embodiment

| | G1 (giữ lại) | Robot DENSO (robot chính) |
|---|---|---|
| Vai trò | Bàn thử: chạy được ngay, có số công bố của Ψ₀ để tái tạo, kiểm thuật toán Failure → Data (spec v10.1) | Đích của DENSO: task khay → máy, dữ liệu nhà máy |
| Simulator | SIMPLE (Isaac Sim 4.5 + MuJoCo) | Isaac Sim, cảnh trạm làm việc dựng từ layout DENSO [Đề xuất] |
| System-0 | Decoupled WBC `g1_sonic` | Bộ điều khiển đế, cột nâng, khớp tay và gripper (cần DENSO cung cấp, mục 9) |
| Stage 1 | `pre.*` của tác giả | `pre.*` của tác giả |
| Stage 2 | `postpre.*` của tác giả | **Train lại**: S2-A hoặc S2-B (mục 6.2) |
| Stage 3 | Fine-tune task SIMPLE | Fine-tune task khay → máy |
| Nguồn teleop | psi-data | Teleop DENSO |

**Không gian action của robot DENSO** [Đề xuất, chờ thông số]. Chia theo nhóm, mỗi nhóm là một đoạn của vector action:

| Nhóm | Số chiều dự kiến | Ghi chú |
|---|---|---|
| `base` | 3 (vx, vy, ωz) | Hoặc 2 nếu đế vi sai, không đi ngang |
| `lift` | 1 | Vị trí hoặc vận tốc cột nâng |
| `arm_l`, `arm_r` | 6–7 mỗi tay | Khớp tuyệt đối, hoặc tư thế đầu tay (EEF) nếu bộ điều khiển nhận EEF |
| `gripper_l`, `gripper_r` | 1 mỗi bên | Độ mở hoặc lệnh đóng/mở |
| `head` | 0–2 | Nếu camera đỉnh cột xoay được |

Tổng khoảng 18–22 chiều. Checkpoint stage 2 của tác giả có tên chứa `pad36`, gợi ý action được đệm tới 36 chiều; cần kiểm trong mã nguồn Ψ₀ (V-D1, mục 10). Mỗi embodiment khai `action_layout` trong cấu hình Embodiment: nhóm nào nằm ở chỉ số nào của vector 36 chiều, chỉ số nào là đệm, cùng mask để loss bỏ qua phần đệm.

### 3.1 Robot thay thế khi DENSO gửi thông tin muộn

[Đã chốt] Dùng một robot thay thế giống robot DENSO ít nhất 95%. Phần dưới định nghĩa "95%" thành con số đo được và cách dựng robot thay thế [Đề xuất].

**Cách dựng: robot thay thế tham số `denso_mm_proxy`.** Đội tự dựng URDF và USD từ hình vẽ DENSO, ghép các linh kiện có mô hình công khai:

- tay 7 khớp kiểu Kinova Gen3 (khớp tròn trong hình vẽ gợi ý dòng tay này; đây là phán đoán, chưa xác nhận);
- gripper hai ngón kiểu Robotiq 2F-85;
- cột nâng tuyến tính, đế bánh xe, camera trên đỉnh cột.

Mọi kích thước (chiều cao cột, khoảng cách hai vai, chiều dài link, vị trí camera, kích thước đế) nằm trong một file tham số. Khi DENSO gửi thông số, chỉ sửa file này rồi chấm lại; không phải dựng lại.

Không chọn sẵn một robot thương mại làm robot thay thế chính, vì chưa robot nào được biết là giống robot DENSO. Dự phòng nếu tự dựng tốn quá thời gian: **TIAGo++** (có cột nâng, hai tay 7 khớp, camera đầu; đã có công bố đưa vào Isaac Sim, [arXiv 2510.10273](https://arxiv.org/abs/2510.10273)). Trossen Mobile AI có sẵn USD cho Isaac Sim nhưng tay nhỏ 6 khớp, ít giống hơn.

**Thước đo giống.** Hai loại điều kiện.

Điều kiện bắt buộc (sai một điều là không đạt):

- Cùng cấu trúc: đế, cột nâng, hai tay, hai gripper, camera đỉnh cột; mỗi tay cùng số khớp, cùng loại và thứ tự khớp.
- Cùng loại đế (vi sai hoặc đa hướng) và cùng giao diện lệnh (khớp, EEF hoặc vận tốc).

Điểm thành phần, mỗi mục phải ≥ 0,95:

| Mục | Cách đo |
|---|---|
| Vùng với tới tại trạm | IoU voxel 1 cm giữa vùng với tới của gripper (robot thay thế so với robot thật), trong hộp bao quanh khay và đồ gá, đế ở vị trí đỗ |
| Kích thước link | 1 − sai lệch tương đối trung bình của chiều dài và offset các link |
| Giới hạn khớp | Tỉ lệ chồng lấp khoảng góc, trung bình theo khớp |
| Camera | Đạt 1 khi lệch vị trí ≤ 2 cm, lệch góc ≤ 2°, FOV và độ phân giải lệch ≤ 5%; ngoài các mức đó giảm tuyến tính |
| Gripper | 1 − sai lệch tương đối của hành trình và kích thước ngón |
| Động học | 1 − sai lệch tương đối của vận tốc và gia tốc tối đa của khớp, cột nâng và đế |

Đạt "giống 95%" khi mọi điều kiện bắt buộc đúng và mọi điểm thành phần ≥ 0,95. Dùng ngưỡng cho từng mục thay vì trung bình, để một mục rất lệch (ví dụ vùng với tới) không bị các mục khác che. Bộ chấm là một lệnh `fw embodiment score`, ghi `Decision` `milestone`.

Trước khi có thông số, chỉ chấm được so với kích thước ước từ hình vẽ. Báo cáo ghi rõ "chấm so với hình vẽ", không ghi là đã đạt 95% so với robot thật.

**Khi chuyển sang robot thật.**

- `embodiment_id` khác nhau (`denso_mm_proxy@0` và `denso_mm@0`); không trộn trong một release nếu không có ánh xạ (ADR-08).
- Dữ liệu S1–S2 sinh trên robot thay thế giữ lại nếu điểm ≥ 0,95; ngược lại sinh lại trên robot thật.
- Checkpoint stage 2 train trên robot thay thế dùng làm khởi tạo cho stage 2 của robot thật, như một phương án thứ ba S2-C, đo cùng cách với S2-A và S2-B (mục 6.2).
- Teleop của DENSO luôn gắn với robot thật; robot thay thế chỉ có dữ liệu synthetic.

## 4. Định dạng episode chung

Mọi nguồn dữ liệu được chuẩn hóa về một bundle episode trước khi vào catalog, theo đúng bố cục 03-architecture mục 7.2 (`frames.parquet`, `signals.parquet`, `videos/`, `meta.json`). Tài liệu này thêm các trường sau.

| Trường | Ở đâu | Nội dung |
|---|---|---|
| `source_kind` | Episode | `teleop`, `egocentric`, `synthetic` |
| `synthetic_tier` | Episode `meta` | `S1`–`S4` (mục 5.2), null nếu không phải synthetic |
| `action_quality` | Episode | `measured` (đo từ robot), `planned` (planner sinh), `retargeted` (chuyển từ tay người), `pseudo` (suy ra từ video bằng model), `none` |
| `embodiment_id` | Episode (đã có) | `g1_sonic_dwbc@1`, `denso_mm@0`, `human_ego@1` |
| Nhóm state và action | `frames.parquet` | Cột theo nhóm của `action_layout`, có hậu tố `_cmd` (lệnh gửi) và `_meas` (đo được) |
| Camera | `meta.json` | Nội tham số, ngoại tham số, tên link gắn, fps, `t_image` từng khung |
| Ngôn ngữ | `segments.parquet` (mới) | Mỗi dòng một đoạn: `t_start`, `t_end`, `step_id` theo TaskDefinition, mô tả ngôn ngữ, nguồn nhãn (`human`, `cosmos_reason`, `rule`) |
| Riêng tư | Episode | `data_class` (đã có) cộng `deid_status` (`raw`, `blurred`, `verified`) |

Quy tắc:

1. Episode có `action_quality` là `pseudo` hoặc `retargeted` không bao giờ vào stage 2 hay 3 nếu không có cờ cho phép trong RunPlan, và luôn được báo riêng trong release.
2. Episode `human_ego` không có action robot; chúng chỉ vào probe, continued pretraining tùy chọn và làm đầu vào cho bộ sinh (mục 5.3).
3. Xuất LeRobot là một bước export theo embodiment, kèm `stats_psi0.json` tính trên đúng release, chạy `patch_lerobot_meta.py` và contract test đọc lại bằng loader Ψ₀ (03-architecture mục 11).

## 5. Pipeline xử lý theo nguồn

Mọi nguồn đi qua cùng sáu tầng; mỗi nguồn hiện thực khác nhau ở tầng 2–4.

```text
1 Ingest      tải thô, sha256, Source kèm giấy phép và data_class
2 Normalize   giải mã, đồng bộ thời gian, đổi đơn vị và khung, ánh xạ vào action_layout
3 Annotate    cắt đoạn theo bước task, nhãn ngôn ngữ, che danh tính
4 QA          7 phép kiểm của spec mục 4.4 cộng phép kiểm riêng của nguồn
5 Release     manifest đóng băng, guard split, giấy phép gộp
6 Export      LeRobot theo embodiment, stats, contract test
```

### 5.1 Teleop (G1 và DENSO)

| Tầng | Việc | Ghi chú |
|---|---|---|
| Ingest | Nhận định dạng thô của DENSO (ROS bag, MCAP, hoặc MP4 kèm CSV/JSON; chờ mục 9) và gói psi-data | Mỗi định dạng một bộ đọc trong adapter `TeleopSource`, lõi không biết định dạng |
| Normalize | Đồng bộ mọi luồng về đồng hồ chung; nội suy state về tần số điều khiển; giữ `t_image` riêng từng camera; đổi sang SI và radian; ánh xạ khớp vào `action_layout` | Lệch đồng hồ giữa máy teleop và robot đo bằng sự kiện chung (ví dụ lệnh đóng gripper và khung ảnh gripper đóng) |
| Annotate | Cắt đoạn theo bước của task khay → máy (mục 7.1). Ưu tiên tín hiệu luật (gripper đóng/mở, vận tốc đế bằng 0); Cosmos Reason gợi ý ranh giới khi luật mơ hồ, người duyệt mẫu | Nhãn ngôn ngữ một câu cho cả episode, cộng nhãn từng đoạn |
| QA | 7 phép kiểm của spec, thêm: lệnh ngoài giới hạn khớp, gripper đóng mà không có vật, đế chạy khi tay đang gắp (nếu task cấm), tỉ lệ khung rơi theo camera | Ngưỡng hiệu chỉnh từ episode thành công |
| Export | LeRobot, `stats_psi0.json`, mask phần đệm | Contract test bắt buộc |

### 5.2 Synthetic: thang bốn tầng

Xếp từ rẻ và tin cậy nhất đến đắt và rủi ro nhất. Chỉ tầng S1–S2 có action đo được; S3 giữ action của mẫu gốc; S4 phải suy ra action.

| Tầng | Cách sinh | Công cụ | Action | Nhắm lỗi gì | Kiểm trước khi nhận |
|---|---|---|---|---|---|
| S1 · Planner trong sim | Motion planning từ điều kiện ban đầu ngẫu nhiên trong miền train | G1: datagen của SIMPLE (CuRobo). DENSO: CuRobo hoặc planner của Isaac Sim trên cảnh trạm làm việc | `planned` | THIẾU VÙNG PHỦ | Rollout lại trong sim đạt; QA |
| S2 · Biến thể từ teleop | Biến đổi đoạn teleop theo tư thế vật kiểu MimicGen; correction từ trạng thái lỗi đã lưu | Isaac Sim, IK của robot | `planned` | THIẾU VÙNG PHỦ, TRẠNG THÁI ĐẦU XẤU | Rollout lại đạt; khoảng cách tới demo gốc |
| S3 · Đổi ngoại hình | Giữ quỹ đạo và action, đổi hình ảnh: ánh sáng, vật liệu, nền theo ảnh nhà máy DENSO; điều khiển bằng depth, segmentation hoặc edge của render sim | **Cosmos Transfer** (NIM) | Giữ nguyên action gốc | NHẬN THỨC, khoảng cách sim → nhà máy, Level 1 | Cosmos Reason chấm tính nhất quán; vị trí vật trong video sinh khớp segmentation gốc (IoU) |
| S4 · Video task mới | Sinh video từ ảnh đầu cộng câu lệnh, kiểu GR00T-Dreams | **Cosmos Predict / Cosmos Generator** (NIM) | `pseudo`, suy ra bằng inverse dynamics model train trên teleop | Biến thể chưa có demo | Cosmos Reason loại video sai vật lý; chỉ dùng khi RunPlan cho phép; luôn báo riêng |

**Quy tắc scale** [Đề xuất]:

1. Đi theo thứ tự S1 → S2 → S3; chỉ mở S4 khi S1–S3 đã có số đo và còn ngân sách.
2. Mỗi tầng là một loại can thiệp trong bảng 6.10 của spec, có đơn giá đo trong sổ chi phí và tỉ lệ sửa được f_t riêng. Nhờ vậy flywheel tự học tầng nào đáng tiền.
3. Tỉ lệ synthetic trong batch ρ chọn trên dev, như spec mục 7.3.
4. Không sinh với tham số của Level 1 hoặc Level 2 của bộ đánh giá (chống rò, spec mục 7.3). S3 chỉ dùng phân phối ánh sáng và vật liệu lấy từ ảnh nhà máy, không lấy từ preset của bộ đánh giá.

### 5.3 Video egocentric: hai phương án

DENSO chưa xác nhận cách thu, nên giữ hai phương án [Option].

| | E-A · Chỉ video RGB | E-B · Có tracking tay và đầu |
|---|---|---|
| Thiết bị | Camera đội đầu hoặc kính | Thiết bị có hand tracking như Vision Pro (cách EgoDex thu), hoặc găng có cảm biến |
| Pose tay 3D | Ước lượng bằng model hand pose từ RGB, độ tin thấp | Đo trực tiếp |
| Tư thế camera | Ước lượng bằng visual SLAM | Đo trực tiếp |
| Ra được action dạng 48-DoF như EgoDex | Có, nhưng nhiễu; gắn `action_quality = pseudo` | Có; gắn `retargeted` sau khi chuyển định dạng H-RDT |

**Pipeline chung:** Ingest → **che danh tính** (khuôn mặt, thẻ tên, màn hình; bắt buộc trước mọi bước khác, `deid_status`) → cắt đoạn theo bước task (luật cộng Cosmos Reason, người duyệt mẫu) → pose tay và camera (E-A ước lượng, E-B đọc từ thiết bị) → chuyển sang định dạng action 48-DoF của pipeline H-RDT mà Ψ₀ dùng ở stage 1 → QA riêng (độ tin pose, tỉ lệ tay ra khỏi khung, độ rung).

**Bốn cách dùng, theo thứ tự ưu tiên** [Đề xuất]:

| Mã | Cách dùng | E-A | E-B |
|---|---|---|---|
| U1 | Bộ probe cho VLM stage 1: trên khung hình nhà máy, VLM có nhận ra linh kiện, khay, máy và bước đang làm không (mục 6.1) | Có | Có |
| U2 | Mẫu cho bộ sinh: ảnh đầu và câu lệnh cho S3, S4; ảnh tham chiếu ánh sáng, vật liệu nhà máy | Có | Có |
| U3 | Khuôn cấu trúc task: thứ tự bước, thời lượng, điểm hay hỏng của người làm, để hiệu chỉnh scorer và phân bố điều kiện | Có | Có |
| U4 | Continued pretraining stage 1 trên checkpoint `pre.*` (LoRA hoặc vài nghìn bước) để VLM quen cảnh nhà máy | Không khuyến nghị: action quá nhiễu | Tùy chọn, chỉ khi U1 cho thấy VLM yếu trên cảnh nhà máy và còn ngân sách |

Giới hạn phải nêu: stage 1 học chuyển động **bàn tay người**, còn robot DENSO cầm bằng **gripper hai ngón**. Giá trị chính của video egocentric nằm ở hình ảnh và cấu trúc task, không ở nhãn action.

### 5.4 Dùng NVIDIA NIM: hai phương án triển khai

| | N-A · API hosted | N-B · NIM tự host |
|---|---|---|
| Nơi chạy | build.nvidia.com hoặc endpoint NVIDIA quản lý | Container NIM trên máy đội hoặc máy thuê, API kiểu OpenAI |
| Dữ liệu được gửi | Chỉ dữ liệu `public`: sim G1, synthetic sinh từ sim, mẫu EgoDex | Mọi `data_class`, kể cả `restricted` của DENSO |
| Ưu | Không cần GPU lớn, bắt đầu ngay | Dữ liệu không rời hạ tầng; không phụ thuộc lịch ngừng API |
| Nhược | Model có thể bị ngừng (API hosted của Cosmos Reason1-7B ngừng 24/03/2026); dữ liệu rời hạ tầng | Cần GPU: Reasoner nano khoảng 23 GB (chạy trên 5090); Generator nano 58 GB BF16, khoảng 31 GB khi offload (nên chạy trên A100 80 GB thuê) |

**Bộ định tuyến** [Đề xuất]: adapter NIM nhận `data_class` của từng yêu cầu. `restricted` và `internal` chỉ đi N-B; `public` đi N-A nếu cấu hình bật, ngược lại đi N-B. Mọi lời gọi ghi `LedgerEntry` (số giây video, token, GPU-giây) và phiên bản model. Danh sách model và endpoint nằm trong cấu hình có hash, vì danh mục NIM thay đổi theo thời gian.

Vai trò từng model NIM:

| Model | Dùng ở đâu |
|---|---|
| Cosmos Reason (Reasoner) | Gợi ý cắt đoạn và nhãn ngôn ngữ; chấm và lọc mẫu S3, S4; mô tả lỗi trong rollout cho evidence card (chỉ là gợi ý, không thay phép kiểm) |
| Cosmos Transfer | Tầng S3 |
| Cosmos Predict / Generator | Tầng S4 |

## 6. Training và output từng stage

### 6.1 Chấm checkpoint của tác giả (stage 1 và stage 2 gốc)

Đội không có log train gốc của stage 1 và 2. "Output của stage" vì vậy được định nghĩa là **kết quả chạy bộ probe cố định trên checkpoint của stage đó**. Bộ probe được đóng băng trước khi train và có hash.

| Probe | Checkpoint | Đo gì | Dữ liệu |
|---|---|---|---|
| P1 · Hiểu cảnh | `pre.*` | Hỏi đáp có đáp án về vật, vị trí, bước đang làm; định vị linh kiện (điểm hoặc hộp) | Khung hình nhà máy (U1), khung sim G1 và DENSO |
| P2 · Dự đoán action token | `pre.*` | Loss autoregressive của token FAST trên egocentric held-out | EgoDex mẫu, egocentric DENSO nếu có E-B |
| P3 · Action offline | `postpre.*`, các checkpoint stage 2 mới | Sai số action open-loop theo nhóm và theo vị trí trong chunk | Episode teleop held-out của từng robot |
| P4 · Giữ năng lực | Mọi checkpoint sau fine-tune | Chạy lại P1 và P3 trên dữ liệu gốc để đo quên | Như trên |

### 6.2 Stage 2 cho robot DENSO: các phương án đo, không chọn trước

- **S2-A:** fine-tune action expert từ `postpre.*`, ánh xạ action DENSO vào khung 36 chiều, mask phần đệm.
- **S2-B:** khởi tạo lại action expert, train trên dữ liệu DENSO (teleop cộng S1–S3), VLM đóng băng như recipe gốc.

- **S2-C** (chỉ khi đã có robot thay thế, mục 3.1): khởi tạo từ checkpoint stage 2 đã train trên robot thay thế.

Chọn bằng P3 và closed-loop trên dev ở cùng số bước và cùng dữ liệu. Ghi kết quả vào `Decision` `milestone`. Nếu dữ liệu DENSO ít (vài giờ), dự đoán S2-A lợi hơn; đây chỉ là giả định cần đo.

### 6.3 Những gì mỗi lần train phải lưu

Mọi lần train (stage 2 mới, stage 3) chạy qua `TrainerAdapter` và ghi vào thư mục job:

| Nhóm | Nội dung | Tần suất |
|---|---|---|
| Định danh | Hash RunPlan, release, `action_layout`, recipe, checkpoint cha, commit mã Ψ₀, digest image | Một lần |
| Loss | Loss flow matching tổng; **loss theo từng nhóm action** (`base`, `lift`, `arm_l`, `arm_r`, `gripper_*`) và theo vị trí trong chunk; loss trên tập val cố định | Mỗi N bước |
| Động học tối ưu | Learning rate, chuẩn gradient (tổng và theo khối VLM / action expert), tỉ lệ cập nhật trên trọng số, số bước bị bỏ do NaN hoặc Inf | Mỗi N bước |
| Dự đoán | Phương sai action dự đoán theo chiều trên batch val (phát hiện chiều chết, sụp mode); phân bố độ mở gripper dự đoán so với thật | Mỗi lần val |
| Tài nguyên | Thông lượng mẫu/giây, VRAM đỉnh, GPU-giờ, thời gian dừng do I/O | Mỗi N bước |
| Checkpoint trung gian | Lưu mỗi K bước; mỗi checkpoint tự động chạy P3 (offline) và P4 | Mỗi K bước |
| Eval closed-loop | Checkpoint cuối, và checkpoint tốt nhất theo P3, chạy trên dev theo spec | Cuối job |

Log ở `metrics.jsonl` (03-architecture mục 3.1). Nếu script Ψ₀ gắn sẵn W&B thì chạy W&B ở chế độ offline song song, nhưng `metrics.jsonl` là nguồn sự thật.

## 7. Định nghĩa lỗi

### 7.1 Task khay → máy: các bước và kiểu lỗi

Vị từ là đề xuất; tham số lấy từ thông số DENSO (mục 9).

| Bước | Tên | Vị từ đạt |
|---|---|---|
| 1 | Vào vị trí | Đế dừng trong vùng đỗ trước trạm, sai lệch vị trí và hướng dưới ngưỡng |
| 2 | Tiếp cận | Gripper trong bán kính r_reach quanh linh kiện mục tiêu trong khay |
| 3 | Gắp | Gripper đóng có tiếp xúc, linh kiện rời khay quá h_grasp |
| 4 | Mang | Linh kiện vẫn trong gripper tới vùng phía trên đồ gá của máy |
| 5 | Đặt | Linh kiện nằm trong đồ gá, sai lệch vị trí và góc dưới dung sai lắp của máy |
| 6 | Nhả và lui | Gripper mở, tay rời vùng máy, linh kiện đứng yên trong đồ gá T_stable giây |

| Mã | Kiểu lỗi | Lớp chung | Dấu hiệu |
|---|---|---|---|
| L-NAV | Đỗ sai vị trí | approach | Hết giờ ở bước 1, hoặc sai lệch đỗ vượt ngưỡng |
| L-REACH | Không tới linh kiện | approach | Hết giờ ở bước 2 |
| L-GRASP | Gắp trượt hoặc gắp nhầm | grasp | Đóng gripper mà không giữ được, hoặc giữ linh kiện khác |
| L-SLIP | Rơi khi mang | carry | Mất tiếp xúc ở bước 4 |
| L-PLACE | Đặt lệch | place | Linh kiện ngoài dung sai đồ gá |
| L-INSERT | Kẹt khi lắp | place | Lực hoặc va chạm tăng tại đồ gá, linh kiện không vào hết |
| L-RELEASE | Nhả sai lúc | place | Nhả trước khi vào đồ gá, hoặc không nhả |
| L-COLLIDE | Va chạm | theo bước k | Tiếp xúc ngoài ý muốn với khay, máy, người mô phỏng hoặc chính robot |
| L-TIMEOUT | Đứng yên | theo bước k | Hết giờ không chuyển bước |
| L-UNKNOWN | Thiếu tín hiệu | không gán | Không đủ dữ liệu |

G1 giữ bảng của spec mục 5. Cả hai bảng dùng chung lớp lỗi (`approach`, `grasp`, `carry`, `place`, `balance`) để gộp được tỉ lệ sửa được giữa robot.

### 7.2 Bảng lỗi theo nguồn tín hiệu

Mỗi lỗi có mã, nguồn tín hiệu, quy tắc phát hiện và nơi xử lý. Ngưỡng hiệu chỉnh từ episode teleop thành công và từ A/A test; lưu trong `configs/thresholds/` có hash.

**F-DATA · Lỗi dữ liệu và pipeline** (phát hiện ở QA và export; chặn train)

| Mã | Lỗi | Quy tắc phát hiện | Xử lý |
|---|---|---|---|
| D1 | Sai schema | Thiếu cột của `action_layout` hoặc sai kiểu | Từ chối ingest |
| D2 | Lệch đồng bộ | Lệch `t_image` và `t_state` p99 > τ_sync | Cách ly episode, sửa bộ đọc |
| D3 | Action ngoài giới hạn | Lệnh vượt giới hạn khớp, vận tốc, gia tốc của robot | Cách ly |
| D4 | Stats sai | `stats_psi0.json` không tính trên đúng release, hoặc chiều có độ lệch chuẩn bằng 0 mà không bị mask | Chặn export |
| D5 | Rò split | Trùng seed, `layout_hash` hoặc gần trùng với holdout | Chặn release |
| D6 | Nhãn sai | Đoạn ngôn ngữ không khớp bước theo luật; Cosmos Reason bất đồng với luật | Đưa người duyệt |
| D7 | Danh tính chưa che | Egocentric có `deid_status = raw` khi rời bước 3 | Chặn mọi bước sau |
| D8 | Synthetic hỏng | S1–S2 rollout lại không đạt; S3 lệch IoU; S4 bị Reasoner loại | Loại, ghi lý do và chi phí |

**F-TRAIN · Lỗi động học train** (đọc từ log mục 6.3; đánh dấu checkpoint, không tự dừng job trừ T1)

| Mã | Lỗi | Quy tắc phát hiện |
|---|---|---|
| T1 | Phân kỳ | Loss NaN hoặc Inf, hoặc loss tăng quá k lần giá trị nhỏ nhất trong cửa sổ W; dừng job |
| T2 | Không học | Loss val giảm dưới x% sau N bước đầu |
| T3 | Quá khớp | Loss train giảm trong khi loss val tăng liên tiếp M lần đo |
| T4 | Mất cân bằng nhóm | Loss một nhóm (thường `gripper` hoặc `base`) không giảm trong khi nhóm khác giảm |
| T5 | Chiều chết | Phương sai dự đoán của một chiều không bị mask < ε trên batch val |
| T6 | Sụp mode | Phân bố action dự đoán hẹp hơn hẳn phân bố thật (tỉ lệ độ lệch chuẩn < ngưỡng) |
| T7 | Quên | P4 giảm quá ngưỡng so với checkpoint cha |
| T8 | Gradient bất thường | Chuẩn gradient của VLM khác 0 khi VLM được khai là đóng băng; hoặc chuẩn gradient vượt ngưỡng nhiều lần |

**F-OFF · Lỗi khi chạy offline** (P3 trên episode held-out)

| Mã | Lỗi | Quy tắc phát hiện |
|---|---|---|
| O1 | Sai số nhóm cao | Sai số action của một nhóm vượt τ theo nhóm |
| O2 | Sai số tăng theo chunk | Sai số ở cuối chunk lớn hơn đầu chunk quá tỉ lệ ngưỡng |
| O3 | Sai thời điểm gripper | Lệch thời điểm đóng/mở gripper so với thật > Δt |
| O4 | Lỗi khử chuẩn hóa | Action dự đoán sau khử chuẩn hóa nằm ngoài giới hạn robot |

**F-CL · Lỗi khi chạy closed-loop** (eval trong sim): bảng kiểu lỗi mục 7.1, chấm bằng scorer theo bước như spec mục 5.

**F-SYS · Lỗi runtime và hệ thống** (log inference và trace)

| Mã | Lỗi | Quy tắc phát hiện |
|---|---|---|
| R1 | Độ trễ | Thời gian suy luận p99 > τ_lat (Ψ₀ khoảng 160 ms mỗi lần chạy) |
| R2 | Tràn chunk | Real-time chunking hết action trước khi chunk mới tới |
| R3 | Bám lệnh kém | Sai số giữa `_cmd` và `_meas` theo nhóm > τ_track (WBC cho G1; đế, cột nâng, tay cho DENSO) |
| R4 | Lệch đồng bộ | Như D2 nhưng trên trace eval |
| R5 | Lệch calibration | `camera_params_hash` khác bản tham chiếu |
| R6 | Server lỗi | Health check thất bại, timeout; ghi `infra_status`, không tính là lỗi policy |

### 7.3 Quy lỗi về stage

Áp dụng cho lỗi F-CL đã qua kiểm hệ thống (F-SYS âm) và kiểm dữ liệu (F-DATA âm). Thêm vào sau bước 4 của thuật toán Failure → Data, trước phép kiểm khả thi. Mỗi quy tắc cho một **giả thuyết** kèm bằng chứng, kỹ sư xác nhận trên evidence card.

| Bằng chứng | Quy về | Can thiệp gợi ý |
|---|---|---|
| P1 sai trên chính khung hình của lượt lỗi (không định vị đúng linh kiện, khay hoặc đồ gá) | Stage 1 · nhận thức | S3 đổi ngoại hình; U4 nếu lặp lại nhiều cụm |
| P1 đúng, P3 cho nhóm liên quan cao trên episode held-out tương tự | Stage 2 hoặc 3 · học action của nhóm đó | Thêm dữ liệu teleop hoặc S1–S2 cho bước k; xem T4, T5 |
| P1 đúng, P3 thấp, closed-loop vẫn hỏng | Lệch phân phối khi chạy (lỗi tích lũy) | Dữ liệu phục hồi, correction (TRẠNG THÁI ĐẦU XẤU, KỸ NĂNG YẾU) |
| Lỗi xuất hiện sau fine-tune mà checkpoint cha không có, kèm T7 | Stage 3 · quên | Tăng replay, giảm learning rate |
| Lỗi nằm ngoài miền train (NGOÀI MIỀN) | Không phải lỗi stage | Chỉ báo cáo |

## 8. Gắn vào kiến trúc hiện có

| Phần mới | Nằm ở đâu trong 03-architecture |
|---|---|
| Bộ đọc teleop DENSO, pipeline egocentric | Adapter `TeleopSource` mới và package `flywheel-ingest` mới (ngoài lõi, vì cần thư viện video và pose) |
| Robot DENSO trong Isaac Sim | `SimulatorAdapter` mới `DensoIsaacSim`, nhận cả robot thay thế và robot thật qua cấu hình Embodiment; `TaskDefinition` mới `DensoTrayToMachine` |
| Robot thay thế và bộ chấm giống | File tham số trong `configs/embodiments/`; lệnh `fw embodiment score` (mục 3.1) |
| Tầng S1–S4 | `GeneratorAdapter` theo tầng; tầng là loại can thiệp trong `decide` |
| NIM | Adapter `NimClient` có bộ định tuyến theo `data_class` |
| Probe P1–P4 | Module `gate` mở rộng, bộ probe có hash như tập cổng |
| Log train mục 6.3 | `TrainerAdapter` ghi; `reports` vẽ |
| Bảng lỗi mục 7 | `qa` (F-DATA), `training` cộng `reports` (F-TRAIN, F-OFF), `scorer` (F-CL), `diagnosis` (F-SYS, quy lỗi về stage) |

Lõi không đổi nguyên tắc: không import thư viện model hay simulator.

## 9. Thông tin cần xin DENSO

**Robot**

1. Mô hình robot: URDF, MJCF hoặc USD, kèm mesh; khối lượng và quán tính từng link.
2. Đế: loại (vi sai hay đa hướng), vận tốc và gia tốc tối đa, kích thước, có định vị (odometry, LiDAR, bản đồ) không.
3. Cột nâng: hành trình, vận tốc, độ phân giải.
4. Mỗi tay: số khớp, giới hạn góc, vận tốc, mô-men; hãng và model tay.
5. Gripper: loại, hành trình, lực kẹp, có cảm biến lực hoặc vị trí không.
6. Cảm biến: số camera, vị trí gắn (đỉnh cột, cổ tay), loại (RGB, RGB-D), độ phân giải, fps, nội và ngoại tham số; cảm biến lực ở cổ tay nếu có.
7. Bộ điều khiển: giao diện lệnh (khớp, EEF, vận tốc), tần số điều khiển, ROS 1 hay ROS 2, tên topic; có sẵn mô hình trong Isaac Sim chưa.

**Dữ liệu teleop**

8. Thiết bị teleop (leader arm, VR, spacemouse), tần số ghi.
9. Định dạng thô và một episode mẫu; danh sách topic hoặc cột.
10. Số episode và số giờ hiện có, tỉ lệ thành công, có ghi episode hỏng không.
11. Có nhãn task, nhãn bước hoặc mô tả ngôn ngữ không.
12. Calibration camera và đồng bộ thời gian giữa các luồng.

**Video egocentric**

13. Thiết bị thu (quyết định E-A hay E-B), có hand tracking và head pose không.
14. Số giờ, số người, số task; video có âm thanh không.
15. Chính sách riêng tư: đã che mặt chưa, có được dùng để train và lưu trữ bao lâu.

**Trạm làm việc và task**

16. Layout trạm: bản vẽ hoặc CAD của khay, máy, đồ gá, kích thước và vị trí tương đối.
17. Linh kiện: CAD hoặc kích thước, khối lượng, vật liệu, số loại linh kiện, cách xếp trong khay.
18. Tiêu chí thành công: dung sai đặt vào đồ gá, thời gian chu kỳ mục tiêu, các lỗi không chấp nhận được (va chạm, rơi).
19. Điều kiện thay đổi trong nhà máy: ánh sáng, vị trí khay, loại linh kiện, có người đi lại không.

**Quyền dữ liệu**

20. Dữ liệu được phân loại thế nào; có được gửi lên API bên ngoài như build.nvidia.com không (quyết định N-A hay N-B).
21. Giấy phép dùng dữ liệu và model đã train; ai sở hữu kết quả.

## 10. Câu hỏi kỹ thuật cần kiểm khi có mã hoặc dữ liệu

| Mã | Câu hỏi | Ảnh hưởng |
|---|---|---|
| V-D1 | Ψ₀ đệm action tới 36 chiều thế nào, có mask trong loss không | S2-A khả thi không; cách khai `action_layout` |
| V-D2 | Script train Ψ₀ log được loss theo nhóm action không, hay phải thêm hook | Khối lượng việc ở mục 6.3 |
| V-D3 | Dữ liệu stage 1 cần định dạng gì (đầu ra của pipeline H-RDT) | U4 và chuyển đổi egocentric |
| V-D4 | NIM nào còn hoạt động tại thời điểm triển khai, giấy phép model và đầu ra sinh ra | Mục 5.4 |
| V-D5 | Cosmos Transfer có giữ đủ chính xác vị trí vật để action gốc còn đúng không | Tầng S3 dùng được tới đâu |
| V-D6 | Inverse dynamics model cho S4 cần bao nhiêu teleop để đủ tin | Có mở S4 hay không |

## 11. Thứ tự làm [Đề xuất]

Pha A chạy được ngay, không cần DENSO:

1. Định dạng episode chung, `action_layout` cho G1, export LeRobot cộng contract test.
2. Pipeline teleop trên psi-data (G1).
3. Log train mục 6.3 và bảng F-TRAIN, F-OFF trên một lần fine-tune G1.
4. Pipeline egocentric E-B trên mẫu EgoDex (có tracking sẵn); E-A trên cùng mẫu, bỏ dữ liệu tracking, để so độ tin của pose ước lượng.
5. Probe P1–P4 trên checkpoint `pre.*` và `postpre.*`.
6. NIM tự host Cosmos Reason trên máy 5090; S3 thử trên video sim G1.

7. Robot thay thế `denso_mm_proxy` trong Isaac Sim, cảnh trạm và task khay → máy, S1–S2 trên robot thay thế (mục 3.1). Bước này không cần chờ DENSO.

Pha B khi DENSO gửi thông tin: chấm lại robot thay thế theo thông số thật, bộ đọc teleop DENSO, `action_layout` thật, so S2-A, S2-B, S2-C.

**Năng lực** [Đã chốt: giữ đủ phạm vi, không cắt trước]. Ghi chú để quyết định này được theo dõi:

- Ước lượng khoảng 962 giờ của 04-delivery-plan **đã tính việc dùng AI viết mã** (04 mục 0). Dùng model mạnh hơn có thể làm k nhỏ hơn, nhưng chỉ đo được sau Sprint 1.
- Phần tài liệu này thêm chưa nằm trong 962 giờ. Ước thô ban đầu khoảng 160–220 giờ; ước chi tiết theo 14 story DA-01…DA-14 ở [07 mục 2.2](../../product/07-team-workflow.md) là khoảng **185–255 giờ**, dùng con số này.
- AI không rút ngắn được: GPU-giờ train và eval, thời gian chạy rollout, thời gian chờ DENSO, giờ người của thí nghiệm HD và duyệt nhãn.
- Quy tắc giữ nguyên của 04: đo k sau Sprint 1; nếu nhu cầu còn lại × k vượt 110% mức kế hoạch ở review G0, áp thứ tự cắt 04 mục 7.2, rồi cắt trong tài liệu này theo thứ tự: S4, U4, E-A trên dữ liệu thật, S2-B.

**Khi vượt thời gian: thay phần tự xây bằng API theo từng phần** [Đã chốt]. Trước khi cắt phạm vi, phần nào trễ thì chuyển sang dùng API hoặc dịch vụ có sẵn để ra sản phẩm nhanh hơn. Mỗi lần chuyển ghi một `Decision` kèm lý do và chi phí API vào sổ chi phí. Ánh xạ gợi ý [Đề xuất]:

| Phần tự xây | Thay bằng | Điều kiện |
|---|---|---|
| NIM Cosmos Reason tự host (gắn nhãn, cắt đoạn, chấm synthetic) | API hosted của NVIDIA | Chỉ dữ liệu `public` |
| Cosmos Transfer, Cosmos Predict tự host trên A100 | API hosted của NVIDIA nếu có | Chỉ dữ liệu `public`; kiểm model còn hoạt động (V-D4) |
| Model hand pose và SLAM tự chạy cho E-A | API hoặc model có sẵn của bên thứ ba | Dữ liệu đã che danh tính; DENSO cho phép gửi ra ngoài |
| Dựng robot thay thế từ đầu | TIAGo++ có sẵn (mục 3.1) | Chấm giống theo mục 3.1, báo điểm thật |

Quy tắc định tuyến theo `data_class` (mục 5.4) không bao giờ được nới khi chuyển sang API. Nhờ ranh giới adapter, mỗi lần chuyển chỉ là đổi cấu hình adapter, lõi không đổi.

## 12. Để lại cho người xây

- Chọn model hand pose cụ thể cho E-A và thư viện SLAM.
- Chọn giá trị ngưỡng ban đầu (sau đó hiệu chỉnh từ dữ liệu).
- Cách tổ chức mã trong `flywheel-ingest`.
- Chọn planner cụ thể cho robot DENSO trong Isaac Sim.

## Nguồn

- Ψ₀: [repo](https://github.com/physical-superintelligence-lab/Psi0), [trang dự án](https://psi-lab.ai/Psi0/).
- Cosmos NIM: [giới thiệu](https://docs.nvidia.com/nim/cosmos/latest/introduction.html), [support matrix](https://docs.nvidia.com/nim/cosmos/latest/support-matrix.html), [Cosmos Reason2-8B](https://build.nvidia.com/nvidia/cosmos-reason2-8b/modelcard), [Cosmos Reason1-7B](https://build.nvidia.com/nvidia/cosmos-reason1-7b/modelcard).
- GR00T-Dreams và GR00T-Mimic: [blog NVIDIA](https://developer.nvidia.com/blog/enhance-robot-learning-with-synthetic-trajectory-data-generated-by-world-foundation-models).
- MimicGen: [arXiv 2310.17596](https://arxiv.org/abs/2310.17596).
- Tổng hợp paper flywheel: [data-flywheel.md](../../references/data-flywheel.md).
