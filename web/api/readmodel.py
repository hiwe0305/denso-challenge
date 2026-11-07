"""Read side of the API (DESIGN.md §7.1, §7.4).

The routes in `app.py` never touch storage. They call a `ReadModel`, and there
are two of them, for the same reason `fwsync` has two sinks: the dev machine
has no PostgreSQL yet (§9.3), and the read path still has to be tested now.

* ``SinkReadModel`` reads the JSONL tables that ``fwsync import --sink jsonl``
  writes, and computes each view of ``web/schema/70-views.sql`` in Python.
  This is also the fallback of §9.4 if ADR-13 keeps Postgres out of L0.
* ``PostgresReadModel`` will ``SELECT`` from those views. It needs `psycopg`
  and a database, so constructing it says exactly that instead of failing on
  an import.

Every method returns plain dicts in the shapes of ``web/fe/src/api/types.ts``.
The test ``web/tests/test_api.py`` compares them with the responses the FE's
MSW layer serves for the same mock set, so FE and API cannot drift apart.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from web.contracts.enums import ALL

Row = dict[str, Any]

DATA_BUDGET_DIAGNOSIS = ALL["data_budget_diagnosis"]
PIPELINE_STAGE = ALL["pipeline_stage"]

#: g/c stop rule: 1 percentage point per $100 (spec v10.5 §8).
STOP_THRESHOLD_PP_PER_100USD = 1

FAMILIES = ("F-DATA", "F-TRAIN", "F-OFF", "F-CL", "F-SYS")


class ReadModel(Protocol):
    """One method per read endpoint of §7.1. `None` means "not found or not yours"."""

    def recommendations(self) -> list[Row]: ...
    def recommendation(self, rec_id: str) -> Row | None: ...
    def steps(self, rec_id: str) -> list[Row]: ...
    def clusters(self, rec_id: str) -> list[Row]: ...
    def card(self, cluster_id: str) -> Row | None: ...
    def repair_tickets(self, rec_id: str | None) -> list[Row]: ...
    def fix_rates(self) -> list[Row]: ...
    def evaluations(self, role: str) -> list[Row]: ...
    def evaluation(self, eval_id: str, role: str) -> Row | None: ...
    def eval_episodes(self, eval_id: str, role: str) -> list[Row] | None: ...
    def funnel(self, eval_id: str, role: str) -> list[Row] | None: ...
    def system_checks(self, eval_id: str, role: str) -> list[Row] | None: ...
    def failures(self, eval_id: str, role: str) -> Row | None: ...
    def datasets(self) -> list[Row]: ...
    def dataset(self, dataset_id: str) -> Row | None: ...
    def stages(self, dataset_id: str) -> Row | None: ...
    def episodes(self, dataset_id: str) -> list[Row] | None: ...
    def report(self, dataset_id: str) -> Row | None: ...
    def intakes(self) -> list[Row]: ...
    def branches(self, task_id: str) -> list[Row]: ...
    def he_curve(self, role: str) -> list[Row]: ...
    def e1_curve(self) -> list[Row]: ...
    def ledger(self) -> list[Row]: ...
    def cost_by_branch(self) -> Row: ...
    def cost_by_intervention(self) -> list[Row]: ...
    def sensitivity(self, price_book: str | None) -> list[Row]: ...
    def decisions(self) -> list[Row]: ...
    def defect_scoreboard(self) -> Row: ...
    def defect_scores(self) -> list[Row]: ...
    def refresh(self) -> None: ...


# ---------------------------------------------------------------- helpers


def js_round(value: float, digits: int = 4) -> float:
    """Round like the FE (`Math.round`), half up, not Python's half to even."""
    factor = float(10**digits)
    return math.floor(value * factor + 0.5) / factor


def _sum(values: Iterable[float | None]) -> float:
    return float(sum((v or 0) for v in values))


def _sum_or_none(values: Iterable[float | None]) -> float | None:
    """A sum that stays None when nothing was measured: "not measured" is not 0."""
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class SinkTables:
    """The JSONL tables of `fwsync import --sink jsonl`, read once and cached."""

    directory: Path
    _cache: dict[str, list[Row]] = field(default_factory=dict)

    def __call__(self, table: str) -> list[Row]:
        if table not in self._cache:
            path = self.directory / f"{table}.jsonl"
            if not path.exists():
                self._cache[table] = []
            else:
                lines = path.read_text(encoding="utf-8").splitlines()
                self._cache[table] = [json.loads(line) for line in lines if line.strip()]
        return self._cache[table]

    def invalidate(self) -> None:
        """Forget every table; the next read sees what `fwsync import` just wrote."""
        self._cache.clear()


