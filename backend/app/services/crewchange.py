"""船员换班业务规则：船舶归属、提交权限、人数核对与确认幂等都收在这里。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "crewchange"
CREW_MODULE = "crewmember"
REQUIRED_FIELDS = ["所属船舶", "登船人员", "离船人员", "登船时间", "离船时间", "提交人"]
STATUS_ORDER = ["待确认", "已确认", "已取消"]
ACTIONS = ["确认换班", "取消换班"]

# 账号名册：值班人员只能提交本船计划，船员管理员不限船舶，其余角色只能查看。
ACCOUNTS: list[dict[str, str]] = [
    {"姓名": "王海", "角色": "值班人员", "所属船舶": "远洋轮"},
    {"姓名": "李霞", "角色": "值班人员", "所属船舶": "长江轮"},
    {"姓名": "赵敏", "角色": "船员管理员", "所属船舶": ""},
    {"姓名": "陈强", "角色": "闸口值守", "所属船舶": ""},
]

# 名单分隔符：登记时允许用顿号、逗号、分号或换行隔开多个人名。
_NAME_SEPARATORS = ["、", "，", ",", "；", ";", "\n"]


def split_names(raw: Any) -> list[str]:
    """把登船/离船名单拆成人名列表，兼容字符串和数组两种提交方式。"""
    if isinstance(raw, (list, tuple)):
        names = [str(item).strip() for item in raw]
    else:
        text = str(raw or "")
        for sep in _NAME_SEPARATORS:
            text = text.replace(sep, " ")
        names = [part.strip() for part in text.split(" ")]
    return [name for name in names if name]


class CrewchangeService:
    def list_accounts(self) -> list[dict[str, str]]:
        return [dict(account) for account in ACCOUNTS]

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        vessel: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("计划编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if vessel:
            rows = [row for row in rows if row.get("所属船舶") == vessel]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def list_crew(
        self,
        *,
        vessel: str | None = None,
        onboard: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = store.rows(CREW_MODULE)
        if vessel:
            rows = [row for row in rows if row.get("所属船舶") == vessel]
        if onboard:
            rows = [row for row in rows if row.get("在船状态") == onboard]
        return rows

    def expired_crew(self) -> list[dict[str, Any]]:
        """证件有效期早于今天的随船人员，单独列出方便先安排换证。"""
        today = date.today().isoformat()
        return [
            dict(row)
            for row in store.rows(CREW_MODULE)
            if str(row.get("证件有效期") or "") and str(row["证件有效期"]) < today
        ]

    # ---- 提交权限 ----

    def _permission_denied(self, operator: str, vessel: str) -> str | None:
        """返回 None 表示允许提交，否则返回拒绝原因。"""
        account = next((item for item in ACCOUNTS if item["姓名"] == operator), None)
        if account is None:
            return f"账号「{operator}」不在账号名册内，只有本船值班人员和船员管理员能提交换班"
        if account["角色"] == "船员管理员":
            return None
        if account["角色"] == "值班人员" and account["所属船舶"] == vessel:
            return None
        return (
            f"账号「{operator}」（{account['角色']}）不是船舶「{vessel}」的值班人员，"
            "也不是船员管理员，越权提交已拒绝"
        )

    # ---- 登记换班计划 ----

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        vessel = str(values["所属船舶"]).strip()
        operator = str(values["提交人"]).strip()
        denied = self._permission_denied(operator, vessel)
        if denied:
            return None, denied
        boarding = split_names(values.get("登船人员"))
        leaving = split_names(values.get("离船人员"))
        if len(boarding) != len(leaving):
            return None, (
                f"登船 {len(boarding)} 人、离船 {len(leaving)} 人，人数对不上，"
                "换班须保持船上人数一致，请核对登离船名单后再提交"
            )
        roster = {str(member.get("姓名")): member for member in store.rows(CREW_MODULE)}
        for name in boarding + leaving:
            member = roster.get(name)
            if member is None:
                return None, f"随船人员「{name}」不在名册内，请先登记随船人员再提交换班"
            if member.get("所属船舶") != vessel:
                return None, f"随船人员「{name}」属于「{member.get('所属船舶')}」，不能登记到「{vessel}」的换班计划"
        rows = store.rows(MODULE)
        plan_no = self._next_plan_no(rows)
        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "计划编号": plan_no,
            "所属船舶": vessel,
            "登船人员": boarding,
            "离船人员": leaving,
            "登船人数": len(boarding),
            "离船人数": len(leaving),
            "登船时间": str(values["登船时间"]).strip(),
            "离船时间": str(values["离船时间"]).strip(),
            "提交人": operator,
            "确认人": "",
            "确认时间": "",
            "status": STATUS_ORDER[0],
            "pending": True,
            "abnormal": False,
        }
        rows.append(entry)
        store.save(MODULE)
        return entry, f"换班计划 {plan_no} 已登记，待确认"

    def _next_plan_no(self, rows: list[dict[str, Any]]) -> str:
        used = 0
        for row in rows:
            plan_no = str(row.get("计划编号", ""))
            if plan_no.startswith("CREW-") and plan_no[5:].isdigit():
                used = max(used, int(plan_no[5:]))
        return f"CREW-{used + 1:04d}"

    # ---- 计划动作 ----

    def run_action(
        self, entry_id: int, action: str, operator: str
    ) -> tuple[dict[str, Any] | None, str, bool]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"换班计划 {entry_id} 不存在或已归档", False
        if action not in ACTIONS:
            return None, f"动作「{action}」不属于船员换班可执行范围", False
        denied = self._permission_denied(operator, str(entry.get("所属船舶") or ""))
        if denied:
            return None, denied, False
        if action == "确认换班":
            return self._confirm(entry, operator)
        return self._cancel(entry)

    def _confirm(self, entry: dict[str, Any], operator: str) -> tuple[dict[str, Any] | None, str, bool]:
        if entry.get("status") == "已确认":
            # 幂等：同一条计划重复确认只生效一次，确认人与确认时间保持首次结果。
            return entry, f"换班计划 {entry['计划编号']} 已确认过，重复确认不再生效", True
        if entry.get("status") == "已取消":
            return None, f"换班计划 {entry['计划编号']} 已取消，不能再确认", False
        entry["status"] = "已确认"
        entry["pending"] = False
        entry["确认人"] = operator
        entry["确认时间"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._apply_movement(entry)
        store.save(MODULE)
        store.save(CREW_MODULE)
        return entry, f"换班计划 {entry['计划编号']} 已确认，登离船记录已同步到随船人员名单", True

    def _cancel(self, entry: dict[str, Any]) -> tuple[dict[str, Any] | None, str, bool]:
        if entry.get("status") == "已确认":
            return None, f"换班计划 {entry['计划编号']} 已确认，登离船记录已生效，不能取消", False
        if entry.get("status") == "已取消":
            return entry, f"换班计划 {entry['计划编号']} 已是取消状态，未重复操作", True
        entry["status"] = "已取消"
        entry["pending"] = False
        entry["abnormal"] = True
        store.save(MODULE)
        return entry, f"换班计划 {entry['计划编号']} 已取消", True

    def _apply_movement(self, entry: dict[str, Any]) -> None:
        """按确认的登离船记录更新随船人员在船状态，保证名单与记录一致。"""
        vessel = entry.get("所属船舶")
        boarding = set(split_names(entry.get("登船人员")))
        leaving = set(split_names(entry.get("离船人员")))
        for member in store.rows(CREW_MODULE):
            if member.get("所属船舶") != vessel:
                continue
            name = str(member.get("姓名") or "")
            if name in boarding:
                member["在船状态"] = "在船"
                member["status"] = "在船"
            if name in leaving:
                member["在船状态"] = "已离船"
                member["status"] = "已离船"
