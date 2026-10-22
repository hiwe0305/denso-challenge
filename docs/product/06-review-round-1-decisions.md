# 06 · Quyết định áp dụng phản biện vòng 1

_Ngày 22/10/2026. Trưởng nhóm duyệt áp dụng 10 sửa ưu tiên ở [05 mục 7](05-review-and-mentor-questions.md). File này chốt **cách** áp dụng từng sửa để spec và 00–03 sửa thống nhất. Mã đề giữ "H1" cho đến khi BTC xác nhận (ảnh đề ghi H2, xem [đề bài](../challenge/README.md)). Mục 11 (thêm ngày 23/10/2026) ghi các quyết định của trưởng nhóm sau phản biện vòng 1, làm căn cứ cho spec v10.2 và các bản cập nhật cùng ngày._

## Quy ước đổi tên áp dụng cho mọi tài liệu

| Cũ | Mới | Nghĩa |
|---|---|---|
| Giả thuyết H1 | **HS** | Sim thay được 30% demo teleop |
| Giả thuyết H2 | **HT** (tách **HTa**, **HTb**) | HTa: nhắm theo lỗi tốt hơn bổ sung đều. HTb: chẩn đoán giúp thêm ngoài việc chỉ nhắm theo lỗi |
| Giả thuyết H3 | **HD** | Evidence card giảm thời gian chẩn đoán |

Chỉ đổi khi "H1/H2/H3" là tên giả thuyết. **Không** đổi: mã đề ("thử thách H1", "đề H1"), robot "Unitree H1", "PPO H1".

## 1. Bộ điều khiển teleop và motion planning (V3)

- Spec 2.1: System-0 của task chính là **decoupled WBC (`g1_sonic`, env `SonicLocoManipEnv`)**; AMO là bộ điều khiển của pipeline MP. Kiểm hệ thống (6.4) nhắm vào stack WBC; "lệnh gửi" và "trạng thái đo" định nghĩa theo giao diện WBC (lệnh thân trên, lệnh thân dưới).
- Thêm câu hỏi **V3** vào G0 với **hạn ngày 5 của Sprint 1**: rollout MP có cùng bộ điều khiển với teleop không, nếu không thì ánh xạ được không.
- Bốn tuyến khi V3 âm, ghi vào mục rủi ro: **T1** tái thực thi quỹ đạo MP trong env WBC (1–2 tuần); **T2** biến thể kiểu MimicGen / IntervenGen từ đoạn teleop, chạy IK cộng WBC (2–3 tuần); **T3** planner trong env WBC (2–4 tuần); **T4** chuyển sang env MP và thu hẹp claim (vài ngày, phương án cuối). Thử T1 và T2 song song tuần 1–2, chốt cuối tuần 2.
- Task F1 **không còn là dự phòng cho Q2** cho tới khi V3 xác nhận cặp task của F1 cùng bộ điều khiển; F1 giữ vai trò kiểm khả năng tổng quát của lõi.
- Kịch bản V3 âm và Q6 âm: C chỉ còn kiểm demo mâu thuẫn; HT sụp; phải ghi vào báo cáo.
- PRD: tách V3 thành story riêng hạn ngày 5; thêm story "xây tuyến generator đã chọn" (1–4 tuần) ở epic sinh dữ liệu.

## 2. Thống kê

- Khoảng tin cậy dùng **bootstrap phân cấp**: lấy mẫu lại seed huấn luyện, rồi lấy mẫu lại điều kiện trong từng mức. Mô hình logistic hỗn hợp (hiệu ứng ngẫu nhiên theo điều kiện và theo seed) chạy làm kiểm tra chéo.
- Quy tắc "cùng chiều ở ≥ 2/3 seed" chỉ còn là chỉ số phụ.
- **Power analysis ở G2:** chạy 2 seed ở mức D\* trong E1 để đo độ lệch giữa seed; tính hiệu ứng nhỏ nhất phát hiện được (MDE) với 80% lực. Nếu MDE > 10 điểm %: tăng Ψ₀ lên 5 seed cho B và C, hoặc chuyển chỉ tiêu chính của HT sang mức còn dư địa, hoặc hạ HT thành kết quả mô tả. Nếu phải cắt về 2 seed thì HT tự động thành mô tả.
- D\*: chạy 2 seed ở hai điểm lưới quanh ngưỡng (hoặc nội suy đường cong) để tránh chọn nhầm do may mắn.
- Cổng G0: thay "lệch không quá 1/10" bằng **30 lượt mỗi mức** hoặc kiểm nhị thức một phía.

