# Task bê khay trên cảnh đồ gá: run M (DA-48)

Tài liệu này giữ quy tắc đọc kết quả và runbook của run M, lần train Ψ₀ đầu tiên trên cảnh đồ gá `jig2`. Story: [DA-48](../product/stories/DA-48-train-vong-moi-canh-do-ga.md). Plan: `configs/runplans/tray/he-tray-jig-m.yaml`. Các vòng trước (cảnh cũ) ở [tray.md](tray.md).

Mọi số ở mục 1 và 3 là ước lượng trừ khi ghi "thực đo". Kết quả eval của run M ở mục 5; đề xuất vòng train tiếp (run N) và luật đọc của nó ở mục 6.

## 1. Run M là gì

| Mục | Giá trị |
|---|---|
| Dữ liệu | Một tập ghép từ bốn phần, 1 037 episode, 948 639 khung (thực đo 25/11/2026) |
| Phần 1, 2 | Episode đầy đủ của lô DA-41: `tray_s1_bfbdcbcf719e` (mức 1, 356 episode), `tray_s1_8631ace9b1b3` (mức 2, 142) |
| Phần 3, 4 | Bản cắt đoạn đặt của lô DA-46 (lệch đích CARRY ±10 cm): `tray_s1place_a1797e480160` (377), `tray_s1place_56e6d006d8d1` (162) |
| Lọc | **[Đã chốt]** (Hiếu, 25/11/2026) chỉ giữ episode đặt lệch ≤ 3 cm và ≤ 5°; bỏ 143 trong 1 180 |
| Stats | Của chính tập ghép (`own_train_set`) |
| Recipe | `configs/models/psi0-stage3.yaml`, batch 16, seed 0, cặp checkpoint cha `psi0-baseline-egodex-he` như các nhánh C của DA-34 |
| Số bước | 100 000, khoảng 1,7 lượt qua dữ liệu. Checkpoint chính `ckpt_100000`; `ckpt_60000` và `ckpt_80000` là bản đọc sớm |
| GPU | **[Đã chốt]** (Hiếu, 25/11/2026) Colab L4. Ước lượng khoảng 20 giờ và 40 CU, từ run C của DA-34 (40 000 bước, 8,27 giờ, 15,99 CU, thực đo) |
| Số run | **[Đã chốt]** (Hiếu, 25/11/2026) một run. Run đối chứng K (498 episode đầy đủ, không có bản cắt) là tùy chọn, Hiếu quyết sau |

Vì sao tập này: [place-data.md](../g0/tray/place-data.md) và story DA-48. Tỉ trọng đoạn từ ARRIVE_B tới hết trong tập ghép khoảng 40 % (ước lượng), so với 22,9 % của lô DA-41.

## 2. Quy tắc đọc kết quả

Viết ngày 25/11/2026, trước khi train. **[Đề xuất]** của Claude; có hiệu lực khi Hiếu merge PR đóng băng plan, vì plan ghim sha256 của khối dưới đây.

<!-- jig-m-rules -->

**Phạm vi.** Một run: M, `ckpt_100000`, một seed train. Eval theo story DA-47 trên cảnh `jig2` với bộ chấm bản 2: mức 1 và mức 2, mỗi mức 30 điều kiện, mỗi điều kiện 3 lượt, tức 180 rollout. Nếu DA-47 chốt cỡ khác thì dùng cỡ đó, các quy tắc dưới không đổi.

**Đơn vị thống kê là điều kiện, không phải rollout.** Tỉ lệ của một điều kiện là số lượt thành công chia số lượt. Tỉ lệ của một nhóm là trung bình các điều kiện. Khoảng tin cậy 95 % lấy bằng bootstrap theo điều kiện, 10 000 lần lấy lại, seed 20261125. Khoảng Wilson trên số rollout chỉ ghi kèm để mô tả.

