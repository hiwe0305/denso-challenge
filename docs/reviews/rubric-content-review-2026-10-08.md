# Rà soát nội dung theo bảng chấm điểm — 08/10/2026

## Phạm vi và kết luận

Đối chiếu ảnh bảng tiêu chí người dùng gửi với nội dung 24 slide trong `deliverables/DENSO-Humanoid-Data-Flywheel-2026.pptx`, `IDEA.md`, bản form, bản pitch Markdown và `docs/07-business-case.md`. Đây là rà soát nội dung và bằng chứng có trong hồ sơ, không phải chấm điểm chính thức, kiểm chứng các paper bên ngoài hoặc đánh giá trực tiếp chất lượng model. Chưa sửa bản PPT hay nội dung nộp.

Nhận xét “nhiều kiến thức nhưng chưa đúng trọng tâm chấm điểm” có cơ sở. Hồ sơ giải thích hệ thống và thiết kế kiểm chứng khá kỹ, nhưng chưa đưa ra một business case cụ thể để người chấm thấy vấn đề, giá trị và khả năng thực hiện. Có khoảng trống bằng chứng thực tế bên cạnh vấn đề diễn đạt. Rút gọn slide chỉ giải quyết được phần diễn đạt.

Deck có 14 slide chính và 10 slide phụ lục, không phải cả 24 slide đều là phần pitch. Dù vậy, phần chính thiếu slide hiệu quả kinh tế, mở rộng và đội ngũ đủ rõ. Không thể suy từ độ dài rằng bài chắc chắn trượt.

## Đối chiếu sáu tiêu chí

| Tiêu chí | Trọng số | Hồ sơ hiện có | Khoảng trống và việc cần làm |
|---|---:|---|---|
| Sáng tạo và đột phá | 30% | Slide 3 nêu phần kế thừa và phần đội xây; slide 5–6, 9 minh họa quyết định dữ liệu từ lỗi | Cần một so sánh trước/sau với cách làm cụ thể: kỹ sư hiện quyết định thế nào, hệ thống hỗ trợ thêm điều gì, phép đo nào xác nhận giá trị. Data flywheel hay dùng VLA tự chúng chưa chứng minh mức đột phá. |
| Khả thi nghiệp vụ | 20% | Slide 2 nhận diện công thu mẫu, QA, debug, training; IDEA xác định người dùng là kỹ sư robot learning | Chưa có công đoạn DENSO, task owner hoặc baseline được xác nhận. Cần chọn một quy trình, người sử dụng và điểm nghẽn có quy mô đo được. Tiết kiệm công phát triển skill phải gắn với nhu cầu phát triển/thay đổi skill thực tế. |
| Khả thi kỹ thuật | 20% | Slide 4, 7–12 có thành phần, dữ liệu, GPU và kế hoạch; reference nhỏ đã được mô tả trong hồ sơ | Native integration, training/inference và robot thật của đội chưa có bằng chứng. GPU có sẵn chưa chứng minh recipe chạy được. Đưa trạng thái đã làm, kết quả kiểm, phần còn thiếu và phụ thuộc hardware lên một slide. |
| Hiệu quả và đo lường | 15% | Slide 11 mô tả phép so; slide 21 có mục tiêu thử nghiệm; business case có các hạng mục chi phí | Chưa có lợi ích USD/năm hoặc mô hình before/after đủ cơ sở. Ngân sách thử nghiệm không phải tiền tiết kiệm. Cần baseline, số lần áp dụng/năm, chênh lệch tổng chi phí, giả định và cách xác nhận. |
| Mở rộng và tích hợp | 10% | Slide 23 đề cập task thứ hai cùng robot; tài liệu có hướng reuse và adaptation | Chưa có slide chính thể hiện nơi áp dụng tiếp, thành phần tái sử dụng, công phải làm mới và điều kiện tích hợp. Không thể lấy số nhà máy nhân thẳng với lợi ích khi chưa biết khả năng áp dụng. |
| Năng lực và kinh nghiệm đội | 5% | Slide 24 liệt kê vai trò cần có | Chưa có tên, kinh nghiệm, sản phẩm đã làm, phân công và mức tham gia thực tế. Đây là tiêu chí bắt buộc có ít nhất một thành viên kỹ thuật theo ảnh; danh sách vai trò mong muốn chưa đáp ứng bằng chứng đó. |

