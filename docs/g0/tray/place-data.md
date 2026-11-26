# Dữ liệu riêng cho bước đặt khay (DA-46)

Story: [DA-46](../../product/stories/DA-46-du-lieu-rieng-buoc-dat.md). Cảnh, planner và lô gốc 568 episode: [jig.md](jig.md). Mọi số ở mục 3 là thực đo trên laptop ngày 23/11/2026, một lần chạy, mẫu nhỏ (36 seed mỗi cấu hình). Mục 5 là runbook nháp, chưa chạy.

## 1. Vì sao

Policy Ψ₀ hỏng nhiều nhất ở bước đặt. Trong lô gốc, ARRIVE_B + LOWER + RELEASE chỉ chiếm trung vị 18,8 % số khung (jig.md mục 4.13), và mọi episode tới bàn B theo cùng một kiểu. Story này sinh thêm episode mà robot tới nơi lệch đích rồi tự sửa, và chỉ giữ đoạn từ lúc tới nơi trở đi.

## 2. Cách làm

Ba bước, đều chạy trên cảnh đồ gá `jig2` với planner `da41-planner-8`:

| Bước | Lệnh | Việc |
|---|---|---|
| Sinh | `scripts/g0/tray/generate.py --scene jig --carry-jitter-ahead A --carry-jitter-side S` | Mỗi episode dịch đích của pha CARRY một đoạn rút đều trong `[-A, A]` (dọc hướng đi, dương là tiến sâu hơn về bàn B) và `[-S, S]` (sang trái), tính từ seed. Robot tới lệch; ARRIVE_B sửa bằng vòng bước sẵn có |
| QA và release | Như lô gốc (jig.md mục 5.1, bước 2–8) | Episode đầy đủ qua QA phát lại, release, QA DA-03, lọc chất lượng, tập `ALL` |
| Cắt | `scripts/g0/tray/cut_place.py --release R --batch B --releases D [--demo-sets F --set ALL]` | Release dẫn xuất `tray_s1place_<hash12>`: mỗi episode từ ARRIVE_B trừ 1 s tới hết |

Điều cần biết:

- `gen_log.jsonl` ghi thêm `phases` (tên pha, giây sim từ lúc planner bắt đầu) và `carry_offset` (mét: dọc, ngang) cho mỗi lượt. Khung k của episode ghi ở giây k/50, nên pha vào ở giây t bắt đầu tại khung `round(50 t)`.
- Độ lệch không nằm trong `PlannerConfig`. `planner_version` chỉ thêm hậu tố khi bật, ví dụ `da41-planner-8+cfg.bee61399+cj.a100s100` (±10 cm hai trục). Không bật thì chuỗi vẫn là `da41-planner-8+cfg.bee61399`, nên lô gốc không đổi. `generate` từ chối trộn hai chuỗi trong một thư mục.
- Bản cắt giữ layout Ψ₀ của release cha (state 32, action 36, 50 fps). Parquet đánh số lại `frame_index`, `timestamp`, `index`, `episode_index`; video mã hóa lại từ khung bắt đầu (h264, số khung bằng số dòng); bốn file stats tính lại trên bản cắt. `meta/flywheel_cut.json` ghi `release_id` và `release_hash` của cha, cùng khoảng khung nguồn, `carry_offset` và mốc pha của từng episode.
- Đường train hiện có đọc được bản cắt mà không cần trường hợp đồng mới: `demo_sets.read_release`, bộ đọc DA-03 (`iter_episodes`, `check_index`), `scripts/he/demo_subset.py` (có test). File tập demo cho bản cắt phải dựng riêng trên hash của bản cắt; `--demo-sets` của lệnh cắt chỉ dùng file của cha để chọn seed.
- QA phát lại theo `uid` chỉ chạy được trên episode đầy đủ. Vì vậy cắt sau khi cha đã có tập `ALL`, và chỉ cắt các seed trong tập đó.

## 3. Lô mẫu trên laptop (nhiệm vụ 4.1, 23/11/2026)

Ba cấu hình trên cùng 36 seed train chưa dùng: mức 1 `510000–510023` (24 seed), mức 2 `511000–511011` (12 seed). Một worker, commit `e170f258`, hình ảnh SimReady. Thư mục: `fwdata/simple/tray/gen/da46-sample/` ở thư mục gốc của repo (ngoài git, 108 lượt). Thời gian một lượt: trung bình 34–36 s.

### 3.1 Tỉ lệ thành công

| Cấu hình | Mức 1 | Mức 2 | Tổng | Lỗi |
|---|---|---|---|---|
| Không lệch | 24/24 | 11/12 | **35/36 (97 %)** | `L-ONE-HAND` 1 |
| ±5 cm | 22/24 | 10/12 | **32/36 (89 %)** | `L-ONE-HAND` 3, `L-TRAY-TILT` 1 |
| ±10 cm | 22/24 | 10/12 | **32/36 (89 %)** | `L-ONE-HAND` 2, `L-TRAY-TILT` 2 |