1. **Cả task, mốc 80 %.** Chỉ viết "đạt mốc 80 %" khi cận dưới của khoảng tin cậy trên mức 1 và 2 gộp lại từ 0,80 trở lên. Ngược lại viết tỉ lệ, khoảng tin cậy và "chưa đạt mốc 80 %".
2. **Từng mức, mốc 70 %.** Mức 1 và mức 2 đọc riêng: chỉ viết "đạt mốc 70 %" cho một mức khi cận dưới của mức đó từ 0,70 trở lên.
3. **Bước đặt, mốc 50 %.** Tỉ lệ qua bước `place` tính trên mọi rollout của mức 1 và 2 (rollout không tới bước đặt tính là không qua). Chỉ viết "bước đặt trên 50 %" khi cận dưới lớn hơn 0,50.
4. **So với các run của DA-34 chỉ là mô tả.** Khác cảnh, khác tập eval, khác bộ chấm, khác số bước. Không viết "tốt hơn" hay "tăng X điểm" so với chúng; chỉ đặt hai con số cạnh nhau kèm câu nêu các điểm khác này.
5. **Không quy kết quả cho dữ liệu bước đặt khi không có run K.** Run M đổi cùng lúc cảnh, dữ liệu và số bước. Chỉ khi run K được train và eval trên cùng tập điều kiện mới so M với K: hiệu ghép cặp theo điều kiện, bootstrap như trên, và chỉ viết "dữ liệu bước đặt giúp" khi khoảng tin cậy của hiệu nằm hẳn trên 0.
6. **Checkpoint.** Số chính là của `ckpt_100000`. `ckpt_60000` và `ckpt_80000` chỉ đọc trên tối đa 20 điều kiện, để phát hiện run hỏng (ví dụ không rollout nào tới bàn B) và dừng sớm. Nếu về sau báo số của một checkpoint khác 100 000 thì phải ghi rõ là chọn sau khi đã xem kết quả.
7. **Lỗi theo bước.** Báo tỉ lệ qua từng bước và nhãn lỗi của bộ chấm bản 2 cho mọi rollout hỏng. Đây là mô tả, không có ngưỡng.

**Điều kiện trước khi đọc.** Plan đã đóng băng và id trùng `MIX_FROZEN`; sha256 của checkpoint trùng bản ghi lúc persist; tập điều kiện có `conditions.sha256` và seed không trùng seed train; đủ mọi rollout của tập. Rollout chỉ được loại khi lỗi hạ tầng (server chết, sim không mở), và phải liệt kê từng cái.

**Giới hạn phải ghi cùng kết quả.** Một seed train, một lần train, trong mô phỏng; rollout dưới EGL không lặp lại được từng bit. Số là sơ bộ.

**Không đổi quy tắc sau khi có kết quả.** Muốn đổi thì viết một Decision mới, ghi lý do và ngày, và giữ nguyên khối này.

<!-- /jig-m-rules -->

## 3. Runbook

Chạy theo thứ tự. Bước A đã làm trong nhiệm vụ 3.1; số ghim nằm trong plan.

**A. Dựng tập trên `rtx3060`** (không GPU). Thư mục làm việc `~/fwdata/da48-m/`, `E=G1WholebodyTrayTransferJigTeleop-v0`:

```bash
uv run python -m flywheel_psi0.tray.demo_sets --release <kho>/releases/<R> --keep-seeds keep-<R>.json --size Q=<n> --out configs/runplans/tray/demo_sets-jig-m-<R>.json
```

```bash
uv run python scripts/he/demo_subset.py --src <kho>/releases/<R> --sets configs/runplans/tray/demo_sets-jig-m-<R>.json --set Q --out ~/fwdata/da48-m/parts/<R>/$E
```

```bash
uv run python -m flywheel_psi0.tray.cplus_cut --part <p1> --part <p2> --part <p3> --part <p4> --demo-set M --out ~/fwdata/da48-m/M/$E
```

**B. Kiểm và đóng tar** (sau khi PR đóng băng đã merge và code trên `rtx3060` là `master`):

```bash
uv run python -m flywheel_psi0.tray.mixplan check configs/runplans/tray/he-tray-jig-m.yaml --data ~/fwdata/da48-m/M/$E --launch
```

```bash
uv run python -m flywheel_psi0.tray.mixplan pack configs/runplans/tray/he-tray-jig-m.yaml --data ~/fwdata/da48-m/M/$E --out ~/fwdata/da48-m/M.tar
```

Chép `M.tar` và `M.tar.json` về laptop, so sha256 với file `.json`, rồi đưa cả hai lên `MyDrive/denso/da48/cuts/` của account Colab dùng để train.

