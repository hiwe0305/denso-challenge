# Run in the session's kernel by the shared CU watcher at the soft cap (DA-26):
#   colab exec -s da26-t2-ft-vego-n20-s0 --timeout 590 -f configs/runplans/he/persist_cell.py
# Copies every job of /content/da26/runs (metrics, results, complete checkpoints) to
# Drive, as the driver's `persist` phase; the train shell's `persist --watch` keeps
# running beside it.
import sys

sys.path.insert(0, "/content/da26/fw/scripts/he")
from he1_colab import main  # noqa: E402

main(["persist", "--work", "/content/da26"])
