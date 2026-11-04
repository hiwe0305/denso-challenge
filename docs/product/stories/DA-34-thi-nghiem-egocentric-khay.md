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
- [ ] 3. Eval và bảng kết quả, video (AC 3, 4)
- [ ] 4. Nhánh B khi có video (AC 5)
- [ ] 5. Vòng Failure → Data trên lỗi của C: chẩn đoán, sinh nhắm lỗi, fine-tune và eval C+ (AC 6; trước 12/11/2026)

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

## Ghi chép khi làm

- 3/11/2026 (nhiệm vụ 1): RunPlan `rp_59164e3970c4` đóng băng ([`he-tray.yaml`](../../../configs/runplans/tray/he-tray.yaml)); tập `A` = `94245f8d36ab…`, `C` = `5db98a38ed80…` ([`demo_sets.json`](../../../configs/runplans/tray/demo_sets.json)); quy tắc diễn giải ở [docs/he/tray.md](../../he/tray.md). Sổ ước lượng 4 lần fine-tune × 26 CU = 104 CU trong khoảng 162 CU còn lại. Rủi ro: con số giữ chỗ 1,0 s/bước của `psi0-stage3.yaml` cho 11,1 giờ và khoảng 75 CU mỗi lần, tức khoảng 300 CU cho 4 lần; cần số đo của S1-04 trước khi chạy nhiệm vụ 2. **4/11/2026:** S1-04 đã đo; Hiếu chốt Colab L4, recipe DA-19 không đổi, validation mỗi 2.000 bước: khoảng 8,5 giờ và 16,6 CU mỗi lần, 4 lần khoảng 66 CU (ước lượng). Bản 1 đóng băng lại thành `rp_c49c99c8d8da` vì thêm ghi đè này. **4/11/2026 (review PO):** phát lại action S1 qua `eval-decoupled-wbc` thành công 6/6 ở thời gian sim, nhưng 4/6 ở thời gian thật trên máy tải nặng. Vì vậy eval phải chạy ở thời gian sim, và `eval-decoupled-wbc` cần bộ nạp episode khay: hai việc này thuộc `flywheel_simple.tray.run`, cần PR riêng trước nhiệm vụ 3. Ψ₀ không đọc cột `index`. Mức 0 tính là lượt lặp của một cảnh (tray.md mục 8). Tập con 40 và 80 chưa thành dataset LeRobot: Ψ₀ `LerobotDataConfig` không có bộ lọc episode, nên nhiệm vụ 2 phải dựng hai dataset con kèm `stats_psi0.json` riêng.
- 4/11/2026 (bậc 2): Hiếu duyệt "Approve tier 2". Bản 2 chỉ train C (tập 160) và C+; vẫn ghim bốn tập 40/80/160/320 để A chạy được sau. RunPlan có trường `budget` (trần 36 CU, cap 18 CU mỗi lần, watcher dừng phiên ở cap) mà `runplan check` kiểm. Giới hạn mới: không có A nên C+ − C gộp tác động của nhiều dữ liệu hơn và của dữ liệu nhắm lỗi (tray.md mục 9, quy tắc đọc **[Đề xuất]** chờ Hiếu duyệt).
- 5/11/2026 (nhiệm vụ con 1.7): kho planner-5 `s1-pool-1104` sinh xong (610 lượt, 542 ghi, QA phát lại 542/542). Release `tray_s1_f9433b028c52` có 541 episode. QA của DA-03 ra 534 pass, 0 flag, 7 reject; bộ lọc giữ 436, còn 429 sau khi loại reject. **[Đã chốt 5/11/2026, Hiếu] loại 7 reject DA-03 khỏi tập demo**; `demo_sets --qa-work` làm việc này và dừng nếu thiếu report. 1.7 chưa đánh dấu xong: nếu planner-6 được nhận thì kho sinh lại (tray.md mục 10).
- 5/11/2026 (nhiệm vụ con 1.8–1.9): planner-6 của DA-33 được 38/50 (planner-5 44/50), nên bản 2 đóng băng trên release planner-5. Tập cắt trên `rtx3060` bằng code của 4848b70, trùng từng byte với lần cắt thử: `C` = `a202cc028a2e…`, `A` = `b914d6412f59…` ([`demo_sets-v2.json`](../../../configs/runplans/tray/demo_sets-v2.json)). RunPlan [`he-tray-v2.yaml`](../../../configs/runplans/tray/he-tray-v2.yaml) đóng băng lần đầu là `rp_301f08e73358`; sau review #116 đóng băng lại thành `rp_a04c14e79dfd`. `quality-s1-pool-1104.jsonl` (số đo theo seed, không có dữ liệu episode) commit cạnh plan để `runplan check` chạy trên CI. Sổ chi phí thêm 4 dòng ước lượng eval 270 episode (C và C+ mỗi nhánh 4,5 giờ 3060; A và C-NOEGO 0). Ba ca `joint_limit` không kiểm lại, vì việc đó chỉ cần khi nhận planner-6. Train chờ PR này merge và lô của DA-26.
