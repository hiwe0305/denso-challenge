# Kịch bản quay video demo · Humanoid Data Flywheel (17/11/2026)

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 15/11/2026 | 0.2 | Sửa sau khi site xong và sau lượt soát số: thêm "khay nằm trên bàn B 50/60 so với 43/60" (cảnh 6); thay cặp 16,1 → 12,7 cm bằng "trượt sát nút 4 → 11 lượt" (cảnh 11); sửa câu về 2 441; bỏ "0 giờ người"; cột màn hình theo route thật; đếm lại thời lượng; bảng việc mở thành bảng đã kiểm | Hiếu (soạn với Claude) |
| 15/11/2026 | 0.1 | Bản đầu: 12 cảnh, lời nói đầy đủ, nguồn từng số, danh sách kiểm trước khi quay | Hiếu (soạn với Claude) |

Video quay màn hình website Flywheel Console ở chế độ khóa (`--lock`), tối đa 15 phút. Kịch bản bám cấu trúc site bản 0.3 ([design 0.3](../superpowers/specs/2026-11-15-console-flywheel-v03-design.md)) và bộ số đã kiểm. Script thuyết trình cho phiên dịch ở [file riêng](2026-11-17-script-thuyet-trinh.md).

## 1. Yêu cầu của ban tổ chức và chỗ trả lời

Yêu cầu nguyên văn: "Video tối đa 15 phút giải thích và demo sản phẩm. Cần nêu rõ được các vấn đề sau: INPUT - OUTPUT của quy trình, ENVIRONMENT và các DEVICES đi cùng, các yêu cầu về DATA, RESOURCE và quá trình xử lý của sản phẩm/dịch vụ."

| Mục | Cảnh chính | Cảnh nhắc lại |
|---|---|---|
| INPUT - OUTPUT | 2 (Thiết kế) | 6, 8 |
| ENVIRONMENT | 2 | |
| DEVICES | 2 | |
| DATA | 3 (Bước 1) | 4, 10 |
| RESOURCE | 2 | 5, 7, 10 |
| Quá trình xử lý | 3–8 (sáu bước), 9 (một lượt thật đi trọn vòng) | 11 |

## 2. Thông điệp và giọng

- Ba phần, theo đúng thứ tự: cái đã chạy tốt (hệ thống đo và kiểm định) → cái chưa tốt, nói thẳng 10/60 → 4/60 kèm cách đọc đo được và vì sao dừng là đúng → việc tiếp theo và lộ trình. Bản hôm nay là nền cho các vòng sau.
- Một ví dụ chạy suốt: lượt thi mức 1, seed 1000107 (cảnh 9).
- Từ nhà máy, dùng ít và đúng nghĩa: PDCA (vòng 6 bước, cảnh 2), kiểm tra đầu vào (Agent QA/QC, cảnh 4), kế toán chi phí (sổ chi phí, cảnh 10), Jidoka (luật viết trước cho dừng, cảnh 11).
- Không dùng từ quảng cáo. Mọi kết quả có mẫu số. Mỗi màn có kết quả nói một lần "sơ bộ, mô phỏng, mỗi bản dạy một lần" (cảnh 6, 11; cảnh 1 nói chung cho cả video).
- Trên trang story chỉ dùng tên thường của bản dạy ("425 bài mẫu", "sau vòng 1"), không đọc mã nội bộ.

## 3. Cách tính thời lượng

- Tốc độ nói 130 từ một phút. "Từ" ở đây là âm tiết khi đọc to; số đọc thành chữ rồi mới đếm (ví dụ "2 572" là 7 âm tiết, "77,27" là 7). Đếm bằng script, không đếm tay.
- Thời lượng một cảnh = số từ × 60 / 130, làm tròn tới giây, cộng 2 giây chuyển màn.
- Tổng: **1730 từ**, lời nói **13:19**, cả video **13:43** (12 lần chuyển màn × 2 giây). Còn khoảng 1:17 dự phòng tới mốc 15:00.

