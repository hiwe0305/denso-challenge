# Console một website · kế hoạch làm

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biến Flywheel Console thành một website cho cả đội lẫn người ngoài: menu 6 trạm, phần giải thích đầu mỗi trang, VI/EN, trang Bắt đầu, Theo chân một lỗi, thư viện mô phỏng, cờ `--lock`.

**Architecture:** Không thêm trang kỹ thuật mới; `route()` trong `app.js` chèn một phần giải thích (từ `web/explain.js`) lên trên thân trang hiện có theo bảng route → trạm. Chữ nằm trong `web/i18n/{vi,en}.js`, gọi qua `t()`. Dữ liệu mới đi qua indexer (`index/sim.py`, khối `follow` trong `story.json`), không có số viết tay trong JS.

**Tech Stack:** Python 3.11 (http.server, tarfile, zipfile, cv2 qua `posters.py`), JS thuần, ECharts có sẵn, pytest.

**Spec:** [docs/superpowers/specs/2026-11-15-console-one-site-design.md](../specs/2026-11-15-console-one-site-design.md) (bản 0.2, Hiếu duyệt 15/11).

`PK` = `packages/flywheel-console/src/flywheel/console/`, `T` = `packages/flywheel-console/tests/`.

## Global Constraints

- Server chỉ nghe `127.0.0.1`; không CDN trong `index.html`; mọi JS nằm trong `web/vendor/`.
- Không mã màu hex trong `pages_*.js`; không đường dẫn máy trong package; literal 262, 229, 177, 160, 240 cấm trong `pages_story.js`, `ring.js`.
- Mọi số trên phần giải thích lấy từ `catalog.json`, `story.json`, `sim.json` hoặc `cited.yaml` (kèm câu trích).
- Từ điển: câu dẫn (khóa `*.a`, `*.lead`) tối đa 30 từ; tổng chữ một trạm (`st.N.*`) tối đa 90 từ. `budget.py` giữ nguyên cho file khác.
- Video egocentric chỉ bản `*.deid.mp4` hoặc EgoDex có pin; không đọc `vault/`; không commit `fwdata/`.
- Hỏi Hiếu trước khi commit, push, mở PR.
- Không nói quá: `C70_R1` 4/60 < `C_70` 10/60; luật viết trước cho F, dừng.

## Review Focus

1. Laptop không có `C70_R1.tar` hay zip teleop → `sim.py` ghi `sim.json` rỗng, trang `#/sim` hiện trạng thái trống, không lỗi (test ở Task 4).
2. `localStorage` bị chặn → đổi ngôn ngữ và gập phần giải thích vẫn chạy trong phiên (mọi truy cập bọc `try/catch`; kiểm tay ở Task 9).
3. Server khóa nhưng trang Training gọi `/api/tool` → trang dùng `story.json`, không hiện lỗi đỏ (Task 1, kiểm trên trình duyệt).
4. Đổi ngôn ngữ giữa chừng trên một route có tham số (`sim/449`, `data/:id`) → giữ route, vẽ lại (Task 2).
5. `/ego/index.html` khi chưa có `web/vendor/three/` → giữ thẻ CDN gốc thay vì trỏ vào file không tồn tại (Task 8).

---

### Task 1: `--lock`, nút khóa, hộp xác nhận, ẩn đường dẫn

**Files:** Modify `PK/cli.py` (`serve`), `PK/server/app.py` (`ConsoleServer`, `do_POST`, `api`, `api_get`, `make_server`, `serve`), `PK/web/core.js`, `PK/web/pages_ops.js`, `PK/web/pages_story.js`, `PK/web/chat.js`, `PK/web/app.js`. Test `T/server/test_app.py`, `T/test_cli.py`.

**Interfaces:**
- Produces: `make_server(paths, port, lock: bool = False)`, `serve(paths, port, lock: bool = False)`, `ConsoleServer.locked: bool`; `/api/status` có `"locked": bool`; JS `UI.locked` (bool, từ `poll()`), `UI.confirm(msg: string) -> boolean`, `UI.redact(s: string) -> string`.

