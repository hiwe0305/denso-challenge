# 04 · Kế hoạch triển khai: Humanoid Data Flywheel

_Ngày 22/10/2026. Vai trò BMAD: Product Owner (Sarah) viết mục 1; Scrum Master (Bob) viết mục 0, 2–8. Đầu vào: [README](README.md), [00](00-idea-analysis.md), [01](01-project-brief.md), [02](02-prd.md), [03](03-architecture.md), [spec v10.1](../spec-v10-failure-to-data.md), phản biện của QA ở [05](05-review-and-mentor-questions.md) và quyết định áp phản biện ở [06](06-review-round-1-decisions.md). Bản 0.2 đồng bộ với spec v10.1, 00 bản 0.2, 01 bản 0.3, 02 bản 0.3, 03 bản 0.3. Tên giả thuyết theo 06: **HS** (sim), **HT** gồm **HTa** và **HTb** (nhắm theo lỗi), **HD** (debug); mã đề giữ "H1" cho tới khi BTC xác nhận. Story Sprint 1 nằm ở [stories/](stories/). Câu hỏi cụ thể cho mentor do QA soạn ở 05 mục 6 và 6.6; file này chỉ trỏ tới._

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 22/10/2026 | 0.1 | Bản đầu: kết quả kiểm PO, nhịp sprint, phân công, kế hoạch 6 sprint, DoR, DoD, lịch mentor, phương án trễ, chỉ số theo dõi | PO, SM |
| 22/10/2026 | 0.2 | Đổi tên giả thuyết H1, H2, H3 thành HS, HT (HTa, HTb), HD; giữ mã đề. Sửa mã trích 05 bị sai: "05 TN…" thành "05 TH…" (TN là mã tính năng của 01) | SM theo 06 |
| 22/10/2026 | 0.2 | Thêm 5 story mới của 02 bản 0.3: 1.9 V3 (S1-11, S1, hạn ngày 5); 5.5 tuyến generator (S2–S3); 2.8 backup (S3–S4); 7.11 B-fail (S4–S5); 7.10 F-ACT (S5–S6). Phân công theo vai ở mục 3; S1-05 còn Q2 | SM theo 06 |
| 22/10/2026 | 0.2 | Lập kế hoạch ở 70% năng lực (06 mục 9); ước lại giờ theo AC bản 0.3; bảng tải mới (mục 4.7); thêm mục 4.8 kết luận tải: phạm vi mặc định vượt mức 70%, thứ tự cắt đã duyệt không đủ bù, nêu phương án chờ quyết | SM theo 06 |
| 22/10/2026 | 0.2 | Phạm vi mặc định: 1 vòng C trên Ψ₀, F-ACT trên ACT, B-fail trên ACT, holdout sớm niêm phong; thứ tự cắt (mục 7.2) khớp 02 §8 bản 0.3; G0 30 lượt mỗi mức; luật MDE ở G2 | SM theo 06 |
| 22/10/2026 | 0.2 | Mục 1: ghi "Cập nhật 0.2" cho P04, P11, P12, P20, P21, P22, P27, P29–P33 theo 06; mục 1.3, 1.4 theo L0-lite (03 §2.4, §4.3) và tuyến V3 mới | SM theo 06 |
| 25/10/2026 | 0.4 | Theo spec v10.3 và design ngày 25/10/2026: mục 4.1 ghi story Sprint 1 bị bỏ, thu nhỏ, đổi hướng; thêm mục 4.10 (robot DENSO trên MuJoCo, story DA-15…DA-23, giờ ước, máy chạy, quy trình duyệt) | PO (Hiếu) |
| 24/10/2026 | 0.3 | Mục 4.1 (điều kiện qua G0) và mục 5 (DoD, ý 7): sổ chi phí G0 tách theo story trong `docs/g0/ledger/`; story spike ghi đề xuất cho 03 §3.3 trong file của mình, Hiếu gom ở review G0 | PO (Hiếu) |
| 22/10/2026 | 0.2 | Mục 6: lịch mentor khớp câu hỏi của 05, gồm câu hỏi mở sau vòng 1 (05 mục 6.6, MO1–MO5); câu đã chốt theo 06 chuyển thành câu xác nhận | SM theo 06 |

## 0. Giả định lập kế hoạch

- **H** là số giờ làm mỗi tuần của một người. Chưa biết số thật. Kế hoạch gốc dùng **H = 20**; kiểm thêm ở 15, 18 và 25.
- Nghi thức (mục 2.2) tốn khoảng 2 giờ mỗi tuần. Năng lực ròng mỗi sprint là **2 × (H − 2)**: 36 giờ ở H = 20, 32 giờ ở H = 18, 26 giờ ở H = 15.
- Sprint 5 trùng Giáng sinh và Tết dương lịch: tính 80% năng lực (29 giờ ở H = 20).
- **Lập kế hoạch ở 70% năng lực ròng** (06 mục 9, spec 9): khoảng 25 giờ mỗi sprint, 20 giờ ở S5, 146 giờ mỗi người trong 12 tuần ở H = 20. 30% còn lại là đệm cho việc chưa biết và tích hợp lần đầu (05 KT1). Mức này thay mức 85% của bản 0.1.
- Ước lượng tính bằng giờ tập trung của một người, có dùng AI viết mã theo story (cách làm của BMAD). Bản 0.2 ước lại theo AC của 02 bản 0.3 và 5 story mới: tổng khoảng **960 giờ** cho phạm vi mặc định (56 story; 7.9 không lên lịch). PRD ước 3,5 ngày mỗi story, tức 200–215 người-ngày (02 §4). Chênh lệch đo bằng hệ số **k = giờ thực / giờ ước** sau Sprint 1.
- Trong bảng tải, ô vượt mức kế hoạch 70% có dấu ⚠; ô vượt cả năng lực ròng được in đậm.
- Hiếu được trừ sẵn 8 giờ mỗi sprint cho việc trưởng nhóm (DENSO, BTC, mentor); Thông 3–4 giờ cho vai Scrum Master. Lịch giả định bắt đầu thứ Hai 26/10/2026; bắt đầu ngày khác thì dời cả lịch, giữ thứ tự. Ngày 5 của Sprint 1 là thứ Sáu 30/10/2026.

**Cách điều chỉnh khi H hoặc k khác giả định.** Cuối mỗi sprint, SM tính: nhu cầu còn lại = tổng giờ ước của story chưa xong × k; mức kế hoạch còn lại = 70% × tổng theo người của 2 × (H thực − 2) × số sprint còn lại. Nếu nhu cầu vượt mức kế hoạch, áp các quyết định ở mục 4.8 rồi mức cắt kế tiếp ở mục 7.2.

| H thực (giờ/tuần) | Năng lực ròng 12 tuần mỗi người | Mức kế hoạch 70% | Tải lớn nhất sau cắt mức 1–7 / mức 70% | Kết luận |
|---|---|---|---|---|
| 25 | 267 giờ | 187 giờ | 199 / 187 = 106% | Gần vừa; tổng đội vừa (935 so với 934 giờ); cần cân lại Long, Thông |
| 20 | 209 giờ | 146 giờ | 199 / 146 = 136% | Không vừa; cần quyết ở mục 4.8 |
| 18 | 186 giờ | 130 giờ | 199 / 130 = 153% | Không vừa |
| 15 | 151 giờ | 106 giờ | 199 / 106 = 188% | Không vừa kể cả khi cắt thêm ngoài danh sách |

## 1. Kết quả kiểm của Product Owner

### 1.1 Cách kiểm

Theo tinh thần PO master checklist của BMAD: (1) khởi tạo dự án và hạ tầng, (2) phụ thuộc bên ngoài, (3) truy vết requirement ↔ story, (4) tên module và thực thể giữa PRD và kiến trúc, (5) thứ tự story và phụ thuộc vòng, (6) cổng G0–G6, (7) phạm vi MVP và khả thi 12 tuần, (8) rủi ro và trách nhiệm người. Đã đối chiếu thêm với phản biện 05 của QA. Bản 0.2: SM ghi "Cập nhật 0.2" ở các quyết định bị 06 thay; nội dung kiểm gốc của PO giữ nguyên.

### 1.2 Vấn đề → quyết định → file đã sửa

