# 01 · Project Brief: Humanoid Data Flywheel

_Ngày 22/10/2026. Vai trò: Analyst (BMAD). Đầu vào: [00 · Phân tích idea](00-idea-analysis.md), [spec v10](../spec-v10-failure-to-data.md), [đề H1](../challenge/README.md), [README](../../README.md). Brief không đổi phạm vi của các đầu vào này. Chỗ nào là đề xuất riêng của Analyst thì ghi rõ "đề xuất". Thuật ngữ theo glossary ở mục 12 của spec v10. Bản 0.3 áp quyết định phản biện vòng 1 ở [06](06-review-round-1-decisions.md)._

Quy ước nhãn bằng chứng dùng trong toàn file:

- **Đã kiểm:** đội đã tự kiểm.
- **Công bố:** số hoặc kết quả do tác giả hay công ty khác công bố; đội chưa tái tạo.
- **Giả định:** con số dùng để lập kế hoạch, chưa đo. Mọi số về DENSO đều thuộc loại này.
- **Giả thuyết:** điều PoC sẽ kiểm. Tên theo 06 để không trùng mã đề: **HS** (sim thay được 30% demo teleop), **HTa** (nhắm theo lỗi tốt hơn bổ sung đều), **HTb** (chẩn đoán giúp thêm ngoài việc chỉ nhắm theo lỗi), **HD** (evidence card giảm thời gian chẩn đoán). HT là tên chung của HTa và HTb.

## 1. Tóm tắt điều hành

Khi một humanoid làm hỏng task, đội robot hiện thường đoán nguyên nhân bằng cách xem video và log, rồi thu thêm teleop vì không có cách chắc hơn. Cách này tốn giờ operator và giờ kỹ sư, và không cho biết lần sửa đó đáng bao nhiêu tiền.

**Humanoid Data Flywheel** là nền tảng trả lời ba câu sau mỗi lỗi: nên sửa hệ thống hay bổ sung dữ liệu; nếu bổ sung thì loại nào, bao nhiêu; và lần sửa tốn bao nhiêu so với chất lượng nhận được. Sản phẩm không phải model mới, cũng không phải bộ dữ liệu. Model, simulator và robot là phần cắm. Recipe đầu tiên là **Ψ₀ + SIMPLE / G1** trong mô phỏng.

Lõi là vòng flywheel 8 bước: chạy, chấm, chẩn đoán, quyết định, thu và QA, train, cổng kiểm, ghi sổ chi phí. Mỗi vòng để lại tài sản dùng lại được. Thống kê **tỉ lệ sửa được** của từng loại can thiệp với từng loại lỗi, kèm chi phí thật, là tài sản cần đo ở L1; ở L0 mới có tín hiệu sớm (mục 3.4).

Các quyết định chính của brief:

1. **Định vị:** _Humanoid Data Flywheel là quy trình vận hành có kiểm toán cho vòng lỗi → dữ liệu: loại lỗi hệ thống trước khi tiêu tiền vào dữ liệu, chọn giữa nhiều loại can thiệp theo chi phí thật kể cả chi phí chẩn đoán, và xuất **khuyến nghị thu dữ liệu định lượng** cho DENSO. PoC kiểm lại trên G1 toàn thân với Ψ₀ xem "nhắm lỗi thắng rải đều" có còn đúng khi tính đủ chi phí._ Không claim thuật toán học máy mới; đóng góp là cách ghép và phép đo.
2. **Phạm vi 12 tuần là L0:** 1 task, 1 robot, mô phỏng. Nhưng mô hình dữ liệu và giao diện adapter phải đúng cho L1–L3 để không viết lại.
3. **Thành công của MVP** là vòng Failure → Data chạy trọn, có sổ chi phí, và HS, HT, HD được kết luận trung thực. HT trượt vẫn là kết quả hợp lệ; khi đó claim thu hẹp về DENSO Data Model và sổ chi phí.
4. **Khoảng trống cạnh tranh:** đã có công cụ tốt cho từng khâu riêng lẻ (xem log, sinh dữ liệu, thu dữ liệu, chọn dữ liệu trong nghiên cứu). Trong phạm vi đã tra ngày 22/10/2026, chưa thấy quy trình kiểm hệ thống trước rồi chọn giữa nhiều loại can thiệp bằng một thước đo tiền và giờ công gồm cả chi phí chẩn đoán, rồi đo lại có đối chứng. Ý "chọn dữ liệu theo lỗi" tự nó không mới: HT là kiểm lại kết quả kiểu Mulligan / DISEIL (mục 8).

Ba đầu ra khớp đề BTC: **DENSO Data Model** (Data Core cộng SOP thu và kiểm dữ liệu, gọi đúng như tên đề), báo cáo so sánh phương pháp huấn luyện (ACT, Diffusion Policy, Ψ₀) kèm kết quả HS, HT, HD, và video demo kỹ năng trên tập holdout.

Tiêu chí 3 cấp của BTC map vào PoC như sau (ngưỡng và cổng ở mục 5.3):

| Cấp BTC | Tiêu chí | PoC trả lời bằng |
|---|---|---|
| 1 · Basic | ≥ 50% với lượng demo nhỏ | Tỉ lệ thành công ở các mức 10% và 25% của đường cong E1 |
| 2 · Efficient | Giảm ≥ 30% demo cùng hiệu năng; ≥ 75% | HS: B ở 0,7D\* không kém A và đạt ≥ 75% |
| 3 · Advanced | ≥ 70% trên biến thể chưa train; khuyến nghị thu dữ liệu định lượng | Level 1 và Level 2 của holdout báo riêng so với 70%; đầu ra của bước Decide cộng sổ chi phí là khuyến nghị định lượng |

## 2. Vấn đề

### 2.1 Hiện trạng

- Policy hỏng thì kỹ sư robot learning xem video, đồ thị và log để đoán nguyên nhân. Không có quy trình cố định để tách lỗi controller, lỗi runtime, lỗi nhận thức và lỗi do thiếu dữ liệu.
- Lựa chọn mặc định là "thu thêm teleop". Operator thường thu lại những tình huống policy đã làm được.
- Kỹ sư simulation sinh dữ liệu rải đều vì không biết vùng điều kiện nào đang yếu. Tốn GPU mà không trúng chỗ yếu.
- Kỹ sư data gặp dữ liệu lệch đơn vị, khung tọa độ, thời gian; biến thể bị đếm như demo gốc; dữ liệu test lộ vào train.
- Chủ công đoạn không có con số: cần bao nhiêu công để robot đạt chuẩn lại khi đổi linh kiện, khay hoặc ánh sáng.

### 2.2 Vì sao giải pháp hiện có chưa đủ

- **Công cụ xem và quản lý log** (Rerun, Foxglove) giúp tìm và xem sự kiện, nhưng kỹ sư vẫn tự chẩn đoán và tự quyết định thu gì.
- **Công cụ sinh dữ liệu** (Isaac Lab Mimic, GR00T-Mimic, Cosmos) sinh rất nhiều dữ liệu, nhưng không nói nên sinh ở đâu, bao nhiêu, và có đáng không.
- **Hạ tầng mở** (LeRobot) chuẩn hóa định dạng, train và đánh giá, nhưng không có chẩn đoán lỗi hay sổ chi phí.
- **Dịch vụ dữ liệu physical AI** (Scale AI, Encord) thu và gán nhãn theo đơn hàng hoặc tuyển chọn edge case. Trong phạm vi đã tra, chưa thấy công bố về chọn loại can thiệp theo chi phí rồi đo lại.
- **Nghiên cứu** (DataMIL, Mulligan, DISEIL, IntervenGen, CUPID) chứng minh chọn hoặc sinh dữ liệu có chủ đích tốt hơn rải đều trong một số bối cảnh. Mulligan còn học value function từ cả dữ liệu lỗi; DISEIL kiểm khả thi trước khi tốn công expert. Phần lớn là thuật toán cho một loại can thiệp. Trong phạm vi đã tra ngày 22/10/2026, chưa thấy quy trình vận hành kiểm hệ thống trước, chọn giữa nhiều loại can thiệp theo chi phí gồm cả chi phí chẩn đoán, có cổng kiểm và sổ chi phí.

