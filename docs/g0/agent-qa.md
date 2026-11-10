# Agent QA/QC (DA-20)

Agent đọc artifact của từng stage (dataset, train, stage 1, stage 3, inference, eval), rồi ra `AgentReport` cùng trang HTML tĩnh để kỹ sư duyệt. Code tính mọi con số. Model chỉ xếp hạng, giải thích, đề xuất và ước lượng, và mọi câu của model phải trích dẫn fact của code. Story: [DA-20](../product/stories/DA-20-agent-qa-qc.md). Bộ chấm: [defect-bench](defect-bench.md) (DA-31).

Trạng thái 7/11/2026: code và test của cả 7 nhiệm vụ con đã có; nhiệm vụ 1–4 xong. Nhiệm vụ 5, 6, 7 còn mở vì AC 6, 7, 8 đòi chạy model thật (Nemotron, Qwen3.5-4B), mà mọi lần chạy dưới đây đều dùng model giả (`EchoModel`) trên laptop. **Chưa có số đo nào với Nemotron**; runbook ở mục 5. Ngày 7/11 sửa theo review của #151: chặn endpoint ngoài mạng, link vào `vault/`, số mượn fact không trích (mục 1).

Cập nhật 11/11/2026: sửa issue #175 (lần đầu chạy Nemotron thật, Hưng 9/11). Agent lên **bản 2** (`version` trong `agent.yaml`): đổi fact, prompt và cửa sổ. Bản 2 **chưa chấm** với Nemotron trên bộ lỗi cấy, nên chưa được dùng cho demo trước khi chạy lại theo mục 5.1 và chấm bằng DA-31. Chi tiết ở mục 3.5.

## 1. Luồng chạy

```
artifact (file hoặc thư mục)
  │  inputs.py: đọc theo danh sách tên file đã biết; từ chối vault/ và answers/
  ▼
analyze.py (code): mỗi chủ thể (dataset, train/<job>, rtc/<job>, probe, eval) ra
  FactBook (F1, F2, …: tên, giá trị, nguồn, đơn vị) + danh sách ứng viên phát hiện
  · ứng viên "code": phép kiểm hoặc bộ phát hiện của làn đã bắt (QA tầng 4, F-TRAIN, R1/R2, O1–O4)
  · ứng viên "hint": dấu hiệu code thấy nhưng không kết luận (ví dụ D5: hai episode cùng dấu vân QA)
  │
  ▼
agent.py (model): gửi fact + ứng viên theo lô, vừa cửa sổ server (16K token, tính 2,5 ký tự/token);
  bỏ fact không ứng viên nào trích trước; vẫn vượt thì từ chối, không gửi để server cắt
  model trả {decisions, added, estimates}; code kiểm từng câu:
  · số trong câu phải khớp một fact mà chính mục đó trích (hoặc dạng % của fact tỉ lệ);
    `12,000`, `120ms`, `10x`, hai vế của `45/90` đều là số; sai thì gửi lại 1 lần
  · mỗi ứng viên cần đúng một decision, `keep` là true hoặc false
  · mã phát hiện phải hợp với stage (stage không có mã thì không được thêm); target phải là
    một đơn vị có trong đầu vào
  · bỏ ứng viên code phải có `reason` (cùng luật số); ứng viên bị bỏ ghi vào dropped.jsonl
  · không được thêm mã có trong `cleared_by_code` (bộ phát hiện đã xét và không thấy lỗi)
  · ước lượng phải có basis là fact
  sai hai lần thì báo cáo "broken", không có phát hiện nào
  │
  ▼
AgentReport (reports.jsonl) → NNN-<stage>.html + figures/*.svg + index.html
                            → dropped.jsonl (ứng viên code model bỏ, kèm lý do và fact)
                            → estimates.jsonl (ước lượng; số đo thật ghi dòng riêng)
                            → LedgerEntry: một dòng estimated, một dòng measured (activity agent_qa)
kỹ sư: fw agentqa review → <report_id>.review.json (AgentReview, append-only)
```

Hai điểm thiết kế:

- **Tách code với hint.** Ứng viên mang `origin` (code hoặc hint) trong lượt gửi cho model, để model biết đâu là bộ phát hiện đã bắn và đâu là dấu hiệu phải tự cân nhắc. Model giữ một hint thì hint đó thành phát hiện; model bỏ hint thì chỉ còn phần của code. `origin` **không** đi vào `AgentFinding` (hợp đồng không có trường này), nên DA-31 không đọc được nó. DA-31 tách phần agent thêm bằng cách tự chạy lại lớp code từ khóa `code` trong spec rồi so với phát hiện của agent (design mục 9.2). Muốn lưu `origin` trong báo cáo thì cần PR hợp đồng (mục 6).
- **Endpoint chỉ trong mạng của đội.** URL phải là loopback, IP mạng riêng hoặc host khai trong `local_hosts`; request bỏ qua biến proxy và từ chối redirect. Bất biến "dữ liệu `restricted`, `internal` không tới API hosted" vì vậy không chỉ dựa vào config. Cách kiểm host và opener bỏ proxy theo commit `cbdfc295` của Hưng.
- **Model hỏng không được tính công.** Endpoint chết, JSON sai hay câu bịa số đều cho báo cáo `broken` không có phát hiện nào. Như vậy bộ chấm không ghi cho agent những phát hiện mà thực ra là của code.

| Module | Việc |
|---|---|
| `endpoint.py` | Client OpenAI-compatible (`/chat/completions`, JSON mode); `RecordingModel` / `ReplayModel` để ghi và phát lại câu trả lời |
| `inputs.py` | Danh sách file được đọc, kiểm schema từng dòng, sha256; từ chối `vault/`, `answers/` cả khi đi qua link |
| `facts.py`, `numbers.py` | FactBook; kiểm số trong câu theo độ chính xác đã viết |
| `analyze.py` | Chủ thể và ứng viên; train gọi `flywheel.eval.api.diagnose_train`, RTC gọi R1/R2 của `diagnosis.system` |
| `agent.py` | Prompt, chia lô, kiểm câu trả lời, xếp hạng, gộp trùng (mã, target) |
| `figures.py` | SVG viết tay: dataset, loss, RTC, action dự đoán so với thật (kèm link video), lưới stage 1 |
| `html.py` | Trang báo cáo; `{F#}` hiện thành giá trị kèm đơn vị, title là id · tên fact |
| `review.py`, `estimates.py` | `AgentReview`; ước lượng và số đo là hai dòng riêng |
| `vision.py` | Lượt hai với Qwen3.5-4B: mô tả ảnh thành fact chữ; câu có số bị bỏ |
| `run.py`, `cli.py` | `fw agentqa run · review · html · estimates` |

Cấu hình: [`configs/eval/agentqa/agent.yaml`](../../configs/eval/agentqa/agent.yaml). Prompt: [`prompts/system.md`](../../configs/eval/agentqa/prompts/system.md), sha256 của prompt ghi vào mỗi báo cáo.

## 2. Lệnh

```bash
uv run fw agentqa run --input <thư mục hoặc file> [--input …] --out fwdata/agentqa/<tên lần chạy> \
    [--record replies.jsonl | --replay replies.jsonl] [--vision --image <png> …] [--store <gốc store>]
uv run fw agentqa review --reports <out>/reports.jsonl --report-id <rep_…> --reviewer hieu \
    --decide find_001=agree --decide find_002=override:"lý do"
uv run fw agentqa html --reports <out>/reports.jsonl --out <thư mục> [--reviews <thư mục review>]
uv run fw agentqa estimates --path <out>/estimates.jsonl [--measure <rep_…>/<est_…>=<giá trị> --source <artifact>]
```

`--out` phải là thư mục mới. Lỗi đầu vào thoát mã 2. Lần chạy có báo cáo `broken` vẫn ghi đủ file, rồi thoát mã 1. Đổi URL endpoint mà không sửa config: `FW_AGENTQA_AGENT_URL`, `FW_AGENTQA_VISION_URL`.

## 3. Kết quả trên laptop, 6/11/2026