| Mã | Vấn đề | Quyết định của PO | File đã sửa |
|---|---|---|---|
| P01 | "F1" vừa là task dự phòng (spec 2.3) vừa là tính năng F1 (01 §6.1) | Spec là chuẩn nên giữ "F1" cho task dự phòng; tính năng trong brief đổi thành TN1–TN10 | 01 |
| P02 | CLI `hdf` (02) và `fw` (03) | Chọn `fw`; thêm các lệnh còn thiếu (`plan`, `train`, `ledger`, `index`) vào 03 §7.1 | 02, 03 |
| P03 | Cây mã `flywheel/core` (02) và `packages/flywheel/src` (03) | Theo 03 §7.1 | 02 |
| P04 | Metadata trong SQLite (02) và DuckDB dựng lại từ Parquet (03 ADR-04) | Theo 03; xem lại sau câu DS1 của mentor (P27). **Cập nhật 0.2:** 06 mục 9 chốt L0-lite; metadata là JSONL append-only, một tệp DuckDB chỉ chứa view, tự tạo khi mở, không có lệnh dựng lại (03 ADR-04, ADR-13) | 02 |
| P05 | Tên cờ khả năng `supports_*` (02) và `capabilities()` (03); FR14, FR21 không có cờ để khai | Theo 03; thêm `fault_injection` vào SimCapabilities và `plan` vào GenCapabilities | 02, 03 |
| P06 | RepairTicket: 03 §5.1 giao `diagnosis`; 03 §2.3 và 02 FR25 giao `decide` | `decide` tạo, vì bảng quyết định là cấu hình của `decide` | 03 |
| P07 | Tỉ lệ sửa được lưu ở `decide` (02 FR26) hay `ledger` (03 ADR-12) | `ledger` lưu FixRateEvent và tính posterior; `decide` đọc để tính g, c | 02 |
| P08 | Nhập psi-data: TeleopSource [Adapter] (02 · 2.2) hay `catalog` (03 §6.1) | Theo 03: bộ đọc LeRobot trong `catalog`, story 2.2 thành [Lõi]; ánh xạ trường psi-data nằm trong `configs/embodiments/` | 02 |
| P09 | 02 NFR6 đòi mức phân loại cho mỗi episode; 03 §4.3 thiếu trường | Thêm `data_class` vào Episode | 03 |
| P10 | RunPlan chưa có module chủ trong 03 §5.1 | `catalog` (khớp 02 FR5) | 03 |
| P11 | 02 FR1 liệt kê 10 thực thể, 03 §4.3 có 28 | 03 §4.3 là danh sách chuẩn; bảng tên ở mục 1.4. Thực thể được làm dần theo sprint, không làm cả 28 ngay. **Cập nhật 0.2:** 03 §4.3 bản 0.3 còn 12 thực thể L0-lite (ADR-13); 28 tên cũ là tên khái niệm, nơi lưu theo bảng gộp ở 03 §4.3 và mục 1.4 | 02 |
| P12 | V3 (teleop chạy WBC `g1_sonic`, MP chạy AMO) không có story nào ở G0 | Thêm AC vào 02 · 1.5; spike ngày 1–10; cây phương án ở 1.3. **Cập nhật 0.2:** V3 tách thành story 02 · 1.9 (S1-11), hạn ngày 5 của S1; tuyến được chọn xây ở 02 · 5.5 | 02, 03 |
| P13 | V6, V7 (tập điều kiện, tín hiệu cho scorer) không có story | Thêm story 02 · 1.8 | 02 |
| P14 | 02 NFR1 đòi đo độ không tất định ở G0 nhưng không có AC | Thêm vào 02 · 1.3 | 02 |
| P15 | Giấy phép (NFR6, V9) và nguồn gốc checkpoint gốc (05 TH12) không có AC ở G0 | Thêm V1, V9 vào 02 · 1.6; thêm Q0 vào 02 · 1.3; RunPlan mẫu ở 03 §8.1 không ghim sẵn `simple-checkpoints` | 02, 03 |
| P16 | FR14 (cấy lỗi) phần chung không có story [Lõi] | Thêm AC 4 vào 02 · 6.5; khi viết story tách thành 6.5a [Lõi] và 6.5b [Adapter] (nay ở S5) | 02 |
| P17 | Gần vòng 1.7 ↔ 2.1: vòng rỗng cần bản ghi, còn 2.1 lại phụ thuộc 1.7 | 2.1 chỉ phụ thuộc 1.1; 1.7 dùng kiểu v0 tối thiểu; 2.1 tách 2.1a (S1) và 2.1b (S3) | 02 |
| P18 | 02 · 1.4 phụ thuộc cứng 1.3, kéo dài G0 | Bỏ phụ thuộc cứng; chạy song song | 02 |
| P19 | Sprint 2 quá tải khoảng 20% | τ_cov và story 2.4 dời sang G2; ACT, DP qua `runner` dời sang đầu S3; G1 chỉ cần train, nạp lại, đánh giá từ bản export | 02 |
| P20 | Ngưỡng 8/10 lỗi cấy do PM tự đặt (02 · 6.5) | Duyệt có điều kiện, xem 1.3. **Cập nhật 0.2:** 06 mục 5 thêm phép kiểm đồng bộ cảm biến và camera chuẩn vào 6.2, nên điều kiện về trễ camera và lệch calibration đã giải | 02 |
| P21 | B⁺ tùy chọn: 03 §1.1 ghi như việc chắc chắn | Ghi "(tùy chọn)"; không lên lịch; điều kiện mở ở 1.3. **Cập nhật 0.2:** B-fail (02 · 7.11) thay vai ưu tiên của B⁺ và nằm trong phạm vi mặc định trên ACT | 03 |
| P22 | Thứ tự cắt giảm do PM tự đặt (02 §8) | Duyệt có sửa: trình xem HTML lên mức 2; thêm mức 6, 7; mở rộng danh sách không cắt. **Cập nhật 0.2:** 02 bản 0.3 sửa thứ tự để giữ ACT cho HTa và F-ACT (8 mức); xem mục 7.2 | 02 |
| P23 | Robot Learning chỉ 1 người, là trưởng nhóm, giữ 11 story trên đường găng (05 KT2) | Giao lại 7 story; Hiếu giữ quyết định; Châu là dự phòng Ψ₀ từ tuần 1 (mục 3) | 02 (trỏ sang 04) |
| P24 | 01 TN8 (sổ chi phí) ghi G3–G4, TN10 ghi G1; 02 đặt ledger lõi ở G1, Protocol v0 ở G0 | TN8 thành G1–G4, TN10 thành G0–G1 | 01 |
| P25 | 01 A6 không nhắc V3 | Thêm điều kiện planner cùng bộ điều khiển | 01 |
| P26 | 01 §8.2 đề xuất thêm đối chứng Mulligan | Ngoài phạm vi 12 tuần; ghi quyết định | 01 |
| P27 | 05 AR1: kiến trúc quá nặng cho L0 | Giữ trường mở rộng L1–L3 (rẻ, đúng ưu tiên "lõi dễ mở rộng"); hoãn MLflow, console Streamlit, S3, revision card; thực thể làm dần. Chốt lại sau DS1 ở review G0. **Cập nhật 0.2:** thay bằng 06 mục 9: L0-lite (03 §2.4, ADR-13), 12 thực thể, trường mở rộng trong `meta`; `task_id`, `embodiment_id`, `site_id` là cột thường có mặc định; hoãn thêm phân vùng ngày và lệnh dựng lại chỉ mục. DS1 chỉ còn để xác nhận | Không |
| P28 | 05 AR4: chỉ số chính ở holdout lấy từ scorer hay cờ SIMPLE chưa rõ | Chỉ số chính là cờ `check_success` của SIMPLE; scorer cho chỉ số theo bước và nhãn lỗi; ghi vào RunPlan holdout (nay là 03 ADR-14) | Không |
| P29 | 05 KT3 đề xuất chạy holdout sớm cho nhánh không phụ thuộc C | Không làm: spec 7.3 mục 8 yêu cầu đóng băng toàn bộ trước holdout. Thay bằng giữ lịch máy tuần 11 và đóng băng scorer cuối S4. **Cập nhật 0.2:** đảo theo 06 mục 9 và spec v10.1 mục 7.3, 7.5: nhánh không phụ thuộc C chạy holdout sớm ở S5 và niêm phong tới G5 (02 · 3.8 AC 4, 8.3 AC 4) | Không |
| P30 | 05 TH14: G0 chỉ 10 lượt mỗi mức | Giữ tiêu chí spec; nếu lệch đúng biên (2/10) thì chạy thêm 20 lượt trước khi kết luận. **Cập nhật 0.2:** thay bằng 30 lượt mỗi mức và kiểm nhị thức một phía (02 · 1.3 AC 1–2, S1-03) | Không |
| P31 | 05 TH1: lượng dữ liệu của B định nghĩa vòng tròn | Hiếu chốt N_sim hoặc trần GPU-giờ của B ở review G2, trước story 5.2; ghi vào RunPlan. **Cập nhật 0.2:** N_B = 2 × (D\* − 0,7D\*) rollout đạt QA, kèm trần GPU-giờ, chốt trong RunPlan trước G3 (02 · 5.2, spec 7.2) | Không (spec do đội sửa) |
| P32 | Spec 2.1, 6.4 ghi đối tượng kiểm hệ thống là AMO; task chính chạy WBC (05 DK1) | Không sửa spec ở đây; story 6.2 kiểm stack WBC; Hiếu đưa vào danh sách sửa spec ở G0. **Cập nhật 0.2:** spec v10.1 đã sửa: System-0 của task chính là decoupled WBC (03 ADR-15) | Không |
| P33 | Phạm vi 12 tuần có khả thi | Khả thi có điều kiện: H ≥ 18, k ≤ 1,1, V3 chốt trước S2 ngày 3, ngân sách GPU duyệt trong S1. Vòng 2 của C là có điều kiện (mục 7). **Cập nhật 0.2:** ở mức kế hoạch 70%, phạm vi mặc định không vừa ở H = 20; điều kiện mới và phương án ở mục 4.8 | Không |

### 1.3 Quyết định cho các điểm mở

**V3, bộ điều khiển teleop và motion planning.** Tuyến theo 06 mục 1 và spec v10.1 mục 10:

1. Ngày 1–5 (story [S1-11](stories/S1-11-bo-dieu-khien-v3.md), 02 · 1.9): so env, robot, bộ điều khiển, không gian state và action, tần số, camera của dữ liệu teleop và rollout MP, cho task chính và cặp F1. Kết luận sơ bộ trong check-in ngày 5.
2. Nếu cùng embodiment hoặc có ánh xạ tường minh: giữ thiết kế; 5.5 đóng "không cần".
3. Nếu khác: tuần 1–2 thử song song T1 (tái thực thi quỹ đạo MP trong env WBC, Hưng) và T2 (biến thể kiểu MimicGen hoặc IntervenGen từ đoạn teleop, chạy IK cộng WBC, Châu). Chốt tuyến cuối tuần 2 ở review G0, chậm nhất S2 ngày 3. Tuyến được chọn xây trong 5.5 (S2–S3).
4. T3 (planner trong env WBC) chỉ khi T1, T2 hỏng và mentor thấy khả thi (RL2). Tốn 2–4 tuần nên kích hoạt ngay mức cắt 2–4.
5. T4 (chuyển sang env MP) là đường lui cuối. HS bị thu hẹp thành "sim thay sim"; cần Hiếu và mentor đồng ý; ghi vào báo cáo.
6. Luôn giữ: release cấm trộn embodiment (03 ADR-08). F1 không chữa được V3 (05 DK4); F1 chỉ còn là phép thử NFR7 và dự phòng cho Q1, không là dự phòng cho Q2 trừ khi S1-11 xác nhận cặp của F1 cùng bộ điều khiển.
7. Correction do máy sinh và phép kiểm khả thi đi theo cùng tuyến. Nếu V3 âm và Q6 âm, C chỉ còn kiểm demo mâu thuẫn, mà phần này chỉ ra báo cáo; HT sụp; báo cáo phải nêu (06 mục 1).

**Giấy phép psi-data và trọng số Ψ₀** (chưa ghi giấy phép):

- Mọi episode từ psi-data và mọi checkpoint dẫn xuất mang `license = unknown`, `data_class = restricted` cho tới khi có văn bản của tác giả.
- Chỉ dùng cho PoC. Không đăng lại dữ liệu, bản export hay checkpoint fine-tune lên kho công khai.
- Bàn giao cho DENSO ở G6: mã của đội, SOP, báo cáo, video. Dataset và checkpoint dẫn xuất chỉ giao khi tác giả xác nhận.
- Hiếu gửi email cho PSI Lab trong tuần 1, hỏi cả giấy phép và nguồn gốc checkpoint (Q0). Sau 2 tuần chưa có trả lời thì hỏi mentor (DS7) và BTC (05 SR6), ghi giới hạn vào báo cáo.

**Ngưỡng 8/10 lỗi cấy (02 · 6.5).** Duyệt 8/10, kèm hai điều kiện:

- Điều kiện cứng: không lỗi cấy nào có đáp án thuộc lớp hệ thống bị xếp vào lớp tiêu ngân sách dữ liệu. Đây là lời hứa "hệ thống trước, dữ liệu sau".
- Đáp án từng loại khóa trước khi chạy, do Hưng giữ. Trễ camera và lệch calibration nay có phép kiểm đồng bộ cảm biến và camera chuẩn ở 6.2 (06 mục 5, 03 V11). Recall theo lớp và tỉ lệ báo nhầm trên đối chứng sạch là AC 5 của 6.5.

**B-fail, B⁺ và đối chứng khác.** B-fail (7.11) thay vai ưu tiên của B⁺ và nằm trong phạm vi mặc định, chạy trên ACT. B-fail trên Ψ₀ chỉ mở ở review G4 khi còn ngân sách. B⁺ giữ là tùy chọn, không lên lịch; chỉ mở sau B-fail khi đủ ba điều kiện: G4 đúng hạn, A100 đã tiêu ≤ 70% ngân sách, Hưng có ≤ 24 giờ kế hoạch ở S6.

**Mulligan và DISEIL.** Đã kiểm là có thật. Không thêm nhánh đối chứng Mulligan đầy đủ trong 12 tuần; B-fail là phiên bản rút gọn. Claim giữ theo spec 1.2 và bảng claim ở 05 mục 2.1: gọi HT là kiểm lại trên G1 toàn thân, có tính chi phí chẩn đoán. Báo cáo 8.4 có mục so sánh với hai công trình này. Hiếu rà claim trong pitch trước buổi mentor đầu tiên.

**Thứ tự cắt giảm** theo 02 §8 bản 0.3 (mục 7.2). **Robot Learning một người:** Hiếu giữ việc cần đúng chuyên môn và quyền quyết định, giao 7 story (mục 3.2); Châu đồng sở hữu Ψ₀ từ tuần 1 và vận hành ACT, F-ACT.

### 1.4 Tên thống nhất

