# DA-52 · Vòng lặp điều tra cho Agent QA/QC

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng làm; Hiếu chốt năm điểm thiết kế ngày 27/11/2026 |
| Người làm | Hiếu, cùng Claude |
| Làn | Đánh giá (`flywheel.eval.agentqa`); không sửa nhân, làn khác hay adapter |
| Nguồn yêu cầu | Hiếu ngày 27/11/2026: "tôi muốn hệ thống agent này có thêm loop để nó có khả năng reasoning rồi làm nó thì mới đạt được mục tiêu chứ!" |
| Nhãn | `area:eval`, `area:agentqa` |
| Sprint | Trước vòng chung kết; chạy được trên run M trước 30/11/2026 để kịp thử trên run N |
| Ước lượng | Khoảng 16 giờ (ước lượng): công cụ 4, vòng lặp và kiểm 7, phép thử trên run M 3, tài liệu 2 |
| Phụ thuộc | DA-43 (đã merge: đường ống vòng, cổng model, ba luật cơ chế). DA-49 nhiệm vụ 2.1 (lớp nối `ToolSpec` sang schema công cụ, đang làm ở phiên riêng): vòng lặp dùng lại lớp đó, không viết bản thứ hai |

## Story

Là người phân tích một vòng eval, tôi muốn agent tự điều tra các cụm lỗi qua nhiều bước: tự chọn công cụ, đọc fact, tự nêu giả thuyết, gọi thêm công cụ để kiểm hoặc bác, rồi kết luận kèm hành động dữ liệu cụ thể. Như vậy agent tìm được cơ chế lỗi mà chưa ai viết luật cho nó, thay vì chỉ xếp hạng giả thuyết do luật sinh.

Vì sao cần, đo ngày 26/11/2026 trên run M (`docs/g0/agent-qa.md` mục 9.9): model chỉ có vai `rank`, nên trước khi có luật nó không nêu được cơ chế nào; ba cơ chế (khay nằm cao hơn mặt đặt, lệch góc, khay nghiêng khi còn trong tay) chỉ xuất hiện sau khi người viết ba luật bằng tay, sau khi đã biết số nhóm A đo. Với một lỗi kiểu mới ở run sau, agent hiện nay sẽ lại trả "không luật nào khớp".

## Cách làm

**[Đề xuất]** Claude 27/11/2026, theo yêu cầu thiết kế của phiên điều phối cùng ngày. **[Đã chốt]** năm điểm ở cuối mục: Hiếu 27/11/2026.

### Chỗ đứng trong đường ống

Một bước mới `investigate`, sau `hypothesize` (sàn code đã có) và trước `judge`. Bật bằng `fw agentqa round --investigate`; mặc định tắt, nên mọi số đã đo của DA-43 giữ nguyên. Bước dùng cổng model, `model_calls.jsonl` và hàng rào lớp dữ liệu sẵn có.

### Một bước của vòng lặp

Mỗi lượt, model nhận: danh sách cụm, các fact đã có (kèm một dòng nghĩa của từng fact), danh sách công cụ với tham số là miền đóng tính từ gói, các giả thuyết đang mở, và ngân sách còn lại. Nó trả một JSON theo schema, đúng một trong bốn hành động:

| Hành động | Nội dung | Code làm gì |
|---|---|---|
| `call_tool` | tên công cụ, tham số | kiểm tham số bằng `check_params`, chạy, ghi fact mới, đưa lại cho model |
| `propose` | giả thuyết mới cho một cụm: câu mô tả, chẩn đoán và loại can thiệp trong danh sách đóng, fact ủng hộ, fact phản bác | kiểm id fact có thật; ghi là giả thuyết của model, trạng thái "mở" |
| `drop` | bỏ một giả thuyết của chính nó, kèm fact bác | ghi lại; giả thuyết của luật không bỏ được |
| `conclude` | với mỗi giả thuyết giữ lại: nội dung dữ liệu cần thu, phép kiểm rẻ nhất nên chạy trước | chuyển sang kiểm cuối |

Giao thức là JSON qua cổng model sẵn có, không dùng API gọi công cụ riêng của nhà cung cấp nào, nên chạy được với model tự host. Vòng lặp dừng khi model `conclude`, hoặc hết trần (số bước, số lời gọi, token, tiền; ghi trong `roles.yaml`, vai `investigate`). Hết trần thì giữ các giả thuyết đã qua kiểm, phần còn lại rơi về sàn code. Mọi bước ghi vào `investigation.jsonl` của thư mục lần chạy, kể cả phần lập luận của model, để người đọc lần lại được.

### Công cụ cần thêm

