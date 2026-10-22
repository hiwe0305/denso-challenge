# 00 · Phân tích idea: Humanoid Data Flywheel

_Ngày 22/10/2026. Đây là đầu vào chung cho cả "phòng phát triển sản phẩm" (các file 01–05 trong thư mục này). Chi tiết thuật toán và thiết kế PoC nằm ở [spec v10.1](../spec-v10-failure-to-data.md); file này trả lời: sản phẩm là gì, lõi là gì, đã chứng minh gì, và cần gì để mở rộng. Bản 0.2 áp quyết định phản biện vòng 1 ở [06](06-review-round-1-decisions.md); tên giả thuyết theo 06: HS (sim), HT gồm HTa và HTb (nhắm theo lỗi), HD (debug)._

## 1. Sản phẩm trong một câu

**Một nền tảng giúp đội robot biết, sau mỗi lần humanoid làm hỏng một task, nên sửa hệ thống hay bổ sung loại dữ liệu nào, bổ sung bao nhiêu, và lần sửa đó tốn bao nhiêu so với chất lượng nhận được.**

Không phải một model mới, cũng không phải một bộ dữ liệu. Model (Ψ₀), simulator (SIMPLE) và robot (G1) là những thứ được cắm vào nền tảng.

**Định vị:** _Humanoid Data Flywheel là quy trình vận hành có kiểm toán cho vòng lỗi → dữ liệu: loại lỗi hệ thống trước khi tiêu tiền vào dữ liệu, chọn giữa nhiều loại can thiệp theo chi phí thật kể cả chi phí chẩn đoán, và xuất **khuyến nghị thu dữ liệu định lượng** cho DENSO. PoC kiểm lại trên G1 toàn thân với Ψ₀ xem "nhắm lỗi thắng rải đều" có còn đúng khi tính đủ chi phí._

Data Core cộng SOP thu và kiểm dữ liệu là **"DENSO Data Model"** mà tên đề yêu cầu.

## 2. Ai dùng, đau ở đâu

| Người dùng | Việc hằng ngày | Điều đang đau |
|---|---|---|
| Kỹ sư robot learning | Train, đánh giá, sửa policy | Policy hỏng thì đoán nguyên nhân bằng cách xem video và log; thường chọn "thu thêm teleop" vì không có cách nào khác chắc hơn |
| Kỹ sư simulation | Dựng cảnh, sinh dữ liệu sim | Không biết nên sinh dữ liệu ở vùng điều kiện nào; sinh đều thì tốn GPU mà không trúng chỗ yếu |
| Kỹ sư data | Chuẩn hóa, QA, quản lý phiên bản dữ liệu | Dữ liệu từ nhiều nguồn khác nhau về đơn vị, khung tọa độ, thời gian; biến thể bị đếm như demo gốc; lộ dữ liệu test vào train |
| Operator teleop | Điều khiển robot để thu demo | Thu lặp lại những tình huống robot đã làm được; mỗi lượt tốn thời gian reset |
| Chủ công đoạn (task owner) tại nhà máy | Quyết định đưa robot vào dây chuyền | Không có con số rõ: cần bao nhiêu công để robot đạt chuẩn khi đổi linh kiện, khay, ánh sáng |

Đề H1 của BTC hỏi đúng các điểm này: huấn luyện nhanh, chính xác, ít công; quy trình thu dữ liệu chuẩn; so sánh phương pháp; demo kỹ năng.

## 3. Lõi của sản phẩm: vòng flywheel

Vòng lặp, mỗi bước có đầu vào và đầu ra rõ:

| Bước | Làm gì | Đầu ra lưu lại |
|---|---|---|
| 1 · Run | Chạy policy trên một bộ tình huống (điều kiện) đã khai | Trace từng episode |
| 2 · Score | Chấm từng bước của task bằng scorer độc lập | Bước hỏng đầu tiên, kiểu lỗi |
| 3 · Diagnose | Chạy chuỗi phép kiểm: hệ thống → khả thi → khoanh vùng → thị giác → vùng phủ | Evidence card, chẩn đoán |
| 4 · Decide | Chọn can thiệp theo lợi ích kỳ vọng trên chi phí, trong ngân sách; kỹ sư duyệt | Kế hoạch thu dữ liệu |
| 5 · Acquire & QA | Sinh sim, thu correction, tăng cường ảnh; kiểm QA; tạo release mới | Dataset release có lineage |
| 6 · Train | Fine-tune từ checkpoint cha, trộn lại dữ liệu cũ | Policy ứng viên |
| 7 · Gate | Kiểm trên dev (cụm mục tiêu, hồi quy), rồi holdout | Quyết định dùng hay từ chối |
| 8 · Ledger | Ghi chi phí thật mọi bước; cập nhật "tỉ lệ sửa được" của từng loại can thiệp | Sổ chi phí, thống kê can thiệp |

### Vì sao gọi là flywheel

Mỗi vòng để lại tài sản dùng lại được cho vòng sau và cho task sau:

1. **Thư viện tình huống và lỗi:** điều kiện nào đã thử, policy nào hỏng ở đâu.
2. **Thống kê "loại can thiệp nào sửa được loại lỗi nào"** với chi phí thật. Đây là tài sản cần đo ở L1, chưa phải lợi thế đã có: ở L0, Ψ₀ mặc định chỉ chạy 1 vòng C. Tỉ lệ sửa được đo có đối chứng (chạy lại policy cha trên điều kiện mới quanh điểm lỗi); tín hiệu sớm lấy từ thí nghiệm F-ACT, 5–8 vòng rẻ với ACT trên cùng task.
3. **Dữ liệu đã QA, có lineage**, trộn lại được cho task mới.
4. **Scorer và định nghĩa bước** của từng loại task (gắp, đặt, đẩy...).
5. **Sổ chi phí:** biết trước một lần cải thiện tốn bao nhiêu công.

Vòng càng quay, phần đoán càng ít, chi phí mỗi điểm % thành công càng giảm. Đó là lời hứa cần đo được, không phải mặc định.

### Lõi và phần cắm

Để mở rộng được, phải tách rõ:

| Thuộc lõi (không đổi khi đổi model, robot, simulator) | Thuộc phần cắm (adapter, thay được) |
|---|---|
| Mô hình dữ liệu: episode, release, trace, evidence card, ledger | Model và trainer: Ψ₀, ACT, Diffusion Policy... |
| Lineage, chia tập, QA chung | Simulator: SIMPLE (Isaac Sim, MuJoCo), sau này cell thật |
| Scorer từng bước (khung), phân loại lỗi | Robot: G1 trong sim, sau này G1 thật hoặc robot khác |
| Chuỗi phép kiểm chẩn đoán và bảng quyết định | Bộ sinh dữ liệu: motion planning, MimicGen-style, V2D |
| Chọn can thiệp theo ngân sách, thống kê tỉ lệ sửa được | Nguồn teleop: thiết bị VR, bàn điều khiển |
| Sổ chi phí, cổng kiểm, báo cáo | Định nghĩa task cụ thể và vị từ của scorer |

**Ψ₀ + SIMPLE / G1 là recipe đầu tiên cắm vào lõi**, không phải bản thân sản phẩm.

## 4. Đã chứng minh gì, còn là giả định gì

