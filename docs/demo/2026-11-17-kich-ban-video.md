# Kịch bản quay video demo · Humanoid Data Flywheel (17/11/2026)

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 19/11/2026 | 0.8 | Bỏ khỏi dòng change log 0.2 cặp số của kết quả không trình bày (quyết định 16/11/2026); lệnh bật server dùng `$PWD/fwdata` thay cho đường dẫn máy; ghi chú rằng với model hosted, chat chỉ thấy dữ liệu `public` và không có tool đọc job, log, phát hiện QA, video người | Hiếu (soạn với Claude) |
| 17/11/2026 | 0.7 | Trợ lý ở cảnh 12 chạy bằng model Nemotron của NVIDIA qua dịch vụ OpenRouter (quyết định của Hiếu), không còn là model tự host. Sửa lời cảnh 12, bảng yêu cầu, bảng nguồn và danh sách kiểm (cách bật server, giới hạn lượt gọi mỗi ngày của gói miễn phí) | Hiếu (soạn với Claude) |
| 16/11/2026 | 0.6 | Theo quyết định của Hiếu ngày 16/11/2026: không trình bày kết quả thi lại của bản sau vòng 1. Bỏ mọi câu và số về kết quả đó (cảnh 1, 8, 9, 11, 12) và các dòng nguồn tương ứng; cảnh 9 còn ba màn; cảnh 11 nói vòng sửa lỗi là phần chưa chứng minh; cảnh 12 đổi câu hỏi cho trợ lý. Website nói "không trình bày", không nói "chưa chạy". Đếm lại thời lượng | Hiếu (soạn với Claude) |
| 16/11/2026 | 0.5 | Cả 13 cảnh quay trên một server: bản khóa chạy thêm cờ `--chat` (`fw console serve --lock --chat`) giữ chat và vẫn từ chối mọi việc ghi. Server tự nối và nạp model khi khởi động. Sửa cảnh 12 và danh sách kiểm; lời nói không đổi | Hiếu (soạn với Claude) |
| 16/11/2026 | 0.4 | Theo website mới: trang đầu là "Các task" (`#/tasks`), trang Tổng quan có dải sáu bước, thêm trang "Video người → dữ liệu" (`#/egoflow`). Cảnh 1 mở từ trang task; cảnh 3 thêm một câu về 21 khớp bàn tay; cảnh 9 và 10 rút gọn; thêm cảnh 12 "Hỏi trợ lý về kết quả" (chatbot Nemotron, quay ở bản không khóa); cảnh kết thành cảnh 13 và thêm câu về thêm task. Đếm lại thời lượng: 14:18. Đã mở lại cả 25 trang của kịch bản trên bản khóa, không trang nào lỗi | Hiếu (soạn với Claude) |
| 15/11/2026 | 0.3 | Site dựng lại theo quy trình: các trang kể chuyện nằm trong mục "Báo cáo vòng". Đổi đường dẫn: `#/home?s=N` thành `#/report?s=N`, `#/loop?tab=cost` thành `#/cost`, bước 2 là `#/qa`. Lời nói không đổi. Chưa quay thử lại từng cảnh trên site mới | Hiếu (soạn với Claude) |
| 15/11/2026 | 0.2 | Sửa sau khi site xong và sau lượt soát số: thêm "khay nằm trên bàn B 50/60 so với 43/60" (cảnh 6); thay một cặp số đo ở cảnh 11 (bản 0.6 bỏ cả hai cặp, nên không ghi lại ở đây); sửa câu về 2 441; bỏ "0 giờ người"; cột màn hình theo route thật; đếm lại thời lượng; bảng việc mở thành bảng đã kiểm | Hiếu (soạn với Claude) |
| 15/11/2026 | 0.1 | Bản đầu: 12 cảnh, lời nói đầy đủ, nguồn từng số, danh sách kiểm trước khi quay | Hiếu (soạn với Claude) |

Video quay màn hình website Flywheel Console, tối đa 15 phút. Cả 13 cảnh quay trên một server ở chế độ khóa có chat (`fw console serve --lock --chat`, cổng 4190): mọi việc ghi bị từ chối, chat vẫn trả lời vì nó chỉ đọc. Kịch bản bám cấu trúc site hiện tại (trang "Các task", Tổng quan, các trang Quy trình, mục "Báo cáo vòng") và bộ số đã kiểm. Script thuyết trình cho phiên dịch ở [file riêng](2026-11-17-script-thuyet-trinh.md).

## 1. Yêu cầu của ban tổ chức và chỗ trả lời

Yêu cầu nguyên văn: "Video tối đa 15 phút giải thích và demo sản phẩm. Cần nêu rõ được các vấn đề sau: INPUT - OUTPUT của quy trình, ENVIRONMENT và các DEVICES đi cùng, các yêu cầu về DATA, RESOURCE và quá trình xử lý của sản phẩm/dịch vụ."

| Mục | Cảnh chính | Cảnh nhắc lại |
|---|---|---|
| INPUT - OUTPUT | 2 (Thiết kế) | 6, 8 |
| ENVIRONMENT | 2 | 12 (model của trợ lý, gọi qua dịch vụ ngoài) |
| DEVICES | 2 | |
| DATA | 3 (Bước 1) | 4, 10 |
| RESOURCE | 2 | 5, 7, 10 |
| Quá trình xử lý | 3–8 (sáu bước), 9 (một lượt thật đi trọn vòng) | 1, 11, 12 |

## 2. Thông điệp và giọng

