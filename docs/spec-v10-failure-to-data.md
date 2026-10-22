# Spec v10: thuật toán Failure → Data và PoC ba nhánh

_Trạng thái: đặc tả đề xuất, chưa thực nghiệm. Ngày 22/10/2026. Áp dụng cho recipe Ψ₀ + SIMPLE / G1 của [Pitch v10](../deliverables/DENSO-ilovephysicalintelligence-1.pptx). Tài liệu này là đặc tả canonical cho thuật toán flywheel và thiết kế đánh giá. Hồ sơ của recipe cũ FluxVLA / GR00T N1.5 / GR1 (docs 01–14, idea v3) nằm trong tag git `archive/v3`; các quy tắc dữ liệu cần dùng đã được đưa vào mục 4. Thuật ngữ được định nghĩa ở mục 12._

## 0. Đọc nhanh

**Một câu:** khi policy humanoid thất bại trong mô phỏng, hệ thống chạy một chuỗi phép kiểm tự động để xác định lỗi do hệ thống hay do dữ liệu, nếu do dữ liệu thì thiếu loại nào, rồi đề xuất cách bổ sung có lợi ích kỳ vọng cao nhất trên mỗi đô-la. Kỹ sư duyệt đề xuất; mọi bước được ghi vào sổ chi phí.

**Ba giả thuyết cần kiểm:**

- **H1 · Sim thay được teleop:** 0,7D\* demo teleop cộng dữ liệu sim đạt chất lượng không kém D\* demo teleop.
- **H2 · Chọn theo lỗi tốt hơn bổ sung đều:** cùng ngân sách thu dữ liệu, dữ liệu do Failure → Data chọn cho kết quả tốt hơn dữ liệu sim rải đều.
- **H3 · Giảm giờ chẩn đoán:** evidence card giúp kỹ sư chẩn đoán lỗi nhanh hơn mà không sai nhiều hơn.

**Các nhánh chính:** A (D\* teleop), B (0,7D\* teleop + sim rải đều), C (0,7D\* teleop + dữ liệu chọn bởi Failure → Data). Nhánh đối chứng A₀.₇ (chỉ 0,7D\* teleop) cho biết khoảng cách mà B và C cần lấp.

**Đầu ra 12 tuần, khớp đề H1 của BTC:**

1. SOP thu và kiểm dữ liệu: mục 4 và mục 6 viết thành checklist.
2. Báo cáo so sánh phương pháp huấn luyện: ACT, Diffusion Policy và Ψ₀, kèm kết quả H1–H3.
3. Demo kỹ năng đã học: video rollout trong SIMPLE trên tập holdout.

## 1. Phạm vi và ranh giới claim

### 1.1 Kế thừa, đội làm, sau PoC

| Lớp | Nội dung | Ghi chú khi trình bày |
|---|---|---|
| Kế thừa | Checkpoint Ψ₀ đã pretrain trên video người (EgoDex) và dữ liệu humanoid; simulator SIMPLE; dữ liệu psi-data; bộ điều khiển thân dưới AMO | Viết "kế thừa prior video người từ Ψ₀", không viết "platform kết hợp video người" như đóng góp của đội |
| Đội làm trong PoC | Data Core (QA, lineage, chia tập), scorer từng bước, thuật toán Failure → Data, evidence card, sổ chi phí, thiết kế và chạy PoC ba nhánh, so sánh phương pháp | Đây là phần được chấm là đóng góp |
| Sau PoC | Video công nhân DENSO qua V2D, world model DreamDojo, task DENSO thật, robot thật | Mỗi hướng cần cổng nghiệm thu riêng |

### 1.2 Không claim

- Không claim thuật toán học máy mới. Các thành phần đều có tiền lệ: DAgger / HG-DAgger cho correction, MimicGen cho sinh biến thể, DataMIL cho chọn dữ liệu. Đóng góp là **cách ghép các phép kiểm thành quy trình ra quyết định có ghi chi phí**, và **phép đo** xem quy trình đó có đáng tiền không.
- Không claim kết quả trên robot thật. Mọi số liệu PoC là trong mô phỏng; dữ liệu sim cùng phân phối với môi trường test nên lợi ích của sim có thể bị phóng đại so với robot thật.
- Không claim tiết kiệm tiền mặt. Sổ chi phí đo giá trị nguồn lực theo đơn giá giả định.

## 2. Nền tảng kỹ thuật

### 2.1 Ψ₀

