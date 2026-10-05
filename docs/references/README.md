# Nguồn nghiên cứu

Các nguồn dưới đây làm cơ sở chọn phương pháp. Kết quả của tác giả không phải kết quả của đội. Khi triển khai cần kiểm quyền sử dụng code, mô hình và dữ liệu.

## Nguồn chính cho hướng hiện tại

| Nguồn | Dùng để tìm hiểu |
|---|---|
| [EgoVLA](https://rchalyang.github.io/EgoVLA/) | Học từ dữ liệu người và thích nghi sang humanoid |
| [HumanEgo](https://humanego-ai.github.io/) | Tín hiệu thao tác người và phương pháp học robot |
| [Ψ₀](https://psi-lab.ai/Psi0/) | Quy trình học kỹ năng humanoid từ dữ liệu người |
| [FluxVLA](https://github.com/FluxVLA/FluxVLA) | Nền tảng để tích hợp huấn luyện, đánh giá và suy luận |

FluxVLA đã được chọn theo yêu cầu của đội. Phương pháp học từ người và robot / task cụ thể còn cần kiểm tra khả năng tích hợp. Dữ liệu teleop theo LeRobotDataset; dữ liệu công khai dùng cho thử nghiệm ban đầu khi phù hợp.

## Thư viện paper local

PDF giữ trên máy tại `docs/references/papers/` để nghiên cứu các hướng mở rộng; không commit lên GitHub và không mặc định đưa tất cả vào MVP ba tháng. Website đọc nội dung/ảnh đã chuẩn bị, không cần thư viện PDF này để chạy. Nguồn online của phương pháp có trong catalog và các tài liệu khảo sát.

- Thu và tăng cường dữ liệu: UMI, [MimicGen](https://mimicgen.github.io/), [DreamGen](https://research.nvidia.com/labs/gear/dreamgen/).
- Các hướng học / mô hình bổ sung: FOCA, WALA, World Action Models Survey, Fast WAM, Faster WAM, [DreamZero](https://dreamzero0.github.io/), Tau0 WM.

Chi phí hiện dùng trong [business case](../07-business-case.md) là giả định minh bạch. Đơn giá và lợi ích thực cần đo / lấy báo giá cho pilot DENSO.

Khảo sát hiện hành theo cơ chế và lựa chọn MVP nằm ở [docs11](../11-method-survey.md); nguồn numerical samples, remote media và giới hạn ở [docs12](../12-public-data-examples.md). Các PDF trong thư mục papers là thư viện tham khảo, không tự là implementation tương thích FluxVLA.