- Ba phần, theo đúng thứ tự: cái đã chạy tốt (hệ thống đo và kiểm định) → cái chưa chứng minh (vòng sửa lỗi đầu tiên đã đặt đơn 181 bài mẫu; kết quả thi lại của bản sau vòng không trình bày trong video) → việc tiếp theo và lộ trình. Bản hôm nay là nền cho các vòng sau.
- Không nói vòng sửa lỗi làm robot tốt lên, và không nói nó chưa chạy: chỉ nói kết quả thi lại không nằm trong bản trình bày này.
- Một ví dụ chạy suốt: lượt thi mức 1, seed 1000107 (cảnh 9), đi tới chỗ sinh bài mẫu quanh lượt đó.
- Từ nhà máy, dùng ít và đúng nghĩa: PDCA (vòng 6 bước, cảnh 2), kiểm tra đầu vào (Agent QA/QC, cảnh 4), kế toán chi phí (sổ chi phí, cảnh 10).
- Sản phẩm là nền chạy nhiều task: mở đầu bằng trang "Các task" (cảnh 1), kết bằng khối "Thêm task mới" (cảnh 13).
- Trợ lý (cảnh 12) được giới thiệu đúng mức: mã đọc và tính số, model nhỏ chỉ diễn đạt; câu trả lời là đề xuất.
- Không dùng từ quảng cáo. Mọi kết quả có mẫu số. Mỗi màn có kết quả nói một lần "sơ bộ, mô phỏng, mỗi bản dạy một lần" (cảnh 6; cảnh 1 nói chung cho cả video).
- Trên trang story chỉ dùng tên thường của bản dạy ("425 bài mẫu", "sau vòng 1"), không đọc mã nội bộ.

## 3. Cách tính thời lượng

- Tốc độ nói 130 từ một phút. "Từ" ở đây là âm tiết khi đọc to; số đọc thành chữ rồi mới đếm (ví dụ "2 572" là 7 âm tiết, "77,27" là 7). Đếm bằng script, không đếm tay.
- Thời lượng một cảnh = số từ × 60 / 130, làm tròn tới giây, cộng 2 giây chuyển màn.
- Tổng: **1751 từ**, lời nói **13:28**, cả video **13:55** (13 lần chuyển màn × 2 giây). Còn khoảng 1:05 dự phòng tới mốc 15:00. Số từ đếm bằng script (mỗi tiếng một từ, số đọc thành chữ).

| Cảnh | Tên | Bắt đầu | Kết thúc | Số từ | Lời nói (giây) |
|---|---|---|---|---|---|
| 1 | Mở đầu: một câu ý tưởng | 0:00 | 1:08 | 142 | 66 |
| 2 | Thiết kế: đầu vào, đầu ra, môi trường, thiết bị, tài nguyên | 1:08 | 2:54 | 225 | 104 |
| 3 | Bước 1 · Nạp, chuẩn hóa (yêu cầu về dữ liệu) | 2:54 | 4:14 | 168 | 78 |
| 4 | Bước 2 · Agent QA/QC | 4:14 | 5:04 | 104 | 48 |
| 5 | Bước 3 · Dạy Ψ₀ | 5:04 | 5:34 | 61 | 28 |
| 6 | Bước 4 · Thi, chấm 7 bước | 5:34 | 6:49 | 158 | 73 |
| 7 | Bước 5 · Kiểm hệ thống, chẩn đoán | 6:49 | 7:36 | 97 | 45 |
| 8 | Bước 6 · Lỗi → Dữ liệu | 7:36 | 8:24 | 100 | 46 |
| 9 | Theo chân một lỗi: mức 1, seed 1000107 | 8:24 | 9:18 | 112 | 52 |
| 10 | Sổ chi phí, và số cập nhật sau khi nộp slide | 9:18 | 10:22 | 135 | 62 |
| 11 | Bảng nền: đã chứng minh, chưa chứng minh, việc tiếp theo | 10:22 | 11:48 | 183 | 84 |
| 12 | Hỏi trợ lý về kết quả | 11:48 | 12:48 | 125 | 58 |
| 13 | Mở rộng và kết | 12:48 | 13:55 | 141 | 65 |
| | **Tổng** | 0:00 | 13:55 | **1751** | **809** |

## 4. Kịch bản từng cảnh

### Cảnh 1 · Mở đầu: một câu ý tưởng

| Trường | Nội dung |
|---|---|
| Thời gian | 0:00–1:08 (68 giây) |
| Màn hình | Mở ở `#/tasks` (trang đầu "Các task"): hai thẻ task có clip robot, bảng "Mọi task, sáu bước". Không bấm gì trong 4 giây đầu. Khi nói "video đi theo task bê khay", bấm thẻ "Bê khay" sang `#/home`: phải thấy clip lớn, số 10/60 và dải sáu bước có số (2.572 → 30/30 → 5 → 10/60 → 4/8 → 23 → 181). Khi nói "Ý tưởng nằm trong một câu", bấm "Xem trong báo cáo vòng" sang `#/report`: tiêu đề "Robot hỏng ở đâu, thu dữ liệu đúng chỗ đó", vòng 6 bước với sổ chi phí ở giữa. Cuối cảnh, rê chuột theo chiều kim đồng hồ qua 6 nút. |
| Lời nói | Xin chào quý vị. Chúng tôi là đội ilovephysicalintelligence, với sản phẩm Humanoid Data Flywheel. Đây là Flywheel Console. Mỗi kỹ năng của robot là một task, và mọi task đi qua cùng sáu bước. Hiện có hai task; video đi theo task bê khay. Ý tưởng nằm trong một câu: robot hỏng ở đâu, thu dữ liệu đúng chỗ đó. Thông thường, người ta thu thêm thật nhiều dữ liệu mà ít khi biết mỗi vòng tốn bao nhiêu. Đội làm khác. Robot thi trong nhà máy ảo. Hệ thống tìm đúng bước robot hỏng, kiểm lỗi hệ thống trước, rồi mới thu dữ liệu cho bước đó, và ghi chi phí của từng việc. Video có ba phần: phần đã chạy tốt, phần chưa chứng minh, và các bước tiếp theo. Mọi số là sơ bộ, đo trong mô phỏng. |
| Mục của BTC | Ý tưởng; quá trình xử lý (tóm tắt một câu) |
| Số từ | 142 |