- [x] Test: fixture `locked_srv` (`make_server(fw, 0, lock=True)`); parametrize POST `/api/jobs`, `/api/jobs/x/cancel`, `/api/upload`, `/api/chat`, `/api/models/prewarm`, `/api/models/connect` → 403 `{"error": "locked"}`; GET `/api/fs`, `/api/dir_check`, `/api/tool`, `/api/exports/a.zip` → 403; GET `/api/status` → `locked is True`; GET `/data/catalog.json` → 200. Server không khóa: `/api/status` có `locked is False`.
- [x] Chạy, thấy fail.
- [x] Cài: `LOCKED_GET = ("/api/fs", "/api/dir_check", "/api/tool")` và `parts[1] == "exports"` (3 phần); kiểm trong `do_POST` sau host/origin và đầu `api()`. `/api/status` trả `runner.status() | {"locked": self.server.locked}`. CLI `--lock` (typer bool).
- [x] JS: `poll()` đặt `UI.locked`; `startJob`, nút Cancel, upload, xuất gọi `UI.confirm` và bị tắt kèm "🔒" khi khóa; chat hiện "offline" khi khóa (không POST). `UI.redact` thay `/home/<user>/` bằng `~/` trong dòng lệnh job hiển thị.
- [x] Chạy `uv run pytest T/server T/test_cli.py` → qua.

### Task 2: `t()`, VI/EN, khung phần giải thích, menu theo trạm

**Files:** Create `PK/web/i18n/vi.js`, `PK/web/i18n/en.js`, `PK/web/explain.js`; modify `PK/web/core.js` (một bộ định dạng số), `PK/web/app.js` (`SIDE`, `route()`, `sideActive`), `PK/web/index.html`, `PK/web/style.css`, `PK/budget.py`. Test `T/test_i18n.py`, `T/test_budget.py`.

**Interfaces:**
- Produces: `window.I18N = {vi: {...}, en: {...}}`; `t(key: string, vars?: object) -> string` (thiếu khóa → trả khóa); `UI.lang` ("vi" | "en"), `UI.setLang(l)`; `UI.loc()` → "vi-VN" | "en-US", dùng bởi `fmt`, `pct`, `UI.fmt`; `EXPLAIN.stationOf(path: string, qs: object) -> number | null` (1–6); `EXPLAIN.band(n: number) -> Element`; `EXPLAIN.register(n, {fig?: () => Element, stats?: () => [{v, k, src}]})`; `budget.dict_violations(path) -> list[str]`.
- File từ điển: mỗi dòng `"key": "value",` trong `window.I18N.vi = {` … `};` để Python đọc bằng regex.

- [x] Test `test_i18n.py`: hai file cùng tập khóa; mọi `t("…")` trong `web/*.js` có khóa trong `vi`; `budget.dict_violations` rỗng cho cả hai file; một file mẫu có câu dẫn 31 từ thì bị bắt.
- [x] Chạy, thấy fail.
- [x] Cài từ điển, `t()`, nút `VI | EN` và nút "Giải thích" trên `#hdr`; `?lang=en` (search hoặc hash) thắng `localStorage["v5lang"]`; cập nhật `<html lang>`; đổi ngôn ngữ thì `drawSide(); route()`.
- [x] `SIDE`: Bắt đầu (`#/home`), 1 `#/data`, 2 `#/jobs?view=pipeline` (sáng cả khi ở `qa`), 3 `#/jobs?panel=export`, 4 `#/runs`, 5 `#/eval`, 6 `#/loop`, nhóm VẬN HÀNH: Jobs, Máy, Chi phí, Nhập. Bảng route → trạm theo spec 5.1; `route()` chèn `EXPLAIN.band(n)` trước thân trang khi `n != null` và chưa gập (`localStorage["v5explain"] === "off"`).
- [x] Band: câu hỏi, câu trả lời, hình (nếu có), ≤ 3 số có `title` nguồn, dòng "chỗ có thể sai", nút trạm trước/sau.
- [x] `budget.py`: thêm `explain.js`, `pages_start.js`, `pages_sim.js` vào `BUDGET`.
- [x] `uv run pytest T` → qua; trình duyệt: mọi route cũ mở, đổi ngôn ngữ, gập/mở.

### Task 3: Trang Bắt đầu

**Files:** Create `PK/web/pages_start.js`; modify `PK/web/app.js` (đổi `UI.route("home", pageHome)` thành `pageStart`; `pageHome` vẫn vẽ mục "Hôm nay"), `index.html`, `style.css`.

**Interfaces:** Consumes `t`, `EXPLAIN`, `CAT.totals`, `STORY.pair`, `STORY.round`, `STORY.h1m`. Produces `stationNumbers() -> {1..6: {v, k}}` (dùng lại trong band).

