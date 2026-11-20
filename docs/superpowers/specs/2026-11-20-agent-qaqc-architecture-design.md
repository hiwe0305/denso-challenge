# Kiến trúc: đường ống Agent QA/QC từ dữ liệu vào tới báo cáo ra (DA-43)

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 20/11/2026 | 0.3 | Hiếu duyệt ("Duyệt theo đề xuất"): Q1–Q9 của mục 16 thành **[Đã chốt]** | Hiếu (soạn với Claude) |
| 20/11/2026 | 0.2 | Thêm phần B (mục 18–26): hai bề mặt (báo cáo vòng và chat của Console), tool calling, vòng lặp, bộ nhớ, gói kiến thức (skill), điểm mở rộng (plugin), schema bản ghi, prompt và config. Thêm Q8, Q9 | Hiếu (soạn với Claude) |
| 20/11/2026 | 0.1 | Bản đầu, chờ Hiếu duyệt. Thay mục 5.1, 5.4, 12 và phần chọn model của mục 8 của [design 19/11/2026](2026-11-19-agent-qaqc-system-design.md) | Hiếu (soạn với Claude) |

_Trạng thái: **đã duyệt 20/11/2026** (bản 0.3: Q1–Q9 của mục 16 chốt theo đề xuất). Các nhãn **[Đề xuất]** trong thân bài có quyết định tương ứng ở mục 16 nay đọc là đã chốt; số ghi ước lượng vẫn là ước lượng tới khi đo. Tài liệu này trả lời yêu cầu ngày 20/11/2026 của Hiếu: thiết kế kiến trúc agent rõ ràng, sạch từ dữ liệu, xử lý tới đầu ra, theo chuẩn production; và có model nào rẻ mà tốt hơn không. Design 19/11/2026 vẫn giữ phần "làm gì và vì sao" (công cụ ở mục 4, luật trích số ở mục 6, hợp đồng ở mục 7, đánh giá ở mục 11). Tài liệu này quyết "dựng thế nào". Chỗ hai tài liệu khác nhau thì tài liệu này thắng. Số chưa đo ghi là ước lượng._

## 0. Đọc nhanh

1. Hệ này **không phải một agent tự hành**, và không nên là. Nó là một **đường ống cố định 8 bước**; model chỉ có mặt ở đúng một bước, làm ba việc hẹp. Đây là dạng chuẩn cho bài toán mà các bước biết trước và mọi con số phải kiểm lại được.
2. Mỗi bước đọc file của bước trước và ghi file của mình vào một **thư mục lần chạy**. Bước nào hỏng thì chạy lại từ bước đó. Bảy trong tám bước là code tất định.
3. Dữ liệu vào qua một cửa duy nhất: **gói vòng** có bảng kê (file nào, loại gì, sha256, lớp dữ liệu, nối với nhau thế nào). Agent không đoán loại file theo tên như hiện nay.
4. Model gọi qua một **cổng model** duy nhất: chọn model theo lớp dữ liệu, giữ ngân sách, ghi lại mọi lời gọi, phát lại được. Đổi nhà cung cấp là đổi config.
5. Câu trả lời của model không tới báo cáo trực tiếp. Một bước **kiểm** bằng code duyệt từng mục; mục trượt thì báo cáo dùng kết quả của code cho mục đó và ghi rõ. Báo cáo luôn ra, kể cả khi model hỏng.
6. Hệ có **hai bề mặt**: báo cáo vòng (DA-43, đường ống này) và hỏi đáp (chat của Console, đã có). Chat không tính lại chẩn đoán; nó đọc file mà đường ống ghi ra. Tool calling, vòng lặp, bộ nhớ, skill và plugin áp vào hệ này thế nào: phần B, mục 18–23.
7. Về model: `claude-haiku-5-5` (0,10 và 0,50 USD mỗi triệu token) đã ở nhóm rẻ nhất thị trường. "Rẻ mà tốt hơn" chỉ trả lời được bằng số đo trên bộ ca lịch sử; kiến trúc này làm cho việc đo ba, bốn model chỉ là đổi config (mục 12).

## 1. Vì sao cách hiện tại chưa ổn

Đối chiếu với mã ở `packages/flywheel-eval/src/flywheel/eval/agentqa/` và design 19/11/2026:

| # | Vấn đề | Chỗ thấy | Hậu quả |
|---|---|---|---|
| 1 | Không có ranh giới đầu vào. Loại file được đoán theo tên (`scores.jsonl`, `metrics.jsonl`) | `inputs.py`, hàm `kind_of` | File đặt tên khác thì bị bỏ qua lặng lẽ. Không biết `scores.jsonl` nào thuộc run nào, checkpoint nào. Design 19/11 gọi "gói vòng" nhưng chưa định nghĩa |
| 2 | Một hàm làm mọi việc trong bộ nhớ | `run.py`, hàm `run` | `reports.jsonl` chỉ ghi khi mọi chủ thể xong. Không chạy lại riêng một bước. Không xem được kết quả giữa chừng |
| 3 | Lời gọi model gắn vào một kiểu endpoint | `endpoint.py`: chỉ `/chat/completions`, `json_object`, không ép schema | Đổi model là sửa mã. Không có ngân sách, không có chỗ duy nhất để chặn theo lớp dữ liệu |
| 4 | Dựng prompt, gọi model và kiểm câu trả lời nằm chung | `agent.py`, `_parse_reply` dài khoảng 150 dòng | Khó test từng luật; thêm luật là sửa hàm lớn |
| 5 | Design 19/11 mô tả "5 chuyên viên và một bộ tổng hợp" như 6 agent | Design 19/11 mục 5 | Nghe như multi-agent, nhưng thực chất là cùng một việc trên các tập fact khác nhau. Tên gọi làm thiết kế có vẻ phức tạp hơn nó cần |
| 6 | Model hỏng thì cả phần tổng hợp là `broken` | Design 19/11 mục 6, luật 8 | Kỹ sư mất báo cáo vì một câu trả lời sai, dù code đã có đủ bảng và giả thuyết |
| 7 | Không có hồ sơ lần chạy | Chỉ có file `--record` và một dòng sổ chi phí | Không trả lời được "báo cáo này do phiên bản nào, prompt nào, tốn bao nhiêu, bước nào chậm" |

## 2. Ba khái niệm cần nắm

Phần này dành cho người chưa thiết kế hệ dùng model ngôn ngữ.

**Đường ống, agent, multi-agent.**

| Dạng | Ai quyết bước tiếp theo | Hợp khi | Giá phải trả |
|---|---|---|---|
| Đường ống (workflow) | Code. Các bước cố định; model được gọi ở vài bước, mỗi lần một việc hẹp | Biết trước các bước; cần lặp lại được và kiểm được | Không tự xử lý được ca ngoài kịch bản |
| Agent | Model. Nó nhận công cụ, tự chọn gọi gì, lặp tới khi thấy đủ | Việc mở, không biết trước cần bao nhiêu bước | Hai lần chạy đi hai đường; khó chấm; cần model mạnh |
| Multi-agent | Nhiều model, mỗi cái một vai, trao đổi với nhau | Việc chia được thành phần độc lập mà mỗi phần cần ngữ cảnh riêng hay quyền riêng | Tốn nhiều token nhất; lỗi lan qua tin nhắn giữa các agent; khó gỡ nhất |

Quy tắc chọn: dùng dạng **đơn giản nhất** làm được việc. Chỉ lên agent khi không liệt kê trước được các bước.

**Model chỉ làm việc mà code không làm được.** Code tính số, so ngưỡng, nối bảng, áp luật. Model đọc một tập bằng chứng có mâu thuẫn rồi nói cái nào đáng tin hơn và vì sao, bằng lời. Ở dự án này, sáu kết luận tay của tray.md đều là phép tính cộng một bước suy luận ngắn (design 19/11 mục 1.2), nên phần của model nhỏ.

**Không tin câu trả lời của model.** Mọi câu trả lời đi qua một bước kiểm bằng code trước khi tới người đọc. Và mọi thay đổi (prompt, model, luật) phải có điểm trên bộ chấm trước khi dùng. Hai điều này là khác biệt chính giữa bản thử và bản production.

## 3. Các cách dựng đã cân nhắc