Tất cả dùng `EchoModel`: giữ mọi ứng viên code, bỏ mọi hint, câu chỉ trích fact. Đây là kiểm lớp code và đường ống, **không phải số của Nemotron**, và chưa đủ cho AC 6 (chấm agent trước khi dùng).

### 3.1 Bộ ca mẫu (nhiệm vụ 5)

`tests/contract/agentqa/test_agentqa_cases.py` có 13 ca: train sạch, NaN, phân kỳ; RTC sạch, trễ vượt τ, cạn buffer quá d; dataset sạch, NaN, sai câu lệnh, hint trùng D5; stage 3 lỗi nhóm, sai số tăng trong chunk, sạch. Thêm hai ca: model giữ hint D5 thì báo cáo có D5; model bịa số thì báo cáo `broken`. Tất cả qua trong CI.

### 3.2 Bộ log cấy DA-27, chấm bằng DA-31

Bộ log dựng bằng `python -m flywheel.data.inject.log_defects` (seed mặc định). Bản có lỗi là `bench-c6da75e9ff36`, 30 lỗi cấy (T1–T8, R1, R2, mỗi loại 3). Bản sạch là `bench-cfcb0ba66776`.

| Đại lượng | Lớp agent (EchoModel) |
|---|---|
| Precision theo mã T1–T8, R1, R2 | 3/3 mỗi mã |
| Báo nhầm trên bản sạch | 0/40 đơn vị (cận trên) |
| Agent thêm so với code (`agent_adds`) | 0 ở mọi loại, đúng như mong đợi vì Echo không thêm gì |
| Review | 30 phát hiện `unreviewed`, chưa ai duyệt |

Vì `EchoModel` giữ mọi ứng viên code, precision và báo nhầm ở đây chỉ đo lớp code: chúng cho biết đường từ bộ phát hiện qua `AgentReport` tới bộ chấm không làm rơi hay lệch phát hiện nào. Chúng chưa nói gì về việc model giữ, bỏ, thêm hay giải thích đúng không.

### 3.3 Log thật (nhiệm vụ 7, báo riêng với lỗi cấy)

Đầu vào: ba job fine-tune Ψ₀ đã chạy xong, mỗi job 40k step, cùng một log RTC.

| Chủ thể | Nguồn | Phát hiện của code |
|---|---|---|
| `train/da26-t2-ft-vego-n20-s0` | DA-26 (HE, có ego) | T1, T2, T8 |
| `train/da26-t2-ft-vnoego-n20-s0` | DA-26 (HE, không ego) | T1, T2, T3, T8 |
| `train/da34-t2-ft-c-s0` | DA-34 (tray, C) | T1, T2, T8 |
| `rtc/job-g1` | mẫu `da38_g1` trong test của `diagnosis.system` | không có (p99 trễ 0,05 s; delay tối đa 3 step) |

Cả ba job đều có loss giảm bình thường, ví dụ train 46,4 → 0,12 và val 45,8 → 0,29. Vì vậy các phát hiện trên nhiều khả năng là **báo nhầm của bộ phát hiện F-TRAIN trên log thật**, không phải lỗi của job. Agent không sửa được chuyện này vì agent chỉ diễn giải fact của code. Đây là việc của làn Đánh giá (Châu):

- **T2, lỗi logic khi val đo thưa.** Val đo mỗi 2000 step (0, 2000, 4000, …). Baseline là trung vị 3 lần đo đầu, tức gồm cả step 2000. Điểm được chấm lại là lần đo đầu tiên từ `n_steps` = 2000 trở đi, cũng là step 2000. Kết quả: mức giảm bằng 0 dù val đã giảm 45,8 → 2,3. Cần một trong hai: lấy điểm chấm sau cửa sổ baseline, hoặc lấy baseline trước `n_steps`.
- **T8, ngưỡng giả định thấp hơn mức thật.** `max_grad_norm` = 10 (giả định trong `train.yaml`). Trên log thật, trung vị `grad_norm_action` là 7–8 và p99 khoảng 46–51; khoảng 12–13 nghìn trên 40 nghìn bản ghi vượt 10. Ghi chú hiệu chỉnh trong config ("p99 trên job sạch") cho ngưỡng khoảng 50.
- **T1 (k = 10, cửa sổ 500 step)** báo ở step 3588–6191 với tỉ lệ 3,9–5,2. Cần xem có phải spike thật không trước khi chỉnh `k`.
- **T3** chỉ báo trên job không ego: val tăng 3 lần đo liên tiếp từ step 18000. Có thể là overfit thật; cần người xem.