| Cảnh | Tên | Bắt đầu | Kết thúc | Số từ | Lời nói (giây) |
|---|---|---|---|---|---|
| 1 | Mở đầu: một câu ý tưởng | 0:00 | 0:56 | 116 | 54 |
| 2 | Thiết kế: đầu vào, đầu ra, môi trường, thiết bị, tài nguyên | 0:56 | 2:46 | 235 | 108 |
| 3 | Bước 1 · Nạp, chuẩn hóa (yêu cầu về dữ liệu) | 2:46 | 4:00 | 155 | 72 |
| 4 | Bước 2 · Agent QA/QC | 4:00 | 4:51 | 106 | 49 |
| 5 | Bước 3 · Dạy Ψ₀ | 4:51 | 5:21 | 60 | 28 |
| 6 | Bước 4 · Thi, chấm 7 bước | 5:21 | 6:35 | 157 | 72 |
| 7 | Bước 5 · Kiểm hệ thống, chẩn đoán | 6:35 | 7:22 | 98 | 45 |
| 8 | Bước 6 · Lỗi → Dữ liệu | 7:22 | 8:07 | 93 | 43 |
| 9 | Theo chân một lỗi: mức 1, seed 1000107 | 8:07 | 9:27 | 169 | 78 |
| 10 | Sổ chi phí, và số cập nhật sau khi nộp slide | 9:27 | 10:57 | 190 | 88 |
| 11 | Bảng nền: đã chứng minh, chưa chứng minh, việc tiếp theo | 10:57 | 12:38 | 215 | 99 |
| 12 | Mở rộng và kết | 12:38 | 13:43 | 136 | 63 |
| | **Tổng** | 0:00 | 13:43 | **1730** | **799** |

## 4. Kịch bản từng cảnh

### Cảnh 1 · Mở đầu: một câu ý tưởng

| Trường | Nội dung |
|---|---|
| Thời gian | 0:00–0:56 (56 giây) |
| Màn hình | `#/home` (trang vòng tròn). Không bấm gì trong 5 giây đầu. Phải thấy: tiêu đề "Robot hỏng ở đâu, thu dữ liệu đúng chỗ đó", vòng 6 bước với sổ chi phí ở giữa, dải kết quả cố định dưới tiêu đề có "10/60 → 4/60 · dừng". Cuối cảnh, rê chuột theo chiều kim đồng hồ qua 6 nút. |
| Lời nói | Xin chào quý vị. Chúng tôi là đội ilovephysicalintelligence, với sản phẩm Humanoid Data Flywheel. Ý tưởng nằm trong một câu: robot hỏng ở đâu, thu dữ liệu đúng chỗ đó. Thông thường, người ta thu thêm thật nhiều dữ liệu mà ít khi biết mỗi vòng tốn bao nhiêu. Đội làm khác. Robot thi trong nhà máy ảo. Hệ thống tìm đúng bước robot hỏng, kiểm lỗi hệ thống trước, rồi mới thu dữ liệu cho bước đó, và ghi chi phí của từng việc. Video có ba phần: phần đã chạy tốt, phần chưa tốt kèm lý do đo được, và các bước tiếp theo. Mọi số là sơ bộ, đo trong mô phỏng. |
| Mục của BTC | Ý tưởng; quá trình xử lý (tóm tắt một câu) |
| Số từ | 116 |

### Cảnh 2 · Thiết kế: đầu vào, đầu ra, môi trường, thiết bị, tài nguyên

| Trường | Nội dung |
|---|---|
| Thời gian | 0:56–2:46 (110 giây) |
| Màn hình | `#/design`. Rê chuột lần lượt qua 5 khối theo thứ tự lời nói: Đầu vào, Đầu ra, Môi trường, Thiết bị, Tài nguyên. Phải thấy cả 5 nhãn tiếng Anh INPUT, OUTPUT, ENVIRONMENT, DEVICES, RESOURCE cạnh nhãn tiếng Việt, và hàng 6 bước ở giữa. |
| Lời nói | Trang Thiết kế trả lời năm yêu cầu của ban tổ chức. INPUT, tức đầu vào: mô tả kỹ năng và bố trí bàn A, bàn B; bài mẫu robot do máy sinh trong mô phỏng; video người; và teleop, tức người điều khiển robot từ xa để làm mẫu. OUTPUT, tức đầu ra: model đã dạy; bảng điểm bảy bước cho biết robot hỏng ở bước nào; khuyến nghị thu dữ liệu gì, bao nhiêu, tốn bao nhiêu; và báo cáo so sánh các cách dạy. ENVIRONMENT, tức môi trường: robot Unitree G1, model Ψ₀, trình mô phỏng SIMPLE chạy vật lý MuJoCo, còn Isaac Sim chỉ để dựng hình. DEVICES, tức thiết bị: laptop chạy Flywheel Console; máy RTX 3060 để sinh dữ liệu và chạy lượt thi; GPU đám mây Colab để dạy và chạy model; điện thoại đeo đầu để quay video người. RESOURCE, tức tài nguyên, tính bằng CU, đơn vị GPU của Colab, giả định 0,1 USD một CU. Một lần dạy model ở vòng vừa rồi đo được 77,27 CU. Sinh và kiểm 181 bài mẫu mới mất khoảng 1,8 giờ máy. Quá trình xử lý là sáu bước trên vòng tròn, một vòng PDCA cho việc dạy robot. |
| Mục của BTC | INPUT, OUTPUT, ENVIRONMENT, DEVICES, RESOURCE, quá trình xử lý (giới thiệu) |
| Số từ | 235 |