### Cảnh 2 · Thiết kế: đầu vào, đầu ra, môi trường, thiết bị, tài nguyên

| Trường | Nội dung |
|---|---|
| Thời gian | 1:08–2:54 (106 giây) |
| Màn hình | `#/design`. Rê chuột lần lượt qua 5 khối theo thứ tự lời nói: Đầu vào, Đầu ra, Môi trường, Thiết bị, Tài nguyên. Phải thấy cả 5 nhãn tiếng Anh INPUT, OUTPUT, ENVIRONMENT, DEVICES, RESOURCE cạnh nhãn tiếng Việt, và hàng 6 bước ở giữa. |
| Lời nói | Trang Thiết kế trả lời năm yêu cầu của ban tổ chức. INPUT, tức đầu vào: mô tả kỹ năng và bố trí bàn A, bàn B; bài mẫu robot do máy sinh trong mô phỏng; video người; và teleop, tức người điều khiển robot từ xa để làm mẫu. OUTPUT, tức đầu ra: model đã dạy; bảng điểm bảy bước cho biết robot hỏng ở bước nào; khuyến nghị thu dữ liệu gì, bao nhiêu, tốn bao nhiêu; và báo cáo so sánh các cách dạy. ENVIRONMENT, tức môi trường: robot Unitree G1, model Ψ₀, trình mô phỏng SIMPLE chạy vật lý MuJoCo, còn Isaac Sim chỉ để dựng hình. DEVICES, tức thiết bị: laptop chạy Flywheel Console; máy RTX 3060 để sinh dữ liệu và chạy lượt thi; GPU đám mây Colab để dạy và chạy model; điện thoại đeo đầu để quay video người. RESOURCE, tức tài nguyên, tính bằng CU, đơn vị GPU của Colab, giả định 0,1 USD một CU. Một lần dạy model ở vòng vừa rồi đo được 77,27 CU. Sinh và kiểm 181 bài mẫu mới mất khoảng 1,8 giờ máy. Quá trình xử lý là sáu bước trên vòng tròn, một vòng PDCA cho việc dạy robot. |
| Mục của BTC | INPUT, OUTPUT, ENVIRONMENT, DEVICES, RESOURCE, quá trình xử lý (giới thiệu) |
| Số từ | 225 |

### Cảnh 3 · Bước 1 · Nạp, chuẩn hóa (yêu cầu về dữ liệu)

| Trường | Nội dung |
|---|---|
| Thời gian | 2:54–4:14 (80 giây) |
| Màn hình | `#/report?s=1` (2 giây: bảng bước 1 bên phải, số 2 572 trên nút), rồi bấm "Xem chi tiết bước 1" sang `#/data`. Phải thấy ba thẻ nguồn: video người 379, teleop 193 với dòng "dữ liệu của tác giả, việc khác, 0 tập của việc bê khay", mô phỏng 2 000 (S1 1 032 + S2 968), và ô thành phần lần dạy gần nhất (301 + 124 + 181). Khi nói câu về 21 khớp bàn tay, mở `#/egoflow` (mục "Video người → dữ liệu" ở menu trái): dải bảy bước và trình xem một episode có khung xương bàn tay, để chạy 5 giây. Cuối cảnh mở `#/sim`, rê chuột qua 2 ảnh bài mẫu. |
| Lời nói | Bước một: nạp và chuẩn hóa ba loại dữ liệu về chuẩn LeRobot. Kho có 2 572 tập không trùng. Video người có 379 clip, gồm video đội tự quay và mẫu EgoDex đã công bố. Video người rẻ vì quay bằng điện thoại. Mỗi clip được dò 21 khớp mỗi bàn tay, cắt thành bước và gắn câu mô tả. Teleop có 193 tập, là dữ liệu công bố của nhóm tác giả cho một việc khác. Đội có 0 tập teleop của việc bê khay. Bài mẫu máy sinh trong mô phỏng có 2 000 tập, chỉ tốn giờ máy. Vì vậy hệ thống ưu tiên nguồn rẻ. Lần dạy gần nhất dùng 606 bài mẫu máy sinh: 301 bài phủ rộng, 124 bài nhắm lỗi từ vòng trước, và 181 bài nhắm lỗi của vòng này. |
| Mục của BTC | DATA; quá trình xử lý bước 1 |
| Số từ | 168 |

### Cảnh 4 · Bước 2 · Agent QA/QC

| Trường | Nội dung |
|---|---|
| Thời gian | 4:14–5:04 (50 giây) |
| Màn hình | `#/report?s=2` (nút bước 2 ghi 30/30), rồi bấm "Xem chi tiết bước 2" sang `#/qa`. Phải thấy ba ô số 30/30 · 0/40 · 317/379 và hai chuỗi lọc bên dưới. Rê chuột lên ô 30/30 một giây để hiện nguồn. Quay lại `#/data`, cuộn tới "Xem ví dụ thật", rê chuột lên một clip "bị loại" để thấy lý do. |
| Lời nói | Bước hai: Agent QA/QC, tức kiểm định viên tự động. Nó kiểm từng tập dữ liệu trước khi dạy, giống khâu kiểm tra đầu vào ở nhà máy. Với video người, 379 clip đi vào, 317 clip qua kiểm định, 54 clip bị loại, và 8 clip bị loại từ trước. Để thử kiểm định viên, đội cố ý cấy lỗi vào bản sao dữ liệu. Ở lớp kiểm tra bằng mã, nó bắt được 30 trên 30 lỗi cấy và báo nhầm 0 trên 40 lần trên dữ liệu sạch. |
| Mục của BTC | DATA (chất lượng); quá trình xử lý bước 2 |
| Số từ | 104 |