Thực thể theo 03 §4.3 bản 0.3 (L0-lite, 12 bảng): Source, Condition, Episode, QAReport, Release, Checkpoint, RunPlan, Score, Cluster, FixRateEvent, LedgerEntry, Decision. Tên khái niệm của 02, spec và bản 0.2 ánh xạ như sau: cụm lỗi là Cluster; evidence card là trang sinh lại từ Cluster và Decision; can thiệp là một dòng `iv_<ULID>` trong `plan.json` cộng Decision `plan_review`; phiếu sửa và quyết định cổng là Decision `repair_ticket`, `dev_gate`; mục sổ chi phí là LedgerEntry; tỉ lệ sửa được là FixRateEvent với posterior tính lúc đọc (`ledger`); trace là Episode có `kind` là `eval_rollout` hoặc `diag_rollout`; bước hỏng và kiểu lỗi nằm trong Score (có `failure_class`); vòng flywheel là RunPlan `purpose = round`; Embodiment, Task, SplitPlan, PriceBook là cấu hình YAML có hash trong `configs/`. Adapter giả: `FakeSim2D`, `FakePolicy`, `FakeTrainer`, `FakeGenerator`, `FakeTeleop`, `ToyPickPlace`. TaskDefinition: `G1BendPickAndPlace` (task chính), `G1BendPick` (task F1).

### 1.5 Kết luận checklist

Khởi tạo và hạ tầng: đạt sau P02–P03. Truy vết requirement ↔ story: đạt sau P12–P16 và 5 story mới của 02 bản 0.3. Tên module, thực thể: đạt sau P02–P11 và L0-lite. Thứ tự story, phụ thuộc vòng: đạt sau P17–P19. Trách nhiệm người: đạt sau P23. Cổng G0–G6: đạt, điều kiện từng cổng ở mục 4. Phụ thuộc bên ngoài: đạt có điều kiện, V3 (hạn ngày 5), Q0, giấy phép và ngân sách GPU phải xong trong S1. Phạm vi và khả thi: **chưa đạt ở mức kế hoạch 70%** (P33, mục 4.8).

**Kết luận: ĐI TIẾP CÓ ĐIỀU KIỆN.** Sprint 1 bắt đầu được. Các thay đổi spec mà 05 mục 7 đề xuất đã áp ngày 22/10/2026 theo 06. Điều kiện mới: Hiếu và PO quyết phạm vi theo mục 4.8 ở họp lập kế hoạch S1, xem lại ở review G0.

## 2. Nhịp làm việc

### 2.1 Lịch sprint và cổng

| Sprint | Tuần | Ngày (giả định) | Cổng | Mục tiêu một dòng |
|---|---|---|---|---|
| S1 | 1–2 | 26/10–08/11 | G0 | Biết recipe chạy được không, tốn bao nhiêu; trả lời Q0–Q6, V1–V11; V3 trước ngày 5, thử T1 và T2; vòng rỗng chạy trên adapter giả |
| S2 | 3–4 | 09/11–22/11 | G1 | Data Core v0 và lát dọc trên SIMPLE trước tuần 4; scorer trùng cờ SIMPLE ≥ 95%; bắt đầu xây tuyến generator (5.5) |
| S3 | 5–6 | 23/11–06/12 | G2 | E1 cho 3 phương pháp, D\* theo ngưỡng 75%, power analysis; RunPlan và quy tắc công bằng; tuyến generator chạy được; backup hằng ngày |
| S4 | 7–8 | 07/12–20/12 | G3 | N_B chốt, sinh sim nhánh B, đo B_add; train A, A₀.₇, B; π₀ và B-fail của ACT; A/A test; báo lỗi dev theo mức |
| S5 | 9–10 | 21/12–03/01 | G4 | 1 vòng C trên Ψ₀, F-ACT 5–8 vòng trên ACT, C cuối, HD, holdout sớm niêm phong |
| S6 | 11–12 | 04/01–17/01 | G5, G6 | Holdout của C, mở niêm phong; báo cáo, SOP, video, khuyến nghị thu dữ liệu định lượng, rà claim |

### 2.2 Nghi thức tối giản

| Nghi thức | Khi | Thời lượng | Ai | Đầu ra |
|---|---|---|---|---|
| Lập kế hoạch sprint | Ngày đầu sprint | 60 phút | Cả đội | Story đạt DoR chuyển sang "Đang làm"; giờ dự kiến từng người; S1: H thực từng người và quyết định ở mục 4.8 |
| Check-in không đồng bộ | Thứ Hai, Tư, Sáu | 5 phút viết | Cả đội | 3 dòng trên kênh chat: đã làm, sẽ làm, vướng gì |
| Họp tuần | Giữa sprint | 30 phút | Cả đội | Gỡ vướng, kiểm tải, lịch GPU |
| Chuẩn bị story sprint sau | Tuần 2 của sprint | 45 phút | Thông, Hiếu, người phụ trách | File story sprint sau theo mẫu ở `stories/` |
| Review và cổng | Ngày cuối sprint | 60 phút | Cả đội, mời mentor khi có | Demo; checklist cổng; GateDecision do Hiếu ký |
| Retro | Ngay sau review | 30 phút | Cả đội | 1–2 thay đổi cách làm, có người giữ |

### 2.3 Kênh giao tiếp

- **Kênh chat nhóm** (đội chọn công cụ): check-in, hỏi nhanh. Quyết định không để lại ở chat; chép vào issue hoặc tài liệu.
- **GitHub Issues và Projects:** mọi việc. **Pull request:** mọi thay đổi mã và tài liệu, có ít nhất 1 người review.
- **`docs/product/`:** quyết định sản phẩm, có change log. ADR mới thêm vào 03 §12.
- **DENSO và BTC:** chỉ qua Hiếu. Thông soạn bản tin tuần (mục 8), Hiếu gửi.
- **Mentor:** Hiếu đặt lịch; Thông chuẩn bị tài liệu theo mục 6.

### 2.4 Bảng công việc

- Một GitHub Project "HDF L0", cột: Backlog → Sẵn sàng (đạt DoR) → Đang làm → Chờ review → Xong.
- Trường tùy chỉnh: Sprint, Người review, Giờ ước, Giờ thực, Cổng.
- Nhãn: `epic:1` … `epic:8`; `[Lõi]`, `[Adapter]`; `gate:G0` … `gate:G6`; `area:sim`, `area:data`, `area:rl`; `blocked`, `decision`, `spike`, `cut-candidate`.
- Milestone là sprint, ví dụ "S1 · G0".
- Tên issue: `[S1-03] PRD 1.3 · Tái tạo đánh giá Ψ₀`. Issue trỏ tới file story; file story là nguồn sự thật.
- Nhánh git theo story: `s1-03-psi0-eval`. Không commit dữ liệu, checkpoint, video.

## 3. Phân công

### 3.1 Vai chính và người dự phòng

| Người | Vai chính | Người dự phòng | Người này dự phòng cho |
|---|---|---|---|
| Dương Đình Hiếu | Trưởng nhóm, PO của đội, đầu mối DENSO, BTC, mentor; quyết định về Ψ₀ (checkpoint gốc, cấu hình train, D\*, ρ, luật MDE, duyệt đề xuất vòng C); ký cổng | Trần Trịnh Hoàng Châu (việc Ψ₀); Long chủ trì họp khi Hiếu vắng | Không ai, để giữ tải thấp |
| Trần Ngọc Hưng | Simulation lead: môi trường SIMPLE, SimulatorAdapter, V3 (S1-11) và tuyến generator (5.5), khôi phục trạng thái, cấy lỗi, sinh sim B-fail, điều phối HD, chạy holdout, lịch máy GPU | Trần Trịnh Hoàng Châu | Châu |
| Trần Trịnh Hoàng Châu | Scorer, TaskDefinition, vùng phủ, ACT và Diffusion Policy, vận hành F-ACT, Psi0Policy, vận hành train Ψ₀ trên A100, khóa holdout | Trần Ngọc Hưng | Hiếu (Ψ₀), Hưng |
| Nguyễn Thăng Long | Tech lead lõi: khung repo, contracts, catalog, runner, chia tập, chẩn đoán, quyết định, điều phối vòng C, sinh báo cáo | Dương Tiến Thông | Thông |
| Dương Tiến Thông | Scrum Master; dữ liệu và đo lường: nhập psi-data, QA, sổ chi phí, backup, cổng dev, thống kê, evidence card, công cụ HD, báo cáo theo vòng của F-ACT, SOP | Nguyễn Thăng Long | Long |

Châu dự phòng cho hai người. Bù bằng: runbook Ψ₀ (`packages/flywheel-psi0/RUNBOOK.md`) từ S2; Hưng biết serve Ψ₀ qua S1-03. Tải của Châu vượt năng lực ròng ở S2, S3, S5 (mục 4.7); đây là rủi ro người lớn nhất cùng với tải của Long và Thông (mục 4.8).

### 3.2 Giảm tải trưởng nhóm

**Hiếu tự làm, không giao:**

1. Đầu mối DENSO, BTC, mentor: hỏi kỹ năng và layout DENSO (05 DN1), ngân sách GPU, mã đề H1 hay H2 (05 R17); email PSI Lab về giấy phép và Q0.
2. Chọn checkpoint gốc (Q0), cấu hình fine-tune Ψ₀ (02 · 1.3, 4.2).
3. Chọn D\*, ρ, áp luật trần, sàn và luật MDE (02 · 4.4, 5.3).
4. Duyệt hoặc ghi đè đề xuất trong vòng C (02 · 7.6, 7.7), vì đây là vai "kỹ sư robot learning" của spec 6.14.
5. Ký cổng G0–G6 và quyết định cắt việc cùng Thông (mục 4.8, 7).
6. Tham gia HD như người không xây công cụ chẩn đoán.
7. Diễn giải kết quả, rà claim, cập nhật pitch.

**Giao cho người khác** (so với gợi ý của 02 §4):

| Story PRD | Gợi ý của 02 | Người làm | Hiếu còn giữ |
|---|---|---|---|
| 1.4 Chi phí fine-tune | Robot Learning | Châu | Duyệt cấu hình |
| 3.5 Hiệu chỉnh scorer | Robot Learning | Châu | Gán nhãn 20 lỗi |
| 3.6 Cổng dev | Robot Learning | Thông | Không |
| 7.6 Vòng 1 nhánh C | Robot Learning | Long vận hành | Duyệt đề xuất, ký cổng |
| 7.7 C cuối (vòng 2 Ψ₀ chỉ khi đủ điều kiện) | Robot Learning | Châu vận hành | Duyệt |
| 8.2 Chạy HD | Robot Learning | Hưng điều phối | Là người tham gia |
| 8.4 Báo cáo so sánh | Robot Learning | Long sinh báo cáo | Diễn giải, ký |

Story mới không thuộc Robot Learning nhưng cần Hiếu duyệt: 7.10 F-ACT (02 gợi ý Data-Platform; Châu vận hành, Thông báo cáo theo vòng; Hiếu duyệt RunPlan F-ACT trước vòng 1) và 7.11 B-fail (Hưng sinh sim, Châu train ACT; Hiếu quyết B-fail trên Ψ₀ ở review G4).

Quy tắc: Hiếu không là người review duy nhất của PR nào; mọi lệnh train và serve Ψ₀ có trong runbook; card chờ Hiếu duyệt quá 2 ngày thì Thông nhắc trong check-in.

### 3.3 RACI theo module và adapter

R: làm. A: chịu trách nhiệm cuối, mỗi dòng một người. C: hỏi ý kiến. I: được báo.