## 3. Chọn can thiệp và tỉ lệ sửa được

- Lợi ích kỳ vọng tính theo **số lỗi thực được xử lý sau khi áp giới hạn mỗi cụm**: g_j = (n_eff_j / N) × f̄_t, với n_eff_j = min(m_j, giới hạn của loại can thiệp). Hòa thì ưu tiên bước hỏng sớm hơn.
- Ghi rõ: ở vòng 1 (prior đều), thứ tự chọn chỉ là **đơn giá của loại can thiệp trong các loại mà chẩn đoán cho phép**. Có unit test chứng minh tính chất này.
- **Đo tỉ lệ sửa được có đối chứng:** với mỗi cụm, lấy điều kiện mới quanh điểm lỗi (bán kính τ_cov / 2, tối đa 5 điều kiện mỗi lỗi, tối đa 30 mỗi cụm); chạy policy cha và ứng viên mỗi bên ≥ 3 lượt. fixed_j = làm tròn(n × (p_ứng viên − p_cha)), kẹp trong [0, n]; α += fixed_j, β += n − fixed_j.
- **Cổng dev mỗi vòng dùng một tập điều kiện mới** (từ dải hạt giống dev, chưa dùng), chạy cả cha và ứng viên, ≥ 3 lượt mỗi điều kiện. **A/A test** (chạy cha hai lần) cho sàn hồi quy giả; ngưỡng hồi quy = max(5%, sàn A/A). "Tăng" phải ≥ 1 sai số chuẩn.
- **Thí nghiệm F-ACT:** chạy 5–8 vòng Failure → Data rẻ với ACT trên cùng task để có bằng chứng "flywheel học" (tỉ lệ sửa được ổn định dần, chi phí mỗi điểm % giảm). Không dùng Ψ₀ cho phần này.
- 00 §3: bỏ câu "thứ đối thủ không có sẵn"; tỉ lệ sửa được là tài sản cần đo ở L1.

## 4. Công bằng giữa các nhánh

- **Lượng dữ liệu của B chốt trước G3:** N_B = 2 × (D\* − 0,7D\*) rollout sim đạt QA (làm tròn lên), kèm trần GPU-giờ; ghi vào RunPlan. **B_add là chi phí thực đo để tạo đúng N_B rollout đó**; C bị chặn ở B_add.
- **Tăng cường thị giác là phần cố định của recipe, áp như nhau cho mọi nhánh** (khai trong RunPlan), không còn là can thiệp riêng của C. Chẩn đoán NHẬN THỨC vẫn được ghi nhận và báo cáo, không tiêu ngân sách trong PoC.
- **Kiểm demo mâu thuẫn chỉ ra báo cáo**, không loại demo khỏi danh sách 0,7D\* (giữ cùng danh sách cho A₀.₇, B, C).
- Báo riêng số demo người (teleop và correction) của từng nhánh.
- Luật mới **NGOÀI MIỀN:** lỗi có điều kiện nằm ngoài miền train (ví dụ vị trí vật của Level 2 ngoài khoảng train) được chẩn đoán NGOÀI MIỀN, không tiêu ngân sách, được báo cáo.
- Ngay sau G3, báo số lỗi dev theo mức của π₀; nếu Level 0 có dưới 15 lỗi, kích hoạt task khó hơn đã khai ở spec 7.1.
- **Nhánh B-fail** (thay vai trò ưu tiên của B⁺): sinh sim quanh mọi điều kiện lỗi dev, không chẩn đoán, cùng ngân sách với C (kiểu Mulligan rút gọn). Chạy trên ACT là chính; trên Ψ₀ nếu còn ngân sách sau G4. HTa: B-fail so với B. HTb: C so với B-fail. B⁺ giữ tùy chọn, ưu tiên thấp hơn B-fail.

## 5. Phép kiểm cho lỗi cấy và thí nghiệm HD

- Thêm hai phép kiểm hệ thống vào bước 4: **đồng bộ cảm biến** (lệch thời gian giữa khung ảnh và state vượt τ_sync, hiệu chỉnh từ demo teleop thành công) và **camera chuẩn** (tham số camera hoặc tư thế camera khác bản tham chiếu đã hash). Thêm hai chẩn đoán tương ứng vào bảng quyết định: LỖI ĐỒNG BỘ, LỖI CALIBRATION (đều sửa hệ thống, không tiêu ngân sách dữ liệu).
- Tiêu chí của story chẩn đoán lỗi cấy: báo **recall theo từng lớp** và **đối chứng sạch** (episode không cấy lỗi, đo tỉ lệ báo nhầm).
- HD: **≥ 2 người ngoài đội** (mentor hoặc đội khác); đối thủ là công cụ chuẩn (Rerun cộng đồ thị mặc định), không phải log do đội tự đóng gói; chèn 3–4 evidence card sai cố ý để đo mức tin mù quáng; r_debug báo dạng khoảng.

