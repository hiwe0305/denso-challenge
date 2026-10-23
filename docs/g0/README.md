# docs/g0 · Kết quả spike Sprint 1 (cổng G0)

_Ngày 24/10/2026. Quy ước cho các story S1-02 đến S1-11, theo [07 mục 3.2](../product/07-team-workflow.md). [Đã chốt] bởi Hiếu._

Thư mục này chứa câu trả lời Q và V của cổng G0. Nhiều story chạy song song cùng ghi vào đây, nên mỗi story chỉ ghi vào file của mình. Như vậy hai nhánh không bao giờ sửa cùng một file.

## 1. File của từng story

| Story | File kết quả | Dòng 03 §3.3 đề xuất |
|---|---|---|
| S1-02 | `env-simple.md` | Không; số đo là đầu vào cho V8, V10 |
| S1-03 | `psi0-eval.md` | V2; V8 phần suy luận |
| S1-04 | `psi0-finetune-cost.md` | V8 phần fine-tune |
| S1-05 | `q2-planner.md` | Không |
| S1-06 | `q3-q4-restore-visual.md` | V4, V5 |
| S1-07 | `psi-data.md` | V1; V6 phần dữ liệu; V9 |
| S1-09 | `signals-conditions.md` | V6 phần sim; V7 |
| S1-11 | `v3-planner-controller.md` | V3 |

## 2. Đề xuất cho 03 §3.3

Story không sửa [03 · Kiến trúc](../product/03-architecture.md). File kết quả kết thúc bằng mục `## Đề xuất cho 03 §3.3`:

| Dòng | Câu trả lời đề xuất | Trạng thái | Bằng chứng |
|---|---|---|---|
| V2 | … | có, không, hoặc tạm (kèm việc còn thiếu) | lệnh hoặc file số đo |

Ở review G0 cuối Sprint 1, Hiếu gom các mục này vào 03 §3.3 bằng một commit tài liệu riêng, kèm dòng change log của 03. Khi hai story cùng đề xuất một dòng (V6, V8), Hiếu ghép hai phần thành một câu trả lời.

## 3. Sổ chi phí G0

Mỗi story ghi vào `ledger/<story-id>.csv` của mình, ví dụ `ledger/S1-03.csv`. Sổ chỉ ghi thêm: không sửa hay xóa dòng cũ; ghi sai thì thêm dòng sửa có `note` giải thích.

Dòng đầu là tên cột:

```text
date,activity,resource_type,quantity,unit,unit_price_usd,amount_usd,estimated_or_measured,branch,round,job,person,note
```

- Các cột lấy theo LedgerEntry (03 §4.3).
- `branch` ghi `g0`.
- `person` dùng mã giả danh (03 §10.3), không ghi tên thật.
- `estimated_or_measured` là `estimated` hoặc `measured`; ước tính và thực đo luôn là hai dòng riêng.

Tổng chi phí G0 là gộp mọi file trong `ledger/`, bỏ dòng tên cột của từng file.
