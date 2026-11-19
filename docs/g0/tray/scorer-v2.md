# Bộ chấm khay bản 2, tín hiệu lỗi trong outcome, eval nhiều lượt (DA-42)

Viết 19/11/2026 cho [story DA-42](../../product/stories/DA-42-bo-cham-outcome-eval-nhieu-luot.md). Bộ chấm ở đây là vị từ của task SIMPLE, `flywheel_simple/tray/predicates.py` (DA-32): nó quyết `check_success`, nhãn lỗi và `scorer_steps` của outcome. Hai phiếu soạn sẵn ở [tray.md](../../he/tray.md) mục 20.11 là đầu vào.

**Trạng thái.** Mã và test CPU xong; test MuJoCo chạy trên laptop. **Chưa đo trên rollout của policy**: chưa có lô eval nào chạy với bản 2. Mọi kết luận về số lượt bị ảnh hưởng dưới đây là suy từ mã và từ outcome cũ, ghi rõ ở từng mục. Runbook đo ở mục 7.

## 1. Tóm tắt

| Thay đổi | Bản 1 | Bản 2 | Bằng chứng | Chưa kiểm |
|---|---|---|---|---|
| `approach_a`, vế tay | Hai điểm lòng bàn tay cách **tâm** tay cầm ≤ `r_reach` 0,10 m trong cùng một chu kỳ | Cách **thanh** tay cầm (đoạn dài `handle_length` 0,12 m) ≤ 0,10 m, **hoặc** cả hai tay đang chạm tay cầm | Hình học (mục 2); tray.md 20.11: 7–10 trên 60 lượt mang khay sang B mà không qua bước này | Khoảng cách lòng bàn tay–tay cầm thật của policy: outcome cũ không có |
| `L-TRAY-TILT` | Khay rời cả hai bàn sau khi nhấc và nghiêng > 15° | Như bản 1, **và** cả hai tay đang chạm tay cầm | Mã (mục 3); outcome cũ: 138 trên 292 lượt `L-TRAY-TILT` kết thúc với khay nằm phẳng trên bàn B; test MuJoCo | Nhãn bật lúc nào trong các lượt cũ: outcome cũ không có `failure_t` |
| Outcome | Nhãn cuối, tư thế khay cuối, 7 cờ bước | Thêm `scorer_version`, `failure_t`, trạng thái lúc lỗi, thời điểm chốt từng bước, khoảng cách lòng bàn tay–tay cầm nhỏ nhất, và kết luận của bản 1 trên cùng rollout | Test CPU; chạy thử với `StepTracker` thật | Chưa chạy trong một lô eval thật (mục 7) |
| Gộp kết quả | Không ghi phiên bản | `eval_results`, `place_error` ghi phiên bản, từ chối trộn | Test CPU; đọc lại lô `C_70` cho cùng số | — |
| Eval | Một lượt mỗi điều kiện | `--repeats N`, Wilson theo cỡ mẫu hiệu dụng | Test CPU | Lượt lặp của Ψ₀ khác nhau bao nhiêu khi đổi hạt nhiễu: chưa chạy |

Bản 1 vẫn chạy được: `StepTracker(cfg, sample, version=1)`. Mặc định là bản 2 (`SCORER_VERSION`).

## 2. `approach_a`

**Bản 1.** `approach_a` cần cùng một chu kỳ: base trong `approach_zone` trước mép bàn A, và hai điểm lòng bàn tay (trung điểm `wrist_yaw_link` và `hand_middle_0_link`) cách **tâm** tay cầm ≤ 0,10 m. Các bước chốt theo thứ tự, và `carrying` (điều kiện của `L-TRAY-TILT`, `L-ONE-HAND`) đọc cờ của bước `lift`. Nên một lượt không qua `approach_a` thì không qua bước nào, và hai nhãn đó không bao giờ bật.

**Vì sao sai, theo hình học.** Tay cầm là thanh dài 0,12 m dọc trục x của khay (`mjcf.py`, `handle_length`). Bàn tay nắm gần một đầu thanh đã cách tâm 0,06 m dọc thanh, trước khi tính khoảng cách từ điểm lòng bàn tay (giữa cổ tay và gốc ngón giữa) tới thanh. Điểm đó nằm sau chỗ ngón tay ôm thanh vài cm; con số thật chưa đo. Với 0,06 m dọc thanh và 0,08 m ra ngoài, khoảng cách tới tâm đã là 0,10 m.