### Cảnh 5 · Bước 3 · Dạy Ψ₀

| Trường | Nội dung |
|---|---|
| Thời gian | 5:04–5:34 (30 giây) |
| Màn hình | `#/report?s=3`: nút bước 3 màu xám, nhãn "giữ nguyên". Rồi `#/runs`: lưới 5 bản đã dạy với tên thường và chi phí đo của từng lần dạy. Không mở "Chi tiết kỹ thuật". |
| Lời nói | Bước ba: dạy Ψ₀. Đây là bước duy nhất đội giữ nguyên, không thêm mô-đun. Model Ψ₀ là của nhóm tác giả và đã học trước từ video người. Đội dạy tiếp model trên một bộ dữ liệu đã đóng băng. Đến nay đội đã dạy năm bản để so sánh. Mỗi bản dạy một lần trên GPU đám mây. |
| Mục của BTC | RESOURCE (GPU); quá trình xử lý bước 3 |
| Số từ | 61 |

### Cảnh 6 · Bước 4 · Thi, chấm 7 bước

| Trường | Nội dung |
|---|---|
| Thời gian | 5:34–6:49 (75 giây) |
| Màn hình | `#/report?s=4`, rồi `#/eval`. Phải thấy số "10/60" màu trung tính, số "78–87 %", dòng "sơ bộ, mô phỏng, mỗi bản dạy một lần" và thanh 7 bước của bản 425 bài mẫu. Rê chuột từ "tới bàn A" xuống "đặt xuống". Bấm phát video "Một lượt thành công" khoảng 6 giây. Cuộn tới bảng "Thang chấm", rê chuột dọc hàng "Khay nằm trên bàn B" (43, 50, 44, 51) khi nói câu về 50 và 43. |
| Lời nói | Bước bốn: thi và chấm bảy bước. Mỗi bản thi 60 lượt: hai mức khó, mỗi mức 30 vị trí khay. Thành công nghĩa là lệch không quá 5 cm và xoay không quá 10 độ. Bộ chấm chia mỗi lượt thành bảy bước, từ tới bàn A đến buông tay. Với bản tốt nhất, robot mang khay tới bàn B khá đều, rồi tụt mạnh ở bước đặt. Ở cả bốn bản trình bày ở đây, 78 đến 87 phần trăm lượt hỏng mang nhãn đặt lệch hoặc khay nghiêng. Bản tốt nhất đạt 10 trên 60 lượt, và đó là bản dùng ít hơn 30 phần trăm bài mẫu. Với bản này, khay nằm trên bàn B ở 50 trên 60 lượt; với bản dùng đủ bài mẫu là 43 trên 60 lượt. Số sơ bộ, mô phỏng, mỗi bản dạy một lần. |
| Mục của BTC | OUTPUT (bảng điểm 7 bước); quá trình xử lý bước 4 |
| Số từ | 158 |

### Cảnh 7 · Bước 5 · Kiểm hệ thống, chẩn đoán

| Trường | Nội dung |
|---|---|
| Thời gian | 6:49–7:36 (47 giây) |
| Màn hình | `#/report?s=5`, rồi `#/diagnose`. Phải thấy ba ô số 4/8 · 4/8 · 0 CU, bảng "Kiểm hệ thống trước khi mua dữ liệu" bốn dòng, và 8 thẻ nhóm lượt hỏng chia hai cột: sang thu dữ liệu, thành phiếu sửa hệ thống. |
| Lời nói | Bước năm: kiểm hệ thống và chẩn đoán. Robot hỏng có thể vì model còn yếu. Nhưng cũng có thể bộ chấm sai, hoặc hệ thống thiếu một tín hiệu đo. Thu thêm dữ liệu cho lỗi của hệ thống thì mất tiền mà robot không tốt lên. Các lượt hỏng được gom thành 8 cụm. 4 cụm được đọc là model còn yếu và đi tiếp sang bước thu dữ liệu. 4 cụm còn lại là lỗi của hệ thống, nên thành phiếu sửa, không tiêu ngân sách dữ liệu. Bước kiểm này tốn 0 CU. |
| Mục của BTC | Quá trình xử lý bước 5; RESOURCE (0 CU) |
| Số từ | 97 |

### Cảnh 8 · Bước 6 · Lỗi → Dữ liệu

| Trường | Nội dung |
|---|---|
| Thời gian | 7:36–8:24 (48 giây) |
| Màn hình | `#/report?s=6`, rồi `#/loop`. Phải thấy chuỗi lọc 23 → 290 → 262 → 261 → 204 → 181 có chú thích "chưa phải kết quả của robot", và ô bên phải ghi "Kết quả thi lại của bản sau vòng không trình bày ở bản này". Không có số lượt đạt nào của bản sau vòng trên màn hình. |
| Lời nói | Bước sáu: lỗi thành dữ liệu. Bốn cụm đi tiếp chứa 23 lượt hỏng. Quanh đúng các tình huống đó, máy sinh 290 lượt làm mẫu. 262 lượt ghi được. 261 lượt qua kiểm định. 204 lượt qua bộ lọc chất lượng. Hệ thống chọn 181 bài mẫu theo luật viết trước khi sinh. Đây là chuỗi lọc dữ liệu, chưa phải kết quả của robot. Kết quả thi lại của bản sau vòng không trình bày trong video này. |
| Mục của BTC | OUTPUT (khuyến nghị thu dữ liệu); quá trình xử lý bước 6 |
| Số từ | 100 |

### Cảnh 9 · Theo chân một lỗi: mức 1, seed 1000107

