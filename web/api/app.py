"""The web API (DESIGN.md §7): every read endpoint of §7.1 and the two writes M7 uses.

Routes are thin: validate, call the `ReadModel`, shape errors. They hold no
view logic, so swapping `SinkReadModel` for `PostgresReadModel` changes no route.

Conventions of §7.3 kept here:
* every path lives under ``/api``;
* one error shape ``{code, message, hint, ref}``;
* list pages are ``{items, next_cursor, total}``;
* writes answer 202 ``{action_id, sync_status}`` and need ``Idempotency-Key``;
* sealed evaluations are hidden from every role but ADMIN (BR-10). Until
  sessions exist the role comes from the ``X-Fw-Role`` header (§7.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from web.api.actions import ActionStore
from web.api.readmodel import ReadModel
from web.contracts.enums import ALL
from web.fwsync import actions as action_log
from web.fwsync.runner import run_cycle
from web.fwsync.sink import JsonlSink

API_PREFIX = "/api"
DEFAULT_ROLE = "ML_ENGINEER"
USER_ROLES = ALL["user_role"]
CLUSTER_DIAGNOSES = ALL["cluster_diagnosis"]
INTERVENTION_DECISIONS = ALL["intervention_decision"]
SYNC_STATUSES = ALL["sync_status"]
#: §7.2: `POST /sync/run` is for ADMIN and LEAD only.
SYNC_ROLES = ("ADMIN", "LEAD")


@dataclass(frozen=True)
class SyncConfig:
    """Where one sync pass reads and writes in sink mode (`POST /sync/run`)."""

    outbox: Path
    inbox: Path
    sink: Path
    fake_core: bool
    origin: str = "core"


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.hint = status, code, message, hint


def _not_found(what: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{what} không tồn tại hoặc bạn không được xem")


def _found(value: Any, what: str) -> Any:
    if value is None:
        raise _not_found(what)
    return value


def _role(x_fw_role: str | None) -> str:
    return x_fw_role if x_fw_role in USER_ROLES else DEFAULT_ROLE


def _page(items: list[Any], cursor: str | None, limit: int | None) -> dict[str, Any]:
    size = min(limit or 100, 500)
    try:
        offset = int(cursor or 0)
    except ValueError:
        offset = 0
    nxt = str(offset + size) if offset + size < len(items) else None
    return {"items": items[offset:offset + size], "next_cursor": nxt, "total": len(items)}


def _require_key(key: str | None) -> str:
    if not key:
        raise ApiError(400, "IDEMPOTENCY_KEY_REQUIRED", "thiếu header Idempotency-Key (§7.3)")
    return key


def create_app(
    model: ReadModel, actions: ActionStore, sync: SyncConfig | None = None
) -> FastAPI:
    app = FastAPI(
        title="Humanoid Data Flywheel · web API",
        version="0.4.0",
        description="DESIGN.md §7. Hình dạng response: web/fe/src/api/types.ts.",
    )

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, error: ApiError) -> JSONResponse:
        body = {"code": error.code, "message": error.message, "hint": error.hint, "ref": None}
        return JSONResponse(body, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, error: RequestValidationError) -> JSONResponse:
        body = {"code": "BAD_REQUEST", "message": str(error.errors()[:1]), "hint": None,
                "ref": None}
        return JSONResponse(body, status_code=422)

    r = APIRouter(prefix=API_PREFIX)
    Role = Header(default=None, alias="X-Fw-Role")
    Key = Header(default=None, alias="Idempotency-Key")

    # ------------------------------------------------------------ M7
    @r.get("/recommendations")
    def recommendations() -> Any:
        return model.recommendations()

    @r.get("/recommendations/{rec_id}")
    def recommendation(rec_id: str) -> Any:
        return _found(model.recommendation(rec_id), "đề xuất")

    @r.get("/recommendations/{rec_id}/steps")
    def steps(rec_id: str) -> Any:
        return model.steps(rec_id)

    @r.get("/recommendations/{rec_id}/clusters")
    def clusters(rec_id: str) -> Any:
        return model.clusters(rec_id)

    @r.get("/clusters/{cluster_id}/card")
    def card(cluster_id: str) -> Any:
        return _found(model.card(cluster_id), "cụm")

    @r.get("/repair-tickets")
    def repair_tickets(recommendation_id: str | None = None) -> Any:
        return model.repair_tickets(recommendation_id)

    @r.get("/fix-rates")
    def fix_rates() -> Any:
        return model.fix_rates()

    # ------------------------------------------------------------ M6
    @r.get("/evaluations")
    def evaluations(cursor: str | None = None, limit: int | None = None,
                    x_fw_role: str | None = Role) -> Any:
        return _page(model.evaluations(_role(x_fw_role)), cursor, limit)

    @r.get("/evaluations/{eval_id}")
    def evaluation(eval_id: str, x_fw_role: str | None = Role) -> Any:
        return _found(model.evaluation(eval_id, _role(x_fw_role)), "lượt eval")

    @r.get("/evaluations/{eval_id}/episodes")
    def eval_episodes(eval_id: str, cursor: str | None = None, limit: int | None = None,
                      x_fw_role: str | None = Role) -> Any:
        rows = _found(model.eval_episodes(eval_id, _role(x_fw_role)), "lượt eval")
        return _page(rows, cursor, limit)

    @r.get("/evaluations/{eval_id}/funnel")
    def funnel(eval_id: str, x_fw_role: str | None = Role) -> Any:
        return _found(model.funnel(eval_id, _role(x_fw_role)), "lượt eval")

    @r.get("/evaluations/{eval_id}/failures")
    def failures(eval_id: str, x_fw_role: str | None = Role) -> Any:
        return _found(model.failures(eval_id, _role(x_fw_role)), "lượt eval")

    @r.get("/evaluations/{eval_id}/system-checks")
    def system_checks(eval_id: str, x_fw_role: str | None = Role) -> Any:
        return _found(model.system_checks(eval_id, _role(x_fw_role)), "lượt eval")

    # ------------------------------------------------------------ M2
    @r.get("/datasets")
    def datasets(cursor: str | None = None, limit: int | None = None) -> Any:
        return _page(model.datasets(), cursor, limit)

    @r.get("/datasets/{dataset_id}")
    def dataset(dataset_id: str) -> Any:
        return _found(model.dataset(dataset_id), "lô")

    @r.get("/datasets/{dataset_id}/stages")
    def stages(dataset_id: str) -> Any:
        return _found(model.stages(dataset_id), "lô")

    @r.get("/datasets/{dataset_id}/episodes")
    def episodes(dataset_id: str, cursor: str | None = None, limit: int | None = None) -> Any:
        return _page(_found(model.episodes(dataset_id), "lô"), cursor, limit)

    @r.get("/datasets/{dataset_id}/report")
    def report(dataset_id: str) -> Any:
        return _found(model.report(dataset_id), "lô")

    @r.get("/intakes")
    def intakes(cursor: str | None = None, limit: int | None = None) -> Any:
        return _page(model.intakes(), cursor, limit)

    # ------------------------------------------------------------ M9
    @r.get("/results/branches")
    def branches(task_id: str | None = None) -> Any:
        if not task_id:
            raise ApiError(400, "TASK_REQUIRED", "nhánh luôn đi kèm task_id (§6.4)")
        return model.branches(task_id)

    @r.get("/results/he-curve")
    def he_curve(x_fw_role: str | None = Role) -> Any:
        return model.he_curve(_role(x_fw_role))

    @r.get("/results/e1-curve")
    def e1_curve() -> Any:
        return model.e1_curve()

    # ------------------------------------------------------------ M8
    @r.get("/cost/ledger")
    def ledger(cursor: str | None = None, limit: int | None = None) -> Any:
        return _page(model.ledger(), cursor, limit)

    @r.get("/cost/by-branch")
    def cost_by_branch() -> Any:
        return model.cost_by_branch()

    @r.get("/cost/by-intervention")
    def cost_by_intervention() -> Any:
        return model.cost_by_intervention()

    @r.get("/cost/sensitivity")
    def sensitivity(price_book: str | None = None) -> Any:
        return model.sensitivity(price_book)

    # ------------------------------------------------------------ actions
    @r.get("/actions")
    def action_list(sync_status: str | None = None, cursor: str | None = None,
                    limit: int | None = None) -> Any:
        if sync_status is not None and sync_status not in SYNC_STATUSES:
            raise ApiError(422, "BAD_SYNC_STATUS", f"sync_status {sync_status} không hợp lệ")
        return _page(actions.list_actions(sync_status), cursor, limit)

    @r.get("/actions/{action_id}")
    def action(action_id: str) -> Any:
        return _found(actions.status(action_id), "hành động")

    @r.get("/decisions")
    def decisions(cursor: str | None = None, limit: int | None = None) -> Any:
        return _page(model.decisions(), cursor, limit)

    @r.get("/sync/runs")
    def sync_runs() -> Any:
        return actions.runs()

    @r.post("/sync/run")
    def sync_run(x_fw_role: str | None = Role) -> Any:
        """One pass of §5.5 in sink mode: export → (fake core) → import → APPLIED."""
        if _role(x_fw_role) not in SYNC_ROLES:
            raise ApiError(403, "ROLE", "chỉ ADMIN và LEAD được chạy đồng bộ (§7.2)")
        if sync is None:
            raise ApiError(409, "SYNC_NOT_CONFIGURED", "API chạy không kèm thư mục đồng bộ",
                           "khởi động lại với --outbox và --inbox")
        started = action_log.now_iso()
        result = run_cycle(actions.path, sync.outbox, sync.inbox,
                           JsonlSink(directory=sync.sink), fake_core=sync.fake_core,
                           origin=sync.origin)
        model.refresh()
        return actions.add_run({
            "id": f"sync_{len(actions.runs()) + 1:04d}",
            "direction": "cycle",
            "status": result.status,
            "started_at": started,
            "finished_at": action_log.now_iso(),
            "exported": result.exported,
            "applied": result.applied,
            "fake_core": sync.fake_core,
            "errors": [
                *result.export.errors,
                *(result.fake_core.errors if result.fake_core else []),
                *(result.imported.errors if result.imported else []),
            ],
        })

    @r.post("/recommendations/{rec_id}/decision", status_code=202)
    def decide(rec_id: str, body: dict[str, Any], idempotency_key: str | None = Key) -> Any:
        key = _require_key(idempotency_key)
        rec = _found(model.recommendation(rec_id), "đề xuất")
        items = body.get("items") or []
        known = {iv["id"]: iv for iv in rec["interventions"]}
        for item in items:
            if item.get("intervention_id") not in known:
                raise ApiError(422, "UNKNOWN_INTERVENTION",
                               f"can thiệp {item.get('intervention_id')} không thuộc đề xuất này")
            if item.get("decision") not in INTERVENTION_DECISIONS:
                raise ApiError(422, "BAD_DECISION",
                               f"quyết định {item.get('decision')} không hợp lệ")
            if item["decision"] != "APPROVE" and not str(item.get("reason") or "").strip():
                raise ApiError(422, "REASON_REQUIRED", "duyệt có sửa và từ chối phải ghi lý do")
            if item["decision"] == "APPROVE_EDITED" and not (
                isinstance(item.get("approved_quantity"), (int, float))
                and item["approved_quantity"] > 0
            ):
                raise ApiError(422, "QUANTITY_REQUIRED", "duyệt có sửa phải có số lượng > 0")
        # BR-07: approval may not push any of the three ceilings below zero.
        approved = {"usd": 0.0, "human_minutes": 0.0, "gpu_hours": 0.0}
        for item in items:
            if item["decision"] == "REJECT":
                continue
            iv = known[item["intervention_id"]]
            quantity = (item["approved_quantity"] if item["decision"] == "APPROVE_EDITED"
                        else iv["target_quantity"])
            factor = quantity / iv["target_quantity"]
            approved["usd"] += iv["estimated_usd"] * factor
            approved["human_minutes"] += iv["estimated_human_minutes"] * factor
            approved["gpu_hours"] += iv["estimated_gpu_hours"] * factor
        for line in rec["budget"]:
            if line["used"] + approved[line["resource"]] > line["cap"] + 1e-9:
                raise ApiError(422, "BR-07", f"vượt trần {line['resource']}",
                               "giảm số lượng hoặc từ chối bớt can thiệp")
        row = actions.record(key, "RECOMMENDATION_DECISION", "flywheel_recommendations",
                             rec_id, {"items": items}, None)
        return {"action_id": row["id"], "sync_status": row["sync_status"]}

    @r.post("/clusters/{cluster_id}/diagnosis-override", status_code=202)
    def override(cluster_id: str, body: dict[str, Any],
                 idempotency_key: str | None = Key) -> Any:
        key = _require_key(idempotency_key)
        _found(model.card(cluster_id), "cụm")
        diagnosis = body.get("diagnosis")
        if diagnosis not in CLUSTER_DIAGNOSES:
            raise ApiError(422, "BAD_DIAGNOSIS", "chẩn đoán không thuộc 11 giá trị của spec §6.9")
        reason = str(body.get("reason") or "").strip()
        if not reason:
            raise ApiError(422, "REASON_REQUIRED", "ghi đè chẩn đoán bắt buộc ghi lý do")
        row = actions.record(key, "DIAGNOSIS_OVERRIDE", "failure_clusters", cluster_id,
                             {"diagnosis": diagnosis}, reason)
        return {"action_id": row["id"], "sync_status": row["sync_status"]}

    app.include_router(r)
    return app