- [x] Khung "Theo chân một lần robot hỏng" (hình vòng của Task 5, nút → `#/follow`); một câu bài toán; vòng 6 trạm (lưới 3 × 2 + mũi tên 6 → 1, trạm 6 màu nhấn); số chính: 1 `CAT.totals.all.episodes` tập, 2 h1m xuất/tổng, 3 số tập `C70_R1` từ catalog, 4 số run `STORY.pair.runs`, 5 best/60, 6 lỗi → tập chọn từ `STORY.round`.
- [x] Mục "Hôm nay": gọi `pageHome(div)`.
- [x] Trình duyệt: số khớp Datasets và Eval.

### Task 4: Trạm 1 · `sim.py`, `/simmedia/`, thư viện mô phỏng

**Files:** Create `PK/index/sim.py`, `PK/web/pages_sim.js`, `T/index/test_sim.py`; modify `PK/index/__init__.py` (`PARTS` thêm `"sim"`), `PK/server/app.py` (`resolve`), `PK/paths.py` (`sim_media` property), `T/server/test_app.py`.

**Interfaces:**
- Produces: `sim.build(paths, out) -> dict[str, int]` (`{"sim_episodes": n, "sim_media": m}`); `sim.json` = `{"source", "sha8", "parts": [{label, n, release}], "chain", "episodes": [{i, label, cluster, seed, level, len, tray, target, spawn, steps, success, video, poster}], "teleop": [{i, video, poster}]}`; nhãn `"coverage" | "prev" | "round" | "teleop"` theo `meta/flywheel_subset.json` (`base.parts[0]` → coverage, `base.parts[1]` → prev, `targeted` → round). `ConsolePaths.sim_media = console_dir / "media" / "sim"`; mount `GET /simmedia/` có Range.
- Nguồn: `fw_root/tray/pair-cuts/C70_R1.tar` (sha8 từ `C70_R1.tar.json`), `fw_root/psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip`.
- Mẫu video: mọi tập có `cluster_id` kết thúc `L1-1000107` (367, 449, 450, 481, 511, 541, 571), 16 coverage rải đều theo chỉ số, 16 round rải theo cụm, 8 teleop rải đều; file có rồi thì bỏ qua.

- [x] Test: tar nhỏ dựng trong `tmp` (4 tập: 2 coverage, 1 prev, 1 round có `cluster_id` `place-L1-1000107`, mp4 bằng `write_mp4`) và zip 2 tập teleop → nhãn đúng, video tập cluster được trích, poster tồn tại, lần dựng thứ hai không ghi lại (mtime giữ nguyên); thiếu tar → `{"episodes": []}`. Server: `/simmedia/<sha8>/ep_000003.mp4` trả 206 với `Range`, `/simmedia/../x` → 404.
- [x] Chạy, thấy fail; cài; chạy qua.
- [x] `pages_sim.js`: `#/sim` (tab Thư viện ảnh · Chất lượng · Tất cả tập), `#/sim/:i` (video, hình nhìn từ trên với khay, ô đích, robot; 7 bước; liên kết `#/follow` khi cluster là `L1-1000107`). Đăng ký band trạm 1: ba thẻ nguồn (ego → `/ego/`, teleop → `#/sim?tag=teleop`, mô phỏng → `#/sim`) và thanh 301 / 124 / 181 từ `sim.json.parts`.
- [x] `FW_ROOT=… uv run fw console index` trên fwdata thật; trình duyệt `#/sim`, di chuột phát video.

### Task 5: Theo chân một lỗi

**Files:** Modify `PK/index/story.py` (`_follow(fw)`, khóa `"follow"`), `PK/seed/cited.yaml` (`follow.c1`), `PK/web/pages_start.js` (`#/follow`). Test `T/index/test_story.py`.

**Interfaces:** Produces `story.follow = {"level": 1, "seed": 1000107, "tol": {"distance_m", "yaw_error_deg"}, "runs": {run: {success, failure, reach_b, distance_m, yaw_error_deg}}, "r3": {run: {"got": [k, 23], "rest": [k, 37], "n": 60}}, "c1": {faults: 14, data: 10, quote}}` từ `stage1-60k/place-error-*.json`, `r3.json`, `cited.yaml`.