| Trường | Nội dung |
|---|---|
| Thời gian | 8:24–9:18 (54 giây) |
| Màn hình | `#/follow?s=1` → `?s=2` → `?s=3`, bấm "Tiếp" đúng lúc lời nói đổi màn (trang chỉ còn ba màn). Màn 1: hình ô đích, vòng 5 cm, vòng 7,0 cm, cung 16,3°. Màn 2: cụm lỗi và chẩn đoán. Màn 3: bấm phát 1 trong 6 video bài mẫu, để chạy khoảng 5 giây; dưới video có dòng "không trình bày". |
| Lời nói | Đây là một lượt thi thật: mức một, seed 1000107. Bản tốt nhất mang khay tới bàn B, nhưng đặt lệch 7,0 cm và xoay 16,3 độ. Mức cho phép là 5 cm và 10 độ, nên lượt này hỏng ở bước đặt. Lượt này thuộc cụm một, chẩn đoán là kỹ năng còn yếu. Máy sinh 6 bài mẫu quanh đúng tình huống này, và chúng nằm trong 181 bài đưa vào lần dạy lại. Đây là cách một lượt hỏng trở thành dữ liệu: từ một lỗi cụ thể tới bài mẫu nhắm đúng lỗi đó. |
| Mục của BTC | Quá trình xử lý từ một lượt hỏng tới dữ liệu mới, trên một lượt thật |
| Số từ | 112 |

### Cảnh 10 · Sổ chi phí, và số cập nhật sau khi nộp slide

| Trường | Nội dung |
|---|---|
| Thời gian | 9:18–10:22 (64 giây) |
| Màn hình | `#/cost` (bấm ô `$` ở giữa vòng cũng được). Phải thấy "13 việc có sổ chi phí", bảng "Chi phí vòng 1" bằng USD với CU trong ngoặc: dạy lần 1 8,55 CU, dạy lần 2 77,27 CU, chạy model khi thi khoảng 23,4 CU, cả vòng khoảng 10,9 USD. Rê chuột lên dòng 8,55 CU. Khi nói tới ba số cập nhật, chuyển sang `#/base` và cuộn tới ô "Số cập nhật sau khi nộp slide". |
| Lời nói | Ở giữa vòng là sổ chi phí, giống kế toán chi phí. Mỗi việc có một dòng ước tính trước khi chạy và một dòng thực đo sau khi chạy. Vòng một đo được: dạy model 8,55 CU cho lần đầu bị dừng sớm, 77,27 CU cho lần chạy lại, và chạy model để thi khoảng 23,4 CU. Tổng khoảng 109 CU, tức khoảng 10,9 USD. Sau khi nộp slide, đội sửa ba số. Số bài mẫu tự sinh trên slide đếm trùng; số không trùng là 2 000. Chi phí một vòng là khoảng 10,9 USD, không phải dưới 10. Còn con số tăng 28 lần chưa có nguồn, nên bỏ. |
| Mục của BTC | RESOURCE (thực đo); DATA (sửa số đếm) |
| Số từ | 135 |

### Cảnh 11 · Bảng nền: đã chứng minh, chưa chứng minh, việc tiếp theo

| Trường | Nội dung |
|---|---|
| Thời gian | 10:22–11:48 (86 giây) |
| Màn hình | `#/base`. Cuộn từ cột "Đã chứng minh" sang "Chưa chứng minh" rồi "Việc tiếp theo" theo lời nói. Phải thấy: 10/60 so với 5/60; ô "Vòng sửa lỗi có làm robot tốt lên không" với dòng "không trình bày"; nhãn "đề xuất" trên mỗi việc tiếp theo; dòng "sơ bộ, mô phỏng, mỗi bản dạy một lần". |
| Lời nói | Đây là bảng nền của dự án. Đã chứng minh: hệ thống đo và kiểm định chạy trọn một vòng, chỉ ra robot hỏng ở bước đặt khay, chặn dữ liệu lỗi trước khi dạy, và ghi chi phí từng việc. Bớt 30 phần trăm bài mẫu, robot không kém đi: 10 trên 60 lượt so với 5 trên 60 lượt. Chưa chứng minh: vòng sửa lỗi có làm robot tốt lên hay không. Kết quả thi lại của bản sau vòng không trình bày trong video này. Ngoài ra, mỗi bản mới dạy một lần, nên chưa đo được độ nhiễu giữa hai lần dạy; và bộ chấm còn lỗi ngưỡng. Luật đọc kết quả được viết và khóa trước khi thi, để không ai đổi cách đọc sau khi thấy số. Việc tiếp theo đều là đề xuất: dạy lại mỗi bản thêm một lần để đo độ nhiễu; sửa bộ chấm và tín hiệu còn thiếu theo hai phiếu đã mở; và ở vòng hai, nhắm vào lỗi khay nghiêng và độ chính xác ở bước đặt. |
| Mục của BTC | Kết quả (đã chứng minh và chưa chứng minh); việc tiếp theo |
| Số từ | 183 |

### Cảnh 12 · Hỏi trợ lý về kết quả

