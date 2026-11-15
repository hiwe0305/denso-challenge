# Flywheel Console · trang vòng dữ liệu theo deck (bản 0.3)

| Ngày | Phiên bản | Nội dung | Người viết |
|---|---|---|---|
| 15/11/2026 | 0.3 | Sửa [bản 0.2](2026-11-15-console-one-site-design.md) theo đánh giá của Hiếu ngày 15/11: chia lại 6 trạm đúng 6 bước Data Flywheel của deck bản 7 (slide 8–9), thêm trang vòng tròn làm trang đầu, thêm trạm "Kiểm hệ thống", đưa sổ chi phí vào giữa vòng, đổi trang story sang nền sáng màu DENSO. Phương án A, Hiếu chọn 15/11 | Hiếu (soạn với Claude) |

Bản này chỉ ghi phần **thay đổi** so với 0.2. Mọi quy tắc của 0.2 không nhắc lại ở đây vẫn giữ: số lấy từ file hoặc `cited.yaml`, `--lock`, VI/EN, "Theo chân một lỗi", thư viện mô phỏng, không chạy job mới cho demo.

## 1. Ý định

Hiếu xem bản 0.2 ngày 15/11: "nhìn nó xấu quá và không xem được kỹ các bước… chưa show ra được toàn ảnh các bước của data flywheel như trong powerpoint mới nhất". **[Đã chốt]**

Người xem tại DENSO Factory Hacks thường xem deck trước, rồi mở Console. Hai bên phải kể **cùng một vòng**, cùng tên bước, cùng thứ tự, cùng màu. Nếu hai bên kể khác nhau, người xem sẽ nghĩ đó là hai sản phẩm.

Nguồn chuẩn là deck `DENSO-ilovephysicalintelligence-7.pptx` (14/11). Slide 9 "Thiết kế kỹ thuật" ghi 6 bước: 1 Nạp, chuẩn hóa (LeRobot) · 2 Agent QA/QC · 3 Dạy Ψ₀ · 4 Thi, chấm 7 bước · 5 Kiểm hệ thống, chẩn đoán · 6 Lỗi → Dữ liệu, và sổ chi phí áp cho mọi bước. Slide 8 vẽ các bước đó thành vòng tròn, sổ chi phí ở giữa. **[Đã chốt]**

## 2. Mục tiêu, phản mục tiêu

**Mục tiêu**

1. Mở Console là thấy ngay toàn cảnh vòng 6 bước, giống slide 8. Bấm vào một bước là thấy bước đó làm gì, nhận gì, ra gì, và số đo thật.
2. Menu trái, dải giải thích, trang đầu và "Theo chân một lỗi" dùng cùng 6 tên bước của slide 9.
3. Trang story trông như deck: nền sáng, xanh navy và xanh lá DENSO, biểu tượng trong vòng tròn xanh.
4. Mỗi bước có một trang chi tiết theo cùng một khuôn (mục 5).

**Phản mục tiêu** (làm vậy là hỏng, dù chạy được)

- Hiện số không có file nguồn hay trích dẫn. Ví dụ "×28, đặt khay đúng chỗ 1 → 27 lượt" ở slide 8: mình chưa tìm thấy nguồn trong repo, nên không hiện cho tới khi có (mục 8).
- Làm vòng tròn đẹp nhưng kể quá kết quả: vòng 1 không cải thiện robot (`C70_R1` 4/60 < `C_70` 10/60). Bước 6 phải nói đúng như vậy.
- Phá trang kỹ thuật cũ hoặc đường dẫn cũ. Mọi URL cũ vẫn mở được (chuyển hướng).

## 3. Các phương án đã cân nhắc

| Phương án | Làm gì | Đánh đổi | Kết quả |
|---|---|---|---|
| **A** | Chia lại trạm theo slide 9, trang vòng tròn làm trang đầu, khuôn trang bước, nền sáng | Khoảng 1–1,5 ngày, phải sửa i18n, `stationOf`, test | **Hiếu chọn** |
| B | Giữ 6 trạm cũ, chỉ thêm trang vòng tròn toàn màn hình và nền sáng | Khoảng nửa ngày, nhưng menu vẫn khác deck, vẫn hai câu chuyện | Bỏ |
| C | Thiết kế lại mọi trang, cả trang vận hành | Không kịp 17/11 | Bỏ |

## 4. Chia lại 6 bước

| Bước mới | Tên (VI · EN) | Gộp từ trạm cũ | Route chính | Route khác thuộc bước |
|---|---|---|---|---|
| 1 | Nạp, chuẩn hóa · Ingest & standardise | 1 Thu dữ liệu + 3 Đóng gói | `#/data` | `#/sim`, `#/jobs?panel=export` |
| 2 | Agent QA/QC | 2 Xử lý và kiểm định | `#/jobs?view=pipeline` | `#/qa` |
| 3 | Dạy Ψ₀ · Train Ψ₀ | 4 Dạy Ψ₀ | `#/runs` | |
| 4 | Thi, chấm 7 bước · Test, score 7 steps | 5 Thi | `#/eval` | |
| 5 | Kiểm hệ thống, chẩn đoán · System check & diagnosis | **mới** (trước đây là tab "1 Kiểm hệ thống" trong trạm 6) | `#/diagnose` (mới) | |
| 6 | Lỗi → Dữ liệu · Failure → Data | 6 Lỗi → Dữ liệu | `#/loop` | |
| giữa vòng | Sổ chi phí · Cost ledger | menu Vận hành "Chi phí" | `#/loop?tab=cost` | |

