# Humanoid Skill Learning

**Giúp đội AI/robotics dạy và cải thiện kỹ năng humanoid: biết bước nào đã được thử, kiểm điểm nghẽn, thu dữ liệu đúng và đo tổng công tới cùng chất lượng.**

Đề xuất hướng tới bài toán H1 của DENSO: huấn luyện humanoid nhanh, chính xác và giảm công sức con người. Người dùng chính là đội AI/robotics phát triển kỹ năng mới cho robot.

## Vấn đề

Thu dữ liệu bằng cách điều khiển robot làm mẫu cần người vận hành, thiết bị, chuẩn bị hiện trường và đặt lại vật sau mỗi lượt. Khi tác vụ, vị trí hoặc ánh sáng thay đổi, đội phát triển có thể phải thu thêm mẫu và thử nghiệm nhiều lần.

Trong khi đó, video người và dữ liệu mô phỏng có thể bổ sung trải nghiệm liên quan. Thách thức là sử dụng đúng tín hiệu của từng nguồn để giúp robot học, đồng thời kiểm tra xem công sức tiết kiệm có lớn hơn phần xử lý và huấn luyện thêm hay không.

## Ý tưởng giải pháp

Xây dựng công cụ hỗ trợ đội AI/robotics xuyên suốt quá trình chuẩn bị dữ liệu, huấn luyện, đánh giá và cải thiện một kỹ năng humanoid.

| Nguồn dữ liệu | Vai trò trong giải pháp |
|---|---|
| Video góc nhìn thứ nhất của người | Bổ sung trình tự thao tác và chuyển động tay khi có nhãn đủ tin cậy |
| Video internet có quyền sử dụng | Bổ sung ví dụ về vật, thao tác và bối cảnh liên quan |
| Dữ liệu tổng hợp/mô phỏng | Mở rộng điều kiện học bằng biến thể được kiểm tra chất lượng |
| Mẫu thao tác robot đích | Dạy hành động đúng với robot, hỗ trợ hiệu chuẩn và sửa lỗi tương tác |

Video người không tự trở thành lệnh điều khiển robot. Giải pháp kết hợp tín hiệu học bổ sung từ video với đường học hành động từ mẫu robot. Mỗi phương án chỉ dùng các nguồn phù hợp với tác vụ, quyền sử dụng và khả năng tích hợp.

## Ví dụ sử dụng

**Nhiệm vụ: “Đặt linh kiện màu vàng vào ô A1.”**

Humanoid quan sát linh kiện và khay, tiếp cận, gắp, chuyển, đặt và nhả vật. Video người cung cấp ví dụ về trình tự; mẫu robot cung cấp hành động tương ứng với robot đích.

Nếu robot còn yếu ở nền hoặc ánh sáng mới, đội thử bổ sung biến thể hình ảnh. Nếu linh kiện bị trượt khi gắp, đội kiểm tra bộ gắp và ưu tiên mẫu sửa lỗi của robot. Mỗi thay đổi được đánh giá lại về chất lượng và tổng công sức.

Đây là tác vụ đại diện đề xuất. Tác vụ cụ thể và tiêu chuẩn tại DENSO cần được xác nhận khi tiếp cận nhà máy.

## Cách triển khai

1. **Định nghĩa kỹ năng:** chọn tác vụ, robot, điều kiện thao tác và tiêu chuẩn hoàn thành.
2. **Chuẩn bị dữ liệu:** thu mẫu robot, chọn video liên quan, kiểm quyền, nhãn và chất lượng; tách dữ liệu học khỏi dữ liệu đánh giá.
3. **Huấn luyện:** tận dụng mô hình có sẵn, giữ đường học hành động robot và tích hợp tín hiệu bổ sung từ nguồn đủ điều kiện.
4. **Đánh giá và cải thiện:** chấm từng bước và cả task, kiểm hệ thống/đầu vào bước, chọn correction hoặc bootstrap; huấn luyện với dữ liệu cũ + mới và kiểm regression/tổng công.
5. **Bàn giao:** mô hình điều khiển, cấu hình thực thi, quy trình dữ liệu và báo cáo so sánh có thể tái lập.

Đường kỹ thuật dự kiến là **FluxVLA + GR00T N1.5 + humanoid GR1 trong RoboCasa/MuJoCo**. Phạm vi đầu tiên gồm một tác vụ gắp–đặt, một tay hoạt động và torso cố định trong mô phỏng. Nhánh video người cần kiểm tương thích trước khi thử lợi ích; biến đổi hình ảnh cơ bản được ưu tiên trước các phương án tổng hợp phức tạp.

## Kết quả kỳ vọng

Ba đầu ra của kế hoạch nghiên cứu 12 tuần:

- **Demo kỹ năng:** humanoid thực hiện gắp–đặt bằng mô hình đã huấn luyện trong mô phỏng, kèm tiêu chuẩn chấm kết quả.
- **Quy trình dữ liệu:** hướng dẫn thu, kiểm tra và sử dụng từng nguồn, lưu nguồn gốc và phiên bản để dùng lại.
- **Báo cáo so sánh:** ít nhất hai cách huấn luyện thực sự chạy, báo chất lượng, số mẫu robot, giờ công và chi phí.

Mục tiêu PoC dự kiến là **≥75% thành công**, **≥70% trên biến thể giữ riêng** và **giảm ≥30% mẫu robot ở cùng chất lượng**. Đây là mục tiêu cần kiểm chứng và xác nhận theo tác vụ, chưa phải kết quả đã đạt hoặc chuẩn nghiệm thu nhà máy.

Giảm số mẫu robot chưa đồng nghĩa giảm tổng chi phí. Đánh giá phải tính cả thu mẫu, xử lý video, kiểm dữ liệu, huấn luyện, thử lại và phân tích kết quả.

## Giá trị khác biệt và hướng mở rộng

Giá trị đề xuất nằm ở việc nối dữ liệu đa nguồn với hiệu quả phát triển kỹ năng: dùng từng nguồn đúng vai trò, chọn phần cần bổ sung và đo tổng công để đạt chất lượng yêu cầu. Đội tận dụng nền tảng và phương pháp có sẵn, tập trung xây phần tích hợp dữ liệu, tác vụ, đánh giá và quy trình cải thiện.

Sau kỹ năng đầu tiên, thử tác vụ thứ hai trên cùng robot để đo mức tái sử dụng. Chuyển sang robot thật cần kiểm điều khiển, chất lượng, thời gian chu kỳ và nghiệm thu riêng.

**Hiện trạng: đề xuất ở vòng idea; chưa có kết quả huấn luyện hoặc tiết kiệm thực nghiệm của đội.**

Chi tiết: [Sản phẩm](docs/01-product.md) · [Cơ chế học](docs/04-learning-core.md) · [Kết quả kỳ vọng](docs/13-expected-outcomes.md).

## Revision 2: vòng cải thiện task

Pass/fail/chưa thử/chưa rõ giúp không quy lỗi cho bước chưa tới. Controlled probes kiểm lỗi do bước trước; useful baseline dùng targeted corrections, no basic skill dùng expert seed/curriculum hoặc rescope. Shared policy cần prior replay và whole-task/regression checks; local success không đủ promote.

[Solution đầy đủ](docs/14-task-improvement.md) · [Rà soát toàn idea](docs/reviews/full-idea-audit-2026-10-05.md). Website có ví dụ tương tác khai báo để giải thích logic; chưa verifier hoặc training backend kết nối robot. Bộ ảnh/video 9 cảnh là bản nhập môn; bản revision2 này sở hữu chi tiết cải thiện.