| Trường | Nội dung |
|---|---|
| Thời gian | 11:48–12:48 (60 giây) |
| Màn hình | Quay trên cùng bản khóa có chat (xem mục 6). Mở `#/home` của task Bê khay, bấm nút "Chat" ở thanh trên. Phải thấy chấm xanh, dòng "nemotron-3.5-super-vl · openrouter warm" và năm câu hỏi gợi ý. Bấm "So sánh các bản model", chờ câu trả lời (khoảng 2 giây), giữ 4 giây. Bấm tiếp "Nên làm gì tiếp theo?", chờ câu trả lời. Không gõ tay, không mở "trace". Xong thì đóng khung chat. |
| Lời nói | Console có một trợ lý để hỏi về kết quả. Nó chạy bằng Nemotron, một model ngôn ngữ của NVIDIA, gọi qua dịch vụ OpenRouter; chỉ dữ liệu công khai của demo được gửi đi. Trợ lý không trả lời từ trí nhớ. Mã đọc số từ chỉ mục và tính sẵn các điểm đáng nói; model chỉ diễn đạt lại. Tôi hỏi so sánh các bản model. Trợ lý liệt kê kết quả thi của bốn bản và nói bản tốt nhất đạt 10 trên 60 lượt. Hỏi nên làm gì tiếp, nó đưa ra phương án kèm lý do: sửa hai phiếu lỗi hệ thống trước khi đặt đơn dữ liệu tiếp. Đó là đề xuất; người quyết định vẫn là đội. |
| Mục của BTC | Quá trình xử lý (đọc kết quả); ENVIRONMENT (model của trợ lý) |
| Số từ | 125 |

### Cảnh 13 · Mở rộng và kết

| Trường | Nội dung |
|---|---|
| Thời gian | 12:48–13:55 (67 giây) |
| Màn hình | Bắt đầu ở `#/tasks`: bảng "Mọi task, sáu bước" (task hai bàn có ô "chưa chạy") và khối "Thêm task mới" bốn bước, giữ tới hết câu về thêm task. Rồi `#/base`, cuộn xuống phần lộ trình (3 mốc: 17/11 PoC · 3 tháng · sau đó). Phải thấy nhãn "mục tiêu" trên ≥ 50 % và ≥ 75 %. 10 giây cuối quay về `#/report`, giữ vòng tròn trên màn hình tới hết câu cảm ơn. |
| Lời nói | Vì sao cách làm này dùng lại được? Lõi hệ thống không gắn với một model, robot hay trình mô phỏng nào; nó nối qua sáu giao diện chuẩn. Thêm một kỹ năng là thêm một task: một file mô tả, một bộ chấm, và dữ liệu mẫu, không sửa giao diện. Dữ liệu do máy sinh, nên chi phí tăng theo giờ máy, không theo giờ người. Lộ trình đề xuất: trong ba tháng, dạy một kỹ năng của DENSO từ video DENSO quay, mục tiêu 50 phần trăm rồi 75 phần trăm lượt thành công. Đó là mục tiêu, chưa phải kết quả. Sau đó là nhiều kỹ năng hơn và robot thật của DENSO, cùng một quy trình. Robot hỏng ở đâu, thu dữ liệu đúng chỗ đó. Cảm ơn quý vị đã theo dõi. |
| Mục của BTC | Hướng phát triển; ý tưởng (nhắc lại) |
| Số từ | 141 |

## 5. Nguồn của từng số trong lời nói

Mọi số dưới đây đã kiểm trong repo hoặc trong chỉ mục `fwdata/console/index/` ngày 15/11/2026. Không thêm số nào vào lời nói mà không thêm dòng ở đây.

| Số | Cảnh | Nguồn |
|---|---|---|
| 10/60, 5/60, 6/60, 7/60 lượt thành công (lệch ≤ 5 cm, xoay ≤ 10°) | 6, 11, 12 | `story.json · pair`; [tray.md](../he/tray.md) mục 20.18 (b), bảng mức 1–2 gộp |
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
| 23 → 290 → 262 → 261 → 204 → 181 | 2 (181), 8, 9 (181) | `story.json · round.chain`; tray.md 20.16 |
| seed 1000107; lệch 7,0 cm, xoay 16,3 độ | 9 | `story.json · follow.runs.C_70` (0,0704 m; 16,32°) |
| 6 bài mẫu sinh quanh lượt này | 9 | [design 0.2](../superpowers/specs/2026-11-15-console-one-site-design.md) mục 6.7: tập 449, 450, 481, 511, 541, 571 trong `episodes.jsonl` của `C70_R1.tar` |
| 77,27 CU (dạy lần 2); 8,55 CU (dạy lần 1, dừng sớm) | 2, 10 | tray.md 20.17, 20.18 "Watcher đo 77,27 CU" và bảng "Chi phí của 7.6–7.7" |
| khoảng 23,4 CU chạy model; khoảng 8 CU là phí | 10 | tray.md bảng "Chi phí của 7.6–7.7" ("Tổng serve khoảng 23,4"; "Khoảng 8 CU serve là phí") |
| khoảng 109 CU, khoảng 10,9 USD | 10 | Tính: 8,55 + 77,27 + 23,4 = 109,2 CU; × 0,1 USD |
| 0,1 USD một CU (giả định) | 2 | Deck slide 15, ghi là giả định |
| 1,8 giờ máy cho 181 bài mẫu | 2 | tray.md 20.16: sinh 1,16 giờ + QA 0,67 giờ trên `rtx3060`, 0 CU. "0 giờ người" của deck không có nguồn nên không nói |
| bớt 30 phần trăm, 606 → 425; 10/60 so với 5/60 | 6, 11 | `story.json · pair` (`C_70`, `C_ALL`); tray.md 20.1 "(g) `C_70` − `C_ALL` +8,3 điểm %, CI 95 % −1,7 đến +18,3" |
| khay nằm trên bàn B: 50/60 (425 bài) so với 43/60 (606 bài) | 6 | tray.md 20.18 bảng "Khay trên bàn B ở cuối lượt (chỉ số phụ)" |
| hai phiếu đã mở | 11, 12 | `story.json · round.clusters` (DA-37, DA-38) |
| 6 giao diện chuẩn | 13 | Deck slide 16; [03 Kiến trúc](../product/03-architecture.md) mục 5.2 (6 Protocol) |
| mục tiêu 50 % rồi 75 % trong 3 tháng | 13 | Deck slide 16, ghi là mục tiêu |
| hai task; mọi task đi qua sáu bước | 1 | `tasks.json` (chỉ mục console, dựng từ `seed/tasks.yaml`): `tray`, `two_table`; sáu bước là sáu trang Quy trình |
| 21 khớp mỗi bàn tay; cắt thành bước, gắn câu mô tả | 3 | [egocentric.yaml](../../configs/data/egocentric.yaml) mục `pose_ea` (MediaPipe Hands) và `segment`; [egocentric.md](../g0/egocentric.md) mục 4 và 5 |
| trợ lý chạy bằng Nemotron của NVIDIA qua OpenRouter; chỉ dữ liệu công khai được gửi đi | 12 | Biến môi trường `FW_CHAT_BASE_URL`, `FW_CHAT_MODEL` (`nvidia/nemotron-3.5-super-vl:free`) khi bật server; README của `packages/flywheel-console` mục Rules (các dòng không `public` bị ẩn khỏi công cụ khi dùng model bên ngoài); đã chạy thử 16 và 17/11/2026 |
| thêm task = file mô tả + bộ chấm + dữ liệu mẫu | 13 | `seed/tasks.yaml` của console; `configs/eval/scorer/`; trang `#/tasks` khối "Thêm task mới" |
| 2 441 bài, chưa tới 10 USD, tăng 28 lần (số của slide, nhắc để sửa) | 10 | Deck slide 2, 3, 8, 15, 16; sửa theo brief mục 5 |

