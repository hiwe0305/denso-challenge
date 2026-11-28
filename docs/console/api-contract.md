# Hợp đồng API của Flywheel Console

Ngày viết: 25/11/2026; cập nhật 28/11/2026 cho vòng `tray-jig-r1` (story [DA-53](../product/stories/DA-53-console-hien-run-canh-do-ga.md): mục 1.2, 2, 2.1 và 3); cập nhật lần hai 28/11/2026 theo đợt đánh giá Console (nhánh `chore-console-index-data`: mục 1.3, 2, 2.1, 2.2 mới); cập nhật lần ba tối 28/11/2026 theo đánh giá chat (audit 05, nhánh `chore-console-latest-round`: mục 2 và 2.3 mới). Trạng thái: **[Đề xuất]**, chờ Hiếu duyệt.

File này mô tả mọi URL mà giao diện web của Console gọi tới server. Mục đích: xây lại giao diện (`packages/flywheel-console/src/flywheel/console/web/`) mà **không đổi server**. Giao diện mới chỉ được gọi các URL trong file này.

Nguồn sự thật là mã: [server/app.py](../../packages/flywheel-console/src/flywheel/console/server/app.py), [server/runner.py](../../packages/flywheel-console/src/flywheel/console/server/runner.py), [server/media.py](../../packages/flywheel-console/src/flywheel/console/server/media.py), [chat/llm.py](../../packages/flywheel-console/src/flywheel/console/chat/llm.py). Khi file này lệch với mã, mã thắng; sửa file này cho khớp.

JSON mẫu thật nằm trong [api-samples/](api-samples/). Cách lấy: chạy server trên `fwdata/` của laptop ngày 25/11/2026, rồi cắt mỗi danh sách còn 2 phần tử, cắt chuỗi dài, bỏ dòng catalog không `public`, thay đường dẫn máy bằng `fwdata/`, `~/` và `<repo>/`. `data_story.json` và `data_tasks.json` lấy lại ngày 28/11/2026 từ index dựng trên bản sao `fwdata` có `results.json` của run M (cắt danh sách còn 2 phần tử, trừ `readings` và `rounds`; cắt chuỗi quá 260 ký tự). Lần lấy thứ hai cùng ngày (đợt đánh giá) dựng index từ `fwdata` thật vào thư mục tạm, rồi thay các khóa đổi hình dạng: `ledger`, `colab_sessions`, `runs[]`, `jig.runs[]`, `jig.evals[]`, `jig.cost`, `diag` của `data_story.json`; `rounds` và `tasks[0].index` của `data_tasks.json`; `rounds` của `data_sim.json` (mỗi vòng cắt còn 2 episode). Lần lấy thứ ba (tối 28/11/2026) dựng bằng `fw console index` vào một `FW_ROOT` tạm (symlink tới `fwdata`, riêng `console/index` và `console/media`), rồi thêm `timeline`, `latest`, `next_steps`, `failure_table` và các trường `historical` của `diag`, `round` vào `data_story.json`; `default_round`, `index`, `rounds[].links`, `rounds[].scorer_version` vào `data_tasks.json`. Mẫu chỉ cho biết **hình dạng**, không phải số liệu để trình bày.

## 1. Quy tắc chung

| Quy tắc | Chi tiết |
|---|---|
| Địa chỉ | Server chỉ nghe `127.0.0.1`, cổng mặc định 4178 (`fw console serve --port 4178`). Giao diện gọi URL tương đối (`/api/...`, `data/...`), không ghi cứng host. |
| Host | Mọi GET cần header `Host` là `127.0.0.1:<cổng>` hoặc `localhost:<cổng>`; sai thì 403 `forbidden host`. Trình duyệt tự gửi đúng. |
| POST | Cần thêm `Origin` là `http://127.0.0.1:<cổng>` hoặc `http://localhost:<cổng>`; sai thì 403 `forbidden origin`. Thân JSON tối đa 1 MB. |
| Lỗi | Mọi lỗi trả JSON `{"error": "<thông điệp>"}` với mã 400, 403, 404, 411, 413, 500 hoặc 503. Thông điệp có thể là tiếng Việt. |
| Cache | Mọi `.json`, `.html`, `.js`, `.css` có `Cache-Control: no-cache`. |
| File tĩnh | Mọi file trả có `Accept-Ranges: bytes`, hỗ trợ `Range` (206, 416). Video phát được tua. |
| Thư viện ngoài | Console chạy offline. Không gọi CDN hay font ngoài; thư viện để trong `web/vendor/` (hiện có `echarts.min.js`). |

### 1.1. Chế độ khóa (`--lock`)

`fw console serve --lock` dùng cho máy demo. Giao diện biết chế độ này qua `GET /api/status` (trường `locked`, `chat_on`).

| Khi `locked: true` | Giao diện phải làm |
|---|---|
| Mọi POST trả 403 `locked`, trừ `/api/chat`, `/api/models/prewarm`, `/api/models/connect` khi `chat_on: true` | Ẩn nút chạy job, hủy job, upload, nhập dữ liệu |
| GET `/api/fs`, `/api/dir_check`, `/api/tool`, `/api/chat/traces`, `/api/chat/traces/<id>`, `/api/exports/<file>` trả 403 | Ẩn bộ chọn thư mục, nút gọi tool trực tiếp, trang trace, nút tải zip |
| Đường dẫn máy trong JSON đã bị thay: gốc dữ liệu thành `fwdata`, thư mục home thành `~/` | Hiển thị nguyên văn; khi gửi lại server (ví dụ `out=fwdata/...`) gửi đúng chuỗi đã nhận, server tự đổi ngược |

