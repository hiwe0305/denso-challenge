# Humanoid Data Flywheel · Tổng quan hệ thống

_Tài liệu trình bày với mentor ngày 28/10/2026. Đội ilovephysicalintelligence, thử thách DENSO Factory Hacks. Nội dung theo spec v10.4 và design ngày 27/10/2026; không nói về tiến độ code. Mọi con số của đội là mục tiêu, giả định hoặc ước lượng, chưa phải kết quả đo. Số của tác giả Ψ₀ ghi rõ là "tác giả báo"._

---

## 0. Một trang

**Vấn đề.** Dạy humanoid một kỹ năng mới tốn nhiều demo người, và mỗi lần robot hỏng, kỹ sư không biết nên sửa hệ thống hay thu thêm dữ liệu, thu loại gì, bao nhiêu, tốn bao nhiêu.

**Sản phẩm.** Humanoid Data Flywheel là một quy trình vận hành có kiểm toán cho vòng **lỗi → dữ liệu**: loại lỗi hệ thống trước khi tiêu tiền vào dữ liệu, chọn giữa nhiều loại can thiệp theo chi phí thật (kể cả chi phí chẩn đoán), và xuất **khuyến nghị thu dữ liệu định lượng** cho DENSO.

**Nền kỹ thuật.** Model Ψ₀ (USC PSI Lab, RSS 2026) dùng lại checkpoint của tác giả; robot Unitree G1 trong simulator SIMPLE; task chính là **task hai bàn**: G1 gắp vật ở bàn này, đi sang bàn kia, đặt vật lên.

**Bốn khối của hệ thống:**

1. **Thu dữ liệu** ba loại: **egocentric của người**, **teleop**, **synthetic**. Ba loại này cố định; chỉ nguồn để có dữ liệu thay đổi theo thời gian. Hiện giờ đội chứng minh hệ thống trên dữ liệu công bố và dữ liệu sim (EgoDex, dataset teleop của tác giả Ψ₀, teleop bàn phím và sinh tự động trong SIMPLE); sau đó thêm video egocentric đội tự quay; về sau là dữ liệu của DENSO.
2. **Xử lý và chuẩn hóa dữ liệu** qua 6 tầng về một định dạng chung cho cả ba loại, có QA (với dữ liệu robot thì phát lại action) trước khi train.
3. **Thuật toán Failure → Data** 12 bước: chạy policy, phân loại lỗi, kiểm hệ thống, chẩn đoán, chọn can thiệp theo lợi ích trên chi phí, thu, train, kiểm cổng.
4. **Đánh giá và kiểm soát**: scorer từng bước, bảng lỗi theo 5 nguồn tín hiệu, probe theo stage của Ψ₀, Agent QA/QC, sổ chi phí.

**Năm câu hỏi thí nghiệm:**

| Mã | Câu hỏi |
|---|---|
| HE | Dữ liệu egocentric của người có giúp Ψ₀ cần ít demo robot hơn không? |
| HS | Dữ liệu sim có thay được 30% demo teleop không? |
| HT | Thu dữ liệu nhắm theo lỗi có tốt hơn bổ sung đều không (HTa), và chẩn đoán có giúp thêm không (HTb)? |
| HD | Evidence card có giảm thời gian chẩn đoán của kỹ sư không? |
| M | ACT, Diffusion Policy và Ψ₀ cần bao nhiêu demo để đạt ngưỡng? |

**Mốc.** Demo ngày 17/11/2026 (tuần 4); PoC 12 tuần với 7 cổng G0–G6.

---

## 1. Đề bài và cách đội hiểu đề

**Đề của BTC** (ảnh đề ghi H2, bản chữ ghi H1; đang chờ BTC xác nhận mã): huấn luyện humanoid nhanh, chính xác, ít giờ công; thiết kế mô hình thu thập dữ liệu chuẩn của DENSO. Phạm vi 3 tháng: 1 kỹ năng thao tác trong simulation, so sánh ít nhất 2 phương pháp train và lượng dữ liệu cần.

**Ba cấp tiêu chí và cách đội đo:**

| Cấp BTC | Tiêu chí | Đội đo bằng |
|---|---|---|
| 1 · Basic | ≥ 50% với lượng demo nhỏ | Thành công ở mức 10% và 25% demo của đường cong dữ liệu (E1) |
| 2 · Efficient | Giảm ≥ 30% demo cùng hiệu năng; ≥ 75% | HS: nhánh dùng 0,7D\* demo cộng dữ liệu sim không kém nhánh D\* demo và đạt ≥ 75% |
| 3 · Advanced | ≥ 70% trên biến thể chưa train; khuyến nghị thu dữ liệu định lượng | Báo riêng Level 1 và Level 2 so với 70%; khuyến nghị lấy từ thuật toán Failure → Data cộng sổ chi phí |

D\* là số demo nhỏ nhất để Ψ₀ đạt ≥ 75% trên tập dev.

**Ba đầu ra 12 tuần, khớp đề:**

1. **DENSO Data Model**: Data Core (QA, lineage, chia tập, pipeline) cộng SOP thu và kiểm dữ liệu.
2. Báo cáo so sánh phương pháp huấn luyện (ACT, Diffusion Policy, Ψ₀) kèm kết quả HE, HS, HT, HD.
3. Demo kỹ năng đã học trên tập holdout, kèm khuyến nghị thu dữ liệu định lượng.

---

## 2. Định vị và ranh giới claim

**Đội không claim:**

- Thuật toán học máy mới. Các thành phần đều có tiền lệ: DAgger, HG-DAgger (correction), IntervenGen (sinh correction), MimicGen (sinh biến thể), DataMIL, CUPID (chọn dữ liệu). Ý "thu dữ liệu từ chỗ policy hỏng" đã có ở Mulligan (2026) và DISEIL (2026).
- Kết quả trên robot thật. Mọi số là trong mô phỏng; dữ liệu sim cùng phân phối với môi trường test nên lợi ích của sim có thể bị phóng đại.
- Tiết kiệm tiền mặt. Sổ chi phí đo nguồn lực theo đơn giá giả định.

**Đội claim (đóng góp):** cách ghép các phép kiểm thành **một quy trình ra quyết định có ghi chi phí** (kiểm hệ thống trước, rồi chọn giữa nhiều loại can thiệp bằng một thước đo tiền và giờ công gồm cả chi phí chẩn đoán), và **phép đo** xem quy trình đó có đáng tiền không. HT vì vậy là **kiểm lại** kết quả kiểu Mulligan / DISEIL trên humanoid toàn thân với Ψ₀, không phải điểm mới. HE là **kiểm lại** claim của Ψ₀ theo một cách tác giả chưa báo.

**Ba lớp:**

| Lớp | Nội dung |
|---|---|
| Kế thừa | Checkpoint Ψ₀ (pretrain trên khoảng 829 giờ video EgoDex và Humanoid Everyday, tác giả báo); SIMPLE; dataset psi-data; bộ điều khiển toàn thân decoupled WBC và AMO của SIMPLE |
| Đội làm | Data Core và pipeline 6 tầng cho ba loại dữ liệu (egocentric, teleop, synthetic); teleop bàn phím, sinh tự động S1 và S2 cho task hai bàn; scorer; Failure → Data; evidence card; sổ chi phí; probe theo stage; Agent QA/QC; thiết kế và chạy thí nghiệm có đối chứng |
| Sau PoC | Robot của DENSO (trong sim rồi robot thật), world model, synthetic đổi ngoại hình bằng Cosmos, continued pretraining trên video nhà máy |

---

## 3. Nền kỹ thuật

### 3.1 Ψ₀