Số không dùng vì chưa tìm thấy nguồn trong repo: "thi 60 lượt khoảng 9 CU" và "dạy 1 lần khoảng 76 CU" (deck slide 9, 15, 16; kịch bản dùng số đo 77,27 CU và 23,4 CU thay), "922 bước con có nhãn" (deck slide 11; chưa thấy trong chỉ mục), "×28" (deck slide 8).

## 6. Danh sách kiểm trước khi quay

**Máy và trình duyệt**

- [ ] Quay ở 1920×1080, trình duyệt toàn màn hình (F11), zoom 125 % (tương đương khung 1536×864: chữ đủ lớn, trang Thiết kế vẫn vừa một màn). Ẩn thanh dấu trang, tắt thông báo hệ điều hành, đóng mọi tab khác.
- [ ] Một server, bật bằng lệnh ở cuối mục này (nạp khóa từ `~/.config/fw-chat.env`, đặt model OpenRouter, rồi `fw console serve --lock --chat --port 4190`). Dòng khởi động phải ghi "(locked, chat on)". Ngôn ngữ VI. Nền sáng.
- [ ] Tải lại cứng (Ctrl+Shift+R) trước khi quay. Nếu menu trái chưa có mục "Tasks" trên cùng và mục "Video người → dữ liệu" thì trình duyệt còn giữ bản cũ: mở `http://localhost:4190/?v=200#/tasks`. Thẻ "Bê khay" phải có nhãn "đang chọn".
- [ ] Mở sẵn theo thứ tự, mỗi trang tải xong một lần để video và ảnh đã vào bộ đệm: `#/tasks`, `#/home`, `#/report`, `#/design`, `#/report?s=1`…`?s=6`, `#/data`, `#/egoflow`, `#/sim`, `#/qa`, `#/runs`, `#/eval`, `#/diagnose`, `#/loop`, `#/follow?s=1`…`?s=3`, `#/cost`, `#/base`.
- [ ] Thử phát 1 video bài mẫu ở màn 3 của `#/follow` và 2 ảnh ở `#/sim` khi đang khóa.
- [ ] Cảnh 12 (chatbot): trước khi quay, mở `#/home`, bấm "Chat" và kiểm đầu khung ghi "nemotron-3.5-super-vl · openrouter warm". Nếu ghi "nemotron warm" thì server đang dùng model tự host: tắt và bật lại bằng lệnh ở cuối mục này.
- [ ] Gói miễn phí của OpenRouter có giới hạn lượt gọi mỗi ngày (ngày 16/11 hết lượt sau khoảng 60–70 lượt, lỗi "free-models-per-day"). Trong ngày quay, không chạy bộ đo và chỉ bấm thử mỗi câu hỏi một lần. Nếu chat báo lỗi giới hạn: bật server không có ba biến `FW_CHAT_*` để dùng lại Nemotron tự host (cần máy `rtx3060`), và đọc cảnh 12 theo bản 0.6 của kịch bản. Bấm thử cả hai câu hỏi của cảnh một lượt, rồi bấm "new" để xóa trước khi quay. Mỗi câu trả lời mất 3–6 giây. Máy `rtx3060` phải bật và không ai đang nạp model khác trên đó.
- [ ] Câu trả lời của trợ lý có thể đổi vài chữ giữa các lần hỏi. Quay xong đọc lại câu trả lời trên màn hình: câu đầu phải liệt kê bốn bản và có "Bản tốt nhất là bản gốc C_70, đạt 10/60"; câu hai phải có "Đóng các phiếu DA-38, DA-37"; nếu không thì hỏi lại rồi quay lại cảnh.
- [ ] Thu âm riêng hoặc micro ngoài; đọc thử cảnh 2 và cảnh 11 (hai cảnh dài nhất) để kiểm tốc độ ≈ 130 từ một phút.

Lệnh bật server cho buổi quay (một dòng, chạy ở thư mục gốc của repo; khóa không hiện ra màn hình). Với model hosted, chat chỉ thấy dữ liệu `public` và không có các tool đọc job, log, phát hiện QA và dây chuyền video người (bản 0.8), nên cảnh 12 chỉ hỏi về kết quả vòng:

```bash
. ~/.config/fw-chat.env && FW_CHAT_BASE_URL=https://openrouter.ai/api/v1 FW_CHAT_MODEL=nvidia/nemotron-3.5-super-vl:free FW_CHAT_NAME=openrouter FW_ROOT="$PWD/fwdata" uv run fw console serve --lock --chat --port 4190
```