Chi tiết và nguồn ở mục 8.

### 2.3 Mức độ cấp thiết

- Đề H1 của BTC hỏi đúng điểm này: huấn luyện nhanh, chính xác, ít công; cần quy trình thu dữ liệu chuẩn trong 3 tháng.
- Foundation model cho humanoid như Ψ₀ cho phép thích nghi với task mới bằng fine-tune trên ít dữ liệu teleop (công bố). Khi lượng dữ liệu cần ít đi, câu hỏi chuyển từ "thu thật nhiều" sang "thu đúng chỗ".
- Thị trường đang đầu tư vào hạ tầng dữ liệu physical AI: Foxglove ra tính năng tìm và tuyển chọn dữ liệu (4/2026), Encord gọi vốn (2/2026), Scale AI mở mảng Physical AI. Đây là bằng chứng thị trường quan tâm, không phải bằng chứng DENSO cần.

### 2.4 Bằng chứng công khai và giả định chưa đo

| Nhận định | Nhãn | Nguồn hoặc ghi chú |
|---|---|---|
| Thu demo teleop tốn thời gian operator và cần người theo dõi liên tục | Công bố | Genie Centurion (arXiv 2505.18793); trang Physical AI của Scale AI |
| Lỗi của policy thường tập trung ở một số ít trạng thái đầu; thu rải đều lãng phí giờ operator | Công bố, bối cảnh khác | Mulligan (arXiv 2610.05882), robot tay, chưa đo trên G1 |
| Ψ₀ đạt 10/10 ở cả ba mức cho `BendPickMP` | Công bố | Trang Ψ₀; đội chưa tái tạo |
| Gói task chính có trên psi-data, 108 MB | Đã kiểm | Spec v10 mục 2.3 |
| Sim thay được 30% demo teleop | Giả thuyết HS | Spec v10 mục 3 |
| Nhắm theo lỗi tốt hơn bổ sung đều | Giả thuyết HTa | Kiểm lại (replication) kết quả kiểu Mulligan / DISEIL trên G1 toàn thân, tính đủ chi phí chẩn đoán |
| Chẩn đoán giúp thêm ngoài việc chỉ nhắm theo lỗi | Giả thuyết HTb | Câu hỏi Mulligan và DISEIL chưa tách; đo bằng C so với B-fail |
| Evidence card giảm 50% giờ chẩn đoán | Giả định; đo bằng HD | Chiếm phần lớn lợi ích kinh tế; r_debug báo dạng khoảng |
| Debug baseline 20 giờ kỹ sư mỗi đợt cải thiện | Giả định | Pitch v10 |
| Đơn giá operator $10/h, kỹ sư $20/h | Giả định | Pitch v10; chưa tính chi phí giờ cell (robot, người giám sát, thời gian dừng); chờ số của DENSO |
| 144 đợt cải thiện mỗi năm tại DENSO | Giả định | Chưa có cơ sở; cần DENSO xác nhận |
| DENSO có công đoạn gắp và đặt phù hợp humanoid | Giả định | Chưa có task owner xác nhận |

Brief không claim thuật toán học máy mới; đóng góp là cách ghép và phép đo (spec v10 mục 1.2).

## 3. Giải pháp đề xuất

### 3.1 Vòng flywheel

| Bước | Làm gì | Tài sản để lại |
|---|---|---|
| 1 · Run | Chạy policy trên bộ điều kiện dev đã khai | Trace từng episode |
| 2 · Score | Scorer từng bước chấm từng bước của task | Bước hỏng đầu tiên, kiểu lỗi |
| 3 · Diagnose | Chuỗi phép kiểm: hệ thống → khả thi → khoanh vùng → thị giác → vùng phủ | Evidence card, chẩn đoán cho mỗi cụm lỗi |
| 4 · Decide | Chọn can thiệp theo lợi ích kỳ vọng trên chi phí, trong ngân sách; kỹ sư duyệt hoặc ghi đè có lý do | Kế hoạch thu dữ liệu |
| 5 · Acquire và QA | Sinh rollout sim, thu teleop correction, dữ liệu phục hồi, tăng cường thị giác; QA | Release mới có lineage |
| 6 · Train | Fine-tune từ checkpoint cha, trộn lại dữ liệu cũ | Policy ứng viên |
| 7 · Gate | Cổng dev trên tập điều kiện mới mỗi vòng: tăng thành công ≥ 1 sai số chuẩn, cụm được can thiệp cải thiện, hồi quy không vượt max(5 điểm %, sàn A/A) | Quyết định dùng hay từ chối |
| 8 · Ledger | Ghi chi phí thật mọi bước; cập nhật tỉ lệ sửa được, đo có đối chứng với policy cha | Sổ chi phí, thống kê can thiệp |

Thứ tự kiểm cố định: hệ thống trước, dữ liệu sau. Lỗi hệ thống thành phiếu sửa, không tiêu ngân sách dữ liệu. Thuật toán đề xuất; kỹ sư quyết định.

### 3.2 Tài sản tích lũy sau mỗi vòng

| Tài sản | Dùng lại thế nào |
|---|---|
| Thư viện điều kiện và lỗi | Biết điều kiện nào đã thử, policy nào hỏng ở đâu; làm tập dev cho phiên bản sau |
| Thống kê tỉ lệ sửa được theo loại can thiệp và loại lỗi, có chi phí thật | Ước lượng lợi ích trên chi phí chính xác dần; dùng làm prior cho task mới cùng họ. Cần đo ở L1; ở L0 mới có tín hiệu sớm |
| Dữ liệu đã QA, có lineage và giấy phép | Trộn lại cho task mới; truy được nguồn khi có sự cố hoặc khi cần gỡ dữ liệu |
| Scorer và định nghĩa bước theo loại task | Task gắp, đặt, đẩy mới chỉ cần khai vị từ và tham số |
| Sổ chi phí | Biết trước một lần cải thiện tốn bao nhiêu công; so sánh phương án bằng cùng đơn vị |

Lời hứa là: vòng càng quay, phần đoán càng ít, chi phí mỗi điểm % thành công càng giảm. Đây là điều cần đo, không phải mặc định.

### 3.3 Lõi và phần cắm

- **Lõi** (không đổi khi đổi model, robot, simulator): mô hình dữ liệu (episode, release, trace, evidence card, mục sổ chi phí), lineage, chia tập, QA chung, khung scorer, chuỗi phép kiểm, bảng quyết định, chọn theo ngân sách, sổ chi phí, cổng kiểm, báo cáo.
- **Phần cắm** (adapter): model và trainer (Ψ₀, ACT, Diffusion Policy), simulator (SIMPLE), robot (G1 trong sim), bộ sinh dữ liệu (motion planning, kiểu MimicGen), nguồn teleop, định nghĩa task và vị từ của scorer.

### 3.4 Vì sao khó sao chép

Nói thẳng: từng thành phần đều có tiền lệ (DAgger, HG-DAgger, MimicGen, IntervenGen, DataMIL, CUPID, Mulligan, DISEIL). Một đội mạnh có thể viết lại thuật toán. Thứ khó sao chép nằm ở chỗ khác, và phần lớn chỉ hình thành từ L1:

1. **Thống kê tỉ lệ sửa được với chi phí thật** chỉ có khi vòng đã quay nhiều lần trên task và cell của chính DENSO. Đây là tài sản cần đo ở L1, chưa phải lợi thế ở L0: Ψ₀ mặc định chỉ 1 vòng C, và tỉ lệ đo từ 1 lượt dễ thiên lệch hồi quy về trung bình. Điều kiện đo: đối chứng chạy lại policy cha ≥ 3 lượt trên điều kiện mới quanh điểm lỗi (06 mục 3). Tín hiệu sớm: thí nghiệm F-ACT, 5–8 vòng rẻ với ACT trên cùng task.
2. **Thư viện điều kiện, lỗi và scorer theo công đoạn DENSO** gắn với linh kiện, khay, ánh sáng của nhà máy. Dữ liệu này nằm trong DENSO, không công khai.
3. **Kỷ luật quy trình** (chia tập theo hạt giống điều kiện, holdout chạy một lần, sổ chi phí, ghi đè có lý do) được viết thành SOP trong DENSO Data Model và gắn vào cách đội DENSO làm việc. Đổi công cụ thì phải đổi quy trình.
4. **Trung lập với model và simulator:** lõi không phụ thuộc Ψ₀ hay SIMPLE, nên đổi model nền không làm mất tài sản tích lũy.

Ở L0 hào chắn gần như bằng không vì mới có một task và mặc định một vòng C trên Ψ₀. Hào chắn chỉ hình thành từ L1 trở đi, khi thống kê được dùng lại giữa task.

## 4. Người dùng mục tiêu

### 4.1 Người dùng chính: kỹ sư robot learning

Trong PoC là đội 5 người. Sau PoC là đội phát triển robot của DENSO. Việc họ cần làm được:

- Biết vì sao một cụm lỗi xảy ra trong vài phút, có bằng chứng, thay vì xem video hàng giờ.
- Nhận đề xuất can thiệp có số lượng, lợi ích kỳ vọng và chi phí ước tính; duyệt hoặc ghi đè kèm lý do.
- Biết policy ứng viên qua hay trượt cổng, và có hồi quy ở đâu.
- Trình bày cho quản lý con số: đợt cải thiện này tốn bao nhiêu, được bao nhiêu điểm %.

### 4.2 Người dùng phụ

| Người dùng | Việc cần làm được | Nền tảng hỗ trợ bằng |
|---|---|---|
| Kỹ sư simulation | Sinh dữ liệu đúng vùng điều kiện đang yếu | Đề xuất "sinh sim quanh điều kiện lỗi" với số lượng và bán kính vùng phủ |
| Kỹ sư data | Nạp, chuẩn hóa, QA, chia tập không lộ holdout | Data Core: QA bắt buộc, lineage, chia tập theo hạt giống điều kiện, release |
| Operator teleop | Chỉ thu những đoạn có giá trị | Danh sách teleop correction và dữ liệu phục hồi bắt đầu từ trạng thái lỗi đã lưu |
| Chủ công đoạn tại nhà máy | Quyết định đưa robot vào dây chuyền dựa trên số | Báo cáo chi phí mỗi điểm %, số ngày để đạt ngưỡng trở lại |
| Ban giám khảo BTC và DENSO | Đánh giá đóng góp và khả năng mở rộng | Báo cáo so sánh phương pháp, kết quả HS, HT, HD, map tiêu chí 3 cấp, sổ chi phí |

### 4.3 Chưa phục vụ ở L0

Operator dây chuyền thật, bộ phận an toàn, IT nhà máy và nhiều đội dùng chung. Các nhóm này xuất hiện từ L2 và L4.

## 5. Mục tiêu và chỉ số thành công

### 5.1 Mục tiêu kinh doanh

| Mã | Mục tiêu | Đo bằng |
|---|---|---|
| BG1 | Giảm giờ công để policy đạt chuẩn sau một thay đổi điều kiện | Giờ operator và giờ kỹ sư mỗi điểm % thành công tăng thêm, từ sổ chi phí |
| BG2 | Giao đủ ba đầu ra BTC trong 12 tuần | SOP, báo cáo so sánh, video demo ở cổng G6 |
| BG3 | Thay giả định kinh tế của Pitch v10 bằng số đo | r_demo, r_debug dạng khoảng, GPU-giờ thực; bảng độ nhạy theo đơn giá DENSO và chi phí giờ cell thay cho một con số lợi ích ròng |
| BG4 | Cho DENSO cơ sở quyết định đi tiếp L1 hoặc L2 | Báo cáo nêu rõ claim nào được giữ, claim nào bị gỡ |
| BG5 | Lõi dùng lại được khi thêm task, robot, simulator | Adapter thứ hai (ACT, Diffusion Policy) cắm vào không phải sửa lõi |

### 5.2 Chỉ số người dùng

- Thời gian từ lúc có cụm lỗi đến lúc kỹ sư ra quyết định (HD).
- Tỉ lệ chẩn đoán đúng khi dùng evidence card so với công cụ chuẩn (Rerun cộng đồ thị mặc định) (HD).
- **Tỉ lệ ghi đè của kỹ sư.** Spec v10 mục 6.14 coi việc ghi đè phần lớn đề xuất là dấu hiệu phép kiểm chưa đủ tốt. Đề xuất: lấy 50% làm ngưỡng cảnh báo.
- Tỉ lệ cụm lỗi có evidence card đầy đủ mọi trường.
- Giờ operator cho mỗi điểm % thành công tăng thêm.

### 5.3 KPI đo được trong 12 tuần (L0)

Mọi ngưỡng chốt trước khi chạy holdout. "Cận dưới" là cận dưới khoảng tin cậy 95% bằng bootstrap phân cấp: lấy mẫu lại seed huấn luyện, rồi lấy mẫu lại điều kiện trong từng mức; mô hình logistic hỗn hợp chạy làm kiểm tra chéo (06 mục 2). Chỉ số chính ở holdout lấy từ cờ thành công của SIMPLE. **D\*** là mức demo nhỏ nhất để Ψ₀ đạt **≥ 75%** trên dev gộp (Cấp 2 của BTC), chọn bằng 2 seed ở hai điểm lưới quanh ngưỡng hoặc nội suy đường cong.

**Map tiêu chí 3 cấp của BTC** ([đề bài](../challenge/README.md)):

| Cấp BTC | Tiêu chí | Chỉ tiêu trong PoC | Cổng |
|---|---|---|---|
| 1 · Basic | ≥ 50% với lượng demo nhỏ | Báo tỉ lệ thành công ở các mức 10% và 25% của đường cong E1 | G2 |
| 2 · Efficient | Giảm ≥ 30% demo cùng hiệu năng; ≥ 75% | HS: B ở 0,7D\* không kém A và đạt ≥ 75% | G5 |
| 3 · Advanced | ≥ 70% trên biến thể chưa train; khuyến nghị thu dữ liệu định lượng | Báo riêng Level 1 và Level 2 của holdout so với 70%; đầu ra của bước Decide cộng sổ chi phí là khuyến nghị định lượng | G5–G6 |

**KPI:**

