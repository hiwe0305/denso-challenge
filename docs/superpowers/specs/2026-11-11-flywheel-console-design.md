# Flywheel Console · phân tích nghiệp vụ và thiết kế

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 11/11/2026 | 0.5 | Bản v5 và ghép v3 + v5 theo yêu cầu của Hiếu tối 11/11: mục mới 15.1b (người dùng là AI Engineer, Agent là chatbot gọi công cụ, khung sidebar trái + panel phải, trực quan trước, giới hạn chữ, bench chatbot); ghi chú thay thế ở mục 6, 7, P6, 15.1a; câu hỏi 6 (mục 16); quyết định 6–8 (mục 17) | Hiếu (soạn với Claude) |
| 11/11/2026 | 0.4 | Console chạy được việc, theo yêu cầu của Hiếu chiều 11/11: mục 11.1 (bộ chạy việc), 15.1 (bỏ "chỉ đọc"), mục mới 15.1a (bộ chạy việc, Nhập, Xuất, vòng flywheel, chế độ trình chiếu), 17.1 và 17.2 | Hiếu (soạn với Claude) |
| 11/11/2026 | 0.3 | Thiết kế lại sau đánh giá của Fable, chuẩn hình thức là Egocentric Explorer: mục 6 (nguyên tắc, token sáng), mục 7 (sáu tab, bỏ menu trái và cột phải, các mức xem dữ liệu), 11.1 (server có Range, ảnh bằng `cv2`, thư viện đóng gói), 12 (chế độ trình chiếu), 15.1 (lộ trình demo, gói việc, lịch) | Hiếu (soạn với Claude) |
| 11/11/2026 | 0.2 | Thêm P0 Datasets (danh mục toàn hệ thống, 60 dataset); console vào demo 12/11, phạm vi bản 12/11 (mục 15.1); câu hỏi mở và quyết định của người viết (mục 16, 17) | Hiếu (soạn với Claude) |
| 11/11/2026 | 0.1 | Bản đầu: phân tích nghiệp vụ, kiểm kê dữ liệu thật, tham khảo sản phẩm, yêu cầu từng trang, kiến trúc đề xuất | Hiếu (soạn với Claude) |

