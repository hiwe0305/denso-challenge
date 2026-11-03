# DA-39 · Hợp đồng `EvidenceCard` và file mẫu dùng chung

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (Hiếu mở ngày 4/11/2026: "Mở session làm luôn") |
| Người làm | Hiếu |
| Làn | Nhân (`flywheel-contracts`, chủ là Hiếu, 07 mục 2.1) |
| Story PRD | Epic 3 · FR21 (không im lặng thành đạt); [spec v10.5](../../spec-v10-failure-to-data.md) mục 4.5 (Evidence card), 6.4 (bước 4b), 6.9, 6.10, 6.11, 6.13, 6.14; [03](../03-architecture.md) mục 2.4 (dòng Evidence card), 4.3, 7.3; [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 10, mục 11 phần 6 |
| Nhãn | [Lõi] · `epic:3` · `area:contracts` |
| Sprint | S2 · merge trước **11/11/2026** (07 mục 2.4); từ 12/11 seam `6-EvidenceCard` của `tests/e2e/test_demo_seams.py` đỏ thay vì xfail |
| Ước lượng | 4 giờ (ước lượng) |
| Phụ thuộc | `Cluster`, `Score`, `Decision`, `LedgerEntry` của S1-10 (đã merge). Không chặn: bản ghi `SystemDiagnosisRecord` và `StageAttributionRecord` của DA-13 (#71, chưa merge) — hợp đồng đọc đúng các trường của hai bản ghi đó, không import chúng |

## Story

Là kỹ sư duyệt một cụm lỗi ở phần 6 của demo, tôi muốn một evidence card có schema chung, để làn Đánh giá dựng card từ Cluster, Score, kiểm hệ thống và quy lỗi về stage, còn `decide` của làn Vòng đọc đúng file đó, không phải hai bên tự đoán dạng của nhau. Hiện card không có hợp đồng, không có chủ và không có story; seam `6-EvidenceCard` đang xfail.

## Tiêu chí chấp nhận

1. Có model `EvidenceCard` trong `flywheel.contracts`, chứa đủ các mục của spec mục 4.5: định danh cụm, danh sách episode, các đại diện đã kiểm (kèm hạt giống chọn); bước hỏng đầu tiên k và kiểu lỗi; kết quả từng phép kiểm (sai số bám lệnh thân trên và thân dưới, độ trễ, buffer cạn, lệch đồng bộ, camera chuẩn, trạng thái hạ tầng, planner khả thi, s_k kèm số lượt, kiểm thị giác, trong miền train, khoảng cách vùng phủ); chẩn đoán, can thiệp đề xuất, lợi ích kỳ vọng, chi phí ước tính; quyết định của kỹ sư; kết quả sau khi train lại.
2. **Không chấm không đọc thành đạt (FR21).** Mỗi phép kiểm có giá trị kèm ngưỡng, hoặc ghi "không chấm" kèm lý do. Thiếu hẳn một phép kiểm bắt buộc là lỗi schema. Kết luận "nổ" hay "không nổ" của phép kiểm do hợp đồng tính lại từ giá trị và ngưỡng; card ghi sai kết luận thì bị từ chối. Một đại diện chưa chấm đủ R1–R6 không được mang chẩn đoán dữ liệu.
3. Mã F-SYS (R1–R6), dòng của bảng quy lỗi về stage và 12 chẩn đoán (11 của spec mục 6.9 cộng `infra` của R6) là `Literal`. Giả thuyết stage là đề xuất có `confirmed`; chỉ được `confirmed = true` khi card đã có quyết định của kỹ sư (spec mục 6.4).
4. Quyết định của kỹ sư là đồng ý hoặc ghi đè. Ghi đè phải có lý do không rỗng và nói rõ ghi đè chẩn đoán hay can thiệp (spec mục 6.14). Cụm hòa phiếu không có chẩn đoán, chỉ kỹ sư chọn được (spec mục 6.1, "hòa thì kỹ sư quyết").
5. Chi phí ghi rõ ước tính hay thực đo và trỏ về dòng sổ chi phí: chi phí của đề xuất là ước tính, của kết quả train lại là thực đo (03 mục 4.3, LedgerEntry hai dòng). Lợi ích kỳ vọng và số lỗi sửa được khớp công thức của spec mục 6.11 và 6.13.
6. JSON Schema xuất ra `packages/flywheel-contracts/schemas/EvidenceCard.json`; file mẫu dùng chung `artifacts/EvidenceCard.json` trong testkit cho một cụm lỗi của task hai bàn, với hash camera tham chiếu G0 `fc7f9c90…cdeea2` (DA-38).
7. Contract test: khứ hồi JSON, ghi đè thiếu lý do bị từ chối, phép kiểm thiếu ngưỡng hoặc thiếu lý do không chấm bị từ chối, schema khớp file đã commit.
8. Seam `6-EvidenceCard` qua (không còn xfail); dòng seam ghi chủ, story và hạn.
9. Card **không** là bảng catalog: không thêm vào `TABLE_MODELS` của store (03 mục 2.4: sinh lại từ Cluster và Decision, không có revision ở L0).
10. (PO P1, 4/11/2026) Card ghi tại `runs/<run_plan_id>/cards/<cluster_id>/card.json`, HTML để cạnh. Quy tắc đường dẫn nằm ở một chỗ: `StorePaths.card_path` của `flywheel.store.paths`. `Cluster.card_uri` không được ghi (ghi vào thì đổi ID nội dung của cụm); có test chứng minh ID cụm không đổi khi card được ghi.
11. (PO P4, 4/11/2026) Chẩn đoán hoặc can thiệp bị ghi đè nằm trong `Decision.criteria` dưới hai khóa `override.diagnosis`, `override.intervention`, khai bằng hằng số trong `flywheel.contracts.evidence`; có test khứ hồi từ `Decision` sang `EngineerDecision` của card.

## Nhiệm vụ

- [x] 1. Model `EvidenceCard` và các phần của nó trong `flywheel.contracts.evidence` (AC 1–5, 9)
- [x] 2. JSON Schema và file mẫu dùng chung, kèm script sinh lại (AC 6)
- [x] 3. Contract test (AC 7)
- [x] 4. Dòng seam: vị trí hợp đồng, chủ, story, hạn (AC 8)
- [x] 5. Đường dẫn card trong `StorePaths`, ghi chú `Cluster.card_uri` không dùng ở L0-lite, test ID cụm không đổi (AC 10)
- [ ] 6. Khóa ghi đè trong `Decision.criteria` và `EngineerDecision.from_decision` (AC 11)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-contracts/src/flywheel/contracts/evidence.py`
- `packages/flywheel-contracts/schemas/EvidenceCard.json`
- `packages/flywheel-contracts/tests/test_evidence.py`, `packages/flywheel-contracts/tests/generate_evidence_card.py`
- `packages/flywheel-testkit/src/flywheel/testkit/fixtures/artifacts/EvidenceCard.json`
- `tests/e2e/test_demo_seams.py`: chỉ dòng seam `EvidenceCard`
- `packages/flywheel-store/src/flywheel/store/paths.py`: chỉ `card_dir`, `card_path` (PO P1)
- `packages/flywheel-store/tests/unit/test_card_paths.py`
- `packages/flywheel-contracts/src/flywheel/contracts/entities.py`: chỉ ghi chú trên `Cluster.card_uri` (PO P1)

## Quyết định của PO

PO chốt ngày 4/11/2026 trên #82 ("Chốt theo đề xuất"), kèm sửa ở P1:

1. **[Đã chốt] P1 · Card nằm ở đâu.** 03 mục 4.3 ghi card nằm trong `meta` của Cluster, nhưng Cluster địa chỉ hóa nội dung: `meta` và cả `card_uri` đều nằm trong hash, nên ghi card hay đường dẫn của nó vào Cluster đều đổi ID cụm. Card ghi tại đường dẫn suy từ ID cụm, `runs/<run_plan_id>/cards/<cluster_id>/card.json` (AC 10); `Cluster.card_uri` để `None`. Dòng 03 mục 4.3 sửa ở PR tài liệu riêng.
2. **[Đã chốt] P2 · Vị trí hợp đồng.** Giữ `flywheel.contracts.evidence`; dòng seam như đã sửa.
3. **[Đã chốt] P3 · 07.** Đăng ký DA-39 trong 07 mục 2.2 và 2.4 ở PR tài liệu riêng, không trong story này.
4. **[Đã chốt] P4 · Ghi đè trong Decision.** Khóa `override.diagnosis` và `override.intervention` của `Decision.criteria` (AC 11).

## Ghi chú cho người làm

- Hợp đồng chỉ import `pydantic`; không import làn hay adapter (03 mục 7.3).
- Chẩn đoán dùng tên tiếng Anh, theo `Diagnosis` của DA-13, để artifact đọc được mà không cần tiếng Việt; tên tiếng Việt của spec mục 6.9 là việc hiển thị, nằm ở bộ dựng HTML (epic cards, Châu), không trong story này.
- Trường của giả thuyết stage và bằng chứng probe trùng từng trường với `StageHypothesisRecord`, `EvidenceRecord` của DA-13, để DA-13 chuyển sang hợp đồng mà không đổi dữ liệu.

## Kiểm thử

- `uv run pytest packages/flywheel-contracts/tests/test_evidence.py tests/e2e/test_demo_seams.py`
- `uv run ruff check`, `uv run mypy`, `uv run lint-imports` theo README gốc.

## Người phụ trách

- Làm: Dương Đình Hiếu (hợp đồng), qua phiên Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Long (`decide` đọc card), Châu (làn Đánh giá dựng và hiển thị card; DA-13)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 4/11/2026 | Tạo story theo yêu cầu của PO; mã DA-39 chưa dùng trong 07 và trên các nhánh | Hiếu |
| 4/11/2026 | Ghi quyết định P1–P4 của PO; thêm AC 10, 11, nhiệm vụ 5, 6 và ba đường dẫn vào phạm vi file | Hiếu |