### 1.2. Kết quả bị giữ lại (`withhold_eval`)

Vòng có danh sách `withhold_eval` trong [seed/tasks.yaml](../../packages/flywheel-console/src/flywheel/console/seed/tasks.yaml) (hiện là `C70_R1`, quyết định của Hiếu 16/11/2026). Kết quả thi lại của các run này **không được trình bày** ở bất kỳ trang, biểu đồ hay tooltip nào.

- Server đã bỏ các khối kết quả của run này khỏi `data/story.json` trước khi gửi ([server/withhold.py](../../packages/flywheel-console/src/flywheel/console/server/withhold.py)).
- Giao diện mới **vẫn phải lọc lần nữa** theo `rounds[].withhold_eval` của `data/tasks.json`, giống hàm `unhide` trong `web/core.js` hiện tại: bỏ run khỏi `pair.runs`, bỏ so sánh có run đó khỏi `pair.comparisons`, bỏ khóa run khỏi `follow.runs`, xóa `follow.r3`, xóa `demo.round1_reading`, bỏ khóa run khỏi `demo.ladder.runs` và `demo.ladder.on_table_b.value`. Trong khối `jig` (mục 2.1): mục của run trong `evals` chỉ còn `{run, role, status: "withheld"}`, run bị bỏ khỏi `outcomes`, `rollouts`, `conditions` và `compare60.earlier`, `featured` không trỏ tới nó (hàm `filterWithheldStory` của `web/core.js`).
- Thông tin train, bản cắt dữ liệu và chi phí của run vẫn được hiện.

### 1.3. Run bị ẩn (`withhold_runs`)

Vòng có danh sách `withhold_runs` trong [seed/tasks.yaml](../../packages/flywheel-console/src/flywheel/console/seed/tasks.yaml) (hiện là run `N` của vòng `tray-jig-r1`, quyết định của Hiếu 28/11/2026, story [DA-53](../product/stories/DA-53-console-hien-run-canh-do-ga.md)). Khác `withhold_eval`, run này **không được trình bày gì cả**: không đường cong train, tập cắt, phiên Colab, eval đang chạy, kết quả eval hay phép so với run khác.

- Index không ghi run này. Server lọc thêm `data/story.json` và `data/tasks.json` trước khi gửi, kể cả khi index trên đĩa được dựng trước thay đổi ([index/hidden.py](../../packages/flywheel-console/src/flywheel/console/index/hidden.py); danh sách đọc từ seed, không từ index).
- `data/tasks.json`: run bị bỏ khỏi `rounds[].runs`; vòng có run sau vòng bị ẩn ghi `after_round: null`; không có khóa `withhold_runs`.
- `data/story.json`: run bị bỏ khỏi `runs`, `colab_sessions` (theo mẫu tên phiên) và mọi phần của khối `jig` (`runs`, `evals`, `outcomes`, `rollouts`, `conditions`, `cuts`, `live_evals`, `active_sessions`, cụm `agentqa`); `jig.paired`, `jig.next_cut`, `jig.n_ckpt_done` là `null`.
- `/api/status` (danh sách run train, máy Colab) và chat cũng không có run này. Số của sổ chi phí (`ledger`) giữ nguyên vì đó là tiền đã tiêu.
- Một mục của `withhold_runs` có thể kèm `stories` (hiện `DA-50`, story của run N). Quyết định Q1 của Hiếu, 28/11/2026: dòng sổ chi phí của các story này gộp vào **một** dòng `{story: "other", label: "Thí nghiệm khác (không trình bày)"}` ở cuối `ledger`, giữ đúng số (mục 2.2); dòng catalog của các story này, hay có chữ nhắc run bị ẩn (ví dụ `analysis/da50-clean` trong `notes`), bị bỏ khỏi `data/catalog.json`, `story.ds`, `tasks[].catalog_rows` và không có thư mục `data/ds/<id>/`; `parents`, `children` và cạnh trỏ tới chúng cũng bị bỏ. Hiện là 4 tập (`tray_s1_02d895d28050`, `tray_s1_2c861cdfe7fd`, `tray_s1place_6a7b780fb66b`, `tray_s1place_e793fb05a9df`). `docs/g0/ledger` không đổi. Với index dựng trước thay đổi này, server lọc lúc phục vụ: `hidden.story` cho `ledger` qua `hidden.ledger` (dòng DA-50 gộp vào `other`); `hidden.catalog_doc(doc, h)` bỏ các dòng ấy khỏi `data/catalog.json` (hay `story.ds`) và tính lại `totals`; `hidden.catalog_hidden_ids(doc, h)` cho tập id để server trả 404 cho `/data/ds/<id>/...` và bỏ chúng khỏi `tasks[].catalog_rows`.
- Giao diện không cần lọc thêm, nhưng phải chịu được `after_round: null`, `jig.paired: null`, `jig.next_cut: null` (không hiện "undefined", không hiện khung trống).

## 2. File chỉ mục (đọc, không có tham số)

Do `fw console index` tạo trong `fwdata/console/index/`, server phục vụ ở `/data/`. Giao diện tải các file này khi mở trang.

