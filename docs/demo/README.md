# DA-28 · Chạy sáu phần demo

Đây là bản ghép trình chiếu ngoại tuyến [Đề xuất]. Mỗi phần đọc bằng chứng đã chuẩn bị từ máy của đội, kiểm SHA-256 rồi tạo một trang HTML để mở trong trình duyệt. Nó **không chạy train, simulator hoặc Agent QA/QC**, và không biến file mẫu thành kết quả đo. Các job thật theo runbook của người phụ trách; trang này chỉ trình bày đầu ra đã bàn giao.

Ngày 5/11/2026 chưa có đủ bằng chứng cho cả sáu phần trong kho. Video, dữ liệu và kết quả job nằm ngoài git. Không coi một phần là sẵn sàng nếu thiếu file hoặc `check` báo lỗi. Các kịch bản, thời lượng và kết quả thật cần Hiếu duyệt và chạy thử ngày 12/11.

## Chuẩn bị trên máy demo

1. Cài Python 3.10 trở lên. Lấy mã ở đúng revision đã duyệt; công cụ trình chiếu chỉ dùng thư viện chuẩn, không cần GPU hay mạng khi chạy.
2. Tập hợp **bản sao chỉ đọc** của báo cáo, bảng, video và sổ chi phí đã được duyệt vào `fwdata/demo/`. Không chép checkpoint, dữ liệu nhạy cảm hoặc đáp án lỗi cấy vào gói trình chiếu. Mỗi số hiển thị phải nằm trong file nguồn tương ứng; báo cáo cần nêu rõ tập, điều kiện và giới hạn của nó.
3. Tạo manifest mẫu và điền `path`, `sha256`, `title`, `kind`, `label`, `source` cho từng vai trò:

   ```bash
   python -X utf8 scripts/demo/demo.py template --output fwdata/demo/manifest.json
   ```

   `path` là đường dẫn tương đối từ thư mục chứa manifest, dùng `/`. `source` là chuỗi không rỗng xác định nguồn gốc thật của bằng chứng, ví dụ ID RunPlan, ID release hoặc dòng ledger, đường dẫn báo cáo nguồn kèm commit/PR đã tạo ra nó. Không dùng riêng đường dẫn bản sao làm nguồn gốc. Trên trang, nguồn gốc được hiển thị riêng với đường dẫn và SHA-256 của bản sao. Người bàn giao phải kiểm tính đúng của `source`; chương trình không tự xác minh ID.

   `kind` là `text` (UTF-8, tối đa 2 MB, hiện toàn văn), `image`, `video` hoặc `file` (liên kết mở file). `label` là `measured`, `preliminary`, `injected` hoặc `reference`. Phần 4 bắt buộc `injected`, phần 5 bắt buộc `preliminary`. Có thể thêm nhiều item cùng vai trò khi cần cả bảng và video. File HTML liên kết tới bằng chứng tại chỗ: **giữ nguyên vị trí bundle** sau khi tạo trang.

4. Tính SHA-256 của từng file sau khi chép, rồi điền 64 ký tự hex thường vào manifest. Ví dụ chạy được trên Windows và Linux:

   ```bash
   python -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" fwdata/demo/ten-file
   ```

   Với file lớn nên dùng `sha256sum <file>` trên Linux hoặc `(Get-FileHash -Algorithm SHA256 <file>).Hash.ToLower()` trên PowerShell. So hash với sổ bàn giao của người tạo dữ liệu; hash trong manifest chỉ chứng minh file không đổi sau lúc lập manifest, không tự chứng minh số liệu đúng.
