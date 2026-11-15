# Script thuyết trình · Humanoid Data Flywheel (17/11/2026)

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 15/11/2026 | 0.1 | Bản đầu cho phiên dịch: lời nói theo 18 slide của deck đã nộp, phần trình diễn theo 12 cảnh của video, bảng thuật ngữ Việt · Anh | Hiếu (soạn với Claude) |

Yêu cầu của ban tổ chức: "Nội dung script bao gồm đầy đủ các ý chính dự kiến trình bày trong phần thuyết trình, nhằm hỗ trợ phiên dịch chuẩn bị bản dịch trước cho các đại biểu Nhật Bản."

## Ghi chú cho phiên dịch

- Thứ tự theo deck `DENSO-ilovephysicalintelligence-7.pptx` (18 slide). Tiêu đề mỗi mục là số slide và tiêu đề slide. Phần trình diễn trực tiếp nằm giữa slide 10 và slide 11, theo đúng 12 cảnh của [kịch bản video](2026-11-17-kich-ban-video.md).
- Câu ngắn, mỗi câu một ý, chủ ngữ rõ. Một thuật ngữ chỉ có một cách gọi; bảng thuật ngữ ở cuối file.
- Mọi kết quả là sơ bộ, đo trong mô phỏng, mỗi bản dạy được dạy một lần. Chưa có robot thật.
- Ở năm chỗ, deck có số sai hoặc chưa có nguồn. Script đọc số đúng và nói một câu "đã được cập nhật sau khi nộp slide". Danh sách ở mục "Số trong deck đã được cập nhật sau khi nộp".
- "Ψ₀" đọc là "Psi-zero". "CU" đọc là "xê-u", là đơn vị tính tiền GPU của Google Colab. "%" đọc là "phần trăm".
- Độ dài: **1344 từ** (âm tiết khi đọc, số đọc thành chữ), khoảng **10:20** ở 130 từ một phút. Phần slide 1074 từ (8:16), phần trình diễn 270 từ (2:05).

## Slide 1 · HUMANOID DATA FLYWHEEL

Xin chào quý vị. Chúng tôi là đội ilovephysicalintelligence. Sản phẩm của đội tên là Humanoid Data Flywheel, nghĩa là vòng quay dữ liệu cho robot hình người. Câu chính là: Robot hỏng ở đâu, thu dữ liệu đúng chỗ đó. Nghĩa là: robot hỏng ở bước nào, đội thu dữ liệu cho bước đó.

_Số từ: 55._

## Slide 2 · Giới thiệu team

Đội có năm thành viên. Dương Đình Hiếu là trưởng nhóm. Nguyễn Thăng Long phụ trách lõi hệ thống. Trần Trịnh Hoàng Châu phụ trách bộ chấm. Trần Ngọc Hưng phụ trách video người và kiểm định. Dương Tiến Thông phụ trách kế hoạch ở giai đoạn đầu. Slide ghi 2 441 bài mẫu tự sinh. Số này đã được cập nhật sau khi nộp slide: số bài mẫu không trùng là 1 032 bài loại một; tính cả loại hai là 2 000 bài.

_Ghi chú: Slide còn ghi 7 lần dạy, 820+ lượt thi và 153 đoạn video. Script không đọc ba số này vì người viết chưa kiểm được nguồn (xem mục cuối file)._

_Số từ: 80._

## Slide 3 · Checklist tự đánh giá trước khi nộp

Slide này tóm tắt sáu điểm. Điểm mới là tìm đúng bước robot hỏng và chỉ thu dữ liệu cho bước đó. Công cụ là robot Unitree G1 và model Ψ₀. Ψ₀, đọc là Psi-zero, là model do nhóm tác giả bài báo Ψ₀ công bố. Hiệu quả sơ bộ là bớt 30 phần trăm bài mẫu mà robot không kém đi.

_Số từ: 64._

## Slide 4 · Bối cảnh

