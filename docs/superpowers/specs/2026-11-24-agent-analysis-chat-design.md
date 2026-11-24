# Design: agent chat phân tích một vòng Failure → Data

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 24/11/2026 | 0.2 | Hiếu duyệt theo đề xuất: Q1–Q7 của mục 11 thành **[Đã chốt]**; chưa dựng vội. Thêm mục 13 (yêu cầu thêm của Hiếu cùng ngày: model tốt nhất, đa phương thức và đa model, câu hỏi về quyền terminal), **[Đề xuất]**, chờ duyệt Q8–Q10 | Hiếu (soạn với Claude) |
| 24/11/2026 | 0.1 | Bản đầu, **[Đề xuất]**, chờ Hiếu duyệt trước khi viết mã | Hiếu (soạn với Claude) |

_Trạng thái: **đã duyệt 24/11/2026** (bản 0.2: Q1–Q7 của mục 11 chốt theo đề xuất). **Chưa dựng**: Hiếu yêu cầu chưa làm vội. Tài liệu này thay mục 18 và quyết định Q8 của [kiến trúc 20/11/2026](2026-11-20-agent-qaqc-architecture-design.md) ("DA-43 không dựng chat thứ hai") và mở vòng điều tra của mục 20 ở đó; các mục khác của hai tài liệu Agent QA/QC giữ nguyên. Mục 13 là đề xuất mới, chờ duyệt._

## 0. Đọc nhanh

1. Hiếu nêu ngày 24/11/2026: Agent QA/QC phải là một **agent chat phân tích**. Kỹ sư trò chuyện với nó để phân tích một vòng theo đúng thuật toán Failure → Data của [spec](../../spec-v10-failure-to-data.md) mục 6, như cách một người làm việc với một trợ lý lập trình.
2. Hiện nay hệ là đường ống chạy một lần, không hội thoại. Model được gọi một lần mỗi cụm để xếp hạng giả thuyết code đã đề xuất.
3. Số đo 24/11/2026 ([agent-qa.md](../../g0/agent-qa.md) mục 9.4): với vai đó, sáu model đều không thêm được gì so với code. Vấn đề nằm ở **vai của model**, không ở model nào.
4. Đề xuất: giữ đường ống làm nền (nó tính sẵn chẩn đoán của cả vòng), dựng thêm **một vòng hội thoại** phía trên. Trong vòng đó model tự chọn công cụ phân tích, đọc kết quả, hỏi tiếp và trả lời kỹ sư.
5. Ba luật cứng không đổi: model không viết số; mọi câu trích fact do code tính; thứ tự "hệ thống trước, dữ liệu sau" do code giữ.
6. Agent đề xuất, kỹ sư quyết định (spec 6.14). Agent không khởi động job, không sửa dữ liệu, không đọc holdout.

## 1. Vì sao

| Điều đo được | Nguồn | Ý nghĩa |
|---|---|---|
| Sàn code tới 22 trên 24 điểm chốt của ca `tray-c70-step4`, không khẳng định sai | agent-qa 9.3 | Phần tính toán và bảng luật đã dùng được |
| Sáu model ra đúng điểm của sàn code, phần "model thêm" bằng 0 | agent-qa 9.4 | Xếp lại thứ tự code đã xếp không tạo giá trị |
| Bỏ gợi ý thứ tự thì hạng 1 của model khớp code từ 3 tới 12 trên 16 cụm | agent-qa 9.4 | Model không tự dựng lại được chẩn đoán từ một lần đọc fact |
| Phân tích tay của đội đi qua nhiều lượt: xem bảng, nghi một nguyên nhân, chạy thêm một phép tính, loại trừ, rồi mới kết luận | [tray.md](../../he/tray.md) mục 20 | Việc cần hỗ trợ là **quá trình** đó, không chỉ kết luận |

Một báo cáo tĩnh trả lời câu hỏi người viết luật đã nghĩ tới. Kỹ sư thật luôn có câu hỏi tiếp theo: "nới dung sai thêm thì sao", "run kia có cùng lỗi không", "cụm này gồm những lượt nào". Hiện mỗi câu như vậy cần một người viết mã.

## 2. Người dùng và kịch bản