5. Với phần 6, đặt `sections["6"].tray_outcome` là `full` nếu có C+ train, eval và bảng so C, C+, A; bổ sung ba item `tray_train`, `tray_eval`, `tray_comparison`. Nếu phải dùng đường lui đã duyệt, đặt `fallback`: báo cáo `tray_decision` phải ghi rõ dừng sau sinh và QA, lý do và việc C+ để sau. Trang sẽ hiện nhãn đường lui.
6. Kiểm cả sáu phần:

   ```bash
   python -X utf8 scripts/demo/demo.py check --manifest fwdata/demo/manifest.json
   ```

   Mã 0 là đủ vai trò và hash khớp, mã 1 là thiếu hoặc sai bằng chứng, mã 2 là manifest không đọc được hoặc lỗi tạo đầu ra. Mã lỗi cho bằng chứng giống nhau ở `check` và lệnh từng phần. Kiểm thủ công nội dung, khả năng phát video và nguồn của mỗi con số; công cụ không kiểm tính đúng đắn của báo cáo hay tự phát hiện file bị gán sai vai trò.

   Phần 4 từ chối đường dẫn có tên giống `DefectManifest` hoặc thư mục `answers` và kiểm tra hình dạng manifest trong JSON/JSONL. Đây chỉ là rào phát hiện các trường hợp thường gặp, không bảo đảm phát hiện mọi cách đổi tên hoặc nhúng đáp án: bộ chấm giữ đáp án riêng, người bàn giao vẫn phải kiểm bundle trước khi trình chiếu.

## Sáu lệnh trình chiếu

Mỗi lệnh tạo HTML; mở file HTML bằng trình duyệt trên máy demo. Đầu ra phải nằm **ngoài** thư mục bundle để không ghi đè bằng chứng. Nếu không có `--output`, HTML được in ra stdout.

```bash
python -X utf8 scripts/demo/demo.py 1 --manifest fwdata/demo/manifest.json --output fwdata/demo-html/01.html
python -X utf8 scripts/demo/demo.py 2 --manifest fwdata/demo/manifest.json --output fwdata/demo-html/02.html
python -X utf8 scripts/demo/demo.py 3 --manifest fwdata/demo/manifest.json --output fwdata/demo-html/03.html
python -X utf8 scripts/demo/demo.py 4 --manifest fwdata/demo/manifest.json --output fwdata/demo-html/04.html
python -X utf8 scripts/demo/demo.py 5 --manifest fwdata/demo/manifest.json --output fwdata/demo-html/05.html
python -X utf8 scripts/demo/demo.py 6 --manifest fwdata/demo/manifest.json --output fwdata/demo-html/06.html
```

Nếu một file thiếu hoặc hash sai, lệnh dừng trước khi tạo HTML mới. Với file HTML đã tạo từ lần trước, xóa hoặc đổi tên trước buổi demo và chạy lại; không dùng trang cũ khi lệnh báo lỗi. Trình duyệt phải cho phép mở file cục bộ và codec của video đã chọn.

## Vai trò bằng chứng và lời dẫn

| Phần | Vai trò bắt buộc trong manifest | Lời dẫn và nguồn bàn giao |
|---|---|---|
| 1 · Tái tạo Ψ₀ | `comparison`, `video` | Giới thiệu task hai bàn, checkpoint tác giả và cách tái tạo; nêu cấu hình thực tế và số của tác giả là số tác giả báo. Đầu mối S1-03: [psi0-eval.md](../g0/psi0-eval.md). |
| 2 · Ba nguồn | `egocentric`, `teleop`, `synthetic_s1`, `synthetic_s2`, `ledger` | Chỉ ra nguồn dữ liệu egocentric, teleop và synthetic, rồi chi phí thu/sinh. Quyết định 3/11 bỏ lượt teleop bàn phím trực tiếp; S1, S2 lấy từ task khay. Xem [quy trình đội](../product/07-team-workflow.md) mục 2.4 và [S2](../g0/tray/s2.md). |
| 3 · Pipeline | `egocentric_stage1`, `teleop_release`, `synthetic_release`, `dataset_report`, `loader_check` | Nêu các tầng đã thực sự chạy, release và lần stage 1 ngắn; tầng chưa có phải nói rõ. Bàn giao dữ liệu robot ở [data-pipeline.md](../g0/data-pipeline.md), kiểm loader ở [export-v21.md](../g0/export-v21.md) và stage 1 ở [stage1.md](../he/stage1.md). |
| 4 · Agent QA/QC | `benchmark_metrics`, `agent_report` | Cho thấy báo cáo và precision/recall trên **bản lỗi cấy**, không nói đây là kết quả trên lỗi tự nhiên. Chỉ bộ chấm đọc đáp án niêm phong; không đưa đáp án vào bundle. |
| 5 · HE-1 | `comparison`, `video` | Trình bày kết quả **sơ bộ** V-EGO và V-NOEGO đúng RunPlan, kèm tập và điều kiện thực tế. Nếu chưa đủ dữ liệu thì để phần này chưa sẵn sàng; không dựng đường cong giả. Nguồn: [HE-1](../he/he-1.md). |
| 6 · Failure → Data | `two_table_score`, `two_table_diagnosis`, `two_table_card`, `two_table_proposal`, `two_table_ledger`, `tray_score`, `tray_diagnosis`, `tray_card`, `tray_generation`, `tray_qa`, `tray_decision` | Hai bàn dừng ở đề xuất dữ liệu và sổ chi phí. Khay: lỗi C → chấm/chẩn đoán → sinh nhắm lỗi → QA → C+ → eval, hoặc đường lui đã ghi ở trên. Kết quả C/C+/A trên dev, một seed là mô tả sơ bộ, không gọi là kiểm HT. Nguồn: [design task khay](../superpowers/specs/2026-10-28-tray-transfer-he-design.md) mục 6.6 và [runbook khay](../he/tray.md). |

