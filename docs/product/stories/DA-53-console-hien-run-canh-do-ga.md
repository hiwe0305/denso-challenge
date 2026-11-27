# DA-53 · Console hiện run train và eval trên cảnh đồ gá (run M, run N)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Nháp 27/11/2026, chờ Hiếu duyệt story và chốt các câu hỏi ở mục "Cần Hiếu chốt"; mã chỉ bắt đầu sau khi nhánh dựng lại giao diện `chore-console-ui-rebuild` vào master |
| Người làm | Hiếu, cùng Claude |
| Làn | Ngoài ba làn: `packages/flywheel-console` (index, seed, giao diện). Không sửa nhân, làn, adapter hay đường ống eval |
| Nguồn yêu cầu | Hiếu, 27/11/2026: lần train gần nhất (run M) và kết quả tốt nhất không thấy trên Console |
| Nhãn | `area:console`, `area:eval` |
| Sprint | Trước vòng chung kết (khoảng 3/12/2026) |
| Ước lượng | Mã khoảng 8 giờ (ước lượng); bước vận hành 3.1 khoảng 15 phút |
| Phụ thuộc | Nhánh `chore-console-ui-rebuild` (hợp đồng `docs/console/api-contract.md`, giao diện mới; chưa vào master). DA-48 (run M, đã merge). DA-47 (eval `jig2`, outcome K1). DA-50 (run N, đang train từ 27/11/2026). DA-51 sửa cùng hợp đồng API, nên hai story không chạy song song trên cùng file |

## Story

Là người xem Flywheel Console, tôi muốn thấy run M (và run N khi có) trên trang Train, Đánh giá và Vòng, cùng số liệu và luật đọc như trong [tray-jig.md](../../he/tray-jig.md), để Console hiện đúng lần train gần nhất và kết quả tốt nhất hiện có thay vì dừng ở DA-34.

Hiện trạng, đọc ngày 27/11/2026 (chỉ đọc, `fwdata` thật trên laptop và index vừa dựng lại ngày 26/11/2026):

| Chỗ | Hiện trạng | Hệ quả |
|---|---|---|
| `seed/tasks.yaml` | Task `tray` chỉ có vòng `tray-r1`: `train_dir: tray/pair60k`, `eval_dir: tray/pair60k/stage1-60k`, `max_steps: 60000` | Index không đọc chỗ nào khác |
| `index/story.py` `_runs` | Chỉ quét `<train_dir>/*/*/metrics.jsonl`; tên nhánh lấy từ tên thư mục cha | Run M ở `tray/jig-m/da48-ft-m-s0/` không được đọc; nếu trỏ vào thì nhánh sẽ tên `jig-m` chứ không phải `M` |
| `index/story.py` `_pair` | Đọc file `stage1-*.json` của phép so cặp DA-34 | Kết quả eval của M (`tray/outcomes/jig-m-100000-r3/`, 180 rollout) không có đường đọc |
| `index/story.py` `_train_log` | Lấy `phases[*].seconds` của `report.json` như thời lượng từng pha | `persist` là mốc cộng dồn (luôn bằng `train` cộng khoảng 200–600 s ở cả 5 run DA-34), nên trang Train ghi pha lưu mất hơn 10 giờ |
| Index sau khi dựng lại | Catalog có 4 release `jig2`, trang chi phí có phiên Colab `da48-m` | Không có dòng nào chứa `rp_a410d01efa62` hay `da48-ft-m` |

Số của run M (thực đo, [tray-jig.md](../../he/tray-jig.md) mục 4 và 5): 100 000 bước, 56,15 CU, khoảng 21 giờ train; eval `ckpt_100000` trên 60 điều kiện × 3 lượt: 75,6 % (136/180), khoảng tin cậy 70,0–81,1, chưa đạt mốc 80 %; mức 1 là 85,6 %, mức 2 là 65,6 %; bước `place` 89,4 %. Claude đã đếm lại từ `scores.jsonl` ngày 27/11/2026 và khớp các tỉ số.

## Cách làm

**[Đề xuất]** Claude 27/11/2026. Chờ Hiếu chốt các câu hỏi ở mục sau.

### Mô hình hóa: run M và N là một vòng trên cảnh đồ gá

DA-50 gọi run N là "một vòng Failure → Data trên cảnh đồ gá". Vì vậy đề xuất thêm vòng thứ hai vào task `tray` thay vì một khối riêng:

| Phương án | Nội dung | Được | Mất |
|---|---|---|---|
| **A (đề xuất)** | Vòng `tray-jig-r1`: `baseline: M`, `after_round: N`, `controls: []`. Mỗi run khai báo đường dẫn train của riêng nó. Eval đọc bằng một bộ đọc mới theo kiểu file | Đúng ý vòng Failure → Data; dùng lại bộ chọn vòng, trang Train, Đánh giá, Vòng và phép lọc `withhold_eval` | Phải nới `Round` cho `controls` rỗng và đường dẫn theo từng run |
| B | Khối `experiments:` riêng, mỗi run một mục | Không đụng `Round` | Thêm một khái niệm, giao diện phải có trang riêng; mất mối nối M → N |

