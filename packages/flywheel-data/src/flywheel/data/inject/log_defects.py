"""Train log defects T1-T8 and RTC log defects R1-R2 (DA-27 task 2, AC 2).

Logs are written in the schemas the real ones use and in the layout the evaluation
lane reads (design 27/10 sections 9.2, 10):

    train/<job>/metrics.jsonl          TrainingMetric per record (DA-19 trainer log)
    train/<job>/action_layout.json     ActionLayout of the G1 action
    train/<job>/probe_p4.json          ProbeP4 of the job's checkpoint, and of its parent
    train/<job>/probe_p4_parent.json
    rtc/<job>/rtc.jsonl                RTCInferenceRecord per chunk (DA-19 RTCClient log)

A clean job is a smooth run drawn from the job's own seed. Each defect changes one
signal past the threshold of `configs/eval/diagnosis/{train,system}.yaml` and nothing
else, so the evaluation lane's detectors raise exactly its code. Like the data copies
there are two copies of the same shape, neutral ids, and the answer is only in their
sealed DefectManifests. The testkit has no metrics or RTC log fake yet, so the
generator here stands in for `FakeTrainer` and the RTC fake of design 9.2.
"""

import argparse
import hashlib
import json
import math
import os
import random
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from flywheel.contracts.artifacts import (
    ActionLayout,
    Defect,
    DefectManifest,
    ProbeP1,
    ProbeP3,
    ProbeP4,
    RTCInferenceRecord,
)
from flywheel.contracts.training import TrainingMetric
from flywheel.contracts.v0 import DatasetRef
from flywheel.data.inject.build import BenchmarkBuild, BuiltCopy, ledger_handoff, load_layout
from flywheel.data.inject.codes import LOG_DEFECT_CODES
from flywheel.data.inject.config import InjectConfig, LogDefectConfig, load_inject_config
from flywheel.data.inject.dataset import copy_ids
from flywheel.data.inject.manifest import MANIFEST_FILENAME, seal_manifest
from flywheel.data.ledger import job_ledger

G1_LAYOUT = Path(__file__).resolve().parents[6] / "configs" / "embodiments" / "g1.yaml"
PROBE_SET = hashlib.sha256(b"DA-27 synthetic probe set").hexdigest()
STAMP = 1_700_000_000  # one mtime for every file of both copies

Params = dict[str, bool | float | int | str]
Job = tuple[list[TrainingMetric], ProbeP4, ProbeP4]


def _job_id(seed: int, copy_id: str, kind: str, i: int) -> str:
    return "job-" + hashlib.sha256(f"{seed}:{copy_id}:{kind}:{i}".encode()).hexdigest()[:12]


def clean_train_job(job_id: str, layout: ActionLayout, cfg: LogDefectConfig) -> Job:
    """A smooth train run: train and val loss falling, every group with it, no spike."""
    rng = random.Random(job_id)
    tau, base, amp = rng.uniform(500, 900), rng.uniform(0.15, 0.25), rng.uniform(1.5, 2.0)
    groups = list(dict.fromkeys(d.group for d in layout.dimensions))
    weight = {g: rng.uniform(0.5, 1.5) for g in groups}
    dims = len(layout.dimensions)
    ckpt = f"ckpt-{job_id[4:]}"
    common: dict[str, Any] = {
        "run_plan_id": f"rp-{job_id[4:]}",
        "job_id": job_id,
        "checkpoint_id": ckpt,
        "release_id": f"rel-{job_id[4:]}",
        "attempt": 0,
        "lr": 1e-4,
        "vlm_frozen": True,
    }
    records = []
    for step in range(cfg.train_every, cfg.steps + 1, cfg.train_every):
        loss = base + amp * math.exp(-step / tau)
        records.append(
            TrainingMetric(
                **common,
                step=step,
                epoch=step // 1000,
                split="train",
                loss=loss,
                loss_by_group={g: weight[g] * loss for g in groups},
                grad_norm_vlm=0.0,
                grad_norm_action=rng.uniform(0.5, 2.0),
                pred_var_by_dim=[rng.uniform(0.02, 0.08) for _ in range(dims)],
                pred_std=[rng.uniform(0.22, 0.28) for _ in range(dims)],
                target_std=[0.3] * dims,
                wall_time_s=step * 0.5,
            )
        )
        if step % cfg.val_every == 0:
            records.append(
                TrainingMetric(
                    **common,
                    step=step,
                    epoch=step // 1000,
                    split="val",
                    loss=1.05 * loss,
                    wall_time_s=step * 0.5,
                )
            )
    parent = _probe(f"ckpt-parent-{job_id[4:]}", f"ckpt-root-{job_id[4:]}", groups, rng, 1.0)
    child = _probe(ckpt, parent.checkpoint_id, groups, random.Random(f"{job_id}:p4"), 1.0)
    child = _improve(child, parent)
    return records, child, parent