Đề bài nêu bốn khó khăn. Với mỗi khó khăn, đội có một câu trả lời. Đội luyện robot trước trong mô phỏng. Đội tìm đúng bước robot hỏng và chỉ dạy thêm bước đó. Đội dùng một quy trình cho ba nguồn dữ liệu, có kiểm định tự động. Đội chọn nguồn dữ liệu rẻ nhất và ghi chi phí từng việc.

_Số từ: 63._

## Slide 5 · Vấn đề bạn nhìn thấy?

Dạy robot hình người hôm nay cần rất nhiều dữ liệu do người làm. Nguồn số của các công ty ghi ở chân slide. Đội đo lại trong mô phỏng. Robot G1 bê khay từ bàn A sang bàn B. Robot đưa khay tới bàn B trong 43 đến 51 trên 60 lượt thi. Robot đặt khay đúng chỗ, lệch không quá 5 cm, chỉ trong 5 đến 10 trên 60 lượt thi.

_Ghi chú: Số của Tesla, Physical Intelligence, BMW và Figure là số công bố bên ngoài, nguồn ở chân slide; script không đọc lại._

_Số từ: 81._

## Slide 6 · Thị trường & khoa học

Các nhóm nghiên cứu đã có từng phần riêng. Đội ghép các phần đó thành một quy trình có ghi chi phí. Điểm mới của đội là kiểm lỗi hệ thống trước, chọn dữ liệu theo chi phí thật, và đưa ra khuyến nghị thu dữ liệu có số lượng cụ thể.

_Ghi chú: Số thị trường là của Counterpoint Research, nguồn ở chân slide; script không đọc lại._

_Số từ: 52._

## Slide 7 · Vì sao DENSO chưa làm được?

Quy trình thường gặp là: hỏng thì đoán lỗi, rồi thu thêm dữ liệu đại trà. Không ai đo mỗi vòng tốn bao nhiêu. Slide ghi mỗi lần dạy và thi tốn khoảng 85 CU. CU là đơn vị tính tiền GPU của Google Colab. Số này đã được cập nhật sau khi nộp slide: ở vòng vừa rồi, một lần dạy và một lần thi đo được khoảng 101 CU.

_Số từ: 76._

## Slide 8 · Giải pháp đề xuất là gì?

Đội giữ nguyên quy trình và thêm năm mô-đun vào năm bước. Bước ba, dạy model, được giữ nguyên. Sổ chi phí áp cho mọi bước. Slide nêu ba kết quả. Thứ nhất, 78 đến 87 phần trăm lượt thi hỏng nằm ở bước đặt khay. Thứ hai, kiểm định viên tự động bắt 30 trên 30 lỗi cấy và báo nhầm 0 trên 40 lần. Thứ ba, slide ghi đặt khay đúng chỗ tăng 28 lần. Đội đã bỏ số này sau khi nộp slide, vì số này chưa có nguồn.

_Số từ: 101._

## Slide 9 · Thiết kế kỹ thuật

Slide này ghi đầu vào, sáu bước, đầu ra, môi trường, thiết bị và tài nguyên. Hai số tài nguyên đã được cập nhật sau khi nộp slide. Một lần dạy model đo được 77,27 CU. Một lần thi 60 lượt đo được khoảng 23,4 CU, kể cả phí do máy chạy không.

_Số từ: 64._

## Slide 10 · Demo

Từ đây người trình bày mở website Flywheel Console. Thứ tự cảnh giống video; lời nói rút gọn.

### Phần trình diễn trực tiếp trên Flywheel Console

