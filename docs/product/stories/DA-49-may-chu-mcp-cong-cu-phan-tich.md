# DA-49 · Máy chủ MCP cho 13 công cụ phân tích của Agent QA/QC

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng làm; Hiếu chốt phương án A ngày 26/11/2026 |
| Người làm | Hiếu, cùng Claude |
| Làn | Đánh giá (`flywheel.eval.agentqa`); không sửa nhân, làn khác hay adapter |
| Nguồn yêu cầu | Hiếu ngày 26/11/2026: dùng ngay phần nào của DeepSeek Harness dùng được cho hệ agent, sau đó đưa lên website; đồng ý mở story cho máy chủ MCP |
| Nhãn | `area:eval`, `area:agentqa` |
| Sprint | Trước vòng chung kết (khoảng 3/12/2026); không chặn kế hoạch nhóm C |
| Ước lượng | Khoảng 6 giờ (ước lượng) |
| Phụ thuộc | DA-43 (đã merge: sổ đăng ký công cụ, gói vòng `pack.json`, bước `admit`). Không phụ thuộc PR đang mở |

## Story

Là người phân tích một vòng eval, tôi muốn 13 công cụ phân tích của Agent QA/QC lộ ra qua một máy chủ MCP chạy trên stdio, để bất kỳ vỏ chat nào nói được MCP (DeepSeek Harness, Claude Code, vỏ của Console sau này) gọi được chúng trên một gói vòng mà không phải viết lại công cụ, và mọi con số trong câu trả lời vẫn đến từ code.

MCP (Model Context Protocol) là giao thức để một chương trình chat gọi công cụ của một chương trình khác. Ở kiểu stdio, vỏ chat khởi chạy máy chủ như một tiến trình con và trao đổi JSON-RPC 2.0 qua stdin và stdout, mỗi thông điệp một dòng.

13 công cụ là đúng các công cụ trong `agentqa/tools/registry.py`: `task_lookup`, `step_pass_table`, `failure_clusters`, `latch_consistency`, `signal_presence`, `paired_compare`, `trace_stats`, `train_window`, `lineage`, `coverage_distance`, `cost_lookup`, `history_lookup`, `relaxed_sweep`.

Story này **không** làm vỏ chat, không cài DeepSeek Harness và không sửa Console. Đó là việc sau chung kết, cần story riêng.

## Cách làm

**[Đã chốt]** Hiếu chọn phương án A ngày 26/11/2026 (đề xuất của Claude cùng ngày).

Vì sao MCP là phần dùng được ngay của DeepSeek Harness (khảo sát chỉ đọc ngày 26/11/2026, bản `dsh-v0.2.3-alpha.2`, chưa cài và chưa chạy): harness không cho đăng ký công cụ bằng Python; công cụ ngoài chỉ vào được qua plugin TypeScript hoặc MCP. Máy chủ MCP do đội viết thì dùng được với harness mà không cần sửa harness, và dùng được với vỏ khác nếu sau này không chọn harness.

| Phương án | Nội dung | Được | Mất |
|---|---|---|---|
| **A (chọn)** | Viết máy chủ stdio bằng thư viện chuẩn của Python: `initialize`, `tools/list`, `tools/call`, `ping` | Không thêm phụ thuộc, không đụng `pyproject.toml` và `uv.lock`; làm được ngay | Tự giữ đúng giao thức; chỉ có phần công cụ, không có resource hay prompt |
| B | Dùng thư viện MCP chính thức của Python | Đúng giao thức theo bản thư viện; dễ thêm kiểu truyền HTTP | Cần Hiếu thêm phụ thuộc vào `pyproject.toml` và `uv.lock`; thư viện kéo theo máy chủ HTTP mà L0 không cần |
| C | Viết plugin TypeScript cho harness | Tích hợp sâu nhất với harness | Máy không có Node; khóa vào một vỏ đang ở bản preview |

Chọn A vì phần cần dùng của giao thức nhỏ (bốn phương thức) và A không chờ quyết định nào ngoài story này. Nếu sau này cần kiểu truyền HTTP cho website thì đổi sang B trong một story khác; lớp nối công cụ (mục 2.1) giữ nguyên.

Thiết kế:

| Phần | Nội dung |
|---|---|
| Đầu vào | Một `pack.json` đã có. Máy chủ chạy `admit` một lần khi khởi động, dựng `MeasureContext` và một `FactBook`, rồi giữ trong bộ nhớ đến khi tắt |
| `tools/list` | Sinh từ `ToolSpec`: tên, phiên bản, và JSON Schema của tham số. Miền đóng của mỗi tham số (run, mức, nhãn có trong gói) thành `enum` tính từ gói đang mở |
| `tools/call` | Kiểm tham số bằng `check_params` của sổ đăng ký trước khi chạy; tham số ngoài miền trả lỗi công cụ (`isError`), không chạy gì. Kết quả là `ToolResult`: các fact (id, tên, giá trị, nguồn), bảng `rows`, và lý do `not_judged` |
| Công cụ thiếu dữ liệu | Công cụ cần loại artifact mà gói không có vẫn được liệt kê, khi gọi trả `not_judged` như trong đường ống vòng |
| Lệnh | `fw agentqa mcp --pack <pack.json> [--store <dir>]` |
| Nhật ký | Mỗi lời gọi ghi một dòng JSON ra stderr hoặc file `--log`: công cụ, tham số, id các fact, thời gian. Stdout chỉ dành cho giao thức |

Ba ràng buộc không được nới:

- **Lớp dữ liệu.** Máy chủ không biết model phía sau vỏ chat là tự host hay hosted. Vì vậy nó chỉ mở gói mà `admit` xác nhận `public` (cùng phép kiểm `hosted_refusal` của cổng model). Gói `internal` hoặc `restricted` luôn bị từ chối và story này không có cờ nào để mở chúng: dữ liệu của demo đều `public`, còn mở gói khác lớp chỉ bằng một lời khai thì không kiểm được. Cần phục vụ gói không `public` cho model tự host thì mở story riêng.
- **Chỉ đọc gói.** Máy chủ chỉ đọc các file mà gói khai. Không có công cụ đọc file theo đường dẫn, không đọc `vault/`, file đáp án hay `docs/`.
- **Số từ code.** Máy chủ chỉ trả fact do công cụ sinh. Nó không sinh văn bản và không gọi model. Việc chặn câu trả lời cuối của vỏ chat (mọi câu phải dẫn fact) không thuộc story này, vì harness không có chỗ để chặn; ghi rõ là giới hạn.

## Tiêu chí chấp nhận

1. `fw agentqa mcp --pack <pack.json>` trả lời `initialize`, `ping`, `tools/list` và `tools/call` trên stdio theo JSON-RPC 2.0; phương thức lạ trả lỗi `-32601`; dòng không phải JSON trả lỗi `-32700` và máy chủ chạy tiếp. Thông điệp không có `id` là notification (ví dụ `notifications/initialized` mà vỏ chat gửi sau `initialize`): máy chủ không trả lời gì, kể cả lỗi `-32601` khi không biết phương thức. Có test chạy máy chủ như tiến trình con, gồm ca notification.
2. `tools/list` trả đúng 13 công cụ của sổ đăng ký; một test so tên với `registry` để thêm công cụ mới thì test báo. Schema của mỗi tham số có `enum` là miền đóng tính từ gói.
3. `tools/call` với tham số ngoài miền trả `isError` kèm lý do của `check_params` và không ghi fact nào. Với tham số hợp lệ, các fact trả về bằng đúng fact mà bước `measure` của đường ống vòng sinh cho cùng công cụ và cùng tham số trên cùng gói (test trên gói giả của `flywheel.testkit`).
4. Gói không được xác nhận `public` bị từ chối khi khởi động, mã thoát khác 0, và không có cờ nào bỏ qua phép kiểm này. Có test cho gói `public` và gói không `public`.
5. Không có công cụ hay tham số nào nhận đường dẫn file. Có test quét schema.
6. Mã chạy trên CPU, không thêm phụ thuộc, không import adapter hay làn khác. `uv run ruff check`, `uv run mypy` (không thêm lỗi), `uv run pytest`, `uv run lint-imports`, `scripts/repo/check_links.py`, `scripts/repo/pr_guard.py` qua.
7. `docs/g0/agent-qa.md` có một mục ngắn: cách chạy, cách khai máy chủ trong cấu hình MCP của một vỏ chat, ba ràng buộc ở trên, và giới hạn. Có một lần chạy tay trên gói thật `stage1-60k-out` (liệt kê công cụ và một lời gọi), ghi kết quả vào thân commit.

## Nhiệm vụ

- [x] 1.1 Viết story (file này)
- [x] 2.1 Lớp nối: từ `ToolSpec` và `MeasureContext` ra schema công cụ và từ `ToolResult` ra nội dung trả về, có test (AC 2, 3, 5)
- [ ] 2.2 Vòng lặp stdio JSON-RPC: `initialize`, `ping`, `tools/list`, `tools/call`, notification, xử lý lỗi, có test tiến trình con (AC 1)
- [ ] 2.3 Lệnh `fw agentqa mcp`, phép kiểm lớp dữ liệu khi khởi động, nhật ký lời gọi, có test (AC 4)
- [ ] 3.1 Mục tài liệu trong `docs/g0/agent-qa.md`, lần chạy tay trên gói thật, chạy đủ kiểm tra (AC 6, 7)

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/agentqa/mcp/` (thư mục mới)
- `packages/flywheel-eval/src/flywheel/eval/agentqa/cli.py` (chỉ thêm lệnh `mcp`)
- `packages/flywheel-eval/tests/unit/agentqa/mcp/` (thư mục mới)
- `docs/g0/agent-qa.md` (chỉ thêm một mục)

## Ghi chú cho người làm

- Không sửa `agentqa/tools/` (sổ đăng ký và 13 công cụ), `agentqa/round/`, `agentqa/endpoint.py`, `agentqa/bench/`, `flywheel.contracts`, `pyproject.toml`, `uv.lock` hay workflow CI. Cần đổi một trong các chỗ này thì dừng lại và báo Hiếu.
- Không cài và không tải gói nào (Node, `deepseek-harness-sdk`, thư viện MCP). Thử máy chủ với một vỏ chat thật là việc Hiếu quyết sau.
- Ghim một bản giao thức MCP trong mã và ghi nguồn; trả đúng bản đó ở `initialize`. Trước khi viết, đọc đặc tả của bản được ghim thay vì dựa vào trí nhớ.
- `FactBook` sống suốt một phiên máy chủ. Tên fact cố định giá trị trong một vòng, nên gọi lại cùng công cụ cùng tham số phải trả cùng fact, không báo trùng.
- Kết quả thi lại của `C70_R1` không trình bày (Hiếu, 16/11/2026): không dùng gói chứa kết quả này cho lần chạy tay hay ví dụ trong tài liệu.
- Số chưa đo ghi là ước lượng.

## Kiểm thử

- `uv run pytest packages/flywheel-eval/tests/unit/agentqa/mcp`
- `uv run ruff check`, `uv run mypy` (lệnh đủ ở README gốc), `uv run pytest`, `uv run lint-imports`
- `python3 scripts/repo/check_links.py`
- `python3 scripts/repo/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"`

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