**Bằng chứng từ dữ liệu.** tray.md 20.11, trên lô stage 1 của bốn run cặp 60k: 7/60 lượt của `C_70`, 10/60 của `C_ALL` và 7/60 của `B_70` không bao giờ qua `approach_a` mà vẫn mang khay sang bàn B; vế base có giữ (≥ 0,947 thời gian trong vùng). Vế tay bị loại trừ là suy ra, vì trace không có tư thế tay.

**Bản 2.** Base vẫn phải trong vùng trước bàn A, và một trong hai:
- hai điểm lòng bàn tay cách **thanh** tay cầm ≤ `r_reach` (khoảng cách từ điểm tới đoạn thẳng, bỏ phần 0,06 m dọc thanh);
- cả hai tay đang chạm tay cầm của mình. Chạm là sự kiện mạnh hơn "ở gần", và đã là vị từ của bước `grasp`.

Không nới `r_reach`: nới làm bước này qua cả khi tay còn cách xa khay, mà không có số đo để chọn giá trị mới. Ngưỡng ở `configs/sim/tray.yaml` cũng thuộc DA-41.

**Hệ quả không chỉ là nới.** Ở lượt mà bản 1 không cho qua `approach_a`, bản 2 cho `carrying` đúng, nên `L-TRAY-TILT` hay `L-ONE-HAND` có thể bật ở đó, kể cả ở lượt bản 1 tính là thành công (tray.md 20.11 nêu hai lượt như vậy). Ở lượt bản 1 đã qua `approach_a`, lỗi của bản 2 là tập con lỗi của bản 1.

**Chưa kiểm.** Khoảng cách thật từ điểm lòng bàn tay tới thanh khi policy cầm khay. Outcome mới ghi `palm_handle_min_m` (tới tâm) và `palm_handle_bar_min_m` (tới thanh), mỗi tay và `both` (lớn hơn của hai tay trong cùng chu kỳ, đúng đại lượng bước này so với `r_reach`). Lô đo của mục 7 cho biết bản 2 có đủ không.

## 3. `L-TRAY-TILT` khi khay nằm phẳng trên bàn B

**Từ mã.** Ở bản 1, `_first_failure` đặt `carrying = steps[lift] and tray_on_table == "none"`. Không có vế nào về tay. Sau khi robot buông khay phía trên bàn B, khay rơi hoặc nảy vài chu kỳ mà không chạm bàn nào; nếu lúc đó nghiêng > 15° thì nhãn là `L-TRAY-TILT`. Nhãn đầu tiên là cuối cùng, và thành công không được xét sau lỗi, nên khay nằm yên đúng đích sau đó vẫn không bao giờ là thành công. Đây là đường duy nhất trong mã cho ra `L-TRAY-TILT` mà tư thế cuối phẳng trên bàn B, trừ khi khay nghiêng thật lúc còn mang rồi được đặt lại phẳng.

**Từ outcome cũ** (đọc trên laptop, chỉ đọc file, các lô eval của DA-34 chép từ `rtx3060` trong `fwdata/rtx3060/denso-da34-pool`; không tính `C70_R1`, theo quyết định của Hiếu ngày 16/11/2026). "Phẳng trên bàn B": nghiêng cuối < 1°, đáy khay cách mặt bàn < 5 mm, phía bàn B. "Trong đích": vị trí và góc cuối trong dung sai của bộ chấm, đích dựng lại bằng `sample_episode`. Linh kiện và độ đứng yên không kiểm được: outcome không có.

| Lô | `L-TRAY-TILT` | Phẳng trên bàn B | Trong đó trong đích |
|---|---|---|---|
| `eval-c` | 142 | 30 | 0 |
| `eval-c-simready` | 38 | 25 | 1 |
| `eval-cplus-simready` | 36 | 31 | 4 |
| `pair60k-C_70` (stage 1) | 10 | 8 | 2 |
| `pair60k-C_ALL` (stage 1) | 15 | 9 | 0 |
| `pair60k-B_70` (stage 1) | 21 | 18 | 4 |
| `pair60k-B_ALL` (stage 1) | 17 | 13 | 3 |
| Bốn lô kiểm `check-*` | 13 | 4 | 0 |
| **Cộng** | **292** | **138** | **14** |

