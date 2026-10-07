# 12 · Claim → evidence → phạm vi

| Tuyên bố | Artifact/check | Kết luận đúng |
|---|---|---|
| Pipeline dữ liệu/model/thực thi nối được | run.py + releases/checkpoints/MuJoCo traces | Executed reference pipeline |
| Actions có outcome thực thi trong sim | seed/variants logged; measured object height/target | Reference kinematic weld sim, không physical grasp real |
| Training/reload có thật | weights/loss/checkpoint hashes/reload error | Ridge predictor reference, không GR00T |
| S generalize trong reference | Final12/12 + disjoint regression | Task/profile/domain nhỏ, không visual/real efficiency |
| C sửa local chưa đủ | Dev pass/final0/12/gate false | Không promote dù example nhìn tốt |
| Không train trên inputs sai | Pytest contract/rejection tests | Reference schemas guard; native needs its own tests |
| Không lỗi hóa bước chưa tới | zero-skill trace + tests | not_attempted đúng trong reference |
| Không pass khi thiếu verifier | unknown trace + tests | unknown giữ; timeout fulltask fail |
| Phân biệt prediction/command/response | binding-fault trace | Health route; không chứng minh causal module diagnosis |
| Human học motor giúp GR1 | Chưa artifact | not_integrated/not_tested |
| Native VLA latent/action traces | Chưa checkpoint/rollout | not_tested |
| Đã tiết kiệm tổng chi phí | Chưa activity/cost ledger đầy đủ | not_established |

Hash manifest nhận diện artifacts, không tự scientific validity. Tests meaningful về schema/split/scoring/gates; không xác nhận behavior mọi task. Final selection/training không nối ngược cùng round. Version/source data/profile thay phải rerun applicable checks và invalidate stale claims.