| Hạng mục | Trạng thái |
|---|---|
| Dữ liệu task `G1WholebodyBendPickAndPlaceTeleop-v0` có trên psi-data | Đã kiểm (108 MB) |
| Ψ₀ đạt điểm cao trên SIMPLE khi dùng đủ dữ liệu | Số công bố của tác giả, đội chưa tái tạo |
| Đội fine-tune được Ψ₀ trên phần cứng hiện có | Chưa kiểm; full fine-tune 2,5B tham số cần GPU 80 GB |
| Sim thay được 30% teleop (HS) | Giả thuyết |
| Nhắm theo lỗi tốt hơn bổ sung đều (HTa) | Giả thuyết; kiểm lại (replication) kết quả kiểu Mulligan / DISEIL trên G1 toàn thân, tính đủ chi phí chẩn đoán |
| Chẩn đoán giúp thêm ngoài việc chỉ nhắm theo lỗi (HTb) | Giả thuyết; đo bằng C so với B-fail, chạy trên ACT là chính |
| Giảm 50% giờ debug (HD) | Giả định chiếm phần lớn lợi ích kinh tế; chưa đo; sẽ báo dạng khoảng |
| Rollout motion planning chạy cùng bộ điều khiển với teleop, hoặc ánh xạ được (V3) | Chưa kiểm; teleop chạy decoupled WBC (`g1_sonic`), motion planning chạy AMO; hạn trả lời ngày 5 của Sprint 1 |
| Checkpoint gốc Ψ₀ chưa thấy dữ liệu task chính (Q0) | Chưa kiểm; chọn `pre.*` hoặc `postpre.*`, hỏi PSI Lab ở G0 |
| Lợi ích $168,20 mỗi đợt, 144 đợt/năm | Mô hình ước lượng; số đợt chưa có cơ sở; chỉ số chính chuyển sang giờ người và số ngày |
| Chạy trên robot thật | Ngoài phạm vi 12 tuần |

Không claim thuật toán học máy mới; đóng góp là cách ghép và phép đo. Phần khác biệt còn lại hẹp: kiểm hệ thống trước, chọn giữa nhiều loại can thiệp trên một thước đo chi phí gồm cả chi phí chẩn đoán.

## 5. Điểm yếu cần xử lý (từ rà soát ngày 22/10 và phản biện vòng 1 ở [05](05-review-and-mentor-questions.md))

1. **Lời hứa và thí nghiệm lệch nhau.** Pitch hứa "biết cần bổ sung dữ liệu nào", nhưng PoC cũ chỉ so teleop với teleop + sim. Spec v10 thêm nhánh C để kiểm đúng điều này; nhánh B-fail (nhắm lỗi, không chẩn đoán) tách phần chẩn đoán.
2. **Thuật toán chẩn đoán trước đây chỉ là "kỹ sư phân loại".** Spec v10 đã đặc tả thành 12 bước; cần biến thành phần mềm chạy được.
3. **Kinh tế phụ thuộc giờ debug.** Không giảm được giờ debug thì lỗ $31,80/đợt. Cần đo bằng thí nghiệm HD; r_debug báo dạng khoảng.
4. **Đánh giá dễ chạm trần.** Ψ₀ đạt 10/10 ở nhiều task SIMPLE; phải đo ở mức dữ liệu thấp và trên Level 1–2.
5. **Năng lực đội cần minh chứng.** Hai mảng Simulation và Data trên trang đội vẫn "chờ bổ sung minh chứng".
6. **Bộ điều khiển (V3).** Teleop của task chính chạy decoupled WBC, motion planning chạy AMO. Nếu không ánh xạ được, nhánh B không có dữ liệu sinh hợp lệ. Hạn trả lời ngày 5 của Sprint 1; tuyến thay thế T1–T4 ở [06 mục 1](06-review-round-1-decisions.md).
7. **Nguồn gốc checkpoint (Q0).** Nếu checkpoint gốc Ψ₀ đã train trên dữ liệu SIMPLE hoặc sonic của task chính, đường cong E1 và mọi nhánh mất nghĩa. Chốt checkpoint có nguồn gốc rõ ở G0.
8. **Thống kê.** Khoảng tin cậy cũ bỏ phương sai giữa seed; với 3 seed, HT có thể chỉ phát hiện được chênh lệch cỡ 7–14 điểm %. Chuyển sang bootstrap phân cấp và power analysis ở G2; nếu hiệu ứng nhỏ nhất phát hiện được trên 10 điểm %, thêm seed hoặc hạ HT thành kết quả mô tả.

## 6. Các trục mở rộng

