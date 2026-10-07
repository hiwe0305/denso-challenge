# 03 · Example xuyên suốt: gắp được nhưng rơi lúc chuyển

**Đây là scenario cần kiểm, chưa là episode native đã quan sát.** Các ô measurement/artifact dưới đây hiện pending, không tạo số hoặc semantic output giả để lấp trace. Khi có episode thật, cùng IDs nối từ đầu tới cuối.

## Lượt chạy E0

Input là RGB thực của episode, instruction A1 và proprio/state theo native profile. VLM tạo selected features/masks. Action Expert conditioned bằng features/state/ID tạo final normalized action chunk. Binding đổi thành commands theo normalization/order/timebase; controller thực thi; scene/readback cung cấp object/hand/contact states cho scorer.

Giả sử trace tương lai cho thấy vật đã nâng rồi rời tay trước khi vào A1. Full-task fail. Mốc trước đã pass vẫn giữ historical status; các bước chưa tới không bị tính fail. Không coi rơi ở bước chuyển là bằng chứng chỉ cần train transition.

| Boundary | Bằng chứng phải điền từ E0 | Không tự suy ra |
|---|---|---|
| Input | Frames/raw+processed refs, prompt, state, calibration và clocks | Ánh sáng khác nghĩa là perception sai |
| VLM/interface | Hook/layer/version, actual feature refs/shape/masks/validity | JSON ý định nếu model không xuất; latent = giải thích nhân quả |
| Action Expert | Conditioning, seed/noise config, final chunk, horizon và native stats | Training vector field = command |
| Execution | Predicted→sent mapping/clipping/queue, timestamps và measured response | Robot làm giống prediction nếu chỉ có log model |
| Outcome | Object/contact trajectory, step entry/pass/fail/unknown, first divergence | Bước chưa tới = fail; thiếu sensor = pass |

## Ba giả thuyết cần phân biệt

| Giả thuyết | Phép kiểm | Hành động khi có bằng chứng phù hợp |
|---|---|---|
| Binding/controller/timing làm sai action | Replay cùng chunk qua pinned binding; so predicted/sent/readback và native expert command response | Repair/re-pin; lập lại baseline trước data contrast |
| Pose gắp do bước trước chưa đủ tốt | So chuyển từ expert grip reachable và từ grip policy tự tạo; giữ điều kiện/controller và ghi entry distribution | Thu correction có context tiếp cận→gắp→nâng/chuyển; không chỉ đoạn cuối |
| Coverage cho transport/contact còn thiếu | Expert grip vẫn chưa giải quyết; kiểm actual trajectory/contact, source coverage và controlled scene variants | Thử positive sim execution hoặc expert correction; recipe/update theo evidence |

Probe VLM trên independent labels có thể giúp kiểm representation hypothesis. Nó không thay command/response checks và không định danh nguyên nhân tự động. Mỗi phép kiểm phải lưu alternatives, kết quả và giới hạn. Clean-grip staged evaluation là diagnostic, không thay full natural-start task evaluation.

## Quyết định và training candidate

Engineer ghi EvidenceCard gồm observed facts, hypotheses, test refs, decision và collection mode. Nếu chưa phân biệt được giả thuyết, status defer/collect evidence. Không chọn nhánh data sẵn.

Nếu chọn S: lấy training seed/context phù hợp, sinh và thực thi trong train domain, giữ accepted/rejected traces. Nếu chọn correction: expert takeover hoặc expert-reset được ghi đúng mode; desired command và measured response đều có provenance. Policy failure action không tự là positive target. Intervention làm thay đổi source/study question phải được version riêng; không nhập correction vào R+S contrast rồi vẫn gọi là source-only effect.

Candidate train cùng parent đã pin, replay prior data theo recipe, loss/module route đã kiểm. Không dùng failure rate để quyết định neuron hoặc “chỉ train VLM/chỉ train action”. Action-only/vision/joint scope là controlled development trials khi có giả thuyết và budget, không chạy cả ba mặc định.

## Đo lại E1

Đo case lỗi trên development, các điều kiện trước đó tốt, transitions và toàn task từ natural starts. Nếu chỉ sửa được E0 mà regression hoặc full-task kém, không nhận cải thiện. Nếu có gain development, freeze candidate/config/scorer/releases rồi dùng final mới giữ riêng. Final fail được báo; không train tiếp trên cùng final rồi gọi là độc lập.

## Nếu fail từ đầu đến cuối

Không quy tất cả stages thành fail. Kiểm health/feasibility/verifier trước. Nếu native mapping/scorer sai: repair. Nếu chưa có basic skill nhưng expert replay feasible: bổ sung expert seed/curriculum trong cap, tính công vào total cost. Nếu expert cũng không thực hiện được hoặc physics/gripper không phù hợp: sửa binding/task scope. Không thiếu kỹ năng nền bằng cách sinh nhiều video không có valid actions.

Cap/no-gain: dừng source trial và lưu no-gain, giữ comparator/version để có thể đọc lại. Không mở thêm module vô hạn.

## Recovery trong một episode: extension có gate

Chỉ mở khi TaskSpec cho retry và verifier phát hiện failure đủ tin cậy. Thu expert demonstrations từ reachable post-failure state đến corrected grasp và full-task completion, giữ observation/context/timing/takeover authority. Failure prefix giữ role failure; không biến policy failed actions thành positive imitation targets. Recovery có thể nằm trong cùng policy, chưa cần một model riêng.

Đo first-attempt success, eventual success trong cùng deadline, attempts/episode, cycle time và intervention. Retry không tạo thêm independent episodes. Recovery/scorer/cycle chưa đạt thì giữ ngoài acceptance. Đây là proposed branch, chưa có native recovery recordings.

## Bộ example để trình bày (artifacts)

Một episode thất bại + timeline năm boundaries + một phép kiểm có kết quả + approved plan + dataset release + new checkpoint + development comparison + final report. Mỗi vật liệu có cùng task/profile, episode/scenario/root/model IDs và link receipt. Native artifacts chưa có thì cảnh mang nhãn proposal; animation không đóng vai kết quả.
