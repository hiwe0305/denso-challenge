# Spec v10.1: thuật toán Failure → Data và PoC đối chứng

_Trạng thái: đặc tả đề xuất, chưa thực nghiệm. Ngày 22/10/2026. Phiên bản v10.1: đã áp dụng [quyết định phản biện vòng 1](product/06-review-round-1-decisions.md), xem mục 14. Áp dụng cho recipe Ψ₀ + SIMPLE / G1 của [Pitch v10](../deliverables/DENSO-ilovephysicalintelligence-1.pptx). Tài liệu này là đặc tả canonical cho thuật toán flywheel và thiết kế đánh giá. Hồ sơ của recipe cũ FluxVLA / GR00T N1.5 / GR1 (docs 01–14, idea v3) nằm trong tag git `archive/v3`; các quy tắc dữ liệu cần dùng đã được đưa vào mục 4. Thuật ngữ được định nghĩa ở mục 12._

## 0. Đọc nhanh

**Một câu (định vị):** _Humanoid Data Flywheel là quy trình vận hành có kiểm toán cho vòng lỗi → dữ liệu: loại lỗi hệ thống trước khi tiêu tiền vào dữ liệu, chọn giữa nhiều loại can thiệp theo chi phí thật kể cả chi phí chẩn đoán, và xuất **khuyến nghị thu dữ liệu định lượng** cho DENSO. PoC kiểm lại trên G1 toàn thân với Ψ₀ xem "nhắm lỗi thắng rải đều" có còn đúng khi tính đủ chi phí._

**Cách làm:** khi policy humanoid thất bại trong mô phỏng, hệ thống chạy một chuỗi phép kiểm tự động để xác định lỗi do hệ thống hay do dữ liệu, nếu do dữ liệu thì thiếu loại nào, rồi đề xuất cách bổ sung có lợi ích kỳ vọng cao nhất trên mỗi đô-la. Kỹ sư duyệt đề xuất; mọi bước được ghi vào sổ chi phí.

**Ba giả thuyết cần kiểm** (tên HS, HT, HD để không trùng mã đề "H1"/"H2" của BTC):

- **HS · Sim thay được teleop:** 0,7D\* demo teleop cộng dữ liệu sim đạt chất lượng không kém D\* demo teleop và đạt ≥ 75% (Cấp 2 của BTC).
- **HT · Nhắm theo lỗi tốt hơn bổ sung đều:** cùng ngân sách thu dữ liệu, dữ liệu do Failure → Data chọn cho kết quả tốt hơn dữ liệu sim rải đều. Đây là **kiểm lại** kết quả kiểu Mulligan / DISEIL, không phải điểm mới. Tách hai phần: **HTa** nhắm theo lỗi có tốt hơn bổ sung đều không (B-fail so với B); **HTb** chẩn đoán có giúp thêm ngoài việc chỉ nhắm theo lỗi không (C so với B-fail).
- **HD · Giảm giờ chẩn đoán:** evidence card giúp kỹ sư chẩn đoán lỗi nhanh hơn công cụ chuẩn mà không sai nhiều hơn.

**Các nhánh chính:** A (D\* teleop), B (0,7D\* teleop + sim rải đều), C (0,7D\* teleop + dữ liệu chọn bởi Failure → Data). Nhánh đối chứng A₀.₇ (chỉ 0,7D\* teleop) cho biết khoảng cách mà B và C cần lấp. Nhánh B-fail (sinh sim quanh mọi lỗi dev, không chẩn đoán) tách tác dụng của chẩn đoán khỏi tác dụng của việc nhắm theo lỗi.

**Đầu ra 12 tuần, khớp đề H1 của BTC** (mã đề giữ "H1" cho tới khi BTC xác nhận; ảnh đề ghi "H2"):

1. SOP thu và kiểm dữ liệu: mục 4 và mục 6 viết thành checklist. Data Core cộng SOP là **DENSO Data Model** theo tên đề.
2. Báo cáo so sánh phương pháp huấn luyện: ACT, Diffusion Policy và Ψ₀, kèm kết quả HS, HT, HD.
3. Demo kỹ năng đã học: video rollout trong SIMPLE trên tập holdout.
4. Khuyến nghị thu dữ liệu định lượng (Cấp 3 của BTC): đầu ra của bước 10–11 (mục 6.1) cộng sổ chi phí (mục 8).

## 1. Phạm vi và ranh giới claim

### 1.1 Kế thừa, đội làm, sau PoC

| Lớp | Nội dung | Ghi chú khi trình bày |
|---|---|---|
| Kế thừa | Checkpoint Ψ₀ đã pretrain trên video người (EgoDex) và dữ liệu humanoid; simulator SIMPLE; dữ liệu psi-data; stack decoupled WBC của SIMPLE (task chính) và bộ điều khiển AMO (pipeline MP) | Viết "kế thừa prior video người từ Ψ₀", không viết "platform kết hợp video người" như đóng góp của đội |
| Đội làm trong PoC | Data Core (QA, lineage, chia tập), scorer từng bước, thuật toán Failure → Data, evidence card, sổ chi phí, thiết kế và chạy PoC với các nhánh đối chứng, so sánh phương pháp. Data Core cộng SOP gọi là **DENSO Data Model** | Đây là phần được chấm là đóng góp |
| Sau PoC | Video công nhân DENSO qua V2D, world model DreamDojo, task DENSO thật, robot thật | Mỗi hướng cần cổng nghiệm thu riêng |

### 1.2 Không claim

- Không claim thuật toán học máy mới. Các thành phần đều có tiền lệ: DAgger / HG-DAgger cho correction, IntervenGen (2024) cho sinh correction hàng loạt từ ít can thiệp của người, MimicGen cho sinh biến thể, DataMIL và CUPID (2025, chọn demo bằng influence function) cho chọn dữ liệu. Ý "thu dữ liệu bắt đầu từ chỗ policy thất bại" cũng đã có: Mulligan (2026) chọn trạng thái đầu của mỗi vòng thu dữ liệu tại các lỗi đã thấy và trạng thái chưa thử, và dùng cả dữ liệu lỗi để học value function; DISEIL (2026) tìm điểm policy bắt đầu không tin cậy, gom lỗi thành nhóm, chọn lỗi nào cần expert làm mẫu và kiểm khả thi trước khi tốn công expert.
- Vì vậy HT là **kiểm lại (replication)** kết quả kiểu Mulligan / DISEIL trên G1 toàn thân với Ψ₀, có tính đủ chi phí chẩn đoán; HT không phải điểm khác biệt chính.
- **Định vị:** _Humanoid Data Flywheel là quy trình vận hành có kiểm toán cho vòng lỗi → dữ liệu: loại lỗi hệ thống trước khi tiêu tiền vào dữ liệu, chọn giữa nhiều loại can thiệp theo chi phí thật kể cả chi phí chẩn đoán, và xuất **khuyến nghị thu dữ liệu định lượng** cho DENSO. PoC kiểm lại trên G1 toàn thân với Ψ₀ xem "nhắm lỗi thắng rải đều" có còn đúng khi tính đủ chi phí._
- Trong phạm vi đã tra ngày 22/10/2026, chưa thấy quy trình kiểm hệ thống trước rồi chọn giữa nhiều loại can thiệp (sinh sim, correction, dữ liệu phục hồi) bằng một thước đo tiền và giờ công gồm cả chi phí chẩn đoán. Đóng góp là **cách ghép các phép kiểm thành quy trình ra quyết định có ghi chi phí**, và **phép đo** xem quy trình đó có đáng tiền không.
- Không dùng dữ liệu lỗi làm tín hiệu train trong PoC (mục 4.4). Dùng dữ liệu lỗi để train, như Mulligan, là hướng L1.
- Không claim kết quả trên robot thật. Mọi số liệu PoC là trong mô phỏng; dữ liệu sim cùng phân phối với môi trường test nên lợi ích của sim có thể bị phóng đại so với robot thật.
- Không claim tiết kiệm tiền mặt. Sổ chi phí đo giá trị nguồn lực theo đơn giá giả định.

## 2. Nền tảng kỹ thuật

### 2.1 Ψ₀

