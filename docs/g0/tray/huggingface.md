# Release S1 khay trên Hugging Face

Ngày 5/11/2026. Release synthetic S1 planner-5 `tray_s1_f9433b028c52` của task bê khay được đưa lên Hugging Face ở [`hiwe0305/denso-hackrathon-g1-pick-and-place`](https://huggingface.co/datasets/hiwe0305/denso-hackrathon-g1-pick-and-place). Hiếu chọn repo và giao Claude chốt giấy phép (D-30 trong [decisions.md](decisions.md)).

## Nội dung

| Trường | Giá trị |
|---|---|
| Release | `tray_s1_f9433b028c52`, `release_hash` `f9433b028c520b4fd78b34469b389862f7b34de0bb185840aa18143d2d5d8461` |
| Nguồn | `rtx3060:~/denso-da34-pool/fwdata/releases/tray_s1_f9433b028c52/`, đưa lên nguyên byte (hardlink vào `~/hf-stage-g1/`, không sửa file nào của release) |
| Thêm ở gốc repo | `README.md` (dataset card) và `NOTICE.md` (giấy phép và thông báo của bên thứ ba); hai file này không nằm trong `release_manifest.json` |
| Định dạng | LeRobot v2.1 như Ψ₀ đọc; chưa chuyển sang v3.0 (DA-21, sau 13/11/2026) |
| Episode | 541, gồm cả 7 episode bị QA của DA-03 loại (seed 1072, 1097, 1153, 1166, 1358, 1372, 1431); card ghi danh sách để người dùng tự bỏ |
| Seed | 1000–1609, đều thuộc dải train của `configs/splits/default.yaml`; không có seed dev hay holdout |
| Chế độ | Public. Repo đã có sẵn, public và trống (chỉ `.gitattributes`, commit `17a3d1f` lúc 13:51Z) khi Claude kiểm trước lúc đưa lên |

Không đưa lên: psi-data và mọi bản suy ra từ nó (giấy phép `unknown`, cảnh HSSD CC-BY-NC-4.0, vật GraspNet CC BY-NC-SA 4.0, [psi-data.md](../psi-data.md) mục 5), bản sao lỗi cấy và `DefectManifest`, mẫu EgoDex (CC-BY-NC-ND), video egocentric tự quay, checkpoint. Release S1 cũ `tray_s1_0d84cc87b1e5` (planner-4, có cờ `action_jump.arm`, D-28) cũng không đưa lên.

## Giấy phép [Đã chốt 5/11/2026, Hiếu giao Claude chốt]

Dataset phát hành theo **CC BY 4.0**. Các thành phần tạo ra hay xuất hiện trong dữ liệu, kiểm tại nguồn ngày 5/11/2026:

| Thành phần | Nguồn | Giấy phép | Ràng buộc |
|---|---|---|---|
| Mesh khay, bàn, linh kiện | `nvidia/simready-assets` @ `4763fbf` ([assets.md](assets.md)) | CC BY 4.0 | Ghi nguồn, nói rõ đã co giãn và đổi texture |
| Mô hình G1 `g1_29dof_with_hand` | `unitreerobotics/unitree_ros`, `robots/g1_description` (bản SIMPLE mang theo không kèm file giấy phép) | BSD 3-Clause, © 2016–2022 Unitree Robotics | Giữ thông báo bản quyền; `NOTICE.md` chép nguyên văn |
| Simulator | SIMPLE | MIT | Giữ thông báo bản quyền |
| Bộ điều khiển | NVIDIA GR00T-WholeBodyControl | Mã Apache 2.0, trọng số NVIDIA Open Model License | Dataset chỉ chứa đầu ra (state, action), không chứa mã hay trọng số |

CC BY 4.0 khớp với ràng buộc chặt nhất (SimReady CC BY 4.0) và không thêm điều kiện phi thương mại. `release_manifest.json` đóng băng trước khi chọn giấy phép nên vẫn ghi `combined_license: unknown`; card ghi rõ điều này thay vì sửa manifest, vì sửa thì đổi `release_hash` mà RunPlan `rp_301f08e73358` đang ghim.

## Cách đưa lên

Chạy trên `rtx3060` bằng token Hugging Face có sẵn của tài khoản `hiwe0305`:

```bash
uvx --from "huggingface_hub[hf_xet]==0.36.0" hf upload-large-folder \
    hiwe0305/denso-hackrathon-g1-pick-and-place ~/hf-stage-g1 --repo-type dataset --num-workers 4
```

`upload-large-folder` ghi trạng thái để chạy tiếp vào `~/hf-stage-g1/.cache/`, nên thư mục release không bị đụng. Chạy lại cùng lệnh là tiếp tục. Sổ chi phí: `job_hf_tray_s1` trong [`ledger/DA-34.csv`](../ledger/DA-34.csv).