def _probe(ckpt: str, parent: str, groups: list[str], rng: random.Random, scale: float) -> ProbeP4:
    return ProbeP4(
        checkpoint_id=ckpt,
        parent_checkpoint_id=parent,
        p1=ProbeP1(
            checkpoint_id=ckpt,
            dataset_sha256=PROBE_SET,
            accuracy_by_question_type={
                q: scale * rng.uniform(0.7, 0.9) for q in ("object", "position", "stage")
            },
        ),
        p3=ProbeP3(
            checkpoint_id=ckpt,
            dataset_sha256=PROBE_SET,
            error_by_group={g: rng.uniform(0.05, 0.15) for g in groups},
            error_by_chunk_pos=[0.1] * 4,
            hand_event_offset_steps=2.0,
            out_of_limit_dims=[],
        ),
    )


def _improve(child: ProbeP4, parent: ProbeP4) -> ProbeP4:
    """The child no worse than its parent on any P4 metric: a clean fine-tune."""
    p1 = child.p1.model_copy(
        update={
            "accuracy_by_question_type": {
                q: v * 1.02 for q, v in parent.p1.accuracy_by_question_type.items()
            }
        }
    )
    p3 = child.p3.model_copy(
        update={"error_by_group": {g: v * 0.98 for g, v in parent.p3.error_by_group.items()}}
    )
    return child.model_copy(update={"p1": p1, "p3": p3})


def _with(
    records: list[TrainingMetric], pick: Callable[[TrainingMetric], bool], **change: object
) -> list[TrainingMetric]:
    return [r.model_copy(update=change) if pick(r) else r for r in records]


def inject_train(
    kind: str, job: Job, cfg: LogDefectConfig, rng: random.Random
) -> tuple[Job, Params]:
    """One defect of `kind` in a clean job; every change stays past its threshold."""
    records, child, parent = job
    train = [r for r in records if r.split == "train"]
    mid = cfg.steps // 2
    if kind == "T1_divergence":  # one loss that is not finite
        step = rng.choice([r.step for r in train if r.step >= mid])
        records = _with(records, lambda r: r.split == "train" and r.step == step, loss="NaN")
        return (records, child, parent), {"step": step}
    if kind == "T2_not_learning":  # train, val and every group flat
        first = {s: next(float(r.loss) for r in records if r.split == s) for s in ("train", "val")}
        records = [
            r.model_copy(
                update={
                    "loss": first[r.split] * (1 - cfg.t2_val_drop * r.step / cfg.steps),
                    "loss_by_group": {
                        g: v / float(r.loss) * first[r.split] for g, v in r.loss_by_group.items()
                    },
                }
            )
            for r in records
        ]
        return (records, child, parent), {"total_drop": cfg.t2_val_drop}
    if kind == "T3_overfitting":  # val rises at the last measurements while train falls
        vals = [r for r in records if r.split == "val"][-cfg.t3_val_rises :]
        start = float(vals[0].loss)
        rises = {r.step: start * (1 + 0.03 * (i + 1)) for i, r in enumerate(vals)}
        records = [
            r.model_copy(update={"loss": rises[r.step]})
            if r.split == "val" and r.step in rises
            else r
            for r in records
        ]
        return (records, child, parent), {"rises": cfg.t3_val_rises, "from_step": vals[0].step}
    if kind == "T4_group_imbalance":  # one group stops falling, the others go on
        group = rng.choice(sorted(train[0].loss_by_group))
        frozen = train[0].loss_by_group[group]
        records = [
            r.model_copy(update={"loss_by_group": {**r.loss_by_group, group: frozen}})
            if r.split == "train"
            else r
            for r in records
        ]
        return (records, child, parent), {"group": group}
    if kind == "T5_dead_dimension":  # one dimension's prediction variance gone
        dim = rng.randrange(len(train[0].pred_var_by_dim))
        last = cfg.steps - 2 * cfg.t5_window_steps

        def dead(r: TrainingMetric) -> TrainingMetric:
            var = list(r.pred_var_by_dim)
            var[dim] = 0.0
            return r.model_copy(update={"pred_var_by_dim": var})

        records = [dead(r) if r.split == "train" and r.step > last else r for r in records]
        return (records, child, parent), {"dimension": dim}
    if kind == "T6_mode_collapse":  # predictions far narrower than the targets
        records = [
            r.model_copy(update={"pred_std": [cfg.t6_std_ratio * t for t in r.target_std]})
            if r.split == "train" and r.step > mid
            else r
            for r in records
        ]
        return (records, child, parent), {"std_ratio": cfg.t6_std_ratio, "from_step": mid}
    if kind == "T7_forgetting":  # the child lost one P1 question type its parent had
        question = rng.choice(sorted(parent.p1.accuracy_by_question_type))
        accuracy = dict(child.p1.accuracy_by_question_type)
        accuracy[question] = parent.p1.accuracy_by_question_type[question] * (1 - cfg.t7_p1_drop)
        child = child.model_copy(
            update={"p1": child.p1.model_copy(update={"accuracy_by_question_type": accuracy})}
        )
        return (records, child, parent), {"question": question, "drop": cfg.t7_p1_drop}
    if kind == "T8_gradient_anomaly":  # the frozen VLM receives gradient
        step = rng.choice([r.step for r in train if r.step >= mid])
        records = _with(
            records,
            lambda r: r.split == "train" and r.step == step,
            grad_norm_vlm=cfg.t8_frozen_grad,
        )
        return (records, child, parent), {"step": step, "grad_norm_vlm": cfg.t8_frozen_grad}
    raise ValueError(f"{kind} is not a train log defect")


