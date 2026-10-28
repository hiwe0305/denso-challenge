# Design: task bê khay công nghiệp trên SIMPLE (MuJoCo) và thí nghiệm egocentric thay một phần demo robot

_Ngày 28/10/2026. Trạng thái: **nháp, chờ trưởng nhóm duyệt**. Tài liệu này **thêm** một nhánh việc chạy song song với [design 27/10/2026](2026-10-27-g1-psi0-demo-design.md) [Đã chốt: song song]. Task hai bàn vẫn là task chính của data flywheel và của demo; Long, Thông, Hưng, Châu không đổi việc. Task bê khay và thí nghiệm của nó là nhánh của trưởng nhóm. Khi duyệt, thêm story mới và sửa story của trưởng nhóm kèm dòng change log; design 27/10 chỉ thêm một dòng trỏ tới tài liệu này. **Sửa chiều 28/10/2026** [Đã chốt]: bộ điều khiển đổi từ đường MP với AMO sang decoupled WBC (mục 4), sau khi S1-02 chạy được task hai bàn với decoupled WBC trên máy dev._

Quy ước như design 27/10: **[Đã chốt]** là quyết định của trưởng nhóm (Hiếu). **[Đề xuất]** là lựa chọn của người viết, cần duyệt. Số chưa đo là ước lượng.

## 0. Đọc nhanh

1. **Task mới hoàn toàn**: G1 bê một khay linh kiện bằng hai tay từ bàn A, đi qua hành lang, đặt khay vào vùng đích trên bàn B [Đã chốt]. Cảnh theo spec "Humanoid Industrial Tray Transfer" của trưởng nhóm (mục 3), chuyển từ Isaac Lab sang SIMPLE.
2. **Chỉ MuJoCo**: vật lý, ảnh camera của policy, thu dữ liệu, train và eval đều dùng MuJoCo của SIMPLE (`sim_mode=mujoco`, render offscreen EGL), với robot G1 của SIMPLE [Đã chốt]. Isaac Sim không nằm trên đường chính. Bộ điều khiển là **decoupled WBC** (robot `g1_sonic`, env `SonicLocoManipEnv`), như task hai bàn [Đã chốt 28/10/2026].
3. **Dữ liệu robot là synthetic sinh trong sim của task mới** [Đã chốt]. Task mới chưa có teleop PICO, nên "demo robot" chủ yếu là synthetic S1 (planner kịch bản trên decoupled WBC), thêm S2 và teleop bàn phím khi có (mục 5).
4. **Thí nghiệm chứng minh idea, theo đúng Ψ₀** [Đã chốt]: so công thức dữ liệu **100% demo robot** với công thức **egocentric của người đã qua data flywheel cộng demo robot bị cắt bớt**. Nếu nhánh có egocentric giữ được tỉ lệ thành công thì egocentric đã thay được phần demo bị cắt (mục 6).
5. **Thêm một nhánh đối chứng** [Đề xuất]: demo robot bị cắt bớt nhưng **không** có egocentric. Không có nhánh này thì không biết tỉ lệ thành công giữ được là nhờ egocentric hay vì task vốn không cần nhiều demo.
6. **Egocentric phải là video người làm đúng task bê khay** [Đề xuất]. Checkpoint gốc của Ψ₀ đã pretrain trên EgoDex, nên thêm EgoDex lần nữa không chứng minh được gì.
7. **Simulation trước, quay video sau** [Đã chốt]. Trước demo 17/11: task khay, synthetic, nhánh A và C, cộng tầng phụ dùng checkpoint ablation của tác giả (có và không có EgoDex), không cần video. Nhánh B chạy khi đã quay video; người quay chốt sau.
8. **Tính toán**: Colab Pro, thuê server khi cần [Đã chốt]. Không đặt trần cứng; mỗi job ghi sổ chi phí như mọi job khác.
9. **Song song với task hai bàn** [Đã chốt]. Bốn người làm data flywheel không đổi việc; nhánh này dùng lại pipeline và lõi của họ khi có (mục 8).

## 1. Bối cảnh và lý do

Trưởng nhóm muốn idea được chứng minh trên một task trông giống công việc trong nhà máy, thay cho task gắp một vật giữa hai bàn của SIMPLE. Không có dataset công khai nào cho humanoid bê khay trong nhà máy (tra ngày 28/10/2026: dataset G1 của Unitree chỉ có robot thật, thân trên; Humanoid Everyday, AgiBot World, RoboCOIN chủ yếu là cảnh nhà và văn phòng). Vì vậy dữ liệu robot phải sinh trong sim.