**Người dùng**: kỹ sư AI của đội, sau khi một vòng eval xong. Họ biết thuật toán, không muốn viết script cho từng câu hỏi.

**Kịch bản chính**: một buổi phân tích đi theo các bước 3–11 của spec 6.1. Agent dẫn theo thứ tự đó nhưng kỹ sư được hỏi bất kỳ lúc nào.

| Bước của spec | Kỹ sư hỏi (ví dụ) | Agent làm | Trả lời có gì |
|---|---|---|---|
| 3. Gom cụm | "Vòng này hỏng ở đâu?" | Đọc bảng cụm đã tính | Cụm theo bước, kiểu lỗi, mức, cỡ; cụm lớn nhất |
| 4. Kiểm hệ thống | "Có phải lỗi controller không?" | Gọi `trace_stats` cho lượt hỏng và lượt thành công | Sai số bám hai phần thân so với τ; kết luận hoặc "chưa đủ tín hiệu", nêu tín hiệu thiếu |
| 4. Kiểm hệ thống | "Chuỗi bước gãy ở `approach_a` là lỗi policy hay bộ chấm?" | Gọi `latch_consistency`, xem lượt thành công mà chuỗi vẫn gãy | Số lượt; giả thuyết ngưỡng bộ chấm; phép kiểm rẻ nhất để tách |
| 5–7 | "Planner chuẩn có làm được điều kiện này không?" | Tra artifact; nếu vòng không có thì nói rõ thiếu gì | "Không xét được", kèm artifact cần thu |
| 8. Vùng phủ | "Cụm c1 trong miền train không? Cách tập train bao xa?" | Gọi `coverage_distance` cho cụm | d, τ_cov, trong miền hay ngoài miền |
| 9. Chẩn đoán | "Vậy cụm c1 là gì?" | Ghép kết quả 4–8 theo bảng quyết định của spec 6.9 | Chẩn đoán, fact ủng hộ, fact phản bác, điều đã loại trừ |
| 10. Đề xuất | "Nên làm gì, tốn bao nhiêu?" | Tra can thiệp được phép của chẩn đoán, bảng giá, lịch sử tỉ lệ sửa | Loại can thiệp; chi phí nếu có giá, "chưa có giá" nếu không |
| 11. Chọn | "Với ngân sách này chọn gì?" | Xếp theo spec 6.11 trên các đề xuất đã có | Danh sách; cụm bị chặn vì còn lỗi hệ thống |
| Ngoài luồng | "So `C_70` với `B_70`", "nới dung sai lên mức kế thì sao" | Gọi `paired_compare`, `relaxed_sweep` | Bảng số của code, câu đọc của model |
| Ghi đè | "Tôi cho cụm c3 là lỗi controller, vì …" | Ghi quyết định và lý do | `AgentReview` loại `override` (spec 6.14) |

**Một lượt trông như thế nào** (phác; `{F…}` là id fact, code điền giá trị khi hiển thị):

```text
Kỹ sư : Cụm place / L-PLACE-POSE của C_70 có phải thiếu vùng phủ không?
Agent : [gọi coverage_distance(run=C_70, cluster=c1)]
        [gọi signal_presence(label=L-PLACE-POSE)]
        Chưa kết luận được là thiếu vùng phủ. Hai lý do:
        1. Nhãn này chưa chấm được vì thiếu tư thế khay cuối và đích {F312}.
           Đây là lỗi hệ thống, phải gỡ trước (spec 6.9).
        2. Trung bình khoảng cách của cụm là {F708}, dưới ngưỡng {F672};
           mọi lượt trong miền train {F682}.
        Bước tiếp rẻ nhất: xuất outcome có tư thế khay rồi chạy lại phép này.
        Tôi chưa đề xuất thu dữ liệu cho cụm này.
```

## 3. Mục tiêu, không làm, phản mục tiêu

**Mục tiêu**

- Kỹ sư đi hết một buổi phân tích một vòng mà không viết script.
- Mọi kết luận lần ngược được về fact, và fact lần ngược được về file của vòng.
- Cùng một bộ câu hỏi chạy lại được và chấm được.

**Không làm (bản đầu)**

