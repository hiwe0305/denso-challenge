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

**Sửa 6/11/2026 (mục 13.2, change log).** Câu "chạy lại riêng một episode cho ra đúng nó" ở hàng "Nhiễu của policy" **không đúng** khi render bằng EGL trên `rtx3060`. Câu cũ giữ nguyên ở trên. Server đã tất định: cùng request và cùng seed cho cùng reply. Nhưng ảnh reset của client lệch 13/230400 pixel, mỗi pixel 1 mức, nên một rollout không lặp lại được. Ghép cặp theo điều kiện giữa các nhánh vẫn đúng **theo cảnh**: cùng seed, cùng mức, cùng cảnh dựng lại. Ghép cặp không đúng theo từng rollout. Chạy lại một episode do lỗi hạ tầng sẽ cho một rollout mới của cùng điều kiện. **[Đã chốt 6/11/2026, Hiếu]**: chạy tiếp, ghi giới hạn, không đổi quy tắc đọc.

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

## 12. Nhiệm vụ 2: chạy fine-tune C trên Colab (soạn 5/11/2026, chưa chạy)

Một phiên Colab L4 cho một lần train: nhánh C của `rp_a04c14e79dfd`, job `da34-t2-ft-c-s0`, cap 18 CU. Mã phía VM là [`flywheel_psi0.tray.colab_train`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/colab_train.py). Hai pha `setup` và `train` tự từ chối nếu plan không phải `rp_a04c14e79dfd`, nếu `runplan check` không qua, nếu một file của `pinned_files` lệch, hoặc nếu bản cắt C tải lên không khớp tập C (marker, `set_hash`, `release_hash`, n, index nguồn, `stats_psi0.json` riêng). Phần sau train dùng lại của DA-26: `scripts/he/he1_colab.py stage` và `persist`, `scripts/he/he1_fetch.py` (kéo checkpoint bằng rsync qua `colab ssh --proxy-mode`, kiểm sha256, quy tắc dừng sớm). Mọi lệnh `he1_fetch` của C truyền `--remote-work /content/da34`; tùy chọn này và bản cắt theo seed đến từ PR #121 (`chore-demo-subset-tray-seeds`, phạm vi DA-26, Hiếu cho phép 5/11/2026).

**Điều kiện trước khi chạy.**

1. PR này đã merge; mọi lệnh chạy từ bản checkout `master`.
2. PR #121 đã merge. Trước #121, `scripts/he/demo_subset.py` từ chối tập khay vì kiểm `set_hash` trên `episode_indices`; #121 kiểm trên seed và lấy index của từng seed từ `meta/flywheel_export.json` của bản phát hành, còn `he1_fetch.py` có thêm `--remote-work`. #121 chỉ merge sau khi các phiên DA-26 chạy lại đã qua setup. Bản cắt thử bằng mã của #121 trên rtx3060 qua `cut_problems` (5/11/2026, đã xóa sau khi kiểm).
3. Lô của DA-26 đã xong và guard của nó đã thoát; `colab sessions` trống (một lô mỗi tài khoản). Hiếu cho chạy.
4. Số dư ít nhất 32 CU: sàn 14 cộng cap 18.
5. Laptop thức suốt lần chạy.

**rtx3060: kiểm lúc khởi chạy và dựng bản cắt** (0 CU; `D` là bản `master` mới, ví dụ `~/denso-da34-master-<sha>`):

```bash
cd $D && export PYTHONPATH=$(ls -d $PWD/packages/*/src | paste -sd:)
PY=~/denso-da34-pool/.venv/bin/python
REL=~/denso-da34-pool/fwdata/releases/tray_s1_f9433b028c52
CUT=~/denso-da34-pool/fwdata/cut-c-rp_a04c14e79dfd
$PY -m flywheel_psi0.tray.runplan check configs/runplans/tray/he-tray-v2.yaml --release $REL --launch \
  || { echo "runplan check --launch failed: do not launch"; exit 1; }
$PY scripts/he/demo_subset.py --src $REL --sets configs/runplans/tray/demo_sets-v2.json --set C \
  --out $CUT/sets/C/G1WholebodyTrayTransferTeleop-v0
$PY -m flywheel_psi0.tray.colab_train check --work $CUT   # "cut and plan hold", exit 0
```

**Laptop: kéo bản cắt, rồi guard và watcher** (thư mục gốc là bản checkout `master`):

```bash
rsync -a --delete --partial-dir=.rsync-partial rtx3060:denso-da34-pool/fwdata/cut-c-rp_a04c14e79dfd/ fwdata/tray/cut-c/   # --delete: no stale file mixes in
export PATH=~/project/wm-wam-review/.venv-colab-cli/bin:$PATH
colab sessions; colab usage
S=da34-t2-ft-c-s0
R=fwdata/colab/batch-$(date +%Y%m%d-%H%M%S); mkdir -p fwdata/colab && mkdir $R && git rev-parse HEAD > $R/master.sha
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py guard --registry "$0" --floor 14 --log "$0/guard.jsonl"; echo "exit $?"' $R < /dev/null > $R/guard.out 2>&1 &
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name "$1" --gpu L4 --cap 18 --floor 14 --persist "python3 scripts/he/he1_fetch.py once --session $1 --registry $0 --dest fwdata/tray/runs --remote-work /content/da34" --log "$0/$1.jsonl"; echo "exit $?"' $R $S < /dev/null > $R/$S.out 2>&1 &
```

`ready` và `vm` như ở [he-1.md](he-1.md) mục 7: `ready` chặn bước sau khi watcher chưa thấy L4 hoặc heartbeat của guard cũ hơn 120 s; `vm` chỉ SSH khi watcher còn sống và phiên còn trong danh sách.

```bash
ready() { if ( until [ -f $R/$1.ready ]; do grep -q '^exit ' $R/$1.out && exit 1; sleep 5; done
  [ -f $R/guard.beat ] && [ $(( $(date +%s) - $(stat -c %Y $R/guard.beat) )) -lt 120 ] )
  then echo "$1 READY"; else echo "$1 NOT READY: do not start the job"; return 1; fi; }
vm() { grep -q '^exit ' $R/$1.out && { echo "$1: watcher exited, no ssh"; return 1; }
  colab sessions < /dev/null | grep -q "^\[$1\]" || { echo "$1: not listed, no ssh"; return 1; }
  ssh -o ProxyCommand="colab ssh --proxy-mode -s $1" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@colab "${@:2}"; }
```

**Phiên C.** Mỗi bước chỉ chạy khi bước trước đã xong. `probe` tạo `/content/da34` trên VM.

```bash
ready $S && python3 scripts/he/he1_fetch.py probe --session $S --registry $R --dest fwdata/tray/runs --remote-work /content/da34 \
  || { colab stop -s $S; echo "$S: not ready or proxy too slow, session stopped"; }
git archive --format=tar.gz HEAD | vm $S 'mkdir -p /content/da34/fw && tar -xz -C /content/da34/fw'
rsync -a --partial-dir=.rsync-partial -e "ssh -o ProxyCommand='colab ssh --proxy-mode -s $S' -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
  fwdata/tray/cut-c/sets/ root@colab:/content/da34/sets/
VMPP=fw/packages/flywheel-psi0/src:fw/packages/flywheel-contracts/src
vm $S "cd /content/da34 && PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_train check" \
  || { colab stop -s $S; echo "$S: cut or plan does not hold on the VM, session stopped"; }
vm $S "cd /content/da34; nohup setsid bash -c 'PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_train setup; echo setup exit \$?' > setup.log 2>&1 < /dev/null &"
vm $S 'tail -2 /content/da34/setup.log'   # chờ "setup exit 0"
vm $S "cd /content/da34; nohup setsid bash -c 'PYTHONPATH=$VMPP Psi0/.venv-psi/bin/python -m flywheel_psi0.tray.colab_train train; echo train exit \$?' > train.log 2>&1 < /dev/null &"
nohup setsid bash -c 'python3 scripts/he/he1_fetch.py follow --session "$1" --registry "$0" --dest fwdata/tray/runs --remote-work /content/da34 --every 600 --stop-when-done; echo "exit $?"' $R $S < /dev/null > $R/$S.fetch.log 2>&1 &
```

Khi đã mount được Drive, thêm sau `setup`: `colab drivemount -s $S /content/drive`, rồi `persist` của he1_colab với `--work /content/da34 --to /content/drive/MyDrive/denso/da34`.

**Trong và sau lúc chạy.** Quy tắc dừng sớm, `ALERT` và các mã thoát là của `he1_fetch` ([he-1.md](he-1.md) mục 7): dự kiến CU khi `ckpt_40000` đã về laptop, tính từ bước 2 200. Watcher dừng phiên ở cap 18 CU kể cả khi chưa đủ 40.000 bước. Khi xong, ghi dòng `measured` cho `job_da34_ft_C`: CU thật theo `colab usage`, số bước, giờ, trỏ về dòng ước lượng. Checkpoint về `fwdata/tray/runs/da34-t2-ft-c-s0/` trên laptop (không commit). Eval của nhiệm vụ 3 chạy trên `rtx3060`.

**Chuyển checkpoint sang rtx3060 cho eval (nhiệm vụ 3).** Chỉ chuyển khi `fetched.json` báo `final` (đủ `ckpt_40000`, sha256 trên laptop đã khớp VM). Danh sách sha256 lập trên laptop, rồi kiểm lại trên rtx3060 sau khi chép; lệch một file thì không eval.

```bash
J=fwdata/tray/runs/da34-t2-ft-c-s0
python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["final"] else 1)' $J/fetched.json \
  || { echo "not final: no hand-off"; exit 1; }
(cd $J && find . -type f -not -path '*/.*' -print0 | sort -z | xargs -0 sha256sum) > $J.sha256
rsync -a --partial-dir=.rsync-partial --exclude='.*' $J/ rtx3060:denso-da34-pool/fwdata/tray/runs/da34-t2-ft-c-s0/
ssh rtx3060 'cd denso-da34-pool/fwdata/tray/runs/da34-t2-ft-c-s0 && sha256sum -c --quiet' < $J.sha256 \
  && echo "hand-off OK" || echo "hand-off FAILED: do not eval"
```

Giả định của ước lượng, chưa đo: tải bản cắt lên VM (khoảng 1,3 GB, 160/541 của 4,5 GB) với tốc độ không dưới 6 MB/s của `probe`, tức tối đa khoảng 4 phút. Tốc độ tải lên chưa đo; `probe` chỉ đo chiều kéo về.


## 13. Nhiệm vụ 3: eval C (6/11/2026)

_Chạy trên `rtx3060`, 0 CU. Story [DA-34](../product/stories/DA-34-thi-nghiem-egocentric-khay.md) nhiệm vụ con 3.2–3.4. Mọi số của eval C là **sơ bộ, trên dev**._

### 13.1 Khởi chạy

| Mục | Giá trị |
|---|---|
| Mã | master `2e57f60`, tức #147 squash: [`eval_set`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/eval_set.py), [`act_log`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/act_log.py), [`eval_driver`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/eval_driver.py), [`eval_batch`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/eval_batch.py). `git archive` vào `~/denso-da34-master-2e57f60` |
| Kiểm lúc khởi chạy | `runplan check he-tray-v2.yaml --release … --launch`: "rp_a04c14e79dfd, 270 eval conditions, launch OK", mã 0, 2026-11-06T03:17:33Z |
| Điều kiện | `eval_set` dựng 3 dataset LeRobot một khung mỗi episode, từ `eval.by_level` của plan. `conditions.sha256` = `b9c38b37…`. Bản dựng bằng mã master giống từng byte bản dựng trước (284 file). Env khay dựng lại cảnh chỉ từ `tray.sample` (seed, mức) |
| Checkpoint | C `ckpt_40000` của `da34-t2-ft-c-s0` (mục 12). Danh sách sha256 432 file qua trên `rtx3060`. `fetched.json` báo `final: false`, `train: failed`: đây là race của `stage` đã ghi ở story 2.3, `result.json` ok ở bước 40 000. Lệch với điều kiện "chỉ chuyển khi `fetched.json` báo `final`" của mục 12; chuyển vì sha256 khớp |
| Server | `scripts/g0/serve_psi0.sh serve` (launcher gieo nhiễu theo episode), image `psi0@sha256:0d580125…`, `127.0.0.1:22185`, 7,2 GB VRAM |
| Lô | Bắt đầu 2026-11-06T03:17:58Z. **1 worker**, scope `MemoryMax=8G`. 27 lô 10 episode: mức 1 và 2 xen kẽ, mức 0 cuối **[Đã chốt 6/11/2026, Hiếu]**. Mỗi lô gồm một client `eval_driver` và một proxy `act_log`. Episode thiếu chạy lại tối đa 3 lần |
| Vì sao 1 worker | Server Ψ₀ `serve_psi0_simple` tại `cda3fdf` giữ **một** trạng thái RTC (`previous_action`) cho mọi client. Client của SIMPLE không gửi `session_id`, nên hai client chạy song song trên cùng server sẽ dùng chung trạng thái đó mà không báo lỗi. Server thứ hai không vừa GPU 12 GB |
| Log cho Agent QA/QC | Trong `~/denso-da34-pool/fwdata/tray/eval/eval-c-rp_a04c14e79dfd/<lô>/attempt-<k>/` (không commit): `requests.jsonl` (mọi request), `outcomes.jsonl` (mọi episode, có `scorer_steps`), `traces/` (trace DA-38 từng chu kỳ), `eval/` (thống kê của SIMPLE), `data/evals/…` (video). Mỗi lần chạy một lô ghi một dòng vào `runs.jsonl` ở thư mục gốc |

### 13.2 Kiểm tất định (mục 8.5): hỏng

Cùng checkpoint C, 3 điều kiện mức 0, mỗi điều kiện 2 lượt, thời gian sim, EGL. Thời điểm: 2026-11-06T01:50–02:11Z.

| Seed | Lượt 1 | Lượt 2 |
|---|---|---|
| 1 000 100 | `L-PLACE-POSE`, 5/7 bước, khay ở x = −1,21 (bàn B) | `L-TRAY-TILT`, 3/7, khay ở x = +0,72 (gần bàn A) |
| 1 000 101 | `L-TIMEOUT`, 3/7, x = +0,73 | `L-TRAY-TILT`, 5/7, x = −0,46 |
| 1 000 102 | `L-TRAY-TILT`, 5/7, x = −1,19 | `L-TRAY-TILT`, 5/7, x = −0,49 |

Khoanh nguyên nhân:

- **Server tất định.** Một request cố định (reset + seed) gửi 3 lần cho cùng hash action. Seed khác cho hash khác; gửi lại seed cũ thì hash cũ trở lại.
- **Ảnh reset của client không tất định dưới EGL.** Ảnh `head_stereo_left` đầu tiên của hai lượt lệch nhau 13/230 400 pixel (39 giá trị kênh), mỗi giá trị lệch 1 mức, ở hàng 320–323, cột 276–282. State gửi lên giống hệt. Reply đầu tiên vì thế đã khác, rồi vòng kín tách hẳn.
- **OSMesa (render CPU) không dùng được.** 364 s tới request `/act` đầu tiên, 54 s mỗi request, so với 0,83 s khi dùng EGL. Cả lô sẽ mất nhiều tuần.

Hệ quả: xem đoạn sửa ở mục 8.2. Quy tắc đọc của mục 9 không đổi.

### 13.3 Chạy thử và thời gian

| Lượt | Kết quả | Thời gian |
|---|---|---|
| Thử 2 mức 1 + 2 mức 2 (02:28–02:43Z) | 4/4 hỏng: `L-PLACE-POSE` 1, `L-TIMEOUT` 3. Không có lỗi hạ tầng | 200–220 s tường mỗi episode hỏng, tính cả khởi động. Client 3,5 GB RSS, khoảng 2,9 lõi. `/act` trung vị 0,38–0,41 s, 188 request mỗi episode, đều 200 |
| Kiểm trước PR #147, 1 episode mức 1 (02:54Z) | `L-PLACE-POSE`, 5/7 bước, mã 0, trace 7,1 MB, 2 video | 349 s, lúc máy tải 35: một `llama-server` của ollama (không thuộc đội) dùng khoảng 12 lõi và 84 % GPU. Latency server tăng khoảng 55 %, phần client tăng khoảng 52 % |
| 2 episode đầu của lô (03:18Z) | 2/2 hỏng | 188–189 s mỗi episode, máy rảnh. Ước lượng cả lô khoảng 14,4 giờ |

Episode hỏng chạy đủ 4 664 bước env (93,3 s sim). Client SIMPLE `b75c678` khi chạy 1 worker thoát mã 1 sau episode cuối, do thanh tiến trình in vào luồng đã đóng; mọi outcome đã ghi xong trước đó. `eval_batch` đặt `DEBUG=1` để tắt thanh tiến trình (như [trace.md](../g0/trace.md) mục 1).

### 13.4 Yaw và hướng đi (R3 của DA-38): số đo, chưa kết luận

Đo trên 4 episode chạy thử, mỗi 1 s sim: yaw của pelvis và `navigate_cmd` (chiều 32–35: vx, vy, vyaw, `target_yaw`).

- Robot quay khoảng π rồi đi về bàn B ở cả 4 episode: pelvis x đi từ +0,45 xuống −0,8…−0,9. Ở 3/4 episode, khay vẫn nằm ở bàn A.
- `target_yaw` của Ψ₀ không wrap về [−π, π]: có lúc lên tới +3,56 rad. Khi yaw đo qua ±π, yaw đo là −3,13 còn `target_yaw` là +3,19. Hiệu thô khoảng 6,3 rad; sau khi wrap chỉ khoảng 0,04 rad.
- 78 mẫu có hiệu thô trên 2,5 rad (56 + 7 + 4 + 11). Bỏ 8 mẫu có lệnh cũ của episode trước (vết của phép đo ghi trước request đầu tiên của episode), không mẫu nào có hiệu sau wrap trên 2,5 rad. Hiệu sau wrap lớn nhất là 1,25 rad, lúc đang quay; `target_yaw` đi trước yaw đo 0,3–0,5 rad.

Cách đọc **[Đề xuất]**, chưa kiểm ở mã của DA-13: nhãn R3 "`target_yaw` gần ngược yaw đo" có thể do bộ chẩn đoán so yaw mà không wrap góc. Việc kiểm thuộc DA-13. Trace từng chu kỳ của eval C (`traces/`) là đầu vào cho việc đó.

### 13.5 Giới hạn ghi cạnh mọi số của eval C

- Rollout không lặp lại được (mục 13.2). Episode chạy lại do hạ tầng là một rollout mới. Bộ đọc kết quả lấy lần xong sớm nhất của mỗi episode, đếm số rollout thừa, và không bao giờ chọn giữa các lần.
- `fetched.json` báo `final: false` do race (mục 13.1); checkpoint đủ và sha256 khớp.
- Cờ bước của scorer chỉ tính theo thứ tự, bắt đầu từ `approach_a` (hai lòng bàn tay trên tay cầm, trước mép bàn A). Một episode mang khay sang bàn B mà không qua `approach_a` có 0/7 bước. Tỉ lệ qua từng bước đọc theo định nghĩa này.
- 1 worker, đồng hồ sim. Thời gian tường phụ thuộc tải của máy, nhưng kết quả thì không (mục 8.1).
- Trace DA-38 của lô không có `timing`. Hook ghi `timing` vào `rollout_result.json` từ #148, nhưng lô chạy ở master `2e57f60`, trước #148. `steps.jsonl` vẫn có `t_state`, `t_image` từng chu kỳ.
- Checkout SIMPLE thực chạy là `6d10628`, không phải `b75c678` mà `code.simple` của plan ghim. Hai bản chỉ khác một file: task hai bàn (`g1_wholebody_locomotion_pick_between_tables_teleop.py`, 11 dòng `init_qpos`). Env khay không dùng file này. Kho S1 của release cũng sinh trên checkout này (cùng thư mục, qua symlink), nên train và eval của C dùng cùng một bản SIMPLE. Mọi file của `pinned_files` đều khớp. **Việc còn mở:** `runplan check --launch` không kiểm `code.simple`, nên lệch này không bị chặn. Đây là khoảng trống của công cụ, chưa sửa trong nhiệm vụ 3.

### 13.6 C-max: chuẩn bị, chưa train

**[Đã chốt 6/11/2026, Hiếu]** "Chuẩn bị sẵn, chưa train". C-max chỉ dùng khi quy tắc 0 của mục 9 xảy ra (p_C < 10 % ở mức 1–2) **và** Hiếu ra lệnh. Khi đó C+ không chạy. C-max hỏi "160 demo có quá ít không?" trước khi quy lỗi cho pipeline ảnh.

| Mục | Giá trị |
|---|---|
| RunPlan | [`he-tray-cmax.yaml`](../../configs/runplans/tray/he-tray-cmax.yaml), `rp_366283071c4a`, `status: draft`. `runplan check --launch` và `freeze` từ chối plan nháp. Khác bản 2 ở đúng 5 trường: `name`, `demo_sets`, `branches`, `budget`, `supersedes` (test). Cùng recipe, checkpoint gốc, seed train, eval 270, khối quy tắc và các file ghim |
| Tập | `CMAX` = cả kho dùng được: 429 episode (bỏ 7 reject DA-03, qua bộ lọc). File [`demo_sets-v2-cmax.json`](../../configs/runplans/tray/demo_sets-v2-cmax.json): tập N40, N80, C, A giữ nguyên hash của bản 2, thêm `CMAX` = `084ebc03…` theo cùng thứ tự hash |
| Bản cắt | `~/denso-da34-pool/fwdata/cut-cmax-draft` trên `rtx3060`: 429 episode, 610 069 frame, 3,6 GB, có danh sách sha256 (không commit). `demo_subset.py` của master `2e57f60`, 49 s |
| Ngân sách | Cap 18 CU, lấy suất của C+ (C+ không chạy khi quy tắc 0 xảy ra). Bậc 2 vẫn dưới trần 36 CU. Ước lượng 16,0 CU trên L4, giả định thời gian một bước không đổi theo số episode (chưa đo với 429) |
| `Decision` | [`he-tray-v2.rule0.decision.json`](../../configs/runplans/tray/he-tray-v2.rule0.decision.json): `dev_gate`, chủ thể `rp_a04c14e79dfd`, ngưỡng 0,10. Soạn 6/11 với `verdict: open`; từ 7/11 đã điền số đo của eval C, `verdict: fail`, Hiếu ký 8/11/2026 (mục 13.7). Lệnh của Hiếu về C-max ghi vào đó |

Hai biến thể chờ Hiếu chọn (`criteria.c_max_variants` của `Decision`):

| Biến thể | Số episode | Nguồn | Trạng thái |
|---|---|---|---|
| (i) chỉ S1 | 429 | Release `tray_s1_f9433b028c52`: cả kho S1 dùng được, gồm 160 episode của C | Sẵn sàng ở dạng nháp: plan `rp_366283071c4a`, `runplan check` qua, `--launch` từ chối |
| (ii) S1 cộng S2 | Chưa có số | 429 của S1, cộng S2 của lô `prod-1105` (DA-35). Hiếu đã chốt release 669 biến thể qua DA-03 (5/11/2026, [s2.md](../g0/tray/s2.md)) | Chưa sẵn sàng: chưa có release S2 (id, hash), nên chưa có tập, plan hay `runplan check` |

Khoảng trống của (ii), ghi trong `meta.gaps` của `Decision`, không tự điền số:

- `TrayRunPlan` chỉ nhận một release. Muốn S1 cộng S2 thì cần một release dựng từ cả hai lô, hoặc đổi schema plan; việc này thuộc story khác.
- Chưa so `action_layout` và feature của bản xuất S2 với release S1.
- Release S2 lệch chọn mẫu: 20,6 % biến thể bị DA-03 loại, dồn vào khớp xoay cổ tay và `waist_pitch`. Nó cũng có vài episode mức 0, còn S1 chỉ có mức 1.

Ước lượng CU của cả hai biến thể là 16,0 CU: cùng 40.000 bước, nên lấy theo 15,99 CU đo được của C. Đây là giả định: thời gian một bước được coi là không đổi theo số episode, chưa đo với 429 hay hơn 1000 episode.

Hai khoảng trống chung: quy tắc 0 đòi "kiểm pipeline ảnh" nhưng chưa có quy trình cho phép kiểm đó; bảng lỗi theo bước của C chỉ có khi eval C xong (đã có từ 7/11, mục 13.7).

Nếu C-max chạy, phép so C-max với C không có trong quy tắc bậc 2. Quy tắc đọc phải ghi trong `Decision` **trước** khi chạy eval C-max.

### 13.7 Kết quả eval C (sơ bộ, trên dev)

Đọc bằng [`eval_results`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/eval_results.py) trên bản sao log của lô (không có video), máy laptop, 7/11/2026. Mỗi episode lấy lần xong sớm nhất. Số khớp từng con số với phép đếm thô của phiên điều phối trên `rtx3060` (20:52Z 6/11).

**Chạy.** 27/27 lô xong ở lần chạy đầu (`attempt-0`), mã 0, không episode thiếu, không rollout thừa, không chạy lại. Từ 03:17:58Z tới 17:27:02Z 6/11/2026: **14,15 giờ tường**, 188,7 s mỗi episode (mỗi lô 10 episode: 1 838–1 940 s), khớp ước lượng 14,4 giờ. Mọi episode chạy hết giới hạn: 92,1–93,3 s sim. 50 787 request `/act`. `conditions.sha256` của bộ điều kiện đọc lại vẫn là `b9c38b37…`.

| Mức | n | Thành công | p | Wilson 95 % | CI bootstrap của plan |
|---|---|---|---|---|---|
| 0 (30 lượt lặp, một cảnh) | 30 | 0 | 0 % | 0–11,4 % | 0–0 % |
| 1 | 120 | 0 | 0 % | 0–3,1 % | 0–0 % |
| 2 | 120 | 0 | 0 % | 0–3,1 % | 0–0 % |
| **1–2 gộp (chỉ số chính)** | **240** | **0** | **0 %** | **0–1,6 %** | 0–0 % |
| Cả lô | 270 | 0 | 0 % | 0–1,4 % | – |

CI bootstrap theo điều kiện (`stats` của plan, 10 000 lần, seed 20261103) suy biến về một điểm khi không có lượt thành công nào. Vì vậy bảng ghi thêm khoảng Wilson 95 %.

Nhãn lỗi (mục 8.2, design 3.3):

| Mức | `L-TRAY-TILT` | `L-TIMEOUT` | `L-PLACE-POSE` | `L-PART-DROP` | `L-ONE-HAND` |
|---|---|---|---|---|---|
| 0 | 17 | 8 | 4 | 0 | 1 |
| 1 | 62 | 37 | 14 | 6 | 1 |
| 2 | 63 | 47 | 5 | 5 | 0 |
| 1–2 gộp | 125 (52 %) | 84 (35 %) | 19 (8 %) | 11 (5 %) | 1 |

Tỉ lệ qua từng bước của bộ chấm (`scorer_steps`, theo thứ tự `STEP_NAMES`; bước chỉ bật theo thứ tự, mục 13.5):

| Mức | `approach_a` | `grasp` | `lift` | `carry` | `reach_b` | `place` | `release_stand` |
|---|---|---|---|---|---|---|---|
| 0 | 93,3 % | 93,3 % | 93,3 % | 70,0 % | 66,7 % | 0 % | 0 % |
| 1 | 75,0 % | 75,0 % | 75,0 % | 59,2 % | 55,8 % | 0,8 % | 0 % |
| 2 | 75,0 % | 75,0 % | 75,0 % | 57,5 % | 55,0 % | 0 % | 0 % |
| 1–2 gộp | 75,0 % | 75,0 % | 75,0 % | 58,3 % | 55,4 % | 0,4 % | 0 % |

Số bước qua liên tiếp từ bước đầu, mức 1–2 (240 rollout), với nhãn lỗi:

| Bước qua | Rollout | Nhãn lỗi |
|---|---|---|
| 0 | 60 | `L-TIMEOUT` 41, `L-PART-DROP` 11, `L-PLACE-POSE` 8 |
| 3 (tới `lift`) | 40 | `L-TRAY-TILT` 29, `L-TIMEOUT` 10, `L-ONE-HAND` 1 |
| 4 (tới `carry`) | 7 | `L-TRAY-TILT` 6, `L-TIMEOUT` 1 |
| 5 (tới `reach_b`) | 132 | `L-TRAY-TILT` 90, `L-TIMEOUT` 32, `L-PLACE-POSE` 10 |
| 6 (tới `place`) | 1 | `L-PLACE-POSE` 1 |

Không rollout nào dừng ở 1 hay 2 bước: `approach_a`, `grasp` và `lift` bật cùng nhau. 19 rollout có 0 bước mà vẫn có nhãn `L-PART-DROP` hoặc `L-PLACE-POSE`. Đây là ca khay rời bàn A mà cờ `approach_a` không bật (mục 13.5); chưa xem video.

**Yaw (R3 của DA-38), số đo, chưa kết luận.** Trên cả 270 trace (1 215 000 chu kỳ): 730 147 chu kỳ (60,1 %) có |`target_yaw` − yaw đo| thô trên 2,5 rad. Sau khi wrap về [−π, π] còn 1 163 chu kỳ, ở 27 episode, lớn nhất 3,14 rad. Như vậy khác với 4 episode chạy thử ở mục 13.4 (0 chu kỳ sau wrap): có những đoạn `target_yaw` thật sự ngược hướng. Chưa xem các đoạn này ứng với pha nào; việc đọc thuộc DA-13.

**Đọc theo bậc 2 (mục 9).** p_C = 0/240 = 0 % ở mức 1–2 gộp, cận trên Wilson 1,6 %, dưới ngưỡng 10 %. **Quy tắc 0 xảy ra.** Theo đúng câu của quy tắc: Ψ₀ chưa học được task khay từ ảnh MuJoCo; **không chạy C+**; kiểm pipeline ảnh; ghi `Decision`. Quy tắc 1–6 không đọc, vì quy tắc 0 đã chặn và C+ không chạy. Mọi số trên là **sơ bộ, trên dev**, một seed train, kèm các giới hạn của mục 13.5.

Ghi cạnh, không đổi cách đọc: bảng bước cho thấy 55 % rollout mức 1–2 đã cầm, nhấc, mang khay tới bàn B, rồi hỏng ở bước đặt (`L-TRAY-TILT` là nhãn nhiều nhất của nhóm này). Đây là dữ kiện cho Hiếu khi chọn bước tiếp theo, không phải quy tắc mới.

**`Decision`.** [`he-tray-v2.rule0.decision.json`](../../configs/runplans/tray/he-tray-v2.rule0.decision.json) chốt nhánh này: `verdict: fail` (quy tắc 0 xảy ra), số đo ở `metrics`, Hiếu ký 8/11/2026. Bước tiếp theo Hiếu chọn là C+ (mục 17.1), không phải C-max. Bước tiếp theo đề xuất **[Đề xuất]**: C-max (i), chỉ S1, 429 episode, ước lượng 16 CU, plan nháp `rp_366283071c4a` (mục 13.6). Chưa launch; C-max chỉ chạy khi Hiếu duyệt. C-max (ii) vẫn trong danh sách khoảng trống.

## 14. Kiểm pipeline ảnh (T1, T2)

_Bước "kiểm pipeline ảnh" của quy tắc 0 (mục 13.7), khoảng trống đầu tiên trong `Decision` `dec_01M6QERTS21J48KPACJX83QC3R`. **[Đã chốt 7/11/2026, Hiếu]** "Chạy T1 + T2": trên `rtx3060`, 0 CU, không Colab, không train. Luật đọc dưới đây là **[Đề xuất]** (ngưỡng do phiên điều phối đề xuất, Hiếu chốt sau). Luật được commit **trước** rollout đầu tiên của T1, và không sửa sau khi thấy kết quả._

Chung cho T1 và T2:
- Cùng checkpoint C `ckpt_40000`, cùng client SIMPLE `psi0_decoupled_wbc`, thời gian sim, EGL, 1 worker, `eval_batch` và `eval_results` như eval C (mục 13.1).
- Mỗi điều kiện lấy lần xong sớm nhất.
- Rollout EGL không lặp lại được (mục 13.2). Vì vậy so sánh theo cặp điều kiện chỉ là so hai rollout, không phải hai lần đo cùng một rollout.
- Số đọc là **sơ bộ, trên dev**; T1 đọc trên cảnh train.

### 14.1 T1: eval trên điều kiện train của C

- **Điều kiện.** 20 episode của tập C, lấy tất định: 20 seed đầu theo thứ tự `sha256(salt | release_hash | seed)` mà `demo_sets` đã dùng ([`demo_sets-v2.json`](../../configs/runplans/tray/demo_sets-v2.json), salt `DA-34/demo-sets/v1`). Theo thứ tự đó là 1279, 1574, 1503, 1572, 1386, 1532, 1531, 1013, 1274, 1117, 1398, 1210, 1599, 1193, 1338, 1408, 1554, 1350, 1405, 1038; tất cả ở mức 1.
- **Cảnh.** Env khay dựng lại cảnh chỉ từ (seed, mức) qua `sample_episode`. Trước khi chạy, so tư thế khay, vùng đích và chỗ robot xuất phát với `tray.sample` đã ghi trong release.
- **Đọc** (p_T1 = số thành công / 20):

| Kết quả | Đọc |
|---|---|
| ≥ 5/20 | C học được cảnh train nhưng không tổng quát sang dev; thêm dữ liệu (C-max) có lý do |
| 1–4/20 | Yếu; báo kèm Wilson 95 % |
| 0/20 | Model không tái hiện được cảnh đã học; nghi chuỗi train/serve (chuẩn hóa action, `stats_psi0.json`, bố cục 36 chiều, ảnh đầu vào, chunk). Không train gì cho tới khi tìm ra lỗi |

- **Chỉ số phụ, báo cạnh:** tỉ lệ qua từng bước (`scorer_steps`), nhất là `reach_b` và `place`.

### 14.2 T2: đổi cách chạy, không train lại

- **Điều kiện.** 20 điều kiện dev đầu tiên của mức 1 trong eval C: seed 1 000 100–1 000 119, đúng các dòng `conditions.jsonl` của eval C.
- **Mốc.** Rollout eval C trên đúng 20 điều kiện này (lô `l1-000`, `l1-010`), ghép cặp theo điều kiện.
- **Kiểm tại nguồn** (Psi0 `cda3fdf`, SIMPLE `6d10628`):
  - Số action thực thi mỗi lần gọi đặt ở **server**: `psi0_serve_simple.py` trả `pred_actions[:Ta]`, với `Ta` = `--action-exec-horizon`. Client `psi0_decoupled_wbc` đưa mọi action nhận được vào hàng đợi, rồi mới hỏi lại.
  - Eval C chạy với `--action-exec-horizon 24 --rtc`, theo mặc định của `scripts/g0/serve_psi0.sh`, không phải 30. Khi đó `inference_delay` của RTC cố định bằng `Tp − Ta` = 6.
  - Khi bật RTC, server assert `Tp − Ta ≤ max_delay`. Checkpoint C có chunk `Tp = 30` và `max_delay = 8`, nên `Ta` phải ≥ 22.
  - **Vì vậy Ta = 10 với RTC bật không chạy được** nếu không sửa Psi0.
  - Tắt RTC không cần sửa Psi0: `RTC_FLAG=` (rỗng) trong `serve_psi0.sh`.
