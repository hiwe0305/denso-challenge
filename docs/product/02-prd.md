# 02 · PRD: Humanoid Data Flywheel

_Ngày 22/10/2026, cập nhật 23/10/2026. Vai trò: Product Manager (BMAD). Trạng thái: bản 0.4 thêm Epic 9 (dữ liệu đa nguồn và robot DENSO), FR48–FR57, NFR13 theo [spec v10.2](../spec-v10-failure-to-data.md), [design 23/10/2026](../superpowers/specs/2026-10-23-data-pipeline-and-failure-eval-design.md) và [06 mục 11](06-review-round-1-decisions.md). Bản 0.3, PM áp 10 sửa ưu tiên theo [06 · Quyết định phản biện vòng 1](06-review-round-1-decisions.md); bản 0.2 đã được PO đối chiếu với 01 và 03 (kết quả ở [04 mục 1](04-delivery-plan.md)). Đầu vào: [00 · Phân tích idea](00-idea-analysis.md), [01 · Project brief](01-project-brief.md), [spec v10.1](../spec-v10-failure-to-data.md), [05 · Phản biện](05-review-and-mentor-questions.md), [06](06-review-round-1-decisions.md), [đề H1](../challenge/README.md). Khi PRD lệch spec v10 về thuật toán hoặc thiết kế thí nghiệm, spec v10 thắng; khi 05 và 06 khác nhau, theo 06. PRD quyết định phạm vi, thứ tự làm và nghiệm thu. Thuật ngữ theo glossary ở mục 12 của spec v10. Tên giả thuyết theo 06: HS, HT (HTa, HTb), HD; mã đề giữ "H1" cho tới khi BTC xác nhận._

## 1. Mục tiêu và bối cảnh

### 1.1 Mục tiêu

| Mã | Mục tiêu | Đo bằng |
|---|---|---|
| MT1 | Vòng Failure → Data chạy trọn bằng CLI cho recipe Ψ₀ + SIMPLE / G1: trace → evidence card → đề xuất → kỹ sư duyệt → thu và QA → train → cổng dev → cập nhật tỉ lệ sửa được | Vòng 1 của nhánh C trên Ψ₀ và 5–8 vòng F-ACT trên ACT xong ở G4, mọi cụm lỗi có evidence card |
| MT2 | Kết luận HS, HT (HTa, HTb), HD đúng tiêu chí đã chốt ở spec mục 3, kể cả khi trượt | Báo cáo G6 có CI 95% bootstrap phân cấp, kết quả từng seed, MDE từ power analysis, r_debug dạng khoảng |
| MT3 | Giao đủ ba đầu ra của đề H1: SOP thu dữ liệu, báo cáo so sánh phương pháp, demo kỹ năng | Ba sản phẩm có mặt ở G6 |
| MT4 | Mọi nguồn lực đã tiêu đều có trong sổ chi phí | 0 lần chạy tiêu GPU hoặc giờ người mà thiếu mục sổ, kiểm ở G4 và G6 |
| MT5 | Lõi tách khỏi recipe | Cắm ACT, Diffusion Policy và TaskDefinition của task dự phòng F1 mà không sửa mã lõi, không đổi schema |
| MT6 | Mọi claim trong pitch có số đo đi kèm hoặc bị gỡ | Rà soát ở G6 |
| MT7 | Bám tiêu chí 3 cấp của BTC | Mỗi cấp có số đo trong báo cáo G6 theo bảng map dưới đây |
| MT8 | Recipe chính chạy trên robot DENSO hoặc robot thay thế (bản 0.4) | Dữ liệu ba nguồn đi trọn pipeline thành release; Ψ₀ chạy task khay → máy trong Isaac Sim; ít nhất một vòng Failure → Data chạy trọn với bảng lỗi và quy lỗi về stage; điểm giống của robot thay thế báo đúng cơ sở chấm. Tiêu chí 3 cấp BTC báo riêng cho robot DENSO khi có kết quả |

**Tên giả thuyết** (06): **HS** là sim thay được 30% demo teleop. **HT** là chọn dữ liệu theo lỗi, tách **HTa** (nhắm theo lỗi tốt hơn bổ sung đều; đạt khi cận dưới CI 95% của (B-fail − B) > 0) và **HTb** (chẩn đoán giúp thêm ngoài việc chỉ nhắm theo lỗi; đạt khi cận dưới CI 95% của (C − B-fail) > 0); chênh lệch C − B vẫn báo. HT là phép **kiểm lại (replication)** kết quả kiểu Mulligan / DISEIL trên G1 toàn thân, không phải điểm khác biệt chính. **HD** là evidence card giảm thời gian chẩn đoán.

**Map tiêu chí BTC 3 cấp** (06 mục 7):

| Cấp BTC | Tiêu chí | Chỉ tiêu trong PoC | Mục tiêu, story |
|---|---|---|---|
| 1 · Basic | ≥ 50% với lượng demo nhỏ | Báo tỉ lệ thành công ở các mức 10% và 25% của đường cong E1 | MT3; 4.4, 8.4 |
| 2 · Efficient | Giảm ≥ 30% demo cùng hiệu năng; ≥ 75% | HS: B ở 0,7D\* không kém A và đạt ≥ 75%. D\* là mức demo nhỏ nhất để Ψ₀ đạt ≥ 75% trên dev gộp | MT2; 4.4, 5.3, 8.3 |
| 3 · Advanced | ≥ 70% trên biến thể chưa train; khuyến nghị thu dữ liệu định lượng | Báo riêng Level 1 và Level 2 của holdout so với 70%; đầu ra của bước Decide cộng sổ chi phí là khuyến nghị định lượng (FR47) | MT2, MT4; 7.8, 8.3, 8.4 |

Pitch v10 vẫn ghi "≥ 80% / 50 lượt"; cập nhật pitch nằm ngoài lần sửa này.

Chỉ số theo dõi mỗi vòng: tỉ lệ ghi đè của kỹ sư, chi phí mỗi điểm % thành công trên dev, tỉ lệ sinh đạt, số cụm có chẩn đoán CHƯA RÕ, sàn hồi quy của A/A test.

Chỉ số giá trị chính (06 mục 10), báo ở 7.8 và 8.4: số demo người để đạt ngưỡng; phút operator mỗi điểm %; sai số dự báo chi phí (ước tính so với thực đo trong sổ); số ngày để policy đạt lại ngưỡng. Đô-la chỉ xuất hiện trong bảng độ nhạy.

### 1.2 Bối cảnh

- **Vấn đề.** Khi humanoid hỏng một task, đội robot đoán nguyên nhân từ video và log, rồi thường chọn thu thêm teleop. Không ai biết trước một lần sửa tốn bao nhiêu công (00, mục 2).
- **Sản phẩm.** Lõi data flywheel quyết định sau mỗi lỗi: sửa hệ thống hay bổ sung loại dữ liệu nào, bao nhiêu, tốn bao nhiêu. Model, simulator, robot và task là phần cắm. Câu định vị (06 mục 6): quy trình vận hành có kiểm toán cho vòng lỗi → dữ liệu, loại lỗi hệ thống trước khi tiêu tiền vào dữ liệu, chọn giữa nhiều loại can thiệp theo chi phí thật kể cả chi phí chẩn đoán, và xuất **khuyến nghị thu dữ liệu định lượng** cho DENSO. Data Core cộng SOP gọi là **"DENSO Data Model"** như tên đề.
- **Recipe đầu tiên.** Ψ₀ + SIMPLE / Unitree G1 trong mô phỏng. Task chính `G1WholebodyBendPickAndPlaceTeleop-v0`, bộ điều khiển là decoupled WBC (`g1_sonic`, env `SonicLocoManipEnv`); AMO là bộ điều khiển của pipeline motion planning. Task dự phòng F1 là cặp `G1WholebodyBendPick*`: dự phòng cho Q1 và phép thử tổng quát của lõi; **không** là dự phòng cho Q2 cho tới khi story 1.9 xác nhận cặp task của F1 cùng bộ điều khiển.
- **Recipe chính (bản 0.4).** Ψ₀ + Isaac Sim / mobile manipulator của DENSO (đế bánh xe, cột nâng, hai tay, gripper hai ngón, camera đỉnh cột), task lấy linh kiện từ khay đặt vào máy. Stage 1 của Ψ₀ giữ nguyên, stage 2 train lại, stage 3 fine-tune theo task. Dữ liệu teleop, video egocentric của nhà máy và synthetic (S1–S4, Cosmos qua NVIDIA NIM) đi qua cùng pipeline. Chưa có thông số robot: dùng robot thay thế giống ≥ 95% (spec mục 2.5). G1 là bàn thử cho HS, HT, HD.
- **Bằng chứng.** Đã kiểm: gói dữ liệu task chính có trên psi-data (108 MB). Chưa kiểm: tái tạo số của Ψ₀, fine-tune trên GPU của đội, V3, HS, HT, HD. Số kinh tế trong pitch là giả định.
- **Người dùng trong 12 tuần.** Chính 5 thành viên đội (kỹ sư robot learning, simulation, data) và giám khảo đọc báo cáo. Operator teleop và chủ công đoạn là người dùng của L1–L2.
- **Ưu tiên của chủ dự án.** Làm rõ và phát triển lõi để dễ mở rộng. PRD vì vậy đặt mô hình dữ liệu, giao diện adapter và sổ chi phí lên trước. Mỗi lần train hay chạy thí nghiệm được coi là việc của recipe.

### 1.3 Change log

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 22/10/2026 | 0.1 | Bản đầu, dựng từ 00, 01 và spec v10 | PM |
| 22/10/2026 | 0.2 | Đổi CLI `hdf` thành `fw`; cây thư mục, lưu trữ DuckDB và tên cờ khả năng theo 03 (mục 3, 4, story 1.1, 2.6, 2.7, 3.8, 4.3, 7.3) | PO |
| 22/10/2026 | 0.2 | FR1 trỏ về danh sách thực thể chuẩn của 03 mục 4.3; FR26 ghi tỉ lệ sửa được lưu trong `ledger` (03 ADR-12) | PO |
| 22/10/2026 | 0.2 | Thêm AC cho yêu cầu chưa có story ở G0: NFR1 (1.3), V3 (1.5), V1 và V9 giấy phép (1.6); thêm story 1.8 cho V6, V7 | PO |
| 22/10/2026 | 0.2 | Bỏ phụ thuộc cứng 1.4 → 1.3 và 2.1 → 1.7 (gỡ gần vòng 1.7 ↔ 2.1); τ_cov và story 2.4 dời sang G2; điều kiện G1 của 4.1 làm rõ | PO |
| 22/10/2026 | 0.2 | Story 2.2 đổi thành nhập psi-data qua `catalog`, nhãn [Lõi], theo 03 mục 6.1 | PO |
| 22/10/2026 | 0.2 | Story 6.5: PO duyệt ngưỡng 8/10 kèm điều kiện cứng; thêm AC wrapper cấy lỗi chung (FR14) | PO |
| 22/10/2026 | 0.2 | Thứ tự cắt giảm ở mục 8 được PO duyệt có sửa; phân công thực tế chuyển sang 04 | PO |
| 22/10/2026 | 0.2 | Story 1.3 thêm AC Q0 (nguồn gốc checkpoint gốc), theo phản biện 05 TH12 | PO |
| 22/10/2026 | 0.3 | Đổi tên giả thuyết H1 → HS, H2 → HT (HTa, HTb), H3 → HD trong toàn PRD; giữ mã đề "H1"; thêm định nghĩa HTa, HTb ở mục 1.1 | PM theo 06 |
| 22/10/2026 | 0.3 | Sửa #1 (V3): tách V3 khỏi 1.5 (AC 5 chuyển đi) thành story mới 1.9, hạn ngày 5 Sprint 1; thêm story 5.5 xây tuyến generator đã chọn (T1–T4); 5.1 đổi tên, AC 1 bỏ F1 làm dự phòng cho Q2; 6.3, 6.4, 7.4 theo tuyến V3; FR30; §1.2, §7; §8 thêm rủi ro V3, T1–T4 và kịch bản V3 âm cộng Q6 âm | PM theo 06 |
| 22/10/2026 | 0.3 | Sửa #2 (thống kê): FR36, FR39; 1.3 AC 1–2 (30 lượt mỗi mức, kiểm nhị thức một phía); 3.7 bootstrap phân cấp, logistic hỗn hợp kiểm chéo, 2/3 seed là chỉ số phụ; 4.4 AC 4–5 (2 seed quanh ngưỡng khi chọn D\*, power analysis ở G2, luật MDE > 10 điểm) | PM theo 06 |
| 22/10/2026 | 0.3 | Sửa #3 (chọn can thiệp, tỉ lệ sửa được): FR26, FR37, thêm FR46; 3.6 AC 3–5 (tập cổng mới mỗi vòng, ≥ 3 lượt, A/A test); 7.2 AC 1–5 (n_eff, unit test "vòng 1 xếp theo đơn giá", đo có đối chứng); thêm story 7.10 F-ACT | PM theo 06 |
| 22/10/2026 | 0.3 | Sửa #4 (công bằng giữa nhánh): FR4, FR5, FR11, FR20, FR25, FR29, FR31, FR32, FR33, FR35, FR41; 4.2, 4.3, 5.2 (N_B chốt trước G3, B_add thực đo), 5.3 AC 4 (dưới 15 lỗi Level 0 thì đổi task), 6.2 (NGOÀI MIỀN), 6.3, 7.1, 7.5; thêm story 7.11 B-fail, ngưỡng HTa, HTb là cận dưới CI 95% của chênh lệch > 0 (§1.1, 7.11 AC 3); 7.9 B⁺ ưu tiên thấp hơn; 7.8, 8.3, 8.4 thêm phụ thuộc mới | PM theo 06 |
| 22/10/2026 | 0.3 | Sửa #5 (lỗi cấy, HD): FR14, FR20, FR44; 3.5 τ_sync; 6.2 kiểm đồng bộ cảm biến, camera chuẩn trên stack WBC; 6.5 AC 1, 2, 5 (recall theo lớp, đối chứng sạch); 8.1, 8.2 (≥ 2 người ngoài đội, Rerun cộng đồ thị mặc định, 3–4 card sai cố ý, r_debug dạng khoảng); §3 | PM theo 06 |
| 22/10/2026 | 0.3 | Sửa #6, phần chạm PRD: câu định vị, "DENSO Data Model" (§1.2, Epic 2); HT là kiểm lại; backlog L1 thêm "dùng dữ liệu lỗi để train" | PM theo 06 |
| 22/10/2026 | 0.3 | Sửa #7 (tiêu chí BTC): bảng map 3 cấp và MT7 ở §1.1; D\* theo ngưỡng ≥ 75% (FR36, 4.4); báo riêng Level 1–2 (FR39, 3.7, 8.3, 8.4); thêm FR47 khuyến nghị thu dữ liệu định lượng | PM theo 06 |
| 22/10/2026 | 0.3 | Sửa #8 (nguồn gốc checkpoint, chống rò): 1.3 AC 5 (Q0, Source, `simple-checkpoints` chỉ dùng ở G0); 4.3 AC 4 chặn checkpoint; 2.4 AC 4 guard gần trùng theo khoảng cách; 2.5 AC 1 dải hạt giống rời với tác giả; FR9, FR10, NFR5 | PM theo 06 |
| 22/10/2026 | 0.3 | Sửa #9 (năng lực, L0-lite): §4 lập kế hoạch ở 70% năng lực, bảng năng lực theo 57 story; §8 phạm vi mặc định (1 vòng C trên Ψ₀, vòng thêm trên ACT, holdout sớm niêm phong) và thứ tự cắt sửa cho khớp B-fail, F-ACT; 7.7; 3.8 AC 4 và dời sang G4, 8.3 AC 4–5 (holdout sớm, chỉ số chính từ cờ SIMPLE); FR1, FR17, FR38, NFR3, NFR7 (L0-lite, `site_id`), thêm NFR11 backup, NFR12 L0-lite; thêm story 2.8 backup; 2.1, 3.3 (lớp lỗi chung); §9 bỏ SQLite | PM theo 06 |
| 22/10/2026 | 0.3 | Sửa #10 (kinh tế): FR41, FR42; 2.7 tách ước tính và thực đo; 7.8 AC 1–5 (chi phí mỗi điểm % của C so với B và B-fail, chỉ số chính mới, r_debug dạng khoảng, độ nhạy theo đơn giá và chi phí giờ cell, HT theo hai ràng buộc); chỉ số giá trị ở §1.1 | PM theo 06 |
| 23/10/2026 | 0.4 | Theo spec v10.2 và 06 mục 11: §1.1 thêm MT8; §1.2 thêm recipe chính Ψ₀ + Isaac Sim / robot DENSO; thêm FR48–FR57 (định dạng episode chung, pipeline teleop và egocentric, tầng synthetic, NIM, probe theo stage, log train và bộ phát hiện lỗi, quy lỗi về stage, robot DENSO và robot thay thế, task khay → máy); thêm NFR13 (riêng tư, định tuyến dữ liệu); §5, §6 thêm Epic 9 gồm 9.1–9.14, ứng với DA-01…DA-14 của 07; §7 sửa ngoài phạm vi; §8 thêm 5 rủi ro | PM theo 06 mục 11 |

