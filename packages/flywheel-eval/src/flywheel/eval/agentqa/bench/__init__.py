"""Scorer of the injected-defect benchmark for QA and Agent QA/QC (DA-31).

Reads what the code checks and the agent reported on each copy of DA-27's
benchmark (`detections`, `logs`), then opens the sealed answer key (`answers`)
through a `session` that refuses to do so before both layers have run. Only this
package reads a `DefectManifest`; the agent code beside it never does
(`test_bench_barrier.py`).
"""

from flywheel.eval.agentqa.bench.answers import AnswerKeyError
from flywheel.eval.agentqa.bench.detections import (
    BenchInputError,
    Detection,
    LayerRun,
    agent_run,
    read_qa_work,
)
from flywheel.eval.agentqa.bench.logs import run_log_checks
from flywheel.eval.agentqa.bench.session import (
    AnswerLeak,
    BenchIncomplete,
    BenchSession,
    OpenedBench,
)

__all__ = [
    "AnswerKeyError",
    "AnswerLeak",
    "BenchIncomplete",
    "BenchInputError",
    "BenchSession",
    "Detection",
    "LayerRun",
    "OpenedBench",
    "agent_run",
    "read_qa_work",
    "run_log_checks",
]