def clean_rtc_log(job_id: str, cfg: LogDefectConfig) -> list[RTCInferenceRecord]:
    """A healthy RTC client: latency well under tau_lat, no stall past the server's d."""
    rng = random.Random(job_id)
    trace = f"tr-{job_id[4:]}"
    return [
        _chunk(job_id, trace, i, rng.uniform(0.04, 0.09), rng.uniform(0.0, 0.02), cfg)
        for i in range(cfg.rtc_chunks)
    ]


def _chunk(
    job_id: str, trace: str, i: int, latency: float, jump: float, cfg: LogDefectConfig
) -> RTCInferenceRecord:
    sent = 0.4 * i
    return RTCInferenceRecord(
        job_id=job_id,
        trace_id=trace,
        chunk_index=i,
        observation_sent_s=sent,
        chunk_received_s=sent + latency,
        delay_steps=math.ceil(latency * cfg.control_hz),
        buffer_level=0,
        boundary_jump=jump,
    )


def inject_rtc(
    kind: str, log: list[RTCInferenceRecord], cfg: LogDefectConfig, rng: random.Random
) -> tuple[list[RTCInferenceRecord], Params]:
    """R1: sustained latency past tau_lat within d; R2: one stall past the server's d.

    Chunk 0 is never picked: the system check leaves it out of R1 and R2 (the
    client asks for it before any action ran), so a defect there would be one
    nobody can detect.
    """
    count = max(1, round(cfg.r1_fraction * len(log))) if kind == "R1_high_latency" else 1
    latency = cfg.r1_latency_s if kind == "R1_high_latency" else cfg.r2_latency_s
    if kind not in ("R1_high_latency", "R2_buffer_depleted"):
        raise ValueError(f"{kind} is not an RTC log defect")
    picked = set(rng.sample([r.chunk_index for r in log if r.chunk_index > 0], count))
    log = [
        _chunk(r.job_id, r.trace_id, r.chunk_index, latency, r.boundary_jump, cfg)
        if r.chunk_index in picked
        else r
        for r in log
    ]
    return log, {"chunks": count, "latency_s": latency}


def _write_train(job_dir: Path, job: Job, layout: ActionLayout) -> None:
    records, child, parent = job
    job_dir.mkdir(parents=True)
    (job_dir / "metrics.jsonl").write_text("".join(r.model_dump_json() + "\n" for r in records))
    (job_dir / "action_layout.json").write_text(layout.model_dump_json(indent=2))
    (job_dir / "probe_p4.json").write_text(child.model_dump_json(indent=2))
    (job_dir / "probe_p4_parent.json").write_text(parent.model_dump_json(indent=2))