| | P1. Đường ống theo bước, file có kiểu giữa các bước | P2. Một agent với vòng gọi công cụ | P3. Multi-agent có điều phối |
|---|---|---|---|
| Cách chạy | 8 bước cố định; model ở một bước, ba vai hẹp | Model nhận 14 công cụ, tự gọi, tự viết chẩn đoán | Một agent điều phối giao việc cho các agent chuyên nguồn, rồi gộp |
| Luật "model không viết số" | Giữ được: model chỉ trả id và câu có chỗ chèn `{F#}` | Phải kiểm cả tham số mỗi lời gọi công cụ và mọi câu trung gian | Như P2, nhân với số agent |
| Chạy trên model 4 GB cục bộ (bắt buộc cho dữ liệu DENSO) | Được; bản 3 đã chạy kiểu này | Không ổn: Nemotron 4 GB gọi công cụ không ổn định (design 19/11 mục 3) | Không |
| Lặp lại, chấm điểm | Tốt: 7 bước tất định, bước model phát lại được | Kém | Kém nhất |
| Chi phí mỗi vòng | Thấp, biết trước (khoảng 25 lời gọi, ước lượng) | Cao hơn, không biết trước | Cao nhất |
| Tới được nguyên nhân chưa lường trước | Chỉ trong phạm vi công cụ và bảng luật | Có thể | Có thể |

**[Đề xuất] P1.** Lý do: dữ liệu DENSO buộc hệ chạy đủ trên model nhỏ cục bộ; ban giám khảo cần kết quả kiểm lại được; và phần giá trị đã đo nằm ở code. Điểm yếu của P1 (ca chưa lường trước) được bù bằng cách thêm công cụ và luật sau mỗi vòng, có bộ ca lịch sử chống tụt. Cửa "model xin thêm công cụ" của design 19/11 mục 5.4 **rút khỏi DA-43**: nó là một bước nhỏ về phía P2, chưa có số nào cho thấy cần, và có thể thêm sau như một vai mới mà không đổi kiến trúc.

Đây cũng là cách A đã chốt ngày 19/11/2026 (Q1), nay dựng cho đúng. Không đảo quyết định nào đã chốt, trừ việc rút cửa xin thêm công cụ.

## 4. Nguyên tắc

| # | Nguyên tắc | Nghĩa là |
|---|---|---|
| N1 | Một cửa vào | Mọi dữ liệu vào qua gói vòng có bảng kê. Không bước nào tự đi tìm file |
| N2 | Đóng khi nghi ngờ | Thiếu lớp dữ liệu, sai sha256, sai schema: từ chối và nói rõ, không đoán |
| N3 | Bước thuần, file có kiểu | Mỗi bước là một hàm: file vào, file ra, có schema. Không trạng thái ẩn giữa các bước |
| N4 | Code trước, model sau | Báo cáo đầy đủ dựng được khi không có model. Model chỉ cải thiện thứ đã có |
| N5 | Model sau một cổng | Một chỗ duy nhất gọi model: chọn theo lớp dữ liệu, ngân sách, ghi lại |
| N6 | Kiểm trước khi tin | Không mục nào của model tới báo cáo khi chưa qua bước kiểm |
| N7 | Xuống cấp, không sập | Một phần hỏng thì phần đó dùng kết quả của code và báo cáo ghi rõ; không mất cả báo cáo |
| N8 | Mọi lần chạy để lại hồ sơ | Phiên bản, hash, thời gian, token, tiền, trạng thái từng bước |
| N9 | Đổi là phải chấm | Prompt, luật, model, công cụ đổi thì thành phiên bản mới, phải có điểm trước khi dùng |
| N10 | Chỉ đọc | Agent không ghi gì ngoài thư mục lần chạy và sổ chi phí; không chạy job, không ký quyết định |

## 5. Đường ống

```text
round.yaml (kỹ sư khai: run nào, job nào, release nào, lớp dữ liệu)
   │
B0 ĐÓNG GÓI    pack.json: từng file, loại, schema, sha256, lớp dữ liệu, quan hệ nối
   │
B1 NHẬN        admission.json: file nào nhận, file nào từ chối và vì sao; lớp dữ liệu của cả gói
   │
B2 ĐO          facts.jsonl, tables/, tool_calls.jsonl        (lớp công cụ, kế hoạch cố định)
   │
B3 GIẢ THUYẾT  hypotheses.jsonl: ứng viên, fact ủng hộ và phản bác, phép kiểm, hạng của code
   │                                              ── tới đây đã đủ một báo cáo (sàn code)
B4 XÉT         model_calls.jsonl        (bước duy nhất gọi model; gồm một lần gửi lại khi trượt kiểm)
   │
B5 KIỂM        verdicts.jsonl: mục nào qua, mục nào trượt và vì luật nào
   │
B6 LẮP         assembly.json, reports.jsonl (và round_diagnosis.json khi K2 đã merge); code gắn chi phí
   │
B7 TRÌNH BÀY   index.html (từ assembly.json và tables/)  ──►  kỹ sư duyệt (AgentReview)  ──►  lịch sử, ca mới
```

| Bước | Vào | Ra | Tất định | Khi hỏng |
|---|---|---|---|---|
| B0 Đóng gói | `round.yaml` do kỹ sư viết, thư mục artifact | `pack.json` | Có | Dừng, mã thoát khác 0 |
| B1 Nhận | `pack.json` | `admission.json` | Có | Gói không nhận được: dừng. File lẻ bị từ chối: ghi lại, đi tiếp |
| B2 Đo | Artifact đã nhận, config task | `facts.jsonl`, `tables/`, `tool_calls.jsonl` | Có | Công cụ thiếu đầu vào ra fact "không xét được". Công cụ lỗi mã: dừng |
| B3 Giả thuyết | `facts.jsonl`, bảng luật | `hypotheses.jsonl` | Có | Dừng |
| B4 Xét | `hypotheses.jsonl`, `facts.jsonl` | `model_calls.jsonl` | Không; phát lại được | Lời gọi lỗi được ghi lại; B5 cho mục đó trượt |
| B5 Kiểm | `model_calls.jsonl`, `facts.jsonl`, `hypotheses.jsonl` | `verdicts.jsonl` | Có | Mục trượt dùng sàn code |
| B6 Lắp | Mọi file trên, sổ chi phí | `assembly.json`, `reports.jsonl`, `round_diagnosis.json` (sau K2) | Có | Dừng |
| B7 Trình bày | `assembly.json`, `tables/`, `tool_calls.jsonl` | `index.html` | Có | Dừng; chạy lại riêng bước này |

## 6. Từng bước

### B0 Đóng gói

Kỹ sư viết một file `round.yaml` ngắn: task, các run eval, checkpoint và job train của từng run, release và dataset của job đó, đường dẫn tới artifact, và lớp dữ liệu. Lệnh `fw agentqa pack` đọc file khai, kiểm từng file tồn tại, tính sha256, và ghi `pack.json`.

- Quan hệ nối (lượt eval → checkpoint → job train → release → dataset) được **khai**, không suy từ tên thư mục. Công cụ `lineage` của design 19/11 chỉ còn đọc bảng kê.
- Artifact chưa ở dạng hợp đồng thì phải xuất trước bằng lệnh của adapter, ví dụ `export_scores` (nhiệm vụ 1.2, đã xong). Bước đóng gói không đọc dạng riêng của adapter.
- Gói là bất biến: đổi một file là gói mới, sha256 mới.
- Trong DA-43, `round.yaml` chỉ do người viết. Để RunPlan (làn Vòng) tự sinh file này là dữ liệu qua ranh giới làn, cần hợp đồng; việc đó để story sau.

### B1 Nhận

Bước duy nhất quyết dữ liệu nào được đi tiếp.

- Mỗi file được nạp bằng đúng model hợp đồng ghi trong bảng kê. Sai schema thì file bị từ chối kèm lý do.
- Đường dẫn chứa `vault`, `answers`, `docs` bị từ chối, kể cả qua link (luật hiện có của `inputs.py`, thêm `docs`).
- **Lớp dữ liệu của gói** là lớp cao nhất trong các file. File không khai lớp thì coi là `restricted`, đúng mặc định của hợp đồng `Episode`. Khi file có bản ghi mang `data_class` (`Episode`, `Source`), bước này đối chiếu với lớp đã khai và lấy lớp cao hơn.
- **Lời khai `public` một mình không đủ để đi hosted.** Nhiều artifact (ví dụ `Score`) không mang `data_class`. Một gói chỉ được coi là `public` khi mọi file khai `public` **và** chuỗi nối của nó dẫn tới ít nhất một bản ghi nguồn có `data_class: public` nằm trong gói, và không bản ghi nào nói khác. Thiếu bản ghi nguồn thì gói là "không rõ lớp", tức chỉ model cục bộ. Giữ đúng luật "không rõ lớp thì không phải `public`" của design 19/11 mục 8.
- `admission.json` ghi: file nhận, file từ chối, loại artifact còn thiếu so với kế hoạch công cụ, lớp dữ liệu của gói, và từ đó **đường model được phép** (cục bộ, hay cả hosted).

### B2 Đo

Lớp công cụ của design 19/11 mục 4, chạy theo một **kế hoạch cố định** trong config task: danh sách công cụ và tham số cho từng loại artifact. Sáu công cụ đã xong (nhiệm vụ 2.1–2.3).

