# Idea v3.1 · Pipeline dữ liệu và cải thiện kỹ năng robot

**Hồ sơ engineering · 05/10/2026.** Bản trình bày để gửi đánh giá hiện tại là [IDEA.md](../IDEA.md); recipe Skill A1 mới nhất nằm ở [kế hoạch triển khai](../docs/implementation-plan/skill-a1/README.md). Các bản lịch sử đã được dọn; folder này giữ đặc tả kỹ thuật và bằng chứng reference.

> Từ pretrained VLA, dùng dữ liệu đủ tín hiệu để học một kỹ năng robot; chạy policy, ghi bằng chứng, bổ sung dữ liệu/can thiệp phù hợp và kiểm toàn task. Mục tiêu là ít robot collection và tổng chi phí thấp hơn **ở cùng chất lượng**, không phải nhiều video hơn.

## Hiện có gì thực sự chạy?

**Đã chạy một reference pipeline trong MuJoCo:** expert seed → biến đổi waypoint → thực thi → QA → học action predictor → checkpoint/reload → closed-loop → evidence → correction/replay → so tập giữ riêng → gate nghiệm thu.

Reference sử dụng Cartesian mocap effector, grasp bằng weld, adapter đọc idealized scene state, sequencer theo kịch bản và model tuyến tính được fit thật. Đây là kiểm chứng engineering của reference pipeline; **chưa FluxVLA/GR00T, chưa GR1, chưa VLM, chưa human transfer, chưa gripper contact chính xác hoặc robot thật.**

Đường native vẫn là FluxVLA / GR00T N1.5 / GR1 sau compatibility gate. Không đổi model/robot đích để lấy kết quả reference làm kết quả native. CUDA không khả dụng trong lần kiểm môi trường; checkpoint native chưa có. Native có thể chạy trên môi trường khác khi đủ dependencies/weights và binding, chưa thử ở đây.

## Đọc để hiểu và triển khai

| File | Nội dung |
|---|---|
| [01 · Idea và phạm vi](01-idea-va-pitch.md) | Vấn đề, đầu ra, giá trị và giới hạn |
| [02 · Kiến trúc](02-kien-truc-va-cach-hoc.md) | Training / inference / evidence; gradient và action semantics |
| [03 · Dữ liệu](03-workflow-du-lieu.md) | Nhãn, transforms, QA, lineage và split |
| [04 · Xử lý lỗi](04-bang-chung-vla-va-loi.md) | Bằng chứng, probe, data/update plan và cold start |
| [05 · Kiểm chứng](05-thiet-ke-kiem-chung.md) | Source contrasts, regression, freeze, final và claim |
| [06 · Chi phí](06-chi-phi-va-kha-thi.md) | Activity ledger, measured/unknown và resource gates |
| [07 · Đánh giá/quyết định](07-danh-gia-va-quyet-dinh.md) | Rủi ro có anchor; thay đổi v3 → v3.1 |
| [08 · Triển khai](08-ke-hoach-trien-khai.md) | Việc phải làm, artifact, người duyệt và stop conditions |
| [09 · Nguồn](09-nguon-va-bang-chung.md) | Tiền lệ khoa học; không gán kết quả tác giả cho đội |
| [17 · Model Engine Core](17-model-engine-core-fluxvla.md) | Vì sao chọn FluxVLA: training → eval → robot thật; modules/config/artifacts và mapping flywheel |
| [16 · Model AI](16-model-ai-va-data-flywheel.md) | Policy nền, supervision/loss/gradient scopes và model interventions |
| [15 · Dataset và training blueprint](15-dataset-training-blueprint.md) | Khảo sát 7 VLA/WM recipes, file schema, targets/loss/modules và end-to-end protocol |
| [13 · Example native từng bước](13-example-native-tu-dau-den-cuoi.md) | Input/output, error paths và proof cần có cho task A1 |
| [10 · Example toàn luồng](10-example-chay-toan-he-thong.md) | Bản chạy thật, input/output và kết quả từng nhánh |
| [11 · Contracts và logic](11-contracts-va-logic.md) | Hợp đồng dữ liệu/model/runtime; từ chối inputs sai |
| [12 · Kiểm chứng nội dung](12-bang-kiem-chung.md) | Claim → artifact/test → phạm vi |
| [project-spec.json](project-spec.json) | Một bản khai scope/profile/status để kiểm máy và docs |

![Kiến trúc và mức bằng chứng](assets/kien-truc-v3.png)

[SVG gốc](assets/kien-truc-v3.svg). Native walkthrough ở13. Phép thử reference dưới10 là phụ lục kiểm plumbing; số C0/12 không kết luận về correction trên VLA. Code/results dùng bản duy nhất tại [examples/engineering-loop](../examples/engineering-loop/README.md); website ZIP thêm bản portable khi xuất.

## Quyết định được giữ

- Một kỹ năng/robot/model trước. Robot baseline và controller/scorer hợp lệ là điều kiện đầu.
- Human và synthetic là nguồn có thể giúp tiết kiệm; phải kiểm từng nguồn. Không bắt mixture dùng đủ nguồn.
- Human RGB-only không có robot-action loss nếu thiếu target. A1 common-wrist/shared motor là custom candidate, chưa native integrated; action-free future route là candidate khác và schedule cần kiểm.
- Synthetic execution ghi actions/state/outcomes trong sim. Appearance kế thừa nhãn có QA; neural video có action-free future route hoặc pseudo-label extension riêng.
- Evidence phục vụ engineer. Không tự quy lỗi cho VLM/action expert hoặc tự update model sau fail.
- Same-quality + total-cost là tiêu chuẩn hiệu quả. Reference 12 trials không chứng minh savings/human/native VLA.

## Điểm sửa quan trọng so với v3

V3 đã chọn shared human motor trunk và grid 27 jobs quá sớm. V3.1 hạ các lựa chọn đó về giả thuyết có gate, bổ sung schema/loss/gradient/runtime contracts và một example thực thi. Mục tiêu vẫn giữ, thay đổi mức cam kết và thứ tự kiểm. Không mở một platform interpretability hoặc foundation-model training riêng.

- [16 · Model AI × Data Core](16-model-ai-va-data-flywheel.md): backbone, module inputs/outputs, training phases, loss/gradient scopes, World Model roles và inference.
