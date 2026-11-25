# DA-48 · Train vòng mới trên cảnh đồ gá

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Đang làm (mở ngày 25/11/2026; PR mã trước, dữ liệu và freeze sau) |
| Người làm | Hiếu |
| Làn | Ngoài ba làn: adapter `flywheel-psi0` (task bê khay), không sửa nhân hay làn |
| Nguồn yêu cầu | Quyết định của Hiếu ngày 23/11/2026 (DA-46: sinh dữ liệu bước đặt trước, rồi train một lần trên toàn bộ) và ngày 25/11/2026 (ngưỡng lọc sai lệch đặt ≤ 3 cm và ≤ 5°; một run) |
| Nhãn | `area:train`, `area:data` |
| Sprint | Sau demo 17/11/2026, trước vòng chung kết (khoảng 3/12/2026) |
| Ước lượng | Mã (2.1–2.4) khoảng 6 giờ (ước lượng); job Colab tính riêng ở mục Cách làm |
| Phụ thuộc | DA-41 (đã merge: cảnh đồ gá `jig2`, kho `tray-s1-jig2-20261122`), DA-46 (kho `tray-s1place-jig2-20261124`). Checkpoint giao cho DA-47 (eval, nhóm A) |

## Story

Là người train policy Ψ₀ cho task bê khay, tôi muốn fine-tune stage 3 một lần ("run M") trên toàn bộ dữ liệu cảnh đồ gá đã lọc theo sai lệch đặt, gồm episode đầy đủ và đoạn đặt cắt riêng, để có checkpoint mới cho eval vòng chung kết càng sớm càng tốt.

Dữ liệu là **một** dataset ghép từ bốn phần. Mỗi phần là một tập con "Q" của một release LeRobot v2.1 của cảnh đồ gá (env `simple/G1WholebodyTrayTransferJigTeleop-v0`):

| Phần | Release | Kho | Nội dung | Giữ (seed) |
|---|---|---|---|---|
| 1 | `tray_s1_bfbdcbcf719e` | `tray-s1-jig2-20261122` | Mức 1, episode đầy đủ | 356 |
| 2 | `tray_s1_8631ace9b1b3` | `tray-s1-jig2-20261122` | Mức 2, episode đầy đủ | 142 |
| 3 | `tray_s1place_a1797e480160` | `tray-s1place-jig2-20261124` | Đoạn đặt cắt từ release cha mức 1 có lệch đích | 377 |
| 4 | `tray_s1place_56e6d006d8d1` | `tray-s1place-jig2-20261124` | Đoạn đặt cắt (release cha thứ hai) | 162 |
| | | | **Tổng** | **1037 episode, 948 639 khung** |

Số episode và số khung là **thực đo ngày 25/11/2026** trên máy sinh. Danh sách giữ của từng release (sai lệch đặt ≤ 3 cm và ≤ 5°, Hiếu chốt 25/11/2026) nằm trên máy sinh dưới dạng một file JSON `{release_id: [seed, ...]}`; người chạy tách thành một file cho mỗi release. Release cắt đoạn đặt do `packages/flywheel-simple/src/flywheel_simple/tray/cut.py` sinh (marker `meta/flywheel_cut.json`).

## Cách làm

**[Đề xuất] Claude 25/11/2026; Hiếu đã chốt ngưỡng lọc và một run.**

| Phương án | Nội dung | Được | Mất |
|---|---|---|---|
| **A (chọn)** | Một run M trên cả bốn phần ghép | Một phiên Colab, checkpoint sớm nhất; dùng hết dữ liệu đã lọc | Không có đối chứng cặp trong cùng plan |
| B | M và run đối chứng K (chỉ 498 episode đầy đủ) song song | Đo được phần đóng góp của đoạn đặt | Gấp đôi CU; trễ nếu Colab từ chối phiên thứ hai |
| C | Mở rộng plan cặp `he-tray-pair60k.yaml` | Dùng lại mã | Plan cặp cần hai cha trong lưới đầy đủ và env eval cũ, không hợp |

Vì sao một run: Hiếu chốt một run để có checkpoint sớm. So sánh với các run cũ (C, C+, `C_ALL`, `C_70`…) **chỉ mang tính mô tả**: khác cảnh (đồ gá), khác dữ liệu, khác số bước và khác env eval, nên không phải phép so cặp. Run đối chứng K (498 episode đầy đủ một mình, cùng recipe) là **tùy chọn, Hiếu quyết sau**; plan M không chặn việc thêm K thành plan riêng.

Công thức train:

| Mục | Giá trị |
|---|---|
| Recipe | `configs/models/psi0-stage3.yaml`, batch 16, seed train 0 |
| Cha | Cùng cặp checkpoint cha của plan cặp DA-34 (`configs/runplans/tray/he-tray-pair60k.yaml`); bản nháp chọn cha của C (`psi0-baseline-egodex-he`), cần Hiếu xác nhận |
| Số bước | `max_training_steps` 100 000 trên một L4 (Hiếu chốt 25/11/2026); là trường của plan, đổi được trước freeze |
| Checkpoint đọc | Chính: 100 000. Đọc sớm: 60 000 và 80 000 |
| Stats | Của chính tập ghép (`own_train_set`) |
| Job | `da48-ft-m-s0`; thư mục Drive dưới `MyDrive/denso/da48/` (`cuts/`, `runs/`) |
| Plan | `configs/runplans/tray/he-tray-jig-m.yaml`, schema mới `flywheel_psi0.tray.mixplan` (`TrayMixPlan`, một run, N phần) |

Chi phí và thời gian (**ước lượng**, chưa đo trên dữ liệu này): khoảng 40 CU và khoảng 20 giờ cho 100 000 bước trên L4, từ run C của DA-34 (40 000 bước, 15,99 CU, 8,27 giờ, thực đo). A100 không nhanh hơn trong thực tế (`C70_R1`: 60 000 bước mất khoảng 11,5 giờ và 77,27 CU), nên Hiếu chọn L4 ngày 25/11/2026. Số đo thật ghi ở 4.2.

Vì sao cần mã mới (đã đọc mã ở `origin/master` `d54a4d89`):

- `tray/demo_sets.py` chỉ dựng các tập lồng nhau theo hạng băm; chưa chọn được đúng một danh sách seed cho trước.
- `TrayRunPlan` chỉ có một release; `TrayPairPlan` cần hai cha trong lưới đầy đủ và env eval cũ. Không plan nào chứa được bốn phần và một run.
- `tray/colab_train.py` chỉ biết các nhánh của DA-34, thư mục Drive gán cứng `MyDrive/denso/da34/cuts/`, và không có pha khôi phục run sau khi mất VM.

## Tiêu chí chấp nhận

1. `demo_sets --keep-seeds FILE` giới hạn ứng viên vào danh sách seed trước khi xếp hạng, nên `--size Q=<số seed>` cho đúng danh sách đó; từ chối seed không có trong release và danh sách có seed trùng; ghi sha256 của file giữ vào đầu ra; chạy được không cần `--qa-work`. Có test.
2. `tray/mixplan.py`: plan một run `TrayMixPlan` (N ≥ 1 phần, mỗi phần ghim release, file demo set và sha256, tên tập, `set_hash`, n), ghim `episodes`, `frames`, `stats_sha256`, nhánh `M` với cha, số bước trong `recipe.overrides`, `checkpoints` (chính và đọc sớm, bội của `checkpointing_steps`, không quá số bước), luật đọc (`interpretation`). Lệnh `check` (đọc JSON, chạy được trên VM Colab trước khi cài), `freeze` (ghi lock), `pack` (tar và `.json` có số byte, sha256). Có test, gồm ghép bốn phần qua `cplus_cut.join_cuts` và các ca từ chối (sai số phần, sai sha256 stats, chưa freeze).
3. `colab_train --branch M` đọc `configs/runplans/tray/he-tray-jig-m.yaml`, job `da48-ft-m-s0`, lấy tar từ thư mục Drive của plan; từ chối chạy khi hằng frozen id còn `None` hoặc plan còn chỗ ghim trống; có pha `restore` đưa `runs/<job>` từ Drive về VM để `Psi0Trainer` chạy tiếp. Các nhánh cũ giữ nguyên hành vi (test chứng minh).
4. `uv run ruff check`, `uv run mypy` (không thêm lỗi), `uv run pytest`, `uv run lint-imports`, `scripts/repo/check_links.py`, `scripts/repo/pr_guard.py` qua.
5. Sau PR mã: bốn phần, tập ghép và các chỗ ghim dựng trên `rtx3060`; PR freeze (ghim plan, lock, frozen id, luật đọc, runbook); job chạy đủ trên Colab L4; checkpoint lưu Drive, VM dừng, có dòng sổ chi phí thực đo; checkpoint giao cho DA-47.

## Nhiệm vụ