| Thành phần | Hiếu | Hưng | Châu | Long | Thông |
|---|---|---|---|---|---|
| `contracts`, `store` | I | C | C | A, R | R |
| `catalog` (nhập nguồn, release, RunPlan, lineage) | I | I | I | A, R | R |
| `qa` | C | I | I | C | A, R |
| `scenarios` (chia tập, vùng phủ, guard gần trùng, vault) | C | C | R | A, R | I |
| `runner` (kể cả wrapper cấy lỗi 6.5a) | I | C | C | A, R | I |
| `scorer` | C | C | A, R | C | I |
| `diagnosis` | C | C | R | A, R | C |
| `decide` (kể cả chế độ B-fail) | C | I | I | A, R | R |
| `acquisition` | I | C | I | A, R | C |
| `training` | A | I | C | R | I |
| `gate` (cổng dev, A/A, thống kê, khóa holdout, niêm phong) | A | C | R | C | R |
| `ledger` | I | I | I | C | A, R |
| `reports` (card, báo cáo, HD) | A | C | I | R | R |
| Backup và diễn tập khôi phục (2.8) | I | C | I | C | A, R |
| SimulatorAdapter: `SimpleSimulator` | I | A, R | C | C | I |
| PolicyAdapter: `Psi0Policy` | C | A | R | I | I |
| PolicyAdapter, TrainerAdapter: LeRobot (ACT, DP) | C | C | A, R | I | I |
| TrainerAdapter: `Psi0Trainer` | A, R | I | R | C | I |
| GeneratorAdapter: tuyến V3 đã chọn (1.9, 5.1, 5.5) | C | A, R | R | C | I |
| TeleopSource: `SimpleTeleop`, `PlannerCorrectionSource` | C | A, R | I | C | I |
| TaskDefinition: `G1BendPickAndPlace`, `G1BendPick` | C | R | A, R | I | I |
| Bộ giả `flywheel-fakes` | I | I | C | A, R | C |
| Cấy lỗi trên SIMPLE, khóa đáp án | I | A, R | I | C | I |
| Thí nghiệm Ψ₀ (E1, nhánh, vòng C) | A | C | R | R | I |
| F-ACT (7.10) | C | I | A, R | C | R |
| B-fail (7.11) | C | A, R | R | C | I |
| Holdout (đợt sớm và G5) | A | R | C | I | R |
| HD | C | A, R | I | I | R |
| SOP | C | C | C | C | A, R |
| DENSO, BTC, mentor | A, R | I | I | C | C |
| Bảng công việc, nghi thức, bản tin tuần | A | I | I | I | R |

### 3.4 Kỹ năng chưa có minh chứng

Theo 00 §7, năng lực đã nêu chỉ ở mức mảng. Các kỹ năng sau chưa có minh chứng và được ghi là rủi ro.

| Kỹ năng cần | Người | Đã có theo 00 §7 | Cách bù |
|---|---|---|---|
| Docker có GPU, Isaac Sim 4.5 headless, image ghim digest | Hưng | MuJoCo, Isaac Sim | Thử cài trên 5090 ngày 1–3 (05 SI3); Long pair phần compose; hỏi mentor |
| Fine-tune VLA 2,5B, flash-attn, A100 thuê | Hiếu, Châu | Hiếu: FOCA trên SmolVLA, PPO; Châu: chưa có | Chạy đúng script công bố của Ψ₀; S1-04 làm cặp; RL3 |
| Train ACT, Diffusion Policy; chạy nhiều vòng ACT (F-ACT) | Châu | Chưa có | Baseline có sẵn trong SIMPLE; Hiếu review cấu hình |
| Thư viện Python có kiểu, CI, import-linter, Pydantic | Long, Thông | Phân tích, xử lý, chuẩn hóa dataset | S1-01 dựng mẫu; L0-lite bớt model; AI viết mã theo story; review chéo |
| Bootstrap phân cấp, logistic hỗn hợp, power analysis | Thông, Hiếu | Phân tích dataset | Test mô phỏng có đáp án (05 mục 3); TK1, TK2 |
| Planner, IK, WBC cho tuyến V3 | Hưng, Châu | Chưa có với cuRobo, WBC | Thử T1, T2 tuần 1–2 (S1-11); RL2; T4 là đường lui |
| Thiết bị teleop | Chưa ai | Chưa rõ có thiết bị (Q6) | Correction do máy sinh, gắn cờ "máy sinh" |

## 4. Kế hoạch sprint

Giờ trong bảng là ước lượng ở mục 0, cho **phạm vi mặc định trước khi cắt**. "Quyết định" là việc chọn phương án có hạn chót. Phần lớn đề xuất của 05 mục 7 đã chốt theo 06; phần còn mở nằm ở 05 mục 6.6.

### 4.1 Sprint 1 · Tuần 1–2 · G0

**Mục tiêu.** Biết recipe Ψ₀ + SIMPLE / G1 chạy được không và tốn bao nhiêu; có câu trả lời Q0–Q6, V1–V11; V3 trước ngày 5; khung lõi chạy vòng rỗng trên adapter giả.

| File story | PRD | Story | Nhãn | Người | Giờ |
|---|---|---|---|---|---|
| [S1-01](stories/S1-01-khung-repo-cli-ci.md) | 1.1 | Khung repo, CLI `fw`, CI (L0-lite) | [Lõi] | Long | 11 |
| [S1-02](stories/S1-02-moi-truong-simple.md) | 1.2 | Môi trường SIMPLE ghim phiên bản | [Adapter] | Hưng | 16 |
| [S1-03](stories/S1-03-tai-tao-danh-gia-psi0.md) | 1.3 | Tái tạo đánh giá Ψ₀ 30 lượt mỗi mức, Q0, độ không tất định | [Adapter] | Hiếu | 20 |
| [S1-04](stories/S1-04-chi-phi-finetune-psi0.md) | 1.4 | Đo chi phí fine-tune Ψ₀ (Q5) | [Adapter] | Châu | 12 |
| [S1-05](stories/S1-05-planner-va-bo-dieu-khien.md) | 1.5 phần Q2 | Planner của SIMPLE cho task chính | [Adapter] | Hưng | 6 |
| [S1-06](stories/S1-06-khoi-phuc-trang-thai-va-hinh-anh.md) | 1.5 phần Q3, Q4 | Khôi phục trạng thái, tách hình ảnh | [Adapter] | Châu | 8 |
| [S1-07](stories/S1-07-phan-tich-psi-data.md) | 1.6 | Phân tích psi-data (Q1, Q6, V1, V6, V9) | [Adapter] | Thông | 12 |
| [S1-08](stories/S1-08-khung-loi-adapter-gia.md) | 1.7 | Khung lõi chạy trên adapter giả | [Lõi] | Long | 18 |
| [S1-09](stories/S1-09-tin-hieu-va-tap-dieu-kien.md) | 1.8 | Tín hiệu từng bước, tập điều kiện (V6, V7) | [Adapter] | Châu | 8 |
| [S1-10](stories/S1-10-mo-hinh-du-lieu-va-kho.md) | 2.1 phần a | Mô hình dữ liệu L0-lite và kho lưu | [Lõi] | Thông | 10 |
| [S1-11](stories/S1-11-bo-dieu-khien-v3.md) | 1.9 | Bộ điều khiển teleop và MP (V3), hạn ngày 5; thử T1 (Hưng 12 giờ), T2 (Châu 6 giờ) | [Adapter] | Hưng | 18 |

**Bản 0.4 (25/10/2026).** Theo [design ngày 25/10/2026](../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md) mục 11.1: S1-05 và S1-11 **hủy** (teleop, planner và policy chạy cùng bộ điều khiển trên MuJoCo, không còn V3); S1-02 thu nhỏ còn môi trường đủ cho S1-03; S1-06 thu nhỏ còn phần tách hình ảnh; S1-07 thay bằng DA-22 (dataset BTC); S1-09 đổi sang task khay → máy trên MuJoCo; S1-04 mở rộng sang stage 2–3 trên Colab. S1-01, S1-03, S1-08, S1-10 giữ nguyên. Story mới của Sprint 1 ở mục 4.10.

Việc ngoài story: Hiếu 10 giờ (DENSO DN1, ngân sách GPU, mã đề, email PSI Lab, buổi mentor đầu, rà claim theo 05 mục 2.1, chốt H thực từng người); Hưng 2 giờ hỗ trợ S1-03; Thông 4 giờ dựng bảng công việc.

**Phụ thuộc.** Bước 1 của S1-11 (bảng đối chiếu) đọc cấu hình và mã SIMPLE nên bắt đầu ngày 1, không chờ S1-02; thử T1, T2 cần S1-02. S1-02 xong trong tuần 1 vì S1-03, S1-05, S1-06, S1-09, S1-11 cần môi trường SIMPLE. Phần serve Ψ₀ của S1-03 và toàn bộ S1-04 bắt đầu ngày 1. S1-08 và S1-10 cùng dùng `contracts`: Thông đưa `contracts/base.py` trước ngày 4. **Rủi ro.** V3 âm (05 R01); Isaac Sim hoặc flash-attn không chạy trên 5090 (R05); checkpoint gốc đã thấy dữ liệu task chính (R02); tranh máy 5090 giữa S1-03, S1-04 và T1, T2.

**Điều kiện qua G0.** Ψ₀ chạy 30 lượt mỗi mức, kiểm nhị thức một phía (α = 0,05) không cho thấy tỉ lệ thấp hơn số công bố; Q0 có checkpoint `pre.*` hoặc `postpre.*` kèm provenance trong Source, hoặc giới hạn được ghi; Q1, Q2, Q5, Q6 có câu trả lời; Q3, Q4 có câu trả lời tạm, chốt trong 6.4 ở S3; V3 có kết luận trước ngày 5 và tuyến chốt cuối tuần 2, chậm nhất S2 ngày 3; V1–V11 có câu trả lời hoặc người giữ và hạn (V11 do Hưng chốt trong 3.1a ở S2; V8 gồm W khi policy là ACT, đầu vào cho 05 MO2); ngân sách GPU biết; email giấy phép và Q0 đã gửi; vòng rỗng xanh trong CI dưới 10 phút; chi phí G0 có trong `docs/g0/ledger/`, mỗi story một file (bản 0.3); H thực từng người và quyết định phạm vi ở mục 4.8 đã ghi. **Demo cuối sprint.** Video Ψ₀ chạy task công bố trong SIMPLE kèm bảng so với số công bố; bảng V3 và kết quả T1, T2; `fw --version`; CI chạy vòng rỗng; bảng trả lời Q và V.

### 4.2 Sprint 2 · Tuần 3–4 · G1

**Mục tiêu.** Data Core v0 và lát dọc trên SIMPLE trước tuần 4 (spec 9, 05 PM4); scorer hiệu chỉnh đạt ngưỡng; ACT và DP train thử; bắt đầu xây tuyến generator đã chọn.

| PRD | Story | Nhãn | Người | Giờ | Phụ thuộc |
|---|---|---|---|---|---|
| 2.2 | Nhập psi-data vào catalog | [Lõi] | Thông | 16 | S1-07, S1-10 |
| 2.3 | QA bắt buộc | [Lõi] | Thông | 14 | 2.2, 3.3 |
| 2.7b | Sổ chi phí đủ: bảng giá, ước tính và thực đo tách riêng, `fw ledger add`, nhập CSV G0 | [Lõi] | Thông | 7 | S1-10 |
| 2.5 | Chia tập theo hạt giống, dải rời dải tác giả, canary chống rò | [Lõi] | Long | 11 | S1-10 |
| 3.2 | Runner và trace | [Lõi] | Long | 12 | S1-08, S1-10 |
| 2.6 | Release bất biến, export, đếm demo gốc | [Lõi] | Long | 12 | 2.3, 2.5 |
| 3.1a | `SimpleSimulator`, hook ghi tín hiệu, `t_state`, `t_image`, tham số camera (chốt V11) | [Adapter] | Hưng | 16 | S1-02, S1-09 |
| 3.4 phần task chính | TaskDefinition `G1BendPickAndPlace`; khung F1 dời S6 | [Adapter] | Hưng | 8 | 3.3, S1-09 |
| 5.5 phần 1 | Xây tuyến generator đã chọn (T1 hoặc T2) | [Adapter] | Hưng | 12 | S1-11, 3.1a |
| 4.1 phần G1 | ACT, DP train thử từ export | [Adapter] | Châu | 4 | 2.6 |
| 3.1b | `Psi0Policy`, contract test | [Adapter] | Châu | 8 | S1-03 |
| 3.3 | Khung scorer từng bước, lớp lỗi chung | [Lõi] | Châu | 13 | S1-08 |
| 3.5 | Hiệu chỉnh scorer, τ_track, τ_sync | [Lõi] | Châu | 12 | 3.2, 3.4; Hiếu gán nhãn |
| 4.2 | TrainerAdapter Ψ₀, tăng cường thị giác cố định đọc từ RunPlan | [Adapter] | Hiếu | 17 | S1-04, 2.6 |