13 công cụ hiện có chỉ trả số gộp theo cụm do luật định trước; model không nhìn được số đo từng lượt, nên không có gì để suy luận. Thêm hai công cụ tổng quát, không gắn với cơ chế nào:

| Công cụ | Tham số (đều là miền đóng tính từ gói) | Fact trả về |
|---|---|---|
| `measure_compare` | cụm; một số đo dạng số có trong outcome (tên, thành phần nếu là vectơ; góc nghiêng suy từ quaternion do code tính); nhóm đối chiếu: lượt thành công của run, hoặc một cụm khác | trung vị của cụm và của nhóm đối chiếu; số lượt của cụm nằm ngoài khoảng phân vị 5–95 của nhóm đối chiếu; nếu số đo có ngưỡng trong cấu hình bộ chấm thì số lượt vượt ngưỡng; một cờ "tách biệt" do code tính |
| `measure_tally` | cụm; một số đo dạng cờ hoặc chuỗi (ví dụ tay chạm khay, khay ở bàn nào) | số lượt theo từng giá trị, trong cụm và trong nhóm đối chiếu |

Bổ sung 27/11/2026 (review của phiên điều phối): khi gói có artifact điều kiện (`Condition`, thứ `coverage_distance` đã đọc), hai công cụ nhận cả tham số điều kiện của lượt (ví dụ khoảng cách hai bàn, vị trí đứng ban đầu, khối lượng linh kiện) như một số đo, cùng luật miền đóng. Câu hỏi "tham số nào của mức 2 gây lỗi" chưa ai có đáp án, nên đây là phần mù của phép thử trên run M. Gói run M chưa có artifact điều kiện; xem ghi chú.

Model không bao giờ truyền con số: ngưỡng lấy từ dữ liệu (phân vị của lượt thành công) hoặc từ cấu hình bộ chấm. Hai phân vị 5 và 95 là **giả định**, ghi trong cấu hình. Sửa theo review 27/11/2026: nhóm đối chiếu mặc định là lượt thành công **cùng mức** với cụm (`successes_same_level`); "mọi mức" là lựa chọn riêng. Cờ "tách biệt" chỉ có khi cụm đủ cỡ tối thiểu (3, **giả định**). Mỗi lời gọi trả cả số lượt của nhóm và số lượt thiếu số đo.

### Các chốt giữ nguyên

- **Số từ code.** Mọi con số trong kết luận là fact do công cụ sinh, dẫn bằng `{F#}`; bước `verify` kiểm lại như với vai `rank`.
- **Giả thuyết của model phải có bằng chứng tách biệt.** Một giả thuyết của model chỉ được giữ khi dẫn ít nhất một fact so sánh do code tính (cờ "tách biệt", hoặc số lượt vượt ngưỡng chiếm quá nửa cụm). Thiếu thì ghi là "chưa đủ bằng chứng" và xếp dưới sàn code. Sửa 27/11/2026 (Hiếu đồng ý sau lần chạy đầu trên run M): số đo mà bộ chấm đã đặt ngưỡng chính là số đo định nghĩa nhãn lỗi, nên "vượt ngưỡng" hay "tách biệt" trên số đo đó chỉ nhắc lại nhãn và không còn tự nó đủ. Bằng chứng giữ giả thuyết là cờ "tách biệt" đúng, của chính cụm đó, trên một số đo bộ chấm không đặt ngưỡng.
- **Không thấp hơn sàn code.** Giả thuyết của luật không bị xoá hay sửa. Bước `investigate` hỏng, hết ngân sách hay bị loại thì kết quả đúng bằng lần chạy không có nó.
- **Lớp dữ liệu.** Gói không được xác nhận `public` không tới model hosted; cùng phép kiểm của cổng model.
- **Không sửa `flywheel.contracts`.** Giả thuyết của model phải vừa `RoundHypothesis` hiện có. Việc đầu tiên của nhiệm vụ 2.3 là kiểm điều này; nếu không vừa thì dừng và báo Hiếu.
- **Chỉ đề xuất.** Agent không chạy sinh dữ liệu, không train, không đọc `vault/`, file đáp án hay `docs/`.

### Hành động trong đầu ra

Với mỗi giả thuyết giữ lại: loại dữ liệu (danh sách đóng, như hiện nay), **nội dung cụ thể** (ví dụ "demo sửa lệch góc lúc tới bàn B"), và phép kiểm rẻ nhất nên chạy trước. Nội dung cụ thể là lời văn của model: trang kết quả đánh dấu rõ là "lời của model", phải dẫn fact, không được mang số ngoài fact. Chi phí chỉ có khi gói có sổ chi phí.

### Phép thử chấp nhận