### Đọc số eval: dùng `eval_results --json`, không tự tính lại

Khoảng tin cậy trong tray-jig.md là bootstrap theo điều kiện, lấy lại trong từng mức (seed 20261125 cho M, 20261126 cho N), do `flywheel_psi0.tray.eval_results` tính. Console không được import adapter (import-linter: "Console reads files, never lanes or adapters"). Tự viết lại bootstrap trong Console sẽ cho số lệch với tài liệu.

Vì vậy Console chỉ đọc file `results.json` do `python -m flywheel_psi0.tray.eval_results … --repeats 3 --json results.json` ghi cạnh outcome:

| Trường Console | Lấy từ `results.json` |
|---|---|
| Tỉ lệ, khoảng tin cậy của cả task (mức 1 và 2 gộp) | khối headline |
| Tỉ lệ, khoảng tin cậy từng mức; số điều kiện, số rollout | khối từng mức, `conditions`, `n` |
| Tỉ lệ qua từng bước | `scorer_steps` |
| Nhãn lỗi | khối nhãn lỗi của từng mức |
| Wilson (chỉ mô tả) | `wilson`, `wilson_n_eff` |
| Thiếu rollout | `missing` |
| N trừ M theo điều kiện (khi có N) | `paired.repeats` (`paired_diff_repeats`), chạy với `--baseline` là thư mục eval của M |

Thiếu `results.json` thì trang ghi "Chưa có" kèm lệnh ở trên, không tự tính.

### Luật đọc

Ngưỡng của luật (80 % cả task, 70 % từng mức, bước đặt trên 50 %, đều đọc ở cận dưới) khai báo trong `tasks.yaml` của vòng, kèm nguồn `docs/he/tray-jig.md` khối `jig-m-rules` và `jig-n-rules`. Index so cận dưới với ngưỡng và ghi câu đọc ("đạt mốc" hoặc "chưa đạt mốc"); trang luôn hiện nguồn của luật. Câu so N với M theo quy tắc 2 và 3 của `jig-n-rules`.

**Điều kiện trước khi đọc:**
- Đủ số rollout khai báo (180), `missing` rỗng.
- `conditions.sha256` trùng giá trị khai báo trong vòng.
- Thiếu một điều kiện thì trang không hiện câu đọc, chỉ hiện số kèm lý do.

**So với DA-34:** đặt cạnh nhau, luôn kèm câu nêu điểm khác (cảnh, tập eval, bộ chấm, số bước), không có chữ "tốt hơn" (quy tắc 4 của `jig-m-rules`).

### Sửa thời lượng pha VM

Thời lượng của một pha là `seconds` của nó trừ `seconds` của pha trước nếu giá trị tăng dần; ghi rõ cách tính trong docstring. Trang Train ghi pha VM thuộc run nào. Lỗi này cũng có ở vòng `tray-r1`.

### Cần Hiếu chốt

1. Phương án A hay B.
2. Có hiện run N trên Console khi đang train không (đường cong từ `metrics.jsonl` khi file đã kéo về laptop), hay chỉ hiện khi đã có eval.
3. Kết quả eval của M và N có nằm ngoài `withhold_eval` không. Đề xuất: có hiện; công tắc chỉ dành cho `C70_R1` theo quyết định ngày 16/11/2026.
4. Trang tổng quan và trang chọn bài toán: "kết quả tốt nhất" của task `tray` lấy theo vòng đang chọn (đề xuất), hay luôn lấy vòng mới nhất.

## Tiêu chí chấp nhận

1. `seed/tasks.yaml` có vòng `tray-jig-r1` (theo phương án đã chốt), và `index/tasks.py` kiểm hình dạng của nó: đường dẫn theo từng run, `controls` rỗng, ngưỡng luật, nguồn luật, `conditions_sha256`, số rollout. Vòng `tray-r1` cho ra đúng file index như trước (so byte với index dựng lại ngày 26/11/2026, trừ phần pha VM ở AC 5). Có test.
2. Trang Train hiện run M với tên nhánh `M` (không phải `jig-m`), đường cong loss, val, thr, vram, gn, số bước 100 000 trên 100 000, và loss cuối. Có test trên một `metrics.jsonl` nhỏ dựng trong test.
3. Index đọc `results.json` của M:
   - Trên bản sao trong test, ra đúng 136/180 cả task, 77/90 mức 1, 59/90 mức 2, 161/180 bước `place`.
   - Khoảng tin cậy chép nguyên từ file, không tính lại.
   - Thiếu file thì trả trạng thái "chưa có" kèm lệnh.
   - Có test.