Việc ngoài story: Hiếu 12 giờ (gán nhãn 20 lỗi cho 3.5, việc trưởng nhóm); Thông 3 giờ Scrum Master. Nếu S1-11 kết luận cùng bộ điều khiển hoặc có ánh xạ, 5.5 đóng "không cần"; 12 giờ của Hưng chuyển sang khung F1 (3.4) và đệm. **Rủi ro.** Tín hiệu thiếu khiến scorer nhiều "chưa rõ" (V7); dữ liệu psi-data không có hạt giống (V6) nên guard dựa trên `layout_hash` và khoảng cách (05 TH13); 5.5 kéo dài nếu tuyến là T2 hoặc T3.

**Điều kiện qua G1.** Scorer trùng cờ SIMPLE ≥ 95% trên 100 episode, 20 lỗi được xác nhận bước hỏng; τ_track, τ_sync trong RunPlan nháp; lát dọc chạy trọn trước tuần 4: một trace SIMPLE thật qua runner, scorer, card nháp và sổ chi phí; psi-data đã nhập, có QA và lineage; SplitPlan đóng băng với dải rời dải tác giả, canary holdout bị chặn; release đầu tiên đóng băng; ACT và DP train, nạp lại, đánh giá được từ bản export; `camera_ref_hash` chốt (03 §5.2). **Demo.** Một episode psi-data thành release; một trace SIMPLE thật thành bảng trạng thái từng bước; báo cáo QA theo nguồn.

### 4.3 Sprint 3 · Tuần 5–6 · G2

**Mục tiêu.** Đường cong E1, D\*, power analysis; RunPlan đóng băng và quy tắc công bằng chạy tự động; tuyến generator chạy được; chẩn đoán và bảng quyết định chạy trên adapter giả; backup hằng ngày.

| PRD | Story | Nhãn | Người | Giờ | Phụ thuộc |
|---|---|---|---|---|---|
| 2.1b | RunPlan, `fw plan freeze`, test NFR7 với task giả | [Lõi] | Long | 8 | S1-10 |
| 4.3 | Điều phối train, quy tắc công bằng, chặn `simple-checkpoints` | [Lõi] | Long | 12 | 2.1b |
| 6.1 | Gom cụm, chẩn đoán cụm | [Lõi] | Long | 8 | 3.3 |
| 6.2 phần 1 | Kiểm hệ thống trên stack WBC, đồng bộ cảm biến, camera chuẩn, NGOÀI MIỀN | [Lõi] | Long | 10 | 3.5, 2.4 |
| 4.4 | E1, seed thứ hai của Ψ₀ quanh ngưỡng 75%, D\*, power analysis và hàm MDE | [Adapter] | Hiếu | 18 | 4.2, 3.5, 4.3 |
| 4.1 | ACT, DP qua `runner`, contract test; E1 phần ACT, DP | [Adapter] | Châu | 16 | 3.2 |
| 2.4 | Vector điều kiện, kNN, τ_cov, guard gần trùng, chế độ B-fail | [Lõi] | Châu | 15 | S1-10 |
| 5.5 phần 2 | Xây tuyến generator, đo tỉ lệ sinh đạt trên 50 điều kiện | [Adapter] | Hưng | 16 | 5.5 phần 1 |
| 5.5 phần 2, nhánh T2 | Phần IK cộng WBC, chỉ khi chọn T2 | [Adapter] | Châu | 8 | 5.5 phần 1 |
| 5.1 | GeneratorAdapter bọc tuyến đã chọn | [Adapter] | Hưng | 8 | S1-11, 3.1a, 5.5 |
| 6.4 phần 1 | Khôi phục trạng thái dưới stack WBC; chốt Q3, Q4 | [Adapter] | Hưng | 8 | S1-06, 3.1a |
| 3.6 | Cổng dev trên tập điều kiện mới, A/A test trên giả | [Lõi] | Thông | 14 | 3.2, 3.3 |
| 7.1 | Bảng quyết định (gồm LỖI ĐỒNG BỘ, LỖI CALIBRATION, NGOÀI MIỀN), định lượng | [Lõi] | Thông | 12 | 6.1, 2.7b |
| 2.8 phần 1 | Backup hằng ngày sang máy 3060 | [Lõi] | Thông | 6 | S1-10, 2.7b |

Việc ngoài story: Hiếu 12 giờ (review mã chẩn đoán, việc trưởng nhóm); Thông 3 giờ Scrum Master. 4.3 phải xong tuần 5 vì E1 cần nó. Backup 3 giờ của Châu ở bản 0.1 nay là story 2.8.

**Quyết định ở review G2** (Hiếu giữ, hỏi mentor trước): luật MDE > 10 điểm % (5 seed cho B và C, đổi chỉ tiêu, hoặc hạ HT thành mô tả) ghi vào RunPlan trước G3; trần GPU-giờ của B (N_B đã có công thức ở 5.2); ước sớm số lỗi Level 0 từ điểm lưới E1 gần 0,7D\* và cách đếm của luật 15 lỗi (05 MO1); chia ngân sách vòng C trên Ψ₀ khi chỉ có 1 vòng (60/40 hay dồn 100%, chờ spec); số vòng, ngân sách mỗi vòng, giao thức thu nhỏ của F-ACT và checkpoint làm nhánh C của ACT (05 MO2, MO3). Đã chốt theo 06, không cần quyết lại: tăng cường thị giác chung cho mọi nhánh, bootstrap phân cấp, B-fail thay B⁺, phép kiểm cho trễ camera và lệch calibration, luật NGOÀI MIỀN.

**Điều kiện qua G2.** 15 lần train E1 cộng seed thứ hai của Ψ₀ ở hai điểm quanh ngưỡng xong; D\* theo spec 7.1 (≥ 75%), hoặc luật trần, sàn đã kích hoạt và ghi lại; MDE đã tính, lựa chọn ghi vào RunPlan; `fw train` từ chối RunPlan vi phạm quy tắc công bằng hoặc trỏ `simple-checkpoints`; τ_cov trong RunPlan; guard gần trùng chạy trước khi E1 đánh giá trên dev; backup chạy hằng ngày; tuyến generator sinh được rollout cùng `embodiment_id` với teleop. **Demo.** Biểu đồ E1 ba phương pháp; `fw train` từ chối một RunPlan sai; vòng chẩn đoán trên bộ giả ra cụm và đề xuất.

### 4.4 Sprint 4 · Tuần 7–8 · G3

**Mục tiêu.** N_B chốt; dữ liệu sim nhánh B đạt QA, B_add đo từ sổ; train A, A₀.₇, B; π₀ và B-fail của ACT; A/A test; chạy thử chẩn đoán trên π₀ để kéo rủi ro của S5 lên sớm.

| PRD | Story | Nhãn | Người | Giờ | Phụ thuộc |
|---|---|---|---|---|---|
| 5.3 | Chọn ρ, train A, A₀.₇, B × 3 seed (A₀.₇ seed 0 trước, là π₀); báo lỗi dev theo mức | [Adapter] | Hiếu | 16 | 4.4, 5.2 |
| 5.4 | ACT, DP nhánh A, B × 3 seed; π₀ của ACT (0,7D\*, 1 seed) | [Adapter] | Châu | 10 | 4.4, 5.2 |
| 6.3 | Phép kiểm cần rollout, planner theo tuyến V3 | [Lõi] | Châu | 17 | 3.2, 6.1 |
| 7.4 | Teleop correction, dữ liệu phục hồi theo tuyến V3 | [Adapter] | Hưng | 14 | 6.4, 5.5 |
| 6.4 phần 2 | Hình ảnh chuẩn, contract test khôi phục | [Adapter] | Hưng | 8 | 6.4 phần 1 |
| 7.11 phần 1 | B-fail: sinh sim quanh mọi lỗi dev của π₀ ACT, chặn ở B_add | [Adapter] | Hưng | 12 | 5.2, 5.4, 2.4 |
| 6.2 phần 2 | Kiểm vùng phủ, golden test | [Lõi] | Long | 6 | 2.4 |
| 7.2 | g theo n_eff, chọn theo ngân sách, tỉ lệ sửa được đo có đối chứng | [Lõi] | Long | 16 | 3.6, 7.1 |
| 7.3 | Duyệt và ghi đè (`fw review`) | [Lõi] | Long | 8 | 6.6, 7.2 |
| 7.5 phần 1 | Điều phối thu dữ liệu nhánh C và B-fail | [Lõi] | Long | 7 | 5.2, 7.2 |
| 5.2 | N_B chốt trong RunPlan, điều phối sinh sim, đo B_add | [Lõi] | Thông | 14 | 2.3, 2.4, 5.1, 5.5 |
| 6.6 | Evidence card (Markdown, HTML) | [Lõi] | Thông | 14 | 6.1–6.3 |
| 2.8 phần 2 | Diễn tập khôi phục trước G3 | [Lõi] | Thông | 2 | 2.8 phần 1 |

Việc ngoài story: Hiếu 12 giờ (duyệt card chạy thử trên π₀, việc trưởng nhóm); Châu 4 giờ vận hành A100 cho 5.3 và A/A test; Hưng 2 giờ hỗ trợ sinh sim; Thông 6 giờ dựng bộ lỗi cấy chuẩn trên bộ giả, đóng vai red team cho mã chẩn đoán của Long và Châu (05 mục 3), 3 giờ Scrum Master. **Rủi ro.** Cần ít nhất 2 A100 song song cho khoảng 11 lần train Ψ₀ trong 2 tuần (05 KT4); chạm trần ở Level 0 (R03): với cách đếm hiện tại luật "dưới 15 lỗi Level 0" gần như chắc kích hoạt, mà đổi task ở tuần 8 khó kịp (05 MO1); B-fail dồn vào cuối S4 vì cần π₀ của ACT.

**Điều kiện qua G3.** N_B và trần GPU-giờ trong RunPlan trước khi sinh; rollout sim qua QA, tỉ lệ sinh đạt có trong sổ; B_add tính từ sổ; ρ chốt; A, A₀.₇, B của Ψ₀ và A, B của ACT, DP đã train và đánh giá trên dev; π₀ của ACT có; A/A test cho cổng xong; số lỗi dev theo mức của π₀ được báo, luật Level 0 áp theo cách đếm đã chốt ở G2; scorer đóng băng; diễn tập khôi phục đạt. **Demo.** Báo cáo B_add; bảng dev của các nhánh; vài evidence card thật trên π₀; một lỗi cấy trên bộ giả và kết quả chẩn đoán.

### 4.5 Sprint 5 · Tuần 9–10 · G4