- Ở bước 1, câu giải thích nhắc "ưu tiên nguồn rẻ" để khớp nhãn "Chọn nguồn rẻ" của slide 8. **[Đề xuất]**
- "Đóng gói" (bản cắt có sha256) trở thành một phần của bước 1 ("chuẩn hóa"). Bước 3 nói model được dạy trên bộ dữ liệu đã đóng băng. **[Đề xuất]**
- Sổ chi phí vào nhóm menu của vòng, có biểu tượng `$`. Nó không còn nằm trong nhóm Vận hành. **[Đề xuất]**
- Nhóm Vận hành (Jobs, Máy, Nhập dữ liệu) vẫn còn, nhưng ẩn khỏi menu khi chạy `--lock`; vẫn mở được qua "Chi tiết kỹ thuật". **[Đề xuất]**

## 5. Trang

### 5.1 Trang đầu = vòng tròn (thay trang "Bắt đầu")

Bố cục theo mockup `.superpowers/brainstorm/mockups/flywheel-v03.html` (worktree d49f4f):

- Tiêu đề lấy câu chính của deck: "Robot hỏng ở đâu, thu dữ liệu đúng chỗ đó", thêm một câu dẫn.
- Bên trái là vòng SVG: 6 nút tròn đánh số, mũi tên theo chiều kim đồng hồ, sổ chi phí ở giữa. Mỗi nút có tên bước, kèm một số và nhãn của số đó.
- Bên phải là bảng của bước đang chọn: câu hỏi · Đầu vào → Hệ thống làm gì → Đầu ra · tối đa 3 số chứng minh · một hình nhỏ khi có (bước 4 là thanh 7 bước) · "Chỗ có thể sai" · nút "Xem chi tiết bước n".
- Bấm nút trên vòng thì đổi bảng. Phím ←/→ chuyển bước. Mặc định chọn bước 1.
- Dưới vòng là thẻ "Theo chân một lỗi" và phần "Hôm nay · cho đội" (KPI, chờ duyệt) như bản 0.2.
- Màn rộng dưới 1180 px thì bảng chi tiết xuống dưới vòng.

### 5.2 Khuôn trang một bước (thay dải giải thích của 0.2)

Thứ tự từ trên xuống:

1. Thanh 7 ô: 6 bước và Chi phí. Ô đang xem tô navy, ô trước tô xanh nhạt. Bấm được.
2. "BƯỚC n / 6", câu hỏi làm tiêu đề, một câu trả lời.
3. Ba ô Đầu vào → Hệ thống làm gì → Đầu ra.
4. Tối đa 3 số chứng minh, có tooltip nguồn như 0.2.
5. Hình của bước (giữ hình của 0.2, chỉ đổi màu; bước 5 dùng thẻ cụm).
6. "Chỗ có thể sai".
7. "Chi tiết kỹ thuật": trang vận hành cũ của route đó, đặt bên dưới, giữ nguyên.
8. Nút ← bước trước / bước sau →.

Giới hạn chữ: câu trả lời cùng ba ô vào/làm/ra ≤ 90 từ mỗi bước, theo quy tắc `st.N.*` của 0.2. Nhãn hình không tính vào giới hạn.

### 5.3 Trang mới `#/diagnose` (bước 5)

Không chạy gì mới; chỉ đọc file đã có.

- Thẻ cụm: 8 cụm từ `story.round.clusters`, chia hai nhóm: sang dữ liệu (c1, c2, c3, c8) và phiếu sửa hệ thống (c4, c5 → DA-38; c6, c7 → DA-37). c3, c8 thuộc nhóm dữ liệu theo quyết định R8 (tray.md 20.9, "[Đã chốt 12/11/2026, Hiếu]": "c3, c8 đọc là lỗi của policy"). Hai phiếu lấy từ tray.md 20.11 và dòng 7.2 của 20.9. Cả ba câu vào `cited.yaml`.
- Tab "1 Kiểm hệ thống" của trang Loop thành liên kết sang `#/diagnose`, không vẽ bảng cụm hai lần. **[Đề xuất]**
- Bảng kiểm H1–H3 cùng dòng "Độ trễ, đồng bộ, camera", trích ngắn từ `docs/he/tray.md` mục 20.3. Thêm vào `cited.yaml` với câu trích nguyên văn.
- Số: 4/8 cụm sang dữ liệu · 4/8 cụm thành phiếu sửa · 0 CU (tiêu đề 20.3 ghi "(0 CU)").
- Phần "Chi tiết kỹ thuật": bảng cụm hiện có của trang Loop.

