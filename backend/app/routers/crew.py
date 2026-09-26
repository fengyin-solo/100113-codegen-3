"""船员换班接口：按所属船舶管理换班计划、随船人员与登离船台账。

账号通过请求体里的 account_id 传入；越权提交由服务层说明原因，这里统一转成 403 拒绝。
所有列表接口只读开放，提交与确认才校验归属。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, PageResult
from app.services.crew import PermissionDenied, _is_expired
from app.services.crew import CrewService

router = APIRouter(prefix="/api/crew", tags=["船员换班"])

service = CrewService()


def _denied(exc: PermissionDenied) -> HTTPException:
    # 越权提交要说明原因后拒绝
    return HTTPException(status_code=403, detail=str(exc))


@router.get("/accounts")
def list_accounts() -> dict[str, Any]:
    """可选账号：前端身份切换与权限演示用，任何人都能查看。"""
    return {"items": service.list_accounts()}


@router.get("/persons")
def list_persons(
    vessel: str | None = Query(default=None, description="按所属船舶过滤"),
    keyword: str | None = Query(default=None, description="按姓名或工号检索"),
) -> dict[str, Any]:
    """随船人员名册，附证件状态（有效/已过期）与当前在船状态。"""
    items = service.list_persons(vessel=vessel, keyword=keyword)
    for row in items:
        row["证件状态"] = "已过期" if _is_expired(row.get("证件到期日")) else "有效"
    return {"items": items, "total": len(items)}


@router.get("/persons/expired")
def list_expired_persons(
    vessel: str | None = Query(default=None, description="按所属船舶过滤"),
) -> dict[str, Any]:
    """证件过期的随船人员单独列出。"""
    items = service.expired_persons(vessel=vessel)
    return {"items": items, "total": len(items)}


@router.get("/aboard")
def list_aboard(
    vessel: str | None = Query(default=None, description="按所属船舶过滤"),
) -> dict[str, Any]:
    """当前还在船上的随船人员：替代值班本子上的口头确认。"""
    items = service.on_board_persons(vessel=vessel)
    return {"items": items, "total": len(items)}


@router.get("/plans", response_model=PageResult[dict])
def list_plans(
    vessel: str | None = Query(default=None, description="按所属船舶过滤"),
    status: str | None = Query(default=None, description="待确认、已确认"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """换班计划列表，任何账号都可查看。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_plans(vessel=vessel, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int) -> dict[str, Any]:
    entry = service.get_plan(plan_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"换班计划 {plan_id} 不存在或已归档")
    return entry


@router.post("/plans", response_model=ActionResult)
def create_plan(payload: dict[str, Any]) -> ActionResult:
    """登记换班计划：校验归属、名单人数、人员在船状态与证件名单。"""
    try:
        entry, message = service.create_plan(payload)
    except PermissionDenied as exc:
        raise _denied(exc) from exc
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/plans/{plan_id}/confirm", response_model=ActionResult)
def confirm_plan(plan_id: int, payload: dict[str, Any]) -> ActionResult:
    """确认换班计划：同一条计划重复确认只生效一次，确认后生成登离船记录。"""
    try:
        entry, message = service.confirm_plan(plan_id, payload)
    except PermissionDenied as exc:
        raise _denied(exc) from exc
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/records", response_model=PageResult[dict])
def list_records(
    vessel: str | None = Query(default=None, description="按所属船舶过滤"),
    direction: str | None = Query(default=None, description="登船、离船"),
    keyword: str | None = Query(default=None, description="按姓名或换班编号检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """登离船台账，与换班计划列表保持一致。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_records(
        vessel=vessel, direction=direction, keyword=keyword, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/records/consistency")
def records_consistency() -> dict[str, Any]:
    """核对已确认换班计划与登离船记录是否一一对应。"""
    return service.consistency_report()


@router.get("/duty-logs")
def list_duty_logs(
    vessel: str | None = Query(default=None, description="按所属船舶过滤"),
) -> dict[str, Any]:
    """既有值班本子记录：照旧只读，不提供新增、修改或删除入口。"""
    items = service.list_duty_logs(vessel=vessel)
    return {"items": items, "total": len(items)}
