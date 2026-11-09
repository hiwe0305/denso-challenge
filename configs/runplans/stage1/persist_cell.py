# Run in the session's kernel by the shared CU watcher at the soft cap (DA-30):
#   colab exec -s <session> -f configs/runplans/stage1/persist_cell.py
# The driver's `persist` phase on the plan `setup` recorded in /content/da30/plan.path
# (egodex-short when there is none): logs and metrics, then the VLM if the plan keeps it.
import sys
from pathlib import Path

sys.path[:0] = [
    "/content/da30/fw/packages/flywheel-psi0/src",
    "/content/da30/fw/packages/flywheel-contracts/src",
]
from flywheel_psi0.stage1.colab import main  # noqa: E402

pointer = Path("/content/da30/plan.path")
plan = (
    pointer.read_text().strip()
    if pointer.exists()
    else "/content/da30/fw/configs/runplans/stage1/egodex-short.yaml"
)
main(["persist", "--work", "/content/da30", "--plan", plan])