### Cảnh 3 · Bước 1 · Nạp, chuẩn hóa (yêu cầu về dữ liệu)

| Trường | Nội dung |
|---|---|
| Thời gian | 2:46–4:00 (74 giây) |
| Màn hình | `#/home?s=1` (2 giây: bảng bước 1 bên phải, số 2 572 trên nút), rồi bấm "Xem chi tiết bước 1" sang `#/data`. Phải thấy ba thẻ nguồn: video người 379, teleop 193 với dòng "dữ liệu của tác giả, việc khác, 0 tập của việc bê khay", mô phỏng 2 000 (S1 1 032 + S2 968), và ô thành phần lần dạy gần nhất (301 + 124 + 181). Cuối cảnh mở `#/sim`, rê chuột qua 2 ảnh bài mẫu. |
| Lời nói | Bước một: nạp và chuẩn hóa ba loại dữ liệu về chuẩn LeRobot. Kho có 2 572 tập không trùng. Video người có 379 clip, gồm video đội tự quay và mẫu EgoDex đã công bố. Video người rẻ vì quay bằng điện thoại. Teleop có 193 tập, là dữ liệu công bố của nhóm tác giả cho một việc khác. Đội có 0 tập teleop của việc bê khay. Teleop tốn giờ người nhiều nhất. Bài mẫu máy sinh trong mô phỏng có 2 000 tập, chỉ tốn giờ máy. Vì vậy hệ thống ưu tiên nguồn rẻ. Lần dạy gần nhất dùng 606 bài mẫu máy sinh: 301 bài phủ rộng, 124 bài nhắm lỗi từ vòng trước, và 181 bài nhắm lỗi của vòng này. |
| Mục của BTC | DATA; quá trình xử lý bước 1 |
| Số từ | 155 |

### Cảnh 4 · Bước 2 · Agent QA/QC

| Trường | Nội dung |
|---|---|
| Thời gian | 4:00–4:51 (51 giây) |
| Màn hình | `#/home?s=2` (nút bước 2 ghi 30/30), rồi bấm "Xem chi tiết bước 2" sang `#/jobs?view=pipeline`. Phải thấy ba ô số 30/30 · 0/40 · 317/379 và hai chuỗi lọc bên dưới. Rê chuột lên ô 30/30 một giây để hiện nguồn. Quay lại `#/data`, cuộn tới "Xem ví dụ thật", rê chuột lên một clip "bị loại" để thấy lý do. |
| Lời nói | Bước hai: Agent QA/QC, tức kiểm định viên tự động. Nó kiểm từng tập dữ liệu trước khi dạy, giống khâu kiểm tra đầu vào ở nhà máy. Với video người, 379 clip đi vào, 317 clip qua kiểm định, 54 clip bị loại, và 8 clip bị loại từ trước. Để thử kiểm định viên, đội cố ý cấy lỗi vào bản sao dữ liệu. Ở lớp kiểm tra bằng mã, nó bắt được 30 trên 30 lỗi cấy và báo nhầm 0 trên 40 lần trên dữ liệu sạch. |
| Mục của BTC | DATA (chất lượng); quá trình xử lý bước 2 |
| Số từ | 106 |

### Cảnh 5 · Bước 3 · Dạy Ψ₀

| Trường | Nội dung |
|---|---|
| Thời gian | 4:51–5:21 (30 giây) |
| Màn hình | `#/home?s=3`: nút bước 3 màu xám, nhãn "giữ nguyên". Rồi `#/runs`: lưới 5 bản đã dạy với tên thường và chi phí đo của từng lần dạy. Không mở "Chi tiết kỹ thuật". |
| Lời nói | Bước ba: dạy Ψ₀. Đây là bước duy nhất đội giữ nguyên, không thêm mô-đun. Model Ψ₀ là của nhóm tác giả và đã học trước từ video người. Đội dạy tiếp model trên một bộ dữ liệu đã đóng băng. Đến nay đội đã dạy năm bản để so sánh. Mỗi bản dạy một lần trên GPU đám mây. |
| Mục của BTC | RESOURCE (GPU); quá trình xử lý bước 3 |
| Số từ | 60 |

### Cảnh 6 · Bước 4 · Thi, chấm 7 bước