- Mỗi fact có id, tên, giá trị, đơn vị, file nguồn và **nguồn gốc** (`code`, `vision`, `history`).
- `tool_calls.jsonl`: mỗi lời gọi một dòng (công cụ, tham số, sha256 đầu vào, id các fact sinh ra, thời gian).
- Im lặng không bao giờ là "sạch": thiếu đầu vào ra một fact "không xét được" có lý do.

### B3 Giả thuyết

Bảng luật trong config ánh xạ dấu hiệu sang chẩn đoán của spec 6.9 (design 19/11 mục 5.3). Bước này ra, cho mỗi cụm lỗi:

- các giả thuyết ứng viên, mỗi cái có fact ủng hộ, fact phản bác, tập can thiệp được phép;
- các phép kiểm tách được từng cặp giả thuyết, kèm chi phí từ sổ, đã sắp theo chi phí;
- một **hạng của code**: theo thứ tự bảng luật (hệ thống và bộ chấm trước, dữ liệu sau, spec 6.4), rồi theo số fact ủng hộ trừ số fact phản bác. Hạng này là sàn: báo cáo dùng nó khi model không có hoặc trượt;
- luật chặn: cụm còn giả thuyết hệ thống chưa bị loại thì không có đề xuất tiêu ngân sách dữ liệu.

Sau B3, chạy thẳng B6 và B7 là có báo cáo không model. Đây là mốc giao hàng đầu tiên.

### B4 Xét

Bước duy nhất gọi model. Có ba **vai**; mỗi vai là một prompt, một schema câu trả lời và một phạm vi fact. "Chuyên viên dataset, train, eval, runtime" của design 19/11 là **cùng một vai** chạy trên bốn phạm vi fact, không phải bốn agent.

| Vai | Đơn vị một lời gọi | Model thấy gì | Model trả gì | Số lời gọi mỗi vòng (ước lượng) |
|---|---|---|---|---|
| `adjudicate` (xét ứng viên) | Một nguồn, tối đa 10 ứng viên | Ứng viên và fact của nguồn đó | Với mỗi ứng viên: giữ hay bỏ, id fact trích, một câu giải thích | 6–10 |
| `rank` (xếp hạng) | Một cụm lỗi | Giả thuyết ứng viên của cụm, phát hiện đã qua kiểm, bảng nối, danh sách phép kiểm đã sắp | Thứ tự id giả thuyết; id một phép kiểm; id một can thiệp; mỗi lựa chọn một câu có trích fact | Tối đa 8 (cụm lớn nhất trước) |
| `look` (nhìn hình) | Một lượt, tối đa 6 khung hình | Khung hình và câu hỏi đóng của config task | `có`, `không` hoặc `không rõ` cho từng câu | Tối đa 6; làm cuối, rút được |

**Thứ tự trong bước.** Vai `adjudicate` chạy trước; vai `rank` chạy sau và chỉ thấy phát hiện đã qua kiểm. Sau mỗi câu trả lời, B4 gọi **thư viện luật kiểm** (cùng các hàm thuần mà B5 dùng) để quyết có gửi lại không. Mỗi mục được gửi lại nhiều nhất một lần, kèm danh sách lỗi; lời gửi lại là một lời gọi model bình thường: tính vào ngân sách và có dòng riêng trong `model_calls.jsonl`. Như vậy mọi lời gọi model nằm trong B4, còn luật kiểm là code thuần dùng ở cả hai bước.

Ba điều chung cho mọi vai:

- **Model chỉ chọn trong tập đóng và viết câu giải thích.** Nó trả id (giả thuyết, phép kiểm, can thiệp, fact), không trả số. Số trong câu là chỗ chèn `{F#}` do code điền, như bản 3.
- **Câu trả lời theo schema.** Nhà cung cấp nào ép được schema thì ép; dù ép hay không, B5 vẫn kiểm lại bằng model pydantic.
- **Chuỗi lấy từ artifact là dữ liệu, không phải lệnh.** Nhãn lỗi, tên file, dòng log vào prompt như giá trị của fact, bị cắt độ dài. Model không có công cụ nào gây tác dụng phụ, nên một chuỗi độc trong log chỉ có thể làm hỏng một câu giải thích, và câu đó còn phải qua B5.

### B5 Kiểm

Các luật 1–8 của design 19/11 mục 6 và ba sửa của mục 5.2, tách thành từng hàm kiểm nhỏ, mỗi hàm một test. B5 là lượt kiểm **chính thức**: nó đọc các câu trả lời cuối cùng trong `model_calls.jsonl`, không gọi model, và ghi phán quyết. Vì vậy `--from B5` kiểm lại một lần chạy cũ bằng luật mới mà không tốn lời gọi nào. Mỗi mục của model nhận một phán quyết:

| Phán quyết | Nghĩa | Báo cáo dùng gì |
|---|---|---|
| `accepted` | Qua mọi luật | Mục của model, ghi nguồn là model |
| `repaired` | Câu trả lời đầu trượt, câu gửi lại (đã có trong `model_calls.jsonl`) qua | Mục đã sửa |
| `rejected` | Trượt cả hai lần, hoặc lời gọi lỗi | **Sàn code** của mục đó ở báo cáo vòng: hạng của B3 và câu mẫu của luật giả thuyết, ghi rõ "của code, model chưa xét" và lý do |

Mục `rejected` không được tính công cho model ở bất kỳ bảng chấm nào.

**`AgentReport` không đổi nghĩa.** Sàn code chỉ áp ở báo cáo vòng. Với `AgentReport` của vai `adjudicate`, luật bản 3 giữ nguyên: lô trượt hai lần không góp phát hiện nào và báo cáo đó là `broken`. Ứng viên của lô đó vẫn hiện trong báo cáo vòng như "ứng viên của code, model chưa xét", nhưng không thành `AgentFinding`. Nhờ vậy số đo trên bộ lỗi cấy (DA-31) so được với bản 3.

Chỗ đổi so với design 19/11 luật 8 **[Đề xuất]**: trước đây lời gọi trượt hai lần làm cả phần tổng hợp `broken`. Nay ở báo cáo vòng chỉ mục đó về sàn code, lần chạy mang trạng thái `degraded`. Lý do: kỹ sư vẫn cần bảng và giả thuyết của code; và vì mục trượt được ghi rõ là của code, luật "câu trả lời hỏng không được tính công" vẫn giữ nguyên.

### B6 Lắp

Code dựng đầu ra từ các mục đã có phán quyết:

- gắn `Cost` (ước tính, trỏ về dòng sổ) và `ExpectedGain` cho can thiệp; đánh dấu phép kiểm rẻ nhất;
- ghi `assembly.json`, bản lắp đầy đủ của riêng làn (giả thuyết đã xếp hạng, phán quyết, nguồn của từng mục, phần không xét được), và `reports.jsonl` gồm các `AgentReport` không đổi hợp đồng, để bộ chấm DA-31 đọc như cũ;
- **sau khi PR hợp đồng K2 merge** (nhiệm vụ 5.5), xuất thêm `round_diagnosis.json` theo `RoundDiagnosis` từ `assembly.json`. Trước đó không ghi file này và không có trường tạm nào trong mã làn; mốc 4.4 dùng `assembly.json`;
- ghi hai dòng sổ chi phí (ước tính trước khi chạy, thực đo sau khi chạy), như bất biến của repo. Mỗi lần gọi lệnh, kể cả `--from`, `--replay` và `--no-model`, ghi một cặp dòng mới của riêng nó.

### B7 Trình bày

Trang HTML tĩnh theo design 19/11 mục 7.3. Phần kết luận (ba dòng đầu, chuỗi nguyên nhân, phần không xét được) dựng từ `assembly.json`; bảng của công cụ, ứng viên bị bỏ và lời gọi công cụ đọc thẳng từ các file khác trong thư mục lần chạy. Bước này không tính gì và không gọi model. Console sau này chỉ đọc `round_diagnosis.json`, nên hợp đồng K2 không phải mang bảng thô. Mỗi dòng trên trang ghi nó do code hay do model; mục về sàn code có nhãn riêng.

**Vòng phản hồi.** Kỹ sư duyệt bằng `AgentReview` (đồng ý hoặc sửa, kèm lý do). Kết quả thật của can thiệp nằm ở `EvidenceCard.result`. Hai thứ này là đầu vào của công cụ `history_lookup` ở vòng sau, và mỗi lần kỹ sư sửa là một ứng viên cho ca mới của bộ ca lịch sử. Đây là cách agent tốt lên mà không cần huấn luyện lại model.

## 7. Thư mục một lần chạy

```text
<out>/
  run.json              hồ sơ: phiên bản agent, hash, trạng thái và thời gian từng bước, token, tiền
  pack.json             B0
  admission.json        B1
  facts.jsonl           B2
  tool_calls.jsonl      B2
  tables/               B2
  hypotheses.jsonl      B3
  model_calls.jsonl     B4   (không commit khi gói không phải public)
  verdicts.jsonl        B5
  assembly.json         B6
  round_diagnosis.json  B6   (chỉ sau khi K2 merge)
  reports.jsonl         B6
  index.html, figures/  B7
```