**C. Trước khi mở phiên.** Đăng nhập CLI Colab bằng account đó ngay trước lúc chạy (token hết hạn sau khoảng 16 giờ; run dài khoảng 20 giờ nên phải đăng nhập lại một lần vào khoảng giờ thứ 12–15). Giữ laptop thức suốt run. Chạy bộ canh `scripts/colab/cu_watch.py session --gpu L4` với trần của plan.

**D. Trên VM**, thư mục `/content/da48`, theo đúng thứ tự của [tray.md](tray.md) mục 19.9 phần D, đổi nhánh thành `M`: chép code bằng `git archive`, `colab drivemount` (chạy lại một lần nếu hết 120 giây chờ đồng ý), rồi:

```bash
python3 -m flywheel_psi0.tray.colab_train setup --branch M --work /content/da48
```

```bash
Psi0/.venv-psi/bin/python -m flywheel_psi0.tray.colab_train train --branch M --work /content/da48
```

```bash
python3 fw/scripts/he/he1_colab.py persist --work /content/da48 --to /content/drive/MyDrive/denso/da48/runs --watch 600 --pid <pid của train>
```

Trên laptop theo dõi bằng `he1_fetch.py follow --stop-when-done --total-steps 100000 --gpu L4`, để VM dừng ngay khi train xong.

Mặc định wandb chạy `offline`. Muốn đồ thị lên wandb.ai theo thời gian thực, người vận hành tự chạy `wandb login` trên VM (khóa không nằm trong repo, plan hay nhật ký chat) rồi khởi động `train` với `FW_WANDB_MODE=online` (chỉ nhận `offline` hoặc `online`). Biến này được xuất ra môi trường của tiến trình train, thắng dòng `WANDB_MODE=offline` trong `.env` của Psi0 (`scripts/train.py` gọi `load_dotenv()` không ghi đè). Dữ liệu của run này là `public`.

**E. Nếu mất VM giữa chừng.** Mở VM mới, làm lại `setup`, rồi trước `train`:

```bash
python3 -m flywheel_psi0.tray.colab_train restore --branch M --work /content/da48
```

`restore` chép về checkpoint mới nhất còn nguyên vẹn trên Drive; `train` chạy tiếp từ đó với cùng job `da48-ft-m-s0`. Lần thử thật ngày 26/11/2026 hỏng vì symlink `wandb/latest-run` trên Drive (mục 4); bản sửa bỏ qua symlink, có test, chưa chạy lại trên job thật.

**F. Khi xong.** Dừng VM, ghi dòng ledger thực đo (CU, giờ) trỏ về dòng ước tính, ghi sha256 của `ckpt_100000`, và giao đường dẫn Drive cho story DA-47.

## 4. Kết quả train (thực đo, 26/11/2026)

Chỉ là số của lần train. Chưa có eval; mọi quy tắc ở mục 2 còn nguyên.

| Mục | Giá trị thực đo |
|---|---|
| Số bước | 100 000 / 100 000, `result.json` ghi `status: ok` |
| Phiên 1 | L4, 03:48Z 25/11 tới khoảng 17:12Z; laptop tắt nên watcher trả VM ở khoảng bước 61 374; 31,22 CU; 1,46 bước/giây |
| Phiên 2 | L4 mới, chạy tiếp từ `ckpt_60000` lúc 18:08Z 25/11, tới bước 100 000 lúc 02:31Z 26/11 (0,74 giây/bước); 24,93 CU, trong đó khoảng 4,3 CU là VM chờ sau khi train xong |
| Tổng | 56,15 CU (số dư 214,88 xuống 158,73), khoảng 21 giờ train. Ước lượng trước là 40 CU và 20 giờ |
| Checkpoint | `ckpt_10000` … `ckpt_100000` trên `MyDrive/denso/da48/runs/da48-ft-m-s0/`; laptop có bản không kèm optimizer ở `fwdata/tray/jig-m/da48-ft-m-s0/` |
| sha256 của `ckpt_100000/model.safetensors` | `3358434935cea2cd64e17ed57fc22799218bc630f5c322c787a836b9b02120a3`, khớp giữa Drive và laptop (6 253 648 840 byte) |
| Loss validation | 0,615 (20k), 0,408 (40k), 0,361 (60k), 0,342 (80k), 0,174 (bước cuối). Dao động mạnh giữa các lần đo (0,402 ở 98k), không dùng để kết luận chất lượng |
| wandb | run `ikp5c209` của project `psi`, một run cho cả hai phiên |
| Sổ chi phí | [DA-48.csv](../g0/ledger/DA-48.csv), hai dòng thực đo. Không có dòng ước tính ghi trước (sót, đã ghi trong sổ) |