Bộ log cấy cho 0 báo nhầm trên bản sạch (mục 3.2), nhưng log thật thì báo trên cả ba job. Như vậy bản sạch của DA-27 chưa giống log Ψ₀ thật, ít nhất ở grad norm và nhịp đo val.

### 3.4 Endpoint chết

`FW_AGENTQA_AGENT_URL=http://127.0.0.1:9/v1 fw agentqa run …` cho báo cáo `broken` với lý do `endpoint failed: … Connection refused`, không có phát hiện nào, thoát mã 1. Laptop chưa có Ollama nên đây là đường mặc định nếu chạy thật trên laptop.

### 3.5 Sửa issue #175 (11/11/2026, agent bản 2)

Issue #175 chạy Nemotron thật trên hai job của bộ log cấy và thấy ba lỗi. Bảng dưới ghi cách sửa; mỗi dòng là một commit `DA-20/5.x`.

| Lỗi trong #175 | Nguyên nhân | Sửa |
|---|---|---|
| 36 ứng viên T6 cùng trỏ F19–F21 (giá trị chiều 0) | Tên fact không có nhóm, chiều; `FactBook.add` gộp theo tên và bỏ giá trị mới (Châu tìm ra) | Tên fact mang nhóm, chiều (`T6_value_dim3`, `T6_start_step_dim3`); ngưỡng chung giữ một fact. `FactBook` từ chối một tên mang hai giá trị (`FactClash`) |
| Model đọc ngược T6 ("dưới ngưỡng nên không lỗi") | Fact ngưỡng không ghi phía nào là lỗi | Fact `<mã>_flag_when`, ví dụ `T6_flag_when = "value < threshold"`. Bảng chiều `FLAG_WHEN` ở `analyze.py` chép từ bộ phát hiện DA-08, DA-13 (Finding không có trường chiều) và được kiểm trên từng phát hiện: lệch bảng thì bỏ fact chiều, ghi chú. Prompt luật 3 giải thích fact này |
| Bỏ hết ứng viên code mà báo cáo vẫn `ok`, 0 phát hiện, không lời nào | Bỏ ứng viên không cần lý do, không ghi lại | Bỏ ứng viên `origin = code` phải có `reason`. Ứng viên bị bỏ ghi vào `dropped.jsonl`, hiện ở đầu trang HTML, có cột trong `index.html`, và CLI cảnh báo. Hợp đồng không cho báo cáo `ok` có `problems`, và bỏ là quyền của model (DA-31 tính), nên không đánh `broken` |
| Thêm T1 "phân kỳ" trên job sạch, câu lại nói "hội tụ" | Model được thêm cả mã mà bộ phát hiện đã xét và thấy sạch | `cleared_by_code` trong payload: mã bộ phát hiện đã xét, không bắt, không bỏ qua nhánh nào. Thêm mã đó thì câu trả lời bị gửi lại, lần hai thành `broken`. Mã bị bỏ qua (thiếu số đo) vẫn được thêm |
| Cấu hình 64K token, 3,5 ký tự/token; server chạy 16K, đo được 2,67 | Ngân sách theo cửa sổ của model, không theo server | `context_tokens: 16384`, `chars_per_token: 2.5`. Prompt vượt ngân sách (kể cả lượt gửi lại) bị từ chối, báo cáo `broken` kèm kích thước |