| Thành phần | Mô tả (tác giả báo) | Đội dùng thế nào |
|---|---|---|
| System-2 · VLM | Qwen3-VL-2B-Instruct, pretrain trên video egocentric EgoDex rồi Humanoid Everyday | Kế thừa, không pretrain lại; chạy stage 1 ngắn trên EgoDex qua pipeline của đội để kiểm đường đi; fine-tune trên video đội tự quay khi còn thời gian |
| System-1 · Action expert | Flow matching (MM-DiT), khoảng 500M tham số, dự đoán action chunk toàn thân | Kế thừa bản post-train; fine-tune cùng VLM ở stage 3 |
| System-0 | Bộ điều khiển tầng thấp; trong SIMPLE task teleop chạy decoupled WBC, task motion planning chạy AMO | Kế thừa; là đối tượng của kiểm hệ thống |
| Chạy | Hơn 2,5B tham số, khoảng 160 ms mỗi lần suy luận, real-time chunking | Đo lại trên máy đội |

Paper báo Ψ₀ có tỉ lệ thành công tổng cao hơn 40% so với các baseline pretrain trên lượng dữ liệu nhiều hơn 10 lần, trên các task robot thật, với khoảng 80 trajectory mỗi task để fine-tune (tác giả báo).

### 3.2 SIMPLE

Simulator benchmark của cùng nhóm tác giả, chạy MuJoCo cho vật lý và Isaac Sim cho render. Có G1, hơn 50 cảnh, 18 gói dữ liệu task công khai, ba mức đánh giá:

| Mức | Thay đổi so với môi trường train | Vai trò |
|---|---|---|
| Level 0 | Vật liệu bàn, vật gây nhiễu | Trong miền |
| Level 1 | Level 0 cộng ánh sáng mạnh | Ngoài miền về hình ảnh |
| Level 2 | Level 1 cộng vị trí ban đầu của vật | Ngoài miền về hình ảnh và vị trí |

### 3.3 Task chính: hai bàn

`G1WholebodyLocomotionPickBetweenTablesTeleop-v0`: G1 gắp vật ở bàn nguồn, đi sang bàn đích, đặt vật lên. Lý do chọn:

- Đúng cảnh trưởng nhóm muốn (gắp, di chuyển, đặt), gần công đoạn nhà máy.
- Có dataset teleop của tác giả (203 MB) và checkpoint công bố, nên tái tạo và so được.
- Ψ₀ công bố 7/5/6 trên 10 lượt mỗi mức (tác giả báo): chưa chạm trần, còn chỗ để đo khác biệt giữa các phương pháp.

**Sáu bước của task** (dùng cho scorer và phân loại lỗi): tiếp cận → gắp → đi → tới bàn đích → đặt → nhả và ổn định. Điều kiện suốt episode: thân trong giới hạn thăng bằng.

---

## 4. Kiến trúc tổng thể của data flywheel

```text
                    ┌──────────────────────────── VÒNG FLYWHEEL ────────────────────────────┐
                    │                                                                        │
  ┌──────────────┐  │  ┌────────────┐   ┌──────────────┐   ┌───────────┐   ┌──────────────┐  │
  │ 1 THU DỮ LIỆU │──┼─►│ 2 XỬ LÝ VÀ │──►│ 3 TRAIN Ψ₀   │──►│ 4 CHẠY    │──►│ 5 PHÂN LOẠI   │  │
  │ egocentric    │  │  │ CHUẨN HÓA  │   │ stage 1 ←ego │   │ POLICY    │   │ LỖI, KIỂM     │  │
  │ teleop        │  │  │ 6 tầng, QA │   │ stage 3 ←    │   │ trong sim │   │ HỆ THỐNG,     │  │
  │ synthetic     │  │  │ release    │   │ teleop, syn. │   │           │   │ CHẨN ĐOÁN     │  │
  └──────▲───────┘  │  └────────────┘   └──────────────┘   └───────────┘   └──────┬───────┘  │
         │          │                                                              │          │
         │          │  ┌──────────────────────────────┐   ┌───────────────────────▼───────┐  │
         └──────────┼──┤ 7 THU THEO KẾ HOẠCH          │◄──┤ 6 ĐỀ XUẤT CAN THIỆP, ĐỊNH      │  │
                    │  │ (sinh sim, correction,       │   │ LƯỢNG, CHỌN THEO LỢI ÍCH /     │  │
                    │  │ dữ liệu phục hồi)            │   │ CHI PHÍ, KỸ SƯ DUYỆT           │  │
                    │  └──────────────────────────────┘   └───────────────────────────────┘  │
                    └────────────────────────────────────────────────────────────────────────┘
        Xuyên suốt: sổ chi phí (mọi job) · lineage · Agent QA/QC đọc báo cáo · holdout khóa trong vault
```

**Tài sản tích lũy sau mỗi vòng:** release dữ liệu có lineage; bảng tỉ lệ sửa được theo loại can thiệp và loại lỗi; sổ chi phí ước tính và thực đo; evidence card cho từng cụm lỗi. Đây là thứ làm vòng sau rẻ hơn vòng trước.

---

## 5. Khối 1 · Thu dữ liệu

### 5.1 Ba loại dữ liệu và nguồn để test

Hệ thống có **ba loại dữ liệu cố định**. Mỗi loại đi qua data flywheel và đi vào một phần của model. Cái thay đổi theo thời gian chỉ là nguồn để có dữ liệu: đội chứng minh hệ thống trên dữ liệu công bố và dữ liệu sim trước, rồi thêm dữ liệu đội tự thu, về sau là dữ liệu của DENSO. Thay nguồn không đổi pipeline hay model.

| Loại | Nguồn bây giờ (công bố, sim) | Nguồn sau (khi còn thời gian) | Về sau | Flywheel làm gì | Vào model ở đâu |
|---|---|---|---|---|---|
| **Egocentric của người** | Mẫu EgoDex (dữ liệu Ψ₀ đã pretrain, có sẵn pose tay và tư thế camera) | Video đội tự quay người làm task hai bàn | Video công nhân DENSO | Che danh tính, cắt đoạn theo bước, pose tay và camera, xuất định dạng stage 1 của Ψ₀, QA | Stage 1 (VLM); thí nghiệm HE |
| **Teleop** | Dataset teleop của tác giả cho task hai bàn (psi-data); teleop bàn phím trong SIMPLE | | Teleop trên robot DENSO | Đồng bộ, chuẩn hóa, cắt đoạn, QA, phát lại action | Stage 3 (fine-tune theo task) |
| **Synthetic** | S1 motion planning và S2 biến thể từ đoạn teleop, trong SIMPLE | | S3, S4 bằng Cosmos qua NVIDIA NIM | QA bằng chạy lại trong sim, đo tỉ lệ sinh đạt và chi phí mỗi tầng | Trộn vào train ở nhánh B và C |

### 5.2 Egocentric

| Nguồn | Có gì | Pose tay | Độ tin |
|---|---|---|---|
| Mẫu EgoDex | Video Apple Vision Pro, có tracking tay và đầu | Đọc trực tiếp (phương án E-B) | Cao |
| Video đội tự quay | Điện thoại hoặc camera đội đầu, người làm task hai bàn | Ước lượng bằng model hand pose và SLAM (phương án E-A) | Thấp hơn, gắn nhãn `pseudo` |

Giới hạn phải nêu: stage 1 học chuyển động **bàn tay người**, còn G1 cầm bằng bàn tay robot khác cấu trúc. Giá trị chính của egocentric nằm ở hình ảnh và cấu trúc task; vì vậy đội kiểm tác dụng của nó bằng thí nghiệm HE thay vì giả định.

### 5.3 Teleop: dataset của tác giả và bàn phím

Dataset của tác giả cho task hai bàn (203 MB) thu bằng kính PICO, chạy bộ điều khiển decoupled WBC. Đội không có PICO nên tự viết thiết bị bàn phím.

#### Teleop bàn phím

SIMPLE chỉ hỗ trợ teleop bằng kính PICO 4 cùng tracker đeo cổ chân. Thiết bị bàn phím thay luồng PICO:

| Phím | Điều khiển |
|---|---|
| Nhóm đi | Vận tốc tiến, lùi, sang ngang, xoay; đi qua planner đi bộ của WBC |
| Nhóm tay | Chọn tay trái hoặc phải; dịch cổ tay theo x, y, z và xoay; IK của SIMPLE đổi thành tư thế thân trên |
| Bàn tay | Đóng, mở |
| Episode | Bắt đầu, thành công, thất bại, reset |

