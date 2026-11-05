# HE-1: prior egocentric và số demo robot trên task hai bàn (DA-26)

_**Đã chốt** 4/11/2026: Hiếu duyệt tier 2, RunPlan đóng băng `rp_95c98a476499`, `Decision` `plan_review` trong `he-1.plan_review.json` (mục 5, 6.2). Eval chính là bộ dev của đội (mục 1.2). Story [DA-26](../product/stories/DA-26-thi-nghiem-he-egocentric.md) nhiệm vụ 1, 2; [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 7; [spec](../spec-v10-failure-to-data.md) mục 3 (HE), 7.5, 7.9. RunPlan: [`he-1.yaml`](../../configs/runplans/he/he-1.yaml); tập demo: [`demo_sets.json`](../../configs/runplans/he/demo_sets.json)._

Quy tắc ở mục 2–3 **không đổi sau khi thấy kết quả** (ghi chú của story). Muốn đổi thì viết RunPlan mới kèm `Decision`, và báo kết quả theo cả quy tắc cũ lẫn mới. Sau khi đóng băng, `he1_plan.py check` báo lỗi nếu `he-1.yaml` khác bản trong `he-1.lock.json`.

```bash
uv run python scripts/he/he1_plan.py check configs/runplans/he/he-1.yaml
uv run python scripts/he/he1_plan.py parents configs/runplans/he/he-1.yaml
uv run pytest scripts/he -q
```

## 1. Thiết lập

| Biến thể | Checkpoint gốc (psi-model `cb1480f`) | Dữ liệu egocentric khi pretrain | Chạy trước demo |
|---|---|---|---|
| V-EGO | `pre.fast.1by1.2601091803.ckpt.ego200k.he30k` + `postpre.1by1.pad36.2601131206.ckpt.he30k` | EgoDex đủ, cộng HE | N = 20 (N = 80 sau demo, mục 6.2) |
| V-NOEGO | `pre.abl.only.he.2512311516.48k` + `postpre.abl.only.he.2602050012` | Chỉ HE | N = 20 (N = 80 sau demo, mục 6.2) |
| V-EGO10 (tùy chọn) | `pre.abl.ego.10per.2602021632.46k` + `postpre.abl.ego.10per.2602050006` | 10% EgoDex | Không; sau demo nếu còn ngân sách |

- **Dữ liệu robot**: gói teleop task hai bàn của tác giả, `psi-data` `e78fb93`, `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (sha256 `6cdf9022…`), 99 episode, cả 99 đạt QA của [S1-07](../g0/psi-data.md) (N_teleop = 99 ≥ 80, nên điểm cuối lưới là 80). Train giữ bản `e78fb93` tới sau 13/11/2026 ([psi-data.md mục 4.1](../g0/psi-data.md)).
- **Tập demo** lồng nhau N10 ⊂ N20 ⊂ N40 ⊂ N80, chọn tất định bằng `flywheel_psi0.tray.demo_sets` của DA-34: xếp episode theo sha256(muối | sha256 của zip | `episode_index`), tập n là n episode đầu. Gói không có seed (S1-07, V6), nên khóa là `episode_index` trong zip đã ghim. Hash: N10 `53b361e2…`, N20 `cf4d6e2c…`, N40 `a88f9b6f…`, N80 `3bfc858b…`. Mọi biến thể dùng cùng tập ở cùng N.
- **Loại episode 0–9 khỏi kho chọn** [Đề xuất]. Bộ eval `e78fb93` của tác giả đặt robot, vật và khay của điều kiện i đúng như episode train i ở mức 0, 1, và robot như episode train i ở mức 2 ([S1-03](../product/stories/S1-03-tai-tao-danh-gia-psi0.md) mục 3.1 của `psi0-eval.md`, S1-07 mục 4). Eval chính của HE nay là bộ dev (mục 1.2), không dính chuyện này. Nhưng bộ của tác giả vẫn dùng làm bộ phụ (mốc so, video). Nếu để 0–9 trong kho, N80 dễ chứa điều kiện của bộ phụ hơn N20. Kho còn 89 episode, vẫn ≥ 80, nên loại không tốn gì.
- **Recipe** chung: [`psi0-stage3.yaml`](../../configs/models/psi0-stage3.yaml) (40.000 bước, batch 16 trên một GPU, lr 1e-4 cosine, VLM đóng băng, RTC), ghi đè duy nhất `train.validation_steps: 2000` theo quyết định của Hiếu ở [S1-04 mục 4.1](../g0/psi0-finetune-cost.md). Máy: một Colab L4. Seed train 0 (seed 1 chỉ ở đủ lưới). `stats_psi0.json` của mỗi điểm tính trên chính N episode của điểm đó [Đề xuất], như DA-34. Ψ₀ ở `cda3fdf` không lọc episode, nên mỗi tập cần một dataset LeRobot con (việc của nhiệm vụ 3).
- **Eval chính** **[Đã chốt]** (Hiếu, 4/11/2026, tier 2, mục 6.2): 10 điều kiện mức 0 từ dải dev của đội, seed 1 000 100–1 000 109, như nhau cho mọi điểm (dải dev, không dùng bộ của tác giả). `conditions_sha256` `b63acd59…`: đúng 10 dòng mức 0 đầu của bản dựng 90 điều kiện `b8dec754…`, và một lần dựng lại riêng cho cùng sha256. Cách dựng ở mục 1.2. `eval-decoupled-wbc`, đồng bộ (design mục 8.5), chế độ `mujoco_isaac`, đồng hồ giờ sim (đề xuất của S1-03 sau Q-27C), 1 lượt mỗi điều kiện, 10 episode mỗi điểm. Mức 1, 2 và bộ 30 × 3 để cho đủ lưới sau demo.
- **Bộ phụ**: `simple-eval` của tác giả ở `e78fb93` (sha256 `8a4b0ff7…`), 10 điều kiện mỗi mức. Chỉ dùng cho mốc so và để đối chiếu số công bố 7/5/6. Không đọc số HE nào trên bộ này.
- **Mốc so (AC 3)**: checkpoint hai bàn của tác giả `…betweentablesteleop-v0…b64.gpus4.2604081126/ckpt_40000` (sha256 `c69c2ae8…`), fine-tune từ cặp của V-EGO trên cả 99 episode, 16 × 4 GPU. Ở tier 2 không eval trên bộ dev, vì không có CU (mục 6.2); số của S1-03 trên bộ của tác giả (Isaac mức 0: 6/10, công bố 7/10) báo bên cạnh để soát. Eval mốc so trên bộ dev chờ đủ lưới.

### 1.1 Kiểm checkpoint (nhiệm vụ 2)

`he1_plan.py parents` (4/11/2026) hỏi API cây thư mục của Hugging Face ở revision ghim và đọc header safetensors bằng hai yêu cầu range, không tải trọng số:

| Kiểm | Kết quả |
|---|---|
| sha256 LFS của 6 file trọng số ablation, checkpoint mốc so, gói train, gói eval | Khớp RunPlan, `problems` rỗng |
| Header safetensors của VLM | Cả ba biến thể: 625 tensor, cùng tên, dtype, shape |
| Header safetensors của action header | Cả ba: 181 tensor, cùng tên, dtype, shape |
| `config.json` của VLM | Giống từng byte ở cả ba |

`finetune-simple-psi0.sh` không còn ở Ψ₀ `cda3fdf`; `Psi0Trainer` của DA-19 gọi `scripts/train.py finetune_simple_psi0_config` với tham số của bản cuối (Hiếu chốt 3/11/2026). Smoke của DA-19 trên Colab đã nạp và train cặp V-EGO qua đường này. Hai cặp ablation có cùng bố cục tensor và cùng cấu hình, nên đi cùng đường nạp. Phần còn lại, tải đủ file và băm lại sha256 trên máy train, làm ở bước đầu của mỗi job nhiệm vụ 3; job dừng nếu sha256 khác RunPlan.

### 1.2 Bộ eval dev (`scripts/he/dev_eval_set.py`)

SIMPLE không có lệnh sinh điều kiện eval theo seed cho task hai bàn. Eval đọc điều kiện từ một dataset LeRobot, mỗi episode một khung kèm `environment_config`. Bộ `simple-eval` của tác giả do `dr-decoupled-wbc` dựng từ chính các episode train. Mức k của điều kiện i là episode train i, rút lại ngẫu nhiên theo `DRManager.load_state_dict(dr_level=k)`. Vì vậy mức 0, 1 là cảnh train (S1-07).

`dev_eval_set.py` làm đúng như vậy, chỉ thay episode train bằng một cảnh gốc rút mới từ seed dev:

1. Đặt seed cho RNG toàn cục của numpy và Python bằng seed điều kiện, rồi `env.reset` để có cảnh gốc. Cảnh gốc theo phân phối train (DR đầy đủ).
2. Đặt seed bằng sha256(muối | seed | mức), rồi reset với `state_dict` của cảnh gốc và `dr_level` = k.
3. Ghi `task.state_dict()` vào `environment_config`.

Nghĩa của mức giữ như tác giả: mức 0 rút lại vật gây nhiễu và vật liệu; mức 1 rút thêm ánh sáng; mức 2 rút thêm vị trí vật và khay, giữ vị trí robot.

Kiểm (4/11/2026, CPU, venv SIMPLE local `6d10628`):

| Kiểm | Kết quả |
|---|---|
| Cùng seed, hai lần reset | Cùng `dr_state_dict`; hai seed cho hai cảnh khác nhau |
| Hai tiến trình riêng sinh cùng tập | Cùng hash từng điều kiện và cùng `conditions_sha256` |
| Nạp lại từ `meta/episodes.jsonl` như `eval-decoupled-wbc` (`state_dict`, không `dr_level`) | `state_dict` sau reset giống hệt bản ghi ở mọi điều kiện |
| Nghĩa của mức | Mức 0, 1 cùng vị trí vật, khay, robot với cảnh gốc; mức 2 dời vật và khay, giữ robot |

Hai điểm rút ra khi kiểm:

- **Randomizer của SIMPLE bỏ qua seed của `env.reset`** (`DRManager.reset`) và rút từ RNG toàn cục, nên phải đặt seed trước mỗi lần reset.
- **Thứ tự khóa trong `environment_config` là một phần của cảnh.** SIMPLE gán vật gây nhiễu đã lưu cho `distractor_0, 1, …` theo thứ tự trong dict. Bản thử đầu ghi JSON có sắp khóa, nên khi nạp lại vật gây nhiễu đổi chỗ. Bản sau giữ thứ tự gốc khi ghi và khi băm.

File task `b75c678` của SIMPLE chỉ khác `6d10628` ở tư thế tay lúc spawn, không đổi DR, nên sinh bằng venv `6d10628` cho cùng điều kiện. Eval vẫn chạy với file task `b75c678`. Dữ liệu nằm ngoài git (`fwdata/he/dev-eval-v1`); RunPlan ghim `conditions_sha256`.

## 2. Ước lượng

- Thành công của điểm X (biến thể, N, seed) ở điều kiện i, lượt r: s_X,i,r ∈ {0, 1}, theo cờ `check_success` của SIMPLE.
- Chỉ số chính: tỉ lệ thành công gộp ba mức, p_X = trung bình trên điều kiện của trung bình theo lượt. Báo thêm từng mức, theo khuôn bảng paper (thành công trên số lượt).
- Hiệu V-EGO − V-NOEGO ở cùng N: trung bình theo điều kiện của (p_EGO,i − p_NOEGO,i), ghép cặp theo điều kiện.
- CI 95%: bootstrap theo điều kiện, lấy mẫu lại trong từng mức (tier 2: 10 điều kiện, chỉ mức 0), 10.000 lần, hạt giống 20261104, khoảng phân vị; cùng chỉ số lấy mẫu cho hai biến thể. Ở N có hai seed (đủ lưới) dùng bootstrap phân cấp của spec mục 7.5: lấy mẫu lại seed trước, rồi điều kiện.
- **N₅₀** [Đề xuất]: nội suy tuyến tính theo log₂ N giữa hai điểm lưới liền nhau mà đường cong cắt 50% lần đầu. Đạt ≥ 50% ở N nhỏ nhất đã chạy thì N₅₀ ≤ N đó; chưa tới 50% ở N = 80 thì N₅₀ > 80 (bị chặn). So N₅₀ của hai biến thể chỉ khi ít nhất một bên xác định: V-EGO xác định và V-NOEGO > 80 tính là V-EGO nhỏ hơn; cả hai > 80 là không xác định.
- Lượt hỏng do hạ tầng (server lỗi, sim sập, mất kết nối) không tính là thất bại của policy: chạy lại cùng điều kiện và báo số lần chạy lại.
- **Độ nhạy của bản sơ bộ** (tier 2, tính 4/11/2026, chưa đo): 10 điều kiện mỗi biến thể, 1 lượt, Fisher chính xác hai phía α = 0,05. Chỉ chênh lệch cỡ 50 điểm % trở lên mới có thể có ý nghĩa: 0/10 so với 5/10, 1/10 so với 7/10, 3/10 so với 9/10, 5/10 so với 10/10. MDE ở power 80% khoảng 65–68 điểm % khi nhánh kém ở 10–30%; chênh thật 30 điểm % chỉ được thấy 12–15% số lần (bảng ở mục 6.1). Kết quả không có ý nghĩa vì vậy không phải bằng chứng "không có tác dụng". (Bản nháp 90 điều kiện thấy được khoảng 15 điểm %; xem change log.)

## 3. Quy tắc diễn giải

Kiểm theo thứ tự; quy tắc 0 chặn mọi quy tắc sau.

| # | Điều kiện | Đọc là |
|---|---|---|
| 0 | Mốc so của tác giả, hoặc cả hai biến thể ở mọi N đã chạy, dưới 10% trên bộ eval chính | Pipeline eval hoặc renderer chưa đủ để đo (S1-03, Q-27C). Không so biến thể; ghi `Decision` |
| 1 | Cận dưới CI của (V-EGO − V-NOEGO) > 0 ở ít nhất 2 mức N, **và** N₅₀(V-EGO) < N₅₀(V-NOEGO) | **HE đạt** (spec mục 3) |
| 2 | Cận trên CI của (V-EGO − V-NOEGO) < 0 ở ít nhất 1 mức N, hoặc N₅₀(V-NOEGO) < N₅₀(V-EGO) mà không mức N nào có cận dưới > 0 | **HE âm**: kết quả hợp lệ, phải báo, kèm giải thích có thể (task trong sim gần HE hơn EgoDex; khác biệt chỉ rõ ở N nhỏ hơn lưới) |
| 3 | Còn lại (mọi CI chứa 0, hoặc dấu khác nhau giữa các N) | Không kết luận; báo từng CI và N₅₀ |

**Bản sơ bộ (AC 6, tier 2).** Chỉ có N = 20, một mức DR (mức 0), 10 điều kiện mỗi biến thể. Quy tắc 1 vì vậy không đọc được (cần ≥ 2 mức N). Thứ tự đọc: quy tắc 0 trước (cả hai biến thể dưới 10%, tức 0/10, thì không so); rồi Fisher hai phía α = 0,05 trên bảng 2 × 2, kèm hiệu ghép cặp theo điều kiện và CI bootstrap. Fisher có ý nghĩa thì báo "V-EGO hơn (hoặc kém) V-NOEGO ở N = 20, mức 0, sơ bộ", không gọi HE đạt. Không có ý nghĩa thì báo "bản sơ bộ chỉ thấy được chênh lệch từ khoảng 50 điểm %; chưa kết luận". Kết quả sơ bộ gắn nhãn "sơ bộ" ở mọi bảng, hình và câu trên slide; không gọi là kết luận HE. Kết luận HE chỉ đọc trên đủ lưới (bốn N, seed thứ hai ở N = 20, 40).

**Quy tắc phụ, không quyết định kết luận**: hiệu theo từng mức; tỉ lệ đạt từng bước của scorer; V-EGO10 so với V-NOEGO (đủ lưới) báo là kết quả mô tả.

## 4. Giới hạn (design mục 7.2)

- Ba biến thể khác nhau cả số bước pretrain (200k + 30k, 46k, 48k) và mỗi biến thể có action expert post-train riêng. Đội không tách được tác dụng của EgoDex khỏi hai yếu tố này; câu hỏi gửi PSI Lab ở Q-27E của S1-03.
- Batch toàn cục 16 trên một GPU, so với 64 của checkpoint tác giả (S1-04 mục 1.4); số tuyệt đối của điểm HE vì vậy có thể thấp hơn mốc so.
- Bộ eval chính là điều kiện mới, rút từ cùng phân phối DR với dữ liệu train. Nó đo tổng quát hóa trong phân phối, khác bộ của tác giả (mức 0, 1 là cảnh train). Vì vậy số của mốc so trên bộ dev không so thẳng được với 7/5/6 công bố.
- Kết quả trong sim; không suy ra số trên robot thật.
- Ở N = 20, một bàn tay không cử động trong cả 20 episode: chiều action 0–6 có min = max = 0 trong `stats_psi0.json` của tập cắt, còn ở bộ đầy đủ các chiều này có biên khác 0. Psi0 để nguyên các chiều này, không chuẩn hóa. Vì vậy ở N20 không arm nào học được cử động của bàn tay đó, và so V-EGO với V-NOEGO ở N20 không nói gì về bàn tay này. Báo cáo kết quả N20 phải ghi rõ giới hạn này. Lần chạy b2 (5/11/2026) hỏng vì lỗi NaN ở `hand_open_pose`; bản sửa ở PR #118.

## 5. Việc cần Hiếu chốt trước khi đóng băng

| # | Câu hỏi | Trạng thái |
|---|---|---|
| Q1 | Loại episode 0–9 khỏi kho chọn demo? | [Đề xuất] Có (mục 1). Bản đóng băng 4/11/2026 giữ đề xuất này; đổi thì N20 đổi, phải đóng băng bản mới trước khi chạy |
| Q2 | Bộ eval chính | **[Đã chốt]** (Hiếu, 4/11/2026): dải dev của đội; bộ của tác giả chỉ là bộ phụ. Đã dựng (mục 1.2) |
| Q3 | Chế độ eval (`mujoco` hay `mujoco_isaac`) và đồng hồ (giờ sim hay giờ tường) | S1-03 đã trả lời Q-27C (4/11/2026, `docs/g0/psi0-eval.md` mục 3.5–3.6 ở PR #66, đầu `3d30874`, chưa merge). Checkpoint của tác giả trên `e78fb93` mức 0, cùng 10 điều kiện: `mujoco` 2/10 (giờ tường) và 1/10 (giờ sim), `mujoco_isaac` 6/10. Fisher Isaac so với `mujoco` gộp 3/30: p = 0,003. Renderer gây chênh lệch, đồng hồ thì không. Ảnh của psi-data là ảnh Isaac, nên eval `mujoco` sẽ đặt mọi biến thể gần sàn 10%. Giờ sim của task hai bàn chạy qua `docker/psi0/simtime_eval.py`; đồng hồ sim của #90 chỉ phủ env khay. S1-03 đề xuất `mujoco_isaac`, giờ sim, và giữ eval ở `e78fb93`: ở `de140d6` robot bắt đầu lùi 6,1 cm và cả action teleop phát lại cũng 0/10. RunPlan ghi đề xuất này, chưa ký. **[Đã chốt]** (Hiếu, 4/11/2026, tier 2): `mujoco_isaac`, giờ sim, 10 điều kiện mức 0 mỗi biến thể (mục 6.2) |
| Q4 | Ngân sách CU và số lần fine-tune | **[Đã chốt]** (Hiếu, 4/11/2026, tier 2): 2 lần fine-tune ở N = 20, khoảng 49 CU, trần cứng 52 CU (mục 6.2) |

Đã đóng băng ngày 4/11/2026 theo tier 2 (mục 6.2), bằng lệnh

```bash
uv run python scripts/he/he1_plan.py freeze configs/runplans/he/he-1.yaml --signed-by Hiếu --reason "<lý do>"
```

Lệnh ghi `he-1.lock.json` và `he-1.plan_review.json` (artifact `Decision`, kind `plan_review`, `subject_id` là `run_plan_id`).

## 6. Chi phí ước lượng của bản sơ bộ (nhiệm vụ 3)

_Ước lượng từ số đo S1-04 và S1-03, chưa chạy._

- **Fine-tune** R1 trên L4: 16,6 CU, 8,5 giờ mỗi lần (S1-04 mục 4).
- **Eval** 90 episode mỗi điểm, 5 checkpoint (4 điểm cộng mốc so):
  - `mujoco`: khoảng 60–90 s mỗi episode trên `rtx3060`, server Ψ₀ cùng máy, 0 CU. Tức 1,5–2,3 giờ mỗi checkpoint, 8–11 giờ cho cả 5.
  - `mujoco_isaac`: khoảng 24,6 phút mỗi episode, server trên Colab L4 1,94 CU/giờ (S1-04 mục 5.1). Tức khoảng 37 giờ và 72 CU mỗi checkpoint.

| Phương án | Fine-tune | Eval | Tổng CU | Đáp ứng AC 6 |
|---|---|---|---|---|
| A · 4 lần R1, eval dev ở `mujoco` | 66 CU | 8–11 giờ `rtx3060`, 0 CU | **66** | Về hình thức có; về kỹ thuật yếu: Q-27C cho thấy `mujoco` đặt policy gần sàn 10% (mục 5, Q3) |
| B · như A, cộng video Isaac (design 7.6: vài điều kiện, ba cột, hai mức N) | 66 CU | thêm khoảng 10 episode, 4 giờ, 8 CU | **74** | Có |
| C · 4 lần R1, eval dev ở `mujoco_isaac` | 66 CU | khoảng 185 giờ, 360 CU | **426** | Không vừa cả giờ lẫn CU |
| D · chỉ N = 80 (2 lần R1), eval `mujoco` | 33 CU | 0 CU | **33** | Không: AC 6 cần N = 20 và 80 |
| E · 4 lần, 20.000 bước | khoảng 35 CU | như A | **35** | Có, nhưng đổi recipe mà Hiếu đã chốt R1 |

Số dư khoảng 101,8 CU (4/11/2026). Fine-tune của DA-34 (khoảng 66 CU) dùng chung số dư này, và Hiếu đang quyết cắt bớt số lần fine-tune. Q-27C đã cho thấy `mujoco` thấp hơn Isaac nhiều (mục 5, Q3): A yếu về kỹ thuật, C không vừa. Phương án F dưới đây là thẻ cho Hiếu chọn; mọi cắt giảm ghi `Decision` (AC 8).

### 6.1 Phương án F: eval Isaac trên bộ rút gọn

_Ước lượng, chưa chạy. Chưa ký; không có job Colab nào chạy cho tới khi Hiếu duyệt CU._

Chữ F vì E đã dùng ở bảng trên. Chỉ chạy N = 20, hai biến thể (V-EGO, V-NOEGO), eval `mujoco_isaac` giờ sim trên các điều kiện **mức 0** của bộ dev: 10 điều kiện là seed 1 000 100–1 000 109, 30 điều kiện là cả 1 000 100–1 000 129. Episode chạy trên `rtx3060`, server Ψ₀ trên Colab L4: khoảng 25 phút và 0,8 CU mỗi episode (S1-04 mục 5.1: 24,6 phút, 1,94 CU/giờ). Fine-tune: 2 lần R1 ở N = 20, 2 × 16,6 = 33 CU, 17 giờ.

| Điều kiện mỗi biến thể | Episode | Giờ eval | CU eval | Tổng CU (cả fine-tune) | Thêm mốc so của tác giả trên cùng bộ |
|---|---|---|---|---|---|
| F10 · 10 | 20 | khoảng 8 giờ | 16 | **49** | +10 episode, 4 giờ, 8 CU |
| F30 · 30 | 60 | khoảng 25 giờ | 48 | **81** | +30 episode, 12,5 giờ, 24 CU |

Cả hai vừa số dư 101,8 CU nếu chỉ HE dùng; F30 cộng mốc so (105 CU) thì không vừa. Fine-tune DA-34 dùng chung số dư, nên tổng thực tế là quyết định của Hiếu.

**Mỗi cỡ bộ phát hiện được gì.** Fisher chính xác hai phía, α = 0,05, hai biến thể độc lập, n điều kiện mỗi biến thể (tính 4/11/2026 bằng scipy, liệt kê đủ mọi kết quả). Ghép cặp theo điều kiện (McNemar) có thể nhạy hơn một chút; các số dưới đây theo Fisher như S1-03 dùng.

| n mỗi biến thể | Chênh nhỏ nhất có thể có ý nghĩa (nhánh kém → nhánh tốt) | MDE ở power 80% | Power khi chênh thật 30 điểm % |
|---|---|---|---|
| 10 | 0/10 → 5/10; 1/10 → 7/10; 3/10 → 9/10; 5/10 → 10/10 | khoảng 65–68 điểm % khi nhánh kém ở 10–30%; không đạt 80% khi nhánh kém ở 50% | 12–15% |
| 30 | 0/30 → 6/30; 1/30 → 8/30; 3/30 → 11/30; 5/30 → 13/30 | khoảng 34–39 điểm % khi nhánh kém ở 10–50% | 56–71% |

Đọc kết quả của F:

- F chỉ có một mức N và một mức DR. Vì vậy quy tắc 1 (≥ 2 mức N) không đọc được, và F **không đáp ứng đủ AC 6** (thiếu N = 80). Chọn F cần một `Decision` ghi việc giảm phạm vi.
- Kết quả F chỉ là "sơ bộ, một N" ở mọi bảng và slide. Fisher có ý nghĩa thì báo là chênh lệch quan sát được ở N = 20, mức 0; không gọi là HE đạt.
- F10 chỉ thấy được chênh lệch rất lớn (cỡ 50 điểm % trở lên), hợp cho video và minh họa demo hơn là đo. F30 thấy được chênh lệch cỡ 35–40 điểm % với power 80%; chênh 30 điểm % thì khoảng hai phần ba khả năng không thấy.
- Quy tắc 0 vẫn áp: cả hai biến thể dưới 10% thì không so. Có mốc so của tác giả trên cùng bộ giúp phân biệt "renderer/pipeline hỏng" với "N = 20 quá ít".
- Hiếu chọn F10 ngày 4/11/2026 (mục 6.2); RunPlan đã sửa đúng như vậy và đóng băng.

### 6.2 Quyết định: tier 2 (Hiếu, 4/11/2026) **[Đã chốt]**

Câu hỏi gửi Hiếu: "Approve CU for tier 2, with DA-26 on reduced Isaac eval (~84 CU)?". Hiếu trả lời: **"Approve tier 2"**. Tier 2 dùng chung số dư 101,8 CU với C, C+ của DA-34 và lượt ngắn của DA-30; phần của DA-26 là phương án F10 (mục 6.1), trần cứng **52 CU**. Ghi vào `he-1.plan_review.json` (`Decision`, kind `plan_review`) khi đóng băng.

| Mục | Chốt |
|---|---|
| Fine-tune | 2 lần R1: V-EGO N20 seed 0, V-NOEGO N20 seed 0. N = 80 bỏ khỏi bản sơ bộ, sang đủ lưới sau demo (cần RunPlan bản mới và CU mới) |
| Eval | `mujoco_isaac`, giờ sim, 10 điều kiện dev mức 0 (seed 1 000 100–1 000 109, `b63acd59…`), 1 lượt; server Ψ₀ trên Colab L4, client Isaac trên `rtx3060` |
| Mốc so của tác giả | Không chạy trên bộ dev ở tier 2 (không có CU). Số 6/10 của S1-03 trên mức 0 của bộ tác giả (Isaac) báo bên cạnh để soát |
| Đọc kết quả | Nhãn "sơ bộ"; Fisher hai phía α = 0,05; chỉ thấy được chênh lệch từ khoảng 50 điểm % (mục 2, 3) |
| AC 6 | Không đủ: thiếu N = 80. Đây là giảm phạm vi có `Decision` (AC 8) |
| Chạy | Chỉ chạy từ `master` sau khi Hiếu merge PR này; không chạy từ nhánh chưa merge |

**Trần CU từng job** (ước lượng, chưa chạy; dòng `estimated` trong [`ledger/DA-26.csv`](../g0/ledger/DA-26.csv)).

**Watcher chung** **[Đã chốt]** (4/11/2026): DA-26 chạy bằng watcher chung `scripts/colab/cu_watch.py` (PR #108, thiết kế lại sau review).

- Mỗi phiên Colab một tiến trình `session`. Tiến trình này theo dõi phiên theo endpoint, tự mở phiên (`--new`) và dừng phiên ở trần riêng của nó: **18,0 / 18,0 / 18,0 CU** cho hai fine-tune và server eval (trần eval 16 nâng lên 18, xem dòng dưới).
- **[Đã chốt 5/11/2026, Hiếu]** caps 18/18/16 (`Decision`). Cùng tổng 52 CU, trong tier 2 đã duyệt; thay 17,5 / 17,5 / 17,0 vì trần fine-tune 17,5 quá sát với tốc độ của S1-04 (mục 7, quy tắc dừng sớm). Trần không nằm trong RunPlan, nên `rp_95c98a476499` không đổi.
- **[Đã chốt 5/11/2026, Hiếu]** "Nâng lên 18 + giữ rtx3060": trần eval 18 (dòng dừng 17,77), và rtx3060 chỉ chạy client Isaac trong khung giờ eval, để episode gần 24,6 phút. Hai fine-tune đã đo 33,85 CU (b2 0,995 + b3 32,85), nên tổng DA-26 nhiều nhất 33,85 + 18 = 51,85 CU, trong trần cứng 52.
- **[Đã chốt 5/11/2026, Hiếu]** "Nâng trần cứng, giữ cap 18 (Recommended)", sau lần eval 1 hỏng ở bước chuẩn bị của client (mục 7.1). Trần cứng của DA-26 nâng từ 52 lên **53,54 CU** = 33,85 (hai fine-tune, đã đo) + 1,692 (lần eval 1, đã đo theo đồng hồ watcher; số dư giảm 1,53) + 18 (lần chạy lại). Lần chạy lại giữ trần 18 (dòng dừng 17,77), cùng quy tắc theo cặp và cùng thứ tự xen kẽ. Trần không nằm trong RunPlan, nên `rp_95c98a476499` không đổi.
- Cả đợt có thêm một tiến trình `guard` trong một thư mục registry mới:
  - dừng mọi phiên khi số dư thật xuống tới **`--floor 14`**;
  - dừng mọi assignment mà không watcher sống nào đăng ký.
  - Watcher cũng đặt `--floor 14`.
- **Một đợt một lúc** trên tài khoản, vì guard dừng mọi assignment ngoài registry của nó. Guard từ chối chạy khi đã có guard khác. Thứ tự: lần chạy ngắn 4 CU của DA-30 trước, rồi mới đến đợt của DA-26.
- Phiên server eval mở sau fine-tune: chạy một watcher `session --new` mới trong cùng registry. Nếu guard đã thoát (mọi watcher trước đã xong), chạy lại guard ở registry đó trước.
- Watcher kiểm loại GPU (L4) và dừng có xác nhận. Job chỉ bắt đầu khi đã có file `.ready` của phiên và heartbeat của guard còn mới. Lệnh chạy ở đầu docstring của script.
- **Laptop phải thức suốt lúc chạy**: laptop ngủ thì không có gì dừng phiên.
- **Không chạy job nào** cho tới khi #108 được merge và lần chạy ngắn của DA-30 đã xong.

| Job | Ước lượng | Trần |
|---|---|---|
| `job_da26_t2_ft_vego_n20_s0` | 8,5 giờ, 16,6 CU (S1-04 mục 4, gồm dựng VM 8 phút) | 18,0 CU (9,3 giờ) |
| `job_da26_t2_ft_vnoego_n20_s0` | 8,5 giờ, 16,6 CU | 18,0 CU (9,3 giờ) |
| `job_da26_t2_eval_isaac_n20`: một phiên server cho cả hai checkpoint | 20 episode × 24,6 phút + khoảng 1,0 CU trước episode đầu + 0,16 CU kết thúc ≈ 17,1 CU (mục 7.1) | ~~16,0~~ 18,0 CU (9,3 giờ) |
| `job_da26_t2_eval_isaac_n20`, lần 1 (hỏng, không có episode) | — | đã đo 1,692 CU |
| **Tổng** | **50,3 CU** | **52,0 CU** theo trần ban đầu; theo số đã đo: 33,85 + 18 = 51,85 CU; sau lần eval 1: 33,85 + 1,692 + 18 = **53,54 CU** (trần cứng mới) |

(Lịch sử, trước khi nâng trần.) Trần eval 16,0 thấp hơn ước lượng 16,2. Watcher dừng ở `16 − 1,94 × 430 / 3600 = 15,77` CU, tức khoảng 8,1 giờ. Ở 24,6 phút mỗi episode, đủ cho khoảng 19,5 trên 20 episode. Số 24,6 phút đo trên episode thất bại (S1-03); episode thành công kết thúc sớm hơn, nên ước lượng 16,2 có thể cao. **[Đã chốt 5/11/2026, Hiếu]** Driver eval chạy hai arm xen kẽ theo điều kiện (V-EGO rồi V-NOEGO ở mỗi điều kiện), để nếu thiếu thì thiếu đều ở cả hai arm. Phần này làm trong PR driver eval.

[Đề xuất] Eval chạy xen kẽ hai biến thể theo điều kiện (hai server trên cùng L4, mỗi server khoảng 6,2 GB VRAM; hoặc đổi checkpoint giữa các episode). Nếu phiên chạm trần giữa chừng, hai nhánh vẫn có cùng số điều kiện để so. Chạm trần thì báo số episode đã xong; chạy thêm cần Hiếu duyệt CU mới. Hai fine-tune chạy song song trên hai phiên L4, khoảng 8,5 giờ tường. Eval cần `rtx3060` khoảng 8,3 giờ; đặt máy với DA-34 và DA-35 khi fine-tune xong.

## 7. Chạy tier 2: hai fine-tune N20 (nhiệm vụ 2, 3)

Chưa chạy. Mỗi điểm một phiên Colab L4, một watcher `session` riêng, chung một guard trong một registry mới. Tên phiên cũng là job id của Ψ₀, tên thư mục trên laptop (`fwdata/he/runs/<tên>`) và trên Drive (`MyDrive/denso/da26/<tên>`).

| Điểm | Phiên | Dòng sổ chi phí | Trần |
|---|---|---|---|
| V-EGO/N20/0 | `da26-t2-ft-vego-n20-s0` | `job_da26_t2_ft_vego_n20_s0` | 18,0 CU |
| V-NOEGO/N20/0 | `da26-t2-ft-vnoego-n20-s0` | `job_da26_t2_ft_vnoego_n20_s0` | 18,0 CU |
| Server eval (sau) | `da26-t2-eval-n20` | `job_da26_t2_eval_isaac_n20` | 18,0 CU |

**Trên VM**, `scripts/he/he1_colab.py` chạy theo các pha dưới đây. Pha nào cũng từ chối chạy trong ba trường hợp: `he-1.yaml` khác bản đã đóng băng; khóa không phải `rp_95c98a476499` (giá trị này ghi cứng trong code); điểm không thuộc phần sơ bộ.

- `setup`: dựng môi trường Ψ₀ bằng đúng các lệnh môi trường trong `setup` của DA-19, không chạy phần tải của nó (`install_env`). Phần tải của DA-19 lấy cặp cha baseline và zip hiện hành, không ghim; với V-NOEGO là khoảng 6 GB không dùng mà vẫn tính CU. Sau đó tải đúng bản ghim: cặp checkpoint cha của điểm ở `psi-model@cb1480f`, zip hai bàn ở `psi-data@e78fb93`. Kiểm sha256 của hai safetensors, của zip và của `episodes.jsonl` với RunPlan; lệch một file là dừng, không train. Phần kiểm này là "tải và kiểm trên VM train" của nhiệm vụ 2. Cuối cùng cắt tập demo.
- `train`: chạy `Psi0Trainer` với recipe R1 và override của RunPlan (`train.validation_steps: 2000`), parent của biến thể, seed của điểm.
- `persist`: chép metrics, kết quả và các checkpoint đã ghi xong lên Drive. Phải chép cả trọng số, vì eval cần chúng. Lệnh `persist --watch 600 --pid <train>` chạy cạnh lúc train. `persist` từ chối chạy khi `/content/drive` chưa được mount; nếu không, nó sẽ ghi vào đĩa VM mà vẫn báo xong.
- `stage`: in JSON liệt kê những gì eval cần, kèm kích thước và sha256: mọi file ngoài `checkpoints/`, cùng `ckpt_<step>` mới nhất đã ghi xong (trừ trạng thái optimizer). Mỗi job có trạng thái train. `done` chỉ khi pha `train` của job kết thúc `ok` ở bước 40 000. `failed` khi pha đó có trạng thái khác hoặc bước khác (`train` ghi pha của nó trước khi báo lỗi), hoặc khi `train.log` đã có dòng `train exit` mà chưa có pha. Còn lại là `running`. Cả lần chạy cũng có trạng thái: `failed` khi `train.log` có `train exit N` với N khác 0, hoặc có dòng đó mà chưa có job nào. Trường hợp thứ hai là khi `train` chết trước khi Psi0Trainer tạo `runs/<job>`, ví dụ thiếu `.env`, import lỗi, hoặc kiểm hash, marker không qua. Khi đó `follow` vẫn dừng phiên và thoát 5.

**Bản bền khi chưa có Drive.** `colab drivemount` cần Hiếu đồng ý OAuth trên trình duyệt (DA-30 phát hiện, 4/11/2026). Khi chưa mount được, chỉ còn đĩa VM; dừng ở trần là mất checkpoint, khoảng 17 CU. Vì vậy laptop giữ bản bền, bằng `scripts/he/he1_fetch.py`:

- Không dùng `colab download`. Lệnh này đọc cả file qua API contents của Jupyter, thành một khối base64 nằm trong bộ nhớ ở cả hai đầu. Với `model.safetensors` 6,25 GB là 8,3 GB base64, trên laptop 14 GB RAM.
- File đi bằng rsync qua `colab ssh --proxy-mode`: truyền theo dòng, đứt thì nối lại (`--partial-dir`). Danh sách lấy từ `stage` của VM. Một file chỉ tính là đã lấy khi sha256 trên laptop bằng sha256 trên VM. Lượt quyết định "xong" luôn băm lại từ đầu, không dùng cache. Trong lúc train, log có thể được ghi thêm giữa lúc `stage` liệt kê và lúc kéo; file đó ghi vào `grown`, không tính là lỗi. Chỉ file checkpoint quyết định `bad_or_missing`, tốc độ MB/s và `ALERT`.
- `follow` chạy cạnh mỗi phiên từ lúc train: lấy log, rồi từng checkpoint mới (10 000, 20 000, 30 000) khi vừa ghi xong. Nó dừng khi train xong và `ckpt_40000` đã kiểm trên laptop. Với `--stop-when-done`, nó dừng luôn phiên, để phần còn lại tới trần không bị tính tiền. Từ bước 38 000, và khi train đã kết thúc, mỗi lượt cách nhau 60 s thay vì `--every`, nên phiên không bị tính thêm tới 600 s sau khi có `ckpt_40000`. Train `failed` thì `follow` kéo phần đã xong rồi dừng phiên, thoát 5.
- Mọi lần dừng đều có xác nhận. `colab stop` tối đa 3 lần, mỗi lần chờ 30 s, tới khi hai lần liệt kê tin được liên tiếp không còn phiên. Phiên nhận theo tên, hoặc theo endpoint trong `$R/$S.json` khi CLI mất tên (`[?]`). Nếu vẫn còn, gửi SIGTERM cho watcher, chỉ khi bản ghi `$R/$S.json` ở `starting` hoặc `running` và `/proc/<pid>/cmdline` có `cu_watch.py`; pid rỗng hoặc pid đã bị dùng lại thì không gửi. Watcher tự dừng phiên có xác nhận. Không xác nhận được thì `follow` ghi `ALERT` ra stderr và thoát 6: phiên có thể vẫn đang tính tiền. Mỗi lệnh có thời hạn: 300 s, riêng rsync 3600 s (lượt kéo dở nối lại ở lượt sau).
- `once` là `--persist` của watcher, chạy ở mốc mềm. Hai lệnh dùng chung một khóa, nên `once` chờ lượt kéo đang chạy của `follow`.
- Trước mỗi lần SSH, script kiểm watcher còn sống và một lần liệt kê tin được còn có phiên. Tin được theo đúng cách của `cu_watch.py`: `colab usage` và `colab sessions` cùng thoát 0, mọi dòng đọc được, và số phiên không ít hơn số assignment của `usage`. Lý do: khi lỗi xác thực, CLI in "No active sessions" và vẫn thoát 0. Lần liệt kê không tin được không tính là phiên đã mất. `follow` bỏ qua lượt đó, và ghi `ALERT` từ lần thứ ba liên tiếp. `once` thử lại 3 lần, mỗi lần cách 20 s, rồi thoát 2.
- Mốc thời gian: mốc mềm (0,9 × 18 = 16,2 CU, khoảng 8,35 giờ) đến trước khi train xong (16,6 CU). Sau khi train xong còn khoảng 36 phút trước lệnh dừng ở trần (17,77 CU). 6,25 GB trong 36 phút cần ít nhất 2,9 MB/s. Ngưỡng `probe` và `ALERT` vẫn giữ 6 MB/s, để còn chỗ cho quy tắc dừng sớm. Tốc độ qua proxy Colab chưa đo. `follow` ghi `ALERT` khi một lượt kéo checkpoint trên 1 GB chậm hơn 6 MB/s. Lượt đầu là `ckpt_10000`, khoảng 2,2 giờ sau khi bắt đầu; nếu gặp `ALERT` khi đó thì báo ngay (mount Drive, hoặc Hiếu quyết định).
- Dung lượng laptop: 2 job × 4 checkpoint × 6,25 GB, khoảng 50 GB; đĩa còn 506 GB. Kéo lại cho server eval cũng đi rsync qua proxy, không dùng `colab upload`, vì lệnh này dùng cùng API contents.
- Thử khô trên laptop ngày 4/11/2026, VM giả trên đĩa, rsync thật, không qua SSH: [`test_he1_fetch.py`](../../scripts/he/test_he1_fetch.py) có 40 test (cả thư mục 53), gồm:
  - `probe`, phép tính dừng sớm và dừng sớm của `follow`;
  - train `failed` không bao giờ `final`; log được ghi thêm không phải lỗi; bản kéo hỏng sau rsync bị bắt bằng sha256;
  - lần dừng không xác nhận được thoát 6, có thử lại và SIGTERM; lần liệt kê khi lỗi xác thực không xác nhận được lần dừng; SIGTERM chỉ tới tiến trình `cu_watch.py` còn sống;
  - train chết trước khi có `runs/<job>` thoát 5; tốc độ chỉ tính byte checkpoint; lượt 60 s gần cuối; thời hạn riêng cho rsync.

  Chạy tay `once` và `follow` với file 2 GB: lấy lần lượt `ckpt_10000` đến `ckpt_40000`, thoát 0, `final: true`. Review lại #109 (5/11/2026) dùng đột biến: mỗi đột biến của các kiểm tra mới đều làm ít nhất một test hỏng. Đường SSH thật chỉ được thử ở lượt kéo đầu của đợt chạy, vài phút sau khi train bắt đầu.

**Tập demo của từng điểm** (`scripts/he/demo_subset.py`). Ψ₀ ở `cda3fdf` train trên mọi episode của dataset, không lọc được. Vì vậy mỗi điểm có dataset riêng, dựng như sau:

- lấy các episode của tập (khóa `episode_index` của zip) và đánh số lại 0..n−1 theo thứ tự nguồn;
- ghi qua bộ đọc/ghi DA-03; `index` đổi số được ghi vào `flywheel_lineage.jsonl`;
- tính stats từ chính các episode của tập (`own_train_set`), cùng cách SIMPLE tính khi xuất;
- `meta/flywheel_subset.json` ghi chỉ số nguồn của từng episode và set hash, tính lại từ zip.

Kiểm trên zip thật ngày 4/11/2026, trên laptop:

| Tập | Kết quả |
|---|---|
| N20 (6 s) | 20 episode, 12 367 khung. `action`, `states`, task và số khung video của mỗi episode trùng episode nguồn. `check_index` sạch, giữ đủ 14 cột |
| Cắt đủ 99 episode | `action` trùng `stats_psi0.json` của tác giả tuyệt đối. `states` lệch tối đa 3,6e-4, đúng phát hiện D4 đã biết về stats của nguồn |

**Điều kiện trước khi chạy.**

1. PR của driver đã merge. Chạy từ bản checkout `master`; registry ghi SHA của bản đó.
2. Phiên chính báo DA-30 đã xong và guard của DA-30 đã thoát. `colab sessions` trống.
3. Số dư ít nhất 66 CU: sàn 14, cộng hai trần fine-tune 36, cộng trần eval 16. Như vậy không job nào chạm sàn trước trần của nó. (Với trần eval 18 đã chốt: phiên eval cần số dư ít nhất 14 + 18 = 32 CU.)
4. Laptop thức suốt đợt. Watcher tự giữ `systemd-inhibit`; bật thêm chế độ giữ thức của app.

**Laptop: guard và hai watcher** (thư mục gốc là bản checkout `master`):

```bash
export PATH=$PATH:~/project/wm-wam-review/.venv-colab-cli/bin   # để cuối: python3 của venv này không có PyYAML
colab sessions; colab usage
R=fwdata/colab/batch-$(date +%Y%m%d-%H%M%S); mkdir -p fwdata/colab && mkdir $R && git rev-parse HEAD > $R/master.sha
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py guard --registry "$0" --floor 14 --log "$0/guard.jsonl"; echo "exit $?"' $R < /dev/null > $R/guard.out 2>&1 &
for S in da26-t2-ft-vego-n20-s0 da26-t2-ft-vnoego-n20-s0; do
  nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name "$1" --gpu L4 --cap 18 --floor 14 --persist "python3 scripts/he/he1_fetch.py once --session $1 --registry $0 --dest fwdata/he/runs" --log "$0/$1.jsonl"; echo "exit $?"' $R $S < /dev/null > $R/$S.out 2>&1 &
done
```

Hai hàm dùng trong cả đợt. `ready` in `READY` và trả 0 chỉ khi watcher đã thấy L4 và heartbeat của guard mới hơn 120 s; ngược lại trả 1, nên `ready $S && …` chặn bước sau. `vm` chạy một lệnh SSH trên VM của phiên, chỉ khi watcher còn sống và phiên còn trong danh sách: `colab ssh -s` tự mở phiên mới nếu tên không còn. Runtime chỉ nhận một kết nối SSH mỗi lúc, nên mọi job dài chạy tách khỏi shell. Khi `follow` đang kéo, `vm` có thể bị từ chối; khi đó chạy lại.

```bash
ready() { if ( until [ -f $R/$1.ready ]; do grep -q '^exit ' $R/$1.out && exit 1; sleep 5; done
  [ -f $R/guard.beat ] && [ $(( $(date +%s) - $(stat -c %Y $R/guard.beat) )) -lt 120 ] )
  then echo "$1 READY"; else echo "$1 NOT READY: do not start the job"; return 1; fi; }
vm() { grep -q '^exit ' $R/$1.out && { echo "$1: watcher exited, no ssh"; return 1; }
  colab sessions | grep -q "^\[$1\]" || { echo "$1: not listed, no ssh"; return 1; }
  ssh -o ProxyCommand="colab ssh --proxy-mode -s $1" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@colab "${@:2}"; }
```

**Mỗi phiên**, ví dụ V-EGO; với V-NOEGO thay `S` và `P`. Mỗi bước chỉ chạy khi bước trước đã xong.

Đo tốc độ trước, ngay sau `ready`, trước cả `setup`. `probe` kéo 1 GB từ VM về, mất vài phút, khoảng 0,1 CU. Kết quả ghi vào `fwdata/he/runs/.$S.probe.json`, và `follow` dùng nó cho quy tắc dừng sớm. File này không nằm trong `$R`, vì guard đọc mọi `*.json` ở đó như bản ghi watcher. Dưới 6 MB/s thì `probe` thoát 4: không chạy tiếp, dừng phiên và báo.

```bash
S=da26-t2-ft-vego-n20-s0; P=V-EGO/N20/0
ready $S && python3 scripts/he/he1_fetch.py probe --session $S --registry $R --dest fwdata/he/runs \
  || { colab stop -s $S; echo "$S: not ready or proxy too slow, session stopped"; }
git archive --format=tar.gz HEAD | vm $S 'mkdir -p /content/da26/fw && tar -xz -C /content/da26/fw'
vm $S "cd /content/da26; nohup setsid bash -c 'python3 fw/scripts/he/he1_colab.py setup --point $P; echo setup exit \$?' > setup.log 2>&1 < /dev/null &"
vm $S 'tail -2 /content/da26/setup.log'   # chờ "setup exit 0"
vm $S "cd /content/da26; nohup setsid bash -c 'Psi0/.venv-psi/bin/python fw/scripts/he/he1_colab.py train --point $P; echo train exit \$?' > train.log 2>&1 < /dev/null &"
nohup setsid bash -c 'python3 scripts/he/he1_fetch.py follow --session "$1" --registry "$0" --dest fwdata/he/runs --every 600 --stop-when-done; echo "exit $?"' $R $S < /dev/null > $R/$S.fetch.log 2>&1 &
```

Khi Hiếu đã đồng ý OAuth cho Drive, thêm hai lệnh sau `setup`. `follow` vẫn chạy như trên.

```bash
colab drivemount -s $S /content/drive
vm $S "cd /content/da26; nohup setsid python3 fw/scripts/he/he1_colab.py persist --watch 600 --pid \$(pgrep -f 'he1_colab.py [t]rain' | head -1) > persist.log 2>&1 < /dev/null &"
```

**Trong lúc chạy.**

- Xem tiến độ bằng `vm $S 'tail -1 /content/da26/runs/*/metrics.jsonl'`, `tail -1 $R/$S.jsonl` và `tail -2 $R/$S.fetch.log`.
- **Quy tắc dừng sớm, bắt buộc** (review #109). `follow` tự áp dụng; không cần người theo dõi.
  - Khi nào: mỗi lượt từ bước 2 200. Từ bước 2 200, cửa sổ đo đã có một lượt validation (bước 2 000). Trước `ckpt_10000`, vượt ngưỡng thì dừng; sau đó chỉ ghi `ALERT` mỗi lượt.
  - Tính gì: CU dự kiến đã dùng khi `ckpt_40000` ghi xong và đã kéo về laptop:
    `spent + 1,94 × (bước còn lại × s/bước + số lần lưu còn lại × 60 s + 60 s + 60 s + 6,25 GB / MB/s) / 3600 + 0,1`.
  - Hai số 60 s: khoảng cách lượt cuối (từ bước 38 000), và thời gian băm sha256 checkpoint cuối trên VM rồi trên laptop. Số thứ hai là giả định.
  - Số liệu: `spent` là dòng `poll` cuối của watcher, chỉ khi mới hơn 300 s. s/bước đo từ bước 200 của lần chạy hiện tại. MB/s lấy từ `probe`, rồi thay bằng lượt kéo checkpoint trên 1 GB gần nhất. 60 s mỗi lần lưu là giả định; trên A100 là 31 s.
  - Không tính được (không có `poll` mới, không có s/bước, `stage` hoặc rsync lỗi): `follow` ghi `ALERT` ra stderr mỗi lượt, và **không** dừng. Dừng mù làm mất phần đã tiêu, trong khi trần của watcher vẫn giới hạn chi phí. Nếu watcher ngừng đập nhịp, guard dừng phiên.
  - Ngưỡng: vượt dòng dừng của watcher, `trần − 1,94 × 430 / 3600`, tức `18 − 0,232 = 17,77` CU. `trần` lấy từ dòng `poll` của chính watcher, không ghi cứng trong `he1_fetch.py`. Vượt ngưỡng thì `follow` ghi `EARLY_STOP` kèm các số, dừng phiên có xác nhận, và thoát 3 (6 nếu không xác nhận được). Dừng ở bước 2 200 tốn khoảng 1,3 CU. Để chạm trần thì tốn khoảng 18 CU mà chỉ được `ckpt_30000`, plan không dùng tới.
  - Mức s/bước tối đa để chạy hết ở trần 18. Giả định dựng VM cộng `probe` mất 11 phút, lưu 4 lần mỗi lần 60 s, cộng 2 × 60 s ở trên:

    | Tốc độ kéo về | Thời gian kéo `ckpt_40000` | s/bước tối đa |
    |---|---|---|
    | 6 MB/s | 17,4 phút | 0,768 |
    | 10 MB/s | 10,4 phút | 0,779 |
    | 20 MB/s | 5,2 phút | 0,786 |
    | 50 MB/s | 2,1 phút | 0,791 |
    | Drive đã mount (kéo khoảng 0) | — | 0,794 |

  - Đối chiếu S1-04: 0,710 s/bước là trung vị đo được, không tính validation và lưu. Ước lượng 8,5 giờ suy ra khoảng 0,753 s/bước khi tính cả validation; `progress` cũng đo trung bình có validation, nên 0,753 là đầu vào sát thực tế. Ở 6 MB/s dự kiến 17,44 CU, dưới ngưỡng 17,77; mức này qua được từ khoảng 3,8 MB/s. Ở trần cũ 17,5 thì cần từ 8,7 MB/s. Bốn phương án đã đưa Hiếu (chia lại trần, nâng trần cứng, lưu mỗi 5 000 bước, giữ nguyên). **[Đã chốt]** Hiếu chọn chia lại trần: 18,0 / 18,0 / 16,0 (mục 6.2).
- Mã thoát của watcher và guard theo docstring của `scripts/colab/cu_watch.py`. Gặp mã 5 (`STOP_FAILED`) thì xem `colab sessions` ngay.

**Sau mỗi phiên.**

- `fwdata/he/runs/$S/fetched.json` phải có `"final": true`, tức `ckpt_40000` đã kiểm sha256 trên laptop. Nếu Drive đã mount, trên Drive cũng phải có bản này.
- **Dừng phiên ngay sau đó**, không chờ trần. `follow --stop-when-done` tự gọi `colab stop -s $S`; dừng sớm cũng gọi lệnh này. Kiểm lại: `grep '^exit' $R/$S.out` phải có dòng `exit` (watcher thấy phiên mất, mã 0), và `colab sessions` không còn `$S`. Mã thoát của `follow` là dòng cuối của `$R/$S.fetch.log` (`tail -1 $R/$S.fetch.log`, dạng `exit N`): 0 xong, 3 dừng sớm, 5 train `failed` (phiên đã dừng), 6 dừng không xác nhận được (xem `colab sessions` ngay). Nếu `follow` thoát mà phiên vẫn chạy (mã 1, 2 hoặc 6, hoặc đã thấy `"final": true` mà phiên chưa dừng), thì chạy `colab stop -s $S` bằng tay rồi kiểm lại như trên. Nếu sau một vòng poll watcher vẫn chưa thoát, gửi SIGTERM cho tiến trình watcher: nó dừng phiên có xác nhận rồi thoát mã 6.
- Dòng `exit` cuối của `$R/$S.jsonl` cho `balance_drop`, `spent`, `wall_cu`. Các số này vào dòng `measured` của [`ledger/DA-26.csv`](../g0/ledger/DA-26.csv), trỏ về dòng `estimated` cùng job.
- Server eval mở sau, trong cùng `$R`, theo đúng dạng lệnh của watcher (`--gpu L4`, `--log` và `--persist` đều bắt buộc theo quy ước). Nếu guard đã thoát, chạy lại dòng guard ở trên với `$R` trước. Driver eval ghi log server vào `/content/da26/runs/da26-t2-eval-n20/`, để `once` kéo về được (mục 7.1).

```bash
nohup setsid bash -c 'trap "" TERM HUP INT; python3 scripts/colab/cu_watch.py session --registry "$0" --new --name "$1" --gpu L4 --cap 18 --floor 14 --persist "python3 scripts/he/he1_fetch.py once --session $1 --registry $0 --dest fwdata/he/runs" --log "$0/$1.jsonl"; echo "exit $?"' $R da26-t2-eval-n20 < /dev/null > $R/da26-t2-eval-n20.out 2>&1 &
```

### 7.1 Eval tier 2: hai fine-tune N20 trên 10 điều kiện dev (F10, nhiệm vụ 3)

**Lần 1 (5/11/2026), không có episode nào.** Phiên `da26-t2-eval-n20` từ master `92526397`. Hai server nạp xong (sha256 đã kiểm, `run_dir` đúng arm). `run` bắt đầu 12:23:14Z; client thoát 1 sau 70 s, ở bước chuẩn bị, trước Isaac: `he1_client.sh` còn giữ phép kiểm của S1-03 là `/info` phải chứa tên task, mà `run_dir` của fine-tune (`fw-da26-t2-ft-…`) không chứa. `run` thoát 5, phiên dừng có xác nhận 12:26:28Z. Đo: 1,692 CU theo đồng hồ watcher, số dư giảm 1,53 CU. `probe` đo đẩy lên 5,06 MB/s (bảng dưới giả định 11 MB/s); tải lên 12,5 GB mất 37 phút, nên trước reset đầu khoảng 1,6 CU thay vì 1,0. Đã sửa: client chỉ kiểm `/info` còn trả lời (laptop đã kiểm `run_dir` của từng arm); test chạy `he1_client.sh` thật với `/info` thật của hai server (`scripts/he/testdata/`). **[Đã chốt 5/11/2026, Hiếu]** "Nâng trần cứng, giữ cap 18 (Recommended)": chạy lại với trần 18, trần cứng DA-26 thành 53,54 CU (mục 6.2). Ước lượng lần chạy lại: khoảng 1,6 CU trước reset đầu (đẩy lên khoảng 5 MB/s), rồi 9 cặp nếu episode 24,6 phút (8 cặp ở 27 phút, 7 ở 33 phút; `he1_eval.py fit`), tức khoảng 1,6 + 9 × 1,59 + 0,16 = 16,1 CU, khoảng 8,4 giờ tường; chạm dòng dừng thì 9,2 giờ. Chạy lại chỉ sau khi PR sửa đã merge và được phiên chính xem, từ `master` mới, `preflight` sạch, và có lệnh chạy của phiên chính.

Chờ đợt C của DA-34 dừng và được xác nhận (một đợt một lúc trên tài khoản), và lệnh chạy của phiên chính. Driver: [`scripts/he/he1_eval.py`](../../scripts/he/he1_eval.py) trên laptop, pha `serve-setup` và `serve` của `he1_colab.py` trên VM, [`scripts/he/he1_client.sh`](../../scripts/he/he1_client.sh) trên rtx3060.

**Cách chạy.**

- Một phiên Colab L4 `da26-t2-eval-n20`, trần 18 CU (**[Đã chốt 5/11/2026, Hiếu]**, mục 6.2), dòng dừng của watcher 17,77 CU. Hai server Ψ₀ trên VM, cổng 22085 (V-EGO) và 22086 (V-NOEGO), khoảng 6,2 GB VRAM mỗi server trên card 23 GB (S1-03). Cờ server như S1-03: `--action-exec-horizon 24 --rtc`.
- Client Isaac chạy một lần trên rtx3060, trên bản xen kẽ của bộ dev. **[Đã chốt 5/11/2026, Hiếu]** Xen kẽ theo điều kiện: episode 2i là điều kiện i cho V-EGO, 2i + 1 là cùng điều kiện cho V-NOEGO. Thứ tự arm là thứ tự các điểm `preliminary` trong RunPlan, giống nhau ở mọi điều kiện (`pair_order`, có test). Một lần chạy chỉ khởi động Isaac một lần (khoảng 4 phút), thay vì 20 lần.
- Client chỉ nhận một host và cổng, nên `route` trên laptop (127.0.0.1:22185) chọn server cho từng episode. SIMPLE gọi `agent.reset` một lần mỗi episode; `/act` kế tiếp có `history.reset`. Lần reset thứ n là episode n của bộ xen kẽ, nên `route` gửi nó và mọi `/act` sau nó tới arm của episode đó. rtx3060 tới `route` qua `ssh -R 127.0.0.1:22095` (không dùng 22085 trên rtx3060 vì story khác đang dùng). Laptop tới hai server qua một kết nối `ssh -L` (22285, 22286), vì runtime chỉ nhận một kết nối SSH mỗi lúc. Trước khi chạy client, `run` đọc `/info` của từng cổng: `run_dir` phải là fine-tune của arm đó, không thì không chạy.
- `route` thử lại lỗi kết nối tới server trong 180 s: forward ssh có thể khởi động lại, mà client SIMPLE dừng ở bất kỳ phản hồi nào khác 200 và không tự thử lại. Hết giờ chờ (server nhận mà không trả lời) thì không thử lại.
- **Quy tắc CU theo cặp.** Trước episode đầu của mỗi cặp, `route` tính CU dự kiến khi cặp đó và phần kết thúc đã xong:
  `spent + 1,94 × (tuổi số đo + 2 × episode_s + 300 s) / 3600 + 0,1`.
  - Chỉ bắt đầu cặp khi số này không vượt dòng dừng 17,77 CU, tính từ trần 18 ghi trong driver. Dòng `poll` của watcher có trần khác 18 thì từ chối. Không bao giờ dừng giữa cặp.
  - `episode_s` là số lớn hơn giữa 33 phút và 1,2 × episode dài nhất đã thấy. 33 phút là trung bình của lần chạy 10 episode của S1-03 trên rtx3060 khi máy chạy chung với DA-34 và DA-35 ([psi0-eval.md](../g0/psi0-eval.md)); một episode hỏng trên máy rảnh mất 24,6 phút. Giữ 33 phút cho tới khi đo được trên chính máy này lúc chạy (review #129). Episode nhanh hơn tiết kiệm CU nhưng không nới quy tắc.
  - `spent` là dòng `poll` cuối của watcher, chỉ khi mới hơn 300 s; nếu cũ thì chờ tối đa 600 s, rồi từ chối. 300 s cho phần kết thúc là giả định: đóng forward, kéo log VM, dừng phiên có xác nhận.
  - Bị từ chối thì `route` trả 503, dừng container client (`docker stop da26-eval-client`), `run` thoát 3. Các cặp trước đó đều đủ.
- **Phiên luôn được dừng.** Khi đã thấy phiên chạy, mọi đường ra của `run` đều qua cùng một bước kết thúc: bị từ chối, client lỗi, thiếu RAM, server sai arm, mọi ngoại lệ (cả `SystemExit`), SIGTERM, SIGINT, SIGHUP. Tín hiệu thứ hai trong lúc đang kết thúc chỉ được ghi lại, không cắt bước kết thúc. SIGHUP đã bị bỏ qua sẵn (do `nohup`) thì vẫn bỏ qua. Bước kết thúc làm theo thứ tự: kéo log VM bằng `once`, dừng phiên có xác nhận (khoản CU cuối), rồi mới kéo `client/` từ rtx3060 (không tốn CU, rsync có `ConnectTimeout` và `--timeout=120`) và ghi `results.jsonl`. Lỗi ở một bước không chặn bước sau.
- **Client chết hay treo.** Trong lúc chờ, `run` dừng client khi không có request 30 phút sau khi chạy (copy cache kit, ảnh, khởi động Isaac khoảng 4 phút), hay 15 phút sau request cuối (lớn hơn reset cộng 600 s chờ số đo). Nó cũng dừng client khi số đo cho thấy phần kết thúc sẽ vượt dòng dừng (chốt chặn; quy tắc cặp lẽ ra không để xảy ra), hay khi đã chạy lâu hơn thời gian trần 18 cho phép. Lệnh dừng giết cả nhóm tiến trình của launcher (`setsid` ghi pgid vào `client-<tag>.pgid`; chỉ giết khi nhóm đó còn chứa `he1_client.sh`), nên client đang ở bước chuẩn bị, chưa có container, cũng dừng; sau đó mới `docker stop`. Sau mỗi lần dừng, `he1_client.sh` có 600 s để chuyển file và ghi `exit` (trap EXIT vẫn chạy khi bị SIGTERM); container mất không coi là xong. Không có `exit` thì `run` vẫn kết thúc và dừng phiên.
- **Chạy lại an toàn.** Mỗi lần `run` có một tag. Mọi dòng của `route.jsonl` mang tag đó; `route.jsonl` của lần trước được giữ thành `route-<tag cũ>.jsonl`. File của client theo tag: `client-<tag>.log`, `eval/<tag>/`, `videos/<tag>/`, `summary-<tag>.json`. `results.jsonl` chỉ đọc lần `client_launch` cuối và file của đúng tag đó; mỗi lần ghi thêm `results-<tag>.jsonl`. Một lần `run` không chạy tới client (ví dụ thiếu RAM) không ghi đè kết quả cũ; kết quả của lần trước dựng lại được bằng `results --route route-<tag>.jsonl`. `preflight --dest` từ chối trước khi mở phiên nếu log cũ không giữ được.
- **Tải lên chỉ những gì server đọc**: `argv.txt`, `run_config.json` (chứa sẵn cận chuẩn hóa) và `ckpt_40000/model.safetensors`, 2 × 6,25 GB = 12,5 GB. Kèm theo là `expected.json`, ghi sha256 đã kiểm trên laptop: lấy từ cache `.hashes.json` của `he1_fetch` khi stamp (kích thước, mtime) còn khớp, không thì tính lại. Psi0 ở `cda3fdf` không đọc gì khác của run dir (không cần `*_norm_stats.json`, đã kiểm trong mã nguồn). `serve` kiểm lại sha256 trên VM trước khi nạp; lệch một file là không chạy server nào. Tải lên chạy song song với `serve-setup` (tách khỏi shell). `probe` đo cả tốc độ kéo về (1 GB) và đẩy lên (256 MB).
- **Log cho Agent QA/QC từ đầu**, tất cả trong `fwdata/he/runs/da26-t2-eval-n20/`:
  - `route.jsonl`: mọi request (episode, arm, reset, thời gian, mã trả về), mọi lần chấm cặp với các số của nó, `/info` của hai server, số RAM rtx3060, các lần tunnel khởi động lại, lý do dừng client, kết quả bước kết thúc;
  - `client/`: `client-<tag>.log`, `eval/<tag>/…/eval_stats.txt`, `videos/<tag>/`, `summary-<tag>.json`, `server_info-<tag>.json`, `exit`;
  - `server-<job>.log`, `server-<job>.info.json` (log server trên VM, kéo bằng `once`);
  - `vm-logs/`: `serve-setup.log`, `serve.log`, `report.json`, `launch-env.txt` (chỉ khóa trong allowlist, không bao giờ có khóa bí mật), `pip-freeze-serve.txt`, `nvidia-smi-q.txt`, `df-h.txt`, `free-m.txt`. Với hai fine-tune, `stage` cũng làm mới `vm-logs/` mỗi lượt, nên việc tay của đợt b3 nay là một bước của script;
  - `results.jsonl`: mỗi episode đã bắt đầu, thành công theo `eval_stats.txt`, số lần `/act`, trung vị và tối đa thời gian `/act`, `complete_pair`. Chỉ cặp đủ mới vào so sánh.
- **rtx3060.** Thư mục `~/denso-da26` (không dùng `~/denso-challenge`). Client là container ảnh SIMPLE của S1-03 (cùng digest, cùng file task `b75c678` kiểm sha256, có test so với `eval_psi0.sh`), DDS domain 126, `--memory 20g`. Lệnh chạy dưới `nohup setsid` và `systemd-run --user --scope -p MemoryMax=24G -p MemorySwapMax=0`. MemAvailable ≥ 20 + 16 = 36 GB được kiểm ba lần: `preflight` trước khi mở phiên (chỉ đọc), `run` và client ngay trước khi chạy; thiếu thì không chạy client. Tiến trình `pol.train_stage_a` 10 GB là dự án khác của Hiếu, không động vào. Giờ chạy hẹn với DA-35 qua phiên chính.

**Mấy cặp vừa trần 18** (`he1_eval.py fit`, có test). Số đo đang có: kéo về 11,0–11,25 MB/s (`probe` và lượt kéo `ckpt_40000` của b3); một episode hỏng 24,6 phút trên máy rảnh, trung bình 33 phút khi máy chạy chung (S1-03). Tốc độ đẩy lên chưa đo; bảng giả định bằng tốc độ kéo về. Trước lần reset đầu khoảng 1,0 CU (ước lượng, khoảng 31 phút): watcher và `probe` 4 phút, triển khai 0,5 phút, tải lên 12,5 GB ở 11 MB/s 19 phút (`serve-setup` khoảng 8 phút chạy song song), nạp hai server 3 phút, khởi động Isaac 4 phút. Quy tắc luôn tính mỗi episode ít nhất 33 phút (giữ nguyên theo phiên chính), nên cặp chạy nhanh vẫn được chấm như cặp 66 phút; episode chậm thì dừng ở cặp đủ, không cắt giữa cặp.

| CU đã dùng ở lần reset đầu | Episode thật 33 phút | 27 phút | 24,6 phút | 22 phút | 20 phút |
|---|---|---|---|---|---|
| 0,6 | 7 | 9 | 10 | 10 | 10 |
| 0,9 | 7 | 9 | 10 | 10 | 10 |
| 1,0 (dự kiến) | 7 | 9 | **10** | 10 | 10 |
| 1,2 | 7 | 9 | 9 | 10 | 10 |
| 1,5 | 7 | 8 | 9 | 10 | 10 |

- **[Đã chốt 5/11/2026, Hiếu]** "Nâng lên 18 + giữ rtx3060" (phương án (b) cùng (d) của bản trước): trần 18, rtx3060 chỉ chạy client trong khung giờ eval. Ở 24,6 phút mỗi episode và khoảng 1,0 CU trước reset đầu thì đủ **10 cặp**.
- **Biên mỏng.** Cặp thứ 10 chỉ được bắt đầu khi phần trước reset đầu không quá 1,055 CU (khoảng 32,6 phút) và mọi episode không quá 24,7 phút. Ví dụ: 1,2 CU (đẩy lên chậm hơn khoảng 8 MB/s) hay vài episode dài hơn 25 phút là còn 9 cặp. Máy chạy chung như S1-03 (33 phút) thì 7 cặp.
- Ước lượng ở 10 cặp: 1,0 + 10 × 1,59 + 0,16 = 17,1 CU, dưới dòng dừng 17,77.
- **Giữ rtx3060.** Trước khi mở phiên, `preflight` từ chối (thoát 6) khi trên rtx3060 có tiến trình denso khác (`pgrep -af denso`) hay `pol.train_stage_a` còn chạy. Ngay trước khi chạy client, `run` kiểm lại; nếu có thì không chạy client, dừng phiên, thoát 8. Container docker không thuộc denso (ví dụ `hsk_*`) chỉ được ghi vào log và báo `ALERT`, không chặn. Phiên chính báo DA-35 không chạy gì trong khung giờ này; `pol.train_stage_a` là dự án khác của Hiếu, còn chạy thì báo phiên chính để hỏi Hiếu.

**Lệnh** (thư mục gốc là bản checkout `master`, `ready` và `vm` như trên, `S=da26-t2-eval-n20`). Số dư cần ít nhất sàn 14 + trần 18 = 32 CU.

Trước khi mở phiên, dựng bộ xen kẽ, chép lên rtx3060 và kiểm rtx3060 (chỉ đọc). `preflight` thoát 0 mới mở phiên: 4 thiếu RAM, 5 thiếu `fw/`, bộ khác, hay client còn chạy, 6 rtx3060 còn job khác (denso hay `pol.train_stage_a`): khi đó không mở phiên, báo phiên chính.

```bash
S=da26-t2-eval-n20
python3 scripts/he/he1_eval.py interleave --src fwdata/he/dev-eval-v1-l0n10 --out fwdata/he/eval-n20-interleaved
git archive --format=tar.gz HEAD | ssh rtx3060 'mkdir -p ~/denso-da26/fw ~/denso-da26/sets && tar -xz -C ~/denso-da26/fw'
rsync -a fwdata/he/eval-n20-interleaved/ rtx3060:denso-da26/sets/interleaved/
python3 scripts/he/he1_eval.py preflight --set fwdata/he/eval-n20-interleaved --dest fwdata/he/runs
```

Sau đó guard và watcher như khối ở trên, `--cap 18`, rồi:

```bash
ready $S && python3 scripts/he/he1_eval.py probe --session $S --registry $R --dest fwdata/he/runs \
  || { colab stop -s $S; echo "$S: not ready or probe failed, session stopped"; }
git archive --format=tar.gz HEAD | vm $S 'mkdir -p /content/da26/fw && tar -xz -C /content/da26/fw'
vm $S "cd /content/da26; nohup setsid bash -c 'python3 fw/scripts/he/he1_colab.py serve-setup; echo serve-setup exit \$?' > serve-setup.log 2>&1 < /dev/null &"
python3 scripts/he/he1_eval.py upload --session $S --registry $R --runs fwdata/he/runs   # song song với serve-setup
vm $S 'tail -1 /content/da26/serve-setup.log'   # chờ "serve-setup exit 0"
vm $S "cd /content/da26; nohup setsid bash -c 'python3 fw/scripts/he/he1_colab.py serve; echo serve exit \$?' > serve.log 2>&1 < /dev/null &"
vm $S 'tail -1 /content/da26/serve.log'   # chờ "serve exit 0": hai server trả /health
python3 scripts/he/he1_eval.py preflight --set fwdata/he/eval-n20-interleaved --dest fwdata/he/runs   # kiểm lại RAM và job khác ngay trước
nohup setsid bash -c 'python3 scripts/he/he1_eval.py run --session "$1" --registry "$0" --dest fwdata/he/runs --set fwdata/he/eval-n20-interleaved; echo "exit $?"' $R $S < /dev/null > $R/$S.eval.log 2>&1 &
```

- `run` tự làm phần còn lại, không cần người. Mã thoát (dòng cuối `$R/$S.eval.log`): 0 đủ mọi cặp; 3 một cặp bị quy tắc CU từ chối; 4 rtx3060 thiếu RAM; 5 client, server hay forward lỗi, hoặc `run` gặp ngoại lệ; 6 dừng phiên không xác nhận được (xem `colab sessions` ngay); 7 bị tín hiệu dừng; 8 rtx3060 còn job khác, client không chạy. Trừ mã 6, phiên đều đã dừng có xác nhận.
- Trong lúc eval, forward giữ kết nối SSH duy nhất, nên lượt `--persist` của watcher ở mốc mềm có thể bị từ chối (HTTP 429). Không sao: `run` kéo log VM sau khi đóng forward.
- Xem tiến độ: `tail -3 fwdata/he/runs/da26-t2-eval-n20/route.jsonl`, `tail -1 $R/$S.jsonl`.
- Bộ xen kẽ dựng ngày 5/11/2026 từ bộ dev thật: 20 episode, `order.json` sha256 `6d764478…`; test kiểm từng episode trùng điều kiện của nó (`environment_config`) và hash điều kiện của RunPlan.
- Thử khô trên laptop, CPU, không Colab, không ghi gì lên rtx3060: [`test_he1_eval.py`](../../scripts/he/test_he1_eval.py) có 48 test, gồm:
  - thứ tự xen kẽ; bộ xen kẽ trên bộ giả và trên bộ dev thật;
  - quy tắc CU (vừa, vượt, episode chậm nâng cận, số đo cũ hay thiếu, trần của watcher khác 16); cổng chờ số đo; đọc dòng `poll`; mấy cặp vừa;
  - `route` qua HTTP với hai server giả; thử lại lỗi kết nối;
  - tải lên với cache `.hashes.json` đúng định dạng của `he1_fetch`, và `serve` chấp nhận nó; cache cũ hay sai định dạng thì tính lại;
  - `run` trên đồ giả: thiếu RAM, ngoại lệ, SIGTERM, server sai arm, chạy client lỗi, dừng không xác nhận, và một lượt đủ (log theo tag, giữ log cũ, kết quả chỉ của lượt cuối). Mọi trường hợp đều dừng phiên, theo thứ tự log VM, dừng phiên, rồi rtx3060;
  - client không gọi, im lặng, máy không tới được, quá dòng CU; sau khi bị từ chối vẫn chờ `exit`; `preflight` chỉ đọc; rtx3060 còn job denso hay `pol.train_stage_a` thì không chạy (`preflight` 6, `run` 8), container khác chỉ ghi log;
  - `vm-logs`, `serve` với launcher giả, ghim của client trùng `eval_psi0.sh`;
  - sau lần 1: `he1_client.sh` thật, sau `route` thật, với `/info` thật của hai server, qua bước kiểm `/info` (bản cũ thì hỏng đúng lỗi của lần 1); `results` đọc `eval_stats.txt` thật của S1-03, và dòng có lý do kết thúc của `sonic_wbc.py`.

  - review lại #129: `SystemExit` và log cũ không giữ được vẫn dừng phiên; tín hiệu thứ hai không cắt bước kết thúc; SIGHUP bỏ qua sẵn giữ nguyên; lần chạy không tới client giữ kết quả cũ; lệnh dừng thật (chạy ở máy này với `HOME` tạm, `systemd-run` và `docker` giả) giết nhóm của launcher đang ở bước chuẩn bị và không đụng nhóm khác.

  Kiểm đột biến: bỏ sửa định dạng cache, trả về khi container mất, bỏ bước kết thúc khi thiếu RAM, bắt `Exception` thay vì `BaseException`, ghi đè SIGHUP đã bỏ qua, bỏ lệnh giết nhóm, cho tín hiệu thứ hai cắt ngang. Mỗi đột biến làm test hỏng.

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 4/11/2026 | Bản nháp: thiết lập, kiểm checkpoint, ước lượng, quy tắc diễn giải, câu hỏi chốt và chi phí | Hiếu (soạn với Claude) |
| 4/11/2026 | Eval chính chuyển sang bộ dev 30 × 3 (Hiếu chốt); thêm mục 1.2 cách dựng và kiểm; chế độ và đồng hồ chờ S1-03; chi phí theo 90 episode mỗi điểm, số dư 101,8 CU | Hiếu (soạn với Claude) |
| 4/11/2026 | Q3: ghi kết quả Q-27C của S1-03; RunPlan đề xuất `mujoco_isaac`, giờ sim, chờ ký (`eval.awaiting`); phương án A ghi là yếu; thêm mục 6.1 phương án F (Isaac, mức 0, N = 20, 10 hoặc 30 điều kiện) với CU, giờ và độ nhạy Fisher | Hiếu (soạn với Claude) |
| 4/11/2026 | Tier 2 (Hiếu: "Approve tier 2"): mục 6.2 quyết định và trần CU từng job; eval chính còn 10 điều kiện mức 0 (`b63acd59…`), `mujoco_isaac`, giờ sim; sơ bộ chỉ N = 20; quy tắc đọc sơ bộ theo Fisher và độ nhạy 10 mỗi nhánh; Q3, Q4 đã chốt; đóng băng | Hiếu (soạn với Claude) |
| 4/11/2026 | Review của #99: đầu file ghi đã chốt; mốc so không chạy trên bộ dev ở tier 2 (mục 1); mục 6.2 tả watcher mới (hai đồng hồ, kiểm L4, dừng có xác nhận, laptop phải thức); `Decision` ghi lại với `embodiment_id` `g1_sonic_dwbc@1` (`dec_01M6KG4JFTRWGQ91CD3H1TC1XX`, cùng `rp_95c98a476499`) | Hiếu (soạn với Claude) |
| 4/11/2026 | Mục 6.2: chạy bằng watcher chung `scripts/colab/cu_watch.py` (trần 17,5 / 17,5 / 17,0 CU, `--floor 14`); bỏ watcher riêng của DA-26 | Hiếu (soạn với Claude) |
| 4/11/2026 | Mục 6.2: watcher chung đổi thiết kế (#108): mỗi phiên một watcher theo endpoint, một guard cho đợt; một đợt một lúc trên tài khoản, DA-30 chạy trước rồi đến DA-26 | Review #108 |
| 4/11/2026 | Mục 7: cách chạy hai fine-tune N20 của tier 2. Driver VM `scripts/he/he1_colab.py` kiểm sha256 của cha, zip và `episodes.jsonl` trước khi train; tập demo riêng có stats riêng, dựng bằng `scripts/he/demo_subset.py` (đã kiểm trên zip thật); khối lệnh laptop gồm guard, hai watcher (17,5 / 17,5 CU, `--floor 14`) và `ready`, `vm`; quy tắc dừng sớm đề xuất. Chưa chạy | Hiếu (soạn với Claude) |
| 4/11/2026 | Mục 7: bản bền trên laptop khi chưa mount được Drive (`scripts/he/he1_fetch.py`: rsync qua `colab ssh --proxy-mode`, kiểm sha256; `follow` cạnh mỗi phiên, `once` ở mốc mềm). Lý do không dùng `colab download`; `persist` từ chối khi Drive chưa mount; ngưỡng tốc độ 6 MB/s và `ALERT`; kết quả thử khô | Hiếu (soạn với Claude) |
| 4/11/2026 | Mục 7, theo review #109: `setup` chỉ dựng môi trường, không tải hai lần; đo tốc độ proxy (`probe`) trước `setup`; quy tắc dừng sớm thành bắt buộc, `follow` tự áp dụng, có bảng ngưỡng s/bước theo MB/s và đối chiếu S1-04; bốn **[Option]** về trần cho Hiếu; dừng phiên ngay khi có `ckpt_40000`; lệnh watcher của server eval đủ `--gpu`, `--log`, `--persist`; `rp_95c98a476499` ghi cứng trong driver; bỏ ô persist kernel | Hiếu (soạn với Claude) |
| 5/11/2026 | Mục 7, theo review lại #109: train chỉ `done` khi `ok` ở bước 40 000, `failed` dừng phiên và thoát 5; tốc độ và `ALERT` chỉ tính trên file checkpoint, log được ghi thêm là `grown`; `ready` trả 1 khi chưa sẵn sàng; mọi lần dừng có xác nhận (thử lại, SIGTERM, thoát 6), mọi lệnh có thời hạn; dự báo tính thêm khoảng cách lượt cuối và thời gian băm, bảng ngưỡng tính lại, từ bước 38 000 mỗi lượt cách 60 s; không tính được dự báo thì `ALERT` mỗi lượt, sau `ckpt_10000` chỉ `ALERT`; file `probe` ra khỏi `$R` | Hiếu (soạn với Claude) |
| 5/11/2026 | Mục 6.2, 7: **[Đã chốt 5/11/2026, Hiếu]** caps 18/18/16 (cùng 52 CU). Lệnh watcher `--cap 18` / `--cap 18` / `--cap 16`. Bảng ngưỡng tính lại ở trần 18. Số dư tối thiểu vẫn 66 CU. Ghi chú: trần eval 16 thấp hơn ước lượng 16,2; **[Đã chốt 5/11/2026, Hiếu]** eval xen kẽ hai arm theo điều kiện | Hiếu (soạn với Claude) |
| 5/11/2026 | Mục 7, theo review lại lần hai #109: `stage` có trạng thái cho cả lần chạy, nên train chết trước khi có `runs/<job>` là `failed` (thoát 5); lần liệt kê phiên chỉ tính khi tin được như `cu_watch.py`, lỗi xác thực không còn được coi là đã dừng; SIGTERM chỉ tới tiến trình `cu_watch.py` còn sống; dòng `follow` ghi `exit N` vào `$R/$S.fetch.log` | Hiếu (soạn với Claude) |
| 5/11/2026 | Mục 4: thêm giới hạn của N20, một bàn tay (chiều action 0–6) không cử động. Ghi số đo của lần chạy b2 bị hủy vào sổ chi phí | Hiếu (soạn với Claude) |
| 5/11/2026 | Mục 7.1: cách chạy eval tier 2. Xen kẽ hai arm theo điều kiện (`he1_eval.py`, `route` chọn server theo lần reset); quy tắc CU theo cặp, không dừng giữa cặp; chỉ tải lên file server đọc, kiểm sha256 trên VM; log cho Agent QA/QC trong `runs/da26-t2-eval-n20/`; `vm-logs` thành bước của script; client rtx3060 dưới `systemd-run` MemoryMax. Ở số đo hiện có chỉ 9 cặp vừa trần 16; ba **[Option]** cho Hiếu. Chưa chạy | Hiếu (soạn với Claude) |
| 5/11/2026 | Mục 7.1, theo review #129: cache sha256 đọc đúng định dạng của `he1_fetch`; phiên luôn được dừng (thiếu RAM, ngoại lệ, tín hiệu), `preflight` kiểm rtx3060 trước khi mở phiên; client chết hay treo thì dừng, có hạn chờ; cận episode 33 phút hoặc 1,2 × dài nhất; kết thúc theo thứ tự log VM, dừng phiên, rtx3060; thử lại lỗi kết nối 180 s; chạy lại an toàn theo tag; kiểm `/info` của hai server. Trần 16 còn 6–8 cặp; bốn **[Option]** cho Hiếu. Chưa chạy | Hiếu (soạn với Claude) |
| 5/11/2026 | Mục 6.2, 7, 7.1: **[Đã chốt 5/11/2026, Hiếu]** "Nâng lên 18 + giữ rtx3060": trần eval 18 (dòng dừng 17,77), watcher `--cap 18`, tổng DA-26 nhiều nhất 33,85 + 18 = 51,85 CU; rtx3060 chỉ chạy client trong khung giờ eval (`preflight` thoát 6, `run` thoát 8 khi còn job denso hay `pol.train_stage_a`). Bảng cặp tính lại ở trần 18: 10 cặp ở 24,6 phút, biên mỏng (cần ≤ 1,055 CU trước reset đầu). Quy tắc cặp giữ nguyên | Hiếu (soạn với Claude) |
| 5/11/2026 | Mục 7.1, theo review lại #129: bước kết thúc (dừng phiên) chạy cả khi `SystemExit` hay tín hiệu thứ hai; `preflight --dest` kiểm log cũ trước khi mở phiên; `results-<tag>.jsonl`, lần chạy không tới client không ghi đè kết quả; SIGHUP bỏ qua sẵn giữ nguyên; lệnh dừng giết nhóm tiến trình của launcher (pgid) rồi mới `docker stop` | Hiếu (soạn với Claude) |
| 5/11/2026 | Mục 7, 7.1: lần eval 1 dừng ở bước chuẩn bị của client (phép kiểm tên task trên `/info` chép từ S1-03), 1,692 CU; bỏ phép kiểm đó; `mkdir -p ~/denso-da26/sets` trước rsync; venv của CLI `colab` để cuối `PATH`; `results` chỉ đọc chữ đầu của kết quả episode | Hiếu (soạn với Claude) |
| 5/11/2026 | Mục 6.2, 7.1: **[Đã chốt 5/11/2026, Hiếu]** "Nâng trần cứng, giữ cap 18 (Recommended)": trần cứng DA-26 từ 52 lên 53,54 CU (33,85 + 1,692 lần eval 1 + 18); lần chạy lại giữ trần 18, quy tắc theo cặp và thứ tự xen kẽ; ước lượng khoảng 16,1 CU (9 cặp ở 24,6 phút) | Hiếu (soạn với Claude) |