| Trường | Nội dung |
|---|---|
| Thời gian | 5:21–6:35 (74 giây) |
| Màn hình | `#/home?s=4`, rồi `#/eval`. Phải thấy số "10/60" màu trung tính, số "78–87 %", dòng "sơ bộ, mô phỏng, mỗi bản dạy một lần" và thanh 7 bước của bản 425 bài mẫu. Rê chuột từ "tới bàn A" xuống "đặt xuống". Bấm phát video "Một lượt thành công" khoảng 6 giây. Cuộn tới bảng "Thang chấm", rê chuột dọc hàng "Khay nằm trên bàn B" (43, 50, 44, 51, 49) khi nói câu về 50 và 43. |
| Lời nói | Bước bốn: thi và chấm bảy bước. Mỗi bản thi 60 lượt: hai mức khó, mỗi mức 30 vị trí khay. Thành công nghĩa là lệch không quá 5 cm và xoay không quá 10 độ. Bộ chấm chia mỗi lượt thành bảy bước, từ tới bàn A đến buông tay. Với bản tốt nhất, robot mang khay tới bàn B khá đều, rồi tụt mạnh ở bước đặt. Ở cả bốn bản đầu, 78 đến 87 phần trăm lượt hỏng mang nhãn đặt lệch hoặc khay nghiêng. Bản tốt nhất đạt 10 trên 60 lượt, và đó là bản dùng ít hơn 30 phần trăm bài mẫu. Với bản này, khay nằm trên bàn B ở 50 trên 60 lượt; với bản dùng đủ bài mẫu là 43 trên 60 lượt. Số sơ bộ, mô phỏng, mỗi bản dạy một lần. |
| Mục của BTC | OUTPUT (bảng điểm 7 bước); quá trình xử lý bước 4 |
| Số từ | 157 |

### Cảnh 7 · Bước 5 · Kiểm hệ thống, chẩn đoán

| Trường | Nội dung |
|---|---|
| Thời gian | 6:35–7:22 (47 giây) |
| Màn hình | `#/home?s=5`, rồi `#/diagnose`. Phải thấy ba ô số 4/8 · 4/8 · 0 CU, bảng "Kiểm hệ thống trước khi mua dữ liệu" bốn dòng, và 8 thẻ nhóm lượt hỏng chia hai cột: sang thu dữ liệu, thành phiếu sửa hệ thống. |
| Lời nói | Bước năm: kiểm hệ thống và chẩn đoán. Robot hỏng có thể vì model còn yếu. Nhưng cũng có thể bộ chấm sai, hoặc hệ thống thiếu một tín hiệu đo. Thu thêm dữ liệu cho lỗi của hệ thống thì mất tiền mà robot không tốt lên. Các lượt hỏng được gom thành 8 cụm. 4 cụm được đọc là model còn yếu và đi tiếp sang bước thu dữ liệu. 4 cụm còn lại là lỗi của hệ thống, nên thành phiếu sửa, không tiêu ngân sách dữ liệu. Bước kiểm này tốn 0 CU. |
| Mục của BTC | Quá trình xử lý bước 5; RESOURCE (0 CU) |
| Số từ | 98 |

### Cảnh 8 · Bước 6 · Lỗi → Dữ liệu

| Trường | Nội dung |
|---|---|
| Thời gian | 7:22–8:07 (45 giây) |
| Màn hình | `#/home?s=6`, rồi `#/loop`. Phải thấy chuỗi lọc 23 → 290 → 262 → 261 → 204 → 181 có chú thích "chưa phải kết quả của robot", và ngay cạnh đó ô "Kết quả của robot khi thi lại: 10/60 → 4/60". Chưa cuộn xuống bảng 23/37 ở cảnh này. |
| Lời nói | Bước sáu: lỗi thành dữ liệu. Bốn cụm đi tiếp chứa 23 lượt hỏng. Quanh đúng các tình huống đó, máy sinh 290 lượt làm mẫu. 262 lượt ghi được. 261 lượt qua kiểm định. 204 lượt qua bộ lọc chất lượng. Hệ thống chọn 181 bài mẫu theo luật viết trước khi sinh. Đây là chuỗi lọc dữ liệu, chưa phải kết quả của robot. Kết quả nằm ở lần thi lại. |
| Mục của BTC | OUTPUT (khuyến nghị thu dữ liệu); quá trình xử lý bước 6 |
| Số từ | 93 |

### Cảnh 9 · Theo chân một lỗi: mức 1, seed 1000107