## 2. Yêu cầu

### 2.1 Yêu cầu chức năng

Mỗi FR ghi module chịu trách nhiệm và mục spec gốc.

- **FR1** · `catalog` · Lưu các thực thể: Episode, Trace, Release, Checkpoint, RunPlan, Cụm lỗi, Evidence card, Can thiệp, Phiếu sửa, Mục sổ chi phí. Mỗi thực thể có ID bất biến và content hash. L0 theo kiến trúc L0-lite: khoảng 12 thực thể, trường mở rộng để trong `meta` (06 mục 9). Danh sách và tên chuẩn theo 03 mục 4.3.
- **FR2** · `catalog` · Mỗi episode mang loại đơn vị đếm của spec 4.1 (demo teleop, teleop correction, rollout sim, biến thể, rollout đánh giá) và lineage: nguồn, giấy phép, episode cha, hạt giống điều kiện, phiên bản bộ sinh. Thiếu lineage thì cách ly.
- **FR3** · `catalog` · Release bất biến: release mới bằng release cha cộng episode mới đạt QA, ghi release cha, danh sách episode và hash. Dữ liệu cũ luôn được trộn lại (replay).
- **FR4** · `catalog` · Đếm demo gốc tách khỏi rollout sim và biến thể; tính r_demo theo spec 4.1; đếm riêng số demo người (teleop và correction) của từng nhánh.
- **FR5** · `catalog` · RunPlan khai trước mọi tham số: dải hạt giống, tham số spec 6.15, ngân sách, đơn giá, revision checkpoint gốc đã qua Q0, ngưỡng D\* (≥ 75%), N_B và trần GPU-giờ của B (chốt trước G3), chính sách tăng cường thị giác chung cho mọi nhánh, luật MDE, tiêu chí HS và HT. Đã chốt thì có hash và không sửa được; muốn đổi phải tạo bản mới kèm lý do.
- **FR6** · `qa` · Chạy 7 phép kiểm của spec 4.4 trên mọi episode trước khi vào release. Ngưỡng hiệu chỉnh từ demo teleop thành công và lưu trong RunPlan.
- **FR7** · `qa` · Mẫu bị loại được giữ cùng lý do và chi phí. Báo cáo QA theo nguồn có tỉ lệ đạt và lý do loại.
- **FR8** · `scenarios` · Trích vector điều kiện (spec 4.2) cho mọi episode; chuẩn hóa theo khoảng của tập train; Euclid có trọng số cho phần liên tục, Hamming cho phần phân loại.
- **FR9** · `scenarios` · Chia train, dev (90 điều kiện), holdout (150 điều kiện) theo hạt giống điều kiện, dải rời nhau và rời với dải tác giả dùng cho psi-data và `simple-eval` (không biết dải của tác giả thì chọn dải lệch xa); dải dev đủ rộng để mỗi vòng có một tập cổng mới; ghi vào RunPlan trước khi train.
- **FR10** · `scenarios` · Tính khoảng cách kNN (K = 5) tới tập train và τ_cov (phân vị 95, leave-one-out). Guard gần trùng: điều kiện dev hoặc holdout có khoảng cách tới train dưới phân vị 1 của khoảng cách láng giềng trong train thì bị cách ly (06 mục 8).
- **FR11** · `scenarios` · Lấy mẫu điều kiện theo ba chế độ: đều trong miền train (nhánh B); đều trong bán kính τ_cov quanh điều kiện lỗi đã chẩn đoán và vẫn trong miền train (nhánh C); đều trong bán kính τ_cov quanh mọi điều kiện lỗi dev, không qua chẩn đoán (nhánh B-fail). Có hàm kiểm "trong miền train" theo khoảng train từng chiều, dùng cho bộ sinh và chẩn đoán NGOÀI MIỀN.
- **FR12** · `runner` · Chạy policy trên danh sách điều kiện qua SimulatorAdapter và PolicyAdapter; lưu trace đủ trường spec 4.5, kể cả episode thành công.
- **FR13** · `runner` · Lưu trạng thái simulator ở đầu bước hỏng; khởi động từ trạng thái đã lưu và đặt hình ảnh về mức chuẩn khi adapter khai có khả năng đó (Q3, Q4).
- **FR14** · `runner` · Cấy lỗi có chủ đích (lệch lệnh controller, trễ camera, lệch calibration camera, ánh sáng ngoài miền) và chạy episode sạch làm đối chứng, để kiểm chẩn đoán (recall theo lớp, tỉ lệ báo nhầm) và chạy HD.
- **FR15** · `runner` · Bị ngắt thì chạy tiếp, không chạy lại episode đã xong.
- **FR16** · `scorer` · Khung scorer từng bước nhận TaskDefinition (bước, vị từ, điều kiện chạy suốt) và trả trạng thái mỗi bước: đạt, trượt, chưa thử, chưa rõ.
- **FR17** · `scorer` · Gán bước hỏng đầu tiên k, một trong 9 kiểu lỗi của spec 5.2, và **lớp lỗi chung** của kiểu lỗi đó (tiếp cận, gắp, mang, đặt, thăng bằng) để gộp thống kê được giữa task ở L1.
- **FR18** · `scorer` · Báo cáo hiệu chỉnh: tỉ lệ trùng với cờ thành công của SIMPLE, danh sách episode lệch để kỹ sư xem.
- **FR19** · `diagnosis` · Gom cụm lỗi theo (k, kiểu lỗi, mức); chọn tối đa R đại diện, ngẫu nhiên có ghi hạt giống.
- **FR20** · `diagnosis` · Chạy chuỗi phép kiểm theo thứ tự cố định của spec 6.4–6.8: hệ thống (thiếu tín hiệu; bám lệnh và độ trễ trên stack decoupled WBC; đồng bộ cảm biến; camera chuẩn), khả thi, khoanh vùng, thị giác, vùng phủ (kể cả NGOÀI MIỀN). Kết quả là một chẩn đoán của bảng spec 6.9: 8 lớp gốc cộng LỖI ĐỒNG BỘ, LỖI CALIBRATION, NGOÀI MIỀN (06 mục 4, 5).
- **FR21** · `diagnosis` · Phép kiểm không khả dụng (Q2–Q4) được ghi "gần đúng" hoặc "bỏ qua" trên evidence card, không bỏ im lặng.
- **FR22** · `diagnosis` · Chẩn đoán cụm theo đa số; hòa thì chờ kỹ sư quyết.
- **FR23** · `diagnosis` · Tạo evidence card cho mọi cụm lỗi, đủ trường spec 4.5; mỗi giá trị kèm ngưỡng; có liên kết tới trace và video.
- **FR24** · `decide` · Bảng quyết định spec 6.9 và định lượng spec 6.10 là cấu hình trong RunPlan, không viết cứng trong mã.
- **FR25** · `decide` · Chẩn đoán hệ thống (kể cả LỖI ĐỒNG BỘ, LỖI CALIBRATION) và KHÔNG KHẢ THI sinh phiếu sửa, không tiêu ngân sách dữ liệu. NGOÀI MIỀN và NHẬN THỨC được ghi nhận và báo cáo, không tiêu ngân sách trong PoC. Đóng phiếu sửa xong phải chạy lại baseline của policy hiện tại.
- **FR26** · `decide`, `ledger` · Tỉ lệ sửa được Beta(α, β) theo loại can thiệp, lưu dạng FixRateEvent trong `ledger` (03 ADR-12). `decide` tính g_j = (n_eff_j / N) × f̄_t với n_eff_j = min(m_j, giới hạn mỗi cụm của loại can thiệp), hòa thì ưu tiên bước hỏng sớm hơn; c_j từ đơn giá; chọn tham lam theo g/c trong ngân sách vòng khai trong RunPlan (spec 6.11, 06 mục 3). Ở vòng 1 (prior đều), thứ tự chọn chỉ là đơn giá của loại can thiệp trong các loại mà chẩn đoán cho phép; tính chất này ghi rõ và có unit test. Cập nhật α, β theo FR46.
- **FR27** · `decide` · Kiểm 4 điều kiện dừng của spec 6.13.
- **FR28** · `decide` · Kỹ sư duyệt hoặc ghi đè từng đề xuất; ghi đè bắt buộc có lý do; báo cáo tỉ lệ ghi đè.
- **FR29** · `acquisition` · Điều phối sinh rollout sim qua GeneratorAdapter theo tuyến V3 đã chọn: đúng N_B rollout đạt QA cho nhánh B, trong ngân sách cho C và B-fail; mọi rollout qua QA; đo tỉ lệ sinh đạt.
- **FR30** · `acquisition` · Thu teleop correction và dữ liệu phục hồi qua TeleopSource từ trạng thái lỗi đã lưu. Không có thiết bị (Q6) thì planner hoặc tuyến generator đã chọn (5.5) sinh và gắn cờ "máy sinh".
- **FR31** · `training` · Tăng cường thị giác là phần cố định của recipe, áp như nhau cho mọi nhánh: chỉ dùng biến đổi ảnh đã khai trước (độ sáng, độ tương phản, dịch màu), khai trong RunPlan. Không còn là can thiệp riêng của nhánh C (06 mục 4).
- **FR32** · `acquisition` · Liệt kê tối đa 10 demo gần nhất trong vùng lỗi để kỹ sư kiểm demo mâu thuẫn. Kết quả chỉ ghi vào báo cáo, không loại demo khỏi danh sách 0,7D\* (A₀.₇, B, C dùng cùng danh sách).
- **FR33** · `acquisition` · Chặn cứng chi phí thu dữ liệu của mỗi vòng ở ngân sách vòng; tổng của C, và của B-fail, không vượt B_add.
- **FR34** · `training` · Điều phối fine-tune qua TrainerAdapter: checkpoint gốc hoặc checkpoint cha, release, ρ, S, seed huấn luyện.
- **FR35** · `training` · Kiểm tự động quy tắc công bằng spec 7.3 cho các lần train của một nhánh, gồm cùng checkpoint gốc đã qua Q0, cùng chính sách tăng cường thị giác và cùng danh sách 0,7D\*; lệch thì từ chối chạy.
- **FR36** · `training` · Chạy lưới đường cong hiệu quả dữ liệu (10, 25, 50, 70, 100% N_teleop) và chọn D\* là mức nhỏ nhất để Ψ₀ đạt ≥ 75% trên dev gộp (Cấp 2 BTC), theo luật trần, sàn của spec 7.1. Trước khi chốt, chạy 2 seed ở hai điểm lưới quanh ngưỡng (hoặc nội suy đường cong) để tránh chọn nhầm do may mắn.
- **FR37** · `gate` · Cổng dev theo spec 6.12, siết theo 06 mục 3: mỗi vòng dùng một tập điều kiện mới từ dải hạt giống dev chưa dùng; chạy cả cha và ứng viên, ≥ 3 lượt mỗi điều kiện; A/A test (chạy cha hai lần) cho sàn hồi quy giả; ngưỡng hồi quy = max(5%, sàn A/A); "tăng" phải ≥ 1 sai số chuẩn; cụm được can thiệp cải thiện.
- **FR38** · `gate` · Holdout bị khóa: chỉ chạy khi checkpoint, scorer và cấu hình đã đóng băng (hash khớp); mỗi cặp (nhánh, seed) chạy đúng một lần. Nhánh không phụ thuộc C được chạy sớm ngay khi đóng băng; kết quả niêm phong tới G5.
- **FR39** · `gate` · Thống kê ghép cặp theo spec 7.5, siết theo 06 mục 2: CI 95% bằng **bootstrap phân cấp** (lấy mẫu lại seed huấn luyện, rồi lấy mẫu lại điều kiện trong từng mức), 10.000 lần; mô hình logistic hỗn hợp (hiệu ứng ngẫu nhiên theo điều kiện và theo seed) chạy làm kiểm tra chéo; "cùng chiều ở ≥ 2/3 seed" chỉ là chỉ số phụ. Power analysis ở G2: MDE với 80% lực từ độ lệch giữa seed đo ở E1. Chỉ số chính ở holdout lấy từ cờ thành công của SIMPLE; scorer chỉ cho chỉ số theo bước. Báo riêng từng mức, Level 1 và Level 2 so với 70%. Ước tính nửa độ rộng CI từ phương sai dev; tự kết luận đạt, không đạt hoặc "mô tả" theo tiêu chí trong RunPlan.
- **FR40** · `ledger` · Mọi hoạt động tiêu nguồn lực có mục sổ (spec 4.5, 8.1). Runner, training và acquisition tự ghi GPU-giờ và số rollout; giờ người nhập qua CLI.
- **FR41** · `ledger` · Tổng hợp theo nhánh, vòng, cụm; B_add là chi phí thực đo để tạo đúng N_B rollout của B; tách chi phí thu và chi phí chẩn đoán của nhánh C; số demo người (teleop và correction) theo nhánh; chi phí mỗi điểm % tăng thêm của C so với B và so với B-fail; HT báo kèm hai ràng buộc riêng (phút người, GPU-giờ); tính lợi ích ròng theo spec 8.2 với r_demo, r_debug đo được.
- **FR42** · `reports` · Sinh báo cáo HTML và Markdown tĩnh từ catalog: đường cong hiệu quả dữ liệu, kết quả các nhánh, CI, từng seed, chi phí; chỉ số chính của 06 mục 10 (số demo người để đạt ngưỡng, phút operator mỗi điểm %, sai số dự báo chi phí, số ngày để policy đạt lại ngưỡng); r_debug dạng khoảng; bảng độ nhạy theo đơn giá DENSO và chi phí giờ cell (robot, người giám sát, thời gian dừng). Không có chỗ nhập tay số kết quả.
- **FR43** · `reports` · Trình xem evidence card và sổ chi phí, chỉ đọc, mở offline.
- **FR44** · `reports` · Hỗ trợ HD: đóng gói 20 episode thành tư liệu gốc (mở bằng công cụ chuẩn: Rerun cộng đồ thị mặc định) và gói evidence card; chèn 3–4 card sai cố ý; phân công đối trọng có ≥ 2 người ngoài đội; ghi thời gian và câu trả lời; tính r_debug dạng khoảng và mức tin mù quáng.
- **FR45** · `reports` · Xuất video rollout holdout cho demo, có chú thích điều kiện, mức và kết quả của scorer.
- **FR46** · `gate`, `ledger` · Đo tỉ lệ sửa được có đối chứng (06 mục 3): mỗi cụm lấy điều kiện mới quanh điểm lỗi (bán kính τ_cov / 2, tối đa 5 điều kiện mỗi lỗi, tối đa 30 mỗi cụm); chạy policy cha và ứng viên mỗi bên ≥ 3 lượt; fixed_j = làm tròn(n × (p_ứng viên − p_cha)), kẹp trong [0, n]; α += fixed_j, β += n − fixed_j; ghi FixRateEvent.
- **FR47** · `reports` · Xuất **khuyến nghị thu dữ liệu định lượng** (Cấp 3 BTC) từ đầu ra bước Decide cộng sổ chi phí: theo loại lỗi và loại can thiệp, số lượng, chi phí ước tính và thực đo, điểm % kỳ vọng và đo được.

Yêu cầu thêm ở bản 0.4 (design 23/10/2026; story ở Epic 9):

