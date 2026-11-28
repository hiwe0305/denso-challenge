# DA-55 · Nối chat của Agent QA/QC vào Console

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Nháp, chờ Hiếu duyệt story; mã phía Console chỉ bắt đầu sau khi nhánh dựng lại giao diện `chore-console-ui-rebuild` vào master |
| Người làm | Hiếu, cùng Claude |
| Làn | Làn Đánh giá (`flywheel.eval.agentqa`, phần lệnh chat) và ngoài ba làn: `packages/flywheel-console` |
| Nguồn yêu cầu | Hiếu ngày 28/11/2026: sau khi kiểm xong thiết kế website, muốn nối website vào phần agent để chạy |
| Nhãn | `area:console`, `area:agentqa` |
| Sprint | Trước vòng chung kết (khoảng 3/12/2026) |
| Ước lượng | Khoảng 8 giờ (ước lượng) |
| Phụ thuộc | Nhánh `chore-console-ui-rebuild` (hợp đồng `docs/console/api-contract.md`, chưa vào master). [DA-54](DA-54-vo-deepseek-harness-cho-agent-qaqc.md) (đã merge: `fw agentqa chat`, `fw agentqa chat-page`). [DA-51](DA-51-console-doc-ket-qua-duong-vong.md) (Console đọc lần chạy vòng; story này dùng danh sách lần chạy của nó) |

## Story

Là người xem Flywheel Console, tôi muốn hỏi Agent QA/QC về một lần chạy vòng ngay trên website và thấy nó gọi công cụ, nêu giả thuyết, trả lời, với phần đã qua phép kiểm tách khỏi lời tự do của model, để không phải mở dòng lệnh khi phân tích lỗi.

Hiện trạng, đọc ngày 28/11/2026:

| Chỗ | Hiện trạng | Hệ quả |
|---|---|---|
| Chat của Console (`POST /api/chat`, worktree nhánh dựng lại, chỉ đọc) | Luồng SSE với model và công cụ riêng của Console; không gọi `fw agentqa chat` | Câu trả lời trên web không qua phép kiểm của agent (dẫn fact, số do mã điền) |
| `fw agentqa chat` (master) | Chỉ in kết quả khi cả lượt kết thúc; một lượt thật mất khoảng 100 đến 300 giây (số đo ở `docs/g0/agent-qa.md` mục 11.4 và 11.6) | Trên web người dùng chờ mà không thấy gì |
| `answers.jsonl` của thư mục ghi nhận | Không ghi câu hỏi | Trang kết quả không hiện được câu hỏi của câu trả lời |
| Thư mục làm việc của harness | Dưới thư mục tạm của hệ thống | Máy khởi động lại thì phiên cũ không tiếp tục được |

## Cách làm

**[Đề xuất]** Claude 28/11/2026, chờ Hiếu duyệt.

Console không import `flywheel.eval`. Backend Console chạy `fw agentqa chat` như một tiến trình con (cách `server/runner.py` đã chạy job), đọc từng dòng sự kiện và chuyển thành sự kiện SSE của hợp đồng chat sẵn có.

| Phần | Việc |
|---|---|
| Lệnh chat | Thêm chế độ in sự kiện theo từng dòng NDJSON ngay khi harness phát ra (lời gọi công cụ, kết quả, câu trả lời đã kiểm, lời chưa kiểm, kết thúc). Chế độ hiện có không đổi |
| Ghi câu hỏi | Lệnh chat ghi câu hỏi của lượt vào thư mục ghi nhận; `answer_submit` gắn câu hỏi đó vào dòng của `answers.jsonl` |
| Thư mục làm việc | Tùy chọn đặt thư mục làm việc của harness ở chỗ bền; tên thư mục vẫn trung tính, không chứa tên người hay dự án |
| Backend Console | Một đường API chat của agent: nhận câu hỏi và id lần chạy vòng, tự tìm `pack.json`, tạo thư mục ghi nhận gắn với lần chạy (`--run`), chạy lệnh chat, trả SSE |
| Giao diện | Trên trang Agent QA/QC của một lần chạy: khung chat, danh sách lời gọi công cụ, khối "đã kiểm" và khối "chưa kiểm" tách nhau, nút dựng trang kết quả (`fw agentqa chat-page`) |

Ánh xạ sự kiện, dùng lại tên của hợp đồng chat khi nghĩa trùng:

| Sự kiện của lệnh chat | Sự kiện SSE |
|---|---|
| bắt đầu phiên | `trace_start` |
| lời gọi công cụ, kết quả | `tool_start`, `tool_result` |
| câu trả lời `answer_submit` đã nhận | `checked_answer` (mới): văn bản do mã điền số, danh sách fact đã dẫn |
| phán quyết của `hypothesis_propose` | `hypothesis` (mới): id, phán quyết, luật không qua |
| lời tự do của model | `token`, luôn hiện với nhãn chưa kiểm |
| kết thúc, lỗi | `done`, `error` |

## Tiêu chí chấp nhận