- `fw agentqa round --pack <pack.json> --out <thư mục mới>` chạy cả đường ống. `--from <bước>` chạy lại từ một bước trên thư mục đã có, dùng lại file của các bước trước sau khi kiểm sha256.
- `--no-model` dừng ở sàn code (B3 rồi B6, B7). `--replay` phát lại `model_calls.jsonl` thay cho lời gọi thật.
- File giữa các bước là của riêng làn Đánh giá (model pydantic trong `round/records.py`). Chỉ thứ đi qua ranh giới làn mới cần hợp đồng (mục 14).

## 8. Cổng model

Một module duy nhất được phép gọi model. Mọi vai gọi `gateway.call(vai, yêu cầu)`.

| Việc | Cách làm |
|---|---|
| Chọn model | Config có các **hồ sơ model** (tên, nhà cung cấp, id model, giới hạn) và một bảng `vai × lớp dữ liệu → hồ sơ`. Ví dụ: `rank` với gói `public` dùng hồ sơ hosted; với gói `internal` dùng hồ sơ cục bộ |
| Chặn theo lớp dữ liệu | Cổng nhận lớp dữ liệu của gói từ `admission.json`. Hồ sơ hosted với gói không phải `public` thì ném lỗi trước khi mở kết nối. Đây là lần kiểm thứ hai sau B1; hai lần độc lập để một lỗi config không đủ làm rò dữ liệu |
| Nhà cung cấp | Mỗi nhà cung cấp là một lớp nhỏ thực hiện cùng giao diện `ChatModel`. Cục bộ: `OpenAIEndpoint` đang có, **không sửa**; nó vẫn từ chối mọi host ngoài mạng đội (`check_local_url`), và lệnh bản 3 `fw agentqa run` vẫn chỉ chạy cục bộ. Hosted: hai lớp mới trong `round/providers/`, một cho giao thức kiểu OpenAI (OpenRouter), một cho Anthropic (mục 12). Lớp hosted chỉ cổng model dựng được, và chỉ sau khi đã kiểm lớp dữ liệu |
| Ngân sách | Trần cho mỗi lần chạy: số lời gọi, token vào, tiền (hosted). Chạm trần thì dừng gọi; các mục còn lại về sàn code, trạng thái `degraded` |
| Lỗi mạng, quá tải | Thử lại tối đa 2 lần, giãn cách tăng dần; có hạn thời gian cho mỗi lời gọi |
| Ghi và phát lại | Mỗi lời gọi một dòng trong `model_calls.jsonl`: vai, hash của yêu cầu, hồ sơ, id và revision model, token vào và ra, thời gian, tiền, câu trả lời. Chạy lại với cùng yêu cầu thì đọc từ file, không gọi lại |
| Song song | Cục bộ: tuần tự (một GPU). Hosted: vài lời gọi cùng lúc, số lượng trong config |

Tính lặp lại: model cục bộ chạy nhiệt độ 0. Một số model hosted không nhận tham số nhiệt độ (ví dụ Claude Opus 5.5 trả lỗi khi gửi), nên với hosted, thứ bảo đảm lặp lại là file ghi, không phải nhiệt độ.

Khóa API đọc từ biến môi trường có tên ghi trong hồ sơ; không nằm trong repo hay file ghi.

**Sáu điều chặn cứng của design 19/11 mục 8 giữ nguyên hiệu lực**, tài liệu này chỉ nói chúng nằm ở đâu: (1) khối config `hosted` riêng, tắt mặc định; (2) lớp dữ liệu kiểm trên mọi bản ghi, không rõ thì từ chối (B1); (3) gói không phải `public` mà bật hosted thì dừng trước lời gọi đầu, mã thoát khác 0, có test (B1 và cổng); (4) adapter log robot thật luôn đóng dấu `internal`; (5) lớp dữ liệu và host của model ghi vào `RoundDiagnosis`, `run.json` và sổ chi phí; (6) fact loại `history` chỉ kéo từ vòng cùng lớp hoặc lớp thấp hơn.

## 9. Trạng thái và lỗi

| Trạng thái lần chạy | Khi nào | Kỹ sư nhận được |
|---|---|---|
| `ok` | Mọi bước xong, mọi mục của model `accepted` hoặc `repaired` | Báo cáo đầy đủ |
| `degraded` | Có mục về sàn code, chạm trần ngân sách, không có model, hoặc có file bị từ chối ở B1 | Báo cáo đầy đủ về số và giả thuyết; đầu trang ghi phần nào là của code và vì sao |
| `broken` | B0–B3 hoặc B6 hỏng | Không có báo cáo; `run.json` ghi bước và lỗi; mã thoát khác 0 |

Trạng thái `broken` của từng `AgentReport` giữ nghĩa cũ để bộ chấm DA-31 không đổi.

## 10. Quan sát và chi phí

- `run.json` trả lời bốn câu: phiên bản nào (mục 11), trên gói nào (sha256), mỗi bước mất bao lâu và ra bao nhiêu dòng, model tốn bao nhiêu lời gọi, token và tiền.
- Sổ chi phí của repo nhận hai dòng mỗi lần chạy, như hiện nay.
- Không thêm dịch vụ nào (03 mục 2.4): mọi thứ là file trong thư mục lần chạy.

## 11. Phiên bản và điều kiện dùng

- **Phiên bản agent** là số trong `agent.yaml` cộng một hash tính trên: prompt của ba vai, bảng luật giả thuyết, danh mục phép kiểm, kế hoạch công cụ, config task, và bảng hồ sơ model. Hash ghi trong `run.json` và trên đầu báo cáo.
- Bộ chấm (bộ lỗi cấy và bộ ca lịch sử, design 19/11 mục 11) ghi điểm kèm hash. Báo cáo của một hash chưa có điểm mang nhãn "phiên bản chưa chấm" ở đầu trang. Nhãn này không chặn lần chạy; nó ngăn việc dùng nhầm một bản chưa đo.
- Mọi bảng điểm tách ba cột như design 19/11: sàn code, agent, phần model thêm.

## 12. Model: giá và cách chọn

**Giá.** Chỉ giá của Anthropic là đã kiểm (bảng giá ngày 3/11/2026). Giá của nhà cung cấp khác lấy từ các trang tổng hợp ngày 20/11/2026; các trang này **không khớp nhau**, nên ghi là chưa kiểm.

| Model | Vào / ra (USD mỗi triệu token) | Đọc ảnh | Nguồn giá |
|---|---|---|---|
| `claude-haiku-5-5` | 0,10 / 0,50 | Có | Đã kiểm |
| `claude-sonnet-5-5` | 2 / 10 | Có | Đã kiểm |
| `claude-opus-5-5` | 4 / 20 | Có | Đã kiểm |
| GPT-5 nano | 0,05 / 0,40 | Chưa kiểm | Chưa kiểm |
| Gemini 2.5 Flash-Lite | 0,10 / 0,40 | Chưa kiểm | Chưa kiểm |
| Qwen Turbo | 0,05 / 0,20 | Chưa kiểm | Chưa kiểm |
| DeepSeek V4.1 Flash | 0,30 / 1,20 | Chưa kiểm | Chưa kiểm |
| Nemotron 4 GB cục bộ | 0 (điện và máy dùng chung) | Không | Đang dùng |

**Chi phí một báo cáo vòng** (ước lượng: khoảng 25 lời gọi, 250 nghìn token vào, 60 nghìn token ra; chưa đo, và token suy nghĩ của model tính vào phần ra):

| Model cho cả ba vai | Mỗi vòng |
|---|---|
| `claude-haiku-5-5` | Khoảng 0,06 USD |
| `claude-sonnet-5-5` | Khoảng 1,1 USD |
| `claude-opus-5-5` | Khoảng 2,2 USD |

**Nhận định.**

- Ở mức vài xu mỗi vòng, chênh lệch giá giữa các model rẻ không còn là yếu tố quyết định. Thứ quyết định là model có **xếp hạng đúng** và **trả đúng schema** không. Không bảng giá nào trả lời được câu đó cho bài toán này.
- Vì model chỉ làm ba việc hẹp trên fact đã tính sẵn, một model rẻ có nhiều khả năng là đủ. Đây là giả định; kiến trúc này được dựng để kiểm nó rẻ nhất có thể.
- Model rẻ của nhà cung cấp khác thử được với ít mã: OpenRouter nói cùng giao thức `/chat/completions` với endpoint cục bộ, nên lớp hosted kiểu OpenAI dùng lại phần dựng yêu cầu; mỗi model sau đó chỉ là một hồ sơ trong config.