- **FR48** · `contracts`, `catalog` · Định dạng episode chung cho mọi nguồn: `source_kind`, `action_quality` (measured, planned, retargeted, pseudo, none), `deid_status`, `synthetic_tier`, `segments.parquet`; `action_layout` trong cấu hình Embodiment ánh xạ nhóm action vào khung 36 chiều của Ψ₀ kèm mask. Episode `pseudo` hoặc `retargeted` chỉ vào train khi RunPlan cho phép.
- **FR49** · `flywheel-ingest` · Pipeline teleop 6 tầng (ingest, normalize, annotate, QA, release, export) cho psi-data và teleop DENSO; đồng bộ thời gian theo sự kiện chung; cắt đoạn theo bước task; QA riêng nguồn; export LeRobot kèm `stats_psi0.json` và contract test bằng loader Ψ₀.
- **FR50** · `flywheel-ingest` · Pipeline video egocentric với hai phương án thu (E-A chỉ RGB, E-B có tracking tay và đầu); che danh tính trước mọi bước khác; cắt đoạn; pose tay và camera; xuất định dạng H-RDT; dùng cho probe, mẫu sinh, cấu trúc task, và continued pretraining stage 1 tùy chọn.
- **FR51** · `decide`, `GeneratorAdapter` · Synthetic chia tầng S1 (planner), S2 (biến thể teleop), S3 (Cosmos Transfer, giữ action gốc), S4 (Cosmos Predict, action suy ra); mỗi tầng là một loại can thiệp có đơn giá và tỉ lệ sửa được riêng; mở theo thứ tự S1 → S2 → S3, S4 sau cùng; không sinh với tham số Level 1, Level 2.
- **FR52** · `flywheel-nim` · `NimClient` định tuyến theo `data_class`: `restricted`, `internal` chỉ đi NIM tự host; `public` được đi API hosted nếu bật. Mỗi lời gọi ghi `LedgerEntry` và phiên bản model; danh sách model nằm trong cấu hình có hash.
- **FR53** · `gate`, `flywheel-psi0` · Probe P1 (hiểu cảnh), P2 (dự đoán action token), P3 (action offline theo nhóm và theo vị trí trong chunk), P4 (giữ năng lực) đóng băng có hash; chạy trên `pre.*`, `postpre.*` và mọi checkpoint mới.
- **FR54** · `TrainerAdapter`, `reports` · Mỗi lần train ghi loss tổng, loss theo nhóm action và theo vị trí trong chunk, chuẩn gradient theo khối, phương sai dự đoán theo chiều, tài nguyên; checkpoint trung gian tự chạy P3 và P4. Bộ phát hiện lỗi train T1–T8 và lỗi offline O1–O4 theo design mục 7.2.
- **FR55** · `diagnosis` · Bước 4b quy lỗi về stage của Ψ₀ (nhận thức, học action, lỗi tích lũy, quên) từ probe; chỉ hiện trên card, kỹ sư xác nhận. Kiểm hệ thống cho robot DENSO theo nhóm đế, cột nâng, tay, gripper (R1–R6).
- **FR56** · `flywheel-isaac` · `DensoIsaacSim` nhận robot DENSO thật hoặc robot thay thế qua cấu hình; robot thay thế dựng tham số; lệnh `fw embodiment score` chấm giống theo điều kiện bắt buộc và 6 điểm thành phần, mỗi điểm ≥ 0,95, ghi rõ cơ sở chấm; so stage 2 theo S2-A, S2-B, S2-C.
- **FR57** · `flywheel-tasks` · `DensoTrayToMachine`: 6 bước (vào vị trí, tiếp cận, gắp, mang, đặt, nhả và lui), 10 kiểu lỗi kèm lớp lỗi chung; tham số lấy từ thông số DENSO.

### 2.2 Yêu cầu phi chức năng

- **NFR1 · Tái lập được.** Pin phiên bản mọi thành phần: lockfile Python, môi trường Isaac Sim 4.5, commit SIMPLE, revision checkpoint Ψ₀, revision gói psi-data. Episode, release, checkpoint và báo cáo có content hash. Ghi mọi seed: hạt giống điều kiện, seed huấn luyện, seed chọn đại diện, seed bootstrap. Các bước tính thuần (QA, scorer trên trace có sẵn, chẩn đoán từ log, decide, thống kê) chạy lại cho kết quả trùng. Độ không tất định của rollout trong simulator được đo ở G0 và ghi vào RunPlan.
- **NFR2 · Tách lõi khỏi adapter.** Mã lõi không import SIMPLE, Isaac Sim, MuJoCo, Ψ₀ hay thư viện của một model cụ thể; CI kiểm bằng luật import. Toàn bộ test lõi chạy trên CPU với adapter giả. Mỗi adapter qua bộ contract test chung.
- **NFR3 · Chạy offline.** Sau khi tải checkpoint, gói dữ liệu và môi trường, mọi lệnh chạy không cần internet. Không dùng dịch vụ cloud bắt buộc. L0 không dùng MLflow (trùng ledger) hay công cụ theo dõi thí nghiệm riêng (NFR12). GPU thuê chỉ là nơi chạy job, không phải phụ thuộc của lõi.
- **NFR4 · Chi phí ghi đầy đủ.** Lệnh tiêu GPU hoặc chạy rollout mà không ghi được mục sổ thì báo lỗi. Đơn giá là giả định có nguồn (spec 8.1), đổi trong RunPlan, không viết cứng. Báo cáo liệt kê mọi lần chạy thiếu mục sổ; con số này phải bằng 0.
- **NFR5 · Không rò holdout.** Catalog từ chối đưa episode có hạt giống dev hoặc holdout vào release train. Bộ sinh từ chối điều kiện ngoài miền train và tham số Level 1, Level 2. Danh sách holdout có hash; mọi lần đọc holdout được ghi log. Điều kiện dev hoặc holdout gần trùng train theo khoảng cách bị cách ly (FR10); dải hạt giống dev và holdout rời với dải tác giả (FR9). Checkpoint gốc có nguồn gốc ghi ở thực thể Source (Q0); RunPlan của E1 và các nhánh không trỏ `simple-checkpoints` hoặc `sonic-checkpoints`, hai thư mục này chỉ dùng để tái tạo số công bố ở G0. Rò holdout vô hiệu hóa run liên quan.
- **NFR6 · Quyền dữ liệu.** Mỗi episode có trường giấy phép và mức phân loại (công khai, nội bộ, hạn chế). Release ghi tổng hợp giấy phép. Giấy phép của psi-data và checkpoint Ψ₀ được kiểm và ghi ở G0 (hiện chưa kiểm). Dữ liệu, checkpoint và PDF không commit vào git.
- **NFR7 · Mở rộng L1–L3 không đổi mô hình dữ liệu.** Schema có sẵn từ L0: `task_id`, `embodiment_id`, `site_id` là cột thường có giá trị mặc định (06 mục 9); miền (sim hoặc thật), mô tả không gian state và action theo embodiment, nguồn thu; lớp lỗi chung trong định nghĩa kiểu lỗi. Trường mở rộng khác để trong `meta`. Vector điều kiện khai theo task. Tỉ lệ sửa được lưu với khóa (task, chẩn đoán, loại can thiệp); PoC gộp theo loại can thiệp như spec. Kiểm bằng test: thêm TaskDefinition F1 và một embodiment giả mà không migration schema.
- **NFR8 · Vừa phần cứng của đội.** Các lệnh lõi, trừ train và rollout, chạy được trên máy RTX 3060. Giả định khối lượng PoC dưới 20.000 episode.
- **NFR9 · Bền khi bị ngắt.** Job dài (rollout, train, sinh sim) chạy tiếp được; chạy lại một lệnh không tạo bản ghi trùng.
- **NFR10 · Trung thực số liệu.** Mọi con số trong báo cáo trỏ về ID của run nguồn. Kết quả âm, ứng viên bị từ chối và mẫu bị loại không bị xóa.
- **NFR11 · Bền dữ liệu.** `catalog/`, `releases/`, vault holdout và ledger được backup hằng ngày sang máy thứ hai; diễn tập khôi phục một lần trước G3 (story 2.8). Khôi phục không tạo lần đọc holdout mới.
- **NFR12 · Đơn giản ở L0 (L0-lite, 06 mục 9).** Hoãn MLflow, Streamlit, fsspec S3, revision của evidence card, phân vùng theo ngày và lệnh dựng lại chỉ mục. Giữ: hash release, RunPlan, guard chia tập, khóa holdout dạng tệp có hash cộng test CI, ledger JSONL, trace Parquet, một chỉ mục DuckDB.
- **NFR13 · Riêng tư và định tuyến dữ liệu (bản 0.4).** Video egocentric qua bước che danh tính trước mọi xử lý khác; `catalog` chặn episode có `deid_status = raw` rời bước Annotate. Dữ liệu `restricted` hoặc `internal` không bao giờ gửi tới API hosted bên ngoài. Khi chuyển phần tự xây sang API để kịp tiến độ (04 mục 4.9), quy tắc này không được nới; mỗi lần chuyển ghi Decision và chi phí.

## 3. Mục tiêu giao diện

Giao diện tối giản: **CLI + báo cáo tĩnh + trình xem tĩnh**.

| Thành phần | Dùng để | Người dùng chính |
|---|---|---|
| CLI `fw` (đã chốt ở 03) | Mọi thao tác: nạp, QA, chia tập, release, train, đánh giá, chẩn đoán, duyệt, thu, cổng, holdout, sổ chi phí | Cả đội |
| Báo cáo HTML và Markdown | Đường cong hiệu quả dữ liệu, so sánh nhánh, HS, HT, HD, chi phí, khuyến nghị thu dữ liệu định lượng | Đội, giám khảo |
| Trình xem evidence card | Danh sách cụm của một vòng; từng thẻ với phép kiểm, ngưỡng, video, quyết định | Kỹ sư robot learning, người tham gia HD |
| Trình xem sổ chi phí | Lọc theo nhánh, vòng, cụm, loại nguồn lực | Đội, giám khảo |

Nguyên tắc:

- Trình xem chỉ đọc. Duyệt và ghi đè đề xuất làm qua CLI (`fw review`), để catalog chỉ có một đường ghi.
- HTML tự chứa: nhúng CSS, JS và ảnh, video là file cục bộ, không gọi CDN, mở được bằng `file://` khi không có mạng.
- Trong HD, mọi người tham gia thấy cùng một dạng evidence card. Đối thủ của card là công cụ chuẩn (Rerun cộng đồ thị mặc định) mở trên cùng tư liệu gốc (video, đồ thị, log), không phải gói log do đội tự đóng gói. Rerun là công cụ của người tham gia HD, không phải giao diện của sản phẩm.

**Vì sao không xây web app lớn trong 12 tuần:**

1. Điều cần chứng minh nằm ở lõi và phép đo HS, HT, HD, không ở giao diện.
2. Đội 5 người, không ai làm frontend. Mỗi tuần làm web app là một tuần bớt khỏi Data Core và chẩn đoán.
3. Web app kéo theo server, đăng nhập, phân quyền, trạng thái đồng thời. Đó là phạm vi L4.
4. Người dùng 12 tuần là chính đội và giám khảo. Báo cáo tĩnh đủ để đọc, đính kèm và nộp.
5. Báo cáo sinh từ catalog thì tái lập được. Giao diện có trạng thái riêng dễ lệch với dữ liệu.

## 4. Giả định kỹ thuật

**Kiểu kiến trúc.** Monorepo Python. Lõi là thư viện Python cộng CLI. Mỗi adapter là package riêng, cài theo recipe.

**Ranh giới tiến trình (Architect xác nhận).** Isaac Sim 4.5 dùng Python đi kèm của nó; Ψ₀ có thể cần phiên bản PyTorch và CUDA khác. Giả định lõi gọi adapter nặng qua ranh giới tiến trình (lệnh con hoặc RPC cục bộ) và trao đổi qua file trong kho dữ liệu, không import trực tiếp.

**Cấu trúc repo (đã chốt ở 03 mục 7.1).** Thư mục mới, không đụng `website/` và `deliverables/`:

```text
packages/flywheel/          lõi: contracts, store, 12 module, testing (contract test), cli (lệnh fw)
packages/flywheel-fakes/    adapter giả, task đồ chơi
packages/flywheel-tasks/    TaskDefinition: G1BendPickAndPlace, G1BendPick (task dự phòng F1)
packages/flywheel-simple/   SimpleSimulator, SimpleMPGenerator, SimpleTeleop
packages/flywheel-psi0/     Psi0Policy, Psi0Trainer
packages/flywheel-lerobot/  LeRobotPolicy, LeRobotTrainer (ACT, Diffusion Policy)
configs/                    runplans, embodiments, tasks, thresholds, pricebook
docs/sop/                   SOP thu và kiểm dữ liệu
```

**Lưu trữ (03 mục 7.2, cắt về L0-lite theo 06 mục 9).** Episode và trace là bundle Parquet và MP4; ledger là JSONL; metadata là bảng Parquet append-only với một chỉ mục DuckDB (03 ADR-04). File lớn trong kho theo content hash, đường dẫn cấu hình được, nằm ngoài git. Không có database server. Ở L0 chưa phân vùng theo ngày, chưa có lệnh dựng lại chỉ mục, chưa có fsspec S3 (NFR12). Backup hằng ngày theo NFR11.

**Adapter.** Mỗi adapter là một Protocol có số phiên bản và cờ khả năng, tên theo 03 mục 5.2: `restore_state`, `visual_override`, `fault_injection` (SimCapabilities) và `plan` (GenCapabilities). `diagnosis` đọc cờ để chọn phép kiểm, không dò lỗi lúc chạy.

**Chiến lược test.**

- Unit test cho lõi: phép kiểm QA, vị từ scorer trên trace tổng hợp, bảng quyết định, chọn tham lam (kể cả tính chất "vòng 1 xếp theo đơn giá"), cập nhật Beta có đối chứng, bootstrap phân cấp. Chạy trên CPU trong CI ở mỗi lần push.
- Test mô phỏng cho thống kê và cổng: độ phủ CI khi có phương sai seed (3.7); A/A test của cổng dev trên adapter giả (3.6).
- Adapter giả: FakeSimulator là một thế giới đơn giản có vector điều kiện và vùng lỗi biết trước; FakePolicy, FakeTrainer có hành vi theo kịch bản. Một vòng Failure → Data đầy đủ chạy trên adapter giả trong CI, dưới 10 phút.
- Golden test cho chẩn đoán: mỗi lỗi cấy trên adapter giả phải ra đúng chẩn đoán; episode sạch không ra lớp hệ thống. Bộ này dùng lại cho 10 lỗi cấy của HD.
- Contract test: cùng một bộ test chạy trên adapter giả và adapter thật.
- GPU smoke test: chạy tay hoặc theo lịch trên máy RTX 5090; 1 episode SIMPLE và 1 bước train ngắn.
- Snapshot test cho evidence card và báo cáo. Luật import trong CI (NFR2).

**Định nghĩa hoàn thành chung của story.** Test pass trong CI; lệnh mới có `--help`; mọi lần chạy tiêu nguồn lực có mục sổ; không đọc holdout ngoài 3.8 và 8.3; có ghi chú ngắn trong tài liệu module. Bản đầy đủ (DoR, DoD cho [Lõi] và [Adapter]) ở 04 mục 5.

**Năng lực (giả định).** Lập kế hoạch ở **70% năng lực** (06 mục 9); 30% còn lại là đệm cho việc chưa biết và tích hợp lần đầu (05 KT1). Ước thô của PM: 5 người × 60 ngày làm việc, trừ khoảng 30% cho pitch, họp và chờ máy, còn khoảng 210 người-ngày; mức kế hoạch 70% là khoảng 147 người-ngày. Story trung bình 3,5 ngày; ngoại lệ là 5.5 (5–20 ngày tùy tuyến) và 7.10 (khoảng 6 ngày). Lát dọc trên SIMPLE phải chạy trước tuần 4.

| Mảng | Người | Số story | Ước người-ngày | Mức kế hoạch 70% |
|---|---|---|---|---|
| Data-Platform | 2 | 24 | khoảng 87 | khoảng 59 |
| Simulation | 2 | 21 (thêm 7.9 tùy chọn) | khoảng 75–90 | khoảng 59 |
| Robot Learning | 1, kiêm trưởng nhóm; Châu đồng sở hữu Ψ₀ (04) | 11 | khoảng 39 | khoảng 29 |
| Tổng | 5 | 56 (thêm 1 tùy chọn) | khoảng 200–215 | khoảng 147 |

Theo ước thô này, phạm vi mặc định cần khoảng 1,4–1,5 lần mức kế hoạch. Ước theo giờ của 04 mục 0 (khoảng 830 giờ cho 52 story của bản 0.2, có AI viết mã) thấp hơn nhiều và là số dùng để quyết. SM cộng giờ của 5 story mới (mục 9), nhân hệ số k đo sau Sprint 1 và so với 70% năng lực ròng của 04; nếu vẫn vượt, áp thứ tự cắt ở mục 8 từ đầu dự án, không đợi trễ. Bảng trên là gợi ý của PM. Phân công thực tế, người dự phòng và tải theo giờ nằm ở 04 mục 3 và 4.

## 5. Danh sách epic