| Trường | Nội dung |
|---|---|
| Thời gian | 8:07–9:27 (80 giây) |
| Màn hình | `#/follow?s=1` → `?s=2` → `?s=3` → `?s=4` → `?s=5`, bấm "Tiếp" đúng lúc lời nói đổi màn. Màn 1: hình ô đích, vòng 5 cm, vòng 7,0 cm, cung 16,3°. Màn 3: bấm phát 1 trong 6 video bài mẫu, để chạy khoảng 5 giây. Màn 4: bảng cả năm bản trên cùng lượt. Màn 5: 4/60 so với 10/60, bảng 23/37 có đối chứng. |
| Lời nói | Đây là một lượt thi thật: mức một, seed 1000107, tức một vị trí khay cố định. Màn một. Bản tốt nhất mang khay tới bàn B, nhưng đặt lệch 7,0 cm và xoay 16,3 độ. Mức cho phép là 5 cm và 10 độ, nên lượt này hỏng ở bước đặt. Màn hai. Lượt này thuộc cụm một, chẩn đoán là kỹ năng còn yếu. Màn ba. Máy sinh 6 bài mẫu quanh đúng tình huống này. Màn bốn. Thi lại đúng lượt đó. Bản sau vòng một đạt. Nhưng một bản không nhận dữ liệu này cũng đạt. Đạt một lần chưa chứng minh được gì. Màn năm. Trên cả 60 lượt, bản sau vòng một đạt 4 trên 60 lượt; bản trước đó đạt 10 trên 60 lượt. Trên 23 tình huống đã nhắm, bản mới đạt 2, các bản đối chứng đạt từ 1 đến 3. |
| Mục của BTC | Quá trình xử lý trọn một vòng, trên một lượt thật |
| Số từ | 169 |

### Cảnh 10 · Sổ chi phí, và số cập nhật sau khi nộp slide

| Trường | Nội dung |
|---|---|
| Thời gian | 9:27–10:57 (90 giây) |
| Màn hình | `#/loop?tab=cost` (bấm ô `$` ở giữa vòng cũng được). Phải thấy "13 việc có sổ chi phí", bảng "Chi phí vòng 1" bằng USD với CU trong ngoặc: dạy lần 1 8,55 CU, dạy lần 2 77,27 CU, chạy model khi thi khoảng 23,4 CU, cả vòng khoảng 10,9 USD. Rê chuột lên dòng 8,55 CU. Khi nói tới ba số cập nhật, chuyển sang `#/base` và cuộn tới ô "Số cập nhật sau khi nộp slide". |
| Lời nói | Ở giữa vòng là sổ chi phí, giống kế toán chi phí. Mỗi việc có một dòng ước tính trước khi chạy và một dòng thực đo sau khi chạy. Vòng một đo được: dạy model 8,55 CU cho lần đầu bị dừng sớm, 77,27 CU cho lần chạy lại, và chạy model để thi khoảng 23,4 CU. Tổng khoảng 109 CU, tức khoảng 10,9 USD. Đội cũng cập nhật ba số sau khi nộp slide. Slide ghi 2 441 bài mẫu tự sinh; số đó đếm trùng. Số không trùng là 1 032 bài loại một; tính cả loại hai là 2 000. Slide ghi một vòng chưa tới 10 USD; số đo là khoảng 10,9 USD. Slide ghi đặt khay đúng chỗ tăng 28 lần; số này chưa có nguồn, nên bỏ. Chính sổ chi phí và chỉ mục số liệu đã bắt được các lỗi này. |
| Mục của BTC | RESOURCE (thực đo); DATA (sửa số đếm) |
| Số từ | 190 |

### Cảnh 11 · Bảng nền: đã chứng minh, chưa chứng minh, việc tiếp theo

| Trường | Nội dung |
|---|---|
| Thời gian | 10:57–12:38 (101 giây) |
| Màn hình | `#/base`. Cuộn từ cột "Đã chứng minh" sang "Chưa chứng minh" rồi "Việc tiếp theo" theo lời nói. Phải thấy: 10/60 so với 5/60; 4/60 với số lượt trượt sát nút 4 → 11 (lệch 5–7,5 cm), nghiêng ở bước đặt 4 → 8; nhãn "đề xuất" trên mỗi việc tiếp theo; dòng "sơ bộ, mô phỏng, mỗi bản dạy một lần". |
| Lời nói | Đây là bảng nền của dự án. Đã chứng minh: hệ thống đo và kiểm định chạy trọn một vòng, chỉ ra robot hỏng ở bước đặt khay, chặn dữ liệu lỗi trước khi dạy, và ghi chi phí từng việc. Chưa chứng minh: vòng sửa lỗi đầu tiên chưa làm robot tốt lên, từ 10 trên 60 lượt xuống 4 trên 60 lượt. Số đo cho thấy hai thay đổi cùng lúc. Nhiều lượt trượt sát nút hơn: 11 lượt lệch trong khoảng 5 đến 7,5 cm, trước đó là 4 lượt. Và số lượt khay nghiêng ở bước đặt tăng gấp đôi, từ 4 lên 8. Đây là mô tả, chưa phải nguyên nhân đã kiểm. Luật đọc kết quả được viết và khóa trước khi thi. Theo luật đó, vòng này không khác việc thêm đều 181 bài mẫu, nên luật nói dừng. Đây là Jidoka: kết quả chưa đạt thì dừng chuyền, không đổ thêm dữ liệu. Việc tiếp theo đều là đề xuất: dạy lại mỗi bản thêm một lần để đo độ nhiễu; sửa bộ chấm và tín hiệu còn thiếu theo hai phiếu đã mở; và ở vòng hai, nhắm vào lỗi khay nghiêng ở bước đặt. |
| Mục của BTC | Kết quả (tốt và chưa tốt); quá trình xử lý (đọc kết quả) |
| Số từ | 215 |