**Không được lộ trên màn hình**

- [ ] Terminal, đường dẫn máy, tên tài khoản Colab, token, email, thư mục `vault/`.
- [ ] Khung chat (mặc định đóng; chỉ mở ở cảnh 12 và không mở "trace"), danh sách ATTENTION màu đỏ, nút "Re-run 🔒". Thanh trên có pill 3060 và Chat: chấp nhận được, không rê chuột vào.
- [ ] Mã nội bộ trên mặt trang story (`C70_R1`, `rp_…`, sha256); chỉ được có trong tooltip hoặc "Chi tiết kỹ thuật", và không mở phần đó khi quay. Ngoại lệ đã biết: câu trả lời của trợ lý ở cảnh 12 ghi mã của bốn bản (C_ALL, C_70, B_ALL, B_70) và mã phiếu DA-37, DA-38; lời nói không đọc các mã này.
- [ ] Kết quả thi của bản sau vòng 1: không được có trên bất kỳ màn nào (số lượt đạt, bảng so sánh, tooltip). Đã quét 20 trang ngày 16/11/2026. Nếu hỏi trợ lý về bản đó, nó trả lời "không trình bày ở bản này".
- [ ] Ô tổng "ước tính 202,5 USD" đặt cạnh "thực đo 16,2 USD".
- [ ] Các số đã bỏ: 2 441, ×28 / 1 → 27, "chưa tới 10 USD".

**Đã kiểm trên site** (ngày 15/11/2026 ở chế độ khóa, tiếng Việt, khung 1536×864; ngày 16/11/2026 mở lại cả 25 trang trên bản khóa sau khi dựng lại, không trang nào báo lỗi; ba dòng đầu là trang mới)

| Route | Site hiện | Ghi chú khi quay |
|---|---|---|
| `#/tasks` | Hai thẻ task có clip (Bê khay 10/60, Gắp vật giữa hai bàn 6/10 của checkpoint tác giả), bảng "Mọi task, sáu bước", khối "Thêm task mới" bốn bước | Clip chạy khi rê chuột lên thẻ |
| `#/home` | Clip lớn, 10/60, dải sáu bước có số, bảng chi tiết từng bước | Clip của bê khay cắt từ slide 11 |
| `#/egoflow` | Bảy bước từ video thô tới episode có nhãn, bảng model (YuNet, MediaPipe Hands đang dùng; RoboBrain, Molmo2 mới thử), trình xem một episode có khung xương tay | Trình xem nền tối; cuộn xuống để thấy |
| Chat ở `#/home` | Năm câu hỏi gợi ý; với model OpenRouter trả lời sau 1–4 giây; hai câu của cảnh 12 đã thử trên bản khóa ngày 17/11/2026 | Cần cờ `--chat` khi server chạy `--lock`; có giới hạn lượt gọi mỗi ngày |
| `#/report`, `#/report?s=1…6` | Dải "Vòng 1 đã chọn 181 bài mẫu nhắm lỗi để dạy lại. Kết quả thi lại của bản sau vòng không trình bày ở bản này", vòng 6 nút với sổ chi phí ở giữa, nút 3 xám, nút 6 xanh; bảng bước bên phải đổi theo `s` | `#/report?tour=1` tự chuyển bước 7 giây một lần, dùng được cho cảnh 1 |
| `#/design` | Năm ô có nhãn Việt · Anh quanh dải 6 bước; số có nhãn "đo" hoặc "ước tính"; dạy trên A100, chạy model khi thi trên L4 | Vừa một màn, không cuộn |
| `#/data` | Ba cột Video người 379 · Mô phỏng 2 000 · Teleop 193 (có dòng 0 tập teleop của việc bê khay); ô "Lần dạy gần nhất dùng gì" 606 = 301 + 124 + 181; ví dụ clip đạt và bị loại kèm lý do; 4 bài mẫu mỗi nhóm | Thẻ video người ghi 132 clip đội quay dùng cho hai bản có video người |
| `#/qa` | 30/30 · 0/40 · 317/379; lớp agent 30/30, 1/40 ghi ở dòng nhỏ | Kịch bản cũ ghi `#/qa`; đã sửa |
| `#/runs` | Lưới 5 bản với tên thường, chi phí đo từng lần dạy (một bản chưa có số đo) | |
| `#/eval` | 10/60, 78–87 %, thanh 7 bước, video lượt thành công (nguồn: slide 11), bảng thang chấm 6 hàng × 4 bản | Hàng "Khay nằm trên bàn B" có nhãn chỉ số phụ |
| `#/diagnose` | 4/8 · 4/8 · 0 CU, bảng kiểm bốn dòng, 8 thẻ nhóm lượt hỏng | |
| `#/loop` | Chuỗi lọc 23 → 181 có chú thích; ô bên phải ghi kết quả thi lại không trình bày | Trang này không còn bảng 23/37 |
| `#/cost` | 13 việc có sổ; bảng chi phí vòng 1; không có hai ô tổng đặt cạnh nhau | |
| `#/base` | Ba cột Đã chứng minh / Chưa chứng minh / Việc tiếp theo (đề xuất); cột giữa mở đầu bằng "Vòng sửa lỗi có làm robot tốt lên không" và dòng "không trình bày"; lộ trình có nhãn "mục tiêu"; ô số cập nhật sau khi nộp slide | Cuộn xuống cho cảnh 13 |

Chưa kiểm ở lượt này: nội dung từng cảnh so với lời nói sau khi dựng lại (ngày 16/11 mới kiểm là trang mở được), bản tiếng Anh của các trang bước, và việc phát 6 video ở màn 3 của `#/follow`. Thử các mục này trước khi quay.