- **Biến thể.** Đề xuất gửi phiên điều phối 7/11/2026. **[Đã chốt 7/11/2026, Hiếu]** "Đồng ý": chạy hai biến thể dưới đây, so với mốc eval C. Ngưỡng đọc vẫn là [Đề xuất].

| Biến thể | `Ta` | RTC | Khác eval C ở |
|---|---|---|---|
| T2b | 24 | tắt | chỉ RTC |
| T2a′ | 10 | tắt | RTC và số action thực thi; so với T2b thì chỉ khác số action thực thi |

  So T2a′ với T2b để tách riêng tác động của `Ta`. Thứ tự chạy: T1, rồi T2b, rồi T2a′. Đổi cấu hình server thì khởi động lại server và ghi lệnh. Sau T2, trả server về cấu hình của eval C (`Ta = 24`, `--rtc`).
- **Đọc.** Một biến thể là "đáng xem" nếu thỏa một trong hai điều kiện:
  - hơn mốc ít nhất 3 thành công trên 20 điều kiện;
  - tỉ lệ qua bước `place` tăng rõ so với mốc. "Rõ" ở đây là ít nhất 3 điều kiện có `place` bật ở biến thể mà không bật ở mốc, nhiều hơn số điều kiện theo chiều ngược lại.
- Chạy lại eval đủ 270 episode với cấu hình mới cần Hiếu quyết riêng.

### 14.3 Kết quả T1 (sơ bộ, trên cảnh train)

- **Chạy.** Cây `bb4cef1` (nhánh `DA-34-t4-pipeline-check`), tập `t1-train-C20-bb4cef1` (sha256 `168cd1b8…`), server của eval C không đổi (`Ta = 24`, `--rtc`). Trên `rtx3060` từ 2026-11-06T21:08:32Z tới 22:11:46Z: 1,05 h, 2 lô 10, lần chạy 0, 0 thiếu, 189,4 s mỗi episode như eval C, không thấy `llama-server` trên GPU.
- **Kiểm cảnh** trước khi chạy: 20 seed × 14 trường của `tray.sample` (tư thế khay, vùng đích, chỗ robot xuất phát), sai lệch lớn nhất 0 so với release; cả 20 episode release đều ghi là thành công.
- **Số** (`eval_results` của repo, lần xong sớm nhất mỗi điều kiện):

| Tập | n | Thành công | Wilson 95 % (%) | approach_a | grasp | lift | carry | reach_b | place | release_stand | Loại lỗi |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T1, mức 1, cảnh train | 20 | 0 | 0,0–16,1 | 65,0 | 65,0 | 65,0 | 65,0 | 65,0 | 5,0 | 0,0 | TRAY-TILT 8, PART-DROP 5, TIMEOUT 4, PLACE-POSE 3 |
| Eval C, mức 1, dev (mục 13.7) | 120 | 0 | 0,0–3,1 | 75,0 | 75,0 | 75,0 | 59,2 | 55,8 | 0,8 | 0,0 | TRAY-TILT 62, TIMEOUT 37, PLACE-POSE 14, PART-DROP 6, ONE-HAND 1 |

  Bước xa nhất qua được ở T1: 7 episode không qua bước nào, 12 qua tới `reach_b`, 1 qua tới `place`.
- **Đọc theo luật 14.1:** 0/20, nên **nghi chuỗi train/serve; không train gì cho tới khi tìm ra lỗi**. Trên cảnh đã train, C qua các bước tới `reach_b` gần như trên dev, rồi tắc ở `place` như trên dev. Kết quả này không ủng hộ giả thuyết "C học được cảnh train nhưng không tổng quát"; vì vậy chưa có lý do cho C-max.
- `runs.jsonl` ở `rtx3060:~/denso-da34-pool/fwdata/tray/eval/check-t1-train-C20` (không commit).

### 14.4 Kết quả T2b: `Ta = 24`, RTC tắt (sơ bộ, trên dev)

- **Chạy.** Server của checkpoint C khởi động lại bằng `~/denso-da34-t4/serve.sh t2b 24 nortc` (script trên `rtx3060`):
  - dừng container của eval C (`docker stop -t 30`) lúc 2026-11-06T22:12:09Z;
  - chạy lại `scripts/g0/serve_psi0.sh serve` từ cùng cây `master` 7b585a7, cùng biến môi trường như eval C, cộng `ACTION_EXEC_HORIZON=24 RTC_FLAG=` (rỗng);
  - container mới `fw-psi0-psi0-run-daa657455cb9` có tham số `--action-exec-horizon 24`, không có `--rtc`; khỏe lúc 22:14:29Z.

  Lô từ cây `bb4cef1`, tập `t2-dev-L1-20-bb4cef1` (sha256 `0467f5e5…`), 22:14:39Z tới 23:17:11Z: 1,04 h, 2 lô 10, lần chạy 0, 0 thiếu, 186,6 s mỗi episode. Server nhận 3760 lần gọi `/act`, tức 188 mỗi episode, như eval C; log server không có lỗi; không thấy `llama-server` trên GPU.
- **Số**, ghép cặp với eval C trên đúng 20 điều kiện (`eval_results --baseline`):

| Bước | T2b qua (%) | Mốc eval C qua (%) | Cả hai | Chỉ T2b | Chỉ mốc | Không bên nào |
|---|---|---|---|---|---|---|
| approach_a | 55 | 80 | 11 | 0 | 5 | 4 |
| grasp | 50 | 80 | 10 | 0 | 6 | 4 |
| lift | 25 | 80 | 5 | 0 | 11 | 4 |
| carry | 0 | 65 | 0 | 0 | 13 | 7 |
| reach_b | 0 | 65 | 0 | 0 | 13 | 7 |
| place | 0 | 0 | 0 | 0 | 0 | 20 |
| release_stand | 0 | 0 | 0 | 0 | 0 | 20 |
| **Thành công** | 0/20 (Wilson 0–16,1 %) | 0/20 | 0 | 0 | 0 | 20 |

  Loại lỗi T2b: TIMEOUT 18, TRAY-TILT 1, PART-DROP 1. Số chu kỳ có yaw (quấn về ±π) vượt 2,5 rad: 9627 trên 90 000, so với 18 ở T1; đây là số đo, chưa kết luận.
- **Đọc theo luật 14.2:** `success_gain` = 0, `place_gain` = 0, nên T2b **không đáng xem**. Tắt RTC, giữ `Ta = 24`, làm robot không mang được khay: không điều kiện nào qua `carry`, trong khi mốc qua 13/20.
- `runs.jsonl` ở `rtx3060:~/denso-da34-pool/fwdata/tray/eval/check-t2b-ta24-nortc` (không commit).

### 14.5 Kết quả T2a′: `Ta = 10`, RTC tắt (sơ bộ, trên dev)

- **Chạy.** `~/denso-da34-t4/serve.sh t2a 10 nortc`:
  - dừng container T2b lúc 2026-11-06T23:17:22Z;
  - container mới `fw-psi0-psi0-run-01767bf45f77` có `--action-exec-horizon 10`, không có `--rtc`; khỏe lúc 23:19:34Z.

  Cùng cây và tập như T2b, từ 23:19:43Z tới 2026-11-07T00:57:10Z: 1,62 h, 2 lô 10, lần chạy 0, 0 thiếu, 290,9 s mỗi episode. Server nhận 9000 lần gọi `/act` (450 mỗi episode; ước tính trước là 466). Log server không có lỗi; không thấy `llama-server`.
- **Số.** Tỉ lệ qua từng bước, 20 điều kiện:

| Bước | T2a′ (`Ta` 10, RTC tắt) | T2b (`Ta` 24, RTC tắt) | Mốc eval C (`Ta` 24, RTC bật) |
|---|---|---|---|
| approach_a | 85 | 55 | 80 |
| grasp | 75 | 50 | 80 |
| lift | 50 | 25 | 80 |
| carry | 0 | 0 | 65 |
| reach_b | 0 | 0 | 65 |
| place | 0 | 0 | 0 |
| release_stand | 0 | 0 | 0 |
| **Thành công** | 0/20 | 0/20 | 0/20 |

  Loại lỗi T2a′: TIMEOUT 17, PART-DROP 2, TRAY-TILT 1. Yaw vượt 2,5 rad: 9766 chu kỳ trên 90 000, gần bằng T2b (9627).
- **Ghép cặp** (cả hai / chỉ T2a′ / chỉ đối chứng / không bên nào):

| Bước | T2a′ so với eval C | T2a′ so với T2b (chỉ khác `Ta`) |
|---|---|---|
| approach_a | 14 / 3 / 2 / 1 | 10 / 7 / 1 / 2 |
| grasp | 12 / 3 / 4 / 1 | 7 / 8 / 3 / 2 |
| lift | 8 / 2 / 8 / 2 | 3 / 7 / 2 / 8 |
| carry, reach_b | 0 / 0 / 13 / 7 | 0 / 0 / 0 / 20 |
| place, release_stand, thành công | 0 / 0 / 0 / 20 | 0 / 0 / 0 / 20 |

- **Đọc theo luật 14.2:** so với mốc, `success_gain` = 0, `place_gain` = 0, nên T2a′ **không đáng xem**.
- `runs.jsonl` ở `rtx3060:~/denso-da34-pool/fwdata/tray/eval/check-t2a-ta10-nortc` (không commit).

### 14.6 Tổng hợp T1, T2

- Theo luật viết trước: T1 0/20 trên cảnh train, nên **nghi chuỗi train/serve; không train gì, kể cả C-max, cho tới khi tìm ra lỗi**. T2b và T2a′ không đáng xem.
- Ghi cạnh số, không phải luật mới:
  - Không lần chạy nào qua `place` quá 1/20, dù trên cảnh train hay dev, dù `Ta` 24 hay 10, có hay không RTC. Vì vậy cách thực thi chunk không giải thích được lỗi ở `place`.
  - Tắt RTC thì không điều kiện nào qua `carry`, ở cả hai `Ta`. Với `Ta` 10, các bước đầu tốt hơn `Ta` 24 (`lift` 10 so với 5 điều kiện), nhưng không bù được việc mất RTC.
  - Vì vậy RTC (`inference_delay` 6) đang giữ phần lớn những gì C làm được tới `reach_b`.
- **Server đã trả về cấu hình của eval C** sau T2 (mục 14.2): `~/denso-da34-t4/serve.sh c 24 rtc` dừng container T2a′ lúc 2026-11-07T00:57:22Z; container `fw-psi0-psi0-run-4e2f7b1ee2d3` có `--action-exec-horizon 24 --rtc`, cùng checkpoint và cổng 22185, khỏe lúc 00:59:35Z. Server để chạy, không tắt.
- Bước kế tiếp do Hiếu quyết. Các chỗ nghi trong chuỗi train/serve đã liệt kê ở luật 14.1: chuẩn hóa action, `stats_psi0.json`, bố cục 36 chiều, ảnh đầu vào, chunk.

## 15. Kiểm chuỗi train/serve (A, B)

_Bước kế tiếp của luật 14.1 sau T1 0/20. **[Đã chốt 7/11/2026, Hiếu]** "Giao DA-34 làm": trên `rtx3060`, 0 CU, không train. Mục tiêu: tách hai khả năng "C chưa học được `place`" và "đầu vào lúc serve khác lúc train". Luật đọc và ngưỡng dưới đây là **[Đề xuất]**, commit **trước** lần chạy đầu tiên, không sửa sau khi thấy kết quả._

### 15.1 Đã đọc tại nguồn trước khi viết luật

Psi0 `cda3fdf`, SIMPLE `6d10628`, checkpoint C `ckpt_40000`:

- **Chuẩn hóa.**
  - `run_config.json` của C mang sẵn `action_min/max`, `state_min/max`, khớp `meta/stats_psi0.json` của tập C (sai lệch lớn nhất 0). State có 32 chiều, đệm 0 lên 36. Kiểu chuẩn hóa `bounds`, về [−1, 1].
  - `ActionStateTransform.model_post_init` đọc lại `stat_path` = `meta/stats_psi0.json` nếu đường dẫn này tìm thấy lúc serve (thư mục chạy, thư mục asset, `DATA_HOME`). Vì vậy phải kiểm stats mà server thật sự dùng.
- **Ảnh lúc train.** LeRobot giải mã mp4 bằng `pyav`, `pt_to_pil`, rồi `resize` + `center_crop` về 180 × 320. Màu (`color_jitter`) chỉ bật khi train, tắt ở split `val` và lúc serve.
- **Ảnh lúc serve.** Server nhận ảnh `uint8` dưới khóa `rgb_head_stereo_left`, rồi `resize` + `center_crop` như trên. Checkpoint không có `image_keys`, nên server dùng thứ tự trong payload; log của eval C có cảnh báo này, vô hại với một góc nhìn.
- **Lời nhắc.** Lúc train là `task.lower()`. Log server của eval C cho thấy client gửi đúng câu đó, viết thường. Lời nhắc không phải chỗ nghi.
- **State lúc serve** (`psi0_decoupled_wbc`):
  - qpos các khớp tay và cánh tay, sắp lại theo `STATE_SLICES`;
  - `waist_rpy` = qpos[13, 14, 12];
  - lệnh chiều cao base trước đó (0,74 lúc reset).

  Export đặt tên ba chiều 28–30 là `waist_roll/pitch/yaw_joint` và chiều 31 là `prev_base_height_command`. `modality.json` gọi chúng là `rpy` và `height`, còn dataset có thêm cột `observation.prev_torso_rpy`. Nghĩa của chiều 28–30 là một chỗ nghi.

### 15.2 Phần A: open-loop trên dữ liệu train của C

- **Frame.** 20 episode của T1 (mục 14.1) trong tập C, lấy mỗi frame thứ 10.
- **Nhãn stage của mỗi frame** lấy từ cờ `observation.tray_steps` của episode thô (lô `gen/s1-pool-1104`, qua `flywheel_export.json` của release):
  - stage của frame t là bước đầu tiên chưa bật, theo thứ tự `approach_a` … `release_stand`;
  - frame sau `release_stand` ghi là `done`, báo riêng;
  - nếu độ dài episode thô khác episode export thì không dùng nhãn, và báo.
- **Hai đường gọi trên cùng frame, cùng seed nhiễu:**
  - **Đường serve.** `POST /act` tới server eval C (`Ta` 24, `--rtc`), với `history.reset` và một seed riêng cho mỗi frame. Khi có reset, server bỏ qua nhánh RTC. Payload theo đúng định dạng của client SIMPLE: ảnh là frame mp4 của dataset giải mã thành `uint8`, state là 32 chiều thô của cột `states`, lời nhắc là `task.lower()`.
  - **Đường train.** Dataset của Psi0 dựng từ `launch_config.data` của C (split `val`, `no_aug`) trên bản cắt C ở `rtx3060`, rồi `Psi0Model.predict_action` với cùng seed. Cần tắt server để có VRAM, sau đó trả lại `Ta` 24 + `--rtc`.
- **Số đo.** Tính theo đơn vị chuẩn hóa [−1, 1] của từng chiều, trên 24 hàng đầu của chunk, chỉ các chiều action có biên độ khác 0:
  - `d_path`: sai lệch tuyệt đối trung bình giữa hai đường;
  - `e`: sai lệch giữa đường train và action thật `a[t:t+24]` (thiếu ở cuối episode thì lặp hàng cuối);
  - `h`: sai lệch của mốc "giữ nguyên action hiện tại" (`a[t]` lặp 24 lần) so với action thật;
  - `r` = trung vị `e` / trung vị `h`, tính theo stage.

**Luật đọc A** [Đề xuất]:

| Kiểm | Khớp | Lỗi | Giữa hai ngưỡng |
|---|---|---|---|
| A1, hai đường | trung vị `d_path` ≤ 0,01 và p95 ≤ 0,03 | trung vị > 0,05 hoặc p95 > 0,15: **lỗi chuỗi serve** | lệch nhỏ; báo theo chiều |
| A2, `place` | `r_place` ≤ 0,7 và `e_place` ≤ 1,5 × trung vị `e` của `approach_a` … `reach_b`: **C học được `place` open-loop** | `r_place` ≥ 1 (không hơn mốc giữ nguyên) hoặc `e_place` ≥ 2 × trung vị đó: **C chưa học được `place`** | yếu; báo |

Đọc gộp:
- A1 lỗi: sửa chuỗi serve trước mọi việc khác.
- A1 khớp và A2 chưa học: lỗi ở dữ liệu hoặc ở train.
- A1 khớp và A2 học được: open-loop đúng, nên lỗi nằm ở vòng kín (đầu vào khác, phần B; hoặc sai số cộng dồn).

Bước kế tiếp do Hiếu quyết.

### 15.3 Phần B: so ảnh, state và stats

- **B1, stats.** Trong container Psi0, dựng cấu hình như `Server.__init__` (không cần GPU), rồi so:
  - `action_min/max`, `state_min/max` mà server dùng với `stats_psi0.json` của C;
  - đường dẫn `stat_path` tìm được lúc serve (nếu có) và sha256 của file đó.

  **Khớp** khi sai lệch lớn nhất bằng 0 và không có file nào khác được đọc. Nếu khác thì đó là **lỗi chuỗi serve**.
- **B2, B3, phát lại.** Ba episode train đầu của T1 (seed 1279, 1574, 1503) được phát lại qua client eval thật: `eval_batch` với server giả `replay_server`, trả action của release, 24 frame mỗi lần gọi, như cổng phát lại ở mục 8.1. `replay_server --dump` lưu state, ảnh và lời nhắc của từng request. Request thứ k ứng với frame 24k của dataset.
- **B2, ảnh.** So với frame mp4 cùng chỉ số: kích thước, kiểu dữ liệu, thứ tự kênh (sai lệch giữ nguyên so với đảo RGB/BGR), PSNR.

| Kết quả | Đọc |
|---|---|
| Kích thước như dataset (360 × 640 × 3, `uint8`), thứ tự kênh đúng, PSNR ở frame 0 ≥ 30 dB | **Ảnh khớp** |
| Kích thước khác, kênh đảo, hoặc PSNR ở frame 0 < 20 dB | **Ảnh khác** (camera, tư thế, render hoặc màu); ghi rõ cái nào |
| PSNR ở frame 0 từ 20 tới 30 dB | Báo; xem ảnh |

  Chỉ số phụ: PSNR theo k (phát lại trôi dần nên giảm dần là bình thường).
- **B3, state.** So 32 chiều với cột `states` của dataset, theo đơn vị chuẩn hóa:
  - ở frame 0: sai lệch từng chiều;
  - cả episode: trung vị sai lệch từng chiều, tương quan và hệ số góc với từng chiều của dataset.

| Kết quả | Đọc |
|---|---|
| Mọi chiều sống: trung vị sai lệch ≤ 0,05, chiều tương quan cao nhất là chính nó | **State khớp** |
| Có chiều trung vị > 0,2, hoặc chiều tương quan cao nhất là chiều khác, hoặc hệ số góc âm hay lệch xa 1 | **State khác** (thứ tự, đơn vị, dấu hoặc nghĩa); ghi chiều |
| Còn lại | Báo theo chiều |

- **Đọc gộp B:** một kiểm "khác" là đủ để kết luận đầu vào lúc serve khác lúc train, ở trường được ghi.

### 15.4 Chung

- Log, ảnh và `runs.jsonl` để trên `rtx3060`, không commit.
- Ghi dòng ước lượng trong sổ chi phí trước khi chạy, dòng thực đo sau khi chạy.
- Server eval C (`Ta` 24, `--rtc`) có thể tắt trong phần A để lấy VRAM, và được trả lại cấu hình đó khi xong. Ghi lệnh và thời điểm.
- Số đọc là sơ bộ.

### 15.5 Kết quả A (sơ bộ)

Chạy 7/11/2026 trên `rtx3060`, mã `cb0a386`, 0 CU. Luật 15.2 không đổi.

- **Frame.** 2783 frame của 20 episode T1, chia theo stage:

  | `approach_a` | `grasp` | `lift` | `carry` | `reach_b` | `place` | `release_stand` | `done` |
  |---|---|---|---|---|---|---|---|
  | 479 | 15 | 238 | 480 | 799 | 628 | 144 | 0 |

  Độ dài episode thô bằng độ dài episode export ở cả 20 episode. Có 30 chiều action sống.
- **Đường serve.** `POST /act` tới server eval C (`Ta` 24, `--rtc`, có reset, seed riêng cho mỗi frame), scope `da34-chain-serve`, từ 02:32:25Z tới 02:50:45Z.
- **Đường train.** Server eval C dừng lúc 02:50:59Z. Container Psi0 chạy từ 02:52:03Z tới 03:15:43Z, mã thoát 0, 2783 dòng. Ảnh 320 × 180; lời nhắc viết thường, như lúc train.
- **Trả server.** `serve.sh c 24 rtc` khởi động container `fw-psi0-psi0-run-41b48a6a5890` với `--action-exec-horizon 24 --rtc`, khỏe lúc 03:19:35Z.

**A1, hai đường: khớp.** Trung vị `d_path` = 0, p95 = 0. Đã kiểm trực tiếp trên hai file: 2783/2783 chunk giống hệt từng bit (sai lệch thô lớn nhất 0,0). Khi có reset, chuỗi serve (giải mã ảnh, `resize`/`crop`, chuẩn hóa state, lời nhắc, bỏ chuẩn hóa action) cho đúng kết quả của chuỗi train. Kiểm này không đụng tới nhánh RTC.

**A2, `place`: theo luật là chưa học được**, vì `r_place` = 2,73 ≥ 1.

| Stage | Frame | `e` (trung vị) | `e` p90 | `h` (giữ nguyên) | `r` = `e`/`h` |
|---|---|---|---|---|---|
| approach_a | 479 | 0,018 | 0,070 | 0,042 | 0,43 |
| grasp | 15 | 0,084 | 0,111 | 0,495 | 0,17 |
| lift | 238 | 0,032 | 0,052 | 0,016 | 2,06 |
| carry | 480 | 0,028 | 0,053 | 0,006 | 4,94 |
| reach_b | 799 | 0,025 | 0,057 | 0,002 | 14,59 |
| **place** | 628 | **0,041** | 0,108 | 0,015 | **2,73** |
| release_stand | 144 | 0,048 | 0,102 | 0,002 | 27,40 |

`e_place` / trung vị `e` của `approach_a` … `reach_b` (0,028) = 1,47: dưới ngưỡng 1,5 của "học được", còn xa ngưỡng 2 của "chưa học".

Ghi cạnh số, không phải luật mới:
- `r` ≥ 1 cả ở `lift`, `carry`, `reach_b`, những bước mà vòng kín vẫn qua 65 %. Lý do: trong một chunk 24 hàng ở các stage này robot gần như đứng yên, nên mốc giữ nguyên rất mạnh.
- Vì vậy luật A2 đọc là "chưa học" chủ yếu nhờ vế `r`. Theo vế `e`, sai số ở `place` chỉ cao hơn các bước đầu khoảng một nửa, và nhỏ (0,04 trên nửa biên độ [−1, 1]).

**Đọc gộp theo 15.2:** A1 khớp và A2 chưa học, nên lỗi ở dữ liệu hoặc ở train. Đọc cùng B (mục 15.6): đầu vào ảnh lúc eval khác lúc train, nên kết quả vòng kín của eval C, T1, T2 chưa nói được C có làm được `place` hay không. T1r (mục 15.7) kiểm điều này.

`serve.jsonl`, `train.jsonl`, `a-result.json` ở `rtx3060:~/denso-da34-pool/fwdata/` (`tray/chain-check/` và `psi0/chain-check/`), không commit.

### 15.6 Kết quả B (sơ bộ)

Chạy 7/11/2026 trên `rtx3060`, mã `cb0a386`, 0 CU. Luật 15.3 không đổi.

**Đọc gộp B: đầu vào lúc serve khác lúc train, ở ảnh.** Stats khớp. State khớp về thứ tự, đơn vị và nghĩa; luật bắt vài chiều ngón cái, giải thích ở dưới.

- **B1, stats: khớp.**
  - Server không tìm thấy `stat_path` = `meta/stats_psi0.json` lúc serve, nên không file nào khác được đọc.
  - Biên `action_min/max`, `state_min/max` mà server dùng bằng đúng `stats_psi0.json` của tập C (sha256 `1c9211ff…`): sai lệch lớn nhất 0 ở cả bốn. State có 32 chiều, đệm 0 lên 36.
- **Phát lại.** Lô `b-replay`: 3/3 episode chạy hết, mã thoát 0, 153 s. Có 175 request được lưu (58, 57, 60).

**B2, ảnh: khác** ở cả ba episode, vì PSNR thấp. Kích thước, kiểu dữ liệu và thứ tự kênh đều khớp.

| Seed | Kích thước, kiểu | MAE ở frame 0 (đảo kênh) | PSNR ở frame 0 | PSNR theo request (nhỏ nhất – lớn nhất) |
|---|---|---|---|---|
| 1279 | 360 × 640 × 3, `uint8` | 15,8 (47,8) | 16,48 dB | 14,0 – 19,7 |
| 1574 | 360 × 640 × 3, `uint8` | 15,9 (47,9) | 16,43 dB | 11,6 – 18,5 |
| 1503 | 360 × 640 × 3, `uint8` | 15,7 (47,7) | 16,53 dB | 13,1 – 19,6 |

So ảnh bằng mắt, frame 0 và 30:
- Camera, tư thế, bàn và hai tay trùng chỗ.
- Khay của eval là hộp xanh đặc, đáy mờ đục. Khay của dữ liệu train là thùng lưới đục lỗ (mesh SimReady).
- Mặt dưới và quanh bàn cũng khác.
- Ảnh eval tối hơn, khoảng 0,85 × ảnh train + 7.

**Nguyên nhân, đã kiểm tại nguồn:**
- `flywheel_simple.tray.visuals.default_manifest_path()` chỉ tìm `fwdata/simple/tray/simready/manifest.json` trong các thư mục cha của mã.
- Không thấy manifest thì `mjcf.py` dựng cảnh bằng khối hình học trơn mà không báo. Ngược lại, `generate.py` từ chối chạy khi thiếu manifest, trừ khi có `allow_plain`.
- Cả 160 episode của C ghi `visuals_revision` `4763fbf…`, đúng manifest trong `~/denso-da33`, nơi sinh dữ liệu.
- Các cây đã chạy eval C (`denso-da34-master-2e57f60`), T1, T2 (`denso-da34-t4-bb4cef1`) và lần phát lại này không có manifest, nên revision là `none`.
- Vậy eval C (mục 13.7), T1 và T2 (mục 14) đều chạy trên ảnh mà C chưa thấy lúc train.

Đề xuất, Hiếu quyết, không làm trong DA-34:
- PR riêng cho chủ `flywheel_simple`: eval từ chối chạy khi thiếu manifest, hoặc khi revision khác revision của dữ liệu train.
- Chạy lại T1 với manifest `4763fbf`.

**B3, state: theo luật là khác**, nhưng không phải lỗi thứ tự, đơn vị hay nghĩa.
- Ở frame 0, sai lệch của mọi chiều sống là 0,000.
- Hai cánh tay và hông (chiều 14–30): trung vị sai lệch ≤ 0,024. Tương quan cao nhất là chính chiều đó, hệ số góc gần 1. Vậy `waist_rpy` = qpos[13, 14, 12] đúng nghĩa với chiều 28–30 của dataset; chỗ nghi ở 15.1 bỏ.
- Chiều 31 chết (biên độ 0).
- Các chiều luật bắt:

| Seed | Chiều | Trung vị | Chiều tương quan cao nhất (tương quan với chính nó) | Hệ số góc | Đọc |
|---|---|---|---|---|---|
| 1279 | 7 `right_hand_thumb_0` | 0,0001 | 7 (0,990) | 0,37 | ngón gần như đứng yên, hệ số góc không ổn định |
| 1574 | 0 `left_hand_thumb_0` | 0,233 | 0 (0,924) | 1,72 | ngón cái trôi khi tiếp xúc |
| 1574 | 2, 3, 4 | ≤ 0,006 | 9, 12, 3 (≥ 0,985) | 0,98–1,00 | các khớp ngón chuyển động cùng nhau nên tương quan gần bằng nhau |
| 1503 | 0, 7 | 0,125; 0,051 | chính nó (≥ 0,994) | 1,60; 0,90 | báo, ngón cái trôi khi tiếp xúc |

- **Lời nhắc.** Client gửi câu gốc có chữ hoa ("Pick up the parts tray from table A …"). `serve_psi0_simple` đổi sang chữ thường, nên khớp `task.lower()` lúc train. Mục 15.1 ghi "client gửi viết thường" là chưa chính xác: viết thường là do server.

Dump, ảnh so sánh (`b-img-*.png`) và `b-result.json` ở `rtx3060:~/denso-da34-pool/fwdata/tray/chain-check/`, không commit.

### 15.7 T1r: chạy lại T1 với cảnh SimReady

_**[Đã chốt 7/11/2026, Hiếu]** "Oke chạy lại T1 cho tôi", sau kết quả B2 (mục 15.6). Luật đọc dưới đây là **[Đề xuất]**. Luật được viết và commit **trước** khi đọc PSNR của bước kiểm trước và trước rollout đầu tiên của T1r, và không sửa sau khi thấy kết quả._

- **Chạy.** Chỉ khác T1 (mục 14.3) ở cảnh render:
  - Cây `~/denso-da34-t1r-bb4cef1` là bản chép của cây T1 `bb4cef1`. Thư mục `fwdata/simple/tray/simready/` được chép nguyên từ `~/denso-da33` (không symlink, không sửa; manifest sha256 `eb2886e4…`).
  - Những thứ giữ nguyên như T1: tập `t1-train-C20-bb4cef1` (sha256 `168cd1b8…`); server của eval C (`Ta` 24, `--rtc`), sau khi phần A trả server về cấu hình đó; cùng launcher `batch.sh`, scope `MemoryMax=8G`, 1 worker; `eval_results` của repo, lấy lần xong sớm nhất.
  - Output đặt ở thư mục mới `check-t1r-simready`; lần chạy cũ không bị ghi đè.
  - Không sửa `flywheel_simple`.
- **Kiểm trước khi chạy:**

| Kiểm | Đạt | Không đạt |
|---|---|---|
| `visuals_revision(default_manifest_path())` trong cây T1r | `4763fbf…`, như 160 episode của C | Không chạy; báo |
| PSNR ở frame 0 khi phát lại 3 episode train (seed 1279, 1574, 1503, cách làm như B2) qua client eval của cây T1r | ≥ 20 dB ở cả ba: chạy; dưới 30 dB thì ghi kèm | < 20 dB ở một episode: không chạy; báo |

  Ghi PSNR theo từng episode và kết quả B2 theo luật 15.3.
- **Đọc chính.** Dùng luật 14.1 cho p_T1r (số thành công trên 20):
  - ≥ 5/20;
  - 1–4/20, báo Wilson 95 %;
  - 0/20.
- **So với T1.** Ghép cặp theo điều kiện, từng bước. Đếm số điều kiện ở mỗi ô: cả hai, chỉ T1r, chỉ T1, không bên nào.
  - `place` của T1r "tốt hơn rõ" khi số điều kiện "chỉ T1r" hơn số điều kiện "chỉ T1" ít nhất 3, giống ngưỡng `place_gain` ở mục 14.2.
  - Mọi bước khác cũng báo theo cùng cách.

| Kết quả | Đọc |
|---|---|
| p_T1r ≥ 5/20 | Ảnh lệch là nguyên nhân chính của T1 0/20. Số của eval C, T1, T2 đo trên cảnh trơn nên không đại diện cho C. Chạy lại eval C với SimReady cần Hiếu quyết |
| p_T1r 1–4/20, hoặc `place` tốt hơn rõ | Ảnh lệch là một phần nguyên nhân; báo kèm phần A |
| p_T1r 0/20 và `place` không tốt hơn rõ | Ảnh lệch không giải thích được lỗi ở `place`; đọc cùng A2 (mục 15.2) |

- **Chỉ số phụ, báo cạnh:** loại lỗi, số chu kỳ có yaw vượt 2,5 rad, thời gian mỗi episode, số lần gọi `/act`.
- Không chạy lại eval C đầy đủ và không train gì nếu chưa có lệnh của Hiếu.

### 15.8 Kết quả T1r (sơ bộ)

_Đọc theo luật 15.7, luật không đổi sau khi thấy kết quả. Nhãn "sơ bộ, trên dev" như T1._

**Kiểm trước** (02:45:17Z, 166 s, CPU, chạy song song với đường serve của phần A):

| Kiểm | Kết quả | Đọc |
|---|---|---|
| `visuals_revision(default_manifest_path())` | `4763fbfaa4f8…`, manifest sha256 `eb2886e4…` | Đạt |
| PSNR frame 0, seed 1279 / 1574 / 1503 | 34,88 / 34,85 / 34,97 dB (trước khi chép: 16,48 / 16,43 / 16,53) | Đạt, cả ba ≥ 30 dB |
| MAE frame 0 (đảo kênh) | 2,62 / 2,64 / 2,59 (35,2–35,3) | B2 khớp |
| PSNR trung vị theo request | 27,3 / 19,4 / 21,5 dB | Ghi kèm; các frame sau lệch dần vì vòng hở |
| B3 | Không đổi so với mục 15.6 | Ghi kèm |

**Chạy.** Scope `da34-check-t1r` (`MemoryMax=8G`, 1 worker), 03:19:53Z–04:36:24Z, 2 chunk 10 episode (2458,1 s và 2134,4 s), attempt 0, exit 0, không thiếu episode. `CODE_SHA` `bb4cef1`. Server eval C (`Ta` 24, `--rtc`) như T1, vẫn chạy sau T1r.

**Đọc chính.** p_T1r = **1/20** (5 %, Wilson 95 % 0,9–23,6 %; T1: 0/20, 0–16,1 %). Thành công duy nhất là seed 1038, xong ở 29,5 s mô phỏng; ở T1, seed này dừng sau `reach_b` (`L-TIMEOUT`).

| Bước | T1r | T1 | Cả hai | Chỉ T1r | Chỉ T1 | Không bên nào |
|---|---|---|---|---|---|---|
| `approach_a` | 15 | 13 | 10 | 5 | 3 | 2 |
| `grasp` | 15 | 13 | 10 | 5 | 3 | 2 |
| `lift` | 15 | 13 | 10 | 5 | 3 | 2 |
| `carry` | 15 | 13 | 10 | 5 | 3 | 2 |
| `reach_b` | 14 | 13 | 9 | 5 | 4 | 2 |
| `place` | 1 | 1 | 0 | 1 | 1 | 18 |
| `release_stand` | 1 | 0 | 0 | 1 | 0 | 19 |

- `place`: chỉ T1r 1, chỉ T1 1, hiệu 0 < 3, nên **không tốt hơn rõ**.
- Các bước đầu: hiệu "chỉ T1r" trừ "chỉ T1" là 1–2, dưới ngưỡng 3.
- Hai lần chạy chọn điều kiện khác nhau dù cùng tập: 8 điều kiện đổi kết quả ở `carry`, theo cả hai chiều.

**Theo bảng 15.7:** p_T1r ở khoảng 1–4/20, nên **ảnh lệch là một phần nguyên nhân; báo kèm phần A**. Ghi kèm:
- Thành công là 1 điều kiện. Khoảng Wilson của T1r và T1 chồng nhau.
- Ở `place`, ghép cặp không thấy khác (1 và 1).

