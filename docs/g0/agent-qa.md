# Agent QA/QC (DA-20)

Agent đọc artifact của từng stage (dataset, train, stage 1, stage 3, inference, eval), rồi ra `AgentReport` cùng trang HTML tĩnh để kỹ sư duyệt. Code tính mọi con số. Model chỉ xếp hạng, giải thích, đề xuất và ước lượng, và mọi câu của model phải trích dẫn fact của code. Story: [DA-20](../product/stories/DA-20-agent-qa-qc.md). Bộ chấm: [defect-bench](defect-bench.md) (DA-31).

Trạng thái 7/11/2026: code và test của cả 7 nhiệm vụ con đã có; nhiệm vụ 1–4 xong. Nhiệm vụ 5, 6, 7 còn mở vì AC 6, 7, 8 đòi chạy model thật (Nemotron, Qwen3.5-4B), mà mọi lần chạy dưới đây đều dùng model giả (`EchoModel`) trên laptop. **Chưa có số đo nào với Nemotron**; runbook ở mục 5. Ngày 7/11 sửa theo review của #151: chặn endpoint ngoài mạng, link vào `vault/`, số mượn fact không trích (mục 1).

Cập nhật 11/11/2026: sửa issue #175 (lần đầu chạy Nemotron thật, Hưng 9/11). Agent lên **bản 2** (`version` trong `agent.yaml`): đổi fact, prompt và cửa sổ. Bản 2 **chưa chấm** với Nemotron trên bộ lỗi cấy, nên chưa được dùng cho demo trước khi chạy lại theo mục 5.1 và chấm bằng DA-31. Chi tiết ở mục 3.5.