Ba lỗi vận hành gặp trong run, không ảnh hưởng trọng số:

1. `restore` hỏng khi Drive có symlink `wandb/latest-run`; lần này chép `ckpt_60000` bằng `rsync`. Đã sửa trong mã, có test.
2. Vòng `follow` không thấy `ckpt_100000` vì `completed_checkpoints` xếp theo tên (`ckpt_100000` đứng trước `ckpt_20000`), nên không tự dừng VM; kéo tay rồi dừng. Đã sửa trong mã, có test. Lỗi chỉ lộ khi run từ 100 000 bước.
3. Tiến trình `guard` thoát ở phút thứ 5 của phiên 1 (chưa có phiên nào được liệt kê lúc Colab trả 503) và không chạy ở phiên 2; chỉ watcher của phiên canh CU. Chưa sửa.

Giao cho DA-47: đường dẫn Drive và sha256 ở bảng trên; `ckpt_60000` và `ckpt_80000` là bản đọc sớm theo quy tắc 6.

## 5. Kết quả eval run M (thực đo, 26/11/2026)

Eval của story DA-47 (file story nằm trong PR 228, chưa merge): `ckpt_100000`, cảnh `jig2`, bộ chấm bản 2, 60 điều kiện (mức 1 và 2, seed 1000100–1000129) × 3 lượt = 180 rollout. Đọc theo đúng mục 2. Số là sơ bộ: một seed train, một lần train, trong mô phỏng; rollout dưới EGL không lặp lại được từng bit.

**Điều kiện trước khi đọc.** Plan `rp_a410d01efa62` trùng `MIX_FROZEN` và sha256 của checkpoint đã đối chiếu lúc nạp server; `conditions.sha256` `bbec07e3…5d348`; seed eval nằm ngoài seed train; đủ 180 rollout, không lô nào chạy lại, không rollout nào bị loại. Code eval ở commit `f809d363` (nhánh DA-47, chưa merge lúc chạy).

| Quy tắc | Tỉ lệ | Khoảng tin cậy 95 % | Kết luận |
|---|---|---|---|
| 1. Cả task, mức 1 và 2 (60 điều kiện) | 75,6 % (136/180) | 70,0–81,1 | **Chưa đạt mốc 80 %** |
| 2. Mức 1 (30 điều kiện) | 85,6 % (77/90) | 78,9–92,2 | **Đạt mốc 70 %** |
| 2. Mức 2 (30 điều kiện) | 65,6 % (59/90) | 55,6–75,6 | **Chưa đạt mốc 70 %** |
| 3. Bước `place`, mức 1 và 2 | 89,4 % (161/180) | 85,0–93,9 | **Bước đặt trên 50 %** |

Bootstrap theo điều kiện, 10 000 lần, seed 20261125, bằng hàm `bootstrap_ci` của `eval_results`. Khoảng gộp hai mức lấy lại trong từng mức (cách `eval_results` đã làm từ trước); mục 2 không nói rõ điểm này, và lấy lại chung 60 điều kiện cho 68,9–82,2, cùng kết luận. `eval_results` không nạp được plan của run M nên lệnh chạy với `he-tray-v2.yaml` (seed 20261103); bảng trên là số tính lại với seed của mục 2.

Quy tắc 4 và 5: không so hơn kém với các run DA-34, và không quy kết quả cho dữ liệu bước đặt vì chưa có run K.

**Quy tắc 7, lỗi theo bước (mô tả).**

