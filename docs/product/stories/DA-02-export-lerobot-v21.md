# DA-02 · Checklist export LeRobot v2.1 cho Ψ₀

## Trạng thái

| Trường | Giá trị |
|---|---|
| Trạng thái | Sẵn sàng (PO chốt phạm vi 3/11/2026, [plan chia lại việc](../../superpowers/plans/2026-11-03-thong-reassignment.md) Q2) |
| Người làm | Hiếu |
| Làn | Dữ liệu |
| Story PRD | Story của [design 27/10/2026](../../superpowers/specs/2026-10-27-g1-psi0-demo-design.md) mục 6.4 · Epic 9 |
| Nhãn | [Lõi] · `epic:9` · `gate:G1` · `area:data` |
| Sprint | S2 · **Lịch 3/11/2026:** merge trước **9/11/2026** |
| Ước lượng | 3,5 giờ (ước lượng 3/11/2026; bản 07 0.6: 10 giờ gồm cả bộ export) |
| Phụ thuộc | DA-03 PR 1 (bộ đọc LeRobot v2.1, hạn 5/11), DA-01 (`ActionLayout` của G1; trong lúc chờ dùng `meta/action_layout.json` của export khay), DA-33 (bộ export Ψ₀ và release khay S1). Chặn DA-21 (checklist v3 mở rộng từ checklist này) |

## Story

Là kỹ sư dữ liệu, tôi muốn mọi dataset LeRobot v2.1 đưa vào fine-tune Ψ₀ được kiểm tự động theo checklist chuẩn hóa, để không tốn giờ GPU cho dataset sai layout, sai stats hay loader Ψ₀ đọc lệch.

## Tiêu chí chấp nhận

_Phạm vi 3/11/2026 (Q2): bộ export đã có trong adapter (`flywheel-simple/tray/export.py` của DA-33, ra đúng layout của psi-data qua `postprocess_psi0_sonic.py` của SIMPLE, kèm `meta/action_layout.json`, `stats_psi0.json`). Story này chỉ làm checklist phía làn và contract test bằng loader Ψ₀; không viết bộ export thứ hai._

1. `check_lerobot_v21(root, layout)` trong làn chạy điểm 1–6 của checklist design mục 6.4 và trả danh sách `QACheck`: (1) `meta/info.json` có `codebase_version`, `fps`, `robot_type`, `features` khớp shape và tên từng chiều với `action_layout`; (2) `episode_index`, `index` liên tục, `frame_index` bắt đầu từ 0 mỗi episode; (3) `timestamp` khớp `frame_index / fps` trong dung sai nửa chu kỳ; (4) số khung video theo meta khớp số dòng, codec và độ phân giải đúng khai báo; (5) `tasks` có câu lệnh cho mọi episode; (6) stats tính trên đúng release, không NaN, chiều đã mask không bị báo lỗi stats.
2. Điểm 7 trong `flywheel-psi0`: contract test đọc lại một batch bằng loader Ψ₀ ở `cda3fdf`, so từng giá trị với batch mẫu đã lưu; chạy trong venv Ψ₀, không chạy trong CI của làn.
3. Chạy checklist trên release khay S1 và trên psi-data task hai bàn; output ghi vào `docs/g0/export-v21.md`.

## Nhiệm vụ

- [x] 1. Điểm 1–6 của checklist trong làn (AC 1)
- [x] 2. Điểm 7: contract test bằng loader Ψ₀ (AC 2)
- [x] 3. Chạy trên release khay S1 và psi-data, ghi kết quả (AC 3)

## Giao diện

Theo plan chia lại việc mục 5, session 5. Xuất qua module riêng; không sửa `api.py`, `cli.py` của `flywheel-data` (chỉ DA-03 sửa).

```python
# flywheel/data/export/checklist.py
def check_lerobot_v21(root: Path, layout: ActionLayout) -> list[QACheck]: ...  # points 1-6 of design 6.4
```

## Phạm vi file

Theo 07 mục 3.1. pr-guard chặn PR sửa file ngoài danh sách này; file story luôn được sửa. `export/egodex.py` của Hưng không thuộc story này.

- `packages/flywheel-data/src/flywheel/data/export/checklist.py`
- `packages/flywheel-data/tests/unit/export/`
- `packages/flywheel-psi0/tests/contract/test_loader_roundtrip.py`
- `docs/g0/export-v21.md`

## Ghi chú cho người làm

- Nguồn: design 27/10 mục 6.4; 03 ADR-03, mục 7.3; plan chia lại việc mục 5 (session 5), 7.
- Làn chỉ import nhân (`flywheel.contracts`, `flywheel.store`, `flywheel.testkit`); đọc parquet và json bằng `pyarrow`, `json`, không import `lerobot`, `psi0` hay adapter (03 mục 7.3). Điểm 4 đọc số khung từ meta, không giải mã video trong làn.
- Đọc dataset bằng bộ đọc `read_info`, `iter_episodes` của DA-03 PR 1.
- Loader Ψ₀: fork lerobot `songlin/lerobot@09929d8`, `CODEBASE_VERSION = "v2.1"`; code Ψ₀ ở `cda3fdf`. Batch mẫu lưu ngoài git nếu lớn; test ghi hash của batch.
- Tình huống cần test (plan mục 7): chiều action bị mask có độ lệch chuẩn 0 không bị báo lỗi stats.

## Kiểm thử

- Checklist bắt được dataset mẫu cố ý sai, sinh trong test: `features` sai chiều, `frame_index` không bắt đầu từ 0, timestamp lệch, thiếu `tasks`, stats có NaN.
- Dataset đúng (sinh trong test theo layout của export khay) qua đủ 6 điểm.

## Người phụ trách

- Làm: Dương Đình Hiếu, cùng Claude (từ 3/11/2026; trước đó Dương Tiến Thông, chưa có commit)
- Duyệt và merge: Dương Đình Hiếu (người duy nhất, 07 mục 3.4)
- Bình luận: Long (`ActionLayout`, DA-01)

## Change log

| Ngày | Nội dung | Người |
|---|---|---|
| 3/11/2026 | Tạo file story theo 07 bản 1.6 và plan chia lại việc (Q2): checklist v2.1 điểm 1–6 phía làn, điểm 7 bằng loader Ψ₀; bộ export dùng lại của DA-33 | PO (Hiếu) |

## Ghi chép khi làm

- Giờ thực: 6 giờ (nhiệm vụ 1: 3,5; 2: 1,5; 3: 1)
- Công cụ AI đã dùng: Claude Code (Opus 5.5)
- Ghi chú hoàn thành: hai dataset qua điểm 7. Ở điểm 1–6, cả hai trượt `index` (Q7 của DA-03); lỗi này không làm sai batch Ψ₀. Điểm 6 theo phương án A của PO (4/11/2026): chiều hằng số không mask, không khai `constant` thì trượt. PR #89 đã merge: checklist đọc trường `constant`; psi-data qua, khay S1 trượt ở 5 chiều `[0, 7, 28, 29, 30]`, chờ DA-33 trả lời. Còn chờ PO: siết điểm 3 xuống 1e-4 s. Chi tiết ở [export-v21.md](../../g0/export-v21.md).
- PR: #91 (nhánh `DA-02-export-checklist`, rebase lên master `7d73f1e`)
- File đã tạo hoặc sửa: `packages/flywheel-data/src/flywheel/data/export/checklist.py`, `packages/flywheel-data/tests/unit/export/{checklist_data.py,test_export_checklist.py}`, `packages/flywheel-psi0/tests/contract/test_loader_roundtrip.py`, `docs/g0/export-v21.md`, file story này