Đọc:
- Bật lệch làm mất 3 trong 35 seed mà bản không lệch đạt, ở cả hai biên độ. Seed 511000 hỏng ở cả ba cấu hình (tuột một tay ngay đầu ARRIVE_B), không do lệch.
- Mọi lỗi thêm xảy ra từ ARRIVE_B trở đi: tuột một tay khi đang bước sửa hoặc đang hạ, và khay nghiêng lúc nhả. Hai lượt `L-TRAY-TILT` ở ±10 cm đều có độ lệch dọc dương (robot đứng gần bàn hơn); mẫu quá nhỏ để kết luận đó là nguyên nhân.
- Với 36 lượt, khoảng tin cậy của 89 % rộng (khoảng ±10 điểm). Hai biên độ không phân biệt được về tỉ lệ thành công.

### 3.2 Robot tới lệch bao nhiêu, và đặt có kém đi không

Sai lệch khay so với đích đồ gá, tính như bộ chấm (khoảng cách phẳng; góc theo modulo nửa vòng). "Lúc tới" là khung vào ARRIVE_B; "cuối" là khung cuối. Chỉ tính lượt thành công.

| Cấu hình | n | Lúc tới (cm): trung vị / p90 / max | Lúc tới, dọc: trung bình (độ lệch chuẩn) | Lúc tới, ngang: độ lệch chuẩn | Cuối (cm): trung vị / p90 / max | Cuối, góc (°): trung vị / max |
|---|---|---|---|---|---|---|
| Không lệch | 35 | 3,88 / 5,26 / 5,69 | +3,61 (0,43) | 1,44 | 1,39 / 2,71 / 3,67 | 0,95 / 7,27 |
| ±5 cm | 32 | 4,47 / 8,11 / 10,68 | +3,11 (2,83) | 2,84 | 1,24 / 2,27 / 2,89 | 1,04 / 6,95 |
| ±10 cm | 32 | 6,57 / 13,24 / 15,63 | +2,79 (5,26) | 5,18 | 1,39 / 2,77 / 3,93 | 0,98 / 6,47 |

Đọc:
- **Sai lệch đặt cuối không kém đi** khi bật lệch: trung vị 1,2–1,4 cm ở cả ba, không lượt nào ngoài dung sai 5 cm hoặc 10°. Khay vẫn dừng ngắn khoảng 1,2 cm theo trục dọc, như lô gốc.
- **Điều khác với giả định ban đầu của story:** không bật lệch, robot không tới "gần đúng chỗ" theo trục dọc. Nó luôn dừng ngắn khoảng 3,6 cm (độ lệch chuẩn 0,4 cm), vì CARRY kết thúc khi còn cách đích `carry_tol` = 3 cm. Lô gốc vì thế đã có ca "tới ngắn rồi bước tới", nhưng chỉ một kiểu. Cái nó thiếu là độ đa dạng: lệch ngang, tới quá đích, và lệch lớn.
- Hệ quả: độ lệch dọc dương triệt bớt khoảng ngắn sẵn có, nên không phải lượt nào bật lệch cũng tới lệch hơn. Ở ±5 cm, 13/32 lượt tới lệch trên 5 cm và 4/32 tới quá đích; ở ±10 cm là 20/32 và 11/32. Không bật lệch: 5/35 và 0/35.
- Lệch ngang trên 3 cm lúc tới: 4/35 (không lệch), 11/32 (±5 cm), 20/32 (±10 cm).

### 3.3 Độ dài đoạn đặt

Số khung trung bình mỗi episode thành công (50 khung = 1 s). "Đoạn đặt" là từ ARRIVE_B tới hết; "bản cắt" thêm 1 s dẫn.

| Cấu hình | Cả episode | ARRIVE_B (s, trung vị) | Đoạn đặt | Bản cắt | Bản cắt / cả episode |
|---|---|---|---|---|---|
| Không lệch | 1400 | 2,68 | 321 | 371 | 26 % |
| ±5 cm | 1431 | 2,97 | 351 | 401 | 28 % |
| ±10 cm | 1522 | 5,74 | 439 | 489 | 32 % |

ARRIVE_B dài ra chủ yếu vì planner chờ 2 s giữa hai lần quyết định bước (bộ lọc `arrive_filter_tau`), không phải vì quãng đường. 3–6 lượt mỗi cấu hình chạm trần thời gian của ARRIVE_B (7,02 s) rồi hạ luôn, kể cả 3 lượt không lệch.

### 3.4 Tỉ trọng bước đặt nếu thêm N episode cắt

**Ước lượng**, từ trung bình của lô mẫu (không phải số đếm trên lô gốc): lô gốc 568 episode × 1400 khung, đoạn đặt 321 khung mỗi episode (22,9 %; jig.md đo 18,8 % cho ARRIVE_B + LOWER + RELEASE và 3,0 % cho RETREAT theo trung vị). Mỗi episode cắt thêm 1 s dẫn không tính là đoạn đặt.

| Thêm | ±5 cm (401 khung, 351 đặt) | ±10 cm (489 khung, 439 đặt) |
|---|---|---|
| 0 | 22,9 % | 22,9 % |
| 300 episode cắt | 31,4 % | 33,3 % |
| 600 episode cắt | 37,9 % | 40,9 % |
| 900 episode cắt | 43,1 % | 46,7 % |