Cập nhật 12/11/2026: Hưng chạy lại bản 2 (comment cuối của #175); review PR #185 tìm thêm một lỗi chặn và bốn lỗi nên sửa. Agent lên **bản 3** (mục 3.6). Model serve trên máy 3060 là bản GGUF của NVIDIA trên Hugging Face, không phải bản Ollama library Hưng dùng.

Cập nhật tối 12/11/2026: **bản 3 đã chạy với Nemotron trên máy 3060 và chấm bằng DA-31** (mục 3.7). Trên bộ log cấy, lớp agent bắt 30/30 lỗi cấy, precision 3/3 ở 9 mã, T4 là 3/4, báo nhầm trên bản sạch 1/40 (cận trên). Cả 82 báo cáo `ok`, không câu trả lời nào bị cắt. Hai phát hiện sai đều là T4 do model tự thêm, từ một lần đọc nhầm đơn vị (mục 3.7).

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
agent.py (model): gửi fact + ứng viên theo lô 10, vừa cửa sổ server (16K token, trừ 6144 cho câu
  trả lời và 1024 dự phòng, tính 2,5 ký tự/token); bỏ fact không ứng viên nào trích trước;
  vẫn vượt thì từ chối, không gửi để server cắt; sau câu trả lời đầu, hỏi Ollama (`/api/ps`)
  cửa sổ thật và từ chối nếu nhỏ hơn config; câu trả lời bị cắt ở max_tokens thì chia đôi lô
  model trả {decisions, added, estimates}; code kiểm từng câu:
  · số trong câu phải khớp một fact mà chính mục đó trích (hoặc dạng % của fact tỉ lệ);
    `12,000`, `120ms`, `10x`, hai vế của `45/90` đều là số; sai thì gửi lại 1 lần
  · mỗi ứng viên cần đúng một decision, `keep` là true hoặc false
  · mã phát hiện phải hợp với stage (stage không có mã thì không được thêm); target phải là
    một đơn vị có trong đầu vào
  · bỏ ứng viên code phải có `reason` (cùng luật số); ứng viên bị bỏ ghi vào dropped.jsonl
  · phát hiện thêm trên mã có trong `cleared_by_code` (bộ phát hiện đã xét, không thấy lỗi)
    bị từ chối riêng mục đó, ghi vào dropped.jsonl; phần còn lại của câu trả lời vẫn giữ
  · ước lượng phải có basis là fact
  lô nào sai hai lần thì không góp gì, báo cáo "broken" kèm mã ứng viên của lô đó;
  quyết định của các lô đã qua vẫn giữ
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

| Đại lượng | Lớp agent (EchoModel, 6/11) | Lớp agent (Nemotron, bản 3, 12/11; mục 3.7) |
|---|---|---|
| Recall theo loại T1–T8, R1, R2 | 3/3 mỗi loại | 3/3 mỗi loại (30/30) |
| Precision theo mã T1–T8, R1, R2 | 3/3 mỗi mã | 3/3 ở 9 mã; T4 3/4 |
| Báo nhầm trên bản sạch | 0/40 đơn vị (cận trên) | 1/40 đơn vị (cận trên): T4 trên `train/job-fd57c7341466` |
| Agent thêm so với code (`agent_adds`) | 0 ở mọi loại, đúng như mong đợi vì Echo không thêm gì | 0 ở mọi loại; hai mục model tự thêm đều là T4 sai |
| Review | 30 phát hiện `unreviewed`, chưa ai duyệt | 32 phát hiện `unreviewed` (30 đúng, 1 sai trên bản có lỗi, 1 trên bản sạch) |
| Model, prompt | — | `hf.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB:Q4_K_M`, digest `139e7d57c1c3`, temperature 0; prompt sha256 `5cfb01aa…f0949dfa` |

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

**Đã sửa ở [DA-44](../product/stories/DA-44-bao-nham-log-train.md) (19/11/2026).** Log thật có sẵn trên laptop trong `fwdata/` (không commit): ba job trên và năm job pair60k của DA-34 (60k step). Kết quả của `fw eval diag-train` trên cả 8 job:

| Mã | Trước | Sửa | Sau |
|---|---|---|---|
| T2 | Báo trên 8/8 job, step 2000, mức giảm 0 | Điểm chấm là lần đo val đầu tiên từ `n_steps` trở đi **nằm sau** các lần đo baseline; không có điểm như vậy thì bỏ qua | 0/8 |
| T1 | Báo trên 8/8 job, step 3410–6191 | Nhánh spike so **trung vị trượt 100 step** của loss train (`t1.smooth_steps`, mới) với `k` lần giá trị nhỏ nhất của chính đường đã làm mượt trong 500 step. Loss từng batch của job khỏe lên tới 107–215 lần giá trị nhỏ nhất trong 500 step trước, 4000–8800 bản ghi mỗi job vượt 10 lần. Nhánh NaN, Inf giữ nguyên. `k` = 4, hiệu chỉnh (đường đã làm mượt lớn nhất 1,80 lần trên 8 job, nhân 2) | 0/8 |
| T8 nhánh b | Báo trên 8/8 job, 12–18 nghìn bản ghi vượt 10 | `max_grad_norm` = 570, hiệu chỉnh: 2 × giá trị lớn thứ 6 (`max_exceedances` + 1) của `grad_norm_action` trên job tệ nhất (282,9). Không lấy p99 (42–50): T8 đếm số bản ghi vượt, ở p99 mỗi job có hàng trăm bản ghi vượt theo định nghĩa. Đỉnh lớn nhất nằm ở 2000 step khởi động (vài trăm) và một batch muộn 1224 | 0/8 |
| T5 | `start_step` âm khi job ngắn hơn 1000 step | Không trước bản ghi đầu của job | có test |
| T3 | Báo trên job không ego (step 18000) | Không sửa | Vẫn báo trên job đó và `da34-t6-ft-b-all-s0` (step 38000); cần người xem có phải overfit thật |

Ngưỡng lấy bằng lệnh mới `fw eval calibrate-train --job <log> …`, in số của từng job và luật. Bộ log cấy DA-27 sau khi sửa (lớp code, bản `bench-c6da75e9ff36`): R1, R2, T1–T8 mỗi loại bắt 3/3, không phát hiện thừa; bản sạch `bench-cfcb0ba66776` 0 phát hiện.

Còn chưa kiểm hoặc chờ quyết:

- **Đổi nghĩa T1 [Đã chốt, PO 25/11/2026]**: so loss đã làm mượt thay vì từng batch. Chữ của design mục 10 chưa sửa theo. `smooth_steps` = 100 là giả định, và `k` = 4 chỉ đúng với giá trị này.
- 8 job cùng một công thức train (Ψ₀ stage 3 của DA-26, DA-34). Công thức khác (stage 1 egocentric, batch hay lr khác) phải chạy lại `calibrate-train`.
- T8 báo ở bản ghi đầu tiên vượt ngưỡng (DA-08); job có một batch lẻ vượt rồi mới hỏng thật sẽ báo ở batch lẻ đó.
- Chưa chạy lại agent (Nemotron) trên 3 job thật sau khi sửa; agent hết thấy T1, T2, T8 vì code không còn báo, chưa đo.
- Bản sạch của bộ log cấy (DA-27, `flywheel-data/inject`) vẫn có grad norm 0,5–2 và val mỗi 250 step; đề xuất PR riêng cho giống log thật.

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

### 3.6 Sửa theo review PR #185 và lần chạy lại của Hưng (12/11/2026, agent bản 3)

Hưng chạy lại bản 2 trên hai job của #175. Kết quả: job sạch hết báo nhầm; job có lỗi giữ cả 36 ứng viên T6 và chép đúng `value < threshold`, nhưng báo cáo vẫn `broken` vì hai lỗi mới. Review PR #185 thêm ba lỗi nên sửa.

| Lỗi | Nguyên nhân | Sửa |
|---|---|---|
| B1 (lỗi A của Hưng): "dimension 20" làm cả báo cáo `broken` | Số chiều chỉ có trong tên fact và `detail`, không là giá trị fact nào | Mỗi phát hiện theo chiều có fact `<mã>_dimension_dim<n>` = n trong bằng chứng. Câu của một ứng viên được nêu số chiều của chính nó; nêu chiều của ứng viên khác ("dimensions 0-35") vẫn bị từ chối. Prompt dặn trích fact chiều |
| Một lô sai làm mất mọi lô (đề xuất 2 của Hưng) | `_assemble` xóa hết phát hiện khi có `problems` | Lô sai hai lần không góp gì và mã ứng viên của lô ghi vào `problems`; lô đã qua giữ quyết định. Báo cáo vẫn `broken` (hợp đồng: `ok` không có `problems`), CLI vẫn thoát mã 1. Bộ chấm DA-31 không đọc `status`, nên phát hiện của lô đã qua được chấm như của agent; ứng viên của lô sai không thành phát hiện, tức là tính vào recall thấp của model |
| S1 (lỗi B của Hưng): câu trả lời bị cắt ở 4096 token, không ai biết | Endpoint không đọc `finish_reason`; bản 2 viết khoảng 205 token mỗi quyết định | `finish_reason = length` thành lỗi riêng `ReplyCut`: lô chia đôi và hỏi lại, tới một ứng viên thì báo lỗi. Lô 10 ứng viên, câu trả lời tối đa 6144 token. `limits.reply_tokens` bỏ; chỉ còn `models.agent.max_tokens` |
| S2: thêm mã đã xóa làm hỏng cả câu trả lời; xóa cả mã không có kết luận | `ReplyError` cho cả lô; T4 có nhánh không kết luận mà không ghi bỏ qua | Mục thêm đó bị từ chối riêng (`refused_by_code` trong `dropped.jsonl`). T4 không bao giờ được coi là đã xóa |
| S3: `fw agentqa html` không thấy ứng viên bị bỏ | `dropped.jsonl` chỉ dùng lúc chạy | `html` đọc `dropped.jsonl` cạnh `reports.jsonl`; docstring sửa |
| S4: cửa sổ chỉ giả định, không kiểm | `/v1` của Ollama không nhận `num_ctx`; biên an toàn bằng 0 | Sau câu trả lời đầu, endpoint hỏi `/api/ps` cửa sổ server đã nạp; nhỏ hơn `context_tokens` thì báo lỗi. Server không trả lời thì CLI ghi "not reported". Thêm `safety_tokens: 1024` |

Giới hạn còn biết:

- Không kiểm câu tự mâu thuẫn (ví dụ "hội tụ" trong phát hiện phân kỳ). `cleared_by_code` chỉ chặn mã bộ phát hiện đã xét; mã bị bỏ qua vẫn thêm được với câu bất kỳ, miễn số khớp fact.
- T1 nhánh spike không kết luận ở cửa sổ có loss nhỏ nhất ≤ 0, mà không ghi bỏ qua; T1 vẫn được coi là đã xóa.
- `FactClash` dừng cả lần chạy. Đây là lỗi lập trình (đặt tên fact trùng), nên dừng to thay vì bỏ qua chủ thể.
- `version` của agent không có trong `AgentReport` (mục 6); báo cáo phân biệt phiên bản qua sha256 của prompt và dòng ledger.

### 3.7 Bản 3 với Nemotron trên máy 3060 (12/11/2026, nhiệm vụ con 5.8)

Chạy theo mục 5.1 sau khi lô S2 của DA-35 xong và GPU rảnh. Mã ở đầu nhánh `DA-20-fix-175` (`d4da6d70`), chép vào `~/denso-da20` trên máy 3060, `uv sync --locked`. Bộ log cấy dựng lại bằng `log_defects` mặc định, ra đúng hai bản `bench-c6da75e9ff36`, `bench-cfcb0ba66776` của #175. Ollama 0.32.14 nạp model với `context_length` 16384 (đọc từ `/api/ps`), khớp `limits.context_tokens`; CLI ghi "server window 16384 tokens".

| Mục | Giá trị (đo) |
|---|---|
| Model | `hf.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB:Q4_K_M`, digest `139e7d57c1c3…`, 3,4 GB VRAM khi nạp |
| Agent | bản 3, prompt sha256 `5cfb01aa8da235846bdac4c8322fc920d1839b38c277381d8b1067c9f0949dfa` |
| Câu trả lời | 96 câu (5 của bước 1, 91 của bước 2), cả 96 `finish_reason = stop`; prompt lớn nhất 6433 token, câu trả lời lớn nhất 3617 token (trần 6144); trung vị trên bản có lỗi 1936 và 1289 token |
| Hash kết quả DA-31 | `9a8e094bc01e266aeef1997a27c7b4226e814e2c93322c4ff377452deb29b57a` (dạng `da31-3`) |

**Bước 1, hai job của #175.** Cả hai đạt điều kiện của mục 5.1.

| Job | Trạng thái | Phát hiện | Bỏ | Câu trả lời | Thời gian (ledger, thực đo) |
|---|---|---|---|---|---|
| Có lỗi `train/job-9c5054483b9a` | `ok` | 1 phát hiện T6; model giữ 36/36 ứng viên T6 | 0 | 4 lô (10, 10, 10, 6), cả 4 `stop` | 266 s (ước tính 20 s) |
| Sạch `train/job-ffc08ff2de79` | `ok` | 0 | 0 | 1, `stop` | 18,6 s (ước tính 20 s) |

36 quyết định giữ thành một phát hiện vì `_assemble` gộp theo `(mã, target)` và cả 36 có cùng target là job. Câu của các ứng viên khác không vào báo cáo; người duyệt chỉ thấy câu của chiều xếp đầu (mục 7).

**Bước 2, cả bộ log cấy** (40 job mỗi bản: 30 train, 10 RTC). Cả 80 báo cáo `ok`.

| Bản | Thời gian (ledger, thực đo) | Câu trả lời | Phát hiện | `dropped.jsonl` |
|---|---|---|---|---|
| Có lỗi | 1714 s (ước tính 800 s) | 51 | 31 trên 30 job | 6 ứng viên T6 của `train/job-14bb85c54181`, `dropped_by_model` |
| Sạch | 757 s (ước tính 800 s) | 40 | 1 (T4 trên `train/job-fd57c7341466`) | 0 |

**Bước 3, chấm DA-31** (`python -m flywheel.eval.agentqa.bench`, mã của Châu không sửa; 0,53 s): bảng mục 3.2. Lớp code giữ nguyên 30/30, precision 3/3 mỗi mã, 0/40 báo nhầm. Ở cả 10 loại, `together` = `by_code` = `agent_alone` = 3 và `agent_adds` = 0: model không làm rơi lỗi nào code đã bắt, cũng không bắt thêm lỗi cấy nào.

Ba điều thấy được:

1. **Hai T4 sai cùng một kiểu.** Trên `train/job-87bb15b95cc9` (bản có lỗi, lỗi cấy là T6) và `train/job-fd57c7341466` (bản sạch), model tự thêm T4 với câu "số bước ghi log thấp hơn bước cuối". Nó so `steps_logged` = 72 (đơn vị `rows`) với `train_last_step` = 3000 (đơn vị `steps`): log ghi thưa nên hai số khác đơn vị, không phải lỗi. Câu không nói gì về mất cân bằng nhóm, và cả hai job không có fact T4 nào. T4 thêm được vì T4 không bao giờ nằm trong `cleared_by_code` (mục 3.6, S2). Kiểm số không bắt được vì cả hai số đều là giá trị fact được trích.
2. **Lý do bỏ tự mâu thuẫn.** 6 ứng viên T6 của `train/job-14bb85c54181` có `keep: false` nhưng lý do viết "value {F…} < threshold {F21} … confirming a fault". 30 ứng viên còn lại của job được giữ, nên job vẫn có phát hiện T6 và recall không đổi. `dropped.jsonl` hiện đủ 6 mục cho người duyệt. Đây là loại lỗi mục 3.6 đã ghi (không kiểm câu tự mâu thuẫn).
3. **Ước lượng.** Model ghi 2 ước lượng (`estimates.jsonl`), cả hai `low` 0, `high` 0,1. Log tổng hợp không có kết quả đo sau, nên chưa so được (AC 6).

Ledger (run plan `g0-DA-20-20261112`, store `~/denso-da20/fwdata/agentqa-bench/store` trên máy 3060): 5 cặp dòng ước tính và thực đo, mỗi dòng thực đo trỏ về dòng ước tính và ghi model, digest, "agent v3". Bản chép của báo cáo, `dropped.jsonl`, file `--record` và kết quả DA-31 ở `fwdata/agentqa-v3-3060/` trên laptop (không commit). File `--record` chạy lại được bằng `--replay` mà không cần GPU.

## 4. Nhìn hình (nhiệm vụ 6)

Q-M trả lời không cho tới demo, nên `vision.enabled: false`. Code đã có: `--vision --image <png>` gửi từng ảnh (tối đa `max_images` = 6) tới model thứ hai kèm câu hỏi cố định. Câu mô tả được thêm thành fact chữ `vision_observation:<model>` với nguồn là ảnh. Câu nào có số thì bị bỏ, vì số phải do code đo. Model chính sau đó được phép trích fact này như mọi fact khác. Bộ ca mẫu chạy được với lượt nhìn hình bằng `ScriptedModel`. Với Qwen3.5-4B thật thì chưa chạy.

## 5. Runbook: chạy với model thật

Lần chạy thật đầu tiên là của Hưng trên laptop RTX 4060 8 GB, 9/11/2026 (#175), với agent bản 1. Hưng chạy lại bản 2 ngày 12/11 (mục 3.6). Bản 3 chạy trên máy 3060 tối 12/11 (mục 3.7).

| Model | Vai | Tag Ollama (giả định, cần kiểm tên thật khi pull) | VRAM (ước lượng) |
|---|---|---|---|
| Nemotron 3.5 Bolt E4B, Q4_K_M | agent, chỉ đọc chữ | máy 3060: `hf.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB:Q4_K_M` (digest `139e7d57c1c3`, tên mặc định trong `agent.yaml`). Laptop của Hưng: `nemotron-3.5-bolt:e4b` (digest `69f2be39b309`, bản khác), đặt qua `FW_AGENTQA_AGENT_MODEL`, `FW_AGENTQA_AGENT_REVISION` | 3–4 GB theo tài liệu NVIDIA; #175 đo 6,6 GB khi nạp với cửa sổ 16K |
| Qwen3.5-4B | nhìn hình (tùy chọn) | `qwen3.5:4b` | khoảng 3–4 GB ở Q4 (giả định) |

Hai model cùng lúc không vừa 4 GB của laptop. Trên máy 3060 (12 GB) thì vừa.

Server phải chạy đúng cửa sổ `limits.context_tokens` của `agent.yaml` (16384). Endpoint `/v1` của Ollama không đặt được `num_ctx` theo request, và server không đặt `OLLAMA_CONTEXT_LENGTH` thì dùng mặc định theo VRAM (4096 trên máy của #175). Muốn cửa sổ lớn hơn thì sửa cả hai nơi, và đó là một phiên bản agent mới.

Máy 3060 chạy Ollama 0.32.14 dạng service với `OLLAMA_CONTEXT_LENGTH=16384` và `OLLAMA_KV_CACHE_TYPE=q4_0`. Laptop theo cấu hình của #175:

```bash
ollama pull nemotron-3.5-bolt:e4b
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_CONTEXT_LENGTH=16384 OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_MAX_LOADED_MODELS=1 ollama serve
export FW_AGENTQA_AGENT_MODEL=nemotron-3.5-bolt:e4b FW_AGENTQA_AGENT_REVISION=69f2be39b309
```

#### 5.1 Chạy lại sau khi sửa #175 (Hiếu hoặc Hưng)

Bước 1, hai job của #175, để so với lần chạy bản 1. Job có lỗi phải ra `ok`, giữ được các ứng viên T6 (hoặc ghi lý do bỏ trong `dropped.jsonl`), và không có câu trả lời bị cắt (`finish_reason` trong file `--record`). Job sạch không được có phát hiện sai. Tên thư mục `v2-…` dưới đây giữ như lần chạy của Hưng; lần chạy bản 3 dùng `v3-…`.

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
| `version` của agent và `origin` của phát hiện trong `AgentReport` | Báo cáo chỉ phân biệt phiên bản qua sha256 của prompt; ứng viên bị bỏ nằm ở `dropped.jsonl`, ngoài hợp đồng | Long (hợp đồng `AgentReport`) |

## 7. Còn lại

| Việc | Ở đâu | Ghi chú |
|---|---|---|
| Quyết T4 tự thêm | Hiếu | Mục 3.7 điểm 1: hai báo nhầm duy nhất của bản 3. Hướng sửa (bản 4, phải chấm lại): mục thêm phải trích ít nhất một fact của chính mã đó (`T4_…`), hoặc đặt T4 vào `cleared_by_code` khi bộ phát hiện T4 xét được nhóm. Hoặc chấp nhận 1/40 cho demo |
| Một phát hiện cho mỗi `(mã, target)` | làn Đánh giá | Mục 3.7 bước 1: câu của 35 chiều T6 còn lại không vào báo cáo. Gộp chiều vào bằng chứng của một phát hiện là đổi agent (bản mới) |
| Chạy Nemotron trên hai bản sao psi-data | máy 3060 | Khi DA-27 có QA work dir; AC 6 còn phần này và phần so ước lượng với kết quả đo |
| Chạy Nemotron trên log thật | máy 3060 | Nhiệm vụ 7; sau mục 3.7 |
| `start_step` âm của T5 trên job ngắn | làn Đánh giá (DA-08) | Mục 3.5 |
| Sửa T2 và hiệu chỉnh T8 trên log thật | làn Đánh giá | Mục 3.3 |
| Kỹ sư duyệt 30 phát hiện | `fw agentqa review` | Để bộ chấm có điểm cho phần giải thích và đề xuất |
| Qwen3.5-4B | sau demo | Q-M = không |

## 8. Đường ống vòng (DA-43): cách chạy và bộ ca lịch sử

`fw agentqa round` chẩn đoán một vòng: `pack`, `admit`, `measure`, `hypothesize`, `judge`, `verify`, `assemble`, `render`. Với `--no-model` hai bước `judge` và `verify` không chạy (sàn code). Số đo theo bộ metric của [design 19/11 mục 11.5](../superpowers/specs/2026-11-19-agent-qaqc-system-design.md).

| Mục | Giá trị |
|---|---|
| Ca | `tray-c70-step4`, tập phát triển; đáp án 26 điểm chốt từ [tray.md](../he/tray.md) 20.2 và 20.11; sha256 `3f8e03b2…`; niêm phong ngoài gói |
| Gói đang dùng | `stage1-60k-k1` (mục 9.3). Các gói trước (`stage1-60k`, `stage1-60k-src`) giữ trên đĩa, không dùng để báo số nữa |
| Lớp dữ liệu | `public`, xác nhận bằng hai bản ghi `Source` (**[Đã chốt]** Hiếu, 23/11/2026; căn cứ design 27/10 mục 8.4) |

Đối chiếu số với phân tích tay: số lượt gãy ở `approach_a` mà không hết giờ là 7, 10, 7 trên 60 ở `C_70`, `C_ALL`, `B_70`; cỡ tám cụm c1–c8 của `C_70` là 14, 12, 4, 4, 3, 3, 2, 2; phân vị 99 sai số bám của lượt thành công ở `C_70` là 2,641 và 0,385. Cả ba khớp tray.md 20.2 và 20.11.

Giới hạn của bộ ca: tên fact trong đáp án được viết sau khi đã thấy tên fact của agent, và người viết luật đã đọc chẩn đoán gốc. Đây là số của tập phát triển, một ca, 26 điểm: mọi số là số đếm và không đo khả năng tổng quát.

```bash
uv run fw agentqa round --pack fwdata/agentqa/cases/stage1-60k-k1/pack.json --out <thư mục mới> --no-model
uv run python -m flywheel.eval.agentqa.casebench --answer fwdata/agentqa/answers/tray-c70-step4.yaml \
    --run <thư mục chạy> [--floor-run <thư mục sàn code>] --out <report.json>
```

## 9. Lớp model của đường ống vòng (DA-43 5.4, 5.6)

| Việc | Cách làm |
|---|---|
| Đơn vị một lời gọi | Một cụm lỗi; tối đa 8 cụm lớn nhất (`roles.yaml`). Cụm còn lại ở sàn code, phán quyết `not_ranked` |
| Model thấy gì | Một khối JSON: cụm, giả thuyết ứng viên, phép kiểm, tối đa 60 fact. Prompt ở `prompts/rank.md` |
| Model trả gì | Thứ tự id giả thuyết, một phép kiểm, một can thiệp, mỗi câu có trích fact. Không viết số |
| Kiểm | Các luật trong `round/reply_rules.py`. Trượt thì gửi lại một lần kèm danh sách lỗi |
| Phán quyết | `accepted`, `repaired`, `rejected` (về sàn code, ghi lý do), `not_ranked` |
| Bật model thuê | Không sửa config trong repo. Chép `routing.yaml` và `hosted.yaml` ra thư mục riêng, bật `enabled`, trỏ `rank.public` sang hồ sơ hosted, rồi chạy với `--gateway-config <thư mục>` |

```bash
uv run --env-file <.env của checkout chính> fw agentqa round \
    --pack fwdata/agentqa/cases/stage1-60k-k1/pack.json --out <thư mục mới> \
    --gateway-config fwdata/agentqa/gateway-ckey
```

Điều đã học từ ba lần chạy đầu (23/11/2026; số chi tiết của chúng đã bỏ vì mục 9.3 và 9.4 thay thế):

- Gói chỉ có `Score` cho mỗi cụm đúng một giả thuyết, nên model không có gì để xếp hạng. Phải có điều kiện train (mục 9.3) mới có giả thuyết cạnh tranh.
- Cổng từ chối gói thật khi 248 trên 248 mục chưa có bản ghi nguồn xác nhận lớp `public`; rào này không nới, gói được bổ sung bản ghi `Source`.
- B1 từng nạp mọi file của gói vào RAM (đỉnh 5,8 GB). Sau nhiệm vụ 4.9: đọc từng dòng, đỉnh dưới 400 MB, đầu ra giống từng byte.
- `controller_tracking` không bắn vì lượt thành công cũng vượt τ ở cả bốn run; code không kết luận controller, khớp H2 của tray.md 20.11.
- Cổng ckey.vn là bên bán lại: không xác minh được model đứng sau một tên; token cổng báo không tin được.

### 9.3 Gói có điều kiện train, 23/11/2026

Gói `stage1-60k-k1` (`pack_26ef5704e43fdbc2`, 254 file): gói 9.1 cộng 60 điều kiện eval và điều kiện train theo từng run (`C_70`, `B_70`: 425; `C_ALL`, `B_ALL`: 606), xuất bằng `flywheel_psi0.tray.export_conditions`. Tập train của mỗi run lấy theo lát cắt ghi trong `launch.json`; không điều kiện eval nào trùng dữ liệu train. Chưa có outcome (K1): lệnh xuất đã viết, chờ PR 211 sửa một luật của hợp đồng.

| Số đo | Sàn code | Có model (`claude-opus-5-5` qua ckey.vn) |
|---|---|---|
| Giả thuyết theo luật | `label_signal_missing` 53, `weak_skill` 32, `out_of_domain` 17, `coverage_gap` 15, `scorer_latch_too_strict` 14 | |
| Cụm có từ hai giả thuyết | 53 trên 64 | |
| A1 | 22/24; bắt buộc 7/9 | 22/24; bắt buộc 7/9 |
| A2, A3, A5 | 4/4; 0; 2/2 | 4/4; 0; 2/2 |
| D1 | | 0 ở mọi cột: model giữ thứ tự của code |
| Lời gọi model | | 13 (8 lần đầu, 5 lần gửi lại); bước `judge` 264 giây |
| Phán quyết, luật kiểm lúc chạy | | 3 `accepted`, 5 `rejected` |
| Phán quyết, luật kiểm đã sửa (`--from verify`, không gọi lại model) | | 8 `accepted` |
| Thời gian cả lệnh, đỉnh RAM | 95 giây, 371 MB | 360 giây, 385 MB |

Cách đọc:

- **Năm câu bị loại lúc chạy là lỗi của rào, không phải của model.** Ba câu trượt luật "so sánh": model viết rằng một lượt vượt ngưỡng nhưng trung bình cụm dưới ngưỡng và mọi lượt trong miền, nên giả thuyết thiếu vùng phủ yếu hơn. Luật khi đó cấm mọi câu so sánh trích hai fact khác đơn vị; design 19/11 cho phép khi câu trích một fact mà code đã tự so sánh. Hai câu hỏng JSON vì dấu phẩy thừa ở lần gửi lại. Sau khi sửa (luật theo đúng design; bỏ dấu phẩy thừa ngoài chuỗi), cả 8 câu lần đầu đều qua.
- **Model lập luận được trên fact khi có giả thuyết cạnh tranh, nhưng chưa đổi kết luận nào.** Trên ca này thứ tự của code đã khớp đáp án, nên D1 bằng 0 chưa phân biệt được "model không giúp" với "không còn gì để giúp".
- **τ_cov chưa khớp số của đội.** Công cụ ra 0,868 (mức 1) và 1,920 (mức 2) cho `C_70`; design 19/11 mục 4 ghi số của đội là 1,143 và 1,524. Định nghĩa khoảng cách của công cụ (chuẩn hóa theo thành phần khai trong config task) khác của adapter. Cho tới khi đối chiếu xong, các giả thuyết `weak_skill`, `coverage_gap`, `out_of_domain` trên gói thật là **chưa kiểm chứng**.
- Cả 8 cụm được xếp hạng vẫn bị chặn tiêu ngân sách dữ liệu vì thiếu tư thế khay; hai điểm bắt buộc còn trượt nằm ở đây.


### 9.4 So sáu model qua ckey.vn, phép thử đảo thứ tự và chạy lại bộ lỗi cấy, 24/11/2026

Cùng gói `stage1-60k-k1`, cùng ca `tray-c70-step4`, mã ở `d14bb965`. Mỗi model một lần chạy (Opus 5.5 hai lần), chạy lần lượt trên laptop. Cổng ckey.vn liệt kê 642 tên model; phần lớn là kênh chuyển tiếp của tài khoản khác (tên dạng `<tài khoản>/<model>`). Chỉ dùng tên không có tiền tố. Không xác minh được model đứng sau một tên: `claude-sonnet-4.6` tự xưng là "GPT-5" khi được hỏi. Số token cổng báo không tin được (Haiku báo 82 921 token vào, Opus báo 34 150, cho cùng loại lời gọi).

**Vòng thật.** Sàn code: A1 22/24, bắt buộc 7/9, A2 4/4, A3 0, A5 2/2. Cả sáu model ra đúng các số này và D1 bằng 0 ở mọi cột. Bộ kiểm B1 chạy lại độc lập trên `assembly.json`: 0 câu của model có số ngoài fact ở mọi lần chạy. `facts.jsonl` và `hypotheses.jsonl` giống từng byte giữa tám lần chạy.

| Model | Nhận / sửa / loại (8 cụm) | Lời gọi | Bước `judge` | Cụm bị đổi hạng 1 so với code |
|---|---|---|---|---|
| `claude-opus-5-5` (lần hai) | 5 / 3 / 0 | 11 | 221 giây | 0 |
| `claude-sonnet-4.6` | 6 / 2 / 0 | 10 | 349 giây | 0 |
| `claude-haiku-4.5` | 6 / 2 / 0 | 10 | 69 giây | 2 (lên `out_of_domain`) |
| `gpt-5.5` | 3 / 1 / 4 (trượt schema) | 13 | 164 giây | 1 (lên `out_of_domain`) |
| `deepseek-v4.1-flash` | 1 / 1 / 6 (5 lời gọi trả rỗng, `finish_reason length`) | 10 | 58 giây | 0 |
| `gemini-2.5-flash-lite` | 7 / 1 / 0 | 9 | 24 giây | 1 (lên `coverage_gap`) |

Hai lần chạy Opus 5.5 (E4): hạng 1 và can thiệp giống nhau ở cả 8 cụm; phép kiểm được chọn khác nhau ở 5 cụm (lần hai trả `null` ở 6 cụm dù cụm có phép kiểm).

Hai điều bảng này cho thấy:

- **Bộ ca chưa phân biệt được model.** Bốn cụm bị ba model đẩy một giả thuyết dữ liệu lên trên giả thuyết "thiếu tín hiệu" trong khi cụm đang bị chặn tiêu ngân sách dữ liệu, nhưng điểm ca không đổi vì đáp án không có điểm chốt nào ở các cụm đó. Một ca, 26 điểm là quá ít.
- **Thiếu một luật kiểm.** B5 nhận câu trả lời xếp giả thuyết dữ liệu trên giả thuyết lỗi hệ thống khi `blocked_data_spend` đúng. Điều này trái thứ tự của thuật toán (lỗi hệ thống trước). **[Đề xuất]** thêm luật: khi cụm bị chặn, hạng 1 phải thuộc nhóm hệ thống hoặc bộ chấm.

**Phép thử đảo thứ tự** (thí nghiệm ngoài đường ống, `fwdata/agentqa/probe/`). 16 cụm (8 cụm lớn nhất có hai giả thuyết, 8 cụm lớn nhất có ba), gửi với danh sách giả thuyết đảo ngược và id đánh lại, để vị trí và số id không còn mang thứ tự của code. Một lời gọi mỗi cụm, không gửi lại. "Khớp code" nghĩa là hạng 1 của model trùng hạng 1 của code; đây là số đo độ bám fact, không phải độ đúng, vì chưa đối chiếu với đáp án.

| Model | Trả lời hợp lệ ngay lần đầu | Khớp code, cụm hai giả thuyết | Khớp code, cụm ba giả thuyết | Trung vị một lời gọi |
|---|---|---|---|---|
| `gpt-5.5` | 12/16 | 6/8 | 6/8 | 12–15 giây |
| `claude-sonnet-4.6` | 9/15 (một lời gọi rớt mạng) | 7/7 | 3/8 | 18–36 giây |
| `deepseek-v4.1-flash` | 11/16 | 8/8 | 0/8 | 17–21 giây |
| `claude-haiku-4.5` | 11/16 | 5/8 | 2/8 | 7–10 giây |
| `claude-opus-5-5` | 13/16 | 4/8 | 2/8 | 28 giây |
| `gemini-2.5-flash-lite` | 13/16 | 3/8 | 0/8 | 3 giây |

Cách đọc: khi code đưa thứ tự, mọi model giữ gần nguyên; khi bỏ thứ tự, phần lớn model không tự dựng lại được nó. Ở cụm ba giả thuyết, năm trên sáu model đặt "thiếu tín hiệu" trên "chuỗi bước gãy" (hạng 1 của code và của đội). Prompt có luật 7 ("fact không quyết được thì giữ thứ tự đã cho"), nên một phần kết quả là model làm đúng lời dặn. Kết luận: trên dữ liệu hiện có, hạng do model đưa ra phần lớn là hạng của code; chưa có bằng chứng model nào tự xếp hạng tốt hơn bảng luật.

**Bộ lỗi cấy (C1), đường bản 3.** Dựng lại bộ log bằng `log_defects` mặc định (ra đúng `bench-c6da75e9ff36`, `bench-cfcb0ba66776`), phát lại file `--record` của lần chạy Nemotron 12/11 qua mã hiện tại, chấm bằng DA-31. Kết quả khớp bản 12/11 ở mọi số đếm (recall 30/30, báo nhầm bản sạch 1/40, T4 3/4); khác biệt chỉ ở id báo cáo, ngày và nhãn revision. Đường ống vòng mới chưa chạy được bộ này vì chưa có vai `adjudicate`.

Chưa đo trong lượt này: C2 (gói khỏe), D2 (kỹ sư duyệt), chi phí thật (chỉ có số cổng báo), model cục bộ M1.

### 9.5 Hai luật kiểm sửa sau lần đo 24/11/2026

Chấm lại sáu lần chạy của mục 9.4 bằng `--from verify` (không gọi lại model):

| Sửa | Vì sao | Kết quả khi chấm lại |
|---|---|---|
| Luật mới `system_first`: cụm đang bị chặn tiêu ngân sách dữ liệu thì hạng 1 phải là giả thuyết lỗi hệ thống | Mục 9.4: ba model đẩy giả thuyết dữ liệu lên đầu và được nhận | 4 câu bị loại (Haiku 2, GPT-5.5 1, Gemini 1), cụm về thứ tự của code |
| Nhận `"check": {"id": null, …}` như "không chọn phép kiểm" | Prompt bảo "dùng null", model viết `id: null` và trượt schema | Opus 5.5 từ 5 nhận, 3 sửa lên 8 nhận; GPT-5.5 từ 3 nhận, 4 loại lên 7 nhận, 1 loại |

Điểm ca không đổi ở mọi model (A1 22/24, bắt buộc 7/9, D1 bằng 0). Prompt đổi nên đây là một phiên bản agent mới; chưa chạy lại với model thật sau khi sửa.

### 9.6 Outcome thật và ngưỡng vùng phủ theo spec, 25/11/2026

Gói `stage1-60k-out` (`pack_d1b5f9462d0d6b36`, 258 file): gói 9.3 cộng `outcomes.jsonl` của bốn run (60 lượt mỗi run), xuất bằng `flywheel_psi0.tray.export_outcomes` từ lô eval gốc. Số lượt thành công trong outcome là 10, 5, 7, 6 trên 60 cho `C_70`, `C_ALL`, `B_70`, `B_ALL`, khớp `Score`.

**Ngưỡng vùng phủ.** Công cụ `coverage_distance` bản 2 ra τ_cov 0,868 và 1,920 cho `C_70`; phân tích tay của đội ra 1,143 và 1,524. Cả hai cặp số tái hiện được từ cùng dữ liệu; hai chỗ khác nhau giải thích toàn bộ độ lệch:

| Chỗ khác | Bản 2 | Đội, và spec 6.8 |
|---|---|---|
| Tập train | Chỉ điều kiện train cùng mức với lượt hỏng (362 ở mức 1, 63 ở mức 2) | Cả 425 điều kiện; mức chỉ quyết định thành phần nào vào vector |
| Ánh sáng ở mức 2 | Có trong vector | Không; để cho phép kiểm thị giác của bước 7 |

Hai định nghĩa cho kết luận khác nhau ở 11 trên 50 lượt hỏng của `C_70`. Bản 3 của công cụ theo định nghĩa của spec và của đội (`pool_levels: true` trong config task; đặt `false` để có cách cũ) và ra đúng 1,14288 và 1,52408. Ánh sáng bị bỏ khỏi mức 2 là theo cách của đội, dù spec 4.2 có ghi ánh sáng trong vector điều kiện. **[Đã chốt]** Hiếu, 25/11/2026: bỏ.

**Kết quả, ca `tray-c70-step4`.**

| Số đo | Gói 9.3, công cụ bản 2 | Gói có outcome, công cụ bản 3 |
|---|---|---|
| A1 điểm chốt tới được | 22/24; bắt buộc 7/9 | **24/24; bắt buộc 9/9** |
| A2, A3, A5 | 4/4; 0; 2/2 | 4/4; 0; 2/2 |
| Cụm bị chặn tiêu ngân sách dữ liệu | 53 trên 64 | 40 trên 64 |
| Giả thuyết theo luật | `label_signal_missing` 53, `weak_skill` 32, `out_of_domain` 17, `coverage_gap` 15, `scorer_latch_too_strict` 14 | `weak_skill` 40, `label_signal_missing` 32, `coverage_gap` 18, `scorer_latch_too_strict` 14, `near_miss_placement` 10, `out_of_domain` 6 |
| Hạng 1 của cụm `place`/`L-PLACE-POSE` mức 1 của `C_70` (c1) | "thiếu tín hiệu", bị chặn | `weak_skill`, can thiệp `teleop_correction` |
| D1 với `claude-opus-5-5` | 0 | 0; 8 trên 8 câu được nhận ngay, bước `judge` 120 giây |
| Thời gian sàn code, đỉnh RAM | 95 giây, 371 MB | 113 giây, 397 MB |

Cách đọc:

- Hai điểm bắt buộc trượt từ 22/11 nay tới được: outcome mang tư thế khay cuối và đích nên nhãn `L-PLACE-POSE` chấm được.
- c1 ra `weak_skill`, khớp chẩn đoán "bước đặt yếu" của đội. Với công cụ bản 2 cùng gói, c1 ra `coverage_gap` và đề xuất sinh dữ liệu sim: sai ngưỡng dẫn thẳng tới sai can thiệp.
- D1 vẫn bằng 0, nhưng lý do đã đổi. Trước đây model không có gì để xếp; nay tín hiệu đủ nên bảng luật tự quyết, 5 trên 8 cụm lớn nhất chỉ còn một giả thuyết. Vai `rank` không còn chỗ để thêm giá trị trên ca này.
- Ca này vẫn là tập phát triển, một ca. 24/24 không nói gì về vòng chưa thấy.

### 9.7 Vai `adjudicate` và bộ lỗi cấy trên đường ống vòng, 25/11/2026

Đường ống vòng có thêm bước `adjudicate` giữa `hypothesize` và `judge`. Nó chạy phần xét ứng viên của bản 3 (`analyze.py`, `agent.review_subject`, không đổi) cho từng nguồn trong gói, nhưng gọi model qua cổng model, nên rào lớp dữ liệu, ngân sách và ghi/phát lại đều áp dụng. Thư mục lần chạy có thêm `reports.jsonl`, `dropped.jsonl`, `estimates.jsonl` đúng dạng của `fw agentqa run`, nên bộ chấm DA-31 đọc được mà không sửa.

| Loại mục của gói | Nguồn của bản 3 |
|---|---|
| `metrics` (kèm `action_layout`, `probe_p3`, `probe_p4`, `probe_p4_parent` cùng job) | train |
| `rtc_log` | inference |
| `qa_reports`, `dataset_report`, `episodes`, `replay_reports` | dataset |
| `probe_p1`, `probe_p3` | stage 1, stage 3 |

Với `--no-model`, bước này dùng lớp code: giữ mọi ứng viên của bộ phát hiện, không thêm gì. Vai `rank` chưa đọc các báo cáo này.

**Bộ log cấy (C1), lớp code, đường mới.** Dựng lại hai bản bằng `log_defects` mặc định, khai gói bằng `python -m flywheel.eval.agentqa.round.declare`, chạy `fw agentqa round --no-model`, chấm bằng DA-31 (mã không sửa). Mã đã gồm DA-44.

| Đại lượng | Đường bản 3, lớp code (mốc 6/11) | Đường ống vòng, lớp code |
|---|---|---|
| Recall T1–T8, R1, R2 | 3/3 mỗi loại (30/30) | 3/3 mỗi loại (30/30) |
| Precision theo mã | 3/3 mỗi mã | 3/3 mỗi mã |
| Báo nhầm trên bản sạch | 0/40 | 0/40 |
| Thời gian, RAM một bản | | khoảng 1,6 giây, 150 MB |

Đường bản 3 chạy lại hôm nay trên cùng hai bản cho đúng các phát hiện đó.

**Bộ log cấy với model, đường mới.** **[Đã chốt]** Hiếu, 25/11/2026: hai bản log cấy (log tổng hợp do `log_defects` sinh, không có dữ liệu robot, site hay người thật) nhận bản ghi `Source` lớp `public`. Model `claude-opus-5-5` qua cổng ckey.vn (không xác minh được model đứng sau tên), prompt của bản 3 không đổi.

| Đại lượng | Bản 3, Nemotron cục bộ (12/11) | Đường ống vòng, `claude-opus-5-5` (25/11) |
|---|---|---|
| Recall T1–T8, R1, R2 | 30/30 | 30/30 |
| Precision theo mã | 3/3 ở 9 mã; T4 3/4 | 3/3 ở cả 10 mã |
| Báo nhầm trên bản sạch | 1/40 (cận trên) | 0/40 (cận trên) |
| Model thêm so với code (`agent_adds`) | 0; hai mục tự thêm đều là T4 sai | 0; không tự thêm mục nào |
| Ứng viên của code bị model bỏ | 6 (lý do tự mâu thuẫn) | 0 |
| Báo cáo `ok` / `broken` | 80 / 0 | 80 / 0 |
| Lời gọi model, gửi lại | 96 câu | 89 lời gọi, 0 gửi lại |
| Thời gian | 1714 giây và 757 giây | 850 giây và 271 giây |

Hai lỗi của bản 3 với Nemotron (T4 tự thêm sai, lý do bỏ tự mâu thuẫn) không xuất hiện. Nhưng model cũng không bắt thêm lỗi cấy nào ngoài điều code đã bắt: trên bộ này lớp code đã đạt 30/30, nên phần model thêm chỉ có thể bằng 0 hoặc âm. Điều kiện qua của design 19/11 mục 11.1 (recall không giảm, hai T4 sai biến mất, không lần bỏ tự mâu thuẫn) đạt với model này; chưa đo với model cục bộ.

Giới hạn đã biết:

- `AgentModel.temperature` của hợp đồng phải là số. Model thuê không gửi temperature, nên báo cáo ghi 1,0 (mặc định của server), là **giả định**. Ghi đúng cần hợp đồng cho phép để trống.
- Gói log cấy dùng `task_id: tray`, nên mỗi lần chạy mang trạng thái `degraded` vì thiếu điểm số và trace; bước `adjudicate` tự nó `ok`.
- Ở chế độ có model, mỗi nguồn không có ứng viên vẫn tốn một lời gọi (như bản 3): 40 lời gọi mỗi bản log, so với trần 60 của config.