Câu hỏi idea phải trả lời: **dữ liệu egocentric của người, sau khi đi qua data flywheel, có giảm được số demo robot cần để Ψ₀ làm được task không?** Đây là giả thuyết HE của design 27/10, đổi sang task mới và đổi cách đo từ đường cong theo N sang so công thức trộn dữ liệu.

Task gần nhất có sẵn trong SIMPLE là `G1WholebodyXMoveBendCarryBoxSonic-v0` (bê hộp hai tay, có dữ liệu 178 MB và checkpoint `sonic-wbcbox`). Task này dùng bộ điều khiển SONIC chạy thành tiến trình riêng, khác decoupled WBC và AMO; đội có thể đọc nó làm mẫu cho động tác cầm hai tay khi đi, nhưng không dùng làm task chính.

## 2. Mục tiêu, không làm, phản mục tiêu

**Mục tiêu**

- T1. Task bê khay chạy trong SIMPLE ở `sim_mode=mujoco` với G1 dưới decoupled WBC: cảnh tĩnh đúng va chạm, `check_success`, ngẫu nhiên hóa có hạt giống, ảnh camera đầu (và cổ tay nếu G1 của SIMPLE có).
- T2. Sinh synthetic S1 cho task khay bằng planner, ra episode LeRobot đi qua pipeline 6 tầng của data flywheel.
- T3. Video egocentric người bê khay đi qua pipeline egocentric (che danh tính, cắt đoạn theo bước, pose tay và camera, QA, xuất stage 1 của Ψ₀).
- T4. Trước demo 17/11: nhánh A, C và tầng phụ (mục 6.2) có kết quả sơ bộ. Nhánh B có kết quả sau khi quay video.
- T5. Demo 17/11 thêm một phần ngoài kịch bản chính của design 27/10 mục 11: video G1 bê khay trong MuJoCo, bảng A, C và tầng phụ.

**Không làm**

- Isaac Sim, Isaac Lab cho task khay. Video đẹp bằng Isaac chỉ làm khi còn thời gian sau 14/11.
- Pretrain stage 1 từ đầu, post-train stage 2 từ đầu.
- Reward và học tăng cường. Spec gốc có mục reward; giữ hàm `compute_reward()` trả về giá trị đơn giản để không vỡ interface của SIMPLE, nhưng không thiết kế reward.
- Hàn khay vào tay robot hoặc dịch chuyển khay không qua tiếp xúc (spec gốc mục 2, 5).

**Phản mục tiêu** (vẫn chạy được nhưng coi là hỏng)

- Ba nhánh khác nhau ở chỗ khác ngoài dữ liệu: số bước fine-tune stage 3, hyperparameter, hạt giống điều kiện eval, renderer.
- Nhánh có egocentric "thắng" vì được thêm compute ở stage 1 mà báo cáo không nêu giới hạn này.
- Gọi synthetic là "teleop" trong báo cáo. Ghi đúng nguồn: `synthetic S1`, `synthetic S2`, `teleop_keyboard`.
- Kết luận từ một seed như kết quả chắc chắn.
- Task "đạt" nhờ khay dính vào tay, linh kiện bị khóa trong khay, hay cờ thành công lỏng hơn mục 3.4.

## 3. Task bê khay

### 3.1 Cảnh [Đã chốt theo spec của trưởng nhóm; kích thước là cấu hình]

| Thành phần | Giá trị mặc định | Ghi chú |
|---|---|---|
| Sàn | Mặt phẳng | |
| Bàn A (nguồn), bàn B (đích) | 1,2 × 0,8 × 0,85 m, hai bên hành lang | Khung kim loại, mặt bàn đặc, va chạm thật |
| Hành lang | 1,8 m trống giữa hai bàn | |
| Robot | G1 của SIMPLE, đứng giữa hai bàn, gần bàn A hơn | |
| Khay | 0,45 × 0,30 × 0,06 m, rigid body, hai tay cầm hai bên, khối lượng và ma sát thật | Kiểm cầm được bằng bàn tay G1 trước khi chốt kích thước (mục 7, mốc M0) |
| Linh kiện | 6 vật nhỏ trong 6 ô của khay | Rigid body tự do, không khóa vào khay |
| Vùng đích | Hình chữ nhật hiển thị trên bàn B: tư thế đích, dung sai vị trí, dung sai góc | |

