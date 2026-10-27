# DA-26 · Thí nghiệm HE: prior egocentric và số demo robot

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt hướng 27/10/2026) |
| Người làm | Chờ PO giao |
| Làn | Model và phần cứng (chạy job GPU); kết quả đi qua làn Đánh giá |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 7 · spec mục 3 (HE), 7.9 |
| Nhãn | [Adapter] · `epic:9` · `gate:G2` · `area:rl` |
| Sprint | S1–S3. HE-1 sơ bộ (V-EGO và V-NOEGO ở N = 20 và N = 80) trước 13/11/2026 cho demo; HE-1 đủ lưới trong S3; HE-2 sau demo |
| Ước lượng | 20 giờ người (khoảng 15–25, ước lượng); GPU-giờ theo S1-04 |
| Phụ thuộc | S1-03 (mốc so trên task hai bàn, Q0 của checkpoint ablation), S1-04 (giờ fine-tune và eval), S1-07 (N_teleop, danh sách demo), DA-19 (adapter fine-tune trên Colab). HE-2 cần DA-03, DA-16, S1-05 |

## Story

Là trưởng nhóm, tôi muốn đo Ψ₀ có và không có prior egocentric ở nhiều mức demo robot trên task hai bàn, để chứng minh hoặc bác bỏ bằng số đo của đội rằng dữ liệu egocentric giúp cần ít demo robot hơn.

## Tiêu chí chấp nhận

1. RunPlan `configs/runplans/he/he-1.yaml` chốt trước khi chạy: ba biến thể (V-EGO, V-NOEGO, V-EGO10 tùy chọn) với revision checkpoint; lưới N ∈ {10, 20, 40, 80} (điểm cuối là N_teleop nếu < 80); danh sách demo lồng nhau có hash; recipe fine-tune của tác giả (số bước, batch, learning rate) giống nhau mọi điểm; seed; 30 điều kiện dev × 3 mức có hạt giống; renderer theo kết luận S1-03 AC 10; tiêu chí HE của spec mục 3. Hiếu ký `Decision` `plan_review`.
2. Mỗi điểm (biến thể, N, seed) có: checkpoint, `metrics.jsonl`, thành công theo cờ của SIMPLE theo mức, video, mục sổ chi phí (GPU-giờ fine-tune và eval, `estimated` và `measured` tách riêng).
3. Mốc so: checkpoint task hai bàn của tác giả eval trên cùng 90 điều kiện (lấy từ S1-03 nếu cùng điều kiện).
4. Báo cáo `docs/he/he-1.md`: bảng kiểu paper (thành công trên số lượt, theo mức) và đường cong theo N cho từng biến thể; chênh lệch V-EGO − V-NOEGO có CI 95% bootstrap theo điều kiện (và theo seed ở N = 20, 40); N₅₀; kết luận theo tiêu chí đã chốt, kể cả khi âm; giới hạn ở design mục 7.2.
5. Video so sánh ba cột (V-EGO, V-NOEGO, checkpoint của tác giả) cùng điều kiện, hai mức N, render Isaac; để ngoài git, đường dẫn ghi trong báo cáo.
6. Kết quả sơ bộ cho demo: ít nhất V-EGO và V-NOEGO ở N = 20 và N = 80, 1 seed, trước 13/11/2026; ghi rõ "sơ bộ".
7. HE-2 (sau demo): lặp AC 1–4 trên dataset tự xây (bàn phím cộng sinh tự động qua pipeline), RunPlan `he-2.yaml`.
8. Rút gọn (design mục 7.4) nếu S1-04 cho thấy vượt ngân sách: mỗi rút gọn là một `Decision` ghi trong báo cáo.

## Nhiệm vụ

- [ ] 1. RunPlan HE-1, danh sách demo lồng nhau, Hiếu ký (AC 1)
- [ ] 2. Tải và kiểm sáu checkpoint ablation chạy được với `finetune-simple-psi0.sh` (AC 1)
- [ ] 3. Fine-tune và eval điểm sơ bộ V-EGO, V-NOEGO ở N = 20, 80 (AC 2, 6)
- [ ] 4. Eval mốc so (AC 3)
- [ ] 5. Fine-tune và eval phần còn lại của lưới, seed thứ hai (AC 2)
- [ ] 6. Báo cáo HE-1 và video (AC 4, 5)
- [ ] 7. HE-2 trên dataset tự xây (AC 7)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `configs/runplans/he/`
- `scripts/he/`
- `docs/he/`
- `docs/g0/ledger/DA-26.csv`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 7; spec mục 3 (HE), 7.1 (E1 dùng chung lưới), 7.5 (bootstrap), 7.9; 03 mục 8.1 (RunPlan).
- Checkpoint (thư mục `psi0/` của `USC-PSI-Lab/psi-model`): V-EGO `pre.fast.1by1.2601091803.ckpt.ego200k.he30k` + `postpre.1by1.pad36.2601131206.ckpt.he30k`; V-EGO10 `pre.abl.ego.10per.2602021632.46k` + `postpre.abl.ego.10per.2602050006`; V-NOEGO `pre.abl.only.he.2512311516.48k` + `postpre.abl.only.he.2602050012`.
- Lần fine-tune V-EGO ở mỗi N dùng chung với E1 của spec mục 7.1; không chạy hai lần.
- Không xem kết quả từng điểm rồi đổi lưới hay tiêu chí; đổi gì cũng là `Decision` có lý do, ghi trước khi chạy phần còn lại.
- Trọng số không commit; để trong `fwdata/` hoặc kho bền của Colab.

## Kiểm thử

- Chạy lại một điểm (biến thể, N, seed) từ RunPlan cho cùng danh sách demo (hash) và thành công lệch trong khoảng không tất định đo ở S1-03 AC 5.
- Bộ tính CI có test trên dữ liệu giả với đáp án biết trước.

## Người phụ trách

- Làm: chờ PO giao (job GPU chạy trên máy và Colab của Hiếu)
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 27/10/2026 | Tạo story theo design 27/10/2026 mục 7 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực:
- Công cụ AI đã dùng:
- Ghi chú hoàn thành:
- File đã tạo hoặc sửa:
