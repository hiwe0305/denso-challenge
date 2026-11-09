# DA-34 · Thí nghiệm egocentric thay một phần demo robot trên task bê khay

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (3/11/2026: DA-33 đã có release `tray_s1_0d84cc87b1e5`; nhiệm vụ con của nhiệm vụ 1 đã viết) |
| Người làm | Hiếu |
| Làn | Adapter Ψ₀ (`flywheel-psi0`), RunPlan |
| Story PRD | Story của [design 28/10/2026](../../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 6, 7 (M4, M5) |
| Nhãn | [Adapter] · `epic:9` · `gate:G1` · `area:train` |
| Sprint | S2; M4 12/11/2026, M5 15/11/2026; nhánh B sau demo · **Lịch 3/11/2026:** A, C, C-NOEGO và vòng Failure → Data (C+) xong trước **12/11/2026** (07 mục 2.4) |
| Ước lượng | 15 giờ trước demo (ước lượng), không tính GPU-giờ |
| Phụ thuộc | DA-33 (release synthetic), DA-19 (adapter fine-tune trên Colab; kiểm đường `eval-decoupled-wbc` của Ψ₀), S1-03 (Q0, serve Ψ₀), S1-04 (giờ fine-tune). **3/11/2026:** vòng Failure → Data cần DA-13 (chẩn đoán, Châu), hook `SimpleSim` ghi trace của env khay, và cờ nhận danh sách điều kiện trong `generate.py` của DA-33 |

## Story

Là trưởng nhóm, tôi muốn so Ψ₀ fine-tune với đủ demo robot, với một nửa demo, và với một nửa demo trên checkpoint không có EgoDex, để biết task khay nhạy với số demo đến đâu và egocentric có bù được không.

## Tiêu chí chấp nhận

1. RunPlan cho nhánh A (N = 80), C (N = 40), C-NOEGO (N = 40, checkpoint ablation không EgoDex) với cùng recipe, cùng số bước, cùng hạt giống điều kiện; tập 40 là tập con của 80, cố định bằng hash.
2. Ba lần fine-tune stage 3 chạy trên Colab Pro hoặc server thuê, tiếp tục được từ checkpoint, ghi sổ chi phí.
3. Eval 30 điều kiện dev × 3 mức ở `sim_mode=mujoco`, đồng bộ, qua `eval-decoupled-wbc` (decoupled WBC); Ψ₀ tự xuất lệnh đi.
4. Bảng theo design mục 6.3, khoảng tin cậy bootstrap, diễn giải theo design mục 6.4 ghi "sơ bộ, trên dev"; video rollout cạnh nhau.
5. Sau khi có video egocentric: stage 1 và stage 3 của nhánh B, eval B, cập nhật bảng.
6. (3/11/2026) Một vòng Failure → Data trên lượt thất bại của nhánh C theo design 28/10/2026 mục 6.6: evidence card cho cụm lớn nhất, N_add episode S1 nhắm lỗi qua QA và sổ chi phí, fine-tune C+, eval C+ trên 90 điều kiện dev và trên điều kiện C đã hỏng; bảng C, C+, A ghi "sơ bộ, trên dev", kèm số hồi quy. Trễ thì dừng ở episode nhắm lỗi đã qua QA và ghi `Decision`.

## Nhiệm vụ

- [x] 1. RunPlan ba nhánh, chọn tập demo có hash (AC 1) · **5/11/2026:** bản 2 `rp_a04c14e79dfd` thay bản 1
  - [x] 1.1 Code chọn tập demo lồng nhau tất định từ release DA-33, có hash (`flywheel_psi0.tray.demo_sets`); test CPU: cùng đầu vào ra cùng hash, tập 40 ⊂ tập 80, không phụ thuộc thứ tự, kiểm manifest của release
  - [x] 1.2 Chạy chọn tập trên release `tray_s1_0d84cc87b1e5`, ghi `configs/runplans/tray/demo_sets.json`; chạy lại với `--check` khớp
  - [x] 1.3 RunPlan `he-tray.yaml` cho A, C, C-NOEGO (cùng recipe, số bước, seed train, hạt giống điều kiện eval; checkpoint gốc và ablation có revision và sha256); khung `round-tray-cplus.yaml` cho C+ (AC 6, chưa đóng băng); code kiểm bất biến và tính `run_plan_id`, có test
  - [x] 1.4 Chốt quy tắc diễn giải trước khi chạy ở `docs/he/tray.md` (design mục 6.4, 6.6), rồi đóng băng RunPlan (`he-tray.lock.json`)
  - [x] 1.5 Sổ chi phí ước lượng `docs/g0/ledger/DA-34.csv` (dòng `estimated`: fine-tune A, C, C-NOEGO, C+ và eval)
  - [x] 1.6 (bản 2, quyết định của Hiếu 3/11/2026: tăng dữ liệu, chất lượng cao) Đo chất lượng episode (`flywheel_psi0.tray.quality`), bộ lọc chất lượng trong chọn tập; chốt cỡ tập 320/160, ngưỡng lọc, kho seed 1000–1609 và eval 270 điều kiện ở `docs/he/tray.md` mục 7, trước khi sinh kho
  - [x] 1.7 Sinh kho S1 seed 1000–1609 trên rtx3060, QA phát lại, release có hash, đo chất lượng cả kho
  - [x] 1.8 Chọn tập lồng nhau 40 ⊂ 80 ⊂ 160 ⊂ 320 qua bộ lọc; RunPlan `he-tray-v2.yaml` (eval 270 điều kiện, C+ n_add 160), đóng băng; bản 1 ghi đã thay; theo bậc 2 chỉ nhánh C, có trường `budget` (36 CU, 18 CU mỗi lần)
  - [x] 1.9 Cập nhật sổ chi phí theo bản 2 và giờ máy thực đo của lô sinh
  - [x] 1.10 (quyết định của Hiếu 4/11/2026 ở S1-04 mục 4.1) Ghi đè `train.validation_steps: 2000` ở cấp plan, chung ba nhánh; `runplan check` chỉ cho ghi đè không đổi quá trình train; đóng băng lại bản 1 thành `rp_c49c99c8d8da`; sổ chi phí fine-tune sang Colab L4, 16,6 CU mỗi lần
  - [x] 1.11 (review của PO 4/11/2026) Kiểm trước khi chạy job: cổng phát lại 3 episode S1 qua `eval-decoupled-wbc` (server giả `flywheel_psi0.tray.replay_server`); mức 0 có phải giả lặp; Ψ₀ tại `cda3fdf` có đọc cột `index` không; ghi bản 1 đã thay. Kết quả và quy tắc bản 2 ở `docs/he/tray.md` mục 8
  - [x] 1.12 (sau review, 4/11/2026) Ghi Decision của Hiếu (eval ở thời gian sim; mức 0 là lượt lặp, phân bổ 30 / 120 / 120, nhiễu gieo theo episode) ở `docs/he/tray.md` mục 8; kiểm gieo nhiễu theo episode tại `cda3fdf` (mục 8.5); bản 1 có trường `superseded_by` (không vào id); `runplan check` nhận plan round; sửa batch toàn cục của tác giả thành 16 × 4 = 64 (S1-04)
- [ ] 2. Fine-tune A, C, C-NOEGO (AC 2) · **4/11/2026, bậc 2:** chỉ C (C+ ở nhiệm vụ 5), trần 36 CU, cap 18 CU mỗi lần, có watcher; A và C-NOEGO bỏ ([tray.md](../../he/tray.md) mục 9)
  - [x] 2.1 (5/11/2026) Mã phía VM `flywheel_psi0.tray.colab_train` (setup, train, check) cho nhánh C của `rp_a04c14e79dfd`: từ chối plan khác, lệch `pinned_files`, bản cắt sai; dùng lại `he1_colab.py stage`/`persist` và `he1_fetch.py` của DA-26; runbook ở tray.md mục 12; dòng ước lượng
  - [x] 2.2 (5/11/2026) Dựng bản cắt C trên rtx3060 (`demo_subset.py` ở master a5e863f, sau PR #121), `colab_train check` qua: `cut_problems` rỗng, n = 160, `set_hash` a202cc02… tính lại từ seed của bản cắt, tree sha256 6db888a1…; ở `~/denso-da34-pool/fwdata/cut-c-rp_a04c14e79dfd`
  - [x] 2.3 (5/11/2026) Chạy C trên Colab L4 theo runbook, từ master 5632c74, phiên `da34-t2-ft-c-s0` (03:08–11:24Z): đủ 40.000 bước, `result.json` ok, `train exit 0`; `ckpt_10000`…`ckpt_40000` về laptop, sha256 khớp VM. `follow` thoát 5 do race của `stage` (đã kiểm, không phải lỗi train); hai listing sau khi dừng: 0 assignment. MANIFEST.md (435 mục, 25,47 GB) cho Agent QA/QC; bản chép sang rtx3060 ở `~/denso-da34-pool/fwdata/tray/runs/da34-t2-ft-c-s0`
  - [x] 2.4 (5/11/2026) Dòng `measured` của `job_da34_ft_C`: 15,99 CU theo `colab usage` (ước lượng 16,8, cap 18), 40.000 bước, phiên 8,27 giờ, train 8,08 giờ (0,724 s/bước); trỏ về dòng ước lượng 16,8 CU
- [ ] 3. Eval và bảng kết quả, video (AC 3, 4) · **6/11/2026, Hiếu:** eval C đủ 270 điều kiện trên rtx3060, 1 worker, mức 1–2 xen kẽ trước, mức 0 cuối; chạy từ master sau PR mã eval
  - [x] 3.1 Mã eval trong `flywheel_psi0.tray`, test CPU: `eval_set` (điều kiện của plan thành dataset LeRobot một khung, có hash), `act_log` (proxy ghi mọi request với hash reply), `eval_driver` (cờ 7 bước của scorer và thời gian sim trong dòng outcome, hook trace DA-38; chỉ import `flywheel_simple` lúc chạy), `eval_batch` (lô 10 episode, chạy lại từ episode thiếu, chạy tiếp được, `runs.jsonl`)
  - [x] 3.2 Kiểm tất định (mục 8.5) và chạy thử; ghi giới hạn của EGL ở `docs/he/tray.md` kèm change log · **6/11/2026:** hỏng, ảnh reset EGL lệch 13/230 400 pixel, server tất định; Hiếu: chạy tiếp, ghi giới hạn (tray.md mục 8.2, 13)
  - [x] 3.3 Chạy cả lô 270 episode trên rtx3060 từ master, log đủ cho Agent QA/QC · **6/11/2026:** master `2e57f60`, 1 worker, 27/27 lô lần đầu, mã 0, 0 episode thiếu, 14,15 giờ (tray.md mục 13.7)
  - [x] 3.4 Bảng kết quả, đọc theo bậc 2 (tray.md mục 9, quy tắc 0), khoảng tin cậy bootstrap, tỷ lệ qua từng bước, loại lỗi, `Decision`; dòng ước lượng và thực đo trong sổ chi phí · **7/11/2026:** 0/270, mức 1–2 0/240 (Wilson 0–1,6 %), quy tắc 0 xảy ra: không chạy C+; `Decision` `fail` chờ Hiếu ký; đề xuất C-max (i) (tray.md mục 13.7)
  - [x] 3.5 Chuẩn bị C-max, chưa train: cắt 429 episode S1, RunPlan `draft`, `Decision` theo quy tắc 0, dòng ước lượng · **6/11/2026:** `rp_366283071c4a` (nháp, không khởi chạy được), tập `CMAX` 429 episode, bản cắt trên rtx3060, bản nháp `Decision` mở (tray.md mục 13.6)
  - [x] 3.6 Kiểm pipeline ảnh của quy tắc 0 (Hiếu 7/11/2026 "Chạy T1 + T2"): luật đọc viết trước (tray.md mục 14); T1 eval 20 điều kiện train của C; T2 đổi cách chạy (RTC, số action thực thi) trên 20 điều kiện dev; dòng ước lượng và thực đo. Bằng chứng: T1 0/20 trên cảnh train (Wilson 0–16,1 %, `reach_b` 65 %, `place` 5 %), luật 14.1: nghi chuỗi train/serve; T2b (`Ta` 24, RTC tắt) 0/20, T2a′ (`Ta` 10, RTC tắt) 0/20, cả hai không qua `carry`, không đáng xem (tray.md 14.3–14.6); server trả về `Ta` 24 + RTC; `Decision` ghi `criteria.pipeline_check`
  - [x] 3.7 Kiểm chuỗi train/serve sau T1 0/20 (luật 14.1; Hiếu 7/11/2026 "Giao DA-34 làm"): luật đọc viết trước (tray.md mục 15); A open-loop trên frame train của C, so đường train với đường serve và với action thật theo stage; B so stats, ảnh và state lúc serve với dataset qua phát lại; không train, 0 CU; dòng ước lượng và thực đo; T1r (Hiếu "Oke chạy lại T1 cho tôi"): chạy lại T1 với cảnh SimReady, luật viết trước (tray.md 15.7). Bằng chứng: A1 khớp, 2783/2783 chunk giống hệt từng bit giữa đường serve và đường train; A2 theo luật `place` chưa học (`r_place` 2,73) (tray.md 15.5); B1 stats khớp, B2 ảnh khác (PSNR frame 0 khoảng 16,5 dB, cây eval thiếu manifest SimReady), B3 thứ tự và đơn vị đúng (tray.md 15.6); T1r: PSNR frame 0 34,9 dB, 1/20 (Wilson 0,9–23,6 %), `place` ghép cặp với T1 1 và 1, đọc: ảnh lệch là một phần nguyên nhân, C chưa học `place` (tray.md 15.8); server trả về `Ta` 24 + RTC
  - [x] 3.8 Chạy lại eval C trên cảnh SimReady (Hiếu 7/11/2026 "Chạy lại eval C"): cây master có SimReady chép từ `~/denso-da33`, kiểm revision và PSNR trước khi chạy, guard revision theo từng lô; cùng RunPlan, 270 điều kiện, server `Ta` 24 + RTC, 1 worker; luật quy tắc 0 và bậc 2 không đổi, viết trước lô đầu tiên (tray.md mục 16); chỉ số phụ tư thế cuối của khay (`place_error`); dòng ước lượng và thực đo; không train, 0 CU · **8/11/2026:** 27/27 lô lần đầu, mã 0, 17,2 giờ; mức 1–2 gộp 20/240 = 8,3 % (Wilson 5,5–12,5 %), quy tắc 0 xảy ra; mức 0 5/30; `L-PLACE-POSE` 131/240, trung vị lệch 10–11 cm; `Decision` ghi kết quả mới, chờ Hiếu ký (tray.md mục 16.6)
- [ ] 4. Nhánh B khi có video (AC 5) · **9/11/2026, Hiếu "Chốt 4 mặc định":** B là nhánh C của `rp_a04c14e79dfd` với một thay đổi, VLM cha là VLM của C sau stage 1 trên 153 clip egocentric của đội (DA-30 nhiệm vụ 2); chuẩn bị mọi thứ trừ checkpoint stage 1 ([tray.md](../../he/tray.md) mục 18)
  - [x] 4.1 Thiết lập và luật đọc B viết trước mọi lượt của B (tray.md 18.1–18.2): chính là cận dưới CI 95 % của (B − C) > 0 trên 240 điều kiện mức 1–2, ghép cặp, bootstrap theo điều kiện; McNemar phụ; B so với C+ chỉ mô tả; chỉ số phụ và giới hạn; khối `branch-b-rules` để RunPlan ghim sha256
  - [x] 4.2 RunPlan nháp `he-tray-b.yaml` và `runplan`: cha stage 1 (`Stage1Parent`, ghim thư mục Drive, sha256 trọng số và sha256 manifest của DA-30, để trống tới khi có), bất biến "C của bản 2 với một thay đổi" (`variant_of`), `check` qua ở dạng nháp còn `freeze` và `--launch` từ chối khi chưa đủ ghim; test CPU
  - [x] 4.3 `colab_train --branch B`: chỉ chạy plan B đã đóng băng; lấy VLM từ Drive, kiểm sha256 trọng số, manifest cả thư mục và file không phải trọng số trùng VLM của C; recipe nhận cha stage 1 trong bộ nhớ; runbook Colab (tray.md 18.4); test CPU
  - [x] 4.4 `eval_results`: CI bootstrap ghép cặp của hiệu theo mức và McNemar chính xác cho luật 18.2; runbook eval B trên `rtx3060` sau eval C+ (tray.md 18.5); test CPU
  - [x] 4.5 `Decision` nháp cho B (`he-tray-b.decision.json`, cùng dạng `Decision` quy tắc 0), chờ Hiếu ký sau eval
  - [x] 4.6 Dòng `estimated` trong sổ chi phí: stage 3 B (Colab L4) và eval B (`rtx3060`); stage 1 ở sổ của DA-30
  - [ ] 4.7 Khi DA-30 có checkpoint: điền ghim VLM, bỏ `draft`, đóng băng, ghi id vào `colab_train`; Hiếu launch stage 3 B
  - [ ] 4.8 Eval B trên `rtx3060`, đọc theo luật 18.2, điền `Decision`; dòng thực đo
- [ ] 5. Vòng Failure → Data trên lỗi của C: chẩn đoán, sinh nhắm lỗi, fine-tune và eval C+ (AC 6; trước 12/11/2026)
  - [x] 5.1 `Decision` mở lại C+ sau quy tắc 0 trên eval C SimReady (Hiếu 8/11/2026 "Làm tiếp đi từ kết quả và phân tích kia. tôi muốn làm nó nhanh hơn"): sửa luật sau khi thấy kết quả, luật đọc C+ là quy tắc 1–2 không đổi, chờ Hiếu ký · **8/11/2026:** `round-tray-cplus.rule0-override.decision.json` (tray.md mục 17.1)
  - [x] 5.2 Evidence card cụm `L-PLACE-POSE` và luật chọn điều kiện nhắm lỗi, viết trước khi sinh · **8/11/2026:** 131 điều kiện, mỗi điều kiện 2 seed train (`cplus-conditions.jsonl`, sha256 `64d97c4e…`); card: vùng đích không render, không tham số cảnh nào gắn với lỗi (tray.md mục 17.2–17.3)
  - [x] 5.3 Sinh episode nhắm lỗi trên rtx3060, QA như release của C, release có hash, cắt tập C+ (160 + 160), đóng băng `round-tray-cplus.yaml` và ghi lock; dòng ước lượng và thực đo · **8/11/2026:** 262 lượt, 229 ghi được, release `tray_s1_6c0fd7d37f77`, 177 qua QA và bộ lọc, chọn 160 (`T160` `1104d00e…`), round `rp_71fee3fcff69`, bản cắt C+ 320 episode kiểm đạt (tray.md mục 17.5)
  - [x] 5.4 Runbook Colab cho C+ (như mục 12), chạy từ master; Hiếu launch · **8/11/2026:** runbook ở tray.md mục 17.6, `colab_train --branch C_PLUS` chỉ chạy round `rp_71fee3fcff69`; chưa launch. **9/11/2026:** lần 1 dừng ở khoảng bước 18 000 vì laptop restart (7,49 CU); lần 2 (Hiếu "Chạy lại, cap 17") xong 40 000 bước, 16,11 CU, checkpoint về `rtx3060`, sha256 khớp (tray.md 17.8)
  - [x] 5.5 Đo eval 2 worker trên cùng server (thông lượng, độ lệch kết quả), đề xuất cho eval C+. Bằng chứng (tray.md 17.7): đề xuất không dùng 2 worker trên một server, vì client `psi0_decoupled_wbc.py` không gửi `session_id` nên hai client là một phiên RTC (`previous_action` chung, `reset` của bên này xóa trạng thái bên kia, nhiễu gieo theo episode xen nhau); log server chỉ có `{}` và `{reset, seed}`, không 409. Phép đo dừng theo lệnh phiên điều phối sau 1 episode mỗi bên (7 phút); seed 1000105 cho kết quả khác 1 worker. Sửa câu "409" của 17.4; dòng ước lượng và thực đo trong sổ
  - [ ] 5.6 Eval C+ và đọc theo quy tắc 1–2 (8/11: chuẩn bị sẵn, chưa chạy; `serve-cplus.sh`, `launch-eval-cplus.sh` trên `rtx3060`, tray.md 17.6; chạy khi checkpoint đã về và Hiếu bảo)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `configs/runplans/tray/`
- `packages/flywheel-psi0/src/flywheel_psi0/tray/`, `packages/flywheel-psi0/tests/tray/`
- `docs/he/tray.md`, `docs/g0/ledger/DA-34.csv`

## Ghi chú cho người làm

- Quy tắc diễn giải chốt trước khi chạy (design mục 6.4); không đổi sau khi thấy kết quả.
- Kết quả trên ảnh MuJoCo không so được với số công bố của tác giả; báo cáo ghi renderer ở mọi con số.

## Người phụ trách

- Làm: Dương Đình Hiếu
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 28/10/2026 | Tạo story nháp theo design 28/10/2026 | PO (Hiếu) |
| 28/10/2026 | Eval qua `eval-decoupled-wbc` thay đường MP với AMO | PO (Hiếu) |
| 3/11/2026 | Thêm AC 6 và nhiệm vụ 5: phần 6 của demo chạy hết vòng Failure → Data trên task khay, có nhánh C+ (design 28/10 mục 6.6) | PO (Hiếu) |
| 3/11/2026 | DA-33 có release: viết nhiệm vụ con 1.1–1.5, trạng thái sang Đang làm | Claude cho Hiếu |
| 3/11/2026 | Hiếu chốt tăng dữ liệu, chất lượng cao: thêm nhiệm vụ con 1.6–1.9 (N 320/160, lọc chất lượng, eval 270 điều kiện); nhiệm vụ 1 mở lại | PO (Hiếu) |
| 4/11/2026 | Theo quyết định PO ở S1-04 (L4, validation mỗi 2.000 bước): thêm nhiệm vụ con 1.10; RunPlan bản 1 đóng băng lại thành `rp_c49c99c8d8da` | Claude cho Hiếu |
| 4/11/2026 | Review của PO trên PR #73: thêm nhiệm vụ con 1.11 (cổng phát lại, mức 0, cột `index`, bản 1 đã thay) | Claude cho Hiếu |
| 4/11/2026 | Hiếu chốt eval ở thời gian sim và cách đếm mức 0 (30 / 120 / 120, gieo nhiễu theo episode): thêm nhiệm vụ con 1.12 | PO (Hiếu) |
| 4/11/2026 | Hiếu duyệt bậc 2 ("Approve tier 2"): chỉ fine-tune C và C+, khoảng 33 CU, trần 36 CU; bỏ A và C-NOEGO; eval mujoco trên rtx3060, 0 CU. Ghi ở tray.md mục 9; AC 1, 2 và 6 đọc theo mục này | PO (Hiếu) |
| 5/11/2026 | Kho planner-5 và release `tray_s1_f9433b028c52`; Hiếu chốt loại 7 reject DA-03 khỏi tập demo (tray.md mục 10). Bản 2 chờ kết quả planner-6 của DA-33 | PO (Hiếu) |
| 5/11/2026 | Planner-6 không đạt (38/50, ngưỡng 44/50); bản 2 đóng băng trên planner-5, chỉ nhánh C; C+ kế thừa bản 2 với `n_add` 160. Nhiệm vụ con 1.7–1.9 xong (tray.md mục 11) | Claude cho Hiếu |
| 5/11/2026 | Hiếu duyệt nguyên văn quy tắc đọc bậc 2 (tray.md mục 9, **[Đã chốt]**). Sau review #116: khối quy tắc, file tập demo, config eval, split và mã cảnh/scorer được ghim bằng sha256; bản 2 đóng băng lại thành `rp_a04c14e79dfd` (thay `rp_301f08e73358`, chưa job nào chạy) | PO (Hiếu) |
| 5/11/2026 | Hiếu chốt: mã sim ghim (`pinned_files`) kiểm lúc khởi chạy job (`runplan check --release … --launch`), CI chỉ cảnh báo; id `rp_a04c14e79dfd` không đổi (tray.md mục 11) | PO (Hiếu) |
| 9/11/2026 | Hiếu chốt 4 mặc định cho nhánh B: viết nhiệm vụ con 4.1–4.8 (B là C với VLM sau stage 1 của DA-30; luật đọc viết trước ở tray.md mục 18) | Claude cho Hiếu |

## Ghi chép khi làm

- 3/11/2026 (nhiệm vụ 1): RunPlan `rp_59164e3970c4` đóng băng ([`he-tray.yaml`](../../../configs/runplans/tray/he-tray.yaml)); tập `A` = `94245f8d36ab…`, `C` = `5db98a38ed80…` ([`demo_sets.json`](../../../configs/runplans/tray/demo_sets.json)); quy tắc diễn giải ở [docs/he/tray.md](../../he/tray.md). Sổ ước lượng 4 lần fine-tune × 26 CU = 104 CU trong khoảng 162 CU còn lại. Rủi ro: con số giữ chỗ 1,0 s/bước của `psi0-stage3.yaml` cho 11,1 giờ và khoảng 75 CU mỗi lần, tức khoảng 300 CU cho 4 lần; cần số đo của S1-04 trước khi chạy nhiệm vụ 2. **4/11/2026:** S1-04 đã đo; Hiếu chốt Colab L4, recipe DA-19 không đổi, validation mỗi 2.000 bước: khoảng 8,5 giờ và 16,6 CU mỗi lần, 4 lần khoảng 66 CU (ước lượng). Bản 1 đóng băng lại thành `rp_c49c99c8d8da` vì thêm ghi đè này. **4/11/2026 (review PO):** phát lại action S1 qua `eval-decoupled-wbc` thành công 6/6 ở thời gian sim, nhưng 4/6 ở thời gian thật trên máy tải nặng. Vì vậy eval phải chạy ở thời gian sim, và `eval-decoupled-wbc` cần bộ nạp episode khay: hai việc này thuộc `flywheel_simple.tray.run`, cần PR riêng trước nhiệm vụ 3. Ψ₀ không đọc cột `index`. Mức 0 tính là lượt lặp của một cảnh (tray.md mục 8). Tập con 40 và 80 chưa thành dataset LeRobot: Ψ₀ `LerobotDataConfig` không có bộ lọc episode, nên nhiệm vụ 2 phải dựng hai dataset con kèm `stats_psi0.json` riêng.
- 4/11/2026 (bậc 2): Hiếu duyệt "Approve tier 2". Bản 2 chỉ train C (tập 160) và C+; vẫn ghim bốn tập 40/80/160/320 để A chạy được sau. RunPlan có trường `budget` (trần 36 CU, cap 18 CU mỗi lần, watcher dừng phiên ở cap) mà `runplan check` kiểm. Giới hạn mới: không có A nên C+ − C gộp tác động của nhiều dữ liệu hơn và của dữ liệu nhắm lỗi (tray.md mục 9, quy tắc đọc **[Đề xuất]** chờ Hiếu duyệt).
- 5/11/2026 (nhiệm vụ con 1.7): kho planner-5 `s1-pool-1104` sinh xong (610 lượt, 542 ghi, QA phát lại 542/542). Release `tray_s1_f9433b028c52` có 541 episode. QA của DA-03 ra 534 pass, 0 flag, 7 reject; bộ lọc giữ 436, còn 429 sau khi loại reject. **[Đã chốt 5/11/2026, Hiếu] loại 7 reject DA-03 khỏi tập demo**; `demo_sets --qa-work` làm việc này và dừng nếu thiếu report. 1.7 chưa đánh dấu xong: nếu planner-6 được nhận thì kho sinh lại (tray.md mục 10).
- 5/11/2026 (nhiệm vụ con 1.8–1.9): planner-6 của DA-33 được 38/50 (planner-5 44/50), nên bản 2 đóng băng trên release planner-5. Tập cắt trên `rtx3060` bằng code của 4848b70, trùng từng byte với lần cắt thử: `C` = `a202cc028a2e…`, `A` = `b914d6412f59…` ([`demo_sets-v2.json`](../../../configs/runplans/tray/demo_sets-v2.json)). RunPlan [`he-tray-v2.yaml`](../../../configs/runplans/tray/he-tray-v2.yaml) đóng băng lần đầu là `rp_301f08e73358`; sau review #116 đóng băng lại thành `rp_a04c14e79dfd`. `quality-s1-pool-1104.jsonl` (số đo theo seed, không có dữ liệu episode) commit cạnh plan để `runplan check` chạy trên CI. Sổ chi phí thêm 4 dòng ước lượng eval 270 episode (C và C+ mỗi nhánh 4,5 giờ 3060; A và C-NOEGO 0). Ba ca `joint_limit` không kiểm lại, vì việc đó chỉ cần khi nhận planner-6. Train chờ PR này merge và lô của DA-26.