1. **Run M, tắt ba luật.** Thêm công tắc `disabled_rules` trong cấu hình agent (thuộc mã băm agent; không xoá luật). Chạy `--investigate` với `place_rests_raised`, `place_yaw_miss`, `tilt_while_carried` tắt. Đo: agent tự tới được cơ chế nào trong ba; số bước, số lời gọi, token, thời gian; mọi giả thuyết sai hoặc câu đọc sai fact. Lặp ba lần để thấy độ ổn định. Báo đúng kết quả, kể cả khi không tới.
2. **Run N (khoảng 30/11/2026).** Ca chưa ai xem đáp án: chạy trước, sau đó mới đối chiếu với số nhóm A.

Giới hạn của phép thử 1, nói trước: người thiết kế hai công cụ mới đã biết đáp án của run M, nên công cụ có thể vô tình hợp với ca này. Chỉ run N mới là phép thử mù. Ngoài ra 24 trong 136 lượt thành công của run M cũng có khay nằm cao, nên cơ chế "khay nằm cao" có thể không tách biệt theo phân vị; nếu vậy agent không tới được và đó là kết quả cần báo, không phải lỗi cần lách.

### Năm điểm Hiếu đã chốt (27/11/2026)

| # | Câu hỏi | Đã chốt |
|---|---|---|
| 1 | Giả thuyết của model đã qua kiểm có được xếp trên giả thuyết của luật không | Có, trong cùng nhóm; giả thuyết hệ thống (bộ chấm, đo) của luật vẫn đứng trên và vẫn chặn tiêu dữ liệu |
| 2 | Trần ngân sách một vòng | 30 bước, 40 lời gọi, 400 000 token vào, 1 USD (ước lượng, chưa đo). Hiếu nâng ngày 27/11/2026 sau ba lần đo: 50 bước, 60 lời gọi, 1 000 000 token vào; 1 USD giữ nguyên |
| 3 | Model nào cho run M và run N | `claude-opus-5-5` qua cổng ckey (dữ liệu sim là `public`); cổng là bên bán lại, không xác minh được model sau tên |
| 4 | Nội dung dữ liệu là lời văn của model, có nhãn | Chấp nhận, vì danh sách đóng không tả được nội dung demo |
| 5 | Số công cụ lên 15 | Chấp nhận; máy chủ MCP của DA-49 đọc sổ đăng ký nên tự có hai công cụ mới |

## Tiêu chí chấp nhận

1. `measure_compare` và `measure_tally` có trong sổ đăng ký; mọi tham số là miền đóng tính từ gói; không tham số nào nhận số tự do hay đường dẫn. Có test, gồm số đo thiếu (`not_judged`) và vectơ, quaternion.
2. `disabled_rules` tắt được luật theo id, đổi mã băm agent, id lạ bị từ chối. Có test.
3. Bước `investigate` chạy vòng lặp bốn hành động qua cổng model; trả lời sai schema, tham số ngoài miền, id fact không có đều bị từ chối và ghi lại mà không làm hỏng lần chạy. Có test với model giả của `flywheel.testkit`.
4. Vòng lặp dừng đúng ở từng trần; mỗi trần có test. Hết trần hoặc lỗi cổng thì `assembly.json` bằng đúng lần chạy không có `--investigate` (test so sánh).
5. Giả thuyết của model thiếu fact so sánh do code tính không bao giờ xếp trên sàn code. Có test.
6. Mọi câu trong kết luận dẫn fact; câu mang số ngoài fact bị `verify` loại. Có test.
7. Gói không `public` với cấu hình cổng hosted: bước `investigate` không gửi lời gọi nào. Có test.
8. `investigation.jsonl` ghi đủ từng bước; `run.json` cộng lời gọi và token của bước vào tổng.
9. Phép thử 1 trên run M đã chạy ba lần; `docs/g0/agent-qa.md` có mục kết quả với bảng: cơ chế nào tới được, số bước, token, điều sai. Số ghi là sơ bộ.
10. `uv run ruff check`, `uv run mypy` (không thêm lỗi), `uv run pytest`, `uv run lint-imports`, `scripts/repo/check_links.py`, `scripts/repo/pr_guard.py` qua.

## Nhiệm vụ

