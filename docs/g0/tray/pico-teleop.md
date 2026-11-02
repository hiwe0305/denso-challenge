# Teleop PICO trên task bê khay (DA-35 nhiệm vụ 1)

Đọc mã SIMPLE ở commit `6d10628` (bản trong `fwdata/simple/SIMPLE`) và dựng env khay một lần trên rtx3060, 3/11/2026. Story: [DA-35](../../product/stories/DA-35-synthetic-s2-khay-pico.md).

## Kết luận

Đường teleop PICO của SIMPLE cắm được vào env khay mà không fork SIMPLE: `flywheel_simple.tray.run teleop-decoupled-wbc` (DA-32/4) đăng ký env rồi giao cho CLI của SIMPLE. Chưa chạy được ngay vì ba thứ: (1) venv SIMPLE thiếu PyAV và `xrobotoolkit_sdk`, máy sim chưa cài XRoboToolkit PC service; (2) chưa có kính PICO; (3) recorder của SIMPLE không ghi trạng thái khay và không chọn được seed, cần một wrapper nhỏ của đội (nhiệm vụ 2).

Đường decoupled WBC của SIMPLE điều khiển cả eo (`enable_waist = True` trong cấu hình sonic, đo được): IK tính eo từ tư thế hai tay rồi đưa cho policy thân dưới. Vì thế demo PICO có nghiêng eo như video teleop G1, điều planner S1 của DA-33 không có (eo khóa, D-12 trên nhánh DA-33).

## Lệnh dự kiến

```bash
MUJOCO_GL=egl PYTHONPATH=packages/flywheel-simple/src fwdata/simple/.venv/bin/python \
    -m flywheel_simple.tray.run teleop-decoupled-wbc simple/G1WholebodyTrayTransferTeleop-v0 \
    --sim-mode=mujoco --headless --record --max-episode-steps=4500 --dr-level=0
```

Người thu nhìn qua kính (luồng ảnh camera đầu của robot), nên máy sim chạy `--headless` được.

## Chỗ cắm

| Chỗ | Mã SIMPLE | Trên env khay |
|---|---|---|
| Env id | `teleop_decoupled_wbc.py` gọi `gym.make(env_id, …)`; `simple.envs` không biết env khay | `flywheel_simple.tray.run` gọi `register()` trước (đã có) |
| Tham số env | `target`, `dr_level`, `success_criteria`, `max_episode_steps` | Đo: `gym.make` với đúng bộ tham số này dựng `TrayTransferEnv`, reset 9,3 s, ảnh đầu 360 × 640 |
| Tay | `PicoStreamer` → `TeleopPolicy` → `TeleopRetargetingIK` (nhóm `upper_body`, gồm eo khi `enable_waist`) → `G1DecoupledWholeBodyPolicy` | Không đổi |
| Đi | Cần trái: `vx`, `vy` tới 0,5 m/s; cần phải: quay tới 1 rad/s, tích phân thành yaw đích; X/Y hạ nâng thân | Không đổi; người thu đứng tại chỗ |
| Bàn tay | Cò và nút grip chọn 3 mức đóng rời rạc (ngón trỏ, giữa, áp út) qua IK bàn tay Dex3 | Không có độ đóng liên tục; đủ cho tay cầm khay hay không thì thử ở nhiệm vụ 3 |
| Tracker cổ chân | `PicoStreamer` đọc `motion_tracker_data` nhưng đường decoupled không dùng; chỉ SONIC dùng | Theo mã, chỉ cần kính và 2 tay cầm. Tài liệu SIMPLE vẫn liệt kê 2 tracker; kiểm lại khi có kính |
| Bắt đầu, kết thúc | Ghi khi robot đứng vững và người bấm kích hoạt (menu trái + cò phải); hết episode khi `terminated` (`check_success`) hoặc hết bước; giữ hai grip để reset và bỏ episode | `check_success` của DA-32 dùng được nguyên |
| Ghi | `Gr00tDataExporter` (LeRobot, 50 fps): ảnh đầu, `observation.state`, `action` 43 khớp, `action.eef` 14 (hai cổ tay, vị trí và quaternion wxyz), `teleop.navigate_command`, tư thế và vận tốc đế; `environment_config` = `task.state_dict()` | `state_dict` của task khay có level, seed, tư thế khay, vùng đích |
| Phát lại | `replay_decoupled_wbc` đọc `action` khớp và `navigate_command`, chạy lại vật lý | Dùng cho QA; S2 dùng streamer riêng (story mục "Kế hoạch generator") |

