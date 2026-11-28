# Hợp đồng API của Flywheel Console

Ngày viết: 25/11/2026. Trạng thái: **[Đề xuất]**, chờ Hiếu duyệt.

File này mô tả mọi URL mà giao diện web của Console gọi tới server. Mục đích: xây lại giao diện (`packages/flywheel-console/src/flywheel/console/web/`) mà **không đổi server**. Giao diện mới chỉ được gọi các URL trong file này.

Nguồn sự thật là mã: [server/app.py](../../packages/flywheel-console/src/flywheel/console/server/app.py), [server/runner.py](../../packages/flywheel-console/src/flywheel/console/server/runner.py), [server/media.py](../../packages/flywheel-console/src/flywheel/console/server/media.py), [chat/llm.py](../../packages/flywheel-console/src/flywheel/console/chat/llm.py). Khi file này lệch với mã, mã thắng; sửa file này cho khớp.

JSON mẫu thật nằm trong [api-samples/](api-samples/). Cách lấy: chạy server trên `fwdata/` của laptop ngày 25/11/2026, rồi cắt mỗi danh sách còn 2 phần tử, cắt chuỗi dài, bỏ dòng catalog không `public`, thay đường dẫn máy bằng `fwdata/`, `~/` và `<repo>/`. Mẫu chỉ cho biết **hình dạng**, không phải số liệu để trình bày.

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
- Giao diện mới **vẫn phải lọc lần nữa** theo `rounds[].withhold_eval` của `data/tasks.json`, giống hàm `unhide` trong `web/core.js` hiện tại: bỏ run khỏi `pair.runs`, bỏ so sánh có run đó khỏi `pair.comparisons`, bỏ khóa run khỏi `follow.runs`, xóa `follow.r3`, xóa `demo.round1_reading`, bỏ khóa run khỏi `demo.ladder.runs` và `demo.ladder.on_table_b.value`.
- Thông tin train, bản cắt dữ liệu và chi phí của run vẫn được hiện.

## 2. File chỉ mục (đọc, không có tham số)

Do `fw console index` tạo trong `fwdata/console/index/`, server phục vụ ở `/data/`. Giao diện tải các file này khi mở trang.

| URL | Mẫu | Nội dung |
|---|---|---|
| `data/tasks.json` | [data_tasks.json](api-samples/data_tasks.json) | `{version, source, tasks[], rounds[]}`. Mỗi task: `id` (`tray`, `two_table`…), `name`/`word`/`description` song ngữ `{vi, en}`, `robot`, `model`, `simulator`, `stages[]`, `success`, `rounds[]` (id vòng), `index[]` (khóa của `story.json` mà task được thấy), `process` (stage 0–6: thiếu gì, chạy ở đâu, lệnh), `catalog_totals`, `catalog_rows`. Mỗi round: `id`, `task`, `title`, `runs[]`, `baseline`, `after_round`, `controls[]`, `withhold_eval[]`, `follow`, `max_steps`, `index[]` |
| `data/catalog.json` | [data_catalog.json](api-samples/data_catalog.json) | `{generated, rows[], edges[], runs[], totals}`. Mỗi row là một tập dữ liệu: `id`, `title`, `kind`, `group`, `data_type`, `task`, `episodes`, `frames`, `hours`, `fps`, `format`, `licence`, `data_class`, `status`, `parents[]`, `children[]`, `view`, `thumbs[]`. `edges` là cặp `[cha, con]` của cây nguồn gốc. `totals` theo nhóm (`egocentric`, `teleop`, `s1`, `s2`, `all`) |
| `data/story.json` | [data_story.json](api-samples/data_story.json) | Số liệu cho các trang câu chuyện: `runs`, `train_log_tail`, `sources`, `heat`, `reasons`, `ledger`, `colab_balance`, `colab_sessions`, `eval`, `loop_chain`, `loop_detail`, `pair`, `round`, `follow`, `demo`, `h1m`, `ds`, `vm_phases`, `qa_sample`. Mỗi task chỉ được đọc các khóa có trong `index[]` của task và round (`story.<khóa>`); không hiện số của task khác |
| `data/sim.json` | [data_sim.json](api-samples/data_sim.json) | Tập episode mô phỏng: `source`, `sha8`, `parts[]`, `cuts{}`, `batch{}`, `episodes[]`, `round`, `format`, `teleop[]`. Task không có khóa `sim` trong `index[]` chỉ thấy `teleop[]` lọc theo task |
| `data/ds/<id>/episodes.json` | (không có mẫu) | Danh sách episode của một tập; đây là nguồn số episode cho `#/data/:id/ep/:n`. Tập robot (do [index/robot.py](../../packages/flywheel-console/src/flywheel/console/index/robot.py) viết): `i`, `n`, `s` (giây), `lv`, `seed`, `part`, `cut`, `out`… Tập egocentric và nguồn: `id`, `title`, `s`, `qa`, `reasons`, `poster`… Tập robot chỉ có khi laptop có dữ liệu LeRobot lúc chạy `fw console index` |
| `data/ds/<id>/quality.json`, `method.json`, `qa.json`, `env.json` | (không có mẫu) | Chất lượng, cách tạo tập, kết quả QA từng episode, môi trường (chỉ tập robot); file nào thiếu thì khối đó rỗng |
| `data/ds/<id>/posters/<i>.jpg` | | Ảnh đại diện từng episode |

## 3. API đọc (GET)

| URL | Tham số | Trả về | Mẫu | Khi khóa |
|---|---|---|---|---|
| `/api/status` | | Trạng thái 6 stage của vòng (`collect`, `process`, `release`, `train`, `eval`, `loop`; mỗi cái có `state` = `idle`/`running`/`done`/`blocked`/`waiting`, `now`, `issue`, `how`, `jobs[]`, `link`), 10 job gần nhất, `machines` (`laptop.slots`, `rtx3060.tunnel`, `colab.balance`), `locked`, `chat_on` | [api_status.json](api-samples/api_status.json) | được |
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
- Không trình bày kết quả của run trong `withhold_eval` (mục 1.2).
- Không lưu dữ liệu ngoài `localStorage` cho tùy chọn của người xem (theme, ngôn ngữ, tab đang mở).
- Không thêm server, cơ sở dữ liệu hay bước build vào Console (CLAUDE.md, mục "Không làm").

## 7. Cập nhật file này

Khi server thêm hoặc đổi URL: sửa bảng tương ứng, chạy lại bước lấy mẫu, và thay file trong `api-samples/`. Hai test sau đọc thư mục `web/` và cần sửa theo giao diện mới: [test_web_static.py](../../packages/flywheel-console/tests/test_web_static.py), [test_i18n.py](../../packages/flywheel-console/tests/test_i18n.py).