Vì đi cùng decoupled WBC, dữ liệu bàn phím trộn được với dữ liệu của tác giả. Giới hạn: chậm và kém mượt hơn PICO; dùng để so phương pháp và thu correction, không để nói số tuyệt đối về dữ liệu người thật. Mỗi phiên ghi phút người vào sổ chi phí.

### 5.4 Synthetic: S1 và S2 trước demo

| Tầng | Cách sinh | Action | Nhắm lỗi gì | Khi nào |
|---|---|---|---|---|
| S1 · Planner | Motion planning từ điều kiện ngẫu nhiên trong miền train | Do planner sinh | Thiếu vùng phủ | Trước demo |
| S2 · Biến thể từ teleop | Biến đổi đoạn teleop theo tư thế vật mới (kiểu MimicGen); correction từ trạng thái lỗi đã lưu | Do planner sinh | Thiếu vùng phủ, trạng thái đầu xấu | Trước demo |
| S3 · Đổi ngoại hình | Giữ quỹ đạo, đổi ánh sáng, vật liệu, nền bằng Cosmos Transfer | Giữ action gốc | Nhận thức | Sau demo |
| S4 · Video task mới | Sinh video từ ảnh đầu cộng câu lệnh bằng Cosmos Predict | Suy ra, độ tin thấp | Biến thể chưa có demo | Sau PoC, chỉ khi RunPlan cho phép |

Mỗi tầng là một loại can thiệp riêng trong thuật toán Failure → Data, có đơn giá và tỉ lệ sửa được riêng, nên flywheel tự học tầng nào đáng tiền. Không sinh bằng tham số của Level 1, Level 2 để tránh rò sang tập đánh giá.

#### Sinh tự động S1 và câu hỏi bộ điều khiển (V3)


| Tuyến | Cách làm | Ưu | Nhược |
|---|---|---|---|
| A · Planner trong env WBC | Script đi bộ cộng cuRobo trong env teleop của task hai bàn | Cùng bộ điều khiển với teleop, trộn được | Phải tự viết |
| B · Biến thể MP của SIMPLE | Task MP mới theo mẫu task MP có sẵn, chạy `datagen` | Gần như dùng nguyên công cụ của tác giả | Chạy AMO, khác bộ điều khiển; không trộn với teleop khi chưa có ánh xạ |

Checkpoint `…mixed-v0` của tác giả cho task hai bàn gợi ý họ đã trộn hai nguồn; đội đọc metadata của nó để chọn tuyến ở tuần đầu.

### 5.5 Giảm compute của Isaac Sim

| Chế độ | Dùng cho |
|---|---|
| MuJoCo thuần (`--sim-mode=mujoco`) | Teleop, sinh tự động, phát lại, eval nhanh |
| MuJoCo + render Isaac (`mujoco_isaac`) | Eval so với số công bố, video demo |
| Replay & Render | Render lại episode đã thu bằng MuJoCo sang ảnh Isaac; vật lý không đổi |

Quy tắc: trong một thí nghiệm, ảnh train và ảnh eval cùng một renderer. Theo README Ψ₀, eval ở chế độ render Isaac mất 6–10 phút mỗi episode vì render đồng bộ; đây là chi phí lớn nhất của hệ thống, lớn hơn thu dữ liệu.

---

## 6. Khối 2 · Xử lý và chuẩn hóa dữ liệu

### 6.1 Sáu tầng

```text
1 Ingest      tải thô, sha256, nguồn kèm giấy phép và mức nhạy cảm (data_class)
2 Normalize   giải mã, đồng bộ thời gian, đổi đơn vị và khung, ánh xạ vào action_layout
3 Annotate    cắt đoạn theo bước task, nhãn ngôn ngữ; egocentric: che danh tính trước mọi bước
4 QA          7 phép kiểm bắt buộc, phép kiểm riêng của từng loại dữ liệu, phát lại action
5 Release     manifest đóng băng, chặn rò tập, giấy phép gộp
6 Export      teleop, synthetic: LeRobot v2.1 cho Ψ₀ (bắt buộc), v3 (tùy chọn)
              egocentric: định dạng stage 1 của Ψ₀ (biến đổi khớp tay kiểu EgoDex + video)
              mọi loại: stats, contract test đọc lại bằng loader của Ψ₀
```

Cả ba loại đi cùng sáu tầng; mỗi loại hiện thực khác nhau ở tầng 1–4:

| Tầng | Egocentric | Teleop | Synthetic |
|---|---|---|---|
| Ingest | Video, tracking tay và đầu nếu có | Bản ghi LeRobot của tác giả, bản ghi bàn phím | Episode do planner sinh, kèm tầng, tuyến, phiên bản planner |
| Normalize | Tư thế camera, khớp tay 3D về một khung; fps chung | Đồng bộ, SI, ánh xạ khớp vào `action_layout` | Như teleop |
| Annotate | **Che danh tính** (mặt, thẻ tên, màn hình); cắt đoạn theo bước task; câu lệnh | Cắt đoạn theo bước bằng luật (bàn tay đóng mở, vận tốc đi bằng 0) | Bước đã biết từ planner |
| QA riêng | Độ tin của pose, tỉ lệ tay ra khỏi khung, độ rung | Phát lại action; khoảng dừng của người điều khiển | Chạy lại trong sim đạt; khoảng cách tới demo gốc (S2) |

### 6.2 Định dạng episode chung

Mọi loại dữ liệu về một bundle: `frames.parquet` (state và action theo nhóm, mỗi nhóm có cột lệnh gửi và giá trị đo), `signals.parquet`, `videos/`, `segments.parquet` (đoạn theo bước, nhãn ngôn ngữ), `meta.json` (tham số camera, timestamp từng khung). Trường quan trọng: loại dữ liệu (`source_kind`: egocentric, teleop, synthetic) và nguồn (`source_detail`), trạng thái che danh tính (`deid_status`), tầng synthetic, độ tin của action (`measured`, `planned`, `retargeted`, `pseudo`), embodiment, renderer, hạt giống điều kiện, mức nhạy cảm.

### 6.3 Chuẩn hóa

| Việc | Cách làm |
|---|---|
| Đồng bộ | Mọi luồng về đồng hồ chung; state nội suy về tần số điều khiển; mỗi camera giữ timestamp riêng |
| Đơn vị, khung | SI, radian, khung theo URDF của G1 |
| Action | Ánh xạ vào khung 36 chiều của Ψ₀, có mask cho chiều đệm |
| Ảnh | Đổi kích thước theo config fine-tune của Ψ₀, giữ bản gốc |
| Ngôn ngữ | Câu lệnh task chuẩn hóa một mẫu cho mọi nguồn |
| Egocentric | Episode egocentric không có action robot; chỉ vào stage 1, probe và làm mẫu cho bộ sinh, không bao giờ vào stage 3 |

### 6.4 QA bắt buộc

| Phép kiểm | Ngưỡng | Khi trượt |
|---|---|---|
| Timestamp đơn điệu, bước đều | Lệch ≤ 1 chu kỳ điều khiển | Loại |
| Đồng bộ ảnh và state | Lệch ≤ 1 khung | Sửa, không được thì loại |
| Giới hạn khớp, giá trị hữu hạn | Theo URDF; không NaN, Inf | Loại |
| Bước nhảy action | ≤ phân vị 99,9 của demo teleop | Đánh dấu cho kỹ sư |
| Kết quả task | Scorer báo thành công | Không làm mẫu dương; giữ làm bằng chứng lỗi |
| Lineage | Có nguồn, giấy phép, cha, hạt giống, phiên bản bộ sinh | Cách ly |
| Chia tập | Hạt giống thuộc dải train | Vô hiệu hóa release |
| Phát lại action | Xem dưới | Loại hoặc đánh dấu |

**Phát lại action trên MuJoCo**, cho mọi episode có action robot (teleop, synthetic):