| Cảnh | Trang | Lời nói | Số từ |
|---|---|---|---|
| 1 · Trang đầu | `#/home` | Đây là trang đầu của Flywheel Console. Vòng tròn có sáu bước, sổ chi phí ở giữa. Dải dưới tiêu đề ghi kết quả vòng một: từ 10 trên 60 lượt thi xuống 4 trên 60 lượt thi. | 41 |
| 2 · Thiết kế | `#/design` | Trang Thiết kế ghi đầu vào, đầu ra, môi trường, thiết bị và tài nguyên. Teleop là việc người điều khiển robot từ xa để làm mẫu. | 27 |
| 3 · Bước 1 · Nạp, chuẩn hóa | `#/home?s=1`, `#/data` | Kho có 2 572 tập dữ liệu không trùng. Đội có 0 tập teleop của việc bê khay. | 23 |
| 4 · Bước 2 · Agent QA/QC | `#/qa` | Kiểm định viên cho qua 317 trên 379 clip video người. | 18 |
| 5 · Bước 3 · Dạy Ψ₀ | `#/runs` | Bước dạy model được giữ nguyên. Đội có năm bản dạy. | 11 |
| 6 · Bước 4 · Thi, chấm 7 bước | `#/eval` | Bản dạy tốt nhất đạt 10 trên 60 lượt thi. Robot hỏng nhiều nhất ở bước đặt khay. | 20 |
| 7 · Bước 5 · Kiểm hệ thống, chẩn đoán | `#/diagnose` | Hệ thống gom lượt thi hỏng thành 8 cụm. 4 cụm sang thu dữ liệu. 4 cụm thành phiếu sửa hệ thống. | 22 |
| 8 · Bước 6 · Lỗi → Dữ liệu | `#/loop` | Hệ thống chọn 181 bài mẫu nhắm lỗi. | 12 |
| 9 · Theo chân một lỗi | `#/follow?s=1` → `?s=5` | Đây là một lượt thi thật. Sau vòng một, bản dạy mới đạt ở lượt thi này. Một bản dạy không nhận dữ liệu mới cũng đạt. Trên cả 60 lượt thi, bản dạy mới đạt 4 trên 60 lượt thi. | 43 |
| 10 · Sổ chi phí | `#/loop?tab=cost` | Vòng một tốn khoảng 109 CU, tức khoảng 10,9 USD. | 16 |
| 11 · Bảng nền | `#/base` | Vòng sửa lỗi đầu tiên chưa làm robot tốt lên. Số lượt thi khay nghiêng ở bước đặt tăng từ 4 lên 8. Luật viết trước cho dừng. | 28 |
| 12 · Mở rộng và kết | `#/base` (phần lộ trình) | Trang cuối ghi lộ trình, giống slide 16. | 9 |

## Slide 11 · Demo: người làm mẫu, robot làm lại

Slide này cho thấy một clip video người và một lượt thi thành công của robot. Video người do đội tự quay và đã che mặt. 317 trên 379 clip qua kiểm định.

_Ghi chú: Slide ghi 922 bước con có nhãn. Script không đọc số này vì chưa kiểm được trong chỉ mục._

_Số từ: 40._

## Slide 12 · Kết quả demo: 4 cách dạy

Đội có bốn bản dạy. Bản dạy dùng 606 bài mẫu đạt 5 trên 60 lượt thi. Bản dạy dùng 425 bài mẫu đạt 10 trên 60 lượt thi. Khoảng tin cậy của chênh lệch còn chứa 0, nên đội nói robot không kém đi, không nói robot tốt hơn. Thêm video người chưa thấy lợi. Slide này chưa có bản dạy thứ năm. Bản dạy thứ năm, sau vòng sửa lỗi đầu tiên, đạt 4 trên 60 lượt thi. Kết quả này có sau khi nộp slide.

_Số từ: 99._

## Slide 13 · Kết quả demo: robot hỏng ở đâu?

Ở cả bốn bản dạy, 78 đến 87 phần trăm lượt thi hỏng là đặt lệch hoặc khay nghiêng. Vì vậy đội sinh dữ liệu quanh bước đặt khay.

_Số từ: 33._

## Slide 14 · Kết quả demo: nới dần tiêu chí

Bảng này nới dần dung sai, tức mức lệch cho phép. Robot mang khay tới nơi khá tốt. Robot đặt khay đúng chỗ còn yếu.

_Số từ: 25._

