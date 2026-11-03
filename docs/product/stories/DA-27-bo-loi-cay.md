# DA-27 · Bộ lỗi cấy: cấy lỗi có đáp án

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO duyệt hướng 27/10/2026) |
| Người làm | Hiếu |
| Làn | Dữ liệu |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 9.2 · Epic 9 · 03 ADR-26 |
| Nhãn | [Lõi] · `epic:9` · `gate:G1` · `area:data` |
| Sprint | S2; bộ lỗi dữ liệu xong trước 10/11/2026 để DA-20 chấm kịp demo · **Lịch 3/11/2026:** mở PR và merge trước **6/11/2026** (thay 10/11) |
| Ước lượng | 5 giờ cho nhiệm vụ 6–10 (bản 3/11/2026; bản 27/10: 7 giờ, khoảng 6–8; bộ chấm tách sang DA-31) |
| Phụ thuộc | DA-25 (schema `DefectManifest`, trường `injected_defect`), S1-07 (gói psi-data task hai bàn). Log train và log RTC cấy lỗi dựng trên `FakeTrainer` và log RTC giả của testkit cho tới khi có log thật. Từ 3/11/2026: bộ đọc và ghi LeRobot v2.1 của DA-03 PR 1 (hạn 5/11) cho nhiệm vụ 8 |

## Story

Là kỹ sư dữ liệu, tôi muốn một bộ dữ liệu và log thật được cấy lỗi có đáp án khóa trước, để bộ chấm (DA-31) đo được phép kiểm QA và Agent QA/QC bắt đúng bao nhiêu trước khi đội train model.

## Tiêu chí chấp nhận

1. Bộ cấy chạy trên bản sao của gói psi-data task hai bàn (không sửa bản gốc): mỗi loại lỗi dữ liệu ở design mục 9.2 (rơi khung ảnh; lệch thời gian ảnh và state; nhảy khớp; vượt giới hạn khớp; NaN; sai đơn vị độ và radian; đảo dấu một chiều action; episode hỏng gắn nhãn thành công; sai câu lệnh task; trùng episode; rò hạt giống holdout) có tham số, mỗi loại 3 episode (33 trên 99), quyết định PO 3/11/2026; mỗi episode mang tối đa một lỗi, hạt giống ghi lại.
2. Log train cấy lỗi T1–T8 và log RTC cấy lỗi R1, R2 sinh từ bộ giả, cùng schema với log thật.
3. Đáp án ghi vào `DefectManifest`, hash khóa trước khi chạy QA và agent; agent và phép kiểm không đọc được file này (có test). Bản 3/11/2026: dùng `DefectManifest`, `Defect` của `flywheel.contracts`, không định nghĩa bản ghi riêng; mã lỗi theo design 27/10 mục 10 (D1, D2, D3, D5, D6, D7; log giữ T1–T8, R1–R2), tên lỗi cũ giữ trong `parameters["kind"]`; episode cấy lỗi mang `EpisodeMetadata.injected_defect`.
4. Một bản sạch (không cấy) cùng kích thước để đo báo nhầm.
5. Bản cấy lỗi và bản sạch giao cho DA-31 qua `DatasetRef` và `DefectManifest`; bản cấy lỗi không vào release train (có test). Bản 3/11/2026 (Q5): story này xuất `has_injected_defect(episode) -> bool` trong `flywheel.data.inject.api`; `release` của DA-03 gọi hàm này để chặn; mỗi bên có test riêng.

## Nhiệm vụ

- [ ] 1. Bộ cấy lỗi dữ liệu trên bản sao psi-data (AC 1)
- [x] 2. Log train và log RTC cấy lỗi từ bộ giả (AC 2)
- [ ] 3. `DefectManifest` có hash, chặn agent đọc (AC 3)
- [ ] 4. Bản sạch (AC 4)
- [ ] 5. Giao bản cấy và bản sạch, test chặn release (AC 5)

Bản 3/11/2026 (nhiệm vụ 1–5 là 5 commit của Thông; [plan chia lại việc](../../superpowers/plans/2026-11-03-thong-reassignment.md) session 2):