- **Động học**: đặt state theo bản ghi từng khung. Bắt sai ánh xạ khớp, sai đơn vị, vượt giới hạn, ảnh lệch thời gian với state. Trượt thì loại.
- **Động lực học**: từ state đầu, áp action đã ghi qua bộ điều khiển. Bắt action không tái tạo được state (sai tần số, delta hay tuyệt đối, sai dấu), lệch thời điểm đóng mở tay. Vượt ngưỡng thì đánh dấu.

Ngưỡng hiệu chỉnh từ episode thành công, không đoán trước. Mẫu bị loại vẫn giữ cùng lý do và chi phí, không xóa để làm đẹp tỉ lệ.

### 6.5 Export và chuẩn LeRobot

Egocentric xuất đúng định dạng mà loader stage 1 của Ψ₀ đọc (khớp tay kiểu EgoDex cộng video, độ dài chunk và cách tính action như config gốc), kèm stats. Teleop và synthetic: Ψ₀ dùng một fork của LeRobot định dạng v2.1; export kèm checklist 7 mục chạy tự động: `info.json` khớp `action_layout`; chỉ số episode liên tục; timestamp khớp fps; video giải mã được và đủ khung; mọi episode có câu lệnh; stats tính trên đúng release, không NaN; đọc lại bằng loader của Ψ₀ ra đúng một batch mẫu.

### 6.6 Chia tập và chống rò

Chia theo **hạt giống điều kiện** trước khi sinh biến thể: train; dev 90 điều kiện (30 mỗi mức); holdout 150 điều kiện (50 mỗi mức). Dải hạt giống rời nhau và rời dải tác giả đã dùng. Guard gần trùng cách ly điều kiện dev hoặc holdout quá gần train. Holdout khóa trong `vault/`, chỉ module `gate` đọc, mỗi cặp nhánh và seed chạy đúng một lần.

### 6.7 Báo cáo dataset

Mỗi release có một trang HTML: số episode theo loại dữ liệu và theo nguồn; pass, flag, reject theo phép kiểm; phân bố điều kiện; stats theo nhóm action; video phát lại cạnh video gốc. Đây là số đo hiệu suất của pipeline.

---

## 7. Khối 3 · Thuật toán Failure → Data

### 7.1 Mười hai bước của một vòng

| Bước | Việc | Ra |
|---|---|---|
| 1 | Chạy policy trên 90 điều kiện dev | Trace |
| 2 | Gán nhãn | Bước hỏng đầu tiên k, kiểu lỗi |
| 3 | Gom cụm sơ bộ theo (k, kiểu lỗi, mức) | Cụm, tối đa R đại diện |
| 4 | **Kiểm hệ thống** | Lỗi controller, runtime, đồng bộ, calibration, thiếu tín hiệu |
| 4b | Quy lỗi về stage của Ψ₀ (từ probe) | Giả thuyết stage gây lỗi |
| 5 | Kiểm khả thi bằng planner chuẩn | Task có làm được từ điều kiện đó không |
| 6 | Khoanh vùng: đặt sim vào trạng thái chuẩn ở đầu bước k | s_k |
| 7 | Kiểm thị giác: giữ vật lý, đổi hình ảnh về chuẩn | Lỗi nhận thức hay không |
| 8 | Kiểm vùng phủ | Trong miền train không; khoảng cách tới train |
| 9 | Chẩn đoán cụm theo đa số | Một trong 11 chẩn đoán |
| 10 | Đề xuất và định lượng can thiệp | Can thiệp, số lượng, chi phí ước tính |
| 11 | Chọn theo lợi ích kỳ vọng trên chi phí, trong ngân sách; kỹ sư duyệt | Danh sách can thiệp |
| 12 | Thu, QA, train, cổng dev | Release mới, policy ứng viên, tỉ lệ sửa được đo có đối chứng |

**Thứ tự cố định: hệ thống trước, dữ liệu sau.** Lỗi đã có chẩn đoán hệ thống không đi tiếp vào nhánh dữ liệu.

### 7.2 Mười một chẩn đoán

| Chẩn đoán | Điều kiện | Can thiệp | Tiêu ngân sách dữ liệu |
|---|---|---|---|
| CHƯA RÕ | Thiếu tín hiệu | Sửa logging | Không |
| LỖI CONTROLLER | Sai số bám lệnh vượt ngưỡng | Sửa cấu hình WBC, ánh xạ khớp | Không |
| LỖI RUNTIME | Độ trễ vượt ngưỡng | Sửa pipeline suy luận | Không |
| LỖI ĐỒNG BỘ | Ảnh và state lệch thời gian | Sửa đồng bộ cảm biến | Không |
| LỖI CALIBRATION | Camera khác bản tham chiếu | Sửa calibration | Không |
| KHÔNG KHẢ THI | Planner chuẩn cũng thất bại | Sửa cảnh, thu hẹp miền task | Không |
| TRẠNG THÁI ĐẦU XẤU | Policy làm được bước k khi bắt đầu từ trạng thái chuẩn | Dữ liệu phục hồi từ trạng thái do policy tạo | **Có** |
| NHẬN THỨC | Đổi hình ảnh về chuẩn thì thành công | Báo cáo | Không |
| NGOÀI MIỀN | Điều kiện ngoài miền train | Báo cáo | Không |
| THIẾU VÙNG PHỦ | Trong miền nhưng xa dữ liệu train | Sinh rollout sim quanh điều kiện lỗi | **Có** |
| KỸ NĂNG YẾU | Trong miền, gần dữ liệu train | Teleop correction ở bước k | **Có** |

### 7.3 Chọn can thiệp và đo "flywheel học"

- Mỗi loại can thiệp t có **tỉ lệ sửa được** f_t, phân phối Beta, khởi đầu Beta(1, 1).
- Lợi ích kỳ vọng của đề xuất cho cụm j: g_j = (số lỗi xử lý / 90) × trung bình f_t. Chi phí c_j lấy từ đơn giá trong sổ chi phí. Chọn theo g_j / c_j giảm dần tới hết ngân sách.
- **Cổng dev**: mỗi vòng dùng tập 90 điều kiện mới, chạy cha và ứng viên ≥ 3 lượt; ứng viên phải tăng ≥ 1 sai số chuẩn, cụm được can thiệp phải cải thiện, hồi quy không vượt max(5%, sàn A/A).
- **Tỉ lệ sửa được đo có đối chứng**: trên điều kiện mới quanh lỗi, so cha với ứng viên, tránh thiên lệch hồi quy về trung bình khi chỉ chạy lại đúng điều kiện cũ.
- Ψ₀ chạy 1 vòng mặc định (đắt); bằng chứng "flywheel học" lấy từ **F-ACT**: 5–8 vòng rẻ trên ACT, xem khoảng tin cậy của f_t có hẹp dần và chi phí mỗi điểm % có giảm không.

---

## 8. Khối 4 · Đánh giá và kiểm soát

### 8.1 Scorer từng bước và kiểu lỗi

Scorer chấm 6 bước của task hai bàn. Bước chưa tới là "chưa thử", không phải "trượt"; thiếu tín hiệu là "chưa rõ", không phải "đạt". Chỉ số chính ở holdout vẫn là cờ thành công của SIMPLE (so được với số công bố); scorer chỉ cho chỉ số theo bước và nhãn lỗi. Scorer phải trùng cờ SIMPLE ≥ 95% trên 100 episode trước khi dùng.

| Kiểu lỗi | Lớp chung | Dấu hiệu |
|---|---|---|
| L-REACH | Tiếp cận | Hết giờ ở bước tiếp cận |
| L-GRASP | Gắp | Đóng tay nhưng không giữ được vật |
| L-SLIP | Mang | Rơi vật khi đi |
| L-WALK | Mang | Dừng giữa hai bàn, đi sai hướng, dừng ngoài vùng bàn đích |
| L-PLACE | Đặt | Vật ngoài vùng đích |
| L-RELEASE | Đặt | Nhả sai lúc |
| L-COLLIDE | Theo bước | Va chạm ngoài ý muốn |
| L-BALANCE | Thăng bằng | Vi phạm giới hạn thân |
| L-TIMEOUT, L-UNKNOWN | Theo bước, không gán | Đứng yên; thiếu tín hiệu |

