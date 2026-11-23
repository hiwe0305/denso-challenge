# DA-43 · Hệ Agent QA/QC chẩn đoán một vòng

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm. Design duyệt 19/11/2026 (Hiếu, "Approve as proposed": Q1–Q10, design bản 0.2). Kiến trúc duyệt 20/11/2026 (Hiếu, "Duyệt theo đề xuất": Q1–Q9, kiến trúc bản 0.3) |
| Người làm | Hiếu, làm cùng Claude |
| Làn | Đánh giá (`flywheel.eval.agentqa`); một lệnh xuất trong adapter `flywheel_psi0` |
| Nguồn yêu cầu | Ban giám khảo sau vòng 2: Agent QA/QC phải chạy tốt và phân tích nguyên nhân gốc của lỗi task, robot và kết quả. Design: [2026-11-19-agent-qaqc-system-design.md](../../superpowers/specs/2026-11-19-agent-qaqc-system-design.md); kiến trúc: [2026-11-20-agent-qaqc-architecture-design.md](../../superpowers/specs/2026-11-20-agent-qaqc-architecture-design.md) |
| Nhãn | `area:core` · `epic:9` |
| Sprint | Sau demo 17/11/2026 |
| Ước lượng | Khoảng 10 ngày làm việc, 70–80 giờ (ước lượng); xem cột giờ của từng nhiệm vụ |
| Phụ thuộc | Design đã duyệt. PR hợp đồng K1 chung với DA-42; K2, K3 trên nhánh `DA-43-contract`. DA-44 cho bộ phát hiện log train đã sửa (không chặn: agent gọi `flywheel.eval.api.diagnose_train` như cũ). Chạy thật trên `rtx3060` chỉ khi Hiếu đồng ý |

## Story

Là AI Engineer, tôi muốn một agent đọc toàn bộ artifact của một vòng (ảnh và video, log train, kết quả eval, log inference) và trả lời "nguyên nhân gốc là gì, kiểm gì rẻ nhất để chắc, làm gì tiếp và tốn bao nhiêu", để quyết định của vòng Failure → Data nhanh hơn mà mọi con số vẫn do code tính và tôi vẫn là người quyết.

## Tiêu chí chấp nhận

1. Lớp công cụ có đủ các công cụ ở design mục 4, chỉ đọc artifact hợp đồng, chạy trên CPU, không import làn khác hay adapter. `step_pass_table`, `relaxed_sweep`, `coverage_distance` và `paired_compare` có test đối chiếu cho ra đúng số đã ghi ở tray.md 19.2, 20.2, 20.12 trên file mẫu dựng từ cùng dữ liệu.
2. Công cụ thiếu đầu vào trả "không xét được" kèm lý do dưới dạng fact; không công cụ nào im lặng (có test).
3. Bộ đề xuất giả thuyết (bảng luật trong `configs/eval/agentqa/`) dùng từ vựng `Diagnosis` và `INTERVENTIONS_OF_DIAGNOSIS` của hợp đồng evidence card; cụm còn giả thuyết hệ thống chưa bị loại thì không có đề xuất tiêu ngân sách dữ liệu (code chặn, có test).
4. Luật trích số mở rộng theo design mục 6, luật 1–8, mỗi luật có test: tham số số viết tay trong lời gọi công cụ bị từ chối; câu của bộ tổng hợp không trích fact bị từ chối; mục model tự thêm không trích fact của chính mã đó bị từ chối; chi phí và lợi ích do code gắn.
5. Ba lỗi đã đo của bản 3 có ca kiểm riêng và qua: hai T4 tự thêm sai (agent-qa 3.7 điểm 1), sáu lần bỏ tự mâu thuẫn (điểm 2), câu của các chiều ngoài chiều xếp đầu (agent-qa 7).
6. Đầu ra là các `AgentReport` không đổi hợp đồng, cộng `RoundDiagnosis` theo PR hợp đồng đã merge (K2, K3), cộng trang HTML vòng mở đầu bằng ba dòng: nguyên nhân hạng 1, phép kiểm rẻ nhất, can thiệp kèm chi phí. Không thêm trường tạm trong mã làn khi PR chưa merge.
7. Cổng dữ liệu: agent từ chối `vault/`, `answers/`, `docs/`; gói có bản ghi không phải `public` hoặc không rõ lớp thì không gọi model hosted, dừng trước lời gọi đầu với mã thoát khác 0 (có test). Gói giả của log robot thật trong test luôn là `internal`.
8. Bộ ca lịch sử: đáp án có cấu trúc, niêm phong ngoài gói, chỉ `agentqa/casebench/` đọc, sau khi mọi báo cáo đã ghi; test rào quét các module khác. Có ít nhất 5 ca, chia tập phát triển và tập kiểm như design mục 11.2.
9. Bảng kết quả của bốn phần đánh giá (design mục 11.1–11.4) ghi vào `docs/g0/agent-qa.md`, mỗi bảng tách lớp code, agent và phần model thêm, kèm phiên bản agent, model, revision, sha256 prompt và config. Bộ lỗi cấy không tụt so với bản 3.
10. Đo ít nhất hai model cho bộ tổng hợp (M1 cục bộ; M3 hosted chỉ trên ca `public`, nếu Hiếu mở đường hosted) trên cùng bộ ca, cùng công cụ.
11. Đường ống theo kiến trúc 20/11: mỗi bước ghi file của mình vào thư mục lần chạy, có `run.json`; `--no-model` ra báo cáo chỉ bằng code; `--from <bước>` chạy lại từ một bước; `--replay` phát lại lời gọi model. Mục của model trượt kiểm thì về sàn code và lần chạy là `degraded` (có test); `AgentReport` giữ nghĩa `broken` của bản 3.
12. `uv run ruff check`, `uv run mypy`, `uv run pytest`, `uv run lint-imports` sạch; `python3 scripts/repo/check_links.py` sạch.