Mọi kích thước, khối lượng, ma sát, dung sai nằm trong file cấu hình của task, không viết cứng.

### 3.2 Bước con

Spec gốc có 12 bước. Scorer gộp thành 7 bước có vị từ đo được [Đề xuất]:

| Bước scorer | Gồm bước spec | Vị từ đạt |
|---|---|---|
| 1 Tiếp cận A | 1–3 | Thân trong vùng trước bàn A; hai bàn tay trong bán kính r_reach quanh hai tay cầm |
| 2 Cầm | 4 | Cả hai bàn tay có tiếp xúc với tay cầm tương ứng |
| 3 Nhấc | 5 | Khay rời mặt bàn quá h_lift; đủ 6 linh kiện trong khay |
| 4 Mang | 6–7 | Thân rời vùng bàn A, đi về phía B; khay vẫn trong hai tay; góc nghiêng khay dưới θ_tilt; robot trong giới hạn thăng bằng |
| 5 Tới B | 8–9 | Thân dừng trong vùng trước bàn B; khay vẫn trong tay |
| 6 Đặt | 10 | Khay nằm trên bàn B, trong dung sai vị trí và góc của vùng đích |
| 7 Nhả và đứng | 11–12 | Hết tiếp xúc tay–khay; khay đứng yên T_stable giây; robot đứng |

Bước 1 của spec (quan sát) không có vị từ riêng.

### 3.3 Kiểu lỗi mới

Thêm vào bảng lỗi của spec mục 5.2 và design 27/10 mục 10 [Đề xuất]: **L-PART-DROP** (linh kiện rơi khỏi khay), **L-TRAY-TILT** (khay nghiêng quá θ_tilt khi mang), **L-ONE-HAND** (mất tiếp xúc một tay khi mang), **L-PLACE-POSE** (đặt ngoài dung sai). Giữ L-WALK và L-BALANCE.

### 3.4 Điều kiện thành công [Đã chốt theo spec gốc]

Thành công khi và chỉ khi cùng lúc: khay trên bàn B, trong dung sai vị trí và góc của vùng đích, đứng yên; robot đã nhả; robot vẫn đứng; đủ 6 linh kiện trong khay. `check_success()` của task và scorer bước 7 dùng cùng định nghĩa.

### 3.5 Ngẫu nhiên hóa

Ba mức, giống cách SIMPLE chia Level 0, 1, 2 [Đề xuất]:

| Mức | Thay đổi |
|---|---|
| 0 | Chỉ hạt giống vật lý; khay và vùng đích ở vị trí mặc định |
| 1 | Vị trí và góc khay trên bàn A, vị trí vùng đích trên bàn B, trong khoảng nhỏ |
| 2 | Thêm khoảng cách giữa hai bàn, vị trí đứng ban đầu, ánh sáng, khối lượng linh kiện |

Dải hạt giống của train, dev, holdout rời nhau, theo spec mục 7.3.

### 3.6 Quan sát

Quan sát của policy theo đúng đầu vào Ψ₀ cho G1 trong SIMPLE (ảnh, trạng thái khớp, câu lệnh). Trạng thái đặc quyền (tư thế khay, tư thế linh kiện, tiếp xúc, tư thế đích) tách riêng, chỉ cho scorer, planner và log, không cho policy [Đã chốt theo spec gốc mục 6].

## 4. Simulator và bộ điều khiển