| KPI | Gắn với | Ngưỡng đạt | Cổng |
|---|---|---|---|
| Nhánh B ở 0,7D\* trên holdout gộp ba mức | HS | ≥ 75%; cận dưới của (B − A) > −10 điểm %; cận dưới của (B − A₀.₇) > 0 | G5 |
| Nhánh C so với nhánh B cùng ngân sách thu dữ liệu, trên Ψ₀ | HT | Cận dưới của (C − B) > 0; báo kèm tổng chi phí của C gồm chi phí chẩn đoán; phút người và GPU-giờ báo riêng | G5 |
| Nhánh B-fail so với B cùng ngân sách; ACT là chính, Ψ₀ nếu còn ngân sách sau G4 | HTa | Cận dưới của (B-fail − B) > 0 | G5 |
| Nhánh C so với B-fail cùng ngân sách, cùng model với dòng trên | HTb | Cận dưới của (C − B-fail) > 0; báo kèm chi phí chẩn đoán | G5 |
| Lực thống kê cho HT | HT | Power analysis với 2 seed ở D\*: hiệu ứng nhỏ nhất phát hiện được với 80% lực ≤ 10 điểm %. Nếu không: 5 seed Ψ₀ cho B và C, hoặc đổi chỉ tiêu chính sang mức còn dư địa, hoặc HT thành kết quả mô tả | G2 |
| r_debug | HD | Thời gian giảm và tỉ lệ chẩn đoán đúng không thấp hơn; ≥ 2 người ngoài đội; báo dạng khoảng; là pilot, không phải kiểm định | G4 |
| Số demo người để đạt 75% theo từng phương pháp | So sánh phương pháp, Cấp 2 | Báo cáo mô tả cho ACT, Diffusion Policy, Ψ₀; báo kèm mức 80% | G2 |
| Scorer trùng cờ thành công của SIMPLE | Nền cho HS, HT, HD | ≥ 95% trên 100 episode; 20 episode lỗi gán đúng bước hỏng | G1 |
| Lộ holdout vào train | Kỷ luật dữ liệu | 0 trường hợp; holdout chạy đúng một lần | G5 |
| Release có lineage đầy đủ | Data Core | 100% mẫu trong release; mẫu thiếu lineage bị cách ly | G1 |
| Sổ chi phí của nhánh C | BG1, BG3 | Mọi hoạt động có mục sổ; evidence card cho mọi cụm | G4 |
| Ổn định qua seed (chỉ số phụ) | Độ tin cậy | Chiều của chênh lệch giữ nguyên ở ít nhất 2/3 seed | G5 |

Cách đọc: HS và HT kết luận độc lập. Lượng dữ liệu của B chốt trước G3: N_B = 2 × (D\* − 0,7D\*) rollout sim đạt QA, kèm trần GPU-giờ; B_add là chi phí thực đo để tạo đúng N_B đó, và C, B-fail bị chặn ở B_add. HT trượt là kết quả hợp lệ: kết quả kiểu Mulligan / DISEIL không lặp lại trên G1 khi tính đủ chi phí; pitch khi đó bỏ claim "chọn dữ liệu theo lỗi". Nếu C chỉ hơn B khi chưa tính chi phí chẩn đoán, báo cả hai con số. Nếu Ψ₀ phải cắt về 2 seed, HT tự động thành kết quả mô tả.

**Chỉ số giá trị chính.** Kinh tế trình bày theo giờ người và số ngày, không dẫn bằng đô-la mỗi năm. Mọi chỉ số lấy từ sổ chi phí và báo cáo hiện có.

| Chỉ số | Cách đo | Báo theo |
|---|---|---|
| Số demo người để đạt ngưỡng 75% | Đường cong E1 và các nhánh; tách teleop và correction | Phương pháp, nhánh |
| Phút operator mỗi điểm % tăng thêm | Phút operator trong sổ chi phí chia cho chênh lệch thành công trên holdout | Loại can thiệp, nhánh |
| Chi phí mỗi điểm % tăng thêm của C | Chi phí của C trừ chi phí của nhánh so sánh, chia cho chênh lệch thành công | C so với B; C so với B-fail; phút người và GPU-giờ báo riêng |
| Sai số dự báo chi phí | Chi phí ước tính lúc Decide so với thực đo trong sổ | Can thiệp |
| Số ngày để policy đạt lại ngưỡng | Từ lúc có cụm lỗi tới lúc ứng viên qua cổng dev, theo nhật ký vòng | Vòng |
| r_debug | Thí nghiệm HD | Dạng khoảng, không phải một điểm |

Kèm bảng độ nhạy theo đơn giá DENSO (operator, kỹ sư, GPU) và **chi phí giờ cell** (robot, người giám sát, thời gian dừng dây chuyền). Đơn giá thật chờ DENSO (câu 5 ở mục 10.2).

### 5.4 KPI cho các mức sau

Ngưỡng chốt cùng DENSO khi vào từng mức. Brief không đặt số trước vì chưa có dữ liệu.

| Mức | KPI đề xuất |
|---|---|
| L1 · Nhiều task | Chi phí mỗi điểm % ở task thứ hai trở đi so với task đầu; số ngày để thêm một task mới; tỉ lệ scorer và định nghĩa bước dùng lại được |
| L2 · Robot thật | Chênh lệch thành công giữa sim và cell thật trên cùng bộ điều kiện; giờ operator thật mỗi điểm %; số sự cố an toàn |
| L3 · Nhiều robot | Số ngày để cắm một embodiment mới; tỉ lệ dữ liệu và thống kê can thiệp dùng lại được giữa embodiment |
| L4 · Nhiều nhà máy | Số đội dùng chung; số ngày từ khi đổi điều kiện đến khi policy đạt ngưỡng trở lại; chi phí mỗi đợt theo đơn vị |

## 6. Phạm vi MVP 12 tuần (L0)

### 6.1 Tính năng lõi phải có

Mã TN (tính năng) khác với "task F1" của spec v10 mục 2.3.

| Mã | Tính năng | Nội dung | Cổng |
|---|---|---|---|
| TN1 | Data Core | Nạp psi-data; QA bắt buộc (spec mục 4.4); lineage có giấy phép; chia tập theo hạt giống điều kiện; release cố định. Cùng SOP tạo thành DENSO Data Model | G1 |
| TN2 | Chạy và ghi trace | Chạy policy trên dev và holdout; lưu trace đủ trường (spec mục 4.5) | G0–G1 |
| TN3 | Scorer từng bước | 6 bước của task chính; 9 kiểu lỗi; quy ước "chưa thử" và "chưa rõ" | G1 |
| TN4 | Chẩn đoán Failure → Data | Gom cụm, kiểm hệ thống, khả thi, khoanh vùng, thị giác, vùng phủ; 8 lớp chẩn đoán; evidence card | G4 |
| TN5 | Đề xuất và chọn theo ngân sách | Định lượng can thiệp; lợi ích kỳ vọng trên chi phí; duyệt và ghi đè có lý do | G4 |
| TN6 | Adapter thu dữ liệu | Sinh rollout sim quanh điều kiện lỗi theo tuyến chốt sau V3 (T1–T4); teleop correction (người hoặc máy sinh); dữ liệu phục hồi. Tăng cường thị giác là phần cố định của recipe, áp như nhau cho mọi nhánh | G3–G4 |
| TN7 | Train, cổng dev, cập nhật | Fine-tune từ checkpoint cha có replay; cổng dev; cập nhật tỉ lệ sửa được theo Beta | G4 |
| TN8 | Sổ chi phí | Mỗi hoạt động một mục: loại nguồn lực, số lượng, đơn giá, nhánh, vòng, cụm | G1–G4 |
| TN9 | Thí nghiệm và báo cáo | E1 đường cong hiệu quả dữ liệu; nhánh A, A₀.₇, B, C; nhánh B-fail trên ACT; holdout ghép cặp 3 seed; thí nghiệm HD; F-ACT 5–8 vòng trên ACT; SOP | G2–G6 |
| TN10 | Giao diện adapter | Hợp đồng cho model, simulator, robot, bộ sinh dữ liệu, nguồn teleop; đúng cho L1–L3 dù L0 chỉ có một bản cài | G0–G1 |

Nhánh **B-fail** (06 mục 4): sinh sim quanh mọi điều kiện lỗi dev, không chẩn đoán, cùng ngân sách với C (kiểu Mulligan rút gọn, không cần value function). HTa so B-fail với B; HTb so C với B-fail.

Nên có nếu kịp: B-fail trên Ψ₀ nếu còn ngân sách sau G4; nhánh B⁺ để tách tác dụng "nhắm đúng chỗ lỗi" khỏi "dùng nhiều loại can thiệp", ưu tiên thấp hơn B-fail; một giao diện xem evidence card tối thiểu. Architect chọn công cụ.

### 6.2 Ngoài phạm vi 12 tuần