| | Mức 1 (trên 90) | Mức 2 (trên 90) |
|---|---|---|
| Qua `approach_a` … `reach_b` | 90 | 88 |
| Qua `place` | 82 | 79 |
| Thành công | 77 | 59 |
| Thành công theo lượt 0 / 1 / 2 (trên 30) | 26 / 28 / 23 | 21 / 19 / 19 |
| Điều kiện thành công 3/3, 2/3, 1/3, 0/3 | 18, 11, 1, 0 | 10, 9, 11, 0 |
| `L-PLACE-POSE` | 8 | 20 |
| `L-TRAY-TILT` | 5 | 8 |
| Nhãn khác | 0 | `L-TIMEOUT` 1, `L-PART-DROP` 1, `L-ONE-HAND` 1 |

Phân tích 44 lượt hỏng từ số đo của dòng outcome (vị trí, độ cao, độ nghiêng của khay lúc lỗi và lúc cuối); chưa xem video:

- **`L-PLACE-POSE` (28).** 22 lượt khay gác lên thành đồ gá: cao hơn mặt bàn 1,5–3,5 cm, nghiêng 3–13°, lệch ngang 5–10 cm hoặc lệch góc 8–15°. 5 lượt khay nằm phẳng trên bàn, lệch 6–11 cm về phía robot. 1 lượt lệch góc 21°. Lead-in của mặt vát là 4,2 cm mỗi trục ([jig.md](../g0/tray/jig.md) mục 2.3), tức policy hạ khay khi còn lệch ngoài vùng đồ gá tự dẫn. Ở 27/28 lượt, khay không đổi vị trí từ lúc lỗi tới hết giờ: robot không sửa sau khi buông.
- **`L-TRAY-TILT` (13).** Cả 13 xảy ra khi hai tay còn cầm khay trên không; 11 lượt vừa chạm ngưỡng (15,0–15,8°). 8 lượt ở giữa đường đi, 5 lượt ở sát bàn B lúc hạ.
- **Tham số cảnh của mức 2.** Tương quan giữa số lượt thành công của điều kiện và khoảng cách bàn, vị trí đứng, khối lượng linh kiện, ánh sáng đều yếu (|r| ≤ 0,39 trên 30 điều kiện); không kết luận được tham số nào gây lỗi.
- **Khay nằm phẳng trong đồ gá.** Theo định nghĩa "phẳng" của jig.md mục 4.2 (nghiêng ≤ 2°, cao < 5 mm), 120/180 lượt có khay cuối phẳng, 58 không phẳng, 2 không tới bàn B. Trong 136 lượt thành công có 26 lượt không phẳng: bộ chấm chỉ xét vị trí và góc. Đây là mô tả; luật của mục 2 không đổi.

Sai số đặt so với đích (`place_error`): lượt thành công p50 1,6 cm và 1,1°; `L-PLACE-POSE` p50 6,7 cm và 9,0°. Thành công nới (số phụ, chỉ nới `L-PLACE-POSE`, góc giữ 10°): 150/180 ở 10 cm, 154/180 ở 20 cm.

Chi phí eval, thực đo: một phiên L4 chạy ba server Ψ₀, 2 giờ 24 phút, 6,8 CU (số dư 158,63 xuống 151,83); ba làn `eval_batch` trên `rtx3060`. Outcome K1 (180 dòng `RolloutOutcome`) đã giao nhóm C.

## 6. Run N: đề xuất và luật đọc

**[Đề xuất]** của Claude, 26/11/2026, viết sau khi đọc kết quả run M và **trước** khi sinh dữ liệu hay train run N. Story: [DA-50](../product/stories/DA-50-train-run-n-nham-loi-dat.md). Có hiệu lực khi Hiếu merge PR đóng băng plan của run N, plan ghim sha256 của khối luật dưới đây.

Run N giữ nguyên recipe, checkpoint cha, số bước (100 000), seed train và stats kiểu `own_train_set` của run M; **chỉ đổi tập dữ liệu**. Dữ liệu thêm nhắm vào hai lỗi của mục 5; thành phần cụ thể chốt ở DA-50 sau khi đo tập train của M.

<!-- jig-n-rules -->

**Phạm vi.** Một run: N, `ckpt_100000`, một seed train. Eval trên đúng tập điều kiện của run M (`conditions.sha256` `bbec07e31ee022ac46d59e5322628c226519abe76363160ccbdb78b68725d348`), cảnh `jig2`, bộ chấm bản 2, 3 lượt mỗi điều kiện, 180 rollout.

