# Sửa website sau review Astra · 07/10/2026

Đây là bản ghi sửa đổi sau audit, giữ nguyên ba báo cáo và snapshot cũ để đối chiếu. Phạm vi: website, canonical documentation, packaging/build và temporal guard của reference. Không nhận thêm bằng chứng native/real-robot/transfer/savings.

## Đã sửa và kiểm được

| Finding | Thay đổi | Bằng chứng kiểm |
|---|---|---|
| R07 / U01 | Resolve Markdown theo full path và thư mục tài liệu hiện tại; IDEA/form/A1/reference README có trong reader; khác README không còn cùng doc0 | Route regression mở bốn đích và assert đúng canonical paths |
| R07 / U03 | ZIP chính giữ nguyên cấu trúc relative paths, thêm A1/form và dependency closure; package manifest để không hứa file tải chưa có | 67 entries tại lần kiểm; ZIP CRC đạt; không thiếu local Markdown target |
| R08 / U02 | Normal build kiểm extracted asset hash; PDF local có thì kiểm hash, vắng thì không bắt buộc | Full current workspace copy không có thư viện PDF: build, static verifier và route regression đều đạt |
| R09 / D06 | Timestamp finite/present, monotonic theo recording và spacing khớp step×dt | Reference rerun;32 tests passed gồm NaN/missing/duplicate/reversed/spacing và valid nonzero origin |
| R05–R06 / U04 | Năm trang tóm tắt riêng, H1 riêng; outcomes có bốn deliverables, business dùng shared current budget, roadmap có bốn chặng8–12tuần có điều kiện, validation có source/workflow/final controls | Dựng đủ13routes và assert user-level content; technical docs giữ trong details |
| M04 / U06–U09 | Nhãn shared ACT/common wrist thống nhất; removed conversational headings; selected research path rõ; README mô tả active renderer và source authority | Current catalog/renderer/dossier build và route checks |
| U08 | Thêm original N1.5 architecture SVG từ website NVIDIA, credit/source link, tách custom A1 card | Static markup/source URL kiểm được; ảnh remote cần internet, chưa kiểm load trong browser phiên này |

Build hiện có45 readable documents. Original FluxVLA Figures1–5 giữ provenance/offline assets; N1.5 dùng ảnh nguồn remote và link fallback. Không tạo figure giả của tác giả.

## Đã cụ thể hóa; còn cần thực thi để xác nhận hiệu quả

| Finding | Contract/UI mới | Chưa được kết luận |
|---|---|---|
| R01 / M01 | Selected native run card: input/target/loss/params, binding/reload/closed-loop receipts; trạng thái native hiện ngay đầu Engine | Native A1 useful baseline hoặc real-robot capability của dự án |
| R02 / D01 | AcquisitionDecisionReceipt; matched parent–case workflow comparison, intervention access/cap và order/familiarity controls | Data Core chọn tốt hơn workflow thường hoặc utility estimator đã chạy |
| R03 / D02/D04 | Coverage requested→attempted→accepted/rejected; content identity/duplicate-family grouping trước split; overlap-audit contract | Native generator coverage đủ hoặc cross-source dedup backend đã implement |
| R04 / D03 | Gate96/100 và operating characteristics43,6%/81,8% trong scope IID; owner/sampling/seeds/paired-effect decisions | Owner đã chấp nhận protocol, policy pass hoặc hai policies equivalent |
| R05 / D05 | Measured RunPlan template và shared capacity subtotal5.187,20USD; job set/cap/retry/source/eval/effort fields | 180GPU-hours đủ,8–12tuần chắc chắn hoặc saving đã đo |
| R10 / M02 | FOCA semantic task IDs, train-only negative pool/minimum-count/zero-negative contract; adaptation phải công khai | FOCA branch đã port hoặc cải thiện native A1 |

H wrist-only vẫn là candidate hẹp, VLM frozen ở cả controls; không nhận finger/contact transfer. Need assessment/task owner và humanoid-vs-arm business validation được nêu rõ trên overview/product. Form Markdown vẫn draft; cập nhật/nộp deck/PDF/DOCX là bước riêng chưa thực hiện.

## Verification và giới hạn

- `python examples/engineering-loop/check.py`:32 passed; final R0/12,S12/12,C0/12 giữ nguyên, native/real robot promotion false, savings not established. Artifacts/validation/manifest được cập nhật theo code thật.
- `python presentation-site/verify-site.py`:13routes/45documents, media/plan/generated artifacts và ZIP link closure đạt.
- `node presentation-site/test-presentation.js`:13route summaries, distinct full-path links, shared budget/deliverables/timeline và evidence boundaries đạt. Đây là string-render regression với DOM stubs, không real-browser test.
- `node presentation-site/test-improvement.js`, JS syntax và diff whitespace checks đạt.
- [Clean-source build receipt](website-remediation-checks-2026-10-07.json): bản copy đầy đủ không có ignored PDF library; không phải hosted CI run.

Browser session đã bị policy từ chối trong audit trước; không dùng browser/CLI khác để vượt chặn. Vì vậy chưa có fresh visual/mobile/keyboard/remote-image QA cho bản sửa này. CSS có layouts theo viewport và source fallback nhưng các kiểm tĩnh không thay kiểm UI trực tiếp. Preview local cần refresh để lấy entry asset version07/10.

Build và package mới là local outputs; không commit, publish, submit hoặc nghiệm thu nhà máy. Các mục cần evidence thực nghiệm được giữ pending có phạm vi, không đổi nhãn thành resolved chỉ vì thêm contract.

## Cập nhật trang Ý tưởng & vấn đề sau review trực tiếp

Trang overview đã được viết gọn theo mạch: tình huống gắp hụt → dẫn chứng → Data Core × Model Engine Core + flywheel → dataset/training MVP → hiện trạng/chi phí pilot → phép kiểm và đầu ra. Nội dung pitch/case nằm trong `overview-flywheel.json`; không thay các recipe và trạng thái thực nghiệm ở hồ sơ kỹ thuật.

- Bỏ sơ đồ đặt video/robot actions/sim variants/human motion ngang hàng. Sơ đồ dữ liệu mới thể hiện mẫu robot gốc → tạo biến thể → sim execution/QA, cùng schema và lineage; synthetic là cách tạo, features là biểu diễn.
- Giữ Model AI trên overview với input → VLM features → Action Expert (+ robot state) → action chunk/controller. Chi tiết training branches dẫn sang learning/engine/sources.
- Sáu bước flywheel tương tác dùng cùng một tình huống. Có repair/defer trước acquisition, correction + replay, update scope theo phép kiểm, no-gain và final độc lập.
- Tách chi phí hiện trạng DENSO chưa khảo sát với ngân sách pilot minh họa5.187,20USD; dùng cùng cost inputs, không tạo savings hoặc baseline giả.
- Browser hiện đã kết nối lại được. Kiểm trực tiếp ở viewport973×905: khoảng1.013 từ mặc định thay1.929; chiều dài3.561px thay7.900px; flywheel bắt đầu khoảng1.432px thay6.501px. Không có horizontal overflow. Các con số phụ thuộc viewport và bước đang chọn.
- Đã thử bước kiểm giả thuyết và học có phạm vi; nội dung, trạng thái chọn và output thay đúng, không console error được ghi. Đây là kiểm UI hiện tại, chưa là audit mobile/keyboard/accessibility đầy đủ.

Ảnh kiểm tra giữ ngoài project trong thư mục visualization của chat; không tạo thêm ZIP bàn giao hoặc file review mới.