### Cảnh 12 · Mở rộng và kết

| Trường | Nội dung |
|---|---|
| Thời gian | 12:38–13:43 (65 giây) |
| Màn hình | `#/base`, cuộn xuống phần lộ trình (3 mốc: 17/11 PoC · 3 tháng · sau đó). Phải thấy nhãn "mục tiêu" trên ≥ 50 % và ≥ 75 %. 10 giây cuối quay về `#/home`, giữ vòng tròn trên màn hình tới hết câu cảm ơn. |
| Lời nói | Vì sao cách làm này dùng lại được? Lõi hệ thống không gắn với một model, robot hay trình mô phỏng nào; nó nối qua sáu giao diện chuẩn. Dữ liệu do máy sinh, nên chi phí tăng theo giờ máy, không theo giờ người. Mọi việc có dòng trong sổ chi phí, nên kỹ năng mới có dự toán trước khi làm. Lộ trình đề xuất: trong ba tháng, dạy một kỹ năng của DENSO từ video DENSO quay, mục tiêu 50 phần trăm rồi 75 phần trăm lượt thành công. Đó là mục tiêu, chưa phải kết quả. Sau đó là nhiều kỹ năng hơn và robot thật của DENSO, cùng một quy trình. Robot hỏng ở đâu, thu dữ liệu đúng chỗ đó. Cảm ơn quý vị đã theo dõi. |
| Mục của BTC | Hướng phát triển; ý tưởng (nhắc lại) |
| Số từ | 136 |

## 5. Nguồn của từng số trong lời nói

Mọi số dưới đây đã kiểm trong repo hoặc trong chỉ mục `fwdata/console/index/` ngày 15/11/2026. Không thêm số nào vào lời nói mà không thêm dòng ở đây.