- Robot thật, cell thật, real2sim.
- Video công nhân DENSO qua V2D; world model DreamDojo; task DENSO thật.
- Nhiều task chạy vòng Failure → Data. L0 chỉ có task chính và task F1. F1 kiểm khả năng tổng quát của lõi; chỉ thành dự phòng cho Q2 khi V3 xác nhận cặp task của F1 cùng bộ điều khiển.
- Dùng episode lỗi làm tín hiệu train (Mulligan học value function từ cả dữ liệu lỗi). Đây là hướng L1.
- Nhiều embodiment; phân quyền nhiều người dùng; lưu trữ tập trung cho nhiều đội.
- Giao diện người dùng hoàn chỉnh.
- Pretrain model; train lại AMO.
- Tự động hóa hoàn toàn quyết định. Kỹ sư luôn duyệt.
- Sinh dữ liệu với tham số Level 1 hoặc Level 2.
- Claim tiết kiệm tiền mặt, claim kết quả trên robot thật, claim thuật toán học máy mới.

### 6.3 Tiêu chí MVP thành công

MVP thành công khi **đủ cả năm điều** sau. Không yêu cầu HT đúng.

1. Các cổng G0 đến G6 đạt, hoặc phương án dự phòng của spec v10 mục 10 được kích hoạt và ghi lại.
2. Ít nhất một vòng Failure → Data chạy trọn trên Ψ₀: trace → evidence card → đề xuất → kỹ sư duyệt → thu và QA → train → cổng dev → cập nhật tỉ lệ sửa được, với sổ chi phí đầy đủ.
3. Holdout chạy đúng một lần; không lộ dữ liệu.
4. HS, HT (HTa, HTb), HD được kết luận đúng tiêu chí đã chốt, kể cả khi trượt hoặc khi HT hạ thành kết quả mô tả.
5. Ba đầu ra BTC được giao; mọi claim trong pitch có số đo đi kèm hoặc đã bị gỡ.

## 7. Tầm nhìn sau MVP

| Mức | Phạm vi | Giá trị mở khóa cho DENSO | Lõi cần thêm | Điều kiện để bắt đầu |
|---|---|---|---|---|
| L1 · Nhiều task | 3–5 task cùng robot, sim | Thống kê tỉ lệ sửa được dùng chung giữa task; task mới khởi đầu rẻ hơn; bắt đầu có hào chắn | Thư viện scorer theo loại task; prior tỉ lệ sửa được theo họ task, gộp theo lớp lỗi chung; dùng dữ liệu lỗi để train | L0 xong; có danh sách task DENSO quan tâm |
| L2 · Robot thật | 1 cell thật | Con số giờ công trên robot thật; kiểm được lợi ích sim có chuyển sang thật không | Adapter robot thật, an toàn, teleop thật, real2sim cho tình huống lỗi | Cổng nghiệm thu riêng; BTC hoặc DENSO cấp robot |
| L3 · Nhiều robot | Nhiều embodiment | Đổi robot không mất tài sản dữ liệu; so sánh robot bằng cùng thước đo | Chuẩn hóa schema state và action theo embodiment; adapter model đa robot | L2 có kết quả; có robot thứ hai |
| L4 · Nhiều nhà máy | Nhiều đội dùng chung | Báo cáo chi phí theo đơn vị; tri thức lỗi chia sẻ giữa nhà máy | Phân quyền, nhiều người dùng, lưu trữ tập trung, quản trị dữ liệu | Có ít nhất hai đội cam kết dùng |

Ràng buộc thiết kế cho L0 để không viết lại: vector điều kiện khai báo được theo task; mục sổ chi phí dùng đơn vị chung; evidence card và trace không chứa trường riêng của Ψ₀ hay SIMPLE ở phần lõi.

## 8. Bối cảnh cạnh tranh và giải pháp liền kề

Kiểm ngày 22/10/2026 bằng nguồn công khai. Phần lớn nguồn là tài liệu của chính công ty; số hiệu năng chưa được kiểm độc lập. IntervenGen và CUPID thêm theo phản biện ([05 mục 8](05-review-and-mentor-questions.md)).

### 8.1 Các hướng liền kề