| Epic | Tên | Cổng | Tuần | Giá trị dùng được khi xong |
|---|---|---|---|---|
| 1 | Nền tảng và tái tạo recipe | G0 | 1–2 | Biết recipe chạy được không và tốn bao nhiêu; có câu trả lời Q0–Q6 và V3 (hạn ngày 5); khung lõi chạy end-to-end trên adapter giả |
| 2 | Data Core | G1, G2 | 1–6 | Nạp, QA, lineage, chia tập, release, sổ chi phí và backup dùng được cho mọi dataset; là xương sống của SOP và của "DENSO Data Model" |
| 3 | Đánh giá | G1, G4, G5 | 3–8 | Đánh giá giống nhau cho mọi nhánh: scorer từng bước, cổng dev có A/A, thống kê phân cấp, holdout bị khóa |
| 4 | Baseline và đường cong hiệu quả dữ liệu | G1, G2 | 4–6 | Phần chính của báo cáo so sánh phương pháp; chọn được D\*; có power analysis |
| 5 | Sinh dữ liệu sim, nhánh B | G3 | 3–8 | Kiểm được HS; rollout sinh cùng bộ điều khiển với teleop; B_add là chi phí thực đo của N_B rollout đã chốt |
| 6 | Chẩn đoán | G4 | 5–10 | Evidence card giúp debug ngay cả khi chưa có vòng quyết định |
| 7 | Quyết định và thu dữ liệu, nhánh C | G4 | 6–10 | Vòng flywheel đầy đủ; kiểm được HT (HTa, HTb); bằng chứng flywheel học trên ACT |
| 8 | Thí nghiệm, báo cáo, SOP, demo | G4–G6 | 9–12 | Ba đầu ra của đề H1 và kết luận HS, HT, HD |
| 9 | Dữ liệu đa nguồn và robot DENSO (bản 0.4) | G1–G4 | 1–10 | Pipeline ba nguồn, synthetic qua NIM, đánh giá theo stage của Ψ₀, robot DENSO hoặc robot thay thế với task khay → máy |

**Điều chỉnh so với thứ tự gợi ý, và lý do:**

1. **Sổ chi phí lõi lên Epic 2.** B_add của nhánh B (Epic 5) phải đo từ sổ. GPU-giờ của G0 cũng cần chỗ ghi. Để ledger tới Epic 7 thì chi phí của 6 tuần đầu bị ghi tay hoặc mất.
2. **Epic 1 có khung lõi chạy trên adapter giả.** Mảng Data-Platform làm lõi từ tuần 1, không chờ SIMPLE và Ψ₀ cài xong.
3. **Mã của Epic 6 và 7.1–7.3 viết và kiểm trên adapter giả từ tuần 5–6.** Chỉ chạy trên Ψ₀ khi có π₀ (nhánh A₀.₇) ở G3.
4. **RunPlan thuộc catalog (Epic 2)** vì mọi epic sau đọc nó.
5. **Tuyến generator (5.5) bắt đầu từ tuần 3**, ngay khi 1.9 chốt tuyến, chạy song song Epic 2–4, vì nhánh B ở G3 cần nó.
6. **F-ACT (7.10) và B-fail (7.11) chạy trên ACT**, không chiếm GPU của Ψ₀; Ψ₀ mặc định chỉ 1 vòng C.

Thứ tự epic là thứ tự giá trị và cổng. Ba mảng chạy song song: Simulation làm SIMPLE và adapter; Robot Learning làm Ψ₀, train và thí nghiệm; Data-Platform làm lõi.

## 6. Chi tiết epic

Quy ước nhãn: **[Lõi]** là story có sản phẩm nằm trong lõi hoặc đo lõi, dùng lại được cho recipe khác. **[Adapter]** là story gắn với một model, simulator, robot hoặc task cụ thể, gồm cả các lần chạy thí nghiệm của recipe Ψ₀ + SIMPLE / G1. Mỗi story vừa 1 người trong 2–5 ngày. Dòng đầu mỗi story ghi: nhãn · mảng gợi ý · phụ thuộc · cổng.

### Epic 1 · Nền tảng và tái tạo recipe (G0)

Mục tiêu: môi trường pin phiên bản; Ψ₀ trên SIMPLE tái tạo được số công bố; có câu trả lời Q0–Q6 và V3; khung lõi chạy end-to-end trên adapter giả.

**1.1 · Khung repo, CLI và CI** · [Lõi] · Data-Platform · Phụ thuộc: không · G0. Là kỹ sư data, tôi muốn một monorepo có CLI và CI chạy trên CPU, để cả đội thêm module mà không phá nhau.
1. `fw --version` in phiên bản và commit.
2. CI chạy lint, kiểm kiểu, pytest và luật import (lõi không import adapter) ở mỗi lần push.
3. Lockfile được commit; dựng lại môi trường lõi bằng một lệnh.

**1.2 · Môi trường SIMPLE pin phiên bản** · [Adapter] · Simulation · Phụ thuộc: không · G0. Là kỹ sư simulation, tôi muốn dựng SIMPLE trên Isaac Sim 4.5 bằng một script, để mọi máy chạy cùng phiên bản.
1. Script ghi commit SIMPLE, phiên bản Isaac Sim, driver và CUDA.
2. Chạy được một episode của task chính và lưu video.
3. Đo thời gian mỗi episode đánh giá (một phần Q5).

**1.3 · Tái tạo đánh giá Ψ₀** · [Adapter] · Robot Learning · Phụ thuộc: 1.2 · G0. Là kỹ sư robot learning, tôi muốn chạy checkpoint Ψ₀ công bố trên một task SIMPLE đã công bố, để biết recipe có tái tạo được không.
1. Chạy 30 lượt mỗi mức ở Level 0, 1, 2 (06 mục 2).
2. Tiêu chí đạt thay cho "lệch không quá 1/10": ở mỗi mức, kiểm nhị thức một phía (α = 0,05) không cho thấy tỉ lệ thành công thấp hơn số công bố; ghi p-value từng mức. Nếu thấp hơn có ý nghĩa, ghi nguyên nhân nghi ngờ.
3. Ghi đỉnh VRAM khi suy luận và phân vị 99 độ trễ chu kỳ (nền cho τ_lat); ghi giao thức `act()` (V2 ở 03 mục 3.3).
4. Chạy cùng 20 điều kiện hai lần, ghi tỉ lệ kết quả đổi chiều (NFR1, 03 mục 8.2).
5. Q0: chọn checkpoint gốc cho E1 và mọi nhánh trong nhóm `pre.*` hoặc `postpre.*`, đã xác nhận không train trên dữ liệu SIMPLE hoặc sonic của task chính (hỏi PSI Lab); ghi nguồn gốc (provenance) và bằng chứng vào thực thể Source. `simple-checkpoints` và `sonic-checkpoints` chỉ dùng để tái tạo số công bố ở AC 1–2, không dùng cho E1 và các nhánh (06 mục 8).

**1.4 · Đo chi phí fine-tune Ψ₀ (Q5)** · [Adapter] · Robot Learning · Phụ thuộc: không (dùng chung môi trường Ψ₀ với 1.3) · G0. Là kỹ sư robot learning, tôi muốn đo VRAM và GPU-giờ của fine-tune Ψ₀, để chốt phần cứng và số seed trước khi lập kế hoạch.
1. Fine-tune ngắn trên RTX 5090; hết bộ nhớ thì thử LoRA hoặc đóng băng VLM, rồi A100 80 GB thuê.
2. Ước tính GPU-giờ cho S bước và cho cả khối lượng ở spec mục 9; ghi vào CSV theo cột của mục sổ chi phí.
3. Ghi lựa chọn cấu hình, phần cứng, số seed vào RunPlan nháp.

**1.5 · Trả lời Q2, Q3, Q4** · [Adapter] · Simulation · Phụ thuộc: 1.2 · G0. Là kỹ sư simulation, tôi muốn kiểm planner, lưu và khôi phục trạng thái, và tách ngẫu nhiên hóa hình ảnh, để biết phép kiểm chẩn đoán nào chạy được.
1. Q2: thử motion planning của SIMPLE cho task chính; ghi kết quả. Phương án khi planner khác bộ điều khiển với teleop thuộc 1.9 và 5.5.
2. Q3: lưu trạng thái giữa episode, khôi phục, chạy tiếp; so với chạy liền một mạch.
3. Q4: đổi ánh sáng và vật liệu mà giữ nguyên vật lý.
4. Ba câu trả lời thành giá trị cờ khả năng của SimulatorAdapter.
5. Chuyển sang story 1.9: V3 tách thành story riêng có hạn ngày 5 của Sprint 1 (06 mục 1, 22/10/2026). Số AC 1–4 giữ nguyên.

**1.6 · Phân tích gói psi-data, trả lời Q1 và Q6** · [Adapter] · Data-Platform · Phụ thuộc: không · G0. Là kỹ sư data, tôi muốn biết gói task chính có bao nhiêu demo teleop dùng được và đội có thiết bị teleop không, để chọn task và cách thu correction.
1. Đếm N_teleop đạt QA sơ bộ cho task chính và task F1.
2. Ghi định dạng, tần số, trường state và action, và gói có chứa hạt giống điều kiện hay không.
3. Ghi câu trả lời Q6. Nếu N_teleop < 50, đề xuất chuyển task theo spec 2.4.
4. Ghi `codebase_version` LeRobot (V1) và trạng thái giấy phép của psi-data, psi-model, cảnh và tài sản 3D (V9, NFR6).

**1.8 · Tín hiệu từng bước và tập điều kiện đánh giá (V6, V7)** · [Adapter] · Simulation · Phụ thuộc: 1.2 · G0. Là kỹ sư simulation, tôi muốn biết SIMPLE cho lấy tín hiệu nào và sinh tập điều kiện thế nào, để scorer và chia tập không dựa trên giả định.
1. Liệt kê tín hiệu lấy được khi rollout task chính, đối chiếu với tín hiệu scorer cần cho 6 bước và 9 kiểu lỗi (spec 5).
2. Kiểm `reset(seed)` có tất định không; sinh được tập dev 90 và holdout 150 theo định dạng `simple-eval` không.
3. Câu trả lời ghi vào dòng V6, V7 của 03 mục 3.3.

**1.7 · Khung lõi chạy trên adapter giả** · [Lõi] · Data-Platform · Phụ thuộc: 1.1 · G0. Là kỹ sư data, tôi muốn một vòng rỗng chạy → chấm → chẩn đoán → quyết định → thu → train → cổng trên adapter giả, để các module lõi phát triển song song với G0.
1. Có Protocol v0 cho SimulatorAdapter, PolicyAdapter, TrainerAdapter, GeneratorAdapter, TeleopSource, TaskDefinition, kèm cờ khả năng.
2. FakeSimulator, FakePolicy, FakeTrainer chạy trên CPU.
3. Một lệnh chạy vòng rỗng end-to-end trong CI dưới 10 phút.

**1.9 · Bộ điều khiển teleop và motion planning (V3)** · [Adapter] · Simulation · Phụ thuộc: 1.2 · G0, **hạn ngày 5 của Sprint 1**. Là kỹ sư simulation, tôi muốn biết rollout motion planning có cùng bộ điều khiển với demo teleop của task chính không, để nhánh B, C và B-fail có dữ liệu sinh hợp lệ hoặc chọn sớm tuyến thay thế.
1. Trước ngày 5: bảng đối chiếu demo teleop task chính và rollout MP (env, robot, bộ điều khiển, không gian state, không gian action, tần số điều khiển, camera); mỗi ô có nguồn là file cấu hình hoặc mã SIMPLE. Bảng ghi rõ System-0 của task chính là decoupled WBC (`g1_sonic`, env `SonicLocoManipEnv`) và AMO là bộ điều khiển của pipeline MP.
2. Cùng bảng cho cặp task F1. F1 chỉ được ghi là dự phòng cho Q2 khi bảng này xác nhận cặp task của F1 cùng bộ điều khiển; nếu không, F1 chỉ giữ vai trò kiểm khả năng tổng quát của lõi.
3. Cùng bộ điều khiển hoặc có ánh xạ tường minh: ghi ánh xạ, đề xuất `embodiment_id` cho từng nguồn; 5.5 đóng với ghi chú "không cần".
4. Khác bộ điều khiển: thử song song T1 và T2 trong tuần 1–2 (06 mục 1), ghi tỉ lệ thành công mỗi tuyến; chốt tuyến cuối tuần 2 (review G0, chậm nhất S2 ngày 3). T3, T4 chỉ chọn theo cây ở 04 mục 1.3.
5. Ghi kịch bản V3 âm cộng Q6 âm vào RunPlan nháp và mục rủi ro: C chỉ còn kiểm demo mâu thuẫn, HT sụp, báo cáo phải nêu.
6. Kết luận cập nhật dòng V3 của 03 mục 3.3 và giá trị cờ `GenCapabilities.plan`.

### Epic 2 · Data Core (G1)

Mục tiêu: dữ liệu vào hệ thống có QA, lineage, chia tập đúng, release bất biến; mọi chi phí có mục sổ; kho được backup hằng ngày. Đây là phần lõi của "DENSO Data Model".

**2.1 · Mô hình dữ liệu và RunPlan** · [Lõi] · Data-Platform · Phụ thuộc: 1.1 (dùng chung `contracts` với 1.7) · G1. Là kỹ sư data, tôi muốn schema có phiên bản cho mọi thực thể của catalog, để dữ liệu từ nhiều nguồn và nhiều vòng truy được nguồn gốc.
1. Có các thực thể của FR1 theo L0-lite (khoảng 12 thực thể, trường mở rộng trong `meta`) với ID bất biến và content hash; `task_id`, `embodiment_id`, `site_id` là cột thường có giá trị mặc định; có trường miền, giấy phép, mức phân loại.
2. RunPlan chốt được; sau khi chốt, muốn sửa phải tạo bản mới kèm lý do.
3. Test: thêm TaskDefinition thứ hai và một embodiment giả mà không đổi schema.

**2.2 · Nhập gói psi-data vào catalog** · [Lõi] · Data-Platform · Phụ thuộc: 1.6, 2.1 · G1. Là kỹ sư data, tôi muốn nạp gói psi-data của task chính và F1 vào catalog, để mọi bước sau dùng chung một định dạng.
1. Chuẩn hóa đơn vị, khung tọa độ, timestamp; ghi revision gói và giấy phép. Bộ đọc LeRobot nằm trong `catalog`; ánh xạ trường riêng của psi-data nằm trong `configs/embodiments/` (03 mục 6.1).
2. Gói không có hạt giống điều kiện thì suy vector điều kiện từ trạng thái đầu episode và gắn cờ "suy ra".
3. Nạp lại cùng gói cho cùng hash.

**2.3 · QA bắt buộc** · [Lõi] · Data-Platform · Phụ thuộc: 2.1, 2.2 · G1. Là kỹ sư data, tôi muốn 7 phép kiểm QA chạy trên mọi episode, để dữ liệu hỏng không vào release mà vẫn giữ được bằng chứng.
1. Mỗi phép kiểm của spec 4.4 là một hàm có unit test cho cả đạt và trượt.
2. Ngưỡng hiệu chỉnh từ demo teleop thành công và lưu trong RunPlan.
3. Mẫu bị loại giữ lý do và chi phí; có báo cáo QA theo nguồn.

**2.4 · Vector điều kiện và vùng phủ** · [Lõi] · Simulation · Phụ thuộc: 2.1 · G2 (PO dời từ G1; τ_cov chỉ cần từ G3). Là kỹ sư simulation, tôi muốn đo khoảng cách giữa các điều kiện, để biết một lỗi có nằm ngoài vùng dữ liệu đã phủ không.
1. Vector điều kiện theo spec 4.2, khai theo task; chuẩn hóa theo khoảng train; Euclid có trọng số và Hamming.
2. kNN với K = 5; τ_cov là phân vị 95 leave-one-out; test trên dữ liệu tổng hợp có đáp án.
3. Lấy mẫu điều kiện đều trong miền train và trong bán kính quanh một điểm, theo seed; có chế độ quanh mọi điều kiện lỗi dev cho B-fail (FR11).
4. Guard gần trùng theo khoảng cách: điều kiện dev hoặc holdout có khoảng cách tới train dưới phân vị 1 của khoảng cách láng giềng trong train thì bị cách ly; chạy trước khi E1 đánh giá trên dev; canary gần trùng bị chặn (06 mục 8).
5. Hàm "trong miền train" theo khoảng train từng chiều, dùng chung cho bộ sinh (NFR5) và chẩn đoán NGOÀI MIỀN (6.2).

