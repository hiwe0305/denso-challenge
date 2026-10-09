# Humanoid Data Flywheel

Hệ thống đề xuất giúp đội AI/robotics phát triển kỹ năng robot bằng human video, synthetic trajectories và demonstrations robot đích, kèm bằng chứng để chọn cách cải thiện. Mục tiêu là giảm công thu dữ liệu và tổng chi phí ở chất lượng được thống nhất.

**Bản trình bày hiện hành: [Pitch v9](deliverables/DENSO-ilovephysicalintelligence-Pitch-2026-10-09-v9.pptx).** Website ngày 09/10/2026 kết hợp pitch này với [workflow kỹ thuật](deliverables/DENSO-Platform-Visual-Workflow-2026-10-08-v1.pptx). [IDEA.md](IDEA.md) và các hồ sơ engineering trước đây được giữ để đối chiếu lịch sử; recipe hiện hành là Ψ₀ + SIMPLE / G1.

**Mở website:** chạy `bash start-website.sh` trong thư mục project, rồi mở [website cục bộ](http://127.0.0.1:4175/#overview). Giữ cửa sổ chạy website mở trong lúc xem; nếu máy chủ đang chạy thì chỉ cần mở đường dẫn.

## Tài liệu và sản phẩm còn giữ

- [Kế hoạch triển khai Skill A1](docs/implementation-plan/skill-a1/README.md): task, data/training recipes và phép đo chi tiết.
- [Hồ sơ engineering](idea-v3-2026-10-05/README.md): contracts, nguồn và bằng chứng reference.
- [Reference code và kết quả](examples/engineering-loop/README.md): một bản code/results duy nhất trong repository.
- [Đối chiếu video và nguồn số liệu](docs/research/video-zKaeODg7xeE-2026-10-06/README.md).
- [PowerPoint trình bày mới nhất](deliverables/DENSO-ilovephysicalintelligence-Pitch-2026-10-09-v9.pptx).
- [PowerPoint workflow kỹ thuật để bổ sung website](deliverables/DENSO-Platform-Visual-Workflow-2026-10-08-v1.pptx).
- [Website và cách chạy](presentation-site/README.md).
- [Phản hồi nhận xét kiến trúc và quyết định cập nhật](docs/reviews/architecture-feedback-response-2026-10-06.md).
- [Data Core flywheel](idea-v3-2026-10-05/03-workflow-du-lieu.md): execution → evidence → acquisition → QA → training → evaluation; mở trên website tại `#architecture`.

Reference MuJoCo đã kiểm luồng engineering với các đơn giản hóa được công bố. PoC Ψ₀ + SIMPLE, human transfer và mức tiết kiệm của nhóm còn cần thử nghiệm. Số liệu nghiên cứu trong IDEA.md là cơ sở cho đề xuất, không phải kết quả project.

Các ZIP xuất dư, ảnh xem thử cũ và cache dựng đã được dọn. Hồ sơ technical, tài liệu nghiên cứu, PowerPoint và snapshots đang dùng để build website được giữ; Pitch v9 và website là điểm vào để đánh giá idea. Chỉ tạo ZIP khi cần gửi sang máy khác; hướng dẫn nằm trong README của website.

Training review và schema hiện hành: [Dataset → training → evaluation → inference](idea-v3-2026-10-05/15-dataset-training-blueprint.md), khảo sát 7 VLA/WM recipes; [catalog](docs/11-method-survey.md).