- SIMPLE ở `sim_mode=mujoco`, render offscreen EGL cho ảnh policy. Train và eval cùng renderer MuJoCo, nên quy tắc "ảnh train và ảnh eval cùng renderer" của design 27/10 mục 4.2 tự đạt [Đã chốt].
- Hệ quả phải đo: checkpoint gốc của Ψ₀ train trên ảnh Isaac. Fine-tune stage 3 trên ảnh MuJoCo sẽ phải bù khoảng cách hình ảnh này. Ba nhánh cùng chịu, nên phép so giữa nhánh vẫn công bằng; số tuyệt đối không so được với số công bố.
- Task viết theo lớp `Task` của SIMPLE (`reset`, `check_success`, `state_dict`), lấy task hai bàn `g1_wholebody_locomotion_pick_between_tables_teleop.py` làm mẫu; uid `g1_wholebody_tray_transfer_teleop`, env id `simple/G1WholebodyTrayTransferTeleop-v0`. Hậu tố `Teleop` theo quy ước của SIMPLE chỉ họ bộ điều khiển (decoupled WBC), không phải nguồn dữ liệu.
- **Chỗ đặt mã của task** [Đề xuất]: trong `flywheel-simple`, đăng ký env id từ package của đội, không fork SIMPLE. Nếu SIMPLE không cho đăng ký task từ ngoài package, fork SIMPLE ở commit ghim, chỉ thêm file task và asset, ghi lý do.
- **Bộ điều khiển** [Đã chốt 28/10/2026]: **decoupled WBC** của GR00T, đường SIMPLE dùng cho mọi task `*Teleop-v0`: robot `g1_sonic`, env `SonicLocoManipEnv`, `physics_dt` 0,005, `render_hz` 50, `sonic_config` từ `gear_sonic` như `src/simple/cli/teleop_decoupled_wbc.py`. Thân dưới là policy RL `Balance.onnx` và `Walk.onnx` nhận `navigate_cmd`; thân trên nhận tư thế hai cổ tay qua `TeleopRetargetingIK` (IK thân trên và bàn tay của decoupled_wbc). Lý do: (a) đứng và đi đã chạy trên máy dev không cần cuRobo (S1-02, `docs/g0/env-simple.md`); (b) hai cổ tay đặt mục tiêu cùng lúc, hợp với cầm khay hai tay, trong khi MP agent của SIMPLE lên kế hoạch từng tay một; (c) cùng bộ điều khiển và `action_layout` với checkpoint Ψ₀ của task hai bàn và với teleop bàn phím (DA-16). Cái giá: synthetic không dùng `datagen` của SIMPLE mà dùng planner kịch bản của đội (mục 5); đây là tuyến A của design 27/10 mục 5.3.
- **Bộ điều khiển khi eval** [Đề xuất]: Ψ₀ chạy dưới **cùng decoupled WBC** với dữ liệu train, qua `eval-decoupled-wbc` của SIMPLE (agent `psi0_decoupled_wbc`), như checkpoint `…locomotionpickbetweentablesteleop-v0` của tác giả. Policy xuất toàn bộ action theo `action_layout` của đường này, kể cả lệnh đi; không có script đi khi eval, vì nếu đế đi theo script thì tỉ lệ thành công không đo policy. Việc đầu của DA-19 là đọc `eval-decoupled-wbc` và config fine-tune của checkpoint đó để xác nhận `action_layout` (cổ tay, bàn tay, `navigate_cmd`); planner của DA-33 ghi đúng các trường này.
- **Giới hạn thời gian episode** [Đề xuất]: 90 giây sim; hết giờ tính là thất bại (L-TIMEOUT). Đo thời gian episode synthetic ở M2; nếu trung vị trên 60 giây thì nâng giới hạn lên 1,5 lần trung vị và ghi `Decision`.
- Asset khay, linh kiện, bàn: hình học đơn giản (hộp, trụ) ở MJCF hoặc định dạng `Layout` của SIMPLE; không cần mesh đẹp.

## 5. Dữ liệu

| Loại | Nguồn cho task khay | Vào đâu | Ghi |
|---|---|---|---|
| Synthetic S1 | Planner kịch bản trên decoupled WBC: quỹ đạo hai cổ tay theo hình học tay cầm, `navigate_cmd` cho đi, đóng mở bàn tay; ghi bằng bộ ghi LeRobot của SIMPLE | Stage 3 | `source_kind = synthetic`, `synthetic_tier = S1`, `action_quality = planned` |
| Synthetic S2 | Biến thể từ episode S1 hoặc bàn phím (design 27/10 mục 5.4) | Stage 3 | Sau S1; không bắt buộc cho thí nghiệm sơ bộ |
| Teleop bàn phím | DA-16 trên task khay | Stage 3, và tập nhỏ để đối chứng nguồn | Chậm; dùng khi có |
| Egocentric | Video đội tự quay người bê khay giữa hai bàn, dựng cảnh giống task (mục 5.1) | Stage 1 | Qua pipeline egocentric (design 27/10 mục 6.6), pose E-A, `pseudo` |

Demo robot của thí nghiệm là synthetic S1 đạt QA [Đề xuất]. Nếu có đủ demo bàn phím, chạy lại thí nghiệm với bàn phím là phần phụ.

### 5.1 Quay video egocentric [Đã chốt: làm sau phần simulation; cách quay là Đề xuất; người quay, thiết bị và ngày chốt sau]

