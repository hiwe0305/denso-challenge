# DA-53 · Console hiện run train và eval trên cảnh đồ gá (run M, run N)

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Hiếu đã chốt bốn câu ngày 28/11/2026 (mục "Quyết định của Hiếu"), rồi cùng ngày quyết không trình bày run N (mục "Quyết định 28/11/2026 về run N"). PR #252 đã vào master. 2.1–2.3 xong; 2.5 và 2.6 làm trước 2.4 |
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

Claude đề xuất 27/11/2026; Hiếu chốt ngày 28/11/2026 theo mục "Quyết định của Hiếu".

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

### Quyết định của Hiếu

Hiếu chốt ngày 28/11/2026, cả bốn câu theo đề xuất:

1. **Phương án A.** Vòng `tray-jig-r1` trong `seed/tasks.yaml`, `baseline: M`, `after_round: N`, `controls: []`.
2. **Hiện run N khi đang train.** Đường cong lấy từ `metrics.jsonl` đã kéo về laptop; trang ghi rõ N đang train, chưa có eval.
3. **M và N nằm ngoài `withhold_eval`.** Công tắc vẫn chỉ dành cho `C70_R1` theo quyết định ngày 16/11/2026.
4. **"Kết quả tốt nhất" theo vòng đang chọn.** Không trộn cảnh `tray` với cảnh `jig2` trên trang tổng quan và trang chọn bài toán.

### Quyết định 28/11/2026 về run N

Hiếu quyết ngày 28/11/2026, sau khi có kết quả eval của run N (124/180, thấp hơn run M 136/180; [tray-jig.md](../../he/tray-jig.md) mục 9):

1. **Run N không được trình bày** trên Console, chat và kịch bản demo: không hiện đường cong train, tập `N.tar`, phiên Colab, eval đang chạy, kết quả eval của N hay phép N trừ M. Chỉ trình bày run M. Quyết định này thay câu 2 và câu 3 ở mục trên, và làm AC 6 (N trừ M) không còn hiệu lực cho tới khi Hiếu quyết lại.
2. **Tài liệu đo và sổ chi phí giữ nguyên.** [tray-jig.md](../../he/tray-jig.md) mục 7–9 và `docs/g0/ledger/DA-50.csv` không sửa, không xóa (sổ là append-only). Trang chi phí vẫn cộng dòng tổng của `DA-50` vì đó là tiền đã tiêu; file trong `fwdata` giữ nguyên.
3. **So run M với các run cũ trên cùng cỡ 60 lượt.** Trang Đánh giá có bảng đặt lượt lặp 0 của M (60 rollout: 30 điều kiện mức 1, 30 mức 2) cạnh `C_ALL`, `B_ALL`, `B_70`, `C_70` của DA-34 giai đoạn 1 (60 rollout mỗi run). Lượt 0 được chọn trước theo số thứ tự, không chọn lượt cao nhất; bảng ghi kèm số của cả ba lượt. Bảng luôn đi kèm câu nêu điểm khác (cảnh có đồ gá, bộ chấm `simple-tray-predicates@2`, tập điều kiện, số bước train) và ghi mức chênh không quy riêng cho dữ liệu, theo quy tắc 4 và 5 của `jig-m-rules`. Số đọc từ file outcome bằng mã.

Cách làm (Claude đề xuất): vòng `tray-jig-r1` vẫn khai báo run N (đường dẫn của N là thứ cho bộ lọc biết cần ẩn gì, và mối nối M → N còn sẵn nếu Hiếu quyết lại), thêm khóa cấp vòng `withhold_runs` liệt kê run bị ẩn kèm mẫu tên phiên Colab và thư mục eval của nó (`da50-*`). Khác `withhold_eval` (chỉ giữ kết quả thi lại, vẫn hiện train, tập cắt và chi phí), `withhold_runs` ẩn cả run: `tasks.json` không liệt kê run đó, vòng ghi `after_round: null`. Lọc ở ba lớp: lúc dựng index, lúc server gửi `data/story.json` và `data/tasks.json` (phòng index cũ), và ở các bộ đọc `fwdata` trực tiếp của server và chat. Tiêu đề vòng chỉ nêu run M, `log_run` là M.