**[Đề xuất] cách chọn.** Chạy bộ ca lịch sử (chỉ ca `public`) với cùng prompt, cùng công cụ, trên: sàn code (không model), Nemotron cục bộ, `claude-haiku-5-5`, `claude-opus-5-5`, và nếu Hiếu muốn, một hoặc hai model rẻ qua OpenRouter. Chọn **model rẻ nhất có điểm không kém model tốt nhất** trên số điểm chốt tới được và không có khẳng định sai ở hạng 1. Ước lượng chi phí cho cả lượt so sánh này: dưới 30 USD. Bắt đầu với `claude-haiku-5-5` làm hồ sơ hosted mặc định; chỉ lên `claude-opus-5-5` cho vai `rank` nếu số đo cho thấy có lợi.

Dữ liệu `internal` và `restricted` luôn dùng hồ sơ cục bộ, bất kể kết quả so sánh.

**Lớp Anthropic [Đề xuất, cần Hiếu quyết].** Gọi Anthropic đúng cách là qua SDK chính thức (`anthropic`), không qua lớp giả giao thức OpenAI. Đó là một phụ thuộc mới: đề xuất đặt trong nhóm tùy chọn `agentqa-hosted` của `flywheel-eval`, nạp muộn, để máy không cài nhóm này vẫn chạy được mọi test. Việc này đổi `pyproject.toml` và `uv.lock`, vốn ngoài phạm vi file hiện tại của story (story chỉ cho thêm `opencv-python-headless`), nên cần Hiếu đồng ý và mở rộng phạm vi hoặc tách PR riêng (Q3 ở mục 16). Cũng cần Hiếu xác nhận một SDK gọi HTTP của nhà cung cấp nằm trong `flywheel.eval` là chấp nhận được theo 03 mục 7.3: nó không phải adapter hay runtime mô phỏng, và import-linter hiện không cấm, nhưng đây là lần đầu làn có phụ thuộc loại này.

## 13. Kiểm thử

| Tầng | Kiểm gì | Chạy ở đâu |
|---|---|---|
| Đơn vị | Từng công cụ, từng luật kiểm của B5, từng luật giả thuyết | CPU, mọi PR |
| Từng bước | File vào mẫu ra đúng file ra mẫu; file sai schema bị từ chối | CPU, mọi PR |
| Cả đường ống | Gói mẫu `public` chạy hết với `--no-model`, và với `--replay` trên một file ghi mẫu; kết quả so với bản lưu | CPU, mọi PR |
| Cổng | Gói `internal` với hồ sơ hosted: dừng trước lời gọi đầu, mã thoát khác 0. Chạm trần ngân sách: `degraded`, không sập | CPU, mọi PR |
| Rào | Không module nào ngoài `casebench/` đọc đáp án; import-linter cho luật làn | CPU, mọi PR |
| Chất lượng | Bộ lỗi cấy, bộ ca lịch sử, báo nhầm trên gói khỏe (design 19/11 mục 11) | Khi đổi phiên bản; lượt có model thật theo runbook |

## 14. Cấu trúc mã và hợp đồng

```text
agentqa/
  tools/        B2: mỗi công cụ một file (đã có 6)
  round/
    records.py    model pydantic của các file giữa bước (riêng của làn)
    pack.py       B0    admit.py      B1    measure.py   B2 (kế hoạch công cụ)
    hypotheses.py B3    roles.py      B4    verify.py    B5
    assemble.py   B6    render.py     B7
    gateway.py    cổng model; providers/ cho từng nhà cung cấp
    pipeline.py   chạy các bước, ghi run.json, --from, --no-model, --replay
  casebench/    bộ ca lịch sử
  bench/        DA-31, không sửa
```

Mã bản 3 (`agent.py`, `analyze.py`, `run.py`) tiếp tục phục vụ lệnh `fw agentqa run` và bộ chấm DA-31. Vai `adjudicate` dùng lại phần dựng ứng viên của `analyze.py`. Không xóa đường cũ trong DA-43; gộp hai đường là việc của một story sau, khi đường mới đã có điểm.

**Hợp đồng.** Chỉ thứ đi qua ranh giới làn mới cần PR hợp đồng:

| # | Thứ | Cần hợp đồng? | Ghi chú |
|---|---|---|---|
| K1 | Outcome của một lượt eval | Có | Như design 19/11; chung PR với DA-42 |
| K2 | `RoundDiagnosis` | Có | Console và làn Vòng sẽ đọc. Thêm trường: trạng thái lần chạy, hash phiên bản, và với mỗi mục là nguồn (`model` hay `code`) |
| K3 | Nguồn gốc của fact và phiên bản agent trong `AgentReport` | Có, nhỏ | Như design 19/11 |
| — | Bản ghi lời gọi công cụ, lời gọi model, phán quyết, bảng kê gói | **Không** | Sinh và đọc trong cùng làn Đánh giá. Design 19/11 xếp bản ghi lời gọi công cụ vào K3; đề xuất rút ra để hợp đồng nhỏ hơn |

## 15. Ảnh hưởng tới story DA-43

Việc đã xong (1.2, 2.1–2.3) giữ nguyên và nằm đúng ở B2. Nhiệm vụ 3 (các công cụ còn lại) không đổi. Nhiệm vụ 4 và 5 **[Đề xuất]** sắp lại theo đường ống; số nhiệm vụ con 4.x và 5.x chưa dùng trong commit nào nên đổi được:

| Nhiệm vụ | Nội dung | Mốc dùng được |
|---|---|---|
| 4.1 | B0 và B1: `round.yaml`, `pack.json`, nhận, lớp dữ liệu của gói; gói giả log robot thật | Gói mẫu `C_70` được nhận; gói `internal` được đánh dấu |
| 4.2 | B2 thành một bước: kế hoạch công cụ, thư mục lần chạy, `run.json`, `--from` | Chạy lại được từng bước |
| 4.3 | B3: bảng luật, danh mục phép kiểm, hạng của code, luật chặn ngân sách dữ liệu | Giả thuyết H1, H3 ra từ gói mẫu |
| 4.4 | B6 và B7 với `--no-model`, ghi `assembly.json` (chưa ghi `round_diagnosis.json`); lệnh `fw agentqa round` | **Báo cáo vòng đầu tiên, không cần model** |
| 5.1 | Cổng model: hồ sơ, bảng vai × lớp dữ liệu, chặn hosted, ngân sách, ghi và phát lại | Gói `internal` không gọi được hosted (có test) |
| 5.2 | Vai `adjudicate` và `rank`: prompt, schema | Chạy với Nemotron cục bộ |
| 5.3 | B5: luật 1–8, ba sửa của bản 3, phán quyết và sàn code | Mục trượt về sàn code, lần chạy `degraded` |
| 5.4 | Lớp hosted kiểu OpenAI (OpenRouter); lớp Anthropic nếu Q3 được duyệt | Chạy với model thuê trên gói `public` |
| 5.5 | Xuất `round_diagnosis.json` theo `RoundDiagnosis` sau khi PR K2 merge | Console đọc được |

Nhiệm vụ 6 (bộ ca), 7 (đo) và 8 (nhìn hình, vai `look`) giữ nguyên. Story đã sửa theo bảng này ngày 20/11/2026.

## 16. Quyết định cần Hiếu

**[Đã chốt 20/11/2026, Hiếu]** "Duyệt theo đề xuất": mọi dòng dưới đây chốt theo cột đề xuất (bản 0.3).

| # | Quyết định | Đề xuất (đã chốt) |
|---|---|---|
| Q1 | Dựng theo đường ống 8 bước của tài liệu này, thay mục 5.1, 5.4, 12 và phần chọn model của mục 8 của design 19/11 (sáu điều chặn cứng của mục 8 giữ nguyên) | Có |
| Q2 | Model trượt kiểm thì mục đó về sàn code và lần chạy là `degraded`, thay cho "cả phần tổng hợp `broken`" (design 19/11 mục 6, luật 8) | Có |
| Q3 | Thêm SDK `anthropic` vào nhóm tùy chọn `agentqa-hosted`: mở rộng phạm vi file của story cho `pyproject.toml` và `uv.lock`, và chấp nhận phụ thuộc này trong làn Đánh giá | Có. Nếu không: chỉ dùng OpenRouter cho đường hosted |
| Q4 | Mở đường hosted cho gói `public`, hồ sơ mặc định `claude-haiku-5-5`; chọn model cuối bằng lượt so sánh ở mục 12 | Có |
| Q5 | Rút cửa "model xin thêm công cụ" khỏi DA-43 | Có |
| Q6 | Rút bản ghi lời gọi công cụ khỏi PR hợp đồng K3 (để riêng trong làn) | Có |
| Q7 | Sắp lại nhiệm vụ 4 và 5 của story theo mục 15 | Có |
| Q8 | Hỏi đáp về chẩn đoán đi qua chat của Console (đã có), đọc file của đường ống; DA-43 không dựng chat thứ hai. Tool chat đọc chẩn đoán làm ở một story Console sau | Có |
| Q9 | Bộ nhớ dài hạn chỉ là bản ghi có cấu trúc do code và kỹ sư ghi (mục 21); không có ghi chú tự do do model viết | Có |