- Dựng hai bàn và một khay thật kích thước gần mục 3.1, hành lang khoảng 1,8 m.
- Người đeo camera ở đầu (điện thoại gắn mũ hoặc camera hành động), làm đủ chuỗi bước của mục 3.2, đổi vị trí khay, vùng đích và người làm.
- Che danh tính trước mọi bước xử lý khác (bất biến của repo).
- Ước lượng ban đầu: 1–2 giờ video, 2–3 người làm, khoảng 100–200 lượt. Chốt sau khi xem tốc độ của pipeline trên 20 lượt đầu.

Nếu chưa có video tự quay khi cần chạy nhánh B, dùng tập con EgoDex gần nhất (cầm vật hai tay) làm đường lui và ghi rõ yếu điểm: VLM gốc đã thấy EgoDex.

## 6. Thí nghiệm: egocentric thay một phần demo robot

### 6.1 Giả thuyết

**HE-T.** Trên task bê khay, Ψ₀ có stage 1 fine-tune thêm trên egocentric người bê khay (đã qua data flywheel), fine-tune stage 3 với **một nửa** số demo robot, đạt tỉ lệ thành công **không thấp hơn đáng kể** Ψ₀ fine-tune stage 3 với **đủ** demo robot; và **cao hơn** Ψ₀ fine-tune với một nửa demo mà không có egocentric.

### 6.2 Ba nhánh [Đề xuất]

| Nhánh | Stage 1 (VLM) | Stage 3: demo robot | Vai |
|---|---|---|---|
| A · đủ demo | Checkpoint gốc `pre.*` (Q0 của S1-03) | N_full | Baseline theo Ψ₀ |
| C · cắt demo | Checkpoint gốc `pre.*` | N_cut | Đối chứng: cắt demo mà không bù |
| B · cắt demo + egocentric | `pre.*` fine-tune thêm trên egocentric bê khay đã qua flywheel | N_cut | Nhánh chứng minh idea |

- "Qua data flywheel" ở nhánh B nghĩa là qua **pipeline egocentric 6 tầng** (che danh tính, cắt đoạn, pose, QA, xuất stage 1), không phải do vòng Failure → Data chọn hay đánh trọng số dựa trên lỗi của A, C. Vì vậy stage 1 của B chạy song song với A và C, không phải chờ eval.
- N_full = 80 (số tác giả dùng mỗi task), N_cut = 40 [Đề xuất]. Có ngân sách thì thêm N_cut = 20.
- Demo của N_cut là tập con của N_full, cố định bằng hash trong RunPlan, dùng chung cho B và C.
- Stage 2: cả ba nhánh dùng cùng action expert `postpre.*` đi với `pre.*` đã chọn, nếu code Ψ₀ cho ghép VLM đã fine-tune với action expert gốc. DA-19 kiểm điều này khi đọc code train; nếu không ghép được, mục này phải sửa trước khi chạy B.
- Stage 3: cùng recipe `finetune-simple-psi0.sh`, cùng số bước, batch, learning rate cho cả ba nhánh; ghi trong RunPlan.

**Tầng phụ, chạy trước demo** [Đề xuất]: lặp nhánh C với hai checkpoint ablation của tác giả, một có EgoDex (`pre.fast.1by1…ego200k.he30k` + `postpre.1by1.pad36…he30k`) và một không có EgoDex (`pre.abl.only.he…48k` + `postpre.abl.only.he…`). Ký hiệu C-EGO và C-NOEGO. Câu hỏi: ở cùng N_cut demo, egocentric chung có giúp trên task khay không. Tầng này không cần video, nên là bằng chứng về egocentric duy nhất có trước 17/11. Nếu nhánh A và C dùng `pre.fast.1by1…` làm checkpoint gốc thì C-EGO trùng C, chỉ cần chạy thêm C-NOEGO. Giới hạn: hai checkpoint khác nhau cả số bước pretrain (design 27/10 mục 7.2).

### 6.3 Eval

| Mục | Giá trị [Đề xuất] |
|---|---|
| Điều kiện | 30 điều kiện dev × 3 mức của mục 3.5, cùng hạt giống cho mọi nhánh |
| Renderer | MuJoCo |
| Chế độ | Đồng bộ (design 27/10 mục 8.5) |
| Chỉ số chính | Tỉ lệ thành công theo mục 3.4, gộp ba mức |
| Chỉ số phụ | Theo mức; tỉ lệ đạt từng bước scorer; phân bố kiểu lỗi mục 3.3 |
| Seed | 1 seed mỗi nhánh cho kết quả sơ bộ; thêm seed thứ hai cho cả ba nhánh nếu còn ngân sách |
| Khoảng tin cậy | Bootstrap theo điều kiện, như spec mục 7.5 |
| Tập eval | Điều kiện **dev**; kết quả trước 17/11 ghi "sơ bộ, trên dev". Holdout chạy sau demo bằng `fw holdout run`, theo lộ trình của spec; không là phụ thuộc của demo |