def _write_copy(
    root: Path, copy_id: str, seed: int, layout: ActionLayout, cfg: LogDefectConfig, inject: bool
) -> DefectManifest:
    rng = random.Random(f"log-defects:{seed}:{copy_id}")
    train_kinds = [k for k in LOG_DEFECT_CODES if k.startswith("T")]
    rtc_kinds = [k for k in LOG_DEFECT_CODES if k.startswith("R")]
    defects = []
    for part, kinds, extra in (
        ("train", train_kinds, cfg.extra_clean_train_jobs),
        ("rtc", rtc_kinds, cfg.extra_clean_rtc_jobs),
    ):
        total = len(kinds) * cfg.jobs_per_kind + extra
        plan = [k for k in kinds for _ in range(cfg.jobs_per_kind)] if inject else []
        plan += [""] * (total - len(plan))
        rng.shuffle(plan)
        for i, kind in enumerate(plan):
            job_id = _job_id(seed, copy_id, part, i)
            if part == "train":
                job = clean_train_job(job_id, layout, cfg)
                if kind:
                    job, params = inject_train(kind, job, cfg, rng)
                _write_train(root / part / job_id, job, layout)
            else:
                log = clean_rtc_log(job_id, cfg)
                if kind:
                    log, params = inject_rtc(kind, log, cfg, rng)
                (root / part / job_id).mkdir(parents=True)
                (root / part / job_id / "rtc.jsonl").write_text(
                    "".join(r.model_dump_json() + "\n" for r in log)
                )
            if kind:
                defects.append(
                    Defect(
                        target_ref=f"{part}/{job_id}",
                        code=LOG_DEFECT_CODES[kind],
                        parameters={"kind": kind, **params},
                    )
                )
    (root / "meta").mkdir()
    (root / "meta" / "benchmark_copy.json").write_text(
        json.dumps(
            {
                "benchmark_copy_id": copy_id,
                "scaffolding": {
                    "logs": "synthetic train and RTC logs written by DA-27; not measured"
                },
            }
        )
    )
    for path in [*root.rglob("*"), root]:
        os.utime(path, (STAMP, STAMP))
    return DefectManifest(dataset_id=copy_id, seed=seed, defects=defects)


def build_log_benchmark(
    out_dir: Path,
    config: InjectConfig | None = None,
    layout: ActionLayout | None = None,
    *,
    store: Path | None = None,
    run_plan_id: str | None = None,
) -> BenchmarkBuild:
    """Write the defect and the clean log copy under `out_dir` and seal their answers."""
    cfg = config or load_inject_config()
    layout = layout or load_layout(G1_LAYOUT)
    defect_id, clean_id = copy_ids(cfg.seed, namespace="logs")
    copies, answers = out_dir / "copies", out_dir / "answers"
    with job_ledger(
        "data_generation",
        "inject_logs",
        1.0,
        note="Assumed 1 s for both log copies",
        run_plan_id=run_plan_id,
        story="DA-27",
        store=store,
    ) as job:
        built = []
        for copy_id, inject in ((defect_id, True), (clean_id, False)):
            manifest = _write_copy(copies / copy_id, copy_id, cfg.seed, layout, cfg.logs, inject)
            path = answers / copy_id / MANIFEST_FILENAME
            digest = seal_manifest(manifest, path, copy_roots=[copies])
            built.append(
                BuiltCopy(DatasetRef(dataset_id=copy_id, uri=str(copies / copy_id)), path, digest)
            )
    return BenchmarkBuild(built[0], built[1], job)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the two DA-27 log benchmark copies")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--store", type=Path, help="store root; default $FW_ROOT or ./fwdata")
    args = parser.parse_args(argv)
    result = build_log_benchmark(args.out, load_inject_config(args.config), store=args.store)
    copies = sorted((result.defect, result.clean), key=lambda c: c.ref.dataset_id)
    print(
        json.dumps(
            {
                "copies": [
                    {
                        "dataset_id": c.ref.dataset_id,
                        "uri": c.ref.uri,
                        "manifest": str(c.manifest_path),
                        "manifest_sha256": c.manifest_sha256,
                    }
                    for c in copies
                ],
                "ledger": ledger_handoff(result.ledger),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