### 8.2 Bảng lỗi theo 5 nguồn tín hiệu

| Nguồn | Mã | Ví dụ |
|---|---|---|
| Dữ liệu và pipeline (chặn train) | D1–D8 | Sai schema, lệch đồng bộ, vượt giới hạn, stats sai, rò tập, nhãn sai, phát lại trượt, synthetic hỏng |
| Train (đọc từ log) | T1–T8 | Phân kỳ, không học, quá khớp, một nhóm action không học, chiều chết, sụp mode, quên, gradient bất thường |
| Offline (action trên episode giữ lại) | O1–O4 | Sai số theo nhóm cao, sai số tăng theo vị trí trong chunk, lệch thời điểm bàn tay, action ngoài giới hạn |
| Closed-loop (eval trong sim) | Kiểu lỗi ở 8.1 | Chấm bằng scorer |
| Runtime và hệ thống | R1–R6 | Độ trễ, buffer cạn, bám lệnh WBC kém, lệch đồng bộ, lệch calibration, server lỗi |

### 8.3 Probe theo stage của Ψ₀

Checkpoint công bố không kèm log train, nên "output của stage" là kết quả chạy bộ probe cố định có hash:

| Probe | Trên | Đo |
|---|---|---|
| P1 · Hiểu cảnh | VLM | Hỏi đáp có đáp án về vật, bàn, bước đang làm trên khung hình SIMPLE |
| P2 · Token action | VLM | Loss dự đoán chuyển động tay trên egocentric giữ lại |
| P3 · Action offline | Action expert, checkpoint fine-tune | Sai số action theo nhóm và theo vị trí trong chunk |
| P4 · Giữ năng lực | Sau fine-tune | Chạy lại P1, P3 trên dữ liệu gốc để đo quên |

Probe cho phép quy lỗi về stage: P1 sai trên khung hình của lượt lỗi → stage 1 nhận thức; P1 đúng, P3 cao → stage 3 học action; P1 đúng, P3 thấp mà closed-loop vẫn hỏng → lỗi tích lũy khi chạy; lỗi mới sau fine-tune kèm P4 giảm → quên.

### 8.4 Agent QA/QC

```text
job dữ liệu / train / eval / infer ─► code tính số và dựng hình ─► Agent QA/QC viết báo cáo ─► kỹ sư duyệt
```

| Điểm | Quyết định |
|---|---|
| Model | **Nemotron 3.5 Bolt E4B 4GB** (NVIDIA, ra 23/10/2026; dựng trên Gemma-4-E4B-it; 8B tham số tổng, 4B hiệu dụng; ngữ cảnh 64K; chỉ đọc chữ theo tài liệu NVIDIA; gọi được tool; bản Q4 khoảng 3–4 GB VRAM; giấy phép OpenMDW-1.1). Chạy cục bộ trên RTX 3060, ghim revision; dev và CI dùng model giả |
| Vì sao | Việc của agent là đọc số và chữ có cấu trúc, so ngưỡng, xếp hạng, viết đề xuất; model nhỏ cục bộ giữ dữ liệu trong máy và gần như không tốn tiền mỗi lần chạy |
| Nhìn hình (tùy chọn) | **Qwen3.5-4B** (Apache 2.0, nhận ảnh) qua endpoint thứ hai, chỉ khi cần agent tự xem bảng ảnh stage 1 hay video phát lại; chưa chốt |
| Đọc | Báo cáo dataset, báo cáo phát lại, log train, kết quả probe, kết quả eval, log inference (dòng thời gian real-time chunking của eval bất đồng bộ) |
| Biểu diễn cho người | Code dựng: bảng ảnh stage 1 (khung hình, câu hỏi, câu trả lời, đáp án, khung xương tay); đồ thị action dự đoán so với thật kèm video MuJoCo phát lại; dòng thời gian RTC (độ trễ, buffer, bước nhảy ở ranh giới chunk) |
| Không được | Đọc holdout; tự chạy job; tự chọn dữ liệu; nêu con số không có trong đầu vào |
| Số liệu | Mọi con số do code tính; agent diễn giải, xếp hạng, đề xuất và trích số |
| Đầu ra | Báo cáo HTML mỗi job; kỹ sư ghi đồng ý hoặc ghi đè kèm lý do |

**Đo hiệu suất trước khi có log thật: bộ lỗi cấy.** Đội cấy lỗi có đáp án khóa trước vào bản sao dataset thật của tác giả (rơi khung, lệch thời gian, nhảy khớp, sai đơn vị, đảo dấu action, nhãn thành công sai, rò hạt giống…) và vào log train, log inference sinh từ bộ giả (phân kỳ, chiều chết, độ trễ, buffer cạn). Báo precision và recall theo từng loại lỗi, tỉ lệ báo nhầm trên bản sạch, và tách phần phép kiểm bằng code bắt được khỏi phần agent thêm vào. Số này ghi rõ là "trên lỗi cấy". Bản cấy lỗi không bao giờ vào dữ liệu train. Trước đó, agent chạy qua một bộ ca mẫu ≥ 10 ca có đáp án (log bình thường, loss phân kỳ, chiều action chết, độ trễ vượt ngưỡng, chunk giật); chạy lại mỗi khi đổi model hoặc prompt.

### 8.5 Eval đồng bộ và bất đồng bộ

Ψ₀ cần khoảng 160 ms mỗi lần suy luận và dùng real-time chunking. Nếu sim dừng chờ policy, lỗi do trễ không bao giờ xuất hiện. Vì vậy eval có hai chế độ: **đồng bộ** để gỡ lỗi và so với tác giả (dùng cho G0 và HE); **bất đồng bộ** với độ trễ lấy từ log inference thật (dùng cho chỉ số chính của HS, HT).

### 8.6 Model phụ trợ cho các pipeline dữ liệu

Ngoài Ψ₀, các pipeline dùng một số model nhỏ, trọng số mở, chạy cục bộ trên RTX 3060 (lần lượt theo job). Model chỉ gợi ý; luật và người duyệt mẫu quyết. Thông tin tra ngày 25/10/2026, benchmark là số tự công bố.

| Vai | Model | Ghi chú |
|---|---|---|
| VLM stage 1 của Ψ₀ | Giữ Qwen3-VL-2B | Đổi backbone là train lại stage 1 và 2 |
| Gợi ý ranh giới bước trong video egocentric | RoboBrain 2.5-4B | Ước tiến độ task theo từng khung |
| Theo dõi tay, vật, điểm gắp | Molmo2-4B | Chỉ điểm và theo dõi vật trong video |
| Lọc thô video | SmolVLM2-2.2B | Rẻ nhất, tùy chọn |
| Đối chứng cho probe P1 | RoboBrain 2.5-4B hoặc HY-Embodied-0.5 | Đo VLM của Ψ₀ yếu ở loại câu hỏi nào |
| Che danh tính, pose tay 3D, tư thế camera (video tự quay) | Model phát hiện mặt và chữ; model hand pose; visual SLAM | Chọn khi làm pipeline egocentric |
| Synthetic S1, S2 | cuRobo, IK và WBC của SIMPLE | Không phải model học máy |
| Synthetic S3, S4 (sau demo) | Cosmos Transfer, Cosmos Predict, lọc bằng Cosmos Reason qua NVIDIA NIM | Dữ liệu `restricted`, `internal` chỉ đi NIM tự host |

Model gán nhãn và model nhìn hình chốt bằng một vòng thử 4–6 giờ (ước lượng) trên 30 khung EgoDex, 30 khung render SIMPLE và bộ câu hỏi P1: đo độ đúng hỏi đáp, sai số ranh giới bước, tỉ lệ chỉ đúng điểm gắp, VRAM và độ trễ.

---

## 9. Thiết kế thí nghiệm