| URL | Mẫu | Nội dung |
|---|---|---|
| `data/tasks.json` | [data_tasks.json](api-samples/data_tasks.json) | `{version, source, tasks[], rounds[]}`. Mỗi task: `id` (`tray`, `two_table`…), `name`/`word`/`description` song ngữ `{vi, en}`, `robot`, `model`, `simulator`, `stages[]`, `success`, `rounds[]` (id vòng), `index[]` (khóa của `story.json` mà task được thấy), `process` (stage 0–6: thiếu gì, chạy ở đâu, lệnh), `catalog_totals`, `catalog_rows`. Mỗi round: `id`, `task`, `number`, `title`, `doc`, `eval`, `runs[]`, `baseline`, `after_round` (có thể `null`, mục 1.3), `controls[]` (có thể rỗng), `withhold_eval[]`, `follow`, `max_steps`, `log_run`, `index[]`. Vòng đọc một thư mục (`tray-r1`) có thêm `train_dir`, `eval_dir`, `cut`, `rollouts`; vòng trên cảnh đồ gá (`tray-jig-r1`) có thêm `scene`, `eval_set`, `conditions_sha256`, `rollouts_expected`, `scorer_version`, `rules` (`whole_task`, `per_level`, `place`, `read_at`, `source{vi,en}`), và mỗi run của nó có `train`, `stats`, `outcome`, `cut`, `bootstrap_seed`, `rules_block`, `results_cmd`. Thứ tự `tasks[].rounds` là thứ tự thời gian và thứ tự của bộ chọn vòng: `tray-r1`, rồi `tray-jig-r1`. Vòng mặc định là `tasks[].default_round` (chuỗi; `tray`: `tray-jig-r1`, vòng của kết quả trình bày mới nhất, run M), **không** phải `rounds[0]` (quyết định của Hiếu tối 28/11/2026, audit 05 mục 6, thay Q2 của sáng cùng ngày). Mỗi round có `links = {prev, next}` (mục 2.3) và `scorer_version` (`tray-r1`: 1, `tray-jig-r1`: 2). `story.eval` (đánh giá cũ của policy C ở 40k bước, trước vòng 1) và `story.diag` nằm trong `index[]` của vòng `tray-r1`, không ở cấp task. Khóa `sim` có ở cả hai vòng (xem `data/sim.json`). Vòng `tray-jig-r1` có thêm `cut` (tập dạy của M, `da48/cuts/M.tar`) và `cost_stories` (`{train: DA-48, eval: DA-47}`, nguồn của `jig.cost`). Run trong `withhold_runs` không có mặt (mục 1.3) |
| `data/catalog.json` | [data_catalog.json](api-samples/data_catalog.json) | `{generated, rows[], edges[], runs[], totals}`. Mỗi row là một tập dữ liệu: `id`, `title`, `kind`, `group`, `data_type`, `task`, `episodes`, `frames`, `hours`, `fps`, `format`, `licence`, `data_class`, `status`, `parents[]`, `children[]`, `view`, `thumbs[]`. `edges` là cặp `[cha, con]` của cây nguồn gốc. `totals` theo nhóm (`egocentric`, `teleop`, `s1`, `s2`, `all`) |
| `data/story.json` | [data_story.json](api-samples/data_story.json) | Số liệu cho các trang câu chuyện: `runs`, `train_log_tail`, `sources`, `heat`, `reasons`, `ledger` (mục 2.2), `colab_balance`, `colab_sessions`, `eval`, `loop_chain`, `loop_detail`, `pair`, `round`, `follow`, `demo`, `h1m`, `ds`, `vm_phases`, `qa_sample`, `jig` (vòng trên cảnh đồ gá, mục 2.1), `diag` (chẩn đoán vòng 1, mục 2.2), `timeline`, `latest`, `next_steps`, `failure_table` (diễn tiến dự án, mục 2.3; ở `index[]` cấp task). Mỗi mục của `runs[]` (và `jig.runs[]`) có `samples_per_s` (mẫu/giây, trung vị 50 dòng cuối của `throughput`), `global_batch_size` (từ `launch.json`) và `steps_per_s` (`samples_per_s / global_batch_size`, `null` khi thiếu batch); `thr_med` giữ lại, cùng giá trị với `samples_per_s`, **không** phải bước/giây. Thư mục `<run>.attempt*` (lần chạy dừng sớm) không phải run và không có trong `runs[]`. `colab_sessions[]`: `{session, gpu, state, cap, batch, beat}`, một mục mỗi tên phiên, lấy từ mọi thư mục `colab/batch-*` (bản ghi có `beat` mới nhất). `beat` là nhịp cuối của watcher (UTC, `YYYY-MM-DDTHH:MM:SSZ`, hay `null`). `state` giữ nguyên trạng thái cuối, trừ trạng thái đang chuyển (`starting`, `running`, `stopping`) mà `beat` cũ hơn 600 giây (`colab.STALE_AFTER_S`, bằng mặc định `cu_watch guard --stale`) hay không có: khi đó `state` là `stale`, nghĩa là watcher đã chết, **không** phải đang chạy. Server tính lại quy tắc này lúc gửi file (`hidden.story`), nên index dựng lâu rồi cũng không hiện phiên cũ là đang chạy. Phiên serve và eval của run trong `withhold_eval` (mẫu `*serve*<session>*`, `*eval*<session>*`, ví dụ `da34-serve-c70r1-1`) không có trong mọi danh sách phiên; phiên train của run đó vẫn hiện. Mỗi task chỉ được đọc các khóa có trong `index[]` của task và round (`story.<khóa>`); không hiện số của task khác. `runs`, `train_log_tail`, `vm_phases` thuộc `index[]` của vòng `tray-r1`; vòng `tray-jig-r1` chỉ có `story.jig` và đọc ba khối này trong `jig`. Trong `vm_phases` (và `runs[].vm_phases`), `setup*` và `train` là thời lượng của pha; `persist` chạy song song với `train`, nên giá trị là phần đồng bộ sau train (`persist − train`), không phải mốc cộng dồn |
| `data/sim.json` | [data_sim.json](api-samples/data_sim.json) | Tập episode mô phỏng: `source`, `sha8`, `parts[]`, `cuts{}`, `batch{}`, `episodes[]`, `round`, `format`, `teleop[]`, `rounds{}`. `rounds` có một khối mỗi vòng liệt kê `sim` (`tray-r1`: tập cắt `C70_R1`; `tray-jig-r1`: tập cắt của M, 1 037 episode, các phần đều là `coverage`), cùng các khóa `source`, `round`, `sha8`, `parts`, `cuts`, `format`, `batch`, `episodes`. Các khóa ở cấp trên là bản sao khối của vòng đầu (`tray-r1`), giữ cho trang cũ. Giao diện đọc `rounds[<vòng đang chọn>]` khi có. `cuts` không bao giờ có run bị ẩn. Task không có khóa `sim` trong `index[]` chỉ thấy `teleop[]` lọc theo task |
| `data/ds/<id>/episodes.json` | (không có mẫu) | Danh sách episode của một tập; đây là nguồn số episode cho `#/data/:id/ep/:n`. Tập robot (do [index/robot.py](../../packages/flywheel-console/src/flywheel/console/index/robot.py) viết): `i`, `n`, `s` (giây), `lv`, `seed`, `part`, `cut`, `out`… Tập egocentric và nguồn: `id`, `title`, `s`, `qa`, `reasons`, `poster`… Tập robot chỉ có khi laptop có dữ liệu LeRobot lúc chạy `fw console index` |
| `data/ds/<id>/quality.json`, `method.json`, `qa.json`, `env.json` | (không có mẫu) | Chất lượng, cách tạo tập, kết quả QA từng episode, môi trường (chỉ tập robot); file nào thiếu thì khối đó rỗng |
| `data/ds/<id>/posters/<i>.jpg` | | Ảnh đại diện từng episode |