- [x] 1.1 Viết story và thiết kế (file này)
- [x] 2.1 Công cụ `measure_compare` và `measure_tally`, đăng ký, có test (AC 1)
- [x] 2.2 Công tắc `disabled_rules`, có test (AC 2)
- [x] 2.3 Bản ghi và schema của vòng lặp; kiểm giả thuyết của model vừa `RoundHypothesis`; vai `investigate` trong `roles.yaml`, prompt (AC 3, 8)
- [x] 2.4 Bước `investigate`: vòng lặp, trần ngân sách, rơi về sàn code, có test (AC 3, 4, 7)
- [x] 2.5 Luật giữ giả thuyết của model và `verify` cho kết luận; trang kết quả đánh dấu lời của model, có test (AC 5, 6)
- [x] 3.1 Phép thử trên run M với ba luật tắt, ba lần; ghi kết quả (AC 9)
- [x] 3.2 Chạy đủ kiểm tra (AC 10)
- [ ] 4.1 Run N: chạy trước, đối chiếu sau; ghi kết quả (khi nhóm A có outcome)

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-eval/src/flywheel/eval/agentqa/round/` (bước mới `investigate.py`; `pipeline.py`, `records.py`, `hypotheses.py`, `verify.py`, `assemble.py`, `render.py` chỉ ở chỗ nối bước mới; `version.py` cho mã băm agent; `judge.py` chỉ danh sách dấu hiệu fact so sánh và một trường chở khối `investigate` của `roles.yaml`; `gateway.py`, `gateway_config.py` chỉ cho vai tùy chọn `investigate`)
- `packages/flywheel-eval/src/flywheel/eval/agentqa/tools/` (hai công cụ mới, `registry.py`)
- `packages/flywheel-eval/src/flywheel/eval/agentqa/cli.py` (chỉ cờ `--investigate` và `--disable-rule`)
- `configs/eval/agentqa/` (`roles.yaml`, `agent.yaml`, `routing.yaml` cho route và ngân sách của vai mới, `prompts/investigate.md`, `tasks/tray.yaml`)
- `packages/flywheel-eval/tests/unit/agentqa/round/`, `packages/flywheel-eval/tests/unit/agentqa/tools/`
- `docs/g0/agent-qa.md` (chỉ thêm mục kết quả)
- `packages/flywheel-eval/src/flywheel/eval/agentqa/mcp/bridge.py`: Hiếu đồng ý ba chỗ ngày 27/11/2026 (PR 239 đã merge). Chỉ ba chỗ `DOMAIN_SCHEMAS`, `_PARAM_HELP`, `DESCRIPTIONS` và dòng import đi kèm, cho bốn miền tham số và hai công cụ mới; thiếu thì test của lớp nối DA-49 hỏng khi gộp với master

## Ghi chú cho người làm

- Không sửa `agentqa/mcp/` (DA-49), `agentqa/endpoint.py`, `agentqa/bench/`, `flywheel.contracts`, `pyproject.toml`, `uv.lock` hay workflow CI. Lớp nối `ToolSpec` sang schema của DA-49 chỉ được import; nếu nó chưa vào master khi tới nhiệm vụ 2.4 thì dừng và báo, không chép lại.
- Hai công cụ mới không được nhắc tới độ cao, góc hay khay trong mã: tên số đo đến từ outcome của gói.
- Prompt của vai `investigate` không được chứa đáp án của run M hay tên ba cơ chế.
- Người chạy phép thử không mở `docs/he/` và thư mục đáp án; số nhóm A cho run M đã nằm trong `docs/g0/agent-qa.md` mục 9.9 và chỉ dùng để đối chiếu sau khi chạy.
- Lỗi đã thấy ở run M: model đọc sai nghĩa một tên fact và câu đó qua được phép kiểm vì không mang số. Vì vậy mỗi fact đưa cho model phải kèm một dòng nghĩa do công cụ viết, và báo cáo phép thử phải đếm các câu đọc sai.
- Kết quả thi lại của `C70_R1` không trình bày (Hiếu, 16/11/2026): không dùng gói chứa kết quả này.
- Lời gọi model hosted chỉ chạy khi Hiếu đồng ý; khóa API đọc từ biến môi trường, không ghi vào file hay log.
- Trần 1 USD cho 400 000 token vào là ước lượng và có thể thấp với `claude-opus-5-5`: đo ở lần chạy đầu trên run M, báo Hiếu số thật trước khi lặp ba lần.
- Một việc ngoài phạm vi file hiện nay, **chờ Hiếu quyết** (27/11/2026), chưa làm:
  - `packages/flywheel-psi0/src/flywheel_psi0/tray/export_conditions.py` chưa xử lý cảnh đồ gá, nên chưa xuất được `Condition` cho run M (tập eval ở `fwdata/tray/eval-sets/jig-m-rp_a410d01efa62`).
- Số chưa đo ghi là ước lượng.

## Kiểm thử

- `uv run pytest packages/flywheel-eval/tests/unit/agentqa`
- `uv run ruff check`, `uv run mypy` (lệnh đủ ở README gốc), `uv run pytest`, `uv run lint-imports`
- `python3 scripts/repo/check_links.py`
- `python3 scripts/repo/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"`

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