**Đơn vị thống kê là điều kiện.** Tỉ lệ của một điều kiện là số lượt thành công chia số lượt. Khoảng tin cậy 95 % lấy bằng bootstrap theo điều kiện, 10 000 lần, seed 20261126; khi gộp hai mức thì lấy lại trong từng mức.

1. **Mốc tuyệt đối.** Quy tắc 1, 2, 3 của mục 2 áp cho run N, không đổi ngưỡng: 80 % cả task, 70 % từng mức, bước đặt trên 50 %, đều đọc ở cận dưới.
2. **N so với M, cả task.** Với mỗi điều kiện, hiệu là tỉ lệ của N trừ tỉ lệ của M (mỗi bên 3 lượt). Chỉ viết "N tốt hơn M" khi khoảng tin cậy của trung bình hiệu trên 60 điều kiện nằm hẳn trên 0; "N kém hơn M" khi nằm hẳn dưới 0; còn lại viết "chưa phân biệt được N với M" kèm hiệu và khoảng.
3. **N so với M, mức 2.** Đọc riêng 30 điều kiện mức 2 theo đúng cách của quy tắc 2. Đây là nơi dữ liệu thêm nhắm tới.
4. **Cơ chế (mô tả, không ngưỡng).** Báo cho cả M và N: số lượt `L-PLACE-POSE`, số lượt `L-TRAY-TILT`, và số lượt khay cuối không phẳng (nghiêng > 2° hoặc cao ≥ 5 mm so với khay nằm trong đồ gá) trong các lượt tới bàn B. Số của M: 28, 13, 58/178.
5. **Quy kết.** Hiệu N trừ M chỉ được quy cho **cả tập dữ liệu mới**, không cho riêng một phần thêm nào, vì các phần đổi cùng lúc.
6. **Checkpoint.** Số chính là `ckpt_100000`. Checkpoint sớm hơn chỉ đọc trên tối đa 20 điều kiện để phát hiện run hỏng. Báo số của checkpoint khác thì ghi rõ là chọn sau khi xem kết quả.
7. **Lỗi theo bước.** Như quy tắc 7 của mục 2.

**Điều kiện trước khi đọc.** Plan của N đã đóng băng; sha256 của checkpoint trùng bản ghi lúc persist; seed của dữ liệu thêm không trùng seed eval (1000100–1000129); đủ 180 rollout. Rollout chỉ được loại khi lỗi hạ tầng, liệt kê từng cái. Số của M là bản đã ghi ở mục 5, không chạy lại.

**Giới hạn phải ghi cùng kết quả.** Một seed train, một lần train, trong mô phỏng. Dữ liệu của N được chọn **sau khi đã xem lỗi của M trên chính 60 điều kiện này**, nên đây là kết quả trên tập dev, không phải holdout. Hai lần eval của cùng một checkpoint trên 60 lượt đã lệch nhau tới 5 lượt (mục 5, theo lượt), nên hiệu nhỏ không có nghĩa.

**Không đổi quy tắc sau khi có kết quả.** Muốn đổi thì viết một Decision mới, ghi lý do và ngày, và giữ nguyên khối này.

<!-- /jig-n-rules -->

## 7. Run N: tập dữ liệu, plan và runbook train (27/11/2026)

Plan: `configs/runplans/tray/he-tray-jig-n.yaml`, đóng băng thành `rp_23b25206d96e` (`he-tray-jig-n.lock.json`), ghim khối `jig-n-rules` (sha256 `7ba9df31…3992d`). Plan có hiệu lực khi Hiếu merge PR này. So với plan M chỉ khác tập dữ liệu, thư mục Drive và trần CU.

| Mục | Run M | Run N |
|---|---|---|
| Các phần | 4 (356, 142, 377, 162) | 4 phần của M rồi 2 đoạn đặt lệch góc: `tray_s1place_e793fb05a9df` (mức 1, 227), `tray_s1place_6a7b780fb66b` (mức 2, 327) |
| Episode, khung | 1 037; 948 639 | 1 591; 1 230 839 (thực đo) |
| Số epoch ở 100 000 bước | 1,69 | 1,30 |
| `stats_sha256` | `3c31da5e…cc85ce` | `3dae55d7…57bb6c` |
| Job, thư mục VM | `da48-ft-m-s0`, `/content/da48` | `da50-ft-n-s0`, `/content/da50` |
| Drive | `denso/da48/cuts`, `denso/da48/runs` | `denso/da50/cuts`, `denso/da50/runs` |
| Trần CU | 60 | 70 **[Đề xuất]** |