## 17. Để lại cho người dựng

- Tên trường ở mục 24 là đề xuất; đổi được, miễn mỗi file ở mục 7 có một model pydantic và một test đọc ghi.
- Dạng của `round.yaml` và của `assembly.json`, miễn `round.yaml` khai đủ: task, run, checkpoint, job, release, dataset, đường dẫn, lớp dữ liệu.
- Công thức chính xác của hạng code ở B3, miễn tất định, theo thứ tự spec 6.4, và có test.
- Giá trị trần ngân sách mặc định; chỉnh sau lần đo đầu.
- Cách cắt chuỗi lấy từ artifact trước khi vào prompt.

---

# Phần B. Thiết kế chi tiết (bản 0.2)

## 18. Hai bề mặt: báo cáo vòng và hỏi đáp

Câu hỏi "đây là agent chat đúng không" có hai nửa câu trả lời, vì dự án có **hai** thứ đều gọi là agent:

| | Báo cáo vòng (DA-43, tài liệu này) | Hỏi đáp (chat của Flywheel Console) |
|---|---|---|
| Đã có chưa | Đang dựng | **Đã có**, chạy trong demo 17/11/2026: `packages/flywheel-console/src/flywheel/console/chat/` |
| Ai khởi động | Một lệnh, sau khi một vòng xong | Người dùng gõ câu hỏi trên Console |
| Dạng | Đường ống cố định, không hội thoại | Agent chat: model chọn tool, đọc kết quả, trả lời |
| Tool calling | Code gọi công cụ theo kế hoạch; model không gọi | Có: khoảng 20 tool trong `registry.py` (`eval_summary`, `eval_failures`, `run_compare`, `lineage`, `round_report`…), mỗi lượt mời tối đa 7 |
| Vòng lặp | Không; chỉ một lần gửi lại khi trượt kiểm | Có, tối đa 3 vòng gọi tool rồi một lượt trả lời (`MAX_ROUNDS = 3`) |
| Bộ nhớ hội thoại | Không cần | Có: lịch sử cuộc trò chuyện |
| Trả lời câu gì | "Vòng này hỏng vì đâu, kiểm gì, làm gì tiếp" cho cả vòng | "Run A khác run B thế nào", "cụm c1 gồm lượt nào", và sau này "vì sao agent xếp H1 trước" |

**Vì sao không gộp thành một agent chat.** Chẩn đoán một vòng cần chạy 14 công cụ trên hàng trăm lượt và phải cho cùng kết quả mỗi lần chạy. Nếu để model chat tự quyết gọi gì, hai lần hỏi sẽ ra hai chẩn đoán, và không chấm điểm được. Vì vậy phần nặng làm một lần, ngoài hội thoại, rồi ghi ra file; chat chỉ **tra** file đó.

**Hai bề mặt nối nhau bằng file, không bằng import.** Repo có luật import "Console reads files, never lanes or adapters": Console không được import `flywheel.eval`. Nên:

- Đường ống ghi `round_diagnosis.json` (hợp đồng K2) và thư mục lần chạy.
- Chat của Console thêm một tool đọc file đó (ví dụ `diagnosis_get`: giả thuyết của một cụm, fact ủng hộ, phép kiểm, can thiệp). Tool này thuộc package Console, làm ở **story Console sau** (Q8); DA-43 chỉ bảo đảm file đủ thông tin.
- Câu hỏi đào sâu cần phép tính mới (ví dụ "nới dung sai lên 15 cm thì sao") được phục vụ bằng cách đường ống **tính sẵn cả lưới** tham số của config task và ghi vào `tables/`; chat tra bảng, không tính.

## 19. Tool calling

"Tool" là một hàm mà hệ gọi để lấy dữ kiện. Câu hỏi thiết kế là **ai quyết gọi** và **tham số từ đâu**. Hệ này có ba mức:

| Mức | Ai quyết gọi tool | Ở đâu | Trạng thái |
|---|---|---|---|
| 1. Code gọi theo kế hoạch | Code, theo file kế hoạch của task | B2 của đường ống | Dựng trong DA-43 |
| 2. Model chọn trong tập đóng | Model trả id (giả thuyết, phép kiểm, can thiệp); code thực thi | B4, vai `rank` | Dựng trong DA-43 |
| 3. Model gọi tool tự do trong vòng lặp | Model, mỗi vòng | Chat của Console | Đã có; không dựng lại |

Mức 2 là một dạng tool calling bị thu hẹp: model vẫn "ra lệnh" (chọn phép kiểm nào), nhưng chỉ chọn được trong danh sách code đưa, và không có tham số tự do. Nó giữ được lợi ích chính của tool calling (model quyết việc cần phán đoán) mà bỏ rủi ro chính (model bịa tham số).

### 19.1 Hợp đồng của một công cụ (mức 1)

Mỗi công cụ đăng ký một `ToolSpec` trong `tools/registry.py`:

| Trường | Nội dung | Ví dụ (`relaxed_sweep`) |
|---|---|---|
| `name`, `version` | Tên và số phiên bản; đổi cách tính thì tăng phiên bản | `relaxed_sweep`, 1 |
| `needs` | Loại artifact bắt buộc phải có | `scores`, `outcomes` |
| `params` | Từng tham số và **miền đóng** của nó: tập giá trị của config task, id đơn vị trong gói, hoặc id fact | `label` ∈ nhãn của task; `grid` = lưới `relaxed.position_m` của task |
| `fn` | Hàm thuần `(book, task, inputs, params) -> ToolResult` | |
| `fact_names` | Mẫu tên fact nó sinh, để luật giả thuyết tham chiếu | `{run}_relaxed_{grid}_successes` |

Luật thiết kế công cụ, áp cho mọi công cụ mới:

1. **Một việc.** Một công cụ trả lời một câu hỏi đo lường. Không có công cụ "phân tích tổng hợp".
2. **Chỉ đọc, thuần, tất định.** Cùng đầu vào thì cùng đầu ra; không ghi gì ngoài `FactBook`.
3. **Trả fact, không trả văn.** Kết quả là số và nhãn có đơn vị và nguồn. Câu chữ là việc của bước sau.
4. **So sánh là một fact.** Công cụ nào so với ngưỡng thì tự ra fact boolean (ví dụ `tracking_p99_exceeds_tau`), để model không phải tự so hai số (luật 6 của design 19/11).
5. **Lỗi là giá trị.** Thiếu đầu vào ra fact "không xét được" kèm lý do; chỉ lỗi lập trình mới ném ngoại lệ.
6. **Không tham số tự do.** Mọi tham số thuộc miền đóng; số viết tay bị từ chối khi nạp kế hoạch.
7. **Có test đối chiếu** với một số đã công bố, khi có số như vậy.

### 19.2 Kế hoạch công cụ

`configs/eval/agentqa/plans/<task>.yaml` liệt kê lời gọi: công cụ, tham số, chạy trên run nào. B2 thực thi như sau:

- nạp kế hoạch, kiểm mọi tham số thuộc miền đóng của `ToolSpec`;
- với mỗi lời gọi: thiếu `needs` thì ghi fact "không xét được" và đi tiếp; đủ thì chạy;
- ghi một dòng `tool_calls.jsonl` cho mỗi lời gọi, kể cả lời gọi không chạy được;
- khóa nhớ đệm là (tên, phiên bản, tham số, sha256 đầu vào): chạy lại với `--from` không tính lại lời gọi đã có.

### 19.3 Tool của chat (mức 3)

Chat của Console giữ registry riêng và các rào đã có: mỗi lượt mời tối đa 7 tool theo trang và câu hỏi; tool đọc dữ liệu `internal` không được mời khi model là hosted (`LOCAL_ONLY`); với model nhỏ, code tự chạy tra cứu và model chỉ viết câu trả lời; số trong câu trả lời được đối chiếu với kết quả tool. DA-43 không sửa các rào này. Tool đọc chẩn đoán (Q8) phải theo đúng chúng: chỉ đọc, tham số là id (vòng, cụm, giả thuyết), và ẩn với model hosted khi vòng không phải `public`.

## 20. Vòng lặp

"Vòng lặp agent" là: model trả lời → code làm theo → kết quả quay lại model → lặp tới khi dừng. Rủi ro của nó là không dừng, tốn tiền, và đi lạc. Luật của hệ này: **mọi vòng lặp có trần cứng do code giữ**, không vòng nào dừng vì "model thấy đủ".

