# 05 · Protocol và phạm vi claim

## Câu hỏi chính

Đạt cùng quality với ít target-robot roots/operator-hours hơn? Total cost thấp hơn sau source processing/bridge/generation/QA/train/eval? Evidence giúp engineer chọn tests/interventions có ích? Chưa nhận auto-cause.

## Hai cấp kiểm chứng

Cấp engineering reference: kiểm contracts, training/reload, executed traces, independent scoring, negative cases và promotion gates. Đã có một run trong MuJoCo nhỏ. Không benchmark visual VLA/human/GR1.

Cấp native study: pin code/weights/config/task/controller/scorer/rights; useful learned GR1 baseline; source gates. Chưa chạy.

## Native contrasts sau eligibility

| Arm | Recipe |
|---|---|
| R | Common pretrained base + target robot |
| H | Base + eligible human route + cùng target robot budget |
| S | Base + target robot + accepted sim execution |
| HS | Human và sim definitions giống H/S; không đổi nguồn đồng thời |

Schedule/prefix/co-training/compute/weights/params freeze chỉ khóa sau development. Pretrained human priors chung thuộc mọi arms, không nhận là gain mới. Mixture không bắt thắng hoặc bắt sử dụng.

V3 grid27 giả định shared prefix per seed; v3.1 chưa khóa assumption đó. RunPlan tính actual source pretraining/target runs/seeds/budgets/retries/bootstrap/controls từ recipe hợp lệ. Baseline + source pilots trước factorial grid. V2 core15T/F/A đo acquisition selection khác câu hỏi; giữ historical, không dùng lại ngân sách cũ.

Primary workflow comparison ghi extra source/compute/cost. Causal source advantage vượt extra compute cần matched controls với estimand xác định; không ép equal steps và equal compute khi không thể đồng thời. Không gọi một successful auxiliary loss là transfer.

## Freeze/final

Roots/ancestors/scenarios split trước derivatives. Development dùng diagnostic selection/correction/tuning. Final scenarios/conditions không vào generator/tuning/selection. Freeze recipes/checkpoints/scorer/binding trước final. Fail final: report hoặc round mới với fresh holdout, không tiếp tục train trên chính final rồi giữ tên independent.

Measure all task trials/timeouts/interventions; stage reach/unknown/transitions; good conditions regression; time/cycle và source accepted/rejected; compute/operator/engineer hours; uncertainty/train-seed variation. Sample size/power/noninferiority margin cần owner/development trước final. 12 reference trials rất nhỏ, không production estimate.

## Nghiệm thu

Local gain không đủ; candidate chỉ promote trong binding/domain đã kiểm khi đạt fulltask/heldout/regression và resource caps. Native → real robot acceptance riêng. Chi phí thiếu important quantities hoặc quality không đạt → savings unknown/undefined.

Reference run: R0/12, S12/12, C0/12 final; C local pass bị từ chối. Đây là deterministic reference test, idealized state + scripted sequencing; chưa scientific efficiency của GR1 hoặc human transfer. Không chọn recipe theo final; S đã chọn trên development trước final, C là alternative/diagnostic comparison.

## Mở rộng evaluation sau khảo sát training

[Blueprint](15-dataset-training-blueprint.md) bổ sung controls cho optional action-free future route: native baseline; cùng architecture + auxiliary trên robot videos; rồi thêm recorded/generated video riêng, theo cap. Compute-matched replay khi cần tách source benefit khỏi extra training. Few-shot curve proposed theo unique robot roots; quality/cost là end metric. World Model physics/temporal prediction và downstream control chấm riêng; không dùng visual realism thay task success. Human wrist contrast vẫn R_common vs R_common+H; không gộp nó với FOCA route.
