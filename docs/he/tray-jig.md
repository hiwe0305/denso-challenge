# Task bê khay trên cảnh đồ gá: run M (DA-48)

Tài liệu này giữ quy tắc đọc kết quả và runbook của run M, lần train Ψ₀ đầu tiên trên cảnh đồ gá `jig2`. Story: [DA-48](../product/stories/DA-48-train-vong-moi-canh-do-ga.md). Plan: `configs/runplans/tray/he-tray-jig-m.yaml`. Các vòng trước (cảnh cũ) ở [tray.md](tray.md).

Mọi số ở mục 1 và 3 là ước lượng trừ khi ghi "thực đo". Kết quả eval chưa có.

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

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/11/2026 | Tạo: mô tả run M, quy tắc đọc kết quả (đề xuất), runbook | Hiếu (soạn với Claude) |
| 25/11/2026 | Thêm đoạn bật wandb online qua `FW_WANDB_MODE` ở bước D (ngoài khối luật đọc) | Hiếu (soạn với Claude) |
| 26/11/2026 | Mục 4 mới: số thực đo của lần train (100 000 bước, 56,15 CU, sha256 của `ckpt_100000`), ba lỗi vận hành; sửa câu cuối bước E | Hiếu (soạn với Claude) |