**2.5 · Chia tập theo hạt giống điều kiện** · [Lõi] · Data-Platform · Phụ thuộc: 2.1 · G1. Là kỹ sư robot learning, tôi muốn train, dev và holdout tách theo hạt giống điều kiện, để không rò dữ liệu giữa các tập.
1. Ba dải hạt giống rời nhau ghi vào RunPlan, và rời với dải tác giả dùng cho psi-data và `simple-eval` (không biết dải của tác giả thì chọn dải lệch xa và dựa vào guard khoảng cách ở 2.4); dev 30 × 3 mức; holdout 50 × 3 mức; dải dev còn đủ chỗ cho một tập cổng mới mỗi vòng (3.6).
2. Catalog từ chối episode có hạt giống dev hoặc holdout khi tạo release train (có test).
3. Danh sách holdout có hash; mọi lần đọc được ghi log.

**2.6 · Release bất biến và đếm demo gốc** · [Lõi] · Data-Platform · Phụ thuộc: 2.3, 2.5 · G1. Là kỹ sư robot learning, tôi muốn tạo release từ release cha cộng dữ liệu mới, để mỗi lần train trỏ về đúng một tập dữ liệu.
1. `fw release create` chỉ nhận episode đạt QA; release có hash và trỏ về release cha.
2. Đếm riêng demo teleop, teleop correction, rollout sim, biến thể; tính r_demo.
3. Tạo tất định từ seed các tập con 10, 25, 50, 70, 100% và 0,7D\*.

**2.7 · Sổ chi phí lõi** · [Lõi] · Data-Platform · Phụ thuộc: 2.1 · G1. Là kỹ sư data, tôi muốn mọi hoạt động tiêu nguồn lực tự vào sổ chi phí, để B_add và chi phí nhánh C là số đo chứ không phải ước đoán.
1. Mục sổ đủ trường spec 4.5; đơn giá giả định spec 8.1 nằm trong RunPlan, có nguồn; ước tính và thực đo ghi tách riêng (cho sai số dự báo chi phí ở 7.8).
2. API ghi tự động cho runner, training, acquisition; `fw ledger add` cho giờ người; nhập được CSV từ G0.
3. Lệnh tiêu nguồn lực mà không ghi được mục sổ thì báo lỗi (có test).

**2.8 · Backup hằng ngày và diễn tập khôi phục** · [Lõi] · Data-Platform · Phụ thuộc: 2.1, 2.7 · G2 (diễn tập trước G3). Là kỹ sư data, tôi muốn kho dữ liệu được backup hằng ngày sang máy thứ hai, để máy 5090 hỏng không làm mất catalog, release, holdout và sổ chi phí.
1. Job backup chạy hằng ngày, chép `catalog/`, `releases/`, vault holdout và ledger sang máy thứ hai; mỗi lần ghi thời điểm và hash.
2. Bản backup của vault giữ nguyên khóa và log đọc; khôi phục không tạo lần đọc holdout mới (có test).
3. Diễn tập khôi phục một lần trước G3 trên máy thứ hai: mở được catalog, hash release và tổng ledger khớp bản gốc.
4. Backup trễ quá 1 ngày thì hiện cảnh báo trong báo cáo tiến độ.

### Epic 3 · Đánh giá (G1, G4, G5)

Mục tiêu: chạy và chấm policy giống nhau cho mọi nhánh; có cổng dev, thống kê ghép cặp, holdout bị khóa.

**3.1 · SimulatorAdapter và PolicyAdapter cho SIMPLE và Ψ₀** · [Adapter] · Simulation · Phụ thuộc: 1.5, 1.7 · G1. Là kỹ sư simulation, tôi muốn SIMPLE và Ψ₀ cắm vào lõi qua Protocol, để lõi chạy rollout mà không biết simulator nào.
1. Hai adapter qua bộ contract test chung.
2. Trích vector điều kiện và hạt giống điều kiện từ tham số ngẫu nhiên hóa của SIMPLE.
3. Cờ khả năng đặt theo kết quả 1.5.

**3.2 · Runner và trace** · [Lõi] · Simulation · Phụ thuộc: 2.1, 2.7 (chạy trên SIMPLE cần 3.1) · G1. Là kỹ sư robot learning, tôi muốn chạy policy trên một danh sách điều kiện và lưu trace đầy đủ, để chấm và chẩn đoán dùng cùng một bản ghi.
1. Trace đủ trường spec 4.5, cho cả episode thành công; lưu trạng thái simulator ở đầu bước hỏng khi adapter hỗ trợ.
2. Bị ngắt thì chạy tiếp, không chạy lại episode đã xong.
3. Tự ghi GPU-giờ và số rollout vào sổ; chạy được trên adapter giả và adapter SIMPLE.

**3.3 · Khung scorer từng bước** · [Lõi] · Simulation · Phụ thuộc: 2.1 · G1. Là kỹ sư robot learning, tôi muốn một scorer độc lập chấm từng bước, để biết policy hỏng ở bước nào chứ không chỉ biết "trượt".
1. Nhận TaskDefinition; trả trạng thái mỗi bước: đạt, trượt, chưa thử, chưa rõ.
2. Gán bước hỏng đầu tiên k và một trong 9 kiểu lỗi spec 5.2; thiếu tín hiệu thì L-UNKNOWN.
3. Unit test trên trace tổng hợp cho từng kiểu lỗi.
4. Mỗi kiểu lỗi trong định nghĩa kiểu lỗi của TaskDefinition mang trường **lớp lỗi chung** (tiếp cận, gắp, mang, đặt, thăng bằng) để gộp thống kê giữa task ở L1 (06 mục 9).

**3.4 · TaskDefinition cho task chính và F1** · [Adapter] · Simulation · Phụ thuộc: 3.1, 3.3 · G1. Là kỹ sư simulation, tôi muốn khai 6 bước và vị từ của task chính, để scorer chấm được task này.
1. Vị từ theo spec 5.1; tham số r_reach, h_grasp, h_lift, h_place, T_stable nằm trong cấu hình.
2. Có điều kiện chạy suốt về chiều cao và độ nghiêng thân.
3. Có TaskDefinition khung cho F1, đủ để chạy test của NFR7.

**3.5 · Hiệu chỉnh scorer và ngưỡng** · [Lõi] · Robot Learning · Phụ thuộc: 2.2, 3.2, 3.4 · G1. Là kỹ sư robot learning, tôi muốn đối chiếu scorer với cờ thành công của SIMPLE, để tin được bước hỏng mà scorer gán.
1. Trên 100 episode gồm cả thành công và thất bại, kết luận toàn task trùng cờ SIMPLE ≥ 95%.
2. Kỹ sư xem 20 episode thất bại, xác nhận bước hỏng; kết quả lưu trong catalog.
3. τ_track và τ_sync (lệch thời gian giữa khung ảnh và state, dùng ở 6.2) được hiệu chỉnh từ demo teleop thành công và ghi vào RunPlan; τ_cov tính ở 2.4 (G2).

**3.6 · Cổng dev** · [Lõi] · Robot Learning · Phụ thuộc: 3.2, 3.3 · G4. Là kỹ sư robot learning, tôi muốn một lệnh so ứng viên với policy cha trên một tập điều kiện dev mới mỗi vòng, để biết có nên dùng ứng viên mà không bị nhiễu và thích nghi theo dev đánh lừa.
1. Kiểm ba điều kiện spec 6.12 với ngưỡng ở AC 5; báo cụm được can thiệp và tỉ lệ hồi quy.
2. Quyết định dùng hay từ chối lưu trong catalog; ứng viên bị từ chối vẫn giữ evidence card và chi phí.
3. Test trên adapter giả: ca hồi quy 6% bị từ chối khi sàn A/A dưới 6%.
4. Mỗi vòng dùng một tập điều kiện cổng mới (90 điều kiện) lấy từ dải hạt giống dev chưa dùng; chạy cả cha và ứng viên, ≥ 3 lượt mỗi điều kiện; rollout cổng ghi vào sổ (06 mục 3).
5. A/A test: chạy cha hai lần trên tập cổng để lấy sàn hồi quy giả; ngưỡng hồi quy = max(5%, sàn A/A); "tăng" phải ≥ 1 sai số chuẩn. Trên adapter giả, cổng A/A từ chối hoặc chấp nhận nhầm ≤ 10% (05 mục 3).

**3.7 · Thống kê ghép cặp và tiêu chí** · [Lõi] · Data-Platform · Phụ thuộc: 3.2 · G5. Là kỹ sư robot learning, tôi muốn CI 95% của chênh lệch giữa hai nhánh có tính cả phương sai giữa seed huấn luyện, để kết luận HS và HT đúng tiêu chí đã chốt.
1. Bootstrap phân cấp: lấy mẫu lại seed huấn luyện, rồi lấy mẫu lại điều kiện trong từng mức, 10.000 lần, seed cố định; mô hình logistic hỗn hợp (hiệu ứng ngẫu nhiên theo điều kiện và theo seed) chạy làm kiểm tra chéo. Kiểm trên dữ liệu mô phỏng có hiệu ứng và phương sai seed biết trước: độ phủ CI 93–97%.
2. "Cùng chiều ở ≥ 2/3 seed" chỉ là chỉ số phụ; ước tính nửa độ rộng CI từ phương sai dev, cảnh báo khi trên 7 điểm %.
3. Đọc tiêu chí HS, HT (HTa, HTb) từ RunPlan và tự ghi đạt, không đạt, hoặc "mô tả" khi luật MDE ở 4.4 đã hạ HT.
4. Chỉ số chính lấy từ cờ thành công của SIMPLE; scorer chỉ cho chỉ số theo bước. Báo riêng từng mức, và Level 1, Level 2 so với 70% (Cấp 3 BTC).
5. Hàm MDE dùng chung với power analysis của 4.4; HT báo kèm hai ràng buộc riêng: phút người và GPU-giờ (06 mục 10).

**3.8 · Khóa holdout** · [Lõi] · Data-Platform · Phụ thuộc: 2.5, 3.2 · G4 (dời từ G5 vì đợt holdout sớm cần khóa này). Là kỹ sư robot learning, tôi muốn holdout chỉ chạy được một lần sau khi đóng băng, để kết quả cuối không bị chỉnh theo holdout.
1. `fw holdout run` chỉ chạy khi hash checkpoint, scorer và cấu hình khớp bản đóng băng.
2. Mỗi cặp (nhánh, seed) chạy đúng một lần; lần thứ hai bị từ chối (có test).
3. Mọi lần đọc holdout có log.
4. Hỗ trợ đợt chạy sớm (8.3 AC 4): kết quả niêm phong, hash ghi vào RunPlan, chỉ mở ở G5; mở trước G5 bị từ chối và ghi log (có test).

### Epic 4 · Baseline và đường cong hiệu quả dữ liệu (G1, G2)

Mục tiêu: ba phương pháp train qua cùng lõi; có đường cong hiệu quả dữ liệu và D\*.

**4.1 · Adapter ACT và Diffusion Policy** · [Adapter] · Simulation · Phụ thuộc: 2.6, 3.1, 3.2 · G1. Là kỹ sư robot learning, tôi muốn train ACT và Diffusion Policy từ một release, để có baseline nhỏ chạy trên GPU của đội.
1. Dùng lại baseline có sẵn trong SIMPLE; train từ bản export của release, nạp lại và đánh giá chạy trọn (điều kiện G1). Chạy qua `runner` và contract test xong trước khi E1 bắt đầu (G2).
2. Ghi checkpoint hash và GPU-giờ.
3. Qua contract test của TrainerAdapter và PolicyAdapter.

**4.2 · TrainerAdapter cho Ψ₀** · [Adapter] · Robot Learning · Phụ thuộc: 1.4, 2.6 · G2. Là kỹ sư robot learning, tôi muốn fine-tune Ψ₀ qua lõi, để mọi nhánh dùng chung một đường train.
1. Nhận checkpoint gốc hoặc checkpoint cha, release, S, batch, learning rate, ρ, seed huấn luyện, và chính sách tăng cường thị giác cố định đọc từ RunPlan, như nhau cho mọi nhánh (06 mục 4).
2. Hỗ trợ cấu hình đã chốt ở 1.4 (toàn phần, LoRA hoặc đóng băng VLM).
3. Bị ngắt thì chạy tiếp; ghi checkpoint hash và GPU-giờ.

**4.3 · Điều phối training và quy tắc công bằng** · [Lõi] · Data-Platform · Phụ thuộc: 1.7, 2.1 · G2. Là kỹ sư robot learning, tôi muốn lõi tự kiểm quy tắc công bằng, để chênh lệch giữa các nhánh chỉ đến từ dữ liệu.
1. `fw train` nhận RunPlan của nhánh; kiểm cùng revision checkpoint gốc (đã qua Q0 ở 1.3), S, batch, learning rate, cùng chính sách tăng cường thị giác, cùng danh sách 0,7D\*, cùng bộ seed của RunPlan ({0, 1, 2}, hoặc 5 seed cho B và C nếu luật MDE ở 4.4 chọn).
2. Lệch quy tắc thì từ chối chạy và nêu quy tắc bị vi phạm.
3. Có test trên TrainerAdapter giả.
4. Từ chối RunPlan của E1 và các nhánh trỏ `simple-checkpoints` hoặc `sonic-checkpoints` (06 mục 8; có test).

**4.4 · Đường cong hiệu quả dữ liệu và chọn D\*** · [Adapter] · Robot Learning · Phụ thuộc: 3.5, 4.1, 4.2, 4.3 · G2. Là kỹ sư robot learning, tôi muốn train ba phương pháp ở 5 mức dữ liệu, để chọn D\*, đo lực thống kê và có phần chính của báo cáo so sánh phương pháp.
1. 5 mức × 3 phương pháp × 1 seed, đánh giá trên 90 điều kiện dev.
2. D\* là mức nhỏ nhất để Ψ₀ đạt ≥ 75% trên dev gộp (Cấp 2 BTC, 06 mục 7); luật trần, sàn của spec 7.1 tính tự động; chạm trần thì báo đề xuất chuyển chỉ tiêu.
3. Báo cáo đường cong, "số demo để đạt 75%" cho từng phương pháp (80% báo kèm để đối chiếu pitch v10), và tỉ lệ thành công ở mức 10% và 25% (Cấp 1 BTC).
4. Trước khi chốt D\*, chạy thêm seed thứ hai của Ψ₀ ở hai điểm lưới quanh ngưỡng 75% (hoặc nội suy đường cong) để tránh chọn nhầm do may mắn.
5. Power analysis ở G2: từ độ lệch giữa 2 seed ở D\* và phương sai giữa điều kiện, tính hiệu ứng nhỏ nhất phát hiện được (MDE) với 80% lực cho HT, bằng script mô phỏng có seed. MDE > 10 điểm % thì Hiếu chọn ở review G2 và ghi vào RunPlan một trong ba: tăng Ψ₀ lên 5 seed cho B và C; chuyển chỉ tiêu chính của HT sang mức còn dư địa; hạ HT thành kết quả mô tả.

### Epic 5 · Sinh dữ liệu sim, nhánh B (G3)

Mục tiêu: rollout sim cùng bộ điều khiển với demo teleop, đạt QA và có lineage; N_B chốt trước G3 và B_add là chi phí thực đo của đúng N_B rollout; các nhánh A, A₀.₇, B train xong.

**5.1 · GeneratorAdapter theo tuyến V3** · [Adapter] · Simulation · Phụ thuộc: 1.5, 1.9, 3.1; 5.5 khi V3 âm · G3. Là kỹ sư simulation, tôi muốn sinh rollout sim cho một danh sách điều kiện, để bổ sung dữ liệu mà không cần operator.
1. Dùng motion planning của SIMPLE khi 1.9 xác nhận cùng bộ điều khiển hoặc có ánh xạ tường minh; nếu không, bọc tuyến đã xây ở 5.5. Không dùng task F1 làm dự phòng cho Q2, trừ khi 1.9 xác nhận cặp task của F1 cùng bộ điều khiển (06 mục 1).
2. Mỗi rollout ghi điều kiện gốc hoặc demo gốc và phiên bản bộ sinh.
3. Từ chối điều kiện ngoài miền train và tham số Level 1, Level 2.