## Slide 15 · Hiệu quả mang lại?

Bài mẫu giảm 30 phần trăm, từ 606 xuống 425 bài. Máy sinh 181 bài mẫu trong khoảng 1,8 giờ máy. Slide ghi một vòng sửa lỗi chưa tới 10 USD. Số này đã được cập nhật sau khi nộp slide: số đo là khoảng 10,9 USD.

_Số từ: 69._

## Slide 16 · Tầm nhìn & mục tiêu

Hôm nay hệ thống làm một kỹ năng trong mô phỏng. Kết quả tốt nhất là 10 trên 60 lượt thi. Cấp một của đề cần ít nhất 50 phần trăm lượt thi thành công. Quy trình mở rộng được vì bốn lý do. Lõi hệ thống không gắn với một model hay một robot. Dữ liệu do máy sinh. Kiểm định chạy tự động. Mỗi việc có một dòng trong sổ chi phí. Lộ trình là đề xuất. Trong ba tháng, đội dạy một kỹ năng của DENSO từ video DENSO, với mục tiêu 50 phần trăm rồi 75 phần trăm. Đây là mục tiêu, chưa phải kết quả.

_Số từ: 116._

## Slide 17 · Thời gian triển khai

Dự án chạy bốn tuần. Slide ghi mốc 17/11 là đọc kết quả vòng hai. Thực tế, đội đã đọc kết quả vòng một, và luật viết trước cho dừng. Vòng hai hiện là đề xuất.

_Số từ: 39._

## Slide 18 · Cảm ơn

Cảm ơn quý vị đã lắng nghe. Robot hỏng ở đâu, thu dữ liệu đúng chỗ đó.

_Số từ: 17._

## Số trong deck đã được cập nhật sau khi nộp

| Slide | Deck ghi | Script nói | Lý do |
|---|---|---|---|
| 2, 3, 16 | 2 441 bài mẫu tự sinh | 2 000 bài mẫu không trùng (S1 1 032 + S2 968) | Số cũ đếm trùng; `catalog.json · totals` |
| 7 | Mỗi lần dạy và thi ≈ 85 CU | Khoảng 101 CU ở vòng 1 (77,27 dạy + khoảng 23,4 chạy model để thi) | Số đo, [tray.md](../he/tray.md) 20.18 |
| 8 | ×28, đặt khay đúng chỗ 1 → 27 lượt | Bỏ | Chưa tìm thấy file nguồn |
| 9, 15, 16 | Dạy ≈ 76 CU, thi 60 lượt ≈ 9 CU | 77,27 CU; khoảng 23,4 CU | Số đo của vòng 1; không tìm thấy nguồn của 76 và 9 |
| 15 | Mỗi vòng sửa lỗi chưa tới 10 USD | Khoảng 10,9 USD (khoảng 109 CU) | 8,55 + 77,27 + 23,4 CU, giả định 0,1 USD một CU |
| 12, 17 | Chưa có kết quả vòng 1 | Bản sau vòng 1 đạt 4 trên 60 lượt thi; luật viết trước cho dừng; vòng 2 là đề xuất | Kết quả có sau khi nộp; tray.md 20.18 |

Số trên slide mà script không đọc vì chưa kiểm được nguồn: 7 lần dạy, 820+ lượt thi, 153 đoạn video (slide 2, 3), 922 bước con có nhãn (slide 11). Số công bố bên ngoài (Tesla, Physical Intelligence, BMW và Figure, Counterpoint Research) có nguồn ở chân slide 5, 6, 16; script không đọc lại.

## Bảng thuật ngữ Việt · Anh (30 mục)

