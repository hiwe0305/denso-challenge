# Task hai bàn qua vòng Failure → Data: chẩn đoán và kế hoạch dữ liệu

_**[Đề xuất]**, 11/11/2026. Story [DA-26](../product/stories/DA-26-thi-nghiem-he-egocentric.md) nhiệm vụ 8. Hiếu chọn (11/11/2026) "chẩn đoán + kế hoạch dữ liệu", không train lại trước demo. Nguồn: [spec v10.5](../spec-v10-failure-to-data.md) mục 5, 6; [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 10; [S1-03 `psi0-eval.md`](../g0/psi0-eval.md) mục 3.6; [HE-1](he-1.md) mục 7.1; [trace](../g0/trace.md). Không có job GPU, Colab hay train nào được chạy cho file này._

## 0. Kết luận và mức tin cậy

1. **Hệ thống chưa cho phép tiêu ngân sách dữ liệu cho task hai bàn.** Các lượt Isaac của task hai bàn không ghi trace từng bước, nên R3, R5, R6 không kiểm được. Theo spec mục 6.4, 6.9 và hợp đồng `EvidenceCard` (DA-39), mọi episode hỏng vì vậy là **CHƯA RÕ**. Can thiệp duy nhất được phép là `repair_ticket`: ghi lại trace rồi chẩn đoán lại. Đây là kết quả đúng của thuật toán, không phải lỗi của nó: hệ thống trước, dữ liệu sau.
2. **Bảng lỗi theo bước** (đọc từ video, chưa qua scorer) có 8 episode hỏng trong 14 lượt Isaac. Có 6 ca hỏng ở bước **đặt** (bước 5): 4/4 ca của checkpoint tác giả và 2/4 ca của checkpoint N20. 2 ca còn lại hỏng ở bước **gắp** (bước 2), cùng một điều kiện, cả hai nhánh N20.
3. **Nếu hệ thống sạch**, cụm "đặt" của checkpoint tác giả chỉ có thể ra TRẠNG THÁI ĐẦU XẤU hoặc KỸ NĂNG YẾU. Điều kiện eval `e78fb93` mức 0 trùng episode train, nên THIẾU VÙNG PHỦ bị loại. Vì vậy loại dữ liệu cần thu là **teleop** (dữ liệu phục hồi hoặc correction ở bước đặt), không phải synthetic hay egocentric. Đội chưa có đường thu teleop nào cho task này: không có PICO, thiết bị bàn phím (DA-16) chưa làm, SIMPLE không có MP datagen cho task hai bàn.
4. **Không đo được hiệu ứng trước demo.** Lợi ích kỳ vọng theo prior là 20 điểm % trên 10 điều kiện mức 0 (chưa đo). Để thấy +20 điểm % với power 80%, cần khoảng 85–100 điều kiện mỗi nhánh: 190–480 CU và 100–250 giờ client Isaac. Số dư Colab sau HE-1 là 38,42 CU (5/11/2026).
5. **Mức tin cậy: thấp.** Có 10 + 4 lượt Isaac, n nhỏ, CI rộng: 6/10 có Wilson 95% [31%, 83%]; 0/4 của N20 có [0%, 49%]. Bước hỏng đọc bằng mắt từ video 16 khung, chưa có tín hiệu scorer. Ngưỡng hệ thống còn là giả định. Kết luận 1 chắc chắn, vì nó suy từ quy tắc. Kết luận 2 và 3 là giả thuyết, phải kiểm lại khi có trace.

## 1. Rollout đã gom

Lượt Isaac (`mujoco_isaac`, MuJoCo vật lý, Isaac render) là bằng chứng chính. Lượt `mujoco` chỉ để đối chiếu, vì `mujoco` không render đúng cảnh mà checkpoint đã học (S1-03 mục 3.6: Isaac 6/10 so với `mujoco` 3/30, p = 0,003).

| Lượt | Checkpoint | Điều kiện | Đồng hồ | Kết quả | Thư mục trên laptop (`fwdata/`, ngoài git) |
|---|---|---|---|---|---|
| S1-03 Isaac, 4/11/2026 | Tác giả `…betweentablesteleop-v0…b64.gpus4.2604081126` `ckpt_40000`, `psi-model` `cb1480f` | `e78fb93` mức 0, episode 0–9 | Wall | **6/10** (đạt 0, 1, 2, 3, 7, 8) | `simple/s103/runs/simple-b75c678/eval-e78fb93/mujoco_isaac/level-0/pass-1/ep0-9/` (42 MB) |
| HE-1 lần 3, 5/11/2026 | V-EGO và V-NOEGO, N20, seed 0 (`rp_95c98a476499`) | Bộ dev mức 0, seed 1000100–1000101, xen kẽ theo cặp | Sim | **V-EGO 0/2, V-NOEGO 0/2** | `archive/da26-launch-b3-fwdata/he/runs/da26-t2-eval-n20/` (44 MB) |
| S1-03 `mujoco`, 4/11/2026 (đối chiếu) | Tác giả | `e78fb93` mức 0, 0–9 | Wall, sim | 2/10, 1/10 | Trên `rtx3060`, bản lưu trữ `~/denso-qaqc-archive/rtx3060/2026-11-08-group3/denso-s103/fwdata/simple/s103/runs/simple-b75c678-clock-{wall,sim}/eval-e78fb93/` (thư mục `~/denso-s103` đã dọn) |
| DA-38 `mujoco` có trace, 5/11/2026 (đối chiếu) | Tác giả | `e78fb93` mức 0, 0–1 | Wall | 0/2 | **Đã mất**: thư mục trên `rtx3060` đã dọn, bản lưu trữ `~/denso-qaqc-archive/rtx3060/2026-11-07-groupA/denso-da38` rỗng; chỉ còn số đo trong [`trace.md`](../g0/trace.md) |

Cả hai lượt Isaac dùng image SIMPLE ghim `38a6…`, file task `b75c678`, server Ψ₀ `--action-exec-horizon 24 --rtc` (d = 6, `rtc_max_delay` 8 theo `/info`). Episode thành công kết thúc sau 11,5–14,0 s mô phỏng. Episode hỏng chạy hết 1 200 bước (24,02 s, 1 201 khung).

**Hash** (sha256, 12 ký tự đầu; tính lại 11/11/2026). Bản sao `raw-…` của HE-1 kiểm lại `sha256sum -c SHA256SUMS`: tất cả OK.

| File | sha256 |
|---|---|
| S1-03 `eval_stats.txt` · `summary.json` · `client.log` | `8eb1a3431df7` · `e7dddc282d2d` · `3b1d76ad1cce` |
| S1-03 `videos/episode_{4,5,6,9}/head_stereo_left_failed.mp4` | `29ee4758072f` · `058a728efe7f` · `744e7d0b0760` · `c2dab6620c38` |
| S1-03 `videos/episode_{0,1,2,3,7,8}/head_stereo_left_success.mp4` | `850ab3beb013` · `58cfcb285b93` · `239ee3930e94` · `571032d2858f` · `d263465eb1c4` · `ef6bf4bccfad` |
| HE-1 `route.jsonl` · `order.json` · `MANIFEST.md` | `9870215d13f9` · `6d7644787467` · `8d53bb3ddee2` |
| HE-1 `client/raw-da26-t2-eval-n20-20261105T140750Z/SHA256SUMS` · `…/eval_stats.txt` | `532b1f3c62b9` · `6d84a2c430b5` |
| HE-1 `raw-…/videos/episode_{0,1,2,3}/head_stereo_left_failed.mp4` | `4176644bb572` · `abdab4d4544b` · `bc823d35fd51` · `7486cce25482` |

Thứ tự HE-1 theo `order.json`: episode 0 là V-EGO và 1 là V-NOEGO, cùng seed 1000100; episode 2 là V-EGO và 3 là V-NOEGO, cùng seed 1000101. Video của cả hai nhánh nằm trong thư mục mang tên V-EGO ([HE-1](he-1.md) mục 7.1).

## 2. Chạy công cụ đã merge

Chạy từ `master` `24b9bed2` trên laptop, đúng như CLI `fw`:

| Công cụ | Lệnh | Mã thoát | Vì sao |
|---|---|---|---|
| Kiểm hệ thống R1–R6 (DA-13) | `fw eval diag-system --episode <thư mục lượt>` cho cả hai lượt Isaac | 2 | "không tìm thấy steps.jsonl". `eval_psi0.sh` (S1-03) và `he1_client.sh` (HE-1) gọi thẳng `eval-decoupled-wbc` của SIMPLE, không qua hook trace `flywheel_simple.trace.run` (DA-38). Không có `steps.jsonl`, `camera_params.jsonl`, `rollout_result.json`, `rtc.jsonl` |
| Scorer từng bước (DA-36) | `fw eval score --trace … --task …` | 2 | Chưa có `TaskDefinition` nào cho task hai bàn trên `master`; chỉ có bản giả `toy-pick-place` của testkit. `configs/eval/scorer/two-table.yaml` có sẵn (sha256 `98ce51bd…`), nhưng `TaskDefinition` và tín hiệu V7 thuộc story 3.4 của Hưng (**[Đã chốt 5/11/2026, Hiếu]**, DA-38). Scorer cũng không đọc `TraceStep`: nó đọc trace tín hiệu task V7 (03 mục 4.2) |
| Quy lỗi về stage (DA-13, `stage.yaml`) | `attribute_stage` (API, không có lệnh CLI riêng) | Không chạy | Cả năm dòng của bảng đều cần probe P1, P3 hoặc P4 của checkpoint, hoặc vector điều kiện. Chưa có probe nào cho checkpoint hai bàn. Theo `attribute.py`, các dòng này là `unavailable`, không đoán |
| Evidence card (DA-39) | Hợp đồng `flywheel.contracts.evidence.EvidenceCard` | Không dựng JSON | Chưa có bộ dựng thẻ trên `master`, chỉ có hợp đồng và file mẫu. `Representative` bắt buộc có `score_id` (`sc_…`, từ `Score`) và `trace_sha256`. Cả hai không có thật cho lượt Isaac. Dựng JSON với giá trị bịa thì sai mục đích của thẻ, nên thẻ ở mục 4 viết theo đúng khuôn của hợp đồng nhưng ở dạng bảng |
| Chọn can thiệp (`flywheel.loop.decide`) | — | Không chạy | Package `decide` còn rỗng (chỉ có `__init__.py`). Lợi ích kỳ vọng ở mục 5 tính bằng `ExpectedGain` của hợp đồng (kiểm được công thức), thứ tự theo spec mục 6.11 |

### 2.1 Kiểm hệ thống, đọc tay theo `system.yaml`

Công cụ không chạy được, nên bảng dưới đọc từng mã từ số liệu đang có, theo ngưỡng của [`system.yaml`](../../configs/eval/diagnosis/system.yaml) (sha256 `d30ee7b9…`). Kết quả không thay cho `diag-system`. Cột cuối là `outcome` mà thẻ được phép ghi.

| Mã | Đầu vào cần | Có gì | Đọc được | `outcome` trên thẻ |
|---|---|---|---|---|
| R1 độ trễ | `rtc.jsonl` | `route.jsonl` của HE-1 ghi thời gian từng `/act`: 200/200 trả 200. Trừ chunk 0, p99 là 0,988 / 0,720 / 0,701 / 0,684 s ở episode 0–3, so với τ_lat 0,10 s. S1-03 đo RTT ấm 460 ± 19 ms qua cùng kiểu đường chuyển tiếp Colab (`psi0-eval.md` 3.4.1, 3/11/2026) | Vượt ngưỡng ở mọi episode HE-1. Lượt đạt của S1-03 chạy cùng kiểu đường chuyển tiếp, nên gần như chắc cũng vượt: độ trễ không tách được lượt đạt và lượt hỏng. Vòng eval của SIMPLE đồng bộ: mô phỏng dừng khi chờ server. Vì vậy R1 chỉ được ghi lại, không quyết định gì (`verdict.py`, PR #146/#148) | `not_judged` (không có `rtc.jsonl`); với rollout đồng bộ thì R1 không vào kết luận |
| R2 buffer | `rtc.jsonl` (`delay_steps`) | Như R1: ceil(trễ × 50) > d = 6 ở 49/49 chunk mỗi episode | Như R1: rollout đồng bộ, không quyết định | `not_judged` |
| R3 bám lệnh | `steps.jsonl` | Không có ở lượt Isaac. DA-38 `mujoco`, cùng điều kiện `e78fb93` 0–1: R3 bắn ở cả hai episode (thân trên 2,57 và 2,65; thân dưới 1,75 và 0,82, so với ngưỡng 0,10 và 0,15) | Hai điều kiện này **thành công** ở Isaac, nên ngưỡng R3 hiện tại bắn cả trên lượt tốt. Ngưỡng chưa hiệu chỉnh (DA-37) | `not_judged` |
| R4 đồng bộ | `steps.jsonl` | Không có | SIMPLE render khung ở đúng thời gian sim của state, nên R4 = 0 theo cách dựng (`runtime.py`) | `not_judged` (dự kiến 0 khi có trace) |
| R5 camera | `camera_params.jsonl` | Không có. Bản tham chiếu G0 ghim từ model MuJoCo (`fc7f9c90…`). S1-03 so bằng mắt: góc nhìn và FOV của `head_stereo_left` ở Isaac khớp video train | Chưa kiểm bằng số | `not_judged` |
| R6 hạ tầng | `rollout_result.json` (`infra_status`) | Client S1-03 thoát 0. Mọi `/act` của HE-1 trả 200. Mọi episode hỏng chạy đủ 1 200 bước. Server DA-38 chạy chồng 14:08–14:18Z, trước episode 0 của HE-1 (bắt đầu 14:24:17Z) | Không thấy lỗi hạ tầng, nhưng không có bản ghi theo hợp đồng | `not_judged` |

Theo `Representative._diagnosis_follows_the_checks`: khi còn một mã hệ thống `not_judged`, chẩn đoán duy nhất hợp lệ là `unknown` (CHƯA RÕ).

## 3. Bảng lỗi theo bước

Bước theo spec mục 5.1: 1 tiếp cận, 2 gắp, 3 đi, 4 tới bàn đích, 5 đặt, 6 nhả và ổn định. **Nguồn: đọc video camera đầu** (lưới 16 khung mỗi episode, thêm 12 khung dày ở đoạn nghi ngờ). Không phải tín hiệu scorer. Kiểu lỗi theo spec mục 5.2; chỗ hai kiểu đều hợp thì ghi cả hai, khi có `TaskDefinition` thì scorer quyết.

| Lượt · episode | Checkpoint | Điều kiện | Bước hỏng đầu k | Kiểu lỗi | Lớp | Quan sát |
|---|---|---|---|---|---|---|
| S1-03 · 4 | Tác giả | `e78fb93` L0 #4 | 5 | L-PLACE | Đặt | Gắp, đi, tới bàn 2 được. Hộp ở bên phải giỏ; nhả lúc khoảng 14 s, hộp rơi xuống sàn cạnh bàn |
| S1-03 · 5 | Tác giả | `e78fb93` L0 #5 | 5 | L-PLACE | Đặt | Nhả lúc khoảng 16 s, hộp chạm vành giỏ rồi lật ra ngoài (17,6 s), nằm trên bàn ngoài giỏ |
| S1-03 · 6 | Tác giả | `e78fb93` L0 #6 | 5 | L-PLACE | Đặt | Nhả lúc khoảng 15 s, trước giỏ, hộp rơi xuống sàn |
| S1-03 · 9 | Tác giả | `e78fb93` L0 #9 | 5 | L-PLACE hoặc L-COLLIDE | Đặt | Tay cầm hộp ép vào giỏ ở mép bàn (10–13 s); khoảng 13 s cả hộp và giỏ rơi khỏi bàn |
| HE-1 · 0 | V-EGO N20 | dev 1000100 L0 | 2 | L-GRASP | Gắp | Tay phải khép trong không khí cạnh hộp (khoảng 3 s), hộp đổ ở mép bàn; robot đi sang bàn 2 tay không |
| HE-1 · 1 | V-NOEGO N20 | dev 1000100 L0 | 2 | L-GRASP | Gắp | Như episode 0; ở bàn 2 tay khép trên giỏ, không có vật |
| HE-1 · 2 | V-EGO N20 | dev 1000101 L0 | 5 | L-PLACE (không đưa vật vào vùng đích, không nhả) | Đặt | Gắp, đi, tới bàn 2 được. Từ khoảng 11 s đứng cầm hộp bên phải giỏ tới hết giờ |
| HE-1 · 3 | V-NOEGO N20 | dev 1000101 L0 | 5 | L-PLACE, sau đó đi sai | Đặt | Như episode 2 tới khoảng 17 s, rồi quay người đi về phía bàn 1, vẫn cầm hộp |

**Cụm sơ bộ** (spec mục 6.3; gom theo checkpoint, mức, k và lớp lỗi):

| Cụm | Checkpoint | Mức | k · lớp | Thành viên | m_j |
|---|---|---|---|---|---|
| A | Tác giả | 0 | 5 · đặt | S1-03 #4, #5, #6, #9 | 4 |
| B | N20 (V-EGO, V-NOEGO) | 0 | 2 · gắp | HE-1 #0, #1 (cùng seed 1000100) | 2 |
| C | N20 (V-EGO, V-NOEGO) | 0 | 5 · đặt | HE-1 #2, #3 (cùng seed 1000101) | 2 |

Cụm A là cụm đáng xử lý: đó là checkpoint tốt nhất và là checkpoint cha nếu cải tiến. B và C thuộc hai checkpoint thí nghiệm của HE, có giới hạn N20 là một bàn tay không cử động trong cả 20 demo ([HE-1](he-1.md) mục 4). Thêm demo cho chúng (N = 80) chính là câu hỏi của HE, không phải một can thiệp Failure → Data.

**Quan sát chung, chưa đo** [Đề xuất]: ở cả 6 ca hỏng bước đặt, robot dừng ở bàn 2 với giỏ nằm bên trái bàn tay phải đang cầm hộp, rồi không đưa hộp sang ngang đủ. Episode thành công 7 cũng tới với giỏ bên trái nhưng đưa được hộp vào. Giả thuyết H-A: độ lệch ngang lúc tới bàn đích ở ca hỏng lớn hơn ở ca đạt. Nếu đúng, lỗi thuộc trạng thái đầu bước 5, tức TRẠNG THÁI ĐẦU XẤU, hơn là kỹ năng đặt. Cần tư thế thân và vị trí giỏ trong trace để kiểm. Video không đo được.

## 4. Evidence card

Thẻ của cụm A theo khuôn `EvidenceCard` (DA-39). Ô "chưa có" là trường bắt buộc mà lượt Isaac không cung cấp được (mục 2).

| Trường | Giá trị |
|---|---|
| `cluster_id` | Chưa có: cần `Cluster` dựng từ `Score` |
| `run_plan_id` | Không có: lượt S1-03 chạy trước khi có RunPlan G0 cho eval |
| `task_id` · `embodiment_id` · `level` | `two-table` · `g1_sonic_dwbc@1` · 0 |
| `first_failed_step` · `failure_kind` · `failure_class` | 5 · `L-PLACE` (#9 có thể là `L-COLLIDE`) · `place` |
| `member_episode_ids` | `e78fb93/L0/ep4`, `ep5`, `ep6`, `ep9` |
| `representatives` | Cả 4 (R = 5 > m = 4, nên không cần `representative_seed`) |
| `score_id` · `trace_sha256` | Chưa có · chưa có (video có hash ở mục 1, nhưng video không phải trace) |
| `system_config_sha256` · `stage_table_sha256` | `d30ee7b9…` (`system.yaml`) · `f7b234c0…` (`stage.yaml`) |
| `checks` hệ thống | `infra_status`, `tracking_error` (thân trên, thân dưới), `latency_p99`, `buffer_underruns`, `sync_offset`, `camera_reference`: tất cả `not_judged`, lý do "lượt Isaac không có `steps.jsonl`, `rtc.jsonl`, `camera_params.jsonl`, `rollout_result.json`" (mục 2.1) |
| `checks` dữ liệu | `planner_feasible`: `not_judged`, vì không có planner cho task hai bàn. Thay bằng demo teleop gần nhất: chính episode train i đã đạt ở điều kiện này, nên khả thi gần đúng. `reset_success`: `not_judged`, cần lưu và nạp trạng thái (Q3) và trạng thái chuẩn. `nominal_visuals`: không áp dụng ở mức 0. `in_train_domain`: dự kiến `true`, vì điều kiện i của `e78fb93` mức 0 là episode train i (S1-03 mục 3.1); chưa có công cụ kiểm. `coverage_distance`: dự kiến d ≈ 0 ≤ τ_cov, cùng lý do; τ_cov chưa tính |
| `stage_hypotheses` | Không có |
| `stage_unavailable` | `stage1_perception`, `stage3_action_group`, `runtime_distribution_shift`, `stage3_forgetting`: không có probe P1, P3, P4 của checkpoint. `out_of_domain`: không có vector điều kiện qua hợp đồng |
| `diagnosis` | **`unknown` (CHƯA RÕ)**: đa số 4/4 đại diện |
| `proposal` | `repair_ticket`, `consumes_budget` false: "Chạy lại 10 điều kiện `e78fb93` mức 0 ở `mujoco_isaac` qua hook trace DA-38, rồi `fw eval diag-system` và `fw eval score`" (mục 5.1) |
| `decision` · `result` | Chưa có: Hiếu chấp nhận hoặc ghi đè · không có |

Thẻ của cụm B và C giống hệt ở phần hệ thống: CHƯA RÕ, `repair_ticket`. Chỉ khác `first_failed_step` (2 và 5), checkpoint, và điều kiện dev (seed 1000100, 1000101).

## 5. Kế hoạch dữ liệu có chi phí

Đơn giá dùng bên dưới, đều là **số đo** trừ khi ghi khác:

| Mục | Giá trị | Nguồn |
|---|---|---|
| CU Colab | 0,0999 USD/CU; L4 khoảng 1,94 CU/giờ | Ledger DA-26, `cu_watch.py` |
| Episode Isaac trên `rtx3060` | 33 phút (S1-03, đồng hồ wall, máy chung) đến 83 phút (HE-1, đồng hồ sim); nguyên nhân chênh còn là câu hỏi mở | `psi0-eval.md` 3.6, [HE-1](he-1.md) 7.1 |
| CU mỗi episode Isaac (một server L4) | 1,07–2,68 CU (1,94 CU/giờ × 33–83 phút) | Tính từ hai dòng trên |
| Fine-tune Ψ₀ 40k bước (L4, batch 16) | 16,26 và 16,59 CU | Ledger DA-26, lần b3 |
| Thiết bị bàn phím trên task hai bàn | 12 giờ người (**ước lượng** của DA-16; chưa làm). Phút mỗi demo: **chưa đo** | [DA-16](../product/stories/DA-16-teleop-ban-phim.md) |
| S2 biến thể từ teleop | 18 giờ người để làm cho task hai bàn (**ước lượng** của DA-29; chưa làm). Đơn giá sinh của task khay: 292–358 giây-worker mỗi lượt đạt, 0 CU | [DA-29](../product/stories/DA-29-synthetic-s2-bien-the.md), ledger DA-35 |

### 5.1 Bước 0, bắt buộc: `repair_ticket` (không tiêu ngân sách dữ liệu)

| Việc | Chủ | Chi phí ước lượng |
|---|---|---|
| Chạy eval Isaac qua `flywheel_simple.trace.run` thay cho gọi thẳng SIMPLE. Hook mới được thử ở `mujoco`; ở `mujoco_isaac` chưa thử | Hiếu (DA-38, DA-26) | Vài giờ người; thử 1 episode khoảng 0,5–1,2 giờ client |
| `TaskDefinition` hai bàn và tín hiệu V7 (vật, tiếp xúc tay–vật) để `fw eval score` chấm được | Hưng (story 3.4, quyết định 5/11/2026) | Theo story 3.4 |
| Hiệu chỉnh ngưỡng R3 trên episode teleop thành công, vì ngưỡng hiện tại bắn cả trên lượt đạt | Châu (DA-37) | Theo DA-37 |
| Chạy lại checkpoint tác giả trên 10 điều kiện `e78fb93` mức 0, có trace | Hiếu | 10 episode: 5,5–13,8 giờ client trên `rtx3060`, 10,7–26,8 CU (1,1–2,7 USD) với server L4 |

Sau bước 0, cả 6 ca hỏng bước đặt và 2 ca hỏng bước gắp mới có được chẩn đoán hệ thống. Nếu R3, R5 hay R6 bắn sau hiệu chỉnh, cụm dừng ở đó với `repair_ticket` (ví dụ LỖI CONTROLLER), và vẫn không tiêu ngân sách dữ liệu.

### 5.2 Nếu hệ thống sạch: cụm A đi tiếp thế nào

| Bước spec | Cụm A | Hệ quả cho task hai bàn |
|---|---|---|
| 5 · khả thi | Episode train i đã đạt ở đúng điều kiện i, nên khả thi gần đúng (không có planner) | Không ra KHÔNG KHẢ THI |
| 6 · khoanh vùng bằng reset | Trạng thái chuẩn: phát lại action ghi của episode train i (đường `replay-server` của S1-03, B6) tới đầu bước 5, lưu trạng thái, rồi để policy chạy M = 10 lượt. Cần Q3 (nạp trạng thái đã lưu trong SIMPLE). Chi phí: 4 × 10 = 40 lượt ngắn (khoảng 500 bước mỗi lượt, 1,65–3,5 s mỗi bước như S1-03 và HE-1, cộng tới 9,5 phút nạp cảnh mỗi lượt) ở Isaac, khoảng 9–26 giờ client và 18–50 CU (**ước lượng**). Nếu Q3 "không" thì cụm "chưa khoanh vùng" | s_5 ≥ 0,8: TRẠNG THÁI ĐẦU XẤU (khớp giả thuyết H-A); s_5 < 0,8: sang bước 8 |
| 7 · thị giác | Chỉ áp cho mức 1, 2 | Không áp dụng |
| 8 · vùng phủ | Điều kiện là episode train, nên trong miền và d ≈ 0 | KỸ NĂNG YẾU; **THIẾU VÙNG PHỦ bị loại**, nên S1, S2 không được phép |

Vậy cụm A chỉ có hai kết cục tiêu ngân sách, và **cả hai đều là teleop**:

| Chẩn đoán | Can thiệp (spec 6.9, 6.10) | Số lượng (n_eff = min(4, L_t = 10) = 4) | Đường thu cho task hai bàn | Chi phí ước lượng |
|---|---|---|---|---|
| TRẠNG THÁI ĐẦU XẤU | Dữ liệu phục hồi từ trạng thái policy tạo ở đầu bước 5 | 4 đoạn | Không có PICO; bàn phím chưa làm; không có planner (Q6) | DA-16 12 giờ người (một lần) + 4 đoạn × phút chưa đo + fine-tune 16,6 CU |
| KỸ NĂNG YẾU | Teleop correction ở bước 5 | 4 correction | Như trên | Như trên |

**Lợi ích kỳ vọng** (spec 6.11; kiểm bằng `ExpectedGain` của hợp đồng). Prior Beta(1, 1) cho f̄ = 0,5:
- trên 10 điều kiện mức 0 đã eval: g = 100 × 4 / 10 × 0,5 = **20 điểm %**;
- trên N_dev = 90 của spec: 2,2 điểm %.

Đây là prior, chưa đo. Ở vòng 1, thứ tự chọn chỉ phụ thuộc đơn giá của loại can thiệp mà chẩn đoán cho phép (spec 6.11). Với cụm A thì chỉ có một loại: teleop.

**Ba loại dữ liệu, cho task hai bàn:**

| Loại | Thuật toán có chọn cho cụm A không | Lý do | Đường thu hiện có |
|---|---|---|---|
| Teleop | **Có**, qua dữ liệu phục hồi hoặc correction | Hai chẩn đoán còn lại đều chỉ tới teleop | Không: không có PICO (Q-27F chưa trả lời), bàn phím DA-16 chưa làm |
| Synthetic (S1, S2) | Không | Chỉ dành cho THIẾU VÙNG PHỦ, mà cụm A ở d ≈ 0. Ngoài ra S1 cần MP datagen (không có cho task hai bàn), S2 (DA-29) chưa làm | Không |
| Egocentric | Không | Không phải loại can thiệp trong bảng 6.9. Egocentric vào qua pretrain stage 1, là câu hỏi của HE (spec 7.9). HE-1 0/2 so với 0/2 không nói gì về nó | Không áp dụng |

Với cụm B (gắp) và C (đặt) của N20: điều kiện dev mới so với 20 demo train, nên THIẾU VÙNG PHỦ có thể xảy ra, và khi đó S2 là ứng viên. Nhưng như mục 3 đã nói, cải thiện N20 là việc của lưới HE (N = 80), không phải mục tiêu của vòng này.

### 5.3 Cần bao nhiêu lượt eval để thấy hiệu ứng

Mốc: checkpoint tác giả 6/10 ở mức 0. So cha với ứng viên, hai nhánh độc lập, Fisher chính xác hai phía, α = 0,05. Tính 11/11/2026 bằng cách liệt kê đủ mọi kết quả (scipy). Đây là **ước lượng**, giả định p_cha = 0,6.

| Điều kiện mỗi nhánh | Power với +10 / +20 / +30 điểm % | MDE ở power 80% |
|---|---|---|
| 10 | 0,02 / 0,06 / 0,15 | > 40 điểm % |
| 20 | 0,06 / 0,19 / 0,49 | 37 điểm % |
| 30 | 0,08 / 0,30 / 0,71 | 33 điểm % |
| 50 | 0,13 / 0,52 / 0,93 | 27 điểm % |
| 80 | 0,22 / 0,75 / 0,99 | 22 điểm % |
| 100 | 0,26 / 0,84 / 1,00 | 20 điểm % |

| Mục tiêu | Episode Isaac | Giờ client `rtx3060` | CU (server L4) |
|---|---|---|---|
| Thấy +30 điểm % (khoảng 35 điều kiện mỗi nhánh) | 70 | 38–97 | 75–188 |
| Thấy +20 điểm % (prior; khoảng 90 điều kiện mỗi nhánh) | 180 | 99–249 | 192–483 |
| Cổng dev của spec 6.12 (90 điều kiện × 3 lượt × 2 nhánh) | 540 | 297–747 | 576–1 449 |
| Đo tỉ lệ sửa được, spec 6.13 (4 lỗi × 5 điều kiện mới × 3 lượt × 2 nhánh) | 120 | 66–166 | 128–322 |

Ghép cặp theo điều kiện (McNemar) có thể giảm số điều kiện một chút, tùy tỉ lệ cặp lệch; chưa đo. Bộ `e78fb93` chỉ có 10 điều kiện mỗi mức, nên phải dựng điều kiện mới bằng `scripts/he/dev_eval_set.py`. Client Isaac chạy tuần tự, một episode một lúc trên `rtx3060`. Vì vậy cả dòng nhỏ nhất (+30 điểm %) đã là 2–4 ngày máy. Số dư Colab sau HE-1 là 38,42 CU (5/11/2026). **Trước demo 17/11 không có phương án nào đo được hiệu ứng.**

### 5.4 Tổng chi phí ước lượng tới lúc có câu trả lời về +20 điểm %

| Phần | Giờ người | CU |
|---|---|---|
| Bước 0: trace Isaac, chạy lại 10 điều kiện (chưa gồm story 3.4 và DA-37) | Vài giờ | 10,7–26,8 |
| Khoanh vùng bằng reset (nếu Q3 "có") | Vài giờ | 18–50 |
| Thiết bị bàn phím (DA-16) | 12 (ước lượng) | 0 |
| 4 đoạn phục hồi hoặc 4 correction | Chưa đo | 0 |
| Fine-tune từ checkpoint tác giả | — | 16,6 |
| Eval để thấy +20 điểm % | — | 192–483 |
| **Tổng** | **> 12 giờ + phần chưa đo** | **khoảng 240–580 (24–58 USD)** |

Phần eval chiếm hơn 80% số CU. Đây là ràng buộc thật của task hai bàn: eval Isaac khoảng 83 phút mỗi episode ở cấu hình của HE-1.

## 6. Đo được và không đo được

| Đo được | Không đo được (và vì sao) |
|---|---|
| Thành công theo cờ SIMPLE: 6/10 (Wilson 95% [31%, 83%]); V-EGO 0/2, V-NOEGO 0/2 (mỗi nhánh [0%, 66%]; gộp 0/4 là [0%, 49%]) | Bất kỳ chênh lệch nào giữa nhánh: n = 2 mỗi nhánh. Một lần chạy 10 điều kiện chỉ thấy được chênh lệch trên 40 điểm % |
| Độ dài episode, số `/act`, thời gian `/act` (R1, R2 chỉ để ghi) | R3, R5, R6 theo công cụ: không có trace |
| Bước hỏng đầu tiên, đọc bằng mắt từ video | Bước hỏng theo scorer: chưa có `TaskDefinition` hai bàn; ngưỡng scorer còn là giả định |
| Điều kiện cụm A trùng episode train (theo cách dựng `e78fb93`) | d, τ_cov, s_k, probe P1/P3/P4: chưa có công cụ, trạng thái lưu hay probe |
| Đơn giá CU, giờ fine-tune, giờ eval | Phút người mỗi correction bằng bàn phím: DA-16 chưa làm; f_t thật: chưa có vòng nào |

Có hai lượt eval nguồn và một trong hai có bốn episode. Mọi tỉ lệ ở đây vì vậy là mô tả, không phải ước lượng chính xác. Câu "cụm A hỏng ở bước đặt" đúng với 4/4 ca quan sát. Nhưng 4 ca không đủ nói rằng bước đặt là điểm yếu chính của checkpoint ở mức 0. Muốn nói vậy cần các lượt lặp 2, 3 và mức 1, 2 mà S1-03 chưa chạy.

## 7. Thiếu gì, đề xuất cho chủ story

Không sửa mã lõi trong story này. Các chỗ thiếu dưới đây chặn vòng Failure → Data trên task hai bàn:

| # | Thiếu | Đề xuất | Chủ | Nhãn 08 |
|---|---|---|---|---|
| 1 | Eval Isaac (`eval_psi0.sh`, `he1_client.sh`) không qua hook trace | Chạy eval qua `flywheel_simple.trace.run`; thử hook ở `mujoco_isaac` | Hiếu (DA-38, DA-26) | `cause:test-gap` |
| 2 | Không có `TaskDefinition` hai bàn và tín hiệu V7 | Làm theo quyết định 5/11/2026 | Hưng (story 3.4) | — |
| 3 | Ngưỡng R3 bắn cả trên lượt đạt (DA-38 `mujoco`) | Hiệu chỉnh trên episode teleop thành công | Châu (DA-37) | — |
| 4 | Trace thật duy nhất của task hai bàn (DA-38) đã bị dọn, bản lưu trữ rỗng | Lưu trace thật vào chỗ bền trước khi dọn worktree hay máy | Hiếu | `cause:data` |
| 5 | Chưa có probe P1/P3/P4 cho checkpoint hai bàn | Giao story chạy probe cho checkpoint tác giả | Hiếu (PO) | — |
| 6 | Không có bộ dựng `EvidenceCard`; `decide` và kiểm vùng phủ (bước 8) chưa có mã | Bộ dựng thẻ ở làn Đánh giá; `decide` và bước 8 ở làn Vòng | Hiếu (DA-39), Long | — |
| 7 | Không có đường thu teleop cho task hai bàn | Quyết định Q-27F (PICO) hoặc ưu tiên DA-16 | Hiếu (PO) | — |
| 8 | Q3 (nạp trạng thái đã lưu trong SIMPLE) chưa trả lời | Kiểm trên task hai bàn trước khi lên lịch bước 6 | Hiếu | — |

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 11/11/2026 | Tạo file: gom rollout Isaac (S1-03 6/10, HE-1 0/2 + 0/2) có hash; chạy `diag-system`, `score` (mã 2, thiếu trace và `TaskDefinition`); R1–R6 đọc tay; bảng lỗi theo bước từ video; evidence card cụm A; kế hoạch dữ liệu có chi phí, power | Hiếu (soạn với Claude) |