Danh sách này là yêu cầu bàn giao, không khẳng định mỗi artifact đã tồn tại. `text` hiện nguyên file kèm đường dẫn và hash; với biểu đồ, video hoặc tài liệu `file`, người trình bày phải mở và chỉ rõ báo cáo/ledger chứa từng số. Không đưa kết quả không có nguồn vào slide hoặc lời dẫn.

## Chạy lại phần CPU [Đề xuất, chờ Hiếu chốt]

Review PR #133 đề xuất phần 3, 4 và nhánh hai bàn của phần 6 chạy lại trên CPU, so kết quả rồi mới trình chiếu; nếu chạy lỗi thì hiện bản ghi sẵn và ghi rõ. Bản hiện tại **chưa triển khai** hành vi này và vẫn chỉ trình chiếu. Cần chốt đầu vào, cách so và đường lui trước khi dùng làm bằng chứng AC 2:

- Phần 3: test loader Ψ₀ ở `packages/flywheel-psi0/tests/contract/test_loader_roundtrip.py` cần môi trường Ψ₀ và LeRobot ghim, dataset và `.npz` tham chiếu ngoài git. Thiếu các gói hay dataset có thể làm pytest báo skipped; không được coi skipped là chạy thành công. Báo cáo dataset cần bộ đầu vào và nơi ghi riêng.
- Phần 4: `python -m flywheel.eval.agentqa.bench` cần spec, các thư mục `--answers` riêng và `--out` mới. Đáp án chỉ bộ chấm đọc, không thêm vào bundle trình chiếu. Kết quả hiện chứa `created_at` và ID ledger phát sinh mỗi lần, nên hash toàn bộ file kết quả không ổn định giữa các lần chạy; cần chốt phép so các trường kết quả và nguồn đầu vào, không so hash thô một cách mặc định.
- Phần 6: cần xác nhận lệnh và artifact thật của scorer, chẩn đoán, evidence card, đề xuất và ledger; thiếu một khâu thì không báo đã chạy hết vòng. Các lệnh phải ghi vào thư mục lượt chạy mới, không ghi đè bản bàn giao.

## Chưa có ở demo

Video egocentric đội tự quay; HE-2 trên dataset tự xây; S3, S4; HS, HT, HD; holdout. Không chạy holdout trong demo. Tình trạng này theo [design demo](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 11.

## Chạy thử 12/11/2026

Một người không viết script dùng máy sạch, nhận bundle đã duyệt, chạy `check` rồi sáu lệnh trên. Ghi thời gian từng phần, tên file/hash đã trình bày, lỗi phát video hoặc nguồn thiếu và người xử lý. Chưa chạy thử thì không đánh dấu nghiệm thu AC 5.