### 6.4 Quy tắc diễn giải (chốt trước khi chạy) [Đề xuất]

- **HE-T đạt** khi cả hai cùng đúng: cận dưới CI 95% của (B − A) > −δ với δ = 10 điểm phần trăm; và cận dưới CI 95% của (B − C) > 0.
- **B ≈ A nhưng B ≈ C**: task không cần nhiều demo ở mức này; không kết luận về egocentric. Thử N_cut nhỏ hơn.
- **B < C hoặc B ≪ A**: HE-T âm trên task khay, là kết quả hợp lệ, phải báo.
- **Trước demo, khi chưa có B**: so A với C cho biết task khay nhạy với số demo robot đến đâu (C thấp hơn A rõ thì mới có chỗ để egocentric bù). So C-EGO với C-NOEGO (cận dưới CI 95% của hiệu > 0) là bằng chứng sơ bộ rằng egocentric chung giúp ở N_cut. Báo cáo ghi rõ đây chưa phải HE-T.
- **Giới hạn phải nêu**: B có thêm compute ở stage 1; egocentric và task cùng do đội dựng, cùng phân phối hơn so với dữ liệu thật; kết quả trong sim.

### 6.5 Chi phí (ước lượng, chưa đo)

Trước demo: ba lần fine-tune stage 3 (A, C, C-NOEGO). Sau khi có video: thêm stage 1 và stage 3 của B. Fine-tune chạy trên Colab Pro (A100 hoặc H100); thuê server khi Colab không đủ (giới hạn phiên, hàng đợi GPU) [Đã chốt]. Eval 90 episode mỗi nhánh ở MuJoCo trên máy 3060 hoặc server thuê; thời gian mỗi episode đo ở mốc M0. S1-04 đo giờ một lần fine-tune trước 6/11. Không có trần cứng; nếu tổng chi phí dự kiến vượt khoảng gấp đôi ước lượng sau M0, báo trưởng nhóm trước khi chạy tiếp.

## 7. Lộ trình tới demo 17/11/2026 [Đề xuất]

| Mốc | Ngày | Xong khi | Đường lui nếu trễ |
|---|---|---|---|
| M0 · cảnh tĩnh | 1/11 | Cảnh mục 3.1 load trong SIMPLE `mujoco`, G1 đứng, khay và linh kiện đứng yên 30 s không xuyên, ảnh camera đầu ra đúng; đo thời gian một bước sim | |
| M1 · task chạy được | 4/11 | `reset`, `check_success`, ngẫu nhiên hóa 3 mức; một quỹ đạo planner viết tay mang khay thành công trong sim | 6/11: đơn giản hóa (khay không linh kiện, rồi khay có gờ cao) và ghi `Decision` |
| M2 · synthetic S1 | 8/11 | Planner kịch bản theo 7 bước sinh ≥ 100 episode, ≥ 80 đạt QA (pipeline của Thông nếu đã có, không thì QA tối thiểu mục 7); release có hash | 10/11: giảm N_full còn số đạt QA thực có |
| M4 · train | 12/11 | Stage 3 của A, C, C-NOEGO xong trên Colab hoặc server thuê | Chỉ A và C; C-NOEGO sau demo |
| M5 · eval | 15/11 | Eval A, C, C-NOEGO; bảng mục 6.3; video rollout cạnh nhau | Giảm còn 20 điều kiện mỗi mức, ghi `Decision` |
| Chạy thử | 16/11 | Phần task khay chạy được trong kịch bản demo | |
| M3 · egocentric | Sau demo, ngày chốt sau | Video bê khay quay xong, qua pipeline egocentric, xuất stage 1; chạy stage 1 và stage 3 của B, eval B | |

Mốc giao dữ liệu của 07 mục 2.0 (30/10, 6/11, 12/11) **không đổi**: chúng thuộc task hai bàn. Release synthetic task khay đi qua pipeline của Thông khi pipeline có đủ tầng; trước đó nhánh này tự kiểm QA tối thiểu (chạy lại trong sim đạt, đủ trường) và ghi lý do.

## 8. Ảnh hưởng tới story và người

Vì chạy song song [Đã chốt], chỉ việc của trưởng nhóm đổi:

| Story | Thay đổi [Đề xuất] |
|---|---|
| **DA-32 task bê khay** (mới) | Cảnh, asset, task SIMPLE, ngẫu nhiên hóa, quan sát, `check_success` và vị từ 7 bước trong `flywheel-simple`; mốc M0, M1 |
| **DA-33 synthetic S1 cho task khay** (mới) | Planner kịch bản hai tay trên decoupled WBC (quỹ đạo cổ tay qua `TeleopRetargetingIK`, `navigate_cmd`), sinh hàng loạt, QA tối thiểu, release có hash; mốc M2 |
| **DA-34 thí nghiệm egocentric trên task khay** (mới) | RunPlan và chạy A, C, C-NOEGO (M4, M5); B sau khi có video |
| DA-19 | Thêm nhiệm vụ con: đọc `eval-decoupled-wbc` và config `…locomotionpickbetweentablesteleop-v0` để xác nhận `action_layout` (mục 4); kiểm ghép VLM fine-tune với `postpre.*` (mục 6.2) |
| S1-04 | Thêm đo thời gian eval một episode task khay ở `mujoco` |
| S1-05, S1-11, DA-16, DA-26, DA-29, DA-30 | Không đổi; vẫn cho task hai bàn |

Data flywheel không đổi việc. Nhánh này dùng lại những gì đã merge: schema episode (DA-01), pipeline teleop và synthetic (DA-03), scorer (khi Châu có khung scorer, thêm cấu hình 7 bước của task khay qua PR riêng của trưởng nhóm, Châu bình luận). Không ai phải chờ nhánh này, và nhánh này không chờ ai: trước khi pipeline và scorer có, dùng QA tối thiểu và `check_success` của task.

Tải: ba story mới khoảng 40–60 giờ (ước lượng thô), cộng vào khoảng 230 giờ đã có của trưởng nhóm (07 mục 2.3). Bước giảm tải đã ghi ở 07 mục 2.3 (chuyển S1-06, S1-09, DA-16 cho Hưng nếu có máy chạy SIMPLE) càng cần làm sớm.

## 9. Rủi ro

| Rủi ro | Dấu hiệu | Xử lý |
|---|---|---|
| G1 không giữ thăng bằng khi mang khay có tải | M1 thất bại vì ngã | Giảm khối lượng khay và linh kiện; đi chậm hơn; đọc cách task bê hộp SONIC làm |
| Planner hai tay không giữ khay song song khi đi | Linh kiện rơi trong episode sinh tự động | Giữ cố định tư thế tương đối hai cổ tay trong khung thân khi mang; khay có gờ cao hơn |
| Policy Balance, Walk của decoupled WBC train không có tải ở tay | Robot nghiêng, trôi hoặc ngã khi mang khay | Giảm khối lượng khay và linh kiện; giữ khay sát thân; đi chậm hơn; ghi `Decision` |
| Bàn tay G1 không cầm chắc tay cầm | Khay trượt ở bước 3 | Đổi hình tay cầm; tăng ma sát trong giới hạn hợp lý; ghi `Decision` |
| Ψ₀ không học được từ ảnh MuJoCo | A dưới 10% thành công | Tăng N_full nếu planner sinh rẻ; kiểm lại pipeline ảnh bằng P3 offline |
| Colab không đủ (giới hạn phiên, hàng đợi GPU) | Job bị ngắt, chờ GPU lâu | Resume từ checkpoint; thuê server cho fine-tune và eval |
| Trưởng nhóm quá tải vì thêm nhánh này | Story task hai bàn của trưởng nhóm trễ (R4, k > 1,3) | Ưu tiên task hai bàn khi hai nhánh tranh giờ; nhánh khay lùi mốc, không cắt task hai bàn |

## 10. Quyết định và câu hỏi

**Đã chốt (trưởng nhóm, 28/10/2026)**: task bê khay mới hoàn toàn; bộ điều khiển decoupled WBC (`g1_sonic`, `SonicLocoManipEnv`); chỉ MuJoCo với G1 của SIMPLE; dữ liệu robot là synthetic sinh trong sim; baseline theo Ψ₀; thí nghiệm so 100% demo robot với egocentric qua flywheel cộng demo robot cắt bớt; chạy song song với task hai bàn; simulation trước, quay video sau; Colab Pro, thuê server khi cần.