Theo [trang Ψ₀](https://psi-lab.ai/Psi0/), kiểm ngày 22/10/2026:

| Thành phần | Mô tả | Vai trò trong PoC |
|---|---|---|
| System-2 | VLM Qwen3-VL-2B-Instruct, pretrain trên khoảng 829 giờ video EgoDex cùng Humanoid Everyday | Kế thừa |
| System-1 | Action expert dạng flow matching (MM-DiT), khoảng 500M tham số, dự đoán action chunk toàn thân | Fine-tune |
| System-0 | Bộ điều khiển tầng thấp. Trang Ψ₀ mô tả System-0 là bộ điều khiển thân dưới AMO học bằng RL. Trong SIMPLE, task chính chạy **decoupled WBC**: robot `g1_sonic`, env `SonicLocoManipEnv`, agent `psi0_decoupled_wbc`. AMO (`g1_wholebody`) là bộ điều khiển của pipeline MP (`*MP-v0`) | Kế thừa; stack WBC của task chính là đối tượng của kiểm tra hệ thống (mục 6.4) |
| Tổng | Hơn 2,5B tham số, khoảng 160 ms mỗi lần chạy, dùng real-time chunking | Cần đo VRAM và thời gian ở G0 |

Theo công bố, bước thích nghi với task mới là fine-tune toàn bộ model trên một lượng nhỏ dữ liệu teleop trong miền. Bộ điều khiển của từng loại task theo [tài liệu G1 Decoupled](https://psi-lab.ai/SIMPLE/docs/tasks/g1_decoupled.html) và [G1 MP (AMO)](https://psi-lab.ai/SIMPLE/docs/tasks/g1_mp_amo.html) của SIMPLE. Vì teleop và MP khác bộ điều khiển, rollout MP chưa chắc dùng được cho task chính (câu V3, mục 2.4).

### 2.2 SIMPLE

Theo [repo SIMPLE](https://github.com/physical-superintelligence-lab/SIMPLE): chạy trên Isaac Sim 4.5 và MuJoCo 3.3, có robot Unitree G1, hơn 50 cảnh, hỗ trợ thu dữ liệu bằng teleop và bằng motion planning. Bộ đánh giá có ba mức:

| Mức | Thay đổi so với môi trường train | Vai trò trong spec |
|---|---|---|
| Level 0 | Vật liệu bàn, loại và vị trí vật gây nhiễu | Trong miền |
| Level 1 | Level 0 cộng thay đổi ánh sáng mạnh | Ngoài miền về hình ảnh |
| Level 2 | Level 1 cộng thay đổi vị trí ban đầu của vật cần gắp | Ngoài miền về hình ảnh và vị trí |

Repo SIMPLE có sẵn baseline ACT, Diffusion Policy, π0.5, GR00T N1.6 và một số model khác, nên phần so sánh phương pháp dùng lại được hạ tầng đánh giá.

### 2.3 Task và dữ liệu

- **Task chính:** `G1WholebodyBendPickAndPlaceTeleop-v0` (humanoid cúi xuống gắp vật rồi đặt). Gói dữ liệu có trong [psi-data/simple](https://huggingface.co/datasets/USC-PSI-Lab/psi-data/tree/main/simple), 108 MB.
- Thư mục này có 18 gói gồm hai kiểu: `*Teleop-v0` (thu bằng điều khiển từ xa) và `*MP-v0` (sinh bằng motion planning). Không có gói MP trùng đúng task chính; các gói gần nhất là `G1WholebodyPickAndBendPlaceMP-v0` và `G1WholebodyBendPickAndPlaceOnSofaMP-v0`.
- **Task F1:** cặp `G1WholebodyBendPickTeleop-v0` và `G1WholebodyBendPickMP-v0` (chỉ gắp, không đặt), có sẵn cả hai kiểu dữ liệu. F1 giữ vai trò kiểm khả năng tổng quát của lõi trên task thứ hai. F1 **không còn là dự phòng cho Q2** cho tới khi V3 xác nhận cặp Teleop và MP của F1 cùng bộ điều khiển: mọi `*Teleop-v0` dùng `g1_sonic`, mọi `*MP-v0` dùng AMO, nên F1 nhiều khả năng gặp đúng vấn đề của task chính.
- Ψ₀ công bố 10/10 ở cả ba mức cho `BendPickMP` và 10/9/9 cho `XMoveBendPickTeleop` (10 lượt mỗi mức). Nhiều task đã gần trần 100% khi dùng đủ dữ liệu, nên PoC phải đo ở mức dữ liệu thấp hơn (mục 7.1).

### 2.4 Câu hỏi phải trả lời ở cổng G0

V3 có hạn riêng là **ngày 5 của Sprint 1**; các câu khác hạn cuối G0.

| Mã | Câu hỏi | Nếu câu trả lời là "không" |
|---|---|---|
| Q0 | Checkpoint `pre.*` hoặc `postpre.*` nào đã xác nhận không train trên dữ liệu SIMPLE hoặc sonic của task chính? Hỏi PSI Lab; ghi nguồn gốc vào thực thể Source | Không dùng checkpoint chưa xác nhận cho E1 và các nhánh. Chọn checkpoint ít post-train nhất (`pre.*`) và ghi giới hạn vào báo cáo; nếu Ψ₀ ở mức 10% dữ liệu cao bất thường, cân nhắc đổi task chính |
| Q1 | Gói task chính chứa bao nhiêu demo teleop đạt QA (gọi là N_teleop)? | Nếu N_teleop < 50, đường cong ở mục 7.1 quá thô: chuyển sang task dự phòng hoặc gộp task |
| Q2 | Pipeline motion planning của SIMPLE cấu hình được cho task chính không? | Sinh biến thể kiểu MimicGen / IntervenGen từ đoạn teleop (tuyến T2, mục 10). Chỉ dùng F1 khi V3 xác nhận cặp của F1 cùng bộ điều khiển |
| V3 | Rollout MP có cùng bộ điều khiển với teleop không (decoupled WBC `g1_sonic` so với AMO `g1_wholebody`)? Nếu không, ánh xạ được sang giao diện lệnh của WBC không? Hạn ngày 5 của Sprint 1 | Chọn tuyến T1–T4 (mục 10): thử T1 và T2 song song tuần 1–2, chốt cuối tuần 2. Nhánh B, kiểm khả thi (mục 6.5), trạng thái chuẩn (mục 6.6) và sinh sim (mục 6.10) chờ tuyến được chọn |
| Q3 | Có đặt được simulator vào một trạng thái đã lưu (vị trí robot, vật, khớp) rồi chạy tiếp không? | Bỏ phép kiểm khoanh vùng (mục 6.6); chẩn đoán đánh dấu "chưa khoanh vùng" |
| Q4 | Có tách được ngẫu nhiên hóa hình ảnh khỏi ngẫu nhiên hóa vật lý không? | Bỏ phép kiểm thị giác (mục 6.7) |
| Q5 | Fine-tune Ψ₀ cần bao nhiêu VRAM và GPU-giờ; mỗi episode đánh giá mất bao lâu? | Dùng LoRA hoặc đóng băng VLM; thuê A100 80 GB; giảm số seed |
| Q6 | Đội có thiết bị teleop cho SIMPLE không? | Correction do planner sinh từ trạng thái lỗi thay cho người điều khiển |

## 3. Giả thuyết và tiêu chí chấp nhận

Tên giả thuyết: HS (sim), HT (nhắm theo lỗi, tách HTa và HTb), HD (debug). Các tên này thay H1, H2, H3 của bản trước để không trùng mã đề của BTC.

| Mã | Giả thuyết | So sánh | Tiêu chí chấp nhận (chốt trước khi chạy holdout) |
|---|---|---|---|
| HS | Sim thay được 30% demo teleop | B so với A và A₀.₇ (Ψ₀) | B đạt ≥ 75% trên holdout gộp ba mức; cận dưới CI 95% của (B − A) > −10 điểm %; cận dưới CI 95% của (B − A₀.₇) > 0 |
| HT | Nhắm theo lỗi tốt hơn bổ sung đều; kiểm lại kết quả kiểu Mulligan / DISEIL | C so với B trên Ψ₀, cùng ngân sách thu dữ liệu | Cận dưới CI 95% của (C − B) > 0, CI theo bootstrap phân cấp (mục 7.5). Báo kèm tổng chi phí của C gồm chi phí chẩn đoán, và hai ràng buộc riêng: phút người, GPU-giờ (mục 8.3). Nếu MDE ở G2 > 10 điểm % và không tăng được seed, HT là kết quả mô tả |
| HTa | Nhắm theo lỗi, không chẩn đoán, tốt hơn bổ sung đều | B-fail so với B, cùng ngân sách; ACT là chính, Ψ₀ nếu còn ngân sách sau G4 | Cận dưới CI 95% của (B-fail − B) > 0 |
| HTb | Chẩn đoán giúp thêm ngoài việc chỉ nhắm theo lỗi | C so với B-fail, cùng ngân sách, cùng phương pháp | Cận dưới CI 95% của (C − B-fail) > 0; báo kèm chi phí chẩn đoán của C |
| HD | Evidence card giảm thời gian chẩn đoán | Có card so với công cụ chuẩn (Rerun cộng đồ thị mặc định) | Thời gian giảm và tỉ lệ chẩn đoán đúng không thấp hơn; r_debug báo dạng khoảng. Đây là pilot, không phải kiểm định thống kê |
| M | So sánh phương pháp huấn luyện | ACT, Diffusion Policy, Ψ₀ trên nhánh A và B | Báo cáo mô tả: tỉ lệ thành công theo mức, số demo để đạt 75% (kèm 80% để đối chiếu Pitch v10), chi phí train |

Ghi chú cho HS: nếu A₀.₇ đã không kém A thì HS đúng nhưng không nhờ sim; khi đó dữ liệu teleop chưa phải nút thắt ở mức D\*. Vì vậy điều kiện (B − A₀.₇) > 0 là bắt buộc.

**Map tiêu chí 3 cấp của BTC** ([đề bài](challenge/README.md)):

| Cấp BTC | Tiêu chí | Chỉ tiêu trong PoC |
|---|---|---|
| 1 · Basic | ≥ 50% với lượng demo nhỏ | Báo tỉ lệ thành công ở các mức 10% và 25% của đường cong E1 (mục 7.1) |
| 2 · Efficient | Giảm ≥ 30% demo cùng hiệu năng; ≥ 75% | HS: B ở 0,7D\* không kém A và đạt ≥ 75% |
| 3 · Advanced | ≥ 70% trên biến thể chưa train; khuyến nghị thu dữ liệu định lượng | Báo riêng Level 1 và Level 2 của holdout so với 70%, không gộp với Level 0; đầu ra của bước 10–11 (mục 6.1) cộng sổ chi phí là khuyến nghị định lượng |

- **D\*** là mức demo nhỏ nhất để Ψ₀ đạt **≥ 75%** trên dev gộp ba mức (theo Cấp 2), thay cho 80% của bản trước (mục 7.1).
- Pitch v10 vẫn ghi "≥ 80% / 50 lượt"; cần cập nhật pitch sau, ngoài phạm vi bản sửa này.

## 4. Dữ liệu và hợp đồng

### 4.1 Đơn vị đếm

| Đơn vị | Định nghĩa | Có tính là demo gốc? |
|---|---|---|
| Demo teleop | Một episode người điều khiển, đạt QA và scorer | Có |
| Teleop correction | Đoạn người điều khiển bắt đầu từ một trạng thái lỗi của policy | Có, đếm riêng và cộng vào tổng giờ operator |
| Rollout sim | Episode do planner sinh rồi thực thi trong simulator, đạt scorer | Không. Ghi demo gốc hoặc điều kiện gốc mà nó dựa vào |
| Biến thể | Bản sửa từ một episode khác (đổi vị trí, đổi hình ảnh) | Không. Luôn trỏ về episode cha |
| Rollout đánh giá | Episode chạy policy để chấm | Không bao giờ vào dữ liệu train |

Số "giảm X% demo" chỉ dùng demo teleop và teleop correction: r_demo = 1 − (số demo teleop + correction mà nhánh dùng) / D\*.

### 4.2 Vector điều kiện

Mỗi episode có vector điều kiện c, lấy từ tham số ngẫu nhiên hóa của SIMPLE (cần xác nhận ở Q4):

- Vị trí và góc xoay của vật cần gắp (x, y, yaw).
- Vị trí đích hoặc khay (x, y).
- Độ lệch vị trí xuất phát của robot (x, y, yaw).
- Cường độ và màu ánh sáng.
- Mã vật liệu bàn (one-hot).
- Số vật gây nhiễu.

Thành phần liên tục được chuẩn hóa theo khoảng giá trị của tập train; thành phần phân loại dùng khoảng cách Hamming với trọng số 1. Khoảng cách giữa hai điều kiện là Euclid có trọng số, trọng số mặc định bằng 1.

### 4.3 Chia tập

Chia theo **hạt giống điều kiện** (condition seed) của bộ sinh môi trường, trước khi sinh bất kỳ biến thể nào:

| Tập | Nội dung | Ai được dùng |
|---|---|---|
| Train | Điều kiện của demo teleop và vùng được phép sinh sim | Mọi nhánh |
| Dev | Tập tìm lỗi cố định: 30 điều kiện mỗi mức × 3 mức = 90 điều kiện. Thêm tập cổng mới cho mỗi vòng và điều kiện đo tỉ lệ sửa được, lấy từ phần chưa dùng của dải hạt giống dev (mục 6.12, 6.13) | E1 để chọn D\*; nhánh C và B-fail để tìm lỗi; nhánh B để chọn tỉ lệ trộn ρ |
| Holdout | 50 điều kiện mỗi mức × 3 mức = 150 điều kiện | Chạy đúng một lần cho mỗi cặp nhánh và seed, sau khi nhánh đó đóng băng (mục 7.3) |

Dải hạt giống của ba tập rời nhau và được ghi vào RunPlan trước khi train. Dải dev và holdout còn phải rời với dải hạt giống tác giả đã dùng cho psi-data và `simple-eval`; nếu không biết dải của tác giả thì chọn dải lệch xa và dựa vào guard gần trùng bên dưới. Bộ sinh sim chỉ lấy điều kiện trong miền train, không dùng tham số Level 1 hoặc Level 2. Một episode holdout bị lộ vào train thì vô hiệu hóa run đó.

**Guard gần trùng:** điều kiện dev hoặc holdout có khoảng cách (mục 4.2) tới điều kiện train gần nhất nhỏ hơn phân vị 1 của khoảng cách láng giềng gần nhất trong train thì bị cách ly, không dùng để tìm lỗi hay kết luận. Guard này bắt cả trường hợp demo teleop chỉ có vector điều kiện suy ra, không có hạt giống.

### 4.4 QA bắt buộc

Ngưỡng hiệu chỉnh từ phân phối của demo teleop thành công ở G1, không đoán trước:

| Phép kiểm | Ngưỡng | Hành động khi trượt |
|---|---|---|
| Timestamp tăng đơn điệu, bước đều | Lệch tối đa 1 chu kỳ điều khiển | Loại |
| Đồng bộ ảnh và state | Lệch ≤ 1 khung hình | Sửa đồng bộ, không được thì loại |
| Giới hạn khớp và giá trị hữu hạn | Theo URDF của G1; không NaN hoặc Inf | Loại |
| Bước nhảy action | ≤ phân vị 99,9 của demo teleop | Đánh dấu, kỹ sư xem |
| Kết quả task | Scorer từng bước (mục 5) báo thành công toàn task | Không được làm mẫu dương; giữ làm bằng chứng lỗi |
| Lineage | Có nguồn, giấy phép, cha (nếu là biến thể), hạt giống điều kiện, phiên bản bộ sinh | Cách ly cho đến khi đủ |
| Chia tập | Hạt giống điều kiện thuộc dải train | Vô hiệu hóa release |

Mẫu bị loại vẫn được giữ cùng lý do loại và chi phí đã bỏ ra; không xóa âm thầm để làm đẹp tỉ lệ sinh đạt.

### 4.5 Bản ghi

**Trace** (một bản cho mỗi episode): phiên bản policy, phiên bản release, vector điều kiện, mức, hạt giống điều kiện, chuỗi ảnh kèm timestamp từng khung, hash tham số camera, action chunk dự đoán, lệnh gửi tới WBC (lệnh thân trên, lệnh thân dưới), trạng thái đo được kèm timestamp, độ trễ mỗi chu kỳ, trạng thái từng bước của scorer, cờ thành công của SIMPLE, kết quả cuối.

**Evidence card** (một thẻ cho mỗi cụm lỗi):

- Định danh cụm, danh sách episode, các đại diện đã kiểm.
- Bước hỏng đầu tiên k và kiểu lỗi.
- Kết quả từng phép kiểm: sai số bám lệnh, độ trễ, lệch đồng bộ, camera chuẩn, planner khả thi, s_k (kèm số lượt), kiểm thị giác, trong miền train hay không, khoảng cách vùng phủ. Mỗi giá trị đi kèm ngưỡng tương ứng.
- Chẩn đoán, can thiệp đề xuất, lợi ích kỳ vọng, chi phí ước tính.
- Quyết định của kỹ sư (đồng ý hoặc ghi đè, kèm lý do).
- Kết quả sau khi train lại.

**Mục sổ chi phí:** hoạt động, loại nguồn lực (operator, kỹ sư, A100, RTX 4090, lưu trữ), số lượng, đơn giá, nhánh, vòng, cụm liên quan, cờ "ước tính" hoặc "thực đo" (để tính sai số dự báo chi phí, mục 8.3).

## 5. Scorer từng bước và phân loại lỗi

### 5.1 Các bước của task

Vị từ dưới đây là đề xuất; cần đối chiếu với định nghĩa thành công của SIMPLE cho task chính ở G1.

| Bước | Tên | Vị từ đạt (tham số hiệu chỉnh ở G1) |
|---|---|---|
| 1 | Tiếp cận | Bàn tay trong bán kính r_reach quanh vật |
| 2 | Gắp | Có tiếp xúc tay–vật và vật rời mặt bàn quá h_grasp |
| 3 | Nâng và đứng lên | Vật cao hơn mặt bàn quá h_lift, thân robot trong giới hạn thăng bằng |
| 4 | Di chuyển | Vật nằm trong vùng phía trên đích |
| 5 | Đặt | Vật trong vùng đích, độ cao dưới h_place |
| 6 | Nhả và ổn định | Không còn tiếp xúc tay–vật; vật đứng yên trong vùng đích T_stable giây |

Điều kiện chạy suốt episode: chiều cao và độ nghiêng thân trong giới hạn thăng bằng. Quy ước trạng thái giữ như hồ sơ cũ: bước chưa tới là "chưa thử", không phải "trượt"; thiếu tín hiệu là "chưa rõ", không phải "đạt".

### 5.2 Kiểu lỗi

| Mã | Kiểu lỗi | Lớp lỗi chung | Dấu hiệu |
|---|---|---|---|
| L-REACH | Không tới được vật | Tiếp cận | Hết giờ ở bước 1 |
| L-GRASP | Gắp trượt | Gắp | Đóng tay nhưng không giữ được vật ở bước 2 |
| L-SLIP | Rơi khi mang | Mang | Mất tiếp xúc ở bước 3 hoặc 4 |
| L-COLLIDE | Va chạm | Theo bước hỏng k | Tiếp xúc ngoài ý muốn với bàn, khay hoặc vật gây nhiễu |
| L-PLACE | Đặt lệch | Đặt | Vật ngoài vùng đích ở bước 5 hoặc 6 |
| L-RELEASE | Nhả sai lúc | Đặt | Nhả quá sớm hoặc không nhả |
| L-BALANCE | Mất thăng bằng | Thăng bằng | Vi phạm giới hạn thân ở bất kỳ bước nào |
| L-TIMEOUT | Đứng yên, không tiến triển | Theo bước hỏng k | Hết giờ mà không chuyển bước, không thuộc các kiểu trên |
| L-UNKNOWN | Thiếu tín hiệu | Không gán | Không đủ dữ liệu để gán kiểu |

**Lớp lỗi chung** (tiếp cận, gắp, mang, đặt, thăng bằng) là trường dùng chung giữa các task, để L1 gộp được thống kê lỗi và tỉ lệ sửa được giữa task. "Theo bước hỏng k": bước 1 là tiếp cận, bước 2 là gắp, bước 3–4 là mang, bước 5–6 là đặt. Ở L0 trường này chỉ được ghi, chưa dùng để chọn can thiệp.

### 5.3 Hiệu chỉnh scorer

Cổng G1 đạt khi kết luận toàn task của scorer trùng với cờ thành công của SIMPLE trên ít nhất 95% của 100 episode (gồm cả thành công và thất bại), và kỹ sư xem 20 episode thất bại thấy bước hỏng được gán đúng.

Scorer chỉ dùng cho chỉ số theo bước và gán nhãn lỗi. Chỉ số chính ở holdout lấy từ cờ thành công của SIMPLE (mục 7.5).

## 6. Thuật toán Failure → Data

### 6.1 Tổng quan

Mỗi vòng gồm 12 bước:

| Bước | Tên | Đầu vào | Đầu ra |
|---|---|---|---|
| 1 | Chạy | Policy, 90 điều kiện dev | Trace |
| 2 | Gán nhãn | Trace | Bước hỏng đầu tiên k, kiểu lỗi |
| 3 | Gom cụm sơ bộ | Các lỗi | Cụm theo (k, kiểu lỗi, mức); tối đa R đại diện mỗi cụm |
| 4 | Kiểm hệ thống | Trace của đại diện | Lỗi controller, runtime, đồng bộ, calibration hoặc thiếu tín hiệu |
| 5 | Kiểm khả thi | Điều kiện đầu | Planner chuẩn có làm được không |
| 6 | Khoanh vùng | Trạng thái chuẩn ở đầu bước k | s_k |
| 7 | Kiểm thị giác | Cùng trạng thái vật lý, hình ảnh chuẩn | Lỗi nhận thức hay không |
| 8 | Kiểm vùng phủ | Vector điều kiện | Trong miền train hay không; khoảng cách tới tập train |
| 9 | Chẩn đoán cụm | Kết quả 4–8 của các đại diện | Chẩn đoán theo đa số |
| 10 | Đề xuất và định lượng | Chẩn đoán | Can thiệp, số lượng, chi phí ước tính |
| 11 | Chọn theo ngân sách | Đề xuất, tỉ lệ sửa được | Danh sách can thiệp được chọn |
| 12 | Thu, QA, train, cổng kiểm | Can thiệp được chọn | Release mới, policy ứng viên, tỉ lệ sửa được đo có đối chứng |

Mã giả một vòng:

```python
def failure_to_data_round(policy, release, dev, budget, fix_rate, P):
    # 1–2. Chạy và gán nhãn
    traces = [run(policy, c) for c in dev]
    failures = [label(t) for t in traces if not t.success]   # bước hỏng đầu tiên k, kiểu lỗi

    # 3. Gom cụm sơ bộ, chọn tối đa P.R đại diện mỗi cụm
    clusters = group(failures, key=lambda f: (f.stage, f.kind, f.level))

    for cl in clusters:
        for f in cl.representatives(P.R):
            # 4. Kiểm hệ thống trên stack WBC, chỉ cần log
            if f.missing_signals:                f.diag = "CHUA_RO";             continue
            if f.tracking_error > P.tau_track:   f.diag = "HE_THONG_CONTROLLER"; continue  # thân trên hoặc thân dưới
            if f.latency_p99 > P.tau_lat:        f.diag = "HE_THONG_RUNTIME";    continue
            if f.sync_offset_max > P.tau_sync:   f.diag = "HE_THONG_DONG_BO";    continue  # lệch ảnh và state
            if f.camera_hash != P.camera_ref:    f.diag = "HE_THONG_CALIBRATION"; continue  # khác camera tham chiếu
            # 5. Planner chuẩn từ cùng điều kiện đầu
            if not planner_succeeds(f.condition):
                f.diag = "KHONG_KHA_THI"; continue
            # 6. Khoanh vùng: đặt sim vào trạng thái chuẩn ở đầu bước k
            s_k = success_rate(policy, start=expert_state(f.condition, f.stage), n=P.M)
            if s_k >= P.tau_k:
                f.diag = "TRANG_THAI_DAU_XAU"; continue
            # 7. Kiểm thị giác: giữ trạng thái vật lý, đổi hình ảnh về mức chuẩn
            if f.level > 0 and succeeds(policy, f.condition.with_nominal_visuals()):
                f.diag = "NHAN_THUC"; continue
            # 8. Kiểm vùng phủ: ngoài miền train thì không can thiệp dữ liệu được
            if not in_train_domain(f.condition, release):   # ví dụ vị trí vật Level 2 ngoài khoảng train
                f.diag = "NGOAI_MIEN"; continue
            d = knn_distance(f.condition, release.train_conditions, k=P.K)
            f.diag = "THIEU_VUNG_PHU" if d > P.tau_cov else "KY_NANG_YEU"
        cl.diag = majority([f.diag for f in cl.representatives(P.R)])   # hòa thì kỹ sư quyết

    # 9–10. Tách cụm theo chẩn đoán, đề xuất can thiệp và định lượng
    # DATA_DIAGNOSES = {TRANG_THAI_DAU_XAU, THIEU_VUNG_PHU, KY_NANG_YEU}; NHAN_THUC, NGOAI_MIEN chỉ ra báo cáo
    proposals = [propose(cl, P) for cl in split_by_diag(clusters)
                 if cl.diag in DATA_DIAGNOSES]
    # 11. Chọn theo lợi ích kỳ vọng trên chi phí, trong ngân sách
    for p in proposals:
        p.n_eff = min(p.n_failures, P.cap[p.kind])        # số lỗi thực được xử lý sau giới hạn mỗi cụm (mục 6.10)
        p.gain = p.n_eff / len(dev) * fix_rate[p.kind].mean()
        p.cost = ledger_estimate(p, n=p.n_eff)
    chosen = greedy_by_ratio(proposals, budget, tie_break=lambda p: p.stage)   # hòa thì bước hỏng sớm hơn trước
    # Cụm lỗi hệ thống hoặc không khả thi thành phiếu sửa, không tiêu ngân sách dữ liệu
    return chosen, repair_tickets(clusters), evidence_cards(clusters)
```

Vòng ngoài của nhánh C:

```python
policy = finetune(PSI0_BASE, teleop_subset(0.7 * D_star), steps=S)   # pi_0, cũng là nhánh A0.7
release = release_of(teleop_subset(0.7 * D_star))
aa_floor = aa_test(policy, gate_conditions(round=1), n_runs=3)       # A/A test một lần, ở G3 (mục 6.12)
for r in range(1, P.rounds + 1):        # Ψ₀: P.rounds = 1 mặc định, tối đa 2; F-ACT: 5–8 (mục 7.8)
    chosen, tickets, cards = failure_to_data_round(policy, release, DEV, B_round[r], fix_rate, P)
    chosen = engineer_review(cards, chosen)          # kỹ sư duyệt hoặc ghi đè, có lý do
    fix_system(tickets)                              # sửa hệ thống thì phải đo lại baseline
    release = qa_and_release(release, acquire(chosen))
    candidate = finetune(policy, release, replay=True)
    report = dev_gate(candidate, policy, gate_conditions(round=r), n_runs=3, aa_floor=aa_floor)
    fixed = measure_fixed(candidate, policy, chosen, n_runs=3)   # đối chứng với cha, điều kiện mới quanh lỗi (mục 6.13)
    update_fix_rates(fix_rate, chosen, fixed)
    if report.promote:
        policy = candidate
    if should_stop(report, ledger, P):
        break
final_C = finetune(PSI0_BASE, release, steps=S)      # train lại từ base, cùng S với A và B
```

Trong các vòng, fine-tune tiếp từ checkpoint cha để nhanh. Model cuối của nhánh C được train lại từ checkpoint gốc với cùng số bước S như A và B, để phép so sánh chỉ khác nhau ở dữ liệu. Với F-ACT, `PSI0_BASE` thay bằng khởi tạo ACT.

### 6.2 Bước 1–2: chạy và gán nhãn

Chạy policy trên 90 điều kiện của tập tìm lỗi (dev), mỗi điều kiện một lượt. Scorer ở mục 5 gán bước hỏng đầu tiên và kiểu lỗi. Trace của mọi episode được lưu, kể cả episode thành công (dùng cho evidence card và thống kê theo mức). Phép kiểm hồi quy ở bước 12 chạy trên tập cổng mới, không trên tập này (mục 6.12).

### 6.3 Bước 3: gom cụm sơ bộ

Gom lỗi theo khóa (bước hỏng k, kiểu lỗi, mức). Các phép kiểm 5–7 tốn rollout nên chỉ chạy trên tối đa R = 5 đại diện mỗi cụm, chọn ngẫu nhiên có ghi hạt giống. Phép kiểm 4 và 8 rẻ nên chạy cho mọi episode lỗi.

### 6.4 Bước 4: kiểm hệ thống

Đối tượng kiểm là **stack decoupled WBC** của task chính (`g1_sonic`, `SonicLocoManipEnv`), không phải AMO. "Lệnh gửi" và "trạng thái đo" định nghĩa theo giao diện của WBC:

- **Lệnh gửi:** lệnh thân trên (mục tiêu khớp tay, cổ tay, bàn tay) và lệnh thân dưới (lệnh di chuyển và tư thế thân mà WBC nhận) ở mỗi chu kỳ.
- **Trạng thái đo:** góc khớp thân trên đo được, và trạng thái thân dưới đo được tương ứng với lệnh thân dưới (vận tốc gốc, chiều cao và hướng thân).
- Trường cụ thể chốt ở G0 theo agent `psi0_decoupled_wbc` và ghi vào RunPlan.

Chỉ dùng log, chạy theo thứ tự:

1. **Thiếu tín hiệu** (camera mất khung, trace thiếu trường): chẩn đoán CHƯA RÕ, đề xuất thu thêm bằng chứng, không can thiệp dữ liệu.
2. **Sai số bám lệnh**: chuẩn của (lệnh gửi − trạng thái đo), tính riêng cho thân trên và thân dưới, vượt τ_track của phần đó, với τ_track là phân vị 99 trên episode teleop thành công. Chẩn đoán LỖI CONTROLLER; kiểm cấu hình stack WBC và ánh xạ khớp.
3. **Độ trễ**: phân vị 99 độ trễ chu kỳ suy luận vượt τ_lat, với τ_lat là phân vị 99 trên lần chạy chuẩn ở G0. Chẩn đoán LỖI RUNTIME.
4. **Đồng bộ cảm biến**: lệch thời gian lớn nhất giữa khung ảnh và state (theo timestamp trong trace) vượt τ_sync, với τ_sync hiệu chỉnh từ demo teleop thành công (phân vị 99). Chẩn đoán LỖI ĐỒNG BỘ.
5. **Camera chuẩn**: tham số camera (nội tham số, tư thế camera) khác bản tham chiếu đã hash ở G0. Chẩn đoán LỖI CALIBRATION.

Lỗi hệ thống được sửa trước. Sau khi sửa phải chạy lại baseline của policy hiện tại, vì phép đo cũ không còn giá trị.

### 6.5 Bước 5: kiểm khả thi

Chạy planner motion planning của SIMPLE từ đúng điều kiện đầu. Nếu planner cũng thất bại thì điều kiện có thể không khả thi (vật ngoài tầm với, va chạm không tránh được). Chẩn đoán KHÔNG KHẢ THI; kỹ sư sửa cảnh hoặc loại vùng điều kiện đó khỏi miền task và ghi lại. Planner ở bước 5 và bước 6 phải chạy trong env WBC của task chính (tuyến T1 hoặc T3, mục 10), vì khả thi dưới AMO không chứng minh khả thi dưới WBC và trạng thái sinh trong env AMO không nạp được vào env WBC. Nếu chưa có planner như vậy (Q2 hoặc V3 âm), dùng demo teleop có điều kiện gần nhất làm phép thử thay thế và đánh dấu "kiểm khả thi gần đúng".

### 6.6 Bước 6: khoanh vùng bằng reset

Chạy planner (hoặc demo teleop gần nhất) từ cùng điều kiện đầu đến đầu bước k, lưu trạng thái simulator làm **trạng thái chuẩn**. Đặt simulator vào trạng thái này rồi để policy chạy M = 10 lượt, ra tỉ lệ thành công s_k.

- **s_k ≥ τ_k = 0,8:** policy làm tốt bước k nếu bắt đầu đúng, nên lỗi do bước trước để lại trạng thái xấu. Chẩn đoán TRẠNG THÁI ĐẦU XẤU, cần dữ liệu phục hồi.
- **s_k < 0,8:** bản thân kỹ năng ở bước k yếu; đi tiếp phép kiểm 7 và 8.

Nếu Q3 trả lời "không", bỏ bước này và đánh dấu cụm là "chưa khoanh vùng".

### 6.7 Bước 7: kiểm thị giác

Chỉ áp dụng cho lỗi ở Level 1 và 2. Giữ nguyên điều kiện vật lý, đặt tham số hình ảnh (ánh sáng, vật liệu) về mức chuẩn của Level 0 rồi chạy lại. Nếu thành công, lỗi nằm ở nhận thức: chẩn đoán NHẬN THỨC. Chẩn đoán này được ghi nhận và báo cáo nhưng không tiêu ngân sách trong PoC, vì tăng cường thị giác đã là phần cố định của recipe cho mọi nhánh (mục 7.3).

### 6.8 Bước 8: kiểm vùng phủ

Trước hết kiểm điều kiện của lỗi có nằm trong miền train không. Miền train là khoảng [min, max] của từng thành phần vật lý của vector điều kiện (vị trí và góc vật, vị trí đích, lệch xuất phát robot) trên điều kiện train; thành phần hình ảnh đã do bước 7 xử lý.

- **Ngoài miền train** (ví dụ vị trí vật của Level 2 nằm ngoài khoảng train): chẩn đoán NGOÀI MIỀN. Không tiêu ngân sách, vì mọi can thiệp dữ liệu phải nằm trong miền train (mục 7.3) nên vùng lấy mẫu sẽ rỗng. Số lỗi NGOÀI MIỀN theo mức được báo cáo.

Với lỗi trong miền, tính khoảng cách trung bình d từ vector điều kiện của lỗi tới K = 5 điều kiện train gần nhất. Ngưỡng τ_cov là phân vị 95 của khoảng cách tương tự trong tập train, tính kiểu leave-one-out.

- **d > τ_cov:** lỗi nằm ngoài vùng dữ liệu đã phủ. Chẩn đoán THIẾU VÙNG PHỦ.
- **d ≤ τ_cov:** đã có dữ liệu gần đó mà vẫn lỗi, thường do dữ liệu mâu thuẫn hoặc tình huống khó. Chẩn đoán KỸ NĂNG YẾU.

### 6.9 Bảng quyết định

| Chẩn đoán | Điều kiện | Can thiệp | Tiêu ngân sách dữ liệu? |
|---|---|---|---|
| CHƯA RÕ | Thiếu tín hiệu | Thu thêm bằng chứng, sửa logging | Không |
| LỖI CONTROLLER | Sai số bám lệnh > τ_track | Sửa cấu hình stack WBC, ánh xạ khớp | Không |
| LỖI RUNTIME | Độ trễ > τ_lat | Sửa pipeline suy luận | Không |
| LỖI ĐỒNG BỘ | Lệch thời gian ảnh và state > τ_sync | Sửa đồng bộ cảm biến | Không |
| LỖI CALIBRATION | Tham số hoặc tư thế camera khác bản tham chiếu | Sửa calibration camera | Không |
| KHÔNG KHẢ THI | Planner chuẩn thất bại | Sửa cảnh hoặc thu hẹp miền task | Không |
| TRẠNG THÁI ĐẦU XẤU | s_k ≥ τ_k | Dữ liệu phục hồi: correction bắt đầu từ trạng thái do policy tạo ở đầu bước k | Có |
| NHẬN THỨC | Kiểm thị giác thành công | Ghi nhận và báo cáo; tăng cường thị giác đã cố định cho mọi nhánh (mục 7.3) | Không |
| NGOÀI MIỀN | Điều kiện ngoài miền train | Ghi nhận và báo cáo | Không |
| THIẾU VÙNG PHỦ | Trong miền, d > τ_cov | Sinh rollout sim quanh điều kiện lỗi | Có |
| KỸ NĂNG YẾU | Trong miền, d ≤ τ_cov | Teleop correction ở bước k; kiểm demo mâu thuẫn trong lân cận chỉ ra báo cáo | Có |

Thứ tự kiểm là cố định: hệ thống trước, dữ liệu sau. Một lỗi đã có chẩn đoán hệ thống thì không đi tiếp vào nhánh dữ liệu. Có 11 chẩn đoán; chỉ ba chẩn đoán tiêu ngân sách dữ liệu: TRẠNG THÁI ĐẦU XẤU, THIẾU VÙNG PHỦ, KỸ NĂNG YẾU.

### 6.10 Định lượng can thiệp

Giá trị mặc định, ghi vào RunPlan và chỉnh được:

| Can thiệp | Số lượng | Giới hạn mỗi cụm | Số lỗi xử lý tối đa L_t |
|---|---|---|---|
| Sinh sim quanh điều kiện lỗi | 20 rollout đạt QA cho mỗi lỗi, điều kiện lấy đều trong bán kính τ_cov quanh điều kiện lỗi và nằm trong miền train | 200 rollout | 10 |
| Teleop correction | 1 correction cho mỗi lỗi | 10 correction | 10 |
| Dữ liệu phục hồi | 1 đoạn phục hồi cho mỗi lỗi, bắt đầu từ trạng thái lỗi đã lưu | 10 đoạn | 10 |

Khi cụm có m_j > L_t lỗi, chọn ngẫu nhiên L_t lỗi, có ghi hạt giống. Số lỗi thực được xử lý là n_eff_j = min(m_j, L_t); lợi ích và chi phí ở mục 6.11 tính trên n_eff_j.

Hai việc không còn là can thiệp tiêu ngân sách của C:

- **Tăng cường thị giác** là phần cố định của recipe, áp như nhau cho mọi nhánh (mục 7.3).
- **Kiểm demo mâu thuẫn** (cụm KỸ NĂNG YẾU): kỹ sư xem tối đa 10 demo gần nhất trong vùng lỗi và ghi demo nghi hỏng vào báo cáo. Không loại demo khỏi danh sách 0,7D\*, để A₀.₇, B, B-fail và C dùng cùng danh sách. Giờ kỹ sư tính vào chi phí chẩn đoán.

Nếu Q6 trả lời "không", teleop correction và dữ liệu phục hồi do planner trong env WBC sinh từ trạng thái đã lưu, và báo cáo ghi rõ correction là do máy sinh.

### 6.11 Chọn can thiệp theo ngân sách

- Mỗi loại can thiệp t có **tỉ lệ sửa được** f_t theo phân phối Beta(α_t, β_t), khởi đầu Beta(1, 1) cho mọi loại (trung bình 0,5, không thiên vị).
- Với đề xuất cho cụm j có m_j lỗi trên N_dev = 90 điều kiện của tập tìm lỗi: số lỗi thực được xử lý n_eff_j = min(m_j, L_t) (mục 6.10); lợi ích kỳ vọng g_j = (n_eff_j / N_dev) × trung bình của f_t, đơn vị là điểm % thành công trên dev.
- Chi phí c_j ước tính từ đơn giá trong sổ chi phí và số lượng ở mục 6.10, tính trên n_eff_j lỗi.
- Sắp đề xuất theo g_j / c_j giảm dần, chọn lần lượt cho đến khi hết ngân sách vòng. Hòa thì ưu tiên cụm có bước hỏng k sớm hơn, vì lỗi sớm chặn mọi bước sau.
- **Tính chất cần biết:** g_j và c_j cùng tỉ lệ với n_eff_j, nên g_j / c_j = f̄_t / (N_dev × đơn giá mỗi lỗi của loại t) không phụ thuộc cụm. Ở vòng 1 (prior đều, mọi f̄_t = 0,5), thứ tự chọn chỉ là **đơn giá của loại can thiệp trong các loại mà chẩn đoán cho phép**; chẩn đoán quyết định loại nào được phép, giới hạn L_t quyết định số lượng. Chỉ từ khi f_t đã được cập nhật (vòng 2 trở đi, hoặc F-ACT ở mục 7.8) thì thứ tự mới phản ánh hiệu quả đo được. Có unit test chứng minh tính chất này.
- Ngân sách nhánh C bằng B_add (mục 7.3). Ψ₀ mặc định 1 vòng, dùng toàn bộ B_add. Nếu chạy vòng 2 trên Ψ₀ (chốt trong RunPlan trước vòng 1), chia 60% cho vòng 1 và 40% cho vòng 2. Trong F-ACT, B_add chia đều cho số vòng đã khai.

### 6.12 Thu dữ liệu, train và cổng dev

1. Thu dữ liệu theo danh sách đã chọn; mọi mẫu qua QA ở mục 4.4.
2. Tạo release mới: release cũ cộng dữ liệu mới, giữ lineage. Dữ liệu cũ luôn được trộn lại (replay).
3. Fine-tune từ checkpoint cha.
4. **Cổng dev:** mỗi vòng dùng một **tập cổng mới** gồm 90 điều kiện (30 mỗi mức) lấy từ phần chưa dùng của dải hạt giống dev, không dùng lại tập tìm lỗi. Chạy cả policy cha và ứng viên trên tập này, mỗi điều kiện ≥ 3 lượt. Ứng viên được chấp nhận khi:
   - Thành công trên toàn tập cổng tăng ít nhất 1 sai số chuẩn của chênh lệch ghép cặp (SE tính theo điều kiện, mỗi điều kiện lấy trung bình các lượt).
   - Các cụm được can thiệp cải thiện trên điều kiện mới quanh lỗi (phép đo ở mục 6.13).
   - Hồi quy không vượt ngưỡng: trong số điều kiện cha thành công ở đa số lượt, tỉ lệ điều kiện ứng viên thất bại ở đa số lượt ≤ max(5%, sàn A/A).
5. **A/A test:** chạy một lần ở G3 cho mỗi model (Ψ₀; ACT cho F-ACT). Policy cha chạy hai lần độc lập trên tập cổng vòng 1, mỗi lần 3 lượt mỗi điều kiện, coi một lần là "cha" và lần kia là "ứng viên". Tỉ lệ hồi quy đo được là **sàn hồi quy giả**, do nhiễu chạy lại chứ không do policy.

Ứng viên trượt cổng không được dùng tiếp, nhưng evidence card và chi phí của nó vẫn được giữ.

### 6.13 Cập nhật tỉ lệ sửa được và điều kiện dừng

Chạy lại đúng điều kiện đã lỗi một lượt sẽ thiên lệch hồi quy về trung bình: điều kiện có xác suất thành công thật p_i thì không làm gì cũng "sửa được" với tỉ lệ p_i. Vì vậy tỉ lệ sửa được đo **có đối chứng, trên điều kiện mới quanh lỗi**:

1. Với mỗi cụm j đã can thiệp bằng loại t, lấy điều kiện mới quanh từng điều kiện lỗi: cùng mức, phần vật lý trong bán kính τ_cov / 2, tối đa 5 điều kiện mỗi lỗi và 30 điều kiện mỗi cụm. Gọi n là số điều kiện lấy được. Hạt giống lấy từ phần chưa dùng của dải dev.
2. Chạy policy cha và ứng viên trên n điều kiện này, mỗi bên ≥ 3 lượt mỗi điều kiện; tính tỉ lệ thành công p_cha và p_ứng viên.
3. fixed_j = làm tròn(n × (p_ứng viên − p_cha)), kẹp trong [0, n].
4. Cập nhật α_t += fixed_j và β_t += n − fixed_j.

Rollout của phép đo này ghi vào sổ là chi phí đánh giá, không tính vào B_add. Qua các vòng, f_t cho biết loại can thiệp nào thực sự sửa được loại lỗi nào trên task này. Với Ψ₀ chỉ 1 vòng mặc định, f_t được đo nhưng không kịp dùng lại; bằng chứng "flywheel học" lấy từ thí nghiệm F-ACT (mục 7.8).

Dừng vòng lặp khi gặp một trong các điều kiện:

- Hết ngân sách.
- Đề xuất tốt nhất có g/c dưới 1 điểm % cho mỗi $100.
- Hai vòng liên tiếp không qua cổng dev.
- Đã đủ số vòng khai trong RunPlan (Ψ₀: 1 mặc định, tối đa 2; F-ACT: 5–8).

### 6.14 Vai trò kỹ sư

Thuật toán đề xuất; kỹ sư quyết định. Kỹ sư được ghi đè chẩn đoán hoặc can thiệp nhưng phải ghi lý do vào evidence card. Tỉ lệ ghi đè là một chỉ số được báo cáo: nếu kỹ sư ghi đè phần lớn đề xuất thì các phép kiểm tự động chưa đủ tốt.

### 6.15 Tham số mặc định

| Tham số | Giá trị khởi đầu | Cách hiệu chỉnh |
|---|---|---|
| R (đại diện mỗi cụm) | 5 | Giữ cố định trong PoC |
| M (lượt chạy từ trạng thái chuẩn) | 10 | Giữ cố định |
| τ_k | 0,8 | Giữ cố định |
| K (láng giềng gần nhất) | 5 | Giữ cố định |
| τ_track | Phân vị 99 sai số bám lệnh trên episode teleop thành công | G1 |
| τ_lat | Phân vị 99 độ trễ chu kỳ trên lần chạy chuẩn | G0 |
| τ_cov | Phân vị 95 khoảng cách kNN leave-one-out trong tập train | G1 |
| τ_sync | Phân vị 99 lệch thời gian giữa khung ảnh và state trên demo teleop thành công | G1 |
| Camera tham chiếu | Hash tham số camera (nội tham số, tư thế) của cấu hình chuẩn | G0 |
| L_t (số lỗi xử lý tối đa mỗi cụm) | 10 cho mọi loại can thiệp (mục 6.10) | Giữ cố định |
| Tập cổng mỗi vòng | 90 điều kiện mới (30 mỗi mức) từ dải dev chưa dùng | Giữ cố định |
| Số lượt mỗi điều kiện ở cổng và ở phép đo tỉ lệ sửa được | 3 (tối thiểu) | Giữ cố định |
| Điều kiện đo tỉ lệ sửa được | Bán kính τ_cov / 2; tối đa 5 điều kiện mỗi lỗi, 30 mỗi cụm | Giữ cố định |
| Hồi quy cho phép | max(5%, sàn A/A) | Sàn A/A đo ở G3 |
| Ngưỡng "tăng" ở cổng | ≥ 1 sai số chuẩn của chênh lệch ghép cặp | Chốt trước vòng 1 |
| Ngưỡng dừng g/c | 1 điểm % cho mỗi $100 | Chốt trước vòng 1 |
| Số vòng | Ψ₀: 1 (tối đa 2); F-ACT: 5–8 | Chốt trong RunPlan trước vòng 1 |
| Prior tỉ lệ sửa được | Beta(1, 1) | Không đổi trong PoC |

## 7. Thiết kế PoC

### 7.1 Giai đoạn E1: đường cong hiệu quả dữ liệu và D\*

Train mỗi phương pháp (ACT, Diffusion Policy, Ψ₀) với 10%, 25%, 50%, 70% và 100% của N_teleop demo teleop (1 seed). Đánh giá trên 90 điều kiện dev.

- **D\*** là mức nhỏ nhất mà Ψ₀ đạt ≥ 75% trên dev gộp ba mức (Cấp 2 của BTC, mục 3). Nhánh A dùng D\* demo, các nhánh còn lại dùng 0,7D\*.
- **Chọn D\* chống may mắn:** điểm đầu tiên vượt ngưỡng với 1 seed dễ là may. Chạy thêm seed thứ hai cho Ψ₀ ở hai điểm lưới quanh ngưỡng (điểm đầu tiên vượt 75% và điểm ngay dưới), lấy trung bình 2 seed; hoặc nội suy đường cong giữa hai điểm. Seed thứ hai ở mức D\* cũng là đầu vào cho power analysis ở G2 (mục 7.5).
- **Trần:** nếu Ψ₀ ở mức 10% đã đạt ≥ 90%, task quá dễ để đo khác biệt. Chuyển chỉ tiêu chính sang Level 2, hoặc đổi sang task khó hơn (Ψ₀ công bố 7/5/6 cho `LocomotionPickBetweenTablesTeleop`).
- **Sàn:** nếu ở mức 100% vẫn dưới 60%, D\* = N_teleop và ngưỡng 75% được thay bằng kết quả của nhánh A, ghi rõ trong báo cáo.
- **Đủ lỗi để nhắm:** ngay sau G3, báo số lỗi dev theo mức của π₀ (A₀.₇). Nếu Level 0 có dưới 15 lỗi, kích hoạt task khó hơn ở trên. Để kịp lịch, ước tính sớm số lỗi này ở G2 từ điểm lưới E1 gần 0,7D\* nhất. Cần xác nhận cách đếm: với 30 điều kiện Level 0 × 1 lượt, "dưới 15 lỗi" tương đương thành công Level 0 trên 50%, nên luật có thể kích hoạt ở hầu hết task.

Đường cong này là kết quả có giá trị riêng: chỉ số "số demo để đạt 75%" (kèm 80% để đối chiếu Pitch v10) theo từng phương pháp là phần chính của báo cáo so sánh phương pháp. Tỉ lệ thành công ở các mức 10% và 25% là chỉ tiêu Cấp 1 của BTC (≥ 50% với lượng demo nhỏ).

### 7.2 Các nhánh

| Nhánh | Dữ liệu train | Vai trò |
|---|---|---|
| A | D\* demo teleop | Baseline |
| A₀.₇ | 0,7D\* demo teleop | Đối chứng: không bổ sung gì; cũng là policy khởi đầu π₀ của nhánh C |
| B | 0,7D\* teleop + N_B rollout sim đạt QA, điều kiện lấy đều trong miền train. N_B = 2 × (D\* − 0,7D\*), làm tròn lên, kèm trần GPU-giờ; chốt trong RunPlan trước G3 | Kiểm HS; đối thủ của C trong HT và của B-fail trong HTa |
| C | 0,7D\* teleop + dữ liệu do Failure → Data chọn, tối đa B_add. Ψ₀: 1 vòng mặc định; ACT: kết quả của F-ACT (mục 7.8) | Kiểm HT và HTb |
| B-fail | 0,7D\* teleop + rollout sim sinh quanh mọi điều kiện lỗi dev của π₀, không chẩn đoán, cùng ngân sách B_add (kiểu Mulligan rút gọn). Điều kiện lấy đều trong bán kính τ_cov quanh mỗi lỗi, trong miền train; ngân sách chia đều theo số lỗi | Kiểm HTa; đối thủ của C trong HTb. Chạy trên ACT là chính; trên Ψ₀ nếu còn ngân sách sau G4 |
| B⁺ (tùy chọn, ưu tiên thấp hơn B-fail) | 0,7D\* teleop + đúng tỉ lệ các loại can thiệp mà C đã chọn, nhưng điều kiện lấy đều thay vì quanh điểm lỗi | Tách tác dụng của "nhắm đúng chỗ lỗi" khỏi tác dụng của "dùng nhiều loại can thiệp" |

Chênh lệch C − B gộp ba tác dụng: nhắm theo lỗi, chẩn đoán, và được dùng nhiều loại can thiệp hơn B (B chỉ có sim). B-fail tách phần đầu: HTa = B-fail − B đo tác dụng của nhắm theo lỗi; HTb = C − B-fail đo tác dụng của chẩn đoán cộng nhiều loại can thiệp. B⁺ tách thêm "nhiều loại can thiệp" khỏi "nhắm chỗ lỗi". Báo cáo phải nói rõ phần nào chưa tách được khi bỏ B-fail hoặc B⁺.

### 7.3 Quy tắc công bằng giữa các nhánh

1. Cùng checkpoint gốc Ψ₀ thuộc nhóm `pre.*` hoặc `postpre.*` đã qua Q0 (mục 2.4), ghi revision và nguồn gốc vào thực thể Source. Không dùng `simple-checkpoints` hoặc `sonic-checkpoints` cho E1 và các nhánh; hai thư mục này chỉ dùng để tái tạo số công bố ở G0.
2. Cùng số bước gradient S, batch, learning rate và lịch learning rate. S lấy theo cấu hình fine-tune công bố của Ψ₀ cho SIMPLE và ghi vào RunPlan.
3. A₀.₇, B, C, B-fail và B⁺ dùng cùng một danh sách 0,7D\* demo teleop. Kiểm demo mâu thuẫn không loại demo khỏi danh sách này (mục 6.10).
4. Tỉ lệ mẫu sim trong batch ρ chọn trong {0,25; 0,5} trên dev bằng nhánh B (1 seed), rồi áp nguyên cho C, B-fail và B⁺.
5. **B_add** là chi phí thực đo để tạo đúng N_B rollout sim đạt QA của nhánh B (mục 7.2): sinh sim, QA, tích hợp, kể cả rollout bị loại. Vì N_B và trần GPU-giờ chốt trước G3, B_add xác định được mà không vòng tròn. Nếu chạm trần GPU-giờ trước khi đủ N_B, B dừng ở số đã có và báo cáo. Nhánh C và B-fail bị chặn ở đúng B_add cho chi phí thu dữ liệu. Chi phí chẩn đoán của C (rollout kiểm tra, giờ kỹ sư) ghi riêng và cộng vào tổng chi phí khi báo cáo.
6. Dùng chung 3 seed huấn luyện {0, 1, 2} cho mọi nhánh; tăng lên 5 seed cho B và C nếu power analysis ở G2 yêu cầu (mục 7.5).
7. Không sinh dữ liệu với tham số của Level 1 hoặc Level 2. **Tăng cường thị giác là phần cố định của recipe**, áp như nhau cho mọi nhánh của cùng một phương pháp và khai trong RunPlan: chỉ biến đổi trên ảnh (độ sáng, độ tương phản, dịch màu), không dùng preset ánh sáng của SIMPLE. Đây không còn là can thiệp riêng của C.
8. Holdout chạy đúng một lần cho mỗi cặp nhánh và seed, sau khi checkpoint của nhánh đó, scorer và cấu hình đã đóng băng. Nhánh không phụ thuộc C chạy sớm và kết quả được niêm phong tới khi C xong (mục 7.5).
9. Báo riêng số demo người (teleop và correction) mà từng nhánh dùng.

### 7.4 Ma trận phương pháp

| Phương pháp | A | A₀.₇ | B | C | B-fail |
|---|---|---|---|---|---|
| Ψ₀ | Có | Có | Có | Có, 1 vòng mặc định | Nếu còn ngân sách sau G4 |
| Diffusion Policy | Có | Không | Có | Không | Không |
| ACT | Có | Chỉ làm π₀, 1 seed | Có | Có, từ F-ACT (mục 7.8) | Có |

Nhánh C trên Ψ₀ chạy 1 vòng mặc định vì tốn chi phí chẩn đoán và GPU. Trên ACT, C và B-fail rẻ, nên HTa và HTb kiểm trên ACT là chính, cùng thí nghiệm F-ACT. ACT và Diffusion Policy nhỏ, chạy được trên GPU của đội, và trả lời câu hỏi: dữ liệu sim giúp model nào nhiều nhất. B⁺ chỉ chạy nếu còn ngân sách sau B-fail.

### 7.5 Đánh giá holdout và thống kê

- **Thiết kế ghép cặp:** mọi nhánh và mọi seed chạy trên đúng 150 điều kiện holdout. Mỗi nhánh có 150 × 3 seed = 450 episode (750 nếu tăng lên 5 seed).
- **Holdout sớm và niêm phong:** nhánh không phụ thuộc C (A, A₀.₇, B của Ψ₀; A, B, B-fail của ACT; A, B của Diffusion Policy) chạy holdout ngay khi đóng băng, ở tuần 9–10. Kết quả lưu có hash và niêm phong, không ai xem cho tới khi C xong và chạy holdout ở G5.
- **Chỉ số chính:** tỉ lệ thành công toàn task theo **cờ thành công của SIMPLE** (`check_success`, so được với số công bố); scorer chỉ dùng cho chỉ số theo bước. Gộp ba mức và báo riêng từng mức; Level 1 và Level 2 báo riêng so với 70% (Cấp 3 của BTC, mục 3).
- **Chỉ số phụ:** tỉ lệ đạt từng bước, sai số vị trí đặt (mm), thời gian hoàn thành, tỉ lệ hồi quy trên điều kiện Level 0, tỉ lệ seed có cùng chiều chênh lệch, chi phí từ sổ chi phí.
- **Ước lượng:** chênh lệch giữa hai nhánh a và b là trung bình theo điều kiện i của (p_ia − p_ib), với p_ia là tỉ lệ thành công trung bình qua các seed. Khoảng tin cậy 95% lấy bằng **bootstrap phân cấp**, 10.000 lần lấy mẫu. Mỗi lần: (1) lấy mẫu lại seed huấn luyện, có hoàn lại, độc lập cho từng nhánh; (2) trong từng mức, lấy mẫu lại điều kiện, ghép cặp giữa hai nhánh; (3) tính chênh lệch. Cách này đưa phương sai giữa seed vào CI, nên CI nói về quy trình train chứ không chỉ về vài checkpoint cụ thể.
- **Kiểm tra chéo:** mô hình logistic hỗn hợp, hiệu ứng cố định là nhánh và mức, hiệu ứng ngẫu nhiên theo điều kiện và theo lần train (cặp nhánh, seed). Nếu hai cách cho kết luận khác nhau, báo cả hai và không nêu kết luận.
- **Độ ổn định:** báo kết quả từng seed. Quy tắc "chiều chênh lệch giữ nguyên ở ≥ 2/3 seed" chỉ là chỉ số phụ, không quyết định kết luận.
- **Power analysis ở G2:** dùng 2 seed của Ψ₀ ở mức D\* (mục 7.1) để đo độ lệch giữa seed, cộng phương sai theo điều kiện trên dev; tính hiệu ứng nhỏ nhất phát hiện được (MDE) của C − B với 80% lực, cùng mức tin cậy với tiêu chí ở mục 3, với 150 điều kiện holdout và số seed dự kiến. Nếu MDE > 10 điểm %, chọn một trong ba và ghi vào RunPlan trước G3: (a) tăng Ψ₀ lên 5 seed cho B và C; (b) chuyển chỉ tiêu chính của HT sang mức còn dư địa; (c) hạ HT thành kết quả mô tả. Nếu phải cắt Ψ₀ về 2 seed (mục 10), HT tự động thành kết quả mô tả.
- **Kiểm độ rộng trước khi chạy holdout:** dùng phương sai đo trên dev và độ lệch giữa seed ở trên để ước tính độ rộng khoảng tin cậy. Nếu nửa độ rộng dự kiến lớn hơn 7 điểm %, tăng số điều kiện holdout trước G5.

Để tham khảo: với 50 lượt độc lập ở mức 80%, khoảng tin cậy Wilson 95% là khoảng 67%–89%. Đó là lý do Pitch v10 cần chuyển từ "≥ 80% / 50 lượt" sang thiết kế ghép cặp nhiều seed ở trên.

### 7.6 Thí nghiệm HD: đo thời gian chẩn đoán

- **Nghiệm thu chẩn đoán tự động trên lỗi cấy** (trước thí nghiệm với người): chạy chuỗi chẩn đoán trên bộ lỗi cấy có đáp án khóa trước. Báo **recall theo từng lớp** (không gộp), và **đối chứng sạch**: episode không cấy lỗi, đo tỉ lệ báo nhầm lớp hệ thống. Trễ camera phải ra LỖI ĐỒNG BỘ, lệch calibration phải ra LỖI CALIBRATION (mục 6.4).
- **Mẫu:** 20 episode lỗi.
  - 10 lỗi **cấy có chủ đích**, biết đáp án: lệch lệnh controller, trễ camera, lệch calibration camera, thiếu vùng phủ (train bỏ một vùng điều kiện), ánh sáng ngoài miền; mỗi loại 2 episode.
  - 10 lỗi tự nhiên từ dev. Đáp án là chẩn đoán mà can thiệp tương ứng có tỉ lệ sửa được đo có đối chứng (mục 6.13) ít nhất 0,5 trên cụm.
  - Trong điều kiện có card, 3–4 evidence card được **làm sai cố ý** (chẩn đoán hoặc số liệu sai, đáp án khóa trước) để đo mức tin mù quáng: tỉ lệ người làm theo card sai.
- **Người tham gia:** ≥ 2 người ngoài đội (mentor hoặc đội khác) cùng thành viên đội; kết quả báo riêng hai nhóm.
- **Thiết kế chéo:** mỗi episode được một người chẩn đoán bằng **công cụ chuẩn** (Rerun cộng đồ thị mặc định, không phải log do đội tự đóng gói) và một người khác chẩn đoán bằng evidence card; thứ tự đối trọng giữa người và điều kiện.
- **Đo:** số phút đến khi ra quyết định, chẩn đoán đúng theo 11 lớp ở mục 6.9, can thiệp đúng, tỉ lệ làm theo card sai.
- **Ước lượng:** r_debug = 1 − (thời gian trung bình có card / thời gian trung bình với công cụ chuẩn), chỉ dùng khi độ đúng có card không thấp hơn. r_debug báo **dạng khoảng** (bootstrap theo người và episode), không báo một điểm.
- **Giới hạn phải nêu:** mẫu nhỏ; đáp án của lỗi tự nhiên có phần dựa vào chính các phép kiểm.

### 7.7 Quy tắc diễn giải

- HS và HT được kết luận độc lập. HT trượt là kết quả hợp lệ và phải được báo cáo: khi đó giá trị còn lại của platform là Data Core, sổ chi phí và khuyến nghị thu dữ liệu định lượng, và Pitch phải bỏ claim "nhắm lỗi thắng rải đều".
- HTa và HTb đọc cùng nhau: HTa đạt mà HTb trượt nghĩa là nhắm theo lỗi có ích nhưng chẩn đoán chưa đáng chi phí; HTa trượt mà HTb đạt nghĩa là lợi ích đến từ chẩn đoán và nhiều loại can thiệp, không từ việc nhắm theo lỗi.
- Nếu C chỉ hơn B khi chưa tính chi phí chẩn đoán, báo cả hai con số. HT báo kèm hai ràng buộc riêng: phút người và GPU-giờ (mục 8.3).
- Kết quả âm, ứng viên bị từ chối, vòng không có cải thiện đều được giữ trong báo cáo cùng chi phí của chúng.

### 7.8 Thí nghiệm F-ACT: bằng chứng "flywheel học"

Ψ₀ chỉ chạy 1 vòng C mặc định, nên không đủ vòng để thấy tỉ lệ sửa được học dần. F-ACT chạy **5–8 vòng Failure → Data rẻ với ACT** trên cùng task để có bằng chứng đó. Không dùng Ψ₀ cho phần này.

- **Thiết lập:** π₀ là ACT train trên cùng danh sách 0,7D\* (1 seed). Thuật toán (mục 6.1), cổng có A/A test riêng cho ACT (mục 6.12), phép đo tỉ lệ sửa được (mục 6.13) và tham số (mục 6.15) giữ như nhánh C trên Ψ₀. Tổng ngân sách thu dữ liệu là B_add, chia đều cho số vòng. Số vòng khai trong RunPlan trước vòng 1.
- **Đo theo vòng:** trung bình và CI 95% của f_t từng loại can thiệp; chi phí mỗi điểm % tăng trên tập cổng; thứ tự chọn can thiệp so với thứ tự theo đơn giá ở vòng 1 (mục 6.11); tỉ lệ ghi đè của kỹ sư; số cụm theo chẩn đoán.
- **Kết luận mô tả, không phải kiểm định:** "flywheel học" được nêu khi CI của f_t hẹp dần và ổn định qua các vòng, và chi phí mỗi điểm % giảm. Nếu không thấy, báo đúng như vậy.
- **Dùng cho HTa và HTb:** release cuối của F-ACT được train lại từ khởi tạo ACT, 3 seed, làm nhánh C trên ACT; so với B-fail và B trên ACT ở holdout.
- **Giới hạn phải nêu:** kết quả trên ACT không chứng minh hành vi trên Ψ₀. Khi policy gần trần, lợi ích biên giảm nên chi phí mỗi điểm % có thể tăng dù chọn can thiệp tốt hơn. Mỗi vòng tốn nhiều rollout (mục 9), cần kiểm thông lượng ở G0.

## 8. Sổ chi phí và mô hình kinh tế

### 8.1 Ghi chép

Mọi hoạt động tiêu tốn nguồn lực đều có một mục sổ (mục 4.5): thu teleop, reset cảnh, QA, sinh sim, chẩn đoán, train, đánh giá, lưu trữ, giờ kỹ sư tích hợp. Đơn giá dùng giả định của Pitch v10 cho đến khi có số của DENSO: operator $10/h, kỹ sư $20/h, A100 80 GB $1,59/GPU-h, RTX 4090 $0,74/GPU-h, lưu trữ $0,07/GB-tháng (nguồn ở slide 13 của pitch). Đơn giá operator $10/h chưa tính **chi phí giờ cell** (robot, người giám sát, thời gian dừng dây chuyền); số này chờ DENSO và được xét qua bảng độ nhạy ở mục 8.4.

### 8.2 Công thức của Pitch v10 và độ nhạy

Từ bảng ở slide 8 và 12 của Pitch v10, lợi ích ròng mỗi đợt cải thiện rút gọn thành:

**Lợi ích ròng/đợt = 500 × r_demo + 400 × r_debug − 181,80 (USD)**

- $500 là chi phí thu và QA teleop của baseline; $400 là chi phí debug của baseline.
- $181,80 là chi phí tăng thêm của phương án mới: GPU sinh sim $14,80, QA sim và tích hợp $160, lưu trữ thêm $7.

| r_demo | r_debug | Lợi ích ròng/đợt |
|---|---|---|
| 30% | 50% | +$168,20 (kịch bản Pitch v10) |
| 30% | 0% | −$31,80 |
| khoảng 36% | 0% | Hòa vốn |
| 50% | 0% | +$68,20 |
| 30% | 25% | +$68,20 |

r_debug là đòn bẩy lớn nhất, và chỉ thí nghiệm HD cho số đo của nó. Công thức có hai điểm yếu phải nói thẳng:

- Không có số hạng nào cho HT: r_demo đến từ HS, r_debug đến từ HD. Lõi chọn theo lỗi không đóng góp đô-la nào trong công thức này.
- Với r_demo = 30%, hòa vốn chỉ cần r_debug khoảng 8% ((181,80 − 150) / 400), nên kết luận "có lãi" gần như chắc chắn. Vì vậy r_debug dùng trong công thức là **khoảng** đo ở HD (mục 7.6), lợi ích ròng báo theo cận dưới và cận trên, và báo cáo không dẫn bằng đô-la mà bằng các chỉ số ở mục 8.3.

### 8.3 Thay giả định bằng số đo

| Giả định trong Pitch v10 | Số đo thay thế từ PoC |
|---|---|
| Giảm 30% demo | r_demo của nhánh thắng (mục 4.1), chỉ khi nhánh đó đạt HS |
| Giảm 50% giờ debug | Khoảng r_debug từ HD |
| 140 A100-giờ train và đánh giá mỗi đợt | GPU-giờ thực trong sổ, theo từng nhánh |
| Thu/reset 6 phút, QA 3 phút mỗi lượt | Thời gian thực của teleop và correction trong SIMPLE |
| 144 đợt mỗi năm | Không đo được trong PoC; cần DENSO xác nhận số task và biến thể mỗi năm |

**Chỉ số chính của báo cáo kinh tế**, đều lấy từ sổ chi phí và holdout:

1. **Số demo người để đạt ngưỡng** (teleop và correction, ngưỡng 75%), theo phương pháp và theo nhánh.
2. **Phút operator cho mỗi điểm % tăng thêm**, theo nhánh và theo loại can thiệp.
3. **Chi phí mỗi điểm % tăng thêm của C so với B và so với B-fail:** (tổng chi phí của C, gồm chẩn đoán, trừ tổng chi phí của nhánh đối chiếu) chia cho (thành công của C trừ thành công của nhánh đối chiếu). Nếu CI của mẫu số chứa 0, ghi "không xác định".
4. **Sai số dự báo chi phí:** (ước tính − thực đo) / thực đo cho từng can thiệp, từ cờ "ước tính" và "thực đo" trong sổ (mục 4.5).
5. **Số ngày để policy đạt lại ngưỡng** sau khi đổi điều kiện.

r_debug luôn báo dạng khoảng. **HT báo kèm hai ràng buộc riêng:** số phút người và số GPU-giờ mà B, B-fail và C đã dùng. "Cùng ngân sách USD" phụ thuộc tỉ giá giữa giờ người và GPU-giờ, nên báo cáo nêu rõ C có còn trong ngân sách của B khi chỉ xét phút người, và khi chỉ xét GPU-giờ.

### 8.4 Độ nhạy theo đơn giá và chi phí giờ cell

Chi phí giờ cell áp cho mọi phút teleop, correction và reset, vì trên robot thật mỗi phút này chiếm cell. Với mỗi kịch bản, tính lại chi phí mỗi điểm % (chỉ số 3 ở mục 8.3), lợi ích ròng/đợt theo khoảng r_debug, và xem kết luận HT có đổi chiều không.

| Kịch bản | Đơn giá operator | Chi phí giờ cell | Đơn giá GPU | Mục đích |
|---|---|---|---|---|
| Pitch v10 | $10/h | $0 | Theo mục 8.1 | Đối chiếu với pitch |
| DENSO | Đơn giá DENSO | Chi phí giờ cell DENSO | Theo mục 8.1 | Kịch bản chính khi DENSO gửi số |
| Cell đắt | $10/h | $100/h, giả định để kiểm độ nhạy | Theo mục 8.1 | Khi chi phí cell lớn hơn hẳn nhân công |
| GPU đắt | $10/h | $0 | 2 × mục 8.1 | Khi GPU thuê đắt hoặc khan |

## 9. Lộ trình 12 tuần và cổng

**Nguyên tắc lập kế hoạch:**

- Lập kế hoạch ở **70% năng lực** của đội; 30% còn lại là đệm cho việc chưa biết.
- **Lát dọc trên SIMPLE trước tuần 4:** ít nhất một trace SIMPLE thật đi trọn chạy → scorer → evidence card → sổ chi phí.
- **Mặc định 1 vòng C cho Ψ₀**; các vòng thêm chạy trên ACT (F-ACT, mục 7.8).
- **Holdout sớm, niêm phong** cho nhánh không phụ thuộc C (mục 7.5), để tuần 11 chỉ còn holdout của C.

| Tuần | Cổng | Việc | Điều kiện đi tiếp |
|---|---|---|---|
| 1–2 | G0 · Tái tạo | Cài SIMPLE và Ψ₀; tái tạo số công bố trên một task (dùng `simple-checkpoints` chỉ ở bước này); trả lời Q0–Q6 và V3 (V3 hạn ngày 5 của Sprint 1); thử T1 và T2 song song nếu V3 âm; lưu hash camera tham chiếu; đo VRAM, GPU-giờ fine-tune, thời gian mỗi episode | Chạy 30 lượt mỗi mức; đạt khi kiểm nhị thức một phía (α = 0,05) không cho thấy tỉ lệ thật thấp hơn số công bố (với số công bố 10/10, so với cận dưới Wilson 95% là khoảng 72%). Tuyến T1–T4 chốt cuối tuần 2 |
| 3–4 | G1 · Data Core v0 | Nạp psi-data, QA, lineage, chia tập, guard gần trùng; scorer từng bước; hiệu chỉnh τ_track, τ_cov, τ_sync; lát dọc trên SIMPLE; train thử ACT và Diffusion Policy | Scorer trùng cờ SIMPLE ≥ 95% (mục 5.3); lát dọc chạy trọn trước tuần 4; train, nạp lại, đánh giá chạy trọn |
| 5–6 | G2 · Đường cong | E1 cho ba phương pháp; seed thứ hai của Ψ₀ quanh ngưỡng; chọn D\*; power analysis (mục 7.5) | D\* nằm trong lưới, không chạm trần hoặc sàn (mục 7.1); MDE đã tính và lựa chọn theo luật MDE > 10 điểm % đã ghi vào RunPlan |
| 7–8 | G3 · Nhánh B | Chốt N_B và trần GPU-giờ trong RunPlan; bộ sinh sim theo tuyến đã chọn, đo tỉ lệ sinh đạt; chọn ρ; train A, A₀.₇, B; A/A test cho cổng; báo số lỗi dev theo mức của π₀; ACT: π₀ và B-fail | Rollout sim qua QA; B_add được đo; Level 0 có ≥ 15 lỗi hoặc đã kích hoạt luật đổi task (mục 7.1) |
| 9–10 | G4 · Nhánh C và HD | 1 vòng Failure → Data trên Ψ₀; train C cuối từ base; F-ACT 5–8 vòng trên ACT; thí nghiệm HD; holdout sớm và niêm phong cho nhánh không phụ thuộc C | Sổ chi phí đầy đủ cho C; evidence card cho mọi cụm |
| 11 | G5 · Holdout | Đóng băng; chạy holdout cho C (Ψ₀ và ACT) và nhánh còn lại; mở niêm phong | Mỗi cặp nhánh và seed chạy đúng một lần |
| 12 | G6 · Bàn giao | Báo cáo so sánh, SOP, video demo, khuyến nghị thu dữ liệu định lượng, cập nhật Pitch theo kết quả | Mọi claim trong pitch có số đo đi kèm hoặc được gỡ |

**Khối lượng dự kiến** (giờ máy cụ thể chỉ có sau G0):

| Hạng mục | Ψ₀ | ACT và Diffusion Policy |
|---|---|---|
| Fine-tune ở E1 | 5, cộng 2 cho seed thứ hai quanh ngưỡng | 10 |
| Chọn ρ | 2 | Không |
| Nhánh chính × 3 seed | 12 (A, A₀.₇, B, C) | 12 (A, B cho 2 phương pháp) |
| π₀ của ACT (0,7D\*, 1 seed) | Không | 1 |
| Fine-tune trong các vòng của C | 1 (2 nếu chạy vòng 2) | 5–8 (F-ACT) |
| C và B-fail trên ACT × 3 seed | Không | 6 |
| Tùy chọn | B-fail × 3 seed nếu còn ngân sách sau G4: 3; thêm 2 seed cho B và C nếu MDE > 10: 4; B⁺: 3 | Không |
| Tổng số lần train | Khoảng 22 mặc định, tối đa khoảng 33 | Khoảng 34–37 |
| Episode holdout | 1.800 (thêm 450 cho mỗi nhánh tùy chọn, 600 nếu thêm seed) | 2.700 (gồm C và B-fail của ACT) |
| Rollout mỗi vòng C | Khoảng 630 cộng tới 180 cho mỗi cụm can thiệp: tìm lỗi 90, cổng 540 (90 điều kiện × 3 lượt × 2 policy), đo tỉ lệ sửa được ≤ 30 × 3 × 2 mỗi cụm; chưa tính kiểm 5–7 | Như Ψ₀, nhân với 5–8 vòng |
| A/A test | 270 (một lần ở G3) | 270 |

Ngân sách 140 A100-giờ mỗi đợt trong Pitch v10 phải được kiểm lại theo số đo ở G0.

## 10. Rủi ro và phương án dự phòng

| Rủi ro | Dấu hiệu | Dự phòng |
|---|---|---|
| Ψ₀ không vừa VRAM hoặc quá chậm | G0: hết bộ nhớ hoặc một lần fine-tune quá ngân sách | LoRA hoặc đóng băng VLM; thuê A100 80 GB; giảm còn 2 seed và ghi rõ; khi đó HT tự động thành kết quả mô tả (mục 7.5) |
| Teleop và MP khác bộ điều khiển | V3 âm (hạn ngày 5 của Sprint 1): teleop chạy decoupled WBC, MP chạy AMO, không ánh xạ trực tiếp | Bốn tuyến T1–T4 ở bảng dưới; thử T1 và T2 song song tuần 1–2, chốt cuối tuần 2; T4 là phương án cuối |
| Không có planner cho task chính | Q2 là "không" | Biến đổi đoạn teleop theo vị trí vật kiểu MimicGen / IntervenGen (tuyến T2). F1 chỉ dùng khi V3 xác nhận cặp của F1 cùng bộ điều khiển |
| V3 âm và Q6 âm | Không tuyến T1–T3 nào cho dữ liệu sinh trong env WBC; không có thiết bị teleop | C chỉ còn kiểm demo mâu thuẫn, mà kiểm này chỉ ra báo cáo, nên C không có can thiệp dữ liệu và HT sụp. Ghi kịch bản này vào báo cáo; còn lại HD và HS nếu B có dữ liệu qua T4 |
| Chạm trần | Mọi mức dữ liệu đều ≥ 90%; hoặc Level 0 có dưới 15 lỗi dev sau G3 | Chỉ tiêu chính chuyển sang Level 2; hoặc đổi task khó hơn (mục 7.1) |
| Thiếu lực thống kê | MDE > 10 điểm % ở G2 | Luật ở mục 7.5: thêm seed cho B và C, đổi mức của chỉ tiêu chính, hoặc hạ HT thành mô tả |
| Không reset được simulator | Q3 là "không" | Bỏ bước 6; khoanh vùng bằng chạy lại cùng hạt giống và để planner tiếp quản ở bước k |
| Không có thiết bị teleop | Q6 là "không" | Correction do planner trong env WBC sinh; báo cáo r_demo chỉ trên demo gốc |
| C không hơn B | Cận dưới CI của (C − B) ≤ 0 | Báo cáo trung thực; thu hẹp claim của pitch về Data Core, sổ chi phí và khuyến nghị thu dữ liệu |
| Kết quả sim không chuyển sang robot thật | Ngoài phạm vi PoC | Cổng nghiệm thu robot thật riêng; real2sim cho cell trước khi lên robot |

**Các tuyến khi V3 âm** (công sức là ước lượng, Simulation xác nhận ở tuần 1). Tuyến được chọn cần story xây riêng 1–4 tuần.

| Tuyến | Cách làm | Công sức | Rủi ro | Hệ quả cho claim |
|---|---|---|---|---|
| T1 · Tái thực thi quỹ đạo MP | Lấy quỹ đạo thân trên của rollout MP, suy lệnh thân dưới, chạy lại trong env WBC, giữ lượt thành công | 1–2 tuần | Tỉ lệ sinh đạt có thể rất thấp | Giữ thiết kế; báo tỉ lệ sinh đạt |
| T2 · Biến thể kiểu MimicGen / IntervenGen | Biến đổi đoạn teleop theo tư thế vật, chạy bằng IK cộng WBC trong env Teleop | 2–3 tuần | Cúi người làm phép biến đổi khó hơn tay cố định | "Sim" thành "biến thể của teleop" (mục 4.1 cho phép) |
| T3 · Planner trong env WBC | Planner cho thân trên cộng lệnh cúi cho WBC | 2–4 tuần | Tốn nhất; mảng Simulation chưa có minh chứng | Giữ nguyên thiết kế |
| T4 · Chuyển sang env MP | Lấy task MP làm task chính, coi demo MP là demo gốc | Vài ngày | HS thành "sim thay sim", mất ý nghĩa teleop | Thu hẹp claim rõ ràng; phương án cuối |

Khuyến nghị: thử T1 và T2 song song trong tuần 1–2, chốt tuyến cuối tuần 2. T1 và T3 cho planner dùng được ở bước 5 và bước 6 trong env WBC (mục 6.5). Với T2, hai bước này dùng phương án thay thế đã nêu ở mục 6.5 và mục 6.6. Với T4, planner MP chạy cùng env với policy nên dùng trực tiếp được.

## 11. Quan hệ với tài liệu cũ

Hồ sơ cũ không còn trong thư mục làm việc. Xem lại một file bằng `git show archive/v3:<đường dẫn>`, ví dụ `git show archive/v3:docs/03-data-core.md`.

| Tên trong hồ sơ cũ (tag `archive/v3`) | Tên trong spec này |
|---|---|
| R (robot anchor), robot roots | Demo teleop, demo gốc |
| S, S_exec | Rollout sim do planner sinh |
| H (human egocentric) | Prior video người, kế thừa qua Ψ₀ |
| Arm T (targeted expert teleop) | Teleop correction, một loại can thiệp trong nhánh C |
| Arm F (fixed mixture) | Nhánh B |
| Arm A (condition-cost acquisition) | Nhánh C |
| RUN; DIAG; ACQUIRE; RELEASE, TRAIN và EVAL | Lần lượt bước 1–2; bước 3–9; bước 10–11; bước 12 của mục 6.1 |
| EvidenceCard | Evidence card (mục 4.5) |
| Root, ancestor, descendant | Demo gốc, episode cha, biến thể (mục 4.1) |
| E0 | Cổng G0 |
| core15, grid27 | Không còn dùng |
| Giả thuyết H1, H2, H3 (spec v10 trước bản v10.1) | HS, HT (tách HTa, HTb), HD (mục 3) |

## 12. Glossary

| Thuật ngữ | Tiếng Anh | Nghĩa trong spec |
|---|---|---|
| A/A test | A/A test | Chạy cùng một policy hai lần độc lập như thể là cha và ứng viên; tỉ lệ hồi quy đo được là sàn hồi quy giả do nhiễu (mục 6.12) |
| Action chunk | Action chunk | Chuỗi hành động cho vài bước tới mà policy dự đoán trong một lần chạy |
| AMO | AMO | Bộ điều khiển thân dưới học bằng RL. Trang Ψ₀ gọi là System-0; trong SIMPLE là bộ điều khiển của pipeline MP (`*MP-v0`), không phải của task chính |
| B_add | Added acquisition budget | Chi phí thực đo để tạo đúng N_B rollout sim đạt QA của nhánh B; là trần ngân sách thu dữ liệu cho nhánh C và B-fail |
| B-fail | Failure-targeted baseline | Nhánh sinh sim quanh mọi điều kiện lỗi dev, không chẩn đoán, cùng ngân sách với C (kiểu Mulligan rút gọn); dùng cho HTa và HTb |
| Biến thể | Variant | Episode tạo ra bằng cách sửa một episode khác; không phải demo gốc |
| Bootstrap phân cấp | Hierarchical bootstrap | Lấy mẫu lại seed huấn luyện, rồi lấy mẫu lại điều kiện trong từng mức, để CI gồm cả phương sai giữa seed (mục 7.5) |
| Bước | Stage | Một giai đoạn của task (tiếp cận, gắp, nâng, di chuyển, đặt, nhả) |
| Chẩn đoán | Diagnosis | Một trong 11 lớp ở mục 6.9 |
| Checkpoint | Checkpoint | Bộ trọng số đã lưu của model |
| Cổng | Gate | Điều kiện phải đạt trước khi sang giai đoạn sau |
| Cụm lỗi | Failure cluster | Nhóm các lỗi cùng bước hỏng, cùng kiểu lỗi và cùng mức |
| D\* | D-star | Số demo teleop nhỏ nhất để Ψ₀ đạt ≥ 75% trên dev gộp ba mức, chọn bằng 2 seed quanh ngưỡng (mục 7.1) |
| Decoupled WBC | Decoupled whole-body controller | Stack điều khiển toàn thân tách lệnh thân trên và thân dưới; bộ điều khiển của task chính trong SIMPLE (`g1_sonic`, `SonicLocoManipEnv`) |
| Demo gốc | Root demonstration | Demo do người thu (teleop hoặc correction); là đơn vị đếm khi nói "giảm X% demo" |
| DENSO Data Model | DENSO Data Model | Data Core cộng SOP thu và kiểm dữ liệu, gọi theo tên đề |
| Dev | Development set | Điều kiện dùng để tìm lỗi và chỉnh, gồm tập tìm lỗi 90 điều kiện cố định và tập cổng mới mỗi vòng; không dùng để kết luận |
| Đường cong hiệu quả dữ liệu | Data-efficiency curve | Tỉ lệ thành công theo số demo dùng để train |
| Episode | Episode | Một lần chạy task từ đầu đến khi xong hoặc hết giờ |
| Evidence card | Evidence card | Thẻ ghi kết quả các phép kiểm, chẩn đoán, đề xuất và quyết định cho một cụm lỗi |
| F-ACT | F-ACT experiment | Thí nghiệm chạy 5–8 vòng Failure → Data với ACT để có bằng chứng "flywheel học" (mục 7.8) |
| Failure → Data | Failure-to-data | Thuật toán ở mục 6: từ lỗi đến quyết định bổ sung dữ liệu |
| Fine-tune | Fine-tuning | Tiếp tục train một model đã pretrain trên dữ liệu của task |
| Flow matching | Flow matching | Cách train action expert của Ψ₀: học biến nhiễu thành hành động |
| Flywheel | Data flywheel | Vòng lặp chạy → lỗi → dữ liệu → train → chạy, trong đó mỗi vòng làm vòng sau tốt hơn hoặc rẻ hơn |
| Hạt giống điều kiện | Condition seed | Số khởi tạo của bộ sinh môi trường, quyết định vector điều kiện của một episode |
| Seed huấn luyện | Training seed | Số khởi tạo ngẫu nhiên của một lần train; khác với hạt giống điều kiện |
| HD | Debug hypothesis | Giả thuyết evidence card giảm thời gian chẩn đoán so với công cụ chuẩn (mục 3, 7.6); trước đây là H3 |
| Holdout | Holdout set | Điều kiện chỉ dùng một lần để kết luận, sau khi đóng băng mọi thứ |
| Hồi quy | Regression | Policy mới làm hỏng điều kiện mà policy cũ đã làm được |
| HS | Sim hypothesis | Giả thuyết sim thay được 30% demo teleop: B so với A và A₀.₇ (mục 3); trước đây là H1 |
| HT | Targeting hypothesis | Giả thuyết nhắm theo lỗi tốt hơn bổ sung đều: C so với B trên Ψ₀; là kiểm lại kết quả kiểu Mulligan / DISEIL (mục 3); trước đây là H2 |
| HTa | Targeting hypothesis, part a | Nhắm theo lỗi, không chẩn đoán, có tốt hơn bổ sung đều không: B-fail so với B |
| HTb | Targeting hypothesis, part b | Chẩn đoán có giúp thêm ngoài việc chỉ nhắm theo lỗi không: C so với B-fail |
| Khoanh vùng | Localization | Phép kiểm ở mục 6.6, xác định lỗi do bước k hay do bước trước |
| Không kém hơn | Non-inferiority | Kiểm rằng nhánh mới không kém nhánh cũ quá một biên đã chốt trước (10 điểm %) |
| Level 0, 1, 2 | Evaluation levels | Ba mức thay đổi môi trường của SIMPLE (mục 2.2) |
| Lineage | Lineage | Thông tin nguồn gốc: từ đâu, giấy phép, episode cha, phiên bản bộ sinh |
| Lớp lỗi chung | Generic failure class | Nhóm kiểu lỗi dùng chung giữa task (tiếp cận, gắp, mang, đặt, thăng bằng), để L1 gộp thống kê giữa task (mục 5.2) |
| MDE | Minimum detectable effect | Hiệu ứng nhỏ nhất phát hiện được với 80% lực; tính ở G2 cho C − B (mục 7.5) |
| MP | Motion planning | Sinh quỹ đạo bằng thuật toán lập kế hoạch chuyển động thay vì người điều khiển |
| n_eff | Effective failure count | Số lỗi thực được xử lý của một cụm sau khi áp giới hạn L_t: n_eff_j = min(m_j, L_t) (mục 6.10, 6.11) |
| N_B | Branch B sim volume | Số rollout sim đạt QA của nhánh B, bằng 2 × (D\* − 0,7D\*) làm tròn lên, chốt trước G3 |
| NGOÀI MIỀN | Out of training domain | Chẩn đoán cho lỗi có điều kiện vật lý nằm ngoài miền train; không tiêu ngân sách, được báo cáo (mục 6.8) |
| Niêm phong | Sealed result | Kết quả holdout đã chạy, lưu có hash và không ai xem cho tới khi mọi nhánh xong |
| Ghép cặp | Paired design | Mọi nhánh chạy trên cùng các điều kiện để so sánh trực tiếp |
| Policy | Policy | Model nhận quan sát và câu lệnh, xuất hành động |
| QA | Quality assurance | Các phép kiểm dữ liệu ở mục 4.4 |
| r_demo | Demo reduction | Tỉ lệ demo gốc giảm được so với D\* |
| r_debug | Debug reduction | Tỉ lệ giờ chẩn đoán giảm được, đo ở HD, báo dạng khoảng |
| Release | Dataset release | Phiên bản dữ liệu cố định, có QA và lineage, dùng để train |
| Rollout | Rollout | Một lần chạy policy hoặc planner trong simulator |
| Scorer từng bước | Stage scorer | Bộ chấm độc lập cho từng bước, dùng trạng thái đo được của simulator |
| SIMPLE | SIMPLE | Simulator và bộ đánh giá humanoid loco-manipulation của USC PSI Lab |
| Sổ chi phí | Cost ledger | Bản ghi mọi hoạt động và nguồn lực đã tiêu |
| Tăng cường thị giác | Visual augmentation | Biến đổi ảnh khi train (độ sáng, màu) để policy bền hơn với thay đổi hình ảnh; phần cố định của recipe cho mọi nhánh |
| τ_sync | Sync threshold | Ngưỡng lệch thời gian giữa khung ảnh và state; vượt ngưỡng thì chẩn đoán LỖI ĐỒNG BỘ (mục 6.4) |
| Teleop | Teleoperation | Người điều khiển robot từ xa để thu demo |
| Teleop correction | Correction | Người điều khiển tiếp quản từ một trạng thái lỗi của policy để hoàn thành task |
| Dữ liệu phục hồi | Recovery data | Correction bắt đầu từ trạng thái xấu do bước trước để lại |
| Tỉ lệ sửa được | Fix rate | Xác suất một loại can thiệp sửa được lỗi, đo có đối chứng với policy cha trên điều kiện mới quanh lỗi, cập nhật sau mỗi vòng (mục 6.13) |
| Trạng thái chuẩn | Expert state | Trạng thái simulator ở đầu một bước khi task được làm đúng bởi planner hoặc demo |
| Vector điều kiện | Condition vector | Các tham số mô tả một tình huống: vị trí vật, đích, ánh sáng, vật liệu, vật gây nhiễu |
| VLM | Vision-language model | Model hiểu ảnh và câu lệnh; là System-2 của Ψ₀ |
| Vùng phủ | Coverage | Phần không gian điều kiện đã có dữ liệu train gần đó |
| Ψ₀ | Psi-Zero | Foundation model cho humanoid của USC PSI Lab, gồm System-2, System-1 và System-0 |

## 13. Nguồn

- Ψ₀: [trang dự án](https://psi-lab.ai/Psi0/), [mã nguồn](https://github.com/physical-superintelligence-lab/Psi0), arXiv 2603.12263. Kiểm ngày 22/10/2026.
- SIMPLE: [repo](https://github.com/physical-superintelligence-lab/SIMPLE), [tài liệu](https://psi-lab.ai/SIMPLE/docs), arXiv 2606.08278. Kiểm ngày 22/10/2026.
- Dữ liệu: [psi-data/simple](https://huggingface.co/datasets/USC-PSI-Lab/psi-data/tree/main/simple), 18 gói, kiểm ngày 22/10/2026.
- MimicGen: [arXiv 2310.17596](https://arxiv.org/abs/2310.17596).
- DAgger: [arXiv 1011.0686](https://arxiv.org/abs/1011.0686). HG-DAgger: [arXiv 1810.02890](https://arxiv.org/abs/1810.02890).
- DataMIL: [arXiv 2505.09603](https://arxiv.org/html/2505.09603v1).
- Mulligan: [arXiv 2610.05882](https://arxiv.org/abs/2610.05882). DISEIL: [arXiv 2609.08123](https://arxiv.org/abs/2609.08123). Kiểm ngày 22/10/2026.
- IntervenGen, Hoque và cộng sự, 2024: [arXiv 2405.01472](https://arxiv.org/abs/2405.01472). CUPID, Agia và cộng sự, 2025: [arXiv 2506.19121](https://arxiv.org/abs/2506.19121). Theo [05 mục 8](product/05-review-and-mentor-questions.md), kiểm ngày 22/10/2026.
- Bộ điều khiển của task trong SIMPLE: [G1 Decoupled](https://psi-lab.ai/SIMPLE/docs/tasks/g1_decoupled.html), [G1 MP (AMO)](https://psi-lab.ai/SIMPLE/docs/tasks/g1_mp_amo.html), theo [03 mục 3.2](product/03-architecture.md).
- Checkpoint Ψ₀ trên Hugging Face, thư mục `psi0/`: [USC-PSI-Lab/psi-model](https://huggingface.co/USC-PSI-Lab/psi-model/tree/main/psi0). Không có thẻ model, không ghi giấy phép; vai trò từng thư mục cần tác giả xác nhận (Q0).
- Công cụ chuẩn cho HD: [Rerun](https://github.com/rerun-io/rerun).
- Đơn giá: [Runpod pricing](https://www.runpod.io/pricing), [Runpod storage](https://docs.runpod.io/pods/pricing), theo slide 13 của Pitch v10.

## 14. Change log

| Ngày | Phiên bản | Nội dung | Người sửa |
|---|---|---|---|
| 22/10/2026 | v10.1 | #1 Bộ điều khiển: System-0 của task chính là decoupled WBC `g1_sonic`, AMO là của pipeline MP (mục 1.1, 2.1); F1 không còn là dự phòng cho Q2 (mục 2.3, 2.4, 10); thêm V3 hạn ngày 5 Sprint 1 (mục 2.4, 9); kiểm hệ thống nhắm stack WBC, lệnh gửi và trạng thái đo theo giao diện WBC (mục 4.5, 6.4); planner của bước 5–6 phải chạy trong env WBC (mục 6.5); tuyến T1–T4 và kịch bản V3 âm cộng Q6 âm (mục 10) | Biên tập theo 06 |
| 22/10/2026 | v10.1 | #2 Thống kê: bootstrap phân cấp, mô hình hỗn hợp làm kiểm tra chéo, quy tắc 2/3 seed thành chỉ số phụ, power analysis ở G2 và luật MDE > 10 điểm % (mục 7.5); 2 seed quanh ngưỡng khi chọn D\* (mục 7.1); G0 dùng 30 lượt mỗi mức và kiểm nhị thức một phía, G2 có power analysis (mục 9) | Biên tập theo 06 |
| 22/10/2026 | v10.1 | #3 Chọn can thiệp và tỉ lệ sửa được: `p.gain` dùng n_eff (mục 6.1); n_eff, ưu tiên bước sớm khi hòa, vòng 1 chỉ là xếp theo đơn giá, có unit test (mục 6.10, 6.11); tập cổng mới mỗi vòng, ≥ 3 lượt, A/A test, ngưỡng hồi quy max(5%, sàn A/A), "tăng ≥ 1 SE" (mục 6.12, 6.15); tỉ lệ sửa được đo có đối chứng trên điều kiện mới quanh lỗi (mục 6.13); thêm thí nghiệm F-ACT (mục 7.8) | Biên tập theo 06 |
| 22/10/2026 | v10.1 | #4 Công bằng giữa các nhánh: thêm chẩn đoán NGOÀI MIỀN (mục 6.8, 6.9); bỏ tăng cường thị giác khỏi can thiệp của C, kiểm demo mâu thuẫn chỉ ra báo cáo (mục 6.7, 6.9, 6.10); N_B chốt trước G3, thêm nhánh B-fail, B⁺ ưu tiên thấp hơn (mục 7.2, 7.4); B_add là chi phí thực đo của N_B, tăng cường thị giác cố định cho mọi nhánh, cùng danh sách 0,7D\*, báo số demo người theo nhánh (mục 7.3); luật dưới 15 lỗi Level 0 thì đổi task (mục 7.1, 10) | Biên tập theo 06 |
| 22/10/2026 | v10.1 | #5 Lỗi cấy và HD: thêm phép kiểm đồng bộ cảm biến và camera chuẩn, chẩn đoán LỖI ĐỒNG BỘ và LỖI CALIBRATION (mục 6.1, 6.4, 6.9), τ_sync và camera tham chiếu (mục 6.15); HD có ≥ 2 người ngoài đội, đối thủ Rerun cộng đồ thị mặc định, 3–4 card sai cố ý, recall theo lớp, đối chứng sạch, r_debug dạng khoảng (mục 7.6) | Biên tập theo 06 |
| 22/10/2026 | v10.1 | #6 Định vị: câu định vị thống nhất ở mục 0 và 1.2; HT là kiểm lại kết quả kiểu Mulligan / DISEIL; thêm tiền lệ IntervenGen và CUPID, Mulligan dùng dữ liệu lỗi để học value function, dùng dữ liệu lỗi để train là hướng L1; "DENSO Data Model" (mục 0, 1.1, 1.2, 13) | Biên tập theo 06 |
| 22/10/2026 | v10.1 | #7 Tên giả thuyết H1, H2, H3 đổi thành HS, HT (HTa, HTb), HD trong toàn spec; giữ mã đề "H1"; thêm bảng map tiêu chí 3 cấp của BTC, D\* dùng ngưỡng ≥ 75%, Level 1–2 báo riêng so với 70% (mục 0, 3, 7.1, 7.5, 11, 12) | Biên tập theo 06 |
| 22/10/2026 | v10.1 | #8 Nguồn gốc checkpoint và chống rò: thêm Q0 (mục 2.4); guard gần trùng theo khoảng cách điều kiện, dải hạt giống rời với dải tác giả (mục 4.3); checkpoint gốc `pre.*` hoặc `postpre.*`, `simple-checkpoints` và `sonic-checkpoints` chỉ để tái tạo ở G0 (mục 7.3, 9) | Biên tập theo 06 |
| 22/10/2026 | v10.1 | #9 Năng lực: lập kế hoạch ở 70% năng lực, lát dọc trên SIMPLE trước tuần 4, mặc định 1 vòng C cho Ψ₀ và vòng thêm chạy ACT, holdout sớm niêm phong, bảng khối lượng có B-fail và F-ACT (mục 6.1, 6.11, 6.13, 7.3, 7.5, 9); chỉ số chính ở holdout lấy từ cờ thành công của SIMPLE (mục 5.3, 7.5); thêm "lớp lỗi chung" (mục 5.2) | Biên tập theo 06 |
| 22/10/2026 | v10.1 | #10 Kinh tế: chi phí giờ cell (mục 8.1); điểm yếu của công thức và r_debug dạng khoảng (mục 8.2); chỉ số chính mới gồm chi phí mỗi điểm % của C so với B và B-fail, HT báo theo phút người và GPU-giờ (mục 8.3); bảng độ nhạy theo đơn giá và chi phí giờ cell (mục 8.4) | Biên tập theo 06 |
| 22/10/2026 | v10.1 | Sửa nhỏ: tiêu đề đổi "PoC ba nhánh" thành "PoC đối chứng" vì PoC nay có các nhánh A, A₀.₇, B, B-fail, C (mục 7.2); sửa câu tương ứng ở mục 1.1 | Trưởng nhóm |