class SinkReadModel:
    """Each view of 70-views.sql, computed over the sink tables."""

    def __init__(
        self,
        tables: Callable[[str], list[Row]],
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.t = tables
        self.now = now

    def refresh(self) -> None:
        invalidate = getattr(self.t, "invalidate", None)
        if callable(invalidate):
            invalidate()

    def decisions(self) -> list[Row]:
        """`decisions`, newest last as loaded; M10 shows them newest first."""
        return [
            {
                "id": d["decision_ref"],
                "kind": d.get("kind"),
                "target_kind": d.get("target_kind"),
                "target_id": d.get("target_id"),
                "conclusion": d.get("conclusion"),
                "reason": d.get("reason"),
                "source_action_id": d.get("source_action_id"),
                "origin": d["origin"],
            }
            for d in reversed(self.t("decisions"))
        ]

    # ------------------------------------------------------------ common

    def _sealed(self, ev: Row) -> bool:
        until = ev.get("sealed_until")
        return until is not None and _parse_ts(until) > self.now()

    def _can_see(self, ev: Row, role: str) -> bool:
        """BR-10: a sealed evaluation is visible to ADMIN only."""
        return role == "ADMIN" or not self._sealed(ev)

    def _rec_row(self) -> Row | None:
        rows = self.t("flywheel_recommendations")
        return rows[0] if rows else None

    # ============================================================ M7

    def recommendations(self) -> list[Row]:
        return [self._rec_summary(r) for r in self.t("flywheel_recommendations")]

    @staticmethod
    def _rec_summary(r: Row) -> Row:
        return {
            "id": r["recommendation_ref"],
            "round_no": r["round_no"],
            "task_id": r["task_id"],
            "status": r["status"],
            "checkpoint_id": r["checkpoint_ref"],
            "evaluation_id": r["evaluation_ref"],
            "run_plan_id": r["run_plan_ref"],
            "started_at": r.get("started_at"),
            "finished_at": r.get("finished_at"),
            "origin": r["origin"],
        }

    def _rec(self, rec_id: str) -> Row | None:
        return next(
            (r for r in self.t("flywheel_recommendations") if r["recommendation_ref"] == rec_id),
            None,
        )

    def recommendation(self, rec_id: str) -> Row | None:
        r = self._rec(rec_id)
        if r is None:
            return None
        interventions = [
            self._intervention_row(iv)
            for iv in self.t("interventions")
            if iv["recommendation_ref"] == rec_id
        ]
        interventions.sort(
            key=lambda iv: -(iv["gain_pp_per_100usd"] if iv["gain_pp_per_100usd"] is not None
                             else -1)
        )
        return {
            **self._rec_summary(r),
            "budget": self._budget(r, interventions),
            "interventions": interventions,
            "stop_threshold_pp_per_100usd": STOP_THRESHOLD_PP_PER_100USD,
        }

    def _budget(self, r: Row, interventions: list[Row]) -> list[Row]:
        """BR-07: three parallel ceilings. `used` is measured in the ledger."""
        spent = [
            entry for entry in self.t("cost_ledger_entries")
            if entry.get("recommendation_ref") == r["recommendation_ref"]
        ]
        live = [iv for iv in interventions if iv["status"] not in ("REJECTED", "CANCELLED")]

        def scaled(iv: Row, value: float) -> float:
            quantity = iv["approved_quantity"] or iv["target_quantity"]
            return float(value * quantity / iv["target_quantity"])

        def line(resource: str, cap: float, used: float, proposed: float) -> Row:
            return {
                "resource": resource,
                "cap": cap,
                "used": js_round(used),
                "proposed": js_round(proposed),
                "remaining": js_round(cap - used - proposed),
            }

        return [
            line("usd", r["budget_usd"], _sum(e.get("measured_usd") for e in spent),
                 _sum(scaled(iv, iv["estimated_usd"]) for iv in live)),
            line("human_minutes", r["budget_human_minutes"],
                 _sum(e.get("measured_human_minutes") for e in spent),
                 _sum(scaled(iv, iv["estimated_human_minutes"]) for iv in live)),
            line("gpu_hours", r["budget_gpu_hours"],
                 _sum(e.get("measured_gpu_hours") for e in spent),
                 _sum(scaled(iv, iv["estimated_gpu_hours"]) for iv in live)),
        ]

    def _intervention_row(self, iv: Row) -> Row:
        """v_cost_by_intervention, plus g/c."""
        ref = iv["intervention_ref"]
        measured = [e for e in self.t("cost_ledger_entries") if e.get("intervention_ref") == ref]
        usd = iv["estimated_usd"]
        return {
            "id": ref,
            "recommendation_id": iv["recommendation_ref"],
            "cluster_id": iv["cluster_ref"],
            "kind": iv["kind"],
            "status": iv["status"],
            "unit": iv["unit"],
            "target_quantity": iv["target_quantity"],
            "approved_quantity": iv.get("approved_quantity"),
            "fulfilled_count": sum(
                1 for e in self.t("episodes") if e.get("intervention_ref") == ref
            ),
            "n_failures": iv["n_failures"],
            "n_eff": iv["n_eff"],
            "expected_gain_pp": iv["expected_gain_pp"],
            "estimated_usd": usd,
            "estimated_human_minutes": iv["estimated_human_minutes"],
            "estimated_gpu_hours": iv["estimated_gpu_hours"],
            "gain_pp_per_100usd": (
                js_round(iv["expected_gain_pp"] / (usd / 100), 3) if usd > 0 else None
            ),
            "measured_usd": _sum_or_none(e.get("measured_usd") for e in measured),
            "measured_human_minutes": _sum_or_none(
                e.get("measured_human_minutes") for e in measured
            ),
            "measured_gpu_hours": _sum_or_none(e.get("measured_gpu_hours") for e in measured),
            "spec": iv.get("spec") or {},
            "origin": iv["origin"],
        }

    def steps(self, rec_id: str) -> list[Row]:
        rows = [s for s in self.t("flywheel_algo_steps") if s["recommendation_ref"] == rec_id]
        return [
            {
                "step_no": s["step_no"],
                "name": (s.get("detail") or {}).get("name") or f"bước {s['step_no']}",
                "status": s["status"],
                "started_at": s.get("started_at"),
                "finished_at": s.get("finished_at"),
                "rollout_count": s["rollout_count"],
                "skip_reason": s.get("skip_reason"),
                "origin": s["origin"],
            }
            for s in sorted(rows, key=lambda s: s["step_no"])
        ]

    def clusters(self, rec_id: str) -> list[Row]:
        """v_cluster_board."""
        return [
            self._cluster_row(c) for c in self.t("failure_clusters")
            if c["recommendation_ref"] == rec_id
        ]

    def _cluster_row(self, c: Row) -> Row:
        ref = c["cluster_ref"]
        runs = [r for r in self.t("diagnostic_runs") if r["cluster_ref"] == ref]
        diagnosis = c.get("diagnosis")
        rec = self._rec(c["recommendation_ref"])
        return {
            "cluster_id": ref,
            "recommendation_id": c["recommendation_ref"],
            "task_id": rec["task_id"] if rec else None,
            "failed_step": c["failed_step"],
            "failure_code": c["failure_code"],
            "level": c["level"],
            "member_count": c["member_count"],
            "diagnosis": diagnosis,
            "diagnosis_source": c.get("diagnosis_source"),
            "override_reason": c.get("override_reason"),
            "consumes_data_budget": diagnosis is not None and diagnosis in DATA_BUDGET_DIAGNOSIS,
            "is_system_fault": diagnosis is not None and diagnosis.startswith("HE_THONG"),
            "card_uri": c.get("card_uri"),
            "checks": c.get("checks") or {},
            "diagnostic_run_count": len(runs),
            "diagnostic_rollouts": sum(r["rollout_count"] for r in runs),
            "skipped_checks": sum(1 for r in runs if r["outcome"] == "skipped"),
            "repair_ticket_count": sum(
                1 for t in self.t("repair_tickets") if t["cluster_ref"] == ref
            ),
            "origin": c["origin"],
        }

    def cluster_members(self, cluster_id: str) -> list[Row]:
        """Failed, infra-clean episodes of the round's evaluation with the cluster key."""
        c = next((x for x in self.t("failure_clusters") if x["cluster_ref"] == cluster_id), None)
        rec = self._rec(c["recommendation_ref"]) if c else None
        if c is None or rec is None:
            return []
        return [
            e for e in self.t("eval_episodes")
            if e["evaluation_ref"] == rec["evaluation_ref"]
            and e["infra_status"] == "ok"
            and e.get("sim_success") is False
            and e.get("first_failed_step") == c["failed_step"]
            and e.get("failure_code") == c["failure_code"]
            and e["level"] == c["level"]
        ]

    def card(self, cluster_id: str) -> Row | None:
        c = next((x for x in self.t("failure_clusters") if x["cluster_ref"] == cluster_id), None)
        if c is None:
            return None
        member_refs = {m["eval_episode_ref"] for m in self.cluster_members(cluster_id)}
        system_checks = [
            row for s in self.t("system_diagnoses") if s["eval_episode_ref"] in member_refs
            if (row := self._system_check_row(s)) is not None
        ]
        runs = [
            {
                "cluster_id": r["cluster_ref"],
                "step_no": r["step_no"],
                "check_name": r["check_name"],
                "outcome": r["outcome"],
                "value": r.get("value"),
                "threshold": r.get("threshold"),
                "rollout_count": r["rollout_count"],
                "gpu_seconds": r["gpu_seconds"],
                "representative_episode_id": r.get("representative_episode_ref"),
                "skip_reason": r.get("skip_reason"),
                "origin": r["origin"],
            }
            for r in self.t("diagnostic_runs") if r["cluster_ref"] == cluster_id
        ]
        cluster_skips = (c.get("checks") or {}).get("skipped") or []
        skipped: list[Row] = [
            {"source": "algo_step", "code": str(s["step"]), "reason": s["reason"],
             "eval_episode_id": None}
            for s in cluster_skips
        ]
        skipped += [
            {"source": "diagnostic_run", "code": r["check_name"], "reason": r["skip_reason"] or "",
             "eval_episode_id": r["representative_episode_id"]}
            for r in runs if r["outcome"] == "skipped"
        ]
        skipped += [
            {"source": "system_check", "code": k["code"], "reason": k["reason"],
             "eval_episode_id": s["eval_episode_id"]}
            for s in system_checks for k in s["skipped"]
        ]
        episodes = {e["eval_episode_ref"]: e for e in self.t("eval_episodes")}
        diags = {s["eval_episode_ref"]: s for s in self.t("system_diagnoses")}
        representatives = [
            {
                "eval_episode_id": ref,
                "episode_index": episodes[ref]["episode_index"],
                "video_uri": episodes[ref].get("video_uri"),
                "trajectory_log_uri": episodes[ref].get("trajectory_log_uri"),
                "system_diagnosis": diags[ref]["diagnosis"] if ref in diags else None,
            }
            for ref in c.get("representative_refs") or [] if ref in episodes
        ]
        return {
            "cluster": self._cluster_row(c),
            "diagnostic_runs": runs,
            "skipped": skipped,
            "system_checks": system_checks,
            "representatives": representatives,
            "interventions": [
                self._intervention_row(iv) for iv in self.t("interventions")
                if iv["cluster_ref"] == cluster_id
            ],
            "repair_tickets": [
                t for t in self.repair_tickets(None) if t["cluster_id"] == cluster_id
            ],
        }

    def repair_tickets(self, rec_id: str | None) -> list[Row]:
        in_round = {
            c["cluster_ref"] for c in self.t("failure_clusters")
            if rec_id is None or c["recommendation_ref"] == rec_id
        }
        return [
            {
                "id": f"rt_{t['cluster_ref']}",
                "cluster_id": t["cluster_ref"],
                "diagnosis": t["diagnosis"],
                "title": t["title"],
                "detail": t.get("detail"),
                "status": t["status"],
                "rebaseline_required": t["rebaseline_required"],
                "origin": t["origin"],
            }
            for t in self.t("repair_tickets") if t["cluster_ref"] in in_round
        ]

    def fix_rates(self) -> list[Row]:
        """v_fix_rate: Beta(1, 1) prior plus the events, per intervention kind."""
        kinds = {iv["intervention_ref"]: iv["kind"] for iv in self.t("interventions")}
        grouped: dict[str, list[Row]] = {}
        for event in self.t("fix_rate_events"):
            kind = kinds.get(event.get("intervention_ref", ""))
            if kind:
                grouped.setdefault(kind, []).append(event)
        out = []
        for kind, events in grouped.items():
            n = sum(e["n_conditions"] for e in events)
            fixed = sum(e["fixed_count"] for e in events)
            out.append({
                "intervention_kind": kind, "event_count": len(events), "n_conditions": n,
                "fixed_count": fixed, "alpha": 1 + fixed, "beta": 1 + n - fixed,
                "mean_fix_rate": (1 + fixed) / (2 + n),
            })
        return out

    # ============================================================ M6

    def _evaluation_raw(self, eval_id: str, role: str) -> Row | None:
        ev = next((e for e in self.t("sim_evaluations") if e["evaluation_ref"] == eval_id), None)
        if ev is None or not self._can_see(ev, role):
            return None
        return ev

    def evaluations(self, role: str) -> list[Row]:
        return [
            self._evaluation_summary(ev) for ev in self.t("sim_evaluations")
            if self._can_see(ev, role)
        ]

    def evaluation(self, eval_id: str, role: str) -> Row | None:
        ev = self._evaluation_raw(eval_id, role)
        return self._evaluation_summary(ev) if ev else None

    def _evaluation_summary(self, ev: Row) -> Row:
        """v_eval_summary."""
        scored = ev["total_episodes"] - ev["infra_failed_count"]
        episodes = [
            e for e in self.t("eval_episodes")
            if e["evaluation_ref"] == ev["evaluation_ref"] and e["infra_status"] == "ok"
        ]
        sim_rate = js_round(ev["success_count"] / scored) if scored > 0 else None
        scorer_rate = (
            js_round(sum(1 for e in episodes if e.get("scorer_success") is True) / scored)
            if scored > 0 and episodes else None
        )
        ckpt = next(
            (c for c in self.t("model_checkpoints") if c["checkpoint_ref"] == ev["checkpoint_ref"]),
            None,
        )
        exp = next(
            (x for x in self.t("experiments")
             if ckpt is not None and x["experiment_code"] == ckpt["experiment_code"]),
            None,
        )
        names: list[str] = []
        for e in (episodes or self.t("eval_episodes")):
            step_names = (e.get("details") or {}).get("step_names")
            if step_names:
                names = step_names
                break
        return {
            "evaluation_id": ev["evaluation_ref"],
            "task_id": ev["task_id"],
            "checkpoint_id": ev["checkpoint_ref"],
            "branch": exp["branch"] if exp else None,
            "split": ev["split"],
            "level": ev.get("level"),
            "renderer": ev["renderer"],
            "eval_mode": ev["eval_mode"],
            "scorer_version": ev["scorer_version"],
            "total_episodes": ev["total_episodes"],
            "infra_failed_count": ev["infra_failed_count"],
            "success_count": ev["success_count"],
            "sim_success_rate": sim_rate,
            "scorer_success_rate": scorer_rate,
            "sim_scorer_gap": (
                js_round(abs(sim_rate - scorer_rate))
                if sim_rate is not None and scorer_rate is not None else None
            ),
            "step_names": names,
            "started_at": ev.get("started_at"),
            "finished_at": ev.get("finished_at"),
            "sealed_until": ev.get("sealed_until"),
            "is_sealed": self._sealed(ev),
            "origin": ev["origin"],
        }

    def eval_episodes(self, eval_id: str, role: str) -> list[Row] | None:
        if self._evaluation_raw(eval_id, role) is None:
            return None
        return [
            {
                "id": e["eval_episode_ref"],
                "evaluation_id": e["evaluation_ref"],
                "episode_index": e["episode_index"],
                "level": e["level"],
                "condition_id": e["condition_id"],
                "episode_seed": e["episode_seed"],
                "rollout_seed": e["rollout_seed"],
                "infra_status": e["infra_status"],
                "sim_success": e.get("sim_success"),
                "scorer_success": e.get("scorer_success"),
                "step_status": e["step_status"],
                "first_failed_step": e.get("first_failed_step"),
                "failure_code": e.get("failure_code"),
                "failure_class": e.get("failure_class"),
                "failure_time_s": e.get("failure_time_s"),
                "video_uri": e.get("video_uri"),
                "trajectory_log_uri": e.get("trajectory_log_uri"),
                "origin": e["origin"],
            }
            for e in self.t("eval_episodes") if e["evaluation_ref"] == eval_id
        ]

    def funnel(self, eval_id: str, role: str) -> list[Row] | None:
        """v_eval_funnel: infra-clean episodes, one row per (episode level, step)."""
        ev = self._evaluation_raw(eval_id, role)
        if ev is None:
            return None
        groups: dict[tuple[int, int], Row] = {}
        for e in self.t("eval_episodes"):
            if e["evaluation_ref"] != eval_id or e["infra_status"] != "ok":
                continue
            for index, status in enumerate(e["step_status"]):
                key = (e["level"], index + 1)
                row = groups.get(key)
                if row is None:
                    row = groups[key] = {
                        "evaluation_id": eval_id, "task_id": ev["task_id"], "split": ev["split"],
                        "eval_level": ev.get("level"), "renderer": ev["renderer"],
                        "eval_mode": ev["eval_mode"], "episode_level": e["level"],
                        "step_no": index + 1, "reached_or_beyond": 0, "step_pass": 0,
                        "step_fail": 0, "step_not_attempted": 0, "step_unknown": 0,
                        "is_sealed": self._sealed(ev), "origin": ev["origin"],
                    }
                row["reached_or_beyond"] += 1
                column = {
                    "pass": "step_pass", "fail": "step_fail",
                    "not_attempted": "step_not_attempted",
                }.get(status, "step_unknown")
                row[column] += 1
        return [groups[k] for k in sorted(groups)]

    def _system_check_row(self, s: Row) -> Row | None:
        """v_system_check."""
        e = next(
            (x for x in self.t("eval_episodes") if x["eval_episode_ref"] == s["eval_episode_ref"]),
            None,
        )
        ev = e and next(
            (x for x in self.t("sim_evaluations") if x["evaluation_ref"] == e["evaluation_ref"]),
            None,
        )
        if not e or not ev:
            return None
        return {
            "id": f"sd_{s['eval_episode_ref']}",
            "eval_episode_id": s["eval_episode_ref"],
            "evaluation_id": e["evaluation_ref"],
            "task_id": ev["task_id"],
            "episode_index": e["episode_index"],
            "level": e["level"],
            "diagnosis": s["diagnosis"],
            "config_sha256": s["config_sha256"],
            "trace_sha256": s["trace_sha256"],
            "infra_status": s["infra_status"],
            "fired_codes": sorted(f["code"] for f in s["findings"]),
            "skipped_codes": sorted(k["code"] for k in s["skipped"]),
            "finding_count": len(s["findings"]),
            "skipped_count": len(s["skipped"]),
            "findings": s["findings"],
            "skipped": s["skipped"],
            "measurements": s.get("measurements") or {},
            # Bản 0.5: dòng nạp trước PR #146 không có ba cột này; mặc định
            # là của hợp đồng, và timing None không bao giờ đọc là đồng bộ.
            "timing": s.get("timing"),
            "recorded": s.get("recorded") or [],
            "recorded_skipped": s.get("recorded_skipped") or [],
            "usable_as_policy_evidence": s["diagnosis"] == "clean",
            "is_sealed": self._sealed(ev),
            "origin": s["origin"],
        }

    def system_checks(self, eval_id: str, role: str) -> list[Row] | None:
        if self._evaluation_raw(eval_id, role) is None:
            return None
        refs = {
            e["eval_episode_ref"] for e in self.t("eval_episodes")
            if e["evaluation_ref"] == eval_id
        }
        return [
            row for s in self.t("system_diagnoses") if s["eval_episode_ref"] in refs
            if (row := self._system_check_row(s)) is not None
        ]

    def failures(self, eval_id: str, role: str) -> Row | None:
        """The five signal families of the failure table (design 27/10 §10)."""
        ev = self._evaluation_raw(eval_id, role)
        if ev is None:
            return None

        def counts(codes: Iterable[str]) -> list[Row]:
            tally: dict[str, int] = {}
            for code in codes:
                tally[code] = tally.get(code, 0) + 1
            return [{"code": c, "count": n, "detail": None} for c, n in sorted(tally.items())]

        def not_run(family: str) -> Row:
            return {"family": family, "status": "not_run", "rows": [], "skipped": []}

        ckpt = next(
            (c for c in self.t("model_checkpoints") if c["checkpoint_ref"] == ev["checkpoint_ref"]),
            None,
        )
        release_eps = {
            ri["episode_ref"] for ri in self.t("release_items")
            if ckpt is not None and ri["release_ref"] == ckpt.get("release_ref")
            and not ri["excluded"]
        }
        qa = [q for q in self.t("episode_qa_reports") if q["episode_ref"] in release_eps]
        f_data = not_run("F-DATA") if not qa else {
            "family": "F-DATA", "status": "ok", "skipped": [],
            "rows": counts(
                c["name"] for q in qa if q["decision"] != "pass"
                for c in q.get("checks") or [] if not c["passed"]
            ),
        }

        findings = [
            f for f in self.t("train_diagnoses") if f.get("checkpoint_ref") == ev["checkpoint_ref"]
        ]
        skips = [
            k for k in self.t("train_diagnosis_skips")
            if k.get("checkpoint_ref") == ev["checkpoint_ref"]
        ]
        ran = bool(findings or skips)

        def train_family(family: str, prefix: str) -> Row:
            if not ran:
                return not_run(family)
            return {
                "family": family, "status": "ok",
                "rows": counts(f["code"] for f in findings if f["code"].startswith(prefix)),
                "skipped": [
                    {"source": "train_diagnosis", "code": k["code"], "reason": k["reason"],
                     "eval_episode_id": None}
                    for k in skips if k["code"].startswith(prefix)
                ],
            }

        episodes = [
            e for e in self.t("eval_episodes")
            if e["evaluation_ref"] == eval_id and e["infra_status"] == "ok"
        ]
        f_cl = not_run("F-CL") if not episodes else {
            "family": "F-CL", "status": "ok", "skipped": [],
            "rows": counts(
                e["failure_code"] for e in episodes
                if e.get("sim_success") is False and e.get("failure_code")
            ),
        }
        sys_rows = self.system_checks(eval_id, role) or []
        f_sys = not_run("F-SYS") if not sys_rows else {
            "family": "F-SYS", "status": "ok",
            "rows": counts(code for s in sys_rows for code in s["fired_codes"]),
            "skipped": [
                {"source": "system_check", "code": k["code"], "reason": k["reason"],
                 "eval_episode_id": s["eval_episode_id"]}
                for s in sys_rows for k in s["skipped"]
            ],
        }
        return {
            "evaluation_id": eval_id,
            "families": [
                f_data, train_family("F-TRAIN", "T"), train_family("F-OFF", "O"), f_cl, f_sys,
            ],
        }

    # ============================================================ M2

    def datasets(self) -> list[Row]:
        return [
            {
                "id": d["dataset_code"],
                "dataset_code": d["dataset_code"],
                "source_id": d.get("source_ref"),
                "source_kind": d["source_kind"],
                "source_detail": d.get("source_detail"),
                "data_class": d["data_class"],
                "license": d["license"],
                "episode_count": d["episode_count"],
                "has_seeded_faults": d["has_seeded_faults"],
                "status": d["status"],
                "note": d.get("note"),
                "origin": d["origin"],
            }
            for d in self.t("datasets")
        ]

    def dataset(self, dataset_id: str) -> Row | None:
        return next((d for d in self.datasets() if d["id"] == dataset_id), None)

    def stages(self, dataset_id: str) -> Row | None:
        """v_pipeline_current plus every attempt."""
        if self.dataset(dataset_id) is None:
            return None
        attempts = sorted(
            (
                {
                    "id": f"{r['dataset_code']}:{r['stage_number']}:{r['attempt_no']}",
                    "dataset_id": r["dataset_code"],
                    "stage_number": r["stage_number"],
                    "attempt_no": r["attempt_no"],
                    "is_current": r["is_current"],
                    "status": r["status"],
                    "qa_code_decision": r.get("qa_code_decision"),
                    "qa_agent_verdict": r.get("qa_agent_verdict"),
                    "started_at": r.get("started_at"),
                    "finished_at": r.get("finished_at"),
                    "log_uri": r.get("log_uri"),
                    "origin": r["origin"],
                }
                for r in self.t("pipeline_stage_runs") if r["dataset_code"] == dataset_id
            ),
            key=lambda a: (a["stage_number"], a["attempt_no"]),
        )
        stages = []
        for index, code in enumerate(PIPELINE_STAGE):
            current = next(
                (a for a in attempts if a["stage_number"] == index + 1 and a["is_current"]), None
            )
            stages.append({
                "dataset_id": dataset_id,
                "stage_number": index + 1,
                "stage_code": code,
                "stage_run_id": current["id"] if current else None,
                "attempt_no": current["attempt_no"] if current else None,
                "status": current["status"] if current else None,
                "qa_code_decision": current["qa_code_decision"] if current else None,
                "qa_agent_verdict": current["qa_agent_verdict"] if current else None,
                "started_at": current["started_at"] if current else None,
                "finished_at": current["finished_at"] if current else None,
                "log_uri": current["log_uri"] if current else None,
                "origin": current["origin"] if current else None,
            })
        return {"stages": stages, "attempts": attempts}

    def _dataset_episodes(self, dataset_id: str) -> list[Row] | None:
        if self.dataset(dataset_id) is None:
            return None
        return [e for e in self.t("episodes") if e.get("dataset_code") == dataset_id]

    def _latest_qa(self) -> dict[str, Row]:
        # Append-only table, oldest first: the last row of an episode is its latest verdict.
        return {q["episode_ref"]: q for q in self.t("episode_qa_reports")}

    def episodes(self, dataset_id: str) -> list[Row] | None:
        eps = self._dataset_episodes(dataset_id)
        if eps is None:
            return None
        qa = self._latest_qa()
        return [
            {
                "id": e["episode_ref"],
                "dataset_id": dataset_id,
                "source_kind": e["source_kind"],
                "kind": e["kind"],
                "split": e["split"],
                "deid_status": e["deid_status"],
                "data_class": e["data_class"],
                "operator_kind": e["operator_kind"],
                "is_root": e["is_root"],
                "action_quality": e["action_quality"],
                "qa_decision": qa[e["episode_ref"]]["decision"] if e["episode_ref"] in qa else None,
                "qa_reasons": qa[e["episode_ref"]].get("reasons") or [] if e["episode_ref"] in qa
                else [],
                "origin": e["origin"],
            }
            for e in eps
        ]

    def report(self, dataset_id: str) -> Row | None:
        """v_dataset_report plus the per-check breakdown."""
        eps = self._dataset_episodes(dataset_id)
        if eps is None:
            return None
        qa = self._latest_qa()
        groups: dict[tuple[str, str | None], Row] = {}
        for e in eps:
            tier = e.get("synthetic_tier")
            row = groups.get((e["source_kind"], tier))
            if row is None:
                row = groups[(e["source_kind"], tier)] = {
                    "dataset_id": dataset_id, "source_kind": e["source_kind"],
                    "synthetic_tier": tier, "episode_count": 0, "root_human_count": 0,
                    "qa_pass": 0, "qa_flag": 0, "qa_quarantine": 0, "qa_reject": 0,
                    "qa_not_run": 0, "egocentric_raw": 0, "mean_duration_s": None,
                    "origin": e["origin"],
                }
            row["episode_count"] += 1
            if e["is_root"] and e["operator_kind"] == "human":
                row["root_human_count"] += 1
            if e["source_kind"] == "egocentric" and e["deid_status"] == "raw":
                row["egocentric_raw"] += 1
            decision = qa[e["episode_ref"]]["decision"] if e["episode_ref"] in qa else None
            column = {
                "pass": "qa_pass", "flag": "qa_flag", "quarantine": "qa_quarantine",
                "reject": "qa_reject",
            }.get(decision or "", "qa_not_run")
            row[column] += 1
        checks: dict[str, Row] = {}
        for e in eps:
            for c in (qa.get(e["episode_ref"]) or {}).get("checks") or []:
                entry = checks.setdefault(c["name"], {"name": c["name"], "passed": 0, "failed": 0})
                entry["passed" if c["passed"] else "failed"] += 1
        return {"rows": list(groups.values()), "by_check": list(checks.values())}

    def intakes(self) -> list[Row]:
        # `dataset_intakes` is a W table written by the API; none exists yet in sink mode.
        return []

    # ============================================================ M9

    def _best_checkpoint(self, experiment_code: str) -> Row | None:
        return next(
            (c for c in self.t("model_checkpoints")
             if c["experiment_code"] == experiment_code and c["is_best"]),
            None,
        )

    def branches(self, task_id: str) -> list[Row]:
        """v_branch_comparison: latest unsealed dev eval of each branch's best checkpoint."""
        rows = []
        for x in self.t("experiments"):
            # HE points share one branch; they have their own view (v_he_curve).
            if x["task_id"] != task_id or x["hypothesis"] in ("HE", "HE_T"):
                continue
            ckpt = self._best_checkpoint(x["experiment_code"])
            if ckpt is None:
                continue
            evs = sorted(
                (ev for ev in self.t("sim_evaluations")
                 if ev["checkpoint_ref"] == ckpt["checkpoint_ref"] and ev["split"] == "dev"
                 and not self._sealed(ev)),
                key=lambda ev: ev.get("finished_at") or "",
                reverse=True,
            )
            if not evs:
                continue
            ev = evs[0]
            ledger = [
                e for e in self.t("cost_ledger_entries")
                if e.get("experiment_code") == x["experiment_code"]
            ]
            scored = ev["total_episodes"] - ev["infra_failed_count"]
            rows.append({
                "task_id": x["task_id"], "branch": x["branch"], "method": x["method"],
                "experiment_id": x["experiment_code"], "evaluation_id": ev["evaluation_ref"],
                "level": ev.get("level"),
                "sim_success_rate": js_round(ev["success_count"] / scored) if scored > 0 else None,
                "total_episodes": ev["total_episodes"],
                "infra_failed_count": ev["infra_failed_count"],
                "measured_usd": _sum_or_none(e.get("measured_usd") for e in ledger),
                "measured_human_minutes": _sum_or_none(
                    e.get("measured_human_minutes") for e in ledger
                ),
                "measured_gpu_hours": _sum_or_none(e.get("measured_gpu_hours") for e in ledger),
                "estimated_usd": _sum_or_none(e.get("estimated_usd") for e in ledger),
                "origin": x["origin"],
            })
        return rows

    def _human_root_episodes(self, experiment_code: str) -> set[str]:
        releases = {
            ed["release_ref"] for ed in self.t("experiment_datasets")
            if ed["experiment_code"] == experiment_code
        }
        roots = {
            e["episode_ref"] for e in self.t("episodes")
            if e["is_root"] and e["operator_kind"] == "human"
        }
        return {
            ri["episode_ref"] for ri in self.t("release_items")
            if ri["release_ref"] in releases and not ri["excluded"] and ri["episode_ref"] in roots
        }

    def he_curve(self, role: str) -> list[Row]:
        """v_he_curve."""
        points = []
        for x in self.t("experiments"):
            if x["hypothesis"] not in ("HE", "HE_T"):
                continue
            ckpt = self._best_checkpoint(x["experiment_code"])
            if ckpt is None:
                continue
            for ev in self.t("sim_evaluations"):
                if ev["checkpoint_ref"] != ckpt["checkpoint_ref"] or not self._can_see(ev, role):
                    continue
                scored = ev["total_episodes"] - ev["infra_failed_count"]
                points.append({
                    "task_id": x["task_id"], "branch": x["branch"], "hypothesis": x["hypothesis"],
                    "he_variant": (x.get("hyperparams") or {}).get("he_variant"),
                    "n_demos": len(self._human_root_episodes(x["experiment_code"])),
                    "train_seed": x.get("train_seed"), "level": ev.get("level"),
                    "sim_success_rate": (
                        js_round(ev["success_count"] / scored) if scored > 0 else None
                    ),
                    "n_scored": scored, "is_sealed": self._sealed(ev), "origin": ev["origin"],
                })
        return points

    def e1_curve(self) -> list[Row]:
        # No E1 run exists yet; an empty list renders EmptyState, never a 0% curve.
        return []

    # ============================================================ M8

    def ledger(self) -> list[Row]:
        return [
            {
                "id": e["entry_ref"],
                "entry_kind": e["entry_kind"],
                "activity": e["activity"],
                "resource_type": e["resource_type"],
                "quantity": e["quantity"],
                "unit": e["unit"],
                "price_book_name": e.get("price_book_name"),
                "branch": e.get("branch"),
                "experiment_id": e.get("experiment_code"),
                "evaluation_id": e.get("evaluation_ref"),
                "dataset_id": e.get("dataset_code"),
                "recommendation_id": e.get("recommendation_ref"),
                "cluster_id": e.get("cluster_ref"),
                "intervention_id": e.get("intervention_ref"),
                "estimated_usd": e.get("estimated_usd"),
                "estimated_human_minutes": e.get("estimated_human_minutes"),
                "estimated_gpu_hours": e.get("estimated_gpu_hours"),
                "measured_usd": e.get("measured_usd"),
                "measured_human_minutes": e.get("measured_human_minutes"),
                "measured_gpu_hours": e.get("measured_gpu_hours"),
                "reverses_entry_id": e.get("reverses_entry_ref"),
                "note": e.get("note"),
                "origin": e["origin"],
            }
            for e in self.t("cost_ledger_entries")
        ]

    def _ledger_task(self, entry: Row) -> str | None:
        """v_cost_by_branch: task from the experiment, else the evaluation, else the round."""
        code = entry.get("experiment_code")
        if code:
            x = next((x for x in self.t("experiments") if x["experiment_code"] == code), None)
            if x:
                return str(x["task_id"])
        ev_ref = entry.get("evaluation_ref")
        if ev_ref:
            ev = next((v for v in self.t("sim_evaluations") if v["evaluation_ref"] == ev_ref),
                      None)
            if ev:
                return str(ev["task_id"])
        rec_ref = entry.get("recommendation_ref")
        if rec_ref:
            rec = self._rec(rec_ref)
            if rec:
                return str(rec["task_id"])
        return None

    def cost_by_branch(self) -> Row:
        """v_cost_by_branch, v_r_demo and v_cost_data_allocation (BR-05)."""
        groups: dict[tuple[Any, Any, Any], list[Row]] = {}
        for e in self.t("cost_ledger_entries"):
            key = (e.get("branch"), self._ledger_task(e), e.get("price_book_name"))
            groups.setdefault(key, []).append(e)
        rows = []
        for (branch, task, book), entries in groups.items():
            # Forecast error only on rows carrying both an estimate and a measurement.
            paired = [e for e in entries
                      if e.get("measured_usd") is not None and e.get("estimated_usd") is not None]
            rows.append({
                "branch": branch, "task_id": task, "price_book_name": book,
                "entry_count": len(entries),
                "estimated_usd": _sum_or_none(e.get("estimated_usd") for e in entries),
                "measured_usd": _sum_or_none(e.get("measured_usd") for e in entries),
                "usd_forecast_error": _sum_or_none(
                    e["measured_usd"] - e["estimated_usd"] for e in paired
                ),
                "forecast_pairs": len(paired),
                "estimated_human_minutes": _sum_or_none(
                    e.get("estimated_human_minutes") for e in entries
                ),
                "measured_human_minutes": _sum_or_none(
                    e.get("measured_human_minutes") for e in entries
                ),
                "estimated_gpu_hours": _sum_or_none(e.get("estimated_gpu_hours") for e in entries),
                "measured_gpu_hours": _sum_or_none(e.get("measured_gpu_hours") for e in entries),
                "reversal_count": sum(1 for e in entries if e["entry_kind"] == "REVERSAL"),
                "origin": entries[0]["origin"],
            })
        # v_r_demo: one row per (task, branch, method); HE points live in v_he_curve.
        demo_groups: dict[tuple[str, str, str], tuple[set[str], str]] = {}
        for x in self.t("experiments"):
            if x["hypothesis"] in ("HE", "HE_T"):
                continue
            demo_key = (x["task_id"], x["branch"], x["method"])
            seen, origin = demo_groups.get(demo_key, (set(), x["origin"]))
            demo_groups[demo_key] = (
                seen | self._human_root_episodes(x["experiment_code"]), origin
            )
        r_demo = [
            {"task_id": t, "branch": b, "method": m, "human_root_episodes": len(seen),
             "origin": origin}
            for (t, b, m), (seen, origin) in demo_groups.items() if seen
        ]
        return {"rows": rows, "r_demo": r_demo, "data_allocation": self._data_allocation()}

    def _data_allocation(self) -> list[Row]:
        """v_cost_data_allocation: each dataset's measured cost, shared by episodes used."""
        cost: dict[str, dict[str, float | None]] = {}
        for e in self.t("cost_ledger_entries"):
            code = e.get("dataset_code")
            if not code:
                continue
            c = cost.setdefault(code, {"usd": None, "human_minutes": None, "gpu_hours": None})
            for k in ("usd", "human_minutes", "gpu_hours"):
                v = e.get(f"measured_{k}")
                if v is not None:
                    c[k] = (c[k] or 0) + v
        dataset_of = {e["episode_ref"]: e.get("dataset_code") for e in self.t("episodes")}
        datasets = {d["dataset_code"]: d for d in self.t("datasets")}
        out = []
        for x in self.t("experiments"):
            releases = {
                ed["release_ref"] for ed in self.t("experiment_datasets")
                if ed["experiment_code"] == x["experiment_code"]
            }
            used: dict[str, set[str]] = {}
            for ri in self.t("release_items"):
                if ri["release_ref"] in releases and not ri["excluded"]:
                    code = dataset_of.get(ri["episode_ref"])
                    if code:
                        used.setdefault(code, set()).add(ri["episode_ref"])
            for d in self.t("datasets"):
                code = d["dataset_code"]
                if code not in used:
                    continue
                n, total = len(used[code]), datasets[code]["episode_count"]
                c = cost.get(code, {"usd": None, "human_minutes": None, "gpu_hours": None})

                def part(v: float | None, n: int = n, total: int = total) -> float | None:
                    return v * n / total if v is not None and total else None

                out.append({
                    "experiment_id": x["experiment_code"], "task_id": x["task_id"],
                    "branch": x["branch"], "method": x["method"], "hypothesis": x["hypothesis"],
                    "dataset_id": code, "episodes_used": n, "dataset_episodes": total,
                    "share": n / total if total else None,
                    "allocated_usd": part(c["usd"]),
                    "allocated_human_minutes": part(c["human_minutes"]),
                    "allocated_gpu_hours": part(c["gpu_hours"]),
                    "origin": x["origin"],
                })
        return out

    def cost_by_intervention(self) -> list[Row]:
        rec = self._rec_row()
        if rec is None:
            return []
        full = self.recommendation(rec["recommendation_ref"])
        return full["interventions"] if full else []

    def sensitivity(self, price_book: str | None) -> list[Row]:
        """The ledger repriced under each price book (linear: scale by the rate ratio)."""
        books = {b["name"]: b for b in self.t("price_books")}
        out = []
        for book in self.t("price_books"):
            if price_book is not None and book["name"] != price_book:
                continue
            by_branch: dict[str | None, float] = {}
            for e in self.t("cost_ledger_entries"):
                base = books.get(e.get("price_book_name") or "")
                usd = e.get("measured_usd")
                if usd is None:
                    usd = e.get("estimated_usd")
                usd = usd or 0
                base_rate = (base or {}).get("rates", {}).get(e["resource_type"], {}).get(
                    "usd_per_unit"
                )
                new_rate = book["rates"].get(e["resource_type"], {}).get("usd_per_unit")
                repriced = usd * new_rate / base_rate if base_rate and new_rate is not None else usd
                branch = e.get("branch")
                by_branch[branch] = by_branch.get(branch, 0) + repriced
            rounded = [(b, js_round(v, 2)) for b, v in by_branch.items()]
            by: list[Row] = [{"branch": b, "usd": usd} for b, usd in rounded]
            out.append({
                "price_book_name": book["name"],
                "sha256": book["sha256"],
                "note": book.get("note"),
                "rates": book["rates"],
                "by_branch": by,
                "total_usd": js_round(sum(usd for _, usd in rounded), 2),
            })
        return out

    # ============================================================ M3

    def _latest_bench(self) -> str | None:
        """`result_sha256` of the newest bench run (v_defect_detection.is_latest)."""
        groups = self.t("defect_bench_groups")
        if not groups:
            return None
        newest = max(groups, key=lambda g: (_parse_ts(g["created_at"]), g["result_sha256"]))
        return str(newest["result_sha256"])

    def defect_scores(self) -> list[Row]:
        """v_defect_detection: every rate of every bench run, `value` computed here."""
        latest = self._latest_bench()
        groups = {(g["result_sha256"], g["group_name"]): g for g in self.t("defect_bench_groups")}
        out = []
        for s in self.t("defect_scores"):
            g = groups.get((s["result_sha256"], s["group_name"]))
            if g is None:
                continue
            out.append({
                "result_sha256": s["result_sha256"], "bench_version": g["bench_version"],
                "group_name": s["group_name"], "injected_copy": g["injected_copy"],
                "clean_copy": g["clean_copy"], "layer": s["layer"], "metric": s["metric"],
                "subject": s["subject"], "hit": s["hit"], "total": s["total"],
                "value": _ratio(s["hit"], s["total"]), "masked": s.get("masked"),
                "bound": s.get("bound"), "created_at": s["created_at"],
                "is_latest": s["result_sha256"] == latest, "origin": s["origin"],
            })
        return out

    def defect_scoreboard(self) -> Row:
        """M3: the newest bench run, one block per group, code and agent side by side."""
        latest = self._latest_bench()
        groups = sorted(
            (g for g in self.t("defect_bench_groups") if g["result_sha256"] == latest),
            key=lambda g: str(g["group_name"]),
        )
        rates: dict[tuple[str, str, str, str], Row] = {}
        for s in self.t("defect_scores"):
            if s["result_sha256"] == latest:
                rates[(s["group_name"], s["layer"], s["metric"], s["subject"])] = s
        blocks = [_bench_block(g, rates) for g in groups]
        head = groups[0] if groups else None
        return {
            "result_sha256": latest,
            "bench_version": head["bench_version"] if head else None,
            "created_at": head["created_at"] if head else None,
            "measured_on": head["measured_on"] if head else None,
            "false_alarm_note": head["false_alarm_note"] if head else None,
            "totals": _bench_totals([b["totals"] for b in blocks]),
            "groups": blocks,
            "origin": head["origin"] if head else None,
        }


BENCH_LAYERS = ("code", "agent")


def _ratio(hit: int, total: int) -> float | None:
    return hit / total if total else None


def _bench_rate(row: Row | None) -> Row:
    """`{hit, total, value}`; a rate the bench did not write is 0 of 0, value null."""
    hit, total = (row["hit"], row["total"]) if row else (0, 0)
    return {"hit": hit, "total": total, "value": _ratio(hit, total)}


def _bench_totals(parts: Iterable[Row]) -> Row:
    keys = ("injected", "by_code", "agent_adds", "together")
    rows = list(parts)
    return {k: sum(int(p[k]) for p in rows) for k in keys}


def _bench_block(g: Row, rates: dict[tuple[str, str, str, str], Row]) -> Row:
    name = g["group_name"]

    def both(metric: str, subject: str) -> Row:
        return {layer: _bench_rate(rates.get((name, layer, metric, subject)))
                for layer in BENCH_LAYERS}

    kinds = []
    for s in g["split"]:
        masked = {
            layer: int((rates.get((name, layer, "recall", s["kind"])) or {}).get("masked") or 0)
            for layer in BENCH_LAYERS
        }
        kinds.append({
            "kind": s["kind"], "code": s["code"], "injected": s["injected"],
            "by_code": s["by_code"], "agent_adds": s["agent_adds"], "together": s["together"],
            "agent_alone": s["agent_alone"], "masked": masked,
            "recall": both("recall", s["kind"]),
            "recall_unmasked": both("recall_unmasked", s["kind"]),
        })
    codes = sorted({subject for (n, _, metric, subject) in rates
                    if n == name and metric == "precision"})
    return {
        "group_name": name,
        "injected_copy": g["injected_copy"],
        "clean_copy": g["clean_copy"],
        "defects": g["defects"],
        "totals": _bench_totals(kinds),
        "kinds": kinds,
        "codes": [{"code": c, "precision": both("precision", c)} for c in codes],
        "false_alarm": both("false_alarm", "*"),
        "seconds_to_report": g["seconds_to_report"],
        "clean_reports": g["clean_reports"],
        "natural": g["natural"],
        "not_a_unit": g["not_a_unit"],
        "agent_ranking": _bench_rate(
            {"hit": g["agent_ranking_hit"], "total": g["agent_ranking_total"]}),
        "agent_reviews": g["agent_reviews"],
        "agent_findings": g["agent_findings"],
    }


@dataclass
class PostgresReadModel:
    """Reads the views of 70-views.sql. Not built until Postgres exists (§9.3, W8)."""

    dsn: str

    def __post_init__(self) -> None:
        raise RuntimeError(
            "PostgresReadModel cần ba thứ chưa có: PostgreSQL 16 (DESIGN.md §9.3), "
            "`psycopg` trong workspace, và quyết định W8 (ADR-13). "
            "Tới lúc đó chạy API với `--sink <thư mục JSONL của fwsync>`."
        )
