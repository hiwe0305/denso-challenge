# Thí nghiệm egocentric trên task bê khay: thiết lập và quy tắc diễn giải (DA-34)

_Chốt ngày 3/11/2026, trước khi chạy job nào. Story [DA-34](../product/stories/DA-34-thi-nghiem-egocentric-khay.md) nhiệm vụ 1; [design 28/10/2026](../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 6.2–6.4 và 6.6. RunPlan bản 1: [`he-tray.yaml`](../../configs/runplans/tray/he-tray.yaml), đóng băng ở [`he-tray.lock.json`](../../configs/runplans/tray/he-tray.lock.json), đã thay. RunPlan bản 2: [`he-tray-v2.yaml`](../../configs/runplans/tray/he-tray-v2.yaml), đóng băng ngày 5/11/2026 ở [`he-tray-v2.lock.json`](../../configs/runplans/tray/he-tray-v2.lock.json) (mục 11)._

Quy tắc ở mục 3–5 **không đổi sau khi thấy kết quả** (ghi chú của story). Muốn đổi thì viết RunPlan mới kèm `Decision`, và báo cáo kết quả theo cả quy tắc cũ lẫn quy tắc mới. Test `test_psi0_tray_runplan.py` báo lỗi nếu `he-tray.yaml` khác bản đã đóng băng.

## 1. Thiết lập

| Nhánh | Demo robot (stage 3) | Checkpoint gốc | Vai |
|---|---|---|---|
| A | 80 episode, tập `A` | `pre.fast.1by1…ego200k.he30k` + `postpre.1by1.pad36…he30k` | Baseline theo Ψ₀ |
| C | 40 episode, tập `C` ⊂ `A` | như A | Cắt demo, không bù; trùng C-EGO của design mục 6.2 |
| C-NOEGO | tập `C` | `pre.abl.only.he…48k` + `postpre.abl.only.he…` | C trên checkpoint pretrain không có EgoDex |
| C+ (AC 6) | tập `C` + 40 episode S1 nhắm lỗi của C | như A | Vòng Failure → Data, khung ở [`round-tray-cplus.yaml`](../../configs/runplans/tray/round-tray-cplus.yaml) |
| B (AC 5) | tập `C` | `pre.*` fine-tune thêm trên video bê khay | Sau khi có video; RunPlan riêng |

- **Dữ liệu robot**: release synthetic S1 `tray_s1_0d84cc87b1e5` của DA-33 (102 episode, mức 1, seed train 1000–1129; [synthetic-s1.md](../g0/tray/synthetic-s1.md)). Tập `A` và `C` chọn tất định bằng `flywheel_psi0.tray.demo_sets`: xếp mọi episode theo sha256(muối | `release_hash` | seed), tập n là n episode đầu. Vì vậy `C` ⊂ `A`, và 40 episode A có thêm so với C là một lần rút đều từ 62 episode C bỏ ra. Hash ở [`demo_sets.json`](../../configs/runplans/tray/demo_sets.json): `A` = `94245f8d36ab…`, `C` = `5db98a38ed80…`. 22 episode còn lại của release không dùng.
- **Recipe** chung cho mọi nhánh: [`psi0-stage3.yaml`](../../configs/models/psi0-stage3.yaml), 40.000 bước, batch 16 trên một GPU (checkpoint hai bàn của tác giả: 16 × 4 GPU = 64, theo `argv.txt` ở psi-model `cb1480f`, [S1-04](../g0/psi0-finetune-cost.md) mục 1.4), lr 1e-4 cosine, VLM đóng băng, RTC. Ghi đè duy nhất, chung cho mọi nhánh (4/11/2026): `train.validation_steps: 2000` thay vì 500, theo quyết định của Hiếu ở [S1-04 mục 4.1](../g0/psi0-finetune-cost.md); validation không đổi quá trình train, chỉ ít điểm `val` hơn (21 thay vì 81 mỗi lần). `runplan check` từ chối mọi ghi đè khác. Máy: một Colab L4. Seed train 0. `stats_psi0.json` của mỗi nhánh tính trên chính tập train của nhánh đó [Đề xuất], như Ψ₀ làm khi fine-tune một dataset.
- **Eval**: 90 điều kiện dev, seed 1 000 100–1 000 129 ở mỗi mức 0, 1, 2, như nhau cho mọi nhánh; `eval-decoupled-wbc`, `sim_mode=mujoco`, đồng bộ, 1 lượt mỗi điều kiện, giới hạn 90 s. Mức 0 không ngẫu nhiên hóa, nên 30 điều kiện của mức 0 cùng một cảnh; khác nhau chỉ do lấy mẫu của policy và sim.
- **Phân phối**: release chỉ có mức 1. Mức 0 là cảnh giữa của mức 1; mức 2 là dịch chuyển (khoảng cách bàn, chỗ đứng, khối lượng linh kiện, ánh sáng).

## 2. Ước lượng

- Thành công của nhánh X ở điều kiện i: s_X,i ∈ {0, 1}, theo `check_success` của task (design mục 3.4).
- Chỉ số chính: tỉ lệ thành công gộp ba mức, p_X = trung bình s_X,i trên 90 điều kiện.
- Hiệu X − Y = trung bình theo điều kiện của (s_X,i − s_Y,i), ghép cặp theo điều kiện.
- Khoảng tin cậy 95%: bootstrap theo điều kiện, lấy mẫu lại trong từng mức (30 mỗi mức), 10.000 lần, hạt giống 20261103, khoảng phân vị. Cùng một bộ chỉ số lấy mẫu cho mọi nhánh, để giữ ghép cặp.
- Chỉ số phụ: tỉ lệ theo mức; tỉ lệ đạt từng bước trong 7 bước scorer; phân bố kiểu lỗi (design mục 3.3).
- Lượt hỏng do hạ tầng (server Ψ₀ lỗi, sim sập, mất kết nối) không tính là thất bại của policy: chạy lại cùng điều kiện, cùng hạt giống, và báo số lần chạy lại.

## 3. Quy tắc trước demo: A, C, C-NOEGO

Kiểm theo thứ tự; quy tắc trước chặn quy tắc sau.

| # | Điều kiện | Đọc là |
|---|---|---|
| 0 | p_A < 10% | Ψ₀ chưa học được task khay từ ảnh MuJoCo (design mục 9). Không so nhánh nào; kiểm pipeline ảnh bằng phát lại offline, ghi `Decision` |
| 1 | Cận trên CI của (C − A) < 0 | Task khay nhạy với số demo robot ở N = 40…80: có chỗ để egocentric bù |
| 2 | CI của (C − A) chứa 0 | Chưa thấy task nhạy với số demo ở mức này. HE-T không đo được ở N_cut = 40; đề xuất thêm N_cut = 20 (design mục 6.2, 6.4) |
| 3 | Cận dưới CI của (C − A) > 0 | Bất thường (ít demo hơn mà tốt hơn): báo, kiểm hai lần train trước khi đọc tiếp |
| 4 | Cận dưới CI của (C − C-NOEGO) > 0 | Bằng chứng sơ bộ: egocentric chung (EgoDex) trong pretrain giúp ở N_cut |
| 5 | CI của (C − C-NOEGO) chứa 0 | Không kết luận về egocentric chung |
| 6 | Cận trên CI của (C − C-NOEGO) < 0 | Checkpoint có EgoDex kém hơn ở N_cut: kết quả hợp lệ, phải báo |

Quy tắc 4–6 đọc độc lập với 1–3, trừ khi quy tắc 0 đã chặn. Mọi kết luận ở mục này **chưa phải HE-T**: C-NOEGO khác C ở cả số bước pretrain (48k so với 200k + 30k), không riêng EgoDex.

## 4. Quy tắc HE-T: khi có nhánh B

Theo design mục 6.4, δ = 10 điểm phần trăm:

- **HE-T đạt** khi cả hai cùng đúng: cận dưới CI của (B − A) > −δ, và cận dưới CI của (B − C) > 0.
- **B ≈ A và B ≈ C** (cả hai CI chứa 0): task không cần nhiều demo ở mức này; không kết luận về egocentric; thử N_cut nhỏ hơn.
- **Cận trên CI của (B − C) < 0, hoặc cận trên CI của (B − A) < −δ**: HE-T âm trên task khay, là kết quả hợp lệ, phải báo.
- Các trường hợp còn lại: không kết luận, báo cả hai khoảng.

## 5. Quy tắc vòng Failure → Data: C+ (AC 6)

Theo design mục 6.6:

- **C+ so với A**: A có đúng 40 demo thêm lấy đều so với C, C+ có 40 episode thêm nhắm lỗi. Đây là phép so "bổ sung nhắm lỗi" với "bổ sung đều" cùng số episode, kiểu HT của spec mục 3, nhưng trên dev, 1 seed, 1 vòng. Báo hiệu và CI như mục 2, là **kết quả mô tả**; không gọi là kiểm HT.
- **C+ so với C**: vòng có sửa được lỗi không. Báo ba số: hiệu C+ − C trên 90 điều kiện; tỉ lệ thành công của C+ trên các điều kiện C đã hỏng (tỉ lệ sửa được); **số hồi quy** = số điều kiện C làm được mà C+ hỏng. Với 1 lượt mỗi điều kiện, số hồi quy gồm cả nhiễu lấy mẫu; báo kèm số lượt C hỏng mà C+ làm được để so.
- Episode nhắm lỗi sinh trên seed train (Q-33A), không trên điều kiện dev đã hỏng; C+ eval trên đúng 90 điều kiện của mục 1.
- **Đường lui**: nếu 11/11/2026 C+ chưa bắt đầu train được, dừng ở episode nhắm lỗi đã qua QA cộng sổ chi phí, ghi `Decision`; C+ chạy sau demo.

## 6. Báo cáo

- Mọi số ghi "sơ bộ, trên dev", 1 seed train, renderer MuJoCo. Không so với số tác giả báo (ảnh Isaac, task khác).
- Bảng theo design mục 6.3: nhánh × (gộp, mức 0, 1, 2), kèm CI; tỉ lệ đạt 7 bước; kiểu lỗi.
- Giới hạn phải nêu: dữ liệu robot là synthetic S1 do planner sinh (`action_quality = planned`, một cách cầm); release chỉ có mức 1; batch toàn cục 16 thay vì 64 của tác giả; C-NOEGO khác C cả ở số bước pretrain; kết quả trong sim. Khi có B: B tốn thêm compute ở stage 1; egocentric và task cùng do đội dựng.

## 7. Quyết định 3/11/2026 (bản 2): tăng dữ liệu, lọc chất lượng, eval lớn hơn

**[Đã chốt]** Hiếu, 3/11/2026, trước khi chạy job nào: tăng dữ liệu robot, dữ liệu phải chất lượng cao; không dựa vào giả định. RunPlan bản 1 (mục 1–6, 80/40, 90 điều kiện) chưa chạy và được thay bằng `he-tray-v2.yaml`. Bản 1 đóng băng lần đầu là `rp_59164e3970c4`; ngày 4/11/2026 thêm ghi đè validation (mục 1) và đóng băng lại thành `rp_c49c99c8d8da`, vẫn chưa chạy. Bản 2 giữ cùng ghi đè. Mục 2–6 giữ nguyên, trừ những điểm dưới đây. Phần này chốt **trước khi sinh kho mới**.

**Vì sao.** Số đo ngày 3/11/2026, không phải giả định:

| Đo | Kết quả |
|---|---|
| Độ nhạy của eval 90 điều kiện × 1 lượt (Monte Carlo, độ khó điều kiện dùng chung hai nhánh) | Nửa độ rộng CI của hiệu khoảng ±12 điểm; A 60% → C 40% chỉ thấy được 57% số lần. 270 điều kiện: khoảng ±7 điểm, 98% |
| Chất lượng 102 episode của release `tray_s1_0d84cc87b1e5` (`flywheel_psi0.tray.quality`) | Nghiêng khi mang: trung vị 6,8°, p90 9,7°, tối đa 14,9° (scorer hỏng ở 15°). Linh kiện xê dịch lúc cuối: trung vị 11,5 mm, p90 19,5 mm, tối đa 28,9 mm. Mọi episode rơi khay lúc nhả (vận tốc tối thiểu −0,23 đến −0,80 m/s) |
| Chi phí train theo số episode | Không đổi: recipe chạy cố định 40.000 bước × batch 16 |

| Mục | Bản 1 | Bản 2 |
|---|---|---|
| Kho | Release 102 episode | Một lô mới seed train 1000–1609 (610 lượt), mức 1, cùng planner `da33-planner-4+cfg.815b822a` và cùng code sinh như release đầu. Seed 1000–1129 sinh lại để cả kho là một lô, một release |
| Lọc chất lượng | Chỉ QA tối thiểu và QA phát lại | Thêm: nghiêng khi mang ≤ 10° **và** linh kiện xê dịch lúc cuối ≤ 20 mm. Ngưỡng lấy từ 102 episode cũ (84 đạt), chốt trước khi xem kho mới. Độ rơi khi nhả chỉ ghi lại, không lọc: mọi episode S1 đều có (D-25) |
| N_full / N_cut | 80 / 40 | **320 / 160**, giữ tỉ lệ một nửa. Tập lồng nhau 40 ⊂ 80 ⊂ 160 ⊂ 320 cùng một thứ tự hash; 40 và 80 là điểm dự phòng cho quy tắc 2 (thử N_cut nhỏ hơn), chạy khi còn CU sau A, C, C-NOEGO, C+ |
| Nếu kho thiếu | | Ít hơn 320 episode đạt: sinh tiếp seed 1610 trở đi với cùng lệnh tới khi đủ; không nới ngưỡng |
| C+ | n_add = 40 | n_add = N_full − N_cut = 160 |
| Eval | 30 seed × 3 mức = 90 điều kiện | **90 seed dev mỗi mức** (1 000 100–1 000 189) × 3 mức = **270 điều kiện**, 1 lượt mỗi điều kiện. Chọn nhiều điều kiện thay vì lặp lượt vì chưa kiểm hai lượt cùng điều kiện có khác nhau không. Mức 0 vẫn là một cảnh |

Hệ quả: A thấy mỗi frame khoảng 1,4 lần (320 episode × khoảng 1.430 frame so với 640.000 mẫu), C khoảng 2,8 lần; đây là tính chất của recipe số bước cố định, như tác giả. Eval khoảng 270 episode mỗi nhánh, chỉ tốn giờ máy 3060.

## 8. Kiểm tra trước khi chạy job (review của PO ngày 4/11/2026, PR #73)

_Đo ngày 4/11/2026 trên `rtx3060`, không dùng GPU, không train. Bốn điểm của review [PR #73](https://github.com/hiwe0305/denso-challenge/pull/73#issuecomment-6611206593)._

### 8.1 Cổng phát lại qua client eval (điểm 3)

Cách làm: server Ψ₀ giả [`flywheel_psi0.tray.replay_server`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/replay_server.py) trả cột `action` 36 chiều của episode trong release (đúng thứ Ψ₀ học), 24 frame mỗi lần gọi, bỏ qua quan sát. Client là `eval-decoupled-wbc` của SIMPLE với policy `psi0_decoupled_wbc`, `sim_mode=mujoco`, không sửa SIMPLE. Ba episode S1 của tập `C` (seed 1001, 1003, 1008), mỗi episode chạy hai lượt, ở hai chế độ đồng hồ. Episode nào planner đã giải được thì phát lại phải thành công.

| Đồng hồ | Thành công | Hai lượt cùng episode | Khay cuối so với lúc ghi |
|---|---|---|---|
| Thời gian sim (như QA phát lại của DA-33, D-24) | **6/6** | Giống hệt nhau đến từng bit (lệch 0,0 mm) | 2,6–16,4 mm, ≤ 1,2° |
| Thời gian thật (SIMPLE như hiện có), máy tải khoảng 50 | **4/6**: 1001 lượt 2 `L-TRAY-TILT`, 1008 lượt 2 `L-PLACE-POSE` | Lệch nhau 7–43 mm | 16–31 mm, tới 8,2° |

Kết luận:

- **Chuỗi eval nối đúng.** Cách đọc bố cục action 36 chiều của export, cách client tách action, cảnh dựng lại từ `environment_config` và scorer khớp nhau: ở thời gian sim, cả 6 lượt phát lại đều thành công.
- **Eval chạy ở thời gian sim.** **[Đã chốt]** (Hiếu, 4/11/2026). Agent `psi0_decoupled_wbc`, agent WBC sonic và vòng eval đọc `time.monotonic()`, nên WBC nội suy mục tiêu theo giờ tường. Trên máy tải nặng, cùng một chuỗi action cho kết quả khác nhau, và 2/6 lượt phát lại hoàn hảo bị chấm hỏng. Ở thời gian thật, tỉ lệ thành công của một nhánh lẫn cả tải của máy. Dữ liệu train ghi ở thời gian sim (D-24).
- **Bộ nạp episode khay.** Cổng chạy trên bản `flywheel_simple` cũ trong `~/denso-da33`. Ở đó `get_episode_lerobot` của SIMPLE báo `KeyError: 'dr_state_dict'` (dòng `FIXME`). Hotfix `5a2029a` (#67) trên master đã sửa đúng lỗi này trong `flywheel_simple.tray.run`. Hai việc còn lại thì #67 chưa làm:
  - `eval-decoupled-wbc` vẫn chạy theo giờ tường, kể cả ở worker spawn;
  - bộ nạp vẫn giải mã mọi frame video của episode (khoảng 8 GB RAM mỗi episode trên dataset có video), dù chỉ policy `vlt` dùng.

  Cổng dùng một bộ nạp không giải mã frame. Hai việc này thuộc `flywheel_simple.tray.run`, ngoài phạm vi DA-34: cần PR riêng trước nhiệm vụ 3. Script của cổng và kết quả từng lượt nằm trong ghi chú dùng chung `DA-34-replay-gate/` của nhóm phiên.
- Giả thuyết, chưa kiểm: số 0/20 của S1-03 trên task hai bàn ở `mujoco` chạy ở thời gian thật, nên có thể một phần do đồng hồ.

### 8.2 Mức 0 có phải giả lặp (điểm 1)

- Số đo S1-03, task hai bàn, mức 0, checkpoint của tác giả, thời gian thật, chạy lại hai lần. Cùng một episode: hai lượt trùng nhau trong 33–44 frame đầu, rồi tách ra. Ở frame cuối, ảnh lệch trung bình 38–50 mức xám. Hai episode khác nhau thì lệch ngay từ frame 0, vì bộ eval hai bàn có cảnh khác nhau ở mức 0. Mức 0 của task khay chỉ có một cảnh.
- Nguồn ngẫu nhiên, đọc mã tại pin. Nhiễu flow-matching của Ψ₀ lấy `torch.randn` từ RNG toàn cục, gieo một lần khi server khởi động (`seed_everything(launch_config.seed or 42)`, `src/psi/deploy/serve_psi0_simple.py` dòng 66, server mà eval dùng). Ở thời gian thật, độ trễ của máy cũng làm lượt chạy khác nhau (mục 8.1). Ở thời gian sim, chuỗi sim + WBC tất định (mục 8.1), nên chỉ còn nhiễu của server.

Quy tắc cho bản 2, thay mục 2 (theo nhánh "khác nhau" của review):

| Mục | Quy tắc |
|---|---|
| Mức 0 | Một cảnh. Các lượt ở mức 0 là **lượt lặp** (rollout replicate), không phải điều kiện. Báo p ở mức 0 riêng, CI bootstrap theo lượt, ghi rõ "1 cảnh × k lượt" |
| Chỉ số chính, hiệu, HE-T | Gộp **mức 1 và 2**: mỗi seed là một cảnh khác. Bootstrap theo điều kiện trong từng mức, như mục 2. Luôn báo kèm theo từng mức |
| Nhiễu của policy | **[Đã chốt]** (Hiếu, 4/11/2026): gieo nhiễu theo từng episode, từ seed điều kiện lúc reset (mục 8.5). Nhờ vậy ghép cặp giữa các nhánh là ghép thật, và chạy lại riêng một episode cho ra đúng nó. Ở mức 0, các lượt lặp có seed điều kiện khác nhau, nên là lượt lặp có kiểm soát |
| Phân bổ 270 lượt **[Đã chốt]** (Hiếu, 4/11/2026) | Mức 0: 30 lượt lặp. Mức 1 và 2: mỗi mức 120 seed dev (1 000 100–1 000 219). Tổng vẫn 270 episode mỗi nhánh, 240 cảnh khác nhau cho chỉ số chính. Nửa độ rộng CI ước lượng khoảng ±7,5 điểm (quy theo căn bậc hai từ số Monte Carlo ở mục 7, chưa chạy lại) |

**Decision 4/11/2026 (Hiếu):** (1) eval tray ở thời gian sim; (2) mức 0 là lượt lặp của một cảnh, báo riêng; chỉ số chính từ mức 1–2; phân bổ 30 / 120 / 120; nhiễu gieo theo episode từ seed điều kiện. Đây là thay đổi trước khi chạy bất kỳ job nào, nên vào RunPlan mới `he-tray-v2.yaml`. Quy tắc ở mục 2 của bản 1 và quy tắc ở đây đều được báo cáo. `he-tray-v2.yaml` đóng băng khi có kho dữ liệu (nhiệm vụ con 1.7–1.8). Train chờ kết quả điều tra cú nhảy cổ tay của DA-33.

### 8.3 Cột `index` của release (điểm 2)

Ψ₀ tại `cda3fdf` không đọc cột `index` khi train stage 3. Không cần đánh số lại trước khi train. Đường đọc (đọc mã tại pin):

- `finetune_simple_psi0_config` → `LerobotDataConfig` → `LeRobotDatasetWrapper` → `LeRobotDataset` của fork `songlin/lerobot` tại `09929d8` (bản 0.3.3, ghim trong `uv.lock` của Ψ₀).
- `__getitem__` lấy `hf_dataset[idx]` theo vị trí. Biên episode lấy từ độ dài trong `meta/episodes.jsonl` (`get_episode_data_index`). Frame lân cận lấy theo `idx + delta`. Mã chỉ đọc `episode_index`, `timestamp`, `task_index`.
- Trong Ψ₀, chỉ bộ nạp `psi/data/gear` đọc `index`, và bộ nạp đó không nằm trên đường stage 3.

Điều kiện đi kèm: các hàng parquet phải xếp theo episode, đúng thứ tự và độ dài trong `meta/episodes.jsonl`. Dataset con của nhiệm vụ 2 phải giữ điều kiện này.

### 8.4 Bản 1 đã thay (điểm 4)

Đầu file `he-tray.yaml` ghi dòng `SUPERSEDED - DO NOT RUN`. Bản 2 vào cùng PR #73 (nhiệm vụ con 1.8). Phần chú thích này không đổi plan đã parse, nên `rp_c49c99c8d8da` và lock giữ nguyên.

### 8.5 Gieo nhiễu theo từng episode: làm được không, cần gì

Làm được mà không sửa mã Ψ₀. Đọc mã tại `cda3fdf`:

- Server mà eval dùng là `src/psi/deploy/serve_psi0_simple.py`:
  - Dòng 66 gieo RNG toàn cục một lần (`seed_everything`). Nhiễu là `torch.randn` toàn cục (`src/psi/models/psi0.py` các dòng 1986, 2127, 2275, 2433).
  - `predict_action` (dòng 330) nhận `history` của request nguyên vẹn (dòng 339), và chỉ đọc khóa `reset` cùng `session_id`/`client_id` (dòng 250–284, 373). Khóa lạ bị bỏ qua.
  - Route `/act` gắn `self.predict_action` lúc `run()` (dòng 470).
- Client của SIMPLE (`simple/baselines/psi0_decoupled_wbc.py`) chỉ gửi `history={"reset": True}` ở bước đầu mỗi episode.

Cần hai thứ, đều ngoài phạm vi DA-34:

1. **Client.** `flywheel_simple.tray.run` thêm `history["seed"]` = seed điều kiện của env khay đang chạy (`live_env().sample.seed`) vào request có `reset`. Việc này vào cùng PR `flywheel_simple.tray.run` với thời gian sim.
2. **Server.** Một launcher bọc `Server.predict_action` của `serve_psi0_simple` (trước khi `run()` gắn route, giữ chữ ký cho FastAPI): khi request có `reset` và `seed` thì gọi `torch.manual_seed(seed)` và `torch.cuda.manual_seed_all(seed)`. Launcher chạy trong image Ψ₀ thay cho `serve_psi0_simple`, nên đổi đường serve của S1-03 (`scripts/g0/serve_psi0.sh`). Cần Hiếu chỉ người làm.

Kiểm khi đã có cả hai, cần GPU nên do Hiếu chạy: cùng checkpoint, 3 điều kiện mức 0, mỗi điều kiện 2 lượt, ở thời gian sim, so trajectory. Kỳ vọng: hai lượt cùng seed giống nhau, các seed khác nhau thì khác nhau. Có thể còn sai khác nhỏ do kernel GPU không tất định; điều này chưa đo.

## 9. Quyết định 4/11/2026: bậc 2, chỉ fine-tune C và C+

**[Đã chốt]** Hiếu, 4/11/2026, nguyên văn: "Approve tier 2". Với DA-34, bậc 2 nghĩa là chỉ fine-tune hai nhánh **C** và **C+**, khoảng 33 CU (2 × 16,6 CU trên L4, ước lượng của S1-04, chưa đo trọn 40.000 bước). Bỏ **A** và **C-NOEGO**. Trần cứng 36 CU cho hai lần. Eval chạy `mujoco` trên `rtx3060`, 0 CU. Colab đang dừng cho cả tài khoản; hai lần train chạy từ master sau khi RunPlan bản 2 đóng băng và Hiếu merge.

Phần này thay mục 3 và mục 5 cho bản 2. Mục 3 và 5 giữ nguyên chữ vì bản 1 đã đóng băng với chúng.

| Mục | Trước (bản 2 theo mục 7–8) | Sau quyết định bậc 2 |
|---|---|---|
| Nhánh train | A (320), C (160), C-NOEGO (160), C+ (160 + 160 nhắm lỗi) | **C** (160) và **C+** (160 + 160 nhắm lỗi). `he-tray-v2.yaml` chỉ có nhánh C; C+ ở `round-tray-cplus.yaml` |
| Tập demo | 40 ⊂ 80 ⊂ 160 ⊂ 320 | Vẫn chọn và ghim cả bốn tập, cùng thứ tự hash. Tập 320 không train ở bậc 2; giữ để A chạy được sau mà không chọn lại tập |
| Checkpoint gốc | Baseline (EgoDex + HE) và ablation chỉ HE | Chỉ baseline. Ablation `psi0-abl-he-only` không vào bản 2 |
| Ngân sách trong RunPlan | Không có | Trường `budget`: trần 36 CU; mỗi lần train dừng ở **18 CU** (2 × 18 = 36); `runs: [C]` là đúng các nhánh của plan, `round_runs: [C_PLUS]` là nhánh của plan round. `runplan check` từ chối khi tổng cap vượt trần, khi một nhánh không có lượt trong `runs`, khi `runs` có tên không phải nhánh, khi `round_runs` trùng nhánh của plan, và khi plan round đặt nhánh ngoài `round_runs` |
| Watcher | | Mỗi job train có một watcher dừng phiên Colab khi phiên đã dùng 18 CU, kể cả khi chưa đủ 40.000 bước. Job dừng ở cap ghi dòng `measured` với số CU thật và số bước đã chạy |
| Sổ chi phí | 4 dòng ước lượng 16,6 CU (A, C, C-NOEGO, C+) | Dòng ước lượng mới: C và C+ mỗi lần 16,6 CU, cap 18; A và C-NOEGO 0 CU, ghi "bỏ theo bậc 2". Dòng cũ giữ nguyên (append-only) |

Quy tắc đọc kết quả cho bậc 2 **[Đã chốt 5/11/2026, Hiếu]**, duyệt nguyên văn cùng PR đóng băng bản 2. Khối giữa hai dấu `tier2-rules` (chú thích HTML, không hiện khi đọc) được ghim bằng sha256 ở `interpretation.rules_sha256` của RunPlan bản 2. Sửa một ký tự trong khối thì `runplan check` báo lỗi; nhãn này nằm ngoài khối.

<!-- tier2-rules -->

| # | Điều kiện | Đọc là |
|---|---|---|
| 0 | p_C < 10% (chỉ số chính, mức 1–2) | Ψ₀ chưa học được task khay từ ảnh MuJoCo. Không chạy C+; kiểm pipeline ảnh, ghi `Decision`. Thay quy tắc 0 của mục 3, vốn đọc trên A |
| 1 | C+ so với C | Báo ba số của mục 5 trên 240 điều kiện mức 1–2: hiệu C+ − C và CI bootstrap theo điều kiện; tỉ lệ C+ làm được trên điều kiện C hỏng; số hồi quy, kèm số lượt C hỏng mà C+ làm được. Mức 0 báo riêng theo mục 8.2 |
| 2 | Giới hạn phải ghi cạnh mọi số C+ − C | C+ có 320 episode, C có 160. Hiệu C+ − C gộp hai tác động: **nhiều dữ liệu hơn** và **dữ liệu nhắm lỗi**. Không có A thì không tách được hai tác động. Vì vậy chỉ đọc "vòng Failure → Data sửa được lỗi của C hay không", không đọc "nhắm lỗi tốt hơn bổ sung đều" |
| 3 | Câu hỏi bỏ ngỏ | Độ nhạy của task với số demo (C so với A, quy tắc 1–3 của mục 3) và EgoDex trong pretrain (C so với C-NOEGO, quy tắc 4–6) không trả lời ở bậc 2. Báo cáo ghi rõ hai câu này chưa đo |

Nếu sau này có thêm CU, A chạy trên tập 320 đã ghim, cùng recipe và cùng điều kiện eval. Khi đó phép so C+ với A của mục 5 dùng lại được. Việc đó cần RunPlan mới hoặc một `Decision`; bản 2 không tự mở lại.

<!-- /tier2-rules -->

## 10. Kho planner-5 và release `tray_s1_f9433b028c52` (4–5/11/2026)

Kho sinh lại theo quyết định của Hiếu trên #93 và #103: planner `da33-planner-5` có giới hạn vận tốc trong IK (D-28 của DA-33). Lô cũ `s1-pool-1103` (planner-4, dừng ở 322/610) ghi đã thay và giữ nguyên, không xóa.

| Bước | Kết quả |
|---|---|
| Sinh, `rtx3060`, lô `s1-pool-1104` | 610 lượt, seed 1000–1609, mức 1, 14 worker, 1,29 giờ. Cả 610 dòng ghi `da33-planner-5+cfg.4e2a4505`. 542 thành công và được ghi; 541 qua QA tối thiểu (1 `phases_incomplete`). Không shard nào chết hay khởi động lại, không crash x264 |
| Hỏng | `L-ONE-HAND` 18, `L-TRAY-TILT` 16, `L-PLACE-POSE` 15, timeout 19 (`LIFT` 7, `REACH` 5, `RELEASE` 5, `ARRIVE_B` 2) |
| QA phát lại (D-24), master `3e45bb6` (có #105) | 542/542 đạt, lệch khay 0,0 mm, 0 shard hỏng hay chưa chấm. Chạy 22:31–23:59 ngày 4/11/2026; dòng thực đo `job_da34_pool_v2_replay` trong sổ ghi ngày 5/11 là ngày ghi sổ, không phải ngày chạy (sổ append-only nên không sửa) |
| Release | `tray_s1_f9433b028c52`, `release_hash` `f9433b028c520b4fd78b34469b389862f7b34de0bb185840aa18143d2d5d8461`, 541 episode, 4,5 GB, một phiên bản planner |
| QA của DA-03 (`qa-1@fb6ddaf9f48c`) cùng phát lại động học của DA-17 (`replay-1@cf2515483a8c`) | **534 pass, 0 flag, 7 reject.** Không có cờ `action_jump.arm`; bước tay lớn nhất 0,080 rad |
| Cấp dataset | `stats_json.states` D4 (lệch 0,0058 ở `states.mean[25]`): lỗi đã biết của script tác giả, việc của DA-02. Cột `index` lệch LeRobot v2.1 ở 527 episode (Q7); Ψ₀ không đọc cột này (mục 8.3) |
| Chất lượng 541 episode | Nghiêng khi mang: trung vị 7,05°, p90 10,34°, tối đa 14,78°. Linh kiện xê dịch lúc cuối: 10,35 / 19,57 / 37,66 mm. Khay rơi khi nhả: trung vị −0,45 m/s (−0,18 đến −0,85) |
| Bộ lọc đã chốt (nghiêng ≤ 10°, xê dịch ≤ 20 mm) | 436/541 đạt (80,6 %): 56 hỏng vì nghiêng, 42 vì xê dịch, 7 cả hai. Cả 7 reject đều qua bộ lọc, nên sau khi loại reject còn **429** episode, đủ cho tập 320. Không cần sinh thêm từ seed 1610 |

**[Đã chốt 5/11/2026, Hiếu] loại 7 reject DA-03 khỏi tập demo.** `flywheel_psi0.tray.demo_sets --qa-work` đọc report QA của DA-03 và bỏ episode `reject` và `quarantine` trước bộ lọc chất lượng. Episode `flag` được giữ, đúng như release của DA-03 giữ (`INCLUDED` của `flywheel.data.release.build`); lô này không có episode `flag` nào. Lệnh dừng với lỗi nếu thư mục QA không phải của release này, nếu một episode thiếu report hoặc có hai report, hoặc nếu một dòng không đọc được thành `QAReport` (ví dụ quyết định lạ). File tập demo ghi lại từng episode bị loại; RunPlan ghim sha256 của report QA. Bảy episode bị loại, đều do phép phát lại động học của DA-17 (D7):

| Episode | Seed | Mã | Chi tiết |
|---|---|---|---|
| `ep_423b9d7b6f87d3ca` | 1072 | `joint_mapping` | Tương quan action–state của `right_hand_middle_0_joint` 0,431 (sàn 0,5) |
| `ep_6a3e45cee41460f3` | 1358 | `joint_mapping` | Cùng khớp, 0,407 |
| `ep_d3a1cefb8fbe676c` | 1166 | `joint_mapping` | Cùng khớp, 0,463 |
| `ep_d5afb36303be4d5d` | 1153 | `joint_mapping` | Cùng khớp, 0,191 |
| `ep_76f4f4bcc93e4024` | 1372 | `joint_limit` | State `left_wrist_roll_joint` vượt giới hạn URDF 2,8 mrad (dung sai 1,93 mrad), frame 533–539 và 1063–1094 |
| `ep_099f1666df886001` | 1431 | `joint_limit` | State `right_wrist_roll_joint` vượt 2,39 mrad, frame 380–473 |
| `ep_54dd2d921f64c2a9` | 1097 | `joint_limit` | State `right_wrist_roll_joint` vượt 2,03 mrad, frame 515–516 |

Cách đọc, là giả định, chưa lần theo từng frame:

- `joint_limit` là khớp đo được, không phải lệnh. Tư thế đỡ ngửa (D-25) giữ `wrist_roll` ở giới hạn, và khớp đo vượt quá dung sai dưới 1 mrad.
- `joint_mapping` là cùng kiểu ngón giữa tay phải mà DA-33 thấy ở planner-4 (2/50) và ở seed 1098 của release cũ; ở đây là 4/541 (0,7 %).

Planner-6 của DA-33 (D-29) giải IK xa giới hạn `wrist_roll`. Nếu Hiếu nhận planner-6, kho sinh lại trên planner-6 và phải kiểm lại xem 3 ca `joint_limit` có hết không. RunPlan bản 2 chờ kết quả planner-6, khoảng 12:00 ngày 5/11/2026. C và C+ phải dùng chung một planner. Planner-6 không đạt (mục 11), nên bản 2 đóng băng trên release planner-5 này.

Kết quả thô ở `rtx3060:~/denso-da34-pool/fwdata/` (không commit):

- lô `gen/s1-pool-1104` và `quality.jsonl` (sha256 `49c26d25…`);
- release `releases/tray_s1_f9433b028c52`;
- thư mục QA `pipeline/src_297dedb9d3d39a72`;
- report DA-17 `reports/tray-p5-1104`.

## 11. Đóng băng bản 2 trên planner-5 (5/11/2026)

**Planner-6 không đạt.** Thử nghiệm 50 seed của DA-33 cho 38/50 thành công, dưới ngưỡng 44/50; planner-5 đạt 44/50. Planner-6 gỡ được 2 ca timeout `REACH` của planner-5, nhưng thêm 7 ca hủy vì nghiêng khay ở cuối, so với 1 ca của planner-5. Theo quy tắc Hiếu đặt trước khi có kết quả (nhận planner-6 chỉ khi 0 cờ QA, thành công ≥ 44/50 và qua bộ lọc ≥ 85 %), bản 2 đóng băng trên release planner-5 `tray_s1_f9433b028c52` của mục 10. Ba ca `joint_limit` không kiểm lại: việc đó chỉ cần khi nhận planner-6. Số của planner-6 lấy theo báo cáo của DA-33 qua phiên điều phối; file này không chạy lại.

Mục 7 ghi kho dùng `da33-planner-4+cfg.815b822a`. Kho đã sinh lại trên `da33-planner-5+cfg.4e2a4505` theo quyết định trên #93 và #103 (mục 10). Mọi số khác của mục 7 giữ nguyên: seed 1000–1609, mức 1, bộ lọc nghiêng ≤ 10° và xê dịch ≤ 20 mm, cỡ tập 320 / 160.

| Mục | Giá trị |
|---|---|
| RunPlan | [`he-tray-v2.yaml`](../../configs/runplans/tray/he-tray-v2.yaml), **`rp_a04c14e79dfd`**, lock [`he-tray-v2.lock.json`](../../configs/runplans/tray/he-tray-v2.lock.json). `supersedes: rp_c49c99c8d8da` (bản 1, chưa chạy). Lần đóng băng đầu `rp_301f08e73358` bị thay sau review #116, trước mọi job |
| Nhánh | Chỉ **C** (160 episode) trên `psi0-baseline-egodex-he`. C+ ở [`round-tray-cplus.yaml`](../../configs/runplans/tray/round-tray-cplus.yaml), kế thừa bản 2, `n_add` = 160 |
| Release | `tray_s1_f9433b028c52`, 541 episode, một planner (mục 10) |
| Chọn tập | Bỏ 7 reject của DA-03, rồi qua bộ lọc: còn 429 episode. Tập lồng nhau cùng một thứ tự hash, ở [`demo_sets-v2.json`](../../configs/runplans/tray/demo_sets-v2.json) |
| Hash tập | `N40` = `85278f2016d3…`, `N80` = `fb28061125b8…`, **`C` = `a202cc028a2e…`**, `A` = `b914d6412f59…`. Muối `DA-34/demo-sets/v1` là muối duy nhất của module; thứ tự mới vì `release_hash` mới |
| Ghim chất lượng | [`quality-s1-pool-1104.jsonl`](../../configs/runplans/tray/quality-s1-pool-1104.jsonl), sha256 `49c26d25…`: số đo theo seed (nghiêng, xê dịch, độ rơi), không có dữ liệu episode. Commit vào repo để `runplan check` chạy được trên CI mà không cần `rtx3060` |
| Ghim QA | sha256 của `qa/reports.jsonl` = `fb402300…`, ngưỡng `qa-1@fb6ddaf9f48c` |
| Eval | 270 episode mỗi nhánh: mức 0 là 30 lượt lặp, mức 1 và 2 mỗi mức 120 seed dev, 240 cảnh cho chỉ số chính. Đồng hồ sim, nhiễu gieo theo episode (mục 8) |
| Ngân sách | Trần 36 CU, cap 18 CU mỗi lần, `runs: [C]`, `round_runs: [C_PLUS]`; watcher là `scripts/colab/cu_watch.py session --cap 18` dưới một guard mỗi lô, một lô mỗi tài khoản |
| Recipe | `psi0-stage3.yaml` như bản 1, ghi đè `train.validation_steps: 2000` |
| Ghim thêm (review #116) | `interpretation.rules_sha256`: khối quy tắc mục 9 giữa hai dấu `tier2-rules`. `demo_sets.file_sha256`: cả file tập demo, nên sửa `episode_indices` cũng bị bắt; `check` còn tính lại `set_hash` từ seed. `pinned_files`: sha256 của `configs/sim/tray.yaml`, `configs/splits/default.yaml`, 9 file nguồn cảnh, scorer và vòng eval của `flywheel_simple/tray/` và 5 file `flywheel_simple/wbc/`. Ghim theo file thay vì commit repo vì plan không biết commit chứa chính nó, và `check` kiểm được trên CI không cần lịch sử git. Kiểm lúc khởi chạy job, không chặn CI (quyết định bên dưới) |
| Kiểm theo release | Trên `rtx3060`: `runplan check he-tray-v2.yaml --release <thư mục release>` (có trong `--launch`) đối chiếu `episode_indices` của từng tập với export của release. File tập demo chỉ có hai danh sách đã sắp xếp, nên chỉ release biết index nào của seed nào. Ngày 5/11: khớp; dời một index thì lệnh báo lỗi |
| `delta_pp` | Bỏ ở bản 2. δ là biên của quy tắc HE-T (mục 4, cần nhánh B); quy tắc bậc 2 đọc CI, không dùng δ. Bản 1 giữ δ = 10 và id cũ |

**[Đã chốt 5/11/2026, Hiếu] mã sim ghim kiểm lúc khởi chạy job, CI chỉ cảnh báo.** 16 sha256 của `pinned_files` vẫn nằm trong lock; id không đổi. Các file đó thuộc story khác và có thể đổi trên master sau khi đóng băng. Vì vậy:

| Chế độ | Phần đầu vào riêng của DA-34 (khối quy tắc mục 9, hash tập tính lại từ seed, `demo_sets.file_sha256`, file chất lượng, report QA) | `pinned_files` (`configs/sim/tray.yaml`, split, `flywheel_simple/tray/*`, `wbc/*`) |
|---|---|---|
| CI: `runplan check <plan>` và `test_v2_matches_the_files_it_names` | Lỗi, mã thoát 1 | Chỉ cảnh báo (dòng `warning:` ở stderr, cảnh báo pytest), mã thoát 0 |
| Khởi chạy job: `runplan check <plan> --release <thư mục release> --launch` | Lỗi | **Lỗi**, kèm "re-freeze or record a Decision"; `--launch` bắt buộc có `--release`, nên kiểm cả `episode_indices` |

Mọi lần khởi chạy train hoặc eval của C và C+, kể cả launcher của nhiệm vụ 2, phải chạy lệnh `--launch` trước, và **từ chối chạy** khi lệnh thoát khác 0. Với C+, chạy lệnh đó trên `round-tray-cplus.yaml`: lệnh kiểm plan round và cả plan bản 2 mà nó kế thừa. Nếu lệnh báo lệch: trước job đầu tiên thì đóng băng lại bản 2; sau đó phải ghi một `Decision`, không sửa sha256 trong plan.

Trình tự khởi chạy một job train hoặc eval (C, C+):

```bash
# 1. Trên máy có release (rtx3060), từ bản checkout master của repo:
uv run python -m flywheel_psi0.tray.runplan check configs/runplans/tray/he-tray-v2.yaml \
    --release ~/denso-da34-pool/fwdata/releases/tray_s1_f9433b028c52 --launch \
  || { echo "runplan check --launch failed: do not launch"; exit 1; }
# C+: thay he-tray-v2.yaml bằng round-tray-cplus.yaml (kiểm cả plan bản 2).
# 2. Train trên Colab: guard rồi watcher của phiên, --cap 18, theo scripts/colab/cu_watch.py;
#    chỉ bắt đầu job khi file .ready có và heartbeat của guard mới. Một lô mỗi tài khoản.
# 3. Eval trên rtx3060: server qua scripts/g0/serve_psi0.sh serve (gieo nhiễu theo episode),
#    client flywheel_simple.tray.run ở thời gian sim (mặc định).
```

Điều kiện trước khi chạy, vẫn còn mở:

- Fine-tune C chỉ chạy từ master sau khi PR đóng băng này được merge, và sau lô của DA-26 (một lô mỗi tài khoản).
- Eval ở thời gian sim, seed điều kiện gửi lúc reset và bộ nạp giải mã frame khi đọc **đã có trên master** (hotfix `ee02e0b`, `flywheel_simple/tray/run.py`). Server gieo nhiễu theo episode cũng đã có: `docker/psi0/serve_psi0_seeded.py` (#97), và `scripts/g0/serve_psi0.sh serve` dùng nó (`3fc46c5`). Chỉ còn mở phép kiểm tất định trên GPU của mục 8.5 (cùng checkpoint, 3 điều kiện mức 0, mỗi điều kiện 2 lượt), cần GPU nên do Hiếu chạy.
- Quy tắc đọc bậc 2 ở mục 9: **[Đã chốt 5/11/2026, Hiếu]**, khối quy tắc ghim bằng `interpretation.rules_sha256`.