4. Câu đọc theo luật:
   - Trên số của M, ra đúng ba câu như bảng ở tray-jig.md mục 5: chưa đạt 80 % cả task, mức 1 đạt 70 %, mức 2 chưa đạt, bước đặt trên 50 %.
   - Thiếu rollout hoặc sai `conditions.sha256` thì không có câu đọc.
   - Không trang nào có chữ "tốt hơn" khi đặt M cạnh run DA-34.
   - Có test.
5. Thời lượng pha VM là hiệu giữa các mốc. Trên report của C_70, pha `persist` khoảng 213 s chứ không phải 38 262,6 s. Có test.
6. Khi có `results.json` chạy với `--baseline` của M, vòng hiện N trừ M (trung bình hiệu, khoảng tin cậy, câu đọc theo quy tắc 2 và 3 của `jig-n-rules`). Khi chưa có thì ghi "Chưa có", không ghi 0. Có test.
7. `withhold_eval` vẫn chặn kết quả thi lại của `C70_R1` ở mọi trang và trong chat. Test cũ vẫn qua.
8. `docs/console/api-contract.md` và `docs/console/api-samples/` cập nhật cho các khối mới trong `story.json` và `tasks.json`.
9. `uv run ruff check`, `uv run mypy` (không thêm lỗi), `uv run pytest`, `uv run lint-imports`, `scripts/repo/check_links.py`, `scripts/repo/pr_guard.py` qua.

## Nhiệm vụ

- [x] 1.1 Viết story (file này)
- [ ] 1.2 Hiếu chốt bốn câu ở mục "Cần Hiếu chốt"; ghi quyết định vào file này
- [ ] 2.1 `index/tasks.py` và `seed/tasks.yaml`: vòng `tray-jig-r1`, đường dẫn theo run, ngưỡng và nguồn luật, có test (AC 1)
- [ ] 2.2 `index/story.py`: đọc run train theo đường dẫn của từng run; sửa thời lượng pha VM, có test (AC 2, 5)
- [ ] 2.3 Module mới trong `index/` đọc `results.json`, kiểm điều kiện trước khi đọc, ghi câu đọc theo luật, có test (AC 3, 4, 6)
- [ ] 2.4 Giao diện: trang Train, Đánh giá, Vòng hiện vòng `tray-jig-r1`; câu so với DA-34 có điểm khác đi kèm (AC 2, 3, 4, 6, 7)
- [ ] 3.1 (Hiếu, vận hành) Ghi `results.json` của M cạnh outcome trên laptop, rồi chạy `fw console index` (AC 3)
- [ ] 3.2 Cập nhật hợp đồng API và mẫu; chạy đủ kiểm tra (AC 8, 9)

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-console/src/flywheel/console/index/` (`tasks.py`, `story.py` và một module mới đọc `results.json`)
- `packages/flywheel-console/src/flywheel/console/seed/tasks.yaml`
- `packages/flywheel-console/src/flywheel/console/web/` (chỉ trang Train, Đánh giá, Vòng và i18n)
- `packages/flywheel-console/tests/`
- `docs/console/api-contract.md`, `docs/console/api-samples/`

## Ghi chú cho người làm

- Không sửa `packages/flywheel-psi0` (gồm `eval_results.py`), `flywheel.contracts`, `pyproject.toml`, `uv.lock` hay workflow CI. Nếu `results.json` thiếu một trường cần hiện thì báo Hiếu, không tự tính trong Console.
- Hình dạng `results.json` lấy từ `flywheel_psi0/tray/eval_results.py` tại commit lúc làm; ghi commit đó trong docstring của module đọc.
- Bước 3.1 ghi vào `fwdata` thật nên do Hiếu chạy. Lệnh đầy đủ (plan, `--set`, `--out`) lấy từ runbook ở tray-jig.md mục 3; nếu bản trên `rtx3060` đã có `results.json` thì kéo về thay vì chạy lại.
- Không chạy lại eval hay train nào. Số của M là bản đã ghi ở tray-jig.md mục 5.
- Không bắt đầu mã khi nhánh dựng lại giao diện chưa vào master: `story.py`, hợp đồng API và các trang đang được sửa ở đó.
- Số chưa đo ghi là ước lượng.

## Kiểm thử

- `uv run pytest packages/flywheel-console/tests`
- `uv run ruff check`, `uv run mypy` (lệnh đủ ở README gốc), `uv run pytest`, `uv run lint-imports`
- `python3 scripts/repo/check_links.py`
- `python3 scripts/repo/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"`
- Tay: chạy Console với `FW_ROOT` trỏ `fwdata` thật, chọn vòng `tray-jig-r1`, so số trên trang Train và Đánh giá với tray-jig.md mục 4 và 5

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