### 2.1. Khối `jig`: vòng trên cảnh đồ gá

Khối của vòng có `story.jig` trong `index[]` (`tray-jig-r1`, story DA-53). Hình dạng đầy đủ ghi trong docstring của [index/jig.py](../../packages/flywheel-console/src/flywheel/console/index/jig.py); vòng không có khối thì `jig` là `{}`. Theo quyết định của Hiếu ngày 28/11/2026, khối chỉ có run M: run N nằm trong `withhold_runs` (mục 1.3).

| Trường | Nội dung |
|---|---|
| `round`, `scene`, `doc`, `source` | Id vòng, cảnh (`jig2`), tài liệu, nguồn |
| `rules` | Ngưỡng của luật đọc, chép từ `tasks.yaml`: `whole_task`, `per_level`, `place`, `read_at` (`lower_bound`), `source{vi,en}` (khối `jig-m-rules` của [tray-jig.md](../he/tray-jig.md) mục 2). Trang hiện nguồn này cạnh câu đọc và không viết cứng ngưỡng |
| `eval_set`, `rollouts_expected`, `scorer_version` | Tập điều kiện (`path`, `conditions_sha256`, `sha_ok`), số rollout khai báo (180), bản bộ chấm (2) |
| `runs[]` | Mục train của từng run, như `story.runs[]`: `job`, `branch` (`M`), `step`, `ckpt_step`, `max_steps`, `loss_last`, `val_last`, `samples_per_s`, `steps_per_s`, đường cong `loss`/`val`/`thr` (mẫu/giây)/`vram`/`gn`, `vm_phases`, `log_tail`, `scene`, và `fetched_final`, `fetched_train`, `fetched_step` (bản `metrics.jsonl` trên laptop). File chỉ là bản chưa đủ khi `fetched_final` là `false` và `fetched_train` khác `"done"`. Không có kết quả eval ở đây |
| `log_run`, `train_log_tail`, `vm_phases` | Run có log VM (`M`) và log, pha của nó |
| `evals[]` | Một mục mỗi run được hiện: `run`, `role`, `status`, `results_source`. `status`: `ready` (đủ điều kiện đọc), `blocked` (có số, `problems` nêu điều kiện thiếu, mọi câu đọc `null`), `missing` (chưa có `results.json`: chỉ có `command` là lệnh ghi file, không có số, trang ghi "Chưa có", không ghi 0), `withheld` (run trong `withhold_eval`: chỉ `run`, `role`, `status`). Khi `ready` hoặc `blocked`: `headline` và `levels{"1","2"}` (`n`, `conditions`, `successes`, `p`, `ci` bootstrap theo điều kiện, `wilson` và `wilson_method` chỉ mô tả, `failures`, `step_pass`; chép nguyên từ `results.json`), `place{p, successes, n, ci}` (`ci` chép từ `headline.step_ci.place` của `results.json`, `null` khi file không có), `bootstrap_seed`, `scorer_version`, `plan_mismatch`, `readings[]` |
| `evals[].readings[]` | `{rule, scope, level?, threshold, lower, verdict, why?}`. `scope`: `whole_task` (quy tắc 1), `level` (quy tắc 2, có `level`), `place` (quy tắc 3). `verdict`: `met` khi cận dưới CI 95 % **`>=`** ngưỡng (`lower >= threshold`, cả hai làm tròn 9 chữ số thập phân; bằng ngưỡng là đạt), `not_met` khi `lower < threshold`, hoặc `null` kèm `why`: `blocked` (file chưa đủ điều kiện) hay `no_ci` (bước đặt: `results.json` không có `headline.step_ci.place`, trang hiện tỉ lệ và không có câu đọc). Khi có khoảng tin cậy, quy tắc 3 đọc cận dưới như quy tắc 1 và 2 (ngưỡng `place` 0,50). Câu chữ là của trang. Chat **trích** `readings[].verdict` của index, không tự so cận dưới với ngưỡng |
| `cost` | Chi phí của vòng, từ sổ chi phí: `{train: {...}, eval: {...}, total_cu}`. Mỗi phần: `story` (`DA-48`, `DA-47`), `label`, `cu`, `usd`, `measure_kind` (`measured` khi sổ có dòng thực đo, nếu không thì `estimated`), `est_cu`, `source` (file CSV), `doc{value, source, quote}` (số trích của [tray-jig.md](../he/tray-jig.md) mục 4 và 5), `matches_doc`. Hiện: train 56,15 CU, eval 6,8 CU, đều thực đo |
| `paired` | `null` (phép N trừ M không trình bày, AC 6 tạm không hiệu lực) |
| `featured` | Run có eval `ready` mà trang tổng quan và trang Đánh giá đặt lên đầu (`M`), hoặc `null` khi chưa có |
| `steps`, `outcomes[]`, `rollouts[]`, `conditions[]` | Mô tả đọc từ `scores.jsonl` và `outcomes.jsonl` của thư mục outcome, không có khoảng tin cậy hay câu đọc: tỉ lệ qua từng bước, nhãn lỗi, phân bố lặp lại, đường cong nới dung sai, sai số đặt từng rollout, từng điều kiện. Trang chỉ hiện các khối này khi eval của run là `ready` hoặc `blocked` |
| `cuts{run: {name, files, bytes, source}}`, `m_cut` | Tập dạy của run (`M.tar.json`); `m_cut` là của baseline |
| `next_cut`, `n_ckpt_done` | `null` (của run sau vòng, đang bị ẩn) |
| `live_evals[]`, `active_sessions[]`, `agentqa[]` | Eval đang chạy, phiên Colab đang chạy, gói Agent QA trên các run `jig-*`; không có gì của run bị ẩn hay phiên serve/eval của run bị giữ kết quả. `live_evals[]` và `active_sessions[]` chỉ có phiên còn nhịp trong 600 giây (mỗi mục có `beat`; nhịp của watcher eval là `beat` của bản ghi serve, nếu thiếu thì mtime của `watch.log`); phiên `stale` bị bỏ cả lúc dựng lẫn lúc server gửi. Danh sách rỗng nghĩa là không có phiên nào đang chạy |