**Chỉ số phụ:**

| Chỉ số | T1r | T1 |
|---|---|---|
| Loại lỗi | `L-PLACE-POSE` 11, `L-TIMEOUT` 5, `L-TRAY-TILT` 3 | `L-TRAY-TILT` 8, `L-PART-DROP` 5, `L-TIMEOUT` 4, `L-PLACE-POSE` 3 |
| Bước đạt xa nhất (số điều kiện) | 0 bước: 5; 4 bước: 1; 5 bước: 13; 7 bước: 1 | – |
| Chu kỳ có yaw vượt 2,5 rad (sau khi quấn góc) | 1 / 86 813 (max 2,93 rad) | 18 / 90 000 (max 2,85 rad) |
| Thời gian thật mỗi episode | 229,6 s | 189,4 s |
| Số lần gọi `/act` (reset) | 3627 (20) | 3760 (20) |

- `L-PLACE-POSE` 11/20: khay tới bàn B và nằm trên mặt bàn, nhưng sai tư thế đặt. Ở T1, `L-TRAY-TILT` cộng `L-PART-DROP` là 13/20.
- Ghi đây là quan sát, không có luật đọc riêng: với cảnh SimReady, lỗi dời từ "nghiêng hoặc làm rơi khi mang" sang "đặt sai tư thế".
- Mỗi episode chậm hơn 40 s, có thể vì render lưới SimReady; chưa đo riêng.

**Đọc chung A, B, T1r:**
- A1: đường serve và đường train khớp từng bit (mục 15.5), nên chuẩn hóa, stats và tiền xử lý ảnh lúc serve không có lỗi. Nhánh RTC chưa kiểm.
- B2: ảnh lúc serve khác ảnh train vì cây eval thiếu manifest SimReady (mục 15.6). Đã sửa cho T1r.
- Sửa ảnh làm T1 đổi từ 0/20 sang 1/20, nhưng không đổi `place`.
- A2: theo luật, `place` chưa học được.
- **Đọc chung:** ảnh lệch có góp phần, nhưng không giải thích được lỗi ở `place`. Nguyên nhân còn lại chính là C chưa học `place`.
- Eval C, T1, T2 đều đo trên cảnh trơn, khác cảnh train. Trên 20 cảnh train, T1r cho thấy khác biệt này đổi kết quả của các bước trước `place` theo cả hai chiều, nhưng không đổi `place`. Chạy lại eval C với SimReady, hoặc đi tiếp C-max, cần Hiếu quyết.

## 16. Eval C trên cảnh SimReady (chạy lại)

_**[Đã chốt 7/11/2026, Hiếu]** "Chạy lại eval C". Mục này được viết và commit **trước** lô đầu tiên. Story DA-34 nhiệm vụ con 3.8. Chạy trên `rtx3060`, 0 CU, không train._

### 16.1 Vì sao chạy lại, luật đọc

- **Vì sao chạy lại.** Eval C ở mục 13 đo trên cảnh trơn: cây eval thiếu manifest SimReady, nên khay và cảnh được render bằng khối trơn (`visuals_revision` `none`), còn 160 episode của C được ghi với revision `4763fbf` (mục 15.6). T1r (mục 15.8) đã chạy lại 20 cảnh train với SimReady.
- **Luật không đổi.** Dùng nguyên quy tắc 0 và luật bậc 2 của mục 9 (khối `tier2-rules`, ghim bằng sha256 trong RunPlan bản 2). Chỉ số chính là p_C trên 240 điều kiện mức 1–2 gộp. Mức 0 báo riêng (mục 8.2).
- **Kết quả cũ.** Mục 13.7 và 14 giữ nguyên làm bản ghi, nhưng **không** dùng để đọc quy tắc 0. Quy tắc 0 đọc trên lần chạy này. `Decision` quy tắc 0 không ký và không đổi verdict ở đây; Hiếu quyết sau khi có kết quả.
- Không train, không chạy C-max khi chưa có lệnh của Hiếu.

### 16.2 Chạy

Mọi thứ giữ như eval C (mục 13.1), chỉ khác cây mã và cảnh render.

