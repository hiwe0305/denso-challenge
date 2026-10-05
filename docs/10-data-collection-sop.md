# 10 · SOP thu dữ liệu và sử dụng pilot

_05/10/2026 · Quy trình đề xuất để trial tuần 1–2; tolerances theo task/sensor phải được đo và chốt._

## Chuẩn bị

Task owner chọn skill và success criterion. Khai robot/controller/camera/action profile, active/locked joints, reachable workspace và allowed objects. Kiểm quyền quay/lưu/chia sẻ, làm sạch cảnh tránh identifiers không cần thiết. Chốt session/root IDs và clocks/calibration. Synthetic giữ parent/generator/scenario versions.

## Human ego capture

1. Chọn wearable/capture pipeline có video/timing và pose/geometry đủ cho recipe. RGB-only khai giới hạn.
2. Record task instruction, episode/session/operator ID được pseudonymize, scene/layout và calibration/version.
3. Quay thao tác có chủ đích trong miền robot có thể thực hiện; thu variation theo plan thay vì tùy tiện.
4. Check occlusion/camera motion/frame drops, tracking confidence nếu có; lỗi vào quarantine và ghi công reject/retake.
5. Lưu raw immutable, processor versions và measured/inferred signal flags.

## Real-humanoid teleop

1. Bound controller và operator có quyền thử, calibrated observations/state/action.
2. Capture issued commands và measured state/response theo schema; giữ reset/setup và intervention times.
3. Xuất LeRobotDataset version đúng loader của recipe. Check joint order/frame/units/fps/action meaning và episode outcomes.
4. Demo thành công, failures và corrections có role riêng; không coi failure là expert demonstration.

## Review/release

QA đọc sample trực tiếp, kiểm timestamps/NaN/units/provenance/rights. Group shared ancestors trước split. Lock OOD conditions và final test. Generate recipe views cho target adaptation và các human/video branches đã qua gate; readback one batch; immutable DatasetRelease và cost refs. Không tự điền action thiếu.

## Training và evaluation

Create ExperimentPlan/E1 và E4 T/F/A từ cùng R0; pin recipe/version/compute. E0 save-reload-rollout pass trước benchmark. Ghi usage và errors/retries. Development validation chọn checkpoint; final test chạy sau freeze. Report success/trials/uncertainty, demo count/minutes, total công/compute và confounds. Public khác robot chỉ smoke.

## Improve/infer/handoff

Failure signal → binding/health checks → hypotheses → one controlled change trên train/development → run và gain/no-gain. Không dùng final test làm feedback cùng vòng acceptance. Bundle checkpoint/normalization/camera/controller/config và SOP/report. Real inference phải thử hardware/latency/stop/rollback riêng; thiếu hardware giữ trạng thái chưa kiểm.

## Mở rộng SOP cho internet và synthetic

Internet: đăng ký provider/license và quyền sử dụng, task relevance, duplicates/roots, viewpoints/timing và signals. Video-only tạo observation view; pose inferred giữ confidence/mask. Ghi dữ liệu mới thật sự nhập riêng với prior đã có trong weights. Không scrape corpus chưa có quyền chỉ vì link public.

Synthetic: khai nhánh appearance/physics/world-model. Appearance phải kiểm semantics trước giữ action labels; physics chỉ release trajectory sau controller execution và task outcome; world-model video/pseudo-actions giữ generator/IDM revisions, confidence và lineage. Log generation/QA/reject compute. Tạo derivatives sau root splits, không để variant của holdout vào train. Teleop train/development roots tạo nhiều views nhưng số roots vẫn đếm hợp nhất; final-test riêng.

## Health và eligibility gates sau review

Bốn nguồn có SOP/catalog, không yêu cầu thu cả bốn cho mỗi skill. Khởi động robot baseline; recording/calibration/controller/camera timing/reachability fail thì sửa và đánh giá lại baseline trước data comparison. Trong E4 giữ binding/scorer cố định.

Với visual condition thử basic augmentation/reuse trước Cosmos; human/internet chỉ khi rights/signals/relevance và E0 đủ. Contact ưu tiên robot corrections sau health checks; physics chỉ sau fidelity/controller/scorer gate. Đăng ký T/F/A packages, acquisition và total incremental caps; planning/selection/QA/reset/reject/licensing/generation đều ghi theo activity. Unknown cost không tự thành0; gói không đủ evidence/cap thì defer/pilot nhỏ. Final OOD giữ riêng.

Handoff thêm engineer/operator/robot/GPU-hours, elapsed time tới acceptance, cyclep50/p95, interventions/1000, recoveryminutes và acceptedoutputs/hour. Chưa robot thật: ghi sim-only; không gọi PoC thresholds là production acceptance.
