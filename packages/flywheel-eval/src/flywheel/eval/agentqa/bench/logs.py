"""The code layer on a log copy: this lane's F-TRAIN and F-SYS detectors, job by job.

A log copy of DA-27 holds `train/<job>/` dirs (`metrics.jsonl` and probes, read by
DA-08's `diagnose_train`) and `rtc/<job>/rtc.jsonl` logs (read by DA-13's R1 and
R2 checks). No api function takes an RTC log alone yet (`diagnose_episode_system`
needs a whole trace), so the R checks are called the way the seam test
`tests/e2e/test_log_defects_detected.py` calls them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from flywheel.eval.agentqa.bench.detections import (
    Detection,
    LayerRun,
    log_units,
    read_copy_id,
)
from flywheel.eval.api import DEFAULT_SYSTEM_CONFIG, DEFAULT_TRAIN_CONFIG, diagnose_train
from flywheel.eval.config import load_system_thresholds
from flywheel.eval.diagnosis.system.reader import read_rtc_log
from flywheel.eval.diagnosis.system.runtime import check_r1, check_r2

RTC_LOG = "rtc.jsonl"


def run_log_checks(
    root: Path,
    train_config: Path = DEFAULT_TRAIN_CONFIG,
    system_config: Path = DEFAULT_SYSTEM_CONFIG,
) -> LayerRun:
    """Run the detectors on every job of the log copy at `root`.

    The copy's id comes from its own `meta/benchmark_copy.json`. `reported_at` is
    when the last job was checked.
    """
    dataset_id = read_copy_id(root)
    units = log_units(root)
    system, _ = load_system_thresholds(system_config)
    detections: list[Detection] = []
    for unit in units:
        job = root / unit
        if (job / RTC_LOG).is_file():
            records = read_rtc_log(job / RTC_LOG)
            found = check_r1(records, system.r1).findings + check_r2(records, system.r2).findings
            codes = [f.code for f in found]
        else:
            codes = [f.code for f in diagnose_train(job, train_config).findings]
        detections += [Detection(unit, code) for code in codes]
    return LayerRun(
        layer="code",
        dataset_id=dataset_id,
        units=units,
        detections=tuple(dict.fromkeys(detections)),
        reported_at=datetime.now(timezone.utc),
        inputs=(root.as_posix(),),
    )
