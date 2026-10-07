# 01 · Task và native baseline

## Task A1 đề xuất

Linh kiện cứng dạng hộp vàng, geometry thử40×25×15mm. Vùng đích A1 có mặt trong80×60mm. Cùng một robot GR1, camera/profile/timebase được pin; lấy đúng vật, đưa vào đích, bỏ vật rồi rút tay. Miền object/target positions phải được giới hạn bằng expert reachability/contact replay trước training.

MVP không yêu cầu yaw cụ thể. Thành công khi footprint thật của vật nằm hoàn toàn trong vùng A1, vật tự ổn định trên mặt đỡ, không còn contact tay–vật và tay đã rút. Nhờ vậy “đặt đúng” có predicate hình học thực, không chỉ nhìn ảnh đẹp. Vật/đích, độ sâu khay và mặt đỡ phải có geometry thật khi port task.

Defaults để pilot: deadline30s, object đứng yên2s sau nhả, tốc độ vật≤5mm/s, hand anchor cách vật≥50mm sau rút. Các defaults phải kiểm với simulator/timebase và owner trước freeze. Chưa có final acceptance sản xuất.

Task cần object pose/geometry, target frame/support plane, hand anchor transform và native physical contact information cho scorer. Privileged sim state chỉ cấp cho scorer; policy chỉ nhận các observations/state mà native binding cho phép. Không dùng weld/proximity attachment của reference làm contact proof GR1.

## Các mốc đo được

| Mốc | Entry | Predicate cần kiểm | Nếu thiếu tín hiệu |
|---|---|---|---|
| Tiếp cận | Episode bắt đầu | Hand anchor vào vùng tiếp cận hợp lệ của vật đúng ID; vùng này chốt từ expert replay | Unknown nếu pose/link/calibration không hợp lệ |
| Gắp & nâng kiểm giữ | Sau tiếp cận, đã có thao tác contact/nâng | Vật đúng ID nâng khỏi support≥20mm, contact tay–vật hợp lệ và motion coupling ổn định trong window0,3s | Unknown, không suy “đã gắp” chỉ từ finger close |
| Chuyển & đặt | Đã kiểm giữ | Vật đi tới A1 và footprint nằm trong vùng; response cho thấy support hợp lệ | Unknown khi mất object tracking/contact/support information |
| Nhả & rút | Vật đã vào A1 | Không còn contact tay–vật, hand clearance đạt và vật vẫn đúng đích/ổn định2s | Unknown nếu thiếu readback/verifier |

Gắp và nâng được gom thành một mốc kiểm giữ để tránh xác nhận grasp từ một lệnh đóng tay. Ngưỡng motion coupling và contact mapping phải calibration, chưa gán số giả. Đây là milestones cho analysis, không symbolic sequencer điều khiển native policy. Bước đã pass vẫn là historical pass nếu sau đó rơi vật; full-task fail và trace ghi thời điểm rơi. Kết quả full-task là authoritative acceptance, không tổng điểm các bước.

Not-entered = chưa tới; active = in_progress; missing verifier = unknown; deadline/abort = full-task fail. Không lấy unknown làm success hoặc bỏ khỏi task denominator. Khi verifier lỗi, dừng lượt thử theo runtime profile để tránh tiếp tục dùng score sai.

## Native compatibility trước A1

Task upstream được chọn để kiểm loader/controller: `gr1_unified/PosttrainPnPNovelFromTrayToPlateSplitA_GR1ArmsAndWaistFourierHands_Env`. Nó có trong task list của [config FluxVLA tham chiếu](https://github.com/FluxVLA/FluxVLA/blob/main/configs/gr00tn15/gr00tn15_eagle_3b_robocasa_30_eps_full_finetune.py), chưa được chạy tại đây. Pin exact code/weights/env trước dùng. Task này khác A1; chỉ dùng compatibility smoke test, không đổi tên kết quả thành A1.

Binding tham chiếu là action29D, chunk16; padding32 chỉ là representation của selected head. State/action order, units, absolute/delta, statistics, observation preprocessing và control dt lấy từ pinned implementation + readback. Không biến bốn Cartesian channels reference thành native action bằng padding. Không ép waist/tay không dùng về0; constraint một tay/torso chỉ mở nếu seed/controller/data semantics tương thích.

## Chuỗi receipts baseline R

1. Loader: dataset windows có image/token/state/action masks, đúng profile, source roots và timebase. Missing không zero-fill.
2. Một robot batch: loss finite, actual trainable/frozen parameters/optimizer được ghi, gradients và parameter update có thật. Freeze LLM / tune selected visual modules chỉ sau đối chiếu pinned config và actual requires_grad.
3. Save/reload: checkpoint hashes, preprocessing/stats/profile, predictions trước/sau reload ở cùng inputs và sampling seed. Sai parity → sửa trước rollout.
4. Upstream closed-loop smoke: action chunk→denormalized command→controller→measured response; independent outcome. Sau đó A1 expert replay và learned rollout.
5. Useful R baseline: natural starts trên development; báo toàn bộ fail/unknown. Nếu model chưa usable thì sửa integration hoặc seed/curriculum trong budget; chưa làm source study.

Trace tối thiểu có episode/scenario/root/checkpoint/config IDs, input times/preprocessing, VLM output shape/masks/hook refs, ACT state/ID/final chunk/sampling seed, command order/units/queue/send, measured response, scorer outcomes. Model không expose boundary nào thì ghi not_observable. Debug vs optimized inference phải có parity; hook Python không tự chứng minh accelerated path được quan sát.

Batch size, LR, training steps và capacity chọn từ one-batch memory/time benchmark và development; không copy max_steps upstream thành cam kết. Ghi các lựa chọn trong RunPlan trước final. Không có receipt thì status chưa chạy.
