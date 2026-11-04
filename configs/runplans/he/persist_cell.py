# The shared CU watcher's soft-cap --persist once Drive is mounted (DA-26); until then
# the hook is scripts/he/he1_fetch.py once (docs/he/he-1.md section 7). Usage:
#   colab exec -s da26-t2-ft-vego-n20-s0 --timeout 590 -f configs/runplans/he/persist_cell.py
# Copies every job of /content/da26/runs (metrics, results, complete checkpoints) to
# Drive, as the driver's `persist` phase; the train shell's `persist --watch` keeps
# running beside it.
import sys

sys.path.insert(0, "/content/da26/fw/scripts/he")
from he1_colab import main  # noqa: E402

main(["persist", "--work", "/content/da26"])
