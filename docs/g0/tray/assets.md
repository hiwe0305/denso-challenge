# Asset hiển thị của task bê khay (DA-32)

Ngày 30/10/2026. Cảnh task bê khay vẽ bằng mesh lấy từ [nvidia/simready-assets](https://huggingface.co/datasets/nvidia/simready-assets) **[Đã chốt 30/10/2026, Hiếu]**. Mesh chỉ để render. Va chạm, khối lượng và ma sát vẫn là hộp dựng từ [configs/sim/tray.yaml](../../../configs/sim/tray.yaml), xem [decisions.md](decisions.md) mục D-01.

## Nguồn và giấy phép

| Trường | Giá trị |
|---|---|
| Dataset | `nvidia/simready-assets` trên Hugging Face |
| Revision ghim | `4763fbfaa4f8e97658e68b57d01b4c86659e08b5` (nhánh `main` ngày 29/10/2026) |
| Giấy phép | CC-BY-4.0 cho từng asset (`com.nvidia.simready.packaging.json`) |
| Bản quyền | NVIDIA Corporation |
| Cách lấy | `scripts/g0/tray/import_simready.py`; kiểm sha256 từng file theo bản ghi LFS của Hugging Face |
| Chỗ để | `fwdata/simple/tray/simready/` (không commit) |
| Phân loại dữ liệu | `public` |

## Asset đã dùng và phần đã sửa

CC-BY-4.0 cho phép sửa, với điều kiện ghi nguồn và nói rõ đã sửa gì.

| Vai trong cảnh | Asset | Kích thước gốc (m) | Đã sửa |
|---|---|---|---|
| Khay | `crate_green_a20` | 0,612 × 0,412 × 0,090 | Xoay 90° quanh z; co giãn không đều cho khít hộp khay 0,30 × 0,45 × 0,06 m; texture albedo thu về 512 px; bỏ normal và ORM |
| Bàn A, B | `table_metal_stainless_a03` | 1,800 × 0,699 × 0,850 | Xoay 90°; co giãn về 0,8 × 1,2 × 0,85 m; chỉ dùng texture thép (chân nhựa đen cũng mang texture thép) |
| Linh kiện 0, 2, 4 | `factory_nut_m20_loose` | 0,030 × 0,035 × 0,016 | Giữ tỉ lệ, đặt vào hộp linh kiện 0,035 × 0,035 × 0,03 m; khối lượng lấy từ config (asset khai sai, đai ốc M16 chỉ 3,6 g) |
| Linh kiện 1, 3, 5 | `consumable_bearing_ball_a01` | 0,038 × 0,038 × 0,008 | Như trên |

Ghi nguồn khi dùng ảnh, video hay dữ liệu có cảnh này: "Scene meshes from NVIDIA SimReady Assets (nvidia/simready-assets), CC-BY-4.0, scaled and re-textured."

## Lệnh

```bash
uv run --no-project --with usd-core --with pillow --with numpy \
    python scripts/g0/tray/import_simready.py --out fwdata/simple/tray/simready
```

Mất khoảng 15 giây. Script ghi khoảng 17 MB và một file `manifest.json` mà `flywheel_simple.tray.visuals` đọc. Không có manifest thì cảnh vẫn chạy, các hộp hiện bằng màu trơn.