Dữ liệu thêm và bộ lọc: [place-data.md](../g0/tray/place-data.md) mục 9. 554 seed mới không trùng seed eval (1000100–1000129) và không trùng seed của tập M; kiểm bằng lệnh (commit của nhiệm vụ 4.1) và bằng test `test_n_seeds_are_new_unique_and_outside_the_eval_set`.

**Chi phí (ước lượng, chưa đo).** Cùng recipe, số bước và GPU như M nên lấy số thực đo của M (mục 4): khoảng 52 CU và 21 giờ nếu không có VM chạy không tải (M tốn 56,15 CU, trong đó khoảng 4,3 CU là VM chờ sau khi train xong). Trần 70 CU vì M chỉ còn cách trần 60 có 3,85 CU; với sàn 14, account cần ít nhất 84 CU lúc mở phiên (số dư sau eval của M: 151,83 CU). Hiếu muốn giữ 60 thì đổi ba chỗ trong plan và đóng băng lại, id sẽ đổi.

**Runbook.** Như mục 3, đổi theo bảng trên. Bước A và đóng tar đã làm ngày 27/11/2026:

- `N.tar` (7 075 532 800 byte, sha256 `ae443c49efe63cb2b2962e95cb1db83f845eb870d182d27fdbee36d466a89f48`) và `N.tar.json` ở `rtx3060:~/fwdata/da50-n/` và trên laptop ở `fwdata/tray/jig-n/`; sha256 trên laptop đã so khớp.
- Hai file đã ở `MyDrive/denso/da50/cuts/` từ 27/11/2026 (Hiếu cho phép); sha256 đọc lại từ Drive khớp.

Sau khi PR merge (code trên VM phải có `--branch N`):

```bash
python3 scripts/colab/cu_watch.py session --gpu L4 --cap 70 --floor 14
```

```bash
python3 -m flywheel_psi0.tray.colab_train setup --branch N --work /content/da50
```

```bash
Psi0/.venv-psi/bin/python -m flywheel_psi0.tray.colab_train train --branch N --work /content/da50
```

```bash
python3 fw/scripts/he/he1_colab.py persist --work /content/da50 --to /content/drive/MyDrive/denso/da50/runs --watch 600 --pid <pid của train>
```

Mất VM giữa chừng: `setup` lại rồi `colab_train restore --branch N --work /content/da50` trước `train`. Theo dõi bằng `he1_fetch.py follow --stop-when-done --total-steps 100000 --gpu L4`; bản sửa thứ tự checkpoint (PR 226) đã có nên vòng theo dõi phải thấy `ckpt_100000` và dừng VM. Nếu không thấy trong 15 phút sau bước 100 000 thì dừng VM bằng tay.

Điều chưa kiểm: nhánh `N` của `colab_train` mới chạy trên bộ giả CPU, chưa chạy trên VM; `restore` sau bản sửa symlink chưa chạy trên job thật; tiến trình `guard` thoát sớm chưa sửa (kiểm nó còn sống sau khi phiên được cấp). Token CLI hết hạn sau khoảng 16 giờ, run khoảng 21 giờ nên cần đăng nhập lại một lần.

## 8. Kết quả train run N (thực đo, 28/11/2026)

Chỉ là số của lần train. Chưa có eval; mọi quy tắc của khối `jig-n-rules` còn nguyên.

