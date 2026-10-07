# 13 · Example native từ đầu đến cuối: task A1

**Vai trò:** walkthrough triển khai đầy đủ, chưa native execution. Mỗi bước có input/output, kiểm lỗi và artifact. Reference contracts ở10 không thay native proof.

## 1. TaskSpec / binding

Instruction: lấy đúng linh kiện vàng trong miền cho phép, đặt vào A1, nhả/rút. Owner khóa vật/đích/domain/timeout/tolerances/sensors. Native config tham chiếu29D bao gồm arm/hand/waist; camera/order/units/state/action/dt/scheduler/controller profile và constraint một tay/torso cần kiểm. Unknown owner thresholds không điền thành “đã đạt”.

## 2. Seed và nguồn

Robot đích/expert seed với actual input/state/action/timing/outcome tạo baseline. Source audit human: RGB/pose/camera/confidence/rights và target frame; thiếu thì objective motion disabled. Synthetic: seed object-frame transform + simulator/controller execution; appearance chỉ kế thừa action sau QA; video-only không ground-truth robot action. Missing không zero-label.

## 3. Release QA

Roots/sessions/scenarios split trước variants, final không sinh dữ liệu/correction. Cùng profile không chỉ cùng tensor shape. Readback/camera alignment/timing/action normalization masks và outcome QA. Source fail → reject/quarantine/not-integrated, không training theo story đẹp.

## 4. Training

Processed image/tokens/state/embodiment/future-action masks → native selected head objective. Nếu flow matching, training velocity không final command. TrainingPlan khóa route gradients, actual trainable/frozen/optimizer, schedule/replay, normalization/stats và seeds. Human route chọn một hypothesis sau source/native pilot; không mặc định shared motor. Loss/newlabels không tồn tại trong forward thì chưa implementation.

Output: actual trainer receipt, loss/parameter manifests, weights/checkpoint revision, load/reload/inference parity. Kiểm GPU/memory/time từ batch thực; chưa có checkpoint ở môi trường hiện tại.

## 5. Closed-loop

Observation hiện tại/instruction → VLM features/masks → action expert với state/ID → normalized future actions → binding denormalization/scheduler → commands → measured response → independent scorer. Trace cả input, representation selected hooks, action/noise config, sent-command/horizon/timestamps, response. Chưa expose latent → not-observable; không invent semantic JSON.

## 6. Ví dụ lỗi: gắp được nhưng rơi lúc chuyển

Đây là scenario cần thử, chưa observed native failure. Chấm stage entered/known/unknown/not_attempted; first divergence có thể ở gắp trước. Health camera/mapping/normalization/latency/controller/reachability trước data hypothesis. Probe visual/goal representation cần labels độc lập; probe đúng không chứng minh ACT dùng, probe sai có thể probe yếu.

Test transition từ pose gắp chuẩn reachable so entry policy tự gây ra; ghi distribution/predecessors, không staged success thay fulltask. Alternative causes giữ trên EvidenceCard. Missing verifier → collect/annotate, không route training bằng confidence giả.

## 7. Chọn can thiệp

Controller/binding fault: repair ngoài source-only contrast, re-pin baseline. Coverage/contact hypothesis: expert correction với context/takeover/command/response nguồn rõ, hoặc sim execution khi fidelity hợp lệ. Visual hypothesis: basic augmentation trước expensive source khi QA labels giữ nghĩa. Human chỉ khi bridge/task relevance pass. Engineer duyệt plan/cap; auto update không có trong MVP.

## 8. Training candidate và regression

Replay prior robot data, targets valid và source schedule rõ; action-only/selected vision/interface/joint update là controlled trial theo question riêng, không infer neuron từ failure rate. Compare same-development conditions, full natural starts, transition readiness, đang-good conditions, costs/all failures. Local gain không là nghiệm thu.

## 9. Final và bundle

Freeze candidate/configs/scorer/binding/releases; independent final mới, all failures/timeouts/interventions vào denominator. Quality/uncertainty và cost đầy đủ mới claim robot-data/saving. Fail: report no-gain/reject hoặc round mới fresh holdout. Bundle có model/IO/controller/stats/licenses/traces/scoring/SOP/limits. Sim result không robot thật; real acceptance riêng.

## Những thứ đã có và chưa có

| Thành phần | Hiện trạng | Proof cần bổ sung |
|---|---|---|
| Reference release/train/reload/physics/scoring/gates | Executed, tests passed | Giới hạn4D/state idealized/weld/scripts ở10 |
| Native weights/loader/binding/scorer/rollout | Not-tested | P1 compatibility receipts + actual learned rollout |
| Native human route | Not-integrated | Source audit + target/module gradients + R/H downstream |
| Native synthetic generator | Not-integrated | Seed/controller port, traces/outcomes/QA/yield |
| VLM/ACT native evidence | Not-tested | Feature/action hooks + optimized parity + probes |
| Native quality-cost advantage | Not-established | Preregistered contrasts + independent final + ledger |

Đây là contract triển khai và checklist proof; không nói native đã chạy khi các receipts chưa có. Vòng nào còn thiếu artifact sẽ bị gate chặn thay vì truyền trạng thái pass ngầm.