Video camera đầu của một lượt `C_70` (mức 1, seed 1000102, nhãn `L-TRAY-TILT`, 6 cờ bước): khay được mang thẳng, đặt xuống bàn B lúc khoảng 24,8 s, robot buông và lùi đi; khay nằm phẳng tới hết lượt. Video không cho biết nhãn bật ở chu kỳ nào.

**Bản 2.** `L-TRAY-TILT` cần thêm: cả hai tay đang chạm tay cầm. Nghiêng khi chỉ còn một tay là việc của `L-ONE-HAND` (bật sau `contact_grace` 0,2 s, như cũ). Nghiêng khi không tay nào chạm thì khay không còn được mang. Cách đặt xuống vẫn được chấm: khay rơi khỏi bàn hay sai tư thế là `L-PLACE-POSE` hoặc hết giờ, linh kiện rơi là `L-PART-DROP`.

**Test MuJoCo** (`test_predicates_sim.py`, cảnh MJCF thật của task, không robot): khay và linh kiện được thả cách đích 8 cm, nghiêng 18° quanh trục dài. Khay rời cả hai bàn 5 chu kỳ (0,1 s), cả 5 đều nghiêng > 15°, rồi nằm phẳng (0,0°). Bản 1 gắn `L-TRAY-TILT` ở chu kỳ đầu tiên trên không, không tay nào chạm; bản 2 chấm thành công. Cùng trạng thái nghiêng mà hai tay còn cầm thì cả hai bản gắn `L-TRAY-TILT`.

**Chưa kiểm.** Các lượt cũ có đúng bật nhãn sau khi buông hay không: outcome cũ không có `failure_t` hay tiếp xúc lúc lỗi. Lô đo của mục 7 trả lời bằng `at_failure.hand_contacts` của `scorer_v1` trên cùng rollout. Bản 2 cũng chưa phân biệt "buông khay từ cao" với "đặt khay": nếu cần coi thả từ cao là lỗi, đó là một nhãn mới, cần quyết định của Hiếu.

## 4. Outcome: tín hiệu lỗi

`eval_driver` thêm vào mỗi dòng `outcomes.jsonl` (chỉ thêm, khóa cũ giữ nghĩa):

| Khóa | Nghĩa |
|---|---|
| `scorer_version` | Phiên bản bộ chấm của `check_success`, nhãn lỗi và `scorer_steps` của dòng |
| `failure_t` | Thời gian mô phỏng lúc nhãn lỗi bật; `null` nếu không lỗi |
| `at_failure` | Tại `failure_t`: `tray_on_table` (`A`, `B`, `none`), `hand_contacts` (`left`, `right`), `tilt_deg`, `tray_pos`, `tray_quat` |
| `step_latch_t` | Thời điểm mỗi bước trong 7 bước chốt lần đầu, thứ tự `STEP_NAMES`; `null` nếu chưa chốt |
| `palm_handle_min_m` | Khoảng cách nhỏ nhất từ điểm lòng bàn tay tới **tâm** tay cầm, `left`, `right`, và `both` (nhỏ nhất qua các chu kỳ của khoảng cách lớn hơn trong hai tay) |
| `palm_handle_bar_min_m` | Như trên, tới **thanh** tay cầm |
| `scorer_v1` | Bộ chấm bản 1 chạy song song trên cùng trạng thái mỗi chu kỳ: `steps`, `success`, `failure`, `failure_t`, `at_failure`, `step_latch_t` |

`scorer_v1` là cách duy nhất so hai bản: rollout trên EGL không lặp lại (tray.md 13.2), nên so hai lô là so hai rollout khác nhau.

**Giới hạn.** Chỉ outcome của eval (qua `eval_driver`) có các khóa này. `TrayTransferEnv.outcome()` ở `simple_task.py` (DA-41 đang giữ) không đổi; outcome của replay QA và sinh dữ liệu vẫn chấm bằng bản 2 mà không ghi phiên bản. Đề xuất PR riêng sau DA-41: `outcome()` thêm `**self.task.tracker.outcome_fields()`.

## 5. Phiên bản khi gộp kết quả