**5.2 · Điều phối sinh sim và đo B_add** · [Lõi] · Data-Platform · Phụ thuộc: 2.3, 2.4, 2.7, 5.1 · G3. Là kỹ sư data, tôi muốn sinh sim theo lô cho một lượng đã chốt trước, qua QA và ghi chi phí, để biết chi phí thật của nhánh B mà không định nghĩa vòng tròn.
1. N_B = 2 × (D\* − 0,7D\*) rollout sim đạt QA (làm tròn lên) và trần GPU-giờ được ghi vào RunPlan trước G3; RunPlan chưa có N_B thì không chạy. Lấy điều kiện đều trong miền train theo seed; gọi GeneratorAdapter theo lô tới đủ N_B rollout đạt QA, hoặc dừng khi chạm trần GPU-giờ và ghi lý do; bị ngắt thì chạy tiếp.
2. Mọi rollout qua QA; tỉ lệ sinh đạt và chi phí mẫu bị loại có trong sổ.
3. B_add là chi phí thực đo để tạo đúng N_B rollout đó, tính từ sổ, tách sinh sim, QA và tích hợp. Chi phí thu dữ liệu của C và của B-fail bị chặn ở B_add (06 mục 4).

**5.3 · Chọn ρ và train các nhánh của Ψ₀** · [Adapter] · Robot Learning · Phụ thuộc: 4.4, 5.2 · G3. Là kỹ sư robot learning, tôi muốn train A, A₀.₇ và B cho Ψ₀ với 3 seed, để có đối chứng cho HS và policy khởi đầu π₀ cho nhánh C.
1. Chọn ρ trong {0,25; 0,5} trên dev bằng nhánh B seed 0; ghi vào RunPlan.
2. Train A, A₀.₇, B × 3 seed (B 5 seed nếu luật MDE ở 4.4 chọn tăng seed); đánh giá trên dev; checkpoint có hash.
3. Mọi lần train có mục sổ.
4. Ngay sau G3, báo số lỗi dev theo mức của π₀. Level 0 có dưới 15 lỗi thì kích hoạt task khó hơn đã khai ở spec 7.1 và ghi vào RunPlan (06 mục 4).

**5.4 · Train nhánh A và B cho ACT và Diffusion Policy** · [Adapter] · Simulation · Phụ thuộc: 4.4, 5.2 · G3. Là kỹ sư robot learning, tôi muốn train A và B cho hai phương pháp nhỏ với 3 seed, để biết dữ liệu sim giúp model nào nhiều nhất.
1. Đủ các ô của ACT và Diffusion Policy trong ma trận spec 7.4.
2. Đánh giá trên dev theo mức; checkpoint có hash; mọi lần train có mục sổ.

**5.5 · Xây tuyến generator đã chọn (T1–T4)** · [Adapter] · Simulation · Phụ thuộc: 1.9, 3.1 · G3 (tuyến chốt ở G0, chậm nhất S2 ngày 3; xong trước 5.2). Là kỹ sư simulation, tôi muốn xây đến mức chạy được tuyến sinh dữ liệu đã chọn khi V3 âm, để nhánh B, C và B-fail có rollout cùng bộ điều khiển với demo teleop.
Ngoại lệ về cỡ: 1–4 tuần tùy tuyến (T1 tái thực thi quỹ đạo MP trong env WBC, 1–2 tuần; T2 biến thể kiểu MimicGen / IntervenGen từ đoạn teleop, chạy IK cộng WBC, 2–3 tuần; T3 planner trong env WBC, 2–4 tuần; T4 chuyển sang env MP và thu hẹp claim, vài ngày). SM tách thành story con 2–5 ngày khi tuyến đã chốt. 1.9 kết luận cùng bộ điều khiển hoặc có ánh xạ thì story đóng với ghi chú "không cần".
1. Tuyến, lý do chọn, công sức ước và hệ quả cho claim ghi vào RunPlan nháp và dòng V3 của 03 mục 3.3.
2. Rollout sinh ra chạy dưới cùng `embodiment_id` với demo teleop của task chính (03 ADR-08), qua QA, có lineage tới quỹ đạo MP hoặc đoạn teleop gốc và phiên bản bộ sinh.
3. Trên ít nhất 50 điều kiện trong miền train: đo tỉ lệ sinh đạt và thời gian mỗi rollout; ghi vào sổ.
4. Kiểm sinh được từ trạng thái lưu giữa task (cho kiểm khả thi, trạng thái chuẩn, correction do máy sinh); không được thì cờ tương ứng tắt và evidence card ghi "gần đúng" hoặc "bỏ qua".
5. Chọn T3 thì báo Hiếu kích hoạt cắt giảm theo 04 mục 7; chọn T4 thì claim HS thu hẹp ("sim thay sim") và ghi vào báo cáo.

### Epic 6 · Chẩn đoán (G4)

Mục tiêu: mọi cụm lỗi có chẩn đoán theo chuỗi phép kiểm và evidence card đọc được. Mã viết trên adapter giả từ tuần 5; chạy trên π₀ từ G3.

**6.1 · Gom cụm và chẩn đoán cụm** · [Lõi] · Data-Platform · Phụ thuộc: 3.3 · G4. Là kỹ sư robot learning, tôi muốn lỗi được gom thành cụm có đại diện, để phép kiểm tốn rollout chỉ chạy trên vài episode.
1. Khóa cụm (k, kiểu lỗi, mức); tối đa R = 5 đại diện chọn ngẫu nhiên, hạt giống được ghi.
2. Chẩn đoán cụm theo đa số; hòa thì cụm ở trạng thái "chờ kỹ sư".
3. Tách cụm theo chẩn đoán trước khi đề xuất can thiệp.

**6.2 · Kiểm hệ thống và kiểm vùng phủ** · [Lõi] · Simulation · Phụ thuộc: 2.4, 3.5 · G4. Là kỹ sư robot learning, tôi muốn hai phép kiểm rẻ chạy trên mọi episode lỗi, để loại lỗi hệ thống trước khi tiêu tiền vào dữ liệu.
1. Thứ tự: thiếu tín hiệu, τ_track, τ_lat, đồng bộ cảm biến, camera chuẩn (spec 6.4, 06 mục 5); ra CHƯA RÕ, LỖI CONTROLLER, LỖI RUNTIME, LỖI ĐỒNG BỘ hoặc LỖI CALIBRATION. Đối tượng kiểm là stack decoupled WBC của task chính; "lệnh gửi" và "trạng thái đo" định nghĩa theo giao diện WBC (lệnh thân trên, lệnh thân dưới).
2. Kiểm vùng phủ theo spec 6.8; ra THIẾU VÙNG PHỦ hoặc KỸ NĂNG YẾU. Lỗi có điều kiện nằm ngoài miền train (ví dụ vị trí vật của Level 2 ngoài khoảng train, dùng hàm ở 2.4) ra **NGOÀI MIỀN**: không tiêu ngân sách, được báo cáo.
3. Golden test trên adapter giả: lỗi cấy controller, trễ suy luận, trễ camera và lệch calibration camera ra đúng lớp; episode sạch không ra lớp hệ thống.
4. Đồng bộ cảm biến: lệch thời gian giữa khung ảnh và state vượt τ_sync (hiệu chỉnh ở 3.5). Camera chuẩn: tham số hoặc tư thế camera khác bản tham chiếu đã hash. Cả hai ra phiếu sửa hệ thống, không tiêu ngân sách dữ liệu.

**6.3 · Phép kiểm cần rollout** · [Lõi] · Simulation · Phụ thuộc: 3.2, 6.1 · G4. Là kỹ sư robot learning, tôi muốn kiểm khả thi, khoanh vùng và thị giác trên đại diện của cụm, để biết lỗi do bước nào và có do nhận thức không.
1. Khả thi bằng planner chạy dưới cùng bộ điều khiển với task chính (theo 1.9, 5.5), hoặc demo gần nhất và ghi "gần đúng" (spec 6.5).
2. Khoanh vùng M = 10 lượt, τ_k = 0,8; kiểm thị giác chỉ cho Level 1, 2. Cờ khả năng tắt thì ghi "bỏ qua" hoặc "chưa khoanh vùng". Chẩn đoán NHẬN THỨC được ghi và báo cáo, không tiêu ngân sách trong PoC vì tăng cường thị giác đã cố định cho mọi nhánh (06 mục 4).
3. Rollout kiểm tra ghi vào sổ như chi phí chẩn đoán.

**6.4 · SIMPLE: khôi phục trạng thái và hình ảnh chuẩn** · [Adapter] · Simulation · Phụ thuộc: 1.5, 3.1 · G4. Là kỹ sư simulation, tôi muốn SimulatorAdapter đặt được trạng thái chuẩn và hình ảnh chuẩn, để phép kiểm khoanh vùng và thị giác chạy được trên SIMPLE.
1. Chạy planner (theo tuyến ở 1.9, 5.5) hoặc demo đến đầu bước k và lưu trạng thái chuẩn dưới stack WBC của task chính (nếu Q3 cho phép).
2. Đặt ánh sáng, vật liệu về mức Level 0 mà giữ vật lý (nếu Q4 cho phép).
3. Contract test: khôi phục rồi để planner chạy tiếp cho kết quả như chạy liền.

**6.5 · Cấy lỗi trên SIMPLE** · [Adapter] · Simulation · Phụ thuộc: 3.1, 6.2, 6.3 · G4. Là kỹ sư simulation, tôi muốn cấy 5 loại lỗi biết đáp án của spec 7.6, để kiểm chuỗi chẩn đoán và có mẫu cho HD.
1. Cấy được lệch lệnh controller, trễ camera, lệch calibration camera, ánh sáng ngoài miền; trễ camera và lệch calibration có phép kiểm tương ứng ở 6.2 (LỖI ĐỒNG BỘ, LỖI CALIBRATION). Lỗi thiếu vùng phủ lấy từ một lần train bỏ một vùng điều kiện, có mục sổ.
2. Mỗi loại 2 episode, đáp án lưu riêng, người tham gia HD không xem được. Thêm ít nhất 10 episode sạch (không cấy lỗi) làm đối chứng.
3. Chuỗi chẩn đoán gán đúng ít nhất 8/10 lỗi cấy, và không lỗi cấy nào có đáp án thuộc lớp hệ thống bị xếp vào lớp tiêu ngân sách dữ liệu. Đáp án từng loại lỗi chốt trước khi chạy (PO duyệt, 04 mục 1.3).
4. Phần chung (FaultSpec, wrapper bọc PolicyAdapter cho trễ và lệch lệnh) nằm trong `runner`, không phụ thuộc SIMPLE, có test trên adapter giả (FR14).
5. Báo **recall theo từng lớp** và tỉ lệ báo nhầm trên **đối chứng sạch** (06 mục 5). Mục tiêu tham khảo theo 05 mục 3: lớp hệ thống ≥ 0,8 mỗi lớp, lớp dữ liệu ≥ 0,6, báo động hệ thống giả trên ca sạch ≤ 5%.

**6.6 · Evidence card và trình xem** · [Lõi] · Data-Platform · Phụ thuộc: 6.1, 6.2, 6.3 · G4. Là kỹ sư robot learning, tôi muốn mỗi cụm lỗi có một thẻ ghi đủ bằng chứng, để ra quyết định mà không phải mở log thô.
1. Thẻ đủ trường spec 4.5; mỗi giá trị kèm ngưỡng; liên kết tới trace, video, đồ thị.
2. Xuất Markdown và HTML tự chứa, mở offline; trang danh sách cụm của một vòng.
3. Snapshot test cho thẻ.

### Epic 7 · Quyết định và thu dữ liệu, nhánh C (G4)

Mục tiêu: vòng Failure → Data chạy trọn trên Ψ₀ (mặc định 1 vòng), 5–8 vòng trên ACT (F-ACT); nhánh B-fail tách tác dụng của chẩn đoán; chi phí thu không vượt B_add.

**7.1 · Bảng quyết định và định lượng** · [Lõi] · Data-Platform · Phụ thuộc: 2.7, 6.1 · G4. Là kỹ sư robot learning, tôi muốn chẩn đoán được đổi thành can thiệp có số lượng và chi phí, để so sánh các lựa chọn bằng cùng đơn vị.
1. Bảng spec 6.9 (gồm LỖI ĐỒNG BỘ, LỖI CALIBRATION, NGOÀI MIỀN) và số lượng spec 6.10 đọc từ RunPlan.
2. Chi phí ước tính từ đơn giá trong sổ.
3. Chẩn đoán hệ thống (gồm LỖI ĐỒNG BỘ, LỖI CALIBRATION) và KHÔNG KHẢ THI sinh phiếu sửa; đóng phiếu sửa thì yêu cầu chạy lại baseline.
4. Menu can thiệp của C trong PoC: sinh sim quanh điều kiện lỗi, teleop correction, dữ liệu phục hồi. Tăng cường thị giác là phần cố định của recipe cho mọi nhánh, không còn trong menu; NHẬN THỨC và NGOÀI MIỀN được ghi và báo cáo, không tiêu ngân sách; kiểm demo mâu thuẫn chỉ ra báo cáo (06 mục 4).

**7.2 · Tỉ lệ sửa được và chọn theo ngân sách** · [Lõi] · Data-Platform · Phụ thuộc: 3.6, 7.1 · G4. Là kỹ sư robot learning, tôi muốn hệ thống chọn can thiệp có lợi ích kỳ vọng trên chi phí cao nhất và đo tỉ lệ sửa được không thiên lệch, để ngân sách đi vào chỗ sửa được nhiều nhất.
1. Beta(1, 1) khởi đầu, lưu bền với khóa (task, chẩn đoán, loại can thiệp). g_j = (n_eff_j / N) × f̄_t với n_eff_j = min(m_j, giới hạn mỗi cụm của loại can thiệp); hòa thì ưu tiên bước hỏng sớm hơn; c_j theo spec 6.11 (06 mục 3).
2. Chọn tham lam theo g/c trong ngân sách vòng khai trong RunPlan; kiểm 4 điều kiện dừng.
3. Cập nhật α, β sau cổng dev theo AC 5; có test so với ví dụ tính tay.
4. Unit test chứng minh: ở vòng 1 (prior đều), thứ tự chọn chỉ là đơn giá của loại can thiệp trong các loại mà chẩn đoán cho phép. Tính chất này ghi trong tài liệu module và trên báo cáo vòng.
5. Đo tỉ lệ sửa được có đối chứng (FR46): mỗi cụm lấy điều kiện mới quanh điểm lỗi (bán kính τ_cov / 2, tối đa 5 điều kiện mỗi lỗi, tối đa 30 mỗi cụm); chạy policy cha và ứng viên mỗi bên ≥ 3 lượt; fixed_j = làm tròn(n × (p_ứng viên − p_cha)), kẹp trong [0, n]; α += fixed_j, β += n − fixed_j. Trên adapter giả, can thiệp "rỗng" cho fixed_j gần 0.

**7.3 · Duyệt và ghi đè** · [Lõi] · Data-Platform · Phụ thuộc: 6.6, 7.2 · G4. Là kỹ sư robot learning, tôi muốn duyệt hoặc ghi đè đề xuất qua CLI, để thuật toán đề xuất còn người quyết định.
1. `fw review` hiện đề xuất kèm đường dẫn tới evidence card.
2. Ghi đè bắt buộc có lý do; quyết định lưu vào evidence card; giờ kỹ sư vào sổ.
3. Báo cáo tỉ lệ ghi đè; cảnh báo khi trên 50% (đề xuất của brief).

**7.4 · Teleop correction và dữ liệu phục hồi** · [Adapter] · Simulation · Phụ thuộc: 6.4; 5.5 khi V3 âm · G4. Là operator teleop, tôi muốn bắt đầu thu từ đúng trạng thái lỗi đã lưu, để chỉ thu đoạn policy còn yếu.
1. Có thiết bị (Q6) thì TeleopSource thu correction và ghi giờ operator.
2. Không có thiết bị thì planner hoặc tuyến generator đã chọn (5.5) sinh từ trạng thái lưu, gắn cờ "máy sinh". V3 âm và Q6 âm thì loại can thiệp này không có; ghi theo kịch bản ở 1.9 AC 5.
3. Correction được đếm riêng theo spec 4.1.

**7.5 · Điều phối thu dữ liệu nhánh C** · [Lõi] · Data-Platform · Phụ thuộc: 5.2, 7.2, 7.4 · G4. Là kỹ sư data, tôi muốn thực hiện danh sách can thiệp đã duyệt trong giới hạn ngân sách, để release mới chỉ chứa dữ liệu đã chọn và đạt QA.
1. Sinh sim quanh điều kiện lỗi trong bán kính τ_cov và miền train. Tăng cường thị giác không thuộc nhánh C (FR31).
2. Liệt kê tối đa 10 demo gần nhất cho kiểm demo mâu thuẫn; kết quả chỉ ghi vào báo cáo, không loại demo khỏi danh sách 0,7D\* (A₀.₇, B, C dùng cùng danh sách, 06 mục 4).
3. Chặn cứng ở ngân sách vòng; mọi mẫu qua QA trước khi vào release mới.