- Không khởi động eval, train, thu dữ liệu. Agent chỉ viết đề xuất; job vẫn đi qua RunPlan và Hiếu.
- Không nhớ giữa các phiên. Mỗi phiên bắt đầu từ thư mục của một vòng.
- Không nhìn hình (vai `look` của DA-43 vẫn là việc riêng).
- Không thay chat của Console. Chat đó tiếp tục trả lời câu hỏi về kho, job, catalog.

**Phản mục tiêu** (có thì coi là hỏng, dù chạy được)

- Agent nêu một con số không do code tính.
- Agent đề xuất tiêu ngân sách dữ liệu cho cụm còn giả thuyết lỗi hệ thống.
- Agent tự chạy lệnh shell, mã Python tự viết, hoặc đọc đường dẫn do model đưa.
- Dữ liệu `internal` hay `restricted` tới model thuê.
- Agent trả lời về holdout, đáp án niêm phong, hoặc kết quả thi lại của `C70_R1` (quyết định 16/11/2026).

## 4. Các cách dựng đã cân nhắc

| | A. Mở rộng chat của Console | B. Agent tự do có shell | C. Vòng hội thoại trên lớp công cụ **[Đề xuất]** |
|---|---|---|---|
| Cách làm | Thêm tool đọc file chẩn đoán vào chat hiện có (kiến trúc 20/11 mục 18) | Cho model chạy lệnh và mã Python trên thư mục vòng, như một trợ lý lập trình | Model gọi 13 công cụ phân tích đã có, tham số do code kiểm; fact mới vào sổ fact của phiên |
| Trả lời câu hỏi mới | Không: chỉ tra điều đường ống đã tính | Có, mọi câu | Có, trong phạm vi công cụ và tham số của config task |
| Số do ai tính | Code | Mã do model viết: không kiểm được | Code |
| Chấm được không | Được, nhưng ít điều để chấm | Khó: hai lần hỏi ra hai đoạn mã | Được: ghi và phát lại lời gọi |
| Rào dữ liệu | Có sẵn | Phải dựng sandbox, vẫn rủi ro đọc `vault/` | Có sẵn: cổng model và danh sách từ chối của `inputs.py` |
| Việc phải làm | Ít | Nhiều, phần lớn là an toàn | Vừa: vòng lặp, sơ đồ công cụ cho model, luật kiểm câu trả lời |

Chọn C. A không đạt mục tiêu vì không tính được điều mới. B đạt mục tiêu nhưng phá luật "model không viết số" và rào holdout, là hai điều dự án không đổi. C dùng lại gần hết phần đã dựng và đã đo.

## 5. Thiết kế

### 5.1 Hai tầng

```text
Thư mục vòng (đã có)                    Phiên chat (mới)
fw agentqa round --no-model      ->     fw agentqa chat --run <thư mục vòng>
  facts.jsonl, hypotheses.jsonl           đọc mọi file bên trái (chỉ đọc)
  tables/, assembly.json                  gọi thêm công cụ, ghi fact mới vào phiên
  tính một lần, lặp lại được              mỗi lượt: model <-> công cụ, có trần
```

Đường ống vẫn chạy trước, không model, khoảng 95 giây trên gói thật (đo). Nó cho agent một điểm xuất phát giống nhau ở mọi phiên: cụm, giả thuyết của bảng luật, cụm nào bị chặn. Phiên chat không sửa thư mục vòng.

### 5.2 Công cụ model được gọi

Ba nhóm. Mọi tham số là id hoặc giá trị trong danh sách đóng (tên run, id cụm, tên bước, mức); không có tham số nào là đường dẫn hay đoạn mã.

| Nhóm | Công cụ | Ghi chú |
|---|---|---|
| Tra (không tính) | `clusters`, `cluster(id)`, `hypotheses(cluster)`, `fact(id)`, `facts_search(text)`, `rollouts(cluster)`, `table(name)`, `not_judged()` | Đọc file của vòng và của phiên |
| Tính | 13 công cụ của `tools/registry.py`: `step_pass_table`, `failure_clusters`, `latch_consistency`, `signal_presence`, `relaxed_sweep`, `trace_stats`, `train_window`, `coverage_distance`, `paired_compare`, `lineage`, `cost_lookup`, `history_lookup`, `task_lookup` | Tham số đi qua `check_params` đã có. Kết quả thành fact mới có id, nguồn gốc `code` |
| Đề xuất (chỉ ghi vào phiên) | `propose_check(cluster, check_id)`, `propose_intervention(cluster, kind)`, `record_override(cluster, diagnosis, reason)` | Code kiểm theo bảng phép kiểm và `INTERVENTIONS_OF_DIAGNOSIS`; không khởi động gì |

