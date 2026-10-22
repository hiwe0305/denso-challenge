# Đề bài: Efficient Humanoid Training & DENSO Data Model

_Hai ảnh đề chính thức ([1.jpeg](1.jpeg), [2.jpeg](2.jpeg)) ghi mã **H2 · Nhóm 2 · Humanoid & Robot**. Bản chữ chép từ trang BTC trước đây ghi **H1: Train Humanoids Fast, Accurate, Low Man-Hours**. Cần xác nhận với BTC mã nào là mã chính thức; repo hiện vẫn gọi là H1._

## Vấn đề (pain points)

- DMVN muốn phát triển humanoid nhưng đưa vào nhà máy là thách thức lớn.
- Training humanoid tốn nhiều thời gian và chưa đạt độ chính xác cao.
- Chưa có mô hình thu thập dữ liệu chuẩn của DENSO để dạy robot hiệu quả.
- Mỗi kỹ năng mới lại phải thu thập dữ liệu từ đầu, chi phí cao.

## Mục tiêu kỹ thuật

Khảo sát và thử nghiệm phương pháp huấn luyện humanoid đơn giản, hiệu quả hơn; thiết kế mô hình thu thập dữ liệu DENSO để huấn luyện robot.

## Phạm vi 3 tháng

1 kỹ năng thao tác cụ thể trong simulation; so sánh ít nhất 2 phương pháp train và lượng dữ liệu cần.

## Dữ liệu DENSO sẽ cung cấp

- Mô tả 1–2 kỹ năng humanoid DMVN muốn dạy.
- Video / demo thao tác tham chiếu.
- Layout và ràng buộc trạm làm việc.
- (Tùy chọn) Thông số robot humanoid ứng viên.

Kịch bản pain point chi tiết: chờ DENSO gửi.

## Đầu ra sau 3 tháng

Quy trình thu thập dữ liệu chuẩn, báo cáo so sánh phương pháp train, demo kỹ năng học được.

## Công nghệ gợi ý

Isaac Sim, imitation learning / RL, teleoperation data, PyTorch, robomimic.

## Ba cấp độ và tiêu chí định lượng

| Cấp | Trọng tâm kỹ thuật | Tiêu chí định lượng |
|---|---|---|
| 1 · Basic | Thu demo và train behavior cloning cơ bản | Thành công ≥ 50% với lượng demo nhỏ |
| 2 · Efficient | Domain randomization, phương pháp tiết kiệm dữ liệu | Giảm ≥ 30% demo cho cùng hiệu năng; thành công ≥ 75% |
| 3 · Advanced (cần AI) | So sánh phương pháp SOTA và quy trình thu dữ liệu DENSO | ≥ 70% trên biến thể chưa train; khuyến nghị quy trình thu dữ liệu định lượng |

Cấp 3 là cấp khó nhất và hướng tới ứng dụng AI.