Hai trường cho bảng 60 lượt (story DA-53, AC 11, quyết định của Hiếu 28/11/2026):

| Trường | Nội dung |
|---|---|
| `jig.outcomes[].repeats` | `[{repeat, n, successes, levels: {"1": {n, successes}, "2": {...}}}]`, một phần tử cho mỗi lượt lặp. Lượt lặp đọc từ trường `repeat` của dòng `outcomes.jsonl` có cùng `episode_id` với dòng `scores.jsonl`. Hai file không khớp một-một theo `episode_id` thì không có trường này (không đoán) |
| `jig.compare60` | `null`, hoặc `{run, repeat: 0, n, successes, p, levels, repeats: [{repeat, n, successes}], scorer_version, source: {scores, outcomes}, earlier: [{run, n, successes, p}], earlier_scorer, earlier_source, earlier_doc}`. `run` là baseline của vòng (M); số là lượt lặp 0, chọn trước theo số thứ tự, không phải lượt cao nhất. `earlier` lấy từ `pair.runs` của vòng `tray-r1`, chỉ baseline và các run đối chứng, theo thứ tự hiện của vòng, không bao giờ có run trong `withhold_eval` hay `withhold_runs`. `earlier_scorer` là `null` khi file stage 1 không ghi bộ chấm; trang ghi "bộ chấm bản 1". Khối là `null` khi chưa có lượt lặp 0 hoặc có run trong `earlier` khác cỡ `n` |

Khối chỉ mô tả: không có hiệu, khoảng tin cậy hay câu đọc (quy tắc 4 của `jig-m-rules` trong [tray-jig.md](../he/tray-jig.md)). Trang luôn kèm câu nêu điểm khác (cảnh, bộ chấm, tập điều kiện, số bước train) và không dùng chữ "tốt hơn" (test `test_no_dictionary_value_ranks_runs` kiểm cả hai từ điển).

### 2.2. Sổ chi phí (`ledger`) và chẩn đoán vòng 1 (`diag`)

Hai hợp đồng mới của đợt đánh giá 28/11/2026. Trang Chi phí, trang Chẩn đoán và chat đọc đúng các tên trường dưới đây.