## 6. Định vị lại tính mới

Câu định vị dùng thống nhất: _Humanoid Data Flywheel là quy trình vận hành có kiểm toán cho vòng lỗi → dữ liệu: loại lỗi hệ thống trước khi tiêu tiền vào dữ liệu, chọn giữa nhiều loại can thiệp theo chi phí thật kể cả chi phí chẩn đoán, và xuất **khuyến nghị thu dữ liệu định lượng** cho DENSO. PoC kiểm lại trên G1 toàn thân với Ψ₀ xem "nhắm lỗi thắng rải đều" có còn đúng khi tính đủ chi phí._

- HT gọi là **kiểm lại (replication)** kết quả kiểu Mulligan / DISEIL, không còn là "điểm khác biệt chính".
- "Chưa ai ghép đủ" sửa thành "trong phạm vi đã tra ngày 22/10/2026, chưa thấy…"; các ô "Có" của L0 trong bảng khoảng trống đổi thành "Mục tiêu, chưa đo".
- Thêm tiền lệ IntervenGen (sinh correction hàng loạt từ ít can thiệp người) và CUPID (chọn demo bằng influence function); ghi Mulligan dùng dữ liệu lỗi để học value function; "dùng dữ liệu lỗi để train" là hướng L1.
- Data Core cộng SOP được gọi là **"DENSO Data Model"** như tên đề.

## 7. Tiêu chí BTC và chỉ tiêu

| Cấp BTC | Tiêu chí | Chỉ tiêu trong PoC |
|---|---|---|
| 1 · Basic | ≥ 50% với lượng demo nhỏ | Báo tỉ lệ thành công ở các mức 10% và 25% của đường cong E1 |
| 2 · Efficient | Giảm ≥ 30% demo cùng hiệu năng; ≥ 75% | HS: B ở 0,7D\* không kém A và đạt ≥ 75% |
| 3 · Advanced | ≥ 70% trên biến thể chưa train; khuyến nghị thu dữ liệu định lượng | Báo riêng Level 1 và Level 2 của holdout so với 70%; đầu ra của bước Decide cộng sổ chi phí là khuyến nghị định lượng |

- **D\*** = mức demo nhỏ nhất để Ψ₀ đạt **≥ 75%** trên dev gộp (theo Cấp 2), thay cho 80%.
- Pitch v10 vẫn ghi "≥ 80% / 50 lượt"; cần cập nhật pitch sau (ngoài phạm vi lần sửa này).

## 8. Nguồn gốc checkpoint và chống rò

- **Q0 vào G0:** chọn checkpoint `pre.*` hoặc `postpre.*` đã xác nhận không train trên dữ liệu SIMPLE hoặc sonic của task chính; hỏi PSI Lab; ghi nguồn gốc vào thực thể Source.
- RunPlan mẫu **không trỏ** `simple-checkpoints` hoặc `sonic-checkpoints` cho E1 và các nhánh; hai thư mục này chỉ dùng để tái tạo số công bố ở G0.
- Thêm **guard gần trùng theo khoảng cách điều kiện**: điều kiện dev hoặc holdout có khoảng cách tới train dưới phân vị 1 của khoảng cách láng giềng trong train thì bị cách ly.
- Dải hạt giống dev và holdout rời với dải tác giả dùng cho psi-data và `simple-eval` (nếu không biết dải của tác giả thì chọn dải lệch xa và dựa vào guard khoảng cách).

## 9. Năng lực và kiến trúc L0-lite