Thêm công cụ mới vẫn theo cách cũ: đăng ký tường minh trong mã, không tự phát hiện.

### 5.3 Vòng lặp của một lượt

1. Code dựng tin cho model: prompt hệ thống, tóm tắt vòng (cụm, giả thuyết hạng 1, cụm bị chặn), các lượt gần đây, câu hỏi.
2. Model hoặc gọi công cụ, hoặc trả lời.
3. Code chạy công cụ, trả kết quả dạng fact (id, tên, giá trị, đơn vị), rồi quay lại bước 2.
4. Câu trả lời đi qua luật kiểm (5.4). Trượt thì gửi lại một lần kèm lỗi. Trượt nữa thì kỹ sư nhận bảng fact của code và dòng "model không viết được câu trả lời hợp lệ".

Mọi trần do code giữ, không vòng nào dừng vì "model thấy đủ" (kiến trúc 20/11 mục 20). Giá trị đầu là giả định, chỉnh sau lần đo đầu:

| Trần | Giá trị đầu (giả định) |
|---|---|
| Vòng gọi công cụ mỗi lượt | 6 |
| Lời gọi công cụ mỗi lượt | 12 |
| Lời gọi model mỗi phiên | 60 |
| Tiền mỗi phiên với model thuê | trần trong `chat.yaml`, cùng cơ chế ngân sách của cổng model |

### 5.4 Luật của câu trả lời

Dùng lại thư viện `reply_rules.py` và thêm ba luật riêng của chat.

| Luật | Nội dung | Có sẵn |
|---|---|---|
| Số | Không số trần trong câu; số chỉ xuất hiện qua `{F…}` mà code điền khi hiển thị | Có |
| Trích | Mỗi câu khẳng định có ít nhất một fact; id phải thuộc tập đã đưa cho model trong phiên | Có |
| So sánh | Câu so sánh phải trích một fact so sánh do code làm | Có |
| Nguồn gốc | Fact `vision` chỉ ủng hộ, không đứng một mình | Có |
| Hệ thống trước | Không đặt giả thuyết dữ liệu trên giả thuyết hệ thống ở cụm bị chặn | Có (`system_first`, DA-43 5.7) |
| Can thiệp | Loại can thiệp phải thuộc tập của chẩn đoán; cụm bị chặn không nhận can thiệp tiêu ngân sách dữ liệu | Mới, dùng bảng đã có |
| Không biết | Khi công cụ trả `not_judged`, câu trả lời phải nói thiếu gì; không suy đoán | Mới |
| Phạm vi | Câu hỏi về holdout, đáp án, `C70_R1`, hoặc yêu cầu chạy job: từ chối bằng câu cố định của code, không gọi model | Mới |

Câu trả lời có hai phần: chữ của model (đã qua luật) và bảng fact của code hiển thị ngay dưới. Kỹ sư luôn thấy số gốc.

### 5.5 Theo đúng thuật toán

- Prompt hệ thống mang bảng quyết định của spec 6.9 và thứ tự bước; bảng luật giả thuyết hiện có là điểm xuất phát, không phải trần.
- Agent được nêu giả thuyết **ngoài** bảng luật, với điều kiện: có fact ủng hộ, thuộc danh sách `Diagnosis` của hợp đồng, và ghi rõ nguồn là model. Đây là chỗ model thêm được giá trị mà vai `rank` không cho phép.
- Trạng thái của buổi phân tích (cụm nào đã qua bước nào) do code giữ từ các lời gọi công cụ, và hiện cho kỹ sư dưới dạng danh sách "đã kiểm / chưa kiểm".
- Quyết định cuối là của kỹ sư. `record_override` ghi lý do; tỉ lệ ghi đè là số được báo (spec 6.14).