| Mục | Giá trị |
|---|---|
| Mã | master `079160d` (sau #157), `git archive` vào `~/denso-da34-master-079160d`, `TREE_SHA` trong cây |
| Cảnh | `fwdata/simple/tray/simready/` chép nguyên từ `~/denso-da33` (`cp -a`, không symlink, không sửa; `diff -r` trùng), manifest sha256 `eb2886e4…` |
| RunPlan, điều kiện | Bản 2 `rp_a04c14e79dfd`, 270 điều kiện; dùng lại tập `rp_a04c14e79dfd-2e57f60` của eval C, `conditions.sha256` `b9c38b37…` (`eval_batch` kiểm lại) |
| Server | Checkpoint C `ckpt_40000`, `Ta` 24, `--rtc`, `127.0.0.1:22185` (container `fw-psi0-psi0-run-41b48a6a5890`, cấu hình trả về sau phần A) |
| Lô | `eval_batch`, 1 worker, scope `MemoryMax=8G`, `MemorySwapMax=0`, 27 lô 10 episode: mức 1 và 2 xen kẽ, mức 0 cuối; tối đa 3 lần cho mỗi lô |
| Output | Thư mục mới `~/denso-da34-pool/fwdata/tray/eval/eval-c-simready-rp_a04c14e79dfd`; thư mục của eval C cũ không bị ghi đè |
| Đọc | `eval_results`, mỗi điều kiện lấy lần xong sớm nhất |

**Chặn theo từng lô.** `--simple-python` của `eval_batch` trỏ tới script vận hành `~/denso-da34-t6/simple-guard.sh` trên máy (không nằm trong repo, không sửa `flywheel_simple`). Trước mỗi lần khởi động client SIMPLE, tức mỗi lô và mỗi lần chạy lại, script kiểm:
- `visuals_revision(default_manifest_path())` trong cây phải là `4763fbf…`;
- sha256 của manifest phải là `eb2886e4…`.

Nếu khác, script thoát mã 97 mà không chạy episode nào; sau 3 lần, `eval_batch` dừng cả lô. Mỗi lần kiểm ghi một dòng vào `~/denso-da34-t6/guard.log`. Đã thử cả hai chiều: cây này cho chạy; cây `bb4cef1` không có SimReady bị chặn (revision `none`, mã 97).

### 16.3 Kiểm trước khi chạy

| Kiểm | Kết quả | Ngưỡng |
|---|---|---|
| `visuals_revision(default_manifest_path())` trong cây | `4763fbfaa4f8…` | Bằng `4763fbf` |
| PSNR ở frame 0, phát lại 3 episode train (seed 1279, 1574, 1503) qua client eval của cây này và qua `simple-guard.sh`, cách làm như B2 (mục 15.3) | 34,88 / 34,85 / 34,97 dB, MAE 2,62 / 2,64 / 2,59 (đảo kênh 35,2–35,3); B2 khớp ở cả ba, B1 khớp. Giống từng số với kiểm trước của T1r (mục 15.8). Guard ghi `ok` lúc 04:51:25Z | ≥ 30 dB ở cả ba: **đạt** |

### 16.4 Chỉ số phụ: tư thế cuối của khay so với vùng đích

_Thêm **sau khi thấy T1r**. Đây là chỉ số báo cạnh, **không phải luật đọc**, và không đổi cách đọc quy tắc 0._

- **Lý do.** Ở T1r có 11/20 lượt `L-PLACE-POSE`; khay lệch vùng đích 5,6–18,4 cm.
  - Phiên điều phối nêu: vùng đích không hiện trong ảnh và bị dịch ngẫu nhiên ±5 cm, ±10° ở mức 1–2 (`POSE_JITTER`, `YAW_JITTER` của [`randomize.py`](../../packages/flywheel-simple/src/flywheel_simple/tray/randomize.py)).
  - Chỉ số này đo xem lỗi đặt là lệch vị trí hay lệch góc, và lệch bao nhiêu.
- **Cách tính.** [`place_error`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/place_error.py) tính cho từng rollout mà `eval_results` chọn, theo đúng phép kiểm `_in_target` của bộ chấm:
  - khoảng cách: |xy cuối của khay − xy đích|;
  - sai số góc: nhỏ hơn trong hai sai số, so với yaw đích và yaw đích + π, vì khay đối xứng khi quay nửa vòng;
  - đích dựng lại từ (mức, seed) bằng `sample_episode`; dung sai lấy từ `configs/sim/tray.yaml` (5 cm, 10°).
  - Chạy lại trên T1r ra đúng: `L-PLACE-POSE` lệch 5,6–18,4 cm; lượt thành công (seed 1038) lệch 1,2 cm, 7,5°, nằm trong dung sai.
- **Báo cáo.** Trung vị và khoảng 10–90 % của khoảng cách và sai số góc, cùng số rollout trong dung sai, theo từng nhóm:
  - mỗi mức;
  - mức 1–2 có `reach_b`;
  - mức 1–2 theo từng nhãn lỗi.

### 16.5 Báo cáo theo mốc

- Lúc bắt đầu chạy: báo kèm giờ dự kiến xong.
- Xong mức 1–2: báo số thô.
- Xong cả lô: báo số thô; viết kết quả, dòng thực đo trong sổ chi phí, mở PR.

### 16.6 Kết quả (sơ bộ, trên dev)

_Đọc theo mục 16.1. Luật không đổi sau khi thấy kết quả. Đọc bằng `eval_results` của cây chạy (`079160d`) trên `rtx3060`, có yaw, mỗi điều kiện lấy lần xong sớm nhất. Số khớp từng con số với phép đếm thô của phiên điều phối._

**Chạy.**
- Thời gian: 04:58:31Z–22:10:49Z ngày 7/11/2026, **17,2 giờ tường**, 229,4 s mỗi episode (mỗi lô 10 episode: 1 923–2 566 s).
- 27/27 lô xong ở lần chạy đầu (`attempt-0`), mã 0, không episode thiếu, không rollout thừa.
- Guard ghi `ok` ở cả 27 lần khởi động client; không lần nào bị chặn.
- 47 611 request `/act`. Output 11 GB, không commit.
- GPU dùng chung với job của một đội khác trong một phần thời gian chạy.

| Mức | n | Thành công | p | Wilson 95 % | CI bootstrap của plan |
|---|---|---|---|---|---|
| 0 (30 lượt lặp, một cảnh) | 30 | 5 | 16,7 % | 7,3–33,6 % | 3,3–30,0 % |
| 1 | 120 | 9 | 7,5 % | 4,0–13,6 % | 3,3–12,5 % |
| 2 | 120 | 11 | 9,2 % | 5,2–15,7 % | 4,2–15,0 % |
| **1–2 gộp (chỉ số chính)** | **240** | **20** | **8,3 %** | **5,5–12,5 %** | **5,0–12,1 %** |
| Cả lô | 270 | 25 | 9,3 % | 6,4–13,3 % | – |

Tỉ lệ qua từng bước của bộ chấm:

| Mức | `approach_a` | `grasp` | `lift` | `carry` | `reach_b` | `place` | `release_stand` |
|---|---|---|---|---|---|---|---|
| 0 | 93,3 % | 93,3 % | 93,3 % | 90,0 % | 90,0 % | 23,3 % | 16,7 % |
| 1 | 60,8 % | 60,8 % | 60,8 % | 60,8 % | 60,8 % | 10,8 % | 7,5 % |
| 2 | 73,3 % | 73,3 % | 73,3 % | 71,7 % | 68,3 % | 11,7 % | 7,5 % |
| 1–2 gộp | 67,1 % | 67,1 % | 67,1 % | 66,2 % | 64,6 % | 11,2 % | 7,5 % |

Nhãn lỗi:

| Mức | `L-PLACE-POSE` | `L-TIMEOUT` | `L-TRAY-TILT` | `L-PART-DROP` | `L-ONE-HAND` |
|---|---|---|---|---|---|
| 0 | 16 | 1 | 8 | 0 | 0 |
| 1 | 68 | 24 | 10 | 6 | 3 |
| 2 | 63 | 18 | 20 | 5 | 3 |
| 1–2 gộp | 131 (55 %) | 42 (18 %) | 30 (13 %) | 11 (5 %) | 6 (3 %) |

- Ở mức 1–2 có 20 thành công nhưng chỉ 18 lượt bật cờ `release_stand`. Hai lượt thành công ở mức 2 (seed 1000142 và 1000196, xong ở khoảng 30 s mô phỏng) có cả 7 cờ bước đều tắt. Đây là giới hạn cờ bước ở mục 13.5. Thành công tính theo `success` của bộ chấm.
- Yaw: 1 493 trên 1 139 427 chu kỳ vượt 2,5 rad sau khi quấn góc (lớn nhất 3,14 rad); lần chạy trên cảnh trơn là 1 163 trên 1 215 000.

**Đọc theo bậc 2 (mục 9).**
- p_C = 20/240 = **8,3 %** ở mức 1–2 gộp, dưới ngưỡng 10 %. **Quy tắc 0 xảy ra.**
- Theo đúng câu của quy tắc: Ψ₀ chưa học được task khay từ ảnh MuJoCo; **không chạy C+**; ghi `Decision`.
- Quy tắc 1–6 không đọc.
- Ghi kèm, không đổi cách đọc: cận trên của khoảng tin cậy (Wilson 12,5 %, bootstrap 12,1 %) vượt 10 %. Quy tắc 0 đọc trên ước lượng điểm p_C, như đã viết.
- Mọi số là **sơ bộ, trên dev**, một seed train, kèm các giới hạn ở mục 13.5.

**So với lần chạy trên cảnh trơn** (mục 13.7; chỉ là số báo cạnh, ghép cặp trên cùng 270 điều kiện):
- Thành công: 25 điều kiện chỉ lần này thành công, 0 điều kiện chỉ lần cũ thành công.
- `place`: 34 chỉ lần này, 1 chỉ lần cũ.
- `reach_b`: 72 chỉ lần này, 43 chỉ lần cũ.
- Lỗi dời từ `L-TRAY-TILT` (52 % trên cảnh trơn) sang `L-PLACE-POSE` (55 % lần này).

**Chỉ số phụ: tư thế cuối của khay** (mục 16.4; không phải luật). Bảng dưới là các lượt `L-PLACE-POSE`; dung sai là 5 cm và 10°.

| Mức | n | Khoảng cách p10 / p50 / p90 (cm) | Nhỏ nhất–lớn nhất (cm) | Sai số góc p10 / p50 / p90 (°) | Chỉ lệch vị trí | Chỉ lệch góc | Lệch cả hai | Trong dung sai lúc cuối |
|---|---|---|---|---|---|---|---|---|
| 0 | 16 | 2,5 / 9,5 / 17,6 | 0,9–28,6 | 1,5 / 6,9 / 12,1 | 11 | 3 | 2 | 0 |
| 1 | 68 | 5,2 / 10,1 / 19,9 | 0,4–36,1 | 2,1 / 8,4 / 18,8 | 38 | 6 | 23 | 1 |
| 2 | 63 | 6,1 / 11,2 / 32,0 | 2,7–54,7 | 1,4 / 7,3 / 17,5 | 40 | 2 | 21 | 0 |

- Ở mức 1–2, phần lớn lượt `L-PLACE-POSE` lệch vị trí: 78/131 chỉ lệch vị trí, 44 lệch cả hai, 8 chỉ lệch góc.
- Trung vị lệch khoảng 10–11 cm, gấp đôi dung sai 5 cm.
- 20 lượt thành công ở mức 1–2 lệch 1,3 / 3,0 / 4,4 cm và 1,9 / 3,8 / 8,5° (p10 / p50 / p90).
- Một lượt `L-PLACE-POSE` ở mức 1 nằm trong dung sai lúc cuối. Nhãn lỗi lấy theo lúc khay đứng yên sai chỗ lần đầu, nên khay có thể đã vào vùng đích sau đó.

**`Decision`.** Ghi lại kết quả mới vào [`he-tray-v2.rule0.decision.json`](../../configs/runplans/tray/he-tray-v2.rule0.decision.json):
- `verdict: fail` theo quy tắc 0; `signed_by` vẫn chờ Hiếu.
- Số của lần chạy trên cảnh trơn chuyển vào `metrics.plain_visuals_record`, ghi rõ chỉ là bản ghi.
- `next_step_proposed` (C-max (i)) được viết trên kết quả cảnh trơn. Giữ hay đổi bước tiếp theo là quyết định của Hiếu; chưa launch gì.

## 17. Nhiệm vụ 5: C+, vòng Failure → Data trên lỗi của C

_Story DA-34 nhiệm vụ 5 (AC 6). Mốc theo mục 5: C+ phải bắt đầu train trước 11/11/2026; nếu không kịp thì đi đường lui của mục 5. Mục 17.1–17.3 được viết và commit **trước** khi sinh episode nhắm lỗi nào._

### 17.1 `Decision` mở lại C+

**[Đã chốt 8/11/2026, Hiếu]**, qua phiên điều phối, nguyên văn: "Làm tiếp đi từ kết quả và phân tích kia. tôi muốn làm nó nhanh hơn". "Phân tích kia" là đề xuất của phiên điều phối sau mục 16.6:
- C mang khay tới bàn B ở 151/240 lượt nhưng đặt lệch, trung vị khoảng 10 cm;
- lỗi chính là `L-PLACE-POSE` (131/240);
- vì vậy đi C+ thay vì C-max.

**Đây là sửa luật sau khi đã thấy kết quả.** Quy tắc 0 xảy ra trên eval C SimReady (8,3 %, mục 16.6), và câu của quy tắc nói "không chạy C+". [`round-tray-cplus.rule0-override.decision.json`](../../configs/runplans/tray/round-tray-cplus.rule0-override.decision.json) gỡ hệ quả đó cho một vòng:

| Mục | Nội dung |
|---|---|
| Căn cứ | Quy tắc 0 đã xảy ra. Bước "kiểm pipeline ảnh" mà quy tắc 0 yêu cầu đã làm xong, và lỗi đã được sửa: cây eval thiếu manifest SimReady (mục 15), eval C chạy lại trên SimReady có guard (mục 16) |
| Cho chạy | C+ theo [`round-tray-cplus.yaml`](../../configs/runplans/tray/round-tray-cplus.yaml): 160 episode của C cộng 160 episode nhắm lỗi; dùng slot 18 CU đã có trong budget bậc 2 (`round_runs: [C_PLUS]`). Thay cho C-max (i) `rp_366283071c4a`, chưa launch |
| Luật đọc C+ | Quy tắc 1 và 2 của khối `tier2-rules` (mục 9), không đổi; sha256 của khối giữ nguyên |
| Luật 14.1 | Sau T1 0/20, luật 14.1 giữ không train cho tới khi tìm ra lỗi. `Decision` này, khi được ký, gỡ việc giữ đó **cho riêng C+** |
| Ký | `signed_by: Hiếu`, ký 8/11/2026 sau khi #164 merge (`meta.signature_words` trích nguyên văn). Cùng lúc Hiếu ký `Decision` quy tắc 0. Launch Colab chỉ do Hiếu, từ master, sau `runplan check --launch` trên `round-tray-cplus.yaml` |

`Decision` quy tắc 0 (`he-tray-v2.rule0.decision.json`) giữ nguyên, không đổi verdict.

### 17.2 Evidence card: cụm `L-PLACE-POSE`

**Vì sao không dùng công cụ của DA-13.** Phân bổ stage của DA-13 (`flywheel.eval.diagnosis.stage`) cần số đo probe P1/P3 trên model, mà eval C không có. `EvidenceCard` của hợp đồng cần thêm các phép kiểm hệ thống R1–R6 cho từng đại diện, mà trace của lô này không đủ. Vì vậy card dưới đây làm bằng công cụ trong phạm vi DA-34 (`place_error`, `eval_results`) và hai phân tích ad hoc trên outcome. Nó là bảng tóm tắt, không phải `EvidenceCard` theo schema.

| Mục | Giá trị |
|---|---|
| Cụm | `L-PLACE-POSE`, bước hỏng đầu tiên `place` (bước 6), mức 1–2: 131/240 lượt (68 ở mức 1, 63 ở mức 2). Mức 0 có thêm 16/30 |
| Nguồn | Outcome và trace của eval C SimReady (mục 16.6), cây `079160d` |
| Độ lệch cuối (`place_error`) | Trung vị 10,1 cm (mức 1) và 11,2 cm (mức 2); dung sai 5 cm. 78/131 chỉ lệch vị trí, 44 lệch cả vị trí và góc, 8 chỉ lệch góc |
| Vùng đích có hiện trong ảnh không | **Không.** `mjcf.py` không dựng geom nào cho vùng đích; chỉ bộ chấm biết nó |
| Vị trí đặt có đi theo vùng đích không | Gần như không. Hồi quy vị trí cuối (so với vị trí danh định) theo độ dịch của đích, trên lượt thành công và `L-PLACE-POSE` dưới 60 cm: hệ số dốc 0,41 / 0,45 (x / y) ở mức 1 và 0,08 / −0,19 ở mức 2; r ≤ 0,19 |
| Sai số đến từ đâu | Phần lớn là độ tản dọc trục y của bàn B: độ lệch chuẩn 10,0 cm ở mức 0 (đích không dịch), 10,8 cm ở mức 1, 15,3 cm ở mức 2. Theo x là 4,3–5,2 cm. Đích chỉ dịch với độ lệch chuẩn khoảng 2,5 cm. Góc cuối lệch trung bình −4,6° / −6,0°, độ lệch chuẩn khoảng 7° |
| Nếu đặt đúng vị trí danh định | 84 % (mức 1) và 86 % (mức 2) số điều kiện sẽ qua dung sai, dù không thấy vùng đích |
| Tham số cảnh nào gắn với lỗi | Không tham số nào. Trên 151 lượt có khay trên bàn B, so 20 thành công với 131 `L-PLACE-POSE` theo độ dịch của khay và của đích, góc khay và góc đích, khoảng cách hai bàn, vị trí xuất phát, khối lượng linh kiện, ánh sáng: cả 8 tham số đều có p hoán vị > 0,2. Tỉ lệ thành công theo ba khoảng độ dịch của đích là 0,15 / 0,11 / 0,17 |

**Đọc (giả định, chưa kiểm bằng train).**
- Lỗi đặt là độ chính xác của chính policy, chủ yếu theo trục ngang. Nó không tập trung ở vùng cảnh nào.
- Vùng đích không hiện trong ảnh giới hạn mức tối đa, nhưng không phải nguyên nhân chính: đặt đúng chỗ danh định đã đạt khoảng 85 %.
- Theo spec mục 6.9, dạng lỗi này gần "kỹ năng yếu" (`weak_skill`, đề xuất `teleop_correction`) hơn "thiếu vùng phủ" (`coverage_gap`, đề xuất `sim_s1`).
- Sinh S1 nhắm lỗi theo điều kiện, như `targets.py` làm, chọn seed train gần cảnh đã hỏng. Vì lỗi không gắn với cảnh, các seed đó thực chất là thêm dữ liệu S1 rải đều trên vùng mức 1–2.
- Đây là ghi nhận cho Hiếu, không phải luật. C+ vẫn chạy theo `Decision` 17.1. Giới hạn ở quy tắc 2 đã nói hiệu C+ − C gộp "nhiều dữ liệu hơn" và "dữ liệu nhắm lỗi".

### 17.3 Chọn điều kiện nhắm lỗi và luật đọc (viết trước khi sinh)

**[Đề xuất]**, viết và commit trước lần sinh đầu tiên, không sửa sau khi thấy episode.

| Bước | Cách làm |
|---|---|
| Điều kiện | Mọi lượt mức 1–2 của eval C SimReady có nhãn `L-PLACE-POSE` (131 điều kiện dev), mỗi điều kiện `n` = 2. File [`cplus-conditions.jsonl`](../../configs/runplans/tray/cplus-conditions.jsonl), sha256 `64d97c4e…`, xếp theo mức rồi seed |
| Seed | `generate.py --conditions` dùng `flywheel_simple.tray.targets` với tham số mặc định: với mỗi điều kiện, lấy các seed train gần nhất trong cửa sổ 100 000–199 999, đo theo nhóm tham số mà mức đó dịch (mức 1: khay và đích; mức 2: thêm khoảng cách hai bàn, vị trí xuất phát, khối lượng, ánh sáng). Episode luôn sinh trên seed train, không bao giờ trên điều kiện dev (Q-33A). Kế hoạch thử: 262 seed, khoảng cách trung vị 0,28, lớn nhất 0,80 (1,0 = một biên độ dịch). Cửa sổ không chồng với seed 1000–1609 của C |
| Sinh | `rtx3060`, planner `da33-planner-5+cfg.4e2a4505` (trùng C, đã kiểm trên master `079160d`). SimReady chép từ `~/denso-da33`; `generate.py` từ chối ghi khi thiếu SimReady (không truyền `--allow-plain`). Revision và sha của manifest được kiểm trước khi chạy |
| QA | Như release của C (mục 10): QA phát lại, QA của DA-03 (loại `reject` và `quarantine`), rồi bộ lọc chất lượng của C (nghiêng ≤ 10°, xê dịch ≤ 20 mm) |
| Chọn 160 | (1) Đi theo thứ tự trong file, mỗi điều kiện lấy seed qua QA gần nhất. (2) Nếu chưa đủ 160, thêm seed qua QA thứ hai của các điều kiện, ưu tiên điều kiện có độ lệch đặt lớn hơn trong eval C ([`cplus-conditions-place-error.jsonl`](../../configs/runplans/tray/cplus-conditions-place-error.jsonl), sha256 `dd5efd05…`). (3) Nếu vẫn dưới 160, sinh thêm một lô mới với `n` = 1 cho các điều kiện chưa có seed nào qua, rồi áp lại (1)–(2); điều này được ghi lại, không đổi luật |
| Ước lượng hiệu suất | Giả định theo lô `s1-pool-1104`: thành công 89 %, QA của DA-03 99 %, bộ lọc 81 %, tổng khoảng 70 %, tức khoảng 184 episode qua trên 262 |

**Luật đọc C+.** Quy tắc 1 và 2 của khối `tier2-rules`, không đổi:
- trên 240 điều kiện mức 1–2: hiệu C+ − C kèm CI bootstrap theo điều kiện;
- tỉ lệ C+ làm được trên các điều kiện C hỏng;
- số hồi quy, kèm số lượt C hỏng mà C+ làm được;
- mức 0 báo riêng.

Mốc so sánh C là eval C SimReady (mục 16.6). Chỉ số phụ, không phải luật: `place_error` của C+ trên cùng 131 điều kiện, so với C.

### 17.4 Việc còn lại và khoảng trống

- Bản cắt C+ cần 160 episode của C (release `tray_s1_f9433b028c52`) và 160 episode nhắm lỗi (release mới). `round-tray-cplus.yaml` chỉ ghim `targets.seeds` và `set_hash`. `demo_subset.py` của DA-26 và `colab_train` hiện chỉ đọc một release, và `colab_train` từ chối plan khác `rp_a04c14e79dfd`. Bước 3 phải ghép hai release, hoặc dựng một release từ cả hai lô; cách làm ghi ở PR (b).
- Đo eval 2 worker trên cùng server (bước 4, kết quả ở mục 17.7): server Ψ₀ giữ **một** trạng thái RTC cho mọi client (mục 13.1). **Sửa lại (8/11/2026, sau phép đo 17.7): câu "409" dưới đây sai cho đường eval của DA-34.** Câu đó đọc `simple/baselines/psi0.py`, baseline có gửi `session_id`. Eval khay dùng `psi0_decoupled_wbc.py` (SIMPLE `6d10628`): gửi `{"reset": True}` lúc reset (cộng `seed` của `flywheel_simple.tray.run`) và `{}` ở mọi bước khác, không có `session_id`. Khi đó `_claim_rtc_session` lấy host làm danh tính; mọi client trên `rtx3060` đều là `127.0.0.1`, nên hai client là **một** phiên. Chúng dùng chung `previous_action` mà không báo lỗi. Câu gốc của #161–#162 ("dùng chung trạng thái đó mà không báo lỗi") là đúng. Câu sai, giữ để đối chiếu: "Đọc tại nguồn (`serve_psi0_simple.py` của Ψ₀ `cda3fdf`, `_claim_rtc_session`): mỗi client SIMPLE gửi `session_id` riêng; request có `reset` giành phiên RTC, request khác của client không giữ phiên bị trả HTTP 409."

### 17.5 Sinh, QA, release và tập C+ (8/11/2026)

_Chạy trên `rtx3060`, 0 CU. Mọi bước theo luật 17.3 đã commit trước lần sinh đầu tiên (`40dc512a`); không đổi luật nào sau khi thấy episode._

| Bước | Kết quả |
|---|---|
| Sinh, lô `cplus-tgt-1108` | 03:23:33Z–04:19:39Z, 0,93 giờ, 10 worker, cây master `079160d`, SimReady `4763fbf`, planner `da33-planner-5+cfg.4e2a4505` (trùng C). 262 lượt, **229 ghi được** (120 mức 1, 109 mức 2). Hỏng: `L-PLACE-POSE` 9, `L-TRAY-TILT` 7, `L-ONE-HAND` 4, timeout 13. Shard 07–09 chết lúc khởi động vì GPU gần đầy (framebuffer EGL không tạo được; server C giữ 8,5 GB); `generate.py` chạy lại một lần sau các shard khác, không shard nào hỏng |
| QA phát lại (D-24) | 229/229 đạt, lệch khay 0,0 mm, 10 worker, 26 phút |
| Release | **`tray_s1_6c0fd7d37f77`**, `release_hash` `6c0fd7d37f7793f0ce64af79053a4f4778689ec6f5ee9fc6615422a65f18894c`, 229 episode, một planner |
| QA của DA-03 (`qa-1@fb6ddaf9f48c`) cùng phát lại động học DA-17 (`replay-1@cf2515483a8c`) | Chạy từ cây `3e45bb6`, đúng code và ngưỡng của QA cho C (QA trên master đã đổi sau đó vì DA-04). **226 pass, 0 flag, 3 reject**, cả ba `joint_mapping` (seed 125195, 137108, 181063). `stats_json.states` D4 lệch 0,0022, như release của C (lỗi đã biết của script tác giả, mục 10) |
| Bộ lọc chất lượng của C (nghiêng ≤ 10°, xê dịch ≤ 20 mm) | 177 / 226 giữ lại. Trên cả 229: nghiêng trung vị 7,1°, p90 10,0°; xê dịch trung vị 10,9 mm, p90 21,1 mm. [`quality-cplus-tgt-1108.jsonl`](../../configs/runplans/tray/quality-cplus-tgt-1108.jsonl), sha256 `3c1d853c…` |
| Hiệu suất | 177/262 = 67,6 %, gần giả định 70 % của 17.3. Sinh thành công cao hơn giả định (87 % so với 89 % × QA), bộ lọc loại nhiều hơn |
| Chọn 160 ([`cplus_select`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/cplus_select.py)) | Bước (1): 117 điều kiện có seed qua QA, lấy seed gần nhất. Bước (2): thêm 43 seed thứ hai, theo độ lệch đặt giảm dần. Không cần bước (3). 14 điều kiện không có seed nào qua (9 mức 1, 5 mức 2) và không có trong C+. Tập: 82 mức 1, 78 mức 2; khoảng cách tới điều kiện trung vị 0,29, lớn nhất 0,80 |
| Tập `T160` | [`demo_sets-cplus.json`](../../configs/runplans/tray/demo_sets-cplus.json), `set_hash` `1104d00ea3ea…`; danh sách chọn [`cplus-selection.jsonl`](../../configs/runplans/tray/cplus-selection.jsonl) (mỗi dòng: điều kiện, seed, bước, hạng) |
| Đóng băng | [`round-tray-cplus.yaml`](../../configs/runplans/tray/round-tray-cplus.yaml) **`rp_71fee3fcff69`**, lock [`round-tray-cplus.lock.json`](../../configs/runplans/tray/round-tray-cplus.lock.json). Plan ghim conditions, danh sách chọn, release nhắm lỗi, file tập (cùng ghim chất lượng và QA) và tên tập. `runplan check` kiểm cả các ghim đó; `--launch` trên round cần thêm `--targets-release` |
| Bản cắt C+ (dựng thử) | Trên `rtx3060`, từ cây của commit `6a96b1b`: `runplan check … --launch` đạt; `demo_subset` cắt C từ `tray_s1_f9433b028c52` và `T160` từ `tray_s1_6c0fd7d37f77`; [`cplus_cut`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/cplus_cut.py) ghép thành 320 episode, 455 372 frame, 2,7 GB; `colab_train check --branch C_PLUS` đạt. 320 file của phần C (160 parquet, 160 video) giống từng byte bản cắt C đã train. Ở `~/denso-da34-pool/fwdata/cut-cplus-rp_71fee3fcff69`, danh sách sha256 `cut-cplus-rp_71fee3fcff69.sha256` (654 file) |

**Khoảng trống 1 của 17.4 đã xử lý.** C+ là một dataset LeRobot gồm hai phần, theo thứ tự:
- index 0–159: bản cắt C, chép nguyên từng byte;
- index 160–319: tập nhắm lỗi `T160`.

Stats là của chính 320 episode (`own_train_set`), tính lại bằng `flywheel.data.inject.stats` như `demo_subset`. Riêng stats ảnh được giữ theo từng episode của phần gốc. Marker ghi đủ hai phần.

`colab_train --branch C_PLUS` chỉ chạy khi:
- round đã đóng băng đúng `rp_71fee3fcff69`;
- phần 1 của bản cắt đúng là tập C ở index 0–159;
- phần 2 đúng là `T160` từ index 160.

Parent, recipe và seed train lấy của nhánh C.

**Đọc (giả định, chưa kiểm bằng train).** Như 17.2 đã ghi: lỗi đặt không gắn với vùng cảnh nào, nên 160 episode này gần với "thêm 160 episode S1 rải trên mức 1–2" hơn là dữ liệu sửa đúng lỗi. Khác với C về phân bố: C chỉ có mức 1 (seed 1000–1609), còn `T160` có cả mức 2. Vì vậy C+ − C gộp ba thứ: nhiều dữ liệu hơn, dữ liệu nhắm lỗi, và dữ liệu mức 2 (giới hạn đã nói ở quy tắc 2).

### 17.6 Runbook: fine-tune C+ trên Colab (nhiệm vụ 5.4, soạn 8/11/2026, chưa chạy)

Một phiên Colab L4, job `da34-t5-ft-cplus-s0`, cap 18 CU (slot `round_runs: [C_PLUS]` của budget bậc 2). Giống mục 12, chỉ khác: plan round, bản cắt hai phần và `--branch C_PLUS`. **Không chạy gì trước khi Hiếu launch.**

**Ba điều bắt buộc** (thiếu một điều thì không launch, không eval):

| # | Điều | Ở đâu bên dưới |
|---|---|---|
| 1 | `runplan check configs/runplans/tray/round-tray-cplus.yaml --release <C> --targets-release <T> --launch` chạy và **qua** trên `rtx3060` trước khi mở phiên Colab. Lệnh trả mã khác 0 thì dừng ở đó | Khối "rtx3060: kiểm lúc khởi chạy" |
| 2 | Watcher `cu_watch.py session … --cap 18 --floor 14`: phiên bị dừng ở 18 CU kể cả khi chưa đủ 40 000 bước | Khối "Laptop" |
| 3 | Checkpoint về `rtx3060` theo đúng một đường: laptop `fwdata/tray/runs/da34-t5-ft-cplus-s0/` → `rtx3060:denso-da34-pool/fwdata/tray/runs/da34-t5-ft-cplus-s0/`, danh sách sha256 lập trên laptop và kiểm lại trên `rtx3060`. Lệch một file thì không eval | Khối "Chuyển checkpoint sang rtx3060" |

**Điều kiện trước khi chạy.**

1. PR (a) (#162: `Decision` mở lại C+ và luật chọn) và PR (b) (release, round đóng băng, runbook này) đã merge. `Decision` [`round-tray-cplus.rule0-override.decision.json`](../../configs/runplans/tray/round-tray-cplus.rule0-override.decision.json) đã ký. Mọi lệnh chạy từ bản checkout `master`.
2. `colab sessions` trống, một lô mỗi tài khoản. Số dư ít nhất 32 CU (sàn 14 cộng cap 18). Laptop thức suốt lần chạy.
3. Hiếu cho chạy.

**rtx3060: kiểm lúc khởi chạy và dựng bản cắt** (0 CU, khoảng 1 phút; `D` là bản `master` mới, `git archive` vào `~/denso-da34-master-<sha>` kèm `TREE_SHA`). Bản cắt dựng lại từ master vào thư mục mới, vì `demo_subset` và `cplus_cut` không ghi đè; bản dựng thử ở 17.5 chỉ để đối chiếu sha256:

```bash
cd $D && export PYTHONPATH=$(ls -d $PWD/packages/*/src | paste -sd:)
PY=~/denso-da34-pool/.venv/bin/python
REL_C=~/denso-da34-pool/fwdata/releases/tray_s1_f9433b028c52
REL_T=~/denso-da34-pool/fwdata/releases/tray_s1_6c0fd7d37f77
CUT=~/denso-da34-pool/fwdata/cut-cplus-rp_71fee3fcff69-$(cut -c1-7 TREE_SHA)   # D is a git archive with TREE_SHA, as 16.2
E=G1WholebodyTrayTransferTeleop-v0
$PY -m flywheel_psi0.tray.runplan check configs/runplans/tray/round-tray-cplus.yaml \
    --release $REL_C --targets-release $REL_T --launch \
  || { echo "runplan check --launch failed: do not launch"; exit 1; }
$PY scripts/he/demo_subset.py --src $REL_C --sets configs/runplans/tray/demo_sets-v2.json --set C --out $CUT/parts/C/$E
$PY scripts/he/demo_subset.py --src $REL_T --sets configs/runplans/tray/demo_sets-cplus.json --set T160 --out $CUT/parts/T160/$E
$PY -m flywheel_psi0.tray.cplus_cut --part $CUT/parts/C/$E --part $CUT/parts/T160/$E --demo-set C_PLUS --out $CUT/sets/C_PLUS/$E
$PY -m flywheel_psi0.tray.colab_train check --branch C_PLUS --work $CUT   # "rp_71fee3fcff69 da34-t5-ft-cplus-s0: cut and plan hold"
```

**Laptop: kéo bản cắt, rồi guard và watcher** (thư mục gốc là bản checkout `master`). Như mục 12, với `S` và đường dẫn mới:

```bash
CUT=denso-da34-pool/fwdata/cut-cplus-rp_71fee3fcff69-<sha7>   # the folder the rtx3060 step wrote
rsync -a --delete --partial-dir=.rsync-partial rtx3060:$CUT/sets/ fwdata/tray/cut-cplus/sets/   # sets/ only, not parts/
export PATH=~/project/wm-wam-review/.venv-colab-cli/bin:$PATH
colab sessions; colab usage
S=da34-t5-ft-cplus-s0
R=fwdata/colab/batch-$(date +%Y%m%d-%H%M%S); mkdir -p fwdata/colab && mkdir $R && git rev-parse HEAD > $R/master.sha
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py guard --registry "$0" --floor 14 --log "$0/guard.jsonl"; echo "exit $?"' $R < /dev/null > $R/guard.out 2>&1 &
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name "$1" --gpu L4 --cap 18 --floor 14 --persist "python3 scripts/he/he1_fetch.py once --session $1 --registry $0 --dest fwdata/tray/runs --remote-work /content/da34" --log "$0/$1.jsonl"; echo "exit $?"' $R $S < /dev/null > $R/$S.out 2>&1 &
```

Hàm `ready` và `vm` như ở mục 12.

**Phiên C+.** Mỗi bước chỉ chạy khi bước trước đã xong.

```bash
ready $S && python3 scripts/he/he1_fetch.py probe --session $S --registry $R --dest fwdata/tray/runs --remote-work /content/da34 \
  || { colab stop -s $S; echo "$S: not ready or proxy too slow, session stopped"; }
git archive --format=tar.gz HEAD | vm $S 'mkdir -p /content/da34/fw && tar -xz -C /content/da34/fw'
rsync -a --partial-dir=.rsync-partial -e "ssh -o ProxyCommand='colab ssh --proxy-mode -s $S' -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null" \
  fwdata/tray/cut-cplus/sets/ root@colab:/content/da34/sets/
VMPP=fw/packages/flywheel-psi0/src:fw/packages/flywheel-contracts/src
vm $S "cd /content/da34 && PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_train check --branch C_PLUS" \
  || { colab stop -s $S; echo "$S: cut or round does not hold on the VM, session stopped"; }
vm $S "cd /content/da34; nohup setsid bash -c 'PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_train setup --branch C_PLUS; echo setup exit \$?' > setup.log 2>&1 < /dev/null &"
vm $S 'tail -2 /content/da34/setup.log'   # chờ "setup exit 0"
vm $S "cd /content/da34; nohup setsid bash -c 'PYTHONPATH=$VMPP Psi0/.venv-psi/bin/python -m flywheel_psi0.tray.colab_train train --branch C_PLUS; echo train exit \$?' > train.log 2>&1 < /dev/null &"
nohup setsid bash -c 'python3 scripts/he/he1_fetch.py follow --session "$1" --registry "$0" --dest fwdata/tray/runs --remote-work /content/da34 --every 600 --stop-when-done; echo "exit $?"' $R $S < /dev/null > $R/$S.fetch.log 2>&1 &
```

**Trong và sau lúc chạy.** Như mục 12: quy tắc dừng sớm, `ALERT` và mã thoát của `he1_fetch`; watcher dừng ở cap 18 CU. Khi xong, ghi dòng `measured` cho `job_da34_ft_C_PLUS` (CU theo `colab usage`, số bước, giờ), trỏ về dòng ước lượng; dòng ước lượng đã ghi trước khi launch.

**Chuyển checkpoint sang rtx3060 (điều 3).** Từ laptop, như mục 12, cộng một bước: chép cả danh sách sha256 sang `rtx3060`, vì `serve-cplus.sh` kiểm lại nó trước khi phục vụ. Chỉ chuyển khi `fetched.json` báo `final`; nếu không, xử lý như C ở mục 13.1 (chuyển khi `result.json` ok ở bước 40 000 và sha256 khớp, ghi lệch vào mục kết quả).

```bash
J=fwdata/tray/runs/da34-t5-ft-cplus-s0
DST=denso-da34-pool/fwdata/tray/runs/da34-t5-ft-cplus-s0
python3 -c 'import json, sys; sys.exit(0 if json.load(open(sys.argv[1]))["final"] else 1)' $J/fetched.json \
  || { echo "not final: no hand-off"; exit 1; }
(cd $J && find . -type f -not -path '*/.*' -print0 | sort -z | xargs -0 sha256sum) > $J.sha256
rsync -a --partial-dir=.rsync-partial --exclude='.*' $J/ rtx3060:$DST/
rsync -a $J.sha256 rtx3060:$DST.sha256
ssh rtx3060 "cd $DST && sha256sum -c --quiet" < $J.sha256 && echo "hand-off OK" || echo "hand-off FAILED: do not eval"
```

**Eval C+ (nhiệm vụ 5.6) trên rtx3060: đã chuẩn bị, chưa chạy.** Chỉ chạy khi hand-off OK và Hiếu bảo chạy. Giống hệt eval C SimReady (mục 16.2) để so cặp với mốc 16.6:

| Mục | Giá trị |
|---|---|
| Tập, điều kiện | `rp_a04c14e79dfd-2e57f60`, 270 điều kiện, `conditions.sha256` `b9c38b37…` |
| Cây client | `~/denso-da34-master-079160d` có SimReady, như eval C SimReady; `simple-guard.sh` trước mỗi lô |
| Server | C+ `ckpt_40000`, `Ta` 24, `--rtc`, `127.0.0.1:22185`; cùng cây `master` `7b585a7` và cùng `serve_psi0.sh serve` như server C |
| Lô | 1 worker (mục 17.7), 27 lô 10 episode, tối đa 3 lần, scope `MemoryMax=8G`, `MemorySwapMax=0` |
| Output | Thư mục mới `~/denso-da34-pool/fwdata/tray/eval/eval-cplus-simready-rp_a04c14e79dfd` |
| Thời gian | Khoảng 17,2 giờ như eval C SimReady (giả định: cùng tốc độ mỗi episode) |

Hai script vận hành nằm trên máy, trong `~/denso-da34-t8/` (không trong repo, không sửa `flywheel_simple`):
- `serve-cplus.sh <CUT>` từ chối nếu một trong các điều sau không đúng:
  - danh sách sha256 của hand-off kiểm qua;
  - dưới `psi0/finetune/` có đúng một run của `da34-t5-ft-cplus-s0`, có `ckpt_40000`;
  - `action_min/max`, `state_min/max` trong `run_config.json` bằng min/max của `meta/stats_psi0.json` của bản cắt C+ (`stats-check.py`; server chuẩn hóa bằng các giá trị này, mục 15).

  Qua cả ba thì script hard link checkpoint vào `psi0/hf/psi0/simple-checkpoints/<RUN>` như của C. Sau đó nó dừng container `fw-psi0` đang chạy (server C) và khởi động server C+.
- `launch-eval-cplus.sh` từ chối nếu container không mang `da34-t5-ft-cplus-s0`, `--ckpt-step 40000`, `--action-exec-horizon 24`, `--rtc`, nếu `/health` không ok, hoặc nếu đã có client khác trên 22185. Chạy lại file này là chạy tiếp.

Đã thử ngày 8/11 (không chạy episode nào, server C không bị động tới):
- `stats-check.py` cho run C trên stats của tập C ra lệch 0; trên stats của C+ ra lệch 0,133 và từ chối.
- `serve-cplus.sh` từ chối vì chưa có hand-off.
- `launch-eval-cplus.sh` từ chối vì server đang là C.

```bash
# on rtx3060, after "hand-off OK" and Hiếu's go; CUT = the folder the launch step above wrote
~/denso-da34-t8/serve-cplus.sh $CUT
systemd-run --user --scope --unit da34-eval-cplus -p MemoryMax=8G -p MemorySwapMax=0 \
  nohup setsid ~/denso-da34-t8/launch-eval-cplus.sh > ~/denso-da34-t8/eval-cplus.out 2>&1 < /dev/null &
```

Đọc bằng `eval_results --baseline` trỏ vào lô eval C SimReady, theo quy tắc 1–2; `place_error` báo cạnh, không phải luật. Sau eval C+, server để ở C+; muốn trả về C thì chạy `~/denso-da34-t4/serve.sh c 24 rtc`.

Ước lượng (dòng `job_da34_ft_C_PLUS` trong sổ, ghi trước khi launch): khoảng 16,0 CU, như C đo được 15,99 CU (8,27 giờ L4, 0,724 s/bước). Giả định, chưa đo:
- thời gian mỗi bước không phụ thuộc số episode, vì 40 000 bước, batch và recipe như C; chưa đo ở 320 episode;
- bản cắt C+ 2,7 GB tải lên khoảng 1,5 phút ở 33 MB/s, tốc độ probe của lần chạy C (C: 1,3 GB trong 52 s).

### 17.7 Eval 2 worker trên một server: không dùng (nhiệm vụ 5.5, 8/11/2026)

**[Đề xuất] Kết luận: không dùng 2 worker trên một server Ψ₀.** Eval C+ chạy 1 worker như eval C. Lý do là tính đúng của kết quả, không phải tốc độ. Phiên điều phối yêu cầu ghi kết luận này và cho dừng phép đo ngày 8/11; Hiếu duyệt qua PR chứa mục này.

**Vì sao, đọc tại nguồn.** Client của eval khay là `psi0_decoupled_wbc.py` (SIMPLE `6d10628`), không gửi `session_id`. Vì vậy `_claim_rtc_session` của `serve_psi0_simple.py` (Ψ₀ `cda3fdf`) lấy host làm danh tính, và hai client trên `rtx3060` (`127.0.0.1`) là một phiên. Mục 17.4 có câu sửa lại. Hệ quả:

| # | Chuyện gì xảy ra | Vì sao làm hỏng kết quả |
|---|---|---|
| 1 | Một `previous_action` chung | Chunk mới của episode này lấy phần đầu action của episode kia làm tiền tố RTC |
| 2 | `reset` của client này xóa trạng thái RTC của client kia giữa episode | Episode kia mất tiền tố giữa chừng, dù server không báo lỗi |
| 3 | `serve_psi0_seeded` gieo RNG toàn cục của torch lúc `reset`; lượt `/act` của client kia rút nhiễu xen vào | Nhiễu của mỗi episode phụ thuộc thời điểm của client kia; gieo theo episode (mục 8) mất tác dụng |

Kết quả 2 worker vì thế không còn là cùng một thí nghiệm với eval C 1 worker, nên không so cặp được với mốc 16.6.

**Phép đo, dừng giữa chừng.**

| Mục | Giá trị |
|---|---|
| Cách chạy | Hai tiến trình `eval_batch` (`eval_driver` chỉ cho 1 worker mỗi tiến trình), proxy riêng trên 22196 và 22197. Cùng server C (`Ta` 24, `--rtc`). Mỗi bên 5 điều kiện mức 1 của tập eval C (seed 1000100–1000104 và 1000105–1000109). Guard SimReady bật, 1 lần thử, scope `MemoryMax=12G` |
| Thời gian | Bắt đầu 04:54:52Z; dừng 05:01:47Z (`systemctl --user stop da34-w2-probe.scope`), khoảng 7 phút |
| Episode xong | Mỗi bên 1 episode. Episode thứ hai (1000101, 1000106) bị cắt ở khoảng 166–170 s |
| Server thấy gì | `history` chỉ là `{}` và `{"reset": True, "seed": N}`, không có `session_id`; log không có 409 hay lỗi. Đúng như đọc nguồn |

So với cùng seed trong eval C SimReady (1 worker, lô `l1-000`):

| Seed | 2 worker | 1 worker |
|---|---|---|
| 1000100 | `L-TIMEOUT`, 218,7 s | `L-TIMEOUT`, 196,3 s |
| 1000105 | `L-TIMEOUT`, 218,2 s | `L-PLACE-POSE`, 280,4 s |

- Seed 1000105 cho kết quả khác. Chỉ một episode, nên không tách được do tiền tố chung hay do nhiễu đổi; cả hai đều do chạy chung server.
- Độ trễ `/act` trung bình 0,46 s ở 2 client; lô `l1-000` của eval C 1 client là 0,52 s, tải máy lúc đó khác.
- Hai episode xong trong khoảng 219 s, nên thông lượng có thể gần gấp đôi. Đây là ước lượng từ 2 episode, không phải số đo, và không đổi kết luận.

**Đường khác, chưa làm.**
- `serve_psi0_simple_multi.py` giữ trạng thái RTC riêng cho từng client, nhưng gom batch, nên mất gieo nhiễu theo episode.
- Server thứ hai không vừa GPU 12 GB (mục 13.1).

Muốn eval nhanh hơn thì cần một trong hai đường trên, kèm luật đọc mới, và là quyết định của Hiếu.

**Trả server.** Server C chưa bao giờ bị cấu hình lại trong phép đo. Container `fw-psi0-psi0-run-41b48a6a5890` vẫn chạy `ckpt_40000` của C với `--action-exec-horizon 24 --rtc` trên 22185, khỏe lúc 05:02Z, không còn client nào. Client kế tiếp gửi `reset`, lệnh này xóa `previous_action` còn lại của phép đo.

### 17.8 Fine-tune C+: lần 1 dừng giữa chừng, lần 2 chạy lại từ đầu (8–9/11/2026)

| Lần | Diễn biến |
|---|---|
| 1 | Phiên `da34-t5-ft-cplus-s0` chạy từ master `2363f70`, bản cắt dựng lại từ master trùng từng byte bản dựng thử ở 17.5 (654 file). L4 bound 11:30:13Z, train từ 11:38Z, 0,73 s/bước (như C). Lúc 15:21:40Z laptop chạy watcher bị restart từ hộp thoại tắt máy của GNOME. Watcher nhận SIGTERM và trả VM lúc 15:21:47Z, nên không có CU nào chạy khi không có người canh. Train tới khoảng bước 18 000/40 000. Chỉ `ckpt_10000` về tới laptop; checkpoint này không có trạng thái optimizer và `colab_train` không có chế độ chạy tiếp, nên không dùng. Đã tiêu 7,49 CU |
| 2 | Hiếu 9/11/2026: "Chạy lại, cap 17". Chạy lại từ bước 0 trên cùng bản cắt và plan `rp_71fee3fcff69`. L4 bound 18:22:18Z, `colab_train check` trên VM qua. Cap watcher 17 CU để số dư (30,99 CU) không xuống dưới sàn 14. Ước lượng 16,0 CU, 8,3 giờ (giả định theo C). **Kết quả:** 40 000 bước, 0,729 s/bước, `result.json` ok; phiên dừng lúc 02:44:29Z ngày 9/11 (8,37 giờ), tiêu 16,11 CU theo `colab usage`. Checkpoint về `rtx3060` (432 file, 24 GB), sha256 khớp; bounds trong `run_config.json` bằng stats của bản cắt C+ (lệch 0,0) |

**Ngân sách.** C+ tổng 7,49 + 16,11 = 23,6 CU (số đo), vượt slot 18 CU của `round_runs` trong `rp_a04c14e79dfd`. Cộng với C (15,99 CU) là 39,6 CU, vượt trần 36 CU. Hiếu duyệt bằng lời trích ở trên; số đo ở ledger `job_da34_ft_C_PLUS`.

**Đọc kết quả.** Lần 2 dùng đúng recipe, seed, parent và bản cắt của lần 1, nên phép so C+ với C không đổi. Lần 1 không sinh checkpoint nào được dùng.

**Bài học vận hành.** Khóa của watcher (`systemd-inhibit`) chỉ chặn ngủ, nghỉ và gập nắp; nó không chặn restart bấm tay. Trong lúc chạy job Colab, laptop không được restart; có thông báo cập nhật thì hoãn.

## 18. Nhánh B: stage 1 trên egocentric của đội (nhiệm vụ 4, AC 5; soạn 9/11/2026, chưa chạy)

_**Đã thay thế, không chạy** (quyết định của Hiếu 11/11/2026, qua phiên điều phối)._ Cảnh `4763fbfaa4f8e97658e68b57d01b4c86659e08b5+zone1` của DA-33 (PR #182) vẽ vùng đích trên bàn B và sửa `mjcf.py`, `simple_task.py` mà plan B và plan C-max ghim. Câu hỏi egocentric chuyển sang cặp `B_ALL`, `C_ALL` trên cut ALL tái sinh (`he-tray-pair60k.yaml`). Hai plan `he-tray-b.yaml` (`rp_128aec169e12`) và `he-tray-cmax.yaml` (`rp_366283071c4a`) có `superseded_by`; trường này nằm ngoài id, nên id và lịch sử giữ nguyên, còn `runplan check` thoát 1. B và C-max chưa từng đóng băng hay chạy.

_**[Đã chốt 9/11/2026, Hiếu]** "Chốt 4 mặc định" (qua phiên điều phối): chuẩn bị nhánh B để so "egocentric + demo robot" với "chỉ demo robot". Mục này viết và commit **trước** mọi lượt train hay eval của B. Story DA-34 nhiệm vụ con 4.1–4.8. Stage 1 là việc của [DA-30](../product/stories/DA-30-stage1-egocentric.md) nhiệm vụ 2; mục này dùng checkpoint của nó, không chạy nó._

### 18.1 Thiết lập

B là nhánh C của RunPlan bản 2 `rp_a04c14e79dfd` với **đúng một thay đổi**: VLM cha.

| Mục | C (mốc) | B |
|---|---|---|
| VLM cha | `pre.fast.1by1.2601091803.ckpt.ego200k.he30k` (psi-model `cb1480f`) | VLM của C fine-tune thêm ở stage 1 trên 153 clip egocentric của đội (DA-30, khoảng 300 bước, trần 4 CU) |
| Action header | `postpre.1by1.pad36.2601131206.ckpt.he30k` | Giống C |
| Demo robot (stage 3) | Tập `C`, 160 episode, `a202cc02…`, release `tray_s1_f9433b028c52` | Giống C, cùng bản cắt |
| Recipe, bước, seed | `psi0-stage3.yaml`, 40 000 bước, batch 16, seed train 0, ghi đè `train.validation_steps: 2000` | Giống C |
| Ngân sách stage 3 | Cap 18 CU một lần (đo: 15,99 CU) | Cap 18 CU, sàn số dư 14 CU; ngân sách riêng của B, không nằm trong trần 36 CU của bậc 2 |
| Eval | 270 điều kiện của plan, cảnh SimReady (mục 16) | Giống eval C SimReady |

- **Dữ liệu stage 1.** 153 clip egocentric đội tự quay. Mỗi clip là trọn một lần làm task, khuôn mặt đã làm mờ, `data_class` `public` (PR #170). Pose tay ước lượng từ một camera, nội tham số camera là giả định. Mỗi clip dài khoảng 2,6 s; người bê một hộp đỏ, không phải khay của sim.
- **Ghép VLM với action header.** Ψ₀ tại `cda3fdf` nạp VLM (`model_name_or_path`) và action header (`pretrained_action_header_path`) riêng nhau (`src/psi/trainers/finetune.py` dòng 324–356). Vì vậy ghép VLM sau stage 1 với action header gốc không cần sửa Ψ₀ (design mục 6.2, stage 2).
- **Checkpoint stage 3 mang VLM của B.** Server eval nạp cả VLM lẫn action header từ `model.safetensors` của checkpoint stage 3 (`Psi0Model.from_pretrained`, `src/psi/models/psi0.py` dòng 1733–1775). Vì vậy eval B không cần thêm bước nạp VLM nào.
- **Không có A.** Bậc 2 bỏ A (mục 9), nên quy tắc HE-T của mục 4 không đọc được. B so với C chỉ trả lời: thêm egocentric ở stage 1, với cùng 160 demo robot, có giúp không. Câu "egocentric **thay** được một phần demo robot" chưa đo.

### 18.2 Luật đọc B (viết trước khi chạy)

**[Đề xuất]**, chờ Hiếu duyệt; riêng phần "Hai giai đoạn" **[Đã chốt 10/11/2026, Hiếu]** (mục 18.9). Khối giữa hai dấu `branch-b-rules` (chú thích HTML) được ghim bằng sha256 ở `interpretation.rules_sha256` của [`he-tray-b.yaml`](../../configs/runplans/tray/he-tray-b.yaml). Sửa một ký tự trong khối thì `runplan check` báo lỗi; nhãn này nằm ngoài khối. Luật là design mục 6.4 bỏ vế so với A.

<!-- branch-b-rules -->

**Phép đo.** Chỉ số chính là hiệu ghép cặp B − C trên các điều kiện mức 1–2 đã chạy: 60 ở giai đoạn 1, 240 (120 mỗi mức) nếu đi tiếp giai đoạn 2. Mốc C là eval C SimReady (mục 16.6): 7/60 trên 60 điều kiện của giai đoạn 1, 20/240 trên cả mức 1–2. Với mỗi điều kiện i: d_i = s_B,i − s_C,i. Hiệu là trung bình của d_i. CI 95 % bootstrap theo điều kiện: lấy mẫu lại d_i trong từng mức, 10 000 lần, hạt giống 20261103, khoảng phân vị (`stats` của plan, như mục 2 và 9). Phép kiểm phụ: McNemar chính xác hai phía trên các cặp bất đồng. b là số cặp B làm được mà C hỏng, c là số cặp ngược lại.

**Hai giai đoạn.**
- Giai đoạn 1 là 6 lô đầu theo thứ tự chạy của `eval_batch`: `l1-000`, `l2-000`, `l1-010`, `l2-010`, `l1-020`, `l2-020`. Đó là 60 điều kiện: seed 1000100–1000129 ở mức 1 và ở mức 2. Ghép cặp với đúng 60 điều kiện đó của eval C SimReady.
- Sau giai đoạn 1 đọc một trong bốn kết quả (`eval_results --stage1`, trường `stage1.outcome`):

| Kết quả | Điều kiện, trên 60 điều kiện | Làm gì |
|---|---|---|
| E1 | McNemar p < 0,001, b > c, cận dưới CI 95 % của (B − C) > 0 | Dừng. Đọc luật 1 |
| E3 | McNemar p < 0,001, b < c, cận trên CI 95 % của (B − C) < 0 | Dừng. Đọc luật 3 |
| F | Không phải E1 hay E3, và b ≤ c | Dừng vì không hứa hẹn. Đọc như luật 2: "không thấy B hơn C trên 60 điều kiện". Không đọc luật 3, không đọc "egocentric không giúp" |
| Đi tiếp | Còn lại: b > c | Chạy 18 lô còn lại của mức 1–2, rồi mức 0. Đọc luật 1–6 trên đủ 240 điều kiện. 60 lượt của giai đoạn 1 tính vào 240, không chạy lại |

- Mức 0 (30 lượt lặp) chỉ chạy khi đi tiếp giai đoạn 2. Dừng ở giai đoạn 1 thì không chạy mức 0, và `Decision` ghi rõ điều đó.
- Không có điểm đọc nào khác. Giữa giai đoạn 2 không đọc và không dừng vì kết quả.

**Trước khi đọc.** Lô B có đủ rollout của giai đoạn đang đọc: 60 rollout của 6 lô giai đoạn 1, hoặc 270 nếu đã đi tiếp giai đoạn 2. Cùng tập điều kiện với eval C SimReady (`conditions.sha256` `b9c38b37…`), cảnh SimReady có guard từng lô (mục 16.2), server `Ta` 24 + RTC, 1 worker. Thiếu một điều thì không đọc E1, E3, F và quy tắc 1–3: ghi `Decision` và báo. Lượt hỏng do hạ tầng chạy lại như mục 2; mỗi điều kiện lấy lần xong sớm nhất.

Luật 1–3 đọc trên 240 điều kiện khi đã đi tiếp giai đoạn 2, và trên 60 điều kiện khi dừng ở E1 hay E3. Luật 4–6 báo trên đúng các điều kiện đã chạy.

| # | Điều kiện | Đọc là |
|---|---|---|
| 1 | Cận dưới CI 95 % của (B − C) > 0 | **B đạt.** Với cùng 160 demo robot, stage 1 trên egocentric của đội giúp Ψ₀ trên task khay (sơ bộ, trên dev) |
| 2 | CI 95 % của (B − C) chứa 0 | Không thấy tác động của egocentric ở mức này. Không đọc thành "egocentric không giúp" |
| 3 | Cận trên CI 95 % của (B − C) < 0 | B kém hơn C. Đây là kết quả âm hợp lệ, phải báo |
| 4 | McNemar | Báo p cạnh quy tắc 1–3; không đổi quyết định của 1–3. Nếu McNemar (p < 0,05 hay không) và CI cho hai kết luận khác nhau, báo cả hai và ghi rõ là khác nhau |
| 5 | B so với C+ | Chỉ mô tả: hiệu ghép cặp và CI như trên, không có luật. B và C+ khác nhau cả VLM lẫn số demo robot (160 so với 320) |
| 6 | Chỉ số phụ, báo cạnh | Tỉ lệ qua từng bước trong 7 bước của bộ chấm theo mức, và ghép cặp B với C theo từng bước; tỉ lệ `L-PLACE-POSE` (C: 33/60 ở giai đoạn 1, 131/240 trên cả mức 1–2); `place_error` (mục 16.4); mức 0 báo riêng nếu đã chạy (30 lượt lặp, C: 5/30) |

**Giới hạn phải ghi cạnh mọi số B − C.**
- B tốn thêm compute ở stage 1 (sổ chi phí của DA-30).
- Pose tay của 153 clip là pose giả, ước lượng từ một camera với nội tham số giả định.
- 153 clip, mỗi clip khoảng 2,6 s, người bê một hộp đỏ, không phải khay của sim.
- Cùng một đội dựng task, sinh demo robot và quay egocentric.
- Kết quả chỉ trong sim, renderer MuJoCo.
- Sơ bộ, trên dev: 1 seed train mỗi nhánh, 1 rollout mỗi điều kiện. Rollout trên EGL không lặp lại được (mục 13.2), nên một cặp là hai rollout, không phải hai phép đo lặp của một rollout.
- Không có A: không đọc HE-T (mục 4).
- Dừng ở giai đoạn 1 là đọc trên 60 điều kiện. F không phải bằng chứng B không giúp: một cải thiện vừa vẫn có thể dừng ở F (mục 18.9).

Luật này không đổi sau khi thấy kết quả. Muốn đổi thì ghi `Decision` mới và báo theo cả luật cũ lẫn luật mới.

<!-- /branch-b-rules -->

### 18.3 RunPlan B (nhiệm vụ con 4.2)

[`he-tray-b.yaml`](../../configs/runplans/tray/he-tray-b.yaml), `status: draft`, id nháp `rp_128aec169e12` (từ 10/11, khi `rules_sha256` đổi theo mục 18.9). Id này đổi khi điền ghim của checkpoint stage 1 (nhiệm vụ con 4.7), vì ghim nằm trong id.

| Trường | Giá trị |
|---|---|
| `variant_of` | `he-tray-v2.yaml`, `rp_a04c14e79dfd`, nhánh `C`. `runplan check` so mọi trường khác với bản 2 và báo lỗi khi lệch. Chỉ được khác: `name`, `status`, `parents`, `branches`, `budget`, `interpretation`, `variant_of`, `supersedes`, `superseded_by`. Bản 2 phải đã đóng băng và đúng id đó |
| `parents` | Cặp của C giữ nguyên, thêm đúng một cha stage 1 `psi0-b-ego-stage1`: `vlm_stage1.from_parent` là cha của C; action header trùng của C; `story` DA-30, sổ `docs/g0/ledger/DA-30.csv` |
| Ghim stage 1 | `job_id`, `drive_dir` (thư mục dưới `MyDrive`), `weights_sha256` (`model.safetensors`), `manifest_sha256` (cả thư mục, `colab_train manifest`). Để `null` tới khi DA-30 có checkpoint. Có sẵn `parent_header_sha256` `53d000d9…`: sha256 chuẩn hóa của header safetensors của VLM C (tên, dtype, shape của từng tensor). Header đọc bằng range request từ psi-model `cb1480f` ngày 9/11: 625 tensor BF16, không có `lm_head`, `embed_tokens` 153 792 × 2 048 |
| `branches` | `B`: tập `C`, cha `psi0-b-ego-stage1` |
| `budget` | Trần 18 CU, cap 18 CU một lần, `runs` đúng `[B]` (`check` kiểm), watcher `--cap 18 --floor 14`. Ngân sách riêng của B (Hiếu 9/11), ngoài trần 36 CU của bậc 2. Stage 1 tính ở DA-30 |
| `interpretation` | `docs/he/tray.md`, `rules_marker: branch-b-rules`, `rules_sha256` của khối mục 18.2 |

**Chặn khi chưa đủ ghim.** `runplan check` (cũng là lệnh CI chạy) qua và ghi "draft, 4 stage 1 pins pending". `runplan freeze` từ chối khi còn `status: draft` hoặc còn một ghim `null`, kể cả khi đã bỏ `draft`. `runplan check --release … --launch` từ chối với một dòng `DRAFT` và một dòng `PENDING` cho mỗi ghim thiếu. Test: `test_b_neither_launches_nor_freezes_until_stage1_is_pinned`, `test_b_refuses_any_second_change`, `test_b_freezes_once_pinned_and_released_from_draft`.

### 18.4 Runbook: fine-tune stage 3 B trên Colab (nhiệm vụ con 4.3, soạn 9/11/2026, chưa chạy)

Một phiên Colab L4, job `da34-t4-ft-b-s0`, cap 18 CU, sàn số dư 14 CU. Giống mục 17.6, chỉ khác bốn điều: plan `he-tray-b.yaml`, `--branch B`, bản cắt là bản cắt C đặt ở `sets/B/`, và VLM lấy từ Drive. **Không chạy gì trước khi Hiếu launch.**

**Mã phía VM** ([`colab_train`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/colab_train.py) `--branch B`):
- Chỉ chạy plan B đã đóng băng với id bằng `B_FROZEN`. Hiện `B_FROZEN` là `None`, nên `check`, `setup` và `train` của B đều từ chối, kèm lý do: plan còn nháp, 4 ghim chưa điền, chưa duyệt id.
- `setup`: kiểm bản cắt như C, rồi kiểm có `model.safetensors` dưới `/content/drive/MyDrive/<drive_dir>`, cả hai **trước** khi cài môi trường. Sau đó tải từ psi-model (revision của plan) action header của C và thư mục VLM của C **không kèm trọng số**, chép thư mục stage 1 từ Drive vào `Psi0/cache/checkpoints/stage1/<tên thư mục>`, rồi kiểm:
  - sha256 action header bằng ghim của C;
  - sha256 `model.safetensors` bằng `weights_sha256`;
  - header safetensors của `model.safetensors` (tên, dtype, shape) có sha256 bằng `parent_header_sha256`, tức đúng các tensor của VLM C. Lý do: `Qwen3VLForConditionalGeneration.from_pretrained` (`finetune.py` dòng 272) chỉ cảnh báo khi khóa không khớp, ví dụ tiền tố `vlm_model.` hay file chia mảnh, và stage 3 sẽ train khoảng 16 CU trên trọng số khởi tạo ngẫu nhiên. Khi lệch, lỗi in số tensor, dtype, tiền tố, `lm_head` và shape của `embed_tokens`;
  - sha256 manifest cả thư mục bằng `manifest_sha256`;
  - mọi file khác (config, tokenizer, processor) trùng từng byte file cùng tên của VLM C; không thừa, không thiếu file nào. Stage 1 chỉ được đổi trọng số.

  Lệch một điều thì dừng, không train.
- `train`: kiểm lại bản cắt và thư mục stage 1, rồi chạy Psi0Trainer với recipe của plan. Cha stage 1 được thêm vào recipe trong bộ nhớ: `model_name_or_path` trỏ vào thư mục stage 1, action header của C; file recipe không sửa. Mọi thứ khác như C: override, seed, `release_id` `tray_s1_f9433b028c52#C:a202cc028a2e`.
- `manifest --folder <thư mục>` in `header_sha256` (phải bằng `parent_header_sha256`), `weights_sha256`, `manifest_sha256` và số file: chính các ghim của plan. Manifest là một dòng `<sha256>  <đường dẫn>` cho mỗi file, xếp theo đường dẫn, bỏ mục bắt đầu bằng dấu chấm.

**Điều kiện trước khi chạy.**
1. Nhiệm vụ con 4.7 đã merge: ghim stage 1 điền từ checkpoint của DA-30, bỏ `draft`, `runplan freeze` ra id mới, `B_FROZEN` đặt bằng id đó. Luật 18.2 đã duyệt.
2. `colab sessions` trống. Số dư ít nhất 32 CU (sàn 14 cộng cap 18). Ngày 9/11 số dư là 14,88 CU sau C+ (mục 17.8), nên phải mua thêm CU trước khi launch.
3. Laptop thức suốt lần chạy (bài học ở mục 17.8). Hiếu cho chạy.

**rtx3060: kiểm lúc khởi chạy và dựng bản cắt** (0 CU, khoảng 1 phút; `D` như ở mục 17.6):

```bash
cd $D && export PYTHONPATH=$(ls -d $PWD/packages/*/src | paste -sd:)
PY=~/denso-da34-pool/.venv/bin/python
REL_C=~/denso-da34-pool/fwdata/releases/tray_s1_f9433b028c52
CUT=~/denso-da34-pool/fwdata/cut-b-$(cut -c1-7 TREE_SHA)
E=G1WholebodyTrayTransferTeleop-v0
$PY -m flywheel_psi0.tray.runplan check configs/runplans/tray/he-tray-b.yaml --release $REL_C --launch \
  || { echo "runplan check --launch failed: do not launch"; exit 1; }
$PY scripts/he/demo_subset.py --src $REL_C --sets configs/runplans/tray/demo_sets-v2.json --set C --out $CUT/sets/B/$E
$PY -m flywheel_psi0.tray.colab_train check --branch B --work $CUT   # "<B id> da34-t4-ft-b-s0: cut and plan hold"
```

**Laptop: kéo bản cắt, guard và watcher.** Như mục 17.6, với `S=da34-t4-ft-b-s0`, `rsync … rtx3060:$CUT/sets/ fwdata/tray/cut-b/sets/`, `--cap 18 --floor 14`.

**Phiên B.** Như phiên C+ ở mục 17.6, thay `C_PLUS` bằng `B` và `cut-cplus` bằng `cut-b`, cộng một bước: mount Drive ngay sau khi upload mã và bản cắt, trước `setup`.

```bash
colab drivemount -s $S /content/drive
vm $S "cd /content/da34 && PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_train check --branch B" \
  || { colab stop -s $S; echo "$S: cut or plan does not hold on the VM, session stopped"; }
vm $S "cd /content/da34; nohup setsid bash -c 'PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_train setup --branch B; echo setup exit \$?' > setup.log 2>&1 < /dev/null &"
vm $S 'tail -2 /content/da34/setup.log'   # chờ "setup exit 0"; phase setup_tray_b của report.json ghi stage1_vlm
vm $S "cd /content/da34; nohup setsid bash -c 'PYTHONPATH=$VMPP Psi0/.venv-psi/bin/python -m flywheel_psi0.tray.colab_train train --branch B; echo train exit \$?' > train.log 2>&1 < /dev/null &"
```

**Sau khi chạy.** Dòng `measured` cho `job_da34_ft_B` trỏ về dòng ước lượng. Chuyển checkpoint sang `rtx3060` theo đúng ba lệnh của mục 17.6 với `J=fwdata/tray/runs/da34-t4-ft-b-s0`; lệch một file thì không eval.

### 18.5 Eval B và cách đọc (nhiệm vụ con 4.4, soạn 9/11/2026, chưa chạy)

**Chạy.** Giống hệt eval C SimReady (mục 16.2) và eval C+ (mục 17.6), để ghép cặp được với mốc 16.6.

| Mục | Giá trị |
|---|---|
| Khi nào | Sau khi eval C+ xong (dự kiến khoảng 18:10Z ngày 9/11/2026), checkpoint B đã chuyển sang `rtx3060` và kiểm sha256 (mục 18.4), và Hiếu bảo chạy. Không chạy song song với eval khác (mục 17.7) |
| Tập, điều kiện | `rp_a04c14e79dfd-2e57f60`, 270 điều kiện, `conditions.sha256` `b9c38b37…`. B không có tập riêng: `variant_of` bảo đảm eval của B là eval của bản 2. Dòng outcome vì vậy mang `run_plan_id` của bản 2, như C+; danh tính của B là checkpoint `da34-t4-ft-b-s0` và thư mục output |
| Cây client | `~/denso-da34-master-079160d` có SimReady, `simple-guard.sh` trước mỗi lô |
| Server | B `ckpt_40000`, `Ta` 24, `--rtc`, `127.0.0.1:22185`, cùng `serve_psi0.sh serve` như server C và C+ |
| Lô | 1 worker, lô 10 episode: mức 1 và 2 xen kẽ trước, mức 0 cuối; tối đa 3 lần, scope `MemoryMax=8G`, `MemorySwapMax=0`. Hai giai đoạn (luật 18.2): giai đoạn 1 là `eval_batch --max-chunks 6`; giai đoạn 2, nếu đi tiếp, là cùng lệnh không có `--max-chunks`, chạy tiếp từ lô thứ 7 tới đủ 27 lô |
| Output | Thư mục mới `~/denso-da34-pool/fwdata/tray/eval/eval-b-simready-<id của B>`, chung cho hai giai đoạn |
| Thời gian | Giả định, theo số đo của eval C SimReady (`runs.jsonl`, 232 s mỗi episode ở mức 1–2): giai đoạn 1 khoảng 4,1 giờ (6 lô đó đo 4,07 giờ). Nếu đi tiếp: 18 lô còn lại khoảng 11,4 giờ, mức 0 khoảng 1,7 giờ; cả 270 khoảng 17,2 giờ. C+ chạy nhanh hơn (204 s mỗi episode), nên đây là cận trên hợp lý |

Script vận hành trên máy (ngoài repo): chép `serve-cplus.sh` và `launch-eval-cplus.sh` của `~/denso-da34-t8/` thành `serve-b.sh` và `launch-eval-b.sh`, thay job thành `da34-t4-ft-b-s0`. Ba điều chặn giữ nguyên: danh sách sha256 của hand-off kiểm qua; có đúng một run có `ckpt_40000`; bounds trong `run_config.json` bằng `meta/stats_psi0.json` của bản cắt B. Bản cắt B là bản cắt C, nên stats phải lệch 0 so với stats của C. Việc này làm ở nhiệm vụ con 4.8, khi Hiếu cho chạy.

**Dừng sau giai đoạn 1.** Cây client `~/denso-da34-master-079160d` không có `--max-chunks`, và B phải chạy đúng client của C. Vì vậy `launch-eval-b.sh` tách hai phần:
- Bộ điều phối `eval_batch` chạy từ một bản checkout master có `--max-chunks` (sau khi PR này merge): `PYTHONPATH` của lệnh `python -m flywheel_psi0.tray.eval_batch` trỏ vào `packages/*/src` của bản checkout đó.
- `--pythonpath` vẫn là `packages/*/src` của `~/denso-da34-master-079160d`. `launcher` đặt biến này cho proxy `act_log` và client `eval_driver`, nên hai tiến trình đó chạy đúng mã của eval C và C+.

`eval_batch.py` ở `079160d`, ở cây client trên máy và ở master trước PR này cùng sha256 `f2f4434e…`; PR này chỉ thêm `--max-chunks`. Giai đoạn 1: `launch-eval-b.sh` với `--max-chunks 6`, rồi dừng. Hiếu đọc rồi mới bảo chạy tiếp. Giai đoạn 2: chạy lại lệnh không có `--max-chunks`; 60 episode đã xong không chạy lại. Kiểm thứ tự trước khi launch: `--dry-run --max-chunks 6` in đúng `l1-000`, `l2-000`, `l1-010`, `l2-010`, `l1-020`, `l2-020`.

**Đọc giai đoạn 1** bằng [`eval_results`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/eval_results.py) `--baseline … --stage1`:

```bash
PLAN=configs/runplans/tray/he-tray-b.yaml
SET=~/denso-da34-pool/fwdata/tray/eval-sets/rp_a04c14e79dfd-2e57f60   # eval C's set (built by master 2e57f60)
EV=~/denso-da34-pool/fwdata/tray/eval
$PY -m flywheel_psi0.tray.eval_results $PLAN --set $SET --out $EV/eval-b-simready-<B id> \
    --baseline $EV/eval-c-simready-rp_a04c14e79dfd --stage1 --json b-vs-c-stage1.json        # E1, E3, F hay đi tiếp
$PY -m flywheel_psi0.tray.eval_results $PLAN --set $SET --out $EV/eval-b-simready-<B id> \
    --baseline $EV/eval-cplus-simready-rp_a04c14e79dfd --stage1 --json b-vs-cplus-stage1.json  # luật 5, mô tả
```

- `--stage1` chỉ đọc 6 lô đầu của cả hai phía. Thiếu một rollout trong 6 lô đó thì lệnh báo lỗi và không đọc.
- `stage1.outcome` là `E1`, `E3`, `F` hoặc `continue`, theo bảng "Hai giai đoạn" của 18.2, tính từ `paired.headline` trên 60 điều kiện. p của McNemar tính lại không làm tròn: 11 cặp so với 0 cho p 0,00098, làm tròn 4 chữ số sẽ thành 0,001. Chỉ đọc `outcome` của lần so với C; lần so với C+ chỉ để mô tả.
- Thử trên số thật đã có (C+ làm biến thể, C làm mốc, 60 điều kiện): C+ 3, C 7, cặp bất đồng 3 và 7, p 0,34, CI −0,17 đến 0,03, `F`. Đây chỉ là kiểm công cụ, không phải luật đọc C+.

**Đọc giai đoạn 2** (nếu đi tiếp, đủ 270 rollout) bằng `eval_results --baseline` không có `--stage1`, cùng các biến, chạy hai lần:

```bash
$PY -m flywheel_psi0.tray.eval_results $PLAN --set $SET --out $EV/eval-b-simready-<B id> \
    --baseline $EV/eval-c-simready-rp_a04c14e79dfd --json b-vs-c.json      # luật 1–4
$PY -m flywheel_psi0.tray.eval_results $PLAN --set $SET --out $EV/eval-b-simready-<B id> \
    --baseline $EV/eval-cplus-simready-rp_a04c14e79dfd --json b-vs-cplus.json   # luật 5, mô tả
```

- `paired.headline` là phép đo của luật 18.2 trên mức 1–2 gộp: `diff` (B − C), `ci` (bootstrap theo điều kiện trong từng mức, `stats` của plan), `ci_vs_0` (`above`, `contains`, `below`; ứng với luật 1, 2, 3), `variant_only` và `baseline_only` (cặp bất đồng), `mcnemar_exact_p` (luật 4).
- `paired.by_level` cho cùng các số theo từng mức; mức 0 chỉ để báo riêng, không vào luật.
- `paired.steps` cho các cặp theo từng bước của bộ chấm (luật 6). `levels` và `headline.failures` cho tỉ lệ `L-PLACE-POSE`. `place_error` chạy như mục 16.4.
- Kiểm trên số giả (12 điều kiện, B 6, C 2, không cặp nào C làm được mà B hỏng): `ci` 0,08–0,58, `above`, `mcnemar_exact_p` 0,125. Đây đúng là trường hợp luật 4 bắt báo cả hai.

### 18.6 `Decision` nháp của B (nhiệm vụ con 4.5)

[`he-tray-b.decision.json`](../../configs/runplans/tray/he-tray-b.decision.json): cùng dạng `Decision` với `Decision` quy tắc 0 ([`he-tray-v2.rule0.decision.json`](../../configs/runplans/tray/he-tray-v2.rule0.decision.json)); `meta.status` `draft`, `verdict` `open`, `signed_by` "pending: Hiếu".
- `criteria` ghi: luật 18.2 và sha256 của khối; plan B và `variant_of`; ghim stage 1 (đang `null`); mốc C (20/240, `L-PLACE-POSE` 131/240, mức 0 5/30, lô của eval C SimReady); mốc C+ (lô đang chạy); bảng `verdict_map`: luật 1 là `pass`, luật 2 là `recorded`, luật 3 là `fail`; ở giai đoạn 1, E1 là `pass`, E3 là `fail`, F là `recorded`; giới hạn.
- `criteria.two_stage` ghi luật hai giai đoạn (mục 18.9) và mốc C trên 60 điều kiện của giai đoạn 1 (7/60, `L-PLACE-POSE` 33/60). `metrics.stage1` để `null` tới khi giai đoạn 1 xong.
- `metrics` để `null` tới khi eval B xong. Khi đó điền từ `eval_results --baseline` (mục 18.5).
- `subject_id` là id nháp `rp_128aec169e12`. Ở nhiệm vụ con 4.7 nó đổi thành id đóng băng; test `test_the_b_decision_is_an_open_draft_on_the_b_plan_and_its_rules` báo lỗi cho tới khi sửa.

### 18.7 Ước lượng chi phí (nhiệm vụ con 4.6)

Giả định, chưa đo. Dòng `estimated` trong [sổ chi phí](../g0/ledger/DA-34.csv), ghi trước mọi lượt của B:

| Job | Ước lượng | Căn cứ |
|---|---|---|
| `job_da34_ft_B` | 16,0 CU (Colab L4), cap 18, sàn 14 | Như C đo được: 15,99 CU, 8,27 giờ, 0,724 s/bước; cùng recipe, cùng bản cắt, 40 000 bước. Chép thư mục VLM từ Drive thay cho tải trọng số VLM của C (khoảng 4,3 GB), coi như không đổi |
| `job_da34_eval_B` | 17,3 giờ `rtx3060`, 0 CU | Như eval C SimReady đo được 17,25 giờ, cộng thời gian khởi động server. Từ 10/11 đây là cận trên, khi đi tiếp giai đoạn 2 |
| `job_da34_eval_B` giai đoạn 1 | 4,1 giờ `rtx3060`, 0 CU | 6 lô đầu của eval C SimReady đo 4,07 giờ. Dòng `estimated` mới ngày 10/11, trỏ về dòng 17,3 giờ; dòng cũ giữ nguyên |
| Stage 1 | Không tính ở đây | Sổ chi phí của DA-30 ([`DA-30.csv`](../g0/ledger/DA-30.csv)), nhiệm vụ 2 của DA-30, trần 4 CU |

Số dư Colab ngày 9/11 là 14,88 CU (mục 17.8). Nó không đủ cho cap 18 cộng sàn 14, nên phải mua thêm CU trước khi launch stage 3 B.

### 18.8 Việc còn lại

- **Phía DA-30** (nhiệm vụ con 2.2 của DA-30). Checkpoint stage 1 cần đúng dạng mà `colab_train --branch B` nhận:
  - một thư mục trên Drive chứa mọi file của thư mục `pre.fast.1by1.2601091803.ckpt.ego200k.he30k` ở psi-model `cb1480f`, cùng tên và trùng từng byte, trừ `model.safetensors`;
  - `model.safetensors` là trọng số sau stage 1, một file, khóa theo tên của Qwen3VL như `PretrainTrainer.save_checkpoint` ghi (`accelerator.save_model` trên mô hình Qwen3VL; `src/psi/trainers/pretrain.py` dòng 441–447 ở `cda3fdf`); header phải trùng header của VLM C (`parent_header_sha256`). `package` của DA-30 (PR #171) kiểm cùng điều này;
  - không file thừa như optimizer hay trạng thái accelerate.

  Lý do: `save_model` chỉ ghi trọng số, còn `from_pretrained` cần config, tokenizer và processor. Khi có thư mục, chạy `colab_train manifest --folder <thư mục>` để lấy hai sha256.
- **4.7.** Điền `job_id`, `drive_dir`, `weights_sha256`, `manifest_sha256` vào `he-tray-b.yaml`, bỏ `status: draft`, `runplan freeze`. Đặt `B_FROZEN` trong `colab_train`. Đổi `subject_id` của `Decision` sang id mới. Hiếu duyệt luật 18.2 (nhãn ngoài khối, không đổi sha256) rồi launch.
- **4.8.** Script `serve-b.sh` và `launch-eval-b.sh` trên `rtx3060` (bộ điều phối từ bản master có `--max-chunks`, mục 18.5). Eval B giai đoạn 1, đọc `stage1.outcome`; Hiếu bảo chạy tiếp thì giai đoạn 2. Đọc theo 18.2, điền `Decision`, dòng thực đo.

### 18.9 Eval B hai giai đoạn (Hiếu 10/11/2026)

_**[Đã chốt 10/11/2026, Hiếu]** "Ghi Decision" (qua phiên điều phối): eval B chạy hai giai đoạn, và luật 18.2 sửa **trước** mọi lượt của B. Phần còn lại của 18.2 vẫn **[Đề xuất]**._

**Lý do.**
- Eval C+ cho thấy thành công gần như độc lập với điều kiện. Số do phiên điều phối đếm: C và C+ cùng thành công ở đúng 1 trong 240 điều kiện mức 1–2, kỳ vọng ngẫu nhiên khoảng 0,75. Trên 60 điều kiện của giai đoạn 1, C+ 3 và C 7 không trùng điều kiện nào (đếm lại ở mục 18.5).
- Mỗi lượt mất khoảng 4 phút (eval C SimReady: 232 s mỗi episode ở mức 1–2). 240 lượt mất khoảng 15,5 giờ.
- Hiếu muốn dừng sớm khi kết quả đã rõ.

**Sửa gì.** Khối `branch-b-rules` thêm phần "Hai giai đoạn", sửa "Phép đo", "Trước khi đọc", luật 6 và giới hạn. sha256 của khối đổi từ `6c0eb9c9…` thành `52f3385b…`; `interpretation.rules_sha256` của [`he-tray-b.yaml`](../../configs/runplans/tray/he-tray-b.yaml) và `Decision` nháp ghi số mới, nên id nháp của plan đổi (mục 18.3). Chưa có lượt train hay eval nào của B, nên đây là sửa trước khi thấy kết quả, không phải đổi luật sau kết quả. Mã: `eval_batch --max-chunks` và `eval_results --stage1` (mục 18.5).

**Đặc tính của luật hai giai đoạn.** Giả định, không phải kết quả: thành công độc lập theo điều kiện, C 8,3 %, B là tỉ lệ thật của B. Số của phiên điều phối (20 000 lần mô phỏng); "Lượt" là số lượt mức 1–2 trung bình, chưa tính 30 lượt mức 0. Claude chạy lại độc lập (3 000 lần, bootstrap 1 000 mẫu) và ra số gần như vậy, ví dụ B = C: báo nhầm 1,7 % (cố định: 2,0 %), dừng F 56 %, 139 lượt; B 16 %: đạt 67 % (cố định: 72,5 %).

| B thật | "B đạt" | "B đạt" nếu cố định 240 | Dừng F | Lượt trung bình |
|---|---|---|---|---|
| 4 % | 0 %* | 0 %* | 88 % | 81 |
| 8,3 % (bằng C) | 2,1 % (báo nhầm) | 2,3 % | 57 % | 138 |
| 12 % | 24 % | 26 % | 29 %* | 186 |
| 16 % | 69 % | 74 % | 12 % (dừng nhầm) | 217 |
| 25 % | 99 % | 100 %* | 0,5 %* | 215 |
| 40 % | 100 % | 100 %* | 0 %* (dừng E1 76 %) | 104 |

\* Ô phiên điều phối không báo; số lấy từ lần chạy lại của Claude.

Đọc bảng: tiết kiệm nhiều nhất khi B không hơn C, trường hợp hay gặp nhất. Đổi lại mất khoảng 5 điểm power ở mức cải thiện vừa (B 16 %). Tỉ lệ báo nhầm khi B = C không tăng (2,1 % so với 2,3 %).

## 19. Bốn run 60k trên cut ALL có vùng đích: VLM sau stage 1 so với VLM gốc, đủ demo và 70 % (nhiệm vụ 6; soạn 11/11/2026, chưa chạy)

_**[Đã chốt 11/11/2026, Hiếu]** (qua phiên điều phối): vẽ vùng đích và sinh lại demo (W1), stage 1 trên bản xuất đã làm sạch (W2), rồi hai run stage 3 60 000 bước ghép cặp; mục tiêu thành công ≥ 80 % trên task khay. Luật đọc 19.2 là **[Đề xuất]**, viết và commit **trước** mọi lượt train hay eval của hai run._

_**[Đã chốt 11/11/2026 01:50, Hiếu]** (qua phiên điều phối): cần số thành công trong ngày 12/11. Hai run chạy **song song** từ khoảng 12:00 ngày 11/11, mỗi run một L4; `ckpt_40000` lên Drive để đọc sớm trong lúc train tiếp tới 60 000; nếu không chạy song song được thì hai run lần lượt, mỗi run 40 000 bước. Lịch, eval và ngân sách ở 19.5 là **[Đề xuất]**._

_**[Đã chốt 11/11/2026, Hiếu]** ("Chốt A100", qua phiên điều phối): hai run vẫn song song, mỗi run một **A100**, hai nhánh như nhau; batch 16 và `nproc_per_node` 1 giữ nguyên, chỉ đổi phần cứng. Căn cứ: lúc 04:2x Hiếu thử trên tài khoản Colab mới (số dư 500,00 CU). `colab new --gpu A100` READY (A100-SXM4-40GB, 12 vCPU); trong lúc phiên đó còn chạy, `colab new --gpu L4` cũng READY, và `colab sessions` liệt kê cả hai. H100 trả 503 nên không dùng. Plan dự phòng 40k lần lượt không còn cần. VLM stage 1 nằm trên Drive của tài khoản mới (DA-30 chạy stage 1 trên tài khoản đó)._

_**[Đã chốt 11/11/2026, Hiếu]** ("Thêm hai run 70%", qua phiên điều phối): thêm `B_70` và `C_70`, thành **bốn run** (hai VLM × hai lượng dữ liệu), cùng recipe, 60 000 bước, seed train 0 và tập eval. Tập con 70 % lấy theo seed, cùng một danh sách cho cả hai run 70 %. Cả bốn run dùng chung stats của ALL (đề xuất của phiên điều phối; Ψ₀ không bắt stats theo tập train, xem 19.1). Thử bốn phiên A100 cùng lúc, lùi về hai đợt nếu Colab từ chối. Luật đọc 19.2 viết lại cho bốn run là **[Đề xuất]**, chờ Hiếu duyệt. Plan dự phòng 40k đã xóa._

### 19.1 Thiết lập

**Lý do** (số của phiên điều phối, 11/11/2026). Eval C thấp vì vùng đích trên bàn B không được vẽ. Planner căn ngang theo đích ẩn, còn policy chỉ thấy ảnh. Độ lệch chuẩn của độ lệch ngang base − đích là 13 cm ở lượt hỏng, 5,3 cm ở lượt thành công.

**Hai việc đi trước** (của story khác; mục này chỉ dùng kết quả):
- **W1** (DA-33): vẽ vùng đích (revision mới của `visuals`), rồi sinh lại toàn bộ demo của hai kho `tray_s1_f9433b028c52` (kho `s1-pool-1104`, seed 1000–1609) và `tray_s1_6c0fd7d37f77` (kho nhắm lỗi của C+), cùng seed và planner. Cắt tập ALL.
- **W2** (DA-30): stage 1 của VLM C trên bản xuất `egx_7b43c30dc5d88cd7` (153 clip egocentric của đội, đã qua làm sạch E-A của DA-04 nhiệm vụ con 10.5).

**Bốn run**, chỉ khác VLM và lượng dữ liệu:

| Mục | Run 1 `B_ALL` | Run 2 `C_ALL` | Run 3 `B_70` | Run 4 `C_70` |
|---|---|---|---|---|
| VLM | VLM của C sau stage 1 của W2 | VLM của C (`pre.fast.1by1.2601091803.ckpt.ego200k.he30k`) | Như run 1 | Như run 2 |
| Action header | `postpre.1by1.pad36.2601131206.ckpt.he30k` | Giống run 1 | Giống run 1 | Giống run 1 |
| Dữ liệu | Cut ALL của W1 | Cut ALL (mốc "đủ demo") | Tập con S70 của ALL | Đúng tập con S70 đó |
| Stats | `meta/stats_psi0.json` của ALL | Giống run 1 | Giống run 1 | Giống run 1 |
| Recipe | `psi0-stage3.yaml`: batch 16, LR 1e-4, cosine, warmup 1 000; 60 000 bước; seed train 0; `validation_steps` 2 000 | Giống run 1 | Giống run 1 | Giống run 1 |
| Eval | 270 điều kiện của bản 2, tập `rp_a04c14e79dfd-2e57f60`, cảnh có vùng đích của W1 | Giống run 1 | Giống run 1 | Giống run 1 |

- **Tập con S70.** Lấy theo seed, không theo kết quả hay chất lượng. Trong mỗi phần của ALL (kho `s1-pool-1104` và kho nhắm lỗi), xếp seed của tập demo theo sha256 của seed (chuỗi thập phân) rồi lấy ceil(0,7 × n) seed đầu (`pairplan.subset_seeds`). Làm tròn lên trong từng phần, nên mỗi kho giữ đúng phần của nó. Với cỡ W1 đã ghim: ceil(0,7 × 429) + ceil(0,7 × 177) = 301 + 124 = **425 episode**, 603 915 frame. Danh sách của từng phần được ghim bằng sha256 (`subsets` của plan) trước mọi lượt chạy: phần kho `5cd4a08a…`, phần nhắm lỗi `0aa1c409…`; `B_70` và `C_70` dùng đúng một danh sách.
- **Stats chung.** Ψ₀ đọc `meta/stats_psi0.json` trong thư mục dữ liệu (`psi0_trainer.py`), không tự tính lại theo tập train. Vì vậy tập con S70 mang đúng file stats của ALL, và chuẩn hóa (cùng pose mở tay) giống hệt ở cả bốn run. Hai run 70 % chỉ khác hai run ALL ở lượng dữ liệu. Mã 6.3 phải chép file đó vào dữ liệu S70 và kiểm sha256 bằng `cut.stats_sha256`; server eval dùng đúng file đó.

- **Không phải nhánh B.** B (mục 18) là C với VLM stage 1: 160 demo cũ, 40 000 bước, cảnh không có vùng đích. `B_ALL` và `B_70` khác B ở dữ liệu, số bước và cảnh. Hai plan độc lập.
- **Cut ALL.** Mỗi kho tái sinh là một phần: mọi episode mà QA của DA-03 giữ và qua bộ lọc chất lượng ngày 3/11 (nghiêng khay khi mang ≤ 10°, vật lệch cuối ≤ 20 mm). Đây là bộ lọc C, C+ và CMAX đã dùng; không giới hạn số, không xếp hạng, không chọn lọc thêm. Hai phần nối theo thứ tự như `cplus_cut` đã nối C và tập nhắm lỗi.

### 19.2 Luật đọc bốn run 60k (viết trước khi chạy)

**[Đã duyệt 11/11/2026, Hiếu]** ("Duyệt 19.2", qua phiên điều phối), trước mọi lượt của bốn run. Viết lại ngày 11/11/2026 cho bốn run (Hiếu: "Thêm hai run 70%"); khối cũ cho hai run (`rules_sha256` `24747738…`) chưa được duyệt và không còn dùng. Khối giữa hai dấu `pair60k-rules` được ghim bằng sha256 ở `interpretation.rules_sha256` của [`he-tray-pair60k.yaml`](../../configs/runplans/tray/he-tray-pair60k.yaml); nhãn này nằm ngoài khối. Các so sánh (a′), (f), (g), (h) là trường `comparisons` của plan; gói bằng chứng (19.6) tính đúng các so sánh đó.

<!-- pair60k-rules -->

**Bốn run**, cùng recipe, 60 000 bước, seed train 0, cùng file stats của ALL, cùng tập eval:

| Run | VLM | Dữ liệu |
|---|---|---|
| `B_ALL` | VLM của C sau stage 1 (W2) | Cut ALL |
| `C_ALL` | VLM của C | Cut ALL (mốc "đủ demo") |
| `B_70` | VLM của C sau stage 1 (W2) | Tập con S70: 70 % của ALL |
| `C_70` | VLM của C | Đúng tập con S70 đó |

S70 lấy theo seed, không theo kết quả hay chất lượng: trong mỗi phần của ALL, xếp seed theo sha256 của seed (chuỗi thập phân) và lấy ceil(0,7 × n) seed đầu. Danh sách của từng phần được ghim bằng sha256 trong plan trước mọi lượt chạy.

**(a′) So sánh chính: `B_70` so với `C_70`.**
- Phép đo: hiệu ghép cặp `B_70` − `C_70` theo điều kiện, trên tập eval `rp_a04c14e79dfd-2e57f60` (`conditions.sha256` `b9c38b37…`). Mọi run chạy trên cảnh có vùng đích của W1.
- Cách tính như luật nhánh B (mục 18.2): d_i = s_B_70,i − s_C_70,i. CI 95 % bootstrap theo điều kiện: lấy mẫu lại d_i trong từng mức, 10 000 lần, hạt giống 20261103 (`stats` của plan). McNemar chính xác hai phía, với b là số cặp `B_70` làm được mà `C_70` hỏng, c là số cặp ngược lại.

**Hai giai đoạn**, như mục 18.2:
- Giai đoạn 1 là 6 lô đầu (`l1-000`, `l2-000`, `l1-010`, `l2-010`, `l1-020`, `l2-020`): 60 điều kiện, chạy cho **cả bốn** run.
- Đọc trên 60 điều kiện đó (`eval_results --stage1`, biến thể `B_70`, mốc `C_70`):

| Kết quả | Điều kiện | Làm gì |
|---|---|---|
| E1 | McNemar p < 0,001, b > c, cận dưới CI 95 % > 0 | Dừng. Đọc luật 1 |
| E3 | McNemar p < 0,001, b < c, cận trên CI 95 % < 0 | Dừng. Đọc luật 3 |
| F | Không phải E1 hay E3, và b ≤ c | Dừng. Đọc như luật 2: "không thấy `B_70` hơn `C_70` trên 60 điều kiện". Không đọc luật 3 |
| Đi tiếp | Còn lại: b > c | Cả bốn run chạy 18 lô còn lại của mức 1–2, rồi mức 0. Đọc luật 1–3 trên 240 điều kiện; 60 lượt của giai đoạn 1 tính vào 240 |

- Mức 0 (30 lượt lặp) chỉ chạy khi đi tiếp. Chỉ (a′) quyết định dừng hay đi tiếp; (f), (g), (h) đọc trên cùng giai đoạn với (a′). Không có điểm đọc nào khác.

| # | Điều kiện, trên 240 điều kiện (hoặc 60 khi dừng ở E1, E3) | Đọc là |
|---|---|---|
| 1 | Cận dưới CI 95 % của (`B_70` − `C_70`) > 0 | Với cùng 70 % demo, VLM sau stage 1 egocentric giúp, cùng 60 000 bước, trên cảnh có vùng đích (sơ bộ, trên dev) |
| 2 | CI 95 % chứa 0 | Không thấy tác động của stage 1 ở mức này. Không đọc thành "egocentric không giúp" |
| 3 | Cận trên CI 95 % < 0 | `B_70` kém hơn `C_70`. Đây là kết quả âm hợp lệ, phải báo |
| 4 | McNemar | Báo p cạnh luật 1–3, không đổi quyết định. Khi McNemar (p < 0,05 hay không) và CI cho hai kết luận khác nhau, báo cả hai |

**(f) Không kém mốc đủ demo: `B_70` so với `C_ALL`.**
- Phép đo: hiệu ghép cặp `B_70` − `C_ALL`, cùng cách tính CI và McNemar như (a′).
- Biên không kém là 10 điểm %, biên của HS (spec mục 3). Đọc "không kém" khi cận dưới CI 95 % > −0,10; "kém" khi cận trên < −0,10; còn lại là "chưa rõ".
- Đọc "egocentric bù phần demo bị cắt" **chỉ khi** (f) không kém **và** cận dưới CI 95 % của (a′) > 0. Thiếu một trong hai thì không đọc câu đó, kể cả khi (f) không kém.

**(g) Lượng demo có phải nút thắt: `C_70` so với `C_ALL`.**
- Phép đo: hiệu ghép cặp `C_70` − `C_ALL`, cùng cách tính và cùng biên 10 điểm % như (f).
- Nếu `C_70` không kém `C_ALL` thì ghi rõ: 30 % demo cắt đi không phải nút thắt ở mức này, và (f) không kém **cũng không nhờ egocentric** (như ghi chú của HS, spec mục 3).
- Nếu `C_70` kém `C_ALL` thì phần demo cắt đi có giá trị, và (f) mới là phép thử "egocentric bù demo".

**(h) Phụ: `B_ALL` so với `C_ALL`.** Hiệu ghép cặp, CI 95 % so với 0 và McNemar như (a′). Chỉ mô tả: không quyết định dừng hay đi tiếp, không thay (a′).

**(b) Số tuyệt đối của từng run.**
- Mức 1–2 gộp, so với mốc 80 %: tỉ lệ thành công trên các điều kiện mức 1–2 đã chạy (60 hoặc 240), kèm khoảng Wilson 95 %. Đọc "đạt mốc 80 %" khi cận dưới Wilson ≥ 0,80; "chưa đạt" khi cận trên < 0,80; còn lại là "chưa rõ".
- Mức 1 và mức 2 tách riêng, so với 70 % (Cấp 3 của BTC, spec mục 3): mỗi mức một tỉ lệ kèm Wilson 95 %, cùng cách đọc với mốc 0,70. Không gộp với mức 0.
- Mức 0 báo riêng nếu đã chạy.
- (b) không đổi việc dừng hay đi tiếp của (a′). Muốn chạy thêm chỉ để thu hẹp khoảng của (b) thì ghi `Decision` mới.

**(c) Phụ, không tốn CU: thành công theo dung sai nới.**
- Không phải chỉ số chính; không đổi (a′), (b), (f) hay (g). Mọi câu báo số này phải có chữ "nới".
- Với mỗi run, trên các điều kiện đã chạy: số lượt "thành công nới" ở dung sai vị trí 5 cm (dung sai của bộ chấm), 7,5, 10, 15 và 20 cm. Dung sai góc giữ 10° ở mọi điểm.
- Một lượt là "thành công nới" ở dung sai r khi nó thành công, hoặc khi nó hỏng với nhãn `L-PLACE-POSE` mà khoảng cách cuối của khay tới đích ≤ r và sai số góc ≤ 10° (`place_error --curve`, cách tính của mục 16.4).
- Không nới lỗi khác (rơi vật, nghiêng khay, một tay, hết giờ). Lượt `L-PLACE-POSE` dừng trước bước `release_stand`, nên "nới" cũng bỏ qua bước đó.

**(d) So với C và C+ cũ.** Lệch cấu hình ở cả cảnh (vùng đích vẽ hay không), số bước (60 000 so với 40 000) và dữ liệu (ALL tái sinh hay S70 so với 160 hay 320 demo cũ). Chỉ đặt cạnh nhau để mô tả. Không quy hiệu nào cho một nguyên nhân, không ghép cặp với eval C hay C+.

**(e) Checkpoint nào là số chính.**
- Số chính là `ckpt_60000` (`checkpoints.primary` của plan đã đóng băng). (a′), (b), (c), (f), (g), (h) đọc trên checkpoint này.
- `ckpt_40000` là **đọc sớm** (`checkpoints.early`). Đọc giai đoạn 1 (60 điều kiện) của các run đã có, cùng cách tính, và mọi số đều ghi "đọc sớm, 40k".
- Đọc sớm không cho E1, E3, F hay đi tiếp, không đọc câu "egocentric bù" của (f) hay câu "không phải nút thắt" của (g), không quyết định chạy giai đoạn 2, và không thay số chính, kể cả khi hai số khác nhau.
- Bước 40 000 của run 60k không phải run 40 000 bước: LR cosine chạy trên 60 000 bước, nên ở bước 40 000 LR chưa giảm hết. Không so số đọc sớm với số của C hay của C+.
- Một run không có checkpoint số chính (hỏng sau 40k, chạm trần) thì mọi so sánh có run đó không có số chính. Số 40k vẫn chỉ là đọc sớm; chạy lại hay đọc số khác cần `Decision` mới.

**Trước khi đọc.**
- Plan đã đóng băng.
- Bốn run dùng cùng một file stats: `meta/stats_psi0.json` của cả bốn lần chạy có sha256 bằng `cut.stats_sha256` (stats của ALL; S70 dùng đúng file đó).
- `B_70` và `C_70` train trên đúng danh sách S70: số episode và sha256 danh sách của từng phần bằng ghim `subsets` của plan.
- Eval cùng cây client có vùng đích (`pinned_files` của plan), server `Ta` 24 + RTC, 1 worker. Mỗi run có đủ rollout của giai đoạn đang đọc.
- Server của mỗi run nạp checkpoint đúng bước của (e), cùng sha256 với bản trên Drive. Server chạy trên `rtx3060` hay trên Colab qua SSH forward đều được, mỗi server một client; nơi chạy ghi cạnh số.

Thiếu một điều thì không đọc so sánh có run đó: ghi `Decision` và báo. Lượt hỏng do hạ tầng chạy lại như mục 2; mỗi điều kiện lấy lần xong sớm nhất.

**Giới hạn phải ghi cạnh mọi số.**
- Sơ bộ, trên dev: 1 seed train mỗi run, 1 rollout mỗi điều kiện. Rollout trên EGL không lặp lại được (mục 13.2).
- Chỉ trong sim, renderer MuJoCo.
- Với 60 điều kiện, CI 95 % của một hiệu ghép cặp rộng khoảng ±15 điểm % (ước lượng). Vì vậy (f) và (g) gần như không thể đọc "không kém" ở giai đoạn 1: cần cận dưới > −0,10 trong khi nửa độ rộng đã khoảng 0,15. Dừng ở giai đoạn 1 thì (f) và (g) thường là "chưa rõ".
- Bốn so sánh trên cùng bốn run, không hiệu chỉnh đa so sánh; chỉ (a′) quyết định.
- Pose tay của 153 clip là pose giả, ước lượng từ một camera; người bê một hộp đỏ, không phải khay của sim.
- Stage 1 tốn thêm compute (sổ chi phí của DA-30).
- Cùng một đội dựng task, sinh demo và quay egocentric.
- Dừng ở giai đoạn 1 là đọc trên 60 điều kiện. F không phải bằng chứng stage 1 không giúp: một cải thiện vừa vẫn có thể dừng ở F. Bảng đặc tính ở mục 18.9 giả định mốc 8,3 %; mốc `C_70` trên cảnh có vùng đích chưa biết, nên bảng đó không áp nguyên cho các run này.

Luật này không đổi sau khi thấy kết quả. Muốn đổi thì ghi `Decision` mới và báo theo cả luật cũ lẫn luật mới.

<!-- /pair60k-rules -->

### 19.3 RunPlan cặp (nhiệm vụ con 6.1, bốn run ở 6.10)

[`he-tray-pair60k.yaml`](../../configs/runplans/tray/he-tray-pair60k.yaml), `status: draft`, id nháp `rp_e2fb9f62c223` (ghim VLM stage 1 của W2 ngày 11/11/2026; ghim W1 và S70 trước đó là `rp_9d89260a974d`; bốn run trước khi ghim là `rp_9614ef46ed9d`, khối luật mới `e7f90396…`; hai run cap 70 là `rp_d44e3e6262b4`, cap 61 từng cho `rp_92ab06fe3fff`; trước đó `rp_350a28bb7245` khi ghim cảnh `+zone1`, `rp_01c132b8d3b0` lúc đầu). Id đổi khi điền ghim. Mọi chỗ trống đã điền; id còn đổi nếu sửa plan trước khi đóng băng.

**Schema riêng.** Cut ALL trải trên hai release, mà `TrayRunPlan` chỉ có một release. Vì vậy plan cặp dùng schema riêng [`pairplan`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/pairplan.py) (`purpose: paired_train`).
- Cut, tập con, recipe kèm override, seed train, eval và stats nằm một lần ở cấp plan. Mỗi nhánh chỉ chọn cha và dữ liệu (`data`: tên tập con, bỏ trống là cả cut). Vì vậy "giống hệt trừ VLM và tập con" đúng theo cấu trúc.
- Schema chỉ nhận các nhánh là **mọi cặp (cha, dữ liệu) đúng một lần**: hai cha × (cut và các tập con). Thiếu `C_70` thì `B_70` không có mốc, nên plan bị từ chối ngay khi nạp. Plan hai nhánh không tập con vẫn hợp lệ.
- `check` kiểm thêm:
  - hai cha, một cha stage 1 và một cha release; VLM stage 1 bắt đầu từ VLM của cha kia; hai cha cùng action header;
  - mỗi tập con đi theo đúng các phần của cut, đúng thứ tự; khi phần đã ghim, `episodes` và `seeds_sha256` của tập con phải bằng danh sách `subset_seeds` tính lại từ file tập demo đã ghim; tổng episode bằng tổng các phần, nhỏ hơn cut; ghim tập con trước khi phần của nó được ghim thì bị từ chối;
  - `comparisons`: đúng một so sánh chính, giữa hai nhánh cùng dữ liệu, biến thể là nhánh có VLM stage 1; so sánh "không kém" phải có biên, so sánh khác không có;
  - `schedule.waves`, nếu có: chỉ cho lịch song song, mỗi nhánh ở đúng một đợt;
  - recipe đúng file và sha của bản 2; override chỉ được `train.validation_steps` và `train.max_training_steps`, và phải có `train.max_training_steps`;
  - `eval_of`: bản 2 đã đóng băng, đúng id; `eval`, `stats`, `metric`, `task`, `embodiment`, `code`, `psi_model`, recipe và seed train trùng bản 2; tên tập eval thuộc id đó;
  - mỗi phần của cut đã ghim: ghim release, file tập demo và tên tập cùng lúc; release mới, không phải release cũ; `data_class` `public`; file tập demo kiểm như `runplan` (sha256 của file, hash tính lại từ seed, ghim chất lượng và QA);
  - khối luật 19.2 trùng `rules_sha256`; ngân sách là đúng các nhánh, cap × số run không quá trần (4 × 70 = 280); dòng watcher ghi đúng `--cap` và `--floor`;
  - `checkpoints` (luật e): `primary` bằng số bước; `early`, nếu có, trước `primary`; cả hai là bội của `train.checkpointing_steps` (10 000) của recipe, tức Ψ₀ có lưu checkpoint đó.
- `schedule`: `parallel` (một phiên mỗi run cùng lúc) hay `sequential`, sàn số dư, cách checkpoint lên Drive, và `waves` (`[[B_ALL, C_ALL], [B_70, C_70]]`: hai đợt khi Colab từ chối phiên thứ ba hay thứ tư). Dòng tóm tắt của `check` in số dư cần có: sàn cộng cap của mọi run chạy cùng lúc, 14 + 4 × 70 = 294 CU.
- `pairplan subset <plan>` in danh sách seed, số episode và sha256 của từng phần mỗi tập con, khi W1 đã ghim phần đó; số này chép vào `subsets` của plan.

**Plan dự phòng 40k đã xóa** (11/11/2026). `he-tray-pair40k-seq.yaml` (`rp_862e049c8d29`) chỉ có hai nhánh và ghim khối luật cũ; plan 60k chạy trên A100 nên không còn cần nó.

**Chỗ trống.** Không còn chỗ trống nào (11/11/2026): `pairplan check` qua và chỉ ghi "draft" (trước khi ghim W2 là "4 pins pending", trước W1 là 19). `freeze` và `check --launch` vẫn từ chối vì plan còn `draft` và chưa có file khóa; plan có chỗ trống thì cả hai liệt kê từng chỗ. Các chỗ đã ghim:

| Chỗ trống | Ai điền |
|---|---|
| Mỗi phần của cut: `release`, `demo_sets` (file tập demo commit cạnh plan, có ghim chất lượng và QA), `set_name` | **Đã ghim** 11/11/2026 từ cut của W1 (DA-33, 05:11, `rtx3060:~/denso-da34-pool/fwdata/cut-all-zone1`): phần kho `tray_s1_41899efb4b27` (429, tập `ALL` `a919ce21…`, file `demo_sets-all-zone1-pool.json`), phần nhắm lỗi `tray_s1_4a8f4a8c6a8d` (177, `19ed50d2…`, `demo_sets-all-zone1-tgt.json`); file chất lượng là hai file cũ, vì parquet trùng từng byte; QA là báo cáo mới (`3db475f2…`, `ed6d274c…`) |
| `cut.episodes`, `frames`, `stats_sha256` | **Đã ghim**: 606, 861 624, `meta/stats_psi0.json` `1c745091…` (stats của 606 episode, dùng cho cả bốn run) |
| `vlm_stage1.job_id`, `drive_dir`, `weights_sha256`, `manifest_sha256`; header phải trùng `parent_header_sha256` `53d000d9…` như B | **Đã ghim** 11/11/2026 từ `vlm.json` của W2 (DA-30, A100, RunPlan `rp_1d7627234111`, bước 300, `final`): job `da30-tray-ego-b`, `denso/da30/da30-tray-ego-b/vlm` dưới `MyDrive` (12 file), trọng số `c48ec2df…` (4 262 742 488 byte), manifest `019daa80…`. Cha `6e63da17…` là VLM của C; dữ liệu `team-ego-tray-clean-132` (`egx_7b43c30dc5d88cd7`); `header_problems` rỗng. Phiên điều phối chạy lại kiểm nạp như stage 3 (`vlm_checkpoint load-check`): không lỗi, vocab 153 792, tokenizer 151 669, 2 131 333 120 tham số; phase `check-vlm` của DA-30 hỏng vì lỗi ghi báo cáo nên `report.json` không có phase đó. Manifest tính lại từ sha256 từng file trong `vlm.json` khớp `019daa80…`. `colab_train` vẫn kiểm trọng số, manifest và header trên VM trước khi train |
| Tập con S70, mỗi phần: `episodes`, `seeds_sha256` (`pairplan subset`); cả tập: `episodes`, `frames` | **Đã ghim**: 301 `5cd4a08a…`, 124 `0aa1c409…`; 425 episode, 603 915 frame (tổng `length` trong `meta/episodes.jsonl` của ALL trên các seed S70; dữ liệu S70 của 6.3 phải ghi đúng số này trong `meta/info.json`) |
| `pinned_files`: danh sách của bản 2, băm lại trên cây có vùng đích | **Đã ghim** 11/11/2026 trên master `7b0defd1` (sau #182); chỉ `mjcf.py` và `simple_task.py` khác bản 2 |
| `cut.visuals_revision` `4763fbfaa4f8e97658e68b57d01b4c86659e08b5+zone1` | **Đã ghim** 11/11/2026; release của W1 phải ghi đúng revision này |

Lệnh: `python -m flywheel_psi0.tray.pairplan check configs/runplans/tray/he-tray-pair60k.yaml`; với `--launch` trước mọi job; `freeze` khi đủ ghim và đã bỏ `draft`.

### 19.4 Số epoch với 60 000 bước

Một epoch là một lượt qua mọi frame của cut (batch 16, `observation-horizon` 1). Số frame của C, C+ và CMAX lấy từ `meta/info.json` của bản cắt trên `rtx3060`. Số của ALL là **ước lượng**: cùng luật cắt áp lên hai kho hiện tại, đếm từ file chất lượng (cột `frames`) sau khi bỏ reject QA. Cách đếm này cho đúng 429 episode, 610 069 frame của CMAX.

| Tập | Episode | Frame | Bước | Epoch |
|---|---|---|---|---|
| C | 160 | 228 247 | 40 000 | 2,80 |
| C+ | 320 | 455 372 | 40 000 | 1,41 |
| ALL (W1: 429 + 177) | 606 | 861 624 | 60 000 | 1,11 |
| S70 (301 + 124) | 425 | 603 915 | 60 000 | 1,59 |

- **Điểm Hiếu cần xem.** 60 000 bước trên ALL cho mỗi demo **ít** lượt hơn C+ và chỉ khoảng 40 % của C.
  - Muốn bằng số epoch của C+ cần khoảng 75 700 bước, khoảng 30 CU một run.
  - Muốn bằng C cần khoảng 151 000 bước, khoảng 59 CU một run.
  - Plan giữ 60 000 bước như đã duyệt. Đổi số bước thì sửa override trước khi đóng băng (plan còn nháp).
- **Run 70 % cùng số bước, không cùng số epoch.** Với 60 000 bước, mỗi demo của S70 được thấy khoảng 1,43 lần nhiều hơn ở ALL. So sánh 70 % với ALL là "ít demo hơn, cùng compute", như HS (spec mục 3). Số episode và frame của ALL do W1 ghim khớp đúng ước lượng cũ (cùng seed, parquet trùng từng byte); frame của S70 đếm từ `meta/episodes.jsonl` của ALL.
- `pairplan check` in số epoch của ALL và S70 vào dòng tóm tắt, từ `cut.frames` và `subsets[].frames`.

### 19.5 Lịch, eval và ngân sách (ước lượng, chưa đo) [Đề xuất]

**Bốn run song song trên một tài khoản.** `scripts/colab/cu_watch.py` cho một đợt nhiều phiên: một `guard` cho cả đợt, mỗi phiên một `session` watcher trong cùng registry, các lệnh `new` nối nhau qua `new.lock`, và khi nhiều phiên cùng chạy thì phần tụt số dư chia theo tỉ lệ rate của từng phiên. Ngày 3/11 tài khoản cũ đã chạy 3 phiên song song ([psi0-finetune-cost.md](../g0/psi0-finetune-cost.md)); tài khoản mới mới thử hai phiên (một A100, một L4). Bốn phiên A100 cùng lúc **chưa thử**. Ba điều phải giữ:
- **Một đợt mỗi lúc.** Guard từ chối chạy khi đã có guard khác, và dừng mọi phiên không có watcher đăng ký. Đợt stage 1 của W2 phải xong (guard của nó đã thoát) trước khi mở đợt train. Các phiên serve của eval vào **cùng** registry với đợt train, mỗi phiên một watcher.
- **Sàn chỉ an toàn khi số dư đủ cho mọi cap cùng lúc**: lúc launch ít nhất 14 + 4 × 70 = 294 CU (`pairplan check` in số này), cộng cap của các phiên serve khi chúng vào đợt: 294 + 3 × 22 = 360 CU.
- **Mỗi phiên mount Drive riêng** (`colab drivemount -s <phiên>`), cần Hiếu đồng ý trên trình duyệt cho từng phiên. Đo trên A100 của DA-30 (11/11/2026): VM mới nào cũng hỏi đồng ý, và lệnh mount trong VM hết giờ sau 120 s; Hiếu bấm muộn thì chạy lại `colab drivemount` một lần, lần đó mount được mà không hỏi lại. Trên mỗi VM, `persist --watch 600 --pid <pid train>` chép mọi `ckpt_<step>` đã lưu xong lên Drive (`sync_job` của `trainer/colab.py`, không `--delete`). Vì vậy `ckpt_40000` còn trên Drive khi VM chỉ giữ 5 checkpoint gần nhất. Mỗi run lưu 6 checkpoint (mỗi 10 000 bước), bốn run là 24 checkpoint, nên phải xem chỗ trống trên Drive trước khi launch.

**Hai đợt nếu Colab từ chối** (`schedule.waves`). Launch lần lượt `B_ALL`, `C_ALL`, `B_70`, `C_70`. Nếu `cu_watch session --new` của phiên thứ ba hay thứ tư thoát mã 6 (Colab từ chối, không mở phiên nào, không dừng phiên khác), thì dừng phiên đã mở của đợt hai nếu có, và chạy `B_70`, `C_70` thành đợt hai ngay khi hai phiên của đợt một đã dừng.

**`he1_fetch.py follow`** (PR #186) nhận `--total-steps 60000 --gpu A100`, nên cả bốn phiên dùng vòng fetch tự dừng của 19.8.

**Thời gian mỗi run trên A100** (ước lượng, chưa đo trên cut ALL): 60 000 × 0,47 s = 7,83 giờ train (A100, batch 16, đo 400 bước liên tục ở [psi0-finetune-cost.md](../g0/psi0-finetune-cost.md) mục 3), cộng 30 lần val (mỗi 2 000 bước) × khoảng 50 s = 0,42 giờ, cộng khoảng 0,2 giờ setup như C: **khoảng 8,45 giờ**, trong khoảng 8–9 giờ. Job bị chặn ở CPU nạp dữ liệu, và VM A100 mới cũng có 12 vCPU như lúc đo. Trên L4, số đo ngắn (0,71 s) và run C đầy đủ (0,724 s mỗi bước, gồm val và setup) chỉ lệch khoảng 2 %, nên số ngắn của A100 là căn cứ dùng được. Run 70 % có cùng số bước nên cùng thời gian; ít episode hơn không làm nó nhanh hơn.

**Mốc thời gian** (ước lượng). T0 là lúc các phiên của đợt một bắt đầu train, sau khi cut ALL và S70 (W1, rồi `pairplan subset`), VLM stage 1 (W2) và mã chạy của 6.3 đã có, và đợt stage 1 đã đóng. Giờ ví dụ lấy T0 = 06:00 (giả định).

| Mốc | Bốn phiên cùng lúc | Hai đợt: đợt một (`B_ALL`, `C_ALL`) | Hai đợt: đợt hai (`B_70`, `C_70`) | Căn cứ |
|---|---|---|---|---|
| `ckpt_40000` trên Drive | +5,7 giờ | +5,7 | +14,4 | 0,2 + 40 000 × 0,47 s + 20 val; `persist` mỗi 10 phút; đợt hai bắt đầu khoảng +8,7 (dừng đợt một, mở phiên, setup) |
| `ckpt_40000` trên `rtx3060` | +6,0 | +6,0 | +14,7 | 6,25 GB ở khoảng 11 MB/s, khoảng 10 phút, kiểm sha256 |
| `ckpt_60000` trên Drive, hết train | +8,45 | +8,45 | +17,2 | như trên, 60 000 bước, 30 val |
| `ckpt_60000` trên `rtx3060` | +8,8 | +8,8 | +17,5 | như trên |

Luật đọc không đổi khi đổi phần cứng: (e) vẫn lấy `ckpt_60000` làm số chính và `ckpt_40000` chỉ để đọc sớm. Cosine vẫn trải trên 60 000 bước vì recipe và override không đổi; GPU chỉ đổi tốc độ, không đổi bước nào được lưu (mỗi 10 000 bước).

**Eval: bốn làn, mỗi làn một model.** Giai đoạn 1 (6 lô, 60 điều kiện) mất khoảng 4,1 giờ mỗi model trên `rtx3060` (6 lô đó của eval C SimReady đo 4,07 giờ). `rtx3060` chỉ chạy **một** server Ψ₀ (server thứ hai không vừa GPU 12 GB), và mỗi server chỉ một client (mục 17.7). Vì vậy:
- **Làn 1**: server và client trên `rtx3060`, cho `B_ALL`.
- **Làn 2–4**: server Ψ₀ trên một Colab L4, client trên `rtx3060` qua SSH forward (đã chạy được ngày 3/11, RTT 460 ms), cho `B_70`, `C_70` và `C_ALL`. Hai run của so sánh chính (a′) cùng được serve trên Colab, nên chúng được phục vụ như nhau.
- `rtx3060` khi đó chạy một server và bốn client. Phép đo 17.7 mới có một server và hai client; bốn client chưa đo, nên thời gian dưới đây có thể dài hơn (giả định). Giả định mỗi episode qua Colab chậm hơn khoảng 10 %: giai đoạn 1 khoảng 4,5 giờ, cộng khoảng 0,4 giờ setup và nạp.

| Làn | Model | Đọc sớm 40k | Số chính 60k |
|---|---|---|---|
| 1, `rtx3060` | `B_ALL` | +6,0–10,1 | +10,1–14,2 |
| 2, Colab L4 | `B_70` | +6,1–10,6 | +10,6–15,1 |
| 3, Colab L4 | `C_70` | +6,1–10,6 | +10,6–15,1 |
| 4, Colab L4 | `C_ALL` | +6,1–10,6 | +10,6–15,1 |

- Với bốn phiên cùng lúc: đọc sớm của cả bốn khoảng **T0 + 10,6 giờ** (16:35 nếu T0 = 06:00), số chính khoảng **T0 + 15,1 giờ** (21:05).
- Với hai đợt: số chính của `B_ALL`, `C_ALL` như trên, nhưng (a′) cần `B_70`, `C_70` ở 60k: eval giai đoạn 1 từ +17,5, xong khoảng **T0 + 22,4 giờ** (04:25 ngày hôm sau). Đọc sớm 40k của đợt hai rơi vào +14,7, sau khi các làn đã rảnh.
- Các phiên serve mở khoảng T0 + 5,3 giờ bằng `cu_watch session --new --gpu L4` trong registry của đợt train, lúc bốn A100 còn train: tổng cộng bảy phiên, **chưa thử**. Phiên nào bị từ chối (mã 6) thì làn đó mở sau khi các phiên train đóng (+8,9 giờ) và chỉ đọc 60k; làn 1 làm thay đọc sớm của model đó nếu kịp.
- Server Colab phải chạy cùng lệnh với server tại chỗ (`serve_psi0.sh serve`: seeded, `Ta` 24, `--rtc`), nạp đúng file stats của ALL và kiểm sha256 checkpoint trước khi nạp. Mã ở `colab_serve`, lệnh ở 19.9.
- Giai đoạn 2 (đủ 240): theo 19.2, chỉ khi giai đoạn 1 của (a′) ở số chính ra "đi tiếp", và khi đó cho cả bốn run. Mỗi model thêm khoảng 13 giờ (11,4 giờ lô mức 1–2, 1,7 giờ mức 0), bốn làn song song: xong khoảng T0 + 29 giờ. Ba làn Colab thêm khoảng 3 × 14 × 1,94 ≈ 82 CU (ước lượng). Chạy thêm sau E1, E3, F chỉ để thu hẹp khoảng của (b) thì cần `Decision`.

**Ngân sách** (CU Colab, ước lượng; giá 0,0999 USD mỗi CU):

| Khoản | Ước lượng | Cap | Căn cứ |
|---|---|---|---|
| Stage 1 của W2 (sổ DA-30) | 2,5 | 4 | `tray-ego-b.yaml` |
| Train bốn run trên A100 | 4 × 57 = 228 | 4 × 70 = 280 | 8,45 giờ × 6,73 CU/giờ (`RATES` của `cu_watch.py`). Cap là lưới an toàn, xem 19.8 |
| Serve ba làn Colab L4, giai đoạn 1 ở 40k và 60k | 3 × 19 = 57 | 3 × 22 = 66 | mỗi làn khoảng 2 × 4,5 giờ eval + 0,8 giờ setup và nạp, 1,94 CU/giờ |
| **Tổng** | **khoảng 288** | **350** | |

- **Số dư cần có.** Stage 1 chạy trong đợt riêng trước: cần ít nhất 14 + 4 = 18 CU. Đợt train lúc launch cần ít nhất 14 + 280 = 294 CU; khi ba phiên serve nhập vào cần 14 + 280 + 66 = 360 CU, để không phiên nào chạm sàn kể cả khi mọi cap tiêu hết.
- **Số dư 500,00 CU của tài khoản mới đủ**: 360 ≤ 500. Hết đợt còn khoảng 500 − 288 ≈ 212 CU theo ước lượng, ít nhất 500 − 350 = 150 nếu mọi cap tiêu hết. Vẫn đủ chạy lại một run 60k ở cap (cần 14 + 70 = 84), hoặc giai đoạn 2 trên ba làn Colab (khoảng 82), nhưng không đủ cả hai khi mọi cap đã tiêu hết.
- Dòng `estimated` trong [sổ chi phí](../g0/ledger/DA-34.csv), ghi trước mọi lượt chạy: bốn dòng train, tám dòng eval (40k và 60k của mỗi run), ba dòng serve.

### 19.6 Gói bằng chứng (chuẩn bị trước, điền bằng một lệnh)

[`evidence`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/evidence.py) dựng cả gói từ những gì đã có. Phần nào chưa có thì ghi rõ còn thiếu gì, nên cùng một lệnh chạy được từ trước checkpoint đầu tới sau rollout cuối. Chạy trên `rtx3060`, nơi có output eval. Output ở `fwdata/` (không commit):

```bash
EV=~/denso-da34-pool/fwdata/tray/eval
python -m flywheel_psi0.tray.evidence configs/runplans/tray/he-tray-pair60k.yaml \
    --set ~/denso-da34-pool/fwdata/tray/eval-sets/rp_a04c14e79dfd-2e57f60 \
    --eval B_ALL@40000=$EV/eval-b_all-40k --eval C_ALL@40000=$EV/eval-c_all-40k \
    --eval B_ALL@60000=$EV/eval-b_all-60k --eval C_ALL@60000=$EV/eval-c_all-60k \
    --eval B_70@40000=$EV/eval-b_70-40k --eval C_70@40000=$EV/eval-c_70-40k \
    --eval B_70@60000=$EV/eval-b_70-60k --eval C_70@60000=$EV/eval-c_70-60k \
    --train B_ALL=<job dir từ Drive> --train C_ALL=<job dir> \
    --train B_70=<job dir> --train C_70=<job dir> \
    --out fwdata/tray/evidence/<run_plan_id>
```

| Phần | Lấy từ | Ghi chú |
|---|---|---|
| Nguồn gốc | plan và lock: `run_plan_id`, ghim code và psi-model, VLM và dữ liệu của từng nhánh (sha256 stage 1 hay của release; ALL hay S70), release và stats của cut, ghim của tập con, `rules_sha256`; commit của repo; `result.json` của từng job | |
| Thành công, Wilson 95 % | `eval_results` (`summarize`) | Luật (b): mức 1–2 gộp so với 80 %, mức 1 và mức 2 riêng so với 70 %. Mỗi run trên phạm vi rộng nhất nó đã chạy đủ: giai đoạn 1 khi đủ 6 lô, đủ 240 khi đủ 27 lô; thiếu thì ghi số rollout đã xong và không đọc run đó. Đợt hai chạy chậm không giữ lại số của đợt một |
| Ghép cặp, McNemar | `paired_diff`, `stage1_outcome`, trên mỗi so sánh của `comparisons` | (a′), (f), (g), (h), mỗi so sánh trên phạm vi rộng nhất cả hai run đã chạy đủ. Đọc: CI so với 0, hay với (f), (g) cận dưới so với −0,10. E1, E3, F hay đi tiếp chỉ cho (a′) ở checkpoint số chính; khi đã đủ 240 mà giai đoạn 1 đã dừng, luật 1–3 trên 240 chỉ để mô tả. Ở checkpoint số chính, gói ghi câu "egocentric bù phần demo bị cắt" chỉ khi (f) không kém và cận dưới của (a′) > 0, và ghi rõ khi (g) không kém |
| Lỗi theo nhãn và theo bước | nhãn `failure` và `scorer_steps` | Tỉ lệ qua từng bước trong 7 bước của bộ chấm |
| Thành công nới | `place_error` (`rows_for`, `tolerance_curve`) | Luật (c), luôn ghi "nới". Cần `flywheel_simple` để dựng pose đích; `--no-relaxed` bỏ qua phần này |
| Loss | `metrics.jsonl` của từng job | `loss.csv`, `loss.svg`; train lấy trung vị mỗi 500 bước, val như log |
| Video | `data/evals/…/episode_<i>/head_stereo_left_*.mp4` của SIMPLE | Mỗi run vài lượt thành công, rồi mỗi nhãn lỗi một lượt trước khi lặp nhãn (`--videos`) |
| Sổ chi phí | dòng của bốn run trong `DA-34.csv` | Ước lượng và thực đo |

- Mỗi checkpoint có nhãn của luật (e): "số chính" hay "đọc sớm, 40k". Đầu gói ghi các giới hạn của 19.2.
- Kết quả eval đọc qua plan của `eval_of` (bản 2): `pairplan check` giữ eval, stats và tập điều kiện của bốn run trùng bản 2, và `eval_results` đọc kiểu plan đó.
- **Chạy thử trên số thật** (11/11, trên bản hai run của gói; bản sao output eval C và C+ kéo từ `rtx3060` về laptop, chỉ đọc). C+ đóng vai `B_ALL`, C đóng vai `C_ALL`, cả hai ở 60k. Kết quả: C 20/240, `L-PLACE-POSE` 131/240, đúng mốc 16.6. Giai đoạn 1 ra F, như lần kiểm công cụ ở 18.5; luật 3 trên 240 chỉ để mô tả. Video và pose đích tìm đúng. Đây là kiểm công cụ, không phải kết quả của cặp.

### 19.7 Việc còn lại

- **W1, W2:** đã ghim hết (19.3, 11/11/2026).
- **6.2:** Hiếu duyệt khối 19.2 mới cho bốn run (nhãn ngoài khối, không đổi sha256); plan bốn run song song trên A100; `Decision` nháp; bỏ `draft`, `pairplan freeze`.
- **6.3:** mã và runbook cho **cả bốn** nhánh đã có (19.9), chưa chạy.
  - Code: `pair_cut` dựng S70 từ ALL theo seed của từng episode, giữ stats của ALL, và kiểm dữ liệu; `colab_train --branch B_ALL|C_ALL|B_70|C_70` lấy dữ liệu từ Drive; `colab_serve` cho làn 2–4.
  - Làm lúc launch: dựng S70 trên `rtx3060` và đưa hai tar lên Drive (19.9 A, B); PR đặt `PAIR_FROZEN` sau khi plan đóng băng.
- **CUDA trên VM Colab (11/11/2026).** Ảnh VM hôm đó chỉ có CUDA 13.0 (không có `nvcc` trong PATH), còn torch của Ψ₀ là 2.7.0+cu126. Stage 1 của DA-30 (DeepSpeed ZeRO-3) hỏng pre-flight hai lần (`CUDAMismatchException`, rồi "Ninja is required"), và chạy được sau khi cài bộ CUDA 12.6 (`cuda-nvcc-12-6`, `cuda-cudart-dev-12-6`, `libcurand-dev-12-6`, `libcublas-dev-12-6`), `pip install ninja`, và đặt `CUDA_HOME=/usr/local/cuda-12.6`.
  - **Stage 3 không build extension nào**, nên bốn VM A100 không cần các bước đó. Căn cứ là mã Ψ₀ ở `cda3fdf`: stage 3 chạy dưới `torchrun` với `train.data_parallel: ddp` và `torch.optim.AdamW`; plugin DeepSpeed chỉ được tạo khi `data_parallel` là `deepspeed`; `src/psi` không import DeepSpeed, triton hay `cpp_extension`; flash-attn là wheel cu12 dựng sẵn. Chưa chạy thử trên ảnh CUDA 13.0: đây là kết luận từ mã.
  - `colab_train setup` kiểm điều này trên recipe **trước mọi bước cài hay tải** (`extension_builds`) và ghi `cuda_ops_built` vào report. Recipe nào build op (DeepSpeed) thì bị từ chối, trừ khi `CUDA_HOME` là bộ 12.6 có `nvcc` và `ninja` có trong PATH (`toolchain_problems`); thông điệp lỗi ghi đúng các lệnh sửa ở trên. Mã 6.3 cho plan bốn run phải giữ kiểm này.
- **6.4:** bốn run stage 3 (Hiếu launch), dòng thực đo.
- **6.5:** eval giai đoạn 1 ở 40k và 60k, đọc theo 19.2; chạy `evidence` sau mỗi phần kết quả.
- **PR #186** (ngoài phạm vi story, **đã merge** 11/11/2026, `465e29b5`, và đã nhập vào nhánh của #181): `he1_fetch.py` và `he1_colab.py` nhận `--total-steps` và `--gpu`, để `follow --stop-when-done` tự dừng phiên 60k trên A100 (19.8).

### 19.8 Không để phiên treo tốn CU (Hiếu 11/11/2026) [Đề xuất]

Yêu cầu của Hiếu: không để phiên nào chạy không mà vẫn tính CU. `cu_watch.py` chỉ dừng phiên ở cap, ở sàn, hoặc khi nhận tín hiệu; nó **không** dừng khi train xong. Trên A100 (6,73 CU/giờ), một run xong sớm hơn cap 2 giờ là khoảng 13 CU mất không. Vì vậy mỗi phiên phải dừng ngay khi việc của nó xong hoặc hỏng, và cap chỉ là lưới cuối.

**Cap 70 là lưới an toàn, không phải số chi** (cap 70 từ plan `rp_d44e3e6262b4`; nay bốn run, trần 280, plan `rp_e2fb9f62c223`; phiên điều phối 11/11/2026). Không tốn CU khi phiên chạy không: vòng fetch bên dưới dừng phiên ngay khi `ckpt_60000` đã khớp sha256 trên laptop, nên mỗi run tiêu khoảng 57 CU (ước lượng 19.5) dù cap là bao nhiêu.

Cap còn đặt mức dừng sớm của `follow`. Ở bước 2 200, `follow` dự báo CU tới lúc `ckpt_60000` về laptop và dừng phiên nếu vượt mức dừng của cap. Ngưỡng tính bằng `projected_cu` và `stop_line` của PR #186, với s/bước như `metrics.jsonl` đo (cửa sổ tính cả val):

| Cap mỗi run | Dừng sớm khi s/bước trên (pull 11 MB/s) | (pull 6 MB/s) |
|---|---|---|
| 61 (bản trước, sát ước lượng) | 0,509 | 0,501 |
| **70** | **0,589** | **0,582** |

Tốc độ khả dĩ là khoảng 0,505 s/bước. Trên L4, run C đủ chậm hơn số đo ngắn khoảng 2 % (0,724 so với 0,71); áp cùng tỉ lệ cho A100 được 0,47 × 1,02 = 0,48, cộng khoảng 0,025 cho val. Với cap 61, con số này nằm ngay ở mức dừng, nên cả hai run có thể bị dừng oan ở bước 2 200 và lỡ hạn 12/11. Cap 70 để dư khoảng 15 % trên tốc độ đó. Lúc launch cần 14 + 4 × 70 = 294 CU, vẫn dưới số dư 500.

**Dừng khi xong.** Bên cạnh mỗi run, từ lúc launch, chạy một vòng fetch trên laptop:

```
python3 scripts/he/he1_fetch.py follow --session da34-b-all --registry "$R" \
    --dest fwdata/tray/pair60k/B_ALL --remote-work /content/da34 --every 600 \
    --stop-when-done --total-steps 60000 --gpu A100   # hai cờ cuối: PR #186 (đã merge, 465e29b5)
```

Ba run còn lại dùng lệnh giống hệt, mỗi run một vòng fetch: `da34-c-all` với `C_ALL`, `da34-b-70` với `B_70`, `da34-c-70` với `C_70`. Với hai đợt, vòng fetch của `B_70`, `C_70` chạy từ lúc đợt hai launch.
- Mỗi lượt, vòng fetch tải checkpoint mới nhất đã lưu xong và kiểm sha256 với VM. Checkpoint cũ không bị xóa trên laptop, nên `ckpt_40000` của luật (e) vẫn còn đó.
- Khi train xong và `ckpt_60000` đã khớp sha256, nó dừng đúng phiên đó. Lần dừng được xác nhận: `colab stop` tối đa ba lần, tới khi hai lần liệt kê liên tiếp không còn phiên, sau đó SIGTERM tới watcher của phiên.
- Từ bước 58 000 trở đi, nó pull mỗi 60 s, nên phiên dừng khoảng vài phút sau checkpoint cuối.

**Dừng khi hỏng sớm.** Cùng vòng fetch đó:
- Train crash (`stage` ghi `failed`): tải checkpoint đã có, rồi dừng phiên (mã 5).
- Từ bước 2 200, nếu dự báo CU tới lúc `ckpt_60000` về laptop vượt mức dừng của watcher thì dừng phiên trước checkpoint đầu (mã 3). Sau checkpoint đầu thì chỉ báo ALERT.
- Không dự báo được (không có số đo từ watcher, không có s/bước) thì báo ALERT, không dừng.

**Dự phòng: dừng tay khi vòng fetch không chạy.** Chỉ dùng khi vòng fetch đã thoát với mã khác 0 mà phiên còn trong `colab sessions`, hoặc khi không chạy được vòng fetch. Khi đó người trực phải tự dừng phiên trong các trường hợp sau:

| Điều kiện kiểm | Việc |
|---|---|
| `fwdata/tray/pair60k/<run>/fetched.json` có `"checkpoint": "ckpt_60000"`, `"bad_or_missing": []` và `"train": "done"`, và `fetched.json` của lượt có `ckpt_40000` cũng sạch như vậy | `colab stop <phiên>` ngay |
| Từ bước 2 200, s/bước trung bình đọc từ `metrics.jsonl` (cửa sổ tính cả val, như `follow` đo) trên **0,58** | Dừng ngay. Ở tốc độ đó, 60 000 bước cộng setup, val, lưu và pull không còn vừa cap 70 |
| Train crash, hoặc không có bước mới trong 15 phút | Dừng ngay, sau khi lấy checkpoint đã có |

Ngưỡng 0,58 là mức dừng sớm của `follow` ở cap 70 khi pull chậm nhất (6 MB/s), theo bảng trên.

**Các phiên serve của làn 2–4**: mỗi phiên dừng ngay khi lô eval cuối của checkpoint cuối của model đó đã ghi xong kết quả trên `rtx3060`. Không chờ cap 22.

**Bước cuối của runbook.** `colab sessions` không còn phiên nào (lặp lại ít nhất hai lần cách nhau một phút; hai lần liệt kê liên tiếp mới tính). Guard của đợt thoát mã 0. Dòng thực đo vào sổ chi phí theo `colab usage`.

**PR #186** (`chore-he1-fetch-steps`, phương án (a) của phiên điều phối; đã merge 11/11/2026, `465e29b5`):
- `he1_fetch.py` nhận `--total-steps` và `--gpu`; `he1_colab.py stage` nhận `--total-steps`.
- Rate lấy từ `RATES` của `cu_watch.py`; GPU không có trong đó bị từ chối, không đoán.
- Mặc định 40 000 và L4 giữ nguyên, nên DA-26 không đổi.
- Test: với job 60k xong ở 60 000, `follow --stop-when-done --total-steps 60000 --gpu A100` tải và kiểm `ckpt_60000`, dừng phiên rồi thoát 0; không có hai cờ thì thoát 5.
- `cu_watch.py` không đổi.

### 19.9 Runbook bốn run (nhiệm vụ con 6.3) [Đề xuất]

Mã đã có, **chưa chạy trên Colab**. Không bước nào dưới đây chạy trước khi Hiếu cho launch.
- [`pair_cut`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/pair_cut.py): dựng S70 từ ALL, kiểm dữ liệu với plan, đóng gói lên Drive.
- `colab_train --branch B_ALL|C_ALL|B_70|C_70`: train.
- [`colab_serve`](../../packages/flywheel-psi0/src/flywheel_psi0/tray/colab_serve.py): làn eval 2–4.

**Điều kiện trước launch.**
1. Hiếu duyệt 19.2 và ghi `Decision` (6.2). Plan bỏ `draft`, `pairplan freeze` ghi `he-tray-pair60k.lock.json`.
2. Một PR nhỏ đặt `PAIR_FROZEN` trong `colab_train.py` bằng id đã đóng băng, như `B_FROZEN` của B. Trước khi có PR đó, cả bốn nhánh đều từ chối: `colab_train check --branch B_70` trên plan nháp báo "draft", "not frozen", "PAIR_FROZEN is unset".
3. Đợt stage 1 đã đóng: guard của nó đã thoát.
4. Số dư ít nhất 294 CU, hoặc 360 CU khi ba phiên serve vào cùng đợt (19.5).
5. Hai tar đã lên Drive (bước B).

**Ngày 11/11/2026** (nhiệm vụ con 6.2):
- Điều kiện 1 và 2 xong. Hiếu duyệt 19.2. `Decision` nháp ở `he-tray-pair60k.decision.json`. Plan bỏ `draft`, chọn 60k. `pairplan freeze` ghi `he-tray-pair60k.lock.json` với id `rp_e2fb9f62c223`, trùng id nháp vì `status` không vào id. `PAIR_FROZEN` đặt bằng id này.
- Điều kiện 3 xong: guard của đợt stage 1 đã thoát. Phiên `da30-stage1-b` đã được trả máy; tài khoản không còn phiên nào.
- Điều kiện 5 xong: phiên điều phối đưa bốn file lên `MyDrive/denso/da34/cuts/` qua một máy Colab CPU (0,08 CU/giờ, đẩy qua ssh khoảng 21 MB/s). Đọc lại từ Drive ra sha256 `bea55b14…` (ALL) và `f87bfecb…` (S70), khớp bảng ở bước A.
- Còn điều kiện 4 (số dư), kiểm lúc launch.

**Dữ liệu theo seed của chính episode.** Một episode vào S70 khi seed của nó, lấy từ `environment_config.flywheel.seed` ở dòng của nó trong `meta/episodes.jsonl` của ALL, nằm trong danh sách đã ghim của phần nó.

File tập demo liệt kê `seeds` và `episode_indices`, mỗi danh sách tự sắp xếp riêng. Ghép hai danh sách theo vị trí sẽ ra seed sai: episode 0 của cut có chỉ số nguồn 1 và seed 1014, không phải 1001. Đếm frame theo cách ghép đó ra 604 317, không phải 603 915. `pair_cut` không bao giờ ghép hai danh sách này.

Trên dữ liệu thật (sao `meta/` của ALL từ `rtx3060`, chỉ đọc):
- `cut_problems(ALL)` rỗng: seed của từng phần khớp tập của nó, khớp tổng, khớp stats `1c745091…`.
- Lựa chọn S70 ra 301 + 124 episode, 427 758 + 176 157 = 603 915 frame, đúng pin.

Stats của S70 là file của ALL chép nguyên byte, không tính lại. `cut_problems` kiểm sha256 này cho cả hai cỡ dữ liệu.

**A. `rtx3060`: dựng S70, kiểm, đóng gói** (0 CU, chạy từ bản `git archive` của master có `PAIR_FROZEN`, như 17.6). Cần khoảng 13 GB đĩa; ngày 11/11 máy còn 84 GB.

```bash
cd $D && export PYTHONPATH=$(ls -d $PWD/packages/*/src | paste -sd:)
PY=~/denso-da34-pool/.venv/bin/python
CUT=~/denso-da34-pool/fwdata/cut-all-zone1
E=G1WholebodyTrayTransferTeleop-v0
P=configs/runplans/tray/he-tray-pair60k.yaml
$PY -m flywheel_psi0.tray.pairplan check $P --launch || { echo "plan does not hold: do not launch"; exit 1; }
$PY -m flywheel_psi0.tray.pair_cut check --plan $P --name ALL --data $CUT/ALL/$E
$PY -m flywheel_psi0.tray.pair_cut subset --plan $P --cut $CUT/ALL/$E --subset S70 --out $CUT/S70/$E
$PY -m flywheel_psi0.tray.pair_cut check --plan $P --name S70 --data $CUT/S70/$E   # "S70: dataset and plan hold"
mkdir -p $CUT/work/sets $CUT/drive && ln -sfn $CUT/ALL $CUT/work/sets/ALL && ln -sfn $CUT/S70 $CUT/work/sets/S70
for B in B_ALL C_ALL B_70 C_70; do $PY -m flywheel_psi0.tray.colab_train check --branch $B --work $CUT/work || exit 1; done
$PY -m flywheel_psi0.tray.pair_cut pack --plan $P --data $CUT/ALL/$E --name ALL --out $CUT/drive/ALL.tar
$PY -m flywheel_psi0.tray.pair_cut pack --plan $P --data $CUT/S70/$E --name S70 --out $CUT/drive/S70.tar
```

`subset` không ghi đè thư mục đã có. Lệnh này kiểm lại S70 sau khi ghi, gồm cả cách đánh số `index` của LeRobot v2.1. `pack` từ chối nếu dữ liệu không qua `check`. Tar là bản tái lập được: cùng file thì ra cùng byte. File `.json` đi kèm ghi số byte và sha256.

**Tar phải ra đúng các giá trị sau.** Phiên điều phối chạy thử bước A ngày 11/11/2026 trên laptop, từ bản sao cut ALL đã kiểm khớp `cut-all-zone1.sha256` (1 226 file), mã ở `8462c287`. Đóng gói S70 hai lần ra cùng sha256.

| Tar | Byte | sha256 |
|---|---|---|
| `ALL.tar` | 5 298 288 640 | `bea55b14bffa5c72d96fba0fb3439b7d0ddb90e5636eaf6fb798a5357608ccc8` |
| `S70.tar` | 3 707 822 080 | `f87bfecb25c6cdf32bb72ccbaa13e9212639ae18617947098c9edc79c27b864b` |

Ai đóng gói lại từ master, trên laptop hay trên `rtx3060`, phải ra đúng hai giá trị này. Ra sha256 khác nghĩa là đầu vào khác hoặc đường mã khác: **dừng**, không đưa lên Drive, báo phiên điều phối.

Lần chạy thử đó còn so từng episode của S70 với episode nguồn trong ALL, độc lập với `pair_cut`. Cả 425 episode khớp mọi cột trừ `episode_index` và `index`; `index` chạy liền 0..603 914; video trùng từng byte; `stats_psi0.json` và `stats.json` là byte của ALL. `subset` mất 33 s.

**Chạy bước A trên laptop cũng được.** Kéo cut ALL về, kiểm với `cut-all-zone1.sha256`, rồi chạy cùng các lệnh với `CUT` trỏ vào bản sao đó và `PY` là Python của workspace. Như vậy bước B không phải kéo 9 GB tar từ `rtx3060`.

**B. Đưa hai tar lên Drive** (0 CU). Nếu bước A chạy trên `rtx3060`, laptop kéo `drive/` về. Dù chạy ở đâu, kiểm sha256 của tar với `.json` và với bảng trên. Sau đó Hiếu đưa bốn file lên `MyDrive/denso/da34/cuts/` bằng trình duyệt, đúng tên: `ALL.tar`, `ALL.tar.json`, `S70.tar`, `S70.tar.json`. Khoảng 9 GB.

```bash
rsync -a --partial-dir=.rsync-partial rtx3060:denso-da34-pool/fwdata/cut-all-zone1/drive/ fwdata/tray/pair-cuts/
for n in ALL S70; do python3 -c "import hashlib,json,sys; m=json.load(open(sys.argv[1]+'.json')); h=hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest(); print(sys.argv[1], 'OK' if h==m['sha256'] else 'DIFFERS')" fwdata/tray/pair-cuts/$n.tar; done
rsync -a rtx3060:denso-da34-pool/fwdata/cut-all-zone1/ALL/G1WholebodyTrayTransferTeleop-v0/meta/stats_psi0.json fwdata/tray/pair-cuts/ALL-stats_psi0.json
```

Trên VM, `setup` so cỡ file trên Drive với `.json` **trước** khi chép, rồi sha256 sau khi chép, giải nén an toàn và chạy `cut_problems`. Tất cả trước mọi bước cài. Drive chưa đồng bộ xong thì cỡ lệch, và `setup` dừng mà chưa tốn gì ngoài vài giây A100.

**C. Laptop: một đợt `cu_watch`, guard và bốn watcher** (thư mục gốc là bản checkout master, `PATH` có `colab` như 17.6). Hàm `ready` và `vm` như mục 12. Thứ tự launch: `B_ALL`, `C_ALL`, `B_70`, `C_70`.

```bash
colab sessions; colab usage   # số dư >= 294 (360 nếu serve vào cùng đợt)
R=fwdata/colab/batch-$(date +%Y%m%d-%H%M%S); mkdir -p $R && git rev-parse HEAD > $R/master.sha
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py guard --registry "$0" --floor 14 --log "$0/guard.jsonl"; echo "exit $?"' $R < /dev/null > $R/guard.out 2>&1 &
watch_run() {  # $1 session, $2 branch
  nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name "$1" --gpu A100 --cap 70 --floor 14 --persist "python3 scripts/he/he1_fetch.py once --session $1 --registry $0 --dest fwdata/tray/pair60k/$2 --remote-work /content/da34 --total-steps 60000 --gpu A100" --log "$0/$1.jsonl"; echo "exit $?"' $R $1 $2 < /dev/null > $R/$1.out 2>&1 &
}
watch_run da34-b-all B_ALL; watch_run da34-c-all C_ALL; watch_run da34-b-70 B_70; watch_run da34-c-70 C_70
```

**Đường lùi hai đợt** (`schedule.waves`). Watcher của `da34-b-70` hay `da34-c-70` thoát mã 6 nghĩa là Colab từ chối, không mở phiên nào và không dừng phiên khác. Khi đó:
- dừng phiên còn lại của đợt hai nếu nó đã mở (`colab stop`), cùng watcher của nó;
- chạy đợt một như dưới đây;
- khi `colab sessions` không còn `da34-b-all` và `da34-c-all`, gọi lại `watch_run` cho `B_70`, `C_70` trong cùng registry `R`, rồi làm các bước D cho hai phiên đó.

Không mở đợt hai bằng registry mới khi guard cũ còn chạy: guard dừng mọi phiên không có watcher đăng ký.

**D. Mỗi phiên train** (lặp cho từng cặp `S`/`B`; mỗi bước chỉ chạy khi bước trước xong):

```bash
S=da34-b-all; B=B_ALL
VMPP=fw/packages/flywheel-psi0/src:fw/packages/flywheel-contracts/src
ready $S || { colab stop -s $S; echo "$S: not ready, session stopped"; }
git archive --format=tar.gz HEAD | vm $S 'mkdir -p /content/da34/fw && tar -xz -C /content/da34/fw'
colab drivemount -s $S /content/drive || colab drivemount -s $S /content/drive
vm $S 'mountpoint -q /content/drive && ls -l /content/drive/MyDrive/denso/da34/cuts/'
vm $S "cd /content/da34; nohup setsid bash -c 'PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_train setup --branch $B; echo setup exit \$?' > setup.log 2>&1 < /dev/null &"
vm $S 'tail -2 /content/da34/setup.log'   # chờ "setup exit 0"
vm $S "cd /content/da34; nohup setsid bash -c 'echo \$\$ > train.pid; PYTHONPATH=$VMPP Psi0/.venv-psi/bin/python -m flywheel_psi0.tray.colab_train train --branch $B; echo train exit \$?' > train.log 2>&1 < /dev/null &"
vm $S "cd /content/da34; nohup setsid bash -c 'python3 fw/scripts/he/he1_colab.py persist --work /content/da34 --to /content/drive/MyDrive/denso/da34 --watch 600 --pid \$(cat train.pid); echo persist exit \$?' > persist.log 2>&1 < /dev/null &"
nohup setsid bash -c 'python3 scripts/he/he1_fetch.py follow --session "$1" --registry "$0" --dest fwdata/tray/pair60k/"$2" --remote-work /content/da34 --every 600 --stop-when-done --total-steps 60000 --gpu A100; echo "exit $?"' $R $S $B < /dev/null > $R/$S.fetch.log 2>&1 &
```

- **Đồng ý Drive trên mỗi VM**, đo trên A100 của DA-30 ngày 11/11/2026: VM mới nào cũng hỏi. Hiếu bấm trong 120 s; lệnh mount trong VM hết giờ sau 120 s. Bấm muộn thì `colab drivemount` chạy lại đúng một lần (vế sau `||`), lần đó mount được mà không hỏi lại. Drive phải mount **trước** `setup` vì dữ liệu nằm trên Drive. B còn lấy VLM stage 1 từ `denso/da30/da30-tray-ego-b/vlm`.
- `setup` ghi `data_fetched` (cỡ, sha256, số giây chép) và `cuda_ops_built: false` vào `report.json`. Stage 3 không build extension (19.7), nên không cần bộ CUDA 12.6.
- `persist --watch 600 --pid` chép mọi `ckpt_<step>` đã lưu xong lên `MyDrive/denso/da34/<job>/`. Làn serve lấy checkpoint từ chỗ này.
- Vòng fetch tự dừng phiên khi `ckpt_60000` đã khớp sha256 trên laptop, hoặc khi hỏng sớm (19.8). Job trên VM tên `da34-t6-ft-b-all-s0`, `da34-t6-ft-c-all-s0`, `da34-t6-ft-b-70-s0`, `da34-t6-ft-c-70-s0`; sổ chi phí ghi `job_da34_ft_<nhánh>`.

**E. Làn eval** (giai đoạn 1 theo 19.2; mỗi checkpoint đọc 40k rồi 60k).

`colab_serve expect` chạy trên laptop cho **cả bốn** model, cả làn 1. Nó kiểm hai điều:
- file stats đưa vào là stats của ALL (sha256 bằng pin);
- bounds trong `run_config.json` của run đúng là stats đó, bỏ qua phần đệm số 0 của Ψ₀.

Run nào chuẩn hóa bằng stats riêng (ví dụ S70 đã tính lại stats) thì không được serve. Đã thử trên một run thật: `run_config.json` của C+ khớp stats của bản cắt C+, và bị từ chối khi so với stats của ALL.

```bash
export PYTHONPATH=$(ls -d $PWD/packages/*/src | paste -sd:)
python3 -m flywheel_psi0.tray.colab_serve expect --runs fwdata/tray/pair60k/$B --branch $B --step 40000 \
    --stats fwdata/tray/pair-cuts/ALL-stats_psi0.json   # ghi fwdata/tray/pair60k/$B/<job>/expected-40000.json
```

- **Làn 1, `B_ALL`, trên `rtx3060`.** Như B ở mục 18: chép `serve-b.sh` và `launch-eval-b.sh` thành `serve-b-all.sh` và `launch-eval-b-all.sh`. Job là `da34-t6-ft-b-all-s0`, checkpoint từ `fwdata/tray/pair60k/B_ALL`. Ba điều chặn giữ nguyên. Điều thứ ba so bounds với `stats_psi0.json` của ALL.
- **Làn 2–4, `B_70`, `C_70`, `C_ALL`, mỗi làn một phiên Colab L4** trong **cùng** registry `R`, cap 22, sàn 14, tên `da34-serve-b-70`, `da34-serve-c-70`, `da34-serve-c-all`. Mở lúc khoảng T0 + 5,3 giờ (19.5). Bảy phiên cùng lúc **chưa thử**: phiên nào bị từ chối (mã 6) thì mở lại sau khi các phiên train đóng.

```bash
S=da34-serve-c-70; B=C_70; J=da34-t6-ft-c-70-s0; STEP=40000; LP=22287; RP=22197   # cổng: bảng dưới
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name "$1" --gpu L4 --cap 22 --floor 14 --log "$0/$1.jsonl"; echo "exit $?"' $R $S < /dev/null > $R/$S.out 2>&1 &
ready $S || { colab stop -s $S; echo "$S: not ready, session stopped"; }
git archive --format=tar.gz HEAD | vm $S 'mkdir -p /content/da34s/fw && tar -xz -C /content/da34s/fw'
colab drivemount -s $S /content/drive || colab drivemount -s $S /content/drive
vm $S "cd /content/da34s; nohup setsid bash -c 'python3 fw/scripts/he/he1_colab.py serve-setup --work /content/da34s; echo serve-setup exit \$?' > serve-setup.log 2>&1 < /dev/null &"
vm $S 'tail -2 /content/da34s/serve-setup.log'   # chờ "serve-setup exit 0"
vm $S "cat > /content/da34s/expected-$STEP.json" < fwdata/tray/pair60k/$B/$J/expected-$STEP.json
vm $S "cd /content/da34s && PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_serve fetch --expected expected-$STEP.json"
vm $S "cd /content/da34s; nohup setsid bash -c 'PYTHONPATH=$VMPP python3 -m flywheel_psi0.tray.colab_serve serve --expected expected-$STEP.json; echo serve exit \$?' > serve-$STEP.log 2>&1 < /dev/null &"
vm $S "tail -3 /content/da34s/serve-$STEP.log"   # chờ dòng JSON có "pid", rồi "serve exit 0"
nohup ssh -N -o ProxyCommand="colab ssh --proxy-mode -s $S" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ServerAliveInterval=15 -L $LP:127.0.0.1:22085 root@colab > $R/$S.fwd.log 2>&1 &
nohup ssh -N -o ServerAliveInterval=15 -R $RP:127.0.0.1:$LP rtx3060 > $R/$S.rfwd.log 2>&1 &
ssh rtx3060 "curl -s 127.0.0.1:$RP/health"   # "ok"
```

Rồi trên `rtx3060`, `launch-eval-<làn>.sh` chép từ `launch-eval-b.sh`, với `eval_batch --server 127.0.0.1:$RP --listen <cổng proxy của làn>` và thư mục output riêng. Mỗi làn kiểm thứ tự bằng `--dry-run --max-chunks 6` như mục 18.

| Làn | Model | Server (máy, cổng) | Cổng laptop `LP` | Cổng trên `rtx3060` `RP` | `--listen` [Đề xuất] |
|---|---|---|---|---|---|
| 1 | `B_ALL` | `rtx3060`, 22185 | — | 22185 | 22186 |
| 2 | `B_70` | Colab L4, 22085 | 22285 | 22195 | 22196 |
| 3 | `C_70` | Colab L4, 22085 | 22287 | 22197 | 22198 |
| 4 | `C_ALL` | Colab L4, 22085 | 22289 | 22199 | 22200 |

**Chuyển từ 40k sang 60k trên cùng phiên serve.**
1. Khi lô cuối giai đoạn 1 của 40k đã ghi xong, chạy `expect --step 60000` trên laptop sau khi `fetched.json` báo `ckpt_60000` sạch.
2. Gửi file mới lên VM, rồi `fetch`.
3. Dừng server 40k bằng `kill <pid>`, lấy pid ở `report.json` phase `serve_<nhánh>_40000`. `serve` từ chối khi cổng còn server trả lời.
4. Chạy `serve --expected expected-60000.json`.

Phiên serve dừng ngay khi lô cuối của 60k đã ghi kết quả (19.8).

**Chưa thử, phải theo dõi lần đầu.**
- Bốn A100 cùng lúc, và bảy phiên khi ba phiên serve vào.
- Đường Drive cho tar 5,3 GB: cỡ trên Drive phải khớp `.json` ngay khi VM thấy file.
- Bốn client trên `rtx3060` cùng lúc.
- Cổng `--listen` của từng làn; ghi ở bảng là đề xuất.

## 20. Nhiệm vụ 7: một vòng Failure → Data trên `C_70` (soạn 12/11/2026, chưa chạy) [Đề xuất]

_Hiếu 12/11/2026, qua phiên điều phối: "Có, soạn RunPlan", sau khi đọc giai đoạn 1 của bốn run 60k. Mục này viết và commit **trước** mọi rollout chẩn đoán, mọi lần sinh, train hay eval của vòng. Plan nháp: [`round-tray-c70.yaml`](../../configs/runplans/tray/round-tray-c70.yaml). Chưa có loader đọc plan này (20.10); không job nào chạy từ nó._

### 20.1 Vì sao, và vòng này đứng ở đâu trong PoC

Bốn run 60k đã có đủ hình của PoC ở spec mục 7.2, trừ nhánh C:

| Nhánh của spec 7.2 | Ở đây | Dữ liệu |
|---|---|---|
| A₀.₇, policy khởi đầu π₀ của C | `C_70` | S70: 425 episode |
| Bổ sung đều cùng ngân sách | `C_ALL` | S70 cộng 181 episode còn lại của ALL, chọn theo sha256 của seed, không theo lỗi |
| C | **`C70_R1`** (vòng này) | S70 cộng tối đa 181 episode do một vòng Failure → Data chọn trên lỗi của `C_70` |

- Ở task khay, mọi demo đều là episode planner (S1), nên "teleop" của spec đọc là S70.
- ALL không phải D\* đã đo (spec 7.1); đó là bản cắt đang có.
- Theo spec 7.3 luật 5, ngân sách thu dữ liệu của C là B_add. Mọi episode ở đây là S1 cùng đơn giá, nên B_add đếm bằng episode: **606 − 425 = 181**, đúng phần `C_ALL` có thêm so với S70.

Câu hỏi của vòng: **181 episode do Failure → Data chọn có giúp hơn 181 episode thêm đều không?** Đây là dạng của HT (C so với bổ sung đều, cùng ngân sách), ở mức sơ bộ: 1 seed train, trên dev, không holdout.

**Ba điều đã biết, ảnh hưởng thiết kế:**
- **Thêm đều không giúp.** Giai đoạn 1 của 19.2: (g) `C_70` − `C_ALL` +8,3 điểm %, CI 95 % −1,7 đến +18,3. Thêm 181 episode đều không làm `C_70` tốt lên.
- **Thành công gần như không gắn với điều kiện** (18.9). C và C+ cùng thành công ở đúng 1 trong 240 điều kiện; kỳ vọng ngẫu nhiên khoảng 0,75. Một rollout mỗi điều kiện vì vậy gần như tung đồng xu. Phép kiểm nào cần "chạy lại một điều kiện" phải chạy nhiều lượt.
- **Sinh S1 quanh điều kiện lỗi, như C+ làm, gần với rải đều** (17.2, 17.5). C+ ở giai đoạn 1 được 3 so với 7 của C, kết quả F. Vòng này dùng lại cách sinh đó (20.5), nên kỳ vọng không cao. Nếu lại ra F thì đó là bằng chứng loại can thiệp này không hợp với lỗi kỹ năng ở bước đặt, và là căn cứ cho dữ liệu sửa lỗi (correction) sau demo.

### 20.2 Đầu vào: lỗi của `C_70` (bước 1–3 của spec 6.1, đã chạy)

- Nguồn: giai đoạn 1 của `C_70` (60 điều kiện mức 1–2, `ckpt_60000`, một rollout mỗi điều kiện), lô `pair60k-C_70-60000-rp_a04c14e79dfd` trên `rtx3060`, `runs.jsonl` sha256 `9cc9cab0…`.
- Mỗi rollout một dòng trong [`round-c70-rollouts.jsonl`](../../configs/runplans/tray/round-c70-rollouts.jsonl), sha256 `aff514b5…`. Các trường:
  - mức, seed, thành công, nhãn lỗi;
  - bước hỏng đầu tiên: bước đầu tiên chưa qua trong chuỗi bước của bộ chấm;
  - độ lệch cuối tới đích (`place_error`);
  - `on_table_b`: tâm khay cuối nằm trên mặt bàn B, đáy cách mặt bàn ≤ 3 cm, nghiêng < 15°.
- 10 thành công, 50 lỗi. Gom cụm theo khóa (bước hỏng đầu tiên, nhãn lỗi, mức) của spec 6.3:

| Cụm | Bước hỏng đầu tiên | Nhãn | Mức | Số lỗi | Đi tiếp |
|---|---|---|---|---|---|
| c1 | `place` | `L-PLACE-POSE` | 1 | 14 | Bước 5–8 |
| c2 | `place` | `L-PLACE-POSE` | 2 | 12 | Bước 5–8 |
| c3 | `approach_a` | `L-TIMEOUT` | 1 | 4 | Kiểm H2 |
| c4 | `release_stand` | `L-TRAY-TILT` | 2 | 4 | Kiểm H3 |
| c5 | `place` | `L-TRAY-TILT` | 2 | 3 | Kiểm H3 |
| c6 | `approach_a` | `L-PLACE-POSE` | 2 | 3 | Kiểm H1 |
| c7 | `approach_a` | `L-PLACE-POSE` | 1 | 2 | Kiểm H1 |
| c8 | `approach_a` | `L-TIMEOUT` | 2 | 2 | Kiểm H2 |
| Lẻ | `place`, `release_stand`, `carry`, `approach_a` | `L-TRAY-TILT` 3, `L-TIMEOUT` 1, `L-PLACE-POSE` 1, `L-PART-DROP` 1 | 1–2 | 6 | Chỉ báo cáo |

8 trong 10 lượt `L-TRAY-TILT` kết thúc với khay nằm phẳng trên bàn B.

### 20.3 Bước 4: kiểm hệ thống và bộ chấm, trước mọi dữ liệu (0 CU)

Theo spec 6.4 và 6.9: hệ thống trước, dữ liệu sau. Cụm có chẩn đoán hệ thống thành phiếu sửa và không tiêu ngân sách dữ liệu. **Bộ chấm không đổi trong vòng này.** Đổi bộ chấm thì phép đo của `C_70` và `C_ALL` hết giá trị (spec 6.4), nên mọi sửa bộ chấm đi phiếu riêng cho DA-37.

| Kiểm | Cụm | Dấu hiệu | Cách kiểm | Chẩn đoán nếu đúng |
|---|---|---|---|---|
| H1: chuỗi bước ở `approach_a` | c6, c7 (5) và lượt `L-PART-DROP` | Khay đã sang và nằm trên bàn B, mà bước `approach_a` chưa bao giờ qua | `approach_a` cần cùng lúc: base trong `approach_zone` trước mép bàn A, và hai lòng bàn tay trong `r_reach` của tay cầm. Trace không có tư thế tay hay khay, nên chỉ đọc được từ nhãn và tư thế cuối | CHƯA RÕ (ngưỡng bộ chấm); phiếu cho DA-37. Nhãn lỗi cuối (`L-PLACE-POSE`) vẫn đúng, chỉ bước hỏng đầu tiên sai |
| H2: hết giờ ở `approach_a` | c3, c8 (6) | Khay cuối còn cách đích khoảng 2,2 m, tức chưa rời bàn A | Sai số bám lệnh thân trên và thân dưới (lệnh − đo) trong `steps.jsonl`, so với phân vị 99 trên 10 lượt thành công của `C_70`. Đây là τ_track **tạm**: spec lấy τ_track từ teleop thành công, mà task khay chưa có teleop. Xem thêm lệnh thân dưới: policy có ra lệnh đi không | Vượt τ_track: LỖI CONTROLLER, phiếu sửa. Không vượt, và policy không ra lệnh đi: lỗi của policy, sang bước 5–8 |
| H3: nghiêng lúc hạ và buông | c4, c5 và hai lượt lẻ | Khay đã chạm đúng đích (c4) hoặc đã tới bàn B, rồi bị gắn `L-TRAY-TILT`. Nhãn này chỉ ghi khi khay **không chạm bàn nào** mà nghiêng > 15° | Cần thời điểm lỗi và tiếp xúc của khay lúc lỗi; outcome và trace không ghi hai thứ này. Chạy lại không thay được, vì rollout trên EGL không lặp lại (13.2) | CHƯA RÕ (thiếu tín hiệu, spec 6.4 mục 1); đề xuất ghi `failure_t`, tiếp xúc và độ nghiêng lúc lỗi vào outcome (phiếu cho DA-38). Không tiêu ngân sách dữ liệu trong vòng này |
| Độ trễ, đồng bộ, camera | Mọi cụm | — | Eval chạy `timing: sync`: sim chờ server, nên độ trễ không đổi hành vi. Cây eval, cảnh `+zone1` và camera ghim như bốn run | Ghi "đạt", kèm lý do |

### 20.4 Bước 5–8 trên c1, c2 (và c3, c8 nếu H2 trả về policy)

Mỗi cụm R = 5 đại diện, chọn ngẫu nhiên với hạt giống `20261112` (spec 6.3). Tham số theo spec 6.15, không đổi.

| Bước | Làm gì | Chi phí |
|---|---|---|
| 5. Kiểm khả thi | planner-5 của SIMPLE chạy từ đúng điều kiện đầu của từng đại diện, trên `rtx3060`. Episode chỉ dùng để kiểm, **không** vào dữ liệu, vì dữ liệu không bao giờ sinh trên điều kiện dev (Q-33A) | 0 CU, vài phút CPU |
| 6. Khoanh vùng bằng reset | **Không làm được.** Nạp lại trạng thái SIMPLE ở đầu một bước là S1-06, đã cắt tới sau demo. Cụm ghi "chưa khoanh vùng" (spec 6.6), nên không có chẩn đoán TRẠNG THÁI ĐẦU XẤU | — |
| 7. Kiểm thị giác | Chạy lại mỗi đại diện với hình ảnh mức 0, **3 lượt** mỗi đại diện. Spec cho 1 lượt, nhưng 1 lượt gần như tung đồng xu ở task này (20.1). NHẬN THỨC khi ít nhất 2 trên 3 lượt thành công | 2 cụm × 5 × 3 = 30 rollout, khoảng 2,8 giờ trên một L4, khoảng 6 CU (ước lượng) |
| 8. Kiểm vùng phủ | Miền train là [min, max] từng tham số vật lý trên điều kiện của S70. Khoảng cách kNN (K = 5) tới điều kiện S70, theo cách đo của `flywheel_simple.tray.targets`; τ_cov là phân vị 95 leave-one-out trong S70 | 0 CU |

Dự đoán, chưa phải kết quả: c1 và c2 ra KỸ NĂNG YẾU (trong miền, gần dữ liệu train), như card của C ở 17.2.

### 20.5 Can thiệp và chọn theo ngân sách

| Chẩn đoán | Can thiệp theo spec 6.9 | Ở vòng này |
|---|---|---|
| KỸ NĂNG YẾU | Teleop correction ở bước k | **Không có.** Teleop khay chỉ có PICO, đội không có thiết bị. Correction do planner sinh từ trạng thái đã lưu cần S1-06. Kỹ sư ghi đè (spec 6.14) sang sinh S1 quanh điều kiện lỗi, ghi lý do vào card. Đây là chỗ lệch spec lớn nhất của vòng |
| THIẾU VÙNG PHỦ | Sinh S1 quanh điều kiện lỗi | Đúng như spec |
| TRẠNG THÁI ĐẦU XẤU | Dữ liệu phục hồi | Không xảy ra được (không có bước 6) |
| NHẬN THỨC, NGOÀI MIỀN, chẩn đoán hệ thống, CHƯA RÕ | Không tiêu ngân sách | Ghi và báo cáo |

**Sinh.** Giữ mọi thứ phần nhắm lỗi của ALL đã có:
- `generate.py --conditions` với `flywheel_simple.tray.targets`, cửa sổ seed train 100 000–199 999, planner-5, cảnh `+zone1`;
- QA phát lại, QA của DA-03, bộ lọc chất lượng ngày 3/11 (nghiêng ≤ 10°, xê dịch ≤ 20 mm).

Chỉ đổi điều kiện được nhắm tới. **Không thêm bộ lọc chặt hơn ở bước đặt.** Thêm bộ lọc thì hiệu với `C_ALL` gộp cả "dữ liệu tốt hơn" lẫn "nhắm theo lỗi".

**Lệch spec 7.3 luật 7.** Luật 7 cấm sinh với tham số của mức 1–2, nhưng phần nhắm lỗi của ALL (từ C+) đã sinh như vậy. Vòng này theo tiền lệ của ALL để `C_ALL` và `C70_R1` cùng phân bố sinh. Điều này cần `Decision`.

**Chọn theo ngân sách** (spec 6.10–6.11, prior Beta(1, 1)):
- Mọi đề xuất cùng loại, cùng đơn giá, nên g/c bằng nhau. Thứ tự là bước hỏng sớm hơn trước. Các cụm cùng bước gộp một bể, chia vòng tròn theo từng lỗi.
- Mỗi cụm xử lý tối đa L_t = 10 lỗi, chọn ngẫu nhiên với hạt giống `20261112`; 20 rollout đạt QA mỗi lỗi, trần 200 mỗi cụm. Tổng bị chặn ở B_add = 181.

Hai kịch bản, tính trước để thấy luật cho ra gì:

| Kịch bản | Cụm nhận dữ liệu | Phân bổ 181 episode |
|---|---|---|
| H2 ra lỗi hệ thống (hoặc chỉ c1, c2 vào nhánh dữ liệu) | c1, c2: 10 + 10 lỗi | Một bể 20 lỗi, khoảng 9 episode mỗi lỗi |
| H2 trả về policy, c3 và c8 ra chẩn đoán dữ liệu | c3 + c8 (6 lỗi, bước `approach_a`) trước, rồi c1, c2 | 6 × 20 = 120 cho c3, c8; 61 còn lại cho 20 lỗi của c1, c2 (khoảng 3 mỗi lỗi) |

Nếu sinh xong mà chưa đủ số đạt QA, sinh thêm một lô cho các lỗi còn thiếu, như bước (3) của 17.3. Sau lô đó thì dừng ở số đã có và báo cáo, không lấy thêm episode của S70 hay ALL để bù.

### 20.6 Train

| | **A. Train lại từ gốc, như bốn run [Đề xuất]** | B. Fine-tune tiếp từ `C_70` |
|---|---|---|
| Làm gì | VLM của C (cha `psi0-baseline-egodex-he`), dữ liệu S70 + tập nhắm lỗi, 60 000 bước, seed 0, recipe và stats ALL như bốn run | `ckpt_60000` của `C_70`, thêm khoảng 20 000 bước trên S70 + tập nhắm lỗi |
| So được với | `C_ALL` và `C_70`: chỉ khác dữ liệu (spec 6.1: model cuối của C train lại từ gốc với cùng S) | Chỉ với `C_70`, và gộp thêm 20 000 bước |
| Chi phí (ước lượng theo số đo bốn run) | Một A100, khoảng 10,7 giờ, 74–76 CU | Khoảng 25 CU |

- Dữ liệu ghép như `cplus_cut`: index 0–424 là S70, giống từng byte bản đã train `C_70`; tập nhắm lỗi từ index 425.
- Stats là file của ALL (`1c745091…`), như bốn run. Trước khi train phải kiểm action và state của tập nhắm lỗi nằm trong biên của stats đó. Ra ngoài biên thì dừng và ghi `Decision`.

### 20.7 Luật đọc (viết trước khi chạy)

<!-- round-c70-rules -->

**(r1) So sánh chính: `C70_R1` so với `C_ALL`.**
- Cùng 181 episode thêm vào S70: nhắm theo lỗi so với thêm đều.
- Hiệu ghép cặp theo điều kiện trên tập eval `rp_a04c14e79dfd-2e57f60`, cách tính như (a′) của 19.2: CI 95 % bootstrap theo điều kiện (lấy mẫu lại trong từng mức, 10 000 lần, hạt giống 20261103), McNemar chính xác hai phía.
- Hai giai đoạn như 19.2, bảng E1, E3, F, đi tiếp áp cho (r1). Giai đoạn 1 là 6 lô đầu, 60 điều kiện; `C_ALL` đã có đủ 60 điều kiện này.

| # | Điều kiện | Đọc là |
|---|---|---|
| 1 | Cận dưới CI 95 % của (`C70_R1` − `C_ALL`) > 0 | Trên task khay, 181 episode do một vòng Failure → Data chọn giúp hơn 181 episode thêm đều (sơ bộ, dev, 1 seed) |
| 2 | CI chứa 0 | Không thấy khác ở mức này. Không đọc thành "nhắm theo lỗi không giúp" |
| 3 | Cận trên CI 95 % < 0 | Nhắm theo lỗi kém hơn thêm đều. Kết quả âm hợp lệ, phải báo |
| 4 | McNemar | Báo cạnh 1–3, không đổi kết luận. CI và McNemar khác nhau thì báo cả hai |

**(r2) Phụ: `C70_R1` so với `C_70`.** Cùng cách tính. Mô tả vòng có làm π₀ tốt lên không. Không quyết định dừng hay đi tiếp.

**(r3) Mô tả theo cụm.** Thành công của `C70_R1` trên các điều kiện thuộc cụm đã nhận dữ liệu, so với các điều kiện còn lại. Phép đo này thiên lệch hồi quy về trung bình (spec 6.13), nên không phải tỉ lệ sửa được và không cập nhật f_t.

**(b) Số tuyệt đối.** Như (b) của 19.2: mức 1–2 gộp so với 80 %, từng mức so với 70 %, khoảng Wilson 95 %.

**(c) Chỉ số phụ, không đổi (r1), (r2).**
- Thành công nới ở 5, 7,5, 10, 15, 20 cm như (c) của 19.2.
- Tỉ lệ khay nằm trên bàn B ở cuối lượt, cách tính của cột `on_table_b`.
- Số `L-TRAY-TILT` ở bước `place` và `release_stand`.

Mọi câu báo các số này phải có chữ "nới" hoặc "chỉ số phụ".

**Trước khi đọc.**
- Plan vòng đã đóng băng; `rules_sha256` ghim khối này.
- Phần S70 của bản cắt giống từng byte bản cắt của `C_70`. Stats bằng `1c745091…`.
- Checkpoint `ckpt_60000` của `C70_R1` trên server cùng sha256 với bản trên Drive.
- Eval cùng cây, cảnh `+zone1`, server `Ta` 24 + RTC, 1 worker, mỗi server một client, như bốn run.

Thiếu một điều thì không đọc: ghi `Decision` và báo.

**Lệch so với spec, ghi cạnh mọi số.**
- 1 seed train, không phải 3 (spec 7.3 luật 6). Trên dev, không holdout.
- Cổng dev của spec 6.12 (90 điều kiện mới, ≥ 3 lượt mỗi điều kiện, sàn A/A) được thay bằng hai giai đoạn trên tập eval chung. Đo tỉ lệ sửa được của spec 6.13 không làm; Ψ₀ 1 vòng nên f_t cũng không dùng lại.
- Bước 6 không chạy. KỸ NĂNG YẾU dùng sinh S1 thay teleop correction (ghi đè của kỹ sư, 20.5). Sinh với tham số mức 1–2 theo tiền lệ của ALL (20.5).

**Giới hạn ghi cạnh mọi số.**
- Như 19.2: sơ bộ, chỉ trong sim, renderer MuJoCo, rollout EGL không lặp lại, CI của 60 điều kiện rộng khoảng ±15 điểm %.
- `C_ALL` và `C_70` train trước vòng này, cùng recipe và seed. GPU không tất định, nên hai lần train cùng dữ liệu cũng khác nhau một chút.
- Cùng một đội dựng task, sinh dữ liệu, chẩn đoán và đọc kết quả.

Luật này không đổi sau khi thấy kết quả. Muốn đổi thì ghi `Decision` mới và báo theo cả luật cũ lẫn luật mới.

<!-- /round-c70-rules -->

### 20.8 Ngân sách và lịch (ước lượng, chưa đo)

| Việc | Ở đâu | Thời gian | CU |
|---|---|---|---|
| H1–H3, bước 5, bước 8 | `rtx3060` CPU, laptop | Nửa ngày | 0 |
| Bước 7, 30 rollout | Một L4 serve + client `rtx3060` | Khoảng 2,8 giờ | Khoảng 6 (cap 8) |
| Sinh, QA, chọn, đóng băng | `rtx3060` CPU, ≤ 10 worker | Khoảng 300 lượt ≈ 1,2 giờ sinh (theo lô C+: 262 lượt, 0,93 giờ) + 0,5 giờ QA phát lại | 0 |
| Train phương án A | Một A100 | Khoảng 10,7 giờ | 74–76 (cap 80) |
| Eval giai đoạn 1 | Một L4 serve + client `rtx3060` | Khoảng 6 giờ (đo được ở làn `C_70`) | Khoảng 11 (cap 14) |
| **Tổng nếu dừng ở giai đoạn 1** | | Khoảng 2,5 ngày | **Khoảng 92** |
| Nếu đi tiếp | 18 lô còn lại cho `C70_R1`, `C_ALL`, `C_70` (hai run sau chưa có giai đoạn 2) | Khoảng 17 giờ mỗi làn, ba làn song song | Khoảng 100 thêm |

- Số dư Colab lúc 04:34 ngày 12/11 khoảng 195 CU. `B_ALL` còn khoảng 30 CU tới 60k. Đường giai đoạn 1 vừa đủ; đi tiếp thì không đủ, cần `Decision`.
- Lịch, nếu duyệt trong ngày 12/11:
  - 12/11: H1–H3, bước 5, 7, 8.
  - Sáng 13/11: sinh và đóng băng; train từ trưa 13/11.
  - 14/11: eval giai đoạn 1, có số trong ngày 14/11, trước demo 17/11.
- Mỗi job có dòng ước lượng trong sổ chi phí và watcher cap như 19.8, dừng phiên ngay khi xong.

### 20.9 Quyết định cần Hiếu

| # | Quyết định | Đề xuất |
|---|---|---|
| R1 | B_add = 181 episode (phần `C_ALL` có thêm so với S70) | Đồng ý |
| R2 | KỸ NĂNG YẾU dùng sinh S1 quanh điều kiện lỗi thay teleop correction (ghi đè của kỹ sư) | Đồng ý; correction thật để sau demo |
| R3 | Sinh với tham số mức 1–2 theo tiền lệ của ALL, lệch spec 7.3 luật 7 | Đồng ý |
| R4 | Train phương án A (từ gốc, 60 000 bước, cap 80 CU) | A |
| R5 | Thay cổng dev 6.12 và phép đo 6.13 bằng hai giai đoạn ghép cặp với `C_ALL` (20.7) | Đồng ý |
| R6 | Chạy H1–H3, bước 5, sinh và QA trên `rtx3060` (CPU, ≤ 10 worker); bước 7 trên một L4 (cap 8) | Đồng ý |
| R7 | Duyệt luật 20.7 | — |

### 20.10 Việc còn lại

- 7.2 Bước 4 (H1–H3) và phiếu sửa cho DA-37 (ngưỡng `approach_a`) và DA-38 (ghi thời điểm lỗi).
- 7.3 Bước 5, 7, 8, evidence card của từng cụm, chọn cụm nhận dữ liệu.
- 7.4 Mã:
  - loader cho plan vòng có cha là một nhánh của plan cặp (`purpose: round`, `inherits` plan cặp, `base_branch: C_70`);
  - `runplan check` và `freeze` cho plan đó;
  - bản cắt S70 + tập nhắm lỗi (như `cplus_cut`);
  - `colab_train --branch C70_R1`;
  - `evidence` đọc (r1), (r2).
- 7.5 Sinh, QA, chọn, đóng băng plan (điền `targets`, `rules_sha256`).
- 7.6 Train; 7.7 eval giai đoạn 1 và đọc theo 20.7.

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 6/11/2026 | Mục 8.2: sửa câu "chạy lại riêng một episode cho ra đúng nó" (sai dưới EGL), câu cũ giữ nguyên. Thêm mục 13: khởi chạy eval C, kiểm tất định hỏng (ảnh reset EGL lệch 13/230 400 pixel), chạy thử và thời gian, số đo yaw, giới hạn. Quyết định của Hiếu ngày 6/11: chạy tiếp và ghi giới hạn; đủ 270, mức 1–2 trước; 1 worker. Khối quy tắc mục 9 không đổi | Hiếu (soạn với Claude) |
| 6/11/2026 | Mục 13.6: C-max chuẩn bị, chưa train (Hiếu 6/11): RunPlan nháp `rp_366283071c4a`, tập `CMAX` 429 episode, bản cắt trên `rtx3060`, bản nháp `Decision` của quy tắc 0 với hai biến thể (i) chỉ S1, (ii) S1 cộng S2 (chưa có release S2). Mục 13.5: lệch checkout SIMPLE `6d10628` so với ghim `b75c678` | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 13.7: kết quả eval C (0/270; mức 1–2 0/240, Wilson 0–1,6 %), nhãn lỗi, bước của bộ chấm, yaw trên 270 trace, quy tắc 0 xảy ra (không chạy C+), `Decision` `fail` chờ Hiếu, đề xuất C-max (i). Mục 13.5: trace không có `timing` (lô chạy trước #148) | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 14: luật đọc T1, T2 của bước kiểm pipeline ảnh ([Đề xuất]), viết trước rollout đầu tiên. T2: Ta = 10 với RTC không chạy được (`max_delay` 8), đề xuất T2b (Ta 24, RTC tắt) và T2a′ (Ta 10, RTC tắt) | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 14.2: Hiếu chốt hai biến thể T2b (Ta 24, RTC tắt) và T2a′ (Ta 10, RTC tắt) ("Đồng ý"), ghi trước rollout đầu tiên của T2; thêm `inference_delay` = 6 của eval C | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 14.3: kết quả T1 (0/20 trên 20 cảnh train của C, Wilson 0–16,1 %; `reach_b` 65 %, `place` 5 %). Đọc theo luật 14.1: nghi chuỗi train/serve, không train gì cho tới khi tìm ra lỗi. Luật 14.1, 14.2 không đổi | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 14.4: kết quả T2b (`Ta = 24`, RTC tắt): 0/20, không qua `carry` ở điều kiện nào (mốc eval C 13/20); `success_gain` 0, `place_gain` 0, không đáng xem. Ghi lệnh khởi động lại server. Luật 14.2 không đổi | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 14.5, 14.6: kết quả T2a′ (`Ta = 10`, RTC tắt): 0/20, không qua `carry`, không đáng xem; tổng hợp T1, T2; server trả về `Ta = 24`, `--rtc`. `Decision` quy tắc 0 ghi `criteria.pipeline_check` và sửa khoảng trống đầu. Luật 14.1, 14.2 không đổi | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 15: luật đọc A (open-loop trên dữ liệu train của C, hai đường gọi) và B (stats, ảnh, state qua phát lại) của bước kiểm chuỗi train/serve ([Đề xuất]), viết trước lần chạy đầu tiên. Hiếu giao "Giao DA-34 làm" | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 15.6: kết quả B. B1 stats khớp. B2 ảnh khác: PSNR ở frame 0 khoảng 16,5 dB; cây eval thiếu manifest SimReady nên khay và cảnh render bằng khối trơn, `visuals_revision` `none` so với `4763fbf` của dữ liệu C. B3: theo luật là khác ở các chiều ngón cái; thứ tự, đơn vị và nghĩa đúng. Luật 15.3 không đổi | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 15.7: luật đọc T1r (chạy lại T1 với cảnh SimReady, Hiếu "Oke chạy lại T1 cho tôi"), gồm kiểm trước (revision, PSNR) và so với T1 theo bước ([Đề xuất]), viết trước khi đọc PSNR và trước rollout đầu tiên | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 15.5: kết quả A. A1 khớp: 2783/2783 chunk giống hệt từng bit giữa đường serve và đường train. A2 theo luật là chưa học (`r_place` 2,73; `e_place` 1,47 × các bước đầu), ghi kèm việc vế `r` cũng ≥ 1 ở các bước vòng kín vẫn qua. Server trả về `Ta` 24, `--rtc`. Luật 15.2 không đổi | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 15.8: kết quả T1r. Kiểm trước đạt (revision `4763fbf`, PSNR frame 0 34,9 dB). p_T1r 1/20 (Wilson 0,9–23,6 %); `place` ghép cặp với T1: 1 và 1, không tốt hơn rõ. Đọc theo bảng 15.7: ảnh lệch là một phần nguyên nhân; đọc chung với A: C chưa học `place`. Luật 15.7 không đổi | Hiếu (soạn với Claude) |
| 7/11/2026 | Mục 16: chạy lại eval C trên cảnh SimReady (Hiếu "Chạy lại eval C"). Viết trước lô đầu tiên: lý do, luật quy tắc 0 và bậc 2 không đổi, kết quả mục 13.7 giữ làm bản ghi nhưng không dùng để đọc quy tắc 0; cây master `079160d` có SimReady, guard revision theo từng lô; kiểm trước đạt (revision `4763fbf`, PSNR frame 0 34,9 dB); chỉ số phụ tư thế cuối của khay so với vùng đích, thêm sau khi thấy T1r, không phải luật | Hiếu (soạn với Claude) |
| 8/11/2026 | Mục 16.6: kết quả eval C trên cảnh SimReady. 27/27 lô, 17,2 giờ. Mức 1–2 gộp 20/240 = 8,3 % (Wilson 5,5–12,5 %); quy tắc 0 xảy ra theo luật, cận trên khoảng tin cậy vượt 10 % ghi kèm. Mức 0 5/30. `L-PLACE-POSE` 131/240, trung vị lệch vùng đích 10–11 cm (chỉ số phụ). `Decision` ghi kết quả mới, kết quả mục 13.7 là bản ghi trên cảnh trơn; chưa ký. Luật mục 9, 16.1 không đổi | Hiếu (soạn với Claude) |
| 8/11/2026 | Mục 17: nhiệm vụ 5, C+. 17.1 `Decision` mở lại C+ (sửa hệ quả "không chạy C+" của quy tắc 0 sau khi thấy kết quả, trích nguyên văn lời Hiếu 8/11; luật đọc C+ là quy tắc 1–2 không đổi; chờ ký). 17.2 evidence card cụm `L-PLACE-POSE`: vùng đích không render, vị trí đặt không đi theo đích, sai số chủ yếu là độ tản ngang, không tham số cảnh nào gắn với lỗi. 17.3 cách chọn 160 episode nhắm lỗi và luật đọc, viết trước khi sinh. 17.4 khoảng trống | Hiếu (soạn với Claude) |
| 8/11/2026 | Mục 17.5: sinh 262 lượt nhắm lỗi (229 ghi được), QA phát lại 229/229, release `tray_s1_6c0fd7d37f77`, QA DA-03 226 pass / 3 reject, bộ lọc 177; chọn 160 theo luật 17.3 (bước 1: 117, bước 2: 43), tập `T160` `1104d00e…`; `round-tray-cplus.yaml` đóng băng `rp_71fee3fcff69`; bản cắt C+ 320 episode dựng thử và kiểm. Mục 17.6: runbook Colab cho C+ (chưa chạy) | Hiếu (soạn với Claude) |
| 8/11/2026 | Mục 17.4: sửa câu "HTTP 409" (đọc nhầm `baselines/psi0.py`; client của eval khay `psi0_decoupled_wbc.py` không gửi `session_id`, nên hai client là một phiên RTC, dùng chung trạng thái mà không báo lỗi); câu sai giữ để đối chiếu. Mục 17.7: phép đo 2 worker trên một server, dừng sau 1 episode mỗi bên; kết luận không dùng 2 worker trên một server, eval C+ chạy 1 worker | Hiếu (soạn với Claude) |
| 8/11/2026 | Mục 17.6: ba điều bắt buộc (launch check, cap 18 CU, đường checkpoint về `rtx3060` có sha256), lệnh hand-off chép cả danh sách sha256, eval C+ chuẩn bị sẵn (`serve-cplus.sh`, `launch-eval-cplus.sh`, `stats-check.py` trong `~/denso-da34-t8`), chưa chạy; sửa tên job `job_da34_ft_C_PLUS` | Hiếu (soạn với Claude) |
| 8/11/2026 | Hiếu ký hai `Decision`: quy tắc 0 (`he-tray-v2.rule0.decision.json`, `verdict: fail` giữ nguyên) và mở lại C+ (`round-tray-cplus.rule0-override.decision.json`). Các chỗ ghi "chờ ký" đổi thành đã ký; C+ chưa launch | Hiếu (soạn với Claude) |
| 9/11/2026 | Mục 17.8: fine-tune C+ lần 1 dừng ở khoảng bước 18 000 vì laptop restart (7,49 CU, không checkpoint nào dùng được); Hiếu duyệt chạy lại từ đầu với cap 17 CU, C+ tổng khoảng 23,5 CU vượt slot 18 CU | Hiếu (soạn với Claude) |
| 9/11/2026 | Mục 17.8: fine-tune C+ lần 2 xong (40 000 bước, 16,11 CU, 8,37 giờ), checkpoint về `rtx3060` và kiểm sha256; C+ tổng 23,6 CU. Eval C+ chưa chạy | Hiếu (soạn với Claude) |
| 9/11/2026 | Mục 18.1–18.2: nhánh B (nhiệm vụ 4, Hiếu "Chốt 4 mặc định" 9/11): thiết lập (B là C của `rp_a04c14e79dfd`, chỉ đổi VLM cha thành VLM sau stage 1 của DA-30) và luật đọc B ([Đề xuất], khối `branch-b-rules`), viết trước mọi lượt của B. Khối `tier2-rules` không đổi | Hiếu (soạn với Claude) |
| 9/11/2026 | Mục 18.3: RunPlan B nháp `he-tray-b.yaml` (`rp_97922261b774` khi chưa điền ghim), cha stage 1, bất biến `variant_of`, chặn `freeze` và `--launch` khi chưa đủ ghim. Mục 18.2 trỏ tới file plan | Hiếu (soạn với Claude) |
| 9/11/2026 | Mục 18.4: `colab_train --branch B` (chỉ plan B đã đóng băng và duyệt; VLM stage 1 từ Drive, kiểm sha256 trọng số, manifest cả thư mục, file khác trùng VLM của C; cha stage 1 thêm vào recipe trong bộ nhớ) và runbook Colab cho B, chưa chạy | Hiếu (soạn với Claude) |
| 9/11/2026 | Mục 18.5: runbook eval B (như eval C SimReady, sau eval C+) và cách đọc bằng `eval_results --baseline`: hiệu ghép cặp, CI bootstrap theo mức, McNemar chính xác; luật 18.2 không đổi | Hiếu (soạn với Claude) |
| 9/11/2026 | Mục 18.6: `Decision` nháp của B (`he-tray-b.decision.json`, `open`, chờ eval B và chữ ký của Hiếu) | Hiếu (soạn với Claude) |
| 9/11/2026 | Mục 18.7–18.8: ước lượng stage 3 B (16,0 CU, cap 18, sàn 14) và eval B (17,3 giờ `rtx3060`), stage 1 ở sổ DA-30; dạng checkpoint stage 1 mà B nhận và việc còn lại (4.7, 4.8) | Hiếu (soạn với Claude) |
| 9/11/2026 | Mục 18.3, 18.4, 18.6, 18.8 (review PR #172): ghim `parent_header_sha256` (header safetensors của VLM C) và `colab_train` kiểm header của trọng số stage 1 trước khi train; `budget.runs` phải là `[B]`; thêm `superseded_by` vào danh sách trường được khác; id nháp đổi thành `rp_a3d3f96260d9`. Luật 18.2 không đổi | Hiếu (soạn với Claude) |
| 10/11/2026 | Mục 18.9 (quyết định của Hiếu 10/11/2026 "Ghi Decision"): eval B hai giai đoạn, giai đoạn 1 là 6 lô đầu (60 điều kiện), dừng E1, E3 hoặc F, còn lại chạy tiếp tới 240; mức 0 chỉ khi đi tiếp. Mục 18.2: khối `branch-b-rules` sửa trước mọi lượt của B (sha256 `6c0eb9c9…` thành `52f3385b…`), nhãn ngoài khối. Mục 18.5: `eval_batch --max-chunks 6`, `eval_results --stage1`, thời gian từng giai đoạn. Mục 18.3, 18.6, 18.7, 18.8: id nháp mới, `Decision`, dòng ước lượng giai đoạn 1 | Hiếu (soạn với Claude) |
| 11/11/2026 | Mục 19 (Hiếu 11/11/2026 qua phiên điều phối: W1, W2, cặp 60k, mục tiêu ≥ 80 %): thiết lập hai run `B_ALL` và `C_ALL` chỉ khác VLM; khối luật `pair60k-rules` [Đề xuất] viết trước mọi lượt chạy (so sánh chính hai giai đoạn như 18.2, số tuyệt đối so mốc 80 % có Wilson, thành công nới theo dung sai, không quy hiệu so với C và C+); RunPlan cặp nháp `rp_edf5bb2c7808`; số epoch (60 000 bước là 1,11 epoch của ALL ước lượng); ngân sách (khoảng 23,8 CU mỗi run, cap 28, sàn 14) | Hiếu (soạn với Claude) |
| 11/11/2026 | Mục 19 (Hiếu 11/11/2026 01:50 qua phiên điều phối: cần số trong ngày 12/11): hai run song song, `ckpt_40000` lên Drive để đọc sớm. Khối `pair60k-rules` thêm luật (e) (60k là số chính, 40k chỉ đọc sớm; plan dự phòng đọc 40k) và điều kiện server đúng checkpoint, nên `rules_sha256` đổi thành `24747738…`. 19.3: trường `checkpoints`, `schedule`, plan dự phòng `he-tray-pair40k-seq.yaml` (`rp_1160d977dd9f`); id nháp của plan 60k thành `rp_01c132b8d3b0`. 19.5 viết lại: bộ canh CU cho một đợt nhiều phiên; lịch; ba phương án eval R, M, M+; ngân sách và số dư cần mua (gói 100 CU đủ). 19.6 mới: gói bằng chứng `evidence`, chạy thử trên số thật của C và C+. 19.7: việc còn lại | Claude cho Hiếu |
| 11/11/2026 | Mục 18 (quyết định của Hiếu 11/11/2026): B và C-max đã thay thế bởi cặp trên cut ALL, vì cảnh `+zone1` (DA-33, PR #182) đổi file hai plan ghim; `superseded_by` đặt ngoài id, id giữ nguyên. Test tray không còn đọc trạng thái file sống: `tests/tray/conftest.py` bỏ qua độ lệch mà cây sống đã có, giữ độ lệch do test tạo | Claude cho Hiếu |
| 11/11/2026 | Mục 19.3 (#182 đã merge, master `7b0defd1`): hai plan cặp ghim `pinned_files` (danh sách của bản 2, băm lại; chỉ `mjcf.py`, nơi đặt `TARGET_ZONE_REVISION`, và `simple_task.py` đổi) và `cut.visuals_revision` `…+zone1`. Id nháp mới `rp_350a28bb7245` (60k) và `rp_862e049c8d29` (dự phòng); còn 13 ghim chờ W1 và W2 | Hiếu (soạn với Claude) |
| 11/11/2026 | Mục 19 (Hiếu 11/11/2026 "Chốt A100" qua phiên điều phối): cặp 60k chạy song song trên A100. Plan 60k đổi ghi chú, watcher `--gpu A100 --cap 70 --floor 14`, cap 70 mỗi run, trần 140; recipe không đổi. Mục 19.5 tính lại theo ước lượng: 8,45 giờ và khoảng 57 CU mỗi run, số dư 500 CU đủ; mốc tính theo T0. Plan dự phòng không còn cần. Khối 19.2 không đổi. Id nháp mới `rp_d44e3e6262b4` | Hiếu (soạn với Claude) |
| 11/11/2026 | Mục 19.8 (Hiếu 11/11/2026 qua phiên điều phối: "không để treo session mà tốn CU"): runbook dừng phiên khi xong và khi hỏng sớm (vòng `he1_fetch follow --stop-when-done`, bước bắt buộc khi không có nó), cap 61 sát ước lượng (trần 122, id nháp `rp_92ab06fe3fff`), bước cuối `colab sessions` trống. Mục 19.5 theo cap mới | Hiếu (soạn với Claude) |
| 11/11/2026 | Mục 19.8: vòng fetch tự dừng là đường chính (`follow --stop-when-done --total-steps 60000 --gpu A100`, PR #186 merge trước #181); bước dừng tay chỉ là dự phòng, ngưỡng s/bước sửa thành 0,50 tính cả val như `follow` đo (trước ghi 0,485 không tính val) | Hiếu (soạn với Claude) |
| 11/11/2026 | Mục 19.8, 19.5, 19.3 (phiên điều phối 11/11/2026): cap mỗi run nâng lại từ 61 lên 70, trần 140, lúc launch cần 154 CU. Lý do: ở cap 61, dừng sớm của `follow` ở bước 2 200 cắt run trên 0,50–0,51 s/bước, sát tốc độ khả dĩ 0,505; ở cap 70 mức đó là 0,58–0,59. Không tốn thêm CU vì phiên dừng khi `ckpt_60000` đã kiểm. Ngưỡng dừng tay thành 0,58. Id nháp về lại `rp_d44e3e6262b4` | Hiếu (soạn với Claude) |
| 11/11/2026 | Mục 19 (Hiếu 11/11/2026 "Thêm hai run 70%" qua phiên điều phối): thành bốn run, hai VLM × hai lượng dữ liệu (`B_ALL`, `C_ALL`, `B_70`, `C_70`). Tập con S70: 70 % mỗi phần của ALL, chọn theo sha256 của seed, làm tròn lên, ghim sha256 danh sách; cả bốn run dùng stats của ALL. Khối `pair60k-rules` viết lại [Đề xuất]: (a′) chính `B_70` − `C_70` hai giai đoạn; (f) `B_70` − `C_ALL` không kém với biên 10 điểm %; (g) `C_70` − `C_ALL`; (h) phụ `B_ALL` − `C_ALL`; (b) thêm mức 1, mức 2 riêng so với 70 %; `rules_sha256` thành `e7f90396…`. 19.3: schema bốn nhánh (`data`, `subsets`, `comparisons`, `schedule.waves`), lệnh `pairplan subset`, 19 chỗ trống, id nháp `rp_9614ef46ed9d`; plan dự phòng 40k đã xóa. 19.4: epoch của S70 (ước lượng). 19.5: bốn phiên A100, đường lùi hai đợt, bốn làn eval (ba server Colab L4), ngân sách khoảng 288 CU, cap 350, cần 294 CU lúc launch và 360 khi có serve. 19.6: gói bằng chứng đọc mọi so sánh của plan. 19.7, 19.8: 6.3 và vòng fetch cho cả bốn run | Claude cho Hiếu |
| 11/11/2026 | Mục 19.7, 19.8: PR #186 đã merge (`465e29b5`) và đã nhập vào nhánh của #181 | Claude cho Hiếu |
| 11/11/2026 | Mục 19.1, 19.3, 19.4 (W1 xong, cut ALL của DA-33 lúc 05:11, qua phiên điều phối): ghim hai phần của cut (release `tray_s1_41899efb4b27`, `tray_s1_4a8f4a8c6a8d`, file tập demo commit cạnh plan, ghim chất lượng và QA), 606 episode, 861 624 frame, stats `1c745091…`; ghim S70 (301 + 124 = 425 episode, 603 915 frame, sha256 hai danh sách). Còn 4 chỗ trống, đều của W2; id nháp `rp_9d89260a974d` | Claude cho Hiếu |
| 11/11/2026 | Mục 19.7 (phiên điều phối: ảnh VM Colab chỉ có CUDA 13.0, stage 1 hỏng pre-flight): stage 3 không build extension (ddp, `torch.optim.AdamW`, theo mã Ψ₀ `cda3fdf`); `colab_train setup` kiểm trước khi cài và từ chối recipe build op khi thiếu bộ CUDA 12.6 và `ninja` | Claude cho Hiếu |
| 11/11/2026 | Mục 19.3, 19.5, 19.7, 19.8 (W2 xong, stage 1 của DA-30 trên A100, qua phiên điều phối): ghim bốn chỗ của `vlm_stage1` từ `vlm.json` (job `da30-tray-ego-b`, `rp_1d7627234111`, bước 300; trọng số `c48ec2df…`, manifest `019daa80…`, kiểm nạp không lỗi); plan hết chỗ trống, id nháp `rp_e2fb9f62c223`; 19.5 thêm số đo mount Drive trên A100 (đồng ý mỗi VM, hết giờ 120 s, chạy lại một lần) | Claude cho Hiếu |
| 11/11/2026 | Mục 19.9 mới, 19.5, 19.7 (nhiệm vụ con 6.3, qua phiên điều phối): runbook bốn run. Gồm: dựng S70 theo seed của chính episode và giữ stats của ALL (`pair_cut`); hai tar lên Drive; `colab_train` cho bốn nhánh, dữ liệu từ Drive được kiểm trước khi cài; một đợt `cu_watch` và đường lùi hai đợt; bước đồng ý Drive trên mỗi VM; làn serve Colab (`colab_serve`, kiểm sha256 và bounds của stats ALL); bảng cổng. Chưa chạy | Claude cho Hiếu |
| 11/11/2026 | Mục 19.9 (phiên điều phối chạy thử 6.3 trên cut thật): ghi sha256 phải ra của `ALL.tar` (`bea55b14…`) và `S70.tar` (`f87bfecb…`), sha khác thì dừng; bước A chạy được trên laptop từ bản sao đã kiểm | Claude cho Hiếu |
| 12/11/2026 | Mục 20 mới (nhiệm vụ 7, Hiếu "Có, soạn RunPlan" qua phiên điều phối): một vòng Failure → Data trên `C_70` ([Đề xuất], viết trước mọi rollout chẩn đoán, sinh, train hay eval). Đặt vòng vào hình PoC của spec 7.2 (`C_70` = A₀.₇, `C_ALL` = thêm đều, `C70_R1` = C, B_add 181 episode); đầu vào `round-c70-rollouts.jsonl` (`aff514b5…`) và 8 cụm; kiểm hệ thống H1–H3 trước dữ liệu; bước 6 không làm được (S1-06), bước 7 3 lượt mỗi đại diện; ghi đè KỸ NĂNG YẾU sang sinh S1; luật đọc `round-c70-rules` ((r1) `C70_R1` − `C_ALL` quyết định, hai giai đoạn như 19.2); ngân sách khoảng 92 CU tới giai đoạn 1 (ước lượng); bảy quyết định R1–R7 chờ Hiếu. Plan nháp `round-tray-c70.yaml`, chưa có loader | Claude cho Hiếu |