## Nhiệm vụ

Mỗi nhiệm vụ con một commit; giờ là ước lượng.

- [x] 0. Design và story (docs), chờ Hiếu duyệt
  - [x] 0.1 Bộ metric, cổng qua và hiện trạng so với design (design bản 0.5, mục 11.5 và 15; **[Đề xuất]**, chờ Hiếu duyệt)
- [ ] 1. Nền (1 ngày)
  - [x] 1.1 Issue "Contract change" cho K1 (cùng DA-42), K2, K3; soạn PR hợp đồng trên `DA-43-contract` kèm file mẫu và test (PR riêng, không thuộc phạm vi file dưới đây)
  - [x] 1.2 Lệnh xuất eval khay sang `scores.jsonl` theo `Score` trong adapter `flywheel_psi0`; test trên một lô mẫu
  - [ ] 1.3 Gói vòng mẫu cho test: `Score`, `TraceStep`, `TrainingMetric`, `Condition`, outcome theo K1 khi có; dựng từ lô `C_70` giai đoạn 1, chỉ dữ liệu `public`
- [ ] 2. Lớp công cụ, phần eval (2 ngày)
  - [x] 2.1 `ToolResult`, đăng ký công cụ, `task_lookup`, quy tắc "không xét được"
  - [x] 2.2 `step_pass_table`, `failure_clusters`, `paired_compare` và test đối chiếu số
  - [x] 2.3 `latch_consistency`, `signal_presence`
  - [ ] 2.4 `relaxed_sweep` (chờ K1; trước đó chạy trên file mẫu)
- [x] 3. Lớp công cụ, phần trace, train, dữ liệu (1,5 ngày)
  - [x] 3.1 `trace_stats` gồm phép đo trên lượt thành công (thời điểm quay đầu không tính được: `TraceStep` không có vị trí trong thế giới)
  - [x] 3.2 `train_window`, `lineage`
  - [x] 3.3 `coverage_distance` (đọc theo tên trong `Condition.values`); test đối chiếu với tray.md 20.12 còn nợ: repo không có vector điều kiện train
  - [x] 3.4 `cost_lookup`, `history_lookup` (bảng giá trong `costs.yaml` để trống, chờ Hiếu điền)
- [ ] 4. Khung đường ống, sàn code (2 ngày; kiến trúc 20/11 mục 5–7, 15)
  - [x] 4.1 B0 và B1: `round.yaml`, `pack.json`, nhận, lớp dữ liệu của gói; gói giả log robot thật
  - [x] 4.2 B2 thành một bước: đăng ký công cụ (`ToolSpec`), kế hoạch công cụ, thư mục lần chạy, `run.json`, `--from`
  - [x] 4.3 B3: bảng luật giả thuyết, danh mục phép kiểm, hạng của code; chặn tiêu ngân sách khi còn giả thuyết hệ thống
  - [x] 4.4 B6 và B7 với `--no-model`, ghi `assembly.json`; lệnh `fw agentqa round`; báo cáo vòng chạy hết trên gói mẫu
  - [x] 4.5 Sửa theo review PR 204 (21/11/2026): một thư mục chạy một pack, mọi lỗi của bước ghi thành `broken`, `agent_hash` theo plan thực dùng, `--from measure` với plan khác, giả thuyết từ mọi bảng cụm, B1 từ chối `Score` khác task
  - [x] 4.6 Sửa theo review lượt hai của PR 204 (21/11/2026): trần ngân sách của cổng model tính trên cả thư mục chạy, tên fact `not_judged` không phụ thuộc tham số lời gọi, ghi dấu những gì công cụ đọc từ kho, `agent_hash` thêm `agent.yaml` và `diagnosis/system.yaml`, chỉ thử lại lỗi mạng, 429 và 5xx, `lineage` không tính tiếp sau liên kết đứt
  - [x] 4.7 Bản chụp kho trong pack (`store_snapshot`, kiến trúc bản 0.5): `cost_lookup` và `history_lookup` đọc entry `ledger`, `fix_rate` của pack, không đọc kho
  - [x] 4.8 Trace thật: một run khai được nhiều entry `trace` (một file mỗi lượt); `trace_stats` ghép lượt với `Score` theo `Score.trace_sha256` bằng sha256 của entry, không theo `episode_id`; `metrics` vào `provides` của task khay
  - [x] 4.9 Bộ nhớ: B1 đọc và kiểm từng file theo dòng, không giữ bản ghi của `trace`, `metrics`, `rtc_log`; công cụ đọc lại khi cần và kiểm lại sha256 (23/11/2026; đỉnh RAM trên gói thật từ 5,8 GB xuống 365 MB)
  - [x] 4.10 Bảng luật giả thuyết lên 7 trên 8 dòng của design 5.3 (23/11/2026): controller, kỹ năng yếu, thiếu vùng phủ, ngoài miền, lỗi ở stage train; 4 phép kiểm mới; luật mang danh sách chẩn đoán nó loại trừ. Dòng "policy, không phải controller" chờ quyết định hợp đồng của Hiếu