### 5.6 Bộ nhớ

| Loại | Ở đâu | Sống bao lâu |
|---|---|---|
| Sổ fact của phiên | `facts.jsonl` của phiên, nối tiếp id của vòng | Cả phiên; không bao giờ bị cắt |
| Hội thoại | `turns.jsonl` | Cả phiên; khi dài, lượt cũ được thay bằng tóm tắt do **code** dựng: câu hỏi, id fact đã trích, đề xuất đã ghi |
| Giữa các phiên | Không có ở bản đầu | Mở lại phiên cũ bằng `--resume` |

### 5.7 Dữ liệu và model

- Mọi lời gọi model đi qua cổng model đã có, thêm vai `chat` trong `routing.yaml`. Gói không phải `public` thì chỉ model tự host; rào không nới.
- Vai này cần model gọi công cụ ổn định. Design 19/11 mục 3 ghi Nemotron 4 GB không ổn định ở việc này. Bản đầu đo trên gói `public` với model thuê qua cổng đang có; model cục bộ đo sau, khi Hiếu cho dùng `rtx3060`.
- Chọn model bằng số của mục 7, không chọn trước.

### 5.8 Bề mặt

| Bề mặt | Lệnh | Khi nào |
|---|---|---|
| Dòng lệnh, hội thoại | `fw agentqa chat --run <thư mục vòng> [--session <thư mục>] [--resume]` | Bản đầu |
| Dòng lệnh, một câu | `fw agentqa chat --run … --ask "…"` | Bản đầu; dùng cho bộ chấm |
| Giao thức dòng JSON trên stdin/stdout | `--jsonl` | Bản đầu; là chỗ cắm cho Console |
| Trang chat của Console | Console chạy lệnh trên như một tiến trình con, không import làn Đánh giá | Story Console sau |

## 6. Thư mục một phiên

```text
<session>/
  session.json      vòng nào, hash agent, model, trần, trạng thái
  turns.jsonl       mỗi lượt: câu hỏi, câu trả lời, phán quyết luật kiểm
  tool_calls.jsonl  mỗi lời gọi công cụ: tên, tham số, id fact trả về, thời gian
  model_calls.jsonl như của đường ống: ghi và phát lại được
  facts.jsonl       fact mới của phiên
  proposals.jsonl   phép kiểm, can thiệp, ghi đè đã ghi
```

Mọi file chỉ nối thêm. `--replay` chạy lại phiên từ `model_calls.jsonl` mà không gọi model, và phải cho file ra giống từng byte.

## 7. Đánh giá

Bộ ca lịch sử hiện chấm kết luận của một báo cáo. Chat cần thêm một bộ **kịch bản hội thoại**: mỗi kịch bản là một danh sách câu hỏi cố định trên một vòng, kèm điểm chốt có cấu trúc cho từng câu.

| # | Số đo | Cách tính |
|---|---|---|
| H1 | Điểm chốt tới được | Câu trả lời trích đúng fact và nêu đúng giá trị có cấu trúc (chẩn đoán, phép kiểm, can thiệp) của điểm chốt. Dùng lại đáp án niêm phong của `casebench/` |
| H2 | Khẳng định sai | Câu trả lời nêu điều đáp án ghi là đã bác |
| H3 | Rò số, câu không trích | Bộ kiểm chạy lại độc lập trên `turns.jsonl`; phải bằng 0 |
| H4 | Lời gọi công cụ hợp lệ | Số lời gọi bị `check_params` từ chối trên tổng số |
| H5 | Từ chối đúng | Bộ câu bẫy: holdout, `C70_R1`, "thu thêm dữ liệu cho cụm bị chặn", "chạy train giúp tôi" |
| H6 | Biết nói không biết | Câu hỏi mà vòng thiếu artifact: trả lời phải nêu thiếu gì |
| H7 | Model thêm | Điểm chốt tới được mà sàn code của đường ống không tới |
| H8 | Thời gian và chi phí mỗi lượt | Từ `model_calls.jsonl` và `tool_calls.jsonl` |
| H9 | Ổn định | Chạy kịch bản hai lần: số câu đổi kết luận |
| H10 | Kỹ sư duyệt | `agree` và `override` trên các câu trả lời của một buổi thật |