| Trường | Nội dung |
|---|---|
| `ledger[]` | Một mục mỗi file CSV của `docs/g0/ledger`: `{story, label, est_cu, mea_cu, est_usd, mea_usd}`. `label` là tiêu đề của file story (`docs/product/stories/<story>-*.md`), `null` khi không có file. CU cộng cột `quantity` của các dòng có `unit` là `compute_unit`; USD cộng `amount_usd` của mọi dòng. Ước tính và thực đo là hai cột riêng; một phía không có dòng nào là `null`, không phải 0. Dòng cuối có thể là `{story: "other", label: "Thí nghiệm khác (không trình bày)"}`: tổng các story bị ẩn (mục 1.3), cùng số. Ví dụ DA-34: ước tính 784,8 CU, thực đo 148,82 CU |
| `diag.round`, `diag.source` | `tray-r1`; các mục của [tray.md](../he/tray.md) mà số được trích (qua `seed/cited.yaml`) |
| `diag.clusters[]` | Cụm c1–c8 (tray.md 20.2): `{id, key: {step, label, level}, n_fail, diagnosis, intervention, gets_data, source[], quote}`. `diagnosis` lấy từ 20.13 (cụm nhận dữ liệu) hay 20.11 (cụm thành phiếu); `gets_data` là `true` cho c1, c2, c3, c8. `diagnosis_en`, `intervention_en`: bản tiếng Anh, cùng nghĩa, không thêm số |
| `diag.step4[]` | Kiểm hệ thống H1–H3 (tray.md 20.11, R8 ở 20.9): `{id, claim, clusters[], verdict, ticket, source, quote}`. `ticket` là `DA-37`, `null` hay `DA-38`. `claim_en`, `verdict_en`: bản tiếng Anh |
| `diag.*_en` | Chữ trong `diagnosis`, `intervention`, `claim`, `verdict` là tiếng Việt của tài liệu (`quote` giữ nguyên tiếng Việt). Trường `*_en` đi kèm ghi trong `seed/cited.yaml`, dịch sát nghĩa, không đổi số (test kiểm). Chat đọc `*_en` khi `lang = en` |
| `diag.gen_qa_cost` | `{host: "rtx3060", cu: 0, diagnosis_cu: 0, generation: {attempts, recorded, hours}, qa: {hours, qa_pass, quality}, selected, train_serve_cu, train_serve_parts: {train_1, train_2, serve}, source[]}`. Thu dữ liệu (sinh, QA, chọn, cắt) 0 CU; train và serve của `C70_R1` 109,22 CU (8,55 + 77,27 + 23,4, tray.md 20.18). Trống khi seed thiếu một khóa trích |

### 2.3. Diễn tiến dự án, vòng mới nhất và bảng nhãn lỗi

Quyết định của Hiếu tối 28/11/2026 (audit 05 mục 6): Console mở ở vòng mới nhất; trang Tổng quan nối hai vòng hai chiều; chat biết diễn tiến từ 18/11 tới nay và kết quả trình bày mới nhất. Số nào cũng lấy từ index hay từ tài liệu có trích dẫn, không gõ tay.

