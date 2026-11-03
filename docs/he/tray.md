# Thí nghiệm egocentric trên task bê khay: thiết lập và quy tắc diễn giải (DA-34)

_Chốt ngày 3/11/2026, trước khi chạy job nào. Story [DA-34](../product/stories/DA-34-thi-nghiem-egocentric-khay.md) nhiệm vụ 1; [design 28/10/2026](../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 6.2–6.4 và 6.6. RunPlan: [`he-tray.yaml`](../../configs/runplans/tray/he-tray.yaml), đóng băng ở [`he-tray.lock.json`](../../configs/runplans/tray/he-tray.lock.json)._

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
- **Recipe** chung cho mọi nhánh: [`psi0-stage3.yaml`](../../configs/models/psi0-stage3.yaml), 40.000 bước, batch 16 trên một GPU (tác giả dùng 8 × 16 = 128), lr 1e-4 cosine, VLM đóng băng, RTC. Ghi đè duy nhất, chung cho mọi nhánh (4/11/2026): `train.validation_steps: 2000` thay vì 500, theo quyết định của Hiếu ở `docs/g0/psi0-finetune-cost.md` mục 4.1 (S1-04, PR #78); validation không đổi quá trình train, chỉ ít điểm `val` hơn (21 thay vì 81 mỗi lần). `runplan check` từ chối mọi ghi đè khác. Máy: một Colab L4. Seed train 0. `stats_psi0.json` của mỗi nhánh tính trên chính tập train của nhánh đó [Đề xuất], như Ψ₀ làm khi fine-tune một dataset.
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
- Giới hạn phải nêu: dữ liệu robot là synthetic S1 do planner sinh (`action_quality = planned`, một cách cầm); release chỉ có mức 1; batch toàn cục 16 thay vì 128; C-NOEGO khác C cả ở số bước pretrain; kết quả trong sim. Khi có B: B tốn thêm compute ở stage 1; egocentric và task cùng do đội dựng.

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
- **Phải eval ở thời gian sim** [Đề xuất, cần Hiếu duyệt]. Agent `psi0_decoupled_wbc`, agent WBC sonic và vòng eval đọc `time.monotonic()`, nên WBC nội suy mục tiêu theo giờ tường. Trên máy tải nặng, cùng một chuỗi action cho kết quả khác nhau, và 2/6 lượt phát lại hoàn hảo bị chấm hỏng. Ở thời gian thật, tỉ lệ thành công của một nhánh lẫn cả tải của máy. Dữ liệu train ghi ở thời gian sim (D-24).
- **`eval-decoupled-wbc` tại pin không đọc được episode khay.** `get_episode_lerobot` của SIMPLE cần `environment_config["dr_state_dict"]` (dòng `FIXME`), và giải mã mọi frame video của episode (khoảng 8 GB RAM mỗi episode). Cổng dùng một bộ nạp thay thế chỉ trả `environment_config`. Env khay dựng lại cảnh từ `tray.sample`. Hai việc, thời gian sim và bộ nạp, thuộc `flywheel_simple.tray.run`, ngoài phạm vi DA-34: cần PR riêng trước nhiệm vụ 3. Script của cổng và kết quả từng lượt nằm trong ghi chú dùng chung `DA-34-replay-gate/` của nhóm phiên.
- Giả thuyết, chưa kiểm: số 0/20 của S1-03 trên task hai bàn ở `mujoco` chạy ở thời gian thật, nên có thể một phần do đồng hồ.

### 8.2 Mức 0 có phải giả lặp (điểm 1)

- Số đo S1-03, task hai bàn, mức 0, checkpoint của tác giả, thời gian thật, chạy lại hai lần. Cùng một episode: hai lượt trùng nhau trong 33–44 frame đầu, rồi tách ra. Ở frame cuối, ảnh lệch trung bình 38–50 mức xám. Hai episode khác nhau thì lệch ngay từ frame 0, vì bộ eval hai bàn có cảnh khác nhau ở mức 0. Mức 0 của task khay chỉ có một cảnh.
- Nguồn ngẫu nhiên, đọc mã tại pin. Nhiễu flow-matching của Ψ₀ lấy `torch.randn` từ RNG toàn cục, gieo một lần khi server khởi động (`seed_everything(launch_config.seed or 42)`, `psi0_serve_simple.py`). Ở thời gian thật, độ trễ của máy cũng làm lượt chạy khác nhau (mục 8.1). Ở thời gian sim, chuỗi sim + WBC tất định (mục 8.1), nên chỉ còn nhiễu của server.

Quy tắc cho bản 2, thay mục 2 (theo nhánh "khác nhau" của review):

| Mục | Quy tắc |
|---|---|
| Mức 0 | Một cảnh. Các lượt ở mức 0 là **lượt lặp** (rollout replicate), không phải điều kiện. Báo p ở mức 0 riêng, CI bootstrap theo lượt, ghi rõ "1 cảnh × k lượt" |
| Chỉ số chính, hiệu, HE-T | Gộp **mức 1 và 2**: mỗi seed là một cảnh khác. Bootstrap theo điều kiện trong từng mức, như mục 2. Luôn báo kèm theo từng mức |
| Server khi eval | Một tiến trình server cho mỗi nhánh, gieo hạt 42, chạy các episode theo thứ tự cố định, không khởi động lại giữa các episode. Khởi động lại giữa các episode thì các lượt mức 0 sẽ trùng nhau. Ghi hạt giống và thứ tự vào kết quả |
| Phân bổ 270 lượt [Đề xuất, cần Hiếu duyệt] | Mức 0: 30 lượt lặp. Mức 1 và 2: mỗi mức 120 seed dev (1 000 100–1 000 219). Tổng vẫn 270 episode mỗi nhánh, 240 cảnh khác nhau cho chỉ số chính. Nửa độ rộng CI ước lượng khoảng ±7,5 điểm (quy theo căn bậc hai từ số Monte Carlo ở mục 7, chưa chạy lại) |

`he-tray-v2.yaml` chỉ đóng băng sau khi Hiếu chốt hai dòng [Đề xuất] (đồng hồ sim, phân bổ lượt).

### 8.3 Cột `index` của release (điểm 2)

Ψ₀ tại `cda3fdf` không đọc cột `index` khi train stage 3. Không cần đánh số lại trước khi train. Đường đọc (đọc mã tại pin):

- `finetune_simple_psi0_config` → `LerobotDataConfig` → `LeRobotDatasetWrapper` → `LeRobotDataset` của fork `songlin/lerobot` tại `09929d8` (bản 0.3.3, ghim trong `uv.lock` của Ψ₀).
- `__getitem__` lấy `hf_dataset[idx]` theo vị trí. Biên episode lấy từ độ dài trong `meta/episodes.jsonl` (`get_episode_data_index`). Frame lân cận lấy theo `idx + delta`. Mã chỉ đọc `episode_index`, `timestamp`, `task_index`.
- Trong Ψ₀, chỉ bộ nạp `psi/data/gear` đọc `index`, và bộ nạp đó không nằm trên đường stage 3.

Điều kiện đi kèm: các hàng parquet phải xếp theo episode, đúng thứ tự và độ dài trong `meta/episodes.jsonl`. Dataset con của nhiệm vụ 2 phải giữ điều kiện này.

### 8.4 Bản 1 đã thay (điểm 4)

Đầu file `he-tray.yaml` ghi dòng `SUPERSEDED - DO NOT RUN`. Bản 2 vào cùng PR #73 (nhiệm vụ con 1.8). Phần chú thích này không đổi plan đã parse, nên `rp_c49c99c8d8da` và lock giữ nguyên.