| Số | Cảnh | Nguồn |
|---|---|---|
| 10/60, 5/60, 6/60, 7/60, 4/60 lượt thành công (lệch ≤ 5 cm, xoay ≤ 10°) | 9, 11 (6: 10/60) | `story.json · pair`; [tray.md](../he/tray.md) mục 20.18 (b), bảng mức 1–2 gộp |
| 60 lượt = 2 mức × 30 vị trí khay | 6, 9 | `story.json · pair`; tray.md 20.18 (b), "n = 30 mỗi mức" |
| 5 cm, 10 độ | 6, 9 | `story.json · follow.tol` (0,05 m; 10,0°) |
| 78 đến 87 phần trăm lượt hỏng là đặt lệch hoặc nghiêng | 6 | (`L-PLACE-POSE` + `L-TRAY-TILT`) / lượt hỏng của bốn bản đầu, từ `story.pair.runs[].failures`: 80, 84, 78, 87 % |
| 2 572 tập; 379 video người; 193 teleop; 2 000 mô phỏng | 3 | `catalog.json · totals` (egocentric 379, teleop 193, s1 1 032 + s2 968, all 2 572) |
| 0 tập teleop của việc bê khay; teleop là dữ liệu của tác giả cho việc khác | 3 | Brief của lead mục 5 (99 tập hai bàn, 94 tập ôm hộp) |
| 606 = 301 + 124 + 181 bài mẫu | 3 | Brief mục 5; tray.md 20.16 (bản cắt `C70_R1` = S70 425 tập + 181 tập nhắm lỗi) |
| 317 qua, 54 bị loại, 8 loại từ trước (trên 379 clip) | 4 | `story.json · h1m.decisions` |
| 30/30 lỗi cấy, 0/40 báo nhầm (lớp mã) | 4 | [defect-bench.md](../g0/defect-bench.md) dòng "Lớp code, báo nhầm trên bản sạch \| 0/40 job"; [agent-qa.md](../g0/agent-qa.md) mục 3.2 |
| 5 bản đã dạy | 5 | `story.json · pair.runs` (5 bản) |
| 8 cụm, 4 sang dữ liệu, 4 thành phiếu, 0 CU | 7 | `story.json · round.clusters`; tray.md 20.3 (tiêu đề ghi "0 CU"), 20.11 |
| 23 → 290 → 262 → 261 → 204 → 181 | 2 (181), 8 | `story.json · round.chain`; tray.md 20.16 |
| seed 1000107; lệch 7,0 cm, xoay 16,3 độ | 9 | `story.json · follow.runs.C_70` (0,0704 m; 16,32°) |
| 6 bài mẫu sinh quanh lượt này | 9 | [design 0.2](../superpowers/specs/2026-11-15-console-one-site-design.md) mục 6.7: tập 449, 450, 481, 511, 541, 571 trong `episodes.jsonl` của `C70_R1.tar` |
| 23 tình huống: bản mới 2, đối chứng 1 đến 3; 37 tình huống còn lại: 10 xuống 2 | 9 | `story.json · follow.r3`; tray.md 20.18 (r3) |
| 77,27 CU (dạy lần 2); 8,55 CU (dạy lần 1, dừng sớm) | 2, 10 | tray.md 20.17, 20.18 "Watcher đo 77,27 CU" và bảng "Chi phí của 7.6–7.7" |
| khoảng 23,4 CU chạy model; khoảng 8 CU là phí | 10 | tray.md bảng "Chi phí của 7.6–7.7" ("Tổng serve khoảng 23,4"; "Khoảng 8 CU serve là phí") |
| khoảng 109 CU, khoảng 10,9 USD | 10 | Tính: 8,55 + 77,27 + 23,4 = 109,2 CU; × 0,1 USD |
| 0,1 USD một CU (giả định) | 2 | Deck slide 15, ghi là giả định |
| 1,8 giờ máy cho 181 bài mẫu | 2 | tray.md 20.16: sinh 1,16 giờ + QA 0,67 giờ trên `rtx3060`, 0 CU. "0 giờ người" của deck không có nguồn nên không nói |
| bớt 30 phần trăm, 606 → 425; 10/60 so với 5/60 | 11 | `story.json · pair` (`C_70`, `C_ALL`); tray.md 20.1 "(g) `C_70` − `C_ALL` +8,3 điểm %, CI 95 % −1,7 đến +18,3" |
| trượt sát nút 4 → 11 lượt (đạt ở dung sai 7,5 cm nhưng trượt ở 5 cm: 14 − 10 và 15 − 4); nghiêng ở bước đặt 4 → 8 | 11 | `place-error-C_70.json`, `place-error-C70_R1.json` · `relaxed_curve`; tray.md 20.18 bảng "`L-TRAY-TILT` theo bước hỏng đầu tiên". Không dùng cặp 16,1 → 12,7 cm của tray.md: số lệch lớn nhất thật ở từng lượt là 22,1 và 20,4 cm |
| khay nằm trên bàn B: 50/60 (425 bài) so với 43/60 (606 bài) | 6 | tray.md 20.18 bảng "Khay trên bàn B ở cuối lượt (chỉ số phụ)" |
| vòng này không khác thêm đều 181 bài mẫu; luật nói dừng | 11 | tray.md 20.7 (luật viết trước, khóa bằng `rules_sha256`), 20.18 "không cho thấy khác", "theo F, vòng dừng ở giai đoạn 1" |
| hai phiếu đã mở | 11 | `story.json · round.clusters` (DA-37, DA-38) |
| 6 giao diện chuẩn | 12 | Deck slide 16; [03 Kiến trúc](../product/03-architecture.md) mục 5.2 (6 Protocol) |
| mục tiêu 50 % rồi 75 % trong 3 tháng | 12 | Deck slide 16, ghi là mục tiêu |
| 2 441 bài, chưa tới 10 USD, tăng 28 lần (số của slide, nhắc để sửa) | 10 | Deck slide 2, 3, 8, 15, 16; sửa theo brief mục 5 |

Số không dùng vì chưa tìm thấy nguồn trong repo: "thi 60 lượt khoảng 9 CU" và "dạy 1 lần khoảng 76 CU" (deck slide 9, 15, 16; kịch bản dùng số đo 77,27 CU và 23,4 CU thay), "922 bước con có nhãn" (deck slide 11; chưa thấy trong chỉ mục), "×28" (deck slide 8).

## 6. Danh sách kiểm trước khi quay

**Máy và trình duyệt**