- Lập kế hoạch ở **70% năng lực**; lát dọc chạy trên SIMPLE **trước tuần 4**.
- **Kiến trúc L0-lite:** gộp còn khoảng 12 thực thể ở L0, trường mở rộng để trong `meta`; hoãn MLflow (trùng ledger), Streamlit, fsspec S3, revision của evidence card, phân vùng theo ngày và lệnh dựng lại chỉ mục. Giữ hash release, RunPlan, guard chia tập, khóa holdout dạng tệp có hash cộng test CI, ledger JSONL, trace Parquet, một chỉ mục DuckDB.
- **Giữ `task_id`, `embodiment_id`, `site_id` là cột thường có giá trị mặc định** ngay từ L0 (gần như không tốn công, giữ đường mở rộng L1–L4 mà người dùng ưu tiên).
- Đồng sở hữu Ψ₀ (Châu, theo 04); **mặc định 1 vòng C cho Ψ₀**, các vòng thêm chạy trên ACT; chạy holdout sớm và niêm phong cho các nhánh không phụ thuộc C; backup hằng ngày (`catalog/`, `releases/`, vault holdout, ledger) sang máy thứ hai.
- Chỉ số chính ở holdout lấy từ cờ thành công của SIMPLE; scorer chỉ dùng cho chỉ số theo bước.
- Thêm trường **"lớp lỗi chung"** (tiếp cận, gắp, mang, đặt, thăng bằng) vào định nghĩa kiểu lỗi để thống kê gộp được giữa task ở L1.
- PRD: cập nhật bảng năng lực theo số story mới; bỏ chữ SQLite còn sót.

## 10. Kinh tế và chỉ số giá trị

- Thêm **chi phí mỗi điểm % tăng thêm** của C so với B và B-fail.
- Chỉ số chính chuyển sang: số demo người để đạt ngưỡng; phút operator mỗi điểm %; sai số dự báo chi phí (ước tính so với thực đo trong ledger); số ngày để policy đạt lại ngưỡng.
- r_debug báo dạng khoảng; thêm bảng độ nhạy theo đơn giá DENSO và **chi phí giờ cell** (robot, người giám sát, thời gian dừng).
- HT báo kèm hai ràng buộc riêng: phút người và GPU-giờ.

## 11. Quyết định ngày 23/10/2026 (sau vòng 1)

Trưởng nhóm quyết trong buổi thảo luận 22–23/10/2026 và duyệt [design 23/10/2026](../superpowers/specs/2026-10-23-data-pipeline-and-failure-eval-design.md). Đây không phải sửa từ phản biện của 05; QA phản biện các quyết định này ở 05 mục 6.7.

| # | Quyết định | Áp vào |
|---|---|---|
| 11.1 | Robot chính là mobile manipulator của DENSO (đế bánh xe, cột nâng, hai tay, gripper hai ngón, camera đỉnh cột), chạy trong Isaac Sim. G1 trong SIMPLE được giữ làm bàn thử cho HS, HT, HD | Spec v10.2 mục 0, 1.1, 2.5; 00 0.3; 01 0.4; 02 0.4 (MT8, Epic 9); 03 0.4 |
| 11.2 | Task đầu tiên của robot DENSO: lấy linh kiện từ khay, đặt vào máy, theo layout trạm làm việc | Design mục 7.1; 02 FR57 |
| 11.3 | Ψ₀ dùng lại checkpoint của tác giả: stage 1 giữ nguyên, stage 2 train lại cho robot DENSO, stage 3 fine-tune theo task. Mỗi stage được đánh giá riêng | Design mục 6; spec mục 2.5, 6.4; 02 FR53–FR55 |
| 11.4 | Dữ liệu teleop và video egocentric lấy từ nhà máy DENSO; xây pipeline xử lý và chuẩn hóa cho ba nguồn, kể cả synthetic | Design mục 4, 5; 02 FR48–FR50 |
| 11.5 | Ưu tiên model trên NVIDIA NIM cho xử lý và sinh dữ liệu. Giữ hai phương án: API hosted và NIM tự host, định tuyến theo mức nhạy cảm của dữ liệu | Design mục 5.4; 02 FR51, FR52, NFR13 |
| 11.6 | Video egocentric giữ hai phương án thu (chỉ RGB, hoặc có tracking tay và đầu) cho tới khi trao đổi với DENSO | Design mục 5.3; 02 FR50 |
| 11.7 | Nếu DENSO gửi thông tin muộn, dùng robot thay thế giống ít nhất 95% theo thước đo đã định nghĩa | Design mục 3.1; spec mục 2.5; 02 FR56 |
| 11.8 | Giữ đủ phạm vi, không cắt trước. Khi vượt thời gian, chuyển phần trễ sang API theo từng phần trước, rồi mới cắt | Design mục 11; spec mục 9, 10; 04 mục 4.9 |
| 11.9 | Chia việc theo bản đồ sở hữu đường dẫn, mỗi story một nhánh, một worktree, một phiên Claude; theo dõi theo nhiệm vụ con | [07](07-team-workflow.md); CLAUDE.md |

Còn mở: 21 mục thông tin từ DENSO (design mục 9); tiêu chí chấp nhận định lượng cho robot DENSO (05 MO7); câu hỏi D1–D5 ở [data-flywheel.md](../references/data-flywheel.md).
