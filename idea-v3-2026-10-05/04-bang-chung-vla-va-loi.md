# 04 · Evidence → hypothesis → intervention → evaluation

## Dữ kiện cần có

Input: raw/processed frame refs/hash, prompt/tokens/masks, resize/crop, time/calibration/state. VLM/IFACE: selected features/masks/layer/config/shape/dtype và validity; model không exposure thì not_observable. ACT: conditioned state/ID, sampling seed/config, normalized final actions; denoising/vector field khi debug. EXEC: unnormalized/order/clipping/queue/send/horizon và response. SCORE: stage entry/pass/fail/unknown/reach + fulltask. EVID: alternative hypotheses, tests, engineer decision và refs.

Native traces chưa thu. Reference ghi numeric features của idealized adapter và predictor outputs, không gọi chúng là VLM latent. Website replay đo được từ artifacts; không chạy training/model ở browser.

## Representation probe

Probe object/goal/held-state có independent labels, split/scenario và baseline controls. Probe correct chỉ chứng minh có thông tin đọc được; chưa action expert dùng. Probe wrong có thể probe yếu. Attention/feature anomaly/gradient norm/text explanation không tự calibrated cause. Latent vision-language, latent-action video labels và state/action embeddings là các loại khác nhau.

Instrumentation offline/selective trước; đo overhead/parity. Future-frame supervision chỉ offline, không lén đưa future input vào online policy.

## Quy trình khi fail

1. Reproduce pinned policy/data/profile/scorer/timeline.
2. Camera/input/normalization/mapping/controller/reachability health trước thiếu-data hypothesis.
3. First divergence và predecessors: fail chuyển có thể do gắp lệch.
4. Controlled probes: reachable clean vs policy-induced entry; recording distributions/cost. Không chỉ lấy staged success.
5. Engineer chọn repair/data/reuse/augmentation/update/defer; chưa utilities thực thì pilot nhỏ trong cap.
6. TrainingPlan khai modules/loss/targets/ratio/context/optimizer; prior replay.
7. Same conditions + full natural starts/regression; freeze candidate rồi final độc lập.

Update-scope trials (action-only/selected vision+interface/joint) là experiment, không rule “gắp lỗi thì train action expert”. Giữ comparator/compute/development labels; thêm jobs/cost. Không bắt model sửa bằng training nếu binding sai.

## Stage/count semantics

Entered known: pass/(pass+fail), đồng thời unknown/entered và reach. Chưa tới bước not_attempted, không fail. Missing verifier unknown, không pass. Retry attempts khác episodes. Đang thực hiện là in_progress, chỉ deadline/abort kết thúc attempt thành fail. Timeout/abort là full-task fail. Scorer không dùng auxiliary stage head của policy làm ground truth.

## Zero success / no basic skill

Có local progress: probe transitions/corrections gần policy states. Fail ngay đầu: health và useful parent trước, expert seed/curriculum trong cap. Unreachable/physics/gripper sai: repair/rescope. Verifier thiếu: annotate/collect. Cap hết/no gain: stop/defer; không thêm modules vô hạn. Model/task/binding thay phải re-pin comparator và final plan.

## Example evidence đã chạy

R fail approach, bước sau not_attempted. S sửa development và giữ regression. C correction sửa development nhưng final0/12 → không promote. Binding fault làm predicted khác sent command → health route. Withheld verifier sensor → grasp unknown; reference runtime gate dừng stage advance, không thực hiện lift/transfer. Zero weights → approach fail, không gán fail mọi bước. Những facts này thuộc reference, chưa native module diagnosis.