| Vòng | Ở đâu | Lặp cái gì | Trần | Dừng khi |
|---|---|---|---|---|
| Đường ống | B0 → B7 | Không lặp; đi thẳng một chiều | 8 bước | Hết bước, hoặc một bước `broken` |
| Sửa câu trả lời | Trong B4 | Gửi lại một mục kèm lỗi kiểm | 1 lần mỗi mục | Qua kiểm, hoặc đã gửi lại một lần |
| Thử lại mạng | Trong cổng model | Lời gọi lỗi mạng, quá tải | 2 lần, giãn cách tăng dần | Thành công, hết lượt, hoặc quá hạn thời gian |
| Ngân sách | Cổng model, cả lần chạy | Mọi lời gọi | Số lời gọi, token, tiền trong config | Chạm trần: các mục còn lại về sàn code |
| Gọi tool của chat | Console | Model gọi tool, đọc kết quả | 3 vòng, rồi một lượt trả lời không tool | Model trả lời, hoặc hết vòng |
| Vòng ngoài (flywheel) | Giữa các vòng dữ liệu | Báo cáo → kỹ sư duyệt → can thiệp → kết quả → lịch sử | Một lượt mỗi vòng dữ liệu; người quyết | Kỹ sư ký `Decision` |

Vòng ngoài là vòng quan trọng nhất và là vòng duy nhất có người ở trong: agent đề xuất, kỹ sư quyết, kết quả thật quay lại thành dữ kiện của vòng sau (mục 21). Agent tốt lên nhờ vòng này, không nhờ model tự lặp lâu hơn.

**Khi nào mới thêm vòng điều tra tự do** (model tự gọi công cụ nhiều vòng trong đường ống, tức cửa đã rút ở Q5). Cần đủ ba điều: (1) bộ ca lịch sử có ca mà sàn code và vai `rank` cùng trượt vì thiếu một phép đo mà công cụ sẵn có tính được; (2) có model gọi tool ổn định dùng được cho lớp dữ liệu của ca đó; (3) vòng đó chạy sau B5, kết quả của nó lại qua B5. Khi thêm, nó là một vai thứ tư với trần số vòng, không đổi các bước khác.

## 21. Bộ nhớ

"Bộ nhớ" của một hệ dùng model là mọi thứ nó biết ngoài câu hỏi hiện tại. Có bốn loại, và hệ này dùng mỗi loại một cách khác:

| Loại | Là gì ở hệ này | Ai ghi | Sống bao lâu |
|---|---|---|---|
| Ngữ cảnh của một lời gọi | Prompt của lời gọi đó: luật của vai, ứng viên, các fact liên quan. Dựng mới mỗi lần từ file | Code | Một lời gọi |
| Trạng thái lần chạy | Thư mục lần chạy (mục 7) | Code | Vĩnh viễn, bất biến |
| Bộ nhớ dài hạn | **Lịch sử có cấu trúc**: kết quả can thiệp (`EvidenceCard.result`), tỉ lệ sửa được (`FixRateEvent`), quyết định của kỹ sư (`AgentReview`), sổ chi phí | Kỹ sư và code, qua `flywheel.store` | Vĩnh viễn, append-only |
| Bộ nhớ hội thoại | Lịch sử cuộc trò chuyện của chat | Console | Một cuộc trò chuyện |

Ba quyết định thiết kế:

**Lời gọi model không mang trạng thái.** Mỗi lời gọi ở B4 là độc lập: không có "cuộc hội thoại" giữa các lời gọi, không có tóm tắt lượt trước. Thứ nối các lời gọi là file (phát hiện đã qua kiểm của vai `adjudicate` thành đầu vào của vai `rank`). Lợi: phát lại được từng lời gọi, chạy song song được, và một câu trả lời sai không nhiễm sang lời gọi sau.

**Bộ nhớ dài hạn là bản ghi, không phải ghi chú** (Q9). Model không được tự viết "bài học" để vòng sau đọc. Lý do: ghi chú tự do mang số không kiểm được, có thể kéo dữ liệu `internal` sang một vòng `public`, và sai một lần thì sai mãi. Thay vào đó, công cụ `history_lookup` tra bản ghi theo **khóa** (task, chẩn đoán, loại can thiệp, dấu hiệu của cụm: bước hỏng và nhãn), không theo độ giống ngữ nghĩa, và trả về fact có nguồn gốc `history`, ví dụ "can thiệp `sim_s1` cho `weak_skill` ở task khay: 1 lần, kết quả F". Fact `history` chỉ kéo từ vòng cùng lớp dữ liệu hoặc lớp thấp hơn.

**Bộ nhớ về chính agent là bảng điểm.** Mỗi phiên bản agent có điểm kèm hash (mục 11). Mỗi lần kỹ sư `override` một phát hiện là một ứng viên ca mới cho bộ ca lịch sử. Đó là cách hệ "nhớ" lỗi của mình: thành một ca kiểm chạy lại mãi, không thành một dòng nhắc trong prompt.

Không dựng trong DA-43: cơ sở dữ liệu vector, tìm kiếm ngữ nghĩa trên báo cáo cũ. Với vài chục vòng, tra theo khóa là đủ và kiểm được; 03 mục 2.4 cũng không cho thêm dịch vụ ở L0.

## 22. Gói kiến thức (skill)

"Skill" là một gói hướng dẫn và dữ liệu mà hệ **chỉ nạp khi việc cần tới**, để prompt cố định nhỏ và thêm việc mới không phải sửa mã. Hệ này có đúng khái niệm đó, dưới dạng config:

| Gói | File | Nạp khi nào | Thêm cái mới nghĩa là |
|---|---|---|---|
| Gói task | `tasks/<task>.yaml` (đã có `tray.yaml`): bước, ngưỡng và đơn vị, nhãn lỗi và tín hiệu cần, lưới nới | Gói vòng khai task đó | Thêm task: thêm một file |
| Kế hoạch công cụ | `plans/<task>.yaml` | B2 | Thêm phép đo cho task |
| Bộ luật giả thuyết | `rules/<nhóm>.yaml`: bộ chấm, runtime, train, dữ liệu, vùng phủ | B3; chỉ luật có dấu hiệu khớp mới sinh giả thuyết | Thêm một nguyên nhân biết nhận diện |
| Danh mục phép kiểm | `checks.yaml`: tên, tách cặp chẩn đoán nào, cần gì, khóa chi phí | B3 | Thêm một phép kiểm |
| Prompt của vai | `prompts/<vai>.md` cộng mảnh `prompts/sources/<nguồn>.md` | B4; mỗi lời gọi chỉ ghép mảnh của nguồn và chẩn đoán có mặt trong lời gọi đó | Chỉnh cách model lập luận về một nguồn |
| Câu hỏi nhìn hình | `vision/<task>.yaml` | Vai `look` | Thêm câu hỏi đóng |

Quy tắc ghép prompt: **phần cố định trước, phần thay đổi sau**. Luật của vai và schema câu trả lời đứng đầu và giống nhau giữa các lời gọi; ứng viên và fact đứng cuối. Model nhỏ bám luật tốt hơn khi luật ngắn, và với model hosted phần đầu giống nhau được tính giá đọc đệm rẻ hơn.

Mỗi luật giả thuyết ghi **nguồn** là một mục của spec hoặc design, không phải một ca cụ thể, để bảng luật không thành bản chép đáp án (rủi ro ở design 19/11 mục 13).

Không dùng sản phẩm "Agent Skills" của nhà cung cấp: nó chạy trong môi trường hosted, nên không dùng được cho model cục bộ và dữ liệu `internal`. Config của mình cho cùng lợi ích và chạy ở cả hai đường.

## 23. Điểm mở rộng (plugin)

"Plugin" là cách thêm khả năng mà không sửa lõi. Hệ này có bảy điểm mở rộng; mỗi điểm là một giao diện cố định cộng một chỗ đăng ký tường minh:

| Thêm | Viết gì | Đăng ký ở | Phải kèm | Thành phiên bản agent mới? |
|---|---|---|---|---|
| Công cụ | Một file trong `tools/`, một `ToolSpec` | `tools/registry.py`, rồi kế hoạch của task | Test đơn vị; test "không xét được" | Có |
| Task | Gói task, kế hoạch, câu hỏi nhìn hình | `configs/eval/agentqa/` | Gói vòng mẫu chạy hết `--no-model` | Có |
| Luật giả thuyết, phép kiểm | Dòng trong `rules/`, `checks.yaml` | Config | Test trên fact mẫu; nguồn của luật | Có |
| Nguồn dữ liệu (ví dụ log robot DENSO) | Một adapter **ngoài làn** đổi log sang artifact hợp đồng, đóng dấu `internal` | Lệnh xuất của adapter; kỹ sư khai trong `round.yaml` | Test hợp đồng; gói giả thiếu kênh | Không (đầu vào, không phải agent) |
| Nhà cung cấp model | Một lớp trong `round/providers/` thực hiện `ChatModel` | Bảng nhà cung cấp của cổng; hồ sơ trong config | Test với câu trả lời giả; test chặn lớp dữ liệu | Có (hồ sơ model nằm trong hash) |
| Vai | Prompt, schema câu trả lời, phạm vi fact, luật kiểm | `round/roles.py` | Test phát lại; ca trong bộ ca lịch sử | Có |
| Cách trình bày | Một hàm đọc `assembly.json` | `round/render.py` | Test ảnh chụp đầu ra | Không |