Hệ quả cho các nhiệm vụ còn lại: 3.1 chỉ ghi `results.json` của M; 2.4 chỉ dựng trang cho run M.

### Điều chỉnh sau khi đọc dữ liệu (Claude, 28/11/2026)

Đọc `fwdata` thật và mã ở `origin/master` `dd1338ce` trước khi viết code:

1. **Seed bootstrap.** `eval_results` không nạp được plan của M, nên phải chạy với `he-tray-v2.yaml` và `--bootstrap-seed`. Chạy thử vào thư mục tạm cho đúng số của mục 5 tray-jig.md:
   - M, seed 20261125: cả task 0,700–0,811; mức 1 0,789–0,922; mức 2 0,556–0,756.
   - File ghi `bootstrap_seed` và `plan_mismatch`. Index kiểm `bootstrap_seed` bằng seed khai báo của run; sai thì không có câu đọc.
2. **Pha `persist` chạy song song với `train`** (`persist --watch` của `trainer/colab.py`), không phải mốc cộng dồn. `train` có đồng hồ riêng, nên trừ pha trước cho mọi pha sẽ sai `train`. Cách sửa:
   - `setup` và `train` giữ nguyên.
   - `persist` hiện là phần đồng bộ sau train, bằng `persist − train` khi `persist ≥ train` (C_70: 213,4 s), kèm ghi chú chạy song song.
3. **Bước `place` không có khoảng tin cậy trong `results.json`** (chỉ có `step_pass`). Theo ghi chú cho người làm, Console không tự tính: thẻ quy tắc 3 hiện tỉ lệ, ghi "chưa có khoảng tin cậy", và không có câu đọc. AC 4 vì vậy chỉ đòi ba câu của quy tắc 1 và 2. Muốn có câu cho bước đặt thì cần một PR cho `eval_results` (ngoài phạm vi).
4. **Run N đã train xong, nhưng `metrics.jsonl` trên laptop chỉ tới bước 8 201** (`fetched.json`: `final: false`, vòng `follow` hỏng ở bước 8 198, tray-jig.md mục 8). Trang Train hiện đúng file đang có, kèm ghi chú file chưa kéo đủ; bước 3.1 thêm việc kéo `metrics.jsonl` đầy đủ từ Drive.
5. **Eval của N đã có** (`tray/outcomes/jig-n-100000-r3`, 180 dòng, 28/11/2026). Chạy thử với `--baseline` là eval của M ra `paired.repeats`. Vì vậy AC 6 kiểm được trên số thật, không cần chờ.
6. **Vòng mặc định.** Task `tray` liệt kê `tray-jig-r1` trước `tray-r1`, để Console mở vào vòng mới nhất. "Kết quả tốt nhất" vẫn lấy theo vòng đang chọn (quyết định 4).

Lệnh của bước 3.1 (chạy từ gốc repo, `FW` là thư mục `fwdata/tray`):

```bash
uv run python -m flywheel_psi0.tray.eval_results configs/runplans/tray/he-tray-v2.yaml --set $FW/eval-sets/jig-m-rp_a410d01efa62 --out $FW/eval/jig-m-100000-r3 --repeats 3 --bootstrap-seed 20261125 --json $FW/outcomes/jig-m-100000-r3/results.json
uv run python -m flywheel_psi0.tray.eval_results configs/runplans/tray/he-tray-v2.yaml --set $FW/eval-sets/jig-m-rp_a410d01efa62 --out $FW/eval/jig-n-100000-r3 --repeats 3 --bootstrap-seed 20261126 --baseline $FW/eval/jig-m-100000-r3 --json $FW/outcomes/jig-n-100000-r3/results.json
```

### Phần PR #252 đã làm trước

