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
| `Decision` | [`he-tray-v2.rule0.decision.json`](../../configs/runplans/tray/he-tray-v2.rule0.decision.json): `dev_gate`, chủ thể `rp_a04c14e79dfd`, ngưỡng 0,10. Soạn 6/11 với `verdict: open`; từ 7/11 đã điền số đo của eval C, `verdict: fail`, chờ Hiếu ký (mục 13.7). Lệnh của Hiếu về C-max ghi vào đó |

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

**`Decision`.** [`he-tray-v2.rule0.decision.json`](../../configs/runplans/tray/he-tray-v2.rule0.decision.json) chốt nhánh này: `verdict: fail` (quy tắc 0 xảy ra), số đo ở `metrics`, chờ Hiếu ký. Bước tiếp theo đề xuất **[Đề xuất]**: C-max (i), chỉ S1, 429 episode, ước lượng 16 CU, plan nháp `rp_366283071c4a` (mục 13.6). Chưa launch; C-max chỉ chạy khi Hiếu duyệt. C-max (ii) vẫn trong danh sách khoảng trống.

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
