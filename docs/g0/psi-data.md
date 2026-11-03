# Phân tích gói psi-data (Q1, V1, V6, V9)

_Ngày 3/11/2026. Story [S1-07](../product/stories/S1-07-phan-tich-psi-data.md), cổng G0. Làm lại từ PR #24 của Thông (nhánh `S1-07-psi-data` @ `e96da77`): giữ cách đọc cấu trúc gói, bỏ mọi số gán cứng. Mọi số trong file này do [`scripts/g0/inspect_psi_data.py`](../../scripts/g0/inspect_psi_data.py) in ra, chạy trên máy `rtx3060`; bảng trong file là output của lệnh, chép nguyên. Số nào script không đo được thì ghi là giả định hoặc "không suy được"._

## 1. Tải và sha256 (AC 1)

Revision ghim: `USC-PSI-Lab/psi-data` @ `e78fb93cc28912a3031a10b8656d32d7f0a2b867` (commit ngày 14/09/2026). Script lấy kích thước và `lfs.oid` của từng file từ API cây thư mục của Hugging Face ở đúng revision này, tải file qua `resolve/<sha>/<đường dẫn>`, băm sha256 trong lúc tải rồi so với `lfs.oid`. Dữ liệu nằm ngoài git, ở `rtx3060:~/denso-s107/fwdata/psi-data/e78fb93/<đường dẫn trên HF>`; script ghi kết quả vào `fetch.json` cạnh đó.

```bash
python3 -I scripts/g0/inspect_psi_data.py fetch --revision e78fb93 --out fwdata/psi-data/e78fb93 \
    simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip \
    simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip \
    simple/G1WholebodyBendPickTeleop-v0.zip simple/G1WholebodyBendPickMP-v0.zip \
    simple-eval/G1WholebodyBendPickTeleop-v0.zip simple-eval/G1WholebodyBendPickMP-v0.zip
```

| Đường dẫn trên HF | Kích thước (B) | sha256 | Khớp `lfs.oid` của HF |
|---|---|---|---|
| `simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | 202,607,109 | `6cdf9022c23649f68d2faf418a97c47c01aca9d1fac27e9af366116d69927586` | có |
| `simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | 480,532 | `8a4b0ff7d068967dac8baec2c4a4deca4f644215a1ee15e921739f3dfe90e7e0` | có |
| `simple/G1WholebodyBendPickTeleop-v0.zip` | 41,839,721 | `f14802cd95a387f70df2d7601d2f7b804570e431377980acfffee9e6160dce3c` | có |
| `simple/G1WholebodyBendPickMP-v0.zip` | 43,314,543 | `8f1df4dc44c27526029d02d2883343a5cb0f98e9cb84d214e7fef57c331cad6a` | có |
| `simple-eval/G1WholebodyBendPickTeleop-v0.zip` | 382,543 | `b532ece10d05ef22c549006f936599fc0954e4eaac7c5d16cec3bc30e294f548` | có |
| `simple-eval/G1WholebodyBendPickMP-v0.zip` | 1,630,050 | `6bcdb9ddfa1d3f851144f585bda19507ad9efb53e71514dad98836fcefadc5e2` | có |

Sáu file, tổng 290.269.326 B trên đĩa. Tải và băm mất 16 s, RSS đỉnh 23 MB.

Ghi chú:

- HF có hai gói hai bàn. Gói dùng ở đây là `simple/…` (đúng gói của S1-07 và của Ψ₀). Gói `simple-teleop/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` (222.159.491 B, `lfs.oid` `cbe6dddc…`) không dùng.
- Bản cũ đã có trên máy, băm bằng `inspect_psi_data.py hash`:

  | File | Kích thước (B) | sha256 | So với `e78fb93` |
  |---|---|---|---|
  | laptop `fwdata/psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | 202,607,109 | `6cdf9022…927586` | trùng |
  | `rtx3060:~/denso-s103/fwdata/simple-eval/G1WholebodyLocomotionPickBetweenTablesTeleop-v0.zip` | 689,559 | `7d215cf3…c28dee` | **khác**: đây là bản ở `main` hiện tại (`de140d67…`, API trả 689.559 B), không phải bản ở `e78fb93` |

  Tập eval S1-03 đang dùng trên `rtx3060` là bản mới hơn revision ghim. Mục 4 so hai bản.
- `rtx3060:~/denso-da33/fwdata/psi-data/simple/G1WholebodyLocomotionPickBetweenTablesTeleop-v0/` chỉ có `meta/info.json`, không phải gói đầy đủ.