PR #252 (dựng lại giao diện) đã hiện run M và N, trước khi story này được duyệt:
- `index/story.py` có hàm `_jig` quét mọi `tray/outcomes/jig-*/scores.jsonl`, không qua `tasks.yaml`.
- Trang Train vẽ đường cong của M và N.
- Trang Đánh giá hiện bốn thẻ số. Khoảng Wilson trên rollout ghi là "mô tả", không có câu đạt hay chưa đạt, vì ngưỡng đang viết cứng trong JS.

Story này thay cách quét đó bằng vòng `tray-jig-r1` (quyết định 1) và đọc `results.json` (mục "Đọc số eval"). Khi xong, `_jig` và ngưỡng viết cứng được gỡ.

## Tiêu chí chấp nhận

1. `seed/tasks.yaml` có vòng `tray-jig-r1` (theo phương án đã chốt), và `index/tasks.py` kiểm hình dạng của nó: đường dẫn theo từng run, `controls` rỗng, ngưỡng luật, nguồn luật, `conditions_sha256`, số rollout. Vòng `tray-r1` cho ra đúng file index như trước (so byte với index dựng lại ngày 26/11/2026, trừ phần pha VM ở AC 5). Có test.
2. Trang Train hiện run M với tên nhánh `M` (không phải `jig-m`), đường cong loss, val, thr, vram, gn, số bước 100 000 trên 100 000, và loss cuối. Có test trên một `metrics.jsonl` nhỏ dựng trong test.
3. Index đọc `results.json` của M:
   - Trên bản sao trong test, ra đúng 136/180 cả task, 77/90 mức 1, 59/90 mức 2, 161/180 bước `place`.
   - Khoảng tin cậy chép nguyên từ file, không tính lại.
   - Thiếu file thì trả trạng thái "chưa có" kèm lệnh.
   - Có test.
4. Câu đọc theo luật:
   - Trên số của M, ra đúng ba câu như bảng ở tray-jig.md mục 5: chưa đạt 80 % cả task, mức 1 đạt 70 %, mức 2 chưa đạt. Bước đặt hiện tỉ lệ, không có câu đọc (mục "Điều chỉnh sau khi đọc dữ liệu", điểm 3).
   - Sai `bootstrap_seed` so với seed khai báo của run thì không có câu đọc.
   - Thiếu rollout hoặc sai `conditions.sha256` thì không có câu đọc.
   - Không trang nào có chữ "tốt hơn" khi đặt M cạnh run DA-34.
   - Có test.
5. Pha `persist` hiện phần đồng bộ sau train (`persist − train`), `setup` và `train` giữ nguyên. Trên report của C_70, pha `persist` khoảng 213 s chứ không phải 38 262,6 s. Có test.
6. (Tạm không hiệu lực từ 28/11/2026, xem mục "Quyết định 28/11/2026 về run N".) Khi có `results.json` chạy với `--baseline` của M, vòng hiện N trừ M (trung bình hiệu, khoảng tin cậy, câu đọc theo quy tắc 2 và 3 của `jig-n-rules`). Khi chưa có thì ghi "Chưa có", không ghi 0. Có test.
7. `withhold_eval` vẫn chặn kết quả thi lại của `C70_R1` ở mọi trang và trong chat. Test cũ vẫn qua.
8. `docs/console/api-contract.md` và `docs/console/api-samples/` cập nhật cho các khối mới trong `story.json` và `tasks.json`.
10. Run trong `withhold_runs` (hiện là N) không có mặt trong `data/story.json` (đường cong train, kết quả và rollout eval, tập cắt, phiên Colab, eval đang chạy, N trừ M), trong `data/tasks.json`, trong `/api/status` và danh sách run train của server, và trong câu trả lời của chat; kể cả khi index trên đĩa được dựng trước thay đổi này. Dòng tổng của sổ chi phí không đổi. Có test theo mẫu test của `withhold_eval`.
11. Trang Đánh giá có bảng 60 lượt theo quyết định 28/11/2026 câu 3: số của M là lượt lặp 0 đọc từ `outcomes.jsonl` và `scores.jsonl`, số của bốn run DA-34 đọc từ `stage1-*.json`; không có run nào thuộc `withhold_eval` hay `withhold_runs`; có câu nêu điểm khác; không có chữ "tốt hơn" hay "tăng X điểm". Cỡ hai bên khác nhau thì không dựng bảng. Có test.
9. `uv run ruff check`, `uv run mypy` (không thêm lỗi), `uv run pytest`, `uv run lint-imports`, `scripts/repo/check_links.py`, `scripts/repo/pr_guard.py` qua.

