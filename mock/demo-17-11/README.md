# Bộ mock kịch bản demo 17/11

**Dữ liệu mẫu, không phải số đo.** Mọi con số trong thư mục này là bịa, sinh
bằng `web/mock/generate.py` với một seed cố định. Không dòng nào đến từ một
lần chạy thật của lõi, của SIMPLE hay của Ψ₀.

Nạp bằng `fwsync import --from mock/demo-17-11 --origin mock`, để mọi bản ghi
mang `origin = 'mock'` và FE dán nhãn "mock" lên từng bản ghi (DESIGN.md
§4.4b). Đừng nạp thư mục này với `--origin core`.

Đừng sửa tay. Sửa `web/mock/generate.py` rồi chạy
`uv run python -m web.mock.generate`; `web/tests/test_mock.py` so thư mục này
với bản sinh lại và đỏ nếu lệch.

## Câu chuyện nó kể

- Năm lô: psi-data teleop, teleop bàn phím, synthetic S1, mẫu EgoDex, và một
  bản sao chấm Agent QA/QC có 10 lỗi cấy, dừng ở tầng 4. Code bắt 6/10, agent
  bắt thêm 2.
- Bốn thí nghiệm nhánh A, A_07, B, B_FAIL. B_FAIL có T3. B tốt nhất, B_FAIL
  kém hơn A.
- Lưới HE: V_EGO, V_EGO10, V_NOEGO × N ∈ {10, 20, 40, 80}. Mỗi điểm train
  trên release riêng có đúng N demo gốc của người (cộng 20, 10 hoặc 0 clip
  egocentric), nên `n_demos` đếm được từ dữ liệu. Lượt eval của điểm HE chỉ
  có số tổng, không có episode.
- Bốn lượt eval dev có episode (A, A_07, B, B_FAIL), mỗi lượt 90 episode, 2
  episode lỗi hạ tầng bị loại khỏi mẫu số. Một holdout niêm phong tới 20/11.
- Một lượt Failure → Data trên checkpoint B: bốn cụm, bốn chẩn đoán. Hai cụm là
  lỗi hệ thống và ngoài miền, không tốn ngân sách dữ liệu; hai cụm còn lại mới
  cần thu thêm.

## Giả định của bộ mock, không phải của hệ thống

- **Bản tham chiếu camera coi như đã ghim.** `configs/eval/diagnosis/system.yaml`
  thật để `reference_sha256: null` tới G0, nên chạy DA-13 thật hôm nay thì R5
  không chấm được và mọi episode ra `unknown`. Bộ mock giả như G0 đã xong để
  kể đủ câu chuyện; `config_sha256` của nó trỏ một cấu hình không có thật.
- **Video egocentric dùng `kind = teleop_demo`** với `source_kind = egocentric`
  và `is_root = false`. Hợp đồng chưa có `kind` riêng cho video người, và nó
  không phải demo robot nên không tính vào `r_demo`.
- **Tỉ lệ sửa được là prior Beta(1, 1) = 0.5**, vì chưa lượt nào khép lại; lợi
  ích kỳ vọng của bốn can thiệp tính theo đó.
- **Episode nạp vào gắn RunPlan `rp_ingest_g0`** (`purpose = g0_repro`).
  `Episode.run_plan_id` bắt buộc trong hợp đồng, mà `purpose` chưa có giá trị
  riêng cho việc nạp dữ liệu.
- **Bảng giá** là bốn kịch bản độ nhạy bịa; bút toán tính theo `pitch_v10`.
