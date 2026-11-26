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