| Mức | Phạm vi | Lõi cần thêm gì |
|---|---|---|
| L0 · PoC (12 tuần) | 1 task, 1 robot, sim | Mô hình dữ liệu, scorer, chẩn đoán, ledger chạy được cho 1 recipe |
| L1 · Nhiều task | 3–5 task cùng robot, sim | Thư viện scorer theo loại task; thống kê can thiệp dùng chung giữa task |
| L2 · Robot thật | 1 cell thật | Adapter robot thật, an toàn, teleop thật, real2sim cho tình huống lỗi |
| L3 · Nhiều robot | Nhiều embodiment | Chuẩn hóa schema state/action theo embodiment; adapter model đa robot |
| L4 · Nhiều nhà máy | Nhiều đội dùng chung | Phân quyền, nhiều người dùng, lưu trữ tập trung, báo cáo theo đơn vị |

Thiết kế lõi trong 12 tuần chỉ cần chạy ở L0, nhưng **mô hình dữ liệu và giao diện adapter phải đúng cho L1–L3** để không phải viết lại.

## 7. Đội và nguồn lực

| Mảng | Thành viên | Kỹ năng đã nêu trong pitch |
|---|---|---|
| Robot Learning (trưởng nhóm, đầu mối với DENSO) | Dương Đình Hiếu | Lightweight VLA (FOCA trên SmolVLA), RL humanoid (PPO H1 / MuJoCo) |
| Robotics / Simulation | Trần Ngọc Hưng, Trần Trịnh Hoàng Châu | Môi trường MuJoCo, Isaac Sim |
| Data / Platform | Nguyễn Thăng Long, Dương Tiến Thông | Phân tích, xử lý, chuẩn hóa dataset |

- Mentor: có, có thể hỏi ý kiến và nhờ phản biện (chuyên môn cụ thể chưa ghi nhận).
- GPU sẵn có: RTX 3060 12 GB, RTX 5090 32 GB. Fine-tune Ψ₀ toàn phần có thể cần thuê A100 80 GB.
- Thời gian: 12 tuần theo đề BTC. Robot thật phụ thuộc BTC.

## 8. Câu hỏi mở

1. DENSO có xác nhận một công đoạn cụ thể và người phụ trách (task owner) không?
2. Mentor có chuyên môn gì: robot learning, simulation, hệ thống dữ liệu, vận hành nhà máy?
3. Có thiết bị teleop cho SIMPLE không (VR hay bàn điều khiển)?
4. Gói psi-data của task chính có bao nhiêu demo teleop đạt QA?
5. Ngân sách GPU thuê ngoài tối đa cho 12 tuần là bao nhiêu?

## 9. Change log

| Ngày | Phiên bản | Nội dung | Người sửa |
|---|---|---|---|
| 22/10/2026 | 0.1 | Bản đầu | Trưởng nhóm |
| 22/10/2026 | 0.2 | Toàn file: đổi tên giả thuyết H1, H2, H3 thành HS, HT (HTa, HTb), HD; giữ mã đề "H1" và "PPO H1" | Analyst theo 06 |
| 22/10/2026 | 0.2 | Mục 1: thêm câu định vị của 06 mục 6; gọi Data Core cộng SOP là "DENSO Data Model" | Analyst theo 06 |
| 22/10/2026 | 0.2 | Mục 3: bỏ câu "Đây là thứ đối thủ không có sẵn"; tỉ lệ sửa được là tài sản cần đo ở L1, có đối chứng policy cha và thí nghiệm F-ACT (06 mục 3) | Analyst theo 06 |
| 22/10/2026 | 0.2 | Mục 4: HT là kiểm lại kiểu Mulligan / DISEIL, tách HTa và HTb, bỏ "điểm khác biệt chính"; thêm dòng V3 và Q0; thêm câu không claim thuật toán mới | Analyst theo 06 |
| 22/10/2026 | 0.2 | Mục 5: thêm điểm yếu V3, nguồn gốc checkpoint, thống kê; nhắc nhánh B-fail và r_debug dạng khoảng | Analyst theo 06 |
