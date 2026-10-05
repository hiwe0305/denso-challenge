# Hướng trình bày trực quan · 05/10/2026

Ưu tiên người dùng chọn: **demo robot chuyển động, kèm luồng hệ thống như NVIDIA**.

## Tham khảo đã xem

- [NVIDIA Synthetic Manipulation Motion Generation](https://build.nvidia.com/nvidia/isaac-gr00t-synthetic-manipulation): demo chia Teleop Demonstration → Data Generation → Data Augmentation, cùng sơ đồ kết nối các thành phần. Áp dụng cách để ví dụ và pipeline giải thích lẫn nhau.
- [Generalist GEN-1.5](https://generalistai.com/blog/gen-1.5): các cặp Physical prompt / Model rollout cho cùng tác vụ; tabs chọn ví dụ. Áp dụng quan hệ hình đầu vào–đầu ra và điều khiển chọn tình huống. Không chuyển cơ chế one-shot của Generalist thành tuyên bố về proposal.
- [MimicGen](https://mimicgen.github.io/): ví dụ đặt source demonstrations cạnh generated datasets ở các điều kiện khác nhau. Áp dụng cách cho thấy điều kiện thay đổi bằng ví dụ cụ thể; không nhận kết quả hoặc khả năng của MimicGen là kết quả đội.
- [EgoVLA](https://rchalyang.github.io/EgoVLA/): hình phương pháp, human prediction và các tác vụ benchmark. Tham khảo cấu trúc hình giải thích cơ chế; proposal vẫn dùng đường FluxVLA và robot adaptation đã mô tả trong hồ sơ.

## Vấn đề của bản trước

Ảnh robot và các hộp workflow đứng cạnh nhau nhưng người xem vẫn phải đọc và tự nối ý. Sơ đồ năm khối chưa cho thấy rõ loại dữ liệu, action model, controller, dấu vết lỗi và người quyết định. Video là bộ ảnh chuyển cảnh, chưa giúp thấy chuyển động gắp hụt / trượt vật. Chín cảnh và gallery tạo quá nhiều nội dung trước khi người xem hiểu điểm khác biệt.

## Bản mới

1. Sơ đồ có hình ở đầu: người làm mẫu / mẫu robot đích → khối học → runtime robot → phản hồi cho vòng phát triển tiếp theo. Ghi vai trò dữ liệu và phần đội xây.
2. Demo 3D humanoid 30 giây, sáu bước, hai tình huống gắp hụt / tuột vật. Có dừng–tiếp tục, chọn bước và đổi góc nhìn; phần xử lý bên cạnh đổi trọng tâm theo bước.
3. Hai nhánh sau kiểm tra: sửa hệ thống rồi lập lại baseline; hoặc xét gói dữ liệu phù hợp. Quyết định do kỹ sư duyệt, không tự chẩn đoán nguyên nhân từ một hình lỗi.
4. Bộ chín cảnh đầy đủ nằm trong phần mở thêm. Video 72 giây và bộ 18 cảnh vẫn tải được.

Demo 3D là chuyển động theo kịch bản, dựng bằng Three.js 0.160.1/MIT đã lưu trong website. Không chạy MuJoCo, không mô phỏng vật lý tiếp xúc, không gọi FluxVLA hoặc GR00T, không phải mô hình GR1 chính xác và không tạo evidence policy. Cảnh đặt đúng là kỳ vọng để giải thích lần đo lại. Render tĩnh khi không phát; dừng khi ẩn tab/chuyển trang; hủy tài nguyên khi đổi tình huống. WebGL không có thì giữ ảnh và chuyển động giải thích 2D.

Ảnh nguồn dùng built-in image_gen; prompts tại `content/story-image-prompts.json`, ảnh và storyboard tại `dist/assets/story/`. Không sao chép video/ảnh của các trang tham khảo vào demo của đội.

## Bổ sung task improvement · revision2

Ngay sau demo robot, người xem chọn năm tình huống: lỗi gắp, lỗi có thể bắt nguồn từ bước trước, cả task không thành công nhưng vẫn có bước làm được, chưa có kỹ năng nền, hoặc chưa đủ tín hiệu để chấm. Biểu đồ giữ riêng bước đạt, lỗi, chưa tới và chưa rõ; đi kèm phép kiểm tra nguyên nhân, kế hoạch thu dữ liệu và cách học. Nhánh lỗi hệ thống đã xác nhận luôn yêu cầu sửa hệ thống trước khi học.

Sơ đồ `assets/task-improvement.svg` mô tả vòng phát triển đầy đủ từ tiêu chí từng bước đến nghiệm thu toàn task độc lập. Website và hồ sơ dùng chung các ví dụ khai báo tại `content/task-improvement.json`; các số liệu và kết quả probe là minh họa theo kịch bản. Video 72 giây và demo 3D vẫn là phần giới thiệu, chưa diễn tả đầy đủ revision2 và không phải kết quả training. Cơ chế verifier, thu correction, bootstrap và training mới được đặc tả; chưa tích hợp với robot hoặc chạy thí nghiệm ML.
