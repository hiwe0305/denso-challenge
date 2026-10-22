# Phòng phát triển sản phẩm · Humanoid Data Flywheel

Thư mục này là bộ hồ sơ sản phẩm làm theo BMAD Method (Breakthrough Method of Agile AI-Driven Development). Mục tiêu: làm rõ và phát triển **lõi data flywheel** thành sản phẩm mở rộng được, rồi chia việc cho đội 5 người và lấy phản biện từ mentor.

## Vai trò và tài liệu

| Bước | Vai trò BMAD | Tài liệu | Trả lời câu hỏi |
|---|---|---|---|
| 0 | Trưởng nhóm | [00 · Phân tích idea](00-idea-analysis.md) | Sản phẩm là gì, lõi là gì, đã chứng minh gì |
| 1 | Analyst | [01 · Project brief](01-project-brief.md) | Vì sao đáng làm, cho ai, khác gì giải pháp có sẵn |
| 2 | Product Manager | [02 · PRD](02-prd.md) | Phải làm gì, theo epic và story nào, nghiệm thu ra sao |
| 3 | Architect | [03 · Kiến trúc](03-architecture.md) | Xây thế nào để mở rộng từ 1 task sim lên nhiều robot, nhiều nhà máy |
| 4 | Product Owner + Scrum Master | [04 · Kế hoạch triển khai](04-delivery-plan.md) | Ai làm gì, sprint nào, định nghĩa hoàn thành |
| 5 | QA + phản biện | [05 · Phản biện và câu hỏi cho mentor](05-review-and-mentor-questions.md) | Chỗ nào yếu, hỏi mentor gì |
| 6 | Trưởng nhóm | [06 · Quyết định áp dụng phản biện vòng 1](06-review-round-1-decisions.md) | Cách áp 10 sửa ưu tiên của QA, đổi tên giả thuyết HS, HT, HD |
| — | Scrum Master | [stories/](stories) | 11 story của Sprint 1 theo mẫu story của BMAD |

Đặc tả thuật toán và thiết kế thí nghiệm gốc: [spec v10.1](../spec-v10-failure-to-data.md).

## Trạng thái ngày 22/10/2026

- 00–06 và 11 story Sprint 1 đã có; website 12 trang đã cập nhật theo spec v10.1. PO đã đồng bộ tên giữa 01, 02, 03 (xem change log từng file).
- QA xếp 01, 02, 03 ở mức "cần sửa". 10 sửa ưu tiên ([05 mục 7](05-review-and-mentor-questions.md)) đã áp ngày 22/10/2026 theo [06](06-review-round-1-decisions.md): spec v10.1, 00 bản 0.2, 01–03 bản 0.3, 04 bản 0.2. Câu hỏi mở sau vòng 1 ở 05 mục 6.6.
- Mã đề: ảnh đề của BTC ghi H2, bản chữ ghi H1 (xem [đề bài](../challenge/README.md)). Cần xác nhận với BTC.

## Vòng làm việc

BMAD đi theo vòng **Làm rõ → Lập kế hoạch → Xây và kiểm → Học và điều chỉnh**. Áp vào đội:

1. **Làm rõ:** mỗi thay đổi lớn bắt đầu bằng việc sửa 00 hoặc 01, không sửa thẳng code.
2. **Lập kế hoạch:** PRD (02) và kiến trúc (03) là nguồn sự thật; story trong 04 trỏ về requirement và module tương ứng.
3. **Xây và kiểm:** mỗi story có tiêu chí chấp nhận; xong khi qua định nghĩa hoàn thành trong 04.
4. **Học và điều chỉnh:** cuối mỗi sprint, cập nhật sổ chi phí, kết quả cổng, và đưa câu hỏi mới vào 05 để hỏi mentor.

## Quy tắc chung

- Thuật ngữ theo glossary của spec v10 (mục 12).
- Giả định về DENSO luôn ghi là giả định cho đến khi có số đo hoặc xác nhận.
- Khi PRD và kiến trúc lệch nhau, Product Owner quyết định và ghi lý do vào change log của tài liệu bị sửa.