## Nhiệm vụ

- [x] 1.1 Viết story (file này)
- [x] 1.2 Hiếu chốt bốn câu; ghi quyết định vào file này (mục "Quyết định của Hiếu")
- [x] 1.3 Ghi quyết định 28/11/2026 về run N, thêm AC 10, 11 và nhiệm vụ 2.5, 2.6
- [x] 2.1 `index/tasks.py` và `seed/tasks.yaml`: vòng `tray-jig-r1`, đường dẫn theo run, ngưỡng và nguồn luật, có test (AC 1)
- [x] 2.2 `index/story.py`: đọc run train theo đường dẫn của từng run; sửa thời lượng pha VM, có test (AC 2, 5)
- [x] 2.3 Module mới trong `index/` đọc `results.json`, kiểm điều kiện trước khi đọc, ghi câu đọc theo luật, có test (AC 3, 4, 6)
- [ ] 2.5 Ẩn run N theo quyết định 28/11/2026: khóa `withhold_runs` của vòng `tray-jig-r1`, lọc ở index, server và chat, có test chứng minh N không lọt ra (AC 10)
- [ ] 2.6 Bảng 60 lượt: lượt lặp 0 của M cạnh `C_ALL`, `B_ALL`, `B_70`, `C_70`, kèm số các lượt và câu nêu điểm khác, số đọc từ file outcome (AC 11)
- [ ] 2.4 Giao diện: trang Train, Đánh giá, Vòng hiện vòng `tray-jig-r1`, chỉ cho run M (quyết định 28/11/2026); câu so với DA-34 có điểm khác đi kèm (AC 2, 3, 4, 7)
- [ ] 3.1 (Hiếu, vận hành) Ghi `results.json` của M cạnh outcome bằng lệnh đầu ở mục "Điều chỉnh sau khi đọc dữ liệu", rồi chạy `fw console index` (AC 3). Theo quyết định 28/11/2026 không ghi `results.json` của N và không kéo `metrics.jsonl` của N
- [ ] 3.2 Cập nhật hợp đồng API và mẫu; chạy đủ kiểm tra (AC 8, 9)

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-console/src/flywheel/console/index/` (`tasks.py`, `story.py` và một module mới đọc `results.json`)
- `packages/flywheel-console/src/flywheel/console/seed/tasks.yaml`
- `packages/flywheel-console/src/flywheel/console/server/runner.py`: chỉ `_train_dirs` (vòng không có `train_dir`) và dòng trạng thái đọc khối `story.jig`. Thêm ngày 28/11/2026 khi viết 2.1
- `packages/flywheel-console/src/flywheel/console/server/` và `packages/flywheel-console/src/flywheel/console/chat/` (chỉ cho nhiệm vụ 2.5: lọc run trong `withhold_runs`)
- `docs/console/ui-spec.md` (chỉ mục lọc dữ liệu bị giữ)
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

## Change log

| Ngày | Thay đổi | Người |
|---|---|---|
| 28/11/2026 | Ghi quyết định của Hiếu: không trình bày run N, chỉ trình bày run M và bảng 60 lượt so với các run DA-34. Thay câu 2 và 3 của mục "Quyết định của Hiếu"; AC 6 tạm không hiệu lực; thêm AC 10, 11, nhiệm vụ 1.3, 2.5, 2.6; 3.1 chỉ cho M, 2.4 chỉ dựng trang cho M; nới phạm vi file sang `server/`, `chat/` và `docs/console/ui-spec.md` | Hiếu (soạn với Claude) |

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
