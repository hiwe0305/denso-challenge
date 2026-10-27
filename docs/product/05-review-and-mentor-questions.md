# 05 · Phản biện độc lập và câu hỏi cho mentor

> **Lưu trữ (27/10/2026).** File này giữ làm vết quyết định của bản v10.1–v10.2; 02, 03, 04 vẫn trích mã của nó. Không cập nhật theo hướng hiện hành; hướng hiện hành ở [spec v10.4](../spec-v10-failure-to-data.md) và [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md).

_Ngày 22/10/2026. Vai trò: QA / Test Architect (Quinn) kiêm người phản biện độc lập (BMAD). Đầu vào: [spec v10.1](../spec-v10-failure-to-data.md), 00 (file đã xóa ngày 27/10/2026), [01](01-project-brief.md), [02](02-prd.md), [03](03-architecture.md), [đề BTC](../challenge/README.md) gồm hai ảnh `1.jpeg`, `2.jpeg`. File này không sửa tài liệu khác; mọi đề xuất sửa nằm ở mục 7 để trưởng nhóm áp dụng. Nguồn mới kiểm ngày 22/10/2026 ở mục 8. Đã rà lại theo bản 0.2 của 01, 02, 03 và bản sửa mục 1.2 của spec (PO, cùng ngày); 04 chưa có trên đĩa lúc rà nên các chỗ trỏ "04 mục 1.3" chưa được kiểm._

> **Trạng thái áp dụng:** 10 sửa ở mục 7 đã áp ngày 22/10/2026 theo [06](06-review-round-1-decisions.md); xem change log spec v10.1, 00 0.2, 01 0.3, 02 0.3, 03 0.3. Cột "Đã áp" ở mục 7 ghi nơi áp từng sửa. Các bảng phản biện ở mục 1–5 giữ nguyên như lúc rà để làm bằng chứng; trích dẫn trong đó trỏ tới bản cũ (spec v10, 01 0.2, 02 0.2, 03 0.2). Câu hỏi mới phát sinh khi áp sửa nằm ở mục 6.6. Tên giả thuyết đã đổi theo 06: HS, HT (HTa, HTb), HD; mã đề giữ "H1". Phản biện cho [spec v10.2](../spec-v10-failure-to-data.md) và design 23/10/2026 (file đã xóa ngày 27/10/2026) nằm ở mục 6.7.

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 22/10/2026 | 0.1 | Bản đầu: phản biện, chiến lược kiểm thử, pre-mortem, sổ rủi ro, câu hỏi mentor, 10 sửa ưu tiên | QA |
| 22/10/2026 | 0.2 | Ghi trạng thái áp dụng; đổi tên giả thuyết theo 06 (giữ mã đề); thêm cột "Đã áp" ở mục 7; thêm mục 6.6 câu hỏi mở sau vòng 1 (MO1–MO5); sửa trích dẫn trỏ sai (RL8, KT2, mục 5, mục 6) | SM theo 06 |
| 23/10/2026 | 0.3 | Thêm mục 6.7: phản biện và câu hỏi cho spec v10.2 (robot DENSO, pipeline ba nguồn, NIM, probe theo stage, robot thay thế, tải người), MO6–MO13; thêm PM9 vào mục 4; ghi trạng thái áp dụng của MO4 | QA theo 06 mục 11 |

Quy ước: **Cao** là có thể làm sai kết luận HS, HT, HD hoặc lỡ cổng; **TB** là làm yếu claim hoặc tốn thêm 1–2 tuần; **Thấp** là cần sửa cho sạch. Mã tham chiếu: "spec 6.11" là mục 6.11 của spec v10; "01 §8.2" là mục 8.2 của brief; "02 · 6.5" là story 6.5 của PRD. Mã vấn đề của file này (TM, TH, DK, KT, AR, KD, SR) và mã câu hỏi mở (MO) không liên quan tới mã tính năng TN1–TN10 của brief. Tài liệu khác trích mã của file này bằng tiền tố đúng, ví dụ "05 TH12", không phải "05 TN12".

## 1. Kết luận phản biện

### 1.1 Idea đứng vững ở đâu

1. **Kỷ luật đo lường hiếm thấy ở một đội hackathon:** tiêu chí chốt trước (spec 3), nhánh đối chứng A₀.₇ để không nhầm "sim giúp" với "teleop chưa phải nút thắt" (spec 3, ghi chú HS), holdout khóa một lần (spec 7.3.8, 03 §8.3), sổ chi phí tính cả chi phí chẩn đoán (spec 7.3.5). Đây là phần giám khảo khó bắt bẻ nhất.
2. **Ranh giới claim trung thực:** spec 1.2 và 01 §3.4 tự nhận không có thuật toán mới và ý "chọn dữ liệu theo lỗi" không mới. HT trượt vẫn là kết quả hợp lệ (spec 7.7).
3. **Khớp phạm vi BTC:** 1 kỹ năng trong mô phỏng, so sánh ≥ 2 phương pháp và lượng dữ liệu cần (ảnh đề `1.jpeg`, mục "Phạm vi 3 tháng") khớp E1 và ma trận phương pháp (spec 7.1, 7.4). Mức 0,7D\* trùng đúng tiêu chí Cấp 2 "giảm ≥ 30% demo" (ảnh `2.jpeg`).
4. **Kiến trúc đã kiểm nguồn thật** (03 §3.2) và chính nhờ đó phát hiện vấn đề bộ điều khiển (03 §3.3 V3). Đây là phát hiện có giá trị nhất của bộ hồ sơ.

### 1.2 Idea gãy ở đâu

1. **Bộ điều khiển:** task Teleop chạy decoupled WBC (`g1_sonic`), pipeline MP chạy AMO (03 §3.2). Nếu không ánh xạ được, nhánh B không có dữ liệu sinh hợp lệ và 4 trong các đường chẩn đoán, can thiệp của C mất nền (mục 2.3). Task dự phòng F1 không chữa được vì cùng mẫu Teleop/MP.
2. **Thống kê không đủ lực cho HT:** CI bootstrap chỉ lấy mẫu lại điều kiện, bỏ phương sai giữa seed huấn luyện (spec 7.5). Ước tính thô ở mục 2.2 cho thấy cần chênh lệch thật khoảng 7–14 điểm % mới có 80% lực; trong mô phỏng gần trần, khó đạt.
3. **Phần "flywheel học" không chứng minh được ở L0:** chỉ 2 vòng, prior Beta(1, 1), tỉ lệ sửa được bị thiên lệch hồi quy về trung bình (spec 6.13), và hàm chọn g/c suy biến thành "xếp theo đơn giá" ở vòng 1 (spec 6.11).
4. **Tính mới của HT đã bị Mulligan và DISEIL chiếm.** Spec 1.2 (bản sửa) đã ghi nhận, nhưng 00 §4, 01 §2.4 và §10.1 vẫn gọi HT là "điểm khác biệt chính". Khác biệt còn lại hẹp: kiểm hệ thống trước, nhiều loại can thiệp trên một thước đo chi phí gồm chi phí chẩn đoán.
5. **Kinh tế đứng trên chân yếu nhất:** công thức spec 8.2 không có số hạng nào cho HT; lợi ích dương chỉ nhờ r_debug, mà r_debug chỉ đến từ HD với 20 episode do chính thành viên đội làm.
6. **Năng lực:** 52 story (sau bản 0.2) chiếm khoảng 87% năng lực danh nghĩa, không có đệm; trưởng nhóm giữ 11 story nằm trên đường găng của mọi cổng; tuần 9–10 không đủ cho 2 vòng C cộng C cuối (mục 2.4).
7. **Chưa bám tiêu chí BTC:** không tài liệu nào trích tiêu chí định lượng 3 cấp trong ảnh đề (≥ 50%; ≥ 30% ít demo cùng hiệu năng và ≥ 75%; ≥ 70% trên biến thể chưa train kèm khuyến nghị quy trình thu dữ liệu định lượng). Ảnh đề ghi mã "H2 · Efficient Humanoid Training & DENSO Data Model", còn README và mọi tài liệu ghi "H1", trùng tên với giả thuyết H1–H3 cũ (nay là HS, HT, HD theo 06).

### 1.3 Mức sẵn sàng

| Tài liệu | Mức | Lý do | Điều kiện để đạt |
|---|---|---|---|
| 01 · Brief (0.2) | Cần sửa | Nhãn bằng chứng tốt; bản 0.2 đã đổi mã tính năng thành TN1–TN10 và ghi điều kiện V3 vào giả định A6. Nhưng 01 §1 mục 4 và §8.2 vẫn claim "chưa ai ghép đủ", bảng 8.2 ghi "Có" cho L0 khi chưa đo; §2.4 và §10.1 vẫn gọi HT là "điểm khác biệt chính"; §3.4 dựa vào tỉ lệ sửa được không chứng minh được ở L0; KPI §5.3 không map tiêu chí BTC; kinh tế không có HT | Áp dụng mục 7 #6, #7, #10 |
| 02 · PRD (0.2) | Cần sửa; đủ để chạy sprint 1, chưa đủ cho sprint 3 trở đi | FR truy vết spec tốt, AC kiểm được, thứ tự cắt giảm đã được PO duyệt (02 §8). Bản 0.2 đã đưa V3 vào AC 02 · 1.5, thêm 02 · 1.8 cho V6, V7, siết AC 02 · 6.5. Còn thiếu: story xây tuyến generator khi V3 âm, provenance checkpoint, power analysis, A/A test cổng dev; AC 02 · 6.5 không đạt được với 2/5 loại lỗi cấy vì chưa có phép kiểm tương ứng; bảng năng lực 02 §4 vẫn ghi 17 story Simulation trong khi đã có 19 | Mục 7 #1, #5, #8, #9 |
| 03 · Kiến trúc (0.2) | Cần sửa; đủ cho sprint 1–2 nếu cắt về L0-lite | Kiểm nguồn thật, ADR rõ, chống rò nhiều lớp; bản 0.2 đã mở rộng dòng V3 sang correction máy sinh, kiểm khả thi và F1. Nhưng 28 thực thể, 12 module, 7 package là quá sức cho L0; máy 5090 là điểm hỏng đơn lẻ không có backup; RunPlan mẫu §8.1 vẫn trỏ `psi0/simple-checkpoints`; L2 chỉ ghi phép kiểm "skipped" | Mục 7 #8, #9 |
| Spec v10 (tham khảo) | Chưa đạt cho G3–G5 | Mục 1.2 đã sửa (ghi Mulligan, DISEIL). Còn: B không có lượng dữ liệu xác định (7.2, 7.3.5 định nghĩa vòng tròn); CI bỏ phương sai seed (7.5); tỉ lệ sửa được thiên lệch (6.13); 2/5 loại lỗi cấy không có phép kiểm tương ứng (6.4, 7.6); System-0 ghi sai cho task chính (2.1); F1 vẫn là dự phòng cho Q2 (2.4, 10) | Mục 7 #1–#5 trước G2 |

## 2. Phản biện theo chủ đề

### 2.1 Tính mới so với Mulligan, DISEIL, DataMIL, MimicGen, DAgger / HG-DAgger

Bối cảnh đã kiểm: **Mulligan** (Ankile, …, Song, Finn; 10/2026) coi phân phối trạng thái đầu là quyết định, bắt đầu mỗi vòng thu ở trạng thái policy đã lỗi hoặc chưa thử, học value function trên mọi dữ liệu kể cả lỗi; 3 task robot thật, 2 task sim, 2.550 episode held-out mù; thắng lấy mẫu đều ở cùng ngân sách. **DISEIL** (9/2026) đánh dấu bước policy bắt đầu không tin cậy, gom lỗi thành mode, dùng VLM và LLM soạn yêu cầu demo, kiểm khả thi bằng kho ràng buộc trước khi tốn công expert; 5 task sim, 10 setting, thắng ở cả 10 (hòa 1), chênh lớn nhất ở ngân sách demo nhỏ nhất. **IntervenGen** (2024) sinh hàng loạt correction từ khoảng 10 can thiệp của người. **CUPID** (2025) lọc và chọn demo bằng influence function theo ảnh hưởng tới return.