Kiểm trên bộ log cấy dựng lại bằng `log_defects` (cấu hình mặc định, cùng id bản sao với #175), chỉ lớp code, không gọi model:

- 80 chủ thể không chủ thể nào gặp `FactClash`. 3 job có 36 ứng viên T6, mỗi ứng viên trỏ giá trị riêng.
- Mọi ứng viên có ngưỡng đều kèm fact chiều. T6 cả 108 ứng viên là `value < threshold`. Không ứng viên nào lệch bảng.
- Job sạch `job-ffc08ff2de79` của #175: `cleared_by_code` = T1–T8. 36 trên 60 chủ thể train xóa đủ 8 mã, 24 chủ thể xóa 7 mã.
- 83 lượt gọi: prompt lớn nhất 13.087 ký tự (job T6 của #175, lô 20 ứng viên), trung vị 4.666, ngân sách 30.720.

Việc mở theo sau, ngoài phạm vi DA-20: DA-08 `detect_t5` cho `start_step` âm khi job ngắn hơn `t5.window_steps` (1000 step), và `DiagnosisFinding` từ chối giá trị đó. Job thật dài 40k step nên chưa gặp. Báo cho Châu.

## 4. Nhìn hình (nhiệm vụ 6)

Q-M trả lời không cho tới demo, nên `vision.enabled: false`. Code đã có: `--vision --image <png>` gửi từng ảnh (tối đa `max_images` = 6) tới model thứ hai kèm câu hỏi cố định. Câu mô tả được thêm thành fact chữ `vision_observation:<model>` với nguồn là ảnh. Câu nào có số thì bị bỏ, vì số phải do code đo. Model chính sau đó được phép trích fact này như mọi fact khác. Bộ ca mẫu chạy được với lượt nhìn hình bằng `ScriptedModel`. Với Qwen3.5-4B thật thì chưa chạy.

## 5. Runbook: chạy với model thật

Lần chạy thật đầu tiên là của Hưng trên laptop RTX 4060 8 GB, 9/11/2026 (#175), với agent bản 1. Bản 2 chưa chạy với model thật.

| Model | Vai | Tag Ollama (giả định, cần kiểm tên thật khi pull) | VRAM (ước lượng) |
|---|---|---|---|
| Nemotron 3.5 Bolt E4B, Q4_K_M | agent, chỉ đọc chữ | `nemotron-3.5-bolt:e4b`, chép thành `nemotron-3.5-bolt-e4b` (#175) | 3–4 GB theo tài liệu NVIDIA; #175 đo 6,6 GB khi nạp với cửa sổ 16K |
| Qwen3.5-4B | nhìn hình (tùy chọn) | `qwen3.5:4b` | khoảng 3–4 GB ở Q4 (giả định) |

Hai model cùng lúc không vừa 4 GB của laptop. Trên máy 3060 (12 GB) thì vừa.

Server phải chạy đúng cửa sổ `limits.context_tokens` của `agent.yaml` (16384). Endpoint `/v1` của Ollama không đặt được `num_ctx` theo request, và server không đặt `OLLAMA_CONTEXT_LENGTH` thì dùng mặc định theo VRAM (4096 trên máy của #175). Muốn cửa sổ lớn hơn thì sửa cả hai nơi, và đó là một phiên bản agent mới.

```bash
# trên máy serve (đã cài Ollama); cấu hình của #175
ollama pull nemotron-3.5-bolt:e4b
ollama cp nemotron-3.5-bolt:e4b nemotron-3.5-bolt-e4b
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_CONTEXT_LENGTH=16384 OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_MAX_LOADED_MODELS=1 ollama serve
```

#### 5.1 Chạy lại sau khi sửa #175 (Hiếu hoặc Hưng)

Bước 1, hai job của #175, để so với lần chạy bản 1. Job có lỗi phải giữ được các ứng viên T6 (hoặc ghi lý do bỏ trong `dropped.jsonl`). Job sạch không được có T1 thêm vào.

```bash
python -m flywheel.data.inject.log_defects --out ~/agentqa-bench/logs --store ~/agentqa-bench/store
export FW_AGENTQA_AGENT_URL=http://127.0.0.1:11434/v1
B=~/agentqa-bench/logs/copies
uv run fw agentqa run --input $B/bench-c6da75e9ff36/train/job-9c5054483b9a \
  --out ~/agentqa-bench/v2-calib-defect --record ~/agentqa-bench/v2-calib-defect.replies.jsonl \
  --store ~/agentqa-bench/store
uv run fw agentqa run --input $B/bench-cfcb0ba66776/train/job-ffc08ff2de79 \
  --out ~/agentqa-bench/v2-calib-clean --record ~/agentqa-bench/v2-calib-clean.replies.jsonl \
  --store ~/agentqa-bench/store
cat ~/agentqa-bench/v2-calib-defect/dropped.jsonl
```

Bước 2, cả bộ log cấy (#175 ước lượng 12–22 phút trên laptop RTX 4060, chưa đo):

```bash
uv run fw agentqa run --input $B/bench-c6da75e9ff36 \
  --out ~/agentqa-bench/v2-defect --record ~/agentqa-bench/v2-defect.replies.jsonl \
  --store ~/agentqa-bench/store
uv run fw agentqa run --input $B/bench-cfcb0ba66776 \
  --out ~/agentqa-bench/v2-clean --record ~/agentqa-bench/v2-clean.replies.jsonl \
  --store ~/agentqa-bench/store
```

Bước 3, chấm bằng lệnh ở mục 5 của [defect-bench](defect-bench.md), với `agent_reports` trỏ vào hai file `reports.jsonl` của bước 2. Lần chạy có báo cáo `broken` thoát mã 1 nhưng vẫn ghi đủ file; xem `problems` trước khi chấm. Ghi số ứng viên trong `dropped.jsonl` cùng kết quả chấm.

Ghi kết quả vào mục 3.2 thành một cột mới "Nemotron", kèm `version` của agent, revision của model và sha256 của prompt. File `--record` cho phép chạy lại đúng lần đó bằng `--replay` mà không cần GPU. Đổi tag hay quant thì sửa `models.agent.model` / `revision` trong `agent.yaml`.

Thứ tự đề xuất: bộ log cấy trước, rồi log thật ở mục 3.3, rồi hai bản sao psi-data khi DA-27 có QA work dir.

Không chạy trên máy 3060 khi Hiếu chưa đồng ý; máy dùng chung.

## 6. Khoảng trống hợp đồng (đề xuất, chưa làm)

| Thiếu | Ảnh hưởng | Đề xuất cho |
|---|---|---|
| Từng câu hỏi của P1 (khung hình, câu hỏi, câu trả lời, đáp án) trên đĩa | Lưới stage 1 (`figures.stage1_grid`) chỉ dựng được từ `P1Item` trong code; `ProbeP1` chỉ có độ chính xác gộp | Long: thêm danh sách item vào `ProbeP1`, hoặc một artifact riêng |
| Mảng action dự đoán so với thật theo episode | `figures.action_figure` chưa có nguồn từ file | Long |
| Hàm api cho R1/R2 chỉ từ log RTC | `analyze_rtc` import `diagnosis.system.runtime` giống cách bộ chấm làm | Châu (`flywheel.eval.api`) |
| Endpoint khai trong `configs/models/` (AC 1) | Hiện khai trong `configs/eval/agentqa/agent.yaml` vì `configs/models/` thuộc Hiếu | Hiếu: chép khối `models` sang `configs/models/` hoặc trỏ tới đó |
| Giấy phép OpenMDW-1.1 của Nemotron | Chưa ghi vào Source | Hiếu, trước khi giao DENSO |

## 7. Còn lại

| Việc | Ở đâu | Ghi chú |
|---|---|---|
| Chạy agent bản 2 với Nemotron trên bộ log cấy, chấm bằng DA-31 | máy có Ollama | Theo mục 5.1; cột "Nemotron" của mục 3.2. Bản 2 chưa dùng được trước bước này |
| Chạy Nemotron trên log thật | máy có Ollama | Sau mục 5.1 |
| `start_step` âm của T5 trên job ngắn | làn Đánh giá (DA-08) | Mục 3.5 |
| Sửa T2 và hiệu chỉnh T8 trên log thật | làn Đánh giá | Mục 3.3 |
| Kỹ sư duyệt 30 phát hiện | `fw agentqa review` | Để bộ chấm có điểm cho phần giải thích và đề xuất |
| Qwen3.5-4B | sau demo | Q-M = không |