## Khoảng trống

| # | Khoảng trống | Bằng chứng | Cách xử lý [Đề xuất] |
|---|---|---|---|
| 1 | Thiếu PyAV: import CLI hỏng | `ModuleNotFoundError: No module named 'av'` từ `simple.teleop.pico.tcp_video_sender` trên rtx3060 | Cài PyAV vào venv SIMPLE; sửa `setup_simple.sh` qua PR `chore-` (thuộc S1-02) |
| 2 | Thiếu `xrobotoolkit_sdk` và XRoboToolkit PC service | Import hỏng; `/opt/apps/roboticsservice` không có (`PicoStreamer` chạy `runService.sh` ở đó) | Build pybind từ `third_party/XRoboToolkit-PC-Service-Pybind_X86_and_ARM64`; cài PC service theo XR-Robotics, cần sudo trên máy sim |
| 3 | Kính và máy sim phải cùng LAN; luồng ảnh qua TCP cổng 13579 | rtx3060 có `192.168.1.8/24`, chỉ vào qua SSH | Hỏi Hiếu máy nào chạy sim khi thu và kính có vào được mạng đó không |
| 4 | Recorder không ghi tư thế khay và linh kiện | `mj_objects` của env khay rỗng (đo), nên không có `observation.object_poses` | Wrapper thêm trạng thái khay, linh kiện và 7 cờ bước vào frame, lấy từ `info["privileged"]` và `info["tray_report"]` |
| 5 | CLI gọi `env.reset()` không seed | Task rút seed train ngẫu nhiên; seed vẫn vào `environment_config` | Wrapper reset theo danh sách (level, seed) |
| 6 | Mặc định 30 000 bước (600 s) thay 4500 của task | `env.spec.max_episode_steps = 30000` khi truyền mặc định của CLI | Truyền `--max-episode-steps=4500` |
| 7 | Agent dùng `time.monotonic()` cho nội suy WBC và ngủ cho đủ 50 Hz thời gian thực | Mã `pico_decoupled_agent.py` | Đúng cho người thu. Khi sinh S2, agent con dùng đồng hồ sim để ra kết quả tất định (cùng ý D-17) |
| 8 | Lượt hỏng bị bỏ khi reset, không để lại bản ghi | Mã `teleop_decoupled_wbc.py` (`skip_and_start_new_episode`) | Wrapper ghi log mọi lượt cho sổ chi phí |
| 9 | Chưa có khối `flywheel` (nguồn, người thu, phiên bản) | | Wrapper thêm vào `environment_config`, như DA-33 nhiệm vụ 5 |
| 10 | `action.eef` lấy từ `TeleopPolicy`; chưa rõ ở khung tay cầm so với kính hay khung robot | Mã `teleop_policy.py` | Kiểm ở nhiệm vụ 5 trước khi biến đổi; nếu là khung người thì tính tư thế cổ tay bằng FK từ `action` |

## Kiểm được khi chưa có kính

`decoupled_wbc` có `DummyStreamer`, nhưng `PicoDecoupledAgent` vẫn mở cổng TCP và đọc nút qua `xr_client`. Wrapper nhiệm vụ 2 nên có agent con nhận một streamer bất kỳ; cùng cơ chế đó là streamer phát lại của S2 (nhiệm vụ 6). Nhờ vậy wrapper, recorder và streamer phát lại test được trên rtx3060 trước khi có kính.