**Mục tiêu.** 1 vòng Failure → Data trọn trên Ψ₀; vòng 2 trên Ψ₀ là phần thưởng, chỉ chạy nếu cổng dev của vòng 1 xong trước ngày làm việc thứ 4 của sprint và tải cho phép; F-ACT 5–8 vòng trên ACT; B-fail của ACT train; C cuối 3 seed; HD; holdout sớm và niêm phong cho nhánh không phụ thuộc C. Năng lực tính 80% vì kỳ nghỉ.

| PRD | Story | Nhãn | Người | Giờ | Phụ thuộc |
|---|---|---|---|---|---|
| 7.5 phần 2 | Thu dữ liệu nhánh C, chặn ngân sách | [Lõi] | Long | 8 | 7.4 |
| 7.6 | Vòng 1 nhánh C trên Ψ₀ (Long vận hành, Hiếu duyệt) | [Adapter] | Long | 14 | 3.6, 5.3, 6.6, 7.3, 7.5 |
| 6.5a | Wrapper cấy lỗi chung trong `runner` | [Lõi] | Long | 6 | 6.2, 6.3 |
| 6.5b | Cấy lỗi trên SIMPLE, recall theo lớp, đối chứng sạch | [Adapter] | Hưng | 12 | 3.1a, 6.5a |
| 7.7 | C cuối 3 seed từ checkpoint gốc; vòng 2 Ψ₀ chỉ khi đủ điều kiện | [Adapter] | Châu | 8 | 7.6 |
| 3.8 | Khóa holdout, niêm phong đợt sớm | [Lõi] | Châu | 10 | 2.5, 3.2 |
| 7.10 | F-ACT 5–8 vòng trên ACT, vận hành | [Adapter] | Châu | 16 | 3.6, 5.4, 7.2, 7.5 |
| 7.10, báo cáo | Posterior theo vòng, chi phí mỗi điểm % | [Adapter] | Thông | 8 | 7.10 |
| 7.11 phần 2 | Train B-fail của ACT × 3 seed, đánh giá dev | [Adapter] | Châu | 4 | 7.11 phần 1 |
| 8.1 | Công cụ HD: Rerun cộng đồ thị mặc định, card sai cố ý, bấm giờ bằng CLI | [Lõi] | Thông | 18 | 6.5, 6.6 |
| 8.2 phần 1 | Chạy HD phần lỗi cấy, ≥ 2 người ngoài đội | [Lõi] | Hưng | 8 | 7.6, 8.1 |
| 8.3 phần 1 | Holdout sớm, niêm phong: A, A₀.₇, B của Ψ₀; ACT; DP; B-fail của ACT | [Adapter] | Hưng | 8 | 3.8, 5.3, 5.4, 7.11 |

Việc ngoài story: Hiếu 20 giờ (duyệt vòng 1, tham gia HD, ký G4, việc trưởng nhóm); Hưng 4 giờ hỗ trợ rollout; Long 4 giờ review; Thông 3 giờ Scrum Master. 8.1 dựng trên bộ giả trong tuần 9 rồi nạp lỗi cấy của 6.5b. **Rủi ro.** Một vòng Ψ₀ mất 4–5 ngày (05 KT3); F-ACT tốn khoảng 630–850 rollout mỗi vòng, tranh máy với vòng Ψ₀ và holdout sớm (05 MO2); người ngoài đội cho HD khó xếp lịch vào kỳ nghỉ (R13).

**Điều kiện qua G4.** Sổ chi phí đủ cho C, tách chi phí thu và chi phí chẩn đoán; evidence card cho mọi cụm; C cuối đã train; F-ACT có báo cáo theo vòng; B-fail của ACT đã train; holdout sớm đã chạy, kết quả niêm phong, hash trong RunPlan; 6.5 đạt 8/10 cùng điều kiện cứng, có recall theo lớp và tỉ lệ báo nhầm trên đối chứng sạch; HD phần lỗi cấy xong. Phần lỗi tự nhiên của HD được phép trượt sang 2 ngày đầu S6 vì không dùng holdout. **Demo.** Một cụm đi trọn: card → `fw review` → thu → ứng viên → GateDecision; tổng hợp chi phí C; đường posterior của F-ACT; kết quả HD sơ bộ.

### 4.6 Sprint 6 · Tuần 11–12 · G5, G6

**Mục tiêu.** Holdout của C đúng một lần và mở niêm phong; ba đầu ra BTC; claim nào cũng có số đo hoặc bị gỡ. S6 không còn đệm riêng như bản 0.1; đệm nằm trong 30% của mọi sprint, mà mục 4.7 cho thấy đã bị dùng hết.

| PRD | Story | Nhãn | Người | Giờ | Phụ thuộc |
|---|---|---|---|---|---|
| 7.10 phần cuối | Train C của ACT × 3 seed từ checkpoint đã khai (ngày 1–2) | [Adapter] | Châu | 4 | 7.10 |
| 3.7 | Thống kê ghép cặp: bootstrap phân cấp, logistic hỗn hợp, Level 1–2 so với 70% (xong ngày 3) | [Lõi] | Thông | 18 | 3.2, 4.4 |
| 8.3 phần 2 | Đóng băng, precheck CI, holdout của C (Ψ₀ và ACT), mở niêm phong (Thông chứng kiến) | [Adapter] | Hưng | 12 | 3.7, 3.8, 7.7, 7.10, 8.3 phần 1 |
| 8.2 phần 2 | HD phần lỗi tự nhiên, r_debug dạng khoảng | [Lõi] | Hưng | 6 | 8.2 phần 1 |
| 7.8 | Báo cáo sổ chi phí, chi phí mỗi điểm % so với B và B-fail, độ nhạy | [Lõi] | Long | 14 | 2.7, 7.6, 7.11 |
| 8.4 | Báo cáo so sánh phương pháp, bảng 3 cấp BTC (Hiếu diễn giải) | [Lõi] | Long | 16 | 4.4, 7.8, 7.10, 8.2, 8.3 |
| 8.5 | SOP, Châu làm theo như người không viết | [Lõi] | Thông | 12 | 2.3, 2.6, 7.5 |
| 8.6 | Video demo (Hưng), rà claim (Hiếu) | [Adapter] | Hưng | 6 | 8.3, 8.4 |
| 3.4 phần F1 | Khung TaskDefinition `G1BendPick` (NFR7) | [Adapter] | Châu | 4 | 3.4 |

Việc ngoài story: Hiếu 26 giờ (diễn giải 8.4, rà claim 8.6, cập nhật pitch, ký G5, G6, việc trưởng nhóm); Châu 8 giờ hỗ trợ holdout ACT, DP và thử SOP; Thông 5 giờ chứng kiến holdout, bản tin, 3 giờ Scrum Master. **Rủi ro.** 3.7 nằm trên đường găng của precheck (8.3 AC 1): Thông viết phần lõi bootstrap từ S5 nếu còn giờ.

**Điều kiện qua G5, G6.** Theo spec 9: mỗi cặp (nhánh, seed) chạy holdout đúng một lần, kể cả đợt sớm; tiêu chí HS, HT (HTa, HTb) tính tự động; chỉ số chính từ cờ thành công của SIMPLE; Level 1, Level 2 báo riêng so với 70%; báo cáo, SOP, video, khuyến nghị thu dữ liệu định lượng có mặt; danh sách claim đã rà.

### 4.7 Tải từng người (giờ, H = 20, phạm vi mặc định trước khi cắt)

| Người | S1 | S2 | S3 | S4 | S5 | S6 | Tổng | So với mức 70% (146) | So với năng lực ròng (209) |
|---|---|---|---|---|---|---|---|---|---|
| Dương Đình Hiếu | 30 ⚠ | 29 ⚠ | 30 ⚠ | 28 ⚠ | 20 | 26 ⚠ | 163 | 112% | 78% |
| Trần Ngọc Hưng | 36 ⚠ | 36 ⚠ | 32 ⚠ | 36 ⚠ | **32 ⚠** | 24 | 196 | 134% | 94% |
| Trần Trịnh Hoàng Châu | 34 ⚠ | **37 ⚠** | **39 ⚠** | 31 ⚠ | **38 ⚠** | 16 | 195 | 134% | 93% |
| Nguyễn Thăng Long | 29 ⚠ | 35 ⚠ | **38 ⚠** | **37 ⚠** | **32 ⚠** | 30 ⚠ | 201 | 138% | 96% |
| Dương Tiến Thông | 26 ⚠ | **40 ⚠** | 35 ⚠ | **39 ⚠** | 29 ⚠ | **38 ⚠** | 207 | 142% | 99% |
| Tổng đội | 155 | 177 | 174 | 171 | 151 | 134 | 962 | 132% (730) | 92% (1.045) |
| Mức kế hoạch 70% mỗi người | 25 | 25 | 25 | 25 | 20 | 25 | 146 | | |
| Năng lực ròng mỗi người | 36 | 36 | 36 | 36 | 29 | 36 | 209 | | |

Mọi người vượt mức kế hoạch 70%; 10 ô vượt cả năng lực ròng (in đậm). Trong 163 giờ của Hiếu có khoảng 92 giờ việc trưởng nhóm. Nguồn tăng so với bản 0.1 (831 giờ, thêm 131 giờ): 5 story mới khoảng 106 giờ (5.5 là 36 giờ theo giả định tuyến T1 hoặc T2), trừ 23 giờ việc cũ mà chúng thay (phần V3 của S1-05, spike T2, một nửa 5.1, backup và diễn tập ngoài story); AC đổi ở 02 bản 0.3 khoảng 67 giờ (3.6, 3.7, 4.4, 6.2, 7.2, 7.8, 8.1, 8.3 tăng nhiều nhất); L0-lite bớt 5 giờ; 7.7 bớt 4 giờ vì mặc định 1 vòng; việc ngoài story bớt 10 giờ. Nếu tuyến là T3, 5.5 thêm khoảng 40 giờ cho Hưng và mức cắt 2–4 kích hoạt ngay.

### 4.8 Kết luận tải và phương án

**Kết luận.** Ở H = 20, phạm vi mặc định cần khoảng 962 giờ, bằng 132% mức kế hoạch 70% (730 giờ) và 92% năng lực ròng (1.045 giờ). Ước theo người-ngày của 02 §4 cho cùng kết luận: 200–215 so với 147. Kế hoạch này **không vừa** mức 70% của 06 mục 9. SM không giấu phần vượt; sprint đầu chạy theo bảng trên cho tới khi có quyết định dưới đây.

**Thứ tự cắt đã duyệt** (02 §8 bản 0.3, mục 7.2) tính bằng giờ người:

| Mức | Cắt | Giờ người bớt | Ai nhẹ đi | Bớt máy |
|---|---|---|---|---|
| 1 | B⁺ (7.9) và B-fail trên Ψ₀ | 0 | Không | Không nằm trong phạm vi mặc định; tránh 3–6 lần train Ψ₀ |
| 2 | Trình xem HTML và console HD | 8 | Thông 6, Long 2 | Không |
| 3 | Vòng 2 C trên Ψ₀ | 0 | Không | Không nằm trong phạm vi mặc định; tránh 1 lần train Ψ₀ và khoảng 630 rollout |
| 4 | F-ACT còn 5 vòng | 5 | Châu 4, Thông 1 | Bớt tới 3 lần train ACT và khoảng 1.900–2.500 rollout |
| 5 | Diffusion Policy 1 seed cho A, B | 3 | Châu 3 | Bớt 4 lần train DP |
| 6 | Phần lỗi tự nhiên của HD | 6 | Hưng 4, Thông 2 | Không |
| 7 | Diffusion Policy chỉ chạy E1 | 5 | Châu 5 | Bớt 2 lần train DP và holdout DP |
| 8 | Ψ₀ còn 2 seed (chỉ khi GPU vượt; HT thành mô tả) | 4 | Hiếu 2, Châu 2 | Bớt khoảng 4 lần train Ψ₀ |

