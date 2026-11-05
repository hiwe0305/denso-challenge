# Bộ chấm lỗi cấy (DA-31)

Chấm phép kiểm QA bằng code và Agent QA/QC trên bộ lỗi cấy của [DA-27](defect-inject.md), theo [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 9.2 và 9.4. Mã ở `packages/flywheel-eval/src/flywheel/eval/agentqa/bench/`, test ở `packages/flywheel-eval/tests/unit/agentqa/bench/`. Story: [DA-31](../product/stories/DA-31-bo-cham-loi-cay.md).

Mọi số của bộ chấm là số **trên lỗi cấy**. Lỗi tự nhiên của dữ liệu thật liệt kê riêng, không tính vào precision hay recall.

## 1. Luồng chạy

```text
bản sao có lỗi ─┐                       ┌─ lớp code: QA tầng 4 (`fw data qa`) hoặc bộ phát hiện F-TRAIN, F-SYS
bản sao sạch  ──┴─ mỗi bản, hai lớp ─────┤
                                        └─ lớp agent: AgentReport của DA-20
                          │
            BenchSession: đủ hai lớp × mọi bản? không rò đáp án?
                          │ có
            mở DefectManifest niêm phong (kiểm sha256)
                          │
            precision, recall, báo nhầm, thời gian  →  bench_result.json (+ .sha256)  →  index.html
```

| Bước | Mã | Ghi chú |
|---|---|---|
| Đọc lớp code trên bản sao dữ liệu | `detections.read_qa_work` | Đọc `qa/reports.jsonl`, `episodes.jsonl`, `episode_index.json` trong work dir của `fw data qa`. Mã lỗi lấy từ `reasons` (`<check> (<mã>): …`). Từ chối nếu episode không mang `benchmark_copy_id` của đúng bản sao |
| Chạy lớp code trên bản sao log | `logs.run_log_checks` | `diagnose_train` (DA-08) cho `train/<job>`, R1 và R2 (DA-13) cho `rtc/<job>`, cùng cách test nối làn `tests/e2e/test_log_defects_detected.py` |
| Đọc lớp agent | `detections.agent_run` | Một hoặc nhiều `AgentReport` mỗi bản; `target_ref` quy về id của manifest (bảng dưới) |
| Mở đáp án | `session.BenchSession.open_answers` | Chỉ khi mọi bản có đủ hai lớp; trước đó ném `BenchIncomplete` và không đụng file đáp án (có test) |
| Chấm | `score`, `layers` | Mục 2, 3 |
| Ghi | `report.write_bench` | Thư mục mới, không ghi đè; JSON, hash, HTML dựng từ JSON |

`target_ref` của agent được chấp nhận ở các dạng sau, đều quy về id mà `DefectManifest` dùng:

| Bản sao | Id trong manifest | Dạng agent có thể ghi |
|---|---|---|
| Dữ liệu | `episode_000012` (tên file parquet) | `episode_000012`; id ingest `ep_<hex>`; đường dẫn `…/episode_000012.parquet` |
| Log | `train/<job>`, `rtc/<job>` | như trên; đường dẫn tới thư mục job hoặc file trong đó (`…/train/<job>/metrics.jsonl`) |

Dạng khác giữ nguyên chữ; nó không khớp lỗi nào nên tính là báo nhầm, không bị bỏ.

## 2. Cách tính (AC 2)

Theo design mục 9.2 (đã chốt 3/11/2026, issue #34):

| Số đo | Cách tính |
|---|---|
| Recall theo loại | Lỗi của loại đó được bắt / số lỗi cấy của loại đó. Bắt = lớp báo đúng target với đúng mã của lỗi. Không gộp các loại cùng mã |
| Precision theo mã | Trong các cặp (target, mã) khác nhau lớp báo trên bản có lỗi, phần khớp một lỗi cấy |
| Báo nhầm | Trên bản sạch: số episode hoặc job có ít nhất một báo cáo / tổng số |
| Thời gian | Từ lúc job xong (`job_finished_at` trong spec) tới lúc có báo cáo (mtime của `qa/reports.jsonl`, lúc chạy xong bộ phát hiện log, `created_at` muộn nhất của `AgentReport`). Thiếu một trong hai mốc thì ghi "chưa đo" |

Hai quy tắc design để ngỏ, bộ chấm chọn như sau **[Đề xuất]**, cần Hiếu duyệt:

1. **Lỗi tự nhiên.** Bản sạch là cùng dữ liệu không có lỗi cấy. Cặp (target, mã) mà một lớp báo trên cả hai bản là chuyện của dữ liệu, không phải của lỗi cấy: phép kiểm vẫn sẽ báo dù không cấy. Cặp đó ghi là lỗi tự nhiên, bỏ khỏi precision và recall; lỗi cấy trùng cặp đó tính là **bị che**, không tính là bắt được. Trên psi-data điều này quan trọng: DA-17 đo 73/99 episode phát lại không thành công, nên kiểm `task_success` (D6) báo ở cả hai bản.
2. **Trùng episode.** `duplicate_episode` chép episode A đè lên chỗ B; bộ phát hiện trùng có thể chỉ A hoặc B, nên báo A hoặc B với mã D5 đều tính là bắt.

## 3. Tách code và agent (AC 3)

| Cột | Nghĩa |
|---|---|
| by code | Lớp code bắt được |
| agent adds | Agent bắt được mà code không bắt |
| together | Ít nhất một lớp bắt |
| agent alone | Agent bắt được, kể cả phần code đã bắt |

Chất lượng báo cáo của agent:

- **Xếp hạng**: trong mỗi báo cáo, với mỗi cặp (phát hiện đúng, phát hiện sai), đúng khi phát hiện đúng có `rank` nhỏ hơn. Phát hiện tự nhiên không tính.
- **Giải thích và đề xuất**: theo `AgentReview` của kỹ sư (`fw review`). `agree` là insight và đề xuất đứng được, `override` là không. Hợp đồng chỉ có một quyết định cho mỗi phát hiện, nên giải thích và đề xuất chấm chung; muốn chấm riêng cần đổi hợp đồng `FindingDecision` (đề xuất cho Long và Hiếu, chưa làm). Phát hiện chưa ai duyệt ghi `unreviewed`, không tính là đúng.

## 4. Rào chắn đáp án

- Chỉ `agentqa/bench/` đọc `DefectManifest`. `test_bench_barrier.py` quét mọi module khác của `flywheel.eval`, gồm agent của DA-20 dưới `agentqa/`, và đỏ nếu có chỗ nhắc `DefectManifest`, `defect_manifest`, `load_manifest`, `open_sealed` hay import `bench`. Test `test_read_barrier.py` của DA-27 quét cùng chỗ từ phía làn Dữ liệu.
- Trước khi mở đáp án, mọi ref mà một lượt chạy nói đã đọc (`AgentInput.ref`, `AgentFact.source_ref`, `target_ref`, `figures`, `subject_ref`) được kiểm theo quy tắc chạy của DA-27 (đã chốt 4/11/2026): ref tới file đáp án, vào `answers/` (nơi còn giữ lineage), hoặc nhắc tới bản sao kia làm cả lượt chấm dừng với `AnswerLeak`.
- Manifest được kiểm lại với `defect_manifest.sha256` (cùng cách băm của DA-27) và với `dataset_id`; lệch thì dừng với `AnswerKeyError`.
- Mỗi nhóm (dữ liệu, log) phải có đúng một bản có lỗi và một bản sạch.

## 5. Lệnh chạy

```bash
uv run python -m flywheel.eval.agentqa.bench --spec bench.json \
    --answers fwdata/inject/answers --answers fwdata/inject-logs/answers \
    --out fwdata/bench/<tên lần chạy> [--store <gốc store>] [--run-plan-id <id>]
```

File spec (đường dẫn tính từ thư mục của spec) không chứa đường tới đáp án; đáp án chỉ đi qua `--answers`:

```json
{
  "copies": [
    {"group": "data", "dataset_id": "bench-1e258c0a78ca",
     "job_finished_at": "2026-11-04T10:00:00Z",
     "code": {"qa_work": "work/bench-1e258c0a78ca"},
     "agent_reports": ["agent/bench-1e258c0a78ca.jsonl"]},
    {"group": "logs", "dataset_id": "bench-…",
     "code": {"log_root": "../inject-logs/copies/bench-…"},
     "agent_reports": ["agent/logs-….json"]}
  ],
  "reviews": ["reviews/r1.json"]
}
```

Đầu ra trong `--out`: `bench_result.json`, `bench_result.sha256`, `index.html` (tiêu đề và đầu trang ghi "trên lỗi cấy"). Mỗi lần chạy ghi hai dòng `LedgerEntry` (`agent_qa`, `cpu_seconds`) vào sổ của store: dòng ước tính trước khi chạy (giả định 0,05 s mỗi đơn vị × 200 đơn vị mỗi bản), dòng thực đo sau, trỏ về dòng ước tính; chạy hỏng vẫn ghi dòng thực đo với `failed`. Run plan mặc định `g0-DA-31-<yyyymmdd>`.

## 6. Lần chạy 5/11/2026 trên bộ log cấy

Dựng lại bộ log của DA-27 trên laptop (Windows, CPU) bằng `flywheel.data.inject.log_defects.build_log_benchmark` ở `origin/master` `182dd65`, rồi chạy lệnh ở mục 5 với `log_root` của hai bản. **Lớp agent là báo cáo rỗng đứng tạm** (`stand-in-empty`), vì DA-20 chưa có agent; cột agent của lần chạy này không phải số đo của agent.

| Mục | Giá trị (đo) |
|---|---|
| Bản có lỗi, bản sạch | `bench-c6da75e9ff36` (30 lỗi: 10 loại × 3), `bench-cfcb0ba66776`; mỗi bản 40 job (30 train, 10 RTC) |
| Lớp code, recall theo loại | 3/3 cho cả 10 loại T1–T8, R1, R2 |
| Lớp code, precision theo mã | 3/3 cho cả 10 mã |
| Lớp code, báo nhầm trên bản sạch | 0/40 job |
| Lỗi tự nhiên | không có (log tổng hợp) |
| Thời gian tới báo cáo | chưa đo: log tổng hợp không có thời điểm job xong |
| Thời gian chạy bộ chấm | 0,59 s wall (dòng thực đo của ledger); ước tính 20 s |
| Hash kết quả | `dd8104cc…ba86dfe9` |

Kết quả khớp test nối làn của DA-27 (`tests/e2e/test_log_defects_detected.py`): mỗi job cấy ra đúng mã của nó, bản sạch không ra mã nào.

## 7. Còn lại

| Việc | Chờ | Ghi chú |
|---|---|---|
| Chạy trên hai bản sao psi-data | Máy `rtx3060` | Bản sao và đáp án ở `rtx3060:~/denso-da27/fwdata/inject/` (bàn giao của DA-27). Cần `fw data ingest` rồi `fw data qa` trên mỗi bản (mỗi lượt gắn đúng một bản), rồi chạy lệnh ở mục 5. Laptop không vào được máy này |
| Cột agent thật | DA-20 (Hưng) | Bộ chấm đã nhận `AgentReport` và `AgentReview`; chỉ cần thay báo cáo đứng tạm bằng báo cáo thật |
| Hai quy tắc ở mục 2 | Hiếu duyệt | Lỗi tự nhiên và trùng episode |
| Chấm riêng giải thích và đề xuất | Đổi hợp đồng `FindingDecision` nếu cần | Mục 3 |