**Cổng qua [Đề xuất, giả định]**: H3 bằng 0 và H5 đủ (cứng); H2 bằng 0; H7 lớn hơn 0 trên tập phát triển, tức chat phải làm được điều báo cáo tĩnh không làm được. Kịch bản của tập kiểm do người không viết prompt soạn.

## 8. Cấu trúc mã

- Mã mới ở làn Đánh giá: `packages/flywheel-eval/src/flywheel/eval/agentqa/chat/` (`session.py`, `loop.py`, `tools_read.py`, `tools_propose.py`, `answer_rules.py`, `bench.py`). Dùng lại `tools/`, `round/gateway.py`, `round/reply_rules.py`, `round/records.py`.
- Chỉ import nhân và `flywheel.eval`; không import làn khác, adapter hay Console.
- Config: `configs/eval/agentqa/chat.yaml` (trần, vai, công cụ được mời), `prompts/chat.md`.
- Cần lớp gọi model có tool calling. `AnthropicModel` và `OpenAICompatibleModel` hiện chỉ có `chat(system, user)`; thêm một phương thức cho hội thoại nhiều tin và công cụ, giữ phương thức cũ.
- Hợp đồng: `proposals.jsonl` dùng `AgentReview` và `InterventionKind` đã có. Nếu cần trường mới thì dừng và đề xuất PR hợp đồng.

## 9. Thứ tự làm [Đề xuất]

Mỗi bước để lại một thứ dùng được. Chưa ước lượng thời gian; ước lượng sau khi Hiếu chốt mục 11.

| Bước | Việc | Dùng được một mình? |
|---|---|---|
| 1 | Lớp gọi model có tool calling qua cổng; ghi và phát lại | Chưa |
| 2 | Công cụ tra, vòng lặp có trần, `--ask` một câu | Có: hỏi đáp trên điều đã tính |
| 3 | Mở 13 công cụ tính cho model; sổ fact của phiên | Có: trả lời câu hỏi mới |
| 4 | Luật của câu trả lời, bộ câu bẫy | Có: đủ an toàn để người khác dùng |
| 5 | Hội thoại nhiều lượt, `--resume`, tóm tắt do code dựng | Có: một buổi phân tích đầy đủ |
| 6 | Đề xuất và ghi đè | Có |
| 7 | Bộ kịch bản hội thoại, đo H1–H9 với ít nhất hai model | Số để quyết |
| 8 | Giao thức `--jsonl`; trang Console (story riêng) | |

## 10. Rủi ro

| Rủi ro | Giảm bằng |
|---|---|
| Model gọi công cụ lan man, tốn tiền | Trần do code giữ; H8 báo mỗi lượt |
| Model nói trôi chảy nhưng sai | Luật số và trích; bảng fact luôn hiện cạnh câu trả lời; H2 |
| Hội thoại không lặp lại được nên không chấm được | Ghi và phát lại; kịch bản câu hỏi cố định |
| Chỉ có một vòng thật để thử | Thêm ca theo nhiệm vụ 6.1 của DA-43 trước bước 7 |
| Model cục bộ không gọi công cụ được, dữ liệu `internal` không có model | Đo sớm ở bước 7; phương án lùi là sàn code cộng công cụ tra |
| Trùng việc với chat của Console | Ranh giới: Console trả lời về kho và job; chat này trả lời về chẩn đoán một vòng |
| Ngưỡng vùng phủ của công cụ chưa khớp số của đội (agent-qa 9.3) | Đối chiếu trước bước 3; tới lúc đó câu trả lời về vùng phủ ghi "chưa kiểm chứng" |

## 11. Quyết định cần Hiếu

**[Đã chốt 24/11/2026, Hiếu]** "Duyệt theo đề xuất": Q1–Q7 chốt theo cột đề xuất (bản 0.2). Q8–Q10 ở mục 13.4 còn chờ.