| Trường | Nội dung |
|---|---|
| `tasks[].default_round` | Vòng mở mặc định (`tray-jig-r1`). Seed kiểm nó là một vòng của task |
| `rounds[].links` | `{prev: L\|null, next: L\|null}` theo thứ tự `tasks[].rounds`. `L = {round, run, successes, n, scene_differs, scorer_differs}`: `run` là baseline của vòng kia, `successes`/`n` là kết quả nó trình bày (vòng 1: `story.pair`, vòng đồ gá: eval baseline `ready` của `story.jig`; `null` khi chưa có), `scene_differs`/`scorer_differs` so `scene`/`scorer_version` của hai vòng. Khi vòng kia là `tray-r1`, `L` có thêm `carried` (khay tới bàn B) và `placed` (đặt trong dung sai, tức thành công) lấy từ `story.demo.ladder`. Hiện: `tray-r1.next` = M 136/180; `tray-jig-r1.prev` = C_70 10/60, `carried` 50, `placed` 10. Link tới run bị ẩn là `null` |
| `timeline[]` | `{date: "YYYY-MM-DD", story, title{vi,en}, result{vi,en}\|null, doc: "docs/… §x", round\|null}`, xếp theo ngày, đọc từ `seed/timeline.yaml`. Mỗi mục trích tài liệu như `cited.yaml`: câu trích có nguyên văn trong tài liệu, mọi số của `result` có trong câu trích (hay là tổng liệt kê trong `sums`), `en` cùng số với `vi` (test kiểm). Hiện 6 mục: DA-34 vòng 1 (12/11), DA-42 bộ chấm bản 2 (19/11), DA-41 cảnh đồ gá và lô 568 episode (22/11), DA-46 612 bản cắt, M dùng 539 (25/11), DA-48 train M (26/11), DA-47 eval M 136/180 (26/11). Không bao giờ có DA-50, run N, `da50`, `jig-n` hay kết quả thi của `C70_R1`; `hidden.story` bỏ mục như vậy nếu có |
| `latest` | `{round, run, date}`: vòng mới nhất (theo thứ tự `rounds`) có baseline đã có eval trình bày, và ngày của mục `timeline` mới nhất của vòng đó. Hiện `{round: "tray-jig-r1", run: "M", date: "2026-11-26"}`; `null` nếu run bị ẩn |
| `next_steps[]` | `{text{vi,en}, doc, round}`, từ seed, có trích. Hiện một mục: train run đối chứng K (498 episode đầy đủ, không có bản cắt, cùng cảnh `jig2` và tập điều kiện) để tách phần do đồ gá và phần do dữ liệu bước đặt ([tray-jig.md](../he/tray-jig.md) mục 1, quy tắc 5 của mục 2). Không lấy gì từ mục 6–9 (run N) |
| `historical`, `closed`, `handled_by` | Trên mục của `round.clusters[]`, `diag.clusters[]`, `diag.step4[]`, `demo.diagnose.checks[]` có phiếu của vòng 1: `historical: true` nghĩa là lịch sử, chat **không bao giờ** đề xuất nó là việc tiếp theo. DA-38: `closed: "2026-11-06"` (PR #80). DA-37: `closed: null`, `handled_by: "DA-42"` (DA-42 nhận phiếu của tray.md 20.11; story DA-37 vẫn ghi "Đang làm"). Hàng chẩn đoán giữ nguyên |
| `failure_table` | `{<round>: {scorer_version, runs: {<run>: {labels: {<nhãn>: số}, failed, n}}}}`, cùng số với trang Đánh giá: vòng 1 từ `story.pair.runs[]`, vòng đồ gá từ eval `ready` của `story.jig`. `labels` xếp theo số giảm dần; `failed = n − successes`. Run trong `withhold_eval` (`C70_R1`) và run bị ẩn không có mặt. Hiện: C_ALL 55, C_70 50, B_ALL 54, B_70 53 trên 60 (bộ chấm 1); M 44 trên 180 (bộ chấm 2) |

## 3. API đọc (GET)

| URL | Tham số | Trả về | Mẫu | Khi khóa |
|---|---|---|---|---|
| `/api/status` | | Trạng thái 6 stage của vòng (`collect`, `process`, `release`, `train`, `eval`, `loop`; mỗi cái có `state` = `idle`/`running`/`done`/`blocked`/`waiting`, `now`, `issue`, `how`, `jobs[]`, `link`; `eval.now` thêm `Cảnh jig2: <run> <đạt>/<n>` chỉ khi `jig.featured` có eval `ready`), 10 job gần nhất, `machines` (`laptop.slots`, `rtx3060.tunnel`, `colab.balance`), `locked`, `chat_on` | [api_status.json](api-samples/api_status.json) | được |
| `/api/kinds` | | Danh mục loại job chạy được: `kinds[]` (`kind`, `stage`, `title`, `command`, `args[]` mô tả form, `samples[]` tham số gợi ý, `available`, `reason`, `typical_seconds`) và `remote[]` (việc chạy ở Colab hoặc 3060, chỉ để giải thích) | [api_kinds.json](api-samples/api_kinds.json) | được, `available` thành false |
| `/api/jobs` | `limit` (mặc định 100) | Danh sách job, mới nhất trước: `id`, `kind`, `stage`, `task`, `params`, `argv`, `state` (`queued`/`running`/`ok`/`failed`/`cancelled`), `rc`, `created`, `started`, `ended`, `seconds`, `outputs`, `note` | [api_jobs.json](api-samples/api_jobs.json) | được |
| `/api/jobs/<id>` | | Một job như trên, thêm `tail` (dòng log cuối) | | được |
| `/api/jobs/<id>/log` | `offset` (byte) | `{text, offset, state}`; gọi lại với `offset` mới để đọc tiếp, tối đa 1 MB mỗi lần | | được |
| `/api/works` | | Thư mục làm việc của pipeline dữ liệu: `name`, `path`, `source_detail`, `episodes`, `tiers[]` (6 tầng, mỗi tầng `state`, `n`, `total`, `result`), `summary` | [api_works.json](api-samples/api_works.json) | được |
| `/api/work_episodes` | `work` | Episode của một work dir: `episode_id`, `deid`, `frames`, `qa` | | được |
| `/api/artifacts` | | File kết quả cho Agent QA/QC: `label`, `path`, `kind` | [api_artifacts.json](api-samples/api_artifacts.json) | được |
| `/api/agent_result` | `out` (thư mục) | Kết quả một lần chạy Agent QA/QC | | được |
| `/api/agent_stats` | | Thống kê Agent QA/QC: `runs[]`, `findings`, `last_job` | [api_agent_stats.json](api-samples/api_agent_stats.json) | được |
| `/api/estimates` | | Các bản ước tính chi phí egocentric: `path`, `label` | [api_estimates.json](api-samples/api_estimates.json) | được |
| `/api/exports` | | File zip đã xuất: `name`, `size`, `url`, `time` | [api_exports.json](api-samples/api_exports.json) | được |
| `/api/exports/<file>.zip` | | Tải file zip (`application/zip`) | | **403** |
| `/api/models` | | Model chat: `tunnel` (`up`/`down`), `models[]`, `agent_model`, `agent_ready`, `nemotron`, `chat` (`provider`, `model`, `hosted`) | [api_models.json](api-samples/api_models.json) | được |
| `/api/tools` | `route` (trang hiện tại) | Tool của chat: `name`, `description`, `parameters` (JSON Schema), `slash` | [api_tools.json](api-samples/api_tools.json) | được |
| `/api/tool` | `name`, `args` (JSON đã url-encode), `route` | Gọi trực tiếp một tool (lệnh `/slash`), trả kết quả của tool | | **403** |
| `/api/chat/bench` | | Kết quả benchmark chat gần nhất; 404 khi chưa chạy | [api_chat_bench.json](api-samples/api_chat_bench.json) | được |
| `/api/chat/traces` | `limit` (mặc định 20) | Các lượt chat gần đây: `turn_id`, `question`, `tools[]`, `ms_total`, `tokens_in`, `tokens_out`, `error` | [api_chat_traces.json](api-samples/api_chat_traces.json) | **403** |
| `/api/chat/traces/<turn_id>` | | Chi tiết một lượt; 404 khi không có | | **403** |
| `/api/fs` | `path` | Liệt kê thư mục cho bộ chọn đường dẫn (ẩn `vault/`, `holdout`, file ẩn) | | **403** |
| `/api/dir_check` | `path` | Kiểm một thư mục có dùng được làm nguồn nhập không | | **403** |

### 3.1. Media (ảnh, video, dữ liệu robot)

| URL | Tham số | Trả về |
|---|---|---|
| `/api/episode` | `ds` (id tập), `ep` (số episode) | JSON chuỗi thời gian của một episode robot: `ds`, `ep`, `n`, `fps` (50), `hz` (10), `t[]`, `action{nhóm: {names[], v[][]}}`, `state{hand, arm, leg, torso_rpy}`. 404 `episode not on disk` khi thiếu file |
| `/api/strip` | `ds`, `ep` | Ảnh JPEG dải khung hình của episode robot |
| `/api/poster` | `work`, `ep`, `w` (rộng, mặc định 320) | JPEG một khung từ video egocentric **đã che danh tính**; 404 khi chưa có `*.deid.mp4` |
| `/api/ego_strip` | `work`, `ep`, `n` (số khung, mặc định 8) | JPEG dải khung egocentric đã che danh tính |
| `/media/<ds>/<đường dẫn>` | | File của một tập dữ liệu (video mp4 hỗ trợ `Range`) |
| `/simmedia/...`, `/demomedia/...` | | Video mô phỏng và video demo |
| `/ego/` | | Trang Egocentric Explorer có sẵn, mở trong iframe hoặc tab riêng; dữ liệu ở `/ego/data/index.js` |

Giao diện không bao giờ tự dựng URL tới video egocentric gốc; chỉ dùng các URL trên.

## 4. API ghi (POST)

Mọi POST gửi `Content-Type: application/json` (trừ upload) và bị chặn khi khóa (mục 1.1).

| URL | Thân | Trả về |
|---|---|---|
| `/api/jobs` | `{"kind": "<kind trong /api/kinds>", "params": {...}}`; tên và kiểu tham số lấy từ `args[]` của kind đó, gợi ý lấy từ `samples[].params` | 201 và job vừa tạo (như `/api/jobs/<id>`); 400 khi tham số sai, thông điệp nói trường nào |
| `/api/jobs/<id>/cancel` | không cần | Job sau khi hủy; 404 khi không có |
| `/api/upload?dir=upload-YYYYMMDD-HHMM&task=<task>` | Thân là **byte của file video**, header `X-Filename` (tên file, url-encode) và `Content-Length` | 201 `{saved, dir, name, as, size}`. Chỉ nhận đuôi video; tối đa 8 GB; 411 khi thiếu `Content-Length` |
| `/api/models/prewarm` | không cần | Nạp sẵn model chat |
| `/api/models/connect` | không cần | Mở tunnel SSH tới rtx3060 (tối đa 15 giây), trả như `/api/models` |
| `/api/chat` | Xem mục 5 | Luồng SSE |

Theo dõi một job: sau POST, gọi `/api/jobs/<id>/log?offset=<n>` lặp lại (khoảng 1 giây) đến khi `state` không còn là `queued` hoặc `running`.

## 5. Chat (`POST /api/chat`, luồng SSE)

Thân gửi:

```json
{
  "conversation_id": "c-5381bb54",
  "messages": [{"role": "user", "content": "Nên làm gì tiếp theo?"}],
  "context": {"route": "#/home", "selection": null}
}
```

- `conversation_id` bỏ trống ở lượt đầu; lấy từ sự kiện `trace_start` cho các lượt sau.
- `messages` là lịch sử, gửi tối đa 8 tin gần nhất.
- `context.route` là trang đang mở; `context.selection` là thứ người dùng đang chọn (nếu có).

Server trả `text/event-stream`. Mỗi sự kiện có dạng `event: <tên>\ndata: <JSON>\n\n`. Đóng kết nối (hủy `fetch`) thì lượt chat dừng. Dùng `fetch` và đọc `response.body`, không dùng `EventSource` (vì là POST).

| Sự kiện | `data` | Giao diện làm gì |
|---|---|---|
| `trace_start` | `conversation_id`, `turn_id`, `tools_offered[]` | Lưu `conversation_id` |
| `tool_start` | `call_id`, `name`, `args` | Hiện khung "đang gọi tool" |
| `tool_result` | `call_id`, `name`, `ok`, `ms`, `ui` (mô tả khối để vẽ kết quả), `model_chars`, có thể có `navigate` (route nên mở) | Thay khung của `call_id` bằng kết quả; có `navigate` thì đề nghị chuyển trang |
| `token` | `text` | Nối vào câu trả lời đang hiện |
| `done` | `turn_id`, `ms_total`, `tokens_in`, `tokens_out`, `numbers[]` (`text`, `grounded`), `unverified[]` | Kết thúc lượt; đánh dấu các số trong `unverified` là chưa kiểm |
| `error` | `message`, `fallback` (`"slash"` nghĩa là lệnh `/slash` vẫn dùng được) | Hiện lỗi, gọi lại `/api/models` để cập nhật trạng thái model |

Khi model hosted (`/api/models` → `chat.hosted: true`), server tự không cho tool thấy các dòng catalog không `public`. Giao diện không cần làm gì thêm, nhưng nên hiện rõ đang dùng model nào.

## 6. Việc giao diện mới không được làm

- Không gọi URL ngoài file này, không gọi trực tiếp Ollama, Colab hay rtx3060.
- Không đọc `vault/`, đường dẫn có `holdout`, hay video egocentric chưa che danh tính.
- Không trình bày kết quả của run trong `withhold_eval` (mục 1.2), và không trình bày gì của run trong `withhold_runs` (mục 1.3).
- Không lưu dữ liệu ngoài `localStorage` cho tùy chọn của người xem (theme, ngôn ngữ, tab đang mở).
- Không thêm server, cơ sở dữ liệu hay bước build vào Console (CLAUDE.md, mục "Không làm").

## 7. Cập nhật file này

Khi server thêm hoặc đổi URL: sửa bảng tương ứng, chạy lại bước lấy mẫu, và thay file trong `api-samples/`. Hai test sau đọc thư mục `web/` và cần sửa theo giao diện mới: [test_web_static.py](../../packages/flywheel-console/tests/test_web_static.py), [test_i18n.py](../../packages/flywheel-console/tests/test_i18n.py).