- [x] 6. Thay bản ghi manifest riêng bằng `DefectManifest`, `Defect` của hợp đồng; episode cấy lỗi mang `EpisodeMetadata.injected_defect` (AC 3)
- [x] 7. Đổi mã lỗi theo design mục 10: NaN → D1; rơi khung, lệch đồng bộ → D2; nhảy khớp, vượt giới hạn, sai đơn vị → D3; trùng episode, rò hạt giống → D5; nhãn thành công sai, câu lệnh sai → D6; đảo dấu một chiều action → D7 (AC 1, 3)
- [ ] 8. Cấy lên bản sao parquet thật bằng bộ đọc và ghi của DA-03 PR 1, mỗi loại 3 episode (33 trên 99), hạt giống ghi trong manifest (AC 1)
- [ ] 9. Bản sạch cùng số episode; `seal_manifest` ghi `defect_manifest.json` và `.sha256`; test agent không đọc được manifest (AC 3, 4)
- [ ] 10. `has_injected_defect` và test; chạy trên `rtx3060` ra `fwdata/inject/<dataset_id>/{injected,clean}`, gửi `DatasetRef` và đường dẫn manifest cho Châu (DA-31) (AC 5)

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa.

- `packages/flywheel-data/src/flywheel/data/inject/`, `packages/flywheel-data/tests/unit/inject/`
- `configs/data/inject.yaml`
- `docs/g0/defect-inject.md`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 9.2, 10 (mã lỗi D, T, R); spec mục 7.6 (lỗi cấy cho HD dùng cùng ý tưởng); 03 mục 7.3 (artifact), ADR-26.
- Phần chấm là DA-31 (Châu từ 3/11/2026, làn Đánh giá); hai phần chỉ nối qua `DefectManifest` trong `flywheel.contracts`, không import nhau.
- Bản sao cấy lỗi không bao giờ vào release train (có test chặn theo `injected_defect`).
- Dữ liệu cấy lỗi để trong `fwdata/`, không commit; chỉ commit cấu hình và mã.
- Từ 3/11/2026: nhiệm vụ 1–5 là 5 commit của Thông trên nhánh `DA-27-bo-loi-cay` (`6b4e327`), cherry-pick lên nhánh mới và giữ tác giả Thông. Giao diện xuất ở `flywheel.data.inject.api`: `inject_copy`, `clean_copy`, `seal_manifest`, `has_injected_defect` ([plan chia lại việc](../../superpowers/plans/2026-11-03-thong-reassignment.md) session 2).

## Kiểm thử