Với 600 episode cắt ở ±10 cm, tập train có khoảng 1,09 triệu khung (lô gốc khoảng 0,80 triệu), tức thêm khoảng 37 % khung.

### 3.5 Chạy trọn đường trên lô mẫu ±10 cm mức 1

Chạy thật các lệnh của mục 2 trên 22 episode ghi được của `j10-l1`.

| Bước | Kết quả |
|---|---|
| QA phát lại (`replay_qa.py`) | 22/22 qua, lệch khay 0,0 mm |
| Release cha (`release.py`) | `tray_s1_07ed947f223c`, 22 episode, 33 278 khung, 193 MB |
| Cắt (`cut_place.py`, dẫn 1 s, không `--demo-sets`) | `tray_s1place_c4865e156a69`, 22 episode, 10 699 khung (32 % của cha), 56 MB (2,5 MB mỗi episode) |
| Kiểm bản cắt | `verify_manifest` đúng; ở cả 22 episode số khung video giải mã bằng số dòng parquet và bằng `length`; state 32, action 36, `frame_index` bắt đầu từ 0, `next.done` ở dòng cuối; `stats.json` trùng `stats_psi0.json`; mọi episode cắt từ ARRIVE_B |

Chưa chạy trên lô mẫu: ingest, phát lại DA-17, QA DA-03, lọc chất lượng (bước 4–8 của jig.md mục 5.1), nên bản cắt mẫu lấy mọi episode của cha thay vì tập `ALL`.

**Video để xem:** `fwdata/simple/tray/gen/da46-sample/releases/tray_s1place_c4865e156a69/videos/chunk-000/egocentric/episode_000000.mp4` (từ thư mục gốc của repo; seed 510000, mức 1, độ lệch đích −5,3 cm dọc và −9,5 cm ngang, tới nơi lệch 15,6 cm, đặt cuối lệch 0,5 cm; 414 khung, 8,3 s, camera đầu). Episode đầy đủ tương ứng: `releases/tray_s1_07ed947f223c/videos/chunk-000/egocentric/episode_000000.mp4`.

### 3.6 Biên độ đã chốt

**[Đã chốt]** (Hiếu, 24/11/2026) ±10 cm cả hai trục (`--carry-jitter-ahead 0.10 --carry-jitter-side 0.10`). Lý do dưới đây là của đề xuất ngày 23/11/2026.

- Tỉ lệ thành công bằng ±5 cm trên mẫu này (32/36), sai lệch đặt cuối không đổi.
- Độ đa dạng lúc tới gần gấp đôi (độ lệch chuẩn 5,2 cm so với 2,8 cm mỗi trục), số lượt tới quá đích gần gấp ba (11 so với 4), và mỗi episode cắt dài hơn 22 %.
- Chưa đo: biên độ lớn hơn ±10 cm; tỉ lệ thành công với mẫu đủ lớn để tách hai biên độ; việc policy có hưởng lợi từ lệch 10–15 cm hay không (chỉ biết sau khi train và eval).
- Phương án dè dặt hơn: ±5 cm. Đổi lại là ít ca lệch lớn và ít ca tới quá đích.

## 4. Giới hạn đã biết

- `scripts/g0/tray/run_shards.py` kiểm phiên bản planner không hậu tố và không chuyển `--scene` hay cờ lệch cho shard chạy lại, nên không dùng được để chạy tiếp một lô đồ gá hay lô có lệch. `generate.py` chạy lại cùng lệnh vẫn nối tiếp được. Chưa sửa.
- Lượt sinh ném lỗi (ví dụ lỗi renderer) ghi `carry_offset` bằng 0 và `phases` rỗng. Lượt đó không được ghi dữ liệu nên không ảnh hưởng bản cắt.
- Bản cắt bắt đầu giữa episode: khung đầu robot đang đi và cầm khay. Trạng thái đầu của Ψ₀ lấy từ quan sát nên không cần gì thêm, nhưng chưa train thử.
- Khay dừng ngắn khoảng 1,2–1,5 cm theo trục dọc, giữ nguyên như lô gốc (quyết định của story).
- `uv run mypy` theo README báo 20 lỗi ở 10 file ngoài story này (stub numpy trong `flywheel-data`, `flywheel-eval`, `flywheel-psi0`, `replay/compare.py`, `pico/style.py`) trên máy laptop; không lỗi nào ở file story này sửa.

## 5. Runbook nháp cho lô trên `rtx3060`

Đã chạy ngày 24–25/11/2026 theo lời Hiếu; số thực đo ở mục 7. Phần dưới giữ nguyên như lúc viết (ước lượng trước khi chạy). Claude không chạy gì trên `rtx3060` trong story này cho tới khi Hiếu đồng ý. Đường dẫn code và venv trên `rtx3060` lấy theo jig.md mục 5 (`~/denso-da41`), **chưa kiểm lại** ngày 23/11/2026.

| Mục | Giá trị |
|---|---|
| Kho | `~/fwdata/datasets/tray-s1place-jig2-<YYYYMMDD>/` (`$B`): `gen-l1/`, `gen-l2/`, `releases/`, `pipeline/`, `replay17/`, `reports/`, `cards/`, `round.yaml` |
| Biên độ | ±10 cm hai trục (mục 3.6); `planner_version` phải là `da41-planner-8+cfg.bee61399+cj.a100s100` |
| Số lượt | 710, để còn khoảng 600 episode cắt. Ước lượng tỉ lệ giữ 85 %: 89 % lúc sinh (lô mẫu) × 95,5 % qua QA và lọc (lô gốc: 568/595) |
| Chia mức | Như lô gốc, khoảng 70 % mức 1 và 30 % mức 2: **497 lượt mức 1, 213 lượt mức 2** |
| Seed | Train, chưa dùng: mức 1 `520000–520496`, mức 2 `521000–521212`. Đã dùng thêm so với bảng ở jig.md mục 5.1: `500000–500441`, `501000–501189` (lô gốc), `510000–510023`, `511000–511011` (lô mẫu mục 3) |
| Worker | Mức 1: 10, mức 2: 4, tổng 14 (trần của story; máy dùng chung không quá 22). Xem `free -g` trước; thiếu RAM thì giảm worker và `MemoryMax` (khoảng 3,7 GB mỗi worker) |
| Thời gian (ước lượng) | Sinh 710 × khoảng 79 s (lô gốc đo 72,6 s mỗi lượt; episode có lệch dài hơn khoảng 9 %) ≈ 15,6 giờ-worker, khoảng 1,2 giờ. QA phát lại khoảng 630 × 88 s ≈ 15,4 giờ-worker, khoảng 1,3 giờ với 12 worker. Phát lại DA-17 cỡ đó, khoảng 1,3 giờ. Cắt 600 episode một tiến trình: khoảng 20–40 phút (laptop đo 1,8 s cho một video 290 khung). Tổng khoảng 4,5–5 giờ |
| Dung lượng (ước lượng) | Thô khoảng 6,2 GB, release cha khoảng 5,6 GB (lô gốc 8,9 và 8,2 MB mỗi episode, nhân 1,09), bản cắt khoảng 1,5 GB (lô mẫu: 2,5 MB mỗi episode), thư mục làm việc. Tổng khoảng 15 GB |
| Điều kiện dừng | Sau mỗi bước, tỉ lệ giữ của một mức dưới **75 %** thì dừng và gửi output. Ngưỡng 85 % của lô gốc không dùng được vì tỉ lệ dự kiến đã ở quanh 85 % |

Chuẩn bị (sau khi PR của DA-46 merge thì dùng `master`):

```bash
git -C ~/denso-da41 fetch origin && git -C ~/denso-da41 checkout DA-46-tray-place-data && git -C ~/denso-da41 pull --ff-only
```

```bash
cd ~/denso-da41 && grep -n "^PLANNER_VERSION\|class CarryJitter" packages/flywheel-simple/src/flywheel_simple/tray/planner.py && B=~/fwdata/datasets/tray-s1place-jig2-$(date +%Y%m%d) && mkdir -p $B && echo $B && df -h ~/fwdata && free -g
```

**Bước 1. Sinh**, hai mức cùng lúc (thay `$B` bằng đường dẫn in ở trên):

```bash
cd ~/denso-da41 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid systemd-run --user --scope -p MemoryMax=48G -p MemorySwapMax=0 fwdata/simple/.venv/bin/python scripts/g0/tray/generate.py --scene jig --carry-jitter-ahead 0.10 --carry-jitter-side 0.10 --out $B/gen-l1 --n 497 --level 1 --seed-start 520000 --workers 10 > $B/gen-l1.log 2>&1 < /dev/null &
```

```bash
cd ~/denso-da41 && MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src nohup setsid systemd-run --user --scope -p MemoryMax=16G -p MemorySwapMax=0 fwdata/simple/.venv/bin/python scripts/g0/tray/generate.py --scene jig --carry-jitter-ahead 0.10 --carry-jitter-side 0.10 --out $B/gen-l2 --n 213 --level 2 --seed-start 521000 --workers 4 > $B/gen-l2.log 2>&1 < /dev/null &
```

Đọc kết quả (tiến độ và khi xong):

```bash
cd $B && for L in 1 2; do cat gen-l$L/shard-*/gen_log.jsonl | python3 -c "import sys,json,collections; r=[json.loads(l) for l in sys.stdin]; ok=sum(x['recorded'] for x in r); print('L$L', len(r), 'lượt', ok, 'ghi', f'{ok/max(len(r),1):.1%}', {x['planner_version'] for x in r}, collections.Counter(x['failure'] or x['abort_reason'] for x in r if not x['success']))"; done
```

**Bước 2–8.** Đúng các lệnh của jig.md mục 5.1 (QA phát lại, release, ingest, phát lại DA-17 với `--env-id simple/G1WholebodyTrayTransferJigTeleop-v0`, report và QA, lọc chất lượng, tập `ALL`), chỉ đổi `B=$PWD/fwdata/da41-jig-600` thành đường dẫn kho ở trên. Mỗi lệnh sim vẫn nằm trong `nohup setsid systemd-run --user --scope -p MemoryMax=48G -p MemorySwapMax=0 … < /dev/null &`. Kết quả là hai release cha `tray_s1_…` và `demo_sets-l1.json`, `demo_sets-l2.json`.

**Bước 9. Cắt** (không cần GPU; thay `REL` và `L` cho từng mức):

```bash
cd ~/denso-da41 && REL=tray_s1_XXXX && L=1 && PYTHONPATH=packages/flywheel-simple/src nohup setsid systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 fwdata/simple/.venv/bin/python scripts/g0/tray/cut_place.py --release $B/releases/$REL --batch $B/gen-l$L --releases $B/releases --demo-sets $B/demo_sets-l$L.json --set ALL > $B/cut-l$L.log 2>&1 < /dev/null &
```

```bash
cd $B && cat cut-l*.log && for R in releases/tray_s1place_*; do python3 -c "import json; d=json.load(open('$R/meta/flywheel_cut.json')); print('$R', d['parent']['release_id'], len(d['episodes']), 'episode', d['frames'])"; done
```

**Bước 10. Tập demo của bản cắt, thẻ và khai báo.** Dựng tập `ALL` trên từng bản cắt (không `--qa-work`, không `--quality`: đã lọc ở cha), rồi viết `cards/<release_id>.yaml` cho hai release cha và hai bản cắt (bản cắt: `kind: cut`, `lineage.parents` trỏ release cha) và `round.yaml`, theo mẫu của kho `tray-s1-jig2-20261122`:

```bash
cd ~/denso-da41 && for R in $B/releases/tray_s1place_*; do N=$(wc -l < $R/meta/episodes.jsonl) && uv run python -m flywheel_psi0.tray.demo_sets --release $R --size ALL=$N --out $B/demo_sets-$(basename $R).json 2>&1 | tail -2; done
```

Gửi Claude: output của bước 1, 2, 6, 8 và 9.

## 6. Việc tiếp theo (ngoài phiên đầu của DA-46)

- Hiếu xem video mẫu và chọn biên độ; sau đó chạy mục 5 (nhiệm vụ 5.1). Xong, xem mục 7.
- Ghép tập train: 568 episode gốc và các episode cắt (`demo_subset` từng phần rồi ghép như `cplus_cut`), stats tính trên tập ghép. Thuộc story train.
- `run_shards.py` cho cảnh đồ gá và lô có lệch, nếu cần chạy lại shard hỏng.

## 7. Lô trên `rtx3060` (nhiệm vụ 5.1, thực đo 24–26/11/2026)

Kho: `~/fwdata/datasets/tray-s1place-jig2-20261124/` trên `rtx3060`, 14 GB. Bản sao trên laptop ở `fwdata/datasets/tray-s1place-jig2-20261124/` (7,0 GB, không có `gen-l*` và `replay17`; 3 965 file, số byte khớp, sha256 của `meta/info.json` và `meta/episodes.jsonl` khớp cho cả bốn release). Mọi số dưới đây lấy từ `reports/batch_summary.json` của kho, file đó ghi nguồn của từng số.

| | Mức 1 | Mức 2 | Tổng |
|---|---|---|---|
| Seed | `520000–520496` | `521000–521212` | |
| Lượt sinh | 497 | 213 | 710 |
| Ghi được | 459 | 193 | 652 (91,8 %) |
| QA phát lại lúc sinh | 459/459 | 193/193 | 652/652 |
| QA loại | 2 | 2 | 4 |
| Lọc chất lượng bỏ | 26 | 10 | 36 |
| Tập `ALL` | 431 | 181 | 612 (86,2 % số lượt) |
| Release cha | `tray_s1_b71a17f250f1`, 459 episode, 681 541 khung | `tray_s1_45031800e357`, 193 episode, 288 177 khung | |
| Bản cắt | `tray_s1place_a1797e480160`, 431 episode, 198 903 khung | `tray_s1place_56e6d006d8d1`, 181 episode, 83 372 khung | 612 episode, 282 275 khung |
| Độ dài bản cắt trung bình | 461,5 khung | 460,6 khung | |
| Tỉ trọng đoạn cắt trong episode `ALL` của cha | 31,1 % | 30,8 % | |
| Lệch vị trí khi đặt xong (`ALL`): trung vị, p90, lớn nhất | 1,57; 2,92; 4,95 cm | 1,51; 2,70; 4,78 cm | |
| Lệch góc khi đặt xong (`ALL`): trung vị, p90, lớn nhất | 0,85; 4,47; 9,89° | 0,81; 2,90; 6,12° | |
| Thời gian mỗi lượt sinh: trung bình, p95 | 79,9 s; 95,2 s | 74,3 s; 94,5 s | 15,4 giờ-worker |
| Dung lượng: thô, cha, cắt | 4,3; 3,9; 1,1 GB | 1,9; 1,7; 0,43 GB | |

So với ước lượng ở mục 5: tỉ lệ giữ 86,2 % (ước 85 %), không mức nào dưới ngưỡng dừng 75 %; thời gian mỗi lượt gần đúng 79 s; 612 episode cắt (ước khoảng 600). Lượt hỏng lúc sinh: `L-ONE-HAND` 24, `L-TRAY-TILT` 14, `L-PLACE-POSE` 12, hết giờ ở RELEASE 7, hết giờ ở LIFT 1.

Kho có thêm sau bước 10: `demo_sets-tray_s1place_*.json` (tập `ALL` của hai bản cắt), `cards/` (bốn thẻ; bản cắt có `kind: cut` và `lineage.parents`), `round.yaml` (chỉ khai hai release cha, vì bản cắt không có pipeline hay QA riêng), `README.md`, `reports/batch_summary.json`.

Điều cần biết khi dùng lô này:

- Thẻ để `null` các trường không có nguồn trong kho: `generator.simple_commit`, `lineage.ledger`, `quality.place_stage_share`, `place_error_cm.along_mean`. Lô này không có dòng sổ chi phí (0 CU, chỉ CPU của `rtx3060`); đây là một chỗ sót.
- `dataset_report.json` báo `replay_dynamic` trên mọi episode và `replay_success` trên 226/459 (mức 1), 99/193 (mức 2), cùng kiểu với kho gốc `tray-s1-jig2-20261122` (ngưỡng phát lại của DA-17 hiệu chỉnh trên psi-data). Cờ D4 trên `stats.json` được ghi là báo nhầm theo cách ghi của kho gốc; **chưa kiểm riêng cho lô này**.
- Bộ lọc ≤ 3 cm và ≤ 5° mà run M (DA-48) dùng nằm ở `analysis/da48-clean/` của kho, không thuộc `ALL` của lô.
- Mốc thời gian không có trong `gen_log.jsonl`; file sinh đầu tiên ghi 19:42 ngày 24/11, log sinh kết thúc 21:12, phát lại xong 22:49, cắt xong 09:29 ngày 25/11 (giờ máy).

## 8. Lệch góc ở bước CARRY: lô mẫu trên laptop (DA-50 nhiệm vụ 3.1, thực đo 26/11/2026)

Story: [DA-50](../../product/stories/DA-50-train-run-n-nham-loi-dat.md). Mẫu nhỏ, một lần chạy, một worker; số là sơ bộ.

**Cách làm.** `CarryJitter` có thêm biên độ `yaw`: mỗi seed rút một góc, hướng CARRY quay đi góc đó, robot tới bàn B với khay lệch góc so với đồ gá, rồi ARRIVE_B xoay lại. Cờ dòng lệnh `--carry-jitter-yaw-deg`. Độ lệch dọc và ngang của mọi seed giữ nguyên; `planner_version` có thêm hậu tố `y<phần mười độ>` chỉ khi có lệch góc (ví dụ `da41-planner-8+cfg.bee61399+cj.a000s000y150`). Nhật ký sinh và bản cắt ghi `carry_yaw` (rad).

**Hai lần chạy trên cùng 40 seed train chưa dùng** (mức 1 `531000–531019`, mức 2 `532000–532019`), lệch góc ±15°, không lệch vị trí. Thư mục `fwdata/simple/tray/gen/da50-sample/` ở thư mục gốc của repo (ngoài git).

| | Trước khi sửa ARRIVE_B (`y15-l*`) | Sau khi sửa (`y15fix-l*`) |
|---|---|---|
| Thành công | 29/40 (72,5 %) | 36/40 (90 %) |
| Mức 1, mức 2 | 14/20, 15/20 | 19/20, 17/20 |
| Lệch tới 10° | 19/21 | 21/21 |
| Lệch trên 10°, dương | 8/8 | 8/8 |
| Lệch trên 10°, âm | 2/11 | 7/11 |
| Lượt hỏng | `L-PLACE-POSE` 9, `L-ONE-HAND` 1, hết giờ RELEASE 1 | `L-PLACE-POSE` 2, `L-ONE-HAND` 2 |

**Lỗi tìm thấy và bản sửa.** ARRIVE_B chỉ xoay thân trong lúc bước sửa vị trí; tới nơi không lệch vị trí thì robot không bước và không xoay lại, phần lệch góc dồn xuống động tác tay lúc hạ (tối đa 8°). Bản sửa: khi `carry_yaw` khác 0 và thân lệch trên 2° so với hướng đích, ARRIVE_B xoay tại chỗ tới khi còn dưới 1° rồi mới hạ (`ARRIVE_YAW_TOL`, hằng của module, không đổi hash cấu hình). Episode không lệch góc không chạy đoạn mã này; test "lệnh giống từng bit" giữ nguyên.

**Điều chưa biết.**

- Lệch âm trên 10° vẫn hỏng 4/11, lệch dương 0/8. ARRIVE_B và LOWER đối xứng theo dấu; giả thuyết (chưa kiểm) là chiều quay của pha TURN đổi theo dấu lệch. Mẫu 11 và 8 lượt quá nhỏ để kết luận.
- Sai số đặt cuối của các episode thành công chưa đo (cần phát lại như mục 7).
- ARRIVE_B chạm trần 7,02 s ở 18/40 lượt sau khi sửa.
- Hai lô mẫu mang cùng `planner_version` dù khác mã ARRIVE_B; không trộn hai thư mục.

