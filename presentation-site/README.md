# Website · Humanoid Data Flywheel

Bản nội dung ngày 09/10/2026, dựa trên hai PowerPoint còn giữ trong `deliverables/`:

- **Pitch v9**: thông điệp DENSO, đội, PoC Ψ₀ + SIMPLE / G1, chi phí và roadmap.
- **Visual Workflow v1**: dữ liệu, NVIDIA V2D, DreamDojo, training và flywheel. Thời hạn MVP cũ trong deck kỹ thuật không áp dụng; roadmap theo các mốc nghiệm thu của pitch v9.

Website có 13 trang. Mười một mục chính đi từ vấn đề đến workflow, dữ liệu, training, flywheel, đối chứng, chi phí, roadmap, mở rộng và đội. Hai mục paper/toolkit và reference nằm trong nhóm thu gọn; mục PowerPoint & hồ sơ đã bỏ. Ví dụ dataset và công cụ NVIDIA nằm trong Dữ liệu & V2D. Số liệu hiệu quả là **ước lượng có điều kiện**, không phải kết quả đo tại DENSO. Chưa chạy PoC Ψ₀ hoặc robot thật. Reference MuJoCo cũ vẫn có thể phát bản ghi, với giới hạn state lý tưởng, model thu nhỏ và grasp weld.

## Nguồn nội dung và cách sửa

| Thành phần | Nguồn | Hiển thị |
|---|---|---|
| Workflow, team, roadmap, nguồn paper, hai deck | `content/current-platform.json` | `dist/current-platform.js` |
| Giả định chi phí của pitch v9 | `content/current-cost-model.json` | Bảng tính trực tiếp trên trang chi phí |
| Hình tác giả gốc, attribution | `assets/platform/`, `assets/platform/sources.json` | Ψ₀, V2D, DreamDojo |
| Tệp PowerPoint tải về | Hai tệp được khai báo trong `current-platform.json` | `dist/assets/decks/` |
| Phạm vi, hash và text snapshot PPT | Sinh bởi `build-current-platform.py` | `dist/data/presentation-sources.json` |
| Điều hướng, trình đọc Markdown | `dist/app.js` | Mục lục và tài liệu lưu trữ |
| Reference đã ghi | `../examples/engineering-loop/results/` | `dist/engineering.js` |

`renderEngineeringPage()` ưu tiên `renderCurrentPlatform()` trên tất cả các trang hiện hành. Các renderer và tài liệu GR00T/FluxVLA trước đây được giữ để đọc lịch sử, không quyết định nội dung pitch hiện tại. Đặc biệt, ngân sách cũ trong `deliverables/DENSO-Cost-Model-2026-10-08.json` không phải mô hình của pitch v9; website dùng `content/current-cost-model.json` đối chiếu với slide 8/12/13.

Robot Learning đã có video Drive FOCA/SmolVLA trên RTX 3060 và repo Humanoid-RL. Đây là các dự án trước đây của đội, chưa là kết quả PoC Ψ₀ + SIMPLE hoặc DENSO. Số liệu fine-tuning theo video đội cung cấp; log và phần việc cụ thể đang bổ sung. Hai ảnh chụp nguồn được giữ trong assets/team và được crop khi hiển thị. Các mảng Simulation/Data vẫn chờ minh chứng riêng.

## Chạy và kiểm tra

```bash
python presentation-site/build-content.py
python presentation-site/verify-site.py
node presentation-site/test-presentation.js
node presentation-site/test-improvement.js
bash start-website.sh
```

Mở [website cục bộ](http://127.0.0.1:4175/#overview) và giữ tiến trình máy chủ chạy khi xem. Đây là bản xem trước trên máy, chưa xuất bản ra internet.

Build thực hiện offline: tái tạo hồ sơ cũ để giữ liên kết, rồi xuất nội dung hiện hành, chép hai PPT và năm hình gốc từ nguồn trong project. Manifest chứa SHA-256 để kiểm lại đúng phiên bản. `verify-site.py` kiểm các tệp, nguồn và hash. `test-presentation.js` kiểm nội dung 13 trang, phép tính, tình huống chi phí âm, quality gate và liên kết tài liệu; không thay thế kiểm tra trình duyệt.

Chỉ khi sửa code/physics/tests của reference mới chạy `python examples/engineering-loop/check.py` để cập nhật kết quả và hash. Không cần chạy lại training/reference chỉ để đổi website.

## Hồ sơ cũ và xuất bản sao

`dist/assets/idea-v3.1.zip` và `skill-a1-plan.zip` phục vụ hồ sơ/reference cũ, không phải recipe hiện hành. Các Markdown trong phần hồ sơ thu gọn có nhãn lưu trữ rõ ràng.

Nếu cần chuyển website sang máy khác, có thể dùng `python presentation-site/package.py --kind website`. Lệnh này tạo bản sao trong `deliverables/`; không cần chạy để xem website hoặc build bình thường. Giữ nguyên cấu trúc `dist/` khi chuyển sang một máy chủ static khác.