### 9.1 Giả thuyết và tiêu chí (chốt trước khi chạy)

| Mã | So sánh | Tiêu chí chấp nhận |
|---|---|---|
| HE | V-EGO so với V-NOEGO trên Ψ₀ | Cận dưới CI 95% của chênh lệch > 0 ở ít nhất hai mức demo, và V-EGO đạt 50% với ít demo hơn |
| HS | B so với A và A₀.₇ | B ≥ 75% trên holdout; cận dưới CI 95% của (B − A) > −10 điểm %; cận dưới CI 95% của (B − A₀.₇) > 0 |
| HT | C so với B, cùng ngân sách thu dữ liệu | Cận dưới CI 95% của (C − B) > 0; báo kèm tổng chi phí của C gồm chẩn đoán |
| HTa | B-fail so với B | Cận dưới CI 95% > 0 (nhắm theo lỗi, không chẩn đoán) |
| HTb | C so với B-fail | Cận dưới CI 95% > 0 (chẩn đoán giúp thêm) |
| HD | Có evidence card so với công cụ chuẩn (Rerun) | Thời gian giảm, độ đúng không thấp hơn; báo dạng khoảng; là pilot |
| M | ACT, Diffusion Policy, Ψ₀ | Mô tả: thành công theo mức, số demo để đạt 75%, chi phí train |

Kết quả âm của mọi giả thuyết là kết quả hợp lệ và được báo cáo.

### 9.2 Các nhánh

| Nhánh | Dữ liệu train | Vai trò |
|---|---|---|
| A | D\* demo teleop | Baseline |
| A₀.₇ | 0,7D\* demo teleop | Đối chứng không bổ sung; là policy khởi đầu của C |
| B | 0,7D\* + rollout sim lấy đều trong miền train | Kiểm HS; đối thủ của C |
| B-fail | 0,7D\* + rollout sim quanh mọi lỗi, không chẩn đoán | Tách tác dụng của nhắm theo lỗi |
| C | 0,7D\* + dữ liệu do Failure → Data chọn | Kiểm HT |

**Quy tắc công bằng:** cùng checkpoint gốc, cùng số bước gradient và learning rate; cùng danh sách 0,7D\* demo; cùng tăng cường thị giác cho mọi nhánh; C và B-fail bị chặn ở đúng chi phí thu dữ liệu của B; không sinh dữ liệu bằng tham số của Level 1, 2; holdout chạy một lần sau khi đóng băng.

### 9.3 Thống kê

- Ghép cặp: mọi nhánh, mọi seed chạy trên cùng 150 điều kiện holdout; 3 seed train.
- CI 95% bằng **bootstrap phân cấp** (lấy mẫu lại seed, rồi điều kiện trong từng mức), 10.000 lần; kiểm chéo bằng logistic hỗn hợp.
- **Power analysis ở G2**: nếu hiệu ứng nhỏ nhất phát hiện được của C − B > 10 điểm %, chọn trước: thêm seed, đổi mức của chỉ tiêu, hoặc hạ HT thành kết quả mô tả.

### 9.4 Thí nghiệm HE: dữ liệu egocentric và số demo robot

**Bằng chứng hiện có của paper** (tác giả báo, trên 2 task robot thật, 10 lượt): không pretrain 2/10; pretrain 10% EgoDex 1/10 so với 8/10 khi đủ; chỉ Humanoid Everyday 4/10 so với 8/10 và 7/10. Fine-tune luôn 80 trajectory. Paper **không có đường cong thành công theo số demo robot** và không báo số trên SIMPLE.

**Cơ hội:** tác giả công bố checkpoint ablation, nên đội làm được thí nghiệm có đối chứng mà không phải pretrain lại:

| Biến thể | VLM pretrain trên | Action expert |
|---|---|---|
| V-EGO | EgoDex đủ cộng Humanoid Everyday | Bản post-train tương ứng |
| V-EGO10 (tùy chọn) | 10% EgoDex | Bản post-train tương ứng |
| V-NOEGO | Chỉ Humanoid Everyday | Bản post-train tương ứng |

| Thiết kế | Giá trị |
|---|---|
| Task | Task hai bàn |
| Lưới demo | N ∈ {10, 20, 40, 80}, danh sách lồng nhau cố định bằng hash |
| Fine-tune | Recipe của tác giả, giống nhau ở mọi điểm |
| Seed | 1 seed mọi điểm, thêm seed thứ hai ở N = 20, 40 |
| Eval | 30 điều kiện × 3 mức, cùng hạt giống cho mọi biến thể; mốc so là checkpoint của tác giả |
| Chỉ số | Thành công theo N (đường cong), theo mức, N₅₀ (số demo để đạt 50%), chênh lệch V-EGO − V-NOEGO có CI |
| Giai đoạn | HE-1 trên dataset teleop của tác giả (sơ bộ trước demo); HE-2 trên dataset teleop và synthetic đội tự xây |
| Video | Ba cột cùng điều kiện: V-EGO, V-NOEGO, checkpoint của tác giả |

**Giới hạn phải nêu:** ba VLM khác cả số bước pretrain và có action expert post-train riêng, nên đội không tách được hai yếu tố này; kết quả trong sim.

**Hai tầng chứng minh cho egocentric.**

| Tầng | Dữ liệu | Chứng minh gì |
|---|---|---|
| Trên dữ liệu công bố (trước) | Checkpoint ablation (HE); mẫu EgoDex qua pipeline | HE cho thấy tác dụng của egocentric lên số demo robot. Mẫu EgoDex đi trọn pipeline, xuất đúng định dạng stage 1, và một lần chạy stage 1 ngắn (vài trăm bước) chứng minh đường đi từ dữ liệu tới model chạy trọn; lần chạy này không phải thí nghiệm |
| Trên dữ liệu đội tự quay (khi còn thời gian) | Video người làm task hai bàn | Fine-tune stage 1 trên video đúng task, đo bằng probe P1, P2 và closed-loop; so với VLM gốc |

**Chi phí ước lượng** (chưa đo): một điểm của đường cong là 90 episode; ở 8 phút mỗi episode, khoảng 12 giờ máy; 12 điểm khoảng 144 giờ máy eval. Phương án rút gọn: eval ở MuJoCo thuần nếu G0 cho thấy Ψ₀ giữ độ chính xác; giảm điều kiện; bỏ V-EGO10.

### 9.5 Đường cong dữ liệu E1 và D\*

Train ACT, Diffusion Policy, Ψ₀ ở 10%, 25%, 50%, 70%, 100% số demo teleop đạt QA; D\* là mức nhỏ nhất Ψ₀ đạt ≥ 75% trên dev (thêm seed thứ hai quanh ngưỡng để chống may mắn). Lưới của HE trùng E1 cho Ψ₀, nên dùng chung các lần fine-tune V-EGO.

---

## 10. Sổ chi phí và mô hình kinh tế

**Mọi job ghi một mục sổ**: hoạt động, loại nguồn lực (operator, kỹ sư, GPU, lưu trữ), số lượng, đơn giá, nhánh, vòng, cụm, cờ "ước tính" hay "thực đo". Đơn giá giả định theo Pitch v10: operator $10/h, kỹ sư $20/h, A100 $1,59/GPU-h; chưa tính chi phí giờ cell của nhà máy.

**Công thức Pitch v10** (lợi ích ròng mỗi đợt cải thiện): 500 × r_demo + 400 × r_debug − 181,80 USD, với r_demo là tỉ lệ giảm demo, r_debug là tỉ lệ giảm giờ debug.

Đội nói thẳng hai điểm yếu của công thức: HT không đóng góp đô-la nào trong công thức; và với r_demo = 30% thì hòa vốn chỉ cần r_debug khoảng 8%, nên "có lãi" gần như chắc chắn. Vì vậy báo cáo **không dẫn bằng đô-la** mà bằng các chỉ số đo được:

1. Số demo người để đạt 75%, theo phương pháp và theo nhánh.
2. Phút operator cho mỗi điểm % tăng thêm.
3. Chi phí mỗi điểm % tăng của C so với B và B-fail, gồm chi phí chẩn đoán.
4. Sai số dự báo chi phí: (ước tính − thực đo) / thực đo.
5. Số ngày để policy đạt lại ngưỡng sau khi đổi điều kiện.

Kèm bảng độ nhạy theo đơn giá DENSO và chi phí giờ cell.

---

## 11. Kiến trúc phần mềm

### 11.1 Hình thái

Lõi là một thư viện Python kèm CLI `fw`, chạy trên máy host. Adapter nặng (SIMPLE, Ψ₀, LeRobot) chạy ngoài tiến trình, trong container riêng, trao đổi qua job spec JSON và thư mục chung. Lý do: SIMPLE và Ψ₀ cần phiên bản Python, PyTorch, CUDA khác nhau.

### 11.2 Nhân, ba làn và adapter

```text
                         ┌──────────────── NHÂN ────────────────┐
                         │ contracts (schema, 6 Protocol)        │
                         │ store (kho sha256, DuckDB, vault)     │
                         │ testkit (bộ giả, file mẫu, lỗi cấy)   │
                         │ cli (lệnh fw, nối làn và adapter)     │
                         └──────────▲────────▲────────▲─────────┘
                                    │        │        │   chỉ import nhân
            ┌───────────────────────┴┐ ┌─────┴──────┐ ┌┴──────────────────────┐
            │ LÀN DỮ LIỆU             │ │ LÀN ĐÁNH GIÁ│ │ LÀN VÒNG QUYẾT ĐỊNH   │
            │ ingest, normalize,      │ │ scorer,     │ │ RunPlan, runner,      │
            │ annotate, QA, phát lại, │ │ chẩn đoán,  │ │ decide, gate, holdout,│
            │ release, export, cấy lỗi│ │ evidence    │ │ sổ chi phí, báo cáo,  │
            │                         │ │ card, Agent │ │ HD                    │
            │                         │ │ QA/QC       │ │                       │
            └─────────────────────────┘ └────────────┘ └───────────────────────┘
                     ▲ qua 6 Protocol, không import trực tiếp
     ┌───────────────┴──────────────────────────────────────────────────────┐
     │ ADAPTER: flywheel-simple (sim, bàn phím, sinh tự động) · flywheel-psi0  │
     │ (policy, trainer, probe, RTC) · flywheel-lerobot (ACT, DP) · flywheel-nim│
     └────────────────────────────────────────────────────────────────────────┘
```

**Sáu Protocol** là ranh giới duy nhất giữa lõi và thế giới cụ thể: SimulatorAdapter, PolicyAdapter, TrainerAdapter, GeneratorAdapter, TeleopSource, TaskDefinition. Đổi robot, simulator hay model là viết adapter mới, lõi không đổi.

**Bất biến kiến trúc** (CI kiểm bằng import-linter và test):

- Lõi không import simulator, model hay framework train.
- Ba làn không import lẫn nhau; dữ liệu đi giữa làn là artifact có schema trong `contracts`.
- Mọi code của làn chạy được trên CPU với bộ giả.
- Catalog và sổ chi phí append-only; sửa sai bằng bút toán đảo.
- Holdout trong `vault/`, chỉ `gate` đọc.
- Dữ liệu `restricted`, `internal` (mọi dữ liệu DENSO) không bao giờ ra dịch vụ hosted bên ngoài.

### 11.3 Mô hình dữ liệu

12 thực thể L0-lite: Source, Condition, Episode, QAReport, Release, Checkpoint, RunPlan, Score, Cluster, FixRateEvent, LedgerEntry, Decision. Mọi thứ có content hash; RunPlan đóng băng trước khi chạy và ghim phiên bản mọi thành phần (commit SIMPLE, revision checkpoint, revision dataset, digest image), nên mọi kết quả tái lập được.

### 11.4 Thiết kế để mở rộng L0 → L4

| Mức | Phạm vi | Lõi thêm gì |
|---|---|---|
| L0 | 1 task, sim (PoC 12 tuần) | Như trên |
| L1 | 3–5 task cùng robot | Tỉ lệ sửa được dùng chung theo lớp lỗi chung giữa task |
| L2 | 1 cell thật | Adapter robot thật, an toàn, real2sim |
| L3–L4 | Nhiều robot, nhiều nhà máy | Lưu theo site, chia sẻ có kiểm soát |

### 11.5 Hạ tầng tính toán

| Máy | Dùng cho |
|---|---|
| RTX 3060 12 GB | Dev, SIMPLE ở MuJoCo thuần, teleop, phát lại, Agent QA/QC, ACT, Diffusion Policy |
| Colab Pro (A100, H100) | Fine-tune Ψ₀; eval nặng nếu Isaac Sim chạy được trên Colab |

Dữ liệu của demo là công khai (psi-data, sim G1) nên lên Colab được. Mọi job tiếp tục được từ checkpoint và ghi compute unit vào sổ chi phí.

---

## 12. Demo ngày 17/11/2026

| # | Phần | Cho thấy |
|---|---|---|
| 1 | Tái tạo Ψ₀ | Checkpoint của tác giả trên task hai bàn, bảng so với 7/5/6, video |
| 2 | Thu dữ liệu ba loại | Mẫu EgoDex; teleop bàn phím một episode trực tiếp; vài episode sinh tự động S1 và biến thể S2 |
| 3 | Pipeline | Ba loại dữ liệu qua 6 tầng: egocentric ra định dạng stage 1, teleop và synthetic ra release LeRobot; báo cáo dataset |
| 4 | Agent QA/QC | Precision, recall trên bộ lỗi cấy; một báo cáo mẫu |
| 5 | HE-1 sơ bộ | Đường cong V-EGO so với V-NOEGO, video ba cột |
| 6 | Một vòng Failure → Data | Lượt thất bại → scorer → chẩn đoán → evidence card → đề xuất dữ liệu → sổ chi phí |

Chưa có ở demo (nói thẳng khi trình bày): video egocentric đội tự quay, HE-2 trên dataset tự xây, S3 và S4, HS, HT, HD, holdout.

---

## 13. Lộ trình 12 tuần và cổng

| Tuần | Cổng | Việc chính | Điều kiện qua |
|---|---|---|---|
| 1–2 | G0 · Tái tạo | Cài SIMPLE, Ψ₀; tái tạo số công bố; trả lời các câu hỏi kỹ thuật Q0–Q6, V3; đo chi phí fine-tune và eval; thiết bị bàn phím ghi được episode | Thành công không thấp hơn số công bố có ý nghĩa thống kê (30 lượt mỗi mức) |
| 3–4 | G1 · Data Core v0 | Pipeline cho cả ba loại dữ liệu (EgoDex, teleop, S1, S2), QA, chia tập; scorer; một lát dọc chạy trọn; Agent QA/QC trên lỗi cấy; **demo 17/11** | Scorer trùng cờ SIMPLE ≥ 95% |
| 5–6 | G2 · Đường cong | E1 và HE-1 đủ lưới; chọn D\*; power analysis | D\* trong lưới, không chạm trần hay sàn |
| 7–8 | G3 · Nhánh B | Sinh sim; train A, A₀.₇, B; A/A test | Rollout sim qua QA; chi phí của B đo được |
| 9–10 | G4 · Nhánh C và HD | Một vòng Failure → Data trên Ψ₀; F-ACT 5–8 vòng trên ACT; thí nghiệm HD; holdout sớm và niêm phong cho nhánh không phụ thuộc C | Sổ chi phí đủ cho C; evidence card cho mọi cụm |
| 11 | G5 · Holdout | Đóng băng, chạy holdout cho C, mở niêm phong | Mỗi cặp nhánh và seed chạy đúng một lần |
| 12 | G6 · Bàn giao | Báo cáo so sánh, SOP, video, khuyến nghị thu dữ liệu | Mọi claim có số đo hoặc bị gỡ |

Lập kế hoạch ở 70% năng lực đội; khi vượt thời gian, thay phần tự xây bằng API hoặc phần có sẵn trước, rồi mới cắt phạm vi.