### 5.4 Số mới cần nguồn

| Số | Bước | Nguồn |
|---|---|---|
| 30/30 lỗi cấy bị bắt, 0/40 báo nhầm (lớp code, bộ log cấy) | 2 | `docs/g0/defect-bench.md` (dòng "Lớp code, báo nhầm trên bản sạch | 0/40 job") và `docs/g0/agent-qa.md` mục 3.2; vào `cited.yaml` |
| 78–87 % lượt hỏng nằm ở bước đặt khay: với mỗi bản cơ sở `C_ALL`, `C_70`, `B_ALL`, `B_70`, tính (`L-PLACE-POSE` + `L-TRAY-TILT`) / tổng nhãn lỗi, rồi hiện khoảng nhỏ nhất–lớn nhất (80, 84, 78, 87 %). Không tính `C70_R1` | 4 | Tính từ `story.pair.runs[].failures` (khóa đã có) |
| Thanh 7 bước của bản tốt nhất | 4 | `story.pair.runs[].step_pass` (đã có) |
| 4/8, 0 CU | 5 | `story.round.clusters`; tray.md 20.3 |
| Sổ chi phí: số việc có sổ (13), và từng việc hai cột ước tính / thực đo, đơn vị USD (`amount_usd`, chia theo `estimated_or_measured`) | giữa | `story.ledger` |

Số trên mỗi nút của vòng là số chứng minh đầu tiên của bảng bước đó: (1) 2.572 tập, (2) 317/379 clip đạt, (3) 5 bản đã dạy, (4) 10/60 tốt nhất, (5) 4/8 cụm sang dữ liệu, (6) 23 → 181. Ở giữa vòng **không** hiện tổng ước tính 202,5 $ với tổng đo 16,2 $. Hai tổng này không so được với nhau vì nhiều việc chỉ có dòng ước tính, chưa có dòng đo. Thay vào đó, giữa vòng ghi "13 việc có sổ · ước tính và thực đo từng việc". Bảng chi phí hiện từng việc có đủ cả hai dòng. **[Đề xuất]** (sửa so với mockup)

Khi đổi số bước, chỉ URL cũ phải còn mở được. Menu, ⌘K và ngữ cảnh chat đều đọc từ `SIDE()` và `stationOf`, nên đổi tên ở mọi chỗ và không giữ bảng bí danh. **[Đề xuất]**

## 6. Giao diện

- Trang story (trang đầu, khuôn bước, Theo chân một lỗi, thư viện mô phỏng) mặc định nền sáng. Bảng màu lấy theo deck: navy `#1F2A6B`, xanh lá `#1E9E5A` và `#2BB673`, nền xanh nhạt `#EAF6EE`, đỏ lỗi `#C0392B`. Chữ sans 15–16 px. Motif: số bước trong vòng tròn xanh. **[Đề xuất]**
- Thanh trên cùng có chuyển màu navy sang xanh như đầu slide. Khi `--lock`, ẩn các pill vận hành (jobs, 3060, nemotron, chờ duyệt); chỉ giữ VI/EN, Giải thích và huy hiệu khóa. **[Đề xuất]**
- Khung chat đóng khi mở trang. Khi `--lock` thì như 0.2 (offline). **[Đề xuất]**
- Trang vận hành giữ nền tối nếu người dùng chọn tối. Nút ◐ vẫn đổi cả site. Mặc định của site đổi sang sáng. **[Đề xuất]**

## 7. Việc để người làm tự quyết

- Cách vẽ SVG, khoảng cách, cỡ chữ, miễn khớp mockup và đọc được ở 1366×768 lẫn 1920×1080.
- Chia file JS: trang vòng có thể vào `pages_start.js` hoặc một file mới `pages_wheel.js`.
- Tên khóa i18n mới. Khóa `st.N.*` đổi nghĩa theo số bước mới; viết lại cả VI lẫn EN.

## 8. Câu hỏi mở cho Hiếu

1. Số "×28, đặt khay đúng chỗ 1 → 27 lượt" (slide 8): nằm ở file nào? Chưa có nguồn thì bước 5 không hiện số này.
2. Bộ log cấy: dùng số của lớp code (30/30, 0/40, ngày 5/11) hay lớp agent với Nemotron (30/30, 1/40, ngày 12/11)? Đề xuất dùng lớp code vì khớp deck, kèm ghi chú.

## 9. Mốc cắt nếu thiếu giờ

Phải có trước 17/11: mục 4 (chia lại bước và chuyển hướng), 5.1 (trang vòng), 5.3 (trang bước 5), 6 (nền sáng, ẩn pill khi khóa). Có thì tốt: 5.2 đầy đủ cho cả 6 bước (nếu không kịp thì giữ dải 0.2, chỉ đổi màu và thêm thanh 7 ô). Sau demo: dịch bảng kỹ thuật, so sánh "trước / sau" như slide 7–8.
