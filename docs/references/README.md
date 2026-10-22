# Nguồn nghiên cứu

Kết quả của tác giả không phải kết quả của đội. Khi triển khai cần kiểm quyền sử dụng code, mô hình và dữ liệu.

## Nguồn cho recipe hiện hành

| Nguồn | Dùng để làm gì |
|---|---|
| [Ψ₀](https://psi-lab.ai/Psi0/) | Model nền được fine-tune trong PoC |
| [SIMPLE](https://github.com/physical-superintelligence-lab/SIMPLE) | Simulator, dữ liệu teleop/motion planning và bộ đánh giá Level 0/1/2 |
| [psi-data/simple](https://huggingface.co/datasets/USC-PSI-Lab/psi-data/tree/main/simple) | Dữ liệu task G1 cho PoC |
| [MimicGen](https://mimicgen.github.io/), [DAgger](https://arxiv.org/abs/1011.0686), [HG-DAgger](https://arxiv.org/abs/1810.02890), [DataMIL](https://arxiv.org/html/2505.09603v1), [Mulligan](https://arxiv.org/abs/2610.05882), [DISEIL](https://arxiv.org/abs/2609.08123) | Tiền lệ cho sinh biến thể, correction và chọn dữ liệu theo lỗi trong thuật toán Failure → Data |
| [NVIDIA V2D](https://nvidia-isaac.github.io/video_to_data/), [DreamDojo](https://dreamdojo-world.github.io/) | Hướng mở rộng sau PoC |

Cách dùng các nguồn này nằm trong [spec v10](../spec-v10-failure-to-data.md).

## Thư viện paper local

PDF giữ trên máy tại `docs/references/papers/` và không commit lên GitHub (xem `.gitignore`). Website và spec không cần thư mục này để chạy.

- Thu và tăng cường dữ liệu: UMI, MimicGen, DreamGen.
- Người → robot: HumanEgo.
- Model và world model: FOCA, FluxVLA, WALA, World Action Models Survey, Fast WAM, Faster WAM, DreamZero, Tau0 WM.

FluxVLA, FOCA và nhóm world model là nguồn của các thiết kế trước Pitch v10; tài liệu cũ dùng chúng nằm trong tag git `archive/v3`.
