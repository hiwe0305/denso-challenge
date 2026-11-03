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
- **Recipe** chung cho mọi nhánh: [`psi0-stage3.yaml`](../../configs/models/psi0-stage3.yaml), 40.000 bước, batch 16 trên một GPU (tác giả dùng 8 × 16 = 128), lr 1e-4 cosine, VLM đóng băng, RTC. Ghi đè duy nhất, chung cho mọi nhánh (4/11/2026): `train.validation_steps: 2000` thay vì 500, theo quyết định của Hiếu ở [S1-04 mục 4.1](../g0/psi0-finetune-cost.md); validation không đổi quá trình train, chỉ ít điểm `val` hơn (21 thay vì 81 mỗi lần). `runplan check` từ chối mọi ghi đè khác. Máy: một Colab L4. Seed train 0. `stats_psi0.json` của mỗi nhánh tính trên chính tập train của nhánh đó [Đề xuất], như Ψ₀ làm khi fine-tune một dataset.
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