**Đăng ký tường minh, không tự dò.** Không dùng cơ chế tự phát hiện plugin lúc chạy (entry point, quét thư mục). Lý do: mọi thứ agent dùng phải nằm trong hash phiên bản và trong lượt review mã; một plugin tự nạp là một thay đổi không ai chấm.

Nguồn dữ liệu là điểm mở rộng quan trọng nhất cho DENSO: lõi và công cụ không biết gì về định dạng log của robot thật. Adapter đổi log sang hợp đồng; tín hiệu thiếu thì `signal_presence` báo và báo cáo ghi CHƯA RÕ.

## 24. Schema các bản ghi giữa bước

Riêng của làn Đánh giá (`round/records.py`). Trường là đề xuất.

| File | Một dòng là | Trường chính |
|---|---|---|
| `pack.json` | Cả gói | `pack_id`, `task_id`, `created_at`, `declared_by`; `entries[]`: `ref`, `kind`, `schema`, `sha256`, `bytes`, `data_class`, `subject` (run, job, checkpoint, release hoặc dataset); `links[]`: `from`, `to`, `relation` |
| `admission.json` | Cả gói | `pack_sha256`; `accepted[]`; `rejected[]`: `ref`, `reason`; `missing_kinds[]`; `data_class`; `data_class_basis` (bản ghi nguồn nào xác nhận); `hosted_allowed` |
| `facts.jsonl` | Một fact | `fact_id`, `name`, `value`, `unit`, `source_ref`, `provenance` (`code`, `vision`, `history`), `tool_call_id` |
| `tool_calls.jsonl` | Một lời gọi công cụ | `call_id`, `tool`, `version`, `params`, `input_sha256[]`, `fact_ids[]`, `not_judged[]`, `seconds` |
| `hypotheses.jsonl` | Một giả thuyết của một cụm | `hypothesis_id`, `cluster`, `rule_id`, `diagnosis`, `note`, `support[]`, `contra[]`, `interventions[]`, `checks[]` (id phép kiểm, cặp tách được, khóa chi phí), `code_rank`, `blocked_data_spend` |
| `model_calls.jsonl` | Một lời gọi model | `call_id`, `role`, `unit` (nguồn hoặc cụm), `attempt` (1 hoặc 2), `request_sha256`, `prompt_sha256`, `profile`, `model`, `revision`, `host`, `tokens_in`, `tokens_out`, `usd`, `seconds`, `status`, `reply` |
| `verdicts.jsonl` | Một mục của model | `item_id`, `role`, `unit`, `verdict` (`accepted`, `repaired`, `rejected`), `failed_rules[]`, `call_ids[]` |
| `assembly.json` | Cả báo cáo | `status`; `agent_version`, `agent_hash`; theo cụm: giả thuyết đã xếp hạng, mỗi cái có `source` (`model` hoặc `code`), câu giải thích, fact; phép kiểm rẻ nhất và `Cost`; can thiệp và `InterventionProposal`; `not_judged[]`; `report_ids[]` |
| `run.json` | Cả lần chạy | `run_id`, `command`, `git_sha`, `agent_version`, `agent_hash`, `pack_sha256`, `data_class`; `steps[]`: `name`, `status`, `seconds`, `rows`; `totals`: lời gọi, token, tiền; `model_hosts[]` |

## 25. Prompt và câu trả lời của từng vai

Mọi lời gọi có cùng khung: một tin nhắn hệ thống (luật của vai, schema, ghép theo mục 22) và một tin nhắn người dùng chứa **một khối JSON** dữ liệu. Không có ví dụ câu trả lời chứa số thật, để model không chép số.

**Vai `adjudicate`.** Dùng lại dạng của bản 3 để `AgentReport` không đổi:

```json
{"decisions": [{"candidate": "C1", "keep": true, "cites": ["F3", "F9"],
                "insight": "Loss val tăng {F3} lần sau bước {F9}.", "suggestion": "..."}],
 "added": []}
```

**Vai `rank`.** Một cụm một lời gọi:

```json
{"cluster": "approach_a/L-PLACE-POSE",
 "order": ["H2", "H1", "H4"],
 "why": [{"hypothesis": "H2", "cites": ["F41", "F57"],
          "text": "Chuỗi bước gãy ở {F41} lượt, trong đó {F57} lượt thành công."}],
 "check": {"id": "K3", "cites": ["F41"], "text": "..."},
 "intervention": {"id": "repair_ticket", "for": "H2", "cites": ["F41"], "text": "..."},
 "other": []}
```

**Vai `look`.** `{"answers": [{"question": "Q1", "answer": "không rõ"}]}`.

B5 kiểm mỗi mục theo danh sách cố định; mỗi dòng là một hàm và một test:

| Kiểm | Trượt khi |
|---|---|
| Đúng schema | Thiếu trường, sai kiểu, JSON bị cắt |
| Id thuộc tập đã đưa | Giả thuyết, phép kiểm, can thiệp hay fact không có trong lời gọi đó |
| `order` là hoán vị | Thiếu hoặc lặp giả thuyết của cụm |
| Can thiệp được phép | Không thuộc `INTERVENTIONS_OF_DIAGNOSIS` của giả thuyết nó nhắm; hoặc tiêu ngân sách dữ liệu khi cụm bị chặn |
| Mỗi câu có trích | `cites` rỗng |
| Số trong câu | Có chữ số ngoài chỗ chèn `{F#}`; hoặc `{F#}` không nằm trong `cites` |
| So sánh | Câu có từ so sánh, trích hai fact khác đơn vị, mà không trích fact so sánh nào |
| Fact đúng chủ | Mục model tự thêm không trích fact nào của chính mã hay giả thuyết đó |
| Bỏ có lý do | Bỏ ứng viên có fact chiều đang đúng mà không trích fact phản bác |
| Nguồn gốc | Giả thuyết hạng 1 chỉ có fact `vision` ủng hộ |

## 26. Config

```text
configs/eval/agentqa/
  agent.yaml          phiên bản; hồ sơ model cục bộ (đã có)
  hosted.yaml         hồ sơ hosted, tắt mặc định; tên biến môi trường của khóa
  routing.yaml        vai × lớp dữ liệu → hồ sơ; trần ngân sách; số lời gọi song song
  tasks/<task>.yaml   gói task (đã có tray.yaml)
  plans/<task>.yaml   kế hoạch công cụ
  rules/*.yaml        luật giả thuyết theo nhóm
  checks.yaml         danh mục phép kiểm
  prompts/            <vai>.md và sources/<nguồn>.md
  vision/<task>.yaml  câu hỏi đóng
```

Mọi file trên, trừ `hosted.yaml` phần khóa, vào hash phiên bản agent (mục 11). Đổi một dòng là phiên bản mới, phải chấm lại.


## Nguồn

- [Design 19/11/2026](2026-11-19-agent-qaqc-system-design.md) mục 1.2, 3–7, 11; [story DA-43](../../product/stories/DA-43-he-agent-qa-qc.md)
- [Agent QA/QC bản 3 (DA-20)](../../g0/agent-qa.md); [thí nghiệm khay](../../he/tray.md) mục 20.11–20.13
- [03 · Kiến trúc](../../product/03-architecture.md) mục 2.4, 7.3; [07 · Chia việc](../../product/07-team-workflow.md) mục 3.2
- Mã: `packages/flywheel-eval/src/flywheel/eval/agentqa/` (`inputs.py`, `run.py`, `endpoint.py`, `agent.py`); chat của Console: `packages/flywheel-console/src/flywheel/console/chat/` (`llm.py`, `registry.py`, `providers.py`); luật import trong `pyproject.toml` gốc
- Giá Anthropic: bảng giá của Anthropic, bản lưu ngày 3/11/2026. Giá chưa kiểm của nhà cung cấp khác: [benchlm.ai](https://benchlm.ai/llm-pricing), [morphllm.com](https://www.morphllm.com/llm-api), [getnadir.com](https://getnadir.com/blog/llm-api-pricing-june-2026-complete-comparison/), [iotdigitaltwinplm.com](https://iotdigitaltwinplm.com/llm-api-pricing-november-2026-gpt-claude-gemini-grok-deepseek-mistral/), [getmaxim.ai](https://www.getmaxim.ai/bifrost/model-library/provider/openrouter), tra ngày 20/11/2026