Theo [trang Ψ₀](https://psi-lab.ai/Psi0/), kiểm ngày 22/10/2026:

| Thành phần | Mô tả | Vai trò trong PoC |
|---|---|---|
| System-2 | VLM Qwen3-VL-2B-Instruct, pretrain trên khoảng 829 giờ video EgoDex cùng Humanoid Everyday | Kế thừa |
| System-1 | Action expert dạng flow matching (MM-DiT), khoảng 500M tham số, dự đoán action chunk toàn thân | Fine-tune |
| System-0 | Bộ điều khiển thân dưới AMO, học bằng RL | Kế thừa; là đối tượng của kiểm tra hệ thống |
| Tổng | Hơn 2,5B tham số, khoảng 160 ms mỗi lần chạy, dùng real-time chunking | Cần đo VRAM và thời gian ở G0 |

Theo công bố, bước thích nghi với task mới là fine-tune toàn bộ model trên một lượng nhỏ dữ liệu teleop trong miền.

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
- **Task dự phòng F1:** cặp `G1WholebodyBendPickTeleop-v0` và `G1WholebodyBendPickMP-v0` (chỉ gắp, không đặt) vì có sẵn cả hai kiểu dữ liệu.
- Ψ₀ công bố 10/10 ở cả ba mức cho `BendPickMP` và 10/9/9 cho `XMoveBendPickTeleop` (10 lượt mỗi mức). Nhiều task đã gần trần 100% khi dùng đủ dữ liệu, nên PoC phải đo ở mức dữ liệu thấp hơn (mục 7.1).

### 2.4 Câu hỏi phải trả lời ở cổng G0

| Mã | Câu hỏi | Nếu câu trả lời là "không" |
|---|---|---|
| Q1 | Gói task chính chứa bao nhiêu demo teleop đạt QA (gọi là N_teleop)? | Nếu N_teleop < 50, đường cong ở mục 7.1 quá thô: chuyển sang task dự phòng hoặc gộp task |
| Q2 | Pipeline motion planning của SIMPLE cấu hình được cho task chính không? | Dùng task dự phòng F1, hoặc sinh biến thể kiểu MimicGen từ đoạn teleop |
| Q3 | Có đặt được simulator vào một trạng thái đã lưu (vị trí robot, vật, khớp) rồi chạy tiếp không? | Bỏ phép kiểm khoanh vùng (mục 6.6); chẩn đoán đánh dấu "chưa khoanh vùng" |
| Q4 | Có tách được ngẫu nhiên hóa hình ảnh khỏi ngẫu nhiên hóa vật lý không? | Bỏ phép kiểm thị giác (mục 6.7) |
| Q5 | Fine-tune Ψ₀ cần bao nhiêu VRAM và GPU-giờ; mỗi episode đánh giá mất bao lâu? | Dùng LoRA hoặc đóng băng VLM; thuê A100 80 GB; giảm số seed |
| Q6 | Đội có thiết bị teleop cho SIMPLE không? | Correction do planner sinh từ trạng thái lỗi thay cho người điều khiển |

## 3. Giả thuyết và tiêu chí chấp nhận

| Mã | Giả thuyết | So sánh | Tiêu chí chấp nhận (chốt trước khi chạy holdout) |
|---|---|---|---|
| H1 | Sim thay được 30% demo teleop | B so với A và A₀.₇ | B đạt ≥ 80% trên holdout gộp ba mức; cận dưới CI 95% của (B − A) > −10 điểm %; cận dưới CI 95% của (B − A₀.₇) > 0 |
| H2 | Chọn dữ liệu theo lỗi tốt hơn bổ sung đều | C so với B, cùng ngân sách thu dữ liệu | Cận dưới CI 95% của (C − B) > 0. Báo cáo kèm tổng chi phí của C, gồm cả chi phí chẩn đoán |
| H3 | Evidence card giảm thời gian chẩn đoán | Có card so với log thô | Thời gian giảm và tỉ lệ chẩn đoán đúng không thấp hơn. Đây là pilot, cho ước lượng r_debug, không phải kiểm định thống kê |
| M | So sánh phương pháp huấn luyện | ACT, Diffusion Policy, Ψ₀ trên nhánh A và B | Báo cáo mô tả: tỉ lệ thành công theo mức, số demo để đạt 80%, chi phí train |

Ghi chú cho H1: nếu A₀.₇ đã không kém A thì H1 đúng nhưng không nhờ sim; khi đó dữ liệu teleop chưa phải nút thắt ở mức D\*. Vì vậy điều kiện (B − A₀.₇) > 0 là bắt buộc.

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
| Dev | 30 điều kiện mỗi mức × 3 mức = 90 điều kiện | Nhánh C để tìm lỗi; nhánh B để chọn tỉ lệ trộn ρ |
| Holdout | 50 điều kiện mỗi mức × 3 mức = 150 điều kiện | Chỉ chạy một lần sau khi đóng băng mọi nhánh |

Dải hạt giống của ba tập rời nhau và được ghi vào RunPlan trước khi train. Bộ sinh sim chỉ lấy điều kiện trong miền train, không dùng tham số Level 1 hoặc Level 2. Một episode holdout bị lộ vào train thì vô hiệu hóa run đó.

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

**Trace** (một bản cho mỗi episode): phiên bản policy, phiên bản release, vector điều kiện, mức, hạt giống điều kiện, chuỗi ảnh, action chunk dự đoán, lệnh gửi tới controller, trạng thái đo được, độ trễ mỗi chu kỳ, trạng thái từng bước của scorer, kết quả cuối.

**Evidence card** (một thẻ cho mỗi cụm lỗi):

- Định danh cụm, danh sách episode, các đại diện đã kiểm.
- Bước hỏng đầu tiên k và kiểu lỗi.
- Kết quả từng phép kiểm: sai số bám lệnh, độ trễ, planner khả thi, s_k (kèm số lượt), kiểm thị giác, khoảng cách vùng phủ. Mỗi giá trị đi kèm ngưỡng tương ứng.
- Chẩn đoán, can thiệp đề xuất, lợi ích kỳ vọng, chi phí ước tính.
- Quyết định của kỹ sư (đồng ý hoặc ghi đè, kèm lý do).
- Kết quả sau khi train lại.

**Mục sổ chi phí:** hoạt động, loại nguồn lực (operator, kỹ sư, A100, RTX 4090, lưu trữ), số lượng, đơn giá, nhánh, vòng, cụm liên quan.

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

| Mã | Kiểu lỗi | Dấu hiệu |
|---|---|---|
| L-REACH | Không tới được vật | Hết giờ ở bước 1 |
| L-GRASP | Gắp trượt | Đóng tay nhưng không giữ được vật ở bước 2 |
| L-SLIP | Rơi khi mang | Mất tiếp xúc ở bước 3 hoặc 4 |
| L-COLLIDE | Va chạm | Tiếp xúc ngoài ý muốn với bàn, khay hoặc vật gây nhiễu |
| L-PLACE | Đặt lệch | Vật ngoài vùng đích ở bước 5 hoặc 6 |
| L-RELEASE | Nhả sai lúc | Nhả quá sớm hoặc không nhả |
| L-BALANCE | Mất thăng bằng | Vi phạm giới hạn thân ở bất kỳ bước nào |
| L-TIMEOUT | Đứng yên, không tiến triển | Hết giờ mà không chuyển bước, không thuộc các kiểu trên |
| L-UNKNOWN | Thiếu tín hiệu | Không đủ dữ liệu để gán kiểu |

### 5.3 Hiệu chỉnh scorer

Cổng G1 đạt khi kết luận toàn task của scorer trùng với cờ thành công của SIMPLE trên ít nhất 95% của 100 episode (gồm cả thành công và thất bại), và kỹ sư xem 20 episode thất bại thấy bước hỏng được gán đúng.

## 6. Thuật toán Failure → Data

### 6.1 Tổng quan

Mỗi vòng gồm 12 bước:

| Bước | Tên | Đầu vào | Đầu ra |
|---|---|---|---|
| 1 | Chạy | Policy, 90 điều kiện dev | Trace |
| 2 | Gán nhãn | Trace | Bước hỏng đầu tiên k, kiểu lỗi |
| 3 | Gom cụm sơ bộ | Các lỗi | Cụm theo (k, kiểu lỗi, mức); tối đa R đại diện mỗi cụm |
| 4 | Kiểm hệ thống | Trace của đại diện | Lỗi controller, runtime hoặc thiếu tín hiệu |
| 5 | Kiểm khả thi | Điều kiện đầu | Planner chuẩn có làm được không |
| 6 | Khoanh vùng | Trạng thái chuẩn ở đầu bước k | s_k |
| 7 | Kiểm thị giác | Cùng trạng thái vật lý, hình ảnh chuẩn | Lỗi nhận thức hay không |
| 8 | Kiểm vùng phủ | Vector điều kiện | Khoảng cách tới tập train |
| 9 | Chẩn đoán cụm | Kết quả 4–8 của các đại diện | Chẩn đoán theo đa số |
| 10 | Đề xuất và định lượng | Chẩn đoán | Can thiệp, số lượng, chi phí ước tính |
| 11 | Chọn theo ngân sách | Đề xuất, tỉ lệ sửa được | Danh sách can thiệp được chọn |
| 12 | Thu, QA, train, cổng kiểm | Can thiệp được chọn | Release mới, policy ứng viên, cập nhật tỉ lệ sửa được |

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
            # 4. Kiểm hệ thống, chỉ cần log
            if f.missing_signals:              f.diag = "CHUA_RO";            continue
            if f.tracking_error > P.tau_track: f.diag = "HE_THONG_CONTROLLER"; continue
            if f.latency_p99 > P.tau_lat:      f.diag = "HE_THONG_RUNTIME";    continue
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
            # 8. Kiểm vùng phủ
            d = knn_distance(f.condition, release.train_conditions, k=P.K)
            f.diag = "THIEU_VUNG_PHU" if d > P.tau_cov else "KY_NANG_YEU"
        cl.diag = majority([f.diag for f in cl.representatives(P.R)])   # hòa thì kỹ sư quyết

    # 9–10. Tách cụm theo chẩn đoán, đề xuất can thiệp và định lượng
    proposals = [propose(cl, P) for cl in split_by_diag(clusters)
                 if cl.diag in DATA_DIAGNOSES]
    # 11. Chọn theo lợi ích kỳ vọng trên chi phí, trong ngân sách
    for p in proposals:
        p.gain = p.n_failures / len(dev) * fix_rate[p.kind].mean()
        p.cost = ledger_estimate(p)
    chosen = greedy_by_ratio(proposals, budget)
    # Cụm lỗi hệ thống hoặc không khả thi thành phiếu sửa, không tiêu ngân sách dữ liệu
    return chosen, repair_tickets(clusters), evidence_cards(clusters)
```

Vòng ngoài của nhánh C:

```python
policy = finetune(PSI0_BASE, teleop_subset(0.7 * D_star), steps=S)   # pi_0, cũng là nhánh A0.7
release = release_of(teleop_subset(0.7 * D_star))
for r in (1, 2):                                                      # PoC tối đa 2 vòng
    chosen, tickets, cards = failure_to_data_round(policy, release, DEV, B_round[r], fix_rate, P)
    chosen = engineer_review(cards, chosen)          # kỹ sư duyệt hoặc ghi đè, có lý do
    fix_system(tickets)                              # sửa hệ thống thì phải đo lại baseline
    release = qa_and_release(release, acquire(chosen))
    candidate = finetune(policy, release, replay=True)
    report = dev_gate(candidate, policy, DEV)
    update_fix_rates(fix_rate, chosen, report)
    if report.promote:
        policy = candidate
    if should_stop(report, ledger, P):
        break
final_C = finetune(PSI0_BASE, release, steps=S)      # train lại từ base, cùng S với A và B
```

Trong các vòng, fine-tune tiếp từ checkpoint cha để nhanh. Model cuối của nhánh C được train lại từ checkpoint gốc với cùng số bước S như A và B, để phép so sánh chỉ khác nhau ở dữ liệu.

### 6.2 Bước 1–2: chạy và gán nhãn

Chạy policy trên 90 điều kiện dev, mỗi điều kiện một lượt. Scorer ở mục 5 gán bước hỏng đầu tiên và kiểu lỗi. Trace của mọi episode được lưu, kể cả episode thành công (dùng cho phép kiểm hồi quy ở bước 12).

### 6.3 Bước 3: gom cụm sơ bộ

Gom lỗi theo khóa (bước hỏng k, kiểu lỗi, mức). Các phép kiểm 5–7 tốn rollout nên chỉ chạy trên tối đa R = 5 đại diện mỗi cụm, chọn ngẫu nhiên có ghi hạt giống. Phép kiểm 4 và 8 rẻ nên chạy cho mọi episode lỗi.

### 6.4 Bước 4: kiểm hệ thống

Chỉ dùng log, chạy theo thứ tự:

1. **Thiếu tín hiệu** (camera mất khung, trace thiếu trường): chẩn đoán CHƯA RÕ, đề xuất thu thêm bằng chứng, không can thiệp dữ liệu.
2. **Sai số bám lệnh**: chuẩn của (lệnh gửi − trạng thái đo được) vượt τ_track, với τ_track là phân vị 99 trên episode teleop thành công. Chẩn đoán LỖI CONTROLLER; kiểm cấu hình AMO và ánh xạ khớp.
3. **Độ trễ**: phân vị 99 độ trễ chu kỳ suy luận vượt τ_lat, với τ_lat là phân vị 99 trên lần chạy chuẩn ở G0. Chẩn đoán LỖI RUNTIME.

Lỗi hệ thống được sửa trước. Sau khi sửa phải chạy lại baseline của policy hiện tại, vì phép đo cũ không còn giá trị.

### 6.5 Bước 5: kiểm khả thi

Chạy planner motion planning của SIMPLE từ đúng điều kiện đầu. Nếu planner cũng thất bại thì điều kiện có thể không khả thi (vật ngoài tầm với, va chạm không tránh được). Chẩn đoán KHÔNG KHẢ THI; kỹ sư sửa cảnh hoặc loại vùng điều kiện đó khỏi miền task và ghi lại. Nếu Q2 trả lời "không", dùng demo teleop có điều kiện gần nhất làm phép thử thay thế và đánh dấu "kiểm khả thi gần đúng".

### 6.6 Bước 6: khoanh vùng bằng reset

Chạy planner (hoặc demo teleop gần nhất) từ cùng điều kiện đầu đến đầu bước k, lưu trạng thái simulator làm **trạng thái chuẩn**. Đặt simulator vào trạng thái này rồi để policy chạy M = 10 lượt, ra tỉ lệ thành công s_k.

- **s_k ≥ τ_k = 0,8:** policy làm tốt bước k nếu bắt đầu đúng, nên lỗi do bước trước để lại trạng thái xấu. Chẩn đoán TRẠNG THÁI ĐẦU XẤU, cần dữ liệu phục hồi.
- **s_k < 0,8:** bản thân kỹ năng ở bước k yếu; đi tiếp phép kiểm 7 và 8.

Nếu Q3 trả lời "không", bỏ bước này và đánh dấu cụm là "chưa khoanh vùng".

### 6.7 Bước 7: kiểm thị giác

Chỉ áp dụng cho lỗi ở Level 1 và 2. Giữ nguyên điều kiện vật lý, đặt tham số hình ảnh (ánh sáng, vật liệu) về mức chuẩn của Level 0 rồi chạy lại. Nếu thành công, lỗi nằm ở nhận thức: chẩn đoán NHẬN THỨC, đề xuất tăng cường thị giác. Không cần demo mới.

### 6.8 Bước 8: kiểm vùng phủ

Tính khoảng cách trung bình d từ vector điều kiện của lỗi tới K = 5 điều kiện train gần nhất. Ngưỡng τ_cov là phân vị 95 của khoảng cách tương tự trong tập train, tính kiểu leave-one-out.

- **d > τ_cov:** lỗi nằm ngoài vùng dữ liệu đã phủ. Chẩn đoán THIẾU VÙNG PHỦ.
- **d ≤ τ_cov:** đã có dữ liệu gần đó mà vẫn lỗi, thường do dữ liệu mâu thuẫn hoặc tình huống khó. Chẩn đoán KỸ NĂNG YẾU.

### 6.9 Bảng quyết định

| Chẩn đoán | Điều kiện | Can thiệp | Tiêu ngân sách dữ liệu? |
|---|---|---|---|
| CHƯA RÕ | Thiếu tín hiệu | Thu thêm bằng chứng, sửa logging | Không |
| LỖI CONTROLLER | Sai số bám lệnh > τ_track | Sửa controller, ánh xạ khớp, calibration | Không |
| LỖI RUNTIME | Độ trễ > τ_lat | Sửa pipeline suy luận | Không |
| KHÔNG KHẢ THI | Planner chuẩn thất bại | Sửa cảnh hoặc thu hẹp miền task | Không |
| TRẠNG THÁI ĐẦU XẤU | s_k ≥ τ_k | Dữ liệu phục hồi: correction bắt đầu từ trạng thái do policy tạo ở đầu bước k | Có |
| NHẬN THỨC | Kiểm thị giác thành công | Tăng cường thị giác đã khai trước (mục 7.3) | Có (GPU) |
| THIẾU VÙNG PHỦ | d > τ_cov | Sinh rollout sim quanh điều kiện lỗi | Có |
| KỸ NĂNG YẾU | d ≤ τ_cov | Teleop correction ở bước k; kiểm demo mâu thuẫn trong lân cận | Có |

Thứ tự kiểm là cố định: hệ thống trước, dữ liệu sau. Một lỗi đã có chẩn đoán hệ thống thì không đi tiếp vào nhánh dữ liệu.

### 6.10 Định lượng can thiệp

Giá trị mặc định, ghi vào RunPlan và chỉnh được:

| Can thiệp | Số lượng | Giới hạn mỗi cụm |
|---|---|---|
| Sinh sim quanh điều kiện lỗi | 20 rollout đạt QA cho mỗi lỗi, điều kiện lấy đều trong bán kính τ_cov quanh điều kiện lỗi và nằm trong miền train | 200 rollout |
| Teleop correction | 1 correction cho mỗi lỗi | 10 correction |
| Dữ liệu phục hồi | 1 đoạn phục hồi cho mỗi lỗi, bắt đầu từ trạng thái lỗi đã lưu | 10 đoạn |
| Tăng cường thị giác | Áp dụng cho toàn bộ dữ liệu train ở lần train sau | Một lần mỗi vòng |
| Kiểm demo mâu thuẫn | Kỹ sư xem tối đa 10 demo gần nhất trong vùng lỗi, loại demo hỏng | 10 demo |

Nếu Q6 trả lời "không", teleop correction và dữ liệu phục hồi do planner sinh từ trạng thái đã lưu, và báo cáo ghi rõ correction là do máy sinh.

### 6.11 Chọn can thiệp theo ngân sách

- Mỗi loại can thiệp t có **tỉ lệ sửa được** f_t theo phân phối Beta(α_t, β_t), khởi đầu Beta(1, 1) cho mọi loại (trung bình 0,5, không thiên vị).
- Với đề xuất cho cụm j có m_j lỗi trên N_dev = 90 điều kiện dev: lợi ích kỳ vọng g_j = (m_j / N_dev) × trung bình của f_t, đơn vị là điểm % thành công trên dev.
- Chi phí c_j ước tính từ đơn giá trong sổ chi phí và số lượng ở mục 6.10.
- Sắp đề xuất theo g_j / c_j giảm dần, chọn lần lượt cho đến khi hết ngân sách vòng.
- Ngân sách nhánh C bằng B_add (mục 7.3), chia 60% cho vòng 1 và 40% cho vòng 2.

### 6.12 Thu dữ liệu, train và cổng dev

1. Thu dữ liệu theo danh sách đã chọn; mọi mẫu qua QA ở mục 4.4.
2. Tạo release mới: release cũ cộng dữ liệu mới, giữ lineage. Dữ liệu cũ luôn được trộn lại (replay).
3. Fine-tune từ checkpoint cha.
4. **Cổng dev:** chạy ứng viên trên cùng 90 điều kiện dev. Ứng viên được chấp nhận khi:
   - Thành công trên toàn dev tăng.
   - Các cụm được can thiệp cải thiện.
   - Hồi quy ≤ 5 điểm %: trong số điều kiện mà policy cha đã làm được, tỉ lệ ứng viên làm hỏng không vượt quá 5%.

Ứng viên trượt cổng không được dùng tiếp, nhưng evidence card và chi phí của nó vẫn được giữ.

### 6.13 Cập nhật tỉ lệ sửa được và điều kiện dừng

Sau cổng dev, với mỗi cụm j đã can thiệp bằng loại t: gọi fixed_j là số điều kiện trước đó lỗi nay đã thành công. Cập nhật α_t += fixed_j và β_t += m_j − fixed_j. Đây là phần flywheel "học": qua các vòng, hệ thống biết loại can thiệp nào thực sự sửa được loại lỗi nào trên task này.

Dừng vòng lặp khi gặp một trong các điều kiện:

- Hết ngân sách.
- Đề xuất tốt nhất có g/c dưới 1 điểm % cho mỗi $100.
- Hai vòng liên tiếp không qua cổng dev.
- Đã đủ 2 vòng (giới hạn của PoC).

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
| Hồi quy cho phép | 5 điểm % | Chốt trước vòng 1 |
| Ngưỡng dừng g/c | 1 điểm % cho mỗi $100 | Chốt trước vòng 1 |
| Prior tỉ lệ sửa được | Beta(1, 1) | Không đổi trong PoC |

## 7. Thiết kế PoC

### 7.1 Giai đoạn E1: đường cong hiệu quả dữ liệu và D\*

Train mỗi phương pháp (ACT, Diffusion Policy, Ψ₀) với 10%, 25%, 50%, 70% và 100% của N_teleop demo teleop (1 seed). Đánh giá trên 90 điều kiện dev.

- **D\*** là mức nhỏ nhất trong lưới mà Ψ₀ đạt ≥ 80% trên dev gộp ba mức. Nhánh A dùng D\* demo, các nhánh còn lại dùng 0,7D\*.
- **Trần:** nếu Ψ₀ ở mức 10% đã đạt ≥ 90%, task quá dễ để đo khác biệt. Chuyển chỉ tiêu chính sang Level 2, hoặc đổi sang task khó hơn (Ψ₀ công bố 7/5/6 cho `LocomotionPickBetweenTablesTeleop`).
- **Sàn:** nếu ở mức 100% vẫn dưới 60%, D\* = N_teleop và ngưỡng 80% được thay bằng kết quả của nhánh A, ghi rõ trong báo cáo.

Đường cong này là kết quả có giá trị riêng: chỉ số "số demo để đạt 80%" theo từng phương pháp là phần chính của báo cáo so sánh phương pháp.

### 7.2 Các nhánh

| Nhánh | Dữ liệu train | Vai trò |
|---|---|---|
| A | D\* demo teleop | Baseline |
| A₀.₇ | 0,7D\* demo teleop | Đối chứng: không bổ sung gì; cũng là policy khởi đầu π₀ của nhánh C |
| B | 0,7D\* teleop + rollout sim với điều kiện lấy đều trong miền train, tiêu hết B_add | Kiểm H1, là đối thủ của C trong H2 |
| C | 0,7D\* teleop + dữ liệu do Failure → Data chọn, tối đa B_add | Kiểm H2 |
| B⁺ (tùy chọn) | 0,7D\* teleop + đúng tỉ lệ các loại can thiệp mà C đã chọn, nhưng điều kiện lấy đều thay vì quanh điểm lỗi | Tách tác dụng của "nhắm đúng chỗ lỗi" khỏi tác dụng của "dùng nhiều loại can thiệp" |

Không có B⁺, chênh lệch C − B gộp hai tác dụng: nhắm theo lỗi, và được dùng nhiều loại can thiệp hơn B (B chỉ có sim). Báo cáo phải nói rõ điều này nếu bỏ B⁺.

### 7.3 Quy tắc công bằng giữa các nhánh

1. Cùng checkpoint gốc Ψ₀, ghi revision.
2. Cùng số bước gradient S, batch, learning rate và lịch learning rate. S lấy theo cấu hình fine-tune công bố của Ψ₀ cho SIMPLE và ghi vào RunPlan.
3. A₀.₇, B và C dùng cùng một danh sách 0,7D\* demo teleop.
4. Tỉ lệ mẫu sim trong batch ρ chọn trong {0,25; 0,5} trên dev bằng nhánh B (1 seed), rồi áp nguyên cho C.
5. **B_add** là chi phí thu dữ liệu thực đo của nhánh B (sinh sim, QA, tích hợp). Nhánh C bị chặn ở đúng B_add cho chi phí thu dữ liệu. Chi phí chẩn đoán của C (rollout kiểm tra, giờ kỹ sư) ghi riêng và cộng vào tổng chi phí khi báo cáo.
6. Dùng chung 3 seed huấn luyện {0, 1, 2} cho mọi nhánh.
7. Không sinh dữ liệu với tham số của Level 1 hoặc Level 2. Tăng cường thị giác chỉ dùng biến đổi trên ảnh đã khai trước (độ sáng, độ tương phản, dịch màu), không dùng preset ánh sáng của SIMPLE.
8. Holdout chỉ chạy một lần, sau khi đóng băng toàn bộ checkpoint, scorer và cấu hình.

### 7.4 Ma trận phương pháp

| Phương pháp | A | A₀.₇ | B | C |
|---|---|---|---|---|
| Ψ₀ | Có | Có | Có | Có |
| Diffusion Policy | Có | Không | Có | Không |
| ACT | Có | Không | Có | Không |

Nhánh C chỉ chạy với Ψ₀ vì tốn chi phí chẩn đoán. ACT và Diffusion Policy nhỏ, chạy được trên GPU của đội, và trả lời câu hỏi: dữ liệu sim giúp model nào nhiều nhất.

### 7.5 Đánh giá holdout và thống kê

- **Thiết kế ghép cặp:** mọi nhánh và mọi seed chạy trên đúng 150 điều kiện holdout. Mỗi nhánh có 150 × 3 seed = 450 episode.
- **Chỉ số chính:** tỉ lệ thành công toàn task, gộp ba mức và báo riêng từng mức.
- **Chỉ số phụ:** tỉ lệ đạt từng bước, sai số vị trí đặt (mm), thời gian hoàn thành, tỉ lệ hồi quy trên điều kiện Level 0, chi phí từ sổ chi phí.
- **Ước lượng:** với mỗi điều kiện i và nhánh a, p_ia là tỉ lệ thành công trung bình qua 3 seed. Chênh lệch giữa hai nhánh là trung bình theo i của (p_ia − p_ib). Khoảng tin cậy 95% lấy bằng bootstrap ghép cặp trên điều kiện, phân tầng theo mức, 10.000 lần lấy mẫu.
- **Độ ổn định:** báo kết quả từng seed; một kết luận chỉ được nêu khi chiều của chênh lệch giữ nguyên ở ít nhất 2/3 seed.
- **Kiểm độ rộng trước khi chạy holdout:** dùng phương sai đo trên dev để ước tính độ rộng khoảng tin cậy. Nếu nửa độ rộng dự kiến lớn hơn 7 điểm %, tăng số điều kiện holdout trước G5.

Để tham khảo: với 50 lượt độc lập ở mức 80%, khoảng tin cậy Wilson 95% là khoảng 67%–89%. Đó là lý do Pitch v10 cần chuyển từ "≥ 80% / 50 lượt" sang thiết kế ghép cặp nhiều seed ở trên.

### 7.6 Thí nghiệm H3: đo thời gian chẩn đoán

- **Mẫu:** 20 episode lỗi.
  - 10 lỗi **cấy có chủ đích**, biết đáp án: lệch lệnh controller, trễ camera, lệch calibration camera, thiếu vùng phủ (train bỏ một vùng điều kiện), ánh sáng ngoài miền; mỗi loại 2 episode.
  - 10 lỗi tự nhiên từ dev. Đáp án là chẩn đoán mà can thiệp tương ứng sửa được ít nhất một nửa số điều kiện trong cụm khi chạy lại.
- **Người tham gia:** 2–3 kỹ sư, trong đó nên có ít nhất 1 người không xây dựng công cụ.
- **Thiết kế chéo:** mỗi episode được một người chẩn đoán bằng log thô (video, đồ thị, file log) và một người khác chẩn đoán bằng evidence card; thứ tự đối trọng giữa người và điều kiện.
- **Đo:** số phút đến khi ra quyết định, chẩn đoán đúng theo 8 lớp ở mục 6.9, can thiệp đúng.
- **Ước lượng:** r_debug = 1 − (thời gian trung bình có card / thời gian trung bình với log thô), chỉ dùng khi độ đúng có card không thấp hơn.
- **Giới hạn phải nêu:** mẫu nhỏ; đáp án của lỗi tự nhiên có phần dựa vào chính các phép kiểm; người tham gia là thành viên đội.

### 7.7 Quy tắc diễn giải

- H1 và H2 được kết luận độc lập. H2 trượt là kết quả hợp lệ và phải được báo cáo: khi đó giá trị còn lại của platform là Data Core và sổ chi phí, và Pitch phải bỏ claim "chọn dữ liệu theo lỗi".
- Nếu C chỉ hơn B khi chưa tính chi phí chẩn đoán, báo cả hai con số.
- Kết quả âm, ứng viên bị từ chối, vòng không có cải thiện đều được giữ trong báo cáo cùng chi phí của chúng.

## 8. Sổ chi phí và mô hình kinh tế

### 8.1 Ghi chép

Mọi hoạt động tiêu tốn nguồn lực đều có một mục sổ (mục 4.5): thu teleop, reset cảnh, QA, sinh sim, chẩn đoán, train, đánh giá, lưu trữ, giờ kỹ sư tích hợp. Đơn giá dùng giả định của Pitch v10 cho đến khi có số của DENSO: operator $10/h, kỹ sư $20/h, A100 80 GB $1,59/GPU-h, RTX 4090 $0,74/GPU-h, lưu trữ $0,07/GB-tháng (nguồn ở slide 13 của pitch).

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

r_debug là đòn bẩy lớn nhất, và chỉ thí nghiệm H3 cho số đo của nó.

### 8.3 Thay giả định bằng số đo

| Giả định trong Pitch v10 | Số đo thay thế từ PoC |
|---|---|
| Giảm 30% demo | r_demo của nhánh thắng (mục 4.1), chỉ khi nhánh đó đạt H1 |
| Giảm 50% giờ debug | r_debug từ H3 |
| 140 A100-giờ train và đánh giá mỗi đợt | GPU-giờ thực trong sổ, theo từng nhánh |
| Thu/reset 6 phút, QA 3 phút mỗi lượt | Thời gian thực của teleop và correction trong SIMPLE |
| 144 đợt mỗi năm | Không đo được trong PoC; cần DENSO xác nhận số task và biến thể mỗi năm |

Chỉ số bổ sung nên báo cáo vì thuyết phục hơn đô-la: **số ngày từ khi đổi điều kiện đến khi policy đạt ngưỡng trở lại**, và **số giờ operator cần cho mỗi điểm % thành công tăng thêm**.

## 9. Lộ trình 12 tuần và cổng

| Tuần | Cổng | Việc | Điều kiện đi tiếp |
|---|---|---|---|
| 1–2 | G0 · Tái tạo | Cài SIMPLE và Ψ₀; chạy đánh giá trên một task đã công bố; trả lời Q1–Q6; đo VRAM, GPU-giờ fine-tune, thời gian mỗi episode | Kết quả lệch không quá 1/10 so với số công bố ở mỗi mức |
| 3–4 | G1 · Data Core v0 | Nạp psi-data, QA, lineage, chia tập; scorer từng bước; hiệu chỉnh τ_track, τ_cov; train thử ACT và Diffusion Policy | Scorer trùng cờ SIMPLE ≥ 95% (mục 5.3); train, nạp lại, đánh giá chạy trọn |
| 5–6 | G2 · Đường cong | E1 cho ba phương pháp; chọn D\* | D\* nằm trong lưới, không chạm trần hoặc sàn (mục 7.1) |
| 7–8 | G3 · Nhánh B | Bộ sinh sim, đo tỉ lệ sinh đạt; chọn ρ; train A, A₀.₇, B | Rollout sim qua QA; B_add được đo |
| 9–10 | G4 · Nhánh C và H3 | Tối đa 2 vòng Failure → Data; train C cuối từ base; thí nghiệm H3 | Sổ chi phí đầy đủ cho C; evidence card cho mọi cụm |
| 11 | G5 · Holdout | Đóng băng; chạy 150 điều kiện × 3 seed cho mọi nhánh | Chạy đúng một lần |
| 12 | G6 · Bàn giao | Báo cáo so sánh, SOP, video demo, cập nhật Pitch theo kết quả | Mọi claim trong pitch có số đo đi kèm hoặc được gỡ |

**Khối lượng dự kiến** (giờ máy cụ thể chỉ có sau G0):

| Hạng mục | Ψ₀ | ACT và Diffusion Policy |
|---|---|---|
| Fine-tune ở E1 | 5 | 10 |
| Chọn ρ | 2 | Không |
| Nhánh chính × 3 seed | 12 (A, A₀.₇, B, C) | 12 (A, B cho 2 phương pháp) |
| Fine-tune trong các vòng của C | 2 | Không |
| Tổng số lần train | Khoảng 21 | 22 |
| Episode holdout | 1.800 (thêm 450 nếu có B⁺) | 1.800 |

Ngân sách 140 A100-giờ mỗi đợt trong Pitch v10 phải được kiểm lại theo số đo ở G0.

## 10. Rủi ro và phương án dự phòng

| Rủi ro | Dấu hiệu | Dự phòng |
|---|---|---|
| Ψ₀ không vừa VRAM hoặc quá chậm | G0: hết bộ nhớ hoặc một lần fine-tune quá ngân sách | LoRA hoặc đóng băng VLM; thuê A100 80 GB; giảm còn 2 seed và ghi rõ |
| Không có planner cho task chính | Q2 là "không" | Task dự phòng F1; hoặc biến đổi đoạn teleop theo vị trí vật kiểu MimicGen |
| Chạm trần | Mọi mức dữ liệu đều ≥ 90% | Chỉ tiêu chính chuyển sang Level 2; hoặc đổi task khó hơn |
| Không reset được simulator | Q3 là "không" | Bỏ bước 6; khoanh vùng bằng chạy lại cùng hạt giống và để planner tiếp quản ở bước k |
| Không có thiết bị teleop | Q6 là "không" | Correction do planner sinh; báo cáo r_demo chỉ trên demo gốc |
| C không hơn B | Cận dưới CI của (C − B) ≤ 0 | Báo cáo trung thực; thu hẹp claim của pitch về Data Core và sổ chi phí |
| Kết quả sim không chuyển sang robot thật | Ngoài phạm vi PoC | Cổng nghiệm thu robot thật riêng; real2sim cho cell trước khi lên robot |

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

## 12. Glossary

| Thuật ngữ | Tiếng Anh | Nghĩa trong spec |
|---|---|---|
| Action chunk | Action chunk | Chuỗi hành động cho vài bước tới mà policy dự đoán trong một lần chạy |
| AMO | AMO | Bộ điều khiển thân dưới học bằng RL, là System-0 của Ψ₀ |
| B_add | Added acquisition budget | Chi phí thu dữ liệu bổ sung thực đo của nhánh B; là trần ngân sách cho nhánh C |
| Biến thể | Variant | Episode tạo ra bằng cách sửa một episode khác; không phải demo gốc |
| Bước | Stage | Một giai đoạn của task (tiếp cận, gắp, nâng, di chuyển, đặt, nhả) |
| Chẩn đoán | Diagnosis | Một trong 8 lớp ở mục 6.9 |
| Checkpoint | Checkpoint | Bộ trọng số đã lưu của model |
| Cổng | Gate | Điều kiện phải đạt trước khi sang giai đoạn sau |
| Cụm lỗi | Failure cluster | Nhóm các lỗi cùng bước hỏng, cùng kiểu lỗi và cùng mức |
| D\* | D-star | Số demo teleop nhỏ nhất để Ψ₀ đạt 80% trên dev |
| Demo gốc | Root demonstration | Demo do người thu (teleop hoặc correction); là đơn vị đếm khi nói "giảm X% demo" |
| Dev | Development set | Điều kiện dùng để tìm lỗi và chỉnh; không dùng để kết luận |
| Đường cong hiệu quả dữ liệu | Data-efficiency curve | Tỉ lệ thành công theo số demo dùng để train |
| Episode | Episode | Một lần chạy task từ đầu đến khi xong hoặc hết giờ |
| Evidence card | Evidence card | Thẻ ghi kết quả các phép kiểm, chẩn đoán, đề xuất và quyết định cho một cụm lỗi |
| Failure → Data | Failure-to-data | Thuật toán ở mục 6: từ lỗi đến quyết định bổ sung dữ liệu |
| Fine-tune | Fine-tuning | Tiếp tục train một model đã pretrain trên dữ liệu của task |
| Flow matching | Flow matching | Cách train action expert của Ψ₀: học biến nhiễu thành hành động |
| Flywheel | Data flywheel | Vòng lặp chạy → lỗi → dữ liệu → train → chạy, trong đó mỗi vòng làm vòng sau tốt hơn hoặc rẻ hơn |
| Hạt giống điều kiện | Condition seed | Số khởi tạo của bộ sinh môi trường, quyết định vector điều kiện của một episode |
| Seed huấn luyện | Training seed | Số khởi tạo ngẫu nhiên của một lần train; khác với hạt giống điều kiện |
| Holdout | Holdout set | Điều kiện chỉ dùng một lần để kết luận, sau khi đóng băng mọi thứ |
| Hồi quy | Regression | Policy mới làm hỏng điều kiện mà policy cũ đã làm được |
| Khoanh vùng | Localization | Phép kiểm ở mục 6.6, xác định lỗi do bước k hay do bước trước |
| Không kém hơn | Non-inferiority | Kiểm rằng nhánh mới không kém nhánh cũ quá một biên đã chốt trước (10 điểm %) |
| Level 0, 1, 2 | Evaluation levels | Ba mức thay đổi môi trường của SIMPLE (mục 2.2) |
| Lineage | Lineage | Thông tin nguồn gốc: từ đâu, giấy phép, episode cha, phiên bản bộ sinh |
| MP | Motion planning | Sinh quỹ đạo bằng thuật toán lập kế hoạch chuyển động thay vì người điều khiển |
| Ghép cặp | Paired design | Mọi nhánh chạy trên cùng các điều kiện để so sánh trực tiếp |
| Policy | Policy | Model nhận quan sát và câu lệnh, xuất hành động |
| QA | Quality assurance | Các phép kiểm dữ liệu ở mục 4.4 |
| r_demo | Demo reduction | Tỉ lệ demo gốc giảm được so với D\* |
| r_debug | Debug reduction | Tỉ lệ giờ chẩn đoán giảm được, đo ở H3 |
| Release | Dataset release | Phiên bản dữ liệu cố định, có QA và lineage, dùng để train |
| Rollout | Rollout | Một lần chạy policy hoặc planner trong simulator |
| Scorer từng bước | Stage scorer | Bộ chấm độc lập cho từng bước, dùng trạng thái đo được của simulator |
| SIMPLE | SIMPLE | Simulator và bộ đánh giá humanoid loco-manipulation của USC PSI Lab |
| Sổ chi phí | Cost ledger | Bản ghi mọi hoạt động và nguồn lực đã tiêu |
| Tăng cường thị giác | Visual augmentation | Biến đổi ảnh khi train (độ sáng, màu) để policy bền hơn với thay đổi hình ảnh |
| Teleop | Teleoperation | Người điều khiển robot từ xa để thu demo |
| Teleop correction | Correction | Người điều khiển tiếp quản từ một trạng thái lỗi của policy để hoàn thành task |
| Dữ liệu phục hồi | Recovery data | Correction bắt đầu từ trạng thái xấu do bước trước để lại |
| Tỉ lệ sửa được | Fix rate | Xác suất một loại can thiệp sửa được lỗi, cập nhật sau mỗi vòng |
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
- Đơn giá: [Runpod pricing](https://www.runpod.io/pricing), [Runpod storage](https://docs.runpod.io/pods/pricing), theo slide 13 của Pitch v10.