- [x] Test: fixture ghi `place-error-C_70.json` (một dòng seed 1000107), `r3.json` → `story.follow.runs.C_70.distance_m == 0.0704`, `r3.C_70.got == [0, 23]`; thiếu thư mục → `{}`.
- [x] Cài; chạy qua.
- [x] Năm màn (Hỏng · Chẩn đoán · Sinh dữ liệu · Thi lại · Tổng thể), nút Tiếp/Lùi, liên kết trạm. Hình vòng SVG: ô đích, vòng 5 cm, vòng `distance_m` nét đứt có chú thích "hướng không được ghi", cung `yaw_error_deg` so với 10°. Màn 3 phát video 6 tập từ `sim.json`. Màn 4 bảng năm run, câu "đạt một lần chưa chứng minh được gì". Màn 5 bảng 23/37 và F.

### Task 6: Phần giải thích trạm 5, 6

**Files:** `PK/web/explain.js` (đăng ký), `PK/web/i18n/*.js`.

- [x] Trạm 5: bảy bước bằng lời, số best/60 và khoảng tin cậy từ `STORY.pair`, chỗ có thể sai = bộ chấm (bước cuối khác số đạt).
- [x] Trạm 6: sáu bước của vòng, bảng 23/37 từ `STORY.follow.r3`, câu kết không nói quá.
- [x] Trình duyệt: số khớp `story.pair`, `r3.json`.

### Task 7: Phần giải thích trạm 2, 3, 4

- [x] Trạm 2: 379 → 317 / 54 / 8 từ `STORY.h1m`; chuỗi 290 → 262 → 261 → 204 → 181 từ `STORY.round`.
- [x] Trạm 3: thẻ bản cắt `ALL`, `S70`, `C70_R1` với sha256 8 ký tự từ catalog; ghi rõ hai số 606 khác nhau.
- [x] Trạm 4: lưới 2 × 2 + 1 từ `STORY.pair.runs`.

### Task 8: `three.js` cho `/ego/`

**Files:** `PK/web/vendor/three/three.min.js`, `PK/web/vendor/three/OrbitControls.js` (three@0.147.0, MIT; **cần Hiếu đồng ý tải**), `PK/server/app.py` (viết lại `<script>` khi trả `/ego/index.html` nếu file vendor có). Test `T/server/test_app.py`.

- [ ] Test: viewer giả có hai thẻ jsdelivr; khi `vendor/three/` có file → body không chứa `cdn.jsdelivr`; khi không có → giữ nguyên.
- [ ] Cài; chạy qua.

### Task 9: Kiểm toàn bộ

- [ ] `uv run ruff check`, `ruff format --check`, `mypy`, `pytest`, `lint-imports`; `python3 scripts/repo/check_links.py`.
- [ ] Trình duyệt: mọi route ở VI và EN; 1 366 × 768 và 1 920 × 1 080; không lỗi console; chạy `--lock` và bấm các nút ghi.

## Ghi chú sau đánh giá (15/11/2026)

Hai agent đánh giá độc lập (một bản rà soát, một bản chấm theo thang 100) đã đọc bản chưa commit. Các sửa đổi theo phát hiện của họ nằm trong cùng nhánh. Những điểm lệch so với spec, để Product Owner quyết:

- **Điểm bench QA/QC (spec 6.2, "99 tập, 33 lỗi cấy")** chưa hiện. Máy không có file kết quả bench nào (`bench_result.json`), mà mọi số phải lấy từ file. Trạm 2 chỉ nói bộ kiểm được thử bằng bản sao có lỗi cấy.
- **Luật 90 từ (spec 5.5)**: test chỉ đếm các khóa `st.N.*`. Nếu đếm cả nhãn trong hình (`fig.*`) thì dải giải thích dài 93–146 từ. Cần chọn: sửa câu chữ trong spec cho khớp, hoặc cắt bớt hình.
- **Nhóm catalog theo ba loại dưới các thẻ (spec 5.1)** chưa làm; trang Dữ liệu giữ bảng cũ.
- **Ngoài phạm vi đã làm**: dòng trạng thái eval và vòng lặp mới trong `runner._eval_loop_text`, viết lại các bước tour, bỏ nút demo trên thanh trên. Giữ hay bỏ do Product Owner chọn.
- **Khi chạy `--lock`**: lựa chọn ngôn ngữ và nút × chỉ giữ trong bộ nhớ của trang. Khách sau luôn thấy tiếng Việt và dải giải thích bật, trừ khi URL có `?lang=`. Server tự đổi đường dẫn máy trong mọi câu trả lời JSON và từ chối `/api/chat/traces*`.