- Mỗi loại lỗi có một test: cấy một lần, phép kiểm tương ứng bắt được.
- Test chặn: release từ chối episode có `injected_defect`.

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude (từ 3/11/2026); nhiệm vụ 1–5: Dương Tiến Thông
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 27/10/2026 | Tạo story theo design 27/10/2026 mục 9.2 | PO (Hiếu) |
| 27/10/2026 | Tách bộ chấm sang DA-31; giao cho Thông theo 07 mục 2.0 (bản 0.6) | PO (Hiếu) |
| 3/11/2026 | Hạn mới theo lịch hoàn thiện 13/11/2026 (07 mục 2.4) | PO (Hiếu) |
| 3/11/2026 | Người làm Thông → Hiếu theo quyết định PO (07 bản 1.6; [plan chia lại việc](../../superpowers/plans/2026-11-03-thong-reassignment.md) Q1, Q4, Q5): giữ 5 commit của Thông làm nhiệm vụ 1–5; thêm nhiệm vụ 6–10 (hợp đồng, mã lỗi D/T/R, parquet thật, niêm phong, `has_injected_defect`); AC 3, AC 5 ghi rõ theo Q5; bộ chấm DA-31 của Châu | PO (Hiếu) |
| 3/11/2026 | AC 1: tỉ lệ cấy đổi từ khoảng 5–10% số episode sang mỗi loại 3 episode (33 trên 99), mỗi episode tối đa một lỗi; NaN giữ mã D1 theo design mục 9.2 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực: 6.5h
- Công cụ AI đã dùng: Antigravity
- Ghi chú hoàn thành: Đã cấy 11 loại lỗi dữ liệu, log train T1-T8, log RTC R1-R2, khóa DefectManifest và rào chắn release. 29/29 tests passed.
- File đã tạo hoặc sửa: packages/flywheel-data/src/flywheel/data/inject/, packages/flywheel-data/tests/unit/inject/, configs/data/inject.yaml, docs/g0/defect-inject.md
- 3/11/2026 (Hiếu và Claude, nhánh `DA-27-defect-inject`): bỏ dấu xong của nhiệm vụ 1, 3, 4, 5. Mã của Thông chỉ cấy trên `EpisodeData` trong bộ nhớ, chưa trên bản sao parquet của psi-data (AC 1); manifest chưa dùng `DefectManifest` của hợp đồng (AC 3); bản sạch sinh từ bản đã cấy nên vẫn mang lỗi (AC 4); chưa giao cho DA-31 (AC 5). Nhiệm vụ 1, 4, 5 chờ bộ đọc LeRobot (DA-03 PR 1) và `pyarrow`.
- 3/11/2026: mã lỗi theo design mục 9.2 và 10 (sửa 3/11): `Defect.code` là D1, D2, D3, D5, D6, D7 cho dữ liệu và T1–T8, R1–R2 cho log; tên loại giữ trong `parameters["kind"]`. Nhiệm vụ 2 giữ dấu xong.
- 3/11/2026 (`DA-27/8.2`): manifest chỉ ghi lỗi đã cấy thật. Lỗi trên action theo chiều của design 9.2 (`unit_deg_rad` chiều góc 0–30, 35 khác 0; `joint_jump`, `joint_limit_exceeded` chiều khớp 0–30; `action_sign_flip` một chiều có độ lệch chuẩn khác 0); episode không cấy được thì chọn episode khác; mỗi dòng manifest được kiểm đã đổi dữ liệu. Nhiệm vụ 8 còn mở tới khi cấy trên parquet thật.
- 3/11/2026 (`DA-27/9.1`): bản cấy và bản sạch mang id trung tính cùng dạng `bench-<12 hex>`, không lộ vai trò; bản sạch chép từ bản gốc và có `DefectManifest` với `defects` rỗng, nên chỉ bộ chấm biết bản nào sạch. Nhiệm vụ 9 còn mở (niêm phong, test agent không đọc manifest).
- 3/11/2026 (`DA-27/8.3`): `create_defect_dataset(..., layout=ActionLayout)`; `joint_limit_exceeded` vượt `limit_high` của chiều được chọn, lỗi trên action bỏ qua chiều bị mask.
- 4/11/2026 (`DA-27/8.3`, tiếp): test trên `configs/embodiments/g1.yaml` thật: mọi dòng manifest đã cấy; `joint_limit_exceeded` chỉ chọn chiều 0–30 và vượt `limit_high` của chiều đó; `unit_deg_rad`, `action_sign_flip` chỉ đổi đúng một chiều design 9.2 cho phép.
- 3/11/2026 (`DA-27/9.2`): `seal_manifest` ghi `defect_manifest.json` và `.sha256`, từ chối ghi vào thư mục bản sao; test quét mã chặn agent (`flywheel.eval.agentqa` trừ `bench/`) và phép kiểm (`flywheel.data` trừ `inject/`) nhắc tới đáp án; bỏ `ManifestLock.can_agent_read` (chỉ so tên vai). Nhiệm vụ 9 còn mở tới khi bản sạch và niêm phong chạy trên parquet thật.
- 3/11/2026 (`DA-27/10.1`): `flywheel.data.inject.api.has_injected_defect(episode: Episode) -> bool` cho `release` của DA-03, có test; theo hợp đồng hiện tại xét `meta.injected_defect`, đổi sang `benchmark_copy_id` khi #36 merge. Nhiệm vụ 10 còn mở (chạy trên `rtx3060`, giao DA-31).
- 3/11/2026 (issue #62, sau khi #36 merge): episode không còn mang `injected_defect`; mọi episode của hai bản sao chấm mang `benchmark_copy_id` bằng `dataset_id` trung tính của bản sao; đáp án chỉ trong `DefectManifest`; rào release và `has_injected_defect` chặn theo `benchmark_copy_id` (design 6.1, 9.2; 03 bản 1.0 mục 4.3). Nhiệm vụ 6 làm lại theo hợp đồng mới ở `DA-27/6.1`.