- [x] 1.1 Viết story (file này)
- [x] 2.1 `demo_sets --keep-seeds`, có test (AC 1)
- [x] 2.2 `tray/mixplan.py`: `TrayMixPlan`, `check`, `freeze`, `pack`, có test (AC 2)
- [x] 2.3 `colab_train --branch M`, plan nháp `he-tray-jig-m.yaml`, thư mục Drive theo plan, pha `restore`, có test (AC 3)
- [x] 2.4 Chạy đủ kiểm tra, `check_links`, `pr_guard` (AC 4)
- [x] 3.1 Trên `rtx3060`: tách file giữ, `demo_sets --keep-seeds` cho bốn release, `demo_subset` bốn phần, `cplus_cut` ghép, đọc các giá trị cần ghim (AC 5)
- [x] 3.2 PR freeze: điền ghim vào plan, bỏ `status: draft`, `mixplan freeze`, đặt frozen id trong `colab_train`, luật đọc và runbook trong `docs/he/tray-jig.md` (AC 5)
- [x] 4.0 Cho phép wandb online qua FW_WANDB_MODE (Hiếu yêu cầu 25/11/2026), có test
- [ ] 4.1 `mixplan pack`, đưa tar lên Drive, launch trên Colab L4 dưới watcher (AC 5)
- [ ] 4.2 Persist checkpoint lên Drive, dừng VM, dòng sổ chi phí thực đo, giao checkpoint cho DA-47 nhóm A (AC 5)

## Phạm vi file

Theo 07 mục 3.1. File story luôn được sửa.

- `packages/flywheel-psi0/src/flywheel_psi0/tray/`
- `packages/flywheel-psi0/tests/tray/`
- `packages/flywheel-psi0/src/flywheel_psi0/trainer/` (chỉ `psi0_trainer.py`, công tắc wandb)
- `packages/flywheel-psi0/tests/` (chỉ test của trainer)
- `scripts/he/demo_subset.py` (chỉ khi một lỗi chặn release cắt)
- `configs/runplans/tray/`
- `docs/he/` (file mới `docs/he/tray-jig.md` cho luật đọc và runbook; `docs/he/tray.md` chỉ thêm tối đa một dòng chỉ mục)

## Ghi chú cho người làm

- Không sửa `flywheel.contracts`, `pyproject.toml`, `uv.lock`, workflow CI hay `configs/` dùng chung ngoài `configs/runplans/tray/`. Cần trường hợp đồng mới thì dừng lại và báo Hiếu.
- Plan nháp không bịa hash: mọi chỗ chưa biết để `null`, `check --launch` và `freeze` từ chối và liệt kê.
- `cplus_cut.join_cuts` lấy `meta/` (kể cả `tasks.jsonl`) của phần đầu: bốn phần phải cùng câu lệnh task. Kiểm ở 3.1 trước khi ghép.
- `demo_subset` chép cả `meta/flywheel_cut.json` của release cắt vào phần của nó; file này không vào tập ghép (chỉ `meta/` của phần 1, release đầy đủ, được chép).
- Recipe giữ 5 checkpoint gần nhất trên VM (`max_checkpoints_to_keep`); `persist --watch` chép mọi checkpoint đã lưu xong lên Drive, nên 60 000 và 80 000 còn trên Drive. Xem chỗ trống Drive trước khi launch.
- Không chạy gì trên `rtx3060` hay Colab trong PR mã. Job GPU chỉ Hiếu chạy, từ plan đã freeze.
- Số chưa đo ghi là ước lượng.

## Kiểm thử

- `uv run pytest packages/flywheel-psi0/tests/tray`
- `uv run ruff check`, `uv run mypy` (lệnh đủ ở README gốc), `uv run pytest`, `uv run lint-imports`
- `python3 scripts/repo/check_links.py`
- `python3 scripts/repo/pr_guard.py --base origin/master --head HEAD --branch "$(git branch --show-current)"`

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 25/11/2026 | 3.1, 3.2: tập M dựng trên `rtx3060` (1 037 episode, 948 639 khung, thực đo) và ghim vào plan; Hiếu chốt GPU L4, trần 60 CU; plan đóng băng `rp_a410d01efa62`; luật đọc và runbook ở `docs/he/tray-jig.md` | Hiếu (soạn với Claude) |
| 25/11/2026 | Tạo story theo quyết định của Hiếu ngày 25/11/2026 (ngưỡng lọc ≤ 3 cm và ≤ 5°, một run M); phương án do Claude đề xuất | Hiếu (soạn với Claude) |
| 25/11/2026 | 4.0: công tắc `FW_WANDB_MODE` (offline mặc định, online khi đặt) cho trainer, để run M ghi wandb.ai trực tiếp; thêm hai đường dẫn vào Phạm vi file | Hiếu (soạn với Claude) |
