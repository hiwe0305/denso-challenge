# 11 · Contracts bắt buộc, không chỉ sơ đồ

## Native batch contract (cần instantiate từ pin config)

Images/views/masks, language tokens/masks, state schema, embodiment ID, action chunk/masks, timestamps/profile/source/root/split. Khóa dimensions/dtype/token layout/units/frame/action absolute-vs-delta/order/dt/horizon/normalization revision. Selected config29D/chunk16 là reference, task binding chưa pass; không coi batch đúng shape là controller-compatible.

Rights/validity và provenance theo03. Human labels dùng human objective/adapters riêng; không pad giả robot29D để gọi native action loss. Per-source gradient/update manifest: trainable params, frozen params, actual gradients/update hashes, optimizer groups, loss scaling/masks, mixing/replay schedule. Missing target không zero-fill.

## Native inference contract

Same preprocessing/action statistics/profile như train; future labels không future input. Actual VLM feature refs/masks → selected ACT/state/ID → normalized chunk → denormalize/order/clipping → scheduler executed horizon → controller/state. Model/API không expose tensors thì status not_observable; không fabricate semantic output. Optimized/debug paths parity required.

## Runtime trace

Episode/scenario/split/version; observation and processing refs/times; model/config/checkpoint; predicted vs sent action and normalization/clipping; command/queue/send/response timestamps; measured state/contact if available; scorer/version/outcome/unknown; intervention authority; trace hash. Controller fault outside data-only arms.

## Reference contract đã chạy

Feature35; command4 absolute world xyz meters + grip threshold0.5; dt0.05s; profiles explicit; project-authored rights; finite values; monotonically increasing step per recording; train scenario không final-*. Pose rate limit0.035m/control step; attachment khi closed và proximity<0.026m; weld/contact simplification công khai. Reference stable0.6s; native thresholds không kế thừa.

Scorer riêng từ measured world state; policy sequencer own-stage không đọc scorer status. Fit35×4 closed-form ridge, MSE; checkpoint reload numeric parity. Seed/variant/correction IDs và ancestor roots; sim descendants không independent robot seed roots. C replay R + correction, S replay R + transformed/executed variants; hai alternatives, không tự train C sau S đã tốt.

## State transitions và rejection

release_draft → QA_pass → frozen_release → trained_candidate → reload/runtime_pass → development_checked → frozen_candidate → independent_final → promote/reject(scope). Reference promote chỉ scope reference. Rights/profile/geometry/missing/leakage fail → reject/quarantine. Unknown verifier → unknown; fulltask timeout fail. Local correction gain nhưng final fail → reject; nguồn missing → not_integrated.

## Nội dung example không được xuyên tạc

Scorer giữ privileged state để chấm; reference policy cũng có idealized state vì declared test profile. Native image policy không được nhận privilege đó ngầm. Reference model/encoder/sequencer khác native architecture. Một example kiểm plumbing không kiểm perception/language/human-transfer/costs của model lớn. MuJoCo run không robot thật.