| Mục | Giá trị thực đo |
|---|---|
| Số bước | 100 000 / 100 000; `train.log` kết thúc bằng `train exit 0` |
| Phiên | Một phiên L4 `da50-n`, 02:59Z 27/11 tới 03:02Z 28/11 (24,05 giờ); VM tự kết thúc, không phải do vòng `follow` dừng |
| Train | Bắt đầu 03:42Z 27/11, 20 giờ 55 phút 48 giây (trung bình 1,33 bước/giây), xong khoảng 00:38Z 28/11 |
| Chi phí | 55,78 CU (số dư 151,76 xuống 95,98), 2,33 CU/giờ; trần 70 không chạm. Ước lượng trước là 52 CU và 21 giờ. Khoảng 5,6 CU là VM chờ 2,4 giờ sau khi train xong, khoảng 1,2 CU là lúc `setup` treo |
| Checkpoint | `ckpt_10000` … `ckpt_100000` trên `MyDrive/denso/da50/runs/da50-ft-n-s0/`, mỗi cái đủ bốn file và cùng cỡ. **Laptop không có checkpoint nào** |
| sha256 của `ckpt_100000/model.safetensors` | `1011d2ce42bc4969d727a3f0f47106eea7b473586b4459784362b36af112d0e2`, đọc trên Drive (6 253 648 840 byte); chưa có bản thứ hai để so |
| Loss | Loss train ở bước cuối 0,0556 (thanh tiến độ). Loss validation chưa đọc |
| wandb | `offline`, run `pjoscwo7`; file nằm trong thư mục run trên Drive, chưa đẩy lên wandb.ai |
| Sổ chi phí | [DA-50.csv](../g0/ledger/DA-50.csv): dòng thực đo `job_da50_ft_n_s0_measured` trỏ về dòng ước tính |

Lỗi vận hành gặp trong run, không ảnh hưởng trọng số:

1. `setup` treo khoảng 30 phút khi tải checkpoint cha từ Hugging Face (đứng ở 5,5 GB). Dừng lệnh tải và chạy lại `setup`; lần hai xong trong 43 giây, sha256 của hai file checkpoint cha được kiểm.
2. Vòng `follow` hỏng từ bước 8 198: mọi lần kéo bị từ chối với "Already-active SSH session (HTTP 429)" vì một kết nối `colab ssh` khác giữ VM (Colab chỉ cho một kết nối mỗi runtime). Nó ghi ALERT 128 lần vào log mà không ai đọc, nên không kéo checkpoint về và không dừng VM khi train xong. `persist` chạy trên VM nên Drive vẫn đủ. Chưa sửa: ALERT của `follow` cần tới được người vận hành, và không mở `colab ssh` tay trong lúc `follow` chạy.
3. `cu_watch` và `he1_fetch` mặc định gọi CLI Colab 0.7.5 chưa đăng nhập; lần mở đầu thoát mã 6, 0 CU. Chạy lại với `COLAB_CLI` trỏ sang bản 0.8.0 đã đăng nhập. Lúc phiên kết thúc, lệnh `unassign` của watcher trả mã 1 trên bản 0.8.0 (VM đã mất nên không tốn thêm); đường dừng VM ở trần CU bằng bản này vẫn chưa được thử.
4. `guard` lần này sống suốt phiên.

Giao cho làn eval (nhiệm vụ 6): đường dẫn Drive và sha256 ở bảng trên.

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/11/2026 | Tạo: mô tả run M, quy tắc đọc kết quả (đề xuất), runbook | Hiếu (soạn với Claude) |
| 25/11/2026 | Thêm đoạn bật wandb online qua `FW_WANDB_MODE` ở bước D (ngoài khối luật đọc) | Hiếu (soạn với Claude) |
| 26/11/2026 | Mục 4 mới: số thực đo của lần train (100 000 bước, 56,15 CU, sha256 của `ckpt_100000`), ba lỗi vận hành; sửa câu cuối bước E | Hiếu (soạn với Claude) |
| 26/11/2026 | Mục 5 mới: kết quả eval run M đọc theo mục 2 (thực đo). Mục 6 mới: đề xuất run N và khối luật đọc `jig-n-rules`. Khối `jig-m-rules` không đổi | Hiếu (soạn với Claude) |
| 27/11/2026 | Mục 7 mới: tập dữ liệu, plan đóng băng và runbook train của run N. Hai khối luật không đổi | Hiếu (soạn với Claude) |
| 28/11/2026 | Mục 8 mới: số thực đo của lần train run N (100 000 bước, 55,78 CU, sha256 của `ckpt_100000` trên Drive), các lỗi vận hành; mục 7 ghi tar đã lên Drive. Hai khối luật không đổi | Hiếu (soạn với Claude) |
