# DA-51 · Console đọc kết quả đường ống vòng của Agent QA/QC

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Nháp, chờ Hiếu duyệt story; mã chỉ bắt đầu sau khi nhánh dựng lại giao diện `chore-console-ui-rebuild` vào master |
| Người làm | Hiếu, cùng Claude |
| Làn | Ngoài ba làn: `packages/flywheel-console` (backend). Không sửa nhân, làn hay đường ống vòng |
| Nguồn yêu cầu | Hiếu ngày 26/11/2026: đồng ý hướng Console đọc kết quả đường vòng qua một bộ chuyển ở backend, sau bảng đối chiếu của nhóm C cùng ngày |
| Nhãn | `area:console`, `area:agentqa` |
| Sprint | Trước vòng chung kết (khoảng 3/12/2026) |
| Ước lượng | Khoảng 5 giờ (ước lượng) |
| Phụ thuộc | Nhánh `chore-console-ui-rebuild` (hợp đồng `docs/console/api-contract.md` và giao diện mới, chưa vào master). DA-43 (đã merge: đường ống vòng `fw agentqa round`) |

## Story

Là người xem Flywheel Console, tôi muốn trang Agent QA/QC hiện được một lần chạy của đường ống vòng (`fw agentqa round`), kể cả lần chạy có model hosted, cùng với trạng thái thật của nó, để kết quả của vòng chung kết lên được website mà không phải chạy lại bằng đường cũ.

Hiện trạng, đọc ngày 26/11/2026 ở worktree của nhánh dựng lại (chỉ đọc):

| Chỗ | Hiện trạng | Hệ quả |
|---|---|---|
| Job `agentqa.run` của backend | Gọi đường cũ `fw agentqa run --input <artifact>` | Console chưa bao giờ chạy hay đọc đường vòng |
| `agent_results` | Chỉ đọc `<out>/reports.jsonl`; `out` phải nằm dưới thư mục `agentqa` của Console | Lần chạy vòng có model không ghi `reports.jsonl` (kết quả ở `assembly.json`), nên trả rỗng |
| `agent_stats` | Chỉ đếm lần chạy có tên model chứa `nemotron` | Lần chạy bằng model khác đếm là 0 |
| `list_artifacts` | Không liệt kê thư mục lần chạy vòng | Không chọn được từ giao diện |
| Hợp đồng API | Trạng thái chỉ có `ok` và `failed` | Lần chạy `degraded` (thiếu đầu vào) hiện như lành |

## Cách làm

**[Đã chốt]** hướng: Hiếu ngày 26/11/2026. **[Đề xuất]** chi tiết dưới đây: Claude 26/11/2026.

Một bộ chuyển ở backend Console đọc các file mà đường vòng đã ghi và trả về theo hợp đồng API. Đường vòng không đổi: nó thuộc làn Đánh giá, các file của nó không phải hợp đồng giữa làn, nên phía đọc tự chuyển.

| Trường API | Lấy từ |
|---|---|
| id lần chạy | `run.json.run_id` |
| đầu vào | `pack.json.pack_id` và `task_id` |
| thời điểm | `run.json.started_at`; giờ kết thúc lấy từ thời điểm sửa file `run.json` |
| model | `assembly.json.model`; rỗng nghĩa là lớp code |
| hosted hay tự host | `run.json.model_hosts` |
| trạng thái | `run.json.status`: `ok`, `degraded`, `broken`, kèm `problems` |
| số phát hiện | số cụm trong `assembly.json.clusters` có phán quyết nhận hoặc sửa; lần chạy lớp code đếm cụm có giả thuyết hạng 1 |
| phần không xét | `assembly.json.not_judged` |
| chi phí model | `run.json.totals` |
| trang đọc | `index.html` của lần chạy (đường vòng đã dựng, có trích dẫn fact theo câu) |

Lần chạy đường cũ (`reports.jsonl`) vẫn đọc như hiện nay.

## Tiêu chí chấp nhận

1. `agent_results` trên thư mục một lần chạy vòng trả `status`, `problems`, `not_judged`, `totals`, `model`, danh sách cụm đã rút gọn và đường dẫn `index.html`; trên thư mục đường cũ trả như trước. Có test với một thư mục vòng mẫu nhỏ dựng trong test.
2. `agent_stats` đếm mọi lần chạy, không lọc theo tên model; mỗi dòng có `model`, `hosted`, `status`. Có test.
3. `list_artifacts` liệt kê thư mục lần chạy vòng với `kind` `agentqa_round`. Có test.
4. Thư mục vòng nằm ngoài các gốc mà Console cho phép vẫn bị từ chối như mọi đường dẫn khác. Có test.
5. Lần chạy `degraded` hoặc `broken` không bao giờ được trả với trạng thái `ok`. Có test.
6. Kết quả thi lại của `C70_R1` không hiện: bộ chuyển theo công tắc `withhold_eval` trong `seed/tasks.yaml` như các trang khác. Có test.
7. `docs/console/api-contract.md` và mẫu trong `docs/console/api-samples/` được cập nhật cho ba API, gồm định nghĩa "số phát hiện" của vòng.
8. `uv run ruff check`, `uv run mypy` (không thêm lỗi), `uv run pytest`, `uv run lint-imports`, `scripts/repo/check_links.py`, `scripts/repo/pr_guard.py` qua.

## Nhiệm vụ

- [x] 1.1 Viết story (file này)
- [ ] 2.1 Bộ chuyển đọc `run.json`, `assembly.json`, `pack.json` của một lần chạy vòng, có test (AC 1, 5)
- [ ] 2.2 `agent_results`, `agent_stats`, `list_artifacts` dùng bộ chuyển; bỏ bộ lọc tên model; phép kiểm đường dẫn và `withhold_eval`, có test (AC 2, 3, 4, 6)
- [ ] 2.3 Trang Agent QA/QC hiện trạng thái, phần không xét và liên kết `index.html` (AC 1, 5)
- [ ] 3.1 Cập nhật hợp đồng API và mẫu; chạy đủ kiểm tra (AC 7, 8)

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-console/src/flywheel/console/server/` (chỉ `runner.py`, `kinds.py` và một module mới cho bộ chuyển)
- `packages/flywheel-console/src/flywheel/console/web/` (chỉ trang Agent QA/QC)
- `packages/flywheel-console/tests/`
- `docs/console/api-contract.md`, `docs/console/api-samples/`

## Ghi chú cho người làm

- Không sửa `packages/flywheel-eval` (đường vòng), `flywheel.contracts`, `pyproject.toml`, `uv.lock` hay workflow CI. Nếu thấy đường vòng thiếu một trường (ví dụ giờ kết thúc trong bản ghi lần chạy) thì báo nhóm C, không đọc vòng qua cách khác.
- Bộ chuyển chỉ đọc file JSON của lần chạy; không import `flywheel.eval`. Hình dạng file lấy từ `agentqa/round/records.py` tại commit lúc làm, ghi commit đó trong docstring.
- Không bắt đầu mã khi nhánh dựng lại giao diện chưa vào master: hợp đồng API và `runner.py` đang được sửa ở đó, hai người sửa cùng file sẽ giẫm nhau.
- Công cụ chat đọc kết quả agent không thuộc story này; nó đi qua máy chủ MCP của DA-49.
- Số chưa đo ghi là ước lượng.

## Kiểm thử

- `uv run pytest packages/flywheel-console/tests`
- `uv run ruff check`, `uv run mypy` (lệnh đủ ở README gốc), `uv run pytest`, `uv run lint-imports`
- `python3 scripts/repo/check_links.py`
- `python3 scripts/repo/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"`

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