- [ ] Quay ở 1920×1080, trình duyệt toàn màn hình (F11), zoom 125 % (tương đương khung 1536×864: chữ đủ lớn, trang Thiết kế vẫn vừa một màn). Ẩn thanh dấu trang, tắt thông báo hệ điều hành, đóng mọi tab khác.
- [ ] Server chạy `--lock`. Ngôn ngữ VI. Nền sáng.
- [ ] Tải lại cứng (Ctrl+Shift+R) trước khi quay. Nếu menu trái chưa có "Thiết kế" và "Bảng nền" thì trình duyệt còn giữ bản cũ: mở `http://localhost:4190/?v=1#/home`.
- [ ] Mở sẵn theo thứ tự, mỗi trang tải xong một lần để video và ảnh đã vào bộ đệm: `#/home`, `#/design`, `#/home?s=1`…`?s=6`, `#/data`, `#/sim`, `#/jobs?view=pipeline`, `#/runs`, `#/eval`, `#/diagnose`, `#/loop`, `#/follow?s=1`…`?s=5`, `#/loop?tab=cost`, `#/base`.
- [ ] Thử phát 1 video bài mẫu ở màn 3 của `#/follow` và 2 ảnh ở `#/sim` khi đang khóa.
- [ ] Thu âm riêng hoặc micro ngoài; đọc thử cảnh 2 và cảnh 11 (hai cảnh dài nhất) để kiểm tốc độ ≈ 130 từ một phút.

**Không được lộ trên màn hình**

- [ ] Terminal, đường dẫn máy, tên tài khoản Colab, token, email, thư mục `vault/`.
- [ ] Khung chat (phải đóng), pill vận hành (3060, nemotron, jobs, "chờ duyệt"), danh sách ATTENTION màu đỏ, nút "Re-run 🔒".
- [ ] Mã nội bộ trên mặt trang story (`C70_R1`, `rp_…`, sha256); chỉ được có trong tooltip hoặc "Chi tiết kỹ thuật", và không mở phần đó khi quay.
- [ ] Ô tổng "ước tính 202,5 USD" đặt cạnh "thực đo 16,2 USD".
- [ ] Các số đã bỏ: 2 441, ×28 / 1 → 27, "chưa tới 10 USD".

**Đã kiểm trên site ngày 15/11/2026** (chế độ khóa, tiếng Việt, khung 1536×864)

| Route | Site hiện | Ghi chú khi quay |
|---|---|---|
| `#/home`, `#/home?s=1…6` | Dải "Vòng 1 chưa làm robot tốt hơn: 10/60 → 4/60", vòng 6 nút với sổ chi phí ở giữa, nút 3 xám, nút 6 xanh; bảng bước bên phải đổi theo `s` | `#/home?tour=1` tự chuyển bước 7 giây một lần, dùng được cho cảnh 1 |
| `#/design` | Năm ô có nhãn Việt · Anh quanh dải 6 bước; số có nhãn "đo" hoặc "ước tính"; dạy trên A100, chạy model khi thi trên L4 | Vừa một màn, không cuộn |
| `#/data` | Ba cột Video người 379 · Mô phỏng 2 000 · Teleop 193 (có dòng 0 tập teleop của việc bê khay); ô "Lần dạy gần nhất dùng gì" 606 = 301 + 124 + 181; ví dụ clip đạt và bị loại kèm lý do; 4 bài mẫu mỗi nhóm | Thẻ video người ghi 132 clip đội quay dùng cho hai bản có video người |
| `#/jobs?view=pipeline` | 30/30 · 0/40 · 317/379; lớp agent 30/30, 1/40 ghi ở dòng nhỏ | Kịch bản cũ ghi `#/qa`; đã sửa |
| `#/runs` | Lưới 5 bản với tên thường, chi phí đo từng lần dạy (một bản chưa có số đo) | |
| `#/eval` | 10/60, 78–87 %, thanh 7 bước, video lượt thành công (nguồn: slide 11), bảng thang chấm 6 hàng × 5 bản | Hàng "Khay nằm trên bàn B" có nhãn chỉ số phụ |
| `#/diagnose` | 4/8 · 4/8 · 0 CU, bảng kiểm bốn dòng, 8 thẻ nhóm lượt hỏng | |
| `#/loop` | Chuỗi lọc có chú thích, 10/60 → 4/60, "trượt sát nút 4 → 11", "nghiêng lúc đặt 4 → 8", bảng 23/37, luật dừng | |
| `#/loop?tab=cost` | 13 việc có sổ; bảng chi phí vòng 1; không có hai ô tổng đặt cạnh nhau | |
| `#/base` | Ba cột Đã chứng minh / Chưa chứng minh / Việc tiếp theo (đề xuất); lộ trình có nhãn "mục tiêu"; ô số cập nhật sau khi nộp slide | Cuộn xuống cho cảnh 12 |

Chưa kiểm ở lượt này: `#/follow?s=2…4` sau khi đổi màu, bản tiếng Anh của các trang bước, và việc phát 6 video ở màn 3 của `#/follow`. Thử các mục này trước khi quay.