| Mã | Vấn đề | Bằng chứng | Mức | Đề xuất sửa |
|---|---|---|---|---|
| TM1 | HT không còn là điểm khác biệt: "nhắm theo lỗi thắng rải đều cùng ngân sách" đã có kết quả trên robot thật (Mulligan) và trên 10 setting sim (DISEIL) | Spec 1.2 bản sửa đã ghi Mulligan, DISEIL là tiền lệ; nhưng 00 §4 và 01 §2.4 vẫn gọi HT là "điểm khác biệt chính", 01 §10.1 "mất điểm khác biệt chính" nếu HT trượt | Cao | Gọi HT là **kiểm lại (replication) trên humanoid toàn thân với VLA 2,5B, tính đủ chi phí chẩn đoán**. Tách thành HTa "nhắm lỗi có giúp không" và HTb "chẩn đoán có giúp thêm ngoài việc nhắm lỗi không" (TM6) |
| TM2 | Claim "chưa thấy công bố nào ghép đủ chuỗi" quá mạnh và dễ bị giám khảo bắt: DISEIL ghép gom cụm lỗi → yêu cầu demo → kiểm khả thi trước khi tiêu công → đo held-out; RoboLineage ghép lineage và kế hoạch thu tiếp | 01 §1 mục 4; 01 §8.2 dòng cuối ghi "Có" ở cả bốn cột cho L0 | Cao | Viết "trong phạm vi đã tra ngày 22/10/2026"; đổi bốn ô "Có" của L0 thành "Mục tiêu, chưa đo"; ghi rõ DISEIL cũng kiểm khả thi trước khi tốn công |
| TM3 | "Thống kê tỉ lệ sửa được là thứ đối thủ không có" không chứng minh được ở L0: 2 vòng, cập nhật một lần, dùng một lần với 40% ngân sách; thêm thiên lệch ở TH6 | 00 §3 "Đây là thứ đối thủ không có sẵn"; 01 §1 "tài sản quan trọng nhất"; spec 6.11, 6.13 | TB | Gỡ khỏi pitch L0, giữ ở tầm nhìn L1. Muốn có bằng chứng sớm: chạy 5–8 vòng Failure → Data rẻ với ACT trên cùng task (mục 7 #3) |
| TM4 | Bỏ sót tiền lệ gần cho từng can thiệp: dữ liệu phục hồi và correction từ trạng thái lỗi là HG-DAgger cộng IntervenGen; "kiểm demo mâu thuẫn" bằng mắt là phiên bản thủ công của CUPID và DataMIL; Mulligan dùng dữ liệu lỗi làm tín hiệu train còn ta vứt (spec 4.4 "Không được làm mẫu dương") | spec 1.2, 6.10; 01 §8.1 | TB | Thêm IntervenGen và CUPID vào 01 §8.1. Khi Q6 là "không", cân nhắc kiểu IntervenGen thay cho planner sinh từ trạng thái giữa task (DK3). Ghi "dùng dữ liệu lỗi để train" là hướng L1 |
| TM5 | Lớp chọn theo chi phí, phần khác biệt còn lại, đang suy biến. Với g_j = (m_j / 90) × f̄_t và c_j = m_j × q_t × đơn giá_t, tỉ số g_j / c_j = f̄_t / (90 × q_t × đơn giá_t) không phụ thuộc cụm. Vòng 1 mọi f̄_t = 0,5 nên thứ tự chỉ là đơn giá loại can thiệp. Ngoài ra số lượng bị chặn 10 lỗi mỗi cụm (spec 6.10) nhưng g vẫn đếm đủ m_j lỗi, nên cụm lớn được thổi phồng | spec 6.1 mã giả `p.gain`, 6.10, 6.11 | Cao | Tính g theo số lỗi thực được xử lý sau khi chặn; thêm số hạng ưu tiên theo mức nghiêm trọng hoặc theo bước; công khai rằng vòng 1 là "xếp theo đơn giá trong loại được chẩn đoán cho phép". Viết unit test chứng minh tính chất này để không ai bất ngờ |
| TM6 | Thiết kế không đo được phần thật sự mới. B⁺ (spec 7.2) tách "nhiều loại can thiệp" khỏi "nhắm chỗ lỗi", nhưng không tách "chẩn đoán" khỏi "nhắm chỗ lỗi". Đó lại là câu hỏi mà Mulligan và DISEIL để lại | spec 7.2; 01 §8.2: PO đã đưa đối chứng Mulligan ra ngoài 12 tuần, vào backlog L1 | TB | Giữ quyết định của PO cho Ψ₀, nhưng thêm nhánh rẻ **B-fail** trên ACT: sinh sim quanh mọi điều kiện lỗi dev, không chẩn đoán (kiểu Mulligan rút gọn, không cần value function). C so với B-fail mới là bằng chứng cho chuỗi chẩn đoán. Nếu sau G4 còn ngân sách Ψ₀, ưu tiên B-fail hơn B⁺ |

**Claim nên giữ, sửa, bỏ**

| Claim | Nguồn | Quyết định | Viết lại |
|---|---|---|---|
| Không có thuật toán học máy mới; đóng góp là cách ghép và phép đo | spec 1.2 (đã sửa, có Mulligan, DISEIL) | Giữ | Giữ nguyên, đưa lên đầu pitch; chép cùng câu sang 00 §4 và 01 §2.4 |
| Chọn dữ liệu theo lỗi tốt hơn rải đều là điểm khác biệt chính | 00 §4, 01 §2.4 | Bỏ như claim mới | "Kiểm lại kết quả kiểu Mulligan / DISEIL trên G1 toàn thân, có tính chi phí chẩn đoán" |
| Chưa ai ghép đủ chẩn đoán → chọn theo chi phí → đo lại | 01 §1.4, §8.2 | Sửa | "Trong phạm vi đã tra, chưa thấy quy trình kiểm hệ thống trước rồi chọn giữa nhiều loại can thiệp bằng một thước đo tiền và giờ công gồm cả chi phí chẩn đoán" |
| Hệ thống trước, dữ liệu sau | spec 6.9 | Giữ như thực hành kỹ thuật | Chứng minh bằng recall trên bộ lỗi cấy (mục 3), không gọi là mới |
| Khoanh vùng bằng reset về trạng thái chuẩn | spec 6.6 | Giữ, ghi tiền lệ | Ghi Mulligan (trạng thái lỗi), DISEIL (bước không tin cậy), Genie Centurion (tua lại) |
| Tỉ lệ sửa được là tài sản đối thủ không có | 00 §3, 01 §3.4 | Bỏ ở L0 | Chuyển sang tầm nhìn L1, kèm điều kiện đo |
| Bảng khoảng trống ghi "Có" cho L0 | 01 §8.2 | Sửa | "Mục tiêu, chưa đo" |

**Định vị lại đề xuất (một câu cho pitch):** _Humanoid Data Flywheel là quy trình vận hành có kiểm toán cho vòng lỗi → dữ liệu: loại lỗi hệ thống trước khi tiêu tiền vào dữ liệu, chọn giữa nhiều loại can thiệp theo chi phí thật kể cả chi phí chẩn đoán, và xuất ra **khuyến nghị thu dữ liệu định lượng** cho DENSO. PoC kiểm lại trên G1 toàn thân với Ψ₀ xem "nhắm lỗi thắng rải đều" có còn đúng khi tính đủ chi phí._ Cụm "khuyến nghị quy trình thu dữ liệu định lượng" là nguyên văn tiêu chí Cấp 3 của BTC (ảnh `2.jpeg`), và Data Core cộng SOP chính là "DENSO Data Model" mà tên đề yêu cầu. Nên gọi tên hai thứ này đúng như đề.

### 2.2 Tính hợp lệ của thí nghiệm

| Mã | Vấn đề | Bằng chứng | Mức | Đề xuất sửa |
|---|---|---|---|---|
| TH1 | Lượng dữ liệu của B không được định nghĩa: B "tiêu hết B_add", còn B_add là "chi phí thu dữ liệu thực đo của nhánh B". Định nghĩa vòng tròn, nên cả HS lẫn ngân sách của C không xác định | spec 7.2 dòng B; spec 7.3.5; 02 · 5.2 không có số lượng | Cao | Chốt trước G3: N_sim của B (ví dụ bằng 1× hoặc 2× số demo teleop bị cắt) hoặc trần GPU-giờ; ghi vào RunPlan; B_add là chi phí thực đo của lượng đã chốt đó |
| TH2 | CI bỏ phương sai giữa seed huấn luyện: bootstrap chỉ lấy mẫu lại điều kiện sau khi lấy trung bình 3 seed, nên CI nói về 3 checkpoint cụ thể chứ không về quy trình train. Quy tắc "cùng chiều ở ≥ 2/3 seed" gần như luôn đạt vì dấu của trung bình thường trùng đa số | spec 7.5; 02 · 3.7; 03 §6.3 | Cao | Bootstrap phân cấp (lấy mẫu lại seed rồi điều kiện) hoặc mô hình logistic hỗn hợp có hiệu ứng ngẫu nhiên điều kiện và seed. Đo SD giữa seed sớm: chạy 2 seed ở mức D\* trong E1 |
| TH3 | Thiếu lực cho HT. Ước tính thô với p ≈ 0,8, 150 điều kiện, 3 seed: chỉ tính nhiễu điều kiện, SE của chênh lệch ≈ 2,7 điểm, nửa độ rộng CI ≈ 5,2 điểm, hiệu ứng nhỏ nhất phát hiện được với 80% lực ≈ 7,5 điểm. Nếu SD giữa seed là 5 điểm (giả định, cần đo) thì SE ≈ 4,9 điểm và hiệu ứng cần ≈ 13–14 điểm | spec 7.5 chỉ kiểm nửa độ rộng ≤ 7 điểm, không kiểm lực; 02 §8 mục cắt giảm 7 (bản 0.2) cho phép hạ Ψ₀ còn 2 seed, làm lực yếu thêm | Cao | Thêm power analysis ở G2 vào 02 · 3.7; nếu hiệu ứng cần > 10 điểm: tăng Ψ₀ lên 5 seed cho B và C, hoặc chuyển chỉ tiêu chính của HT sang mức có dư địa, hoặc hạ HT thành "mô tả" và nói thẳng. Nếu kích hoạt mục cắt giảm 7 thì HT tự động thành "mô tả" |
| TH4 | C khác B ở nhiều thứ ngoài "nhắm theo lỗi": (a) tăng cường thị giác chỉ C có, áp cho toàn bộ dữ liệu train, tự nó có thể nâng Level 1; (b) correction của người làm C dùng nhiều demo người hơn; (c) "kiểm demo mâu thuẫn" loại demo khỏi C, vi phạm quy tắc cùng danh sách 0,7D\* | spec 6.10, 7.3.3, 7.3.7; 7.2 chỉ nhắc B⁺ | Cao | Cùng chính sách tăng cường cho mọi nhánh (hoặc không nhánh nào); demo bị loại ở C thì B cũng dùng danh sách đã làm sạch, hoặc chỉ hạ trọng số; báo riêng số demo người của từng nhánh |
| TH5 | Chạm trần cộng luật cấm sinh Level 1–2 làm C gần như chỉ nhắm được Level 0. Lỗi Level 2 (vị trí vật) có d > τ_cov nên ra THIẾU VÙNG PHỦ, nhưng can thiệp phải "nằm trong miền train", nên vùng lấy mẫu có thể rỗng. Nếu Ψ₀ ≥ 90% ở Level 0 thì C không còn lỗi để nhắm | spec 2.3 (10/10 ở ba mức cho `BendPickMP`), 4.3, 6.8, 6.10, 7.3.7 | Cao | Thêm luật: lỗi ngoài miền train thì chẩn đoán "NGOÀI MIỀN", không tiêu ngân sách. Báo cáo số lỗi dev theo mức ngay sau G3; nếu < 15 lỗi Level 0, kích hoạt task khó hơn đã khai ở spec 7.1 |
| TH6 | Tỉ lệ sửa được thiên lệch hồi quy về trung bình: điều kiện lỗi ở 1 lượt có xác suất thành công thật p_i; chạy lại không làm gì cũng "sửa được" tỉ lệ p_i. Với policy 70–80%, nhiều lỗi đến từ điều kiện p_i ≈ 0,5, nên f_t sau vòng 1 sẽ quanh 0,5 cho mọi loại, đúng bằng prior. Lại đo trên chính điều kiện đã sinh dữ liệu quanh đó | spec 6.2 (1 lượt), 6.13; định nghĩa đáp án lỗi tự nhiên ở spec 7.6 dùng cùng logic | Cao | Đối chứng: chạy lại policy cha ≥ 3 lượt trên điều kiện lỗi; fixed_j tính bằng chênh lệch ứng viên trừ cha. Đo trên điều kiện mới lấy quanh điểm lỗi, không chỉ chính điểm đó |
| TH7 | Cổng dev nhạy nhiễu: "thành công toàn dev tăng" chấp nhận tăng 1 điều kiện (1,1 điểm); hồi quy ≤ 5% thấp hơn tỉ lệ đổi chiều khi chạy lại cùng một policy | spec 6.12; 03 §8.2 đo tỉ lệ đổi chiều trên 20 điều kiện nhưng không nối vào cổng | TB | A/A test: chạy cha hai lần, lấy tỉ lệ hồi quy giả làm sàn; ≥ 3 lượt mỗi điều kiện ở cổng; ngưỡng "tăng" ≥ 1 SE |
| TH8 | Một tập dev 90 điều kiện được dùng cho chọn D\*, chọn ρ, tìm lỗi, cổng dev và cập nhật tỉ lệ sửa được. Thích nghi theo dev làm cổng thiên về C | spec 4.3, 7.1, 7.3.4, 6.12 | TB | Điều kiện sinh theo hạt giống nên rẻ: mỗi vòng dùng một tập cổng mới, chạy cả cha và ứng viên trên đó |
| TH9 | D\* chọn bằng 1 seed là điểm đầu tiên vượt 80% trên dev, nên dính "winner's curse": A ở holdout dễ tụt dưới 80%. Cùng S cho mọi mức dữ liệu từ 10% đến 100% có thể làm overfit ở mức ít | spec 7.1, 7.3.2 | TB | 2 seed ở hai điểm lưới quanh 80% hoặc nội suy đường cong; hỏi mentor về S (RL4) |
| TH10 | Ngưỡng tự đặt không gắn tiêu chí BTC: 80% so với "≥ 75%" của Cấp 2; biên không kém −10 điểm khó gọi là "cùng hiệu năng"; holdout gộp ba mức trong khi Cấp 3 đòi "≥ 70% trên biến thể chưa train" | spec 3; 01 §5.3; ảnh `2.jpeg` | TB | Thêm bảng map tiêu chí BTC vào 01 §5.3 và spec 3; báo riêng Level 1–2 cho Cấp 3; xin ý mentor về biên (TK3) |
| TH11 | HD nghiêng về card: lỗi cấy hệ thống có chỉ số hiện thẳng trên card (sai số bám lệnh so với ngưỡng); người tham gia là người trong đội; đáp án lỗi tự nhiên dựa vào chính công cụ; "log thô" do đội đóng gói nên dễ thành đối thủ yếu | spec 7.6; 02 · 8.2 "nếu sắp xếp được" | Cao vì kinh tế dựa vào r_debug | ≥ 2 người ngoài đội (mentor, đội khác); đối thủ là công cụ chuẩn (Rerun cộng đồ thị mặc định); chèn 3–4 card sai cố ý để đo mức tin mù quáng; trình bày r_debug là khoảng, không phải điểm |
| TH12 | Nguy cơ checkpoint gốc đã thấy dữ liệu task chính. Thư mục `psi0/` trên HF có `pre.*`, `postpre.*`, `postpre.sonic1.x.unifolm` (post-train có "sonic"), `sonic-checkpoints/multi-task…` và `simple-checkpoints`. RunPlan mẫu của 03 trỏ đúng `simple-checkpoints`. Nếu base đã thấy demo task chính, đường cong E1 vô nghĩa | 03 §8.1 dòng `psi_model`; spec 7.3.1; kiểm HF ngày 22/10/2026 | Cao | Thêm câu Q0 vào G0: chọn checkpoint `pre.*` hoặc `postpre.*` đã xác nhận không chứa dữ liệu SIMPLE hoặc sonic của task chính; hỏi PSI Lab; ghi provenance vào Source |
| TH13 | Guard chống rò chỉ dựa trên seed và `layout_hash`; nếu psi-data không có layout (V6), demo teleop chỉ có vector điều kiện "suy ra", guard không bắt được holdout trùng layout của tác giả | 02 · 2.2 AC2; 03 §8.3; 03 V6 | TB | Thêm guard theo khoảng cách điều kiện (dưới phân vị 1 của khoảng cách láng giềng trong train thì cách ly); chọn dải seed dev và holdout rời với dải seed tác giả dùng cho psi-data và `simple-eval` |
| TH14 | Cổng G0 "lệch không quá 1/10" với 10 lượt: nếu xác suất thật là 0,9, khả năng ra ≤ 8/10 do ngẫu nhiên khoảng 26% | spec 9 dòng G0; 02 · 1.3 | Thấp | 30 lượt mỗi mức hoặc kiểm nhị thức một phía |

### 2.3 Bộ điều khiển teleop và motion planning, hệ quả cho nhánh B và C

| Mã | Vấn đề | Bằng chứng | Mức | Đề xuất sửa |
|---|---|---|---|---|
| DK1 | Spec ghi System-0 của Ψ₀ là AMO và là đối tượng của kiểm tra hệ thống; nhưng task chính chạy `SonicLocoManipEnv`, robot `g1_sonic`, decoupled WBC | spec 2.1 bảng Ψ₀, 6.4 "kiểm cấu hình AMO"; 03 §3.2 dòng "Bộ điều khiển của task chính" | TB | Sửa spec 2.1, 6.4: đối tượng kiểm là stack WBC của env Teleop; định nghĩa lại "lệnh gửi" và "trạng thái đo" theo giao diện WBC (lệnh thân trên, lệnh thân dưới) |
| DK2 | Rollout MP chạy AMO là embodiment khác; ADR-08 cấm trộn trong release. Nếu không có ánh xạ, **nhánh B rỗng** và HS không kiểm được như thiết kế | 03 §3.3 V3, ADR-08, §12.2 dòng đầu; bản 0.2 đã đưa V3 vào AC 5 của 02 · 1.5 và trỏ tới cây phương án ở 04 mục 1.3 | Cao | Hướng đúng. Còn thiếu: hạn trả lời ngày 5 thay vì cuối G0; story 1.5 đang gánh cả Q2, Q3, Q4 và V3 trong 2–5 ngày nên nên tách V3 ra; tuyến được chọn (bảng dưới) cần story xây riêng 1–4 tuần trong kế hoạch |
| DK3 | Bốn đường của C dựa vào planner: kiểm khả thi (bước 5), trạng thái chuẩn cho khoanh vùng (bước 6), sinh sim quanh lỗi (THIẾU VÙNG PHỦ), correction và phục hồi do máy sinh khi không có thiết bị teleop. Planner trong env AMO không chứng minh khả thi dưới WBC; trạng thái sinh dưới AMO không nạp được vào env WBC vì trạng thái nội bộ controller khác. Lập kế hoạch từ trạng thái giữa task (vật đang trong tay, thân đang cúi) cũng khó hơn lập kế hoạch từ layout ban đầu | spec 6.5, 6.6, 6.10; 02 · 7.4 AC2; 03 §6.2 | Cao | Nếu V3 âm và Q6 âm, C chỉ còn tăng cường thị giác và kiểm demo mâu thuẫn; HT sụp. Ghi kịch bản này vào spec 10 và báo cáo |
| DK4 | Task dự phòng F1 nhiều khả năng không chữa V3: theo 03 §3.2 mọi `*Teleop-v0` dùng `g1_sonic` và mọi `*MP-v0` dùng AMO; 03 §3.3 bản 0.2 cũng ghi cặp của F1 "có thể cũng khác bộ điều khiển" | spec 2.3, 2.4 Q2, 10 và 02 · 5.1 AC1 vẫn ghi "hoặc dùng task F1" | Cao | Bỏ F1 khỏi vai trò "dự phòng cho Q2" cho tới khi V3 xác nhận cặp của F1 cùng bộ điều khiển; giữ F1 làm phép thử NFR7 |

**Các tuyến khi V3 âm** (công sức là ước lượng của QA, cần Simulation xác nhận):

| Tuyến | Cách làm | Công sức | Rủi ro | Hệ quả cho claim |
|---|---|---|---|---|
| T1 · Tái thực thi | Lấy quỹ đạo thân trên của rollout MP, suy lệnh thân dưới, chạy lại trong env WBC, giữ lượt thành công | 1–2 tuần | Tỉ lệ sinh đạt có thể rất thấp | Giữ thiết kế; báo tỉ lệ sinh đạt |
| T2 · Biến thể kiểu MimicGen / IntervenGen | Biến đổi đoạn teleop theo tư thế vật, chạy bằng IK cộng WBC trong env Teleop | 2–3 tuần | Cúi người làm phép biến đổi khó hơn tay cố định | "Sim" thành "biến thể của teleop" (spec 4.1 đã cho phép) |
| T3 · Planner trong env WBC | Viết planner cho thân trên cộng lệnh cúi cho WBC | 2–4 tuần | Tốn nhất, mảng Sim chưa có minh chứng | Giữ nguyên thiết kế |
| T4 · Chuyển sang env MP | Lấy task MP làm task chính, coi demo MP là "demo gốc" | Vài ngày | HS thành "sim thay sim", mất ý nghĩa teleop trừ khi tự teleop trong env AMO | Thu hẹp claim rõ ràng |

Khuyến nghị: thử T1 và T2 song song trong tuần 1–2, chốt tuyến cuối tuần 2; T4 là phương án cuối, khai trước trong spec 10.

### 2.4 Tính khả thi 12 tuần với 5 người

| Mã | Vấn đề | Bằng chứng | Mức | Đề xuất sửa |
|---|---|---|---|---|
| KT1 | 52 story × 3,5 ngày ≈ 182 người-ngày trên 210 người-ngày (≈ 87%), không có đệm cho việc chưa biết. Nếu ước lượng lệch 1,5 lần, chuyện thường gặp khi tích hợp lần đầu, nhu cầu ≈ 273 người-ngày | Đếm 52 story trong 02 §6 bản 0.2 (Data-Platform 22, Simulation 19 kể cả 7.9 tùy chọn, Robot Learning 11); bảng 02 §4 vẫn ghi Simulation 17 | Cao | Lập kế hoạch ở mức 70% năng lực; chuyển 02 §8 thứ tự cắt giảm thành phạm vi mặc định (B⁺ và vòng 2 là "thưởng") |
| KT2 | Trưởng nhóm giữ 11 story Robot Learning ≈ 39 người-ngày trên khoảng 42 người-ngày khả dụng, chưa tính đầu mối DENSO, pitch, duyệt card. Các story này nằm trên đường găng của G0 (1.3, 1.4), G1 (3.5), G2 (4.2, 4.4), G3 (5.3), G4 (3.6, 7.6, 7.7, 8.2), G6 (8.4). Chỉ một người biết Ψ₀ | 02 §4, §6; 02 §9 "theo dõi tải" | Cao | Một thành viên Simulation đồng sở hữu Ψ₀ (train, serve) từ tuần 2; chuyển đầu mối DENSO và pitch hằng tuần cho Data-Platform #2; mảng Simulation vẫn nhẹ nhất (19 story ≈ 66 trên 84 người-ngày). Phân công thực tế ở 04 mục 3, 4; Châu đồng sở hữu Ψ₀ từ tuần 1 |
| KT3 | Đường găng tuần 9–10 không vừa: mỗi vòng C gồm 90 rollout, chẩn đoán, thu và QA, fine-tune Ψ₀ (ước 10–20 giờ A100, cần đo), cổng 90 rollout, nên khoảng 4–5 ngày; hai vòng ≈ 10 ngày, rồi C cuối 3 seed mới bắt đầu, đụng holdout tuần 11 | spec 9; 02 · 7.6, 7.7 | Cao | Kế hoạch mặc định 1 vòng Ψ₀; nhiều vòng chạy trên ACT (mục 7 #3); chạy holdout sớm cho các nhánh không phụ thuộc C và niêm phong kết quả (03 §8.3 đã cho mỗi cặp nhánh, seed chạy một lần) |
| KT4 | GPU: khoảng 21–25 lần fine-tune Ψ₀ (spec 9) cần ≥ 2 A100 song song ở tuần 7–8 (11 lần train trong 2 tuần); 22 lần train ACT và DP trên RTX 3060 có thể mất 1–2 tuần máy; RTX 5090 (Blackwell) chạy Isaac Sim 4.5 và `flash_attn==2.7.4.post1` chưa được kiểm | spec 9 "Khối lượng dự kiến"; 03 §2.1, §3.2 | TB đến Cao | Xin ngân sách thuê GPU ngay tuần 1; thử cài trên 5090 trong 3 ngày đầu; có phương án chạy sim trên GPU thuê |
| KT5 | Thông lượng rollout: QA ước khoảng 9.000–11.000 episode (E1 1.350; dev các nhánh ≈ 1.900; vòng C ≈ 1.400 gồm chẩn đoán; holdout 3.600; cộng sinh sim cho B và C), cao hơn 6.000–8.000 của 03. Với t = 60 s, W = 3 là ≈ 55 giờ máy; với t = 120 s, W = 2 là ≈ 170 giờ, trong đó holdout ≈ 60 giờ, trên một máy 5090 dùng chung với server Ψ₀ | 03 §9.2; 02 NFR8 | TB | Đo t và W thật ở G0; chính sách camera ở dev; lịch máy cố định cho tuần 11 |
| KT6 | Story bị ước nhỏ hoặc thiếu: 02 · 3.1 (adapter SIMPLE và Ψ₀ kèm hook ghi tín hiệu từng bước trong client đánh giá), 02 · 5.1 (generator nếu V3 âm), 02 · 6.4 (khôi phục trạng thái WBC), 02 · 1.5 (nay gánh Q2, Q3, Q4 và V3) khó vừa 2–5 ngày; vẫn chưa có story xây tuyến generator khi V3 âm, provenance checkpoint, power analysis, A/A test cổng dev, backup | 02 §6 bản 0.2 | TB | Thêm 5 story trên; tách 3.1 thành worker, hook tín hiệu, contract test; tách V3 khỏi 1.5 |

### 2.5 Kiến trúc: quá sức cho L0, thiếu cho L1–L3, điểm hỏng đơn lẻ

| Mã | Vấn đề | Bằng chứng | Mức | Đề xuất sửa |
|---|---|---|---|---|
| AR1 | Quá sức cho L0: 28 loại thực thể, 12 module, 7 package, Pydantic cộng xuất JSON Schema, Parquet append-only phân vùng ngày, chỉ mục DuckDB dựng lại, fsspec sẵn S3, MLflow, Streamlit, `refs/` có log, vault có đối tượng `HoldoutAccess`. Đội Data-Platform 2 người chưa có minh chứng (00 §5.5) | 03 §3.1, §4.3, §7.1 | Cao cho lịch | **L0-lite:** giữ hash release và RunPlan, guard split, khóa holdout dạng tệp có hash cộng test CI, ledger JSONL, trace Parquet, một chỉ mục DuckDB (02 bản 0.2 đã chốt) nhưng chưa cần phân vùng ngày và lệnh dựng lại. Hoãn MLflow (trùng ledger), Streamlit (02 §8 mục cắt giảm 2 đã cho phép), fsspec S3, `site_id`, revision card. Gộp 28 thực thể còn khoảng 12 ở L0, giữ trường mở rộng trong `meta` |
| AR2 | ADR-03 lưu bundle theo episode rồi export LeRobot cho mỗi lần train: thêm một chỗ có thể làm sai dữ liệu train (thứ tự khung, fps, chuẩn hóa, khóa quan sát) mà không ai thấy | 03 ADR-03, §9.2 "Export LeRobot" | TB | Contract test bắt buộc: export rồi đọc lại bằng loader của Ψ₀, so từng tensor với bundle; cân nhắc giữ LeRobot gốc và release là danh sách chỉ số episode nếu loader Ψ₀ hỗ trợ lọc |
| AR3 | Điểm hỏng đơn lẻ phần cứng: máy 5090 chạy catalog, container SIMPLE, server Ψ₀, MLflow; không có chính sách backup `fwdata/`; A100 thuê đơn lẻ | 03 §2.1, §7.2 | TB | Backup hằng ngày `catalog/`, `releases/`, `vault/`, ledger sang máy 3060 và một kho ngoài; diễn tập khôi phục một lần trước G3 |
| AR4 | Điểm hỏng đơn lẻ logic: scorer quyết định nhãn lỗi, cụm, cổng dev và cả "thành công" ở holdout. Spec 7.5 không nói chỉ số chính lấy từ scorer hay cờ SIMPLE | spec 5.3, 7.5; 03 §6.3 "SCO-->>GAT thành công" | TB | Chỉ số chính ở holdout là cờ `check_success` của SIMPLE (so được với số công bố); scorer chỉ dùng cho chỉ số theo bước |
| AR5 | Thiếu cho L1: tỉ lệ sửa được khóa theo kiểu lỗi lấy từ TaskDefinition, nên không gộp được giữa task. Cần ontology lỗi chung (tiếp cận, gắp, mang, đặt, thăng bằng) | 03 §4.3 FixRateEvent; 02 NFR7 | TB | Thêm trường "lớp lỗi chung" trong FailureKindSpec ngay từ L0 (rẻ) |
| AR6 | Thiếu cho L2: robot thật không khôi phục trạng thái, không đổi hình ảnh, không có planner làm oracle, mỗi lần reset tốn phút người; vòng lặp ở nhà máy chạy trên log sản xuất không có hạt giống điều kiện. 03 chỉ ghi phép kiểm 6, 7 "tự skipped", tức lõi suy biến còn hai phép kiểm | 03 §9.1 dòng L2; 01 §7 | TB (tương lai, nhưng pitch có claim) | Ghi rõ trong pitch: L0 không chứng minh chẩn đoán trên robot thật. Phác thiết kế L2: người đưa robot về đầu bước k, tiếp quản kiểu Genie Centurion, vector điều kiện đo bằng perception kèm độ bất định, chia tập theo phiên làm việc |
| AR7 | Lệch giữa 02 và 03 phần lớn đã sửa ở bản 0.2 (CLI `fw`, cây `packages/`, DuckDB, mã tính năng brief thành TN1–TN10). Còn sót: 02 §9 "Gửi Architect" mục 2 vẫn nhắc SQLite; bảng năng lực 02 §4 chưa cập nhật số story | 02 §1.3 change log, §4, §9 | Thấp | PO sửa hai chỗ sót |

### 2.6 Kinh tế và giá trị cho DENSO

Công thức hiện hành: lợi ích ròng/đợt = 500 × r_demo + 400 × r_debug − 181,80 USD (spec 8.2).

| Mã | Vấn đề | Bằng chứng | Mức | Đề xuất sửa |
|---|---|---|---|---|
| KD1 | Công thức không có số hạng nào cho HT: r_demo đến từ HS (sim), r_debug đến từ HD. Lõi sản phẩm (chọn theo lỗi) không đóng góp đô-la nào trong mô hình | spec 8.2, 8.3 | Cao | Thêm chỉ số "chi phí mỗi điểm % tăng thêm" của C so với B và B-fail, và "số demo người để đạt ngưỡng" theo nhánh |
| KD2 | Giả định yếu nhất là r_debug = 50%: chỉ đo bằng HD (TH11). Hòa vốn khi r_demo = 30% là r_debug ≈ 8% ((181,80 − 150) / 400), nên kết luận "có lãi" gần như chắc chắn từ bất kỳ HD nào, dù yếu. Giám khảo sẽ thấy điều đó | spec 8.2 bảng độ nhạy | Cao | Báo r_debug là khoảng; trình bày kinh tế theo giờ người và số ngày, không theo đô-la |
| KD3 | Theo đơn giá của chính pitch, phương án sim tốn $181,80 để thay $150 teleop. Đơn giá operator $10/h bỏ qua chi phí robot, cell, người giám sát và thời gian dừng dây chuyền, vốn mới là chi phí lớn ở nhà máy | spec 8.1, 8.2; 01 §9.2 A2 | TB | Hỏi DENSO chi phí giờ cell (DN3); thêm bảng độ nhạy theo chi phí giờ cell |
| KD4 | Quy mô: 144 đợt × $168,20 ≈ $24.200 mỗi năm, nhỏ hơn chi phí xây và duy trì nền tảng. Số đợt chưa có cơ sở | 01 §2.4, §9.2 A3 | TB | Thôi dẫn bằng đô-la/năm; dẫn bằng "số ngày đưa kỹ năng trở lại ngưỡng" |
| KD5 | "Cùng ngân sách USD" giữa B và C phụ thuộc bảng giá: đổi tỉ giá giữa giờ operator và GPU-giờ thì C mua được tổ hợp khác, nên kết luận HT phụ thuộc đơn giá | spec 7.3.5, 6.11 | TB | Báo HT kèm hai ràng buộc riêng (phút người, GPU-giờ) và bảng độ nhạy theo đơn giá |
| KD6 | Chưa trả lời hai nỗi đau BTC nêu: "mỗi kỹ năng mới lại phải thu thập dữ liệu lại từ đầu" và "mô hình thu thập dữ liệu DENSO". L0 xếp tái dùng giữa kỹ năng vào L1. Đề cũng ghi DENSO sẽ cung cấp mô tả kỹ năng, video, layout trạm, nhưng 01 §6.2 coi task DENSO là ngoài phạm vi | ảnh `1.jpeg` mục "Vấn đề" và "Dữ liệu DENSO cần cung cấp"; 01 §6.2 | TB | Xin layout trạm và mô tả kỹ năng ngay; dùng layout để đặt khoảng của vector điều kiện (chiều cao bàn, vị trí khay) cho task SIMPLE; trình bày Data Core cộng SOP là "DENSO Data Model" |

**Chỉ số thuyết phục hơn đô-la**, đều lấy được từ ledger và báo cáo hiện có:

1. Số demo người để đạt 75% và 80% theo phương pháp và theo nhánh (Cấp 2 của BTC).
2. Tỉ lệ thành công trên Level 1–2 holdout (Cấp 3: ≥ 70% trên biến thể chưa train).
3. Phút operator và GPU-giờ cho mỗi điểm % tăng thêm, theo loại can thiệp.
4. Số giờ thu dữ liệu tránh được nhờ bắt lỗi hệ thống trước (lỗi cấy và phiếu sửa thật).
5. Sai số dự báo chi phí: ledger đã tách "ước tính" và "thực đo" (03 §1.2), tính được sai số phần trăm của ước tính cho từng can thiệp. Đây là phép đo trực tiếp cho lời hứa "biết trước một lần cải thiện tốn bao nhiêu".
6. Số ngày từ khi đổi điều kiện đến khi policy đạt ngưỡng lại (spec 8.3 đã nêu).

### 2.7 Sim-to-real và quyền dữ liệu

| Mã | Vấn đề | Bằng chứng | Mức | Đề xuất sửa |
|---|---|---|---|---|
| SR1 | Dữ liệu sim cùng phân phối với môi trường test nên lợi ích của HS bị phóng đại; spec đã nêu nhưng không có cách ước lượng mức phóng đại | spec 1.2, 01 §9.1 dòng "Phân phối sim" | TB | Thêm biến thể rẻ "sim lệch": sinh dữ liệu B với tham số vật lý và hình ảnh lệch có chủ đích (ma sát, khối lượng, bộ texture rời với test), đo lợi ích còn lại. Làm trên ACT nếu thiếu ngân sách Ψ₀ |
| SR2 | Giá trị chẩn đoán trên robot thật chưa được chứng minh: ba phép kiểm mạnh nhất (khả thi, khoanh vùng, thị giác) dựa vào khả năng chỉ sim có | spec 6.5–6.7; 03 §9.1 | TB | Nói thẳng trong pitch; đặt cổng L2 riêng có phép đo "mode lỗi chẩn đoán trong sim có khớp mode lỗi trên cell thật không" |
| SR3 | psi-data và trọng số Ψ₀ không khai giấy phép, mặc nhiên là giữ mọi quyền; checkpoint fine-tune là sản phẩm phái sinh; mã Ψ₀ Apache 2.0 không phủ trọng số | 01 §9.1; 03 §3.2, §10.3 | TB | Email PSI Lab tuần 1 xin xác nhận bằng văn bản phạm vi dùng; bàn giao cho DENSO chỉ gồm SOP, báo cáo, mã của đội; dataset và checkpoint ghi là "chỉ nghiên cứu" |
| SR4 | Tài sản cảnh: HSSD (03 ghi theo hiểu biết hiện tại là CC BY-NC 4.0) và Objaverse (giấy phép theo từng vật) có thể lan sang mọi rollout sim render từ chúng | 03 §10.3 | TB | Liệt kê tài sản task chính thật sự dùng; lan truyền giấy phép đã có trong 03 §10.3, cần test |
| SR5 | Video công nhân DENSO qua V2D (sau PoC) là dữ liệu cá nhân, chịu Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân và quy định nội bộ DENSO | spec 1.1 dòng "Sau PoC"; 01 §10.2 câu 4 | Thấp ở L0 | Ghi yêu cầu đồng thuận, làm mờ mặt, lưu tại site vào backlog L2 |
| SR6 | Chưa rõ điều khoản sở hữu trí tuệ của cuộc thi với mã và kết quả | Không tài liệu nào nhắc | Thấp | Hỏi BTC trước G6 |

## 3. Chiến lược kiểm thử cho lõi

Nguyên tắc: kết quả flywheel chỉ đáng tin khi từng mắt xích đã được kiểm trên ca **biết đáp án**, và người thiết kế ca kiểm **không phải** người viết phép kiểm (red team trong đội: một thành viên Data-Platform cấy lỗi cho mảng Simulation và ngược lại). Kiểm trên `FakeSim2D` (03 §11) là cần nhưng chưa đủ: lỗi cấy trong bộ giả được thiết kế khớp phép kiểm nên dễ thành kiểm tra lặp lại chính nó.

| Thành phần | Phải kiểm gì | Cách kiểm | Tiêu chí đạt | Khi |
|---|---|---|---|---|
| Scorer | Kết luận toàn task, bước hỏng đầu tiên, quy ước "chưa thử" và "chưa rõ" | Tập hiệu chỉnh và tập kiểm tách riêng (tránh đạt 95% trong mẫu đã chỉnh); mẫu cân bằng thành công và thất bại; nhãn bước hỏng do 2 người gán độc lập | Trùng cờ SIMPLE ≥ 95% trên tập kiểm; độ nhạy với thất bại ≥ 90% (không đạt nhờ tỉ lệ nền); kappa giữa hai người gán ≥ 0,7 | G1 |
| Scorer, biến đổi | Bất biến khi dịch thời gian, đổi đơn vị tại biên, mất 1 khung | Test metamorphic bằng hypothesis | Không đổi kết luận | G1 |
| Chẩn đoán | Recall theo từng lớp, báo động giả khi không có lỗi, thứ tự kiểm | Bộ lỗi cấy chuẩn bên dưới, có liều; đối chứng sạch | Lớp hệ thống: recall ≥ 0,8 mỗi lớp; lớp dữ liệu: ≥ 0,6; báo động hệ thống giả trên ca sạch ≤ 5%; lỗi kép luôn ra lớp hệ thống | Bộ giả G1; SIMPLE trước G4 |
| Khoanh vùng | Độ trung thực của khôi phục trạng thái | So quỹ đạo khôi phục rồi chạy tiếp với quỹ đạo liền (03 V4); đo độ lệch tư thế vật sau 1 giây | Lệch dưới ngưỡng khai trong RunPlan; nếu không, cờ `restore_state` phải là False | G0–G1 |
| Kiểm thị giác | Đổi hình ảnh mà giữ vật lý | So trạng thái vật lý từng bước với và không có `VisualOverride` | Trùng tới sai số số học | G1 |
| Chọn can thiệp | Không vượt ngân sách; tính đúng g, c sau khi chặn số lượng; tính chất suy biến ở TM5 được ghi | Unit test với ví dụ tính tay; property test; mô phỏng trên bộ giả có đáp án: Failure → Data phải thắng rải đều trong thế giới được thiết kế để nó thắng | Đạt cả ba; nếu không thắng được trên bộ giả thì dừng trước khi tốn GPU cho Ψ₀ | G2 |
| Tỉ lệ sửa được và cổng dev | Thiên lệch hồi quy về trung bình; tỉ lệ từ chối nhầm | A/A test: cùng checkpoint làm cả cha và ứng viên; đối chứng chạy lại cha | Cổng A/A từ chối hoặc chấp nhận nhầm ≤ 10%; f_t của can thiệp "rỗng" có CI chứa 0 | G3 |
| Ledger | Bất biến tổng; không job nào thiếu mục sổ; ước tính và thực đo tách riêng; bút toán đảo | Property test; đối chiếu GPU-giờ với hóa đơn nhà cung cấp và với giờ tường của job | Lệch với hóa đơn ≤ 5%; B_add tính lại từ mục thô ra cùng số | G1, G3 |
| Thống kê | Độ phủ CI; phương sai seed; lực | Mô phỏng 1.000 bộ dữ liệu có hiệu ứng biết trước gồm cả hiệu ứng seed (03 §11 chưa có phần seed); A/A ở mức nhánh | Độ phủ 93–97% khi có phương sai seed; báo cáo hiệu ứng nhỏ nhất phát hiện được | G2 |
| Lineage và chống rò | Không điều kiện dev hoặc holdout nào lọt vào release; checkpoint gốc sạch | Canary: cố ý đưa 1 episode mang seed holdout và 1 episode gần trùng layout holdout vào bản nháp, release phải từ chối; mutation test cho mã guard; truy vấn kiểm toán ở 03 §8.3.7 chạy trong CI | 100% canary bị chặn; provenance checkpoint có văn bản | G1, G5 |
| Quy tắc công bằng | TrainSpec của các nhánh chỉ khác nhau ở release | So khác biệt giữa các TrainSpec đã đóng băng | Chỉ trường `release_id` khác | G3 |
| Báo cáo | Mọi con số trỏ về run nguồn | Test quét báo cáo, mỗi số có ID | 0 số không nguồn | G6 |

**Bộ lỗi cấy chuẩn.** Mỗi loại cấy ở ít nhất 2 liều, ≥ 5 episode mỗi liều trên bộ giả; trên SIMPLE lấy tập con khoảng 30 episode. Đáp án khóa trước khi chạy.

| Mã | Lớp kỳ vọng | Cách cấy | Liều gợi ý | Ghi chú |
|---|---|---|---|---|
| F-SIG | CHƯA RÕ | Bỏ ngẫu nhiên khung camera; để trống cột tiếp xúc | 10%, 50% khung | Kiểm scorer trả "chưa rõ", không trả "trượt" |
| F-CTL1 | LỖI CONTROLLER | Lệch cố định trên 1–2 khớp cổ tay | 0,05 và 0,15 rad | Đã có trong spec 7.6 |
| F-CTL2 | LỖI CONTROLLER | Giảm hệ số PD hoặc đổi ánh xạ hai khớp ngón | ×0,5; đổi chỗ | Lỗi khó thấy bằng mắt |
| F-RT | LỖI RUNTIME | Chèn trễ suy luận; bỏ chunk hành động | +100 ms, +300 ms; bỏ 10% chunk | Phép kiểm độ trễ hiện chỉ đo suy luận |
| F-CAMLAG | Hiện **không có lớp**: phép kiểm 6.4 đo độ trễ suy luận, không đo lệch thời gian ảnh so với state | Trễ khung camera | 2 và 5 khung | Trong 5 loại của spec 7.6; cần thêm phép kiểm "đồng bộ cảm biến" (QA 4.4 đã có cho dữ liệu, chẩn đoán chưa có). AC 3 của 02 · 6.5 bản 0.2 cấm lỗi hệ thống bị xếp vào lớp dữ liệu, nên không thể đạt nếu thiếu phép kiểm này |
| F-CALIB | Hiện **không có lớp**: kiểm thị giác chỉ đổi ánh sáng và vật liệu, không đổi tư thế camera | Lệch ngoại tham số camera | 2 cm và 3°; 5 cm và 5° | Trong 5 loại của spec 7.6; thêm phép kiểm "camera chuẩn" hoặc bỏ khỏi HD |
| F-INF | KHÔNG KHẢ THI | Vật ngoài tầm với; vật cản cố định chắn đường | 2 vị trí | Kiểm planner thất bại thật sự, không phải planner lỗi |
| F-STATE | TRẠNG THÁI ĐẦU XẤU | Đẩy vật lệch trong tay hoặc nghiêng thân ở cuối bước k−1 | 2 biên độ | Từ trạng thái chuẩn ở đầu bước k policy phải làm được |
| F-VIS | NHẬN THỨC | Ánh sáng Level 1; đổi texture vật đích; vật gây nhiễu cùng màu | 2 mức | Chỉ Level 1–2 theo spec 6.7 |
| F-HOLE | THIẾU VÙNG PHỦ | Train bỏ một vùng điều kiện (ví dụ x vật vượt ngưỡng) | Lỗ nhỏ và lỗ lớn | Đã có trong spec 7.6 |
| F-SKILL | KỸ NĂNG YẾU | Làm hỏng 30% demo trong một vùng; hoặc trộn hai kiểu gắp mâu thuẫn | 15%, 30% | Kiểm "kiểm demo mâu thuẫn" có tìm ra demo hỏng |
| F-DOUBLE | Lớp hệ thống | Lệch controller cộng lỗ vùng phủ | Một liều | Kiểm thứ tự "hệ thống trước" |
| F-NOVEL | Không thuộc lớp nào | Ma sát vật thấp làm trượt | Một liều | Đo hệ thống trả CHƯA RÕ hay gán bừa |
| F-NULL | Không lớp hệ thống | Không cấy gì | Không có | Đo báo động giả |

## 4. Pre-mortem: "Tuần 12, dự án thất bại. Vì sao?"

| Mã | Kịch bản | Dấu hiệu sớm | Cách chặn từ bây giờ |
|---|---|---|---|
| PM1 | **Bộ điều khiển chặn nhánh B và C.** Tuần 4 mới xác nhận V3 âm; generator thay thế mất 4 tuần; B và C xong tuần 11; holdout chạy vội, không có C | V3 chưa có câu trả lời ngày 5; replay rollout MP trong env Teleop thất bại | Spike V3 ngày 1–5 có người phụ trách; chốt tuyến T1–T4 cuối tuần 2 (mục 2.3) |
| PM2 | **Trần và nhiễu nuốt hiệu ứng.** Ψ₀ ở 10% dữ liệu đã 88–92%; dev chỉ có 9 lỗi; CI của C − B là ±10 điểm; báo cáo cuối "không kết luận được" cho cả HS và HT | Đường E1 phẳng ở G2; < 15 lỗi Level 0 sau G3; hai seed ở D\* lệch > 5 điểm | Luật đổi task khai trước; power analysis ở G2; ACT và DP làm phép thử nhạy hơn |
| PM3 | **Ψ₀ không train được đúng hạn.** Lỗi flash-attn trên 5090; mỗi fine-tune 20 giờ A100; chỉ thuê được 1 GPU; tuần 8 mới xong A, A₀.₇, B | Tuần 2 chưa có lần fine-tune ngắn nào xong; GPU-giờ mỗi lần > 15 | Ngân sách GPU duyệt tuần 1; đường LoRA hoặc đóng băng VLM sẵn; giảm ô Ψ₀ trong ma trận nếu cần |
| PM4 | **Nền tảng ăn hết thời gian.** Tuần 8 có catalog đẹp, 28 thực thể, nhưng chưa có trace SIMPLE nào qua scorer; chẩn đoán chỉ chạy trên bộ giả | Tuần 4 chưa có một trace thật đi trọn import → scorer | Lát dọc (walking skeleton) trên SIMPLE trước tuần 4; L0-lite (AR1) |
| PM5 | **Trưởng nhóm thắt cổ chai.** Ốm 1 tuần ở tuần 7; mọi việc Ψ₀ dừng; buổi gặp DENSO bị hoãn | Story Robot Learning trễ > 3 ngày; card chờ duyệt tồn > 2 ngày | Đồng sở hữu Ψ₀ từ tuần 2; tài liệu chạy lại train và serve; giao việc đầu mối DENSO |
| PM6 | **Chẩn đoán sai mà không ai biết.** Trễ camera bị gán KỸ NĂNG YẾU; C mua dữ liệu sai chỗ; HD cho thấy card nhanh hơn nhưng sai; giám khảo hỏi đúng chỗ này | Recall lỗi cấy theo lớp thấp; tỉ lệ ghi đè > 50%; nhiều cụm hòa phiếu | Bộ lỗi cấy chuẩn (mục 3), nghiệm thu theo lớp trước G4; thêm phép kiểm đồng bộ cảm biến |
| PM7 | **Kết quả bị vô hiệu vì dữ liệu.** Giám khảo chỉ ra checkpoint gốc đã post-train trên dữ liệu sonic có task chính; hoặc PSI Lab không cho dùng psi-data ngoài nghiên cứu | Ψ₀ ở 10% dữ liệu cao bất thường; email PSI Lab không được trả lời sau 2 tuần | Provenance checkpoint ở G0; email tác giả tuần 1; ghi giới hạn trong báo cáo |
| PM8 | **"Không mới, không phải của DENSO."** Mentor và giám khảo dẫn Mulligan, DISEIL; kinh tế có lãi chỉ nhờ r_debug tự đo; DENSO không thấy kỹ năng của mình | Phản hồi mentor ở buổi đầu; DENSO chưa gửi mô tả kỹ năng, layout ở tuần 4 | Định vị lại (mục 2.1); map tiêu chí BTC; dùng layout DENSO cho vector điều kiện |
| PM9 | **Hai robot, nửa kết quả (bản 0.3).** Tuần 12 có pipeline đẹp và robot thay thế trong Isaac Sim, nhưng Ψ₀ trên robot DENSO chưa đủ tốt để có lỗi có nghĩa; G1 thì thiếu nhánh vì người đã dồn sang robot DENSO; không giả thuyết nào kết luận được | Cuối G2 chưa có episode robot thay thế nào chạy trọn task; k sau Sprint 1 > 1,2; Hưng và Long trễ cùng lúc | Giữ G1 là đường tới HS, HT, HD; robot DENSO đo theo MT8 chứ không gánh giả thuyết; chuyển phần trễ sang API sớm (04 mục 4.9); review G2 quyết dừng hay giữ nhánh nào |

## 5. Sổ rủi ro

Khả năng và tác động: Thấp, TB, Cao. Mảng phụ trách theo 02 §4; người giữ từng rủi ro ở 04 mục 8.

| Mã | Rủi ro | Khả năng | Tác động | Dấu hiệu sớm | Cách giảm | Phụ trách |
|---|---|---|---|---|---|---|
| R01 | Teleop (WBC) và MP (AMO) không tương thích, B và C mất dữ liệu sinh | Cao | Cao | V3 chưa trả lời ngày 5 | Spike V3; tuyến T1–T4; khai trong spec 10 | Simulation |
| R02 | Checkpoint gốc Ψ₀ đã thấy dữ liệu task chính | TB | Cao | Hiệu năng ở 10% dữ liệu cao bất thường | Chọn checkpoint `pre.*` hoặc `postpre.*` có provenance; hỏi PSI Lab | Robot Learning |
| R03 | Chạm trần ở Level 0, C không có lỗi để nhắm | Cao | Cao | A₀.₇ ≥ 90% trên dev | Luật đổi task; báo lỗi theo mức sau G3 | Robot Learning |
| R04 | Thiếu lực thống kê, phương sai seed lớn | Cao | Cao | Hai seed ở D\* lệch > 5 điểm | Bootstrap phân cấp; power analysis; thêm seed hoặc bớt nhánh | Data-Platform |
| R05 | Ψ₀ không chạy trên 5090 hoặc fine-tune quá đắt, quá lâu | TB | Cao | Lỗi CUDA, flash-attn ngày 1–3 | Thuê GPU sớm; LoRA; giảm ô Ψ₀ | Robot Learning |
| R06 | Trưởng nhóm quá tải, Ψ₀ chỉ một người biết | Cao | Cao | Story trễ > 3 ngày | Đồng sở hữu; giao bớt đầu mối DENSO | Trưởng nhóm |
| R07 | Xây nền tảng quá rộng, trễ trace thật | Cao | Cao | Tuần 4 chưa có trace SIMPLE | L0-lite; lát dọc | Data-Platform |
| R08 | Chẩn đoán sai có hệ thống (thiếu phép kiểm trễ camera, calibration) | Cao | TB | Recall lỗi cấy theo lớp thấp | Thêm phép kiểm; bộ lỗi cấy chuẩn | Simulation |
| R09 | Tỉ lệ sửa được và cổng dev bị nhiễu | Cao | TB | A/A test từ chối nhầm > 10% | Đối chứng chạy lại cha; ≥ 3 lượt mỗi điều kiện | Data-Platform |
| R10 | Rò holdout hoặc gần trùng layout | Thấp | Cao | Canary lọt guard | Guard khoảng cách; dải seed rời với tác giả | Data-Platform |
| R11 | Nhiễu can thiệp làm C − B không diễn giải được | Cao | TB | C dùng tăng cường thị giác, loại demo | Chính sách tăng cường chung; B-fail; báo tách | Robot Learning |
| R12 | Không có thiết bị teleop, planner không sinh được từ trạng thái giữa task | Cao | TB | Q6 âm; planner thất bại từ trạng thái lưu | Sinh kiểu IntervenGen; thu hẹp loại can thiệp | Simulation |
| R13 | HD bị coi là thiên lệch, r_debug không được tin | Cao | TB | Không có người ngoài đội tham gia | Người ngoài; card sai cố ý; trình bày khoảng | Robot Learning |
| R14 | Giấy phép psi-data, trọng số Ψ₀, HSSD chặn bàn giao | TB | TB | Không có trả lời của PSI Lab | Email tuần 1; ranh giới bàn giao | Trưởng nhóm |
| R15 | Thông lượng rollout không đủ cho holdout tuần 11 | TB | Cao | t > 90 s hoặc W < 3 ở G0 | Holdout sớm, niêm phong; thuê máy sim tuần 11 | Simulation |
| R16 | Máy 5090 hỏng hoặc mất `fwdata/` | Thấp | Cao | Không có bản backup nào | Backup hằng ngày; diễn tập khôi phục | Data-Platform |
| R17 | Không map tiêu chí 3 cấp và nhầm mã đề (H1 hay H2) | TB | TB | Pitch vẫn dùng ngưỡng tự đặt | Bảng map; xác nhận với BTC | Trưởng nhóm |
| R18 | DENSO chưa xác nhận kỹ năng, layout, task owner | TB | TB | Tuần 4 chưa có tài liệu DENSO | Gửi yêu cầu theo đúng mục "Dữ liệu DENSO cần cung cấp" của đề | Trưởng nhóm |

## 6. Câu hỏi cho mentor

Sprint theo 02 §9 và 04 mục 2.1: S1 = tuần 1–2 (G0), S2 = tuần 3–4 (G1), S3 = tuần 5–6 (G2), S4 = tuần 7–8 (G3), S5 = tuần 9–10 (G4), S6 = tuần 11–12 (G5–G6). S0 là trước sprint 1. **[Chặn]** là câu mà một quyết định đang chờ. Lịch hỏi từng câu ở 04 mục 6; câu đã chốt theo 06 (RL7, DS1, DS5, DS6, TK1, TK8) chỉ còn để mentor xác nhận.

### 6.1 Robot learning / VLA

| Mã | Câu hỏi | Vì sao quan trọng | Quyết định phụ thuộc | Sprint |
|---|---|---|---|---|
| RL1 | **[Chặn]** Trong `psi0/` có `pre.*`, `postpre.*`, `postpre.sonic1.x`, `sonic-checkpoints`, `simple-checkpoints`. Checkpoint nào là "base" hợp lệ để vẽ đường cong dữ liệu, và làm sao biết nó chưa thấy demo task chính? Mentor có liên hệ được PSI Lab không? | Base đã thấy dữ liệu làm E1 và mọi nhánh vô nghĩa (TH12) | Checkpoint gốc ghi trong RunPlan; có đổi task không | S0–S1 |
| RL2 | **[Chặn]** Với Teleop chạy decoupled WBC và MP chạy AMO, tuyến nào nhanh nhất để có dữ liệu sinh cùng embodiment: tái thực thi, biến thể kiểu MimicGen hoặc IntervenGen, planner trong env WBC, hay chuyển sang env MP? | Quyết định nhánh B và C có tồn tại không (mục 2.3) | Chọn T1–T4; phân công Simulation | S1 |
| RL3 | Ở 15–50 demo, full fine-tune và LoRA hoặc đóng băng VLM của Ψ₀ khác nhau bao nhiêu? Kết quả so sánh nhánh có đổi chiều theo cấu hình không? | Quyết định phần cứng và ngân sách thuê | Cấu hình train chung cho mọi nhánh | S1 |
| RL4 | Giữ cùng số bước S cho mọi mức dữ liệu từ 10% đến 100% có làm méo đường cong không? Nên cùng S, cùng số epoch hay dừng sớm theo dev? | Quy tắc công bằng spec 7.3.2 và tính hợp lệ của D\* | Sửa spec 7.1, 7.3 | S2 |
| RL5 | Với VLA cỡ 2,5B fine-tune ít dữ liệu, độ lệch thành công giữa các seed thường bao nhiêu điểm %? 3 seed có đủ? | Đầu vào trực tiếp cho power analysis (TH3) | Số seed; giữ hay bỏ nhánh | S2 |
| RL6 | Trộn đoạn phục hồi bắt đầu giữa task và correction vào dữ liệu flow-matching có action chunk và RTC: có cần trọng số, mask hay độ dài tối thiểu? | Can thiệp phục hồi có thể vô hại hoặc gây hại tùy cách trộn | Định nghĩa can thiệp ở spec 6.10 | S3 |
| RL7 | Sau Mulligan và DISEIL, phần nào của đội còn đáng gọi là đóng góp? Nên thêm nhánh B-fail (nhắm lỗi, không chẩn đoán) thay B⁺ không? | Định vị pitch và thiết kế nhánh (TM1, TM6) | Thêm hay bỏ nhánh; câu định vị | S0–S1 |
| RL8 | Dùng ACT làm "testbed nhanh" chạy 5–8 vòng Failure → Data để thấy tỉ lệ sửa được hội tụ có thuyết phục không, hay kết quả trên model nhỏ không nói gì về Ψ₀? | Cách duy nhất có bằng chứng "flywheel học" trong 12 tuần (TM3) | Phạm vi F-ACT trên ACT (02 · 7.10, spec 7.8) | S3 |

### 6.2 Simulation và sim-to-real

| Mã | Câu hỏi | Vì sao quan trọng | Quyết định phụ thuộc | Sprint |
|---|---|---|---|---|
| SI1 | **[Chặn]** `set_states()` của SIMPLE có khôi phục trạng thái bên trong WBC và hàng đợi hành động, RTC của policy không? Kinh nghiệm với cặp MuJoCo vật lý và Isaac Sim render? | Phép kiểm khoanh vùng (spec 6.6) sống hay chết | Cờ `restore_state`; phương án thay ở spec 10 | S1 |
| SI2 | **[Chặn]** Level 2 đổi vị trí vật ra ngoài phân phối train hay chỉ ngẫu nhiên lại trong cùng khoảng? Tài liệu SIMPLE mô tả mức DR theo hai cách ngược nhau (03 V5) | Lỗi Level 2 có can thiệp dữ liệu được không (TH5) | Chỉ tiêu chính; luật "NGOÀI MIỀN" | S1 |
| SI3 | RTX 5090 có chạy ổn Isaac Sim 4.5 và `flash_attn==2.7.4.post1` không, hay nên thuê GPU cho sim ngay từ đầu? | Rủi ro mất tuần 1–2 cho cài đặt (KT4) | Bố trí máy 03 §2.1 | S0–S1 |
| SI4 | Thời gian thực mỗi episode và số worker song song hợp lý trên một GPU 32 GB khi đồng thời chạy server Ψ₀? Tỉ lệ đổi chiều do không tất định thường bao nhiêu? | Lịch holdout tuần 11 và số lượt ở cổng dev (KT5, TH7) | W, chính sách camera, số lượt | S1 |
| SI5 | Planner thất bại có nên coi là "không khả thi"? Cần bao nhiêu lần thử, bao nhiêu nghiệm IK trước khi kết luận? | Nhãn KHÔNG KHẢ THI giữ lại ngân sách dữ liệu | Tham số bước 5 | S3 |
| SI6 | Có cách rẻ nào trong sim để ước lượng mức phóng đại lợi ích do sim cùng phân phối test, ví dụ sinh dữ liệu với vật lý và texture lệch có chủ đích? | Trả lời trước câu hỏi sim-to-real của giám khảo (SR1) | Thêm biến thể "sim lệch" | S3 |
| SI7 | Trên robot thật, phép kiểm nào của chuỗi chẩn đoán còn dùng được? Real2sim cho trạng thái lỗi có khả thi trong 6 tháng sau PoC không? | Giới hạn claim L2 trong pitch (SR2, AR6) | Lộ trình L2 trong 01 §7 | S5 |

### 6.3 Hệ thống dữ liệu và MLOps

| Mã | Câu hỏi | Vì sao quan trọng | Quyết định phụ thuộc | Sprint |
|---|---|---|---|---|
| DS1 | **[Chặn]** Kiến trúc L0 có quá nặng cho 2 người Data-Platform trong 12 tuần? Mentor chấp nhận bộ tối thiểu nào (LeRobot gốc, manifest có hash, ledger JSONL, một chỉ mục DuckDB) để vẫn tái lập và chống rò? | Lịch của toàn dự án phụ thuộc phạm vi Data Core (AR1) | Cắt 03 về L0-lite | S1 |
| DS2 | Lưu bundle theo episode rồi export LeRobot cho mỗi lần train, hay giữ LeRobot gốc và chọn episode theo chỉ số? Lỗi export nào hay gặp nhất? | Sai dữ liệu train âm thầm (AR2) | ADR-03 | S2 |
| DS3 | Ngoài seed và `layout_hash`, nên chống rò bằng khoảng cách điều kiện với ngưỡng nào? Có cần kiểm toán provenance của checkpoint gốc như một phần lineage? | Rò dữ liệu vô hiệu hóa kết luận (TH12, TH13) | Guard ở 03 §8.3 | S2 |
| DS4 | Ledger nên đo GPU-giờ theo giờ tường của job, theo lấy mẫu pynvml hay theo hóa đơn? Phân bổ thế nào khi một máy chạy cả sim và server? | B_add và so sánh chi phí là số đo chính của BG1, BG3 | Cách `ledger.meter()` quy đổi | S2 |
| DS5 | Chiến lược backup tối thiểu cho máy 5090 đang là điểm hỏng đơn lẻ? | Mất `fwdata/` là mất bằng chứng (AR3) | Quy trình vận hành | S1 |
| DS6 | Để L1 gộp được tỉ lệ sửa được giữa task, có nên thêm ontology lỗi chung ngay từ L0? Mức chi tiết nào là đủ? | Tránh di trú schema ở L1 (AR5) | Trường trong FailureKindSpec | S3 |
| DS7 | psi-data và trọng số Ψ₀ không ghi giấy phép: đội nên làm gì trong lúc chờ tác giả, và nên ghi ranh giới bàn giao cho DENSO thế nào? | Quyết định thứ gì được giao cho doanh nghiệp (SR3) | Danh mục bàn giao G6 | S0 |

### 6.4 Thống kê và thiết kế thí nghiệm

| Mã | Câu hỏi | Vì sao quan trọng | Quyết định phụ thuộc | Sprint |
|---|---|---|---|---|
| TK1 | **[Chặn]** Bootstrap ghép cặp chỉ trên điều kiện có bỏ sót phương sai giữa seed huấn luyện không? Nên dùng bootstrap phân cấp hay mô hình logistic hỗn hợp với hiệu ứng ngẫu nhiên điều kiện và seed? | CI quá hẹp dẫn tới claim sai (TH2) | Phương pháp ở spec 7.5, 02 · 3.7 | S2 |
| TK2 | **[Chặn]** Với hiệu ứng C − B kỳ vọng 5–10 điểm, cần bao nhiêu seed và điều kiện để có lực 80%? Làm power analysis từ dữ liệu E1 thế nào? | Quyết định thêm seed hay cắt nhánh trước khi tiêu GPU (TH3) | Ma trận nhánh và seed | S3 |
| TK3 | Biên không kém −10 điểm có chấp nhận được khi đề BTC ghi "giảm ≥ 30% demo cho cùng hiệu năng; thành công ≥ 75%"? | Tiêu chí HS phải đứng được trước giám khảo (TH10) | Tiêu chí ở spec 3 | S2 |
| TK4 | Tỉ lệ sửa được cập nhật từ 1 lượt mỗi điều kiện bị thiên lệch hồi quy về trung bình. Đối chứng chạy lại policy cha có đủ, hay cần mô hình khác? | Phần "flywheel học" là claim chính (TH6) | Công thức spec 6.13 | S3 |
| TK5 | Cổng dev nên chạy bao nhiêu lượt mỗi điều kiện, và hiệu chỉnh ngưỡng "tăng" và "hồi quy ≤ 5%" bằng A/A test thế nào? | Cổng nhiễu sẽ từ chối ứng viên tốt hoặc nhận ứng viên xấu (TH7) | Spec 6.12, 02 · 3.6 | S4 |
| TK6 | Chỉ tiêu chính nên gộp ba mức hay tách theo mức? Với nhiều phép so sánh (HS ba điều kiện, HT, từng mức, từng phương pháp), cần hiệu chỉnh hay chỉ cần đăng ký trước một chỉ tiêu chính? | Tránh bị coi là chọn kết quả đẹp (TH10) | Đăng ký trước trong RunPlan | S2 |
| TK7 | Thiết kế HD tối thiểu để giám khảo tin: bao nhiêu người ngoài đội, bao nhiêu mục, mù đáp án ra sao, chống hiệu ứng học thế nào? Có nên chèn card sai cố ý? | r_debug là đòn bẩy kinh tế lớn nhất (TH11, KD2) | Thiết kế 02 · 8.1, 8.2 | S4 |
| TK8 | Chọn D\* bằng 1 seed có dính "winner's curse"? Nội suy đường cong hay thêm seed ở hai điểm lưới tốt hơn? | D\* quyết định mọi nhánh (TH9) | Spec 7.1 | S2 |

### 6.5 Vận hành nhà máy và kinh doanh DENSO

| Mã | Câu hỏi | Vì sao quan trọng | Quyết định phụ thuộc | Sprint |
|---|---|---|---|---|
| DN1 | **[Chặn]** DENSO (DMVN) đã có 1–2 kỹ năng cụ thể, video thao tác, layout trạm như đề ghi chưa? Kỹ năng đó có gần "cúi gắp rồi đặt" không? | Tính liên quan với DENSO và lựa chọn task SIMPLE (KD6) | Task chính; khoảng vector điều kiện | S0 |
| DN2 | DENSO quyết định đưa robot vào dây chuyền theo chỉ số nào: tỉ lệ thành công, cycle time, số ngày đưa kỹ năng mới vào, giờ công? Ngưỡng 75% của đề hay 80% của đội? | Chọn chỉ số chính cho báo cáo và kinh tế | KPI ở 01 §5 | S1 |
| DN3 | Một giờ teleop tại DENSO thực tế tốn bao nhiêu nếu tính robot, cell, người giám sát và thời gian dừng dây chuyền? | Thay đơn giá $10/h đang làm sim trông lỗ (KD3) | Bảng giá `pb_v2` | S1 |
| DN4 | Mỗi năm có bao nhiêu lần đổi linh kiện, khay, ánh sáng cần dạy lại, và hiện mỗi lần mất bao lâu? | Thay giả định 144 đợt và 20 giờ debug (KD4) | Mô hình kinh tế | S2 |
| DN5 | Nỗi đau "mỗi kỹ năng mới lại phải thu dữ liệu từ đầu": DENSO muốn tái dùng ở mức nào? Một kỹ năng ở L0 có đủ thuyết phục nếu kèm lộ trình L1? | Định vị L0 so với nỗi đau BTC nêu | Có thêm task thứ hai nhỏ hay không | S2 |
| DN6 | Dữ liệu nhà máy và video công nhân có được rời site? DENSO yêu cầu gì về giấy phép cho checkpoint và dataset được bàn giao? | Ranh giới bàn giao và thiết kế `site_id` (SR3, SR5) | Danh mục bàn giao G6 | S2 |
| DN7 | Giám khảo chấm theo 3 cấp của đề như thế nào? Đội nên trình bày "khuyến nghị quy trình thu dữ liệu định lượng" (Cấp 3) theo dạng nào: bảng chi phí mỗi điểm %, cây quyết định, SOP? Mã đề là H1 hay H2? | Cấu trúc báo cáo cuối và tên gọi (TH10, R17) | Mẫu báo cáo 02 · 8.4 | S1 |

### 6.6 Câu hỏi mở sau vòng 1

Các điểm dưới đây được báo lại khi áp 10 sửa ngày 22/10/2026 (06). Chúng chưa có câu trả lời trong spec v10.1, 02 0.3, 03 0.3. MO4 và MO5 là câu hỏi nội bộ; còn lại hỏi mentor theo lịch ở 04 mục 6.

| Mã | Câu hỏi | Vì sao quan trọng | Ai trả lời | Hạn |
|---|---|---|---|---|
| MO1 | **[Chặn]** Luật "dưới 15 lỗi Level 0 thì đổi task" (spec 7.1, 02 · 5.3 AC 4) đếm thế nào? Với 30 điều kiện Level 0 × 1 lượt, "dưới 15 lỗi" tương đương thành công Level 0 trên 50%, nên luật gần như luôn kích hoạt. Nên đếm trên nhiều lượt, trên dev cộng tập tìm lỗi, hay đổi thành ngưỡng theo tỉ lệ? | Đổi task ở tuần 8 (sau G3) khó kịp; cần ước sớm ở G2 và khai sẵn task khó hơn từ G0 | Hiếu, PO; hỏi mentor | Khai task dự phòng ở review G0; chốt cách đếm ở review G2 |
| MO2 | Thông lượng rollout của F-ACT: khoảng 630 rollout mỗi vòng theo spec 9 (03 §9.2 ước khoảng 850 với giao thức thu nhỏ), 5–8 vòng; tổng khối lượng PoC có thể 13,5–23 nghìn episode. Máy có đủ không? | F-ACT chạy cùng tuần 9–10 với vòng C của Ψ₀ và holdout sớm; thiếu máy thì F-ACT phải cắt vòng (04 mục 7.2 mức 4) | Hưng, Châu đo t và W khi policy là ACT (V8, V10); Architect cập nhật 03 §9.2 | G0 |
| MO3 | Nhánh C trên ACT lấy từ F-ACT: chọn checkpoint ở vòng mà chi phí thu lũy kế chạm B_add (02 · 7.10 AC 5) hay release vòng cuối train lại 3 seed từ khởi tạo (spec 7.8)? | Hai cách cho ngân sách và số seed khác nhau, làm đổi so sánh HTb (C so với B-fail) | PO xác nhận (02 §9 "Gửi PO" điểm 1); mentor cho ý kiến | Khai trong RunPlan F-ACT trước vòng 1; chốt ở review G2 |
| MO4 | Phạm vi mặc định cần khoảng 200–215 người-ngày theo ước 3,5 ngày mỗi story (02 §4), so với 147 người-ngày ở mức 70% năng lực. Theo giờ của 04 là khoảng 962 so với 730 giờ; thứ tự cắt đã duyệt chỉ bớt khoảng 30 giờ người. Chọn H thực cao hơn, cắt thêm ngoài danh sách, hay hạ đệm? | Kế hoạch hiện không vừa mức 70% của 06 mục 9 (04 mục 4.8) | Hiếu, PO | Họp lập kế hoạch S1; xem lại ở review G0 khi có hệ số k |
| MO5 | Episode do người thu (teleop correction, `operator_kind = human`) không tái tạo được nên phải nằm trong backup. 03 §10.4 đã liệt kê, nhưng 06 mục 9 và 02 · 2.8 AC 1 chưa ghi | Mất máy 5090 là mất demo người của nhánh C, không thu lại được cùng điều kiện | PM sửa 02 · 2.8 AC 1; Thông thêm vào job backup | Trước story 2.8 (S3) |

Trạng thái MO4 (23/10/2026): trưởng nhóm quyết giữ đủ phạm vi, đo k sau Sprint 1, khi vượt thì chuyển phần trễ sang API theo từng phần trước khi cắt (06 mục 11). Phạm vi còn tăng thêm khoảng 185–255 giờ (04 mục 4.9), nên MO4 vẫn mở tới review G0.

### 6.7 Phản biện và câu hỏi cho spec v10.2

Spec v10.2 thêm robot chính của DENSO, pipeline ba nguồn, synthetic qua NIM, probe theo stage và robot thay thế. QA rà ngày 23/10/2026; các điểm dưới đây chưa có câu trả lời trong spec v10.2, design hay 03 bản 0.4.

| Mã | Câu hỏi | Vì sao quan trọng | Ai trả lời | Hạn |
|---|---|---|---|---|
| MO6 | **[Chặn]** Robot thay thế giống ≥ 95% về động học (vùng với tới, link, khớp, camera, gripper) có đủ để kết quả trên nó còn đúng cho robot thật không? Thước đo chưa gồm động lực học tiếp xúc, ma sát gripper và cách render | Kết quả trên robot thay thế dễ bị đọc như kết quả trên robot DENSO; tiếp xúc khi gắp và đặt vào đồ gá là chỗ hay hỏng nhất | Hưng; hỏi mentor simulation | Trước khi chốt DA-10 (S1) |
| MO7 | Robot DENSO cần tiêu chí chấp nhận định lượng nào? MT8 mới yêu cầu "chạy trọn", chưa có ngưỡng thành công hay map 3 cấp BTC riêng | Không có ngưỡng thì không biết robot DENSO "đạt" hay chưa ở G6 | Hiếu, PO; hỏi DENSO (DN2) | Review G1 |
| MO8 | Bước 4b quy lỗi về stage dựa trên probe là bằng chứng gián tiếp. Làm sao biết quy tắc quy đúng? Có bộ lỗi cấy theo stage (ví dụ làm hỏng VLM bằng nhiễu ảnh, làm hỏng action expert bằng checkpoint sớm) để đo độ chính xác không? | Quy sai stage dẫn tới mua sai loại dữ liệu, giống PM6 | Long, Hiếu; thêm vào AC của 02 · 9.13 | Trước G4 |
| MO9 | So S2-A, S2-B, S2-C cần bao nhiêu lần train Ψ₀ thêm, bao nhiêu A100-giờ? Bảng khối lượng ở spec mục 9 chưa tính | Có thể vượt ngân sách GPU đã duyệt ở G0 | Châu, Hiếu đo ở G0 (Q5) | G0 |
| MO10 | Cosmos Transfer đổi ngoại hình có giữ đúng vị trí và tiếp xúc tới mức action gốc còn hợp lệ không (V-D5)? Nếu IoU đạt mà vị trí gripper lệch vài mm thì sao? | S3 có thể đưa vào train những cặp ảnh và action không khớp | Hưng (DA-06); hỏi mentor | Trước khi S3 vào release (G3) |
| MO11 | Video egocentric không train stage 1 lại thì có đáng thu không? Nếu U1–U3 (probe, mẫu sinh, cấu trúc task) cho ít giá trị, có nên đề nghị DENSO ưu tiên teleop thay vì video? | Ảnh hưởng tới khuyến nghị thu dữ liệu cho DENSO (Cấp 3 BTC) | Hiếu; số đo từ probe P1 ở G2–G3 | Review G3 |
| MO12 | Có đổi định vị "flywheel" khi L0 chỉ chạy trong sim, và có kéo "dùng dữ liệu lỗi để train" từ L1 vào PoC không (D1, D2 ở [data-flywheel.md](../references/data-flywheel.md))? Mulligan, LoopWAM, RECAP, LWD đều dùng dữ liệu lỗi | Giám khảo dễ hỏi đúng hai điểm này | Hiếu; hỏi mentor | Buổi mentor đầu |
| MO13 | Tải người sau khi cộng Epic 9 là khoảng 138–178% mức kế hoạch 70% (07 mục 2.3). Phần nào chuyển sang API trước, ai quyết, theo dấu hiệu gì? | Không có luật kích hoạt thì việc chuyển sang API sẽ đến muộn | Hiếu, Thông | Họp lập kế hoạch S1 |

## 7. Danh sách sửa ưu tiên

Thứ tự là thứ tự áp dụng. Mỗi mục ghi tài liệu và mục bị sửa; PO ghi change log theo quy tắc của README.

| # | Sửa gì | Ở đâu | Hạn | Đã áp |
|---|---|---|---|---|
| 1 | V3 đã vào G0 (02 · 1.5 AC5, 03 §3.3); còn phải: tách V3 thành story riêng có hạn ngày 5; thêm story xây tuyến generator được chọn; sửa System-0 của task chính thành decoupled WBC; bỏ F1 khỏi vai trò dự phòng cho Q2 cho tới khi V3 xác nhận; khai tuyến T1–T4 trong mục rủi ro của spec | spec 2.1, 2.3, 2.4, 6.4, 10; 02 · 1.5, 5.1, §8; 03 §12.2 | Trước sprint 1 | 22/10/2026: spec v10.1 #1; 02 0.3 (story 1.9, 5.5, 5.1, §8); 03 0.3 (§3.3, §12.2, ADR-15); 01 0.3; 04 0.2 (S1-11) |
| 2 | CI phải gồm phương sai seed (bootstrap phân cấp hoặc mô hình hỗn hợp); bỏ quy tắc 2/3 seed hoặc chỉ giữ làm chỉ số phụ; thêm power analysis ở G2 với 2 seed tại D\*; luật: nếu hiệu ứng phát hiện được > 10 điểm thì tăng seed cho B và C hoặc hạ HT thành mô tả | spec 7.5, 9; 02 · 3.7, 4.4; 03 §6.3, §11 | Trước G2 | 22/10/2026: spec v10.1 #2; 02 0.3 (1.3, 3.7, 4.4); 03 0.3 (§6.3, §11); 01 0.3 |
| 3 | Sửa chọn can thiệp và tỉ lệ sửa được: g tính theo số lỗi được xử lý sau khi chặn; ghi rõ vòng 1 xếp theo đơn giá; fixed_j bằng chênh lệch ứng viên trừ policy cha chạy lại ≥ 3 lượt; đo trên điều kiện mới quanh điểm lỗi; tập cổng dev mới mỗi vòng; bằng chứng "flywheel học" chạy trên ACT 5–8 vòng | spec 6.11, 6.12, 6.13, 7.6; 02 · 3.6, 7.2; 00 §3 | Trước G3 | 22/10/2026: spec v10.1 #3; 02 0.3 (3.6, 7.2, story 7.10, FR46); 03 0.3 (ADR-16, §9.2); 00 0.2 §3; 01 0.3 |
| 4 | Chốt lượng dữ liệu của B (N_sim hoặc trần GPU-giờ), bỏ định nghĩa vòng tròn của B_add; cùng chính sách tăng cường thị giác cho mọi nhánh; xử lý demo bị loại ở C theo quy tắc cùng danh sách 0,7D\*; thêm luật "NGOÀI MIỀN" cho lỗi Level 2; thay hoặc bổ sung B⁺ bằng B-fail | spec 6.8, 6.9, 7.2, 7.3; 02 · 5.2, 7.9 | Trước G3 | 22/10/2026: spec v10.1 #4; 02 0.3 (5.2, 6.2, 7.1, 7.5, story 7.11); 03 0.3 (ADR-17); 01 0.3 |
| 5 | Thêm phép kiểm "đồng bộ cảm biến" và "camera chuẩn" vào chẩn đoán, hoặc bỏ trễ camera và lệch calibration khỏi lỗi cấy HD (nếu không, AC 3 của 02 · 6.5 bản 0.2 không đạt được); bổ sung vào AC đó recall theo lớp và đối chứng sạch theo mục 3; HD có ≥ 2 người ngoài đội và card sai cố ý | spec 6.4, 6.9, 7.6; 02 · 6.2, 6.5, 8.1, 8.2 | Trước G4 | 22/10/2026: spec v10.1 #5; 02 0.3 (6.2, 6.5, 8.1, 8.2); 03 0.3 (§6.2, §6.4, V11); 01 0.3 |
| 6 | Định vị lại tính mới cho khớp spec 1.2 đã sửa: dùng bảng claim ở mục 2.1; bỏ "đối thủ không có"; bỏ "điểm khác biệt chính" của HT; đổi ô "Có" của L0 ở 01 §8.2 thành "Mục tiêu, chưa đo"; thêm IntervenGen, CUPID; ghi Mulligan dùng dữ liệu lỗi để học value function; gọi HT là kiểm lại | 00 §3, §4; 01 §1, §2.2, §2.4, §3.4, §8, §10.1 | Trước buổi mentor đầu tiên | 22/10/2026: spec v10.1 #6; 00 0.2 §1, §3, §4; 01 0.3; 02 0.3 §1.2 |
| 7 | Map tiêu chí 3 cấp của BTC vào KPI (≥ 50%; ≥ 30% ít demo cùng hiệu năng và ≥ 75%; ≥ 70% trên biến thể chưa train kèm khuyến nghị định lượng); báo riêng Level 1–2; xác nhận mã đề với BTC; đổi tên giả thuyết (ví dụ HS cho sim, HT cho nhắm lỗi, HD cho debug) để không trùng mã đề và tên nhánh | spec 0, 3; 01 §1, §5.3; README gốc | Trước sprint 1 | 22/10/2026: spec v10.1 #7 (đổi tên HS, HT, HD, bảng 3 cấp, D\* theo 75%); 01 0.3; 02 0.3 §1.1. Còn mở: mã đề chờ BTC; pitch v10 chưa cập nhật |
| 8 | Provenance checkpoint gốc: thêm câu Q0 vào G0; RunPlan mẫu không trỏ `simple-checkpoints` hoặc `sonic-checkpoints` cho E1 và các nhánh; guard gần trùng theo khoảng cách điều kiện; dải seed dev và holdout rời với dải tác giả dùng | spec 2.4, 7.3.1; 03 §8.1, §8.3; 02 · 1.3, 2.2, 2.5 | G0 | 22/10/2026: spec v10.1 #8; 02 0.3 (1.3, 2.4, 2.5, 4.3); 03 0.3 (§8.1, §8.3); 01 0.3 |
| 9 | Kế hoạch năng lực thực tế: lập ở mức 70% năng lực; lát dọc trên SIMPLE trước tuần 4; kiến trúc L0-lite (AR1); đồng sở hữu Ψ₀; mặc định 1 vòng C cho Ψ₀; holdout sớm và niêm phong cho nhánh không phụ thuộc C; backup hằng ngày; cập nhật bảng năng lực 02 §4 theo 52 story và bỏ chữ SQLite còn sót ở 02 §9 | 02 §4, §5, §8, §9; 03 §2.1, §3.1, §4.3, §7 | Sprint 1 | 22/10/2026: spec v10.1 #9; 02 0.3 (§4, §8, story 2.8, NFR11, NFR12); 03 0.3 (§2.4, ADR-13, ADR-14, §10.4); 04 0.2 (70% năng lực, mục 4.8: vẫn vượt, xem MO4) |
| 10 | Kinh tế: thêm chi phí mỗi điểm % của C so với B và B-fail; bảng độ nhạy theo đơn giá DENSO và chi phí giờ cell; chỉ số chính chuyển sang số demo người để đạt ngưỡng, phút operator mỗi điểm %, sai số dự báo chi phí, số ngày đạt ngưỡng lại; r_debug trình bày là khoảng; báo HT theo hai ràng buộc phút người và GPU-giờ | spec 8.2, 8.3; 01 §5; 02 · 7.8 | Trước G4 | 22/10/2026: spec v10.1 #10; 02 0.3 (2.7, 7.8); 01 0.3 |

## 8. Nguồn kiểm thêm (ngày 22/10/2026)

- Mulligan, Ankile và cộng sự: [arXiv 2610.05882](https://arxiv.org/abs/2610.05882). Đọc trang tóm tắt; chưa đọc bản đầy đủ.
- DISEIL, Khanal và cộng sự: [arXiv 2609.08123](https://arxiv.org/abs/2609.08123). Đọc trang tóm tắt.
- IntervenGen, Hoque và cộng sự, 2024: [arXiv 2405.01472](https://arxiv.org/abs/2405.01472).
- CUPID, Agia và cộng sự, 2025: [arXiv 2506.19121](https://arxiv.org/abs/2506.19121).
- So sánh policy với số lượt nhỏ bằng kiểm định tuần tự (STEP), Snyder và cộng sự, RSS 2025: [arXiv 2503.10966](https://arxiv.org/abs/2503.10966).
- Thực hành tốt khi đánh giá policy robot, Kress-Gazit và cộng sự, 2024: [arXiv 2409.09491](https://arxiv.org/abs/2409.09491).
- Danh sách checkpoint Ψ₀ trên Hugging Face, thư mục `psi0/`: [USC-PSI-Lab/psi-model](https://huggingface.co/USC-PSI-Lab/psi-model/tree/main/psi0). Không có thẻ model và không ghi giấy phép; vai trò từng thư mục chỉ suy từ tên, cần tác giả xác nhận.
- Ảnh đề BTC trong repo: `docs/challenge/1.jpeg` (vấn đề, phạm vi, dữ liệu DENSO cung cấp), `docs/challenge/2.jpeg` (đầu ra, tiêu chí 3 cấp).