Ba tiêu chí đầu chiếm 70%. Hiệu quả kinh tế rất cần sửa nhưng không thể bù toàn bộ phần nghiệp vụ, tính mới và khả thi còn thiếu bằng chứng.

## Những chỗ cụ thể đang làm mất thông điệp

1. **Slide 1:** “Ước lượng 30 ngày phát triển MVP” nhấn vào thời gian làm sản phẩm. Cần đưa người hưởng lợi và giá trị lên trước: công cụ hỗ trợ kỹ sư chọn dữ liệu cần bổ sung khi robot làm sai, hướng tới giảm công phát triển kỹ năng.
2. **Slide 2:** số liệu Figure thể hiện cơ hội ngành, chưa thể hiện thiệt hại hoặc quy mô bài toán ở nơi triển khai. Giữ làm tham khảo nếu cần; phần chính cần số đo của quy trình mục tiêu hoặc giả định được đánh dấu rõ.
3. **Slide 3:** đã phân biệt kế thừa và đóng góp nhưng còn trừu tượng. Dùng một ví dụ: lỗi gì, cách hiện tại xử lý ra sao, hệ thống cung cấp thêm thông tin nào và tránh được công việc gì nếu giả thuyết đúng.
4. **Slide 7–10:** phần model, batch, loss và inference đang nhận nhiều diện tích hơn tác động nghiệp vụ. Gộp sơ đồ vận hành ở phần chính; giữ tensor, loss, gradient và recipe trong phụ lục.
5. **Slide 11:** cách chứng minh khác biệt là cần thiết, nhưng chưa trả lời “cải thiện bao nhiêu và quy thành giá trị thế nào”. Cần thêm slide hiệu quả riêng.
6. **Slide 12–13:** có thể gộp kế hoạch phát triển và mốc cuộc thi để dành chỗ cho hiệu quả, mở rộng và đội.
7. **Slide 21:** mục tiêu 16/20 lượt nằm ở phụ lục. Đưa mục tiêu PoC lên slide khả thi/đo lường, ghi rõ là mục tiêu chưa đạt. Tách khỏi protocol nghiên cứu lớn hơn.
8. **Slide 23, câu 4:** câu hỏi yêu cầu hiệu quả và số liệu nhưng câu trả lời mô tả chức năng sản phẩm. Đây là lệch câu hỏi rõ nhất. Phải trả lời bằng chỉ số kết quả, cách tính và trạng thái số liệu.
9. **Slide 24:** bổ sung đội thật. Vai trò dự kiến chưa chứng minh năng lực triển khai.

## Hiệu quả kinh tế: cần tính gì để trả lời đúng bảng chấm

Ảnh ghi mức cao nhất là **hiệu quả định lượng >20.000 USD/năm**, không phải cứ hiển thị đúng 20.000 là tự có 10 điểm. Ảnh cũng phân biệt mức 4 điểm cho dự kiến lợi ích thiếu cơ sở tính toán và 2 điểm cho chỉ nêu ý tưởng, không có dữ liệu. Không nên mặc định mọi trường hợp trình bày chưa rõ đều chính xác là 2 điểm.

Với sản phẩm hiện tại, đường tạo giá trị trực tiếp nhất để khảo sát là công phát triển/cải thiện skill. Chưa có cơ sở để quy toàn bộ năng suất robot hoặc khoản thay thế lao động thành lợi ích của Data Core.

Mô hình cần thể hiện:

**Lợi ích ròng năm ổn định = số đợt cải thiện đủ điều kiện/năm × (tổng chi phí mỗi đợt hiện tại − tổng chi phí mỗi đợt dùng giải pháp) − chi phí duy trì chung hằng năm.**

**Lợi ích ròng năm đầu = lợi ích của số đợt thực tế áp dụng trong năm đầu − chi phí duy trì năm đầu − chi phí triển khai ban đầu tăng thêm.**

Chi phí mỗi đợt gồm công operator/reset/thu dữ liệu, kỹ sư, QA, robot, GPU, lưu trữ, generation, thử lỗi và evaluation. Tính từng khoản đúng một lần. Hai cách phải đạt mức chất lượng và coverage tương đương mới so được chi phí.

Slide hiệu quả cần một bảng ngắn:

| Đầu vào | Hiện tại | Sau cải tiến | Nguồn và trạng thái |
|---|---|---|---|
| Giờ kỹ sư/đợt | Cần đo | Cần đo/ước tính | Timesheet hoặc giả định |
| Giờ operator và robot/đợt | Cần đo | Cần đo/ước tính | Log thu/reset |
| GPU, QA, thử lại và chi phí khác/đợt | Cần đo | Cần đo/ước tính | Ledger, báo giá, log |
| Số đợt có thể áp dụng/năm | Cần xác nhận | Chỉ tính phạm vi phù hợp | Task owner/kế hoạch công việc |
| Chi phí setup và duy trì tăng thêm | Cần xác định | Cần xác định | Phân biệt một lần và định kỳ |
| Chất lượng đầu ra | Cần đo | Cùng yêu cầu nghiệm thu | Kết quả đối chứng |

Khi chưa có pilot, có thể trình bày **kịch bản dự kiến** với giả định công khai và phân tích độ nhạy. Không đổi nhãn thành kết quả đã đạt. Công kỹ sư được giải phóng cần phân biệt với tiền mặt thực giảm chi.

Con số **5.187,20 USD** trong `docs/07-business-case.md` là subtotal một capacity budget đã ghi rõ giới hạn; không phải saving và không phải tổng ngân sách đã xác nhận của PoC 30 ngày. Mô hình lịch sử trong cùng file còn cho thấy chi phí tăng từ **9.315,89 lên 16.359,98 USD**, dù số robot roots giảm từ 400 xuống 280. Vì vậy, “ít demonstrations hơn” chưa đủ kết luận “rẻ hơn”. Không lấy các số này đổi tên thành lợi ích năm.

## Dàn bài chính đề xuất: 10 slide

| Slide | Nội dung người chấm cần thấy | Tiêu chí |
|---:|---|---|
| 1 | Tên giải pháp, người dùng và lợi ích hướng tới trong một câu | Định vị |
| 2 | Một quy trình mục tiêu, hiện trạng và điểm nghẽn có quy mô | Nghiệp vụ |
| 3 | Trước/sau qua một lỗi robot cụ thể, phần mới do đội xây | Sáng tạo |
| 4 | Một sơ đồ vận hành đơn giản từ lỗi đến dữ liệu và kiểm lại | Sáng tạo, kỹ thuật |
| 5 | Ví dụ can thiệp và bằng chứng đã có, tách mục tiêu chưa đạt | Kỹ thuật |
| 6 | Bảng hiệu quả, lợi ích USD/năm, giả định và phạm vi | Hiệu quả |
| 7 | Cách kiểm cùng chất lượng, chỉ số, đối chứng và tiêu chí đạt | Đo lường, nghiệp vụ |
| 8 | Kế hoạch 30 ngày, nguồn lực, phần thiếu và mốc kiểm khả thi | Kỹ thuật |
| 9 | Task/phòng ban tiếp theo, phần dùng lại và công tích hợp mới | Mở rộng |
| 10 | Đội thật, kinh nghiệm liên quan, phân công và đề nghị hỗ trợ | Năng lực đội |

Mỗi tiêu đề nên nêu kết luận mà slide chứng minh. Nhãn tiêu chí giúp người chấm định hướng; nội dung và bằng chứng mới quyết định khả năng đạt mức điểm.

## Đồng bộ hồ sơ trước khi nộp

- `IDEA.md` mở đầu ưu tiên 30 ngày nhưng mục 11 và câu hỏi cuối vẫn giữ bản nháp 12 tuần. Nếu giữ, gắn rõ “nghiên cứu mở rộng sau MVP” và tách khỏi cam kết nộp.
- `deliverables/Human-first-Humanoid-Pitch.md` còn dàn ý 12 tuần và phạm vi human/synthetic cũ. Cần gắn nhãn lưu trữ hoặc đồng bộ khi dùng làm bản pitch.
- IDEA còn mục tiêu 90%, trong khi form và PPT dùng mục tiêu PoC ≥16/20. Có thể là các cấp kiểm khác nhau, nhưng phải gọi tên và giải thích nhất quán.
- Chọn một ví dụ xuyên suốt cho người chấm. Public bottle-to-cabinet, proxy A1 và task trên robot BTC là các phạm vi khác nhau; không ghép thành một kết quả đã chạy.
- Đưa cùng một mô hình lợi ích, ngân sách, trạng thái demo và thông tin đội vào PPT, form và bản ý tưởng.

Ưu tiên bổ sung dữ liệu nghiệp vụ, mô hình hiệu quả và đội thật trước. Sau đó viết lại phần pitch theo sáu tiêu chí, giữ hồ sơ kỹ thuật làm tài liệu bảo vệ.