- `eval_results` và `place_error` ghi `scorer_version` trong kết quả; bảng markdown mở đầu bằng dòng phiên bản.
- Dòng không có `scorer_version` là **không ghi**, `null`, kèm ghi chú; không được coi là bản 1, dù mọi dòng trước DA-42 là bản 1.
- Một thư mục trộn hai phiên bản, hoặc trộn dòng có và không có phiên bản: từ chối.
- Ghép cặp (`--baseline`) hai bên khác phiên bản: từ chối, trừ khi khai `--cross-scorer`; kết quả ghép cặp luôn ghi phiên bản hai bên và cờ `cross_scorer`.

Đọc lại lô `C_70` stage 1 với `C_ALL` làm baseline bằng mã mới cho cùng số như cũ (10/60 và 5/60, cùng cặp), với phiên bản "không ghi".

## 6. Eval nhiều lượt mỗi điều kiện

**Chạy.** `eval_batch --repeats N`: lượt 0 ở `<out>/<lô>/` như cũ, lượt r ≥ 1 ở `<out>/<lô>.r<r>/`, ngay sau lô của nó. `--max-chunks` và `--chunks` gọi tên lô, không gọi lượt, nên vẫn cắt trọn điều kiện. N = 1 (mặc định) cho đúng thứ tự, thư mục và seed như trước. Lượt r gửi server hạt nhiễu policy `seed + r × 10 000 000`; cảnh vẫn dựng từ seed của điều kiện. Server có dùng hạt này hay không là việc của server (tray.md 8.5).

**Đọc.** `eval_results --repeats N`. Mỗi mức có `n` (số rollout), `conditions`, tỉ lệ qua từng bước trên mọi rollout, và `per_condition`: số thành công trên số rollout của từng điều kiện.

**Khoảng tin cậy.** Các lượt của một điều kiện chung cảnh, nên không độc lập. `wilson` là khoảng Wilson với cỡ mẫu hiệu dụng:
- hệ số thiết kế = phương sai giữa các điều kiện của ước lượng tỉ số, C / (C − 1) · Σ (k_i − p·m_i)² / n², chia cho p(1 − p)/n; tối thiểu 1;
- n_eff = số rollout / hệ số thiết kế (`wilson_n_eff`); cách tính ghi ở `wilson_method`;
- p bằng 0 hoặc 1 thì phương sai đó bằng 0, nên lấy n_eff = số điều kiện (thận trọng);
- một rollout mỗi điều kiện thì n_eff = n và `wilson` đúng là khoảng Wilson cũ.

CI bootstrap lấy mẫu lại **điều kiện** (tỉ lệ thành công của từng điều kiện) trong từng mức. Ghép cặp với baseline chỉ dùng lượt 0 của mỗi điều kiện, là lượt mà lô một-lượt cũ có; kết quả ghi `"on": "repeat 0 of each condition"`.

**Chưa kiểm.** Rollout lặp của Ψ₀ khác nhau bao nhiêu khi đổi hạt nhiễu, tức hệ số thiết kế thật: chưa có lô lặp nào.

## 7. Runbook: đo bộ chấm bản 2 (cho Hiếu)

Mục này nhiệm vụ con 5.2 điền.

## 8. Điều chưa kiểm, tóm lại

1. Bản 2 trên rollout thật của policy: chưa chạy lô nào (mục 7).
2. `approach_a`: khoảng cách lòng bàn tay–thanh thật, và bản 2 có cho qua đủ 7–10 lượt/60 của tray.md 20.11 không.
3. `L-TRAY-TILT`: các lượt cũ có bật nhãn sau khi buông không; outcome cũ không có `failure_t`.
4. Bản vá `compute_reward` của `eval_driver` chỉ chạy với bản giả và với `StepTracker` thật ngoài SIMPLE; chưa chạy trong `eval-decoupled-wbc`.
5. Hệ số thiết kế thật của eval lặp.
6. Plan đã đóng băng ghim `predicates.py` bằng sha256 (`he-tray-v2`, `he-tray-pair60k`, `he-tray-b`, `he-tray-cmax`): sửa bộ chấm làm `pairplan check --launch` và 7 test của `flywheel-psi0` báo "pinned file ... changed". Đó là chốt bảo vệ đúng chức năng; cần `Decision` của Hiếu (story, chỗ cần quyết 4).