1. `fw agentqa chat` ở chế độ sự kiện in mỗi sự kiện một dòng JSON ngay khi có, và dòng cuối cho biết lượt có câu trả lời đã kiểm hay không. Có test với harness giả.
2. Câu hỏi của lượt nằm trong dòng tương ứng của `answers.jsonl`, và trang của `chat-page` hiện nó. Có test.
3. Đường API chat của agent chỉ nhận lần chạy vòng nằm dưới các gốc Console cho phép, và từ chối gói không được `admit` xác nhận `public` trước khi tiến trình nào được chạy. Có test.
4. Giao diện không bao giờ hiện lời tự do của model như câu trả lời đã kiểm: khối đã kiểm chỉ lấy từ sự kiện `checked_answer`. Có test ở backend cho ánh xạ sự kiện.
5. Đóng kết nối thì tiến trình chat dừng; không còn tiến trình con sống sau lượt. Có test.
6. Chế độ `--lock` của Console: đường API này theo cùng luật với `/api/chat` (chỉ mở khi `chat_on`).
7. Khóa API chỉ đi qua biến môi trường của tiến trình con; không nằm trong sự kiện, log hay trace. Có test trên dòng sự kiện.
8. Kết quả thi lại của `C70_R1` không hiện: lần chạy bị công tắc `withhold_eval` giữ lại thì không chat được qua đường này. Có test.
9. `docs/console/api-contract.md` và mẫu trong `docs/console/api-samples/` có đường API mới và hai sự kiện mới; `docs/g0/agent-qa.md` mục 11 có chế độ sự kiện.
10. Một lượt thật trên run M qua website: hỏi, thấy công cụ chạy, nhận câu trả lời đã kiểm, dựng được trang. Ghi số đo (giây, token).
11. `uv run ruff check`, `uv run mypy` (không thêm lỗi), `uv run pytest`, `uv run lint-imports`, `scripts/repo/check_links.py`, `scripts/repo/pr_guard.py` qua.

## Cần Hiếu quyết

| # | Câu hỏi | Đề xuất |
|---|---|---|
| 1 | Chat của agent là đường API riêng, hay thay luôn `/api/chat` trên trang Agent QA/QC? | Đường riêng: chat chung của Console giữ nguyên cho các trang khác |
| 2 | Model của chat trên web | Giữ mặc định của profile (fable qua ckey) cho gói `public`; giá trên cổng chưa ghi nhận, nên có trần token mỗi lượt |
| 3 | Máy demo ở chế độ `--lock` có bật chat của agent không? | Bật khi `chat_on`, như chat chung |
| 4 | Gói không `public` (dữ liệu DENSO) | Ngoài story này: cần tuyến model tự host cho harness |

## Nhiệm vụ

- [x] 1.1 Viết story (file này)
- [ ] 2.1 Chế độ sự kiện của `fw agentqa chat`, có test (AC 1, 7)
- [ ] 2.2 Ghi câu hỏi vào `answers.jsonl` và hiện trên trang; thư mục làm việc bền (AC 2)
- [ ] 3.1 Đường API chat của agent ở backend Console: tìm gói, gắn lần chạy, chạy tiến trình con, ánh xạ sang SSE, có test (AC 3, 4, 5, 6, 7, 8)
- [ ] 3.2 Giao diện trên trang Agent QA/QC (AC 4)
- [ ] 4.1 Hợp đồng API, mẫu, tài liệu; một lượt thật trên run M; chạy đủ kiểm tra (AC 9, 10, 11)

Nhiệm vụ 2.1 và 2.2 không phụ thuộc nhánh dựng lại giao diện, làm trước được. Nhiệm vụ 3.1 trở đi chờ nhánh đó vào master.

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/agentqa/chat/`
- `packages/flywheel-eval/src/flywheel/eval/agentqa/cli.py` (chỉ lệnh `chat`)
- `packages/flywheel-eval/src/flywheel/eval/agentqa/mcp/records.py` (chỉ để ghi câu hỏi)
- `packages/flywheel-eval/tests/unit/agentqa/chat/`
- `packages/flywheel-eval/tests/unit/agentqa/mcp/`
- `packages/flywheel-console/src/flywheel/console/server/` (một module mới cho chat của agent, và chỗ đăng ký đường API trong `app.py`)
- `packages/flywheel-console/src/flywheel/console/web/` (chỉ trang Agent QA/QC)
- `packages/flywheel-console/tests/`
- `docs/console/api-contract.md`
- `docs/console/api-samples/`
- `docs/g0/agent-qa.md` (chỉ mục 11)

## Ghi chú cho người làm

- Console không import `flywheel.eval`; chỉ chạy `fw agentqa chat` và `fw agentqa chat-page` như tiến trình con và đọc đầu ra của chúng.
- Không sửa `flywheel.contracts`, `agentqa/endpoint.py`, `agentqa/bench/`, `configs/eval/agentqa/harness/`, `pyproject.toml`, `uv.lock` hay workflow CI.
- Hàng rào lớp dữ liệu không được nới: chỉ gói `public` tới được model hosted, và phép kiểm này vẫn nằm trong lệnh chat lẫn máy chủ MCP.
- Không gửi tên người, tên dự án hay đường dẫn của máy tới model; thư mục làm việc của harness giữ tên trung tính.
- Không bắt đầu mã phía Console khi nhánh dựng lại giao diện chưa vào master.
- Harness là bản preview, chưa qua kiểm toán bảo mật; Web UI của chính harness không dùng cho demo.
- Số chưa đo ghi là ước lượng.

## Kiểm thử

- `uv run pytest packages/flywheel-eval/tests/unit/agentqa packages/flywheel-console/tests`
- `uv run ruff check`, `uv run mypy` (lệnh đủ ở README gốc), `uv run pytest`, `uv run lint-imports`
- `python3 scripts/repo/check_links.py`
- `python3 scripts/repo/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"`

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