Cắt mức 1–7 còn khoảng **935 giờ**, vẫn bằng 128% mức 70% và 89% năng lực ròng. Thứ tự cắt đã duyệt chủ yếu bớt GPU và rollout, chỉ bớt khoảng 3% giờ người. Sau cắt, tải từng người: Hiếu 163, Hưng 192, Châu 183, Long 199, Thông 198.

**Phương án chờ quyết** (Hiếu và PO quyết ở họp lập kế hoạch S1 ngày 26/10/2026, xem lại ở review G0 khi có k; câu hỏi 05 MO4):

| Phương án | Tác động | Đánh đổi | Ai quyết |
|---|---|---|---|
| A. Mỗi người cam kết H ≈ 25 giờ/tuần | Mức 70% lên khoảng 934 giờ, vừa nhu cầu sau mức 1–7 | Cần cân lại Long, Thông (199 so với 187 giờ mỗi người) | Từng người với Hiếu |
| B. V3 dương: 5.5 đóng "không cần" | Bớt khoảng 36 giờ (Hưng 28, Châu 8) | Không điều khiển được; biết ngày 5 | Theo kết quả S1-11 |
| C. Đo k sau S1 | k = 0,8 thì nhu cầu sau mức 1–7 còn khoảng 750 giờ, xấp xỉ mức 70% | Chỉ biết ở review G0 | SM tính |
| D. Cắt thêm ngoài danh sách đã duyệt: bỏ hẳn Diffusion Policy (M còn ACT và Ψ₀, vẫn đủ 2 phương pháp theo đề) | Bớt thêm khoảng 12 giờ sau mức 7 | Báo cáo so sánh phương pháp mỏng hơn | PO, sửa 02 §8 |
| E. Lập kế hoạch ở 85% như bản 0.1 | Mức kế hoạch lên khoảng 888 giờ ở H = 20; không bớt việc | Trái 06 mục 9; đệm còn 15% | Hiếu, ghi ngoại lệ vào 06 |

Nếu H = 20 và k ≥ 1: mức 1–7 cộng B và D còn khoảng 887 giờ, vẫn 122% mức 70%. Khi đó chỉ còn chọn E, hoặc bỏ bớt một phần giả thuyết phụ (ví dụ HD chỉ còn lỗi cấy và card sai; F-ACT chỉ chạy đủ để có nhánh C của ACT cho HTb). **Đề xuất của SM:** chốt H thực ở họp lập kế hoạch S1; áp sẵn mức 1–7 từ đầu dự án như 02 §4 yêu cầu, trừ khi phương án A được cam kết; quyết B và C ở review G0; nếu sau G0 vẫn vượt 110% mức 70% thì PO chọn D rồi E.

### 4.9 Phạm vi thêm ngày 23/10/2026

Theo spec v10.2 và [design ngày 23/10/2026](../superpowers/specs/2026-10-23-data-pipeline-and-failure-eval-design.md): robot DENSO (hoặc robot thay thế) trong Isaac Sim với task khay → máy, pipeline dữ liệu ba nguồn, synthetic S1–S4 qua NIM, probe theo stage của Ψ₀, log train theo nhóm action và bảng lỗi 5 nguồn.

Ước theo 14 story DA-01…DA-14 ở [07 mục 2.2](07-team-workflow.md) (ước thô ban đầu của design là 160–220 giờ):

| Hạng mục | Story | Giờ người | Pha |
|---|---|---|---|
| Robot thay thế và cảnh trạm làm việc | DA-10, DA-11 | 40–60 | A |
| Định dạng chung, export, pipeline teleop và egocentric | DA-01–DA-04 | 61–84 | A, bộ đọc DENSO ở B |
| NIM và tầng S3 | DA-05, DA-06 | 27–35 | A |
| Log train, phát hiện lỗi train, probe P1–P4 | DA-07–DA-09 | 30–44 | A |
| Task khay → máy và scorer | DA-12 | 15–20 | A |
| Quy lỗi về stage | DA-13 | 8–10 | A |
| Xin thông tin DENSO | DA-14 | 3 | A |
| **Tổng** | | **khoảng 185–255** | Chưa nằm trong khoảng 962 giờ ở mục 4.8 |

Tải từng người sau khi cộng phần này ở 07 mục 2.3.

**Quyết định của trưởng nhóm (23/10/2026):**

1. Giữ đủ phạm vi, không cắt trước. Ước lượng ở mục 0 đã tính việc dùng AI viết mã; mức tăng tốc thật đo bằng k sau Sprint 1.
2. Khi vượt thời gian, **thay phần tự xây bằng API theo từng phần trước** (design mục 11), mỗi lần ghi Decision và chi phí API; quy tắc định tuyến dữ liệu theo `data_class` không nới.
3. Nếu sau bước 2 vẫn vượt 110% mức kế hoạch ở review G0, áp thứ tự cắt mục 7.2, rồi cắt phần mới theo thứ tự S4, U4, E-A trên dữ liệu thật, S2-B.

Story cho phần này chưa viết. SM tách story theo design mục 11 ở họp lập kế hoạch Sprint 1 và giao người theo RACI mục 3.3; Hiếu gửi danh sách 21 mục cần xin DENSO (design mục 9) trong tuần 1.

### 4.10 Thay đổi ngày 25/10/2026: robot DENSO trên MuJoCo

Theo spec v10.3 và [design ngày 25/10/2026](../superpowers/specs/2026-10-25-denso-mujoco-and-stage-qa-design.md). Thí nghiệm có đối chứng chạy trên robot DENSO trong MuJoCo; SIMPLE chỉ còn G0; Isaac Sim sau demo.

**Story mới** (07 mục 2.2). Giờ là ước lượng thô của SM, chốt lại khi viết file story:

| Story | Việc | Người | Giờ | Sprint |
|---|---|---|---|---|
| DA-15 | Robot DENSO tương đương (MJCF), cảnh trạm, task khay → máy, planner | Hưng | 25–35 | S1–S2 |
| DA-16 | Teleop bàn phím, ghi episode | Hưng | 10–15 | S1 |
| DA-17 | Phát lại action hai chế độ | Châu | 8–12 | S1–S2 |
| DA-18 | Egocentric thô → định dạng EgoDex cho stage 1 | Long | 20–30 | S2–S3 |
| DA-19 | Đọc code train của tác giả, lớp bọc log cho 3 stage (gộp DA-07), adapter train trên Colab | Hiếu | 20–28 | S1–S2 |
| DA-20 | Agent QA/QC (Nemotron), dựng hình từng stage, bộ ca mẫu | Thông | 20–30 | S2–S3 |
| DA-21 | Export LeRobot v3, checklist chuẩn hóa | Thông | 4–6 | S2 |
| DA-22 | Đọc và phân tích dataset BTC | Thông | 8–12 | S1 |
| DA-23 | Eval bất đồng bộ trên MuJoCo, log inference RTC | Châu | 10–15 | S2 |
| **Tổng** | | | **khoảng 125–183** | |

**Phần bớt** (ước lượng): S1-05 6 giờ, S1-11 18 giờ, story 5.5 tuyến generator 36 giờ, phần thu nhỏ của S1-02 và S1-06 khoảng 12 giờ, S1-07 12 giờ thay bằng DA-22; DA-07 10–14 giờ gộp vào DA-19; DA-10 gộp vào DA-15 và DA-11 (cảnh Isaac Sim) dời sau demo, bớt khoảng 40–60 giờ trong 12 tuần. Tổng bớt khoảng 135–160 giờ, nên tổng tải gần như không đổi; phân bố theo người ở 07 mục 2.3. Tốc độ đo đầu tiên (S1-01, S1-08) cho thấy phần viết mã nhanh hơn ước lượng 3–10 lần; k chính thức tính sau Sprint 1 (mục 8).

**Máy chạy.** RTX 3060 12 GB cho dev, MuJoCo, ACT, DP, Agent QA/QC; Colab Pro (A100, H100) cho train Ψ₀. S1-04 đo giờ một lần train Ψ₀ trên một GPU trước review G0; nếu tổng số lần train ở spec mục 9 vượt ngân sách, vòng lặp chạy trên ACT và DP, Ψ₀ giữ cho nhánh cuối. Dữ liệu DENSO chưa được lên Colab (design 25/10 mục 9).

**Điều kiện qua G0 thêm** (bản 0.4): robot DENSO tương đương chạy trong MuJoCo; teleop bàn phím ghi được episode qua QA và phát lại; giờ người của 20 demo thử đã đo; giờ một lần train Ψ₀ trên Colab đã đo; bỏ điều kiện V3 và T1, T2.

**Quy trình.** Hiếu là người duyệt và merge duy nhất vào `master` (08 mục 3, RULE mục 4). Lịch tracking tự động lúc 10:00, 14:00, 18:00 và tổng kết cuối ngày lúc 21:30 thay cho người review dự phòng của R2. Không ai phải chờ ai: mỗi chỗ nối có schema trong `contracts`, bản giả trong `flywheel-fakes` và file mẫu (design 25/10 mục 10.1).

## 5. Định nghĩa Sẵn sàng và Hoàn thành

### 5.1 Definition of Ready (story được kéo vào sprint)

1. Có file story theo mẫu ở `stories/`, trạng thái "Sẵn sàng".
2. Câu story nêu vai, mong muốn, lợi ích; tiêu chí chấp nhận đánh số, kiểm được bằng lệnh, test hoặc tài liệu.
3. Trỏ về story PRD, FR hoặc NFR, mục 03 và mục spec liên quan.
4. Phụ thuộc đã xong, hoặc có adapter giả thay thế.
5. Có người phụ trách, người review, người dự phòng; ước lượng ≤ 20 giờ, lớn hơn thì tách (ví dụ 5.5 tách theo sprint khi tuyến đã chốt).
6. Nhu cầu máy đã đặt lịch: GPU nào, bao nhiêu giờ, có cần A100 thuê.
7. Có nhãn epic, [Lõi] hoặc [Adapter], cổng.
8. Story [Adapter]: Protocol mà nó cài đã có phiên bản trong `contracts`.
9. Story chạy thí nghiệm: có RunPlan nháp.

### 5.2 Definition of Done chung

1. Mọi tiêu chí chấp nhận đạt; người review xác nhận trên PR.
2. CI xanh: ruff, mypy, pytest, import-linter.
3. Lệnh mới có `--help`.
4. Mọi lần chạy tiêu GPU hoặc giờ người có mục sổ; số lần chạy thiếu mục sổ bằng 0.
5. Không đọc holdout ngoài 02 · 3.8 và 8.3; không mở kết quả niêm phong trước G5.
6. Không commit dữ liệu, checkpoint, video, khóa bí mật.
7. Có ghi chú ngắn trong README của module hoặc package.
8. File story cập nhật: nhiệm vụ đã tick, mục "Ghi chép khi làm" có giờ thực và danh sách file, change log, trạng thái "Xong".
9. Kết quả âm và mẫu bị loại được giữ, không xóa.
10. Dữ liệu không tái tạo được mà story tạo ra (catalog, release, vault, ledger, episode do người thu) nằm trong phạm vi job backup (02 · 2.8, 03 §10.4).

### 5.3 Thêm cho story [Lõi]

1. Test chạy trên CPU với adapter giả; không cần SIMPLE, Isaac Sim, MuJoCo hay Ψ₀ để chạy test.
2. Import-linter chứng minh `flywheel` không import package adapter hay thư viện model.
3. Bước tính thuần (QA, scorer trên trace có sẵn, chẩn đoán từ log, decide, thống kê): cùng đầu vào cho cùng đầu ra, có test.
4. Đổi schema thì tăng `schema_version` và xuất lại JSON Schema.
5. Vòng end-to-end trên bộ giả vẫn xanh dưới 10 phút.
6. Logic có ví dụ tính tay (Beta có đối chứng, g theo n_eff, c, bootstrap phân cấp, MDE, D\*) thì có test so với ví dụ đó.