Cổng 85 % của story: đạt ở ±15° sau khi sửa (36/40), trên mẫu 40 lượt.


## 9. Lô lệch góc trên `rtx3060` (DA-50 nhiệm vụ 3.2, thực đo 26–27/11/2026)

Story: [DA-50](../../product/stories/DA-50-train-run-n-nham-loi-dat.md). Kho: `~/fwdata/datasets/tray-s1yaw-jig2-20261126/` trên `rtx3060`, 14 GB. Bản sao trên laptop ở `fwdata/datasets/tray-s1yaw-jig2-20261126/` (khoảng 1,7 GB: hai bản cắt và các file nhỏ; không có `gen-l*/shard-*`, hai release cha và `replay17`). Mọi số dưới đây lấy từ `reports/batch_summary.json`, `analysis/da50-clean/` và log của kho; mục 8 là mẫu 40 lượt trên laptop, không trộn với lô này.

**Cái đã chạy.** Sinh episode đầy đủ trên cảnh đồ gá (`jig2`) với lệch góc ±15° ở CARRY, không lệch vị trí. Planner `da41-planner-8+cfg.bee61399+cj.a000s000y150`, mã commit `713dd05a` (đã có sửa ARRIVE_B của mục 8). Sinh từ 23:32 ngày 26/11 tới 00:47 ngày 27/11 (giờ máy, UTC+7), 14 worker trong scope có `MemoryMax` (6 cho mức 1, 8 cho mức 2). Các bước 2–11 (QA phát lại, release, phát lại DA-17, report, lọc chất lượng, tập `ALL`, cắt, thẻ) chạy liền từ 00:48:35 tới 04:48:10. Cắt, tập `ALL` và thẻ làm đúng như mục 5; chỉ đổi biên độ và seed.

| | Mức 1 | Mức 2 | Tổng |
|---|---|---|---|
| Seed | `540000–540279` | `541000–541419` | |
| Lượt sinh | 280 | 420 | 700 |
| Ghi được | 258 (92,1 %) | 391 (93,1 %) | 649 (92,7 %) |
| Lượt hỏng lúc sinh | `L-ONE-HAND` 8, `L-PLACE-POSE` 7, `L-TRAY-TILT` 4, hết giờ ở RELEASE 3 | `L-PLACE-POSE` 13, `L-ONE-HAND` 8, `L-TRAY-TILT` 5, hết giờ ở RELEASE 2, hết giờ ở LIFT 1 | 22 và 29 |
| QA phát lại lúc sinh | 258/258 | 391/391 | 649/649 |
| QA loại | 2 | 7 | 9 |
| Lọc chất lượng bỏ | 13 | 19 | 32 |
| Tập `ALL` | 243 (86,8 % số lượt) | 365 (86,9 % số lượt) | 608 (86,9 %) |
| Release cha | `tray_s1_2c861cdfe7fd`, 258 episode, 394 929 khung | `tray_s1_02d895d28050`, 391 episode, 596 736 khung | |
| Bản cắt (từ ARRIVE_B hoặc LOWER, lead 1,0 s) | `tray_s1place_e793fb05a9df`, 243 episode, 125 787 khung | `tray_s1place_6a7b780fb66b`, 365 episode, 184 691 khung | 608 episode, 310 478 khung |
| Độ dài bản cắt trung bình | 517,6 khung | 506,0 khung | |
| Tỉ trọng đoạn cắt trong episode `ALL` của cha | 33,8 % | 33,2 % | |
| Lệch vị trí khi đặt xong (`ALL` của cha): trung vị, p90, lớn nhất | 1,32; 2,58; 4,22 cm | 1,37; 2,62; 4,26 cm | |
| Lệch góc khi đặt xong (`ALL` của cha): trung vị, p90, lớn nhất | 0,83; 2,16; 8,38° | 0,82; 3,62; 9,93° | |
| Ngoài 5 cm hoặc 10° | 0 | 0 | |
| Thời gian mỗi lượt sinh: trung bình, p95 | 87,9 s; 96,9 s | 82,3 s; 96,2 s | 59 166 giây-worker (16,4 giờ-worker) |
| Dung lượng: thô, cha, cắt | 2,5; 2,3; 0,65 GB | 3,8; 3,4; 0,97 GB | |

Không mức nào chạm ngưỡng dừng 75 % của story (tỉ lệ giữ của `ALL` so với số lượt là 86,8 % và 86,9 %). Lượt sinh `retried_shards` và `failed_shards` đều rỗng.

**So với ước lượng.** Dòng sổ `job_da50_gen_yaw` (mục 8, viết trước khi chạy) ước tính sinh 700 lượt khoảng 1,1 giờ cộng khởi động (ghi 1,3 giờ) và khoảng 3,5 giờ cho các bước sau.

| | Ước lượng | Thực đo |
|---|---|---|
| Thời gian một lượt sinh | khoảng 80 s | trung bình 84,5 s (87,9 s mức 1, 82,3 s mức 2; cao hơn lô DA-46 khoảng 8 %) |
| Thời gian sinh | 1,3 giờ | 1,25 giờ (23:32 tới 00:47) |
| Các bước 2–11 | khoảng 3,5 giờ | 3,99 giờ (00:48:35 tới 04:48:10) |
| Tỉ lệ giữ của `ALL` so với số lượt | trên 75 % (ngưỡng dừng); lô DA-46 đạt 86,2 % | 86,9 % |
| Dung lượng cả kho | khoảng 15 GB (mục 5) | 14 GB |

Các bước dài nhất: QA phát lại 85,3 phút với 12 worker (tối đa 17,1 giờ-worker, cận trên vì worker không luôn bận), phát lại DA-17 72,2 phút với 12 worker (tối đa 14,4 giờ-worker, cận trên), cắt khoảng 70 phút một tiến trình (mức 1 28,4 phút, mức 2 41,7 phút theo mốc bước). Chỉ dùng CPU, 0 CU; máy là máy của đội.

**Lọc theo vị trí đặt xong (như run M).** Giữ episode có lệch vị trí cuối ≤ 3 cm và lệch góc cuối ≤ 5°, tính trên `ALL` của cha, bằng bộ script của `analysis/da48-clean/` chỉ đổi đường dẫn và id trong `common.py`. Kết quả ghi ở `analysis/da50-clean/keep_3cm_5deg.json`, `per_episode.jsonl`, `summary.json`.

| | Mức 1 | Mức 2 | Tổng |
|---|---|---|---|
| Đạt cả hai ngưỡng | 227/243 (93,4 %) | 327/365 (89,6 %) | 554/608 (91,1 %) |
| Đạt riêng ≤ 3 cm | 233 | 343 | |
| Đạt riêng ≤ 5° | 236 | 338 | |
| Trượt vì vị trí, vì góc, vì cả hai | 10, 7, 1 | 22, 27, 11 | |
| So với số lượt sinh | 227/280 (81,1 %) | 327/420 (77,9 %) | 554/700 (79,1 %) |

Phần của mức 2 trong tập giữ lại là 327/554 = 59,0 %, sát mục tiêu khoảng 60 % của nhiệm vụ 2. Trong `keep_3cm_5deg.json`, hai bản cắt có cùng số seed giữ lại (227 và 327) như hai release cha.

Theo độ lớn và dấu của góc lệch ở CARRY (`|carry_yaw|`, tính trên `ALL`):

| `\|carry_yaw\|` | Mức 1: đạt/tổng | Mức 2: đạt/tổng | Tổng |
|---|---|---|---|
| [0°, 5°) | 68/73 | 115/131 | 183/204 (89,7 %) |
| [5°, 10°) | 78/84 | 113/127 | 191/211 (90,5 %) |
| [10°, 15°) | 81/86 | 99/107 | 180/193 (93,3 %) |
| Dấu dương | 114/119 | 169/191 | 283/310 (91,3 %) |
| Dấu âm | 113/124 | 158/174 | 271/298 (90,9 %) |

Tỉ lệ đạt không giảm khi lệch góc tăng (nhóm 10–15° còn cao hơn một chút), và hai dấu gần bằng nhau. Mẫu 40 lượt ở mục 8 thấy lệch âm trên 10° kém hơn; ở 608 episode điều đó không còn thấy, nhưng mục 8 đo tỉ lệ thành công lúc sinh còn bảng này đo sai số đặt cuối trên episode đã ghi, nên hai số không so thẳng được. Nguyên nhân trượt chưa phân tích theo từng phase.

**Điều cần biết khi dùng lô này.**

- Lô mẫu ở mục 8 và lô này mang cùng chuỗi `planner_version` (`...y150`) dù mã ARRIVE_B khác nhau: lô mẫu có hai lần chạy, trước và sau khi sửa, còn lô này chỉ chạy sau khi sửa (commit `713dd05a`). Mã commit, không phải chuỗi này, phân biệt hai lô; không trộn thư mục.
- Thẻ trong `cards/` để `null` các trường không có nguồn trong kho, như mục 7.
- `round.yaml` có trong kho nhưng chưa chạy qua `fw agentqa pack`; Agent QA/QC chưa đọc lô này.
- Bộ giữ ≤ 3 cm và ≤ 5° là script dùng một lần (đổi `common.py` của `da48-clean`). Đã kiểm bằng cách tái tạo file giữ của DA-48 (`tray-s1-jig2-20261122`, hai lô cũ nằm trong cùng `keep_3cm_5deg.json`, cùng khóa); chưa có test tự động.
- Cờ `replay_dynamic` và `replay_success` trong `dataset_report.json` cùng kiểu với mục 7; chưa kiểm riêng cho lô này.
- Số giây-worker của QA phát lại và phát lại DA-17 là cận trên (số worker nhân thời gian, không đo thời gian bận từng worker).
- Số đo là sơ bộ trong sim; chưa có kết quả train hay eval nào dùng lô này.
