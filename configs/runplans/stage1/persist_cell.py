# Run in the session's kernel by the shared CU watcher at the soft cap (DA-30):
#   colab exec -s da30-stage1 -f configs/runplans/stage1/persist_cell.py
# Copies logs and metrics (not weights) to Drive, as the driver's `persist` phase.
import sys

sys.path[:0] = [
    "/content/da30/fw/packages/flywheel-psi0/src",
    "/content/da30/fw/packages/flywheel-contracts/src",
]
from flywheel_psi0.stage1.colab import main  # noqa: E402

main(
    [
        "persist",
        "--work",
        "/content/da30",
        "--plan",
        "/content/da30/fw/configs/runplans/stage1/egodex-short.yaml",
    ]
)