### 5.4 Thêm cho story [Adapter]

1. Qua bộ contract test dùng chung trong `flywheel.testing`: với bộ giả trong CI, với bản thật bằng marker `gpu` trên máy 5090; log lần chạy gắn vào PR.
2. `capabilities()` khai trung thực; không hỗ trợ thì trả `False`, không giả lập.
3. Idempotent theo `job_id`; lỗi hạ tầng nằm ở `infra_status`, không thành `sim_success = False`.
4. Đổi đơn vị và khung tại biên theo 03 §4.1.
5. Ghi đủ phiên bản: digest image, commit SIMPLE, revision HF, phiên bản bộ sinh.
6. Có runbook chạy lại trong README của package.
7. Story spike ở G0: câu trả lời ghi vào file của story trong `docs/g0/`, kèm mục đề xuất cho dòng tương ứng của 03 §3.3; Hiếu gom vào 03 §3.3 ở review G0, có change log (bản 0.3, quy ước ở [docs/g0/README.md](../g0/README.md)); người review chạy lại được ít nhất một lệnh từ tài liệu.

## 6. Lịch làm việc với mentor

Chuyên môn của mentor chưa rõ (00 §8 câu 2). Buổi S0 xác định mảng mentor mạnh; câu hỏi ở mảng mentor không mạnh thì Hiếu xin mentor giới thiệu người khác hoặc hỏi BTC. Mã câu hỏi theo 05 mục 6. Câu đã chốt theo 06 (RL7, DS1, DS5, DS6, TK1, TK8) chỉ còn để mentor xác nhận hoặc phản bác. MO4 và MO5 là câu hỏi nội bộ, trả lời ở họp lập kế hoạch S1 và story 2.8, không cần mentor.

| Khi | Mang tới | Câu hỏi trong 05 | Mảng | Kết quả mong đợi |
|---|---|---|---|---|
| S0 · trước 26/10 | 00–06, tóm tắt kế hoạch này và mục 4.8 | RL1, RL7 (xác nhận), SI3, DS7, DN1, DN7 | Robot learning, dữ liệu, DENSO | Biết mảng mạnh của mentor; ý kiến về checkpoint gốc, định vị sau Mulligan và B-fail; mã đề, cách chấm 3 cấp; nhịp gặp |
| S1 · review G0 | `docs/g0/`, bảng V3 và kết quả T1, T2, cấu hình Ψ₀, ngân sách GPU, số đo t và W | RL2, RL3, SI1, SI2, SI4, DS1 (xác nhận), DS5 (xác nhận), DN2, DN3, MO1, MO2 | Robot learning, simulation, hệ thống dữ liệu | Chốt tuyến V3; xác nhận L0-lite; task dự phòng khó hơn và cách đếm lỗi Level 0; thông lượng F-ACT |
| S2 · review G1 | Báo cáo hiệu chỉnh scorer, báo cáo QA, kế hoạch thống kê | RL4, RL5, DS2, DS3, DS4, TK1 (xác nhận), TK3, TK6, TK8 (xác nhận), DN4, DN5, DN6 | Thống kê, robot learning, dữ liệu | Số bước S cho E1; độ lệch seed dự kiến; guard chống rò; biên không kém |
| S3 · review G2 | Đường cong E1, D\*, power analysis, MDE, RunPlan F-ACT nháp | RL6, RL8, SI5, SI6, DS6 (xác nhận), TK2, TK4, MO1, MO3 | Robot learning, thống kê | Ý kiến cho các quyết định G2 ở mục 4.3; checkpoint làm nhánh C của ACT |
| S4 · review G3 | Kết quả B, B_add, card thật trên π₀, thiết kế HD, kết quả A/A | TK5, TK7 | Thống kê, robot learning | Chốt cách chạy cổng dev và HD; mời mentor làm người ngoài đội trong HD |
| S5 · review G4 | Kết quả vòng 1, sổ chi phí C, posterior F-ACT | SI7; mentor tham gia HD | Simulation, sim-to-real | Phản biện C và F-ACT; giới hạn claim L2 |
| S6 · trước G6 | Bản nháp báo cáo, danh sách claim của pitch | Bảng claim ở 05 mục 2.1 | Toàn bộ | Claim nào giữ, sửa, gỡ |

Thông ghi biên bản ngắn vào issue "Mentor S<n>"; quyết định chép vào change log của tài liệu bị ảnh hưởng.

## 7. Phương án khi trễ

### 7.1 Khi nào cắt

Áp mức cắt kế tiếp khi: một cổng dự báo trễ quá 3 ngày làm việc; nhu cầu còn lại vượt mức kế hoạch 70% còn lại sau khi đã áp quyết định ở mục 4.8 (mục 0), hoặc k > 1,3; GPU đã tiêu vượt 125% kế hoạch tới ngày đó. Hiếu quyết ở review sprint hoặc họp tuần; Thông ghi vào change log của 02 §8 và file này.

### 7.2 Thứ tự cắt (PO duyệt bản 0.2 của 02, PM sửa theo 06 ở 02 bản 0.3)

**Phạm vi mặc định:** nhánh C trên Ψ₀ chạy 1 vòng; vòng thêm chạy trên ACT (F-ACT, 7.10); vòng 2 trên Ψ₀ là phần thưởng theo điều kiện ở mục 4.5. Holdout của nhánh không phụ thuộc C chạy sớm và niêm phong tới G5. B-fail chạy trên ACT; trên Ψ₀ chỉ khi còn ngân sách sau G4. B⁺ (7.9) không lên lịch, ưu tiên thấp hơn B-fail.

1. Nhánh B⁺ (7.9) và B-fail trên Ψ₀, nếu đã mở.
2. Trình xem HTML và console HD; giữ card và sổ chi phí dạng Markdown, bấm giờ HD bằng CLI.
3. Vòng 2 của nhánh C trên Ψ₀, nếu đã mở; C cuối train trên release sau vòng 1.
4. F-ACT còn 5 vòng.
5. Diffusion Policy chỉ 1 seed cho nhánh A và B; ACT giữ 3 seed ở B và B-fail vì HTa dựa vào đó.
6. Phần lỗi tự nhiên của HD; giữ 10 lỗi cấy và card sai cố ý.
7. Diffusion Policy chỉ chạy E1, không chạy nhánh A, B và holdout.
8. Ψ₀ còn 2 seed cho nhánh chính, chỉ khi GPU vượt ngân sách (spec 10); khi đó HT tự động thành kết quả mô tả.

Giờ người mỗi mức bớt được ở mục 4.8.

### 7.3 Không bao giờ cắt

- QA bắt buộc; lineage và giấy phép trên mọi episode.
- Chia tập theo hạt giống trước khi train; guard gần trùng; holdout chạy đúng một lần; không rò holdout.
- Nguồn gốc checkpoint gốc (Q0).
- Sổ chi phí: mọi lần chạy có mục sổ, kể cả lần hỏng và mẫu bị loại.
- Quy tắc công bằng spec 7.3; tiêu chí HS, HT (HTa, HTb) chốt trước holdout.
- Kiểm hệ thống trước dữ liệu; cấm trộn embodiment không tương thích (V3).
- Đo tỉ lệ sửa được có đối chứng và A/A ở cổng dev.
- Backup hằng ngày.
- Báo cáo kết quả âm, ứng viên bị từ chối, giới hạn của HD và của mô phỏng.

### 7.4 Kịch bản lớn

| Kịch bản | Phản ứng |
|---|---|
| G0: Ψ₀ không tái tạo được | Thêm tối đa 1 tuần, nhờ mentor; vẫn hỏng thì Hiếu và mentor chọn model chính khác có sẵn trong SIMPLE, lõi giữ nguyên |
| V3 âm, T1 và T2 đều hỏng | Theo cây ở 1.3; T3 kéo theo cắt mức 2–4 ngay; T4 cần đồng ý của Hiếu và mentor |
| V3 âm và Q6 âm | C chỉ còn kiểm demo mâu thuẫn; HT sụp; ghi vào báo cáo. HS còn kiểm được nếu B có dữ liệu qua tuyến đã chọn hoặc T4; HD vẫn chạy |
| Level 0 có dưới 15 lỗi sau G3 | Kích hoạt task khó hơn đã khai ở spec 7.1; vì đổi task ở tuần 8 khó kịp, ước sớm ở G2 và khai sẵn task từ G0 (05 MO1) |
| Ngân sách GPU không được duyệt | LoRA hoặc đóng băng VLM; áp mức cắt 8; giảm ô Ψ₀ |
| Máy 5090 hỏng | Khôi phục từ backup sang máy 3060 theo diễn tập (2.8); mục tiêu dựng lại trong nửa ngày |
| Một người vắng hơn 1 tuần | Người dự phòng ở mục 3.1 nhận story đang làm; SM tính lại tải trong 1 ngày |

## 8. Theo dõi tiến độ

Thông cập nhật mỗi thứ Hai, đăng thành bình luận trong issue ghim "Bản tin tuần". Hiếu dùng bản này gửi DENSO, BTC khi cần.

| Chỉ số | Cách đo | Ngưỡng cảnh báo |
|---|---|---|
| Story xong so với kế hoạch | Số story và tổng giờ ước đã "Xong" trên GitHub Project | Giữa sprint dưới 40% |
| Trạng thái cổng | Xanh, vàng, đỏ; số ngày trễ dự báo | Đỏ khi trễ quá 3 ngày |
| Giờ thực so với kế hoạch | Trường "Giờ thực" từng người; H thực trung bình | Một người trên 110% hai tuần liền, hoặc dưới 70% |
| Tải so với mức 70% | Nhu cầu còn lại × k so với mức kế hoạch còn lại (mục 0) | Trên 100% sau khi đã áp mục 4.8 |
| Hệ số k | Giờ thực / giờ ước của story đã xong | Trên 1,3 |
| Chi phí GPU | A100-giờ và USD lũy kế so với ngân sách; giờ máy 5090, 3060 | Trên 125% kế hoạch tới ngày |
| Lần chạy thiếu mục sổ | Báo cáo của `ledger`; trước S2 là CSV G0 | Khác 0 |
| Lần đọc holdout trước G5 | Log của vault, kể cả lần mở kết quả niêm phong | Khác 0 |
| Backup | Thời điểm backup cuối, kết quả so hash | Trễ quá 1 ngày |
| CI nhánh chính | Phần trăm ngày xanh | Dưới 90% |
| Vướng mắc | Số issue `blocked` và tuổi | Quá 2 ngày thì đưa lên họp tuần |
| Câu hỏi chặn của 05 | Số câu **[Chặn]** và câu hỏi mở (05 mục 6.6) chưa có câu trả lời | Còn câu của sprint hiện tại ở review |
| Dấu hiệu sớm của 05 mục 5 | Mỗi người giữ rủi ro kiểm dấu hiệu của mình | Có dấu hiệu thì báo ngay trong check-in |
| Chỉ số flywheel (từ S4) | Tỉ lệ ghi đè, recall lỗi cấy theo lớp, số cụm CHƯA RÕ, độ rộng CI của f_t theo vòng F-ACT | Ghi đè trên 50%; CI không hẹp sau 3 vòng F-ACT |

**Người giữ rủi ro** theo sổ rủi ro 05 mục 5: Hiếu giữ R02, R03, R11, R13 (cùng Hưng), R14, R17, R18; Hưng giữ R01, R08 (phần cấy lỗi), R12, R15; Châu giữ R05, R16 (cùng Thông, theo 2.8); Long giữ R07, R08 (phần phép kiểm), R10; Thông giữ R04, R06, R09.