**7.6 · Chạy vòng 1 của nhánh C** · [Adapter] · Robot Learning · Phụ thuộc: 3.6, 5.3, 6.6, 7.3, 7.5 · G4. Là kỹ sư robot learning, tôi muốn chạy trọn vòng 1 từ π₀, để có kết quả thật đầu tiên của Failure → Data.
1. Đủ 12 bước spec 6.1; evidence card cho mọi cụm.
2. Ứng viên qua hoặc trượt cổng dev đều được giữ cùng chi phí.
3. Sổ chi phí đủ cho vòng; α, β được cập nhật bằng đo có đối chứng (7.2 AC 5).

**7.7 · Vòng 2 và C cuối** · [Adapter] · Robot Learning · Phụ thuộc: 7.6 · G4. Là kỹ sư robot learning, tôi muốn train C cuối từ checkpoint gốc (và chạy vòng 2 trên Ψ₀ chỉ khi đủ điều kiện), để C so được công bằng với A, B và B-fail.
1. Mặc định chỉ 1 vòng C trên Ψ₀ (06 mục 9); vòng thêm chạy trên ACT (7.10). Vòng 2 trên Ψ₀ là phần thưởng, chỉ chạy khi đủ điều kiện ở 04 mục 4.5. Điều kiện dừng và phần ngân sách chưa tiêu được ghi.
2. C cuối train từ checkpoint gốc với cùng S, cùng bộ seed với B.
3. Chi phí của C tách thành chi phí thu và chi phí chẩn đoán.

**7.8 · Báo cáo sổ chi phí và mô hình kinh tế** · [Lõi] · Data-Platform · Phụ thuộc: 2.7, 7.6, 7.11 · G4. Là giám khảo, tôi muốn xem mỗi nhánh tốn bao nhiêu và vì sao, để đánh giá claim "ít công" bằng số đo.
1. Tổng hợp theo nhánh, vòng, cụm, loại nguồn lực; B_add của N_B rollout; chi phí C có và không có chi phí chẩn đoán; số demo người (teleop và correction) của từng nhánh.
2. Công thức spec 8.2 với r_demo đo được và r_debug dạng khoảng; bảng độ nhạy theo đơn giá DENSO và theo chi phí giờ cell (robot, người giám sát, thời gian dừng).
3. Chi phí mỗi điểm % tăng thêm của C so với B và so với B-fail; giờ operator mỗi điểm % tăng thêm; trình xem sổ chi phí HTML.
4. Chỉ số chính (06 mục 10): số demo người để đạt ngưỡng; phút operator mỗi điểm %; sai số dự báo chi phí (ước tính so với thực đo trong sổ, theo từng can thiệp); số ngày để policy đạt lại ngưỡng.
5. HT báo kèm hai ràng buộc riêng: phút người và GPU-giờ.

**7.9 · Nhánh B⁺ (tùy chọn, ưu tiên thấp hơn B-fail)** · [Adapter] · Simulation · Phụ thuộc: 7.7 · G4. Là kỹ sư robot learning, tôi muốn một nhánh dùng đúng tỉ lệ can thiệp của C nhưng lấy điều kiện đều, để tách tác dụng "nhắm đúng chỗ lỗi".
1. Tỉ lệ loại can thiệp lấy từ C; điều kiện lấy đều trong miền train; cùng ngân sách.
2. Bỏ B⁺ thì báo cáo nói rõ C − B gộp hai tác dụng (spec 7.2).
3. Chỉ mở khi 7.11 đã xong và đủ điều kiện mở nhánh ở 04 mục 1.3 (06 mục 4).

**7.10 · F-ACT: 5–8 vòng Failure → Data trên ACT** · [Adapter] · Data-Platform · Phụ thuộc: 3.6, 5.4, 7.2, 7.5 · G4. Là kỹ sư robot learning, tôi muốn chạy 5–8 vòng Failure → Data rẻ với ACT trên cùng task, để có bằng chứng "flywheel học" (tỉ lệ sửa được ổn định dần, chi phí mỗi điểm % giảm) mà không tốn GPU của Ψ₀.
1. π₀ của ACT là ACT train trên cùng danh sách 0,7D\* (1 seed), cùng chính sách tăng cường thị giác; story này không dùng Ψ₀ (06 mục 3).
2. Chạy 5–8 vòng đủ 12 bước spec 6.1, với tập cổng dev mới mỗi vòng (3.6) và tỉ lệ sửa được đo có đối chứng (7.2 AC 5). Số vòng, ngân sách mỗi vòng và ước rollout khai trong RunPlan trước vòng 1.
3. Báo cáo theo vòng: posterior Beta theo loại can thiệp (trung bình và CI), chi phí mỗi điểm % tăng trên dev, tỉ lệ ghi đè, số cụm CHƯA RÕ.
4. Kết luận "flywheel học" chỉ nêu khi CI của tỉ lệ sửa được hẹp dần qua các vòng và chi phí mỗi điểm % giảm; không đạt thì báo như kết quả âm.
5. Checkpoint ACT ở vòng mà chi phí thu lũy kế chạm B_add là nhánh C của ACT, dùng để so với B-fail cho HTb (7.11); vòng này khai trong RunPlan trước vòng 1.

**7.11 · Nhánh B-fail** · [Adapter] · Simulation · Phụ thuộc: 5.2, 5.4, 7.10 (π₀ của ACT) · G4. Là kỹ sư robot learning, tôi muốn một nhánh sinh sim quanh mọi điều kiện lỗi dev mà không chẩn đoán, cùng ngân sách với C, để tách tác dụng "nhắm theo lỗi" (HTa) khỏi tác dụng của chuỗi chẩn đoán (HTb).
1. Lấy mọi điều kiện lỗi dev của π₀; sinh sim đều trong bán kính τ_cov quanh từng điều kiện và trong miền train (FR11, chế độ B-fail); không chạy chẩn đoán; dừng khi chi phí thu chạm B_add.
2. Chạy trên ACT là chính (cùng bộ seed với B của ACT); trên Ψ₀ chỉ khi còn ngân sách sau G4, Hiếu quyết ở review G4.
3. HTa đạt khi cận dưới CI 95% của (B-fail − B) > 0. HTb đạt khi cận dưới CI 95% của (C − B-fail) > 0. Cả hai tính bằng thống kê của 3.7, tiêu chí ghi vào RunPlan trước holdout, chạy holdout theo 8.3.
4. Báo cáo ghi B-fail là phiên bản rút gọn kiểu Mulligan (không học value function) và thay vai trò ưu tiên của B⁺ (06 mục 4).

### Epic 8 · Thí nghiệm, báo cáo, SOP, demo (G4–G6)

Mục tiêu: đo HD, chạy holdout đúng một lần cho mỗi cặp (nhánh, seed) (nhánh không phụ thuộc C chạy sớm và niêm phong), giao ba đầu ra của đề H1.

**8.1 · Công cụ HD** · [Lõi] · Data-Platform · Phụ thuộc: 6.5, 6.6 · G4. Là người điều phối HD, tôi muốn đóng gói 20 episode thành hai dạng tư liệu và phân công đối trọng, để đo thời gian chẩn đoán công bằng.
1. 10 lỗi cấy (6.5) và 10 lỗi tự nhiên từ dev; mỗi episode có tư liệu gốc và gói evidence card.
2. Phân công chéo: mỗi episode một người dùng tư liệu gốc, một người khác dùng card; thứ tự đối trọng.
3. Ghi số phút, chẩn đoán và can thiệp; tính r_debug dạng khoảng và độ đúng theo các lớp của spec 6.9.
4. Đối thủ của card là công cụ chuẩn: Rerun cộng đồ thị mặc định trên cùng tư liệu gốc, không phải log do đội tự đóng gói (06 mục 5).
5. Chèn 3–4 evidence card sai cố ý (đáp án khóa trước) để đo mức tin mù quáng: tỉ lệ người làm theo card sai.

**8.2 · Chạy HD và ước lượng r_debug** · [Lõi] · Robot Learning · Phụ thuộc: 7.6, 8.1 · G4. Là trưởng nhóm, tôi muốn chạy HD với người ngoài đội cùng kỹ sư trong đội, để thay giả định 50% giờ debug bằng số đo đáng tin.
1. Có ít nhất 2 người ngoài đội (mentor hoặc đội khác); kết quả của người trong đội báo riêng.
2. Đáp án lỗi tự nhiên theo spec 7.6, lấy sau vòng 1.
3. Báo cáo r_debug dạng khoảng, chỉ khi độ đúng có card không thấp hơn; kèm mức tin mù quáng; nêu đủ giới hạn của spec 7.6.

**8.3 · Đóng băng và chạy holdout** · [Adapter] · Simulation · Phụ thuộc: 3.7, 3.8, 5.3, 5.4, 7.7, 7.11 · G5. Là kỹ sư robot learning, tôi muốn chạy holdout một lần cho mọi nhánh, để có kết luận cuối cho HS và HT.
1. Kiểm nửa độ rộng CI trước; trên 7 điểm % thì tăng số điều kiện holdout trước khi chạy.
2. 150 điều kiện × 3 seed cho mọi ô của ma trận spec 7.4, thêm B-fail (và B⁺ nếu có); 5 seed cho B và C nếu luật MDE ở 4.4 chọn.
3. Tiêu chí HS, HT (HTa, HTb) được tính tự động và lưu cùng hash của mọi thứ đã đóng băng.
4. Đợt sớm (06 mục 9): ngay khi checkpoint, scorer và cấu hình của các nhánh không phụ thuộc C (A, A₀.₇, B của Ψ₀; ACT, Diffusion Policy) đã đóng băng, chạy holdout cho các nhánh đó và niêm phong kết quả (3.8 AC 4); chỉ mở ở G5 cùng kết quả của C. Mỗi cặp (nhánh, seed) vẫn chạy đúng một lần.
5. Chỉ số chính là cờ thành công của SIMPLE (so được với số công bố); scorer chỉ cho chỉ số theo bước. Báo riêng Level 1 và Level 2 so với 70% (Cấp 3 BTC).

**8.4 · Báo cáo so sánh phương pháp và kết quả** · [Lõi] · Robot Learning · Phụ thuộc: 4.4, 7.8, 7.10, 8.2, 8.3 · G6. Là giám khảo, tôi muốn một báo cáo sinh từ catalog, để mọi con số truy được về run gốc.
1. Mẫu báo cáo dùng chung theo nhánh, phương pháp, mức; mọi số trỏ về ID run.
2. Có đường cong hiệu quả dữ liệu, số demo để đạt 75%, chi phí train, HS, HT (HTa, HTb), HD với CI và từng seed; kết quả F-ACT theo vòng.
3. Có kết quả âm, ứng viên bị từ chối và giới hạn (chỉ sim; sim cùng phân phối với test).
4. Có bảng map tiêu chí BTC 3 cấp (mục 1.1) với số đo từng cấp, gồm Level 1 và Level 2 riêng, và khuyến nghị thu dữ liệu định lượng (FR47).

**8.5 · SOP thu và kiểm dữ liệu** · [Lõi] · Data-Platform · Phụ thuộc: 2.3, 2.6, 7.5 · G6. Là operator teleop, tôi muốn một checklist thu và kiểm dữ liệu theo vai, để làm đúng mà không cần đọc spec.
1. Checklist từ spec 4.4 và mục 6, với ngưỡng thật đã hiệu chỉnh lấy từ RunPlan.
2. Tách theo vai: operator, kỹ sư data, kỹ sư robot learning.
3. Một thành viên không viết SOP làm theo được: nạp, QA và tạo release cho một gói.

**8.6 · Video demo và rà claim** · [Adapter] · Simulation · Phụ thuộc: 8.3, 8.4 · G6. Là chủ công đoạn, tôi muốn xem robot làm task trên tình huống chưa thấy, kèm tỉ lệ thật, để hiểu đúng năng lực của policy.
1. Video rollout holdout có chú thích điều kiện, mức, kết quả scorer; có cả ca thất bại.
2. Tỉ lệ thành công thật hiện cạnh video.
3. Danh sách claim của pitch: mỗi claim có số đo đi kèm hoặc bị gỡ (G6).

### Epic 9 · Dữ liệu đa nguồn và robot DENSO (G1–G4, bản 0.4)

Mục tiêu: dữ liệu teleop, video egocentric và synthetic đi qua cùng pipeline; mỗi stage của Ψ₀ được chấm riêng; robot DENSO (hoặc robot thay thế) chạy task khay → máy trong Isaac Sim. Chi tiết ở design 23/10/2026. Mỗi story ứng với một story `DA-xx` ở [07 mục 2.2](07-team-workflow.md), nơi ghi người làm, phạm vi file, giờ và sprint; file story do SM viết theo mẫu story hiện có.

| Story | DA | Tên | Nhãn | Yêu cầu | Cổng | AC chính |
|---|---|---|---|---|---|---|
| 9.1 | DA-01 | Định dạng episode chung và `action_layout` | [Lõi] | FR48 | G1 | Schema validate; test tính chất; thêm embodiment mới không cần migration |
| 9.2 | DA-02 | Export LeRobot theo `action_layout` | [Adapter] | FR48, FR49 | G1 | Contract test đọc lại bằng loader Ψ₀ xanh; stats tính trên đúng release |
| 9.3 | DA-03 | Pipeline teleop trên psi-data | [Lõi] | FR49 | G1 | Toàn bộ gói task chính qua 6 tầng; báo số pass, flag, reject kèm lý do |
| 9.4 | DA-04 | Pipeline egocentric E-A và E-B | [Adapter] | FR50, NFR13 | G2 | Mọi episode có `deid_status` khác `raw` trước khi cắt đoạn; báo độ lệch pose E-A so với E-B trên cùng mẫu |
| 9.5 | DA-05 | `NimClient` và định tuyến | [Adapter] | FR52, NFR13 | G1 | Test: yêu cầu `restricted` tới endpoint hosted bị từ chối; mỗi lời gọi có LedgerEntry |
| 9.6 | DA-06 | Tầng S3 Cosmos Transfer | [Adapter] | FR51 | G3 | IoU vị trí vật với segmentation gốc được đo và lọc theo ngưỡng; chi phí mỗi mẫu trong sổ |
| 9.7 | DA-07 | Log train theo nhóm action | [Adapter] | FR54 | G2 | Một lần fine-tune G1 ghi đủ nhóm log ở design mục 6.3 |
| 9.8 | DA-08 | Bộ phát hiện lỗi train và offline | [Lõi] | FR54 | G2 | Bộ log cấy sẵn từng lỗi T1–T8, O1–O4 đều bị phát hiện |
| 9.9 | DA-09 | Probe P1–P4 | [Lõi] | FR53 | G2 | Bộ probe có hash; kết quả trên `pre.*`, `postpre.*` có trong báo cáo |
| 9.10 | DA-10 | Robot thay thế và chấm giống | [Adapter] | FR56 | G1–G2 | `fw embodiment score` chạy, ghi Decision với cơ sở chấm |
| 9.11 | DA-11 | Cảnh trạm và `DensoIsaacSim` | [Adapter] | FR56 | G3 | Một episode robot thay thế chạy trọn task khay → máy trong sim, ghi đủ tín hiệu |
| 9.12 | DA-12 | `DensoTrayToMachine` | [Adapter] | FR57 | G3 | Scorer khớp nhãn tay trên episode mẫu ở ngưỡng chốt khi hiệu chỉnh |
| 9.13 | DA-13 | Bước 4b quy lỗi về stage | [Lõi] | FR55 | G4 | Lỗi cấy theo từng stage được quy đúng trên card |
| 9.14 | DA-14 | Xin thông tin DENSO | Việc trưởng nhóm | Design mục 9 | G0 | Danh sách 21 mục gửi trong tuần 1; trả lời ghi vào design |

## 7. Ngoài phạm vi 12 tuần