| Tiếng Việt | English | Nghĩa |
|---|---|---|
| bài mẫu | demonstration (episode) | Một lần làm mẫu trọn việc để robot học theo; trong dự án phần lớn do máy sinh trong mô phỏng. |
| bản dạy | trained model version (training run) | Một model Ψ₀ đã dạy trên một bộ bài mẫu cố định; mỗi bản dạy một lần. |
| lượt thi | evaluation episode (rollout) | Một lần robot làm việc bê khay trong mô phỏng để chấm điểm. |
| bước | step (stage) | Một khâu trong việc bê khay hoặc trong quy trình 6 bước của hệ thống. |
| chấm 7 bước | 7-step scoring | Bộ chấm chia một lượt thi thành 7 bước: tới bàn A, cầm, nhấc, mang, tới bàn B, đặt, buông tay và đứng yên. |
| bộ chấm | scorer | Phần mềm chấm từng lượt thi và ghi bước hỏng đầu tiên. |
| sổ chi phí | cost ledger | Bảng ghi chi phí từng việc: một dòng ước tính trước, một dòng thực đo sau, không xóa. |
| ước tính / thực đo | estimated / measured | Hai loại dòng trong sổ chi phí; dòng thực đo trỏ về dòng ước tính. |
| CU | compute unit (Colab) | Đơn vị tính tiền GPU của Google Colab; đội giả định 1 CU khoảng 0,1 USD. |
| kiểm định | quality check (QA) | Kiểm từng tập dữ liệu trước khi dạy, loại tập hỏng. |
| Agent QA/QC | Agent QA/QC (automatic quality inspector) | Kiểm định viên tự động, gồm mã kiểm tra và một model ngôn ngữ. |
| lỗi cấy | planted defect | Lỗi đội cố ý cấy vào bản sao dữ liệu để thử kiểm định viên; bản sao này không bao giờ dùng để dạy. |
| kiểm hệ thống | system check | Bước kiểm bộ chấm, tín hiệu đo và mô phỏng trước khi thu dữ liệu. |
| chẩn đoán | diagnosis | Xác định một nhóm lỗi là do model yếu hay do hệ thống. |
| cụm lỗi | failure cluster | Nhóm các lượt thi hỏng có cùng bước hỏng và cùng kiểu lỗi. |
| phiếu sửa | fix ticket | Việc sửa hệ thống được mở khi lỗi không phải do model; không tốn dữ liệu. |
| nhắm lỗi | failure-targeted | Dữ liệu sinh quanh đúng tình huống robot đã hỏng. |
| thêm đều | uniform addition | Thêm dữ liệu rải đều, không nhắm vào lỗi; dùng làm đối chứng. |
| đối chứng | control (comparison) | Bản dạy hoặc phép so dùng để biết thay đổi có thật do can thiệp hay không. |
| luật viết trước | pre-registered rule | Cách đọc kết quả được viết và khóa trước khi thi; không đổi sau khi thấy kết quả. |
| khoảng tin cậy 95 % | 95 % confidence interval | Khoảng giá trị có thể của chênh lệch; nếu chứa 0 thì chưa kết luận được. |
| dung sai | tolerance | Mức lệch cho phép khi đặt khay: chuẩn là 5 cm và 10 độ. |
| dung sai nới | relaxed tolerance | Dung sai rộng hơn chuẩn (7,5 đến 20 cm), chỉ dùng làm chỉ số phụ. |
| chỉ số phụ | secondary metric | Số đo dùng để mô tả thêm, không dùng để kết luận. |
| mô phỏng | simulation | Môi trường máy tính tái tạo robot, bàn và khay; đội gọi là nhà máy ảo. |
| teleop | teleoperation | Người điều khiển robot từ xa để làm mẫu; tốn giờ người. |
| video người | egocentric human video | Video quay từ góc nhìn người làm việc, bằng điện thoại đeo đầu; được che mặt trước khi xử lý. |
| seed | seed | Mã số cố định vị trí khay của một lượt thi, để lượt thi lặp lại được. |
| vòng | round | Một lần đi hết 6 bước: dạy, thi, chẩn đoán, thu dữ liệu, dạy lại. |
| sơ bộ | preliminary | Kết quả trong mô phỏng, mỗi bản dạy một lần; chưa đủ để kết luận chắc. |