| # | Quyết định | Đề xuất |
|---|---|---|
| Q1 | Cách dựng | C (mục 4) |
| Q2 | Thay mục 18 và Q8 của kiến trúc 20/11; mở vòng lặp của mục 20 | Có |
| Q3 | Story | Story mới, mã do Hiếu cấp; không gộp vào DA-43 (PR 210 đã quá ngưỡng cỡ). Các việc còn mở của DA-43 (vai `adjudicate`, `look`, thêm ca) giữ ở DA-43 |
| Q4 | Bề mặt bản đầu | Dòng lệnh; Console sau |
| Q5 | Model thuê cho gói `public` trong lúc phát triển | Có, qua cổng đang dùng, trần tiền mỗi phiên |
| Q6 | Agent được nêu giả thuyết ngoài bảng luật (mục 5.5) | Có, ghi nguồn là model |
| Q7 | Ai soạn kịch bản của tập kiểm | Một người không viết prompt |

## 12. Để lại cho người dựng

- Dạng chính xác của sơ đồ công cụ gửi model (tên trường, mô tả).
- Cách cắt kết quả công cụ lớn (bảng nhiều hàng) trước khi đưa cho model.
- Cách hiển thị trên dòng lệnh.
- Giá trị các trần sau lần đo đầu.

## 13. Yêu cầu thêm của Hiếu, 24/11/2026 (bản 0.2)

**[Đề xuất]**, chờ duyệt. Ba điều Hiếu nêu sau khi duyệt bản 0.1: dùng model tốt nhất; hệ có ảnh, video và nhiều loại dữ liệu nên phải dùng nhiều model để làm tốt nhất; và câu hỏi "nếu cho agent quyền chạy terminal thì nó có tự chạy phân tích và đưa bảng số liệu được như một trợ lý lập trình không".

### 13.1 Model tốt nhất

Mục 5.7 viết "chọn model bằng số". Bản 0.2 đổi mặc định: vai `chat` dùng **model mạnh nhất có được cho lớp dữ liệu đó**; số đo của mục 7 dùng để kiểm, không để chọn model rẻ.

| Lớp dữ liệu | Model của vai `chat` | Ghi chú |
|---|---|---|
| `public` (dữ liệu demo trong sim) | Model thuê mạnh nhất qua cổng model; hiện là `claude-opus-5-5` | Cổng đang dùng là bên bán lại, không xác minh được model đứng sau tên (agent-qa 9.4). Muốn chắc thì dùng khóa trực tiếp của nhà cung cấp |
| `internal`, `restricted` | Model tự host mạnh nhất vừa máy | Chưa đo model nào gọi công cụ ổn định trên `rtx3060`; rào dữ liệu không nới |

Trần tiền mỗi phiên vẫn giữ: nó chặn vòng lặp lỗi, không để tiết kiệm.

### 13.2 Đa phương thức và đa model

Một vòng có nhiều loại dữ liệu. Nguyên tắc: **code biến mỗi loại thành fact hoặc thành thứ model đọc được**, rồi model phù hợp nhất đọc nó. Không model nào tự mở file.

| Loại dữ liệu | Có ở đâu trong một vòng | Code làm gì | Model đọc |
|---|---|---|---|
| Điểm số, log train, sổ chi phí, catalog | `Score`, log, ledger | 13 công cụ ra fact | Vai `chat` |
| Trace theo thời gian (khớp, lệnh, độ trễ) | trace của rollout | Công cụ tính thống kê; vẽ biểu đồ cho kỹ sư xem | Vai `chat` đọc fact; biểu đồ dành cho người |
| Ảnh | Khung hình camera đầu của rollout | `frames_at` cắt khung tại thời điểm code chọn (bước hỏng đầu tiên, trước và sau) | Vai `look`: model có thị giác |
| Video | Video rollout, video egocentric | Cắt thành chuỗi khung quanh sự kiện; cả đoạn video chỉ dùng khi có model đọc video và phép đo cho thấy nó hơn chuỗi khung | Vai `look` |
| Egocentric của người | Dataset egocentric | Phải qua che danh tính trước mọi bước (bất biến của repo), trừ mẫu EgoDex công bố | Như ảnh và video |

Ba vai model, mỗi vai định tuyến riêng theo lớp dữ liệu qua cổng model:

| Vai | Việc | Vì sao tách |
|---|---|---|
| `chat` | Lập luận, chọn công cụ, viết câu trả lời | Cần model lập luận và gọi công cụ tốt nhất |
| `look` | Trả lời câu hỏi đóng về một ảnh hoặc chuỗi khung ("khay có nghiêng không") | Model thị giác tốt nhất chưa chắc là model `chat`; kết quả là fact nguồn gốc `vision`, chỉ ủng hộ (luật đã có) |
| `second` | Một model **khác họ** đọc lại kết luận quan trọng (chẩn đoán cuối, đề xuất tiêu ngân sách) cùng các fact đã trích, trả "đồng ý" hoặc "không, vì fact nào" | Bắt lỗi lập luận mà luật kiểm không bắt được. Hai model bất đồng thì kỹ sư thấy cả hai |

Lợi ích của vai `second` và của việc đọc cả đoạn video là **giả định**, chưa đo. Mỗi thứ chỉ giữ lại nếu số của mục 7 (H1, H2) tốt hơn khi có nó.

### 13.3 Câu hỏi về quyền terminal

Trả lời: **được.** Với quyền chạy mã, một model mạnh tự viết script, chạy, đọc kết quả và dựng bảng số liệu được, đúng như cách bản thiết kế này và các bảng số của agent-qa 9.4 được làm ra. Điều kiện là kết quả đó phải kiểm lại được, vì mã do model viết có thể sai mà trông vẫn hợp lý.

Bản 0.1 xếp việc này vào phản mục tiêu (cách B của mục 4). Đề xuất của bản 0.2 là mở nó dưới dạng **một công cụ có hộp cát**, không phải một terminal tự do:

| Điều | Quy định |
|---|---|
| Công cụ | `run_analysis(code)`: Python với pandas, numpy; không shell |
| Thấy gì | Bản chỉ đọc của thư mục vòng và thư mục phiên. Không `vault/`, không `answers/`, không `docs/`, không mạng, không biến môi trường |
| Trần | Thời gian, bộ nhớ và số lần chạy mỗi lượt do code giữ |
| Kết quả | Bảng và số thành fact có nguồn gốc mới `model_code`; đoạn mã và đầu ra lưu trong phiên, kỹ sư mở xem được |
| Hiển thị | Mọi số `model_code` mang nhãn "tính bằng mã của model, chưa qua công cụ đã kiểm" |
| Giới hạn dùng | Fact `model_code` không được là chỗ dựa duy nhất của một đề xuất tiêu ngân sách dữ liệu; phải có fact `code` đi kèm, như luật của `vision` |
| Vòng đời | Đoạn mã được dùng lại nhiều lần thì chuyển thành công cụ đăng ký có test; đó là cách lớp công cụ lớn lên |

Như vậy luật "model không viết số" đọc lại là: **model không gõ số; số đến từ mã chạy thật, và người đọc luôn biết mã đó là của ai.** Phần thay đổi so với bản 0.1: phản mục tiêu "agent tự chạy mã Python tự viết" được thay bằng "agent chạy mã ngoài hộp cát".

Việc này làm sau bước 4 của mục 9 (luật của câu trả lời), không trước: hộp cát và nhãn nguồn gốc phải có trước khi model được viết mã.

### 13.4 Quyết định cần Hiếu

| # | Quyết định | Đề xuất |
|---|---|---|
| Q8 | Vai `chat` mặc định dùng model mạnh nhất của lớp dữ liệu (13.1) | Có |
| Q9 | Ba vai `chat`, `look`, `second`; vai `second` và đọc cả đoạn video chỉ giữ nếu số đo tốt hơn (13.2) | Có |
| Q10 | Mở `run_analysis` có hộp cát và nguồn gốc `model_code` (13.3) | Có, sau bước 4 |

## Nguồn

- [Spec v10.6](../../spec-v10-failure-to-data.md) mục 6.1, 6.9, 6.11, 6.14
- [Design 19/11/2026](2026-11-19-agent-qaqc-system-design.md) mục 3, 6, 11; [kiến trúc 20/11/2026](2026-11-20-agent-qaqc-architecture-design.md) mục 8, 18–21
- [agent-qa.md](../../g0/agent-qa.md) mục 9.3–9.5 (số đo 23–24/11/2026)
- [Thí nghiệm khay](../../he/tray.md) mục 20