---

## 14. Rủi ro chính

| Rủi ro | Dấu hiệu | Dự phòng |
|---|---|---|
| Không đủ GPU cho Ψ₀ | Khoảng 22 lần fine-tune mặc định, thêm 8–10 cho HE (ước lượng) | Vòng lặp chạy trên ACT, DP; rút gọn HE; mua thêm compute |
| Eval có render Isaac quá chậm | 6–10 phút mỗi episode | Eval ở MuJoCo thuần nếu G0 cho phép; giảm điều kiện; chạy song song |
| Teleop và motion planning khác bộ điều khiển (V3) | Dữ liệu tuyến B không trộn được với teleop | Tuyến A trong env WBC; không trộn khi chưa có ánh xạ |
| Pose tay ước lượng từ video tự quay quá nhiễu | Độ tin pose thấp, tay ra khỏi khung nhiều | Gắn nhãn `pseudo`, báo riêng; dùng video cho hình ảnh và cấu trúc task, không cho nhãn action; EgoDex vẫn là nguồn chính |
| Video egocentric có người thật | Mặt, thẻ tên, màn hình trong khung | Che danh tính bắt buộc trước mọi bước; dữ liệu DENSO không bao giờ ra dịch vụ hosted |
| Demo bàn phím ít hoặc kém | Giờ người cho 20 demo thử cao | Dựa thêm vào sinh tự động và dataset tác giả; bàn phím chủ yếu cho correction |
| HE bị nhiễu bởi khác biệt ngoài dữ liệu egocentric | Ba checkpoint ablation khác số bước pretrain | Nêu giới hạn; hỏi tác giả; thêm P1 làm bằng chứng phụ |
| Checkpoint gốc đã thấy dữ liệu task chính (Q0) | Ψ₀ ở mức dữ liệu thấp cao bất thường | Chỉ dùng checkpoint có nguồn gốc rõ; hỏi tác giả; ghi giới hạn |
| Chạm trần | Mọi mức dữ liệu ≥ 90% | Chỉ tiêu chính chuyển sang Level 2 |
| Thiếu lực thống kê | Hiệu ứng nhỏ nhất phát hiện được > 10 điểm % | Thêm seed; hoặc hạ HT thành kết quả mô tả |
| Dữ liệu sinh tự động giúp ít hơn dữ liệu người | Kết quả âm đã có trong tài liệu (Mirchandani và cộng sự, CoRL 2024) | Điều kiện (B − A₀.₇) > 0 bắt buộc; nếu HS âm thì khuyến nghị ưu tiên teleop correction |
| C không hơn B | Cận dưới CI ≤ 0 | Báo trung thực; thu hẹp claim về Data Core, sổ chi phí, khuyến nghị thu dữ liệu |

---

## 15. Câu hỏi muốn hỏi mentor

**Về thiết kế thí nghiệm**

1. Thí nghiệm HE dùng checkpoint ablation khác nhau cả số bước pretrain. Cách đọc kết quả nào là chấp nhận được, và có nên thêm đối chứng nào rẻ (ví dụ probe P1) để tách yếu tố không?
2. Lưới N ∈ {10, 20, 40, 80} với 1 seed (thêm seed ở hai điểm) có đủ để vẽ đường cong đáng tin không, hay nên ít điểm hơn nhưng nhiều seed hơn?
3. Eval ở MuJoCo thuần thay cho render Isaac để tiết kiệm compute: rủi ro nào khi checkpoint của tác giả được train trên ảnh Isaac?
4. Với 150 điều kiện holdout và 3 seed, HT khó có đủ lực thống kê. Mentor thấy nên giữ HT là kiểm định hay chấp nhận là kết quả mô tả ngay từ đầu?

**Về dữ liệu**

5. Dữ liệu teleop bàn phím có đáng tin để so phương pháp không, hay nên đầu tư một bộ PICO?
6. Trộn dữ liệu sinh bằng bộ điều khiển AMO với teleop chạy WBC: có cách ánh xạ nào mentor từng thấy hiệu quả không?
7. Video egocentric đội tự quay (điện thoại, camera đội đầu) cho task hai bàn: nên quay bao nhiêu giờ, góc nào, và có nên mượn thiết bị có tracking tay (ví dụ Vision Pro) để pose đáng tin hơn?

**Về sản phẩm**

8. Ở góc nhìn nhà máy, chỉ số nào thuyết phục DENSO nhất: số demo người để đạt ngưỡng, phút operator mỗi điểm %, hay số ngày để policy đạt lại ngưỡng?
9. Agent QA/QC chỉ diễn giải số do code tính. Mentor thấy giá trị của nó nằm ở đâu nếu phép kiểm bằng code đã bắt phần lớn lỗi?

---

## Phụ lục A · Thuật ngữ

| Thuật ngữ | Nghĩa |
|---|---|
| Ψ₀ | Foundation model cho humanoid của USC PSI Lab: VLM (System-2), action expert (System-1), bộ điều khiển tầng thấp (System-0) |
| SIMPLE | Simulator benchmark của cùng nhóm tác giả, vật lý MuJoCo, render Isaac Sim |
| Decoupled WBC, AMO | Hai bộ điều khiển toàn thân của G1 trong SIMPLE: WBC cho task teleop, AMO cho task motion planning |
| Egocentric | Video quay từ góc nhìn người làm việc (EgoDex); một trong ba loại dữ liệu của hệ thống |
| E-A, E-B | Hai cách có pose tay cho egocentric: ước lượng từ video RGB (E-A), hoặc đọc từ thiết bị có tracking (E-B) |
| S1–S4 | Bốn tầng synthetic: planner, biến thể từ teleop, đổi ngoại hình, video task mới |
| Demo teleop | Episode do người điều khiển, đạt QA và scorer |
| Teleop correction | Đoạn người điều khiển bắt đầu từ trạng thái lỗi của policy |
| Rollout sim | Episode do planner sinh rồi chạy trong sim; không tính là demo gốc |
| D\* | Số demo nhỏ nhất để Ψ₀ đạt ≥ 75% trên dev |
| N₅₀ | Số demo nhỏ nhất để đạt 50%, nội suy trên đường cong HE |
| Evidence card | Thẻ cho một cụm lỗi: bước hỏng, kết quả mọi phép kiểm kèm ngưỡng, chẩn đoán, can thiệp đề xuất, chi phí, quyết định của kỹ sư |
| Tỉ lệ sửa được f_t | Xác suất một loại can thiệp sửa được một lỗi, đo có đối chứng |
| Cổng dev | Điều kiện để chấp nhận policy ứng viên sau một vòng |
| Holdout | Tập điều kiện khóa, chạy một lần ở cuối để kết luận |
| Bộ lỗi cấy | Bản sao dữ liệu và log thật được cấy lỗi có đáp án, dùng để đo QA và Agent QA/QC |
| RunPlan | Kế hoạch chạy đóng băng: dữ liệu, checkpoint, recipe, seed, tiêu chí |

## Phụ lục B · Nguồn

- Ψ₀: repo `github.com/physical-superintelligence-lab/Psi0`, paper arXiv 2603.12263, checkpoint `huggingface.co/USC-PSI-Lab/psi-model`.
- SIMPLE: repo `github.com/physical-superintelligence-lab/SIMPLE`, tài liệu `psi-lab.ai/SIMPLE/docs`.
- Dữ liệu: `huggingface.co/datasets/USC-PSI-Lab/psi-data`.
- Tiền lệ: Mulligan (arXiv 2610.05882), DISEIL (arXiv 2609.08123), MimicGen (arXiv 2310.17596), IntervenGen (arXiv 2405.01472), DataMIL (arXiv 2505.09603), CUPID (arXiv 2506.19121).
- Tài liệu chi tiết trong repo: spec v10.4 (`docs/spec-v10-failure-to-data.md`), design 27/10/2026 (`docs/superpowers/specs/2026-10-27-g1-psi0-demo-design.md`), kiến trúc (`docs/product/03-architecture.md`).
