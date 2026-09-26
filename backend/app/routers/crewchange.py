"""船员换班接口：按随船人员登记换班计划与登离船时间，按船舶归属控制提交权限。"""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.crewchange import CrewchangeService

router = APIRouter(prefix="/api/crewchange", tags=["船员换班"])

service = CrewchangeService()

LIST_FIELDS = ["计划编号", "所属船舶", "登船人员", "离船人员", "登船人数", "离船人数", "登船时间", "离船时间", "提交人", "确认人", "确认时间"]
STATUSES = ["待确认", "已确认", "已取消"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按计划编号检索"),
    status: str | None = Query(default=None, description="待确认、已确认、已取消"),
    vessel: str | None = Query(default=None, description="按所属船舶过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """换班计划列表；所有账号都能查看，没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, vessel=vessel, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/accounts")
def list_accounts() -> dict[str, Any]:
    """账号名册：前端切换当前账号时用，不同角色的提交权限不同。"""
    return {"items": service.list_accounts()}


@router.get("/crew")
def list_crew(
    vessel: str | None = Query(default=None, description="按所属船舶过滤"),
    onboard: str | None = Query(default=None, description="在船、已离船"),
) -> dict[str, Any]:
    """随船人员名单：在船状态与已确认的登离船记录保持一致。"""
    items = service.list_crew(vessel=vessel, onboard=onboard)
    return {"items": items, "total": len(items)}


@router.get("/expired")
def expired_crew() -> dict[str, Any]:
    """证件过期的随船人员单独列出，提醒先换证再安排随船。"""
    items = service.expired_crew()
    return {"items": items, "total": len(items), "today": date.today().isoformat()}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出换班记录清单：返回当前全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "crewchange", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条换班计划；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"换班计划 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记换班计划：越权、人数对不上、人员不属于本船都会被拦下并说明原因。"""
    entry, message = service.create_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """确认或取消换班计划；确认动作幂等，同一条计划重复确认只生效一次。"""
    action = str(payload.values.get("action") or "").strip()
    operator = str(payload.values.get("操作人") or "").strip()
    entry, message, ok = service.run_action(entry_id, action, operator)
    return ActionResult(ok=ok, message=message, entry=entry)