**Lựa chọn của người viết, cần trưởng nhóm xem**: nhánh đối chứng C (mục 6.2); tầng phụ C-NOEGO chạy trước demo (mục 6.2); egocentric phải là video bê khay tự quay (mục 0 ý 6, mục 5.1); Ψ₀ eval qua `eval-decoupled-wbc` và tự xuất lệnh đi (mục 4); giới hạn 90 giây (mục 4); 7 bước scorer gộp từ 12 bước (mục 3.2); 4 kiểu lỗi mới (mục 3.3); ba mức ngẫu nhiên hóa (mục 3.5); đăng ký task từ `flywheel-simple`, không fork (mục 4); planner kịch bản thay `datagen` (mục 4, 5); N_full = 80, N_cut = 40, δ = 10 điểm (mục 6); eval trên dev trước demo (mục 6.3); lộ trình và đường lui (mục 7); ba story mới DA-32, DA-33, DA-34 (mục 8).

**Câu hỏi còn mở**

| Mã | Câu hỏi | Ai trả lời | Ảnh hưởng |
|---|---|---|---|
| Q-28B | Ai quay video bê khay, thiết bị gì, quay xong ngày nào? (chốt sau phần simulation) | Hiếu | Mốc M3, nhánh B |
| Q-28C | Code Ψ₀ có cho ghép VLM đã fine-tune stage 1 với action expert `postpre.*` gốc không? | DA-19 | Cách dựng nhánh B |
| Q-28D | SIMPLE có cho đăng ký task từ package ngoài không? | DA-32 nhiệm vụ con đầu | Fork hay không fork |
| Q-28E | G1 trong SIMPLE có camera cổ tay không? | DA-32 | Quan sát của policy |

## Phụ lục: tóm tắt spec gốc của trưởng nhóm

Spec "Humanoid Industrial Tray Transfer" (28/10/2026) viết cho Isaac Sim và Isaac Lab. Những gì design này giữ, đổi hoặc bỏ:

| Mục spec gốc | Nội dung | Ở design này |
|---|---|---|
| 1 Cảnh | Sàn phẳng, hai bàn đối diện, hành lang trống, robot đứng giữa gần bàn A; kích thước mặc định cấu hình được | Giữ (mục 3.1) |
| 2 Khay và linh kiện | Rigid body có khối lượng, ma sát, va chạm; hai tay cầm; 6 linh kiện trong ô; không hàn khay vào tay | Giữ (mục 3.1, 2) |
| 3 Vùng đích | Tư thế đích, dung sai vị trí và góc; khay nằm trọn, ổn định trên bàn B | Giữ (mục 3.1, 3.4) |
| 4 Chuỗi bước | 12 bước, từ quan sát tới đứng lại | Gộp thành 7 bước scorer (mục 3.2) |
| 5 Vật lý | Trọng lực, va chạm, ma sát, thăng bằng, hai tay; không dịch chuyển tức thời | Giữ |
| 6 Quan sát | Camera RGB đầu, cổ tay nếu có, khớp, tư thế gốc, bàn tay, khay, đích, tiếp xúc; trạng thái đặc quyền tách riêng | Giữ (mục 3.6) |
| 7 Thành công | Khay trên B, trong dung sai, ổn định, đã nhả, robot đứng, không rơi linh kiện | Giữ (mục 3.4) |
| 8 Cách chia mã | Cảnh, robot, asset, máy trạng thái, quan sát, reward, thành công và thất bại, reset và ngẫu nhiên hóa; script xem cảnh; làm cảnh tĩnh trước | Giữ, trừ reward (mục 2); cảnh tĩnh là mốc M0 |
| Nền tảng | Isaac Sim, Isaac Lab | Đổi sang SIMPLE `mujoco` (mục 4) |

Spec gốc không nêu giới hạn thời gian episode hay tần số điều khiển; design này chọn ở mục 4.

## Nguồn

- Spec task "Humanoid Industrial Tray Transfer" của trưởng nhóm, ngày 28/10/2026 (bản Isaac Lab), tóm tắt ở phụ lục.
- SIMPLE: https://github.com/physical-superintelligence-lab/SIMPLE và https://psi-lab.ai/SIMPLE/docs (chế độ `mujoco|isaac|mujoco_isaac`, lớp `Task`, task SONIC), tra ngày 28/10/2026.
- Hugging Face `USC-PSI-Lab/psi-data` (thư mục `simple/`) và `USC-PSI-Lab/psi-model` (thư mục `psi0/`), tra ngày 28/10/2026.
- [Design 27/10/2026](2026-10-27-g1-psi0-demo-design.md) mục 3, 4, 5, 6.6, 7, 8.
