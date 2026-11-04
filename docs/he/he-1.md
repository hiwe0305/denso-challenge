# HE-1: prior egocentric và số demo robot trên task hai bàn (DA-26)

_Bản nháp 4/11/2026, **chưa chốt**: chốt khi Hiếu ký `Decision` `plan_review` (mục 5). Eval chính là bộ dev của đội (mục 1.2). Story [DA-26](../product/stories/DA-26-thi-nghiem-he-egocentric.md) nhiệm vụ 1, 2; [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 7; [spec](../spec-v10-failure-to-data.md) mục 3 (HE), 7.5, 7.9. RunPlan: [`he-1.yaml`](../../configs/runplans/he/he-1.yaml); tập demo: [`demo_sets.json`](../../configs/runplans/he/demo_sets.json)._

Quy tắc ở mục 2–3 **không đổi sau khi thấy kết quả** (ghi chú của story). Muốn đổi thì viết RunPlan mới kèm `Decision`, và báo kết quả theo cả quy tắc cũ lẫn mới. Sau khi đóng băng, `he1_plan.py check` báo lỗi nếu `he-1.yaml` khác bản trong `he-1.lock.json`.

```bash
uv run python scripts/he/he1_plan.py check configs/runplans/he/he-1.yaml
uv run python scripts/he/he1_plan.py parents configs/runplans/he/he-1.yaml
uv run pytest scripts/he -q
```

## 1. Thiết lập

| Biến thể | Checkpoint gốc (psi-model `cb1480f`) | Dữ liệu egocentric khi pretrain | Chạy trước demo |
|---|---|---|---|
| V-EGO | `pre.fast.1by1.2601091803.ckpt.ego200k.he30k` + `postpre.1by1.pad36.2601131206.ckpt.he30k` | EgoDex đủ, cộng HE | N = 20, 80 |
| V-NOEGO | `pre.abl.only.he.2512311516.48k` + `postpre.abl.only.he.2602050012` | Chỉ HE | N = 20, 80 |
| V-EGO10 (tùy chọn) | `pre.abl.ego.10per.2602021632.46k` + `postpre.abl.ego.10per.2602050006` | 10% EgoDex | Không; sau demo nếu còn ngân sách |

- **Dữ liệu robot**: gói teleop task hai bàn của tác giả, `psi-data` `e78fb93`, `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (sha256 `6cdf9022…`), 99 episode, cả 99 đạt QA của [S1-07](../g0/psi-data.md) (N_teleop = 99 ≥ 80, nên điểm cuối lưới là 80). Train giữ bản `e78fb93` tới sau 13/11/2026 ([psi-data.md mục 4.1](../g0/psi-data.md)).
- **Tập demo** lồng nhau N10 ⊂ N20 ⊂ N40 ⊂ N80, chọn tất định bằng `flywheel_psi0.tray.demo_sets` của DA-34: xếp episode theo sha256(muối | sha256 của zip | `episode_index`), tập n là n episode đầu. Gói không có seed (S1-07, V6), nên khóa là `episode_index` trong zip đã ghim. Hash: N10 `53b361e2…`, N20 `cf4d6e2c…`, N40 `a88f9b6f…`, N80 `3bfc858b…`. Mọi biến thể dùng cùng tập ở cùng N.
- **Loại episode 0–9 khỏi kho chọn** [Đề xuất]. Bộ eval `e78fb93` của tác giả đặt robot, vật và khay của điều kiện i đúng như episode train i ở mức 0, 1, và robot như episode train i ở mức 2 ([S1-03](../product/stories/S1-03-tai-tao-danh-gia-psi0.md) mục 3.1 của `psi0-eval.md`, S1-07 mục 4). Eval chính của HE nay là bộ dev (mục 1.2), không dính chuyện này. Nhưng bộ của tác giả vẫn dùng làm bộ phụ (mốc so, video). Nếu để 0–9 trong kho, N80 dễ chứa điều kiện của bộ phụ hơn N20. Kho còn 89 episode, vẫn ≥ 80, nên loại không tốn gì.
- **Recipe** chung: [`psi0-stage3.yaml`](../../configs/models/psi0-stage3.yaml) (40.000 bước, batch 16 trên một GPU, lr 1e-4 cosine, VLM đóng băng, RTC), ghi đè duy nhất `train.validation_steps: 2000` theo quyết định của Hiếu ở [S1-04 mục 4.1](../g0/psi0-finetune-cost.md). Máy: một Colab L4. Seed train 0 (seed 1 chỉ ở đủ lưới). `stats_psi0.json` của mỗi điểm tính trên chính N episode của điểm đó [Đề xuất], như DA-34. Ψ₀ ở `cda3fdf` không lọc episode, nên mỗi tập cần một dataset LeRobot con (việc của nhiệm vụ 3).
- **Eval chính**: 30 điều kiện × 3 mức từ dải dev của đội, seed 1 000 100–1 000 129, như nhau cho mọi điểm (Hiếu chốt 4/11/2026: dùng dải dev, không dùng bộ của tác giả). Cách dựng ở mục 1.2. `eval-decoupled-wbc`, đồng bộ (design mục 8.5), 1 lượt mỗi điều kiện, 90 episode mỗi điểm. Chế độ (`mujoco` hay `mujoco_isaac`) và đồng hồ (giờ sim hay giờ tường) để "pending" cho tới khi S1-03 chạy Ψ₀ ở `mujoco` trên `e78fb93` (Q-27C); `freeze` từ chối khi còn trường pending (câu Q3).
- **Bộ phụ**: `simple-eval` của tác giả ở `e78fb93` (sha256 `8a4b0ff7…`), 10 điều kiện mỗi mức. Chỉ dùng cho mốc so và để đối chiếu số công bố 7/5/6. Không đọc số HE nào trên bộ này.
- **Mốc so (AC 3)**: checkpoint hai bàn của tác giả `…betweentablesteleop-v0…b64.gpus4.2604081126/ckpt_40000` (sha256 `c69c2ae8…`), fine-tune từ cặp của V-EGO trên cả 99 episode, 16 × 4 GPU. Eval trên bộ dev như mọi điểm. Số của S1-03 trên bộ của tác giả (Isaac mức 0: 6/10, công bố 7/10) báo bên cạnh, không thay thế.

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
- CI 95%: bootstrap theo điều kiện, lấy mẫu lại trong từng mức (30 mỗi mức), 10.000 lần, hạt giống 20261104, khoảng phân vị; cùng chỉ số lấy mẫu cho hai biến thể. Ở N có hai seed (đủ lưới) dùng bootstrap phân cấp của spec mục 7.5: lấy mẫu lại seed trước, rồi điều kiện.
- **N₅₀** [Đề xuất]: nội suy tuyến tính theo log₂ N giữa hai điểm lưới liền nhau mà đường cong cắt 50% lần đầu. Đạt ≥ 50% ở N nhỏ nhất đã chạy thì N₅₀ ≤ N đó; chưa tới 50% ở N = 80 thì N₅₀ > 80 (bị chặn). So N₅₀ của hai biến thể chỉ khi ít nhất một bên xác định: V-EGO xác định và V-NOEGO > 80 tính là V-EGO nhỏ hơn; cả hai > 80 là không xác định.
- Lượt hỏng do hạ tầng (server lỗi, sim sập, mất kết nối) không tính là thất bại của policy: chạy lại cùng điều kiện và báo số lần chạy lại.
- **Độ nhạy của bản sơ bộ** (ước lượng, chưa đo): 90 điều kiện, 1 lượt. Giả sử p ≈ 50% và hai biến thể gần độc lập theo điều kiện. Khi đó độ lệch chuẩn của hiệu ở một điều kiện khoảng 0,7, sai số chuẩn khoảng 0,074, và nửa độ rộng CI khoảng 15 điểm %. Bản sơ bộ chỉ thấy được chênh lệch cỡ 15 điểm % trở lên. CI chứa 0 không phải bằng chứng "không có tác dụng".

## 3. Quy tắc diễn giải

Kiểm theo thứ tự; quy tắc 0 chặn mọi quy tắc sau.

| # | Điều kiện | Đọc là |
|---|---|---|
| 0 | Mốc so của tác giả, hoặc cả hai biến thể ở mọi N đã chạy, dưới 10% trên bộ eval chính | Pipeline eval hoặc renderer chưa đủ để đo (S1-03, Q-27C). Không so biến thể; ghi `Decision` |
| 1 | Cận dưới CI của (V-EGO − V-NOEGO) > 0 ở ít nhất 2 mức N, **và** N₅₀(V-EGO) < N₅₀(V-NOEGO) | **HE đạt** (spec mục 3) |
| 2 | Cận trên CI của (V-EGO − V-NOEGO) < 0 ở ít nhất 1 mức N, hoặc N₅₀(V-NOEGO) < N₅₀(V-EGO) mà không mức N nào có cận dưới > 0 | **HE âm**: kết quả hợp lệ, phải báo, kèm giải thích có thể (task trong sim gần HE hơn EgoDex; khác biệt chỉ rõ ở N nhỏ hơn lưới) |
| 3 | Còn lại (mọi CI chứa 0, hoặc dấu khác nhau giữa các N) | Không kết luận; báo từng CI và N₅₀ |

**Bản sơ bộ (AC 6).** Chỉ có N = 20 và N = 80, nên "ít nhất 2 mức N" ở quy tắc 1 nghĩa là cả hai. Kết quả sơ bộ gắn nhãn "sơ bộ" ở mọi bảng, hình và câu trên slide; không gọi là kết luận HE. Kết luận HE chỉ đọc trên đủ lưới (bốn N, seed thứ hai ở N = 20, 40).

**Quy tắc phụ, không quyết định kết luận**: hiệu theo từng mức; tỉ lệ đạt từng bước của scorer; V-EGO10 so với V-NOEGO (đủ lưới) báo là kết quả mô tả.

## 4. Giới hạn (design mục 7.2)

- Ba biến thể khác nhau cả số bước pretrain (200k + 30k, 46k, 48k) và mỗi biến thể có action expert post-train riêng. Đội không tách được tác dụng của EgoDex khỏi hai yếu tố này; câu hỏi gửi PSI Lab ở Q-27E của S1-03.
- Batch toàn cục 16 trên một GPU, so với 64 của checkpoint tác giả (S1-04 mục 1.4); số tuyệt đối của điểm HE vì vậy có thể thấp hơn mốc so.
- Bộ eval chính là điều kiện mới, rút từ cùng phân phối DR với dữ liệu train. Nó đo tổng quát hóa trong phân phối, khác bộ của tác giả (mức 0, 1 là cảnh train). Vì vậy số của mốc so trên bộ dev không so thẳng được với 7/5/6 công bố.
- Kết quả trong sim; không suy ra số trên robot thật.

## 5. Việc cần Hiếu chốt trước khi đóng băng

| # | Câu hỏi | Trạng thái |
|---|---|---|
| Q1 | Loại episode 0–9 khỏi kho chọn demo? | [Đề xuất] Có (mục 1) |
| Q2 | Bộ eval chính | **[Đã chốt]** (Hiếu, 4/11/2026): dải dev của đội; bộ của tác giả chỉ là bộ phụ. Đã dựng (mục 1.2) |
| Q3 | Chế độ eval (`mujoco` hay `mujoco_isaac`) và đồng hồ (giờ sim hay giờ tường) | Chờ lượt Ψ₀ ở `mujoco` trên `e78fb93` của S1-03 (Q-27C). Ở `mujoco_isaac`, mức 0 của S1-03 đạt 6/10, công bố 7/10. Với 90 điều kiện mỗi điểm, Isaac không vừa (mục 6) |
| Q4 | Ngân sách CU và số lần fine-tune | Hiếu đang quyết; mọi Colab đã dừng, số dư khoảng 101,8 CU |

Khi Q1, Q3, Q4 xong: sửa RunPlan nếu cần, rồi

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
| A · 4 lần R1, eval dev ở `mujoco` | 66 CU | 8–11 giờ `rtx3060`, 0 CU | **66** | Có, nếu Q3 cho phép `mujoco` |
| B · như A, cộng video Isaac (design 7.6: vài điều kiện, ba cột, hai mức N) | 66 CU | thêm khoảng 10 episode, 4 giờ, 8 CU | **74** | Có |
| C · 4 lần R1, eval dev ở `mujoco_isaac` | 66 CU | khoảng 185 giờ, 360 CU | **426** | Không vừa cả giờ lẫn CU |
| D · chỉ N = 80 (2 lần R1), eval `mujoco` | 33 CU | 0 CU | **33** | Không: AC 6 cần N = 20 và 80 |
| E · 4 lần, 20.000 bước | khoảng 35 CU | như A | **35** | Có, nhưng đổi recipe mà Hiếu đã chốt R1 |

Số dư khoảng 101,8 CU (4/11/2026). Fine-tune của DA-34 (khoảng 66 CU) dùng chung số dư này, và Hiếu đang quyết cắt bớt số lần fine-tune. [Đề xuất] Eval dev chỉ khả thi ở `mujoco`. Nếu Q3 cho thấy `mujoco` thấp hơn Isaac nhiều, eval chính phải giảm số điều kiện hoặc dời sang sau demo; quyết định đó ghi `Decision` (AC 8).

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 4/11/2026 | Bản nháp: thiết lập, kiểm checkpoint, ước lượng, quy tắc diễn giải, câu hỏi chốt và chi phí | Hiếu (soạn với Claude) |
| 4/11/2026 | Eval chính chuyển sang bộ dev 30 × 3 (Hiếu chốt); thêm mục 1.2 cách dựng và kiểm; chế độ và đồng hồ chờ S1-03; chi phí theo 90 episode mỗi điểm, số dư 101,8 CU | Hiếu (soạn với Claude) |