Tài liệu này là bản phân tích nghiệp vụ (BA) cho **Flywheel Console**: trang web nội bộ để quản lý, xử lý và theo dõi toàn bộ data flywheel. Nó đặt cạnh thiết kế web của Châu (`web/DESIGN.md` trên nhánh `chore-web-m0-khung`, PR #72, chưa merge). Mục 11 nói hai bản quan hệ thế nào.

Nhãn quyết định theo [docs/CLAUDE.md](../../CLAUDE.md): **[Đã chốt]** là Hiếu đã nói, **[Đề xuất]** là người viết đề xuất, **[Option]** là nhiều phương án, chờ Hiếu chọn.

---

## 1. Bối cảnh và lý do

Ngày 11/11/2026, trong lúc chờ training, Hiếu muốn hoàn thiện website của sản phẩm. Ba ý của Hiếu, theo đúng lời:

- Web phải "đưa được toàn bộ mọi thứ", vì nó "dùng để quản lý, xử lý dữ liệu theo đúng một data flywheel". **[Đã chốt]**
- Phải "show ra cả được log, toàn bộ cách làm và kết quả từng bước". Phần data, training, eval "phải có cả biểu đồ, đồ thị hỗ trợ đánh giá, phân tích". **[Đã chốt]**
- Trọng tâm là **agent** và **data**. Training và eval có thêm lựa chọn chạy trên **máy ảo** (Colab…) và **máy vật lý**. **[Đã chốt]** Cách hiểu "lựa chọn" còn mở (mục 10).
- Code do model Sonnet viết, sau khi bản BA này được duyệt. **[Đã chốt]**

Bản phác v1 (khung menu, vài thẻ số, bảng tĩnh) bị đánh giá là "chán": không biểu đồ, không log, không thấy cách làm. Bản này sửa từ gốc: mỗi bước phải có ba lớp **Cách làm · Log · Kết quả**, và mỗi kết quả có biểu đồ.

Website tĩnh hiện tại trong `website/` là trang giới thiệu công khai (spec v10.1). Nó giữ nguyên và không thuộc phạm vi tài liệu này.

## 2. Người dùng và việc họ cần làm

| Người | Việc chính trên console |
|---|---|
| Hiếu (PO, người duy nhất chạy job GPU, duyệt và merge) | Xem flywheel đang ở đâu; theo dõi job đang chạy và CU còn lại; đọc kết quả eval; duyệt đề xuất dữ liệu và job |
| Long (nhân, làn Vòng) | Failure→Data: cụm lỗi, evidence, can thiệp, ngân sách |
| Hưng (egocentric, Agent QA/QC) | Kiểm nguồn egocentric, xem lý do QA từng clip, chạy agent, duyệt phát hiện của agent |
| Châu (làn Đánh giá) | Kết quả eval, funnel, nhãn lỗi, video rollout, so cặp hai checkpoint |
| Người xem demo 17/11 | Xem Hiếu trình chiếu trên máy đội; không truy cập trực tiếp |

Các tình huống cụ thể (dùng làm kịch bản nghiệm thu, mục 14):

- **T1.** Sáng nay flywheel đang ở bước nào, có job nào chạy, có gì chờ mình duyệt?
- **T2.** Nguồn video tray của đội có 283/379 clip bị flag. Lý do là gì, clip nào tệ nhất? Mở một clip, xem video, xem từng phép kiểm với giá trị và ngưỡng, xem log của job QA đã sinh ra nó.
- **T3.** Agent QA/QC đã làm gì với lô này: model nào, prompt nào, đọc những gì, kết luận gì, mất bao lâu, tốn bao nhiêu? Mình đồng ý hay bác bỏ từng phát hiện.
- **T4.** Run `pair60k C_70` trên Colab đang ở bước nào, loss có giảm không, nhóm action nào học chậm, VM có treo không, đã tiêu bao nhiêu CU? Xem `train.log` đuôi.
- **T5.** Eval C trên tray đạt 20/240. Rơi ở bước nào (funnel), lỗi gì nhiều nhất, khay lệch đích bao nhiêu cm, xem video vài lượt hỏng.
- **T6.** Từ lỗi `L-PLACE-POSE` đi tới dữ liệu đã sinh thêm và model C+ đã train. Còn thiếu gì để đóng vòng?
- **T7.** Đã tiêu bao nhiêu tiền và giờ máy, so với ước tính, theo story, theo máy?
- **T8.** Muốn chạy một eval hoặc training: chọn máy (Colab A100, Colab L4, rtx3060, laptop), xem ước tính chi phí, gửi Hiếu duyệt.

## 3. Mục tiêu, không mục tiêu, phản mục tiêu

**Mục tiêu**

1. Mỗi bước của flywheel có trang riêng với ba lớp: **Cách làm** (lệnh, config và phiên bản ngưỡng, module code, mục tài liệu), **Log** (file log của lần chạy, xem đuôi, tìm, tải về), **Kết quả** (số tóm tắt, biểu đồ, bảng, tới từng episode).
2. Mọi con số đọc từ file thật trong `fwdata/`, `configs/`, `docs/`. Mỗi số có đường dẫn tới file gốc (nút "nguồn").
3. Đi xuống một mạch: tổng hợp → bảng đã lọc → một episode hoặc một run → log thô. Mỗi bậc một cú bấm; bộ lọc nằm trên URL.
4. Bước chưa chạy hiện rõ "chưa chạy" kèm thẻ cách làm và lệnh để chạy, không hiện số 0.
5. Hiện cả dữ liệu `internal` và dữ liệu có licence hạn chế, vì console chỉ chạy trên máy của đội (mục 12).

**Không mục tiêu**

- Không thay lõi `flywheel`. Console đọc artifact; mọi xử lý vẫn do lệnh `fw` và các module hiện có.
- Không host công khai, không đăng nhập nhiều người, không phân quyền chi tiết.
- Không viết lại trang giới thiệu `website/`.

**Phản mục tiêu** (có những điều này thì coi như hỏng dù chạy được)

- Một con số không truy ngược được về file, hoặc số chưa đo mà trông như kết quả.
- Dữ liệu `internal` hoặc video người rời máy đội, kể cả qua một API model hosted.
- Console tự khởi động job GPU hay tiêu CU mà Hiếu chưa bấm duyệt; hoặc để VM Colab chạy không sau khi job xong.
- Console đọc `vault/` (holdout) hoặc đưa đáp án `DefectManifest` cho agent.
- Trang đẹp nhưng chậm tới mức không mở được `metrics.jsonl` 6 MB hay `train.log` 900 KB.

## 4. Dữ liệu thật đang có (kiểm kê 11/11/2026)

Đây là cái console phải hiện. Chi tiết đường dẫn và schema ở mục 9.

| Bước | Có gì (số thật) | Ở đâu | Trạng thái |
|---|---|---|---|
| Nguồn | EgoDex 218 ep (CC-BY-NC-ND); video tray của đội 161 clip, đã che mặt (licence `team-internal`); psi-data two_table 99, hug 94 (licence chưa rõ); S1 planner 610 lần chạy → 542 ghi; S2 PICO ảo 5 300 biến thể → 843 | `fwdata/pipeline/src_*`, `fwdata/psi-data/`, `rtx3060:~/denso-da34-pool/fwdata` | Có |
| Pipeline và QA | Egocentric 379 clip: 42 pass / 283 flag / 54 reject, export 317 clip (0,88 h); lý do: `segment_ambiguous` 209, `hand_pose_nan` 150. S1: 534 pass / 7 reject, lọc chất lượng giữ 429; replay 542/542. psi-data 95 pass / 4 flag | `qa/egocentric.jsonl`, `report/*.json`, `human1m/*/summary.json`, `meta/batch_summary.json` | Có |
| Release, export | 5 release tray S1; một bản trên HF (CC BY 4.0); export LeRobot v2.1 đạt 17/18 mục | `releases/`, `docs/g0/export-v21.md` | Có |
| Agent QA/QC | Tầng code bắt 30/30 lỗi cấy trên **log giả**, 0/40 báo nhầm. Agent LLM mới chạy `EchoModel`; Nemotron, Qwen chưa chạy. Agent đọc log 3 fine-tune thật: cờ T1, T2, T8 (nghi báo nhầm) | `docs/g0/agent-qa.md`, `defect-bench.md`; không có output trong `fwdata` | Một phần |
| Training | C 40k bước (loss 49,0 → 0,10, 16,0 CU); C+ 40k (16,1 CU); DA-26 hai run 40k; DA-30 stage 1 300 bước; **pair60k ba run đang chạy** trên Colab A100 (khoảng 4–5k/60k bước) | `tray/pair60k/*/*/{metrics.jsonl, launch.json, vm-logs/}`, `colab/batch-*` | Có, đang chạy |
| Probe | Chưa có (DA-09 dời sau demo) | | Chưa chạy |
| Eval | Tray C trên SimReady: **20/240 = 8,3 %** (Wilson 5,5–12,5 %), mức 0 5/30; funnel và nhãn lỗi theo mức; lệch đích trung vị 10–11 cm. two_table với checkpoint tác giả 6/10 | `docs/he/tray.md` §16.6; output 11 GB trên `rtx3060`; `simple/s103/.../summary.json` | Có (sơ bộ, dev) |
| Failure→Data | Tray: cụm `L-PLACE-POSE` 131/240 → 262 lần sinh → 229 ghi → 177 giữ → 160 dùng → C+ đã train, **chưa eval**. two_table: 3 cụm đọc bằng mắt, đều "unknown" | `docs/he/tray.md` §17, `docs/he/two-table-diagnosis.md` | Làm tay, chưa có `EvidenceCard` |
| Chi phí | Thực đo khoảng **$15,3** so với ước tính khoảng $186. Số dư Colab 500 → khoảng 475 CU | `docs/g0/ledger/*.csv`, `sites/local/runs/**/ledger.jsonl`, `colab/batch-*/*.jsonl` | Có, thiếu pair60k |
| Quyết định | `Decision` JSON của tray, chưa ký | `configs/runplans/tray/*.decision.json` | Có |

Mọi tỉ lệ thành công là **sơ bộ, trên tập dev**, như đội đã ghi.

## 5. Tham khảo sản phẩm

Đã đối chiếu với tài liệu của từng sản phẩm.

| Sản phẩm | Mẫu giao diện mượn | Trang của console |
|---|---|---|
| [LeRobot Dataset Visualizer](https://github.com/huggingface/lerobot-dataset-visualizer) | Video đồng bộ với đồ thị state và action trên một thanh thời gian; panel lọc episode bất thường (ít chuyển động, giật, độ dài lạ); histogram độ dài episode | Episode, Nguồn, Agent |
| [Voxel51 FiftyOne](https://docs.voxel51.com/user_guide/app.html) | Lưới thumbnail có lớp nhãn; lọc theo trường, lưới cập nhật ngay; histogram theo view; panel đánh giá model có ma trận nhầm lẫn | Nguồn, Episode, Eval |
| [Cleanlab Datalab](https://docs.cleanlab.ai/stable/tutorials/datalab/image.html) | Báo cáo mở đầu bằng bảng loại vấn đề → số lượng, sau đó mỗi loại một mục với ví dụ tệ nhất | Agent QA/QC, Pipeline |
| [Foxglove](https://docs.foxglove.dev/docs/visualization/panels/state-transitions) | Panel chuyển trạng thái: mỗi bước là một làn màu theo thời gian, có thanh phát | Eval (một rollout), Episode |
| [Rerun](https://rerun.io/docs/concepts/visualization/blueprints) | Log văn bản đặt cạnh video và đồ thị, chung một thanh thời gian | Episode, Eval |
| Weights & Biases | Bảng run ghim cột, sắp theo giá trị cuối/min/max; panel loss; system metrics GPU; đồ thị lineage dataset → run → checkpoint; report trộn biểu đồ và lời bình | Training, Tổng quan |
| [W&B Weave · so sánh eval](https://docs.coreweave.com/products/wandb/weave/guides/evaluation/compare_evals.md) | Thẻ điểm so với baseline, huy hiệu tăng giảm xanh/đỏ; bảng từng ví dụ hai bên cạnh nhau | Eval (C so với C+) |
| [Langfuse](https://langfuse.com/changelog/2025-03-19-new-trace-view) | Trace của agent dạng cây / dòng thời gian / đồ thị; thời gian và chi phí cộng dồn theo nhánh, tô vàng/đỏ theo tỉ trọng | Agent QA/QC, Chi phí |
| [Dagster](https://dagster.io/docs/guides/operate/webserver) | Trang lần chạy: Gantt thời lượng các bước ở trên, log sự kiện có lọc ở dưới, chuyển giữa log có cấu trúc và stdout thô, tải log | Pipeline, Log |
| [Airflow Grid](https://airflow.apache.org/docs/apache-airflow/stable/ui.html) | Ma trận bước × lần chạy, ô tô màu, bấm ô mở log | Pipeline |
| [GitHub Actions](https://docs.github.com/en/actions/how-tos/monitor-workflows/use-the-visualization-graph) | Đồ thị job có biểu tượng trạng thái trên từng nút, bấm nút mở log | Tổng quan (vòng flywheel) |
| [ClearML](https://clear.ml/docs/latest/docs/webapp/webapp_workers_queues/) | Tab worker: bảng máy với job đang chạy, bấm máy xem CPU, GPU, VRAM; tab hàng đợi | Máy và Job |
| [SkyPilot](https://skypilot.ai/blog/announcing-skypilot-0.10.0) | Mỗi job hiện YAML, lệnh chạy, git commit, log trực tiếp | Máy và Job |

## 6. Nguyên tắc thiết kế (bản 0.3) [Đề xuất]

> Bản 0.5: nguyên tắc 2 (sáng là mặc định), 5 (ngăn trượt Cách làm) và 7 (không dùng sankey) được thay bằng mục 15.1b.

Bản 0.3 thay mục này sau khi Hiếu chê bố cục của mockup v2/v3 (tối, dày, ba cột, xấu). Việc đánh giá lại do model Fable làm (11/11). Chuẩn hình thức là trang **Egocentric Explorer** mà Hiếu đã dùng và thích.

1. **Nhìn được dữ liệu thật.** Mỗi dataset có ảnh đại diện. Mỗi episode có video, dải khung hình và đồ thị tín hiệu. Thẻ số liệu không thay được việc xem dữ liệu.
2. **Sáng là mặc định, có công tắc tối.** Dùng lại token của Egocentric Explorer:
   - nền `#f6f7f5`, khung `#ffffff`, viền `#dde2df`, chữ `#1c2321`, chữ phụ `#5d6a66`, nhấn `#2f7d5b`;
   - pass dùng màu nhấn, flag `#b7791f`, reject `#c0392b`, đang chạy `#2f6fd1`, chưa chạy dùng chữ phụ;
   - mỗi kiểu dữ liệu một màu cố định: egocentric cam, teleop xanh dương, S1 xanh lá, S2 tím. Màu giữ nguyên ở thẻ, biểu đồ và lineage.
3. **Chữ đọc được trên máy chiếu.** Thân chữ 15 px, chữ phụ 13 px; 12 px chỉ dùng cho meta trong bảng. Số dùng `tabular-nums`. Chế độ trình chiếu tăng gốc lên 17 px. Nội dung rộng tối đa 1 320 px.
4. **Mỗi biểu đồ trả lời một câu hỏi.** Tiêu đề biểu đồ là câu hỏi đó. Bấm vào biểu đồ thì lọc bảng bên dưới. Biểu đồ không để tên băm làm nhãn; dùng tên người đọc được, băm để phụ.
5. **Cách làm · Log · Nguồn hiện khi cần**, không chiếm một cột cố định:
   - dòng nguồn nhỏ dưới mỗi thẻ;
   - nút "Cách làm" ở đầu trang mở ngăn trượt 480 px;
   - trang dataset và trang run có tab "Cách làm · Log" riêng.
6. **Một mạch đi xuống:** trung tâm dữ liệu → dataset → episode, hoặc tổng quan → run → log. Có breadcrumb `Dữ liệu › S70 › episode 278`.
7. **Không dùng sankey.** Lineage vẽ thành các cột theo tầng (Thô → Pipeline → Release/Export → Cut → Run), di chuột vào một nút thì sáng đường tổ tiên và con cháu. Failure→Data vẽ thành chuỗi bước đánh số.
8. **Trung thực:** số sơ bộ gắn "sơ bộ · dev", số ước tính gắn "ước tính", số trích từ tài liệu ghi tài liệu và mục. Dòng minh hoạ có nhãn "minh hoạ" và không có trên bản chạy thật.

## 7. Kiến trúc thông tin (bản 0.3)

> Bản 0.5: sáu tab trên thanh đầu được thay bằng sidebar trái theo nhóm và panel phải bốn tab (mục 15.1b). Các mức xem dữ liệu dưới đây giữ nguyên.

Bỏ menu trái và cột phải. Thanh đầu có: logo, sáu tab **Tổng quan · Dữ liệu · Agent · Training · Eval · Vòng lặp** đi theo vòng flywheel từ trái sang phải, chọn task, chip máy (Colab, `rtx3060`; bấm mở danh sách job), công tắc sáng/tối. Mức thứ hai là tab trong trang, giống Gallery / Quality / All clips của Egocentric Explorer.

| Tab | Trang con | Tình huống |
|---|---|---|
| Tổng quan | Dải các bước flywheel, chuỗi vòng tray, việc đang chạy, chờ duyệt, hoạt động | T1 |
| Dữ liệu | **Trung tâm dữ liệu** (P0: thẻ dataset nhóm theo kiểu, bảng 60 dòng, lineage) → **Dataset** (Gallery · Chất lượng · Tất cả episode · Lineage · Cách làm · Log) → **Episode** (robot hoặc egocentric). Pipeline 6 tầng (P3) là một tab của trung tâm dữ liệu | T2 |
| Agent | Bảng điểm bench, phát hiện trên run thật, tầng LLM, hàng chờ duyệt | T3 |
| Training | Bảng run có cột **Máy**, biểu đồ loss, trang run (cấu hình, log, checkpoint) | T4, T8 |
| Eval | Funnel theo mức, nhãn lỗi, sai số đặt, so cặp C/C+ | T5 |
| Vòng lặp | Failure→Data (chuỗi bước, cụm lỗi, 12 bước), Chi phí, Quyết định | T6, T7 |

Máy và Job (P12) thành chip trên thanh đầu kèm danh sách job. Log (P13) thành tab "Cách làm · Log" của từng run, từng dataset. Probe P1–P4 có chỗ trong Training nhưng hiện "chưa chạy" tới khi DA-09 có số.

**Mức "xem được tới đâu" của dữ liệu** (bản 0.3), áp cho P0:

| Mức | Dataset | Xem được |
|---|---|---|
| Đủ | S70 (425 ep), ALL (606), egocentric team_tray 132 và egodex 185, các nguồn `src_*` | Ảnh đại diện, video, dải khung hình, tín hiệu action/state, phép kiểm QA từng episode |
| Bảng và thống kê | psi-data two_table 99, hug 94 (phần lớn còn nén), bộ điều kiện eval | Bảng episode, thống kê; video sau khi giải nén |
| Chỉ metadata | Mọi dataset chỉ có trên `rtx3060` (5 release S1, S2 prod-1105, output eval, bản sao lỗi cấy) | Thẻ "chỉ có trên rtx3060" kèm lệnh `rsync` kéo `meta/` |
| Thiếu | 3 dataset có trong tài liệu nhưng không có trên đĩa | Thẻ đỏ "không có trên đĩa" |

Bản sao có lỗi cấy được liệt kê và gắn `injected_defect`, không bao giờ trộn vào trang release. `DefectManifest` không được đánh chỉ mục.

## 8. Yêu cầu từng trang

Mỗi trang ghi: mục đích, KPI, biểu đồ (loại → file nguồn → trường), bảng, đi xuống, ba lớp Cách làm/Log/Kết quả, trạng thái rỗng. "Có" là dữ liệu thật đã có; "Chưa" là trang hiện trạng thái rỗng tới khi có.

### P1 · Tổng quan

- **Sơ đồ vòng flywheel** kiểu đồ thị job của GitHub Actions: 8 nút (Nguồn, Pipeline, Agent, Release, Training, Eval, Failure→Data, Chi phí). Mỗi nút có trạng thái, số chính, thời điểm cập nhật; bấm mở trang. Có.
- **KPI:** episode qua QA; success rate mới nhất kèm CI; job đang chạy theo máy; CU còn lại; chi phí thực đo so với ước tính; số việc chờ duyệt. Có.
- **Dòng hoạt động gần đây:** job bắt đầu/xong, release mới, eval xong, quyết định chờ ký. Đọc từ ledger và cu_watch. Có.
- **Thẻ "câu chuyện tray"**: chuỗi bước đánh số thu nhỏ của P9 (bản 0.3: bỏ sankey).

### P0 · Datasets: danh mục toàn hệ thống (bản 0.2)

Hiếu yêu cầu thấy **toàn bộ dataset của cả hệ thống** (11/11). **[Đã chốt]** Trang này liệt kê mọi tập dữ liệu ở mọi giai đoạn và mọi nơi lưu. Kiểm kê 11/11 có 60 dataset và 50 cạnh lineage. Bản kiểm kê ở dạng JSON là đầu vào mẫu cho bộ đánh chỉ mục.

- **Phạm vi một "dataset":** nguồn thô, nguồn pipeline (`src_*`), export egocentric (`egx_*`, human1m v3), release đóng băng (`tray_s1_*`), cut cho training (C, T160, C_PLUS, ALL, S70, N20…), bản sao lỗi cấy (`bench-*`), bộ điều kiện eval, bản trên HF, tarball trên Drive.
- **KPI theo loại dữ liệu** (dữ liệu duy nhất, không tính cut và bản sao):

  | Loại | Episode | Khung | Giờ |
  |---|---|---|---|
  | Egocentric | 379 | 104 261 | 0,97 |
  | Teleop (psi-data) | 193 | 105 452 | 0,59 |
  | S1 hiện hành | 770 | 1 097 063 | 6,09 |
  | S2 | 843 (669 qua QA) | 1 468 949 | 8,16 |
- **Sơ đồ lineage** (bản 0.3) vẽ theo cột tầng, từ nguồn tới run; di chuột vào một nút thì sáng đường tổ tiên và con cháu. Ví dụ: video đội → `src_8058` → `egx_7b43` → stage 1 B → B_ALL, B_70; `tray_s1_41899` + `4a8f` → ALL → S70 → C_70, B_70. Bấm một nút để lọc danh mục.
- **Danh mục**, mỗi dòng một dataset: id, loại, kiểu dữ liệu, task, episode, khung, giờ, định dạng (LeRobot v2.1/v3, định dạng Ψ₀, video thô), licence và `data_class`, nơi lưu (laptop, `rtx3060`, HF, Drive), dung lượng, cha, run đã dùng, QA, trạng thái. Trạng thái gồm hiện hành, bị thay, bản trùng, bản thử, thiếu. Có lọc theo kiểu dữ liệu, task, nơi lưu, trạng thái. Bấm dòng thì ngăn phải hiện đủ trường, cha và con.
- **Biểu đồ:** số dataset theo loại × trạng thái; dung lượng theo nơi lưu và kiểu dữ liệu.
- **Khoảng trống và điểm lệch** tự phát hiện, ví dụ:
  - release S2 669 episode được quyết 5/11 nhưng không có trên đĩa;
  - `report/egocentric.json` của `src_8058` cũ hơn `qa/egocentric.jsonl`;
  - manifest S1 ghi licence `unknown` trong khi HF ghi CC BY 4.0;
  - bản trùng chiếm khoảng 15 GB trên `rtx3060`.
- **Cách làm:** bộ đánh chỉ mục đọc `meta/info.json` (LeRobot), manifest release, `source.json`, `batch_summary.json`, `launch.json` (`data.root_dir`). Với `rtx3060` thì đọc từ một bản kiểm kê kéo về (mục 17.2), không SSH lúc chạy.

### P2 · Nguồn dữ liệu

- **Bảng nguồn:** id, loại (egocentric / teleop / synthetic), licence, `data_class`, số episode, giờ, ngày nạp, trạng thái pipeline. Đọc `source.json`, `episodes.jsonl`. Có.
- **Biểu đồ:** cột chồng episode theo nguồn và quyết định QA; histogram độ dài clip; phân bố fps và độ phân giải. Đọc `report/egocentric.json`, `human1m/*/summary.json`. Có.
- **Lưới thumbnail** kiểu FiftyOne: mỗi ô một clip, viền màu theo pass/flag/reject, lọc theo lý do QA. Thumbnail tạo một lần bởi bộ đánh chỉ mục (mục 11). Có cho egocentric; S1 cần đọc từ `rtx3060` hoặc bản sao.
- **Cách làm:** `fw egocentric ingest`, `deid` (YuNet), `pose`, `annotate`; config `configs/data/egocentric.yaml`; tài liệu `docs/g0/egocentric.md`.

### P3 · Pipeline 6 tầng

- **Lưới trạng thái** kiểu Airflow: hàng là 6 tầng (Ingest, Normalize, Annotate, QA, Release, Export), cột là nguồn hoặc lô. Ô màu theo trạng thái, ghi số episode qua tầng. Bấm ô mở ngăn log của job đã chạy tầng đó. Có cho egocentric và S1.
- **Phễu theo tầng:** số episode còn lại sau mỗi tầng (ví dụ egocentric 379 → 325 → 317 export; S1 610 → 542 → 541 → 429).
- **Bản đồ nhiệt phép kiểm × quyết định:** 17 phép kiểm D2–D8 của robot, các phép kiểm egocentric (`deid_gate`, `min_frames`, `hand_pose_nan`, `segment_ambiguous`…). Ô là số episode trượt. Bấm ô lọc danh sách episode. Đọc `qa/egocentric.jsonl` (`checks[name, value, threshold, passed]`). Có.
- **Bảng lý do QA** kiểu Cleanlab: lý do → số lượng → 5 ví dụ tệ nhất.
- **Gantt thời lượng job** của mỗi tầng, đọc `ledger.jsonl` (`quantity` cpu_seconds). Có.
- **Cách làm:** lệnh `fw data ingest|qa|release|report`, `fw egocentric …`; `threshold_version` (ví dụ `qa-1@fb6ddaf9f48c`, `ego-1@024bb1b5a624`) và nội dung ngưỡng từ `configs/data/qa.yaml`; tài liệu `docs/g0/data-pipeline.md` §1.
- **Log:** `human1m-logs/*.log`, `egocentric-ea/*/ea.log`, `egocentric-deid-e2e/run.log`, dòng `note` của ledger.

### P4 · Episode

- **Trình phát:** video (bản đã che mặt) cùng thanh thời gian với đồ thị state/action hoặc pose tay, làn các đoạn (segment) đã gán nhãn, và đánh dấu khung lỗi QA. Kiểu LeRobot visualizer và Foxglove.
- **Thẻ QA:** từng phép kiểm với giá trị, ngưỡng, kết quả; quyết định; người duyệt và nhãn duyệt (`sheet.jsonl`).
- **Lineage:** nguồn → episode → release nào chứa nó → run nào train trên nó.
- **Video egocentric thô (chưa che mặt) không bao giờ được phục vụ.** Chỉ đọc file sau bước `deid`.

### P5 · Release và export

- Danh sách release: hash, số item, nguồn góp, licence gộp, release cha, nơi lưu (local, `rtx3060`, HF). Cây lineage release.
- Checklist export LeRobot v2.1 (18 mục, trượt mục nào) và kiểm loader Ψ₀ 3/3.
- Biểu đồ: số episode theo release và theo nguồn; tỉ lệ phần trăm từng phần (S70, ALL).
- Cách làm: `fw data release`, `configs/data/export_checklist.yaml`, `docs/g0/export-v21.md`.

### P6 · Agent QA/QC (trọng tâm)

Bản 0.5: phần hỏi đáp của Agent là một chatbot gọi công cụ đọc dữ liệu thật (mục 15.1b), không phải câu trả lời viết sẵn. Hai tầng dưới đây không đổi.

Agent có **hai tầng tách bạch** theo design 27/10 §9: tầng code (phép kiểm cố định, là cổng) và tầng agent (model tự host, viết diễn giải và xếp hạng). Mọi biểu đồ có hai cột "code" và "agent".

- **Bảng điểm bench lỗi cấy:** theo mã lỗi (D1–D8, T1–T8, R1–R2): số cấy, code bắt, agent bắt thêm, báo nhầm trên bản sạch, precision. Có cho lần chạy trên log giả (30/30, 0/40) từ `docs/g0/defect-bench.md`; khi `bench_result.json` có thì đọc file.
- **Báo cáo agent** kiểu Cleanlab: bảng phát hiện theo loại → số lượng → ví dụ; mỗi phát hiện có bằng chứng (episode, khung, giá trị), mức tin cậy, đề xuất. Đọc `reports.jsonl` (`AgentReport`: `findings`, `facts`, `estimates`, `model`). Chưa có output thật trong `fwdata`; trang hiện "chưa chạy" và lệnh `fw agentqa run`.
- **Trace của một lần chạy agent** kiểu Langfuse: cây bước (đọc input, gọi công cụ, kết luận), thời gian và token mỗi bước, model và hash prompt. Cần agent ghi trace (mục 13, việc cần thêm ở lõi).
- **Hàng chờ duyệt:** phát hiện chưa có quyết định của người. Nút Đồng ý / Bác bỏ / Sửa, bắt buộc lý do khi bác bỏ. Ghi thành `AgentReview` / `FindingDecision` qua lệnh `fw agentqa review` (mục 11.3, đường ghi).
- **Chạy agent:** chọn model (chỉ model tự host: Nemotron qua NIM, Qwen3.5-4B, Echo), chọn đầu vào (lô mới, log training, bản sao lỗi cấy), chọn máy. Ước tính thời gian và chi phí trước khi chạy (`fw agentqa estimates`).
- **Agent đọc log training:** bảng chẩn đoán T1–T8 cho từng run, kèm mã bị bỏ qua và lý do (ví dụ cờ T1, T2, T8 trên 3 fine-tune).
- **Cách làm:** `configs/eval/agentqa/agent.yaml`, `prompts/system.md` (hiện nội dung và hash), `docs/g0/agent-qa.md` §2.
- **Ràng buộc:** agent không đọc đáp án `DefectManifest`; console không gửi dữ liệu tới model hosted bên ngoài.

### P7 · Training

- **Bảng run** kiểu W&B: job, nhánh (C, C+, B_70, C_70, C_ALL…), release dùng, **máy** (Colab A100 / L4 / rtx3060 / laptop), trạng thái, bước hiện tại / tổng, loss cuối, val loss, CU đã tiêu, thời gian; sắp và lọc mọi cột. Đọc `launch.json`, `fetched.json`, `metrics.jsonl`, `vm-logs/report.json`.
- **Biểu đồ của một run hoặc so nhiều run:**
  - loss train (thô mờ + đường làm mượt EMA) và các điểm val;
  - loss theo nhóm action (`hand`, `arm`, `torso_rpy`, `height`, `base_velocity`, `turn`, `target_yaw`) dạng nhiều đường nhỏ;
  - loss theo vị trí trong chunk (`loss_by_chunk_pos`) dạng heatmap theo bước;
  - grad norm (action, VLM), learning rate;
  - throughput, VRAM, thời gian tường;
  - `pred_std` so với `target_std` (dấu hiệu sụp dự đoán).
  
  Có cho pair60k (ba run đang chạy) và các run đã lưu trong `fwdata/archive/`.
- **Pha của VM:** setup, tải checkpoint, kiểm sha256, train, eval định kỳ, đẩy checkpoint, kèm thời lượng (`vm-logs/report.json`).
- **Chẩn đoán train T1–T8** (khi có `TrainDiagnosis`); probe P1–P4 "chưa chạy".
- **Cách làm:** `argv` đầy đủ từ `launch.json`, `configs/models/psi0-stage3.yaml`, RunPlan và `lock_sha256`, commit; `docs/he/train-pipeline.md`.
- **Log:** `train.log` (đuôi, tự cập nhật khi job còn chạy), `setup.log`, `nvidia-smi-q.txt`, `pip-freeze`, `core-debug-*.log`.

### P8 · Eval

- **Chọn task và lần eval.** Lọc mức (0, 1, 2), renderer, tập (dev; holdout có ổ khoá).
- **KPI:** success theo mức với Wilson và bootstrap CI; số rollout bị loại vì lỗi hạ tầng; thời gian mỗi episode; số request `/act`.
- **Funnel theo bước của task** (tray 7 bước, two_table 6 bước), theo từng mức và gộp. Có cho eval C (§16.6).
- **Cột chồng nhãn lỗi theo mức** (`L-PLACE-POSE`, `L-TIMEOUT`, `L-TRAY-TILT`, `L-PART-DROP`, `L-ONE-HAND`). Có.
- **Sai số tư thế cuối:** histogram/box khoảng cách (cm) và góc (°) so với dung sai 5 cm, 10°; scatter khoảng cách × góc tô theo kết quả. Có ở mức tóm tắt; cần `outcomes.jsonl` để có từng lượt.
- **Lưới điều kiện:** mỗi ô một điều kiện (seed, mức), màu theo kết quả; bấm mở rollout. Cần `outcomes.jsonl`.
- **So cặp hai checkpoint** kiểu W&B Weave: B − C trên cùng điều kiện, CI bootstrap, McNemar, bảng điều kiện bất đồng. Khung có sẵn từ `eval_results`; số thật khi pair60k xong.
- **Một rollout:** video, làn bước kiểu Foxglove (`scorer_steps`), log client, request `/act`.
- **Cách làm:** `flywheel_psi0.tray.eval_batch`, `configs/eval/scorer/tray.yaml` (`scorer_version`), `configs/sim/tray*.yaml`, luật đọc kết quả `docs/he/tray.md` §9, §16.1.
- **Log:** `client.log`, `proxy.log`, `server-*.log`, `runs.jsonl`.

### P9 · Failure→Data

- **Chuỗi bước của vòng tray** (bản 0.3, thay sankey): 240 rollout → 131 `L-PLACE-POSE` → 262 lần sinh có chủ đích → 229 ghi → 177 giữ sau lọc → 160 dùng → C+ (40k bước) → eval C+ (chưa chạy). Có (từ §17).
- **Bảng cụm lỗi:** bước hỏng, kiểu lỗi, mức, số thành viên, chẩn đoán (hệ thống / dữ liệu / chỉ ghi nhận), video đại diện. Có cho tray (một cụm, làm tay) và two_table (3 cụm "unknown").
- **Thẻ bằng chứng** theo `EvidenceCard` khi lõi sinh được; trước đó hiện bảng bằng chứng làm tay từ tài liệu, gắn nhãn "làm tay".
- **Can thiệp và ngân sách:** loại can thiệp, số lượng, chi phí ước tính, lợi ích kỳ vọng, ba thanh ngân sách. Nút duyệt ghi `Decision` (mục 11.3).
- **Cách làm:** spec v10.5 §5–8; 12 bước của thuật toán, bước nào đã chạy, bước nào chưa có code (`flywheel.loop` mới là khung).

### P10 · Chi phí

- **Cột ước tính so với thực đo** theo story, theo hoạt động, theo loại tài nguyên. Đọc `docs/g0/ledger/*.csv` và `sites/local/runs/**/ledger.jsonl`. Có.
- **Đường tiêu CU của Colab** theo thời gian và theo phiên, cùng trần (`cap`) và số dư. Đọc `colab/batch-*/*.jsonl`. Có.
- **Theo máy:** CU Colab, giờ GPU `rtx3060`, giờ CPU laptop, giờ người.
- **Sai số dự báo chi phí** (thực đo / ước tính) theo loại job.
- Bút toán chỉ thêm; dòng thực đo trỏ về dòng ước tính.

### P11 · Quyết định

- Nhật ký `Decision`: loại, đối tượng, kết luận, số đo, tiêu chí, người ký, quyết định bị thay thế. Đọc `configs/runplans/**/*.decision.json`. Quyết định chưa ký nổi lên đầu và lên chuông.
- RunPlan đã đóng băng: hash, nhánh, ngân sách (`*.lock.json`).

### P12 · Máy và Job

- **Thẻ máy** kiểu ClearML: Colab (mỗi phiên: GPU, trạng thái, CU đã tiêu, trần), `rtx3060` (GPU, số worker đang dùng trên 22, đội khác có dùng không), laptop. Đọc `colab/batch-*/<session>.json`, `guard.jsonl`; với `rtx3060` cần một lệnh đọc trạng thái qua SSH (chỉ đọc).
- **Dòng thời gian job** kiểu Gantt: training, eval, sinh dữ liệu, QA, theo máy.
- **Lập job** (mục 10).

### P13 · Log

- Tìm trong mọi log đã đánh chỉ mục: theo job, máy, thời gian, mức (lỗi/cảnh báo), từ khoá.
- Xem log: chế độ có cấu trúc (JSONL thành bảng) và thô; nhảy tới dòng lỗi; tải về.
- Thanh tiến trình tqdm trong `train.log` được gộp về dòng cuối của mỗi đoạn, để file 900 KB đọc được.

## 9. Mô hình dữ liệu của console [Đề xuất]

Kiểm kê cho thấy một khoảng trống: run dir trong `sites/local/runs/` chỉ có `ledger.jsonl`, còn sản phẩm của job nằm ở các cây riêng (`pipeline/`, `tray/`, `colab/`, `he/`), và không có gì nối chúng. Console cần một lớp chung gọi là **bước chạy** (`StepRun`):

| Trường | Nghĩa | Lấy từ |
|---|---|---|
| `step` | Bước flywheel: source, ingest, normalize, annotate, qa, release, export, agentqa, train, eval, failure_data, cost | Loại job |
| `run_plan_id`, `job_id` | Khoá nối | ledger, `launch.json`, `metrics.jsonl`, decision JSON |
| `machine` | `colab:<gpu>`, `rtx3060`, `laptop` | `colab/*/<session>.json`, đường dẫn, `launch.json` |
| `status`, `started`, `ended` | Trạng thái và thời gian | ledger, `fetched.json`, cu_watch |
| `method` | Lệnh, config và phiên bản, module, commit, mục tài liệu | `launch.json` (`argv`), `threshold_version`, bảng ánh xạ tĩnh bước → tài liệu |
| `logs[]` | Đường dẫn, loại (có cấu trúc / thô), kích thước | quét thư mục của job |
| `results[]` | Artifact và kiểu hợp đồng (`QAReport`, `TrainingMetric`, `DatasetReport`, `Decision`…) | quét thư mục, tên file |
| `metrics` | Vài số tóm tắt cho bảng và thẻ | đọc artifact |

Tên trường của artifact lấy đúng từ `flywheel-contracts` (`entities.py`, `artifacts.py`, `agentqa.py`, `training.py`, `evidence.py`, `v0.py`). Console không đặt tên mới cho dữ liệu khoa học.

Số chỉ có trong tài liệu Markdown (eval C §16.6, Failure→Data §17, bench `defect-bench.md` §6) được đưa vào một file **dữ liệu trích dẫn** có cấu trúc, mỗi dòng ghi tài liệu và mục nguồn. Khi lõi sinh artifact thật thì dòng trích dẫn được thay bằng file.

## 10. Lựa chọn máy cho training và eval [Option]

Hiếu muốn có lựa chọn máy ảo (Colab…) và máy vật lý. Có hai cách hiểu, khác nhau về rủi ro:

| | **A · Xem, so sánh, sinh lệnh** | **B · Chạy từ web** |
|---|---|---|
| Web làm gì | Mỗi run ghi máy; lọc và so tốc độ, chi phí giữa máy. Form "lập job": chọn máy → web tạo RunPlan nháp, dòng ledger ước tính, và **lệnh chính xác** cho máy đó. Hiếu chạy lệnh | Như A, thêm nút "Chạy" sau khi Hiếu duyệt. Web gọi `colab_train` (Colab) hoặc SSH `nohup setsid` (`rtx3060`), theo dõi log, tự dừng VM khi job xong |
| Đúng luật hiện có | Đúng: "job GPU chỉ Hiếu chạy, từ RunPlan"; thiết kế của Châu cũng để ngoài phạm vi việc chạy job từ web | Cần Hiếu sửa luật; thêm cơ chế duyệt, trần CU, dừng VM khi xong (quy định 11/11) |
| Công sức tới 17/11 | Thấp | Cao; thêm rủi ro tiêu CU ngoài ý muốn và đụng job của đội khác trên `rtx3060` |

**Đề xuất:** làm A trước, thiết kế form và dữ liệu sao cho B chỉ là thêm một nút sau này.

## 11. Kiến trúc kỹ thuật [Đề xuất]

### 11.1 Thành phần

| Thành phần | Chọn | Lý do |
|---|---|---|
| Bộ đánh chỉ mục | Lệnh Python `fw console index`: quét `fwdata/`, `configs/`, `docs/`, dựng `StepRun` và các bảng tóm tắt, ghi `fwdata/console/index/*.json`; tạo thumbnail và bản rút gọn của `metrics.jsonl` | Không cần DB server (03 mục 2.4); chạy lại được bất cứ lúc nào |
| Server | Python stdlib, chạy tại `127.0.0.1`. Phục vụ trang tĩnh và JSON chỉ mục. Hỗ trợ **HTTP Range**, vì `python -m http.server` không có Range nên video không tua được. Có vài API đọc: tín hiệu một episode (đọc một parquet theo yêu cầu, hạ 50 → 10 Hz, lưu cache), dải khung hình, đuôi log và đoạn log theo dòng, `metrics.jsonl` lấy mẫu thưa (tối đa 2 000 điểm mỗi chuỗi) | Đọc file lớn theo nhu cầu; video phục vụ tại chỗ, không chép, không chuyển mã; không mở ra mạng |
| Ảnh đại diện | `cv2` (OpenCV có trong môi trường uv) cắt khung giữa, rộng 320 px, JPEG q70, khoảng 12 kB một ảnh; dải 12 khung tạo khi cần | Máy không có ffmpeg; ước tính khoảng 75 MB cho 1 031 episode robot |
| Giao diện | HTML + JavaScript thuần (module ES), routing bằng hash. ECharts và three.js r147 (cho tay 3D egocentric) **đóng gói sẵn trong repo, không CDN** | Máy đội không có Node; không cần bước build; chạy offline; Egocentric Explorer hiện kéo three.js từ CDN nên sẽ hỏng khi mất mạng |
| Đường ghi (bản 0.4) | Bộ chạy việc của server chỉ gọi lệnh `fw` có sẵn theo một danh sách cho phép (mục 15.1a). Mỗi việc có `job.json` và `log.txt` trong `fwdata/console/jobs/`; mọi ghi là thêm dòng | Giữ một đường ghi; không có lệnh tự do từ trình duyệt |

### 11.2 Vị trí mã

Đề xuất thư mục `console/` ở gốc repo (server, giao diện, bộ đánh chỉ mục), lệnh `fw console` đăng ký qua entry-point `flywheel.commands`. Console chỉ đọc file và gọi lệnh, không import adapter vào lõi; luật import của 03 mục 7.3 không đổi. Cần story và "Phạm vi file" trước khi code (07 mục 3.1).

### 11.3 Quan hệ với PR #72 của Châu [Option]

| | **O1 · Xây trên PR #72** | **O2 · Console nhẹ đọc file thật** |
|---|---|---|
| Stack | FastAPI, Postgres, `fwsync`, React + Vite, MSW | Python + JS thuần + ECharts, đọc file |
| Dữ liệu | Mock trước (`mock/demo-17-11/`); thật khi `fwsync` nạp được artifact | Thật ngay |
| Điều kiện | PR #72 phải sửa 10 lỗi đã review và được merge; cần Node, Postgres trên máy | Không cần gì thêm |
| Giữ lại từ Châu | Toàn bộ | Danh sách màn hình, luật nghiệp vụ, tên component (`StepFunnel`, `EmptyState`, `SkippedList`, `MockBadge`…), hình dạng response |

**Đề xuất:** O2 cho demo 17/11, giữ tên và luật của Châu để sau này có thể trỏ giao diện sang API của Châu.

## 12. An toàn dữ liệu

- Server chỉ nghe `127.0.0.1`. Không đăng lên GitHub Pages, không artifact công khai.
- Không gọi API model hosted. Agent chỉ dùng model tự host (R6).
- Không đọc `vault/`. Không hiện đáp án `DefectManifest` ở trang agent; bench chỉ hiện điểm.
- Video egocentric chỉ phục vụ bản sau `deid`.
- Mỗi trang có nhãn licence của dữ liệu đang hiện (EgoDex NC-ND, psi-data chưa rõ, video đội `team-internal`), để ảnh chụp màn hình không vô tình bị đăng ra ngoài.
- Thư mục chỉ mục `fwdata/console/` nằm trong `fwdata/`, không commit.
- **Chế độ trình chiếu** (bản 0.3, đề xuất; chờ Hiếu chốt ở mục 16): `fw console index --public-only` dựng một chỉ mục riêng chỉ từ dòng `data_class == public`. Nhờ vậy dữ liệu nội bộ không tới trình duyệt. Mở thêm `?present=1` để chữ 17 px, ẩn ngăn Cách làm và đường dẫn tuyệt đối. Các nhãn "sơ bộ · dev" vẫn giữ.

## 13. Việc lõi cần bổ sung để console đầy đủ

Console hiện được cái đã có. Các mục dưới làm trang đầy đủ hơn; mỗi mục cần story riêng và chủ sở hữu làn.

1. Agent QA/QC ghi trace (bước, thời gian, token) cùng `AgentReport`; chạy bench trên bản sao lỗi cấy của psi-data; chạy agent với Nemotron.
2. Kéo output eval C, C+ (`runs.jsonl`, `outcomes.jsonl`, video) từ `rtx3060` về, hoặc cho bộ đánh chỉ mục đọc qua SSH (chỉ đọc).
3. Ghi CU của Colab vào `LedgerEntry` (hiện chỉ có trong cu_watch).
4. Ghi máy chạy (`machine`) vào RunPlan hoặc `launch.json` của mọi job.
5. `EvidenceCard` thật từ `flywheel.loop` (hiện là khung).

## 14. Tiêu chí nghiệm thu

1. Tám tình huống T1–T8 ở mục 2 làm được trên console, mỗi tình huống không quá 4 cú bấm từ Tổng quan. Bản 12/11 nghiệm thu T1, T4, T6, T7 đủ; T2, T3, T5 ở mức tổng hợp (chưa mở từng clip, trace, video rollout); T8 sau demo.
2. Mỗi trang P1–P13 (bản 0.3: gom vào sáu tab, mục 7) có ba lớp Cách làm · Log · Kết quả; trang chưa có dữ liệu hiện "chưa chạy" kèm lệnh, không có số 0 giả.
3. Mỗi con số trên trang có nút nguồn dẫn tới file (hoặc tài liệu và mục, với dữ liệu trích dẫn).
4. Mở `metrics.jsonl` 6 MB và `train.log` 900 KB dưới 2 giây trên laptop.
5. Không request nào ra ngoài `127.0.0.1` khi dùng console (kiểm bằng tab Network).
6. Test Python cho bộ đánh chỉ mục chạy trên CPU với dữ liệu mẫu của `flywheel.testkit`; `ruff`, `mypy`, `pytest` sạch.

## 15. Kế hoạch

**Console nằm trong demo, phải sẵn sàng cho buổi chạy thử 12/11/2026.** **[Đã chốt 11/11]**

### 15.1 Bản cho chạy thử 12/11 (bản 0.3) [Đề xuất]

Bản 12/11 chỉ gồm các trang kể được câu chuyện demo trên dữ liệu thật đã có ở laptop. Từ bản 0.4, bản này chạy được pipeline egocentric và Agent QA/QC, nhập và xuất dữ liệu (mục 15.1a).

| Tab | Có trong bản 12/11 |
|---|---|
| Tổng quan | Dải các bước có ảnh thật, chuỗi vòng tray, việc đang chạy, chờ duyệt |
| Dữ liệu | Trung tâm dữ liệu với 60 dataset (thẻ, bảng, lineage). S70 và hai tập egocentric xem đủ tới episode. ALL và `src_*` có Gallery và bảng, có trang episode nếu kịp |
| Agent | Bảng điểm bench (số trích dẫn), phát hiện T1, T2, T8, tầng LLM "chưa chạy" kèm lệnh |
| Training | Bảng run có cột Máy, loss EMA, loss theo nhóm, pha VM, log |
| Eval | Funnel theo mức, nhãn lỗi, sai số đặt khay, ô C/C+ "chưa eval" |
| Vòng lặp | Chuỗi bước Failure→Data, cụm lỗi, 12 bước, Chi phí |
| Xử lý (bản 0.4) | Pipeline egocentric sáu tầng, nút chạy từng tầng, log trực tiếp, kết quả từng tầng |
| Cắt khỏi bản 12/11 | Tìm kiếm toàn cục, chuông, Quyết định, trang Máy, trang Log, lập job train hoặc eval, xem rollout, chỉnh giao diện tối |

### 15.1a Bổ sung bản 0.4: console chạy được việc [Đã chốt 11/11]

Hiếu cần quay video demo và muốn console làm được việc thật, không chỉ hiển thị. Bốn lựa chọn Hiếu đã chốt chiều 11/11:

| Câu hỏi | Chốt |
|---|---|
| Model của Agent QA/QC | Kéo Nemotron 3.5 Bolt E4B về Ollama trên `rtx3060`. Cùng model với config, nên không tính là phiên bản agent mới. Bản 0.5: tag thư viện `nemotron-3.5-bolt:e4b-q4_K_M` cần Ollama mới hơn 0.32.14 đang cài, nên đã kéo bản chính thức `hf.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-E4B-4GB:Q4_K_M` (6,2 GB trên đĩa, khoảng 9,6 GB VRAM khi nạp) |
| Việc chạy ở đâu | Laptop chạy các bước CPU (ingest, che mặt, pose E-B, QA, báo cáo, xuất). Bước cần model (gắn nhãn bước bằng RoboBrain, agent bằng Nemotron) gọi Ollama trên `rtx3060` qua một đường hầm SSH về `127.0.0.1`. Việc chỉ chạy khi người bấm nút |
| Xuất dữ liệu | Chỉ trên máy: shard LeRobot v3 (`fw egocentric human1m`) và zip metadata. Không đẩy lên HF |
| Nhập dữ liệu | Kéo thả video từ trình duyệt vào `fwdata/egocentric-raw/upload-<thời điểm>/`, hoặc chọn thư mục đã có trên máy |

**Bộ chạy việc.**
- Chỉ nhận các loại việc trong danh sách cho phép: `ego.ingest`, `ego.deid`, `ego.pose`, `ego.annotate`, `ego.qa`, `ego.report`, `ego.pipeline` (chuỗi các bước trên), `ego.human1m`, `agentqa.run`, `agentqa.review`, `export.zip`. Không nhận lệnh tự do.
- Che mặt phải xong trước mọi bước sau.
- Tối đa hai việc chạy cùng lúc trên laptop; việc gọi model chạy lần lượt.
- Agent dùng một bản sao config trong `fwdata/console/config/`, chỉ đổi `base_url` và tên model đang phục vụ; không sửa `configs/`.
- POST chỉ nhận từ chính console (kiểm `Host` và `Origin`). Đường dẫn phải nằm trong `fwdata/` (hoặc trong thư mục nhà, với thư mục nhập).

**Vòng flywheel trên Tổng quan.**
- Sáu khâu xếp thành một vòng: Thu thập → Xử lý và QA → Release → Training → Eval → Failure→Data.
- Mỗi khâu hiện trạng thái, task, việc đang chạy, vấn đề đang xử lý và cách xử lý, lấy từ `GET /api/status`.
- Khâu chưa có nguồn sống (eval, vòng lặp) ghi rõ "dữ liệu tĩnh".

**Dễ hiểu cho video.**
- Mỗi trang mở đầu bằng một câu hỏi và câu trả lời.
- Thuật ngữ có chú giải khi di chuột.
- Chế độ trình chiếu: chữ lớn, ẩn đường dẫn và ID, chỉ dữ liệu `public`.
- Thanh dẫn đường tám bước có lời dẫn cho từng bước.

**Lộ trình demo 4 phút:**
1. Tổng quan.
2. Trung tâm dữ liệu và lineage của S70.
3. S70 › Chất lượng › Gallery › một episode: phát video, kéo đồ thị.
4. Một episode egocentric có tay 3D.
5. Agent.
6. Training (ba run pair60k, cột Máy).
7. Eval.
8. Vòng lặp và chi phí.

**Gói việc cho Sonnet.** Các gói có file tách rời nên chạy song song được:

| Gói | Nội dung | Xong khi |
|---|---|---|
| 0 Hợp đồng (làm trước, 1 giờ) | `console/SCHEMA.md`, fixtures, `index.html`, `tokens.css`, `core.js` (router, thẻ, bảng, ngăn trượt), thư viện đóng gói | Khung sáu tab chạy trên fixtures, cả sáng và tối |
| 1 Chỉ mục dữ liệu | `console/indexer/{catalog,lerobot,egocentric,posters}.py` và test | S70 ra 425 dòng và 425 ảnh; catalog 60 dòng, 50 cạnh; pytest xanh |
| 2 Server | `console/server.py`, tín hiệu episode và test | Video trả 206 khi có Range; API episode dưới 300 ms và dưới 250 kB |
| 3 Giao diện dữ liệu | Trang trung tâm, dataset, episode robot; widget lineage, đồ thị tín hiệu, dòng thời gian | Đi từ trung tâm → S70 → episode; bấm đồ thị thì video tua theo |
| 4 Run | Chỉ mục runs, eval, cost; trang Training, Eval | Ba run pair60k có cột máy; funnel hiện 20/240 |
| 5 Trang câu chuyện | Chỉ mục pipeline, agent, loop; trang Tổng quan, Agent, Vòng lặp | Mọi số trên Tổng quan dẫn tới trang của nó; không có dữ liệu giả |
| 6 Egocentric | Trang episode egocentric, tay 3D với three.js đóng gói | Episode egocentric hiện được khi không có mạng |

**Lịch** (giả định chạy thử lúc 14:00 ngày 12/11 và Hiếu xem hai lần, mỗi lần 30 phút):

| Khi | Việc |
|---|---|
| 11/11 13:00–14:30 | Hiếu chốt; gói 0 |
| 14:30–18:30 | Gói 1–6 song song |
| 18:30–20:00 | Ghép trên dữ liệu thật, chạy chỉ mục lần đầu |
| 20:00–20:30 | Hiếu xem lần 1 (Gallery S70 và trang episode trước) |
| 20:30–23:00 | Sửa; dải khung hình chạy nền |
| 12/11 08:00–09:30 | Hoàn thiện biểu đồ, chế độ trình chiếu, trạng thái rỗng và "chỉ có trên rtx3060" |
| 09:30–10:30 | Làm mới dữ liệu: chạy lại chỉ mục, kéo `meta/` từ `rtx3060`, lấy metrics pair60k mới |
| 10:30–11:30 | Hiếu xem lần 2; kiểm ở 1 280 và 1 440 px, kiểm khi không có mạng |
| 11:30–13:00 | Chỉ sửa lỗi; đóng băng 13:00; chạy thử lộ trình demo hai lần |
| 14:00 | Chạy thử toàn bộ |

### 15.1b Bản 0.5: chatbot và ghép v3 + v5 [Đã chốt 11/11]

Ba yêu cầu của Hiếu tối 11/11, theo đúng lời:

- Bản v4 "quá lắm chữ"; người dùng là **AI Engineer**, phải trình bày cho hợp. **[Đã chốt]**
- Agent phải là **chatbot**, "chứ như này thì khác gì hardcode". **[Đã chốt]**
- Ghép v3 và v5, xoá các bản khác; "kể cả có là AI Engineer thì nó cũng phải trực quan là đa số chứ không phải có mỗi log và chữ". **[Đã chốt]**

Việc đánh giá lại do model Fable làm. Bản v1, v2, v4 đã xoá (vào thùng rác, khôi phục được). Bản chạy là v5 ghép với bố cục v3, tại `.superpowers/brainstorm/mockups/v5/`; tài liệu kỹ thuật của nó là `CONTRACTS.md`, `DESIGN.md`, `MERGE.md` cùng thư mục. Thư mục này chưa được git theo dõi (câu hỏi 6, mục 16).

**Khung trang.**

| Phần | Nội dung |
|---|---|
| Sidebar trái 208 px | Nhóm theo v3: Tổng quan · DỮ LIỆU (Datasets, Pipeline) · AGENT (QA/QC) · MODEL (Training, Eval) · VÒNG LẶP (Failure→Data, Chi phí) · HẠ TẦNG (Jobs, Máy). Mỗi mục có số đếm sống. Phím `[` thu còn 52 px |
| Thanh đầu 40 px | Tìm kiếm `⌘K`, chọn task, chip trạng thái (job đang chạy, `rtx3060`, Nemotron, số chờ duyệt), công tắc giao diện |
| Panel phải 400 px | Bốn tab **Chat · Cách làm · Log · Nguồn**. Trang tự đổ dữ liệu vào panel: Cách làm là danh sách bước kèm lệnh chép được; Log là log của job đang chọn; Nguồn là các file trang đã đọc. Tab đang mở ghi trên URL (`?rp=`), `⌘.` bật tắt panel |

**Trực quan trước.** Trang nào cũng mở bằng một hình: biểu đồ, sơ đồ hoặc ảnh. Bảng nằm dưới. Log chỉ hiện ngay trong trang ở Jobs; ở các trang khác log nằm trong panel. Tiêu đề mỗi hình không quá ba từ.

| Trang | Hình đầu trang |
|---|---|
| Tổng quan | Sáu ô KPI có sparkline; vòng flywheel chín khâu tô màu theo trạng thái sống (`GET /api/status`), bấm khâu mở trang; ba biểu đồ nhỏ (loss EMA, episode theo loại và trạng thái, QA theo nguồn); dòng thời gian job 24 giờ |
| Datasets | Cột chồng episode theo loại × trạng thái, giờ theo loại, QA theo nguồn; danh mục mặc định dạng lưới có ảnh đại diện; thêm các chế độ bảng, lineage và sankey |
| Một dataset | Gallery ảnh, viền theo QA; tab chất lượng là biểu đồ |
| Pipeline | Bảy tầng có thanh tiến độ; ảnh của các clip đã che mặt, viền theo QA; Gantt job |
| QA/QC | Phát hiện theo mã (tách CODE và LLM), donut quyết định, thanh bench |
| Training | Thanh tiến độ bước/60k từng run; loss EMA; loss theo nhóm thành bảy đồ thị nhỏ |
| Eval | Tỉ lệ thành công theo mức kèm thanh sai số Wilson; nhãn lỗi xếp chồng theo mức; funnel |
| Failure→Data | Sankey 240 → 131 → 262 → 229 → 177 → C+ → eval lại (chưa chạy), cạnh cột chi phí ước tính và thực đo |

**Giới hạn chữ.** Nhãn tối đa ba từ, không có câu trong khung trang. Lệnh `tools/word_budget.py` đếm chữ tĩnh của từng file JS và báo lỗi khi vượt; toàn bộ khoảng 430 chữ, so với khoảng 4 200 chữ của v4. Dữ liệu và chú thích biểu đồ không bị tính.

**Chatbot.**

- Model: Nemotron 3.5 Bolt E4B trên Ollama của `rtx3060`, gọi qua đường hầm SSH về `127.0.0.1:11435`. Không có model hosted dự phòng.
- Chatbot trả lời bằng cách **gọi công cụ đọc dữ liệu thật**: 18 công cụ đọc (catalog, dataset, episode, QA, run, metrics, log, eval, vòng lặp, ledger, job, phát hiện, lineage, mở trang) và một công cụ đề xuất job. Mỗi trang chỉ đưa cho model các công cụ hợp với trang đó.
- Kết quả công cụ hiện thành bảng hoặc biểu đồ, gắn nhãn **CODE**. Lời model gắn nhãn **LLM**. Số trong lời model mà không có trong kết quả công cụ bị gạch chân vàng.
- Đề xuất job chỉ hiện thẻ xác nhận; job chỉ chạy khi người bấm, qua đúng bộ chạy việc của mục 15.1a.
- Lệnh `/` (ví dụ `/runs`, `/eval`) gọi thẳng công cụ, không qua model, để dùng được khi `rtx3060` bận hoặc đường hầm đứt.
- Ràng buộc nằm trong code, không nằm trong prompt: chỉ đọc dưới `fwdata/` và dữ liệu của console; từ chối `vault/` và đường dẫn holdout; ảnh egocentric chỉ lấy từ `*.deid.mp4`; không chạy lệnh tự do; trạng thái pass/flag/reject chỉ lấy từ tầng code, model không đổi được. Mỗi lượt hỏi tối đa 3 vòng gọi công cụ, 20 giây, `num_ctx` 16 384.
- Mỗi lượt ghi trace (công cụ, tham số, thời gian, token) vào `fwdata/console/chat/`, xem được trên trang QA/QC.

**Bench chatbot** (`chat_bench.jsonl`, 46 câu, lần chạy 2 lúc 14:01 ngày 11/11, đo trên `rtx3060`):

| Chỉ số | Kết quả |
|---|---|
| Chọn đúng công cụ và tham số | 33/36 (91,7 %) |
| Từ chối đúng (guardrail) | 6/6 |
| Không gọi công cụ khi không cần | 4/4 |
| Số trong câu trả lời có nguồn | 132/135 (97,8 %) |
| Câu hỏi chéo hai trang | 4/6 |
| Độ trễ p50 / p95 | 5,5 s / 10,0 s |

Câu hỏi chéo trang còn yếu. Câu "vì sao 68 lần sinh S1 thất bại" (thêm sau lần chạy 2) vẫn hỏng vì model truyền `dataset_id` là "S1".

**Kiểm tra 11/11:** mười route chạy không lỗi JavaScript ở 1 440 × 900 và 1 920 × 1 080. Theme sáng chưa kiểm qua nút trên app. Nhãn giữa sankey Failure→Data còn chồng nhau. Ảnh lướt khi di chuột (filmstrip) mới có cho dữ liệu robot.

### 15.2 Sau demo

Mỗi đợt kết thúc bằng ảnh chụp màn hình trên dữ liệu thật.

| Đợt | Nội dung | Xong khi |
|---|---|---|
| 1 | Bộ đánh chỉ mục, server, khung giao diện, P1, P13 | Tổng quan hiện số thật, mở được mọi log |
| 2 | P2, P3, P4, P5 (dữ liệu) | T2 làm được |
| 3 | P6 Agent QA/QC | T3 làm được trên những gì đã chạy; phần chưa chạy hiện đúng trạng thái |
| 4 | P7, P8 (training, eval), P12 phương án A | T4, T5, T8 làm được |
| 5 | P9, P10, P11 | T6, T7 làm được |

## 16. Câu hỏi còn mở

Chờ Hiếu trả lời; câu trả lời được ghi lại vào đây. Xếp theo mức ảnh hưởng tới kế hoạch.

1. ~~Hạn và chỗ cắt.~~ **Trả lời 11/11:** console nằm trong demo, sẵn sàng cho chạy thử 12/11. Phạm vi bản 12/11 ở mục 15.1.
2. **Chế độ trình chiếu.** Khi chiếu cho DENSO, có cần một công tắc chỉ hiện dữ liệu `public` (ẩn video đội, EgoDex, psi-data) không? Nếu cần, mọi trang phải tôn trọng bộ lọc này từ đợt 1.
3. Lựa chọn máy: phương án A hay B (mục 10)?
4. Quan hệ với PR #72: O1 hay O2 (mục 11.3)? Nếu O2, có báo Châu trước khi bắt đầu không?
5. Story và người làm: console là một story mới của Hiếu, hay giao cho Châu? Story phải có "Phạm vi file"; việc đăng ký `fw console` chạm `pyproject.toml` gốc và `uv.lock`.
6. (Bản 0.5.) Bản v5 đang nằm trong `.superpowers/brainstorm/mockups/v5/`, chưa được git theo dõi và `.superpowers/` chưa có trong `.gitignore`. Chuyển vào `console/` theo một story, hay giữ ngoài repo tới sau demo?

## 17. Quyết định của người viết

Các điểm dưới đây người viết tự chốt để kế hoạch không phải đoán. Hiếu kiểm khi đọc; thấy sai thì sửa ở đây.

1. **(Thay bằng 15.1a ở bản 0.4.) Đường ghi trong bản đầu là tối thiểu.** Chỉ nút duyệt phát hiện của agent gọi lệnh có sẵn `fw agentqa review` (đồng ý / ghi đè kèm lý do). Duyệt can thiệp (P9), ký `Decision` (P11) và lập job (P12) chỉ **sinh lệnh để chép** và file nháp trong `fwdata/console/drafts/`; console không ghi vào `configs/` đang được git theo dõi, và không thêm lệnh mới vào làn của người khác.
2. **Dữ liệu chưa có trên laptop hiện "chưa có trên máy này"** kèm lệnh kéo về (rsync chỉ đọc từ `rtx3060`). Console không tự SSH, trừ đường hầm tới Ollama ở bản 0.4. Tiêu chí nghiệm thu T5 chấp nhận trạng thái này cho video và lưới điều kiện tới khi output eval được kéo về.
3. **Không tự fetch từ Colab.** Console hiện những gì vòng fetch hiện có (`fetched.json`) đã kéo về, kèm "cập nhật lúc …" và cảnh báo khi quá 30 phút. Trạng thái "VM treo" suy từ `train.log` không lớn thêm qua hai lần fetch.
4. **Nguồn sự thật cho `docs/` và `configs/` là bản checkout của `master` mà console chạy trong đó.** Nút "nguồn" ghi commit đang đọc.
5. **File dữ liệu trích dẫn** (số chỉ có trong Markdown) nằm trong repo, ví dụ `console/cited.yaml`. Mỗi dòng ghi tài liệu, mục và câu gốc chứa con số. Một test kiểm câu gốc vẫn có trong tài liệu ở commit hiện tại, để số trích không trôi khỏi nguồn. Người làm story duyệt file này trong PR.
6. **(Bản 0.5.) Giao diện tối là mặc định**, theo kiểu Linear, số dùng font mono. Lý do: người dùng là AI Engineer và màn hình dày dữ liệu. Có công tắc sáng. Thay nguyên tắc 2 của mục 6.
7. **(Bản 0.5.) Dùng lại sankey** cho chuỗi Failure→Data và chế độ "flow" của Datasets, vì Hiếu cần trực quan hơn. Chế độ "flow" mặc định chỉ hiện dataset hiện hành để còn đọc được. Thay nguyên tắc 7 của mục 6.
8. **(Bản 0.5.) Bỏ dòng "câu hỏi và câu trả lời" ở đầu trang** và thanh dẫn đường có lời dẫn (mục 15.1a) vì vượt giới hạn chữ. Câu chuyện demo do người trình bày nói; trang chỉ có hình và nhãn.