| Hướng | Làm được gì theo nguồn công khai | Chồng lấn với Humanoid Data Flywheel | Nguồn |
|---|---|---|---|
| Data engine xe tự lái: Tesla | Shadow mode so policy với tài xế; bắt snapshot khi lệch; viết bộ phát hiện tình huống rồi gửi xuống đội xe để gom ca tương tự | Ý tưởng gốc của vòng "lỗi → dữ liệu"; dựa vào quy mô đội xe, không có sổ chi phí công khai | [IEEE Spectrum](https://spectrum.ieee.org/tesla-autopilot-data-deluge) |
| Data engine xe tự lái: Applied Intuition | Nạp log, tìm tình huống, sinh biến thể trong sim, theo dõi vùng phủ test và lỗi gắn với commit | Gần nhất về quy trình log → kịch bản → sim → đo; cho xe, không cho humanoid; nguồn là phân tích bên thứ ba | [Sacra](https://sacra.com/research/applied-intuition) |
| NVIDIA Isaac Lab Mimic và GR00T-Mimic | Nhân vài demo người thành nhiều quỹ đạo tổng hợp; chỉ giữ quỹ đạo thành công | Là bộ sinh dữ liệu, phần cắm của ta; không quyết định sinh ở đâu, bao nhiêu | [Isaac Lab Mimic](https://isaac-sim.github.io/IsaacLab/release/3.0.0/source/features/imitation-learning/teleop_imitation.html), [NVIDIA blog](https://developer.nvidia.com/blog/building-a-synthetic-motion-generation-pipeline-for-humanoid-robot-learning) |
| NVIDIA Cosmos | Tăng cường video (Transfer), sinh khung hình (Predict), chấm dữ liệu sinh (Reason), lọc và loại trùng (Curator) | Có thể cắm làm tăng cường thị giác; Reason chấm dữ liệu, không chẩn đoán policy | [NVIDIA Cosmos](https://developer.nvidia.com/cosmos) |
| Hugging Face LeRobot | Định dạng dữ liệu chung, công cụ tách và gộp dataset, train ACT, Diffusion, VLA, đánh giá; hỗ trợ G1; Apache 2.0 | Hạ tầng mở nên tương thích; không có chẩn đoán lỗi hay sổ chi phí | [GitHub LeRobot](https://github.com/huggingface/lerobot) |
| Rerun | Ghi và xem dữ liệu đa phương thức theo thời gian; đọc MCAP và LeRobot; mã nguồn mở | Có thể dùng để xem trace và evidence card; kỹ sư vẫn tự chẩn đoán | [GitHub Rerun](https://github.com/rerun-io/rerun) |
| Foxglove | Ghi, lưu, xem log robot; từ 4/2026 có tìm và tuyển chọn sự kiện bất thường | Gần nhất ở khâu tìm lỗi trong log lớn; chưa thấy chẩn đoán nguyên nhân hay chọn dữ liệu theo chi phí | [Thông cáo 4/2026](https://www.bakersfield.com/ap/news/foxglove-launches-unified-data-search-and-curation-platform-to-accelerate-physical-ai-development/article_dce3e551-9365-53d5-beb2-a21840cdcd1f.html) |
| Scale AI Physical AI | Thu demo quy mô lớn, gán nhãn, kiểm dataset bằng fine-tune nội bộ | Bán dữ liệu theo đơn hàng; trang sản phẩm không nhắc chọn dữ liệu theo lỗi của policy | [Scale Physical AI](https://scale.com/physical-ai) |
| Encord | Nền tảng dữ liệu physical AI; so dự đoán với nhãn để chỉ ra kiểu lỗi và dữ liệu liên quan; tuyển chọn edge case | Chồng lấn ở chẩn đoán kiểu lỗi và tuyển chọn; thiên về thị giác và gán nhãn, chưa thấy quyết định loại can thiệp theo chi phí | [Business Wire 6/2025](https://www.businesswire.com/news/home/20250612297482/en/Encord-Launches-Unified-Platform-to-Accelerate-Physical-AI-Development-Across-Robotics-Autonomous-Vehicles-and-Drones) |
| Nghiên cứu: Mulligan (10/2026) | Coi việc chọn trạng thái đầu là quyết định; ưu tiên trạng thái từng lỗi hoặc chưa thử; học value function trên mọi dữ liệu kể cả lỗi; thắng lấy mẫu đều ở cùng ngân sách trên 3 task robot thật và 2 task sim | Rất gần với kiểm vùng phủ và HTa; một loại can thiệp, không kiểm hệ thống, không sổ chi phí tiền. Dùng dữ liệu lỗi để train, PoC thì chưa (hướng L1) | [arXiv 2610.05882](https://arxiv.org/abs/2610.05882) |
| Nghiên cứu: DISEIL (9/2026) | Đánh dấu bước policy bắt đầu sai, gom thành kiểu lỗi, dùng model ngôn ngữ soạn yêu cầu demo tiếp theo; kiểm khả thi bằng kho ràng buộc trước khi tốn công expert; 5 task sim, 10 setting | Rất gần với gán bước hỏng, cụm lỗi và kiểm khả thi; một vòng, trong sim, chuyên gia phần lớn là script | [arXiv 2609.08123](https://arxiv.org/abs/2609.08123) |
| Nghiên cứu: phân loại lỗi tự động | Model ngôn ngữ thị giác giải thích từng lỗi rồi gom cụm; cụm dùng để định hướng thu dữ liệu | Thay thế được bước gom cụm sơ bộ; không đo lại theo chi phí | [arXiv 2506.06570](https://arxiv.org/abs/2506.06570) |
| Nghiên cứu: Genie Centurion | Tua lại trạng thái trước lỗi, người điều khiển sửa; module dự đoán thành công gọi người khi cần | Tương đương teleop correction và dữ liệu phục hồi; có đo dữ liệu dùng được trên mỗi đơn vị công người | [arXiv 2505.18793](https://arxiv.org/abs/2505.18793) |
| Nghiên cứu: IntervenGen (2024) | Sinh hàng loạt correction từ khoảng 10 can thiệp của người | Tiền lệ cho teleop correction và dữ liệu phục hồi do máy sinh; là bộ sinh dữ liệu, cắm được làm tuyến T2 khi V3 âm hoặc khi không có thiết bị teleop (Q6) | [arXiv 2405.01472](https://arxiv.org/abs/2405.01472) |
| Nghiên cứu: DataMIL | Chọn dữ liệu từ kho có sẵn bằng datamodels | Chọn từ kho, không thu mới; tính toán gấp nhiều lần một lần train | [arXiv 2505.09603](https://arxiv.org/abs/2505.09603) |
| Nghiên cứu: CUPID (2025) | Lọc và chọn demo bằng influence function theo ảnh hưởng tới return của policy | Bước kiểm demo mâu thuẫn bằng mắt của ta là bản thủ công của hướng này; chọn từ kho có sẵn, không thu mới | [arXiv 2506.19121](https://arxiv.org/abs/2506.19121) |
| Nghiên cứu: RoboLineage (6/2026) | Ghi rollout, quyết định dataset, train, đánh giá, kế hoạch thu tiếp thành lineage; agent tóm tắt; mã nguồn mở | Chồng lấn với Data Core và lineage; tóm tắt không mô tả chẩn đoán lỗi hay chọn theo chi phí | [arXiv 2606.22142](https://arxiv.org/abs/2606.22142) |

### 8.2 Khoảng trống

Bảng chỉ phản ánh các nguồn ở mục 8.1. Dòng cuối là mục tiêu của L0, chưa đo.

| Nhóm | Chẩn đoán, tách lỗi hệ thống khỏi lỗi dữ liệu | Chọn loại và lượng dữ liệu theo chi phí | Đo lại có đối chứng, có sổ chi phí | Tích lũy tỉ lệ sửa được qua vòng |
|---|---|---|---|---|
| Data engine xe tự lái | Một phần | Một phần, nhắm tình huống | Một phần | Chưa thấy công bố |
| Bộ sinh dữ liệu NVIDIA | Không | Không | Không | Không |
| LeRobot, Rerun, Foxglove | Một phần, kỹ sư tự làm | Không | Một phần, có đánh giá | Không |
| Scale AI, Encord | Một phần, kiểu lỗi thị giác | Một phần, tuyển chọn | Một phần | Chưa thấy công bố |
| Mulligan, DISEIL, Genie Centurion | Một phần, gom cụm; DISEIL kiểm khả thi trước khi tốn công expert; không kiểm hệ thống | Có, cho một loại can thiệp, ngân sách tính bằng episode | Có, đo held-out | Một phần |
| IntervenGen, CUPID | Một phần: CUPID chỉ ra demo gây hại; không kiểm hệ thống | Một phần: sinh correction (IntervenGen) hoặc chọn demo (CUPID), không theo chi phí | Một phần, đo policy, không sổ chi phí | Chưa thấy công bố |
| Humanoid Data Flywheel (mục tiêu L0) | Mục tiêu, chưa đo: hệ thống trước dữ liệu | Mục tiêu, chưa đo: nhiều loại can thiệp, lợi ích trên chi phí tiền và giờ công | Mục tiêu, chưa đo: cổng dev, holdout ghép cặp, sổ chi phí | Mục tiêu, chưa đo: Ψ₀ mặc định 1 vòng; F-ACT 5–8 vòng trên ACT; đo đầy đủ ở L1 |

Khoảng trống sản phẩm nhắm tới: **trong phạm vi đã tra ngày 22/10/2026, chưa thấy quy trình vận hành nào kiểm hệ thống trước, rồi chọn giữa nhiều loại can thiệp bằng một thước đo tiền và giờ công gồm cả chi phí chẩn đoán, rồi đo lại có đối chứng.** Ở L0 đây là mục tiêu, chưa phải kết quả.

Những điều phải nói rõ khi trình bày:

- Mulligan và DISEIL đã cho thấy chọn dữ liệu theo lỗi tốt hơn rải đều trong bối cảnh của họ, nên ý tưởng này không mới. HT là **kiểm lại (replication)** kết quả đó trên G1 toàn thân với Ψ₀, tính đủ chi phí chẩn đoán. HTb (C so với B-fail) đo phần chẩn đoán mà hai công trình này chưa tách.
- DISEIL cũng kiểm khả thi trước khi tốn công expert; RoboLineage ghép lineage và kế hoạch thu tiếp. Đóng góp của đội hẹp hơn: thứ tự kiểm hệ thống trước, nhiều loại can thiệp trên cùng thước đo chi phí, và phép đo xem cả quy trình có đáng tiền không.
- Mulligan học value function trên mọi dữ liệu kể cả lỗi; PoC hiện không dùng episode lỗi làm mẫu dương (spec 4.4). Dùng dữ liệu lỗi để train là hướng L1.
- Correction và dữ liệu phục hồi có tiền lệ HG-DAgger và IntervenGen; kiểm demo mâu thuẫn bằng mắt là bản thủ công của CUPID và DataMIL.
- Foxglove, Encord hoặc NVIDIA có thể thêm lớp này. Đề xuất: tương thích với LeRobot, dùng được Rerun hoặc Foxglove để xem, cắm Isaac Lab Mimic làm bộ sinh dữ liệu, thay vì cạnh tranh ở các khâu đó.
- Đề xuất cho PM: cân nhắc Mulligan làm đối chứng bổ sung cho nhánh C nếu còn ngân sách sau G4. Đây là thay đổi phạm vi, cần đội quyết. PO quyết: ngoài phạm vi 12 tuần, đưa vào backlog L1 (04 mục 1.3). Theo 06 mục 4, nhánh rẻ **B-fail** (kiểu Mulligan rút gọn, không cần value function; mục 6.1) thay vai trò ưu tiên của B⁺, chạy trên ACT là chính.

## 9. Ràng buộc và giả định

### 9.1 Ràng buộc

| Ràng buộc | Nội dung | Hệ quả |
|---|---|---|
| Thời gian | 12 tuần, 6 cổng G0–G6 | Không có chỗ cho tính năng ngoài mục 6.1 |
| Đội | 5 người; mảng Simulation và Data trên trang đội còn "chờ bổ sung minh chứng" | Rủi ro năng lực ở TN1 và TN6 |
| GPU | Có RTX 3060 12 GB và RTX 5090 32 GB; full fine-tune Ψ₀ 2,5B tham số có thể cần A100 80 GB thuê ngoài | Ngân sách thuê chưa biết; dự phòng LoRA hoặc đóng băng VLM, giảm seed. Cắt Ψ₀ về 2 seed thì HT thành kết quả mô tả |
| Robot thật | Phụ thuộc BTC | Ngoài phạm vi; mọi số liệu là trong mô phỏng |
| Bộ điều khiển | Task chính chạy decoupled WBC (`g1_sonic`, env `SonicLocoManipEnv`); pipeline motion planning chạy AMO | Dữ liệu sinh của B và các đường dựa vào planner của C phụ thuộc V3 (A6); kiểm hệ thống nhắm vào stack WBC |
| Teleop | Chưa rõ có thiết bị cho SIMPLE (Q6) | Correction có thể do planner hoặc bộ sinh kiểu IntervenGen tạo; phải ghi rõ trong báo cáo |
| Phân phối sim | Dữ liệu sim cùng phân phối với môi trường test | Lợi ích của sim có thể bị phóng đại so với robot thật |
| Quyền dữ liệu | Bộ GR00T Teleop-Sim của NVIDIA (video RoboCasa GR1 đang dùng trên website) có giấy phép CC BY-NC 4.0, chỉ dùng phi thương mại | Không đưa dữ liệu NC vào release dùng cho mục đích thương mại của DENSO |
| Quyền dữ liệu | psi-data và trọng số Ψ₀ trên Hugging Face chưa khai giấy phép (kiểm 22/10/2026); mã Ψ₀ là Apache 2.0; SIMPLE là MIT nhưng tài sản Objaverse và HSSD có giấy phép riêng | Lineage phải ghi giấy phép; cần hỏi tác giả trước khi dùng ngoài PoC |

### 9.2 Giả định

| Mã | Giả định | Ai xác nhận, khi nào |
|---|---|---|
| A1 | DENSO có một công đoạn gắp và đặt tương tự task chính | DENSO, càng sớm càng tốt |
| A2 | Đơn giá operator $10/h, kỹ sư $20/h, A100 80 GB $1,59/GPU-h; chưa tính chi phí giờ cell (robot, người giám sát, thời gian dừng) | DENSO cho đơn giá nội bộ và chi phí giờ cell; giá GPU kiểm lại khi thuê |
| A3 | Có 144 đợt cải thiện mỗi năm | DENSO; không đo được trong PoC |
| A4 | Debug baseline 20 giờ kỹ sư mỗi đợt | Đo một phần bằng HD; DENSO cho số thực tế |
| A5 | Gói task chính có ít nhất 50 demo teleop đạt QA | G0, câu Q1 |
| A6 | SIMPLE cho đặt lại trạng thái đã lưu, tách ngẫu nhiên hóa hình ảnh, có planner cho task chính chạy cùng bộ điều khiển với dữ liệu teleop (teleop chạy decoupled WBC, motion planning chạy AMO), hoặc ánh xạ được sang WBC | G0, câu Q2–Q4; phần bộ điều khiển là V3 của 03 mục 3.3, hạn ngày 5 của Sprint 1. Nếu V3 âm, chốt tuyến T1–T4 cuối tuần 2 (mục 10.1) |
| A7 | Fine-tune Ψ₀ vừa ngân sách GPU | G0, câu Q5 |
| A8 | Kết quả trong sim có giá trị định hướng cho robot thật | Chỉ kiểm được ở L2 |
| A9 | Checkpoint gốc Ψ₀ dùng cho E1 và các nhánh (`pre.*` hoặc `postpre.*`) chưa train trên dữ liệu SIMPLE hoặc sonic của task chính | G0, câu Q0; hỏi PSI Lab; ghi nguồn gốc vào thực thể Source. `simple-checkpoints` và `sonic-checkpoints` chỉ dùng để tái tạo số công bố |

## 10. Rủi ro và câu hỏi mở

### 10.1 Rủi ro chính

| Rủi ro | Ảnh hưởng | Dấu hiệu sớm | Giảm thiểu |
|---|---|---|---|
| Teleop và motion planning khác bộ điều khiển (V3 âm) | Nhánh B không có dữ liệu sinh hợp lệ; các đường của C dựa vào planner mất nền. Nếu cả V3 và Q6 âm, C chỉ còn kiểm demo mâu thuẫn, HT sụp và phải ghi vào báo cáo | V3 chưa có câu trả lời ngày 5 của Sprint 1; chạy lại rollout MP trong env WBC thất bại | Thử song song tuần 1–2, chốt cuối tuần 2: T1 tái thực thi quỹ đạo MP trong env WBC (1–2 tuần); T2 biến thể kiểu MimicGen / IntervenGen từ đoạn teleop, chạy IK cộng WBC (2–3 tuần). T3 planner trong env WBC (2–4 tuần). T4 chuyển sang env MP và thu hẹp claim (vài ngày, phương án cuối). F1 không là dự phòng cho Q2 cho tới khi V3 xác nhận |
| Checkpoint gốc Ψ₀ đã thấy dữ liệu task chính (Q0) | Đường cong E1 và so sánh các nhánh mất nghĩa | Ψ₀ ở mức 10% dữ liệu cao bất thường; PSI Lab chưa trả lời | Q0 ở G0 (A9); RunPlan không trỏ `simple-checkpoints` hoặc `sonic-checkpoints` cho E1 và các nhánh; guard gần trùng theo khoảng cách điều kiện |
| HT trượt (C không hơn B) | Kết quả kiểu Mulligan / DISEIL không lặp lại trên G1 khi tính đủ chi phí; claim thu hẹp | Cổng dev của vòng 1 không qua | Báo cáo trung thực; thu hẹp claim về DENSO Data Model và sổ chi phí |
| Thiếu lực thống kê cho HT | Không kết luận được C − B | Hai seed ở D\* lệch > 5 điểm %; hiệu ứng nhỏ nhất phát hiện được > 10 điểm % ở G2 | Bootstrap phân cấp; power analysis ở G2; 5 seed Ψ₀ cho B và C, đổi chỉ tiêu chính, hoặc hạ HT thành mô tả |
| Kinh tế phụ thuộc r_debug | Không giảm giờ debug thì lỗ $31,80 mỗi đợt theo mô hình Pitch v10 | Thí nghiệm HD không cho giảm rõ | Chỉ số chính chuyển sang số demo người để đạt ngưỡng, phút operator mỗi điểm %, sai số dự báo chi phí, số ngày đạt lại ngưỡng (mục 5.3); r_debug báo dạng khoảng; bảng độ nhạy theo đơn giá DENSO và chi phí giờ cell |
| HD thiên lệch | Mẫu 20 episode, người tham gia là thành viên đội | Mentor phản biện thiết kế | ≥ 2 người ngoài đội (mentor hoặc đội khác); đối thủ là công cụ chuẩn (Rerun cộng đồ thị mặc định); chèn 3–4 evidence card sai cố ý; nêu rõ giới hạn |
| Chạm trần | Không đo được khác biệt giữa các nhánh | Ψ₀ ở mức 10% dữ liệu đã ≥ 90%; dưới 15 lỗi dev Level 0 ngay sau G3 | Chuyển chỉ tiêu chính sang Level 2 hoặc kích hoạt task khó hơn đã khai ở spec 7.1 |
| Ψ₀ không vừa GPU | Trễ G0, đội đổi kế hoạch | Hết bộ nhớ khi fine-tune thử | LoRA hoặc đóng băng VLM; thuê A100; giảm seed và ghi rõ |
| Lõi dính chặt vào Ψ₀ hoặc SIMPLE | Không mở rộng được L1–L3 | Lõi có trường hoặc lệnh riêng của Ψ₀ | Viết adapter ACT và Diffusion Policy ngay từ G1 để kiểm ranh giới |
| Trôi phạm vi sang làm giao diện | Vòng chưa chạy trọn khi hết 12 tuần | Tuần 6 chưa có trace và scorer chạy được | Giao diện chỉ ở mức "nên có"; ưu tiên TN1–TN8 |
| Đối thủ lớn thêm tính năng tương tự | Giảm giá trị khác biệt | Thông báo sản phẩm của Foxglove, Encord, NVIDIA | Tích hợp thay vì cạnh tranh; hào chắn dựa vào dữ liệu của DENSO |
| Giấy phép dữ liệu | Không dùng được kết quả cho DENSO | Nguồn không khai giấy phép hoặc là NC | Ghi giấy phép trong lineage; hỏi tác giả psi-data |

### 10.2 Câu hỏi mở, theo thứ tự ưu tiên

Cho DENSO:

1. Có công đoạn cụ thể nào và ai là task owner? Thay đổi nào xảy ra thường nhất: linh kiện, khay hay ánh sáng?
2. Mỗi năm có bao nhiêu lần đổi điều kiện cần huấn luyện lại, và hiện mất bao nhiêu giờ operator và giờ kỹ sư mỗi lần? Số này thay cho giả định 144 đợt và 20 giờ debug.
3. DENSO đánh giá bằng chỉ số nào: tỉ lệ thành công, số ngày đạt ngưỡng, giờ công hay tiền? Ngưỡng 75% theo Cấp 2 của đề có phù hợp không?
4. Dữ liệu nhà máy có được rời khỏi site không? DENSO có chấp nhận dữ liệu giấy phép phi thương mại trong PoC không?
5. Đơn giá nội bộ cho operator và kỹ sư là bao nhiêu? Một giờ cell tốn bao nhiêu nếu tính robot, người giám sát và thời gian dừng dây chuyền?

Cho mentor:

6. Mentor có chuyên môn gì: robot learning, simulation, hệ thống dữ liệu hay vận hành nhà máy?
7. Thiết kế thống kê (3 seed, bootstrap phân cấp, power analysis ở G2, 150 điều kiện holdout) và thiết kế HD đã đủ chặt chưa?
8. Nhánh B-fail trên ACT có đủ để tách phần chẩn đoán khỏi phần nhắm lỗi, hay cần đối chứng Mulligan đầy đủ?

Cho BTC:

9. Ngân sách GPU thuê ngoài tối đa cho 12 tuần là bao nhiêu? BTC có cấp robot hoặc thiết bị teleop không, khi nào?
10. Mã đề chính thức là H1 hay H2? Giám khảo chấm theo 3 cấp của đề như thế nào?

Nội bộ, trả lời ở cổng G0: Q0–Q6 của spec v10 mục 2.4 và V3 (hạn ngày 5 của Sprint 1).

## 11. Change log

| Ngày | Phiên bản | Nội dung | Người sửa |
|---|---|---|---|
| 22/10/2026 | 0.1 | Bản đầu | Analyst |
| 22/10/2026 | 0.2 | Mục 6.1, 9.1, 10.1: đổi mã tính năng F1–F10 thành TN1–TN10 để không trùng "task dự phòng F1" của spec | PO |
| 22/10/2026 | 0.2 | Mục 6.1: TN8 (sổ chi phí) đổi cổng thành G1–G4, TN10 (giao diện adapter) thành G0–G1, khớp PRD Epic 1, 2 | PO |
| 22/10/2026 | 0.2 | Mục 9.2: A6 thêm điều kiện planner chạy cùng bộ điều khiển với dữ liệu teleop (V3 của 03) | PO |
| 22/10/2026 | 0.2 | Mục 8.2: ghi quyết định của PO về đối chứng Mulligan | PO |
| 22/10/2026 | 0.3 | Toàn file (05 #7): đổi tên giả thuyết H1, H2, H3 thành HS, HT (HTa, HTb), HD; giữ mã đề "H1" | Analyst theo 06 |
| 22/10/2026 | 0.3 | #6 Định vị lại tính mới, mục 1, 2.2, 2.4, 3.4, 8, 10.1: câu định vị của 06 mục 6; HT là kiểm lại kiểu Mulligan / DISEIL; "trong phạm vi đã tra ngày 22/10/2026"; ô L0 ở 8.2 thành "Mục tiêu, chưa đo"; thêm IntervenGen, CUPID vào 8.1; Mulligan học value function từ dữ liệu lỗi, dùng dữ liệu lỗi để train là hướng L1; bỏ "mất điểm khác biệt chính"; gọi Data Core cộng SOP là "DENSO Data Model" | Analyst theo 06 |
| 22/10/2026 | 0.3 | #7 Tiêu chí BTC, mục 1, 5.3, 10.2: thêm bảng map tiêu chí 3 cấp; D\* theo ngưỡng ≥ 75%; HS đạt ≥ 75%; hỏi BTC mã đề và cách chấm | Analyst theo 06 |
| 22/10/2026 | 0.3 | #10 Kinh tế, mục 2.4, 5.1, 5.3, 9.2 A2, 10.1, 10.2: chỉ số giá trị chính mới (số demo người để đạt ngưỡng, phút operator mỗi điểm %, sai số dự báo chi phí, số ngày đạt lại ngưỡng, chi phí mỗi điểm % của C so với B và B-fail); r_debug dạng khoảng; chi phí giờ cell | Analyst theo 06 |
| 22/10/2026 | 0.3 | #1 Bộ điều khiển, mục 6.1 TN6, 6.2, 9.1, 9.2 A6, 10.1, 10.2: V3 hạn ngày 5 của Sprint 1; tuyến T1–T4; kịch bản V3 và Q6 cùng âm; F1 không còn là dự phòng cho Q2 | Analyst theo 06 |
| 22/10/2026 | 0.3 | #8 Nguồn gốc checkpoint, mục 9.2 thêm A9, 10.1: Q0 ở G0; RunPlan không trỏ `simple-checkpoints`, `sonic-checkpoints` | Analyst theo 06 |
| 22/10/2026 | 0.3 | #4 Công bằng giữa nhánh, mục 5.3, 6.1, 8.2: nhánh B-fail cho HTa và HTb, ưu tiên hơn B⁺; N_B chốt trước G3; tăng cường thị giác áp chung cho mọi nhánh | Analyst theo 06 |
| 22/10/2026 | 0.3 | #2 Thống kê, mục 5.3, 9.1, 10.1: bootstrap phân cấp; power analysis ở G2; quy tắc 2/3 seed thành chỉ số phụ; cắt về 2 seed thì HT thành mô tả | Analyst theo 06 |
| 22/10/2026 | 0.3 | #3 Tỉ lệ sửa được, mục 1, 3.1, 3.2, 3.4, 6.1 TN9: tài sản cần đo ở L1; cổng dev trên tập điều kiện mới, sàn A/A; đối chứng policy cha; F-ACT 5–8 vòng trên ACT; Ψ₀ mặc định 1 vòng C | Analyst theo 06 |
| 22/10/2026 | 0.3 | #5 Thí nghiệm HD, mục 5.2, 10.1: ≥ 2 người ngoài đội; đối thủ là Rerun cộng đồ thị mặc định; chèn evidence card sai cố ý | Analyst theo 06 |