- [ ] 5. Lớp model (2 ngày; kiến trúc 20/11 mục 8, 19–25)
  - [x] 5.1 Cổng model: hồ sơ, bảng vai × lớp dữ liệu, chặn hosted, ngân sách, ghi và phát lại
  - [ ] 5.2 Vai `adjudicate` và `rank`: prompt, schema câu trả lời
  - [ ] 5.3 B5: các phép kiểm của kiến trúc mục 25 (luật của design mục 6), ba sửa của bản 3 và ca kiểm của AC 5, phán quyết và sàn code
  - [x] 5.4 Lớp hosted kiểu OpenAI (OpenRouter) và lớp Anthropic
  - [x] 5.6 Vai `rank` chạy được trong đường ống vòng (23/11/2026; phần `rank` của 5.2 và 5.3): bước `judge` và `verify`, thư viện luật kiểm, phán quyết và sàn code, `--gateway-config`. Vai `adjudicate`, `look` và các luật kiểm riêng của chúng còn mở ở 5.2, 5.3
  - [ ] 5.5 Xuất `round_diagnosis.json` theo `RoundDiagnosis` sau khi PR hợp đồng K2 merge
- [ ] 6. Bộ ca lịch sử (1,5 ngày)
  - [ ] 6.1 Kiểm artifact của từng ca ứng viên còn đủ; loại ca thiếu, ghi lý do
  - [ ] 6.2 Đáp án có cấu trúc cho tập phát triển; tập kiểm do người không viết bảng luật soạn; niêm phong, sha256
  - [x] 6.3 `agentqa/casebench/`: rào đáp án, kiểm rò, chấm theo design mục 11.2 và 11.5 (A1–A5, D1), test rào; mốc đầu của sàn code trên ca `tray-c70-step4` ghi ở agent-qa mục 8
- [ ] 7. Đo (1 ngày; lượt trên `rtx3060` theo runbook, khi Hiếu đồng ý)
  - [ ] 7.1 Bộ lỗi cấy (DA-31), so với bản 3
  - [ ] 7.2 Bộ ca lịch sử với M1, và M3 trên ca `public` nếu được mở
  - [ ] 7.3 Báo nhầm trên gói khỏe; thời gian, chi phí, tỉ lệ `broken`, độ ổn định
  - [ ] 7.4 Ghi bảng kết quả và runbook vào `docs/g0/agent-qa.md`
- [ ] 8. Nhìn hình (0,5–1 ngày; rút được khỏi story)
  - [ ] 8.1 `frames_at`, câu hỏi đóng trong config task (vai `look`)
  - [ ] 8.2 Hiệu chỉnh trên câu hỏi code đã biết đáp án; fact `vision` chỉ ủng hộ

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa. PR hợp đồng (nhiệm vụ 1.1) đi nhánh riêng `DA-43-contract`, không thuộc danh sách này. Không sửa `agentqa/bench/` (DA-31, của Châu), file của DA-41, DA-42, DA-44.

Nhánh `DA-43-contract` (nhiệm vụ 1.1; K1–K3 đã được Hiếu duyệt trong design 19/11 mục 7.2 và kiến trúc 20/11 mục 14) chỉ sửa:

- `packages/flywheel-contracts/src/flywheel/contracts/outcome.py`, `packages/flywheel-contracts/src/flywheel/contracts/agentqa.py`
- `packages/flywheel-contracts/schemas/`
- `packages/flywheel-contracts/tests/`
- `packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/`
- `docs/product/03-architecture.md`

Danh sách chung của story:

- `docs/superpowers/specs/2026-11-19-agent-qaqc-system-design.md`
- `docs/superpowers/specs/2026-11-20-agent-qaqc-architecture-design.md`
- `docs/g0/agent-qa.md`
- `packages/flywheel-eval/src/flywheel/eval/agentqa/tools/`
- `packages/flywheel-eval/src/flywheel/eval/agentqa/round/`
- `packages/flywheel-eval/src/flywheel/eval/agentqa/casebench/`
- `packages/flywheel-eval/src/flywheel/eval/agentqa/inputs.py`, `packages/flywheel-eval/src/flywheel/eval/agentqa/agent.py`, `packages/flywheel-eval/src/flywheel/eval/agentqa/analyze.py`, `packages/flywheel-eval/src/flywheel/eval/agentqa/endpoint.py`, `packages/flywheel-eval/src/flywheel/eval/agentqa/vision.py`, `packages/flywheel-eval/src/flywheel/eval/agentqa/html.py`, `packages/flywheel-eval/src/flywheel/eval/agentqa/cli.py`, `packages/flywheel-eval/src/flywheel/eval/agentqa/run.py`
- `packages/flywheel-eval/tests/unit/agentqa/tools/`, `packages/flywheel-eval/tests/unit/agentqa/round/`, `packages/flywheel-eval/tests/unit/agentqa/casebench/`, `packages/flywheel-eval/tests/contract/agentqa/`
- `packages/flywheel-eval/pyproject.toml`: chỉ thêm `opencv-python-headless` vào nhóm tùy chọn `agentqa`, và `anthropic` vào nhóm tùy chọn mới `agentqa-hosted` (kiến trúc 20/11, Q3)
- `uv.lock`: chỉ phần do hai dòng trên sinh
- `configs/eval/agentqa/`
- `packages/flywheel-psi0/src/flywheel_psi0/tray/export_scores.py`, `packages/flywheel-psi0/tests/tray/test_psi0_tray_export_scores.py`

## Ghi chú cho người làm

- Đọc design trước, nhất là mục 4 (công cụ), 6 (luật trích số) và 11 (đánh giá); rồi kiến trúc 20/11 (đường ống, cổng model, phần B). Chỗ hai tài liệu khác nhau thì kiến trúc thắng.
- Không dựng chat trong DA-43: hỏi đáp đi qua chat của Console, đọc file của đường ống (kiến trúc Q8).
- Agent không đọc `docs/he/`: chẩn đoán của đội là đáp án của bộ ca lịch sử.
- Kết quả thi lại của `C70_R1` không vào bộ ca và không vào báo cáo (quyết định 16/11/2026).
- Không commit `fwdata/`, đáp án của bộ ca, file `--record` có dữ liệu không phải `public`, hay khóa API.
- Khóa API của model hosted (nếu được mở) đọc từ biến môi trường qua `config.py`, không nằm trong repo.

## Kiểm thử

- `uv run pytest packages/flywheel-eval/tests/unit/agentqa packages/flywheel-eval/tests/contract/agentqa`
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports` theo README gốc
- `python3 scripts/repo/check_links.py`

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 23/11/2026 | Thêm nhiệm vụ 4.9 (bộ nhớ) và 4.10 (bảng luật); design 19/11 bản 0.6 và kiến trúc 20/11 bản 0.6 ghi hiện trạng | Hiếu (soạn với Claude) |
| 23/11/2026 | Thêm nhiệm vụ 5.6 (vai `rank` trong đường ống); 5.4 xong. Hiếu chọn cổng ckey.vn và model `claude-opus-5-5` cho lần chạy thật | Hiếu (soạn với Claude) |
| 22/11/2026 | Thêm nhiệm vụ 0.1: bộ metric và hiện trạng (design 19/11 bản 0.5) | Hiếu (soạn với Claude) |
| 20/11/2026 | Hiếu duyệt kiến trúc 20/11 (Q1–Q9). Sắp lại nhiệm vụ 4 và 5 theo đường ống; thêm AC 11; phạm vi file thêm `anthropic` trong nhóm tùy chọn `agentqa-hosted`; cửa xin thêm công cụ rút khỏi story | Hiếu |
| 20/11/2026 | Thêm [kiến trúc 20/11/2026](../../superpowers/specs/2026-11-20-agent-qaqc-architecture-design.md) vào phạm vi file (đề xuất, chờ duyệt). Nhiệm vụ 4 và 5 sẽ sắp lại theo mục 15 của tài liệu đó sau khi Hiếu duyệt | Hiếu (soạn với Claude) |
| 19/11/2026 | Design duyệt theo đề xuất; story chuyển sang đang làm | Hiếu |
| 19/11/2026 | Tạo story cùng design; mã DA-43 chưa dùng trên `origin/master` | Hiếu (soạn với Claude) |
