# HE-1: prior egocentric và số demo robot trên task hai bàn (DA-26)

_Bản nháp 4/11/2026, **chưa chốt**: chốt khi Hiếu ký `Decision` `plan_review` (mục 5). Story [DA-26](../product/stories/DA-26-thi-nghiem-he-egocentric.md) nhiệm vụ 1, 2; [design 27/10/2026](../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 7; [spec](../spec-v10-failure-to-data.md) mục 3 (HE), 7.5, 7.9. RunPlan: [`he-1.yaml`](../../configs/runplans/he/he-1.yaml); tập demo: [`demo_sets.json`](../../configs/runplans/he/demo_sets.json)._

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
- **Loại episode 0–9 khỏi kho chọn** [Đề xuất]. Bộ eval `e78fb93` đặt robot, vật và khay của điều kiện i đúng như episode train i ở mức 0, 1, và robot như episode train i ở mức 2 ([S1-03](../product/stories/S1-03-tai-tao-danh-gia-psi0.md) mục 3.1 của `psi0-eval.md`, S1-07 mục 4). Nếu để chúng trong kho, N80 có xác suất chứa các điều kiện eval cao hơn N20, và đường cong theo N lẫn hiệu ứng "đã thấy điều kiện". Kho còn 89 episode, vẫn ≥ 80.
- **Recipe** chung: [`psi0-stage3.yaml`](../../configs/models/psi0-stage3.yaml) (40.000 bước, batch 16 trên một GPU, lr 1e-4 cosine, VLM đóng băng, RTC), ghi đè duy nhất `train.validation_steps: 2000` theo quyết định của Hiếu ở [S1-04 mục 4.1](../g0/psi0-finetune-cost.md). Máy: một Colab L4. Seed train 0 (seed 1 chỉ ở đủ lưới). `stats_psi0.json` của mỗi điểm tính trên chính N episode của điểm đó [Đề xuất], như DA-34. Ψ₀ ở `cda3fdf` không lọc episode, nên mỗi tập cần một dataset LeRobot con (việc của nhiệm vụ 3).
- **Eval**: bộ `simple-eval` của tác giả ở `e78fb93` (sha256 `8a4b0ff7…`), mức 0, 1, 2, mỗi mức 10 điều kiện; `eval-decoupled-wbc`, đồng bộ (design mục 8.5). Sơ bộ: 1 lượt mỗi điều kiện, 30 episode mỗi điểm. Đủ lưới: 3 lượt (`--pass 1..3`, như S1-03), lượt 1 chung cho mọi điểm. Renderer `mujoco_isaac` theo câu trả lời tạm của S1-03 cho Q-27C; chuyển sang `mujoco` là một `Decision` trước khi chốt (mục 5, câu Q3).
- **Lệch so với AC 1** ("30 điều kiện dev × 3 mức có hạt giống"): bộ eval của tác giả chỉ có 10 điều kiện mỗi mức, và đội chưa có công cụ sinh điều kiện dev mới cho task hai bàn; sinh thêm thì mất phép so với mốc của tác giả. Ghi thành `Decision` (mục 5, câu Q2).
- **Mốc so (AC 3)**: checkpoint hai bàn của tác giả `…betweentablesteleop-v0…b64.gpus4.2604081126/ckpt_40000` (sha256 `c69c2ae8…`), fine-tune từ cặp của V-EGO trên cả 99 episode, 16 × 4 GPU. Lấy từ S1-03 nếu cùng bộ eval, cùng renderer, cùng file task SIMPLE `b75c678`. Checkpoint này đã thấy episode 0–9, nên ở mức 0, 1 nó được eval trên điều kiện đã thấy; điểm HE thì không.

### 1.1 Kiểm checkpoint (nhiệm vụ 2)

`he1_plan.py parents` (4/11/2026) hỏi API cây thư mục của Hugging Face ở revision ghim và đọc header safetensors bằng hai yêu cầu range, không tải trọng số:

| Kiểm | Kết quả |
|---|---|
| sha256 LFS của 6 file trọng số ablation, checkpoint mốc so, gói train, gói eval | Khớp RunPlan, `problems` rỗng |
| Header safetensors của VLM | Cả ba biến thể: 625 tensor, cùng tên, dtype, shape |
| Header safetensors của action header | Cả ba: 181 tensor, cùng tên, dtype, shape |
| `config.json` của VLM | Giống từng byte ở cả ba |

`finetune-simple-psi0.sh` không còn ở Ψ₀ `cda3fdf`; `Psi0Trainer` của DA-19 gọi `scripts/train.py finetune_simple_psi0_config` với tham số của bản cuối (Hiếu chốt 3/11/2026). Smoke của DA-19 trên Colab đã nạp và train cặp V-EGO qua đường này. Hai cặp ablation có cùng bố cục tensor và cùng cấu hình, nên đi cùng đường nạp. Phần còn lại, tải đủ file và băm lại sha256 trên máy train, làm ở bước đầu của mỗi job nhiệm vụ 3; job dừng nếu sha256 khác RunPlan.

## 2. Ước lượng

- Thành công của điểm X (biến thể, N, seed) ở điều kiện i, lượt r: s_X,i,r ∈ {0, 1}, theo cờ `check_success` của SIMPLE.
- Chỉ số chính: tỉ lệ thành công gộp ba mức, p_X = trung bình trên điều kiện của trung bình theo lượt. Báo thêm từng mức, theo khuôn bảng paper (thành công trên số lượt).
- Hiệu V-EGO − V-NOEGO ở cùng N: trung bình theo điều kiện của (p_EGO,i − p_NOEGO,i), ghép cặp theo điều kiện.
- CI 95%: bootstrap theo điều kiện, lấy mẫu lại trong từng mức (10 mỗi mức), 10.000 lần, hạt giống 20261104, khoảng phân vị; cùng chỉ số lấy mẫu cho hai biến thể. Ở N có hai seed (đủ lưới) dùng bootstrap phân cấp của spec mục 7.5: lấy mẫu lại seed trước, rồi điều kiện.
- **N₅₀** [Đề xuất]: nội suy tuyến tính theo log₂ N giữa hai điểm lưới liền nhau mà đường cong cắt 50% lần đầu. Đạt ≥ 50% ở N nhỏ nhất đã chạy thì N₅₀ ≤ N đó; chưa tới 50% ở N = 80 thì N₅₀ > 80 (bị chặn). So N₅₀ của hai biến thể chỉ khi ít nhất một bên xác định: V-EGO xác định và V-NOEGO > 80 tính là V-EGO nhỏ hơn; cả hai > 80 là không xác định.
- Lượt hỏng do hạ tầng (server lỗi, sim sập, mất kết nối) không tính là thất bại của policy: chạy lại cùng điều kiện và báo số lần chạy lại.
- **Độ nhạy của bản sơ bộ** (ước lượng, chưa đo): 30 điều kiện, 1 lượt. Nếu p ≈ 50% và hai biến thể gần độc lập theo điều kiện, độ lệch chuẩn của hiệu một điều kiện khoảng 0,7, sai số chuẩn khoảng 0,13, nên nửa độ rộng CI khoảng 25 điểm %. Bản sơ bộ chỉ thấy được chênh lệch lớn; CI chứa 0 là kết quả dự kiến, không phải bằng chứng "không có tác dụng".

## 3. Quy tắc diễn giải

Kiểm theo thứ tự; quy tắc 0 chặn mọi quy tắc sau.

| # | Điều kiện | Đọc là |
|---|---|---|
| 0 | Mốc so của tác giả, hoặc cả hai biến thể ở mọi N đã chạy, dưới 10% trên bộ eval của RunPlan | Pipeline eval hoặc renderer chưa đủ để đo (S1-03, Q-27C). Không so biến thể; ghi `Decision` |
| 1 | Cận dưới CI của (V-EGO − V-NOEGO) > 0 ở ít nhất 2 mức N, **và** N₅₀(V-EGO) < N₅₀(V-NOEGO) | **HE đạt** (spec mục 3) |
| 2 | Cận trên CI của (V-EGO − V-NOEGO) < 0 ở ít nhất 1 mức N, hoặc N₅₀(V-NOEGO) < N₅₀(V-EGO) mà không mức N nào có cận dưới > 0 | **HE âm**: kết quả hợp lệ, phải báo, kèm giải thích có thể (task trong sim gần HE hơn EgoDex; khác biệt chỉ rõ ở N nhỏ hơn lưới) |
| 3 | Còn lại (mọi CI chứa 0, hoặc dấu khác nhau giữa các N) | Không kết luận; báo từng CI và N₅₀ |

**Bản sơ bộ (AC 6).** Chỉ có N = 20 và N = 80, nên "ít nhất 2 mức N" ở quy tắc 1 nghĩa là cả hai. Kết quả sơ bộ gắn nhãn "sơ bộ" ở mọi bảng, hình và câu trên slide; không gọi là kết luận HE. Kết luận HE chỉ đọc trên đủ lưới (bốn N, seed thứ hai ở N = 20, 40).

**Quy tắc phụ, không quyết định kết luận**: hiệu theo từng mức; tỉ lệ đạt từng bước của scorer; V-EGO10 so với V-NOEGO (đủ lưới) báo là kết quả mô tả.

## 4. Giới hạn (design mục 7.2)

- Ba biến thể khác nhau cả số bước pretrain (200k + 30k, 46k, 48k) và mỗi biến thể có action expert post-train riêng. Đội không tách được tác dụng của EgoDex khỏi hai yếu tố này; câu hỏi gửi PSI Lab ở Q-27E của S1-03.
- Batch toàn cục 16 trên một GPU, so với 64 của checkpoint tác giả (S1-04 mục 1.4); số tuyệt đối của điểm HE vì vậy có thể thấp hơn mốc so.
- Bộ eval là của tác giả, 10 điều kiện mỗi mức; mức 0, 1 dùng vị trí vật và khay của episode train 0–9, mà điểm HE không train trên đó.
- Kết quả trong sim; không suy ra số trên robot thật.

## 5. Việc cần Hiếu chốt trước khi đóng băng

| # | Câu hỏi | Đề xuất |
|---|---|---|
| Q1 | Loại episode 0–9 khỏi kho chọn demo? | Có (mục 1) |
| Q2 | Eval 10 điều kiện × 3 mức của bộ `e78fb93` thay cho "30 điều kiện dev × 3 mức" của AC 1? | Có, ghi `Decision` |
| Q3 | Renderer của eval HE | Chạy trước 10 episode mức 0 của checkpoint tác giả ở `mujoco` trên bộ `e78fb93` (khoảng 15 phút `rtx3060`, 0 CU). S1-03 chỉ đo `mujoco` trên bộ `de140d6` (0/20); trên `e78fb93`, phát lại action người ở `mujoco` đạt 4/10 so với 0/10 (B6). Gần số Isaac (4/5 tạm) thì eval HE ở `mujoco`; không thì Isaac theo mục 6 |
| Q4 | Ngân sách CU (mục 6) | Chọn trước khi chạy job Colab nào |

Khi Q1–Q4 xong: sửa RunPlan nếu cần, rồi

```bash
uv run python scripts/he/he1_plan.py freeze configs/runplans/he/he-1.yaml --signed-by Hiếu --reason "<lý do>"
```

ghi `he-1.lock.json` và `he-1.plan_review.json` (artifact `Decision`, kind `plan_review`, `subject_id` là `run_plan_id`).

## 6. Chi phí ước lượng của bản sơ bộ (nhiệm vụ 3)

_Ước lượng từ số đo S1-04 và S1-03, chưa chạy._ Fine-tune R1 trên L4: 16,6 CU, 8,5 giờ mỗi lần (S1-04 mục 4). Eval: `mujoco` khoảng 60–90 s mỗi episode trên `rtx3060`, server Ψ₀ cùng máy, 0 CU; `mujoco_isaac` khoảng 24,6 phút mỗi episode, client trên `rtx3060`, server trên Colab L4 1,94 CU/giờ (S1-04 mục 5.1). Mốc so lấy từ S1-03, không tính ở đây.

| Phương án | Fine-tune | Eval (4 điểm) | Tổng CU | Giờ máy | Đáp ứng AC 6 |
|---|---|---|---|---|---|
| A · 4 lần R1, eval `mujoco` 3 mức | 66 CU | 2–3 giờ `rtx3060`, 0 CU | **66** | 2 phiên Colab song song khoảng 17 giờ, cộng eval | Có, nếu Q3 cho phép `mujoco` |
| B · 4 lần R1, Isaac chỉ mức 0 | 66 CU | 40 episode, 16 giờ, 32 CU | **98** | khoảng 17 + 16 giờ | Có, nhưng chỉ mức 0 (10 điều kiện, CI rất rộng) |
| C · 4 lần R1, Isaac 3 mức | 66 CU | 120 episode, 49 giờ, 96 CU | **162** | khoảng 17 + 49 giờ | Có; vượt số dư |
| D · chỉ N = 80 (2 lần R1), eval `mujoco` | 33 CU | 0 CU | **33** | khoảng 9 giờ | Không: AC 6 cần N = 20 và 80 |
| E · 4 lần, 20.000 bước | khoảng 35 CU | như A hoặc B | 35–67 | khoảng 9 giờ | Có, nhưng đổi recipe mà Hiếu đã chốt R1 |

Số dư khoảng 140 CU (S1-04, 4/11/2026) dùng chung với 4 lần fine-tune của DA-34 (khoảng 66 CU). A cộng DA-34 là khoảng 133 CU, sát số dư, chưa tính chạy lại. [Đề xuất] Thứ tự: chạy câu Q3 trước; đúng thì A; không thì B, và Hiếu chọn mua thêm CU hay chuyển một phần DA-34 sang sau demo. Mọi rút gọn ghi `Decision` (AC 8).

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 4/11/2026 | Bản nháp: thiết lập, kiểm checkpoint, ước lượng, quy tắc diễn giải, câu hỏi chốt và chi phí | Hiếu (soạn với Claude) |