- Robot thật (kể cả robot DENSO thật), cell thật, teleop trên G1 thật, an toàn vận hành, real2sim.
- Video công nhân DENSO qua V2D, world model DreamDojo, continued pretraining stage 1 ở quy mô lớn.
- Web app, nhiều người dùng, đăng nhập, phân quyền, lưu trữ tập trung, database server.
- Vòng Failure → Data cho hơn một task. F1 chỉ là dự phòng cho Q1 và phép thử NFR7; không là dự phòng cho Q2 trừ khi 1.9 xác nhận cặp task của F1 cùng bộ điều khiển.
- Dùng dữ liệu lỗi làm tín hiệu train (kiểu Mulligan học value function): hướng L1.
- Thuật toán học máy mới; pretrain; train RL mới (AMO chỉ kế thừa); dò siêu tham số rộng (chỉ chọn ρ trong hai giá trị).
- Tự động hóa hoàn toàn quyết định. Kỹ sư luôn duyệt.
- Sinh dữ liệu với tham số Level 1 hoặc Level 2; tự động thuê và cấp phát GPU cloud.
- Claim tiết kiệm tiền mặt, claim số đợt mỗi năm (cần DENSO xác nhận).

### Backlog L1–L3

| Mức | Hạng mục backlog | Đã chuẩn bị ở L0 |
|---|---|---|
| L1 · Nhiều task | Thư viện TaskDefinition theo loại task (gắp, đặt, đẩy); thêm task khó hơn như `LocomotionPickBetweenTablesTeleop`; gộp tỉ lệ sửa được giữa task bằng prior theo họ task; dùng dữ liệu lỗi để train; báo cáo chéo task | task_id trong schema; vector điều kiện khai theo task; khóa tỉ lệ sửa được có task; lớp lỗi chung trong định nghĩa kiểu lỗi; TaskDefinition F1 |
| L2 · Robot thật | SimulatorAdapter cho cell thật; TeleopSource VR thật; cổng an toàn trước rollout thật; real2sim cho tình huống lỗi; chẩn đoán khi không khôi phục được trạng thái; quyền dữ liệu video nhà máy | Trường miền sim hoặc thật; cờ khả năng; phép kiểm "bỏ qua" có ghi; mức phân loại dữ liệu |
| L3 · Nhiều robot | Mô tả state và action theo embodiment; PolicyAdapter đa robot; vị từ scorer theo khung vật thay vì theo khớp; tỉ lệ sửa được theo embodiment | embodiment_id và mô tả không gian state, action trong schema; test embodiment giả |

L4 (nhiều nhà máy) chỉ ghi nhận, chưa vào backlog; `site_id` đã có từ L0 với giá trị mặc định.

## 8. Rủi ro sản phẩm

| Rủi ro | Câu hỏi spec | Dấu hiệu sớm | PRD giảm rủi ro bằng |
|---|---|---|---|
| Không đủ demo teleop | Q1 | N_teleop < 50 ở 1.6 | Đo ở tuần 1; nạp sẵn F1 (2.2); TaskDefinition tách khỏi lõi nên đổi task không sửa lõi |
| Teleop (WBC) và motion planning (AMO) khác bộ điều khiển | V3 | 1.9 chưa có kết luận ngày 5 của Sprint 1; T1 và T2 đều hỏng ở tuần 2 | Story 1.9 hạn ngày 5; thử T1 và T2 song song tuần 1–2, chốt cuối tuần 2; xây tuyến ở 5.5: T1 tái thực thi quỹ đạo MP trong env WBC (1–2 tuần), T2 biến thể kiểu MimicGen / IntervenGen từ đoạn teleop với IK cộng WBC (2–3 tuần), T3 planner trong env WBC (2–4 tuần), T4 chuyển sang env MP và thu hẹp claim (vài ngày, phương án cuối). F1 không chữa V3 nên không là dự phòng cho Q2 |
| V3 âm và không có thiết bị teleop | V3, Q6 | 1.9 âm và 1.6 trả lời "không" | C chỉ còn kiểm demo mâu thuẫn; HT sụp; báo cáo phải nêu (06 mục 1) |
| Không có planner cho task chính | Q2 | 1.5 thất bại | GeneratorAdapter bọc tuyến đã chọn ở 5.5 (5.1); kiểm khả thi "gần đúng" (FR21) |
| Checkpoint gốc đã thấy dữ liệu task chính | Q0 | Ψ₀ ở mức 10% cao bất thường; PSI Lab chưa trả lời | 1.3 AC 5; 4.3 AC 4 chặn `simple-checkpoints`, `sonic-checkpoints`; ghi giới hạn vào báo cáo |
| Không khôi phục được trạng thái | Q3 | 1.5 thất bại | Cờ khả năng; cụm ghi "chưa khoanh vùng"; nhánh C vẫn chạy với chẩn đoán thô hơn |
| Không tách được hình ảnh | Q4 | 1.5 thất bại | Tắt phép kiểm thị giác qua cờ; evidence card ghi rõ không chẩn đoán được NHẬN THỨC |
| Ψ₀ quá nặng hoặc quá chậm | Q5 | 1.4 hết bộ nhớ hoặc vượt ngân sách | Đo ở tuần 1–2; 4.2 hỗ trợ LoRA và đóng băng VLM; sổ theo dõi GPU-giờ; giảm còn 2 seed và ghi rõ, khi đó HT thành kết quả mô tả |
| Không có thiết bị teleop | Q6 | 1.6 trả lời "không" | Correction do planner hoặc tuyến 5.5 sinh, gắn cờ "máy sinh" (7.4); r_demo chỉ tính demo gốc |
| Chạm trần | Không có | Ψ₀ ở mức 10% đã ≥ 90%; π₀ có dưới 15 lỗi Level 0 trên dev sau G3 | Luật trần tự động ở 4.4; luật đổi sang task khó hơn ở 5.3 AC 4 |
| Thiếu lực thống kê cho HT | Không có | Hai seed ở D\* lệch > 5 điểm; MDE > 10 điểm % | Power analysis ở 4.4; bootstrap phân cấp ở 3.7; luật MDE: thêm seed, đổi chỉ tiêu hoặc hạ HT thành mô tả |
| HT trượt | Không có | Cận dưới CI của (C − B) ≤ 0 | Epic 2, 3, 6 và sổ chi phí vẫn dùng được; HTa trên ACT vẫn có kết quả từ B-fail (7.11); báo cáo trung thực theo spec 7.7 |
| Nhiễu can thiệp làm C − B khó diễn giải | Không có | C khác B ở thứ ngoài dữ liệu được chọn | Tăng cường thị giác cố định cho mọi nhánh (FR31); không loại demo (FR32); báo số demo người theo nhánh; B-fail (7.11) |
| Chẩn đoán sai có hệ thống | Không có | Recall lỗi cấy theo lớp thấp; tỉ lệ ghi đè > 50% | Đồng bộ cảm biến, camera chuẩn ở 6.2; recall theo lớp và đối chứng sạch ở 6.5 |
| Tỉ lệ sửa được và cổng dev bị nhiễu | Không có | A/A test từ chối nhầm > 10% | Đo có đối chứng (7.2 AC 5, FR46); tập cổng mới mỗi vòng và A/A (3.6) |
| HD bị coi là thiên lệch | Không có | Không có người ngoài đội tham gia | ≥ 2 người ngoài đội; Rerun cộng đồ thị mặc định; card sai cố ý; r_debug dạng khoảng (8.1, 8.2) |
| Lõi dính chặt recipe | Không có | Lõi import SIMPLE hoặc Ψ₀ | Luật import trong CI; adapter giả; test thêm task và embodiment giả |
| Rò holdout | Không có | Episode holdout trong release train; điều kiện gần trùng train | NFR5, 2.4 AC 4, 2.5, 3.8 |
| Mất dữ liệu do hỏng máy 5090 | Không có | Không có bản backup nào | NFR11, 2.8 |
| Mảng Robot Learning quá tải | Không có | Story của mảng trễ quá 3 ngày | Simulation nhận train ACT, Diffusion Policy và chạy holdout; Châu đồng sở hữu Ψ₀; thứ tự cắt giảm dưới đây |
| DENSO gửi thông tin muộn (bản 0.4) | Design mục 9 | Cuối tuần 2 chưa có trả lời | Robot thay thế (9.10); pipeline chạy trên psi-data và mẫu EgoDex |
| Tải thêm của Epic 9 (bản 0.4) | Không có | k sau Sprint 1 > 1; Hưng, Long trễ | Chuyển phần trễ sang API theo từng phần trước (04 mục 4.9); rồi cắt S4, U4, E-A trên dữ liệu thật, S2-B |
| Model NIM ngừng hoặc dữ liệu không được gửi ra ngoài (bản 0.4) | V-D4 | API hosted báo ngừng; DENSO cấm | NIM tự host (9.5); danh sách model trong cấu hình có hash |
| Stage 2 không chuyển được sang robot DENSO (bản 0.4) | V-D1 | P3 cao ở mọi nhóm action | So S2-A, S2-B, S2-C; nếu đều kém, dùng ACT làm policy chạy vòng trên robot DENSO |
| Sim giúp ít hơn dữ liệu người (bản 0.4) | Không có | Kết quả âm của Mirchandani và cộng sự (CoRL 2024) | Giữ điều kiện so với A₀.₇ của HS; báo số demo người theo nhánh (FR41) |

**Phạm vi mặc định** (06 mục 9, lập ở 70% năng lực):

- Nhánh C trên Ψ₀ mặc định **1 vòng**; vòng thêm chạy trên ACT (7.10). Vòng 2 trên Ψ₀ là phần thưởng, chỉ mở theo điều kiện ở 04 mục 4.5.
- Holdout của các nhánh không phụ thuộc C chạy sớm ngay khi đóng băng và niêm phong tới G5 (8.3 AC 4).
- B-fail chạy trên ACT; trên Ψ₀ chỉ khi còn ngân sách sau G4. B⁺ (7.9) ưu tiên thấp hơn B-fail.

**Thứ tự cắt giảm nếu trễ** (cắt từ trên xuống, ghi rõ trong báo cáo; điều kiện kích hoạt ở 04 mục 7; PO duyệt bản 0.2, PM sửa theo 06 ở bản 0.3 để giữ ACT cho HTa và F-ACT):

1. Nhánh B⁺ (7.9) và B-fail trên Ψ₀, nếu đã mở.
2. Trình xem HTML và console HD (giữ card và sổ chi phí dạng Markdown; bấm giờ HD bằng CLI).
3. Vòng 2 của nhánh C trên Ψ₀, nếu đã mở (C cuối train trên release sau vòng 1).
4. F-ACT còn 5 vòng (7.10).
5. Diffusion Policy chỉ 1 seed cho nhánh A và B; ACT giữ 3 seed ở B và B-fail vì HTa dựa vào đó.
6. Phần lỗi tự nhiên của HD (giữ 10 lỗi cấy và card sai cố ý).
7. Diffusion Policy chỉ chạy E1, không chạy nhánh A, B và holdout.
8. Ψ₀ còn 2 seed cho nhánh chính, chỉ khi GPU vượt ngân sách (spec mục 10); khi đó HT tự động thành kết quả mô tả (06 mục 2).

Không cắt: QA, lineage và giấy phép, chia tập và khóa holdout, nguồn gốc checkpoint gốc (Q0), sổ chi phí, quy tắc công bằng, kiểm hệ thống trước dữ liệu, cấm trộn embodiment không tương thích (V3), đo tỉ lệ sửa được có đối chứng và A/A ở cổng dev, backup hằng ngày, báo cáo kết quả âm.

## 9. Bước tiếp theo

**Gửi Architect:**

1. Xác nhận ranh giới tiến trình giữa lõi và adapter nặng (Isaac Sim 4.5 và Ψ₀ có thể cần môi trường Python, CUDA khác nhau).
2. Lưu trữ đã chốt ở 03 theo L0-lite (NFR12): trace Parquet, ledger JSONL, một chỉ mục DuckDB, kho theo content hash ngoài git, không database server. Còn chốt: cách lưu và nạp trạng thái simulator dưới stack WBC (trạng thái chuẩn, trạng thái lỗi).
3. Chốt Protocol v0 của 6 adapter và danh sách cờ khả năng, kể cả cờ cho phép kiểm đồng bộ cảm biến và camera chuẩn nếu cần (6.2). Importer psi-data nằm trong `catalog` (đã chốt ở 04 P08).
4. Schema L0-lite: khoảng 12 thực thể, trường mở rộng trong `meta`; `task_id`, `embodiment_id`, `site_id` là cột thường có mặc định; lớp lỗi chung trong định nghĩa kiểu lỗi; FixRateEvent ghi được phép đo có đối chứng (FR46).
5. Chốt tên CLI và thư mục mã. Đã chốt ở 03: CLI `fw`, mã trong `packages/flywheel`.
6. Vault holdout hỗ trợ niêm phong kết quả chạy sớm (3.8 AC 4) và backup không tạo lần đọc mới (2.8).

**Gửi Scrum Master:**

1. Sprint 2 tuần khớp cổng: sprint 1 = G0, 2 = G1, 3 = G2, 4 = G3, 5 = G4, 6 = G5 và G6.
2. Sprint 1 chạy ba luồng: Simulation (1.2, 1.5, 1.8, và 1.9 hạn ngày 5), Robot Learning (1.3, 1.4), Data-Platform (1.1, 1.6, 1.7, rồi 2.1).
3. Epic 6 và 7.1–7.3 phát triển trên adapter giả trước khi có π₀ ở G3.
4. Lập kế hoạch ở 70% năng lực (thay mức 85% ở 04 mục 0); áp phạm vi mặc định và thứ tự cắt giảm ở mục 8.
5. Theo dõi tải của mảng Robot Learning: 1 người, kiêm trưởng nhóm và đầu mối với DENSO.
6. 06 thay các quyết định sau của 04: P29 (holdout sớm, nay làm theo 8.3 AC 4), P30 (G0 nay 30 lượt mỗi mức hoặc kiểm nhị thức), P31 (N_B nay có công thức ở 5.2), thứ tự cắt ở 04 mục 7.2. File story Sprint 1 cần cập nhật: S1-03 (1.3 AC 1, 2, 5), S1-05 (nay chỉ ứng với 1.5 phần Q2; 1.9 có file riêng S1-11), S1-10 (2.1 AC 1: L0-lite, `site_id`).

**Mã story mới và story bị hủy** (bản 0.3, để Scrum Master cập nhật 04). Không đánh số lại story cũ.

| Mã | Story | Epic | Nhãn | Mảng gợi ý | Cổng | Ghi chú cho 04 |
|---|---|---|---|---|---|---|
| 1.9 | Bộ điều khiển teleop và motion planning (V3) | 1 | [Adapter] | Simulation | G0, hạn ngày 5 Sprint 1 | Tách từ 1.5 AC 5; S1-05 nay chỉ gồm 1.5 phần Q2, story 1.9 có file riêng S1-11 |
| 2.8 | Backup hằng ngày và diễn tập khôi phục | 2 | [Lõi] | Data-Platform | G2, diễn tập trước G3 | Thay việc ngoài story "backup" ở S3 và "diễn tập khôi phục" ở S4 |
| 5.5 | Xây tuyến generator đã chọn (T1–T4) | 5 | [Adapter] | Simulation | G3, xong trước 5.2 | 1–4 tuần, bắt đầu tuần 3; tách story con khi chốt tuyến; đóng "không cần" nếu V3 dương |
| 7.10 | F-ACT: 5–8 vòng Failure → Data trên ACT | 7 | [Adapter] | Data-Platform | G4 | Không dùng GPU của Ψ₀; khoảng 6 người-ngày |
| 7.11 | Nhánh B-fail | 7 | [Adapter] | Simulation | G4 | Thay vai ưu tiên của B⁺; ACT là chính |

Story bị hủy: **không có**. B⁺ (7.9) giữ là tùy chọn, ưu tiên thấp hơn 7.11. AC 5 của 1.5 chuyển sang 1.9, số AC 1–4 giữ nguyên. Story 3.8 dời cổng từ G5 sang G4.

Story có AC đổi đáng kể (SM rà file story và ước lượng): 1.3, 1.5, 2.1, 2.4, 2.5, 2.7, 3.3, 3.5, 3.6, 3.7, 3.8, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9, 8.1, 8.2, 8.3, 8.4.

**Gửi PO:** bản 0.2 đã được PO đối chiếu ở 04 mục 1. Xác nhận các điểm PM tự đặt ở bản 0.3, không có trong 06: (1) nhánh C của ACT để so HTb là checkpoint F-ACT ở vòng chạm B_add (7.10 AC 5); (2) mức cắt 4–7 sửa để giữ ACT cho HTa và F-ACT; (3) khi chỉ chạy 1 vòng C trên Ψ₀, cách chia ngân sách vòng (60/40 hay dồn 100% vào vòng 1) chờ spec bản sửa quyết, 7.7 chỉ ghi phần chưa tiêu; (4) backup thành story 2.8; (5) F-ACT giao mảng Data-Platform; (6) 3.8 dời sang G4.
